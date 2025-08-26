#!/bin/bash
# 託管環境依賴安裝腳本

echo "📦 開始安裝 Potato Bot 依賴..."

# 檢查 Python 版本
echo "🐍 檢查 Python 版本..."
python3 --version

# 更新 pip
echo "🔧 更新 pip..."
python3 -m pip install --upgrade pip

# 安裝主要依賴
echo "📋 安裝主要依賴..."
if [ -f "requirements.txt" ]; then
    echo "✅ 找到 requirements.txt，開始安裝..."
    python3 -m pip install -r requirements.txt
elif [ -f "docs/requirements/requirements-production.txt" ]; then
    echo "✅ 找到生產環境依賴列表，開始安裝..."
    python3 -m pip install -r docs/requirements/requirements-production.txt
else
    echo "❌ 未找到依賴列表文件"
    exit 1
fi

# 檢查關鍵模組
echo "🔍 檢查關鍵模組..."
python3 -c "
import sys
modules = [
    'discord', 'fastapi', 'uvicorn', 'aiofiles', 'aioredis', 
    'aiomysql', 'requests', 'aiohttp', 'pandas', 'pillow'
]

missing = []
for module in modules:
    try:
        __import__(module.replace('-', '_'))
        print(f'✅ {module}')
    except ImportError:
        print(f'❌ {module} - 缺失')
        missing.append(module)

if missing:
    print(f'\\n⚠️ 缺失模組: {missing}')
    print('請手動安裝: python3 -m pip install ' + ' '.join(missing))
else:
    print('\\n🎉 所有關鍵模組都已安裝')
"

echo "✅ 依賴安裝完成"