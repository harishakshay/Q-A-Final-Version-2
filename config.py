"""
============================================================
config.py — Centralized Configuration
============================================================
Loads environment variables from .env and exposes typed
constants used by all modules in the AI Memory System.
============================================================
"""

import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


# ============================================================
# WordPress Configuration
# ============================================================
WORDPRESS_URL = os.getenv("WORDPRESS_URL", "https://mydomain.com")
WORDPRESS_API_BASE = f"{WORDPRESS_URL}/wp-json/wp/v2"
WORDPRESS_USERNAME = os.getenv("WORDPRESS_USERNAME", "")
WORDPRESS_APP_PASSWORD = os.getenv("WORDPRESS_APP_PASSWORD", "")

# ============================================================
# Embedding Configuration (OpenAI by default)
# ============================================================
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
EMBEDDING_PROVIDER = os.getenv("EMBEDDING_PROVIDER", "openai")
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")
EMBEDDING_DIMENSIONS = 1536                 # Output dimensions for text-embedding-3-small

# ============================================================
# Groq Configuration (for LLM reasoning)
# ============================================================
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_MODEL = "llama-3.3-70b-versatile"  # Fast inference model

# ============================================================
# Neo4j Configuration (local Community Edition)
# ============================================================
NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USERNAME = os.getenv("NEO4J_USERNAME", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "")

# ============================================================
# ChromaDB Configuration
# ============================================================
CHROMADB_PERSIST_DIR = os.getenv("CHROMADB_PERSIST_DIR", "./data/chromadb")
CHROMADB_COLLECTION_NAME = "wordpress_posts"

# ============================================================
# Data Storage Paths
# ============================================================
DATA_DIR = "./data"
UPLOAD_DIR = os.path.join(DATA_DIR, "uploads")
DOCS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "docs")
CONTENT_MEMORY_PATH = os.path.join(DATA_DIR, "content_memory.json")
PERFORMANCE_MEMORY_PATH = os.path.join(DATA_DIR, "performance_memory.json")
INSIGHTS_PATH = os.path.join(DATA_DIR, "insights_report.json")
PAGES_METADATA_PATH = os.path.join(DATA_DIR, "pages_metadata.json")

# ============================================================
# Health Score Weights
# ============================================================
HEALTH_WEIGHTS = {
    "ctr": 0.3,            # Click-through rate weight
    "engagement": 0.3,     # Engagement time weight
    "bounce": 0.2,         # Bounce rate weight (inverted — lower is better)
    "trend": 0.2,          # Trend/recency weight
}

# ============================================================
# Thresholds
# ============================================================
DECAY_HEALTH_THRESHOLD = 0.7     # Posts below this are flagged as decaying
DECAY_AGE_DAYS = 90              # Posts older than this are candidates for decay
WEAK_CLUSTER_THRESHOLD = 0.6    # Clusters with avg health below this are weak
SIMILARITY_THRESHOLD = 0.8       # Minimum similarity for cross-link suggestions
