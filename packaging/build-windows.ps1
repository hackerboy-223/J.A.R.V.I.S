param(
    [switch]$SkipInstaller,
    [switch]$SkipTests
)

$ErrorActionPreference = "Stop"

$utf8 = New-Object System.Text.UTF8Encoding($false)
[Console]::OutputEncoding = $utf8
$OutputEncoding = $utf8

$projectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $projectRoot

function Invoke-Python {
    param([Parameter(ValueFromRemainingArguments = $true)][string[]]$Args)
    & python @Args
    if ($LASTEXITCODE -ne 0) {
        throw "Python command failed ($LASTEXITCODE): python $($Args -join ' ')"
    }
}

function Invoke-PackagedCheck {
    param(
        [string]$Executable,
        [string]$CommandName
    )
    $process = Start-Process -FilePath $Executable -ArgumentList @($CommandName) -Wait -PassThru
    if ($process.ExitCode -ne 0) {
        throw "Packaged JARVIS check '$CommandName' failed with code $($process.ExitCode)."
    }
}

function Write-Checksums {
    param(
        [string[]]$Files,
        [string]$Destination
    )
    $lines = foreach ($file in $Files) {
        if (-not (Test-Path $file)) { continue }
        $hash = (Get-FileHash -Path $file -Algorithm SHA256).Hash.ToLowerInvariant()
        "$hash  $([System.IO.Path]::GetFileName($file))"
    }
    [System.IO.File]::WriteAllLines($Destination, [string[]]$lines, [System.Text.Encoding]::ASCII)
}

$version = (& python -c "import tomllib; print(tomllib.load(open('pyproject.toml','rb'))['project']['version'])").Trim()
if ($LASTEXITCODE -ne 0 -or -not $version) {
    throw "Unable to read JARVIS version from pyproject.toml."
}
if ($version -notmatch '^\d+\.\d+\.\d+$') {
    throw "Invalid JARVIS version: $version"
}

Write-Host "==> J.A.R.V.I.S. $version Windows build"

if (-not $SkipTests) {
    Write-Host "==> Source validation"
    Invoke-Python -Args @("-m", "compileall", "-q", "jarvis", "tests")
    Invoke-Python -Args @("-m", "unittest", "discover", "-s", "tests", "-v")
    Invoke-Python -Args @("-m", "jarvis", "selftest")
}

Write-Host "==> PyInstaller"
Invoke-Python -Args @("-m", "PyInstaller", "packaging/jarvis.spec", "--noconfirm", "--clean")

$distribution = Join-Path $projectRoot "dist\J.A.R.V.I.S"
$executable = Join-Path $distribution "JARVIS.exe"
if (-not (Test-Path $executable)) {
    throw "Build completed without expected executable: $executable"
}

Write-Host "==> Packaged runtime smoke tests"
Invoke-PackagedCheck -Executable $executable -CommandName "package-doctor"
Invoke-PackagedCheck -Executable $executable -CommandName "selftest"

$commit = "unknown"
try {
    $commit = (& git rev-parse HEAD).Trim()
} catch {
    $commit = "unknown"
}
$pythonVersion = (& python --version 2>&1 | Out-String).Trim()
$buildInfo = [ordered]@{
    product = "J.A.R.V.I.S."
    version = $version
    commit = $commit
    python = $pythonVersion
    built_at_utc = [DateTime]::UtcNow.ToString("o")
    architecture = $env:PROCESSOR_ARCHITECTURE
}
$buildInfo | ConvertTo-Json | Set-Content -Path (Join-Path $distribution "BUILD-INFO.json") -Encoding UTF8

$archive = Join-Path $projectRoot "dist\JARVIS-Windows-x64.zip"
if (Test-Path $archive) { Remove-Item $archive -Force }
Compress-Archive -Path (Join-Path $distribution "*") -DestinationPath $archive
Write-Host "Portable archive ready: $archive"

$checksum = Join-Path $projectRoot "dist\SHA256SUMS.txt"

if ($SkipInstaller) {
    Write-Checksums -Files @($archive) -Destination $checksum
    Write-Host "Checksums ready: $checksum"
    Write-Host "Installer skipped (-SkipInstaller)."
    exit 0
}

$command = Get-Command "ISCC.exe" -ErrorAction SilentlyContinue
$isccCandidates = @(
    $(if ($command) { $command.Source }),
    "$env:LOCALAPPDATA\Programs\Inno Setup 7\ISCC.exe",
    "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe",
    "${env:ProgramFiles(x86)}\Inno Setup 7\ISCC.exe",
    "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe",
    "$env:ProgramFiles\Inno Setup 7\ISCC.exe",
    "$env:ProgramFiles\Inno Setup 6\ISCC.exe"
) | Where-Object { $_ -and (Test-Path $_) }

$iscc = $isccCandidates | Select-Object -First 1
if (-not $iscc) {
    throw "Inno Setup is required. Install with: winget install --id JRSoftware.InnoSetup -e"
}

Write-Host "==> Inno Setup"
$defineVersion = '-dMyAppVersion="' + $version + '"'
& $iscc $defineVersion (Join-Path $projectRoot "packaging\JARVIS.iss")
if ($LASTEXITCODE -ne 0) {
    throw "Inno Setup failed with code $LASTEXITCODE."
}

$setup = Join-Path $projectRoot "dist\JARVIS-Setup-x64.exe"
if (-not (Test-Path $setup)) {
    throw "Inno Setup completed without expected installer: $setup"
}

Write-Checksums -Files @($setup, $archive) -Destination $checksum
Write-Host "Installer ready: $setup"
Write-Host "Checksums ready: $checksum"
Write-Host "==> J.A.R.V.I.S. $version build completed successfully"
