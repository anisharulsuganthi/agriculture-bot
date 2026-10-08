@echo off
setlocal

echo ==============================================================
echo   Starting Smart Farm: Frontend, Backend ^& ML Models
echo ==============================================================
echo.

cd /d "%~dp0"

:: Detect Python interpreter (use backend\venv if present, otherwise system python)
if exist "%~dp0backend\venv\Scripts\python.exe" (
    set "PYTHON_EXEC=%~dp0backend\venv\Scripts\python.exe"
) else (
    set "PYTHON_EXEC=python"
)

:: Ensure backend .env exists
if not exist "%~dp0backend\.env" (
    copy "%~dp0backend\.env.example" "%~dp0backend\.env" >nul
)

:: 1. Launch Backend API and ML Models
echo [1/2] Launching Backend API ^& ML Models on http://127.0.0.1:8000 ...
start "Smart Farm - Backend & ML Engine" cmd /k "cd /d "%~dp0backend" && title Smart Farm Backend && "%PYTHON_EXEC%" main.py"

:: 2. Launch Frontend
echo [2/2] Launching Frontend on http://127.0.0.1:5500 ...
start "Smart Farm - Frontend" cmd /k "cd /d "%~dp0frontend" && title Smart Farm Frontend && "%PYTHON_EXEC%" -m http.server 5500"

:: 3. Directly open the webpage in the browser
echo.
echo Opening Smart Farm in browser...
timeout /t 2 /nobreak >nul
start http://localhost:5500

echo.
echo Application started:
echo   - Web App:      http://localhost:5500
echo   - Backend API:  http://localhost:8000/docs
echo.
pause
