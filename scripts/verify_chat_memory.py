
import requests
import time
import os
import json

API_URL = "http://localhost:8000"

def verify_chat_memory():
    print("Verifying Chat Memory...")

    # 1. Get Assistant
    res = requests.get(f"{API_URL}/agents/")
    agents = res.json()
    sarah = next((a for a in agents if a['name'] == "Sarah_Assistant"), agents[0] if agents else None)
    
    if not sarah:
        print("No agent found.")
        return
    print(f"Using Agent: {sarah['name']}")

    # 2. Turn 1: Establish Context
    print("\n[Turn 1] User: 'My code name is 007.'")
    chat_req_1 = {
        "agent_id": sarah['id'],
        "message": "My code name is 007. Remember it.",
        "history": []
    }
    
    res1 = requests.post(f"{API_URL}/chat/", json=chat_req_1, stream=True)
    resp1_text = ""
    for chunk in res1.iter_content(chunk_size=None):
        if chunk: resp1_text += chunk.decode('utf-8')
    print(f"Agent: {resp1_text}")
    
    # 3. Turn 2: Recall Context
    print("\n[Turn 2] User: 'What is my code name?'")
    # Build history
    history = [
        {"role": "user", "content": "My code name is 007. Remember it."},
        {"role": "assistant", "content": resp1_text}
    ]
    
    chat_req_2 = {
        "agent_id": sarah['id'],
        "message": "What is my code name?",
        "history": history
    }
    
    res2 = requests.post(f"{API_URL}/chat/", json=chat_req_2, stream=True)
    resp2_text = ""
    for chunk in res2.iter_content(chunk_size=None):
        if chunk: resp2_text += chunk.decode('utf-8')
    print(f"Agent: {resp2_text}")
    
    if "007" in resp2_text:
        print("SUCCESS: Memory works!")
    else:
        print("FAILURE: Agent forgot.")

if __name__ == "__main__":
    verify_chat_memory()
