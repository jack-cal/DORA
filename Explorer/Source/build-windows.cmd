@echo off
setlocal
cd /d "%~dp0"
python -m pip install -r requirements.txt
if errorlevel 1 exit /b %errorlevel%
python -m PyInstaller --noconfirm --clean --distpath release --workpath build SUMUWW-Explorer.spec
