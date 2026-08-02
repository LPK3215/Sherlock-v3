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
    $runnerArgs = if ($args.Count -eq 0) { @("--port", "7870") } else { $args }
    # The safe client working directory prevents NLTK from importing project-local
    # packages as third-party dependencies while keeping server modules importable.
    & $python $bot @runnerArgs
    if ($LASTEXITCODE -ne 0) {
        exit $LASTEXITCODE
    }
}
finally {
    Pop-Location
}
