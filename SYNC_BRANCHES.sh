#!/bin/bash

# 同步 ptero 和 develop 分支腳本
# 在完成 main 分支更新後執行

set -e  # 遇到錯誤立即停止

echo "=========================================="
echo "🔄 開始同步分支..."
echo "=========================================="
echo ""

# 步驟 1: 獲取最新遠端狀態
echo "📥 1. 獲取最新遠端狀態..."
git fetch origin --prune
echo "✅ 完成"
echo ""

# 步驟 2: 同步 ptero 部署分支
echo "🚀 2. 同步 ptero 部署分支..."
git checkout ptero
git pull origin ptero
echo "📊 ptero 分支目前狀態:"
git log --oneline -3

echo ""
echo "🔀 合併 main 到 ptero..."
git merge origin/main --no-ff -m "🔄 同步 main 分支的清理更新

從 main 分支同步以下更新：
- 大規模清理：移除 AI、Minecraft 和 Web API 功能
- 添加分支合併操作文檔
- 刪除 .github/workflows 目錄

保持 ptero 部署分支與生產環境同步。
"

echo "📤 推送到遠端..."
git push origin ptero
echo "✅ ptero 分支同步完成"
echo ""

# 步驟 3: 重置 develop 分支
echo "🔄 3. 重置 develop 分支..."
git checkout develop
git pull origin develop

echo "⚠️  即將強制重置 develop 到 main 的狀態"
echo "📊 develop 目前的 commits (即將被重置):"
git log origin/main..develop --oneline || echo "(develop 與 main 已同步)"

echo ""
read -p "確認要繼續嗎？(y/N) " -n 1 -r
echo ""

if [[ $REPLY =~ ^[Yy]$ ]]
then
    # 創建備份標籤
    BACKUP_TAG="backup/develop-$(date +%Y%m%d-%H%M%S)"
    echo "💾 創建備份標籤: $BACKUP_TAG"
    git tag $BACKUP_TAG
    git push origin $BACKUP_TAG

    echo "🔨 強制重置 develop 到 main..."
    git reset --hard origin/main

    echo "📤 強制推送到遠端..."
    git push origin develop --force-with-lease

    echo "✅ develop 分支重置完成"
else
    echo "❌ 取消 develop 分支重置"
    exit 1
fi
echo ""

# 步驟 4: 清理廢棄的遠端分支
echo "🧹 4. 清理廢棄的遠端分支..."
echo "即將刪除以下分支:"
echo "  - dev"
echo "  - feature/cleanup-develop-branch"
echo "  - claude/repo-analysis-011CUyTkJC1NGJkdBmFA7zsN"
echo ""
read -p "確認要刪除這些分支嗎？(y/N) " -n 1 -r
echo ""

if [[ $REPLY =~ ^[Yy]$ ]]
then
    echo "🗑️  刪除 dev..."
    git push origin --delete dev 2>/dev/null || echo "  (分支不存在或已刪除)"

    echo "🗑️  刪除 feature/cleanup-develop-branch..."
    git push origin --delete feature/cleanup-develop-branch 2>/dev/null || echo "  (分支不存在或已刪除)"

    echo "🗑️  刪除 claude/repo-analysis-011CUyTkJC1NGJkdBmFA7zsN..."
    git push origin --delete claude/repo-analysis-011CUyTkJC1NGJkdBmFA7zsN 2>/dev/null || echo "  (分支不存在或已刪除)"

    echo "✅ 廢棄分支清理完成"
else
    echo "❌ 取消分支清理"
fi
echo ""

# 步驟 5: 清理本地引用
echo "🧹 5. 清理本地引用..."
git fetch origin --prune
echo "✅ 完成"
echo ""

# 步驟 6: 驗證最終結構
echo "=========================================="
echo "✅ 驗證最終分支結構"
echo "=========================================="
echo ""

echo "📋 遠端分支列表:"
git branch -r | grep -v "HEAD"
echo ""

echo "📊 各分支最新 commit:"
echo ""
echo "main:"
git log origin/main --oneline -1
echo ""
echo "develop:"
git log origin/develop --oneline -1
echo ""
echo "ptero:"
git log origin/ptero --oneline -1
echo ""

echo "🔍 檢查 develop 和 main 是否同步:"
DIFF_COUNT=$(git rev-list --count origin/main..origin/develop)
if [ "$DIFF_COUNT" -eq 0 ]; then
    echo "✅ develop 和 main 已完全同步"
else
    echo "⚠️  develop 領先 main $DIFF_COUNT 個 commits"
fi
echo ""

echo "=========================================="
echo "🎉 所有操作完成！"
echo "=========================================="
echo ""
echo "📝 後續步驟:"
echo "1. 更新本地依賴: pip install -r requirements.txt"
echo "2. 更新 .env 檔案（參考 .env.example）"
echo "3. 測試 Bot 啟動: python -m potato_bot.main"
echo "4. 重啟生產環境（如果需要）"
echo ""
