import os
import sys

# Add current directory to path
sys.path.append(os.getcwd())

from semantic_memory import SemanticMemory

def view_sample_embedding():
    sm = SemanticMemory()
    
    print("Fetching a sample embedding from ChromaDB...")
    
    # Get the first item including its embedding
    result = sm.collection.get(limit=1, include=["embeddings", "metadatas", "documents"])
    
    if not result["ids"]:
        print("No items found in ChromaDB.")
        return
        
    doc_id = result["ids"][0]
    title = result["metadatas"][0].get("title", "No Title")
    vector = result["embeddings"][0]
    
    print(f"\n--- Sample Item ---")
    print(f"ID: {doc_id}")
    print(f"Title: {title}")
    print(f"Vector Length: {len(vector)} dimensions")
    
    # Print the first 10 numbers and the last 5
    print("\n--- Raw Embedding (First 10 values) ---")
    print(vector[:10])
    print("...")
    print("\n--- Raw Embedding (Last 5 values) ---")
    print(vector[-5:])
    
    print("\nThese are the 'numbers' (vectors) that the AI uses to understand similarity.")

if __name__ == "__main__":
    view_sample_embedding()
