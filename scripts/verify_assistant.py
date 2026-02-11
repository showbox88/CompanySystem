
import requests
import time
import os
import json

API_URL = "http://localhost:8000"
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOG_FILE = os.path.join(BASE_DIR, "Company Doc", "System", "Company_Log.md")

def verify_assistant():
    print("Verifying Assistant Capabilities...")

    # 1. Create Assistant Agent
    print("\n[1] Creating Assistant Agent...")
    agent_data = {
        "name": "Sarah_Assistant",
        "role": "General Assistant",
        "job_title": "Executive Assistant", # Contains 'Assistant'
        "department": "Admin",
        "level": "Staff",
        "system_prompt": "You are a helpful assistant."
    }
    
    # Check if exists first
    res = requests.get(f"{API_URL}/agents/")
    agents = res.json()
    sarah = next((a for a in agents if a['name'] == "Sarah_Assistant"), None)
    
    if not sarah:
        res = requests.post(f"{API_URL}/agents/", json=agent_data)
        if res.status_code != 200:
            print(f"Failed to create agent: {res.text}")
            return
        sarah = res.json()
        print("Assistant created.")
    else:
        print("Assistant found.")
        
    print(f"Agent ID: {sarah['id']}")

    # 2. Test Employee Directory Access
    print("\n[2] Testing Directory Access...")
    # Using chat endpoint (streamed)
    chat_payload = {
        "agent_id": sarah['id'],
        "message": "List all employees in the Admin department."
    }
    
    res = requests.post(f"{API_URL}/chat/", json=chat_payload, stream=True)
    response_text = ""
    for chunk in res.iter_content(chunk_size=None):
        if chunk:
            response_text += chunk.decode('utf-8')
            
    print("Response snippet:", response_text[:100] + "...")
    if "Sarah_Assistant" in response_text:
        print("SUCCESS: Assistant can see itself in the directory.")
    else:
        print("WARNING: Assistant might not have seen the directory.")

    # 3. Test Auto-Logging
    print("\n[3] Testing Auto-Logging...")
    # We need to trick the LLM into outputting [[LOG:...]]
    # Since we can't easily force it without a real conversation context, 
    # we will send a message that explicitly asks for it to simulate the behavior.
    
    chat_payload = {
        "agent_id": sarah['id'],
        "message": "We decided to launch the product on Friday. Please confirm and log this decision."
    }
    
    res = requests.post(f"{API_URL}/chat/", json=chat_payload, stream=True)
    full_resp = ""
    for chunk in res.iter_content(chunk_size=None):
        if chunk:
            full_resp += chunk.decode('utf-8')
    
    print("Response:", full_resp)
    
    # Wait for file write
    time.sleep(2)
    
    # Check Log File
    if os.path.exists(LOG_FILE):
        with open(LOG_FILE, "r", encoding="utf-8") as f:
            content = f.read()
        
        if "launch the product on Friday" in content:
            print("SUCCESS: Auto-log found in Company_Log.md")
        else:
            print("FAILURE: Auto-log NOT found.")
            print("Last 500 chars of log:", content[-500:])
    else:
        print("FAILURE: Log file not found.")

if __name__ == "__main__":
    verify_assistant()
