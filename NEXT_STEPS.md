# 🚀 接下來的步驟

## ✅ 已完成
- 刪除 47 個檔案（AI、Minecraft、Web API）
- 更新 5 個配置檔案
- 移除 17,350+ 行程式碼
- 清理分支已推送到遠端: `claude/repo-analysis-011CUyTkJC1NGJkdBmFA7zsN`

---

## 📝 您需要做的操作

由於技術限制，我無法直接推送到 `main` 分支。請選擇以下方式之一完成合併：

### 🎯 方式 1: GitHub Pull Request（推薦，最安全）

**直接點擊此連結創建 PR:**
```
https://github.com/Craig-0219/potato/compare/main...claude/repo-analysis-011CUyTkJC1NGJkdBmFA7zsN
```

或手動操作：
1. 前往 https://github.com/Craig-0219/potato
2. 點擊 "Pull requests" → "New pull request"
3. 設定 base: `main`, compare: `claude/repo-analysis-011CUyTkJC1NGJkdBmFA7zsN`
4. 複製 `PR_MERGE_GUIDE.md` 的內容作為 PR 說明
5. 審查後點擊 "Merge pull request"

**然後執行後續同步:**
```bash
git fetch origin
git checkout main && git pull origin main
git checkout ptero && git pull origin ptero && git merge main && git push origin ptero
git checkout develop && git reset --hard main && git push origin develop --force
git push origin --delete dev feature/cleanup-develop-branch claude/repo-analysis-011CUyTkJC1NGJkdBmFA7zsN
```

---

### 🎯 方式 2: 本地直接合併並推送

如果您有 main 分支的推送權限：

```bash
# 一鍵執行所有操作
cd /home/user/potato

# 1. 合併到 main
git fetch origin
git checkout main
git pull origin main
git merge origin/claude/repo-analysis-011CUyTkJC1NGJkdBmFA7zsN --no-ff
git push origin main

# 2. 同步 ptero
git checkout ptero
git pull origin ptero
git merge main --no-ff
git push origin ptero

# 3. 重置 develop
git checkout develop
git pull origin develop
git reset --hard main
git push origin develop --force

# 4. 清理分支
git push origin --delete dev feature/cleanup-develop-branch claude/repo-analysis-011CUyTkJC1NGJkdBmFA7zsN

# 5. 驗證
git fetch origin --prune
git branch -r
```

---

## 📚 詳細文檔

已為您準備了兩份詳細文檔：

1. **`PR_MERGE_GUIDE.md`**
   - 完整的 Pull Request 說明
   - 所有變更的詳細列表
   - 測試建議和中斷性變更說明
   - 可直接用作 PR 內容

2. **`BRANCH_MERGE_STEPS.md`**
   - 三種不同的合併方案
   - 逐步操作指令
   - 驗證清單
   - 常見問題排解

---

## ⚡ 快速選擇

**如果您想要:**
- 最安全的方式 → 使用方式 1（GitHub PR）
- 最快速的方式 → 使用方式 2（本地合併），複製貼上上方的指令

**不確定？→ 建議使用方式 1（Pull Request）**

---

## 🎉 完成後記得

1. 更新本地依賴: `pip install -r requirements.txt`
2. 更新 `.env` 檔案（參考 `.env.example`）
3. 測試 Bot 啟動: `python -m potato_bot.main`
4. 重啟生產環境（如果有）

---

需要更多說明請參考 `BRANCH_MERGE_STEPS.md` 📖
