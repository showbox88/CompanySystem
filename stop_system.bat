@echo off
echo Stopping all Company AI System processes...
taskkill /F /IM python.exe /T
taskkill /F /IM uvicorn.exe /T
taskkill /F /IM streamlit.exe /T
echo All processes stopped. You can now safe run run_system.bat
pause
