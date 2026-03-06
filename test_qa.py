import requests
import json
import sys

# Force UTF-8 encoding for standard output
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

url = "http://localhost:5000/api/ask"
payload = {"question": "How does product management relate to the CEO?"}
headers = {"Content-Type": "application/json"}

try:
    response = requests.post(url, json=payload, headers=headers)
    print(f"Status: {response.status_code}")
    
    data = response.json()
    print("\n--- ANSWER ---")
    print(data.get("answer", "No answer provided"))
    
    print(f"\n--- CONFIDENCE ---")
    print(data.get("confidence", "No confidence provided"))
    
    print("\n--- SOURCES ---")
    sources = data.get("sources", [])
    for i, s in enumerate(sources):
        print(f"\nSource {i+1}:")
        print(f" Document: {s.get('document')}")
        print(f" Label:    {s.get('label')}")
        print(f" Score:    {s.get('score')}")
        print(f" Snippet:  {s.get('snippet')}...")
        
except Exception as e:
    print(f"Error: {e}")
