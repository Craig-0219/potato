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
from bot.db.assignment_dao import AssignmentDAO
from bot.db.tag_dao import TagDAO
from bot.services.ticket_manager import TicketManager
from bot.services.assignment_manager import AssignmentManager
from bot.services.tag_manager import TagManager
from bot.services.statistics_manager import StatisticsManager
from bot.services.language_manager import LanguageManager
from bot.db.language_dao import LanguageDAO
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
        self.assignment_dao = AssignmentDAO()
        self.tag_dao = TagDAO()
        self.language_dao = LanguageDAO()
        self.manager = TicketManager(self.DAO)
        self.assignment_manager = AssignmentManager(self.assignment_dao, self.DAO)
        self.tag_manager = TagManager(self.tag_dao)
        self.statistics_manager = StatisticsManager(
            ticket_dao=self.DAO,
            assignment_dao=self.assignment_dao,
            tag_dao=self.tag_dao
        )
        self.language_manager = LanguageManager()
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
            # RatingView 改為動態創建，不在此註冊
            # self.bot.add_view(RatingView(ticket_id=0)) # 評分（改為動態創建）
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

    @commands.command(name="set_ticket_category", aliases=["set_category", "ticket_category"])
    @commands.has_permissions(manage_guild=True)
    async def set_ticket_category(self, ctx: commands.Context, *, category: discord.CategoryChannel = None):
        """
        設定票券分類頻道
        用法: !set_ticket_category #分類頻道名稱
        或者: !set_ticket_category 分類頻道名稱
        """
        if category is None:
            embed = EmbedBuilder.build(
                title="❓ 如何設定票券分類",
                description="請使用以下格式設定票券分類頻道：",
                color=0x3498db
            )
            embed.add_field(
                name="📝 使用方法",
                value="```\n!set_ticket_category #分類頻道名稱\n```\n或者\n```\n!set_ticket_category 分類頻道名稱\n```",
                inline=False
            )
            embed.add_field(
                name="📋 範例",
                value="`!set_ticket_category #客服中心`\n`!set_category 票券系統`",
                inline=False
            )
            await ctx.send(embed=embed)
            return
            
        try:
            # 更新資料庫設定
            await self.DAO.update_settings(ctx.guild.id, {
                'category_id': category.id
            })
            
            embed = EmbedBuilder.success(
                "分類頻道設定成功",
                f"✅ 票券分類已設定為：{category.mention}\n"
                f"📋 票券頻道將會在此分類下建立\n\n"
                f"請確保分類頻道權限設定正確：\n"
                f"• `@everyone` - 拒絕查看頻道\n"
                f"• `@客服角色` - 允許查看頻道、發送訊息\n"
                f"• `{self.bot.user.mention}` - 允許管理頻道、管理權限"
            )
            
            await ctx.send(embed=embed)
            logger.info(f"票券分類設定: {category.name} ({category.id}) by {ctx.author}")
            
        except Exception as e:
            logger.error(f"設定票券分類錯誤: {e}")
            await ctx.send("❌ 設定票券分類失敗，請稍後再試。可能的原因：\n"
                          "• 頻道不存在或已被刪除\n"
                          "• Bot 沒有該頻道的存取權限\n"
                          "• 指定的不是分類頻道")

    @commands.command(name="ticket_settings", aliases=["settings", "ticket_config"])
    @commands.has_permissions(manage_guild=True)
    async def view_ticket_settings(self, ctx: commands.Context):
        """
        查看目前票券系統設定
        """
        try:
            settings = await self.DAO.get_settings(ctx.guild.id)
            
            embed = EmbedBuilder.build(
                title="⚙️ 票券系統設定",
                description="目前的票券系統配置",
                color=TicketConstants.COLORS['info']
            )
            
            # 分類頻道資訊
            category_id = settings.get('category_id')
            if category_id:
                category = ctx.guild.get_channel(category_id)
                category_info = category.mention if category else f"<#{category_id}> (已刪除)"
            else:
                category_info = "❌ 尚未設定"
                
            embed.add_field(
                name="📁 票券分類",
                value=category_info,
                inline=False
            )
            
            # 其他設定
            embed.add_field(
                name="📊 系統設定",
                value=f"• 每人票券限制：{settings.get('max_tickets_per_user', 3)} 張\n"
                      f"• 自動關閉時間：{settings.get('auto_close_hours', 24)} 小時\n"
                      f"• SLA 回應時間：{settings.get('sla_response_minutes', 60)} 分鐘",
                inline=False
            )
            
            # 客服角色
            support_roles = settings.get('support_roles', [])
            if support_roles:
                role_mentions = []
                for role_id in support_roles:
                    role = ctx.guild.get_role(role_id)
                    role_mentions.append(role.mention if role else f"<@&{role_id}> (已刪除)")
                role_info = "\n".join([f"• {role}" for role in role_mentions])
            else:
                role_info = "❌ 尚未設定"
                
            embed.add_field(
                name="👥 客服角色",
                value=role_info,
                inline=False
            )
            
            # 歡迎訊息
            welcome_msg = settings.get('welcome_message', '預設歡迎訊息')
            if len(welcome_msg) > 100:
                welcome_msg = welcome_msg[:100] + "..."
                
            embed.add_field(
                name="💬 歡迎訊息",
                value=f"```{welcome_msg}```",
                inline=False
            )
            
            embed.set_footer(text="💡 使用 !set_ticket_category #分類名稱 來設定票券分類")
            
            await ctx.send(embed=embed)
            
        except Exception as e:
            logger.error(f"查看票券設定錯誤: {e}")
            await ctx.send("❌ 無法查看票券設定，請稍後再試。")

    @commands.command(name="ticket_test")
    @commands.has_permissions(manage_guild=True)
    async def ticket_test(self, ctx: commands.Context):
        """
        測試票券系統是否正常運作
        """
        await ctx.send("✅ 票券系統核心模組運作正常！\n"
                      "可用指令: `!setup_ticket`, `!set_ticket_category`, `!ticket_settings`, `!ticket_test`")

    @commands.command(name="ticket_help", aliases=["help_ticket"])
    async def ticket_help(self, ctx: commands.Context):
        """
        顯示票券系統指令說明
        """
        embed = EmbedBuilder.build(
            title="🎫 票券系統指令說明",
            description="以下是所有可用的票券系統指令：",
            color=TicketConstants.COLORS['info']
        )
        
        embed.add_field(
            name="📋 基礎管理指令",
            value="`!setup_ticket` - 建立票券面板\n"
                  "`!set_ticket_category #頻道` - 設定分類 **(注意空格)**\n"
                  "`!ticket_settings` - 查看系統設定\n"
                  "`!ticket_test` - 測試系統運作",
            inline=False
        )
        
        embed.add_field(
            name="👥 指派系統指令",
            value="`!assign_ticket <ID> @客服` - 手動指派票券\n"
                  "`!auto_assign <ID>` - 自動指派票券\n"
                  "`!staff_workload [@客服]` - 查看工作量\n"
                  "`!add_specialty @客服 <類型> [等級]` - 設定專精\n"
                  "`!assignment_stats [天數]` - 指派統計",
            inline=False
        )
        
        embed.add_field(
            name="⚠️ 常見錯誤",
            value="• 指令和參數間忘記加空格\n"
                  "• 使用了不存在的頻道\n"
                  "• 沒有足夠的權限",
            inline=False
        )
        
        embed.add_field(
            name="💡 正確範例",
            value="`!set_ticket_category #客服中心` ✅\n"
                  "`!set_ticket_category#客服中心` ❌",
            inline=False
        )
        
        await ctx.send(embed=embed)

    # --------- 指派系統指令 ---------
    
    @commands.command(name="assign_ticket", aliases=["assign"])
    @commands.has_permissions(manage_guild=True)
    async def assign_ticket_command(self, ctx: commands.Context, ticket_id: int, member: discord.Member):
        """
        手動指派票券給客服人員
        用法: !assign_ticket <票券ID> @客服人員
        """
        try:
            success, message = await self.assignment_manager.assign_ticket(
                ticket_id, member.id, ctx.author.id, "manual", "管理員手動指派"
            )
            
            if success:
                embed = EmbedBuilder.success(
                    "指派成功",
                    f"✅ {message}\n👤 客服人員：{member.mention}"
                )
            else:
                embed = EmbedBuilder.error("指派失敗", f"❌ {message}")
            
            await ctx.send(embed=embed)
            
        except Exception as e:
            logger.error(f"手動指派票券錯誤: {e}")
            await ctx.send("❌ 指派過程中發生錯誤，請稍後再試。")

    @commands.command(name="auto_assign", aliases=["autoassign"])
    @commands.has_permissions(manage_guild=True)
    async def auto_assign_command(self, ctx: commands.Context, ticket_id: int):
        """
        自動指派票券
        用法: !auto_assign <票券ID>
        """
        try:
            success, message, assigned_to = await self.assignment_manager.auto_assign_ticket(
                ticket_id, ctx.author.id
            )
            
            if success and assigned_to:
                member = ctx.guild.get_member(assigned_to)
                embed = EmbedBuilder.success(
                    "自動指派成功",
                    f"✅ {message}\n🤖 自動指派給：{member.mention if member else f'<@{assigned_to}>'}"
                )
            else:
                embed = EmbedBuilder.error("自動指派失敗", f"❌ {message}")
            
            await ctx.send(embed=embed)
            
        except Exception as e:
            logger.error(f"自動指派票券錯誤: {e}")
            await ctx.send("❌ 自動指派過程中發生錯誤，請稍後再試。")

    @commands.command(name="staff_workload", aliases=["workload"])
    @commands.has_permissions(manage_guild=True)
    async def staff_workload_command(self, ctx: commands.Context, member: discord.Member = None):
        """
        查看客服工作量
        用法: !staff_workload [@客服人員]
        """
        try:
            if member:
                # 查看特定客服的詳細資訊
                profile = await self.assignment_manager.get_staff_profile(ctx.guild.id, member.id)
                
                if not profile:
                    await ctx.send("❌ 找不到該客服人員的工作量資訊。")
                    return
                
                workload = profile['workload']
                specialties = profile['specialties']
                metrics = profile['performance_metrics']
                
                embed = EmbedBuilder.build(
                    title=f"👤 {member.display_name} 的工作負載",
                    color=TicketConstants.COLORS['info']
                )
                
                embed.add_field(
                    name="📊 當前狀況",
                    value=f"• 處理中票券：{workload['current_tickets']} 張\n"
                          f"• 總指派數：{workload['total_assigned']} 張\n"
                          f"• 已完成：{workload['total_completed']} 張",
                    inline=True
                )
                
                embed.add_field(
                    name="⚡ 效率指標",
                    value=f"• 完成率：{metrics['completion_rate']:.1f}%\n"
                          f"• 平均處理時間：{workload['avg_completion_time']} 分鐘\n"
                          f"• 效率分數：{metrics['efficiency_score']:.1f}",
                    inline=True
                )
                
                if specialties:
                    specialty_list = [f"• {s['specialty_type']} ({s['skill_level']})" for s in specialties]
                    embed.add_field(
                        name="🎯 專精領域",
                        value="\n".join(specialty_list),
                        inline=False
                    )
                
                if workload['last_assigned_at']:
                    embed.add_field(
                        name="⏰ 最後指派時間",
                        value=get_time_ago(workload['last_assigned_at']),
                        inline=True
                    )
                
            else:
                # 查看所有客服的工作量摘要
                summary = await self.assignment_manager.get_staff_workload_summary(ctx.guild.id)
                
                if not summary:
                    await ctx.send("📭 目前沒有客服人員的工作量資料。")
                    return
                
                embed = EmbedBuilder.build(
                    title="👥 客服團隊工作負載",
                    description=f"共 {len(summary)} 位客服人員",
                    color=TicketConstants.COLORS['info']
                )
                
                # 顯示前10位客服的摘要
                for i, staff in enumerate(summary[:10], 1):
                    member = ctx.guild.get_member(staff['staff_id'])
                    name = member.display_name if member else f"<@{staff['staff_id']}>"
                    
                    status_emoji = "🟢" if staff['load_status'] == "輕鬆" else "🟡" if staff['load_status'] == "適中" else "🔴"
                    
                    embed.add_field(
                        name=f"{status_emoji} {name}",
                        value=f"處理中：{staff['current_tickets']}張\n"
                              f"完成率：{staff['completion_rate']}%\n"
                              f"狀態：{staff['load_status']}",
                        inline=True
                    )
                
                if len(summary) > 10:
                    embed.set_footer(text=f"顯示前10位，共{len(summary)}位客服")
            
            await ctx.send(embed=embed)
            
        except Exception as e:
            logger.error(f"查看工作量錯誤: {e}")
            await ctx.send("❌ 查看工作量時發生錯誤，請稍後再試。")

    @commands.command(name="add_specialty", aliases=["specialty"])
    @commands.has_permissions(manage_guild=True)
    async def add_specialty_command(self, ctx: commands.Context, member: discord.Member, 
                                  specialty_type: str, skill_level: str = "intermediate"):
        """
        設定客服專精
        用法: !add_specialty @客服人員 <專精類型> [技能等級]
        技能等級: beginner, intermediate, advanced, expert
        """
        try:
            success, message = await self.assignment_manager.add_staff_specialty(
                ctx.guild.id, member.id, specialty_type, skill_level
            )
            
            if success:
                embed = EmbedBuilder.success(
                    "專精設定成功",
                    f"✅ {message}\n👤 客服：{member.mention}"
                )
            else:
                embed = EmbedBuilder.error("設定失敗", f"❌ {message}")
            
            await ctx.send(embed=embed)
            
        except Exception as e:
            logger.error(f"設定客服專精錯誤: {e}")
            await ctx.send("❌ 設定專精時發生錯誤，請稍後再試。")

    @commands.command(name="assignment_stats", aliases=["assign_stats"])
    @commands.has_permissions(manage_guild=True)
    async def assignment_stats_command(self, ctx: commands.Context, days: int = 30):
        """
        查看指派統計
        用法: !assignment_stats [天數]
        """
        try:
            analytics = await self.assignment_manager.get_assignment_analytics(ctx.guild.id, days)
            
            if not analytics:
                await ctx.send("❌ 無法取得指派統計資料。")
                return
            
            embed = EmbedBuilder.build(
                title="📊 指派系統統計",
                description=f"統計期間：過去 {days} 天",
                color=TicketConstants.COLORS['info']
            )
            
            # 基本統計
            embed.add_field(
                name="📈 整體統計",
                value=f"• 客服人數：{analytics['staff_count']} 人\n"
                      f"• 處理中票券：{analytics['total_current_tickets']} 張\n"
                      f"• 已完成票券：{analytics['total_completed_tickets']} 張\n"
                      f"• 平均完成率：{analytics['avg_completion_rate']}%",
                inline=False
            )
            
            # 工作量分佈
            distribution = analytics['workload_distribution']
            embed.add_field(
                name="⚖️ 工作量分佈",
                value=f"🟢 輕鬆：{distribution['輕鬆']} 人\n"
                      f"🟡 適中：{distribution['適中']} 人\n"
                      f"🔴 繁忙：{distribution['繁忙']} 人",
                inline=True
            )
            
            # 指派方法統計
            if analytics['assignment_methods']:
                method_stats = []
                for method in analytics['assignment_methods']:
                    method_name = {
                        'manual': '手動指派',
                        'auto_least_workload': '最少工作量',
                        'auto_round_robin': '輪流指派',
                        'auto_specialty': '專精匹配'
                    }.get(method['method'], method['method'])
                    
                    method_stats.append(f"• {method_name}: {method['count']}次 ({method['percentage']:.1f}%)")
                
                embed.add_field(
                    name="🎯 指派方法分析",
                    value="\n".join(method_stats),
                    inline=True
                )
            
            # 績效排行
            if analytics['staff_summary']:
                top_performers = []
                for i, staff in enumerate(analytics['staff_summary'][:5], 1):
                    member = ctx.guild.get_member(staff['staff_id'])
                    name = member.display_name if member else f"Staff {staff['staff_id']}"
                    top_performers.append(f"{i}. {name} ({staff['completion_rate']:.1f}%)")
                
                embed.add_field(
                    name="🏆 績效排行 TOP5",
                    value="\n".join(top_performers),
                    inline=False
                )
            
            await ctx.send(embed=embed)
            
        except Exception as e:
            logger.error(f"查看指派統計錯誤: {e}")
            await ctx.send("❌ 查看統計時發生錯誤，請稍後再試。")

    # --------- 優先級系統指令 ---------
    
    @app_commands.command(name="set_priority", description="設定票券優先級")
    @app_commands.describe(priority="優先級等級", ticket_id="票券ID（可選，預設為當前頻道票券）")
    @app_commands.choices(priority=[
        app_commands.Choice(name="🔴 高優先級 - 緊急問題", value="high"),
        app_commands.Choice(name="🟡 中優先級 - 一般問題", value="medium"),
        app_commands.Choice(name="🟢 低優先級 - 非緊急問題", value="low")
    ])
    async def set_priority(self, interaction: discord.Interaction, priority: str, ticket_id: int = None):
        """設定票券優先級"""
        try:
            # 取得票券
            if ticket_id:
                ticket = await self.DAO.get_ticket_by_id(ticket_id)
            else:
                if not await self._is_ticket_channel(interaction.channel):
                    await interaction.response.send_message("❌ 請在票券頻道中使用，或指定票券ID。", ephemeral=True)
                    return
                ticket = await self.DAO.get_ticket_by_channel(interaction.channel.id)
            
            if not ticket:
                await interaction.response.send_message("❌ 找不到指定的票券。", ephemeral=True)
                return
            
            if ticket['status'] != 'open':
                await interaction.response.send_message("❌ 只能設定開啟中票券的優先級。", ephemeral=True)
                return
            
            # 檢查權限
            settings = await self.DAO.get_settings(interaction.guild.id)
            is_staff = await self._is_support_staff(interaction.user, settings)
            is_creator = str(interaction.user.id) == ticket['discord_id']
            
            if not (is_staff or interaction.user.guild_permissions.manage_guild):
                await interaction.response.send_message("❌ 只有客服人員或管理員可以設定優先級。", ephemeral=True)
                return
            
            # 更新優先級
            success = await self.DAO.update_ticket_priority(ticket['id'], priority)
            
            if success:
                priority_emoji = TicketConstants.PRIORITY_EMOJIS.get(priority, '🟡')
                priority_name = {'high': '高', 'medium': '中', 'low': '低'}.get(priority, priority)
                
                embed = EmbedBuilder.success(
                    "優先級已更新",
                    f"✅ 票券 #{ticket['id']:04d} 優先級已設定為 {priority_emoji} **{priority_name}優先級**"
                )
                
                # 根據優先級設定顏色
                embed.color = TicketConstants.PRIORITY_COLORS.get(priority, 0xffaa00)
                
                await interaction.response.send_message(embed=embed)
                
                # 如果是高優先級，通知管理員
                if priority == 'high':
                    await self._notify_high_priority_ticket(interaction.guild, ticket, interaction.user)
                    
                logger.info(f"票券 #{ticket['id']} 優先級設定為 {priority} by {interaction.user}")
            else:
                await interaction.response.send_message("❌ 更新優先級失敗，請稍後再試。", ephemeral=True)
                
        except Exception as e:
            logger.error(f"設定優先級錯誤: {e}")
            await interaction.response.send_message("❌ 設定過程中發生錯誤，請稍後再試。", ephemeral=True)

    @commands.command(name="priority_stats", aliases=["pstats"])
    @commands.has_permissions(manage_guild=True)
    async def priority_stats_command(self, ctx: commands.Context, days: int = 7):
        """
        查看優先級統計
        用法: !priority_stats [天數]
        """
        try:
            # 取得優先級統計
            stats = await self._get_priority_statistics(ctx.guild.id, days)
            
            if not stats:
                await ctx.send("❌ 無法取得優先級統計資料。")
                return
            
            embed = EmbedBuilder.build(
                title="📊 優先級統計分析",
                description=f"統計期間：過去 {days} 天",
                color=TicketConstants.COLORS['info']
            )
            
            # 優先級分佈
            total_tickets = sum(stats['distribution'].values())
            if total_tickets > 0:
                embed.add_field(
                    name="📈 優先級分佈",
                    value=f"🔴 高優先級：{stats['distribution']['high']} 張 ({stats['distribution']['high']/total_tickets*100:.1f}%)\n"
                          f"🟡 中優先級：{stats['distribution']['medium']} 張 ({stats['distribution']['medium']/total_tickets*100:.1f}%)\n"
                          f"🟢 低優先級：{stats['distribution']['low']} 張 ({stats['distribution']['low']/total_tickets*100:.1f}%)",
                    inline=False
                )
            
            # 處理時間統計
            if stats['avg_resolution_time']:
                embed.add_field(
                    name="⏱️ 平均處理時間",
                    value=f"🔴 高優先級：{stats['avg_resolution_time']['high']:.1f} 小時\n"
                          f"🟡 中優先級：{stats['avg_resolution_time']['medium']:.1f} 小時\n"
                          f"🟢 低優先級：{stats['avg_resolution_time']['low']:.1f} 小時",
                    inline=True
                )
            
            # 完成率統計
            if stats['completion_rate']:
                embed.add_field(
                    name="✅ 完成率",
                    value=f"🔴 高優先級：{stats['completion_rate']['high']:.1f}%\n"
                          f"🟡 中優先級：{stats['completion_rate']['medium']:.1f}%\n"
                          f"🟢 低優先級：{stats['completion_rate']['low']:.1f}%",
                    inline=True
                )
            
            # 當前開啟中的票券
            if stats['current_open']:
                embed.add_field(
                    name="📋 當前開啟中票券",
                    value=f"🔴 高優先級：{stats['current_open']['high']} 張\n"
                          f"🟡 中優先級：{stats['current_open']['medium']} 張\n"
                          f"🟢 低優先級：{stats['current_open']['low']} 張",
                    inline=False
                )
            
            await ctx.send(embed=embed)
            
        except Exception as e:
            logger.error(f"查看優先級統計錯誤: {e}")
            await ctx.send("❌ 查看統計時發生錯誤，請稍後再試。")

    async def _get_priority_statistics(self, guild_id: int, days: int) -> Dict[str, Any]:
        """取得優先級統計資料"""
        try:
            # 獲取指定天數內的票券資料
            end_date = datetime.now(timezone.utc)
            start_date = end_date - timedelta(days=days)
            
            tickets, _ = await self.DAO.get_tickets(guild_id, page_size=1000)  # 取得所有票券
            
            # 篩選時間範圍內的票券
            filtered_tickets = [
                t for t in tickets 
                if t['created_at'] >= start_date
            ]
            
            # 優先級分佈統計
            distribution = {'high': 0, 'medium': 0, 'low': 0}
            avg_resolution_time = {'high': [], 'medium': [], 'low': []}
            completion_rate = {'high': 0, 'medium': 0, 'low': 0}
            completion_count = {'high': 0, 'medium': 0, 'low': 0}
            current_open = {'high': 0, 'medium': 0, 'low': 0}
            
            for ticket in filtered_tickets:
                priority = ticket.get('priority', 'medium')
                if priority not in distribution:
                    priority = 'medium'
                
                distribution[priority] += 1
                
                if ticket['status'] == 'closed':
                    completion_count[priority] += 1
                    
                    # 計算處理時間
                    if ticket.get('closed_at') and ticket.get('created_at'):
                        duration = ticket['closed_at'] - ticket['created_at']
                        hours = duration.total_seconds() / 3600
                        avg_resolution_time[priority].append(hours)
                elif ticket['status'] == 'open':
                    current_open[priority] += 1
            
            # 計算平均處理時間
            for priority in avg_resolution_time:
                if avg_resolution_time[priority]:
                    avg_resolution_time[priority] = sum(avg_resolution_time[priority]) / len(avg_resolution_time[priority])
                else:
                    avg_resolution_time[priority] = 0
            
            # 計算完成率
            for priority in completion_rate:
                if distribution[priority] > 0:
                    completion_rate[priority] = (completion_count[priority] / distribution[priority]) * 100
                else:
                    completion_rate[priority] = 0
            
            return {
                'distribution': distribution,
                'avg_resolution_time': avg_resolution_time,
                'completion_rate': completion_rate,
                'current_open': current_open
            }
            
        except Exception as e:
            logger.error(f"取得優先級統計錯誤：{e}")
            return {}

    async def _notify_high_priority_ticket(self, guild: discord.Guild, ticket: Dict, user: discord.Member):
        """通知高優先級票券"""
        try:
            settings = await self.DAO.get_settings(guild.id)
            support_roles = settings.get('support_roles', [])
            
            if not support_roles:
                return
            
            # 找到票券頻道
            channel = guild.get_channel(ticket['channel_id'])
            if not channel:
                return
            
            # 建立通知嵌入
            embed = EmbedBuilder.build(
                title="🔴 高優先級票券通知",
                description=f"票券 #{ticket['id']:04d} 已設定為高優先級，需要優先處理！",
                color=TicketConstants.PRIORITY_COLORS['high']
            )
            
            embed.add_field(
                name="📋 票券資訊",
                value=f"• **類型**：{ticket['type']}\n"
                      f"• **建立者**：<@{ticket['discord_id']}>\n"
                      f"• **設定者**：{user.mention}",
                inline=False
            )
            
            embed.add_field(
                name="⏰ SLA 要求",
                value="高優先級票券預期在 **30分鐘內** 回應",
                inline=False
            )
            
            # 提及客服角色
            role_mentions = []
            for role_id in support_roles:
                role = guild.get_role(role_id)
                if role:
                    role_mentions.append(role.mention)
            
            content = " ".join(role_mentions) if role_mentions else ""
            
            await channel.send(content=content, embed=embed)
            
        except Exception as e:
            logger.error(f"通知高優先級票券錯誤: {e}")

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
                # 更新指派統計（如果票券有指派）
                if ticket.get('assigned_to'):
                    await self.assignment_manager.update_ticket_completion(ticket['id'])
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
        priority="優先級篩選",
        tag="標籤篩選（輸入標籤名稱）"
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
                          priority: str = "all", tag: str = None):
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
            
            # 處理標籤篩選
            if tag:
                # 先查找標籤
                tags = await self.tag_dao.get_tags_by_guild(interaction.guild.id)
                tag_obj = next((t for t in tags if t['name'].lower() == tag.lower()), None)
                
                if not tag_obj:
                    await interaction.response.send_message(f"❌ 找不到標籤 '{tag}'", ephemeral=True)
                    return
                
                # 取得使用此標籤的票券
                tagged_tickets = await self.tag_dao.get_tickets_by_tag(tag_obj['id'], 100)
                tagged_ticket_ids = [t['id'] for t in tagged_tickets]
                
                if not tagged_ticket_ids:
                    await interaction.response.send_message("📭 沒有找到使用此標籤的票券。", ephemeral=True)
                    return
                
                # 在已有條件基礎上進一步篩選
                tickets, total = await self.DAO.get_tickets(**query_params)
                
                # 篩選出有指定標籤的票券
                filtered_tickets = [t for t in tickets if t['id'] in tagged_ticket_ids]
                tickets = filtered_tickets
                total = len(tickets)
            else:
                tickets, total = await self.DAO.get_tickets(**query_params)
            
            if not tickets:
                await interaction.response.send_message("📭 沒有找到符合條件的票券。", ephemeral=True)
                return
                
            embed = await self._build_tickets_list_embed(
                tickets, total, status, user, priority, tag
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

    # ========== 標籤管理指令 ==========
    
    @commands.group(name="tag", aliases=["tags"], invoke_without_command=True)
    @commands.has_permissions(manage_guild=True)
    async def tag_group(self, ctx: commands.Context):
        """
        標籤管理指令群組
        用法: !tag <子指令>
        """
        if ctx.invoked_subcommand is None:
            # 顯示標籤列表
            formatted_list = await self.tag_manager.get_formatted_tag_list(ctx.guild.id)
            
            embed = EmbedBuilder.build(
                title="🏷️ 伺服器標籤列表",
                description=formatted_list,
                color=TicketConstants.COLORS['info']
            )
            
            embed.set_footer(text="使用 !tag help 查看更多指令")
            await ctx.send(embed=embed)

    @tag_group.command(name="create", aliases=["add"])
    async def create_tag(self, ctx: commands.Context, name: str, *, display_name: str):
        """
        創建新標籤
        用法: !tag create <標籤名> <顯示名稱>
        """
        try:
            success, message, tag_id = await self.tag_manager.create_tag(
                guild_id=ctx.guild.id,
                name=name,
                display_name=display_name,
                created_by=ctx.author.id
            )
            
            if success:
                embed = EmbedBuilder.success("標籤創建成功", message)
            else:
                embed = EmbedBuilder.error("創建失敗", message)
                
            await ctx.send(embed=embed)
            
        except Exception as e:
            logger.error(f"創建標籤錯誤: {e}")
            await ctx.send("❌ 創建標籤時發生錯誤，請稍後再試。")

    @tag_group.command(name="delete", aliases=["remove", "del"])
    async def delete_tag_command(self, ctx: commands.Context, tag_name: str):
        """
        刪除標籤
        用法: !tag delete <標籤名>
        """
        try:
            # 根據名稱查找標籤
            tags = await self.tag_dao.get_tags_by_guild(ctx.guild.id)
            tag = next((t for t in tags if t['name'].lower() == tag_name.lower()), None)
            
            if not tag:
                await ctx.send(f"❌ 找不到標籤 '{tag_name}'")
                return
            
            success, message = await self.tag_manager.delete_tag(tag['id'])
            
            if success:
                embed = EmbedBuilder.success("標籤刪除成功", message)
            else:
                embed = EmbedBuilder.error("刪除失敗", message)
                
            await ctx.send(embed=embed)
            
        except Exception as e:
            logger.error(f"刪除標籤錯誤: {e}")
            await ctx.send("❌ 刪除標籤時發生錯誤，請稍後再試。")

    @tag_group.command(name="init", aliases=["setup"])
    async def init_default_tags(self, ctx: commands.Context):
        """
        初始化預設標籤
        用法: !tag init
        """
        try:
            success, message, count = await self.tag_manager.initialize_default_tags(
                ctx.guild.id, ctx.author.id
            )
            
            if success:
                embed = EmbedBuilder.success("預設標籤初始化完成", message)
            else:
                embed = EmbedBuilder.error("初始化失敗", message)
                
            await ctx.send(embed=embed)
            
        except Exception as e:
            logger.error(f"初始化預設標籤錯誤: {e}")
            await ctx.send("❌ 初始化預設標籤時發生錯誤，請稍後再試。")

    @app_commands.command(name="add_tag", description="為票券添加標籤")
    @app_commands.describe(
        tag_name="標籤名稱",
        ticket_id="票券ID（可選，預設為當前頻道票券）"
    )
    async def add_tag_to_ticket_slash(self, interaction: discord.Interaction, 
                                     tag_name: str, ticket_id: int = None):
        """為票券添加標籤（slash指令）"""
        try:
            # 檢查權限
            settings = await self.DAO.get_settings(interaction.guild.id)
            is_staff = await self._is_support_staff(interaction.user, settings)
            
            if not (is_staff or interaction.user.guild_permissions.manage_guild):
                await interaction.response.send_message("❌ 只有客服人員或管理員可以添加標籤。", ephemeral=True)
                return
            
            # 取得票券
            if ticket_id:
                ticket = await self.DAO.get_ticket_by_id(ticket_id)
            else:
                if not await self._is_ticket_channel(interaction.channel):
                    await interaction.response.send_message("❌ 請在票券頻道中使用，或指定票券ID。", ephemeral=True)
                    return
                ticket = await self.DAO.get_ticket_by_channel(interaction.channel.id)
            
            if not ticket:
                await interaction.response.send_message("❌ 找不到指定的票券。", ephemeral=True)
                return
            
            # 查找標籤
            tags = await self.tag_dao.get_tags_by_guild(interaction.guild.id)
            tag = next((t for t in tags if t['name'].lower() == tag_name.lower()), None)
            
            if not tag:
                await interaction.response.send_message(f"❌ 找不到標籤 '{tag_name}'", ephemeral=True)
                return
            
            # 添加標籤
            success, message = await self.tag_manager.add_tag_to_ticket(
                ticket['id'], tag['id'], interaction.user.id
            )
            
            if success:
                embed = EmbedBuilder.success("標籤添加成功", message)
                await interaction.response.send_message(embed=embed)
            else:
                await interaction.response.send_message(f"❌ {message}", ephemeral=True)
                
        except Exception as e:
            logger.error(f"添加標籤錯誤: {e}")
            await interaction.response.send_message("❌ 添加標籤時發生錯誤，請稍後再試。", ephemeral=True)

    # ========== 統計面板指令 ==========
    
    @commands.command(name="dashboard", aliases=["stats", "statistics"])
    @commands.has_permissions(manage_guild=True)
    async def dashboard_command(self, ctx: commands.Context, days: int = 30):
        """
        顯示票券系統統計面板
        用法: !dashboard [天數]
        """
        try:
            if days < 1 or days > 365:
                await ctx.send("❌ 天數必須在 1-365 之間。")
                return
            
            # 顯示載入訊息
            loading_msg = await ctx.send("📊 正在生成統計面板...")
            
            # 取得統計數據
            dashboard_data = await self.statistics_manager.get_dashboard_statistics(ctx.guild.id, days)
            
            if not dashboard_data:
                await loading_msg.edit(content="❌ 無法生成統計數據，請稍後再試。")
                return
            
            # 建立統計面板嵌入
            embed = await self._build_dashboard_embed(dashboard_data, ctx.guild)
            
            await loading_msg.edit(content="", embed=embed)
            
        except Exception as e:
            logger.error(f"顯示統計面板錯誤: {e}")
            await ctx.send("❌ 生成統計面板時發生錯誤，請稍後再試。")

    @app_commands.command(name="realtime_stats", description="查看實時統計")
    async def realtime_stats(self, interaction: discord.Interaction):
        """查看實時統計（slash指令）"""
        try:
            # 檢查權限
            settings = await self.DAO.get_settings(interaction.guild.id)
            is_staff = await self._is_support_staff(interaction.user, settings)
            
            if not (is_staff or interaction.user.guild_permissions.manage_guild):
                await interaction.response.send_message("❌ 只有客服人員或管理員可以查看統計。", ephemeral=True)
                return
            
            # 取得實時統計
            stats = await self.statistics_manager.get_realtime_stats(interaction.guild.id)
            
            if not stats:
                await interaction.response.send_message("❌ 無法取得實時統計數據。", ephemeral=True)
                return
            
            embed = EmbedBuilder.build(
                title="📊 實時統計",
                description=f"更新時間：<t:{int(stats['last_updated'].timestamp())}:R>",
                color=TicketConstants.COLORS['info']
            )
            
            # 當前狀況
            embed.add_field(
                name="📋 當前狀況",
                value=f"• 開啟中票券：{stats['open_tickets']} 張\n"
                      f"• 今日新建：{stats['today_created']} 張\n"
                      f"• 今日完成：{stats['today_closed']} 張",
                inline=True
            )
            
            # 優先級分佈
            priority_dist = stats['priority_distribution']
            embed.add_field(
                name="🎯 優先級分佈",
                value=f"🔴 高：{priority_dist['high']} 張\n"
                      f"🟡 中：{priority_dist['medium']} 張\n"
                      f"🟢 低：{priority_dist['low']} 張",
                inline=True
            )
            
            # 客服狀態
            staff_status = stats['staff_status']
            embed.add_field(
                name="👥 客服狀態",
                value=f"• 在線客服：{staff_status['active']}/{staff_status['total']}\n"
                      f"• 利用率：{staff_status['utilization_rate']}%",
                inline=True
            )
            
            await interaction.response.send_message(embed=embed, ephemeral=True)
            
        except Exception as e:
            logger.error(f"查看實時統計錯誤: {e}")
            await interaction.response.send_message("❌ 查看統計時發生錯誤，請稍後再試。", ephemeral=True)

    @commands.command(name="report", aliases=["summary"])
    @commands.has_permissions(manage_guild=True)
    async def summary_report(self, ctx: commands.Context, days: int = 30):
        """
        生成統計摘要報告
        用法: !report [天數]
        """
        try:
            if days < 1 or days > 365:
                await ctx.send("❌ 天數必須在 1-365 之間。")
                return
            
            # 生成報告
            report = await self.statistics_manager.generate_summary_report(ctx.guild.id, days)
            
            if not report or report.startswith("❌"):
                await ctx.send(report or "❌ 生成報告失敗。")
                return
            
            # 如果報告太長，分段發送
            if len(report) > 2000:
                # 分段發送
                parts = []
                current_part = ""
                
                for line in report.split('\n'):
                    if len(current_part + line + '\n') > 1900:
                        parts.append(current_part.strip())
                        current_part = line + '\n'
                    else:
                        current_part += line + '\n'
                
                if current_part.strip():
                    parts.append(current_part.strip())
                
                for i, part in enumerate(parts):
                    if i == 0:
                        await ctx.send(part)
                    else:
                        await ctx.send(f"**（續）**\n{part}")
            else:
                await ctx.send(report)
                
        except Exception as e:
            logger.error(f"生成摘要報告錯誤: {e}")
            await ctx.send("❌ 生成報告時發生錯誤，請稍後再試。")

    async def _build_dashboard_embed(self, dashboard_data: Dict[str, Any], guild: discord.Guild) -> discord.Embed:
        """建立統計面板嵌入"""
        try:
            embed = EmbedBuilder.build(
                title="📊 票券系統統計面板",
                description=f"**{guild.name}** 的票券系統分析報告",
                color=TicketConstants.COLORS['primary']
            )
            
            # 基礎統計
            overview = dashboard_data.get('overview', {})
            if overview:
                embed.add_field(
                    name="📈 整體統計",
                    value=f"• 總票券：{overview.get('total_tickets', 0)} 張\n"
                          f"• 期間新建：{overview.get('period_created', 0)} 張\n"
                          f"• 開啟中：{overview.get('open_tickets', 0)} 張\n"
                          f"• 完成率：{overview.get('completion_rate', 0)}%\n"
                          f"• 平均處理：{overview.get('avg_processing_hours', 0)} 小時",
                    inline=True
                )
            
            # 優先級統計
            priority_stats = dashboard_data.get('priority_stats', {})
            if priority_stats:
                priority_text = []
                for priority, emoji in [('high', '🔴'), ('medium', '🟡'), ('low', '🟢')]:
                    stats = priority_stats.get(priority, {})
                    if stats:
                        priority_text.append(f"{emoji} {stats.get('count', 0)}張 ({stats.get('completion_rate', 0)}%)")
                
                embed.add_field(
                    name="🎯 優先級分析",
                    value="\n".join(priority_text) if priority_text else "無數據",
                    inline=True
                )
            
            # 團隊績效
            performance = dashboard_data.get('performance', {})
            if performance:
                embed.add_field(
                    name="👥 團隊績效",
                    value=f"• 客服人員：{performance.get('total_staff', 0)} 位\n"
                          f"• 總指派：{performance.get('total_assigned', 0)} 張\n"
                          f"• 團隊完成率：{performance.get('avg_completion_rate', 0)}%\n"
                          f"• 平均工作量：{performance.get('avg_current_load', 0)} 張",
                    inline=True
                )
            
            # 標籤洞察
            tag_insights = dashboard_data.get('tag_insights', {})
            if tag_insights:
                embed.add_field(
                    name="🏷️ 標籤使用",
                    value=f"• 總標籤：{tag_insights.get('total_tags', 0)} 個\n"
                          f"• 活躍標籤：{tag_insights.get('active_tags', 0)} 個\n"
                          f"• 使用率：{tag_insights.get('usage_rate', 0)}%\n"
                          f"• 總使用次數：{tag_insights.get('total_usage', 0)}",
                    inline=True
                )
            
            # 工作量分佈
            workload = dashboard_data.get('workload', {})
            if workload:
                distribution = workload.get('distribution', {})
                embed.add_field(
                    name="⚖️ 工作量分佈",
                    value=f"• 輕鬆：{distribution.get('light', 0)} 人\n"
                          f"• 適中：{distribution.get('moderate', 0)} 人\n"
                          f"• 繁忙：{distribution.get('heavy', 0)} 人\n"
                          f"• 超載：{distribution.get('overloaded', 0)} 人\n"
                          f"• 平衡分數：{workload.get('balance_score', 0)}/100",
                    inline=True
                )
            
            # 趨勢分析
            trends = dashboard_data.get('trends', {})
            if trends and trends.get('changes'):
                changes = trends['changes']
                created_emoji = "📈" if changes.get('created_change', 0) > 0 else "📉" if changes.get('created_change', 0) < 0 else "➡️"
                closed_emoji = "📈" if changes.get('closed_change', 0) > 0 else "📉" if changes.get('closed_change', 0) < 0 else "➡️"
                
                embed.add_field(
                    name="📊 趨勢變化",
                    value=f"• 新建票券：{created_emoji} {changes.get('created_change', 0):+.1f}%\n"
                          f"• 完成票券：{closed_emoji} {changes.get('closed_change', 0):+.1f}%",
                    inline=True
                )
            
            # 底部資訊
            period_days = dashboard_data.get('period_days', 30)
            generated_at = dashboard_data.get('generated_at')
            if generated_at:
                embed.set_footer(
                    text=f"統計期間：過去 {period_days} 天 | 生成時間：{generated_at.strftime('%Y-%m-%d %H:%M:%S')} UTC"
                )
            
            return embed
            
        except Exception as e:
            logger.error(f"建立統計面板嵌入錯誤：{e}")
            return EmbedBuilder.error("統計面板錯誤", "無法生成統計面板，請稍後再試。")

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
                                       priority: str, tag: str = None) -> discord.Embed:
        """
        建立票券列表嵌入訊息（優化優先級視覺化）
        """
        # 按優先級排序票券（高優先級在前）
        priority_order = {'high': 0, 'medium': 1, 'low': 2}
        sorted_tickets = sorted(tickets, key=lambda t: (
            priority_order.get(t.get('priority', 'medium'), 1),
            t['created_at']  # 同優先級按時間排序
        ))
        
        embed = EmbedBuilder.build(
            title="🎫 票券列表",
            color=TicketConstants.COLORS['info']
        )
        
        # 篩選條件與統計資訊
        filters = []
        if status != "all": filters.append(f"狀態: {status}")
        if user: filters.append(f"用戶: {user.display_name}")
        if priority != "all": filters.append(f"優先級: {priority}")
        if tag: filters.append(f"標籤: {tag}")
        
        # 添加優先級統計
        priority_stats = {'high': 0, 'medium': 0, 'low': 0}
        for ticket in sorted_tickets:
            ticket_priority = ticket.get('priority', 'medium')
            if ticket_priority in priority_stats:
                priority_stats[ticket_priority] += 1
        
        stats_text = f"🔴 {priority_stats['high']} | 🟡 {priority_stats['medium']} | 🟢 {priority_stats['low']}"
        
        if filters: 
            embed.description = f"**篩選條件：** {' | '.join(filters)}\n**優先級分佈：** {stats_text}"
        else:
            embed.description = f"**優先級分佈：** {stats_text}"
            
        # 分組顯示票券（按優先級）
        high_priority = [t for t in sorted_tickets if t.get('priority') == 'high']
        medium_priority = [t for t in sorted_tickets if t.get('priority', 'medium') == 'medium']
        low_priority = [t for t in sorted_tickets if t.get('priority') == 'low']
        
        displayed_count = 0
        max_display = 10
        
        # 優先顯示高優先級票券
        for priority_group, group_name, group_emoji in [
            (high_priority, "高優先級", "🔴"),
            (medium_priority, "中優先級", "🟡"), 
            (low_priority, "低優先級", "🟢")
        ]:
            if displayed_count >= max_display:
                break
                
            for ticket in priority_group:
                if displayed_count >= max_display:
                    break
                    
                status_emoji = TicketConstants.STATUS_EMOJIS.get(ticket['status'], '🟢')
                priority_emoji = TicketConstants.PRIORITY_EMOJIS.get(ticket.get('priority', 'medium'), '🟡')
                
                # 增強視覺化：添加狀態標籤和時間提示
                status_text = {
                    'open': '🟢 進行中',
                    'closed': '🔒 已關閉',
                    'archived': '🗄️ 已歸檔'
                }.get(ticket['status'], ticket['status'].upper())
                
                field_value = f"{priority_emoji} **{group_name}** | {status_text}\n"
                field_value += f"👤 <@{ticket['discord_id']}>\n"
                
                # 時間資訊（根據狀態顯示不同資訊）
                if ticket['status'] == 'open':
                    time_info = f"📅 建立於 {get_time_ago(ticket['created_at'])}"
                    # 添加 SLA 狀態提示
                    if ticket.get('priority') == 'high':
                        created_time = ticket['created_at']
                        now = datetime.now(timezone.utc)
                        elapsed_minutes = (now - created_time).total_seconds() / 60
                        if elapsed_minutes > 30:  # 高優先級 30 分鐘 SLA
                            time_info += " ⚠️ **SLA超時**"
                        elif elapsed_minutes > 20:
                            time_info += " 🟠 **即將超時**"
                else:
                    time_info = f"📅 {get_time_ago(ticket['created_at'])}"
                
                field_value += time_info
                
                # 指派資訊
                if ticket.get('assigned_to'):
                    field_value += f"\n👥 負責客服：<@{ticket['assigned_to']}>"
                
                # 評分資訊
                if ticket.get('rating'):
                    stars = "⭐" * ticket['rating']
                    field_value += f"\n{stars} 已評分"
                
                # 標籤資訊
                ticket_tags = await self.tag_dao.get_ticket_tags(ticket['id'])
                if ticket_tags:
                    tag_displays = []
                    for tag in ticket_tags[:3]:  # 最多顯示3個標籤
                        emoji = tag.get('emoji', '')
                        tag_display = f"{emoji}{tag['display_name']}" if emoji else tag['display_name']
                        tag_displays.append(tag_display)
                    
                    if len(ticket_tags) > 3:
                        tag_displays.append(f"+{len(ticket_tags) - 3}")
                    
                    field_value += f"\n🏷️ {' • '.join(tag_displays)}"
                
                # 頻道連結（僅開啟中的票券）
                if ticket['status'] == 'open':
                    field_value += f"\n📍 <#{ticket['channel_id']}>"
                
                # 票券標題加上優先級標識
                ticket_title = f"#{ticket['id']:04d} {priority_emoji} {ticket['type']}"
                
                embed.add_field(
                    name=ticket_title,
                    value=field_value,
                    inline=True
                )
                
                displayed_count += 1
        
        # 底部資訊
        footer_text = f"共 {total} 筆記錄，按優先級排序"
        if total > max_display:
            footer_text += f"（顯示前 {displayed_count} 筆）"
        if high_priority:
            footer_text += f" | 🔴 有 {len(high_priority)} 張高優先級票券"
            
        embed.set_footer(text=footer_text)
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
                        ticket_id=ticket['ticket_id'],
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
                                    description=f"您的票券 #{ticket['ticket_id']:04d} 因無活動超過 {hours_threshold} 小時已自動關閉。",
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
                    logger.error(f"自動關閉票券 #{ticket['ticket_id']:04d} 錯誤: {e}")
                    continue
            return closed_count
        except Exception as e:
            logger.error(f"自動關閉無活動票券錯誤: {e}")
            return 0

async def setup(bot: commands.Bot):
    """
    載入 TicketCore cog。
    """
    cog = TicketCore(bot)
    await bot.add_cog(cog)
    
    # 驗證指令是否正確註冊
    commands_registered = []
    for command in cog.get_commands():
        commands_registered.append(command.name)
    
    logger.info(f"✅ 票券核心系統已載入，註冊的指令: {', '.join(commands_registered)}")
    
    # 特別檢查 ticket_settings
    if any(cmd.name == "ticket_settings" for cmd in cog.get_commands()):
        logger.info("✅ ticket_settings 指令已成功註冊")
    else:
        logger.error("❌ ticket_settings 指令註冊失敗")
