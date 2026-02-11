
import sqlite3
import os

# Define database path
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, "company_ai.db")

def add_column(cursor, table_name, column_name, column_type):
    try:
        cursor.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_type}")
        print(f"Successfully added column '{column_name}' to table '{table_name}'.")
    except sqlite3.OperationalError as e:
        if "duplicate column name" in str(e):
            print(f"Column '{column_name}' already exists in table '{table_name}'. Skipping.")
        else:
            print(f"Error adding column '{column_name}': {e}")

def main():
    if not os.path.exists(DB_PATH):
        print(f"Database not found at {DB_PATH}")
        return

    print(f"Connecting to database at {DB_PATH}...")
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Add new columns to agents table
    add_column(cursor, "agents", "job_title", "VARCHAR")
    add_column(cursor, "agents", "department", "VARCHAR")
    add_column(cursor, "agents", "level", "VARCHAR")

    conn.commit()
    conn.close()
    print("Database schema update complete.")

if __name__ == "__main__":
    main()
