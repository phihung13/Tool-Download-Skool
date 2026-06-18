@echo off
REM (NANG CAO) Chay pipeline tai bang dong lenh. Vi du:
REM   "Tai bang dong lenh.cmd" --course "AI Automations by Jack"
REM   "Tai bang dong lenh.cmd" --list-courses
REM Nguoi dung binh thuong KHONG can file nay - dung SkoolArchiver.cmd o thu muc cha.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0..\app\run.ps1" %*
