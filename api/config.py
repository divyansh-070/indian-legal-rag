"""
Configuration for Indian Legal RAG + Guidance API.
"""

import os
from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    # Ollama / Groq
    OLLAMA_HOST: str = os.getenv("OLLAMA_HOST", "https://api.groq.com/openai/v1")
    OLLAMA_MODEL: str = os.getenv("OLLAMA_MODEL", "llama-3.1-8b-instant")
    OLLAMA_FALLBACK_MODEL: str = os.getenv("OLLAMA_FALLBACK_MODEL", "llama-3.1-70b-versatile")
    OLLAMA_NUM_CTX: int = int(os.getenv("OLLAMA_NUM_CTX", "32768"))
    OLLAMA_NUM_PREDICT: int = int(os.getenv("OLLAMA_NUM_PREDICT", "4096"))
    OLLAMA_TEMPERATURE: float = float(os.getenv("OLLAMA_TEMPERATURE", "0.1"))

    # Embeddings
    EMBEDDING_MODEL: str = os.getenv("EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2")
    EMBEDDING_DIM: int = int(os.getenv("EMBEDDING_DIM", "384"))
    EMBEDDING_BATCH_SIZE: int = int(os.getenv("EMBEDDING_BATCH_SIZE", "32"))

    # Pinecone
    PINECONE_API_KEY: str = os.getenv("PINECONE_API_KEY", "")
    PINECONE_INDEX_NAME: str = os.getenv("PINECONE_INDEX_NAME", "legal-documents")
    PINECONE_ENVIRONMENT: str = os.getenv("PINECONE_ENVIRONMENT", "us-east-1")
    PINECONE_EMBEDDING_MODEL: str = os.getenv("PINECONE_EMBEDDING_MODEL", "multilingual-e5-large")

    # Neo4j
    NEO4J_URI: str = os.getenv("NEO4J_URI", "bolt://localhost:7687")
    NEO4J_USER: str = os.getenv("NEO4J_USER", "neo4j")
    NEO4J_PASSWORD: str = os.getenv("NEO4J_PASSWORD", "password")
    NEO4J_DATABASE: str = os.getenv("NEO4J_DATABASE", "neo4j")

    # Redis
    REDIS_URL: str = os.getenv("REDIS_URL", "")

    # API
    API_HOST: str = os.getenv("API_HOST", "0.0.0.0")
    API_PORT: int = int(os.getenv("API_PORT", "8000"))
    API_WORKERS: int = int(os.getenv("API_WORKERS", "1"))
    API_DEBUG: bool = os.getenv("API_DEBUG", "false").lower() == "true"
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")

    # JWT
    JWT_SECRET_KEY: str = os.getenv("JWT_SECRET_KEY", "change-me-in-production")
    JWT_ALGORITHM: str = os.getenv("JWT_ALGORITHM", "HS256")
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = int(os.getenv("JWT_ACCESS_TOKEN_EXPIRE_MINUTES", "15"))
    JWT_REFRESH_TOKEN_EXPIRE_DAYS: int = int(os.getenv("JWT_REFRESH_TOKEN_EXPIRE_DAYS", "7"))

    # CORS
    CORS_ORIGINS: str = os.getenv("CORS_ORIGINS", "http://localhost:3000")

    # Rate limiting
    RATE_LIMIT_GUEST: int = int(os.getenv("RATE_LIMIT_GUEST", "5"))
    RATE_LIMIT_FREE: int = int(os.getenv("RATE_LIMIT_FREE", "50"))
    RATE_LIMIT_PREMIUM: int = int(os.getenv("RATE_LIMIT_PREMIUM", "200"))
    RATE_LIMIT_WINDOW: int = int(os.getenv("RATE_LIMIT_WINDOW", "3600"))

    # Retrieval
    TOP_K_VECTOR: int = int(os.getenv("TOP_K_VECTOR", "20"))
    TOP_K_GRAPH: int = int(os.getenv("TOP_K_GRAPH", "10"))
    TOP_K_FINAL: int = int(os.getenv("TOP_K_FINAL", "8"))
    RERANK_ENABLED: bool = os.getenv("RERANK_ENABLED", "true").lower() == "true"
    RERANK_MODEL: str = os.getenv("RERANK_MODEL", "cross-encoder/ms-marco-MiniLM-L-6-v2")
    SIMILARITY_THRESHOLD: float = float(os.getenv("SIMILARITY_THRESHOLD", "0.65"))

    # GraphRAG
    GRAPH_HOPS: int = int(os.getenv("GRAPH_HOPS", "2"))
    GRAPH_MAX_NODES: int = int(os.getenv("GRAPH_MAX_NODES", "50"))

    # Critic
    CRITIC_ENABLED: bool = os.getenv("CRITIC_ENABLED", "true").lower() == "true"
    CRITIC_MODEL: str = os.getenv("CRITIC_MODEL", "llama-3.1-8b-instant")
    VERIFICATION_THRESHOLD: float = float(os.getenv("VERIFICATION_THRESHOLD", "0.7"))
    MAX_VERIFICATION_RETRIES: int = int(os.getenv("MAX_VERIFICATION_RETRIES", "2"))

    # Ingestion
    CHUNK_SIZE: int = int(os.getenv("CHUNK_SIZE", "512"))
    CHUNK_OVERLAP: int = int(os.getenv("CHUNK_OVERLAP", "64"))
    CHUNK_STRATEGY: str = os.getenv("CHUNK_STRATEGY", "semantic")
    PARSE_TABLES: bool = os.getenv("PARSE_TABLES", "true").lower() == "true"
    EXTRACT_DEFINITIONS: bool = os.getenv("EXTRACT_DEFINITIONS", "true").lower() == "true"
    EXTRACT_CITATIONS: bool = os.getenv("EXTRACT_CITATIONS", "true").lower() == "true"

    # Data paths
    DATA_RAW_DIR: str = os.getenv("DATA_RAW_DIR", "./data/raw")
    DATA_PROCESSED_DIR: str = os.getenv("DATA_PROCESSED_DIR", "./data/processed")
    DATA_SAMPLE_DIR: str = os.getenv("DATA_SAMPLE_DIR", "./data/sample")

    # Optional external APIs
    INDIAN_KANOON_API_KEY: Optional[str] = os.getenv("INDIAN_KANOON_API_KEY")
    GST_PORTAL_API_KEY: Optional[str] = os.getenv("GST_PORTAL_API_KEY")
    MCA_API_KEY: Optional[str] = os.getenv("MCA_API_KEY")

    # Feature flags
    ENABLE_STREAMING: bool = os.getenv("ENABLE_STREAMING", "true").lower() == "true"
    ENABLE_CACHING: bool = os.getenv("ENABLE_CACHING", "true").lower() == "true"
    CACHE_TTL: int = int(os.getenv("CACHE_TTL", "3600"))

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True
        extra = "allow"


settings = Settings()