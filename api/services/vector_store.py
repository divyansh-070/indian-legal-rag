"""
Vector Store Service — Qdrant wrapper for semantic search.
Handles document embeddings, upsert, and hybrid retrieval.
"""

import asyncio
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
from uuid import uuid4

from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    VectorParams,
    PointStruct,
    Filter,
    FieldCondition,
    MatchValue,
    SearchRequest,
    ScoredPoint,
    PayloadSchemaType,
)

from api.config import settings
from api.services.llm import llm_service


@dataclass
class SearchResult:
    """Unified search result."""
    id: str
    score: float
    payload: Dict[str, Any]
    source: str  # "vector" | "keyword"


class VectorStore:
    """Async wrapper around Qdrant for legal document storage."""
    
    COLLECTION_NAME = "legal_documents"
    VECTOR_SIZE = 768  # bge-m3 / nomic-embed-text
    
    def __init__(
        self,
        host: str = None,
        port: int = None,
        collection_name: str = None,
    ):
        self.host = host or settings.QDRANT_HOST
        self.port = port or settings.QDRANT_PORT
        self.collection_name = collection_name or settings.QDRANT_COLLECTION
        self._client: Optional[QdrantClient] = None
    
    async def connect(self):
        """Initialize Qdrant client and create collection if needed."""
        self._client = QdrantClient(host=self.host, port=self.port)
        
        # Create collection if not exists
        collections = self._client.get_collections().collections
        if not any(c.name == self.collection_name for c in collections):
            self._client.create_collection(
                collection_name=self.collection_name,
                vectors_config=VectorParams(
                    size=self.VECTOR_SIZE,
                    distance=Distance.COSINE,
                ),
            )
        
        # Create payload indexes for filtering
        indexes = [
            ("act_name", PayloadSchemaType.KEYWORD),
            ("section_number", PayloadSchemaType.KEYWORD),
            ("doc_type", PayloadSchemaType.KEYWORD),
            ("court", PayloadSchemaType.KEYWORD),
            ("effective_date", PayloadSchemaType.DATETIME),
        ]
        
        for field_name, field_type in indexes:
            try:
                self._client.create_payload_index(
                    collection_name=self.collection_name,
                    field_name=field_name,
                    field_schema=field_type,
                )
            except Exception:
                pass  # May already exist
    
    async def close(self):
        if self._client:
            self._client.close()
            self._client = None
    
    def _get_client(self) -> QdrantClient:
        if not self._client:
            raise RuntimeError("VectorStore not connected. Call connect() first.")
        return self._client
    
    async def upsert_documents(
        self,
        documents: List[Dict[str, Any]],
        batch_size: int = 100,
    ) -> int:
        """Upsert documents with embeddings."""
        client = self._get_client()
        points = []
        
        for doc in documents:
            # Generate embedding
            text_for_embedding = self._build_embedding_text(doc)
            embedding = await llm_service.embed(text_for_embedding)
            
            if not embedding:
                continue
            
            point = PointStruct(
                id=doc.get("id") or str(uuid4()),
                vector=embedding,
                payload={
                    "text": doc["text"],
                    "act_name": doc.get("act_name"),
                    "section_number": doc.get("section_number"),
                    "subsection": doc.get("subsection"),
                    "chapter": doc.get("chapter"),
                    "marginal_note": doc.get("marginal_note"),
                    "doc_type": doc.get("doc_type", "act"),
                    "source_url": doc.get("source_url"),
                    "effective_date": doc.get("effective_date"),
                    "jurisdiction": doc.get("jurisdiction", "India"),
                    "court": doc.get("court"),
                    "citation": doc.get("citation"),
                    "metadata": doc.get("metadata", {}),
                },
            )
            points.append(point)
        
        # Batch upsert
        for i in range(0, len(points), batch_size):
            batch = points[i:i + batch_size]
            client.upsert(collection_name=self.collection_name, points=batch)
        
        return len(points)
    
    def _build_embedding_text(self, doc: Dict[str, Any]) -> str:
        """Build text for embedding from document fields."""
        parts = []
        if doc.get("act_name"):
            parts.append(f"Act: {doc['act_name']}")
        if doc.get("section_number"):
            parts.append(f"Section {doc['section_number']}")
        if doc.get("subsection"):
            parts.append(f"Sub-section {doc['subsection']}")
        if doc.get("chapter"):
            parts.append(f"Chapter {doc['chapter']}")
        parts.append(doc["text"])
        return "\n".join(parts)
    
    async def search(
        self,
        query: str,
        limit: int = 10,
        filters: Dict[str, Any] = None,
        score_threshold: float = 0.55,
    ) -> List[SearchResult]:
        """Semantic vector search."""
        client = self._get_client()
        
        # Generate query embedding
        query_embedding = await llm_service.embed(query)
        if not query_embedding:
            return []
        
        # Build filter
        qdrant_filter = None
        if filters:
            conditions = []
            for key, value in filters.items():
                if value is not None:
                    conditions.append(
                        FieldCondition(key=key, match=MatchValue(value=value))
                    )
            if conditions:
                qdrant_filter = Filter(must=conditions)
        
        # Search
        results = client.search(
            collection_name=self.collection_name,
            query_vector=query_embedding,
            query_filter=qdrant_filter,
            limit=limit,
            score_threshold=score_threshold,
            with_payload=True,
        )
        
        return [
            SearchResult(
                id=str(r.id),
                score=r.score,
                payload=r.payload,
                source="vector",
            )
            for r in results
        ]
    
    async def search_by_section(
        self,
        act_name: str,
        section_number: str,
        limit: int = 5,
    ) -> List[SearchResult]:
        """Exact section lookup."""
        client = self._get_client()
        
        results = client.scroll(
            collection_name=self.collection_name,
            scroll_filter=Filter(
                must=[
                    FieldCondition(key="act_name", match=MatchValue(value=act_name)),
                    FieldCondition(key="section_number", match=MatchValue(value=section_number)),
                ]
            ),
            limit=limit,
            with_payload=True,
        )[0]
        
        return [
            SearchResult(
                id=str(r.id),
                score=1.0,
                payload=r.payload,
                source="keyword",
            )
            for r in results
        ]
    
    async def get_document(self, doc_id: str) -> Optional[SearchResult]:
        """Retrieve single document by ID."""
        client = self._get_client()
        results = client.retrieve(
            collection_name=self.collection_name,
            ids=[doc_id],
            with_payload=True,
        )
        if results:
            r = results[0]
            return SearchResult(
                id=str(r.id),
                score=1.0,
                payload=r.payload,
                source="keyword",
            )
        return None
    
    async def delete_by_filter(self, filters: Dict[str, Any]) -> int:
        """Delete documents matching filter."""
        client = self._get_client()
        conditions = [
            FieldCondition(key=k, match=MatchValue(value=v))
            for k, v in filters.items()
            if v is not None
        ]
        if not conditions:
            return 0
        
        result = client.delete(
            collection_name=self.collection_name,
            points_selector=Filter(must=conditions),
        )
        return result.deleted_count if result else 0
    
    async def count(self, filters: Dict[str, Any] = None) -> int:
        """Count documents matching filter."""
        client = self._get_client()
        
        qdrant_filter = None
        if filters:
            conditions = [
                FieldCondition(key=k, match=MatchValue(value=v))
                for k, v in filters.items()
                if v is not None
            ]
            if conditions:
                qdrant_filter = Filter(must=conditions)
        
        result = client.count(
            collection_name=self.collection_name,
            count_filter=qdrant_filter,
            exact=True,
        )
        return result.count


# Global instance
vector_store = VectorStore()