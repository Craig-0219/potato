# 🌿 分支策略與檔案分類規範

## 📋 分支架構概覽

```mermaid
gitgraph:
    options:
        theme: base
        themeVariables:
            primaryColor: '#ff6b6b'
            primaryTextColor: '#fff'
            primaryBorderColor: '#ff6b6b'
            lineColor: '#333'

    commit id: "Initial"
    
    branch develop
    commit id: "Dev Setup"
    
    branch feature/docs-restructure
    commit id: "New Docs"
    commit id: "Complete Restructure"
    
    checkout develop
    merge feature/docs-restructure
    
    checkout main
    merge develop
    commit id: "Release v3.1.0"
    
    branch ptero
    commit id: "Clean Deploy"
```

---

## 🎯 分支用途定義

### 🚀 **main** - 生產主分支
**用途**: 穩定的生產版本，隨時可部署

#### 檔案分類標準
✅ **包含文件**:
- 完整的核心程式碼 (`bot/`, `shared/`, `web-ui/`)
- 生產配置文件 (`.env.example`, `config/`)
- 部署相關文件 (`docker-compose.yml`, `Dockerfile`)
- 用戶文檔 (`README.md`, `docs/getting-started/`, `docs/user-guide/`)
- 重要的專案文件 (`LICENSE`, `VERSION`)

❌ **排除文件**:
- 開發工具配置 (`.pre-commit-config.yaml`)
- 詳細的開發文檔 (`docs/development/` 的部分內容)
- 測試覆蓋率報告 (`htmlcov/`, `coverage.xml`)
- 開發日誌和歷史文件 (`docs/history_archive/`)
- 開發路線圖 (`DEVELOPMENT_ROADMAP.md`)

#### 分支保護規則
- ✅ 需要 PR 審核 (至少 1 人)
- ✅ 必須通過所有狀態檢查
- ✅ 需要最新的分支
- ✅ 管理員也需要遵循規則
- ✅ 禁止強制推送

---

### 🔧 **develop** - 開發整合分支  
**用途**: 整合所有開發中的功能，包含完整的開發環境

#### 檔案分類標準
✅ **包含所有文件**:
- 完整的專案結構
- 所有開發工具和配置
- 完整的測試套件
- 詳細的開發文檔
- CI/CD 配置文件
- 開發歷史和分析文件

#### 開發規範
- 🎯 功能分支合併的目標分支
- 🧪 完整的 CI/CD 流程驗證
- 📊 代碼覆蓋率和品質檢查
- 🔍 安全掃描和依賴檢查

---

### 🌟 **feature/\*** - 功能開發分支
**用途**: 獨立功能開發，從 `develop` 分出，完成後合併回 `develop`

#### 命名規範
```
feature/功能描述
feature/票務系統優化
feature/ai-integration  
feature/web-ui-dashboard
feature/docs-complete-restructure (當前)
```

#### 生命週期
1. 從 `develop` 分支建立
2. 獨立開發和測試
3. 提交 PR 到 `develop`
4. 代碼審核和 CI 檢查
5. 合併後刪除分支

---

### 🚀 **ptero** - 純淨部署分支
**用途**: 專為託管環境優化的純淨版本

#### 檔案分類標準
✅ **最小化包含**:
- 核心運行時程式碼
- 生產配置文件
- 必要的依賴文件
- 基礎文檔 (README.md)

❌ **完全排除**:
- 開發工具和配置
- 測試文件和覆蓋率報告
- 詳細開發文檔
- CI/CD 配置文件
- Web-UI 源碼 (如果不需要)
- 歷史文件和日誌

---

## 📁 檔案分類詳細規範

### 🎯 **核心程式碼** (所有分支)
```
bot/                 # Discord Bot 主程式
├── cogs/           # 功能模組
├── services/       # 業務邏輯服務  
├── utils/          # 工具函數
└── main.py         # 程式入口

shared/             # 共用組件
├── database/       # 資料庫層
├── config/         # 配置管理
├── models/         # 資料模型
└── utils/          # 共用工具

web-ui/             # Next.js 前端
├── components/     # React 組件
├── pages/          # 頁面路由
├── styles/         # 樣式文件
└── package.json    # 前端依賴
```

### 🔧 **開發工具** (develop 限定)
```
.github/            # GitHub Actions 和模板
.pre-commit-config.yaml
.coverage.yml
.gitignore
pytest.ini
ruff.toml
```

### 📚 **文檔分類**

#### **用戶文檔** (main + develop)
```
docs/
├── index.md                    # 文檔首頁
├── getting-started/           # 快速開始
│   ├── quickstart.md
│   ├── project-setup.md
│   └── contributing.md
├── user-guide/                # 使用指南
│   ├── commands.md
│   ├── features/
│   └── troubleshooting.md
└── administration/            # 管理指南
    └── deployment.md
```

#### **開發文檔** (develop 限定)
```
docs/
├── development/               # 開發者文檔
│   ├── api-reference.md
│   ├── ADMIN_PERMISSION_SETUP.md
│   └── CI_CD_SETUP_GUIDE.md
└── history_archive/           # 歷史文件
    └── *.md
```

### 🔒 **配置文件**

#### **生產配置** (所有分支)
```
.env.example        # 環境變數範例
docker-compose.yml  # Docker 部署配置  
Dockerfile          # 容器化配置
requirements.txt    # Python 依賴
```

#### **開發配置** (develop 限定)  
```
requirements-dev.txt    # 開發依賴
.editorconfig          # 編輯器配置
.vscode/               # VS Code 設定
```

---

## 🔄 合併工作流程

### 1. 功能開發流程
```bash
# 1. 從 develop 建立功能分支
git checkout develop
git pull origin develop
git checkout -b feature/新功能名稱

# 2. 開發和提交
git add .
git commit -m "feat: 新功能描述"

# 3. 推送並建立 PR
git push origin feature/新功能名稱
# 在 GitHub 建立 PR: feature/新功能名稱 -> develop
```

### 2. 發布流程
```bash
# 1. develop 合併到 main
# PR: develop -> main (需要審核)

# 2. main 部署到 ptero (自動化)
# GitHub Actions 自動觸發
```

### 3. 緊急修復流程
```bash
# 1. 從 main 建立修復分支
git checkout main
git checkout -b hotfix/修復描述

# 2. 修復並測試
git commit -m "fix: 緊急修復描述"

# 3. 合併到 main 和 develop
# PR: hotfix/修復描述 -> main
# PR: hotfix/修復描述 -> develop
```

---

## 🛡️ 分支保護與品質門檻

### **main** 分支保護
```yaml
protection_rules:
  required_reviews: 1
  dismiss_stale_reviews: true
  require_code_owner_reviews: false
  required_status_checks:
    - "CI/CD Pipeline"
    - "Security Scan"
    - "Code Quality"
  enforce_admins: true
  allow_force_pushes: false
  allow_deletions: false
```

### **develop** 分支保護  
```yaml
protection_rules:
  required_reviews: 1
  dismiss_stale_reviews: false
  required_status_checks:
    - "Tests"
    - "Code Quality"
    - "Build Check"
  enforce_admins: false
  allow_force_pushes: false
  allow_deletions: false
```

### **品質門檻**
- ✅ 所有測試必須通過
- ✅ 代碼覆蓋率 > 80%
- ✅ Ruff 檢查無錯誤
- ✅ 安全掃描無高風險漏洞
- ✅ 無合併衝突

---

## 📋 檔案清理檢查清單

### 準備 main 分支合併
- [ ] 移除開發工具配置文件
- [ ] 清理測試生成的文件
- [ ] 更新版本號碼
- [ ] 確認生產配置正確
- [ ] 驗證文檔連結有效

### 準備 ptero 分支部署
- [ ] 只保留運行時必需文件
- [ ] 移除所有開發文檔
- [ ] 優化 Docker 映像大小
- [ ] 確認環境變數配置
- [ ] 測試部署流程

---

## 🔍 分支健康監控

### 指標追蹤
- **分支分歧度**: develop 領先 main 的提交數
- **PR 平均處理時間**: 從建立到合併的時間
- **CI/CD 成功率**: 自動化流程的通過率
- **代碼覆蓋率趨勢**: 測試覆蓋率變化

### 定期維護
- 🗓️ **週檢查**: 清理已合併的功能分支
- 🗓️ **月檢查**: 審查分支保護規則效果
- 🗓️ **季檢查**: 評估分支策略是否需要調整

---

*📝 此分支策略將確保程式碼品質和部署穩定性，同時支援高效的團隊協作開發*