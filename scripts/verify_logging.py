
import sys
import os
import requests
import time
import json

API_URL = "http://localhost:8000"
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOG_FILE = os.path.join(BASE_DIR, "Company Doc", "System", "Company_Log.md")

def verify_logging():
    print("Verifying Company Logging System...")
    
    # 1. Trigger File Creation Log (via Task)
    print("\n[1] triggering File Creation Log...")
    res = requests.get(f"{API_URL}/agents/")
    agents = res.json()
    if not agents:
        print("No agents found.")
        return
    agent = agents[0]
    
    task_payload = {
        "title": "Log Test Task",
        "agent_id": agent['id'],
        "input_prompt": "Write a word."
    }
    
    res = requests.post(f"{API_URL}/tasks/", json=task_payload)
    if res.status_code == 200:
        task_id = res.json()['id']
        print(f"Task started: {task_id}")
        # Wait for completion
        for _ in range(10):
            time.sleep(1)
            t_res = requests.get(f"{API_URL}/tasks/")
            my_task = next((t for t in t_res.json() if t['id'] == task_id), None)
            if my_task and my_task['status'] == "completed":
                print("Task completed.")
                break
    else:
        print("Failed to start task.")
        
    # 2. Trigger Decision Log (via API)
    print("\n[2] Triggering Decision Log...")
    decision_payload = {
        "event_type": "DECISION",
        "content": "We decided to use Python for backend."
    }
    res = requests.post(f"{API_URL}/logs/decision", json=decision_payload)
    if res.status_code == 200:
        print("Decision logged successfully.")
    else:
        print(f"Failed to log decision: {res.text}")
        
    # 3. Verify Log File
    print("\n[3] Checking Company_Log.md...")
    if os.path.exists(LOG_FILE):
        with open(LOG_FILE, "r", encoding="utf-8") as f:
            content = f.read()
            
        print("-" * 20)
        print(content[-500:]) # Show last 500 chars
        print("-" * 20)
        
        if "Log Test Task" in content:
            print("SUCCESS: File creation log found.")
        else:
            print("FAILURE: File creation log NOT found.")
            
        if "We decided to use Python" in content:
            print("SUCCESS: Decision log found.")
        else:
            print("FAILURE: Decision log NOT found.")
    else:
        print(f"FAILURE: Log file {LOG_FILE} does not exist.")

if __name__ == "__main__":
    verify_logging()
