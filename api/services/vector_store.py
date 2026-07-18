"""
Vector Store Service — Pinecone wrapper using Inference API for embeddings.
Uses Pinecone Inference API for embeddings + regular upsert/query operations.
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
    """Pinecone-based vector store using Inference API for embeddings."""

    def __init__(self):
        self.pc: Optional[Pinecone] = None
        self.index = None
        self._connected = False
        self._embedding_dim = settings.EMBEDDING_DIM

    async def connect(self):
        """Initialize Pinecone client and index."""
        if self._connected:
            return

        try:
            # Initialize Pinecone client
            self.pc = Pinecone(api_key=settings.PINECONE_API_KEY)

            # Check if index exists, create if not
            index_name = settings.PINECONE_INDEX_NAME
            existing_indexes = [idx.name for idx in self.pc.list_indexes()]

            if index_name not in existing_indexes:
                # Create index (standard, no integrated embedding)
                self.pc.create_index(
                    name=index_name,
                    dimension=settings.EMBEDDING_DIM,
                    metric="cosine",
                    spec=ServerlessSpec(
                        cloud="aws",
                        region="us-east-1"
                    )
                )
                # Wait for index to be ready
                import time
                while not self.pc.describe_index(index_name).status["ready"]:
                    time.sleep(1)

            # Connect to index
            self.index = self.pc.Index(index_name)

            self._connected = True
            print(f"✅ Pinecone connected: {index_name} (using Inference API for embeddings)")

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

    async def _get_embeddings(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings using Pinecone Inference API."""
        if not self.pc or not hasattr(self.pc, 'inference') or not hasattr(self.pc.inference, 'embed'):
            raise RuntimeError("Inference not available. Check Pinecone version.")
        
        # Use Pinecone Inference API for embeddings
        response = self.pc.inference.embed(
            model=settings.PINECONE_EMBEDDING_MODEL,
            inputs=texts,
            parameters={"input_type": "passage", "truncate": "END"}
        )
        return [d["values"] for d in response.data]

    async def upsert_documents(self, documents: List[Dict[str, Any]]) -> int:
        """Upsert documents to Pinecone using Inference API for embeddings."""
        if not self._connected:
            await self.connect()

        if not documents:
            return 0

        # Prepare texts for embedding
        texts = [doc["text"] for doc in documents]
        embeddings = await self._get_embeddings(texts)

        # Prepare vectors for upsert
        vectors = []
        for i, (doc, embedding) in enumerate(zip(documents, embeddings)):
            vectors.append({
                "id": doc["id"],
                "values": embedding,
                "metadata": self._prepare_metadata(doc)
            })

        # Upsert in batches
        batch_size = 100
        total_upserted = 0

        for i in range(0, len(vectors), batch_size):
            batch = vectors[i:i + batch_size]
            self.index.upsert(vectors=batch, namespace="")
            total_upserted += len(batch)

        print(f"✅ Upserted {total_upserted} documents to Pinecone (using Inference API)")
        return total_upserted

    async def search(
        self,
        query: str,
        top_k: int = 20,
        filter_dict: Optional[Dict[str, Any]] = None
    ) -> List[RetrievedChunk]:
        """Search using Pinecone with query embedding from Inference API."""
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

        # Embed query
        query_embedding = (await self._get_embeddings([query]))[0]

        # Search
        results = self.index.query(
            vector=query_embedding,
            top_k=top_k,
            filter=filter_expr,
            include_metadata=True,
            include_values=False
        )

        # Convert to RetrievedChunk
        chunks = []
        for match in results.matches:
            metadata = match.metadata or {}
            chunks.append(RetrievedChunk(
                id=match.id,
                text=metadata.get("text", ""),
                score=match.score,
                act_name=metadata.get("act_name"),
                section_number=metadata.get("section_number"),
                subsection=metadata.get("subsection"),
                chapter=metadata.get("chapter"),
                marginal_note=metadata.get("marginal_note"),
                doc_type=metadata.get("doc_type"),
                source_url=metadata.get("source_url"),
                effective_date=metadata.get("effective_date"),
                jurisdiction=metadata.get("jurisdiction", "India"),
                court=metadata.get("court"),
                citation=metadata.get("citation"),
                metadata=metadata
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

        # Embed query
        query_text = f"{act_name} section {section_number}"
        query_embedding = (await self._get_embeddings([query_text]))[0]

        # Search with exact filter
        results = self.index.query(
            vector=query_embedding,
            top_k=1,
            filter={
                "act_name": {"$eq": act_name},
                "section_number": {"$eq": section_number}
            },
            include_metadata=True,
            include_values=False
        )

        if results.matches:
            match = results.matches[0]
            metadata = match.metadata or {}
            return RetrievedChunk(
                id=match.id,
                text=metadata.get("text", ""),
                score=match.score,
                act_name=metadata.get("act_name"),
                section_number=metadata.get("section_number"),
                subsection=metadata.get("subsection"),
                chapter=metadata.get("chapter"),
                marginal_note=metadata.get("marginal_note"),
                doc_type=metadata.get("doc_type"),
                source_url=metadata.get("source_url"),
                effective_date=metadata.get("effective_date"),
                jurisdiction=metadata.get("jurisdiction", "India"),
                court=metadata.get("court"),
                citation=metadata.get("citation"),
                metadata=metadata
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
        self.index.delete(delete_all=True)
        return True


# Global instance
vector_store = PineconeVectorStore()

# Backward compatibility alias for retriever.py
SearchResult = RetrievedChunk