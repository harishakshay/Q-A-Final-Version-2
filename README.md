# AI Memory & Reasoning Agent: A High-Precision RAG Solution

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![Framework: Flask](https://img.shields.io/badge/Framework-Flask-lightgrey.svg)](https://flask.palletsprojects.com/)

An enterprise-grade, High-Precision RAG (Retrieval-Augmented Generation) system built for the Document Q&A Hackathon. This system doesn't just search—it *understands* and *verifies*.

## 🌟 The Vision
The "AI Memory & Reasoning Agent" is designed to solve the two biggest problems in LLM deployments: **Hallucinations** and **Lack of Traceability**. By combining Semantic Vector search with Knowledge Graph expansion, we provide answers that are both contextually rich and clinically accurate.

## 🚀 Key Features

### 1. Hybrid Retrieval Engine (Vector + Graph)
Unlike standard RAG bots, our system queries **ChromaDB** (Semantic) and **Neo4j** (Structural) simultaneously. 
- **ChromaDB** finds what *sounds* like the answer.
- **Neo4j** finds what is *structurally related* (e.g., related legal clauses or chronological documentation updates).

### 2. Section-Aware Smart Chunking
Our `DocumentChunker` detects headings and logical breaks. It intelligently merges small fragments and splits oversized sections at sentence boundaries to maintain a 220–450 word "context window," maximizing the LLM's comprehension.

### 3. Multi-Factor Reranker
Every retrieved chunk is re-evaluated using a custom reranking algorithm that considers semantic distance, graph connectivity, and category metadata before reaching the reasoning engine.

### 4. Zero-Hallucination Guardrails
- **Mandatory Fallback**: Hardcoded to return: *"I could not find this in the provided documents. Can you share the relevant document?"* if confidence is low.
- **Dual Output**: Provides both a concise `Direct Answer` and a `Structured Markdown` report.
- **Deep Citations**: Every fact is backed by a precise snippet, document source, similarity score, and confidence level.

## 🛠️ Tech Stack
- **Language**: Python 3.9+
- **Database**: ChromaDB (Vector), Neo4j (Graph)
- **Embeddings**: OpenAI `text-embedding-3-small`
- **Reasoning Engine**: Groq (Llama-3.3-70b-versatile)
- **Orchestration**: Flask (REST API)

## 📂 Project Structure
```bash
├── app.py                  # Multi-threaded Flask API & Orchestrator
├── reasoning_engine.py      # LLM logic & confidence scoring
├── hybrid_retrieval.py      # Vector + Graph search orchestration
├── semantic_memory.py       # ChromaDB & OpenAI embedding manager
├── knowledge_graph.py       # Neo4j relationship manager
├── chunking.py              # Section-aware document parser
├── ingest_dataset.py        # Bulk folder-based ingestion tool
├── config.py                # Centralized environment & threshold management
└── data/                    # Local storage for Vector DB & Manifests
```

## 🚥 Quick Start

### 1. Environment Setup
Create a `.env` file in the root directory:
```env
OPENAI_API_KEY=your_key_here
GROQ_API_KEY=your_key_here
NEO4J_URI=bolt://localhost:7687
NEO4J_USERNAME=neo4j
NEO4J_PASSWORD=your_password
```

### 2. Install Dependencies
```bash
pip install -r requirements.txt
```

### 3. Ingest Documents
Place your PDFs/TXTs in the `DATASET/` folder and run:
```bash
python ingest_dataset.py
```

### 4. Launch the Dashboard
```bash
python app.py
```
Access the UI at `http://localhost:5000`.

## 🏆 Hackathon Compliance
- ✅ **Task 1 Component**: Full Document Q&A Bot.
- ✅ **Citation Protocol**: (Document + Snippet + Score) correctly implemented.
- ✅ **Confidence Levels**: (High | medium | low) accurately mapped based on L2 distance.
- ✅ **Folder Support**: Real-time monitoring of `docs/` and `DATASET/`.

---
*Developed for the Q&A Hackathon - Task 1.*
