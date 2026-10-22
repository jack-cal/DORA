@echo off
setlocal
rem Supply the address of a running SUMUWW node. No preset peer is bundled.
if "%~1"=="" goto usage
call "%~dp0run.cmd" app --allow-internet --peer %*
exit /b %errorlevel%
:usage
echo Usage: join-network.cmd HOST:PORT [additional SUMUWW options]
echo Enter the address of a running SUMUWW node you choose.
exit /b 2
