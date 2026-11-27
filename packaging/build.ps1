# Baut InputForge unter Windows als portablen Ordner + ZIP.
#
#   powershell -ExecutionPolicy Bypass -File packaging\build.ps1 [-OneFile] [-Admin]
param(
    [switch]$OneFile,
    [switch]$Admin
)
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

if (-not (Test-Path .venv)) {
    py -3.12 -m venv .venv
}
& .venv\Scripts\python.exe -m pip install --upgrade pip | Out-Null
& .venv\Scripts\python.exe -m pip install -e ".[dev]"

& .venv\Scripts\python.exe -m pytest -q
if ($LASTEXITCODE -ne 0) { throw "Tests fehlgeschlagen" }

$env:INPUTFORGE_ONEFILE = if ($OneFile) { "1" } else { "0" }
$env:INPUTFORGE_UAC_ADMIN = if ($Admin) { "1" } else { "0" }
& .venv\Scripts\pyinstaller.exe packaging\inputforge.spec --noconfirm --clean
if ($LASTEXITCODE -ne 0) { throw "PyInstaller fehlgeschlagen" }

$Version = & .venv\Scripts\python.exe -c "import inputforge; print(inputforge.__version__)"
if (-not $OneFile) {
    $Zip = "dist\InputForge-$Version-win64.zip"
    if (Test-Path $Zip) { Remove-Item $Zip }
    Compress-Archive -Path "dist\InputForge-$Version" -DestinationPath $Zip
    Write-Host "Fertig: $Zip"
} else {
    Write-Host "Fertig: dist\InputForge.exe"
}
