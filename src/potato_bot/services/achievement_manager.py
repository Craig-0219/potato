# bot/services/achievement_manager.py - 成就管理系統
"""
成就管理系統 v2.2.0
管理用戶的遊戲成就、徽章和里程碑
"""

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

from potato_bot.db.pool import db_pool
from potato_shared.cache_manager import cache_manager
from potato_shared.logger import logger


class AchievementType(Enum):
    """成就類型"""

    DAILY = "daily"  # 每日相關
    GAMES = "games"  # 遊戲相關
    ECONOMY = "economy"  # 經濟相關
    SOCIAL = "social"  # 社交相關
    SPECIAL = "special"  # 特殊成就
    MILESTONE = "milestone"  # 里程碑


class AchievementRarity(Enum):
    """成就稀有度"""

    COMMON = "common"  # 普通
    UNCOMMON = "uncommon"  # 不普通
    RARE = "rare"  # 稀有
    EPIC = "epic"  # 史詩
    LEGENDARY = "legendary"  # 傳說


@dataclass
class Achievement:
    """成就定義"""

    id: str
    name: str
    description: str
    type: AchievementType
    rarity: AchievementRarity
    requirements: Dict[str, Any]
    rewards: Dict[str, int]  # {"coins": 100, "gems": 10, "experience": 50}
    icon: str
    hidden: bool = False
    repeatable: bool = False


@dataclass
class UserAchievement:
    """用戶成就記錄"""

    user_id: int
    guild_id: int
    achievement_id: str
    unlocked_at: datetime
    progress: Dict[str, Any] = None

    def __post_init__(self):
        if self.progress is None:
            self.progress = {}


class AchievementManager:
    """成就管理器"""

    def __init__(self):
        self.achievements: Dict[str, Achievement] = {}
        self._load_achievements()
        logger.info("🏆 成就管理系統初始化完成")

    def _load_achievements(self):
        """載入成就定義"""
        # 每日簽到成就
        self.achievements.update(
            {
                "first_checkin": Achievement(
                    id="first_checkin",
                    name="新手報到",
                    description="完成第一次每日簽到",
                    type=AchievementType.DAILY,
                    rarity=AchievementRarity.COMMON,
                    requirements={"checkin_days": 1},
                    rewards={"coins": 100, "experience": 50},
                    icon="🎯",
                ),
                "week_warrior": Achievement(
                    id="week_warrior",
                    name="一週戰士",
                    description="連續簽到 7 天",
                    type=AchievementType.DAILY,
                    rarity=AchievementRarity.UNCOMMON,
                    requirements={"streak_days": 7},
                    rewards={"coins": 500, "gems": 20, "experience": 200},
                    icon="⚔️",
                ),
                "month_master": Achievement(
                    id="month_master",
                    name="月度大師",
                    description="連續簽到 30 天",
                    type=AchievementType.DAILY,
                    rarity=AchievementRarity.RARE,
                    requirements={"streak_days": 30},
                    rewards={"coins": 2000, "gems": 100, "experience": 1000},
                    icon="👑",
                ),
            }
        )

        # 遊戲成就
        self.achievements.update(
            {
                "first_game": Achievement(
                    id="first_game",
                    name="遊戲新手",
                    description="完成第一場遊戲",
                    type=AchievementType.GAMES,
                    rarity=AchievementRarity.COMMON,
                    requirements={"total_games": 1},
                    rewards={"coins": 50, "experience": 25},
                    icon="🎮",
                ),
                "first_win": Achievement(
                    id="first_win",
                    name="初嘗勝果",
                    description="贏得第一場遊戲",
                    type=AchievementType.GAMES,
                    rarity=AchievementRarity.COMMON,
                    requirements={"total_wins": 1},
                    rewards={"coins": 100, "experience": 50},
                    icon="🏆",
                ),
                "game_addict": Achievement(
                    id="game_addict",
                    name="遊戲成癮者",
                    description="總共遊玩 100 場遊戲",
                    type=AchievementType.GAMES,
                    rarity=AchievementRarity.UNCOMMON,
                    requirements={"total_games": 100},
                    rewards={"coins": 1000, "gems": 50, "experience": 500},
                    icon="🎯",
                ),
                "win_streak_5": Achievement(
                    id="win_streak_5",
                    name="五連勝",
                    description="連續贏得 5 場遊戲",
                    type=AchievementType.GAMES,
                    rarity=AchievementRarity.RARE,
                    requirements={"win_streak": 5},
                    rewards={"coins": 750, "gems": 30, "experience": 300},
                    icon="🔥",
                ),
                "guess_master": Achievement(
                    id="guess_master",
                    name="猜謎大師",
                    description="在猜數字遊戲中一次猜中",
                    type=AchievementType.GAMES,
                    rarity=AchievementRarity.EPIC,
                    requirements={"perfect_guess": True},
                    rewards={"coins": 1500, "gems": 75, "experience": 750},
                    icon="🎊",
                ),
            }
        )

        # 經濟成就
        self.achievements.update(
            {
                "first_coin": Achievement(
                    id="first_coin",
                    name="第一桶金",
                    description="擁有 1000 金幣",
                    type=AchievementType.ECONOMY,
                    rarity=AchievementRarity.COMMON,
                    requirements={"total_coins": 1000},
                    rewards={"gems": 10, "experience": 100},
                    icon="🪙",
                ),
                "coin_collector": Achievement(
                    id="coin_collector",
                    name="金幣收藏家",
                    description="擁有 10000 金幣",
                    type=AchievementType.ECONOMY,
                    rarity=AchievementRarity.UNCOMMON,
                    requirements={"total_coins": 10000},
                    rewards={"gems": 50, "experience": 500},
                    icon="💰",
                ),
                "millionaire": Achievement(
                    id="millionaire",
                    name="百萬富翁",
                    description="擁有 100000 金幣",
                    type=AchievementType.ECONOMY,
                    rarity=AchievementRarity.LEGENDARY,
                    requirements={"total_coins": 100000},
                    rewards={"gems": 500, "experience": 5000},
                    icon="💎",
                ),
                "level_10": Achievement(
                    id="level_10",
                    name="十級戰士",
                    description="達到等級 10",
                    type=AchievementType.ECONOMY,
                    rarity=AchievementRarity.UNCOMMON,
                    requirements={"level": 10},
                    rewards={"coins": 1000, "gems": 25},
                    icon="⭐",
                ),
                "level_50": Achievement(
                    id="level_50",
                    name="五十級大師",
                    description="達到等級 50",
                    type=AchievementType.ECONOMY,
                    rarity=AchievementRarity.EPIC,
                    requirements={"level": 50},
                    rewards={"coins": 5000, "gems": 150},
                    icon="🌟",
                ),
            }
        )

        # 特殊成就
        self.achievements.update(
            {
                "lucky_day": Achievement(
                    id="lucky_day",
                    name="幸運之日",
                    description="在一天內贏得 10 場遊戲",
                    type=AchievementType.SPECIAL,
                    rarity=AchievementRarity.RARE,
                    requirements={"daily_wins": 10},
                    rewards={"coins": 1000, "gems": 50, "experience": 500},
                    icon="🍀",
                ),
                "perfect_day": Achievement(
                    id="perfect_day",
                    name="完美一天",
                    description="在一天內保持 100% 勝率（至少 5 場遊戲）",
                    type=AchievementType.SPECIAL,
                    rarity=AchievementRarity.EPIC,
                    requirements={"perfect_day": True, "min_games": 5},
                    rewards={"coins": 2000, "gems": 100, "experience": 1000},
                    icon="✨",
                ),
                "late_night_gamer": Achievement(
                    id="late_night_gamer",
                    name="深夜玩家",
                    description="在凌晨 2-4 點之間遊玩",
                    type=AchievementType.SPECIAL,
                    rarity=AchievementRarity.UNCOMMON,
                    requirements={"late_night_play": True},
                    rewards={"coins": 300, "experience": 150},
                    icon="🌙",
                ),
            }
        )

    # ========== 成就檢查系統 ==========

    async def check_daily_achievements(
        self, user_id: int, guild_id: int, streak_days: int
    ) -> List[Dict[str, Any]]:
        """檢查每日簽到相關成就"""
        achievements_earned = []

        try:
            # 檢查簽到相關成就
            daily_achievements = [
                ("first_checkin", 1),
                ("week_warrior", 7),
                ("month_master", 30),
            ]

            for achievement_id, required_streak in daily_achievements:
                if streak_days >= required_streak:
                    if not await self._user_has_achievement(user_id, guild_id, achievement_id):
                        achievement = await self._grant_achievement(
                            user_id, guild_id, achievement_id
                        )
                        if achievement:
                            achievements_earned.append(achievement)

            return achievements_earned

        except Exception as e:
            logger.error(f"❌ 檢查每日成就失敗: {e}")
            return []

    async def check_game_achievements(
        self,
        user_id: int,
        guild_id: int,
        game_type: str,
        won: bool,
        score: int,
    ) -> List[Dict[str, Any]]:
        """檢查遊戲相關成就"""
        achievements_earned = []

        try:
            # 獲取用戶遊戲統計
            from potato_bot.services.economy_manager import EconomyManager

            economy_manager = EconomyManager()
            user_economy = await economy_manager.get_user_economy(user_id, guild_id)

            # 檢查基礎遊戲成就
            if user_economy.get("total_games", 0) >= 1:
                if not await self._user_has_achievement(user_id, guild_id, "first_game"):
                    achievement = await self._grant_achievement(user_id, guild_id, "first_game")
                    if achievement:
                        achievements_earned.append(achievement)

            if user_economy.get("total_wins", 0) >= 1 and won:
                if not await self._user_has_achievement(user_id, guild_id, "first_win"):
                    achievement = await self._grant_achievement(user_id, guild_id, "first_win")
                    if achievement:
                        achievements_earned.append(achievement)

            # 檢查遊戲次數成就
            if user_economy.get("total_games", 0) >= 100:
                if not await self._user_has_achievement(user_id, guild_id, "game_addict"):
                    achievement = await self._grant_achievement(user_id, guild_id, "game_addict")
                    if achievement:
                        achievements_earned.append(achievement)

            # 檢查特殊遊戲成就
            if game_type == "guess_number" and won and score == 1:  # 一次猜中
                if not await self._user_has_achievement(user_id, guild_id, "guess_master"):
                    achievement = await self._grant_achievement(user_id, guild_id, "guess_master")
                    if achievement:
                        achievements_earned.append(achievement)

            # 檢查每日特殊成就
            daily_wins = user_economy.get("daily_wins", 0)
            if daily_wins >= 10:
                if not await self._user_has_achievement(user_id, guild_id, "lucky_day"):
                    achievement = await self._grant_achievement(user_id, guild_id, "lucky_day")
                    if achievement:
                        achievements_earned.append(achievement)

            # 檢查深夜玩家成就
            current_hour = datetime.now(timezone.utc).hour
            if 2 <= current_hour <= 4:
                if not await self._user_has_achievement(user_id, guild_id, "late_night_gamer"):
                    achievement = await self._grant_achievement(
                        user_id, guild_id, "late_night_gamer"
                    )
                    if achievement:
                        achievements_earned.append(achievement)

            return achievements_earned

        except Exception as e:
            logger.error(f"❌ 檢查遊戲成就失敗: {e}")
            return []

    async def check_economy_achievements(self, user_id: int, guild_id: int) -> List[Dict[str, Any]]:
        """檢查經濟相關成就"""
        achievements_earned = []

        try:
            from potato_bot.services.economy_manager import EconomyManager

            economy_manager = EconomyManager()
            user_economy = await economy_manager.get_user_economy(user_id, guild_id)
            level_info = await economy_manager.calculate_level(user_economy.get("experience", 0))

            # 檢查金幣成就
            coins = user_economy.get("coins", 0)
            coin_achievements = [
                ("first_coin", 1000),
                ("coin_collector", 10000),
                ("millionaire", 100000),
            ]

            for achievement_id, required_coins in coin_achievements:
                if coins >= required_coins:
                    if not await self._user_has_achievement(user_id, guild_id, achievement_id):
                        achievement = await self._grant_achievement(
                            user_id, guild_id, achievement_id
                        )
                        if achievement:
                            achievements_earned.append(achievement)

            # 檢查等級成就
            level = level_info["level"]
            level_achievements = [("level_10", 10), ("level_50", 50)]

            for achievement_id, required_level in level_achievements:
                if level >= required_level:
                    if not await self._user_has_achievement(user_id, guild_id, achievement_id):
                        achievement = await self._grant_achievement(
                            user_id, guild_id, achievement_id
                        )
                        if achievement:
                            achievements_earned.append(achievement)

            return achievements_earned

        except Exception as e:
            logger.error(f"❌ 檢查經濟成就失敗: {e}")
            return []

    # ========== 成就管理功能 ==========

    async def _user_has_achievement(self, user_id: int, guild_id: int, achievement_id: str) -> bool:
        """檢查用戶是否已有該成就"""
        try:
            # 先從快取檢查
            cache_key = f"user_achievement:{user_id}:{guild_id}:{achievement_id}"
            cached_result = await cache_manager.get(cache_key)
            if cached_result is not None:
                return cached_result

            async with db_pool.connection() as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute(
                        """
                        SELECT 1 FROM user_achievements
                        WHERE user_id = %s AND guild_id = %s AND achievement_id = %s
                    """,
                        (user_id, guild_id, achievement_id),
                    )

                    result = await cursor.fetchone()
                    has_achievement = result is not None

                    # 快取結果
                    await cache_manager.set(cache_key, has_achievement, 600)  # 10分鐘快取

                    return has_achievement

        except Exception as e:
            logger.error(f"❌ 檢查用戶成就失敗: {e}")
            return False

    async def _grant_achievement(
        self, user_id: int, guild_id: int, achievement_id: str
    ) -> Optional[Dict[str, Any]]:
        """授予成就"""
        try:
            achievement_def = self.achievements.get(achievement_id)
            if not achievement_def:
                logger.warning(f"⚠️ 未知成就 ID: {achievement_id}")
                return None

            # 檢查是否已有成就（雙重檢查）
            if await self._user_has_achievement(user_id, guild_id, achievement_id):
                return None

            # 授予成就
            async with db_pool.connection() as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute(
                        """
                        INSERT INTO user_achievements
                        (user_id, guild_id, achievement_id, unlocked_at, progress)
                        VALUES (%s, %s, %s, %s, %s)
                        ON DUPLICATE KEY UPDATE unlocked_at = unlocked_at
                    """,
                        (
                            user_id,
                            guild_id,
                            achievement_id,
                            datetime.now(timezone.utc),
                            json.dumps({}),
                        ),
                    )

                    if cursor.rowcount > 0:
                        await conn.commit()

                        # 發放獎勵
                        await self._grant_achievement_rewards(user_id, guild_id, achievement_def)

                        # 清理相關快取
                        cache_key = f"user_achievement:{user_id}:{guild_id}:{achievement_id}"
                        await cache_manager.set(cache_key, True, 600)
                        await cache_manager.delete(f"user_achievements:{user_id}:{guild_id}")

                        logger.info(f"🏆 用戶 {user_id} 獲得成就: {achievement_def.name}")

                        return {
                            "id": achievement_id,
                            "name": achievement_def.name,
                            "description": achievement_def.description,
                            "icon": achievement_def.icon,
                            "rarity": achievement_def.rarity.value,
                            "rewards": achievement_def.rewards,
                        }

                    return None

        except Exception as e:
            logger.error(f"❌ 授予成就失敗: {e}")
            return None

    async def _grant_achievement_rewards(
        self, user_id: int, guild_id: int, achievement: Achievement
    ):
        """發放成就獎勵"""
        try:
            from potato_bot.services.economy_manager import EconomyManager

            economy_manager = EconomyManager()

            # 發放金幣
            if achievement.rewards.get("coins", 0) > 0:
                await economy_manager.add_coins(user_id, guild_id, achievement.rewards["coins"])

            # 發放寶石
            if achievement.rewards.get("gems", 0) > 0:
                await economy_manager.add_gems(user_id, guild_id, achievement.rewards["gems"])

            # 發放經驗值
            if achievement.rewards.get("experience", 0) > 0:
                await economy_manager.add_experience(
                    user_id, guild_id, achievement.rewards["experience"]
                )

        except Exception as e:
            logger.error(f"❌ 發放成就獎勵失敗: {e}")

    # ========== 查詢功能 ==========

    async def get_user_achievements(self, user_id: int, guild_id: int) -> List[Dict[str, Any]]:
        """獲取用戶成就列表"""
        try:
            cache_key = f"user_achievements:{user_id}:{guild_id}"
            cached_result = await cache_manager.get(cache_key)
            if cached_result:
                return cached_result

            async with db_pool.connection() as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute(
                        """
                        SELECT achievement_id, unlocked_at, progress
                        FROM user_achievements
                        WHERE user_id = %s AND guild_id = %s
                        ORDER BY unlocked_at DESC
                    """,
                        (user_id, guild_id),
                    )

                    results = await cursor.fetchall()

                    achievements = []
                    for achievement_id, unlocked_at, progress_json in results:
                        achievement_def = self.achievements.get(achievement_id)
                        if achievement_def:
                            achievements.append(
                                {
                                    "id": achievement_id,
                                    "name": achievement_def.name,
                                    "description": achievement_def.description,
                                    "icon": achievement_def.icon,
                                    "rarity": achievement_def.rarity.value,
                                    "type": achievement_def.type.value,
                                    "unlocked_at": unlocked_at,
                                    "progress": (
                                        json.loads(progress_json) if progress_json else {}
                                    ),
                                }
                            )

                    # 快取結果
                    await cache_manager.set(cache_key, achievements, 300)  # 5分鐘快取

                    return achievements

        except Exception as e:
            logger.error(f"❌ 獲取用戶成就失敗: {e}")
            return []

    async def get_achievement_progress(
        self, user_id: int, guild_id: int, achievement_id: str
    ) -> Dict[str, Any]:
        """獲取成就進度"""
        try:
            achievement_def = self.achievements.get(achievement_id)
            if not achievement_def:
                return {}

            # 檢查是否已解鎖
            if await self._user_has_achievement(user_id, guild_id, achievement_id):
                return {"completed": True, "progress": 100.0}

            # 獲取當前進度（根據成就類型計算）
            progress = await self._calculate_achievement_progress(
                user_id, guild_id, achievement_def
            )

            return {
                "completed": False,
                "progress": progress.get("percentage", 0.0),
                "current": progress.get("current", 0),
                "required": progress.get("required", 1),
            }

        except Exception as e:
            logger.error(f"❌ 獲取成就進度失敗: {e}")
            return {}

    async def _calculate_achievement_progress(
        self, user_id: int, guild_id: int, achievement: Achievement
    ) -> Dict[str, Any]:
        """計算成就進度"""
        try:
            from potato_bot.services.economy_manager import EconomyManager

            economy_manager = EconomyManager()
            user_economy = await economy_manager.get_user_economy(user_id, guild_id)

            requirements = achievement.requirements
            progress = {"current": 0, "required": 1, "percentage": 0.0}

            # 根據成就類型計算進度
            if "total_games" in requirements:
                current = user_economy.get("total_games", 0)
                required = requirements["total_games"]
                progress = {
                    "current": current,
                    "required": required,
                    "percentage": min(100.0, (current / required) * 100),
                }

            elif "total_wins" in requirements:
                current = user_economy.get("total_wins", 0)
                required = requirements["total_wins"]
                progress = {
                    "current": current,
                    "required": required,
                    "percentage": min(100.0, (current / required) * 100),
                }

            elif "total_coins" in requirements:
                current = user_economy.get("coins", 0)
                required = requirements["total_coins"]
                progress = {
                    "current": current,
                    "required": required,
                    "percentage": min(100.0, (current / required) * 100),
                }

            elif "level" in requirements:
                level_info = await economy_manager.calculate_level(
                    user_economy.get("experience", 0)
                )
                current = level_info["level"]
                required = requirements["level"]
                progress = {
                    "current": current,
                    "required": required,
                    "percentage": min(100.0, (current / required) * 100),
                }

            return progress

        except Exception as e:
            logger.error(f"❌ 計算成就進度失敗: {e}")
            return {"current": 0, "required": 1, "percentage": 0.0}

    # ========== 統計功能 ==========

    async def get_achievement_stats(self, guild_id: int) -> Dict[str, Any]:
        """獲取成就統計"""
        try:
            async with db_pool.connection() as conn:
                async with conn.cursor() as cursor:
                    # 獲取總體統計
                    await cursor.execute(
                        """
                        SELECT
                            COUNT(DISTINCT user_id) as active_users,
                            COUNT(*) as total_achievements_earned,
                            achievement_id,
                            COUNT(*) as earn_count
                        FROM user_achievements
                        WHERE guild_id = %s
                        GROUP BY achievement_id
                        ORDER BY earn_count DESC
                    """,
                        (guild_id,),
                    )

                    results = await cursor.fetchall()

                    if not results:
                        return {
                            "active_users": 0,
                            "total_achievements": len(self.achievements),
                            "total_earned": 0,
                            "popular_achievements": [],
                        }

                    # 處理結果
                    active_users = results[0][0] if results else 0
                    total_earned = sum(row[3] for row in results)

                    popular_achievements = []
                    for achievement_id, _, _, count in results[:5]:
                        achievement_def = self.achievements.get(achievement_id)
                        if achievement_def:
                            popular_achievements.append(
                                {
                                    "id": achievement_id,
                                    "name": achievement_def.name,
                                    "icon": achievement_def.icon,
                                    "earned_count": count,
                                }
                            )

                    return {
                        "active_users": active_users,
                        "total_achievements": len(self.achievements),
                        "total_earned": total_earned,
                        "popular_achievements": popular_achievements,
                    }

        except Exception as e:
            logger.error(f"❌ 獲取成就統計失敗: {e}")
            return {}

    async def get_rarest_achievements(self, guild_id: int, limit: int = 5) -> List[Dict[str, Any]]:
        """獲取最稀有的成就"""
        try:
            async with db_pool.connection() as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute(
                        """
                        SELECT achievement_id, COUNT(*) as earn_count
                        FROM user_achievements
                        WHERE guild_id = %s
                        GROUP BY achievement_id
                        ORDER BY earn_count ASC
                        LIMIT %s
                    """,
                        (guild_id, limit),
                    )

                    results = await cursor.fetchall()

                    rarest = []
                    for achievement_id, count in results:
                        achievement_def = self.achievements.get(achievement_id)
                        if achievement_def:
                            rarest.append(
                                {
                                    "id": achievement_id,
                                    "name": achievement_def.name,
                                    "description": achievement_def.description,
                                    "icon": achievement_def.icon,
                                    "rarity": achievement_def.rarity.value,
                                    "earned_count": count,
                                }
                            )

                    return rarest

        except Exception as e:
            logger.error(f"❌ 獲取稀有成就失敗: {e}")
            return []


# 全域實例
achievement_manager = AchievementManager()

# ========== 數據庫初始化 ==========


async def ensure_achievement_tables():
    """確保成就相關表格存在"""
    try:
        async with db_pool.connection() as conn:
            async with conn.cursor() as cursor:
                # 用戶成就表
                await cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS user_achievements (
                        user_id BIGINT NOT NULL,
                        guild_id BIGINT NOT NULL,
                        achievement_id VARCHAR(50) NOT NULL,
                        unlocked_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                        progress JSON,

                        PRIMARY KEY (user_id, guild_id, achievement_id),
                        INDEX idx_user_guild (user_id, guild_id),
                        INDEX idx_achievement (achievement_id),
                        INDEX idx_unlocked_at (unlocked_at)
                    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
                """
                )

                await conn.commit()
                logger.info("✅ 成就相關表格檢查完成")

    except Exception as e:
        logger.error(f"❌ 建立成就表格失敗: {e}")
        raise
