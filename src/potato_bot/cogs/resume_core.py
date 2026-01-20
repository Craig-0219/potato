"""
Resume Core
"""

from __future__ import annotations

from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands

from potato_bot.db.resume_dao import ResumeDAO
from potato_bot.services.resume_service import ResumePanelService, ResumeService
from potato_bot.utils.managed_cog import ManagedCog
from potato_bot.views.resume_views import (
    CompanyRolePanelView,
    CompanyRoleSelectView,
    ResumePanelView,
    ResumeReviewView,
    build_company_role_panel_embed,
    build_company_role_select_embed,
)
from potato_shared.logger import logger


class ResumeCore(ManagedCog):
    """Resume system core."""

    def __init__(self, bot: commands.Bot):
        super().__init__(bot)
        self.bot = bot
        self.dao = ResumeDAO()
        self.service = ResumeService(self.dao)
        self.panel_service = ResumePanelService(bot, self.dao)
        self._ready = False

    async def cog_load(self):
        await self.dao._ensure_tables()
        await self._rebind_pending_views()

    @commands.Cog.listener()
    async def on_ready(self):
        if self._ready:
            return
        self._ready = True
        await self._rebind_pending_views()

    async def _rebind_pending_views(self):
        """Rebind persistent views on restart."""
        try:
            for guild in self.bot.guilds:
                companies = await self.service.list_companies(guild.id)
                for settings in companies:
                    if not settings.panel_channel_id or not settings.is_enabled:
                        continue
                    panel_view = ResumePanelView(self.bot, self.dao, settings)
                    message = await self.panel_service.ensure_panel_message(settings, panel_view)
                    message_id = message.id if message else settings.panel_message_id
                    if message_id:
                        try:
                            self.bot.add_view(panel_view, message_id=message_id)
                        except Exception:
                            pass

            pending = await self.dao.list_pending_with_message()
            for row in pending:
                guild = self.bot.get_guild(row["guild_id"])
                if not guild:
                    continue
                settings = await self.service.load_company(row["company_id"])
                if not settings:
                    continue
                application = await self.dao.get_application(row["id"])
                applicant_id = application.get("user_id") if application else 0
                view = ResumeReviewView(
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
            logger.error(f"Resume view rebind failed: {e}")

    # ===== Slash Commands =====

    @app_commands.command(name="resume_company", description="創建或者更新履歷設定")
    @app_commands.checks.has_permissions(administrator=True)
    async def resume_company(
        self,
        interaction: discord.Interaction,
        company_name: str,
        panel_channel: Optional[discord.TextChannel] = None,
        review_channel: Optional[discord.TextChannel] = None,
        review_role_1: Optional[discord.Role] = None,
        review_role_2: Optional[discord.Role] = None,
        review_role_3: Optional[discord.Role] = None,
        review_role_4: Optional[discord.Role] = None,
        review_role_5: Optional[discord.Role] = None,
        approved_role_1: Optional[discord.Role] = None,
        approved_role_2: Optional[discord.Role] = None,
        approved_role_3: Optional[discord.Role] = None,
        approved_role_4: Optional[discord.Role] = None,
        approved_role_5: Optional[discord.Role] = None,
        enabled: Optional[bool] = None,
    ):
        guild = interaction.guild
        if not guild:
            await interaction.response.send_message("此指令必須在指定頻道使用", ephemeral=True)
            return

        existing = await self.service.load_company_by_name(guild.id, company_name)
        if not existing and review_channel is None:
            await interaction.response.send_message(
                "必須設置審核頻道",
                ephemeral=True,
            )
            return

        panel_channel_id = (
            panel_channel.id
            if panel_channel
            else (existing.panel_channel_id if existing else interaction.channel.id)
        )
        review_channel_id = (
            review_channel.id if review_channel else (existing.review_channel_id if existing else None)
        )
        if not review_channel_id:
            await interaction.response.send_message(
                "尚未設置審核頻道",
                ephemeral=True,
            )
            return

        role_inputs = [review_role_1, review_role_2, review_role_3, review_role_4, review_role_5]
        roles_provided = any(role is not None for role in role_inputs)
        role_ids = [role.id for role in role_inputs if role]
        role_ids = list(dict.fromkeys(role_ids))

        approved_role_inputs = [
            approved_role_1,
            approved_role_2,
            approved_role_3,
            approved_role_4,
            approved_role_5,
        ]
        approved_roles_provided = any(role is not None for role in approved_role_inputs)
        approved_role_ids = [role.id for role in approved_role_inputs if role]
        approved_role_ids = list(dict.fromkeys(approved_role_ids))

        settings = await self.service.save_company(
            guild.id,
            company_name,
            panel_channel_id=panel_channel_id,
            review_channel_id=review_channel_id,
            review_role_ids=(role_ids if roles_provided else None),
            approved_role_ids=(approved_role_ids if approved_roles_provided else None),
            is_enabled=enabled,
        )

        if settings.panel_channel_id:
            panel_view = ResumePanelView(self.bot, self.dao, settings)
            try:
                message = await self.panel_service.ensure_panel_message(settings, panel_view)
                message_id = message.id if message else settings.panel_message_id
                if message_id:
                    self.bot.add_view(panel_view, message_id=message_id)
            except Exception as e:
                logger.error(f"面板刷新失敗: {e}")

        embed = discord.Embed(
            title="履歷設定",
            description=f"公司名稱: {settings.company_name}",
            color=0x3498DB,
        )
        embed.add_field(
            name="頻道",
            value=f"面板: <#{settings.panel_channel_id}>\審核: <#{settings.review_channel_id}>",
            inline=False,
        )
        if settings.review_role_ids:
            role_text = ", ".join(f"<@&{role_id}>" for role_id in settings.review_role_ids)
        else:
            role_text = "Not set"
        embed.add_field(name="Reviewer roles", value=role_text, inline=False)
        if settings.approved_role_ids:
            approved_text = ", ".join(f"<@&{role_id}>" for role_id in settings.approved_role_ids)
        else:
            approved_text = "Not set"
        embed.add_field(name="Approved roles", value=approved_text, inline=False)
        embed.add_field(name="Enabled", value="Yes" if settings.is_enabled else "No", inline=False)

        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="resume_panel", description="部屬或刷新履歷面板")
    @app_commands.checks.has_permissions(administrator=True)
    async def resume_panel(
        self,
        interaction: discord.Interaction,
        company_name: str,
        panel_channel: Optional[discord.TextChannel] = None,
    ):
        guild = interaction.guild
        if not guild:
            await interaction.response.send_message("此指令必須在指定頻道使用", ephemeral=True)
            return

        settings = await self.service.load_company_by_name(guild.id, company_name)
        if not settings:
            await interaction.response.send_message("不存在的企業名稱", ephemeral=True)
            return

        if panel_channel:
            settings = await self.service.save_company(
                guild.id, company_name, panel_channel_id=panel_channel.id
            )
        elif not settings.panel_channel_id:
            settings = await self.service.save_company(
                guild.id, company_name, panel_channel_id=interaction.channel.id
            )

        if not settings.panel_channel_id:
            await interaction.response.send_message("Panel channel is not set.", ephemeral=True)
            return

        panel_view = ResumePanelView(self.bot, self.dao, settings)
        message = await self.panel_service.ensure_panel_message(settings, panel_view)
        try:
            message_id = message.id if message else settings.panel_message_id
            if message_id:
                self.bot.add_view(panel_view, message_id=message_id)
        except Exception:
            pass

        await interaction.response.send_message("履歷面板已佈署/刷新", ephemeral=True)

    @app_commands.command(name="resume_companies", description="列出所有履歷公司履歷設定")
    @app_commands.checks.has_permissions(administrator=True)
    async def resume_companies(self, interaction: discord.Interaction):
        guild = interaction.guild
        if not guild:
            await interaction.response.send_message("此指令必須在指定頻道使用", ephemeral=True)
            return

        companies = await self.service.list_companies(guild.id)
        if not companies:
            await interaction.response.send_message("不存在的設定", ephemeral=True)
            return

        embed = discord.Embed(title="Resume Companies", color=0x3498DB)
        for settings in companies[:20]:
            panel = f"<#{settings.panel_channel_id}>" if settings.panel_channel_id else "Not set"
            review = f"<#{settings.review_channel_id}>" if settings.review_channel_id else "Not set"
            roles = (
                ", ".join(f"<@&{role_id}>" for role_id in settings.review_role_ids)
                if settings.review_role_ids
                else "Not set"
            )
            approved_roles = (
                ", ".join(f"<@&{role_id}>" for role_id in settings.approved_role_ids)
                if settings.approved_role_ids
                else "Not set"
            )
            embed.add_field(
                name=settings.company_name,
                value=f"Panel: {panel}\nReview: {review}\nReviewer roles: {roles}\nApproved roles: {approved_roles}\nEnabled: {'Yes' if settings.is_enabled else 'No'}",
                inline=False,
            )

        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="company_roles", description="公司身分組管理面板")
    async def company_roles(self, interaction: discord.Interaction):
        guild = interaction.guild
        if not guild:
            await interaction.response.send_message("此功能只能在伺服器中使用。", ephemeral=True)
            return

        companies = await self.service.list_companies(guild.id)
        manageable = [
            company
            for company in companies
            if company.is_enabled and self._can_manage_company(interaction.user, company)
        ]

        if not manageable:
            await interaction.response.send_message(
                "你沒有可管理的公司身分組權限。", ephemeral=True
            )
            return

        if len(manageable) == 1:
            settings = manageable[0]
            if not settings.approved_role_ids:
                await interaction.response.send_message(
                    "此公司尚未設定可管理的身分組，請通知管理員設定。", ephemeral=True
                )
                return
            embed = build_company_role_panel_embed(guild, settings)
            view = CompanyRolePanelView(self.bot, settings, interaction.user.id)
        else:
            embed = build_company_role_select_embed(manageable)
            view = CompanyRoleSelectView(self.bot, manageable, interaction.user.id)

        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    @staticmethod
    def _can_manage_company(
        member: discord.Member, settings
    ) -> bool:
        if member.guild_permissions.administrator or member.guild_permissions.manage_roles:
            return True
        role_ids = settings.review_role_ids or []
        if not role_ids:
            return False
        member_role_ids = {role.id for role in member.roles}
        return bool(member_role_ids & set(role_ids))


async def setup(bot: commands.Bot):
    await bot.add_cog(ResumeCore(bot))
