# 🚀 正式上線檢查清單

**上線日期**: 2025-08-31  
**系統版本**: v2025.08.30  
**負責人**: 系統管理員  

---

## ✅ 上線前最終檢查

### 🔧 技術檢查
- [ ] **程式主程式啟動測試**
  ```bash
  python start.py --test-mode
  ```
- [ ] **資料庫連接測試**
  ```bash
  python -c "from shared.config import get_database_url; print('DB OK')"
  ```
- [ ] **Redis 連接測試**  
  ```bash
  redis-cli ping
  ```
- [ ] **Discord Bot Token 驗證**
  ```bash
  # 檢查 .env 檔案中的 DISCORD_BOT_TOKEN
  ```
- [ ] **API 服務啟動測試**
  ```bash
  curl http://localhost:8000/health
  ```

### 🧪 功能檢查
- [ ] **核心 Cogs 載入**
  - [ ] TicketCore - 票券系統
  - [ ] VoteCore - 投票系統
  - [ ] LanguageCore - 多語言
  - [ ] MinecraftCore - 遊戲整合
  - [ ] SecurityCore - 安全管理
- [ ] **基礎指令測試**
  - [ ] `/help` - 幫助指令
  - [ ] `/ticket create` - 建立票券
  - [ ] `/vote create` - 建立投票
  - [ ] `/lang set zh-TW` - 語言切換
- [ ] **Web UI 訪問**
  - [ ] http://localhost:3000 (開發模式)
  - [ ] 儀表板載入正常

### 🔒 安全檢查
- [ ] **環境變數保護**
  - [ ] .env 檔案不在版本控制中
  - [ ] 敏感資訊已加密
  - [ ] API 金鑰安全存儲
- [ ] **權限設定**
  - [ ] 檔案權限正確 (644/755)
  - [ ] 資料庫使用者權限最小化
  - [ ] Discord Bot 權限適當

### 📊 監控檢查  
- [ ] **日誌系統**
  - [ ] 日誌檔案可正常寫入
  - [ ] 日誌等級設定正確
  - [ ] 錯誤日誌格式正確
- [ ] **系統監控**
  - [ ] CPU 和記憶體監控
  - [ ] 磁碟空間監控
  - [ ] 網路連接監控

---

## 🚀 上線步驟

### Step 1: 環境準備
1. **更新程式碼到最新版本**
   ```bash
   git checkout main
   git pull origin main
   ```

2. **安裝依賴**
   ```bash
   pip install -r requirements.txt
   ```

3. **環境變數設定**
   ```bash
   cp .env.example .env
   # 編輯 .env 填入正確的配置
   nano .env
   ```

### Step 2: 資料庫初始化
1. **資料庫連接測試**
   ```bash
   python -c "from bot.db.database_manager import DatabaseManager; DatabaseManager().test_connection()"
   ```

2. **資料表建立** (如需要)
   ```bash
   python -c "from bot.db.database_manager import DatabaseManager; DatabaseManager().create_tables()"
   ```

### Step 3: 服務啟動
1. **啟動 Discord Bot**
   ```bash
   # 方法1: Python 啟動器
   python start.py
   
   # 方法2: 直接啟動
   cd bot && python main.py
   
   # 方法3: 系統服務 (推薦生產環境)
   systemctl start potato-bot
   ```

2. **啟動 Web API** (如果需要)
   ```bash
   cd bot/api && uvicorn app:app --host 0.0.0.0 --port 8000
   ```

3. **啟動前端** (如果需要)
   ```bash
   cd web-ui && npm run build && npm start
   ```

### Step 4: 驗證部署
1. **檢查 Bot 狀態**
   - 在 Discord 中查看 Bot 是否在線
   - 測試基礎指令回應

2. **檢查系統狀態**
   ```bash
   # 檢查程序運行
   ps aux | grep python
   
   # 檢查端口占用
   netstat -tlnp | grep :8000
   
   # 檢查日誌
   tail -f bot.log
   ```

---

## 🎯 上線後立即任務 (0-24小時)

### ⏰ 第1小時
- [ ] **系統狀態確認**
  - 所有服務正常運行
  - Discord Bot 在線狀態
  - API 服務回應正常
- [ ] **基礎功能測試**
  - 建立測試票券
  - 執行測試投票  
  - 驗證語言切換
- [ ] **監控系統檢查**
  - 日誌正常輸出
  - 無錯誤或警告訊息
  - 系統資源使用正常

### ⏰ 第2-4小時
- [ ] **使用者反饋收集**
  - 建立回饋收集渠道
  - 監控使用者問題回報
  - 記錄常見問題
- [ ] **效能監控**
  - API 回應時間
  - 資料庫查詢效能
  - 記憶體和 CPU 使用率

### ⏰ 第8-24小時
- [ ] **穩定性評估**
  - 系統連續運行狀況
  - 錯誤率統計
  - 使用者活動統計
- [ ] **問題修復**
  - 緊急問題立即修復
  - 一般問題記錄排程
  - 優化建議整理

---

## 🚨 應急處理

### 常見問題快速解決

#### Bot 無法啟動
```bash
# 檢查錯誤訊息
python start.py 2>&1 | tee startup.log

# 檢查依賴
pip check

# 檢查配置
python -c "from shared.config import *; print('Config OK')"
```

#### 資料庫連接失敗
```bash
# 檢查資料庫服務
systemctl status mysql  # 或 postgresql

# 檢查連接字串
python -c "from shared.config import get_database_url; print(get_database_url())"

# 測試連接
mysql -h localhost -u username -p database_name
```

#### Discord Bot 離線
```bash
# 檢查 Token
echo $DISCORD_BOT_TOKEN

# 檢查網路連接
ping discord.com

# 重新啟動 Bot
python start.py --restart
```

### 🆘 緊急回滾
如果出現嚴重問題，執行緊急回滾：
```bash
# 停止服務
systemctl stop potato-bot

# 回滾到上一個穩定版本
git checkout <last_stable_commit>

# 重新啟動
systemctl start potato-bot
```

---

## 📞 聯絡資訊

### 🛠️ 技術支援
- **系統管理員**: [管理員聯絡方式]
- **開發團隊**: [開發團隊聯絡方式]  
- **緊急聯絡**: [24小時緊急聯絡]

### 📋 文檔資源
- **使用者手冊**: [docs/user-guides/USER_MANUAL.md](docs/user-guides/USER_MANUAL.md)
- **指令參考**: [docs/user-guides/COMMANDS.md](docs/user-guides/COMMANDS.md)
- **問題記錄**: [docs/issues/](docs/issues/)
- **系統文檔**: [docs/system/](docs/system/)

---

## 🎉 上線成功確認

### ✅ 成功指標
- [ ] **系統穩定運行 > 2小時**
- [ ] **基礎功能全部正常**  
- [ ] **無重大錯誤或崩潰**
- [ ] **使用者可以正常使用**
- [ ] **監控系統運作正常**

### 🎯 上線宣告
當所有檢查項目完成後，可以發布上線公告：

```
🎉 Potato Bot 正式上線！

我們的多功能社群管理機器人現已正式啟用，提供：
✅ 智能客服系統
✅ 社群互動工具  
✅ 多語言支援
✅ 遊戲整合功能
✅ AI 智能助手
✅ 安全管理機制
✅ 社群數據分析

感謝大家的支持，讓我們一起打造更好的社群體驗！

如有問題請聯絡：[支援聯絡方式]
```

---

**檢查清單完成日期**: ___________  
**負責人簽名**: ___________  
**上線確認時間**: ___________  
**狀態**: 🚀 **準備發射** | ✅ **上線成功** | ⚠️ **需要處理**