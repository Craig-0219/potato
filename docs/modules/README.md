# 🧩 系統模組開發文檔

本目錄包含所有核心模組的技術架構、開發指南和 API 規範。

## 📚 模組架構概覽

### 🏗️ 系統分層架構

```
┌─────────────────────────────────────────┐
│           Presentation Layer            │
│  ┌─────────────────┐ ┌─────────────────┐ │
│  │   Discord Bot   │ │   Web Interface │ │
│  │     (Cogs)      │ │    (React UI)   │ │
│  └─────────────────┘ └─────────────────┘ │
└─────────────────────────────────────────┘
┌─────────────────────────────────────────┐
│            API Gateway                  │
│  ┌─────────────────┐ ┌─────────────────┐ │
│  │   REST API      │ │   WebSocket     │ │
│  │   (FastAPI)     │ │   (Real-time)   │ │
│  └─────────────────┘ └─────────────────┘ │
└─────────────────────────────────────────┘
┌─────────────────────────────────────────┐
│           Business Layer                │
│  ┌─────────┐ ┌─────────┐ ┌─────────────┐ │
│  │ Tickets │ │  Votes  │ │ AI Services │ │
│  │ Service │ │ Service │ │   Module    │ │
│  └─────────┘ └─────────┘ └─────────────┘ │
└─────────────────────────────────────────┘
┌─────────────────────────────────────────┐
│            Data Layer                   │
│  ┌─────────┐ ┌─────────┐ ┌─────────────┐ │
│  │Database │ │  Cache  │ │   Search    │ │
│  │  (DAO)  │ │ (Redis) │ │ (Optional)  │ │
│  └─────────┘ └─────────┘ └─────────────┘ │
└─────────────────────────────────────────┘
┌─────────────────────────────────────────┐
│            Shared Layer                 │
│  ┌─────────┐ ┌─────────┐ ┌─────────────┐ │
│  │ Config  │ │  Utils  │ │   Models    │ │
│  │Manager  │ │ Library │ │ & Schemas   │ │
│  └─────────┘ └─────────┘ └─────────────┘ │
└─────────────────────────────────────────┘
```

## 🤖 Bot 核心模組

### 📋 模組清單
- **[Discord Cogs](bot-cogs.md)** - Discord 指令和事件處理
- **[API 服務](bot-api.md)** - REST API 和 WebSocket 服務
- **[資料庫存取](bot-database.md)** - 資料存取層 (DAO)
- **[業務服務](bot-services.md)** - 核心業務邏輯
- **[工具模組](bot-utils.md)** - 共用工具和輔助函數

### 🎯 模組職責矩陣

| 模組 | 主要職責 | 依賴關係 | 對外接口 |
|------|----------|----------|----------|
| **Cogs** | Discord 指令處理 | Services | Discord API |
| **API** | Web API 服務 | Services, Database | HTTP/WebSocket |
| **Services** | 業務邏輯實現 | Database, Utils | Python API |
| **Database** | 資料存取抽象 | Shared/Config | DAO Interface |
| **Utils** | 共用工具函數 | - | Helper Functions |

### 🔄 模組互動流程

```python
# 典型的請求處理流程
┌─────────────┐    ┌──────────────┐    ┌─────────────┐
│ Discord Bot │───▶│   Service    │───▶│  Database   │
│    (Cog)    │    │   Layer      │    │    (DAO)    │
└─────────────┘    └──────────────┘    └─────────────┘
       │                   │                   │
       │            ┌──────▼──────┐           │
       │            │   Shared    │           │
       │            │   Utils     │           │
       │            └─────────────┘           │
       │                                      │
       └──────────────────────────────────────┘
              回傳處理結果
```

## 🔄 共用模組 (shared/)

### 📦 共用組件
- **[配置管理](shared-config.md)** - 環境配置和設定管理
- **[資料模型](shared-models.md)** - Pydantic 模型和資料結構
- **[工具函數](shared-utils.md)** - 跨模組共用的工具函數
- **[常數定義](shared-constants.md)** - 系統常數和列舉值
- **[異常處理](shared-exceptions.md)** - 自訂異常和錯誤處理

### 🏗️ 共用模組設計原則
```python
# 配置管理範例
from pydantic import BaseSettings
from typing import Optional

class Settings(BaseSettings):
    # Discord 設定
    discord_token: str
    guild_id: int
    
    # 資料庫設定
    database_url: str
    redis_url: Optional[str] = None
    
    # API 設定
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    secret_key: str
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

# 單例模式配置
settings = Settings()
```

### 📊 資料模型範例
```python
from pydantic import BaseModel, Field
from datetime import datetime
from enum import Enum

class TicketStatus(str, Enum):
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    PENDING = "pending"
    RESOLVED = "resolved"
    CLOSED = "closed"

class TicketModel(BaseModel):
    id: Optional[int] = None
    title: str = Field(..., min_length=1, max_length=200)
    description: str = Field(..., min_length=1)
    status: TicketStatus = TicketStatus.OPEN
    priority: str = "medium"
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    
    class Config:
        orm_mode = True
        use_enum_values = True
```

## 🌐 Web UI 模組

### 🎨 前端架構
- **[組件系統](webui-components.md)** - React 組件架構
- **[狀態管理](webui-state.md)** - 全域狀態管理方案
- **[API 整合](webui-api.md)** - 前後端資料整合
- **[路由系統](webui-routing.md)** - 頁面路由和導航
- **[主題系統](webui-theming.md)** - UI 主題和樣式管理

### 🛠️ 前端技術棧
```typescript
// 主要技術組合
import React from 'react';
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from 'react-query';
import { ChakraProvider } from '@chakra-ui/react';

// 狀態管理
import { create } from 'zustand';

// API 客戶端
import axios from 'axios';

// 組件範例
interface TicketListProps {
  tickets: Ticket[];
  onTicketSelect: (ticket: Ticket) => void;
}

const TicketList: React.FC<TicketListProps> = ({
  tickets,
  onTicketSelect
}) => {
  return (
    <div className="ticket-list">
      {tickets.map(ticket => (
        <TicketCard
          key={ticket.id}
          ticket={ticket}
          onClick={() => onTicketSelect(ticket)}
        />
      ))}
    </div>
  );
};
```

## 🔗 模組間通信

### 📡 通信模式
1. **同步調用** - 直接函數調用
2. **事件驅動** - Event Bus 模式
3. **依賴注入** - IoC 容器管理
4. **消息隊列** - 異步消息處理

### 🔄 事件系統
```python
from typing import Dict, List, Callable, Any
import asyncio

class EventBus:
    def __init__(self):
        self._listeners: Dict[str, List[Callable]] = {}
    
    def subscribe(self, event_name: str, callback: Callable):
        if event_name not in self._listeners:
            self._listeners[event_name] = []
        self._listeners[event_name].append(callback)
    
    async def emit(self, event_name: str, data: Any = None):
        if event_name in self._listeners:
            tasks = []
            for callback in self._listeners[event_name]:
                if asyncio.iscoroutinefunction(callback):
                    tasks.append(callback(data))
                else:
                    callback(data)
            
            if tasks:
                await asyncio.gather(*tasks)

# 全域事件總線
event_bus = EventBus()

# 使用範例
@event_bus.subscribe('ticket_created')
async def on_ticket_created(ticket_data):
    # 處理票券創建事件
    await send_notification(ticket_data)
```

## 🔐 模組安全設計

### 🛡️ 安全原則
1. **最小權限原則** - 模組僅擁有必要權限
2. **輸入驗證** - 所有外部輸入都要驗證
3. **輸出編碼** - 防止注入攻擊
4. **錯誤處理** - 不洩露敏感資訊

### 🔒 安全實現
```python
from functools import wraps
import hashlib
import secrets

# 權限裝飾器
def require_permission(permission: str):
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            user = kwargs.get('current_user')
            if not user or not user.has_permission(permission):
                raise PermissionError(f"需要 {permission} 權限")
            return await func(*args, **kwargs)
        return wrapper
    return decorator

# 輸入驗證
def validate_input(schema: BaseModel):
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            try:
                validated_data = schema(**kwargs)
                kwargs.update(validated_data.dict())
            except ValidationError as e:
                raise ValueError(f"輸入驗證失敗: {e}")
            return await func(*args, **kwargs)
        return wrapper
    return decorator

# API 密鑰生成
def generate_api_key() -> tuple[str, str]:
    key_id = secrets.token_urlsafe(16)
    key_secret = secrets.token_urlsafe(32)
    raw_key = f"{key_id}.{key_secret}"
    hashed_key = hashlib.sha256(raw_key.encode()).hexdigest()
    return raw_key, hashed_key
```

## 📊 模組效能監控

### 📈 效能指標
- **回應時間** - API 端點回應時間
- **吞吐量** - 每秒處理請求數
- **資源使用** - CPU、記憶體使用率
- **錯誤率** - 錯誤請求比例

### 🔍 監控實現
```python
import time
import functools
from prometheus_client import Counter, Histogram, Gauge

# Prometheus 指標
REQUEST_COUNT = Counter('requests_total', 'Total requests', ['method', 'endpoint'])
REQUEST_DURATION = Histogram('request_duration_seconds', 'Request duration')
ACTIVE_CONNECTIONS = Gauge('active_connections', 'Active connections')

def monitor_performance(func):
    @functools.wraps(func)
    async def wrapper(*args, **kwargs):
        start_time = time.time()
        try:
            result = await func(*args, **kwargs)
            REQUEST_COUNT.labels(method='POST', endpoint='/api/tickets').inc()
            return result
        except Exception as e:
            REQUEST_COUNT.labels(method='POST', endpoint='/api/tickets').inc()
            raise
        finally:
            REQUEST_DURATION.observe(time.time() - start_time)
    return wrapper

# 使用範例
@monitor_performance
async def create_ticket(ticket_data: TicketCreate):
    # 實現票券創建邏輯
    pass
```

## 🧪 模組測試策略

### 📋 測試類型
1. **單元測試** - 個別函數和類別測試
2. **整合測試** - 模組間交互測試
3. **合約測試** - API 合約驗證
4. **端到端測試** - 完整流程測試

### 🔬 測試實現
```python
import pytest
from unittest.mock import Mock, patch
from httpx import AsyncClient

# 單元測試範例
class TestTicketService:
    @pytest.fixture
    def ticket_service(self):
        return TicketService(Mock())
    
    async def test_create_ticket(self, ticket_service):
        ticket_data = TicketCreate(
            title="Test Ticket",
            description="Test Description"
        )
        
        result = await ticket_service.create_ticket(ticket_data)
        
        assert result is not None
        assert result.title == "Test Ticket"

# 整合測試範例
class TestTicketAPI:
    async def test_create_ticket_endpoint(self):
        async with AsyncClient(app=app, base_url="http://test") as client:
            response = await client.post("/api/v1/tickets", json={
                "title": "Integration Test",
                "description": "Test Description"
            })
            
            assert response.status_code == 201
            data = response.json()
            assert data["title"] == "Integration Test"
```

## 📚 模組開發指南

### 🛠️ 開發流程
1. **需求分析** - 確定模組功能和接口
2. **架構設計** - 設計模組結構和依賴
3. **接口定義** - 定義清晰的 API 合約
4. **測試驅動** - 先寫測試再實現功能
5. **文檔更新** - 同步更新技術文檔

### 📋 開發檢查清單
- [ ] 模組職責單一且清晰
- [ ] 接口設計符合 SOLID 原則
- [ ] 包含完整的單元測試
- [ ] 異常處理完善
- [ ] 日誌記錄適當
- [ ] 效能監控到位
- [ ] 文檔更新完整

---

**🔔 開發提醒：**
- 保持模組間低耦合、高內聚
- 使用依賴注入增強可測試性
- 實施全面的錯誤處理
- 監控模組效能和健康狀態

**📅 最後更新：** 2025-08-31  
**🧩 模組數量：** 5 個核心模組  
**📊 架構完成度：** 95%