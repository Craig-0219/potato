# 🥔 Potato Bot - 企業級 Discord 票券管理系統

![Version](https://img.shields.io/badge/version-2.0.0-blue.svg)
![Python](https://img.shields.io/badge/python-3.13-green.svg)
![Discord.py](https://img.shields.io/badge/discord.py-2.5.2-blue.svg)
![FastAPI](https://img.shields.io/badge/FastAPI-0.104.1-green.svg)
![License](https://img.shields.io/badge/license-MIT-yellow.svg)

一個功能完整的企業級 Discord 票券管理系統，包含 Web 管理介面、REST API 和強大的自動化功能。

## ✨ 核心特性

### 🎫 票券管理系統
- **完整的票券生命週期管理**：從創建到關閉的全程追蹤
- **優先級系統**：低、中、高、緊急四個優先級
- **智能分配**：自動分配給可用的客服人員
- **SLA 監控**：自動追蹤回應時間和解決時間
- **評分系統**：用戶滿意度評分和反饋收集

### 🌐 現代化 Web 介面
- **響應式設計**：支援桌面、平板和手機設備
- **即時更新**：WebSocket 即時數據同步
- **互動式儀表板**：豐富的圖表和統計數據
- **多語言支援**：繁體中文、簡體中文、英文、日文、韓文

### 🔐 企業級安全
- **多重認證**：JWT 令牌、API 金鑰、會話管理
- **細粒度權限**：角色基礎存取控制 (RBAC)
- **安全審計**：完整的操作日誌和追蹤
- **資料保護**：加密存儲敏感資訊

### 🚀 高性能架構
- **微服務設計**：模組化、可擴展的架構
- **異步處理**：高並發性能優化
- **快取機制**：Redis 支援的高效快取
- **負載均衡**：支援分散式部署

## 📋 功能模組

### Core Modules
- **票券系統** (`ticket_core`) - 核心票券管理功能
- **投票系統** (`vote`) - 社群投票和決策工具
- **歡迎系統** (`welcome_core`) - 新成員引導和設定
- **抽獎系統** (`lottery_core`) - 全功能抽獎管理系統 **🆕**
- **系統管理** (`system_admin`) - 全面的系統管理工具

### Advanced Features
- **AI 整合** (`ai_core`) - 智能客服輔助
- **工作流程** (`workflow_core`) - 可視化流程自動化
- **安全審計** (`security_core`) - 企業級安全監控
- **儀表板** (`dashboard_core`) - 高級分析和報告
- **Webhook** (`webhook_core`) - 外部系統整合

### Management Services
- **認證管理** (`auth_manager`) - 完整的身份認證系統
- **即時同步** (`realtime_sync_manager`) - 跨平台數據同步
- **系統監控** (`system_monitor`) - 性能和健康監控
- **資料管理** (`database_cleanup_manager`) - 自動化資料庫清理和優化 **🆕**
- **資料匯出** (`data_export_manager`) - 多格式資料匯出

## 🚀 快速開始

### 系統需求

- **Python 3.13+**
- **Node.js 18+** (Web UI)
- **MariaDB/MySQL 8.0+**
- **Redis** (可選，用於快取和即時功能)

### 1. 環境設定

```bash
# 克隆專案
git clone <repository-url>
cd potato

# 安裝 Python 依賴
pip install -r requirements.txt

# 安裝 API 依賴 (如需使用 Web 介面)
pip install -r requirements-api.txt
```

### 2. 設定檔配置

複製並編輯設定檔：
```bash
cp .env.example .env
```

必要的設定項目：
```env
# Discord Bot 設定
DISCORD_TOKEN=your_bot_token

# 資料庫設定
DB_HOST=localhost
DB_PORT=3306
DB_USER=your_db_user
DB_PASSWORD=your_db_password
DB_NAME=potato_bot

# API 設定 (可選)
API_PORT=8001
JWT_SECRET_KEY=your_secret_key
```

### 3. 啟動服務

#### Discord 機器人
```bash
python -m bot.main
```

#### Web API (可選)
```bash
# 使用批次檔 (推薦)
start_api.bat

# 或命令行
python start_api.py
```

#### Web UI (可選)
```bash
cd web-ui
npm install
npm run dev
```

### 4. 基本設定

在 Discord 中使用以下指令進行初始設定：

1. **設定票券系統**：
   ```
   /setup_ticket
   ```

2. **設定 Web 登入**：
   ```
   /setup-web-password password: 你的安全密碼
   ```

3. **創建 API 金鑰**：
   ```
   /create-api-key name: "我的應用程式"
   ```

## 🎯 主要指令

### 票券管理
| 指令 | 描述 | 權限 |
|------|------|------|
| `/setup_ticket` | 初始化票券系統 | 管理員 |
| `/ticket_settings` | 配置票券設定 | 管理員 |
| `/assign_ticket` | 手動分配票券 | 客服 |
| `/ticket_help` | 顯示幫助信息 | 所有人 |

### 系統管理
| 指令 | 描述 | 權限 |
|------|------|------|
| `/admin` | 系統管理面板 | 管理員 |
| `/dashboard` | 統計儀表板 | 客服 |
| `/report` | 生成系統報告 | 管理員 |

### Web 認證
| 指令 | 描述 | 權限 |
|------|------|------|
| `/setup-web-password` | 設定 Web 密碼 | 所有人 |
| `/create-api-key` | 創建 API 金鑰 | 客服 |
| `/web-login-info` | 查看登入資訊 | 所有人 |

## 🌐 API 文檔

### 基本端點
- **健康檢查**: `GET /health`
- **API 文檔**: `GET /docs`
- **用戶登入**: `POST /auth/login`

### 票券管理 API
- **票券列表**: `GET /tickets`
- **創建票券**: `POST /tickets`
- **票券詳情**: `GET /tickets/{id}`
- **更新票券**: `PUT /tickets/{id}`
- **關閉票券**: `POST /tickets/{id}/close`

### 統計 API
- **概覽統計**: `GET /tickets/stats/overview`
- **每日統計**: `GET /tickets/stats/daily`

完整的 API 文檔請訪問：`http://localhost:8001/docs`

## 🏗️ 架構設計

### 技術棧
- **後端**: Python 3.13 + FastAPI + Discord.py
- **前端**: Next.js 14 + TypeScript + Tailwind CSS
- **資料庫**: MariaDB/MySQL + Redis
- **部署**: Docker + Docker Compose

### 模組架構
```
potato/
├── bot/                    # Discord 機器人核心
│   ├── cogs/              # 指令模組
│   ├── services/          # 業務邏輯層
│   ├── db/                # 資料存取層
│   ├── views/             # UI 組件
│   └── utils/             # 工具函式
├── api/                   # FastAPI Web API
│   ├── routes/            # API 路由
│   └── middleware/        # 中介軟體
├── web-ui/                # Next.js 前端
│   ├── src/app/          # 頁面組件
│   ├── src/components/   # UI 組件
│   └── src/lib/          # 工具庫
└── shared/                # 共享模組
```

## 📊 監控與維運

### 系統監控
- **即時健康檢查**: 自動監控系統狀態
- **性能指標**: CPU、記憶體、響應時間追蹤
- **警報系統**: 異常情況自動通知

### 資料管理
- **自動備份**: 定期資料庫備份
- **資料匯出**: CSV、JSON、Excel 格式匯出
- **智能清理**: 自動歷史資料歸檔和清理 **🆕**
- **資料庫優化**: 自動索引優化和儲存壓縮 **🆕**
- **排程管理**: 可設定的清理和維護排程 **🆕**

### 日誌與除錯
- **結構化日誌**: 詳細的操作記錄
- **錯誤追蹤**: 異常自動捕捉和報告
- **除錯模式**: 開發和測試支援

## 🔧 進階設定

### 效能優化
- **連接池設定**: 優化資料庫連接
- **快取策略**: Redis 快取配置
- **負載均衡**: 多實例部署支援

### 安全強化
- **HTTPS 設定**: SSL/TLS 證書配置
- **防火牆規則**: 網路安全設定
- **權限審計**: 定期權限檢查

### 自訂擴展
- **插件系統**: 自訂功能模組
- **外部整合**: Webhook 和 API 整合
- **主題自訂**: UI 外觀自訂

## 🤝 貢獻指南

### 開發環境設定
1. Fork 專案並克隆到本地
2. 創建虛擬環境並安裝依賴
3. 設定開發資料庫
4. 運行測試確保環境正常

### 程式碼規範
- 遵循 PEP 8 Python 代碼風格
- 使用 TypeScript 嚴格模式
- 編寫單元測試覆蓋新功能
- 更新相關文檔

### 提交流程
1. 創建功能分支
2. 實現功能並測試
3. 提交 Pull Request
4. 通過程式碼審查

## 📄 授權協議

本專案採用 MIT 授權協議。詳見 [LICENSE](LICENSE) 檔案。

## 🆘 支援與反饋

### 獲取幫助
- **文檔**: 查看 `/docs` 目錄中的詳細文檔
- **FAQ**: 常見問題解答
- **社群**: Discord 伺服器交流

### 問題回報
- **Bug 報告**: 請提供詳細的錯誤信息和重現步驟
- **功能請求**: 描述期望的功能和使用場景
- **安全問題**: 請私下聯繫維護者

### 聯繫方式
- **GitHub Issues**: 公開問題討論
- **Email**: 技術支援和商業合作
- **Discord**: 即時社群支援

---

## 🎉 更新日誌

### v2.1.0 (2025-08-11) - 抽獎系統與資料庫優化 🆕

#### 新增功能
- **🎲 完整抽獎系統**
  - 支援反應參與和指令參與
  - 靈活的參與條件設定（帳號年齡、伺服器年資、角色需求）
  - 自動開獎和結果公告
  - 抽獎統計和管理介面
  
- **📦 智能資料管理**
  - 自動歷史資料歸檔系統
  - 票券和投票記錄長期保存
  - 用戶活動數據分析歸檔
  - 可配置的清理排程

- **⚡ 資料庫優化工具**
  - 自動索引分析和優化
  - 歷史資料壓縮
  - 儲存空間統計和建議
  - 性能監控和調整

#### 技術改進
- 新增 `LotteryDAO` 和 `ArchiveDAO` 資料存取層
- 實作 `LotteryManager` 和 `DatabaseCleanupManager` 服務
- 擴展系統管理指令支援資料庫維護
- 優化資料庫表結構設計

#### 指令更新
- `/create_lottery` - 創建抽獎活動
- `/join_lottery` - 參與抽獎
- `/lottery_info` - 查看抽獎資訊
- `/lottery_stats` - 抽獎統計分析
- `!cleanup` - 資料庫清理操作
- `!db_optimize` - 資料庫優化工具

### v2.0.0 (2025-08-10)
- ✨ 全新的企業級架構設計
- 🌐 完整的 Web 管理介面
- 🔐 強化的安全和認證系統
- 📊 高級統計和分析功能
- 🚀 REST API 和即時同步
- 🎨 現代化的用戶介面設計

### v1.8.0
- 基礎票券管理系統
- Discord 機器人核心功能
- 資料庫架構建立

---

**🎊 感謝使用 Potato Bot！讓我們一起建構更好的社群管理體驗！**