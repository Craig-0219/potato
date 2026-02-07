# Potato Bot

Discord 多功能管理機器人（模組化、可擴充）。

## 功能模組

- 🎫 票券系統：面板建立/關閉、客服角色、聊天紀錄匯出
- 🗳️ 投票系統：建立投票、結果統計
- 🎲 抽獎系統：抽獎建立、管理與公告
- 🎵 音樂系統：Lavalink 播放與管理面板
- 🧾 履歷/招募系統：公司身分組、履歷投遞與審核
- 🗂️ 類別自動化：批量建立類別與管理權限
- 🤖 自動回覆：指定使用者自動回覆規則
- 🛂 入境審核：白名單審核與面板
- 👋 歡迎系統：入/退伺服器訊息
- 🪝 Webhook：事件轉發與管理
- 🛰️ FiveM 狀態播報：txAdmin 狀態面板與通知
- 🧰 系統管理面板：集中式設定 UI
- 🩺 健康檢查：服務狀態監控

## 系統需求

- Python 3.10+
- MySQL 8+
- Discord Bot Token

## 快速開始

```bash
# 1) 建立虛擬環境
python -m venv venv

# 2) 啟用虛擬環境
# Windows
venv\Scripts\activate
# macOS/Linux
source venv/bin/activate

# 3) 安裝依賴
pip install -r requirements.txt
```

建立 `.env`（放在專案根目錄）：

```bash
DISCORD_TOKEN=your_discord_bot_token
DB_HOST=localhost
DB_PORT=3306
DB_USER=your_db_user
DB_PASSWORD=your_db_password
DB_NAME=potato_bot
```

啟動機器人：

```bash
python src/potato_bot/main.py
```

首次啟動會自動建立資料表。

## 常用設定（可選）

```bash
LOG_LEVEL=INFO
DEBUG=false
SYNC_COMMANDS=true

TICKET_AUTO_REPLIES=true
TICKET_DEFAULT_AUTO_CLOSE_HOURS=24
TICKET_MAX_PER_USER=3
```

其他設定請參考 `src/potato_shared/config.py`。

## 音樂系統（Lavalink）

可在 **/admin → 音樂系統設定** 設定 Lavalink（優先使用後台設定，若未設定則回落 .env）。

```bash
LAVALINK_HOST=your_lavalink_host
LAVALINK_PORT=2333
LAVALINK_PASSWORD=your_lavalink_password
LAVALINK_SECURE=false
# 或直接使用完整 URI
# LAVALINK_URI=https://your_lavalink_host:443
```

## FiveM 狀態播報

請使用 **/admin → FiveM 狀態設定** 完成以下設定：

- `播報頻道`
- `info.json / players.json URL`（面板顯示用）
- `輪詢間隔`（秒，留空使用預設值）
- `狀態通知身分組 / DM 通知身分組`
- `伺服器連結`（狀態面板會顯示「🔗 連線伺服器」按鈕）
- `狀態圖片`
- `部署/更新狀態面板`

info.json / players.json 僅用於狀態面板顯示（玩家數、伺服器名稱），不會發送「上線 / 離線」通知。
需同時設定兩個 URL 才會啟用輪詢。

輪詢與狀態檔設定（仍使用環境變數）：

```bash
FIVEM_POLL_INTERVAL=3
FIVEM_OFFLINE_THRESHOLD=3
FIVEM_STARTING_GRACE_SECONDS=60
FIVEM_TXADMIN_STATUS_FILE=D:\\server\\txData\\QBBOX\\resources\\[01-核心系統]\\Potato_Discord_API\\data\\txadmin_status.json
FIVEM_RESTART_NOTIFY_SECONDS=600,300,180,120,60,10
```

備註：txAdmin 狀態檔讀取目前固定每 3 秒輪詢；API（info.json / players.json）則依上方輪詢間隔。

### txAdmin 狀態檔（FTP 讀取）

若 bot 無法直接存取檔案，可改用 FTP 讀取：

```bash
FIVEM_TXADMIN_FTP_HOST=your-ftp-host
FIVEM_TXADMIN_FTP_PORT=21
FIVEM_TXADMIN_FTP_USER=your-ftp-user
FIVEM_TXADMIN_FTP_PASSWORD=your-ftp-password
FIVEM_TXADMIN_FTP_PATH=/txData/QBBOX/resources/[01-核心系統]/Potato_Discord_API/data/txadmin_status.json
FIVEM_TXADMIN_FTP_PASSIVE=true
FIVEM_TXADMIN_FTP_TIMEOUT=10
```

## 票券系統常用指令

- `!setup_ticket`：建立票券面板
- `/ticket_settings`：管理票券設定（分類/客服角色/限額）
- `!ticket_help`：票券指令說明

## 專案結構

```
src/
  potato_bot/     # Bot 核心、Cogs、服務
  potato_shared/  # 共用工具與設定
```

## 相關文件

- `Potato Bot Core 公開 API 規格 v1.md`

## 授權

MIT
