#!/usr/bin/env python3
"""
Initialize database connections and create schema for Pinecone + Neo4j.
"""
import asyncio
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from api.config import settings
from api.services.vector_store import vector_store
from api.services.graph_store import graph_store


async def init_pinecone():
    """Initialize Pinecone index with integrated embedding."""
    print("🔧 Initializing Pinecone...")
    try:
        await vector_store.connect()
        print(f"✅ Pinecone connected: {settings.PINECONE_INDEX_NAME}")
        count = await vector_store.count()
        print(f"   Current document count: {count}")
        return True
    except Exception as e:
        print(f"❌ Pinecone init failed: {e}")
        return False


async def init_neo4j():
    """Initialize Neo4j connection and create constraints/indexes."""
    print("🔧 Initializing Neo4j...")
    try:
        await graph_store.connect()
        print("✅ Neo4j connected")
        
        # Create constraints and indexes
        constraints = [
            "CREATE CONSTRAINT section_unique IF NOT EXISTS FOR (s:Section) REQUIRE (s.act_name, s.number) IS UNIQUE",
            "CREATE CONSTRAINT act_unique IF NOT EXISTS FOR (a:Act) REQUIRE a.name IS UNIQUE",
            "CREATE CONSTRAINT case_unique IF NOT EXISTS FOR (c:CaseLaw) REQUIRE c.citation IS UNIQUE",
        ]
        
        for constraint in constraints:
            try:
                await graph_store.run_query(constraint)
                print(f"   ✅ Constraint created")
            except Exception as e:
                print(f"   ⚠️ Constraint warning: {e}")
        
        return True
    except Exception as e:
        print(f"❌ Neo4j init failed: {e}")
        return False


async def main():
    print("=" * 50)
    print("🚀 Indian Legal RAG - Database Initialization")
    print("=" * 50)
    
    print(f"📋 Configuration:")
    print(f"   Pinecone Index: {settings.PINECONE_INDEX_NAME}")
    print(f"   Embedding Model: {settings.PINECONE_EMBEDDING_MODEL}")
    print(f"   Embedding Dim: {settings.EMBEDDING_DIM}")
    print(f"   Neo4j URI: {settings.NEO4J_URI}")
    print()
    
    # Initialize services
    pinecone_ok = await init_pinecone()
    neo4j_ok = await init_neo4j()
    
    if pinecone_ok and neo4j_ok:
        print("\n✅ All databases initialized successfully!")
        return 0
    else:
        print("\n❌ Some databases failed to initialize")
        return 1


if __name__ == "__main__":
    import sys
    import os
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    exit_code = asyncio.run(main())
    sys.exit(exit_code)