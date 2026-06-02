# Build Aegis Clipper into a one-click Windows installer.
#
#   powershell -ExecutionPolicy Bypass -File packaging\build.ps1            # exe only
#   powershell -ExecutionPolicy Bypass -File packaging\build.ps1 -Ffmpeg    # also vendor ffmpeg
#   powershell -ExecutionPolicy Bypass -File packaging\build.ps1 -Installer # also build the .exe installer (needs Inno Setup)
#
# Run from the repo root. Produces:
#   dist\AegisClipper\AegisClipper.exe         (the app)
#   packaging\Output\AegisClipper-Setup.exe    (with -Installer)
param(
    [switch]$Ffmpeg,
    [switch]$Installer
)
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

# Single source of truth for the version: aegis/__init__.py
$verLine = Select-String -Path "aegis\__init__.py" -Pattern '__version__\s*=\s*"([^"]+)"'
$AppVersion = $verLine.Matches[0].Groups[1].Value
Write-Host "Building Aegis Clipper v$AppVersion" -ForegroundColor Cyan

# 1. Build environment ----------------------------------------------------
if (-not (Test-Path ".venv\Scripts\python.exe")) {
    Write-Host "Creating build venv..." -ForegroundColor Cyan
    python -m venv .venv
}
$py = ".\.venv\Scripts\python.exe"
Write-Host "Installing dependencies + PyInstaller..." -ForegroundColor Cyan
& $py -m pip install --quiet --upgrade pip
& $py -m pip install --quiet -r requirements.txt pyinstaller

# 2. Optionally vendor ffmpeg --------------------------------------------
if ($Ffmpeg) {
    $vendor = "packaging\vendor"
    New-Item -ItemType Directory -Force $vendor | Out-Null
    if (-not (Test-Path "$vendor\ffmpeg.exe")) {
        Write-Host "Downloading ffmpeg (gyan.dev essentials build)..." -ForegroundColor Cyan
        $zip = "$env:TEMP\ffmpeg.zip"
        Invoke-WebRequest "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip" -OutFile $zip
        Expand-Archive $zip "$env:TEMP\ffmpeg" -Force
        $bin = Get-ChildItem "$env:TEMP\ffmpeg" -Recurse -Filter "ffmpeg.exe" | Select-Object -First 1
        Copy-Item $bin.FullName "$vendor\ffmpeg.exe"
        Copy-Item (Join-Path $bin.DirectoryName "ffprobe.exe") "$vendor\ffprobe.exe"
        Remove-Item $zip, "$env:TEMP\ffmpeg" -Recurse -Force
    }
    Write-Host "ffmpeg vendored." -ForegroundColor Green
}

# 3. PyInstaller ----------------------------------------------------------
Write-Host "Running PyInstaller..." -ForegroundColor Cyan
& $py -m PyInstaller --noconfirm --clean packaging\aegis.spec
Write-Host "App built -> dist\AegisClipper\AegisClipper.exe" -ForegroundColor Green

# 4. Optionally build the installer --------------------------------------
if ($Installer) {
    $iscc = @(
        "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe",
        "$env:ProgramFiles\Inno Setup 6\ISCC.exe"
    ) | Where-Object { Test-Path $_ } | Select-Object -First 1
    if (-not $iscc) {
        Write-Warning "Inno Setup not found. Install it from https://jrsoftware.org/isinfo.php then re-run with -Installer, or open packaging\aegis.iss in the Inno compiler."
    } else {
        Write-Host "Compiling installer with Inno Setup..." -ForegroundColor Cyan
        & $iscc "/DAppVersion=$AppVersion" "packaging\aegis.iss"
        Write-Host "Installer built -> packaging\Output\AegisClipper-Setup.exe" -ForegroundColor Green
    }
}
