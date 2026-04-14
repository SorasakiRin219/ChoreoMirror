#!/bin/bash
echo ""
echo "======================================"
echo "  Dance Analyser - Startup"
echo "======================================"
echo ""

if ! command -v python3 &>/dev/null; then
    echo "ERROR: python3 not found. Please install Python 3.9+"
    exit 1
fi

if [ ! -f "main.py" ]; then
    echo "ERROR: main.py not found."
    echo "Make sure these files are in the same folder as this script:"
    echo "  main.py"
    echo "  config/"
    echo "  core/"
    echo "  temporal/"
    echo "  pose/"
    echo "  data/"
    echo "  processing/"
    echo "  web/"
    echo "  ai/"
    echo "  utils/"
    echo "  templates/index.html"
    echo "  static/css/style.css"
    echo "  static/js/app.js"
    echo ""
    echo "INFO: This project has been refactored to a modular structure."
    echo "Please download the complete project from the repository."
    exit 1
fi

echo "Installing / updating packages..."
pip3 install flask mediapipe opencv-python numpy anthropic openai --quiet

echo ""
echo "Packages ready. Starting server..."
echo "This is the modular version (v3.1)"
echo "Browser will open at http://127.0.0.1:5000"
echo "Press Ctrl+C to stop."
echo ""

python3 main.py
