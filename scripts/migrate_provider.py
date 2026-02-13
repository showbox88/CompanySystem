import sqlite3
import os

# Define path to database
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, "company_ai.db")

def migrate():
    if not os.path.exists(DB_PATH):
        print(f"Database not found at {DB_PATH}")
        return

    print(f"Connecting to database at {DB_PATH}...")
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    try:
        # Check if column exists
        cursor.execute("PRAGMA table_info(agents)")
        columns = [info[1] for info in cursor.fetchall()]
        
        if "provider" in columns:
            print("Column 'provider' already exists in 'agents' table. Skipping.")
        else:
            print("Adding 'provider' column to 'agents' table...")
            cursor.execute("ALTER TABLE agents ADD COLUMN provider VARCHAR DEFAULT 'openai'")
            conn.commit()
            print("Migration successful.")
            
    except Exception as e:
        print(f"Migration failed: {e}")
        conn.rollback()
    finally:
        conn.close()

if __name__ == "__main__":
    migrate()
