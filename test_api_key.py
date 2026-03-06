from openai import OpenAI
from dotenv import load_dotenv
import os

load_dotenv(override=True)

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

print("Testing API with responses.create...")
try:
    response = client.responses.create(
        model="gpt-4o-mini",
        input="Hello"
    )
    print(f"SUCCESS! Response: {response.output_text}")
except Exception as e:
    print(f"responses.create failed: {e}")

print("\nTesting API with embeddings.create...")
try:
    response = client.embeddings.create(
        input="This is a test sentence.",
        model="text-embedding-3-small"
    )
    print(f"SUCCESS! Embedding dims: {len(response.data[0].embedding)}")
except Exception as e:
    print(f"embeddings.create failed: {e}")
