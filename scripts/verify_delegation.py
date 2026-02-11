
import requests
import re

API_URL = "http://localhost:8000"

def verify_delegation():
    print("Verifying Delegation...")

    # 1. Get Secretary (Xiao Fang)
    res = requests.get(f"{API_URL}/agents/")
    agents = res.json()
    secretary = next((a for a in agents if "秘书" in a['role'] or "Secretary" in a['role']), None)
    
    if not secretary:
        print("No Secretary found.")
        return
    print(f"Secretary: {secretary['name']}")
    
    # 2. Get Xiao Zhang (Target)
    xiaozhang = next((a for a in agents if "张" in a['name']), None)
    if not xiaozhang:
        print("Xiao Zhang not found.")
        return
    print(f"Target: {xiaozhang['name']}")

    # 3. Simulate User Request to Secretary
    print("\n[Step 1] Asking Secretary to delegate...")
    prompt = f"叫{xiaozhang['name']}写一个个人简介"
    
    # We can't easily simulate the FRONTEND loop via script, as the frontend logic does the chaining.
    # But we CAN verify that the Secretary outputs the [[DELEGATE]] tag correctly.
    # The chaining logic is in frontend_app.py and relies on parsing this tag.
    
    chat_req = {
        "agent_id": secretary['id'],
        "message": prompt,
        "history": []
    }
    
    res = requests.post(f"{API_URL}/chat/", json=chat_req, stream=True)
    resp_text = ""
    for chunk in res.iter_content(chunk_size=None):
        if chunk: resp_text += chunk.decode('utf-8')
    
    print(f"Secretary Response: {resp_text}")
    
    if "[[DELEGATE:" in resp_text and xiaozhang['name'] in resp_text:
        print("SUCCESS: Secretary generated DELEGATE tag.")
        
        # Manually extract and simulate the chained call (what frontend would do)
        match = re.search(r"\[\[DELEGATE:\s*(.*?)\s*\|\s*(.*?)\]\]", resp_text, re.DOTALL)
        if match:
            target = match.group(1).strip()
            instruction = match.group(2).strip()
            print(f"Detected Delegation -> Target: {target}, Instruction: {instruction}")
            
            # Simulate Part 2: Sending instruction to Xiao Zhang
            print("\n[Step 2] Simulating chained call to Xiao Zhang...")
            delegated_prompt = f"[Instruction from {secretary['name']}]: {instruction}"
            
            req2 = {
                "agent_id": xiaozhang['id'],
                "message": delegated_prompt,
                "history": [], # In real app, history might be passed or fresh
                "force_execution": True
            }
            res2 = requests.post(f"{API_URL}/chat/", json=req2, stream=True)
            text2 = ""
            for chunk in res2.iter_content(chunk_size=None):
                if chunk: text2 += chunk.decode('utf-8')
            
            print(f"Target Response: {text2}")
            if text2:
                print("SUCCESS: Target responded.")
            else:
                print("FAILURE: Target did not respond.")
                
    else:
        print("FAILURE: Secretary did not generate DELEGATE tag.")
        print("Note: If the prompts haven't reloaded, restart server.")

if __name__ == "__main__":
    verify_delegation()
