# bot/views/lottery_dashboard_views.py
"""
抽獎統計儀表板視圖
提供詳細的抽獎系統統計和分析功能
"""

from datetime import datetime, timedelta
from typing import Any, Dict, List

import discord
from discord import ui

from bot.services.lottery_manager import LotteryManager
from bot.utils.embed_builder import EmbedBuilder
from shared.logger import logger


class LotteryStatsDashboardView(ui.View):
    """抽獎統計儀表板視圖"""

    def __init__(self, guild_id: int):
        super().__init__(timeout=300)
        self.guild_id = guild_id
        self.lottery_manager = LotteryManager()
        self.current_period = 30  # 預設30天

    @ui.select(
        placeholder="選擇統計時間範圍...",
        options=[
            discord.SelectOption(
                label="最近 7 天",
                description="查看近一週的抽獎統計",
                emoji="📅",
                value="7",
            ),
            discord.SelectOption(
                label="最近 30 天",
                description="查看近一個月的抽獎統計",
                emoji="📊",
                value="30",
            ),
            discord.SelectOption(
                label="最近 90 天",
                description="查看近三個月的抽獎統計",
                emoji="📈",
                value="90",
            ),
            discord.SelectOption(
                label="最近 365 天",
                description="查看近一年的抽獎統計",
                emoji="📋",
                value="365",
            ),
        ],
    )
    async def period_select(self, interaction: discord.Interaction, select: ui.Select):
        """選擇統計時間範圍"""
        try:
            self.current_period = int(select.values[0])
            await interaction.response.defer()

            # 獲取統計資料
            stats = await self.lottery_manager.dao.get_lottery_statistics(
                self.guild_id, self.current_period
            )

            # 創建統計嵌入
            embed = await self._create_stats_embed(stats, self.current_period)

            await interaction.followup.edit_message(interaction.message.id, embed=embed, view=self)

        except Exception as e:
            logger.error(f"更新統計時間範圍失敗: {e}")
            await interaction.followup.send("❌ 更新統計資料時發生錯誤", ephemeral=True)

    @ui.button(label="🔄 刷新數據", style=discord.ButtonStyle.secondary, emoji="🔄")
    async def refresh_stats(self, interaction: discord.Interaction, button: ui.Button):
        """刷新統計數據"""
        try:
            await interaction.response.defer()

            # 獲取最新統計資料
            stats = await self.lottery_manager.dao.get_lottery_statistics(
                self.guild_id, self.current_period
            )

            # 創建統計嵌入
            embed = await self._create_stats_embed(stats, self.current_period)
            embed.set_footer(text=f"📊 數據已刷新 • {datetime.now().strftime('%H:%M:%S')}")

            await interaction.followup.edit_message(interaction.message.id, embed=embed, view=self)

        except Exception as e:
            logger.error(f"刷新統計數據失敗: {e}")
            await interaction.followup.send("❌ 刷新統計數據時發生錯誤", ephemeral=True)

    @ui.button(label="🏆 中獎排行榜", style=discord.ButtonStyle.primary, emoji="🏆")
    async def winners_leaderboard(self, interaction: discord.Interaction, button: ui.Button):
        """顯示中獎排行榜"""
        try:
            await interaction.response.defer(ephemeral=True)

            # 獲取中獎排行榜資料
            leaderboard = await self._get_winners_leaderboard(self.current_period)

            if not leaderboard:
                await interaction.followup.send("📊 在選定時間範圍內沒有中獎記錄", ephemeral=True)
                return

            embed = EmbedBuilder.create_info_embed(f"🏆 中獎排行榜 (最近 {self.current_period} 天)")

            leaderboard_text = ""
            medals = ["🥇", "🥈", "🥉"]

            for i, (user_id, username, win_count) in enumerate(leaderboard[:10]):
                medal = medals[i] if i < 3 else f"{i+1}."
                leaderboard_text += f"{medal} <@{user_id}> - {win_count} 次中獎\n"

            embed.add_field(name="🎯 幸運之星", value=leaderboard_text, inline=False)

            if len(leaderboard) > 10:
                embed.set_footer(text=f"顯示前 10 名，共 {len(leaderboard)} 名中獎者")

            await interaction.followup.send(embed=embed, ephemeral=True)

        except Exception as e:
            logger.error(f"獲取中獎排行榜失敗: {e}")
            await interaction.followup.send("❌ 獲取排行榜時發生錯誤", ephemeral=True)

    @ui.button(label="📋 詳細報告", style=discord.ButtonStyle.secondary, emoji="📋")
    async def detailed_report(self, interaction: discord.Interaction, button: ui.Button):
        """生成詳細報告"""
        try:
            await interaction.response.defer(ephemeral=True)

            # 生成詳細報告
            report = await self._generate_detailed_report(self.current_period)

            # 創建報告嵌入
            embed = EmbedBuilder.create_info_embed(
                f"📋 詳細抽獎報告 (最近 {self.current_period} 天)"
            )

            # 活動統計
            embed.add_field(
                name="🎯 活動統計",
                value=f"**總抽獎數**: {report.get('total_lotteries', 0)}\n"
                f"**已完成**: {report.get('completed_lotteries', 0)}\n"
                f"**進行中**: {report.get('active_lotteries', 0)}\n"
                f"**已取消**: {report.get('cancelled_lotteries', 0)}",
                inline=True,
            )

            # 參與統計
            embed.add_field(
                name="👥 參與統計",
                value=f"**總參與次數**: {report.get('total_participations', 0)}\n"
                f"**獨特參與者**: {report.get('unique_participants', 0)}\n"
                f"**平均參與數**: {report.get('avg_participants', 0):.1f}",
                inline=True,
            )

            # 中獎統計
            embed.add_field(
                name="🏆 中獎統計",
                value=f"**總中獎次數**: {report.get('total_wins', 0)}\n"
                f"**獨特中獎者**: {report.get('unique_winners', 0)}\n"
                f"**中獎率**: {report.get('win_rate', 0):.1f}%",
                inline=True,
            )

            # 趨勢分析
            if report.get("daily_trend"):
                trend_text = "📈 **近期趨勢**:\n"
                for day, count in list(report["daily_trend"].items())[-7:]:
                    trend_text += f"{day}: {count} 個抽獎\n"

                embed.add_field(name="📈 每日趨勢 (最近 7 天)", value=trend_text, inline=False)

            embed.set_footer(text=f"報告生成時間: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

            await interaction.followup.send(embed=embed, ephemeral=True)

        except Exception as e:
            logger.error(f"生成詳細報告失敗: {e}")
            await interaction.followup.send("❌ 生成報告時發生錯誤", ephemeral=True)

    async def _create_stats_embed(self, stats: Dict[str, Any], period: int) -> discord.Embed:
        """創建統計嵌入"""
        embed = EmbedBuilder.create_info_embed(f"📊 抽獎統計儀表板 (最近 {period} 天)")

        # 基本統計
        total = stats.get("total_lotteries", 0)
        active = stats.get("active_lotteries", 0)
        completed = stats.get("completed_lotteries", 0)

        embed.add_field(
            name="🎯 總體概覽",
            value=(
                f"**總抽獎數**: {total}\n"
                f"**進行中**: {active} 🟢\n"
                f"**已完成**: {completed} ✅\n"
                f"**完成率**: {(completed/total*100):.1f}%"
                if total > 0
                else "**完成率**: 0%"
            ),
            inline=True,
        )

        # 參與統計
        participations = stats.get("total_participations", 0)
        unique_participants = stats.get("unique_participants", 0)
        avg_participants = stats.get("avg_participants", 0)

        embed.add_field(
            name="👥 參與統計",
            value=f"**總參與次數**: {participations}\n"
            f"**獨特參與者**: {unique_participants}\n"
            f"**平均參與數**: {avg_participants:.1f}",
            inline=True,
        )

        # 中獎統計
        total_wins = stats.get("total_wins", 0)
        unique_winners = stats.get("unique_winners", 0)
        win_rate = (total_wins / participations * 100) if participations > 0 else 0

        embed.add_field(
            name="🏆 中獎統計",
            value=f"**總中獎次數**: {total_wins}\n"
            f"**獨特中獎者**: {unique_winners}\n"
            f"**整體中獎率**: {win_rate:.2f}%",
            inline=True,
        )

        # 時間分佈
        daily = stats.get("daily_lotteries", 0)
        weekly = stats.get("weekly_lotteries", 0)
        monthly = stats.get("monthly_lotteries", 0)

        embed.add_field(
            name="📅 時間分佈",
            value=f"**今日**: {daily}\n" f"**本週**: {weekly}\n" f"**本月**: {monthly}",
            inline=True,
        )

        # 活躍度指標
        if total > 0:
            activity_score = min(100, (active * 20 + completed * 10 + participations / 10))
            activity_text = (
                "🔥 非常活躍"
                if activity_score > 80
                else (
                    "🟢 活躍"
                    if activity_score > 60
                    else "🟡 一般" if activity_score > 30 else "🔴 較少"
                )
            )

            embed.add_field(
                name="📊 活躍度",
                value=f"**活躍指數**: {activity_score:.0f}/100\n" f"**評級**: {activity_text}",
                inline=True,
            )

        # 效率統計
        avg_winners = stats.get("avg_winner_count", 1)
        participation_efficiency = (unique_participants / total) if total > 0 else 0

        embed.add_field(
            name="⚡ 效率統計",
            value=f"**平均中獎數**: {avg_winners:.1f}\n"
            f"**參與效率**: {participation_efficiency:.1f}",
            inline=True,
        )

        embed.set_thumbnail(url="https://cdn.discordapp.com/emojis/🎲.png")
        embed.set_footer(text=f"數據更新時間: {datetime.now().strftime('%H:%M:%S')}")

        return embed

    async def _get_winners_leaderboard(self, period: int) -> List[tuple]:
        """獲取中獎排行榜"""
        try:
            async with self.lottery_manager.dao.db.connection() as conn:
                async with conn.cursor() as cursor:
                    query = """
                    SELECT
                        lw.user_id,
                        lw.username,
                        COUNT(*) as win_count
                    FROM lottery_winners lw
                    JOIN lotteries l ON lw.lottery_id = l.id
                    WHERE l.guild_id = %s
                    AND l.created_at >= DATE_SUB(NOW(), INTERVAL %s DAY)
                    GROUP BY lw.user_id, lw.username
                    ORDER BY win_count DESC
                    LIMIT 20
                    """

                    await cursor.execute(query, (self.guild_id, period))
                    results = await cursor.fetchall()

                    return results

        except Exception as e:
            logger.error(f"獲取中獎排行榜失敗: {e}")
            return []

    async def _generate_detailed_report(self, period: int) -> Dict[str, Any]:
        """生成詳細報告"""
        try:
            # 獲取基本統計
            stats = await self.lottery_manager.dao.get_lottery_statistics(self.guild_id, period)

            # 計算額外指標
            total_participations = stats.get("total_participations", 0)
            total_wins = stats.get("total_wins", 0)
            win_rate = (total_wins / total_participations * 100) if total_participations > 0 else 0

            # 獲取每日趨勢（簡化版）
            daily_trend = {}
            for i in range(7):  # 最近7天
                date = (datetime.now() - timedelta(days=i)).strftime("%m-%d")
                daily_trend[date] = 0  # 簡化，實際應該查詢資料庫

            report = {**stats, "win_rate": win_rate, "daily_trend": daily_trend}

            return report

        except Exception as e:
            logger.error(f"生成詳細報告失敗: {e}")
            return {}


class UserLotteryHistoryView(ui.View):
    """用戶抽獎歷史視圖"""

    def __init__(self, guild_id: int, user_id: int):
        super().__init__(timeout=300)
        self.guild_id = guild_id
        self.user_id = user_id
        self.lottery_manager = LotteryManager()
        self.current_page = 0
        self.page_size = 5

    @ui.button(label="⬅️ 上一頁", style=discord.ButtonStyle.secondary, emoji="⬅️")
    async def previous_page(self, interaction: discord.Interaction, button: ui.Button):
        """上一頁"""
        if self.current_page > 0:
            self.current_page -= 1
            await self._update_history(interaction)
        else:
            await interaction.response.send_message("已經是第一頁了", ephemeral=True)

    @ui.button(label="➡️ 下一頁", style=discord.ButtonStyle.secondary, emoji="➡️")
    async def next_page(self, interaction: discord.Interaction, button: ui.Button):
        """下一頁"""
        # 這裡應該檢查是否還有更多頁面
        self.current_page += 1
        await self._update_history(interaction)

    @ui.button(label="🔄 刷新", style=discord.ButtonStyle.secondary, emoji="🔄")
    async def refresh_history(self, interaction: discord.Interaction, button: ui.Button):
        """刷新歷史"""
        await self._update_history(interaction)

    async def _update_history(self, interaction: discord.Interaction):
        """更新歷史顯示"""
        try:
            await interaction.response.defer()

            # 獲取用戶抽獎歷史
            history = await self.lottery_manager.dao.get_user_lottery_history(
                self.guild_id,
                self.user_id,
                limit=self.page_size * (self.current_page + 1),
            )

            # 分頁處理
            start_idx = self.current_page * self.page_size
            end_idx = start_idx + self.page_size
            current_page_history = history[start_idx:end_idx]

            if not current_page_history:
                embed = EmbedBuilder.create_info_embed("📋 抽獎歷史", "沒有找到抽獎參與記錄")
                await interaction.followup.edit_message(
                    interaction.message.id, embed=embed, view=self
                )
                return

            # 創建歷史嵌入
            embed = EmbedBuilder.create_info_embed(f"📋 <@{self.user_id}> 的抽獎歷史")

            for record in current_page_history:
                status_emoji = {"active": "🟢", "ended": "✅", "cancelled": "❌"}

                win_text = "🏆 中獎" if record.get("is_winner") else "📝 參與"
                position_text = (
                    f" (第{record.get('win_position')}名)" if record.get("win_position") else ""
                )

                embed.add_field(
                    name=f"{status_emoji.get(record['status'], '❓')} {record['name']}",
                    value=f"**狀態**: {win_text}{position_text}\n"
                    f"**參與時間**: <t:{int(record['entry_time'].timestamp())}:F>",
                    inline=False,
                )

            embed.set_footer(text=f"第 {self.current_page + 1} 頁 • 共 {len(history)} 條記錄")

            await interaction.followup.edit_message(interaction.message.id, embed=embed, view=self)

        except Exception as e:
            logger.error(f"更新用戶抽獎歷史失敗: {e}")
            await interaction.followup.send("❌ 更新歷史記錄時發生錯誤", ephemeral=True)
