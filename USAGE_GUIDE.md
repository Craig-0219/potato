# 🥔 Potato Bot 完整使用指南

> **全功能 Discord 機器人部署與使用手冊**

## 📋 目錄

- [快速開始](#-快速開始)
- [系統需求](#-系統需求)  
- [安裝與配置](#-安裝與配置)
- [功能詳解](#-功能詳解)
- [管理面板](#-管理面板)
- [常見問題](#-常見問題)
- [維護指南](#-維護指南)

---

## 🚀 快速開始

### 1. 準備工作
```bash
# 克隆專案
git clone -b ptero https://github.com/Craig-0219/potato.git
cd potato

# 安裝依賴
pip install -r requirements.txt
```

### 2. 基本配置
```bash
# 複製環境配置
cp .env.example .env

# 編輯配置文件
nano .env
```

### 3. 啟動機器人
```bash
# 標準啟動
python start.py

# 或使用批次檔案（Windows）
start.bat

# 或使用腳本（Linux/macOS）
./start.sh
```

---

## 💻 系統需求

### 最低配置
- **作業系統**: Windows 10+ / Ubuntu 20.04+ / macOS 11+
- **Python**: 3.10 或更高版本
- **記憶體**: 512MB RAM
- **處理器**: 1 核心 CPU
- **存儲空間**: 2GB 可用空間
- **網路**: 穩定的網際網路連線

### 建議配置  
- **記憶體**: 1GB+ RAM
- **處理器**: 2+ 核心 CPU
- **存儲空間**: 5GB+ 可用空間
- **網路**: 高速穩定連線

---

## ⚙️ 安裝與配置

### 環境變數配置

#### 🤖 Discord 配置（必填）
```env
# 機器人基本設定
DISCORD_TOKEN=你的機器人令牌
DISCORD_CLIENT_ID=你的客戶端ID  
DISCORD_CLIENT_SECRET=你的客戶端密鑰
DISCORD_GUILD_ID=你的伺服器ID

# 角色管理
DISCORD_ADMIN_ROLE_IDS=管理員角色ID1,管理員角色ID2
DISCORD_STAFF_ROLE_IDS=工作人員角色ID1,工作人員角色ID2
```

#### 🗄️ 資料庫設定（必填）
```env
DB_HOST=localhost          # 資料庫主機
DB_PORT=3306              # 資料庫端口
DB_USER=用戶名             # 資料庫用戶
DB_PASSWORD=密碼          # 資料庫密碼
DB_NAME=potato_bot        # 資料庫名稱
```

#### 🔒 安全與 API
```env
JWT_SECRET=至少32字元的安全密鑰
ENABLE_API_SERVER=true    # 啟用API伺服器
API_PORT=8000            # API端口
```

### 託管平台部署

#### 🦕 Pterodactyl Panel
1. **上傳檔案**: 將專案檔案上傳到伺服器
2. **設定啟動指令**: `python start.py`  
3. **配置環境變數**: 在面板中設定必要的環境變數
4. **分配資源**: 建議至少 1GB RAM 和 1 CPU 核心

#### 🐳 Docker 部署
```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY . .
RUN pip install -r requirements.txt
EXPOSE 8000
CMD ["python", "start.py"]
```

```bash
# 構建映像
docker build -t potato-bot .

# 運行容器
docker run -d --name potato-bot \
  -e DISCORD_TOKEN=你的令牌 \
  -e DB_HOST=你的資料庫主機 \
  -p 8000:8000 \
  potato-bot
```

---

## 🎯 功能詳解

### 🎫 票券系統

#### 基本使用
- `/ticket create` - 創建新票券
- `/ticket close` - 關閉當前票券
- `/ticket claim` - 認領票券處理權
- `/ticket rate` - 為服務評分

#### 管理功能
- **自動分配**: 根據類別自動分配處理人員
- **SLA 監控**: 追蹤響應時間和處理效率
- **評分系統**: 用戶滿意度反饋機制
- **統計分析**: 詳細的數據報表

#### 配置選項
```env
TICKET_AUTO_ASSIGNMENT=true           # 自動分配
TICKET_SLA_MONITORING=true           # SLA監控
TICKET_DEFAULT_SLA_MINUTES=60        # 預設SLA時間
TICKET_MAX_PER_USER=3               # 每用戶最大票券數
```

### 🤖 AI 整合

#### 支援的 AI 服務
- **OpenAI** (GPT-3.5/4): 對話和文本生成
- **Anthropic** (Claude): 智能分析和對話  
- **Google Gemini**: 多模態AI支援

#### 使用指令
- `/ai chat <訊息>` - AI對話
- `/ai analyze <內容>` - 內容分析
- `/ai sentiment <文本>` - 情感分析

#### 使用限制
```env
AI_MAX_TOKENS=4000                   # 最大令牌數
AI_DAILY_FREE_QUOTA=10              # 每日免費額度
AI_RATE_LIMIT_USER=10               # 用戶速率限制
```

### 💰 經濟系統

#### 基本功能
- 虛擬貨幣管理
- 每日簽到獎勵
- 服務消費扣費
- 餘額查詢

#### 使用指令
- `/economy balance` - 查看餘額
- `/economy daily` - 領取每日獎勵
- `/economy transfer @用戶 金額` - 轉帳
- `/economy history` - 交易記錄

#### 系統設定
```env
ECONOMY_ENABLED=true                 # 啟用經濟系統
ECONOMY_STARTING_COINS=1000         # 起始金幣
ECONOMY_DAILY_BONUS=100            # 每日獎勵
```

### 🎵 音樂與娛樂

#### 音樂功能
- `/music play <歌曲>` - 播放音樂
- `/music queue` - 查看播放列表
- `/music skip` - 跳過當前歌曲
- `/music volume <0-100>` - 調整音量

#### 遊戲功能
- 小遊戲集成
- 娛樂互動指令
- 隨機事件系統

#### 配置選項
```env
YOUTUBE_API_KEY=你的YouTube API密鑰
MUSIC_MAX_QUEUE_SIZE=50             # 最大播放列表長度
MUSIC_DAILY_FREE_QUOTA=20          # 每日免費播放次數
```

---

## 📊 管理面板

### 健康檢查
訪問 `http://你的伺服器:8000/health` 查看系統狀態：
- 機器人連線狀態
- 資料庫連接狀態  
- API 伺服器狀態
- 記憶體使用情況

### 監控指標
- **延遲監控**: Discord API 響應時間
- **錯誤追蹤**: 自動記錄系統錯誤
- **使用統計**: 指令使用頻率分析
- **資源監控**: CPU 和記憶體使用率

### 日誌管理
```bash
# 查看實時日誌
tail -f bot.log

# 搜尋錯誤日誌
grep "ERROR" bot.log

# 清理舊日誌（建議定期執行）
find . -name "*.log" -mtime +7 -delete
```

---

## ❓ 常見問題

### 連接問題

**Q: 機器人無法連接到 Discord**
```
A: 檢查以下項目：
1. DISCORD_TOKEN 是否正確
2. 機器人是否已加入伺服器
3. 機器人權限是否充足
4. 網路連接是否正常
```

**Q: 資料庫連接失敗**
```
A: 確認資料庫配置：
1. DB_HOST、DB_USER、DB_PASSWORD 是否正確
2. 資料庫服務是否運行
3. 防火牆是否允許連接
4. 資料庫用戶權限是否充足
```

### 功能問題

**Q: AI 功能無法使用**
```
A: 檢查API密鑰設定：
1. OPENAI_API_KEY 等是否已設定
2. API 配額是否已用完
3. API 密鑰是否有效
4. 網路是否能訪問 API 服務
```

**Q: 音樂功能不工作**
```
A: 確認以下設定：
1. YOUTUBE_API_KEY 是否正確
2. 機器人是否有語音頻道權限
3. FFmpeg 是否已安裝
4. 語音頻道是否可用
```

### 性能問題

**Q: 機器人響應緩慢**
```
A: 優化建議：
1. 增加伺服器記憶體
2. 檢查資料庫性能
3. 啟用 Redis 快取
4. 檢查網路延遲
```

**Q: 記憶體使用過高**
```
A: 解決方法：
1. 重啟機器人服務
2. 清理日誌檔案
3. 優化資料庫查詢
4. 檢查記憶體洩漏
```

---

## 🔧 維護指南

### 日常維護

#### 每日檢查
- [ ] 檢查機器人運行狀態
- [ ] 查看錯誤日誌
- [ ] 監控資源使用
- [ ] 檢查用戶反饋

#### 每週維護
- [ ] 清理舊日誌檔案
- [ ] 更新依賴套件
- [ ] 備份資料庫
- [ ] 檢查安全更新

### 更新流程

#### 安全更新
```bash
# 備份當前版本
cp -r . ../potato-backup-$(date +%Y%m%d)

# 拉取最新代碼
git pull origin ptero

# 更新依賴
pip install -r requirements.txt --upgrade

# 重啟服務
python start.py
```

#### 版本升級
1. **備份資料**: 完整備份資料庫和配置文件
2. **測試環境**: 在測試環境中驗證新版本
3. **漸進部署**: 分步驟升級，確保服務穩定
4. **回滾準備**: 準備快速回滾方案

### 備份策略

#### 資料庫備份
```bash
# 每日備份腳本
mysqldump -u $DB_USER -p$DB_PASSWORD $DB_NAME > backup_$(date +%Y%m%d).sql

# 自動備份（加入 crontab）
0 2 * * * /path/to/backup_script.sh
```

#### 檔案備份
```bash
# 備份配置和日誌
tar -czf potato_backup_$(date +%Y%m%d).tar.gz .env *.log

# 雲端同步（可選）
rclone copy . remote:potato-backup/
```

### 監控告警

#### 系統監控
- **CPU 使用率**: 超過 80% 時告警
- **記憶體使用**: 超過 85% 時告警  
- **磁碟空間**: 剩餘不足 1GB 時告警
- **網路延遲**: 超過 500ms 時告警

#### 服務監控
- **Discord 連接**: 斷線時立即告警
- **資料庫狀態**: 連接失敗時告警
- **API 健康度**: 錯誤率超過 5% 時告警

---

## 📞 技術支援

### 支援管道
- 🐛 **問題回報**: [GitHub Issues](https://github.com/Craig-0219/potato/issues)
- 💬 **社群支援**: Discord 伺服器
- 📧 **技術諮詢**: 透過官方管道聯繫

### 提交問題時請包含
1. **系統資訊**: 作業系統、Python 版本
2. **錯誤訊息**: 完整的錯誤日誌
3. **重現步驟**: 詳細的操作步驟
4. **配置資訊**: 相關的環境變數設定（遮蔽敏感資訊）

---

## 🎉 結語

Potato Bot 是一個功能豐富且高度可客製化的 Discord 機器人。正確的配置和定期維護將確保最佳的使用體驗。

如有任何問題或建議，歡迎透過官方管道與我們聯繫！

**Happy Botting! 🥔**