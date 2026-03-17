@echo off
cd /d "%~dp0"
echo ============================================
echo C-Cleaner DEV MODE (Auto-Reload)
echo ============================================
echo.
echo This mode will:
echo   1. Start the application
echo   2. Watch for code changes
echo   3. Auto-reload when files are modified
echo.
echo Press Ctrl+C to stop
echo ============================================
echo.

:: Check if watchdog is installed
python -c "import watchdog" 2>nul
if errorlevel 1 (
    echo [INFO] Installing watchdog for auto-reload...
    pip install watchdog
    echo.
)

:: Start development runner
python main_dev.py

echo.
echo ============================================
echo Development server stopped
echo ============================================
pause
