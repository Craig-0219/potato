# bot/services/statistics_manager.py
"""
統計分析管理器
提供全面的票券、用戶、系統使用統計和分析功能
"""

import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
import json
import aiomysql

from bot.db.pool import db_pool
from shared.logger import logger


@dataclass
class StatisticsConfig:
    """統計配置"""
    cache_duration_minutes: int = 15
    enable_real_time_stats: bool = True
    default_days: int = 30
    max_days: int = 365


class StatisticsManager:
    """統計分析管理器"""
    
    def __init__(self, config: Optional[StatisticsConfig] = None):
        self.config = config or StatisticsConfig()
        self.db = db_pool
        self._cache = {}
        self._cache_timestamps = {}
    
    async def get_comprehensive_statistics(self, guild_id: Optional[int] = None, days: int = 30) -> Dict[str, Any]:
        """獲取綜合統計資料"""
        start_time = datetime.now()
        
        try:
            end_date = datetime.now()
            start_date = end_date - timedelta(days=days)
            
            # 並行執行各種統計查詢
            tasks = [
                self.get_ticket_statistics(guild_id, start_date, end_date),
                self.get_user_statistics(guild_id, start_date, end_date),
                self.get_performance_statistics(guild_id, start_date, end_date),
                self.get_trend_analysis(guild_id, start_date, end_date),
                self.get_workload_statistics(guild_id, start_date, end_date),
                self.get_satisfaction_statistics(guild_id, start_date, end_date),
                self.get_tag_statistics(guild_id, start_date, end_date),
                self.get_system_health_statistics(guild_id, start_date, end_date)
            ]
            
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # 整合結果
            comprehensive_stats = {
                'metadata': {
                    'guild_id': guild_id,
                    'period_start': start_date.isoformat(),
                    'period_end': end_date.isoformat(),
                    'days_analyzed': days,
                    'generated_at': datetime.now().isoformat(),
                    'generation_time': (datetime.now() - start_time).total_seconds()
                },
                'ticket_statistics': results[0] if not isinstance(results[0], Exception) else {},
                'user_statistics': results[1] if not isinstance(results[1], Exception) else {},
                'performance_statistics': results[2] if not isinstance(results[2], Exception) else {},
                'trend_analysis': results[3] if not isinstance(results[3], Exception) else {},
                'workload_statistics': results[4] if not isinstance(results[4], Exception) else {},
                'satisfaction_statistics': results[5] if not isinstance(results[5], Exception) else {},
                'tag_statistics': results[6] if not isinstance(results[6], Exception) else {},
                'system_health': results[7] if not isinstance(results[7], Exception) else {}
            }
            
            # 記錄錯誤
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    logger.error(f"統計查詢 {i} 失敗: {result}")
            
            logger.info(f"✅ 綜合統計生成完成 (耗時 {comprehensive_stats['metadata']['generation_time']:.2f}s)")
            
            return comprehensive_stats
            
        except Exception as e:
            logger.error(f"❌ 獲取綜合統計失敗: {e}", exc_info=True)
            return {'error': str(e)}
    
    async def get_ticket_statistics(self, guild_id: Optional[int], start_date: datetime, end_date: datetime) -> Dict[str, Any]:
        """獲取票券統計"""
        try:
            async with self.db.connection() as conn:
                async with conn.cursor(aiomysql.DictCursor) as cursor:
                    # 基本票券統計
                    base_query = """
                    SELECT 
                        COUNT(*) as total_tickets,
                        COUNT(CASE WHEN status = 'open' THEN 1 END) as open_tickets,
                        COUNT(CASE WHEN status = 'in_progress' THEN 1 END) as in_progress_tickets,
                        COUNT(CASE WHEN status = 'closed' THEN 1 END) as closed_tickets,
                        COUNT(CASE WHEN status = 'archived' THEN 1 END) as archived_tickets,
                        COUNT(CASE WHEN priority = 'low' THEN 1 END) as low_priority,
                        COUNT(CASE WHEN priority = 'medium' THEN 1 END) as medium_priority,
                        COUNT(CASE WHEN priority = 'high' THEN 1 END) as high_priority,
                        COUNT(CASE WHEN priority = 'urgent' THEN 1 END) as urgent_priority
                    FROM tickets
                    WHERE created_at BETWEEN %s AND %s
                    """
                    params = [start_date, end_date]
                    
                    if guild_id:
                        base_query += " AND guild_id = %s"
                        params.append(guild_id)
                    
                    await cursor.execute(base_query, params)
                    basic_stats = await cursor.fetchone()
                    
                    # 解決時間統計
                    resolution_query = """
                    SELECT 
                        AVG(TIMESTAMPDIFF(MINUTE, created_at, closed_at)) as avg_resolution_minutes,
                        MIN(TIMESTAMPDIFF(MINUTE, created_at, closed_at)) as min_resolution_minutes,
                        MAX(TIMESTAMPDIFF(MINUTE, created_at, closed_at)) as max_resolution_minutes
                    FROM tickets
                    WHERE closed_at IS NOT NULL 
                    AND created_at BETWEEN %s AND %s
                    """
                    params = [start_date, end_date]
                    
                    if guild_id:
                        resolution_query += " AND guild_id = %s"
                        params.append(guild_id)
                    
                    await cursor.execute(resolution_query, params)
                    resolution_stats = await cursor.fetchone()
                    
                    # 每日趨勢
                    daily_trend_query = """
                    SELECT 
                        DATE(created_at) as date,
                        COUNT(*) as daily_count
                    FROM tickets
                    WHERE created_at BETWEEN %s AND %s
                    """
                    params = [start_date, end_date]
                    
                    if guild_id:
                        daily_trend_query += " AND guild_id = %s"
                        params.append(guild_id)
                    
                    daily_trend_query += " GROUP BY DATE(created_at) ORDER BY date"
                    
                    await cursor.execute(daily_trend_query, params)
                    daily_trends = await cursor.fetchall()
                    
                    return {
                        'basic': basic_stats or {},
                        'resolution_time': resolution_stats or {},
                        'daily_trends': daily_trends or [],
                        'summary': {
                            'total_tickets': basic_stats['total_tickets'] if basic_stats else 0,
                            'resolution_rate': (basic_stats['closed_tickets'] / max(basic_stats['total_tickets'], 1) * 100) if basic_stats and basic_stats['total_tickets'] > 0 else 0,
                            'avg_daily_tickets': len(daily_trends) and sum(t['daily_count'] for t in daily_trends) / len(daily_trends) or 0
                        }
                    }
                    
        except Exception as e:
            logger.error(f"獲取票券統計失敗: {e}")
            return {'error': str(e)}
    
    async def get_user_statistics(self, guild_id: Optional[int], start_date: datetime, end_date: datetime) -> Dict[str, Any]:
        """獲取用戶統計"""
        try:
            async with self.db.connection() as conn:
                async with conn.cursor(aiomysql.DictCursor) as cursor:
                    # 活躍用戶統計
                    user_activity_query = """
                    SELECT 
                        COUNT(DISTINCT discord_id) as unique_users,
                        COUNT(*) as total_interactions,
                        AVG(ticket_count_per_user.ticket_count) as avg_tickets_per_user
                    FROM (
                        SELECT 
                            discord_id,
                            COUNT(*) as ticket_count
                        FROM tickets
                        WHERE created_at BETWEEN %s AND %s
                    """
                    params = [start_date, end_date]
                    
                    if guild_id:
                        user_activity_query += " AND guild_id = %s"
                        params.append(guild_id)
                    
                    user_activity_query += """
                        GROUP BY discord_id
                    ) as ticket_count_per_user
                    """
                    
                    await cursor.execute(user_activity_query, params)
                    activity_stats = await cursor.fetchone()
                    
                    # 頂級用戶
                    top_users_query = """
                    SELECT 
                        discord_id,
                        discord_username,
                        COUNT(*) as ticket_count,
                        COUNT(CASE WHEN status = 'closed' THEN 1 END) as closed_count,
                        AVG(CASE WHEN rating IS NOT NULL THEN rating END) as avg_rating,
                        MAX(created_at) as last_ticket_date
                    FROM tickets
                    WHERE created_at BETWEEN %s AND %s
                    """
                    params = [start_date, end_date]
                    
                    if guild_id:
                        top_users_query += " AND guild_id = %s"
                        params.append(guild_id)
                    
                    top_users_query += """
                    GROUP BY discord_id, discord_username
                    ORDER BY ticket_count DESC
                    LIMIT 10
                    """
                    
                    await cursor.execute(top_users_query, params)
                    top_users = await cursor.fetchall()
                    
                    return {
                        'activity_overview': activity_stats or {},
                        'top_users': top_users or [],
                        'summary': {
                            'total_unique_users': activity_stats['unique_users'] if activity_stats else 0,
                            'avg_tickets_per_user': round(activity_stats['avg_tickets_per_user'] or 0, 2)
                        }
                    }
                    
        except Exception as e:
            logger.error(f"獲取用戶統計失敗: {e}")
            return {'error': str(e)}
    
    async def get_performance_statistics(self, guild_id: Optional[int], start_date: datetime, end_date: datetime) -> Dict[str, Any]:
        """獲取性能統計"""
        try:
            async with self.db.connection() as conn:
                async with conn.cursor(aiomysql.DictCursor) as cursor:
                    # 回應時間統計
                    response_time_query = """
                    SELECT 
                        AVG(TIMESTAMPDIFF(MINUTE, created_at, 
                            CASE WHEN first_response_at IS NOT NULL THEN first_response_at
                                 WHEN assigned_at IS NOT NULL THEN assigned_at
                                 ELSE updated_at END)) as avg_first_response_minutes,
                        AVG(TIMESTAMPDIFF(HOUR, created_at, closed_at)) as avg_resolution_hours,
                        COUNT(CASE WHEN TIMESTAMPDIFF(HOUR, created_at, closed_at) <= 24 THEN 1 END) as resolved_within_24h,
                        COUNT(CASE WHEN closed_at IS NOT NULL THEN 1 END) as total_resolved
                    FROM tickets
                    WHERE created_at BETWEEN %s AND %s
                    AND status = 'closed'
                    """
                    params = [start_date, end_date]
                    
                    if guild_id:
                        response_time_query += " AND guild_id = %s"
                        params.append(guild_id)
                    
                    await cursor.execute(response_time_query, params)
                    response_stats = await cursor.fetchone()
                    
                    return {
                        'response_times': response_stats or {},
                        'summary': {
                            'avg_first_response_hours': round((response_stats['avg_first_response_minutes'] or 0) / 60, 2),
                            'avg_resolution_hours': round(response_stats['avg_resolution_hours'] or 0, 2),
                            'resolution_within_24h_rate': round(((response_stats['resolved_within_24h'] or 0) / max(response_stats['total_resolved'], 1)) * 100, 2)
                        }
                    }
                    
        except Exception as e:
            logger.error(f"獲取性能統計失敗: {e}")
            return {'error': str(e)}
    
    async def get_trend_analysis(self, guild_id: Optional[int], start_date: datetime, end_date: datetime) -> Dict[str, Any]:
        """獲取趨勢分析"""
        try:
            async with self.db.connection() as conn:
                async with conn.cursor(aiomysql.DictCursor) as cursor:
                    # 週趨勢分析
                    weekly_trend_query = """
                    SELECT 
                        YEAR(created_at) as year,
                        WEEK(created_at) as week,
                        COUNT(*) as ticket_count,
                        COUNT(CASE WHEN status = 'closed' THEN 1 END) as closed_count
                    FROM tickets
                    WHERE created_at BETWEEN %s AND %s
                    """
                    params = [start_date, end_date]
                    
                    if guild_id:
                        weekly_trend_query += " AND guild_id = %s"
                        params.append(guild_id)
                    
                    weekly_trend_query += " GROUP BY YEAR(created_at), WEEK(created_at) ORDER BY year, week"
                    
                    await cursor.execute(weekly_trend_query, params)
                    weekly_trends = await cursor.fetchall()
                    
                    return {
                        'weekly_trends': weekly_trends or [],
                        'summary': {
                            'trend_direction': 'stable'
                        }
                    }
                    
        except Exception as e:
            logger.error(f"獲取趨勢分析失敗: {e}")
            return {'error': str(e)}
    
    async def get_workload_statistics(self, guild_id: Optional[int], start_date: datetime, end_date: datetime) -> Dict[str, Any]:
        """獲取工作負載統計"""
        try:
            async with self.db.connection() as conn:
                async with conn.cursor(aiomysql.DictCursor) as cursor:
                    # 員工工作負載
                    staff_workload_query = """
                    SELECT 
                        assigned_to,
                        COUNT(*) as assigned_count,
                        COUNT(CASE WHEN status = 'closed' THEN 1 END) as completed_count
                    FROM tickets
                    WHERE assigned_at BETWEEN %s AND %s
                    AND assigned_to IS NOT NULL
                    """
                    params = [start_date, end_date]
                    
                    if guild_id:
                        staff_workload_query += " AND guild_id = %s"
                        params.append(guild_id)
                    
                    staff_workload_query += " GROUP BY assigned_to ORDER BY assigned_count DESC"
                    
                    await cursor.execute(staff_workload_query, params)
                    staff_workloads = await cursor.fetchall()
                    
                    return {
                        'staff_workloads': staff_workloads or [],
                        'summary': {
                            'total_staff': len(staff_workloads)
                        }
                    }
                    
        except Exception as e:
            logger.error(f"獲取工作負載統計失敗: {e}")
            return {'error': str(e)}
    
    async def get_satisfaction_statistics(self, guild_id: Optional[int], start_date: datetime, end_date: datetime) -> Dict[str, Any]:
        """獲取滿意度統計"""
        try:
            async with self.db.connection() as conn:
                async with conn.cursor(aiomysql.DictCursor) as cursor:
                    # 評分統計
                    rating_stats_query = """
                    SELECT 
                        COUNT(CASE WHEN rating IS NOT NULL THEN 1 END) as rated_tickets,
                        COUNT(*) as total_closed_tickets,
                        AVG(rating) as avg_rating,
                        COUNT(CASE WHEN rating = 5 THEN 1 END) as five_star,
                        COUNT(CASE WHEN rating = 4 THEN 1 END) as four_star,
                        COUNT(CASE WHEN rating = 3 THEN 1 END) as three_star,
                        COUNT(CASE WHEN rating = 2 THEN 1 END) as two_star,
                        COUNT(CASE WHEN rating = 1 THEN 1 END) as one_star
                    FROM tickets
                    WHERE closed_at BETWEEN %s AND %s
                    """
                    params = [start_date, end_date]
                    
                    if guild_id:
                        rating_stats_query += " AND guild_id = %s"
                        params.append(guild_id)
                    
                    await cursor.execute(rating_stats_query, params)
                    rating_stats = await cursor.fetchone()
                    
                    if rating_stats:
                        rating_response_rate = (rating_stats['rated_tickets'] / max(rating_stats['total_closed_tickets'], 1)) * 100
                    else:
                        rating_response_rate = 0
                    
                    return {
                        'rating_distribution': rating_stats or {},
                        'summary': {
                            'avg_rating': round(rating_stats['avg_rating'] or 0, 2),
                            'rating_response_rate': round(rating_response_rate, 2)
                        }
                    }
                    
        except Exception as e:
            logger.error(f"獲取滿意度統計失敗: {e}")
            return {'error': str(e)}
    
    async def get_tag_statistics(self, guild_id: Optional[int], start_date: datetime, end_date: datetime) -> Dict[str, Any]:
        """獲取標籤統計"""
        try:
            async with self.db.connection() as conn:
                async with conn.cursor(aiomysql.DictCursor) as cursor:
                    # 標籤使用統計
                    tag_usage_query = """
                    SELECT 
                        tt.name as tag_name,
                        COUNT(ttm.ticket_id) as usage_count
                    FROM ticket_tags tt
                    LEFT JOIN ticket_tag_mappings ttm ON tt.id = ttm.tag_id
                    LEFT JOIN tickets t ON ttm.ticket_id = t.id AND t.created_at BETWEEN %s AND %s
                    WHERE 1=1
                    """
                    params = [start_date, end_date]
                    
                    if guild_id:
                        tag_usage_query += " AND tt.guild_id = %s"
                        params.append(guild_id)
                    
                    tag_usage_query += " GROUP BY tt.id, tt.name ORDER BY usage_count DESC"
                    
                    await cursor.execute(tag_usage_query, params)
                    tag_stats = await cursor.fetchall()
                    
                    return {
                        'tag_usage': tag_stats or [],
                        'summary': {
                            'total_tags': len(tag_stats),
                            'most_used_tag': max(tag_stats, key=lambda x: x['usage_count'])['tag_name'] if tag_stats else None
                        }
                    }
                    
        except Exception as e:
            logger.error(f"獲取標籤統計失敗: {e}")
            return {'error': str(e)}
    
    async def get_system_health_statistics(self, guild_id: Optional[int], start_date: datetime, end_date: datetime) -> Dict[str, Any]:
        """獲取系統健康統計"""
        try:
            async with self.db.connection() as conn:
                async with conn.cursor(aiomysql.DictCursor) as cursor:
                    # 資料庫健康統計
                    db_health_query = """
                    SELECT 
                        table_name,
                        table_rows as record_count,
                        data_length + index_length as size_bytes
                    FROM information_schema.tables
                    WHERE table_schema = DATABASE()
                    AND table_name IN ('tickets', 'votes', 'system_logs', 'security_events')
                    ORDER BY size_bytes DESC
                    """
                    
                    await cursor.execute(db_health_query)
                    db_health = await cursor.fetchall()
                    
                    return {
                        'database_health': db_health or [],
                        'summary': {
                            'system_health_score': 100,
                            'total_database_size_mb': round(sum(table['size_bytes'] for table in db_health) / 1024 / 1024, 2)
                        }
                    }
                    
        except Exception as e:
            logger.error(f"獲取系統健康統計失敗: {e}")
            return {'error': str(e)}
    
    async def generate_statistical_report(self, guild_id: Optional[int] = None, days: int = 30) -> Dict[str, Any]:
        """生成統計報告"""
        try:
            stats = await self.get_comprehensive_statistics(guild_id, days)
            
            if 'error' not in stats:
                # 生成報告摘要
                report_summary = {
                    'period_summary': {
                        'total_tickets': stats.get('ticket_statistics', {}).get('summary', {}).get('total_tickets', 0),
                        'resolution_rate': stats.get('ticket_statistics', {}).get('summary', {}).get('resolution_rate', 0),
                        'avg_rating': stats.get('satisfaction_statistics', {}).get('summary', {}).get('avg_rating', 0),
                        'system_health_score': stats.get('system_health', {}).get('summary', {}).get('system_health_score', 100)
                    }
                }
                
                stats['report_summary'] = report_summary
            
            return stats
            
        except Exception as e:
            logger.error(f"生成統計報告失敗: {e}")
            return {'error': str(e)}