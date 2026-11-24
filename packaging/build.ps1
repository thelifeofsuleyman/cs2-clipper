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
    [switch]$Installer,
    [switch]$Portable
)
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

# Single source of truth for the version: aegis/__init__.py
$verLine = Select-String -Path "aegis\__init__.py" -Pattern '__version__\s*=\s*"([^"]+)"'
$AppVersion = $verLine.Matches[0].Groups[1].Value
Write-Host "Building Aegis Clipper v$AppVersion" -ForegroundColor Cyan

# 1. Build environment ----------------------------------------------------
# Prefer an existing .venv; otherwise use the python already on PATH (CI sets one
# up with deps installed). Avoids a slow, redundant second install on CI.
if (Test-Path ".venv\Scripts\python.exe") {
    $py = ".\.venv\Scripts\python.exe"
} elseif (Get-Command python -ErrorAction SilentlyContinue) {
    $py = "python"
} else {
    python -m venv .venv
    $py = ".\.venv\Scripts\python.exe"
}
Write-Host "Using interpreter: $py" -ForegroundColor Cyan
Write-Host "Installing dependencies + PyInstaller..." -ForegroundColor Cyan
& $py -m pip install --upgrade pip
& $py -m pip install -r requirements.txt pyinstaller
if ($LASTEXITCODE -ne 0) { throw "dependency install failed" }

# 2. Optionally vendor ffmpeg --------------------------------------------
if ($Ffmpeg) {
    $vendor = "packaging\vendor"
    New-Item -ItemType Directory -Force $vendor | Out-Null
    if (-not (Test-Path "$vendor\ffmpeg.exe")) {
        # BtbN's GitHub release builds are CI-friendly (gyan.dev rate-limits runners).
        $assetName = "ffmpeg-master-latest-win64-gpl.zip"
        $url = "https://github.com/FFmpeg-Builds/FFmpeg-Builds/releases/download/latest/$assetName"
        $release = Invoke-RestMethod "https://api.github.com/repos/FFmpeg-Builds/FFmpeg-Builds/releases/tags/latest"
        $asset = $release.assets | Where-Object { $_.name -eq $assetName -and $_.browser_download_url -eq $url }
        if ($asset.digest -notmatch '^sha256:[0-9a-f]{64}$') { throw "FFmpeg download digest is unavailable" }
        Write-Host "Downloading ffmpeg (BtbN win64-gpl)..." -ForegroundColor Cyan
        $vendorRoot = (Resolve-Path -LiteralPath $vendor).Path
        $scratch = Join-Path $vendorRoot ("download-" + [Guid]::NewGuid())
        New-Item -ItemType Directory -Path $scratch | Out-Null
        try {
            $zip = Join-Path $scratch "ffmpeg.zip"
            $unpacked = Join-Path $scratch "unpacked"
            Invoke-WebRequest $url -OutFile $zip -UseBasicParsing
            if ((Get-FileHash -LiteralPath $zip -Algorithm SHA256).Hash -ne $asset.digest.Substring(7)) {
                throw "FFmpeg archive does not match its published SHA-256 digest"
            }
            Expand-Archive -LiteralPath $zip -DestinationPath $unpacked
            $bin = Get-ChildItem $unpacked -Recurse -Filter "ffmpeg.exe" | Select-Object -First 1
            if (-not $bin) { throw "ffmpeg.exe not found in download" }
            Copy-Item $bin.FullName "$vendor\ffmpeg.exe"
            Copy-Item (Join-Path $bin.DirectoryName "ffprobe.exe") "$vendor\ffprobe.exe"
            $license = Join-Path (Split-Path -Parent $bin.DirectoryName) "LICENSE.txt"
            if (Test-Path -LiteralPath $license) {
                Copy-Item -LiteralPath $license -Destination "$vendor\ffmpeg-LICENSE.txt"
            }
        } finally {
            $resolvedScratch = (Resolve-Path -LiteralPath $scratch).Path
            if ((Split-Path -Parent $resolvedScratch) -eq $vendorRoot) {
                Remove-Item -LiteralPath $resolvedScratch -Recurse -Force
            }
        }
    }
    if (-not (Test-Path "$vendor\ffmpeg.exe")) { throw "ffmpeg vendoring failed" }
    Write-Host "ffmpeg vendored." -ForegroundColor Green
}

# 2b. Generate the app icon and installer artwork.
& $py packaging\make_icon.py
if ($LASTEXITCODE -ne 0) { throw "Installer artwork generation failed" }

# 3. PyInstaller ----------------------------------------------------------
Write-Host "Running PyInstaller..." -ForegroundColor Cyan
& $py -m PyInstaller --noconfirm --clean packaging\aegis.spec
if ($LASTEXITCODE -ne 0) { throw "PyInstaller failed (exit $LASTEXITCODE)" }
if (-not (Test-Path "dist\AegisClipper\AegisClipper.exe")) { throw "PyInstaller produced no exe" }
Write-Host "App built -> dist\AegisClipper\AegisClipper.exe" -ForegroundColor Green

New-Item -ItemType Directory -Force "packaging\Output" | Out-Null

# 4. Optionally produce a portable zip -----------------------------------
if ($Portable) {
    $zip = "packaging\Output\AegisClipper-portable.zip"
    if (Test-Path $zip) { Remove-Item $zip }
    Compress-Archive -Path "dist\AegisClipper\*" -DestinationPath $zip
    Write-Host "Portable zip -> $zip" -ForegroundColor Green
}

# 5. Optionally build the installer --------------------------------------
if ($Installer) {
    # Fetch the WebView2 evergreen bootstrapper so Win10 users without the
    # runtime get it during install (no-op on Win11 where it's preinstalled).
    $wv = "packaging\vendor\MicrosoftEdgeWebView2Setup.exe"
    New-Item -ItemType Directory -Force "packaging\vendor" | Out-Null
    if (-not (Test-Path $wv)) {
        Write-Host "Downloading WebView2 bootstrapper..." -ForegroundColor Cyan
        Invoke-WebRequest "https://go.microsoft.com/fwlink/p/?LinkId=2124703" -OutFile $wv
    }
    $signature = Get-AuthenticodeSignature -LiteralPath $wv
    if ($signature.Status -ne 'Valid' -or $signature.SignerCertificate.Subject -notmatch '(?:^|, )CN=Microsoft Corporation(?:,|$)') {
        throw "WebView2 bootstrapper does not have a valid Microsoft signature"
    }

    $iscc = @(
        "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe",
        "$env:ProgramFiles\Inno Setup 6\ISCC.exe"
    ) | Where-Object { Test-Path $_ } | Select-Object -First 1
    if (-not $iscc) {
        throw "Inno Setup not found. Install it from https://jrsoftware.org/isinfo.php then re-run with -Installer."
    } else {
        Write-Host "Compiling installer with Inno Setup..." -ForegroundColor Cyan
        & $iscc "/DAppVersion=$AppVersion" "packaging\aegis.iss"
        if ($LASTEXITCODE -ne 0) { throw "Inno Setup failed (exit $LASTEXITCODE)" }
        Write-Host "Installer built -> packaging\Output\AegisClipper-Setup.exe" -ForegroundColor Green
    }
}
