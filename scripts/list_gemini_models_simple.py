import sqlite3
import requests
import os

def find_real_db():
    base = os.getcwd()
    candidates = []
    for root, dirs, files in os.walk(base):
        if "app.db" in files:
            candidates.append(os.path.join(root, "app.db"))
        if "company_ai.db" in files:
            candidates.append(os.path.join(root, "company_ai.db"))
            
    print(f"Found DB candidates: {candidates}")
    
    for db_path in candidates:
        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='agents';")
            if cursor.fetchone():
                print(f"✅ FOUND REAL DB: {db_path}")
                conn.close()
                return db_path
            conn.close()
        except:
            pass
            
    return None

DB_PATH = find_real_db()
if not DB_PATH:
    print("❌ Could not find any populated app.db")
    exit(1)

def get_key():
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Debug: List tables
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = cursor.fetchall()
        print(f"Tables in DB: {[t[0] for t in tables]}")
        
        cursor.execute("SELECT gemini_api_key FROM settings LIMIT 1")
        row = cursor.fetchone()
        conn.close()
        if row:
            return row[0]
    except Exception as e:
        print(f"DB Error: {e}")
    return None

def list_models(api_key):
    if not api_key:
        print("No API Key found.")
        return

    url = f"https://generativelanguage.googleapis.com/v1beta/models?key={api_key}"
    try:
        print(f"Querying: {url.split('?')[0]}")
        response = requests.get(url)
        if response.status_code == 200:
            data = response.json()
            if "models" in data:
                print("\n✅ Available Models for your Key:")
                for m in data["models"]:
                    name = m["name"].replace("models/", "")
                    print(f"  - {name}")
            else:
                print("No models found.")
        else:
            print(f"Error {response.status_code}: {response.text}")
    except Exception as e:
        print(f"Request Error: {e}")

if __name__ == "__main__":
    key = get_key()
    if key:
        print(f"Key found: {key[:5]}...")
        list_models(key)
    else:
        print("Could not retrieve key from DB.")
