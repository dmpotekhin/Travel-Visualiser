#!/bin/bash
# One-command launcher for Travel Visualizer.
set -e
cd "$(dirname "$0")"

if [ ! -d ".venv" ]; then
  echo "Creating virtualenv..."
  python3 -m venv .venv
fi

source .venv/bin/activate
pip install -q -r requirements.txt

echo "Starting Travel Visualizer at http://127.0.0.1:8000"
python main.py
