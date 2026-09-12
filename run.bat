@echo off
if not exist "venv\Scripts\activate.bat" (
    echo [ERROR] Virtual environment 'venv' not found!
    echo Please run 'setup.bat' first to install packages and set up the project.
    pause
    exit /b 1
)

call venv\Scripts\activate.bat
echo Starting EduPilot AI Assistant...
python main.py
pause
