
import sys
import os
import requests
import time

# Add parent directory to path to import app
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

API_URL = "http://localhost:8000"
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def test_file_output():
    print("Testing File Output Organization...")
    
    try:
        # 1. Get an Agent
        res = requests.get(f"{API_URL}/agents/")
        agents = res.json()
        if not agents:
            print("FAILURE: No agents found.")
            return
        
        agent = agents[0]
        print(f"Using agent: {agent['name']}")
        
        # 2. Create a Task
        task_payload = {
            "title": "Test File Organization",
            "agent_id": agent['id'],
            "input_prompt": "Write a very short sentence."
        }
        
        # Check API Key
        settings_res = requests.get(f"{API_URL}/settings/api_key")
        if settings_res.status_code == 200:
             api_key = settings_res.json().get("value")
             if not api_key:
                 print("WARNING: API Key not set. Task might fail.")
                 # Just in case, set a dummy key if not set, to allow execution proceed to error (or mock)
                 # But we need execution to succeed to save file.
        
        print("Creating Task...")
        res = requests.post(f"{API_URL}/tasks/", json=task_payload)
        if res.status_code != 200:
            print(f"FAILURE: Could not create task. {res.text}")
            return
            
        task_id = res.json()['id']
        print(f"Task Created: {task_id}")
        
        # 3. Wait for Task Completion
        print("Waiting for task completion...")
        for _ in range(20): # Wait up to 20 seconds
            time.sleep(1)
            res = requests.get(f"{API_URL}/tasks/")
            tasks = res.json()
            my_task = next((t for t in tasks if t['id'] == task_id), None)
            
            if my_task and my_task['status'] == "completed":
                print("Task Completed.")
                break
            if my_task and my_task['status'] == "failed":
                print(f"Task Failed: {my_task.get('output_text')}")
                return
        
        # 4. Check File Location
        agent_name_clean = "".join([c for c in agent['name'] if c.isalnum() or c in (' ', '-', '_', '(', ')')]).strip()
        expected_folder = os.path.join(BASE_DIR, "Company Doc", agent_name_clean)
        
        print(f"Checking folder: {expected_folder}")
        
        if os.path.exists(expected_folder):
            print("SUCCESS: Agent folder exists.")
            files = os.listdir(expected_folder)
            found = False
            for f in files:
                if "Test_File_Organization" in f and task_id[:8] in f:
                    print(f"SUCCESS: Found file {f}")
                    found = True
                    break
            if not found:
                print("FAILURE: File not found in agent folder.")
                print(f"Files found: {files}")
        else:
            print("FAILURE: Agent folder does not exist.")

    except Exception as e:
        print(f"FAILURE: Exception {e}")

if __name__ == "__main__":
    test_file_output()
