#Requires -Version 5.0
$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$SourceDir = Join-Path $ScriptDir "phoenix_v7"
$HermesDir = Join-Path $HOME ".hermes"
$PluginsDir = Join-Path $HermesDir "plugins"
$TargetDir = Join-Path $PluginsDir "phoenix_v7"

Write-Host "不死鸟 Phoenix 安装脚本"
Write-Host "========================"

if (-not (Test-Path $HermesDir)) {
    Write-Host "`u274C 没有检测到 Hermes Agent（找不到 $HermesDir）"
    Write-Host "   请先安装 Hermes Agent，再运行本脚本。"
    exit 1
}

if (-not (Test-Path $SourceDir)) {
    Write-Host "`u274C 找不到 phoenix_v7 目录，请确认是在解压后的完整文件夹里运行本脚本。"
    exit 1
}

New-Item -ItemType Directory -Force -Path $PluginsDir | Out-Null

if (Test-Path $TargetDir) {
    $BackupDir = "$TargetDir.backup.$(Get-Date -Format 'yyyyMMddHHmmss')"
    Write-Host "`u26A0`uFE0F  检测到已安装的旧版本，备份到：$BackupDir"
    Move-Item $TargetDir $BackupDir
}

Write-Host "`u{1F4E6} 安装到 $TargetDir ..."
Copy-Item -Path $SourceDir -Destination $TargetDir -Recurse

foreach ($junk in @("__pycache__", ".pytest_cache", "venv")) {
    $junkPath = Join-Path $TargetDir $junk
    if (Test-Path $junkPath) { Remove-Item $junkPath -Recurse -Force }
}
$stateDir = Join-Path $TargetDir "state"
if (Test-Path $stateDir) { Get-ChildItem $stateDir -Filter "*.json" | Remove-Item -Force }

Write-Host "`u2705 文件复制完成"
Write-Host ""
Write-Host "`u{1F50D} 校验安装结果："
Write-Host "------------------------"

$hermesCmd = Get-Command hermes -ErrorAction SilentlyContinue
if ($hermesCmd) {
    hermes phoenix-status
    if ($LASTEXITCODE -ne 0) {
        Write-Host ""
        Write-Host "`u26A0`uFE0F  hermes phoenix-status 执行失败，请检查上面的报错信息。"
        exit 1
    }
} else {
    Write-Host "`u26A0`uFE0F  找不到 hermes 命令，无法自动校验。请手动运行：hermes phoenix-status"
}

Write-Host ""
Write-Host "安装完成。"
