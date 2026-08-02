# web-bot-official Cascade 启动脚本

$env:NLTK_DISABLE_IMPORT_SECURITY = "1"
$env:PYTHONSAFEPATH = "1"
$env:PYTHONIOENCODING = "utf-8"
$env:PYTHONUTF8 = "1"
$env:PYTHONPATH = $PSScriptRoot

[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
[Console]::InputEncoding = [System.Text.Encoding]::UTF8

Push-Location $PSScriptRoot
try {
    Write-Host "=== web-bot-official (cascade mode) ===" -ForegroundColor Cyan
    Write-Host "Python: $( & .venv\Scripts\python.exe --version )" -ForegroundColor Green
    & .venv\Scripts\python.exe -u bot.py --transport webrtc
} finally {
    Pop-Location
}
