#!/bin/bash
set -e

echo "  MapEditor macOS 打包脚本"
echo "========================================"
echo ""

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

if [ -d "venv" ]; then
    echo "激活虚拟环境..."
    source venv/bin/activate
fi

echo "清理旧的构建文件..."
rm -rf dist build

echo "开始打包..."
pyinstaller MapEditor.mac.spec --clean

if [ ! -d "dist/MapEditor.app" ]; then
    echo "打包失败！"
    exit 1
fi

echo ""
echo "========================================"
echo "  打包完成！"
echo "========================================"
echo "输出: dist/MapEditor.app"
