# bot/cogs/ticket_core.py - 修復完善版
"""
票券系統核心功能 - 修復完善版
解決所有已知問題並增強功能穩定性
"""

import discord
from discord.ext import commands, tasks
from discord import app_commands
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Any, Tuple
import asyncio
import json

from bot.db.ticket_repository import TicketRepository
from bot.services.ticket_manager import TicketManager
from bot.views.ticket_views import TicketPanelView, TicketControlView
from bot.utils.constants import TicketConstants, TicketError
from bot.utils.helpers import format_duration, get_time_ago
from bot.utils.validators import validate_ticket_creation
from shared.logger import logger


class TicketCore(commands.Cog):
    """票券系統核心功能 - 修復版"""
    
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.repository = TicketRepository()
        self.manager = TicketManager(self.repository)
        
        # 啟動 SLA 監控
        self.sla_monitor.start()
        self.cleanup_task.start()
    
    def cog_unload(self):
        """清理資源"""
        self.sla_monitor.cancel()
        self.cleanup_task.cancel()

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
            
            # 修復：正確傳遞設定
            view = TicketPanelView(settings)
            message = await ctx.send(embed=embed, view=view)
            
            # 儲存面板訊息ID用於持久化
            await self.repository.save_panel_message(ctx.guild.id, message.id, ctx.channel.id)
            
            logger.info(f"票券面板建立於 {ctx.guild.name} by {ctx.author}")
            
        except Exception as e:
            logger.error(f"建立票券面板錯誤：{e}")
            await ctx.send("❌ 建立票券面板失敗，請稍後再試。")

    @app_commands.command(name="close", description="關閉票券")
    @app_commands.describe(reason="關閉原因", request_rating="是否要求評分")
    async def close_ticket(self, interaction: discord.Interaction, 
                          reason: str = None, request_rating: bool = True):
        """關閉票券 - 修復版"""
        try:
            # 驗證是否為票券頻道
            if not self._is_ticket_channel(interaction.channel):
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
            
            # 檢查票券狀態
            if ticket['status'] == 'closed':
                await interaction.response.send_message(
                    "❌ 此票券已經關閉。", ephemeral=True
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
                reason=reason or "手動關閉"
            )
            
            if success:
                embed = discord.Embed(
                    title="✅ 票券已關閉",
                    description=f"票券 #{ticket['id']:04d} 已成功關閉",
                    color=TicketConstants.COLORS['success']
                )
                
                if reason:
                    embed.add_field(name="關閉原因", value=reason, inline=False)
                
                await interaction.response.send_message(embed=embed)
                
                # 如果是票券創建者且要求評分
                if (str(interaction.user.id) == ticket['discord_id'] and 
                    request_rating and not ticket.get('rating')):
                    
                    # 延遲顯示評分界面
                    await asyncio.sleep(2)
                    await self._show_rating_interface(interaction.channel, ticket['id'])
                
                # 延遲刪除頻道
                await self._schedule_channel_deletion(interaction.channel, delay=30)
                
            else:
                await interaction.response.send_message(
                    "❌ 關閉票券失敗，請稍後再試。", ephemeral=True
                )
                
        except Exception as e:
            logger.error(f"關閉票券錯誤：{e}")
            if not interaction.response.is_done():
                await interaction.response.send_message(
                    "❌ 發生錯誤，請稍後再試。", ephemeral=True
                )

    @app_commands.command(name="ticket_info", description="查看票券資訊")
    @app_commands.describe(ticket_id="票券編號（可選）")
    async def ticket_info(self, interaction: discord.Interaction, ticket_id: int = None):
        """查看票券資訊 - 修復版"""
        try:
            # 取得票券
            if ticket_id:
                ticket = await self.repository.get_ticket_by_id(ticket_id)
            elif self._is_ticket_channel(interaction.channel):
                ticket = await self.repository.get_ticket_by_channel(interaction.channel.id)
            else:
                await interaction.response.send_message(
                    "❌ 請在票券頻道中使用，或指定票券編號。", ephemeral=True
                )
                return
            
            if not ticket:
                await interaction.response.send_message(
                    "❌ 找不到票券。", ephemeral=True
                )
                return
            
            # 檢查查看權限
            settings = await self.repository.get_settings(interaction.guild.id)
            can_view = await self._check_view_permission(interaction.user, ticket, settings)
            
            if not can_view:
                await interaction.response.send_message(
                    "❌ 你沒有權限查看此票券。", ephemeral=True
                )
                return
            
            # 建立資訊嵌入
            embed = await self._build_ticket_info_embed(ticket, interaction.guild)
            await interaction.response.send_message(embed=embed, ephemeral=True)
            
        except Exception as e:
            logger.error(f"查看票券資訊錯誤：{e}")
            await interaction.response.send_message(
                "❌ 查詢失敗，請稍後再試。", ephemeral=True
            )

    @app_commands.command(name="tickets", description="查看票券列表")
    @app_commands.describe(
        status="狀態篩選",
        user="指定用戶（客服限定）",
        priority="優先級篩選"
    )
    @app_commands.choices(
        status=[
            app_commands.Choice(name="全部", value="all"),
            app_commands.Choice(name="開啟中", value="open"),
            app_commands.Choice(name="已關閉", value="closed")
        ],
        priority=[
            app_commands.Choice(name="全部", value="all"),
            app_commands.Choice(name="高", value="high"),
            app_commands.Choice(name="中", value="medium"),
            app_commands.Choice(name="低", value="low")
        ]
    )
    async def list_tickets(self, interaction: discord.Interaction, 
                          status: str = "all", user: discord.Member = None,
                          priority: str = "all"):
        """查看票券列表 - 修復版"""
        try:
            settings = await self.repository.get_settings(interaction.guild.id)
            is_staff = await self._is_support_staff(interaction.user, settings)
            
            # 權限檢查
            if user and not is_staff:
                await interaction.response.send_message(
                    "❌ 只有客服人員可以查看其他用戶的票券。", ephemeral=True
                )
                return
            
            # 構建查詢參數
            query_params = {
                'guild_id': interaction.guild.id,
                'page': 1,
                'page_size': 10
            }
            
            # 用戶篩選
            if user:
                query_params['user_id'] = user.id
            elif not is_staff:
                query_params['user_id'] = interaction.user.id
            
            # 狀態篩選
            if status != "all":
                query_params['status'] = status
                
            # 優先級篩選
            if priority != "all":
                query_params['priority'] = priority
            
            # 查詢票券
            tickets, total = await self.repository.get_tickets(**query_params)
            
            if not tickets:
                await interaction.response.send_message(
                    "📭 沒有找到符合條件的票券。", ephemeral=True
                )
                return
            
            # 建立列表嵌入
            embed = await self._build_tickets_list_embed(
                tickets, total, status, user, priority
            )
            
            # 如果票券很多，添加分頁控制
            if total > 10:
                from bot.ui.ticket_views import TicketListView
                view = TicketListView(tickets, 1, (total + 9) // 10, **query_params)
                await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
            else:
                await interaction.response.send_message(embed=embed, ephemeral=True)
            
        except Exception as e:
            logger.error(f"查看票券列表錯誤：{e}")
            await interaction.response.send_message(
                "❌ 查詢失敗，請稍後再試。", ephemeral=True
            )

    # ===== 管理指令 =====
    
    @app_commands.command(name="ticket_assign", description="指派票券")
    @app_commands.describe(user="要指派的客服", ticket_id="票券編號（可選）")
    async def assign_ticket(self, interaction: discord.Interaction, 
                           user: discord.Member, ticket_id: int = None):
        """指派票券 - 修復版"""
        try:
            settings = await self.repository.get_settings(interaction.guild.id)
            
            # 權限檢查
            if not await self._is_support_staff(interaction.user, settings):
                await interaction.response.send_message(
                    "❌ 只有客服人員可以指派票券。", ephemeral=True
                )
                return
            
            # 檢查被指派者是否為客服
            if not await self._is_support_staff(user, settings):
                await interaction.response.send_message(
                    "❌ 只能指派給客服人員。", ephemeral=True
                )
                return
            
            # 取得票券
            if ticket_id:
                ticket = await self.repository.get_ticket_by_id(ticket_id)
            elif self._is_ticket_channel(interaction.channel):
                ticket = await self.repository.get_ticket_by_channel(interaction.channel.id)
            else:
                await interaction.response.send_message(
                    "❌ 請在票券頻道中使用，或指定票券編號。", ephemeral=True
                )
                return
            
            if not ticket:
                await interaction.response.send_message(
                    "❌ 找不到票券。", ephemeral=True
                )
                return
                
            if ticket['status'] == 'closed':
                await interaction.response.send_message(
                    "❌ 無法指派已關閉的票券。", ephemeral=True
                )
                return
            
            # 執行指派
            success = await self.manager.assign_ticket(
                ticket['id'], user.id, interaction.user.id
            )
            
            if success:
                embed = discord.Embed(
                    title="👥 票券指派成功",
                    description=f"票券 #{ticket['id']:04d} 已指派給 {user.mention}",
                    color=TicketConstants.COLORS['success']
                )
                
                # 添加票券資訊
                embed.add_field(
                    name="票券資訊",
                    value=f"**類型：** {ticket['type']}\n"
                          f"**創建者：** <@{ticket['discord_id']}>\n"
                          f"**指派者：** {interaction.user.mention}",
                    inline=False
                )
                
                await interaction.response.send_message(embed=embed)
                
                # 通知被指派者
                try:
                    await self._notify_assignment(user, ticket)
                except:
                    pass  # 私訊失敗不影響主流程
                    
            else:
                await interaction.response.send_message(
                    "❌ 指派失敗，請稍後再試。", ephemeral=True
                )
                
        except Exception as e:
            logger.error(f"指派票券錯誤：{e}")
            await interaction.response.send_message(
                "❌ 指派失敗，請稍後再試。", ephemeral=True
            )

    @app_commands.command(name="ticket_priority", description="設定票券優先級")
    @app_commands.describe(priority="優先級", ticket_id="票券編號（可選）")
    @app_commands.choices(priority=[
        app_commands.Choice(name="🔴 高", value="high"),
        app_commands.Choice(name="🟡 中", value="medium"), 
        app_commands.Choice(name="🟢 低", value="low")
    ])
    async def set_priority(self, interaction: discord.Interaction, 
                          priority: str, ticket_id: int = None):
        """設定票券優先級 - 修復版"""
        try:
            settings = await self.repository.get_settings(interaction.guild.id)
            
            # 權限檢查
            if not await self._is_support_staff(interaction.user, settings):
                await interaction.response.send_message(
                    "❌ 只有客服人員可以設定優先級。", ephemeral=True
                )
                return
            
            # 取得票券
            if ticket_id:
                ticket = await self.repository.get_ticket_by_id(ticket_id)
            elif self._is_ticket_channel(interaction.channel):
                ticket = await self.repository.get_ticket_by_channel(interaction.channel.id)
            else:
                await interaction.response.send_message(
                    "❌ 請在票券頻道中使用，或指定票券編號。", ephemeral=True
                )
                return
            
            if not ticket:
                await interaction.response.send_message(
                    "❌ 找不到票券。", ephemeral=True
                )
                return
                
            if ticket['status'] == 'closed':
                await interaction.response.send_message(
                    "❌ 無法修改已關閉票券的優先級。", ephemeral=True
                )
                return
            
            # 檢查是否已是相同優先級
            if ticket.get('priority') == priority:
                await interaction.response.send_message(
                    f"ℹ️ 票券優先級已經是 {TicketConstants.PRIORITY_EMOJIS[priority]} **{priority.upper()}**",
                    ephemeral=True
                )
                return
            
            # 更新優先級
            success = await self.repository.update_ticket_priority(
                ticket['id'], priority
            )
            
            if success:
                # 記錄操作日誌
                await self.repository.add_log(
                    ticket['id'], 
                    'priority_change',
                    f"優先級從 {ticket.get('priority', 'medium')} 變更為 {priority}",
                    str(interaction.user.id)
                )
                
                emoji = TicketConstants.PRIORITY_EMOJIS[priority]
                embed = discord.Embed(
                    title="🎯 優先級已更新",
                    description=f"票券 #{ticket['id']:04d} 優先級已設為 {emoji} **{priority.upper()}**",
                    color=TicketConstants.PRIORITY_COLORS[priority]
                )
                
                await interaction.response.send_message(embed=embed)
                
                # 如果是提升到高優先級，發送通知
                if priority == 'high':
                    await self._notify_high_priority(ticket, interaction.guild, settings)
                    
            else:
                await interaction.response.send_message(
                    "❌ 設定失敗，請稍後再試。", ephemeral=True
                )
                
        except Exception as e:
            logger.error(f"設定優先級錯誤：{e}")
            await interaction.response.send_message(
                "❌ 設定失敗，請稍後再試。", ephemeral=True
            )

    @app_commands.command(name="ticket_rating", description="為票券評分")
    @app_commands.describe(
        ticket_id="票券編號", 
        rating="評分（1-5星）", 
        feedback="評分回饋（可選）"
    )
    @app_commands.choices(rating=[
        app_commands.Choice(name="⭐ 1星", value=1),
        app_commands.Choice(name="⭐⭐ 2星", value=2),
        app_commands.Choice(name="⭐⭐⭐ 3星", value=3),
        app_commands.Choice(name="⭐⭐⭐⭐ 4星", value=4),
        app_commands.Choice(name="⭐⭐⭐⭐⭐ 5星", value=5)
    ])
    async def rate_ticket(self, interaction: discord.Interaction, 
                         ticket_id: int, rating: int, feedback: str = None):
        """票券評分 - 修復版"""
        try:
            # 取得票券
            ticket = await self.repository.get_ticket_by_id(ticket_id)
            if not ticket:
                await interaction.response.send_message(
                    "❌ 找不到指定的票券。", ephemeral=True
                )
                return
                
            # 檢查權限（只有票券創建者可以評分）
            if str(interaction.user.id) != ticket['discord_id']:
                await interaction.response.send_message(
                    "❌ 只有票券創建者可以進行評分。", ephemeral=True
                )
                return
                
            # 檢查票券狀態
            if ticket['status'] != 'closed':
                await interaction.response.send_message(
                    "❌ 只能為已關閉的票券評分。", ephemeral=True
                )
                return
                
            # 檢查是否已評分
            if ticket.get('rating'):
                await interaction.response.send_message(
                    "❌ 此票券已經評分過了。", ephemeral=True
                )
                return
            
            # 保存評分
            success = await self.manager.save_rating(ticket_id, rating, feedback)
            
            if success:
                stars = TicketConstants.RATING_EMOJIS.get(rating, "⭐")
                color = TicketConstants.RATING_COLORS.get(rating, 0xf1c40f)
                
                embed = discord.Embed(
                    title="⭐ 評分已保存",
                    description=f"感謝您為票券 #{ticket_id:04d} 評分！",
                    color=color
                )
                
                embed.add_field(
                    name="評分",
                    value=f"{stars} ({rating}/5)",
                    inline=True
                )
                
                if feedback:
                    embed.add_field(
                        name="回饋意見",
                        value=feedback[:500] + "..." if len(feedback) > 500 else feedback,
                        inline=False
                    )
                
                embed.add_field(
                    name="票券資訊",
                    value=f"**類型：** {ticket['type']}\n"
                          f"**處理時間：** {get_time_ago(ticket['created_at'])} - {get_time_ago(ticket['closed_at'])}",
                    inline=False
                )
                
                await interaction.response.send_message(embed=embed)
                
                # 記錄評分日誌
                await self.repository.add_log(
                    ticket_id, 
                    'rating',
                    f"用戶評分：{rating}星" + (f"，回饋：{feedback[:100]}" if feedback else ""),
                    str(interaction.user.id)
                )
                
            else:
                await interaction.response.send_message(
                    "❌ 評分保存失敗，請稍後再試。", ephemeral=True
                )
                
        except Exception as e:
            logger.error(f"票券評分錯誤：{e}")
            await interaction.response.send_message(
                "❌ 評分失敗，請稍後再試。", ephemeral=True
            )

    @app_commands.command(name="ticket_setting", description="票券系統設定")
    @app_commands.describe(setting="設定項目", value="設定值")
    @app_commands.checks.has_permissions(manage_guild=True)
    @app_commands.choices(setting=[
        app_commands.Choice(name="分類頻道", value="category"),
        app_commands.Choice(name="客服身分組", value="support_roles"),
        app_commands.Choice(name="每人票券限制", value="limits"),
        app_commands.Choice(name="自動關閉時間", value="auto_close"),
        app_commands.Choice(name="SLA回應時間", value="sla_response"),
        app_commands.Choice(name="歡迎訊息", value="welcome"),
        app_commands.Choice(name="日誌頻道", value="log_channel")
    ])
    async def ticket_setting(self, interaction: discord.Interaction, 
                            setting: str = None, value: str = None):
        """票券系統設定 - 修復版"""
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
            success, message = await self._update_setting(interaction, setting, value)
            
            if success:
                embed = discord.Embed(
                    title="⚙️ 設定已更新",
                    description=f"設定項目 `{setting}` 已成功更新",
                    color=TicketConstants.COLORS['success']
                )
                
                if message:
                    embed.add_field(name="詳細資訊", value=message, inline=False)
                
                await interaction.response.send_message(embed=embed)
            else:
                await interaction.response.send_message(
                    f"❌ 設定更新失敗：{message}",
                    ephemeral=True
                )
                
        except Exception as e:
            logger.error(f"設定更新錯誤：{e}")
            await interaction.response.send_message(
                "❌ 設定失敗，請稍後再試。", ephemeral=True
            )

    @app_commands.command(name="ticket_stats", description="票券統計")
    @app_commands.describe(period="統計期間")
    @app_commands.choices(period=[
        app_commands.Choice(name="今日", value="today"),
        app_commands.Choice(name="本週", value="week"),
        app_commands.Choice(name="本月", value="month"),
        app_commands.Choice(name="全部", value="all")
    ])
    async def ticket_stats(self, interaction: discord.Interaction, period: str = "week"):
        """查看票券統計 - 修復版"""
        try:
            settings = await self.repository.get_settings(interaction.guild.id)
            
            # 權限檢查
            if not await self._is_support_staff(interaction.user, settings):
                await interaction.response.send_message(
                    "❌ 只有客服人員可以查看統計。", ephemeral=True
                )
                return
            
            # 取得統計資料
            stats = await self.repository.get_statistics(interaction.guild.id, period)
            
            # 期間名稱映射
            period_names = {
                "today": "今日",
                "week": "本週", 
                "month": "本月",
                "all": "全部時間"
            }
            
            embed = discord.Embed(
                title=f"📊 票券統計 - {period_names.get(period, '本週')}",
                color=TicketConstants.COLORS['info']
            )
            
            # 基本統計
            embed.add_field(
                name="📋 基本統計",
                value=f"**總票券：** {stats.get('total', 0)}\n"
                      f"**開啟中：** {stats.get('open', 0)}\n"
                      f"**已關閉：** {stats.get('closed', 0)}\n"
                      f"**新建票券：** {stats.get('created', 0)}",
                inline=True
            )
            
            # 優先級分布
            priority_stats = stats.get('priority_distribution', {})
            if priority_stats:
                priority_text = ""
                for priority in ['high', 'medium', 'low']:
                    emoji = TicketConstants.PRIORITY_EMOJIS.get(priority, '🟡')
                    count = priority_stats.get(priority, 0)
                    priority_text += f"{emoji} **{priority.upper()}：** {count}\n"
                
                embed.add_field(
                    name="🎯 優先級分布",
                    value=priority_text,
                    inline=True
                )
            
            # 評分統計
            if stats.get('avg_rating'):
                satisfaction_rate = stats.get('satisfaction_rate', 0)
                embed.add_field(
                    name="⭐ 滿意度",
                    value=f"**平均評分：** {stats.get('avg_rating', 0):.1f}/5\n"
                          f"**評分總數：** {stats.get('total_ratings', 0)}\n"
                          f"**滿意度：** {satisfaction_rate:.1f}%",
                    inline=True
                )
            
            # SLA統計
            if stats.get('sla_stats'):
                sla_stats = stats['sla_stats']
                embed.add_field(
                    name="⏱️ SLA表現",
                    value=f"**平均回應：** {sla_stats.get('avg_response_time', 0):.1f} 分鐘\n"
                          f"**達標率：** {sla_stats.get('compliance_rate', 0):.1f}%\n"
                          f"**超時票券：** {sla_stats.get('overdue_tickets', 0)}",
                    inline=True
                )
            
            # 客服統計（只對管理員顯示）
            if interaction.user.guild_permissions.manage_guild:
                staff_stats = stats.get('staff_performance', {})
                if staff_stats:
                    top_staff = sorted(
                        staff_stats.items(),
                        key=lambda x: x[1].get('handled_tickets', 0),
                        reverse=True
                    )[:3]  # 顯示前3名
                    
                    staff_text = ""
                    for staff_id, performance in top_staff:
                        try:
                            member = interaction.guild.get_member(int(staff_id))
                            name = member.display_name if member else f"用戶{staff_id}"
                            handled = performance.get('handled_tickets', 0)
                            avg_rating = performance.get('avg_rating', 0)
                            staff_text += f"**{name}：** {handled}張 ({avg_rating:.1f}⭐)\n"
                        except:
                            continue
                    
                    if staff_text:
                        embed.add_field(
                            name="👥 客服表現 TOP3",
                            value=staff_text,
                            inline=False
                        )
            
            # 添加時間戳
            embed.set_footer(
                text=f"統計時間：{datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M')} UTC"
            )
            
            await interaction.response.send_message(embed=embed, ephemeral=True)
            
        except Exception as e:
            logger.error(f"查看統計錯誤：{e}")
            await interaction.response.send_message(
                "❌ 查詢失敗，請稍後再試。", ephemeral=True
            )

    # ===== SLA 監控任務 =====
    
    @tasks.loop(minutes=5)
    async def sla_monitor(self):
        """SLA 監控任務 - 修復版"""
        try:
            # 取得所有超時票券
            overdue_tickets = await self.repository.get_overdue_tickets()
            
            if not overdue_tickets:
                return
            
            # 按伺服器分組處理
            guild_tickets = {}
            for ticket in overdue_tickets:
                guild_id = ticket['guild_id']
                if guild_id not in guild_tickets:
                    guild_tickets[guild_id] = []
                guild_tickets[guild_id].append(ticket)
            
            # 處理每個伺服器的超時票券
            for guild_id, tickets in guild_tickets.items():
                try:
                    guild = self.bot.get_guild(guild_id)
                    if guild:
                        await self._handle_guild_overdue_tickets(guild, tickets)
                except Exception as e:
                    logger.error(f"處理伺服器 {guild_id} SLA 超時錯誤：{e}")
                    
        except Exception as e:
            logger.error(f"SLA 監控錯誤：{e}")

    @tasks.loop(hours=6)
    async def cleanup_task(self):
        """定期清理任務"""
        try:
            logger.info("開始執行票券系統清理任務")
            
            # 清理舊日誌（30天前）
            cleaned_logs = await self.repository.cleanup_old_logs(days=30)
            logger.info(f"清理了 {cleaned_logs} 條舊日誌")
            
            # 清理過期的統計快取
            await self.repository.cleanup_expired_cache()
            
            # 檢查並關閉超時的未活動票券
            for guild in self.bot.guilds:
                try:
                    settings = await self.repository.get_settings(guild.id)
                    auto_close_hours = settings.get('auto_close_hours', 24)
                    
                    if auto_close_hours > 0:
                        closed_count = await self._auto_close_inactive_tickets(
                            guild.id, auto_close_hours
                        )
                        if closed_count > 0:
                            logger.info(f"自動關閉了 {closed_count} 張無活動票券 - 伺服器: {guild.name}")
                except Exception as e:
                    logger.error(f"清理伺服器 {guild.id} 票券錯誤：{e}")
            
            logger.info("票券系統清理任務完成")
            
        except Exception as e:
            logger.error(f"清理任務錯誤：{e}")

    @sla_monitor.before_loop
    async def before_sla_monitor(self):
        await self.bot.wait_until_ready()

    @cleanup_task.before_loop
    async def before_cleanup_task(self):
        await self.bot.wait_until_ready()

    # ===== 私有方法 =====
    
    def _is_ticket_channel(self, channel: discord.TextChannel) -> bool:
        """檢查是否為票券頻道"""
        return (hasattr(channel, 'name') and 
                channel.name.startswith('ticket-'))
    
    async def _check_close_permission(self, user: discord.Member, 
                                    ticket: Dict, settings: Dict) -> bool:
        """檢查關閉權限"""
        # 票券創建者可以關閉
        if str(user.id) == ticket['discord_id']:
            return True
        
        # 客服人員可以關閉
        return await self._is_support_staff(user, settings)
    
    async def _check_view_permission(self, user: discord.Member, 
                                   ticket: Dict, settings: Dict) -> bool:
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
        if not support_roles:
            return False
            
        user_role_ids = {role.id for role in user.roles}
        return any(role_id in user_role_ids for role_id in support_roles)
    
    async def _build_ticket_info_embed(self, ticket: Dict, guild: discord.Guild) -> discord.Embed:
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
        time_info = f"**建立：** {created_time}"
        
        if ticket.get('closed_at'):
            closed_time = get_time_ago(ticket['closed_at'])
            duration = ticket['closed_at'] - ticket['created_at']
            time_info += f"\n**關閉：** {closed_time}\n"
            time_info += f"**持續：** {format_duration(duration)}"
        else:
            # 計算已開啟時間
            open_duration = datetime.now(timezone.utc) - ticket['created_at']
            time_info += f"\n**已開啟：** {format_duration(open_duration)}"
        
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
        
        # 添加頻道資訊
        if ticket['status'] == 'open':
            embed.add_field(
                name="📍 頻道資訊",
                value=f"**頻道：** <#{ticket['channel_id']}>",
                inline=True
            )
        
        return embed
    
    async def _build_tickets_list_embed(self, tickets: List[Dict], total: int, 
                                       status: str, user: discord.Member, 
                                       priority: str) -> discord.Embed:
        """建立票券列表嵌入"""
        embed = discord.Embed(
            title="🎫 票券列表",
            color=TicketConstants.COLORS['info']
        )
        
        # 篩選條件描述
        filters = []
        if status != "all":
            filters.append(f"狀態: {status}")
        if user:
            filters.append(f"用戶: {user.display_name}")
        if priority != "all":
            filters.append(f"優先級: {priority}")
        
        if filters:
            embed.description = f"**篩選條件：** {' | '.join(filters)}"
        
        # 顯示票券
        for ticket in tickets[:10]:  # 限制顯示前10個
            status_emoji = TicketConstants.STATUS_EMOJIS.get(ticket['status'], '🟢')
            priority_emoji = TicketConstants.PRIORITY_EMOJIS.get(ticket.get('priority', 'medium'), '🟡')
            
            field_value = f"{status_emoji} {ticket['status'].upper()} {priority_emoji}\n"
            field_value += f"👤 <@{ticket['discord_id']}>\n"
            field_value += f"📅 {get_time_ago(ticket['created_at'])}"
            
            if ticket.get('assigned_to'):
                field_value += f"\n👥 <@{ticket['assigned_to']}>"
            
            if ticket.get('rating'):
                stars = "⭐" * ticket['rating']
                field_value += f"\n{stars}"
            
            # 如果是開啟的票券，添加頻道連結
            if ticket['status'] == 'open':
                field_value += f"\n📍 <#{ticket['channel_id']}>"
            
            embed.add_field(
                name=f"#{ticket['id']:04d} - {ticket['type']}",
                value=field_value,
                inline=True
            )
        
        embed.set_footer(text=f"共 {total} 筆記錄" + (f"（顯示前 10 筆）" if total > 10 else ""))
        return embed
    
    async def _show_all_settings(self, interaction: discord.Interaction):
        """顯示所有設定"""
        try:
            settings = await self.repository.get_settings(interaction.guild.id)
            
            embed = discord.Embed(
                title="⚙️ 票券系統設定",
                color=TicketConstants.COLORS['info']
            )
            
            # 基本設定
            category_text = f"<#{settings['category_id']}>" if settings.get('category_id') else "❌ 未設定"
            log_channel_text = f"<#{settings['log_channel_id']}>" if settings.get('log_channel_id') else "未設定"
            
            embed.add_field(
                name="🎫 基本設定",
                value=f"**分類頻道：** {category_text}\n"
                      f"**每人限制：** {settings.get('max_tickets_per_user', 3)} 張\n"
                      f"**自動關閉：** {settings.get('auto_close_hours', 24)} 小時\n"
                      f"**SLA 時間：** {settings.get('sla_response_minutes', 60)} 分鐘\n"
                      f"**日誌頻道：** {log_channel_text}",
                inline=False
            )
            
            # 客服設定
            support_roles = settings.get('support_roles', [])
            if support_roles:
                role_mentions = []
                for role_id in support_roles:
                    role = interaction.guild.get_role(role_id)
                    if role:
                        role_mentions.append(role.mention)
                    else:
                        role_mentions.append(f"<@&{role_id}> (已刪除)")
                support_text = ", ".join(role_mentions)
            else:
                support_text = "❌ 未設定"
            
            embed.add_field(
                name="👥 客服設定",
                value=f"**客服身分組：** {support_text}",
                inline=False
            )
            
            # 歡迎訊息
            welcome_msg = settings.get('welcome_message', TicketConstants.DEFAULT_SETTINGS['welcome_message'])
            welcome_preview = welcome_msg[:100] + "..." if len(welcome_msg) > 100 else welcome_msg
            
            embed.add_field(
                name="💬 歡迎訊息",
                value=f"```{welcome_preview}```",
                inline=False
            )
            
            # 系統狀態
            stats = await self.repository.get_statistics(interaction.guild.id, "today")
            embed.add_field(
                name="📊 今日狀態",
                value=f"**開啟票券：** {stats.get('open', 0)}\n"
                      f"**新建票券：** {stats.get('created', 0)}\n"
                      f"**已關閉：** {stats.get('closed', 0)}",
                inline=True
            )
            
            # 使用說明
            embed.add_field(
                name="💡 設定指令",
                value="使用 `/ticket_setting <項目> <值>` 來修改設定\n"
                      "例如：`/ticket_setting limits 5`",
                inline=False
            )
            
            await interaction.response.send_message(embed=embed, ephemeral=True)
            
        except Exception as e:
            logger.error(f"顯示設定錯誤：{e}")
            await interaction.response.send_message(
                "❌ 查詢設定失敗，請稍後再試。", ephemeral=True
            )
    
    async def _show_setting(self, interaction: discord.Interaction, setting: str):
        """顯示特定設定"""
        try:
            settings = await self.repository.get_settings(interaction.guild.id)
            
            setting_info = {
                "category": {
                    "name": "分類頻道",
                    "current": f"<#{settings['category_id']}>" if settings.get('category_id') else "未設定",
                    "description": "票券頻道將建立在此分類下",
                    "example": "/ticket_setting category #客服中心"
                },
                "support_roles": {
                    "name": "客服身分組",
                    "current": "已設定" if settings.get('support_roles') else "未設定",
                    "description": "擁有這些身分組的成員可以處理票券",
                    "example": "/ticket_setting support_roles @客服 @管理員"
                },
                "limits": {
                    "name": "每人票券限制",
                    "current": f"{settings.get('max_tickets_per_user', 3)} 張",
                    "description": "每個用戶同時可以開啟的票券數量",
                    "example": "/ticket_setting limits 5"
                },
                "auto_close": {
                    "name": "自動關閉時間",
                    "current": f"{settings.get('auto_close_hours', 24)} 小時",
                    "description": "無活動票券將在此時間後自動關閉",
                    "example": "/ticket_setting auto_close 48"
                },
                "sla_response": {
                    "name": "SLA 回應時間",
                    "current": f"{settings.get('sla_response_minutes', 60)} 分鐘",
                    "description": "客服預期回應時間，用於 SLA 監控",
                    "example": "/ticket_setting sla_response 30"
                },
                "welcome": {
                    "name": "歡迎訊息",
                    "current": "已設定" if settings.get('welcome_message') else "使用預設",
                    "description": "票券建立時顯示的歡迎訊息",
                    "example": "/ticket_setting welcome 歡迎使用客服系統！"
                },
                "log_channel": {
                    "name": "日誌頻道",
                    "current": f"<#{settings['log_channel_id']}>" if settings.get('log_channel_id') else "未設定",
                    "description": "票券操作日誌將發送到此頻道",
                    "example": "/ticket_setting log_channel #票券日誌"
                }
            }
            
            if setting not in setting_info:
                await interaction.response.send_message(
                    f"❌ 未知的設定項目：{setting}", ephemeral=True
                )
                return
            
            info = setting_info[setting]
            
            embed = discord.Embed(
                title=f"⚙️ {info['name']} 設定",
                color=TicketConstants.COLORS['info']
            )
            
            embed.add_field(
                name="目前設定",
                value=info['current'],
                inline=False
            )
            
            embed.add_field(
                name="說明",
                value=info['description'],
                inline=False
            )
            
            embed.add_field(
                name="使用範例",
                value=f"`{info['example']}`",
                inline=False
            )
            
            await interaction.response.send_message(embed=embed, ephemeral=True)
            
        except Exception as e:
            logger.error(f"顯示特定設定錯誤：{e}")
            await interaction.response.send_message(
                "❌ 查詢設定失敗，請稍後再試。", ephemeral=True
            )
    
    async def _update_setting(self, interaction: discord.Interaction, 
                            setting: str, value: str) -> Tuple[bool, str]:
        """更新設定"""
        try:
            from bot.utils.validators import SettingsValidator
            
            # 驗證和處理不同類型的設定
            if setting == "category":
                # 驗證分類頻道
                result = SettingsValidator.validate_category_channel(interaction.guild, value)
                if not result.is_valid:
                    return False, result.error_message
                
                success = await self.repository.update_setting(
                    interaction.guild.id, 'category_id', result.cleaned_value
                )
                return success, "分類頻道設定成功" if success else "設定失敗"
                
            elif setting == "support_roles":
                # 驗證客服身分組
                result = SettingsValidator.validate_support_roles(interaction.guild, value)
                if not result.is_valid:
                    return False, result.error_message
                
                success = await self.repository.update_setting(
                    interaction.guild.id, 'support_roles', result.cleaned_value
                )
                return success, f"客服身分組設定成功，共 {len(result.cleaned_value)} 個身分組" if success else "設定失敗"
                
            elif setting == "limits":
                # 驗證票券限制
                result = SettingsValidator.validate_max_tickets(value)
                if not result.is_valid:
                    return False, result.error_message
                
                success = await self.repository.update_setting(
                    interaction.guild.id, 'max_tickets_per_user', result.cleaned_value
                )
                return success, f"每人票券限制設為 {result.cleaned_value} 張" if success else "設定失敗"
                
            elif setting == "auto_close":
                # 驗證自動關閉時間
                result = SettingsValidator.validate_auto_close_hours(value)
                if not result.is_valid:
                    return False, result.error_message
                
                success = await self.repository.update_setting(
                    interaction.guild.id, 'auto_close_hours', result.cleaned_value
                )
                return success, f"自動關閉時間設為 {result.cleaned_value} 小時" if success else "設定失敗"
                
            elif setting == "sla_response":
                # 驗證 SLA 時間
                result = SettingsValidator.validate_sla_minutes(value)
                if not result.is_valid:
                    return False, result.error_message
                
                success = await self.repository.update_setting(
                    interaction.guild.id, 'sla_response_minutes', result.cleaned_value
                )
                return success, f"SLA 回應時間設為 {result.cleaned_value} 分鐘" if success else "設定失敗"
                
            elif setting == "welcome":
                # 驗證歡迎訊息
                result = SettingsValidator.validate_welcome_message(value)
                if not result.is_valid:
                    return False, result.error_message
                
                success = await self.repository.update_setting(
                    interaction.guild.id, 'welcome_message', result.cleaned_value
                )
                return success, "歡迎訊息設定成功" if success else "設定失敗"
                
            elif setting == "log_channel":
                # 驗證日誌頻道
                result = SettingsValidator.validate_text_channel(interaction.guild, value)
                if not result.is_valid:
                    return False, result.error_message
                
                success = await self.repository.update_setting(
                    interaction.guild.id, 'log_channel_id', result.cleaned_value
                )
                return success, "日誌頻道設定成功" if success else "設定失敗"
                
            else:
                return False, f"未知的設定項目：{setting}"
                
        except Exception as e:
            logger.error(f"更新設定錯誤：{e}")
            return False, "設定更新過程發生錯誤"
    
    async def _show_rating_interface(self, channel: discord.TextChannel, ticket_id: int):
        """顯示評分界面"""
        try:
            from bot.ui.ticket_views import RatingView
            
            embed = discord.Embed(
                title="⭐ 服務評分",
                description=f"感謝您使用我們的客服系統！\n請為票券 #{ticket_id:04d} 的服務品質評分：",
                color=TicketConstants.COLORS['warning']
            )
            
            embed.add_field(
                name="💡 評分說明",
                value="• ⭐ 1星：非常不滿意\n"
                      "• ⭐⭐ 2星：不滿意\n"
                      "• ⭐⭐⭐ 3星：普通\n"
                      "• ⭐⭐⭐⭐ 4星：滿意\n"
                      "• ⭐⭐⭐⭐⭐ 5星：非常滿意",
                inline=False
            )
            
            view = RatingView(ticket_id)
            await channel.send(embed=embed, view=view)
            
        except Exception as e:
            logger.error(f"顯示評分界面錯誤：{e}")
    
    async def _schedule_channel_deletion(self, channel: discord.TextChannel, delay: int = 30):
        """安排頻道刪除"""
        try:
            await asyncio.sleep(delay)
            await channel.delete(reason="票券已關閉")
        except discord.NotFound:
            pass  # 頻道已被刪除
        except discord.Forbidden:
            logger.warning(f"沒有權限刪除頻道：{channel.name}")
        except Exception as e:
            logger.error(f"刪除頻道錯誤：{e}")
    
    async def _notify_assignment(self, user: discord.Member, ticket: Dict):
        """通知票券指派"""
        try:
            embed = discord.Embed(
                title="📋 票券指派通知",
                description=f"你被指派了票券 #{ticket['id']:04d}",
                color=TicketConstants.COLORS['info']
            )
            
            embed.add_field(
                name="票券資訊",
                value=f"**類型：** {ticket['type']}\n"
                      f"**優先級：** {TicketConstants.PRIORITY_EMOJIS.get(ticket.get('priority', 'medium'), '🟡')} {ticket.get('priority', 'medium').upper()}\n"
                      f"**創建者：** <@{ticket['discord_id']}>\n"
                      f"**頻道：** <#{ticket['channel_id']}>",
                inline=False
            )
            
            await user.send(embed=embed)
            
        except discord.Forbidden:
            logger.warning(f"無法向用戶 {user.id} 發送指派通知")
    
    async def _notify_high_priority(self, ticket: Dict, guild: discord.Guild, settings: Dict):
        """通知高優先級票券"""
        try:
            # 取得日誌頻道
            log_channel_id = settings.get('log_channel_id')
            if not log_channel_id:
                return
                
            log_channel = guild.get_channel(log_channel_id)
            if not log_channel:
                return
            
            embed = discord.Embed(
                title="🚨 高優先級票券警告",
                description=f"票券 #{ticket['id']:04d} 已設為高優先級",
                color=TicketConstants.PRIORITY_COLORS['high']
            )
            
            embed.add_field(
                name="票券資訊",
                value=f"**類型：** {ticket['type']}\n"
                      f"**創建者：** <@{ticket['discord_id']}>\n"
                      f"**頻道：** <#{ticket['channel_id']}>",
                inline=False
            )
            
            embed.add_field(
                name="⚠️ 注意事項",
                value="• 請優先處理此票券\n"
                      "• 預期回應時間已縮短至原來的一半\n"
                      "• 建議指派經驗豐富的客服人員",
                inline=False
            )
            
            # 提及客服身分組
            support_roles = settings.get('support_roles', [])
            mentions = []
            for role_id in support_roles:
                role = guild.get_role(role_id)
                if role:
                    mentions.append(role.mention)
            
            content = " ".join(mentions) if mentions else ""
            await log_channel.send(content=content, embed=embed)
            
        except Exception as e:
            logger.error(f"發送高優先級通知錯誤：{e}")
    
    async def _handle_guild_overdue_tickets(self, guild: discord.Guild, tickets: List[Dict]):
        """處理伺服器超時票券"""
        try:
            settings = await self.repository.get_settings(guild.id)
            log_channel_id = settings.get('log_channel_id')
            
            if not log_channel_id:
                return
                
            log_channel = guild.get_channel(log_channel_id)
            if not log_channel:
                return
            
            # 按優先級分組
            priority_groups = {'high': [], 'medium': [], 'low': []}
            for ticket in tickets:
                priority = ticket.get('priority', 'medium')
                if priority in priority_groups:
                    priority_groups[priority].append(ticket)
            
            # 建立超時警告嵌入
            embed = discord.Embed(
                title="⚠️ SLA 超時警告",
                description=f"發現 {len(tickets)} 張票券超過預期回應時間",
                color=discord.Color.red()
            )
            
            # 顯示各優先級超時票券
            for priority, priority_tickets in priority_groups.items():
                if not priority_tickets:
                    continue
                    
                emoji = TicketConstants.PRIORITY_EMOJIS.get(priority, '🟡')
                ticket_list = []
                
                for ticket in priority_tickets[:5]:  # 最多顯示5張
                    overdue_time = self._calculate_overdue_time(ticket, settings)
                    ticket_list.append(
                        f"#{ticket['id']:04d} - {ticket['type']} "
                        f"(超時 {overdue_time:.0f} 分鐘)"
                    )
                
                if len(priority_tickets) > 5:
                    ticket_list.append(f"... 還有 {len(priority_tickets) - 5} 張")
                
                embed.add_field(
                    name=f"{emoji} {priority.upper()} 優先級 ({len(priority_tickets)} 張)",
                    value="\n".join(ticket_list),
                    inline=False
                )
            
            # 提及客服身分組
            support_roles = settings.get('support_roles', [])
            mentions = []
            for role_id in support_roles:
                role = guild.get_role(role_id)
                if role:
                    mentions.append(role.mention)
            
            content = " ".join(mentions) if mentions else ""
            
            embed.add_field(
                name="📋 建議行動",
                value="• 請優先處理高優先級票券\n"
                      "• 檢查客服人員配置\n"
                      "• 考慮調整 SLA 時間設定",
                inline=False
            )
            
            await log_channel.send(content=content, embed=embed)
            
        except Exception as e:
            logger.error(f"處理伺服器超時票券錯誤：{e}")
    
    def _calculate_overdue_time(self, ticket: Dict, settings: Dict) -> float:
        """計算超時時間（分鐘）"""
        try:
            now = datetime.now(timezone.utc)
            created_at = ticket['created_at']
            
            # 計算已過時間
            elapsed_minutes = (now - created_at).total_seconds() / 60
            
            # 計算目標時間
            base_sla = settings.get('sla_response_minutes', 60)
            priority = ticket.get('priority', 'medium')
            multiplier = TicketConstants.SLA_MULTIPLIERS.get(priority, 1.0)
            target_minutes = base_sla * multiplier
            
            return max(0, elapsed_minutes - target_minutes)
            
        except Exception as e:
            logger.error(f"計算超時時間錯誤：{e}")
            return 0
    
    async def _auto_close_inactive_tickets(self, guild_id: int, hours_threshold: int) -> int:
        """自動關閉無活動票券"""
        try:
            cutoff_time = datetime.now(timezone.utc) - timedelta(hours=hours_threshold)
            
            # 取得無活動票券
            inactive_tickets = await self.repository.get_inactive_tickets(guild_id, cutoff_time)
            
            closed_count = 0
            
            for ticket in inactive_tickets:
                try:
                    # 關閉票券
                    success = await self.manager.close_ticket(
                        ticket_id=ticket['id'],
                        closed_by=0,  # 系統關閉
                        reason=f"自動關閉：無活動超過 {hours_threshold} 小時"
                    )
                    
                    if success:
                        closed_count += 1
                        
                        # 通知用戶
                        try:
                            guild = self.bot.get_guild(guild_id)
                            user = guild.get_member(int(ticket['discord_id'])) if guild else None
                            
                            if user:
                                embed = discord.Embed(
                                    title="🔒 票券自動關閉",
                                    description=f"您的票券 #{ticket['id']:04d} 因無活動超過 {hours_threshold} 小時已自動關閉。",
                                    color=TicketConstants.COLORS['warning']
                                )
                                
                                embed.add_field(
                                    name="票券資訊",
                                    value=f"**類型：** {ticket['type']}\n"
                                          f"**建立時間：** {get_time_ago(ticket['created_at'])}",
                                    inline=False
                                )
                                
                                embed.add_field(
                                    name="💡 提醒",
                                    value="如果您還需要幫助，可以重新建立票券。",
                                    inline=False
                                )
                                
                                await user.send(embed=embed)
                        except:
                            pass  # 通知失敗不影響關閉流程
                        
                        # 刪除頻道
                        try:
                            guild = self.bot.get_guild(guild_id)
                            if guild:
                                channel = guild.get_channel(ticket['channel_id'])
                                if channel:
                                    await channel.delete(reason="票券自動關閉")
                        except:
                            pass
                            
                except Exception as e:
                    logger.error(f"自動關閉票券 #{ticket['id']:04d} 錯誤：{e}")
                    continue
            
            return closed_count
            
        except Exception as e:
            logger.error(f"自動關閉無活動票券錯誤：{e}")
            return 0


async def setup(bot: commands.Bot):
    """載入 Cog"""
    await bot.add_cog(TicketCore(bot))
    logger.info("✅ 票券核心系統已載入")