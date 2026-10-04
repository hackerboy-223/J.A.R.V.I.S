$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $projectRoot

python -m PyInstaller packaging/jarvis.spec --noconfirm --clean

$distribution = Join-Path $projectRoot "dist\J.A.R.V.I.S"
$executable = Join-Path $distribution "JARVIS.exe"
if (-not (Test-Path $executable)) {
    throw "Build terminée sans exécutable attendu : $executable"
}

$archive = Join-Path $projectRoot "dist\JARVIS-Windows-x64.zip"
if (Test-Path $archive) {
    Remove-Item $archive -Force
}
Compress-Archive -Path (Join-Path $distribution "*") -DestinationPath $archive
Write-Host "Build Windows prête : $archive"

# Optional installer build with Inno Setup.
$isccCandidates = @(
    "$env:ProgramFiles(x86)\Inno Setup 6\ISCC.exe",
    "$env:ProgramFiles\Inno Setup 6\ISCC.exe"
)
$iscc = $isccCandidates | Where-Object { Test-Path $_ } | Select-Object -First 1
if ($iscc) {
    & $iscc (Join-Path $projectRoot "packaging\JARVIS.iss")
    Write-Host "Installateur Inno Setup généré."
} else {
    Write-Host "Inno Setup non détecté : archive ZIP générée, installateur ignoré."
}
