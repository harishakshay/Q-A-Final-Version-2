import os
import shutil
import json
from datetime import datetime
from semantic_memory import SemanticMemory
from knowledge_graph import KnowledgeGraph
from data_manager import DataManager
import config

def reset_system():
    print("--- FULL SYSTEM RESET START ---")

    # 1. Clear Semantic Memory (ChromaDB)
    print("Clearing ChromaDB...")
    try:
        sm = SemanticMemory()
        sm.clear_collection()
        print("ChromaDB cleared.")
    except Exception as e:
        print(f"Error clearing ChromaDB: {e}")

    # 2. Clear Knowledge Graph (Neo4j)
    print("Clearing Neo4j Knowledge Graph...")
    try:
        kg = KnowledgeGraph()
        if kg.driver:
            kg.clear_graph()
            kg.close()
            print("Neo4j Graph cleared.")
        else:
            print("Neo4j not connected, skipping graph clear.")
    except Exception as e:
        print(f"Error clearing Neo4j: {e}")

    # 3. Clear File Manifest and Data Directories
    print("Clearing data manifest and directories...")
    try:
        # Reset Manifest
        dm = DataManager()
        dm.manifest = {"files": {}, "last_updated": datetime.utcnow().isoformat()}
        dm._save_manifest()
        print("Manifest reset.")

        # Cleanup folders
        processed_dir = os.path.join(config.DATA_DIR, "processed")
        input_docs_dir = os.path.join("doc_converter", "input_docs")
        output_txt_dir = os.path.join("doc_converter", "output_txt")
        
        target_folders = [
            config.UPLOAD_DIR, 
            processed_dir, 
            input_docs_dir, 
            output_txt_dir
        ]

        for folder in target_folders:
            if os.path.exists(folder):
                print(f"Cleaning folder: {folder}")
                for filename in os.listdir(folder):
                    file_path = os.path.join(folder, filename)
                    try:
                        if os.path.isfile(file_path) or os.path.islink(file_path):
                            os.unlink(file_path)
                        elif os.path.isdir(file_path):
                            shutil.rmtree(file_path)
                    except Exception as e:
                        print(f'Failed to delete {file_path}. Reason: {e}')
            else:
                print(f"Folder not found, skipping: {folder}")

    except Exception as e:
        print(f"Error clearing manifest/folders: {e}")

    # 4. Delete specific JSON memory files
    print("Deleting memory JSON files...")
    json_files = [
        config.CONTENT_MEMORY_PATH,
        config.PERFORMANCE_MEMORY_PATH,
        config.INSIGHTS_PATH,
        config.PAGES_METADATA_PATH,
        os.path.join(config.DATA_DIR, "rag_results.json"), # Just in case
        "rag_results.txt"
    ]

    for jf in json_files:
        if os.path.exists(jf):
            try:
                os.remove(jf)
                print(f"Deleted: {jf}")
            except Exception as e:
                print(f"Error deleting {jf}: {e}")

    print("--- FULL SYSTEM RESET COMPLETE ---")

if __name__ == "__main__":
    reset_system()
