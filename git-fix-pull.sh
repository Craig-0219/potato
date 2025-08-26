#!/bin/bash
# Git Pull 修復腳本 - 託管環境使用

echo "🔧 修復 Git pull 分歧問題..."

# 設定 Git 配置
git config pull.rebase false
git config user.name "Potato Bot Deploy" 
git config user.email "deploy@potato-bot.com"

echo "✅ Git 配置完成"

# 執行 pull
echo "📥 嘗試 pull 最新代碼..."
if git pull origin dev; then
    echo "✅ Pull 成功完成"
else
    echo "❌ Pull 失敗，嘗試強制同步..."
    git fetch origin
    git reset --hard origin/dev
    echo "✅ 強制同步完成"
fi

echo "🎉 Git 修復完成"