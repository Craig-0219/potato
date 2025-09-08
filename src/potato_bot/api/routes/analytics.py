# bot/api/routes/analytics.py
"""
分析統計 API 端點
提供系統分析、報告生成和數據視覺化功能
"""

from datetime import datetime, timedelta

# from slowapi import Limiter, _rate_limit_exceeded_handler
# from slowapi.util import get_remote_address
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from potato_shared.logger import logger

from ..auth import APIUser, require_read_permission
from ..models import StaffPerformance

router = APIRouter()
# limiter = Limiter(key_func=get_remote_address)


@router.get("/dashboard", summary="獲取分析儀表板數據")
# @limiter.limit("20/minute")
async def get_dashboard_data(
    guild_id: Optional[int] = Query(None, description="伺服器 ID"),
    period: str = Query("30d", pattern="^(1d|7d|30d|90d|1y)$", description="統計期間"),
    user: APIUser = Depends(require_read_permission),
):
    """
    獲取分析儀表板數據（需要認證）

    包含票券統計、性能指標、趨勢分析等
    """
    return await _get_dashboard_data_internal(guild_id, period)


@router.get("/public-dashboard", summary="獲取公開分析儀表板數據")
# @limiter.limit("30/minute")
async def get_public_dashboard_data(
    guild_id: Optional[int] = Query(None, description="伺服器 ID"),
    period: str = Query("30d", pattern="^(1d|7d|30d|90d|1y)$", description="統計期間"),
):
    """
    獲取分析儀表板數據（無需認證）

    包含票券統計、性能指標、趨勢分析等
    """
    return await _get_dashboard_data_internal(guild_id, period)


async def _get_dashboard_data_internal(guild_id: Optional[int], period: str):
    """
    獲取分析儀表板數據（內部實現）

    包含票券統計、性能指標、趨勢分析等
    """
    try:
        # 解析期間參數
        period_map = {"1d": 1, "7d": 7, "30d": 30, "90d": 90, "1y": 365}
        days = period_map.get(period, 30)

        # 實現儀表板數據查詢邏輯 - 使用獨立資料庫連接
        import os

        import aiomysql

        conn = await aiomysql.connect(
            host=os.getenv("DB_HOST", "localhost"),
            port=int(os.getenv("DB_PORT", 3306)),
            user=os.getenv("DB_USER", "root"),
            password=os.getenv("DB_PASSWORD", ""),
            db=os.getenv("DB_NAME", "potato_db"),
            charset="utf8mb4",
            autocommit=True,
        )

        try:
            async with conn.cursor(aiomysql.DictCursor) as cursor:
                start_date = datetime.now() - timedelta(days=days)

                # 查詢票券統計
                await cursor.execute(
                    """
                    SELECT
                        COUNT(*) as total_tickets,
                        COUNT(CASE WHEN status != 'closed' THEN 1 END) as active_tickets,
                        COUNT(CASE WHEN status = 'closed' THEN 1 END) as resolved_tickets,
                        AVG(CASE
                            WHEN status = 'closed' AND closed_at IS NOT NULL
                            THEN TIMESTAMPDIFF(HOUR, created_at, closed_at)
                        END) as avg_resolution_hours
                    FROM tickets
                    WHERE created_at >= %s
                    AND (%s IS NULL OR guild_id = %s)
                """,
                    (start_date, guild_id, guild_id),
                )

                ticket_stats = await cursor.fetchone()

                # 查詢票券創建趨勢（每日）
                await cursor.execute(
                    """
                    SELECT
                        DATE(created_at) as date,
                        COUNT(*) as count
                    FROM tickets
                    WHERE created_at >= %s
                    AND (%s IS NULL OR guild_id = %s)
                    GROUP BY DATE(created_at)
                    ORDER BY date DESC
                    LIMIT 7
                """,
                    (start_date, guild_id, guild_id),
                )

                daily_tickets = await cursor.fetchall()

                # 查詢投票統計
                await cursor.execute(
                    """
                    SELECT
                        COUNT(*) as total_votes,
                        COUNT(CASE WHEN end_time > NOW() THEN 1 END) as active_votes,
                        COUNT(CASE WHEN end_time <= NOW() THEN 1 END) as completed_votes
                    FROM votes
                    WHERE start_time >= %s
                    AND (%s IS NULL OR guild_id = %s)
                """,
                    (start_date, guild_id, guild_id),
                )

                vote_stats = await cursor.fetchone()

                # 轉換類型並處理 None 值
                import decimal

                def convert_decimal(value):
                    if value is None:
                        return 0
                    return float(value) if isinstance(value, decimal.Decimal) else value

                return {
                    "success": True,
                    "data": {
                        "daily_tickets": convert_decimal(ticket_stats["total_tickets"]),
                        "resolution_rate": round(
                            (
                                convert_decimal(ticket_stats["resolved_tickets"])
                                / max(
                                    convert_decimal(ticket_stats["total_tickets"]),
                                    1,
                                )
                            )
                            * 100,
                            1,
                        ),
                        "satisfaction_score": 4.2,  # 暫時使用固定值
                        "response_time": (
                            round(
                                convert_decimal(ticket_stats["avg_resolution_hours"]),
                                1,
                            )
                            if ticket_stats["avg_resolution_hours"]
                            else 0
                        ),
                        "active_agents": 8,  # 暫時使用固定值
                        "pending_tickets": convert_decimal(ticket_stats["active_tickets"]),
                        "vote_statistics": {
                            "total_votes": convert_decimal(vote_stats["total_votes"]),
                            "active_votes": convert_decimal(vote_stats["active_votes"]),
                            "completed_votes": convert_decimal(vote_stats["completed_votes"]),
                        },
                        "trends": {
                            "daily_counts": [
                                convert_decimal(item["count"]) for item in daily_tickets[::-1]
                            ]  # 反轉以顯示時間順序
                        },
                    },
                    "timestamp": datetime.now(),
                }
        finally:
            conn.close()

    except Exception as e:
        logger.error(f"獲取儀表板數據錯誤: {e}")
        raise HTTPException(status_code=500, detail="獲取儀表板數據失敗")


@router.get("/reports", summary="生成分析報告")
# @limiter.limit("5/minute")
async def generate_report(
    report_type: str = Query(..., pattern="^(summary|detailed|performance|trend)$"),
    format: str = Query("json", pattern="^(json|csv|pdf)$"),
    guild_id: Optional[int] = Query(None),
    start_date: Optional[datetime] = Query(None),
    end_date: Optional[datetime] = Query(None),
    user: APIUser = Depends(require_read_permission),
):
    """生成各類分析報告"""
    try:
        # TODO: 實現報告生成邏輯

        return {
            "success": True,
            "message": f"{report_type} 報告生成成功",
            "data": {
                "report_id": "rpt_" + datetime.now().strftime("%Y%m%d_%H%M%S"),
                "type": report_type,
                "format": format,
                "download_url": "/api/v1/analytics/reports/download/rpt_example",
                "expires_at": datetime.now() + timedelta(hours=24),
            },
        }

    except Exception as e:
        logger.error(f"生成報告錯誤: {e}")
        raise HTTPException(status_code=500, detail="生成報告失敗")


@router.get(
    "/staff-performance",
    response_model=List[StaffPerformance],
    summary="獲取客服績效數據",
)
# @limiter.limit("10/minute")
async def get_staff_performance(
    guild_id: Optional[int] = Query(None),
    days: int = Query(30, ge=1, le=365),
    user: APIUser = Depends(require_read_permission),
):
    """獲取客服團隊績效統計"""
    try:
        # TODO: 實現客服績效查詢邏輯

        return [
            {
                "staff_id": 123456789,
                "username": "客服小王",
                "total_assigned": 45,
                "total_completed": 40,
                "avg_completion_time": 2.1,
                "avg_rating": 4.6,
                "current_workload": 5,
                "efficiency_score": 0.92,
            }
        ]

    except Exception as e:
        logger.error(f"獲取客服績效錯誤: {e}")
        raise HTTPException(status_code=500, detail="獲取客服績效失敗")
