@echo off
cd /d "%~dp0"

start "Lint Fix" cmd /k "python lint_fix.py --backend ruff"

timeout /t 1 /nobreak >nul
exit /b