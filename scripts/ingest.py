#!/usr/bin/env python3
"""
Ingest sample data into Pinecone and Neo4j.
"""
import asyncio
import json
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from api.config import settings
from api.services.vector_store import vector_store
from api.services.graph_store import graph_store


async def ingest_acts():
    """Ingest Acts into Pinecone and Neo4j."""
    print("📥 Ingesting Acts...")
    
    with open("data/sample/acts.json", "r", encoding="utf-8") as f:
        acts = json.load(f)
    
    # Prepare documents for Pinecone
    documents = []
    for act in acts:
        for section in act["sections"]:
            doc_id = f"{act['act_name']}_{section['number']}_{section.get('subsection', '')}".replace(" ", "_").replace("/", "_")
            documents.append({
                "id": doc_id,
                "text": f"Act: {act['act_name']}\nSection: {section['number']}{section.get('subsection', '')}\nMarginal Note: {section['marginal_note']}\n{section['text']}",
                "act_name": act["act_name"],
                "section_number": f"{section['number']}{section.get('subsection', '')}",
                "chapter": section.get("chapter", ""),
                "marginal_note": section.get("marginal_note", ""),
                "doc_type": "act_section",
                "metadata": {"act_short_name": act.get("short_name", ""), "year": act.get("year", "")}
            })
    
    # Upsert to Pinecone
    count = await vector_store.upsert_documents(documents)
    print(f"✅ Upserted {count} act sections to Pinecone")
    
    # Create Neo4j nodes
    for act in acts:
        await graph_store.create_act(
            name=act["act_name"],
            short_name=act.get("short_name", ""),
            year=act.get("year", 0)
        )
        
        for section in act["sections"]:
            await graph_store.create_section(
                act_name=act["act_name"],
                number=f"{section['number']}{section.get('subsection', '')}",
                text=section["text"],
                chapter=section.get("chapter", ""),
                marginal_note=section.get("marginal_note", "")
            )
    
    print(f"✅ Created Neo4j nodes for {len(acts)} acts")
    return True


async def ingest_cases():
    """Ingest Case Law into Pinecone and Neo4j."""
    print("📥 Ingesting Case Law...")
    
    with open("data/sample/cases.json", "r", encoding="utf-8") as f:
        cases = json.load(f)
    
    documents = []
    for case in cases:
        doc_id = case["citation"].replace(" ", "_").replace("/", "_")
        documents.append({
            "id": doc_id,
            "text": f"Case: {case['title']}\nCitation: {case['citation']}\nCourt: {case['court']}\nYear: {case['year']}\nHolding: {case['holding']}\nRatio: {case['ratio']}",
            "doc_type": "case_law",
            "citation": case["citation"],
            "court": case["court"],
            "act_name": case.get("act_referenced", ""),
            "section_number": case.get("section_referenced", ""),
            "metadata": {"title": case["title"], "year": case["year"]}
        })
    
    count = await vector_store.upsert_documents(documents)
    print(f"✅ Upserted {count} cases to Pinecone")
    
    # Neo4j
    for case in cases:
        await graph_store.create_case_law(
            citation=case["citation"],
            title=case["title"],
            court=case["court"],
            year=case["year"],
            holding=case["holding"],
            ratio=case["ratio"]
        )
    
    print(f"✅ Created Neo4j nodes for {len(cases)} cases")
    return True


async def ingest_notifications():
    """Ingest notifications."""
    print("📥 Ingesting Notifications...")
    
    with open("data/sample/notifications.json", "r", encoding="utf-8") as f:
        notifications = json.load(f)
    
    documents = []
    for notif in notifications:
        doc_id = notif["notification_number"].replace("/", "_").replace(" ", "_")
        documents.append({
            "id": doc_id,
            "text": f"Notification: {notif['title']}\nNumber: {notif['notification_number']}\nDate: {notif['date']}\n{notif['content']}",
            "doc_type": "notification",
            "source_url": "",
            "effective_date": notif["date"],
            "metadata": {"notification_number": notif["notification_number"]}
        })
    
    count = await vector_store.upsert_documents(documents)
    print(f"✅ Upserted {count} notifications to Pinecone")
    return True


async def main():
    import json
    print("=" * 50)
    print("📦 Indian Legal RAG - Data Ingestion")
    print("=" * 50)
    
    await vector_store.connect()
    await graph_store.connect()
    
    await ingest_acts()
    await ingest_cases()
    await ingest_notifications()
    
    print("\n✅ All data ingested successfully!")
    print("\n📊 Summary:")
    print("   - Acts & Sections: Ingested to Pinecone + Neo4j")
    print("   - Case Law: Ingested to Pinecone + Neo4j")
    print("   - Notifications: Ingested to Pinecone")
    return 0


if __name__ == "__main__":
    import json
    import os
    import sys
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    exit_code = asyncio.run(main())
    sys.exit(exit_code)