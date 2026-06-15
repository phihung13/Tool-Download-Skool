@echo off
REM Go watcher transcribe chay ngam.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0app\uninstall_transcribe_task.ps1" %*
echo.
pause
