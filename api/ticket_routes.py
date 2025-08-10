# api/ticket_routes.py
"""
票券管理 API 路由
提供完整的票券 CRUD 操作
"""

from datetime import datetime, timezone
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, HTTPException, Depends, Query, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, validator

from api.auth_routes import get_current_user, get_staff_user
from bot.services.auth_manager import AuthUser
from bot.db.ticket_dao import TicketDAO
from bot.services.ticket_manager import TicketManager
from shared.logger import logger

# 請求和回應模型
class TicketCreateRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=200, description="票券標題")
    description: str = Field(..., min_length=1, description="票券描述")
    ticket_type: str = Field(default="general", description="票券類型")
    priority: str = Field(default="medium", description="優先級")
    
    @validator('priority')
    def validate_priority(cls, v):
        if v not in ['low', 'medium', 'high', 'urgent']:
            raise ValueError('優先級必須是: low, medium, high, urgent')
        return v

class TicketUpdateRequest(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = Field(None, min_length=1)
    status: Optional[str] = Field(None)
    priority: Optional[str] = Field(None)
    assigned_to: Optional[int] = Field(None)
    tags: Optional[List[str]] = Field(None)
    
    @validator('status')
    def validate_status(cls, v):
        if v and v not in ['open', 'in_progress', 'pending', 'resolved', 'closed']:
            raise ValueError('狀態必須是: open, in_progress, pending, resolved, closed')
        return v
    
    @validator('priority')
    def validate_priority(cls, v):
        if v and v not in ['low', 'medium', 'high', 'urgent']:
            raise ValueError('優先級必須是: low, medium, high, urgent')
        return v

class TicketResponse(BaseModel):
    id: int
    title: str
    description: str
    status: str
    priority: str
    ticket_type: str
    discord_id: str
    username: str
    guild_id: int
    channel_id: Optional[int] = None
    assigned_to: Optional[int] = None
    assigned_by: Optional[int] = None
    rating: Optional[int] = None
    feedback: Optional[str] = None
    created_at: datetime
    updated_at: Optional[datetime] = None
    closed_at: Optional[datetime] = None
    first_response_at: Optional[datetime] = None
    tags: Optional[List[str]] = None

class TicketListResponse(BaseModel):
    tickets: List[TicketResponse]
    total: int
    page: int
    per_page: int
    has_next: bool
    has_prev: bool

class TicketStatsResponse(BaseModel):
    total_tickets: int
    open_tickets: int
    closed_tickets: int
    in_progress_tickets: int
    avg_resolution_time: Optional[float] = None
    avg_rating: Optional[float] = None

router = APIRouter(prefix="/tickets", tags=["票券管理"])

# 初始化 DAO 和服務
ticket_dao = TicketDAO()
ticket_manager = TicketManager(ticket_dao)

# ===== 票券 CRUD 操作 =====

@router.get("/", response_model=TicketListResponse, summary="獲取票券列表")
async def get_tickets(
    page: int = Query(1, ge=1, description="頁碼"),
    per_page: int = Query(20, ge=1, le=100, description="每頁數量"),
    status: Optional[str] = Query(None, description="狀態篩選"),
    priority: Optional[str] = Query(None, description="優先級篩選"),
    assigned_to: Optional[int] = Query(None, description="指派人篩選"),
    search: Optional[str] = Query(None, description="搜尋關鍵字"),
    current_user: AuthUser = Depends(get_staff_user)
):
    """
    獲取票券列表，支援分頁和篩選
    
    - 客服可以看到所有票券
    - 一般用戶只能看到自己的票券
    """
    try:
        # 構建篩選條件
        filters = {}
        if status:
            filters['status'] = status
        if priority:
            filters['priority'] = priority
        if assigned_to:
            filters['assigned_to'] = assigned_to
        if search:
            filters['search'] = search
        
        # 如果不是客服，只能看自己的票券
        if not current_user.is_staff:
            filters['discord_id'] = current_user.discord_id
        
        # 計算偏移量
        offset = (page - 1) * per_page
        
        # 獲取票券列表
        tickets_data = await ticket_dao.get_tickets_with_filters(
            filters=filters,
            limit=per_page,
            offset=offset,
            guild_id=current_user.guild_id
        )
        
        # 獲取總數
        total = await ticket_dao.count_tickets_with_filters(
            filters=filters,
            guild_id=current_user.guild_id
        )
        
        # 轉換為回應模型
        tickets = []
        for ticket in tickets_data:
            ticket_response = TicketResponse(
                id=ticket['id'],
                title=ticket.get('title', f"票券 #{ticket['id']:04d}"),
                description=ticket.get('description', ticket.get('type', 'general')),
                status=ticket['status'],
                priority=ticket.get('priority', 'medium'),
                ticket_type=ticket.get('type', 'general'),
                discord_id=ticket['discord_id'],
                username=ticket['username'],
                guild_id=ticket['guild_id'],
                channel_id=ticket.get('channel_id'),
                assigned_to=ticket.get('assigned_to'),
                assigned_by=ticket.get('assigned_by'),
                rating=ticket.get('rating'),
                feedback=ticket.get('feedback'),
                created_at=ticket['created_at'],
                updated_at=ticket.get('updated_at'),
                closed_at=ticket.get('closed_at'),
                first_response_at=ticket.get('first_response_at'),
                tags=[]  # 暫時為空，後續實現標籤功能
            )
            tickets.append(ticket_response)
        
        return TicketListResponse(
            tickets=tickets,
            total=total,
            page=page,
            per_page=per_page,
            has_next=offset + per_page < total,
            has_prev=page > 1
        )
        
    except Exception as e:
        logger.error(f"獲取票券列表失敗: {e}")
        raise HTTPException(status_code=500, detail=f"獲取票券列表失敗: {str(e)}")

@router.get("/{ticket_id}", response_model=TicketResponse, summary="獲取票券詳情")
async def get_ticket(
    ticket_id: int,
    current_user: AuthUser = Depends(get_current_user)
):
    """
    獲取指定票券的詳細資訊
    """
    try:
        ticket = await ticket_dao.get_ticket_by_id(ticket_id)
        
        if not ticket:
            raise HTTPException(status_code=404, detail="票券不存在")
        
        # 權限檢查：只有客服或票券創建者可以查看
        if not current_user.is_staff and ticket['discord_id'] != current_user.discord_id:
            raise HTTPException(status_code=403, detail="無權限查看此票券")
        
        return TicketResponse(
            id=ticket['id'],
            title=ticket.get('title', f"票券 #{ticket['id']:04d}"),
            description=ticket.get('description', ticket.get('type', 'general')),
            status=ticket['status'],
            priority=ticket.get('priority', 'medium'),
            ticket_type=ticket.get('type', 'general'),
            discord_id=ticket['discord_id'],
            username=ticket['username'],
            guild_id=ticket['guild_id'],
            channel_id=ticket.get('channel_id'),
            assigned_to=ticket.get('assigned_to'),
            assigned_by=ticket.get('assigned_by'),
            rating=ticket.get('rating'),
            feedback=ticket.get('feedback'),
            created_at=ticket['created_at'],
            updated_at=ticket.get('updated_at'),
            closed_at=ticket.get('closed_at'),
            first_response_at=ticket.get('first_response_at'),
            tags=[]  # 暫時為空
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"獲取票券詳情失敗: {e}")
        raise HTTPException(status_code=500, detail=f"獲取票券詳情失敗: {str(e)}")

@router.post("/", response_model=TicketResponse, summary="創建新票券")
async def create_ticket(
    request: TicketCreateRequest,
    current_user: AuthUser = Depends(get_current_user)
):
    """
    創建新票券
    
    注意：這個 API 創建的是純數據記錄，不會創建 Discord 頻道
    如需創建 Discord 頻道，請使用 Discord 機器人指令
    """
    try:
        # 創建票券記錄
        ticket_id = await ticket_dao.create_ticket(
            discord_id=current_user.discord_id,
            username=current_user.username,
            ticket_type=request.ticket_type,
            channel_id=None,  # Web 創建的票券沒有頻道
            guild_id=current_user.guild_id,
            priority=request.priority,
            title=request.title,
            description=request.description
        )
        
        if not ticket_id:
            raise HTTPException(status_code=500, detail="創建票券失敗")
        
        # 獲取創建的票券
        ticket = await ticket_dao.get_ticket_by_id(ticket_id)
        
        return TicketResponse(
            id=ticket['id'],
            title=ticket.get('title', request.title),
            description=ticket.get('description', request.description),
            status=ticket['status'],
            priority=ticket.get('priority', request.priority),
            ticket_type=ticket.get('type', request.ticket_type),
            discord_id=ticket['discord_id'],
            username=ticket['username'],
            guild_id=ticket['guild_id'],
            channel_id=ticket.get('channel_id'),
            assigned_to=ticket.get('assigned_to'),
            assigned_by=ticket.get('assigned_by'),
            rating=ticket.get('rating'),
            feedback=ticket.get('feedback'),
            created_at=ticket['created_at'],
            updated_at=ticket.get('updated_at'),
            closed_at=ticket.get('closed_at'),
            first_response_at=ticket.get('first_response_at'),
            tags=[]
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"創建票券失敗: {e}")
        raise HTTPException(status_code=500, detail=f"創建票券失敗: {str(e)}")

@router.put("/{ticket_id}", response_model=TicketResponse, summary="更新票券")
async def update_ticket(
    ticket_id: int,
    request: TicketUpdateRequest,
    current_user: AuthUser = Depends(get_staff_user)
):
    """
    更新票券資訊
    
    需要客服權限
    """
    try:
        ticket = await ticket_dao.get_ticket_by_id(ticket_id)
        
        if not ticket:
            raise HTTPException(status_code=404, detail="票券不存在")
        
        # 準備更新資料
        update_data = {}
        if request.title is not None:
            update_data['title'] = request.title
        if request.description is not None:
            update_data['description'] = request.description
        if request.status is not None:
            update_data['status'] = request.status
            if request.status == 'closed':
                update_data['closed_at'] = datetime.now(timezone.utc)
        if request.priority is not None:
            update_data['priority'] = request.priority
        if request.assigned_to is not None:
            update_data['assigned_to'] = request.assigned_to
            update_data['assigned_by'] = current_user.user_id
        
        # 執行更新
        success = await ticket_dao.update_ticket(ticket_id, update_data)
        
        if not success:
            raise HTTPException(status_code=500, detail="更新票券失敗")
        
        # 獲取更新後的票券
        updated_ticket = await ticket_dao.get_ticket_by_id(ticket_id)
        
        return TicketResponse(
            id=updated_ticket['id'],
            title=updated_ticket.get('title', f"票券 #{updated_ticket['id']:04d}"),
            description=updated_ticket.get('description', ''),
            status=updated_ticket['status'],
            priority=updated_ticket.get('priority', 'medium'),
            ticket_type=updated_ticket.get('type', 'general'),
            discord_id=updated_ticket['discord_id'],
            username=updated_ticket['username'],
            guild_id=updated_ticket['guild_id'],
            channel_id=updated_ticket.get('channel_id'),
            assigned_to=updated_ticket.get('assigned_to'),
            assigned_by=updated_ticket.get('assigned_by'),
            rating=updated_ticket.get('rating'),
            feedback=updated_ticket.get('feedback'),
            created_at=updated_ticket['created_at'],
            updated_at=updated_ticket.get('updated_at'),
            closed_at=updated_ticket.get('closed_at'),
            first_response_at=updated_ticket.get('first_response_at'),
            tags=[]
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"更新票券失敗: {e}")
        raise HTTPException(status_code=500, detail=f"更新票券失敗: {str(e)}")

@router.delete("/{ticket_id}", summary="刪除票券")
async def delete_ticket(
    ticket_id: int,
    current_user: AuthUser = Depends(get_staff_user)
):
    """
    刪除票券
    
    需要客服權限，謹慎使用
    """
    try:
        ticket = await ticket_dao.get_ticket_by_id(ticket_id)
        
        if not ticket:
            raise HTTPException(status_code=404, detail="票券不存在")
        
        # 執行軟刪除或標記為已刪除
        success = await ticket_dao.update_ticket(ticket_id, {
            'status': 'deleted',
            'updated_at': datetime.now(timezone.utc)
        })
        
        if not success:
            raise HTTPException(status_code=500, detail="刪除票券失敗")
        
        return {"message": f"票券 #{ticket_id:04d} 已成功刪除"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"刪除票券失敗: {e}")
        raise HTTPException(status_code=500, detail=f"刪除票券失敗: {str(e)}")

# ===== 票券操作 =====

@router.post("/{ticket_id}/assign", summary="指派票券")
async def assign_ticket(
    ticket_id: int,
    assigned_to: int,
    current_user: AuthUser = Depends(get_staff_user)
):
    """指派票券給客服人員"""
    try:
        success = await ticket_manager.assign_ticket(
            ticket_id=ticket_id,
            assigned_to=assigned_to,
            assigned_by=current_user.user_id
        )
        
        if not success:
            raise HTTPException(status_code=500, detail="指派票券失敗")
        
        return {"message": f"票券 #{ticket_id:04d} 已指派成功"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"指派票券失敗: {e}")
        raise HTTPException(status_code=500, detail=f"指派票券失敗: {str(e)}")

@router.post("/{ticket_id}/close", summary="關閉票券")
async def close_ticket(
    ticket_id: int,
    reason: Optional[str] = None,
    current_user: AuthUser = Depends(get_staff_user)
):
    """關閉票券"""
    try:
        success = await ticket_manager.close_ticket(
            ticket_id=ticket_id,
            closed_by=current_user.user_id,
            reason=reason
        )
        
        if not success:
            raise HTTPException(status_code=500, detail="關閉票券失敗")
        
        return {"message": f"票券 #{ticket_id:04d} 已關閉"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"關閉票券失敗: {e}")
        raise HTTPException(status_code=500, detail=f"關閉票券失敗: {str(e)}")

class RatingRequest(BaseModel):
    rating: int = Field(..., ge=1, le=5, description="評分 1-5 星")
    feedback: Optional[str] = Field(None, description="評價反饋")

@router.post("/{ticket_id}/rate", summary="評分票券")
async def rate_ticket(
    ticket_id: int,
    request: RatingRequest,
    current_user: AuthUser = Depends(get_current_user)
):
    """為票券評分"""
    try:
        ticket = await ticket_dao.get_ticket_by_id(ticket_id)
        
        if not ticket:
            raise HTTPException(status_code=404, detail="票券不存在")
        
        # 只有票券創建者可以評分
        if ticket['discord_id'] != current_user.discord_id:
            raise HTTPException(status_code=403, detail="只有票券創建者可以評分")
        
        success = await ticket_manager.save_rating(
            ticket_id=ticket_id,
            rating=request.rating,
            feedback=request.feedback
        )
        
        if not success:
            raise HTTPException(status_code=500, detail="評分失敗")
        
        return {"message": f"票券 #{ticket_id:04d} 評分成功"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"評分票券失敗: {e}")
        raise HTTPException(status_code=500, detail=f"評分票券失敗: {str(e)}")

# ===== 統計資訊 =====

@router.get("/stats/overview", response_model=TicketStatsResponse, summary="票券統計概覽")
async def get_ticket_stats(
    current_user: AuthUser = Depends(get_staff_user)
):
    """獲取票券統計資訊"""
    try:
        from bot.services.statistics_manager import StatisticsManager
        from bot.db.database_manager import DatabaseManager
        
        stats_manager = StatisticsManager(DatabaseManager())
        stats = await stats_manager.get_ticket_statistics(current_user.guild_id)
        
        return TicketStatsResponse(
            total_tickets=stats.get('total_tickets', 0),
            open_tickets=stats.get('open_tickets', 0),
            closed_tickets=stats.get('closed_tickets', 0),
            in_progress_tickets=stats.get('in_progress_tickets', 0),
            avg_resolution_time=stats.get('avg_resolution_time'),
            avg_rating=stats.get('avg_rating')
        )
        
    except Exception as e:
        logger.error(f"獲取統計資訊失敗: {e}")
        raise HTTPException(status_code=500, detail=f"獲取統計資訊失敗: {str(e)}")

@router.get("/stats/daily", summary="每日統計")
async def get_daily_stats(
    days: int = Query(30, ge=1, le=90, description="統計天數"),
    current_user: AuthUser = Depends(get_staff_user)
):
    """獲取每日票券統計"""
    try:
        # 這裡可以實現每日統計邏輯
        # 暫時返回模擬資料
        return {
            "period": f"最近 {days} 天",
            "data": [
                {"date": "2025-08-10", "created": 5, "closed": 3, "pending": 2},
                {"date": "2025-08-09", "created": 3, "closed": 4, "pending": 1},
                # ... 更多數據
            ]
        }
        
    except Exception as e:
        logger.error(f"獲取每日統計失敗: {e}")
        raise HTTPException(status_code=500, detail=f"獲取每日統計失敗: {str(e)}")

# ===== 輔助函數 =====

def handle_value_error(exc: ValueError):
    """處理值錯誤"""
    return JSONResponse(
        status_code=400,
        content={"error": str(exc)}
    )