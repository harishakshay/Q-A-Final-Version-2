import json
import os
import sys

# Ensure current directory is in path
sys.path.append(os.getcwd())

from knowledge_graph import KnowledgeGraph
import config

def rebuild():
    print("=== STARTING CLEAN GRAPH REBUILD FROM PAGES_METADATA.JSON ===")
    
    kg = KnowledgeGraph()
    if not kg.driver:
        print("Error: Neo4j not connected")
        return

    # 1. Clear everything
    print("\n[Step 1/4] DETACH DELETE all existing nodes and edges...")
    kg.clear_graph()

    # 2. Load pages_metadata.json (now includes categories)
    path = config.PAGES_METADATA_PATH
    if not os.path.exists(path):
        print(f"Error: {path} not found at {path}")
        kg.close()
        return
        
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    print(f"Loaded {len(data)} entries from pages_metadata.json")

    # 3. Ingest Nodes and Mandatory Relationships
    print("\n[Step 2/4] Ingesting Articles, Categories, Years, and Taxonomy...")
    kg.ingest_pages_metadata(data)

    # 4. Build Chronological Chain
    print("\n[Step 3/4] Building Chronological Chain (NEXT_POST)...")
    kg.link_chronologically()

    # 5. Final Verification
    print("\n[Step 4/4] Fetching Final Stats...")
    stats = kg.get_graph_stats()
    print("\nFinal Knowledge Graph State:")
    print(json.dumps(stats, indent=2))

    kg.close()
    print("\n=== GRAPH REBUILD SUCCESSFUL ===")

if __name__ == "__main__":
    rebuild()
