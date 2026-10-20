@echo off
setlocal
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0run_native.ps1" %*
echo.
echo Exit code: %ERRORLEVEL%
pause
