"""
============================================================
semantic_memory.py — Embeddings & ChromaDB Vector Store
============================================================
Generates OpenAI embeddings for WordPress posts (content_memory.json).
Stores them in ChromaDB for semantic search.
Supports similarity queries and clustering for WordPress content.
============================================================
============================================================
"""

import os
import json
import hashlib
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime

import openai
import chromadb

import config


class SemanticMemory:
    """
    Manages semantic embeddings and vector search.

    Handles WordPress posts, storing all as embeddings 
    in ChromaDB for semantic search.
    """

    def __init__(self):
        """Initialize OpenAI client and ChromaDB persistent storage."""
        # ---- OpenAI Client ----
        self.openai_client = openai.OpenAI(api_key=config.OPENAI_API_KEY)
        self.embedding_model = config.EMBEDDING_MODEL

        # ---- ChromaDB Client ----
        os.makedirs(config.CHROMADB_PERSIST_DIR, exist_ok=True)
        self.chroma_client = chromadb.PersistentClient(
            path=config.CHROMADB_PERSIST_DIR,
        )

        self.collection = self.chroma_client.get_or_create_collection(
            name=config.CHROMADB_COLLECTION_NAME,
            metadata={"description": "WordPress posts and uploaded content embeddings"},
        )

        print(f"[Semantic Memory] ChromaDB initialized — {self.collection.count()} existing embeddings")

    # ============================================================
    # Embedding Generation
    # ============================================================

    def generate_embedding(self, text: str) -> List[float]:
        """Generate an embedding vector for text using OpenAI."""
        max_chars = 8000
        truncated = text[:max_chars] if len(text) > max_chars else text

        try:
            response = self.openai_client.embeddings.create(
                input=truncated,
                model=self.embedding_model,
            )
            return response.data[0].embedding
        except Exception as e:
            print(f"[Semantic Memory] Embedding error: {e}")
            return [0.0] * config.EMBEDDING_DIMENSIONS

    def generate_embeddings_batch(self, texts: List[str], batch_size: int = 50) -> List[List[float]]:
        """Generate embeddings for multiple texts in batches."""
        all_embeddings = []

        for i in range(0, len(texts), batch_size):
            batch = [t[:8000] for t in texts[i : i + batch_size]]

            try:
                response = self.openai_client.embeddings.create(
                    input=batch,
                    model=self.embedding_model,
                )
                all_embeddings.extend([item.embedding for item in response.data])
                print(f"[Semantic Memory] Embeddings: {i + len(batch)}/{len(texts)}")
            except Exception as e:
                print(f"[Semantic Memory] Batch error: {e}")
                all_embeddings.extend([[0.0] * config.EMBEDDING_DIMENSIONS] * len(batch))

        return all_embeddings

    # ============================================================
    # Store WordPress Posts
    # ============================================================

    def store_chunks(self, chunks: List[Dict[str, Any]]) -> int:
        """
        Generate embeddings for granular section chunks and store in ChromaDB.

        Args:
            chunks: List of chunk dictionaries with 'chunk_id', 'content', etc.

        Returns:
            Number of chunks stored.
        """
        print(f"[Semantic Memory] Storing {len(chunks)} chunks...")

        # Combine title, heading and content for optimal embedding context
        texts = [
            f"{c.get('title', '')} - {c.get('section_heading', '')}: {c.get('content', '')}"
            for c in chunks
        ]

        embeddings = self.generate_embeddings_batch(texts)

        ids = [str(c.get("chunk_id")) for c in chunks]
        metadatas = [
            {
                "chunk_id": str(c.get("chunk_id")),
                "parent_post_id": str(c.get("parent_post_id")),
                # source_file = parent_post_id for document chunks (the filename)
                "source_file": str(c.get("parent_post_id")),
                "title": c.get("title", ""),
                "section_heading": c.get("section_heading", ""),
                "categories": json.dumps(c.get("category", [])),
                "publish_date": c.get("publish_date", ""),
                "source": "wordpress_chunk",
                "type": "section",
            }
            for c in chunks
        ]

        # Store full content text alongside embedding for graph sync
        documents = [c.get("content", t) for c, t in zip(chunks, texts)]

        self.collection.upsert(
            ids=ids, embeddings=embeddings, documents=documents, metadatas=metadatas,
        )

        print(f"[Semantic Memory] Stored {len(ids)} chunks — total: {self.collection.count()}")
        return len(ids)

    def store_posts(self, posts: List[Dict[str, Any]]) -> int:
        """
        DEPRECATED: Use store_chunks instead.
        Kept for backward compatibility during transition.
        """
        print("[Semantic Memory] store_posts is deprecated, redirecting to store_chunks if possible")
        if posts and "chunk_id" in posts[0]:
            return self.store_chunks(posts)
        
        # Original logic for full posts (if still needed)
        texts = [f"{post.get('title', '')}. {post.get('content', '')}" for post in posts]
        embeddings = self.generate_embeddings_batch(texts)
        ids = [str(post.get("id", i)) for i, post in enumerate(posts)]
        metadatas = [{
            "id": str(post.get("id", "")),
            "title": post.get("title", ""),
            "source": "wordpress_post",
            "type": "post"
        } for post in posts]
        
        self.collection.upsert(ids=ids, embeddings=embeddings, documents=texts, metadatas=metadatas)
        return len(ids)

    # ============================================================
    # Semantic Search / Queries
    # ============================================================

    def query_similar(self, query_text: str, n_results: int = 5) -> List[Dict[str, Any]]:
        """Find the most semantically similar items to a query text."""
        query_embedding = self.generate_embedding(query_text)

        count = self.collection.count()
        if count == 0:
            return []

        results = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=min(n_results, count),
            include=["metadatas", "documents", "distances"],
        )

        formatted = []
        if results and results["ids"]:
            for i, doc_id in enumerate(results["ids"][0]):
                formatted.append({
                    "id": doc_id,
                    "metadata": results["metadatas"][0][i] if results["metadatas"] else {},
                    "distance": results["distances"][0][i] if results["distances"] else 0,
                    "similarity": 1 - (results["distances"][0][i] if results["distances"] else 0),
                    "document_preview": (
                        results["documents"][0][i][:200] + "..."
                        if results["documents"] and len(results["documents"][0][i]) > 200
                        else results["documents"][0][i] if results["documents"] else ""
                    ),
                })

        return formatted

    def find_similar_posts(self, post_id: str, n_results: int = 5) -> List[Dict[str, Any]]:
        """Find items semantically similar to a given post by ID."""
        try:
            result = self.collection.get(
                ids=[str(post_id)], include=["embeddings", "documents"],
            )

            if not result["embeddings"]:
                return []

            similar = self.collection.query(
                query_embeddings=[result["embeddings"][0]],
                n_results=n_results + 1,
                include=["metadatas", "documents", "distances"],
            )

            formatted = []
            for i, doc_id in enumerate(similar["ids"][0]):
                if doc_id != str(post_id):
                    formatted.append({
                        "id": doc_id,
                        "metadata": similar["metadatas"][0][i],
                        "distance": similar["distances"][0][i],
                        "similarity": 1 - similar["distances"][0][i],
                    })

            return formatted[:n_results]

        except Exception as e:
            print(f"[Semantic Memory] Error: {e}")
            return []

    # ============================================================
    # Weak Content Detection
    # ============================================================

    def find_weak_content(self, health_threshold: float = None) -> List[Dict[str, Any]]:
        """Find items with low health scores."""
        threshold = health_threshold or config.DECAY_HEALTH_THRESHOLD

        all_posts = self.collection.get(include=["metadatas"])

        weak = []
        if all_posts and all_posts["metadatas"]:
            for i, metadata in enumerate(all_posts["metadatas"]):
                health = metadata.get("health_score", 0)
                if health < threshold:
                    weak.append({
                        "id": all_posts["ids"][i],
                        "title": metadata.get("title", ""),
                        "slug": metadata.get("slug", ""),
                        "health_score": health,
                        "decay_flag": metadata.get("decay_flag", "False"),
                        "source": metadata.get("source", "unknown"),
                    })

        weak.sort(key=lambda x: x["health_score"])
        return weak

    # ============================================================
    # Clustering
    # ============================================================

    def detect_clusters(self, n_clusters: int = 5) -> List[Dict[str, Any]]:
        """Group semantically similar items into clusters."""
        print("[Semantic Memory] Detecting clusters...")

        all_data = self.collection.get(include=["embeddings", "metadatas"])

        if not all_data["ids"]:
            return []

        num = len(all_data["ids"])
        if num <= n_clusters:
            return [
                {
                    "cluster_id": i,
                    "posts": [all_data["ids"][i]],
                    "centroid_title": all_data["metadatas"][i].get("title", ""),
                    "size": 1,
                }
                for i in range(num)
            ]

        clusters = []
        assigned = set()
        embeddings = all_data["embeddings"]

        for i in range(num):
            if all_data["ids"][i] in assigned:
                continue

            cluster = {
                "cluster_id": len(clusters),
                "posts": [all_data["ids"][i]],
                "titles": [all_data["metadatas"][i].get("title", "")],
                "centroid_title": all_data["metadatas"][i].get("title", ""),
            }
            assigned.add(all_data["ids"][i])

            results = self.collection.query(
                query_embeddings=[embeddings[i]],
                n_results=min(num // n_clusters + 2, num),
                include=["metadatas", "distances"],
            )

            for j, doc_id in enumerate(results["ids"][0]):
                if doc_id not in assigned and results["distances"][0][j] < 0.5:
                    cluster["posts"].append(doc_id)
                    cluster["titles"].append(results["metadatas"][0][j].get("title", ""))
                    assigned.add(doc_id)

            cluster["size"] = len(cluster["posts"])
            clusters.append(cluster)

            if len(clusters) >= n_clusters and len(assigned) >= num * 0.8:
                break

        # Assign remaining
        for i in range(num):
            if all_data["ids"][i] not in assigned:
                results = self.collection.query(
                    query_embeddings=[embeddings[i]], n_results=1, include=["distances"],
                )
                nearest_id = results["ids"][0][0]
                for cluster in clusters:
                    if nearest_id in cluster["posts"]:
                        cluster["posts"].append(all_data["ids"][i])
                        cluster["size"] = len(cluster["posts"])
                        assigned.add(all_data["ids"][i])
                        break

        print(f"[Semantic Memory] Detected {len(clusters)} clusters")
        return clusters

    # ============================================================
    # Utilities
    # ============================================================

    def get_collection_stats(self) -> Dict[str, Any]:
        """Get ChromaDB collection statistics."""
        count = self.collection.count()
        all_data = self.collection.get(include=["metadatas"])

        health_scores = [
            m.get("health_score", 0)
            for m in (all_data["metadatas"] or [])
            if m.get("health_score") is not None
        ]

        # Count by source type
        sources = {}
        for m in (all_data["metadatas"] or []):
            src = m.get("source", "unknown")
            sources[src] = sources.get(src, 0) + 1

        return {
            "total_items": count,
            "sources": sources,
            "avg_health_score": round(sum(health_scores) / max(len(health_scores), 1), 3),
            "min_health_score": round(min(health_scores), 3) if health_scores else 0,
            "max_health_score": round(max(health_scores), 3) if health_scores else 0,
        }

    def get_all_items(self) -> List[Dict[str, Any]]:
        """Get all items from the collection with full metadata and document text."""
        all_data = self.collection.get(include=["metadatas", "documents"])
        items = []
        if all_data and all_data["ids"]:
            for i, doc_id in enumerate(all_data["ids"]):
                items.append({
                    "id": doc_id,
                    "metadata": all_data["metadatas"][i] if all_data["metadatas"] else {},
                    # Return the full document text (not a truncated preview)
                    "document": all_data["documents"][i] if all_data["documents"] else "",
                })
        return items

    def delete_by_file_id(self, file_id: str) -> bool:
        """Delete all items associated with a specific file_id."""
        if not file_id:
            return False
            
        print(f"[Semantic Memory] Deleting items for file_id: {file_id}")
        try:
            # We use parent_post_id as the filter key for document chunks
            self.collection.delete(where={"parent_post_id": str(file_id)})
            return True
        except Exception as e:
            print(f"[Semantic Memory] Delete error: {e}")
            return False

    def clear_collection(self):
        """Delete all embeddings."""
        self.chroma_client.delete_collection(config.CHROMADB_COLLECTION_NAME)
        self.collection = self.chroma_client.create_collection(
            name=config.CHROMADB_COLLECTION_NAME,
        )
        print("[Semantic Memory] Collection cleared")


# ============================================================
# Standalone Usage
# ============================================================
if __name__ == "__main__":
    sm = SemanticMemory()
    stats = sm.get_collection_stats()
    print(f"\nCollection stats: {json.dumps(stats, indent=2)}")
