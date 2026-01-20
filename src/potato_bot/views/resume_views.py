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
from potato_bot.utils.embed_builder import EmbedBuilder
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
        self.age = discord.ui.TextInput(
            label="年齡",
            max_length=128,
            required=True,
            default=str(self.prefill.get("age", self.prefill.get("contact", "")))[:128],
        )
        self.experience = discord.ui.TextInput(
            label="經歷摘要&為何想加入（最多1000字）",
            style=discord.TextStyle.paragraph,
            max_length=1000,
            required=True,
            default=str(self.prefill.get("experience", ""))[:1000],
        )
        self.online_time = discord.ui.TextInput(
            label="上線時段",
            style=discord.TextStyle.paragraph,
            max_length=50,
            required=True,
            default=str(self.prefill.get("online_time", self.prefill.get("skills", "")))[:50],
        )
        self.can_follow_rules = discord.ui.TextInput(
            label="是否能配合公司規章制度？若不能請說明原因（最多1000字）",
            style=discord.TextStyle.paragraph,
            max_length=1000,
            required=False,
            default=str(
                self.prefill.get("can_follow_rules", self.prefill.get("portfolio", ""))
            )[:1000],
        )

        for item in [
            self.full_name,
            self.age,
            self.experience,
            self.online_time,
            self.can_follow_rules,
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
            "age": str(self.age),
            "experience": str(self.experience),
            "online_time": str(self.online_time),
            "can_follow_rules": str(self.can_follow_rules),
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

    async def _apply_approved_roles(self, guild: discord.Guild, user_id: int) -> None:
        role_ids = self.settings.approved_role_ids or []
        if not role_ids:
            return

        member = guild.get_member(user_id)
        if not member:
            return

        existing_role_ids = {role.id for role in member.roles}
        roles_to_add = []
        for role_id in role_ids:
            if role_id in existing_role_ids:
                continue
            role = guild.get_role(role_id)
            if role:
                roles_to_add.append(role)

        if not roles_to_add:
            return

        try:
            await member.add_roles(*roles_to_add, reason="Resume approved")
        except Exception as e:
            logger.error(f"履歷通過自動身分組失敗: {e}")

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
        if status == "APPROVED":
            await self._apply_approved_roles(interaction.guild, applicant_id)

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
    age_value = answers.get("age") or answers.get("contact") or "未填"
    online_time_value = answers.get("online_time") or answers.get("skills") or "未填"
    can_follow_rules_value = (
        answers.get("can_follow_rules") or answers.get("portfolio") or "未填"
    )
    embed.add_field(name="DC名稱/城內名稱", value=answers.get("full_name", "未填"), inline=False)
    embed.add_field(name="年齡", value=str(age_value), inline=False)
    embed.add_field(
        name="經歷摘要/為何想加入", value=answers.get("experience", "未填")[:1024], inline=False
    )
    embed.add_field(name="上線時段", value=str(online_time_value)[:1024], inline=False)
    embed.add_field(
        name="是否能配合公司規章制度？",
        value=str(can_follow_rules_value)[:1024],
        inline=False,
    )
    embed.add_field(name="狀態", value=status_text, inline=False)
    if reviewer:
        embed.add_field(name="審核員", value=reviewer.mention, inline=False)
    if note:
        embed.add_field(name="備註", value=note[:1024], inline=False)
    return embed


def build_company_role_panel_embed(
    guild: discord.Guild, settings: ResumeCompanySettings
) -> discord.Embed:
    manageable_role_ids = settings.get_manageable_role_ids()
    manageable_roles = [guild.get_role(role_id) for role_id in manageable_role_ids]
    manageable_mentions = [role.mention for role in manageable_roles if role]
    manageable_text = "、".join(manageable_mentions) if manageable_mentions else "未設定"

    approved_role_ids = settings.approved_role_ids or []
    approved_roles = [guild.get_role(role_id) for role_id in approved_role_ids]
    approved_mentions = [role.mention for role in approved_roles if role]
    approved_text = "、".join(approved_mentions) if approved_mentions else "未設定"

    manager_role_ids = settings.review_role_ids or []
    manager_roles = [guild.get_role(role_id) for role_id in manager_role_ids]
    manager_mentions = [role.mention for role in manager_roles if role]
    manager_text = "、".join(manager_mentions) if manager_mentions else "未設定"

    embed = EmbedBuilder.create_info_embed(
        f"🏷️ {settings.company_name} 身分組管理",
        "選擇成員與身分組後，使用下方按鈕進行新增或移除。\n"
        "僅可操作「可管理身分組」，通過身分組僅供參考。",
    )
    embed.add_field(name="可管理身分組", value=manageable_text, inline=False)
    embed.add_field(name="通過身分組", value=approved_text, inline=False)
    embed.add_field(name="可操作身分組的高層", value=manager_text, inline=False)
    return embed


def build_company_role_select_embed(companies: list[ResumeCompanySettings]) -> discord.Embed:
    embed = EmbedBuilder.create_info_embed(
        "🏷️ 公司身分組管理",
        "請選擇要管理的公司。",
    )
    lines = [f"• {company.company_name}" for company in companies[:25]]
    embed.add_field(
        name="可管理公司",
        value="\n".join(lines) if lines else "未找到可管理的公司",
        inline=False,
    )
    return embed


class CompanyRoleSelectView(discord.ui.View):
    """公司選擇面板。"""

    def __init__(
        self,
        bot: commands.Bot,
        companies: list[ResumeCompanySettings],
        user_id: int,
    ):
        super().__init__(timeout=180)
        self.bot = bot
        self.companies = companies
        self.user_id = user_id
        self.add_item(CompanyRoleCompanySelect(self))

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("❌ 只有開啟面板者可以操作。", ephemeral=True)
            return False
        return True


class CompanyRoleCompanySelect(discord.ui.Select):
    """公司選擇下拉選單。"""

    def __init__(self, parent_view: CompanyRoleSelectView):
        options = []
        for company in parent_view.companies[:25]:
            role_count = len(company.get_manageable_role_ids())
            description = (
                f"可管理 {role_count} 個身分組" if role_count else "尚未設定可管理身分組"
            )
            options.append(
                discord.SelectOption(
                    label=company.company_name[:100],
                    value=str(company.company_id),
                    description=description[:100],
                )
            )

        super().__init__(
            placeholder="選擇公司",
            options=options,
            min_values=1,
            max_values=1,
            custom_id="company_role:company",
        )
        self.parent_view = parent_view

    async def callback(self, interaction: discord.Interaction):
        company_id = int(self.values[0])
        settings = next(
            (company for company in self.parent_view.companies if company.company_id == company_id),
            None,
        )
        if not settings:
            await interaction.response.send_message("找不到公司設定。", ephemeral=True)
            return

        if not settings.get_manageable_role_ids():
            await interaction.response.send_message(
                "此公司尚未設定可管理的身分組，請通知管理員設定。", ephemeral=True
            )
            return

        embed = build_company_role_panel_embed(interaction.guild, settings)
        view = CompanyRolePanelView(
            self.parent_view.bot,
            settings,
            self.parent_view.user_id,
        )
        await interaction.response.edit_message(embed=embed, view=view)


class CompanyRolePanelView(discord.ui.View):
    """公司身分組管理面板。"""

    def __init__(
        self,
        bot: commands.Bot,
        settings: ResumeCompanySettings,
        user_id: int,
    ):
        super().__init__(timeout=300)
        self.bot = bot
        self.settings = settings
        self.user_id = user_id

        self.member_select = CompanyMemberSelect()
        self.role_select = CompanyRoleSelect()
        self.add_item(self.member_select)
        self.add_item(self.role_select)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("❌ 只有開啟面板者可以操作。", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="➕ 新增身分組", style=discord.ButtonStyle.success, row=2)
    async def add_roles(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._apply_roles(interaction, action="add")

    @discord.ui.button(label="➖ 移除身分組", style=discord.ButtonStyle.danger, row=2)
    async def remove_roles(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._apply_roles(interaction, action="remove")

    @discord.ui.button(label="❌ 關閉面板", style=discord.ButtonStyle.secondary, row=2)
    async def close_panel(self, interaction: discord.Interaction, button: discord.ui.Button):
        for item in self.children:
            item.disabled = True
        await interaction.response.edit_message(view=self)

    async def _apply_roles(self, interaction: discord.Interaction, action: str) -> None:
        await interaction.response.defer(ephemeral=True)

        guild = interaction.guild
        if not guild:
            await interaction.followup.send("此功能只能在伺服器中使用。", ephemeral=True)
            return

        allowed_role_ids = set(self.settings.get_manageable_role_ids())
        if not allowed_role_ids:
            await interaction.followup.send(
                "此公司尚未設定可管理的身分組，請通知管理員設定。", ephemeral=True
            )
            return

        if not self.member_select.values:
            await interaction.followup.send("請先選擇成員。", ephemeral=True)
            return

        if not self.role_select.values:
            await interaction.followup.send("請先選擇身分組。", ephemeral=True)
            return

        selected_user = self.member_select.values[0]
        member = (
            selected_user
            if isinstance(selected_user, discord.Member)
            else guild.get_member(selected_user.id)
        )
        if not member:
            try:
                member = await guild.fetch_member(selected_user.id)
            except Exception:
                member = None
        if not member:
            await interaction.followup.send("找不到成員，請重新選擇。", ephemeral=True)
            return

        roles = list(self.role_select.values)
        invalid_roles = [role for role in roles if role.id not in allowed_role_ids]
        if invalid_roles:
            allowed_roles = [
                guild.get_role(role_id) for role_id in allowed_role_ids if guild.get_role(role_id)
            ]
            allowed_text = (
                "、".join(role.mention for role in allowed_roles) if allowed_roles else "未設定"
            )
            await interaction.followup.send(
                f"選擇的身分組不在可管理清單內。\n可管理身分組：{allowed_text}",
                ephemeral=True,
            )
            return

        bot_member = guild.get_member(self.bot.user.id) if self.bot.user else None
        if not bot_member or not bot_member.guild_permissions.manage_roles:
            await interaction.followup.send("機器人缺少管理身分組權限。", ephemeral=True)
            return

        blocked = []
        for role in roles:
            if role.is_default() or role.managed:
                blocked.append(f"{role.mention} (系統身分組)")
                continue
            if role >= bot_member.top_role:
                blocked.append(f"{role.mention} (機器人權限不足)")
                continue
            if not (
                interaction.user.guild_permissions.manage_roles
                or interaction.user.guild_permissions.administrator
            ):
                if role >= interaction.user.top_role:
                    blocked.append(f"{role.mention} (高於你的最高身分組)")

        if blocked:
            await interaction.followup.send(
                "以下身分組無法操作：\n" + "\n".join(blocked),
                ephemeral=True,
            )
            return

        existing_ids = {role.id for role in member.roles}
        if action == "add":
            roles_to_apply = [role for role in roles if role.id not in existing_ids]
        else:
            roles_to_apply = [role for role in roles if role.id in existing_ids]

        if not roles_to_apply:
            await interaction.followup.send("沒有需要變更的身分組。", ephemeral=True)
            return

        try:
            if action == "add":
                await member.add_roles(*roles_to_apply, reason="Company role panel")
                action_text = "新增"
            else:
                await member.remove_roles(*roles_to_apply, reason="Company role panel")
                action_text = "移除"
        except Exception as e:
            logger.error(f"公司身分組操作失敗: {e}")
            await interaction.followup.send("身分組變更失敗，請稍後再試。", ephemeral=True)
            return

        role_mentions = "、".join(role.mention for role in roles_to_apply)
        await interaction.followup.send(
            f"已為 {member.mention} {action_text}：{role_mentions}",
            ephemeral=True,
        )


class CompanyMemberSelect(discord.ui.UserSelect):
    """成員選擇器。"""

    def __init__(self):
        super().__init__(
            placeholder="選擇成員",
            min_values=1,
            max_values=1,
            custom_id="company_role:member",
        )


class CompanyRoleSelect(discord.ui.RoleSelect):
    """身分組選擇器。"""

    def __init__(self):
        super().__init__(
            placeholder="選擇身分組（僅允許公司可管理清單）",
            min_values=1,
            max_values=10,
            custom_id="company_role:roles",
        )
