"""
Category auto-create helpers.
"""

from __future__ import annotations

from typing import Dict, Iterable

import discord


def can_use_category_auto(
    member: discord.Member,
    allowed_role_ids: Iterable[int],
    *,
    is_owner: bool = False,
) -> bool:
    if is_owner:
        return True
    allowed_set = set(allowed_role_ids or [])
    if allowed_set:
        member_role_ids = {role.id for role in member.roles}
        return bool(member_role_ids & allowed_set)
    return member.guild_permissions.administrator or member.guild_permissions.manage_guild


def build_manager_overwrites(
    guild: discord.Guild, manager_role_ids: Iterable[int]
) -> Dict[discord.abc.Snowflake, discord.PermissionOverwrite]:
    overwrites: Dict[discord.abc.Snowflake, discord.PermissionOverwrite] = {}
    for role_id in manager_role_ids or []:
        role = guild.get_role(int(role_id))
        if not role:
            continue
        overwrites[role] = discord.PermissionOverwrite(
            view_channel=True,
            manage_channels=True,
        )
    return overwrites
