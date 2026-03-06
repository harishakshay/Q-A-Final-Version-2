"""
============================================================
hybrid_retrieval.py — Hybrid Search Orchestrator
============================================================
Coordinates:
1. Query Classification (Intent)
2. Vector Search (ChromaDB Chunks)
3. Graph Expansion (Neo4j Neighbors)
4. Multi-Factor Reranking (SectionReranker)
============================================================
"""

from typing import List, Dict, Any, Optional
import json

from query_classifier import QueryClassifier
from reranker import SectionReranker

class HybridRetrievalEngine:
    """
    Orchestrates the hybrid retrieval pipeline.
    """

    def __init__(self, semantic_memory, knowledge_graph):
        self.semantic_memory = semantic_memory
        self.knowledge_graph = knowledge_graph
        self.classifier = QueryClassifier()
        self.reranker = SectionReranker()

    def retrieve(self, query: str, top_n: int = 5) -> List[Dict[str, Any]]:
        """
        Executes the full hybrid retrieval flow.
        """
        print(f"\n[Hybrid Retrieval] Processing query: \"{query}\"")
        
        # 1. Classify Query
        intent = self.classifier.classify(query)
        strategy = self.classifier.get_retrieval_strategy(intent)
        print(f"[Hybrid Retrieval] Intent: {intent} (Strategy: Vector={strategy['vector_weight']}, Graph={strategy['graph_weight']})")

        # 2. Stage 1: Vector Search (ChromaDB)
        # Search for top K chunks
        vector_results = self.semantic_memory.query_similar(query, n_results=strategy['top_k'])
        
        if not vector_results:
            print("[Hybrid Retrieval] No vector results found.")
            return []

        # Convert ChromaDB format to flat chunk list
        candidate_chunks = []
        for res in vector_results:
            chunk = res.get("metadata", {})
            chunk["distance"] = res.get("distance", 0.5)
            chunk["similarity"] = res.get("similarity", 0.0)
            chunk["content"] = res.get("document_preview", "")
            candidate_chunks.append(chunk)

        # 3. Stage 2: Graph Expansion
        # Collect parent post IDs
        parent_ids = list(set([str(c.get("parent_post_id")) for c in candidate_chunks if c.get("parent_post_id")]))
        
        graph_boosts = []
        if self.knowledge_graph:
            print(f"[Hybrid Retrieval] Expanding via Neo4j for {len(parent_ids)} parent posts...")
            graph_boosts = self.knowledge_graph.expand_context(parent_ids, limit=5)
            
        # 4. Stage 3: Reranking
        self.reranker.w_vector = strategy['vector_weight']
        self.reranker.w_graph = strategy['graph_weight']
        
        # Determine target categories for boosting (from initial vector matches)
        all_cats = []
        for c in candidate_chunks:
            cats = c.get("categories")
            if cats:
                if isinstance(cats, str):
                    try: cats = json.loads(cats)
                    except: cats = [cats]
                all_cats.extend(cats)
        
        target_cats = list(set(all_cats))[:3] # Boost Top 3 categories found
        
        reranked = self.reranker.rerank(
            query=query,
            chunks=candidate_chunks,
            graph_nodes=graph_boosts,
            target_categories=target_cats
        )

        # 5. Final Selection
        final_selection = reranked[:strategy.get("top_n", top_n)]
        
        print(f"[Hybrid Retrieval] Selected {len(final_selection)} chunks after reranking.")
        for i, c in enumerate(final_selection):
            print(f"  {i+1}. [{c.get('rerank_score')}] {c.get('title')} > {c.get('section_heading')}")
            
        return final_selection

    def get_structured_context(self, chunks: List[Dict[str, Any]]) -> str:
        """
        Formats the selected chunks into a clean context block for the LLM.
        """
        if not chunks:
            return "No relevant context found."

        context_blocks = []
        
        # Group by parent post for cleaner reading
        grouped = {}
        for chunk in chunks:
            pid = chunk.get("parent_post_id")
            if pid not in grouped:
                grouped[pid] = {"title": chunk.get("title"), "sections": []}
            grouped[pid]["sections"].append(chunk)

        for pid, data in grouped.items():
            context_blocks.append(f"### SOURCE: {data['title']} (Post ID: {pid})")
            for sec in data["sections"]:
                heading = sec.get("section_heading", "General")
                content = sec.get("content", "")
                context_blocks.append(f"#### SECTION: {heading}")
                context_blocks.append(content)
                context_blocks.append("")
        
        return "\n".join(context_blocks)
