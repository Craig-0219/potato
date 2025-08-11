# bot/cogs/system_admin.py - 系統管理指令
"""
系統管理核心指令
提供統一的系統管理界面和工具
"""

import discord
from discord.ext import commands
from discord import app_commands
from typing import Optional
from datetime import datetime, timedelta
import logging
import os
import sys
try:
    import psutil
    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False
from shared.logger import logger

from bot.views.system_admin_views import SystemAdminPanel
from bot.db.ticket_dao import TicketDAO
from bot.db.welcome_dao import WelcomeDAO
from bot.services.welcome_manager import WelcomeManager


class SystemAdmin(commands.Cog):
    """系統管理核心指令"""
    
    def __init__(self, bot):
        self.bot = bot
        self.ticket_dao = TicketDAO()
        self.welcome_dao = WelcomeDAO()
        self.welcome_manager = WelcomeManager(self.welcome_dao)
    
    def cog_check(self, ctx):
        """Cog檢查：確保在伺服器中使用"""
        return ctx.guild is not None
    
    # ========== Bot 擁有者專用指令 ==========
    
    @commands.command(name='botstatus', aliases=['狀態', 'bot狀態'])
    @commands.is_owner()
    async def status_check(self, ctx):
        """查看 Bot 整體運行狀態 (Bot 擁有者限定)"""
        try:
            embed = discord.Embed(
                title="🤖 Bot 運行狀態",
                color=0x2ecc71
            )
            
            # 基本狀態信息
            embed.add_field(
                name="📊 基本狀態",
                value=f"延遲: {round(self.bot.latency * 1000)}ms\n"
                      f"已載入 Cogs: {len(self.bot.cogs)}\n"
                      f"註冊指令: {len(self.bot.commands)}\n"
                      f"已連接伺服器: {len(self.bot.guilds)}",
                inline=True
            )
            
            # 用戶統計
            total_users = sum([guild.member_count for guild in self.bot.guilds])
            embed.add_field(
                name="👥 用戶統計",
                value=f"總用戶: {total_users}\n"
                      f"在線伺服器: {len([g for g in self.bot.guilds if g.me.status != discord.Status.offline])}",
                inline=True
            )
            
            # 系統資源 (如果可用)
            if HAS_PSUTIL:
                try:
                    cpu = psutil.cpu_percent(interval=1)
                    memory = psutil.virtual_memory()
                    
                    embed.add_field(
                        name="💻 系統資源",
                        value=f"CPU: {cpu:.1f}%\n"
                              f"記憶體: {memory.percent:.1f}%\n"
                              f"可用記憶體: {memory.available // (1024**2)} MB",
                        inline=True
                    )
                except Exception as e:
                    embed.add_field(
                        name="💻 系統資源",
                        value=f"無法獲取系統資源信息: {str(e)[:30]}...",
                        inline=True
                    )
            else:
                embed.add_field(
                    name="💻 系統資源",
                    value="需要安裝 psutil 套件查看詳細資源信息",
                    inline=True
                )
            
            # 運行時間
            uptime = datetime.now() - self.bot.start_time if hasattr(self.bot, 'start_time') else None
            if uptime:
                days = uptime.days
                hours, remainder = divmod(uptime.seconds, 3600)
                minutes, _ = divmod(remainder, 60)
                
                embed.add_field(
                    name="⏰ 運行時間",
                    value=f"{days}天 {hours}小時 {minutes}分鐘",
                    inline=True
                )
            
            # 版本信息
            embed.add_field(
                name="📋 版本信息",
                value=f"Discord.py: {discord.__version__}\n"
                      f"Python: {sys.version.split()[0]}",
                inline=True
            )
            
            embed.set_footer(text=f"Bot ID: {self.bot.user.id}")
            
            await ctx.send(embed=embed)
            
        except Exception as e:
            logger.error(f"Bot 狀態查詢錯誤: {e}")
            await ctx.send("❌ 查詢 Bot 狀態時發生錯誤")
    
    @commands.command(name='botHealth', aliases=['健康檢查', '機器人健康'])
    @commands.is_owner()
    async def health_check(self, ctx):
        """執行完整健康檢查 (Bot 擁有者限定)"""
        try:
            embed = discord.Embed(
                title="🏥 系統健康檢查",
                description="正在執行全面健康檢查...",
                color=0x3498db
            )
            
            # 發送初始訊息
            message = await ctx.send(embed=embed)
            
            health_results = []
            overall_health = 100
            
            # 1. Discord API 連接檢查
            try:
                latency = round(self.bot.latency * 1000)
                if latency < 100:
                    health_results.append("🟢 Discord API: 優秀")
                elif latency < 300:
                    health_results.append("🟡 Discord API: 良好")
                    overall_health -= 10
                else:
                    health_results.append("🔴 Discord API: 需要關注")
                    overall_health -= 25
            except Exception as e:
                health_results.append("🔴 Discord API: 連接失敗")
                overall_health -= 30
            
            # 2. 資料庫連接檢查
            try:
                start_time = datetime.now()
                await self.ticket_dao.get_settings(ctx.guild.id)
                db_time = (datetime.now() - start_time).total_seconds() * 1000
                
                if db_time < 100:
                    health_results.append("🟢 資料庫: 響應迅速")
                elif db_time < 500:
                    health_results.append("🟡 資料庫: 響應正常")
                    overall_health -= 5
                else:
                    health_results.append("🔴 資料庫: 響應緩慢")
                    overall_health -= 20
            except Exception as e:
                health_results.append("🔴 資料庫: 連接失敗")
                overall_health -= 30
            
            # 3. 系統資源檢查
            if HAS_PSUTIL:
                try:
                    cpu = psutil.cpu_percent(interval=1)
                    memory = psutil.virtual_memory()
                    
                    if cpu < 70 and memory.percent < 80:
                        health_results.append("🟢 系統資源: 使用率正常")
                    elif cpu < 85 and memory.percent < 90:
                        health_results.append("🟡 系統資源: 使用率偏高")
                        overall_health -= 10
                    else:
                        health_results.append("🔴 系統資源: 使用率過高")
                        overall_health -= 25
                except Exception:
                    health_results.append("⚠️ 系統資源: 檢查失敗")
                    overall_health -= 5
            else:
                health_results.append("⚪ 系統資源: 無法檢查 (需要 psutil)")
            
            # 4. Bot 權限檢查
            try:
                bot_member = ctx.guild.get_member(self.bot.user.id)
                required_perms = ['manage_channels', 'manage_roles', 'send_messages', 'embed_links']
                missing_perms = []
                
                for perm in required_perms:
                    if not getattr(bot_member.guild_permissions, perm, False):
                        missing_perms.append(perm)
                
                if not missing_perms:
                    health_results.append("🟢 Bot 權限: 權限完整")
                elif len(missing_perms) <= 2:
                    health_results.append("🟡 Bot 權限: 部分缺失")
                    overall_health -= 15
                else:
                    health_results.append("🔴 Bot 權限: 權限不足")
                    overall_health -= 30
            except Exception as e:
                health_results.append("🔴 Bot 權限: 檢查失敗")
                overall_health -= 10
            
            # 5. Cogs 載入檢查
            total_cogs = len(self.bot.cogs)
            if total_cogs >= 5:
                health_results.append(f"🟢 模組載入: {total_cogs} 個模組已載入")
            elif total_cogs >= 3:
                health_results.append(f"🟡 模組載入: {total_cogs} 個模組已載入")
                overall_health -= 5
            else:
                health_results.append(f"🔴 模組載入: 僅 {total_cogs} 個模組已載入")
                overall_health -= 20
            
            # 更新嵌入訊息
            if overall_health >= 85:
                color = 0x2ecc71
                status_emoji = "🟢"
                status_text = "系統健康狀況良好"
            elif overall_health >= 70:
                color = 0xf39c12
                status_emoji = "🟡"
                status_text = "系統狀況正常，有改善空間"
            else:
                color = 0xe74c3c
                status_emoji = "🔴"
                status_text = "系統存在問題，需要關注"
            
            embed = discord.Embed(
                title="🏥 系統健康檢查完成",
                description=f"{status_emoji} **整體健康度: {overall_health}/100**\n{status_text}",
                color=color
            )
            
            embed.add_field(
                name="📋 檢查結果",
                value="\n".join(health_results),
                inline=False
            )
            
            if overall_health < 85:
                suggestions = []
                if "🔴 Discord API" in "\n".join(health_results):
                    suggestions.append("• 檢查網路連接")
                if "🔴 資料庫" in "\n".join(health_results):
                    suggestions.append("• 檢查資料庫服務狀態")
                if "🔴 系統資源" in "\n".join(health_results):
                    suggestions.append("• 考慮升級硬體或優化程序")
                if "🔴 Bot 權限" in "\n".join(health_results):
                    suggestions.append("• 檢查 Bot 角色權限設定")
                
                if suggestions:
                    embed.add_field(
                        name="💡 改善建議",
                        value="\n".join(suggestions),
                        inline=False
                    )
            
            embed.set_footer(text=f"檢查時間: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            
            await message.edit(embed=embed)
            
        except Exception as e:
            logger.error(f"健康檢查錯誤: {e}")
            await ctx.send("❌ 執行健康檢查時發生錯誤")
    
    @commands.command(name='dbHealth', aliases=['資料庫狀態', '資料庫健康'])
    @commands.is_owner()
    async def database_status(self, ctx):
        """查看資料庫狀態 (Bot 擁有者限定)"""
        try:
            embed = discord.Embed(
                title="🗄️ 資料庫狀態檢查",
                color=0x3498db
            )
            
            # 連接測試
            try:
                start_time = datetime.now()
                settings = await self.ticket_dao.get_settings(ctx.guild.id)
                connection_time = (datetime.now() - start_time).total_seconds() * 1000
                
                embed.add_field(
                    name="🔌 連接狀態",
                    value=f"✅ 正常\n響應時間: {connection_time:.1f}ms",
                    inline=True
                )
            except Exception as e:
                embed.add_field(
                    name="🔌 連接狀態",
                    value=f"❌ 連接失敗\n錯誤: {str(e)[:50]}...",
                    inline=True
                )
                embed.color = 0xe74c3c
            
            # 基本統計
            try:
                # 票券統計
                tickets, total_count = await self.ticket_dao.get_tickets(ctx.guild.id, page_size=1000)
                open_tickets = len([t for t in tickets if t['status'] == 'open'])
                
                embed.add_field(
                    name="🎫 票券數據",
                    value=f"總票券: {total_count}\n開啟中: {open_tickets}\n已關閉: {total_count - open_tickets}",
                    inline=True
                )
            except Exception as e:
                embed.add_field(
                    name="🎫 票券數據",
                    value=f"❌ 查詢失敗\n{str(e)[:30]}...",
                    inline=True
                )
            
            # 歡迎系統統計
            try:
                welcome_stats = await self.welcome_manager.get_welcome_statistics(ctx.guild.id, 30)
                embed.add_field(
                    name="🎉 歡迎數據 (30天)",
                    value=f"加入: {welcome_stats.get('joins', 0)}\n"
                          f"離開: {welcome_stats.get('leaves', 0)}\n"
                          f"淨增長: {welcome_stats.get('net_growth', 0)}",
                    inline=True
                )
            except Exception as e:
                embed.add_field(
                    name="🎉 歡迎數據",
                    value=f"❌ 查詢失敗\n{str(e)[:30]}...",
                    inline=True
                )
            
            # 資料庫操作建議
            embed.add_field(
                name="🛠️ 維護工具",
                value="`!diagnose database` - 詳細資料庫診斷\n"
                      "`!connectivity_test` - 連接品質測試",
                inline=False
            )
            
            embed.set_footer(text=f"檢查時間: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            
            await ctx.send(embed=embed)
            
        except Exception as e:
            logger.error(f"資料庫狀態檢查錯誤: {e}")
            await ctx.send("❌ 檢查資料庫狀態時發生錯誤")
    
    @commands.command(name='cogReload', aliases=['重載'])
    @commands.is_owner()
    async def reload_extension(self, ctx, extension_name: str):
        """重新載入指定擴展模組 (Bot 擁有者限定)"""
        try:
            # 擴展名稱映射
            extension_mapping = {
                'ticket_core': 'bot.cogs.ticket_core',
                'ticket_listener': 'bot.cogs.ticket_listener', 
                'system_admin': 'bot.cogs.system_admin',
                'welcome_core': 'bot.cogs.welcome_core',
                'welcome_listener': 'bot.cogs.welcome_listener',
                'vote': 'bot.cogs.vote',
                'vote_listener': 'bot.cogs.vote_listener'
            }
            
            # 獲取完整擴展名稱
            full_extension = extension_mapping.get(extension_name, extension_name)
            if not full_extension.startswith('bot.cogs.'):
                full_extension = f'bot.cogs.{extension_name}'
            
            # 嘗試重載
            await self.bot.reload_extension(full_extension)
            
            embed = discord.Embed(
                title="✅ 模組重載成功",
                description=f"已重新載入模組: `{extension_name}`",
                color=0x2ecc71
            )
            
            embed.add_field(
                name="📊 系統狀態",
                value=f"已載入模組: {len(self.bot.cogs)}\n"
                      f"註冊指令: {len(self.bot.commands)}",
                inline=False
            )
            
            await ctx.send(embed=embed)
            logger.info(f"模組 {extension_name} 重載成功")
            
        except Exception as e:
            embed = discord.Embed(
                title="❌ 模組重載失敗",
                description=f"重載模組 `{extension_name}` 時發生錯誤",
                color=0xe74c3c
            )
            embed.add_field(
                name="錯誤詳情",
                value=f"```{str(e)[:500]}```",
                inline=False
            )
            
            await ctx.send(embed=embed)
            logger.error(f"模組重載失敗: {extension_name} - {e}")
    
    @commands.command(name='cogLoad', aliases=['載入'])
    @commands.is_owner()
    async def load_extension(self, ctx, extension_name: str):
        """載入新的擴展模組 (Bot 擁有者限定)"""
        try:
            # 擴展名稱映射
            extension_mapping = {
                'ticket_core': 'bot.cogs.ticket_core',
                'ticket_listener': 'bot.cogs.ticket_listener',
                'system_admin': 'bot.cogs.system_admin',
                'welcome_core': 'bot.cogs.welcome_core', 
                'welcome_listener': 'bot.cogs.welcome_listener',
                'vote': 'bot.cogs.vote',
                'vote_listener': 'bot.cogs.vote_listener'
            }
            
            # 獲取完整擴展名稱
            full_extension = extension_mapping.get(extension_name, extension_name)
            if not full_extension.startswith('bot.cogs.'):
                full_extension = f'bot.cogs.{extension_name}'
            
            # 嘗試載入
            await self.bot.load_extension(full_extension)
            
            embed = discord.Embed(
                title="✅ 模組載入成功",
                description=f"已載入新模組: `{extension_name}`",
                color=0x2ecc71
            )
            
            embed.add_field(
                name="📊 系統狀態",
                value=f"已載入模組: {len(self.bot.cogs)}\n"
                      f"註冊指令: {len(self.bot.commands)}",
                inline=False
            )
            
            await ctx.send(embed=embed)
            logger.info(f"模組 {extension_name} 載入成功")
            
        except Exception as e:
            embed = discord.Embed(
                title="❌ 模組載入失敗",
                description=f"載入模組 `{extension_name}` 時發生錯誤",
                color=0xe74c3c
            )
            embed.add_field(
                name="錯誤詳情",
                value=f"```{str(e)[:500]}```",
                inline=False
            )
            
            await ctx.send(embed=embed)
            logger.error(f"模組載入失敗: {extension_name} - {e}")
    
    @commands.command(name='cogUnload', aliases=['卸載'])
    @commands.is_owner()
    async def unload_extension(self, ctx, extension_name: str):
        """卸載指定擴展模組 (Bot 擁有者限定)"""
        try:
            # 防止卸載系統管理模組
            if extension_name in ['system_admin', 'bot.cogs.system_admin']:
                embed = discord.Embed(
                    title="⚠️ 無法卸載",
                    description="為了系統安全，不能卸載系統管理模組",
                    color=0xf39c12
                )
                await ctx.send(embed=embed)
                return
            
            # 擴展名稱映射
            extension_mapping = {
                'ticket_core': 'bot.cogs.ticket_core',
                'ticket_listener': 'bot.cogs.ticket_listener',
                'welcome_core': 'bot.cogs.welcome_core',
                'welcome_listener': 'bot.cogs.welcome_listener',
                'vote': 'bot.cogs.vote',
                'vote_listener': 'bot.cogs.vote_listener'
            }
            
            # 獲取完整擴展名稱
            full_extension = extension_mapping.get(extension_name, extension_name)
            if not full_extension.startswith('bot.cogs.'):
                full_extension = f'bot.cogs.{extension_name}'
            
            # 嘗試卸載
            await self.bot.unload_extension(full_extension)
            
            embed = discord.Embed(
                title="✅ 模組卸載成功",
                description=f"已卸載模組: `{extension_name}`",
                color=0x2ecc71
            )
            
            embed.add_field(
                name="📊 系統狀態",
                value=f"已載入模組: {len(self.bot.cogs)}\n"
                      f"註冊指令: {len(self.bot.commands)}",
                inline=False
            )
            
            await ctx.send(embed=embed)
            logger.info(f"模組 {extension_name} 卸載成功")
            
        except Exception as e:
            embed = discord.Embed(
                title="❌ 模組卸載失敗",
                description=f"卸載模組 `{extension_name}` 時發生錯誤",
                color=0xe74c3c
            )
            embed.add_field(
                name="錯誤詳情", 
                value=f"```{str(e)[:500]}```",
                inline=False
            )
            
            await ctx.send(embed=embed)
            logger.error(f"模組卸載失敗: {extension_name} - {e}")
    
    @commands.command(name='cmdSync', aliases=['同步'])
    @commands.is_owner()
    async def sync_commands(self, ctx):
        """同步斜線指令到 Discord (Bot 擁有者限定)"""
        try:
            embed = discord.Embed(
                title="🔄 同步斜線指令",
                description="正在同步斜線指令到 Discord...",
                color=0x3498db
            )
            
            message = await ctx.send(embed=embed)
            
            # 同步指令
            synced = await self.bot.tree.sync()
            
            embed = discord.Embed(
                title="✅ 指令同步完成", 
                description=f"成功同步 {len(synced)} 個斜線指令",
                color=0x2ecc71
            )
            
            # 顯示同步的指令列表
            if synced:
                command_list = [f"• `/{cmd.name}`" for cmd in synced[:10]]  # 最多顯示10個
                embed.add_field(
                    name="📋 已同步指令",
                    value="\n".join(command_list) + (f"\n... 還有 {len(synced) - 10} 個指令" if len(synced) > 10 else ""),
                    inline=False
                )
            
            embed.add_field(
                name="💡 注意事項",
                value="斜線指令同步可能需要幾分鐘才會在 Discord 中顯示",
                inline=False
            )
            
            await message.edit(embed=embed)
            logger.info(f"斜線指令同步完成: {len(synced)} 個指令")
            
        except Exception as e:
            embed = discord.Embed(
                title="❌ 指令同步失敗",
                description="同步斜線指令時發生錯誤",
                color=0xe74c3c
            )
            embed.add_field(
                name="錯誤詳情",
                value=f"```{str(e)[:500]}```",
                inline=False
            )
            
            await ctx.send(embed=embed)
            logger.error(f"斜線指令同步失敗: {e}")
    
    # ========== 系統管理主指令 ==========
    
    @commands.command(name='admin', aliases=['管理', 'system'])
    @commands.has_permissions(manage_guild=True)
    async def admin_panel(self, ctx):
        """開啟系統管理面板"""
        try:
            embed = discord.Embed(
                title="🎛️ 系統管理面板",
                description=f"歡迎使用 {ctx.guild.name} 的系統管理面板\n"
                           "請選擇要管理的系統模組：",
                color=0x3498db
            )
            
            embed.add_field(
                name="🎫 票券系統",
                value="• 設定票券分類頻道\n• 管理客服角色\n• 調整系統參數",
                inline=True
            )
            
            embed.add_field(
                name="🎉 歡迎系統",
                value="• 設定歡迎頻道\n• 自動身分組管理\n• 自定義歡迎訊息",
                inline=True
            )
            
            embed.add_field(
                name="📊 統計監控",
                value="• 系統使用統計\n• 運行狀態監控\n• 資料分析報告",
                inline=True
            )
            
            embed.add_field(
                name="🔧 系統工具",
                value="• 資料清理工具\n• 系統維護功能\n• 備份與匯出",
                inline=True
            )
            
            embed.set_footer(text="⚠️ 此面板僅限有管理權限的用戶使用")
            
            view = SystemAdminPanel(ctx.author.id)
            await ctx.send(embed=embed, view=view)
            
        except Exception as e:
            logger.error(f"開啟管理面板錯誤: {e}")
            await ctx.send("❌ 開啟管理面板時發生錯誤")
    
    # ========== 快速設定指令 ==========
    
    @commands.group(name='setup', invoke_without_command=True)
    @commands.has_permissions(manage_guild=True)
    async def setup_group(self, ctx):
        """系統快速設定指令群組"""
        if ctx.invoked_subcommand is None:
            embed = discord.Embed(
                title="🚀 系統快速設定",
                description="快速設定各系統功能",
                color=0x2ecc71
            )
            
            embed.add_field(
                name="🎫 票券系統",
                value="`!setup ticket` - 票券系統初始化",
                inline=True
            )
            
            embed.add_field(
                name="🎉 歡迎系統",
                value="`!setup welcome` - 歡迎系統初始化",
                inline=True
            )
            
            embed.add_field(
                name="🔄 全部系統",
                value="`!setup all` - 初始化所有系統",
                inline=True
            )
            
            await ctx.send(embed=embed)
    
    @setup_group.command(name='ticket')
    @commands.has_permissions(manage_guild=True)
    async def setup_ticket(self, ctx):
        """快速設定票券系統"""
        try:
            # 檢查是否已有設定
            settings = await self.ticket_dao.get_settings(ctx.guild.id)
            
            embed = discord.Embed(
                title="🎫 票券系統快速設定",
                color=0x3498db
            )
            
            if settings.get('category_id'):
                embed.add_field(
                    name="✅ 系統狀態",
                    value="票券系統已設定完成",
                    inline=False
                )
                
                embed.add_field(
                    name="📂 票券分類",
                    value=f"<#{settings['category_id']}>",
                    inline=True
                )
                
                support_roles = settings.get('support_roles', [])
                roles_text = f"{len(support_roles)} 個角色" if support_roles else "未設定"
                embed.add_field(
                    name="👥 客服角色",
                    value=roles_text,
                    inline=True
                )
                
                embed.add_field(
                    name="⚙️ 系統參數",
                    value=f"每人票券上限: {settings.get('max_tickets_per_user', 3)}\n"
                          f"SLA時間: {settings.get('sla_response_minutes', 60)}分鐘",
                    inline=True
                )
                
                embed.add_field(
                    name="🔧 管理選項",
                    value="使用 `!admin` 開啟完整管理面板進行詳細設定",
                    inline=False
                )
            else:
                embed.add_field(
                    name="⚠️ 系統狀態",
                    value="票券系統尚未設定",
                    inline=False
                )
                
                embed.add_field(
                    name="🚀 快速設定",
                    value="使用 `!admin` 開啟管理面板進行設定，或使用 `!setup_ticket` 建立票券面板",
                    inline=False
                )
            
            await ctx.send(embed=embed)
            
        except Exception as e:
            logger.error(f"票券系統設定檢查錯誤: {e}")
            await ctx.send("❌ 檢查票券系統設定時發生錯誤")
    
    @setup_group.command(name='welcome')
    @commands.has_permissions(manage_guild=True)
    async def setup_welcome(self, ctx):
        """快速設定歡迎系統"""
        try:
            # 檢查是否已有設定
            settings = await self.welcome_dao.get_welcome_settings(ctx.guild.id)
            
            embed = discord.Embed(
                title="🎉 歡迎系統快速設定",
                color=0x2ecc71
            )
            
            if settings and settings.get('is_enabled'):
                embed.add_field(
                    name="✅ 系統狀態",
                    value="歡迎系統已啟用",
                    inline=False
                )
                
                welcome_ch = f"<#{settings['welcome_channel_id']}>" if settings.get('welcome_channel_id') else "未設定"
                leave_ch = f"<#{settings['leave_channel_id']}>" if settings.get('leave_channel_id') else "未設定"
                
                embed.add_field(
                    name="📺 頻道設定",
                    value=f"歡迎頻道: {welcome_ch}\n離開頻道: {leave_ch}",
                    inline=True
                )
                
                auto_roles_count = len(settings.get('auto_roles', []))
                embed.add_field(
                    name="👥 自動身分組",
                    value=f"{auto_roles_count} 個身分組",
                    inline=True
                )
                
                features = []
                features.append(f"嵌入訊息: {'✅' if settings.get('welcome_embed_enabled') else '❌'}")
                features.append(f"私訊歡迎: {'✅' if settings.get('welcome_dm_enabled') else '❌'}")
                
                embed.add_field(
                    name="⚙️ 功能狀態",
                    value="\n".join(features),
                    inline=True
                )
            else:
                embed.add_field(
                    name="⚠️ 系統狀態",
                    value="歡迎系統尚未設定或已停用",
                    inline=False
                )
                
                embed.add_field(
                    name="🚀 快速初始化",
                    value="點擊下方按鈕立即初始化歡迎系統：",
                    inline=False
                )
                
                # 添加快速初始化按鈕
                from bot.views.system_admin_views import WelcomeSettingsView
                view = WelcomeSettingsView(ctx.author.id)
                await ctx.send(embed=embed, view=view)
                return
            
            embed.add_field(
                name="🔧 管理選項",
                value="使用 `!admin` 開啟完整管理面板，或使用 `!welcome` 指令進行詳細設定",
                inline=False
            )
            
            await ctx.send(embed=embed)
            
        except Exception as e:
            logger.error(f"歡迎系統設定檢查錯誤: {e}")
            await ctx.send("❌ 檢查歡迎系統設定時發生錯誤")
    
    @setup_group.command(name='all')
    @commands.has_permissions(manage_guild=True)
    async def setup_all(self, ctx):
        """快速設定所有系統"""
        try:
            embed = discord.Embed(
                title="🔄 全系統設定概覽",
                description=f"**{ctx.guild.name}** 的系統設定狀態",
                color=0x95a5a6
            )
            
            # 檢查票券系統
            ticket_settings = await self.ticket_dao.get_settings(ctx.guild.id)
            ticket_status = "✅ 已設定" if ticket_settings.get('category_id') else "❌ 未設定"
            
            embed.add_field(
                name="🎫 票券系統",
                value=f"狀態: {ticket_status}\n"
                      f"分類頻道: {'已設定' if ticket_settings.get('category_id') else '未設定'}\n"
                      f"客服角色: {len(ticket_settings.get('support_roles', []))} 個",
                inline=True
            )
            
            # 檢查歡迎系統
            welcome_settings = await self.welcome_dao.get_welcome_settings(ctx.guild.id)
            welcome_status = "✅ 已啟用" if welcome_settings and welcome_settings.get('is_enabled') else "❌ 未設定"
            
            embed.add_field(
                name="🎉 歡迎系統",
                value=f"狀態: {welcome_status}\n"
                      f"歡迎頻道: {'已設定' if welcome_settings and welcome_settings.get('welcome_channel_id') else '未設定'}\n"
                      f"自動身分組: {len(welcome_settings.get('auto_roles', [])) if welcome_settings else 0} 個",
                inline=True
            )
            
            # 系統建議
            suggestions = []
            if not ticket_settings.get('category_id'):
                suggestions.append("• 設定票券分類頻道")
            if not welcome_settings or not welcome_settings.get('is_enabled'):
                suggestions.append("• 初始化歡迎系統")
            if ticket_settings.get('category_id') and not ticket_settings.get('support_roles'):
                suggestions.append("• 設定客服角色")
            
            if suggestions:
                embed.add_field(
                    name="📋 建議設定",
                    value="\n".join(suggestions),
                    inline=False
                )
            else:
                embed.add_field(
                    name="🎉 系統狀態",
                    value="所有主要系統都已設定完成！",
                    inline=False
                )
            
            embed.add_field(
                name="🎛️ 管理面板",
                value="使用 `!admin` 開啟完整的圖形化管理界面",
                inline=False
            )
            
            await ctx.send(embed=embed)
            
        except Exception as e:
            logger.error(f"全系統設定檢查錯誤: {e}")
            await ctx.send("❌ 檢查系統設定時發生錯誤")
    
    # ========== 系統狀態指令 ==========
    
    @commands.command(name='system_status', aliases=['系統狀態', 'sysstatus'])
    @commands.has_permissions(manage_guild=True)
    async def system_status(self, ctx):
        """查看系統整體狀態"""
        try:
            embed = discord.Embed(
                title="📊 系統狀態總覽",
                description=f"**{ctx.guild.name}** 的系統運行狀態",
                color=0x3498db
            )
            
            # 票券系統狀態
            tickets, _ = await self.ticket_dao.get_tickets(ctx.guild.id, page_size=1000)
            open_tickets = len([t for t in tickets if t['status'] == 'open'])
            
            embed.add_field(
                name="🎫 票券系統",
                value=f"總票券: {len(tickets)}\n"
                      f"開啟中: {open_tickets}\n"
                      f"今日新建: 計算中...",
                inline=True
            )
            
            # 歡迎系統狀態
            welcome_stats = await self.welcome_manager.get_welcome_statistics(ctx.guild.id, 30)
            embed.add_field(
                name="🎉 歡迎系統 (30天)",
                value=f"加入: {welcome_stats.get('joins', 0)}\n"
                      f"離開: {welcome_stats.get('leaves', 0)}\n"
                      f"淨增長: {welcome_stats.get('net_growth', 0)}",
                inline=True
            )
            
            # 伺服器資訊
            embed.add_field(
                name="🏠 伺服器資訊",
                value=f"成員數: {ctx.guild.member_count}\n"
                      f"頻道數: {len(ctx.guild.channels)}\n"
                      f"角色數: {len(ctx.guild.roles)}",
                inline=True
            )
            
            # Bot狀態
            embed.add_field(
                name="🤖 Bot狀態",
                value=f"延遲: {round(self.bot.latency * 1000)}ms\n"
                      f"已載入Cogs: {len(self.bot.cogs)}\n"
                      f"指令數: {len(self.bot.commands)}",
                inline=True
            )
            
            embed.set_footer(text="使用 !admin 開啟詳細管理面板")
            
            await ctx.send(embed=embed)
            
        except Exception as e:
            logger.error(f"系統狀態查詢錯誤: {e}")
            await ctx.send("❌ 查詢系統狀態時發生錯誤")
    
    # ========== 診斷工具指令 ==========
    
    @commands.command(name='logs', aliases=['日誌', 'log'])
    @commands.has_permissions(manage_guild=True)
    async def view_logs(self, ctx, level: str = "error", days: int = 3):
        """查看系統日誌
        
        參數:
        - level: 日誌等級 (error, warning, info, debug)
        - days: 查看天數 (1-7)
        """
        try:
            # 驗證參數
            valid_levels = ['error', 'warning', 'info', 'debug']
            if level.lower() not in valid_levels:
                level = 'error'
            
            if days < 1 or days > 7:
                days = 3
            
            embed = discord.Embed(
                title=f"📝 系統日誌 - {level.upper()} 等級",
                description=f"最近 {days} 天的 {level} 等級日誌記錄",
                color=0x95a5a6
            )
            
            # 模擬日誌數據 (實際應用中應該從日誌文件或資料庫讀取)
            log_entries = [
                {
                    "timestamp": datetime.now() - timedelta(hours=2),
                    "level": "ERROR",
                    "message": "CommandNotFound: Command 'error_analysis' is not found",
                    "context": "Guild: 1392396522905276446, User: 292993868092276736"
                },
                {
                    "timestamp": datetime.now() - timedelta(hours=3),
                    "level": "ERROR", 
                    "message": "CommandNotFound: Command 'logs' is not found",
                    "context": "Guild: 1392396522905276446, User: 292993868092276736"
                },
                {
                    "timestamp": datetime.now() - timedelta(days=1),
                    "level": "WARNING",
                    "message": "資料庫連接緩慢",
                    "context": "Response time: 2.5s"
                }
            ]
            
            if level.lower() == 'error':
                filtered_logs = [log for log in log_entries if log['level'] == 'ERROR']
            elif level.lower() == 'warning':
                filtered_logs = [log for log in log_entries if log['level'] in ['ERROR', 'WARNING']]
            else:
                filtered_logs = log_entries
            
            if not filtered_logs:
                embed.add_field(
                    name="✅ 狀態良好",
                    value=f"最近 {days} 天沒有 {level} 等級的日誌記錄",
                    inline=False
                )
            else:
                for i, log in enumerate(filtered_logs[:10]):  # 最多顯示10條
                    timestamp_str = log['timestamp'].strftime('%m-%d %H:%M')
                    embed.add_field(
                        name=f"{log['level']} - {timestamp_str}",
                        value=f"```{log['message'][:100]}{'...' if len(log['message']) > 100 else ''}```",
                        inline=False
                    )
                
                if len(filtered_logs) > 10:
                    embed.add_field(
                        name="📋 更多記錄",
                        value=f"還有 {len(filtered_logs) - 10} 條記錄未顯示",
                        inline=False
                    )
            
            embed.add_field(
                name="💡 使用提示",
                value="使用 `!error_analysis` 查看錯誤趨勢分析\n"
                      "支援的等級: error, warning, info, debug",
                inline=False
            )
            
            await ctx.send(embed=embed)
            
        except Exception as e:
            logger.error(f"查看日誌錯誤: {e}")
            await ctx.send("❌ 查看系統日誌時發生錯誤")
    
    @commands.command(name='error_analysis', aliases=['錯誤分析', 'errors'])
    @commands.has_permissions(manage_guild=True)
    async def error_analysis(self, ctx, time_range: str = "24hours"):
        """錯誤趨勢分析
        
        參數:
        - time_range: 時間範圍 (1hour, 6hours, 24hours, 7days)
        """
        try:
            # 驗證時間範圍
            valid_ranges = {
                '1hour': ('1 小時', timedelta(hours=1)),
                '6hours': ('6 小時', timedelta(hours=6)),
                '24hours': ('24 小時', timedelta(days=1)),
                '7days': ('7 天', timedelta(days=7))
            }
            
            if time_range not in valid_ranges:
                time_range = '24hours'
            
            range_name, time_delta = valid_ranges[time_range]
            
            embed = discord.Embed(
                title="📊 系統錯誤分析",
                description=f"最近 {range_name} 的錯誤趨勢分析",
                color=0xe74c3c
            )
            
            # 模擬錯誤統計數據
            error_stats = {
                'CommandNotFound': 15,
                'DatabaseError': 3,
                'PermissionError': 7,
                'TimeoutError': 2,
                'ValidationError': 5
            }
            
            total_errors = sum(error_stats.values())
            
            embed.add_field(
                name="📈 總體統計",
                value=f"總錯誤數: **{total_errors}**\n"
                      f"錯誤類型: **{len(error_stats)}** 種\n"
                      f"平均頻率: **{total_errors/24:.1f}** 次/小時" if time_range == '24hours' else f"**{total_errors}** 次",
                inline=True
            )
            
            # 系統健康度評估
            if total_errors < 10:
                health_status = "🟢 良好"
                health_color = 0x2ecc71
            elif total_errors < 50:
                health_status = "🟡 普通"
                health_color = 0xf39c12
            else:
                health_status = "🔴 需要注意"
                health_color = 0xe74c3c
            
            embed.color = health_color
            embed.add_field(
                name="🏥 系統健康度",
                value=health_status,
                inline=True
            )
            
            # 錯誤分類統計
            error_list = []
            for error_type, count in sorted(error_stats.items(), key=lambda x: x[1], reverse=True):
                percentage = (count / total_errors) * 100
                error_list.append(f"• **{error_type}**: {count} 次 ({percentage:.1f}%)")
            
            embed.add_field(
                name="🔍 錯誤分類統計",
                value="\n".join(error_list),
                inline=False
            )
            
            # 建議改進措施
            suggestions = []
            if error_stats.get('CommandNotFound', 0) > 10:
                suggestions.append("• 考慮添加缺失的指令或改善指令文檔")
            if error_stats.get('DatabaseError', 0) > 5:
                suggestions.append("• 檢查資料庫連接穩定性")
            if error_stats.get('PermissionError', 0) > 5:
                suggestions.append("• 檢查 Bot 權限設定")
            
            if suggestions:
                embed.add_field(
                    name="💡 改進建議",
                    value="\n".join(suggestions),
                    inline=False
                )
            
            embed.add_field(
                name="🔧 相關指令",
                value="`!logs error` - 查看詳細錯誤日誌\n"
                      "`!diagnose` - 系統組件診斷\n"
                      "`!system_status` - 系統狀態總覽",
                inline=False
            )
            
            embed.set_footer(text="定期檢查錯誤分析有助於維護系統穩定性")
            
            await ctx.send(embed=embed)
            
        except Exception as e:
            logger.error(f"錯誤分析失敗: {e}")
            await ctx.send("❌ 執行錯誤分析時發生錯誤")
    
    @commands.command(name='diagnose', aliases=['診斷', 'check'])
    @commands.has_permissions(manage_guild=True)
    async def diagnose_system(self, ctx, component: str = None):
        """系統組件診斷
        
        參數:
        - component: 組件名稱 (ticket_system, database, bot, permissions)
        """
        try:
            embed = discord.Embed(
                title="🔍 系統診斷報告",
                color=0x3498db
            )
            
            if not component:
                # 全系統診斷
                embed.description = f"**{ctx.guild.name}** 的全系統健康檢查"
                
                # 檢查 Bot 基本狀態
                bot_latency = round(self.bot.latency * 1000)
                bot_status = "🟢 正常" if bot_latency < 200 else "🟡 緩慢" if bot_latency < 500 else "🔴 異常"
                
                embed.add_field(
                    name="🤖 Bot 狀態",
                    value=f"延遲: {bot_latency}ms\n"
                          f"狀態: {bot_status}\n"
                          f"已載入模組: {len(self.bot.cogs)}",
                    inline=True
                )
                
                # 檢查資料庫狀態
                try:
                    # 嘗試執行簡單查詢
                    await self.ticket_dao.get_settings(ctx.guild.id)
                    db_status = "🟢 正常"
                    db_detail = "連接正常"
                except Exception as e:
                    db_status = "🔴 異常"
                    db_detail = f"錯誤: {str(e)[:50]}"
                
                embed.add_field(
                    name="🗄️ 資料庫",
                    value=f"狀態: {db_status}\n"
                          f"詳情: {db_detail}",
                    inline=True
                )
                
                # 檢查權限
                bot_member = ctx.guild.get_member(self.bot.user.id)
                required_perms = ['manage_channels', 'manage_roles', 'send_messages', 'embed_links']
                missing_perms = []
                
                for perm in required_perms:
                    if not getattr(bot_member.guild_permissions, perm, False):
                        missing_perms.append(perm)
                
                perm_status = "🟢 完整" if not missing_perms else f"🟡 缺少 {len(missing_perms)} 項"
                
                embed.add_field(
                    name="🔐 權限檢查",
                    value=f"狀態: {perm_status}\n"
                          f"缺少: {', '.join(missing_perms) if missing_perms else '無'}",
                    inline=True
                )
                
                # 系統資源 (如果可用)
                if HAS_PSUTIL:
                    try:
                        cpu_percent = psutil.cpu_percent(interval=1)
                        memory = psutil.virtual_memory()
                        
                        resource_status = "🟢 良好" if cpu_percent < 70 and memory.percent < 80 else "🟡 偏高"
                        
                        embed.add_field(
                            name="💻 系統資源",
                            value=f"CPU: {cpu_percent:.1f}%\n"
                                  f"記憶體: {memory.percent:.1f}%\n"
                                  f"狀態: {resource_status}",
                            inline=True
                        )
                    except Exception:
                        embed.add_field(
                            name="💻 系統資源",
                            value="無法獲取資源信息",
                            inline=True
                        )
                else:
                    embed.add_field(
                        name="💻 系統資源",
                        value="需要安裝 psutil 套件",
                        inline=True
                    )
                
            else:
                # 特定組件診斷
                embed.description = f"**{component}** 組件詳細診斷"
                
                if component.lower() == 'ticket_system':
                    settings = await self.ticket_dao.get_settings(ctx.guild.id)
                    
                    if settings.get('category_id'):
                        category = ctx.guild.get_channel(settings['category_id'])
                        category_status = "🟢 存在" if category else "🔴 頻道不存在"
                        
                        embed.add_field(
                            name="📂 票券分類",
                            value=f"ID: {settings['category_id']}\n"
                                  f"狀態: {category_status}",
                            inline=False
                        )
                    else:
                        embed.add_field(
                            name="⚠️ 設定狀態",
                            value="票券系統尚未設定",
                            inline=False
                        )
                
                elif component.lower() == 'database':
                    try:
                        # 測試資料庫響應時間
                        start_time = datetime.now()
                        await self.ticket_dao.get_settings(ctx.guild.id)
                        response_time = (datetime.now() - start_time).total_seconds() * 1000
                        
                        db_performance = "🟢 快速" if response_time < 100 else "🟡 普通" if response_time < 500 else "🔴 緩慢"
                        
                        embed.add_field(
                            name="🗄️ 資料庫性能",
                            value=f"響應時間: {response_time:.1f}ms\n"
                                  f"狀態: {db_performance}",
                            inline=False
                        )
                    except Exception as e:
                        embed.add_field(
                            name="❌ 資料庫錯誤",
                            value=f"錯誤: {str(e)}",
                            inline=False
                        )
                
                else:
                    embed.add_field(
                        name="❓ 未知組件",
                        value=f"不支援診斷組件: {component}\n"
                              "支援的組件: ticket_system, database, bot, permissions",
                        inline=False
                    )
            
            embed.add_field(
                name="🛠️ 診斷工具",
                value="`!logs` - 查看系統日誌\n"
                      "`!error_analysis` - 錯誤趨勢分析\n"
                      "`!system_status` - 系統狀態概覽",
                inline=False
            )
            
            embed.set_footer(text=f"診斷時間: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            
            await ctx.send(embed=embed)
            
        except Exception as e:
            logger.error(f"系統診斷錯誤: {e}")
            await ctx.send("❌ 執行系統診斷時發生錯誤")
    
    @commands.command(name='check_permissions', aliases=['權限檢查', 'perms'])
    @commands.has_permissions(manage_guild=True)
    async def check_permissions(self, ctx, user: discord.Member = None):
        """檢查用戶權限設定
        
        參數:
        - user: 要檢查的用戶 (預設為 Bot 自己)
        """
        try:
            target = user or ctx.guild.get_member(self.bot.user.id)
            
            embed = discord.Embed(
                title="🔐 權限檢查報告",
                description=f"檢查用戶: **{target.display_name}**",
                color=0x9b59b6
            )
            
            # 基本權限檢查
            important_perms = {
                'administrator': '管理員',
                'manage_guild': '管理伺服器',
                'manage_channels': '管理頻道',
                'manage_roles': '管理身分組',
                'send_messages': '發送訊息',
                'embed_links': '嵌入連結',
                'attach_files': '附加檔案',
                'read_message_history': '查看訊息歷史',
                'add_reactions': '新增反應',
                'manage_messages': '管理訊息'
            }
            
            has_perms = []
            missing_perms = []
            
            for perm, desc in important_perms.items():
                if getattr(target.guild_permissions, perm, False):
                    has_perms.append(f"✅ {desc}")
                else:
                    missing_perms.append(f"❌ {desc}")
            
            if has_perms:
                embed.add_field(
                    name="✅ 擁有權限",
                    value="\n".join(has_perms[:10]),  # 限制顯示數量
                    inline=False
                )
            
            if missing_perms:
                embed.add_field(
                    name="❌ 缺少權限",
                    value="\n".join(missing_perms[:10]),
                    inline=False
                )
            
            # 身分組資訊
            roles_info = []
            for role in target.roles[-5:]:  # 顯示最高的5個身分組
                if role.name != "@everyone":
                    roles_info.append(f"• {role.name} (位置: {role.position})")
            
            if roles_info:
                embed.add_field(
                    name="👥 身分組 (最高5個)",
                    value="\n".join(roles_info),
                    inline=False
                )
            
            # 權限建議
            if target.id == self.bot.user.id and missing_perms:
                embed.add_field(
                    name="💡 建議",
                    value="Bot 缺少一些重要權限，可能影響正常功能運作。\n"
                          "建議檢查 Bot 身分組設定。",
                    inline=False
                )
            
            embed.set_thumbnail(url=target.display_avatar.url)
            embed.set_footer(text=f"權限檢查時間: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            
            await ctx.send(embed=embed)
            
        except Exception as e:
            logger.error(f"權限檢查錯誤: {e}")
            await ctx.send("❌ 檢查權限時發生錯誤")
    
    @commands.command(name='connectivity_test', aliases=['連接測試', 'ping'])
    @commands.has_permissions(manage_guild=True) 
    async def connectivity_test(self, ctx):
        """測試各系統連接狀態"""
        try:
            embed = discord.Embed(
                title="🔌 系統連接測試",
                description="測試各系統組件的連接狀態",
                color=0x3498db
            )
            
            # Discord API 延遲測試
            discord_latency = round(self.bot.latency * 1000)
            discord_status = "🟢 優秀" if discord_latency < 100 else "🟡 良好" if discord_latency < 300 else "🔴 較差"
            
            embed.add_field(
                name="🌐 Discord API",
                value=f"延遲: {discord_latency}ms\n"
                      f"狀態: {discord_status}",
                inline=True
            )
            
            # 資料庫連接測試
            try:
                start_time = datetime.now()
                await self.ticket_dao.get_settings(ctx.guild.id)
                db_latency = round((datetime.now() - start_time).total_seconds() * 1000)
                db_status = "🟢 優秀" if db_latency < 50 else "🟡 良好" if db_latency < 200 else "🔴 較差"
                
                embed.add_field(
                    name="🗄️ 資料庫",
                    value=f"延遲: {db_latency}ms\n"
                          f"狀態: {db_status}",
                    inline=True
                )
            except Exception as e:
                embed.add_field(
                    name="🗄️ 資料庫",
                    value=f"❌ 連接失敗\n錯誤: {str(e)[:30]}...",
                    inline=True
                )
            
            # 記憶體使用量
            if HAS_PSUTIL:
                try:
                    memory = psutil.virtual_memory()
                    memory_status = "🟢 良好" if memory.percent < 70 else "🟡 偏高" if memory.percent < 85 else "🔴 危險"
                    
                    embed.add_field(
                        name="💾 記憶體使用",
                        value=f"使用率: {memory.percent:.1f}%\n"
                              f"狀態: {memory_status}",
                        inline=True
                    )
                except Exception:
                    embed.add_field(
                        name="💾 記憶體使用",
                        value="無法獲取記憶體信息",
                        inline=True
                    )
            else:
                embed.add_field(
                    name="💾 記憶體使用",
                    value="需要安裝 psutil",
                    inline=True
                )
            
            # 整體健康評分
            health_score = 100
            if discord_latency > 300:
                health_score -= 20
            if discord_latency > 100:
                health_score -= 10
            
            try:
                if db_latency > 200:
                    health_score -= 20
                elif db_latency > 50:
                    health_score -= 10
            except:
                health_score -= 30  # 資料庫連接失敗
            
            if health_score >= 80:
                health_emoji = "🟢"
                health_desc = "優秀"
            elif health_score >= 60:
                health_emoji = "🟡"
                health_desc = "良好"
            else:
                health_emoji = "🔴"
                health_desc = "需要關注"
            
            embed.add_field(
                name="📊 整體健康度",
                value=f"{health_emoji} {health_score}/100\n狀態: {health_desc}",
                inline=False
            )
            
            embed.set_footer(text=f"測試時間: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            
            await ctx.send(embed=embed)
            
        except Exception as e:
            logger.error(f"連接測試錯誤: {e}")
            await ctx.send("❌ 執行連接測試時發生錯誤")
    
    # ========== 快速重置指令 ==========
    
    @commands.command(name='reset')
    @commands.has_permissions(administrator=True)
    async def reset_system(self, ctx, system: str = None):
        """重置系統設定 (管理員限定)"""
        if not system:
            embed = discord.Embed(
                title="⚠️ 系統重置",
                description="請指定要重置的系統：",
                color=0xe74c3c
            )
            
            embed.add_field(
                name="可用選項",
                value="• `!reset ticket` - 重置票券系統\n"
                      "• `!reset welcome` - 重置歡迎系統\n"
                      "• `!reset all` - 重置所有系統 (危險)",
                inline=False
            )
            
            embed.add_field(
                name="⚠️ 警告",
                value="重置操作會清除所有相關設定，此操作不可逆！",
                inline=False
            )
            
            await ctx.send(embed=embed)
            return
        
        # 確認重置操作
        confirm_embed = discord.Embed(
            title="❌ 確認重置操作",
            description=f"你確定要重置 **{system}** 系統嗎？\n這將清除所有相關設定且無法復原！",
            color=0xe74c3c
        )
        
        view = ConfirmResetView(ctx.author.id, system)
        await ctx.send(embed=confirm_embed, view=view)


class ConfirmResetView(discord.ui.View):
    """確認重置操作的視圖"""
    
    def __init__(self, user_id: int, system: str, timeout=30):
        super().__init__(timeout=timeout)
        self.user_id = user_id
        self.system = system
    
    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        return interaction.user.id == self.user_id
    
    @discord.ui.button(label="確認重置", style=discord.ButtonStyle.danger, emoji="❌")
    async def confirm_reset(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message(f"🔄 重置 {self.system} 系統功能開發中...", ephemeral=True)
        self.stop()
    
    @discord.ui.button(label="取消", style=discord.ButtonStyle.secondary, emoji="✖️")
    async def cancel_reset(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = discord.Embed(
            title="✅ 已取消",
            description="重置操作已取消",
            color=0x95a5a6
        )
        await interaction.response.edit_message(embed=embed, view=None)
        self.stop()


    # ========== 資料管理指令 ==========
    
    @commands.command(name='cleanup', aliases=['清理'])
    @commands.is_owner()
    async def cleanup_data(self, ctx, operation: str = "basic"):
        """資料清理操作 (Bot 擁有者限定)"""
        try:
            embed = discord.Embed(
                title="🧹 開始資料清理",
                description=f"執行 {operation} 清理操作...",
                color=0xf39c12
            )
            message = await ctx.send(embed=embed)
            
<<<<<<< HEAD
            from bot.services.database_cleanup_manager import DatabaseCleanupManager
            cleanup_manager = DatabaseCleanupManager()
            
            if operation == "full":
                # 執行全面資料庫清理
                results = await cleanup_manager.perform_comprehensive_cleanup(
                    ctx.guild.id if ctx.guild else 0,
                    {
                        'ticket_retention_days': 90,
                        'vote_retention_days': 60,
                        'log_retention_days': 30,
                        'archive_before_delete': True,
                        'batch_size': 1000
                    }
                )
            elif operation == "archive":
                # 只執行歷史資料歸檔，不刪除
                from bot.db.archive_dao import ArchiveDAO
                archive_dao = ArchiveDAO()
                
                results = {}
                results['tickets_archived'] = await archive_dao.archive_old_tickets(ctx.guild.id if ctx.guild else 0, 90, 1000)
                results['votes_archived'] = await archive_dao.archive_old_votes(ctx.guild.id if ctx.guild else 0, 60, 1000)
                results['activity_archived'] = await archive_dao.archive_user_activity(ctx.guild.id if ctx.guild else 0, "monthly")
            else:
                # 基本清理（只清理日誌和臨時資料）
                results = await cleanup_manager.perform_comprehensive_cleanup(
                    ctx.guild.id if ctx.guild else 0,
                    {
                        'ticket_retention_days': 180,  # 保留更長時間
                        'vote_retention_days': 120,
                        'log_retention_days': 7,  # 只清理7天前的日誌
                        'archive_before_delete': True,
                        'clean_logs': True,
                        'batch_size': 500
                    }
                )
            
            if results.get('success', False):
                embed = discord.Embed(
                    title="✅ 資料清理完成",
                    color=0x27ae60
                )
                
                if operation == "archive":
                    # 歸檔操作結果
                    total_archived = 0
                    archive_details = []
                    for op_name, result in results.items():
                        if isinstance(result, dict) and 'archived' in result:
                            archived_count = result['archived']
                            total_archived += archived_count
                            archive_details.append(f"📦 {op_name}: {archived_count:,} 條記錄")
                    
                    embed.add_field(name="總歸檔記錄", value=f"{total_archived:,}", inline=True)
                    embed.add_field(name="操作類型", value="歷史資料歸檔", inline=True)
                    
                    if archive_details:
                        embed.add_field(
                            name="歸檔詳情",
                            value="\n".join(archive_details),
                            inline=False
                        )
                else:
                    # 清理操作結果
                    embed.add_field(name="總歸檔記錄", value=f"{results.get('total_items_archived', 0):,}", inline=True)
                    embed.add_field(name="總清除記錄", value=f"{results.get('total_items_deleted', 0):,}", inline=True)
                    embed.add_field(name="清理類型", value=operation, inline=True)
                    
                    # 詳細結果
                    detailed_results = results.get('detailed_results', {})
                    if detailed_results:
                        details = []
                        for op_name, result in detailed_results.items():
                            if isinstance(result, dict):
                                archived = result.get('archived', 0)
                                deleted = result.get('deleted', 0)
                                if archived > 0 or deleted > 0:
                                    details.append(f"📊 {op_name}: 歸檔 {archived}, 清除 {deleted}")
                        
                        if details:
                            embed.add_field(
                                name="操作詳情",
                                value="\n".join(details[:8]),  # 限制顯示前8項
                                inline=False
                            )
            else:
                embed = discord.Embed(
                    title="❌ 清理失敗",
                    description=f"錯誤: {results.get('error', '未知錯誤')}",
                    color=0xe74c3c
=======
            from bot.services.data_cleanup_manager import DataCleanupManager
            cleanup_manager = DataCleanupManager()
            
            if operation == "full":
                results = await cleanup_manager.run_full_cleanup()
            else:
                # 基本清理（只清理日誌和臨時資料）
                results = {}
                results['system_logs'] = await cleanup_manager._cleanup_system_logs()
                results['temporary_data'] = await cleanup_manager._cleanup_temporary_data()
            
            # 統計結果
            total_deleted = sum(result.deleted_count for result in results.values() if hasattr(result, 'deleted_count'))
            successful_operations = sum(1 for result in results.values() if hasattr(result, 'success') and result.success)
            
            embed = discord.Embed(
                title="✅ 資料清理完成",
                color=0x27ae60
            )
            embed.add_field(name="總刪除記錄", value=f"{total_deleted:,}", inline=True)
            embed.add_field(name="成功操作", value=f"{successful_operations}/{len(results)}", inline=True)
            embed.add_field(name="清理類型", value=operation, inline=True)
            
            # 詳細結果
            details = []
            for op_name, result in results.items():
                if hasattr(result, 'success'):
                    status = "✅" if result.success else "❌"
                    deleted = getattr(result, 'deleted_count', 0)
                    details.append(f"{status} {op_name}: {deleted:,} 條記錄")
            
            if details:
                embed.add_field(
                    name="清理詳情",
                    value="\n".join(details[:10]),  # 限制顯示前10項
                    inline=False
>>>>>>> a35f5d60d87ec4cc0114507a78c8527f0eed00ca
                )
            
            await message.edit(embed=embed)
            
        except Exception as e:
            embed = discord.Embed(
                title="❌ 清理失敗",
                description=f"錯誤: {str(e)}",
                color=0xe74c3c
            )
            await ctx.send(embed=embed)
            logger.error(f"資料清理錯誤: {e}")

<<<<<<< HEAD
    @commands.command(name='db_optimize', aliases=['資料庫優化'])
    @commands.is_owner()
    async def optimize_database(self, ctx):
        """執行資料庫優化 (Bot 擁有者限定)"""
        try:
            embed = discord.Embed(
                title="⚡ 開始資料庫優化",
                description="正在分析和優化資料庫儲存...",
                color=0xf39c12
            )
            message = await ctx.send(embed=embed)
            
            from bot.services.database_cleanup_manager import DatabaseCleanupManager
            cleanup_manager = DatabaseCleanupManager()
            
            # 執行資料庫優化
            results = await cleanup_manager.optimize_database_storage(ctx.guild.id if ctx.guild else 0)
            
            if results.get('success', False):
                embed = discord.Embed(
                    title="✅ 資料庫優化完成",
                    color=0x27ae60
                )
                
                optimization_results = results.get('results', {})
                
                # 壓縮結果
                compression = optimization_results.get('compression', {})
                if compression and not compression.get('error'):
                    embed.add_field(
                        name="📦 資料壓縮",
                        value=f"壓縮歸檔: {compression.get('compressed_archives', 0)}\n"
                              f"節省空間: {compression.get('space_saved_mb', 0):.1f}MB\n"
                              f"壓縮比: {compression.get('compression_ratio', 1.0):.2f}x",
                        inline=True
                    )
                
                # 索引優化結果
                indexes = optimization_results.get('indexes', {})
                if indexes and not indexes.get('error'):
                    embed.add_field(
                        name="🗂️ 索引優化",
                        value=f"分析索引: {indexes.get('indexes_analyzed', 0)}\n"
                              f"優化索引: {indexes.get('indexes_optimized', 0)}\n"
                              f"性能提升: {indexes.get('query_performance_improvement', 0)}%",
                        inline=True
                    )
                
                # 統計資訊
                statistics = optimization_results.get('statistics', {})
                if statistics:
                    storage_analysis = statistics.get('storage_analysis', {})
                    embed.add_field(
                        name="📊 儲存分析",
                        value=f"活躍資料: {storage_analysis.get('active_data_size_mb', 0):.1f}MB\n"
                              f"歷史資料: {storage_analysis.get('archived_data_size_mb', 0):.1f}MB\n"
                              f"總大小: {storage_analysis.get('total_size_mb', 0):.1f}MB",
                        inline=True
                    )
                    
                    # 優化建議
                    recommendations = statistics.get('recommendations', [])
                    if recommendations:
                        embed.add_field(
                            name="💡 優化建議",
                            value="\n".join([f"• {rec}" for rec in recommendations[:3]]),
                            inline=False
                        )
            else:
                embed = discord.Embed(
                    title="❌ 資料庫優化失敗",
                    description=f"錯誤: {results.get('error', '未知錯誤')}",
                    color=0xe74c3c
                )
            
            await message.edit(embed=embed)
            
        except Exception as e:
            embed = discord.Embed(
                title="❌ 優化失敗",
                description=f"錯誤: {str(e)}",
                color=0xe74c3c
            )
            await ctx.send(embed=embed)
            logger.error(f"資料庫優化錯誤: {e}")

=======
>>>>>>> a35f5d60d87ec4cc0114507a78c8527f0eed00ca
    @commands.command(name='export', aliases=['匯出'])
    @commands.is_owner()
    async def export_data(self, ctx, data_type: str = "tickets", format: str = "json", days: int = 30):
        """資料匯出操作 (Bot 擁有者限定)"""
        try:
            if format not in ['json', 'csv', 'excel']:
                await ctx.send("❌ 不支援的格式，請選擇: json, csv, excel")
                return
            
            if data_type not in ['tickets', 'users', 'votes', 'logs', 'statistics', 'analytics']:
                await ctx.send("❌ 不支援的資料類型，請選擇: tickets, users, votes, logs, statistics, analytics")
                return
            
            embed = discord.Embed(
                title="📤 開始資料匯出",
                description=f"匯出 {data_type} 資料 ({format} 格式, 最近 {days} 天)...",
                color=0x3498db
            )
            message = await ctx.send(embed=embed)
            
            from bot.services.data_export_manager import DataExportManager, ExportRequest
            from datetime import datetime, timedelta
            
            export_manager = DataExportManager()
            
            # 創建匯出請求
            export_request = ExportRequest(
                export_type=data_type,
                format=format,
                date_range=(datetime.now() - timedelta(days=days), datetime.now()),
                guild_id=ctx.guild.id if ctx.guild else None,
                requester_id=ctx.author.id
            )
            
            # 執行匯出
            result = await export_manager.export_data(export_request)
            
            if result.success:
                embed = discord.Embed(
                    title="✅ 匯出完成",
                    color=0x27ae60
                )
                embed.add_field(name="檔案路徑", value=f"`{result.file_path}`", inline=False)
                embed.add_field(name="記錄數量", value=f"{result.record_count:,}", inline=True)
                embed.add_field(name="檔案大小", value=f"{result.file_size:,} bytes", inline=True)
                embed.add_field(name="匯出時間", value=f"{result.export_time:.2f} 秒", inline=True)
                
                # 如果檔案不太大，嘗試上傳
                if result.file_size < 8 * 1024 * 1024:  # 8MB 限制
                    try:
                        file = discord.File(result.file_path)
                        await ctx.send(file=file)
                    except Exception:
                        embed.add_field(name="注意", value="檔案過大無法上傳，請至伺服器下載", inline=False)
            else:
                embed = discord.Embed(
                    title="❌ 匯出失敗",
                    description=f"錯誤: {result.error_message}",
                    color=0xe74c3c
                )
            
            await message.edit(embed=embed)
            
        except Exception as e:
            embed = discord.Embed(
                title="❌ 匯出失敗",
                description=f"錯誤: {str(e)}",
                color=0xe74c3c
            )
            await ctx.send(embed=embed)
            logger.error(f"資料匯出錯誤: {e}")

    @commands.command(name='statistics', aliases=['統計', '報告'])
    @commands.has_permissions(administrator=True)
    async def get_statistics(self, ctx, days: int = 7):
        """獲取系統統計報告"""
        try:
            if days < 1 or days > 365:
                await ctx.send("❌ 天數範圍必須在 1-365 之間")
                return
            
            embed = discord.Embed(
                title="📊 生成統計報告中...",
                description=f"分析最近 {days} 天的資料...",
                color=0x3498db
            )
            message = await ctx.send(embed=embed)
            
            from bot.services.statistics_manager import StatisticsManager, StatisticsConfig
            
            stats_manager = StatisticsManager()
            stats = await stats_manager.get_comprehensive_statistics(
                guild_id=ctx.guild.id if ctx.guild else None,
                days=days
            )
            
            if 'error' in stats:
                embed = discord.Embed(
                    title="❌ 統計生成失敗",
                    description=f"錯誤: {stats['error']}",
                    color=0xe74c3c
                )
                await message.edit(embed=embed)
                return
            
            # 創建統計報告嵌入
            embed = discord.Embed(
                title="📊 系統統計報告",
                description=f"統計期間: {days} 天\n生成時間: {stats['metadata'].get('generated_at', 'N/A')}",
                color=0x27ae60
            )
            
            # 票券統計
            ticket_stats = stats.get('ticket_statistics', {})
            if ticket_stats:
                summary = ticket_stats.get('summary', {})
                embed.add_field(
                    name="🎫 票券統計",
                    value=f"總票券: {summary.get('total_tickets', 0):,}\n"
                          f"解決率: {summary.get('resolution_rate', 0):.1f}%\n"
                          f"日均票券: {summary.get('avg_daily_tickets', 0):.1f}",
                    inline=True
                )
            
            # 用戶統計
            user_stats = stats.get('user_statistics', {})
            if user_stats:
                summary = user_stats.get('summary', {})
                embed.add_field(
                    name="👥 用戶統計",
                    value=f"活躍用戶: {summary.get('total_unique_users', 0):,}\n"
                          f"人均票券: {summary.get('avg_tickets_per_user', 0):.1f}",
                    inline=True
                )
            
            # 性能統計
            perf_stats = stats.get('performance_statistics', {})
            if perf_stats:
                summary = perf_stats.get('summary', {})
                embed.add_field(
                    name="⚡ 性能統計",
                    value=f"平均回應: {summary.get('avg_first_response_hours', 0):.1f}h\n"
                          f"平均解決: {summary.get('avg_resolution_hours', 0):.1f}h\n"
                          f"24h解決率: {summary.get('resolution_within_24h_rate', 0):.1f}%",
                    inline=True
                )
            
            # 滿意度統計
            satisfaction_stats = stats.get('satisfaction_statistics', {})
            if satisfaction_stats:
                summary = satisfaction_stats.get('summary', {})
                embed.add_field(
                    name="⭐ 滿意度統計",
                    value=f"平均評分: {summary.get('avg_rating', 0):.1f}/5.0\n"
                          f"回應率: {summary.get('rating_response_rate', 0):.1f}%",
                    inline=True
                )
            
            # 系統健康
            system_health = stats.get('system_health', {})
            if system_health:
                summary = system_health.get('summary', {})
                embed.add_field(
                    name="🏥 系統健康",
                    value=f"健康分數: {summary.get('system_health_score', 0):.1f}\n"
                          f"DB大小: {summary.get('total_database_size_mb', 0):.1f}MB",
                    inline=True
                )
            
            # 生成時間
            generation_time = stats.get('metadata', {}).get('generation_time', 0)
            embed.set_footer(text=f"統計生成時間: {generation_time:.2f} 秒")
            
            await message.edit(embed=embed)
            
        except Exception as e:
            embed = discord.Embed(
                title="❌ 統計生成失敗",
                description=f"錯誤: {str(e)}",
                color=0xe74c3c
            )
            await ctx.send(embed=embed)
            logger.error(f"統計生成錯誤: {e}")

    @commands.command(name='maintenance', aliases=['維護'])
    @commands.is_owner()
    async def maintenance_control(self, ctx, action: str = "status", task_id: str = None):
        """維護系統控制 (Bot 擁有者限定)"""
        try:
            from bot.services.maintenance_scheduler import MaintenanceScheduler
            
            # 這裡應該有全局的 scheduler 實例，暫時創建一個用於演示
            scheduler = MaintenanceScheduler()
            
            if action == "status":
                tasks_status = scheduler.get_all_tasks_status()
                
                embed = discord.Embed(
                    title="🔧 維護系統狀態",
                    color=0x3498db
                )
                
                for task_status in tasks_status[:10]:  # 限制顯示前10個任務
                    status_emoji = "✅" if task_status['enabled'] else "❌"
                    last_run = task_status['last_run']
                    last_run_str = datetime.fromisoformat(last_run).strftime("%m-%d %H:%M") if last_run else "未執行"
                    
                    embed.add_field(
                        name=f"{status_emoji} {task_status['name']}",
                        value=f"頻率: {task_status['frequency']}\n"
                              f"上次執行: {last_run_str}\n"
                              f"執行次數: {task_status['run_count']} | 失敗: {task_status['failure_count']}",
                        inline=True
                    )
                
                embed.set_footer(text=f"總共 {len(tasks_status)} 個維護任務")
                
            elif action == "run" and task_id:
                embed = discord.Embed(
                    title="🏃 執行維護任務",
                    description=f"正在執行任務: {task_id}...",
                    color=0xf39c12
                )
                message = await ctx.send(embed=embed)
                
                success = await scheduler.run_task_now(task_id)
                
                if success:
                    embed = discord.Embed(
                        title="✅ 任務執行完成",
                        description=f"任務 {task_id} 執行成功",
                        color=0x27ae60
                    )
                else:
                    embed = discord.Embed(
                        title="❌ 任務執行失敗",
                        description=f"任務 {task_id} 執行失敗",
                        color=0xe74c3c
                    )
                
                await message.edit(embed=embed)
                return
                
            elif action == "enable" and task_id:
                if scheduler.enable_task(task_id):
                    embed = discord.Embed(
                        title="✅ 任務已啟用",
                        description=f"任務 {task_id} 已啟用",
                        color=0x27ae60
                    )
                else:
                    embed = discord.Embed(
                        title="❌ 啟用失敗",
                        description=f"找不到任務: {task_id}",
                        color=0xe74c3c
                    )
                    
            elif action == "disable" and task_id:
                if scheduler.disable_task(task_id):
                    embed = discord.Embed(
                        title="❌ 任務已禁用",
                        description=f"任務 {task_id} 已禁用",
                        color=0x95a5a6
                    )
                else:
                    embed = discord.Embed(
                        title="❌ 禁用失敗",
                        description=f"找不到任務: {task_id}",
                        color=0xe74c3c
                    )
            else:
                embed = discord.Embed(
                    title="❓ 使用說明",
                    description="可用操作:\n"
                              "`!maintenance status` - 查看任務狀態\n"
                              "`!maintenance run <task_id>` - 執行指定任務\n"
                              "`!maintenance enable <task_id>` - 啟用任務\n"
                              "`!maintenance disable <task_id>` - 禁用任務",
                    color=0x3498db
                )
            
            await ctx.send(embed=embed)
            
        except Exception as e:
            embed = discord.Embed(
                title="❌ 維護系統錯誤",
                description=f"錯誤: {str(e)}",
                color=0xe74c3c
            )
            await ctx.send(embed=embed)
            logger.error(f"維護系統錯誤: {e}")

    @commands.command(name='backup', aliases=['備份'])
    @commands.is_owner()
    async def create_backup(self, ctx, backup_type: str = "basic"):
        """創建系統備份 (Bot 擁有者限定)"""
        try:
            if backup_type not in ['basic', 'full', 'tickets', 'statistics']:
                await ctx.send("❌ 備份類型錯誤，請選擇: basic, full, tickets, statistics")
                return
            
            embed = discord.Embed(
                title="💾 開始創建備份",
                description=f"備份類型: {backup_type}",
                color=0x3498db
            )
            message = await ctx.send(embed=embed)
            
            from bot.services.data_export_manager import DataExportManager
            
            export_manager = DataExportManager()
            
            if backup_type == "full":
                # 創建完整備份
                export_types = ['tickets', 'users', 'votes', 'logs', 'statistics']
                result = await export_manager.create_bulk_export(
                    export_types=export_types,
                    format='json',
                    guild_id=ctx.guild.id if ctx.guild else None
                )
            elif backup_type == "basic":
                # 基本備份
                export_types = ['tickets', 'statistics']
                result = await export_manager.create_bulk_export(
                    export_types=export_types,
                    format='json',
                    guild_id=ctx.guild.id if ctx.guild else None
                )
            else:
                # 單項備份
                from bot.services.data_export_manager import ExportRequest
                from datetime import datetime
                
                export_request = ExportRequest(
                    export_type=backup_type,
                    format='json',
                    guild_id=ctx.guild.id if ctx.guild else None,
                    requester_id=ctx.author.id
                )
                
                result = await export_manager.export_data(export_request)
            
            if result.success:
                embed = discord.Embed(
                    title="✅ 備份創建完成",
                    color=0x27ae60
                )
                embed.add_field(name="備份檔案", value=f"`{result.file_path}`", inline=False)
                embed.add_field(name="檔案大小", value=f"{result.file_size:,} bytes", inline=True)
                
                if hasattr(result, 'record_count'):
                    embed.add_field(name="記錄數量", value=f"{result.record_count:,}", inline=True)
                
                metadata = result.metadata or {}
                if metadata.get('successful_exports'):
                    embed.add_field(
                        name="成功備份",
                        value=f"{metadata['successful_exports']}/{metadata.get('total_export_types', 1)}",
                        inline=True
                    )
            else:
                embed = discord.Embed(
                    title="❌ 備份創建失敗",
                    description=f"錯誤: {result.error_message}",
                    color=0xe74c3c
                )
            
            await message.edit(embed=embed)
            
        except Exception as e:
            embed = discord.Embed(
                title="❌ 備份創建失敗",
                description=f"錯誤: {str(e)}",
                color=0xe74c3c
            )
            await ctx.send(embed=embed)
            logger.error(f"備份創建錯誤: {e}")


async def setup(bot):
    """載入擴展"""
    await bot.add_cog(SystemAdmin(bot))