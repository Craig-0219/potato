# 🚀 Potato Bot 快速開始指南

> ⚡ 5 分鐘內啟動並運行 Potato Bot

## 📋 系統需求

### 最低要求
- **Python 3.10+** (建議 3.11+)
- **MySQL/MariaDB** 資料庫
- **Discord Bot Token**
- **2GB RAM** (建議 4GB+)
- **1GB 可用磁碟空間**

### 可選元件
- **Redis** (用於快取，可使用內建替代)
- **Docker** (容器化部署)

---

## 🎯 快速啟動 (1 分鐘)

### 方法一：一鍵啟動器 ⭐ 推薦

```bash
# 下載專案
git clone https://github.com/Craig-0219/potato.git
cd potato

# 使用啟動器 (會自動檢查環境和安裝依賴)
python start.py          # 跨平台
# 或
./start.sh              # Linux/macOS
# 或  
start.bat               # Windows
```

### 方法二：傳統方式

```bash
# 1. 安裝依賴
pip install -r requirements.txt

# 2. 配置環境
cp .env.example .env
nano .env  # 編輯配置

# 3. 啟動
python bot/main.py
```

---

## ⚙️ 環境配置

### 1. Discord Bot 設定

1. 前往 [Discord Developer Portal](https://discord.com/developers/applications)
2. 創建新應用程式 → Bot
3. 複製 Token 到 `.env` 檔案

```env
DISCORD_TOKEN=your_discord_bot_token_here
```

### 2. 資料庫設定

```env
DB_HOST=localhost
DB_PORT=3306
DB_USER=your_db_user
DB_PASSWORD=your_db_password
DB_NAME=potato_bot
```

### 3. API 服務設定

```env
# 啟用 API 服務
ENABLE_API_SERVER=true
API_EXTERNAL_ACCESS=true
LOCAL_API_HOST=0.0.0.0
LOCAL_API_PORT=8080
```

### 4. Redis 設定 (可選)

```env
# 如果沒有 Redis，會自動使用內建快取
REDIS_URL=redis://localhost:6379
```

---

## 🎮 支援的啟動方式

### 🐍 Python 啟動器 (`start.py`)
```bash
python start.py          # 互動式啟動
python start.py start    # 直接啟動
python start.py check    # 只檢查環境
python start.py install  # 只安裝依賴
```

**特色：**
- ✅ 自動環境檢查
- ✅ 依賴自動安裝
- ✅ 錯誤診斷
- ✅ 跨平台支援

### 🐧 Linux/macOS 腳本 (`start.sh`)
```bash
./start.sh               # 互動式啟動
./start.sh start         # 直接啟動
./start.sh check         # 只檢查環境
./start.sh install       # 只安裝依賴
```

**特色：**
- ✅ 彩色輸出
- ✅ 信號處理
- ✅ 進階系統檢查

### 🪟 Windows 批次檔 (`start.bat`)
```cmd
start.bat                # 互動式啟動
start.bat start          # 直接啟動
start.bat check          # 只檢查環境
start.bat install        # 只安裝依賴
```

**特色：**
- ✅ Windows 原生支援
- ✅ 自動 Notepad 編輯器
- ✅ 錯誤處理

### 🔧 Make 命令
```bash
make run-bot             # 啟動 Bot
make run-api             # 啟動 API 服務
make run-web             # 啟動 Web 界面
make health-check        # 健康檢查
```

---

## 🐳 Docker 快速部署

### 使用 Docker Compose (推薦)
```bash
# 1. 克隆專案
git clone https://github.com/Craig-0219/potato.git
cd potato

# 2. 配置環境
cp .env.example .env
# 編輯 .env 填入配置

# 3. 一鍵啟動
docker-compose up -d

# 4. 查看日誌
docker-compose logs -f potato-bot
```

### 手動 Docker 部署
```bash
# 構建映像
docker build -t potato-bot .

# 運行容器
docker run -d --name potato-bot --env-file .env -p 8080:8080 potato-bot
```

---

## 📊 啟動後驗證

### 1. 檢查 Bot 狀態
```bash
# 查看日誌
tail -f bot.log

# 使用健康檢查
make health-check
```

### 2. 測試 Discord 命令
在 Discord 中輸入：
```
/menu          # GUI 選單系統
/ticket        # 票券系統
/vote          # 投票系統
/help          # 幫助資訊
```

### 3. 訪問 Web 管理界面
```
http://localhost:8080     # 管理面板
http://localhost:8080/api/v1/docs  # API 文檔
```

---

## 🛠️ 故障排除

### 常見問題

#### 1. Python 版本錯誤
```bash
# 檢查版本
python --version

# 如果版本 < 3.10，請升級
# Ubuntu/Debian
sudo apt update && sudo apt install python3.11

# macOS (使用 Homebrew)
brew install python@3.11

# Windows
# 從 https://python.org 下載最新版本
```

#### 2. 依賴安裝失敗
```bash
# 更新 pip
python -m pip install --upgrade pip

# 重新安裝依賴
pip install -r requirements.txt --force-reinstall
```

#### 3. 資料庫連線失敗
```bash
# 檢查 MySQL 服務
sudo systemctl status mysql

# 測試連線
mysql -h localhost -u your_user -p

# 創建資料庫
mysql> CREATE DATABASE potato_bot CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
```

#### 4. Discord Bot 無法連線
- 檢查 Token 是否正確
- 確認 Bot 權限設定
- 檢查網路連線

#### 5. 端口被佔用
```bash
# 查看端口使用情況
netstat -tulpn | grep 8080

# 修改 API 端口
echo "LOCAL_API_PORT=8081" >> .env
```

---

## 🔗 有用的連結

### 📚 文檔
- [完整用戶手冊](docs/user-guides/USER_MANUAL.md)
- [命令列表](docs/user-guides/COMMANDS.md)
- [API 文檔](docs/API.md)

### 🛠️ 開發
- [開發環境設置](docs/DEVELOPMENT.md)
- [貢獻指南](CONTRIBUTING.md)
- [程式碼規範](docs/CODING_STANDARDS.md)

### 🆘 支援
- [GitHub Issues](https://github.com/Craig-0219/potato/issues)
- [GitHub Discussions](https://github.com/Craig-0219/potato/discussions)
- [Discord 社群](https://discord.gg/potato-bot)

---

## ⚡ 進階設定

### 內網部署模式
```env
# 內網環境配置
API_EXTERNAL_ACCESS=false
OFFLINE_MODE=true
LOCAL_CACHE_ONLY=true
```

### 高性能配置
```env
# 性能優化
DB_POOL_SIZE=20
REDIS_POOL_SIZE=10
API_WORKERS=4
```

### 安全性配置
```env
# 安全設定
ENABLE_API_AUTH=true
JWT_SECRET=your_secure_secret_key
RATE_LIMIT_ENABLED=true
```

---

## 🎉 啟動成功！

當您看到以下訊息時，代表 Potato Bot 已成功啟動：

```
✅ Bot 已登入：YourBot#1234 (ID: 123456789)
📊 已連接到 X 個伺服器
🌐 API 伺服器已整合啟動 - http://0.0.0.0:8080
📚 API 文檔位址: http://0.0.0.0:8080/api/v1/docs
```

🎮 **開始享受 Potato Bot 帶來的強大功能吧！**

---

<div align="center">

**需要幫助？**
[📖 查看文檔](docs/) | [💬 加入社群](https://discord.gg/potato-bot) | [🐛 回報問題](https://github.com/Craig-0219/potato/issues)

*Made with ❤️ for the gaming community*

</div>