# bot/cogs/category_auto_core.py
"""
Category auto-create cog.
"""

from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands

from potato_bot.db.category_auto_dao import CategoryAutoDAO
from potato_bot.services.category_auto_service import can_use_category_auto
from potato_bot.views.system_admin_views import CategoryAutoCreateView, CATEGORY_BULK_LIMIT


class CategoryAuto(commands.Cog):
    """類別自動建立功能"""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.dao = CategoryAutoDAO()

    @app_commands.command(name="category_auto", description="批量建立類別")
    async def category_auto(self, interaction: discord.Interaction):
        if not interaction.guild:
            await interaction.response.send_message("❌ 此功能僅能在伺服器中使用", ephemeral=True)
            return

        settings = await self.dao.get_settings(interaction.guild.id)
        allowed_roles = settings.get("allowed_role_ids", [])
        is_owner = False
        try:
            is_owner = await self.bot.is_owner(interaction.user)
        except Exception:
            is_owner = False

        if not can_use_category_auto(interaction.user, allowed_roles, is_owner=is_owner):
            await interaction.response.send_message("❌ 你沒有使用此功能的權限", ephemeral=True)
            return

        manager_roles = settings.get("manager_role_ids", [])
        manager_text = (
            "未設定（不額外授權）"
            if not manager_roles
            else "、".join(
                role.mention
                for role in (interaction.guild.get_role(rid) for rid in manager_roles)
                if role
            )
        )
        if not manager_text:
            manager_text = "未設定（不額外授權）"

        embed = discord.Embed(
            title="🗂️ 類別批量建立",
            description="點擊下方按鈕輸入類別名稱（每行一個）。",
            color=0x3498DB,
        )
        embed.add_field(name="預設管理身分組", value=manager_text, inline=False)
        embed.add_field(
            name="限制",
            value=f"每次最多 {CATEGORY_BULK_LIMIT} 個類別",
            inline=False,
        )

        view = CategoryAutoCreateView(interaction.user.id, interaction.guild)
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(CategoryAuto(bot))
