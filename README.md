# 🥔 Potato Bot - 託管部署版

<div align="center">

[![Version](https://img.shields.io/badge/version-3.1.0-blue.svg)](VERSION)
[![Discord Bot](https://img.shields.io/badge/Discord-Bot-7289DA.svg)](https://discord.com)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Production Ready](https://img.shields.io/badge/production-ready-brightgreen.svg)](#-生產環境)

**全功能 Discord 社群管理機器人**

*現代化架構 • AI 整合 • 生產就緒*

</div>

## 🚀 快速部署

### 生產環境要求
- Python 3.10+
- MySQL 8.0+ 或 PostgreSQL 13+
- Redis 7.0+ (推薦)

### 一鍵部署

```bash
# 1. 下載並配置
git clone https://github.com/Craig-0219/potato.git
cd potato
cp .env.example .env

# 2. 編輯配置文件
nano .env
# 設置您的 DISCORD_TOKEN, DB_* 等配置

# 3. 安裝依賴並啟動
pip install -r requirements.txt
python start.py
```

## 🎯 核心功能

| 功能模組 | 描述 | 生產狀態 |
|---------|------|----------|
| 🎫 **票券系統** | 智能客服、自動分配、SLA 監控 | ✅ 穩定運行 |
| 🗳️ **投票系統** | 多種模式、實時統計、權限控制 | ✅ 穩定運行 |
| 🤖 **AI 助手** | 多平台整合、智能對話、內容審核 | ✅ 穩定運行 |
| 💰 **經濟系統** | 虛擬貨幣、積分獎勵、交易記錄 | ✅ 穩定運行 |
| 🌐 **Web 面板** | 管理介面、實時監控 | 🚧 開發中 |

## 📁 專案結構

```
potato/
├── bot/                # Discord 機器人核心
├── shared/             # 共用模組和工具
├── docs/               # 用戶和管理文檔
├── start.py            # 主要啟動腳本
├── .env.example        # 環境變數範例
└── requirements.txt    # 生產依賴清單
```

## ⚙️ 配置說明

### 必要配置
```bash
# Discord 設定
DISCORD_TOKEN=your_bot_token_here
DISCORD_GUILD_ID=your_server_id

# 資料庫配置  
DB_HOST=localhost
DB_USER=potato_bot
DB_PASSWORD=secure_password
DB_NAME=potato_bot

# 基本設定
ENVIRONMENT=production
DEBUG=false
```

### 可選功能
```bash
# Redis 快取 (提升效能)
REDIS_URL=redis://localhost:6379/0

# AI 服務 (可選)
OPENAI_API_KEY=your_openai_key
ANTHROPIC_API_KEY=your_anthropic_key
GEMINI_API_KEY=your_gemini_key
```

完整配置說明請參考 [.env.example](.env.example)

## 📚 文檔指南

### 👥 使用者文檔
- **[用戶指南](docs/user-guide/README.md)** - 功能使用說明
- **[管理指南](docs/admin-guide/README.md)** - 系統管理配置

### 🚀 部署文檔  
- **[部署指南](docs/deployment/README.md)** - 多環境部署方案
- **[生產部署詳細指南](README.prod.md)** - 完整生產環境配置

### 🔌 開發者資源
- **[API 文檔](docs/api/README.md)** - RESTful API 參考

## 🛡️ 生產環境特性

- ✅ **高可用性**: 支援負載均衡和故障轉移
- ✅ **安全加固**: 完整的安全配置和監控
- ✅ **效能優化**: Redis 快取和資料庫優化
- ✅ **監控告警**: 完整的日誌和監控系統
- ✅ **自動備份**: 資料庫和配置自動備份

## 📊 系統狀態

| 組件 | 狀態 | 版本 |
|------|------|------|
| Discord Bot | 🟢 運行中 | 3.1.0 |
| API 服務 | 🟢 運行中 | 3.1.0 |
| 資料庫 | 🟢 正常 | MySQL 8.0+ |
| 快取系統 | 🟢 正常 | Redis 7.0+ |

## 🆘 支援

- 🐛 **問題回報**: [GitHub Issues](https://github.com/Craig-0219/potato/issues)
- 📖 **完整文檔**: [文檔中心](docs/index.md)
- 💬 **技術支援**: support@potato-bot.com

## 📄 授權

本專案使用 [MIT 授權](LICENSE)。

---

<div align="center">

**準備部署？** [查看部署指南](docs/deployment/README.md) • [生產環境配置](README.prod.md)

*適用於生產環境的穩定版本*

</div>
