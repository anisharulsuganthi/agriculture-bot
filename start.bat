@echo off
echo ==============================================================
echo  Starting Smart Farm: Agricultural Decision Intelligence System
echo ==============================================================
echo.

cd /d "%~dp0"

echo [1/2] Launching Backend API on http://127.0.0.1:8000 ...
start "Smart Farm - Backend" cmd /k "cd /d "%~dp0backend" && python main.py"

echo [2/2] Launching Frontend SPA on http://127.0.0.1:5500 ...
start "Smart Farm - Frontend" cmd /k "cd /d "%~dp0frontend" && python -m http.server 5500"

echo.
echo Application successfully launched!
echo Access the system at: http://localhost:5500
echo Backend API Docs at:  http://localhost:8000/docs
echo.
pause
