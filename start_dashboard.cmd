@echo off
cd /d "%~dp0"
python ricca_dashboard.py
if errorlevel 1 pause
