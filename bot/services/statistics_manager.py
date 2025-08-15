# bot/services/statistics_manager.py
"""
統計分析管理器 - 簡化版
提供基本的統計功能，避免複雜的合併衝突
"""

import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional, Any
import aiomysql
from bot.db.pool import db_pool
from shared.logger import logger


class StatisticsConfig:
    """統計配置"""
    DEFAULT_DAYS = 30
    MAX_DAYS = 365
    CACHE_DURATION = 300  # 5分鐘快取


class StatisticsManager:
    """統計分析管理器 - 簡化版"""
    
    def __init__(self):
        self.db = db_pool
        self.config = StatisticsConfig()
    
    async def get_comprehensive_statistics(self, guild_id: Optional[int] = None, days: int = 30) -> Dict[str, Any]:
        """獲取綜合統計資料（簡化版）"""
        try:
            # 基本票券統計
            ticket_stats = await self._get_basic_ticket_stats(guild_id, days)
            
            # 基本投票統計
            vote_stats = await self._get_basic_vote_stats(guild_id, days)
            
            # 基本系統統計
            system_stats = await self._get_basic_system_stats()
            
            return {
                'ticket_statistics': ticket_stats,
                'vote_statistics': vote_stats,
                'system_statistics': system_stats,
                'period': f"最近 {days} 天",
                'generated_at': datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"獲取綜合統計失敗: {e}")
            return {'error': str(e)}
    
    async def _get_basic_ticket_stats(self, guild_id: Optional[int], days: int) -> Dict[str, Any]:
        """獲取基本票券統計"""
        try:
            async with self.db.connection() as conn:
                async with conn.cursor(aiomysql.DictCursor) as cursor:
                    where_clause = ""
                    params = [days]
                    
                    if guild_id:
                        where_clause = "AND guild_id = %s"
                        params.append(guild_id)
                    
                    query = f"""
                    SELECT 
                        COUNT(*) as total_tickets,
                        COUNT(CASE WHEN status = 'closed' THEN 1 END) as closed_tickets,
                        COUNT(CASE WHEN status = 'open' THEN 1 END) as open_tickets,
                        COALESCE(AVG(rating), 0) as avg_rating
                    FROM tickets 
                    WHERE created_at >= DATE_SUB(NOW(), INTERVAL %s DAY)
                    {where_clause}
                    """
                    
                    await cursor.execute(query, params)
                    result = await cursor.fetchone()
                    
                    if result:
                        total = result['total_tickets'] or 0
                        closed = result['closed_tickets'] or 0
                        resolution_rate = (closed / total * 100) if total > 0 else 0
                        
                        return {
                            'summary': {
                                'total_tickets': total,
                                'open_tickets': result['open_tickets'] or 0,
                                'closed_tickets': closed,
                                'resolution_rate': round(resolution_rate, 2),
                                'avg_rating': round(result['avg_rating'] or 0, 2)
                            }
                        }
                    
                    return {'summary': {'total_tickets': 0, 'resolution_rate': 0}}
                    
        except Exception as e:
            logger.error(f"獲取票券統計失敗: {e}")
            return {'error': str(e)}
    
    async def _get_basic_vote_stats(self, guild_id: Optional[int], days: int) -> Dict[str, Any]:
        """獲取基本投票統計"""
        try:
            async with self.db.connection() as conn:
                async with conn.cursor(aiomysql.DictCursor) as cursor:
                    where_clause = ""
                    params = [days]
                    
                    if guild_id:
                        where_clause = "AND guild_id = %s"
                        params.append(guild_id)
                    
                    query = f"""
                    SELECT 
                        COUNT(*) as total_votes,
                        COUNT(CASE WHEN end_time < NOW() THEN 1 END) as completed_votes,
                        COUNT(CASE WHEN end_time >= NOW() THEN 1 END) as active_votes
                    FROM votes 
                    WHERE start_time >= DATE_SUB(NOW(), INTERVAL %s DAY)
                    {where_clause}
                    """
                    
                    await cursor.execute(query, params)
                    result = await cursor.fetchone()
                    
                    if result:
                        return {
                            'summary': {
                                'total_votes': result['total_votes'] or 0,
                                'completed_votes': result['completed_votes'] or 0,
                                'active_votes': result['active_votes'] or 0
                            }
                        }
                    
                    return {'summary': {'total_votes': 0}}
                    
        except Exception as e:
            logger.error(f"獲取投票統計失敗: {e}")
            return {'error': str(e)}
    
    async def _get_basic_system_stats(self) -> Dict[str, Any]:
        """獲取基本系統統計"""
        try:
            async with self.db.connection() as conn:
                async with conn.cursor(aiomysql.DictCursor) as cursor:
                    # 簡單的系統統計
                    await cursor.execute("SELECT DATABASE() as db_name, NOW() as current_time")
                    result = await cursor.fetchone()
                    
                    return {
                        'summary': {
                            'database_name': result['db_name'] if result else 'unknown',
                            'system_time': str(result['current_time']) if result else str(datetime.now()),
                            'status': 'healthy'
                        }
                    }
                    
        except Exception as e:
            logger.error(f"獲取系統統計失敗: {e}")
            return {'error': str(e)}
    
    async def get_ticket_statistics(self, guild_id: Optional[int] = None, days: int = 30) -> Dict[str, Any]:
        """獲取票券統計（向後兼容）"""
        return await self._get_basic_ticket_stats(guild_id, days)
    
    async def get_vote_statistics(self, guild_id: Optional[int] = None, days: int = 30) -> Dict[str, Any]:
        """獲取投票統計（向後兼容）"""
        return await self._get_basic_vote_stats(guild_id, days)
    
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
                        'total_votes': stats.get('vote_statistics', {}).get('summary', {}).get('total_votes', 0),
                        'system_status': stats.get('system_statistics', {}).get('summary', {}).get('status', 'unknown')
                    }
                }
                
                stats['report_summary'] = report_summary
            
            return stats
            
        except Exception as e:
            logger.error(f"生成統計報告失敗: {e}")
            return {'error': str(e)}
    
    async def generate_comprehensive_report(self, guild_id: Optional[int] = None, days: int = 30) -> Dict[str, Any]:
        """生成綜合報告 - 修復缺失的方法"""
        try:
            logger.info(f"開始生成綜合報告 - Guild ID: {guild_id}, 天數: {days}")
            
            # 獲取基本統計數據
            comprehensive_stats = await self.get_comprehensive_statistics(guild_id, days)
            
            if 'error' in comprehensive_stats:
                return comprehensive_stats
            
            # 生成關鍵指標
            ticket_stats = comprehensive_stats.get('ticket_statistics', {}).get('summary', {})
            vote_stats = comprehensive_stats.get('vote_statistics', {}).get('summary', {})
            system_stats = comprehensive_stats.get('system_statistics', {}).get('summary', {})
            
            # 計算關鍵績效指標
            kpi_metrics = {
                'ticket_resolution_rate': ticket_stats.get('resolution_rate', 0),
                'average_rating': ticket_stats.get('avg_rating', 0),
                'total_interactions': ticket_stats.get('total_tickets', 0) + vote_stats.get('total_votes', 0),
                'system_health_score': 100.0 if system_stats.get('status') == 'healthy' else 0.0
            }
            
            # 生成趨勢分析（簡化版）
            trend_analysis = {
                'ticket_trend': 'stable',  # 簡化版，實際應該基於歷史數據
                'vote_trend': 'stable',
                'engagement_trend': 'positive' if kpi_metrics['total_interactions'] > 0 else 'low'
            }
            
            # 生成建議和洞察
            insights = []
            if ticket_stats.get('resolution_rate', 0) < 80:
                insights.append("票券解決率偏低，建議檢查處理流程")
            if vote_stats.get('total_votes', 0) == 0:
                insights.append("投票參與度較低，可考慮推廣投票功能")
            if kpi_metrics['average_rating'] < 3.0 and kpi_metrics['average_rating'] > 0:
                insights.append("用戶滿意度有待改進，建議優化服務品質")
            
            if not insights:
                insights.append("系統運行良好，各項指標正常")
            
            # 構建完整報告
            comprehensive_report = {
                **comprehensive_stats,
                'kpi_metrics': kpi_metrics,
                'trend_analysis': trend_analysis,
                'insights': insights,
                'report_metadata': {
                    'report_type': 'comprehensive',
                    'guild_id': guild_id,
                    'analysis_period_days': days,
                    'generated_timestamp': datetime.now().isoformat(),
                    'data_freshness': 'real_time'
                }
            }
            
            logger.info("綜合報告生成成功")
            return comprehensive_report
            
        except Exception as e:
            logger.error(f"生成綜合報告失敗: {e}")
            return {
                'error': str(e),
                'report_metadata': {
                    'report_type': 'comprehensive',
                    'status': 'failed',
                    'error_timestamp': datetime.now().isoformat()
                }
            }
    
    async def get_realtime_stats(self, guild_id: int) -> Dict[str, Any]:
        """獲取實時統計數據"""
        try:
            async with self.db.connection() as conn:
                async with conn.cursor(aiomysql.DictCursor) as cursor:
                    # 獲取今日新票券數
                    await cursor.execute("""
                        SELECT COUNT(*) as today_new_tickets
                        FROM tickets 
                        WHERE guild_id = %s 
                        AND DATE(created_at) = CURDATE()
                    """, (guild_id,))
                    today_tickets_result = await cursor.fetchone()
                    
                    # 獲取開放和待處理票券數
                    await cursor.execute("""
                        SELECT 
                            COUNT(CASE WHEN status = 'open' THEN 1 END) as open_tickets,
                            COUNT(CASE WHEN status = 'pending' THEN 1 END) as pending_tickets
                        FROM tickets 
                        WHERE guild_id = %s 
                        AND status IN ('open', 'pending')
                    """, (guild_id,))
                    tickets_result = await cursor.fetchone()
                    
                    # 獲取活躍投票數
                    await cursor.execute("""
                        SELECT COUNT(*) as active_votes
                        FROM votes 
                        WHERE guild_id = %s 
                        AND end_time > NOW()
                    """, (guild_id,))
                    votes_result = await cursor.fetchone()
                    
                    return {
                        'system_online': True,
                        'active_users': 0,  # 暫時使用預設值
                        'current_load': 0.1,  # 暫時使用預設值
                        'open_tickets': tickets_result['open_tickets'] if tickets_result else 0,
                        'pending_tickets': tickets_result['pending_tickets'] if tickets_result else 0,
                        'today_new_tickets': today_tickets_result['today_new_tickets'] if today_tickets_result else 0,
                        'active_workflows': 0,  # 暫時使用預設值
                        'running_executions': 0,  # 暫時使用預設值
                        'today_executions': 0,  # 暫時使用預設值
                        'active_votes': votes_result['active_votes'] if votes_result else 0,
                        'last_updated': datetime.now().isoformat()
                    }
                    
        except Exception as e:
            logger.error(f"獲取實時統計失敗: {e}")
            return {
                'system_online': False,
                'active_users': 0,
                'current_load': 0.0,
                'open_tickets': 0,
                'pending_tickets': 0,
                'today_new_tickets': 0,
                'active_workflows': 0,
                'running_executions': 0,
                'today_executions': 0,
                'active_votes': 0,
                'error': str(e)
            }