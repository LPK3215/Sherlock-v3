$ErrorActionPreference = "Stop"

$python = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
$bot = Join-Path $PSScriptRoot "bot.py"
$safeWorkingDirectory = Join-Path $PSScriptRoot "..\client"

if (-not (Test-Path -LiteralPath $python)) {
    throw "Python environment not found. Run 'uv sync' in the server directory first."
}

$env:PYTHONUTF8 = "1"
$env:PYTHONIOENCODING = "utf-8"

Push-Location -LiteralPath $safeWorkingDirectory
try {
    & $python -P $bot @args
    if ($LASTEXITCODE -ne 0) {
        exit $LASTEXITCODE
    }
}
finally {
    Pop-Location
}
