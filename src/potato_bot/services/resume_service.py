"""
履歷服務模組。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, List, Optional

import json
import discord

from potato_bot.db.resume_dao import ResumeDAO
from potato_shared.logger import logger


def _normalize_role_ids(value: Any) -> List[int]:
    if value is None:
        return []
    if isinstance(value, list):
        return [int(role_id) for role_id in value]
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
            if isinstance(parsed, list):
                return [int(role_id) for role_id in parsed]
        except json.JSONDecodeError:
            return []
    return []


@dataclass
class ResumeCompanySettings:
    company_id: int
    guild_id: int
    company_name: str
    panel_channel_id: Optional[int] = None
    review_channel_id: Optional[int] = None
    review_role_ids: List[int] | None = None
    approved_role_ids: List[int] | None = None
    manageable_role_ids: List[int] | None = None
    panel_message_id: Optional[int] = None
    is_enabled: bool = True

    @property
    def is_complete(self) -> bool:
        return bool(self.panel_channel_id and self.review_channel_id and self.review_role_ids)

    def get_manageable_role_ids(self) -> List[int]:
        return list(self.manageable_role_ids or [])


class ResumeService:
    """履歷設定服務（高階封裝）。"""

    def __init__(self, dao: ResumeDAO):
        self.dao = dao

    async def load_company(self, company_id: int) -> Optional[ResumeCompanySettings]:
        data = await self.dao.get_company(company_id)
        if not data:
            return None
        return ResumeCompanySettings(
            company_id=data["id"],
            guild_id=data["guild_id"],
            company_name=data["company_name"],
            panel_channel_id=data.get("panel_channel_id"),
            review_channel_id=data.get("review_channel_id"),
            review_role_ids=_normalize_role_ids(data.get("review_role_ids")),
            approved_role_ids=_normalize_role_ids(data.get("approved_role_ids")),
            manageable_role_ids=_normalize_role_ids(data.get("manageable_role_ids")),
            panel_message_id=data.get("panel_message_id"),
            is_enabled=bool(data.get("is_enabled", True)),
        )

    async def load_company_by_name(
        self, guild_id: int, company_name: str
    ) -> Optional[ResumeCompanySettings]:
        data = await self.dao.get_company_by_name(guild_id, company_name)
        if not data:
            return None
        return ResumeCompanySettings(
            company_id=data["id"],
            guild_id=data["guild_id"],
            company_name=data["company_name"],
            panel_channel_id=data.get("panel_channel_id"),
            review_channel_id=data.get("review_channel_id"),
            review_role_ids=_normalize_role_ids(data.get("review_role_ids")),
            approved_role_ids=_normalize_role_ids(data.get("approved_role_ids")),
            manageable_role_ids=_normalize_role_ids(data.get("manageable_role_ids")),
            panel_message_id=data.get("panel_message_id"),
            is_enabled=bool(data.get("is_enabled", True)),
        )

    async def list_companies(self, guild_id: int) -> List[ResumeCompanySettings]:
        rows = await self.dao.list_companies(guild_id)
        companies: List[ResumeCompanySettings] = []
        for row in rows:
            companies.append(
                ResumeCompanySettings(
                    company_id=row["id"],
                    guild_id=row["guild_id"],
                    company_name=row["company_name"],
                    panel_channel_id=row.get("panel_channel_id"),
                    review_channel_id=row.get("review_channel_id"),
                    review_role_ids=_normalize_role_ids(row.get("review_role_ids")),
                    approved_role_ids=_normalize_role_ids(row.get("approved_role_ids")),
                    manageable_role_ids=_normalize_role_ids(row.get("manageable_role_ids")),
                    panel_message_id=row.get("panel_message_id"),
                    is_enabled=bool(row.get("is_enabled", True)),
                )
            )
        return companies

    async def save_company(
        self,
        guild_id: int,
        company_name: str,
        **settings: Any,
    ) -> ResumeCompanySettings:
        current = await self.dao.get_company_by_name(guild_id, company_name) or {}
        payload = {
            "panel_channel_id": current.get("panel_channel_id"),
            "review_channel_id": current.get("review_channel_id"),
            "review_role_ids": _normalize_role_ids(current.get("review_role_ids")),
            "approved_role_ids": _normalize_role_ids(current.get("approved_role_ids")),
            "manageable_role_ids": _normalize_role_ids(current.get("manageable_role_ids")),
            "panel_message_id": current.get("panel_message_id"),
            "is_enabled": current.get("is_enabled", True),
        }

        for key, value in settings.items():
            if value is not None:
                payload[key] = value

        await self.dao.upsert_company(guild_id, company_name, **payload)
        company = await self.load_company_by_name(guild_id, company_name)
        if not company:
            raise RuntimeError("儲存履歷公司設定失敗。")
        return company

    async def rename_company(
        self,
        guild_id: int,
        company_id: int,
        new_name: str,
    ) -> ResumeCompanySettings:
        current = await self.dao.get_company(company_id)
        if not current or current.get("guild_id") != guild_id:
            raise RuntimeError("找不到要更名的公司。")

        if current.get("company_name") == new_name:
            company = await self.load_company(company_id)
            if not company:
                raise RuntimeError("取得公司資料失敗。")
            return company

        existing = await self.dao.get_company_by_name(guild_id, new_name)
        if existing and existing.get("id") != company_id:
            raise ValueError("公司已存在。")

        updated = await self.dao.rename_company(guild_id, company_id, new_name)
        if not updated:
            raise RuntimeError("公司更名失敗。")

        company = await self.load_company(company_id)
        if not company:
            raise RuntimeError("取得公司資料失敗。")
        return company

    async def delete_company(self, guild_id: int, company_id: int) -> bool:
        current = await self.dao.get_company(company_id)
        if not current or current.get("guild_id") != guild_id:
            return False
        return await self.dao.delete_company(guild_id, company_id)


class ResumePanelService:
    """處理履歷面板訊息。"""

    def __init__(self, bot: discord.Client, dao: ResumeDAO):
        self.bot = bot
        self.dao = dao

    async def ensure_panel_message(
        self, settings: ResumeCompanySettings, view: discord.ui.View
    ) -> Optional[discord.Message]:
        if not settings.panel_channel_id:
            logger.warning("履歷公司未設定 panel_channel_id。")
            return None

        guild = self.bot.get_guild(settings.guild_id)
        if not guild:
            return None

        if hasattr(guild, "get_channel_or_thread"):
            channel = guild.get_channel_or_thread(settings.panel_channel_id)
        else:
            channel = guild.get_channel(settings.panel_channel_id) or guild.get_thread(
                settings.panel_channel_id
            )
        if not channel:
            logger.warning("找不到履歷面板頻道。")
            return None
        if not isinstance(channel, (discord.TextChannel, discord.Thread)):
            logger.warning("履歷面板頻道類型不支援。")
            return None

        embed = discord.Embed(
            title=f"履歷提交櫃台- {settings.company_name}",
            description="點擊下方按鈕以提交您的履歷。提交後，相關負責人員將會收到通知並進行審核。",
            color=0x3498DB,
        )

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
            await self.dao.update_panel_message_id(settings.company_id, message.id)
        else:
            try:
                await message.edit(embed=embed, view=view)
            except Exception as e:
                logger.warning(f"更新履歷面板訊息失敗: {e}")

        return message
