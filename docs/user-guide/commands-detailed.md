# 🎮 Potato Bot 指令手冊

完整的 Discord 機器人指令列表和 REST API 端點文檔。

## 📋 目錄

- [Discord 指令](#discord-指令)
  - [票券系統](#票券系統)
  - [投票系統](#投票系統)
  - [抽獎系統](#抽獎系統)
  - [AI 系統](#ai-系統)
  - [工作流程系統](#工作流程系統)
  - [Webhook 系統](#webhook-系統)
  - [系統管理與儀表板](#系統管理與儀表板)
  - [語言設定](#語言設定)
  - [Web 認證](#web-認證)
- [文字指令](#文字指令)
- [REST API 端點](#rest-api-端點)
  - [認證 API](#認證-api)
  - [票券管理 API](#票券管理-api)
  - [統計分析 API](#統計分析-api)
- [權限說明](#權限說明)
- [使用範例](#使用範例)

## Discord 指令

### 票券系統

#### 基本票券操作

| 指令 | 描述 | 權限 |
|------|------|------|
| `/close` | 關閉票券 | 所有人 |
| `/tickets` | 查看票券列表 | 客服+ |
| `/tickets_test` | 測試票券列表指令 | 管理員 |
| `/ticket_info` | 查看票券資訊 | 客服+ |
| `/realtime_stats` | 查看實時統計 | 客服+ |

#### 票券管理與標籤

| 指令 | 描述 | 權限 |
|------|------|------|
| `/add_tag` | 為票券添加標籤 | 客服+ |
| `/set_priority` | 設定票券優先級 | 客服+ |

#### AI 增強功能

| 指令 | 描述 | 權限 |
|------|------|------|
| `/ai_priority` | 為當前票券獲取 AI 優先級評估 | 客服+ |
| `/ai_suggest` | 為當前票券獲取 AI 智能回覆建議 | 客服+ |
| `/ai_tags` | 為當前票券獲取 AI 標籤建議 | 客服+ |

### 投票系統

| 指令 | 描述 | 權限 |
|------|------|------|
| `/vote` | 開始建立一個投票 | 客服+ |
| `/votes` | 查看目前進行中的投票 | 所有人 |
| `/vote_detail` | 查看特定投票的詳細資訊 | 所有人 |
| `/vote_history` | 查看投票歷史記錄 | 客服+ |
| `/vote_result` | 查詢投票結果 | 所有人 |
| `/vote_search` | 搜尋投票 | 客服+ |
| `/vote_open` | 補發互動式投票 UI (限管理員) | 管理員 |
| `/vote_debug` | 診斷投票系統問題（管理員用） | 管理員 |
| `/my_votes` | 查看我參與過的投票 | 所有人 |

### 抽獎系統

#### 抽獎管理

| 指令 | 描述 | 權限 |
|------|------|------|
| `/create_lottery` | 創建新的抽獎活動 (傳統指令) | 管理訊息+ |
| `/create_lottery_quick` | 快速創建抽獎 (使用互動式表單) | 管理訊息+ |
| `/end_lottery` | 提前結束抽獎 | 管理訊息+ |
| `/lottery_panel` | 打開抽獎管理面板 | 管理訊息+ |

#### 抽獎參與

| 指令 | 描述 | 權限 |
|------|------|------|
| `/join_lottery` | 參與抽獎 | 所有人 |
| `/leave_lottery` | 退出抽獎 | 所有人 |
| `/lottery_list` | 查看進行中的抽獎列表 | 所有人 |
| `/lottery_info` | 查看抽獎資訊 | 所有人 |
| `/my_lottery_history` | 查看我的抽獎參與歷史 | 所有人 |

#### 抽獎統計

| 指令 | 描述 | 權限 |
|------|------|------|
| `/lottery_stats` | 查看抽獎統計 | 管理訊息+ |

### AI 系統

| 指令 | 描述 | 權限 |
|------|------|------|
| `/ai_priority` | 為當前票券獲取 AI 優先級評估 | 客服+ |
| `/ai_suggest` | 為當前票券獲取 AI 智能回覆建議 | 客服+ |
| `/ai_tags` | 為當前票券獲取 AI 標籤建議 | 客服+ |

### 工作流程系統

| 指令 | 描述 | 權限 |
|------|------|------|
| `/workflow_create` | 創建新的工作流程 | 管理員 |
| `/workflow_list` | 查看工作流程列表 | 客服+ |
| `/workflow_execute` | 手動執行工作流程 | 客服+ |
| `/workflow_status` | 查看工作流程執行狀態 | 客服+ |
| `/workflow_template` | 創建工作流程模板 | 管理員 |
| `/workflow_toggle` | 啟用/停用工作流程 | 管理員 |
| `/workflow_stats` | 查看工作流程統計 | 管理員 |

### Webhook 系統

| 指令 | 描述 | 權限 |
|------|------|------|
| `/webhook_create` | 創建新的Webhook | 管理員 |
| `/webhook_list` | 查看Webhook列表 | 客服+ |
| `/webhook_config` | 配置Webhook設定 | 管理員 |
| `/webhook_test` | 測試Webhook | 管理員 |
| `/webhook_delete` | 刪除Webhook | 管理員 |
| `/webhook_stats` | 查看Webhook統計 | 管理員 |

### 系統管理與儀表板

#### 基本管理

| 指令 | 描述 | 權限 |
|------|------|------|
| `/admin` | 打開系統管理面板 | 管理員 |
| `/basic_dashboard` | 查看基礎系統儀表板 | 客服+ |
| `/system_status` | 查看系統整體狀態 | 管理員 |
| `/vote_admin` | 投票系統管理面板 | 客服+ |

#### 高級分析儀表板

| 指令 | 描述 | 權限 |
|------|------|------|
| `/dashboard_overview` | 查看系統概覽儀表板 | 管理伺服器+ |
| `/dashboard_performance` | 查看系統性能分析儀表板 | 管理伺服器+ |
| `/dashboard_prediction` | 查看智能預測分析儀表板 | 管理伺服器+ |
| `/dashboard_realtime` | 查看實時系統狀態 | 管理伺服器+ |
| `/dashboard_cache` | 管理儀表板快取 | 管理員 |

#### 資料管理

| 指令 | 描述 | 權限 |
|------|------|------|
| `/backup` | 執行系統資料備份 | 管理員 |
| `/database` | 資料庫管理面板 | 管理員 |

### 語言設定

| 指令 | 描述 | 權限 |
|------|------|------|
| `/my_language` | 查看您的語言設定 | 所有人 |
| `/set_language` | 設定您的語言偏好 | 所有人 |
| `/reset_language` | 重置您的語言設定 | 所有人 |

### Web 認證

| 指令 | 描述 | 權限 |
|------|------|------|
| `/setup-web-password` | 設定 Web 介面登入密碼 | 所有人 |
| `/create-api-key` | 創建 API 金鑰 | 客服+ |
| `/list-api-keys` | 列出我的 API 金鑰 | 客服+ |
| `/revoke-api-key` | 撤銷 API 金鑰 | 客服+ |
| `/web-login-info` | 顯示 Web 登入資訊 | 所有人 |

## 文字指令

### 票券系統文字指令

| 指令 | 描述 | 權限 |
|------|------|------|
| `!setup_ticket` | 建立票券面板 | 管理員 |
| `!set_ticket_category` | 設定票券分類頻道 | 管理員 |
| `!ticket_settings` | 查看目前票券系統設定 | 管理員 |
| `!ticket_test` | 測試票券系統是否正常運作 | 管理員 |
| `!ticket_help` | 顯示票券系統指令說明 | 所有人 |

#### 票券指派與管理

| 指令 | 描述 | 權限 |
|------|------|------|
| `!assign_ticket` | 手動指派票券給客服人員 | 客服+ |
| `!auto_assign` | 自動指派票券 | 客服+ |
| `!staff_workload` | 查看客服工作量 | 客服+ |
| `!add_specialty` | 設定客服專精 | 客服+ |
| `!assignment_stats` | 查看指派統計 | 客服+ |

#### 統計與標籤

| 指令 | 描述 | 權限 |
|------|------|------|
| `!dashboard` | 顯示票券系統統計面板 | 客服+ |
| `!priority_stats` | 查看優先級統計 | 客服+ |
| `!report` | 生成統計摘要報告 | 客服+ |
| `!tag` | 標籤管理指令群組 | 客服+ |

### 系統管理文字指令

| 指令 | 描述 | 權限 |
|------|------|------|
| `!botstatus` | Bot 整體狀態 | Bot 擁有者 |
| `!healthcheck` | 完整健康檢查 | Bot 擁有者 |
| `!welcome` | 歡迎系統管理指令群組 | 管理員 |
| `!language` | 語言系統管理指令群組 | 管理員 |
| `!ai` | AI 系統管理指令群組 | 管理員 |

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

**📝 最後更新：2025-08-11**

## 🔧 指令使用提示

### Discord 指令前綴
- **斜線指令 (`/`)** - 所有現代指令，支援自動完成和參數提示
- **文字指令 (`!`)** - 傳統指令，主要用於高級管理功能

### 權限層級說明
- **所有人** - 無特殊權限要求
- **客服+** - 需要客服或管理員角色
- **管理伺服器+** - 需要管理伺服器權限
- **管理員** - 需要管理員角色
- **Bot 擁有者** - 僅 Bot 擁有者可用

### 快速指令索引

**常用票券指令：**
- `/tickets` - 查看票券列表
- `/close` - 關閉票券
- `/add_tag` - 添加標籤
- `/set_priority` - 設定優先級

**管理功能：**
- `/admin` - 系統管理面板
- `/basic_dashboard` - 基礎儀表板
- `/system_status` - 系統狀態

**投票功能：**
- `/vote` - 創建投票
- `/votes` - 查看投票

**抽獎功能：**
- `/create_lottery_quick` - 快速創建抽獎
- `/join_lottery` - 參與抽獎

**AI 輔助：**
- `/ai_suggest` - AI 回覆建議
- `/ai_priority` - AI 優先級評估

## 📝 更新說明

### v2.1.0 (2025-08-11) - 功能完整版

**🆕 新增功能：**
- ✅ 完整的斜線指令系統 (58+ 指令)
- ✅ AI 增強票券處理系統
- ✅ 高級分析儀表板系統
- ✅ 工作流程自動化系統
- ✅ Webhook 整合系統
- ✅ 多語言支援系統
- ✅ 抽獎系統完整功能

**🔧 系統修復：**
- 修復資料庫健康檢查顯示異常
- 修復抽獎資料表缺失問題
- 修復 DashboardManager 缺少方法
- 修復 Discord 互動超時問題
- 修復 API 權限規則和認證系統

**✨ 系統改進：**
- 統一的互動超時處理機制
- 改進的資料庫清理策略
- 增強的錯誤處理和日誌記錄
- 優化的 REST API 認證系統

**📊 系統檢測：**
- 核心系統完整性：✅ 100%
- 指令系統可用性：✅ 58+ 指令正常
- API 系統穩定性：✅ 完整功能
- 資料庫健康狀態：✅ 所有表格正常
- 整體系統穩定性：✅ 生產就緒