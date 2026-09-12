@echo off
echo ===================================================
echo EduPilot Project Setup Script (Windows)
echo ===================================================
echo.

:: Check if Python is installed
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python is not installed or not in PATH!
    echo Please install Python 3.10 or higher from https://python.org
    pause
    exit /b 1
)

echo [1/4] Creating Python Virtual Environment (venv)...
if not exist "venv" (
    python -m venv venv
    if %errorlevel% neq 0 (
        echo [ERROR] Failed to create virtual environment.
        pause
        exit /b 1
    )
    echo Virtual environment created successfully.
) else (
    echo Virtual environment 'venv' already exists.
)

echo.
echo [2/4] Upgrading pip...
call venv\Scripts\activate.bat
python -m pip install --upgrade pip

echo.
echo [3/4] Installing project dependencies from requirements.txt...
pip install -r requirements.txt
if %errorlevel% neq 0 (
    echo [ERROR] Package installation failed!
    pause
    exit /b 1
)

echo.
echo [4/4] Initializing EduPilot Database...
python -c "from database.database import initialize_database; initialize_database(); print('Database initialized successfully!')"

echo.
echo ===================================================
echo Setup complete! You can now run EduPilot by double-clicking 'run.bat'
echo or running 'python main.py' inside the virtual environment.
echo ===================================================
pause
