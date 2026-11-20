@echo off
rem Careers loop + result page (http://127.0.0.1:8910/careers) in two windows outside Claude Code.
rem Close a window to stop it. ASCII only: cmd parses this file before any code page switch.
set PYTHONIOENCODING=utf-8
cd /d "%~dp0.."
start "careers-page 8910" cmd /k "chcp 65001 >nul & .venv\Scripts\python.exe -m servers.admin.server"
start "careers-loop" cmd /k "chcp 65001 >nul & .venv\Scripts\python.exe -m careers.cycle --forever --queries 80 --sleep 30"
echo Started. Page: http://127.0.0.1:8910/careers
