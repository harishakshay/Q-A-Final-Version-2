import requests
import json

def test_search():
    url = "http://localhost:5000/api/search"
    payload = {"query": "How do I choose the right n8n trigger?"}
    
    print(f"Testing query: {payload['query']}")
    try:
        response = requests.post(url, json=payload, timeout=60)
        if response.status_code == 200:
            result = response.json()
            answer = result.get("answer", "")
            
            # Save to file with UTF-8 encoding
            with open("test_result_full.md", "w", encoding="utf-8") as f:
                f.write("# AI Test Answer\n\n")
                f.write(answer)
                f.write("\n\n---\n## Sources\n")
                for s in result.get("sources", []):
                    f.write(f"- {s.get('title')} (Score: {s.get('similarity')})\n")
            
            print("\nSuccess! Answer saved to test_result_full.md")
        else:
            print(f"Error: {response.status_code}")
            print(response.text)
    except Exception as e:
        print(f"Failed: {e}")

if __name__ == "__main__":
    test_search()
