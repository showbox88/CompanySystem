
import sys
import os
import requests

# Add parent directory to path to import app
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

API_URL = "http://localhost:8000"

def test_chat():
    print("Testing Chat Endpoint (Streaming)...")
    
    # 1. Get an Agent
    try:
        res = requests.get(f"{API_URL}/agents/")
        agents = res.json()
        if not agents:
            print("FAILURE: No agents found to test chat.")
            return
        
        agent = agents[0]
        print(f"Using agent: {agent['name']} ({agent['id']})")
        
        # 2. Send Chat Message
        payload = {
            "agent_id": agent['id'],
            "message": "Hello, write a short poem about coding."
        }
        
        # Check if API Key is set
        settings_res = requests.get(f"{API_URL}/settings/api_key")
        if settings_res.status_code == 200:
             api_key = settings_res.json().get("value")
             if not api_key:
                 print("WARNING: API Key not set. Chat might fail if using real LLM.")
        
        print("Sending request...")
        # Enable streaming
        res = requests.post(f"{API_URL}/chat/", json=payload, stream=True)
        
        if res.status_code == 200:
            print("Stream started: [", end="", flush=True)
            full_response = ""
            for chunk in res.iter_content(chunk_size=None):
                if chunk:
                    text = chunk.decode('utf-8')
                    print(text, end="", flush=True)
                    full_response += text
            print("]\nSUCCESS: Stream finished.")
        else:
            print(f"FAILURE: Chat request failed with code {res.status_code}")
            print(f"Error: {res.text}")

    except Exception as e:
        print(f"FAILURE: Exception {e}")

if __name__ == "__main__":
    test_chat()
