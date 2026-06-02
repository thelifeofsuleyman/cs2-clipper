@echo off
REM Convenience launcher — runs Aegis Clipper with the venv interpreter.
cd /d "%~dp0"
if not exist .venv\Scripts\python.exe (
    echo .venv not set up. Run: python -m venv .venv  then activate and pip install -r requirements.txt
    pause
    exit /b 1
)
.venv\Scripts\python.exe -m aegis %*
