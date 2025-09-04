# 🛠️ 專案設置指南

> 完整的開發環境設置與專案配置說明

## 📋 開發環境要求

### 系統需求
- **作業系統**: Linux, macOS, Windows 10/11
- **Python**: 3.10+ (推薦 3.11)
- **Git**: 2.30+
- **IDE**: VSCode/PyCharm (推薦)

### 相關服務
- **MySQL**: 8.0+ 或 **PostgreSQL**: 13+
- **Redis**: 6.0+ (可選，用於快取)
- **Docker**: 20.0+ (可選，用於容器化)

## 🚀 完整開發環境設置

### 1. 專案複製與分支

```bash
# 複製主專案
git clone https://github.com/Craig-0219/potato.git
cd potato

# 設置上游源
git remote add upstream https://github.com/Craig-0219/potato.git

# 切換到開發分支
git checkout develop
git pull upstream develop
```

### 2. Python 環境設置

=== "使用 venv (推薦)"
    ```bash
    # 創建虛擬環境
    python -m venv .venv
    
    # 啟動虛擬環境
    # Linux/macOS:
    source .venv/bin/activate
    # Windows:
    .venv\Scripts\activate
    
    # 安裝開發依賴
    pip install -e ".[dev]"
    ```

=== "使用 conda"
    ```bash
    # 創建 conda 環境
    conda create -n potato-bot python=3.11
    conda activate potato-bot
    
    # 安裝開發依賴
    pip install -e ".[dev]"
    ```

### 3. 資料庫設置

=== "MySQL"
    ```sql
    -- 創建資料庫
    CREATE DATABASE potato_bot CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
    
    -- 創建用戶
    CREATE USER 'potato_user'@'localhost' IDENTIFIED BY 'your_secure_password';
    GRANT ALL PRIVILEGES ON potato_bot.* TO 'potato_user'@'localhost';
    FLUSH PRIVILEGES;
    ```

=== "PostgreSQL"
    ```sql
    -- 創建資料庫
    CREATE DATABASE potato_bot;
    
    -- 創建用戶
    CREATE USER potato_user WITH PASSWORD 'your_secure_password';
    GRANT ALL PRIVILEGES ON DATABASE potato_bot TO potato_user;
    ```

=== "SQLite (開發用)"
    ```bash
    # SQLite 會自動創建檔案，無需額外設置
    # 在 .env 中設置: DATABASE_URL=sqlite:///potato_bot.db
    ```

### 4. 開發工具設置

```bash
# 安裝 pre-commit hooks
pre-commit install

# 設置 Git hooks
make git-hooks

# 創建環境配置文件
make setup-env

# 驗證開發環境
make dev-setup
```

## ⚙️ 配置文件設置

### 1. 環境變數配置

創建 `.env` 文件：

```env
# ======================
# 開發環境配置
# ======================

# 環境設定
ENVIRONMENT=development
DEBUG=true
LOG_LEVEL=DEBUG

# Discord 設定
DISCORD_TOKEN=你的開發機器人令牌
DISCORD_CLIENT_ID=你的客戶端ID
DISCORD_GUILD_ID=你的測試伺服器ID

# 資料庫設定
DB_HOST=localhost
DB_PORT=3306
DB_USER=potato_user
DB_PASSWORD=your_secure_password
DB_NAME=potato_bot_dev

# 測試資料庫 (可選)
TEST_DB_URL=sqlite:///test.db

# 開發服務
ENABLE_API_SERVER=true
API_PORT=8000
API_DEBUG=true

# 快取設定
REDIS_URL=redis://localhost:6379/1

# 同步設定 (開發環境建議開啟)
SYNC_COMMANDS=true

# AI 服務 (測試用)
OPENAI_API_KEY=你的測試金鑰
AI_RATE_LIMIT_USER=100
```

### 2. IDE 設置

=== "VSCode"
    創建 `.vscode/settings.json`：
    ```json
    {
      "python.defaultInterpreterPath": "./.venv/bin/python",
      "python.formatting.provider": "black",
      "python.linting.enabled": true,
      "python.linting.flake8Enabled": true,
      "python.linting.mypyEnabled": true,
      "editor.formatOnSave": true,
      "editor.codeActionsOnSave": {
        "source.organizeImports": true
      }
    }
    ```

=== "PyCharm"
    1. 設置解釋器為專案虛擬環境
    2. 啟用 Black 格式化工具
    3. 配置 Flake8 和 MyPy
    4. 設置 pytest 為測試執行器

## 🧪 開發流程設置

### 1. 程式碼品質工具

```bash
# 格式化程式碼
make format

# 檢查程式碼品質
make lint

# 執行安全掃描
make security

# 完整品質檢查
make quality-check
```

### 2. 測試設置

```bash
# 執行所有測試
make test

# 執行單元測試
make test-unit

# 執行整合測試
make test-integration

# 生成覆蓋率報告
make test-coverage
```

### 3. Git 工作流程

```bash
# 創建功能分支
git checkout -b feature/your-feature-name

# 開發完成後
make quality-check  # 確保程式碼品質
git add .
git commit -m "feat: your feature description"

# 推送分支
git push origin feature/your-feature-name
```

## 🚀 CI/CD 設置

### 分支策略

- **`main`** - 生產穩定版本
- **`develop`** - 開發主分支
- **`feature/*`** - 功能開發分支
- **`hotfix/*`** - 緊急修復分支

### GitHub Actions

專案已配置以下 CI/CD 流程：

1. **程式碼品質檢查** - Black, isort, Flake8, MyPy
2. **安全掃描** - Bandit, Safety, Secrets 檢測
3. **測試執行** - 單元測試、整合測試、E2E 測試
4. **自動部署** - main 分支自動部署到生產環境

### 本地 CI 模擬

```bash
# 執行完整 CI 流程
make ci-test

# 執行建構檢查
make ci-build
```

## 📊 專案監控

### 開發指標

```bash
# 檢查技術債務
make tech-debt-check

# 性能分析
make analyze-performance

# 記憶體監控
make monitor-memory

# 專案統計
make stats
```

### 日誌和除錯

```bash
# 啟用除錯日誌
make debug-logs

# 清理除錯程式碼
make debug-cleanup

# 查看系統健康狀態
make health-check
```

## 🔧 常見問題解決

### 依賴問題

```bash
# 清理並重新安裝依賴
pip uninstall -y -r requirements.txt
pip install -r requirements.txt

# 或者重建虛擬環境
rm -rf .venv
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

### 權限問題

```bash
# Git hooks 權限
chmod +x .git/hooks/*

# 腳本權限
chmod +x start.sh
chmod +x scripts/*.sh
```

### 資料庫遷移

```bash
# 執行資料庫遷移
make db-migrate

# 創建資料庫備份
make db-backup
```

## 📚 開發資源

- 🛠️ [API 文檔](../development/api-reference.md)
- 🔍 [故障排除]
- 🏗️ [系統架構](../development/ADMIN_PERMISSION_SETUP.md)
- 📖 [貢獻指南](contributing.md)

---

🎉 **開發環境設置完成！**

現在你已經擁有一個功能完整的開發環境。開始你的第一個功能開發吧！

需要協助？查看我們的 [貢獻指南](contributing.md) 或加入 [Discord 討論]。