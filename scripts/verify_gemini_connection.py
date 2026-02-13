import sqlite3
import requests
import os
import json

# Path to the CONFIRMED active database
DB_PATH = r"c:\Users\Showbox\Desktop\AI Agengt Management\CompanySystem\company_ai.db"

def get_key_from_db():
    if not os.path.exists(DB_PATH):
        print(f"❌ DB File not found at: {DB_PATH}")
        return None
        
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT gemini_api_key FROM settings LIMIT 1")
        row = cursor.fetchone()
        conn.close()
        
        if row and row[0]:
            return row[0]
        else:
            print("❌ No API Key found in 'settings' table.")
            return None
    except Exception as e:
        print(f"❌ DB Read Error: {e}")
        return None

def test_gemini(api_key):
    print(f"\n🔑 Testing API Key: {api_key[:5]}...{api_key[-5:]}")
    
    # 1. List Models
    print("\n--- 1. Checking Available Models ---")
    url = f"https://generativelanguage.googleapis.com/v1beta/models?key={api_key}"
    response = requests.get(url)
    
    available_models = []
    if response.status_code == 200:
        data = response.json()
        print("✅ API Connection Successful!")
        if "models" in data:
            for m in data["models"]:
                name = m["name"].replace("models/", "")
                if "generateContent" in m.get("supportedGenerationMethods", []):
                    available_models.append(name)
            print(f"📋 Found {len(available_models)} generation models.")
            if "gemini-1.5-flash" in available_models:
                print("   ✔ gemini-1.5-flash is AVAILABLE.")
            else:
                print("   ❌ gemini-1.5-flash is NOT in the list.")
        else:
            print("⚠️ No models returned in list.")
    else:
        print(f"❌ List Models Failed: {response.status_code} - {response.text}")
        return

    # 2. Test Text Generation (gemini-1.5-flash)
    print("\n--- 2. Testing Text Generation (gemini-1.5-flash) ---")
    gen_url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={api_key}"
    payload = {
        "contents": [{"parts": [{"text": "Hello, explain AI in 5 words."}]}]
    }
    
    resp = requests.post(gen_url, json=payload)
    if resp.status_code == 200:
        print(f"✅ Text Gen Success: {resp.json()['candidates'][0]['content']['parts'][0]['text']}")
    else:
        print(f"❌ Text Gen Failed: {resp.status_code} - {resp.text}")

    # 3. Test Image Generation (imagen-3.0-generate-001)
    print("\n--- 3. Testing Image Generation (imagen-3.0-generate-001) ---")
    img_url = f"https://generativelanguage.googleapis.com/v1beta/models/imagen-3.0-generate-001:predict?key={api_key}"
    img_payload = {
        "instances": [{"prompt": "A futuristic glass bottle"}],
        "parameters": {"sampleCount": 1}
    }
    
    img_resp = requests.post(img_url, json=img_payload)
    if img_resp.status_code == 200:
        print("✅ Image Gen Success (Base64 data received)")
    else:
        print(f"❌ Image Gen Failed: {img_resp.status_code} - {img_resp.text}")

if __name__ == "__main__":
    key = get_key_from_db()
    if key:
        test_gemini(key)
    else:
        print("Please ensure the API Key is set in the Settings page and saved.")
