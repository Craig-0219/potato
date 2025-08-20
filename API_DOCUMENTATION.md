# 📡 Potato Bot v3.0.1 - API 文檔

> **🏛️ 企業級全功能 Discord Bot 系統 - REST API & WebSocket 文檔**

---

## 🎯 API 概覽

Potato Bot v3.0.1 提供完整的 REST API 和 WebSocket 接口，支援企業級多伺服器架構，具備完整的 GDPR 合規性和零信任安全模型。

### 🔒 **安全特性**
- **OAuth2 認證** - Discord OAuth2 整合
- **JWT Token** - 安全的會話管理
- **RBAC 權限控制** - 階層式權限驗證
- **速率限制** - 防止 API 濫用
- **完整審計** - 所有 API 調用記錄

### 🏢 **多伺服器支援**
- **完全數據隔離** - 基於 guild_id 的強制隔離
- **伺服器驗證** - 所有請求強制伺服器驗證
- **資源配額** - 個別伺服器資源限制
- **安全邊界** - 零交叉存取保證

---

## 🌐 API 基礎資訊

### 📋 **基本資訊**
```
Base URL: http://localhost:8000
WebSocket: ws://localhost:8000/ws
API Version: v3.0.1
Authentication: Bearer JWT Token
Content-Type: application/json
```

### 🔐 **認證方式**

#### Discord OAuth2 認證
```
1. 重導向到: /auth/discord
2. 授權後回調: /auth/discord/callback
3. 取得 JWT Token
4. Header: Authorization: Bearer <token>
```

#### API Key 認證 (企業版)
```
Header: X-API-Key: <your-api-key>
```

---

## 🏛️ 伺服器管理 API

### 📊 **伺服器統計**

#### `GET /api/guild/{guild_id}/stats`
取得伺服器基本統計資訊

**參數:**
- `guild_id` (int): Discord 伺服器 ID

**回應:**
```json
{
  "guild_id": 1234567890,
  "stats": {
    "total_tickets": 145,
    "active_tickets": 23,
    "total_votes": 67,
    "active_votes": 5,
    "daily_active_users": 234,
    "commands_used_today": 1250
  },
  "performance": {
    "avg_response_time": 95,
    "success_rate": 0.997,
    "uptime_percentage": 99.97
  }
}
```

#### `GET /api/guild/{guild_id}/analytics`
取得詳細分析儀表板數據

**參數:**
- `guild_id` (int): Discord 伺服器 ID  
- `days` (int, optional): 分析天數 (1-30, 預設 7)

**回應:**
```json
{
  "guild_id": 1234567890,
  "time_range": {
    "start_date": "2024-12-13",
    "end_date": "2024-12-20",
    "days": 7
  },
  "current_metrics": {
    "total_tickets": 145,
    "open_tickets_count": 23,
    "total_votes_today": 12,
    "api_calls_today": 1456,
    "daily_active_users": 234,
    "security_events_today": 0,
    "mfa_adoption_rate": 0.85
  },
  "trends": {
    "tickets_trend": {
      "change_rate": 0.15,
      "direction": "up"
    },
    "votes_trend": {
      "change_rate": -0.05,
      "direction": "down"
    }
  },
  "performance": {
    "avg_response_time": 67.5,
    "max_response_time": 145,
    "total_requests_24h": 2341
  },
  "recent_alerts": [
    {
      "timestamp": "2024-12-20T10:30:00Z",
      "event_name": "高錯誤率警告",
      "severity": "warning",
      "description": "API 錯誤率超過 5%"
    }
  ]
}
```

---

## 🎫 票券系統 API

### 📋 **票券管理**

#### `GET /api/tickets`
取得票券列表

**查詢參數:**
- `guild_id` (int, required): 伺服器 ID
- `status` (string, optional): 票券狀態 (open, closed, pending)
- `assigned_to` (int, optional): 分配給的用戶 ID
- `page` (int, optional): 頁數 (預設 1)
- `page_size` (int, optional): 每頁數量 (預設 20)

**回應:**
```json
{
  "tickets": [
    {
      "id": 123,
      "guild_id": 1234567890,
      "discord_id": "9876543210",
      "username": "用戶名稱",
      "type": "technical_support",
      "priority": "high",
      "status": "open",
      "subject": "登入問題",
      "description": "無法登入帳戶",
      "created_at": "2024-12-20T10:00:00Z",
      "assigned_to": 1111111111,
      "channel_id": 2222222222
    }
  ],
  "pagination": {
    "total": 145,
    "page": 1,
    "page_size": 20,
    "total_pages": 8
  }
}
```

#### `POST /api/tickets`
建立新票券

**請求體:**
```json
{
  "guild_id": 1234567890,
  "discord_id": "9876543210",
  "username": "用戶名稱",
  "type": "general_inquiry",
  "priority": "medium",
  "subject": "一般詢問",
  "description": "我有一個關於功能的問題"
}
```

#### `PUT /api/tickets/{ticket_id}`
更新票券

**請求體:**
```json
{
  "status": "closed",
  "priority": "low",
  "assigned_to": 1111111111,
  "close_reason": "問題已解決",
  "rating": 5,
  "rating_feedback": "服務很好"
}
```

---

## 🗳️ 投票系統 API

### 📊 **投票管理**

#### `GET /api/votes`
取得投票列表

**查詢參數:**
- `guild_id` (int, required): 伺服器 ID
- `status` (string, optional): 投票狀態 (active, ended, draft)
- `creator_id` (int, optional): 創建者 ID

**回應:**
```json
{
  "votes": [
    {
      "id": 456,
      "guild_id": 1234567890,
      "title": "下次活動時間投票",
      "description": "請選擇下次線上活動的時間",
      "creator_id": "1111111111",
      "status": "active",
      "is_anonymous": false,
      "allows_multiple_choice": true,
      "created_at": "2024-12-20T10:00:00Z",
      "ends_at": "2024-12-27T23:59:59Z",
      "options": [
        {
          "id": 1,
          "text": "週六下午 2:00",
          "votes_count": 15
        },
        {
          "id": 2,
          "text": "週日晚上 8:00", 
          "votes_count": 23
        }
      ],
      "total_votes": 38,
      "total_participants": 35
    }
  ]
}
```

#### `POST /api/votes`
建立新投票

**請求體:**
```json
{
  "guild_id": 1234567890,
  "title": "新功能投票",
  "description": "您希望我們下個月推出什麼新功能？",
  "options": [
    "更多 AI 功能",
    "遊戲整合",
    "音樂播放器升級"
  ],
  "duration_hours": 168,
  "is_anonymous": false,
  "allows_multiple_choice": true
}
```

---

## 🔒 安全管理 API

### 👥 **權限管理**

#### `GET /api/permissions/{guild_id}`
取得伺服器權限設定

**回應:**
```json
{
  "guild_id": 1234567890,
  "roles": [
    {
      "role": "owner",
      "users": ["292993868092276736"],
      "permissions": [
        "system:admin",
        "data:export",
        "data:delete",
        "user:manage",
        "security:admin"
      ]
    },
    {
      "role": "admin", 
      "users": ["1111111111", "2222222222"],
      "permissions": [
        "ticket:admin",
        "vote:admin", 
        "user:moderate"
      ]
    }
  ]
}
```

#### `POST /api/permissions/{guild_id}/assign`
分配用戶角色

**請求體:**
```json
{
  "user_id": "1111111111",
  "role": "admin",
  "assigned_by": "292993868092276736"
}
```

### 📊 **安全事件**

#### `GET /api/security/events/{guild_id}`
取得安全事件記錄

**查詢參數:**
- `severity` (string, optional): 事件嚴重程度
- `event_type` (string, optional): 事件類型
- `limit` (int, optional): 限制數量

**回應:**
```json
{
  "events": [
    {
      "id": 789,
      "guild_id": 1234567890,
      "event_type": "permission_denied",
      "severity": "warning",
      "user_id": "3333333333",
      "description": "用戶嘗試存取無權限的資源",
      "metadata": {
        "resource": "admin_panel",
        "ip_address": "192.168.1.100"
      },
      "timestamp": "2024-12-20T10:30:00Z"
    }
  ]
}
```

---

## 🇪🇺 GDPR 合規 API

### 📤 **數據導出**

#### `POST /api/gdpr/export/{guild_id}`
請求數據導出 (GDPR Article 20)

**請求體:**
```json
{
  "data_types": ["business_data", "configuration_data"],
  "format": "json",
  "include_personal_data": true
}
```

**回應:**
```json
{
  "export_id": "exp_1234567890abcdef",
  "status": "processing",
  "estimated_completion": "2024-12-20T11:00:00Z",
  "download_url": null
}
```

#### `GET /api/gdpr/export/{export_id}/status`
檢查導出狀態

**回應:**
```json
{
  "export_id": "exp_1234567890abcdef",
  "status": "completed",
  "created_at": "2024-12-20T10:30:00Z",
  "completed_at": "2024-12-20T10:45:00Z",
  "file_size_mb": 2.5,
  "download_url": "/api/gdpr/download/exp_1234567890abcdef"
}
```

### 🗑️ **數據刪除**

#### `POST /api/gdpr/delete/{guild_id}`
請求數據刪除 (GDPR Article 17)

**請求體:**
```json
{
  "data_types": ["personal_data"],
  "hard_delete": false,
  "confirmation": "CONFIRM"
}
```

**回應:**
```json
{
  "deletion_id": "del_1234567890abcdef",
  "status": "completed",
  "deleted_records": {
    "api_users": 1,
    "user_mfa": 1,
    "guild_user_permissions": 1
  },
  "retained_records": {
    "tickets": "15 筆已匿名化",
    "votes": "8 筆已匿名化"
  }
}
```

---

## 📡 WebSocket API

### 🔗 **連接建立**

```javascript
const ws = new WebSocket('ws://localhost:8000/ws');

// 認證
ws.send(JSON.stringify({
  type: 'auth',
  token: 'your-jwt-token',
  guild_id: 1234567890
}));
```

### 📊 **即時數據訂閱**

#### 訂閱即時統計
```javascript
// 訂閱
ws.send(JSON.stringify({
  type: 'subscribe',
  channel: 'guild_stats',
  guild_id: 1234567890
}));

// 接收即時數據
ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  if (data.type === 'guild_stats_update') {
    console.log('新的統計數據:', data.stats);
  }
};
```

#### 訂閱投票更新
```javascript
// 訂閱特定投票
ws.send(JSON.stringify({
  type: 'subscribe', 
  channel: 'vote_updates',
  vote_id: 456
}));

// 接收投票更新
ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  if (data.type === 'vote_update') {
    console.log('投票更新:', data.vote);
  }
};
```

### 🚨 **即時警報**

```javascript
// 訂閱安全警報
ws.send(JSON.stringify({
  type: 'subscribe',
  channel: 'security_alerts', 
  guild_id: 1234567890
}));

// 接收警報
ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  if (data.type === 'security_alert') {
    console.log('安全警報:', data.alert);
  }
};
```

---

## ⚠️ 錯誤處理

### 📋 **HTTP 狀態碼**

| 狀態碼 | 說明 | 範例 |
|-------|------|------|
| 200 | 成功 | 請求成功處理 |
| 400 | 請求錯誤 | 參數格式錯誤 |
| 401 | 未授權 | Token 無效或過期 |
| 403 | 禁止存取 | 權限不足 |
| 404 | 資源不存在 | 票券或投票不存在 |
| 429 | 速率限制 | API 調用過於頻繁 |
| 500 | 伺服器錯誤 | 內部系統錯誤 |

### 🔒 **安全錯誤**

```json
{
  "error": {
    "code": "TENANT_ISOLATION_VIOLATION",
    "message": "無權存取指定伺服器的資源",
    "details": {
      "guild_id": 1234567890,
      "user_id": "9876543210",
      "attempted_resource": "ticket:123"
    },
    "timestamp": "2024-12-20T10:30:00Z"
  }
}
```

### 🚫 **GDPR 合規錯誤**

```json
{
  "error": {
    "code": "GDPR_COMPLIANCE_VIOLATION", 
    "message": "數據處理不符合 GDPR 要求",
    "details": {
      "article": "Article 17",
      "requirement": "數據刪除請求處理",
      "reason": "用戶未提供有效的身份驗證"
    }
  }
}
```

---

## 🚀 速率限制

### 📊 **限制規則**

| 端點類型 | 限制 | 時間窗口 | 
|----------|------|----------|
| 一般 API | 100 req/min | 每分鐘 |
| 統計查詢 | 30 req/min | 每分鐘 |
| 數據導出 | 5 req/hour | 每小時 |
| 數據刪除 | 2 req/day | 每天 |
| WebSocket | 1000 msg/min | 每分鐘 |

### 🔧 **速率限制標頭**

```
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 95
X-RateLimit-Reset: 1640000000
X-RateLimit-Window: 60
```

---

## 📚 SDK 和範例

### 🐍 **Python SDK 範例**

```python
import requests
from datetime import datetime

class PotatoBotAPI:
    def __init__(self, token, base_url="http://localhost:8000"):
        self.token = token
        self.base_url = base_url
        self.headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
    
    def get_guild_stats(self, guild_id):
        response = requests.get(
            f"{self.base_url}/api/guild/{guild_id}/stats",
            headers=self.headers
        )
        return response.json()
    
    def create_ticket(self, guild_id, ticket_data):
        response = requests.post(
            f"{self.base_url}/api/tickets",
            headers=self.headers,
            json={**ticket_data, "guild_id": guild_id}
        )
        return response.json()
    
    def export_data(self, guild_id, data_types, format="json"):
        response = requests.post(
            f"{self.base_url}/api/gdpr/export/{guild_id}",
            headers=self.headers,
            json={
                "data_types": data_types,
                "format": format,
                "include_personal_data": True
            }
        )
        return response.json()

# 使用範例
api = PotatoBotAPI("your-jwt-token")
stats = api.get_guild_stats(1234567890)
print(f"活躍票券數: {stats['stats']['active_tickets']}")
```

### 🌐 **JavaScript SDK 範例**

```javascript
class PotatoBotAPI {
  constructor(token, baseUrl = 'http://localhost:8000') {
    this.token = token;
    this.baseUrl = baseUrl;
    this.headers = {
      'Authorization': `Bearer ${token}`,
      'Content-Type': 'application/json'
    };
  }

  async getGuildAnalytics(guildId, days = 7) {
    const response = await fetch(
      `${this.baseUrl}/api/guild/${guildId}/analytics?days=${days}`,
      { headers: this.headers }
    );
    return response.json();
  }

  async createVote(guildId, voteData) {
    const response = await fetch(
      `${this.baseUrl}/api/votes`,
      {
        method: 'POST',
        headers: this.headers,
        body: JSON.stringify({ ...voteData, guild_id: guildId })
      }
    );
    return response.json();
  }

  connectWebSocket(guildId) {
    const ws = new WebSocket(`ws://localhost:8000/ws`);
    
    ws.onopen = () => {
      ws.send(JSON.stringify({
        type: 'auth',
        token: this.token,
        guild_id: guildId
      }));
    };

    return ws;
  }
}

// 使用範例
const api = new PotatoBotAPI('your-jwt-token');
const analytics = await api.getGuildAnalytics(1234567890, 14);
console.log('伺服器分析:', analytics.current_metrics);
```

---

<div align="center">

## 🎉 **API 文檔完成**

### 🏛️ **Potato Bot v3.0.1 - 企業級 API**
### 🔒 **多租戶架構 | GDPR 合規 | 零信任安全**

[![API 版本](https://img.shields.io/badge/API-v3.0.1-success?style=for-the-badge)](API_DOCUMENTATION.md)
[![文檔狀態](https://img.shields.io/badge/文檔-完整-blue?style=for-the-badge)](API_DOCUMENTATION.md)
[![安全等級](https://img.shields.io/badge/安全-企業級-green?style=for-the-badge)](PHASE_6_COMPLETION_REPORT.md)

**🌟 強大的 API 為您的應用提供企業級 Discord 管理能力 🌟**

**[🚀 快速開始](DEPLOYMENT_GUIDE.md) • [📚 完整文檔](docs/README.md) • [💬 API 支援](https://discord.gg/potato-dev)**

---

*🛡️ 零信任架構 • 🇪🇺 GDPR 合規 • 📊 即時分析 • 🔒 企業級安全*

</div>