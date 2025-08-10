# bot/cogs/dashboard_core.py - 高級分析儀表板核心 v1.7.0
"""
高級分析儀表板核心功能
提供Discord指令介面來生成和查看各種分析儀表板
"""

import discord
from discord.ext import commands
from discord import app_commands
from typing import Dict, List, Optional, Any
import json
import asyncio
from datetime import datetime, timezone

from bot.services.dashboard_manager import dashboard_manager, ChartType, MetricType
from bot.services.statistics_manager import StatisticsManager
from bot.utils.embed_builder import EmbedBuilder
from bot.views.dashboard_views import DashboardView, ChartDisplayView
from shared.logger import logger


class DashboardCore(commands.Cog):
    """高級分析儀表板核心功能"""
    
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.dashboard_manager = dashboard_manager
        self.stats_manager = StatisticsManager()
        logger.info("✅ 高級分析儀表板系統已初始化")
    
    # ========== 儀表板指令 ==========
    
    @app_commands.command(name="dashboard_overview", description="查看系統概覽儀表板")
    @app_commands.describe(
        days="分析天數 (默認30天)",
        refresh="是否刷新快取"
    )
    async def dashboard_overview(
        self, 
        interaction: discord.Interaction, 
        days: int = 30, 
        refresh: bool = False
    ):
        """查看系統概覽儀表板"""
        try:
            # 檢查權限
            if not interaction.user.guild_permissions.manage_guild:
                await interaction.response.send_message("❌ 需要管理伺服器權限才能查看儀表板", ephemeral=True)
                return
            
            # 驗證參數
            if not 1 <= days <= 365:
                await interaction.response.send_message("❌ 分析天數必須在1-365天之間", ephemeral=True)
                return
            
            await interaction.response.defer(ephemeral=True)
            
            # 清除快取 (如果需要)
            if refresh:
                await self.dashboard_manager.clear_dashboard_cache(f"overview_{interaction.guild.id}_{days}")
            
            # 生成儀表板數據
            dashboard_data = await self.dashboard_manager.generate_overview_dashboard(
                interaction.guild.id, days
            )
            
            # 創建嵌入式訊息
            embed = EmbedBuilder.build(
                title=f"📊 {dashboard_data.title}",
                description=f"系統綜合分析報告 - {interaction.guild.name}",
                color=0x3498db
            )
            
            # 添加關鍵指標
            metrics_text = []
            for metric_name, metric_data in dashboard_data.metrics.items():
                emoji = "📈" if metric_data.trend == "up" else "📉" if metric_data.trend == "down" else "➡️"
                status_emoji = "🟢" if metric_data.status == "good" else "🟡" if metric_data.status == "warning" else "🔴"
                
                metrics_text.append(
                    f"{status_emoji} **{metric_name.replace('_', ' ').title()}**: {metric_data.current_value} "
                    f"{emoji} ({metric_data.change_percentage:+.1f}%)"
                )
            
            if metrics_text:
                embed.add_field(
                    name="📋 關鍵指標",
                    value="\n".join(metrics_text[:5]),  # 限制顯示5個指標
                    inline=False
                )
            
            # 添加智能洞察
            if dashboard_data.insights:
                embed.add_field(
                    name="💡 智能洞察",
                    value="\n".join(dashboard_data.insights[:3]),  # 限制顯示3個洞察
                    inline=False
                )
            
            # 添加圖表數量信息
            embed.add_field(
                name="📊 可用圖表",
                value=f"共 {len(dashboard_data.charts)} 個分析圖表\n點擊下方按鈕查看詳細圖表",
                inline=False
            )
            
            # 添加更新資訊
            embed.set_footer(
                text=f"數據更新時間: {dashboard_data.generated_at.strftime('%Y-%m-%d %H:%M:%S UTC')} | "
                     f"下次更新: {dashboard_data.refresh_interval//60}分鐘後"
            )
            
            # 創建互動視圖
            view = DashboardView(interaction.user.id, dashboard_data)
            
            await interaction.followup.send(embed=embed, view=view, ephemeral=True)
            
        except Exception as e:
            logger.error(f"生成系統概覽儀表板失敗: {e}")
            await interaction.followup.send(f"❌ 生成儀表板失敗: {str(e)}", ephemeral=True)
    
    @app_commands.command(name="dashboard_performance", description="查看系統性能分析儀表板")
    @app_commands.describe(
        days="分析天數 (默認30天)"
    )
    async def dashboard_performance(self, interaction: discord.Interaction, days: int = 30):
        """查看系統性能分析儀表板"""
        try:
            # 檢查權限
            if not interaction.user.guild_permissions.manage_guild:
                await interaction.response.send_message("❌ 需要管理伺服器權限才能查看性能儀表板", ephemeral=True)
                return
            
            await interaction.response.defer(ephemeral=True)
            
            # 生成性能儀表板
            dashboard_data = await self.dashboard_manager.generate_performance_dashboard(
                interaction.guild.id, days
            )
            
            # 創建嵌入式訊息
            embed = EmbedBuilder.build(
                title=f"⚡ {dashboard_data.title}",
                description=f"系統性能深度分析 - {interaction.guild.name}",
                color=0xf39c12
            )
            
            # 添加性能摘要
            performance_summary = []
            for metric_name, metric_data in dashboard_data.metrics.items():
                if metric_name in ['response_time', 'system_uptime', 'sla_compliance']:
                    status_icon = "🟢" if metric_data.status == "good" else "🟡"
                    performance_summary.append(f"{status_icon} {metric_name.replace('_', ' ').title()}: {metric_data.current_value}")
            
            if performance_summary:
                embed.add_field(
                    name="🎯 性能摘要",
                    value="\n".join(performance_summary),
                    inline=False
                )
            
            # 添加改進建議
            if dashboard_data.insights:
                embed.add_field(
                    name="💡 性能建議",
                    value="\n".join(dashboard_data.insights[:3]),
                    inline=False
                )
            
            embed.set_footer(text=f"分析期間: {days}天 | 生成時間: {dashboard_data.generated_at.strftime('%H:%M:%S')}")
            
            # 創建互動視圖
            view = DashboardView(interaction.user.id, dashboard_data)
            
            await interaction.followup.send(embed=embed, view=view, ephemeral=True)
            
        except Exception as e:
            logger.error(f"生成性能儀表板失敗: {e}")
            await interaction.followup.send(f"❌ 生成性能儀表板失敗: {str(e)}", ephemeral=True)
    
    @app_commands.command(name="dashboard_prediction", description="查看智能預測分析儀表板")
    async def dashboard_prediction(self, interaction: discord.Interaction):
        """查看智能預測分析儀表板"""
        try:
            # 檢查權限
            if not interaction.user.guild_permissions.administrator:
                await interaction.response.send_message("❌ 需要管理員權限才能查看預測分析", ephemeral=True)
                return
            
            await interaction.response.defer(ephemeral=True)
            
            # 生成預測儀表板
            dashboard_data = await self.dashboard_manager.generate_predictive_dashboard(
                interaction.guild.id
            )
            
            # 創建嵌入式訊息
            embed = EmbedBuilder.build(
                title=f"🔮 {dashboard_data.title}",
                description=f"基於AI的未來趨勢預測 - {interaction.guild.name}",
                color=0x9b59b6
            )
            
            # 添加預測摘要
            prediction_summary = []
            for metric_name, metric_data in dashboard_data.metrics.items():
                trend_emoji = "📈" if metric_data.trend == "up" else "📉" if metric_data.trend == "down" else "➡️"
                prediction_summary.append(f"{trend_emoji} {metric_name.replace('_', ' ').title()}: {metric_data.current_value}")
            
            if prediction_summary:
                embed.add_field(
                    name="🎯 預測摘要",
                    value="\n".join(prediction_summary[:4]),
                    inline=False
                )
            
            # 添加預測洞察
            if dashboard_data.insights:
                embed.add_field(
                    name="🧠 AI洞察",
                    value="\n".join(dashboard_data.insights[:3]),
                    inline=False
                )
            
            # 添加預測說明
            embed.add_field(
                name="ℹ️ 預測說明",
                value="預測基於歷史數據和趨勢分析，僅供參考。建議結合實際情況進行決策。",
                inline=False
            )
            
            embed.set_footer(text=f"預測時間窗: 30天 | AI模型更新: 每小時")
            
            # 創建互動視圖
            view = DashboardView(interaction.user.id, dashboard_data)
            
            await interaction.followup.send(embed=embed, view=view, ephemeral=True)
            
        except Exception as e:
            logger.error(f"生成預測儀表板失敗: {e}")
            await interaction.followup.send(f"❌ 生成預測儀表板失敗: {str(e)}", ephemeral=True)
    
    @app_commands.command(name="dashboard_cache", description="管理儀表板快取")
    @app_commands.describe(
        action="操作類型",
        cache_key="特定快取鍵 (可選)"
    )
    @app_commands.choices(action=[
        app_commands.Choice(name="查看快取資訊", value="info"),
        app_commands.Choice(name="清除所有快取", value="clear_all"),
        app_commands.Choice(name="清除特定快取", value="clear_key")
    ])
    async def dashboard_cache(
        self, 
        interaction: discord.Interaction, 
        action: str,
        cache_key: str = None
    ):
        """管理儀表板快取"""
        try:
            # 檢查權限
            if not interaction.user.guild_permissions.administrator:
                await interaction.response.send_message("❌ 需要管理員權限才能管理快取", ephemeral=True)
                return
            
            if action == "info":
                # 查看快取資訊
                cache_info = await self.dashboard_manager.get_dashboard_cache_info()
                
                embed = EmbedBuilder.build(
                    title="🗄️ 儀表板快取資訊",
                    color=0x95a5a6
                )
                
                embed.add_field(
                    name="📊 基本資訊",
                    value=f"快取數量: {cache_info['cache_count']}\n"
                          f"TTL: {cache_info['cache_ttl']}秒\n"
                          f"記憶體使用: ~{cache_info['memory_usage']//1024}KB",
                    inline=True
                )
                
                if cache_info['cache_keys']:
                    embed.add_field(
                        name="🔑 快取鍵列表",
                        value="\n".join(f"• `{key}`" for key in cache_info['cache_keys'][:5]),
                        inline=False
                    )
                
                await interaction.response.send_message(embed=embed, ephemeral=True)
                
            elif action == "clear_all":
                # 清除所有快取
                await self.dashboard_manager.clear_dashboard_cache()
                
                embed = EmbedBuilder.build(
                    title="✅ 快取已清除",
                    description="所有儀表板快取已成功清除",
                    color=0x2ecc71
                )
                
                await interaction.response.send_message(embed=embed, ephemeral=True)
                
            elif action == "clear_key":
                # 清除特定快取
                if not cache_key:
                    await interaction.response.send_message("❌ 請提供要清除的快取鍵", ephemeral=True)
                    return
                
                await self.dashboard_manager.clear_dashboard_cache(cache_key)
                
                embed = EmbedBuilder.build(
                    title="✅ 快取已清除",
                    description=f"快取鍵 `{cache_key}` 已清除",
                    color=0x2ecc71
                )
                
                await interaction.response.send_message(embed=embed, ephemeral=True)
            
        except Exception as e:
            logger.error(f"管理儀表板快取失敗: {e}")
            await interaction.response.send_message(f"❌ 操作失敗: {str(e)}", ephemeral=True)
    
    # ========== 實時數據指令 ==========
    
    @app_commands.command(name="dashboard_realtime", description="查看實時系統狀態")
    async def dashboard_realtime(self, interaction: discord.Interaction):
        """查看實時系統狀態"""
        try:
            # 檢查權限
            if not interaction.user.guild_permissions.manage_guild:
                await interaction.response.send_message("❌ 需要管理伺服器權限", ephemeral=True)
                return
            
            await interaction.response.defer(ephemeral=True)
            
            # 獲取實時數據
            realtime_data = await self._get_realtime_data(interaction.guild.id)
            
            embed = EmbedBuilder.build(
                title="⚡ 實時系統狀態",
                description=f"即時數據監控 - {interaction.guild.name}",
                color=0xe74c3c
            )
            
            # 系統狀態
            embed.add_field(
                name="🖥️ 系統狀態",
                value=f"在線狀態: {'🟢 正常' if realtime_data['system_online'] else '🔴 異常'}\n"
                      f"活躍用戶: {realtime_data['active_users']}\n"
                      f"當前負載: {realtime_data['current_load']:.1f}%",
                inline=True
            )
            
            # 票券狀態
            priority_dist = realtime_data.get('priority_distribution', {})
            high_priority = priority_dist.get('high', 0)
            medium_priority = priority_dist.get('medium', 0)
            low_priority = priority_dist.get('low', 0)
            
            embed.add_field(
                name="🎫 票券狀態",
                value=f"開啟票券: {realtime_data['open_tickets']}\n"
                      f"🔴 高優先級: {high_priority}\n"
                      f"🟡 中優先級: {medium_priority}\n"
                      f"🟢 低優先級: {low_priority}\n"
                      f"今日新建: {realtime_data['today_new_tickets']}",
                inline=True
            )
            
            # 工作流程狀態
            embed.add_field(
                name="⚙️ 工作流程",
                value=f"活躍流程: {realtime_data['active_workflows']}\n"
                      f"執行中: {realtime_data['running_executions']}\n"
                      f"今日執行: {realtime_data['today_executions']}",
                inline=True
            )
            
            # 添加系統健康指標
            system_health = "🟢 正常"
            if realtime_data.get('error'):
                system_health = "🔴 異常"
            elif realtime_data['current_load'] > 80:
                system_health = "🟡 負載高"
            elif realtime_data['open_tickets'] == 0:
                system_health = "💤 閒置"
            
            embed.add_field(
                name="📊 系統健康",
                value=f"整體狀態: {system_health}\n"
                      f"數據來源: {'📊 實時統計' if realtime_data.get('last_updated') else '🔧 系統估算'}\n"
                      f"負載等級: {'🔴 高' if realtime_data['current_load'] > 70 else '🟡 中' if realtime_data['current_load'] > 30 else '🟢 低'}",
                inline=False
            )
            
            # 設置頁腳，包含數據更新時間
            last_updated = realtime_data.get('last_updated')
            if last_updated:
                try:
                    from dateutil import parser
                    update_time = parser.isoparse(last_updated)
                    footer_text = f"數據更新: {update_time.strftime('%H:%M:%S UTC')} | 刷新間隔: 30秒"
                except:
                    footer_text = f"數據更新: {datetime.now(timezone.utc).strftime('%H:%M:%S UTC')} | 實時監控"
            else:
                footer_text = f"數據更新: {datetime.now(timezone.utc).strftime('%H:%M:%S UTC')} | 系統估算"
            
            embed.set_footer(text=footer_text)
            
            # 如果有錯誤，添加錯誤信息
            if realtime_data.get('error'):
                embed.add_field(
                    name="⚠️ 系統警告",
                    value=f"檢測到問題: {str(realtime_data['error'])[:100]}...",
                    inline=False
                )
            
            await interaction.followup.send(embed=embed, ephemeral=True)
            
        except Exception as e:
            logger.error(f"獲取實時數據失敗: {e}")
            await interaction.followup.send(f"❌ 獲取實時數據失敗: {str(e)}", ephemeral=True)
    
    async def _get_realtime_data(self, guild_id: int) -> Dict[str, Any]:
        """獲取實時數據"""
        try:
            # 使用 StatisticsManager 獲取真實的實時統計
            realtime_stats = await self.stats_manager.get_realtime_stats(guild_id)
            
            if not realtime_stats:
                # 如果統計數據不可用，使用基本的模擬數據
                return {
                    'system_online': True,
                    'active_users': 0,
                    'current_load': 0.0,
                    'open_tickets': 0,
                    'pending_tickets': 0,
                    'today_new_tickets': 0,
                    'active_workflows': 0,
                    'running_executions': 0,
                    'today_executions': 0
                }
            
            # 獲取額外的實時數據
            try:
                # 獲取工作流程數據（如果可用）
                workflow_data = await self._get_workflow_realtime_data(guild_id)
            except Exception as e:
                logger.warning(f"獲取工作流程實時數據失敗: {e}")
                workflow_data = {
                    'active_workflows': 0,
                    'running_executions': 0,
                    'today_executions': 0
                }
            
            # 計算系統負載（基於開啟票券數）
            open_tickets = realtime_stats.get('open_tickets', 0)
            max_capacity = 50  # 假設最大處理能力為50張票券
            current_load = min((open_tickets / max_capacity) * 100, 100.0) if max_capacity > 0 else 0.0
            
            # 估算活躍用戶數（基於今日創建的票券）
            today_created = realtime_stats.get('today_created', 0)
            estimated_active_users = today_created * 2  # 假設每2張票券對應1個活躍用戶
            
            realtime_data = {
                'system_online': True,
                'active_users': estimated_active_users,
                'current_load': current_load,
                'open_tickets': realtime_stats.get('open_tickets', 0),
                'pending_tickets': realtime_stats.get('priority_distribution', {}).get('high', 0),
                'today_new_tickets': realtime_stats.get('today_created', 0),
                'active_workflows': workflow_data.get('active_workflows', 0),
                'running_executions': workflow_data.get('running_executions', 0),
                'today_executions': workflow_data.get('today_executions', 0),
                'last_updated': realtime_stats.get('last_updated'),
                'priority_distribution': realtime_stats.get('priority_distribution', {})
            }
            
            return realtime_data
            
        except Exception as e:
            logger.error(f"獲取實時數據失敗: {e}")
            return {
                'system_online': False,
                'active_users': 0,
                'current_load': 0.0,
                'open_tickets': 0,
                'pending_tickets': 0,
                'today_new_tickets': 0,
                'active_workflows': 0,
                'running_executions': 0,
                'today_executions': 0,
                'error': str(e)
            }
    
    async def _get_workflow_realtime_data(self, guild_id: int) -> Dict[str, Any]:
        """獲取工作流程實時數據"""
        try:
            # 嘗試獲取工作流程數據
            from bot.db.workflow_dao import WorkflowDAO
            workflow_dao = WorkflowDAO()
            
            # 獲取活躍工作流程
            active_workflows = await workflow_dao.get_active_workflows(guild_id)
            
            # 獲取今日執行數據
            today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
            today_executions = await workflow_dao.get_executions_count(
                guild_id=guild_id,
                start_time=today_start
            )
            
            # 獲取執行中的工作流程
            running_executions = await workflow_dao.get_running_executions_count(guild_id)
            
            return {
                'active_workflows': len(active_workflows) if active_workflows else 0,
                'running_executions': running_executions if running_executions else 0,
                'today_executions': today_executions if today_executions else 0
            }
            
        except Exception as e:
            logger.warning(f"工作流程實時數據不可用: {e}")
            # 如果工作流程系統不可用，返回默認值
            return {
                'active_workflows': 0,
                'running_executions': 0,
                'today_executions': 0
            }
    
    # ========== 錯誤處理 ==========
    
    async def cog_app_command_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        """處理應用指令錯誤"""
        logger.error(f"儀表板指令錯誤: {error}")
        
        if not interaction.response.is_done():
            await interaction.response.send_message("❌ 指令執行時發生錯誤，請稍後再試", ephemeral=True)
        else:
            await interaction.followup.send("❌ 操作失敗，請檢查系統狀態", ephemeral=True)


async def setup(bot):
    await bot.add_cog(DashboardCore(bot))