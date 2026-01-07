"""
履歷系統視圖：面板、表單、審核操作。
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
    """履歷提交表單。"""

    def __init__(
        self,
        bot: commands.Bot,
        dao: ResumeDAO,
        settings: ResumeCompanySettings,
        *,
        title: str = "履歷申請",
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
            label="DC名稱/城內名稱",
            max_length=64,
            required=True,
            default=str(self.prefill.get("full_name", ""))[:64],
        )
        self.contact = discord.ui.TextInput(
            label="年齡",
            max_length=128,
            required=True,
            default=str(self.prefill.get("contact", ""))[:128],
        )
        self.experience = discord.ui.TextInput(
            label="經歷摘要&為何想加入（最多1000字）",
            style=discord.TextStyle.paragraph,
            max_length=1000,
            required=True,
            default=str(self.prefill.get("experience", ""))[:1000],
        )
        self.skills = discord.ui.TextInput(
            label="上線時段",
            style=discord.TextStyle.paragraph,
            max_length=50,
            required=True,
            default=str(self.prefill.get("skills", ""))[:1000],
        )
        self.portfolio = discord.ui.TextInput(
            label="是否能配合公司規章制度？若不能請說明原因（最多1000字）",
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
                "此功能只能在伺服器中使用。", ephemeral=True
            )
            return

        if not self.settings.is_enabled:
            await interaction.response.send_message("此公司目前已停用。", ephemeral=True)
            return

        review_channel = (
            guild.get_channel(self.settings.review_channel_id)
            if self.settings.review_channel_id
            else None
        )
        if not review_channel:
            await interaction.response.send_message(
                "尚未設定審核頻道，請聯絡管理員。",
                ephemeral=True,
            )
            return

        if await self.dao.has_pending(guild.id, self.settings.company_id, interaction.user.id):
            await interaction.response.send_message(
                "你已經有此公司的待審履歷，請等待審核。",
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
            logger.error(f"送出履歷審核卡失敗: {send_error}")
            await interaction.response.send_message(
                "送出審核卡片失敗，請聯絡管理員。",
                ephemeral=True,
            )
            return

        await interaction.response.send_message(
            f"已提交履歷申請 #{app_id}，請等待審核。", ephemeral=True
        )


class ResumePanelView(discord.ui.View):
    """履歷面板常駐 View。"""

    def __init__(self, bot: commands.Bot, dao: ResumeDAO, settings: ResumeCompanySettings):
        super().__init__(timeout=None)
        self.bot = bot
        self.dao = dao
        self.settings = settings

        label = f"填寫{settings.company_name}履歷申請".strip()
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
                "此功能只能在伺服器中使用。", ephemeral=True
            )
            return
        latest = await self.dao.get_latest_application(
            interaction.guild.id,
            self.settings.company_id,
            interaction.user.id,
            statuses=["NEED_MORE"],
        )
        prefill = {}
        title = "履歷申請"
        app_id = None
        if latest:
            title = "履歷申請（補件）"
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
    """履歷審核常駐 View。"""

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
                "此公司尚未設定審核身分組。",
                ephemeral=True,
            )
            return False
        if any(role.id in review_role_ids for role in interaction.user.roles):
            return True
        await interaction.response.send_message("你沒有審核權限。", ephemeral=True)
        return False

    async def _notify_applicant(
        self,
        guild: discord.Guild,
        user_id: int,
        status: str,
        note: Optional[str] = None,
    ) -> None:
        status_text = {
            "APPROVED": "通過",
            "DENIED": "拒絕",
            "NEED_MORE": "需補件",
        }.get(status, status)
        embed = discord.Embed(
            title="履歷審核結果",
            description=f"公司：{self.settings.company_name}\n狀態：{status_text}",
            color={
                "APPROVED": 0x2ECC71,
                "DENIED": 0xE74C3C,
                "NEED_MORE": 0xF1C40F,
            }.get(status, 0x3498DB),
        )
        if note:
            embed.add_field(name="備註", value=note[:1024], inline=False)
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
            await interaction.followup.send("找不到申請資料。", ephemeral=True)
            return

        applicant_id = app.get("user_id", self.applicant_id)
        if app.get("status") not in ("PENDING", "NEED_MORE"):
            await interaction.followup.send("申請已處理。", ephemeral=True)
            return

        updated = await self.dao.set_status(self.app_id, status, interaction.user.id, note)
        if not updated:
            await interaction.followup.send("申請已被其他審核員處理。", ephemeral=True)
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
        status_display = {
            "APPROVED": "通過",
            "DENIED": "拒絕",
            "NEED_MORE": "需補件",
        }.get(status, status)
        await interaction.followup.send(
            f"已將申請 #{self.app_id} 更新為 {status_display}。", ephemeral=True
        )

    @discord.ui.button(label="通過", style=discord.ButtonStyle.success, custom_id="resume:approve")
    async def approve(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self._check_reviewer(interaction):
            return
        await self._mark_done(interaction, "APPROVED")

    @discord.ui.button(label="拒絕", style=discord.ButtonStyle.danger, custom_id="resume:deny")
    async def deny(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self._check_reviewer(interaction):
            return
        await interaction.response.send_modal(ResumeReasonModal(self, status="DENIED"))

    @discord.ui.button(label="需補件", style=discord.ButtonStyle.secondary, custom_id="resume:needmore")
    async def need_more(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self._check_reviewer(interaction):
            return
        await interaction.response.send_modal(ResumeReasonModal(self, status="NEED_MORE"))


class ResumeReasonModal(discord.ui.Modal):
    """審核備註表單（選填）。"""

    def __init__(self, review_view: ResumeReviewView, status: str):
        super().__init__(title="審核備註（選填）", timeout=180)
        self.review_view = review_view
        self.status = status
        self.note = discord.ui.TextInput(
            label="備註", style=discord.TextStyle.paragraph, required=False, max_length=500
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
        "PENDING": "待審核",
        "APPROVED": "通過",
        "DENIED": "拒絕",
        "NEED_MORE": "需補件",
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
        title=f"履歷申請 #{app_id}",
        description=f"公司：{company_name}\n申請人：{mention} (`{display_id}`)",
        color=color_map.get(status_code, 0x3498DB),
    )
    embed.add_field(name="姓名", value=answers.get("full_name", "未填"), inline=False)
    embed.add_field(name="聯絡方式", value=answers.get("contact", "未填"), inline=False)
    embed.add_field(
        name="經歷摘要", value=answers.get("experience", "未填")[:1024], inline=False
    )
    embed.add_field(name="技能 / 工具", value=answers.get("skills", "未填")[:1024], inline=False)
    embed.add_field(
        name="作品集 / 連結", value=answers.get("portfolio", "未填")[:1024], inline=False
    )
    embed.add_field(name="狀態", value=status_text, inline=False)
    if reviewer:
        embed.add_field(name="審核員", value=reviewer.mention, inline=False)
    if note:
        embed.add_field(name="備註", value=note[:1024], inline=False)
    return embed
