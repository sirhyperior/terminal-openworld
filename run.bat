@echo off
setlocal
cd /d "%~dp0"
where python >nul 2>nul
if errorlevel 1 (
    py -3 main.py %*
) else (
    python main.py %*
)
if errorlevel 1 pause
