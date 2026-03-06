"""
============================================================
reranker.py — Multi-Factor Scoring Engine
============================================================
Calculates a final relevance score for retrieved chunks using:
1. Semantic Similarity (Vector)
2. Graph Connectivity (Neo4j)
3. Category Coherence
4. Recency (Temporal decay)
============================================================
"""

from typing import List, Dict, Any
from datetime import datetime
import json

class SectionReranker:
    """
    Reranks granular chunks based on multiple signals.
    """

    def __init__(self, 
                 vector_weight: float = 0.6, 
                 graph_weight: float = 0.2, 
                 category_weight: float = 0.1, 
                 recency_weight: float = 0.1):
        self.w_vector = vector_weight
        self.w_graph = graph_weight
        self.w_category = category_weight
        self.w_recency = recency_weight

    def rerank(self, 
               query: str, 
               chunks: List[Dict[str, Any]], 
               graph_nodes: List[Dict[str, Any]] = None,
               target_categories: List[str] = None) -> List[Dict[str, Any]]:
        """
        Applies scoring formula to a list of candidate chunks.
        
        Args:
            query: The original user question.
            chunks: List of candidates from vector search (must contain 'similarity').
            graph_nodes: Optional enrichment from Neo4j relationships.
            target_categories: Categories relevant to the query context.
            
        Returns:
            Sorted list of chunks with 'rerank_score' attached.
        """
        # 1. Map graph connections for easy lookup
        # graph_nodes should be a list of dicts with {id: parent_id, weight: connection_strength}
        post_graph_weights = {str(node['id']): node.get('weight', 0.5) for node in (graph_nodes or [])}
        
        # 2. Get reference date for recency (use latest in chunks if available)
        now = datetime.now()
        
        for chunk in chunks:
            # --- SIGNAL 1: Vector Similarity (already 0.0 to 1.0 ideally) ---
            v_score = chunk.get("similarity", 0.0)
            
            # --- SIGNAL 2: Graph Connectivity ---
            parent_id = str(chunk.get("parent_post_id"))
            g_score = post_graph_weights.get(parent_id, 0.0)
            
            # --- SIGNAL 3: Category Match ---
            c_score = 0.0
            if target_categories:
                chunk_cats = chunk.get("category", [])
                matches = set(chunk_cats).intersection(set(target_categories))
                if matches:
                    c_score = 1.0 # Simple binary for now, could be ratio
            
            # --- SIGNAL 4: Recency ---
            r_score = 0.0
            pub_date_str = chunk.get("publish_date")
            if pub_date_str:
                try:
                    # Handle typical ISO strings
                    pub_date = datetime.fromisoformat(pub_date_str.replace('Z', ''))
                    days_old = (now - pub_date).days
                    # Normalize: 1.0 for fresh, decays over 2 years (730 days)
                    r_score = max(0.0, 1.0 - (days_old / 730))
                except:
                    r_score = 0.5 # Neutral fallback
            
            # Compute final weighted score
            final_score = (
                (v_score * self.w_vector) +
                (g_score * self.w_graph) +
                (c_score * self.w_category) +
                (r_score * self.w_recency)
            )
            
            chunk["rerank_score"] = round(final_score, 4)
            chunk["score_breakdown"] = {
                "vector": round(v_score, 3),
                "graph": round(g_score, 3),
                "category": round(c_score, 3),
                "recency": round(r_score, 3)
            }

        # Sort by final score descending
        chunks.sort(key=lambda x: x["rerank_score"], reverse=True)
        return chunks
