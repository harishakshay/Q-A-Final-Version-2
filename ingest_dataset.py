import os
import json
import re
from typing import List, Dict, Any
from chunking import DocumentChunker
from semantic_memory import SemanticMemory
import config

def validate_chunks(all_chunks: list[dict]):
    """Validation logic from Step 8."""
    ids = [c["id"] for c in all_chunks]
    
    errors = []
    for chunk in all_chunks:
        wc = chunk["metadata"]["word_count"]
        if wc < 220:
            errors.append(f"UNDER MINIMUM: {chunk['id']} ({wc} words)")
        if wc > 450:
            errors.append(f"OVER MAXIMUM: {chunk['id']} ({wc} words)")
        
        for field in ["source_file", "article_title", "category", "section_heading"]:
            if not chunk["metadata"].get(field):
                errors.append(f"MISSING METADATA: {chunk['id']} missing {field}")

    if len(ids) != len(set(ids)):
        errors.append("DUPLICATE IDs FOUND")

    if errors:
        print("\n--- VALIDATION ERRORS ---")
        for e in errors:
            print(f"  ERROR: {e}")
    else:
        print("\nAll chunks valid.")

    print(f"\nTotal chunks    : {len(all_chunks)}")
    if all_chunks:
        print(f"Avg word count  : {sum(c['metadata']['word_count'] for c in all_chunks)/len(all_chunks):.1f}")
        print(f"Min word count  : {min(c['metadata']['word_count'] for c in all_chunks)}")
        print(f"Max word count  : {max(c['metadata']['word_count'] for c in all_chunks)}")
        print(f"Unique articles : {len(set(c['metadata']['article_title'] for c in all_chunks))}")

def ingest_dataset():
    dataset_dir = "DATASET"
    if not os.path.exists(dataset_dir):
        print(f"Error: {dataset_dir} directory not found.")
        return

    sm = SemanticMemory()

    # Clear existing embeddings for a clean start
    print("Clearing existing embeddings...")
    sm.clear_collection()

    all_ingested_chunks = []
    
    # Iterate through files in DATASET
    files = sorted([f for f in os.listdir(dataset_dir) if f.lower().endswith(('.pdf', '.txt', '.md'))])
    print(f"Found {len(files)} files in {dataset_dir}\n")

    for filename in files:
        filepath = os.path.join(dataset_dir, filename)
        
        try:
            chunks = DocumentChunker.extract_chunks(filepath)
            if chunks:
                print(f"  {filename}: {len(chunks)} chunks, words: {[c['metadata']['word_count'] for c in chunks]}")

                # Format for store_chunks (SemanticMemory expects certain keys)
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
                all_ingested_chunks.extend(chunks)
            else:
                print(f"  {filename}: No chunks extracted!")
        except Exception as e:
            print(f"  FAILED {filename}: {e}")
            import traceback
            traceback.print_exc()

    # Step 8: Validation
    print("\n" + "="*60)
    print("VALIDATION REPORT")
    print("="*60)
    validate_chunks(all_ingested_chunks)

if __name__ == "__main__":
    ingest_dataset()
