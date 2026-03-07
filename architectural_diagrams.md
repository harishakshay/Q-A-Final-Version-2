# Architectural Diagrams

This document visualizes the core architecture and data flows of the **AI Memory & Reasoning Agent**.

## 1. High-Level System Architecture
The system follows a modular, layered approach to separate concerns between data ingestion, storage, retrieval, and reasoning.

```mermaid
graph TD
    subgraph "Client Layer"
        UI[Web Dashboard / JavaScript]
        API[Flask REST API]
    end

    subgraph "Orchestration Layer"
        PL[Memory Pipeline]
        HR[Hybrid Retrieval Engine]
        RE[Reasoning Engine]
    end

    subgraph "Processing Layer"
        DC[Document Chunker]
        CV[Doc Converter]
        PT[Performance Tracker]
    end

    subgraph "Storage Layer"
        CH[ChromaDB - Vector]
        NJ[Neo4j - Graph]
        FS[Local Filesystem]
    end

    UI <--> API
    API <--> PL
    API <--> HR
    
    PL --> CV --> DC --> CH
    DC --> FS
    PL --> NJ
    PL --> PT
    
    HR --> CH
    HR --> NJ
    RE --> HR
    RE --> API
```

## 2. Data Ingestion Pipeline
How documents move from raw files to structured, searchable knowledge.

```mermaid
sequenceDiagram
    participant U as User/WP
    participant P as Pipeline
    participant C as Converter/Chunker
    participant V as ChromaDB (Vector)
    participant G as Neo4j (Graph)

    U->>P: Upload Document / Fetch Post
    P->>C: Process File (Convert & Chunk)
    C->>P: Section-Aware Chunks
    P->>V: Store Embeddings (Semantic)
    P->>G: Sync Nodes & Relationships (Structural)
    G->>G: Build Chronological Chains
    P->>U: Final Status: Processed
```

## 3. Hybrid RAG Retrieval Flow
The multi-stage process used to generate high-precision answers.

```mermaid
flowchart LR
    Q[User Query] --> QC[Query Classifier]
    
    subgraph "Hybrid Retrieval"
        QC --> VS[Vector Search - ChromaDB]
        QC --> GE[Graph Expansion - Neo4j]
        VS --> RR[Multi-Factor Reranker]
        GE --> RR
    end
    
    RR --> RE[Reasoning Engine - LLM]
    RE --> A[Synthesized Answer]
    RE --> C[Deep Citations]
```
