# 🎮 Potato Bot 指令手冊

完整的 Discord 機器人指令列表和 REST API 端點文檔。

## 📋 目錄

- [Discord 指令](#discord-指令)
  - [票券系統](#票券系統)
  - [投票系統](#投票系統)
  - [歡迎系統](#歡迎系統)
<<<<<<< HEAD
  - [抽獎系統](#抽獎系統) 🆕
=======
>>>>>>> a35f5d60d87ec4cc0114507a78c8527f0eed00ca
  - [系統管理](#系統管理)
  - [Web 認證](#web-認證)
- [REST API 端點](#rest-api-端點)
  - [認證 API](#認證-api)
  - [票券管理 API](#票券管理-api)
  - [統計分析 API](#統計分析-api)
- [權限說明](#權限說明)
- [使用範例](#使用範例)

## Discord 指令

### 票券系統

#### 管理員指令

| 指令 | 描述 | 使用方法 | 權限 |
|------|------|----------|------|
| `/setup_ticket` | 初始化票券系統設定 | `/setup_ticket` | 管理員 |
| `/ticket_settings` | 配置票券系統參數 | `/ticket_settings [選項]` | 管理員 |
| `/admin_close` | 管理員強制關閉票券 | `/admin_close [ticket_id] [原因]` | 管理員 |
| `/export_tickets` | 匯出票券資料 | `/export_tickets [格式] [日期範圍]` | 管理員 |

#### 客服指令

| 指令 | 描述 | 使用方法 | 權限 |
|------|------|----------|------|
| `/assign_ticket` | 手動分配票券給客服 | `/assign_ticket [ticket_id] [客服]` | 客服+ |
| `/ticket_stats` | 查看票券統計數據 | `/ticket_stats [時間範圍]` | 客服+ |
| `/transfer_ticket` | 轉移票券給其他客服 | `/transfer_ticket [ticket_id] [目標客服]` | 客服+ |
| `/add_note` | 為票券添加內部備註 | `/add_note [ticket_id] [備註內容]` | 客服+ |
| `/priority_set` | 設定票券優先級 | `/priority_set [ticket_id] [優先級]` | 客服+ |

#### 用戶指令

| 指令 | 描述 | 使用方法 | 權限 |
|------|------|----------|------|
| `/ticket` | 創建新票券 | `/ticket [類型] [標題] [描述]` | 所有人 |
| `/close` | 關閉自己的票券 | `/close [原因]` | 所有人 |
| `/rate` | 為已關閉票券評分 | `/rate [評分] [評價]` | 所有人 |
| `/my_tickets` | 查看自己的票券 | `/my_tickets [狀態]` | 所有人 |
| `/ticket_help` | 顯示票券系統幫助 | `/ticket_help` | 所有人 |

### 投票系統

| 指令 | 描述 | 使用方法 | 權限 |
|------|------|----------|------|
| `/create_vote` | 創建投票 | `/create_vote [標題] [選項] [時長]` | 客服+ |
| `/end_vote` | 提前結束投票 | `/end_vote [vote_id]` | 客服+ |
| `/vote_stats` | 查看投票統計 | `/vote_stats [vote_id]` | 客服+ |

### 歡迎系統

| 指令 | 描述 | 使用方法 | 權限 |
|------|------|----------|------|
| `/setup_welcome` | 設定歡迎系統 | `/setup_welcome [頻道] [訊息]` | 管理員 |
| `/welcome_test` | 測試歡迎訊息 | `/welcome_test` | 管理員 |
| `/auto_role` | 設定自動角色 | `/auto_role [角色] [條件]` | 管理員 |

<<<<<<< HEAD
### 抽獎系統 🆕

#### 管理員指令

| 指令 | 描述 | 使用方法 | 權限 |
|------|------|----------|------|
| `/create_lottery` | 創建抽獎活動 | `/create_lottery [名稱] [中獎人數] [持續時間]` | 管理訊息+ |
| `/end_lottery` | 提前結束抽獎 | `/end_lottery [抽獎ID]` | 管理訊息+ |
| `/lottery_list` | 查看進行中的抽獎 | `/lottery_list` | 所有人 |

#### 用戶指令

| 指令 | 描述 | 使用方法 | 權限 |
|------|------|----------|------|
| `/join_lottery` | 參與抽獎 | `/join_lottery [抽獎ID]` | 所有人 |
| `/leave_lottery` | 退出抽獎 | `/leave_lottery [抽獎ID]` | 所有人 |
| `/lottery_info` | 查看抽獎詳情 | `/lottery_info [抽獎ID]` | 所有人 |

#### 統計指令

| 指令 | 描述 | 使用方法 | 權限 |
|------|------|----------|------|
| `/lottery_stats` | 抽獎統計分析 | `/lottery_stats [天數]` | 管理訊息+ |

#### 抽獎參數說明

**創建抽獎參數：**
- **名稱** - 抽獎活動名稱
- **中獎人數** - 1-50 人（預設：1）
- **持續時間** - 1-168 小時（預設：24）
- **描述** - 抽獎說明（可選）
- **獎品** - 獎品描述（可選）
- **參與方式** - 反應/指令/兩者皆可

**參與條件：**
- 帳號年齡限制（可設定）
- 伺服器加入時間限制（可設定）
- 特定角色需求（可設定）
- 排除角色設定（可設定）

### 系統管理

#### 基本管理指令

=======
### 系統管理

>>>>>>> a35f5d60d87ec4cc0114507a78c8527f0eed00ca
| 指令 | 描述 | 使用方法 | 權限 |
|------|------|----------|------|
| `/admin` | 打開系統管理面板 | `/admin` | 管理員 |
| `/dashboard` | 查看系統儀表板 | `/dashboard` | 客服+ |
| `/system_status` | 檢查系統狀態 | `/system_status` | 客服+ |
<<<<<<< HEAD

#### 資料管理指令 🆕

| 指令 | 描述 | 使用方法 | 權限 |
|------|------|----------|------|
| `!cleanup` | 執行資料庫清理 | `!cleanup [basic/full/archive]` | Bot 擁有者 |
| `!db_optimize` | 資料庫優化 | `!db_optimize` | Bot 擁有者 |
| `!backup` | 創建系統備份 | `!backup [basic/full/tickets]` | Bot 擁有者 |
| `!export` | 資料匯出 | `!export [資料類型] [格式] [天數]` | Bot 擁有者 |

#### 系統診斷指令

| 指令 | 描述 | 使用方法 | 權限 |
|------|------|----------|------|
| `!logs` | 查看系統日誌 | `!logs [等級] [天數]` | 管理伺服器+ |
| `!diagnose` | 系統組件診斷 | `!diagnose [組件名]` | 管理伺服器+ |
| `!connectivity_test` | 連接測試 | `!connectivity_test` | 管理伺服器+ |
| `!error_analysis` | 錯誤趨勢分析 | `!error_analysis [時間範圍]` | 管理伺服器+ |

#### Bot 擁有者專用

| 指令 | 描述 | 使用方法 | 權限 |
|------|------|----------|------|
| `!botstatus` | Bot 整體狀態 | `!botstatus` | Bot 擁有者 |
| `!botHealth` | 完整健康檢查 | `!botHealth` | Bot 擁有者 |
| `!dbHealth` | 資料庫狀態檢查 | `!dbHealth` | Bot 擁有者 |
| `!maintenance` | 維護系統控制 | `!maintenance [操作] [任務ID]` | Bot 擁有者 |

#### 資料清理操作說明

**清理模式：**
- `basic` - 基本清理（保留 180 天票券，120 天投票，7 天日誌）
- `full` - 完整清理（保留 90 天票券，60 天投票，30 天日誌）
- `archive` - 僅歸檔，不刪除原始資料

**匯出格式：**
- `json` - JSON 格式（推薦）
- `csv` - CSV 表格格式
- `excel` - Excel 格式

**資料類型：**
- `tickets` - 票券資料
- `votes` - 投票資料
- `statistics` - 統計資料
- `users` - 用戶資料
- `logs` - 系統日誌
=======
| `/backup_data` | 創建資料備份 | `/backup_data [類型]` | 管理員 |
| `/restore_data` | 恢復資料備份 | `/restore_data [檔案]` | 管理員 |
| `/maintenance` | 維護模式開關 | `/maintenance [on/off]` | 管理員 |
| `/clear_cache` | 清理系統快取 | `/clear_cache [類型]` | 管理員 |
| `/update_bot` | 更新機器人設定 | `/update_bot` | 管理員 |
>>>>>>> a35f5d60d87ec4cc0114507a78c8527f0eed00ca

### Web 認證

| 指令 | 描述 | 使用方法 | 權限 |
|------|------|----------|------|
| `/setup-web-password` | 設定 Web 登入密碼 | `/setup-web-password password:[密碼]` | 所有人 |
| `/create-api-key` | 創建 API 金鑰 | `/create-api-key name:[應用名稱]` | 客服+ |
| `/web-login-info` | 查看 Web 登入資訊 | `/web-login-info` | 所有人 |
| `/revoke-api-key` | 撤銷 API 金鑰 | `/revoke-api-key [key_id]` | 客服+ |
| `/list-api-keys` | 查看 API 金鑰列表 | `/list-api-keys` | 客服+ |

## REST API 端點

### 認證 API

#### POST `/auth/login`
**用戶登入**

```json
請求體:
{
  "discord_id": "123456789",
  "password": "user_password"
}

回應:
{
  "access_token": "jwt_token",
  "token_type": "bearer",
  "expires_in": 3600,
  "user": {
    "discord_id": "123456789",
    "username": "使用者名稱",
    "is_staff": true,
    "guild_id": 987654321
  }
}
```

#### POST `/auth/refresh`
**刷新令牌**

```json
請求體:
{
  "refresh_token": "refresh_token"
}
```

#### POST `/auth/logout`
**用戶登出**

```json
請求標頭:
Authorization: Bearer <token>
```

### 票券管理 API

#### GET `/tickets`
**獲取票券列表**

```
查詢參數:
- page: 頁碼 (預設: 1)
- per_page: 每頁數量 (預設: 20, 最大: 100)
- status: 狀態篩選 (open, in_progress, pending, resolved, closed)
- priority: 優先級篩選 (low, medium, high, urgent)
- assigned_to: 指派人 ID
- search: 搜尋關鍵字

回應:
{
  "tickets": [票券列表],
  "total": 100,
  "page": 1,
  "per_page": 20,
  "has_next": true,
  "has_prev": false
}
```

#### GET `/tickets/{id}`
**獲取票券詳情**

```
路徑參數:
- id: 票券 ID

回應:
{
  "id": 1,
  "title": "票券標題",
  "description": "票券描述",
  "status": "open",
  "priority": "medium",
  "created_at": "2025-08-10T12:00:00Z",
  ...
}
```

#### POST `/tickets`
**創建新票券**

```json
請求體:
{
  "title": "票券標題",
  "description": "詳細描述",
  "ticket_type": "general",
  "priority": "medium"
}
```

#### PUT `/tickets/{id}`
**更新票券**

```json
請求體:
{
  "title": "新標題",
  "description": "新描述", 
  "status": "in_progress",
  "priority": "high",
  "assigned_to": 456
}
```

#### DELETE `/tickets/{id}`
**刪除票券**

執行軟刪除，將狀態設為 `deleted`

#### POST `/tickets/{id}/assign`
**指派票券**

```json
請求體:
{
  "assigned_to": 456
}
```

#### POST `/tickets/{id}/close`
**關閉票券**

```json
請求體:
{
  "reason": "問題已解決"
}
```

#### POST `/tickets/{id}/rate`
**評分票券**

```json
請求體:
{
  "rating": 5,
  "feedback": "服務很好"
}
```

### 統計分析 API

#### GET `/tickets/stats/overview`
**票券統計概覽**

```json
回應:
{
  "total_tickets": 500,
  "open_tickets": 45,
  "closed_tickets": 455,
  "in_progress_tickets": 23,
  "avg_resolution_time": 2.5,
  "avg_rating": 4.2
}
```

#### GET `/tickets/stats/daily`
**每日統計**

```
查詢參數:
- days: 統計天數 (1-90, 預設: 30)

回應:
{
  "period": "最近 30 天",
  "data": [
    {"date": "2025-08-10", "created": 5, "closed": 3, "pending": 2},
    {"date": "2025-08-09", "created": 3, "closed": 4, "pending": 1}
  ]
}
```

#### GET `/health`
**系統健康檢查**

```json
回應:
{
  "status": "healthy",
  "timestamp": "2025-08-10T12:00:00Z",
  "services": {
    "auth": "healthy",
    "monitoring": "healthy", 
    "realtime_sync": "healthy"
  },
  "metrics": {
    "active_tickets": 45,
    "system_health_score": 95
  }
}
```

## 權限說明

### 權限層級

| 層級 | 描述 | 包含權限 |
|------|------|----------|
| **管理員** | 完整系統管理權限 | 所有指令和 API |
| **客服** | 票券處理和統計權限 | 票券管理、統計查看、API 金鑰 |
| **一般用戶** | 基本票券操作 | 創建票券、查看自己的票券、評分 |

### API 認證方式

#### 1. JWT 令牌認證
```
Authorization: Bearer <jwt_token>
```
- 用於 Web 介面登入
- 有效期：1 小時
- 支援自動刷新

#### 2. API 金鑰認證  
```
Authorization: Bearer <key_id>.<secret>
```
- 用於程式化訪問
- 長期有效
- 可隨時撤銷

#### 3. 會話令牌
```
Authorization: Bearer <session_token>
```
- 用於持久會話
- 支援記住登入狀態

## 使用範例

### Discord 指令範例

```
# 創建技術支援票券
/ticket 類型:technical 標題:網站無法登入 描述:我無法登入官網，顯示密碼錯誤

# 設定票券優先級
/priority_set ticket_id:1234 優先級:high

# 查看統計數據
/ticket_stats 時間範圍:本月

# 設定 Web 密碼
/setup-web-password password:mySecurePassword123

# 創建 API 金鑰
/create-api-key name:我的應用程式
```

### API 請求範例

#### 登入並獲取令牌
```bash
curl -X POST http://localhost:8001/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "discord_id": "123456789",
    "password": "myPassword"
  }'
```

#### 獲取票券列表
```bash
curl -X GET "http://localhost:8001/tickets?status=open&page=1" \
  -H "Authorization: Bearer your_jwt_token"
```

#### 創建新票券
```bash
curl -X POST http://localhost:8001/tickets \
  -H "Authorization: Bearer your_jwt_token" \
  -H "Content-Type: application/json" \
  -d '{
    "title": "網站問題",
    "description": "登入頁面載入緩慢",
    "priority": "medium",
    "ticket_type": "technical"
  }'
```

#### 更新票券狀態
```bash
curl -X PUT http://localhost:8001/tickets/1234 \
  -H "Authorization: Bearer your_jwt_token" \
  -H "Content-Type: application/json" \
  -d '{
    "status": "in_progress",
    "assigned_to": 456
  }'
```

### JavaScript SDK 範例

```javascript
// 初始化 API 客戶端
const apiClient = new PotatoBotAPI({
  baseURL: 'http://localhost:8001',
  apiKey: 'your_api_key'
});

// 登入
const { token } = await apiClient.auth.login({
  discord_id: '123456789',
  password: 'password'
});

// 獲取票券
const tickets = await apiClient.tickets.list({
  status: 'open',
  page: 1,
  per_page: 20
});

// 創建票券
const newTicket = await apiClient.tickets.create({
  title: '新問題',
  description: '詳細描述',
  priority: 'high'
});

// 更新票券
await apiClient.tickets.update(newTicket.id, {
  status: 'resolved'
});
```

## 錯誤處理

### 常見錯誤碼

| 狀態碼 | 錯誤 | 描述 |
|--------|------|------|
| 400 | Bad Request | 請求參數錯誤 |
| 401 | Unauthorized | 未認證或令牌無效 |
| 403 | Forbidden | 權限不足 |
| 404 | Not Found | 資源不存在 |
| 429 | Too Many Requests | 請求過於頻繁 |
| 500 | Internal Server Error | 服務器內部錯誤 |

### 錯誤回應格式

```json
{
  "error": "錯誤描述",
  "status_code": 400,
  "path": "/tickets",
  "method": "POST"
}
```

## 開發工具

### API 文檔
- **Swagger UI**: http://localhost:8001/docs
- **OpenAPI Schema**: http://localhost:8001/openapi.json

### 測試工具
- **健康檢查**: http://localhost:8001/health
- **系統狀態**: `/system_status` 指令

### 監控端點
- **系統指標**: http://localhost:8001/metrics
- **即時狀態**: WebSocket `ws://localhost:8001/ws`

---

## 📞 技術支援

如有問題請使用：
- Discord 指令：`/ticket_help`
- API 文檔：http://localhost:8001/docs
- 健康檢查：http://localhost:8001/health

**📝 最後更新：2025-08-10**