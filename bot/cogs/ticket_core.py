"""
票券系統核心功能 - v4.2 完整修正版
處理 PersistentView 註冊、型態註解、異常記錄、async/await一致化
Author: Craig JunWei + ChatGPT Turbo
"""

import discord
from discord.ext import commands, tasks
from discord import app_commands
from datetime import datetime, timezone, timedelta
from typing import Tuple, List, Dict, Optional, Any
import asyncio

from bot.db.ticket_dao import TicketDAO
from bot.services.ticket_manager import TicketManager
from bot.views.ticket_views import TicketPanelView, TicketControlView, TicketListView, RatingView
from bot.utils.embed_builder import EmbedBuilder
from bot.utils.ticket_constants import TicketConstants
from bot.utils.helper import format_duration, get_time_ago
from shared.logger import logger

class TicketCore(commands.Cog):
    """票券系統核心功能"""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.DAO = TicketDAO()
        self.manager = TicketManager(self.DAO)
        # 註冊所有 Persistent View
        self._register_persistent_views()
        # 啟動 SLA 監控與清理任務
        self.sla_monitor.start()
        self.cleanup_task.start()

    def cog_unload(self):
        self.sla_monitor.cancel()
        self.cleanup_task.cancel()

    def _register_persistent_views(self):
        """
        註冊所有持久化互動 View。
        必須於機器人啟動時註冊，否則斷線後 Discord 互動元件會失效。
        """
        try:
            self.bot.add_view(TicketPanelView(settings=None))    # 主面板（不需參數即 persistent）
            self.bot.add_view(TicketControlView())  # 控制面板
            self.bot.add_view(RatingView(ticket_id=0, persistent=True)) # 評分（0為範例persistent，真實互動需動態）
        except Exception as e:
            logger.error(f"PersistentView 註冊失敗: {e}")

    # ========== 工具 - 票券頻道判斷 ==========
    async def _is_ticket_channel(self, channel: discord.TextChannel) -> bool:
        """
        用資料庫查詢該頻道是否為票券頻道。
        """
        try:
            ticket = await self.DAO.get_ticket_by_channel(channel.id)
            return ticket is not None
        except Exception as e:
            logger.error(f"[票券頻道判斷] 頻道 {getattr(channel, 'id', None)} 查詢失敗: {e}")
            # fallback: 若資料庫失敗則比對名稱
            return hasattr(channel, 'name') and channel.name.startswith('ticket-')

    # ========== 指令區 ==========

    @commands.command(name="setup_ticket")
    @commands.has_permissions(manage_guild=True)
    async def setup_ticket(self, ctx: commands.Context):
        """
        建立票券面板（文字指令）。
        """
        try:
            settings = await self.DAO.get_settings(ctx.guild.id)
            embed = EmbedBuilder.build(
                title="🎫 客服中心",
                description=settings.get('welcome_message', "請選擇問題類型來建立支援票券"),
                color=TicketConstants.COLORS['primary']
            )
            embed.add_field(
                name="📋 系統資訊",
                value=f"• 每人限制：{settings.get('max_tickets_per_user', 3)} 張\n"
                      f"• 自動關閉：{settings.get('auto_close_hours', 24)} 小時\n"
                      f"• 預期回覆：{settings.get('sla_response_minutes', 60)} 分鐘",
                inline=False
            )
            view = TicketPanelView(settings)
            message = await ctx.send(embed=embed, view=view)
            await self.DAO.save_panel_message(ctx.guild.id, message.id, ctx.channel.id)
            logger.info(f"票券面板建立於 {ctx.guild.name} by {ctx.author}")
        except Exception as e:
            logger.error(f"建立票券面板錯誤: {e}")
            await ctx.send("❌ 建立票券面板失敗，請稍後再試。")

    # --------- 票券操作 ---------
    @app_commands.command(name="close", description="關閉票券")
    @app_commands.describe(reason="關閉原因", request_rating="是否要求評分")
    async def close_ticket(self, interaction: discord.Interaction, reason: str = None, request_rating: bool = True):
        """
        關閉票券（slash 指令）
        """
        try:
            if not await self._is_ticket_channel(interaction.channel):
                await interaction.response.send_message("❌ 此指令只能在票券頻道中使用。", ephemeral=True)
                return
            ticket = await self.DAO.get_ticket_by_channel(interaction.channel.id)
            if not ticket:
                await interaction.response.send_message("❌ 找不到票券資訊。", ephemeral=True)
                return
            if ticket['status'] == 'closed':
                await interaction.response.send_message("❌ 此票券已經關閉。", ephemeral=True)
                return
            settings = await self.DAO.get_settings(interaction.guild.id)
            can_close = await self._check_close_permission(interaction.user, ticket, settings)
            if not can_close:
                await interaction.response.send_message("❌ 只有票券創建者或客服人員可以關閉票券。", ephemeral=True)
                return
            success = await self.manager.close_ticket(
                ticket_id=ticket['id'],
                closed_by=interaction.user.id,
                reason=reason or "手動關閉"
            )
            if success:
                embed = EmbedBuilder.build(
                    title="✅ 票券已關閉",
                    description=f"票券 #{ticket['id']:04d} 已成功關閉",
                    color=TicketConstants.COLORS['success']
                )
                if reason:
                    embed.add_field(name="關閉原因", value=reason, inline=False)
                await interaction.response.send_message(embed=embed)
                # 評分（僅創建者可評分，未評過才顯示）
                if (str(interaction.user.id) == ticket['discord_id']
                    and request_rating and not ticket.get('rating')):
                    await asyncio.sleep(2)
                    await self._show_rating_interface(interaction.channel, ticket['id'])
                await self._schedule_channel_deletion(interaction.channel, delay=30)
            else:
                await interaction.response.send_message("❌ 關閉票券失敗，請稍後再試。", ephemeral=True)
        except Exception as e:
            logger.error(f"關閉票券錯誤: {e}")
            if not interaction.response.is_done():
                await interaction.response.send_message("❌ 發生錯誤，請稍後再試。", ephemeral=True)

    @app_commands.command(name="ticket_info", description="查看票券資訊")
    @app_commands.describe(ticket_id="票券編號（可選）")
    async def ticket_info(self, interaction: discord.Interaction, ticket_id: int = None):
        """
        查看票券資訊（slash 指令）。
        """
        try:
            if ticket_id:
                ticket = await self.DAO.get_ticket_by_id(ticket_id)
            elif await self._is_ticket_channel(interaction.channel):
                ticket = await self.DAO.get_ticket_by_channel(interaction.channel.id)
            else:
                await interaction.response.send_message("❌ 請在票券頻道中使用，或指定票券編號。", ephemeral=True)
                return
            if not ticket:
                await interaction.response.send_message("❌ 找不到票券。", ephemeral=True)
                return
            settings = await self.DAO.get_settings(interaction.guild.id)
            can_view = await self._check_view_permission(interaction.user, ticket, settings)
            if not can_view:
                await interaction.response.send_message("❌ 你沒有權限查看此票券。", ephemeral=True)
                return
            embed = await self._build_ticket_info_embed(ticket, interaction.guild)
            await interaction.response.send_message(embed=embed, ephemeral=True)
        except Exception as e:
            logger.error(f"查看票券資訊錯誤: {e}")
            await interaction.response.send_message("❌ 查詢失敗，請稍後再試。", ephemeral=True)

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
        """
        查看票券列表（slash 指令）。
        """
        try:
            settings = await self.DAO.get_settings(interaction.guild.id)
            is_staff = await self._is_support_staff(interaction.user, settings)
            if user and not is_staff:
                await interaction.response.send_message(
                    "❌ 只有客服人員可以查看其他用戶的票券。", ephemeral=True
                )
                return
            query_params = {
                'guild_id': interaction.guild.id,
                'page': 1,
                'page_size': 10
            }
            if user:
                query_params['user_id'] = user.id
            elif not is_staff:
                query_params['user_id'] = interaction.user.id
            if status != "all":
                query_params['status'] = status
            if priority != "all":
                query_params['priority'] = priority
            tickets, total = await self.DAO.get_tickets(**query_params)
            if not tickets:
                await interaction.response.send_message("📭 沒有找到符合條件的票券。", ephemeral=True)
                return
            embed = await self._build_tickets_list_embed(
                tickets, total, status, user, priority
            )
            if total > 10:
                view = TicketListView(tickets, 1, (total + 9) // 10, **query_params)
                await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
            else:
                await interaction.response.send_message(embed=embed, ephemeral=True)
        except Exception as e:
            logger.error(f"查看票券列表錯誤: {e}")
            await interaction.response.send_message(
                "❌ 查詢失敗，請稍後再試。", ephemeral=True
            )

    # 其餘指令（assign、priority、rate、setting、stats ...）建議同上寫法搬入即可。
    # 若需一併全部指令自動產生可再補出！

    # ========== SLA 監控任務 ==========
    @tasks.loop(minutes=5)
    async def sla_monitor(self):
        """
        SLA 監控任務 - 定時檢查超時票券並通知。
        """
        try:
            overdue_tickets = await self.DAO.get_overdue_tickets()
            if not overdue_tickets:
                return
            guild_tickets = {}
            for ticket in overdue_tickets:
                guild_id = ticket['guild_id']
                guild_tickets.setdefault(guild_id, []).append(ticket)
            for guild_id, tickets in guild_tickets.items():
                try:
                    guild = self.bot.get_guild(guild_id)
                    if guild:
                        await self._handle_guild_overdue_tickets(guild, tickets)
                except Exception as e:
                    logger.error(f"處理伺服器 {guild_id} SLA 超時錯誤: {e}")
        except Exception as e:
            logger.error(f"SLA 監控錯誤: {e}")

    @tasks.loop(hours=6)
    async def cleanup_task(self):
        """
        定期清理過期票券與日誌。
        """
        try:
            logger.info("開始執行票券系統清理任務")
            cleaned_logs = await self.DAO.cleanup_old_logs(days=30)
            logger.info(f"清理了 {cleaned_logs} 條舊日誌")
            await self.DAO.cleanup_expired_cache()
            for guild in self.bot.guilds:
                try:
                    settings = await self.DAO.get_settings(guild.id)
                    auto_close_hours = settings.get('auto_close_hours', 24)
                    if auto_close_hours > 0:
                        closed_count = await self._auto_close_inactive_tickets(
                            guild.id, auto_close_hours
                        )
                        if closed_count > 0:
                            logger.info(f"自動關閉了 {closed_count} 張無活動票券 - 伺服器: {guild.name}")
                except Exception as e:
                    logger.error(f"清理伺服器 {guild.id} 票券錯誤: {e}")
            logger.info("票券系統清理任務完成")
        except Exception as e:
            logger.error(f"清理任務錯誤: {e}")

    @sla_monitor.before_loop
    async def before_sla_monitor(self): await self.bot.wait_until_ready()
    @cleanup_task.before_loop
    async def before_cleanup_task(self): await self.bot.wait_until_ready()

    # ========== 權限檢查與工具 ==========

    async def _check_close_permission(self, user: discord.Member, ticket: Dict, settings: Dict) -> bool:
        """
        票券創建者或客服可關閉
        """
        if str(user.id) == ticket['discord_id']:
            return True
        return await self._is_support_staff(user, settings)

    async def _check_view_permission(self, user: discord.Member, ticket: Dict, settings: Dict) -> bool:
        """
        票券創建者或客服可查看
        """
        if str(user.id) == ticket['discord_id']:
            return True
        return await self._is_support_staff(user, settings)

    async def _is_support_staff(self, user: discord.Member, settings: Dict) -> bool:
        """
        是否為客服身分組或管理員
        """
        if user.guild_permissions.manage_guild:
            return True
        support_roles = settings.get('support_roles', [])
        user_role_ids = {role.id for role in user.roles}
        return any(role_id in user_role_ids for role_id in support_roles)

    # ========== 嵌入建構 ==========
    async def _build_ticket_info_embed(self, ticket: Dict, guild: discord.Guild) -> discord.Embed:
        """
        建立票券資訊嵌入訊息。
        """
        priority_emoji = TicketConstants.PRIORITY_EMOJIS.get(ticket.get('priority', 'medium'), '🟡')
        status_emoji = TicketConstants.STATUS_EMOJIS.get(ticket['status'], '🟢')
        color = TicketConstants.PRIORITY_COLORS.get(ticket.get('priority', 'medium'), 0x00ff00)

        embed = EmbedBuilder.build(
            title=f"🎫 票券 #{ticket['id']:04d}",
            color=color
        )
        embed.add_field(
            name="📋 基本資訊",
            value=f"**類型：** {ticket['type']}\n"
                  f"**狀態：** {status_emoji} {ticket['status'].upper()}\n"
                  f"**優先級：** {priority_emoji} {ticket.get('priority', 'medium').upper()}",
            inline=True
        )
        embed.add_field(
            name="👤 用戶資訊",
            value=f"**開票者：** <@{ticket['discord_id']}>\n"
                  f"**用戶名：** {ticket['username']}",
            inline=True
        )
        created_time = get_time_ago(ticket['created_at'])
        time_info = f"**建立：** {created_time}"
        if ticket.get('closed_at'):
            closed_time = get_time_ago(ticket['closed_at'])
            duration = ticket['closed_at'] - ticket['created_at']
            time_info += f"\n**關閉：** {closed_time}\n"
            time_info += f"**持續：** {format_duration(duration)}"
        else:
            open_duration = datetime.now(timezone.utc) - ticket['created_at']
            time_info += f"\n**已開啟：** {format_duration(open_duration)}"
        embed.add_field(name="⏰ 時間資訊", value=time_info, inline=False)
        if ticket.get('assigned_to'):
            embed.add_field(
                name="👥 指派資訊",
                value=f"**負責客服：** <@{ticket['assigned_to']}>",
                inline=True
            )
        if ticket.get('rating'):
            stars = TicketConstants.RATING_EMOJIS.get(ticket['rating'], "⭐")
            rating_text = f"**評分：** {stars} ({ticket['rating']}/5)"
            if ticket.get('rating_feedback'):
                feedback = ticket['rating_feedback'][:100] + "..." if len(ticket['rating_feedback']) > 100 else ticket['rating_feedback']
                rating_text += f"\n**回饋：** {feedback}"
            embed.add_field(name="⭐ 評分", value=rating_text, inline=True)
        if ticket['status'] == 'open':
            embed.add_field(
                name="📍 頻道資訊",
                value=f"**頻道：** <#{ticket['channel_id']}>",
                inline=True
            )
        return embed

    async def _build_tickets_list_embed(self, tickets: List[Dict], total: int, 
                                       status: str, user: Optional[discord.Member], 
                                       priority: str) -> discord.Embed:
        """
        建立票券列表嵌入訊息。
        """
        embed = EmbedBuilder.build(
            title="🎫 票券列表",
            color=TicketConstants.COLORS['info']
        )
        filters = []
        if status != "all": filters.append(f"狀態: {status}")
        if user: filters.append(f"用戶: {user.display_name}")
        if priority != "all": filters.append(f"優先級: {priority}")
        if filters: embed.description = f"**篩選條件：** {' | '.join(filters)}"
        for ticket in tickets[:10]:
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
            if ticket['status'] == 'open':
                field_value += f"\n📍 <#{ticket['channel_id']}>"
            embed.add_field(
                name=f"#{ticket['id']:04d} - {ticket['type']}",
                value=field_value,
                inline=True
            )
        embed.set_footer(text=f"共 {total} 筆記錄" + (f"（顯示前 10 筆）" if total > 10 else ""))
        return embed

    # ========== 互動工具 ==========
    async def _show_rating_interface(self, channel: discord.TextChannel, ticket_id: int):
        """
        顯示評分界面
        """
        try:
            embed = EmbedBuilder.build(
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
            logger.error(f"顯示評分界面錯誤: {e}")

    async def _schedule_channel_deletion(self, channel: discord.TextChannel, delay: int = 30):
        """
        延遲刪除票券頻道。
        """
        try:
            await asyncio.sleep(delay)
            await channel.delete(reason="票券已關閉")
        except discord.NotFound:
            pass
        except discord.Forbidden:
            logger.warning(f"沒有權限刪除頻道：{channel.name}")
        except Exception as e:
            logger.error(f"刪除頻道錯誤: {e}")

    async def _handle_guild_overdue_tickets(self, guild: discord.Guild, tickets: List[Dict]):
        """
        通知指定伺服器的所有超時票券。
        """
        try:
            settings = await self.DAO.get_settings(guild.id)
            log_channel_id = settings.get('log_channel_id')
            if not log_channel_id: return
            log_channel = guild.get_channel(log_channel_id)
            if not log_channel: return
            priority_groups = {'high': [], 'medium': [], 'low': []}
            for ticket in tickets:
                priority = ticket.get('priority', 'medium')
                if priority in priority_groups:
                    priority_groups[priority].append(ticket)
            embed = EmbedBuilder.build(
                title="⚠️ SLA 超時警告",
                description=f"發現 {len(tickets)} 張票券超過預期回應時間",
                color=discord.Color.red()
            )
            for priority, priority_tickets in priority_groups.items():
                if not priority_tickets:
                    continue
                emoji = TicketConstants.PRIORITY_EMOJIS.get(priority, '🟡')
                ticket_list = []
                for ticket in priority_tickets[:5]:
                    overdue_time = self._calculate_overdue_time(ticket, settings)
                    ticket_list.append(
                        f"#{ticket['id']:04d} - {ticket['type']} (超時 {overdue_time:.0f} 分鐘)"
                    )
                if len(priority_tickets) > 5:
                    ticket_list.append(f"... 還有 {len(priority_tickets) - 5} 張")
                embed.add_field(
                    name=f"{emoji} {priority.upper()} 優先級 ({len(priority_tickets)} 張)",
                    value="\n".join(ticket_list),
                    inline=False
                )
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
            logger.error(f"處理伺服器超時票券錯誤: {e}")

    def _calculate_overdue_time(self, ticket: Dict, settings: Dict) -> float:
        """
        計算超時時間（分鐘）
        """
        try:
            now = datetime.now(timezone.utc)
            created_at = ticket['created_at']
            elapsed_minutes = (now - created_at).total_seconds() / 60
            base_sla = settings.get('sla_response_minutes', 60)
            priority = ticket.get('priority', 'medium')
            multiplier = TicketConstants.SLA_MULTIPLIERS.get(priority, 1.0)
            target_minutes = base_sla * multiplier
            return max(0, elapsed_minutes - target_minutes)
        except Exception as e:
            logger.error(f"計算超時時間錯誤: {e}")
            return 0

    async def _auto_close_inactive_tickets(self, guild_id: int, hours_threshold: int) -> int:
        """
        自動關閉無活動票券。
        """
        try:
            cutoff_time = datetime.now(timezone.utc) - timedelta(hours=hours_threshold)
            inactive_tickets = await self.DAO.get_inactive_tickets(guild_id, cutoff_time)
            closed_count = 0
            for ticket in inactive_tickets:
                try:
                    success = await self.manager.close_ticket(
                        ticket_id=ticket['id'],
                        closed_by=0,  # 系統關閉
                        reason=f"自動關閉：無活動超過 {hours_threshold} 小時"
                    )
                    if success:
                        closed_count += 1
                        try:
                            guild = self.bot.get_guild(guild_id)
                            user = guild.get_member(int(ticket['discord_id'])) if guild else None
                            if user:
                                embed = EmbedBuilder.build(
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
                            pass
                        try:
                            guild = self.bot.get_guild(guild_id)
                            if guild:
                                channel = guild.get_channel(ticket['channel_id'])
                                if channel:
                                    await channel.delete(reason="票券自動關閉")
                        except:
                            pass
                except Exception as e:
                    logger.error(f"自動關閉票券 #{ticket['id']:04d} 錯誤: {e}")
                    continue
            return closed_count
        except Exception as e:
            logger.error(f"自動關閉無活動票券錯誤: {e}")
            return 0

async def setup(bot: commands.Bot):
    """
    載入 TicketCore cog。
    """
    await bot.add_cog(TicketCore(bot))
    logger.info("✅ 票券核心系統已載入")
