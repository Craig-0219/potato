# Potato Bot

Discord 多功能管理機器人（模組化、可擴充）。

## 功能模組

- 🎫 票券系統：建立/關閉、優先級、客服角色、聊天紀錄匯出
- 🗳️ 投票系統：建立投票、結果統計
- 🪝 Webhook：事件轉發與管理
- 👋 社群管理：歡迎訊息、白名單、健康檢查
- 🎲 娛樂功能：抽獎、遊戲、音樂
- 💰 經濟/簽到：與遊戲系統整合的點數與成就

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

## 票券系統常用指令

- `!setup_ticket`：建立票券面板
- `/ticket_settings`：管理票券設定（分類/客服角色/限額）
- `/my_tickets`：查看自己的票券
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
