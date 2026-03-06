import json
import os
import sys

# Ensure current directory is in path
sys.path.append(os.getcwd())

from pipeline import MemoryPipeline

def main():
    print("=== STARTING FULL GRAPH RELATIONSHIP BUILD ===")
    
    pipeline = MemoryPipeline()
    
    if not pipeline.semantic_memory:
        print("Error: Semantic Memory not available")
        return
    
    if not pipeline.knowledge_graph or not pipeline.knowledge_graph.driver:
        print("Error: Knowledge Graph not connected")
        return

    # 1. Load data
    posts = pipeline._load_cached_posts()
    if not posts:
        print("Error: No posts found in cache")
        return
    print(f"Loaded {len(posts)} posts.")

    # 2. Taxonomy (Categories/Tags) and Article Nodes
    print("\n[Step 1/5] Ingesting Taxonomy...")
    pipeline.knowledge_graph.ingest_enriched_posts(posts)

    # 3. Chronological Links
    print("\n[Step 2/5] Linking Chronology...")
    pipeline.knowledge_graph.link_chronologically()

    # 4. Clusters
    print("\n[Step 3/5] Detecting and Linking Clusters...")
    clusters = pipeline.semantic_memory.detect_clusters(n_clusters=8)
    pipeline.knowledge_graph.link_clusters(clusters)

    # 5. Semantic Similarity
    print("\n[Step 4/5] Linking Semantic Similarity (this may take a minute)...")
    for i, post in enumerate(posts):
        pid = post.get("id")
        if pid:
            similar = pipeline.semantic_memory.find_similar_posts(str(pid), n_results=3)
            pipeline.knowledge_graph.link_similarity(str(pid), similar)
            if i % 50 == 0:
                print(f"  Processed {i}/{len(posts)} posts...")

    # 6. Final Stats
    print("\n[Step 5/5] Build Complete. Fetching Final Stats...")
    stats = pipeline.knowledge_graph.get_graph_stats()
    print("\nFinal Knowledge Graph State:")
    print(json.dumps(stats, indent=2))

    pipeline.cleanup()
    print("\n=== BUILD SUCCESSFUL ===")

if __name__ == "__main__":
    main()
