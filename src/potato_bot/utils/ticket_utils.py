# bot/utils/ticket_utils.py - 票券系統工具函數

import re
from typing import Any, Dict, List, Optional

import discord

from potato_bot.utils.ticket_constants import TicketConstants


class TicketPermissionChecker:
    """票券權限檢查器"""

    @staticmethod
    def is_admin(user: discord.Member) -> bool:
        """檢查是否為管理員"""
        if not user:
            return False
        return user.guild_permissions.manage_guild or user.guild_permissions.administrator

    @staticmethod
    def is_support_staff(user: discord.Member, support_roles: List[int]) -> bool:
        """檢查是否為客服人員"""
        if not user:
            return False

        # 管理員自動視為客服
        if TicketPermissionChecker.is_admin(user):
            return True

        # 檢查客服身分組
        user_role_ids = {role.id for role in user.roles}
        return any(role_id in user_role_ids for role_id in support_roles)

    @staticmethod
    def can_manage_ticket(
        user: discord.Member,
        ticket_info: Dict[str, Any],
        support_roles: List[int],
    ) -> bool:
        """檢查是否可以管理票券"""
        if not user or not ticket_info:
            return False

        # 票券創建者可以管理
        if str(user.id) == ticket_info.get("discord_id"):
            return True

        # 客服人員可以管理
        return TicketPermissionChecker.is_support_staff(user, support_roles)

    @staticmethod
    def can_close_ticket(
        user: discord.Member,
        ticket_info: Dict[str, Any],
        support_roles: List[int],
    ) -> bool:
        """檢查是否可以關閉票券"""
        return TicketPermissionChecker.can_manage_ticket(user, ticket_info, support_roles)

    @staticmethod
    def can_view_ticket(
        user: discord.Member,
        ticket_info: Dict[str, Any],
        support_roles: List[int],
    ) -> bool:
        """檢查是否可以查看票券"""
        if not user or not ticket_info:
            return False

        # 票券創建者可以查看
        if str(user.id) == ticket_info.get("discord_id"):
            return True

        # 客服人員可以查看所有票券
        return TicketPermissionChecker.is_support_staff(user, support_roles)


def is_ticket_channel(channel: discord.TextChannel) -> bool:
    """檢查是否為票券頻道"""
    if not channel or not hasattr(channel, "name"):
        return False
    name = channel.name or ""
    if name.startswith("ticket-"):
        return True
    return re.match(r"^[^A-Za-z0-9]*ticket-", name) is not None


def get_support_roles_for_ticket(
    settings: Dict[str, Any], ticket_type: Optional[str]
) -> List[int]:
    """依票券類型取得對應的處理角色列表"""
    settings = settings or {}
    support_roles = settings.get("support_roles") or []
    sponsor_roles = settings.get("sponsor_support_roles") or []

    if ticket_type == TicketConstants.SPONSOR_TICKET_NAME:
        return sponsor_roles or support_roles

    return support_roles


__all__ = [
    "TicketPermissionChecker",
    "is_ticket_channel",
    "get_support_roles_for_ticket",
]
