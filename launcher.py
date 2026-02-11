import subprocess
import time
import sys
import os

def main():
    print("🚀 Starting Company AI System...")
    
    # Define paths
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    BACKEND_CMD = [sys.executable, "-m", "uvicorn", "backend.app.main:app", "--reload", "--port", "8000"]
    FRONTEND_CMD = [sys.executable, "-m", "streamlit", "run", "frontend_app.py"]

    # 1. Start Backend
    print("   [1/2] Launching Backend Server (FastAPI)...")
    backend = subprocess.Popen(BACKEND_CMD, cwd=BASE_DIR)
    
    # Wait for backend to be ready
    time.sleep(5)
    
    # 2. Start Frontend
    print("   [2/2] Launching Frontend Interface (Streamlit)...")
    frontend = subprocess.Popen(FRONTEND_CMD, cwd=BASE_DIR)

    print("\n✅ System Running! Press Ctrl+C to stop.")
    print("   - API:      http://localhost:8000/docs")
    print("   - Frontend: http://localhost:8501")

    try:
        backend.wait()
        frontend.wait()
    except KeyboardInterrupt:
        print("\n🛑 Stopping system...")
        backend.terminate()
        frontend.terminate()
        print("   Shutdown complete.")

if __name__ == "__main__":
    main()
