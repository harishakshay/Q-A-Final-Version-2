"""
============================================================
data_manager.py — Cognee-style Data Operations
============================================================
Manages a manifest of uploaded files, their metadata, and 
processing status. Allows for manual ingestion control.
============================================================
"""

import os
import json
import uuid
import shutil
from datetime import datetime
from typing import List, Dict, Any, Optional

import config

class DataManager:
    """
    Handles file manifest persistence and management operations.
    """

    def __init__(self, data_dir: str = config.DATA_DIR):
        self.data_dir = data_dir
        self.upload_dir = config.UPLOAD_DIR
        self.processed_dir = os.path.join(data_dir, "processed")
        self.manifest_path = os.path.join(data_dir, "manifest.json")
        
        os.makedirs(self.upload_dir, exist_ok=True)
        os.makedirs(self.processed_dir, exist_ok=True)
        self.manifest = self._load_manifest()

    def _load_manifest(self) -> Dict[str, Any]:
        """Load manifest from disk or return empty defaults."""
        default = {"files": {}, "last_updated": datetime.utcnow().isoformat()}
        if os.path.exists(self.manifest_path):
            try:
                with open(self.manifest_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    # Ensure essential keys exist
                    if not isinstance(data, dict) or "files" not in data:
                        data = default
                    return data
            except Exception as e:
                print(f"[DataManager] Error loading manifest: {e}")
        
        return default

    def _save_manifest(self):
        """Persist manifest to disk."""
        self.manifest["last_updated"] = datetime.utcnow().isoformat()
        try:
            with open(self.manifest_path, "w", encoding="utf-8") as f:
                json.dump(self.manifest, f, indent=2)
        except Exception as e:
            print(f"[DataManager] Error saving manifest: {e}")

    def add_file(self, filename: str, source_type: str, filepath: str) -> Dict[str, Any]:
        """Add a new file to the manifest."""
        file_id = str(uuid.uuid4())[:8]
        
        # We assume the file is already in the upload directory
        # but we store the relative path for portability
        rel_path = os.path.relpath(filepath, self.data_dir)

        file_entry = {
            "id": file_id,
            "filename": filename,
            "type": source_type,
            "path": rel_path,
            "status": "uploaded",
            "components": {
                "conversion": "pending",
                "semantic": "pending",
                "graph": "pending"
            },
            "added_at": datetime.utcnow().isoformat(),
            "size": os.path.getsize(filepath) if os.path.exists(filepath) else 0
        }

        self.manifest["files"][file_id] = file_entry
        self._save_manifest()
        return file_entry

    def list_files(self) -> List[Dict[str, Any]]:
        """Return list of all managed files."""
        return list(self.manifest["files"].values())

    def get_file(self, file_id: str) -> Optional[Dict[str, Any]]:
        """Get file metadata by ID."""
        return self.manifest["files"].get(file_id)

    def delete_file(self, file_id: str, semantic_memory=None, knowledge_graph=None) -> bool:
        """Delete file from disk and manifest, cleaning up databases as necessary."""
        if file_id not in self.manifest["files"]:
            return False

        file_info = self.manifest["files"][file_id]

        # 1. Clean up Semantic Memory (ChromaDB)
        if semantic_memory:
            semantic_memory.delete_by_file_id(file_id)

        # 2. Clean up Knowledge Graph (Neo4j)
        if knowledge_graph:
            knowledge_graph.delete_by_file_id(file_id)

        # 3. Delete original file
        full_path = os.path.join(self.data_dir, file_info["path"])
        if os.path.exists(full_path):
            try:
                os.remove(full_path)
            except Exception as e:
                print(f"[DataManager] Error deleting original file {full_path}: {e}")

        # 4. Delete converted text file if it exists
        conv_path = file_info.get("converted_path")
        if conv_path:
            full_conv_path = os.path.join(self.data_dir, conv_path)
            if os.path.exists(full_conv_path):
                try:
                    os.remove(full_conv_path)
                except Exception as e:
                    print(f"[DataManager] Error deleting converted file {full_conv_path}: {e}")

        del self.manifest["files"][file_id]
        self._save_manifest()
        return True

    def update_status(self, file_id: str, component: str, status: str):
        """Update processing status for a specific component."""
        if file_id in self.manifest["files"]:
            entry = self.manifest["files"][file_id]
            if component in entry["components"]:
                entry["components"][component] = status
                
                # Update overall status
                comps = entry["components"]
                if all(s == "indexed" for s in comps.values()):
                    entry["status"] = "fully_processed"
                elif any(s == "indexed" for s in comps.values()):
                    entry["status"] = "partially_processed"
                
                self._save_manifest()

    def save_converted_file(self, file_id: str, content: str) -> str:
        """Save converted text content and update manifest."""
        if file_id not in self.manifest["files"]:
            return ""

        file_info = self.manifest["files"][file_id]
        new_filename = f"{file_info['filename'].rsplit('.', 1)[0]}_converted.txt"
        dest_path = os.path.join(self.processed_dir, new_filename)

        try:
            with open(dest_path, "w", encoding="utf-8") as f:
                f.write(content)
            
            # Update manifest
            file_info["converted_path"] = os.path.relpath(dest_path, self.data_dir)
            file_info["status"] = "converted"
            self._save_manifest()
            return dest_path
        except Exception as e:
            print(f"[DataManager] Error saving converted file: {e}")
            return ""

    def rollback(self, file_id: str, semantic_memory=None, knowledge_graph=None) -> bool:
        """
        Roll back all changes made by a file processing attempt.
        Cleans up ChromaDB, Neo4j, and the File System.
        """
        if file_id not in self.manifest["files"]:
            return False

        file_info = self.manifest["files"][file_id]
        print(f"[DataManager] Rolling back file_id: {file_id}")

        # 1. Clean up Semantic Memory (ChromaDB)
        if semantic_memory:
            semantic_memory.delete_by_file_id(file_id)

        # 2. Clean up Knowledge Graph (Neo4j)
        if knowledge_graph:
            knowledge_graph.delete_by_file_id(file_id)

        # 3. Clean up converted files — ONLY if conversion failed
        # If conversion succeeded, we keep the file for the user to see/copy.
        if file_info.get("components", {}).get("conversion") != "indexed":
            if file_info.get("converted_path"):
                conv_path = os.path.join(self.data_dir, file_info["converted_path"])
                if os.path.exists(conv_path):
                    try:
                        os.remove(conv_path)
                    except Exception as e:
                        print(f"[DataManager] Error removing converted file: {e}")
                file_info["converted_path"] = None

        # 4. Reset statuses
        file_info["status"] = "failed"
        for comp in file_info["components"]:
            file_info["components"][comp] = "failed"
            
        self._save_manifest()
        return True

if __name__ == "__main__":
    dm = DataManager()
    print(f"Managed files: {len(dm.list_files())}")
