#!/bin/bash
# 託管環境快速修復腳本

echo "🚀 Potato Bot 託管環境快速修復工具"
echo "===================================="

# 1. Git 修復
echo "🔧 1. 修復 Git 問題..."
if [ -f "git-fix-pull.sh" ]; then
    bash git-fix-pull.sh
else
    echo "⚠️ git-fix-pull.sh 不存在，跳過 Git 修復"
fi

# 2. 環境檢查
echo ""
echo "🔍 2. 環境檢查..."
if [ -f "check-env.py" ]; then
    python3 check-env.py
else
    echo "⚠️ check-env.py 不存在，跳過環境檢查"
fi

# 3. 依賴安裝
echo ""
echo "📦 3. 安裝缺失依賴..."

# 直接安裝最常缺失的依賴
echo "安裝關鍵依賴..."
python3 -m pip install aiofiles==23.2.0
python3 -m pip install python-jose[cryptography]==3.3.0
python3 -m pip install websockets==12.0

# 嘗試安裝完整依賴
if [ -f "requirements.txt" ]; then
    echo "安裝完整依賴..."
    python3 -m pip install -r requirements.txt
fi

# 4. 配置檢查
echo ""
echo "⚙️ 4. 配置檢查..."
if [ ! -f ".env" ]; then
    if [ -f ".env.example" ]; then
        echo "⚠️ 缺少 .env 文件，請參考 .env.example 創建"
    else
        echo "⚠️ 缺少 .env 和 .env.example 文件"
    fi
else
    echo "✅ .env 文件存在"
fi

# 5. 最終測試
echo ""
echo "🧪 5. 模組導入測試..."
python3 -c "
import sys
import os
sys.path.insert(0, '.')

test_modules = [
    ('aiofiles', 'aiofiles'),
    ('jose.jwt', 'python-jose'),
    ('shared.local_cache_manager', 'shared模組'),
    ('bot.services.local_api_server', 'local_api_server')
]

print('模組測試結果:')
all_good = True
for module, name in test_modules:
    try:
        __import__(module)
        print(f'✅ {name}')
    except ImportError as e:
        print(f'❌ {name}: {e}')
        all_good = False

if all_good:
    print('\\n🎉 所有關鍵模組可用！可以嘗試啟動機器人。')
else:
    print('\\n⚠️ 部分模組仍有問題，請檢查錯誤訊息。')
"

echo ""
echo "✅ 快速修復完成"
echo "📋 接下來可以嘗試啟動機器人: python3 bot/main.py"