# 🔗 API 參考文檔

> 完整的 REST API 和 WebSocket 介面規範

## 📋 API 概覽

Potato Bot 提供完整的 RESTful API 和 WebSocket 介面，支援第三方整合和客製化應用開發。

### 🌐 基本資訊

| 項目 | 詳情 |
|------|------|
| **Base URL** | `https://your-bot-domain.com/api/v1` |
| **認證方式** | Bearer Token (JWT) |
| **資料格式** | JSON |
| **字元編碼** | UTF-8 |
| **HTTPS** | ✅ 強制使用 |
| **CORS** | ✅ 支援跨域請求 |

### 📊 API 狀態

| 端點類別 | 狀態 | 版本 | 說明 |
|----------|------|------|------|
| **認證 API** | ✅ 穩定 | v1.0 | 用戶認證與授權 |
| **票券 API** | ✅ 穩定 | v1.2 | 票券管理系統 |
| **投票 API** | ✅ 穩定 | v1.1 | 投票功能介面 |
| **統計 API** | ✅ 穩定 | v1.0 | 數據分析與報告 |
| **WebSocket** | ✅ 穩定 | v1.0 | 實時通信 |

## 🔐 認證與授權

### 獲取 API Token

```http
POST /api/v1/auth/token
Content-Type: application/json

{
  "discord_id": "123456789012345678",
  "guild_id": "987654321098765432"
}
```

**回應:**
```json
{
  "access_token": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...",
  "token_type": "bearer",
  "expires_in": 3600,
  "refresh_token": "def502001f35c3..."
}
```

### 使用 Token

```http
GET /api/v1/tickets
Authorization: Bearer eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...
```

## 🎫 票券管理 API

### 獲取票券列表

```http
GET /api/v1/tickets
```

**查詢參數:**
| 參數 | 類型 | 必填 | 說明 |
|------|------|------|------|
| `status` | string | ❌ | 票券狀態: `open`, `closed`, `pending` |
| `assignee` | string | ❌ | 指派人員 Discord ID |
| `priority` | string | ❌ | 優先級: `high`, `medium`, `low` |
| `page` | integer | ❌ | 頁數 (預設: 1) |
| `limit` | integer | ❌ | 每頁筆數 (預設: 20, 最大: 100) |

**回應:**
```json
{
  "tickets": [
    {
      "id": "T20250904001",
      "title": "登入問題",
      "description": "無法正常登入機器人",
      "status": "open",
      "priority": "high",
      "creator": {
        "id": "123456789012345678",
        "username": "user123",
        "avatar": "https://cdn.discordapp.com/avatars/..."
      },
      "assignee": {
        "id": "987654321098765432", 
        "username": "support_staff",
        "avatar": "https://cdn.discordapp.com/avatars/..."
      },
      "created_at": "2025-09-04T12:30:00Z",
      "updated_at": "2025-09-04T14:15:00Z",
      "tags": ["技術支援", "登入問題"],
      "channel_id": "808123456789012345"
    }
  ],
  "pagination": {
    "page": 1,
    "limit": 20,
    "total": 156,
    "pages": 8
  }
}
```

### 創建票券

```http
POST /api/v1/tickets
Content-Type: application/json

{
  "title": "無法使用投票功能",
  "description": "投票按鈕點擊後沒有反應",
  "priority": "medium",
  "category": "功能問題",
  "tags": ["投票系統", "UI問題"]
}
```

**回應:**
```json
{
  "id": "T20250904002",
  "title": "無法使用投票功能",
  "status": "open",
  "priority": "medium", 
  "creator_id": "123456789012345678",
  "created_at": "2025-09-04T15:30:00Z",
  "channel_id": "808123456789012346"
}
```

### 更新票券

```http
PATCH /api/v1/tickets/{ticket_id}
Content-Type: application/json

{
  "status": "closed",
  "resolution": "已修復投票按鈕問題",
  "assignee_id": "987654321098765432"
}
```

## 🗳️ 投票系統 API

### 獲取投票列表

```http
GET /api/v1/votes
```

**回應:**
```json
{
  "votes": [
    {
      "id": "V20250904001",
      "title": "下週團隊聚餐地點",
      "description": "選擇大家都方便的餐廳",
      "status": "active",
      "type": "single_choice",
      "options": [
        {
          "id": 1,
          "text": "🍕 義式餐廳",
          "votes": 67,
          "percentage": 43.2
        },
        {
          "id": 2, 
          "text": "🍜 拉麵店",
          "votes": 34,
          "percentage": 21.9
        }
      ],
      "total_votes": 155,
      "participation_rate": "78%",
      "creator_id": "123456789012345678",
      "created_at": "2025-09-01T09:00:00Z",
      "ends_at": "2025-09-08T18:00:00Z"
    }
  ]
}
```

### 創建投票

```http
POST /api/v1/votes  
Content-Type: application/json

{
  "title": "新功能優先級投票",
  "description": "選擇最希望優先開發的功能",
  "type": "multiple_choice",
  "max_choices": 2,
  "options": [
    "語音通話整合",
    "遊戲統計追蹤", 
    "自訂表情符號",
    "進階權限管理"
  ],
  "duration": "7d",
  "privacy": "public",
  "anonymous": false
}
```

### 參與投票

```http
POST /api/v1/votes/{vote_id}/vote
Content-Type: application/json

{
  "choices": [1, 3]
}
```

**回應:**
```json
{
  "success": true,
  "vote_id": "V20250904001",
  "choices": [1, 3],
  "timestamp": "2025-09-04T16:45:00Z"
}
```

## 📊 統計分析 API

### 伺服器統計

```http
GET /api/v1/stats/server
```

**回應:**
```json
{
  "server": {
    "guild_id": "987654321098765432",
    "name": "Amazing Discord Server",
    "member_count": 1247,
    "online_members": 342,
    "bot_uptime": "7d 14h 23m",
    "commands_used_today": 89
  },
  "tickets": {
    "total": 1543,
    "open": 23,
    "closed": 1520,
    "avg_response_time": "2h 15m",
    "satisfaction_rate": "94%"
  },
  "votes": {
    "total": 234,
    "active": 5,
    "completed": 229,
    "avg_participation": "72%"
  }
}
```

### 用戶活動統計

```http
GET /api/v1/stats/users
```

**查詢參數:**
- `period` - 統計期間: `day`, `week`, `month`
- `limit` - 返回用戶數量 (預設: 10)

## 🔄 WebSocket API

### 連接端點

```javascript
const ws = new WebSocket('wss://your-bot-domain.com/api/ws/live');

ws.onopen = function() {
  // 認證
  ws.send(JSON.stringify({
    type: 'auth',
    token: 'your-jwt-token'
  }));
};
```

### 訂閱投票更新

```javascript
// 訂閱特定投票
ws.send(JSON.stringify({
  type: 'subscribe',
  channel: 'vote:V20250904001'
}));

// 接收實時更新
ws.onmessage = function(event) {
  const data = JSON.parse(event.data);
  
  if (data.type === 'vote_update') {
    console.log('投票更新:', data.vote);
    // 更新 UI 顯示
  }
};
```

### 訂閱票券通知

```javascript
// 訂閱新票券通知
ws.send(JSON.stringify({
  type: 'subscribe', 
  channel: 'tickets:new'
}));

ws.onmessage = function(event) {
  const data = JSON.parse(event.data);
  
  if (data.type === 'ticket_created') {
    console.log('新票券:', data.ticket);
    // 顯示通知
  }
};
```

## 📝 資料模型

### 票券 (Ticket)

```typescript
interface Ticket {
  id: string;                    // 票券 ID
  title: string;                 // 標題
  description: string;           // 描述  
  status: 'open' | 'closed' | 'pending';
  priority: 'high' | 'medium' | 'low';
  creator: User;                 // 創建者
  assignee?: User;               // 指派人員
  tags: string[];                // 標籤
  created_at: string;            // 創建時間 (ISO 8601)
  updated_at: string;            // 更新時間
  channel_id: string;            // Discord 頻道 ID
}
```

### 投票 (Vote)

```typescript
interface Vote {
  id: string;                    // 投票 ID
  title: string;                 // 標題
  description?: string;          // 描述
  status: 'active' | 'ended' | 'cancelled';
  type: 'single_choice' | 'multiple_choice' | 'ranking';
  options: VoteOption[];         // 選項列表
  total_votes: number;           // 總票數
  participation_rate: string;    // 參與率
  creator_id: string;            // 創建者 ID
  created_at: string;            // 創建時間
  ends_at?: string;              // 結束時間
  settings: VoteSettings;        // 投票設定
}

interface VoteOption {
  id: number;                    // 選項 ID
  text: string;                  // 選項文字
  votes: number;                 // 得票數
  percentage: number;            // 得票率
}
```

### 用戶 (User)

```typescript
interface User {
  id: string;                    // Discord 用戶 ID
  username: string;              // 用戶名
  discriminator?: string;        // 識別碼 (已棄用)
  avatar?: string;               // 頭像 URL
  bot: boolean;                  // 是否為機器人
  system?: boolean;              // 是否為系統帳號
}
```

## ⚠️ 錯誤處理

### 標準錯誤格式

```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "請求資料驗證失敗",
    "details": {
      "field": "title",
      "issue": "標題不能為空"
    },
    "timestamp": "2025-09-04T16:30:00Z",
    "request_id": "req_1234567890"
  }
}
```

### 常見錯誤碼

| HTTP 狀態 | 錯誤碼 | 說明 |
|-----------|--------|------|
| `400` | `VALIDATION_ERROR` | 請求資料格式錯誤 |
| `401` | `UNAUTHORIZED` | 認證失敗或 Token 無效 |
| `403` | `FORBIDDEN` | 權限不足 |
| `404` | `NOT_FOUND` | 資源不存在 |
| `429` | `RATE_LIMITED` | 請求頻率超限 |
| `500` | `INTERNAL_ERROR` | 伺服器內部錯誤 |

## 🚦 速率限制

| 端點類型 | 限制 | 時間窗口 |
|----------|------|----------|
| **認證端點** | 5 requests | 1 分鐘 |
| **讀取端點** | 100 requests | 1 分鐘 |
| **寫入端點** | 30 requests | 1 分鐘 |
| **WebSocket** | 50 messages | 1 分鐘 |

### 速率限制標頭

```http
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 95
X-RateLimit-Reset: 1725456000
```

## 📚 SDK 和範例

### Python SDK 範例

```python
import requests
from potato_bot_sdk import PotatoBotAPI

# 初始化 API 客戶端
api = PotatoBotAPI(
    base_url="https://your-bot-domain.com/api/v1",
    token="your-jwt-token"
)

# 獲取票券列表
tickets = api.tickets.list(status="open", limit=10)

# 創建新票券
new_ticket = api.tickets.create(
    title="API 測試票券",
    description="透過 API 創建的測試票券",
    priority="medium"
)

# 參與投票
api.votes.vote("V20250904001", choices=[1, 3])
```

### JavaScript SDK 範例

```javascript
import { PotatoBotAPI } from 'potato-bot-sdk';

const api = new PotatoBotAPI({
  baseURL: 'https://your-bot-domain.com/api/v1',
  token: 'your-jwt-token'
});

// 獲取伺服器統計
const stats = await api.stats.getServer();

// 建立 WebSocket 連線
const ws = api.websocket.connect();
ws.subscribe('vote:V20250904001', (data) => {
  console.log('投票更新:', data);
});
```

## 🧪 測試環境

### Sandbox API

開發和測試環境：

- **Base URL**: `https://sandbox.your-bot-domain.com/api/v1`
- **測試 Token**: 使用測試用 Discord 機器人
- **資料重置**: 每日午夜自動重置測試資料

### Postman Collection

匯入我們的 Postman Collection 快速開始測試：

```bash
# 下載 Collection
curl -o potato-bot-api.json https://your-domain.com/api/postman-collection.json

# 匯入到 Postman 並設置環境變數
```

---

🚀 **開始 API 整合！**

我們的 API 設計簡單易用，文檔詳盡。有任何問題請參考 [故障排除指南](troubleshooting.md) 或 [聯繫技術支援](#)。

需要更多功能？查看 [系統設計文檔](../system-design/admin-permissions.md) 了解完整架構。