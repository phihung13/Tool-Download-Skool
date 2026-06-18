# === Skool Archiver - MOT FILE DUY NHAT: tu cai (lan dau) roi mo giao dien ===
# Duoc SkoolArchiver.cmd goi. Nguoi dung CHI CAN bam SkoolArchiver.cmd.
$ErrorActionPreference = "Stop"
$here = Split-Path -Parent $MyInvocation.MyCommand.Definition          # ...\Archiver\app
$base = Split-Path -Parent (Split-Path -Parent $here)                 # ...\SkoolProject

function Has-Gui($py) {
    if (-not (Test-Path $py)) { return $false }
    & $py -c "import customtkinter" 2>$null
    return ($LASTEXITCODE -eq 0)
}

Write-Host ""
Write-Host "  ===== Skool Archiver =====" -ForegroundColor Cyan
Write-Host "  Dang kiem tra moi truong..." -ForegroundColor DarkGray

# 1) Tim Python da san sang (uu tien venv co san cua du an)
$py = $null
foreach ($c in @("$base\whisper\venv\Scripts\python.exe", "$here\venv\Scripts\python.exe")) {
    if (Has-Gui $c) { $py = $c; break }
}

# 2) Chua co moi truong -> tu cai vao app\venv (chi xay ra o may moi)
if (-not $py) {
    Write-Host ""
    Write-Host "  Lan dau tren may nay - dang CAI DAT (vai phut, can mang)..." -ForegroundColor Yellow
    $venv = "$here\venv"
    if (-not (Test-Path "$venv\Scripts\python.exe")) {
        $sys = $null
        if (Get-Command python -ErrorAction SilentlyContinue) { $sys = "python" }
        elseif (Get-Command py -ErrorAction SilentlyContinue) { $sys = "py" }
        if (-not $sys) {
            Add-Type -AssemblyName System.Windows.Forms
            [System.Windows.Forms.MessageBox]::Show(
                "Chua cai Python tren may nay.`n`nTai Python 3.11+ tai https://www.python.org/downloads/`n(nho tick 'Add Python to PATH' khi cai), roi bam lai SkoolArchiver.cmd.",
                "Skool Archiver") | Out-Null
            throw "Thieu Python"
        }
        Write-Host "  Tao moi truong ao..." -ForegroundColor DarkGray
        if ($sys -eq "py") { & py -3 -m venv $venv } else { & python -m venv $venv }
    }
    $vpy = "$venv\Scripts\python.exe"
    Write-Host "  Nang pip..." -ForegroundColor DarkGray
    & $vpy -m pip install --upgrade pip --quiet
    Write-Host "  Cai thu vien (yt-dlp, whisper, customtkinter, python-docx...)..." -ForegroundColor DarkGray
    & $vpy -m pip install -r "$here\requirements.txt"
    Write-Host "  Cai ffmpeg..." -ForegroundColor DarkGray
    try { & "$venv\Scripts\ffdl.exe" install --add-path } catch { Write-Host "  (ffmpeg: bo qua)" -ForegroundColor DarkGray }
    Write-Host "  Cai trinh duyet de tai khoa (playwright)..." -ForegroundColor DarkGray
    try { & $vpy -m playwright install chromium } catch { Write-Host "  (playwright: cai sau khi can)" -ForegroundColor DarkGray }
    if (Has-Gui $vpy) { $py = $vpy } else { throw "Cai xong nhung van thieu customtkinter - xem log ben tren." }
    Write-Host "  Cai dat xong!" -ForegroundColor Green
}

# 3) Mo giao dien (pythonw = khong hien cua so console den)
$pyw = $py -replace "python\.exe$", "pythonw.exe"
if (-not (Test-Path $pyw)) { $pyw = $py }
Write-Host "  Dang mo giao dien..." -ForegroundColor Green
Start-Process -FilePath $pyw -ArgumentList "gui.py" -WorkingDirectory $here
Start-Sleep -Milliseconds 800
