# bot/services/economy_manager.py - 跨平台經濟系統管理器
"""
跨平台經濟系統管理器 v3.0.0 - Phase 5 Stage 4
管理用戶的虛擬貨幣、經驗值、等級系統等，支援 Discord-Minecraft 跨平台同步
整合抗通膨機制、動態平衡、風險控制等高級功能
"""

import asyncio
import base64
import hashlib
import hmac
import json
import secrets
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

import aiohttp

from bot.db.pool import db_pool
from shared.cache_manager import cache_manager
from shared.logger import logger

# ========== 新增：跨平台經濟系統枚舉 ==========


class CurrencyType(Enum):
    """貨幣類型"""

    COINS = "coins"  # 金幣 - 日常交易
    GEMS = "gems"  # 寶石 - 高價值商品
    TICKETS = "tickets"  # 票券 - 特殊功能
    EXPERIENCE = "experience"  # 經驗值 - 技能升級


class TransactionType(Enum):
    """交易類型"""

    EARN = "earn"  # 獲得
    SPEND = "spend"  # 消費
    TRANSFER = "transfer"  # 轉帳
    SYNC = "sync"  # 同步調整
    PENALTY = "penalty"  # 懲罰扣除
    BONUS = "bonus"  # 獎勵加成


class EconomyAction(Enum):
    """經濟活動類型"""

    DAILY_ACTIVITY = "daily_activity"
    MESSAGE_SEND = "message_send"
    VOICE_PARTICIPATION = "voice_participation"
    TASK_COMPLETION = "task_completion"
    ACHIEVEMENT_UNLOCK = "achievement_unlock"
    SPECIAL_EVENT = "special_event"
    CROSS_PLATFORM_SYNC = "cross_platform_sync"
    MINECRAFT_ACTIVITY = "minecraft_activity"


@dataclass
class CrossPlatformTransaction:
    """跨平台交易記錄"""

    transaction_id: str
    user_id: int
    guild_id: int
    currency_type: CurrencyType
    transaction_type: TransactionType
    amount: int
    balance_before: int
    balance_after: int
    description: str
    source_platform: str  # "discord" 或 "minecraft"
    timestamp: datetime
    minecraft_server_id: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class EconomySettings:
    """經濟系統設定"""

    guild_id: int

    # 日常獲得上限
    daily_coins_base: int = 50
    daily_coins_max: int = 500
    daily_gems_base: int = 5
    daily_gems_max: int = 20

    # 活動獎勵倍率
    message_coins: int = 2
    voice_coins_per_minute: int = 5
    task_completion_multiplier: float = 1.5

    # 通膨控制參數
    inflation_threshold: float = 0.03  # 3% 通膨閾值
    deflation_enabled: bool = True
    market_adjustment_interval: int = 86400  # 24小時

    # 跨平台同步設定
    sync_enabled: bool = False
    minecraft_api_endpoint: Optional[str] = None
    minecraft_server_key: Optional[str] = None
    sync_interval: int = 300  # 5分鐘

    last_updated: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


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

        # 新增：跨平台同步相關
        self._cross_platform_transactions: List[CrossPlatformTransaction] = []
        self._economy_settings: Dict[int, EconomySettings] = {}
        self._daily_limits: Dict[str, Dict[CurrencyType, int]] = {}
        self._inflation_data: Dict[int, Dict[str, float]] = {}
        self._sync_tasks: Dict[int, asyncio.Task] = {}
        self._last_sync_time: Dict[int, datetime] = {}

        logger.info("💰 跨平台經濟系統管理器初始化完成 v3.0.0")

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
                    await cursor.execute(
                        """
                        SELECT
                            coins, gems, tickets, experience,
                            total_games, total_wins, daily_games, daily_wins,
                            daily_claimed, last_checkin, last_daily_reset
                        FROM user_economy
                        WHERE user_id = %s AND guild_id = %s
                    """,
                        (user_id, guild_id),
                    )

                    result = await cursor.fetchone()

                    if result:
                        (
                            coins,
                            gems,
                            tickets,
                            experience,
                            total_games,
                            total_wins,
                            daily_games,
                            daily_wins,
                            daily_claimed,
                            last_checkin,
                            last_daily_reset,
                        ) = result

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
                            "win_rate": (total_wins / total_games * 100) if total_games > 0 else 0,
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
                            "win_rate": 0.0,
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
                    await cursor.execute(
                        """
                        INSERT INTO user_economy
                        (user_id, guild_id, coins, gems, tickets, experience)
                        VALUES (%s, %s, %s, %s, %s, %s)
                        ON DUPLICATE KEY UPDATE
                        coins = coins  -- 如果已存在則不更新
                    """,
                        (user_id, guild_id, 100, 10, 5, 0),
                    )
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
                    await cursor.execute(
                        """
                        UPDATE user_economy
                        SET daily_games = 0, daily_wins = 0, daily_claimed = FALSE,
                            last_daily_reset = CURDATE()
                        WHERE user_id = %s AND guild_id = %s
                    """,
                        (user_id, guild_id),
                    )
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
                    await cursor.execute(
                        """
                        UPDATE user_economy
                        SET coins = coins + %s
                        WHERE user_id = %s AND guild_id = %s
                    """,
                        (amount, user_id, guild_id),
                    )

                    if cursor.rowcount == 0:
                        # 用戶不存在，先創建
                        await self._create_user_economy(user_id, guild_id)
                        await cursor.execute(
                            """
                            UPDATE user_economy
                            SET coins = coins + %s
                            WHERE user_id = %s AND guild_id = %s
                        """,
                            (amount, user_id, guild_id),
                        )

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
                    await cursor.execute(
                        """
                        UPDATE user_economy
                        SET gems = gems + %s
                        WHERE user_id = %s AND guild_id = %s
                    """,
                        (amount, user_id, guild_id),
                    )

                    if cursor.rowcount == 0:
                        await self._create_user_economy(user_id, guild_id)
                        await cursor.execute(
                            """
                            UPDATE user_economy
                            SET gems = gems + %s
                            WHERE user_id = %s AND guild_id = %s
                        """,
                            (amount, user_id, guild_id),
                        )

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
                    await cursor.execute(
                        """
                        UPDATE user_economy
                        SET experience = %s
                        WHERE user_id = %s AND guild_id = %s
                    """,
                        (new_exp, user_id, guild_id),
                    )
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
                "level_info": new_level_info,
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
                next_level_exp_requirement = int(
                    self.base_exp * (self.exp_multiplier ** (level - 1))
                )
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
                "progress_percentage": (
                    (current_level_progress / next_level_exp_requirement * 100)
                    if next_level_exp_requirement > 0
                    else 100
                ),
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
                    await cursor.execute(
                        """
                        UPDATE user_economy
                        SET daily_claimed = TRUE, last_checkin = NOW()
                        WHERE user_id = %s AND guild_id = %s
                    """,
                        (user_id, guild_id),
                    )
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
                    await cursor.execute(
                        """
                        SELECT last_checkin FROM user_economy
                        WHERE user_id = %s AND guild_id = %s
                    """,
                        (user_id, guild_id),
                    )

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
                    await cursor.execute(
                        """
                        SELECT DATEDIFF(CURDATE(), DATE(last_checkin)) + 1 as streak
                        FROM user_economy
                        WHERE user_id = %s AND guild_id = %s
                    """,
                        (user_id, guild_id),
                    )

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
                    await cursor.execute(
                        """
                        SELECT DATEDIFF(CURDATE(), DATE(created_at)) as total_days
                        FROM user_economy
                        WHERE user_id = %s AND guild_id = %s
                    """,
                        (user_id, guild_id),
                    )

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
                    await cursor.execute(
                        """
                        UPDATE user_economy
                        SET daily_games = daily_games + 1, total_games = total_games + 1
                        WHERE user_id = %s AND guild_id = %s
                    """,
                        (user_id, guild_id),
                    )
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
                    await cursor.execute(
                        """
                        UPDATE user_economy
                        SET daily_wins = daily_wins + 1, total_wins = total_wins + 1
                        WHERE user_id = %s AND guild_id = %s
                    """,
                        (user_id, guild_id),
                    )
                    await conn.commit()

            # 清理快取
            cache_key = f"user_economy:{user_id}:{guild_id}"
            await cache_manager.delete(cache_key)

        except Exception as e:
            logger.error(f"❌ 增加勝利次數失敗: {e}")

    # ========== 排行榜系統 ==========

    async def get_leaderboard(
        self, guild_id: int, metric: str, limit: int = 10
    ) -> List[Dict[str, Any]]:
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
                "games": "total_games DESC",
            }

            order_by = order_by_map.get(metric, "coins DESC")

            async with db_pool.connection() as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute(
                        f"""
                        SELECT
                            user_id, coins, gems, tickets, experience,
                            total_games, total_wins,
                            (total_wins / GREATEST(total_games, 1) * 100) as win_rate
                        FROM user_economy
                        WHERE guild_id = %s
                        ORDER BY {order_by}
                        LIMIT %s
                    """,
                        (guild_id, limit),
                    )

                    results = await cursor.fetchall()

                    leaderboard = []
                    for row in results:
                        (
                            user_id,
                            coins,
                            gems,
                            tickets,
                            experience,
                            total_games,
                            total_wins,
                            win_rate,
                        ) = row

                        leaderboard.append(
                            {
                                "user_id": user_id,
                                "coins": coins,
                                "gems": gems,
                                "tickets": tickets,
                                "experience": experience,
                                "total_games": total_games,
                                "total_wins": total_wins,
                                "win_rate": float(win_rate),
                            }
                        )

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
                "games": "total_games DESC",
            }

            order_by_map.get(metric, "coins DESC")

            async with db_pool.connection() as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute(
                        f"""
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
                    """,
                        (user_id, guild_id, guild_id, metric, metric, metric, metric, metric),
                    )

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
                    await cursor.execute(
                        """
                        UPDATE user_economy
                        SET daily_games = 0, daily_wins = 0, daily_claimed = FALSE,
                            last_daily_reset = CURDATE()
                        WHERE last_daily_reset < CURDATE() OR last_daily_reset IS NULL
                    """
                    )
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
                    await cursor.execute(
                        """
                        DELETE FROM user_economy
                        WHERE last_checkin < DATE_SUB(NOW(), INTERVAL %s DAY)
                        AND total_games = 0
                        AND coins < 100
                    """,
                        (days,),
                    )

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
                    await cursor.execute(
                        """
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
                    """,
                        (guild_id,),
                    )

                    result = await cursor.fetchone()

                    if result:
                        (
                            total_users,
                            total_coins,
                            total_gems,
                            total_games,
                            total_wins,
                            avg_coins,
                            max_coins,
                            daily_checkins,
                        ) = result

                        safe_total_games = total_games or 0
                        safe_total_wins = total_wins or 0

                        return {
                            "total_users": total_users or 0,
                            "total_coins": total_coins or 0,
                            "total_gems": total_gems or 0,
                            "total_games": safe_total_games,
                            "total_wins": safe_total_wins,
                            "avg_coins": float(avg_coins) if avg_coins else 0,
                            "max_coins": max_coins or 0,
                            "daily_checkins": daily_checkins or 0,
                            "win_rate": (
                                (safe_total_wins / safe_total_games * 100)
                                if safe_total_games > 0
                                else 0
                            ),
                        }

                    return {}

        except Exception as e:
            logger.error(f"❌ 獲取經濟統計失敗: {e}")
            return {}

    # ========== 新增：跨平台同步功能 ==========

    async def get_economy_settings(self, guild_id: int) -> EconomySettings:
        """獲取伺服器經濟設定"""
        if guild_id not in self._economy_settings:
            self._economy_settings[guild_id] = EconomySettings(guild_id=guild_id)
        return self._economy_settings[guild_id]

    async def update_economy_settings(self, guild_id: int, **kwargs) -> EconomySettings:
        """更新伺服器經濟設定"""
        settings = await self.get_economy_settings(guild_id)

        for key, value in kwargs.items():
            if hasattr(settings, key):
                setattr(settings, key, value)

        settings.last_updated = datetime.now(timezone.utc)
        return settings

    async def enable_cross_platform_sync(
        self, guild_id: int, minecraft_api_endpoint: str, minecraft_server_key: str
    ) -> bool:
        """啟用跨平台同步"""
        try:
            settings = await self.get_economy_settings(guild_id)
            settings.sync_enabled = True
            settings.minecraft_api_endpoint = minecraft_api_endpoint
            settings.minecraft_server_key = minecraft_server_key

            logger.info(f"✅ 伺服器 {guild_id} 已啟用跨平台同步")
            return True

        except Exception as e:
            logger.error(f"❌ 啟用跨平台同步失敗: {e}")
            return False

    async def trigger_cross_platform_sync(self, user_id: int, guild_id: int):
        """觸發跨平台同步"""
        try:
            settings = await self.get_economy_settings(guild_id)

            if not settings.sync_enabled or not settings.minecraft_api_endpoint:
                return

            # 檢查同步間隔
            last_sync = self._last_sync_time.get(user_id)
            if (
                last_sync
                and (datetime.now(timezone.utc) - last_sync).total_seconds()
                < settings.sync_interval
            ):
                return

            # 如果已有同步任務在執行，取消舊任務
            if user_id in self._sync_tasks:
                self._sync_tasks[user_id].cancel()

            # 建立新的同步任務
            self._sync_tasks[user_id] = asyncio.create_task(
                self._perform_cross_platform_sync(user_id, guild_id, settings)
            )

        except Exception as e:
            logger.error(f"❌ 觸發跨平台同步失敗: {e}")

    async def _perform_cross_platform_sync(
        self, user_id: int, guild_id: int, settings: EconomySettings
    ):
        """執行跨平台同步 - 連接到 Zientis API"""
        try:
            # 獲取當前用戶經濟數據
            economy_data = await self.get_user_economy(user_id, guild_id)

            # 準備 Zientis API 同步數據
            sync_data = {
                "user_id": str(user_id),
                "guild_id": str(guild_id),
                "sync_type": "discord_to_minecraft",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "balances": {
                    "coins": economy_data.get("coins", 0),
                    "gems": economy_data.get("gems", 0),
                    "tickets": economy_data.get("tickets", 0),
                    "experience": economy_data.get("experience", 0),
                },
            }

            # 生成請求簽名
            payload_str = json.dumps(sync_data, sort_keys=True)
            signature = self._generate_request_signature(payload_str, settings.minecraft_server_key)
            sync_data["signature"] = signature

            # 發送到 Zientis Discord API
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{settings.minecraft_api_endpoint}/api/v1/discord/economy/sync",
                    json=sync_data,
                    timeout=aiohttp.ClientTimeout(total=15),
                    headers={
                        "Authorization": f"Bearer {await self._get_user_token(user_id)}",
                        "X-Server-Key": settings.minecraft_server_key,
                        "Content-Type": "application/json",
                        "User-Agent": "PotatoBot/3.0.0",
                    },
                ) as response:
                    if response.status == 200:
                        result = await response.json()

                        # 處理 Zientis 同步回應
                        if result.get("status") == "success":
                            self._last_sync_time[user_id] = datetime.now(timezone.utc)
                            logger.info(f"✅ Zientis 跨平台同步成功：用戶 {user_id}")

                            # 記錄同步交易
                            await self._record_sync_transaction(
                                user_id, guild_id, "discord_to_zientis", sync_data["balances"]
                            )

                            # 處理 Minecraft 獎勵加成
                            if (
                                result.get("adjustments")
                                and result["adjustments"].get("bonus_coins", 0) > 0
                            ):
                                bonus_amount = int(result["adjustments"]["bonus_coins"])
                                await self.add_currency(
                                    user_id,
                                    guild_id,
                                    CurrencyType.COINS,
                                    bonus_amount,
                                    TransactionType.BONUS,
                                    "Minecraft 服務器獎勵加成",
                                )
                                logger.info(
                                    f"🎁 Minecraft 獎勵加成：用戶 {user_id} 獲得 {bonus_amount} 金幣"
                                )

                            # 更新最終餘額（如果有調整）
                            if result.get("balances"):
                                final_balances = result["balances"]
                                await self._update_balances_from_minecraft(
                                    user_id, guild_id, final_balances
                                )
                        else:
                            logger.error(
                                f"❌ Zientis 同步失敗：{result.get('message', '未知錯誤')}"
                            )
                    elif response.status == 404:
                        logger.warning(f"⚠️ 用戶 {user_id} 尚未綁定 Minecraft 帳戶")
                    elif response.status == 423:
                        logger.warning(f"🧊 用戶 {user_id} Minecraft 帳戶已被凍結")
                    else:
                        error_text = await response.text()
                        logger.error(f"❌ Zientis 同步 HTTP 錯誤：{response.status} - {error_text}")

        except asyncio.CancelledError:
            logger.info(f"🔄 Zientis 跨平台同步已取消：用戶 {user_id}")
        except Exception as e:
            logger.error(f"❌ 執行跨平台同步失敗 {user_id}: {e}")
        finally:
            # 清理同步任務
            if user_id in self._sync_tasks:
                del self._sync_tasks[user_id]

    async def _apply_minecraft_adjustments(
        self, user_id: int, guild_id: int, adjusted_balances: Dict[str, int]
    ):
        """應用來自 Minecraft 的餘額調整"""
        try:
            economy_data = await self.get_user_economy(user_id, guild_id)

            for currency, amount in adjusted_balances.items():
                current_amount = economy_data.get(currency, 0)

                if current_amount != amount:
                    difference = amount - current_amount

                    # 更新對應的貨幣
                    if currency == "coins":
                        if difference > 0:
                            await self.add_coins(user_id, guild_id, difference)
                        else:
                            await self.subtract_coins(user_id, guild_id, abs(difference))
                    elif currency == "gems":
                        await self.add_gems(user_id, guild_id, difference)
                    elif currency == "experience":
                        await self.add_experience(user_id, guild_id, difference)

                    # 記錄調整交易
                    await self._record_sync_transaction(
                        user_id,
                        guild_id,
                        "minecraft_adjustment",
                        {currency: difference},
                        f"Minecraft端調整：{currency}",
                    )

        except Exception as e:
            logger.error(f"❌ 應用Minecraft調整失敗: {e}")

    async def _record_sync_transaction(
        self,
        user_id: int,
        guild_id: int,
        sync_type: str,
        balances: Dict[str, int],
        description: str = "跨平台同步",
    ):
        """記錄同步交易"""
        try:
            transaction = CrossPlatformTransaction(
                transaction_id=self._generate_transaction_id(),
                user_id=user_id,
                guild_id=guild_id,
                currency_type=CurrencyType.COINS,  # 主要貨幣類型
                transaction_type=TransactionType.SYNC,
                amount=sum(balances.values()),
                balance_before=0,  # 簡化處理
                balance_after=sum(balances.values()),
                description=description,
                source_platform=sync_type,
                timestamp=datetime.now(timezone.utc),
                metadata={"balances": balances, "sync_type": sync_type},
            )

            self._cross_platform_transactions.append(transaction)

            # 限制交易記錄數量
            if len(self._cross_platform_transactions) > 1000:
                self._cross_platform_transactions = self._cross_platform_transactions[-500:]

        except Exception as e:
            logger.error(f"❌ 記錄同步交易失敗: {e}")

    def _generate_transaction_id(self) -> str:
        """產生交易ID - 使用安全隨機數生成"""
        timestamp = str(int(time.time() * 1000))
        # 使用 secrets 模組生成安全的隨機字符串
        random_str = secrets.token_hex(4)  # 8個字符的十六進制字符串
        return f"tx_{timestamp}_{random_str}"

    async def handle_minecraft_webhook(self, webhook_data: Dict[str, Any]) -> bool:
        """處理來自 Minecraft 的 Webhook 請求"""
        try:
            event_type = webhook_data.get("event_type")
            user_id = webhook_data.get("user_id")
            guild_id = webhook_data.get("guild_id")

            if not all([event_type, user_id, guild_id]):
                logger.warning("⚠️ Minecraft Webhook 數據不完整")
                return False

            if event_type == "player_activity":
                # 處理玩家活動獎勵
                activity_type = webhook_data.get("activity_type")
                reward_amount = webhook_data.get("reward_amount", 0)

                if activity_type == "mining":
                    await self.add_coins(user_id, guild_id, reward_amount)
                elif activity_type == "building":
                    await self.add_experience(user_id, guild_id, reward_amount)
                elif activity_type == "pvp_win":
                    await self.add_gems(user_id, guild_id, reward_amount)

                # 記錄 Minecraft 活動交易
                await self._record_sync_transaction(
                    user_id,
                    guild_id,
                    "minecraft",
                    {activity_type: reward_amount},
                    f"Minecraft活動：{activity_type}",
                )

                logger.info(
                    f"✅ 處理Minecraft活動：用戶 {user_id} {activity_type} +{reward_amount}"
                )

            elif event_type == "balance_sync":
                # 處理餘額同步請求
                await self.trigger_cross_platform_sync(user_id, guild_id)

            return True

        except Exception as e:
            logger.error(f"❌ 處理Minecraft Webhook失敗: {e}")
            return False

    async def get_cross_platform_statistics(self, guild_id: int) -> Dict[str, Any]:
        """獲取跨平台統計"""
        try:
            settings = await self.get_economy_settings(guild_id)

            # 統計跨平台交易
            guild_transactions = [
                t for t in self._cross_platform_transactions if t.guild_id == guild_id
            ]

            stats = {
                "sync_enabled": settings.sync_enabled,
                "total_sync_transactions": len(guild_transactions),
                "active_sync_tasks": len(self._sync_tasks),
                "last_24h_syncs": len(
                    [
                        t
                        for t in guild_transactions
                        if (datetime.now(timezone.utc) - t.timestamp).total_seconds() < 86400
                    ]
                ),
                "platform_distribution": {
                    "discord": len(
                        [t for t in guild_transactions if "discord" in t.source_platform]
                    ),
                    "minecraft": len(
                        [t for t in guild_transactions if "minecraft" in t.source_platform]
                    ),
                },
            }

            return stats

        except Exception as e:
            logger.error(f"❌ 獲取跨平台統計失敗: {e}")
            return {}

    async def perform_anti_inflation_adjustment(self, guild_id: int):
        """執行抗通膨調整"""
        try:
            # 獲取經濟統計
            economy_stats = await self.get_economy_stats(guild_id)
            settings = await self.get_economy_settings(guild_id)

            total_coins = economy_stats.get("total_coins", 0)
            total_users = economy_stats.get("total_users", 1)
            avg_coins = total_coins / total_users if total_users > 0 else 0

            # 計算通膨指標（簡化）
            inflation_rate = 0.0
            if guild_id in self._inflation_data:
                last_avg = self._inflation_data[guild_id].get("last_avg_coins", avg_coins)
                if last_avg > 0:
                    inflation_rate = (avg_coins - last_avg) / last_avg

            # 更新通膨數據
            if guild_id not in self._inflation_data:
                self._inflation_data[guild_id] = {}

            self._inflation_data[guild_id].update(
                {
                    "last_avg_coins": avg_coins,
                    "inflation_rate": inflation_rate,
                    "last_adjustment": datetime.now(timezone.utc).isoformat(),
                }
            )

            # 執行調整
            if inflation_rate > settings.inflation_threshold:
                # 通膨過高，降低獎勵
                adjustment_factor = 0.9
                settings.message_coins = max(1, int(settings.message_coins * adjustment_factor))
                settings.voice_coins_per_minute = max(
                    1, int(settings.voice_coins_per_minute * adjustment_factor)
                )

                logger.warning(f"⚠️ 伺服器 {guild_id} 通膨率 {inflation_rate:.2%}，調整獎勵倍率")

            elif settings.deflation_enabled and inflation_rate < -settings.inflation_threshold:
                # 通縮過多，提高獎勵
                adjustment_factor = 1.1
                settings.message_coins = min(10, int(settings.message_coins * adjustment_factor))
                settings.voice_coins_per_minute = min(
                    20, int(settings.voice_coins_per_minute * adjustment_factor)
                )

                logger.info(f"📈 伺服器 {guild_id} 通縮率 {abs(inflation_rate):.2%}，提高獎勵倍率")

            return {
                "inflation_rate": inflation_rate,
                "avg_coins": avg_coins,
                "adjustment_applied": abs(inflation_rate) > settings.inflation_threshold,
            }

        except Exception as e:
            logger.error(f"❌ 抗通膨調整失敗: {e}")
            return {}

    # ========== Zientis 整合輔助方法 ==========

    def _generate_request_signature(self, payload: str, secret: str) -> str:
        """生成請求簽名"""
        try:
            signature = hmac.new(
                secret.encode("utf-8"), payload.encode("utf-8"), hashlib.sha256
            ).digest()
            return base64.b64encode(signature).decode("utf-8")
        except Exception as e:
            logger.error(f"❌ 生成請求簽名失敗: {e}")
            return ""

    async def _get_user_token(self, user_id: int) -> str:
        """獲取用戶授權令牌"""
        # 這裡可以從數據庫或緩存中獲取用戶令牌
        # 暫時返回一個基於用戶ID的簡單令牌
        return f"user_token_{user_id}_{int(time.time())}"

    async def _update_balances_from_minecraft(
        self, user_id: int, guild_id: int, balances: Dict[str, float]
    ):
        """從 Minecraft 更新餘額"""
        try:
            for currency, amount in balances.items():
                if currency == "coins":
                    # 更新資料庫中的金幣餘額
                    async with db_pool.acquire() as conn:
                        await conn.execute(
                            """
                            UPDATE user_economy
                            SET coins = $1, last_updated = $2
                            WHERE user_id = $3 AND guild_id = $4
                        """,
                            int(amount),
                            datetime.now(timezone.utc),
                            user_id,
                            guild_id,
                        )

                    # 清除緩存
                    cache_key = f"user_economy:{user_id}:{guild_id}"
                    await cache_manager.delete(cache_key)

                    logger.info(f"💰 從 Minecraft 更新用戶 {user_id} 金幣餘額: {amount}")

        except Exception as e:
            logger.error(f"❌ 從 Minecraft 更新餘額失敗: {e}")

    async def setup_zientis_integration(
        self, guild_id: int, api_endpoint: str, server_key: str
    ) -> bool:
        """設置 Zientis 整合 (修復版)"""
        try:
            # 測試連接 (修復 SSL 問題)
            connector = aiohttp.TCPConnector(ssl=False)  # 對 HTTP 端點禁用 SSL
            async with aiohttp.ClientSession(connector=connector) as session:
                async with session.get(
                    f"{api_endpoint}/api/v1/discord/economy/health",
                    headers={"X-Server-Key": server_key},
                    timeout=aiohttp.ClientTimeout(total=10),
                ) as response:
                    if response.status != 200:
                        logger.error(f"❌ Zientis API 連接測試失敗: {response.status}")
                        return False

                    health_data = await response.json()
                    logger.info(
                        f"🔗 Zientis API 健康檢查通過: {health_data.get('status', 'unknown')}"
                    )

            # 更新記憶體設定
            if guild_id not in self._economy_settings:
                self._economy_settings[guild_id] = EconomySettings(guild_id=guild_id)

            settings = self._economy_settings[guild_id]
            settings.sync_enabled = True
            settings.minecraft_api_endpoint = api_endpoint
            settings.minecraft_server_key = server_key

            # 保存到資料庫 (修復資料庫連接問題)
            try:
                if not db_pool._initialized:
                    logger.warning("⚠️ 資料庫連接池未初始化，跳過資料庫保存")
                    logger.info(f"✅ Zientis 整合設置成功 (僅記憶體)：伺服器 {guild_id}")
                    return True

                async with db_pool.connection() as conn:
                    async with conn.cursor() as cursor:
                        # 檢查表是否存在
                        await cursor.execute("SHOW TABLES LIKE 'economy_settings'")
                        if not await cursor.fetchone():
                            logger.warning("⚠️ economy_settings 表不存在，跳過資料庫保存")
                            logger.info(f"✅ Zientis 整合設置成功 (僅記憶體)：伺服器 {guild_id}")
                            return True

                        # 執行資料庫操作
                        await cursor.execute(
                            """
                            INSERT INTO economy_settings (guild_id, sync_enabled, minecraft_api_endpoint, minecraft_server_key, last_updated)
                            VALUES (%s, %s, %s, %s, %s)
                            ON DUPLICATE KEY UPDATE
                                sync_enabled = VALUES(sync_enabled),
                                minecraft_api_endpoint = VALUES(minecraft_api_endpoint),
                                minecraft_server_key = VALUES(minecraft_server_key),
                                last_updated = VALUES(last_updated)
                        """,
                            (guild_id, True, api_endpoint, server_key, datetime.now(timezone.utc)),
                        )
                        await conn.commit()

                        logger.info(f"✅ Zientis 整合設置成功 (包含資料庫)：伺服器 {guild_id}")

            except Exception as db_error:
                logger.error(f"⚠️ 資料庫保存失敗但設定已儲存至記憶體: {db_error}")
                logger.info(f"✅ Zientis 整合設置成功 (僅記憶體)：伺服器 {guild_id}")

            return True

        except Exception as e:
            logger.error(f"❌ Zientis 整合設置失敗: {e}")
            return False


# 全域實例保持不變
economy_manager = EconomyManager()
