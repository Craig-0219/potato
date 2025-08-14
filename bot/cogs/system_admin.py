# bot/cogs/system_admin.py
"""
系統管理 Cog - 簡化版
提供基本的系統管理功能
"""

import discord
from discord.ext import commands
from discord import app_commands
from typing import Optional
import asyncio
from datetime import datetime, timedelta
from shared.logger import logger


class SystemAdmin(commands.Cog):
    """系統管理功能 - 簡化版"""
    
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="admin", description="系統管理面板")
    @app_commands.default_permissions(administrator=True)
    async def admin_panel(self, interaction: discord.Interaction):
        """系統管理面板"""
        try:
            from bot.views.system_admin_views import SystemAdminPanel
            
            embed = discord.Embed(
                title="🔧 系統管理面板",
                description="選擇要執行的管理操作",
                color=0x3498db
            )
            
            embed.add_field(
                name="📊 功能模組",
                value="• 🎫 票券系統設定\n• 🎉 歡迎系統設定\n• 🗳️ 投票系統設定\n• 📊 統計與監控\n• 🔧 系統工具",
                inline=False
            )
            
            embed.add_field(
                name="💡 使用說明",
                value="點擊下方按鈕進入相應的設定頁面",
                inline=False
            )
            
            view = SystemAdminPanel(user_id=interaction.user.id)
            await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
            
        except Exception as e:
            logger.error(f"管理面板錯誤: {e}")
            try:
                if not interaction.response.is_done():
                    await interaction.response.send_message("❌ 管理面板載入失敗", ephemeral=True)
                else:
                    await interaction.followup.send("❌ 管理面板載入失敗", ephemeral=True)
            except Exception as followup_error:
                logger.error(f"發送錯誤訊息失敗: {followup_error}")

    @app_commands.command(name="basic_dashboard", description="查看基礎系統儀表板")
    @app_commands.default_permissions(manage_messages=True)
    async def basic_dashboard(self, interaction: discord.Interaction):
        """基礎系統儀表板（避免與高級儀表板衝突）"""
        from bot.utils.interaction_helper import SafeInteractionHandler
        
        try:
            if not await SafeInteractionHandler.safe_defer(interaction, ephemeral=True):
                logger.debug("基礎儀表板互動無法延遲，可能已過期")
                return
            
            # 獲取基本系統資訊
            embed = discord.Embed(
                title="📊 基礎系統儀表板",
                color=0x2ecc71
            )
            
            # Bot 基本資訊
            embed.add_field(
                name="🤖 Bot 資訊",
                value=f"延遲: {round(self.bot.latency * 1000)}ms\n"
                      f"伺服器: {len(self.bot.guilds)}\n"
                      f"用戶: {len(self.bot.users)}",
                inline=True
            )
            
            # 系統資訊
            embed.add_field(
                name="⚙️ 系統狀態",
                value=f"擴展: {len(self.bot.extensions)}\n"
                      f"指令: {len(self.bot.tree.get_commands())}\n"
                      f"狀態: 正常運行",
                inline=True
            )
            
            # 伺服器資訊
            if interaction.guild:
                embed.add_field(
                    name="📋 目前伺服器",
                    value=f"名稱: {interaction.guild.name}\n"
                          f"成員: {interaction.guild.member_count}\n"
                          f"頻道: {len(interaction.guild.channels)}",
                    inline=True
                )
            
            embed.set_footer(text=f"運行時間: {self.bot.get_uptime() if hasattr(self.bot, 'get_uptime') else '未知'}")
            
            await SafeInteractionHandler.safe_respond(interaction, embed=embed, ephemeral=True)
            
        except Exception as e:
            logger.error(f"基礎儀表板錯誤: {e}")
            await SafeInteractionHandler.handle_interaction_error(interaction, e, "基礎儀表板")

    @app_commands.command(name="system_status", description="查看系統整體狀態")
    @app_commands.default_permissions(administrator=True)
    async def system_status(self, interaction: discord.Interaction):
        """系統整體狀態 (斜線指令版本)"""
        try:
            if not await SafeInteractionHandler.safe_defer(interaction, ephemeral=True):
                logger.debug("系統狀態互動無法延遲，可能已過期")
                return
            
            from bot.db.pool import get_db_health
            
            # 獲取資料庫健康狀態
            db_health = await get_db_health()
            
            embed = discord.Embed(
                title="🤖 系統整體狀態",
                color=0x00ff00 if db_health.get('status') == 'healthy' else 0xffaa00
            )
            
            # Bot 基本資訊
            embed.add_field(
                name="📊 基本資訊",
                value=f"延遲: {round(self.bot.latency * 1000)}ms\n"
                      f"伺服器數: {len(self.bot.guilds)}\n"
                      f"擴展數: {len(self.bot.extensions)}",
                inline=True
            )
            
            # 資料庫狀態
            embed.add_field(
                name="💾 資料庫",
                value=f"狀態: {db_health.get('status', 'unknown')}\n"
                      f"連接: {'✅' if db_health.get('status') == 'healthy' else '❌'}",
                inline=True
            )
            
            # 系統狀態
            embed.add_field(
                name="⚙️ 系統",
                value=f"指令樹: {len(self.bot.tree.get_commands())}\n"
                      f"整體狀態: {'🟢 正常' if db_health.get('status') == 'healthy' else '🟡 警告'}",
                inline=True
            )
            
            await SafeInteractionHandler.safe_respond(interaction, embed=embed, ephemeral=True)
            
        except Exception as e:
            logger.error(f"系統狀態查詢失敗: {e}")
            await SafeInteractionHandler.handle_interaction_error(interaction, e, "系統狀態查詢")

    @commands.command(name='botstatus', aliases=['狀態'])
    @commands.is_owner()
    async def system_status_cmd(self, ctx):
        """Bot 整體狀態 (Bot 擁有者限定)"""
        try:
            from bot.db.pool import get_db_health
            
            # 獲取資料庫健康狀態
            db_health = await get_db_health()
            
            embed = discord.Embed(
                title="🤖 Bot 整體狀態",
                color=0x00ff00 if db_health.get('status') == 'healthy' else 0xffaa00
            )
            
            # Bot 基本資訊
            embed.add_field(
                name="📊 基本資訊",
                value=f"延遲: {round(self.bot.latency * 1000)}ms\n"
                      f"伺服器數: {len(self.bot.guilds)}\n"
                      f"擴展數: {len(self.bot.extensions)}",
                inline=True
            )
            
            # 資料庫狀態
            embed.add_field(
                name="💾 資料庫",
                value=f"狀態: {db_health.get('status', 'unknown')}\n"
                      f"連接: {'✅' if db_health.get('status') == 'healthy' else '❌'}",
                inline=True
            )
            
            # 系統狀態
            embed.add_field(
                name="⚙️ 系統",
                value=f"指令樹: {len(self.bot.tree.get_commands())}\n"
                      f"整體狀態: {'🟢 正常' if db_health.get('status') == 'healthy' else '🟡 警告'}",
                inline=True
            )
            
            await ctx.send(embed=embed)
            
        except Exception as e:
            await ctx.send(f"❌ 獲取狀態失敗：{e}")
            logger.error(f"獲取Bot狀態失敗: {e}")

    @commands.command(name='healthcheck', aliases=['健康檢查'])
    @commands.is_owner()
    async def system_health_check(self, ctx):
        """完整健康檢查 (Bot 擁有者限定)"""
        try:
            embed = discord.Embed(
                title="🏥 系統健康檢查",
                description="正在檢查所有系統組件...",
                color=0xf39c12
            )
            message = await ctx.send(embed=embed)
            
            # 執行檢查
            checks = {
                "🤖 Bot 連接": self.bot.is_ready(),
                "💾 資料庫": False,
                "📊 指令系統": len(self.bot.tree.get_commands()) > 0,
                "🔧 擴展載入": len(self.bot.extensions) > 5,
            }
            
            # 檢查資料庫
            try:
                from bot.db.pool import get_db_health
                db_health = await get_db_health()
                checks["💾 資料庫"] = db_health.get('status') == 'healthy'
            except:
                pass
            
            # 生成結果
            results = []
            all_healthy = True
            
            for check_name, is_healthy in checks.items():
                status = "✅" if is_healthy else "❌"
                results.append(f"{status} {check_name}")
                if not is_healthy:
                    all_healthy = False
            
            embed = discord.Embed(
                title="🏥 系統健康檢查結果",
                description="\n".join(results),
                color=0x00ff00 if all_healthy else 0xff9900
            )
            
            embed.add_field(
                name="📈 整體評估",
                value="🎉 系統運行良好" if all_healthy else "⚠️ 發現部分問題",
                inline=False
            )
            
            await message.edit(embed=embed)
            
        except Exception as e:
            await ctx.send(f"❌ 健康檢查失敗：{e}")
            logger.error(f"健康檢查失敗: {e}")

    @app_commands.command(name="vote_admin", description="投票系統管理面板")
    @app_commands.default_permissions(manage_messages=True)
    async def vote_admin(self, interaction: discord.Interaction):
        """投票系統管理面板"""
        try:
            from bot.views.system_admin_views import VoteAdminView
            
            embed = discord.Embed(
                title="🗳️ 投票系統管理",
                description="選擇要執行的投票管理操作",
                color=0x3498db
            )
            
            embed.add_field(
                name="📊 功能說明",
                value="• 查看活躍投票\n• 強制結束投票\n• 查看投票統計\n• 管理投票權限",
                inline=False
            )
            
            view = VoteAdminView()
            await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
            
        except Exception as e:
            logger.error(f"投票管理面板錯誤: {e}")
            try:
                if not interaction.response.is_done():
                    await interaction.response.send_message("❌ 投票管理面板載入失敗", ephemeral=True)
                else:
                    await interaction.followup.send("❌ 投票管理面板載入失敗", ephemeral=True)
            except Exception as followup_error:
                logger.error(f"發送錯誤訊息失敗: {followup_error}")

    @app_commands.command(name="backup", description="執行系統資料備份")
    @app_commands.describe(
        backup_type="備份類型 (all/tickets/votes/statistics)",
        format_type="檔案格式 (json/csv/sql)"
    )
    @app_commands.choices(
        backup_type=[
            app_commands.Choice(name="全部資料", value="all"),
            app_commands.Choice(name="票券系統", value="tickets"),
            app_commands.Choice(name="投票系統", value="votes"),
            app_commands.Choice(name="統計資料", value="statistics")
        ],
        format_type=[
            app_commands.Choice(name="JSON 格式", value="json"),
            app_commands.Choice(name="CSV 格式", value="csv"),
            app_commands.Choice(name="SQL 格式", value="sql")
        ]
    )
    @app_commands.default_permissions(administrator=True)
    async def backup(self, interaction: discord.Interaction, backup_type: str = "all", format_type: str = "json"):
        """執行系統資料備份"""
        try:
            await interaction.response.defer(ephemeral=True)
            
            # 導入必要的模組
            from bot.services.data_export_manager import DataExportManager, ExportRequest
            from datetime import datetime
            
            export_manager = DataExportManager()
            
            embed = discord.Embed(
                title="💾 系統資料備份",
                description="正在執行資料備份...",
                color=0xf39c12
            )
            
            await interaction.followup.send(embed=embed, ephemeral=True)
            
            # 根據備份類型決定要備份的內容
            backup_types = []
            if backup_type == "all":
                backup_types = ["tickets", "votes", "statistics"]
            else:
                backup_types = [backup_type]
            
            results = {}
            total_size = 0
            successful_backups = 0
            
            for btype in backup_types:
                try:
                    export_request = ExportRequest(
                        data_type=btype,
                        format=format_type,
                        date_range=None,  # 備份所有資料
                        requested_by=interaction.user.id
                    )
                    
                    export_result = await export_manager.export_data(export_request)
                    
                    if export_result.success:
                        successful_backups += 1
                        total_size += export_result.file_size
                        
                    results[btype] = {
                        'success': export_result.success,
                        'file_path': export_result.file_path,
                        'file_size': export_result.file_size,
                        'record_count': export_result.record_count,
                        'error': export_result.error_message
                    }
                    
                except Exception as e:
                    results[btype] = {
                        'success': False,
                        'error': str(e)
                    }
            
            # 更新結果嵌入訊息
            if successful_backups > 0:
                embed = discord.Embed(
                    title="✅ 備份完成",
                    description=f"成功備份 {successful_backups}/{len(backup_types)} 個資料類型",
                    color=0x2ecc71
                )
                
                # 添加備份詳情
                backup_details = []
                for btype, result in results.items():
                    if result['success']:
                        size_mb = result['file_size'] / 1024 / 1024 if result['file_size'] else 0
                        backup_details.append(
                            f"✅ **{btype.title()}**: {result['record_count']} 筆記錄 ({size_mb:.2f} MB)"
                        )
                    else:
                        backup_details.append(f"❌ **{btype.title()}**: {result.get('error', '未知錯誤')}")
                
                embed.add_field(
                    name="📋 備份詳情",
                    value="\n".join(backup_details),
                    inline=False
                )
                
                embed.add_field(
                    name="📊 總計",
                    value=f"總大小: {total_size / 1024 / 1024:.2f} MB\n"
                          f"備份時間: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
                    inline=False
                )
                
            else:
                embed = discord.Embed(
                    title="❌ 備份失敗",
                    description="所有備份操作都失敗了",
                    color=0xe74c3c
                )
                
                error_details = []
                for btype, result in results.items():
                    error_details.append(f"❌ **{btype.title()}**: {result.get('error', '未知錯誤')}")
                
                embed.add_field(
                    name="❌ 錯誤詳情",
                    value="\n".join(error_details),
                    inline=False
                )
            
            embed.set_footer(text=f"由 {interaction.user.display_name} 執行")
            await interaction.edit_original_response(embed=embed)
            
        except Exception as e:
            logger.error(f"備份指令錯誤: {e}")
            error_embed = discord.Embed(
                title="❌ 備份失敗",
                description=f"執行備份時發生錯誤: {str(e)}",
                color=0xe74c3c
            )
            try:
                await interaction.edit_original_response(embed=error_embed)
            except:
                await interaction.followup.send(embed=error_embed, ephemeral=True)

    @app_commands.command(name="database", description="資料庫管理面板")
    @app_commands.describe(
        action="管理動作",
        target="目標對象"
    )
    @app_commands.choices(
        action=[
            app_commands.Choice(name="檢查健康狀態", value="health"),
            app_commands.Choice(name="清理過期資料", value="cleanup"),
            app_commands.Choice(name="重建索引", value="reindex"),
            app_commands.Choice(name="查看統計", value="stats")
        ]
    )
    @app_commands.default_permissions(administrator=True)
    async def database(self, interaction: discord.Interaction, action: str, target: str = "all"):
        """資料庫管理面板"""
        try:
            await interaction.response.defer(ephemeral=True)
            
            from bot.db.pool import get_db_health
            from bot.services.data_cleanup_manager import DataCleanupManager
            
            embed = discord.Embed(
                title="🗄️ 資料庫管理",
                description=f"正在執行操作: {action}...",
                color=0x3498db
            )
            
            await interaction.followup.send(embed=embed, ephemeral=True)
            
            if action == "health":
                # 檢查資料庫健康狀態
                db_health = await get_db_health()
                
                embed = discord.Embed(
                    title="💊 資料庫健康檢查",
                    color=0x2ecc71 if db_health.get('status') == 'healthy' else 0xe74c3c
                )
                
                embed.add_field(
                    name="🔍 連接狀態",
                    value=f"狀態: {'✅ 正常' if db_health.get('status') == 'healthy' else '❌ 異常'}\n"
                          f"延遲: {db_health.get('latency', 'N/A')}ms\n"
                          f"連接池: {db_health.get('pool_status', 'N/A')}",
                    inline=True
                )
                
                # 獲取資料庫統計
                try:
                    from bot.db.database_manager import get_database_manager
                    import aiomysql
                    db = get_database_manager()
                    
                    async with db.db.connection() as conn:
                        async with conn.cursor(aiomysql.DictCursor) as cursor:
                            # 獲取表格統計
                            tables_info = {}
                            main_tables = ['tickets', 'votes', 'ticket_logs', 'vote_responses']
                            
                            for table in main_tables:
                                try:
                                    await cursor.execute(f"SELECT COUNT(*) as count FROM {table}")
                                    result = await cursor.fetchone()
                                    tables_info[table] = result['count'] if result else 0
                                except Exception as e:
                                    logger.warning(f"無法查詢表格 {table}: {e}")
                                    tables_info[table] = "N/A"
                            
                            # 添加表格資訊
                            table_stats = []
                            for table, count in tables_info.items():
                                table_stats.append(f"📊 **{table.title()}**: {count} 筆")
                            
                            embed.add_field(
                                name="📈 資料統計",
                                value="\n".join(table_stats),
                                inline=True
                            )
                            
                except Exception as e:
                    embed.add_field(
                        name="⚠️ 統計警告",
                        value=f"無法獲取詳細統計: {str(e)}",
                        inline=False
                    )
                
            elif action == "cleanup":
                # 執行資料清理
                cleanup_manager = DataCleanupManager()
                results = await cleanup_manager.run_full_cleanup()
                
                total_deleted = results.cleaned_items
                successful_ops = 1 if results.success else 0
                
                embed = discord.Embed(
                    title="🧹 資料庫清理完成",
                    description=f"清理狀態: {'✅ 成功' if results.success else '❌ 失敗'}",
                    color=0x2ecc71 if successful_ops > 0 else 0xe74c3c
                )
                
                # 添加清理詳情
                cleanup_details = results.details if results.details else ["沒有需要清理的資料"]
                
                embed.add_field(
                    name="🗑️ 清理詳情",
                    value="\n".join(cleanup_details) if cleanup_details else "沒有需要清理的資料",
                    inline=False
                )
                
                embed.add_field(
                    name="📊 總計",
                    value=f"清理記錄: {total_deleted} 筆\n"
                          f"執行時間: {results.duration_seconds:.2f} 秒\n"
                          f"預估節省空間: {results.space_freed_mb:.2f} MB",
                    inline=False
                )
                
            elif action == "reindex":
                # 重建索引
                try:
                    from bot.db.database_manager import get_database_manager
                    import aiomysql
                    db = get_database_manager()
                    
                    async with db.db.connection() as conn:
                        async with conn.cursor(aiomysql.DictCursor) as cursor:
                            # 主要表格
                            main_tables = ['tickets', 'votes', 'ticket_logs', 'vote_responses']
                            reindex_results = {}
                            
                            for table in main_tables:
                                try:
                                    await cursor.execute(f"OPTIMIZE TABLE {table}")
                                    reindex_results[table] = "success"
                                except Exception as e:
                                    reindex_results[table] = f"failed: {str(e)}"
                            
                            # 建立結果嵌入
                            embed = discord.Embed(
                                title="🔧 索引重建完成",
                                color=0x2ecc71
                            )
                            
                            reindex_details = []
                            successful = 0
                            for table, result in reindex_results.items():
                                if result == "success":
                                    reindex_details.append(f"✅ **{table.title()}**: 重建成功")
                                    successful += 1
                                else:
                                    reindex_details.append(f"❌ **{table.title()}**: {result}")
                            
                            embed.add_field(
                                name="🔨 重建詳情",
                                value="\n".join(reindex_details),
                                inline=False
                            )
                            
                            embed.add_field(
                                name="📊 總計",
                                value=f"成功重建: {successful}/{len(main_tables)} 個表格",
                                inline=False
                            )
                            
                except Exception as e:
                    embed = discord.Embed(
                        title="❌ 索引重建失敗",
                        description=f"執行重建時發生錯誤: {str(e)}",
                        color=0xe74c3c
                    )
                    
            elif action == "stats":
                # 查看資料庫統計
                try:
                    from bot.services.statistics_manager import StatisticsManager
                    stats_manager = StatisticsManager()
                    
                    # 獲取綜合統計
                    stats = await stats_manager.get_comprehensive_statistics(interaction.guild.id)
                    
                    embed = discord.Embed(
                        title="📊 資料庫統計資訊",
                        color=0x3498db
                    )
                    
                    # 票券統計
                    ticket_stats = stats.get('ticket_statistics', {}).get('summary', {})
                    embed.add_field(
                        name="🎫 票券系統",
                        value=f"總票券: {ticket_stats.get('total_tickets', 0)}\n"
                              f"開啟中: {ticket_stats.get('open_tickets', 0)}\n"
                              f"解決率: {ticket_stats.get('resolution_rate', 0)}%",
                        inline=True
                    )
                    
                    # 投票統計
                    vote_stats = stats.get('vote_statistics', {}).get('summary', {})
                    embed.add_field(
                        name="🗳️ 投票系統",
                        value=f"總投票: {vote_stats.get('total_votes', 0)}\n"
                              f"完成投票: {vote_stats.get('completed_votes', 0)}\n"
                              f"活躍投票: {vote_stats.get('active_votes', 0)}",
                        inline=True
                    )
                    
                    # 系統統計
                    system_stats = stats.get('system_statistics', {}).get('summary', {})
                    embed.add_field(
                        name="⚙️ 系統狀態",
                        value=f"資料庫: {system_stats.get('database_name', 'unknown')}\n"
                              f"狀態: {system_stats.get('status', 'unknown')}\n"
                              f"更新: {system_stats.get('system_time', 'N/A')[:19]}",
                        inline=True
                    )
                    
                except Exception as e:
                    embed = discord.Embed(
                        title="❌ 統計獲取失敗",
                        description=f"無法獲取統計資訊: {str(e)}",
                        color=0xe74c3c
                    )
            
            embed.set_footer(text=f"由 {interaction.user.display_name} 執行 | {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            await interaction.edit_original_response(embed=embed)
            
        except Exception as e:
            logger.error(f"資料庫管理指令錯誤: {e}")
            error_embed = discord.Embed(
                title="❌ 資料庫管理失敗",
                description=f"執行操作時發生錯誤: {str(e)}",
                color=0xe74c3c
            )
            try:
                await interaction.edit_original_response(embed=error_embed)
            except:
                await interaction.followup.send(embed=error_embed, ephemeral=True)


async def setup(bot):
    await bot.add_cog(SystemAdmin(bot))