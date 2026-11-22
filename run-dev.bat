@echo off
call "%~dp0run.bat" --dev %*
exit /b %errorlevel%
