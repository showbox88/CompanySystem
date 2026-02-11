import requests
import json

API_URL = "http://localhost:8000"

def test_force_execution():
    # 1. Get Xiao Zhang
    res = requests.get(f"{API_URL}/agents/")
    agents = res.json()
    xiaozhang = next((a for a in agents if "张" in a['name'] or "Zhang" in a['name']), None)
    
    if not xiaozhang:
        print("Xiao Zhang not found.")
        return

    print(f"Testing Force Execution on: {xiaozhang['name']}")
    
    # 2. Send Request with force_execution=True
    # We use a prompt that implies file generation but usually would ask for confirmation
    prompt = "Generate a file named 'test_force.md' with content: 'Force execution worked.'"
    
    payload = {
        "agent_id": xiaozhang['id'],
        "message": prompt,
        "history": [],
        "force_execution": True
    }
    
    print(f"Sending payload: {payload}")
    
    try:
        with requests.post(f"{API_URL}/chat/", json=payload, stream=True) as response:
            if response.status_code == 200:
                full_content = ""
                # Handle raw streaming or SSE (since we support both now in frontend, backend emits SSE)
                # But wait, backend emits SSE "data: ..." format? 
                # My backend rewrite logic: yield delta. 
                # If backend yields raw delta, we just read raw chunk.
                for chunk in response.iter_content(chunk_size=None):
                    if chunk:
                        text = chunk.decode('utf-8')
                        print(f"Chunk: {text}")
                        full_content += text
                
                print(f"\nFull Response: {full_content}")
                
                if "[[EXECUTE_TASK:" in full_content:
                    print("SUCCESS: EXECUTE_TASK tag found.")
                else:
                    print("FAILURE: EXECUTE_TASK tag NOT found.")
            else:
                print(f"Error: {response.status_code} - {response.text}")
    except Exception as e:
        print(f"Request Exception: {e}")

if __name__ == "__main__":
    test_force_execution()
