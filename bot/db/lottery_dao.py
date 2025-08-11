# bot/db/lottery_dao.py
"""
抽獎系統資料存取物件
處理抽獎相關的資料庫操作
"""

import asyncio
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
import aiomysql

from .base_dao import BaseDAO
from shared.logger import logger


@dataclass
class LotteryData:
    """抽獎資料類別"""
    id: Optional[int] = None
    guild_id: int = 0
    name: str = ""
    description: Optional[str] = None
    creator_id: int = 0
    channel_id: int = 0
    message_id: Optional[int] = None
    prize_type: str = "custom"
    prize_data: Optional[Dict] = None
    winner_count: int = 1
    entry_method: str = "reaction"
    required_roles: Optional[List[int]] = None
    excluded_roles: Optional[List[int]] = None
    min_account_age_days: int = 0
    min_server_join_days: int = 0
    start_time: datetime = None
    end_time: datetime = None
    status: str = "pending"
    auto_end: bool = True
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class LotteryDAO(BaseDAO):
    """抽獎系統資料存取物件"""
    
    def __init__(self):
        super().__init__()
        self.table_name = "lotteries"
    
    async def _initialize(self):
        """初始化抽獎DAO"""
        logger.info("✅ 抽獎 DAO 初始化完成")

    async def create_lottery(self, lottery_data: LotteryData) -> int:
        """創建抽獎"""
        try:
            async with self.db.connection() as conn:
                async with conn.cursor() as cursor:
                    query = """
                    INSERT INTO lotteries (
                        guild_id, name, description, creator_id, channel_id,
                        prize_type, prize_data, winner_count, entry_method,
                        required_roles, excluded_roles, min_account_age_days,
                        min_server_join_days, start_time, end_time, auto_end
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """
                    
                    await cursor.execute(query, (
                        lottery_data.guild_id, lottery_data.name, lottery_data.description,
                        lottery_data.creator_id, lottery_data.channel_id,
                        lottery_data.prize_type, json.dumps(lottery_data.prize_data) if lottery_data.prize_data else None,
                        lottery_data.winner_count, lottery_data.entry_method,
                        json.dumps(lottery_data.required_roles) if lottery_data.required_roles else None,
                        json.dumps(lottery_data.excluded_roles) if lottery_data.excluded_roles else None,
                        lottery_data.min_account_age_days, lottery_data.min_server_join_days,
                        lottery_data.start_time, lottery_data.end_time, lottery_data.auto_end
                    ))
                    
                    lottery_id = cursor.lastrowid
                    await conn.commit()
                    
                    logger.info(f"創建抽獎成功: {lottery_id} - {lottery_data.name}")
                    return lottery_id
                    
        except Exception as e:
            logger.error(f"創建抽獎失敗: {e}")
            raise

    async def get_lottery(self, lottery_id: int) -> Optional[Dict]:
        """獲取單個抽獎"""
        try:
            async with self.db.connection() as conn:
                async with conn.cursor(aiomysql.DictCursor) as cursor:
                    query = "SELECT * FROM lotteries WHERE id = %s"
                    await cursor.execute(query, (lottery_id,))
                    result = await cursor.fetchone()
                    
                    if result:
                        # 解析JSON欄位
                        if result['prize_data']:
                            result['prize_data'] = json.loads(result['prize_data'])
                        if result['required_roles']:
                            result['required_roles'] = json.loads(result['required_roles'])
                        if result['excluded_roles']:
                            result['excluded_roles'] = json.loads(result['excluded_roles'])
                    
                    return result
                    
        except Exception as e:
            logger.error(f"獲取抽獎失敗: {e}")
            return None

    async def get_active_lotteries(self, guild_id: int) -> List[Dict]:
        """獲取活躍抽獎列表"""
        try:
            async with self.db.connection() as conn:
                async with conn.cursor(aiomysql.DictCursor) as cursor:
                    query = """
                    SELECT * FROM lotteries 
                    WHERE guild_id = %s AND status IN ('pending', 'active')
                    ORDER BY created_at DESC
                    """
                    await cursor.execute(query, (guild_id,))
                    results = await cursor.fetchall()
                    
                    # 解析JSON欄位
                    for result in results:
                        if result['prize_data']:
                            result['prize_data'] = json.loads(result['prize_data'])
                        if result['required_roles']:
                            result['required_roles'] = json.loads(result['required_roles'])
                        if result['excluded_roles']:
                            result['excluded_roles'] = json.loads(result['excluded_roles'])
                    
                    return results
                    
        except Exception as e:
            logger.error(f"獲取活躍抽獎失敗: {e}")
            return []

    async def add_entry(self, lottery_id: int, user_id: int, username: str, entry_method: str = "reaction") -> bool:
        """添加參與者"""
        try:
            async with self.db.connection() as conn:
                async with conn.cursor() as cursor:
                    query = """
                    INSERT INTO lottery_entries (lottery_id, user_id, username, entry_method)
                    VALUES (%s, %s, %s, %s)
                    ON DUPLICATE KEY UPDATE entry_time = CURRENT_TIMESTAMP
                    """
                    
                    await cursor.execute(query, (lottery_id, user_id, username, entry_method))
                    await conn.commit()
                    
                    return True
                    
        except Exception as e:
            logger.error(f"添加抽獎參與者失敗: {e}")
            return False

    async def remove_entry(self, lottery_id: int, user_id: int) -> bool:
        """移除參與者"""
        try:
            async with self.db.connection() as conn:
                async with conn.cursor() as cursor:
                    query = "DELETE FROM lottery_entries WHERE lottery_id = %s AND user_id = %s"
                    await cursor.execute(query, (lottery_id, user_id))
                    await conn.commit()
                    
                    return cursor.rowcount > 0
                    
        except Exception as e:
            logger.error(f"移除抽獎參與者失敗: {e}")
            return False

    async def get_entries(self, lottery_id: int) -> List[Dict]:
        """獲取抽獎參與者列表"""
        try:
            async with self.db.connection() as conn:
                async with conn.cursor(aiomysql.DictCursor) as cursor:
                    query = """
                    SELECT * FROM lottery_entries 
                    WHERE lottery_id = %s AND is_valid = TRUE
                    ORDER BY entry_time ASC
                    """
                    await cursor.execute(query, (lottery_id,))
                    return await cursor.fetchall()
                    
        except Exception as e:
            logger.error(f"獲取抽獎參與者失敗: {e}")
            return []

    async def select_winners(self, lottery_id: int, winners: List[Tuple[int, str, int]]) -> bool:
        """選出中獎者"""
        try:
            async with self.db.connection() as conn:
                async with conn.cursor() as cursor:
                    # 獲取抽獎資料
                    lottery_query = "SELECT prize_data FROM lotteries WHERE id = %s"
                    await cursor.execute(lottery_query, (lottery_id,))
                    lottery_result = await cursor.fetchone()
                    
                    if not lottery_result:
                        return False
                    
                    prize_data = lottery_result[0]
                    
                    # 插入中獎者
                    winners_query = """
                    INSERT INTO lottery_winners (lottery_id, user_id, username, prize_data, win_position)
                    VALUES (%s, %s, %s, %s, %s)
                    """
                    
                    for user_id, username, position in winners:
                        await cursor.execute(winners_query, (
                            lottery_id, user_id, username, prize_data, position
                        ))
                    
                    # 更新抽獎狀態
                    update_query = "UPDATE lotteries SET status = 'ended' WHERE id = %s"
                    await cursor.execute(update_query, (lottery_id,))
                    
                    await conn.commit()
                    return True
                    
        except Exception as e:
            logger.error(f"選出中獎者失敗: {e}")
            return False

    async def get_winners(self, lottery_id: int) -> List[Dict]:
        """獲取中獎者列表"""
        try:
            async with self.db.connection() as conn:
                async with conn.cursor(aiomysql.DictCursor) as cursor:
                    query = """
                    SELECT * FROM lottery_winners 
                    WHERE lottery_id = %s
                    ORDER BY win_position ASC
                    """
                    await cursor.execute(query, (lottery_id,))
                    results = await cursor.fetchall()
                    
                    # 解析JSON欄位
                    for result in results:
                        if result['prize_data']:
                            result['prize_data'] = json.loads(result['prize_data'])
                    
                    return results
                    
        except Exception as e:
            logger.error(f"獲取中獎者失敗: {e}")
            return []

    async def update_lottery_status(self, lottery_id: int, status: str, message_id: Optional[int] = None) -> bool:
        """更新抽獎狀態"""
        try:
            async with self.db.connection() as conn:
                async with conn.cursor() as cursor:
                    if message_id:
                        query = "UPDATE lotteries SET status = %s, message_id = %s WHERE id = %s"
                        await cursor.execute(query, (status, message_id, lottery_id))
                    else:
                        query = "UPDATE lotteries SET status = %s WHERE id = %s"
                        await cursor.execute(query, (status, lottery_id))
                    
                    await conn.commit()
                    return cursor.rowcount > 0
                    
        except Exception as e:
            logger.error(f"更新抽獎狀態失敗: {e}")
            return False

    async def get_lottery_settings(self, guild_id: int) -> Dict[str, Any]:
        """獲取抽獎設定"""
        try:
            async with self.db.connection() as conn:
                async with conn.cursor(aiomysql.DictCursor) as cursor:
                    query = "SELECT * FROM lottery_settings WHERE guild_id = %s"
                    await cursor.execute(query, (guild_id,))
                    result = await cursor.fetchone()
                    
                    if result:
                        # 解析JSON欄位
                        if result['admin_roles']:
                            result['admin_roles'] = json.loads(result['admin_roles'])
                        return result
                    else:
                        # 返回預設設定
                        return {
                            'guild_id': guild_id,
                            'default_duration_hours': 24,
                            'max_concurrent_lotteries': 3,
                            'allow_self_entry': True,
                            'require_boost': False,
                            'log_channel_id': None,
                            'announcement_channel_id': None,
                            'admin_roles': []
                        }
                        
        except Exception as e:
            logger.error(f"獲取抽獎設定失敗: {e}")
            return {}

    async def update_lottery_settings(self, guild_id: int, settings: Dict[str, Any]) -> bool:
        """更新抽獎設定"""
        try:
            async with self.db.connection() as conn:
                async with conn.cursor() as cursor:
                    query = """
                    INSERT INTO lottery_settings (
                        guild_id, default_duration_hours, max_concurrent_lotteries,
                        allow_self_entry, require_boost, log_channel_id,
                        announcement_channel_id, admin_roles
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    ON DUPLICATE KEY UPDATE
                        default_duration_hours = VALUES(default_duration_hours),
                        max_concurrent_lotteries = VALUES(max_concurrent_lotteries),
                        allow_self_entry = VALUES(allow_self_entry),
                        require_boost = VALUES(require_boost),
                        log_channel_id = VALUES(log_channel_id),
                        announcement_channel_id = VALUES(announcement_channel_id),
                        admin_roles = VALUES(admin_roles),
                        updated_at = CURRENT_TIMESTAMP
                    """
                    
                    await cursor.execute(query, (
                        guild_id,
                        settings.get('default_duration_hours', 24),
                        settings.get('max_concurrent_lotteries', 3),
                        settings.get('allow_self_entry', True),
                        settings.get('require_boost', False),
                        settings.get('log_channel_id'),
                        settings.get('announcement_channel_id'),
                        json.dumps(settings.get('admin_roles', []))
                    ))
                    
                    await conn.commit()
                    return True
                    
        except Exception as e:
            logger.error(f"更新抽獎設定失敗: {e}")
            return False

    async def cleanup_expired_lotteries(self) -> int:
        """清理過期抽獎"""
        try:
            async with self.db.connection() as conn:
                async with conn.cursor() as cursor:
                    # 自動結束過期的活躍抽獎
                    query = """
                    UPDATE lotteries 
                    SET status = 'ended' 
                    WHERE status = 'active' 
                    AND end_time <= NOW() 
                    AND auto_end = TRUE
                    """
                    
                    await cursor.execute(query)
                    updated_count = cursor.rowcount
                    await conn.commit()
                    
                    if updated_count > 0:
                        logger.info(f"自動結束了 {updated_count} 個過期抽獎")
                    
                    return updated_count
                    
        except Exception as e:
            logger.error(f"清理過期抽獎失敗: {e}")
            return 0

    async def get_lottery_statistics(self, guild_id: int, days: int = 30) -> Dict[str, Any]:
        """獲取抽獎統計"""
        try:
            async with self.db.connection() as conn:
                async with conn.cursor(aiomysql.DictCursor) as cursor:
                    start_date = datetime.now() - timedelta(days=days)
                    
                    # 基本統計
                    stats_query = """
                    SELECT 
                        COUNT(*) as total_lotteries,
                        COUNT(CASE WHEN status = 'active' THEN 1 END) as active_lotteries,
                        COUNT(CASE WHEN status = 'ended' THEN 1 END) as completed_lotteries,
                        COUNT(CASE WHEN status = 'cancelled' THEN 1 END) as cancelled_lotteries,
                        AVG(winner_count) as avg_winners_per_lottery
                    FROM lotteries
                    WHERE guild_id = %s AND created_at >= %s
                    """
                    
                    await cursor.execute(stats_query, (guild_id, start_date))
                    basic_stats = await cursor.fetchone()
                    
                    # 參與者統計
                    participation_query = """
                    SELECT 
                        COUNT(DISTINCT le.user_id) as unique_participants,
                        COUNT(le.id) as total_entries,
                        AVG(entry_count) as avg_entries_per_lottery
                    FROM lottery_entries le
                    JOIN lotteries l ON le.lottery_id = l.id
                    LEFT JOIN (
                        SELECT lottery_id, COUNT(*) as entry_count
                        FROM lottery_entries
                        GROUP BY lottery_id
                    ) ec ON l.id = ec.lottery_id
                    WHERE l.guild_id = %s AND l.created_at >= %s
                    """
                    
                    await cursor.execute(participation_query, (guild_id, start_date))
                    participation_stats = await cursor.fetchone()
                    
                    return {
                        'period': f'最近 {days} 天',
                        'basic_stats': basic_stats or {},
                        'participation_stats': participation_stats or {},
                        'generated_at': datetime.now().isoformat()
                    }
                    
        except Exception as e:
            logger.error(f"獲取抽獎統計失敗: {e}")
            return {}