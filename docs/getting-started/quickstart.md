# 🚀 快速開始

> ⚡ 5 分鐘內讓 Potato Bot 運行起來

## 📋 系統需求

### 最低要求
- **Python** 3.10+
- **記憶體** 512MB+
- **磁碟空間** 2GB+
- **Discord Bot Token**

### 推薦配置
- **Python** 3.11+
- **記憶體** 1GB+
- **磁碟空間** 5GB+
- **資料庫** MySQL/PostgreSQL

## 🏃‍♂️ 快速部署

### 1. 獲取專案

=== "生產版本 (推薦)"
    ```bash
    git clone -b main https://github.com/Craig-0219/potato.git
    cd potato
    ```

=== "開發版本"
    ```bash
    git clone -b develop https://github.com/Craig-0219/potato.git
    cd potato
    ```

### 2. 環境配置

```bash
# 複製配置範例
cp .env.example .env

# 編輯配置文件 (必要!)
nano .env
```

### 3. 安裝依賴

```bash
# 生產環境
pip install -r requirements.txt

# 開發環境 (包含測試工具)
pip install -e ".[dev]"
```

### 4. 啟動機器人

=== "Python 啟動器 (推薦)"
    ```bash
    python start.py
    ```

=== "平台專用腳本"
    ```bash
    # Linux/macOS
    ./start.sh

    # Windows
    start.bat
    ```

## ⚙️ 基本配置

### 必填設定

編輯 `.env` 文件，確保以下設定正確：

```env
# Discord 機器人設定 (必填)
DISCORD_TOKEN=你的機器人令牌
DISCORD_CLIENT_ID=你的客戶端ID
DISCORD_GUILD_ID=你的伺服器ID

# 資料庫設定 (必填)
DB_HOST=localhost
DB_PORT=3306
DB_USER=數據庫用戶名
DB_PASSWORD=數據庫密碼
DB_NAME=potato_bot

# 安全設定 (必填)
JWT_SECRET=至少32字符的隨機字串
```

### 可選設定

```env
# API 服務
ENABLE_API_SERVER=true
API_PORT=8000

# Redis 快取 (推薦)
REDIS_URL=redis://localhost:6379/0

# AI 服務 (可選)
OPENAI_API_KEY=你的OpenAI金鑰
ANTHROPIC_API_KEY=你的Anthropic金鑰
GEMINI_API_KEY=你的Gemini金鑰
```

## 🎯 驗證部署

### 1. 檢查機器人狀態

如果配置正確，你應該看到：

```bash
✅ Database connected successfully
✅ Discord bot logged in as: YourBotName#1234
✅ API server started on http://0.0.0.0:8000
🚀 Potato Bot is ready!
```

### 2. Discord 測試

在你的 Discord 伺服器中：

```
/help          # 查看可用指令
/ping          # 測試機器人回應
/status        # 檢查系統狀態
```

### 3. API 測試

訪問 `http://localhost:8000/health` 應該返回：

```json
{
  "status": "healthy",
  "timestamp": "2025-09-04T06:30:00Z"
}
```

## 🛠️ 故障排除

### 常見問題

!!! question "機器人無法啟動"
    - 檢查 `DISCORD_TOKEN` 是否正確
    - 確認機器人已邀請到伺服器
    - 檢查網路連接

!!! question "資料庫連接失敗"
    - 確認資料庫服務正在運行
    - 檢查 `DB_*` 設定是否正確
    - 確認用戶具有資料庫存取權限

!!! question "模組導入錯誤"
    - 確認 Python 版本 >= 3.10
    - 重新安裝依賴：`pip install -r requirements.txt`
    - 檢查虛擬環境是否啟用

### 取得協助

- 📖 [詳細文檔](../developer-docs/troubleshooting.md)
- 🐛 [提交問題](https://github.com/Craig-0219/potato/issues)
- 💬 [社群支援](https://discord.gg/your-server)

## 📚 下一步

機器人運行成功後：

1. **用戶指南** - [了解所有功能](../user-guide/commands.md)
2. **管理設定** - [配置權限和功能](../system-design/admin-permissions.md)
3. **開發環境** - [設置開發環境](project-setup.md)

---

🎉 **恭喜！** 你已經成功部署 Potato Bot！

需要更多幫助？查看我們的 [完整使用指南](../user-guide/commands.md) 或 [系統管理文檔](../system-design/admin-permissions.md)。