# Potato Bot 專案結構

## 📁 專案目錄結構

```
potato/
├── 📁 bot/                    # 核心機器人程式
│   ├── 📁 api/               # FastAPI 後端服務
│   ├── 📁 cogs/              # Discord 指令模組
│   ├── 📁 db/                # 資料庫存取層
│   ├── 📁 services/          # 業務邏輯服務
│   ├── 📁 utils/             # 工具函數
│   ├── 📁 views/             # Discord UI 視圖
│   ├── 📁 ui/                # 使用者介面元件
│   └── 📄 main.py            # 程式進入點
├── 📁 shared/                # 共享模組
├── 📁 web-ui/                # Next.js 前端介面
├── 📁 docs/                  # 專案文檔
├── 📁 tests/                 # 測試檔案
├── 📁 scripts/               # 工具腳本
├── 📁 backups/               # 備份檔案
├── 📁 transcripts/           # 對話記錄
├── 📄 start.py               # 跨平台啟動器
├── 📄 start.sh               # Linux/macOS 啟動腳本
└── 📄 start.bat              # Windows 啟動腳本
```

## 🎯 核心模組說明

### Bot 核心 (`bot/`)
- **API**: RESTful API 服務，提供外部介面
- **Cogs**: Discord 指令和事件處理器
- **DB**: 資料庫操作和連接管理
- **Services**: 業務邏輯和系統服務
- **Utils**: 通用工具函數
- **Views**: Discord 互動式介面元件

### 前端界面 (`web-ui/`)
- Next.js 應用程式
- 響應式管理面板
- 實時數據顯示

### 文檔系統 (`docs/`)
- 用戶指南和開發文檔
- API 文檔和系統設計
- 已歸檔的歷史文檔

## 🚀 啟動方式

```bash
# 推薦 - 跨平台啟動器
python start.py

# Linux/macOS
./start.sh

# Windows
start.bat

# 傳統方式
python bot/main.py
```

## 📊 專案統計
- **程式碼行數**: ~175,000 行
- **Python 模組**: 162 個
- **Discord Cogs**: 33 個
- **API 端點**: 12+ 個
- **服務模組**: 43 個