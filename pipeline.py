"""
============================================================
pipeline.py — Automated Memory Pipeline Orchestrator
============================================================
Orchestrates all layers of the AI Memory System:
1. Fetches WordPress posts → content memory
2. Merges CSV metrics → performance memory
3. Generates embeddings → ChromaDB
4. Updates Neo4j knowledge graph
5. Runs reasoning → insights / alerts

Supports single runs, scheduled runs, and dashboard-triggered runs.
============================================================
"""

import os
import json
import time
from typing import Dict, Any, Optional, List
from datetime import datetime

import schedule

import config
from content_layer import WordPressFetcher
from performance_layer import PerformanceTracker
from semantic_memory import SemanticMemory
from knowledge_graph import KnowledgeGraph
from reasoning_engine import ReasoningEngine


class MemoryPipeline:
    """
    Orchestrates the complete AI Memory System pipeline.
    Components are initialized independently so failures
    in one don't prevent others from working.
    """

    def __init__(self):
        """Initialize all pipeline components."""
        print("\n" + "=" * 60)
        print("  PERSONAL AI MEMORY SYSTEM — PIPELINE")
        print("=" * 60 + "\n")

        self.content_fetcher = WordPressFetcher()
        self.performance_tracker = PerformanceTracker()

        self.semantic_memory = None
        try:
            self.semantic_memory = SemanticMemory()
        except Exception as e:
            print(f"[Pipeline] SemanticMemory init failed: {e}")

        self.knowledge_graph = None
        try:
            self.knowledge_graph = KnowledgeGraph()
        except Exception as e:
            print(f"[Pipeline] KnowledgeGraph init failed: {e}")

        self.reasoning_engine = ReasoningEngine(
            semantic_memory=self.semantic_memory,
            knowledge_graph=self.knowledge_graph,
        )

        # Store the latest posts and clusters for dashboard access
        self.current_posts: List[Dict[str, Any]] = []
        self.current_clusters: List[Dict[str, Any]] = []
        self.current_csv_records: List[Dict[str, Any]] = []
        self.latest_report: Dict[str, Any] = {}

        print("[Pipeline] All components initialized\n")

    # ============================================================
    # Individual Stage Methods (callable from dashboard)
    # ============================================================

    def fetch_wordpress_posts(self) -> List[Dict[str, Any]]:
        """Stage 1: Fetch WordPress posts."""
        print("\n[Pipeline] STAGE 1: Fetching WordPress posts...")
        self.current_posts = self.content_fetcher.fetch_all_posts()
        self.content_fetcher.save_to_json(self.current_posts)

        # Apply default health scores
        self.current_posts = self.performance_tracker.enrich_posts_default(self.current_posts)
        return self.current_posts

    def format_csv_to_text(self, records: List[Dict[str, Any]]) -> str:
        """Format internal CSV records into a beautiful structured text."""
        if not records:
            return "No data found."

        # Dynamically find max key width for alignment
        max_key_len = 0
        all_keys = set()
        for record in records:
            data = record.get("row_data", {})
            for key in data.keys():
                all_keys.add(key)
                max_key_len = max(max_key_len, len(key))
        
        # Constrain key width for better layout
        max_key_len = min(max(max_key_len, 10), 30)

        output = []
        output.append("=" * 60)
        output.append("             CONVERTED DATA REPORT")
        output.append(f"             Generated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC")
        output.append(f"             Total Records: {len(records)}")
        output.append("=" * 60 + "\n")

        for i, record in enumerate(records):
            output.append(f"RECORD #{i+1}")
            output.append("-" * 40)
            data = record.get("row_data", {})
            # Sort keys so they are consistent across records
            for key in sorted(data.keys()):
                val = data[key]
                output.append(f"{key:<{max_key_len}} : {val}")
            output.append("") # Blank line between records

        return "\n".join(output)

    def load_csv_file(self, filepath: str) -> List[Dict[str, Any]]:
        """Stage 2a: Load and convert a CSV file to text records."""
        print(f"\n[Pipeline] Loading CSV: {filepath}")
        self.current_csv_records = self.performance_tracker.load_and_convert(filepath)

        # If we have WordPress posts, try to enrich them with CSV data
        if self.current_posts:
            self.current_posts = self.performance_tracker.enrich_posts_from_csv(
                self.current_posts, self.current_csv_records
            )
            self.performance_tracker.save_performance_data(self.current_posts)

        return self.current_csv_records

    def process_file_pipeline(self, file_id: str, data_manager, status_callback=None) -> Dict[str, Any]:
        """
        Automated processing pipeline for a specific file.
        Mirrors incremental_ingest.py exactly:
          1. Extract chunks via DocumentChunker (from the raw uploaded file)
          2. Format and store in ChromaDB (same parent_post_id = filename)
          3. Update manifest status
          4. Append to split.json
          5. Incrementally sync new chunks to Neo4j (MERGE only — no wipe)
        """
        file_info = data_manager.get_file(file_id)
        if not file_info:
            raise ValueError(f"File {file_id} not found in manifest")

        filename = file_info["filename"]

        # Resolve the actual file path — it may be relative to data_dir or absolute
        raw_path = file_info.get("path", "")
        if os.path.isabs(raw_path):
            full_path = raw_path
        else:
            full_path = os.path.join(config.DATA_DIR, raw_path)

        # Files uploaded via dashboard are saved directly in input_docs — fall back there
        if not os.path.exists(full_path):
            input_path = os.path.join(os.path.dirname(__file__), "doc_converter", "input_docs", filename)
            if os.path.exists(input_path):
                full_path = input_path

        if not os.path.exists(full_path):
            raise FileNotFoundError(f"Could not locate file for {filename} (id={file_id})")

        print(f"\n[Pipeline] STARTING for: {filename} ({file_id}) — path: {full_path}")

        try:
            # ── STAGE 1: CONVERSION ───────────────────────────────────────
            if status_callback: status_callback(file_id, "converting")
            import doc_converter.scripts.convert_to_txt as converter
            converter_output_dir = os.path.join(os.path.dirname(__file__), "doc_converter", "output_txt")
            os.makedirs(converter_output_dir, exist_ok=True)
            try:
                converter.convert_file(full_path, converter_output_dir)
                base_name = os.path.splitext(filename)[0]
                conv_path = os.path.join(converter_output_dir, base_name + ".txt")
                with open(conv_path, "r", encoding="utf-8") as f:
                    content = f.read()
                data_manager.save_converted_file(file_id, content)
            except Exception as e:
                print(f"[Pipeline] Converter failed ({e}), falling back to direct read")
                with open(full_path, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read()
                data_manager.save_converted_file(file_id, content)

            data_manager.update_status(file_id, "conversion", "indexed")

            # ── STAGE 2: CHUNKING + EMBEDDING ─────────────────────────────
            if status_callback: status_callback(file_id, "chunking")
            if self.semantic_memory:
                from chunking import DocumentChunker
                print(f"[Pipeline] Chunking {filename}...")
                raw_chunks = DocumentChunker.extract_chunks(full_path)
                if not raw_chunks:
                    print(f"[Pipeline] Warning: no chunks extracted from {filename}")
                else:
                    print(f"[Pipeline] Extracted {len(raw_chunks)} chunks.")

                # *** Same format as incremental_ingest.py ***
                formatted_chunks = []
                for c in raw_chunks:
                    meta = c.get("metadata", {})
                    formatted_chunks.append({
                        "chunk_id": c["id"],
                        "parent_post_id": meta.get("source_file", filename),   # filename, NOT file_id
                        "title": meta.get("article_title", filename),
                        "section_heading": meta.get("section_heading", "General"),
                        "content": c.get("document", "").split("\n\n", 1)[-1],
                        "category": [meta.get("category", "")],
                        "publish_date": file_info.get("added_at", ""),
                    })

                if status_callback: status_callback(file_id, "embedding")
                self.semantic_memory.store_chunks(formatted_chunks)
                print(f"[Pipeline] Stored {len(formatted_chunks)} chunks in ChromaDB.")
                data_manager.update_status(file_id, "semantic", "indexed")
            else:
                data_manager.update_status(file_id, "semantic", "skipped")

            # ── STAGE 3: GRAPH SYNC (incremental MERGE only) ──────────────
            if self.knowledge_graph and self.knowledge_graph.driver:
                if status_callback: status_callback(file_id, "indexing")
                print("[Pipeline] Syncing new chunks to Neo4j (incremental MERGE — no wipe)...")
                try:
                    # Pull only the chunks for this file from ChromaDB
                    all_items = self.semantic_memory.get_all_items() or []
                    new_chunks = [
                        c for c in all_items
                        if c.get("metadata", {}).get("source_file") == filename
                        or c.get("metadata", {}).get("parent_post_id") == filename
                    ]
                    print(f"[Pipeline] Found {len(new_chunks)} chunks for {filename} in ChromaDB for graph sync.")

                    if new_chunks:
                        driver = self.knowledge_graph.driver
                        with driver.session() as session:
                            chunk_ids_in_order = []
                            for item in new_chunks:
                                meta = item.get("metadata", {})
                                doc_id  = meta.get("parent_post_id", filename)
                                title   = meta.get("title", filename)
                                chunk_id = item["id"]
                                chunk_ids_in_order.append(chunk_id)

                                # Document node
                                session.run(
                                    "MERGE (d:Document {id: $id}) SET d.title = $title",
                                    {"id": doc_id, "title": title}
                                )

                                # Category nodes
                                cats_raw = meta.get("categories", meta.get("category", "[]"))
                                if isinstance(cats_raw, str):
                                    try:    cats = json.loads(cats_raw)
                                    except: cats = [cats_raw] if cats_raw else []
                                elif isinstance(cats_raw, list):
                                    cats = cats_raw
                                else:
                                    cats = []

                                for cat in cats:
                                    if cat:
                                        session.run("MERGE (cat:Category {name: $name})", {"name": cat})
                                        session.run("""
                                            MATCH (d:Document {id: $did})
                                            MATCH (cat:Category {name: $cat})
                                            MERGE (d)-[:CATEGORIZED_AS]->(cat)
                                        """, {"did": doc_id, "cat": cat})

                                # Chunk node + BELONGS_TO
                                session.run("""
                                    MERGE (c:Chunk {id: $id})
                                    SET c.section_heading = $heading,
                                        c.text = $text,
                                        c.source = $source
                                """, {
                                    "id": chunk_id,
                                    "heading": meta.get("section_heading", ""),
                                    "text": item.get("document", ""),
                                    "source": filename,
                                })
                                session.run("""
                                    MATCH (c:Chunk {id: $cid})
                                    MATCH (d:Document {id: $did})
                                    MERGE (c)-[:BELONGS_TO]->(d)
                                """, {"cid": chunk_id, "did": doc_id})

                                for cat in cats:
                                    if cat:
                                        session.run("""
                                            MATCH (c:Chunk {id: $cid})
                                            MATCH (cat:Category {name: $cat})
                                            MERGE (c)-[:CATEGORIZED_AS]->(cat)
                                        """, {"cid": chunk_id, "cat": cat})

                            # NEXT_CHUNK chain for sequential reading order
                            for i in range(len(chunk_ids_in_order) - 1):
                                session.run("""
                                    MATCH (c1:Chunk {id: $id1})
                                    MATCH (c2:Chunk {id: $id2})
                                    MERGE (c1)-[:NEXT_CHUNK]->(c2)
                                """, {"id1": chunk_ids_in_order[i], "id2": chunk_ids_in_order[i+1]})

                        print(f"[Pipeline] Incremental graph sync complete for {filename}.")

                    # Update split.json to stay in sync with ChromaDB
                    all_chunks = self.semantic_memory.get_all_items()
                    split_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "split.json")
                    with open(split_path, "w", encoding="utf-8") as f:
                        json.dump(all_chunks, f, indent=2, ensure_ascii=False)
                    print(f"[Pipeline] split.json updated: {len(all_chunks)} total chunks.")

                except Exception as ge:
                    print(f"[Pipeline] Graph sync error (non-fatal): {ge}")

                data_manager.update_status(file_id, "graph", "indexed")

            # ── STAGE 4: MARK AS PROCESSED ────────────────────────────────
            if file_id in data_manager.manifest["files"]:
                data_manager.manifest["files"][file_id]["status"] = "processed"
                data_manager.manifest["files"][file_id]["components"]["conversion"] = "success"
                data_manager.manifest["files"][file_id]["components"]["semantic"] = "success"
                data_manager.manifest["files"][file_id]["components"]["graph"] = "success"
                data_manager._save_manifest()

            print(f"[Pipeline] ✓ COMPLETED for {filename} ({file_id})")
            if status_callback: status_callback(file_id, "ready")
            return {"status": "success", "file_id": file_id}

        except Exception as e:
            print(f"[Pipeline] ✗ FAILED for {filename} ({file_id}): {e}")
            import traceback; traceback.print_exc()
            data_manager.rollback(file_id, self.semantic_memory, self.knowledge_graph)
            raise e

        # Ensure we have posts loaded for enrichment if it's a CSV
        if not self.current_posts:
            self.current_posts = self._load_cached_posts() or []
            print(f"[Pipeline] Loaded {len(self.current_posts)} posts for potential enrichment")

        try:
            # 1. CONVERSION STAGE
            if status_callback: status_callback(file_id, "converting")
            conv_path = ""
            import doc_converter.scripts.convert_to_txt as converter
            
            try:
                converter_output_dir = os.path.join(os.path.dirname(__file__), "doc_converter", "output_txt")
                os.makedirs(converter_output_dir, exist_ok=True)
                
                # Run the actual converter logic
                converter.convert_file(full_path, converter_output_dir)
                
                # convert_file writes to OUTPUT_FOLDER with same base name + .txt
                base_name = os.path.splitext(file_info['filename'])[0]
                conv_path = os.path.join(converter_output_dir, base_name + ".txt")
                
                # Read converted content to save it into the data manager manifest
                with open(conv_path, "r", encoding="utf-8") as f:
                    content = f.read()
                data_manager.save_converted_file(file_id, content)
            except Exception as e:
                print(f"[Pipeline] External converter failed: {e}")
                # Fallback to direct reading for safety
                with open(full_path, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read()
                conv_path = data_manager.save_converted_file(file_id, content)
            
            data_manager.update_status(file_id, "conversion", "indexed")

            # 2. SEMANTIC STAGE — CHUNKING AND EMBEDDING
            if status_callback: status_callback(file_id, "chunking")
            if self.semantic_memory:
                print("[Pipeline] Chunking and embedding converted document...")
                # Read the actual text we just converted
                with open(conv_path, "r", encoding="utf-8") as f:
                    converted_text = f.read()
                    
                # Create a pseudo-post object for the chunker
                # We use the document name as the title
                doc_obj = {
                    "id": file_id,
                    "title": file_info["filename"],
                    "content": converted_text,
                    "raw_content": "", # Force fallback chunker since it's plain text, not HTML
                    "categories": ["Upload"],
                    "publish_date": file_info["added_at"]
                }
                
                from chunking import DocumentChunker
                
                # DocumentChunker returns chunks with 'document' and 'metadata', 
                # we need to map them to the format expected by the rest of the pipeline
                raw_chunks = DocumentChunker.extract_chunks(full_path)
                chunks = []
                for c in raw_chunks:
                    meta = c.get("metadata", {})
                    chunks.append({
                        "chunk_id": c.get("id"),
                        "parent_post_id": str(doc_obj.get("id")),
                        "title": meta.get("article_title", doc_obj.get("title", "")),
                        "section_heading": meta.get("section_heading", "General"),
                        "content": c.get("document", "").split("\n\n", 1)[-1],
                        "category": [meta.get("category", "")],
                        "publish_date": doc_obj.get("publish_date", ""),
                        "cluster_id": doc_obj.get("cluster_id")
                    })
                
                # Store in ChromaDB
                if status_callback: status_callback(file_id, "embedding")
                self.semantic_memory.store_chunks(chunks)
                data_manager.update_status(file_id, "semantic", "indexed")
            else:
                data_manager.update_status(file_id, "semantic", "skipped")

            # 3. GRAPH STAGE
            if self.knowledge_graph and self.knowledge_graph.driver:
                print("[Pipeline] Updating Knowledge Graph incrementally (no wipe)...")
                if file_info["type"] == "csv":
                    self.update_knowledge_graph()
                else:
                    # INCREMENTAL ONLY: add just the new file's chunks to Neo4j via MERGE.
                    # NEVER call load_to_neo4j() here — it wipes the entire graph first.
                    try:
                        import load_split_to_neo4j
                        from collections import defaultdict

                        # Only process the newly embedded chunks for this file
                        source_file = file_info.get("filename", "")
                        new_chunks = [
                            c for c in (self.semantic_memory.get_all_items() or [])
                            if c.get("metadata", {}).get("source_file") == source_file
                        ]

                        if new_chunks:
                            print(f"[Pipeline] Incrementally adding {len(new_chunks)} chunks to Neo4j for {source_file}...")
                            driver = self.knowledge_graph.driver
                            with driver.session() as session:
                                for item in new_chunks:
                                    meta = item.get("metadata", {})
                                    doc_id = meta.get("parent_post_id", source_file)
                                    title = meta.get("title", source_file)
                                    chunk_id = item["id"]

                                    # Ensure Document node exists
                                    session.run(
                                        "MERGE (d:Document {id: $id}) SET d.title = $title",
                                        {"id": doc_id, "title": title}
                                    )

                                    # Ensure Category node and link
                                    cats_raw = meta.get("categories", "[]")
                                    if isinstance(cats_raw, str):
                                        try:
                                            cats = json.loads(cats_raw)
                                        except Exception:
                                            cats = [cats_raw] if cats_raw else []
                                    else:
                                        cats = cats_raw or []

                                    for cat in cats:
                                        if cat:
                                            session.run("MERGE (cat:Category {name: $name})", {"name": cat})
                                            session.run("""
                                                MATCH (d:Document {id: $did})
                                                MATCH (cat:Category {name: $cat})
                                                MERGE (d)-[:CATEGORIZED_AS]->(cat)
                                            """, {"did": doc_id, "cat": cat})

                                    # Create Chunk node and BELONGS_TO link
                                    session.run("""
                                        MERGE (c:Chunk {id: $id})
                                        SET c.section_heading = $heading,
                                            c.text = $text,
                                            c.source = $source
                                    """, {
                                        "id": chunk_id,
                                        "heading": meta.get("section_heading", ""),
                                        "text": item.get("document", ""),
                                        "source": source_file,
                                    })
                                    session.run("""
                                        MATCH (c:Chunk {id: $cid})
                                        MATCH (d:Document {id: $did})
                                        MERGE (c)-[:BELONGS_TO]->(d)
                                    """, {"cid": chunk_id, "did": doc_id})

                                    for cat in cats:
                                        if cat:
                                            session.run("""
                                                MATCH (c:Chunk {id: $cid})
                                                MATCH (cat:Category {name: $cat})
                                                MERGE (c)-[:CATEGORIZED_AS]->(cat)
                                            """, {"cid": chunk_id, "cat": cat})

                            # Also update split.json to stay in sync (export_split)
                            all_chunks = self.semantic_memory.get_all_items()
                            split_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "split.json")
                            with open(split_path, "w", encoding="utf-8") as f:
                                json.dump(all_chunks, f, indent=2, ensure_ascii=False)
                            print(f"[Pipeline] Updated split.json with {len(all_chunks)} total chunks.")
                        else:
                            print(f"[Pipeline] No new chunks found for {source_file}, skipping graph sync.")
                    except Exception as ge:
                        print(f"[Pipeline] Error during incremental graph sync: {ge}")

                data_manager.update_status(file_id, "graph", "indexed")
            
            # 4. REASONING STAGE
            self.run_reasoning()
            # data_manager doesn't track reasoning independently yet but we could
            
            print(f"[Pipeline] COMPLETED SUCCESSFULLY for {file_id}")
            if status_callback: status_callback(file_id, "ready")
            return {"status": "success", "file_id": file_id}

        except Exception as e:
            print(f"[Pipeline] FAILED for {file_id}: {e}. Triggering rollback...")
            data_manager.rollback(file_id, self.semantic_memory, self.knowledge_graph)
            raise e

    def update_embeddings(self) -> int:
        """Stage 3: Generate/update embeddings in ChromaDB using section chunks."""
        if not self.semantic_memory:
            return 0

        # We now load chunks from the file because content_layer.py transforms them during save
        chunks = self._load_cached_posts() # This will now be a list of chunks
        if not chunks:
            print("[Pipeline] No chunks found for embedding")
            return 0

        count = self.semantic_memory.store_chunks(chunks)

        # Detect clusters (still useful at chunk level, or could be at post level)
        self.current_clusters = self.semantic_memory.detect_clusters()

        return count

    def update_knowledge_graph(self) -> Dict[str, Any]:
        """Stage 4: Build/update the Neo4j knowledge graph with all relationships."""
        if not self.knowledge_graph or not self.knowledge_graph.driver:
            return {"status": "not_connected"}

        # Use current posts or load from content_memory.json
        posts = self.current_posts
        if not posts:
            posts = self._load_cached_posts()
        
        if not posts:
            print("[Pipeline] No posts found for Neo4j sync")
            return {"status": "no_data"}

        try:
            # 1. Ingest Nodes, Categories and Tags
            self.knowledge_graph.ingest_enriched_posts(posts)
            
            # 2. Build Chronological Chain
            self.knowledge_graph.link_chronologically()
            
            # 3. Link Clusters (if detected)
            if self.current_clusters:
                self.knowledge_graph.link_clusters(self.current_clusters)
            
            # 4. Link Semantic Similarity
            if self.semantic_memory:
                print("[Pipeline] Building semantic similarity links in Neo4j...")
                for post in posts:
                    pid = post.get("id")
                    if pid:
                        similar = self.semantic_memory.find_similar_posts(str(pid), n_results=3)
                        self.knowledge_graph.link_similarity(str(pid), similar)
            
            return self.knowledge_graph.get_graph_stats()
        except Exception as e:
            print(f"[Pipeline] Error during Neo4j relationship build: {e}")
            return {"status": "error", "message": str(e)}

    def run_reasoning(self) -> Dict[str, Any]:
        """Stage 5: Run reasoning engine and generate insights."""
        try:
            self.latest_report = self.reasoning_engine.generate_insights_report(
                self.current_posts, getattr(self, 'current_clusters', [])
            )
            if hasattr(self.reasoning_engine, 'save_report'):
                self.reasoning_engine.save_report(self.latest_report)
            return self.latest_report
        except AttributeError as e:
            print(f"[Pipeline] Reasoning engine requires extended graph schema not supported directly here: {e}")
            return {}
        except Exception as e:
            print(f"[Pipeline] Reasoning engine encountered an error: {e}")
            return {}

    # ============================================================
    # Full Pipeline Run
    # ============================================================

    def run(self, dry_run: bool = False) -> Dict[str, Any]:
        """Execute the complete pipeline."""
        start_time = time.time()
        report = {
            "started_at": datetime.utcnow().isoformat(),
            "dry_run": dry_run,
            "stages": {},
            "success": True,
        }

        if dry_run:
            return self._dry_run(report)

        try:
            # Stage 1: WordPress
            posts = self.fetch_wordpress_posts()
            report["stages"]["content"] = {"status": "success", "count": len(posts)}

            if not posts:
                posts = self._load_cached_posts()
                if posts:
                    self.current_posts = posts

            # Stage 2: Apply default metrics (CSV can be loaded separately)
            report["stages"]["performance"] = {
                "status": "success",
                "count": len(self.current_posts),
                "decaying": len([p for p in self.current_posts if p.get("decay_flag")]),
            }

            # Stage 3: Embeddings
            if self.semantic_memory:
                stored = self.update_embeddings()
                report["stages"]["semantic"] = {
                    "status": "success",
                    "stored": stored,
                    "clusters": len(self.current_clusters),
                }
            else:
                report["stages"]["semantic"] = {"status": "skipped"}

            # Stage 4: Knowledge Graph
            if self.knowledge_graph and self.knowledge_graph.driver:
                graph_stats = self.update_knowledge_graph()
                report["stages"]["graph"] = {"status": "success", "stats": graph_stats}
            else:
                report["stages"]["graph"] = {"status": "skipped"}

            # Stage 5: Reasoning
            insights = self.run_reasoning()
            report["stages"]["reasoning"] = {
                "status": "success",
                "summary": insights.get("summary", {}),
            }

        except Exception as e:
            print(f"[Pipeline] ERROR: {e}")
            report["success"] = False
            report["error"] = str(e)

        elapsed = round(time.time() - start_time, 2)
        report["completed_at"] = datetime.utcnow().isoformat()
        report["elapsed_seconds"] = elapsed
        return report

    def _dry_run(self, report):
        """Verify component connectivity."""
        print("\n[Pipeline] DRY RUN\n")

        checks = {
            "content": {"status": "ready", "api": config.WORDPRESS_API_BASE},
            "performance": {"status": "ready", "mode": "csv_upload"},
            "semantic": {
                "status": "ready" if self.semantic_memory else "not_configured",
            },
            "graph": {
                "status": "ready" if (self.knowledge_graph and self.knowledge_graph.driver) else "not_connected",
            },
            "reasoning": {
                "status": "ready" if self.reasoning_engine.llm else "not_configured",
            },
        }

        for name, data in checks.items():
            icon = "✓" if data["status"] == "ready" else "✗"
            print(f"  {icon} {name.upper()}: {data['status']}")

        report["stages"] = checks
        report["success"] = True
        return report

    # ============================================================
    # Scheduling
    # ============================================================

    def schedule_daily(self, hour: int = 3, minute: int = 0):
        """Schedule the pipeline to run daily."""
        time_str = f"{hour:02d}:{minute:02d}"
        schedule.every().day.at(time_str).do(self.run)
        print(f"[Pipeline] Scheduled daily at {time_str} — Ctrl+C to stop\n")

        try:
            while True:
                schedule.run_pending()
                time.sleep(60)
        except KeyboardInterrupt:
            print("\n[Pipeline] Scheduler stopped")

    def _load_cached_posts(self):
        """Load posts from cache."""
        for path in [config.PERFORMANCE_MEMORY_PATH, config.CONTENT_MEMORY_PATH]:
            if os.path.exists(path):
                with open(path, "r", encoding="utf-8") as f:
                    return json.load(f)
        return None

    def cleanup(self):
        """Close connections."""
        if self.knowledge_graph:
            self.knowledge_graph.close()


# ============================================================
# Standalone Usage
# ============================================================
if __name__ == "__main__":
    pipeline = MemoryPipeline()
    report = pipeline.run()
    pipeline.cleanup()
