# bot/views/ticket_views.py - 票券系統 UI 組件

import discord
from discord.ext import commands
from typing import Dict, List, Optional, Any, Callable
from datetime import datetime, timezone
import asyncio

from bot.db.ticket_repository import TicketDAO
from bot.utils.ticket_constants import (
    TicketConstants, get_priority_emoji, get_status_emoji,
    get_priority_color, TicketSelectOptions, Priority, Status,
    ERROR_MESSAGES, SUCCESS_MESSAGES
)
from bot.utils.debug import debug_log


class TicketView(discord.ui.View):
    """主要票券建立面板"""
    
    def __init__(self, settings: Dict[str, Any]):
        super().__init__(timeout=None)
        self.settings = settings
        self.dao = TicketDAO()
        
        # 添加票券類型按鈕
        for ticket_type in TicketConstants.DEFAULT_TICKET_TYPES:
            button = TicketTypeButton(
                label=ticket_type['name'],
                emoji=ticket_type['emoji'],
                style=ticket_type['style'],
                custom_id=f"ticket_create_{ticket_type['name']}"
            )
            self.add_item(button)


class TicketTypeButton(discord.ui.Button):
    """票券類型按鈕"""
    
    def __init__(self, label: str, emoji: str, style: discord.ButtonStyle, custom_id: str):
        super().__init__(label=label, emoji=emoji, style=style, custom_id=custom_id)
        self.ticket_type = label
        self.dao = TicketDAO()
    
    async def callback(self, interaction: discord.Interaction):
        # 檢查票券限制
        settings = await self.dao.get_guild_settings(interaction.guild.id)
        if not settings:
            settings = await self.dao.create_default_settings(interaction.guild.id)
        
        current_tickets = await self.dao.get_user_ticket_count(
            str(interaction.user.id), 
            interaction.guild.id, 
            "open"
        )
        
        max_tickets = settings.get('max_tickets_per_user', 3)
        if current_tickets >= max_tickets:
            await interaction.response.send_message(
                f"❌ 你已達到票券上限（{max_tickets}張）！請先關閉現有票券。",
                ephemeral=True
            )
            return
        
        # 顯示優先級選擇面板
        priority_view = PrioritySelectForCreation(self.ticket_type, settings)
        
        embed = discord.Embed(
            title=f"🎫 建立{self.ticket_type}票券",
            description="請選擇問題優先級：",
            color=discord.Color.blue()
        )
        
        await interaction.response.send_message(embed=embed, view=priority_view, ephemeral=True)


class PrioritySelectForCreation(discord.ui.View):
    """建立票券時的優先級選擇"""
    
    def __init__(self, ticket_type: str, settings: Dict[str, Any]):
        super().__init__(timeout=300)
        self.ticket_type = ticket_type
        self.settings = settings
        self.dao = TicketDAO()
        
        # 添加優先級選擇下拉選單
        select = PrioritySelect(ticket_type, settings)
        self.add_item(select)


class PrioritySelect(discord.ui.Select):
    """優先級選擇下拉選單"""
    
    def __init__(self, ticket_type: str, settings: Dict[str, Any]):
        self.ticket_type = ticket_type
        self.settings = settings
        self.dao = TicketDAO()
        
        options = TicketSelectOptions.get_priority_options()
        super().__init__(placeholder="選擇優先級...", options=options)
    
    async def callback(self, interaction: discord.Interaction):
        priority = self.values[0]
        
        # 建立票券頻道
        success = await self._create_ticket_channel(interaction, priority)
        
        if success:
            await interaction.response.edit_message(
                content="✅ 票券已成功建立！",
                embed=None,
                view=None
            )
        else:
            await interaction.response.send_message(
                "❌ 建立票券失敗，請聯繫管理員。",
                ephemeral=True
            )
    
    async def _create_ticket_channel(self, interaction: discord.Interaction, priority: str) -> bool:
        """建立票券頻道"""
        try:
            # 取得分類頻道
            category_id = self.settings.get('category_id')
            if not category_id:
                await interaction.response.send_message(
                    "❌ 尚未設定票券分類頻道，請聯繫管理員。",
                    ephemeral=True
                )
                return False
            
            category = interaction.guild.get_channel(category_id)
            if not category:
                await interaction.response.send_message(
                    "❌ 票券分類頻道不存在，請聯繫管理員。",
                    ephemeral=True
                )
                return False
            
            # 生成票券代碼
            ticket_code = await self.dao.next_ticket_code()
            
            # 建立頻道權限
            overwrites = {
                interaction.guild.default_role: discord.PermissionOverwrite(read_messages=False),
                interaction.user: discord.PermissionOverwrite(
                    read_messages=True,
                    send_messages=True,
                    attach_files=True,
                    embed_links=True
                ),
                interaction.guild.me: discord.PermissionOverwrite(
                    read_messages=True,
                    send_messages=True,
                    manage_messages=True,
                    embed_links=True
                )
            }
            
            # 添加客服身分組權限
            support_roles = self.settings.get('support_roles', [])
            for role_id in support_roles:
                role = interaction.guild.get_role(role_id)
                if role:
                    overwrites[role] = discord.PermissionOverwrite(
                        read_messages=True,
                        send_messages=True,
                        manage_messages=True,
                        embed_links=True
                    )
            
            # 建立頻道
            channel_name = f"ticket-{ticket_code}"
            channel = await interaction.guild.create_text_channel(
                name=channel_name,
                category=category,
                overwrites=overwrites,
                reason=f"建立票券 - 用戶: {interaction.user}"
            )
            
            # 儲存到資料庫
            ticket_id = await self.dao.create_ticket(
                discord_id=str(interaction.user.id),
                username=interaction.user.display_name,
                ticket_type=self.ticket_type,
                channel_id=channel.id,
                guild_id=interaction.guild.id,
                priority=priority
            )
            
            if not ticket_id:
                await channel.delete(reason="票券建立失敗")
                return False
            
            # 發送歡迎訊息
            await self._send_welcome_message(channel, interaction.user, ticket_id, priority)
            
            return True
            
        except Exception as e:
            debug_log(f"[TicketView] 建立票券頻道錯誤：{e}")
            return False
    
    async def _send_welcome_message(self, channel: discord.TextChannel, user: discord.Member, 
                                  ticket_id: int, priority: str):
        """發送歡迎訊息"""
        priority_emoji = get_priority_emoji(priority)
        priority_color = get_priority_color(priority)
        
        embed = discord.Embed(
            title=f"🎫 票券 #{ticket_id:04d}",
            description=f"你好 {user.mention}！\n\n請詳細描述你的問題，我們的客服團隊會盡快回覆。",
            color=priority_color
        )
        
        embed.add_field(
            name="📋 票券資訊",
            value=f"**類型：** {self.ticket_type}\n"
                  f"**優先級：** {priority_emoji} {priority.upper()}\n"
                  f"**預期回覆：** {self.settings.get('sla_response_minutes', 60)} 分鐘內",
            inline=True
        )
        
        embed.add_field(
            name="⏰ 建立時間",
            value=f"<t:{int(datetime.now(timezone.utc).timestamp())}:F>",
            inline=True
        )
        
        embed.add_field(
            name="💡 使用說明",
            value="• 使用 `/close` 來關閉此票券\n"
                  "• 請保持禮貌和耐心\n"
                  "• 提供詳細資訊有助於快速解決問題\n"
                  "• 關閉後可為服務評分",
            inline=False
        )
        
        embed.set_footer(text="感謝你使用我們的客服系統！")
        
        # 票券控制面板
        control_view = TicketControlView(ticket_id)
        
        await channel.send(embed=embed, view=control_view)


class TicketControlView(discord.ui.View):
    """票券控制面板"""
    
    def __init__(self, ticket_id: int):
        super().__init__(timeout=None)
        self.ticket_id = ticket_id
        self.dao = TicketDAO()
    
    @discord.ui.button(label="關閉票券", emoji="🔒", style=discord.ButtonStyle.danger, custom_id="close_ticket")
    async def close_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        """關閉票券按鈕"""
        # 檢查權限
        ticket_info = await self.dao.get_ticket_by_id(self.ticket_id)
        if not ticket_info:
            await interaction.response.send_message("❌ 找不到票券資訊。", ephemeral=True)
            return
        
        settings = await self.dao.get_guild_settings(interaction.guild.id)
        support_roles = settings.get('support_roles', [])
        
        can_close = (
            str(interaction.user.id) == ticket_info['discord_id'] or
            any(role.id in support_roles for role in interaction.user.roles) or
            interaction.user.guild_permissions.manage_guild
        )
        
        if not can_close:
            await interaction.response.send_message(
                "❌ 只有票券創建者或客服人員可以關閉票券。",
                ephemeral=True
            )
            return
        
        # 顯示關閉確認
        confirm_view = ConfirmCloseView(self.ticket_id, ticket_info)
        
        embed = discord.Embed(
            title="🛑 確認關閉票券",
            description=f"確定要關閉票券 #{self.ticket_id:04d}？",
            color=discord.Color.red()
        )
        
        await interaction.response.send_message(embed=embed, view=confirm_view, ephemeral=True)
    
    @discord.ui.button(label="票券資訊", emoji="ℹ️", style=discord.ButtonStyle.secondary, custom_id="ticket_info")
    async def ticket_info(self, interaction: discord.Interaction, button: discord.ui.Button):
        """票券資訊按鈕"""
        ticket_info = await self.dao.get_ticket_by_id(self.ticket_id)
        if not ticket_info:
            await interaction.response.send_message("❌ 找不到票券資訊。", ephemeral=True)
            return
        
        # 建立詳細資訊
        embed = await self._build_ticket_info_embed(ticket_info, interaction.guild)
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    async def _build_ticket_info_embed(self, ticket_info: Dict, guild: discord.Guild) -> discord.Embed:
        """建立票券資訊嵌入"""
        priority_emoji = get_priority_emoji(ticket_info.get('priority', 'medium'))
        status_emoji = get_status_emoji(ticket_info['status'])
        
        embed = discord.Embed(
            title=f"🎫 票券 #{ticket_info['ticket_id']:04d}",
            color=get_priority_color(ticket_info.get('priority', 'medium'))
        )
        
        embed.add_field(
            name="📋 基本資訊",
            value=f"**類型：** {ticket_info['type']}\n"
                  f"**狀態：** {status_emoji} {ticket_info['status'].upper()}\n"
                  f"**優先級：** {priority_emoji} {ticket_info.get('priority', 'medium').upper()}",
            inline=True
        )
        
        embed.add_field(
            name="👤 用戶資訊",
            value=f"**開票者：** <@{ticket_info['discord_id']}>\n"
                  f"**用戶名：** {ticket_info['username']}",
            inline=True
        )
        
        # 時間資訊
        created_timestamp = int(ticket_info['created_at'].timestamp())
        time_value = f"**建立：** <t:{created_timestamp}:F>\n"
        time_value += f"**建立：** <t:{created_timestamp}:R>"
        
        if ticket_info.get('closed_at'):
            closed_timestamp = int(ticket_info['closed_at'].timestamp())
            time_value += f"\n**關閉：** <t:{closed_timestamp}:F>"
            time_value += f"\n**關閉：** <t:{closed_timestamp}:R>"
        
        embed.add_field(name="⏰ 時間資訊", value=time_value, inline=False)
        
        # 指派資訊
        if ticket_info.get('assigned_to'):
            embed.add_field(
                name="👥 指派資訊",
                value=f"**客服：** <@{ticket_info['assigned_to']}>",
                inline=True
            )
        
        # 評分資訊
        if ticket_info.get('rating'):
            stars = TicketConstants.RATING_EMOJIS.get(ticket_info['rating'], "⭐")
            rating_value = f"**評分：** {stars} ({ticket_info['rating']}/5)"
            if ticket_info.get('rating_feedback'):
                rating_value += f"\n**回饋：** {ticket_info['rating_feedback']}"
            
            embed.add_field(name="⭐ 評分資訊", value=rating_value, inline=False)
        
        return embed


class ConfirmCloseView(discord.ui.View):
    """關閉確認對話框"""
    
    def __init__(self, ticket_id: int, ticket_info: Dict):
        super().__init__(timeout=60)
        self.ticket_id = ticket_id
        self.ticket_info = ticket_info
        self.dao = TicketDAO()
    
    @discord.ui.button(label="確認關閉", emoji="✅", style=discord.ButtonStyle.danger)
    async def confirm_close(self, interaction: discord.Interaction, button: discord.ui.Button):
        """確認關閉"""
        success = await self.dao.close_ticket(
            interaction.channel.id,
            str(interaction.user.id),
            "用戶手動關閉"
        )
        
        if success:
            # 檢查是否要求評分
            if self.ticket_info['status'] == 'open' and str(interaction.user.id) == self.ticket_info['discord_id']:
                rating_view = RatingView(self.ticket_id)
                
                embed = discord.Embed(
                    title="⭐ 服務評分",
                    description="請為此次客服體驗評分，你的回饋對我們很重要！",
                    color=discord.Color.gold()
                )
                
                await interaction.response.edit_message(
                    content=None,
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
            await interaction.response.send_message("❌ 關閉票券失敗。", ephemeral=True)
    
    @discord.ui.button(label="取消", emoji="❌", style=discord.ButtonStyle.secondary)
    async def cancel_close(self, interaction: discord.Interaction, button: discord.ui.Button):
        """取消關閉"""
        await interaction.response.edit_message(
            content="❌ 已取消關閉操作。",
            embed=None,
            view=None
        )


class RatingView(discord.ui.View):
    """評分系統介面"""
    
    def __init__(self, ticket_id: int):
        super().__init__(timeout=300)
        self.ticket_id = ticket_id
        self.dao = TicketDAO()
        
        # 添加評分選擇下拉選單
        select = RatingSelect(ticket_id)
        self.add_item(select)
    
    @discord.ui.button(label="稍後評分", emoji="⏭️", style=discord.ButtonStyle.secondary)
    async def skip_rating(self, interaction: discord.Interaction, button: discord.ui.Button):
        """跳過評分"""
        await interaction.response.edit_message(
            content="感謝你使用我們的客服系統！",
            embed=None,
            view=None
        )


class RatingSelect(discord.ui.Select):
    """評分選擇下拉選單"""
    
    def __init__(self, ticket_id: int):
        self.ticket_id = ticket_id
        self.dao = TicketDAO()
        
        options = TicketSelectOptions.get_rating_options()
        super().__init__(placeholder="選擇評分...", options=options)
    
    async def callback(self, interaction: discord.Interaction):
        rating = int(self.values[0])
        
        # 顯示回饋輸入視窗
        feedback_modal = FeedbackModal(self.ticket_id, rating)
        await interaction.response.send_modal(feedback_modal)


class FeedbackModal(discord.ui.Modal):
    """回饋輸入視窗"""
    
    def __init__(self, ticket_id: int, rating: int):
        super().__init__(title="意見回饋", timeout=300)
        self.ticket_id = ticket_id
        self.rating = rating
        self.dao = TicketDAO()
        
        # 添加回饋文字輸入
        self.feedback_input = discord.ui.TextInput(
            label="意見回饋（可選）",
            placeholder="請分享你對此次服務的看法...",
            style=discord.TextStyle.paragraph,
            required=False,
            max_length=1000
        )
        self.add_item(self.feedback_input)
    
    async def on_submit(self, interaction: discord.Interaction):
        feedback = self.feedback_input.value.strip() if self.feedback_input.value else None
        
        # 保存評分
        success = await self.dao.save_ticket_rating(self.ticket_id, self.rating, feedback)
        
        if success:
            stars = TicketConstants.RATING_EMOJIS.get(self.rating, "⭐")
            
            embed = discord.Embed(
                title="⭐ 評分已保存",
                description=f"感謝你為票券 #{self.ticket_id:04d} 評分！",
                color=discord.Color.gold()
            )
            embed.add_field(name="評分", value=f"{stars} ({self.rating}/5)", inline=True)
            
            if feedback:
                embed.add_field(name="意見回饋", value=feedback, inline=False)
            
            await interaction.response.edit_message(
                content=None,
                embed=embed,
                view=None
            )
        else:
            await interaction.response.send_message(
                "❌ 保存評分失敗，請稍後再試。",
                ephemeral=True
            )


class TicketPaginationView(discord.ui.View):
    """票券分頁瀏覽"""
    
    def __init__(self, tickets: List[Dict], total: int, page: int, page_size: int, 
                 query_params: Dict[str, Any], user_id: str = None):
        super().__init__(timeout=300)
        self.tickets = tickets
        self.total = total
        self.page = page
        self.page_size = page_size
        self.query_params = query_params
        self.user_id = user_id
        self.dao = TicketDAO()
        
        # 計算分頁資訊
        self.total_pages = (total + page_size - 1) // page_size
        
        # 更新按鈕狀態
        self._update_buttons()
    
    def _update_buttons(self):
        """更新分頁按鈕狀態"""
        # 清除現有按鈕
        self.clear_items()
        
        # 第一頁按鈕
        first_button = discord.ui.Button(
            label="⏮️",
            style=discord.ButtonStyle.secondary,
            disabled=(self.page <= 1)
        )
        first_button.callback = self._first_page
        self.add_item(first_button)
        
        # 上一頁按鈕
        prev_button = discord.ui.Button(
            label="◀️",
            style=discord.ButtonStyle.secondary,
            disabled=(self.page <= 1)
        )
        prev_button.callback = self._previous_page
        self.add_item(prev_button)
        
        # 頁數顯示
        page_button = discord.ui.Button(
            label=f"{self.page}/{self.total_pages}",
            style=discord.ButtonStyle.primary,
            disabled=True
        )
        self.add_item(page_button)
        
        # 下一頁按鈕
        next_button = discord.ui.Button(
            label="▶️",
            style=discord.ButtonStyle.secondary,
            disabled=(self.page >= self.total_pages)
        )
        next_button.callback = self._next_page
        self.add_item(next_button)
        
        # 最後一頁按鈕
        last_button = discord.ui.Button(
            label="⏭️",
            style=discord.ButtonStyle.secondary,
            disabled=(self.page >= self.total_pages)
        )
        last_button.callback = self._last_page
        self.add_item(last_button)
    
    async def _first_page(self, interaction: discord.Interaction):
        """第一頁"""
        await self._go_to_page(interaction, 1)
    
    async def _previous_page(self, interaction: discord.Interaction):
        """上一頁"""
        await self._go_to_page(interaction, max(1, self.page - 1))
    
    async def _next_page(self, interaction: discord.Interaction):
        """下一頁"""
        await self._go_to_page(interaction, min(self.total_pages, self.page + 1))
    
    async def _last_page(self, interaction: discord.Interaction):
        """最後一頁"""
        await self._go_to_page(interaction, self.total_pages)
    
    async def _go_to_page(self, interaction: discord.Interaction, new_page: int):
        """跳轉到指定頁面"""
        if new_page == self.page:
            await interaction.response.defer()
            return
        
        # 重新查詢資料
        tickets, total = await self.dao.paginate_tickets(
            user_id=self.user_id,
            status=self.query_params.get('status', 'all'),
            page=new_page,
            page_size=self.page_size,
            guild_id=self.query_params.get('guild_id'),
            priority=self.query_params.get('priority')
        )
        
        # 更新分頁資訊
        self.tickets = tickets
        self.total = total
        self.page = new_page
        self.total_pages = (total + self.page_size - 1) // self.page_size
        
        # 更新按鈕
        self._update_buttons()
        
        # 建立新的嵌入
        embed = self._build_tickets_embed()
        
        await interaction.response.edit_message(embed=embed, view=self)
    
    def _build_tickets_embed(self) -> discord.Embed:
        """建立票券列表嵌入"""
        embed = discord.Embed(
            title="🎫 票券列表",
            color=discord.Color.blue()
        )
        
        if not self.tickets:
            embed.description = "📭 沒有找到符合條件的票券。"
            return embed
        
        # 篩選條件顯示
        filters = []
        if self.query_params.get('status', 'all') != 'all':
            filters.append(f"狀態: {self.query_params['status']}")
        if self.query_params.get('priority'):
            filters.append(f"優先級: {self.query_params['priority']}")
        
        if filters:
            embed.description = f"篩選條件：{' | '.join(filters)}"
        
        # 顯示票券
        for ticket in self.tickets:
            status_emoji = get_status_emoji(ticket['status'])
            priority_emoji = get_priority_emoji(ticket.get('priority', 'medium'))
            
            field_value = f"{status_emoji} {ticket['status'].upper()} {priority_emoji}\n"
            field_value += f"👤 <@{ticket['discord_id']}>\n"
            field_value += f"📅 <t:{int(ticket['created_at'].timestamp())}:R>"
            
            if ticket.get('assigned_to'):
                field_value += f"\n👥 <@{ticket['assigned_to']}>"
            
            if ticket.get('rating'):
                stars = TicketConstants.RATING_EMOJIS.get(ticket['rating'], "⭐")
                field_value += f"\n{stars}"
            
            embed.add_field(
                name=f"#{ticket['ticket_id']:04d} - {ticket['type']}",
                value=field_value,
                inline=True
            )
        
        embed.set_footer(text=f"頁面 {self.page}/{self.total_pages} | 共 {self.total} 筆記錄")
        return embed


class AdminPanelView(discord.ui.View):
    """管理員控制面板"""
    
    def __init__(self, guild_id: int, stats: Dict[str, Any]):
        super().__init__(timeout=300)
        self.guild_id = guild_id
        self.stats = stats
        self.dao = TicketDAO()
    
    @discord.ui.button(label="系統設定", emoji="⚙️", style=discord.ButtonStyle.primary)
    async def system_settings(self, interaction: discord.Interaction, button: discord.ui.Button):
        """系統設定按鈕"""
        settings = await self.dao.get_guild_settings(self.guild_id)
        
        embed = discord.Embed(
            title="⚙️ 系統設定",
            color=discord.Color.blue()
        )
        
        # 基本設定
        category_mention = f"<#{settings['category_id']}>" if settings.get('category_id') else "未設定"
        
        embed.add_field(
            name="🎫 基本設定",
            value=f"**分類頻道：** {category_mention}\n"
                  f"**每人限制：** {settings.get('max_tickets_per_user', 3)} 張\n"
                  f"**自動關閉：** {settings.get('auto_close_hours', 24)} 小時",
            inline=False
        )
        
        # SLA 設定
        embed.add_field(
            name="⏰ SLA 設定",
            value=f"**回應時間：** {settings.get('sla_response_minutes', 60)} 分鐘\n"
                  f"**自動分配：** {'啟用' if settings.get('auto_assign_enabled') else '停用'}",
            inline=True
        )
        
        # 客服設定
        support_roles = settings.get('support_roles', [])
        if support_roles:
            role_mentions = [f"<@&{role_id}>" for role_id in support_roles]
            support_text = ", ".join(role_mentions)
        else:
            support_text = "未設定"
        
        embed.add_field(
            name="👥 客服設定",
            value=f"**客服身分組：** {support_text}",
            inline=True
        )
        
        # 操作提示
        embed.add_field(
            name="💡 快速操作",
            value="使用 `/ticket_setting` 指令來修改這些設定",
            inline=False
        )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    @discord.ui.button(label="SLA 監控", emoji="📊", style=discord.ButtonStyle.success)
    async def sla_monitoring(self, interaction: discord.Interaction, button: discord.ui.Button):
        """SLA 監控按鈕"""
        sla_view = SLADashboardView(self.guild_id)
        await sla_view.show_dashboard(interaction)
    
    @discord.ui.button(label="客服統計", emoji="👥", style=discord.ButtonStyle.secondary)
    async def staff_statistics(self, interaction: discord.Interaction, button: discord.ui.Button):
        """客服統計按鈕"""
        stats = await self.dao.get_staff_workload_stats(self.guild_id, "week")
        
        embed = discord.Embed(
            title="👥 客服團隊統計 - 本週",
            color=discord.Color.blue()
        )
        
        if not stats:
            embed.description = "📊 本週尚無客服活動記錄。"
        else:
            # 排序客服人員
            sorted_staff = sorted(stats.items(), key=lambda x: x[1].get('handled_tickets', 0), reverse=True)
            
            for staff_id, staff_stats in sorted_staff[:10]:  # 限制顯示10位
                try:
                    member = interaction.guild.get_member(int(staff_id))
                    if not member:
                        continue
                    
                    embed.add_field(
                        name=f"👤 {member.display_name}",
                        value=f"處理：{staff_stats.get('handled_tickets', 0)} 張\n"
                              f"評分：{staff_stats.get('avg_rating', 0):.1f}⭐\n"
                              f"SLA：{staff_stats.get('sla_rate', 0):.1f}%",
                        inline=True
                    )
                except:
                    continue
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    @discord.ui.button(label="批次操作", emoji="🔧", style=discord.ButtonStyle.danger)
    async def batch_operations(self, interaction: discord.Interaction, button: discord.ui.Button):
        """批次操作按鈕"""
        batch_view = BatchOperationView(self.guild_id)
        
        embed = discord.Embed(
            title="🔧 批次操作",
            description="請選擇要執行的批次操作：",
            color=discord.Color.orange()
        )
        
        embed.add_field(
            name="⚠️ 注意事項",
            value="• 批次操作無法撤銷\n• 建議在維護時間執行\n• 大量操作可能需要較長時間",
            inline=False
        )
        
        await interaction.response.send_message(embed=embed, view=batch_view, ephemeral=True)


class SLADashboardView(discord.ui.View):
    """SLA 監控面板"""
    
    def __init__(self, guild_id: int):
        super().__init__(timeout=300)
        self.guild_id = guild_id
        self.dao = TicketDAO()
    
    async def show_dashboard(self, interaction: discord.Interaction):
        """顯示 SLA 監控面板"""
        stats = await self.dao.get_sla_statistics(self.guild_id)
        
        embed = discord.Embed(
            title="📈 SLA 監控面板",
            color=discord.Color.blue()
        )
        
        # 總體統計
        total_tickets = stats.get('total_tickets', 0)
        responded_tickets = stats.get('responded_tickets', 0)
        sla_rate = stats.get('sla_rate', 0)
        
        embed.add_field(
            name="📊 本週統計",
            value=f"**總票券：** {total_tickets}\n"
                  f"**已回應：** {responded_tickets}\n"
                  f"**達標：** {stats.get('met_sla', 0)} ({sla_rate:.1f}%)\n"
                  f"**超時：** {stats.get('missed_sla', 0)}\n"
                  f"**平均回應：** {stats.get('avg_response_time', 0):.1f} 分鐘",
            inline=True
        )
        
        # 當前超時
        embed.add_field(
            name="⚠️ 當前超時",
            value=f"🔴 **高優先級：** {stats.get('overdue_high', 0)}\n"
                  f"🟡 **中優先級：** {stats.get('overdue_medium', 0)}\n"
                  f"🟢 **低優先級：** {stats.get('overdue_low', 0)}",
            inline=True
        )
        
        # SLA 達標率圖示
        sla_indicator = self._create_sla_indicator(sla_rate)
        embed.add_field(
            name="📈 SLA 達標率",
            value=f"```{sla_indicator}```\n**{sla_rate:.1f}%**",
            inline=False
        )
        
        embed.set_footer(text=f"最後更新：{datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')} UTC")
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    def _create_sla_indicator(self, sla_rate: float) -> str:
        """建立 SLA 達標率指示器"""
        filled = int(sla_rate / 10)  # 每10%一格
        empty = 10 - filled
        
        indicator = "█" * filled + "░" * empty
        return f"[{indicator}] {sla_rate:.1f}%"


class BatchOperationView(discord.ui.View):
    """批次操作面板"""
    
    def __init__(self, guild_id: int):
        super().__init__(timeout=300)
        self.guild_id = guild_id
        self.dao = TicketDAO()
    
    @discord.ui.button(label="關閉無活動票券", emoji="💤", style=discord.ButtonStyle.danger)
    async def close_inactive_tickets(self, interaction: discord.Interaction, button: discord.ui.Button):
        """關閉無活動票券"""
        modal = InactiveThresholdModal(self.guild_id)
        await interaction.response.send_modal(modal)
    
    @discord.ui.button(label="匯出票券資料", emoji="📄", style=discord.ButtonStyle.secondary)
    async def export_tickets(self, interaction: discord.Interaction, button: discord.ui.Button):
        """匯出票券資料"""
        await interaction.response.defer(ephemeral=True)
        
        try:
            # 匯出最近30天的資料
            start_date = datetime.now(timezone.utc) - timedelta(days=30)
            tickets_data = await self.dao.export_tickets_data(
                self.guild_id,
                start_date=start_date
            )
            
            if not tickets_data:
                await interaction.followup.send("📭 沒有可匯出的票券資料。")
                return
            
            # 建立 CSV 內容
            csv_content = "票券ID,用戶ID,用戶名,類型,優先級,狀態,建立時間,關閉時間,評分\n"
            
            for ticket in tickets_data:
                csv_content += f"{ticket['ticket_id']},{ticket['discord_id']},{ticket['username']},"
                csv_content += f"{ticket['type']},{ticket.get('priority', 'medium')},{ticket['status']},"
                csv_content += f"{ticket['created_at']},{ticket.get('closed_at', '')},"
                csv_content += f"{ticket.get('rating', '')}\n"
            
            # 建立檔案
            import io
            file_buffer = io.StringIO(csv_content)
            file = discord.File(
                io.BytesIO(file_buffer.getvalue().encode('utf-8-sig')),
                filename=f"tickets_{self.guild_id}_{datetime.now().strftime('%Y%m%d')}.csv"
            )
            
            embed = discord.Embed(
                title="📄 票券資料匯出",
                description=f"✅ 成功匯出 {len(tickets_data)} 筆票券記錄",
                color=discord.Color.green()
            )
            
            await interaction.followup.send(embed=embed, file=file)
            
        except Exception as e:
            debug_log(f"[BatchOperation] 匯出資料錯誤：{e}")
            await interaction.followup.send("❌ 匯出資料時發生錯誤。")
    
    @discord.ui.button(label="清理舊資料", emoji="🧹", style=discord.ButtonStyle.secondary)
    async def cleanup_old_data(self, interaction: discord.Interaction, button: discord.ui.Button):
        """清理舊資料"""
        await interaction.response.defer(ephemeral=True)
        
        try:
            cleaned_count = await self.dao.cleanup_old_data(90)  # 清理90天前的資料
            
            embed = discord.Embed(
                title="🧹 資料清理完成",
                description=f"✅ 清理了 {cleaned_count} 條舊資料記錄",
                color=discord.Color.green()
            )
            
            await interaction.followup.send(embed=embed)
            
        except Exception as e:
            debug_log(f"[BatchOperation] 清理資料錯誤：{e}")
            await interaction.followup.send("❌ 清理資料時發生錯誤。")


class InactiveThresholdModal(discord.ui.Modal):
    """無活動時間閾值輸入視窗"""
    
    def __init__(self, guild_id: int):
        super().__init__(title="關閉無活動票券", timeout=300)
        self.guild_id = guild_id
        self.dao = TicketDAO()
        
        self.hours_input = discord.ui.TextInput(
            label="無活動時間（小時）",
            placeholder="例如：48 (表示48小時無活動)",
            default="48",
            min_length=1,
            max_length=3
        )
        self.add_item(self.hours_input)
    
    async def on_submit(self, interaction: discord.Interaction):
        try:
            hours = int(self.hours_input.value)
            if hours < 1 or hours > 168:  # 1小時到1週
                await interaction.response.send_message(
                    "❌ 時間必須在 1-168 小時之間。",
                    ephemeral=True
                )
                return
            
            await interaction.response.defer(ephemeral=True)
            
            # 執行批次關閉
            closed_count = await self.dao.close_inactive_tickets(self.guild_id, hours)
            
            embed = discord.Embed(
                title="💤 批次關閉完成",
                description=f"✅ 成功關閉了 {closed_count} 張無活動票券",
                color=discord.Color.green()
            )
            embed.add_field(
                name="關閉條件",
                value=f"超過 {hours} 小時無活動",
                inline=True
            )
            
            await interaction.followup.send(embed=embed)
            
        except ValueError:
            await interaction.response.send_message(
                "❌ 請輸入有效的數字。",
                ephemeral=True
            )
        except Exception as e:
            debug_log(f"[BatchOperation] 批次關閉錯誤：{e}")
            await interaction.response.send_message(
                "❌ 批次關閉時發生錯誤。",
                ephemeral=True
            )


class TemplateSelectView(discord.ui.View):
    """模板選擇介面"""
    
    def __init__(self, guild_id: int, templates: List[Dict[str, Any]]):
        super().__init__(timeout=300)
        self.guild_id = guild_id
        self.templates = templates
        self.dao = TicketDAO()
        
        # 添加模板選擇下拉選單
        if templates:
            select = TemplateSelect(guild_id, templates)
            self.add_item(select)
    
    @discord.ui.button(label="建立新模板", emoji="➕", style=discord.ButtonStyle.primary)
    async def create_template(self, interaction: discord.Interaction, button: discord.ui.Button):
        """建立新模板"""
        modal = CreateTemplateModal(self.guild_id)
        await interaction.response.send_modal(modal)


class TemplateSelect(discord.ui.Select):
    """模板選擇下拉選單"""
    
    def __init__(self, guild_id: int, templates: List[Dict[str, Any]]):
        self.guild_id = guild_id
        self.templates = templates
        self.dao = TicketDAO()
        
        # 建立選項
        options = []
        for template in templates[:25]:  # Discord 限制25個選項
            options.append(discord.SelectOption(
                label=template['name'],
                description=template.get('description', '')[:100],  # 限制描述長度
                value=str(template['id'])
            ))
        
        super().__init__(placeholder="選擇模板...", options=options)
    
    async def callback(self, interaction: discord.Interaction):
        template_id = int(self.values[0])
        
        # 找到選中的模板
        template = next((t for t in self.templates if t['id'] == template_id), None)
        if not template:
            await interaction.response.send_message("❌ 找不到模板。", ephemeral=True)
            return
        
        # 發送模板內容到頻道
        embed = discord.Embed(
            title=f"📋 模板：{template['name']}",
            description=template['content'],
            color=discord.Color.blue()
        )
        
        if template.get('description'):
            embed.set_footer(text=f"說明：{template['description']}")
        
        await interaction.response.send_message(embed=embed)
        
        # 增加使用次數
        await self.dao.increment_template_usage(template_id)


class CreateTemplateModal(discord.ui.Modal):
    """建立模板視窗"""
    
    def __init__(self, guild_id: int):
        super().__init__(title="建立回覆模板", timeout=300)
        self.guild_id = guild_id
        self.dao = TicketDAO()
        
        self.name_input = discord.ui.TextInput(
            label="模板名稱",
            placeholder="例如：常見問題回覆",
            min_length=2,
            max_length=100
        )
        self.add_item(self.name_input)
        
        self.content_input = discord.ui.TextInput(
            label="模板內容",
            style=discord.TextStyle.paragraph,
            placeholder="輸入模板內容...",
            min_length=10,
            max_length=2000
        )
        self.add_item(self.content_input)
        
        self.description_input = discord.ui.TextInput(
            label="模板描述（可選）",
            placeholder="簡短說明此模板的用途",
            required=False,
            max_length=200
        )
        self.add_item(self.description_input)
    
    async def on_submit(self, interaction: discord.Interaction):
        name = self.name_input.value.strip()
        content = self.content_input.value.strip()
        description = self.description_input.value.strip() if self.description_input.value else None
        
        # 檢查模板是否已存在
        existing_template = await self.dao.get_template(self.guild_id, name)
        if existing_template:
            await interaction.response.send_message(
                f"❌ 模板名稱 `{name}` 已存在。",
                ephemeral=True
            )
            return
        
        # 建立模板
        success = await self.dao.create_template(self.guild_id, name, content, description)
        
        if success:
            embed = discord.Embed(
                title="✅ 模板建立成功",
                description=f"模板 `{name}` 已建立。",
                color=discord.Color.green()
            )
            embed.add_field(name="內容預覽", value=content[:200] + "..." if len(content) > 200 else content, inline=False)
            
            await interaction.response.send_message(embed=embed, ephemeral=True)
        else:
            await interaction.response.send_message(
                "❌ 建立模板失敗，請稍後再試。",
                ephemeral=True
            )


# ===== 票券標籤系統 =====

class TagManagementView(discord.ui.View):
    """標籤管理介面"""
    
    def __init__(self, ticket_id: int, current_tags: List[str]):
        super().__init__(timeout=300)
        self.ticket_id = ticket_id
        self.current_tags = current_tags
        self.dao = TicketDAO()
    
    @discord.ui.button(label="添加標籤", emoji="🏷️", style=discord.ButtonStyle.primary)
    async def add_tags(self, interaction: discord.Interaction, button: discord.ui.Button):
        """添加標籤"""
        modal = AddTagsModal(self.ticket_id)
        await interaction.response.send_modal(modal)
    
    @discord.ui.button(label="查看標籤", emoji="👁️", style=discord.ButtonStyle.secondary)
    async def view_tags(self, interaction: discord.Interaction, button: discord.ui.Button):
        """查看標籤"""
        if not self.current_tags:
            await interaction.response.send_message("🏷️ 此票券尚無標籤。", ephemeral=True)
            return
        
        embed = discord.Embed(
            title=f"🏷️ 票券 #{self.ticket_id:04d} 標籤",
            color=discord.Color.blue()
        )
        
        tags_text = " ".join([f"`{tag}`" for tag in self.current_tags])
        embed.add_field(name="當前標籤", value=tags_text, inline=False)
        
        await interaction.response.send_message(embed=embed, ephemeral=True)


class AddTagsModal(discord.ui.Modal):
    """添加標籤視窗"""
    
    def __init__(self, ticket_id: int):
        super().__init__(title="添加標籤", timeout=300)
        self.ticket_id = ticket_id
        self.dao = TicketDAO()
        
        self.tags_input = discord.ui.TextInput(
            label="標籤（用空格或逗號分隔）",
            placeholder="例如：緊急 技術問題 已處理",
            min_length=1,
            max_length=200
        )
        self.add_item(self.tags_input)
    
    async def on_submit(self, interaction: discord.Interaction):
        tags_text = self.tags_input.value.strip()
        
        # 解析標籤
        import re
        tags = re.split(r'[,\s]+', tags_text)
        tags = [tag.strip() for tag in tags if tag.strip()]
        
        if not tags:
            await interaction.response.send_message("❌ 請輸入有效的標籤。", ephemeral=True)
            return
        
        # 檢查標籤數量限制
        current_tags = await self.dao.get_ticket_tags(self.ticket_id)
        total_tags = len(current_tags) + len(tags)
        
        if total_tags > TicketConstants.LIMITS['max_tags_per_ticket'][1]:
            await interaction.response.send_message(
                f"❌ 標籤總數不能超過 {TicketConstants.LIMITS['max_tags_per_ticket'][1]} 個。",
                ephemeral=True
            )
            return
        
        # 添加標籤
        success = await self.dao.add_tags_to_ticket(self.ticket_id, tags)
        
        if success:
            embed = discord.Embed(
                title="🏷️ 標籤添加成功",
                description=f"已為票券 #{self.ticket_id:04d} 添加標籤。",
                color=discord.Color.green()
            )
            
            tags_text = " ".join([f"`{tag}`" for tag in tags])
            embed.add_field(name="新增標籤", value=tags_text, inline=False)
            
            await interaction.response.send_message(embed=embed, ephemeral=True)
        else:
            await interaction.response.send_message("❌ 添加標籤失敗。", ephemeral=True)


# ===== 匯出功能 =====

async def create_pagination_view(tickets: List[Dict], total: int, page: int, 
                                page_size: int, query_params: Dict[str, Any], 
                                user_id: str = None) -> TicketPaginationView:
    """建立分頁視圖的輔助函數"""
    view = TicketPaginationView(tickets, total, page, page_size, query_params, user_id)
    return view


async def create_admin_panel(guild_id: int) -> AdminPanelView:
    """建立管理面板的輔助函數"""
    dao = TicketDAO()
    stats = await dao.get_server_statistics(guild_id)
    return AdminPanelView(guild_id, stats)


async def create_template_view(guild_id: int) -> TemplateSelectView:
    """建立模板選擇視圖的輔助函數"""
    dao = TicketDAO()
    templates = await dao.get_templates(guild_id)
    return TemplateSelectView(guild_id, templates)


def create_sla_dashboard(guild_id: int) -> SLADashboardView:
    """建立 SLA 監控面板的輔助函數"""
    return SLADashboardView(guild_id)


def create_batch_operation_view(guild_id: int) -> BatchOperationView:
    """建立批次操作面板的輔助函數"""
    return BatchOperationView(guild_id)