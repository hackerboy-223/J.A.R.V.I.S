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

$innoCandidates = @(
    "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe",
    "$env:ProgramFiles(x86)\Inno Setup 6\ISCC.exe",
    "$env:ProgramFiles\Inno Setup 6\ISCC.exe"
)
$iscc = $innoCandidates | Where-Object { $_ -and (Test-Path $_) } | Select-Object -First 1

if ($iscc) {
    Write-Host "Inno Setup détecté : $iscc"
    & $iscc "packaging\jarvis.iss"
    $installer = Join-Path $projectRoot "dist\JARVIS-Setup-x64.exe"
    if (Test-Path $installer) {
        Write-Host "Installateur Windows prêt : $installer"
    } else {
        throw "Inno Setup s'est terminé sans installateur attendu : $installer"
    }
} else {
    Write-Host "Inno Setup non détecté : archive ZIP créée, installateur .exe ignoré."
}