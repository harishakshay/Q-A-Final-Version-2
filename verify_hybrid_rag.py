import requests
import json

def test_hybrid_search(query):
    print(f"\n--- Testing Query: '{query}' ---")
    url = "http://localhost:5000/api/search"
    try:
        response = requests.post(url, json={"query": query})
        if response.status_code == 200:
            data = response.json()
            print("Answer:")
            print(data.get("answer"))
            print(f"\nContext Count: {data.get('context_count')}")
            print("Top Sources:")
            for s in data.get("sources", []):
                print(f"- {s.get('title')} (Sim: {s.get('similarity')})")
        else:
            print(f"Error: {response.status_code} - {response.text}")
    except Exception as e:
        print(f"Connection failed: {e}")

if __name__ == "__main__":
    # Test 1: Quantitative
    test_hybrid_search("How many posts have I done in total?")
    
    # Test 2: Content + Relationship
    test_hybrid_search("What are some related n8n trigger types for architectural workflows?")
    
    # Test 3: Time-based
    test_hybrid_search("Which posts were published in 2026?")
