import os
import json
import shutil
from typing import List, Dict, Any

from data_manager import DataManager
from chunking import DocumentChunker
from semantic_memory import SemanticMemory
import config

# We'll import the loading logic from load_split_to_neo4j
import load_split_to_neo4j
import export_split

def incremental_ingest():
    print("=" * 60)
    print("INCREMENTAL DOCUMENT INGESTION")
    print("=" * 60)

    dm = DataManager()
    sm = SemanticMemory()
    dataset_dir = "DATASET"
    upload_dir = config.UPLOAD_DIR

    # 1. IDENTIFY NEW FILES
    existing_filenames = {f["filename"] for f in dm.list_files()}
    all_files = sorted([f for f in os.listdir(dataset_dir) if f.lower().endswith(('.pdf', '.txt', '.md'))])
    
    new_files = [f for f in all_files if f not in existing_filenames]
    
    if not new_files:
        print("No new documents found in DATASET/ folder.")
        return

    print(f"Found {len(new_files)} new files to process:")
    for f in new_files:
        print(f"  - {f}")

    # 2. CHUNK AND EMBED NEW FILES
    all_new_chunks = []
    for filename in new_files:
        filepath = os.path.join(dataset_dir, filename)
        print(f"\nProcessing {filename}...")
        
        try:
            chunks = DocumentChunker.extract_chunks(filepath)
            if not chunks:
                print(f"  Warning: No chunks extracted from {filename}")
                continue

            print(f"  Extracted {len(chunks)} chunks.")
            
            # Format for store_chunks
            formatted_chunks = []
            for c in chunks:
                formatted_chunks.append({
                    "chunk_id": c["id"],
                    "parent_post_id": c["metadata"]["source_file"],
                    "title": c["metadata"]["article_title"],
                    "section_heading": c["metadata"]["section_heading"],
                    "content": c["document"].split("\n\n", 1)[-1],
                    "category": [c["metadata"]["category"]],
                    "publish_date": "",
                })
            
            sm.store_chunks(formatted_chunks)
            print(f"  Stored {len(formatted_chunks)} chunks in ChromaDB.")
            
            # 3. REGISTER NEW FILE IN MANIFEST
            dst_path = os.path.join(upload_dir, filename)
            shutil.copy2(filepath, dst_path)
            
            ext = os.path.splitext(filename)[1].lower().replace('.', '')
            file_entry = dm.add_file(filename, ext, dst_path)
            
            # Mark as processed
            file_entry["status"] = "processed"
            file_entry["components"]["conversion"] = "success"
            file_entry["components"]["semantic"] = "success"
            file_entry["components"]["graph"] = "success" # We will update graph below
            
            dm.manifest["files"][file_entry["id"]] = file_entry
            
        except Exception as e:
            print(f"  Failed to process {filename}: {e}")

    dm._save_manifest()
    print("\n✓ New files added to ChromaDB and manifest.")

    # 4. SYNC split.json
    print("\nExporting all chunks to split.json...")
    export_split.export_chunks()

    # 5. REBUILD NEO4J GRAPH
    print("\nRebuilding Knowledge Graph from updated split.json...")
    try:
        # Load the updated split.json
        with open("split.json", "r", encoding="utf-8") as f:
            split_data = json.load(f)
        
        load_split_to_neo4j.load_to_neo4j(split_data)
        print("\n✓ Knowledge Graph rebuilt successfully.")
    except Exception as e:
        print(f"\nError rebuilding Knowledge Graph: {e}")

    print("\n" + "=" * 60)
    print("INCREMENTAL INGESTION COMPLETE")
    print("=" * 60)

if __name__ == "__main__":
    incremental_ingest()
