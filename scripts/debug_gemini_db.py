import sqlite3
import os

DB_PATH = r"c:\Users\Showbox\Desktop\AI Agengt Management\CompanySystem\company_ai.db"

def check_db():
    if not os.path.exists(DB_PATH):
        print(f"❌ DB not found at {DB_PATH}")
        return

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # 1. Check Settings
    print("--- Settings ---")
    try:
        cursor.execute("SELECT key, value FROM settings WHERE key='gemini_api_key'")
        row = cursor.fetchone()
        if row:
            key_val = row[1]
            masked = key_val[:4] + "..." + key_val[-4:] if key_val and len(key_val) > 8 else "EMPTY/SHORT"
            print(f"gemini_api_key: {masked}")
        else:
            print("gemini_api_key: NOT FOUND in DB")
    except Exception as e:
        print(f"Error reading settings: {e}")

    # 2. Check Agent '小智'
    print("\n--- Agent '小智' ---")
    try:
        # Try to find by name containing '小智'
        cursor.execute("SELECT name, provider, model_name FROM agents WHERE name LIKE '%小智%'")
        rows = cursor.fetchall()
        for r in rows:
            print(f"Name: {r[0]}, Provider: {r[1]}, Model: {r[2]}")
            
        if not rows:
            print("No agent found with name like '小智'. Listing all agents:")
            cursor.execute("SELECT name, provider, model_name FROM agents")
            for r in cursor.fetchall():
                print(f"Name: {r[0]}, Provider: {r[1]}, Model: {r[2]}")

    except Exception as e:
        print(f"Error reading agents: {e}")
        
    conn.close()

if __name__ == "__main__":
    check_db()
