import requests

url = "http://localhost:5000/api/ask"
payload = {"question": "What is the meaning of life?"}
headers = {"Content-Type": "application/json"}

try:
    response = requests.post(url, json=payload, headers=headers)
    print("Status:", response.status_code)
    print("Response JSON:")
    print(response.json())
except Exception as e:
    print(f"Error: {e}")
