"""
Whitelist views: panel, modal, review buttons
"""

from __future__ import annotations

import json
from typing import Any, Dict, Optional

import discord
from discord.ext import commands

from potato_bot.db.whitelist_dao import WhitelistDAO
from potato_bot.db.whitelist_interview_dao import WhitelistInterviewDAO
from potato_bot.services.whitelist_interview_service import WhitelistInterviewService
from potato_bot.services.whitelist_service import AnnounceService, RoleService, WhitelistSettings
from potato_bot.views.whitelist_interview_views import WhitelistInterviewAdminView
from potato_bot.utils.interaction_helper import SafeInteractionHandler
from potato_shared.logger import logger


async def _build_interview_reminder(
    guild: discord.Guild,
) -> tuple[str, str]:
    """
    回傳：
    - 審核卡片欄位內容（給審核員看）
    - 送出申請後提醒內容（給申請者看）
    """
    try:
        interview_settings = await WhitelistInterviewService(
            WhitelistInterviewDAO()
        ).load_settings(guild.id)
    except Exception:
        return ("狀態：未設定\n時段：未設定\n等候區：未設定", "")

    start_hour = int(interview_settings.session_start_hour) % 24
    end_hour = int(interview_settings.session_end_hour) % 24
    status_text = "已啟用" if interview_settings.is_enabled else "未啟用"
    waiting_channel_id = interview_settings.waiting_channel_id
    waiting_text = f"<#{waiting_channel_id}>" if waiting_channel_id else "未設定"
    schedule_text = (
        f"{start_hour:02d}:00 - {end_hour:02d}:00 ({interview_settings.timezone})"
    )

    reviewer_field = (
        f"狀態：{status_text}\n"
        f"時段：{schedule_text}\n"
        f"等候區：{waiting_text}"
    )
    applicant_reminder = (
        "🎙️ 面試提醒：填寫完申請表後，"
        f"請於 {schedule_text} 前往 {waiting_text} 準備面試。"
    )
    return reviewer_field, applicant_reminder


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
            label="角色名(至少有名有姓)",
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
            label="角色人設(1000字內)",
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
            await SafeInteractionHandler.safe_respond(
                interaction, content="❌ 此功能僅能在伺服器中使用", ephemeral=True
            )
            return

        await SafeInteractionHandler.safe_defer(interaction, ephemeral=True)

        review_channel = (
            guild.get_channel(self.settings.review_channel_id)
            if self.settings.review_channel_id
            else None
        )
        if not review_channel:
            await SafeInteractionHandler.safe_respond(
                interaction,
                content="❌ 尚未設定審核頻道，請通知管理員",
                ephemeral=True,
            )
            return

        # 檢查 pending（補件可繼續）
        if await self.dao.has_pending(guild.id, interaction.user.id):
            await SafeInteractionHandler.safe_respond(
                interaction,
                content="⚠️ 你已有待審核申請，請等待結果",
                ephemeral=True,
            )
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
        embed = build_review_embed(app_id, interaction.user.id, interaction.user, answers)
        interview_reviewer_field, interview_reminder = await _build_interview_reminder(guild)
        embed.add_field(
            name="🎙️ 海關語音面試資訊",
            value=interview_reviewer_field[:1024],
            inline=False,
        )
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
            await SafeInteractionHandler.safe_respond(
                interaction,
                content="❌ 發送審核卡失敗，請通知管理員檢查權限",
                ephemeral=True,
            )
            return

        response_text = f"✅ 已提交申請編號 #{app_id}，請等待審核結果"
        if interview_reminder:
            response_text += f"\n\n{interview_reminder}"

        await SafeInteractionHandler.safe_respond(
            interaction,
            content=response_text,
            ephemeral=True,
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

    @discord.ui.button(
        label="🎙️ 面試管理",
        style=discord.ButtonStyle.secondary,
        custom_id="whitelist:interview_manage",
        row=1,
    )
    async def interview_manage_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        guild = interaction.guild
        member = interaction.user if isinstance(interaction.user, discord.Member) else None
        if not guild or not member:
            await interaction.response.send_message("❌ 僅能在伺服器中使用。", ephemeral=True)
            return

        if not await self._can_manage_interview(member):
            await interaction.response.send_message("❌ 你沒有面試管理權限。", ephemeral=True)
            return

        panel_view = WhitelistInterviewAdminView(
            self.bot,
            guild,
            member.id,
            allow_configuration=False,
        )
        embed = await panel_view.build_embed()
        await interaction.response.send_message(embed=embed, view=panel_view, ephemeral=True)

    async def _can_manage_interview(self, member: discord.Member) -> bool:
        if (
            member.guild_permissions.administrator
            or member.guild_permissions.manage_guild
            or member.guild_permissions.manage_channels
        ):
            return True

        member_role_ids = {role.id for role in member.roles}
        if self.settings.role_staff_id and self.settings.role_staff_id in member_role_ids:
            return True

        try:
            interview_settings = await WhitelistInterviewService(
                WhitelistInterviewDAO()
            ).load_settings(member.guild.id)
            if interview_settings.staff_role_id and interview_settings.staff_role_id in member_role_ids:
                return True
        except Exception:
            pass

        return False


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
        self.interview_dao = WhitelistInterviewDAO()
        self.interview_service = WhitelistInterviewService(self.interview_dao)
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

        answers: Any = app.get("answers_json")
        if isinstance(answers, str):
            try:
                answers = json.loads(answers)
            except json.JSONDecodeError:
                answers = {}
        if not isinstance(answers, dict):
            answers = {}

        if app.get("status") not in ("PENDING", "NEED_MORE"):
            await interaction.followup.send("⚠️ 申請已處理", ephemeral=True)
            return

        # 嘗試以資料庫層級鎖定狀態，避免多人同時審核重複處理
        updated = await self.dao.set_status(self.app_id, status, interaction.user.id, note)
        if not updated:
            await interaction.followup.send("⚠️ 申請已被其他管理員處理", ephemeral=True)
            return

        await self._remove_from_interview_channel(interaction.guild, applicant_id)

        if status in ("DENIED", "NEED_MORE"):
            await self._restore_interview_original_nickname(interaction.guild, applicant_id, status)
            await self._mark_interview_queue_done(interaction.guild.id, applicant_id)

        # 身分組處理（僅通過）
        if status == "APPROVED":
            member = interaction.guild.get_member(applicant_id)
            if member:
                character_name = None
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

        # 關閉按鈕 + 更新審核卡（顯示審核者）
        for item in self.children:
            item.disabled = True
        try:
            applicant = interaction.guild.get_member(applicant_id)
            if applicant is None:
                try:
                    applicant = await self.bot.fetch_user(applicant_id)
                except Exception:
                    applicant = None

            embed = build_review_embed(
                self.app_id,
                applicant_id,
                applicant,
                answers,
                status=status,
                note=note,
                reviewer=interaction.user,
            )
            interview_reviewer_field, _ = await _build_interview_reminder(interaction.guild)
            embed.add_field(
                name="🎙️ 海關語音面試資訊",
                value=interview_reviewer_field[:1024],
                inline=False,
            )
            await interaction.message.edit(embed=embed, view=self)
        except Exception:
            try:
                await interaction.message.edit(view=self)
            except Exception:
                pass

        await interaction.followup.send(f"✅ 已更新申請 #{self.app_id} 為 {status}", ephemeral=True)

    async def _restore_interview_original_nickname(
        self,
        guild: discord.Guild,
        applicant_id: int,
        status: str,
    ) -> None:
        try:
            row = await self.interview_dao.get_latest_queue_entry_for_user(guild.id, applicant_id)
            if not row:
                return

            member = guild.get_member(applicant_id)
            if not member:
                try:
                    member = await guild.fetch_member(applicant_id)
                except Exception:
                    member = None
            if not member:
                return

            me = guild.me
            if not me and self.bot.user:
                me = guild.get_member(self.bot.user.id)
            if not me or not me.guild_permissions.manage_nicknames:
                return
            if member == guild.owner:
                return
            if me.top_role <= member.top_role:
                return

            original_nickname = row.get("original_nickname")
            target_nick: str | None
            if original_nickname is None:
                target_nick = None
            else:
                cleaned = str(original_nickname).strip()
                target_nick = cleaned if cleaned else None

            if member.nick == target_nick:
                return

            reason = (
                "Whitelist denied - restore original nickname"
                if status == "DENIED"
                else "Whitelist need more - restore original nickname"
            )
            await member.edit(nick=target_nick, reason=reason)
        except Exception as e:
            logger.warning(f"還原面試原暱稱失敗 (user={applicant_id}): {e}")

    async def _mark_interview_queue_done(self, guild_id: int, applicant_id: int) -> None:
        try:
            await self.interview_dao.complete_waiting_entries_for_user(guild_id, applicant_id)
        except Exception as e:
            logger.warning(f"更新面試隊列狀態失敗 (user={applicant_id}): {e}")

    async def _remove_from_interview_channel(
        self, guild: discord.Guild, applicant_id: int
    ) -> None:
        try:
            interview_settings = await self.interview_service.load_settings(guild.id)
            interview_channel_id = interview_settings.interview_channel_id
            if not interview_channel_id:
                return

            member = guild.get_member(applicant_id)
            if not member:
                try:
                    member = await guild.fetch_member(applicant_id)
                except Exception:
                    member = None
            if not member or not member.voice or not member.voice.channel:
                return
            if member.voice.channel.id != interview_channel_id:
                return

            await member.move_to(None, reason="Whitelist review completed")
        except Exception as e:
            logger.warning(f"移除面試語音成員失敗 (user={applicant_id}): {e}")

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


def build_review_embed(
    app_id: int,
    applicant_id: int,
    user: Optional[discord.abc.User],
    answers: Dict[str, Any],
    *,
    status: str | None = None,
    note: str | None = None,
    reviewer: Optional[discord.abc.User] = None,
) -> discord.Embed:
    """建立審核卡片 embed。"""
    status_text = {
        "PENDING": "待審核",
        "APPROVED": "通過",
        "DENIED": "拒絕",
        "NEED_MORE": "補件",
    }
    color_map = {
        "PENDING": 0x9B59B6,
        "APPROVED": 0x2ECC71,
        "DENIED": 0xE74C3C,
        "NEED_MORE": 0xF1C40F,
    }
    status_code = status or "PENDING"
    mention = user.mention if user else f"<@{applicant_id}>"
    display_id = user.id if user else applicant_id
    embed = discord.Embed(
        title=f"🧾 申請單 #{app_id}",
        description=f"申請人: {mention} (`{display_id}`)",
        color=color_map.get(status_code, 0x9B59B6),
    )
    embed.add_field(name="角色名", value=answers.get("character_name", "未填"), inline=False)
    embed.add_field(name="年齡", value=answers.get("age", "未填"), inline=False)
    embed.add_field(name="角色人設", value=answers.get("background", "未填")[:1024], inline=False)
    embed.add_field(name="超人扮演/情緒帶入示例", value=answers.get("roleplay_examples", "未填")[:1024], inline=False)
    embed.add_field(name="同意規章", value=answers.get("rules", "未填"), inline=False)
    if status is not None:
        embed.add_field(name="狀態", value=status_text.get(status_code, status_code), inline=False)
    if reviewer:
        embed.add_field(name="審核員", value=reviewer.mention, inline=False)
    if note:
        embed.add_field(name="備註", value=note[:1024], inline=False)
    return embed
