@echo off
setlocal
cd /d "%~dp0"
if exist "%~dp0SUMUWW-Explorer.exe" (
  "%~dp0SUMUWW-Explorer.exe" --open-browser %*
) else (
  python -X utf8 -B server.py --open-browser %*
)
if errorlevel 1 pause
