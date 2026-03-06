import json
import os
from pipeline import MemoryPipeline

def test_neo4j_integration():
    print("Initializing Pipeline...")
    pipeline = MemoryPipeline()
    
    if not pipeline.knowledge_graph or not pipeline.knowledge_graph.driver:
        print("Neo4j not connected. Please ensure Neo4j is running.")
        return

    print("\nTriggering Knowledge Graph Update Stage 4...")
    # This will use cached posts if fetch hasn't run in this session
    stats = pipeline.update_knowledge_graph()
    
    print("\nGraph Sync Results:")
    print(json.dumps(stats, indent=2))
    
    # Simple check for relationships
    with pipeline.knowledge_graph.driver.session() as session:
        # Check Categories
        res = session.run("MATCH ()-[r:IN_CATEGORY]->() RETURN count(r)").single()
        print(f"IN_CATEGORY relationships: {res[0]}")
        
        # Check Tags
        res = session.run("MATCH ()-[r:HAS_TAG]->() RETURN count(r)").single()
        print(f"HAS_TAG relationships: {res[0]}")
        
        # Check Chronology
        res = session.run("MATCH ()-[r:NEXT_POST]->() RETURN count(r)").single()
        print(f"NEXT_POST relationships: {res[0]}")

        # Check Similarity
        res = session.run("MATCH ()-[r:SIMILAR_TO]->() RETURN count(r)").single()
        print(f"SIMILAR_TO relationships: {res[0]}")

    pipeline.cleanup()

if __name__ == "__main__":
    test_neo4j_integration()
