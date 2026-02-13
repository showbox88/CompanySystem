import sqlite3
import os
import requests
import json
import base64
import time

DB_PATH = r"c:\Users\Showbox\Desktop\AI Agengt Management\CompanySystem\company_ai.db"

def test_image_gen():
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

    # 2. Call API
    print("🚀 Calling Gemini Image API (Imagen 3)...")
    
    # Try the endpoint from builtins.py (Updated to 4.0)
    url = f"https://generativelanguage.googleapis.com/v1beta/models/imagen-3.0-generate-001:predict?key={api_key}"
    # actually let's try the one found in list
    model_id = "imagen-3.0-generate-001" 
    # Wait, list showed: imagen-4.0-generate-001
    model_id = "imagen-3.0-generate-001" # OLD
    
    # NEW
    model_id = "imagen-3.0-generate-001" # Let's try 4.0 if 3.0 failed
    
    # Actually the list showed 4.0 models.
    #  - models/imagen-4.0-generate-preview-06-06
    #  - models/imagen-4.0-ultra-generate-preview-06-06
    #  - models/imagen-3.0-generate-001 (NOT FOUND in my previous grep? Wait, previous grep was filtered)
    
    # RE-READING OUTPUT:
    # "Message: models/imagen-3.0-generate-001 is not found"
    # "Found... models/imagen-4.0-generate-001"
    
    url = f"https://generativelanguage.googleapis.com/v1beta/models/imagen-3.0-generate-001:predict?key={api_key}"
    url = url.replace("imagen-3.0-generate-001", "imagen-4.0-generate-001")
    
    prompt = "A futuristic glass bottle, colorful and artistic, high quality, 4k"
    
    headers = {
        "Content-Type": "application/json"
    }
    
    payload = {
        "instances": [
            {
                "prompt": prompt
            }
        ],
        "parameters": {
            "sampleCount": 1,
            "aspectRatio": "1:1"
        }
    }
    
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=60)
        
        print(f"Status Code: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            if "predictions" in data and len(data["predictions"]) > 0:
                b64_data = data["predictions"][0].get("bytesBase64Encoded")
                if b64_data:
                    # Save
                    filename = f"test_gemini_img_{int(time.time())}.png"
                    with open(filename, "wb") as f:
                        f.write(base64.b64decode(b64_data))
                    print(f"✅ Image saved to: {os.path.abspath(filename)}")
                else:
                    print("❌ No base64 data in prediction.")
            else:
                print(f"❌ No predictions returned. Data: {data}")
        else:
            print(f"❌ API Error: {response.text}")
            
    except Exception as e:
        print(f"❌ Exception: {e}")

if __name__ == "__main__":
    test_image_gen()
