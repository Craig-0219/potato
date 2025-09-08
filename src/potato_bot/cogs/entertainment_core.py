# bot/cogs/entertainment_core.py - 娛樂模組核心
"""
Discord Bot 娛樂模組 v2.3.0
提供各種小遊戲和娛樂功能，使用 Discord 原生 GUI 組件
"""

from datetime import datetime
from enum import Enum
from typing import Dict, Optional

import discord
from discord import app_commands
from discord.ext import commands

from potato_bot.utils.embed_builder import EmbedBuilder
from potato_bot.views.entertainment_views import (
    EntertainmentMenuView,
    GameLeaderboardView,
)
from potato_shared.logger import logger


class GameType(Enum):
    """遊戲類型"""

    GUESS_NUMBER = "guess_number"
    ROCK_PAPER_SCISSORS = "rock_paper_scissors"
    COIN_FLIP = "coin_flip"
    DICE_ROLL = "dice_roll"
    TRUTH_DARE = "truth_dare"
    QUIZ = "quiz"
    MEMORY_GAME = "memory_game"
    WORD_CHAIN = "word_chain"


class EntertainmentCore(commands.Cog):
    """娛樂功能核心"""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.active_games: Dict[int, Dict] = {}  # 進行中的遊戲
        self.user_stats: Dict[int, Dict] = {}  # 用戶統計
        self.daily_limits: Dict[int, int] = {}  # 每日遊戲限制

        # 遊戲配置
        self.game_config = {
            "daily_limit": 50,  # 每日遊戲次數限制
            "cooldown_seconds": 3,  # 遊戲冷卻時間
            "max_concurrent_games": 3,  # 最大同時進行遊戲數
            "points_multiplier": 1.0,  # 積分倍數
        }

        logger.info("🎮 娛樂模組核心初始化完成")

    def cog_check(self, ctx):
        """Cog檢查：確保在伺服器中使用"""
        return ctx.guild is not None

    async def get_user_stats(self, user_id: int) -> Dict:
        """獲取用戶統計資料"""
        if user_id not in self.user_stats:
            self.user_stats[user_id] = {
                "total_games": 0,
                "wins": 0,
                "losses": 0,
                "points": 0,
                "achievements": [],
                "favorite_game": None,
                "last_played": None,
                "streak": 0,
                "game_history": {},
            }
        return self.user_stats[user_id]

    async def update_user_stats(self, user_id: int, game_type: str, won: bool, points: int = 0):
        """更新用戶統計"""
        stats = await self.get_user_stats(user_id)
        stats["total_games"] += 1
        stats["last_played"] = datetime.now()
        stats["points"] += points

        if won:
            stats["wins"] += 1
            stats["streak"] += 1
        else:
            stats["losses"] += 1
            stats["streak"] = 0

        # 更新遊戲歷史
        if game_type not in stats["game_history"]:
            stats["game_history"][game_type] = {"played": 0, "won": 0}
        stats["game_history"][game_type]["played"] += 1
        if won:
            stats["game_history"][game_type]["won"] += 1

        # 檢查成就
        await self.check_achievements(user_id, stats)

    async def check_achievements(self, user_id: int, stats: Dict):
        """檢查並獎勵成就"""
        achievements = []

        # 首次遊戲
        if stats["total_games"] == 1:
            achievements.append("🎮 新手玩家")

        # 遊戲達人
        if stats["total_games"] >= 100:
            achievements.append("🏆 遊戲達人")

        # 連勝紀錄
        if stats["streak"] >= 5:
            achievements.append("🔥 連勝高手")

        # 積分里程碑
        if stats["points"] >= 1000:
            achievements.append("💎 積分大師")

        # 添加新成就
        for achievement in achievements:
            if achievement not in stats["achievements"]:
                stats["achievements"].append(achievement)

    async def check_daily_limit(self, user_id: int) -> bool:
        """檢查每日遊戲限制"""
        datetime.now().date()
        if user_id not in self.daily_limits:
            self.daily_limits[user_id] = 0

        # 重置每日計數
        # 實際應用中應該用資料庫存儲
        return self.daily_limits[user_id] < self.game_config["daily_limit"]

    # ========== 主要娛樂指令 ==========

    @app_commands.command(
        name="entertainment",
        description="🎮 開啟娛樂中心 - 各種小遊戲等你來玩！",
    )
    async def entertainment_center(self, interaction: discord.Interaction):
        """娛樂中心主菜單"""
        try:
            # 檢查每日限制
            if not await self.check_daily_limit(interaction.user.id):
                embed = EmbedBuilder.create_error_embed(
                    "每日遊戲次數已達上限",
                    f"您今天已經玩了 {self.game_config['daily_limit']} 次遊戲，請明天再來！",
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return

            # 獲取用戶統計
            stats = await self.get_user_stats(interaction.user.id)

            # 創建主菜單嵌入
            embed = EmbedBuilder.create_info_embed(
                "🎮 娛樂中心",
                "歡迎來到 Potato Bot 娛樂中心！選擇您想要的遊戲：",
            )

            # 添加用戶統計信息
            embed.add_field(
                name="📊 您的統計",
                value=f"🎯 總遊戲: {stats['total_games']}\n"
                f"🏆 勝利: {stats['wins']}\n"
                f"💎 積分: {stats['points']}\n"
                f"🔥 連勝: {stats['streak']}",
                inline=True,
            )

            # 添加遊戲選項說明
            embed.add_field(
                name="🎲 可用遊戲",
                value="🔢 猜數字遊戲\n"
                "✂️ 剪刀石頭布\n"
                "🪙 拋硬幣\n"
                "🎲 骰子遊戲\n"
                "❓ 真心話大冒險\n"
                "🧠 知識問答\n"
                "🏆 排行榜",
                inline=True,
            )

            # 添加每日限制信息
            remaining = self.game_config["daily_limit"] - self.daily_limits.get(
                interaction.user.id, 0
            )
            embed.add_field(
                name="⏰ 今日剩餘",
                value=f"{remaining} 次遊戲機會",
                inline=True,
            )

            # 創建互動視圖
            view = EntertainmentMenuView(self, interaction.user.id)

            await interaction.response.send_message(embed=embed, view=view, ephemeral=False)
            logger.info(f"娛樂中心已為用戶 {interaction.user.name} 開啟")

        except Exception as e:
            logger.error(f"娛樂中心錯誤: {e}")
            embed = EmbedBuilder.create_error_embed("系統錯誤", "娛樂中心暫時無法使用，請稍後再試")
            await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="game_stats", description="📊 查看您的遊戲統計")
    async def game_stats(
        self,
        interaction: discord.Interaction,
        user: Optional[discord.Member] = None,
    ):
        """查看遊戲統計"""
        target_user = user or interaction.user
        stats = await self.get_user_stats(target_user.id)

        embed = EmbedBuilder.create_info_embed(f"📊 {target_user.display_name} 的遊戲統計", "")

        # 基本統計
        win_rate = (stats["wins"] / stats["total_games"] * 100) if stats["total_games"] > 0 else 0
        embed.add_field(
            name="🎮 基本統計",
            value=f"總遊戲: {stats['total_games']}\n"
            f"勝利: {stats['wins']}\n"
            f"失敗: {stats['losses']}\n"
            f"勝率: {win_rate:.1f}%\n"
            f"積分: {stats['points']}\n"
            f"當前連勝: {stats['streak']}",
            inline=True,
        )

        # 成就系統
        if stats["achievements"]:
            achievements_text = "\n".join(stats["achievements"])
        else:
            achievements_text = "暫無成就"

        embed.add_field(name="🏆 獲得成就", value=achievements_text, inline=True)

        # 遊戲歷史
        if stats["game_history"]:
            history_text = ""
            for game, data in stats["game_history"].items():
                rate = (data["won"] / data["played"] * 100) if data["played"] > 0 else 0
                history_text += f"{game}: {data['played']}場 ({rate:.1f}%勝率)\n"
        else:
            history_text = "暫無遊戲記錄"

        embed.add_field(name="📈 遊戲記錄", value=history_text, inline=False)

        if stats["last_played"]:
            embed.set_footer(text=f"上次遊戲: {stats['last_played'].strftime('%Y-%m-%d %H:%M')}")

        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="leaderboard", description="🏆 查看遊戲排行榜")
    async def leaderboard(self, interaction: discord.Interaction):
        """顯示遊戲排行榜"""
        # 對用戶統計進行排序
        sorted_users = sorted(
            self.user_stats.items(),
            key=lambda x: (x[1]["points"], x[1]["wins"], x[1]["total_games"]),
            reverse=True,
        )

        embed = EmbedBuilder.create_info_embed("🏆 遊戲排行榜", "最強玩家排名（按積分排序）")

        leaderboard_text = ""
        for i, (user_id, stats) in enumerate(sorted_users[:10], 1):
            try:
                user = self.bot.get_user(user_id)
                username = user.display_name if user else f"User#{user_id}"

                medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else f"{i}."
                leaderboard_text += f"{medal} {username}\n"
                leaderboard_text += f"   💎 {stats['points']}分 | 🏆 {stats['wins']}勝 | 🎮 {stats['total_games']}場\n\n"

            except Exception:
                continue

        if not leaderboard_text:
            leaderboard_text = "暫無排行榜數據"

        embed.description = leaderboard_text

        # 添加用戶排名
        user_rank = None
        for i, (user_id, _) in enumerate(sorted_users, 1):
            if user_id == interaction.user.id:
                user_rank = i
                break

        if user_rank:
            embed.set_footer(text=f"您目前排名第 {user_rank} 位")
        else:
            embed.set_footer(text="開始遊戲來獲得排名！")

        view = GameLeaderboardView(self)
        await interaction.response.send_message(embed=embed, view=view)

    @app_commands.command(name="daily_rewards", description="🎁 領取每日獎勵")
    async def daily_rewards(self, interaction: discord.Interaction):
        """每日獎勵系統"""
        stats = await self.get_user_stats(interaction.user.id)

        # 檢查是否已領取今日獎勵
        last_reward = stats.get("last_daily_reward")
        today = datetime.now().date()

        if last_reward and last_reward == today:
            embed = EmbedBuilder.create_warning_embed(
                "已領取今日獎勵", "您今天已經領取過每日獎勵了，明天再來吧！"
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        # 計算獎勵
        base_reward = 50
        streak_bonus = stats.get("daily_streak", 0) * 10
        total_reward = base_reward + streak_bonus

        # 更新統計
        stats["points"] += total_reward
        stats["last_daily_reward"] = today
        stats["daily_streak"] = stats.get("daily_streak", 0) + 1

        embed = EmbedBuilder.create_success_embed(
            "🎁 每日獎勵已領取！", f"恭喜獲得 {total_reward} 積分！"
        )

        embed.add_field(
            name="獎勵詳情",
            value=f"基礎獎勵: {base_reward}分\n"
            f"連續獎勵: {streak_bonus}分\n"
            f"總計: {total_reward}分",
            inline=True,
        )

        embed.add_field(
            name="連續天數",
            value=f"🔥 {stats['daily_streak']} 天",
            inline=True,
        )

        await interaction.response.send_message(embed=embed)


async def setup(bot):
    await bot.add_cog(EntertainmentCore(bot))
    logger.info("✅ 娛樂模組核心已載入")
