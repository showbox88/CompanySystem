import sqlite3
import os
import requests
import json

DB_PATH = r"c:\Users\Showbox\Desktop\AI Agengt Management\CompanySystem\company_ai.db"

def list_models():
    # 1. Get Key
    if not os.path.exists(DB_PATH):
        print(f"❌ DB not found at {DB_PATH}")
        return

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT value FROM settings WHERE key='gemini_api_key'")
    row = cursor.fetchone()
    conn.close()
    
    if not row:
        print("❌ Gemini API Key not found in DB.")
        return

    api_key = row[0]
    print(f"✅ Found API Key: {api_key[:5]}...")

    # 2. List Models
    url = f"https://generativelanguage.googleapis.com/v1beta/models?key={api_key}"
    
    try:
        response = requests.get(url, timeout=30)
        
        if response.status_code == 200:
            data = response.json()
            if "models" in data:
                print(f"✅ Found {len(data['models'])} models. Filtering for 'image' capabilities:")
                found = False
                for m in data['models']:
                    name = m.get('name')
                    methods = m.get('supportedGenerationMethods', [])
                    
                    if "imagen" in name.lower() or "image" in str(methods).lower():
                        print(f"  - {name} (Methods: {methods})")
                        found = True
                
                if not found:
                    print("❌ No image generation models found.")
            else:
                print(f"❌ No models key in response: {data}")
        else:
            print(f"❌ API Error: {response.status_code} - {response.text}")
            
    except Exception as e:
        print(f"❌ Exception: {e}")

if __name__ == "__main__":
    list_models()
