import requests
import time
import sys

API_URL = "http://localhost:8000"

def main():
    print("🦜 Starting Agent Verification Demo...")

    # 1. Check if System is Running
    try:
        requests.get(f"{API_URL}/health")
    except requests.exceptions.ConnectionError:
        print("❌ Error: The backend is NOT running.")
        print("   Please double-click 'run_system.bat' on your desktop first!")
        return

    # 2. Check Settings
    print("🔍 Checking API Configuration...")
    key_res = requests.get(f"{API_URL}/settings/api_key")
    if key_res.status_code != 200 or not key_res.json().get("value"):
        print("❌ Error: API Key is NOT configured.")
        print("   Please go to the 'Settings' page in the UI and enter your API Key.")
        return
    print("✅ API Key found.")

    # 3. Create a DISTINCT Personality Agent
    print("\n👤 Creating Test Agent: 'Captain Blackbeard'...")
    agent_payload = {
        "name": "Captain Blackbeard",
        "role": "Pirate Captain",
        "system_prompt": "You are a rude, drunk 18th-century pirate captain. You answer everything with potential threats of walking the plank, lots of 'Arrr's, and nautical slang. You NEVER break character.",
        "model_name": "gpt-4-turbo",
        "temperature": 0.9
    }
    
    # Check if exists first to avoid duplicates (optional but good)
    # For now just create new
    agent_res = requests.post(f"{API_URL}/agents/", json=agent_payload)
    if agent_res.status_code != 200:
        print(f"❌ Failed to create agent: {agent_res.text}")
        return
    
    agent = agent_res.json()
    agent_id = agent["id"]
    print(f"✅ Agent Created! ID: {agent_id}")

    # 4. Dispatch a SERIOUS Task
    print("\n📜 Dispatching Task: 'Explain Quantum Mechanics'...")
    task_payload = {
        "title": "Explain Quantum Mechanics",
        "input_prompt": "Please explain only the basics of Quantum Mechanics in a simple way.",
        "agent_id": agent_id
    }
    
    task_res = requests.post(f"{API_URL}/tasks/", json=task_payload)
    if task_res.status_code != 200:
        print(f"❌ Failed to create task: {task_res.text}")
        return
        
    task_id = task_res.json()["id"]
    print(f"✅ Task Launched! ID: {task_id}")
    
    # 5. Poll for Result
    print("\n⏳ Waiting for Agent to return from the seven seas...")
    for i in range(30): # Wait up to 30 seconds
        time.sleep(2)
        res = requests.get(f"{API_URL}/tasks/")
        tasks = res.json()
        # Find our task
        my_task = next((t for t in tasks if t["id"] == task_id), None)
        
        if my_task:
            status = my_task["status"]
            print(f"   Status: {status}...")
            
            if status == "completed":
                print("\n🎉 MISSION ACCOMPLISHED! Here is the output:")
                print("="*60)
                print(my_task["output_text"])
                print("="*60)
                print("\n✅ Verification Successful: If the text above sounds like a Pirate, your System Prompt is working!")
                return
            elif status == "failed":
                print(f"\n❌ Task Failed: {my_task.get('output_text')}")
                return
    
    print("\n❌ Timeout waiting for task completion.")

if __name__ == "__main__":
    main()
