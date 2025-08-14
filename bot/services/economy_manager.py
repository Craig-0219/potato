# bot/services/economy_manager.py - 虛擬經濟系統管理器
"""
虛擬經濟系統管理器 v2.2.0
管理用戶的虛擬貨幣、經驗值、等級系統等
"""

import asyncio
import math
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timezone, timedelta
from dataclasses import dataclass

from bot.db.pool import db_pool
from shared.cache_manager import cache_manager, cached
from shared.logger import logger

@dataclass
class UserEconomy:
    """用戶經濟數據"""
    user_id: int
    guild_id: int
    coins: int = 0
    gems: int = 0
    tickets: int = 0
    experience: int = 0
    total_games: int = 0
    total_wins: int = 0
    daily_games: int = 0
    daily_wins: int = 0
    daily_claimed: bool = False
    last_checkin: Optional[datetime] = None
    last_daily_reset: Optional[datetime] = None

class EconomyManager:
    """經濟系統管理器"""
    
    def __init__(self):
        # 等級經驗配置
        self.base_exp = 1000  # 基礎升級經驗
        self.exp_multiplier = 1.5  # 經驗倍數
        self.max_level = 100  # 最大等級
        
        # 每日限制
        self.daily_game_limit = 20
        self.daily_checkin_bonus_max = 500
        
        logger.info("💰 經濟系統管理器初始化完成")

    # ========== 用戶經濟數據管理 ==========

    async def get_user_economy(self, user_id: int, guild_id: int) -> Dict[str, Any]:
        """獲取用戶經濟數據"""
        try:
            # 嘗試從快取獲取
            cache_key = f"user_economy:{user_id}:{guild_id}"
            cached_data = await cache_manager.get(cache_key)
            
            if cached_data:
                return cached_data
            
            # 從資料庫獲取
            async with db_pool.connection() as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute("""
                        SELECT 
                            coins, gems, tickets, experience,
                            total_games, total_wins, daily_games, daily_wins,
                            daily_claimed, last_checkin, last_daily_reset
                        FROM user_economy 
                        WHERE user_id = %s AND guild_id = %s
                    """, (user_id, guild_id))
                    
                    result = await cursor.fetchone()
                    
                    if result:
                        (coins, gems, tickets, experience, total_games, total_wins,
                         daily_games, daily_wins, daily_claimed, last_checkin, 
                         last_daily_reset) = result
                         
                        # 檢查是否需要重置每日數據
                        should_reset = await self._should_reset_daily(last_daily_reset)
                        
                        economy_data = {
                            "coins": coins,
                            "gems": gems,
                            "tickets": tickets,
                            "experience": experience,
                            "total_games": total_games,
                            "total_wins": total_wins,
                            "daily_games": 0 if should_reset else daily_games,
                            "daily_wins": 0 if should_reset else daily_wins,
                            "daily_claimed": False if should_reset else daily_claimed,
                            "last_checkin": last_checkin,
                            "win_rate": (total_wins / total_games * 100) if total_games > 0 else 0
                        }
                        
                        # 如果需要重置，更新資料庫
                        if should_reset:
                            await self._reset_daily_data(user_id, guild_id)
                    else:
                        # 創建新用戶
                        await self._create_user_economy(user_id, guild_id)
                        economy_data = {
                            "coins": 100,  # 新用戶獎勵
                            "gems": 10,
                            "tickets": 5,
                            "experience": 0,
                            "total_games": 0,
                            "total_wins": 0,
                            "daily_games": 0,
                            "daily_wins": 0,
                            "daily_claimed": False,
                            "last_checkin": None,
                            "win_rate": 0.0
                        }
                    
                    # 快取數據
                    await cache_manager.set(cache_key, economy_data, 300)  # 5分鐘快取
                    
                    return economy_data
                    
        except Exception as e:
            logger.error(f"❌ 獲取用戶經濟數據失敗: {e}")
            return {}

    async def _create_user_economy(self, user_id: int, guild_id: int):
        """創建新用戶經濟數據"""
        try:
            async with db_pool.connection() as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute("""
                        INSERT INTO user_economy 
                        (user_id, guild_id, coins, gems, tickets, experience)
                        VALUES (%s, %s, %s, %s, %s, %s)
                        ON DUPLICATE KEY UPDATE
                        coins = coins  -- 如果已存在則不更新
                    """, (user_id, guild_id, 100, 10, 5, 0))
                    await conn.commit()
                    
        except Exception as e:
            logger.error(f"❌ 創建用戶經濟數據失敗: {e}")

    async def _should_reset_daily(self, last_reset: Optional[datetime]) -> bool:
        """檢查是否需要重置每日數據"""
        if last_reset is None:
            return True
        
        today = datetime.now(timezone.utc).date()
        last_reset_date = last_reset.date() if isinstance(last_reset, datetime) else last_reset
        
        return today > last_reset_date

    async def _reset_daily_data(self, user_id: int, guild_id: int):
        """重置每日數據"""
        try:
            async with db_pool.connection() as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute("""
                        UPDATE user_economy 
                        SET daily_games = 0, daily_wins = 0, daily_claimed = FALSE,
                            last_daily_reset = CURDATE()
                        WHERE user_id = %s AND guild_id = %s
                    """, (user_id, guild_id))
                    await conn.commit()
                    
            # 清理快取
            cache_key = f"user_economy:{user_id}:{guild_id}"
            await cache_manager.delete(cache_key)
            
        except Exception as e:
            logger.error(f"❌ 重置每日數據失敗: {e}")

    # ========== 貨幣操作 ==========

    async def add_coins(self, user_id: int, guild_id: int, amount: int) -> bool:
        """增加金幣"""
        try:
            async with db_pool.connection() as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute("""
                        UPDATE user_economy 
                        SET coins = coins + %s
                        WHERE user_id = %s AND guild_id = %s
                    """, (amount, user_id, guild_id))
                    
                    if cursor.rowcount == 0:
                        # 用戶不存在，先創建
                        await self._create_user_economy(user_id, guild_id)
                        await cursor.execute("""
                            UPDATE user_economy 
                            SET coins = coins + %s
                            WHERE user_id = %s AND guild_id = %s
                        """, (amount, user_id, guild_id))
                    
                    await conn.commit()
                    
                    # 清理快取
                    cache_key = f"user_economy:{user_id}:{guild_id}"
                    await cache_manager.delete(cache_key)
                    
                    return True
                    
        except Exception as e:
            logger.error(f"❌ 增加金幣失敗: {e}")
            return False

    async def subtract_coins(self, user_id: int, guild_id: int, amount: int) -> bool:
        """扣除金幣"""
        try:
            # 先檢查餘額
            economy = await self.get_user_economy(user_id, guild_id)
            if economy.get("coins", 0) < amount:
                return False
            
            return await self.add_coins(user_id, guild_id, -amount)
            
        except Exception as e:
            logger.error(f"❌ 扣除金幣失敗: {e}")
            return False

    async def add_gems(self, user_id: int, guild_id: int, amount: int) -> bool:
        """增加寶石"""
        try:
            async with db_pool.connection() as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute("""
                        UPDATE user_economy 
                        SET gems = gems + %s
                        WHERE user_id = %s AND guild_id = %s
                    """, (amount, user_id, guild_id))
                    
                    if cursor.rowcount == 0:
                        await self._create_user_economy(user_id, guild_id)
                        await cursor.execute("""
                            UPDATE user_economy 
                            SET gems = gems + %s
                            WHERE user_id = %s AND guild_id = %s
                        """, (amount, user_id, guild_id))
                    
                    await conn.commit()
                    
                    # 清理快取
                    cache_key = f"user_economy:{user_id}:{guild_id}"
                    await cache_manager.delete(cache_key)
                    
                    return True
                    
        except Exception as e:
            logger.error(f"❌ 增加寶石失敗: {e}")
            return False

    async def add_experience(self, user_id: int, guild_id: int, amount: int) -> Dict[str, Any]:
        """增加經驗值並檢查升級"""
        try:
            # 獲取當前經驗
            economy = await self.get_user_economy(user_id, guild_id)
            old_exp = economy.get("experience", 0)
            new_exp = old_exp + amount
            
            # 計算舊等級和新等級
            old_level_info = await self.calculate_level(old_exp)
            new_level_info = await self.calculate_level(new_exp)
            
            # 更新經驗值
            async with db_pool.connection() as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute("""
                        UPDATE user_economy 
                        SET experience = %s
                        WHERE user_id = %s AND guild_id = %s
                    """, (new_exp, user_id, guild_id))
                    await conn.commit()
            
            # 清理快取
            cache_key = f"user_economy:{user_id}:{guild_id}"
            await cache_manager.delete(cache_key)
            
            # 檢查是否升級
            leveled_up = new_level_info["level"] > old_level_info["level"]
            
            result = {
                "old_exp": old_exp,
                "new_exp": new_exp,
                "gained_exp": amount,
                "old_level": old_level_info["level"],
                "new_level": new_level_info["level"],
                "leveled_up": leveled_up,
                "level_info": new_level_info
            }
            
            # 如果升級了，給予升級獎勵
            if leveled_up:
                level_reward = new_level_info["level"] * 50  # 每級50金幣獎勵
                await self.add_coins(user_id, guild_id, level_reward)
                result["level_reward"] = level_reward
            
            return result
            
        except Exception as e:
            logger.error(f"❌ 增加經驗值失敗: {e}")
            return {}

    async def calculate_level(self, experience: int) -> Dict[str, Any]:
        """計算等級資訊"""
        try:
            if experience < 0:
                experience = 0
                
            # 計算等級 (使用指數增長公式)
            level = 1
            required_exp = 0
            
            while level < self.max_level:
                level_exp_requirement = int(self.base_exp * (self.exp_multiplier ** (level - 1)))
                if required_exp + level_exp_requirement > experience:
                    break
                required_exp += level_exp_requirement
                level += 1
            
            # 計算到下一級需要的經驗
            if level < self.max_level:
                next_level_exp_requirement = int(self.base_exp * (self.exp_multiplier ** (level - 1)))
                current_level_progress = experience - required_exp
                next_level_exp = next_level_exp_requirement - current_level_progress
            else:
                next_level_exp_requirement = 0
                current_level_progress = 0
                next_level_exp = 0
            
            return {
                "level": level,
                "experience": experience,
                "current_level_exp": current_level_progress,
                "current_level_required": next_level_exp_requirement,
                "next_level_exp": next_level_exp,
                "progress_percentage": (current_level_progress / next_level_exp_requirement * 100) if next_level_exp_requirement > 0 else 100
            }
            
        except Exception as e:
            logger.error(f"❌ 計算等級失敗: {e}")
            return {"level": 1, "experience": 0}

    # ========== 每日系統 ==========

    async def record_checkin(self, user_id: int, guild_id: int):
        """記錄每日簽到"""
        try:
            async with db_pool.connection() as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute("""
                        UPDATE user_economy 
                        SET daily_claimed = TRUE, last_checkin = NOW()
                        WHERE user_id = %s AND guild_id = %s
                    """, (user_id, guild_id))
                    await conn.commit()
                    
            # 清理快取
            cache_key = f"user_economy:{user_id}:{guild_id}"
            await cache_manager.delete(cache_key)
            
        except Exception as e:
            logger.error(f"❌ 記錄簽到失敗: {e}")

    async def get_last_checkin(self, user_id: int, guild_id: int) -> Optional[datetime]:
        """獲取最後簽到時間"""
        try:
            economy = await self.get_user_economy(user_id, guild_id)
            return economy.get("last_checkin")
            
        except Exception as e:
            logger.error(f"❌ 獲取簽到時間失敗: {e}")
            return None

    async def calculate_checkin_streak(self, user_id: int, guild_id: int) -> int:
        """計算連續簽到天數"""
        try:
            async with db_pool.connection() as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute("""
                        SELECT last_checkin FROM user_economy 
                        WHERE user_id = %s AND guild_id = %s
                    """, (user_id, guild_id))
                    
                    result = await cursor.fetchone()
                    
                    if not result or not result[0]:
                        return 1  # 第一次簽到
                    
                    last_checkin = result[0]
                    today = datetime.now(timezone.utc).date()
                    last_date = last_checkin.date()
                    
                    # 計算連續天數
                    days_diff = (today - last_date).days
                    
                    if days_diff == 1:
                        # 連續簽到，查詢歷史記錄計算完整連續天數
                        # 這裡簡化處理，返回基於一定邏輯的連續天數
                        return await self._calculate_full_streak(user_id, guild_id)
                    elif days_diff == 0:
                        # 今天已經簽到過
                        return await self._calculate_full_streak(user_id, guild_id)
                    else:
                        # 中斷了，重新開始
                        return 1
                    
        except Exception as e:
            logger.error(f"❌ 計算簽到連續天數失敗: {e}")
            return 1

    async def _calculate_full_streak(self, user_id: int, guild_id: int) -> int:
        """計算完整的連續簽到天數（簡化版本）"""
        try:
            # 這裡可以實現更複雜的連續天數計算邏輯
            # 暫時返回基於最後簽到時間的簡單計算
            async with db_pool.connection() as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute("""
                        SELECT DATEDIFF(CURDATE(), DATE(last_checkin)) + 1 as streak
                        FROM user_economy 
                        WHERE user_id = %s AND guild_id = %s
                    """, (user_id, guild_id))
                    
                    result = await cursor.fetchone()
                    return min(result[0] if result else 1, 30)  # 最多30天連續
                    
        except Exception as e:
            logger.error(f"❌ 計算完整連續天數失敗: {e}")
            return 1

    async def get_total_checkins(self, user_id: int, guild_id: int) -> int:
        """獲取總簽到天數（簡化實現）"""
        try:
            # 這裡可以實現一個專門的簽到記錄表
            # 暫時基於創建時間估算
            async with db_pool.connection() as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute("""
                        SELECT DATEDIFF(CURDATE(), DATE(created_at)) as total_days
                        FROM user_economy 
                        WHERE user_id = %s AND guild_id = %s
                    """, (user_id, guild_id))
                    
                    result = await cursor.fetchone()
                    total_days = result[0] if result else 0
                    
                    # 假設70%的天數有簽到
                    return int(total_days * 0.7)
                    
        except Exception as e:
            logger.error(f"❌ 獲取總簽到天數失敗: {e}")
            return 0

    # ========== 遊戲統計 ==========

    async def increment_daily_games(self, user_id: int, guild_id: int):
        """增加每日遊戲次數"""
        try:
            async with db_pool.connection() as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute("""
                        UPDATE user_economy 
                        SET daily_games = daily_games + 1, total_games = total_games + 1
                        WHERE user_id = %s AND guild_id = %s
                    """, (user_id, guild_id))
                    await conn.commit()
                    
            # 清理快取
            cache_key = f"user_economy:{user_id}:{guild_id}"
            await cache_manager.delete(cache_key)
            
        except Exception as e:
            logger.error(f"❌ 增加遊戲次數失敗: {e}")

    async def increment_daily_wins(self, user_id: int, guild_id: int):
        """增加每日勝利次數"""
        try:
            async with db_pool.connection() as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute("""
                        UPDATE user_economy 
                        SET daily_wins = daily_wins + 1, total_wins = total_wins + 1
                        WHERE user_id = %s AND guild_id = %s
                    """, (user_id, guild_id))
                    await conn.commit()
                    
            # 清理快取
            cache_key = f"user_economy:{user_id}:{guild_id}"
            await cache_manager.delete(cache_key)
            
        except Exception as e:
            logger.error(f"❌ 增加勝利次數失敗: {e}")

    # ========== 排行榜系統 ==========

    async def get_leaderboard(self, guild_id: int, metric: str, limit: int = 10) -> List[Dict[str, Any]]:
        """獲取排行榜"""
        try:
            cache_key = f"economy_leaderboard:{guild_id}:{metric}:{limit}"
            cached_result = await cache_manager.get(cache_key)
            
            if cached_result:
                return cached_result
            
            # 根據指標選擇排序欄位
            order_by_map = {
                "coins": "coins DESC",
                "gems": "gems DESC",
                "experience": "experience DESC",
                "wins": "total_wins DESC",
                "games": "total_games DESC"
            }
            
            order_by = order_by_map.get(metric, "coins DESC")
            
            async with db_pool.connection() as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute(f"""
                        SELECT 
                            user_id, coins, gems, tickets, experience,
                            total_games, total_wins,
                            (total_wins / GREATEST(total_games, 1) * 100) as win_rate
                        FROM user_economy 
                        WHERE guild_id = %s
                        ORDER BY {order_by}
                        LIMIT %s
                    """, (guild_id, limit))
                    
                    results = await cursor.fetchall()
                    
                    leaderboard = []
                    for row in results:
                        (user_id, coins, gems, tickets, experience, 
                         total_games, total_wins, win_rate) = row
                        
                        leaderboard.append({
                            "user_id": user_id,
                            "coins": coins,
                            "gems": gems,
                            "tickets": tickets,
                            "experience": experience,
                            "total_games": total_games,
                            "total_wins": total_wins,
                            "win_rate": float(win_rate)
                        })
                    
                    # 快取結果
                    await cache_manager.set(cache_key, leaderboard, 300)  # 5分鐘快取
                    
                    return leaderboard
                    
        except Exception as e:
            logger.error(f"❌ 獲取排行榜失敗: {e}")
            return []

    async def get_user_rank(self, user_id: int, guild_id: int, metric: str) -> int:
        """獲取用戶排名"""
        try:
            order_by_map = {
                "coins": "coins DESC",
                "gems": "gems DESC",
                "experience": "experience DESC",
                "wins": "total_wins DESC",
                "games": "total_games DESC"
            }
            
            order_by = order_by_map.get(metric, "coins DESC")
            
            async with db_pool.connection() as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute(f"""
                        SELECT COUNT(*) + 1 as rank
                        FROM user_economy u1, user_economy u2
                        WHERE u1.user_id = %s AND u1.guild_id = %s
                        AND u2.guild_id = %s
                        AND (
                            CASE WHEN %s = 'coins' THEN u2.coins > u1.coins
                                 WHEN %s = 'gems' THEN u2.gems > u1.gems
                                 WHEN %s = 'experience' THEN u2.experience > u1.experience
                                 WHEN %s = 'wins' THEN u2.total_wins > u1.total_wins
                                 WHEN %s = 'games' THEN u2.total_games > u1.total_games
                                 ELSE u2.coins > u1.coins
                            END
                        )
                    """, (user_id, guild_id, guild_id, metric, metric, metric, metric, metric))
                    
                    result = await cursor.fetchone()
                    return result[0] if result else 1
                    
        except Exception as e:
            logger.error(f"❌ 獲取用戶排名失敗: {e}")
            return 1

    # ========== 系統維護 ==========

    async def reset_daily_stats(self):
        """重置所有用戶的每日統計"""
        try:
            async with db_pool.connection() as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute("""
                        UPDATE user_economy 
                        SET daily_games = 0, daily_wins = 0, daily_claimed = FALSE,
                            last_daily_reset = CURDATE()
                        WHERE last_daily_reset < CURDATE() OR last_daily_reset IS NULL
                    """)
                    affected_rows = cursor.rowcount
                    await conn.commit()
                    
            # 清理所有經濟快取
            await cache_manager.clear_all("user_economy:*")
            await cache_manager.clear_all("economy_leaderboard:*")
            
            logger.info(f"✅ 重置每日統計完成，影響 {affected_rows} 位用戶")
            
        except Exception as e:
            logger.error(f"❌ 重置每日統計失敗: {e}")

    async def cleanup_inactive_users(self, days: int = 30):
        """清理不活躍用戶（可選）"""
        try:
            async with db_pool.connection() as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute("""
                        DELETE FROM user_economy 
                        WHERE last_checkin < DATE_SUB(NOW(), INTERVAL %s DAY)
                        AND total_games = 0
                        AND coins < 100
                    """, (days,))
                    
                    affected_rows = cursor.rowcount
                    await conn.commit()
                    
            logger.info(f"✅ 清理不活躍用戶完成，清理 {affected_rows} 位用戶")
            
        except Exception as e:
            logger.error(f"❌ 清理不活躍用戶失敗: {e}")

    async def get_economy_stats(self, guild_id: int) -> Dict[str, Any]:
        """獲取經濟系統統計"""
        try:
            async with db_pool.connection() as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute("""
                        SELECT 
                            COUNT(*) as total_users,
                            SUM(coins) as total_coins,
                            SUM(gems) as total_gems,
                            SUM(total_games) as total_games,
                            SUM(total_wins) as total_wins,
                            AVG(coins) as avg_coins,
                            MAX(coins) as max_coins,
                            COUNT(CASE WHEN daily_claimed = TRUE THEN 1 END) as daily_checkins
                        FROM user_economy 
                        WHERE guild_id = %s
                    """, (guild_id,))
                    
                    result = await cursor.fetchone()
                    
                    if result:
                        (total_users, total_coins, total_gems, total_games, total_wins,
                         avg_coins, max_coins, daily_checkins) = result
                        
                        return {
                            "total_users": total_users or 0,
                            "total_coins": total_coins or 0,
                            "total_gems": total_gems or 0,
                            "total_games": total_games or 0,
                            "total_wins": total_wins or 0,
                            "avg_coins": float(avg_coins) if avg_coins else 0,
                            "max_coins": max_coins or 0,
                            "daily_checkins": daily_checkins or 0,
                            "win_rate": (total_wins / total_games * 100) if total_games > 0 else 0
                        }
                    
                    return {}
                    
        except Exception as e:
            logger.error(f"❌ 獲取經濟統計失敗: {e}")
            return {}