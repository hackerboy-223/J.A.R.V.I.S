param(
    [switch]$SkipInstaller
)

$ErrorActionPreference = "Stop"

# Keep Windows PowerShell output readable when this UTF-8 script prints accents.
$utf8 = New-Object System.Text.UTF8Encoding($false)
[Console]::OutputEncoding = $utf8
$OutputEncoding = $utf8

$projectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $projectRoot

Write-Host "==> Build PyInstaller"
python -m PyInstaller packaging/jarvis.spec --noconfirm --clean
if ($LASTEXITCODE -ne 0) {
    throw "PyInstaller a echoue avec le code $LASTEXITCODE."
}

$distribution = Join-Path $projectRoot "dist\J.A.R.V.I.S"
$executable = Join-Path $distribution "JARVIS.exe"
if (-not (Test-Path $executable)) {
    throw "Build termine sans executable attendu : $executable"
}

$archive = Join-Path $projectRoot "dist\JARVIS-Windows-x64.zip"
if (Test-Path $archive) {
    Remove-Item $archive -Force
}
Compress-Archive -Path (Join-Path $distribution "*") -DestinationPath $archive
Write-Host "Archive portable prete : $archive"

if ($SkipInstaller) {
    Write-Host "Installateur ignore (-SkipInstaller)."
    exit 0
}

$command = Get-Command "ISCC.exe" -ErrorAction SilentlyContinue
$isccCandidates = @(
    $(if ($command) { $command.Source }),
    "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe",
    "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe",
    "$env:ProgramFiles\Inno Setup 6\ISCC.exe"
) | Where-Object { $_ -and (Test-Path $_) }

$iscc = $isccCandidates | Select-Object -First 1
if (-not $iscc) {
    throw @"
Inno Setup 6 est requis pour generer JARVIS-Setup-x64.exe.
Installe-le puis relance ce script :
  winget install --id JRSoftware.InnoSetup -e
ou :
  choco install innosetup -y
"@
}

Write-Host "==> Build installateur avec Inno Setup"
& $iscc (Join-Path $projectRoot "packaging\JARVIS.iss")
if ($LASTEXITCODE -ne 0) {
    throw "Inno Setup a echoue avec le code $LASTEXITCODE."
}

$setup = Join-Path $projectRoot "dist\JARVIS-Setup-x64.exe"
if (-not (Test-Path $setup)) {
    throw "Inno Setup s'est termine sans installateur attendu : $setup"
}

Write-Host "Installateur Windows prêt : $setup"
