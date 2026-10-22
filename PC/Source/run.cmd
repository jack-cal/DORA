@echo off
setlocal
if /i "%~1"=="app" goto app_binary
if /i "%~1"=="node" goto node_binary
if /i "%~1"=="peer" goto node_binary
if /i "%~1"=="rpc" goto node_binary
goto python_fallback
:app_binary
if exist "%~dp0SUMUWW.exe" goto app_here
if exist "%~dp0bin\SUMUWW\SUMUWW.exe" goto app_nested
goto python_fallback
:app_here
"%~dp0SUMUWW.exe" %*
exit /b %errorlevel%
:app_nested
"%~dp0bin\SUMUWW\SUMUWW.exe" %*
exit /b %errorlevel%
:node_binary
if exist "%~dp0SUMUWW-node.exe" goto node_here
if exist "%~dp0bin\SUMUWW\SUMUWW-node.exe" goto node_nested
goto python_fallback
:node_here
"%~dp0SUMUWW-node.exe" %*
exit /b %errorlevel%
:node_nested
"%~dp0bin\SUMUWW\SUMUWW-node.exe" %*
exit /b %errorlevel%
:python_fallback
if defined SUMUWW_PYTHON goto ready
set "SUMUWW_PYTHON=python"
:ready
"%SUMUWW_PYTHON%" -B "%~dp0run.py" %*
exit /b %errorlevel%
