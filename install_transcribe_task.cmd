@echo off
REM Dang ky watcher transcribe chay ngam. Vi du:
REM   install_transcribe_task.cmd -All
REM   install_transcribe_task.cmd -Course "AI Automations by Jack"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0app\install_transcribe_task.ps1" %*
echo.
pause
