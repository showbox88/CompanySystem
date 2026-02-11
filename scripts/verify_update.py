
import sys
import os

# Add parent directory to path to import app
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi.testclient import TestClient
from backend.app.main import app

client = TestClient(app)

def test_update_agent():
    print("Testing Update Agent...")
    # 1. Create Agent
    create_payload = {
        "name": "Update Test Agent",
        "role": "Tester",
        "system_prompt": "You are a tester.",
        "level": "Junior (初级)"
    }
    try:
        res = client.post("/agents/", json=create_payload)
        if res.status_code != 200:
            print(f"Failed to create agent: {res.text}")
            return
        
        agent_id = res.json()["id"]
        print(f"Created agent {agent_id} with level {res.json().get('level')}")

        # 2. Update Agent
        update_payload = {
            "job_title": "Senior Tester",
            "level": "Senior (资深)"
        }
        res = client.put(f"/agents/{agent_id}", json=update_payload)
        if res.status_code == 200:
            data = res.json()
            if data.get("job_title") == "Senior Tester" and data.get("level") == "Senior (资深)":
                print("SUCCESS: Agent updated successfully.")
            else:
                print(f"FAILURE: Update mismatch. Got: {data}")
        else:
            print(f"FAILURE: Update failed with status {res.status_code}: {res.text}")
            
    except Exception as e:
        print(f"FAILURE: Exception {e}")

if __name__ == "__main__":
    test_update_agent()
