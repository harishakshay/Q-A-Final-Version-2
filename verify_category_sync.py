import json
import os
import sys

# Ensure current directory is in path
sys.path.append(os.getcwd())

from knowledge_graph import KnowledgeGraph
import config

def verify():
    print("=== VERIFYING CATEGORY SYNC FROM PAGES_METADATA.JSON ===")
    
    kg = KnowledgeGraph()
    if not kg.driver:
        print("Error: Neo4j not connected")
        return

    # 1. Load pages_metadata.json
    path = config.PAGES_METADATA_PATH
    if not os.path.exists(path):
        print(f"Error: {path} not found")
        return
        
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    print(f"Loaded {len(data)} entries from pages_metadata.json")

    # 2. Ingest
    print("Ingesting metadata into Neo4j...")
    kg.ingest_pages_metadata(data)

    # 3. Verify in Neo4j
    with kg.driver.session() as session:
        # Get count of Category nodes
        cat_count = session.run("MATCH (c:Category) RETURN count(c)").single()[0]
        # Get count of IN_CATEGORY relationships
        rel_count = session.run("MATCH ()-[r:IN_CATEGORY]->() RETURN count(r)").single()[0]
        
        print(f"\nVerification Results:")
        print(f"Category Nodes: {cat_count}")
        print(f"IN_CATEGORY Relationships: {rel_count}")
        
        if cat_count > 0 and rel_count > 0:
            print("\nSUCCESS: Categories and relationships are present in the graph!")
        else:
            print("\nFAILURE: Category data missing from graph.")

    kg.close()

if __name__ == "__main__":
    verify()
