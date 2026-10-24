$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $projectRoot
if (-not (Test-Path -LiteralPath '.venv/Scripts/python.exe')) {
    throw 'Run the setup steps in README.md first.'
}
if (-not (Test-Path -LiteralPath 'data/sample.db')) {
    & ./.venv/Scripts/python.exe data/seed.py
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}
if (-not (Test-Path -LiteralPath 'frontend/dist/index.html')) {
    Push-Location frontend
    npm run build
    Pop-Location
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}
Write-Host 'Querycraft is starting at http://localhost:8000'
& ./.venv/Scripts/python.exe -m scripts.serve
