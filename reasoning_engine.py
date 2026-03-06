"""
============================================================
reasoning_engine.py — AI Reasoning & Insights Engine
============================================================
Uses Groq (via LangChain) for fast LLM inference to:
- Detect decaying content that needs updates
- Generate specific improvement suggestions
- Identify weak topic clusters
- Suggest cross-linking opportunities
- Combine ChromaDB semantic queries with Neo4j graph queries
============================================================
"""

import json
from typing import List, Dict, Any, Optional
from datetime import datetime

from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

import config


from hybrid_retrieval import HybridRetrievalEngine

class ReasoningEngine:
    """
    AI-powered reasoning engine that analyzes content health,
    detects decay, suggests improvements, and identifies
    cross-linking opportunities.

    Integrates:
    - ChromaDB semantic queries (via SemanticMemory)
    - Neo4j graph queries (via KnowledgeGraph)
    - Groq LLM for natural language reasoning
    """

    def __init__(self, semantic_memory=None, knowledge_graph=None):
        """
        Initialize the reasoning engine.

        Args:
            semantic_memory: SemanticMemory instance for vector queries.
            knowledge_graph: KnowledgeGraph instance for graph queries.
        """
        self.semantic_memory = semantic_memory
        self.knowledge_graph = knowledge_graph
        self.hybrid_engine = HybridRetrievalEngine(semantic_memory, knowledge_graph)

        # ---- Initialize Groq LLM via LangChain ----
        self.llm = None
        try:
            self.llm = ChatGroq(
                api_key=config.GROQ_API_KEY,
                model_name=config.GROQ_MODEL,
                temperature=0.3,       # Low temperature for analytical tasks
                max_tokens=2048,
            )
            print("[Reasoning Engine] Groq LLM initialized successfully")
        except Exception as e:
            print(f"[Reasoning Engine] Groq initialization error: {e}")
            print("[Reasoning Engine] LLM-based suggestions will be unavailable")

        # Output parser for clean string responses
        self.output_parser = StrOutputParser()

    def _extract_json(self, response_raw: str) -> Optional[Dict[str, Any]]:
        """
        Robustly extract and parse JSON from an LLM response.
        If full JSON parsing fails, it attempts to extract keys via regex.
        """
        if not response_raw:
            return None
            
        import re
        
        # 1. Standard approach: Code block stripping
        cleaned = response_raw.strip()
        cleaned = re.sub(r'^```(?:json)?\s*', '', cleaned)
        cleaned = re.sub(r'\s*```$', '', cleaned)
        cleaned = cleaned.strip()
        
        try:
            return json.loads(cleaned)
        except:
            pass
            
        # 2. Extract balanced braces if surrounded by text
        try:
            match = re.search(r'(\{.*\})', response_raw, re.DOTALL)
            if match:
                return json.loads(match.group(1))
        except:
            pass
            
        # 3. AGGRESSIVE FALLBACK: Extract values for known keys directly
        # This handles cases where JSON is malformed (e.g. unescaped newlines/quotes)
        data = {}
        
        # Extract "direct" value
        direct_match = re.search(r'"direct":\s*"(.*?)"(?=,\s*"|\s*\})', response_raw, re.DOTALL)
        if direct_match:
            data["direct"] = direct_match.group(1).replace('\\n', '\n').replace('\\"', '"')
            
        # Extract "structured" value
        structured_match = re.search(r'"structured":\s*"(.*?)"(?=\s*\})', response_raw, re.DOTALL)
        if structured_match:
            data["structured"] = structured_match.group(1).replace('\\n', '\n').replace('\\"', '"')
            
        if "direct" in data:
            return data
            
        return None

    def score_to_confidence(self, distance: float, answer: str = "") -> str:
        """
        Maps ChromaDB cosine distance to confidence levels.
        Special rule: Only returns 'low' if the answer indicates no information found.
        """
        not_found_phrase = "I could not find this in the provided documents. Can you share the relevant document?"
        
        if answer and not_found_phrase in answer:
            return "low"
            
        if distance < 0.6:
            return "high"
        else:
            return "medium" # Default to medium if not high and not 'not found'

    def format_citations(self, chunks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Formats retrieved chunks into structured citations as required by Step 7.
        """
        citations = []
        for chunk in chunks:
            # hybrid_retrieval flattens metadata into the chunk dict
            doc_name = chunk.get("parent_post_id", "Unknown")
            article_title = chunk.get("title", "Untitled")
            section = chunk.get("section_heading", "General")
            
            # Distance and confidence
            dist = chunk.get("distance", 0.5)
            conf = self.score_to_confidence(dist)
            
            # Snippet logic: first 40 words of paragraph (strip Title | Heading prefix)
            full_content = chunk.get("content", "")
            paragraph_text = full_content.split("\n\n", 1)[-1] if "\n\n" in full_content else full_content
            snippet_words = paragraph_text.split()[:40]
            snippet = " ".join(snippet_words) + ("..." if len(paragraph_text.split()) > 40 else "")
            
            # Similarity percentage: (1 - distance) * 100
            similarity = max(0, min(100, round((1.0 - dist) * 100, 1)))
            
            citations.append({
                "document": doc_name,
                "article_title": article_title,
                "section": section,
                "snippet": snippet,
                "score": similarity,
                "confidence": conf
            })
        return citations

    # ============================================================
    # Decay Detection
    # ============================================================

    def detect_decaying_content(self, posts: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Identify posts that are decaying based on health score
        and decay flag criteria.

        Criteria:
        - health_score < DECAY_HEALTH_THRESHOLD (default: 0.7)
        - decay_flag == True

        Also queries Neo4j for graph-based decay signals if available.

        Args:
            posts: List of enriched memory objects.

        Returns:
            List of decaying post dicts with analysis details.
        """
        print("[Reasoning Engine] Detecting decaying content...")

        decaying_posts = []

        # ---- Method 1: Direct metric analysis ----
        for post in posts:
            health_score = post.get("health_score", 1.0)
            decay_flag = post.get("decay_flag", False)

            if health_score is not None and health_score < config.DECAY_HEALTH_THRESHOLD and decay_flag:
                # Determine severity
                if health_score < 0.3:
                    severity = "critical"
                elif health_score < 0.5:
                    severity = "high"
                else:
                    severity = "moderate"

                # Identify specific issues
                issues = self._identify_issues(post)

                decaying_posts.append({
                    "slug": post.get("slug", ""),
                    "title": post.get("title", ""),
                    "health_score": health_score,
                    "severity": severity,
                    "issues": issues,
                    "publish_date": post.get("publish_date", ""),
                    "url": post.get("url", ""),
                    "metrics": post.get("metrics", {}),
                })

        # ---- Method 2: Neo4j graph-based detection ----
        if self.knowledge_graph and self.knowledge_graph.driver:
            graph_decaying = self.knowledge_graph.get_decaying_articles()
            # Merge any graph-detected posts not already found
            existing_slugs = {p["slug"] for p in decaying_posts}
            for gd in graph_decaying:
                if gd.get("slug") not in existing_slugs:
                    decaying_posts.append({
                        "slug": gd["slug"],
                        "title": gd["title"],
                        "health_score": gd["health_score"],
                        "severity": "moderate",
                        "issues": ["Detected via graph analysis"],
                        "source": "neo4j",
                    })

        # Sort by severity (worst first)
        severity_order = {"critical": 0, "high": 1, "moderate": 2}
        decaying_posts.sort(key=lambda x: severity_order.get(x.get("severity", "moderate"), 3))

        print(f"[Reasoning Engine] Found {len(decaying_posts)} decaying posts")
        return decaying_posts

    def _identify_issues(self, post: Dict[str, Any]) -> List[str]:
        """
        Analyze a post's metrics to identify specific issues.

        Args:
            post: Memory object with metrics.

        Returns:
            List of human-readable issue descriptions.
        """
        issues = []
        metrics = post.get("metrics", {})
        gsc = metrics.get("gsc", {})
        ga4 = metrics.get("ga4", {})

        # Check CTR
        ctr = gsc.get("ctr", 0)
        if ctr < 0.02:
            issues.append(f"Very low CTR ({ctr:.1%}) — title/meta description may need optimization")
        elif ctr < 0.05:
            issues.append(f"Below-average CTR ({ctr:.1%}) — consider improving SERP snippet")

        # Check position
        position = gsc.get("position", 100)
        if position > 20:
            issues.append(f"Low search position ({position:.0f}) — content may need SEO improvements")

        # Check bounce rate
        bounce = ga4.get("bounce_rate", 1.0)
        if bounce > 0.8:
            issues.append(f"High bounce rate ({bounce:.0%}) — content may not match search intent")
        elif bounce > 0.6:
            issues.append(f"Elevated bounce rate ({bounce:.0%}) — consider improving content engagement")

        # Check engagement time
        engagement = ga4.get("engagement_time", 0)
        if engagement < 30:
            issues.append(f"Very low engagement ({engagement:.0f}s) — content may be too thin")
        elif engagement < 60:
            issues.append(f"Low engagement ({engagement:.0f}s) — consider adding depth or media")

        # Check content length
        content_length = post.get("content_length", 0)
        if content_length < 500:
            issues.append(f"Short content ({content_length} chars) — consider expanding")

        # Check impressions
        impressions = gsc.get("impressions", 0)
        if impressions < 100:
            issues.append(f"Low impressions ({impressions}) — may need better keyword targeting")

        return issues if issues else ["General performance decline detected"]

    # ============================================================
    # Interactive Search / RAG
    # ============================================================

    def answer_query(self, query: str, system_stats: Dict[str, Any] = None) -> str:
        """
        Use the Hybrid Retrieval Engine to get context and Groq LLM to 
        generate a high-quality section-level answer.

        Args:
            query: The user's search/question string.
            system_stats: Global metadata.

        Returns:
            Natural language response from the AI.
        """
        if not self.llm:
            return {
                "answer": "AI Reasoning Engine is currently offline (LLM initialization failed).",
                "sources": [],
                "confidence": "low"
            }

        # ---- 1. Hybrid Retrieval Stage ----
        chunks = self.hybrid_engine.retrieve(query)
        context_text = self.hybrid_engine.get_structured_context(chunks)

        # ---- 2. System Stats Stage ----
        stats_text = "System Metadata:\n"
        if system_stats:
            stats_text += f"- Total content chunks: {system_stats.get('total_items', 'unknown')}\n"
            stats_text += f"- Average section health: {system_stats.get('avg_health_score', 0):.2f}\n"
        else:
            stats_text += "- Metadata unavailable.\n"

        # ---- 3. LLM Synthesis Stage (Factual Persona with Dual Output) ----
        prompt = ChatPromptTemplate.from_messages([
            ("system", """You are a factual Document AI Assistant.
Your task is to answer the user's question using ONLY the provided CONTEXT BLOCKS.

STRICT PROTOCOL:
1. NO HALLUCINATION: You MUST NOT use outside knowledge. If the answer is not contained in the CONTEXT BLOCKS, you MUST state that the information is not found in the uploaded documents.
2. CITE SOURCES: When providing facts, mention which document they came from if possible.

RESPONSE FORMAT:
You MUST return your response as a STRICT JSON object with EXACTLY two keys:
1. "direct": A single, short, and concise paragraph that is direct and purely factual.
2. "structured": A well-organized, human-friendly version of the answer. Use markdown headers, bullet points, or bold text. 

CRITICAL: 
- The value of "structured" MUST be a single STRING, not an array or object.
- If the information is not found in the documents, both "direct" and "structured" MUST BE EXACTLY: "I could not find this in the provided documents. Can you share the relevant document?"
- DO NOT include any text, code, or explanation outside the JSON object.
- Ensure all inner quotes and newlines are properly escaped for JSON.
- Return ONLY valid JSON."""),
            ("human", """
{stats}

CONTEXT BLOCKS:
{context}

USER QUERY:
{query}

SYNTHESIZE DUAL ANSWERS:
"""),
        ])

        try:
            # We need to ensure the response is parsed as JSON
            chain = prompt | self.llm | self.output_parser
            response_raw = chain.invoke({
                "stats": stats_text,
                "context": context_text,
                "query": query,
            })
            
            # Attempt to parse JSON response with robust extraction
            data = self._extract_json(response_raw)
            if data:
                answer_direct = data.get("direct", response_raw)
                answer_structured = data.get("structured", "")
            else:
                # Fallback if parsing failed
                print(f"[Reasoning Engine] JSON parsing failed for query: {query}")
                answer_direct = response_raw
                answer_structured = response_raw

            return {
                "answer": answer_direct,
                "answer_structured": answer_structured,
                "sources": self.format_citations(chunks),
                "confidence": self.score_to_confidence(
                    min([c.get("distance", 1.0) for c in chunks]) if chunks else 1.0,
                    answer=answer_direct
                )
            }
        except Exception as e:
            print(f"[Reasoning Engine] RAG query error: {e}")
            return {
                "answer": f"Error generating response: {str(e)}",
                "sources": [],
                "confidence": "low"
            }

    def answer_hybrid_query(self, query: str, hybrid_context: List[Dict[str, Any]], system_stats: Dict[str, Any] = None) -> str:
        """
        Synthesize an answer using Hybrid Context (Semantic + Graph).
        
        Args:
            query: User's question.
            hybrid_context: List of context items enriched with graph data.
            system_stats: Global system metadata.
        """
        if not self.llm:
            return {
                "answer": "AI Reasoning Engine is offline.",
                "sources": [],
                "confidence": "low"
            }

        # Format stats
        stats_text = "System Stats:\n"
        if system_stats:
            stats_text += f"- Total items: {system_stats.get('total_items', 'unknown')}\n"
            stats_text += f"- Avg Health: {system_stats.get('avg_health_score', 0):.2f}\n"

        # Format hybrid context
        context_parts = []
        for i, item in enumerate(hybrid_context):
            source_type = item.get("source_type", "semantic")
            title = item.get("title", "Untitled")
            content = item.get("content", "")
            graph_info = item.get("graph_info", "")
            
            part = f"[{i+1}] {title} ({source_type.upper()})\n"
            if content: part += f"CONTENT: {content[:500]}...\n"
            if graph_info: part += f"GRAPH INSIGHT: {graph_info}\n"
            context_parts.append(part)
        
        context_text = "\n---\n".join(context_parts)

        # ---- Hybrid Synthesis Stage (Factual Persona with Dual Output) ----
        prompt = ChatPromptTemplate.from_messages([
            ("system", """You are a factual Document AI Assistant utilizing Hybrid Context (Semantic Text + Graph Relationships).

STRICT PROTOCOL:
1. NO HALLUCINATION: You MUST answer the question using ONLY the provided HYBRID CONTEXT.
2. MISSING INFORMATION: If the provided context does not contain the answer, reply exactly with: "I cannot answer this question based on the provided documents."
3. SYNTHESIZE: Combine the CONTENT (text) and GRAPH INSIGHT (relationships) to form a complete, accurate answer.

RESPONSE FORMAT:
You MUST return your response as a STRICT JSON object with EXACTLY two keys:
1. "direct": A single, short, and concise paragraph that is direct and purely factual.
2. "structured": A well-organized, human-friendly version of the answer. Use markdown headers, bullet points, or bold text.

CRITICAL:
- The value of "structured" MUST be a single STRING, not an array or object.
- DO NOT include any text, code, or explanation outside the JSON object.
- Ensure all inner quotes and newlines are properly escaped for JSON.
- Return ONLY valid JSON."""),
            ("human", """
{stats}

HYBRID CONTEXT (Semantic + Graph):
{context}

USER QUERY:
{query}

SYNTHESIZE DUAL ANSWERS:
"""),
        ])

        try:
            chain = prompt | self.llm | self.output_parser
            response_raw = chain.invoke({
                "stats": stats_text,
                "context": context_text,
                "query": query,
            })
            
            data = self._extract_json(response_raw)
            if data:
                answer_direct = data.get("direct", response_raw)
                answer_structured = data.get("structured", "")
            else:
                print(f"[Reasoning Engine] Hybrid JSON parsing failed for query: {query}")
                answer_direct = response_raw
                answer_structured = response_raw

            return {
                "answer": answer_direct,
                "answer_structured": answer_structured,
                "sources": self.format_citations(hybrid_context),
                "confidence": self.score_to_confidence(
                    min([c.get("distance", 1.0) for c in hybrid_context]) if hybrid_context else 1.0,
                    answer=answer_direct
                )
            }
        except Exception as e:
            print(f"[Reasoning Engine] Hybrid RAG error: {e}")
            return {"answer": f"Error: {str(e)}", "sources": [], "confidence": "low"}


    def suggest_updates(self, post: Dict[str, Any]) -> Dict[str, Any]:
        """
        Use the Groq LLM to generate specific improvement
        suggestions for a decaying post.

        Args:
            post: Memory object with content and metrics.

        Returns:
            Dict with 'suggestions' text and 'action_items' list.
        """
        if not self.llm:
            return {
                "suggestions": "LLM not available. Manual review recommended.",
                "action_items": ["Review content for relevance", "Update title and meta description"],
            }

        # Build a detailed prompt with post context
        prompt = ChatPromptTemplate.from_messages([
            ("system", """You are an expert SEO content strategist. Analyze the following 
WordPress post and its performance metrics, then provide specific, actionable 
suggestions to improve its performance. Be concise and prioritize by impact."""),
            ("human", """
Post Title: {title}
URL: {url}
Published: {publish_date}
Content Length: {content_length} characters
Health Score: {health_score}/1.0

Performance Metrics:
- Impressions: {impressions}
- Clicks: {clicks}
- CTR: {ctr}
- Search Position: {position}
- Bounce Rate: {bounce_rate}
- Engagement Time: {engagement_time}s
- Pageviews: {pageviews}

Known Issues:
{issues}

Content Preview (first 500 chars):
{content_preview}

Provide:
1. A brief diagnosis (2-3 sentences)
2. Top 5 specific action items to improve this post's performance
3. Suggested title improvements (if applicable)
4. Content structure recommendations
"""),
        ])

        try:
            chain = prompt | self.llm | self.output_parser

            # Extract metrics for the prompt
            gsc = post.get("metrics", {}).get("gsc", {})
            ga4 = post.get("metrics", {}).get("ga4", {})
            issues = self._identify_issues(post)

            response = chain.invoke({
                "title": post.get("title", "Unknown"),
                "url": post.get("url", ""),
                "publish_date": post.get("publish_date", "Unknown"),
                "content_length": post.get("content_length", 0),
                "health_score": post.get("health_score", 0),
                "impressions": gsc.get("impressions", 0),
                "clicks": gsc.get("clicks", 0),
                "ctr": f"{gsc.get('ctr', 0):.1%}",
                "position": gsc.get("position", 0),
                "bounce_rate": f"{ga4.get('bounce_rate', 0):.0%}",
                "engagement_time": ga4.get("engagement_time", 0),
                "pageviews": ga4.get("pageviews", 0),
                "issues": "\n".join(f"- {i}" for i in issues),
                "content_preview": post.get("content", "")[:500],
            })

            return {
                "post_slug": post.get("slug", ""),
                "post_title": post.get("title", ""),
                "suggestions": response,
                "generated_at": datetime.utcnow().isoformat(),
            }

        except Exception as e:
            print(f"[Reasoning Engine] LLM suggestion error: {e}")
            return {
                "suggestions": f"Error generating suggestions: {str(e)}",
                "action_items": ["Manual review recommended"],
            }

    # ============================================================
    # Weak Cluster Detection
    # ============================================================

    def detect_weak_clusters(self, clusters: List[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """
        Identify weak topic clusters that need strengthening.

        Combines:
        - Neo4j graph query for cluster health averages
        - Semantic analysis for content gaps

        Args:
            clusters: Optional cluster list from SemanticMemory.

        Returns:
            List of weak cluster analysis dicts.
        """
        print("[Reasoning Engine] Detecting weak clusters...")

        weak_clusters = []

        # ---- Neo4j graph-based cluster analysis ----
        if self.knowledge_graph and self.knowledge_graph.driver:
            graph_weak = self.knowledge_graph.get_weak_clusters()
            for cluster in graph_weak:
                weak_clusters.append({
                    "cluster_id": cluster.get("cluster_id"),
                    "centroid_title": cluster.get("centroid_title", ""),
                    "avg_health": cluster.get("avg_health", 0),
                    "article_count": cluster.get("article_count", 0),
                    "articles": cluster.get("article_titles", []),
                    "recommendation": self._generate_cluster_recommendation(cluster),
                    "source": "neo4j",
                })

        # ---- Semantic cluster analysis (fallback / supplement) ----
        if clusters:
            for cluster in clusters:
                cid = cluster.get("cluster_id")
                # Skip if already found via Neo4j
                if any(wc.get("cluster_id") == cid for wc in weak_clusters):
                    continue

                # Check if cluster is small (potentially underdeveloped topic)
                if cluster.get("size", 0) <= 2:
                    weak_clusters.append({
                        "cluster_id": cid,
                        "centroid_title": cluster.get("centroid_title", ""),
                        "size": cluster.get("size", 0),
                        "recommendation": "Small cluster — consider creating more content on this topic",
                        "source": "semantic",
                    })

        print(f"[Reasoning Engine] Found {len(weak_clusters)} weak clusters")
        return weak_clusters

    def _generate_cluster_recommendation(self, cluster: Dict[str, Any]) -> str:
        """Generate a recommendation for strengthening a weak cluster."""
        avg_health = cluster.get("avg_health", 0)
        count = cluster.get("article_count", 0)

        if avg_health < 0.3:
            return "Critical: Major content overhaul needed. Consider rewriting core articles and adding fresh supporting content."
        elif avg_health < 0.5:
            return "Update existing articles with fresh data, improve internal linking, and add 2-3 new supporting articles."
        elif count <= 2:
            return "Thin cluster: Create 3-5 new articles to build topical authority."
        else:
            return "Moderate: Refresh outdated articles and strengthen internal linking within the cluster."

    # ============================================================
    # Cross-Linking Suggestions
    # ============================================================

    def suggest_cross_links(self, posts: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Suggest cross-linking opportunities between semantically
        related posts that currently lack connections.

        Combines:
        - ChromaDB similarity search
        - Neo4j graph analysis (missing RELATED_TO edges)

        Args:
            posts: List of enriched memory objects.

        Returns:
            List of cross-link suggestion dicts.
        """
        print("[Reasoning Engine] Generating cross-link suggestions...")

        suggestions = []

        if not self.semantic_memory:
            print("[Reasoning Engine] SemanticMemory not available for cross-linking")
            return suggestions

        # Find articles without cross-links (from Neo4j)
        isolated_articles = []
        if self.knowledge_graph and self.knowledge_graph.driver:
            isolated_articles = self.knowledge_graph.get_articles_without_crosslinks()
            isolated_slugs = {a["slug"] for a in isolated_articles}
        else:
            # Fall back to checking all posts
            isolated_slugs = {p["slug"] for p in posts}

        # For each isolated article, find semantically similar posts
        for post in posts:
            slug = post.get("slug", "")
            if slug not in isolated_slugs:
                continue

            post_id = str(post.get("id", ""))
            similar = self.semantic_memory.find_similar_posts(post_id, n_results=3)

            for sim in similar:
                similarity = sim.get("similarity", 0)
                if similarity >= config.SIMILARITY_THRESHOLD:
                    suggestions.append({
                        "source_slug": slug,
                        "source_title": post.get("title", ""),
                        "target_id": sim.get("id", ""),
                        "target_title": sim.get("metadata", {}).get("title", ""),
                        "target_slug": sim.get("metadata", {}).get("slug", ""),
                        "similarity": round(similarity, 3),
                        "recommendation": f"Add internal link from '{post.get('title', '')}' to '{sim.get('metadata', {}).get('title', '')}' (similarity: {similarity:.0%})",
                    })

                    # Create the link in Neo4j if available
                    if self.knowledge_graph and self.knowledge_graph.driver:
                        target_slug = sim.get("metadata", {}).get("slug", "")
                        if target_slug:
                            self.knowledge_graph.link_related_articles(
                                slug, target_slug, similarity
                            )

        # Remove duplicate suggestions
        seen = set()
        unique_suggestions = []
        for s in suggestions:
            key = tuple(sorted([s["source_slug"], s.get("target_slug", "")]))
            if key not in seen:
                seen.add(key)
                unique_suggestions.append(s)

        print(f"[Reasoning Engine] Generated {len(unique_suggestions)} cross-link suggestions")
        return unique_suggestions

    # ============================================================
    # Full Analysis Report
    # ============================================================

    def generate_insights_report(self, posts: List[Dict[str, Any]], clusters: List[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Run all reasoning analyses and compile a comprehensive
        insights report.

        Args:
            posts: List of enriched memory objects.
            clusters: Optional cluster list from SemanticMemory.

        Returns:
            Complete insights report dict.
        """
        print("\n" + "=" * 60)
        print("[Reasoning Engine] Generating Full Insights Report")
        print("=" * 60)

        report = {
            "generated_at": datetime.utcnow().isoformat(),
            "total_posts_analyzed": len(posts),
            "summary": {},
            "decaying_content": [],
            "update_suggestions": [],
            "weak_clusters": [],
            "cross_link_suggestions": [],
        }

        # ---- 1. Detect Decaying Content ----
        decaying = self.detect_decaying_content(posts)
        report["decaying_content"] = decaying

        # ---- 2. Generate Update Suggestions (for top decaying posts) ----
        top_decaying = decaying[:5]  # Limit to top 5 to save API calls
        for dp in top_decaying:
            # Find the full post data
            matching_post = next(
                (p for p in posts if p.get("slug") == dp.get("slug")),
                None,
            )
            if matching_post:
                suggestion = self.suggest_updates(matching_post)
                report["update_suggestions"].append(suggestion)

        # ---- 3. Detect Weak Clusters ----
        weak_clusters = self.detect_weak_clusters(clusters)
        report["weak_clusters"] = weak_clusters

        # ---- 4. Suggest Cross-Links ----
        cross_links = self.suggest_cross_links(posts)
        report["cross_link_suggestions"] = cross_links

        # ---- 5. Summary Statistics ----
        health_scores = [p.get("health_score", 0) for p in posts if p.get("health_score") is not None]
        report["summary"] = {
            "total_posts": len(posts),
            "decaying_count": len(decaying),
            "critical_count": len([d for d in decaying if d.get("severity") == "critical"]),
            "weak_cluster_count": len(weak_clusters),
            "cross_link_opportunities": len(cross_links),
            "avg_health_score": round(sum(health_scores) / max(len(health_scores), 1), 3),
            "healthy_posts": len([h for h in health_scores if h >= config.DECAY_HEALTH_THRESHOLD]),
        }

        # ---- Print Summary ----
        print("\n" + "-" * 40)
        print("INSIGHTS SUMMARY")
        print("-" * 40)
        for key, value in report["summary"].items():
            print(f"  {key}: {value}")
        print("-" * 40)

        return report

    def save_report(self, report: Dict[str, Any], filepath: str = None) -> str:
        """
        Save the insights report to a JSON file.

        Args:
            report: Insights report dict.
            filepath: Output path. Defaults to config.INSIGHTS_PATH.

        Returns:
            Path to the saved file.
        """
        import os

        filepath = filepath or config.INSIGHTS_PATH
        os.makedirs(os.path.dirname(filepath), exist_ok=True)

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, ensure_ascii=False, default=str)

        print(f"[Reasoning Engine] Report saved to {filepath}")
        return filepath


# ============================================================
# Standalone Usage
# ============================================================
if __name__ == "__main__":
    import os

    # Load posts
    memory_path = config.PERFORMANCE_MEMORY_PATH
    if not os.path.exists(memory_path):
        memory_path = config.CONTENT_MEMORY_PATH

    if os.path.exists(memory_path):
        with open(memory_path, "r", encoding="utf-8") as f:
            posts = json.load(f)

        engine = ReasoningEngine()
        report = engine.generate_insights_report(posts)
        engine.save_report(report)
    else:
        print("No memory file found. Run earlier layers first.")
