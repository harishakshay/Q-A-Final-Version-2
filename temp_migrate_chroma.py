import json
from semantic_memory import SemanticMemory
import config

def migrate():
    sm = SemanticMemory()
    print("Clearing collection...")
    sm.clear_collection()
    
    print(f"Loading chunks from {config.CONTENT_MEMORY_PATH}...")
    with open(config.CONTENT_MEMORY_PATH, "r", encoding="utf-8") as f:
        chunks = json.load(f)
        
    print(f"Storing {len(chunks)} chunks...")
    sm.store_chunks(chunks)
    print("Migration complete.")

if __name__ == "__main__":
    migrate()
