# Discord Bot API 金鑰整合指南

## 🎯 整合概述

Web UI 現已完全整合 Discord Bot 的 API 金鑰系統！用戶可以使用通過 Discord Bot 生成的真實 API 金鑰登入 Web 介面。

## 🤖 如何取得 Discord Bot API 金鑰

### 步驟 1: 在 Discord 伺服器中使用指令
```
/create_api_key name:WebUI expires_days:30
```

### 步驟 2: 接收 API 金鑰
- Bot 會私訊您完整的 API 金鑰
- 格式：`key_id.key_secret`
- 例如：`A1B2C3D4E5F6G7H8.I9J0K1L2M3N4O5P6Q7R8S9T0U1V2W3X4Y5Z6`

### 步驟 3: 在 Web UI 中登入
1. 造訪 Web UI: `http://localhost:3000`
2. 在登入頁面的 "API 金鑰" 欄位中貼上完整金鑰
3. 點擊登入

## 🔑 權限系統

Discord Bot 會根據您在伺服器中的角色自動分配權限：

### 管理員權限
- **條件**: 角色名稱包含 "管理員"、"admin"、"owner"、"服主" 或 "commander"
- **權限**: `['all']` - 完整系統存取權限
- **功能**: 
  - 查看所有統計資料
  - 管理票券系統
  - 系統監控
  - 用戶管理
  - API 管理

### 客服權限
- **條件**: 角色名稱包含 "客服"、"staff"、"support"、"moderator" 或 "mod"
- **權限**: `['tickets.read', 'tickets.write', 'tickets.assign', 'tickets.close', 'statistics.read', 'users.read']`
- **功能**:
  - 查看和處理票券
  - 查看統計資料
  - 基本用戶管理

### 一般用戶權限
- **條件**: 其他角色
- **權限**: `['tickets.read_own']`
- **功能**:
  - 只能查看自己的票券

## 🔧 技術實現

### Web UI 認證流程

1. **API 金鑰驗證**: 
   ```typescript
   // 首先嘗試向 Discord Bot API 驗證
   const response = await fetch(`${botApiUrl}/api/auth/verify`, {
     method: 'POST',
     headers: {
       'Authorization': `Bearer ${apiKey}`
     }
   })
   ```

2. **備用驗證**: 如果無法連接到 Bot API，使用本地格式驗證

3. **用戶資料轉換**: 將 Discord Bot 用戶資料轉換為 Web UI 格式

### Discord Bot API 端點

- **驗證端點**: `POST /api/v1/auth/verify`
- **用戶資訊**: `GET /api/v1/auth/user`
- **健康檢查**: `GET /api/v1/health`

## 🌐 環境設定

### Web UI 環境變數
```env
NEXT_PUBLIC_BOT_API_URL=http://localhost:8000
```

### Discord Bot API 設定
- **預設端口**: 8000
- **CORS**: 已設定允許來自 Web UI 的請求
- **認證**: Bearer Token 格式

## 🛠️ 開發和測試

### 測試 API 金鑰（開發環境）
如果無法連接到 Discord Bot，系統提供測試金鑰：

```
potato-admin-key-123   # 管理員權限
potato-staff-key-456   # 客服權限
```

### 本地開發
1. 啟動 Discord Bot API: `python -m bot.api.app`
2. 啟動 Web UI: `npm run dev`
3. 使用 Discord Bot 生成的真實 API 金鑰登入

## 🔒 安全性考量

### API 金鑰安全
- API 金鑰只在生成時顯示一次
- 所有請求都通過 HTTPS (生產環境)
- 金鑰有過期時間限制
- 支援金鑰撤銷功能

### 權限驗證
- 每個 API 請求都驗證權限
- 角色和權限即時同步
- 支援細粒度權限控制

## 📝 故障排除

### 常見問題

#### 1. "API 金鑰格式錯誤"
**原因**: 金鑰格式不是 `key_id.key_secret`
**解決**: 確保複製完整的金鑰，包含中間的點號

#### 2. "無法連接到 Discord bot API"
**原因**: Bot API 服務未啟動或網路問題
**解決**: 
- 檢查 Bot API 是否運行在 `http://localhost:8000`
- 系統會自動使用備用驗證模式

#### 3. "權限不足"
**原因**: Discord 角色未正確配置
**解決**: 
- 檢查 Discord 伺服器中的角色設定
- 確保角色名稱包含適當的關鍵字

### 偵錯工具

#### 瀏覽器開發者工具
查看 Console 中的認證日誌：
```
🧪 使用測試 API 金鑰登入: Administrator
🔑 嘗試驗證 Discord bot API 金鑰...
✅ Discord bot API 金鑰驗證成功: Username
🔄 使用本地驗證模式
```

#### API 端點測試
```bash
# 測試 Bot API 連接
curl http://localhost:8000/api/v1/health

# 測試 API 金鑰驗證
curl -X POST http://localhost:8000/api/v1/auth/verify \
  -H "Authorization: Bearer your_api_key_here"
```

## 🚀 部署考量

### 生產環境設定
1. 設定正確的 `NEXT_PUBLIC_BOT_API_URL`
2. 啟用 HTTPS
3. 配置防火牆和安全群組
4. 設定監控和日誌記錄

### 擴展性
- 支援多伺服器部署
- 資料庫分離
- 負載平衡
- 快取層

---

**注意**: 此系統設計為與 Potato Discord Bot 緊密整合，確保 Bot 和 Web UI 版本相容。