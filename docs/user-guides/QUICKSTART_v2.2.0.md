# 🚀 Potato Bot v2.2.0 快速啟動指南

## 🎯 新功能概覽

v2.2.0 引入了創意內容生成功能，包含：
- 🤖 **AI智能助手** (6個指令) - ChatGPT整合
- 🎨 **圖片處理工具** (4個指令) - 特效、迷因、頭像框架
- 🎵 **音樂娛樂系統** (12個指令) - 播放、問答、歌詞
- 📊 **內容分析工具** (6個指令) - 情感分析、安全檢查
- 🔄 **跨平台經濟整合** (11個指令) - Discord-Minecraft同步

**總計新增 39 個 Slash Commands！**

## 📋 必要環境變數

請在 `.env` 檔案中新增以下配置：

### AI助手功能
```env
OPENAI_API_KEY=your_openai_api_key_here
OPENAI_MODEL=gpt-3.5-turbo
AI_DAILY_FREE_QUOTA=10
```

### 音樂系統功能
```env
YOUTUBE_API_KEY=your_youtube_api_key_here
MUSIC_DAILY_FREE_QUOTA=20
```

### 跨平台整合（可選）
```env
MINECRAFT_SERVER_API_URL=http://your-minecraft-server.com:8080/api
MINECRAFT_SERVER_API_KEY=your_minecraft_api_key_here
```

## 🔧 安裝依賴

安裝新功能所需的依賴套件：

```bash
pip install -r requirements.txt
```

新增的主要依賴包括：
- `openai>=1.0.0` - AI助手
- `Pillow>=9.0.0` - 圖片處理
- `aiohttp>=3.8.0` - HTTP請求
- `yt-dlp>=2023.1.6` - YouTube支援
- `PyNaCl>=1.5.0` - Discord語音

## 🚀 啟動步驟

1. **更新配置文件**
   ```bash
   cp .env.example .env
   # 編輯 .env 檔案，填入必要的API金鑰
   ```

2. **建立跨平台資料表**（如需要）
   ```bash
   python scripts/create_cross_platform_tables.py
   ```

3. **運行測試**（可選）
   ```bash
   python test_module_loading.py
   python test_slash_commands.py
   ```

4. **啟動機器人**
   ```bash
   python bot/main.py
   ```

## 🎮 主要功能指令

### 🤖 AI智能助手
```
/ask [問題] - AI對話聊天
/code_help [程式問題] - 程式設計助手
/translate [文本] [目標語言] - 翻譯服務
/generate_story [主題] - AI故事生成
/generate_poem [主題] - AI詩歌創作
/ai_usage - 查看使用統計
```

### 🎨 圖片處理工具
```
/image_effect [圖片] [特效類型] - 圖片特效
/create_meme [圖片] [上方文字] [下方文字] - 迷因製作
/avatar_frame [頭像] [框架類型] - 頭像框架
/image_usage - 使用統計
```

### 🎵 音樂娛樂系統
```
/play [歌曲名稱] - 播放音樂
/search [關鍵詞] - 搜尋音樂
/lyrics - 查看歌詞
/music_quiz [難度] - 音樂問答
/queue - 播放佇列
/music_stats - 使用統計
```

### 📊 內容分析工具
```
/analyze_sentiment [文本] - 情感分析
/check_content [文本] - 安全檢查
/analyze_links [文本] - 連結分析
/comprehensive_analysis [文本] - 全面分析
/content_stats - 統計報告
```

### 🔄 跨平台經濟整合
```
/link_minecraft [用戶名] - 綁定Minecraft帳號
/sync_economy - 手動同步經濟數據
/cross_platform_status - 查看同步狀態
/balance - 查看錢包餘額
/daily - 每日簽到獎勵
```

## 💰 經濟系統

所有新功能都整合了統一的經濟機制：

### 免費額度（每日）
- 🤖 AI服務：10次
- 🎨 圖片處理：5次
- 🎵 音樂功能：20次
- 📊 內容分析：15次

### 付費機制
超出免費額度後，將消耗金幣：
- AI對話：5🪙
- 圖片特效：3🪙
- 音樂搜尋：3🪙
- 歌詞查看：5🪙
- 音樂問答：8🪙（答對可獲得獎勵）
- 內容分析：2🪙

## ⚠️ 注意事項

1. **API金鑰必需**
   - AI功能需要 OpenAI API 金鑰
   - 音樂功能需要 YouTube Data API 金鑰

2. **語音頻道權限**
   - 音樂功能需要機器人有語音頻道權限
   - 確保機器人能加入和播放音樂

3. **檔案大小限制**
   - 圖片處理最大支援 10MB 檔案
   - 支援格式：JPG, PNG, GIF, WebP

4. **Redis 快取（建議）**
   - 建議使用 Redis 來提升性能
   - 沒有 Redis 也能正常運行，但性能會降低

## 🔍 故障排除

### 模組載入失敗
```bash
python test_module_loading.py
```

### 指令無法使用
```bash
python test_slash_commands.py
```

### 同步指令到 Discord
在 Discord 中執行：
```
!sync
```

## 📊 監控與統計

新版本包含完整的使用統計和監控：
- Prometheus 指標收集
- 實時使用量統計
- 錯誤追蹤和報告
- 性能監控儀表板

## 🎉 享受新功能！

v2.2.0 大幅擴展了機器人的創意內容生成能力，讓您的 Discord 伺服器更有趣和智能！

如有問題，請查看：
- [README.md](README.md) - 完整文檔
- [CHANGELOG.md](CHANGELOG.md) - 更新日誌
- [GitHub Issues](https://github.com/Craig-0219/potato/issues) - 問題回報

---
**Potato Bot v2.2.0** - 創意內容生成版本 🎨