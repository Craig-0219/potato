# bot/api/models.py
"""
API 數據模型定義
使用 Pydantic 進行數據驗證和序列化
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, field_validator


# 基礎響應模型
class BaseResponse(BaseModel):
    """基礎 API 響應模型"""

    success: bool = True
    message: str = "操作成功"
    timestamp: datetime = Field(default_factory=datetime.now)


class ErrorResponse(BaseModel):
    """錯誤響應模型"""

    success: bool = False
    error: Dict[str, Any]
    timestamp: datetime = Field(default_factory=datetime.now)


class PaginationInfo(BaseModel):
    """分頁信息模型"""

    page: int = Field(ge=1, description="當前頁碼")
    page_size: int = Field(ge=1, le=100, description="每頁記錄數")
    total: int = Field(ge=0, description="總記錄數")
    total_pages: int = Field(ge=0, description="總頁數")
    has_next: bool = Field(description="是否有下一頁")
    has_prev: bool = Field(description="是否有上一頁")


class PaginatedResponse(BaseModel):
    """分頁響應模型"""

    data: List[Any]
    pagination: PaginationInfo
    success: bool = True
    message: str = "查詢成功"
    timestamp: datetime = Field(default_factory=datetime.now)


# 票券相關模型
class TicketStatus(str, Enum):
    OPEN = "open"
    CLOSED = "closed"
    ARCHIVED = "archived"


class TicketPriority(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class TicketBase(BaseModel):
    """票券基礎模型"""

    type: str = Field(..., description="票券類型")
    priority: TicketPriority = Field(
        default=TicketPriority.MEDIUM, description="優先級"
    )
    title: Optional[str] = Field(None, description="票券標題")
    description: Optional[str] = Field(None, description="票券描述")


class TicketCreate(TicketBase):
    """創建票券請求模型"""

    guild_id: int = Field(..., description="伺服器 ID")
    discord_id: str = Field(..., description="用戶 Discord ID")
    username: str = Field(..., description="用戶名稱")


class TicketUpdate(BaseModel):
    """更新票券請求模型"""

    status: Optional[TicketStatus] = Field(None, description="票券狀態")
    priority: Optional[TicketPriority] = Field(None, description="優先級")
    assigned_to: Optional[int] = Field(None, description="指派給用戶 ID")
    tags: Optional[List[str]] = Field(None, description="標籤列表")


class TicketResponse(BaseModel):
    """票券響應模型"""

    id: int = Field(..., description="票券 ID")
    type: str = Field(..., description="票券類型")
    status: TicketStatus = Field(..., description="票券狀態")
    priority: TicketPriority = Field(..., description="優先級")
    title: Optional[str] = Field(None, description="票券標題")
    description: Optional[str] = Field(None, description="票券描述")
    guild_id: int = Field(..., description="伺服器 ID")
    discord_id: str = Field(..., description="創建者 Discord ID")
    username: str = Field(..., description="創建者用戶名")
    assigned_to: Optional[int] = Field(None, description="指派給用戶 ID")
    assigned_to_username: Optional[str] = Field(
        None, description="指派給用戶名"
    )
    channel_id: Optional[int] = Field(None, description="頻道 ID")
    created_at: datetime = Field(..., description="創建時間")
    updated_at: Optional[datetime] = Field(None, description="更新時間")
    closed_at: Optional[datetime] = Field(None, description="關閉時間")
    rating: Optional[int] = Field(None, ge=1, le=5, description="評分")
    feedback: Optional[str] = Field(None, description="回饋")
    tags: List[str] = Field(default_factory=list, description="標籤列表")


class TicketSearchQuery(BaseModel):
    """票券搜尋查詢模型"""

    guild_id: Optional[int] = Field(None, description="伺服器 ID")
    status: Optional[TicketStatus] = Field(None, description="狀態篩選")
    priority: Optional[TicketPriority] = Field(None, description="優先級篩選")
    discord_id: Optional[str] = Field(None, description="用戶 Discord ID 篩選")
    assigned_to: Optional[int] = Field(None, description="指派給用戶篩選")
    tag: Optional[str] = Field(None, description="標籤篩選")
    created_after: Optional[datetime] = Field(None, description="創建時間起始")
    created_before: Optional[datetime] = Field(
        None, description="創建時間結束"
    )
    keyword: Optional[str] = Field(None, description="關鍵字搜尋")


# 分析統計相關模型
class TicketStatistics(BaseModel):
    """票券統計模型"""

    total_tickets: int = Field(..., description="總票券數")
    open_tickets: int = Field(..., description="開啟中票券數")
    closed_tickets: int = Field(..., description="已關閉票券數")
    high_priority: int = Field(..., description="高優先級票券數")
    medium_priority: int = Field(..., description="中優先級票券數")
    low_priority: int = Field(..., description="低優先級票券數")
    avg_resolution_time: Optional[float] = Field(
        None, description="平均解決時間（小時）"
    )
    avg_rating: Optional[float] = Field(None, description="平均評分")
    period_start: datetime = Field(..., description="統計期間開始")
    period_end: datetime = Field(..., description="統計期間結束")


class StaffPerformance(BaseModel):
    """客服績效模型"""

    staff_id: int = Field(..., description="客服 ID")
    username: str = Field(..., description="客服用戶名")
    total_assigned: int = Field(..., description="總指派票券數")
    total_completed: int = Field(..., description="已完成票券數")
    avg_completion_time: Optional[float] = Field(
        None, description="平均完成時間（小時）"
    )
    avg_rating: Optional[float] = Field(None, description="平均評分")
    current_workload: int = Field(..., description="當前工作量")
    efficiency_score: Optional[float] = Field(None, description="效率評分")


# 自動化相關模型
class AutomationRuleStatus(str, Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    PAUSED = "paused"


class AutomationTriggerType(str, Enum):
    MESSAGE_RECEIVED = "message_received"
    TICKET_CREATED = "ticket_created"
    TICKET_UPDATED = "ticket_updated"
    MEMBER_JOINED = "member_joined"
    REACTION_ADDED = "reaction_added"
    SCHEDULED = "scheduled"


class AutomationActionType(str, Enum):
    SEND_MESSAGE = "send_message"
    ASSIGN_ROLE = "assign_role"
    CREATE_TICKET = "create_ticket"
    CLOSE_TICKET = "close_ticket"
    SEND_EMAIL = "send_email"
    WEBHOOK_CALL = "webhook_call"


class AutomationRule(BaseModel):
    """自動化規則模型"""

    id: Optional[str] = Field(None, description="規則 ID")
    name: str = Field(..., description="規則名稱")
    description: Optional[str] = Field(None, description="規則描述")
    guild_id: int = Field(..., description="伺服器 ID")
    status: AutomationRuleStatus = Field(
        default=AutomationRuleStatus.ACTIVE, description="規則狀態"
    )
    trigger_type: AutomationTriggerType = Field(..., description="觸發類型")
    trigger_conditions: Dict[str, Any] = Field(..., description="觸發條件")
    actions: List[Dict[str, Any]] = Field(..., description="執行動作")
    priority: int = Field(default=1, ge=1, le=10, description="執行優先級")
    cooldown_seconds: int = Field(default=0, ge=0, description="冷卻時間")
    created_by: int = Field(..., description="創建者 ID")
    created_at: Optional[datetime] = Field(None, description="創建時間")
    updated_at: Optional[datetime] = Field(None, description="更新時間")
    execution_count: int = Field(default=0, description="執行次數")
    last_executed: Optional[datetime] = Field(None, description="最後執行時間")


class AutomationExecution(BaseModel):
    """自動化執行記錄模型"""

    id: str = Field(..., description="執行記錄 ID")
    rule_id: str = Field(..., description="規則 ID")
    rule_name: str = Field(..., description="規則名稱")
    executed_at: datetime = Field(..., description="執行時間")
    success: bool = Field(..., description="執行是否成功")
    execution_time_ms: int = Field(..., description="執行時間（毫秒）")
    trigger_data: Dict[str, Any] = Field(..., description="觸發數據")
    action_results: List[Dict[str, Any]] = Field(
        ..., description="動作執行結果"
    )
    error_message: Optional[str] = Field(None, description="錯誤信息")


# API 金鑰管理模型
class APIKeyCreate(BaseModel):
    """創建 API 金鑰請求模型"""

    name: str = Field(..., description="金鑰名稱")
    permission_level: str = Field(..., description="權限等級")
    guild_id: Optional[int] = Field(None, description="限制伺服器 ID")
    expires_days: Optional[int] = Field(
        None, ge=1, le=365, description="過期天數"
    )


class APIKeyResponse(BaseModel):
    """API 金鑰響應模型"""

    key_id: str = Field(..., description="金鑰 ID")
    name: str = Field(..., description="金鑰名稱")
    permission_level: str = Field(..., description="權限等級")
    guild_id: Optional[int] = Field(None, description="限制伺服器 ID")
    created_at: datetime = Field(..., description="創建時間")
    last_used_at: Optional[datetime] = Field(None, description="最後使用時間")
    expires_at: Optional[datetime] = Field(None, description="過期時間")
    is_active: bool = Field(..., description="是否啟用")
    usage_count: int = Field(..., description="使用次數")


# 系統監控模型
class SystemHealth(BaseModel):
    """系統健康狀態模型"""

    status: str = Field(..., description="整體狀態")
    timestamp: datetime = Field(..., description="檢查時間")
    uptime: float = Field(..., description="運行時間（秒）")
    version: str = Field(..., description="系統版本")
    components: Dict[str, str] = Field(..., description="組件狀態")
    metrics: Dict[str, float] = Field(..., description="性能指標")


class SystemMetrics(BaseModel):
    """系統性能指標模型"""

    cpu_usage: float = Field(..., description="CPU 使用率")
    memory_usage: float = Field(..., description="記憶體使用率")
    disk_usage: float = Field(..., description="磁碟使用率")
    database_connections: int = Field(..., description="資料庫連接數")
    active_tickets: int = Field(..., description="活躍票券數")
    api_requests_per_minute: int = Field(..., description="每分鐘 API 請求數")
    bot_latency: float = Field(..., description="機器人延遲（毫秒）")
    timestamp: datetime = Field(..., description="指標收集時間")


# 通用查詢參數模型
class CommonQueryParams(BaseModel):
    """通用查詢參數"""

    page: int = Field(default=1, ge=1, description="頁碼")
    page_size: int = Field(default=10, ge=1, le=100, description="每頁記錄數")
    sort_by: Optional[str] = Field(None, description="排序欄位")
    sort_order: Optional[str] = Field(
        default="desc", pattern="^(asc|desc)$", description="排序方向"
    )

    @field_validator("sort_order")
    @classmethod
    def validate_sort_order(cls, v):
        if v not in ["asc", "desc"]:
            raise ValueError("sort_order must be either asc or desc")
        return v
