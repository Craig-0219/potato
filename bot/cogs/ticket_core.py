# bot/cogs/ticket_core.py - 重構後的票券核心系統
"""
票券系統核心功能 - 簡化版
專注於基本的 CRUD 操作和核心管理功能
"""

import discord
from discord.ext import commands, tasks
from discord import app_commands
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Any

from bot.db.ticket_repository import TicketRepository
from bot.services.ticket_manager import TicketManager
from bot.ui.ticket_views import TicketPanelView, TicketControlView
from bot.utils.constants import TicketConstants, TicketError
from bot.utils.helpers import format_duration, get_time_ago
from bot.utils.validators import validate_ticket_creation
from shared.logger import logger


class TicketCore(commands.Cog):
    """票券系統核心功能"""
    
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.repository = TicketRepository()
        self.manager = TicketManager(self.repository)
        
        # 啟動 SLA 監控
        self.sla_monitor.start()
    
    def cog_unload(self):
        """清理資源"""
        self.sla_monitor.cancel()

    # ===== 基本指令 =====
    
    @commands.command(name="setup_ticket")
    @commands.has_permissions(manage_guild=True)
    async def setup_ticket(self, ctx: commands.Context):
        """建立票券面板"""
        try:
            settings = await self.repository.get_settings(ctx.guild.id)
            
            embed = discord.Embed(
                title="🎫 客服中心",
                description=settings.get('welcome_message', "請選擇問題類型來建立支援票券"),
                color=TicketConstants.COLORS['primary']
            )
            
            # 系統資訊
            embed.add_field(
                name="📋 系統資訊",
                value=f"• 每人限制：{settings.get('max_tickets_per_user', 3)} 張\n"
                      f"• 自動關閉：{settings.get('auto_close_hours', 24)} 小時\n"
                      f"• 預期回覆：{settings.get('sla_response_minutes', 60)} 分鐘",
                inline=False
            )
            
            view = TicketPanelView(settings)
            await ctx.send(embed=embed, view=view)
            
            logger.info(f"票券面板建立於 {ctx.guild.name} by {ctx.author}")
            
        except Exception as e:
            logger.error(f"建立票券面板錯誤：{e}")
            await ctx.send("❌ 建立票券面板失敗，請稍後再試。")

    @app_commands.command(name="close", description="關閉票券")
    @app_commands.describe(reason="關閉原因")
    async def close_ticket(self, interaction: discord.Interaction, reason: str = None):
        """關閉票券"""
        try:
            # 驗證是否為票券頻道
            if not interaction.channel.name.startswith('ticket-'):
                await interaction.response.send_message(
                    "❌ 此指令只能在票券頻道中使用。", ephemeral=True
                )
                return
            
            # 取得票券資訊
            ticket = await self.repository.get_ticket_by_channel(interaction.channel.id)
            if not ticket:
                await interaction.response.send_message(
                    "❌ 找不到票券資訊。", ephemeral=True
                )
                return
            
            # 檢查權限
            settings = await self.repository.get_settings(interaction.guild.id)
            can_close = await self._check_close_permission(interaction.user, ticket, settings)
            
            if not can_close:
                await interaction.response.send_message(
                    "❌ 只有票券創建者或客服人員可以關閉票券。", ephemeral=True
                )
                return
            
            # 關閉票券
            success = await self.manager.close_ticket(
                ticket_id=ticket['id'],
                closed_by=interaction.user.id,
                reason=reason
            )
            
            if success:
                await interaction.response.send_message("✅ 票券關閉中...")
                
                # 延遲刪除頻道
                await asyncio.sleep(5)
                try:
                    await interaction.channel.delete(reason=f"票券關閉 - {reason or '無原因'}")
                except:
                    pass
            else:
                await interaction.response.send_message("❌ 關閉票券失敗。", ephemeral=True)
                
        except Exception as e:
            logger.error(f"關閉票券錯誤：{e}")
            await interaction.response.send_message("❌ 發生錯誤，請稍後再試。", ephemeral=True)

    @app_commands.command(name="ticket_info", description="查看票券資訊")
    @app_commands.describe(ticket_id="票券編號（可選）")
    async def ticket_info(self, interaction: discord.Interaction, ticket_id: int = None):
        """查看票券資訊"""
        try:
            # 如果沒有指定 ID，從頻道名稱解析
            if ticket_id is None:
                if not interaction.channel.name.startswith('ticket-'):
                    await interaction.response.send_message(
                        "❌ 請在票券頻道中使用，或指定票券編號。", ephemeral=True
                    )
                    return
                
                ticket = await self.repository.get_ticket_by_channel(interaction.channel.id)
            else:
                ticket = await self.repository.get_ticket_by_id(ticket_id)
            
            if not ticket:
                await interaction.response.send_message("❌ 找不到票券。", ephemeral=True)
                return
            
            # 檢查查看權限
            settings = await self.repository.get_settings(interaction.guild.id)
            can_view = await self._check_view_permission(interaction.user, ticket, settings)
            
            if not can_view:
                await interaction.response.send_message("❌ 你沒有權限查看此票券。", ephemeral=True)
                return
            
            # 建立資訊嵌入
            embed = await self._build_ticket_info_embed(ticket, interaction.guild)
            await interaction.response.send_message(embed=embed, ephemeral=True)
            
        except Exception as e:
            logger.error(f"查看票券資訊錯誤：{e}")
            await interaction.response.send_message("❌ 查詢失敗，請稍後再試。", ephemeral=True)

    @app_commands.command(name="tickets", description="查看票券列表")
    @app_commands.describe(
        status="狀態篩選",
        user="指定用戶（客服限定）"
    )
    async def list_tickets(self, interaction: discord.Interaction, 
                          status: str = "all", user: discord.Member = None):
        """查看票券列表"""
        try:
            settings = await self.repository.get_settings(interaction.guild.id)
            is_staff = await self._is_support_staff(interaction.user, settings)
            
            # 權限檢查
            if user and not is_staff:
                await interaction.response.send_message(
                    "❌ 只有客服人員可以查看其他用戶的票券。", ephemeral=True
                )
                return
            
            # 確定查詢範圍
            target_user_id = user.id if user else (None if is_staff else interaction.user.id)
            
            # 查詢票券
            tickets, total = await self.repository.get_tickets(
                guild_id=interaction.guild.id,
                user_id=target_user_id,
                status=status,
                page=1,
                page_size=10
            )
            
            if not tickets:
                await interaction.response.send_message("📭 沒有找到票券。", ephemeral=True)
                return
            
            # 建立列表嵌入
            embed = await self._build_tickets_list_embed(tickets, total, status, user)
            await interaction.response.send_message(embed=embed, ephemeral=True)
            
        except Exception as e:
            logger.error(f"查看票券列表錯誤：{e}")
            await interaction.response.send_message("❌ 查詢失敗，請稍後再試。", ephemeral=True)

    # ===== 管理指令 =====
    
    @app_commands.command(name="ticket_assign", description="指派票券")
    @app_commands.describe(user="要指派的客服", ticket_id="票券編號")
    async def assign_ticket(self, interaction: discord.Interaction, 
                           user: discord.Member, ticket_id: int = None):
        """指派票券"""
        try:
            settings = await self.repository.get_settings(interaction.guild.id)
            
            # 權限檢查
            if not await self._is_support_staff(interaction.user, settings):
                await interaction.response.send_message("❌ 只有客服人員可以指派票券。", ephemeral=True)
                return
            
            # 檢查被指派者是否為客服
            if not await self._is_support_staff(user, settings):
                await interaction.response.send_message("❌ 只能指派給客服人員。", ephemeral=True)
                return
            
            # 取得票券
            if ticket_id:
                ticket = await self.repository.get_ticket_by_id(ticket_id)
            else:
                ticket = await self.repository.get_ticket_by_channel(interaction.channel.id)
            
            if not ticket:
                await interaction.response.send_message("❌ 找不到票券。", ephemeral=True)
                return
            
            # 執行指派
            success = await self.manager.assign_ticket(ticket['id'], user.id, interaction.user.id)
            
            if success:
                embed = discord.Embed(
                    title="👥 票券指派成功",
                    description=f"票券 #{ticket['id']:04d} 已指派給 {user.mention}",
                    color=TicketConstants.COLORS['success']
                )
                await interaction.response.send_message(embed=embed)
                
                # 通知被指派者
                try:
                    await user.send(f"📋 你被指派了票券 #{ticket['id']:04d}")
                except:
                    pass
            else:
                await interaction.response.send_message("❌ 指派失敗。", ephemeral=True)
                
        except Exception as e:
            logger.error(f"指派票券錯誤：{e}")
            await interaction.response.send_message("❌ 指派失敗，請稍後再試。", ephemeral=True)

    @app_commands.command(name="ticket_priority", description="設定票券優先級")
    @app_commands.describe(priority="優先級", ticket_id="票券編號")
    @app_commands.choices(priority=[
        app_commands.Choice(name="🔴 高", value="high"),
        app_commands.Choice(name="🟡 中", value="medium"), 
        app_commands.Choice(name="🟢 低", value="low")
    ])
    async def set_priority(self, interaction: discord.Interaction, 
                          priority: str, ticket_id: int = None):
        """設定票券優先級"""
        try:
            settings = await self.repository.get_settings(interaction.guild.id)
            
            # 權限檢查
            if not await self._is_support_staff(interaction.user, settings):
                await interaction.response.send_message("❌ 只有客服人員可以設定優先級。", ephemeral=True)
                return
            
            # 取得票券
            if ticket_id:
                ticket = await self.repository.get_ticket_by_id(ticket_id)
            else:
                ticket = await self.repository.get_ticket_by_channel(interaction.channel.id)
            
            if not ticket:
                await interaction.response.send_message("❌ 找不到票券。", ephemeral=True)
                return
            
            # 更新優先級
            success = await self.repository.update_ticket_priority(ticket['id'], priority)
            
            if success:
                emoji = TicketConstants.PRIORITY_EMOJIS[priority]
                await interaction.response.send_message(
                    f"✅ 票券 #{ticket['id']:04d} 優先級已設為 {emoji} **{priority.upper()}**"
                )
            else:
                await interaction.response.send_message("❌ 設定失敗。", ephemeral=True)
                
        except Exception as e:
            logger.error(f"設定優先級錯誤：{e}")
            await interaction.response.send_message("❌ 設定失敗，請稍後再試。", ephemeral=True)

    @app_commands.command(name="ticket_setting", description="票券系統設定")
    @app_commands.describe(setting="設定項目", value="設定值")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def ticket_setting(self, interaction: discord.Interaction, 
                            setting: str = None, value: str = None):
        """票券系統設定"""
        try:
            if not setting:
                # 顯示所有設定
                await self._show_all_settings(interaction)
                return
            
            if not value:
                # 顯示特定設定
                await self._show_setting(interaction, setting)
                return
            
            # 更新設定
            success = await self._update_setting(interaction, setting, value)
            
            if success:
                await interaction.response.send_message(f"✅ 設定 `{setting}` 已更新")
            else:
                await interaction.response.send_message("❌ 設定更新失敗", ephemeral=True)
                
        except Exception as e:
            logger.error(f"設定更新錯誤：{e}")
            await interaction.response.send_message("❌ 設定失敗，請稍後再試。", ephemeral=True)

    @app_commands.command(name="ticket_stats", description="票券統計")
    async def ticket_stats(self, interaction: discord.Interaction):
        """查看票券統計"""
        try:
            settings = await self.repository.get_settings(interaction.guild.id)
            
            # 權限檢查
            if not await self._is_support_staff(interaction.user, settings):
                await interaction.response.send_message("❌ 只有客服人員可以查看統計。", ephemeral=True)
                return
            
            # 取得統計資料
            stats = await self.repository.get_statistics(interaction.guild.id)
            
            embed = discord.Embed(
                title="📊 票券統計",
                color=TicketConstants.COLORS['info']
            )
            
            embed.add_field(
                name="📋 基本統計",
                value=f"**總票券：** {stats.get('total', 0)}\n"
                      f"**開啟中：** {stats.get('open', 0)}\n"
                      f"**已關閉：** {stats.get('closed', 0)}\n"
                      f"**今日新增：** {stats.get('today', 0)}",
                inline=True
            )
            
            # 評分統計
            if stats.get('avg_rating'):
                embed.add_field(
                    name="⭐ 評分統計",
                    value=f"**平均評分：** {stats.get('avg_rating', 0):.1f}/5\n"
                          f"**總評分數：** {stats.get('total_ratings', 0)}\n"
                          f"**滿意度：** {stats.get('satisfaction_rate', 0):.1f}%",
                    inline=True
                )
            
            await interaction.response.send_message(embed=embed, ephemeral=True)
            
        except Exception as e:
            logger.error(f"查看統計錯誤：{e}")
            await interaction.response.send_message("❌ 查詢失敗，請稍後再試。", ephemeral=True)

    # ===== SLA 監控任務 =====
    
    @tasks.loop(minutes=5)
    async def sla_monitor(self):
        """SLA 監控任務"""
        try:
            overdue_tickets = await self.repository.get_overdue_tickets()
            
            for ticket in overdue_tickets:
                guild = self.bot.get_guild(ticket['guild_id'])
                if guild:
                    await self._handle_overdue_ticket(ticket, guild)
                    
        except Exception as e:
            logger.error(f"SLA 監控錯誤：{e}")

    # ===== 私有方法 =====
    
    async def _check_close_permission(self, user: discord.Member, ticket: Dict, settings: Dict) -> bool:
        """檢查關閉權限"""
        # 票券創建者可以關閉
        if str(user.id) == ticket['discord_id']:
            return True
        
        # 客服人員可以關閉
        return await self._is_support_staff(user, settings)
    
    async def _check_view_permission(self, user: discord.Member, ticket: Dict, settings: Dict) -> bool:
        """檢查查看權限"""
        # 票券創建者可以查看
        if str(user.id) == ticket['discord_id']:
            return True
        
        # 客服人員可以查看
        return await self._is_support_staff(user, settings)
    
    async def _is_support_staff(self, user: discord.Member, settings: Dict) -> bool:
        """檢查是否為客服人員"""
        # 管理員視為客服
        if user.guild_permissions.manage_guild:
            return True
        
        # 檢查客服身分組
        support_roles = settings.get('support_roles', [])
        user_role_ids = {role.id for role in user.roles}
        
        return any(role_id in user_role_ids for role_id in support_roles)
    
    async def _build_ticket_info_embed(self, ticket: Dict, guild: discord.Guild) -> discord.Embed:
        """建立票券資訊嵌入"""
        priority_emoji = TicketConstants.PRIORITY_EMOJIS.get(ticket['priority'], '🟡')
        status_emoji = TicketConstants.STATUS_EMOJIS.get(ticket['status'], '🟢')
        color = TicketConstants.PRIORITY_COLORS.get(ticket['priority'], 0x00ff00)
        
        embed = discord.Embed(
            title=f"🎫 票券 #{ticket['id']:04d}",
            color=color
        )
        
        embed.add_field(
            name="📋 基本資訊", 
            value=f"**類型：** {ticket['type']}\n"
                  f"**狀態：** {status_emoji} {ticket['status'].upper()}\n"
                  f"**優先級：** {priority_emoji} {ticket['priority'].upper()}",
            inline=True
        )
        
        embed.add_field(
            name="👤 用戶資訊",
            value=f"**開票者：** <@{ticket['discord_id']}>\n"
                  f"**用戶名：** {ticket['username']}",
            inline=True
        )
        
        # 時間資訊
        created_time = get_time_ago(ticket['created_at'])
        time_info = f"**建立：** {created_time}"
        
        if ticket['closed_at']:
            closed_time = get_time_ago(ticket['closed_at'])
            duration = ticket['closed_at'] - ticket['created_at']
            time_info += f"\n**關閉：** {closed_time}\n"
            time_info += f"**持續：** {format_duration(duration)}"
        
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
            stars = "⭐" * ticket['rating']
            rating_text = f"**評分：** {stars} ({ticket['rating']}/5)"
            
            if ticket.get('rating_feedback'):
                rating_text += f"\n**回饋：** {ticket['rating_feedback'][:100]}..."
            
            embed.add_field(name="⭐ 評分", value=rating_text, inline=True)
        
        return embed
    
    async def _build_tickets_list_embed(self, tickets: List[Dict], total: int, 
                                       status: str, user: discord.Member) -> discord.Embed:
        """建立票券列表嵌入"""
        embed = discord.Embed(
            title="🎫 票券列表",
            color=TicketConstants.COLORS['info']
        )
        
        # 篩選條件
        filters = []
        if status != "all":
            filters.append(f"狀態: {status}")
        if user:
            filters.append(f"用戶: {user.display_name}")
        
        if filters:
            embed.description = f"篩選條件：{' | '.join(filters)}"
        
        # 顯示票券
        for ticket in tickets[:10]:  # 限制顯示
            status_emoji = TicketConstants.STATUS_EMOJIS.get(ticket['status'], '🟢')
            priority_emoji = TicketConstants.PRIORITY_EMOJIS.get(ticket['priority'], '🟡')
            
            field_value = f"{status_emoji} {ticket['status'].upper()} {priority_emoji}\n"
            field_value += f"👤 <@{ticket['discord_id']}>\n"
            field_value += f"📅 {get_time_ago(ticket['created_at'])}"
            
            if ticket.get('assigned_to'):
                field_value += f"\n👥 <@{ticket['assigned_to']}>"
            
            if ticket.get('rating'):
                stars = "⭐" * ticket['rating']
                field_value += f"\n{stars}"
            
            embed.add_field(
                name=f"#{ticket['id']:04d} - {ticket['type']}",
                value=field_value,
                inline=True
            )
        
        embed.set_footer(text=f"共 {total} 筆記錄")
        return embed
    
    async def _show_all_settings(self, interaction: discord.Interaction):
        """顯示所有設定"""
        settings = await self.repository.get_settings(interaction.guild.id)
        
        embed = discord.Embed(
            title="⚙️ 票券系統設定",
            color=TicketConstants.COLORS['info']
        )
        
        # 基本設定
        category_text = f"<#{settings['category_id']}>" if settings.get('category_id') else "未設定"
        
        embed.add_field(
            name="🎫 基本設定",
            value=f"**分類頻道：** {category_text}\n"
                  f"**每人限制：** {settings.get('max_tickets_per_user', 3)} 張\n"
                  f"**自動關閉：** {settings.get('auto_close_hours', 24)} 小時\n"
                  f"**SLA 時間：** {settings.get('sla_response_minutes', 60)} 分鐘",
            inline=False
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
            inline=False
        )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    async def _show_setting(self, interaction: discord.Interaction, setting: str):
        """顯示特定設定"""
        # 實作特定設定顯示邏輯
        pass
    
    async def _update_setting(self, interaction: discord.Interaction, setting: str, value: str) -> bool:
        """更新設定"""
        # 實作設定更新邏輯
        return await self.repository.update_setting(interaction.guild.id, setting, value)
    
    async def _handle_overdue_ticket(self, ticket: Dict, guild: discord.Guild):
        """處理超時票券"""
        # 實作超時處理邏輯
        pass


async def setup(bot: commands.Bot):
    """載入 Cog"""
    await bot.add_cog(TicketCore(bot))