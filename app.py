"""
============================================================
app.py — Flask Backend for AI Memory System
============================================================
Provides a REST API for the dashboard and serves static files.
============================================================
"""

import os
import json
import logging
import subprocess
import socket
import time
import threading
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from werkzeug.utils import secure_filename
from flasgger import Swagger

import config
from pipeline import MemoryPipeline
from data_manager import DataManager

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ============================================================
# Neo4j Startup Utilities (Must be defined first)
# ============================================================

def is_neo4j_running():
    """Check if Neo4j is already running on the default Bolt port (7687)."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(('localhost', 7687)) == 0

def ensure_neo4j_running():
    """Ensure Neo4j is running, start it if not."""
    if is_neo4j_running():
        logger.info("Neo4j is already running.")
        return True
    
    logger.info("Neo4j not detected. Attempting to start...")
    neo4j_path = r"C:\Users\haris\Downloads\neo4j-community-5.26.21-windows\neo4j-community-5.26.21\bin\neo4j.bat"
    
    try:
        # Start Neo4j in a new console window
        subprocess.Popen(f'start "Neo4j_Server" "{neo4j_path}" console', shell=True)
        
        # Wait for the service to actually start before continuing
        logger.info("Neo4j start command issued. Waiting for server to initialize (10s)...")
        time.sleep(10)
        return True
    except Exception as e:
        logger.error(f"Failed to start Neo4j: {e}")
        return False

# ============================================================
# Initialize Application
# ============================================================

# 1. Ensure Neo4j is ready before we create the Pipeline
# (The Pipeline initializes the KnowledgeGraph connection)
ensure_neo4j_running()

app = Flask(__name__, static_folder='static')
CORS(app)  # Enable CORS for all routes
swagger = Swagger(app)

# 2. Initialize the pipeline and data manager
pipeline = MemoryPipeline()
data_manager = DataManager()

# Ensure upload directory exists
os.makedirs(config.UPLOAD_DIR, exist_ok=True)

# ============================================================
# Static Files
# ============================================================

@app.route('/')
def index():
    return send_from_directory('static', 'index.html')

@app.route('/<path:path>')
def static_files(path):
    return send_from_directory('static', path)

# ============================================================
# Data Management Endpoints
# ============================================================

@app.route('/api/data/list', methods=['GET'])
def list_data():
    """List all managed data files.
    ---
    responses:
      200:
        description: A list of managed files.
        schema:
          type: array
          items:
            type: object
            properties:
              filename:
                type: string
              type:
                type: string
              added_at:
                type: string
              status:
                type: string
    """
    return jsonify(data_manager.list_files())

@app.route('/api/data/delete/<file_id>', methods=['DELETE'])
def delete_data(file_id):
    """Delete a managed data file."""
    success = data_manager.delete_file(
        file_id,
        semantic_memory=pipeline.semantic_memory,
        knowledge_graph=pipeline.knowledge_graph
    )
    if success:
        return jsonify({"status": "success"})
    return jsonify({"status": "error", "message": "File not found"}), 404

@app.route('/api/data/process/<file_id>', methods=['POST'])
def process_data(file_id):
    """Trigger the automated processing pipeline for a file."""
    def status_callback(fid, status):
        # Update the manifest directly whenever a stage completes
        data_manager.update_status(fid, "processing", status)
        
    try:
        # Use the callback to update manifest during the run
        result = pipeline.process_file_pipeline(file_id, data_manager, status_callback=status_callback)
        return jsonify({
            "status": "success",
            "message": f"File {file_id} processed through the complete pipeline successfully",
            "file": data_manager.get_file(file_id)
        })
    except Exception as e:
        logger.error(f"Pipeline error for file {file_id}: {e}")
        data_manager.update_status(file_id, "processing", "failed")
        return jsonify({"status": "error", "message": str(e)}), 500

# ============================================================
# Core Pipeline Triggers
# ============================================================

@app.route('/api/status', methods=['GET'])
def get_status():
    """Get system status and basic stats."""
    sm_ok = pipeline.semantic_memory is not None
    kg_ok = pipeline.knowledge_graph and pipeline.knowledge_graph.driver is not None
    llm_ok = pipeline.reasoning_engine.llm is not None
    
    stats = {}
    graph_stats = {}
    
    if sm_ok:
        stats = pipeline.semantic_memory.get_collection_stats()
    
    if kg_ok:
        graph_stats = pipeline.knowledge_graph.get_graph_stats()
        
    return jsonify({
        "components": {
            "chromadb": sm_ok,
            "neo4j": kg_ok,
            "groq": llm_ok,
            "wordpress": True
        },
        "stats": stats,
        "graph_stats": graph_stats
    })

@app.route('/api/graph/details', methods=['GET'])
def get_graph_details():
    """Get detailed graph entity information."""
    if not pipeline.knowledge_graph:
        return jsonify({"status": "error", "message": "KnowledgeGraph not initialized"}), 500
        
    try:
        entities = pipeline.knowledge_graph.get_latest_entities(limit=20)
        stats = pipeline.knowledge_graph.get_graph_stats()
        return jsonify({
            "entities": entities,
            "stats": stats
        })
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/fetch_posts', methods=['POST'])
def fetch_posts():
    """Trigger WordPress post fetching."""
    try:
        posts = pipeline.fetch_wordpress_posts()
        return jsonify({
            "status": "success",
            "count": len(posts)
        })
    except Exception as e:
        logger.error(f"Error fetching posts: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/pages', methods=['GET'])
def get_pages():
    """Get lightweight page metadata (id, url, title, publish_date)."""
    if os.path.exists(config.PAGES_METADATA_PATH):
        with open(config.PAGES_METADATA_PATH, "r", encoding="utf-8") as f:
            return jsonify(json.load(f))
    return jsonify([])

@app.route('/api/content', methods=['GET'])
def get_content():
    """Get all fetched posts/content."""
    posts = pipeline.current_posts
    if not posts:
        # Try to load from cache
        posts = pipeline._load_cached_posts() or []
        pipeline.current_posts = posts
        
    return jsonify(posts)

@app.route('/api/upload_document', methods=['POST'])
def upload_document():
    """Handle document uploads (.txt, .pdf, .md).
    ---
    parameters:
      - name: file
        in: formData
        type: file
        required: true
        description: The document file to upload.
    responses:
      200:
        description: Document successfully uploaded and registered.
      400:
        description: Invalid file or missing file part.
    """
    if 'file' not in request.files:
        return jsonify({"status": "error", "message": "No file part"}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({"status": "error", "message": "No selected file"}), 400
    
    allowed_extensions = ('.txt', '.pdf', '.md')
    if file and file.filename.lower().endswith(allowed_extensions):
        filename = secure_filename(file.filename)
        
        # Save directly into the data/uploads folder that DataManager tracks
        # (NOT input_docs — that was causing the path mismatch in the manifest)
        upload_dir = os.path.join(os.path.dirname(__file__), "data", "uploads")
        os.makedirs(upload_dir, exist_ok=True)
        filepath = os.path.join(upload_dir, filename)
        file.save(filepath)
        
        # Also copy to doc_converter/input_docs for the converter
        input_docs_dir = os.path.join(os.path.dirname(__file__), "doc_converter", "input_docs")
        os.makedirs(input_docs_dir, exist_ok=True)
        import shutil
        shutil.copy2(filepath, os.path.join(input_docs_dir, filename))
        
        # Determine type for data manager
        file_ext = filename.rsplit('.', 1)[1].lower() if '.' in filename else 'txt'
        
        # Register with data manager — filepath is now correctly in data/uploads/
        entry = data_manager.add_file(filename, file_ext, filepath)
        
        # Async background processing function
        def run_pipeline_async(file_id):
            with app.app_context():
                # Map pipeline stage names to valid DataManager component keys
                STAGE_TO_COMPONENT = {
                    "converting": "conversion",
                    "chunking":   "semantic",
                    "embedding":  "semantic",
                    "indexing":   "graph",
                    "ready":      None,   # No component for final status
                }
                def status_callback(fid, stage):
                    component = STAGE_TO_COMPONENT.get(stage)
                    if component:
                        data_manager.update_status(fid, component, stage)
                try:
                    logger.info(f"Starting async pipeline for {file_id}")
                    pipeline.process_file_pipeline(file_id, data_manager, status_callback=status_callback)
                    logger.info(f"Finished async pipeline for {file_id}")
                except Exception as e:
                    logger.error(f"Async pipeline error for {file_id}: {e}")
                    # Mark all components as failed in the manifest
                    for comp in ["conversion", "semantic", "graph"]:
                        data_manager.update_status(file_id, comp, "failed")
        
        # Kick off background thread
        processing_thread = threading.Thread(target=run_pipeline_async, args=(entry["id"],), daemon=True)
        processing_thread.start()
        
        return jsonify({
            "status": "success",
            "message": f"Document ({file_ext.upper()}) uploaded. Processing started in background.",
            "file": entry
        })
            
    return jsonify({"status": "error", "message": "Invalid file type. Only .txt, .pdf, and .md are supported."}), 400

@app.route('/api/update_embeddings', methods=['POST'])
def update_embeddings():
    """Trigger ChromaDB updates."""
    try:
        count = pipeline.update_embeddings()
        return jsonify({
            "status": "success",
            "count": count,
            "clusters": len(pipeline.current_clusters)
        })
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/run_reasoning', methods=['POST'])
def run_reasoning():
    """Trigger reasoning engine and get insights."""
    try:
        report = pipeline.run_reasoning()
        return jsonify(report)
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/search', methods=['POST'])
def semantic_search_rag():
    """Hybrid RAG search: Semantic + Graph retrieval with re-ranking."""
    data = request.json
    query = data.get('query')
    
    if not query:
        return jsonify({"status": "error", "message": "No query provided"}), 400
        
    try:
        # Get Global Stats for the prompt
        system_stats = pipeline.semantic_memory.get_collection_stats()
        
        # Call the refactored reasoning engine which handles the whole hybrid pipeline
        result = pipeline.reasoning_engine.answer_query(query, system_stats)
        
        return jsonify({
            "answer": result["answer"],
            "answer_structured": result.get("answer_structured", ""),
            "context_count": len(result["sources"]),
            "sources": [
                {
                    "title": f"{s.get('article_title', s.get('document', 'Unknown'))} > {s.get('section', '')}",
                    "url": s.get("url", ""),
                    "similarity": s.get("score", 0),
                    "confidence": s.get("confidence", "low")
                } 
                for s in result["sources"][:5]
            ]
        })
    except Exception as e:
        logger.error(f"Hybrid search error: {e}")
        return jsonify({"status": "error", "message": f"Hybrid search failed: {str(e)}"}), 500

@app.route('/api/insights', methods=['GET'])
def get_insights():
    """Get the latest insights report."""
    if not pipeline.latest_report:
        if os.path.exists(config.INSIGHTS_PATH):
            with open(config.INSIGHTS_PATH, "r", encoding="utf-8") as f:
                pipeline.latest_report = json.load(f)
                
    return jsonify(pipeline.latest_report or {})

@app.route('/api/semantic/detail', methods=['GET'])
def get_semantic_detail():
    """Get detailed embedding status from ChromaDB and DataManager."""
    if not pipeline.semantic_memory:
        return jsonify({"status": "error", "message": "SemanticMemory not initialized"}), 500
        
    try:
        # 1. Get all items in ChromaDB
        chroma_items = pipeline.semantic_memory.get_all_items()
        
        # 2. Get all managed files
        managed_files = data_manager.list_files()
        
        # 3. Consolidate status
        return jsonify({
            "chroma_items": chroma_items,
            "managed_files": managed_files,
            "stats": pipeline.semantic_memory.get_collection_stats()
        })
    except Exception as e:
        logger.error(f"Error fetching semantic detail: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/knowledge/analytics', methods=['GET'])
def get_knowledge_analytics():
    """Get advanced graph intelligence and analytics."""
    if not pipeline.knowledge_graph:
        return jsonify({"status": "error", "message": "KnowledgeGraph not initialized"}), 500
    return jsonify(pipeline.knowledge_graph.get_knowledge_analytics())

@app.route('/api/ask', methods=['POST'])
def ask_question():
    """Document QA endpoint: answers a question using RAG over ingested documents.
    ---
    parameters:
      - name: body
        in: body
        required: true
        schema:
          type: object
          properties:
            question:
              type: string
              example: "What is New Product Development?"
    responses:
      200:
        description: AI-generated answer based on the documents.
        schema:
          type: object
          properties:
            answer:
              type: string
            confidence:
              type: string
            sources:
              type: array
              items:
                type: object
      400:
        description: No question provided.
    """
    data = request.json
    question = data.get('question', '').strip()

    if not question:
        return jsonify({"status": "error", "message": "No question provided"}), 400

    try:
        system_stats = pipeline.semantic_memory.get_collection_stats()
        result = pipeline.reasoning_engine.answer_query(question, system_stats)

        sources = []
        for s in result.get("sources", [])[:5]:
            doc_name = s.get('article_title') or s.get('document') or 'Unknown Document'
            section = s.get('section', '')
            if section and section != "General":
                label = f"{doc_name} › {section}"
            else:
                label = doc_name

            snippet = s.get('snippet', '')
            if len(snippet) > 250:
                snippet = snippet[:250] + '...'

            score = s.get('score', 0)
            sources.append({
                "document": doc_name,
                "label": label,
                "snippet": snippet,
                "score": score,
                "confidence": s.get("confidence", "low"),
                "url": s.get('url', '')
            })

        # Derive confidence from top source similarity percentage (0-100)
        top_similarity = sources[0]['score'] if sources else 0
        if top_similarity >= 40:
            confidence = "high"
        elif top_similarity >= 20:
            confidence = "medium"
        else:
            confidence = "low"

        answer = result.get("answer", "")
        answer_structured = result.get("answer_structured", "")
        print(f"DEBUG: result keys: {list(result.keys())}")
        print(f"DEBUG: answer_structured length: {len(answer_structured) if answer_structured else 'None'}")
        
        no_info = (
            not answer or
            not sources or
            "no relevant" in answer.lower() or
            "cannot find" in answer.lower() or
            "not found" in answer.lower() or
            "could not find" in answer.lower() or
            "i don't know" in answer.lower() or
            "i do not know" in answer.lower() or
            (len(sources) == 0 and len(answer) < 80)
        )

        return jsonify({
            "answer": answer,
            "answer_structured": answer_structured,
            "sources": sources,
            "confidence": confidence,
            "no_relevant_info": no_info
        })
    except Exception as e:
        logger.error(f"QA error: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)

