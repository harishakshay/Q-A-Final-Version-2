import sys
import os
import json

# Add project root to sys.path
sys.path.append(os.getcwd())

import config
from data_manager import DataManager
from semantic_memory import SemanticMemory
from knowledge_graph import KnowledgeGraph

def test_deletion():
    dm = DataManager()
    sm = SemanticMemory()
    kg = KnowledgeGraph()
    
    files = dm.list_files()
    if not files:
        print("No files to test deletion with.")
        return
        
    # Take the first file
    file = files[0]
    file_id = file['id']
    filename = file['filename']
    
    print(f"Testing deletion for: {filename} ({file_id})")
    
    # 1. Check ChromaDB before
    print(f"ChromaDB count for {file_id}: {len(sm.collection.get(where={'parent_post_id': file_id})['ids'])}")
    
    # 2. Check Neo4j before
    # (Just an existence check)
    
    # 3. Delete
    print("Executing delete...")
    success = dm.delete_file(file_id, semantic_memory=sm, knowledge_graph=kg)
    print(f"Delete result: {success}")
    
    # 4. Check ChromaDB after
    print(f"ChromaDB count for {file_id} after: {len(sm.collection.get(where={'parent_post_id': file_id})['ids'])}")
    
    # 5. Check manifest after
    print(f"File in manifest: {file_id in dm.manifest['files']}")
    
    # 6. Check filesystem
    original_path = os.path.join(config.DATA_DIR, file['path'])
    print(f"Original file exists: {os.path.exists(original_path)}")
    
    conv_path = file.get('converted_path')
    if conv_path:
        full_conv_path = os.path.join(config.DATA_DIR, conv_path)
        print(f"Converted file exists: {os.path.exists(full_conv_path)}")

if __name__ == "__main__":
    test_deletion()
