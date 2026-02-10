"""
Whitelist interview core
白名單語音面試：等候區排號、書審摘要通知
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Optional

import discord
from discord.ext import commands

from potato_bot.db.whitelist_dao import WhitelistDAO
from potato_bot.db.whitelist_interview_dao import WhitelistInterviewDAO
from potato_bot.services.whitelist_interview_service import (
    WhitelistInterviewService,
    WhitelistInterviewSettings,
)
from potato_bot.utils.managed_cog import ManagedCog
from potato_shared.logger import logger


def _parse_answers_json(raw: Any) -> dict[str, Any]:
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str):
        try:
            loaded = json.loads(raw)
            if isinstance(loaded, dict):
                return loaded
        except json.JSONDecodeError:
            return {}
    return {}


def _short_text(value: Any, limit: int = 1000) -> str:
    if value is None:
        return "未填"
    text = str(value).strip()
    if not text:
        return "未填"
    return text[:limit]


class WhitelistInterviewCore(ManagedCog):
    """白名單語音面試核心"""

    def __init__(self, bot: commands.Bot):
        super().__init__(bot)
        self.bot = bot
        self.whitelist_dao = WhitelistDAO()
        self.interview_dao = WhitelistInterviewDAO()
        self.service = WhitelistInterviewService(self.interview_dao)

    async def cog_load(self):
        await self.whitelist_dao._ensure_tables()
        await self.interview_dao._ensure_tables()

    # ===== Voice Queue =====
    @commands.Cog.listener()
    async def on_voice_state_update(
        self, member: discord.Member, before: discord.VoiceState, after: discord.VoiceState
    ):
        if member.bot:
            return
        if not member.guild:
            return

        before_channel_id = before.channel.id if before.channel else None
        after_channel_id = after.channel.id if after.channel else None
        if before_channel_id == after_channel_id:
            return

        try:
            settings = await self.service.load_settings(member.guild.id)
            if not settings.is_enabled or not settings.waiting_channel_id:
                return

            waiting_channel_id = settings.waiting_channel_id
            interview_channel_id = settings.interview_channel_id
            queue_date = settings.local_today()

            # 等候區 -> 面試區
            if (
                before_channel_id == waiting_channel_id
                and interview_channel_id
                and after_channel_id == interview_channel_id
            ):
                await self.interview_dao.set_status(
                    member.guild.id, member.id, queue_date, "CALLED"
                )
                return

            # 面試區 -> 其他
            if (
                interview_channel_id
                and before_channel_id == interview_channel_id
                and after_channel_id != interview_channel_id
            ):
                await self.interview_dao.set_status(member.guild.id, member.id, queue_date, "DONE")
                return

            # 進入等候區
            if after_channel_id == waiting_channel_id and before_channel_id != waiting_channel_id:
                await self._handle_waiting_join(member, settings, queue_date)
                return

            # 離開等候區
            if before_channel_id == waiting_channel_id and after_channel_id != waiting_channel_id:
                await self.interview_dao.set_status(member.guild.id, member.id, queue_date, "LEFT")
                return
        except Exception as e:
            logger.error(f"whitelist interview voice listener 失敗: {e}")

    async def _handle_waiting_join(
        self, member: discord.Member, settings: WhitelistInterviewSettings, queue_date
    ) -> None:
        if not settings.is_in_session():
            await self._notify_not_in_session(member, settings)
            return

        latest_application = await self.whitelist_dao.get_latest_application(
            member.guild.id, member.id
        )
        if not latest_application:
            await self._notify_missing_application(member)
            return

        queue_entry = await self.interview_dao.get_or_create_queue_entry(
            guild_id=member.guild.id,
            user_id=member.id,
            username=str(member),
            original_nickname=member.nick,
            queue_date=queue_date,
        )
        queue_number = int(queue_entry["queue_number"])

        await self.interview_dao.set_status(member.guild.id, member.id, queue_date, "WAITING")
        await self._apply_queue_nickname(member, queue_number)

        if queue_entry.get("notified_message_id"):
            return

        message_id = await self._send_interview_notification(
            member=member,
            settings=settings,
            queue_number=queue_number,
            application=latest_application,
        )
        if message_id:
            await self.interview_dao.set_notified_message_id(
                member.guild.id,
                member.id,
                queue_date,
                message_id,
            )

    async def _notify_not_in_session(
        self, member: discord.Member, settings: WhitelistInterviewSettings
    ) -> None:
        start = int(settings.session_start_hour) % 24
        end = int(settings.session_end_hour) % 24
        tz_name = settings.timezone
        try:
            await member.send(
                f"目前不在海關語音面試時段。\n時段：{start:02d}:00 - {end:02d}:00 ({tz_name})"
            )
        except Exception:
            pass

    async def _notify_missing_application(self, member: discord.Member) -> None:
        try:
            await member.send("你尚未完成書面白名單申請，無法加入語音面試排隊。")
        except Exception:
            pass

    async def _apply_queue_nickname(self, member: discord.Member, queue_number: int) -> None:
        guild = member.guild
        me = guild.me
        if not me and self.bot.user:
            me = guild.get_member(self.bot.user.id)
        if not me:
            return
        if not me.guild_permissions.manage_nicknames:
            return
        if member == guild.owner:
            return
        if me.top_role <= member.top_role:
            return

        target_nick = str(queue_number)
        if member.nick == target_nick:
            return

        try:
            await member.edit(nick=target_nick, reason="Whitelist interview queue")
        except Exception:
            pass

    async def _send_interview_notification(
        self,
        member: discord.Member,
        settings: WhitelistInterviewSettings,
        queue_number: int,
        application: dict[str, Any],
    ) -> Optional[int]:
        notify_channel = member.guild.get_channel(settings.notify_channel_id or 0)
        if not isinstance(notify_channel, discord.TextChannel):
            return None

        answers = _parse_answers_json(application.get("answers_json"))
        status_text = str(application.get("status") or "UNKNOWN")
        app_id = application.get("id")
        created_at = application.get("created_at")
        created_text = (
            discord.utils.format_dt(created_at, "f")
            if isinstance(created_at, datetime)
            else "未知"
        )

        embed = discord.Embed(
            title="🎙️ 海關語音面試排隊通知",
            description=(
                f"排隊號碼：`#{queue_number}`\n"
                f"申請人：{member.mention} (`{member.id}`)\n"
                f"等候語音：<#{settings.waiting_channel_id}>"
            ),
            color=0x3498DB,
        )
        embed.add_field(name="書審狀態", value=status_text, inline=True)
        embed.add_field(name="申請單號", value=f"#{app_id}" if app_id else "未知", inline=True)
        embed.add_field(name="書審提交時間", value=created_text, inline=False)
        embed.add_field(
            name="角色名",
            value=_short_text(answers.get("character_name"), 200),
            inline=False,
        )
        embed.add_field(name="年齡", value=_short_text(answers.get("age"), 200), inline=False)
        embed.add_field(
            name="角色背景",
            value=_short_text(answers.get("background"), 1024),
            inline=False,
        )
        embed.add_field(
            name="超人扮演/情緒帶入示例",
            value=_short_text(answers.get("roleplay_examples"), 1024),
            inline=False,
        )
        embed.add_field(
            name="同意規章",
            value=_short_text(answers.get("rules"), 300),
            inline=False,
        )

        content = None
        allowed_mentions = None
        if settings.staff_role_id:
            role = member.guild.get_role(settings.staff_role_id)
            if role:
                content = role.mention
                allowed_mentions = discord.AllowedMentions(roles=True)

        try:
            message = await notify_channel.send(
                content=content,
                embed=embed,
                allowed_mentions=allowed_mentions,
            )
            return message.id
        except Exception as e:
            logger.error(f"發送 whitelist interview 通知失敗: {e}")
            return None


async def setup(bot: commands.Bot):
    await bot.add_cog(WhitelistInterviewCore(bot))
