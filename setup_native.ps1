$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$Venv = Join-Path $ProjectRoot ".venv"

if (-not (Test-Path -LiteralPath $Venv)) {
    py -3.11 -m venv $Venv
}

$Python = Join-Path $Venv "Scripts\python.exe"
& $Python -m pip install --upgrade pip
& $Python -m pip install -r (Join-Path $ProjectRoot "requirements-native.txt")
Write-Host "环境已就绪。运行 .\run_native.ps1 启动。"
