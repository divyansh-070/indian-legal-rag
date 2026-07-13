"""
Main FastAPI Application for Indian Legal RAG + Guidance.
"""

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.config import settings
from api.routes import health_router, query_router, graph_router, guide_router
from api.services.vector_store import vector_store
from api.services.graph_store import graph_store
from api.services.llm import llm_service


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    print("Starting Indian Legal RAG + Guidance API...")
    
    # Initialize services
    await vector_store.connect()
    print("✓ Qdrant connected")
    
    await graph_store.connect()
    print("✓ Neo4j connected")
    
    # Warm up LLM
    try:
        await llm_service.generate("Test", system="Respond with OK")
        print("✓ Ollama LLM ready")
    except Exception as e:
        print(f"⚠ Ollama warmup failed: {e}")
    
    yield
    
    # Shutdown
    print("Shutting down...")
    await vector_store.close()
    await graph_store.close()
    await llm_service.close()
    print("✓ All services closed")


app = FastAPI(
    title="Indian Legal RAG + Guidance API",
    description="Agentic RAG system for Indian legal research with self-correcting retrieval + plain-language legal guidance",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routes
from api.routes import health_router, query_router, graph_router, guide_router

app.include_router(health_router)
app.include_router(query_router, prefix="/api/v1")
app.include_router(graph_router, prefix="/api/v1/graph")
app.include_router(guide_router, prefix="/api/v1/guide")


@app.get("/")
async def root():
    return {
        "service": "Indian Legal RAG + Guidance API",
        "version": "1.0.0",
        "docs": "/docs",
        "health": "/health",
        "endpoints": {
            "research": "/api/v1/query",
            "guidance": "/api/v1/guide",
            "graph": "/api/v1/graph",
        },
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "api.main:app",
        host=settings.API_HOST,
        port=settings.API_PORT,
        reload=settings.API_DEBUG,
    )