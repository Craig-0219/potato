"""
Whitelist Core
"""

from __future__ import annotations

from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands

from potato_bot.db.whitelist_dao import WhitelistDAO
from potato_bot.services.whitelist_service import PanelService, WhitelistService
from potato_bot.utils.managed_cog import ManagedCog
from potato_bot.views.whitelist_views import PanelView, ReviewView
from potato_shared.logger import logger


class WhitelistCore(ManagedCog):
    """入境審核核心模組"""

    def __init__(self, bot: commands.Bot):
        super().__init__(bot)
        self.bot = bot
        self.dao = WhitelistDAO()
        self.service = WhitelistService(self.dao)
        self.panel_service = PanelService(bot, self.dao)
        self._ready = False

    async def cog_load(self):
        # 確保資料表
        await self.dao._ensure_tables()
        # 重新綁定 pending 審核 view
        await self._rebind_pending_views()

    @commands.Cog.listener()
    async def on_ready(self):
        if self._ready:
            return
        self._ready = True
        await self._rebind_pending_views()

    async def _rebind_pending_views(self):
        """重啟後重新綁定 Persistent Views"""
        try:
            # 面板 view（依各 guild 設定）
            for guild in self.bot.guilds:
                settings = await self.service.load_settings(guild.id)
                if settings.panel_channel_id:
                    panel_view = PanelView(self.bot, self.dao, settings)
                    message = await self.panel_service.ensure_panel_message(settings, panel_view)
                    message_id = message.id if message else settings.panel_message_id
                    if message_id:
                        try:
                            self.bot.add_view(panel_view, message_id=message_id)
                        except Exception:
                            pass

            # 審核 view
            pending = await self.dao.list_pending_with_message()
            for row in pending:
                guild = self.bot.get_guild(row["guild_id"])
                if not guild:
                    continue
                settings = await self.service.load_settings(row["guild_id"])
                application = await self.dao.get_application(row["id"])
                applicant_id = application.get("user_id") if application else 0
                view = ReviewView(
                    self.bot,
                    self.dao,
                    app_id=row["id"],
                    applicant_id=applicant_id,
                    settings=settings,
                )
                try:
                    self.bot.add_view(view, message_id=row["review_message_id"])
                except Exception:
                    pass
        except Exception as e:
            logger.error(f"重新綁定 whitelist views 失敗: {e}")

    # ===== Slash Commands =====

    @app_commands.command(name="whitelist_panel", description="部署或刷新入境申請面板")
    @app_commands.checks.has_permissions(administrator=True)
    async def whitelist_panel(self, interaction: discord.Interaction):
        guild = interaction.guild
        if not guild:
            await interaction.response.send_message("❌ 僅能在伺服器中使用", ephemeral=True)
            return

        settings = await self.service.load_settings(guild.id)
        # 預設 panel_channel 用當前 channel
        if not settings.panel_channel_id:
            settings.panel_channel_id = interaction.channel.id
            await self.service.save_settings(guild.id, panel_channel_id=settings.panel_channel_id)

        panel_view = PanelView(self.bot, self.dao, settings)
        message = await self.panel_service.ensure_panel_message(settings, panel_view)

        # 註冊 persistent view（無 message_id 仍可讓新訊息工作）
        try:
            message_id = message.id if message else settings.panel_message_id
            if message_id:
                self.bot.add_view(panel_view, message_id=message_id)
        except Exception:
            pass

        await interaction.response.send_message("✅ 入境申請面板已部署/刷新", ephemeral=True)

async def setup(bot: commands.Bot):
    await bot.add_cog(WhitelistCore(bot))
