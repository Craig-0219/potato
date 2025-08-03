# bot/views/ticket_views.py - v2.1
"""
票券系統專用互動式 UI View 模組
支援 Persistent View 註冊、分頁、評分、控制操作
"""

import discord
from discord.ui import View, Button, Select, button, select
from typing import List, Optional, Dict, Any

from bot.utils.ticket_constants import TicketConstants
from shared.logger import logger

# ============ 票券主面板 View ============

class TicketPanelView(View):
    """
    票券主面板（PersistentView）
    顯示所有可建立的票券類型
    """
    def __init__(self, settings: Optional[Dict[str, Any]] = None, timeout=None):
        super().__init__(timeout=timeout)
        self.settings = settings or {}  # 防呆
        ticket_types = self.settings.get('ticket_types', TicketConstants.DEFAULT_TICKET_TYPES)
        self.add_item(TicketTypeSelect(ticket_types))

class TicketTypeSelect(Select):
    """
    下拉選單：選擇票券類型
    """
    def __init__(self, ticket_types: List[Dict]):
        options = [
            discord.SelectOption(label=tp['name'], value=tp['name'], description=tp.get('description', ''))
            for tp in ticket_types
        ] if ticket_types else [
            discord.SelectOption(label="一般問題", value="general", description="一般疑難與協助")
        ]
        super().__init__(placeholder="請選擇票券類型...", min_values=1, max_values=1, options=options, custom_id="ticket_panel_type_select")

    async def callback(self, interaction: discord.Interaction):
        ticket_type = self.values[0]
        await interaction.response.send_message(
            f"📝 正在建立 {ticket_type} 票券...", ephemeral=True
        )
        # 此處可串接 ticket_core 或發事件（由 listener 處理建立流程）


# ============ 單一票券操作區 View ============

class TicketControlView(View):
    """
    單一票券頻道的控制列（PersistentView）
    包含關閉、指派、評分等按鈕
    """
    def __init__(self, can_close=True, can_assign=True, can_rate=False, ticket_id: Optional[int]=None, timeout=None):
        super().__init__(timeout=timeout)
        self.can_close = can_close
        self.can_assign = can_assign
        self.can_rate = can_rate
        self.ticket_id = ticket_id

        if can_close:
            self.add_item(TicketCloseButton())
        if can_assign:
            self.add_item(TicketAssignButton())
        if can_rate:
            self.add_item(RatingButton(ticket_id))

class TicketCloseButton(Button):
    def __init__(self):
        super().__init__(style=discord.ButtonStyle.danger, label="關閉票券", emoji="🔒", custom_id="ticket_close_btn")

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.send_message("❓ 請稍候，正在關閉票券...", ephemeral=True)
        # 這裡可直接呼叫 ticket_core 的 close_ticket 或發事件

class TicketAssignButton(Button):
    def __init__(self):
        super().__init__(style=discord.ButtonStyle.primary, label="指派客服", emoji="👥", custom_id="ticket_assign_btn")

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.send_message("🔄 請輸入要指派的客服", ephemeral=True)
        # 可引導用戶輸入/選擇指派對象

class RatingButton(Button):
    def __init__(self, ticket_id: Optional[int]):
        super().__init__(style=discord.ButtonStyle.success, label="評分票券", emoji="⭐", custom_id=f"ticket_rating_btn_{ticket_id or 'x'}")

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.send_message("請點擊下方進行評分：", ephemeral=True, view=RatingView(ticket_id=self.custom_id.split('_')[-1]))


# ============ 評分/回饋專用 View ============

class RatingView(View):
    """
    票券評分專用 View（可直接多星點擊）
    """
    def __init__(self, ticket_id: int, timeout=300):
        super().__init__(timeout=timeout)
        self.ticket_id = ticket_id

    @button(label="1 星", style=discord.ButtonStyle.secondary, emoji="⭐", custom_id="rating_1")
    async def rate_1(self, interaction: discord.Interaction, button: Button):
        await self.send_rating(interaction, 1)

    @button(label="2 星", style=discord.ButtonStyle.secondary, emoji="⭐⭐", custom_id="rating_2")
    async def rate_2(self, interaction: discord.Interaction, button: Button):
        await self.send_rating(interaction, 2)

    @button(label="3 星", style=discord.ButtonStyle.secondary, emoji="⭐⭐⭐", custom_id="rating_3")
    async def rate_3(self, interaction: discord.Interaction, button: Button):
        await self.send_rating(interaction, 3)

    @button(label="4 星", style=discord.ButtonStyle.success, emoji="⭐⭐⭐⭐", custom_id="rating_4")
    async def rate_4(self, interaction: discord.Interaction, button: Button):
        await self.send_rating(interaction, 4)

    @button(label="5 星", style=discord.ButtonStyle.success, emoji="⭐⭐⭐⭐⭐", custom_id="rating_5")
    async def rate_5(self, interaction: discord.Interaction, button: Button):
        await self.send_rating(interaction, 5)

    async def send_rating(self, interaction: discord.Interaction, rating: int):
        # 可以改為直接呼叫 ticket_core 的 rate_ticket，這裡為展示用
        await interaction.response.send_message(
            f"感謝您的評分！票券 {self.ticket_id}，評分：{rating} 星", ephemeral=True
        )
        # 此處可以加 popup modal 收集額外回饋

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
        super().__init__(label="上一頁", style=discord.ButtonStyle.secondary, custom_id="list_prev")
        self.parent = parent

    async def callback(self, interaction: discord.Interaction):
        # 這裡應該呼叫 parent.page - 1 查詢刷新
        await interaction.response.send_message("⬅️ 上一頁（待接資料查詢刷新）", ephemeral=True)

class NextPageButton(Button):
    def __init__(self, parent: TicketListView):
        super().__init__(label="下一頁", style=discord.ButtonStyle.secondary, custom_id="list_next")
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
        bot.add_view(TicketPanelView(), persistent=True)
        bot.add_view(TicketControlView(), persistent=True)
        bot.add_view(RatingView(ticket_id=0))
        # 分頁、評分等如果需 Persistent 也可註冊
        logger.info("✅ 票券所有主要 View 已註冊 PersistentView")
    except Exception as e:
        logger.error(f"❌ Persistent View 註冊失敗：{e}")

