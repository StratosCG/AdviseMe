@echo off
echo ==========================================
echo  Course Tracker - Build EXE
echo ==========================================
echo.

:: ── Find the real Python (skip Windows Store stub) ──────────────
set PYTHON=

:: Try 'py' launcher first (most reliable on Windows)
py --version >nul 2>&1
if %ERRORLEVEL% equ 0 (
    set PYTHON=py
    goto :found_python
)

:: Try 'python' but verify it's not the Windows Store stub
for /f "delims=" %%i in ('where python 2^>nul') do (
    echo %%i | findstr /i "WindowsApps" >nul
    if errorlevel 1 (
        set PYTHON=%%i
        goto :found_python
    )
)

:: Last resort
set PYTHON=python

:found_python
echo Using Python: %PYTHON%
%PYTHON% --version
echo.

:: ── Install dependencies ─────────────────────────────────────────
echo Installing dependencies...
"%PYTHON%" -m pip install -r requirements.txt --quiet
"%PYTHON%" -m pip install pyinstaller --quiet
echo.

:: ── Locate CustomTkinter ─────────────────────────────────────────
echo Locating CustomTkinter assets...
for /f "delims=" %%i in ('"%PYTHON%" -c "import customtkinter, os; print(os.path.dirname(customtkinter.__file__))" 2^>nul') do set CTK_PATH=%%i

if "%CTK_PATH%"=="" (
    echo WARNING: Could not locate CustomTkinter. Building without it.
    echo.
    "%PYTHON%" -m PyInstaller --onefile --windowed ^
        --name "CourseTracker" ^
        --icon "assets\AdviseMe.ico" ^
        --add-data "programs;programs" ^
        --add-data "version.py;." ^
        --add-data "assets;assets" ^
        --hidden-import "customtkinter" ^
        --hidden-import "PIL" ^
        --hidden-import "PIL.Image" ^
        --hidden-import "PIL.ImageTk" ^
        --hidden-import "core.models" ^
        --hidden-import "core.evaluation_parser" ^
        --hidden-import "core.grid_loader" ^
        --hidden-import "core.course_matcher" ^
        --hidden-import "core.semester_planner" ^
        --hidden-import "core.pdf_generator" ^
        --hidden-import "core.updater" ^
        --hidden-import "gui.app" ^
        main.py
) else (
    echo Found CustomTkinter at: %CTK_PATH%
    echo.
    echo Building executable...
    "%PYTHON%" -m PyInstaller --onefile --windowed ^
        --name "CourseTracker" ^
        --icon "assets\AdviseMe.ico" ^
        --add-data "programs;programs" ^
        --add-data "version.py;." ^
        --add-data "assets;assets" ^
        --add-data "%CTK_PATH%;customtkinter" ^
        --hidden-import "customtkinter" ^
        --hidden-import "PIL" ^
        --hidden-import "PIL.Image" ^
        --hidden-import "PIL.ImageTk" ^
        --hidden-import "core.models" ^
        --hidden-import "core.evaluation_parser" ^
        --hidden-import "core.grid_loader" ^
        --hidden-import "core.course_matcher" ^
        --hidden-import "core.semester_planner" ^
        --hidden-import "core.pdf_generator" ^
        --hidden-import "core.updater" ^
        --hidden-import "gui.app" ^
        main.py
)

if %ERRORLEVEL% neq 0 (
    echo.
    echo ==========================================
    echo  BUILD FAILED - see errors above
    echo ==========================================
    pause
    exit /b 1
)

echo.
echo ==========================================
echo  Build complete!
echo  EXE location: dist\CourseTracker.exe
echo ==========================================
echo.
echo To distribute to other faculty, just share
echo the CourseTracker.exe file from the dist folder.
echo They do NOT need Python installed.
echo ==========================================
pause
