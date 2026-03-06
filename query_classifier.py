"""
============================================================
query_classifier.py — Lightweight Intent Detection
============================================================
Categorizes user queries into predefined intent types to 
influence retrieval and reranking strategies.
============================================================
"""

import re
from typing import Dict, Any

class QueryClassifier:
    """
    Classifies queries into types: COMPARISON, TROUBLESHOOT, DECISION, ARCHITECTURE, GENERAL.
    """

    INTENT_PATTERNS = {
        "COMPARISON": [
            r"difference", r"versus", r"vs", r"compare", r"pros and cons", 
            r"better than", r"alternative", r"which one is better"
        ],
        "TROUBLESHOOT": [
            r"fail", r"error", r"fix", r"issue", r"problem", r"symptom", 
            r"wrong", r"solve", r"troubleshoot", r"not working", r"debugging"
        ],
        "DECISION": [
            r"choose", r"select", r"pick", r"decision", r"selection", 
            r"when to use", r"which trigger", r"best approach"
        ],
        "ARCHITECTURE": [
            r"architect", r"design", r"structure", r"how it works", 
            r"overview", r"components", r"layer", r"high-level"
        ]
    }

    @staticmethod
    def classify(query: str) -> str:
        """
        Classifies the query text.
        
        Returns:
            String representing the intent (all caps).
        """
        query_lower = query.lower().strip()
        
        # Check patterns
        for intent, patterns in QueryClassifier.INTENT_PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, query_lower):
                    return intent
        
        # Default
        return "GENERAL"

    @staticmethod
    def get_retrieval_strategy(intent: str) -> Dict[str, Any]:
        """
        Returns retrieval hints based on intent.
        """
        strategies = {
            "COMPARISON": {
                "vector_weight": 0.5,
                "graph_weight": 0.3,
                "diverse_posts": True,  # Preference for chunks from different parent posts
                "top_k": 12
            },
            "TROUBLESHOOT": {
                "vector_weight": 0.7,
                "graph_weight": 0.1,
                "boost_section": "Troubleshooting",
                "top_k": 8
            },
            "DECISION": {
                "vector_weight": 0.6,
                "graph_weight": 0.2,
                "boost_section": "Decision Table",
                "top_k": 10
            },
            "ARCHITECTURE": {
                "vector_weight": 0.4,
                "graph_weight": 0.4,
                "expand_neighbors": True, # Expand more in graph
                "top_k": 15
            },
            "GENERAL": {
                "vector_weight": 0.6,
                "graph_weight": 0.2,
                "top_k": 8
            }
        }
        return strategies.get(intent, strategies["GENERAL"])
