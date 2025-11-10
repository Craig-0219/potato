# 分支合併完整操作步驟

## 🎯 目標

將清理分支 `claude/repo-analysis-011CUyTkJC1NGJkdBmFA7zsN` 合併到 `main`，並重組整個分支結構。

---

## ✅ 目前狀態

- ✅ 清理工作已完成（刪除 47 個檔案，17,350+ 行程式碼）
- ✅ 清理分支已推送到遠端
- ✅ 所有配置檔案已更新
- ⏳ 等待合併到 main 分支
- ⏳ 需要重組其他分支

---

## 📋 方案 1: GitHub Pull Request (推薦)

### 步驟 1: 創建 Pull Request

前往 GitHub 網頁：
```
https://github.com/Craig-0219/potato/compare/main...claude/repo-analysis-011CUyTkJC1NGJkdBmFA7zsN
```

或手動操作：
1. 進入 https://github.com/Craig-0219/potato
2. 點擊 "Pull requests" 標籤
3. 點擊 "New pull request"
4. 設定：
   - **base:** `main`
   - **compare:** `claude/repo-analysis-011CUyTkJC1NGJkdBmFA7zsN`
5. 填寫標題和說明（參考 `PR_MERGE_GUIDE.md`）
6. 點擊 "Create pull request"

### 步驟 2: 審查並合併

1. 檢查 "Files changed" 標籤，確認變更正確
2. 執行任何自動化測試（如果有 CI/CD）
3. 點擊 "Merge pull request"
4. 選擇合併方式：
   - **Squash and merge** (推薦，保持歷史簡潔)
   - **Create a merge commit**
   - **Rebase and merge**
5. 確認合併

### 步驟 3: 同步其他分支

合併完成後，在本地執行：

```bash
# 1. 更新本地 main
git fetch origin
git checkout main
git pull origin main

# 2. 同步 ptero 部署分支
git checkout ptero
git pull origin ptero
git merge main
git push origin ptero

# 3. 重置 develop 分支
git checkout develop
git pull origin develop
git reset --hard main
git push origin develop --force

# 4. 刪除廢棄的遠端分支
git push origin --delete dev
git push origin --delete feature/cleanup-develop-branch
git push origin --delete claude/repo-analysis-011CUyTkJC1NGJkdBmFA7zsN
```

---

## 📋 方案 2: 本地合併並推送

如果您偏好在本地環境完成所有操作：

### 完整指令序列

```bash
# ===== 步驟 1: 確保本地最新 =====
git fetch origin --prune

# ===== 步驟 2: 合併到 main =====
git checkout main
git pull origin main
git merge origin/claude/repo-analysis-011CUyTkJC1NGJkdBmFA7zsN --no-ff -m "🧹 合併大規模清理：移除 AI、Minecraft 和 Web API 功能

## 主要變更
- 移除 AI 整合 (14 個檔案)
- 移除 Minecraft 整合 (9 個檔案)
- 移除 Web 管理介面 (15 個檔案)
- 清理過時文檔 (6 個檔案)
- 更新所有配置檔案

## 影響
- 刪除 47 個檔案，17,350+ 行程式碼
- 減少 12 個依賴套件
- 保留所有核心 Discord Bot 功能

詳細資訊請參考 PR_MERGE_GUIDE.md
"

# 推送到遠端
git push origin main

# ===== 步驟 3: 同步 ptero 部署分支 =====
git checkout ptero
git pull origin ptero
git merge main --no-ff -m "🔄 同步 main 分支的清理更新"
git push origin ptero

# ===== 步驟 4: 重置 develop 分支 =====
git checkout develop
git pull origin develop

# 備份當前 develop（以防萬一）
git tag backup/develop-before-reset

# 強制重置為 main
git reset --hard main
git push origin develop --force

# ===== 步驟 5: 清理廢棄分支 =====

# 刪除遠端分支
git push origin --delete dev
git push origin --delete feature/cleanup-develop-branch
git push origin --delete claude/repo-analysis-011CUyTkJC1NGJkdBmFA7zsN

# 清理本地追蹤的遠端分支
git fetch origin --prune

# 可選：刪除本地分支
git branch -D dev 2>/dev/null || true
git branch -D feature/cleanup-develop-branch 2>/dev/null || true

# ===== 步驟 6: 驗證最終結構 =====
echo "=== 遠端分支 ==="
git branch -r

echo -e "\n=== 本地分支 ==="
git branch

echo -e "\n=== main 分支最新 commit ==="
git log main --oneline -5

echo -e "\n=== develop 和 main 是否同步 ==="
git log develop..main --oneline
git log main..develop --oneline
```

---

## 📋 方案 3: 逐步手動操作（最安全）

如果您想要更謹慎地操作，可以一步一步來：

### 第 1 階段: 合併到 main

```bash
# 1. 獲取最新狀態
git fetch origin

# 2. 檢出並更新 main
git checkout main
git pull origin main

# 3. 查看即將合併的內容
git log main..origin/claude/repo-analysis-011CUyTkJC1NGJkdBmFA7zsN --oneline
git diff main...origin/claude/repo-analysis-011CUyTkJC1NGJkdBmFA7zsN --stat

# 4. 確認後合併
git merge origin/claude/repo-analysis-011CUyTkJC1NGJkdBmFA7zsN --no-ff

# 5. 查看合併結果
git log --oneline -3

# 6. 推送到遠端
git push origin main
```

**⚠️ 檢查點:** 確認 main 分支推送成功後再繼續

### 第 2 階段: 同步 ptero

```bash
# 1. 切換到 ptero
git checkout ptero
git pull origin ptero

# 2. 查看 main 的新變更
git log ptero..main --oneline

# 3. 合併 main 到 ptero
git merge main --no-ff

# 4. 推送
git push origin ptero
```

**⚠️ 檢查點:** 確認 ptero 分支推送成功後再繼續

### 第 3 階段: 重置 develop

```bash
# 1. 切換到 develop
git checkout develop
git pull origin develop

# 2. 創建備份標籤
git tag backup/develop-$(date +%Y%m%d-%H%M%S)
git push origin backup/develop-$(date +%Y%m%d-%H%M%S)

# 3. 查看即將丟失的 commit（如果有）
git log main..develop --oneline

# 4. 確認後重置
git reset --hard main

# 5. 強制推送
git push origin develop --force-with-lease
```

**⚠️ 檢查點:** 確認 develop 分支重置成功後再繼續

### 第 4 階段: 清理分支

```bash
# 1. 查看所有遠端分支
git branch -r

# 2. 刪除 dev 分支
git push origin --delete dev

# 3. 刪除 feature/cleanup-develop-branch
git push origin --delete feature/cleanup-develop-branch

# 4. 刪除清理分支
git push origin --delete claude/repo-analysis-011CUyTkJC1NGJkdBmFA7zsN

# 5. 清理本地引用
git fetch origin --prune

# 6. 查看最終分支列表
git branch -r
```

---

## 🎯 預期的最終分支結構

### 遠端分支 (origin)
```
main                     # 生產環境主分支
develop                  # 開發分支（與 main 同步）
ptero                    # Pterodactyl 部署分支
```

### 本地分支
```
* main                   # 追蹤 origin/main
  develop                # 追蹤 origin/develop
  ptero                  # 追蹤 origin/ptero
```

---

## ✅ 驗證清單

完成操作後，執行以下檢查：

### 1. 分支結構驗證
```bash
# 應該只有 3 個遠端分支
git branch -r | grep -v "HEAD"
# 預期輸出:
#   origin/main
#   origin/develop
#   origin/ptero

# 檢查 develop 和 main 是否同步
git log origin/main..origin/develop --oneline  # 應該無輸出
git log origin/develop..origin/main --oneline  # 應該無輸出
```

### 2. 提交歷史驗證
```bash
# main 分支最新 commit 應該是清理 commit
git log origin/main --oneline -1
# 預期看到: 17cce48 🧹 大規模清理：移除 AI、Minecraft 和 Web API 功能

# ptero 應該包含 main 的所有 commit
git log origin/ptero --oneline -3
```

### 3. 檔案驗證
```bash
# 切換到 main 分支
git checkout main

# 確認已刪除的檔案不存在
! test -f src/potato_bot/cogs/ai_core.py && echo "✅ AI 檔案已刪除"
! test -d src/potato_bot/api && echo "✅ API 目錄已刪除"
! test -f src/potato_bot/cogs/minecraft_core.py && echo "✅ Minecraft 檔案已刪除"

# 確認更新的檔案存在
test -f requirements.txt && echo "✅ requirements.txt 存在"
test -f .env.example && echo "✅ .env.example 存在"
```

### 4. 依賴驗證
```bash
# 檢查 requirements.txt 不包含已刪除的依賴
! grep -q "fastapi\|openai\|mcrcon" requirements.txt && echo "✅ 依賴已清理"
```

---

## 🚨 常見問題排解

### Q1: 推送時遇到 403 錯誤
```
error: RPC failed; HTTP 403
```

**原因:** 分支保護規則或權限問題

**解決方案:**
1. 使用 Pull Request 方式（方案 1）
2. 暫時關閉分支保護（GitHub Settings → Branches）
3. 確認您的 Git 認證是否有效

### Q2: 合併衝突
```
CONFLICT (content): Merge conflict in ...
```

**解決方案:**
```bash
# 查看衝突檔案
git status

# 解決衝突後
git add <解決的檔案>
git commit -m "解決合併衝突"
```

### Q3: 強制推送 develop 時被拒絕
```
! [rejected]        develop -> develop (non-fast-forward)
```

**解決方案:**
```bash
# 使用 --force-with-lease（更安全）
git push origin develop --force-with-lease

# 或使用 --force（需要確認沒有其他人在使用）
git push origin develop --force
```

### Q4: 刪除遠端分支失敗
```
error: unable to delete 'xxx': remote ref does not exist
```

**解決方案:**
```bash
# 先更新遠端引用
git fetch origin --prune

# 再次嘗試刪除
git push origin --delete <branch-name>
```

---

## 📞 需要幫助？

如果遇到任何問題，請：
1. 檢查上方的「常見問題排解」
2. 執行 `git status` 查看當前狀態
3. 執行 `git log --oneline -5` 查看最近的 commit
4. 保存錯誤訊息並尋求協助

---

## 🎉 完成後

所有操作完成後：

1. ✅ **更新本地環境**
   ```bash
   pip install -r requirements.txt
   ```

2. ✅ **更新 .env 檔案**
   - 參考新的 `.env.example`
   - 移除 AI、Minecraft、API 相關配置

3. ✅ **測試 Bot 啟動**
   ```bash
   python -m potato_bot.main
   ```

4. ✅ **更新部署環境**
   - 如果使用 Pterodactyl，同步 ptero 分支
   - 重啟生產環境的 Bot

5. ✅ **更新文檔**
   - 通知團隊成員關於移除的功能
   - 更新 README（如果需要）

---

最後更新: 2025-11-10
版本: v3.1.0-cleanup
