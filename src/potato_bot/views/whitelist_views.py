"""
Whitelist views: panel, modal, review buttons
"""

from __future__ import annotations

import json
from typing import Any, Dict, Optional

import discord
from discord.ext import commands

from potato_bot.db.whitelist_dao import WhitelistDAO
from potato_bot.services.whitelist_service import AnnounceService, RoleService, WhitelistSettings
from potato_shared.logger import logger


class ApplyModal(discord.ui.Modal):
    """入境申請表單"""

    def __init__(
        self,
        bot: commands.Bot,
        dao: WhitelistDAO,
        settings: WhitelistSettings,
        *,
        title: str = "📝 入境申請表",
        prefill: Optional[Dict[str, Any]] = None,
        app_id: Optional[int] = None,
    ):
        super().__init__(title=title, timeout=300)
        self.bot = bot
        self.dao = dao
        self.settings = settings
        self.prefill = prefill or {}
        self.existing_app_id = app_id

        self.character_name = discord.ui.TextInput(
            label="角色名",
            max_length=64,
            required=True,
            default=str(self.prefill.get("character_name", ""))[:64],
        )
        self.age = discord.ui.TextInput(
            label="年齡",
            max_length=10,
            required=True,
            default=str(self.prefill.get("age", ""))[:10],
        )
        self.background = discord.ui.TextInput(
            label="角色背景(1000字內)",
            style=discord.TextStyle.paragraph,
            max_length=1000,
            required=True,
            default=str(self.prefill.get("background", ""))[:1000],
        )
        self.roleplay_examples = discord.ui.TextInput(
            label="請舉例：什麼是超人扮演與情緒帶入(兩者均要回答)",
            style=discord.TextStyle.paragraph,
            max_length=500,
            required=True,
            default=str(self.prefill.get("roleplay_examples", ""))[:500],
        )
        self.rules = discord.ui.TextInput(
            label="是否同意 DC 社群規章 (是/否)",
            max_length=10,
            required=True,
            default=str(self.prefill.get("rules", ""))[:10],
        )

        for item in [
            self.character_name,
            self.age,
            self.background,
            self.roleplay_examples,
            self.rules,
        ]:
            self.add_item(item)

    async def on_submit(self, interaction: discord.Interaction):
        guild = interaction.guild
        if not guild:
            await interaction.response.send_message("❌ 此功能僅能在伺服器中使用", ephemeral=True)
            return

        review_channel = (
            guild.get_channel(self.settings.review_channel_id)
            if self.settings.review_channel_id
            else None
        )
        if not review_channel:
            await interaction.response.send_message("❌ 尚未設定審核頻道，請通知管理員", ephemeral=True)
            return

        # 檢查 pending（補件可繼續）
        if await self.dao.has_pending(guild.id, interaction.user.id):
            await interaction.response.send_message("⚠️ 你已有待審核申請，請等待結果", ephemeral=True)
            return

        answers: Dict[str, Any] = {
            "character_name": str(self.character_name),
            "age": str(self.age),
            "background": str(self.background),
            "roleplay_examples": str(self.roleplay_examples),
            "rules": str(self.rules),
        }

        # 建立或更新申請
        app_id = self.existing_app_id
        if app_id:
            await self.dao.update_application(app_id, str(interaction.user), answers)
        else:
            app_id = await self.dao.create_application(
                guild_id=guild.id,
                user_id=interaction.user.id,
                username=str(interaction.user),
                answers=answers,
            )

        # 發送審核卡
        view = ReviewView(
            self.bot,
            self.dao,
            app_id=app_id,
            applicant_id=interaction.user.id,
            settings=self.settings,
        )
        embed = build_review_embed(app_id, interaction.user, answers)
        try:
            mention = f"<@&{self.settings.role_staff_id}>" if self.settings.role_staff_id else None
            existing_message_id = None
            if self.existing_app_id:
                existing_app = await self.dao.get_application(self.existing_app_id)
                existing_message_id = existing_app.get("review_message_id") if existing_app else None

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
            # 註冊 persistent view
            try:
                self.bot.add_view(view, message_id=message.id)
            except Exception:
                pass
        except Exception as send_error:
            logger.error(f"❌ 發送審核卡失敗: {send_error}")
            await interaction.response.send_message("❌ 發送審核卡失敗，請通知管理員檢查權限", ephemeral=True)
            return

        await interaction.response.send_message(
            f"✅ 已提交申請編號 #{app_id}，請等待審核結果", ephemeral=True
        )


class PanelView(discord.ui.View):
    """入境申請面板 Persistent View"""

    def __init__(self, bot: commands.Bot, dao: WhitelistDAO, settings: WhitelistSettings):
        super().__init__(timeout=None)
        self.bot = bot
        self.dao = dao
        self.settings = settings

    @discord.ui.button(
        label="📝 申請入境",
        style=discord.ButtonStyle.primary,
        custom_id="whitelist:apply",
    )
    async def apply_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """開啟申請表單"""
        latest = await self.dao.get_latest_application(
            interaction.guild.id, interaction.user.id, statuses=["NEED_MORE"]
        )
        prefill = {}
        title = "📝 入境申請表"
        app_id = None
        if latest:
            title = "📝 入境申請表（補件）"
            app_id = latest.get("id")
            answers_json = latest.get("answers_json")
            if isinstance(answers_json, str):
                try:
                    prefill = json.loads(answers_json)
                except json.JSONDecodeError:
                    prefill = {}
            elif isinstance(answers_json, dict):
                prefill = answers_json

        modal = ApplyModal(
            self.bot,
            self.dao,
            self.settings,
            title=title,
            prefill=prefill,
            app_id=app_id,
        )
        await interaction.response.send_modal(modal)


class ReviewView(discord.ui.View):
    """審核按鈕 Persistent View"""

    def __init__(
        self,
        bot: commands.Bot,
        dao: WhitelistDAO,
        app_id: int,
        applicant_id: int,
        settings: WhitelistSettings,
    ):
        super().__init__(timeout=None)
        self.bot = bot
        self.dao = dao
        self.app_id = app_id
        self.applicant_id = applicant_id
        self.settings = settings

    async def _check_staff(self, interaction: discord.Interaction) -> bool:
        """確認操作人是否具備審核權限"""
        if interaction.user.guild_permissions.manage_roles:
            return True

        if not self.settings.role_staff_id:
            await interaction.response.send_message("❌ 你沒有審核權限", ephemeral=True)
            return False

        role = interaction.guild.get_role(self.settings.role_staff_id)
        if not role or role not in interaction.user.roles:
            await interaction.response.send_message("❌ 你沒有審核權限", ephemeral=True)
            return False
        return True

    async def _mark_done(
        self,
        interaction: discord.Interaction,
        status: str,
        note: Optional[str] = None,
    ):
        await interaction.response.defer(ephemeral=True)
        app = await self.dao.get_application(self.app_id)
        if not app:
            await interaction.followup.send("❌ 找不到申請資料", ephemeral=True)
            return

        applicant_id = app.get("user_id", self.applicant_id)

        if app.get("status") not in ("PENDING", "NEED_MORE"):
            await interaction.followup.send("⚠️ 申請已處理", ephemeral=True)
            return

        # 嘗試以資料庫層級鎖定狀態，避免多人同時審核重複處理
        updated = await self.dao.set_status(self.app_id, status, interaction.user.id, note)
        if not updated:
            await interaction.followup.send("⚠️ 申請已被其他管理員處理", ephemeral=True)
            return

        # 身分組處理（僅通過）
        if status == "APPROVED":
            member = interaction.guild.get_member(applicant_id)
            if member:
                answers = app.get("answers_json")
                if isinstance(answers, str):
                    try:
                        answers = json.loads(answers)
                    except json.JSONDecodeError:
                        answers = {}
                character_name = None
                if isinstance(answers, dict):
                    character_name = answers.get("character_name")
                await RoleService(self.settings).apply_approved(
                    member, character_name=character_name
                )

        # 公告
        await AnnounceService(self.bot, self.settings).post_result(
            {**app, "id": self.app_id, "user_id": applicant_id},
            status,
            note,
        )

        # 關閉按鈕
        for item in self.children:
            item.disabled = True
        try:
            await interaction.message.edit(view=self)
        except Exception:
            pass

        await interaction.followup.send(f"✅ 已更新申請 #{self.app_id} 為 {status}", ephemeral=True)

    @discord.ui.button(
        label="✅ 通過",
        style=discord.ButtonStyle.success,
        custom_id="whitelist:approve",
    )
    async def approve(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self._check_staff(interaction):
            return
        await self._mark_done(interaction, "APPROVED")

    @discord.ui.button(
        label="❌ 拒絕",
        style=discord.ButtonStyle.danger,
        custom_id="whitelist:deny",
    )
    async def deny(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self._check_staff(interaction):
            return
        await interaction.response.send_modal(ReasonModal(self, status="DENIED"))

    @discord.ui.button(
        label="🔁 補件",
        style=discord.ButtonStyle.secondary,
        custom_id="whitelist:needmore",
    )
    async def need_more(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self._check_staff(interaction):
            return
        await interaction.response.send_modal(ReasonModal(self, status="NEED_MORE"))


class ReasonModal(discord.ui.Modal):
    """審核原因 Modal（可空白）"""

    def __init__(self, review_view: ReviewView, status: str):
        super().__init__(title="審核原因（可留空）", timeout=180)
        self.review_view = review_view
        self.status = status
        self.note = discord.ui.TextInput(
            label="備註/原因", style=discord.TextStyle.paragraph, required=False, max_length=500
        )
        self.add_item(self.note)

    async def on_submit(self, interaction: discord.Interaction):
        await self.review_view._mark_done(interaction, self.status, note=str(self.note))


def build_review_embed(app_id: int, user: discord.abc.User, answers: Dict[str, Any]) -> discord.Embed:
    """建立審核卡片 embed"""
    embed = discord.Embed(
        title=f"🧾 申請單 #{app_id}",
        description=f"申請人: {user.mention} (`{user.id}`)",
        color=0x9b59b6,
    )
    embed.add_field(name="角色名", value=answers.get("character_name", "未填"), inline=False)
    embed.add_field(name="年齡", value=answers.get("age", "未填"), inline=False)
    embed.add_field(name="角色背景", value=answers.get("background", "未填")[:1024], inline=False)
    embed.add_field(name="超人扮演/情緒帶入示例", value=answers.get("roleplay_examples", "未填")[:1024], inline=False)
    embed.add_field(name="同意規章", value=answers.get("rules", "未填"), inline=False)
    return embed
