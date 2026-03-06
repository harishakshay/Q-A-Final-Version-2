import json
import os
from semantic_memory import SemanticMemory

def export_chunks():
    sm = SemanticMemory()
    collection = sm.collection
    
    # Get all items from the collection
    results = collection.get(include=["metadatas", "documents"])
    
    chunks = []
    if results and results["ids"]:
        for i, doc_id in enumerate(results["ids"]):
            metadata = results["metadatas"][i] if results["metadatas"] else {}
            document = results["documents"][i] if results["documents"] else ""
            
            chunk_data = {
                "id": doc_id,
                "document": document,
                "metadata": metadata
            }
            chunks.append(chunk_data)
            
    output_file = "split.json"
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(chunks, f, indent=4, ensure_ascii=False)
        
    print(f"Successfully exported {len(chunks)} chunks to {output_file}")

if __name__ == "__main__":
    export_chunks()
