# bot/api/routes/tickets.py
"""
票券管理 API 端點
提供票券的 CRUD 操作和查詢功能
"""

from fastapi import APIRouter, Depends, HTTPException, Query, Request
try:
    from slowapi import Limiter, _rate_limit_exceeded_handler
    from slowapi.util import get_remote_address
    HAS_SLOWAPI = True
except ImportError:
    HAS_SLOWAPI = False
from typing import Optional, List
from datetime import datetime

from ..auth import APIUser, require_read_permission, require_write_permission
from ..models import (
    TicketResponse, TicketCreate, TicketUpdate, TicketSearchQuery,
    PaginatedResponse, BaseResponse, TicketStatistics, CommonQueryParams
)
from bot.db.ticket_dao import TicketDAO
from bot.db.tag_dao import TagDAO
from bot.services.ticket_manager import TicketManager
from shared.logger import logger

router = APIRouter()
if HAS_SLOWAPI:
    limiter = Limiter(key_func=get_remote_address)
else:
    limiter = None

# 初始化服務
def get_ticket_dao():
    """獲取票券 DAO 實例"""
    return TicketDAO()

def get_tag_dao():
    """獲取標籤 DAO 實例"""
    return TagDAO()

def get_ticket_manager():
    """獲取票券管理器實例"""
    ticket_dao = get_ticket_dao()
    return TicketManager(ticket_dao)

@router.get("/", response_model=PaginatedResponse, summary="獲取票券列表")
async def get_tickets(
    request: Request,
    guild_id: Optional[int] = Query(None, description="伺服器 ID 篩選"),
    status: Optional[str] = Query(None, description="狀態篩選"),
    priority: Optional[str] = Query(None, description="優先級篩選"),
    discord_id: Optional[str] = Query(None, description="用戶 Discord ID 篩選"),
    assigned_to: Optional[int] = Query(None, description="指派給用戶篩選"),
    tag: Optional[str] = Query(None, description="標籤篩選"),
    created_after: Optional[datetime] = Query(None, description="創建時間起始"),
    created_before: Optional[datetime] = Query(None, description="創建時間結束"),
    keyword: Optional[str] = Query(None, description="關鍵字搜尋"),
    page: int = Query(1, ge=1, description="頁碼"),
    page_size: int = Query(10, ge=1, le=100, description="每頁記錄數"),
    sort_by: Optional[str] = Query("created_at", description="排序欄位"),
    sort_order: str = Query("desc", pattern="^(asc|desc)$", description="排序方向"),
    user: APIUser = Depends(require_read_permission)
):
    """
    獲取票券列表
    
    支援多種篩選條件和分頁查詢
    """
    try:
        ticket_dao = get_ticket_dao()
        
        # 構建查詢參數
        query_params = {
            'page': page,
            'page_size': page_size,
            'sort_by': sort_by,
            'sort_order': sort_order
        }
        
        # 添加篩選條件
        if guild_id:
            query_params['guild_id'] = guild_id
        if status:
            query_params['status'] = status
        if priority:
            query_params['priority'] = priority
        if discord_id:
            query_params['discord_id'] = discord_id
        if assigned_to:
            query_params['assigned_to'] = assigned_to
        if created_after:
            query_params['created_after'] = created_after
        if created_before:
            query_params['created_before'] = created_before
        if keyword:
            query_params['keyword'] = keyword
        
        # 執行查詢
        tickets, total = await ticket_dao.get_tickets(**query_params)
        
        # 處理標籤篩選（如果需要）
        if tag:
            tag_dao = get_tag_dao()
            # 這裡需要實現標籤篩選邏輯
            # filtered_tickets = await filter_tickets_by_tag(tickets, tag, tag_dao)
            # tickets = filtered_tickets
        
        # 計算分頁信息
        total_pages = (total + page_size - 1) // page_size
        has_next = page < total_pages
        has_prev = page > 1
        
        # 構建響應
        pagination_info = {
            "page": page,
            "page_size": page_size,
            "total": total,
            "total_pages": total_pages,
            "has_next": has_next,
            "has_prev": has_prev
        }
        
        return {
            "data": tickets,
            "pagination": pagination_info,
            "success": True,
            "message": f"成功獲取 {len(tickets)} 張票券",
            "timestamp": datetime.now()
        }
        
    except Exception as e:
        logger.error(f"獲取票券列表錯誤: {e}")
        raise HTTPException(
            status_code=500,
            detail="獲取票券列表失敗"
        )

@router.get("/{ticket_id}", response_model=TicketResponse, summary="獲取票券詳情")
#@limiter.limit("60/minute")
async def get_ticket(
    ticket_id: int,
    user: APIUser = Depends(require_read_permission)
):
    """獲取特定票券的詳細信息"""
    try:
        ticket_dao = get_ticket_dao()
        
        # 獲取票券基本信息
        ticket = await ticket_dao.get_ticket(ticket_id)
        if not ticket:
            raise HTTPException(
                status_code=404,
                detail=f"票券 #{ticket_id} 不存在"
            )
        
        # 獲取票券標籤
        tag_dao = get_tag_dao()
        ticket_tags = await tag_dao.get_ticket_tags(ticket_id)
        ticket['tags'] = [tag['name'] for tag in ticket_tags]
        
        return ticket
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"獲取票券詳情錯誤: {e}")
        raise HTTPException(
            status_code=500,
            detail="獲取票券詳情失敗"
        )

@router.post("/", response_model=BaseResponse, summary="創建新票券", status_code=201)
#@limiter.limit("10/minute")
async def create_ticket(
    ticket_data: TicketCreate,
    user: APIUser = Depends(require_write_permission)
):
    """創建新的票券"""
    try:
        ticket_manager = get_ticket_manager()
        
        # 創建票券
        success, message, ticket_id = await ticket_manager.create_ticket(
            user=None,  # 這裡需要適配，因為原方法需要 Discord Member 對象
            ticket_type=ticket_data.type,
            priority=ticket_data.priority
        )
        
        if not success:
            raise HTTPException(
                status_code=400,
                detail=message
            )
        
        return {
            "success": True,
            "message": f"票券 #{ticket_id:04d} 創建成功",
            "data": {"ticket_id": ticket_id}
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"創建票券錯誤: {e}")
        raise HTTPException(
            status_code=500,
            detail="創建票券失敗"
        )

@router.put("/{ticket_id}", response_model=BaseResponse, summary="更新票券")
#@limiter.limit("20/minute")
async def update_ticket(
    ticket_id: int,
    ticket_data: TicketUpdate,
    user: APIUser = Depends(require_write_permission)
):
    """更新票券信息"""
    try:
        ticket_dao = get_ticket_dao()
        
        # 檢查票券是否存在
        existing_ticket = await ticket_dao.get_ticket(ticket_id)
        if not existing_ticket:
            raise HTTPException(
                status_code=404,
                detail=f"票券 #{ticket_id} 不存在"
            )
        
        # 構建更新數據
        update_data = {}
        if ticket_data.status is not None:
            update_data['status'] = ticket_data.status
        if ticket_data.priority is not None:
            update_data['priority'] = ticket_data.priority
        if ticket_data.assigned_to is not None:
            update_data['assigned_to'] = ticket_data.assigned_to
        
        # 執行更新
        if update_data:
            success = await ticket_dao.update_ticket(ticket_id, **update_data)
            if not success:
                raise HTTPException(
                    status_code=500,
                    detail="更新票券失敗"
                )
        
        # 處理標籤更新
        if ticket_data.tags is not None:
            tag_dao = get_tag_dao()
            # 這裡需要實現標籤更新邏輯
            # await update_ticket_tags(ticket_id, ticket_data.tags, tag_dao)
        
        return {
            "success": True,
            "message": f"票券 #{ticket_id} 更新成功"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"更新票券錯誤: {e}")
        raise HTTPException(
            status_code=500,
            detail="更新票券失敗"
        )

@router.delete("/{ticket_id}", response_model=BaseResponse, summary="刪除票券")
#@limiter.limit("10/minute")
async def delete_ticket(
    ticket_id: int,
    user: APIUser = Depends(require_write_permission)
):
    """刪除票券（標記為已刪除）"""
    try:
        ticket_dao = get_ticket_dao()
        
        # 檢查票券是否存在
        existing_ticket = await ticket_dao.get_ticket(ticket_id)
        if not existing_ticket:
            raise HTTPException(
                status_code=404,
                detail=f"票券 #{ticket_id} 不存在"
            )
        
        # 軟刪除票券（更新狀態為 archived）
        success = await ticket_dao.update_ticket(ticket_id, status="archived")
        if not success:
            raise HTTPException(
                status_code=500,
                detail="刪除票券失敗"
            )
        
        return {
            "success": True,
            "message": f"票券 #{ticket_id} 已刪除"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"刪除票券錯誤: {e}")
        raise HTTPException(
            status_code=500,
            detail="刪除票券失敗"
        )

@router.post("/{ticket_id}/close", response_model=BaseResponse, summary="關閉票券")
#@limiter.limit("20/minute")
async def close_ticket(
    ticket_id: int,
    reason: Optional[str] = None,
    user: APIUser = Depends(require_write_permission)
):
    """關閉指定的票券"""
    try:
        ticket_manager = get_ticket_manager()
        
        # 關閉票券
        success = await ticket_manager.close_ticket(
            ticket_id=ticket_id,
            closed_by=0,  # API 關閉，使用特殊用戶 ID
            reason=reason
        )
        
        if not success:
            raise HTTPException(
                status_code=400,
                detail="關閉票券失敗"
            )
        
        return {
            "success": True,
            "message": f"票券 #{ticket_id} 已關閉"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"關閉票券錯誤: {e}")
        raise HTTPException(
            status_code=500,
            detail="關閉票券失敗"
        )

@router.post("/{ticket_id}/assign", response_model=BaseResponse, summary="指派票券")
#@limiter.limit("20/minute")
async def assign_ticket(
    ticket_id: int,
    assigned_to: int,
    user: APIUser = Depends(require_write_permission)
):
    """將票券指派給指定用戶"""
    try:
        ticket_manager = get_ticket_manager()
        
        # 指派票券
        success = await ticket_manager.assign_ticket(
            ticket_id=ticket_id,
            assigned_to=assigned_to,
            assigned_by=0  # API 指派，使用特殊用戶 ID
        )
        
        if not success:
            raise HTTPException(
                status_code=400,
                detail="指派票券失敗"
            )
        
        return {
            "success": True,
            "message": f"票券 #{ticket_id} 已指派給用戶 {assigned_to}"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"指派票券錯誤: {e}")
        raise HTTPException(
            status_code=500,
            detail="指派票券失敗"
        )

@router.post("/{ticket_id}/rating", response_model=BaseResponse, summary="為票券評分")
#@limiter.limit("10/minute")
async def rate_ticket(
    ticket_id: int,
    rating: int = Query(..., ge=1, le=5, description="評分 (1-5)"),
    feedback: Optional[str] = Query(None, description="回饋內容"),
    user: APIUser = Depends(require_write_permission)
):
    """為已關閉的票券進行評分"""
    try:
        ticket_manager = get_ticket_manager()
        
        # 保存評分
        success = await ticket_manager.save_rating(
            ticket_id=ticket_id,
            rating=rating,
            feedback=feedback
        )
        
        if not success:
            raise HTTPException(
                status_code=400,
                detail="保存評分失敗"
            )
        
        return {
            "success": True,
            "message": f"票券 #{ticket_id} 評分已保存"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"保存評分錯誤: {e}")
        raise HTTPException(
            status_code=500,
            detail="保存評分失敗"
        )

@router.get("/statistics/overview", response_model=TicketStatistics, summary="獲取票券統計概覽")
#@limiter.limit("10/minute")
async def get_ticket_statistics(
    guild_id: Optional[int] = Query(None, description="伺服器 ID 篩選"),
    days: int = Query(30, ge=1, le=365, description="統計天數"),
    user: APIUser = Depends(require_read_permission)
):
    """獲取票券統計概覽"""
    try:
        ticket_dao = get_ticket_dao()
        
        # 這裡需要實現統計查詢邏輯
        # stats = await ticket_dao.get_ticket_statistics(guild_id, days)
        
        # 暫時返回模擬數據
        return {
            "total_tickets": 100,
            "open_tickets": 25,
            "closed_tickets": 75,
            "high_priority": 10,
            "medium_priority": 60,
            "low_priority": 30,
            "avg_resolution_time": 2.5,
            "avg_rating": 4.2,
            "period_start": datetime.now(),
            "period_end": datetime.now()
        }
        
    except Exception as e:
        logger.error(f"獲取統計數據錯誤: {e}")
        raise HTTPException(
            status_code=500,
            detail="獲取統計數據失敗"
        )