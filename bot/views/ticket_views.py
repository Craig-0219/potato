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
        try:
            ticket_type = self.values[0]
            
            # 顯示優先級選擇
            embed = discord.Embed(
                title="🎯 選擇票券優先級",
                description=f"正在建立 **{ticket_type}** 票券\n請選擇此問題的緊急程度：",
                color=0x3498db
            )
            
            embed.add_field(
                name="🔴 高優先級",
                value="緊急問題、系統故障、安全問題\n預期 30 分鐘內回應",
                inline=False
            )
            
            embed.add_field(
                name="🟡 中優先級",
                value="一般問題、功能諮詢\n預期 1-2 小時內回應",
                inline=False
            )
            
            embed.add_field(
                name="🟢 低優先級",
                value="建議回饋、非緊急問題\n預期 4-8 小時內回應",
                inline=False
            )
            
            view = PrioritySelectView(ticket_type, interaction.user.id)
            await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
                
        except Exception as e:
            logger.error(f"票券建立流程錯誤: {e}")
            await interaction.response.send_message(
                "❌ 建立票券時發生錯誤，請稍後再試或聯繫管理員。", ephemeral=True
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
                emoji="🔴"
            ),
            discord.SelectOption(
                label="🟡 中優先級 - 一般問題",
                value="medium",
                description="一般問題、功能諮詢（推薦選項）",
                emoji="🟡"
            ),
            discord.SelectOption(
                label="🟢 低優先級 - 非緊急問題",
                value="low",
                description="建議回饋、非緊急問題",
                emoji="🟢"
            )
        ]
        
        super().__init__(
            placeholder="請選擇問題的緊急程度...",
            min_values=1,
            max_values=1,
            options=options,
            custom_id=f"priority_select_{user_id}"
        )
    
    async def callback(self, interaction: discord.Interaction):
        try:
            # 檢查是否為同一用戶
            if interaction.user.id != self.user_id:
                await interaction.response.send_message("❌ 只有票券建立者可以選擇優先級。", ephemeral=True)
                return
            
            priority = self.values[0]
            priority_name = {'high': '高', 'medium': '中', 'low': '低'}.get(priority, priority)
            priority_emoji = {'high': '🔴', 'medium': '🟡', 'low': '🟢'}.get(priority, '🟡')
            
            await interaction.response.send_message(
                f"📝 正在建立 {priority_emoji} **{priority_name}優先級** {self.ticket_type} 票券...", 
                ephemeral=True
            )
            
            # 調用票券創建邏輯
            from bot.services.ticket_manager import TicketManager
            from bot.db.ticket_dao import TicketDAO
            
            ticket_dao = TicketDAO()
            ticket_manager = TicketManager(ticket_dao)
            
            # 確保是在 Guild 中且用戶是 Member
            if not interaction.guild:
                await interaction.followup.send(
                    "❌ 只能在伺服器中建立票券。", ephemeral=True
                )
                return
            
            # 確保 interaction.user 是 Member
            user = interaction.user
            if not isinstance(user, discord.Member):
                user = interaction.guild.get_member(interaction.user.id)
                if not user:
                    await interaction.followup.send(
                        "❌ 無法在此伺服器中找到您的成員資訊。", ephemeral=True
                    )
                    return
            
            success, message, ticket_id = await ticket_manager.create_ticket(
                user=user,
                ticket_type=self.ticket_type,
                priority=priority
            )
            
            if success:
                # 根據優先級顯示不同顏色的成功訊息
                priority_colors = {'high': 0xff0000, 'medium': 0xffaa00, 'low': 0x00ff00}
                
                embed = discord.Embed(
                    title="✅ 票券建立成功！",
                    description=f"{message}\n\n{priority_emoji} **{priority_name}優先級** - {self.ticket_type}",
                    color=priority_colors.get(priority, 0x00ff00)
                )
                
                if priority == 'high':
                    embed.add_field(
                        name="⚡ 高優先級處理",
                        value="您的票券已標記為高優先級，客服團隊將優先處理。\n預期 30 分鐘內回應。",
                        inline=False
                    )
                elif priority == 'medium':
                    embed.add_field(
                        name="📋 一般處理流程",
                        value="您的票券將按正常流程處理。\n預期 1-2 小時內回應。",
                        inline=False
                    )
                else:
                    embed.add_field(
                        name="🕐 非緊急處理",
                        value="您的票券已加入處理佇列。\n預期 4-8 小時內回應。",
                        inline=False
                    )
                
                await interaction.followup.send(embed=embed, ephemeral=True)
                
                # 如果是高優先級，自動嘗試指派
                if priority == 'high' and ticket_id:
                    try:
                        from bot.services.assignment_manager import AssignmentManager
                        from bot.db.assignment_dao import AssignmentDAO
                        
                        assignment_dao = AssignmentDAO()
                        assignment_manager = AssignmentManager(assignment_dao, ticket_dao)
                        
                        # 嘗試自動指派高優先級票券
                        auto_success, auto_message, assigned_to = await assignment_manager.auto_assign_ticket(
                            ticket_id, user.id
                        )
                        
                        if auto_success and assigned_to:
                            logger.info(f"高優先級票券 #{ticket_id} 自動指派給 {assigned_to}")
                        
                    except Exception as auto_assign_error:
                        logger.error(f"高優先級票券自動指派失敗: {auto_assign_error}")
                
            else:
                await interaction.followup.send(
                    f"❌ {message}", ephemeral=True
                )
                
        except Exception as e:
            logger.error(f"優先級選擇處理錯誤: {e}")
            try:
                await interaction.followup.send(
                    "❌ 建立票券時發生錯誤，請稍後再試或聯繫管理員。", ephemeral=True
                )
            except:
                pass


# ============ 單一票券操作區 View ============

class TicketControlView(View):
    """
    單一票券頻道的控制列（PersistentView）
    包含關閉、指派、評分等按鈕，以及優先級狀態顯示
    """
    def __init__(self, can_close=True, can_assign=True, can_rate=False, ticket_id: Optional[int]=None, 
                 priority: str = None, timeout=None):
        super().__init__(timeout=timeout)
        self.can_close = can_close
        self.can_assign = can_assign
        self.can_rate = can_rate
        self.ticket_id = ticket_id
        self.priority = priority

        # 添加優先級狀態按鈕（僅顯示，不可點擊）
        if priority:
            self.add_item(PriorityStatusButton(priority))
        
        if can_close:
            self.add_item(TicketCloseButton())
        if can_assign:
            self.add_item(TicketAssignButton())
        if can_rate:
            self.add_item(RatingButton(ticket_id))

class PriorityStatusButton(Button):
    """優先級狀態顯示按鈕（僅用於視覺顯示）"""
    def __init__(self, priority: str):
        priority_config = {
            'high': {'emoji': '🔴', 'label': '高優先級', 'style': discord.ButtonStyle.danger},
            'medium': {'emoji': '🟡', 'label': '中優先級', 'style': discord.ButtonStyle.secondary},
            'low': {'emoji': '🟢', 'label': '低優先級', 'style': discord.ButtonStyle.success}
        }
        
        config = priority_config.get(priority, priority_config['medium'])
        
        super().__init__(
            style=config['style'], 
            label=config['label'], 
            emoji=config['emoji'], 
            custom_id=f"priority_status_{priority}",
            disabled=True  # 設為禁用，僅用於顯示
        )

    async def callback(self, interaction: discord.Interaction):
        # 這個按鈕不應該被點擊，但以防萬一
        await interaction.response.send_message("此按鈕僅用於顯示優先級狀態。", ephemeral=True)

class TicketCloseButton(Button):
    def __init__(self):
        super().__init__(style=discord.ButtonStyle.danger, label="關閉票券", emoji="🔒", custom_id="ticket_close_btn")

    async def callback(self, interaction: discord.Interaction):
        """處理關閉票券按鈕點擊"""
        try:
            # 先回應用戶，避免超時
            await interaction.response.send_message("🔄 請稍候，正在關閉票券...", ephemeral=True)
            
            # 獲取票券核心處理器
            ticket_core = interaction.client.get_cog("TicketCore")
            if not ticket_core:
                await interaction.followup.send("❌ 系統錯誤：找不到票券處理模組", ephemeral=True)
                return
            
            # 檢查是否為票券頻道
            if not await ticket_core._is_ticket_channel(interaction.channel):
                await interaction.followup.send("❌ 此按鈕只能在票券頻道中使用", ephemeral=True)
                return
            
            # 獲取票券資訊
            ticket = await ticket_core.DAO.get_ticket_by_channel(interaction.channel.id)
            if not ticket:
                await interaction.followup.send("❌ 找不到票券資訊", ephemeral=True)
                return
            
            if ticket['status'] == 'closed':
                await interaction.followup.send("❌ 此票券已經關閉", ephemeral=True)
                return
            
            # 檢查權限
            settings = await ticket_core.DAO.get_settings(interaction.guild.id)
            can_close = await ticket_core._check_close_permission(interaction.user, ticket, settings)
            if not can_close:
                await interaction.followup.send("❌ 只有票券創建者或客服人員可以關閉票券", ephemeral=True)
                return
            
            # 關閉票券
            success = await ticket_core.manager.close_ticket(
                ticket_id=ticket['id'],
                closed_by=interaction.user.id,
                reason="按鈕關閉"
            )
            
            if success:
                # 更新指派統計（如果票券有指派）
                if ticket.get('assigned_to'):
                    await ticket_core.assignment_manager.update_ticket_completion(ticket['id'])
                
                # 發送成功消息
                from bot.utils.embed_builder import EmbedBuilder
                from bot.utils.ticket_constants import TicketConstants
                
                embed = EmbedBuilder.build(
                    title="✅ 票券已關閉",
                    description=f"票券 #{ticket['id']:04d} 已成功關閉",
                    color=TicketConstants.COLORS['success']
                )
                embed.add_field(name="關閉原因", value="按鈕關閉", inline=False)
                embed.add_field(name="關閉者", value=interaction.user.mention, inline=False)
                
                await interaction.followup.send(embed=embed)
                
                # 顯示評分界面
                await ticket_core._show_rating_interface(interaction.channel, ticket['id'])
                
                # 30秒後刪除頻道
                await ticket_core._schedule_channel_deletion(interaction.channel, 30)
                
            else:
                await interaction.followup.send("❌ 關閉票券時發生錯誤", ephemeral=True)
                
        except Exception as e:
            from shared.logger import logger
            logger.error(f"關閉票券按鈕錯誤: {e}")
            try:
                await interaction.followup.send("❌ 處理關閉票券請求時發生錯誤", ephemeral=True)
            except:
                pass

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

    @button(label="1 星", style=discord.ButtonStyle.secondary, emoji="1️⃣", custom_id="rating_1")
    async def rate_1(self, interaction: discord.Interaction, button: Button):
        await self.send_rating(interaction, 1)

    @button(label="2 星", style=discord.ButtonStyle.secondary, emoji="2️⃣", custom_id="rating_2")
    async def rate_2(self, interaction: discord.Interaction, button: Button):
        await self.send_rating(interaction, 2)

    @button(label="3 星", style=discord.ButtonStyle.secondary, emoji="3️⃣", custom_id="rating_3")
    async def rate_3(self, interaction: discord.Interaction, button: Button):
        await self.send_rating(interaction, 3)

    @button(label="4 星", style=discord.ButtonStyle.success, emoji="4️⃣", custom_id="rating_4")
    async def rate_4(self, interaction: discord.Interaction, button: Button):
        await self.send_rating(interaction, 4)

    @button(label="5 星", style=discord.ButtonStyle.success, emoji="5️⃣", custom_id="rating_5")
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

