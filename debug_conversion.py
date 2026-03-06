
import os
import sys
import json
from data_manager import DataManager
from pipeline import MemoryPipeline
import config

def debug_conversion():
    print(f"Current Working Directory: {os.getcwd()}")
    print(f"config.DATA_DIR: {config.DATA_DIR}")
    
    dm = DataManager()
    pipeline = MemoryPipeline()
    
    # Use the existing test file
    test_file_id = "47e8a065" # From manifest.json
    file_info = dm.get_file(test_file_id)
    
    if not file_info:
        print(f"File {test_file_id} not found in manifest")
        return
    
    print(f"Processing file: {file_info['filename']} (Type: {file_info['type']})")
    
    full_path = os.path.join(config.DATA_DIR, file_info["path"])
    print(f"Full path to source: {full_path}")
    print(f"Source file exists: {os.path.exists(full_path)}")
    
    try:
        if file_info["type"] == "csv":
            print("Loading CSV records...")
            records = pipeline.load_csv_file(full_path)
            print(f"Loaded {len(records)} records")
            
            print("Formatting records to text...")
            formatted_text = pipeline.format_csv_to_text(records)
            print(f"Formatted text length: {len(formatted_text)}")
            
            print("Saving converted file...")
            dest_path = dm.save_converted_file(test_file_id, formatted_text)
            print(f"Saved to: {dest_path}")
            
            if os.path.exists(dest_path):
                print("SUCCESS: Converted file exists on disk.")
                with open(dest_path, "r", encoding="utf-8") as f:
                    print("First 100 characters of saved file:")
                    print(f.read()[:100])
            else:
                print("FAILURE: Converted file does NOT exist on disk after saving.")
        
    except Exception as e:
        print(f"Error during debugging: {e}")

if __name__ == "__main__":
    debug_conversion()
