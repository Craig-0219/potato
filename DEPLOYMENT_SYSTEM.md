# 🚀 Potato Bot 部署系統完整指南

## 📋 系統概述

本文檔描述了 Potato Bot 的完整自動化部署系統，實現了從開發到生產環境的無縫部署流程。

### 🎯 核心目標
- **自動化**: dev → main → ptero 全自動部署管線
- **安全性**: 多層次品質檢查和安全掃描
- **可靠性**: 智能變更檢測和緊急回滾機制
- **監控性**: 實時部署狀態監控和健康檢查

## 🏗️ 系統架構

```
┌─────────────┐    ┌──────────────┐    ┌─────────────────┐
│   dev 分支   │───▶│  main 分支   │───▶│  ptero 分支     │
│  (開發環境)  │    │  (暫存環境)  │    │ (生產環境)      │
└─────────────┘    └──────────────┘    └─────────────────┘
       │                   │                    │
       ▼                   ▼                    ▼
┌─────────────┐    ┌──────────────┐    ┌─────────────────┐
│ 智能變更檢測 │    │  品質門檻檢查 │    │  Pterodactyl   │
│ 代碼品質檢查 │    │  安全掃描     │    │  自動部署      │
│ 測試套件執行 │    │  生產合規檢查 │    │                │
└─────────────┘    └──────────────┘    └─────────────────┘
```

## 🔄 工作流程詳解

### 1. 開發階段 (dev 分支)
當開發者推送代碼到 `dev` 分支時，系統會自動觸發：

#### a) 智能變更檢測 (`smart-change-detection.yml`)
- **觸發條件**: push 到 dev 分支
- **功能**: 
  - 分析變更文件類型 (核心邏輯/API/文檔等)
  - 計算影響等級 (高/中/低/無)
  - 決定測試策略 (完整/針對性/快速/跳過)
  - 生成後續 workflow 執行建議
- **關鍵腳本**: `.github/scripts/classify-changes.py`

#### b) 代碼品質檢查 (`code-quality.yml`)
- **檢查項目**:
  - Python 語法檢查
  - Black 代碼格式化檢查
  - isort import 排序檢查
  - Flake8 代碼規範檢查
- **關鍵腳本**: `.github/scripts/code-quality-check.sh`

#### c) 安全掃描 (`security-scans.yml`)
- **安全檢查**:
  - Bandit 代碼安全問題掃描
  - Safety 依賴包漏洞檢查
  - Secrets 機密資訊洩漏檢測
- **關鍵腳本**: `.github/scripts/security-scan.sh`

### 2. 自動合併階段 (dev → main)

#### 自動合併 (`auto-merge.yml`)
- **觸發條件**: 
  - dev 分支所有檢查通過
  - 手動觸發合併請求
- **執行邏輯**:
  1. 驗證 dev 分支所有檢查狀態
  2. 檢測 main 分支衝突
  3. 執行自動合併或創建 PR
  4. 觸發後續部署流程

### 3. 生產部署階段 (main → ptero)

#### 部署到 Pterodactyl (`deploy-to-ptero.yml`)
- **觸發條件**:
  - main 分支有新提交 (通常來自 auto-merge)
  - 手動觸發部署
  - auto-merge workflow 成功完成
  
- **部署流程**:
  1. **部署前驗證**
     - 分析提交類型 (合併/直推/緊急)
     - 收集部署資訊和元數據
  
  2. **品質檢查** (可跳過-緊急部署用)
     - Python 語法檢查
     - 必要文件完整性驗證
     - 基本代碼規範檢查
  
  3. **分支同步**
     - 檢查或創建 ptero 分支
     - 同步 main 分支內容到 ptero
     - 處理可能的合併衝突
  
  4. **生產環境優化**
     - 清理開發相關文件
     - 生成部署資訊文件
     - 創建版本標記文件
  
  5. **安全推送**
     - 自動重試機制 (最多3次)
     - 推送到 ptero 分支
  
  6. **部署後驗證**
     - 驗證關鍵文件完整性
     - 生成部署狀態報告
     - 記錄部署統計資料

## 🚨 緊急處理機制

### 緊急回滾 (`emergency-ptero-rollback.yml`)
當生產環境出現問題時，提供快速回滾機制：

#### 使用方式
```bash
# 在 GitHub Actions 頁面手動觸發
# 參數:
# - rollback_reason: 回滾原因 (必填)
# - target_commit: 目標 commit (可選，預設上一版本)
# - skip_health_check: 跳過健康檢查 (緊急情況)
```

#### 回滾流程
1. **回滾前驗證**
   - 收集當前 ptero 分支狀態
   - 確定回滾目標 commit
   - 執行安全性檢查

2. **執行緊急回滾**
   - 強制重置 ptero 分支到目標 commit
   - 創建回滾記錄文件
   - 推送回滾變更

3. **回滾後驗證**
   - 驗證回滾完整性
   - 基本功能檢查
   - 生成回滾報告

## 📊 監控系統

### 部署狀態監控 (`deployment-monitor.yml`)
每30分鐘自動執行，監控整個部署系統健康狀況：

#### 監控項目
- **Ptero 分支狀態**: 檢查分支存在性和文件完整性
- **Main 分支狀態**: 檢查更新活躍度和提交新鮮度
- **分支同步狀態**: 檢查 main 和 ptero 分支同步情況
- **系統健康分數**: 基於各項指標計算 0-100 分健康分數

#### 自動修復建議
系統會根據監控結果自動生成修復建議：
- 🟢 90-100分: 優秀，無需干預
- 🟡 70-89分: 良好，建議關注
- 🟠 50-69分: 警告，建議儘快處理
- 🔴 0-49分: 危急，需要立即處理

## 🛠️ 管理和維護

### 手動觸發部署
```bash
# 1. 進入 GitHub Repository
# 2. 點擊 "Actions" 標籤
# 3. 選擇 "🚀 Deploy to Ptero Branch"
# 4. 點擊 "Run workflow"
# 5. 設置參數並執行
```

### 查看部署狀態
```bash
# 方法1: 查看 GitHub Actions 運行記錄
# https://github.com/{repository}/actions

# 方法2: 檢查 ptero 分支的 DEPLOYMENT_INFO.md 文件
# 包含最新部署的詳細資訊

# 方法3: 檢查 .ptero_deploy_info.json 文件
# JSON 格式的部署元數據
```

### 緊急操作指南

#### 🚨 緊急停止部署
```bash
# 1. 進入 GitHub Actions 頁面
# 2. 找到正在運行的 deploy-to-ptero workflow
# 3. 點擊 "Cancel workflow run"
```

#### 🔄 緊急回滾操作
```bash
# 1. 進入 GitHub Actions 頁面
# 2. 選擇 "🚨 Emergency Ptero Rollback"
# 3. 填寫回滾原因
# 4. (可選) 指定目標 commit
# 5. 執行回滾
```

#### 📊 檢查系統健康
```bash
# 1. 進入 GitHub Actions 頁面
# 2. 選擇 "📊 Deployment Status Monitor"
# 3. 手動觸發檢查
# 4. 查看健康分數和修復建議
```

## 🔧 配置和自訂

### GitHub Secrets 設定
系統需要以下 GitHub Secrets：
```bash
GITHUB_TOKEN          # GitHub API 訪問權限 (自動提供)
DISCORD_TEST_TOKEN     # Discord 測試 Token (可選)
CODECOV_TOKEN         # Codecov 整合 Token (可選)
SEMGREP_APP_TOKEN     # Semgrep 安全掃描 Token (可選)
```

### 環境變數配置
在 `.env.example` 中定義的環境變數：
```bash
DISCORD_CLIENT_ID         # Discord OAuth 應用程式 ID
DISCORD_CLIENT_SECRET     # Discord OAuth 應用程式密鑰
DISCORD_REDIRECT_URI      # OAuth 重定向 URI
DISCORD_GUILD_ID          # Discord 伺服器 ID
DISCORD_TOKEN             # Discord Bot Token
# ... 其他配置
```

### 工作流程自訂
可以通過修改 `.github/workflows/*.yml` 文件來自訂工作流程：

1. **修改觸發條件**: 編輯 `on:` 部分
2. **調整檢查嚴格度**: 修改腳本中的檢查參數
3. **自訂通知頻率**: 調整 `deployment-monitor.yml` 中的 cron 設定
4. **修改並發控制**: 調整 `concurrency:` 設定

## 📈 效能和最佳實踐

### 部署效能優化
- **並發控制**: 避免同時執行多個部署操作
- **智能跳過**: 根據變更類型跳過不必要的檢查
- **快取策略**: 利用 GitHub Actions 快取加速構建
- **漸進式部署**: 支援分階段部署降低風險

### 安全最佳實踐
- **最小權限原則**: 工作流程只獲得必要的權限
- **機密管理**: 使用 GitHub Secrets 管理敏感資訊
- **安全掃描**: 自動化安全漏洞檢測
- **審計日誌**: 完整的部署操作記錄

### 監控最佳實踐
- **主動監控**: 定期自動檢查系統健康
- **告警機制**: 異常情況自動通知
- **歷史追蹤**: 保存部署歷史和趨勢分析
- **自動修復**: 提供具體的問題修復建議

## 🐛 故障排除

### 常見問題和解決方案

#### 1. 部署失敗：「推送被拒絕」
**原因**: Git 權限問題或分支保護規則
**解決方案**:
```bash
# 檢查 GitHub Token 權限
# 確認 GITHUB_TOKEN 具有 repo 權限
# 檢查分支保護規則設定
```

#### 2. 自動合併失敗：「衝突檢測」
**原因**: dev 和 main 分支存在衝突
**解決方案**:
```bash
# 1. 手動解決衝突
git checkout dev
git pull origin main
# 解決衝突後提交
git push origin dev

# 2. 重新觸發 auto-merge workflow
```

#### 3. 健康檢查失敗：「文件缺失」
**原因**: 部署過程中關鍵文件丟失
**解決方案**:
```bash
# 1. 檢查 main 分支文件完整性
# 2. 重新執行部署 workflow
# 3. 如問題持續，執行緊急回滾
```

#### 4. 監控顯示「分支分歧」
**原因**: main 和 ptero 分支意外分歧
**解決方案**:
```bash
# 選項 A: 重新部署
# 手動觸發 deploy-to-ptero workflow

# 選項 B: 緊急回滾
# 使用 emergency-ptero-rollback workflow
```

### 聯繫支援
如需技術支援或發現系統錯誤，請：
1. 查看 [GitHub Issues](https://github.com/{repository}/issues)
2. 創建新的 Issue 並包含：
   - 錯誤描述和重現步驟
   - 相關的 GitHub Actions 運行 ID
   - 系統健康監控報告截圖

---

## 📚 附錄

### A. 工作流程文件清單
- `auto-merge.yml` - 自動合併 dev 到 main
- `deploy-to-ptero.yml` - 主要部署工作流程
- `emergency-ptero-rollback.yml` - 緊急回滾機制
- `deployment-monitor.yml` - 部署狀態監控
- `smart-change-detection.yml` - 智能變更檢測
- `code-quality.yml` - 代碼品質檢查
- `security-scans.yml` - 安全掃描

### B. 腳本文件清單
- `classify-changes.py` - 智能變更分類
- `production-compliance-check.sh` - 生產環境合規檢查
- `code-quality-check.sh` - 代碼品質檢查
- `security-scan.sh` - 安全掃描

### C. 版本歷史
- **v2.0** (2025年1月): 完整重寫，新增監控和緊急回滾
- **v1.0** (2024年12月): 初始部署系統實現

---

*🤖 本文檔由 Claude Code 自動生成和維護*  
*📅 最後更新: 2025年1月*