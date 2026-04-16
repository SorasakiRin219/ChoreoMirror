@echo off
cd /d "%~dp0"

echo.
echo  ==========================================
echo   choreomirror - Startup
echo  ==========================================
echo.

set PYTHON_CMD=

python --version > nul 2>&1
if not errorlevel 1 set PYTHON_CMD=python
if not errorlevel 1 goto found

py --version > nul 2>&1
if not errorlevel 1 set PYTHON_CMD=py
if not errorlevel 1 goto found

python3 --version > nul 2>&1
if not errorlevel 1 set PYTHON_CMD=python3
if not errorlevel 1 goto found

echo  [ERROR] Python not found.
echo  Install Python 3.9+ from https://www.python.org/downloads/
echo  IMPORTANT: check Add Python to PATH during install.
echo.
start https://www.python.org/downloads/
pause
exit /b 1

:found
echo  [OK] Python found: %PYTHON_CMD%
%PYTHON_CMD% --version
echo.

if not exist "main.py" (
    echo  [ERROR] main.py not found.
    echo  Make sure these files are in the SAME folder as this .bat:
    echo    main.py
    echo    config\
    echo    core\
    echo    temporal\
    echo    pose\
    echo    data\
    echo    processing\
    echo    web\
    echo    ai\
    echo    utils\
    echo    templates\index.html
    echo    static\css\style.css
    echo    static\js\app.js
    echo.
    echo  [INFO] This project has been refactored to a modular structure.
    echo  Please download the complete project from the repository.
    echo.
    pause
    exit /b 1
)

if not exist "templates\index.html" (
    echo  [ERROR] templates\index.html not found.
    echo  Please check the project folder structure.
    echo.
    pause
    exit /b 1
)

echo  [INFO] Installing / updating packages...
echo.

%PYTHON_CMD% -m pip install flask --quiet
echo  [1/6] flask OK

%PYTHON_CMD% -m pip install mediapipe --quiet
echo  [2/6] mediapipe OK

%PYTHON_CMD% -m pip install opencv-python --quiet
echo  [3/6] opencv OK

%PYTHON_CMD% -m pip install numpy --quiet
echo  [4/6] numpy OK

%PYTHON_CMD% -m pip install anthropic --quiet
echo  [5/6] anthropic OK

%PYTHON_CMD% -m pip install openai --quiet
echo  [6/6] openai OK

echo.
echo  [OK] All packages ready.
echo  [OK] Starting server...
echo  [INFO] This is the modular version (v3.1)
echo.
echo  Browser will open at: http://127.0.0.1:5000
echo  Press Ctrl+C or close this window to stop.
echo.

%PYTHON_CMD% main.py

echo.
echo  [INFO] Server stopped.
pause
