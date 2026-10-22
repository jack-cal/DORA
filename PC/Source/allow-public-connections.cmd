@echo off
setlocal
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0tools\allow-public-connections.ps1"
exit /b %errorlevel%
