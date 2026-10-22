@echo off
setlocal
call "%~dp0run.cmd" app --allow-internet --listen 0.0.0.0:18444 %*
exit /b %errorlevel%
