@echo off
REM Chay pipeline ma khong vuong ExecutionPolicy. Vi du:
REM   run.cmd --course "AI Automations by Jack"
REM   run.cmd --list-courses
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0app\run.ps1" %*
