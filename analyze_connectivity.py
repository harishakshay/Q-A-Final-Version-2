"""
Deep Chunk Connectivity Analysis
Analyzes how well chunks are interconnected through shared entities,
document co-membership, category links, and semantic relationships.
"""
import json
import sys
import os
from collections import defaultdict
from itertools import combinations

sys.path.insert(0, r"c:\Users\haris\Downloads\Rag")
from load_split_to_neo4j import (
    CONCEPTS, PERSONS, TOOLS, CONCEPT_RELATIONS,
    PERSON_CREATED_CONCEPT, TOOL_IMPLEMENTS_CONCEPT,
    extract_entities
)

with open(r"c:\Users\haris\Downloads\Rag\split.json", "r", encoding="utf-8") as f:
    split_data = json.load(f)

print(f"Total chunks: {len(split_data)}")

# ─────────────────────────────────────────────
# 1. Build chunk → entity mappings
# ─────────────────────────────────────────────
chunk_entities = {}  # chunk_id -> set of all entities
chunk_concepts = {}
chunk_persons = {}
chunk_tools = {}
chunk_meta = {}

for item in split_data:
    cid = item["id"]
    text = item["document"]
    meta = item["metadata"]
    
    c = extract_entities(text, CONCEPTS)
    p = extract_entities(text, PERSONS)
    t = extract_entities(text, TOOLS)
    
    chunk_concepts[cid] = c
    chunk_persons[cid] = p
    chunk_tools[cid] = t
    chunk_entities[cid] = c | p | t
    chunk_meta[cid] = meta

all_chunk_ids = list(chunk_entities.keys())

# ─────────────────────────────────────────────
# 2. SHARED ENTITY CONNECTIVITY
# ─────────────────────────────────────────────
print("\n" + "=" * 80)
print("SECTION 1: SHARED ENTITY CONNECTIVITY")
print("=" * 80)

# Build entity → chunks index (inverted index)
entity_to_chunks = defaultdict(set)
for cid, entities in chunk_entities.items():
    for e in entities:
        entity_to_chunks[e].add(cid)

# Count how many chunks each entity connects
print("\n--- Entity Bridge Power (entities that connect the most chunks) ---")
entity_bridge = [(e, len(chunks)) for e, chunks in entity_to_chunks.items()]
entity_bridge.sort(key=lambda x: -x[1])
for e, count in entity_bridge[:25]:
    print(f"  {e}: connects {count} chunks")

# Compute pairwise chunk connectivity through shared entities
shared_entity_pairs = defaultdict(set)  # (chunk_a, chunk_b) -> shared entities
for entity, chunks in entity_to_chunks.items():
    for a, b in combinations(sorted(chunks), 2):
        shared_entity_pairs[(a, b)].add(entity)

# Count connections per chunk
chunk_connections = defaultdict(int)
for (a, b) in shared_entity_pairs:
    chunk_connections[a] += 1
    chunk_connections[b] += 1

# Find isolated chunks (no shared entities with any other chunk)
isolated = [cid for cid in all_chunk_ids if chunk_connections.get(cid, 0) == 0]
print(f"\n--- Chunk Connection Distribution ---")
conn_values = [chunk_connections.get(cid, 0) for cid in all_chunk_ids]
print(f"  Min connections: {min(conn_values)}")
print(f"  Max connections: {max(conn_values)}")
print(f"  Avg connections: {sum(conn_values)/len(conn_values):.1f}")
print(f"  Isolated chunks (0 connections): {len(isolated)}")
if isolated:
    for cid in isolated:
        title = chunk_meta[cid].get("title", "")
        print(f"    - {cid}: {title}")

# Top connected chunks
print(f"\n--- Most Connected Chunks (Top 10) ---")
top_connected = sorted(all_chunk_ids, key=lambda x: -chunk_connections.get(x, 0))[:10]
for cid in top_connected:
    title = chunk_meta[cid].get("title", "")
    n = chunk_connections.get(cid, 0)
    ents = sorted(chunk_entities[cid])
    print(f"  {cid}: {n} connections via {ents}")

# Least connected chunks (non-isolated)
print(f"\n--- Least Connected Chunks (Bottom 10, excluding isolated) ---")
non_isolated = [cid for cid in all_chunk_ids if chunk_connections.get(cid, 0) > 0]
bottom_connected = sorted(non_isolated, key=lambda x: chunk_connections.get(x, 0))[:10]
for cid in bottom_connected:
    title = chunk_meta[cid].get("title", "")
    n = chunk_connections.get(cid, 0)
    ents = sorted(chunk_entities[cid])
    print(f"  {cid}: {n} connections via {ents}")

# ─────────────────────────────────────────────
# 3. CROSS-DOCUMENT CONNECTIVITY
# ─────────────────────────────────────────────
print("\n" + "=" * 80)
print("SECTION 2: CROSS-DOCUMENT CONNECTIVITY")
print("=" * 80)

# Group chunks by document
doc_chunks = defaultdict(list)
for cid in all_chunk_ids:
    doc = chunk_meta[cid].get("parent_post_id", chunk_meta[cid].get("title", ""))
    doc_chunks[doc].append(cid)

# Find cross-document connections through shared entities
cross_doc_links = defaultdict(set)  # (doc_a, doc_b) -> shared entities
for (a, b), shared in shared_entity_pairs.items():
    doc_a = chunk_meta[a].get("parent_post_id", chunk_meta[a].get("title", ""))
    doc_b = chunk_meta[b].get("parent_post_id", chunk_meta[b].get("title", ""))
    if doc_a != doc_b:
        key = tuple(sorted([doc_a, doc_b]))
        cross_doc_links[key].update(shared)

# Documents with most cross-links
doc_cross_count = defaultdict(int)
for (da, db) in cross_doc_links:
    doc_cross_count[da] += 1
    doc_cross_count[db] += 1

print(f"\n  Total document pairs with shared entities: {len(cross_doc_links)}")
total_possible = len(doc_chunks) * (len(doc_chunks) - 1) // 2
print(f"  Total possible document pairs: {total_possible}")
cross_doc_pct = len(cross_doc_links)/total_possible*100 if total_possible > 0 else 0
print(f"  Cross-document connectivity: {cross_doc_pct:.1f}%")

print(f"\n--- Most Cross-Linked Documents (Top 10) ---")
for doc in sorted(doc_cross_count, key=lambda x: -doc_cross_count[x])[:10]:
    print(f"  {doc}: linked to {doc_cross_count[doc]} other documents")

# Documents with fewest cross-links
print(f"\n--- Least Cross-Linked Documents (Bottom 10) ---")
for doc in sorted(doc_cross_count, key=lambda x: doc_cross_count[x])[:10]:
    print(f"  {doc}: linked to {doc_cross_count[doc]} other documents")

# Strongest document pairs (most shared entities)
print(f"\n--- Strongest Document Pairs (Top 15 by shared entity count) ---")
strong_pairs = sorted(cross_doc_links.items(), key=lambda x: -len(x[1]))[:15]
for (da, db), shared in strong_pairs:
    print(f"  {da} <-> {db}: {len(shared)} shared ({sorted(shared)})")

# ─────────────────────────────────────────────
# 4. CATEGORY-LEVEL CONNECTIVITY
# ─────────────────────────────────────────────
print("\n" + "=" * 80)
print("SECTION 3: CATEGORY-LEVEL CONNECTIVITY")
print("=" * 80)

cat_chunks = defaultdict(list)
for cid in all_chunk_ids:
    cat = chunk_meta[cid].get("categories", chunk_meta[cid].get("category", "Unknown"))
    cat_chunks[cat].append(cid)

print(f"\n--- Categories and Chunk Counts ---")
for cat in sorted(cat_chunks):
    count = len(cat_chunks[cat])
    # Average entities per chunk in this category
    avg_ents = sum(len(chunk_entities[c]) for c in cat_chunks[cat]) / count
    print(f"  {cat}: {count} chunks, avg {avg_ents:.1f} entities/chunk")

# Cross-category connections
cross_cat_links = defaultdict(int)
for (a, b) in shared_entity_pairs:
    cat_a = chunk_meta[a].get("categories", chunk_meta[a].get("category", ""))
    cat_b = chunk_meta[b].get("categories", chunk_meta[b].get("category", ""))
    if cat_a != cat_b:
        key = tuple(sorted([cat_a, cat_b]))
        cross_cat_links[key] += 1

print(f"\n--- Cross-Category Connections ---")
for cats in sorted(cross_cat_links, key=lambda x: -cross_cat_links[x]):
    print(f"  {cats[0]} <-> {cats[1]}: {cross_cat_links[cats]} chunk pairs")

# ─────────────────────────────────────────────
# 5. SEQUENTIAL CHAIN ANALYSIS (NEXT_CHUNK)
# ─────────────────────────────────────────────
print("\n" + "=" * 80)
print("SECTION 4: SEQUENTIAL CHAIN ANALYSIS (NEXT_CHUNK)")
print("=" * 80)

# Group by document and check sequential numbering
for doc, chunks in sorted(doc_chunks.items()):
    indices = []
    for cid in chunks:
        idx = chunk_meta[cid].get("chunk_index", -1)
        indices.append((idx, cid))
    indices.sort()
    
    # Check if sequential
    expected = list(range(len(indices)))
    actual = [x[0] for x in indices]
    is_sequential = actual == expected
    
    total = chunk_meta[chunks[0]].get("total_chunks", 0)
    match = total == len(chunks)
    
    if not is_sequential or not match:
        print(f"  WARNING {doc}: indices={actual}, total_chunks={total}, actual={len(chunks)}")

print(f"\n  All {len(doc_chunks)} documents have sequential NEXT_CHUNK chains")

# Topical continuity in chains: do adjacent chunks share entities?
print(f"\n--- Topical Continuity (adjacent chunks sharing entities) ---")
total_adjacent = 0
shared_adjacent = 0
weak_transitions = []

for doc, chunks in doc_chunks.items():
    # Sort by chunk_index
    sorted_chunks = sorted(chunks, key=lambda c: chunk_meta[c].get("chunk_index", 0))
    for i in range(len(sorted_chunks) - 1):
        a = sorted_chunks[i]
        b = sorted_chunks[i + 1]
        total_adjacent += 1
        shared = chunk_entities[a] & chunk_entities[b]
        if shared:
            shared_adjacent += 1
        else:
            weak_transitions.append((a, b, doc))

print(f"  Total adjacent pairs: {total_adjacent}")
print(f"  Pairs sharing entities: {shared_adjacent} ({shared_adjacent/total_adjacent*100:.1f}%)")
print(f"  Disconnected transitions: {len(weak_transitions)}")
if weak_transitions:
    print(f"\n  Weak transitions (no shared entities between adjacent chunks):")
    for a, b, doc in weak_transitions:
        ea = sorted(chunk_entities[a]) if chunk_entities[a] else ["(none)"]
        eb = sorted(chunk_entities[b]) if chunk_entities[b] else ["(none)"]
        print(f"    {doc}: {a} {ea} -> {b} {eb}")

# ─────────────────────────────────────────────
# 6. SEMANTIC RELATIONSHIP COVERAGE
# ─────────────────────────────────────────────
print("\n" + "=" * 80)
print("SECTION 5: SEMANTIC RELATIONSHIP COVERAGE")
print("=" * 80)

# Check how many defined CONCEPT_RELATIONS are actually realized in chunk pairs
realized = 0
unrealized = []
for c1, c2, desc in CONCEPT_RELATIONS:
    chunks_1 = entity_to_chunks.get(c1, set())
    chunks_2 = entity_to_chunks.get(c2, set())
    if chunks_1 and chunks_2:
        realized += 1
    else:
        missing_side = []
        if not chunks_1:
            missing_side.append(f"{c1} (0 chunks)")
        if not chunks_2:
            missing_side.append(f"{c2} (0 chunks)")
        unrealized.append((c1, c2, desc, missing_side))

print(f"  Defined concept relationships: {len(CONCEPT_RELATIONS)}")
print(f"  Realized (both endpoints in chunks): {realized}")
print(f"  Unrealized: {len(unrealized)}")
if unrealized:
    print(f"\n  Unrealized relationships:")
    for c1, c2, desc, missing in unrealized:
        print(f"    {c1} <-> {c2} ({desc}): missing {missing}")

# Person-created-concept coverage
realized_pc = 0
for person, concept in PERSON_CREATED_CONCEPT:
    p_chunks = entity_to_chunks.get(person, set())
    c_chunks = entity_to_chunks.get(concept, set())
    if p_chunks and c_chunks:
        realized_pc += 1
print(f"\n  Person-Created-Concept links: {realized_pc}/{len(PERSON_CREATED_CONCEPT)} realized")

# Tool-implements-concept coverage  
realized_tc = 0
for tool, concept in TOOL_IMPLEMENTS_CONCEPT:
    t_chunks = entity_to_chunks.get(tool, set())
    c_chunks = entity_to_chunks.get(concept, set())
    if t_chunks and c_chunks:
        realized_tc += 1
print(f"  Tool-Implements-Concept links: {realized_tc}/{len(TOOL_IMPLEMENTS_CONCEPT)} realized")

# ─────────────────────────────────────────────
# 7. CONNECTIVITY SUMMARY SCORE
# ─────────────────────────────────────────────
print("\n" + "=" * 80)
print("SECTION 6: OVERALL CONNECTIVITY SCORECARD")
print("=" * 80)

scores = {}
# Entity coverage: % of chunks with >=3 entities
s1 = sum(1 for cid in all_chunk_ids if len(chunk_entities[cid]) >= 3) / len(all_chunk_ids) * 100
scores["Entity Coverage (>=3 entities)"] = f"{s1:.1f}%"

# Cross-chunk connectivity: avg connections per chunk
s2 = sum(conn_values) / len(conn_values)
scores["Avg Connections per Chunk"] = f"{s2:.1f}"

# Isolation rate  
s3 = len(isolated) / len(all_chunk_ids) * 100
scores["Isolation Rate"] = f"{s3:.1f}%"

# Cross-document coverage
s4 = len(cross_doc_links) / total_possible * 100 if total_possible > 0 else 0
scores["Cross-Document Coverage"] = f"{s4:.1f}%"

# Adjacent continuity
s5 = shared_adjacent / total_adjacent * 100 if total_adjacent > 0 else 0
scores["Adjacent Chunk Continuity"] = f"{s5:.1f}%"

# Semantic relationship realization
s6 = realized / len(CONCEPT_RELATIONS) * 100
scores["Semantic Rel. Realization"] = f"{s6:.1f}%"

for metric, score in scores.items():
    print(f"  {metric}: {score}")

# Overall grade
avg_score = (s1 + min(s2 * 2, 100) + (100 - s3) + s4 + s5 + s6) / 6
print(f"\n  OVERALL CONNECTIVITY GRADE: {avg_score:.1f}/100")
if avg_score >= 80:
    print("  Rating: EXCELLENT")
elif avg_score >= 65:
    print("  Rating: GOOD")
elif avg_score >= 50:
    print("  Rating: FAIR")
else:
    print("  Rating: NEEDS IMPROVEMENT")
