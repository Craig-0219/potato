# bot/views/ticket_views.py - v2.1
"""
票券系統專用互動式 UI View 模組
支援 Persistent View 註冊、分頁、控制操作
"""

from typing import Any, Dict, List, Optional

import discord
from discord.ui import Button, Select, View

from potato_bot.utils.ticket_constants import TicketConstants
from potato_bot.utils.managed_cog import register_persistent_view
from potato_shared.logger import logger

# ============ 票券主面板 View ============


class TicketPanelView(View):
    """
    票券主面板（PersistentView）
    顯示所有可建立的票券類型
    """

    def __init__(self, settings: Optional[Dict[str, Any]] = None, timeout=None):
        super().__init__(timeout=timeout)
        self.settings = settings or {}  # 防呆
        ticket_types = self.settings.get("ticket_types", TicketConstants.DEFAULT_TICKET_TYPES)
        self.add_item(TicketTypeSelect(ticket_types))


class TicketTypeSelect(Select):
    """
    下拉選單：選擇票券類型
    """

    def __init__(self, ticket_types: List[Dict]):
        options = (
            [
                discord.SelectOption(
                    label=tp["name"],
                    value=tp["name"],
                    description=tp.get("description", ""),
                )
                for tp in ticket_types
            ]
            if ticket_types
            else [
                discord.SelectOption(
                    label="一般問題",
                    value="general",
                    description="一般疑難與協助",
                )
            ]
        )
        super().__init__(
            placeholder="請選擇票券類型...",
            min_values=1,
            max_values=1,
            options=options,
            custom_id="ticket_panel_type_select",
        )

    async def callback(self, interaction: discord.Interaction):
        try:
            ticket_type = self.values[0]

            # 顯示優先級選擇
            embed = discord.Embed(
                title="🎯 選擇票券優先級",
                description=f"正在建立 **{ticket_type}** 票券\n請選擇此問題的緊急程度：",
                color=0x3498DB,
            )

            embed.add_field(
                name="🔴 高優先級",
                value="緊急問題、系統故障、安全問題\n預期 30 分鐘內回應",
                inline=False,
            )

            embed.add_field(
                name="🟡 中優先級",
                value="一般問題、功能諮詢\n預期 1-2 小時內回應",
                inline=False,
            )

            embed.add_field(
                name="🟢 低優先級",
                value="建議回饋、非緊急問題\n預期 4-8 小時內回應",
                inline=False,
            )

            view = PrioritySelectView(ticket_type, interaction.user.id)
            await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

        except Exception as e:
            logger.error(f"票券建立流程錯誤: {e}")
            await interaction.response.send_message(
                "❌ 建立票券時發生錯誤，請稍後再試或聯繫管理員。",
                ephemeral=True,
            )


# ============ 優先級選擇 View ============


class PrioritySelectView(View):
    """優先級選擇視圖"""

    def __init__(self, ticket_type: str, user_id: int, timeout=300):
        super().__init__(timeout=timeout)
        self.ticket_type = ticket_type
        self.user_id = user_id
        self.add_item(PrioritySelect(ticket_type, user_id))


class PrioritySelect(Select):
    """優先級選擇下拉選單"""

    def __init__(self, ticket_type: str, user_id: int):
        self.ticket_type = ticket_type
        self.user_id = user_id

        options = [
            discord.SelectOption(
                label="🔴 高優先級 - 緊急問題",
                value="high",
                description="緊急問題、系統故障、安全問題",
                emoji="🔴",
            ),
            discord.SelectOption(
                label="🟡 中優先級 - 一般問題",
                value="medium",
                description="一般問題、功能諮詢（推薦選項）",
                emoji="🟡",
            ),
            discord.SelectOption(
                label="🟢 低優先級 - 非緊急問題",
                value="low",
                description="建議回饋、非緊急問題",
                emoji="🟢",
            ),
        ]

        super().__init__(
            placeholder="請選擇問題的緊急程度...",
            min_values=1,
            max_values=1,
            options=options,
            custom_id=f"priority_select_{user_id}",
        )

    async def callback(self, interaction: discord.Interaction):
        try:
            if interaction.user.id != self.user_id:
                await interaction.response.send_message(
                    "❌ 只有票券建立者可以選擇優先級。", ephemeral=True
                )
                return

            priority = self.values[0]

            # Get manager from cog
            ticket_core = interaction.client.get_cog("CachedTicketCore")
            if not ticket_core or not hasattr(ticket_core, "manager"):
                await interaction.response.send_message(
                    "❌ 系統錯誤：找不到票券處理模組", ephemeral=True
                )
                return

            await ticket_core.manager.create_ticket_from_interaction(
                interaction, self.ticket_type, priority
            )
            # Delete the ephemeral message that contained the priority selection
            await interaction.delete_original_response()

        except Exception as e:
            logger.error(f"優先級選擇處理錯誤: {e}")
            try:
                # followup is needed because the interaction is deferred in the manager
                await interaction.followup.send(
                    "❌ 建立票券時發生錯誤，請稍後再試或聯繫管理員。",
                    ephemeral=True,
                )
            except:
                pass


# ============ 單一票券操作區 View ============


class TicketControlView(View):
    """
    單一票券頻道的控制列（PersistentView）
    包含關閉按鈕與優先級狀態顯示
    """

    def __init__(self, can_close: bool = True, priority: str = None, timeout=None):
        super().__init__(timeout=timeout)
        self.can_close = can_close
        self.priority = priority

        # 添加優先級狀態按鈕（僅顯示，不可點擊）
        if priority:
            self.add_item(PriorityStatusButton(priority))

        if can_close:
            self.add_item(TicketCloseButton())


class PriorityStatusButton(Button):
    """優先級狀態顯示按鈕（僅用於視覺顯示）"""

    def __init__(self, priority: str):
        priority_config = {
            "high": {
                "emoji": "🔴",
                "label": "高優先級",
                "style": discord.ButtonStyle.danger,
            },
            "medium": {
                "emoji": "🟡",
                "label": "中優先級",
                "style": discord.ButtonStyle.secondary,
            },
            "low": {
                "emoji": "🟢",
                "label": "低優先級",
                "style": discord.ButtonStyle.success,
            },
        }

        config = priority_config.get(priority, priority_config["medium"])

        super().__init__(
            style=config["style"],
            label=config["label"],
            emoji=config["emoji"],
            custom_id=f"priority_status_{priority}",
            disabled=True,  # 設為禁用，僅用於顯示
        )

    async def callback(self, interaction: discord.Interaction):
        # 這個按鈕不應該被點擊，但以防萬一
        await interaction.response.send_message("此按鈕僅用於顯示優先級狀態。", ephemeral=True)


class TicketCloseButton(Button):
    def __init__(self):
        super().__init__(
            style=discord.ButtonStyle.danger,
            label="關閉票券",
            emoji="🔒",
            custom_id="ticket_close_btn",
        )

    async def callback(self, interaction: discord.Interaction):
        """處理關閉票券按鈕點擊"""
        try:
            # 嘗試取得票券核心（優先快取版）
            ticket_core = interaction.client.get_cog("CachedTicketCore") or interaction.client.get_cog(
                "TicketCore"
            )
            if not ticket_core or not hasattr(ticket_core, "manager"):
                await interaction.response.send_message("❌ 系統錯誤：找不到票券處理模組", ephemeral=True)
                return

            await ticket_core.manager.close_ticket_from_interaction(interaction)

        except Exception as e:
            logger.error(f"關閉票券按鈕錯誤: {e}")
            try:
                # followup is needed because the interaction is deferred in the manager
                await interaction.followup.send("❌ 處理關閉票券請求時發生錯誤", ephemeral=True)
            except:
                pass


# ============ 票券分頁/列表瀏覽 ============


class TicketListView(View):
    """
    票券列表分頁 View
    """

    def __init__(self, tickets: List[Dict], page: int, total_pages: int, **query_params):
        super().__init__(timeout=300)
        self.tickets = tickets
        self.page = page
        self.total_pages = total_pages
        self.query_params = query_params

        # 分頁控制
        if page > 1:
            self.add_item(PrevPageButton(self))
        if page < total_pages:
            self.add_item(NextPageButton(self))


class PrevPageButton(Button):
    def __init__(self, parent: TicketListView):
        super().__init__(
            label="上一頁",
            style=discord.ButtonStyle.secondary,
            custom_id="list_prev",
        )
        self.parent = parent

    async def callback(self, interaction: discord.Interaction):
        # 這裡應該呼叫 parent.page - 1 查詢刷新
        await interaction.response.send_message("⬅️ 上一頁（待接資料查詢刷新）", ephemeral=True)


class NextPageButton(Button):
    def __init__(self, parent: TicketListView):
        super().__init__(
            label="下一頁",
            style=discord.ButtonStyle.secondary,
            custom_id="list_next",
        )
        self.parent = parent

    async def callback(self, interaction: discord.Interaction):
        # 這裡應該呼叫 parent.page + 1 查詢刷新
        await interaction.response.send_message("➡️ 下一頁（待接資料查詢刷新）", ephemeral=True)


# ============ Persistent View 統一註冊 ============


def register_ticket_views(bot: discord.Client):
    """
    主程式統一註冊 PersistentView
    """
    try:
        # PanelView 永遠帶防呆空 settings（PersistentView無法帶參數/隨機內容，建議 settings 用預設或查表）
        register_persistent_view(bot, TicketPanelView(), persistent=True)
        register_persistent_view(bot, TicketControlView(), persistent=True)
        # 分頁等如果需 Persistent 也可註冊
        logger.info("✅ 票券所有主要 View 已註冊 PersistentView")
    except Exception as e:
        logger.error(f"❌ Persistent View 註冊失敗：{e}")
