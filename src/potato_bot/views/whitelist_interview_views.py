"""
Whitelist interview admin views
白名單語音面試管理面板（無 slash 指令）
"""

from __future__ import annotations

from typing import Optional
from zoneinfo import ZoneInfo

import discord

from potato_bot.db.whitelist_interview_dao import WhitelistInterviewDAO
from potato_bot.services.whitelist_interview_service import (
    WhitelistInterviewService,
    WhitelistInterviewSettings,
)
from potato_shared.logger import logger


def _status_to_text(status: str) -> str:
    mapping = {
        "WAITING": "等待",
        "CALLED": "已叫號",
        "DONE": "已完成",
        "LEFT": "離開",
    }
    return mapping.get(status, status)


class InterviewScheduleModal(discord.ui.Modal):
    """設定面試時段與時區"""

    def __init__(self, parent_view: "WhitelistInterviewAdminView", settings: WhitelistInterviewSettings):
        super().__init__(title="設定面試時段", timeout=180)
        self.parent_view = parent_view
        self.timezone = discord.ui.TextInput(
            label="時區（IANA）",
            default=settings.timezone or "Asia/Taipei",
            placeholder="例如：Asia/Taipei",
            max_length=64,
            required=True,
        )
        self.start_hour = discord.ui.TextInput(
            label="開始小時（0-23）",
            default=str(int(settings.session_start_hour) % 24),
            max_length=2,
            required=True,
        )
        self.end_hour = discord.ui.TextInput(
            label="結束小時（0-23）",
            default=str(int(settings.session_end_hour) % 24),
            max_length=2,
            required=True,
        )
        self.add_item(self.timezone)
        self.add_item(self.start_hour)
        self.add_item(self.end_hour)

    async def on_submit(self, interaction: discord.Interaction):
        tz = str(self.timezone.value).strip() or "Asia/Taipei"
        try:
            ZoneInfo(tz)
        except Exception:
            await interaction.response.send_message(
                "❌ 時區格式錯誤，請使用 IANA 時區，例如 `Asia/Taipei`。",
                ephemeral=True,
            )
            return

        try:
            start = int(str(self.start_hour.value).strip())
            end = int(str(self.end_hour.value).strip())
        except ValueError:
            await interaction.response.send_message("❌ 開始/結束小時必須是數字。", ephemeral=True)
            return

        if start < 0 or start > 23 or end < 0 or end > 23:
            await interaction.response.send_message("❌ 小時範圍需在 0 到 23 之間。", ephemeral=True)
            return

        try:
            saved = await self.parent_view.service.save_settings(
                self.parent_view.guild.id,
                timezone=tz,
                session_start_hour=start,
                session_end_hour=end,
            )
        except Exception as e:
            logger.error(f"更新面試時段失敗: {e}")
            await interaction.response.send_message(
                "❌ 更新失敗，請稍後再試或查看 bot log。",
                ephemeral=True,
            )
            return

        await interaction.response.send_message(
            (
                "✅ 面試時段已更新。\n"
                f"目前：{int(saved.session_start_hour)%24:02d}:00 - "
                f"{int(saved.session_end_hour)%24:02d}:00 ({saved.timezone})\n"
                "回到面板按「🔄 重新整理」可同步顯示。"
            ),
            ephemeral=True,
        )


class WaitingChannelSelect(discord.ui.ChannelSelect):
    def __init__(self, parent_view: "WhitelistInterviewAdminView"):
        super().__init__(
            placeholder="設定等候語音頻道",
            channel_types=[discord.ChannelType.voice],
            min_values=1,
            max_values=1,
            row=0,
        )
        self.parent_view = parent_view

    async def callback(self, interaction: discord.Interaction):
        channel = self.values[0]
        await self.parent_view.service.save_settings(
            self.parent_view.guild.id,
            waiting_channel_id=channel.id,
        )
        await self.parent_view.refresh_message(
            interaction, notice=f"✅ 已設定等候語音：{channel.mention}"
        )


class InterviewChannelSelect(discord.ui.ChannelSelect):
    def __init__(self, parent_view: "WhitelistInterviewAdminView"):
        super().__init__(
            placeholder="設定面試語音頻道",
            channel_types=[discord.ChannelType.voice],
            min_values=1,
            max_values=1,
            row=1,
        )
        self.parent_view = parent_view

    async def callback(self, interaction: discord.Interaction):
        channel = self.values[0]
        await self.parent_view.service.save_settings(
            self.parent_view.guild.id,
            interview_channel_id=channel.id,
        )
        await self.parent_view.refresh_message(
            interaction, notice=f"✅ 已設定面試語音：{channel.mention}"
        )


class NotifyChannelSelect(discord.ui.ChannelSelect):
    def __init__(self, parent_view: "WhitelistInterviewAdminView"):
        super().__init__(
            placeholder="設定面試官通知文字頻道",
            channel_types=[discord.ChannelType.text],
            min_values=1,
            max_values=1,
            row=2,
        )
        self.parent_view = parent_view

    async def callback(self, interaction: discord.Interaction):
        channel = self.values[0]
        await self.parent_view.service.save_settings(
            self.parent_view.guild.id,
            notify_channel_id=channel.id,
        )
        await self.parent_view.refresh_message(
            interaction, notice=f"✅ 已設定通知頻道：{channel.mention}"
        )


class InterviewStaffRoleSelect(discord.ui.RoleSelect):
    def __init__(self, parent_view: "WhitelistInterviewAdminView"):
        super().__init__(
            placeholder="設定面試官身分組",
            min_values=1,
            max_values=1,
            row=3,
        )
        self.parent_view = parent_view

    async def callback(self, interaction: discord.Interaction):
        role = self.values[0]
        await self.parent_view.service.save_settings(
            self.parent_view.guild.id,
            staff_role_id=role.id,
        )
        await self.parent_view.refresh_message(
            interaction, notice=f"✅ 已設定面試官身分組：{role.mention}"
        )


class WhitelistInterviewAdminView(discord.ui.View):
    """海關語音面試管理面板"""

    def __init__(
        self,
        bot: discord.Client,
        guild: discord.Guild,
        user_id: int,
        *,
        allow_configuration: bool = True,
    ):
        super().__init__(timeout=300)
        self.bot = bot
        self.guild = guild
        self.user_id = user_id
        self.allow_configuration = allow_configuration
        self.dao = WhitelistInterviewDAO()
        self.service = WhitelistInterviewService(self.dao)

        if self.allow_configuration:
            self.add_item(WaitingChannelSelect(self))
            self.add_item(InterviewChannelSelect(self))
            self.add_item(NotifyChannelSelect(self))
            self.add_item(InterviewStaffRoleSelect(self))
        else:
            self.remove_item(self.toggle_enabled)
            self.remove_item(self.set_schedule)
            self.remove_item(self.reset_today)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("❌ 只有開啟面板者可以操作。", ephemeral=True)
            return False
        return True

    async def build_embed(self, notice: Optional[str] = None) -> discord.Embed:
        settings = await self.service.load_settings(self.guild.id)
        now_local = settings.local_now()
        queue_date = settings.local_today()
        in_session = settings.is_in_session(now_local)

        status_text = "啟用" if settings.is_enabled else "停用"
        session_text = "開放中" if in_session else "未開放"
        waiting_text = (
            f"<#{settings.waiting_channel_id}>" if settings.waiting_channel_id else "未設定"
        )
        interview_text = (
            f"<#{settings.interview_channel_id}>" if settings.interview_channel_id else "未設定"
        )
        notify_text = f"<#{settings.notify_channel_id}>" if settings.notify_channel_id else "未設定"
        staff_text = f"<@&{settings.staff_role_id}>" if settings.staff_role_id else "未設定"

        embed = discord.Embed(
            title="🎙️ 海關語音面試管理面板",
            description=(
                "使用下方選單與按鈕調整設定與叫號。"
                if self.allow_configuration
                else "此面板僅提供叫號與查看排隊資訊。"
                " 等候/面試頻道與面試官設定請至 Admin 面板。"
            ),
            color=0x3498DB,
        )
        if notice:
            embed.description = f"{notice}\n\n{embed.description}"
        embed.add_field(name="系統狀態", value=status_text, inline=True)
        embed.add_field(name="目前時段", value=session_text, inline=True)
        embed.add_field(
            name="時間",
            value=(
                f"{now_local.strftime('%Y-%m-%d %H:%M:%S')} ({settings.timezone})\n"
                f"時段：{int(settings.session_start_hour)%24:02d}:00 - "
                f"{int(settings.session_end_hour)%24:02d}:00"
            ),
            inline=False,
        )
        embed.add_field(name="等候語音", value=waiting_text, inline=False)
        embed.add_field(name="面試語音", value=interview_text, inline=False)
        embed.add_field(name="通知頻道", value=notify_text, inline=False)
        embed.add_field(name="面試官身分組", value=staff_text, inline=False)

        queue_rows = await self.dao.list_queue(self.guild.id, queue_date)
        waiting_channel_id = settings.waiting_channel_id or 0
        lines: list[str] = []
        for row in queue_rows[:20]:
            user_id = int(row.get("user_id") or 0)
            queue_number = int(row.get("queue_number") or 0)
            status = _status_to_text(str(row.get("status") or "WAITING"))
            member = self.guild.get_member(user_id)
            mention = member.mention if member else f"<@{user_id}>"
            is_waiting_here = (
                bool(
                    member
                    and member.voice
                    and member.voice.channel
                    and member.voice.channel.id == waiting_channel_id
                )
                if waiting_channel_id
                else False
            )
            icon = "🟢" if is_waiting_here else "⚪"
            lines.append(f"{icon} `#{queue_number}` {mention} - {status}")
        if len(queue_rows) > 20:
            lines.append(f"... 其餘 {len(queue_rows) - 20} 位未顯示")

        embed.add_field(
            name=f"今日排隊（{queue_date.isoformat()}）",
            value="\n".join(lines) if lines else "目前無排隊資料",
            inline=False,
        )
        return embed

    async def refresh_message(self, interaction: discord.Interaction, notice: Optional[str] = None):
        embed = await self.build_embed(notice=notice)
        if interaction.response.is_done():
            await interaction.edit_original_response(embed=embed, view=self)
        else:
            await interaction.response.edit_message(embed=embed, view=self)

    async def _call_next(self) -> str:
        settings = await self.service.load_settings(self.guild.id)
        if not settings.is_enabled:
            return "⚠️ 系統尚未啟用。"
        if not settings.is_complete:
            return "⚠️ 設定尚未完整（等候/面試/通知頻道）。"

        waiting_channel = self.guild.get_channel(settings.waiting_channel_id or 0)
        interview_channel = self.guild.get_channel(settings.interview_channel_id or 0)
        if not isinstance(waiting_channel, discord.VoiceChannel) or not isinstance(
            interview_channel, discord.VoiceChannel
        ):
            return "❌ 語音頻道設定無效。"

        queue_date = settings.local_today()
        queue_rows = await self.dao.list_waiting_queue(self.guild.id, queue_date)
        for row in queue_rows:
            user_id = int(row.get("user_id") or 0)
            member = self.guild.get_member(user_id)
            if not member or not member.voice or not member.voice.channel:
                continue
            if member.voice.channel.id != waiting_channel.id:
                continue
            try:
                await member.move_to(interview_channel, reason="Whitelist interview call next (panel)")
                await self.dao.set_status(self.guild.id, user_id, queue_date, "CALLED")
                return (
                    f"✅ 已叫號 `#{row.get('queue_number')}`，"
                    f"已移動 {member.mention} 到 {interview_channel.mention}"
                )
            except Exception as e:
                logger.error(f"面板叫號移動失敗: {e}")
                return "❌ 移動失敗，請檢查機器人語音權限。"

        return "⚠️ 等候區目前沒有可叫號的成員。"

    @discord.ui.button(label="🔁 啟用/停用", style=discord.ButtonStyle.primary, row=4)
    async def toggle_enabled(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self.allow_configuration:
            await interaction.response.send_message("❌ 此面板不可修改設定。", ephemeral=True)
            return
        settings = await self.service.load_settings(self.guild.id)
        new_value = not settings.is_enabled
        await self.service.save_settings(self.guild.id, is_enabled=new_value)
        await self.refresh_message(
            interaction,
            notice=f"✅ 已{'啟用' if new_value else '停用'}語音面試系統。",
        )

    @discord.ui.button(label="🕒 設定時段", style=discord.ButtonStyle.secondary, row=4)
    async def set_schedule(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self.allow_configuration:
            await interaction.response.send_message("❌ 此面板不可修改設定。", ephemeral=True)
            return
        settings = await self.service.load_settings(self.guild.id)
        await interaction.response.send_modal(InterviewScheduleModal(self, settings))

    @discord.ui.button(label="📣 叫下一位", style=discord.ButtonStyle.success, row=4)
    async def call_next(self, interaction: discord.Interaction, button: discord.ui.Button):
        notice = await self._call_next()
        await self.refresh_message(interaction, notice=notice)

    @discord.ui.button(label="🧹 重置今日號碼", style=discord.ButtonStyle.danger, row=4)
    async def reset_today(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self.allow_configuration:
            await interaction.response.send_message("❌ 此面板不可修改設定。", ephemeral=True)
            return
        settings = await self.service.load_settings(self.guild.id)
        queue_date = settings.local_today()
        await self.dao.reset_today_queue(self.guild.id, queue_date)
        await self.refresh_message(
            interaction,
            notice=f"✅ 已重置 {queue_date.isoformat()} 排隊資料，下一位從 1 開始。",
        )

    @discord.ui.button(label="🔄 重新整理", style=discord.ButtonStyle.secondary, row=4)
    async def refresh(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.refresh_message(interaction, notice="✅ 已重新整理。")
