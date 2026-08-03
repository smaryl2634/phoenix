#Requires -Version 5.0
$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$SourceDir = Join-Path $ScriptDir "phoenix_v7"
if ($env:HERMES_HOME) {
    $HermesDir = $env:HERMES_HOME
} elseif ($env:LOCALAPPDATA) {
    $HermesDir = Join-Path $env:LOCALAPPDATA "hermes"
} else {
    $HermesDir = Join-Path $HOME "AppData\Local\hermes"
}
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

$NewStateDir = Join-Path $HermesDir "phoenix_v7_state"

if (Test-Path $TargetDir) {
    $OldStateDir = Join-Path $TargetDir "state"
    if (Test-Path $OldStateDir) {
        Write-Host "`u{1F4E6} 检测到旧版本的 state 数据，迁移到新位置：$NewStateDir"
        New-Item -ItemType Directory -Force -Path $NewStateDir | Out-Null
        Get-ChildItem $OldStateDir | ForEach-Object {
            $dest = Join-Path $NewStateDir $_.Name
            if (-not (Test-Path $dest)) {
                Copy-Item $_.FullName $dest -Recurse
            }
        }
    }
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

Write-Host "`u2705 文件复制完成"
Write-Host ""

$hermesCmd = Get-Command hermes -ErrorAction SilentlyContinue
if ($hermesCmd) {
    Write-Host "`u{1F50C} 启用插件："
    Write-Host "------------------------"
    # Hermes 要求用户安装的插件显式启用才会真正加载——只把文件复制到
    # plugins/ 目录不够，第一次装的用户之前从未启用过 phoenix_v7，不调这一步
    # 的话下面的 phoenix-status 校验必然失败（命令根本不存在），会被误报成
    # "安装失败"。已装过旧版本再次运行本脚本时这一步是幂等的。老版本 Hermes
    # 没有这个子命令时，不阻断安装，只提示用户自己手动启用。
    hermes plugins enable phoenix_v7 --no-allow-tool-override
    if ($LASTEXITCODE -ne 0) {
        Write-Host "`u26A0`uFE0F  自动启用失败（可能是较旧版本的 Hermes 没有这个子命令），"
        Write-Host "   请手动运行：hermes plugins enable phoenix_v7"
    }
    Write-Host ""
    Write-Host "`u{1F50D} 校验安装结果："
    Write-Host "------------------------"
    hermes phoenix-status
    if ($LASTEXITCODE -ne 0) {
        Write-Host ""
        Write-Host "`u26A0`uFE0F  hermes phoenix-status 执行失败，请检查上面的报错信息。"
        exit 1
    }
} else {
    Write-Host "`u26A0`uFE0F  找不到 hermes 命令，无法自动启用/校验。请手动运行："
    Write-Host "   hermes plugins enable phoenix_v7"
    Write-Host "   hermes phoenix-status"
}

Write-Host ""
Write-Host "安装完成。"
Write-Host ""
Write-Host "`u{1F4D6} 不死鸟怎么用："
Write-Host "------------------------"
Write-Host "装完不用学新命令，正常用 Hermes 就行，下面这些是不死鸟自动生效/可选用的部分："
Write-Host ""
Write-Host "  hermes phoenix-status       随时查看当前状态（路由/熔断/花费/抗体库/兜底链）"
Write-Host "  hermes phoenix-router on/off  开关自动路由换模型（默认关，只判断档位不切模型，"
Write-Host "                              需要自己配置好档位对应的模型后再开启）"
Write-Host "  /goal 你的任务描述           长任务模式，Hermes 原生命令，不死鸟自动接管清单强制"
Write-Host "                              + 高危操作换模型复核"
Write-Host ""
Write-Host "  以下完全自动，不需要手动开启："
Write-Host "    - 熔断保护：连续报错自动跳闸，冷却后自动恢复"
Write-Host "    - 高危回复核验：深度/真神档位回复自动交叉核验，通道故障自动降级放行"
Write-Host "    - 隐私提醒/本地模型：仅 macOS 支持，Windows 上不会看到这条提醒，属于正常现象"
Write-Host "    - 欠费兜底：主力模型不可用时，如果你在 Hermes 配置了 fallback_model，会"
Write-Host "      自动尝试；没配置也完全没问题，不是必须项"
Write-Host ""
Write-Host "  完整文档在 phoenix_v7/docs/ 目录，遇到问题也可以直接问 Hermes 里的 AI。"
