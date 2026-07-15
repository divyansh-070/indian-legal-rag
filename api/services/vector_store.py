"""
Vector Store Service — Pinecone wrapper with integrated embedding (no local model).
Uses Pinecone Serverless integrated embedding API - zero local memory for embeddings.
"""

import asyncio
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime
import json

from pinecone import Pinecone, ServerlessSpec

from api.config import settings


@dataclass
class RetrievedChunk:
    """A retrieved document chunk with metadata."""
    id: str
    text: str
    score: float
    act_name: Optional[str] = None
    section_number: Optional[str] = None
    subsection: Optional[str] = None
    chapter: Optional[str] = None
    marginal_note: Optional[str] = None
    doc_type: Optional[str] = None
    source_url: Optional[str] = None
    effective_date: Optional[str] = None
    jurisdiction: str = "India"
    court: Optional[str] = None
    citation: Optional[str] = None
    metadata: Dict[str, Any] = None

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


class PineconeVectorStore:
    """Pinecone-based vector store with integrated embedding (no local model)."""

    def __init__(self):
        self.pc: Optional[Pinecone] = None
        self.index = None
        self._connected = False
        self._embedding_dim = settings.EMBEDDING_DIM

    async def connect(self):
        """Initialize Pinecone client and index with integrated embedding."""
        if self._connected:
            return

        try:
            # Initialize Pinecone client
            self.pc = Pinecone(api_key=settings.PINECONE_API_KEY)

            # Check if index exists, create if not
            index_name = settings.PINECONE_INDEX_NAME
            existing_indexes = [idx.name for idx in self.pc.list_indexes()]

            if index_name not in existing_indexes:
                # Create index with integrated embedding (serverless)
                # Use Pinecone's integrated embedding
                self.pc.create_index(
                    name=index_name,
                    dimension=settings.EMBEDDING_DIM,
                    metric="cosine",
                    spec=ServerlessSpec(
                        cloud="aws",
                        region="us-east-1"
                    ),
                    # Use Pinecone's integrated embedding
                    embedding_config={
                        "model": settings.PINECONE_EMBEDDING_MODEL,
                        "field_map": {"text": "text"}
                    }
                )
                # Wait for index to be ready
                import time
                while not self.pc.describe_index(index_name).status["ready"]:
                    time.sleep(1)

            # Connect to index
            self.index = self.pc.Index(index_name)

            self._connected = True
            print(f"✅ Pinecone connected: {index_name} (integrated embedding: {settings.PINECONE_EMBEDDING_MODEL})")

        except Exception as e:
            print(f"❌ Pinecone connection failed: {e}")
            raise

    async def close(self):
        """Close connections."""
        if self.index:
            self.index.close()
        self._connected = False

    def _prepare_metadata(self, doc: Dict[str, Any]) -> Dict[str, Any]:
        """Prepare metadata for Pinecone (string/number/bool only)."""
        return {
            "text": doc["text"][:8000],
            "act_name": doc.get("act_name", "") or "",
            "section_number": doc.get("section_number", "") or "",
            "subsection": doc.get("subsection", "") or "",
            "chapter": doc.get("chapter", "") or "",
            "marginal_note": doc.get("marginal_note", "") or "",
            "doc_type": doc.get("doc_type", "") or "",
            "source_url": doc.get("source_url", "") or "",
            "effective_date": doc.get("effective_date", "") or "",
            "jurisdiction": doc.get("jurisdiction", "India") or "India",
            "court": doc.get("court", "") or "",
            "citation": doc.get("citation", "") or "",
            **{k: v for k, v in doc.get("metadata", {}).items()
               if isinstance(v, (str, int, float, bool)) and k != "text"}
        }

    async def upsert_documents(self, documents: List[Dict[str, Any]]) -> int:
        """Upsert documents to Pinecone using integrated embedding."""
        if not self._connected:
            await self.connect()

        if not documents:
            return 0

        # Prepare records for Pinecone integrated embedding
        records = []
        for doc in documents:
            records.append({
                "id": doc["id"],
                "text": doc["text"],
                **self._prepare_metadata(doc)
            })

        # Upsert in batches
        batch_size = 96  # Pinecone limit for integrated embedding
        total_upserted = 0

        for i in range(0, len(records), batch_size):
            batch = records[i:i + batch_size]
            self.index.upsert_records(namespace="", records=batch)
            total_upserted += len(batch)

        print(f"✅ Upserted {total_upserted} documents to Pinecone (integrated embedding)")
        return total_upserted

    async def search(
        self,
        query: str,
        top_k: int = 20,
        filter_dict: Optional[Dict[str, Any]] = None
    ) -> List[RetrievedChunk]:
        """Search using Pinecone integrated embedding."""
        if not self._connected:
            await self.connect()

        # Build filter
        filter_expr = None
        if filter_dict:
            filter_expr = {}
            for k, v in filter_dict.items():
                if isinstance(v, list):
                    filter_expr[k] = {"$in": v}
                else:
                    filter_expr[k] = {"$eq": v}

        # Search using integrated embedding (query as text)
        results = self.index.search(
            namespace="",
            query={
                "top_k": top_k,
                "inputs": {"text": query}
            },
            filter=filter_expr,
            fields=["text", "act_name", "section_number", "subsection", "chapter",
                    "marginal_note", "doc_type", "source_url", "effective_date",
                    "jurisdiction", "court", "citation"]
        )

        # Convert to RetrievedChunk
        chunks = []
        for hit in results.get("result", {}).get("hits", []):
            fields = hit.get("fields", {})
            chunks.append(RetrievedChunk(
                id=hit.get("id", ""),
                text=fields.get("text", ""),
                score=hit.get("score", 0.0),
                act_name=fields.get("act_name"),
                section_number=fields.get("section_number"),
                subsection=fields.get("subsection"),
                chapter=fields.get("chapter"),
                marginal_note=fields.get("marginal_note"),
                doc_type=fields.get("doc_type"),
                source_url=fields.get("source_url"),
                effective_date=fields.get("effective_date"),
                jurisdiction=fields.get("jurisdiction", "India"),
                court=fields.get("court"),
                citation=fields.get("citation"),
                metadata=fields
            ))

        return chunks

    async def get_section(
        self,
        act_name: str,
        section_number: str
    ) -> Optional[RetrievedChunk]:
        """Get specific section by act and section number."""
        if not self._connected:
            await self.connect()

        results = self.index.search(
            namespace="",
            query={
                "top_k": 1,
                "inputs": {"text": f"{act_name} section {section_number}"}
            },
            filter={
                "act_name": {"$eq": act_name},
                "section_number": {"$eq": section_number}
            },
            fields=["text", "act_name", "section_number", "subsection", "chapter",
                    "marginal_note", "doc_type", "source_url", "effective_date",
                    "jurisdiction", "court", "citation"]
        )

        hits = results.get("result", {}).get("hits", [])
        if hits:
            hit = hits[0]
            fields = hit.get("fields", {})
            return RetrievedChunk(
                id=hit.get("id", ""),
                text=fields.get("text", ""),
                score=hit.get("score", 0.0),
                act_name=fields.get("act_name"),
                section_number=fields.get("section_number"),
                subsection=fields.get("subsection"),
                chapter=fields.get("chapter"),
                marginal_note=fields.get("marginal_note"),
                doc_type=fields.get("doc_type"),
                source_url=fields.get("source_url"),
                effective_date=fields.get("effective_date"),
                jurisdiction=fields.get("jurisdiction", "India"),
                court=fields.get("court"),
                citation=fields.get("citation"),
                metadata=fields
            )
        return None

    async def count(self) -> int:
        """Get total document count."""
        if not self._connected:
            await self.connect()
        stats = self.index.describe_index_stats()
        return stats.total_vector_count

    async def delete_all(self) -> bool:
        """Delete all vectors (use with caution)."""
        if not self._connected:
            await self.connect()
        self.index.delete(delete_all=True, namespace="")
        return True


# Global instance
vector_store = PineconeVectorStore()

# Backward compatibility alias for retriever.py
SearchResult = RetrievedChunk