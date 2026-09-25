@echo off
if not exist "venv\Scripts\python.exe" (
    echo [ERROR] The project Python environment is missing.
    echo Run 'setup.bat' first to install packages and set up the project.
    pause
    exit /b 1
)

call "venv\Scripts\python.exe" --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] The project Python environment is broken or its base Python was moved.
    echo Run 'setup.bat' to rebuild the generated environment.
    pause
    exit /b 1
)

echo Starting EduPilot AI Assistant...
"venv\Scripts\python.exe" main.py
pause
