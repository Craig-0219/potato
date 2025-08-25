# Potato Bot - Pterodactyl 部署版本

這是 Potato Bot 的精簡部署版本，專為 Pterodactyl 托管平台優化。

## 檔案結構

```
.
├── bot.py              # Pterodactyl 啟動入口點
├── bot/
│   ├── __init__.py     # 模組初始化
│   └── main.py         # 主程式
├── shared/
│   ├── __init__.py     # 共享模組初始化
│   ├── config.py       # 配置管理
│   └── logger.py       # 日誌系統
└── requirements.txt    # Python 依賴
```

## 部署步驟

### 1. Pterodactyl 設定

1. 創建新的 Python 伺服器
2. 設定啟動指令：`python bot.py`
3. 上傳此分支的所有檔案

### 2. 環境變數設定

在 Pterodactyl 面板設定以下環境變數：

```
DISCORD_TOKEN=你的機器人token
LOG_LEVEL=INFO
```

### 3. 啟動機器人

直接啟動伺服器，機器人會自動執行基本功能檢查並啟動。

## 功能說明

此精簡版本包含：
- ✅ Discord 機器人基本功能
- ✅ Ping/Pong 測試
- ✅ 機器人資訊顯示
- ✅ 幫助指令
- ✅ Slash Commands 支援
- ✅ 日誌記錄

## 注意事項

- 這是精簡版本，僅包含核心功能
- 不包含資料庫相關功能
- 適合快速部署和測試
- 可作為擴展功能的基礎

## 版本資訊

- 版本：v3.2.0-minimal
- 平台：Pterodactyl 優化
- Python 版本：3.8+