# 📁 Potato Bot - 專案目錄結構

> **Discord & Minecraft 社群管理平台架構**  
> **更新時間**: 2025-08-25

---

## 🏗️ 根目錄結構

```
potato/
├── 📋 **專案文檔**
│   ├── PROJECT_STRUCTURE.md                 # 專案架構說明
│   ├── PROJECT_DIRECTORY_STRUCTURE.md       # 本文件 - 目錄結構
│   ├── COMMUNITY_GAMING_DEVELOPMENT_PLAN.md # 遊戲社群開發計畫
│   ├── NEXT_DEVELOPMENT_PLAN.md             # 舊開發計畫 (已更新)
│   ├── CHANGELOG.md                         # 版本更新記錄
│   └── README.md                            # 專案主要說明
│
├── 🤖 **Bot 核心程式**
│   ├── bot/                              # Python Discord Bot
│   │   ├── minecraft/                    # Minecraft 整合模組
│   │   └── gaming/                       # 遊戲功能模組
│   ├── api/                             # RESTful API 服務
│   └── shared/                          # 共享模組
│
├── 🌐 **Web 管理介面**
│   └── web-ui/                          # Next.js 管理面板
│
├── 📚 **統一文檔中心**
│   └── docs/                            # 所有項目文檔
│
├── 💾 **資料與備份**
│   ├── backups/                         # 系統備份檔案
│   ├── transcripts/                     # 票券對話記錄
│   └── health_check.json               # 系統健康狀態
│
├── 🗂️ **整理區域**
│   └── archive/                         # 已整理的舊檔案
│
├── ⚙️ **配置檔案**
│   ├── .gitignore                       # Git 版本控制忽略
│   ├── .env.example                     # 環境變數範本
│   ├── requirements.txt                 # Python 主要依賴
│   ├── requirements-api.txt             # API 服務依賴
│   └── create_missing_tables.sql        # 資料庫初始化
│
└── 🔧 **支援檔案**
    └── monitor_bot.py                   # Bot 監控腳本
```

---

## 🤖 Bot 核心程式詳細結構

### 📂 **bot/** - Python Discord Bot
```
bot/
├── main.py                             # 程式進入點
├── 🧩 cogs/                            # 功能模組 (25個)
│   ├── __init__.py
│   ├── ai_assistant_core.py            # AI 助手核心
│   ├── ai_core.py                      # AI 功能
│   ├── automation_core.py              # 自動化系統
│   ├── cached_ticket_core.py           # 票券快取
│   ├── content_analysis_core.py        # 內容分析
│   ├── cross_platform_economy_core.py # 跨平台經濟 (遊戲用)
│   ├── dashboard_core.py               # 儀表板
│   ├── entertainment_core.py           # 娛樂功能
│   ├── fallback_commands.py            # 後備指令
│   ├── game_core.py                    # 遊戲核心功能
│   ├── guild_management_core.py        # 伺服器管理
│   ├── image_tools_core.py             # 圖像工具
│   ├── language_core.py                # 語言系統
│   ├── lottery_core.py                 # 抽獎系統
│   ├── menu_core.py                    # 選單系統
│   ├── music_core.py                   # 音樂播放
│   ├── security_admin_core.py          # 安全管理
│   ├── security_core.py                # 安全核心
│   ├── system_admin_core.py            # 系統管理
│   ├── ticket_core.py                  # 票券系統
│   ├── ticket_listener.py              # 票券監聽器
│   ├── vote_core.py                    # 投票系統
│   ├── vote_listener.py                # 投票監聽器
│   ├── web_auth_core.py                # Web 認證
│   ├── webhook_core.py                 # Webhook 管理
│   ├── welcome_core.py                 # 歡迎系統
│   ├── welcome_listener.py             # 歡迎監聽器
│   └── workflow_core.py                # 工作流程
│
├── 🎮 minecraft/                      # Minecraft 整合模組 (新增)
│   ├── mc_bridge.py                 # Discord-MC 聊天橋接
│   ├── server_monitor.py            # 伺服器狀態監控
│   ├── whitelist_manager.py         # 白名單自動管理
│   └── economy_sync.py              # 經濟系統同步
│
├── 🎯 gaming/                         # 遊戲功能模組 (新增)
│   ├── lfg_system.py                # 尋找隊友 (LFG) 系統
│   ├── tournament.py                # 競賽和錦標賽管理
│   ├── leaderboard.py               # 多維度排行榜
│   └── streaming.py                 # 直播整合 (Twitch/YouTube)
│
├── 🗄️ db/                              # 資料庫存取層 (18個 DAO)
│   ├── __init__.py
│   ├── ai_dao.py                       # AI 資料存取
│   ├── archive_dao.py                  # 封存資料
│   ├── assignment_dao.py               # 任務指派
│   ├── automation_dao.py               # 自動化資料
│   ├── base_dao.py                     # 基礎 DAO
│   ├── cached_ticket_dao.py            # 票券快取 DAO
│   ├── database_manager.py             # 資料庫管理器
│   ├── language_dao.py                 # 語言設定
│   ├── lottery_dao.py                  # 抽獎資料
│   ├── migrations/                     # 資料庫遷移
│   │   ├── guild_management_tables.py
│   │   └── security_tables.py
│   ├── pool.py                         # 連接池
│   ├── secure_ticket_dao.py            # 安全票券 DAO
│   ├── security_dao.py                 # 安全資料
│   ├── tag_dao.py                      # 標籤資料
│   ├── ticket_dao.py                   # 票券資料
│   ├── vote_dao.py                     # 投票資料
│   ├── vote_template_dao.py            # 投票模板
│   ├── webhook_dao.py                  # Webhook 資料
│   ├── welcome_dao.py                  # 歡迎資料
│   └── workflow_dao.py                 # 工作流程資料
│
├── 🛠️ services/                       # 業務邏輯服務 (28個)
│   ├── achievement_manager.py          # 成就管理
│   ├── ai/                            # AI 服務模組
│   │   ├── __init__.py
│   │   ├── ai_engine_manager.py       # AI 引擎管理
│   │   ├── conversation_manager.py    # 對話管理
│   │   └── intent_recognition.py      # 意圖識別
│   ├── ai_assistant.py                # AI 助手服務
│   ├── ai_manager.py                  # AI 管理器
│   ├── api_manager.py                 # API 管理
│   ├── assignment_manager.py          # 任務分配管理
│   ├── auth_manager.py                # 認證管理
│   ├── automation_engine.py           # 自動化引擎
│   ├── backup_service.py              # 備份服務
│   ├── chat_transcript_manager.py     # 對話記錄管理
│   ├── content_analyzer.py            # 內容分析器
│   ├── cross_platform_economy.py     # 跨平台經濟 (遊戲用)
│   ├── dashboard_manager.py           # 儀表板管理
│   ├── data_cleanup_manager.py        # 資料清理管理
│   ├── data_export_manager.py         # 資料匯出管理
│   ├── data_management_service.py     # 資料管理服務
│   ├── database_cleanup_manager.py    # 資料庫清理
│   ├── economy_manager.py             # 經濟系統管理
│   ├── game_manager.py                # 遊戲管理
│   ├── guild_analytics_service.py     # 伺服器分析服務
│   ├── guild_manager.py               # 伺服器管理
│   ├── guild_permission_manager.py    # 權限管理
│   ├── image_processor.py             # 圖像處理
│   ├── language_manager.py            # 語言管理
│   ├── lottery_manager.py             # 抽獎管理
│   ├── maintenance_scheduler.py       # 維護排程
│   ├── music_player.py                # 音樂播放器
│   ├── realtime_sync_manager.py       # 即時同步管理
│   ├── security/                      # 安全服務模組
│   │   ├── api_security.py           # API 安全
│   │   ├── audit_manager.py          # 審計管理
│   │   ├── mfa_manager.py            # 多因素認證
│   │   └── rbac_manager.py           # 角色權限管理
│   ├── security_audit_manager.py      # 安全審計管理
│   ├── statistics_manager.py          # 統計管理
│   ├── system_monitor.py              # 系統監控
│   ├── tag_manager.py                 # 標籤管理
│   ├── ticket_manager.py              # 票券管理
│   ├── vote_template_manager.py       # 投票模板管理
│   ├── webhook_manager.py             # Webhook 管理
│   ├── welcome_manager.py             # 歡迎管理
│   └── workflow_engine.py             # 工作流程引擎
│
├── 🖥️ ui/                             # 使用者介面
│   ├── __init__.py
│   ├── context_awareness.py           # 上下文感知
│   └── menu_system.py                 # 選單系統
│
├── 🔧 utils/                          # 工具函數庫
│   ├── embed_builder.py               # 嵌入訊息建構器
│   ├── error_handler.py               # 錯誤處理器
│   ├── helper.py                      # 輔助函數
│   ├── interaction_helper.py          # 互動輔助器
│   ├── localization.py                # 本地化工具
│   ├── multi_tenant_security.py      # 多租戶安全
│   ├── ticket_constants.py            # 票券常數
│   ├── ticket_utils.py                # 票券工具
│   └── vote_utils.py                  # 投票工具
│
├── 🎨 views/                          # UI 互動介面 (17個)
│   ├── __init__.py
│   ├── ai_assistant_views.py          # AI 助手視圖
│   ├── ai_views.py                    # AI 視圖
│   ├── automation_views.py            # 自動化視圖
│   ├── content_analysis_views.py      # 內容分析視圖
│   ├── dashboard_views.py             # 儀表板視圖
│   ├── entertainment_views.py         # 娛樂視圖
│   ├── game_views.py                  # 遊戲視圖
│   ├── image_tools_views.py           # 圖像工具視圖
│   ├── lottery_dashboard_views.py     # 抽獎儀表板視圖
│   ├── lottery_views.py               # 抽獎視圖
│   ├── music_views.py                 # 音樂視圖
│   ├── security_management_views.py   # 安全管理視圖
│   ├── security_views.py              # 安全視圖
│   ├── system_admin_views.py          # 系統管理視圖
│   ├── ticket_views.py                # 票券視圖
│   ├── vote_template_views.py         # 投票模板視圖
│   ├── vote_views.py                  # 投票視圖
│   ├── webhook_views.py               # Webhook 視圖
│   └── workflow_views.py              # 工作流程視圖
│
├── 🌍 locales/                        # 多語言支援 (5種語言)
│   ├── en.json                        # 英文
│   ├── ja.json                        # 日文
│   ├── ko.json                        # 韓文
│   ├── zh-CN.json                     # 簡體中文
│   └── zh-TW.json                     # 繁體中文
│
└── 📝 transcripts/                    # 空目錄(對話記錄)
```

### 📂 **api/** - RESTful API 服務
```
api/
├── app.py                             # Flask API 主程式
├── auth.py                           # 認證系統
├── models.py                         # 資料模型
├── realtime_api.py                   # 即時 API 支援
└── routes/                           # API 路由 (8個模組)
    ├── __init__.py
    ├── analytics.py                  # 分析 API
    ├── automation.py                 # 自動化 API
    ├── economy.py                    # 經濟系統 API
    ├── oauth.py                      # OAuth API
    ├── security.py                   # 安全 API
    ├── system.py                     # 系統 API
    └── tickets.py                    # 票券 API
```

### 📂 **shared/** - 共享模組
```
shared/
├── __init__.py
├── cache_manager.py                  # 快取管理
├── config.py                         # 配置管理
├── db_optimizer.py                   # 資料庫優化
├── enums.py                         # 列舉定義
├── logger.py                        # 日誌系統
└── prometheus_metrics.py            # 監控指標
```

---

## 🌐 Web UI 詳細結構

### 📂 **web-ui/** - Next.js 管理面板
```
web-ui/
├── 📦 **配置檔案**
│   ├── next.config.js               # Next.js 配置
│   ├── package.json                 # NPM 依賴管理
│   ├── package-lock.json            # 依賴鎖定檔案
│   ├── postcss.config.js            # PostCSS 配置
│   ├── tailwind.config.js           # Tailwind CSS 配置
│   ├── tsconfig.json                # TypeScript 配置
│   ├── next-env.d.ts                # Next.js 類型定義
│   ├── .gitignore                   # Web UI Git 忽略
│   └── README.md                    # Web UI 說明
│
├── 🖼️ **靜態資源**
│   └── public/                      # 公開資源
│       ├── favicon.ico              # 網站圖標
│       ├── favicon.svg              # SVG 圖標
│       ├── manifest.json            # PWA 清單
│       └── icon-*.png               # 各尺寸圖標
│
└── 📱 **程式碼**
    └── src/
        ├── 📄 app/                  # App Router 頁面 (9個頁面)
        │   ├── globals.css          # 全域樣式
        │   ├── layout.tsx           # 根布局
        │   ├── page.tsx             # 首頁
        │   ├── providers.tsx        # 提供者設置
        │   ├── analytics/           # 分析頁面
        │   │   └── page.tsx
        │   ├── api-management/      # API 管理
        │   │   └── page.tsx
        │   ├── auth/                # 認證頁面
        │   │   ├── discord/
        │   │   │   └── page.tsx
        │   │   ├── error/
        │   │   │   └── page.tsx
        │   │   └── success/
        │   │       └── page.tsx
        │   ├── bot-management/      # Bot 管理
        │   │   └── page.tsx
        │   ├── dashboard/           # 儀表板
        │   │   └── page.tsx
        │   ├── system/              # 系統頁面
        │   │   └── page.tsx
        │   ├── system-monitor/      # 系統監控
        │   │   └── page.tsx
        │   ├── tickets/             # 票券管理
        │   │   └── page.tsx
        │   └── votes/               # 投票管理
        │       └── page.tsx
        │
        ├── 🧩 components/           # React 組件庫
        │   ├── bot/                 # Bot 相關組件
        │   │   └── bot-connection-status.tsx
        │   ├── landing/             # 登陆頁組件
        │   │   └── landing-page.tsx
        │   ├── layout/              # 布局組件
        │   │   └── navbar.tsx
        │   ├── providers/           # 提供者組件
        │   │   └── bot-connection-provider.tsx
        │   └── ui/                  # UI 基礎組件
        │       ├── badge.tsx
        │       ├── button.tsx
        │       ├── card.tsx
        │       ├── spinner.tsx
        │       └── tabs.tsx
        │
        └── 📚 lib/                  # 工具庫和配置
            ├── utils.ts             # 通用工具
            ├── api/                 # API 客戶端
            │   └── client.ts
            ├── auth/                # 認證相關
            │   └── auth-context.tsx
            ├── config/              # 配置文件
            │   └── bot-config.ts
            ├── connection/          # 連接管理
            │   ├── bot-connector.ts
            │   └── use-bot-connection.ts
            ├── utils/               # 工具函數
            │   ├── cache-manager.ts
            │   ├── performance-monitor.ts
            │   └── system-health.ts
            └── websocket/           # WebSocket 相關
                └── websocket-provider.tsx
```

---

## 📚 文檔系統詳細結構

### 📂 **docs/** - 統一文檔中心
```
docs/
├── README.md                        # 文檔中心索引
│
├── 📖 **使用者指南**
│   └── user-guides/
│       ├── COMMANDS.md              # 指令參考
│       ├── QUICKSTART_v2.2.0.md    # 快速入門
│       └── USER_MANUAL.md          # 用戶手冊
│
├── 🛠️ **開發文檔**
│   └── development/
│       └── CHANGELOG.md             # 版本更新日誌
│
├── ⚙️ **系統文檔**
│   └── system/
│       ├── ADMIN_PERMISSION_SETUP.md     # 管理員權限設置
│       ├── REALTIME_VOTING_SYSTEM.md     # 即時投票系統
│       └── VOTE_TEMPLATE_SYSTEM.md       # 投票模板系統
│
├── 📦 **依賴管理**
│   └── requirements/
│       ├── requirements-combined.txt     # 統一依賴清單
│       ├── requirements-development.txt  # 開發環境依賴
│       └── requirements-production.txt   # 生產環境依賴
│
├── 🌐 **整合計畫**
│   ├── CROSS_PLATFORM_ECONOMY_PLAN.md   # 跨平台經濟系統
│   ├── MINECRAFT_PLUGIN_ARCHITECTURE.md # Minecraft 插件架構
│   └── ZIENTIS_INTEGRATION_PLAN.md      # Zientis 整合計畫
│
├── 📜 **歷史文檔**
│   ├── phase-archive/               # 階段計畫封存
│   │   └── PHASE7_DEVELOPMENT_PLAN.md
│   └── archived/                    # 項目完成文檔 (15個)
│       ├── API_DOCUMENTATION.md
│       ├── COMMAND_OPTIMIZATION.md
│       ├── DEPLOYMENT_GUIDE.md
│       ├── ENTERTAINMENT_DESIGN.md
│       ├── ENTERTAINMENT_GUIDE.md
│       ├── MENU_FIXES_SUMMARY.md
│       ├── PHASE5_DEVELOPMENT_PLAN.md
│       ├── PHASE6_DEVELOPMENT_PLAN.md
│       ├── PHASE7_STAGE1_COMPLETION.md
│       ├── PHASE7_STAGE2_COMPLETION.md
│       ├── PHASE_6_COMPLETION_REPORT.md
│       ├── PROJECT_COMPLETION_SUMMARY.md
│       ├── PROJECT_STATUS.md
│       ├── test_menu_functions.py
│       └── TOP_GG_DEPLOYMENT_READY.md
```

---

## 💾 資料與備份結構

### 📂 **backups/** - 系統備份檔案
```
backups/
├── daily_backup_20250823_020246.json.gz   # 每日備份
├── daily_backup_20250824_020342.json.gz   # 每日備份
└── weekly_backup_2025_W34.json.gz          # 每週備份
```

### 📂 **transcripts/** - 票券對話記錄
```
transcripts/
├── ticket_0008_20250810_191124.html       # 票券對話記錄
├── ticket_0011_20250812_140717.html
├── ticket_0013_20250815_171717.html
└── ticket_0014_20250817_190057.html
```

### 📂 **archive/** - 整理歸檔區域
```
archive/
├── old-logs/                               # 舊日誌檔案
├── old-tokens/                             # 舊認證檔案
└── temp-files/                             # 暫存檔案
```

---

## 📊 專案統計資訊

### 📈 **代碼規模統計**
- **總檔案數**: ~250+ 個檔案 (移除企業整合後)
- **Python 檔案**: 120+ 個 (.py) 
- **總程式碼行數**: ~70,000 行 (Python, 清理後)
- **TypeScript/JavaScript 檔案**: ~30 個
- **文檔檔案**: 20+ 個 (.md)
- **配置檔案**: 15+ 個

### 🏗️ **架構複雜度**
- **Bot Cogs (功能模組)**: 25 個 (遊戲社群專用)
- **服務層 (Services)**: 20+ 個 (移除企業整合後)
- **Minecraft 模組**: 4 個 (新增)
- **Gaming 模組**: 4 個 (新增)
- **資料存取層 (DAO)**: 18 個
- **UI 視圖 (Views)**: 17 個
- **Web UI 頁面**: 9 個主頁面
- **支援語言**: 5 種語言

### 📁 **目錄深度分析**
- **最大深度**: 4-5 層
- **核心模組**: bot/, api/, web-ui/, docs/
- **支援檔案**: shared/, archive/, backups/
- **配置管理**: 根目錄 + 各子模組

---

<div align="center">

# 🎮 遊戲社群 • Discord 整合 • Minecraft 專精

**Potato Bot 遊戲社群管理平台架構**

---

*📅 結構更新: 2025-08-25*  
*🎯 新定位: Discord & Minecraft 社群管理平台*

</div>