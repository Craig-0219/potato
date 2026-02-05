# bot/views/lottery_views.py
"""
抽獎系統互動式介面視圖
提供完整的抽獎管理和參與介面
"""

from datetime import datetime, timedelta
from typing import Any, Dict

import discord
from discord import ui

from potato_bot.services.lottery_manager import LotteryManager
from potato_bot.utils.embed_builder import EmbedBuilder
from potato_shared.logger import logger


async def _can_manage_lottery(
    interaction: discord.Interaction, manager: LotteryManager
) -> bool:
    if not interaction.guild:
        return False
    if await interaction.client.is_owner(interaction.user):
        return True
    if interaction.user.guild_permissions.administrator or interaction.user.guild_permissions.manage_guild:
        return True
    settings = await manager.dao.get_lottery_settings(interaction.guild.id)
    allowed_roles = settings.get("admin_roles", []) if settings else []
    if not allowed_roles:
        return False
    member_role_ids = {role.id for role in interaction.user.roles}
    return bool(member_role_ids & set(allowed_roles))


def build_lottery_panel_embed() -> discord.Embed:
    """建立抽獎管理面板嵌入"""
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
    return embed

class LotteryCreationModal(ui.Modal):
    """抽獎創建模態框"""

    def __init__(self):
        super().__init__(title="🎲 創建新抽獎", timeout=300)

        # 抽獎名稱
        self.name_input = ui.TextInput(
            label="抽獎名稱",
            placeholder="輸入抽獎活動的名稱...",
            max_length=100,
            required=True,
        )
        self.add_item(self.name_input)

        # 抽獎描述
        self.description_input = ui.TextInput(
            label="抽獎描述",
            placeholder="描述這個抽獎活動...",
            style=discord.TextStyle.paragraph,
            max_length=500,
            required=False,
        )
        self.add_item(self.description_input)

        # 獎品描述
        self.prize_input = ui.TextInput(
            label="獎品說明",
            placeholder="描述抽獎獎品...",
            max_length=200,
            required=False,
        )
        self.add_item(self.prize_input)

        # 中獎人數
        self.winner_count_input = ui.TextInput(
            label="中獎人數",
            placeholder="1-50",
            default="1",
            max_length=2,
            required=True,
        )
        self.add_item(self.winner_count_input)

        # 持續時間
        self.duration_input = ui.TextInput(
            label="持續時間(小時)",
            placeholder="1-168",
            default="24",
            max_length=3,
            required=True,
        )
        self.add_item(self.duration_input)

    async def on_submit(self, interaction: discord.Interaction):
        """處理表單提交"""
        try:
            # 驗證數值輸入
            try:
                winner_count = int(self.winner_count_input.value)
                duration_hours = int(self.duration_input.value)
            except ValueError:
                await interaction.response.send_message(
                    "❌ 中獎人數和持續時間必須是數字", ephemeral=True
                )
                return

            # 驗證範圍
            if winner_count < 1 or winner_count > 50:
                await interaction.response.send_message(
                    "❌ 中獎人數必須在 1-50 之間", ephemeral=True
                )
                return

            if duration_hours < 1 or duration_hours > 168:
                await interaction.response.send_message(
                    "❌ 持續時間必須在 1-168 小時之間", ephemeral=True
                )
                return

            await interaction.response.defer(ephemeral=True)

            # 創建抽獎配置
            lottery_config = {
                "name": self.name_input.value,
                "description": self.description_input.value or None,
                "prize": self.prize_input.value or None,
                "winner_count": winner_count,
                "duration_hours": duration_hours,
                "channel_id": interaction.channel.id,
                "entry_method": "both",  # 預設兩者皆可
            }

            # 顯示確認視圖
            confirmation_view = LotteryCreationConfirmView(lottery_config)

            embed = EmbedBuilder.create_info_embed(
                "🎲 確認抽獎設定",
                f"**抽獎名稱**: {lottery_config['name']}\n"
                f"**描述**: {lottery_config['description'] or '無'}\n"
                f"**獎品**: {lottery_config['prize'] or '無'}\n"
                f"**中獎人數**: {winner_count} 人\n"
                f"**持續時間**: {duration_hours} 小時\n"
                f"**參與方式**: 反應點擊 + 指令\n\n"
                "請確認設定後點擊「創建抽獎」",
            )

            await interaction.followup.send(embed=embed, view=confirmation_view, ephemeral=True)

        except Exception as e:
            logger.error(f"處理抽獎創建表單失敗: {e}")
            if not interaction.response.is_done():
                await interaction.response.send_message("❌ 處理表單時發生錯誤", ephemeral=True)
            else:
                await interaction.followup.send("❌ 處理表單時發生錯誤", ephemeral=True)


class LotteryCreationConfirmView(ui.View):
    """抽獎創建確認視圖"""

    def __init__(self, lottery_config: Dict[str, Any]):
        super().__init__(timeout=120)
        self.lottery_config = lottery_config
        self.lottery_manager = LotteryManager()

    @ui.button(label="✅ 創建抽獎", style=discord.ButtonStyle.green)
    async def create_lottery(self, interaction: discord.Interaction, button: ui.Button):
        """確認創建抽獎"""
        try:
            # 檢查權限
            if not await _can_manage_lottery(interaction, self.lottery_manager):
                await interaction.response.send_message(
                    "❌ 您沒有權限創建抽獎，請聯絡管理員設定。", ephemeral=True
                )
                return

            await interaction.response.defer(ephemeral=True)

            # 創建抽獎
            success, message, lottery_id = await self.lottery_manager.create_lottery(
                interaction.guild, interaction.user, self.lottery_config
            )

            if success and lottery_id:
                # 立即開始抽獎
                start_success, start_message, lottery_message = (
                    await self.lottery_manager.start_lottery(lottery_id, interaction.channel)
                )

                if start_success:
                    await interaction.followup.send(
                        f"✅ {message}\n抽獎已成功開始！", ephemeral=True
                    )
                    # 禁用按鈕
                    for item in self.children:
                        item.disabled = True
                    await interaction.edit_original_response(view=self)
                else:
                    await interaction.followup.send(
                        f"✅ 抽獎創建成功，但啟動失敗：{start_message}",
                        ephemeral=True,
                    )
            else:
                await interaction.followup.send(f"❌ {message}", ephemeral=True)

        except Exception as e:
            logger.error(f"創建抽獎失敗: {e}")
            await interaction.followup.send("❌ 創建抽獎時發生錯誤", ephemeral=True)

    @ui.button(label="❌ 取消", style=discord.ButtonStyle.grey)
    async def cancel_creation(self, interaction: discord.Interaction, button: ui.Button):
        """取消創建"""
        await interaction.response.send_message("❌ 已取消創建抽獎", ephemeral=True)
        for item in self.children:
            item.disabled = True
        await interaction.edit_original_response(view=self)

    async def on_timeout(self):
        """超時處理"""
        for item in self.children:
            item.disabled = True


class LotteryParticipationView(ui.View):
    """抽獎參與視圖"""

    def __init__(self, lottery_id: int):
        super().__init__(timeout=None)
        self.lottery_id = lottery_id
        self.lottery_manager = LotteryManager()

    @ui.button(label="參加抽獎", style=discord.ButtonStyle.primary, emoji="🎲")
    async def join_lottery(self, interaction: discord.Interaction, button: ui.Button):
        """參加抽獎"""
        try:
            await interaction.response.defer(ephemeral=True)

            success, message = await self.lottery_manager.join_lottery(
                self.lottery_id, interaction.user
            )

            if success:
                await interaction.followup.send(f"✅ {message}", ephemeral=True)
            else:
                await interaction.followup.send(f"❌ {message}", ephemeral=True)

        except Exception as e:
            logger.error(f"參加抽獎失敗: {e}")
            await interaction.followup.send("❌ 參加抽獎時發生錯誤", ephemeral=True)


class EndLotteryModal(ui.Modal):
    """提前結束抽獎"""

    def __init__(self, manager: LotteryManager):
        super().__init__(title="🛑 提前結束抽獎", timeout=300)
        self.manager = manager
        self.lottery_id_input = ui.TextInput(
            label="抽獎 ID",
            placeholder="輸入抽獎 ID",
            max_length=10,
            required=True,
        )
        self.add_item(self.lottery_id_input)

    async def on_submit(self, interaction: discord.Interaction):
        if not await _can_manage_lottery(interaction, self.manager):
            await interaction.response.send_message(
                "❌ 您沒有權限使用管理功能，請聯絡管理員設定。", ephemeral=True
            )
            return

        try:
            lottery_id = int(self.lottery_id_input.value)
        except ValueError:
            await interaction.response.send_message("❌ 抽獎 ID 必須是數字", ephemeral=True)
            return

        lottery = await self.manager.dao.get_lottery(lottery_id)
        if not lottery or lottery.get("guild_id") != interaction.guild.id:
            await interaction.response.send_message("❌ 找不到該抽獎", ephemeral=True)
            return

        if lottery.get("status") != "active":
            await interaction.response.send_message(
                f"❌ 抽獎狀態不正確: {lottery.get('status')}", ephemeral=True
            )
            return

        channel = interaction.guild.get_channel(lottery.get("channel_id")) or interaction.channel
        success, message, _ = await self.manager.end_lottery(
            lottery_id, channel, forced=True
        )

        if success:
            await interaction.response.send_message(f"✅ {message}", ephemeral=True)
        else:
            await interaction.response.send_message(f"❌ {message}", ephemeral=True)


class RedrawLotteryModal(ui.Modal):
    """重新開獎"""

    def __init__(self, manager: LotteryManager):
        super().__init__(title="🔄 重新開獎", timeout=300)
        self.manager = manager
        self.lottery_id_input = ui.TextInput(
            label="抽獎 ID",
            placeholder="輸入抽獎 ID",
            max_length=10,
            required=True,
        )
        self.add_item(self.lottery_id_input)

    async def on_submit(self, interaction: discord.Interaction):
        if not await _can_manage_lottery(interaction, self.manager):
            await interaction.response.send_message(
                "❌ 您沒有權限使用管理功能，請聯絡管理員設定。", ephemeral=True
            )
            return

        try:
            lottery_id = int(self.lottery_id_input.value)
        except ValueError:
            await interaction.response.send_message("❌ 抽獎 ID 必須是數字", ephemeral=True)
            return

        lottery = await self.manager.dao.get_lottery(lottery_id)
        if not lottery or lottery.get("guild_id") != interaction.guild.id:
            await interaction.response.send_message("❌ 找不到該抽獎", ephemeral=True)
            return

        if lottery.get("status") != "ended":
            await interaction.response.send_message(
                f"❌ 抽獎狀態不正確: {lottery.get('status')}", ephemeral=True
            )
            return

        channel = interaction.guild.get_channel(lottery.get("channel_id")) or interaction.channel
        success, message, _ = await self.manager.redraw_lottery(lottery_id, channel)

        if success:
            await interaction.response.send_message(f"✅ {message}", ephemeral=True)
        else:
            await interaction.response.send_message(f"❌ {message}", ephemeral=True)


class ViewWinnersModal(ui.Modal):
    """查看中獎者"""

    def __init__(self, manager: LotteryManager):
        super().__init__(title="🏆 查看中獎者", timeout=300)
        self.manager = manager
        self.lottery_id_input = ui.TextInput(
            label="抽獎 ID",
            placeholder="輸入抽獎 ID",
            max_length=10,
            required=True,
        )
        self.add_item(self.lottery_id_input)

    async def on_submit(self, interaction: discord.Interaction):
        if not await _can_manage_lottery(interaction, self.manager):
            await interaction.response.send_message(
                "❌ 您沒有權限使用管理功能，請聯絡管理員設定。", ephemeral=True
            )
            return

        try:
            lottery_id = int(self.lottery_id_input.value)
        except ValueError:
            await interaction.response.send_message("❌ 抽獎 ID 必須是數字", ephemeral=True)
            return

        lottery = await self.manager.dao.get_lottery(lottery_id)
        if not lottery or lottery.get("guild_id") != interaction.guild.id:
            await interaction.response.send_message("❌ 找不到該抽獎", ephemeral=True)
            return

        winners = await self.manager.dao.get_winners(lottery_id)
        if not winners:
            await interaction.response.send_message("📭 目前尚無中獎者", ephemeral=True)
            return

        embed = EmbedBuilder.create_info_embed(f"🏆 中獎者 - {lottery.get('name', '抽獎')}")
        for winner in winners:
            position = winner.get("win_position")
            user_id = winner.get("user_id")
            embed.add_field(
                name=f"第 {position} 名",
                value=f"<@{user_id}> ({winner.get('username')})",
                inline=False,
            )

        await interaction.response.send_message(embed=embed, ephemeral=True)


class LotteryPanelDeployView(ui.View):
    """抽獎面板部署視圖"""

    def __init__(self, user_id: int, manager: LotteryManager):
        super().__init__(timeout=120)
        self.user_id = user_id
        self.manager = manager
        self.add_item(LotteryPanelChannelSelect(self))

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("❌ 只有開啟此面板的管理員可操作", ephemeral=True)
            return False
        return True


class LotteryPanelChannelSelect(discord.ui.ChannelSelect):
    """抽獎面板頻道選擇器"""

    def __init__(self, parent_view: LotteryPanelDeployView):
        self.parent_view = parent_view
        super().__init__(
            placeholder="選擇要部署的文字頻道...",
            min_values=1,
            max_values=1,
            channel_types=[discord.ChannelType.text],
        )

    async def callback(self, interaction: discord.Interaction):
        if not await _can_manage_lottery(interaction, self.parent_view.manager):
            await interaction.response.send_message(
                "❌ 您沒有權限部署抽獎面板，請聯絡管理員設定。", ephemeral=True
            )
            return

        channel = self.values[0]
        view = LotteryManagementView(timeout=None)
        embed = build_lottery_panel_embed()

        await channel.send(embed=embed, view=view)
        await interaction.response.send_message(
            f"✅ 抽獎面板已重新佈署至 {channel.mention}", ephemeral=True
        )

    @ui.button(label="查看詳情", style=discord.ButtonStyle.secondary, emoji="📊")
    async def lottery_info(self, interaction: discord.Interaction, button: ui.Button):
        """查看抽獎詳情"""
        try:
            await interaction.response.defer(ephemeral=True)

            lottery = await self.lottery_manager.dao.get_lottery(self.lottery_id)
            if not lottery:
                await interaction.followup.send("❌ 抽獎不存在", ephemeral=True)
                return

            # 獲取參與者數量
            participant_count = await self.lottery_manager.dao.get_participant_count(
                self.lottery_id
            )

            # 創建詳情嵌入
            embed = await self._create_info_embed(lottery, participant_count)
            await interaction.followup.send(embed=embed, ephemeral=True)

        except Exception as e:
            logger.error(f"獲取抽獎詳情失敗: {e}")
            await interaction.followup.send("❌ 獲取抽獎詳情時發生錯誤", ephemeral=True)

    @ui.button(label="退出抽獎", style=discord.ButtonStyle.danger, emoji="🚪")
    async def leave_lottery(self, interaction: discord.Interaction, button: ui.Button):
        """退出抽獎"""
        try:
            await interaction.response.defer(ephemeral=True)

            success, message = await self.lottery_manager.leave_lottery(
                self.lottery_id, interaction.user
            )

            if success:
                await interaction.followup.send(f"✅ {message}", ephemeral=True)
            else:
                await interaction.followup.send(f"❌ {message}", ephemeral=True)

        except Exception as e:
            logger.error(f"退出抽獎失敗: {e}")
            await interaction.followup.send("❌ 退出抽獎時發生錯誤", ephemeral=True)

    async def _create_info_embed(
        self, lottery: Dict[str, Any], participant_count: int
    ) -> discord.Embed:
        """創建抽獎詳情嵌入"""
        embed = EmbedBuilder.create_info_embed(f"🎲 {lottery['name']}")

        # 基本資訊
        embed.add_field(
            name="📋 基本資訊",
            value=f"**描述**: {lottery.get('description', '無')}\n"
            f"**獎品**: {lottery.get('prize_data', {}).get('description', '無')}\n"
            f"**中獎人數**: {lottery['winner_count']} 人",
            inline=False,
        )

        # 參與資訊
        embed.add_field(
            name="👥 參與資訊",
            value=f"**目前參與人數**: {participant_count} 人\n"
            f"**參與方式**: {self._get_entry_method_text(lottery.get('entry_method', 'both'))}",
            inline=True,
        )

        # 時間資訊
        end_time = lottery.get("end_time")
        if end_time:
            if isinstance(end_time, str):
                end_time = datetime.fromisoformat(end_time.replace("Z", "+00:00"))
            time_left = end_time - datetime.now()

            embed.add_field(
                name="⏰ 時間資訊",
                value=f"**結束時間**: <t:{int(end_time.timestamp())}:F>\n"
                f"**剩餘時間**: {self._format_time_delta(time_left)}",
                inline=True,
            )

        # 狀態資訊
        status_emoji = {
            "active": "🟢",
            "pending": "🟡",
            "ended": "🔴",
            "cancelled": "⚫",
        }

        embed.add_field(
            name="📊 狀態",
            value=f"{status_emoji.get(lottery.get('status', 'unknown'), '❓')} {lottery.get('status', '未知').upper()}",
            inline=True,
        )

        embed.set_footer(text=f"抽獎 ID: {lottery['id']}")

        return embed

    def _get_entry_method_text(self, entry_method: str) -> str:
        """獲取參與方式文字"""
        method_map = {
            "reaction": "反應點擊",
            "command": "指令參與",
            "both": "反應 + 指令",
        }
        return method_map.get(entry_method, "未知")

    def _format_time_delta(self, delta: timedelta) -> str:
        """格式化時間差"""
        if delta.total_seconds() <= 0:
            return "已結束"

        days = delta.days
        hours = delta.seconds // 3600
        minutes = (delta.seconds % 3600) // 60

        parts = []
        if days > 0:
            parts.append(f"{days} 天")
        if hours > 0:
            parts.append(f"{hours} 小時")
        if minutes > 0:
            parts.append(f"{minutes} 分鐘")

        return " ".join(parts) if parts else "不到 1 分鐘"


class LotteryManagementView(ui.View):
    """抽獎管理面板視圖"""

    def __init__(self, timeout=300):
        super().__init__(timeout=timeout)
        self.lottery_manager = LotteryManager()

    @ui.button(label="創建新抽獎", style=discord.ButtonStyle.primary, emoji="🎲")
    async def create_new_lottery(self, interaction: discord.Interaction, button: ui.Button):
        """創建新抽獎"""
        if not await _can_manage_lottery(interaction, self.lottery_manager):
            await interaction.response.send_message(
                "❌ 您沒有權限創建抽獎，請聯絡管理員設定。", ephemeral=True
            )
            return

        modal = LotteryCreationModal()
        await interaction.response.send_modal(modal)

    @ui.button(label="活動抽獎", style=discord.ButtonStyle.secondary, emoji="📋")
    async def active_lotteries(self, interaction: discord.Interaction, button: ui.Button):
        """查看活動抽獎"""
        try:
            await interaction.response.defer(ephemeral=True)

            active_lotteries = await self.lottery_manager.dao.get_active_lotteries(
                interaction.guild.id
            )

            if not active_lotteries:
                embed = EmbedBuilder.create_info_embed("📋 活動抽獎", "目前沒有進行中的抽獎活動")
                await interaction.followup.send(embed=embed, ephemeral=True)
                return

            # 創建抽獎列表嵌入
            embed = EmbedBuilder.create_info_embed(f"📋 活動抽獎 ({len(active_lotteries)})")

            for lottery in active_lotteries[:10]:  # 最多顯示10個
                participant_count = await self.lottery_manager.dao.get_participant_count(
                    lottery["id"]
                )

                end_time = lottery.get("end_time")
                if isinstance(end_time, str):
                    end_time = datetime.fromisoformat(end_time.replace("Z", "+00:00"))

                embed.add_field(
                    name=f"🎲 {lottery['name']}",
                    value=f"**ID**: {lottery['id']}\n"
                    f"**參與人數**: {participant_count} 人\n"
                    f"**結束**: <t:{int(end_time.timestamp())}:R>",
                    inline=True,
                )

            if len(active_lotteries) > 10:
                embed.set_footer(text=f"顯示前 10 個，共 {len(active_lotteries)} 個活動抽獎")

            await interaction.followup.send(embed=embed, ephemeral=True)

        except Exception as e:
            logger.error(f"獲取活動抽獎失敗: {e}")
            await interaction.followup.send("❌ 獲取活動抽獎時發生錯誤", ephemeral=True)

    @ui.button(label="統計儀表板", style=discord.ButtonStyle.secondary, emoji="📊")
    async def lottery_statistics(self, interaction: discord.Interaction, button: ui.Button):
        """打開統計儀表板"""
        try:
            await interaction.response.defer(ephemeral=True)

            # 導入儀表板視圖
            from potato_bot.views.lottery_dashboard_views import (
                LotteryStatsDashboardView,
            )

            # 獲取統計資料
            stats = await self.lottery_manager.dao.get_lottery_statistics(interaction.guild.id)

            # 創建儀表板視圖
            dashboard_view = LotteryStatsDashboardView(interaction.guild.id)

            # 創建統計嵌入
            embed = await dashboard_view._create_stats_embed(stats, 30)

            await interaction.followup.send(embed=embed, view=dashboard_view, ephemeral=True)

        except Exception as e:
            logger.error(f"打開統計儀表板失敗: {e}")
            await interaction.followup.send("❌ 打開統計儀表板時發生錯誤", ephemeral=True)

    @ui.select(
        placeholder="選擇管理操作...",
        options=[
            discord.SelectOption(
                label="結束抽獎",
                description="提前結束指定的抽獎",
                emoji="🛑",
                value="end_lottery",
            ),
            discord.SelectOption(
                label="重新佈署面板",
                description="在指定頻道重新部署抽獎面板",
                emoji="📌",
                value="deploy_panel",
            ),
            discord.SelectOption(
                label="重新開獎",
                description="重新進行開獎",
                emoji="🔄",
                value="redraw",
            ),
            discord.SelectOption(
                label="查看中獎者",
                description="查看抽獎中獎者",
                emoji="🏆",
                value="view_winners",
            ),
            discord.SelectOption(
                label="抽獎設定",
                description="修改抽獎系統設定",
                emoji="⚙️",
                value="settings",
            ),
        ],
    )
    async def management_select(self, interaction: discord.Interaction, select: ui.Select):
        """管理操作選擇"""
        if not await _can_manage_lottery(interaction, self.lottery_manager):
            await interaction.response.send_message(
                "❌ 您沒有權限使用管理功能，請聯絡管理員設定。", ephemeral=True
            )
            return

        action = select.values[0]

        if action == "end_lottery":
            await self._handle_end_lottery(interaction)
        elif action == "deploy_panel":
            await self._handle_deploy_panel(interaction)
        elif action == "redraw":
            await self._handle_redraw(interaction)
        elif action == "view_winners":
            await self._handle_view_winners(interaction)
        elif action == "settings":
            await self._handle_settings(interaction)

    async def _handle_end_lottery(self, interaction: discord.Interaction):
        """處理結束抽獎"""
        modal = EndLotteryModal(self.lottery_manager)
        await interaction.response.send_modal(modal)

    async def _handle_redraw(self, interaction: discord.Interaction):
        """處理重新開獎"""
        modal = RedrawLotteryModal(self.lottery_manager)
        await interaction.response.send_modal(modal)

    async def _handle_view_winners(self, interaction: discord.Interaction):
        """處理查看中獎者"""
        modal = ViewWinnersModal(self.lottery_manager)
        await interaction.response.send_modal(modal)

    async def _handle_settings(self, interaction: discord.Interaction):
        """處理抽獎設定"""
        if not interaction.user.guild_permissions.manage_guild:
            await interaction.response.send_message(
                "❌ 需要管理伺服器權限才能設定抽獎系統", ephemeral=True
            )
            return

        from potato_bot.views.system_admin_views import (
            LotterySettingsView,
            SystemAdminPanel,
        )

        panel = SystemAdminPanel(interaction.user.id)
        embed = await panel._create_lottery_settings_embed(interaction.guild)
        view = LotterySettingsView(interaction.user.id, interaction.guild)
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    async def _handle_deploy_panel(self, interaction: discord.Interaction):
        """處理重新佈署抽獎面板"""
        view = LotteryPanelDeployView(interaction.user.id, self.lottery_manager)
        embed = discord.Embed(
            title="📌 重新佈署抽獎面板",
            description="選擇要部署抽獎面板的文字頻道",
            color=0x3498DB,
        )
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
