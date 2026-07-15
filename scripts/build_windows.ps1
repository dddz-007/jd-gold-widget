Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location -LiteralPath $projectRoot

$python = "python"
$guiAppName = "JDGoldWidget"
$cliAppName = "JDGoldWidgetCli"

Write-Host "Building $guiAppName and $cliAppName from $projectRoot"

if (Test-Path -LiteralPath ".\build") {
    Remove-Item -LiteralPath ".\build" -Recurse -Force
}

if (Test-Path -LiteralPath ".\dist") {
    Remove-Item -LiteralPath ".\dist" -Recurse -Force
}

& $python -m PyInstaller `
    --noconfirm `
    --clean `
    --onefile `
    --windowed `
    --name $guiAppName `
    .\gold_widget.pyw

& $python -m PyInstaller `
    --noconfirm `
    --clean `
    --onefile `
    --console `
    --name $cliAppName `
    .\gold_widget_cli.py

Write-Host ""
Write-Host "Build complete:"
Write-Host "  $projectRoot\dist\$guiAppName.exe"
Write-Host "  $projectRoot\dist\$cliAppName.exe"
