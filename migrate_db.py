import sqlite3

def migrate():
    try:
        conn = sqlite3.connect('company_ai.db')
        cursor = conn.cursor()
        
        # Check if column exists
        cursor.execute("PRAGMA table_info(tasks)")
        columns = [info[1] for info in cursor.fetchall()]
        
        if 'project_file' not in columns:
            print("Adding 'project_file' column to 'tasks' table...")
            cursor.execute("ALTER TABLE tasks ADD COLUMN project_file VARCHAR")
            conn.commit()
            print("Migration successful.")
        else:
            print("'project_file' column already exists.")
            
        conn.close()
    except Exception as e:
        print(f"Migration failed: {e}")

if __name__ == "__main__":
    migrate()
