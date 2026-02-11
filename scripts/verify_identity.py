
import sys
import os
import requests

# Add parent directory to path to import app
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

API_URL = "http://localhost:8000"

def test_identity():
    print("Testing Agent Identity Injection...")
    
    try:
        # 1. Get an Agent
        res = requests.get(f"{API_URL}/agents/")
        agents = res.json()
        if not agents:
            print("FAILURE: No agents found.")
            return
        
        agent = agents[0]
        print(f"Target Agent: {agent['name']}, {agent['job_title']}, {agent['level']}")
        
        # 2. Ask "Who are you?"
        payload = {
            "agent_id": agent['id'],
            "message": "Who are you? Please state your name, title, and department."
        }
        
        # Check API Key
        settings_res = requests.get(f"{API_URL}/settings/api_key")
        if settings_res.status_code == 200:
             api_key = settings_res.json().get("value")
             if not api_key:
                 print("WARNING: API Key not set.")

        print("Sending request...")
        # Use simple POST (non-streaming for easy check, or streaming)
        # Check non-streaming first (which backend still supports if stream=False, but we hardcoded stream=True in frontend. 
        # Backend defaults stream=False in definition, so we can use simple post)
        
        # Actually our backend call_llm_service logic handles stream param, but the /chat/ endpoint explicitly calls it with stream=True.
        # Wait, let's check main.py again.
        # It seems /chat/ endpoint creates a StreamingResponse unconditionally now using stream=True.
        # So we must consume stream.
        
        res = requests.post(f"{API_URL}/chat/", json=payload, stream=True)
        
        full_response = ""
        if res.status_code == 200:
            for chunk in res.iter_content(chunk_size=None):
                if chunk:
                    full_response += chunk.decode('utf-8')
            
            print(f"\nResponse: {full_response}\n")
            
            if agent['name'] in full_response:
                print("SUCCESS: Agent mentioned its name.")
            else:
                print("WARNING: Agent name not found in response.")
                
        else:
            print(f"FAILURE: API Error {res.status_code} - {res.text}")

    except Exception as e:
        print(f"FAILURE: Exception {e}")

if __name__ == "__main__":
    test_identity()
