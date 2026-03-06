import os
import shutil
from semantic_memory import SemanticMemory
from data_manager import DataManager
import config

def cleanup_system():
    print("--- SYSTEM CLEANUP START ---")

    # 1. Clear Semantic Memory (ChromaDB)
    print("Clearing ChromaDB...")
    try:
        sm = SemanticMemory()
        sm.clear_collection()
        print("ChromaDB cleared.")
    except Exception as e:
        print(f"Error clearing ChromaDB: {e}")

    # 2. Clear File Manifest
    print("Clearing data manifest...")
    try:
        dm = DataManager()
        dm.manifest = {"files": {}, "last_updated": datetime.utcnow().isoformat()}
        dm._save_manifest()
        print("Manifest cleared.")
    except Exception as e:
        print(f"Error clearing manifest: {e}")

    # 3. Delete Uploaded and Processed Files
    directories = [config.UPLOAD_DIR, config.DATA_DIR]
    # We also have 'processed' inside DATA_DIR usually.
    # DataManager.save_converted_file uses DATA_DIR/processed
    processed_dir = os.path.join(config.DATA_DIR, "processed")
    
    for folder in [config.UPLOAD_DIR, processed_dir]:
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

    print("--- SYSTEM CLEANUP COMPLETE ---")

if __name__ == "__main__":
    cleanup_system()
