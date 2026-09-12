#!/bin/bash
set -e

echo "==================================================="
echo "EduPilot Project Setup Script (macOS/Linux)"
echo "==================================================="
echo ""

if ! command -v python3 &> /dev/null
then
    echo "[ERROR] Python 3 could not be found. Please install Python 3.10+."
    exit 1
fi

echo "[1/4] Creating Python Virtual Environment (venv)..."
if [ ! -d "venv" ]; then
    python3 -m venv venv
    echo "Virtual environment created successfully."
else
    echo "Virtual environment 'venv' already exists."
fi

echo ""
echo "[2/4] Upgrading pip..."
source venv/bin/activate
pip install --upgrade pip

echo ""
echo "[3/4] Installing project dependencies from requirements.txt..."
pip install -r requirements.txt

echo ""
echo "[4/4] Initializing EduPilot Database..."
python3 -c "from database.database import initialize_database; initialize_database(); print('Database initialized successfully!')"

echo ""
echo "==================================================="
echo "Setup complete! Run './run.sh' or 'python main.py' to start."
echo "==================================================="
