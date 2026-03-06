import json
import os
import sys

# Add current directory to path so we can import local modules
sys.path.append(os.getcwd())

from semantic_memory import SemanticMemory
import config

def ingest():
    print("Starting manual ingestion of content_memory.json...")
    
    if not os.path.exists(config.CONTENT_MEMORY_PATH):
        print(f"Error: {config.CONTENT_MEMORY_PATH} not found.")
        return

    try:
        with open(config.CONTENT_MEMORY_PATH, "r", encoding="utf-8") as f:
            posts = json.load(f)
        
        print(f"Loaded {len(posts)} posts from JSON.")
        
        sm = SemanticMemory()
        # Get count before
        count_before = sm.collection.count()
        print(f"Collection count before: {count_before}")
        
        # Ingest
        stored_count = sm.store_posts(posts)
        
        # Get count after
        count_after = sm.collection.count()
        print(f"Collection count after: {count_after}")
        print(f"Successfully stored {stored_count} posts.")
        
    except Exception as e:
        print(f"Error during ingestion: {e}")

if __name__ == "__main__":
    ingest()
