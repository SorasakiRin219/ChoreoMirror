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

if [ ! -f "Dance_Analyser.py" ]; then
    echo "ERROR: Dance_Analyser.py not found."
    echo "Make sure these files are in the same folder as this script:"
    echo "  Dance_Analyser.py"
    echo "  templates/index.html"
    echo "  static/css/style.css"
    echo "  static/js/app.js"
    exit 1
fi

echo "Installing / updating packages..."
pip3 install flask mediapipe opencv-python numpy anthropic openai --quiet

echo ""
echo "Packages ready. Starting server..."
echo "Browser will open at http://127.0.0.1:5000"
echo "Press Ctrl+C to stop."
echo ""

python3 Dance_Analyser.py
