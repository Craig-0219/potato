# Potato Bot 更新日誌

## v2.3.0 - 2025-08-18

### 🚀 新增功能
- **Discord OAuth 認證系統**: 替代複雜的 API 金鑰認證，提供一鍵登入體驗
- **Bot 管理 Web 界面**: 統一的 Web GUI 管理 Discord Bot 各項功能
- **整合設定管理**: 可在 Web 界面中配置票券、投票、歡迎系統等設定

### ⚡ 性能優化
- **移除無用指令模組**: 從 100 個指令減少到 51 個，提升 49% 性能
- **精簡核心功能**: 移除娛樂模組，專注企業級管理功能
- **優化系統架構**: 保留核心業務邏輯，移除冗餘功能

### 🛠️ 技術改進
- **新增 Bot 設定 API**: 支援 Web 界面配置管理
- **擴展系統路由**: 新增 Bot 指令列表、擴展重載等管理功能
- **統一認證流程**: Discord OAuth 與 API 金鑰雙重認證支援

### 📋 移除的功能
- 抽獎系統 (lottery_core)
- AI 對話助手 (ai_assistant_core)
- 圖片處理工具 (image_tools_core)
- 音樂播放功能 (music_core)
- 內容分析工具 (content_analysis_core)
- 遊戲娛樂功能 (game_core)

### 🎯 保留的核心功能
- ✅ 票券管理系統
- ✅ 投票系統
- ✅ 歡迎系統
- ✅ 系統管理
- ✅ AI 智能回覆
- ✅ 多語言支援
- ✅ 工作流程管理
- ✅ 分析儀表板
- ✅ Webhook 整合

### 🔧 API 更新
- `GET /api/v1/system/bot-settings` - 獲取 Bot 設定
- `POST /api/v1/system/bot-settings/{section}` - 更新特定模組設定
- `GET /api/v1/system/bot-commands` - 獲取 Bot 指令列表
- `POST /api/v1/system/bot-reload-extension` - 重新載入擴展模組

### 🌟 用戶體驗改善
**之前**: 需要在 Discord 中記憶複雜指令
**現在**: 直觀的 Web 界面統一管理

---

## v2.2.0 - 2025-08-17

### 🚀 新增功能
- 投票系統現代化
- 項目清理與重組
- 實時統計系統

### 🛠️ 技術改進
- 檔案重新組織
- Cogs 目錄標準化
- 系統數據串聯修復

---

## v2.1.0 - 2025-08-16

### 🚀 新增功能
- 基礎票券系統
- 用戶認證機制
- 基本 Web 界面

### 🛠️ 技術改進
- 資料庫架構設計
- API 路由建立
- 前端框架建置