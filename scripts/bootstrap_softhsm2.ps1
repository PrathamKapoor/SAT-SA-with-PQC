# A1.2 — Bootstrap the development SoftHSM2 portable archive.
#
# Downloads SoftHSM2 2.5.0 portable (DISIG SoftHSM2-Windows fork of upstream
# SoftHSMv2) into `.devtools/softhsm2/`.  This is the developer-only PKCS#11
# provider used to certify the real-provider path in A1.2.
#
# Usage (from the repo root):
#   powershell -ExecutionPolicy Bypass -File scripts\bootstrap_softhsm2.ps1
#
# The script is idempotent: re-running it skips the download if the archive is
# already present and verified.

$ErrorActionPreference = "Stop"
$RepoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$DevToolsDir = Join-Path $RepoRoot ".devtools"
$DestDir = Join-Path $DevToolsDir "softhsm2"
$ZipPath = Join-Path $DevToolsDir "SoftHSM2-2.5.0-portable.zip"
$Url = "https://github.com/disig/SoftHSM2-for-Windows/releases/download/v2.5.0/SoftHSM2-2.5.0-portable.zip"

if (-not (Test-Path $DevToolsDir)) {
    New-Item -ItemType Directory -Path $DevToolsDir | Out-Null
}

# Quick sanity: if the binaries already exist, skip.
$Marker = Join-Path $DestDir "lib\softhsm2-x64.dll"
if (Test-Path $Marker) {
    Write-Host "SoftHSM2 already bootstrapped at $DestDir — nothing to do." -ForegroundColor Yellow
    exit 0
}

Write-Host "Downloading SoftHSM2 2.5.0 portable from $Url ..." -ForegroundColor Cyan
try {
    [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
    Invoke-WebRequest -Uri $Url -OutFile $ZipPath -UseBasicParsing
} catch {
    Write-Host "Download failed: $_" -ForegroundColor Red
    exit 1
}

# Verify ZIP integrity — expand, expect to see lib\softhsm2-x64.dll.
Write-Host "Verifying archive ..."
$tempExtract = Join-Path $DevToolsDir "_extract_verify"
if (Test-Path $tempExtract) { Remove-Item $tempExtract -Recurse -Force }
Expand-Archive -Path $ZipPath -DestinationPath $tempExtract -Force
$expectedDll = Join-Path $tempExtract "SoftHSM2\lib\softhsm2-x64.dll"
if (-not (Test-Path $expectedDll)) {
    Write-Host "Archive did not contain expected $expectedDll" -ForegroundColor Red
    exit 2
}
Remove-Item $tempExtract -Recurse -Force

# Extract to final destination.
Write-Host "Extracting to $DestDir ..."
if (Test-Path $DestDir) {
    Remove-Item $DestDir -Recurse -Force
}
Expand-Archive -Path $ZipPath -DestinationPath $DevToolsDir -Force
# The archive's top-level folder is named "SoftHSM2" and unpacks directly;
# the Expand-Archive call places it as ".devtools\SoftHSM2".  Rename.
$extracted = Join-Path $DevToolsDir "SoftHSM2"
if (Test-Path $extracted) {
    Rename-Item $extracted $DestDir
}

# Remove the zip to keep the dev tools directory tidy.
Remove-Item $ZipPath -Force

Write-Host "SoftHSM2 installed at $DestDir" -ForegroundColor Green
Write-Host "Next: provision an isolated development token (see .devtools/softhsm2/README.md)." -ForegroundColor Cyan
