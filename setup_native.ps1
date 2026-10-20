$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$Venv = Join-Path $ProjectRoot ".venv"

if (-not (Test-Path -LiteralPath $Venv)) {
    py -3.11 -m venv $Venv
    if ($LASTEXITCODE -ne 0) { throw "Python 3.11 环境创建失败" }
}

$Python = Join-Path $Venv "Scripts\python.exe"
& $Python -m pip install --upgrade pip
if ($LASTEXITCODE -ne 0) { throw "pip 更新失败" }
& $Python -m pip install -r (Join-Path $ProjectRoot "requirements-native.txt")
if ($LASTEXITCODE -ne 0) { throw "依赖安装失败，运行环境未就绪" }
Write-Host "环境已就绪。运行 .\run_native.ps1 启动。"
