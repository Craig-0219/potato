# 🥔 Potato Bot v2.2.0

> 多功能Discord機器人 - 整合AI助手、創意工具、娛樂功能和跨平台經濟系統

[![Version](https://img.shields.io/badge/version-2.2.0-blue.svg)](https://github.com/Craig-0219/potato)
[![Python](https://img.shields.io/badge/python-3.8+-green.svg)](https://www.python.org/)
[![Discord.py](https://img.shields.io/badge/discord.py-2.0+-blue.svg)](https://discordpy.readthedocs.io/)
[![License](https://img.shields.io/badge/license-MIT-orange.svg)](LICENSE)

一個功能豐富的多功能 Discord 機器人，提供AI智能助手、創意內容生成、音樂娛樂、圖片處理和跨平台經濟整合等功能，讓您的Discord伺服器更有趣和智能！

## 🔄 最新更新 (2025-08-15)

📋 **檔案重新組織完成**
- 投票系統檔案已重新組織以提升可維護性
- `vote.py` → `vote_core.py` (統一命名慣例)
- 整合重複的投票視圖檔案到統一的 `vote_views.py`
- 詳見 [重新組織更新日誌](./REORGANIZATION_CHANGELOG.md)

## ✨ 功能特色

### 🤖 AI智能助手
- **ChatGPT整合**: 智能對話、代碼助手、翻譯服務
- **創意寫作**: 故事生成、詩歌創作、廣告文案
- **安全過濾**: 內容審核、速率限制、使用統計

### 🎨 圖片處理工具
- **圖片特效**: 8種濾鏡效果（復古、霓虹、模糊等）
- **迷因製作**: Drake模板、自定義文字迷因
- **頭像裝飾**: 圓形、方形、六邊形框架

### 🎵 音樂娛樂系統
- **音樂播放**: YouTube搜尋、播放控制、佇列管理
- **歌詞顯示**: 即時歌詞查看、快取優化
- **音樂問答**: 多難度音樂測驗遊戲

### 📊 內容分析工具
- **情感分析**: 正面/負面/中性情感檢測
- **安全檢查**: 毒性內容、騷擾言論識別
- **連結分析**: URL安全性檢查、短網址展開

### 🎮 遊戲娛樂系統
- **經濟系統**: 金幣、寶石、經驗值管理
- **抽獎系統**: 多種獎品、機率控制
- **成就系統**: 任務追蹤、獎勵發放

### 🔄 跨平台整合
- **Minecraft整合**: Discord-Minecraft經濟同步
- **數據同步**: 帳戶綁定、交易記錄
- **API接口**: RESTful API支持

### 🎫 工單管理系統
- **智能工單**: 自動分類、優先級管理
- **團隊協作**: 分配系統、進度追蹤
- **數據分析**: 統計報表、效能監控

## 🚀 系統特色

### 🎯 核心技術優勢
- **經濟整合**: 所有服務都整合了金幣消費機制
- **免費額度**: 每日免費使用次數，超出後付費
- **緩存優化**: Redis快取提升性能
- **錯誤處理**: 完善的異常處理和用戶提示
- **統計監控**: Prometheus指標收集
- **安全防護**: 內容過濾、速率限制

## 📋 指令列表

### 🤖 AI助手指令
- `/ask` - AI對話聊天
- `/code_help` - 程式設計助手
- `/translate` - 文本翻譯
- `/generate_story` - 故事生成
- `/generate_poem` - 詩歌創作
- `/ai_usage` - AI使用統計

### 🎨 圖片工具指令
- `/image_effect` - 圖片特效
- `/create_meme` - 迷因製作
- `/avatar_frame` - 頭像框架
- `/image_usage` - 圖片處理統計

### 🎵 音樂指令
- `/play` - 播放音樂
- `/search` - 搜尋音樂
- `/lyrics` - 查看歌詞
- `/music_quiz` - 音樂問答
- `/queue` - 播放佇列
- `/music_stats` - 音樂統計

### 📊 內容分析指令
- `/analyze_sentiment` - 情感分析
- `/check_content` - 安全檢查
- `/analyze_links` - 連結分析
- `/comprehensive_analysis` - 綜合分析
- `/content_stats` - 內容統計

### 🎮 遊戲指令
- `/balance` - 查看餘額
- `/daily` - 每日簽到
- `/lottery` - 參與抽獎
- `/achievements` - 查看成就
- `/link_minecraft` - 綁定Minecraft

## 🚀 快速開始

### 環境需求
- Python 3.8+
- PostgreSQL 12+
- Redis 6+
- Discord Bot Token

### 安裝步驟

1. **克隆專案**
```bash
git clone https://github.com/Craig-0219/potato.git
cd potato
```

2. **安裝依賴**
```bash
pip install -r requirements.txt
```

3. **配置環境變數**
```bash
cp .env.example .env
# 編輯 .env 檔案，填入必要的配置
```

4. **初始化資料庫**
```bash
python scripts/create_cross_platform_tables.py
```

5. **啟動機器人**
```bash
python bot/main.py
```

### Docker 部署

```bash
# 使用 Docker Compose 快速部署
docker-compose up -d
```

## 🛠️ 配置說明

### 基本配置 (.env)
```env
# Discord 配置
DISCORD_TOKEN=your_discord_bot_token
GUILD_ID=your_guild_id

# 資料庫配置
DATABASE_URL=postgresql://user:password@localhost/potato_bot

# Redis 配置
REDIS_URL=redis://localhost:6379

# AI 服務配置
OPENAI_API_KEY=your_openai_api_key

# 音樂服務配置
YOUTUBE_API_KEY=your_youtube_api_key
```

### 進階配置
詳細配置選項請參考 [配置文檔](CONFIGURATION.md)

## 📊 架構設計

```
potato/
├── bot/                    # 機器人核心
│   ├── cogs/              # 功能模組
│   ├── services/          # 服務層
│   ├── utils/             # 工具函數
│   └── views/             # UI 視圖
├── api/                   # REST API
├── web-ui/                # Web 管理界面
├── shared/                # 共享模組
└── scripts/               # 工具腳本
```

## 🔧 開發指南

### 新增功能模組

1. 在 `bot/cogs/` 目錄建立新的 cog 檔案
2. 在 `bot/services/` 目錄實現業務邏輯
3. 更新 `bot/main.py` 載入新模組
4. 編寫測試並更新文檔

### 程式碼規範
- 使用 Black 進行程式碼格式化
- 遵循 PEP 8 風格指南
- 編寫詳細的 docstring
- 使用類型提示

## 🤝 貢獻指南

歡迎貢獻程式碼！請遵循以下步驟：

1. Fork 這個專案
2. 建立功能分支 (`git checkout -b feature/amazing-feature`)
3. 提交更改 (`git commit -m 'Add amazing feature'`)
4. 推送到分支 (`git push origin feature/amazing-feature`)
5. 開啟 Pull Request

## 📝 更新日誌

### v2.2.0 (2025-08-14) - 創意內容生成版本 🎨

**主要新功能：**
- ✨ 新增 AI智能助手模組 (ChatGPT整合)
- 🎨 完善圖片處理工具 (特效、迷因、頭像框架)
- 🎵 實作音樂娛樂系統 (播放、問答、歌詞)
- 📊 加入內容分析工具 (情感分析、安全檢查)
- 🔄 支援跨平台經濟整合 (Discord-Minecraft同步)

**系統改進：**
- ⚡ 全面整合經濟系統和免費額度機制
- 🛡️ 強化內容過濾和安全檢查
- 🚀 優化緩存策略和性能監控
- 📈 新增Prometheus指標收集
- 🔧 完善錯誤處理和用戶體驗

**技術升級：**
- 🎯 模組化服務架構設計
- 💾 Redis多層緩存優化
- 🔒 完善的速率限制機制
- 📊 實時使用統計和監控

### v2.1.0 (2025-08-11) - 穩定性修復版
- 🐛 修復資料庫結構和API問題
- ✨ 改進錯誤處理和日誌系統
- 🔧 優化系統穩定性和安全性

詳細更新日誌請參考 [CHANGELOG.md](CHANGELOG.md)

## 📄 授權協議

本專案採用 MIT 授權協議 - 詳情請參考 [LICENSE](LICENSE) 檔案

## 🙏 致謝

- [Discord.py](https://github.com/Rapptz/discord.py) - Discord API 封裝
- [OpenAI](https://openai.com/) - AI 服務支援
- [PIL/Pillow](https://python-pillow.org/) - 圖片處理
- 所有貢獻者和使用者的支持

## 📞 聯絡方式

- 專案作者: Craig
- Discord: [邀請連結](https://discord.gg/your-server)
- 問題回報: [GitHub Issues](https://github.com/Craig-0219/potato/issues)

---

<div align="center">

**🥔 Potato Bot - 讓你的Discord伺服器更有趣！**

[官方網站](https://your-website.com) • [使用指南](USER_MANUAL.md) • [API文檔](API_DOCS.md)

</div>