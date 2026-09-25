#!/bin/bash
if [ ! -x "venv/bin/python" ]; then
    echo "[ERROR] The project Python environment is missing."
    echo "Please run './setup.sh' first to install packages."
    exit 1
fi

if ! venv/bin/python --version >/dev/null 2>&1; then
    echo "[ERROR] The project Python environment is broken or its base Python was moved."
    echo "Run './setup.sh' to rebuild the generated environment."
    exit 1
fi

echo "Starting EduPilot AI Assistant..."
venv/bin/python main.py
