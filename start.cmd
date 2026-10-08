@echo off
cd /d "%~dp0"
echo YiRead - http://127.0.0.1:8765
if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" backend\server.py --open-browser
) else (
    python backend\server.py --open-browser
)
pause
