"""
Whitelist services
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional

import discord
import json

from potato_bot.db.whitelist_dao import WhitelistDAO
from potato_bot.db.whitelist_interview_dao import WhitelistInterviewDAO
from potato_bot.services.whitelist_interview_service import WhitelistInterviewService
from potato_shared.logger import logger


@dataclass
class WhitelistSettings:
    guild_id: int
    panel_channel_id: Optional[int] = None
    review_channel_id: Optional[int] = None
    result_channel_id: Optional[int] = None
    role_newcomer_ids: list[int] | None = None
    role_citizen_id: Optional[int] = None
    role_staff_id: Optional[int] = None
    nickname_role_id: Optional[int] = None
    nickname_prefix: Optional[str] = None
    panel_message_id: Optional[int] = None

    @property
    def is_complete(self) -> bool:
        newcomer_ready = bool(self.role_newcomer_ids)
        required = [
            self.panel_channel_id,
            self.review_channel_id,
            self.result_channel_id,
            newcomer_ready,
            self.role_citizen_id,
            self.role_staff_id,
        ]
        return all(required)


class WhitelistService:
    """高層操作服務"""

    def __init__(self, dao: WhitelistDAO):
        self.dao = dao

    async def load_settings(self, guild_id: int) -> WhitelistSettings:
        data = await self.dao.get_settings(guild_id)
        newcomer_ids = []
        if data.get("role_newcomer_ids"):
            try:
                newcomer_ids = json.loads(data.get("role_newcomer_ids"))
            except json.JSONDecodeError:
                newcomer_ids = []
        return WhitelistSettings(
            guild_id=guild_id,
            panel_channel_id=data.get("panel_channel_id"),
            review_channel_id=data.get("review_channel_id"),
            result_channel_id=data.get("result_channel_id"),
            role_newcomer_ids=newcomer_ids,
            role_citizen_id=data.get("role_citizen_id"),
            role_staff_id=data.get("role_staff_id"),
            nickname_role_id=data.get("nickname_role_id"),
            nickname_prefix=data.get("nickname_prefix"),
            panel_message_id=data.get("panel_message_id"),
        )

    async def save_settings(self, guild_id: int, **settings: Any) -> WhitelistSettings:
        await self.dao.upsert_settings(guild_id, **settings)
        return await self.load_settings(guild_id)


class RoleService:
    """處理審核通過的身分組"""

    def __init__(self, settings: WhitelistSettings):
        self.settings = settings

    async def apply_approved(self, member: discord.Member, character_name: Optional[str] = None) -> None:
        """移除初始身分並加入市民"""
        try:
            newcomer_roles = []
            if self.settings.role_newcomer_ids:
                newcomer_roles = [
                    member.guild.get_role(role_id)
                    for role_id in self.settings.role_newcomer_ids
                ]
                newcomer_roles = [role for role in newcomer_roles if role]
            citizen = (
                member.guild.get_role(self.settings.role_citizen_id)
                if self.settings.role_citizen_id
                else None
            )

            if newcomer_roles:
                await member.remove_roles(*newcomer_roles, reason="Whitelist approved")

            role_ids = {role.id for role in member.roles}

            if citizen and citizen.id not in role_ids:
                await member.add_roles(citizen, reason="Whitelist approved")
                role_ids.add(citizen.id)

            nickname_role = None
            if self.settings.nickname_role_id:
                nickname_role = member.guild.get_role(self.settings.nickname_role_id)
                if nickname_role and nickname_role.id not in role_ids:
                    await member.add_roles(nickname_role, reason="Whitelist approved")
                    role_ids.add(nickname_role.id)
        except Exception as e:
            logger.error(f"身分組處理失敗: {e}")

        # 暱稱更新（可選）
        try:
            nickname_role_id = self.settings.nickname_role_id
            prefix = self.settings.nickname_prefix or ""
            if not nickname_role_id or not character_name:
                return

            if nickname_role_id in {role.id for role in member.roles}:
                name = str(character_name).strip()
                new_nick = f"{prefix}{name}"
                if not new_nick:
                    return
                if len(new_nick) > 32:
                    new_nick = new_nick[:32]
                await member.edit(nick=new_nick, reason="Whitelist approved")
        except Exception as e:
            logger.error(f"暱稱更新失敗: {e}")


class AnnounceService:
    """公告與 DM"""

    def __init__(self, bot: discord.Client, settings: WhitelistSettings):
        self.bot = bot
        self.settings = settings

    async def post_result(
        self,
        application: Dict[str, Any],
        status: str,
        note: Optional[str] = None,
    ) -> None:
        """公告結果並通知玩家"""
        guild = self.bot.get_guild(application["guild_id"])
        if not guild:
            return

        user_id = application["user_id"]
        mention = f"<@{user_id}>"
        status_emoji = {"APPROVED": "✅", "DENIED": "❌", "NEED_MORE": "🔁"}.get(
            status, "ℹ️"
        )

        embed = discord.Embed(
            title=f"{status_emoji} 入境審核結果",
            description=f"{mention}",
            color={"APPROVED": 0x2ecc71, "DENIED": 0xe74c3c, "NEED_MORE": 0xf1c40f}.get(
                status, 0x3498db
            ),
        )
        status_text = {"APPROVED": "通過", "DENIED": "拒絕", "NEED_MORE": "補件"}.get(status, status)
        embed.add_field(name="申請編號", value=f"#{application['id']}", inline=True)
        embed.add_field(name="狀態", value=status_text, inline=True)
        if note:
            embed.add_field(name="備註", value=note[:1000], inline=False)
        if status == "NEED_MORE":
            embed.add_field(
                name="補件提醒",
                value="請再次點擊「入境申請」按鈕補件，系統會自動帶入上次申請內容。",
                inline=False,
            )

        # 公告頻道
        if self.settings.result_channel_id:
            channel = guild.get_channel(self.settings.result_channel_id)
            if channel:
                try:
                    await channel.send(content=mention, embed=embed)
                except Exception as e:
                    logger.error(f"公告結果失敗: {e}")

        # DM 玩家（如果可能）
        try:
            user = guild.get_member(user_id) or await self.bot.fetch_user(user_id)
            if user:
                await user.send(embed=embed)
        except Exception:
            # 忽略 DM 失敗
            pass


class PanelService:
    """處理面板訊息維護"""

    def __init__(self, bot: discord.Client, dao: WhitelistDAO):
        self.bot = bot
        self.dao = dao

    async def ensure_panel_message(self, settings: WhitelistSettings, view: discord.ui.View):
        """確保面板訊息存在，缺失時重發並 pin"""
        if not settings.panel_channel_id:
            logger.warning("未設定 panel_channel_id，無法建立面板")
            return None

        guild = self.bot.get_guild(settings.guild_id)
        if not guild:
            return None

        channel = guild.get_channel(settings.panel_channel_id)
        if not channel:
            logger.warning("找不到入境申請頻道")
            return None

        interview_section = (
            "狀態：未設定\n"
            "時段：未設定\n"
            "等候區：未設定\n"
            "提醒：填寫完申請表後，請於指定時段至等候區準備面試。"
        )
        try:
            interview_settings = await WhitelistInterviewService(
                WhitelistInterviewDAO()
            ).load_settings(settings.guild_id)
            start_hour = int(interview_settings.session_start_hour) % 24
            end_hour = int(interview_settings.session_end_hour) % 24
            status_text = "已啟用" if interview_settings.is_enabled else "未啟用"
            waiting_channel_id = interview_settings.waiting_channel_id
            waiting_text = (
                f"<#{waiting_channel_id}>"
                if waiting_channel_id
                else "未設定"
            )
            interview_section = (
                f"狀態：{status_text}\n"
                f"時段：{start_hour:02d}:00 - {end_hour:02d}:00 ({interview_settings.timezone})\n"
                f"等候區：{waiting_text}\n"
                "提醒：填寫完申請表後，請於指定時段至等候區準備面試。"
            )
        except Exception as e:
            logger.warning(f"讀取 whitelist interview 設定失敗: {e}")

        embed = discord.Embed(
            title="🛂 入境申請櫃台",
            description="點擊下方按鈕填寫入境申請表。",
            color=0x3498DB,
        )
        embed.add_field(name="🎙️ 海關語音面試資訊", value=interview_section, inline=False)

        message = None
        if settings.panel_message_id:
            try:
                message = await channel.fetch_message(settings.panel_message_id)
            except Exception:
                message = None

        if message is None:
            message = await channel.send(embed=embed, view=view)
            try:
                await message.pin()
            except Exception:
                pass
            await self.dao.update_panel_message_id(settings.guild_id, message.id)
        else:
            try:
                await message.edit(embed=embed, view=view)
            except Exception as e:
                logger.warning(f"更新入境申請面板訊息失敗: {e}")

        return message
