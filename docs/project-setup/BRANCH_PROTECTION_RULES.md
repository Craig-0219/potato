# 🛡️ 分支保護和合併規則

## 分支架構

### 主要分支
- **`main`** - 生產分支，穩定代碼
- **`develop`** - 開發分支，整合新功能

### 功能分支
- **`feature/*`** - 新功能開發
- **`bugfix/*`** - 錯誤修復
- **`hotfix/*`** - 緊急修復

## 🔒 分支保護規則設置

### Main 分支保護

```json
{
  "required_status_checks": {
    "strict": true,
    "contexts": [
      "🔍 Code Quality / code-quality",
      "🛡️ Security Scans / security-summary", 
      "🧪 Test Coverage / test-summary",
      "🏗️ Build Validation / build-summary"
    ]
  },
  "enforce_admins": true,
  "required_pull_request_reviews": {
    "required_approving_review_count": 2,
    "dismiss_stale_reviews": true,
    "require_code_owner_reviews": true,
    "require_last_push_approval": true
  },
  "restrictions": null,
  "allow_force_pushes": false,
  "allow_deletions": false
}
```

### Develop 分支保護

```json
{
  "required_status_checks": {
    "strict": true,
    "contexts": [
      "🔍 Code Quality / code-quality",
      "🧪 Test Coverage / test-summary"
    ]
  },
  "enforce_admins": false,
  "required_pull_request_reviews": {
    "required_approving_review_count": 1,
    "dismiss_stale_reviews": true,
    "require_code_owner_reviews": false,
    "require_last_push_approval": false
  },
  "restrictions": null,
  "allow_force_pushes": false,
  "allow_deletions": false
}
```

## 🤖 自動合併條件

### Main 分支自動合併條件
✅ **必須全部滿足：**

1. **標籤要求**
   - 必須有 `auto-merge` 或 `ready-to-merge` 標籤
   - 不能有 `do-not-merge` 或 `work-in-progress` 標籤

2. **狀態檢查通過**
   - ✅ Code Quality (程式碼品質)
   - ✅ Security Scans (安全掃描)
   - ✅ Test Coverage (測試覆蓋率)
   - ✅ Build Validation (建構驗證)

3. **審查要求**
   - 至少 2 個批准的審查
   - 沒有要求變更的審查
   - 最新推送後需要重新批准

4. **其他條件**
   - 不是草稿 PR
   - 沒有合併衝突
   - 通過智能變更檢測

### Develop 分支自動合併條件
✅ **必須全部滿足：**

1. **標籤要求**
   - 必須有 `auto-merge` 或 `ready-to-merge` 標籤
   - 不能有阻擋標籤

2. **狀態檢查通過**
   - ✅ Code Quality (程式碼品質)
   - ✅ Test Coverage (測試覆蓋率)

3. **審查要求**
   - 至少 1 個批准的審查
   - 沒有要求變更的審查

## 📋 GitHub 設置指南

### 1. 設置 Main 分支保護

```bash
# 使用 GitHub CLI 設置
gh api repos/:owner/:repo/branches/main/protection \
  --method PUT \
  --field required_status_checks='{"strict":true,"contexts":["🔍 Code Quality / code-quality","🛡️ Security Scans / security-summary","🧪 Test Coverage / test-summary","🏗️ Build Validation / build-summary"]}' \
  --field enforce_admins=true \
  --field required_pull_request_reviews='{"required_approving_review_count":2,"dismiss_stale_reviews":true,"require_code_owner_reviews":true,"require_last_push_approval":true}' \
  --field allow_force_pushes=false \
  --field allow_deletions=false
```

### 2. 設置 Develop 分支保護

```bash
gh api repos/:owner/:repo/branches/develop/protection \
  --method PUT \
  --field required_status_checks='{"strict":true,"contexts":["🔍 Code Quality / code-quality","🧪 Test Coverage / test-summary"]}' \
  --field enforce_admins=false \
  --field required_pull_request_reviews='{"required_approving_review_count":1,"dismiss_stale_reviews":true,"require_code_owner_reviews":false,"require_last_push_approval":false}' \
  --field allow_force_pushes=false \
  --field allow_deletions=false
```

### 3. 設置自動合併標籤

創建以下標籤：

```bash
# 自動合併標籤
gh label create "auto-merge" --color "0E8A16" --description "🤖 此 PR 可以自動合併"
gh label create "ready-to-merge" --color "0E8A16" --description "✅ 準備合併"

# 阻擋標籤
gh label create "do-not-merge" --color "D93F0B" --description "❌ 禁止合併"
gh label create "work-in-progress" --color "FBE200" --description "🚧 開發中"
gh label create "needs-review" --color "0052CC" --description "👀 需要審查"
```

## 🔄 Workflow 觸發條件

### 何時觸發合併檢查
- PR 被標記或取消標記
- PR 收到新的審查
- 狀態檢查完成
- 提交狀態更新

### 合併策略
- **Main 分支**: Squash merge (壓縮合併)
- **Develop 分支**: Merge commit (合併提交)

## 📊 監控和通知

### 自動合併成功時
- ✅ 在 PR 中添加成功評論
- 📧 通知相關人員
- 🏷️ 自動移除合併標籤

### 自動合併失敗時
- ❌ 在 PR 中添加失敗評論
- 📋 列出失敗原因
- 🔧 提供修復建議

## 🚫 例外情況處理

### 緊急修復流程
1. 創建 `hotfix/*` 分支
2. 添加 `urgent` 標籤
3. 可暫時繞過部分檢查
4. 需要更高權限人員批准

### 依賴更新
- 使用 Dependabot 自動創建 PR
- 自動添加適當標籤
- 通過基礎檢查後自動合併

## 🔧 故障排除

### 常見問題

#### 1. 檢查一直顯示 "待處理"
- 檢查 workflow 是否正常運行
- 確認分支是最新的
- 重新運行失敗的檢查

#### 2. 自動合併沒有觸發
- 確認有正確的標籤
- 檢查所有必要的檢查是否通過
- 確認審查要求已滿足

#### 3. 合併衝突
- 自動合併會跳過有衝突的 PR
- 需要手動解決衝突後重新觸發

### 調試命令

```bash
# 檢查分支保護狀態
gh api repos/:owner/:repo/branches/main/protection

# 檢查 PR 狀態
gh pr view 123 --json statusCheckRollup,reviewRequests,reviews

# 手動觸發自動合併檢查
gh workflow run auto-merge.yml
```

## 📈 效果指標

### 目標指標
- 🎯 自動合併成功率 > 80%
- ⚡ 平均合併時間 < 2 小時
- 🛡️ 安全問題檢測率 > 95%
- 📊 測試覆蓋率 > 70%

### 監控方法
- GitHub Actions 運行時間統計
- PR 合併時間追蹤
- 安全掃描結果分析
- 測試覆蓋率趨勢圖

---

**注意**: 這些規則旨在確保代碼品質和安全性，同時提高開發效率。根據團隊需求可以適當調整。