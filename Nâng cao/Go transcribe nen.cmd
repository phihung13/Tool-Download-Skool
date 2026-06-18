@echo off
REM (NANG CAO) Go watcher transcribe chay ngam.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0..\app\uninstall_transcribe_task.ps1" %*
echo.
pause
