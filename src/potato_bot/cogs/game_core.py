# bot/cogs/game_core.py - 遊戲娛樂系統核心
"""
遊戲娛樂系統核心模組 v2.2.0
提供多樣化的遊戲和娛樂功能，讓 Discord 伺服器更加有趣和活躍

功能特點：
1. 多種小遊戲（猜數字、剪刀石頭布、文字接龍等）
2. 虛擬經濟系統（金幣、經驗值、每日簽到）
3. 成就徽章系統
4. 排行榜和競技功能
5. 團隊遊戲和協作模式
"""

import json
import random
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, Optional

import discord
from discord import app_commands
from discord.ext import commands, tasks

# 遊戲相關導入
from potato_bot.db.pool import db_pool
from potato_bot.services.achievement_manager import AchievementManager
from potato_bot.services.game_manager import GameManager
from potato_bot.utils.embed_builder import EmbedBuilder
from potato_bot.views.game_views import (
    GameMenuView,
    GuessNumberView,
)
from potato_shared.cache_manager import cache_manager
from potato_shared.logger import logger


class GameType(Enum):
    """遊戲類型"""

    GUESS_NUMBER = "guess_number"
    ROCK_PAPER_SCISSORS = "rock_paper_scissors"
    COIN_FLIP = "coin_flip"
    ROULETTE = "roulette"
    TRIVIA = "trivia"
    WORD_CHAIN = "word_chain"
    TRUTH_DARE = "truth_dare"
    DICE_ROLL = "dice_roll"


class GameDifficulty(Enum):
    """遊戲難度"""

    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"
    EXPERT = "expert"


@dataclass
class GameSession:
    """遊戲會話"""

    game_id: str
    game_type: GameType
    player_id: int
    guild_id: int
    channel_id: int
    start_time: datetime
    end_time: Optional[datetime] = None
    status: str = "active"  # active, completed, abandoned
    score: int = 0
    data: Dict[str, Any] = None

    def __post_init__(self):
        if self.data is None:
            self.data = {}


class GameEntertainment(commands.Cog):
    """遊戲娛樂系統"""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.game_manager = GameManager()
        self.achievement_manager = AchievementManager()

        # 活躍的遊戲會話
        self.active_sessions: Dict[str, GameSession] = {}

        # 遊戲配置
        self.game_configs = {
            GameType.GUESS_NUMBER: {
                "min_number": 1,
                "max_number": 100,
                "max_attempts": 6,
            },
            GameType.ROCK_PAPER_SCISSORS: {
                "choices": ["rock", "paper", "scissors"],
            },
            GameType.COIN_FLIP: {
                "min_bet": 10,
                "max_bet": 1000,
                "win_multiplier": 2.0,
            },
            GameType.ROULETTE: {
                "min_bet": 20,
                "max_bet": 500,
                "payouts": {
                    "number": 35,
                    "color": 2,
                    "even_odd": 2,
                    "dozen": 3,
                },
            },
        }

        # 啟動定時任務
        self.cleanup_sessions.start()
        self.daily_reset.start()

        logger.info("🎮 遊戲娛樂系統初始化完成")

    def cog_unload(self):
        """模組卸載"""
        self.cleanup_sessions.cancel()
        self.daily_reset.cancel()
        logger.info("🎮 遊戲娛樂系統已卸載")

    # ========== 遊戲選單和入口 ==========

    @app_commands.command(name="games", description="打開遊戲選單")
    async def games_menu(self, interaction: discord.Interaction):
        """遊戲選單"""
        try:
            # 創建遊戲選單嵌入
            embed = EmbedBuilder.build(
                title="🎮 遊戲娛樂中心",
                description="選擇您想要遊玩的遊戲！",
                color=0x00FF88,
            )

            # 可用遊戲列表
            games_list = [
                "🔢 猜數字 - 考驗運氣和邏輯",
                "✂️ 剪刀石頭布 - 經典對戰遊戲",
                "🪙 拋硬幣 - 簡單的賭博遊戲",
                "🎰 輪盤 - 刺激的賭場遊戲",
                "🧠 問答競賽 - 測試知識水平",
                "🎲 骰子遊戲 - 運氣大比拼",
            ]

            embed.add_field(name="🎯 可用遊戲", value="\n".join(games_list), inline=False)

            # 創建遊戲選單視圖
            view = GameMenuView(self)

            await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

        except Exception as e:
            logger.error(f"❌ 遊戲選單錯誤: {e}")
            await interaction.response.send_message("❌ 開啟遊戲選單時發生錯誤。", ephemeral=True)

    # ========== 成就系統指令 ==========

    @app_commands.command(name="achievements", description="查看成就列表")
    async def view_achievements(self, interaction: discord.Interaction, user: discord.User = None):
        """查看成就"""
        try:
            target_user = user or interaction.user
            user_id = target_user.id
            guild_id = interaction.guild.id

            # 獲取用戶成就
            user_achievements = await self.achievement_manager.get_user_achievements(
                user_id, guild_id
            )

            embed = EmbedBuilder.build(
                title=f"🏆 {target_user.display_name} 的成就",
                description=f"已解鎖 {len(user_achievements)} 個成就",
                color=0xFFD700,
            )

            embed.set_thumbnail(url=target_user.display_avatar.url)

            if not user_achievements:
                embed.add_field(
                    name="📝 暫無成就",
                    value="還沒有解鎖任何成就，快去遊玩獲得成就吧！",
                    inline=False,
                )
            else:
                # 按稀有度分組顯示
                rarity_groups = {}
                for achievement in user_achievements:
                    rarity = achievement["rarity"]
                    if rarity not in rarity_groups:
                        rarity_groups[rarity] = []
                    rarity_groups[rarity].append(achievement)

                rarity_emojis = {
                    "common": "🥉",
                    "uncommon": "🥈",
                    "rare": "🥇",
                    "epic": "💎",
                    "legendary": "👑",
                }

                rarity_order = [
                    "legendary",
                    "epic",
                    "rare",
                    "uncommon",
                    "common",
                ]

                for rarity in rarity_order:
                    if rarity in rarity_groups:
                        achievements_list = []
                        for ach in rarity_groups[rarity][:5]:  # 最多顯示5個
                            achievements_list.append(f"{ach['icon']} **{ach['name']}**")

                        if len(rarity_groups[rarity]) > 5:
                            achievements_list.append(
                                f"... 還有 {len(rarity_groups[rarity]) - 5} 個"
                            )

                        embed.add_field(
                            name=f"{rarity_emojis[rarity]} {rarity.title()} ({len(rarity_groups[rarity])})",
                            value="\n".join(achievements_list),
                            inline=True,
                        )

            # 獲取成就統計
            stats = await self.achievement_manager.get_achievement_stats(guild_id)
            if stats:
                embed.add_field(
                    name="📊 伺服器統計",
                    value=f"活躍用戶: {stats.get('active_users', 0)}\n"
                    f"總成就數: {stats.get('total_achievements', 0)}\n"
                    f"已解鎖: {stats.get('total_earned', 0)}",
                    inline=True,
                )

            await interaction.response.send_message(embed=embed, ephemeral=user is None)

        except Exception as e:
            logger.error(f"❌ 查看成就錯誤: {e}")
            await interaction.response.send_message("❌ 查看成就時發生錯誤。", ephemeral=True)

    @app_commands.command(name="achievement_progress", description="查看成就進度")
    @app_commands.describe(achievement_id="成就ID（可選）")
    async def achievement_progress(
        self, interaction: discord.Interaction, achievement_id: str = None
    ):
        """查看成就進度"""
        try:
            await interaction.response.defer(ephemeral=True)
            user_id = interaction.user.id
            if not interaction.guild:
                await interaction.followup.send("❌ 請在伺服器中使用此指令。", ephemeral=True)
                return
            guild_id = interaction.guild.id

            if achievement_id:
                # 查看特定成就進度
                progress = await self.achievement_manager.get_achievement_progress(
                    user_id, guild_id, achievement_id
                )

                if not progress:
                    await interaction.followup.send("❌ 未找到該成就。", ephemeral=True)
                    return

                achievement_def = self.achievement_manager.achievements.get(achievement_id)
                if not achievement_def:
                    await interaction.followup.send("❌ 成就定義不存在。", ephemeral=True)
                    return

                embed = EmbedBuilder.build(
                    title=f"🎯 成就進度：{achievement_def.name}",
                    description=achievement_def.description,
                    color=0x00AAFF,
                )

                if progress["completed"]:
                    embed.add_field(name="✅ 狀態", value="已完成", inline=True)
                else:
                    progress_bar = self._create_progress_bar(progress["progress"])
                    embed.add_field(
                        name="📈 進度",
                        value=f"{progress_bar}\n"
                        f"{progress['current']}/{progress['required']} ({progress['progress']:.1f}%)",
                        inline=False,
                    )



            else:
                # 顯示所有未完成成就的進度
                embed = EmbedBuilder.build(
                    title="🎯 成就進度總覽",
                    description="您的成就解鎖進度",
                    color=0x4169E1,
                )

                incomplete_count = 0
                for (
                    ach_id,
                    ach_def,
                ) in self.achievement_manager.achievements.items():
                    progress = await self.achievement_manager.get_achievement_progress(
                        user_id, guild_id, ach_id
                    )

                    if not progress.get("completed", False):
                        incomplete_count += 1
                        if incomplete_count <= 8:  # 只顯示前8個
                            progress_bar = self._create_progress_bar(progress.get("progress", 0))
                            embed.add_field(
                                name=f"{ach_def.icon} {ach_def.name}",
                                value=f"{progress_bar} {progress.get('progress', 0):.0f}%",
                                inline=True,
                            )

                if incomplete_count == 0:
                    embed.add_field(
                        name="🎉 恭喜！",
                        value="您已經完成所有成就！",
                        inline=False,
                    )
                elif incomplete_count > 8:
                    embed.set_footer(text=f"還有 {incomplete_count - 8} 個成就未顯示")

            await interaction.followup.send(embed=embed, ephemeral=True)

        except Exception as e:
            logger.error(f"❌ 查看成就進度錯誤: {e}")
            if interaction.response.is_done():
                await interaction.followup.send("❌ 查看成就進度時發生錯誤。", ephemeral=True)
            else:
                await interaction.response.send_message("❌ 查看成就進度時發生錯誤。", ephemeral=True)

    def _create_progress_bar(self, progress: float, length: int = 10) -> str:
        """創建進度條"""
        filled = int((progress / 100) * length)
        bar = "█" * filled + "░" * (length - filled)
        return f"[{bar}]"

    # ========== 具體遊戲實現 ==========

    @app_commands.command(name="guess", description="猜數字遊戲")
    @app_commands.describe(difficulty="遊戲難度")
    @app_commands.choices(
        difficulty=[
            app_commands.Choice(name="簡單 (1-50)", value="easy"),
            app_commands.Choice(name="中等 (1-100)", value="medium"),
            app_commands.Choice(name="困難 (1-200)", value="hard"),
        ]
    )
    async def guess_number_game(self, interaction: discord.Interaction, difficulty: str = "medium"):
        """猜數字遊戲"""
        try:
            # 檢查用戶是否已有活躍遊戲
            user_session = await self._get_user_active_session(
                interaction.user.id, interaction.guild.id
            )
            if user_session:
                await interaction.response.send_message(
                    "❌ 您已經有一個進行中的遊戲！請先完成當前遊戲。",
                    ephemeral=True,
                )
                return

            # 遊戲配置
            difficulty_configs = {
                "easy": {"max_num": 50, "attempts": 8, "reward": 50},
                "medium": {"max_num": 100, "attempts": 6, "reward": 100},
                "hard": {"max_num": 200, "attempts": 5, "reward": 200},
            }

            config = difficulty_configs[difficulty]
            secret_number = random.randint(1, config["max_num"])

            # 創建遊戲會話
            session = GameSession(
                game_id=f"guess_{interaction.user.id}_{int(time.time())}",
                game_type=GameType.GUESS_NUMBER,
                player_id=interaction.user.id,
                guild_id=interaction.guild.id,
                channel_id=interaction.channel.id,
                start_time=datetime.now(timezone.utc),
                data={
                    "secret_number": secret_number,
                    "attempts_left": config["attempts"],
                    "max_attempts": config["attempts"],
                    "difficulty": difficulty,
                    "reward": config["reward"],
                    "max_num": config["max_num"],
                    "guesses": [],
                },
            )

            self.active_sessions[session.game_id] = session

            # 創建遊戲嵌入
            embed = EmbedBuilder.build(
                title=f"🔢 猜數字遊戲 ({difficulty.title()})",
                description=f"我想了一個 1 到 {config['max_num']} 之間的數字！\n你有 {config['attempts']} 次機會猜中它！",
                color=0x00AAFF,
            )

            embed.add_field(
                name="🎯 遊戲規則",
                value=f"• 數字範圍: 1 - {config['max_num']}\n"
                f"• 嘗試次數: {config['attempts']}\n"
                f"• 獎勵金幣: {config['reward']} 🪙",
                inline=True,
            )

            embed.add_field(
                name="💡 提示",
                value="我會告訴你猜的數字是太大還是太小！\n使用下方按鈕輸入你的猜測。",
                inline=True,
            )

            # 創建遊戲視圖
            view = GuessNumberView(self, session)

            await interaction.response.send_message(embed=embed, view=view)

        except Exception as e:
            logger.error(f"❌ 猜數字遊戲錯誤: {e}")
            await interaction.response.send_message("❌ 開始遊戲時發生錯誤。", ephemeral=True)

    # ========== 遊戲會話管理 ==========

    async def _get_user_active_session(self, user_id: int, guild_id: int) -> Optional[GameSession]:
        """獲取用戶活躍會話"""
        for session in self.active_sessions.values():
            if (
                session.player_id == user_id
                and session.guild_id == guild_id
                and session.status == "active"
            ):
                return session
        return None

    async def end_game_session(self, session: GameSession, won: bool = False, score: int = 0):
        """結束遊戲會話"""
        try:
            session.end_time = datetime.now(timezone.utc)
            session.status = "completed"
            session.score = score

            # 檢查成就
            await self.achievement_manager.check_game_achievements(
                session.player_id,
                session.guild_id,
                session.game_type,
                won,
                score,
            )

            # 移除活躍會話
            if session.game_id in self.active_sessions:
                del self.active_sessions[session.game_id]

            # 記錄到資料庫
            await self._save_game_result(session, won)

        except Exception as e:
            logger.error(f"❌ 結束遊戲會話錯誤: {e}")

    async def _save_game_result(self, session: GameSession, won: bool):
        """保存遊戲結果到資料庫"""
        try:
            async with db_pool.connection() as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute(
                        """
                        INSERT INTO game_results
                        (game_id, game_type, player_id, guild_id, channel_id,
                         start_time, end_time, won, score, game_data)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        ON DUPLICATE KEY UPDATE
                        end_time = VALUES(end_time),
                        won = VALUES(won),
                        score = VALUES(score)
                    """,
                        (
                            session.game_id,
                            session.game_type.value,
                            session.player_id,
                            session.guild_id,
                            session.channel_id,
                            session.start_time,
                            session.end_time,
                            won,
                            session.score,
                            json.dumps(session.data),
                        ),
                    )
                    await conn.commit()
        except Exception as e:
            logger.error(f"❌ 保存遊戲結果錯誤: {e}")

    # ========== 定時任務 ==========

    @tasks.loop(minutes=30)
    async def cleanup_sessions(self):
        """清理過期的遊戲會話"""
        try:
            current_time = datetime.now(timezone.utc)
            expired_sessions = []

            for game_id, session in self.active_sessions.items():
                # 超過30分鐘沒有活動的會話視為過期
                if (current_time - session.start_time).total_seconds() > 1800:
                    expired_sessions.append(game_id)

            # 清理過期會話
            for game_id in expired_sessions:
                session = self.active_sessions[game_id]
                session.status = "expired"
                await self._save_game_result(session, False)
                del self.active_sessions[game_id]

            if expired_sessions:
                logger.info(f"🧹 清理過期遊戲會話: {len(expired_sessions)} 個")

        except Exception as e:
            logger.error(f"❌ 清理遊戲會話錯誤: {e}")

    @tasks.loop(time=datetime.min.time())
    async def daily_reset(self):
        """每日重置任務"""
        try:
            logger.info("🔄 每日重置任務完成")

        except Exception as e:
            logger.error(f"❌ 每日重置任務錯誤: {e}")

    @cleanup_sessions.before_loop
    @daily_reset.before_loop
    async def before_tasks(self):
        """等待機器人準備完成"""
        await self.bot.wait_until_ready()


async def setup(bot):
    """設置 Cog"""
    await bot.add_cog(GameEntertainment(bot))
