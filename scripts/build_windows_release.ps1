[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)]
    [string]$Version,
    [string]$Python = "python",
    [string]$OutputDirectory = ".\dist\release"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$ScriptsDirectory = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepositoryRoot = Split-Path -Parent $ScriptsDirectory

function Assert-LastExitCode {
    param([string]$Operation)

    if ($LASTEXITCODE -ne 0) {
        throw "$Operation failed with exit code $LASTEXITCODE"
    }
}

if ([Environment]::OSVersion.Platform -ne [PlatformID]::Win32NT) {
    throw "The executable release can only be built on Windows"
}
if ($Version -notmatch '^\d+\.\d+\.\d+$') {
    throw "Version must use the major.minor.patch format"
}

Push-Location $RepositoryRoot
try {
    $RepositoryStatus = & git status --porcelain
    Assert-LastExitCode "Checking the repository status"
    if ($RepositoryStatus) {
        throw "Refusing to build a release from a dirty working tree"
    }

    $PythonVersion = (& $Python -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')").Trim()
    Assert-LastExitCode "Checking the Python version"
    if ($PythonVersion -ne "3.10") {
        throw "Building the Windows release requires Python 3.10; got $PythonVersion"
    }

    & $Python -m pytest
    Assert-LastExitCode "Running the regression suite"

    $BuildRoot = Join-Path $RepositoryRoot "build\release"
    $PyInstallerWork = Join-Path $BuildRoot "pyinstaller"
    $PyInstallerDist = Join-Path $BuildRoot "dist"
    $ReleaseName = "AI-Sign-Language-Translator-v$Version"
    $OutputPath = if ([IO.Path]::IsPathRooted($OutputDirectory)) {
        $OutputDirectory
    } else {
        Join-Path $RepositoryRoot $OutputDirectory
    }
    $ResolvedOutputDirectory = [IO.Path]::GetFullPath($OutputPath)
    $ReleaseRoot = Join-Path $ResolvedOutputDirectory $ReleaseName
    $ReleaseZip = "$ReleaseRoot-windows-x64.zip"

    foreach ($Path in @($BuildRoot, $ReleaseRoot)) {
        if (Test-Path -LiteralPath $Path) {
            Remove-Item -LiteralPath $Path -Recurse -Force
        }
    }
    if (Test-Path -LiteralPath $ReleaseZip) {
        Remove-Item -LiteralPath $ReleaseZip -Force
    }

    New-Item -ItemType Directory -Force -Path $BuildRoot, $ResolvedOutputDirectory | Out-Null
    & $Python -m PyInstaller `
        --noconfirm `
        --clean `
        --onedir `
        --windowed `
        --contents-directory . `
        --name "AI-Sign-Language-Translator" `
        --icon (Join-Path $RepositoryRoot "src\assets\ans.ico") `
        --add-data "$(Join-Path $RepositoryRoot 'src\assets');assets" `
        --add-data "$(Join-Path $RepositoryRoot 'models');models" `
        --collect-data symspellpy `
        --specpath $BuildRoot `
        --workpath $PyInstallerWork `
        --distpath $PyInstallerDist `
        (Join-Path $RepositoryRoot "src\main.py")
    Assert-LastExitCode "Building the executable"

    $ReleaseApp = Join-Path $ReleaseRoot "app"
    New-Item -ItemType Directory -Force -Path $ReleaseRoot | Out-Null
    Copy-Item -LiteralPath (Join-Path $PyInstallerDist "AI-Sign-Language-Translator") `
        -Destination $ReleaseApp -Recurse

    foreach ($Directory in @("docs", "third_party")) {
        Copy-Item -LiteralPath (Join-Path $RepositoryRoot $Directory) `
            -Destination (Join-Path $ReleaseApp $Directory) -Recurse
    }
    foreach ($File in @("README.md", "README.pl.md")) {
        Copy-Item -LiteralPath (Join-Path $RepositoryRoot $File) -Destination $ReleaseApp
    }
    foreach ($File in @("LICENSE", "LICENSE-docs", "SECURITY.md")) {
        Copy-Item -LiteralPath (Join-Path $RepositoryRoot $File) -Destination $ReleaseRoot
        Copy-Item -LiteralPath (Join-Path $RepositoryRoot $File) -Destination $ReleaseApp
    }

    # Single-file (portable) executable: everything packed into one .exe, no
    # surrounding folder required. Built separately from the onedir variant above.
    $OneFileWork = Join-Path $BuildRoot "pyinstaller-onefile"
    $OneFileDist = Join-Path $BuildRoot "dist-onefile"
    & $Python -m PyInstaller `
        --noconfirm `
        --clean `
        --onefile `
        --windowed `
        --name "AI-Sign-Language-Translator" `
        --icon (Join-Path $RepositoryRoot "src\assets\ans.ico") `
        --add-data "$(Join-Path $RepositoryRoot 'src\assets');assets" `
        --add-data "$(Join-Path $RepositoryRoot 'models');models" `
        --collect-data symspellpy `
        --specpath $BuildRoot `
        --workpath $OneFileWork `
        --distpath $OneFileDist `
        (Join-Path $RepositoryRoot "src\main.py")
    Assert-LastExitCode "Building the single-file executable"

    $OneFileExe = Join-Path $OneFileDist "AI-Sign-Language-Translator.exe"
    # Ship the single-file exe both inside the release folder/ZIP and as a
    # standalone, versioned asset next to the ZIP for direct download.
    Copy-Item -LiteralPath $OneFileExe -Destination $ReleaseRoot
    $StandaloneExe = Join-Path $ResolvedOutputDirectory "$ReleaseName-windows-x64.exe"
    Copy-Item -LiteralPath $OneFileExe -Destination $StandaloneExe

    $RunBatch = @'
@echo off
start "" "%~dp0app\AI-Sign-Language-Translator.exe"
'@
    Set-Content -LiteralPath (Join-Path $ReleaseRoot "RUN.bat") -Value $RunBatch -Encoding ascii

    $RunPowerShell = @'
& (Join-Path $PSScriptRoot "app\AI-Sign-Language-Translator.exe")
'@
    Set-Content -LiteralPath (Join-Path $ReleaseRoot "RUN.ps1") -Value $RunPowerShell -Encoding ascii

    $StartHere = @'
# AI Sign Language Translator v{0}

Two ways to run it, no Python installation required:
- Double-click `AI-Sign-Language-Translator.exe` in this folder (single portable file), or
- Run `RUN.bat` / `RUN.ps1` (uses the folder build in `app`).
A webcam is required for live recognition.

Dwa sposoby uruchomienia, bez instalacji Pythona:
- Kliknij dwukrotnie `AI-Sign-Language-Translator.exe` w tym folderze (pojedynczy przenosny plik), lub
- Uruchom `RUN.bat` / `RUN.ps1` (korzysta z wersji katalogowej w `app`).
Rozpoznawanie na zywo wymaga kamery.
'@ -f $Version
    Set-Content -LiteralPath (Join-Path $ReleaseRoot "START_HERE.md") -Value $StartHere -Encoding utf8

    $SourceCommit = (& git rev-parse HEAD).Trim()
    Assert-LastExitCode "Reading the source revision"
    $BuildTime = [DateTime]::UtcNow.ToString("yyyy-MM-ddTHH:mm:ssZ")
    $BuildInfo = @"
Version: $Version
Platform: Windows x64
Source commit: $SourceCommit
Python: $(& $Python --version 2>&1)
Built (UTC): $BuildTime
Tests: passed before build
"@
    Set-Content -LiteralPath (Join-Path $ReleaseRoot "BUILD_INFO.txt") -Value $BuildInfo -Encoding ascii

    Compress-Archive -LiteralPath $ReleaseRoot -DestinationPath $ReleaseZip -CompressionLevel Optimal
    Write-Host "Created release folder/ZIP: $ReleaseZip"
    Write-Host "Created single-file executable: $StandaloneExe"
}
finally {
    Pop-Location
}
