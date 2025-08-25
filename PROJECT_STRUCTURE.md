# 🏗️ Potato Bot 專案結構說明

> **遊戲社群管理平台架構** - Discord & Minecraft 深度整合

---

## 📁 核心專案結構

```
potato/
├── 📋 專案文檔
│   ├── README.md                           # 專案主要說明
│   ├── CHANGELOG.md                        # 版本更新記錄
│   ├── COMMUNITY_GAMING_DEVELOPMENT_PLAN.md # 遊戲社群開發計畫
│   ├── NEXT_DEVELOPMENT_PLAN.md            # 舊開發計畫 (已更新)
│   └── PROJECT_STRUCTURE.md                # 本文件 - 專案結構說明
│
├── 🤖 Bot 核心程式
│   ├── bot/                         # Python Discord Bot 主程式
│   │   ├── main.py                  # 程式進入點
│   │   ├── cogs/                    # 功能模組 (Discord 社群功能)
│   │   ├── services/                # 業務邏輯服務 (遊戲社群服務)
│   │   ├── minecraft/               # Minecraft 整合模組 (新增)
│   │   │   ├── mc_bridge.py         # MC 聊天橋接器
│   │   │   ├── server_monitor.py    # 伺服器監控
│   │   │   └── whitelist_manager.py # 白名單管理
│   │   ├── gaming/                  # 遊戲功能模組 (新增)
│   │   │   ├── lfg_system.py        # 尋找隊友系統
│   │   │   ├── tournament.py        # 競賽系統
│   │   │   └── leaderboard.py       # 排行榜
│   │   ├── db/                      # 資料庫存取層 (18個 DAO)
│   │   ├── utils/                   # 工具函數庫
│   │   ├── views/                   # UI 互動介面
│   │   ├── ui/                      # 上下文感知UI系統
│   │   └── locales/                 # 多語言支援
│   │
│   ├── api/                         # RESTful API 服務
│   │   ├── app.py                   # Flask API 主程式
│   │   ├── routes/                  # API 路由 (8個模組)
│   │   ├── auth.py                  # 認證系統
│   │   ├── models.py                # 資料模型
│   │   └── realtime_api.py          # 即時API支援
│   │
│   └── shared/                      # 共享模組
│       ├── config.py                # 配置管理
│       ├── logger.py                # 日誌系統
│       ├── cache_manager.py         # 快取管理
│       ├── db_optimizer.py          # 資料庫優化
│       ├── enums.py                 # 列舉定義
│       └── prometheus_metrics.py    # 監控指標
│
├── 🌐 Web 管理介面
│   └── web-ui/                      # Next.js 管理面板
│       ├── src/app/                 # App Router 頁面 (9個頁面)
│       ├── src/components/          # React 組件庫
│       ├── src/lib/                 # 工具庫和配置
│       ├── package.json             # 前端依賴管理
│       └── next.config.js           # Next.js 配置
│
├── 📚 文檔系統
│   └── docs/                        # 統一文檔中心
│       ├── user-guides/             # 使用者指南 (3個指南)
│       ├── system/                  # 系統文檔 (3個系統文檔)
│       ├── requirements/            # 需求文件 (3個需求文件)
│       ├── development/             # 開發文檔
│       ├── phase-archive/           # 階段計畫封存
│       ├── archived/                # 項目完成文檔 (15個)
│       ├── CROSS_PLATFORM_ECONOMY_PLAN.md
│       ├── ZIENTIS_INTEGRATION_PLAN.md
│       ├── MINECRAFT_PLUGIN_ARCHITECTURE.md
│       └── README.md                # 文檔中心索引
│
├── 💾 資料與備份
│   ├── backups/                     # 系統備份 (3個最新備份)
│   ├── transcripts/                 # 票券對話記錄
│   ├── health_check.json           # 健康檢查狀態
│   └── requirements*.txt           # Python 依賴清單
│
├── 🗂️ 整理區域
│   └── archive/                     # 已整理的舊檔案
│       ├── temp-files/              # 暫時檔案
│       ├── old-logs/                # 舊日誌檔案
│       └── old-tokens/              # 舊認證檔案
│
└── 🔧 支援檔案
    ├── monitor_bot.py               # Bot 監控腳本
    ├── create_missing_tables.sql   # 資料庫初始化
    └── docs/phase-archive/          # 階段性計畫封存
```

---

## 🎯 專案瘦身成果

### ✅ **已清理項目**
- **臨時檔案**: `fix_oauth_temp.md`, `test_fallback.py`, `check_commands.py` → `archive/temp-files/`
- **舊日誌**: `bot.log`, `bot_output.log` → `archive/old-logs/`
- **測試檔案**: `token_response*.json`, `ticket_test.json` → `archive/old-tokens/`
- **舊階段計畫**: `PHASE7_DEVELOPMENT_PLAN.md` → `docs/phase-archive/`
- **移除移動應用**: 暫不開發的 `mobile-app/` 目錄

### 📊 **瘦身統計**
- **移除檔案**: 8個暫時/測試檔案
- **整理歸檔**: 15個舊文檔和日誌
- **保留核心**: 所有必要的業務邏輯和功能
- **結構優化**: 清晰的分層架構

---

## 🏗️ 核心架構分析

### 🤖 **Bot 核心層** (Python)
```
Discord 社群功能模組:
├── 核心功能: ticket_core, vote_core, ai_core
├── 管理功能: security_core, system_admin_core
├── 遊戲功能: game_core, lottery_core
└── 社群功能: welcome_core, automation_core

遊戲社群服務:
├── Minecraft 整合: mc_bridge, server_monitor, whitelist_manager
├── 遊戲功能: lfg_system, tournament, leaderboard
├── AI 服務: ai_manager, conversation_manager, intent_recognition
└── 社群服務: ticket_manager, vote_manager, welcome_manager
```

### 🌐 **Web 介面層** (Next.js)
```
9個主要頁面:
├── 認證: /auth/discord, /auth/success, /auth/error
├── 管理: /dashboard, /tickets, /votes
├── 系統: /analytics, /system-monitor, /api-management
└── Bot管理: /bot-management

完整組件系統:
├── UI組件: button, card, badge, spinner, tabs
├── 業務組件: bot-connection-status, landing-page, navbar
└── 服務層: auth-context, websocket-provider, api-client
```

### 💾 **資料存取層** (Database)
```
18個 DAO 資料存取:
├── 核心: ticket_dao, vote_dao, security_dao
├── 功能: ai_dao, automation_dao, webhook_dao
├── 管理: archive_dao, language_dao, workflow_dao
└── 系統: base_dao, database_manager, pool
```

---

## 🚀 下階段發展重點

### 🎯 **遊戲社群發展目標**
1. **⛏️ Minecraft 深度整合**: 伺服器監控、聊天橋接、白名單管理
2. **🎮 遊戲社群工具**: LFG 系統、競賽管理、排行榜
3. **🤖 智能社群管理**: AI 輔助審核、自動配對、內容分析
4. **📊 社群數據分析**: 玩家行為追蹤、社群健康度監控

### 📊 **技術基礎強化**
- **測試體系**: 完善的 pytest 測試框架 (已完成)
- **代碼品質**: black, flake8, mypy 工具整合 (已完成)
- **Minecraft 整合**: WebSocket 即時通訊架構
- **遊戲數據**: 跨平台玩家數據同步系統

---

## 🛡️ 維護指南

### 📋 **定期維護任務**
- **每週**: 備份檔案清理 (保留最近7天)
- **每月**: 對話記錄封存 (transcripts 30天以上)
- **每季**: 程式碼審查和重構
- **每年**: 依賴更新和安全審核

### 🔍 **監控指標**
- **系統健康**: `health_check.json` 狀態檢查
- **效能監控**: Prometheus 指標收集
- **錯誤追蹤**: 日誌分析和告警
- **用戶體驗**: Web 介面效能監控

---

<div align="center">

**🎮 遊戲社群 • Discord 整合 • Minecraft 專精**

*專為遊戲社群設計的 Potato Bot 架構*

---

*📅 結構更新: 2025-08-25*  
*🎯 目標定位: Discord & Minecraft 社群管理平台*

</div>