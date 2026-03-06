import os
import time
from pipeline import MemoryPipeline
from data_manager import DataManager
import config

def main():
    pipeline = MemoryPipeline()
    data_manager = DataManager()
    
    docs_dir = config.DOCS_DIR
    if not os.path.exists(docs_dir):
        print(f"Docs directory not found at {docs_dir}")
        return

    files = [f for f in os.listdir(docs_dir) if f.endswith(('.pdf', '.md', '.txt'))]
    print(f"Found {len(files)} documents in {docs_dir} for ingestion.")

    for filename in files:
        filepath = os.path.join(docs_dir, filename)
        print(f"\n--- Processing {filename} ---")
        try:
            # Check if already in manifest
            existing_id = None
            for fid, info in data_manager.manifest["files"].items():
                if info["filename"] == filename:
                    existing_id = fid
                    break
            
            if existing_id:
                print(f"File {filename} already exists in system (ID: {existing_id}). Jumping to re-processing.")
                file_id = existing_id
            else:
                # Add to manifest
                file_id = data_manager.add_file(filename, filepath)
                print(f"Added {filename} to manifest with ID: {file_id}")

            # Process through pipeline
            pipeline.process_file_pipeline(file_id, data_manager)
            print(f"Successfully ingested {filename}")
            
        except Exception as e:
            print(f"Error processing {filename}: {e}")

    print("\nIngestion complete. All documents from docs/ are now in the RAG system.")

if __name__ == "__main__":
    main()
