# bot/views/system_admin_views.py - 系統管理UI界面
"""
系統管理UI界面
提供圖形化的系統設定面板，包含票券系統、歡迎系統等各項設定
"""

import asyncio
import time
import discord
from discord.ui import (
    Button,
    ChannelSelect,
    Modal,
    RoleSelect,
    Select,
    TextInput,
    UserSelect,
    View,
    button,
)

from potato_bot.db import vote_dao
from potato_bot.db.category_auto_dao import CategoryAutoDAO
from potato_bot.db.auto_reply_dao import AutoReplyDAO
from potato_bot.db.music_dao import MusicDAO
from potato_bot.db.lottery_dao import LotteryDAO
from potato_bot.db.fivem_dao import FiveMDAO
from potato_bot.db.resume_dao import ResumeDAO
from potato_bot.db.pool import db_pool
from potato_bot.db.ticket_dao import TicketDAO
from potato_bot.db.welcome_dao import WelcomeDAO
from potato_bot.services.category_auto_service import (
    build_manager_overwrites,
    can_use_category_auto,
)
from potato_bot.services.data_cleanup_manager import DataCleanupManager
from potato_bot.services.resume_service import ResumePanelService, ResumeService
from potato_bot.services.welcome_manager import WelcomeManager
from potato_bot.services.whitelist_service import WhitelistService
from potato_bot.services.system_settings_service import SystemSettingsService
from potato_bot.db.whitelist_dao import WhitelistDAO
from potato_bot.utils.interaction_helper import BaseView, SafeInteractionHandler
from potato_bot.utils.embed_builder import EmbedBuilder
from potato_bot.views.resume_views import ResumePanelView
from potato_shared.logger import logger
from potato_shared.config import (
    FIVEM_TXADMIN_FTP_HOST,
    FIVEM_TXADMIN_FTP_PATH,
    FIVEM_TXADMIN_STATUS_FILE,
    LAVALINK_HOST,
    LAVALINK_PASSWORD,
    LAVALINK_PORT,
    LAVALINK_SECURE,
    LAVALINK_URI,
)


def _is_guild_owner(interaction: discord.Interaction) -> bool:
    if not interaction.guild:
        return False
    return interaction.user.id == interaction.guild.owner_id


async def _has_system_admin_access(interaction: discord.Interaction) -> bool:
    if await interaction.client.is_owner(interaction.user):
        return True
    if _is_guild_owner(interaction):
        return True
    if interaction.user.guild_permissions.manage_guild:
        return True
    service = SystemSettingsService()
    admin_user_ids = await service.get_admin_user_ids(interaction.guild.id)
    return interaction.user.id in admin_user_ids


class SystemAdminPanel(BaseView):
    """系統管理主面板"""

    def __init__(self, user_id: int, timeout=300):
        super().__init__(user_id=user_id, timeout=timeout)
        self.ticket_dao = TicketDAO()
        self.welcome_dao = WelcomeDAO()
        self.welcome_manager = WelcomeManager(self.welcome_dao)
        self.fivem_dao = FiveMDAO()

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        """檢查用戶權限"""
        # 先檢查基類權限
        if not await super().interaction_check(interaction):
            return False

        if await _has_system_admin_access(interaction):
            return True

        await SafeInteractionHandler.safe_respond(
            interaction, content="❌ 需要管理伺服器權限或已授權管理員", ephemeral=True
        )
        return False

    @button(label="🎫 票券系統設定", style=discord.ButtonStyle.primary, row=0)
    async def ticket_settings_button(self, interaction: discord.Interaction, button: Button):
        """票券系統設定按鈕"""
        await interaction.response.send_message(
            embed=await self._create_ticket_settings_embed(interaction.guild),
            view=TicketSettingsView(self.user_id),
            ephemeral=True,
        )

    @button(label="🎉 歡迎系統設定", style=discord.ButtonStyle.success, row=0)
    async def welcome_settings_button(self, interaction: discord.Interaction, button: Button):
        """歡迎系統設定按鈕"""
        await interaction.response.send_message(
            embed=await self._create_welcome_settings_embed(interaction.guild),
            view=WelcomeSettingsView(self.user_id),
            ephemeral=True,
        )

    @button(label="🗳️ 投票系統設定", style=discord.ButtonStyle.primary, row=0)
    async def vote_settings_button(self, interaction: discord.Interaction, button: Button):
        """投票系統設定按鈕"""
        await interaction.response.send_message(
            embed=await self._create_vote_settings_embed(interaction.guild),
            view=VoteSettingsView(self.user_id),
            ephemeral=True,
        )

    @button(label="🎲 抽獎系統設定", style=discord.ButtonStyle.primary, row=0)
    async def lottery_settings_button(self, interaction: discord.Interaction, button: Button):
        """抽獎系統設定按鈕"""
        await interaction.response.send_message(
            embed=await self._create_lottery_settings_embed(interaction.guild),
            view=LotterySettingsView(self.user_id, interaction.guild),
            ephemeral=True,
        )

    @button(label="🎵 音樂系統設定", style=discord.ButtonStyle.primary, row=0)
    async def music_settings_button(self, interaction: discord.Interaction, button: Button):
        """音樂系統設定按鈕"""
        await interaction.response.send_message(
            embed=await self._create_music_settings_embed(interaction.guild, interaction.client),
            view=MusicSettingsView(self.user_id, interaction.guild),
            ephemeral=True,
        )

    @button(label="🛂 入境審核設定", style=discord.ButtonStyle.secondary, row=1)
    async def whitelist_settings_button(self, interaction: discord.Interaction, button: Button):
        """入境審核設定"""
        await SafeInteractionHandler.safe_defer(interaction, ephemeral=True)
        try:
            service = WhitelistService(WhitelistDAO())
            settings = await service.load_settings(interaction.guild.id)
            embed = await self._create_whitelist_settings_embed(
                interaction.guild, settings=settings
            )
            view = WhitelistSettingsView(self.user_id, interaction.guild)
            await SafeInteractionHandler.safe_respond(
                interaction,
                embed=embed,
                view=view,
                ephemeral=True,
            )
        except Exception as e:
            logger.error(f"入境審核設定開啟失敗: {e}")
            await SafeInteractionHandler.handle_interaction_error(
                interaction, e, operation_name="入境審核設定"
            )

    @button(label="🧾 履歷系統設定", style=discord.ButtonStyle.primary, row=1)
    async def resume_settings_button(self, interaction: discord.Interaction, button: Button):
        """履歷系統設定"""
        await SafeInteractionHandler.safe_defer(interaction, ephemeral=True)
        try:
            service = ResumeService(ResumeDAO())
            companies = await service.list_companies(interaction.guild.id)
            selected_id = companies[0].company_id if companies else None
            embed = await self._create_resume_settings_embed(
                interaction.guild, companies, selected_company_id=selected_id
            )
            view = ResumeSettingsView(
                self.user_id,
                interaction.guild,
                interaction.client,
                companies=companies,
                selected_company_id=selected_id,
            )
            await SafeInteractionHandler.safe_respond(
                interaction,
                embed=embed,
                view=view,
                ephemeral=True,
            )
        except Exception as e:
            logger.error(f"履歷系統設定開啟失敗: {e}")
            await SafeInteractionHandler.handle_interaction_error(
                interaction, e, operation_name="履歷系統設定"
            )

    @button(label="🛰️ FiveM 狀態設定", style=discord.ButtonStyle.secondary, row=1)
    async def fivem_settings_button(self, interaction: discord.Interaction, button: Button):
        """FiveM 狀態設定"""
        await interaction.response.send_message(
            embed=await self._create_fivem_settings_embed(interaction.guild, interaction.client),
            view=FiveMSettingsView(self.user_id, interaction.guild),
            ephemeral=True,
        )

    @button(label="📊 系統狀態", style=discord.ButtonStyle.secondary, row=2)
    async def system_status_button(self, interaction: discord.Interaction, button: Button):
        """系統狀態按鈕"""
        await SafeInteractionHandler.safe_defer(interaction, ephemeral=True)
        try:
            embed = await self._create_system_status_embed(interaction)
            view = SystemStatusView(self.user_id, interaction.guild)
            await SafeInteractionHandler.safe_respond(
                interaction, embed=embed, view=view, ephemeral=True
            )
        except Exception as e:
            logger.error(f"系統狀態面板開啟失敗: {e}")
            await SafeInteractionHandler.handle_interaction_error(
                interaction, e, operation_name="系統狀態"
            )

    @button(label="🔧 系統工具", style=discord.ButtonStyle.secondary, row=2)
    async def system_tools_button(self, interaction: discord.Interaction, button: Button):
        """系統工具按鈕"""
        await interaction.response.send_message(
            embed=self._create_system_tools_embed(),
            view=SystemToolsView(self.user_id),
            ephemeral=True,
        )

    @button(label="❌ 關閉面板", style=discord.ButtonStyle.danger, row=2)
    async def close_button(self, interaction: discord.Interaction, button: Button):
        """關閉面板按鈕"""
        embed = discord.Embed(
            title="✅ 管理面板已關閉",
            description="系統管理面板已關閉",
            color=0x95A5A6,
        )
        await interaction.response.edit_message(embed=embed, view=None)
        self.stop()

    async def _create_ticket_settings_embed(self, guild: discord.Guild) -> discord.Embed:
        """創建票券系統設定嵌入"""
        settings = await self.ticket_dao.get_settings(guild.id)

        embed = discord.Embed(
            title="🎫 票券系統設定",
            description="當前票券系統配置狀態",
            color=0x3498DB,
        )

        # 基本設定
        category_status = "✅ 已設定" if settings.get("category_id") else "❌ 未設定"
        embed.add_field(
            name="📂 票券分類頻道",
            value=f"{category_status}\n{('<#' + str(settings['category_id']) + '>') if settings.get('category_id') else '尚未設定'}",
            inline=True,
        )

        support_roles = settings.get("support_roles", [])
        roles_text = "✅ 已設定" if support_roles else "❌ 未設定"
        if support_roles:
            roles_text += f"\n{len(support_roles)} 個角色"

        embed.add_field(name="👥 客服角色", value=roles_text, inline=True)

        sponsor_roles = settings.get("sponsor_support_roles", [])
        sponsor_text = "✅ 已設定" if sponsor_roles else "❌ 未設定（沿用客服）"
        if sponsor_roles:
            sponsor_text += f"\n{len(sponsor_roles)} 個角色"
        embed.add_field(name="💖 贊助處理角色", value=sponsor_text, inline=True)

        # 系統參數
        embed.add_field(
            name="⚙️ 系統參數",
            value=f"每人票券上限: {settings.get('max_tickets_per_user', 3)}\n"
            f"自動關閉時間: {settings.get('auto_close_hours', 24)}小時",
            inline=True,
        )

        return embed

    async def _create_welcome_settings_embed(self, guild: discord.Guild) -> discord.Embed:
        """創建歡迎系統設定嵌入"""
        settings = await self.welcome_dao.get_welcome_settings(guild.id)

        embed = discord.Embed(
            title="🎉 歡迎系統設定",
            description="當前歡迎系統配置狀態",
            color=0x2ECC71,
        )

        if not settings:
            embed.add_field(
                name="⚠️ 系統狀態",
                value="歡迎系統尚未初始化\n請點擊下方按鈕進行設定",
                inline=False,
            )
            return embed

        # 系統狀態
        status = "✅ 已啟用" if settings.get("is_enabled") else "❌ 已停用"
        embed.add_field(name="🔧 系統狀態", value=status, inline=True)

        # 頻道設定
        welcome_ch = (
            f"<#{settings['welcome_channel_id']}>"
            if settings.get("welcome_channel_id")
            else "❌ 未設定"
        )
        leave_ch = (
            f"<#{settings['leave_channel_id']}>"
            if settings.get("leave_channel_id")
            else "❌ 未設定"
        )

        embed.add_field(
            name="📺 頻道設定",
            value=f"歡迎頻道: {welcome_ch}\n離開頻道: {leave_ch}",
            inline=True,
        )

        # 功能狀態
        features = []
        features.append(f"嵌入訊息: {'✅' if settings.get('welcome_embed_enabled') else '❌'}")
        features.append(f"私訊歡迎: {'✅' if settings.get('welcome_dm_enabled') else '❌'}")
        features.append(f"自動身分組: {'✅' if settings.get('auto_role_enabled') else '❌'}")

        embed.add_field(name="⚙️ 功能狀態", value="\n".join(features), inline=True)

        return embed

    async def _create_vote_settings_embed(self, guild: discord.Guild) -> discord.Embed:
        """創建投票系統設定嵌入"""
        embed = discord.Embed(
            title="🗳️ 投票系統設定",
            description="管理投票系統的頻道和參數設定",
            color=0x3498DB,
        )

        # 取得投票設定
        vote_settings = await vote_dao.get_vote_settings(guild.id)

        if vote_settings:
            # 頻道設定
            vote_channel = (
                f"<#{vote_settings['default_vote_channel_id']}>"
                if vote_settings.get("default_vote_channel_id")
                else "未設定"
            )
            announce_channel = (
                f"<#{vote_settings['announcement_channel_id']}>"
                if vote_settings.get("announcement_channel_id")
                else "未設定"
            )

            embed.add_field(
                name="📺 頻道設定",
                value=f"預設投票頻道: {vote_channel}\n" f"結果公告頻道: {announce_channel}",
                inline=False,
            )

            # 系統狀態
            status = "✅ 啟用" if vote_settings.get("is_enabled") else "❌ 停用"
            embed.add_field(name="🔧 系統狀態", value=status, inline=True)

            # 時間限制
            embed.add_field(
                name="⏰ 時間限制",
                value=f"最長: {vote_settings.get('max_vote_duration_hours', 72)}小時\n"
                f"最短: {vote_settings.get('min_vote_duration_minutes', 60)}分鐘",
                inline=True,
            )

            # 功能狀態
            features = []
            features.append(
                f"匿名投票: {'✅' if vote_settings.get('allow_anonymous_votes') else '❌'}"
            )
            features.append(
                f"多選投票: {'✅' if vote_settings.get('allow_multi_choice') else '❌'}"
            )
            features.append(
                f"自動公告: {'✅' if vote_settings.get('auto_announce_results') else '❌'}"
            )

            embed.add_field(name="⚙️ 功能開關", value="\n".join(features), inline=True)

            allowed_roles = vote_settings.get("allowed_creator_roles", []) or []
            if allowed_roles:
                role_text = "、".join(
                    role.mention
                    for role in (guild.get_role(role_id) for role_id in allowed_roles)
                    if role
                )
                if not role_text:
                    role_text = "未設定（僅管理員可用）"
            else:
                role_text = "未設定（僅管理員可用）"
            embed.add_field(name="👥 面板權限", value=role_text, inline=False)
        else:
            embed.add_field(
                name="⚠️ 系統狀態",
                value="投票系統尚未設定，使用預設配置\n" "投票將發布在執行指令的頻道",
                inline=False,
            )

        embed.add_field(name="📋 管理選項", value="使用下方按鈕進行設定", inline=False)

        return embed

    async def _create_lottery_settings_embed(self, guild: discord.Guild) -> discord.Embed:
        """創建抽獎系統設定嵌入"""
        embed = discord.Embed(
            title="🎲 抽獎系統設定",
            description="管理抽獎面板權限",
            color=0x3498DB,
        )

        settings = await LotteryDAO().get_lottery_settings(guild.id)
        allowed_roles = settings.get("admin_roles", []) if settings else []

        if allowed_roles:
            role_text = "、".join(
                role.mention
                for role in (guild.get_role(role_id) for role_id in allowed_roles)
                if role
            )
            if not role_text:
                role_text = "未設定（僅管理員可用）"
        else:
            role_text = "未設定（僅管理員可用）"

        embed.add_field(name="👥 面板權限", value=role_text, inline=False)
        embed.add_field(name="📋 管理選項", value="使用下方按鈕進行設定", inline=False)

        return embed

    async def _create_music_settings_embed(
        self, guild: discord.Guild, bot: discord.Client | None = None
    ) -> discord.Embed:
        """創建音樂系統設定嵌入"""
        embed = discord.Embed(
            title="🎵 音樂系統設定",
            description="管理音樂面板權限",
            color=0x3498DB,
        )

        settings = await MusicDAO().get_music_settings(guild.id)
        allowed_roles = settings.get("allowed_role_ids", []) if settings else []
        require_role = settings.get("require_role_to_use", False) if settings else False

        if require_role and allowed_roles:
            role_text = "、".join(
                role.mention
                for role in (guild.get_role(role_id) for role_id in allowed_roles)
                if role
            )
            if not role_text:
                role_text = "未設定（僅管理員可用）"
        elif require_role and not allowed_roles:
            role_text = "未設定（僅管理員可用）"
        else:
            role_text = "未限制（所有人可用）"

        embed.add_field(name="👥 面板權限", value=role_text, inline=False)

        admin_override = any(
            settings.get(key)
            for key in (
                "lavalink_host",
                "lavalink_port",
                "lavalink_password",
                "lavalink_uri",
            )
        ) or settings.get("lavalink_secure") is not None

        lavalink_host = settings.get("lavalink_host") or LAVALINK_HOST or "未設定"
        lavalink_port = settings.get("lavalink_port") or LAVALINK_PORT or "未設定"
        if settings.get("lavalink_secure") is None:
            lavalink_secure = LAVALINK_SECURE
        else:
            lavalink_secure = bool(settings.get("lavalink_secure"))
        lavalink_uri = settings.get("lavalink_uri") or LAVALINK_URI or "未設定"
        lavalink_password = settings.get("lavalink_password") or LAVALINK_PASSWORD

        status_text = "⏳ 尚未取得"
        if bot:
            music_cog = bot.get_cog("MusicCore")
            if music_cog and hasattr(music_cog, "get_lavalink_status"):
                status = await music_cog.get_lavalink_status(guild.id)
                if status.get("connected"):
                    status_text = "✅ 已連線"
                else:
                    status_text = "❌ 未連線"
                if status.get("error"):
                    status_text = f"{status_text}\n{status.get('error')}"

        config_text = "\n".join(
            [
                f"來源: {'Admin' if admin_override else '.env'}",
                f"URI: {lavalink_uri}",
                f"Host: {lavalink_host}",
                f"Port: {lavalink_port}",
                f"Secure: {'true' if lavalink_secure else 'false'}",
                f"Password: {'已設定' if lavalink_password else '未設定'}",
            ]
        )

        embed.add_field(name="🎛️ Lavalink 設定", value=config_text, inline=False)
        embed.add_field(name="📡 Lavalink 狀態", value=status_text, inline=False)
        embed.add_field(name="📋 管理選項", value="使用下方按鈕進行設定", inline=False)

        return embed

    async def _create_fivem_settings_embed(
        self, guild: discord.Guild, bot: discord.Client | None = None
    ) -> discord.Embed:
        """創建 FiveM 狀態設定嵌入"""
        settings = await self.fivem_dao.get_fivem_settings(guild.id)

        channel_id = settings.get("status_channel_id") or 0
        channel_text = f"<#{channel_id}>" if channel_id else "未設定"
        info_url = settings.get("info_url") or "未設定"
        players_url = settings.get("players_url") or "未設定"
        poll_interval = settings.get("poll_interval")
        poll_text = f"{poll_interval} 秒" if poll_interval else "預設"
        server_link = settings.get("server_link") or "未設定"
        status_image_url = settings.get("status_image_url") or "未設定"
        status_roles = settings.get("alert_role_ids", []) or []
        if status_roles:
            role_text = "、".join(
                role.mention
                for role in (guild.get_role(role_id) for role_id in status_roles)
                if role
            )
            if not role_text:
                role_text = "未設定"
        else:
            role_text = "未設定"

        dm_roles = settings.get("dm_role_ids", []) or []
        if dm_roles:
            dm_role_text = "、".join(
                role.mention
                for role in (guild.get_role(role_id) for role_id in dm_roles)
                if role
            )
            if not dm_role_text:
                dm_role_text = "未設定"
        else:
            dm_role_text = "未設定"

        embed = discord.Embed(
            title="🛰️ FiveM 狀態設定",
            description="使用下方分類按鈕進行設定",
            color=0x3498DB,
        )

        panel_message_id = settings.get("panel_message_id") or 0
        panel_status_text = "✅ 已部署" if panel_message_id else "❌ 未部署"

        ftp_configured = bool(FIVEM_TXADMIN_FTP_HOST and FIVEM_TXADMIN_FTP_PATH)
        txadmin_source_configured = ftp_configured or bool(FIVEM_TXADMIN_STATUS_FILE)
        ftp_status_text = "未啟用"
        if ftp_configured:
            ftp_status_text = "⏳ 尚未取得"
            if bot:
                fivem_cog = bot.get_cog("FiveMStatusCore")
                if fivem_cog and hasattr(fivem_cog, "get_ftp_connection_status"):
                    status = await fivem_cog.get_ftp_connection_status(guild)
                    if status is True:
                        ftp_status_text = "✅ 已連線"
                    elif status is False:
                        ftp_status_text = "❌ 未連線"
                    else:
                        ftp_status_text = "未啟用"

        txadmin_read_text = "未啟用"
        if txadmin_source_configured:
            txadmin_read_text = "⏳ 尚未讀取"
            if bot:
                fivem_cog = bot.get_cog("FiveMStatusCore")
                if fivem_cog and hasattr(fivem_cog, "get_txadmin_read_status"):
                    status = await fivem_cog.get_txadmin_read_status(guild)
                    if status is None:
                        txadmin_read_text = "未啟用"
                    else:
                        ok = status.get("ok")
                        last_at = status.get("last_read_at")
                        if last_at:
                            seconds_ago = max(0, int(time.time() - last_at))
                            time_text = f"{seconds_ago} 秒前"
                        else:
                            time_text = "尚未"
                        if ok is True:
                            txadmin_read_text = f"✅ 已讀取（{time_text}）"
                        elif ok is False:
                            txadmin_read_text = f"❌ 讀取失敗（{time_text}）"
                        else:
                            txadmin_read_text = "⏳ 尚未讀取"

        embed.add_field(
            name="📣 播報",
            value=f"頻道: {channel_text}\n面板: {panel_status_text}",
            inline=False,
        )
        embed.add_field(
            name="🌐 API",
            value=f"info: {info_url}\nplayers: {players_url}\n輪詢: {poll_text}",
            inline=False,
        )
        embed.add_field(
            name="🔔 通知",
            value=f"頻道標註: {role_text}\nDM 通知: {dm_role_text}",
            inline=False,
        )
        embed.add_field(
            name="🧩 面板",
            value=f"連結: {server_link}\n圖片: {status_image_url}",
            inline=False,
        )
        embed.add_field(
            name="🧪 txAdmin",
            value=f"FTP: {ftp_status_text}\n狀態檔: {txadmin_read_text}",
            inline=False,
        )

        return embed

    async def _create_whitelist_settings_embed(
        self, guild: discord.Guild, settings=None
    ) -> discord.Embed:
        """創建入境審核設定摘要"""
        if settings is None:
            service = WhitelistService(WhitelistDAO())
            settings = await service.load_settings(guild.id)

        embed = discord.Embed(
            title="🛂 入境審核設定",
            description="入境面板、審核頻道與角色配置",
            color=0x9B59B6,
        )

        panel_ch = f"<#{settings.panel_channel_id}>" if settings.panel_channel_id else "未設定"
        review_ch = f"<#{settings.review_channel_id}>" if settings.review_channel_id else "未設定"
        result_ch = f"<#{settings.result_channel_id}>" if settings.result_channel_id else "未設定"

        staff_role = f"<@&{settings.role_staff_id}>" if settings.role_staff_id else "未設定"
        if settings.role_newcomer_ids:
            newcomer_role = ", ".join(f"<@&{rid}>" for rid in settings.role_newcomer_ids)
        else:
            newcomer_role = "未設定"
        citizen_role = f"<@&{settings.role_citizen_id}>" if settings.role_citizen_id else "未設定"
        nickname_role = (
            f"<@&{settings.nickname_role_id}>" if settings.nickname_role_id else "未設定"
        )
        nickname_prefix = settings.nickname_prefix or "未設定"

        embed.add_field(
            name="📺 頻道設定",
            value=f"面板: {panel_ch}\n審核: {review_ch}\n結果公告: {result_ch}",
            inline=True,
        )
        embed.add_field(
            name="🛡️ 角色配置",
            value=f"審核員: {staff_role}\n新手: {newcomer_role}\n市民: {citizen_role}",
            inline=True,
        )
        embed.add_field(
            name="🏷️ 暱稱設定",
            value=f"套用角色: {nickname_role}\n前綴: {nickname_prefix}",
            inline=True,
        )

        embed.add_field(
            name="⚙️ 設定狀態",
            value="✅ 已設定完整" if settings.is_complete else "⚠️ 尚未填完所有必要設定",
            inline=False,
        )

        return embed

    async def _create_resume_settings_embed(
        self,
        guild: discord.Guild,
        companies: list,
        selected_company_id: int | None = None,
    ) -> discord.Embed:
        """創建履歷系統設定摘要"""
        embed = discord.Embed(
            title="🧾 履歷系統設定",
            description="管理各公司的履歷填單與審核設定",
            color=0x3498DB,
        )

        if not companies:
            embed.add_field(
                name="⚠️ 尚未建立公司",
                value="請使用下方「新增公司」按鈕建立公司設定",
                inline=False,
            )
            return embed

        selected = None
        for company in companies:
            if company.company_id == selected_company_id:
                selected = company
                break
        if selected is None:
            selected = companies[0]

        lines = []
        for company in companies[:25]:
            marker = "➡️ " if company.company_id == selected.company_id else "• "
            status = "✅" if company.is_enabled else "❌"
            lines.append(f"{marker}{company.company_name} {status}")
        companies_text = "\n".join(lines) if lines else "未建立公司"

        embed.add_field(name="🏢 公司清單", value=companies_text, inline=False)
        embed.add_field(name="📌 目前公司", value=selected.company_name, inline=False)

        panel_ch = f"<#{selected.panel_channel_id}>" if selected.panel_channel_id else "未設定"
        review_ch = (
            f"<#{selected.review_channel_id}>" if selected.review_channel_id else "未設定"
        )
        embed.add_field(
            name="📺 頻道設定",
            value=f"填單頻道: {panel_ch}\n審核頻道: {review_ch}",
            inline=True,
        )

        if selected.review_role_ids:
            role_text = ", ".join(f"<@&{role_id}>" for role_id in selected.review_role_ids)
        else:
            role_text = "未設定"
        embed.add_field(name="🛡️ 審核身分組", value=role_text, inline=True)

        if selected.approved_role_ids:
            approved_text = ", ".join(
                f"<@&{role_id}>" for role_id in selected.approved_role_ids
            )
        else:
            approved_text = "未設定"
        embed.add_field(name="🎯 通過身分組", value=approved_text, inline=True)

        if selected.manageable_role_ids:
            manageable_text = ", ".join(
                f"<@&{role_id}>" for role_id in selected.manageable_role_ids
            )
        else:
            manageable_text = "未設定"
        embed.add_field(name="🏷️ 可管理身分組", value=manageable_text, inline=True)

        status_text = "✅ 啟用" if selected.is_enabled else "❌ 停用"
        embed.add_field(name="⚙️ 狀態", value=status_text, inline=True)

        return embed

    async def _create_system_status_embed(
        self, interaction: discord.Interaction
    ) -> discord.Embed:
        """創建系統狀態嵌入"""
        bot = interaction.client
        guild = interaction.guild

        latency_ms = None
        if bot and bot.latency is not None:
            latency_ms = round(bot.latency * 1000, 2)

        uptime = "未知"
        if bot and hasattr(bot, "get_uptime"):
            uptime = bot.get_uptime()

        guild_count = len(bot.guilds) if bot else 0
        member_count = guild.member_count if guild and guild.member_count else 0

        overall_status = "healthy"
        db_status_text = "❓ 未知"
        db_latency = "N/A"
        pool_status = "N/A"
        db_name = "N/A"

        try:
            health = await db_pool.health_check()
            db_status = health.get("status", "unknown")
            db_latency = health.get("latency", "N/A")
            pool_status = health.get("pool_status", "N/A")
            db_name = (health.get("database") or {}).get("name", "N/A")

            if db_status == "healthy":
                db_status_text = "✅ 正常"
            elif db_status == "unhealthy":
                db_status_text = "❌ 異常"
                overall_status = "unhealthy"
            else:
                db_status_text = f"⚠️ {db_status}"
                overall_status = "degraded"
        except Exception as e:
            logger.error(f"系統狀態檢查失敗: {e}")
            db_status_text = "❌ 無法取得"
            overall_status = "degraded"

        if latency_ms is not None and latency_ms >= 1000 and overall_status == "healthy":
            overall_status = "degraded"

        status_color = {
            "healthy": 0x2ECC71,
            "degraded": 0xF1C40F,
            "unhealthy": 0xE74C3C,
        }.get(overall_status, 0x95A5A6)

        overall_text = {
            "healthy": "✅ 正常",
            "degraded": "⚠️ 注意",
            "unhealthy": "❌ 異常",
        }.get(overall_status, "❓ 未知")

        embed = discord.Embed(
            title="📊 系統狀態",
            description="系統運行狀態概覽",
            color=status_color,
        )
        embed.add_field(name="📈 整體狀態", value=overall_text, inline=True)

        latency_text = f"{latency_ms} ms" if latency_ms is not None else "未知"
        bot_lines = [
            f"延遲: {latency_text}",
            f"運行時間: {uptime}",
            f"連接伺服器: {guild_count}",
        ]
        if member_count:
            bot_lines.append(f"本伺服器成員: {member_count}")
        embed.add_field(name="🤖 機器人", value="\n".join(bot_lines), inline=False)

        db_lines = [
            f"狀態: {db_status_text}",
            f"延遲: {db_latency}",
            f"連線池: {pool_status}",
        ]
        if db_name and db_name != "N/A":
            db_lines.append(f"資料庫: {db_name}")
        embed.add_field(name="🗄️ 資料庫", value="\n".join(db_lines), inline=False)

        embed.set_footer(text="資料為即時快照")
        embed.timestamp = discord.utils.utcnow()
        return embed

    def _create_system_tools_embed(self) -> discord.Embed:
        """創建系統工具嵌入"""
        embed = discord.Embed(
            title="🔧 系統工具",
            description="系統維護和管理工具",
            color=0x95A5A6,
        )

        embed.add_field(
            name="🧹 資料清理",
            value="• 清理舊日誌\n• 清理過期快取\n• 整理資料庫",
            inline=True,
        )

        embed.add_field(
            name="🗑️ 頻道清空",
            value="• 清空頻道訊息\n• 清空近期訊息\n• 按用戶清空",
            inline=True,
        )

        embed.add_field(
            name="💬 自動回覆",
            value="• @ 指定成員自動回覆\n• 管理回覆內容",
            inline=True,
        )

        embed.add_field(
            name="🗳️ 投票管理面板",
            value="• 管理投票建立\n• 查看投票統計",
            inline=True,
        )

        embed.add_field(
            name="🎲 抽獎管理面板",
            value="• 管理抽獎建立\n• 查看抽獎統計",
            inline=True,
        )

        embed.add_field(
            name="🎵 音樂管理面板",
            value="• 播放與控制音樂\n• 搜索與播放列表",
            inline=True,
        )

        embed.add_field(
            name="🗂️ 類別自動建立",
            value="• 批量建立類別\n• 設定可用身分組與管理身分組",
            inline=True,
        )

        embed.add_field(
            name="🤖 狀態欄位設定",
            value="• 輪播內容\n• 輪播間隔",
            inline=True,
        )

        embed.add_field(
            name="🛡️ 管理面板授權",
            value="• Owner 指定授權成員",
            inline=True,
        )

        return embed


class SystemStatusView(BaseView):
    """系統狀態面板"""

    def __init__(self, user_id: int, guild: discord.Guild, timeout=300):
        super().__init__(user_id=user_id, timeout=timeout)
        self.guild = guild

        self.add_item(ResumeBackToSystemButton(user_id, guild, row=1))

    @button(label="🔄 重新整理", style=discord.ButtonStyle.secondary, row=0)
    async def refresh_status(self, interaction: discord.Interaction, button: Button):
        """重新整理系統狀態"""
        await SafeInteractionHandler.safe_defer(interaction, ephemeral=True)
        panel = SystemAdminPanel(self.user_id)
        embed = await panel._create_system_status_embed(interaction)
        await interaction.edit_original_response(embed=embed, view=self)


class WhitelistSettingsView(View):
    """入境審核設定選單"""

    def __init__(self, user_id: int, guild: discord.Guild, timeout=300):
        super().__init__(timeout=timeout)
        self.user_id = user_id
        self.guild = guild
        self.service = WhitelistService(WhitelistDAO())

        # 頻道選單各佔一行，避免寬度限制
        self.add_item(WhitelistChannelSelect("panel_channel_id", "選擇申請面板頻道", self, row=0))
        self.add_item(WhitelistChannelSelect("review_channel_id", "選擇審核頻道", self, row=1))
        self.add_item(WhitelistChannelSelect("result_channel_id", "選擇結果公告頻道", self, row=2))

        # 角色設定改為子面板
        self.add_item(OpenRoleSettingsButton(self.user_id, self.guild, self.service, row=3))

        self.add_item(CloseWhitelistSettingsButton(row=4))

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("❌ 只有開啟此面板的管理員可設定", ephemeral=True)
            return False
        return True

    async def _build_payload(self) -> dict:
        """取得現有設定，避免覆蓋其他欄位"""
        current = await self.service.load_settings(self.guild.id)
        return {
            "panel_channel_id": current.panel_channel_id,
            "review_channel_id": current.review_channel_id,
            "result_channel_id": current.result_channel_id,
            "role_newcomer_ids": current.role_newcomer_ids,
            "role_citizen_id": current.role_citizen_id,
            "role_staff_id": current.role_staff_id,
            "nickname_role_id": current.nickname_role_id,
            "nickname_prefix": current.nickname_prefix,
            "panel_message_id": current.panel_message_id,
        }

    async def save_and_refresh(self, interaction: discord.Interaction, **patch):
        payload = await self._build_payload()
        payload.update(patch)
        settings = await self.service.save_settings(self.guild.id, **payload)

        # 重新載入摘要並更新訊息
        panel = SystemAdminPanel(self.user_id)
        embed = await panel._create_whitelist_settings_embed(self.guild, settings=settings)
        view = WhitelistSettingsView(self.user_id, self.guild)
        await interaction.response.edit_message(embed=embed, view=view)


class WhitelistChannelSelect(ChannelSelect):
    """通用頻道選擇器"""

    def __init__(
        self,
        field_key: str,
        placeholder: str,
        parent_view: WhitelistSettingsView,
        row: int | None = None,
    ):
        self.field_key = field_key
        self.parent_view = parent_view
        super().__init__(
            placeholder=placeholder,
            min_values=1,
            max_values=1,
            channel_types=[discord.ChannelType.text],
            row=row,
        )

    async def callback(self, interaction: discord.Interaction):
        channel = self.values[0]
        await self.parent_view.save_and_refresh(interaction, **{self.field_key: channel.id})


class WhitelistRoleSelect(RoleSelect):
    """通用身分組選擇器"""

    def __init__(
        self,
        field_key: str,
        placeholder: str,
        parent_view: WhitelistSettingsView,
        row: int | None = None,
        max_values: int = 1,
    ):
        self.field_key = field_key
        self.parent_view = parent_view
        super().__init__(
            placeholder=placeholder,
            min_values=1,
            max_values=max_values,
            row=row,
        )

    async def callback(self, interaction: discord.Interaction):
        if self.field_key == "role_newcomer_ids":
            role_ids = [role.id for role in self.values]
            await self.parent_view.save_and_refresh(interaction, **{"role_newcomer_ids": role_ids})
            return

        role = self.values[0]
        await self.parent_view.save_and_refresh(interaction, **{self.field_key: role.id})


class CloseWhitelistSettingsButton(Button):
    """關閉入境審核設定面板"""

    def __init__(self, row: int | None = None):
        super().__init__(label="❌ 關閉", style=discord.ButtonStyle.secondary, row=row)

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.edit_message(
            embed=discord.Embed(
                title="✅ 入境審核設定已關閉", description="已關閉設定面板", color=0x95A5A6
            ),
            view=None,
        )


class OpenRoleSettingsButton(Button):
    """開啟角色設定子面板"""

    def __init__(self, user_id: int, guild: discord.Guild, service: WhitelistService, row: int | None = None):
        super().__init__(label="👥 設定角色", style=discord.ButtonStyle.primary, row=row)
        self.user_id = user_id
        self.guild = guild
        self.service = service

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("❌ 只有開啟此面板的管理員可設定", ephemeral=True)
            return

        settings = await self.service.load_settings(self.guild.id)
        panel = SystemAdminPanel(self.user_id)
        embed = await panel._create_whitelist_settings_embed(self.guild, settings=settings)
        view = WhitelistRoleSettingsView(self.user_id, self.guild, self.service)
        await interaction.response.edit_message(embed=embed, view=view)


class WhitelistRoleSettingsView(View):
    """入境審核角色設定子面板"""

    def __init__(
        self,
        user_id: int,
        guild: discord.Guild,
        service: WhitelistService,
        timeout=300,
    ):
        super().__init__(timeout=timeout)
        self.user_id = user_id
        self.guild = guild
        self.service = service

        self.add_item(WhitelistRoleSelect("role_staff_id", "選擇審核員身分組", self, row=0))
        self.add_item(
            WhitelistRoleSelect(
                "role_newcomer_ids",
                "選擇新手身分組（可多選）",
                self,
                row=1,
                max_values=10,
            )
        )
        self.add_item(WhitelistRoleSelect("role_citizen_id", "選擇市民身分組", self, row=2))
        self.add_item(WhitelistRoleSelect("nickname_role_id", "選擇暱稱套用身分組", self, row=3))
        self.add_item(WhitelistPrefixButton(self.user_id, self.guild, self.service, row=4))
        self.add_item(BackToWhitelistButton(self.user_id, self.guild, self.service, row=4))

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("❌ 只有開啟此面板的管理員可設定", ephemeral=True)
            return False
        return True

    async def _build_payload(self) -> dict:
        current = await self.service.load_settings(self.guild.id)
        return {
            "panel_channel_id": current.panel_channel_id,
            "review_channel_id": current.review_channel_id,
            "result_channel_id": current.result_channel_id,
            "role_newcomer_ids": current.role_newcomer_ids,
            "role_citizen_id": current.role_citizen_id,
            "role_staff_id": current.role_staff_id,
            "nickname_role_id": current.nickname_role_id,
            "nickname_prefix": current.nickname_prefix,
            "panel_message_id": current.panel_message_id,
        }

    async def save_and_refresh(self, interaction: discord.Interaction, **patch):
        payload = await self._build_payload()
        payload.update(patch)
        settings = await self.service.save_settings(self.guild.id, **payload)

        panel = SystemAdminPanel(self.user_id)
        embed = await panel._create_whitelist_settings_embed(self.guild, settings=settings)
        view = WhitelistRoleSettingsView(self.user_id, self.guild, self.service)
        await interaction.response.edit_message(embed=embed, view=view)


class WhitelistPrefixModal(Modal):
    """設定暱稱前綴"""

    def __init__(self, service: WhitelistService, guild_id: int, current_prefix: str | None = None):
        super().__init__(title="設定暱稱前綴")
        self.service = service
        self.guild_id = guild_id

        self.prefix = TextInput(
            label="暱稱前綴（可留空清除）",
            max_length=32,
            required=False,
            default=(current_prefix or ""),
        )
        self.add_item(self.prefix)

    async def on_submit(self, interaction: discord.Interaction):
        current = await self.service.load_settings(self.guild_id)
        prefix = self.prefix.value.strip() if self.prefix.value else ""

        payload = {
            "panel_channel_id": current.panel_channel_id,
            "review_channel_id": current.review_channel_id,
            "result_channel_id": current.result_channel_id,
            "role_newcomer_ids": current.role_newcomer_ids,
            "role_citizen_id": current.role_citizen_id,
            "role_staff_id": current.role_staff_id,
            "nickname_role_id": current.nickname_role_id,
            "nickname_prefix": prefix or None,
            "panel_message_id": current.panel_message_id,
        }
        await self.service.save_settings(self.guild_id, **payload)
        await interaction.response.send_message("✅ 已更新暱稱前綴", ephemeral=True)


class WhitelistPrefixButton(Button):
    """開啟暱稱前綴設定"""

    def __init__(self, user_id: int, guild: discord.Guild, service: WhitelistService, row: int | None = None):
        super().__init__(label="🏷️ 設定前綴", style=discord.ButtonStyle.secondary, row=row)
        self.user_id = user_id
        self.guild = guild
        self.service = service

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("❌ 只有開啟此面板的管理員可設定", ephemeral=True)
            return
        settings = await self.service.load_settings(self.guild.id)
        await interaction.response.send_modal(
            WhitelistPrefixModal(self.service, self.guild.id, current_prefix=settings.nickname_prefix)
        )


class BackToWhitelistButton(Button):
    """返回主設定面板"""

    def __init__(self, user_id: int, guild: discord.Guild, service: WhitelistService, row: int | None = None):
        super().__init__(label="← 返回頻道設定", style=discord.ButtonStyle.secondary, row=row)
        self.user_id = user_id
        self.guild = guild
        self.service = service

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("❌ 只有開啟此面板的管理員可設定", ephemeral=True)
            return
        settings = await self.service.load_settings(self.guild.id)
        panel = SystemAdminPanel(self.user_id)
        embed = await panel._create_whitelist_settings_embed(self.guild, settings=settings)
        view = WhitelistSettingsView(self.user_id, self.guild)
        await interaction.response.edit_message(embed=embed, view=view)


class ResumeSettingsView(View):
    """履歷系統設定面板"""

    def __init__(
        self,
        user_id: int,
        guild: discord.Guild,
        bot: discord.Client,
        *,
        companies: list,
        selected_company_id: int | None = None,
        timeout=300,
    ):
        super().__init__(timeout=timeout)
        self.user_id = user_id
        self.guild = guild
        self.bot = bot
        self.dao = ResumeDAO()
        self.service = ResumeService(self.dao)
        self.panel_service = ResumePanelService(bot, self.dao)
        self.companies = companies or []
        self.selected_company_id = selected_company_id
        if self.selected_company_id is None and self.companies:
            self.selected_company_id = self.companies[0].company_id

        if self.companies:
            self.add_item(
                ResumeCompanySelect(self, self.companies, self.selected_company_id, row=0)
            )
            panel_channel_types = [
                discord.ChannelType.text,
                discord.ChannelType.public_thread,
                discord.ChannelType.private_thread,
                discord.ChannelType.news_thread,
            ]
            self.add_item(
                ResumeChannelSelect(
                    "panel_channel_id",
                    "選擇填單頻道",
                    self,
                    row=1,
                    channel_types=panel_channel_types,
                )
            )
            self.add_item(ResumeChannelSelect("review_channel_id", "選擇審核頻道", self, row=2))
            self.add_item(ResumeRoleSettingsButton(self, row=3))
            self.add_item(ResumeRenameCompanyButton(self, row=3))
            self.add_item(ResumeToggleCompanyButton(self, row=4))
            self.add_item(ResumeRefreshPanelButton(self, row=4))
            self.add_item(ResumeDeleteCompanyButton(self, row=4))

        self.add_item(ResumeCreateCompanyButton(self, row=4))
        self.add_item(ResumeBackToSystemButton(self.user_id, self.guild, row=4))

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("❌ 只有開啟此面板的管理員可設定", ephemeral=True)
            return False
        return True

    async def _get_selected_company(self):
        if not self.selected_company_id:
            return None
        return await self.service.load_company(self.selected_company_id)

    async def _deploy_panel(self, settings) -> bool:
        if not settings or not settings.panel_channel_id:
            return False
        panel_view = ResumePanelView(self.bot, self.dao, settings)
        message = await self.panel_service.ensure_panel_message(settings, panel_view)
        message_id = message.id if message else settings.panel_message_id
        if message_id:
            try:
                self.bot.add_view(panel_view, message_id=message_id)
            except Exception:
                pass
        return True

    async def refresh_message(
        self,
        interaction: discord.Interaction,
        *,
        selected_company_id: int | None = None,
        notice: str | None = None,
    ) -> None:
        companies = await self.service.list_companies(self.guild.id)
        next_selected = selected_company_id
        if next_selected is None and companies:
            next_selected = self.selected_company_id or companies[0].company_id

        panel = SystemAdminPanel(self.user_id)
        embed = await panel._create_resume_settings_embed(
            self.guild, companies, selected_company_id=next_selected
        )
        view = ResumeSettingsView(
            self.user_id,
            self.guild,
            self.bot,
            companies=companies,
            selected_company_id=next_selected,
        )

        try:
            if interaction.message:
                await interaction.response.edit_message(embed=embed, view=view)
                return
        except Exception:
            pass

        if notice is None:
            notice = "✅ 設定已更新，請重新開啟面板查看最新內容"
        await SafeInteractionHandler.safe_respond(interaction, content=notice, ephemeral=True)

    async def save_and_refresh(self, interaction: discord.Interaction, **patch):
        settings = await self._get_selected_company()
        if not settings:
            await interaction.response.send_message("❌ 尚未選擇公司", ephemeral=True)
            return

        updated = await self.service.save_company(self.guild.id, settings.company_name, **patch)

        if "panel_channel_id" in patch:
            await self._deploy_panel(updated)

        await self.refresh_message(interaction, selected_company_id=updated.company_id)

    async def refresh_panel(self, interaction: discord.Interaction):
        settings = await self._get_selected_company()
        if not settings:
            await interaction.response.send_message("❌ 尚未選擇公司", ephemeral=True)
            return
        if not settings.panel_channel_id:
            await interaction.response.send_message("❌ 尚未設定填單頻道", ephemeral=True)
            return

        await self._deploy_panel(settings)
        await self.refresh_message(interaction, selected_company_id=settings.company_id)

    async def toggle_company(self, interaction: discord.Interaction):
        settings = await self._get_selected_company()
        if not settings:
            await interaction.response.send_message("❌ 尚未選擇公司", ephemeral=True)
            return
        await self.save_and_refresh(interaction, is_enabled=not settings.is_enabled)

    async def rename_company(self, interaction: discord.Interaction, new_name: str) -> None:
        settings = await self._get_selected_company()
        if not settings:
            await interaction.response.send_message("❌ 尚未選擇公司", ephemeral=True)
            return

        trimmed = new_name.strip() if new_name else ""
        if not trimmed:
            await interaction.response.send_message("❌ 請輸入公司名稱", ephemeral=True)
            return
        if trimmed == settings.company_name:
            await interaction.response.send_message("⚠️ 公司名稱未變更", ephemeral=True)
            return

        try:
            updated = await self.service.rename_company(
                self.guild.id, settings.company_id, trimmed
            )
        except ValueError:
            await interaction.response.send_message("❌ 公司已存在", ephemeral=True)
            return
        except Exception as e:
            logger.error(f"公司更名失敗: {e}")
            await interaction.response.send_message("❌ 公司更名失敗", ephemeral=True)
            return

        if updated.panel_channel_id:
            await self._deploy_panel(updated)

        await self.refresh_message(
            interaction,
            selected_company_id=updated.company_id,
            notice="✅ 已更名公司，請重新開啟面板查看",
        )

    async def _cleanup_panel_message(self, settings) -> None:
        if not settings.panel_channel_id or not settings.panel_message_id:
            return

        guild = self.bot.get_guild(settings.guild_id)
        if not guild:
            return

        if hasattr(guild, "get_channel_or_thread"):
            channel = guild.get_channel_or_thread(settings.panel_channel_id)
        else:
            channel = guild.get_channel(settings.panel_channel_id) or guild.get_thread(
                settings.panel_channel_id
            )
        if not channel or not isinstance(channel, (discord.TextChannel, discord.Thread)):
            return

        try:
            message = await channel.fetch_message(settings.panel_message_id)
        except Exception:
            return

        try:
            await message.delete()
        except Exception as e:
            logger.warning(f"刪除履歷面板訊息失敗: {e}")

    async def delete_company(self, interaction: discord.Interaction, *, settings=None) -> None:
        target = settings or await self._get_selected_company()
        if not target:
            await interaction.response.send_message("❌ 尚未選擇公司", ephemeral=True)
            return

        await self._cleanup_panel_message(target)
        removed = await self.service.delete_company(self.guild.id, target.company_id)
        if not removed:
            await interaction.response.send_message("❌ 移除公司失敗", ephemeral=True)
            return

        companies = await self.service.list_companies(self.guild.id)
        next_selected = companies[0].company_id if companies else None
        await self.refresh_message(
            interaction,
            selected_company_id=next_selected,
            notice="✅ 已移除公司",
        )


class ResumeRoleSettingsView(View):
    """履歷身分組設定子面板"""

    def __init__(
        self,
        user_id: int,
        guild: discord.Guild,
        bot: discord.Client,
        *,
        selected_company_id: int | None = None,
        timeout=300,
    ):
        super().__init__(timeout=timeout)
        self.user_id = user_id
        self.guild = guild
        self.bot = bot
        self.dao = ResumeDAO()
        self.service = ResumeService(self.dao)
        self.selected_company_id = selected_company_id

        self.add_item(ResumeReviewRoleSelect(self, row=0))
        self.add_item(ResumeApprovedRoleSelect(self, row=1))
        self.add_item(ResumeManageableRoleSelect(self, row=2))
        self.add_item(ResumeClearReviewRolesButton(self, row=3))
        self.add_item(ResumeClearApprovedRolesButton(self, row=3))
        self.add_item(ResumeClearManageableRolesButton(self, row=3))
        self.add_item(ResumeBackToResumeSettingsButton(self, row=3))

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("❌ 只有開啟此面板的管理員可設定", ephemeral=True)
            return False
        return True

    async def _get_selected_company(self):
        if not self.selected_company_id:
            return None
        return await self.service.load_company(self.selected_company_id)

    async def refresh_message(
        self,
        interaction: discord.Interaction,
        *,
        selected_company_id: int | None = None,
        notice: str | None = None,
    ) -> None:
        companies = await self.service.list_companies(self.guild.id)
        next_selected = selected_company_id or self.selected_company_id
        if next_selected is None and companies:
            next_selected = companies[0].company_id

        panel = SystemAdminPanel(self.user_id)
        embed = await panel._create_resume_settings_embed(
            self.guild, companies, selected_company_id=next_selected
        )
        view = ResumeRoleSettingsView(
            self.user_id,
            self.guild,
            self.bot,
            selected_company_id=next_selected,
        )

        try:
            if interaction.message:
                await interaction.response.edit_message(embed=embed, view=view)
                return
        except Exception:
            pass

        if notice is None:
            notice = "✅ 設定已更新，請重新開啟面板查看最新內容"
        await SafeInteractionHandler.safe_respond(interaction, content=notice, ephemeral=True)

    async def save_and_refresh(self, interaction: discord.Interaction, **patch):
        settings = await self._get_selected_company()
        if not settings:
            await interaction.response.send_message("❌ 尚未選擇公司", ephemeral=True)
            return

        await self.service.save_company(self.guild.id, settings.company_name, **patch)
        await self.refresh_message(interaction, selected_company_id=settings.company_id)

    async def clear_review_roles(self, interaction: discord.Interaction):
        await self.save_and_refresh(interaction, review_role_ids=[])

    async def clear_approved_roles(self, interaction: discord.Interaction):
        await self.save_and_refresh(interaction, approved_role_ids=[])

    async def clear_manageable_roles(self, interaction: discord.Interaction):
        await self.save_and_refresh(interaction, manageable_role_ids=[])

    async def back_to_settings(self, interaction: discord.Interaction):
        companies = await self.service.list_companies(self.guild.id)
        next_selected = self.selected_company_id
        if next_selected is None and companies:
            next_selected = companies[0].company_id

        panel = SystemAdminPanel(self.user_id)
        embed = await panel._create_resume_settings_embed(
            self.guild, companies, selected_company_id=next_selected
        )
        view = ResumeSettingsView(
            self.user_id,
            self.guild,
            self.bot,
            companies=companies,
            selected_company_id=next_selected,
        )
        await interaction.response.edit_message(embed=embed, view=view)


class ResumeCompanySelect(Select):
    """公司選擇下拉"""

    def __init__(self, parent_view: ResumeSettingsView, companies: list, selected_company_id: int | None, row: int | None = None):
        self.parent_view = parent_view
        options = []
        for company in companies[:25]:
            status = "啟用" if company.is_enabled else "停用"
            options.append(
                discord.SelectOption(
                    label=company.company_name,
                    value=str(company.company_id),
                    description=f"狀態: {status}",
                    default=(company.company_id == selected_company_id),
                )
            )
        super().__init__(
            placeholder="選擇公司",
            min_values=1,
            max_values=1,
            options=options,
            row=row,
        )

    async def callback(self, interaction: discord.Interaction):
        selected_id = int(self.values[0])
        await self.parent_view.refresh_message(interaction, selected_company_id=selected_id)


class ResumeChannelSelect(ChannelSelect):
    """履歷頻道選擇器"""

    def __init__(
        self,
        field_key: str,
        placeholder: str,
        parent_view: ResumeSettingsView,
        row: int | None = None,
        channel_types: list[discord.ChannelType] | None = None,
    ):
        self.field_key = field_key
        self.parent_view = parent_view
        if not channel_types:
            channel_types = [discord.ChannelType.text]
        super().__init__(
            placeholder=placeholder,
            min_values=1,
            max_values=1,
            channel_types=channel_types,
            row=row,
        )

    async def callback(self, interaction: discord.Interaction):
        channel = self.values[0]
        await self.parent_view.save_and_refresh(interaction, **{self.field_key: channel.id})


class ResumeReviewRoleSelect(discord.ui.RoleSelect):
    """履歷審核角色選擇"""

    def __init__(self, parent_view, row: int | None = None):
        self.parent_view = parent_view
        super().__init__(
            placeholder="選擇審核身分組（可多選）",
            min_values=1,
            max_values=10,
            row=row,
        )

    async def callback(self, interaction: discord.Interaction):
        role_ids = [role.id for role in self.values]
        await self.parent_view.save_and_refresh(interaction, review_role_ids=role_ids)


class ResumeApprovedRoleSelect(discord.ui.RoleSelect):
    """履歷通過身分組選擇"""

    def __init__(self, parent_view, row: int | None = None):
        self.parent_view = parent_view
        super().__init__(
            placeholder="選擇通過身分組（可多選）",
            min_values=1,
            max_values=10,
            row=row,
        )

    async def callback(self, interaction: discord.Interaction):
        role_ids = [role.id for role in self.values]
        await self.parent_view.save_and_refresh(interaction, approved_role_ids=role_ids)


class ResumeManageableRoleSelect(discord.ui.RoleSelect):
    """履歷可管理身分組選擇"""

    def __init__(self, parent_view, row: int | None = None):
        self.parent_view = parent_view
        super().__init__(
            placeholder="選擇可管理身分組（可多選）",
            min_values=1,
            max_values=20,
            row=row,
        )

    async def callback(self, interaction: discord.Interaction):
        role_ids = [role.id for role in self.values]
        await self.parent_view.save_and_refresh(
            interaction, manageable_role_ids=role_ids
        )


class ResumeCompanyCreateModal(Modal):
    """新增履歷公司"""

    def __init__(self, parent_view: ResumeSettingsView):
        super().__init__(title="新增履歷公司")
        self.parent_view = parent_view

        self.company_name = TextInput(
            label="公司名稱",
            placeholder="例如：星際物流",
            max_length=100,
            required=True,
        )
        self.add_item(self.company_name)

    async def on_submit(self, interaction: discord.Interaction):
        name = self.company_name.value.strip() if self.company_name.value else ""
        if not name:
            await interaction.response.send_message("❌ 請輸入公司名稱", ephemeral=True)
            return

        existing = await self.parent_view.service.load_company_by_name(
            self.parent_view.guild.id, name
        )
        if existing:
            await interaction.response.send_message("❌ 公司已存在", ephemeral=True)
            return

        settings = await self.parent_view.service.save_company(self.parent_view.guild.id, name)
        await self.parent_view.refresh_message(
            interaction,
            selected_company_id=settings.company_id,
            notice="✅ 已新增公司，請重新開啟面板查看",
        )


class ResumeCompanyRenameModal(Modal):
    """更名履歷公司"""

    def __init__(self, parent_view: ResumeSettingsView, current_name: str):
        super().__init__(title="更名履歷公司")
        self.parent_view = parent_view

        self.company_name = TextInput(
            label="新公司名稱",
            placeholder=current_name,
            max_length=100,
            required=True,
        )
        self.add_item(self.company_name)

    async def on_submit(self, interaction: discord.Interaction):
        await self.parent_view.rename_company(interaction, self.company_name.value)


class ResumeCreateCompanyButton(Button):
    """新增公司按鈕"""

    def __init__(self, parent_view: ResumeSettingsView, row: int | None = None):
        super().__init__(label="➕ 新增公司", style=discord.ButtonStyle.success, row=row)
        self.parent_view = parent_view

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.send_modal(ResumeCompanyCreateModal(self.parent_view))


class ResumeRenameCompanyButton(Button):
    """更名公司按鈕"""

    def __init__(self, parent_view: ResumeSettingsView, row: int | None = None):
        super().__init__(label="✏️ 更名公司", style=discord.ButtonStyle.secondary, row=row)
        self.parent_view = parent_view

    async def callback(self, interaction: discord.Interaction):
        settings = await self.parent_view._get_selected_company()
        if not settings:
            await interaction.response.send_message("❌ 尚未選擇公司", ephemeral=True)
            return
        await interaction.response.send_modal(
            ResumeCompanyRenameModal(self.parent_view, settings.company_name)
        )


class ResumeToggleCompanyButton(Button):
    """切換公司啟用狀態"""

    def __init__(self, parent_view: ResumeSettingsView, row: int | None = None):
        super().__init__(label="🔄 切換啟用", style=discord.ButtonStyle.secondary, row=row)
        self.parent_view = parent_view

    async def callback(self, interaction: discord.Interaction):
        await self.parent_view.toggle_company(interaction)


class ResumeRefreshPanelButton(Button):
    """部署或刷新面板"""

    def __init__(self, parent_view: ResumeSettingsView, row: int | None = None):
        super().__init__(label="📌 部署面板", style=discord.ButtonStyle.primary, row=row)
        self.parent_view = parent_view

    async def callback(self, interaction: discord.Interaction):
        await self.parent_view.refresh_panel(interaction)


class ResumeCompanyDeleteConfirmView(View):
    """履歷公司移除確認"""

    def __init__(self, parent_view: ResumeSettingsView, settings, application_count: int):
        super().__init__(timeout=60)
        self.parent_view = parent_view
        self.settings = settings
        self.application_count = application_count
        self.user_id = parent_view.user_id

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.user_id:
            await interaction.response.send_message(
                "❌ 只有開啟此面板的管理員可設定", ephemeral=True
            )
            return False
        return True

    @button(label="🗑️ 確認移除", style=discord.ButtonStyle.danger)
    async def confirm_button(self, interaction: discord.Interaction, button: Button):
        await self.parent_view.delete_company(interaction, settings=self.settings)

    @button(label="❌ 取消", style=discord.ButtonStyle.secondary)
    async def cancel_button(self, interaction: discord.Interaction, button: Button):
        await self.parent_view.refresh_message(
            interaction, selected_company_id=self.settings.company_id
        )


class ResumeDeleteCompanyButton(Button):
    """移除公司按鈕"""

    def __init__(self, parent_view: ResumeSettingsView, row: int | None = None):
        super().__init__(label="🗑️ 移除公司", style=discord.ButtonStyle.danger, row=row)
        self.parent_view = parent_view

    async def callback(self, interaction: discord.Interaction):
        settings = await self.parent_view._get_selected_company()
        if not settings:
            await interaction.response.send_message("❌ 尚未選擇公司", ephemeral=True)
            return

        try:
            application_count = await self.parent_view.dao.count_applications_by_company(
                settings.company_id
            )
        except Exception as e:
            logger.error(f"讀取履歷申請數量失敗: {e}")
            application_count = 0

        embed = discord.Embed(
            title="⚠️ 確認移除公司",
            description=(
                f"公司：{settings.company_name}\n"
                "此操作將刪除公司設定與所有履歷申請資料，無法復原。"
            ),
            color=0xE74C3C,
        )
        embed.add_field(
            name="影響資料",
            value=f"履歷申請：{application_count} 筆",
            inline=False,
        )

        view = ResumeCompanyDeleteConfirmView(self.parent_view, settings, application_count)
        await interaction.response.edit_message(embed=embed, view=view)


class ResumeRoleSettingsButton(Button):
    """開啟履歷身分組設定"""

    def __init__(self, parent_view: ResumeSettingsView, row: int | None = None):
        super().__init__(label="🛡️ 身分組設定", style=discord.ButtonStyle.secondary, row=row)
        self.parent_view = parent_view

    async def callback(self, interaction: discord.Interaction):
        settings = await self.parent_view._get_selected_company()
        if not settings:
            await interaction.response.send_message("❌ 尚未選擇公司", ephemeral=True)
            return

        companies = await self.parent_view.service.list_companies(self.parent_view.guild.id)
        panel = SystemAdminPanel(self.parent_view.user_id)
        embed = await panel._create_resume_settings_embed(
            self.parent_view.guild,
            companies,
            selected_company_id=settings.company_id,
        )
        view = ResumeRoleSettingsView(
            self.parent_view.user_id,
            self.parent_view.guild,
            self.parent_view.bot,
            selected_company_id=settings.company_id,
        )
        await interaction.response.edit_message(embed=embed, view=view)


class ResumeClearReviewRolesButton(Button):
    """清空審核身分組"""

    def __init__(self, parent_view, row: int | None = None):
        super().__init__(label="🧹 清空審核身分組", style=discord.ButtonStyle.secondary, row=row)
        self.parent_view = parent_view

    async def callback(self, interaction: discord.Interaction):
        await self.parent_view.clear_review_roles(interaction)


class ResumeClearApprovedRolesButton(Button):
    """清空通過身分組"""

    def __init__(self, parent_view, row: int | None = None):
        super().__init__(label="🧹 清空通過身分組", style=discord.ButtonStyle.secondary, row=row)
        self.parent_view = parent_view

    async def callback(self, interaction: discord.Interaction):
        await self.parent_view.clear_approved_roles(interaction)


class ResumeClearManageableRolesButton(Button):
    """清空可管理身分組"""

    def __init__(self, parent_view, row: int | None = None):
        super().__init__(label="🧹 清空可管理身分組", style=discord.ButtonStyle.secondary, row=row)
        self.parent_view = parent_view

    async def callback(self, interaction: discord.Interaction):
        await self.parent_view.clear_manageable_roles(interaction)


class ResumeBackToResumeSettingsButton(Button):
    """返回履歷設定面板"""

    def __init__(self, parent_view, row: int | None = None):
        super().__init__(label="← 返回履歷設定", style=discord.ButtonStyle.secondary, row=row)
        self.parent_view = parent_view

    async def callback(self, interaction: discord.Interaction):
        await self.parent_view.back_to_settings(interaction)


class ResumeBackToSystemButton(Button):
    """返回系統管理面板"""

    def __init__(self, user_id: int, guild: discord.Guild, row: int | None = None):
        super().__init__(label="← 返回管理面板", style=discord.ButtonStyle.secondary, row=row)
        self.user_id = user_id
        self.guild = guild

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("❌ 只有開啟此面板的管理員可設定", ephemeral=True)
            return

        embed = discord.Embed(
            title="🔧 系統管理面板",
            description="選擇要執行的管理操作",
            color=0x3498DB,
        )
        embed.add_field(
            name="📊 功能模組",
            value="• 🎫 票券系統設定\n• 🎉 歡迎系統設定\n• 🗳️ 投票系統設定\n• 🛂 入境審核設定\n• 🧾 履歷系統設定\n• 📊 系統狀態\n• 🔧 系統工具\n• 🗂️ 類別自動建立",
            inline=False,
        )
        embed.add_field(
            name="💡 使用說明",
            value="點擊下方按鈕進入相應的設定頁面",
            inline=False,
        )

        view = SystemAdminPanel(user_id=self.user_id)
        await interaction.response.edit_message(embed=embed, view=view)


class TicketSettingsView(View):
    """票券系統設定界面"""

    def __init__(self, user_id: int, timeout=300):
        super().__init__(timeout=timeout)
        self.user_id = user_id
        self.ticket_dao = TicketDAO()

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        return interaction.user.id == self.user_id

    @button(label="📂 設定票券分類", style=discord.ButtonStyle.primary, row=0)
    async def set_category_button(self, interaction: discord.Interaction, button: Button):
        """設定票券分類頻道"""
        embed = discord.Embed(
            title="📂 選擇票券分類頻道",
            description="請選擇要用作票券分類的頻道",
            color=0x3498DB,
        )

        view = ChannelSelectView(self.user_id, "ticket_category")
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    @button(label="👥 設定客服角色", style=discord.ButtonStyle.secondary, row=0)
    async def set_support_roles_button(self, interaction: discord.Interaction, button: Button):
        """設定客服角色"""
        embed = discord.Embed(
            title="👥 選擇客服角色",
            description="請選擇要設定為客服的角色",
            color=0x3498DB,
        )

        view = RoleSelectView(self.user_id, "support_roles")
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    @button(label="💖 贊助處理角色", style=discord.ButtonStyle.secondary, row=0)
    async def set_sponsor_support_roles_button(
        self, interaction: discord.Interaction, button: Button
    ):
        """設定贊助處理角色"""
        embed = discord.Embed(
            title="💖 選擇贊助處理角色",
            description="請選擇要設定為贊助處理的角色",
            color=0x3498DB,
        )

        view = RoleSelectView(self.user_id, "sponsor_support_roles")
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    @button(label="⚙️ 系統參數", style=discord.ButtonStyle.secondary, row=0)
    async def system_params_button(self, interaction: discord.Interaction, button: Button):
        """系統參數設定"""
        modal = TicketSettingsModal()
        await interaction.response.send_modal(modal)

    @button(label="📝 票券面板訊息", style=discord.ButtonStyle.success, row=1)
    async def ticket_panel_messages_button(self, interaction: discord.Interaction, button: Button):
        """設定票券面板顯示的訊息"""
        modal = TicketMessageModal()
        await interaction.response.send_modal(modal)

    @button(label="🔄 重新整理", style=discord.ButtonStyle.secondary, row=1)
    async def refresh_button(self, interaction: discord.Interaction, button: Button):
        """重新整理設定狀態"""
        embed = await self._update_ticket_settings_embed(interaction.guild)
        await interaction.response.edit_message(embed=embed, view=self)

    async def _update_ticket_settings_embed(self, guild: discord.Guild) -> discord.Embed:
        """更新票券設定嵌入"""
        settings = await self.ticket_dao.get_settings(guild.id)

        embed = discord.Embed(
            title="🎫 票券系統設定",
            description="當前票券系統配置狀態",
            color=0x3498DB,
        )

        # 基本設定狀態
        category_text = (
            f"<#{settings['category_id']}>" if settings.get("category_id") else "❌ 未設定"
        )
        embed.add_field(name="📂 票券分類", value=category_text, inline=True)

        support_roles = settings.get("support_roles", [])
        roles_text = f"✅ {len(support_roles)} 個角色" if support_roles else "❌ 未設定"
        embed.add_field(name="👥 客服角色", value=roles_text, inline=True)

        sponsor_roles = settings.get("sponsor_support_roles", [])
        sponsor_text = (
            f"✅ {len(sponsor_roles)} 個角色" if sponsor_roles else "❌ 未設定（沿用客服）"
        )
        embed.add_field(name="💖 贊助處理角色", value=sponsor_text, inline=True)

        embed.add_field(
            name="⚙️ 系統參數",
            value=f"票券上限: {settings.get('max_tickets_per_user', 3)}\n"
            f"自動關閉: {settings.get('auto_close_hours', 24)}小時",
            inline=True,
        )

        return embed


class WelcomeSettingsView(View):
    """歡迎系統設定界面"""

    def __init__(self, user_id: int, timeout=300):
        super().__init__(timeout=timeout)
        self.user_id = user_id
        self.welcome_dao = WelcomeDAO()
        self.welcome_manager = WelcomeManager(self.welcome_dao)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        return interaction.user.id == self.user_id

    @button(label="🚀 初始化系統", style=discord.ButtonStyle.success, row=0)
    async def init_system_button(self, interaction: discord.Interaction, button: Button):
        """初始化歡迎系統"""
        default_settings = {
            "is_enabled": True,
            "welcome_embed_enabled": True,
            "welcome_dm_enabled": False,
            "auto_role_enabled": False,
            "welcome_color": 0x2ECC71,
        }

        success, message = await self.welcome_manager.update_welcome_settings(
            interaction.guild.id, **default_settings
        )

        if success:
            embed = discord.Embed(
                title="✅ 歡迎系統初始化完成",
                description="系統已成功初始化，現在可以進行詳細設定",
                color=0x2ECC71,
            )
        else:
            embed = discord.Embed(
                title="❌ 初始化失敗",
                description=f"初始化過程中發生錯誤：{message}",
                color=0xE74C3C,
            )

        await interaction.response.send_message(embed=embed, ephemeral=True)

    @button(label="📺 設定頻道", style=discord.ButtonStyle.primary, row=0)
    async def set_channels_button(self, interaction: discord.Interaction, button: Button):
        """設定歡迎和離開頻道"""
        embed = discord.Embed(
            title="📺 頻道設定",
            description="選擇歡迎和離開訊息的頻道",
            color=0x3498DB,
        )

        view = WelcomeChannelSelectView(self.user_id)
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    @button(label="👥 自動身分組", style=discord.ButtonStyle.secondary, row=0)
    async def auto_roles_button(self, interaction: discord.Interaction, button: Button):
        """設定自動身分組"""
        embed = discord.Embed(
            title="👥 自動身分組設定",
            description="設定新成員自動獲得的身分組",
            color=0x3498DB,
        )

        view = RoleSelectView(self.user_id, "auto_roles")
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    @button(label="📝 自定義訊息", style=discord.ButtonStyle.success, row=1)
    async def custom_messages_button(self, interaction: discord.Interaction, button: Button):
        """自定義歡迎訊息"""
        modal = WelcomeMessageModal()
        await interaction.response.send_modal(modal)

    @button(label="🔧 功能開關", style=discord.ButtonStyle.secondary, row=1)
    async def feature_toggles_button(self, interaction: discord.Interaction, button: Button):
        """功能開關設定"""
        view = WelcomeFeatureToggleView(self.user_id)
        embed = discord.Embed(
            title="🔧 歡迎系統功能開關",
            description="啟用或停用各項功能",
            color=0x95A5A6,
        )
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)


class ChannelSelectView(View):
    """頻道選擇界面"""

    def __init__(self, user_id: int, setting_type: str, timeout=300):
        super().__init__(timeout=timeout)
        self.user_id = user_id
        self.setting_type = setting_type
        self.add_item(ChannelSelect(setting_type))

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        return interaction.user.id == self.user_id


class ChannelSelect(discord.ui.ChannelSelect):
    """頻道選擇下拉選單"""

    def __init__(self, setting_type: str):
        self.setting_type = setting_type

        # 根據設定類型決定顯示的頻道類型
        if setting_type == "ticket_category":
            channel_types = [discord.ChannelType.category]
            placeholder = "選擇票券分類頻道..."
        else:  # welcome_channel, leave_channel 等文字頻道
            channel_types = [discord.ChannelType.text]
            placeholder = "選擇文字頻道..."

        super().__init__(
            placeholder=placeholder,
            channel_types=channel_types,
            min_values=1,
            max_values=1,
        )

    async def callback(self, interaction: discord.Interaction):
        channel = self.values[0]

        try:
            if self.setting_type == "ticket_category":

                ticket_dao = TicketDAO()
                success = await ticket_dao.update_settings(
                    interaction.guild.id, {"category_id": channel.id}
                )

                if success:
                    embed = discord.Embed(
                        title="✅ 票券分類已設定",
                        description=f"票券分類頻道已設定為：**{channel.name}**\n"
                        f"新的票券將在此分類下建立專屬頻道",
                        color=0x2ECC71,
                    )
                    embed.add_field(
                        name="📋 說明",
                        value="• 票券將自動在此分類下建立頻道\n"
                        "• 頻道名稱格式：`ticket-用戶名-編號`\n"
                        "• 確保Bot有管理此分類的權限",
                        inline=False,
                    )
                else:
                    embed = discord.Embed(
                        title="❌ 設定失敗",
                        description="設定票券分類時發生錯誤，請確認Bot有足夠權限",
                        color=0xE74C3C,
                    )

                await interaction.response.send_message(embed=embed, ephemeral=True)

            elif self.setting_type == "welcome_channel":

                welcome_manager = WelcomeManager()
                success, message = await welcome_manager.set_welcome_channel(
                    interaction.guild.id, channel.id
                )

                if success:
                    embed = discord.Embed(
                        title="✅ 歡迎頻道已設定",
                        description=message,
                        color=0x2ECC71,
                    )
                else:
                    embed = discord.Embed(
                        title="❌ 設定失敗",
                        description=message,
                        color=0xE74C3C,
                    )

                await interaction.response.send_message(embed=embed, ephemeral=True)

            elif self.setting_type == "leave_channel":

                welcome_manager = WelcomeManager()
                success, message = await welcome_manager.set_leave_channel(
                    interaction.guild.id, channel.id
                )

                if success:
                    embed = discord.Embed(
                        title="✅ 離開頻道已設定",
                        description=message,
                        color=0x2ECC71,
                    )
                else:
                    embed = discord.Embed(
                        title="❌ 設定失敗",
                        description=message,
                        color=0xE74C3C,
                    )

                await interaction.response.send_message(embed=embed, ephemeral=True)

        except Exception as e:
            logger.error(f"頻道設定錯誤: {e}")
            await interaction.response.send_message("❌ 設定過程中發生錯誤", ephemeral=True)


class RoleSelectView(View):
    """角色選擇界面"""

    def __init__(self, user_id: int, setting_type: str, timeout=300):
        super().__init__(timeout=timeout)
        self.user_id = user_id
        self.setting_type = setting_type
        self.add_item(RoleSelect(setting_type))

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        return interaction.user.id == self.user_id


class RoleSelect(discord.ui.RoleSelect):
    """角色選擇下拉選單"""

    def __init__(self, setting_type: str):
        self.setting_type = setting_type
        super().__init__(placeholder="選擇角色...", min_values=1, max_values=10)  # 最多選擇10個角色

    # RoleSelect不需要手動填充選項，Discord會自動處理

    async def callback(self, interaction: discord.Interaction):
        selected_role_ids = [role.id for role in self.values]

        try:
            if self.setting_type == "support_roles":
                ticket_dao = TicketDAO()
                success = await ticket_dao.update_settings(
                    interaction.guild.id, {"support_roles": selected_role_ids}
                )

                role_mentions = [f"<@&{role_id}>" for role_id in selected_role_ids]

                if success:
                    embed = discord.Embed(
                        title="✅ 客服角色已設定",
                        description=f"客服角色已設定為：\n{', '.join(role_mentions)}",
                        color=0x2ECC71,
                    )
                else:
                    embed = discord.Embed(
                        title="❌ 設定失敗",
                        description="設定客服角色時發生錯誤",
                        color=0xE74C3C,
                    )

            elif self.setting_type == "sponsor_support_roles":
                ticket_dao = TicketDAO()
                success = await ticket_dao.update_settings(
                    interaction.guild.id, {"sponsor_support_roles": selected_role_ids}
                )

                role_mentions = [f"<@&{role_id}>" for role_id in selected_role_ids]

                if success:
                    embed = discord.Embed(
                        title="✅ 贊助處理角色已設定",
                        description=f"贊助處理角色已設定為：\n{', '.join(role_mentions)}",
                        color=0x2ECC71,
                    )
                else:
                    embed = discord.Embed(
                        title="❌ 設定失敗",
                        description="設定贊助處理角色時發生錯誤",
                        color=0xE74C3C,
                    )

            elif self.setting_type == "auto_roles":
                welcome_manager = WelcomeManager()
                success, message = await welcome_manager.set_auto_roles(
                    interaction.guild.id, selected_role_ids
                )

                if success:
                    embed = discord.Embed(
                        title="✅ 自動身分組已設定",
                        description=message,
                        color=0x2ECC71,
                    )
                else:
                    embed = discord.Embed(
                        title="❌ 設定失敗",
                        description=message,
                        color=0xE74C3C,
                    )

            await interaction.response.send_message(embed=embed, ephemeral=True)

        except Exception as e:
            logger.error(f"角色設定錯誤: {e}")
            await interaction.response.send_message("❌ 設定過程中發生錯誤", ephemeral=True)


class WelcomeChannelSelectView(View):
    """歡迎頻道選擇界面"""

    def __init__(self, user_id: int, timeout=300):
        super().__init__(timeout=timeout)
        self.user_id = user_id

    @button(label="📢 設定歡迎頻道", style=discord.ButtonStyle.primary)
    async def welcome_channel_button(self, interaction: discord.Interaction, button: Button):
        view = ChannelSelectView(self.user_id, "welcome_channel")
        await interaction.response.send_message("請選擇歡迎頻道：", view=view, ephemeral=True)

    @button(label="👋 設定離開頻道", style=discord.ButtonStyle.secondary)
    async def leave_channel_button(self, interaction: discord.Interaction, button: Button):
        view = ChannelSelectView(self.user_id, "leave_channel")
        await interaction.response.send_message("請選擇離開頻道：", view=view, ephemeral=True)


class WelcomeFeatureToggleView(View):
    """歡迎功能開關界面"""

    def __init__(self, user_id: int, timeout=300):
        super().__init__(timeout=timeout)
        self.user_id = user_id
        self.welcome_manager = WelcomeManager()

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        return interaction.user.id == self.user_id

    @button(label="🔄 嵌入訊息", style=discord.ButtonStyle.secondary)
    async def toggle_embed_button(self, interaction: discord.Interaction, button: Button):
        """切換嵌入訊息功能"""
        settings = await self.welcome_manager.welcome_dao.get_welcome_settings(interaction.guild.id)
        current_state = settings.get("welcome_embed_enabled", True) if settings else True
        new_state = not current_state

        success, message = await self.welcome_manager.update_welcome_settings(
            interaction.guild.id, welcome_embed_enabled=new_state
        )

        if success:
            status = "啟用" if new_state else "停用"
            await interaction.response.send_message(f"✅ 嵌入訊息功能已{status}", ephemeral=True)
        else:
            await interaction.response.send_message(f"❌ 設定失敗：{message}", ephemeral=True)

    @button(label="💌 私訊歡迎", style=discord.ButtonStyle.secondary)
    async def toggle_dm_button(self, interaction: discord.Interaction, button: Button):
        """切換私訊歡迎功能"""
        settings = await self.welcome_manager.welcome_dao.get_welcome_settings(interaction.guild.id)
        current_state = settings.get("welcome_dm_enabled", False) if settings else False
        new_state = not current_state

        success, message = await self.welcome_manager.update_welcome_settings(
            interaction.guild.id, welcome_dm_enabled=new_state
        )

        if success:
            status = "啟用" if new_state else "停用"
            await interaction.response.send_message(f"✅ 私訊歡迎功能已{status}", ephemeral=True)
        else:
            await interaction.response.send_message(f"❌ 設定失敗：{message}", ephemeral=True)

    @button(label="👥 自動身分組", style=discord.ButtonStyle.secondary)
    async def toggle_auto_role_button(self, interaction: discord.Interaction, button: Button):
        """切換自動身分組功能"""
        settings = await self.welcome_manager.welcome_dao.get_welcome_settings(interaction.guild.id)
        current_state = settings.get("auto_role_enabled", False) if settings else False
        new_state = not current_state

        success, message = await self.welcome_manager.update_welcome_settings(
            interaction.guild.id, auto_role_enabled=new_state
        )

        if success:
            status = "啟用" if new_state else "停用"
            await interaction.response.send_message(f"✅ 自動身分組功能已{status}", ephemeral=True)
        else:
            await interaction.response.send_message(f"❌ 設定失敗：{message}", ephemeral=True)


class SystemToolsView(View):
    """系統工具界面"""

    def __init__(self, user_id: int, timeout=300):
        super().__init__(timeout=timeout)
        self.user_id = user_id

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        return interaction.user.id == self.user_id

    @button(label="🧹 清理資料", style=discord.ButtonStyle.secondary, row=0)
    async def cleanup_button(self, interaction: discord.Interaction, button: Button):
        """資料清理工具"""
        embed = discord.Embed(
            title="🧹 資料清理系統",
            description="選擇要執行的清理操作",
            color=0x95A5A6,
        )
        embed.add_field(
            name="🗑️ 基礎清理",
            value="• 清理舊日誌 (30天前)\n• 清理過期快取\n• 清理臨時資料",
            inline=True,
        )
        embed.add_field(
            name="🔧 深度清理",
            value="• 資料庫優化\n• 索引重建\n• 完整清理",
            inline=True,
        )
        view = DataCleanupView(self.user_id)
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    @button(label="💬 自動回覆", style=discord.ButtonStyle.primary, row=0)
    async def auto_reply_button(self, interaction: discord.Interaction, button: Button):
        """自動回覆設定"""
        view = AutoReplySettingsView(self.user_id, interaction.guild)
        embed = await view.build_embed()
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
        try:
            view.message = await interaction.original_response()
        except Exception:
            pass

    @button(label="🗳️ 投票管理面板", style=discord.ButtonStyle.primary, row=0)
    async def vote_panel_button(self, interaction: discord.Interaction, button: Button):
        """投票管理面板"""
        from potato_bot.views.vote_views import VoteManagementView

        embed = discord.Embed(
            title="🗳️ 投票系統管理面板",
            description="使用現代化GUI界面管理投票系統",
            color=0x3498DB,
        )
        embed.add_field(
            name="🎯 主要功能",
            value="• 🗳️ 創建新投票\n• ⚙️ 管理現有投票\n• 📊 查看投票統計",
            inline=False,
        )
        embed.add_field(
            name="💡 使用說明",
            value="點擊下方按鈕開始使用投票系統",
            inline=False,
        )
        view = VoteManagementView()
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    @button(label="🎲 抽獎管理面板", style=discord.ButtonStyle.primary, row=0)
    async def lottery_panel_button(self, interaction: discord.Interaction, button: Button):
        """抽獎管理面板"""
        from potato_bot.views.lottery_views import LotteryManagementView

        embed = discord.Embed(
            title="🎲 抽獎系統管理面板",
            description="使用圖形化界面管理抽獎系統",
            color=0x3498DB,
        )
        embed.add_field(
            name="🎯 主要功能",
            value="• 🎲 創建新抽獎\n• 📋 管理活動抽獎\n• 📊 查看抽獎統計",
            inline=False,
        )
        embed.add_field(
            name="💡 使用說明",
            value="點擊下方按鈕開始使用抽獎系統",
            inline=False,
        )

        view = LotteryManagementView()
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    @button(label="🎵 音樂管理面板", style=discord.ButtonStyle.primary, row=0)
    async def music_panel_button(self, interaction: discord.Interaction, button: Button):
        """音樂管理面板"""
        from potato_bot.views.music_views import MusicMenuView

        music_cog = interaction.client.get_cog("MusicCore")
        if not music_cog:
            await interaction.response.send_message(
                "❌ 音樂系統尚未載入，請稍後再試。", ephemeral=True
            )
            return

        embed = EmbedBuilder.create_info_embed(
            "🎵 音樂系統",
            "歡迎使用 Potato Bot 音樂系統！\n支援 YouTube 直接播放",
        )
        embed.add_field(
            name="🎯 主要功能",
            value="🎵 播放音樂\n🎛️ 控制面板\n📝 播放列表\n🔍 搜索音樂",
            inline=True,
        )
        embed.add_field(
            name="💡 使用提示",
            value="• 直接貼上 YouTube 網址\n• 輸入歌曲名稱搜索\n• 支援完整播放控制",
            inline=True,
        )

        view = MusicMenuView(music_cog)
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    @button(label="🗂️ 類別自動建立", style=discord.ButtonStyle.primary, row=1)
    async def category_auto_button(self, interaction: discord.Interaction, button: Button):
        """類別自動建立設定"""
        view = CategoryAutoSettingsView(self.user_id, interaction.guild)
        embed = await view.build_embed()
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    @button(label="🤖 狀態欄位設定", style=discord.ButtonStyle.secondary, row=1)
    async def presence_settings_button(self, interaction: discord.Interaction, button: Button):
        """Bot 狀態欄位設定"""
        view = PresenceSettingsView(self.user_id, interaction.guild)
        embed = await view.build_embed()
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    @button(label="🛡️ 管理面板授權", style=discord.ButtonStyle.secondary, row=1)
    async def admin_access_button(self, interaction: discord.Interaction, button: Button):
        """管理面板授權（僅限伺服器 Owner）"""
        if not (_is_guild_owner(interaction) or await interaction.client.is_owner(interaction.user)):
            await interaction.response.send_message("❌ 僅限伺服器 Owner 設定", ephemeral=True)
            return
        view = AdminAccessSettingsView(self.user_id, interaction.guild)
        embed = await view.build_embed()
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    @button(label="🗑️ 清空頻道", style=discord.ButtonStyle.danger, row=1)
    async def clear_channel_button(self, interaction: discord.Interaction, button: Button):
        """清空頻道訊息"""
        try:
            # 檢查用戶權限
            if not interaction.user.guild_permissions.manage_messages:
                await interaction.response.send_message(
                    "❌ 需要管理訊息權限才能使用此功能", ephemeral=True
                )
                return

            embed = discord.Embed(
                title="🗑️ 清空頻道訊息",
                description="選擇要清空的頻道和清空選項",
                color=0xE74C3C,
            )

            embed.add_field(
                name="⚠️ 警告",
                value="此操作將永久刪除頻道中的訊息，無法復原！\n請謹慎選擇要清空的頻道。",
                inline=False,
            )

            view = ChannelClearView(self.user_id)
            view.add_item(ChannelClearSelect(self.user_id, interaction.guild))
            await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

        except Exception as e:
            logger.error(f"清空頻道按鈕錯誤: {e}")
            try:
                if not interaction.response.is_done():
                    await interaction.response.send_message(
                        "❌ 開啟清空頻道面板時發生錯誤", ephemeral=True
                    )
                else:
                    await interaction.followup.send("❌ 開啟清空頻道面板時發生錯誤", ephemeral=True)
            except:
                pass


class PresenceSettingsView(View):
    """狀態欄位設定"""

    def __init__(self, user_id: int, guild: discord.Guild, timeout=300):
        super().__init__(timeout=timeout)
        self.user_id = user_id
        self.guild = guild
        self.service = SystemSettingsService()

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("❌ 只有開啟此面板的管理員可設定", ephemeral=True)
            return False
        if await _has_system_admin_access(interaction):
            return True
        await interaction.response.send_message("❌ 需要管理伺服器權限或已授權管理員", ephemeral=True)
        return False

    async def build_embed(self) -> discord.Embed:
        custom = await self.service.get_custom_settings(self.guild.id)
        messages = custom.get("presence_messages") or []
        interval = custom.get("presence_interval")
        if isinstance(messages, str):
            messages = [line.strip() for line in messages.splitlines() if line.strip()]
        if not isinstance(messages, list):
            messages = []

        interval_text = f"{interval} 秒" if interval else "預設 (30 秒)"
        if messages:
            lines = [f"• {line}" for line in messages[:10]]
            if len(messages) > 10:
                lines.append(f"... 其餘 {len(messages) - 10} 項")
            message_text = "\n".join(lines)
        else:
            message_text = "未設定（使用預設狀態）"

        embed = discord.Embed(
            title="🤖 狀態欄位設定",
            description="設定 Bot 狀態輪播內容與間隔",
            color=0x5865F2,
        )
        embed.add_field(name="輪播間隔", value=interval_text, inline=False)
        embed.add_field(name="輪播內容", value=message_text, inline=False)
        embed.add_field(name="提示", value="狀態更新時會優先顯示 FiveM 狀態", inline=False)
        return embed

    @button(label="✏️ 設定內容", style=discord.ButtonStyle.secondary, row=0)
    async def set_messages(self, interaction: discord.Interaction, button: Button):
        custom = await self.service.get_custom_settings(self.guild.id)
        messages = custom.get("presence_messages") or []
        if isinstance(messages, list):
            default = "\n".join(str(line) for line in messages)
        else:
            default = ""
        await interaction.response.send_modal(PresenceMessagesModal(self, default))

    @button(label="⏱️ 設定間隔", style=discord.ButtonStyle.secondary, row=0)
    async def set_interval(self, interaction: discord.Interaction, button: Button):
        custom = await self.service.get_custom_settings(self.guild.id)
        interval = custom.get("presence_interval")
        default = str(interval) if interval else ""
        await interaction.response.send_modal(PresenceIntervalModal(self, default))

    @button(label="🧹 清除設定", style=discord.ButtonStyle.secondary, row=1)
    async def clear_settings(self, interaction: discord.Interaction, button: Button):
        success = await self.service.update_custom_settings(
            self.guild.id,
            {"presence_messages": [], "presence_interval": None},
        )
        if success:
            manager = getattr(interaction.client, "presence_manager", None)
            if manager:
                await manager.refresh_settings(self.guild.id)
            embed = await self.build_embed()
            await interaction.response.edit_message(embed=embed, view=self)
        else:
            await interaction.response.send_message("❌ 清除失敗", ephemeral=True)

    @button(label="🔄 重新整理", style=discord.ButtonStyle.secondary, row=1)
    async def refresh_button(self, interaction: discord.Interaction, button: Button):
        embed = await self.build_embed()
        await interaction.response.edit_message(embed=embed, view=self)

    @button(label="❌ 關閉", style=discord.ButtonStyle.danger, row=1)
    async def close_button(self, interaction: discord.Interaction, button: Button):
        embed = discord.Embed(title="✅ 狀態欄位設定已關閉", color=0x95A5A6)
        await interaction.response.edit_message(embed=embed, view=None)


class PresenceMessagesModal(Modal):
    """設定狀態欄位內容"""

    def __init__(self, parent_view: PresenceSettingsView, default: str):
        super().__init__(title="設定狀態輪播內容")
        self.parent_view = parent_view
        self.messages = TextInput(
            label="狀態內容（一行一個）",
            placeholder="例如：\n歡迎來到福北市\n福北市城內人數 ...",
            default=default,
            style=discord.TextStyle.paragraph,
            required=False,
            max_length=600,
        )
        self.add_item(self.messages)

    async def on_submit(self, interaction: discord.Interaction):
        raw = self.messages.value.strip()
        lines = [line.strip() for line in raw.splitlines() if line.strip()]
        success = await self.parent_view.service.update_custom_settings(
            self.parent_view.guild.id,
            {"presence_messages": lines},
        )
        if success:
            manager = getattr(interaction.client, "presence_manager", None)
            if manager:
                await manager.refresh_settings(self.parent_view.guild.id)
            await interaction.response.send_message("✅ 已更新狀態內容", ephemeral=True)
        else:
            await interaction.response.send_message("❌ 更新失敗", ephemeral=True)


class PresenceIntervalModal(Modal):
    """設定狀態輪播間隔"""

    def __init__(self, parent_view: PresenceSettingsView, default: str):
        super().__init__(title="設定狀態輪播間隔")
        self.parent_view = parent_view
        self.interval = TextInput(
            label="輪播間隔（秒）",
            placeholder="最小 3 秒，留空使用預設",
            default=default,
            required=False,
            max_length=5,
        )
        self.add_item(self.interval)

    async def on_submit(self, interaction: discord.Interaction):
        raw = self.interval.value.strip()
        if raw:
            try:
                interval = int(raw)
            except ValueError:
                await interaction.response.send_message("❌ 請輸入有效的整數秒數", ephemeral=True)
                return
            if interval < 3:
                await interaction.response.send_message("❌ 輪播間隔最小為 3 秒", ephemeral=True)
                return
        else:
            interval = None

        success = await self.parent_view.service.update_custom_settings(
            self.parent_view.guild.id,
            {"presence_interval": interval},
        )
        if success:
            manager = getattr(interaction.client, "presence_manager", None)
            if manager:
                await manager.refresh_settings(self.parent_view.guild.id)
            await interaction.response.send_message("✅ 已更新輪播間隔", ephemeral=True)
        else:
            await interaction.response.send_message("❌ 更新失敗", ephemeral=True)


class AdminAccessUserSelect(UserSelect):
    """選擇授權成員"""

    def __init__(self, parent_view, row: int | None = None):
        self.parent_view = parent_view
        super().__init__(
            placeholder="選擇可使用 /admin 的成員（可多選）",
            min_values=0,
            max_values=25,
            row=row,
        )

    async def callback(self, interaction: discord.Interaction):
        user_ids = [member.id for member in self.values]
        success = await self.parent_view.service.update_custom_settings(
            self.parent_view.guild.id,
            {"admin_user_ids": user_ids},
        )
        if success:
            embed = await self.parent_view.build_embed()
            await interaction.response.edit_message(embed=embed, view=self.parent_view)
        else:
            await interaction.response.send_message("❌ 更新失敗", ephemeral=True)


class AdminAccessSettingsView(View):
    """管理面板授權設定（Owner Only）"""

    def __init__(self, user_id: int, guild: discord.Guild, timeout=300):
        super().__init__(timeout=timeout)
        self.user_id = user_id
        self.guild = guild
        self.service = SystemSettingsService()

        self.add_item(AdminAccessUserSelect(self, row=0))

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("❌ 只有開啟此面板的 Owner 可設定", ephemeral=True)
            return False
        if _is_guild_owner(interaction) or await interaction.client.is_owner(interaction.user):
            return True
        await interaction.response.send_message("❌ 僅限伺服器 Owner 設定", ephemeral=True)
        return False

    async def build_embed(self) -> discord.Embed:
        admin_user_ids = await self.service.get_admin_user_ids(self.guild.id)
        if admin_user_ids:
            lines = []
            for user_id in admin_user_ids[:15]:
                lines.append(f"<@{user_id}>")
            if len(admin_user_ids) > 15:
                lines.append(f"... 其餘 {len(admin_user_ids) - 15} 人")
            text = "、".join(lines)
        else:
            text = "未設定"

        embed = discord.Embed(
            title="🛡️ 管理面板授權",
            description="指定可使用 /admin 的成員（Owner 專用）",
            color=0xF1C40F,
        )
        embed.add_field(name="授權成員", value=text, inline=False)
        return embed

    @button(label="🧹 清除授權", style=discord.ButtonStyle.secondary, row=1)
    async def clear_admins(self, interaction: discord.Interaction, button: Button):
        success = await self.service.update_custom_settings(
            self.guild.id,
            {"admin_user_ids": []},
        )
        if success:
            embed = await self.build_embed()
            await interaction.response.edit_message(embed=embed, view=self)
        else:
            await interaction.response.send_message("❌ 清除失敗", ephemeral=True)

    @button(label="❌ 關閉", style=discord.ButtonStyle.danger, row=1)
    async def close_button(self, interaction: discord.Interaction, button: Button):
        embed = discord.Embed(title="✅ 授權設定已關閉", color=0x95A5A6)
        await interaction.response.edit_message(embed=embed, view=None)


# ========== 類別自動建立 ==========


CATEGORY_BULK_LIMIT = 20


def _format_name_list(names: list[str], limit: int = 10) -> str:
    if not names:
        return "無"
    lines = [f"• {name}" for name in names[:limit]]
    if len(names) > limit:
        lines.append(f"... 其餘 {len(names) - limit} 個")
    return "\n".join(lines)


class CategoryAutoSettingsView(View):
    """類別自動建立設定面板"""

    def __init__(self, user_id: int, guild: discord.Guild, timeout=300):
        super().__init__(timeout=timeout)
        self.user_id = user_id
        self.guild = guild
        self.dao = CategoryAutoDAO()

        self.add_item(CategoryAutoAllowedRoleSelect(self, row=0))
        self.add_item(CategoryAutoManagerRoleSelect(self, row=1))
        self.add_item(CategoryAutoBulkCreateButton(self, row=2))
        self.add_item(CategoryAutoClearAllowedRolesButton(self, row=2))
        self.add_item(CategoryAutoClearManagerRolesButton(self, row=2))
        self.add_item(ResumeBackToSystemButton(user_id, guild, row=3))

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("❌ 只有開啟此面板的管理員可設定", ephemeral=True)
            return False
        return True

    async def build_embed(self, notice: str | None = None) -> discord.Embed:
        settings = await self.dao.get_settings(self.guild.id)
        allowed_roles = settings.get("allowed_role_ids", [])
        manager_roles = settings.get("manager_role_ids", [])

        allowed_text = (
            "未設定（僅管理員/擁有者可使用）"
            if not allowed_roles
            else "、".join(
                role.mention
                for role in (self.guild.get_role(rid) for rid in allowed_roles)
                if role
            )
        )
        if not allowed_text:
            allowed_text = "未設定（僅管理員/擁有者可使用）"

        manager_text = (
            "未設定（不額外授權）"
            if not manager_roles
            else "、".join(
                role.mention
                for role in (self.guild.get_role(rid) for rid in manager_roles)
                if role
            )
        )
        if not manager_text:
            manager_text = "未設定（不額外授權）"

        embed = discord.Embed(
            title="🗂️ 類別自動建立設定",
            description="設定可使用者與預設管理身分組，並提供批量建立類別工具。",
            color=0x3498DB,
        )
        embed.add_field(name="可使用身分組", value=allowed_text, inline=False)
        embed.add_field(name="預設管理身分組", value=manager_text, inline=False)
        embed.add_field(
            name="批量建立",
            value=f"點擊「批量建立類別」後，輸入每行一個類別名稱（每次最多 {CATEGORY_BULK_LIMIT} 個）。",
            inline=False,
        )
        if notice:
            embed.add_field(name="提示", value=notice, inline=False)
        return embed

    async def update_panel(
        self, interaction: discord.Interaction | None = None, notice: str | None = None
    ) -> None:
        embed = await self.build_embed(notice=notice)
        if interaction:
            if interaction.response.is_done():
                await interaction.edit_original_response(embed=embed, view=self)
            else:
                await interaction.response.edit_message(embed=embed, view=self)
            return

    async def save_settings(self, interaction: discord.Interaction, **patch) -> None:
        await self.dao.save_settings(self.guild.id, **patch)
        await self.update_panel(interaction, notice="✅ 設定已更新")

    async def open_bulk_create_modal(self, interaction: discord.Interaction) -> None:
        modal = CategoryAutoBulkCreateModal(self, self.guild, self.dao, self.user_id)
        await interaction.response.send_modal(modal)


class CategoryAutoCreateView(View):
    """類別批量建立面板（一般使用者）"""

    def __init__(self, user_id: int, guild: discord.Guild, timeout=300):
        super().__init__(timeout=timeout)
        self.user_id = user_id
        self.guild = guild
        self.dao = CategoryAutoDAO()

        self.add_item(CategoryAutoBulkCreateButton(self, row=0))
        self.add_item(CategoryAutoCloseButton(row=1))

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("❌ 只有開啟此面板者可以操作", ephemeral=True)
            return False
        return True

    async def open_bulk_create_modal(self, interaction: discord.Interaction) -> None:
        modal = CategoryAutoBulkCreateModal(self, self.guild, self.dao, self.user_id)
        await interaction.response.send_modal(modal)


class CategoryAutoAllowedRoleSelect(discord.ui.RoleSelect):
    """可使用身分組選擇"""

    def __init__(self, parent_view: CategoryAutoSettingsView, row: int | None = None):
        self.parent_view = parent_view
        super().__init__(
            placeholder="選擇可使用身分組（可多選）",
            min_values=1,
            max_values=10,
            row=row,
        )

    async def callback(self, interaction: discord.Interaction):
        role_ids = [role.id for role in self.values]
        await self.parent_view.save_settings(interaction, allowed_role_ids=role_ids)


class CategoryAutoManagerRoleSelect(discord.ui.RoleSelect):
    """預設管理身分組選擇"""

    def __init__(self, parent_view: CategoryAutoSettingsView, row: int | None = None):
        self.parent_view = parent_view
        super().__init__(
            placeholder="選擇預設管理身分組（可多選）",
            min_values=1,
            max_values=10,
            row=row,
        )

    async def callback(self, interaction: discord.Interaction):
        role_ids = [role.id for role in self.values]
        await self.parent_view.save_settings(interaction, manager_role_ids=role_ids)


class CategoryAutoClearAllowedRolesButton(Button):
    """清除可使用身分組"""

    def __init__(self, parent_view: CategoryAutoSettingsView, row: int | None = None):
        super().__init__(label="🧹 清除可使用身分組", style=discord.ButtonStyle.secondary, row=row)
        self.parent_view = parent_view

    async def callback(self, interaction: discord.Interaction):
        await self.parent_view.save_settings(interaction, allowed_role_ids=[])


class CategoryAutoClearManagerRolesButton(Button):
    """清除預設管理身分組"""

    def __init__(self, parent_view: CategoryAutoSettingsView, row: int | None = None):
        super().__init__(label="🧹 清除管理身分組", style=discord.ButtonStyle.secondary, row=row)
        self.parent_view = parent_view

    async def callback(self, interaction: discord.Interaction):
        await self.parent_view.save_settings(interaction, manager_role_ids=[])


class CategoryAutoBulkCreateButton(Button):
    """批量建立類別按鈕"""

    def __init__(self, parent_view, row: int | None = None):
        super().__init__(label="➕ 批量建立類別", style=discord.ButtonStyle.success, row=row)
        self.parent_view = parent_view

    async def callback(self, interaction: discord.Interaction):
        await self.parent_view.open_bulk_create_modal(interaction)


class CategoryAutoCloseButton(Button):
    """關閉類別批量建立面板"""

    def __init__(self, row: int | None = None):
        super().__init__(label="❌ 關閉面板", style=discord.ButtonStyle.danger, row=row)

    async def callback(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="✅ 面板已關閉",
            description="類別批量建立面板已關閉",
            color=0x95A5A6,
        )
        await interaction.response.edit_message(embed=embed, view=None)


class CategoryAutoBulkCreateModal(Modal):
    """批量建立類別表單"""

    def __init__(
        self,
        parent_view,
        guild: discord.Guild,
        dao: CategoryAutoDAO,
        user_id: int,
    ):
        super().__init__(title="批量建立類別", timeout=300)
        self.parent_view = parent_view
        self.guild = guild
        self.dao = dao
        self.user_id = user_id

        self.names_input = TextInput(
            label="類別名稱（每行一個）",
            style=discord.TextStyle.paragraph,
            max_length=1000,
            required=True,
            placeholder="範例：\n行政部\n財務部\n市場部",
        )
        self.add_item(self.names_input)

    @staticmethod
    def _parse_names(raw_text: str) -> list[str]:
        if not raw_text:
            return []
        lines: list[str] = []
        for line in raw_text.replace(",", "\n").splitlines():
            cleaned = line.strip()
            if cleaned:
                lines.append(cleaned)
        # 去重（保留順序）
        seen = set()
        unique: list[str] = []
        for name in lines:
            key = name.casefold()
            if key in seen:
                continue
            seen.add(key)
            unique.append(name)
        return unique

    async def on_submit(self, interaction: discord.Interaction):
        if not interaction.guild:
            await interaction.response.send_message("❌ 此功能僅能在伺服器中使用", ephemeral=True)
            return
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("❌ 只有開啟面板者可操作", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)

        settings = await self.dao.get_settings(self.guild.id)
        allowed_roles = settings.get("allowed_role_ids", [])
        is_owner = False
        try:
            is_owner = await interaction.client.is_owner(interaction.user)
        except Exception:
            is_owner = False

        if not can_use_category_auto(interaction.user, allowed_roles, is_owner=is_owner):
            await interaction.followup.send("❌ 你沒有使用此功能的權限", ephemeral=True)
            return

        bot_member = interaction.guild.get_member(interaction.client.user.id)
        if not bot_member or not bot_member.guild_permissions.manage_channels:
            await interaction.followup.send("❌ 機器人缺少管理頻道權限", ephemeral=True)
            return

        manager_roles = settings.get("manager_role_ids", [])
        overwrites = build_manager_overwrites(self.guild, manager_roles)

        names = self._parse_names(self.names_input.value)
        if not names:
            await interaction.followup.send("❌ 沒有有效的類別名稱", ephemeral=True)
            return

        extras = 0
        if len(names) > CATEGORY_BULK_LIMIT:
            extras = len(names) - CATEGORY_BULK_LIMIT
            names = names[:CATEGORY_BULK_LIMIT]

        existing = {category.name.casefold() for category in self.guild.categories}
        created: list[str] = []
        skipped: list[str] = []
        failed: list[str] = []

        for name in names:
            if len(name) > 100:
                skipped.append(f"{name[:100]}（名稱過長）")
                continue
            key = name.casefold()
            if key in existing:
                skipped.append(f"{name}（已存在）")
                continue
            try:
                await self.guild.create_category(
                    name=name,
                    overwrites=overwrites or None,
                    reason=f"Category auto-create by {interaction.user}",
                )
                created.append(name)
                existing.add(key)
            except discord.Forbidden:
                failed.append(f"{name}（權限不足）")
            except Exception as e:
                failed.append(f"{name}（{e}）")

        summary_lines = [
            f"✅ 已建立 {len(created)} 個類別",
            f"⚠️ 略過 {len(skipped)} 個類別",
            f"❌ 失敗 {len(failed)} 個類別",
        ]
        if extras:
            summary_lines.append(f"ℹ️ 超過上限略過 {extras} 個類別")

        embed = discord.Embed(
            title="🗂️ 批量建立結果",
            description="\n".join(summary_lines),
            color=0x2ECC71 if created else 0xE67E22,
        )
        embed.add_field(name="已建立", value=_format_name_list(created), inline=False)
        embed.add_field(name="略過", value=_format_name_list(skipped), inline=False)
        embed.add_field(name="失敗", value=_format_name_list(failed), inline=False)

        await interaction.followup.send(embed=embed, ephemeral=True)


# ========== 自動回覆設定 ==========


class AutoReplySettingsView(View):
    """自動回覆設定面板"""

    def __init__(self, user_id: int, guild: discord.Guild, timeout=300):
        super().__init__(timeout=timeout)
        self.user_id = user_id
        self.guild = guild
        self.dao = AutoReplyDAO()
        self.selected_user_id: int | None = None
        self.message: discord.Message | None = None

        self.add_item(AutoReplyUserSelect(self, row=0))
        self.add_item(AutoReplyAddButton(self, row=1))
        self.add_item(AutoReplyRemoveButton(self, row=1))
        self.add_item(AutoReplyRefreshButton(self, row=1))
        self.add_item(ResumeBackToSystemButton(user_id, guild, row=2))

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        return interaction.user.id == self.user_id

    async def build_embed(self, notice: str | None = None) -> discord.Embed:
        embed = discord.Embed(
            title="💬 自動回覆設定",
            description="當有人 @ 指定成員時，自動回覆指定內容。",
            color=0x3498DB,
        )

        if self.selected_user_id:
            embed.add_field(
                name="目前選擇",
                value=f"<@{self.selected_user_id}>",
                inline=False,
            )

        rules = await self.dao.list_rules(self.guild.id)
        if not rules:
            embed.add_field(
                name="⚠️ 尚未設定",
                value="請選擇成員並新增回覆內容。",
                inline=False,
            )
        else:
            lines = []
            for rule in rules[:20]:
                mention = f"<@{rule['target_user_id']}>"
                reply_text = str(rule.get("reply_text", "")).replace("\n", " ").strip()
                if len(reply_text) > 60:
                    reply_text = reply_text[:60] + "..."
                lines.append(f"{mention} → {reply_text}")
            embed.add_field(
                name="已設定規則",
                value="\n".join(lines),
                inline=False,
            )
            if len(rules) > 20:
                embed.set_footer(text=f"僅顯示前 20 筆，共 {len(rules)} 筆")

        if notice:
            embed.add_field(name="提示", value=notice, inline=False)

        return embed

    async def update_panel(
        self, interaction: discord.Interaction | None = None, notice: str | None = None
    ) -> None:
        embed = await self.build_embed(notice=notice)
        if interaction:
            if interaction.response.is_done():
                await interaction.edit_original_response(embed=embed, view=self)
            else:
                await interaction.response.edit_message(embed=embed, view=self)
            if interaction.message:
                self.message = interaction.message
        elif self.message:
            await self.message.edit(embed=embed, view=self)

    async def save_rule(self, target_user_id: int, reply_text: str, actor_id: int) -> str | None:
        text = str(reply_text or "").strip()
        if not text:
            return "回覆內容不可為空"
        await self.dao.upsert_rule(self.guild.id, target_user_id, text, actor_id=actor_id)
        return None


class AutoReplyUserSelect(discord.ui.UserSelect):
    """成員選擇下拉"""

    def __init__(self, parent_view: AutoReplySettingsView, row: int | None = None):
        self.parent_view = parent_view
        super().__init__(
            placeholder="選擇要設定的成員",
            min_values=1,
            max_values=1,
            row=row,
        )

    async def callback(self, interaction: discord.Interaction):
        selected_user = self.values[0]
        self.parent_view.selected_user_id = selected_user.id
        await interaction.response.defer()


class AutoReplyAddButton(Button):
    """新增或更新回覆"""

    def __init__(self, parent_view: AutoReplySettingsView, row: int | None = None):
        super().__init__(label="➕ 新增/更新", style=discord.ButtonStyle.success, row=row)
        self.parent_view = parent_view

    async def callback(self, interaction: discord.Interaction):
        target_user_id = self.parent_view.selected_user_id
        if not target_user_id:
            await interaction.response.send_message("❌ 請先選擇成員", ephemeral=True)
            return
        await interaction.response.send_modal(
            AutoReplyResponseModal(self.parent_view, target_user_id)
        )


class AutoReplyRemoveButton(Button):
    """移除回覆"""

    def __init__(self, parent_view: AutoReplySettingsView, row: int | None = None):
        super().__init__(label="🗑️ 移除", style=discord.ButtonStyle.danger, row=row)
        self.parent_view = parent_view

    async def callback(self, interaction: discord.Interaction):
        target_user_id = self.parent_view.selected_user_id
        if not target_user_id:
            await interaction.response.send_message("❌ 請先選擇成員", ephemeral=True)
            return
        removed = await self.parent_view.dao.delete_rule(
            self.parent_view.guild.id, target_user_id
        )
        notice = "✅ 已移除設定" if removed else "⚠️ 找不到該成員的設定"
        await self.parent_view.update_panel(interaction, notice=notice)


class AutoReplyRefreshButton(Button):
    """重新整理"""

    def __init__(self, parent_view: AutoReplySettingsView, row: int | None = None):
        super().__init__(label="🔄 重新整理", style=discord.ButtonStyle.secondary, row=row)
        self.parent_view = parent_view

    async def callback(self, interaction: discord.Interaction):
        await self.parent_view.update_panel(interaction)


class AutoReplyResponseModal(Modal):
    """自動回覆內容輸入"""

    def __init__(self, parent_view: AutoReplySettingsView, target_user_id: int):
        super().__init__(title="設定自動回覆")
        self.parent_view = parent_view
        self.target_user_id = target_user_id

        self.reply_text = TextInput(
            label="回覆內容",
            placeholder="輸入要回覆的訊息",
            style=discord.TextStyle.paragraph,
            max_length=500,
            required=True,
        )
        self.add_item(self.reply_text)

    async def on_submit(self, interaction: discord.Interaction):
        error = await self.parent_view.save_rule(
            self.target_user_id, self.reply_text.value, interaction.user.id
        )
        if error:
            await interaction.response.send_message(f"❌ {error}", ephemeral=True)
            return

        await self.parent_view.update_panel(notice="✅ 已更新設定")
        await interaction.response.send_message("✅ 已更新自動回覆設定", ephemeral=True)


# ========== Modal 表單 ==========


class TicketSettingsModal(Modal):
    """票券系統設定表單"""

    def __init__(self):
        super().__init__(title="⚙️ 票券系統參數設定")

        self.max_tickets = TextInput(
            label="每人最大票券數量",
            placeholder="預設: 3",
            default="3",
            max_length=2,
            required=True,
        )

        self.auto_close_hours = TextInput(
            label="自動關閉時間 (小時)",
            placeholder="預設: 24",
            default="24",
            max_length=3,
            required=True,
        )

        self.add_item(self.max_tickets)
        self.add_item(self.auto_close_hours)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            max_tickets = int(self.max_tickets.value)
            auto_close_hours = int(self.auto_close_hours.value)

            # 驗證範圍
            if not (1 <= max_tickets <= 10):
                await interaction.response.send_message(
                    "❌ 每人票券數量必須在 1-10 之間", ephemeral=True
                )
                return

            if not (1 <= auto_close_hours <= 168):
                await interaction.response.send_message(
                    "❌ 自動關閉時間必須在 1-168 小時之間", ephemeral=True
                )
                return

            # 更新設定
            ticket_dao = TicketDAO()
            success = await ticket_dao.update_settings(
                interaction.guild.id,
                {
                    "max_tickets_per_user": max_tickets,
                    "auto_close_hours": auto_close_hours,
                },
            )

            if success:
                embed = discord.Embed(
                    title="✅ 票券系統參數已更新",
                    description=f"每人票券上限: {max_tickets}\n"
                    f"自動關閉時間: {auto_close_hours} 小時",
                    color=0x2ECC71,
                )
            else:
                embed = discord.Embed(
                    title="❌ 設定更新失敗",
                    description="更新票券系統參數時發生錯誤",
                    color=0xE74C3C,
                )

            await interaction.response.send_message(embed=embed, ephemeral=True)

        except ValueError:
            await interaction.response.send_message("❌ 請輸入有效的數字", ephemeral=True)
        except Exception as e:
            logger.error(f"票券設定更新錯誤: {e}")
            await interaction.response.send_message("❌ 設定過程中發生錯誤", ephemeral=True)


class TicketMessageModal(Modal):
    """票券訊息設定表單"""

    def __init__(self):
        super().__init__(title="🎨 票券系統訊息設定")

        self.welcome_msg = TextInput(
            label="票券面板歡迎訊息",
            placeholder="票券系統的歡迎描述文字",
            style=discord.TextStyle.paragraph,
            max_length=2000,
            required=False,
        )

        self.close_msg = TextInput(
            label="票券關閉後訊息",
            placeholder="票券關閉時顯示的訊息",
            style=discord.TextStyle.paragraph,
            max_length=2000,
            required=False,
        )

        self.add_item(self.welcome_msg)
        self.add_item(self.close_msg)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            ticket_dao = TicketDAO()
            settings_to_update = {}

            if self.welcome_msg.value:
                settings_to_update["welcome_message"] = self.welcome_msg.value

            if self.close_msg.value:
                settings_to_update["close_message"] = self.close_msg.value

            if not settings_to_update:
                await interaction.response.send_message("❌ 請至少填寫一項訊息", ephemeral=True)
                return

            success = await ticket_dao.update_settings(interaction.guild.id, settings_to_update)

            if success:
                embed = discord.Embed(
                    title="✅ 票券訊息已更新",
                    description="票券系統訊息設定已成功保存",
                    color=0x2ECC71,
                )
            else:
                embed = discord.Embed(
                    title="❌ 設定更新失敗",
                    description="更新票券訊息時發生錯誤",
                    color=0xE74C3C,
                )

            await interaction.response.send_message(embed=embed, ephemeral=True)

        except Exception as e:
            logger.error(f"票券訊息設定錯誤: {e}")
            await interaction.response.send_message("❌ 設定過程中發生錯誤", ephemeral=True)


class WelcomeMessageModal(Modal):
    """歡迎訊息設定表單"""

    def __init__(self):
        super().__init__(title="📝 歡迎訊息設定")

        self.welcome_msg = TextInput(
            label="歡迎訊息",
            placeholder="可使用變數: {user_mention}, {guild_name}, {member_count}",
            style=discord.TextStyle.paragraph,
            max_length=2000,
            required=False,
        )

        self.leave_msg = TextInput(
            label="離開訊息",
            placeholder="可使用變數: {username}, {guild_name}, {join_date}",
            style=discord.TextStyle.paragraph,
            max_length=2000,
            required=False,
        )

        self.add_item(self.welcome_msg)
        self.add_item(self.leave_msg)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            welcome_manager = WelcomeManager()
            settings_to_update = {}

            if self.welcome_msg.value:
                settings_to_update["welcome_message"] = self.welcome_msg.value

            if self.leave_msg.value:
                settings_to_update["leave_message"] = self.leave_msg.value

            if not settings_to_update:
                await interaction.response.send_message("❌ 請至少填寫一項訊息", ephemeral=True)
                return

            success, message = await welcome_manager.update_welcome_settings(
                interaction.guild.id, **settings_to_update
            )

            if success:
                embed = discord.Embed(
                    title="✅ 歡迎訊息已更新",
                    description="歡迎訊息設定已成功保存",
                    color=0x2ECC71,
                )
            else:
                embed = discord.Embed(
                    title="❌ 設定更新失敗",
                    description=f"更新過程中發生錯誤：{message}",
                    color=0xE74C3C,
                )

            await interaction.response.send_message(embed=embed, ephemeral=True)

        except Exception as e:
            logger.error(f"歡迎訊息設定錯誤: {e}")
            await interaction.response.send_message("❌ 設定過程中發生錯誤", ephemeral=True)


class VoteSettingsView(View):
    """投票系統設定視圖"""

    def __init__(self, user_id: int, timeout=300):
        super().__init__(timeout=timeout)
        self.user_id = user_id

    async def _build_vote_settings_payload(self, guild_id: int, **patch) -> dict:
        current = await vote_dao.get_vote_settings(guild_id) or {}
        payload = {
            "default_vote_channel_id": current.get("default_vote_channel_id"),
            "announcement_channel_id": current.get("announcement_channel_id"),
            "max_vote_duration_hours": current.get("max_vote_duration_hours", 72),
            "min_vote_duration_minutes": current.get("min_vote_duration_minutes", 60),
            "require_role_to_create": current.get("require_role_to_create", False),
            "allowed_creator_roles": current.get("allowed_creator_roles", []),
            "auto_announce_results": current.get("auto_announce_results", True),
            "allow_anonymous_votes": current.get("allow_anonymous_votes", True),
            "allow_multi_choice": current.get("allow_multi_choice", True),
            "is_enabled": current.get("is_enabled", True),
        }
        payload.update(patch)
        return payload

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        """檢查用戶權限"""
        if interaction.user.id != self.user_id:
            await interaction.response.send_message(
                "❌ 只有指令使用者可以操作此面板", ephemeral=True
            )
            return False

        if await _has_system_admin_access(interaction):
            return True

        await interaction.response.send_message("❌ 需要管理伺服器權限或已授權管理員", ephemeral=True)
        return False

    @button(label="🚀 現代GUI投票", style=discord.ButtonStyle.success, row=0)
    async def modern_vote_gui_button(self, interaction: discord.Interaction, button: Button):
        """現代化GUI投票系統按鈕"""
        try:
            from potato_bot.views.vote_views import VoteManagementView

            embed = discord.Embed(
                title="🚀 現代化GUI投票系統",
                description="使用全新的圖形界面創建和管理投票",
                color=0x3498DB,
            )

            embed.add_field(
                name="✨ 新功能特色",
                value="• 🎯 直覺的拖拉式界面\n"
                "• ⚙️ 豐富的設定選項\n"
                "• 🎨 美觀的視覺效果",
                inline=False,
            )

            embed.add_field(
                name="🔧 可用功能",
                value="• 快速創建投票\n" "• 管理現有投票",
                inline=False,
            )

            view = VoteManagementView()
            await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

        except Exception as e:
            logger.error(f"現代GUI投票系統錯誤: {e}")
            await interaction.response.send_message(
                "❌ 啟動現代GUI投票系統時發生錯誤", ephemeral=True
            )

    @button(label="📺 設定投票頻道", style=discord.ButtonStyle.primary, row=0)
    async def set_vote_channel_button(self, interaction: discord.Interaction, button: Button):
        """設定預設投票頻道按鈕"""
        self.clear_items()
        self.add_item(VoteChannelSelect(self.user_id))
        self.add_item(BackToVoteSettingsButton(self.user_id))

        embed = discord.Embed(
            title="📺 選擇預設投票頻道",
            description="選擇新建立的投票要發布到哪個頻道",
            color=0x3498DB,
        )

        await interaction.response.edit_message(embed=embed, view=self)

    @button(label="📢 設定公告頻道", style=discord.ButtonStyle.secondary, row=0)
    async def set_announce_channel_button(self, interaction: discord.Interaction, button: Button):
        """設定投票結果公告頻道按鈕"""
        self.clear_items()
        self.add_item(AnnounceChannelSelect(self.user_id))
        self.add_item(BackToVoteSettingsButton(self.user_id))

        embed = discord.Embed(
            title="📢 選擇投票結果公告頻道",
            description="選擇投票結束後結果要公告到哪個頻道",
            color=0x3498DB,
        )

        await interaction.response.edit_message(embed=embed, view=self)

    @button(label="📋 管理活躍投票", style=discord.ButtonStyle.primary, row=0)
    async def manage_active_votes_button(self, interaction: discord.Interaction, button: Button):
        """管理活躍投票按鈕"""
        await interaction.response.send_message(
            embed=await self._create_active_votes_embed(interaction.guild),
            view=ActiveVoteManageView(self.user_id),
            ephemeral=True,
        )

    @button(label="⚙️ 系統開關", style=discord.ButtonStyle.success, row=1)
    async def toggle_system_button(self, interaction: discord.Interaction, button: Button):
        """切換系統開關按鈕"""
        # 取得當前設定
        settings = await vote_dao.get_vote_settings(interaction.guild.id)
        current_enabled = settings.get("is_enabled", True) if settings else True

        # 切換狀態
        new_enabled = not current_enabled
        payload = await self._build_vote_settings_payload(
            interaction.guild.id, is_enabled=new_enabled
        )
        success = await vote_dao.update_vote_settings(interaction.guild.id, payload)

        if success:
            status = "啟用" if new_enabled else "停用"
            color = 0x2ECC71 if new_enabled else 0xF39C12
            embed = discord.Embed(
                title=f"✅ 投票系統已{status}",
                description=f"投票系統現在已{status}",
                color=color,
            )
        else:
            embed = discord.Embed(
                title="❌ 操作失敗",
                description="切換系統狀態時發生錯誤",
                color=0xE74C3C,
            )

        await interaction.response.send_message(embed=embed, ephemeral=True)

    @button(label="👥 設定面板身分組", style=discord.ButtonStyle.secondary, row=1)
    async def set_vote_panel_roles_button(
        self, interaction: discord.Interaction, button: Button
    ):
        """設定投票面板可使用身分組"""
        self.clear_items()
        self.add_item(VotePanelRoleSelect(self, row=0))
        self.add_item(BackToVoteSettingsButton(self.user_id))

        embed = discord.Embed(
            title="👥 設定投票面板可使用身分組",
            description="選擇可以使用 /vote_panel 的身分組（可多選）",
            color=0x3498DB,
        )

        await interaction.response.edit_message(embed=embed, view=self)

    @button(label="🧹 清除面板身分組", style=discord.ButtonStyle.secondary, row=1)
    async def clear_vote_panel_roles_button(
        self, interaction: discord.Interaction, button: Button
    ):
        """清除投票面板可使用身分組"""
        payload = await self._build_vote_settings_payload(
            interaction.guild.id,
            allowed_creator_roles=[],
            require_role_to_create=False,
        )
        success = await vote_dao.update_vote_settings(interaction.guild.id, payload)

        if success:
            embed = discord.Embed(
                title="✅ 已清除投票面板身分組",
                description="現在僅管理員可使用投票面板",
                color=0x2ECC71,
            )
        else:
            embed = discord.Embed(
                title="❌ 清除失敗",
                description="更新設定時發生錯誤",
                color=0xE74C3C,
            )

        await interaction.response.send_message(embed=embed, ephemeral=True)

    @button(label="🔄 重新整理", style=discord.ButtonStyle.secondary, row=2)
    async def refresh_button(self, interaction: discord.Interaction, button: Button):
        """重新整理設定按鈕"""
        from potato_bot.views.system_admin_views import SystemAdminPanel

        admin_panel = SystemAdminPanel(self.user_id)
        embed = await admin_panel._create_vote_settings_embed(interaction.guild)
        await interaction.response.edit_message(embed=embed, view=self)

    @button(label="❌ 關閉", style=discord.ButtonStyle.danger, row=2)
    async def close_button(self, interaction: discord.Interaction, button: Button):
        """關閉按鈕"""
        embed = discord.Embed(title="✅ 投票系統設定已關閉", color=0x95A5A6)
        await interaction.response.edit_message(embed=embed, view=None)

    async def _create_active_votes_embed(self, guild: discord.Guild) -> discord.Embed:
        """創建活躍投票嵌入"""
        active_votes = await vote_dao.get_active_votes(guild.id if guild else None)

        embed = discord.Embed(title="📋 活躍投票管理", color=0x3498DB)

        if not active_votes:
            embed.description = "目前沒有進行中的投票"
            embed.color = 0x95A5A6
        else:
            embed.description = f"共有 {len(active_votes)} 個進行中的投票"

            for vote in active_votes[:5]:  # 最多顯示5個
                embed.add_field(
                    name=f"#{vote['id']} - {vote['title'][:50]}",
                    value=f"⏰ 結束時間: {vote['end_time'].strftime('%m-%d %H:%M')}\n"
                    f"🏷️ 模式: {'匿名' if vote['anonymous'] else '公開'}{'多選' if vote['is_multi'] else '單選'}",
                    inline=True,
                )

            if len(active_votes) > 5:
                embed.add_field(
                    name="📌 提示",
                    value=f"還有 {len(active_votes) - 5} 個投票未顯示",
                    inline=False,
                )

        return embed


class VotePanelRoleSelect(discord.ui.RoleSelect):
    """投票面板可使用身分組選擇"""

    def __init__(self, parent_view: VoteSettingsView, row: int | None = None):
        self.parent_view = parent_view
        super().__init__(
            placeholder="選擇可使用投票面板的身分組（可多選）",
            min_values=1,
            max_values=10,
            row=row,
        )

    async def callback(self, interaction: discord.Interaction):
        role_ids = [role.id for role in self.values]
        payload = await self.parent_view._build_vote_settings_payload(
            interaction.guild.id,
            allowed_creator_roles=role_ids,
            require_role_to_create=True,
        )
        success = await vote_dao.update_vote_settings(interaction.guild.id, payload)

        if success:
            admin_panel = SystemAdminPanel(self.parent_view.user_id)
            embed = await admin_panel._create_vote_settings_embed(interaction.guild)
            view = VoteSettingsView(self.parent_view.user_id)
            await interaction.response.edit_message(embed=embed, view=view)
        else:
            await interaction.response.send_message("❌ 設定失敗，請稍後再試", ephemeral=True)


class LotterySettingsView(View):
    """抽獎系統設定視圖"""

    def __init__(self, user_id: int, guild: discord.Guild, timeout=300):
        super().__init__(timeout=timeout)
        self.user_id = user_id
        self.guild = guild
        self.dao = LotteryDAO()

    async def _build_lottery_settings_payload(self, **patch) -> dict:
        current = await self.dao.get_lottery_settings(self.guild.id) or {}
        payload = {
            "default_duration_hours": current.get("default_duration_hours", 24),
            "max_concurrent_lotteries": current.get("max_concurrent_lotteries", 3),
            "allow_self_entry": current.get("allow_self_entry", True),
            "require_boost": current.get("require_boost", False),
            "log_channel_id": current.get("log_channel_id"),
            "announcement_channel_id": current.get("announcement_channel_id"),
            "admin_roles": current.get("admin_roles", []),
        }
        payload.update(patch)
        return payload

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.user_id:
            await interaction.response.send_message(
                "❌ 只有指令使用者可以操作此面板", ephemeral=True
            )
            return False
        if await _has_system_admin_access(interaction):
            return True
        await interaction.response.send_message("❌ 需要管理伺服器權限或已授權管理員", ephemeral=True)
        return False

    @button(label="👥 設定面板身分組", style=discord.ButtonStyle.secondary, row=0)
    async def set_lottery_panel_roles_button(
        self, interaction: discord.Interaction, button: Button
    ):
        """設定抽獎面板可使用身分組"""
        self.clear_items()
        self.add_item(LotteryPanelRoleSelect(self, row=0))
        self.add_item(BackToLotterySettingsButton(self.user_id, self.guild))

        embed = discord.Embed(
            title="👥 設定抽獎面板可使用身分組",
            description="選擇可以使用 /lottery_panel 的身分組（可多選）",
            color=0x3498DB,
        )
        await interaction.response.edit_message(embed=embed, view=self)

    @button(label="🧹 清除面板身分組", style=discord.ButtonStyle.secondary, row=0)
    async def clear_lottery_panel_roles_button(
        self, interaction: discord.Interaction, button: Button
    ):
        """清除抽獎面板可使用身分組"""
        payload = await self._build_lottery_settings_payload(admin_roles=[])
        success = await self.dao.update_lottery_settings(self.guild.id, payload)

        if success:
            embed = discord.Embed(
                title="✅ 已清除抽獎面板身分組",
                description="現在僅管理員可使用抽獎面板",
                color=0x2ECC71,
            )
        else:
            embed = discord.Embed(
                title="❌ 清除失敗",
                description="更新設定時發生錯誤",
                color=0xE74C3C,
            )

        await interaction.response.send_message(embed=embed, ephemeral=True)

    @button(label="🔄 重新整理", style=discord.ButtonStyle.secondary, row=1)
    async def refresh_button(self, interaction: discord.Interaction, button: Button):
        panel = SystemAdminPanel(self.user_id)
        embed = await panel._create_lottery_settings_embed(self.guild)
        await interaction.response.edit_message(embed=embed, view=self)

    @button(label="❌ 關閉", style=discord.ButtonStyle.danger, row=1)
    async def close_button(self, interaction: discord.Interaction, button: Button):
        embed = discord.Embed(title="✅ 抽獎系統設定已關閉", color=0x95A5A6)
        await interaction.response.edit_message(embed=embed, view=None)


class LotteryPanelRoleSelect(discord.ui.RoleSelect):
    """抽獎面板可使用身分組選擇"""

    def __init__(self, parent_view: LotterySettingsView, row: int | None = None):
        self.parent_view = parent_view
        super().__init__(
            placeholder="選擇可使用抽獎面板的身分組（可多選）",
            min_values=1,
            max_values=10,
            row=row,
        )

    async def callback(self, interaction: discord.Interaction):
        role_ids = [role.id for role in self.values]
        payload = await self.parent_view._build_lottery_settings_payload(
            admin_roles=role_ids
        )
        success = await self.parent_view.dao.update_lottery_settings(
            self.parent_view.guild.id, payload
        )

        if success:
            admin_panel = SystemAdminPanel(self.parent_view.user_id)
            embed = await admin_panel._create_lottery_settings_embed(self.parent_view.guild)
            view = LotterySettingsView(self.parent_view.user_id, self.parent_view.guild)
            await interaction.response.edit_message(embed=embed, view=view)
        else:
            await interaction.response.send_message("❌ 設定失敗，請稍後再試", ephemeral=True)


class BackToLotterySettingsButton(Button):
    """返回抽獎設定按鈕"""

    def __init__(self, user_id: int, guild: discord.Guild):
        self.user_id = user_id
        self.guild = guild
        super().__init__(label="← 返回", style=discord.ButtonStyle.secondary)

    async def callback(self, interaction: discord.Interaction):
        admin_panel = SystemAdminPanel(self.user_id)
        embed = await admin_panel._create_lottery_settings_embed(self.guild)
        view = LotterySettingsView(self.user_id, self.guild)
        await interaction.response.edit_message(embed=embed, view=view)


class MusicSettingsView(View):
    """音樂系統設定視圖"""

    def __init__(self, user_id: int, guild: discord.Guild, timeout=300):
        super().__init__(timeout=timeout)
        self.user_id = user_id
        self.guild = guild
        self.dao = MusicDAO()

    async def _build_music_settings_payload(self, **patch) -> dict:
        current = await self.dao.get_music_settings(self.guild.id) or {}
        payload = {
            "allowed_role_ids": current.get("allowed_role_ids", []),
            "require_role_to_use": current.get("require_role_to_use", False),
            "lavalink_host": current.get("lavalink_host"),
            "lavalink_port": current.get("lavalink_port"),
            "lavalink_password": current.get("lavalink_password"),
            "lavalink_secure": current.get("lavalink_secure"),
            "lavalink_uri": current.get("lavalink_uri"),
        }
        payload.update(patch)
        return payload

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.user_id:
            await interaction.response.send_message(
                "❌ 只有指令使用者可以操作此面板", ephemeral=True
            )
            return False
        if await _has_system_admin_access(interaction):
            return True
        await interaction.response.send_message("❌ 需要管理伺服器權限或已授權管理員", ephemeral=True)
        return False

    @staticmethod
    async def _require_owner(interaction: discord.Interaction) -> bool:
        is_owner = await interaction.client.is_owner(interaction.user)
        if not is_owner:
            await interaction.response.send_message("❌ 僅限 Bot Owner 設定 Lavalink", ephemeral=True)
            return False
        return True

    @button(label="👥 設定面板身分組", style=discord.ButtonStyle.secondary, row=0)
    async def set_music_panel_roles_button(
        self, interaction: discord.Interaction, button: Button
    ):
        """設定音樂面板可使用身分組"""
        self.clear_items()
        self.add_item(MusicPanelRoleSelect(self, row=0))
        self.add_item(BackToMusicSettingsButton(self.user_id, self.guild))

        embed = discord.Embed(
            title="👥 設定音樂面板可使用身分組",
            description="選擇可以使用 /music_menu 的身分組（可多選）",
            color=0x3498DB,
        )
        await interaction.response.edit_message(embed=embed, view=self)

    @button(label="🧹 清除面板身分組", style=discord.ButtonStyle.secondary, row=0)
    async def clear_music_panel_roles_button(
        self, interaction: discord.Interaction, button: Button
    ):
        """清除音樂面板可使用身分組"""
        payload = await self._build_music_settings_payload(
            allowed_role_ids=[],
            require_role_to_use=False,
        )
        success = await self.dao.update_music_settings(self.guild.id, payload)

        if success:
            embed = discord.Embed(
                title="✅ 已清除音樂面板身分組",
                description="現在所有人都可使用音樂面板",
                color=0x2ECC71,
            )
        else:
            embed = discord.Embed(
                title="❌ 清除失敗",
                description="更新設定時發生錯誤",
                color=0xE74C3C,
            )

        await interaction.response.send_message(embed=embed, ephemeral=True)

    @button(label="🔧 設定 Lavalink", style=discord.ButtonStyle.secondary, row=0)
    async def set_lavalink_button(self, interaction: discord.Interaction, button: Button):
        if not await self._require_owner(interaction):
            return
        settings = await self.dao.get_music_settings(self.guild.id)
        await interaction.response.send_modal(LavalinkSettingsModal(self, settings))

    @button(label="🔄 重新連線", style=discord.ButtonStyle.secondary, row=1)
    async def reconnect_lavalink_button(self, interaction: discord.Interaction, button: Button):
        if not await self._require_owner(interaction):
            return
        music_cog = interaction.client.get_cog("MusicCore")
        if not music_cog or not hasattr(music_cog, "reload_lavalink"):
            await interaction.response.send_message("❌ 音樂系統尚未載入", ephemeral=True)
            return

        success = await music_cog.reload_lavalink(interaction.guild.id)
        if success:
            await interaction.response.send_message("✅ 已重新連線 Lavalink", ephemeral=True)
        else:
            await interaction.response.send_message("❌ 重新連線失敗，請檢查設定", ephemeral=True)

    @button(label="🧹 清除 Lavalink", style=discord.ButtonStyle.secondary, row=1)
    async def clear_lavalink_button(self, interaction: discord.Interaction, button: Button):
        if not await self._require_owner(interaction):
            return
        payload = await self._build_music_settings_payload(
            lavalink_host=None,
            lavalink_port=None,
            lavalink_password=None,
            lavalink_secure=None,
            lavalink_uri=None,
        )
        success = await self.dao.update_music_settings(self.guild.id, payload)
        if success:
            music_cog = interaction.client.get_cog("MusicCore")
            if music_cog and hasattr(music_cog, "reload_lavalink"):
                await music_cog.reload_lavalink(interaction.guild.id)
            await interaction.response.send_message("✅ 已清除 Lavalink 設定", ephemeral=True)
        else:
            await interaction.response.send_message("❌ 清除失敗", ephemeral=True)

    @button(label="🔄 重新整理", style=discord.ButtonStyle.secondary, row=1)
    async def refresh_button(self, interaction: discord.Interaction, button: Button):
        panel = SystemAdminPanel(self.user_id)
        embed = await panel._create_music_settings_embed(self.guild, interaction.client)
        await interaction.response.edit_message(embed=embed, view=self)

    @button(label="❌ 關閉", style=discord.ButtonStyle.danger, row=1)
    async def close_button(self, interaction: discord.Interaction, button: Button):
        embed = discord.Embed(title="✅ 音樂系統設定已關閉", color=0x95A5A6)
        await interaction.response.edit_message(embed=embed, view=None)


class MusicPanelRoleSelect(discord.ui.RoleSelect):
    """音樂面板可使用身分組選擇"""

    def __init__(self, parent_view: MusicSettingsView, row: int | None = None):
        self.parent_view = parent_view
        super().__init__(
            placeholder="選擇可使用音樂面板的身分組（可多選）",
            min_values=1,
            max_values=10,
            row=row,
        )

    async def callback(self, interaction: discord.Interaction):
        role_ids = [role.id for role in self.values]
        payload = await self.parent_view._build_music_settings_payload(
            allowed_role_ids=role_ids,
            require_role_to_use=True,
        )
        success = await self.parent_view.dao.update_music_settings(
            self.parent_view.guild.id, payload
        )

        if success:
            admin_panel = SystemAdminPanel(self.parent_view.user_id)
            embed = await admin_panel._create_music_settings_embed(
                self.parent_view.guild, interaction.client
            )
            view = MusicSettingsView(self.parent_view.user_id, self.parent_view.guild)
            await interaction.response.edit_message(embed=embed, view=view)
        else:
            await interaction.response.send_message("❌ 設定失敗，請稍後再試", ephemeral=True)


class LavalinkSettingsModal(Modal):
    """設定 Lavalink 連線"""

    def __init__(self, parent_view: MusicSettingsView, settings: dict):
        super().__init__(title="設定 Lavalink 連線")
        self.parent_view = parent_view

        current_uri = settings.get("lavalink_uri") or ""
        current_host = settings.get("lavalink_host") or ""
        current_port = settings.get("lavalink_port")
        current_password = settings.get("lavalink_password") or ""
        secure_value = settings.get("lavalink_secure")
        if secure_value is None:
            secure_text = ""
        else:
            secure_text = "true" if secure_value else "false"

        self.uri = TextInput(
            label="Lavalink URI (選填)",
            placeholder="https://your-lavalink:443",
            default=current_uri,
            required=False,
            max_length=200,
        )
        self.host = TextInput(
            label="Lavalink Host (選填)",
            placeholder="your-lavalink-host",
            default=current_host,
            required=False,
            max_length=200,
        )
        self.port = TextInput(
            label="Lavalink Port (選填)",
            placeholder="2333",
            default=str(current_port) if current_port else "",
            required=False,
            max_length=5,
        )
        self.password = TextInput(
            label="Lavalink Password (選填)",
            placeholder="your-lavalink-password",
            default=current_password,
            required=False,
            max_length=100,
        )
        self.secure = TextInput(
            label="Lavalink Secure (true/false)",
            placeholder="true 或 false",
            default=secure_text,
            required=False,
            max_length=5,
        )

        self.add_item(self.uri)
        self.add_item(self.host)
        self.add_item(self.port)
        self.add_item(self.password)
        self.add_item(self.secure)

    async def on_submit(self, interaction: discord.Interaction):
        if not await MusicSettingsView._require_owner(interaction):
            return
        uri = self.uri.value.strip() or None
        host = self.host.value.strip() or None
        port_text = self.port.value.strip()
        password = self.password.value.strip() or None
        secure_text = self.secure.value.strip().lower()

        if uri and not (uri.startswith("http://") or uri.startswith("https://")):
            await interaction.response.send_message("❌ URI 必須為 http/https", ephemeral=True)
            return

        port = None
        if port_text:
            try:
                port = int(port_text)
                if port <= 0 or port > 65535:
                    raise ValueError("port out of range")
            except Exception:
                await interaction.response.send_message("❌ Port 必須為 1-65535 的數字", ephemeral=True)
                return

        secure = None
        if secure_text:
            if secure_text in ("true", "1", "yes", "y", "t", "on"):
                secure = True
            elif secure_text in ("false", "0", "no", "n", "f", "off"):
                secure = False
            else:
                await interaction.response.send_message("❌ Secure 必須為 true 或 false", ephemeral=True)
                return

        payload = await self.parent_view._build_music_settings_payload(
            lavalink_uri=uri,
            lavalink_host=host,
            lavalink_port=port,
            lavalink_password=password,
            lavalink_secure=secure,
        )
        success = await self.parent_view.dao.update_music_settings(
            self.parent_view.guild.id, payload
        )
        if not success:
            await interaction.response.send_message("❌ 更新失敗，請稍後再試", ephemeral=True)
            return

        music_cog = interaction.client.get_cog("MusicCore")
        if music_cog and hasattr(music_cog, "reload_lavalink"):
            await music_cog.reload_lavalink(interaction.guild.id)

        await interaction.response.send_message("✅ 已更新 Lavalink 設定", ephemeral=True)


class BackToMusicSettingsButton(Button):
    """返回音樂設定按鈕"""

    def __init__(self, user_id: int, guild: discord.Guild):
        self.user_id = user_id
        self.guild = guild
        super().__init__(label="← 返回", style=discord.ButtonStyle.secondary)

    async def callback(self, interaction: discord.Interaction):
        admin_panel = SystemAdminPanel(self.user_id)
        embed = await admin_panel._create_music_settings_embed(self.guild, interaction.client)
        view = MusicSettingsView(self.user_id, self.guild)
        await interaction.response.edit_message(embed=embed, view=view)


class FiveMSettingsBaseView(View):
    """FiveM 狀態設定共用基底"""

    def __init__(self, user_id: int, guild: discord.Guild, timeout=300):
        super().__init__(timeout=timeout)
        self.user_id = user_id
        self.guild = guild
        self.dao = FiveMDAO()

    async def _build_payload(self, **patch) -> dict:
        current = await self.dao.get_fivem_settings(self.guild.id)
        payload = {
            "info_url": current.get("info_url"),
            "players_url": current.get("players_url"),
            "status_channel_id": current.get("status_channel_id", 0),
            "alert_role_ids": current.get("alert_role_ids", []),
            "dm_role_ids": current.get("dm_role_ids", []),
            "panel_message_id": current.get("panel_message_id", 0),
            "poll_interval": current.get("poll_interval"),
            "server_link": current.get("server_link"),
            "status_image_url": current.get("status_image_url"),
        }
        payload.update(patch)
        return payload

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.user_id:
            await interaction.response.send_message(
                "❌ 只有指令使用者可以操作此面板", ephemeral=True
            )
            return False
        if await _has_system_admin_access(interaction):
            return True
        await interaction.response.send_message("❌ 需要管理伺服器權限或已授權管理員", ephemeral=True)
        return False

    async def _return_to_menu(self, interaction: discord.Interaction) -> None:
        panel = SystemAdminPanel(self.user_id)
        embed = await panel._create_fivem_settings_embed(self.guild, interaction.client)
        view = FiveMSettingsView(self.user_id, self.guild)
        await interaction.response.edit_message(embed=embed, view=view)


class FiveMSettingsView(FiveMSettingsBaseView):
    """FiveM 狀態設定主選單"""

    @button(label="⚙️ 基礎設定", style=discord.ButtonStyle.secondary, row=0)
    async def open_basic(self, interaction: discord.Interaction, button: Button):
        panel = SystemAdminPanel(self.user_id)
        embed = await panel._create_fivem_settings_embed(self.guild, interaction.client)
        view = FiveMBasicSettingsView(self.user_id, self.guild)
        await interaction.response.edit_message(embed=embed, view=view)

    @button(label="🔔 通知設定", style=discord.ButtonStyle.secondary, row=0)
    async def open_notify(self, interaction: discord.Interaction, button: Button):
        panel = SystemAdminPanel(self.user_id)
        embed = await panel._create_fivem_settings_embed(self.guild, interaction.client)
        view = FiveMNotifySettingsView(self.user_id, self.guild)
        await interaction.response.edit_message(embed=embed, view=view)

    @button(label="🧩 面板設定", style=discord.ButtonStyle.secondary, row=0)
    async def open_panel(self, interaction: discord.Interaction, button: Button):
        panel = SystemAdminPanel(self.user_id)
        embed = await panel._create_fivem_settings_embed(self.guild, interaction.client)
        view = FiveMPanelSettingsView(self.user_id, self.guild)
        await interaction.response.edit_message(embed=embed, view=view)

    @button(label="🔧 維護", style=discord.ButtonStyle.secondary, row=0)
    async def open_maintenance(self, interaction: discord.Interaction, button: Button):
        panel = SystemAdminPanel(self.user_id)
        embed = await panel._create_fivem_settings_embed(self.guild, interaction.client)
        view = FiveMMaintenanceSettingsView(self.user_id, self.guild)
        await interaction.response.edit_message(embed=embed, view=view)

    @button(label="🔄 重新整理", style=discord.ButtonStyle.secondary, row=1)
    async def refresh_button(self, interaction: discord.Interaction, button: Button):
        panel = SystemAdminPanel(self.user_id)
        embed = await panel._create_fivem_settings_embed(self.guild, interaction.client)
        await interaction.response.edit_message(embed=embed, view=self)

    @button(label="❌ 關閉", style=discord.ButtonStyle.danger, row=1)
    async def close_button(self, interaction: discord.Interaction, button: Button):
        embed = discord.Embed(title="✅ FiveM 狀態設定已關閉", color=0x95A5A6)
        await interaction.response.edit_message(embed=embed, view=None)


class FiveMBasicSettingsView(FiveMSettingsBaseView):
    """FiveM 基礎設定"""

    @button(label="📣 播報頻道", style=discord.ButtonStyle.secondary, row=0)
    async def set_status_channel(self, interaction: discord.Interaction, button: Button):
        self.clear_items()
        self.add_item(FiveMStatusChannelSelect(self, row=0))
        self.add_item(BackToFiveMSettingsButton(self.user_id, self.guild))

        embed = discord.Embed(
            title="📣 選擇 FiveM 播報頻道",
            description="選擇一個文字頻道作為狀態播報用。",
            color=0x3498DB,
        )
        await interaction.response.edit_message(embed=embed, view=self)

    @button(label="🌐 API URL", style=discord.ButtonStyle.secondary, row=0)
    async def set_api_url(self, interaction: discord.Interaction, button: Button):
        settings = await self.dao.get_fivem_settings(self.guild.id)
        await interaction.response.send_modal(
            FiveMApiUrlModal(
                self,
                settings.get("info_url"),
                settings.get("players_url"),
            )
        )

    @button(label="⏱️ 輪詢間隔", style=discord.ButtonStyle.secondary, row=0)
    async def set_poll_interval(self, interaction: discord.Interaction, button: Button):
        settings = await self.dao.get_fivem_settings(self.guild.id)
        await interaction.response.send_modal(
            FiveMPollIntervalModal(self, settings.get("poll_interval"))
        )

    @button(label="← 返回", style=discord.ButtonStyle.secondary, row=1)
    async def back_button(self, interaction: discord.Interaction, button: Button):
        await self._return_to_menu(interaction)


class FiveMNotifySettingsView(FiveMSettingsBaseView):
    """FiveM 通知設定"""

    @button(label="🔔 狀態通知身分組", style=discord.ButtonStyle.secondary, row=0)
    async def set_alert_roles(self, interaction: discord.Interaction, button: Button):
        self.clear_items()
        self.add_item(FiveMAlertRoleSelect(self, row=0))
        self.add_item(BackToFiveMSettingsButton(self.user_id, self.guild))

        embed = discord.Embed(
            title="🔔 設定狀態通知身分組",
            description="狀態更新時在頻道標註的身分組（可多選）",
            color=0x3498DB,
        )
        await interaction.response.edit_message(embed=embed, view=self)

    @button(label="📩 DM 通知身分組", style=discord.ButtonStyle.secondary, row=0)
    async def set_dm_roles(self, interaction: discord.Interaction, button: Button):
        self.clear_items()
        self.add_item(FiveMDmRoleSelect(self, row=0))
        self.add_item(BackToFiveMSettingsButton(self.user_id, self.guild))

        embed = discord.Embed(
            title="📩 設定 DM 通知身分組",
            description="異常時會私訊通知的身分組（可多選）",
            color=0x3498DB,
        )
        await interaction.response.edit_message(embed=embed, view=self)

    @button(label="🧹 清除狀態通知", style=discord.ButtonStyle.secondary, row=1)
    async def clear_alert_roles(self, interaction: discord.Interaction, button: Button):
        payload = await self._build_payload(alert_role_ids=[])
        success = await self.dao.update_fivem_settings(self.guild.id, payload)
        if success:
            await interaction.response.send_message("✅ 已清除狀態通知身分組", ephemeral=True)
        else:
            await interaction.response.send_message("❌ 清除失敗", ephemeral=True)

    @button(label="🧹 清除 DM 通知", style=discord.ButtonStyle.secondary, row=1)
    async def clear_dm_roles(self, interaction: discord.Interaction, button: Button):
        payload = await self._build_payload(dm_role_ids=[])
        success = await self.dao.update_fivem_settings(self.guild.id, payload)
        if success:
            await interaction.response.send_message("✅ 已清除 DM 通知身分組", ephemeral=True)
        else:
            await interaction.response.send_message("❌ 清除失敗", ephemeral=True)

    @button(label="← 返回", style=discord.ButtonStyle.secondary, row=2)
    async def back_button(self, interaction: discord.Interaction, button: Button):
        await self._return_to_menu(interaction)


class FiveMPanelSettingsView(FiveMSettingsBaseView):
    """FiveM 面板設定"""

    @button(label="🔗 伺服器連結", style=discord.ButtonStyle.secondary, row=0)
    async def set_server_link(self, interaction: discord.Interaction, button: Button):
        settings = await self.dao.get_fivem_settings(self.guild.id)
        await interaction.response.send_modal(
            FiveMServerLinkModal(self, settings.get("server_link"))
        )

    @button(label="🖼️ 狀態圖片", style=discord.ButtonStyle.secondary, row=0)
    async def set_status_image(self, interaction: discord.Interaction, button: Button):
        settings = await self.dao.get_fivem_settings(self.guild.id)
        await interaction.response.send_modal(
            FiveMStatusImageModal(self, settings.get("status_image_url"))
        )

    @button(label="📌 部署/更新面板", style=discord.ButtonStyle.secondary, row=0)
    async def deploy_status_panel(self, interaction: discord.Interaction, button: Button):
        fivem_cog = interaction.client.get_cog("FiveMStatusCore")
        if not fivem_cog or not hasattr(fivem_cog, "deploy_status_panel"):
            await interaction.response.send_message("❌ FiveM 狀態系統未啟用", ephemeral=True)
            return

        success = await fivem_cog.deploy_status_panel(interaction.guild)
        if success:
            panel = SystemAdminPanel(self.user_id)
            embed = await panel._create_fivem_settings_embed(self.guild, interaction.client)
            await interaction.response.edit_message(embed=embed, view=self)
        else:
            await interaction.response.send_message("❌ 部署失敗，請檢查播報頻道設定", ephemeral=True)

    @button(label="← 返回", style=discord.ButtonStyle.secondary, row=1)
    async def back_button(self, interaction: discord.Interaction, button: Button):
        await self._return_to_menu(interaction)


class FiveMMaintenanceSettingsView(FiveMSettingsBaseView):
    """FiveM 維護設定"""

    @button(label="🔄 重讀 FiveM Core", style=discord.ButtonStyle.secondary, row=0)
    async def reload_fivem_core(self, interaction: discord.Interaction, button: Button):
        fivem_cog = interaction.client.get_cog("FiveMStatusCore")
        if not fivem_cog or not hasattr(fivem_cog, "reload_guild"):
            await interaction.response.send_message("❌ FiveM 狀態系統未啟用", ephemeral=True)
            return

        success = await fivem_cog.reload_guild(interaction.guild)
        if success:
            panel = SystemAdminPanel(self.user_id)
            embed = await panel._create_fivem_settings_embed(self.guild, interaction.client)
            await interaction.response.edit_message(embed=embed, view=self)
        else:
            await interaction.response.send_message("❌ 重讀失敗，請稍後再試", ephemeral=True)

    @button(label="🧹 清除設定", style=discord.ButtonStyle.secondary, row=0)
    async def clear_settings(self, interaction: discord.Interaction, button: Button):
        payload = await self._build_payload(
            status_channel_id=0,
            panel_message_id=0,
            alert_role_ids=[],
            dm_role_ids=[],
            info_url=None,
            players_url=None,
            poll_interval=None,
            server_link=None,
            status_image_url=None,
        )
        success = await self.dao.update_fivem_settings(self.guild.id, payload)
        if success:
            await interaction.response.send_message("✅ 已清除 FiveM 設定", ephemeral=True)
        else:
            await interaction.response.send_message("❌ 清除設定失敗", ephemeral=True)

    @button(label="← 返回", style=discord.ButtonStyle.secondary, row=1)
    async def back_button(self, interaction: discord.Interaction, button: Button):
        await self._return_to_menu(interaction)


class FiveMServerLinkModal(Modal):
    """設定 FiveM 伺服器連結"""

    def __init__(self, parent_view: FiveMSettingsBaseView, server_link: str | None):
        super().__init__(title="設定伺服器連結")
        self.parent_view = parent_view
        self.server_link = TextInput(
            label="伺服器連結 (http/https)",
            placeholder="https://cfx.re/join/xxxxxx",
            default=server_link or "",
            required=False,
            max_length=200,
        )
        self.add_item(self.server_link)

    async def on_submit(self, interaction: discord.Interaction):
        raw_link = self.server_link.value.strip()
        if raw_link and not (raw_link.startswith("http://") or raw_link.startswith("https://")):
            await interaction.response.send_message("❌ 請輸入有效的 http/https 連結", ephemeral=True)
            return

        payload = await self.parent_view._build_payload(
            server_link=raw_link or None,
        )
        success = await self.parent_view.dao.update_fivem_settings(
            self.parent_view.guild.id, payload
        )
        if success:
            await interaction.response.send_message("✅ 已更新伺服器連結", ephemeral=True)
        else:
            await interaction.response.send_message("❌ 更新失敗，請稍後再試", ephemeral=True)


class FiveMApiUrlModal(Modal):
    """設定 FiveM API URL"""

    def __init__(
        self,
        parent_view: FiveMSettingsBaseView,
        info_url: str | None,
        players_url: str | None,
    ):
        super().__init__(title="設定 FiveM API URL")
        self.parent_view = parent_view
        self.info_url = TextInput(
            label="info.json URL",
            placeholder="http://your-server:30120/info.json",
            default=info_url or "",
            required=False,
            max_length=200,
        )
        self.players_url = TextInput(
            label="players.json URL",
            placeholder="http://your-server:30120/players.json",
            default=players_url or "",
            required=False,
            max_length=200,
        )
        self.add_item(self.info_url)
        self.add_item(self.players_url)

    async def on_submit(self, interaction: discord.Interaction):
        info_url = self.info_url.value.strip()
        players_url = self.players_url.value.strip()
        for url in (info_url, players_url):
            if url and not (url.startswith("http://") or url.startswith("https://")):
                await interaction.response.send_message("❌ 請輸入有效的 http/https 連結", ephemeral=True)
                return

        payload = await self.parent_view._build_payload(
            info_url=info_url or None,
            players_url=players_url or None,
        )
        success = await self.parent_view.dao.update_fivem_settings(
            self.parent_view.guild.id, payload
        )
        if success:
            note = ""
            if bool(info_url) ^ bool(players_url):
                note = "（需同時設定 info.json 與 players.json 才會啟用輪詢）"
            await interaction.response.send_message(f"✅ 已更新 API URL{note}", ephemeral=True)
        else:
            await interaction.response.send_message("❌ 更新失敗，請稍後再試", ephemeral=True)


class FiveMPollIntervalModal(Modal):
    """設定 FiveM 輪詢間隔"""

    def __init__(self, parent_view: FiveMSettingsBaseView, poll_interval: int | None):
        super().__init__(title="設定輪詢間隔")
        self.parent_view = parent_view
        default_value = str(poll_interval) if poll_interval else ""
        self.poll_interval = TextInput(
            label="輪詢間隔（秒）",
            placeholder="留空使用預設值",
            default=default_value,
            required=False,
            max_length=5,
        )
        self.add_item(self.poll_interval)

    async def on_submit(self, interaction: discord.Interaction):
        raw_value = self.poll_interval.value.strip()
        if raw_value:
            try:
                interval = int(raw_value)
            except ValueError:
                await interaction.response.send_message("❌ 請輸入有效的整數秒數", ephemeral=True)
                return
            if interval < 3:
                await interaction.response.send_message("❌ 輪詢間隔最小為 3 秒", ephemeral=True)
                return
        else:
            interval = None

        payload = await self.parent_view._build_payload(poll_interval=interval)
        success = await self.parent_view.dao.update_fivem_settings(
            self.parent_view.guild.id, payload
        )
        if success:
            await interaction.response.send_message("✅ 已更新輪詢間隔", ephemeral=True)
        else:
            await interaction.response.send_message("❌ 更新失敗，請稍後再試", ephemeral=True)


class FiveMStatusImageModal(Modal):
    """設定 FiveM 狀態圖片"""

    def __init__(self, parent_view: FiveMSettingsBaseView, image_url: str | None):
        super().__init__(title="設定狀態圖片")
        self.parent_view = parent_view
        self.image_url = TextInput(
            label="圖片 URL (http/https)",
            placeholder="https://example.com/status.png",
            default=image_url or "",
            required=False,
            max_length=300,
        )
        self.add_item(self.image_url)

    async def on_submit(self, interaction: discord.Interaction):
        raw_url = self.image_url.value.strip()
        if raw_url and not (raw_url.startswith("http://") or raw_url.startswith("https://")):
            await interaction.response.send_message("❌ 請輸入有效的 http/https 圖片連結", ephemeral=True)
            return

        payload = await self.parent_view._build_payload(
            status_image_url=raw_url or None,
        )
        success = await self.parent_view.dao.update_fivem_settings(
            self.parent_view.guild.id, payload
        )
        if success:
            await interaction.response.send_message("✅ 已更新狀態圖片", ephemeral=True)
        else:
            await interaction.response.send_message("❌ 更新失敗，請稍後再試", ephemeral=True)


class FiveMStatusChannelSelect(discord.ui.ChannelSelect):
    """FiveM 狀態播報頻道選擇器"""

    def __init__(self, parent_view: FiveMSettingsBaseView, row: int | None = None):
        self.parent_view = parent_view
        super().__init__(
            placeholder="選擇播報頻道...",
            min_values=1,
            max_values=1,
            channel_types=[discord.ChannelType.text],
            row=row,
        )

    async def callback(self, interaction: discord.Interaction):
        channel = self.values[0]
        payload = await self.parent_view._build_payload(status_channel_id=channel.id)
        success = await self.parent_view.dao.update_fivem_settings(
            self.parent_view.guild.id, payload
        )
        if success:
            admin_panel = SystemAdminPanel(self.parent_view.user_id)
            embed = await admin_panel._create_fivem_settings_embed(
                self.parent_view.guild, interaction.client
            )
            view = FiveMSettingsView(self.parent_view.user_id, self.parent_view.guild)
            await interaction.response.edit_message(embed=embed, view=view)
        else:
            await interaction.response.send_message("❌ 設定失敗，請稍後再試", ephemeral=True)


class FiveMAlertRoleSelect(discord.ui.RoleSelect):
    """FiveM 狀態通知身分組選擇器"""

    def __init__(self, parent_view: FiveMSettingsBaseView, row: int | None = None):
        self.parent_view = parent_view
        super().__init__(
            placeholder="選擇狀態通知身分組（可多選）",
            min_values=1,
            max_values=10,
            row=row,
        )

    async def callback(self, interaction: discord.Interaction):
        role_ids = [role.id for role in self.values]
        payload = await self.parent_view._build_payload(alert_role_ids=role_ids)
        success = await self.parent_view.dao.update_fivem_settings(
            self.parent_view.guild.id, payload
        )
        if success:
            admin_panel = SystemAdminPanel(self.parent_view.user_id)
            embed = await admin_panel._create_fivem_settings_embed(
                self.parent_view.guild, interaction.client
            )
            view = FiveMSettingsView(self.parent_view.user_id, self.parent_view.guild)
            await interaction.response.edit_message(embed=embed, view=view)
        else:
            await interaction.response.send_message("❌ 設定失敗，請稍後再試", ephemeral=True)


class FiveMDmRoleSelect(discord.ui.RoleSelect):
    """FiveM DM 通知身分組選擇器"""

    def __init__(self, parent_view: FiveMSettingsBaseView, row: int | None = None):
        self.parent_view = parent_view
        super().__init__(
            placeholder="選擇 DM 通知身分組（可多選）",
            min_values=1,
            max_values=10,
            row=row,
        )

    async def callback(self, interaction: discord.Interaction):
        role_ids = [role.id for role in self.values]
        payload = await self.parent_view._build_payload(dm_role_ids=role_ids)
        success = await self.parent_view.dao.update_fivem_settings(
            self.parent_view.guild.id, payload
        )
        if success:
            admin_panel = SystemAdminPanel(self.parent_view.user_id)
            embed = await admin_panel._create_fivem_settings_embed(
                self.parent_view.guild, interaction.client
            )
            view = FiveMSettingsView(self.parent_view.user_id, self.parent_view.guild)
            await interaction.response.edit_message(embed=embed, view=view)
        else:
            await interaction.response.send_message("❌ 設定失敗，請稍後再試", ephemeral=True)


class BackToFiveMSettingsButton(Button):
    """返回 FiveM 設定按鈕"""

    def __init__(self, user_id: int, guild: discord.Guild):
        self.user_id = user_id
        self.guild = guild
        super().__init__(label="← 返回", style=discord.ButtonStyle.secondary)

    async def callback(self, interaction: discord.Interaction):
        admin_panel = SystemAdminPanel(self.user_id)
        embed = await admin_panel._create_fivem_settings_embed(self.guild, interaction.client)
        view = FiveMSettingsView(self.user_id, self.guild)
        await interaction.response.edit_message(embed=embed, view=view)


class VoteChannelSelect(discord.ui.ChannelSelect):
    """投票頻道選擇器"""

    def __init__(self, user_id: int):
        self.user_id = user_id
        super().__init__(
            placeholder="選擇預設投票頻道...",
            min_values=1,
            max_values=1,
            channel_types=[discord.ChannelType.text],
        )

    async def callback(self, interaction: discord.Interaction):
        channel = self.values[0]
        success = await vote_dao.set_default_vote_channel(interaction.guild.id, channel.id)

        if success:
            embed = discord.Embed(
                title="✅ 投票頻道設定成功",
                description=f"預設投票頻道已設定為 {channel.mention}",
                color=0x2ECC71,
            )
            embed.add_field(
                name="📋 說明",
                value="新建立的投票將自動發布到此頻道",
                inline=False,
            )
        else:
            embed = discord.Embed(
                title="❌ 設定失敗",
                description="設定投票頻道時發生錯誤",
                color=0xE74C3C,
            )

        await interaction.response.send_message(embed=embed, ephemeral=True)


class AnnounceChannelSelect(discord.ui.ChannelSelect):
    """投票結果公告頻道選擇器"""

    def __init__(self, user_id: int):
        self.user_id = user_id
        super().__init__(
            placeholder="選擇投票結果公告頻道...",
            min_values=1,
            max_values=1,
            channel_types=[discord.ChannelType.text],
        )

    async def callback(self, interaction: discord.Interaction):
        channel = self.values[0]
        success = await vote_dao.set_announcement_channel(interaction.guild.id, channel.id)

        if success:
            embed = discord.Embed(
                title="✅ 公告頻道設定成功",
                description=f"投票結果公告頻道已設定為 {channel.mention}",
                color=0x2ECC71,
            )
            embed.add_field(
                name="📋 說明",
                value="投票結束後的結果將自動公告到此頻道",
                inline=False,
            )
        else:
            embed = discord.Embed(
                title="❌ 設定失敗",
                description="設定公告頻道時發生錯誤",
                color=0xE74C3C,
            )

        await interaction.response.send_message(embed=embed, ephemeral=True)


class BackToVoteSettingsButton(Button):
    """返回投票設定按鈕"""

    def __init__(self, user_id: int):
        self.user_id = user_id
        super().__init__(label="← 返回", style=discord.ButtonStyle.secondary)

    async def callback(self, interaction: discord.Interaction):
        from potato_bot.views.system_admin_views import SystemAdminPanel

        admin_panel = SystemAdminPanel(self.user_id)
        embed = await admin_panel._create_vote_settings_embed(interaction.guild)
        view = VoteSettingsView(self.user_id)
        await interaction.response.edit_message(embed=embed, view=view)


class ChannelClearView(View):
    """頻道清空界面"""

    def __init__(self, user_id: int, timeout=300):
        super().__init__(timeout=timeout)
        self.user_id = user_id
        self.selected_channel = None

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        try:
            if interaction.user.id != self.user_id:
                await interaction.response.send_message(
                    "❌ 只有指令使用者可以操作此面板", ephemeral=True
                )
                return False

            if not interaction.user.guild_permissions.manage_messages:
                await interaction.response.send_message("❌ 需要管理訊息權限", ephemeral=True)
                return False

            return True
        except Exception as e:
            logger.error(f"ChannelClearView interaction_check 錯誤: {e}")
            return False


class ChannelClearSelect(Select):
    """頻道清空選擇器"""

    def __init__(self, user_id: int, guild: discord.Guild):
        self.user_id = user_id

        # 獲取所有文字頻道並建立選項
        text_channels = [ch for ch in guild.channels if isinstance(ch, discord.TextChannel)]

        if not text_channels:
            options = [
                discord.SelectOption(
                    label="無可用頻道",
                    value="none",
                    description="沒有找到文字頻道",
                )
            ]
        else:
            options = []
            for channel in text_channels[:25]:  # Discord 限制最多25個選項
                options.append(
                    discord.SelectOption(
                        label=f"#{channel.name}",
                        value=str(channel.id),
                        description=f"ID: {channel.id}",
                    )
                )

        super().__init__(
            placeholder="選擇要清空的頻道...",
            min_values=1,
            max_values=1,
            options=options,
        )

    async def callback(self, interaction: discord.Interaction):
        try:
            # 檢查是否為無效選項
            if self.values[0] == "none":
                await interaction.response.send_message("❌ 沒有可用的頻道進行清空", ephemeral=True)
                return

            # 處理頻道選擇
            channel_id = int(self.values[0])
            selected_channel = interaction.guild.get_channel(channel_id)

            if not selected_channel:
                await interaction.response.send_message("❌ 找不到選擇的頻道", ephemeral=True)
                return

            # 設定選中的頻道
            if hasattr(self.view, "selected_channel"):
                self.view.selected_channel = selected_channel

            embed = discord.Embed(
                title="🗑️ 確認清空頻道",
                description=f"您選擇了頻道：{selected_channel.mention}\n" f"請選擇清空選項：",
                color=0xE74C3C,
            )

            embed.add_field(
                name="⚠️ 重要提醒",
                value="• 此操作無法復原\n"
                "• 將永久刪除頻道中的訊息\n"
                "• 請確認您有足夠的權限\n"
                "• 建議在低峰時段執行",
                inline=False,
            )

            # 清除選擇器，添加操作按鈕
            self.view.clear_items()
            self.view.add_item(ClearAllButton(self.user_id, selected_channel))
            self.view.add_item(ClearRecentButton(self.user_id, selected_channel))
            self.view.add_item(ClearByUserButton(self.user_id, selected_channel))
            self.view.add_item(BackToClearSelectButton(self.user_id))

            await interaction.response.edit_message(embed=embed, view=self.view)

        except Exception as e:
            logger.error(f"ChannelClearSelect callback 錯誤: {e}")
            try:
                if not interaction.response.is_done():
                    await interaction.response.send_message("❌ 選擇頻道時發生錯誤", ephemeral=True)
                else:
                    await interaction.followup.send("❌ 選擇頻道時發生錯誤", ephemeral=True)
            except:
                pass


class ClearAllButton(Button):
    """清空全部訊息按鈕"""

    def __init__(self, user_id: int, channel: discord.TextChannel):
        self.user_id = user_id
        self.channel = channel
        super().__init__(label="🗑️ 清空全部", style=discord.ButtonStyle.danger, row=0)

    async def callback(self, interaction: discord.Interaction):
        # 最終確認
        embed = discord.Embed(
            title="❗ 最終確認",
            description=f"您確定要清空 {self.channel.mention} 中的**所有訊息**嗎？",
            color=0xE74C3C,
        )

        embed.add_field(
            name="⚠️ 這將會：",
            value="• 刪除頻道中的所有訊息\n" "• 無法復原任何內容\n" "• 可能需要較長時間",
            inline=False,
        )

        view = FinalConfirmView(self.user_id, self.channel, "all")
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)


class ClearRecentButton(Button):
    """清空最近訊息按鈕"""

    def __init__(self, user_id: int, channel: discord.TextChannel):
        self.user_id = user_id
        self.channel = channel
        super().__init__(label="⏰ 清空近期", style=discord.ButtonStyle.secondary, row=0)

    async def callback(self, interaction: discord.Interaction):
        modal = ClearRecentModal(self.channel)
        await interaction.response.send_modal(modal)


class ClearByUserButton(Button):
    """按用戶清空訊息按鈕"""

    def __init__(self, user_id: int, channel: discord.TextChannel):
        self.user_id = user_id
        self.channel = channel
        super().__init__(label="👤 按用戶清空", style=discord.ButtonStyle.secondary, row=0)

    async def callback(self, interaction: discord.Interaction):
        modal = ClearByUserModal(self.channel)
        await interaction.response.send_modal(modal)


class BackToClearSelectButton(Button):
    """返回頻道選擇按鈕"""

    def __init__(self, user_id: int):
        self.user_id = user_id
        super().__init__(label="← 重新選擇", style=discord.ButtonStyle.secondary, row=1)

    async def callback(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="🗑️ 清空頻道訊息",
            description="選擇要清空的頻道和清空選項",
            color=0xE74C3C,
        )

        embed.add_field(
            name="⚠️ 警告",
            value="此操作將永久刪除頻道中的訊息，無法復原！\n請謹慎選擇要清空的頻道。",
            inline=False,
        )

        view = ChannelClearView(self.user_id)
        view.add_item(ChannelClearSelect(self.user_id, interaction.guild))
        await interaction.response.edit_message(embed=embed, view=view)


class FinalConfirmView(View):
    """最終確認視圖"""

    _PURGE_BATCH_SIZE = 100
    _BASE_DELAY_SECONDS = 2.0
    _MAX_BACKOFF_SECONDS = 30.0
    _DELETE_PAUSE_EVERY = 5

    def __init__(
        self,
        user_id: int,
        channel: discord.TextChannel,
        clear_type: str,
        timeout=60,
    ):
        super().__init__(timeout=timeout)
        self.user_id = user_id
        self.channel = channel
        self.clear_type = clear_type

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        return interaction.user.id == self.user_id

    @button(label="✅ 確認執行", style=discord.ButtonStyle.danger)
    async def confirm_button(self, interaction: discord.Interaction, button: Button):
        """確認執行清空"""
        await interaction.response.defer(ephemeral=True)

        try:
            # 開始清空過程
            embed = discord.Embed(
                title="🔄 正在清空頻道...",
                description=f"正在清空 {self.channel.mention}，請稍候...",
                color=0xF39C12,
            )

            await interaction.followup.send(embed=embed, ephemeral=True)

            # 執行清空
            deleted_count = 0
            if self.clear_type == "all":
                deleted_count = await self._clear_all_messages()
            elif self.clear_type.startswith("recent_"):
                hours = int(self.clear_type.split("_")[1])
                deleted_count = await self._clear_recent_messages(hours)
            elif self.clear_type.startswith("user_"):
                user_id = int(self.clear_type.split("_")[1])
                deleted_count = await self._clear_user_messages(user_id)

            # 完成提示
            embed = discord.Embed(
                title="✅ 清空完成",
                description=f"已成功清空 {self.channel.mention}",
                color=0x2ECC71,
            )

            embed.add_field(
                name="📊 清空統計",
                value=f"共刪除 {deleted_count} 條訊息",
                inline=False,
            )

            await interaction.followup.send(embed=embed, ephemeral=True)

        except discord.Forbidden:
            embed = discord.Embed(
                title="❌ 權限不足",
                description="Bot沒有足夠權限清空此頻道的訊息",
                color=0xE74C3C,
            )
            await interaction.followup.send(embed=embed, ephemeral=True)

        except Exception as e:
            embed = discord.Embed(
                title="❌ 清空失敗",
                description=f"清空過程中發生錯誤：{str(e)[:100]}",
                color=0xE74C3C,
            )
            await interaction.followup.send(embed=embed, ephemeral=True)

    @button(label="❌ 取消", style=discord.ButtonStyle.secondary)
    async def cancel_button(self, interaction: discord.Interaction, button: Button):
        """取消操作"""
        embed = discord.Embed(title="✅ 已取消", description="頻道清空操作已取消", color=0x95A5A6)
        await interaction.response.edit_message(embed=embed, view=None)

    def _extract_retry_after(self, error: discord.HTTPException) -> float | None:
        retry_after = getattr(error, "retry_after", None)
        if retry_after is not None:
            try:
                return float(retry_after)
            except (TypeError, ValueError):
                pass

        response = getattr(error, "response", None)
        headers = getattr(response, "headers", None)
        if headers:
            value = headers.get("Retry-After") or headers.get("retry-after")
            if value is not None:
                try:
                    return float(value)
                except (TypeError, ValueError):
                    return None
        return None

    async def _sleep_rate_limited(self, error: discord.HTTPException, backoff: float) -> float:
        retry_after = self._extract_retry_after(error)
        if retry_after is not None:
            delay = max(retry_after, self._BASE_DELAY_SECONDS)
            backoff = min(max(backoff, delay), self._MAX_BACKOFF_SECONDS)
        else:
            backoff = min(backoff * 2, self._MAX_BACKOFF_SECONDS)
            delay = backoff

        logger.warning(f"⚠️ 清理訊息觸發 rate limit，等待 {delay:.1f} 秒後重試")
        await asyncio.sleep(delay)
        return backoff

    async def _purge_with_backoff(self, *, check=None, after=None) -> int:
        deleted_count = 0
        backoff = self._BASE_DELAY_SECONDS

        while True:
            try:
                deleted = await self.channel.purge(
                    limit=self._PURGE_BATCH_SIZE,
                    check=check,
                    after=after,
                )
            except discord.HTTPException as e:
                if e.status == 429:
                    backoff = await self._sleep_rate_limited(e, backoff)
                    continue
                raise

            if not deleted:
                break

            deleted_count += len(deleted)
            backoff = self._BASE_DELAY_SECONDS
            await asyncio.sleep(self._BASE_DELAY_SECONDS)

        return deleted_count

    async def _delete_messages_slowly(self, messages, *, predicate=None) -> int:
        deleted_count = 0
        backoff = self._BASE_DELAY_SECONDS

        async for message in messages:
            if predicate is not None and not predicate(message):
                continue

            while True:
                try:
                    await message.delete()
                    deleted_count += 1
                    break
                except discord.NotFound:
                    break
                except discord.Forbidden:
                    return deleted_count
                except discord.HTTPException as e:
                    if e.status == 429:
                        backoff = await self._sleep_rate_limited(e, backoff)
                        continue
                    return deleted_count

            if deleted_count % self._DELETE_PAUSE_EVERY == 0:
                await asyncio.sleep(self._BASE_DELAY_SECONDS)
                backoff = self._BASE_DELAY_SECONDS

        return deleted_count

    async def _clear_all_messages(self) -> int:
        """清空所有訊息"""
        try:
            # Discord限制：purge一次最多刪除100條訊息，且訊息不能超過14天
            return await self._purge_with_backoff(check=lambda m: True)
        except discord.HTTPException:
            # 如果purge失敗，嘗試逐個刪除（較慢但更可靠）
            return await self._delete_messages_slowly(self.channel.history(limit=None))

    async def _clear_recent_messages(self, hours: int) -> int:
        """清空最近指定小時內的訊息"""
        from datetime import datetime, timedelta, timezone

        cutoff_time = datetime.now(timezone.utc) - timedelta(hours=hours)
        deleted_count = 0

        try:
            # 使用purge刪除最近的訊息
            def check_time(message):
                return message.created_at > cutoff_time

            deleted_count = await self._purge_with_backoff(check=check_time)
            return deleted_count

        except discord.HTTPException:
            # 如果purge失敗，嘗試逐個刪除
            return await self._delete_messages_slowly(
                self.channel.history(limit=None, after=cutoff_time)
            )

    async def _clear_user_messages(self, user_id: int) -> int:
        """清空指定用戶的所有訊息"""
        try:
            # 使用purge刪除指定用戶的訊息
            def check_user(message):
                return message.author.id == user_id

            return await self._purge_with_backoff(check=check_user)

        except discord.HTTPException:
            # 如果purge失敗，嘗試逐個刪除
            return await self._delete_messages_slowly(
                self.channel.history(limit=None),
                predicate=lambda message: message.author.id == user_id,
            )


class ClearRecentModal(Modal):
    """清空近期訊息表單"""

    def __init__(self, channel: discord.TextChannel):
        self.channel = channel
        super().__init__(title="⏰ 清空近期訊息")

        self.hours = TextInput(
            label="清空多少小時內的訊息",
            placeholder="輸入小時數 (例如: 24)",
            min_length=1,
            max_length=3,
            required=True,
        )

        self.add_item(self.hours)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            hours = int(self.hours.value)
            if hours <= 0 or hours > 168:  # 最多7天
                await interaction.response.send_message("❌ 小時數必須在1-168之間", ephemeral=True)
                return

            embed = discord.Embed(
                title="❗ 確認清空近期訊息",
                description=f"將清空 {self.channel.mention} 中最近 {hours} 小時內的訊息",
                color=0xE74C3C,
            )

            embed.add_field(
                name="⚠️ 注意",
                value=f"• 將刪除 {hours} 小時內的所有訊息\n"
                "• 此操作無法復原\n"
                "• 請確認選擇正確",
                inline=False,
            )

            view = FinalConfirmView(interaction.user.id, self.channel, f"recent_{hours}")
            await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

        except ValueError:
            await interaction.response.send_message("❌ 請輸入有效的數字", ephemeral=True)


class ClearByUserModal(Modal):
    """按用戶清空訊息表單"""

    def __init__(self, channel: discord.TextChannel):
        self.channel = channel
        super().__init__(title="👤 按用戶清空訊息")

        self.user_id = TextInput(
            label="用戶ID或@用戶",
            placeholder="輸入用戶ID或@提及用戶",
            min_length=1,
            max_length=100,
            required=True,
        )

        self.add_item(self.user_id)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            user_input = self.user_id.value.strip()

            # 解析用戶ID或提及
            target_user = None
            if user_input.startswith("<@") and user_input.endswith(">"):
                # 處理提及格式 <@123456789> 或 <@!123456789>
                user_id_str = user_input[2:-1]
                if user_id_str.startswith("!"):
                    user_id_str = user_id_str[1:]
                try:
                    user_id = int(user_id_str)
                    target_user = interaction.guild.get_member(user_id)
                except ValueError:
                    pass
            else:
                # 嘗試直接解析為用戶ID
                try:
                    user_id = int(user_input)
                    target_user = interaction.guild.get_member(user_id)
                except ValueError:
                    pass

            if not target_user:
                await interaction.response.send_message(
                    "❌ 找不到指定的用戶，請檢查用戶ID或@提及格式",
                    ephemeral=True,
                )
                return

            embed = discord.Embed(
                title="❗ 確認按用戶清空訊息",
                description=f"將清空 {self.channel.mention} 中 {target_user.mention} 的所有訊息",
                color=0xE74C3C,
            )

            embed.add_field(
                name="⚠️ 注意",
                value="• 將刪除該用戶的所有歷史訊息\n"
                "• 此操作無法復原\n"
                "• 可能需要較長時間處理",
                inline=False,
            )

            view = FinalConfirmView(interaction.user.id, self.channel, f"user_{target_user.id}")
            await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

        except Exception as e:
            logger.error(f"ClearByUserModal 錯誤: {e}")
            await interaction.response.send_message("❌ 處理用戶輸入時發生錯誤", ephemeral=True)


class DataCleanupView(View):
    """資料清理界面"""

    def __init__(self, user_id: int, timeout=300):
        super().__init__(timeout=timeout)
        self.user_id = user_id
        self.cleanup_manager = DataCleanupManager()

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        return interaction.user.id == self.user_id

    @button(label="🗑️ 基礎清理", style=discord.ButtonStyle.secondary)
    async def basic_cleanup_button(self, interaction: discord.Interaction, button: Button):
        """執行基礎清理"""
        await interaction.response.defer(ephemeral=True)

        try:
            embed = discord.Embed(
                title="🔄 正在執行基礎清理...",
                description="清理過程可能需要幾分鐘，請稍候",
                color=0xF39C12,
            )
            await interaction.followup.send(embed=embed, ephemeral=True)

            # 執行基礎清理
            result = await self.cleanup_manager.run_basic_cleanup()

            if result.success:
                embed = discord.Embed(
                    title="✅ 基礎清理完成",
                    description="已成功完成基礎資料清理",
                    color=0x2ECC71,
                )
                embed.add_field(
                    name="📊 清理結果",
                    value=f"清理的資料項目: {result.cleaned_items}\n"
                    f"釋放空間: {result.space_freed_mb:.2f} MB\n"
                    f"耗時: {result.duration_seconds:.2f} 秒",
                    inline=False,
                )
                if result.details:
                    embed.add_field(
                        name="📋 詳細信息",
                        value="\n".join([f"• {detail}" for detail in result.details[:5]]),
                        inline=False,
                    )
            else:
                embed = discord.Embed(
                    title="❌ 清理失敗",
                    description=f"清理過程中發生錯誤：{result.error}",
                    color=0xE74C3C,
                )

            await interaction.followup.send(embed=embed, ephemeral=True)

        except Exception as e:
            logger.error(f"基礎清理錯誤: {e}")
            embed = discord.Embed(
                title="❌ 清理失敗",
                description=f"清理過程中發生意外錯誤：{str(e)[:100]}",
                color=0xE74C3C,
            )
            await interaction.followup.send(embed=embed, ephemeral=True)

    @button(label="🔧 深度清理", style=discord.ButtonStyle.primary)
    async def full_cleanup_button(self, interaction: discord.Interaction, button: Button):
        """執行深度清理"""
        # 確認對話框
        embed = discord.Embed(
            title="⚠️ 深度清理確認",
            description="深度清理會執行以下操作：",
            color=0xF39C12,
        )
        embed.add_field(
            name="🔧 清理內容",
            value="• 清理所有過期資料\n" "• 優化資料庫索引\n" "• 重建統計快取\n" "• 清理系統日誌",
            inline=False,
        )
        embed.add_field(name="⏰ 預計時間", value="5-15 分鐘（取決於資料量）", inline=True)
        embed.add_field(name="⚠️ 注意事項", value="清理期間系統性能可能受影響", inline=True)

        view = ConfirmCleanupView(self.user_id)
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)


class ConfirmCleanupView(View):
    """確認清理視圖"""

    def __init__(self, user_id: int, timeout=60):
        super().__init__(timeout=timeout)
        self.user_id = user_id
        self.cleanup_manager = DataCleanupManager()

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        return interaction.user.id == self.user_id

    @button(label="✅ 確認執行", style=discord.ButtonStyle.danger)
    async def confirm_button(self, interaction: discord.Interaction, button: Button):
        """確認執行深度清理"""
        await interaction.response.defer(ephemeral=True)

        try:
            embed = discord.Embed(
                title="🔄 正在執行深度清理...",
                description="深度清理正在進行中，這可能需要幾分鐘時間",
                color=0xF39C12,
            )
            embed.add_field(name="📋 當前狀態", value="正在分析資料庫...", inline=False)
            await interaction.followup.send(embed=embed, ephemeral=True)

            # 執行深度清理
            result = await self.cleanup_manager.run_full_cleanup()

            if result.success:
                embed = discord.Embed(
                    title="✅ 深度清理完成",
                    description="已成功完成深度資料清理和優化",
                    color=0x2ECC71,
                )
                embed.add_field(
                    name="📊 清理統計",
                    value=f"清理的資料項目: {result.cleaned_items:,}\n"
                    f"釋放空間: {result.space_freed_mb:.2f} MB\n"
                    f"優化表格: {len(result.details)}\n"
                    f"總耗時: {result.duration_seconds:.1f} 秒",
                    inline=False,
                )
                if result.details:
                    embed.add_field(
                        name="🔧 執行的操作",
                        value="\n".join([f"• {detail}" for detail in result.details[:8]]),
                        inline=False,
                    )
                embed.set_footer(text="建議定期執行深度清理以保持系統性能")
            else:
                embed = discord.Embed(
                    title="❌ 深度清理失敗",
                    description=f"清理過程中發生錯誤：{result.error}",
                    color=0xE74C3C,
                )
                embed.add_field(
                    name="💡 建議",
                    value="請稍後重試，或聯繫系統管理員",
                    inline=False,
                )

            await interaction.followup.send(embed=embed, ephemeral=True)

        except Exception as e:
            logger.error(f"深度清理錯誤: {e}")
            embed = discord.Embed(
                title="❌ 深度清理失敗",
                description=f"執行過程中發生意外錯誤：{str(e)[:100]}",
                color=0xE74C3C,
            )
            await interaction.followup.send(embed=embed, ephemeral=True)

    @button(label="❌ 取消", style=discord.ButtonStyle.secondary)
    async def cancel_button(self, interaction: discord.Interaction, button: Button):
        """取消清理操作"""
        embed = discord.Embed(
            title="✅ 已取消", description="深度清理操作已取消", color=0x95A5A6
        )
        await interaction.response.edit_message(embed=embed, view=None)


class VoteAdminView(View):
    """投票管理主面板"""

    def __init__(self, user_id: int = None, timeout=300):
        super().__init__(timeout=timeout)
        self.user_id = user_id

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        """檢查用戶權限"""
        if self.user_id and interaction.user.id != self.user_id:
            await interaction.response.send_message(
                "❌ 只有指令使用者可以操作此面板", ephemeral=True
            )
            return False

        if not interaction.user.guild_permissions.manage_messages:
            await interaction.response.send_message("❌ 需要管理訊息權限", ephemeral=True)
            return False

        return True

    @button(label="📋 查看活躍投票", style=discord.ButtonStyle.primary, row=0)
    async def view_active_votes_button(self, interaction: discord.Interaction, button: Button):
        """查看活躍投票按鈕"""
        try:
            await interaction.response.defer()

            votes = await vote_dao.get_active_votes(interaction.guild.id)

            if not votes:
                embed = discord.Embed(
                    title="📋 活躍投票",
                    description="目前沒有進行中的投票",
                    color=0x95A5A6,
                )
                await interaction.followup.send(embed=embed, ephemeral=True)
                return

            embed = discord.Embed(
                title="📋 活躍投票",
                description=f"找到 {len(votes)} 個進行中的投票",
                color=0x3498DB,
            )

            for vote in votes[:10]:  # 只顯示前10個
                vote_info = f"ID: {vote['id']}\n創建者: <@{vote['creator_id']}>\n結束時間: {vote['end_time'].strftime('%Y-%m-%d %H:%M')}"
                embed.add_field(
                    name=f"🗳️ {vote['title'][:50]}{'...' if len(vote['title']) > 50 else ''}",
                    value=vote_info,
                    inline=True,
                )

            view = ActiveVoteManageView(interaction.user.id)
            await interaction.followup.send(embed=embed, view=view, ephemeral=True)

        except Exception as e:
            logger.error(f"查看活躍投票錯誤: {e}")
            await interaction.followup.send("❌ 無法獲取投票資訊", ephemeral=True)

    @button(label="🛠️ 投票設定", style=discord.ButtonStyle.secondary, row=0)
    async def vote_settings_button(self, interaction: discord.Interaction, button: Button):
        """投票設定按鈕"""
        try:
            embed = discord.Embed(
                title="🛠️ 投票系統設定",
                description="投票系統功能管理",
                color=0xF39C12,
            )

            embed.add_field(
                name="ℹ️ 功能說明",
                value="• 投票系統已啟用並正常運作\n"
                "• 支援匿名和公開投票\n"
                "• 支援單選和多選模式",
                inline=False,
            )

            embed.add_field(
                name="⚙️ 系統狀態",
                value="🟢 投票系統: 已啟用\n" "🟢 資料庫: 連接正常",
                inline=False,
            )

            view = VoteSettingsView(interaction.user.id)
            await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

        except Exception as e:
            logger.error(f"投票設定錯誤: {e}")
            await interaction.response.send_message("❌ 無法載入投票設定", ephemeral=True)


class ActiveVoteManageView(View):
    """活躍投票管理介面"""

    def __init__(self, user_id: int, timeout=300):
        super().__init__(timeout=timeout)
        self.user_id = user_id

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        """檢查用戶權限"""
        if interaction.user.id != self.user_id:
            await interaction.response.send_message(
                "❌ 只有指令使用者可以操作此面板", ephemeral=True
            )
            return False

        if not interaction.user.guild_permissions.manage_messages:
            await interaction.response.send_message("❌ 需要管理訊息權限", ephemeral=True)
            return False

        return True

    @button(label="🗳️ 選擇投票管理", style=discord.ButtonStyle.secondary, row=0)
    async def select_vote_button(self, interaction: discord.Interaction, button: Button):
        """選擇要管理的投票"""
        try:
            active_votes = await vote_dao.get_active_votes(interaction.guild.id)

            if not active_votes:
                embed = discord.Embed(
                    title="📋 沒有活躍投票",
                    description="目前沒有進行中的投票",
                    color=0x95A5A6,
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return

            # 創建選擇下拉選單
            options = []
            for vote in active_votes[:25]:  # Discord 限制最多25個選項
                options.append(
                    discord.SelectOption(
                        label=f"#{vote['id']} - {vote['title'][:50]}",
                        value=str(vote["id"]),
                        description=f"結束: {vote['end_time'].strftime('%m-%d %H:%M')}",
                    )
                )

            self.clear_items()
            self.add_item(VoteManageSelect(self.user_id, options))
            self.add_item(BackToActiveVoteManageButton(self.user_id))

            embed = discord.Embed(
                title="🗳️ 選擇要管理的投票",
                description="請從下拉選單中選擇要管理的投票",
                color=0x3498DB,
            )

            await interaction.response.edit_message(embed=embed, view=self)

        except Exception as e:
            logger.error(f"選擇投票錯誤: {e}")
            await interaction.response.send_message("❌ 無法載入投票列表", ephemeral=True)

    @button(label="🔄 重新整理", style=discord.ButtonStyle.secondary, row=1)
    async def refresh_button(self, interaction: discord.Interaction, button: Button):
        """重新整理投票列表"""
        try:
            vote_settings_view = VoteSettingsView(self.user_id)
            embed = await vote_settings_view._create_active_votes_embed(interaction.guild)

            # 重新建立介面
            new_view = ActiveVoteManageView(self.user_id)

            await interaction.response.edit_message(embed=embed, view=new_view)

        except Exception as e:
            logger.error(f"重新整理錯誤: {e}")
            await interaction.response.send_message("❌ 重新整理失敗", ephemeral=True)

    @button(label="❌ 關閉", style=discord.ButtonStyle.danger, row=1)
    async def close_button(self, interaction: discord.Interaction, button: Button):
        """關閉按鈕"""
        embed = discord.Embed(title="✅ 投票管理已關閉", color=0x95A5A6)
        await interaction.response.edit_message(embed=embed, view=None)


class VoteManageSelect(Select):
    """投票管理選擇下拉選單"""

    def __init__(self, user_id: int, options):
        self.user_id = user_id
        super().__init__(
            placeholder="選擇要管理的投票...",
            options=options,
            min_values=1,
            max_values=1,
        )

    async def callback(self, interaction: discord.Interaction):
        vote_id = int(self.values[0])

        try:
            vote = await vote_dao.get_vote_by_id(vote_id)
            if not vote:
                await interaction.response.send_message("❌ 找不到該投票", ephemeral=True)
                return

            embed = discord.Embed(
                title=f"🗳️ 投票管理 - #{vote_id}",
                description=vote["title"],
                color=0x3498DB,
            )

            embed.add_field(
                name="📊 投票資訊",
                value=f"模式: {'匿名' if vote['anonymous'] else '公開'}{'多選' if vote['is_multi'] else '單選'}\n"
                f"結束時間: {vote['end_time'].strftime('%Y-%m-%d %H:%M')}",
                inline=False,
            )

            view = SingleVoteManageView(self.user_id, vote_id)
            await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

        except Exception as e:
            logger.error(f"獲取投票詳情錯誤: {e}")
            await interaction.response.send_message("❌ 無法獲取投票詳情", ephemeral=True)


class SingleVoteManageView(View):
    """單一投票管理介面"""

    def __init__(self, user_id: int, vote_id: int, timeout=300):
        super().__init__(timeout=timeout)
        self.user_id = user_id
        self.vote_id = vote_id

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        return interaction.user.id == self.user_id

    @button(label="🛑 強制結束", style=discord.ButtonStyle.danger, row=0)
    async def force_end_vote_button(self, interaction: discord.Interaction, button: Button):
        """強制結束投票"""
        try:
            # 確認對話框
            embed = discord.Embed(
                title="⚠️ 確認強制結束投票",
                description=f"你確定要強制結束投票 #{self.vote_id} 嗎？\n這個操作無法復原。",
                color=0xE74C3C,
            )

            view = VoteConfirmActionView(self.user_id, self.vote_id, "force_end")
            await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

        except Exception as e:
            logger.error(f"強制結束投票錯誤: {e}")
            await interaction.response.send_message("❌ 操作失敗", ephemeral=True)


class VoteConfirmActionView(View):
    """投票確認操作介面"""

    def __init__(self, user_id: int, vote_id: int, action_type: str, timeout=60):
        super().__init__(timeout=timeout)
        self.user_id = user_id
        self.vote_id = vote_id
        self.action_type = action_type

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        return interaction.user.id == self.user_id

    @button(label="✅ 確認", style=discord.ButtonStyle.danger)
    async def confirm_action(self, interaction: discord.Interaction, button: Button):
        """確認執行操作"""
        try:
            if self.action_type == "force_end":
                # 強制結束投票
                success = await vote_dao.end_vote(self.vote_id)

                if success:
                    # 發送結果通知
                    pass

                    vote_cog = interaction.client.get_cog("VoteCore")
                    if vote_cog:
                        try:
                            await vote_cog._send_vote_result(self.vote_id)
                        except Exception as e:
                            logger.error(f"發送投票結果錯誤: {e}")

                    embed = discord.Embed(
                        title="✅ 投票已強制結束",
                        description=f"投票 #{self.vote_id} 已成功結束並公告結果",
                        color=0x2ECC71,
                    )
                    await interaction.response.send_message(embed=embed, ephemeral=True)
                else:
                    await interaction.response.send_message("❌ 結束投票失敗", ephemeral=True)

        except Exception as e:
            logger.error(f"確認操作錯誤: {e}")
            await interaction.response.send_message("❌ 操作執行失敗", ephemeral=True)

    @button(label="❌ 取消", style=discord.ButtonStyle.secondary)
    async def cancel_action(self, interaction: discord.Interaction, button: Button):
        """取消操作"""
        embed = discord.Embed(
            title="❌ 操作已取消",
            description="沒有執行任何變更",
            color=0x95A5A6,
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)


class BackToActiveVoteManageButton(Button):
    """返回活躍投票管理按鈕"""

    def __init__(self, user_id: int):
        self.user_id = user_id
        super().__init__(label="← 返回", style=discord.ButtonStyle.secondary)

    async def callback(self, interaction: discord.Interaction):
        vote_settings_view = VoteSettingsView(self.user_id)
        embed = await vote_settings_view._create_active_votes_embed(interaction.guild)
        view = ActiveVoteManageView(self.user_id)
        await interaction.response.edit_message(embed=embed, view=view)
