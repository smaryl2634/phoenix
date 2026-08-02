#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SOURCE_DIR="$SCRIPT_DIR/phoenix_v7"
HERMES_DIR="$HOME/.hermes"
PLUGINS_DIR="$HERMES_DIR/plugins"
TARGET_DIR="$PLUGINS_DIR/phoenix_v7"

echo "不死鸟 Phoenix 安装脚本"
echo "========================"

if [ ! -d "$HERMES_DIR" ]; then
  echo "❌ 没有检测到 Hermes Agent（找不到 $HERMES_DIR）"
  echo "   请先安装 Hermes Agent，再运行本脚本。"
  exit 1
fi

if [ ! -d "$SOURCE_DIR" ]; then
  echo "❌ 找不到 phoenix_v7 目录，请确认是在解压后的完整文件夹里运行本脚本。"
  exit 1
fi

mkdir -p "$PLUGINS_DIR"

if [ -d "$TARGET_DIR" ]; then
  BACKUP_DIR="${TARGET_DIR}.backup.$(date +%Y%m%d%H%M%S)"
  echo "⚠️  检测到已安装的旧版本，备份到：$BACKUP_DIR"
  mv "$TARGET_DIR" "$BACKUP_DIR"
fi

echo "📦 安装到 $TARGET_DIR ..."
cp -R "$SOURCE_DIR" "$TARGET_DIR"

# 安装产生的本地状态/缓存目录不需要带过去
rm -rf "$TARGET_DIR/__pycache__" "$TARGET_DIR/.pytest_cache" "$TARGET_DIR/venv" "$TARGET_DIR/state"/*.json 2>/dev/null || true

echo "✅ 文件复制完成"
echo ""
echo "🔍 校验安装结果："
echo "------------------------"

if command -v hermes >/dev/null 2>&1; then
  hermes phoenix-status || {
    echo ""
    echo "⚠️  hermes phoenix-status 执行失败，请检查上面的报错信息。"
    exit 1
  }
else
  echo "⚠️  找不到 hermes 命令，无法自动校验。请手动运行：hermes phoenix-status"
fi

echo ""
echo "安装完成。"
