
import sys
import os

# Add the project root to sys.path
sys.path.append(os.getcwd())

try:
    print("Attempting to import app.main...")
    from app import main
    print("Successfully imported app.main!")
except Exception as e:
    print(f"FAILED to import app.main:")
    import traceback
    traceback.print_exc()
