$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$LocalPython = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
$ReferencePython = $env:RICCA_DEV_PYTHON

if (Test-Path -LiteralPath $LocalPython) {
    $Python = $LocalPython
} elseif ($ReferencePython -and (Test-Path -LiteralPath $ReferencePython)) {
    $Python = $ReferencePython
} else {
    throw "未找到带 PySide6 的 Python。请先运行 setup_native.ps1。"
}

$env:PYTHONPATH = Join-Path $ProjectRoot "src"
& $Python -m ricca_dglab.app @args
