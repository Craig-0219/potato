# bot/cogs/ticket.py - v7.0 修復版
# 🎫 Discord Ticket System - 主控制器

import discord
from discord.ext import commands, tasks
from discord import app_commands
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Any, Tuple
import asyncio

# 內部模組導入
from bot.db.ticket_dao import TicketDAO
from bot.utils.ticket_utils import (
    TicketPermissionChecker, build_ticket_embed, build_stats_embed,
    format_duration, parse_channel_mention,
    parse_role_mention, format_settings_value, TicketCache
)
from bot.utils.ticket_constants import (
    TicketConstants, get_priority_emoji, get_status_emoji,
    get_priority_color, calculate_sla_time, ERROR_MESSAGES, SUCCESS_MESSAGES
)
from bot.utils.debug import debug_log


class TicketSystem(commands.Cog):
    """Discord 票券系統主控制器"""
    
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.dao = TicketDAO()
        
        # 系統組件
        self.permission_checker = TicketPermissionChecker()
        self.cache = TicketCache(timeout_minutes=5)
        
        # 任務管理
        self._tasks = {}
        
        # 啟動後台任務
        self.sla_monitor.start()
        
    def cog_unload(self):
        """清理資源"""
        self.sla_monitor.cancel()
        self.cache.clear()
        for task in self._tasks.values():
            if not task.done():
                task.cancel()

    # ===== 核心設定管理 =====
    
    async def get_guild_settings(self, guild_id: int) -> Dict[str, Any]:
        """取得伺服器設定（含快取）"""
        cache_key = f"settings_{guild_id}"
        
        # 檢查快取
        cached_settings = self.cache.get(cache_key)
        if cached_settings:
            return cached_settings
        
        # 從資料庫取得
        settings = await self.dao.get_guild_settings(guild_id)
        if not settings:
            settings = await self.dao.create_default_settings(guild_id)
        
        # 快取設定
        self.cache.set(cache_key, settings)
        return settings

    async def clear_settings_cache(self, guild_id: int):
        """清除設定快取"""
        cache_key = f"settings_{guild_id}"
        self.cache.delete(cache_key)

    def check_permissions(self, user: discord.Member, settings: Dict[str, Any]) -> Dict[str, bool]:
        """檢查用戶權限"""
        support_roles = settings.get('support_roles', [])
        
        return {
            'is_admin': self.permission_checker.is_admin(user),
            'is_support': self.permission_checker.is_support_staff(user, support_roles),
            'can_manage': self.permission_checker.is_support_staff(user, support_roles)
        }

    # ===== 基礎票券指令 =====
    
    @commands.command(name="setup_ticket")
    @commands.has_permissions(manage_guild=True)
    async def setup_ticket(self, ctx: commands.Context):
        """建立票券互動面板"""
        try:
            settings = await self.get_guild_settings(ctx.guild.id)
            
            embed = discord.Embed(
                title="🎫 客服中心",
                description=settings.get('welcome_message', "請選擇你的問題類型，我們會為你建立專屬頻道。"),
                color=discord.Color.green()
            )
            
            # 添加系統資訊
            embed.add_field(
                name="📋 系統資訊", 
                value=f"• 每人限制：{settings.get('max_tickets_per_user', 3)} 張票券\n"
                      f"• 自動關閉：{settings.get('auto_close_hours', 24)} 小時無活動\n"
                      f"• 目標回覆：{settings.get('sla_response_minutes', 60)} 分鐘內\n"
                      f"• 自動分配：{'啟用' if settings.get('auto_assign_enabled') else '停用'}",
                inline=False
            )

            # 暫時使用基礎視圖，後續會在 views 文件中完善
            from bot.views.ticket_views import TicketView
            view = TicketView(settings)
            await ctx.send(embed=embed, view=view)
            
            debug_log(f"[Ticket] {ctx.author} 在 {ctx.guild.name} 建立了票券面板")
            
        except Exception as e:
            await self._handle_error(ctx, "建立票券面板時發生錯誤", e)

    @app_commands.command(name="close", description="關閉票券")
    @app_commands.describe(
        reason="關閉原因（可選）",
        request_rating="是否要求用戶評分（預設：是）"
    )
    async def close_ticket(self, interaction: discord.Interaction, reason: str = None, request_rating: bool = True):
        """關閉票券指令"""
        try:
            # 驗證票券頻道
            validation_result = await self._validate_ticket_channel(interaction)
            if not validation_result:
                return
                
            ticket_info, settings = validation_result
            
            # 檢查關閉權限
            permissions = self.check_permissions(interaction.user, settings)
            can_close = (
                str(interaction.user.id) == ticket_info['discord_id'] or 
                permissions['can_manage']
            )
            
            if not can_close:
                await interaction.response.send_message(
                    "❌ 只有票券創建者或客服人員可以關閉票券。", 
                    ephemeral=True
                )
                return

            # 執行關閉流程
            await self._execute_ticket_closure(interaction, ticket_info, reason, request_rating)
            
        except Exception as e:
            await self._handle_interaction_error(interaction, "關閉票券時發生錯誤", e)

    @app_commands.command(name="ticket_info", description="查詢票券詳細資訊")
    @app_commands.describe(ticket_id="票券編號")
    async def ticket_info(self, interaction: discord.Interaction, ticket_id: int):
        """查詢票券資訊"""
        try:
            # 取得票券資料
            ticket = await self.dao.get_ticket_by_id(ticket_id)
            if not ticket:
                await interaction.response.send_message("❌ 找不到此票券 ID。", ephemeral=True)
                return

            # 權限檢查
            settings = await self.get_guild_settings(interaction.guild.id)
            permissions = self.check_permissions(interaction.user, settings)
            
            can_view = (
                str(interaction.user.id) == ticket['discord_id'] or 
                permissions['can_manage']
            )
            
            if not can_view:
                await interaction.response.send_message("❌ 你只能查看自己的票券。", ephemeral=True)
                return

            # 建立資訊顯示
            embed = await self._build_detailed_ticket_info(ticket, interaction.guild)
            
            # 記錄查看
            await self.dao.record_ticket_view(ticket_id, interaction.user.id)
            
            await interaction.response.send_message(embed=embed, ephemeral=True)
            
        except Exception as e:
            await self._handle_interaction_error(interaction, "查詢票券資訊時發生錯誤", e)

    @app_commands.command(name="tickets", description="查詢票券列表")
    @app_commands.describe(
        status="篩選狀態：all/open/closed/archived",
        user="指定用戶（客服限定）",
        priority="篩選優先級：high/medium/low"
    )
    async def tickets(self, interaction: discord.Interaction, 
                     status: str = "all", 
                     user: discord.Member = None, 
                     priority: str = None):
        """分頁查詢票券"""
        try:
            settings = await self.get_guild_settings(interaction.guild.id)
            permissions = self.check_permissions(interaction.user, settings)
            
            # 權限檢查
            if user and not permissions['can_manage']:
                await interaction.response.send_message("❌ 只有客服人員可以查詢其他用戶的票券。", ephemeral=True)
                return
            
            # 確定查詢範圍
            target_user_id = self._determine_query_scope(interaction.user, user, permissions)
            
            # 執行查詢
            tickets, total = await self.dao.paginate_tickets(
                user_id=target_user_id,
                status=status,
                page=1,
                page_size=5,
                guild_id=interaction.guild.id,
                priority=priority
            )
            
            if not tickets:
                target_name = self._get_target_name(user, target_user_id, permissions)
                await interaction.response.send_message(f"📭 {target_name}沒有找到符合條件的票券。", ephemeral=True)
                return

            # 建立簡化的嵌入顯示（後續會用 PaginationView 替換）
            embed = self._build_tickets_list_embed(tickets, status, priority, user)
            await interaction.response.send_message(embed=embed, ephemeral=True)
            
        except Exception as e:
            await self._handle_interaction_error(interaction, "查詢票券列表時發生錯誤", e)

    # ===== 管理員指令 =====
    
    @app_commands.command(name="ticket_admin", description="票券管理員面板")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def ticket_admin(self, interaction: discord.Interaction):
        """管理員控制面板"""
        try:
            # 取得統計資料
            stats = await self.dao.get_server_statistics(interaction.guild.id)
            
            # 建立管理面板
            embed = build_stats_embed(stats, "🛠️ 票券系統管理面板", discord.Color.orange())
            
            # 添加快速操作提示
            embed.add_field(
                name="⚡ 快速操作",
                value="• `/ticket_setting` - 系統設定\n"
                      "• `/sla_dashboard` - SLA 監控\n"
                      "• `/staff_stats` - 客服統計\n"
                      "• `/ticket_batch` - 批次操作",
                inline=False
            )
            
            await interaction.response.send_message(embed=embed, ephemeral=True)
            
        except Exception as e:
            await self._handle_interaction_error(interaction, "載入管理面板時發生錯誤", e)

    @app_commands.command(name="ticket_priority", description="設定票券優先級")
    @app_commands.describe(
        priority="優先級：high/medium/low",
        ticket_id="票券編號（可選，預設為當前頻道）"
    )
    async def ticket_priority(self, interaction: discord.Interaction, priority: str, ticket_id: int = None):
        """設定票券優先級"""
        try:
            # 驗證優先級
            if priority not in TicketConstants.PRIORITIES:
                valid_priorities = ", ".join(TicketConstants.PRIORITIES)
                await interaction.response.send_message(
                    f"❌ 優先級必須是：{valid_priorities}", 
                    ephemeral=True
                )
                return
            
            # 權限檢查
            settings = await self.get_guild_settings(interaction.guild.id)
            permissions = self.check_permissions(interaction.user, settings)
            
            if not permissions['can_manage']:
                await interaction.response.send_message(ERROR_MESSAGES['no_permission'], ephemeral=True)
                return
            
            # 確定票券 ID
            resolved_ticket_id = await self._resolve_ticket_id(interaction, ticket_id)
            if not resolved_ticket_id:
                return
            
            # 更新優先級
            success = await self.dao.update_ticket_priority(resolved_ticket_id, priority, interaction.user.id)
            if success:
                priority_emoji = get_priority_emoji(priority)
                await interaction.response.send_message(
                    f"✅ 票券 #{resolved_ticket_id:04d} 優先級已設為：{priority_emoji} **{priority.upper()}**"
                )
                
                # 記錄操作到日誌頻道
                await self._log_ticket_action(
                    interaction.guild, resolved_ticket_id, "優先級變更",
                    f"{interaction.user.mention} 設定為 {priority_emoji} {priority.upper()}"
                )
            else:
                await interaction.response.send_message(ERROR_MESSAGES['database_error'], ephemeral=True)
                
        except Exception as e:
            await self._handle_interaction_error(interaction, "設定優先級時發生錯誤", e)

    @app_commands.command(name="ticket_assign", description="指派票券給客服人員")
    @app_commands.describe(
        user="要指派的客服人員",
        ticket_id="票券編號（可選，預設為當前頻道）"
    )
    async def ticket_assign(self, interaction: discord.Interaction, user: discord.Member, ticket_id: int = None):
        """指派票券"""
        try:
            settings = await self.get_guild_settings(interaction.guild.id)
            permissions = self.check_permissions(interaction.user, settings)
            
            # 權限檢查
            if not permissions['can_manage']:
                await interaction.response.send_message(ERROR_MESSAGES['no_permission'], ephemeral=True)
                return
            
            # 檢查被指派者權限
            target_permissions = self.check_permissions(user, settings)
            if not target_permissions['can_manage']:
                await interaction.response.send_message("❌ 只能指派給客服人員。", ephemeral=True)
                return
            
            # 執行指派
            resolved_ticket_id = await self._resolve_ticket_id(interaction, ticket_id)
            if not resolved_ticket_id:
                return
            
            await self._execute_ticket_assignment(interaction, resolved_ticket_id, user)
            
        except Exception as e:
            await self._handle_interaction_error(interaction, "指派票券時發生錯誤", e)

    # ===== 系統設定指令 =====
    
    @app_commands.command(name="ticket_setting", description="票券系統設定")
    @app_commands.describe(
        setting="設定項目",
        value="設定值（留空顯示當前設定）"
    )
    @app_commands.checks.has_permissions(manage_guild=True)
    async def ticket_setting(self, interaction: discord.Interaction, setting: str = None, value: str = None):
        """系統設定管理"""
        try:
            if not setting:
                # 顯示所有設定
                await self._show_all_settings(interaction)
                return
            
            if not value:
                # 顯示特定設定
                await self._show_specific_setting(interaction, setting)
                return
            
            # 更新設定
            await self._update_setting(interaction, setting, value)
            
        except Exception as e:
            await self._handle_interaction_error(interaction, "設定系統時發生錯誤", e)

    @app_commands.command(name="sla_dashboard", description="SLA 監控面板")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def sla_dashboard(self, interaction: discord.Interaction):
        """SLA 監控面板"""
        try:
            await interaction.response.defer()
            
            stats = await self.dao.get_sla_statistics(interaction.guild.id)
            embed = self._build_sla_dashboard_embed(stats)
            
            await interaction.followup.send(embed=embed)
            
        except Exception as e:
            await self._handle_interaction_error(interaction, "載入 SLA 面板時發生錯誤", e)

    @app_commands.command(name="staff_stats", description="客服人員工作統計")
    @app_commands.describe(
        period="統計期間：today/week/month",
        user="指定客服人員（可選）"
    )
    @app_commands.checks.has_permissions(manage_guild=True)
    async def staff_stats(self, interaction: discord.Interaction, period: str = "week", user: discord.Member = None):
        """客服統計"""
        try:
            await interaction.response.defer()
            
            stats = await self.dao.get_staff_workload_stats(
                interaction.guild.id, period, user.id if user else None
            )
            
            embed = self._build_staff_stats_embed(stats, period, user, interaction.guild)
            await interaction.followup.send(embed=embed)
            
        except Exception as e:
            await self._handle_interaction_error(interaction, "載入客服統計時發生錯誤", e)

    # ===== 搜尋和評分指令 =====
    
    @app_commands.command(name="ticket_search", description="搜尋票券")
    @app_commands.describe(
        keyword="搜尋關鍵字",
        search_type="搜尋類型：content"
    )
    async def ticket_search(self, interaction: discord.Interaction, keyword: str, search_type: str = "content"):
        """搜尋票券"""
        try:
            if len(keyword.strip()) < 2:
                await interaction.response.send_message("❌ 搜尋關鍵字至少需要2個字元。", ephemeral=True)
                return
            
            await interaction.response.defer(ephemeral=True)
            
            # 權限檢查
            settings = await self.get_guild_settings(interaction.guild.id)
            permissions = self.check_permissions(interaction.user, settings)
            
            # 執行搜尋
            results = await self.dao.search_tickets_by_content(interaction.guild.id, keyword)
            
            # 權限過濾
            if not permissions['can_manage']:
                results = [r for r in results if str(r.get('discord_id')) == str(interaction.user.id)]
            
            if not results:
                await interaction.followup.send(f"🔍 沒有找到包含「{keyword}」的票券。")
                return
            
            # 建立結果顯示
            embed = self._build_search_results_embed(results, keyword)
            await interaction.followup.send(embed=embed)
            
        except Exception as e:
            await self._handle_interaction_error(interaction, "搜尋時發生錯誤", e)

    @app_commands.command(name="ticket_rating", description="為票券評分")
    @app_commands.describe(
        ticket_id="票券編號",
        rating="評分 (1-5星)",
        feedback="意見回饋（可選）"
    )
    async def ticket_rating(self, interaction: discord.Interaction, ticket_id: int, rating: int, feedback: str = None):
        """票券評分系統"""
        try:
            # 驗證評分
            if not (1 <= rating <= 5):
                await interaction.response.send_message("❌ 評分必須在 1-5 之間。", ephemeral=True)
                return
            
            # 取得票券資訊
            ticket = await self.dao.get_ticket_by_id(ticket_id)
            if not ticket:
                await interaction.response.send_message(ERROR_MESSAGES['ticket_not_found'], ephemeral=True)
                return
            
            # 權限檢查
            if str(interaction.user.id) != ticket['discord_id']:
                await interaction.response.send_message("❌ 只有票券創建者可以評分。", ephemeral=True)
                return
            
            # 狀態檢查
            if ticket['status'] != 'closed':
                await interaction.response.send_message("❌ 只能為已關閉的票券評分。", ephemeral=True)
                return
            
            # 重複評分檢查
            if ticket.get('rating'):
                await interaction.response.send_message(ERROR_MESSAGES['already_rated'], ephemeral=True)
                return
            
            # 保存評分
            success = await self.dao.save_ticket_rating(ticket_id, rating, feedback)
            if success:
                stars = TicketConstants.RATING_EMOJIS.get(rating, "⭐")
                embed = discord.Embed(
                    title="⭐ 評分已保存",
                    description=f"感謝你為票券 #{ticket_id:04d} 評分！",
                    color=discord.Color.gold()
                )
                embed.add_field(name="評分", value=f"{stars} ({rating}/5)", inline=True)
                if feedback:
                    embed.add_field(name="意見回饋", value=feedback, inline=False)
                
                await interaction.response.send_message(embed=embed)
                
                # 通知被指派的客服
                if ticket.get('assigned_to'):
                    assignee = interaction.guild.get_member(int(ticket['assigned_to']))
                    if assignee:
                        try:
                            await assignee.send(f"⭐ 你處理的票券 #{ticket_id:04d} 收到了 {rating} 星評價！")
                        except discord.Forbidden:
                            pass
                
                # 記錄操作
                await self._log_ticket_action(
                    interaction.guild, ticket_id, "用戶評分",
                    f"{interaction.user.mention} 給予 {stars} ({rating}/5) 評分"
                )
            else:
                await interaction.response.send_message(ERROR_MESSAGES['database_error'], ephemeral=True)
                
        except Exception as e:
            await self._handle_interaction_error(interaction, "評分時發生錯誤", e)

    # ===== 後台任務 =====
    
    @tasks.loop(minutes=5)
    async def sla_monitor(self):
        """SLA 監控任務"""
        try:
            overdue_tickets = await self.dao.get_overdue_tickets()
            
            for ticket in overdue_tickets:
                await self._process_overdue_ticket(ticket)
                
        except Exception as e:
            debug_log(f"[Ticket] SLA 監控錯誤：{e}")

    async def _process_overdue_ticket(self, ticket: Dict[str, Any]):
        """處理超時票券"""
        try:
            guild = self.bot.get_guild(ticket['guild_id'])
            if not guild:
                return
            
            settings = await self.get_guild_settings(guild.id)
            await self._send_sla_alert(guild, ticket, settings)
            
            # 標記已警告
            await self.dao.mark_sla_warned(ticket['ticket_id'])
            
        except Exception as e:
            debug_log(f"[Ticket] 處理超時票券錯誤：{e}")

    # ===== 私有輔助方法 =====
    
    async def _validate_ticket_channel(self, interaction: discord.Interaction) -> Optional[Tuple[Dict, Dict]]:
        """驗證票券頻道並返回票券資訊和設定"""
        if not interaction.channel.name.startswith("ticket-"):
            await interaction.response.send_message(ERROR_MESSAGES['not_ticket_channel'], ephemeral=True)
            return None
        
        ticket_info = await self.dao.get_ticket_by_channel(interaction.channel.id)
        if not ticket_info:
            await interaction.response.send_message(ERROR_MESSAGES['ticket_not_found'], ephemeral=True)
            return None
        
        settings = await self.get_guild_settings(interaction.guild.id)
        return ticket_info, settings

    async def _resolve_ticket_id(self, interaction: discord.Interaction, ticket_id: int = None) -> Optional[int]:
        """解析票券 ID"""
        if ticket_id is not None:
            return ticket_id
        
        # 從當前頻道解析
        if not interaction.channel.name.startswith("ticket-"):
            await interaction.response.send_message(ERROR_MESSAGES['not_ticket_channel'], ephemeral=True)
            return None
        
        ticket_info = await self.dao.get_ticket_by_channel(interaction.channel.id)
        if not ticket_info:
            await interaction.response.send_message(ERROR_MESSAGES['ticket_not_found'], ephemeral=True)
            return None
        
        return ticket_info['ticket_id']

    def _determine_query_scope(self, user: discord.Member, target_user: discord.Member, permissions: Dict[str, bool]) -> Optional[str]:
        """確定查詢範圍"""
        if target_user:  # 客服指定查詢用戶
            return str(target_user.id)
        elif not permissions['can_manage']:  # 一般用戶只能查自己的
            return str(user.id)
        return None  # 客服查詢全部

    def _get_target_name(self, user: discord.Member, target_user_id: str, permissions: Dict[str, bool]) -> str:
        """取得目標名稱"""
        if user:
            return f"{user.display_name} "
        elif target_user_id:
            return "你"
        elif permissions['can_manage']:
            return "伺服器"
        return ""

    async def _execute_ticket_closure(self, interaction: discord.Interaction, 
                                    ticket_info: Dict, reason: str, request_rating: bool):
        """執行票券關閉流程"""
        # 簡化版關閉確認
        embed = discord.Embed(
            title="🛑 確認關閉票券",
            description=f"確定要關閉票券 #{ticket_info['ticket_id']:04d}？",
            color=discord.Color.red()
        )
        
        if reason:
            embed.add_field(name="關閉原因", value=reason, inline=False)
        
        # 創建確認按鈕視圖（簡化版）
        view = discord.ui.View(timeout=60)
        
        async def confirm_callback(button_interaction):
            # 執行關閉
            success = await self.dao.close_ticket(
                interaction.channel.id, 
                str(interaction.user.id), 
                reason
            )
            
            if success:
                await button_interaction.response.send_message("✅ 票券已關閉。", ephemeral=True)
                
                # 記錄操作
                await self._log_ticket_action(
                    interaction.guild, ticket_info['ticket_id'], "票券關閉",
                    f"{interaction.user.mention} 關閉了票券"
                )
            else:
                await button_interaction.response.send_message("❌ 關閉票券失敗。", ephemeral=True)
        
        confirm_button = discord.ui.Button(label="確認關閉", style=discord.ButtonStyle.danger)
        confirm_button.callback = confirm_callback
        view.add_item(confirm_button)
        
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    async def _execute_ticket_assignment(self, interaction: discord.Interaction, ticket_id: int, user: discord.Member):
        """執行票券指派"""
        success = await self.dao.assign_ticket(ticket_id, user.id, interaction.user.id)
        
        if success:
            embed = discord.Embed(
                title="👥 票券已指派",
                description=f"票券 #{ticket_id:04d} 已指派給 {user.mention}",
                color=discord.Color.blue()
            )
            embed.add_field(name="指派者", value=interaction.user.mention, inline=True)
            embed.add_field(name="被指派者", value=user.mention, inline=True)
            embed.add_field(name="時間", value=f"<t:{int(datetime.now(timezone.utc).timestamp())}:F>", inline=False)
            
            await interaction.response.send_message(embed=embed)
            
            # 通知被指派者
            try:
                await user.send(f"📋 你被指派了票券：#{ticket_id:04d}")
            except discord.Forbidden:
                pass
            
            # 記錄操作
            await self._log_ticket_action(
                interaction.guild, ticket_id, "票券指派",
                f"{interaction.user.mention} 指派給 {user.mention}"
            )
        else:
            await interaction.response.send_message("❌ 指派票券失敗。", ephemeral=True)

    async def _build_detailed_ticket_info(self, ticket: Dict, guild: discord.Guild) -> discord.Embed:
        """建立詳細票券資訊"""
        embed = build_ticket_embed(ticket, include_stats=True)
        
        # 添加 SLA 資訊
        sla_info = await self.dao.get_ticket_sla_info(ticket['ticket_id'])
        if sla_info:
            sla_status = "✅ 達標" if sla_info['met_sla'] else "❌ 超時"
            embed.add_field(
                name="📈 SLA 資訊",
                value=f"🎯 首次回應：{sla_info['first_response_time']:.1f} 分鐘\n📊 SLA 狀態：{sla_status}",
                inline=True
            )
        
        return embed

    def _build_tickets_list_embed(self, tickets: List[Dict], status: str, priority: str, user: discord.Member) -> discord.Embed:
        """建立票券列表嵌入"""
        embed = discord.Embed(
            title="🎫 票券列表",
            color=discord.Color.blue()
        )
        
        # 篩選條件
        filters = []
        if status != "all":
            filters.append(f"狀態: {status}")
        if priority:
            filters.append(f"優先級: {priority}")
        if user:
            filters.append(f"用戶: {user.display_name}")
        
        if filters:
            embed.description = f"篩選條件：{' | '.join(filters)}"
        
        # 顯示票券
        for ticket in tickets[:10]:  # 限制顯示10筆
            status_emoji = get_status_emoji(ticket['status'])
            priority_emoji = get_priority_emoji(ticket.get('priority', 'medium'))
            
            field_value = f"{status_emoji} {ticket['status'].upper()} {priority_emoji}\n"
            field_value += f"👤 <@{ticket['discord_id']}>\n"
            field_value += f"📅 <t:{int(ticket['created_at'].timestamp())}:R>"
            
            if ticket.get('rating'):
                stars = TicketConstants.RATING_EMOJIS.get(ticket['rating'], "⭐")
                field_value += f"\n{stars}"
            
            embed.add_field(
                name=f"#{ticket['ticket_id']:04d} - {ticket['type']}",
                value=field_value,
                inline=True
            )
        
        embed.set_footer(text=f"顯示 {len(tickets)} 筆結果")
        return embed

    def _build_search_results_embed(self, results: List[Dict], keyword: str) -> discord.Embed:
        """建立搜尋結果嵌入"""
        embed = discord.Embed(
            title=f"🔍 搜尋結果：「{keyword}」",
            color=discord.Color.gold()
        )
        embed.set_footer(text=f"找到 {len(results)} 筆符合的票券")
        
        for ticket in results[:10]:  # 限制顯示10筆
            status_emoji = get_status_emoji(ticket['status'])
            priority_emoji = get_priority_emoji(ticket.get('priority', 'medium'))
            
            field_value = f"{status_emoji} {ticket['status'].upper()} {priority_emoji}\n"
            field_value += f"👤 <@{ticket['discord_id']}>\n"
            field_value += f"📅 <t:{int(ticket['created_at'].timestamp())}:R>"
            
            embed.add_field(
                name=f"#{ticket['ticket_id']:04d} - {ticket['type']}",
                value=field_value,
                inline=True
            )
        
        if len(results) > 10:
            embed.add_field(
                name="📋 更多結果",
                value=f"還有 {len(results) - 10} 筆結果未顯示",
                inline=False
            )
        
        return embed

    # ===== 設定管理方法 =====
    
    async def _show_all_settings(self, interaction: discord.Interaction):
        """顯示所有設定"""
        settings = await self.get_guild_settings(interaction.guild.id)
        
        embed = discord.Embed(
            title="⚙️ 票券系統設定",
            color=discord.Color.blue()
        )
        
        # 基本設定
        embed.add_field(
            name="🎫 基本設定",
            value=f"分類頻道：{self._format_channel_setting(interaction.guild, settings.get('category_id'))}\n"
                  f"客服身分組：{self._format_roles_setting(interaction.guild, settings.get('support_roles', []))}\n"
                  f"每人限制：{settings.get('max_tickets_per_user', 3)} 張",
            inline=False
        )
        
        # 自動化設定
        embed.add_field(
            name="🤖 自動化設定",
            value=f"自動關閉：{settings.get('auto_close_hours', 24)} 小時\n"
                  f"SLA 時間：{settings.get('sla_response_minutes', 60)} 分鐘\n"
                  f"自動分配：{'啟用' if settings.get('auto_assign_enabled') else '停用'}",
            inline=False
        )
        
        # 日誌設定
        embed.add_field(
            name="📝 日誌設定",
            value=f"日誌頻道：{self._format_channel_setting(interaction.guild, settings.get('log_channel_id'))}\n"
                  f"SLA 警告頻道：{self._format_channel_setting(interaction.guild, settings.get('sla_alert_channel_id'))}",
            inline=False
        )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)

    async def _show_specific_setting(self, interaction: discord.Interaction, setting: str):
        """顯示特定設定"""
        try:
            settings = await self.get_guild_settings(interaction.guild.id)
            
            # 設定映射
            setting_map = {
                'category': ('category_id', '分類頻道'),
                'support_roles': ('support_roles', '客服身分組'),
                'limits': ('max_tickets_per_user', '每人票券限制'),
                'auto_close': ('auto_close_hours', '自動關閉時間'),
                'sla_response': ('sla_response_minutes', 'SLA 回應時間'),
                'auto_assign': ('auto_assign_enabled', '自動分配'),
                'welcome': ('welcome_message', '歡迎訊息'),
                'log_channel': ('log_channel_id', '日誌頻道'),
                'sla_alert_channel': ('sla_alert_channel_id', 'SLA 警告頻道')
            }
            
            if setting not in setting_map:
                available_settings = ", ".join(setting_map.keys())
                await interaction.response.send_message(
                    f"❌ 無效設定項目。可用項目：{available_settings}", 
                    ephemeral=True
                )
                return
            
            db_field, display_name = setting_map[setting]
            current_value = settings.get(db_field)
            
            embed = discord.Embed(
                title=f"⚙️ 設定：{display_name}",
                color=discord.Color.blue()
            )
            
            formatted_value = format_settings_value(db_field, current_value, interaction.guild)
            embed.add_field(name="當前值", value=formatted_value, inline=False)
            
            await interaction.response.send_message(embed=embed, ephemeral=True)
            
        except Exception as e:
            await self._handle_interaction_error(interaction, "查詢設定時發生錯誤", e)

    async def _update_setting(self, interaction: discord.Interaction, setting: str, value: str):
        """更新設定"""
        # 設定映射
        setting_map = {
            'category': 'category_id',
            'support_roles': 'support_roles',
            'limits': 'max_tickets_per_user',
            'auto_close': 'auto_close_hours',
            'sla_response': 'sla_response_minutes',
            'auto_assign': 'auto_assign_enabled',
            'welcome': 'welcome_message',
            'log_channel': 'log_channel_id',
            'sla_alert_channel': 'sla_alert_channel_id'
        }
        
        if setting not in setting_map:
            available_settings = ", ".join(setting_map.keys())
            await interaction.response.send_message(
                f"❌ 無效設定項目。可用項目：{available_settings}", 
                ephemeral=True
            )
            return
        
        # 處理設定值
        processed_value = await self._process_setting_value(setting, value, interaction.guild)
        if processed_value is None:
            await interaction.response.send_message(f"❌ 無效的設定值：{value}", ephemeral=True)
            return
        
        # 更新資料庫
        db_field = setting_map[setting]
        success = await self.dao.update_guild_setting(interaction.guild.id, db_field, processed_value)
        
        if success:
            await self.clear_settings_cache(interaction.guild.id)
            await interaction.response.send_message(f"✅ 設定 `{setting}` 已更新為：{value}")
        else:
            await interaction.response.send_message("❌ 更新設定失敗", ephemeral=True)

    async def _process_setting_value(self, setting: str, value: str, guild: discord.Guild) -> Any:
        """處理設定值"""
        try:
            if setting in ['category', 'log_channel', 'sla_alert_channel']:
                channel = parse_channel_mention(value, guild)
                return channel.id if channel else None
            
            elif setting == 'support_roles':
                role_ids = []
                for role_str in value.split(','):
                    role = parse_role_mention(role_str.strip(), guild)
                    if role:
                        role_ids.append(role.id)
                return role_ids
            
            elif setting in ['limits', 'auto_close', 'sla_response']:
                return int(value)
            
            elif setting == 'auto_assign':
                return value.lower() in ['true', '1', 'yes', 'on', '啟用']
            
            elif setting == 'welcome':
                return value
            
        except (ValueError, AttributeError):
            return None
        
        return None

    # ===== 統計面板建立方法 =====
    
    def _build_sla_dashboard_embed(self, stats: Dict[str, Any]) -> discord.Embed:
        """建立 SLA 監控面板"""
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
            value=f"總票券：{total_tickets}\n"
                  f"已回應：{responded_tickets}\n"
                  f"達標：{stats.get('met_sla', 0)} ({sla_rate:.1f}%)\n"
                  f"超時：{stats.get('missed_sla', 0)}\n"
                  f"平均回應：{stats.get('avg_response_time', 0):.1f} 分鐘",
            inline=True
        )
        
        # 當前超時
        embed.add_field(
            name="⚠️ 當前超時",
            value=f"🔴 高優先級：{stats.get('overdue_high', 0)}\n"
                  f"🟡 中優先級：{stats.get('overdue_medium', 0)}\n"
                  f"🟢 低優先級：{stats.get('overdue_low', 0)}",
            inline=True
        )
        
        return embed

    def _build_staff_stats_embed(self, stats: Dict[str, Any], period: str, user: discord.Member, guild: discord.Guild) -> discord.Embed:
        """建立客服統計面板"""
        period_name = {"today": "今日", "week": "本週", "month": "本月"}.get(period, period)
        
        if user:
            # 個人統計
            embed = discord.Embed(
                title=f"👤 {user.display_name} 工作統計 - {period_name}",
                color=discord.Color.green()
            )
            
            user_stats = stats.get(str(user.id), {})
            embed.add_field(
                name="📊 處理統計",
                value=f"處理票券：{user_stats.get('handled_tickets', 0)} 張\n"
                      f"關閉票券：{user_stats.get('closed_tickets', 0)} 張\n"
                      f"平均處理時間：{user_stats.get('avg_handling_time', 0):.1f} 小時\n"
                      f"SLA 達標率：{user_stats.get('sla_rate', 0):.1f}%",
                inline=True
            )
            
            embed.add_field(
                name="⭐ 評分統計",
                value=f"平均評分：{user_stats.get('avg_rating', 0):.1f}/5\n"
                      f"5星評價：{user_stats.get('five_star_count', 0)} 次\n"
                      f"評分總數：{user_stats.get('total_ratings', 0)} 次",
                inline=True
            )
        else:
            # 團隊統計
            embed = discord.Embed(
                title=f"👥 客服團隊統計 - {period_name}",
                color=discord.Color.blue()
            )
            
            # 排序客服人員
            sorted_staff = sorted(stats.items(), key=lambda x: x[1].get('handled_tickets', 0), reverse=True)
            
            for staff_id, staff_stats in sorted_staff[:10]:
                member = guild.get_member(int(staff_id))
                if not member:
                    continue
                
                embed.add_field(
                    name=f"👤 {member.display_name}",
                    value=f"處理：{staff_stats.get('handled_tickets', 0)} 張\n"
                          f"評分：{staff_stats.get('avg_rating', 0):.1f}⭐\n"
                          f"SLA：{staff_stats.get('sla_rate', 0):.1f}%",
                    inline=True
                )
        
        return embed

    # ===== 格式化方法 =====
    
    def _format_channel_setting(self, guild: discord.Guild, channel_id: Optional[int]) -> str:
        """格式化頻道設定顯示"""
        if not channel_id:
            return "未設定"
        channel = guild.get_channel(channel_id)
        return channel.mention if channel else f"<#{channel_id}> (已刪除)"

    def _format_roles_setting(self, guild: discord.Guild, role_ids: List[int]) -> str:
        """格式化身分組設定顯示"""
        if not role_ids:
            return "未設定"
        
        role_mentions = []
        for role_id in role_ids:
            role = guild.get_role(role_id)
            if role:
                role_mentions.append(role.mention)
            else:
                role_mentions.append(f"<@&{role_id}> (已刪除)")
        
        return ", ".join(role_mentions)

    # ===== 日誌和警告方法 =====
    
    async def _send_sla_alert(self, guild: discord.Guild, ticket: Dict[str, Any], settings: Dict[str, Any]):
        """發送 SLA 警告"""
        try:
            alert_channel_id = settings.get('sla_alert_channel_id')
            if not alert_channel_id:
                return
            
            channel = guild.get_channel(alert_channel_id)
            if not channel:
                return
            
            # 計算超時時間
            now = datetime.now(timezone.utc)
            overdue_minutes = (now - ticket['created_at']).total_seconds() / 60
            target_minutes = calculate_sla_time(ticket.get('priority', 'medium'), settings.get('sla_response_minutes', 60))
            
            embed = discord.Embed(
                title="⚠️ SLA 超時警告",
                description=f"票券 #{ticket['ticket_id']:04d} 已超過目標回應時間",
                color=discord.Color.red()
            )
            
            priority_emoji = get_priority_emoji(ticket.get('priority', 'medium'))
            
            embed.add_field(name="票券類型", value=ticket['type'], inline=True)
            embed.add_field(name="優先級", value=f"{priority_emoji} {ticket.get('priority', 'medium').upper()}", inline=True)
            embed.add_field(name="超時時間", value=f"{overdue_minutes - target_minutes:.0f} 分鐘", inline=True)
            embed.add_field(name="開票者", value=f"<@{ticket['discord_id']}>", inline=True)
            
            if ticket.get('assigned_to'):
                embed.add_field(name="指派給", value=f"<@{ticket['assigned_to']}>", inline=True)
            
            # 添加頻道連結
            ticket_channel = guild.get_channel(ticket['channel_id'])
            if ticket_channel:
                embed.add_field(name="頻道", value=ticket_channel.mention, inline=True)
            
            await channel.send(embed=embed)
            
        except Exception as e:
            debug_log(f"[Ticket] 發送 SLA 警告錯誤：{e}")

    async def _log_ticket_action(self, guild: discord.Guild, ticket_id: int, action: str, details: str):
        """記錄票券操作到日誌頻道"""
        try:
            settings = await self.get_guild_settings(guild.id)
            log_channel_id = settings.get('log_channel_id')
            
            if not log_channel_id:
                return
            
            log_channel = guild.get_channel(log_channel_id)
            if not log_channel:
                return
            
            embed = discord.Embed(
                title=f"📋 票券操作：{action}",
                color=discord.Color.blue()
            )
            embed.add_field(name="票券編號", value=f"#{ticket_id:04d}", inline=True)
            embed.add_field(name="操作詳情", value=details, inline=False)
            embed.add_field(name="時間", value=f"<t:{int(datetime.now(timezone.utc).timestamp())}:F>", inline=True)
            
            await log_channel.send(embed=embed)
            
        except Exception as e:
            debug_log(f"[Ticket] 記錄操作錯誤：{e}")

    # ===== 錯誤處理 =====
    
    async def _handle_error(self, ctx: commands.Context, message: str, error: Exception):
        """處理指令錯誤"""
        debug_log(f"[Ticket] {message}: {error}")
        
        embed = discord.Embed(
            title="❌ 發生錯誤",
            description=message,
            color=discord.Color.red()
        )
        
        try:
            await ctx.send(embed=embed)
        except:
            try:
                await ctx.send(f"❌ {message}")
            except:
                pass

    async def _handle_interaction_error(self, interaction: discord.Interaction, message: str, error: Exception):
        """處理互動錯誤"""
        debug_log(f"[Ticket] {message}: {error}")
        
        embed = discord.Embed(
            title="❌ 發生錯誤",
            description=message,
            color=discord.Color.red()
        )
        
        try:
            if interaction.response.is_done():
                await interaction.followup.send(embed=embed, ephemeral=True)
            else:
                await interaction.response.send_message(embed=embed, ephemeral=True)
        except:
            try:
                if interaction.response.is_done():
                    await interaction.followup.send(f"❌ {message}", ephemeral=True)
                else:
                    await interaction.response.send_message(f"❌ {message}", ephemeral=True)
            except:
                pass

    # ===== 事件處理器 =====
    
    @commands.Cog.listener()
    async def on_ready(self):
        """系統啟動完成"""
        debug_log("[Ticket] 票券系統已啟動")
        
        # 啟動資料表檢查
        try:
            await self.dao.create_tables()
            debug_log("[Ticket] 資料表檢查完成")
        except Exception as e:
            debug_log(f"[Ticket] 資料表檢查失敗：{e}")

    @commands.Cog.listener()
    async def on_command_error(self, ctx: commands.Context, error: commands.CommandError):
        """指令錯誤處理"""
        if isinstance(error, commands.MissingPermissions):
            await ctx.send("❌ 你沒有權限使用此指令。", delete_after=10)
        elif isinstance(error, commands.CommandOnCooldown):
            await ctx.send(f"❌ 指令冷卻中，請等待 {error.retry_after:.1f} 秒。", delete_after=10)
        elif isinstance(error, commands.CommandNotFound):
            pass  # 忽略未知指令
        else:
            await self._handle_error(ctx, "執行指令時發生未預期的錯誤", error)

    @commands.Cog.listener()
    async def on_app_command_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        """應用程式指令錯誤處理"""
        if isinstance(error, app_commands.MissingPermissions):
            await interaction.response.send_message("❌ 你沒有權限使用此指令。", ephemeral=True)
        elif isinstance(error, app_commands.CommandOnCooldown):
            await interaction.response.send_message(f"❌ 指令冷卻中，請等待 {error.retry_after:.1f} 秒。", ephemeral=True)
        else:
            await self._handle_interaction_error(interaction, "執行指令時發生未預期的錯誤", error)


# ===== 註冊系統 =====

async def setup(bot: commands.Bot):
    """註冊票券系統"""
    try:
        # 載入系統
        ticket_system = TicketSystem(bot)
        await bot.add_cog(ticket_system)
        
        debug_log("✅ 票券系統已成功載入")
        
    except Exception as e:
        debug_log(f"❌ 票券系統載入失敗：{e}")
        raise