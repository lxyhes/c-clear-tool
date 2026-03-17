@echo off
cd /d "%~dp0"
echo ============================================
echo C-Cleaner Launcher
echo ============================================
echo.
echo Current Directory: %CD%
echo.
python --version
echo.
echo Starting application...
echo (Press Ctrl+C to force quit)
echo ============================================
echo.

:: Run Python with unbuffered output (-u) so logs appear immediately
python -u main.py

set EXIT_CODE=%ERRORLEVEL%
echo.
echo ============================================
echo Application exited with code: %EXIT_CODE%
echo ============================================
pause