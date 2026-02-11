import requests
import json
import re

API_URL = "http://localhost:8000"

def verify_multi_delegation():
    print("Verifying Multi-Target Delegation...")
    
    # 1. Get Secretary (Xiao Fang)
    res = requests.get(f"{API_URL}/agents/")
    agents = res.json()
    secretary = next((a for a in agents if "Secretary" in a['role'] or "秘书" in a['role']), None)
    
    if not secretary:
        print("Secretary 'Xiao Fang' not found.")
        return

    print(f"Secretary: {secretary['name']}")
    
    # 2. Ask Secretary to delegate to TWO people
    prompt = "让小张和小美写个人简历。"
    print(f"\n[Step 1] Sending prompt: '{prompt}'")
    
    payload = {
        "agent_id": secretary['id'],
        "message": prompt,
        "history": [],
        "force_execution": False 
    }
    
    full_response = ""
    try:
        with requests.post(f"{API_URL}/chat/", json=payload, stream=True) as response:
            if response.status_code == 200:
                for chunk in response.iter_content(chunk_size=None):
                    if chunk:
                        text = chunk.decode('utf-8')
                        print(text, end="", flush=True)
                        full_response += text
            else:
                print(f"Error: {response.status_code} - {response.text}")
                return
    except Exception as e:
        print(f"Request Exception: {e}")
        return

    print("\n\n[Step 2] Checking for multiple DELEGATE tags...")
    matches = list(re.finditer(r"\[\[DELEGATE:\s*(.*?)\s*\|\s*(.*?)\]\]", full_response, re.DOTALL))
    
    if len(matches) >= 2:
        print(f"SUCCESS: Found {len(matches)} DELEGATE tags.")
        for i, match in enumerate(matches):
            print(f"  Tag {i+1}: Target='{match.group(1).strip()}', Instruction='{match.group(2).strip()}'")
    else:
        print(f"FAILURE: Found only {len(matches)} DELEGATE tags. Expected at least 2.")
        print("Note: The LLM might need a few tries to adapt to the new prompt.")

if __name__ == "__main__":
    verify_multi_delegation()
