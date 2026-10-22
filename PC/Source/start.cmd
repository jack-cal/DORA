@echo off
setlocal
call "%~dp0run.cmd" app %*
exit /b %errorlevel%
