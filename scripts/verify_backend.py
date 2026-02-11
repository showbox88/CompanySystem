
import sys
import os
import requests
import time
import subprocess

# Add parent directory to path to import app
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


from fastapi.testclient import TestClient
from backend.app.main import app

client = TestClient(app)

def test_create_agent():
    print("Testing Create Agent with new fields...")
    payload = {
        "name": "Test Manager",
        "role": "Test Role",
        "job_title": "Sales Manager",
        "department": "Sales",
        "level": "Manager",
        "system_prompt": "You are a test agent.",
        "model_name": "gpt-4-turbo",
        "temperature": 0.7
    }
    try:
        response = client.post("/agents/", json=payload)
        if response.status_code == 200:
            data = response.json()
            if (data.get('job_title') == "Sales Manager" and 
                data.get('department') == "Sales" and 
                data.get('level') == "Manager"):
                print("SUCCESS: Agent created with new fields.")
                return data['id']
            else:
                print(f"FAILURE: Fields mismatch. Got: {data}")
        else:
            print(f"FAILURE: Status code {response.status_code}. Text: {response.text}")
    except Exception as e:
        print(f"FAILURE: Exception {e}")
    return None

def test_get_agent(agent_id):
    print(f"Testing Get Agent {agent_id}...")
    try:
        response = client.get(f"/agents/{agent_id}")
        if response.status_code == 200:
            data = response.json()
            print(f"Retrieved Agent: {data['name']}, Level: {data.get('level')}")
            if data.get('level') == "Manager":
                 print("SUCCESS: Agent retrieval confirmed new fields.")
            else:
                 print("FAILURE: Level mismatch.")
        else:
            print(f"FAILURE: Status code {response.status_code}")
    except Exception as e:
        print(f"FAILURE: Exception {e}")

def main():
    agent_id = test_create_agent()
    if agent_id:
        test_get_agent(agent_id)

if __name__ == "__main__":
    main()
