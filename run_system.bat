@echo off
echo Starting Company AI System...

:: Create virtual environment if it doesn't exist
if not exist "venv" (
    echo Creating virtual environment...
    python -m venv venv
)

:: Force upgrade dependencies to fix version conflicts
echo Updating dependencies (Force Upgrade)...
call venv\Scripts\activate
pip install -r backend\requirements.txt --upgrade

:: Run the unified launcher script
python launcher.py
pause
