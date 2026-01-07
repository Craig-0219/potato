"""
Resume views: panel, modal, review actions.
"""

from __future__ import annotations

import json
from typing import Any, Dict, Optional

import discord
from discord.ext import commands

from potato_bot.db.resume_dao import ResumeDAO
from potato_bot.services.resume_service import ResumeCompanySettings
from potato_shared.logger import logger


class ResumeApplyModal(discord.ui.Modal):
    """Resume submission form."""

    def __init__(
        self,
        bot: commands.Bot,
        dao: ResumeDAO,
        settings: ResumeCompanySettings,
        *,
        title: str = "Resume Submission",
        prefill: Optional[Dict[str, Any]] = None,
        app_id: Optional[int] = None,
    ):
        super().__init__(title=title, timeout=300)
        self.bot = bot
        self.dao = dao
        self.settings = settings
        self.prefill = prefill or {}
        self.existing_app_id = app_id

        self.full_name = discord.ui.TextInput(
            label="Full name",
            max_length=64,
            required=True,
            default=str(self.prefill.get("full_name", ""))[:64],
        )
        self.contact = discord.ui.TextInput(
            label="Contact (email/phone)",
            max_length=128,
            required=True,
            default=str(self.prefill.get("contact", ""))[:128],
        )
        self.experience = discord.ui.TextInput(
            label="Experience summary (1000 chars)",
            style=discord.TextStyle.paragraph,
            max_length=1000,
            required=True,
            default=str(self.prefill.get("experience", ""))[:1000],
        )
        self.skills = discord.ui.TextInput(
            label="Skills / tools",
            style=discord.TextStyle.paragraph,
            max_length=1000,
            required=True,
            default=str(self.prefill.get("skills", ""))[:1000],
        )
        self.portfolio = discord.ui.TextInput(
            label="Portfolio / links (optional)",
            style=discord.TextStyle.paragraph,
            max_length=1000,
            required=False,
            default=str(self.prefill.get("portfolio", ""))[:1000],
        )

        for item in [
            self.full_name,
            self.contact,
            self.experience,
            self.skills,
            self.portfolio,
        ]:
            self.add_item(item)

    async def on_submit(self, interaction: discord.Interaction):
        guild = interaction.guild
        if not guild:
            await interaction.response.send_message(
                "This feature can only be used in a guild.", ephemeral=True
            )
            return

        if not self.settings.is_enabled:
            await interaction.response.send_message("This company is disabled.", ephemeral=True)
            return

        review_channel = (
            guild.get_channel(self.settings.review_channel_id)
            if self.settings.review_channel_id
            else None
        )
        if not review_channel:
            await interaction.response.send_message(
                "Review channel is not configured. Please contact an admin.",
                ephemeral=True,
            )
            return

        if await self.dao.has_pending(guild.id, self.settings.company_id, interaction.user.id):
            await interaction.response.send_message(
                "You already have a pending application for this company.",
                ephemeral=True,
            )
            return

        answers: Dict[str, Any] = {
            "full_name": str(self.full_name),
            "contact": str(self.contact),
            "experience": str(self.experience),
            "skills": str(self.skills),
            "portfolio": str(self.portfolio),
        }

        app_id = self.existing_app_id
        if app_id:
            await self.dao.update_application(app_id, str(interaction.user), answers)
        else:
            app_id = await self.dao.create_application(
                guild_id=guild.id,
                company_id=self.settings.company_id,
                user_id=interaction.user.id,
                username=str(interaction.user),
                answers=answers,
            )

        view = ResumeReviewView(
            self.bot,
            self.dao,
            app_id=app_id,
            applicant_id=interaction.user.id,
            settings=self.settings,
        )
        embed = build_review_embed(
            app_id,
            self.settings.company_name,
            interaction.user.id,
            interaction.user,
            answers,
            status="PENDING",
        )

        mention = None
        if self.settings.review_role_ids:
            mention = " ".join(f"<@&{role_id}>" for role_id in self.settings.review_role_ids)

        existing_message_id = None
        if self.existing_app_id:
            existing_app = await self.dao.get_application(self.existing_app_id)
            existing_message_id = existing_app.get("review_message_id") if existing_app else None

        try:
            message = None
            if existing_message_id:
                try:
                    message = await review_channel.fetch_message(existing_message_id)
                except Exception:
                    message = None

            if message:
                await message.edit(content=mention, embed=embed, view=view)
            else:
                message = await review_channel.send(content=mention, embed=embed, view=view)

            await self.dao.set_review_message_id(app_id, message.id)
            try:
                self.bot.add_view(view, message_id=message.id)
            except Exception:
                pass
        except Exception as send_error:
            logger.error(f"Failed to send resume review card: {send_error}")
            await interaction.response.send_message(
                "Failed to send review card. Please contact an admin.",
                ephemeral=True,
            )
            return

        await interaction.response.send_message(
            f"Application #{app_id} submitted. Please wait for review.", ephemeral=True
        )


class ResumePanelView(discord.ui.View):
    """Resume panel persistent view."""

    def __init__(self, bot: commands.Bot, dao: ResumeDAO, settings: ResumeCompanySettings):
        super().__init__(timeout=None)
        self.bot = bot
        self.dao = dao
        self.settings = settings

        label = f"Apply - {settings.company_name}".strip()
        if len(label) > 80:
            label = label[:80]
        button = discord.ui.Button(
            label=label,
            style=discord.ButtonStyle.primary,
            custom_id=f"resume:apply:{settings.company_id}",
        )
        button.callback = self.apply_button
        self.add_item(button)

    async def apply_button(self, interaction: discord.Interaction):
        if not interaction.guild:
            await interaction.response.send_message(
                "This feature can only be used in a guild.", ephemeral=True
            )
            return
        latest = await self.dao.get_latest_application(
            interaction.guild.id,
            self.settings.company_id,
            interaction.user.id,
            statuses=["NEED_MORE"],
        )
        prefill = {}
        title = "Resume Submission"
        app_id = None
        if latest:
            title = "Resume Submission (Update)"
            app_id = latest.get("id")
            answers_json = latest.get("answers_json")
            if isinstance(answers_json, str):
                try:
                    prefill = json.loads(answers_json)
                except json.JSONDecodeError:
                    prefill = {}
            elif isinstance(answers_json, dict):
                prefill = answers_json

        modal = ResumeApplyModal(
            self.bot,
            self.dao,
            self.settings,
            title=title,
            prefill=prefill,
            app_id=app_id,
        )
        await interaction.response.send_modal(modal)


class ResumeReviewView(discord.ui.View):
    """Resume review persistent view."""

    def __init__(
        self,
        bot: commands.Bot,
        dao: ResumeDAO,
        app_id: int,
        applicant_id: int,
        settings: ResumeCompanySettings,
    ):
        super().__init__(timeout=None)
        self.bot = bot
        self.dao = dao
        self.app_id = app_id
        self.applicant_id = applicant_id
        self.settings = settings

    async def _check_reviewer(self, interaction: discord.Interaction) -> bool:
        if (
            interaction.user.guild_permissions.administrator
            or interaction.user.guild_permissions.manage_roles
        ):
            return True
        review_role_ids = self.settings.review_role_ids or []
        if not review_role_ids:
            await interaction.response.send_message(
                "Reviewer roles are not configured for this company.",
                ephemeral=True,
            )
            return False
        if any(role.id in review_role_ids for role in interaction.user.roles):
            return True
        await interaction.response.send_message("You do not have review permission.", ephemeral=True)
        return False

    async def _notify_applicant(
        self,
        guild: discord.Guild,
        user_id: int,
        status: str,
        note: Optional[str] = None,
    ) -> None:
        status_text = {
            "APPROVED": "APPROVED",
            "DENIED": "DENIED",
            "NEED_MORE": "NEED MORE INFO",
        }.get(status, status)
        embed = discord.Embed(
            title="Resume Review Result",
            description=f"Company: {self.settings.company_name}\nStatus: {status_text}",
            color={
                "APPROVED": 0x2ECC71,
                "DENIED": 0xE74C3C,
                "NEED_MORE": 0xF1C40F,
            }.get(status, 0x3498DB),
        )
        if note:
            embed.add_field(name="Note", value=note[:1024], inline=False)
        try:
            member = guild.get_member(user_id) or await self.bot.fetch_user(user_id)
            if member:
                await member.send(embed=embed)
        except Exception:
            pass

    async def _mark_done(self, interaction: discord.Interaction, status: str, note: str | None = None):
        await interaction.response.defer(ephemeral=True)
        app = await self.dao.get_application(self.app_id)
        if not app:
            await interaction.followup.send("Application not found.", ephemeral=True)
            return

        applicant_id = app.get("user_id", self.applicant_id)
        if app.get("status") not in ("PENDING", "NEED_MORE"):
            await interaction.followup.send("Application already processed.", ephemeral=True)
            return

        updated = await self.dao.set_status(self.app_id, status, interaction.user.id, note)
        if not updated:
            await interaction.followup.send("Application already handled by another reviewer.", ephemeral=True)
            return

        answers = app.get("answers_json")
        if isinstance(answers, str):
            try:
                answers = json.loads(answers)
            except json.JSONDecodeError:
                answers = {}

        applicant = interaction.guild.get_member(applicant_id)
        if applicant is None:
            try:
                applicant = await self.bot.fetch_user(applicant_id)
            except Exception:
                applicant = None

        embed = build_review_embed(
            self.app_id,
            self.settings.company_name,
            applicant_id,
            applicant,
            answers if isinstance(answers, dict) else {},
            status=status,
            note=note,
            reviewer=interaction.user,
        )

        for item in self.children:
            item.disabled = True
        try:
            await interaction.message.edit(embed=embed, view=self)
        except Exception:
            pass

        await self._notify_applicant(interaction.guild, applicant_id, status, note)
        await interaction.followup.send(f"Updated application #{self.app_id} to {status}.", ephemeral=True)

    @discord.ui.button(label="Approve", style=discord.ButtonStyle.success, custom_id="resume:approve")
    async def approve(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self._check_reviewer(interaction):
            return
        await self._mark_done(interaction, "APPROVED")

    @discord.ui.button(label="Deny", style=discord.ButtonStyle.danger, custom_id="resume:deny")
    async def deny(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self._check_reviewer(interaction):
            return
        await interaction.response.send_modal(ResumeReasonModal(self, status="DENIED"))

    @discord.ui.button(label="Need More", style=discord.ButtonStyle.secondary, custom_id="resume:needmore")
    async def need_more(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self._check_reviewer(interaction):
            return
        await interaction.response.send_modal(ResumeReasonModal(self, status="NEED_MORE"))


class ResumeReasonModal(discord.ui.Modal):
    """Review reason modal (optional)."""

    def __init__(self, review_view: ResumeReviewView, status: str):
        super().__init__(title="Review note (optional)", timeout=180)
        self.review_view = review_view
        self.status = status
        self.note = discord.ui.TextInput(
            label="Note", style=discord.TextStyle.paragraph, required=False, max_length=500
        )
        self.add_item(self.note)

    async def on_submit(self, interaction: discord.Interaction):
        await self.review_view._mark_done(interaction, self.status, note=str(self.note))


def build_review_embed(
    app_id: int,
    company_name: str,
    applicant_id: int,
    applicant: Optional[discord.abc.User],
    answers: Dict[str, Any],
    *,
    status: str | None = None,
    note: str | None = None,
    reviewer: Optional[discord.abc.User] = None,
) -> discord.Embed:
    status_code = status or "PENDING"
    status_text = {
        "PENDING": "PENDING",
        "APPROVED": "APPROVED",
        "DENIED": "DENIED",
        "NEED_MORE": "NEED MORE INFO",
    }.get(status_code, status_code)
    color_map = {
        "PENDING": 0x3498DB,
        "APPROVED": 0x2ECC71,
        "DENIED": 0xE74C3C,
        "NEED_MORE": 0xF1C40F,
    }
    mention = applicant.mention if applicant else f"<@{applicant_id}>"
    display_id = applicant.id if applicant else applicant_id
    embed = discord.Embed(
        title=f"Resume Application #{app_id}",
        description=f"Company: {company_name}\nApplicant: {mention} (`{display_id}`)",
        color=color_map.get(status_code, 0x3498DB),
    )
    embed.add_field(name="Full name", value=answers.get("full_name", "N/A"), inline=False)
    embed.add_field(name="Contact", value=answers.get("contact", "N/A"), inline=False)
    embed.add_field(
        name="Experience summary", value=answers.get("experience", "N/A")[:1024], inline=False
    )
    embed.add_field(name="Skills / tools", value=answers.get("skills", "N/A")[:1024], inline=False)
    embed.add_field(
        name="Portfolio / links", value=answers.get("portfolio", "N/A")[:1024], inline=False
    )
    embed.add_field(name="Status", value=status_text, inline=False)
    if reviewer:
        embed.add_field(name="Reviewer", value=reviewer.mention, inline=False)
    if note:
        embed.add_field(name="Note", value=note[:1024], inline=False)
    return embed
