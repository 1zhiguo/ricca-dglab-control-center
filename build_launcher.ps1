$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$Source = Join-Path $ProjectRoot "launcher\RiccaLauncher.cs"
$Output = Join-Path $ProjectRoot "Ricca-x-DGlab.exe"
$Icon = Join-Path $ProjectRoot "launcher\ricca-app.ico"
$Compiler = "$env:WINDIR\Microsoft.NET\Framework64\v4.0.30319\csc.exe"

if (Test-Path -LiteralPath $Output) {
    Remove-Item -LiteralPath $Output -Force
}

if (-not (Test-Path -LiteralPath $Compiler)) {
    throw "未找到 Windows C# 编译器：$Compiler"
}

& $Compiler /nologo /target:winexe "/out:$Output" "/win32icon:$Icon" `
    /reference:System.dll /reference:System.Core.dll /reference:System.Windows.Forms.dll `
    $Source
if ($LASTEXITCODE -ne 0 -or -not (Test-Path -LiteralPath $Output)) {
    throw "启动器编译失败，退出代码：$LASTEXITCODE"
}

Write-Host "Launcher created: $Output"
