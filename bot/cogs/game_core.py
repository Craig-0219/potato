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

import asyncio
import json
import random
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

import discord
from discord import app_commands
from discord.ext import commands, tasks

# 遊戲相關導入
from bot.db.pool import db_pool
from bot.services.achievement_manager import AchievementManager
from bot.services.cross_platform_economy import cross_platform_economy
from bot.services.economy_manager import EconomyManager
from bot.services.game_manager import GameManager
from bot.utils.embed_builder import EmbedBuilder
from bot.views.game_views import (
    CoinFlipView,
    GameMenuView,
    GuessNumberView,
    RockPaperScissorsView,
    RouletteView,
    TriviaView,
)
from shared.cache_manager import cache_manager, cached
from shared.logger import logger
from shared.prometheus_metrics import prometheus_metrics, track_command_execution


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
        self.economy_manager = EconomyManager()
        self.achievement_manager = AchievementManager()

        # 活躍的遊戲會話
        self.active_sessions: Dict[str, GameSession] = {}

        # 遊戲配置
        self.game_configs = {
            GameType.GUESS_NUMBER: {
                "min_number": 1,
                "max_number": 100,
                "max_attempts": 6,
                "rewards": {"easy": 50, "medium": 100, "hard": 200},
            },
            GameType.ROCK_PAPER_SCISSORS: {
                "choices": ["rock", "paper", "scissors"],
                "rewards": {"win": 30, "draw": 10},
            },
            GameType.COIN_FLIP: {"min_bet": 10, "max_bet": 1000, "win_multiplier": 2.0},
            GameType.ROULETTE: {
                "min_bet": 20,
                "max_bet": 500,
                "payouts": {"number": 35, "color": 2, "even_odd": 2, "dozen": 3},
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
            # 記錄指令執行
            track_command_execution("games", interaction.guild.id)

            # 獲取用戶經濟狀態
            user_economy = await self.economy_manager.get_user_economy(
                interaction.user.id, interaction.guild.id
            )

            # 創建遊戲選單嵌入
            embed = EmbedBuilder.build(
                title="🎮 遊戲娛樂中心", description="選擇您想要遊玩的遊戲！", color=0x00FF88
            )

            embed.add_field(
                name="💰 您的資產",
                value=f"🪙 金幣: {user_economy.get('coins', 0):,}\n"
                f"💎 寶石: {user_economy.get('gems', 0):,}\n"
                f"⭐ 經驗: {user_economy.get('experience', 0):,}",
                inline=True,
            )

            embed.add_field(
                name="🏆 今日狀態",
                value=f"✅ 每日簽到: {'已完成' if user_economy.get('daily_claimed') else '未完成'}\n"
                f"🎯 遊戲次數: {user_economy.get('daily_games', 0)}/10\n"
                f"🏅 勝利次數: {user_economy.get('daily_wins', 0)}",
                inline=True,
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
            view = GameMenuView(self, user_economy)

            await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

        except Exception as e:
            logger.error(f"❌ 遊戲選單錯誤: {e}")
            await interaction.response.send_message("❌ 開啟遊戲選單時發生錯誤。", ephemeral=True)

    # ========== 經濟系統指令 ==========

    @app_commands.command(name="daily", description="每日簽到獎勵")
    async def daily_checkin(self, interaction: discord.Interaction):
        """每日簽到"""
        try:
            user_id = interaction.user.id
            guild_id = interaction.guild.id

            # 檢查是否已簽到
            last_checkin = await self.economy_manager.get_last_checkin(user_id, guild_id)
            today = datetime.now(timezone.utc).date()

            if last_checkin and last_checkin.date() >= today:
                embed = EmbedBuilder.build(
                    title="⏰ 已完成簽到",
                    description="您今天已經完成每日簽到了！明天再來吧~",
                    color=0xFFAA00,
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return

            # 計算連續簽到天數
            streak = await self.economy_manager.calculate_checkin_streak(user_id, guild_id)

            # 計算獎勵
            base_coins = 100
            streak_bonus = min(streak * 10, 500)  # 最多額外500
            total_coins = base_coins + streak_bonus

            # 隨機額外獎勵
            bonus_gems = 0
            if random.random() < 0.1:  # 10% 機率獲得寶石
                bonus_gems = random.randint(5, 20)

            # 發放獎勵
            await self.economy_manager.add_coins(user_id, guild_id, total_coins)
            if bonus_gems > 0:
                await self.economy_manager.add_gems(user_id, guild_id, bonus_gems)

            # 記錄簽到
            await self.economy_manager.record_checkin(user_id, guild_id)

            # 創建獎勵嵌入
            embed = EmbedBuilder.build(
                title="✅ 每日簽到成功！", description=f"感謝您的持續參與！", color=0x00FF00
            )

            embed.add_field(
                name="🎁 今日獎勵",
                value=f"🪙 基礎金幣: {base_coins:,}\n"
                f"🔥 連續獎勵: {streak_bonus:,} (第{streak}天)\n"
                + (f"💎 幸運寶石: {bonus_gems}" if bonus_gems > 0 else ""),
                inline=True,
            )

            embed.add_field(
                name="📊 統計資訊",
                value=f"🔥 連續簽到: {streak} 天\n"
                f"🏆 累計簽到: {await self.economy_manager.get_total_checkins(user_id, guild_id)} 天",
                inline=True,
            )

            # 檢查成就
            achievements = await self.achievement_manager.check_daily_achievements(
                user_id, guild_id, streak
            )

            if achievements:
                achievement_text = "\n".join([f"🏆 {ach['name']}" for ach in achievements])
                embed.add_field(name="🎊 獲得成就", value=achievement_text, inline=False)

            await interaction.response.send_message(embed=embed)

            # 記錄指標
            prometheus_metrics.increment_counter(
                "potato_bot_daily_checkins_total", {"guild": str(guild_id)}
            )

        except Exception as e:
            logger.error(f"❌ 每日簽到錯誤: {e}")
            await interaction.response.send_message(
                "❌ 簽到時發生錯誤，請稍後再試。", ephemeral=True
            )

    @app_commands.command(name="balance", description="查看錢包餘額")
    async def check_balance(self, interaction: discord.Interaction, user: discord.User = None):
        """查看餘額"""
        try:
            target_user = user or interaction.user
            user_id = target_user.id
            guild_id = interaction.guild.id

            # 獲取經濟狀態
            economy = await self.economy_manager.get_user_economy(user_id, guild_id)

            # 獲取排名資訊
            coin_rank = await self.economy_manager.get_user_rank(user_id, guild_id, "coins")
            level_info = await self.economy_manager.calculate_level(economy.get("experience", 0))

            embed = EmbedBuilder.build(
                title=f"💰 {target_user.display_name} 的錢包", color=0xFFD700
            )

            # 設置頭像
            embed.set_thumbnail(url=target_user.display_avatar.url)

            # 資產資訊
            embed.add_field(
                name="💳 資產狀況",
                value=f"🪙 金幣: {economy.get('coins', 0):,}\n"
                f"💎 寶石: {economy.get('gems', 0):,}\n"
                f"🎫 遊戲券: {economy.get('tickets', 0):,}",
                inline=True,
            )

            # 等級資訊
            embed.add_field(
                name="📈 等級資訊",
                value=f"⭐ 等級: {level_info['level']}\n"
                f"🎯 經驗: {economy.get('experience', 0):,}\n"
                f"📊 下級需要: {level_info['next_level_exp']:,}",
                inline=True,
            )

            # 統計資訊
            embed.add_field(
                name="🏆 遊戲統計",
                value=f"🎮 總遊戲: {economy.get('total_games', 0):,}\n"
                f"🏅 勝利數: {economy.get('total_wins', 0):,}\n"
                f"📈 勝率: {economy.get('win_rate', 0):.1f}%",
                inline=True,
            )

            # 排名資訊
            embed.add_field(
                name="🏆 伺服器排名",
                value=f"💰 金幣排名: #{coin_rank}\n"
                f"⭐ 等級排名: #{await self.economy_manager.get_user_rank(user_id, guild_id, 'experience')}",
                inline=True,
            )

            # 每日狀態
            embed.add_field(
                name="📅 今日狀態",
                value=f"✅ 簽到: {'已完成' if economy.get('daily_claimed') else '未完成'}\n"
                f"🎮 遊戲: {economy.get('daily_games', 0)}/10\n"
                f"🏆 勝利: {economy.get('daily_wins', 0)}",
                inline=True,
            )

            await interaction.response.send_message(embed=embed, ephemeral=user is None)

        except Exception as e:
            logger.error(f"❌ 查看餘額錯誤: {e}")
            await interaction.response.send_message("❌ 查看餘額時發生錯誤。", ephemeral=True)

    @app_commands.command(name="leaderboard", description="查看排行榜")
    @app_commands.describe(category="排行榜類型")
    @app_commands.choices(
        category=[
            app_commands.Choice(name="金幣排行", value="coins"),
            app_commands.Choice(name="等級排行", value="experience"),
            app_commands.Choice(name="勝場排行", value="wins"),
            app_commands.Choice(name="遊戲次數", value="games"),
        ]
    )
    async def leaderboard(self, interaction: discord.Interaction, category: str = "coins"):
        """排行榜"""
        try:
            guild_id = interaction.guild.id

            # 獲取排行榜數據
            leaderboard_data = await self.economy_manager.get_leaderboard(
                guild_id, category, limit=10
            )

            category_names = {
                "coins": "💰 金幣排行榜",
                "experience": "⭐ 等級排行榜",
                "wins": "🏆 勝場排行榜",
                "games": "🎮 遊戲次數排行榜",
            }

            category_emojis = {"coins": "🪙", "experience": "⭐", "wins": "🏅", "games": "🎯"}

            embed = EmbedBuilder.build(
                title=category_names.get(category, "📊 排行榜"),
                description=f"🏆 {interaction.guild.name} 的頂尖玩家",
                color=0xFFD700,
            )

            if not leaderboard_data:
                embed.add_field(
                    name="📝 暫無數據", value="還沒有玩家參與遊戲，快來成為第一名！", inline=False
                )
            else:
                rank_text = []
                for i, entry in enumerate(leaderboard_data[:10], 1):
                    user = self.bot.get_user(entry["user_id"])
                    username = user.display_name if user else f"用戶{entry['user_id']}"

                    # 排名表情
                    rank_emoji = {1: "🥇", 2: "🥈", 3: "🥉"}.get(i, f"{i}.")

                    # 格式化數值
                    value = entry[category]
                    if category == "experience":
                        level = await self.economy_manager.calculate_level(value)
                        value_text = f"等級 {level['level']} ({value:,} XP)"
                    else:
                        value_text = f"{value:,}"

                    rank_text.append(
                        f"{rank_emoji} {username}\n{category_emojis[category]} {value_text}"
                    )

                # 分成兩欄顯示
                mid_point = len(rank_text) // 2 + 1
                embed.add_field(
                    name="🏆 前5名", value="\n\n".join(rank_text[:mid_point]), inline=True
                )

                if len(rank_text) > mid_point:
                    embed.add_field(
                        name="🎖️ 6-10名", value="\n\n".join(rank_text[mid_point:]), inline=True
                    )

            # 用戶排名
            user_rank = await self.economy_manager.get_user_rank(
                interaction.user.id, guild_id, category
            )
            user_economy = await self.economy_manager.get_user_economy(
                interaction.user.id, guild_id
            )

            user_value = user_economy.get(category, 0)
            if category == "experience":
                level = await self.economy_manager.calculate_level(user_value)
                user_value_text = f"等級 {level['level']}"
            else:
                user_value_text = f"{user_value:,}"

            embed.add_field(
                name="📍 您的排名",
                value=f"排名: #{user_rank}\n{category_emojis[category]} {user_value_text}",
                inline=False,
            )

            embed.set_footer(
                text=f"數據更新時間: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}"
            )

            await interaction.response.send_message(embed=embed)

        except Exception as e:
            logger.error(f"❌ 排行榜錯誤: {e}")
            await interaction.response.send_message("❌ 獲取排行榜時發生錯誤。", ephemeral=True)

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

                rarity_order = ["legendary", "epic", "rare", "uncommon", "common"]

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
            user_id = interaction.user.id
            guild_id = interaction.guild.id

            if achievement_id:
                # 查看特定成就進度
                progress = await self.achievement_manager.get_achievement_progress(
                    user_id, guild_id, achievement_id
                )

                if not progress:
                    await interaction.response.send_message("❌ 未找到該成就。", ephemeral=True)
                    return

                achievement_def = self.achievement_manager.achievements.get(achievement_id)
                if not achievement_def:
                    await interaction.response.send_message("❌ 成就定義不存在。", ephemeral=True)
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

                embed.add_field(
                    name="🎁 獎勵",
                    value=f"🪙 金幣: {achievement_def.rewards.get('coins', 0)}\n"
                    f"💎 寶石: {achievement_def.rewards.get('gems', 0)}\n"
                    f"⭐ 經驗: {achievement_def.rewards.get('experience', 0)}",
                    inline=True,
                )

            else:
                # 顯示所有未完成成就的進度
                embed = EmbedBuilder.build(
                    title="🎯 成就進度總覽", description="您的成就解鎖進度", color=0x4169E1
                )

                incomplete_count = 0
                for ach_id, ach_def in self.achievement_manager.achievements.items():
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
                    embed.add_field(name="🎉 恭喜！", value="您已經完成所有成就！", inline=False)
                elif incomplete_count > 8:
                    embed.set_footer(text=f"還有 {incomplete_count - 8} 個成就未顯示")

            await interaction.response.send_message(embed=embed, ephemeral=True)

        except Exception as e:
            logger.error(f"❌ 查看成就進度錯誤: {e}")
            await interaction.response.send_message("❌ 查看成就進度時發生錯誤。", ephemeral=True)

    def _create_progress_bar(self, progress: float, length: int = 10) -> str:
        """創建進度條"""
        filled = int((progress / 100) * length)
        bar = "█" * filled + "░" * (length - filled)
        return f"[{bar}]"

    # ========== 跨平台經濟系統 ==========

    @app_commands.command(name="link_minecraft", description="綁定Minecraft帳號以同步經濟數據")
    @app_commands.describe(minecraft_username="您的Minecraft用戶名")
    async def link_minecraft_account(
        self, interaction: discord.Interaction, minecraft_username: str
    ):
        """綁定Minecraft帳號"""
        try:
            # 這裡需要將用戶名轉換為UUID，簡化處理暫時使用用戶名
            # 實際環境中應該調用Mojang API獲取UUID
            minecraft_uuid = f"minecraft_{minecraft_username}"  # 簡化UUID

            result = await cross_platform_economy.link_accounts(
                discord_id=interaction.user.id,
                minecraft_uuid=minecraft_uuid,
                guild_id=interaction.guild.id,
            )

            if result["success"]:
                embed = EmbedBuilder.build(
                    title="🔗 帳號綁定成功！",
                    description=f"您的Discord帳號已成功綁定到Minecraft帳號 `{minecraft_username}`",
                    color=0x00FF00,
                )

                embed.add_field(
                    name="✅ 綁定信息",
                    value=f"Discord: <@{interaction.user.id}>\n"
                    f"Minecraft: {minecraft_username}\n"
                    f"同步狀態: {'已完成' if result.get('sync_completed') else '待同步'}",
                    inline=True,
                )

                embed.add_field(
                    name="🎮 跨平台功能",
                    value="• 經濟數據自動同步\n"
                    "• 成就進度共享\n"
                    "• 排行榜統一計算\n"
                    "• 未來更多功能...",
                    inline=True,
                )

                embed.add_field(
                    name="📋 後續步驟",
                    value="使用 `/sync_economy` 可手動同步數據\n"
                    "使用 `/cross_platform_status` 查看同步狀態",
                    inline=False,
                )

            else:
                embed = EmbedBuilder.build(
                    title="❌ 帳號綁定失敗",
                    description=result.get("error", "未知錯誤"),
                    color=0xFF0000,
                )

                if "已綁定" in result.get("error", ""):
                    embed.add_field(
                        name="💡 提示",
                        value="如需重新綁定，請先使用 `/unlink_minecraft` 解除當前綁定",
                        inline=False,
                    )

            await interaction.response.send_message(embed=embed, ephemeral=True)

        except Exception as e:
            logger.error(f"❌ 綁定Minecraft帳號錯誤: {e}")
            await interaction.response.send_message(
                "❌ 綁定過程中發生錯誤，請稍後再試。", ephemeral=True
            )

    @app_commands.command(name="unlink_minecraft", description="解除Minecraft帳號綁定")
    async def unlink_minecraft_account(self, interaction: discord.Interaction):
        """解除Minecraft帳號綁定"""
        try:
            result = await cross_platform_economy.unlink_accounts(discord_id=interaction.user.id)

            if result["success"]:
                embed = EmbedBuilder.build(
                    title="🔓 帳號解綁成功",
                    description="您的Discord與Minecraft帳號綁定已解除",
                    color=0x00FF00,
                )

                embed.add_field(
                    name="⚠️ 注意事項",
                    value="• 經濟數據將不再同步\n" "• 已同步的數據會保留\n" "• 可以隨時重新綁定",
                    inline=False,
                )
            else:
                embed = EmbedBuilder.build(
                    title="❌ 解綁失敗",
                    description=result.get("error", "未找到綁定記錄"),
                    color=0xFF0000,
                )

            await interaction.response.send_message(embed=embed, ephemeral=True)

        except Exception as e:
            logger.error(f"❌ 解除Minecraft綁定錯誤: {e}")
            await interaction.response.send_message(
                "❌ 解綁過程中發生錯誤，請稍後再試。", ephemeral=True
            )

    @app_commands.command(name="sync_economy", description="手動同步經濟數據到Minecraft")
    @app_commands.describe(direction="同步方向")
    @app_commands.choices(
        direction=[
            app_commands.Choice(name="Discord → Minecraft", value="to_minecraft"),
            app_commands.Choice(name="Minecraft → Discord", value="from_minecraft"),
        ]
    )
    async def sync_economy_data(
        self, interaction: discord.Interaction, direction: str = "to_minecraft"
    ):
        """手動同步經濟數據"""
        try:
            await interaction.response.defer(ephemeral=True)

            result = await cross_platform_economy.sync_user_economy(
                discord_id=interaction.user.id, guild_id=interaction.guild.id, direction=direction
            )

            if result["success"]:
                embed = EmbedBuilder.build(
                    title="🔄 數據同步成功！",
                    description=f"經濟數據已成功同步：{direction.replace('_', ' → ').title()}",
                    color=0x00FF00,
                )

                if direction == "to_minecraft" and "discord_data" in result:
                    discord_data = result["discord_data"]
                    embed.add_field(
                        name="📊 已同步數據",
                        value=f"🪙 金幣: {discord_data.get('coins', 0):,}\n"
                        f"💎 寶石: {discord_data.get('gems', 0):,}\n"
                        f"⭐ 經驗: {discord_data.get('experience', 0):,}\n"
                        f"🏆 等級: {(await self.economy_manager.calculate_level(discord_data.get('experience', 0)))['level']}",
                        inline=True,
                    )

                embed.add_field(name="⏰ 同步時間", value=f"<t:{int(time.time())}:R>", inline=True)

                if result.get("cached"):
                    embed.add_field(
                        name="📦 緩存狀態",
                        value="數據已緩存，將在Minecraft服務器上線時自動同步",
                        inline=False,
                    )
            else:
                embed = EmbedBuilder.build(
                    title="❌ 數據同步失敗",
                    description=result.get("error", "未知錯誤"),
                    color=0xFF0000,
                )

                if "未綁定" in result.get("error", ""):
                    embed.add_field(
                        name="💡 解決方法",
                        value="請先使用 `/link_minecraft` 綁定您的Minecraft帳號",
                        inline=False,
                    )

            await interaction.followup.send(embed=embed, ephemeral=True)

        except Exception as e:
            logger.error(f"❌ 同步經濟數據錯誤: {e}")
            await interaction.followup.send("❌ 同步過程中發生錯誤，請稍後再試。", ephemeral=True)

    @app_commands.command(name="cross_platform_status", description="查看跨平台狀態")
    async def cross_platform_status(self, interaction: discord.Interaction):
        """查看跨平台同步狀態"""
        try:
            # 獲取綁定信息
            link_info = await cross_platform_economy._get_account_link(
                discord_id=interaction.user.id
            )

            embed = EmbedBuilder.build(
                title="🌐 跨平台狀態", description="您的跨平台整合狀態", color=0x4169E1
            )

            if link_info:
                embed.add_field(name="🔗 綁定狀態", value="✅ 已綁定", inline=True)

                embed.add_field(
                    name="🎮 Minecraft帳號", value=f"`{link_info['minecraft_uuid']}`", inline=True
                )

                embed.add_field(
                    name="📅 綁定時間",
                    value=f"<t:{int(link_info['linked_at'].timestamp())}:R>",
                    inline=True,
                )

                # 獲取交易記錄
                transactions = await cross_platform_economy.get_user_transactions(
                    str(interaction.user.id), limit=5
                )

                if transactions:
                    recent_transactions = []
                    for trans in transactions[:3]:
                        trans_time = trans["timestamp"]
                        recent_transactions.append(
                            f"• {trans['currency_type']} {trans['amount']:+} "
                            f"({trans['transaction_type']}) "
                            f"<t:{int(trans_time.timestamp())}:R>"
                        )

                    embed.add_field(
                        name="📋 最近交易",
                        value=(
                            "\n".join(recent_transactions)
                            if recent_transactions
                            else "暫無交易記錄"
                        ),
                        inline=False,
                    )

                embed.add_field(
                    name="⚙️ 可用操作",
                    value="• `/sync_economy` - 手動同步數據\n"
                    "• `/unlink_minecraft` - 解除綁定\n"
                    "• `/cross_platform_stats` - 詳細統計",
                    inline=False,
                )
            else:
                embed.add_field(name="🔗 綁定狀態", value="❌ 未綁定", inline=True)

                embed.add_field(
                    name="🚀 開始使用",
                    value="使用 `/link_minecraft` 綁定您的Minecraft帳號",
                    inline=False,
                )

                embed.add_field(
                    name="🎁 跨平台優勢",
                    value="• 經濟數據跨平台同步\n"
                    "• 成就進度共享\n"
                    "• 統一排行榜計算\n"
                    "• 更多功能持續開發中...",
                    inline=False,
                )

            await interaction.response.send_message(embed=embed, ephemeral=True)

        except Exception as e:
            logger.error(f"❌ 查看跨平台狀態錯誤: {e}")
            await interaction.response.send_message("❌ 獲取狀態時發生錯誤。", ephemeral=True)

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
                    "❌ 您已經有一個進行中的遊戲！請先完成當前遊戲。", ephemeral=True
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

            # 記錄遊戲開始
            await self.economy_manager.increment_daily_games(
                interaction.user.id, interaction.guild.id
            )

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

            # 發放獎勵
            if won and session.data.get("reward", 0) > 0:
                reward = session.data["reward"]
                await self.economy_manager.add_coins(session.player_id, session.guild_id, reward)

                # 增加經驗
                exp_reward = reward // 2
                await self.economy_manager.add_experience(
                    session.player_id, session.guild_id, exp_reward
                )

                # 更新勝利統計
                await self.economy_manager.increment_daily_wins(session.player_id, session.guild_id)

            # 檢查成就
            await self.achievement_manager.check_game_achievements(
                session.player_id, session.guild_id, session.game_type, won, score
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
            # 重置每日統計
            await self.economy_manager.reset_daily_stats()

            # 更新排行榜快取
            await self._update_leaderboard_cache()

            logger.info("🔄 每日重置任務完成")

        except Exception as e:
            logger.error(f"❌ 每日重置任務錯誤: {e}")

    async def _update_leaderboard_cache(self):
        """更新排行榜快取"""
        try:
            # 清理排行榜相關快取
            await cache_manager.clear_all("leaderboard:*")

            # 預載前10名的排行榜
            for guild in self.bot.guilds:
                for category in ["coins", "experience", "wins", "games"]:
                    await self.economy_manager.get_leaderboard(guild.id, category, 10)

        except Exception as e:
            logger.error(f"❌ 更新排行榜快取錯誤: {e}")

    @cleanup_sessions.before_loop
    @daily_reset.before_loop
    async def before_tasks(self):
        """等待機器人準備完成"""
        await self.bot.wait_until_ready()


async def setup(bot):
    """設置 Cog"""
    # 確保資料庫表格存在
    await _ensure_game_tables()
    # 確保成就表格存在
    from bot.services.achievement_manager import ensure_achievement_tables

    await ensure_achievement_tables()
    await bot.add_cog(GameEntertainment(bot))


async def _ensure_game_tables():
    """確保遊戲相關表格存在"""
    try:
        async with db_pool.connection() as conn:
            async with conn.cursor() as cursor:
                # 遊戲結果表
                await cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS game_results (
                        game_id VARCHAR(255) PRIMARY KEY,
                        game_type VARCHAR(50) NOT NULL,
                        player_id BIGINT NOT NULL,
                        guild_id BIGINT NOT NULL,
                        channel_id BIGINT NOT NULL,
                        start_time TIMESTAMP NOT NULL,
                        end_time TIMESTAMP NULL,
                        won BOOLEAN DEFAULT FALSE,
                        score INT DEFAULT 0,
                        game_data JSON,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

                        INDEX idx_player_guild (player_id, guild_id),
                        INDEX idx_game_type (game_type),
                        INDEX idx_start_time (start_time)
                    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
                """
                )

                # 用戶經濟表
                await cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS user_economy (
                        user_id BIGINT NOT NULL,
                        guild_id BIGINT NOT NULL,
                        coins BIGINT DEFAULT 0,
                        gems INT DEFAULT 0,
                        tickets INT DEFAULT 0,
                        experience BIGINT DEFAULT 0,
                        total_games INT DEFAULT 0,
                        total_wins INT DEFAULT 0,
                        daily_games INT DEFAULT 0,
                        daily_wins INT DEFAULT 0,
                        daily_claimed BOOLEAN DEFAULT FALSE,
                        last_checkin TIMESTAMP NULL,
                        last_daily_reset DATE NULL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

                        PRIMARY KEY (user_id, guild_id),
                        INDEX idx_coins (coins DESC),
                        INDEX idx_experience (experience DESC),
                        INDEX idx_last_checkin (last_checkin)
                    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
                """
                )

                await conn.commit()
                logger.info("✅ 遊戲相關表格檢查完成")

    except Exception as e:
        logger.error(f"❌ 建立遊戲表格失敗: {e}")
        raise
