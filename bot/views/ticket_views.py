# bot/ui/ticket_views.py - 票券系統 UI 組件完整版
"""
票券系統 UI 組件 - 簡化但完整的實現
包含所有必要的用戶界面組件
"""

import discord
from discord.ext import commands
from typing import Dict, List, Optional, Any
from datetime import datetime, timezone
import asyncio

from bot.utils.constants import TicketConstants, TicketError
from bot.utils.helpers import format_duration, get_time_ago
from shared.logger import logger


class TicketPanelView(discord.ui.View):
    """主要票券建立面板"""
    
    def __init__(self, settings: Dict[str, Any]):
        super().__init__(timeout=None)
        self.settings = settings
        
        # 添加票券類型按鈕
        for ticket_type in TicketConstants.DEFAULT_TICKET_TYPES:
            button = TicketTypeButton(
                label=ticket_type['name'],
                emoji=ticket_type['emoji'],
                custom_id=f"create_{ticket_type['name']}"
            )
            self.add_item(button)


class TicketTypeButton(discord.ui.Button):
    """票券類型按鈕"""
    
    def __init__(self, label: str, emoji: str, custom_id: str):
        super().__init__(
            label=label, 
            emoji=emoji, 
            style=discord.ButtonStyle.primary,
            custom_id=custom_id
        )
        self.ticket_type = label
    
    async def callback(self, interaction: discord.Interaction):
        """按鈕回調"""
        try:
            # 顯示優先級選擇
            view = PrioritySelectView(self.ticket_type)
            
            embed = discord.Embed(
                title=f"🎫 建立 {self.ticket_type} 票券",
                description="請選擇問題的優先級：",
                color=TicketConstants.COLORS['primary']
            )
            
            await interaction.response.send_message(
                embed=embed, 
                view=view, 
                ephemeral=True
            )
            
        except Exception as e:
            logger.error(f"票券類型按鈕錯誤：{e}")
            await interaction.response.send_message(
                "❌ 發生錯誤，請稍後再試。", 
                ephemeral=True
            )


class PrioritySelectView(discord.ui.View):
    """優先級選擇視圖"""
    
    def __init__(self, ticket_type: str):
        super().__init__(timeout=300)
        self.ticket_type = ticket_type
        
        # 添加優先級選擇器
        select = PrioritySelect(ticket_type)
        self.add_item(select)


class PrioritySelect(discord.ui.Select):
    """優先級選擇下拉選單"""
    
    def __init__(self, ticket_type: str):
        self.ticket_type = ticket_type
        
        options = [
            discord.SelectOption(
                label="🔴 高優先級",
                value="high",
                description="緊急問題，需要立即處理",
                emoji="🔴"
            ),
            discord.SelectOption(
                label="🟡 中優先級", 
                value="medium",
                description="一般問題，正常處理時間",
                emoji="🟡"
            ),
            discord.SelectOption(
                label="🟢 低優先級",
                value="low", 
                description="非緊急問題，可稍後處理",
                emoji="🟢"
            )
        ]
        
        super().__init__(
            placeholder="選擇優先級...",
            options=options
        )
    
    async def callback(self, interaction: discord.Interaction):
        """選擇回調"""
        try:
            priority = self.values[0]
            
            # 呼叫票券管理器建立票券
            from bot.services.ticket_manager import TicketManager
            from bot.db.ticket_repository import TicketRepository
            
            repository = TicketRepository()
            manager = TicketManager(repository)
            
            # 建立票券
            success, message, ticket_id = await manager.create_ticket(
                user=interaction.user,
                ticket_type=self.ticket_type,
                priority=priority
            )
            
            if success:
                await interaction.response.edit_message(
                    content=f"✅ {message}",
                    embed=None,
                    view=None
                )
            else:
                await interaction.response.send_message(
                    f"❌ {message}",
                    ephemeral=True
                )
                
        except Exception as e:
            logger.error(f"建立票券錯誤：{e}")
            await interaction.response.send_message(
                "❌ 建立票券失敗，請稍後再試。",
                ephemeral=True
            )


class TicketControlView(discord.ui.View):
    """票券控制面板"""
    
    def __init__(self, ticket_id: int):
        super().__init__(timeout=None)
        self.ticket_id = ticket_id
    
    @discord.ui.button(
        label="關閉票券",
        emoji="🔒", 
        style=discord.ButtonStyle.danger,
        custom_id="close_ticket"
    )
    async def close_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        """關閉票券按鈕"""
        try:
            # 檢查權限和顯示確認對話框
            view = ConfirmCloseView(self.ticket_id)
            
            embed = discord.Embed(
                title="🛑 確認關閉票券",
                description=f"確定要關閉票券 #{self.ticket_id:04d} 嗎？",
                color=discord.Color.red()
            )
            
            await interaction.response.send_message(
                embed=embed,
                view=view,
                ephemeral=True
            )
            
        except Exception as e:
            logger.error(f"關閉票券按鈕錯誤：{e}")
            await interaction.response.send_message(
                "❌ 操作失敗，請稍後再試。",
                ephemeral=True
            )
    
    @discord.ui.button(
        label="票券資訊",
        emoji="ℹ️",
        style=discord.ButtonStyle.secondary,
        custom_id="ticket_info"
    )
    async def ticket_info(self, interaction: discord.Interaction, button: discord.ui.Button):
        """票券資訊按鈕"""
        try:
            from bot.db.ticket_repository import TicketRepository
            
            repository = TicketRepository()
            ticket = await repository.get_ticket_by_id(self.ticket_id)
            
            if not ticket:
                await interaction.response.send_message(
                    "❌ 找不到票券資訊。",
                    ephemeral=True
                )
                return
            
            # 建立資訊嵌入
            embed = self._build_ticket_info_embed(ticket)
            await interaction.response.send_message(
                embed=embed,
                ephemeral=True
            )
            
        except Exception as e:
            logger.error(f"票券資訊錯誤：{e}")
            await interaction.response.send_message(
                "❌ 查詢失敗，請稍後再試。",
                ephemeral=True
            )
    
    def _build_ticket_info_embed(self, ticket: Dict[str, Any]) -> discord.Embed:
        """建立票券資訊嵌入"""
        priority_emoji = TicketConstants.PRIORITY_EMOJIS.get(ticket.get('priority', 'medium'), '🟡')
        status_emoji = TicketConstants.STATUS_EMOJIS.get(ticket['status'], '🟢')
        color = TicketConstants.PRIORITY_COLORS.get(ticket.get('priority', 'medium'), 0x00ff00)
        
        embed = discord.Embed(
            title=f"🎫 票券 #{ticket['id']:04d}",
            color=color
        )
        
        # 基本資訊
        embed.add_field(
            name="📋 基本資訊",
            value=f"**類型：** {ticket['type']}\n"
                  f"**狀態：** {status_emoji} {ticket['status'].upper()}\n"
                  f"**優先級：** {priority_emoji} {ticket.get('priority', 'medium').upper()}",
            inline=True
        )
        
        # 用戶資訊
        embed.add_field(
            name="👤 用戶資訊",
            value=f"**開票者：** <@{ticket['discord_id']}>\n"
                  f"**用戶名：** {ticket['username']}",
            inline=True
        )
        
        # 時間資訊
        created_time = get_time_ago(ticket['created_at'])
        time_info = f"**建立時間：** {created_time}"
        
        if ticket.get('closed_at'):
            closed_time = get_time_ago(ticket['closed_at'])
            duration = ticket['closed_at'] - ticket['created_at']
            time_info += f"\n**關閉時間：** {closed_time}"
            time_info += f"\n**持續時間：** {format_duration(duration)}"
        
        embed.add_field(name="⏰ 時間資訊", value=time_info, inline=False)
        
        # 指派資訊
        if ticket.get('assigned_to'):
            embed.add_field(
                name="👥 指派資訊",
                value=f"**負責客服：** <@{ticket['assigned_to']}>",
                inline=True
            )
        
        # 評分資訊
        if ticket.get('rating'):
            stars = TicketConstants.RATING_EMOJIS.get(ticket['rating'], "⭐")
            rating_text = f"**評分：** {stars} ({ticket['rating']}/5)"
            
            if ticket.get('rating_feedback'):
                feedback = ticket['rating_feedback'][:100] + "..." if len(ticket['rating_feedback']) > 100 else ticket['rating_feedback']
                rating_text += f"\n**回饋：** {feedback}"
            
            embed.add_field(name="⭐ 評分", value=rating_text, inline=True)
        
        return embed


class ConfirmCloseView(discord.ui.View):
    """關閉確認對話框"""
    
    def __init__(self, ticket_id: int):
        super().__init__(timeout=60)
        self.ticket_id = ticket_id
    
    @discord.ui.button(
        label="確認關閉",
        emoji="✅",
        style=discord.ButtonStyle.danger
    )
    async def confirm_close(self, interaction: discord.Interaction, button: discord.ui.Button):
        """確認關閉"""
        try:
            from bot.services.ticket_manager import TicketManager
            from bot.db.ticket_repository import TicketRepository
            
            repository = TicketRepository()
            manager = TicketManager(repository)
            
            # 關閉票券
            success = await manager.close_ticket(
                ticket_id=self.ticket_id,
                closed_by=interaction.user.id,
                reason="用戶手動關閉"
            )
            
            if success:
                # 檢查是否需要評分
                ticket = await repository.get_ticket_by_id(self.ticket_id)
                
                if (ticket and 
                    str(interaction.user.id) == ticket['discord_id'] and 
                    not ticket.get('rating')):
                    
                    # 顯示評分界面
                    rating_view = RatingView(self.ticket_id)
                    embed = discord.Embed(
                        title="⭐ 服務評分",
                        description="請為此次客服體驗評分：",
                        color=TicketConstants.COLORS['warning']
                    )
                    
                    await interaction.response.edit_message(
                        embed=embed,
                        view=rating_view
                    )
                else:
                    await interaction.response.edit_message(
                        content="✅ 票券已關閉。",
                        embed=None,
                        view=None
                    )
                
                # 延遲刪除頻道
                await asyncio.sleep(30)
                try:
                    await interaction.channel.delete(reason="票券已關閉")
                except:
                    pass
            else:
                await interaction.response.send_message(
                    "❌ 關閉票券失敗。",
                    ephemeral=True
                )
                
        except Exception as e:
            logger.error(f"確認關閉錯誤：{e}")
            await interaction.response.send_message(
                "❌ 操作失敗，請稍後再試。",
                ephemeral=True
            )
    
    @discord.ui.button(
        label="取消",
        emoji="❌",
        style=discord.ButtonStyle.secondary
    )
    async def cancel_close(self, interaction: discord.Interaction, button: discord.ui.Button):
        """取消關閉"""
        await interaction.response.edit_message(
            content="❌ 已取消關閉操作。",
            embed=None,
            view=None
        )


class RatingView(discord.ui.View):
    """評分系統界面"""
    
    def __init__(self, ticket_id: int):
        super().__init__(timeout=300)
        self.ticket_id = ticket_id
        
        # 添加評分選擇器
        select = RatingSelect(ticket_id)
        self.add_item(select)
    
    @discord.ui.button(
        label="稍後評分",
        emoji="⏭️",
        style=discord.ButtonStyle.secondary
    )
    async def skip_rating(self, interaction: discord.Interaction, button: discord.ui.Button):
        """跳過評分"""
        await interaction.response.edit_message(
            content="感謝使用我們的客服系統！",
            embed=None,
            view=None
        )


class RatingSelect(discord.ui.Select):
    """評分選擇下拉選單"""
    
    def __init__(self, ticket_id: int):
        self.ticket_id = ticket_id
        
        options = [
            discord.SelectOption(label="⭐ 1星 - 非常不滿意", value="1", emoji="⭐"),
            discord.SelectOption(label="⭐⭐ 2星 - 不滿意", value="2", emoji="⭐"),
            discord.SelectOption(label="⭐⭐⭐ 3星 - 普通", value="3", emoji="⭐"),
            discord.SelectOption(label="⭐⭐⭐⭐ 4星 - 滿意", value="4", emoji="⭐"),
            discord.SelectOption(label="⭐⭐⭐⭐⭐ 5星 - 非常滿意", value="5", emoji="⭐")
        ]
        
        super().__init__(
            placeholder="選擇評分...",
            options=options
        )
    
    async def callback(self, interaction: discord.Interaction):
        """評分回調"""
        try:
            rating = int(self.values[0])
            
            # 顯示回饋輸入視窗
            modal = FeedbackModal(self.ticket_id, rating)
            await interaction.response.send_modal(modal)
            
        except Exception as e:
            logger.error(f"評分選擇錯誤：{e}")
            await interaction.response.send_message(
                "❌ 評分失敗，請稍後再試。",
                ephemeral=True
            )


class FeedbackModal(discord.ui.Modal):
    """回饋輸入視窗"""
    
    def __init__(self, ticket_id: int, rating: int):
        super().__init__(title="意見回饋", timeout=300)
        self.ticket_id = ticket_id
        self.rating = rating
        
        # 添加回饋文字輸入
        self.feedback_input = discord.ui.TextInput(
            label="意見回饋（可選）",
            placeholder="請分享您對此次服務的看法...",
            style=discord.TextStyle.paragraph,
            required=False,
            max_length=500
        )
        self.add_item(self.feedback_input)
    
    async def on_submit(self, interaction: discord.Interaction):
        """提交回饋"""
        try:
            feedback = self.feedback_input.value.strip() if self.feedback_input.value else None
            
            # 保存評分
            from bot.services.ticket_manager import TicketManager
            from bot.db.ticket_repository import TicketRepository
            
            repository = TicketRepository()
            manager = TicketManager(repository)
            
            success = await manager.save_rating(self.ticket_id, self.rating, feedback)
            
            if success:
                stars = TicketConstants.RATING_EMOJIS.get(self.rating, "⭐")
                
                embed = discord.Embed(
                    title="⭐ 評分已保存",
                    description=f"感謝您為票券 #{self.ticket_id:04d} 評分！",
                    color=TicketConstants.RATING_COLORS.get(self.rating, 0xf1c40f)
                )
                
                embed.add_field(
                    name="評分",
                    value=f"{stars} ({self.rating}/5)",
                    inline=True
                )
                
                if feedback:
                    embed.add_field(
                        name="意見回饋",
                        value=feedback,
                        inline=False
                    )
                
                await interaction.response.edit_message(
                    embed=embed,
                    view=None
                )
            else:
                await interaction.response.send_message(
                    "❌ 保存評分失敗，請稍後再試。",
                    ephemeral=True
                )
                
        except Exception as e:
            logger.error(f"提交回饋錯誤：{e}")
            await interaction.response.send_message(
                "❌ 提交失敗，請稍後再試。",
                ephemeral=True
            )


class TicketListView(discord.ui.View):
    """票券列表視圖"""
    
    def __init__(self, tickets: List[Dict], page: int, total_pages: int, **kwargs):
        super().__init__(timeout=300)
        self.tickets = tickets
        self.page = page
        self.total_pages = total_pages
        self.kwargs = kwargs
        
        # 添加分頁按鈕
        if page > 1:
            self.add_item(PreviousPageButton())
        
        if page < total_pages:
            self.add_item(NextPageButton())
        
        # 添加刷新按鈕
        self.add_item(RefreshButton())
    
    def build_embed(self) -> discord.Embed:
        """建立列表嵌入"""
        embed = discord.Embed(
            title="🎫 票券列表",
            color=TicketConstants.COLORS['info']
        )
        
        if not self.tickets:
            embed.description = "📭 沒有找到票券。"
            return embed
        
        for ticket in self.tickets:
            status_emoji = TicketConstants.STATUS_EMOJIS.get(ticket['status'], '🟢')
            priority_emoji = TicketConstants.PRIORITY_EMOJIS.get(ticket.get('priority', 'medium'), '🟡')
            
            field_value = f"{status_emoji} {ticket['status'].upper()} {priority_emoji}\n"
            field_value += f"👤 <@{ticket['discord_id']}>\n"
            field_value += f"📅 {get_time_ago(ticket['created_at'])}"
            
            if ticket.get('assigned_to'):
                field_value += f"\n👥 <@{ticket['assigned_to']}>"
            
            if ticket.get('rating'):
                stars = TicketConstants.RATING_EMOJIS.get(ticket['rating'], "⭐")
                field_value += f"\n{stars}"
            
            embed.add_field(
                name=f"#{ticket['id']:04d} - {ticket['type']}",
                value=field_value,
                inline=True
            )
        
        embed.set_footer(text=f"頁面 {self.page}/{self.total_pages}")
        return embed


class PreviousPageButton(discord.ui.Button):
    """上一頁按鈕"""
    
    def __init__(self):
        super().__init__(
            label="上一頁",
            emoji="◀️",
            style=discord.ButtonStyle.secondary
        )
    
    async def callback(self, interaction: discord.Interaction):
        """上一頁回調"""
        view: TicketListView = self.view
        new_page = max(1, view.page - 1)
        
        # 重新查詢資料
        await self._update_page(interaction, view, new_page)


class NextPageButton(discord.ui.Button):
    """下一頁按鈕"""
    
    def __init__(self):
        super().__init__(
            label="下一頁",
            emoji="▶️",
            style=discord.ButtonStyle.secondary
        )
    
    async def callback(self, interaction: discord.Interaction):
        """下一頁回調"""
        view: TicketListView = self.view
        new_page = min(view.total_pages, view.page + 1)
        
        # 重新查詢資料
        await self._update_page(interaction, view, new_page)


class RefreshButton(discord.ui.Button):
    """刷新按鈕"""
    
    def __init__(self):
        super().__init__(
            label="刷新",
            emoji="🔄",
            style=discord.ButtonStyle.primary
        )
    
    async def callback(self, interaction: discord.Interaction):
        """刷新回調"""
        view: TicketListView = self.view
        
        # 重新查詢當前頁面
        await self._update_page(interaction, view, view.page)


async def _update_page(interaction: discord.Interaction, view: TicketListView, new_page: int):
    """更新頁面"""
    try:
        from bot.db.ticket_repository import TicketRepository
        
        repository = TicketRepository()
        
        # 重新查詢
        tickets, total = await repository.get_tickets(
            guild_id=interaction.guild.id,
            page=new_page,
            **view.kwargs
        )
        
        # 更新視圖
        view.tickets = tickets
        view.page = new_page
        view.total_pages = (total + 9) // 10  # 每頁10個
        
        # 重建視圖
        view.clear_items()
        if new_page > 1:
            view.add_item(PreviousPageButton())
        if new_page < view.total_pages:
            view.add_item(NextPageButton())
        view.add_item(RefreshButton())
        
        # 更新嵌入
        embed = view.build_embed()
        await interaction.response.edit_message(embed=embed, view=view)
        
    except Exception as e:
        logger.error(f"更新頁面錯誤：{e}")
        await interaction.response.send_message(
            "❌ 更新失敗，請稍後再試。",
            ephemeral=True
        )


# ===== 輔助函數 =====

def create_ticket_panel(settings: Dict[str, Any]) -> TicketPanelView:
    """建立票券面板"""
    return TicketPanelView(settings)


def create_ticket_controls(ticket_id: int) -> TicketControlView:
    """建立票券控制面板"""
    return TicketControlView(ticket_id)


def create_ticket_list(tickets: List[Dict], page: int, total_pages: int, **kwargs) -> TicketListView:
    """建立票券列表"""
    return TicketListView(tickets, page, total_pages, **kwargs)