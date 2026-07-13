"""
Health Check Routes
"""

from fastapi import APIRouter
from typing import Dict, Any

from api.services.vector_store import vector_store
from api.services.graph_store import graph_store
from api.services.llm import llm_service
from api.config import settings


router = APIRouter(prefix="/health", tags=["health"])


@router.get("")
async def health_check() -> Dict[str, Any]:
    """Comprehensive health check for all services."""
    checks = {}
    overall = "healthy"
    
    # Check Qdrant
    try:
        count = await vector_store.count()
        checks["qdrant"] = {
            "status": "healthy",
            "collection": settings.QDRANT_COLLECTION,
            "document_count": count,
        }
    except Exception as e:
        checks["qdrant"] = {"status": "unhealthy", "error": str(e)}
        overall = "degraded"
    
    # Check Neo4j
    try:
        result = await graph_store.run_cypher("RETURN 1 as test")
        checks["neo4j"] = {
            "status": "healthy",
            "database": settings.NEO4J_DATABASE,
        }
    except Exception as e:
        checks["neo4j"] = {"status": "unhealthy", "error": str(e)}
        overall = "degraded"
    
    # Check Ollama
    try:
        await llm_service.generate("ping", system="pong")
        checks["ollama"] = {
            "status": "healthy",
            "model": settings.OLLAMA_MODEL,
            "fallback": settings.OLLAMA_FALLBACK_MODEL,
        }
    except Exception as e:
        checks["ollama"] = {"status": "unhealthy", "error": str(e)}
        overall = "degraded"
    
    return {
        "status": overall,
        "version": "1.0.0",
        "checks": checks,
        "config": {
            "top_k_final": settings.TOP_K_FINAL,
            "critic_enabled": settings.CRITIC_ENABLED,
        },
    }


@router.get("/ready")
async def readiness() -> Dict[str, str]:
    """Kubernetes readiness probe."""
    return {"status": "ready"}


@router.get("/live")
async def liveness() -> Dict[str, str]:
    """Kubernetes liveness probe."""
    return {"status": "alive"}