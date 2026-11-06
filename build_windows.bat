@echo off
setlocal
cd /d "%~dp0"
echo The Project Company - Universal Licence Generator v0.1.0
where py >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python launcher not found. Install Python 3.10 or newer.
    pause
    exit /b 1
)
if not exist ".venv\Scripts\python.exe" (
    py -3 -m venv .venv
    if errorlevel 1 goto :fail
)
call ".venv\Scripts\python.exe" -m pip install --upgrade pip
if errorlevel 1 goto :fail
call ".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 goto :fail
call ".venv\Scripts\python.exe" -m PyInstaller --noconfirm --clean --onefile --windowed --name TPC_Licence_Generator --add-data "assets;assets" run_admin.py
if errorlevel 1 goto :fail
echo.
echo BUILD COMPLETE: dist\TPC_Licence_Generator.exe
echo Private signing keys are NEVER included in the executable.
pause
exit /b 0
:fail
echo.
echo BUILD FAILED. Read the error messages above.
pause
exit /b 1
