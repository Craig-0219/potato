# bot/cogs/lottery_core.py
"""
抽獎系統核心 Cog
提供抽獎相關的指令和功能
"""

from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands

from bot.services.lottery_manager import LotteryManager
from bot.utils.embed_builder import EmbedBuilder
from bot.views.lottery_views import (
    LotteryCreationModal,
    LotteryManagementView,
)
from shared.logger import logger


class LotteryCore(commands.Cog):
    """抽獎系統核心功能"""

    def __init__(self, bot):
        self.bot = bot
        self.lottery_manager = LotteryManager(bot)

    @app_commands.command(name="lottery_panel", description="打開抽獎管理面板")
    async def lottery_panel(self, interaction: discord.Interaction):
        """打開抽獎管理面板"""
        try:
            # 檢查基本權限 (查看需要)
            if not interaction.user.guild_permissions.send_messages:
                await interaction.response.send_message(
                    "❌ 您沒有權限使用此功能", ephemeral=True
                )
                return

            view = LotteryManagementView()

            embed = EmbedBuilder.create_info_embed(
                "🎲 抽獎系統管理面板",
                "使用下方按鈕來管理抽獎活動\n\n"
                "🎲 **創建新抽獎** - 創建新的抽獎活動\n"
                "📋 **活動抽獎** - 查看目前進行中的抽獎\n"
                "📊 **抽獎統計** - 查看抽獎系統統計資料\n"
                "⚙️ **管理操作** - 進階管理功能",
            )

            embed.set_thumbnail(url="https://cdn.discordapp.com/emojis/🎲.png")
            embed.set_footer(text="點擊按鈕開始使用抽獎系統")

            await interaction.response.send_message(
                embed=embed, view=view, ephemeral=True
            )

        except Exception as e:
            logger.error(f"打開抽獎管理面板失敗: {e}")
            await interaction.response.send_message(
                "❌ 打開管理面板時發生錯誤", ephemeral=True
            )

    @app_commands.command(
        name="create_lottery_quick",
        description="快速創建抽獎 (使用互動式表單)",
    )
    async def create_lottery_quick(self, interaction: discord.Interaction):
        """快速創建抽獎"""
        try:
            # 檢查權限
            if not interaction.user.guild_permissions.manage_messages:
                await interaction.response.send_message(
                    "❌ 您需要「管理訊息」權限才能創建抽獎", ephemeral=True
                )
                return

            modal = LotteryCreationModal()
            await interaction.response.send_modal(modal)

        except Exception as e:
            logger.error(f"打開抽獎創建表單失敗: {e}")
            try:
                if not interaction.response.is_done():
                    await interaction.response.send_message(
                        "❌ 打開創建表單時發生錯誤", ephemeral=True
                    )
                else:
                    await interaction.followup.send(
                        "❌ 打開創建表單時發生錯誤", ephemeral=True
                    )
            except Exception as followup_error:
                logger.error(f"發送錯誤訊息失敗: {followup_error}")

    @app_commands.command(
        name="create_lottery", description="創建新的抽獎活動 (傳統指令)"
    )
    @app_commands.describe(
        name="抽獎名稱",
        description="抽獎描述",
        winner_count="中獎人數",
        duration_hours="持續時間(小時)",
        prize="獎品描述",
        entry_method="參與方式",
    )
    @app_commands.choices(
        entry_method=[
            app_commands.Choice(name="點擊反應", value="reaction"),
            app_commands.Choice(name="使用指令", value="command"),
            app_commands.Choice(name="兩者皆可", value="both"),
        ]
    )
    async def create_lottery(
        self,
        interaction: discord.Interaction,
        name: str,
        winner_count: int = 1,
        duration_hours: int = 24,
        description: Optional[str] = None,
        prize: Optional[str] = None,
        entry_method: str = "reaction",
    ):
        """創建抽獎"""
        try:
            # 檢查權限
            if not interaction.user.guild_permissions.manage_messages:
                await interaction.response.send_message(
                    "❌ 您需要「管理訊息」權限才能創建抽獎", ephemeral=True
                )
                return

            # 驗證參數
            if winner_count < 1 or winner_count > 50:
                await interaction.response.send_message(
                    "❌ 中獎人數必須在 1-50 之間", ephemeral=True
                )
                return

            if duration_hours < 1 or duration_hours > 168:  # 最多一週
                await interaction.response.send_message(
                    "❌ 持續時間必須在 1-168 小時之間", ephemeral=True
                )
                return

            # 準備抽獎配置
            lottery_config = {
                "name": name,
                "description": description,
                "channel_id": interaction.channel.id,
                "winner_count": winner_count,
                "duration_hours": duration_hours,
                "entry_method": entry_method,
                "prize_data": {"description": prize} if prize else None,
                "auto_end": True,
            }

            await interaction.response.defer()

            # 創建抽獎
            success, message, lottery_id = (
                await self.lottery_manager.create_lottery(
                    interaction.guild, interaction.user, lottery_config
                )
            )

            if success and lottery_id:
                # 立即開始抽獎
                start_success, start_message, lottery_message = (
                    await self.lottery_manager.start_lottery(
                        lottery_id, interaction.channel
                    )
                )

                if start_success:
                    await interaction.followup.send(
                        f"✅ {message}\n抽獎已開始！", ephemeral=True
                    )
                else:
                    await interaction.followup.send(
                        f"✅ 抽獎創建成功，但啟動失敗：{start_message}",
                        ephemeral=True,
                    )
            else:
                await interaction.followup.send(
                    f"❌ {message}", ephemeral=True
                )

        except Exception as e:
            logger.error(f"創建抽獎指令錯誤: {e}")
            if not interaction.response.is_done():
                await interaction.response.send_message(
                    "❌ 創建抽獎時發生錯誤", ephemeral=True
                )
            else:
                await interaction.followup.send(
                    "❌ 創建抽獎時發生錯誤", ephemeral=True
                )

    @app_commands.command(name="join_lottery", description="參與抽獎")
    @app_commands.describe(lottery_id="抽獎ID")
    async def join_lottery(
        self, interaction: discord.Interaction, lottery_id: int
    ):
        """參與抽獎"""
        try:
            success, message = await self.lottery_manager.join_lottery(
                lottery_id, interaction.user, "command"
            )

            if success:
                await interaction.response.send_message(
                    f"✅ {message}", ephemeral=True
                )
            else:
                await interaction.response.send_message(
                    f"❌ {message}", ephemeral=True
                )

        except Exception as e:
            logger.error(f"參與抽獎指令錯誤: {e}")
            await interaction.response.send_message(
                "❌ 參與抽獎時發生錯誤", ephemeral=True
            )

    @app_commands.command(name="leave_lottery", description="退出抽獎")
    @app_commands.describe(lottery_id="抽獎ID")
    async def leave_lottery(
        self, interaction: discord.Interaction, lottery_id: int
    ):
        """退出抽獎"""
        try:
            success, message = await self.lottery_manager.leave_lottery(
                lottery_id, interaction.user
            )

            if success:
                await interaction.response.send_message(
                    f"✅ {message}", ephemeral=True
                )
            else:
                await interaction.response.send_message(
                    f"❌ {message}", ephemeral=True
                )

        except Exception as e:
            logger.error(f"退出抽獎指令錯誤: {e}")
            await interaction.response.send_message(
                "❌ 退出抽獎時發生錯誤", ephemeral=True
            )

    @app_commands.command(name="lottery_info", description="查看抽獎資訊")
    @app_commands.describe(lottery_id="抽獎ID")
    async def lottery_info(
        self, interaction: discord.Interaction, lottery_id: int
    ):
        """查看抽獎資訊"""
        try:
            lottery = await self.lottery_manager.get_lottery_info(lottery_id)

            if not lottery:
                await interaction.response.send_message(
                    "❌ 找不到指定的抽獎", ephemeral=True
                )
                return

            # 創建資訊嵌入
            embed = EmbedBuilder.build(
                title=f"🎲 {lottery['name']} - 抽獎資訊",
                description=lottery.get("description", "無描述"),
                color="info",
            )

            # 基本資訊
            embed.add_field(
                name="📊 狀態", value=lottery["status"], inline=True
            )
            embed.add_field(
                name="👥 參與人數",
                value=str(lottery.get("participant_count", 0)),
                inline=True,
            )
            embed.add_field(
                name="🏆 中獎人數",
                value=str(lottery["winner_count"]),
                inline=True,
            )

            # 時間資訊
            if lottery["start_time"]:
                embed.add_field(
                    name="⏰ 開始時間",
                    value=f"<t:{int(lottery['start_time'].timestamp())}:F>",
                    inline=True,
                )
            if lottery["end_time"]:
                embed.add_field(
                    name="⏰ 結束時間",
                    value=f"<t:{int(lottery['end_time'].timestamp())}:F>",
                    inline=True,
                )

            # 獎品資訊
            if lottery.get("prize_data"):
                prize_info = lottery["prize_data"]
                if isinstance(prize_info, dict):
                    embed.add_field(
                        name="🎁 獎品",
                        value=prize_info.get("description", "未知獎品"),
                        inline=False,
                    )

            # 中獎者資訊（如果已結束）
            if lottery["status"] == "ended" and lottery.get("winners"):
                winner_names = [
                    f"<@{w['user_id']}>" for w in lottery["winners"][:5]
                ]
                winners_text = ", ".join(winner_names)
                if len(lottery["winners"]) > 5:
                    winners_text += f" 等 {len(lottery['winners'])} 人"
                embed.add_field(
                    name="🏆 中獎者", value=winners_text, inline=False
                )

            embed.set_footer(text=f"抽獎 ID: {lottery_id}")

            await interaction.response.send_message(
                embed=embed, ephemeral=True
            )

        except Exception as e:
            logger.error(f"查看抽獎資訊錯誤: {e}")
            await interaction.response.send_message(
                "❌ 查看抽獎資訊時發生錯誤", ephemeral=True
            )

    @app_commands.command(name="end_lottery", description="提前結束抽獎")
    @app_commands.describe(lottery_id="抽獎ID")
    async def end_lottery(
        self, interaction: discord.Interaction, lottery_id: int
    ):
        """提前結束抽獎"""
        try:
            # 檢查權限
            if not interaction.user.guild_permissions.manage_messages:
                await interaction.response.send_message(
                    "❌ 您需要「管理訊息」權限才能結束抽獎", ephemeral=True
                )
                return

            await interaction.response.defer()

            success, message, winners = await self.lottery_manager.end_lottery(
                lottery_id, interaction.channel, forced=True
            )

            if success:
                await interaction.followup.send(
                    f"✅ {message}", ephemeral=True
                )
            else:
                await interaction.followup.send(
                    f"❌ {message}", ephemeral=True
                )

        except Exception as e:
            logger.error(f"結束抽獎指令錯誤: {e}")
            if not interaction.response.is_done():
                await interaction.response.send_message(
                    "❌ 結束抽獎時發生錯誤", ephemeral=True
                )
            else:
                await interaction.followup.send(
                    "❌ 結束抽獎時發生錯誤", ephemeral=True
                )

    @app_commands.command(
        name="lottery_list", description="查看進行中的抽獎列表"
    )
    async def lottery_list(self, interaction: discord.Interaction):
        """查看抽獎列表"""
        try:
            from bot.db.lottery_dao import LotteryDAO

            dao = LotteryDAO()

            lotteries = await dao.get_active_lotteries(interaction.guild.id)

            if not lotteries:
                await interaction.response.send_message(
                    "📋 目前沒有進行中的抽獎", ephemeral=True
                )
                return

            embed = EmbedBuilder.build(title="🎲 進行中的抽獎", color="info")

            for lottery in lotteries[:10]:  # 最多顯示10個
                status_emoji = "🟢" if lottery["status"] == "active" else "🟡"
                end_time = (
                    f"<t:{int(lottery['end_time'].timestamp())}:R>"
                    if lottery["end_time"]
                    else "未設定"
                )

                embed.add_field(
                    name=f"{status_emoji} {lottery['name']} (ID: {lottery['id']})",
                    value=f"中獎人數: {lottery['winner_count']} | 結束: {end_time}",
                    inline=False,
                )

            if len(lotteries) > 10:
                embed.set_footer(text=f"顯示 10/{len(lotteries)} 個抽獎")

            await interaction.response.send_message(
                embed=embed, ephemeral=True
            )

        except Exception as e:
            logger.error(f"查看抽獎列表錯誤: {e}")
            await interaction.response.send_message(
                "❌ 查看抽獎列表時發生錯誤", ephemeral=True
            )

    @app_commands.command(name="lottery_stats", description="查看抽獎統計")
    @app_commands.describe(days="統計天數（預設30天）")
    async def lottery_stats(
        self, interaction: discord.Interaction, days: int = 30
    ):
        """查看抽獎統計"""
        try:
            if days < 1 or days > 365:
                await interaction.response.send_message(
                    "❌ 統計天數必須在 1-365 之間", ephemeral=True
                )
                return

            await interaction.response.defer()

            stats = await self.lottery_manager.get_lottery_statistics(
                interaction.guild.id, days
            )

            if (
                not stats
                or stats.get("basic_stats", {}).get("total_lotteries", 0) == 0
            ):
                await interaction.followup.send(
                    f"📊 最近 {days} 天沒有抽獎活動", ephemeral=True
                )
                return

            basic_stats = stats.get("basic_stats", {})
            participation_stats = stats.get("participation_stats", {})

            embed = EmbedBuilder.build(
                title=f"📊 抽獎統計 - 最近 {days} 天", color="info"
            )

            # 基本統計
            embed.add_field(
                name="🎲 抽獎活動",
                value=f"總數: {basic_stats.get('total_lotteries', 0)}\n"
                f"進行中: {basic_stats.get('active_lotteries', 0)}\n"
                f"已完成: {basic_stats.get('completed_lotteries', 0)}\n"
                f"已取消: {basic_stats.get('cancelled_lotteries', 0)}",
                inline=True,
            )

            # 參與統計
            embed.add_field(
                name="👥 參與情況",
                value=f"獨特參與者: {participation_stats.get('unique_participants', 0)}\n"
                f"總參與次數: {participation_stats.get('total_entries', 0)}\n"
                f"平均參與數: {participation_stats.get('avg_entries_per_lottery', 0):.1f}",
                inline=True,
            )

            # 平均中獎數
            avg_winners = basic_stats.get("avg_winners_per_lottery", 0)
            embed.add_field(
                name="🏆 中獎情況",
                value=f"平均中獎數: {avg_winners:.1f}",
                inline=True,
            )

            embed.set_footer(
                text=f"統計期間: {stats.get('period', f'最近 {days} 天')}"
            )

            await interaction.followup.send(embed=embed, ephemeral=True)

        except Exception as e:
            logger.error(f"查看抽獎統計錯誤: {e}")
            if not interaction.response.is_done():
                await interaction.response.send_message(
                    "❌ 查看抽獎統計時發生錯誤", ephemeral=True
                )
            else:
                await interaction.followup.send(
                    "❌ 查看抽獎統計時發生錯誤", ephemeral=True
                )

    @commands.Cog.listener()
    async def on_raw_reaction_add(
        self, payload: discord.RawReactionActionEvent
    ):
        """處理反應參與抽獎"""
        try:
            # 檢查是否為抽獎反應
            if str(payload.emoji) != "🎉":
                return

            if payload.user_id == self.bot.user.id:
                return

            # 查找相關抽獎
            from bot.db.lottery_dao import LotteryDAO

            dao = LotteryDAO()

            lotteries = await dao.get_active_lotteries(payload.guild_id)

            for lottery in lotteries:
                if lottery.get("message_id") == payload.message_id:
                    # 獲取用戶
                    guild = self.bot.get_guild(payload.guild_id)
                    if not guild:
                        continue

                    user = guild.get_member(payload.user_id)
                    if not user:
                        continue

                    # 參與抽獎
                    success, message = await self.lottery_manager.join_lottery(
                        lottery["id"], user, "reaction"
                    )

                    # 可選：發送私訊通知結果
                    if success:
                        try:
                            await user.send(
                                f"✅ 成功參與抽獎「{lottery['name']}」！"
                            )
                        except:
                            pass  # 忽略私訊失敗

                    break

        except Exception as e:
            logger.error(f"處理抽獎反應錯誤: {e}")

    @commands.Cog.listener()
    async def on_raw_reaction_remove(
        self, payload: discord.RawReactionActionEvent
    ):
        """處理反應取消參與抽獎"""
        try:
            # 檢查是否為抽獎反應
            if str(payload.emoji) != "🎉":
                return

            if payload.user_id == self.bot.user.id:
                return

            # 查找相關抽獎
            from bot.db.lottery_dao import LotteryDAO

            dao = LotteryDAO()

            lotteries = await dao.get_active_lotteries(payload.guild_id)

            for lottery in lotteries:
                if lottery.get("message_id") == payload.message_id:
                    # 獲取用戶
                    guild = self.bot.get_guild(payload.guild_id)
                    if not guild:
                        continue

                    user = guild.get_member(payload.user_id)
                    if not user:
                        continue

                    # 退出抽獎
                    await self.lottery_manager.leave_lottery(
                        lottery["id"], user
                    )
                    break

        except Exception as e:
            logger.error(f"處理抽獎反應移除錯誤: {e}")

    @app_commands.command(
        name="my_lottery_history", description="查看我的抽獎參與歷史"
    )
    async def my_lottery_history(self, interaction: discord.Interaction):
        """查看用戶抽獎歷史"""
        try:
            await interaction.response.defer(ephemeral=True)

            # 導入歷史視圖
            from bot.views.lottery_dashboard_views import (
                UserLotteryHistoryView,
            )

            # 創建用戶歷史視圖
            history_view = UserLotteryHistoryView(
                interaction.guild.id, interaction.user.id
            )

            # 獲取初始歷史數據
            history = await self.lottery_manager.dao.get_user_lottery_history(
                interaction.guild.id, interaction.user.id, limit=5
            )

            if not history:
                embed = EmbedBuilder.create_info_embed(
                    "📋 我的抽獎歷史", "您還沒有參與過任何抽獎活動"
                )
                await interaction.followup.send(embed=embed, ephemeral=True)
                return

            # 創建歷史嵌入
            embed = EmbedBuilder.create_info_embed(
                f"📋 <@{interaction.user.id}> 的抽獎歷史"
            )

            for record in history:
                status_emoji = {
                    "active": "🟢",
                    "ended": "✅",
                    "cancelled": "❌",
                }

                win_text = "🏆 中獎" if record.get("is_winner") else "📝 參與"
                position_text = (
                    f" (第{record.get('win_position')}名)"
                    if record.get("win_position")
                    else ""
                )

                embed.add_field(
                    name=f"{status_emoji.get(record['status'], '❓')} {record['name']}",
                    value=f"**狀態**: {win_text}{position_text}\n"
                    f"**參與時間**: <t:{int(record['entry_time'].timestamp())}:F>",
                    inline=False,
                )

            embed.set_footer(text=f"第 1 頁 • 共 {len(history)} 條記錄")

            await interaction.followup.send(
                embed=embed, view=history_view, ephemeral=True
            )

        except Exception as e:
            logger.error(f"查看抽獎歷史失敗: {e}")
            if not interaction.response.is_done():
                await interaction.response.send_message(
                    "❌ 查看抽獎歷史時發生錯誤", ephemeral=True
                )
            else:
                await interaction.followup.send(
                    "❌ 查看抽獎歷史時發生錯誤", ephemeral=True
                )


async def setup(bot):
    await bot.add_cog(LotteryCore(bot))
