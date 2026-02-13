import sqlite3
import os

# Explicitly target the active DB found in previous step
DB_PATH = r"c:\Users\Showbox\Desktop\AI Agengt Management\CompanySystem\company_ai.db"

if not os.path.exists(DB_PATH):
    print(f"Error: {DB_PATH} not found!")
    exit(1)

print(f"Migrating DB at: {DB_PATH}")

try:
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Check if column exists
    cursor.execute("PRAGMA table_info(settings)")
    columns = [row[1] for row in cursor.fetchall()]
    
    if "gemini_api_key" not in columns:
        print("Adding 'gemini_api_key' column to 'settings' table...")
        cursor.execute("ALTER TABLE settings ADD COLUMN gemini_api_key VARCHAR")
        conn.commit()
        print("✅ Migration successful.")
    else:
        print("Column 'gemini_api_key' already exists.")
        
    # Check agents table
    cursor.execute("PRAGMA table_info(agents)")
    agent_cols = [row[1] for row in cursor.fetchall()]
    if "provider" not in agent_cols:
        print("Adding 'provider' column to 'agents' table...")
        cursor.execute("ALTER TABLE agents ADD COLUMN provider VARCHAR DEFAULT 'openai'")
        conn.commit()
    
    if "model_name" not in agent_cols:
        print("Adding 'model_name' column to 'agents' table...")
        cursor.execute("ALTER TABLE agents ADD COLUMN model_name VARCHAR")
        conn.commit()
        
    conn.close()
    
except Exception as e:
    print(f"Migration Failed: {e}")
