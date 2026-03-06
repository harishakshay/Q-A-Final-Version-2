"""
============================================================
knowledge_graph.py — Neo4j Knowledge Graph
============================================================
Builds and manages a knowledge graph in Neo4j Community Edition
with Article, Topic, and Cluster nodes. Edges represent
relationships between content, topics, and thematic clusters.
Supports dynamic addition, metric updates, and graph queries.
============================================================
"""

import json
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime

from neo4j import GraphDatabase

import config


class KnowledgeGraph:
    """
    Manages a content knowledge graph in Neo4j.
    Strictly restricted to 'Article' nodes from pages_metadata.json.
    """

    def __init__(self):
        """Initialize connection to local Neo4j Community Edition."""
        self.driver = None
        try:
            self.driver = GraphDatabase.driver(
                config.NEO4J_URI,
                auth=(config.NEO4J_USERNAME, config.NEO4J_PASSWORD),
            )
            self.driver.verify_connectivity()
            print("[Knowledge Graph] Connected to Neo4j successfully")
        except Exception as e:
            print(f"[Knowledge Graph] Neo4j connection error: {e}")
            self.driver = None
            return

        # Try index creation separately so it doesn't kill the driver if one fails
        try:
            self._create_indexes()
        except Exception as e:
            print(f"[Knowledge Graph] Warning: Index creation failed: {e}")

    def close(self):
        """Close the Neo4j driver connection."""
        if self.driver:
            self.driver.close()

    def _create_indexes(self):
        """Create indexes and constraints."""
        if not self.driver:
            return
        with self.driver.session() as session:
            # Unique constraint on id (Primary Identifier)
            session.run("""
                CREATE CONSTRAINT article_id IF NOT EXISTS
                FOR (a:Article) REQUIRE a.id IS UNIQUE
            """)
            session.run("""
                CREATE CONSTRAINT category_name IF NOT EXISTS
                FOR (c:Category) REQUIRE c.name IS UNIQUE
            """)
            session.run("""
                CREATE CONSTRAINT tag_name IF NOT EXISTS
                FOR (t:Tag) REQUIRE t.name IS UNIQUE
            """)
            session.run("""
                CREATE CONSTRAINT cluster_id IF NOT EXISTS
                FOR (c:Cluster) REQUIRE c.id IS UNIQUE
            """)
            session.run("""
                CREATE CONSTRAINT year_value IF NOT EXISTS
                FOR (y:Year) REQUIRE y.value IS UNIQUE
            """)
        print("[Knowledge Graph] Indexes and constraints created")

    def ingest_pages_metadata(self, pages_data: List[Dict[str, Any]]) -> int:
        """
        Wrapper for ingest_enriched_posts to maintain compatibility 
        with pages_metadata.json source.
        """
        return self.ingest_enriched_posts(pages_data)

    def ingest_enriched_posts(self, posts: List[Dict[str, Any]]) -> int:
        """
        Ingest enriched post data, building Article, Category, and Tag nodes.
        Uses MERGE to prevent duplication.
        """
        if not self.driver or not posts:
            return 0

        print(f"[Knowledge Graph] Ingesting {len(posts)} enriched posts...")
        count = 0
        with self.driver.session() as session:
            for post in posts:
                try:
                    # 1. Merge Article node
                    session.run("""
                        MERGE (a:Article {id: $id})
                        SET a.url = $url,
                            a.title = $title,
                            a.publish_date = $publish_date,
                            a.updated_at = $updated_at
                    """, {
                        "id": post.get("id"),
                        "url": post.get("url"),
                        "title": post.get("title"),
                        "publish_date": post.get("publish_date"),
                        "updated_at": datetime.utcnow().isoformat()
                    })

                    # 2. Merge Categories and Link
                    categories = post.get("categories", [])
                    if isinstance(categories, str): # Fallback if list is stringified
                        try: categories = json.loads(categories)
                        except: categories = [categories]
                    
                    for cat_name in categories:
                        session.run("""
                            MATCH (a:Article {id: $id})
                            MERGE (c:Category {name: $cat_name})
                            MERGE (a)-[:IN_CATEGORY]->(c)
                        """, {"id": post.get("id"), "cat_name": cat_name})

                    # 3. Merge Tags and Link
                    tags = post.get("tags", [])
                    if isinstance(tags, str):
                        try: tags = json.loads(tags)
                        except: tags = [tags]

                    for tag_name in tags:
                        session.run("""
                            MATCH (a:Article {id: $id})
                            MERGE (t:Tag {name: $tag_name})
                            MERGE (a)-[:HAS_TAG]->(t)
                        """, {"id": post.get("id"), "tag_name": tag_name})

                    # 4. Merge Year and Link (Post -> Year)
                    pdate = post.get("publish_date")
                    if pdate:
                        try:
                            year = int(pdate[:4])
                            session.run("""
                                MATCH (a:Article {id: $id})
                                MERGE (y:Year {value: $year})
                                MERGE (a)-[:PUBLISHED_IN]->(y)
                            """, {"id": post.get("id"), "year": year})
                        except:
                            pass

                    # 5. Link Post -> Post (SAME_CATEGORY_AS)
                    for cat_name in categories:
                        session.run("""
                            MATCH (a:Article {id: $id})
                            MATCH (other:Article)-[:IN_CATEGORY]->(c:Category {name: $cat_name})
                            WHERE a <> other
                            MERGE (a)-[:SAME_CATEGORY_AS]-(other)
                        """, {"id": post.get("id"), "cat_name": cat_name})

                    count += 1
                except Exception as e:
                    print(f"Error ingesting enriched post {post.get('id')}: {e}")
        
        print(f"[Knowledge Graph] Successfully synced {count} Article nodes with taxonomy")
        return count

    def link_chronologically(self):
        """Build [:NEXT_POST] relationships between articles based on publish_date."""
        if not self.driver:
            return
        
        print("[Knowledge Graph] Building chronological links...")
        with self.driver.session() as session:
            session.run("""
                MATCH (a:Article)
                WHERE a.publish_date IS NOT NULL
                WITH a ORDER BY a.publish_date ASC
                WITH collect(a) AS articles
                UNWIND range(0, size(articles)-2) AS i
                WITH articles[i] AS current, articles[i+1] AS next
                MERGE (current)-[:NEXT_POST]->(next)
            """)

    def link_clusters(self, clusters: List[Dict[str, Any]]):
        """Link Articles to Cluster nodes based on detected thematic groups."""
        if not self.driver or not clusters:
            return

        print(f"[Knowledge Graph] Linking {len(clusters)} clusters...")
        with self.driver.session() as session:
            for cluster in clusters:
                cluster_id = str(cluster.get("cluster_id"))
                centroid = cluster.get("centroid_title", "")
                
                # Create Cluster node
                session.run("""
                    MERGE (c:Cluster {id: $id})
                    SET c.name = $name,
                        c.updated_at = $updated_at
                """, {
                    "id": cluster_id,
                    "name": f"Theme: {centroid}",
                    "updated_at": datetime.utcnow().isoformat()
                })

                # Link Article members
                post_ids = cluster.get("posts", [])
                for pid in post_ids:
                    session.run("""
                        MATCH (a:Article {id: $pid})
                        MATCH (c:Cluster {id: $cid})
                        MERGE (a)-[:BELONGS_TO]->(c)
                    """, {"pid": str(pid), "cid": cluster_id})

    def link_similarity(self, article_id: str, similar_items: List[Dict[str, Any]]):
        """Link an article to its semantically similar neighbors."""
        if not self.driver or not similar_items:
            return

        with self.driver.session() as session:
            for item in similar_items:
                target_id = str(item.get("id"))
                score = item.get("similarity", 0.0)
                
                if score < 0.7: continue # Threshold for graph links

                session.run("""
                    MATCH (a:Article {id: $aid})
                    MATCH (t:Article {id: $tid})
                    WHERE a <> t
                    MERGE (a)-[r:SIMILAR_TO]-(t)
                    SET r.score = $score
                """, {"aid": str(article_id), "tid": target_id, "score": score})

    def expand_context(self, post_ids: List[str], limit: int = 5) -> List[Dict[str, Any]]:
        """
        Expands the candidate set by finding related articles in Neo4j.
        Returns Article IDs and their connection strength.
        """
        if not self.driver or not post_ids:
            return []
            
        # Ensure post_ids are integers for Neo4j match if stored as int
        # In ingest_enriched_posts we use post.get("id") which is likely int from WP
        ids = [int(pid) if isinstance(pid, str) and pid.isdigit() else pid for pid in post_ids]
        
        query = """
        MATCH (a:Article) WHERE a.id IN $ids
        MATCH (a)-[r:SIMILAR_TO|BELONGS_TO|SAME_CATEGORY_AS]-(neighbor:Article)
        WHERE NOT neighbor.id IN $ids
        RETURN neighbor.id as id, 
               neighbor.title as title,
               avg(CASE 
                   WHEN type(r) = 'SIMILAR_TO' THEN r.score 
                   WHEN type(r) = 'BELONGS_TO' THEN 0.7 
                   WHEN type(r) = 'SAME_CATEGORY_AS' THEN 0.5 
                   ELSE 0.1 
               END) as weight
        ORDER BY weight DESC
        LIMIT $limit
        """
        
        expanded = []
        with self.driver.session() as session:
            result = session.run(query, {"ids": ids, "limit": limit})
            for record in result:
                expanded.append({
                    "id": str(record["id"]),
                    "title": record["title"],
                    "weight": record["weight"]
                })
        return expanded

    def get_graph_stats(self) -> Dict[str, Any]:
        """Get summary statistics dynamically from the graph."""
        if not self.driver:
            return {"status": "disconnected"}
        
        stats = {
            "nodes": {},
            "relationships": {},
            "total_nodes": 0,
            "total_relationships": 0
        }
        
        try:
            with self.driver.session() as session:
                # Get Node counts by label
                node_result = session.run("""
                    MATCH (n)
                    RETURN labels(n)[0] AS type, count(n) AS count
                """)
                for record in node_result:
                    label = record["type"] or "Unknown"
                    stats["nodes"][label] = record["count"]
                    stats["total_nodes"] += record["count"]
                
                # Get Relationship counts by type
                rel_result = session.run("""
                    MATCH ()-[r]->()
                    RETURN type(r) AS type, count(r) AS count
                """)
                for record in rel_result:
                    stats["relationships"][record["type"]] = record["count"]
                    stats["total_relationships"] += record["count"]
                    
            return stats
        except Exception as e:
            print(f"[Knowledge Graph] Error fetching stats: {e}")
            return {"status": "error", "message": str(e)}

    def get_knowledge_analytics(self) -> Dict[str, Any]:
        """
        Comprehensive graph analytics for the dashboard.
        Calculates centrality, clustering, and health metrics.
        """
        if not self.driver:
            return {"status": "error", "message": "Disconnected"}

        analytics = {
            "central_entities": [],
            "graph_statistics": {},
            "knowledge_clusters": [],
            "recent_activity": [],
            "health_metrics": {},
            "top_docs": []
        }

        try:
            with self.driver.session() as session:
                # 1. Influential Nodes (Degree Centrality)
                centrality_res = session.run("""
                    MATCH (e)
                    WHERE NOT e:Article AND NOT e:Year
                    WITH e, head(labels(e)) as type
                    OPTIONAL MATCH (e)-[r]-()
                    RETURN e.name as name, type, count(r) as connections
                    ORDER BY connections DESC
                    LIMIT 5
                """)
                for rec in centrality_res:
                    analytics["central_entities"].append({
                        "name": rec["name"] or "Unknown",
                        "type": rec["type"] or "Concept",
                        "connections": rec["connections"]
                    })

                # 2. Graph Statistics & Health
                stats_res = session.run("""
                    MATCH (n)
                    OPTIONAL MATCH (n)-[r]->()
                    WITH count(DISTINCT n) as total_nodes, count(r) as total_rels
                    RETURN total_nodes, total_rels
                """)
                stats = stats_res.single()
                num_nodes = stats["total_nodes"]
                num_rels = stats["total_rels"]
                
                analytics["graph_statistics"] = {
                    "total_nodes": num_nodes,
                    "total_relationships": num_rels,
                    "avg_relationships": round(float(num_rels)/num_nodes if num_nodes > 0 else 0, 2)
                }

                # 3. Knowledge Cluster (Top Categories)
                cluster_res = session.run("""
                    MATCH (c:Category)
                    OPTIONAL MATCH (c)<-[:IN_CATEGORY]-(a:Article)
                    RETURN c.name as name, count(a) as size
                    ORDER BY size DESC
                    LIMIT 3
                """)
                for rec in cluster_res:
                    analytics["knowledge_clusters"].append({
                        "name": rec["name"],
                        "size": rec["size"],
                        "type": "Category Cluster"
                    })

                # 4. Recent Activity (Latest Nodes with names/titles)
                activity_res = session.run("""
                    MATCH (n)
                    WHERE n.updated_at IS NOT NULL
                    WITH n, head(labels(n)) as lbl, 
                         coalesce(n.name, n.title, "Unnamed Node") as displayName
                    RETURN 'node' as type, lbl as label, displayName as name, n.updated_at as ts
                    ORDER BY n.updated_at DESC
                    LIMIT 5
                """)
                for rec in activity_res:
                    analytics["recent_activity"].append({
                        "type": rec["type"],
                        "label": rec["label"] or "Entity",
                        "name": rec["name"],
                        "timestamp": rec["ts"]
                    })

                # 5. Top Knowledge-Rich Documents
                doc_res = session.run("""
                    MATCH (a:Article)
                    OPTIONAL MATCH (a)-[r]-()
                    RETURN a.title as title, count(r) as knowledge_density
                    ORDER BY knowledge_density DESC
                    LIMIT 5
                """)
                for rec in doc_res:
                    analytics["top_docs"].append({
                        "title": rec["title"],
                        "density": rec["knowledge_density"]
                    })

                # 6. Health: Density estimate (Edges / Nodes^2)
                density = 0
                if num_nodes > 1:
                    density = (2.0 * num_rels) / (num_nodes * (num_nodes - 1))
                
                analytics["health_metrics"] = {
                    "graph_density": round(density, 4),
                    "node_rel_ratio": round(num_rels / num_nodes if num_nodes > 0 else 0, 2)
                }

            return analytics
        except Exception as e:
            print(f"[Knowledge Graph] Analytics error: {e}")
            return {"status": "error", "message": str(e)}

    def delete_by_file_id(self, file_id: str) -> bool:
        """Delete all Document, Chunk, and related nodes for a specific file_id."""
        if not self.driver or not file_id:
            return False

        print(f"[Knowledge Graph] Deleting nodes for file_id: {file_id}")
        try:
            with self.driver.session() as session:
                # Delete chunks associated with the document
                session.run("""
                    MATCH (c:Chunk {document_id: $file_id})
                    DETACH DELETE c
                """, {"file_id": file_id})

                # Delete the document node itself
                session.run("""
                    MATCH (d:Document {id: $file_id})
                    DETACH DELETE d
                """, {"file_id": file_id})
                
                # Delete old Article/Document references if any exist matching the file_id
                session.run("""
                    MATCH (a:Article {id: $file_id})
                    DETACH DELETE a
                """, {"file_id": file_id})

            print(f"[Knowledge Graph] Successfully deleted graph data for file_id: {file_id}")
            return True
        except Exception as e:
            print(f"[Knowledge Graph] Error deleting file {file_id}: {e}")
            return False

    def get_latest_entities(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Get the latest entities in the graph along with their connection counts."""
        if not self.driver:
            return []
            
        try:
            with self.driver.session() as session:
                result = session.run("""
                    MATCH (n)
                    WHERE NOT n:Article AND NOT n:Year AND NOT n:Document AND NOT n:Chunk
                    WITH n, head(labels(n)) AS type
                    OPTIONAL MATCH (n)-[r]-()
                    RETURN coalesce(n.name, n.id, n.title, "Unknown Node") AS name, type, count(r) AS connections
                    ORDER BY connections DESC
                    LIMIT $limit
                """, limit=limit)
                
                records = list(result)
                print(f"[Knowledge Graph] get_latest_entities found {len(records)} records")
                
                return [
                    {
                        "name": rec["name"],
                        "type": rec["type"] or "Unknown",
                        "connections": rec["connections"]
                    }
                    for rec in records
                ]
        except Exception as e:
            print(f"[Knowledge Graph] Error fetching latest entities: {e}")
            return []


if __name__ == "__main__":
    import os
    print("Standalone Test: Initializing KnowledgeGraph...")
    kg = KnowledgeGraph()
    if kg.driver:
        print("Success: Driver connected.")
        # Load from content_memory.json for enriched data
        path = config.CONTENT_MEMORY_PATH
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            print(f"Loaded {len(data)} posts from cache.")
            kg.ingest_enriched_posts(data)
            kg.link_chronologically()
            print(f"Final Stats: {kg.get_graph_stats()}")
            print(f"Analytics: {kg.get_knowledge_analytics()}")
        else:
            print(f"Error: {path} not found")
        kg.close()
    else:
        print("Error: Driver failed to initialize.")
