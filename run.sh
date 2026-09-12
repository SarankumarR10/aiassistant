#!/bin/bash
if [ ! -f "venv/bin/activate" ]; then
    echo "[ERROR] Virtual environment 'venv' not found!"
    echo "Please run './setup.sh' first to install packages."
    exit 1
fi

source venv/bin/activate
echo "Starting EduPilot AI Assistant..."
python3 main.py
