import sqlite3
import os

DB_PATH = r"c:\Users\Showbox\Desktop\AI Agengt Management\CompanySystem\company_ai.db"

def switch_to_openai():
    if not os.path.exists(DB_PATH):
        print(f"❌ DB not found at {DB_PATH}")
        return

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    print(f"Switching '小智' to OpenAI...")
    try:
        # Update provider AND model_name (to a valid OpenAI model)
        cursor.execute("UPDATE agents SET provider='openai', model_name='gpt-4o' WHERE name LIKE '%小智%'")
        rows_affected = cursor.rowcount
        conn.commit()
        print(f"✅ Success. Updated {rows_affected} rows.")
        
        # Verify
        cursor.execute("SELECT name, provider, model_name FROM agents WHERE name LIKE '%小智%'")
        for r in cursor.fetchall():
            print(f"  Verified -> Name: {r[0]}, Provider: {r[1]}, Model: {r[2]}")
            
    except Exception as e:
        print(f"❌ Error updating agent: {e}")
        
    conn.close()

if __name__ == "__main__":
    switch_to_openai()
