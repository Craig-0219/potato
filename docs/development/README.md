# 🛠️ 開發指南 - Dev 分支專用

本目錄包含 dev 分支的完整開發文檔，涵蓋環境設置、開發流程、測試策略等。

## 🚀 開發環境設置

### 📋 系統要求
- **Python 3.10+** - 主要開發語言
- **Git** - 版本控制系統
- **MySQL/SQLite** - 資料庫系統
- **Redis** (可選) - 快取系統
- **Node.js 16+** (可選) - Web UI 開發

### 🔧 開發工具鏈
```bash
# 安裝開發依賴
pip install -r requirements.txt
pip install pytest black isort flake8 mypy bandit safety

# 安裝 pre-commit hooks
pre-commit install

# 設置開發環境
cp .env.example .env
# 編輯 .env 填入開發配置
```

### 🐳 Docker 開發環境
```yaml
# docker-compose.dev.yml
version: '3.8'
services:
  app:
    build: 
      context: .
      target: development
    volumes:
      - .:/app
      - /app/__pycache__
    ports:
      - "8000:8000"
    environment:
      - DEBUG=true
      - RELOAD=true
    depends_on:
      - db
      - redis
  
  db:
    image: mysql:8.0
    environment:
      - MYSQL_ROOT_PASSWORD=dev_password
      - MYSQL_DATABASE=potato_bot_dev
    ports:
      - "3306:3306"
    volumes:
      - mysql_dev_data:/var/lib/mysql

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"

volumes:
  mysql_dev_data:
```

## 📊 Dev 分支特色功能

### 🧪 完整測試框架
- **pytest** - 主要測試框架
- **coverage** - 測試覆蓋率分析
- **pytest-asyncio** - 異步測試支援
- **pytest-mock** - Mock 和 stub 工具
- **httpx** - HTTP 客戶端測試

### 🔍 代碼品質工具
```bash
# 格式化工具
black .                    # 代碼格式化
isort .                    # import 排序
autoflake --in-place --recursive --remove-all-unused-imports .

# 語法檢查
flake8 .                   # PEP 8 檢查
mypy bot/ shared/          # 類型檢查
bandit -r bot/ shared/     # 安全檢查
safety check              # 依賴漏洞檢查
```

### 📈 開發監控
- **效能分析工具** - cProfile, line_profiler
- **記憶體監控** - tracemalloc, memory_profiler  
- **API 監控** - 請求追蹤和效能分析
- **開發指標** - 測試覆蓋率、代碼品質分數

## 🔄 CI/CD 開發流程

### 🌟 智能變更檢測
```yaml
# .github/workflows/smart-change-detection.yml 特色
- name: 🧠 智能變更分析
  run: |
    # 分析變更範圍和影響
    python scripts/analyze_changes.py
    
    # 動態調整測試策略
    if [[ "$CHANGED_AREAS" == *"database"* ]]; then
      echo "DATABASE_TESTS=true" >> $GITHUB_ENV
    fi
    
    # 節省執行時間
    if [[ "$MINOR_CHANGES" == "true" ]]; then
      echo "SKIP_HEAVY_TESTS=true" >> $GITHUB_ENV
    fi
```

### 🛡️ 多層品質檢查
1. **Pre-commit hooks** - 提交前自動檢查
2. **Pull Request 檢查** - 代碼審查和自動測試
3. **持續整合** - 完整測試套件執行
4. **部署前驗證** - 生產就緒性檢查

### 📊 自動化報告生成
- **測試覆蓋率報告** - HTML 格式詳細報告
- **代碼品質報告** - SonarQube 風格分析
- **安全掃描報告** - 安全漏洞和風險評估
- **效能基準報告** - 效能回歸測試結果

## 🧩 模組開發指南

### 📦 模組結構標準
```python
# 標準模組結構
module_name/
├── __init__.py          # 模組初始化
├── models.py           # 資料模型
├── services.py         # 業務邏輯
├── exceptions.py       # 自訂異常
├── utils.py           # 工具函數
└── tests/             # 模組測試
    ├── __init__.py
    ├── test_services.py
    ├── test_models.py
    └── fixtures.py
```

### 🏗️ 開發模式最佳實踐
```python
# 依賴注入模式
from typing import Protocol

class TicketRepository(Protocol):
    async def create(self, ticket_data: dict) -> dict:
        ...
    
    async def get_by_id(self, ticket_id: int) -> dict:
        ...

class TicketService:
    def __init__(self, repository: TicketRepository):
        self._repository = repository
    
    async def create_ticket(self, data: dict) -> dict:
        # 業務邏輯驗證
        validated_data = self._validate_ticket_data(data)
        
        # 調用資料層
        return await self._repository.create(validated_data)
```

### 🧪 測試驅動開發
```python
# 先寫測試
import pytest
from unittest.mock import Mock

class TestTicketService:
    @pytest.fixture
    def mock_repository(self):
        return Mock(spec=TicketRepository)
    
    @pytest.fixture
    def ticket_service(self, mock_repository):
        return TicketService(mock_repository)
    
    async def test_create_ticket_success(self, ticket_service, mock_repository):
        # Given
        ticket_data = {"title": "Test", "description": "Test desc"}
        mock_repository.create.return_value = {"id": 1, **ticket_data}
        
        # When
        result = await ticket_service.create_ticket(ticket_data)
        
        # Then
        assert result["id"] == 1
        assert result["title"] == "Test"
        mock_repository.create.assert_called_once()

# 然後實現功能
class TicketService:
    async def create_ticket(self, data: dict) -> dict:
        if not data.get("title"):
            raise ValueError("Title is required")
        
        return await self._repository.create(data)
```

## 🔍 開發調試技巧

### 🐛 調試工具配置
```python
# rich 美化輸出
from rich import print
from rich.console import Console
from rich.traceback import install

# 安裝 rich traceback
install(show_locals=True)
console = Console()

# 調試輸出
console.print("[bold red]Debug Info[/bold red]")
print({"key": "value"})  # 自動美化 JSON

# icecream 變數檢查
from icecream import ic

ic.disable()  # 生產環境停用
ic(variable_name, another_var)
```

### 🔬 效能分析
```python
# 函數執行時間分析
import functools
import time

def timing_decorator(func):
    @functools.wraps(func)
    async def wrapper(*args, **kwargs):
        start = time.perf_counter()
        try:
            return await func(*args, **kwargs)
        finally:
            end = time.perf_counter()
            print(f"{func.__name__} 執行時間: {end - start:.4f}s")
    return wrapper

# 記憶體使用分析
import tracemalloc

def memory_usage(func):
    @functools.wraps(func)
    async def wrapper(*args, **kwargs):
        tracemalloc.start()
        try:
            result = await func(*args, **kwargs)
            current, peak = tracemalloc.get_traced_memory()
            print(f"記憶體使用: {current / 1024 / 1024:.1f} MB (峰值: {peak / 1024 / 1024:.1f} MB)")
            return result
        finally:
            tracemalloc.stop()
    return wrapper
```

## 🌐 API 開發指南

### 🔗 FastAPI 開發模式
```python
from fastapi import FastAPI, Depends, HTTPException
from pydantic import BaseModel
import asyncio

app = FastAPI(
    title="Potato Bot API",
    description="Development API with full debugging",
    version="dev",
    debug=True  # 開發模式
)

# 開發中間件
@app.middleware("http")
async def debug_middleware(request, call_next):
    start_time = time.time()
    response = await call_next(request)
    process_time = time.time() - start_time
    response.headers["X-Process-Time"] = str(process_time)
    return response

# 自動重載和熱更新
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,        # 開發模式自動重載
        log_level="debug",  # 詳細日誌
        access_log=True     # 訪問日誌
    )
```

### 📡 WebSocket 開發
```python
from fastapi import WebSocket, WebSocketDisconnect
import json

class ConnectionManager:
    def __init__(self):
        self.active_connections: list[WebSocket] = []
    
    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        print(f"[DEV] WebSocket 連接數: {len(self.active_connections)}")
    
    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)
        print(f"[DEV] WebSocket 連接數: {len(self.active_connections)}")

manager = ConnectionManager()

@app.websocket("/ws/{client_id}")
async def websocket_endpoint(websocket: WebSocket, client_id: str):
    await manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            message = json.loads(data)
            
            # 開發模式詳細日誌
            print(f"[DEV] 收到來自 {client_id} 的訊息: {message}")
            
            # 回響測試
            await websocket.send_text(json.dumps({
                "type": "echo",
                "original": message,
                "timestamp": time.time()
            }))
    except WebSocketDisconnect:
        manager.disconnect(websocket)
```

## 📚 開發文檔管理

### 📝 文檔自動生成
```python
# 使用 pydantic 自動生成 API 文檔
from pydantic import BaseModel, Field

class TicketResponse(BaseModel):
    """票券回應模型
    
    包含票券的完整資訊，用於 API 回應。
    """
    id: int = Field(..., description="票券唯一識別碼")
    title: str = Field(..., description="票券標題", example="無法登入系統")
    description: str = Field(..., description="詳細描述")
    status: str = Field(..., description="處理狀態", example="open")
    
    class Config:
        schema_extra = {
            "example": {
                "id": 1,
                "title": "無法登入系統",
                "description": "嘗試登入時出現錯誤訊息",
                "status": "open"
            }
        }

# FastAPI 自動生成 OpenAPI 規範
@app.get("/api/v1/tickets/{ticket_id}", response_model=TicketResponse)
async def get_ticket(ticket_id: int):
    """獲取特定票券資訊
    
    根據票券 ID 獲取詳細資訊，包括狀態、優先級等。
    
    Args:
        ticket_id: 票券的唯一識別碼
        
    Returns:
        TicketResponse: 票券的完整資訊
        
    Raises:
        HTTPException: 當票券不存在時回傳 404
    """
    pass
```

### 📊 開發統計和指標

#### 📈 代碼品質指標
- **測試覆蓋率**: 目標 >85%
- **代碼重複率**: 目標 <5%
- **圈複雜度**: 目標 <10
- **技術債務**: 持續監控和清理

#### 🎯 開發效率指標
- **構建時間**: 目標 <5 分鐘
- **測試執行時間**: 目標 <2 分鐘
- **熱重載時間**: 目標 <3 秒
- **API 回應時間**: 目標 <100ms

## 🔧 開發故障排除

### 🐛 常見開發問題
1. **依賴衝突** - 使用虛擬環境隔離
2. **資料庫連接** - 檢查連接字串和權限
3. **異步程式** - 注意 await 的使用
4. **測試失敗** - 檢查測試資料和 mock 設定

### 🛠️ 調試命令
```bash
# 開發模式啟動
python -m uvicorn bot.api.app:app --reload --log-level debug

# 測試執行
pytest -v --tb=short          # 簡潔錯誤訊息
pytest -s                    # 顯示 print 輸出
pytest --pdb                 # 錯誤時進入調試器
pytest --cov=bot --cov-report=html  # 覆蓋率報告

# 代碼品質檢查
black --check .               # 檢查格式
isort --check-only .          # 檢查 import 排序
flake8 .                      # 語法檢查
mypy bot/ shared/             # 類型檢查
```

## 🤝 團隊協作流程

### 🔄 開發工作流程
1. **創建功能分支** - `git checkout -b feature/new-feature`
2. **開發和測試** - TDD 測試驅動開發
3. **代碼審查** - Pull Request 和 Code Review
4. **CI/CD 驗證** - 自動化測試和品質檢查
5. **合併到 dev** - 經過審查後合併

### 📋 Pull Request 檢查清單
- [ ] 所有測試通過
- [ ] 代碼覆蓋率維持在 85% 以上
- [ ] 通過所有品質檢查 (black, isort, flake8, mypy)
- [ ] 無安全漏洞 (bandit, safety)
- [ ] 文檔更新完整
- [ ] 功能正常運作

---

**🔔 開發提醒：**
- dev 分支包含完整的開發工具和測試框架
- 所有變更都會經過嚴格的 CI/CD 流程驗證
- 優先使用測試驅動開發 (TDD) 方法
- 保持代碼品質和文檔更新

**📅 最後更新：** 2025-08-31  
**🏷️ 分支版本：** dev-v2.1.0  
**📊 開發成熟度：** Production Ready