# 🔄 Potato Bot 專案重構指南

> **從分層架構轉向領域驅動設計 (Domain-Driven Design)**

## 📋 重構概述

### 重構目標
- 從**按層分類** (Layer-based) 轉向**按功能領域** (Feature-based) 架構
- 實現高內聚、低耦合的模組化設計
- 提升程式碼可維護性和擴展性
- 統一依賴管理和開發工具

### 重構範圍
1. ✅ **依賴管理統一**: 移除 `requirements.txt`，優化 `pyproject.toml`
2. ✅ **目錄結構現代化**: 建立 `src/` 目錄，重命名為 `potato_bot`、`potato_shared`
3. ✅ **測試架構建立**: 創建完整的測試目錄和配置
4. 🚧 **功能領域重組**: 按業務功能重新組織程式碼
5. ⏳ **文檔更新**: 更新所有相關文檔

---

## 🏗️ 新架構設計

### 目錄結構對比

#### ❌ 舊架構 (分層式)
```
bot/
├── cogs/           # 所有 Discord 指令
├── services/       # 所有業務邏輯
├── db/            # 所有資料存取
├── views/         # 所有 UI 組件
├── api/routes/    # 所有 API 路由
└── utils/         # 工具函數
```

#### ✅ 新架構 (領域式)
```
src/potato_bot/
├── features/                    # 按功能領域組織
│   ├── tickets/                # 票券系統
│   │   ├── cog.py             # Discord 指令
│   │   ├── service.py         # 業務邏輯
│   │   ├── dao.py             # 資料存取
│   │   ├── views.py           # UI 組件
│   │   ├── api.py             # API 路由
│   │   └── constants.py       # 相關常數
│   ├── economy/               # 經濟系統
│   ├── security/              # 安全系統
│   ├── ai/                    # AI 整合
│   └── ...
├── core/                       # 核心基礎設施
│   ├── bot.py                 # Bot 實例
│   ├── database.py            # 資料庫管理
│   └── error_handler.py       # 錯誤處理
└── main.py                     # 應用程式入口
```

---

## 🎯 功能領域劃分

### 已識別的領域

| 領域 | 說明 | 相關檔案 |
|------|------|----------|
| **tickets** | 票券系統 | ticket_core.py, ticket_manager.py, ticket_dao.py |
| **economy** | 經濟系統 | economy_core.py, economy_manager.py |  
| **security** | 安全管理 | security_core.py, security_audit_manager.py |
| **ai** | AI 助手 | ai_core.py, ai_assistant_core.py |
| **automation** | 自動化工具 | automation_core.py, workflow_core.py |
| **vote** | 投票系統 | vote_core.py, vote_listener.py |
| **game** | 遊戲功能 | game_core.py, lottery_core.py |
| **music** | 音樂播放 | music_core.py |
| **content_analysis** | 內容分析 | content_analysis_core.py |

---

## 🔧 實施步驟

### 第一階段：基礎架構 ✅
- [x] 統一依賴管理到 `pyproject.toml`
- [x] 建立 `src/` 目錄結構
- [x] 設定測試框架和配置
- [x] 建立 `features/` 目錄架構

### 第二階段：領域重組 🚧
- [x] **tickets**: 完成示範重組
- [ ] **economy**: 經濟系統重組
- [ ] **security**: 安全系統重組
- [ ] **ai**: AI 功能重組
- [ ] **automation**: 自動化工具重組
- [ ] **vote**: 投票系統重組
- [ ] **game**: 遊戲功能重組
- [ ] **music**: 音樂功能重組
- [ ] **content_analysis**: 內容分析重組

### 第三階段：整合優化 ⏳
- [ ] 更新所有導入路徑
- [ ] 清理舊目錄結構
- [ ] 更新 `main.py` 載入邏輯
- [ ] 驗證功能完整性

### 第四階段：文檔更新 ⏳
- [ ] 更新 README.md
- [ ] 更新 USAGE_GUIDE.md
- [ ] 建立開發者指南
- [ ] 更新 API 文檔

---

## 📝 重組模板

### 功能領域標準結構
```
features/{domain}/
├── __init__.py          # 模組初始化
├── cog.py              # Discord 指令處理
├── service.py          # 業務邏輯
├── dao.py              # 資料存取物件
├── views.py            # Discord UI 組件
├── api.py              # Web API 路由
├── constants.py        # 領域常數
├── utils.py            # 領域工具函數
├── models.py           # 資料模型 (可選)
└── exceptions.py       # 領域例外 (可選)
```

### 檔案命名規範
- **cog.py**: Discord Cog 類別
- **service.py**: 業務邏輯服務類別
- **dao.py**: 資料存取物件
- **views.py**: Discord UI 視圖
- **api.py**: FastAPI 路由
- **constants.py**: 常數定義
- **utils.py**: 工具函數

---

## 🔄 導入路徑更新

### 更新規則

#### 舊導入方式
```python
from bot.cogs.ticket_core import TicketCog
from bot.services.ticket_manager import TicketManager
from bot.db.ticket_dao import TicketDAO
```

#### 新導入方式
```python
from src.potato_bot.features.tickets.cog import TicketCog
from src.potato_bot.features.tickets.service import TicketManager  
from src.potato_bot.features.tickets.dao import TicketDAO
```

#### 領域內相對導入
```python
# 在 tickets/cog.py 中
from .service import TicketManager
from .views import TicketViews
from .constants import TICKET_STATUSES
```

---

## 🧪 測試策略

### 測試組織
```
tests/
├── unit/                    # 單元測試
│   ├── features/
│   │   ├── test_tickets/
│   │   ├── test_economy/
│   │   └── ...
│   └── core/
├── integration/             # 整合測試
│   ├── test_api/
│   ├── test_database/
│   └── test_discord/
└── fixtures/               # 測試資料
```

### 測試覆蓋目標
- **服務層**: 100% 業務邏輯覆蓋
- **資料層**: 90% DAO 方法覆蓋
- **API層**: 95% 端點覆蓋
- **整體**: 80% 程式碼覆蓋率

---

## 🚀 部署注意事項

### 向下相容性
- 保持現有 API 端點不變
- Discord 指令功能完全一致
- 資料庫結構無變更

### 漸進式遷移
1. **並行運行**: 新舊結構共存
2. **功能驗證**: 逐個領域測試
3. **逐步清理**: 確認穩定後移除舊檔案

### 風險控制
- 充分備份原始程式碼
- 分支開發，避免影響主線
- 完整測試覆蓋

---

## 🎉 重構效益

### 開發體驗提升
- **更快定位**: 相關程式碼集中管理
- **更易理解**: 清晰的職責劃分
- **更好維護**: 高內聚模組設計

### 技術債務減少
- **統一工具鏈**: 現代化的開發配置
- **標準化結構**: 一致的程式碼組織
- **完整測試**: 可靠的品質保證

### 擴展性增強
- **新功能添加**: 只需建立新領域目錄
- **團隊協作**: 按功能分配開發任務
- **微服務準備**: 為未來架構演進鋪路

---

**重構是一項長期投資，將為 Potato Bot 的持續發展奠定堅實基礎！** 🥔✨