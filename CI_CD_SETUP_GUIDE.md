# 🚀 CI/CD 設置完整指南

## 📋 概述

本指南將協助你設置完整的現代化 CI/CD 流程，包含程式碼品質檢查、安全掃描、測試覆蓋率和自動合併機制。

**當前狀態**: 
- ✅ CI/CD workflows 已實作完成
- ✅ 分支已推送: `feature/cicd-complete-rewrite`
- 🔄 等待 PR 合併和後續設置

---

## 🏗️ 新增的核心 Workflows

### 🔍 Code Quality (`code-quality.yml`)
**功能概述**:
- **Black** 程式碼格式檢查
- **isort** Import 排序檢查  
- **Flake8** 程式碼風格檢查
- **MyPy** 型別檢查 (警告模式)
- **Radon** 程式碼複雜度分析
- **文件完整性檢查** (README, pyproject.toml 等)
- **依賴安全檢查** (safety, pip-audit)

**執行條件**: PR 和 push 到 main/develop 分支

### 🛡️ Security Scans (`security-scans.yml`)
**功能概述**:
- **detect-secrets** 機密資訊掃描
- **Bandit** Python 安全掃描
- **Semgrep** 進階程式碼分析
- **Safety/Pip-audit** 依賴漏洞掃描
- **Trivy** Docker 映像安全掃描
- **每日自動掃描** (凌晨 2 點)

**執行條件**: PR、push 和每日排程

### 🧪 Test Coverage (`test-coverage.yml`)
**功能概述**:
- **多版本測試** Python 3.10, 3.11
- **分組單元測試** (core, services, api, utils)
- **整合測試** (MySQL + Redis 服務)
- **E2E 測試** (僅 main 分支)
- **覆蓋率報告** 自動 PR 評論
- **最低覆蓋率要求** 70%

**執行條件**: PR 和 push，支援測試類型選擇

### 🏗️ Build Validation (`build-validation.yml`)
**功能概述**:
- **多版本 Python 建構驗證** (3.10, 3.11, 3.12)
- **Docker 映像建構和檢查**
- **Web UI 建構驗證** (如果存在)
- **效能和記憶體使用檢查**
- **啟動時間測試**

**執行條件**: PR 和 push，支援建構類型選擇

### 🤖 Auto Merge (`auto-merge.yml`)
**功能概述**:
- **智能標籤檢查** (auto-merge, do-not-merge)
- **狀態檢查驗證** (所有必要檢查通過)
- **審查要求確認** (main: 2個批准, develop: 1個批准)
- **自動合併執行** 和通知
- **衝突檢測和處理**

**執行條件**: PR 標籤變更、審查提交、檢查完成

---

## 📋 第一步：創建和合併 Pull Request

### 1.1 手動創建 PR

**PR 地址**: https://github.com/Craig-0219/potato/pull/new/feature/cicd-complete-rewrite

**建議的 PR 標題**:
```
🔧 完整 CI/CD 重構 - 深度清潔和現代化工作流程
```

**建議的 PR 描述**:
```markdown
## ✨ 新增的核心 Workflows

### 🔍 Code Quality 
- Black/isort/Flake8/MyPy 檢查
- 程式碼複雜度分析  
- 文件完整性和依賴安全檢查

### 🛡️ Security Scans
- 機密資訊、程式碼、依賴、Docker 安全掃描
- 每日自動安全掃描

### 🧪 Test Coverage
- 多版本 Python 測試 (3.10, 3.11)
- 單元/整合/E2E 測試
- 覆蓋率報告和 PR 評論

### 🏗️ Build Validation  
- 多版本建構驗證
- Docker 映像建構檢查
- 效能和記憶體使用檢查

### 🤖 Auto Merge
- 智能標籤和狀態檢查
- 自動合併執行和通知

## 📋 建議的分支保護規則

**Main 分支**:
- code-quality + security-summary + test-summary + build-summary
- 需要 2 個審查批准

**Develop 分支**:
- code-quality + test-summary  
- 需要 1 個審查批准

## ⚠️ 重要提醒

此 PR 包含重大 workflow 變更，合併後將完全替換現有 CI/CD 流程。
建議合併後按照 `CI_CD_SETUP_GUIDE.md` 完成後續設置。
```

### 1.2 合併策略

- **目標分支**: `develop`
- **合併方式**: Merge commit (保留提交歷史)
- **合併前檢查**: 確保所有新 workflow 語法正確

---

## 📋 第二步：設置分支保護規則

### 2.1 設置 Main 分支保護

**路徑**: `Settings` → `Branches` → `Add branch protection rule`

**設置詳情**:

| 設定項目 | 配置 |
|---------|------|
| **Branch name pattern** | `main` |
| **Require a pull request before merging** | ✅ |
| └─ Required number of reviewers | `2` |
| └─ Dismiss stale PR approvals | ✅ |
| └─ Require review from code owners | ✅ |
| └─ Require approval of most recent push | ✅ |
| **Require status checks before merging** | ✅ |
| └─ Require branches to be up to date | ✅ |
| └─ **Required status checks** | 見下方清單 |
| **Require conversation resolution** | ✅ |
| **Include administrators** | ✅ |
| **Allow force pushes** | ❌ |
| **Allow deletions** | ❌ |

**Main 分支必要狀態檢查**:
```
🔍 Code Quality / code-quality
🛡️ Security Scans / security-summary
🧪 Test Coverage / test-summary
🏗️ Build Validation / build-summary
```

### 2.2 設置 Develop 分支保護

**設置詳情**:

| 設定項目 | 配置 |
|---------|------|
| **Branch name pattern** | `develop` |
| **Require a pull request before merging** | ✅ |
| └─ Required number of reviewers | `1` |
| └─ Dismiss stale PR approvals | ✅ |
| └─ Require review from code owners | ❌ |
| └─ Require approval of most recent push | ❌ |
| **Require status checks before merging** | ✅ |
| └─ Require branches to be up to date | ✅ |
| └─ **Required status checks** | 見下方清單 |
| **Require conversation resolution** | ✅ |
| **Include administrators** | ❌ |
| **Allow force pushes** | ❌ |
| **Allow deletions** | ❌ |

**Develop 分支必要狀態檢查**:
```
🔍 Code Quality / code-quality
🧪 Test Coverage / test-summary
```

### 2.3 使用 GitHub CLI 設置 (替代方案)

如果你有 GitHub CLI 和適當權限，可以使用以下命令快速設置：

```bash
# 設置 Main 分支保護
gh api repos/Craig-0219/potato/branches/main/protection \
  --method PUT \
  --field required_status_checks='{"strict":true,"contexts":["🔍 Code Quality / code-quality","🛡️ Security Scans / security-summary","🧪 Test Coverage / test-summary","🏗️ Build Validation / build-summary"]}' \
  --field required_pull_request_reviews='{"required_approving_review_count":2,"dismiss_stale_reviews":true,"require_code_owner_reviews":true,"require_last_push_approval":true}' \
  --field allow_force_pushes=false \
  --field allow_deletions=false

# 設置 Develop 分支保護  
gh api repos/Craig-0219/potato/branches/develop/protection \
  --method PUT \
  --field required_status_checks='{"strict":true,"contexts":["🔍 Code Quality / code-quality","🧪 Test Coverage / test-summary"]}' \
  --field required_pull_request_reviews='{"required_approving_review_count":1,"dismiss_stale_reviews":true}' \
  --field allow_force_pushes=false \
  --field allow_deletions=false
```

---

## 📋 第三步：創建自動合併標籤

### 3.1 標籤清單

在 `Issues` → `Labels` 中創建以下標籤：

| 標籤名稱 | 顏色代碼 | 描述 | 用途 |
|---------|---------|------|------|
| `auto-merge` | `#0E8A16` | 🤖 此 PR 可以自動合併 | 啟用自動合併 |
| `ready-to-merge` | `#0E8A16` | ✅ 準備合併 | 啟用自動合併 |
| `do-not-merge` | `#D93F0B` | ❌ 禁止合併 | 阻止自動合併 |
| `work-in-progress` | `#FBE200` | 🚧 開發中 | 阻止自動合併 |
| `needs-review` | `#0052CC` | 👀 需要審查 | 阻止自動合併 |
| `urgent` | `#D93F0B` | 🚨 緊急修復 | 標記緊急 PR |

### 3.2 使用 GitHub CLI 創建標籤 (可選)

```bash
# 自動合併標籤
gh label create "auto-merge" --color "0E8A16" --description "🤖 此 PR 可以自動合併"
gh label create "ready-to-merge" --color "0E8A16" --description "✅ 準備合併"

# 阻擋標籤
gh label create "do-not-merge" --color "D93F0B" --description "❌ 禁止合併"
gh label create "work-in-progress" --color "FBE200" --description "🚧 開發中"
gh label create "needs-review" --color "0052CC" --description "👀 需要審查"
gh label create "urgent" --color "D93F0B" --description "🚨 緊急修復"
```

### 3.3 自動合併使用方式

**啟用自動合併**:
1. 在 PR 中添加 `auto-merge` 或 `ready-to-merge` 標籤
2. 確保所有必要檢查通過
3. 確保審查要求滿足
4. 系統將自動執行合併

**防止自動合併**:
1. 添加 `do-not-merge`、`work-in-progress` 或 `needs-review` 標籤
2. 將 PR 標記為草稿
3. 有未解決的審查變更要求

---

## 📋 第四步：配置 GitHub Secrets (可選)

### 4.1 必要的 Secrets

在 `Settings` → `Secrets and variables` → `Actions` 中添加：

| Secret 名稱 | 用途 | 是否必需 |
|------------|------|---------|
| `SEMGREP_APP_TOKEN` | Semgrep 安全掃描 | 可選 |
| `CODECOV_TOKEN` | 代碼覆蓋率上傳 | 可選 |
| `DOCKER_REGISTRY_TOKEN` | Docker 推送權限 | 可選 |

### 4.2 獲取 Tokens

**Semgrep Token**:
1. 註冊 https://semgrep.dev/
2. 創建專案並獲取 token
3. 添加到 GitHub Secrets

**Codecov Token**:
1. 註冊 https://codecov.io/
2. 連結 GitHub 倉庫
3. 獲取上傳 token

---

## 📋 第五步：測試和驗證 Workflows

### 5.1 創建測試 PR

合併主要 PR 後，創建測試分支驗證功能：

```bash
# 切換到 develop 分支並更新
git checkout develop
git pull origin develop

# 創建測試分支
git checkout -b test/workflow-validation

# 做一個小修改
echo "# Test workflow validation" >> README.md
git add README.md
git commit -m "test: validate new CI/CD workflows"

# 推送並創建 PR
git push -u origin test/workflow-validation
```

### 5.2 驗證檢查項目

創建測試 PR 後，確認以下項目：

**✅ Workflow 執行檢查**:
- [ ] Smart Change Detection 正常運行
- [ ] Code Quality 檢查執行
- [ ] Test Coverage 正常運行  
- [ ] Build Validation 成功
- [ ] Security Scans 執行 (develop 分支可能跳過)

**✅ 報告和通知**:
- [ ] PR 中出現覆蓋率報告評論
- [ ] Workflow 執行摘要正確顯示
- [ ] 失敗時有詳細錯誤訊息

### 5.3 測試自動合併

在測試 PR 上：

1. **添加自動合併標籤**:
   ```bash
   gh pr edit <PR_NUMBER> --add-label "auto-merge"
   ```

2. **確保通過必要檢查**:
   - Code Quality 通過
   - Test Coverage 通過 (如果是 develop 分支)

3. **添加必要的審查批准**:
   - Develop 分支需要 1 個批准
   - Main 分支需要 2 個批准

4. **觀察自動合併執行**:
   - 檢查 PR 是否自動合併
   - 確認成功通知評論

### 5.4 故障排除

**常見問題和解決方案**:

| 問題 | 可能原因 | 解決方案 |
|------|---------|---------|
| Workflow 不執行 | 分支保護規則衝突 | 檢查並調整分支保護設置 |
| 檢查一直 pending | Workflow 語法錯誤 | 查看 Actions 頁面錯誤訊息 |
| 自動合併不觸發 | 標籤或檢查未通過 | 確認標籤和狀態檢查 |
| 測試失敗 | 環境設置問題 | 檢查依賴安裝和服務配置 |

---

## 📋 第六步：監控和維護

### 6.1 日常監控

**檢查項目**:
- [ ] Actions 頁面查看 workflow 執行狀態
- [ ] 檢查失敗的 workflow 並及時修復
- [ ] 監控安全掃描結果和建議
- [ ] 跟蹤測試覆蓋率趨勢

**週期性任務**:
- **每週**: 檢查安全掃描報告
- **每月**: 更新依賴套件和工具版本
- **季度**: 評估和調整 CI/CD 流程效率

### 6.2 效能指標

**目標指標**:

| 指標 | 目標值 | 監控方式 |
|------|-------|---------|
| 自動合併成功率 | > 80% | GitHub Actions 統計 |
| 平均合併時間 | < 2 小時 | PR 時間追蹤 |
| 測試覆蓋率 | > 70% | 覆蓋率報告 |
| 安全問題檢測率 | > 95% | 安全掃描結果 |
| Workflow 執行時間 | < 15 分鐘 | Actions 執行時間 |

### 6.3 持續改進

**優化方向**:
- **效能優化**: 並行執行、快取優化
- **品質提升**: 提高測試覆蓋率要求
- **安全加強**: 新增更多安全掃描工具
- **自動化擴展**: 更多自動化流程

---

## 🎯 完成清單

完成設置後，你將擁有：

### ✅ 核心功能
- [x] 現代化的 CI/CD 流程
- [x] 多層安全掃描機制
- [x] 自動化測試和覆蓋率追蹤  
- [x] 智能合併和分支保護
- [x] 詳細的執行報告和通知

### ✅ 品質保證
- [x] 程式碼格式和風格統一
- [x] 型別檢查和複雜度控制
- [x] 安全漏洞自動檢測
- [x] 全面的測試覆蓋率要求

### ✅ 開發體驗
- [x] 智能變更檢測和條件執行
- [x] 自動合併減少手動操作
- [x] 詳細的 PR 評論和報告
- [x] 清晰的失敗診斷和修復建議

---

## 📞 支援和協助

如果在設置過程中遇到問題：

1. **檢查 Actions 日誌**: 查看詳細的錯誤訊息
2. **參考文檔**: `BRANCH_PROTECTION_RULES.md` 
3. **測試環境**: 在測試分支上驗證修改
4. **逐步調整**: 可以先設置基礎功能，再逐步完善

**重要提醒**: 這個 CI/CD 系統設計為逐步完善，你可以根據團隊需求調整各種檢查的嚴格程度和覆蓋範圍。

🎉 **祝你設置順利！這將大大提升你的開發效率和代碼品質。**