@echo off
REM ================================================================
REM  Skool Archiver - BAM PHAT LA CHAY.
REM  Lan dau se tu cai dat (vai phut). Cac lan sau mo giao dien ngay.
REM  Khong can chay setup hay run gi het - chi can file nay.
REM ================================================================
title Skool Archiver
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0app\start.ps1"
if errorlevel 1 (
  echo.
  echo [!] Khong mo duoc giao dien - xem thong bao o tren.
  echo     Bam phim bat ky de dong.
  pause >nul
)
