@echo off
setlocal
echo ========================================================
echo   GTFB - Building Windows Standalone Executable (.exe)
echo ========================================================
echo.

REM Check Python installation
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python is not found in your PATH.
    echo Please install Python 3.12+ and ensure "Add Python to PATH" is checked.
    pause
    exit /b 1
)

REM Run Python build script
python "%~dp0build_windows.py" %*
if %errorlevel% neq 0 (
    echo.
    echo [ERROR] Build failed! See error messages above.
    pause
    exit /b %errorlevel%
)

echo.
echo [SUCCESS] Build complete! Executable is located in the dist\ folder.
echo.
pause
