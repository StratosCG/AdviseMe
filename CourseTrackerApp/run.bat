@echo off
echo ==========================================
echo  Course Tracker - Starting...
echo ==========================================
echo.

:: Try 'py' command first (Python Install Manager), then 'python'
where py >nul 2>&1
if %errorlevel% equ 0 (
    set PYCMD=py
    goto :found
)

where python >nul 2>&1
if %errorlevel% equ 0 (
    set PYCMD=python
    goto :found
)

echo ERROR: Python is not found on your system.
echo.
echo Please install Python from https://www.python.org/downloads/
echo Make sure to check "Add Python to PATH" during installation.
pause
exit /b 1

:found
echo Found Python:
%PYCMD% --version
echo.

echo Installing required packages (first time only)...
%PYCMD% -m pip install PyMuPDF reportlab customtkinter 2>&1
echo.

echo Launching Course Tracker...
echo.
%PYCMD% "%~dp0main.py"

if %errorlevel% neq 0 (
    echo.
    echo ==========================================
    echo  Something went wrong. See error above.
    echo ==========================================
    pause
)
