import os
import json
import time
from pipeline import MemoryPipeline
from data_manager import DataManager
from semantic_memory import SemanticMemory
from knowledge_graph import KnowledgeGraph
import config

def verify_end_to_end():
    print("============================================================")
    print("             END-TO-END SYSTEM VERIFICATION")
    print("============================================================\n")

    pipeline = MemoryPipeline()
    dm = DataManager()
    
    # 1. Create Test CSV
    test_filename = "e2e_test_metrics.csv"
    test_filepath = os.path.join(config.UPLOAD_DIR, test_filename)
    
    csv_content = "url,clicks,impressions,ctr,position\n"
    csv_content += "https://flowgenius.in/ai-guide/,50,1000,0.05,4.2\n"
    csv_content += "https://flowgenius.in/seo-tips/,10,500,0.02,12.5\n"
    
    with open(test_filepath, "w") as f:
        f.write(csv_content)
    print(f"[1] Created test CSV: {test_filename}")

    # 2. Register File
    file_entry = dm.add_file(test_filename, "csv", test_filepath)
    file_id = file_entry["id"]
    print(f"[2] Registered file in manifest. ID: {file_id}")

    # 3. Process File (The New Automated Pipeline)
    print(f"[3] Running automated pipeline for {file_id}...")
    try:
        pipeline.process_file_pipeline(file_id, dm)
        print("[OK] Pipeline execution finished successfully")
    except Exception as e:
        print(f"[FAIL] Pipeline execution failed: {e}")
        return

    # 4. Verify Manifest Status
    updated_file = dm.get_file(file_id)
    print(f"\n[4] Manifest Verification:")
    print(f"    - Status: {updated_file['status']}")
    print(f"    - Converted Path: {updated_file.get('converted_path')}")
    print(f"    - Components: {json.dumps(updated_file['components'], indent=2)}")

    # 5. Verify ChromaDB
    print(f"\n[5] ChromaDB Verification:")
    sm = SemanticMemory()
    items = sm.get_all_items()
    found_in_chroma = [item for item in items if item['metadata'].get('file_id') == file_id]
    print(f"    - Found {len(found_in_chroma)} embeddings for this file_id in ChromaDB")

    # 6. Verify Neo4j (if connected)
    print(f"\n[6] Neo4j Verification:")
    kg = KnowledgeGraph()
    if kg.driver:
        with kg.driver.session() as session:
            result = session.run("MATCH (a:Article {file_id: $fid}) RETURN count(a) as count", {"fid": file_id})
            count = result.single()["count"]
            print(f"    - Found {count} Article nodes for this file_id in Neo4j")
        kg.close()
    else:
        print("    - Neo4j not connected - skipping verification")

    print("\n============================================================")
    print("             VERIFICATION COMPLETE")
    print("============================================================")

if __name__ == "__main__":
    verify_end_to_end()
