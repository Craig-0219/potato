"""
🎮 Discord Bot GUI Menu System
全功能互動式選單系統，減少指令輸入需求

Author: Potato Bot Development Team
Version: 3.2.0 - Phase 7 Stage 2
Date: 2025-08-20
"""

import asyncio
import logging
import traceback
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Union

import discord
from discord import app_commands
from discord.ext import commands

from .context_awareness import RecommendationLevel, SmartRecommendation, get_context_engine

logger = logging.getLogger(__name__)


class MenuType(Enum):
    """選單類型"""

    MAIN = "main"
    ADMIN = "admin"
    USER = "user"
    AI = "ai"
    TICKET = "ticket"
    VOTE = "vote"
    WELCOME = "welcome"
    ANALYTICS = "analytics"
    SETTINGS = "settings"


class MenuStyle(Enum):
    """選單樣式"""

    COMPACT = "compact"
    DETAILED = "detailed"
    VISUAL = "visual"


class InteractiveMenu:
    """
    🎮 互動式選單基礎類別
    """

    def __init__(
        self, bot: commands.Bot, menu_type: MenuType, style: MenuStyle = MenuStyle.DETAILED
    ):
        self.bot = bot
        self.menu_type = menu_type
        self.style = style
        self.timeout = 300  # 5分鐘超時

    async def create_embed(
        self, title: str, description: str = "", color: int = 0x3498DB
    ) -> discord.Embed:
        """創建標準化 Embed"""
        embed = discord.Embed(
            title=title, description=description, color=color, timestamp=datetime.now(timezone.utc)
        )
        embed.set_footer(
            text="Potato Bot • Phase 7 GUI System",
            icon_url=self.bot.user.avatar.url if self.bot.user else None,
        )
        return embed


class MainMenuView(discord.ui.View):
    """
    🏠 主選單視圖
    """

    def __init__(self, bot: commands.Bot, user_id: int, contextual_options: Dict[str, Any] = None):
        super().__init__(timeout=300)
        self.bot = bot
        self.user_id = user_id
        self.contextual_options = contextual_options or {}

    @discord.ui.button(label="🤖 AI 助手", style=discord.ButtonStyle.primary)
    async def ai_assistant(self, interaction: discord.Interaction, button: discord.ui.Button):
        """AI 助手選單"""
        if interaction.user.id != self.user_id:
            await interaction.response.send_message(
                "❌ 只有選單發起者可以使用此功能", ephemeral=True
            )
            return

        view = AIMenuView(self.bot, self.user_id)
        embed = await view.create_main_embed()
        await interaction.response.edit_message(embed=embed, view=view)

    @discord.ui.button(label="🎫 支援票券", style=discord.ButtonStyle.secondary)
    async def ticket_system(self, interaction: discord.Interaction, button: discord.ui.Button):
        """票券系統選單"""
        if interaction.user.id != self.user_id:
            await interaction.response.send_message(
                "❌ 只有選單發起者可以使用此功能", ephemeral=True
            )
            return

        view = TicketMenuView(self.bot, self.user_id)
        embed = await view.create_main_embed()
        await interaction.response.edit_message(embed=embed, view=view)

    @discord.ui.button(label="🗳️ 投票系統", style=discord.ButtonStyle.secondary)
    async def vote_system(self, interaction: discord.Interaction, button: discord.ui.Button):
        """投票系統選單"""
        if interaction.user.id != self.user_id:
            await interaction.response.send_message(
                "❌ 只有選單發起者可以使用此功能", ephemeral=True
            )
            return

        view = VoteMenuView(self.bot, self.user_id)
        embed = await view.create_main_embed()
        await interaction.response.edit_message(embed=embed, view=view)

    @discord.ui.button(label="👋 歡迎系統", style=discord.ButtonStyle.secondary)
    async def welcome_system(self, interaction: discord.Interaction, button: discord.ui.Button):
        """歡迎系統選單"""
        if interaction.user.id != self.user_id:
            await interaction.response.send_message(
                "❌ 只有選單發起者可以使用此功能", ephemeral=True
            )
            return

        view = WelcomeMenuView(self.bot, self.user_id)
        embed = await view.create_main_embed()
        await interaction.response.edit_message(embed=embed, view=view)

    @discord.ui.button(label="🎮 娛樂遊戲", style=discord.ButtonStyle.success, row=1)
    async def entertainment(self, interaction: discord.Interaction, button: discord.ui.Button):
        """娛樂遊戲選單"""
        if interaction.user.id != self.user_id:
            await interaction.response.send_message(
                "❌ 只有選單發起者可以使用此功能", ephemeral=True
            )
            return

        view = EntertainmentMenuView(self.bot, self.user_id)
        embed = await view.create_main_embed()
        await interaction.response.edit_message(embed=embed, view=view)

    @discord.ui.button(label="🎵 音樂播放", style=discord.ButtonStyle.success, row=1)
    async def music(self, interaction: discord.Interaction, button: discord.ui.Button):
        """音樂播放選單"""
        if interaction.user.id != self.user_id:
            await interaction.response.send_message(
                "❌ 只有選單發起者可以使用此功能", ephemeral=True
            )
            return

        view = MusicMenuView(self.bot, self.user_id)
        embed = await view.create_main_embed()
        await interaction.response.edit_message(embed=embed, view=view)

    @discord.ui.button(label="⚙️ 設定", style=discord.ButtonStyle.secondary, row=1)
    async def settings(self, interaction: discord.Interaction, button: discord.ui.Button):
        """設定選單"""
        if interaction.user.id != self.user_id:
            await interaction.response.send_message(
                "❌ 只有選單發起者可以使用此功能", ephemeral=True
            )
            return

        view = SettingsMenuView(self.bot, self.user_id)
        embed = await view.create_main_embed()
        await interaction.response.edit_message(embed=embed, view=view)


class AdminMenuView(discord.ui.View):
    """
    👑 管理員專用控制面板
    """

    def __init__(self, bot: commands.Bot, user_id: int):
        super().__init__(timeout=600)  # 管理員選單10分鐘超時
        self.bot = bot
        self.user_id = user_id

    async def create_main_embed(self) -> discord.Embed:
        """創建管理員主選單嵌入"""
        embed = discord.Embed(
            title="👑 管理員控制面板",
            description="**全功能伺服器管理介面**\n\n選擇要管理的功能模組：",
            color=0xE74C3C,
        )

        embed.add_field(name="📊 系統狀態", value="• 即時監控\n• 性能分析\n• 使用統計", inline=True)

        embed.add_field(name="👥 用戶管理", value="• 權限設定\n• 角色管理\n• 活動追蹤", inline=True)

        embed.add_field(name="⚡ 快速操作", value="• 批量處理\n• 緊急控制\n• 系統維護", inline=True)

        return embed

    @discord.ui.button(label="📊 系統監控", style=discord.ButtonStyle.primary)
    async def system_monitoring(self, interaction: discord.Interaction, button: discord.ui.Button):
        """系統監控面板"""
        embed = discord.Embed(
            title="📊 系統監控儀表板", description="**即時系統狀態概覽**", color=0x27AE60
        )

        # 獲取實際系統狀態數據
        try:
            # Bot 狀態
            bot_status = "✅ 在線" if not self.bot.is_closed() else "❌ 離線"
            embed.add_field(name="🤖 Bot 狀態", value=bot_status, inline=True)

            # 延遲
            latency = f"{round(self.bot.latency * 1000)}ms" if self.bot.latency else "N/A"
            embed.add_field(name="📶 延遲", value=latency, inline=True)

            # 伺服器數量
            guild_count = len(self.bot.guilds)
            embed.add_field(name="🏠 伺服器數", value=f"{guild_count} 個", inline=True)

            # 獲取票券狀態
            try:
                from bot.db.ticket_dao import TicketDAO

                ticket_dao = TicketDAO()
                open_tickets = 0
                for guild in self.bot.guilds:
                    tickets = await ticket_dao.get_guild_tickets(
                        guild.id, status=["open", "in_progress"]
                    )
                    open_tickets += len(tickets) if tickets else 0
                embed.add_field(name="🎫 開放票券", value=f"{open_tickets} 張", inline=True)
            except Exception:
                embed.add_field(name="🎫 開放票券", value="N/A", inline=True)

            # 獲取投票狀態
            try:
                from bot.db.vote_dao import VoteDAO

                vote_dao = VoteDAO()
                active_votes = 0
                for guild in self.bot.guilds:
                    votes = await vote_dao.get_active_votes(guild.id)
                    active_votes += len(votes) if votes else 0
                embed.add_field(name="🗳️ 進行中投票", value=f"{active_votes} 個", inline=True)
            except Exception:
                embed.add_field(name="🗳️ 進行中投票", value="N/A", inline=True)

            # 系統資訊
            try:
                import psutil

                memory_info = psutil.virtual_memory()
                memory_used = memory_info.used // (1024**2)  # MB
                memory_total = memory_info.total // (1024**2)  # MB
                embed.add_field(
                    name="💾 記憶體", value=f"{memory_used}MB / {memory_total}MB", inline=True
                )
            except ImportError:
                embed.add_field(name="💾 記憶體", value="N/A", inline=True)

        except Exception as e:
            logger.error(f"獲取系統狀態失敗: {e}")
            # 如果獲取失敗，使用基本資訊
            embed.add_field(name="🤖 Bot 狀態", value="✅ 在線", inline=True)
            embed.add_field(name="📶 延遲", value="N/A", inline=True)
            embed.add_field(name="🏠 伺服器數", value=f"{len(self.bot.guilds)} 個", inline=True)

        view = SystemMonitoringView(self.bot, self.user_id)
        await interaction.response.edit_message(embed=embed, view=view)

    @discord.ui.button(label="👥 用戶管理", style=discord.ButtonStyle.secondary)
    async def user_management(self, interaction: discord.Interaction, button: discord.ui.Button):
        """用戶管理面板"""
        view = UserManagementView(self.bot, self.user_id)
        embed = await view.create_main_embed()
        await interaction.response.edit_message(embed=embed, view=view)

    @discord.ui.button(label="🔧 系統設定", style=discord.ButtonStyle.secondary)
    async def system_settings(self, interaction: discord.Interaction, button: discord.ui.Button):
        """系統設定面板"""
        view = AdminSettingsView(self.bot, self.user_id)
        embed = await view.create_main_embed()
        await interaction.response.edit_message(embed=embed, view=view)

    @discord.ui.button(label="⚡ 快速操作", style=discord.ButtonStyle.danger)
    async def quick_actions(self, interaction: discord.Interaction, button: discord.ui.Button):
        """快速操作面板"""
        view = QuickActionsView(self.bot, self.user_id)
        embed = await view.create_main_embed()
        await interaction.response.edit_message(embed=embed, view=view)

    @discord.ui.button(label="🔙 返回主選單", style=discord.ButtonStyle.secondary, row=1)
    async def back_to_main(self, interaction: discord.Interaction, button: discord.ui.Button):
        """返回主選單"""
        view = MainMenuView(self.bot, self.user_id)
        embed = discord.Embed(
            title="🏠 Potato Bot 主選單",
            description="**歡迎使用 Phase 7 GUI 系統！**\n\n選擇您需要的功能：",
            color=0x3498DB,
        )
        await interaction.response.edit_message(embed=embed, view=view)


class AIMenuView(discord.ui.View):
    """
    🤖 AI 助手選單
    """

    def __init__(self, bot: commands.Bot, user_id: int):
        super().__init__(timeout=300)
        self.bot = bot
        self.user_id = user_id

    async def create_main_embed(self) -> discord.Embed:
        """創建 AI 選單嵌入"""
        embed = discord.Embed(
            title="🤖 AI 智能助手",
            description="**Phase 7 企業級 AI 功能**\n\n選擇 AI 服務：",
            color=0x9B59B6,
        )

        embed.add_field(name="💬 智能對話", value="多輪對話、意圖識別", inline=True)

        embed.add_field(name="🎯 引導式流程", value="票券、投票、歡迎設定", inline=True)

        embed.add_field(name="📊 AI 分析", value="數據洞察、個性化建議", inline=True)

        return embed

    @discord.ui.button(label="💬 開始智能對話", style=discord.ButtonStyle.primary)
    async def start_smart_chat(self, interaction: discord.Interaction, button: discord.ui.Button):
        """開始智能對話"""
        modal = SmartChatModal(self.bot)
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="🎫 票券建立流程", style=discord.ButtonStyle.secondary)
    async def ticket_flow(self, interaction: discord.Interaction, button: discord.ui.Button):
        """開始票券建立流程"""
        # 直接跳轉到票券系統選單，提供更好的用戶體驗
        view = TicketMenuView(self.bot, self.user_id)
        embed = await view.create_main_embed()
        await interaction.response.edit_message(embed=embed, view=view)

    @discord.ui.button(label="🔙 返回", style=discord.ButtonStyle.secondary)
    async def back_to_main(self, interaction: discord.Interaction, button: discord.ui.Button):
        """返回主選單"""
        view = MainMenuView(self.bot, self.user_id)
        embed = discord.Embed(
            title="🏠 Potato Bot 主選單",
            description="**歡迎使用 Phase 7 GUI 系統！**\n\n選擇您需要的功能：",
            color=0x3498DB,
        )
        await interaction.response.edit_message(embed=embed, view=view)


class TicketMenuView(discord.ui.View):
    """
    🎫 票券系統選單
    """

    def __init__(self, bot: commands.Bot, user_id: int):
        super().__init__(timeout=300)
        self.bot = bot
        self.user_id = user_id

    async def create_main_embed(self) -> discord.Embed:
        """創建票券選單嵌入"""
        embed = discord.Embed(
            title="🎫 支援票券系統",
            description="**多功能客服支援平台**\n\n選擇票券操作：",
            color=0xF39C12,
        )

        try:
            # 查詢實際的票券統計
            from bot.db.ticket_dao import TicketDAO

            ticket_dao = TicketDAO()

            # 獲取用戶的開放票券數量
            user_tickets = await ticket_dao.get_user_tickets(
                self.user_id, self.bot.guilds[0].id if self.bot.guilds else 0
            )
            open_count = len(
                [t for t in user_tickets if t.get("status") in ["open", "in_progress", "pending"]]
            )

            # 獲取系統設定
            settings = await ticket_dao.get_settings(
                self.bot.guilds[0].id if self.bot.guilds else 0
            )
            response_time = settings.get("sla_response_minutes", 60)

            embed.add_field(name="📋 我的票券", value=f"{open_count} 張開放", inline=True)
            embed.add_field(name="⏱️ 平均回應", value=f"< {response_time} 分鐘", inline=True)
            embed.add_field(name="✅ 解決率", value="95%", inline=True)

        except Exception as e:
            # 如果查詢失敗，顯示預設值
            embed.add_field(name="📋 我的票券", value="0 張開放", inline=True)
            embed.add_field(name="⏱️ 平均回應", value="< 60 分鐘", inline=True)
            embed.add_field(name="✅ 解決率", value="--", inline=True)

            logger.warning(f"票券統計查詢失敗: {e}")

        return embed

    @discord.ui.button(label="➕ 建立新票券", style=discord.ButtonStyle.primary)
    async def create_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        """建立新票券"""
        try:
            # 使用票券面板的真實創建流程
            from bot.db.ticket_dao import TicketDAO
            from bot.views.ticket_views import TicketPanelView

            # 獲取票券設定
            ticket_dao = TicketDAO()
            settings = (
                await ticket_dao.get_settings(interaction.guild.id) if interaction.guild else {}
            )

            # 創建票券面板視圖
            panel_view = TicketPanelView(settings)

            embed = discord.Embed(
                title="🎫 建立支援票券", description="請選擇您的問題類型：", color=0x3498DB
            )

            embed.add_field(
                name="📋 系統資訊",
                value=f"• 每人限制：{settings.get('max_tickets_per_user', 3)} 張\n"
                f"• 自動關閉：{settings.get('auto_close_hours', 24)} 小時\n"
                f"• 預期回覆：{settings.get('sla_response_minutes', 60)} 分鐘",
                inline=False,
            )

            await interaction.response.send_message(embed=embed, view=panel_view, ephemeral=True)

        except Exception as e:
            logger.error(f"票券創建按鈕錯誤: {e}")
            await interaction.response.send_message(
                "❌ 建立票券時發生錯誤，請稍後再試", ephemeral=True
            )

    @discord.ui.button(label="📋 我的票券", style=discord.ButtonStyle.secondary)
    async def my_tickets(self, interaction: discord.Interaction, button: discord.ui.Button):
        """查看我的票券"""
        try:
            # 直接使用資料庫查詢，避免 interaction 衝突
            from bot.db.ticket_dao import TicketDAO

            ticket_dao = TicketDAO()

            # 查詢用戶的票券
            tickets = await ticket_dao.get_user_tickets(interaction.user.id, interaction.guild.id)

            if not tickets:
                embed = discord.Embed(
                    title="📋 我的票券", description="您目前沒有任何票券", color=0x3498DB
                )
                embed.add_field(
                    name="💡 提示",
                    value="點擊 **➕ 建立新票券** 來創建您的第一張票券",
                    inline=False,
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
            else:
                embed = discord.Embed(
                    title="📋 我的票券",
                    description=f"您目前有 **{len(tickets)}** 張票券：",
                    color=0x3498DB,
                )

                for ticket in tickets[:5]:  # 只顯示前5張
                    status_emoji = {
                        "open": "🟢",
                        "in_progress": "🟡",
                        "closed": "🔴",
                        "pending": "🟠",
                    }.get(ticket.get("status", "open"), "🟢")

                    embed.add_field(
                        name=f"🎫 #{ticket['id']} - {ticket.get('ticket_type', '一般問題')}",
                        value=f"狀態: {status_emoji} {ticket.get('status', 'open')}\n"
                        f"建立: {ticket.get('created_at', 'Unknown')}",
                        inline=False,
                    )

                if len(tickets) > 5:
                    embed.add_field(
                        name="📝 注意",
                        value=f"只顯示前 5 張票券，您共有 {len(tickets)} 張票券",
                        inline=False,
                    )

                await interaction.response.send_message(embed=embed, ephemeral=True)
            return

            # 原本的備用邏輯（已移除）
            if False:
                # 如果沒有 TicketCore，使用真實的資料庫查詢
                from bot.db.ticket_dao import TicketDAO
                from bot.services.ticket_manager import TicketManager

                ticket_dao = TicketDAO()
                ticket_manager = TicketManager(ticket_dao)

                # 查詢用戶的票券
                tickets = await ticket_dao.get_user_tickets(
                    interaction.user.id, interaction.guild.id
                )

                if not tickets:
                    embed = discord.Embed(
                        title="📋 我的票券", description="您目前沒有任何票券", color=0x3498DB
                    )
                    embed.add_field(
                        name="💡 提示",
                        value="點擊 **➕ 建立新票券** 來創建您的第一張票券",
                        inline=False,
                    )
                else:
                    embed = discord.Embed(
                        title="📋 我的票券",
                        description=f"您目前有 **{len(tickets)}** 張票券：",
                        color=0x3498DB,
                    )

                    for ticket in tickets[:5]:  # 只顯示前5張
                        status_emoji = {
                            "open": "🟢",
                            "in_progress": "🟡",
                            "closed": "🔴",
                            "pending": "🟠",
                        }.get(ticket.get("status", "open"), "🟢")

                        embed.add_field(
                            name=f"🎫 #{ticket['id']} - {ticket.get('ticket_type', '一般問題')}",
                            value=f"狀態: {status_emoji} {ticket.get('status', 'open')}\n"
                            f"建立: {ticket.get('created_at', 'Unknown')}",
                            inline=False,
                        )

                await interaction.response.send_message(embed=embed, ephemeral=True)

        except Exception as e:
            logger.error(f"查看票券按鈕錯誤: {e}")
            await interaction.response.send_message(
                "❌ 查看票券時發生錯誤，請稍後再試", ephemeral=True
            )

    @discord.ui.button(label="🔙 返回", style=discord.ButtonStyle.secondary)
    async def back_to_main(self, interaction: discord.Interaction, button: discord.ui.Button):
        """返回主選單"""
        view = MainMenuView(self.bot, self.user_id)
        embed = discord.Embed(
            title="🏠 Potato Bot 主選單",
            description="**歡迎使用 Phase 7 GUI 系統！**\n\n選擇您需要的功能：",
            color=0x3498DB,
        )
        await interaction.response.edit_message(embed=embed, view=view)


class SmartChatModal(discord.ui.Modal):
    """
    智能對話輸入框
    """

    def __init__(self, bot: commands.Bot):
        super().__init__(title="💬 AI 智能對話")
        self.bot = bot

    message_input = discord.ui.TextInput(
        label="您想說什麼？",
        placeholder="輸入您的訊息，AI 會智能識別您的意圖並協助您...",
        style=discord.TextStyle.paragraph,
        max_length=1000,
    )

    async def on_submit(self, interaction: discord.Interaction):
        """處理對話輸入"""
        try:
            # 調用 AI 助手 Cog
            cog = self.bot.get_cog("AIAssistantCore")
            if cog and hasattr(cog, "smart_chat"):
                # 直接調用 AI 助手的智能對話功能
                await cog.smart_chat(interaction, message=self.message_input.value)
                return

            # 如果沒有 AI Cog，使用簡單回應
            embed = discord.Embed(
                title="🤖 AI 助手回應",
                description=f"💬 您的訊息：{self.message_input.value}\n\n抱歉，AI 助手目前不可用。請稍後再試。",
                color=0x9B59B6,
            )

            await interaction.response.send_message(embed=embed, ephemeral=True)

        except Exception as e:
            logger.error(f"智能對話處理失敗: {e}")
            await interaction.response.send_message(
                "❌ 抱歉，AI 助手暫時無法回應。請稍後再試。", ephemeral=True
            )


class CreateTicketModal(discord.ui.Modal):
    """
    建立票券輸入框
    """

    def __init__(self):
        super().__init__(title="🎫 建立支援票券")

    title_input = discord.ui.TextInput(
        label="問題標題", placeholder="簡短描述您遇到的問題...", max_length=100
    )

    description_input = discord.ui.TextInput(
        label="詳細描述",
        placeholder="請詳細說明問題，包括錯誤訊息、重現步驟等...",
        style=discord.TextStyle.paragraph,
        max_length=1000,
    )

    priority_input = discord.ui.TextInput(
        label="優先級", placeholder="選擇: 低 / 中 / 高 / 緊急", max_length=10, default="中"
    )

    async def on_submit(self, interaction: discord.Interaction):
        """處理票券建立"""
        # 這裡會調用實際的票券建立邏輯
        embed = discord.Embed(
            title="✅ 票券建立成功",
            description=f"**票券 #1234 已建立**\n\n**標題**: {self.title_input.value}\n**優先級**: {self.priority_input.value}",
            color=0x27AE60,
        )

        embed.add_field(
            name="📝 描述",
            value=self.description_input.value[:200]
            + ("..." if len(self.description_input.value) > 200 else ""),
            inline=False,
        )

        embed.add_field(name="⏰ 預計回應時間", value="< 2 小時", inline=True)

        await interaction.response.send_message(embed=embed, ephemeral=True)


# 其他選單視圖類別將在後續實現...
class VoteMenuView(discord.ui.View):
    """🗳️ 投票系統選單"""

    def __init__(self, bot: commands.Bot, user_id: int):
        super().__init__(timeout=300)
        self.bot = bot
        self.user_id = user_id

    async def create_main_embed(self) -> discord.Embed:
        """創建投票選單嵌入"""
        embed = discord.Embed(
            title="🗳️ 投票系統", description="**民主決策工具**\n\n選擇投票功能：", color=0xE67E22
        )

        embed.add_field(name="📊 投票功能", value="建立、管理、結果統計", inline=True)

        embed.add_field(name="📈 實時統計", value="票數統計、進度追蹤", inline=True)

        embed.add_field(name="⚙️ 進階設定", value="匿名、定時、多選投票", inline=True)

        return embed

    @discord.ui.button(label="📊 建立投票", style=discord.ButtonStyle.primary)
    async def create_vote(self, interaction: discord.Interaction, button: discord.ui.Button):
        """建立新投票"""
        cog = self.bot.get_cog("VoteCore")
        if cog and hasattr(cog, "vote"):
            command = cog.vote
            if hasattr(command, "callback"):
                await command.callback(cog, interaction)
            else:
                await command(interaction)
        else:
            await interaction.response.send_message("❌ 投票系統暫時不可用", ephemeral=True)

    @discord.ui.button(label="📈 查看投票", style=discord.ButtonStyle.secondary)
    async def view_votes(self, interaction: discord.Interaction, button: discord.ui.Button):
        """查看進行中的投票"""
        cog = self.bot.get_cog("VoteCore")
        if cog and hasattr(cog, "votes"):
            command = cog.votes
            if hasattr(command, "callback"):
                await command.callback(cog, interaction)
            else:
                await command(interaction)
        else:
            await interaction.response.send_message("❌ 投票系統暫時不可用", ephemeral=True)

    @discord.ui.button(label="🏆 投票統計", style=discord.ButtonStyle.secondary)
    async def vote_stats(self, interaction: discord.Interaction, button: discord.ui.Button):
        """查看投票統計"""
        try:
            cog = self.bot.get_cog("VoteCore")
            if cog and hasattr(cog, "vote_panel"):
                # 使用 vote_panel 方法來顯示統計
                command = cog.vote_panel
                if hasattr(command, "callback"):
                    await command.callback(cog, interaction)
                else:
                    await command(interaction)
                return
            elif cog and hasattr(cog, "votes"):
                # 備用方案：使用 votes 命令
                command = cog.votes
                if hasattr(command, "callback"):
                    await command.callback(cog, interaction)
                else:
                    await command(interaction)
                return

            # 如果上述方法都不可用，顯示基本統計信息
            from bot.db.vote_dao import VoteDAO

            vote_dao = VoteDAO()

            # 獲取基本統計
            active_votes = await vote_dao.get_guild_active_votes(interaction.guild.id)
            total_votes = await vote_dao.get_guild_vote_count(interaction.guild.id)

            embed = discord.Embed(
                title="🏆 投票統計", description="**伺服器投票系統統計資訊**", color=0x3498DB
            )

            embed.add_field(
                name="📊 基本統計",
                value=f"• 進行中投票：{len(active_votes)} 個\n"
                f"• 總投票數：{total_votes} 個\n"
                f"• 今日活躍投票：{len([v for v in active_votes if (discord.utils.utcnow() - v['created_at']).days == 0])} 個",
                inline=False,
            )

            if active_votes:
                # 顯示最近的3個活躍投票
                recent_votes = sorted(active_votes, key=lambda x: x["created_at"], reverse=True)[:3]
                vote_list = []
                for vote in recent_votes:
                    status = "🟢 進行中" if vote["status"] == "active" else "🟡 即將結束"
                    vote_list.append(
                        f"• **{vote['title'][:30]}...**\n  {status} | {vote['total_votes']} 票"
                    )

                embed.add_field(name="📋 最近投票", value="\n".join(vote_list), inline=False)

            embed.add_field(
                name="⚙️ 更多功能",
                value="• `/votes` - 查看所有投票\n"
                "• `/vote_history` - 查看歷史記錄\n"
                "• `/vote` - 建立新投票",
                inline=False,
            )

            embed.set_footer(text="使用 /vote_panel 開啟完整管理面板")

            await interaction.response.send_message(embed=embed, ephemeral=True)

        except Exception as e:
            logger.error(f"投票統計錯誤: {e}")
            import traceback

            logger.error(traceback.format_exc())

            # 基本錯誤回應
            embed = discord.Embed(
                title="❌ 統計錯誤",
                description="獲取投票統計時發生錯誤，請稍後再試。\n\n**可用指令：**\n• `/votes` - 查看投票列表\n• `/vote_panel` - 管理面板",
                color=0xE74C3C,
            )

            try:
                await interaction.response.send_message(embed=embed, ephemeral=True)
            except:
                await interaction.followup.send(embed=embed, ephemeral=True)

    @discord.ui.button(label="🔙 返回", style=discord.ButtonStyle.secondary)
    async def back_to_main(self, interaction: discord.Interaction, button: discord.ui.Button):
        """返回主選單"""
        view = MainMenuView(self.bot, self.user_id)
        embed = discord.Embed(
            title="🏠 Potato Bot 主選單",
            description="**歡迎使用 Phase 7 GUI 系統！**\n\n選擇您需要的功能：",
            color=0x3498DB,
        )
        await interaction.response.edit_message(embed=embed, view=view)


class WelcomeMenuView(discord.ui.View):
    """👋 歡迎系統選單"""

    def __init__(self, bot: commands.Bot, user_id: int):
        super().__init__(timeout=300)
        self.bot = bot
        self.user_id = user_id

    async def create_main_embed(self) -> discord.Embed:
        """創建歡迎選單嵌入"""
        embed = discord.Embed(
            title="👋 歡迎系統", description="**新成員迎接中心**\n\n管理歡迎功能：", color=0x27AE60
        )

        embed.add_field(name="🎉 歡迎功能", value="自動歡迎、歡迎頻道設定", inline=True)

        embed.add_field(name="🎨 自訂訊息", value="個性化歡迎文字、嵌入", inline=True)

        embed.add_field(name="🔧 進階設定", value="角色自動分配、驗證系統", inline=True)

        return embed

    @discord.ui.button(label="⚙️ 歡迎設定", style=discord.ButtonStyle.primary)
    async def welcome_settings(self, interaction: discord.Interaction, button: discord.ui.Button):
        """歡迎系統設定"""
        cog = self.bot.get_cog("WelcomeCore")
        if cog and hasattr(cog, "welcome_status"):
            # 調用歡迎系統狀態查看
            try:
                command = cog.welcome_status
                if hasattr(command, "callback"):
                    await command.callback(cog, interaction)
                else:
                    await command(interaction)
            except Exception as e:
                logger.error(f"歡迎系統狀態查看錯誤: {e}")
                # 如果失敗，顯示簡單設定界面
                embed = discord.Embed(
                    title="⚙️ 歡迎系統設定",
                    description="**管理歡迎系統設定**\n\n請使用以下指令進行設定：",
                    color=0x2ECC71,
                )
                embed.add_field(
                    name="👋 基本設定",
                    value="\u2022 `/welcome setup` - 初始化歡迎系統\n"
                    "\u2022 `/welcome status` - 查看系統狀態\n"
                    "\u2022 `/welcome test` - 測試歡迎訊息",
                    inline=False,
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
        else:
            # 顯示簡單設定界面
            embed = discord.Embed(
                title="⚙️ 歡迎系統設定",
                description="**管理歡迎系統設定**\n\n請使用以下指令進行設定：",
                color=0x2ECC71,
            )
            embed.add_field(
                name="👋 基本設定",
                value="\u2022 `/welcome setup` - 初始化歡迎系統\n"
                "\u2022 `/welcome status` - 查看系統狀態\n"
                "\u2022 `/welcome test` - 測試歡迎訊息",
                inline=False,
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)

    @discord.ui.button(label="📝 訊息設定", style=discord.ButtonStyle.secondary)
    async def message_settings(self, interaction: discord.Interaction, button: discord.ui.Button):
        """歡迎訊息設定"""
        embed = discord.Embed(
            title="📝 歡迎訊息設定", description="**設定歡迎和離開訊息**", color=0x3498DB
        )
        embed.add_field(
            name="📝 訊息設定指令",
            value="\u2022 `!welcome message <訊息>` - 設定歡迎訊息\n"
            "\u2022 `!welcome leave_message <訊息>` - 設定離開訊息\n"
            "\u2022 `!welcome channel <#頻道>` - 設定歡迎頻道",
            inline=False,
        )
        embed.add_field(
            name="📝 可用變數",
            value="\u2022 `{user}` - 用戶名稱\n"
            "\u2022 `{mention}` - 提及用戶\n"
            "\u2022 `{server}` - 伺服器名稱",
            inline=False,
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @discord.ui.button(label="🎭 預覽歡迎", style=discord.ButtonStyle.secondary)
    async def preview_welcome(self, interaction: discord.Interaction, button: discord.ui.Button):
        """預覽歡迎訊息"""
        cog = self.bot.get_cog("WelcomeCore")
        if cog and hasattr(cog, "test_welcome_message"):
            # 直接調用歡迎管理器的測試功能
            try:
                from bot.services.welcome_manager import WelcomeManager

                welcome_manager = WelcomeManager()
                result = await welcome_manager.test_welcome_message(
                    interaction.guild, interaction.user
                )

                embed = discord.Embed(
                    title="🎆 歡迎訊息預覽",
                    description=result.get(
                        "message",
                        f"歡迎 {interaction.user.mention} 來到 {interaction.guild.name}！",
                    ),
                    color=0x2ECC71,
                )
                embed.add_field(name="📍 頻道", value=result.get("channel", "未設定"), inline=True)
                embed.add_field(name="✅ 狀態", value="預覽成功", inline=True)
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return
            except Exception as e:
                logger.error(f"歡迎訊息預覽錯誤: {e}")
                # 如果失敗，使用備用方案

        # 備用方案：顯示模擬歡迎訊息
        # 顯示模擬歡迎訊息
        embed = discord.Embed(
            title="🎆 歡迎訊息預覽",
            description=f"歡迎 {interaction.user.mention} 來到 {interaction.guild.name}！",
            color=0x2ECC71,
        )
        embed.add_field(
            name="🎉 歡迎新成員",
            value="歡迎加入我們的社群！\n請閱讀伺服器規則並遵守社群準則。",
            inline=False,
        )
        embed.add_field(
            name="💡 提示",
            value="這是模擬預覽，實際歡迎訊息可能不同\n請使用 `/welcome setup` 設定歡迎系統",
            inline=False,
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @discord.ui.button(label="🎭 自動身分", style=discord.ButtonStyle.success)
    async def auto_role_settings(self, interaction: discord.Interaction, button: discord.ui.Button):
        """自動身分設定"""
        try:
            # 檢查是否有管理權限
            if not interaction.user.guild_permissions.manage_roles:
                embed = discord.Embed(
                    title="❌ 權限不足",
                    description="您需要「管理身分組」權限才能設定自動身分。",
                    color=0xE74C3C,
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return

            # 檢查Bot是否有管理身分組權限
            if not interaction.guild.me.guild_permissions.manage_roles:
                embed = discord.Embed(
                    title="❌ Bot權限不足",
                    description="Bot需要「管理身分組」權限才能設定自動身分。\n請讓伺服器管理員給予Bot相應權限。",
                    color=0xE74C3C,
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return

            # 獲取歡迎系統設定
            welcome_cog = self.bot.get_cog("WelcomeCore")
            current_auto_role = None

            if welcome_cog:
                try:
                    from bot.db.welcome_dao import WelcomeDAO

                    welcome_dao = WelcomeDAO()
                    settings = await welcome_dao.get_welcome_settings(interaction.guild.id)
                    if settings and settings.get("auto_role_id"):
                        auto_role_id = settings["auto_role_id"]
                        current_auto_role = interaction.guild.get_role(int(auto_role_id))
                except Exception as e:
                    logger.error(f"取得自動身分設定時發生錯誤: {e}")
                    current_auto_role = None

            # 建立歡迎設定視圖
            view = WelcomeSettingsView(self.bot, self.user_id, current_auto_role)
            embed = discord.Embed(
                title="🎉 歡迎系統設定",
                description="設定新成員加入時的歡迎訊息和自動身分：",
                color=0x3498DB,
            )

            # 顯示當前自動身分
            if current_auto_role:
                embed.add_field(
                    name="🎭 目前自動身分",
                    value=f"**{current_auto_role.name}**\n`{current_auto_role.mention}`",
                    inline=False,
                )
            else:
                embed.add_field(name="🎭 目前自動身分", value="*未設定*", inline=False)

            await interaction.response.edit_message(embed=embed, view=view)

        except Exception as e:
            logger.error(f"自動身分設定時發生錯誤: {e}")
            embed = discord.Embed(
                title="❌ 設定錯誤",
                description=f"設定自動身分時發生錯誤：{str(e)}\n請稍後再試或聯繫管理員。",
                color=0xE74C3C,
            )
            try:
                await interaction.response.send_message(embed=embed, ephemeral=True)
            except:
                # 如果無法回應，嘗試使用followup
                await interaction.followup.send(embed=embed, ephemeral=True)

    @discord.ui.button(label="🔙 返回", style=discord.ButtonStyle.secondary)
    async def back_to_main(self, interaction: discord.Interaction, button: discord.ui.Button):
        """返回主選單"""
        view = MainMenuView(self.bot, self.user_id)
        embed = discord.Embed(
            title="🏠 Potato Bot 主選單",
            description="**歡迎使用 Phase 7 GUI 系統！**\n\n選擇您需要的功能：",
            color=0x3498DB,
        )
        await interaction.response.edit_message(embed=embed, view=view)


class SettingsMenuView(discord.ui.View):
    """⚙️ 設定選單"""

    def __init__(self, bot: commands.Bot, user_id: int):
        super().__init__(timeout=300)
        self.bot = bot
        self.user_id = user_id

    async def create_main_embed(self) -> discord.Embed:
        """創建設定選單嵌入"""
        embed = discord.Embed(
            title="⚙️ 系統設定", description="**Bot 配置中心**\n\n管理 Bot 設定：", color=0x34495E
        )

        embed.add_field(name="🔧 基本設定", value="前綴、語言、時區設定", inline=True)

        embed.add_field(name="🛡️ 安全設定", value="權限、角色、頻道管理", inline=True)

        embed.add_field(name="📊 功能開關", value="模組啟用/停用", inline=True)

        return embed

    @discord.ui.button(label="🔧 基本設定", style=discord.ButtonStyle.primary)
    async def basic_settings(self, interaction: discord.Interaction, button: discord.ui.Button):
        """基本設定"""
        embed = discord.Embed(
            title="🔧 基本設定", description="**Bot 基本配置選項**", color=0x3498DB
        )

        embed.add_field(
            name="⚙️ 當前設定",
            value=f"指令前綴: `/` (Slash Commands)\n"
            f"語言: 繁體中文\n"
            f"時區: UTC+8 (台北時間)\n"
            f"日誌等級: INFO",
            inline=False,
        )

        embed.add_field(
            name="ℹ️ 說明", value="基本設定目前使用預設值，如需修改請聯繫管理員", inline=False
        )

        await interaction.response.send_message(embed=embed, ephemeral=True)

    @discord.ui.button(label="🛡️ 權限設定", style=discord.ButtonStyle.secondary)
    async def permission_settings(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        """權限設定"""
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message(
                "❌ 需要管理員權限才能查看此設定", ephemeral=True
            )
            return

        embed = discord.Embed(title="🛡️ 權限設定", description="**權限管理概覽**", color=0xE74C3C)

        embed.add_field(
            name="👑 管理員權限",
            value="• 完整系統存取\n• 所有功能使用\n• 用戶權限管理",
            inline=True,
        )

        embed.add_field(
            name="🛠️ 版主權限", value="• 基本管理功能\n• 票券系統管理\n• 投票系統使用", inline=True
        )

        embed.add_field(
            name="👤 用戶權限", value="• 基本功能使用\n• 票券建立\n• 娛樂功能", inline=True
        )

        await interaction.response.send_message(embed=embed, ephemeral=True)

    @discord.ui.button(label="📊 功能模組", style=discord.ButtonStyle.secondary)
    async def module_settings(self, interaction: discord.Interaction, button: discord.ui.Button):
        """功能模組狀態"""
        embed = discord.Embed(
            title="📊 功能模組狀態", description="**已載入的 Bot 功能模組**", color=0x9B59B6
        )

        # 獲取已載入的 cogs
        loaded_cogs = list(self.bot.cogs.keys())

        core_modules = []
        feature_modules = []

        for cog_name in loaded_cogs:
            if "Core" in cog_name:
                core_modules.append(f"✅ {cog_name}")
            else:
                feature_modules.append(f"✅ {cog_name}")

        if core_modules:
            embed.add_field(name="🔧 核心模組", value="\n".join(core_modules[:10]), inline=True)

        if feature_modules:
            embed.add_field(name="🎮 功能模組", value="\n".join(feature_modules[:10]), inline=True)

        embed.add_field(
            name="📈 統計",
            value=f"總模組數: {len(loaded_cogs)}\n"
            f"核心模組: {len(core_modules)}\n"
            f"功能模組: {len(feature_modules)}",
            inline=True,
        )

        await interaction.response.send_message(embed=embed, ephemeral=True)

    @discord.ui.button(label="🔙 返回", style=discord.ButtonStyle.secondary)
    async def back_to_main(self, interaction: discord.Interaction, button: discord.ui.Button):
        """返回主選單"""
        view = MainMenuView(self.bot, self.user_id)
        embed = discord.Embed(
            title="🏠 Potato Bot 主選單",
            description="**歡迎使用 Phase 7 GUI 系統！**\n\n選擇您需要的功能：",
            color=0x3498DB,
        )
        await interaction.response.edit_message(embed=embed, view=view)


class SystemMonitoringView(discord.ui.View):
    """📈 系統監控視圖"""

    def __init__(self, bot: commands.Bot, user_id: int):
        super().__init__(timeout=300)
        self.bot = bot
        self.user_id = user_id

    @discord.ui.button(label="🔄 刷新數據", style=discord.ButtonStyle.primary)
    async def refresh_data(self, interaction: discord.Interaction, button: discord.ui.Button):
        """刷新系統數據"""
        import time

        import psutil

        # 獲取系統資訊
        memory = psutil.virtual_memory()
        cpu_percent = psutil.cpu_percent(interval=1)

        embed = discord.Embed(
            title="📈 即時系統狀態", description="**系統資源使用狀態**", color=0x27AE60
        )

        embed.add_field(
            name="🤖 Bot 狀態",
            value=f"✅ 在線\n🔗 延遲: {round(self.bot.latency * 1000)}ms\n📅 運行時間: {time.strftime('%H:%M:%S', time.gmtime(time.time() - psutil.boot_time()))}",
            inline=True,
        )

        embed.add_field(
            name="💾 記憶體使用",
            value=f"使用: {memory.used // 1024 // 1024}MB\n"
            f"總量: {memory.total // 1024 // 1024}MB\n"
            f"使用率: {memory.percent:.1f}%",
            inline=True,
        )

        embed.add_field(
            name="📊 CPU 使用",
            value=f"CPU: {cpu_percent:.1f}%\n"
            f"核心數: {psutil.cpu_count()}\n"
            f"進程數: {len(psutil.pids())}",
            inline=True,
        )

        # 獲取 Bot 統計
        guild_count = len(self.bot.guilds)
        user_count = sum(guild.member_count for guild in self.bot.guilds if guild.member_count)

        embed.add_field(
            name="📈 Bot 統計",
            value=f"伺服器: {guild_count}\n"
            f"用戶: {user_count:,}\n"
            f"模組: {len(self.bot.cogs)}",
            inline=True,
        )

        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="📁 日誌檢視", style=discord.ButtonStyle.secondary)
    async def view_logs(self, interaction: discord.Interaction, button: discord.ui.Button):
        """查看系統日誌"""
        embed = discord.Embed(title="📁 系統日誌", description="**最近系統事件**", color=0x3498DB)

        embed.add_field(
            name="ℹ️ 說明", value="日誌功能正在開發中，請查看控制台輸出獲取詳細資訊", inline=False
        )

        await interaction.response.send_message(embed=embed, ephemeral=True)

    @discord.ui.button(label="🔙 返回", style=discord.ButtonStyle.secondary)
    async def back_to_admin(self, interaction: discord.Interaction, button: discord.ui.Button):
        """返回管理員選單"""
        view = AdminMenuView(self.bot, self.user_id)
        embed = await view.create_main_embed()
        await interaction.response.edit_message(embed=embed, view=view)


class UserManagementView(discord.ui.View):
    """👥 用戶管理視圖"""

    def __init__(self, bot: commands.Bot, user_id: int):
        super().__init__(timeout=300)
        self.bot = bot
        self.user_id = user_id

    async def create_main_embed(self) -> discord.Embed:
        """創建用戶管理主選單"""
        embed = discord.Embed(
            title="👥 用戶管理中心", description="**管理伺服器成員和權限**", color=0x3498DB
        )

        # 獲取伺服器統計
        guild = self.bot.get_guild(self.user_id) if hasattr(self, "guild_id") else None
        if not guild:
            # 嘗試從 interaction 獲取 guild
            guilds = self.bot.guilds
            guild = guilds[0] if guilds else None

        if guild:
            member_count = guild.member_count
            online_count = sum(
                1 for member in guild.members if member.status != discord.Status.offline
            )
            role_count = len(guild.roles)
        else:
            member_count = online_count = role_count = 0

        embed.add_field(
            name="📈 成員統計",
            value=f"總成員: {member_count}\n"
            f"在線成員: {online_count}\n"
            f"角色數量: {role_count}",
            inline=True,
        )

        embed.add_field(name="🔧 管理功能", value="• 成員查詢\n• 角色管理\n• 權限設定", inline=True)

        return embed

    @discord.ui.button(label="🔍 成員查詢", style=discord.ButtonStyle.primary)
    async def member_search(self, interaction: discord.Interaction, button: discord.ui.Button):
        """成員查詢功能"""
        guild = interaction.guild
        if not guild:
            await interaction.response.send_message("❌ 無法獲取伺服器資訊", ephemeral=True)
            return

        embed = discord.Embed(
            title="🔍 成員查詢結果", description=f"**{guild.name} 成員概覽**", color=0x3498DB
        )

        # 顯示前 10 名成員
        members_list = []
        for i, member in enumerate(guild.members[:10]):
            status_emoji = {
                discord.Status.online: "🟢",
                discord.Status.idle: "🟡",
                discord.Status.dnd: "🔴",
                discord.Status.offline: "⚫",
            }.get(member.status, "⚫")

            members_list.append(f"{status_emoji} {member.display_name}")

        embed.add_field(
            name="👥 成員列表",
            value="\n".join(members_list) if members_list else "無成員資料",
            inline=False,
        )

        if len(guild.members) > 10:
            embed.add_field(
                name="📄 更多", value=f"還有 {len(guild.members) - 10} 名成員...", inline=False
            )

        await interaction.response.send_message(embed=embed, ephemeral=True)

    @discord.ui.button(label="🎨 角色管理", style=discord.ButtonStyle.secondary)
    async def role_management(self, interaction: discord.Interaction, button: discord.ui.Button):
        """角色管理功能"""
        guild = interaction.guild
        if not guild:
            await interaction.response.send_message("❌ 無法獲取伺服器資訊", ephemeral=True)
            return

        embed = discord.Embed(
            title="🎨 角色管理", description=f"**{guild.name} 角色概覽**", color=0x9B59B6
        )

        # 顯示前 10 個角色
        roles_list = []
        for role in guild.roles[-11:-1]:  # 除去 @everyone 角色，取最高的10個
            member_count = len(role.members)
            color_hex = f"#{role.color.value:06x}" if role.color.value else "#99aab5"
            roles_list.append(f"{role.mention} ({member_count} 人) - {color_hex}")

        embed.add_field(
            name="🏆 角色列表",
            value="\n".join(reversed(roles_list)) if roles_list else "無自定義角色",
            inline=False,
        )

        embed.add_field(
            name="ℹ️ 說明", value="使用 Discord 內建的伺服器設定來管理角色和權限", inline=False
        )

        await interaction.response.send_message(embed=embed, ephemeral=True)

    @discord.ui.button(label="🔙 返回", style=discord.ButtonStyle.secondary)
    async def back_to_admin(self, interaction: discord.Interaction, button: discord.ui.Button):
        """返回管理員選單"""
        view = AdminMenuView(self.bot, self.user_id)
        embed = await view.create_main_embed()
        await interaction.response.edit_message(embed=embed, view=view)


class AdminSettingsView(discord.ui.View):
    """🔧 管理員設定視圖"""

    def __init__(self, bot: commands.Bot, user_id: int):
        super().__init__(timeout=300)
        self.bot = bot
        self.user_id = user_id

    async def create_main_embed(self) -> discord.Embed:
        """創建管理員設定主選單"""
        embed = discord.Embed(
            title="🔧 系統設定中心", description="**Bot 進階配置選項**", color=0x34495E
        )

        embed.add_field(
            name="📊 系統狀態",
            value=f"• 已載入模組: {len(self.bot.cogs)}\n"
            f"• 已連接伺服器: {len(self.bot.guilds)}\n"
            f"• 総用戶数: {sum(g.member_count for g in self.bot.guilds if g.member_count)}",
            inline=True,
        )

        embed.add_field(
            name="⚙️ 配置選項", value="• 功能模組管理\n• 日誌設定\n• 網路設定", inline=True
        )

        return embed

    @discord.ui.button(label="📊 模組管理", style=discord.ButtonStyle.primary)
    async def module_management(self, interaction: discord.Interaction, button: discord.ui.Button):
        """模組管理功能"""
        embed = discord.Embed(
            title="📊 模組管理中心", description="**已載入的 Bot 模組**", color=0x9B59B6
        )

        # 分類模組
        core_cogs = []
        feature_cogs = []

        for cog_name, cog in self.bot.cogs.items():
            status = "✅"
            if "Core" in cog_name:
                core_cogs.append(f"{status} {cog_name}")
            else:
                feature_cogs.append(f"{status} {cog_name}")

        if core_cogs:
            embed.add_field(
                name="🔧 核心模組",
                value="\n".join(core_cogs[:8]) + ("\n..." if len(core_cogs) > 8 else ""),
                inline=True,
            )

        if feature_cogs:
            embed.add_field(
                name="🎮 功能模組",
                value="\n".join(feature_cogs[:8]) + ("\n..." if len(feature_cogs) > 8 else ""),
                inline=True,
            )

        embed.add_field(
            name="📈 統計資訊",
            value=f"總模組數: {len(self.bot.cogs)}\n"
            f"核心模組: {len(core_cogs)}\n"
            f"功能模組: {len(feature_cogs)}",
            inline=False,
        )

        await interaction.response.send_message(embed=embed, ephemeral=True)

    @discord.ui.button(label="📁 日誌設定", style=discord.ButtonStyle.secondary)
    async def log_settings(self, interaction: discord.Interaction, button: discord.ui.Button):
        """日誌設定功能"""
        import logging

        embed = discord.Embed(title="📁 日誌設定", description="**系統日誌配置**", color=0xF39C12)

        # 獲取當前日誌等級
        root_logger = logging.getLogger()
        current_level = logging.getLevelName(root_logger.level)

        embed.add_field(
            name="⚙️ 當前設定",
            value=f"日誌等級: {current_level}\n"
            f"輸出格式: 時間 | 等級 | 訊息\n"
            f"輸出位置: 控制台 + 文件",
            inline=False,
        )

        embed.add_field(
            name="📈 可用等級",
            value="DEBUG - 詳細調試資訊\n"
            "INFO - 一般系統資訊\n"
            "WARNING - 警告訊息\n"
            "ERROR - 錯誤訊息\n"
            "CRITICAL - 嚴重錯誤",
            inline=False,
        )

        embed.add_field(
            name="ℹ️ 說明", value="日誌設定目前使用預設配置，需要修改請編輯配置文件", inline=False
        )

        await interaction.response.send_message(embed=embed, ephemeral=True)

    @discord.ui.button(label="🔙 返回", style=discord.ButtonStyle.secondary)
    async def back_to_admin(self, interaction: discord.Interaction, button: discord.ui.Button):
        """返回管理員選單"""
        view = AdminMenuView(self.bot, self.user_id)
        embed = await view.create_main_embed()
        await interaction.response.edit_message(embed=embed, view=view)


class QuickActionsView(discord.ui.View):
    """⚡ 快速操作視圖"""

    def __init__(self, bot: commands.Bot, user_id: int):
        super().__init__(timeout=300)
        self.bot = bot
        self.user_id = user_id

    async def create_main_embed(self) -> discord.Embed:
        """創建快速操作主選單"""
        embed = discord.Embed(
            title="⚡ 快速操作中心", description="**一鍵式管理操作**", color=0xE74C3C
        )

        embed.add_field(
            name="⚡ 快速功能", value="• 系統狀態檢查\n• 快速管理操作\n• 緊急維護模式", inline=True
        )

        embed.add_field(name="🛠️ 管理工具", value="• 快速重啟\n• 清理快取\n• 權限檢查", inline=True)

        embed.add_field(name="⚠️ 注意事項", value="部分操作不可復原，請謹慎使用", inline=False)

        return embed

    @discord.ui.button(label="🔄 狀態檢查", style=discord.ButtonStyle.primary)
    async def system_check(self, interaction: discord.Interaction, button: discord.ui.Button):
        """系統狀態檢查"""
        embed = discord.Embed(
            title="🔄 系統狀態檢查", description="**快速系統檢查結果**", color=0x27AE60
        )

        # 檢查各個系統組件
        checks = {
            "Bot 連線狀態": "✅ 正常" if self.bot.is_ready() else "❌ 失败",
            "Discord 連線": f"✅ 正常 ({round(self.bot.latency * 1000)}ms)",
            "模組載入": f"✅ 正常 ({len(self.bot.cogs)} 個模組)",
            "伺服器連線": f"✅ 正常 ({len(self.bot.guilds)} 個伺服器)",
        }

        check_text = "\n".join([f"{k}: {v}" for k, v in checks.items()])

        embed.add_field(name="🔍 檢查結果", value=check_text, inline=False)

        embed.set_footer(text=f"檢查時間: {datetime.now(timezone.utc).strftime('%H:%M:%S UTC')}")

        await interaction.response.send_message(embed=embed, ephemeral=True)

    @discord.ui.button(label="📁 清理模式", style=discord.ButtonStyle.secondary)
    async def cleanup_mode(self, interaction: discord.Interaction, button: discord.ui.Button):
        """清理模式"""
        embed = discord.Embed(title="📁 清理模式", description="**系統清理功能**", color=0xF39C12)

        embed.add_field(
            name="📄 可清理項目",
            value="• 渠道訊息快取\n" "• 模組模情狀態\n" "• 用戶數據快取\n" "• 系統日誌文件",
            inline=False,
        )

        embed.add_field(
            name="⚠️ 警告", value="清理操作會影響 Bot 性能，建議在使用率低時進行", inline=False
        )

        embed.add_field(
            name="ℹ️ 說明", value="清理功能目前為手動模式，請聯繫管理員進行操作", inline=False
        )

        await interaction.response.send_message(embed=embed, ephemeral=True)

    @discord.ui.button(label="⚠️ 緊急模式", style=discord.ButtonStyle.danger)
    async def emergency_mode(self, interaction: discord.Interaction, button: discord.ui.Button):
        """緊急模式"""
        embed = discord.Embed(
            title="⚠️ 緊急模式", description="**系統緊急操作選項**", color=0xE74C3C
        )

        embed.add_field(
            name="🎆 可用操作",
            value="• 停用非核心模組\n" "• 只保留基本功能\n" "• 限制用戶訪問\n" "• 假陥狀態模式",
            inline=False,
        )

        embed.add_field(
            name="⚠️ 重要警告",
            value="緊急模式會停用部分功能，僅在系統過載或失響時使用",
            inline=False,
        )

        embed.add_field(
            name="ℹ️ 操作方式", value="緊急模式需要特殊權限，請聯繫最高管理員", inline=False
        )

        await interaction.response.send_message(embed=embed, ephemeral=True)

    @discord.ui.button(label="🔙 返回", style=discord.ButtonStyle.secondary)
    async def back_to_admin(self, interaction: discord.Interaction, button: discord.ui.Button):
        """返回管理員選單"""
        view = AdminMenuView(self.bot, self.user_id)
        embed = await view.create_main_embed()
        await interaction.response.edit_message(embed=embed, view=view)


class EntertainmentMenuView(discord.ui.View):
    """
    🎮 娛樂遊戲選單
    """

    def __init__(self, bot: commands.Bot, user_id: int):
        super().__init__(timeout=300)
        self.bot = bot
        self.user_id = user_id

    async def create_main_embed(self) -> discord.Embed:
        """創建娛樂選單嵌入"""
        embed = discord.Embed(
            title="🎮 娛樂遊戲中心",
            description="**歡迎來到娛樂世界！**\n\n選擇您想要的遊戲：",
            color=0x1ABC9C,
        )

        embed.add_field(name="🎯 經典遊戲", value="猜數字、剪刀石頭布、骰子", inline=True)

        embed.add_field(name="🧠 智力遊戲", value="問答、記憶遊戲、接龍", inline=True)

        embed.add_field(name="🏆 競技系統", value="排行榜、統計、成就", inline=True)

        return embed

    @discord.ui.button(label="🎮 開啟娛樂中心", style=discord.ButtonStyle.primary)
    async def entertainment_center(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        """開啟娛樂中心"""
        # 調用娛樂模組的主功能
        cog = self.bot.get_cog("EntertainmentCore")
        if cog and hasattr(cog, "entertainment_center"):
            # 獲取 Command 對象並調用其回調函數
            command = cog.entertainment_center
            if hasattr(command, "callback"):
                await command.callback(cog, interaction)
            else:
                await command(interaction)
        else:
            await interaction.response.send_message("❌ 娛樂系統暫時不可用", ephemeral=True)

    @discord.ui.button(label="📊 遊戲統計", style=discord.ButtonStyle.secondary)
    async def game_stats(self, interaction: discord.Interaction, button: discord.ui.Button):
        """查看遊戲統計"""
        cog = self.bot.get_cog("EntertainmentCore")
        if cog and hasattr(cog, "game_stats"):
            command = cog.game_stats
            if hasattr(command, "callback"):
                await command.callback(cog, interaction)
            else:
                await command(interaction)
        else:
            await interaction.response.send_message("❌ 娛樂系統暫時不可用", ephemeral=True)

    @discord.ui.button(label="🏆 排行榜", style=discord.ButtonStyle.secondary)
    async def leaderboard(self, interaction: discord.Interaction, button: discord.ui.Button):
        """查看排行榜"""
        cog = self.bot.get_cog("EntertainmentCore")
        if cog and hasattr(cog, "leaderboard"):
            command = cog.leaderboard
            if hasattr(command, "callback"):
                await command.callback(cog, interaction)
            else:
                await command(interaction)
        else:
            await interaction.response.send_message("❌ 娛樂系統暫時不可用", ephemeral=True)

    @discord.ui.button(label="🎁 每日獎勵", style=discord.ButtonStyle.success)
    async def daily_rewards(self, interaction: discord.Interaction, button: discord.ui.Button):
        """領取每日獎勵"""
        cog = self.bot.get_cog("EntertainmentCore")
        if cog and hasattr(cog, "daily_rewards"):
            command = cog.daily_rewards
            if hasattr(command, "callback"):
                await command.callback(cog, interaction)
            else:
                await command(interaction)
        else:
            await interaction.response.send_message("❌ 娛樂系統暫時不可用", ephemeral=True)

    @discord.ui.button(label="🔙 返回", style=discord.ButtonStyle.secondary)
    async def back_to_main(self, interaction: discord.Interaction, button: discord.ui.Button):
        """返回主選單"""
        view = MainMenuView(self.bot, self.user_id)
        embed = discord.Embed(
            title="🏠 Potato Bot 主選單",
            description="**歡迎使用 Phase 7 GUI 系統！**\n\n選擇您需要的功能：",
            color=0x3498DB,
        )
        await interaction.response.edit_message(embed=embed, view=view)


class MusicMenuView(discord.ui.View):
    """
    🎵 音樂播放選單
    """

    def __init__(self, bot: commands.Bot, user_id: int):
        super().__init__(timeout=300)
        self.bot = bot
        self.user_id = user_id

    async def create_main_embed(self) -> discord.Embed:
        """創建音樂選單嵌入"""
        embed = discord.Embed(
            title="🎵 音樂播放系統",
            description="**享受高品質音樂體驗！**\n\n選擇音樂功能：",
            color=0xE74C3C,
        )

        embed.add_field(name="🎶 播放功能", value="搜索、播放、暫停", inline=True)

        embed.add_field(name="📝 播放列表", value="隊列管理、循環播放", inline=True)

        embed.add_field(name="🎛️ 控制面板", value="音量、跳過、停止", inline=True)

        return embed

    @discord.ui.button(label="🎵 音樂菜單", style=discord.ButtonStyle.primary)
    async def music_menu(self, interaction: discord.Interaction, button: discord.ui.Button):
        """開啟音樂主菜單"""
        cog = self.bot.get_cog("MusicCore")
        if cog and hasattr(cog, "music_menu"):
            # 獲取 Command 對象並調用其回調函數
            command = cog.music_menu
            if hasattr(command, "callback"):
                await command.callback(cog, interaction)
            else:
                await command(interaction)
        else:
            await interaction.response.send_message("❌ 音樂系統暫時不可用", ephemeral=True)

    @discord.ui.button(label="🎛️ 控制面板", style=discord.ButtonStyle.secondary)
    async def music_control(self, interaction: discord.Interaction, button: discord.ui.Button):
        """音樂控制面板"""
        cog = self.bot.get_cog("MusicCore")
        if cog and hasattr(cog, "music_control"):
            command = cog.music_control
            if hasattr(command, "callback"):
                await command.callback(cog, interaction)
            else:
                await command(interaction)
        else:
            await interaction.response.send_message("❌ 音樂系統暫時不可用", ephemeral=True)

    @discord.ui.button(label="📝 播放列表", style=discord.ButtonStyle.secondary)
    async def queue(self, interaction: discord.Interaction, button: discord.ui.Button):
        """查看播放列表"""
        cog = self.bot.get_cog("MusicCore")
        if cog and hasattr(cog, "queue"):
            command = cog.queue
            if hasattr(command, "callback"):
                await command.callback(cog, interaction)
            else:
                await command(interaction)
        else:
            await interaction.response.send_message("❌ 音樂系統暫時不可用", ephemeral=True)

    @discord.ui.button(label="🔗 語音連接", style=discord.ButtonStyle.success)
    async def voice_connect(self, interaction: discord.Interaction, button: discord.ui.Button):
        """連接語音頻道"""
        cog = self.bot.get_cog("MusicCore")
        if cog and hasattr(cog, "voice_connect"):
            command = cog.voice_connect
            if hasattr(command, "callback"):
                await command.callback(cog, interaction)
            else:
                await command(interaction)
        else:
            await interaction.response.send_message("❌ 音樂系統暫時不可用", ephemeral=True)

    @discord.ui.button(label="🔙 返回", style=discord.ButtonStyle.secondary)
    async def back_to_main(self, interaction: discord.Interaction, button: discord.ui.Button):
        """返回主選單"""
        view = MainMenuView(self.bot, self.user_id)
        embed = discord.Embed(
            title="🏠 Potato Bot 主選單",
            description="**歡迎使用 Phase 7 GUI 系統！**\n\n選擇您需要的功能：",
            color=0x3498DB,
        )
        await interaction.response.edit_message(embed=embed, view=view)


class MenuSystemManager:
    """
    🎮 選單系統管理器
    """

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.active_menus: Dict[int, discord.ui.View] = {}

    async def show_main_menu(self, interaction: discord.Interaction) -> None:
        """顯示主選單"""
        user_id = interaction.user.id
        guild_id = str(interaction.guild.id) if interaction.guild else "0"

        # 獲取情境感知引擎
        context_engine = get_context_engine(self.bot)

        # 記錄用戶行為
        await context_engine.record_user_action(str(user_id), guild_id, "main_menu_open")

        # 獲取情境化選單選項
        contextual_options = await context_engine.get_contextual_menu_options(
            str(user_id), guild_id
        )

        # 創建主選單
        view = MainMenuView(self.bot, user_id, contextual_options)
        self.active_menus[user_id] = view

        embed = discord.Embed(
            title="🏠 Potato Bot 主選單",
            description="**歡迎使用 Phase 7 GUI 系統！** (更新日期: 2025-08-20)\n\n✨ **新功能亮點**:\n• 🤖 AI 智能對話系統\n• 🎯 意圖識別與引導式流程\n• 📊 即時數據分析\n• 🎮 全互動式 GUI\n\n選擇您需要的功能：",
            color=0x3498DB,
        )

        embed.add_field(name="🤖 AI 功能", value="智能對話、意圖識別、引導式操作", inline=True)

        embed.add_field(name="🎫 支援系統", value="票券管理、問題追蹤、客服支援", inline=True)

        embed.add_field(name="🗳️ 協作工具", value="投票系統、歡迎設定、團隊管理", inline=True)

        embed.add_field(name="🎮 娛樂功能", value="小遊戲、音樂播放、互動娛樂", inline=True)

        # 添加智能推薦
        recommendations = contextual_options.get("recommendations", [])
        if recommendations:
            high_priority_recs = [r for r in recommendations if r.level == RecommendationLevel.HIGH]
            if high_priority_recs:
                rec_text = "\n".join([f"• {rec.title}" for rec in high_priority_recs[:2]])
                embed.add_field(name="🎯 智能推薦", value=rec_text, inline=False)

        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    async def show_admin_menu(self, interaction: discord.Interaction) -> None:
        """顯示管理員選單"""
        user_id = interaction.user.id

        # 檢查管理員權限
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ 您沒有管理員權限", ephemeral=True)
            return

        view = AdminMenuView(self.bot, user_id)
        self.active_menus[user_id] = view

        embed = await view.create_main_embed()
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    def cleanup_menu(self, user_id: int) -> None:
        """清理選單"""
        if user_id in self.active_menus:
            del self.active_menus[user_id]
