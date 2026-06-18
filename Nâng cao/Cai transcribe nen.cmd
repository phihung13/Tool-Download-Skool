@echo off
REM (NANG CAO) Dang ky watcher transcribe chay ngam (Windows Scheduled Task). Vi du:
REM   "Cai transcribe nen.cmd" -All
REM   "Cai transcribe nen.cmd" -Course "AI Automations by Jack"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0..\app\install_transcribe_task.ps1" %*
echo.
pause
