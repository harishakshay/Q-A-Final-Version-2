import os
import shutil
from data_manager import DataManager
from semantic_memory import SemanticMemory
import config

def register_dataset():
    dataset_dir = "DATASET"
    upload_dir = config.UPLOAD_DIR
    
    # Ensure upload directory exists
    os.makedirs(upload_dir, exist_ok=True)
    
    dm = DataManager()
    
    # Clear existing manifest files to avoid duplicates
    dm.manifest["files"] = {}
    
    files = sorted([f for f in os.listdir(dataset_dir) if f.lower().endswith('.pdf')])
    print(f"Registering {len(files)} files from {dataset_dir} to dashboard...")
    
    for filename in files:
        src_path = os.path.join(dataset_dir, filename)
        dst_path = os.path.join(upload_dir, filename)
        
        # Copy file to uploads folder so Document Viewer can find it
        shutil.copy2(src_path, dst_path)
        
        # Determine file type
        ext = os.path.splitext(filename)[1].lower().replace('.', '')
        
        # Add to DataManager manifest
        file_entry = dm.add_file(filename, ext, dst_path)
        
        # Mark as processed since we already ingrained them in ingest_dataset.py
        file_entry["status"] = "processed"
        file_entry["components"]["conversion"] = "success"
        file_entry["components"]["semantic"] = "success"
        
        # Update manifest directly
        dm.manifest["files"][file_entry["id"]] = file_entry
    
    dm._save_manifest()
    print("Done! Files should now appear in the dashboard.")

if __name__ == "__main__":
    register_dataset()
