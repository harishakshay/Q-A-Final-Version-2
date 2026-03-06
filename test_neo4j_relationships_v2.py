import json
import os
import sys

# Ensure current directory is in path
sys.path.append(os.getcwd())

from pipeline import MemoryPipeline
from knowledge_graph import KnowledgeGraph

def test_neo4j_integration():
    print("--- START VERIFICATION ---")
    
    print("Initializing KnowledgeGraph directly...")
    try:
        kg = KnowledgeGraph()
        if kg.driver:
            print("SUCCESS: KnowledgeGraph initialized with driver")
        else:
            print("FAILURE: KnowledgeGraph driver is None")
            return
    except Exception as e:
        print(f"EXCEPTION during KG init: {e}")
        return

    print("\nInitializing Pipeline...")
    try:
        pipeline = MemoryPipeline()
        if pipeline.knowledge_graph and pipeline.knowledge_graph.driver:
            print("SUCCESS: Pipeline initialized with KG driver")
        else:
            print("FAILURE: Pipeline KG driver is None")
    except Exception as e:
        print(f"EXCEPTION during Pipeline init: {e}")
        return

    print("\nTriggering Knowledge Graph Update Step 4...")
    try:
        stats = pipeline.update_knowledge_graph()
        print(f"Sync Results Stats: {stats}")
    except Exception as e:
        print(f"EXCEPTION during update: {e}")

    print("\nQuerying Relationships...")
    with pipeline.knowledge_graph.driver.session() as session:
        query = """
        MATCH (n)
        OPTIONAL MATCH (n)-[r]->(m)
        RETURN 
            count(DISTINCT labels(n)) as node_labels,
            count(DISTINCT type(r)) as rel_types,
            count(r) as total_rels
        """
        res = session.run(query).single()
        print(f"Graph Metrics: Labels: {res['node_labels']}, Types: {res['rel_types']}, Total Rels: {res['total_rels']}")

    pipeline.cleanup()
    print("--- END VERIFICATION ---")

if __name__ == "__main__":
    test_neo4j_integration()
