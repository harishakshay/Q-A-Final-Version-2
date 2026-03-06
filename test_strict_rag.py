import sys
sys.path.insert(0, r"c:\Users\haris\Downloads\Rag")

from semantic_memory import SemanticMemory
from knowledge_graph import KnowledgeGraph
from reasoning_engine import ReasoningEngine

def test_rag():
    print("Initializing components...")
    sm = SemanticMemory()
    kg = KnowledgeGraph()
    engine = ReasoningEngine(semantic_memory=sm, knowledge_graph=kg)

    questions = [
        # Answerable strictly from documents
        "What is the Kano Model?",
        # Relies on linking multiple documents based on entities
        "How is ARIMA used in forecasting according to the documents?",
        # Known unanswerable - should trigger the strict "I cannot answer..." response
        "Who won the Superbowl in 2024?",
        # Tricky unanswerable - uses words that exist but asks a question not in text
        "What is the history of the Net Promoter Score before 1990?"
    ]

    for q in questions:
        print("\n" + "="*50)
        print(f"Q: {q}")
        print("="*50)
        
        result = engine.answer_query(q)
        
        print("\nANSWER:")
        print(result["answer"])
        print("\nSOURCES:")
        for s in result.get("sources", []):
            print(f"- {s.get('document')} ({s.get('confidence')})")

if __name__ == "__main__":
    test_rag()
