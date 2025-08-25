# bot/cogs/workflow_core.py - 智能工作流程核心 v1.6.0
"""
智能工作流程核心功能
提供工作流程創建、管理、執行等指令
"""

import discord
from discord.ext import commands
from discord import app_commands
from typing import Dict, List, Optional, Any
import json
from datetime import datetime, timezone

from bot.services.workflow_engine import workflow_engine, WorkflowStatus, TriggerType, ActionType
from bot.db.workflow_dao import WorkflowDAO
from bot.utils.embed_builder import EmbedBuilder
from shared.logger import logger

class WorkflowCore(commands.Cog):
    """智能工作流程核心功能"""
    
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.workflow_dao = WorkflowDAO()
        self.workflow_engine = workflow_engine
        
        # 註冊事件觸發器
        self._register_event_triggers()
        logger.info("✅ 工作流程系統已初始化")
    
    def _register_event_triggers(self):
        """註冊Discord事件觸發器"""
        
        @self.bot.event
        async def on_member_join(member):
            await self.workflow_engine.trigger_workflows(
                TriggerType.MEMBER_JOINED,
                {
                    'guild_id': member.guild.id,
                    'user_id': member.id,
                    'username': member.name,
                    'display_name': member.display_name,
                    'joined_at': member.joined_at.isoformat() if member.joined_at else None
                }
            )
        
        @self.bot.event
        async def on_member_remove(member):
            await self.workflow_engine.trigger_workflows(
                TriggerType.MEMBER_LEFT,
                {
                    'guild_id': member.guild.id,
                    'user_id': member.id,
                    'username': member.name,
                    'display_name': member.display_name
                }
            )
    
    # ========== 工作流程管理指令 ==========
    
    @app_commands.command(name="workflow_create", description="創建新的工作流程")
    @app_commands.describe(
        name="工作流程名稱",
        description="工作流程描述"
    )
    async def create_workflow(self, interaction: discord.Interaction, name: str, description: str = ""):
        """創建工作流程"""
        try:
            # 檢查權限
            if not interaction.user.guild_permissions.manage_guild:
                await interaction.response.send_message("❌ 需要管理伺服器權限才能創建工作流程", ephemeral=True)
                return
            
            # 創建基礎工作流程數據
            workflow_data = {
                'name': name,
                'description': description,
                'guild_id': interaction.guild.id,
                'trigger_type': 'manual',
                'trigger_conditions': [],
                'trigger_parameters': {},
                'actions': [],
                'created_by': interaction.user.id,
                'tags': []
            }
            
            # 創建工作流程
            workflow_id = await workflow_engine.create_workflow(workflow_data)
            
            # 儲存到資料庫
            await self.workflow_dao.create_workflow({
                'id': workflow_id,
                **workflow_data
            })
            
            embed = EmbedBuilder.build(
                title="✅ 工作流程已創建",
                description=f"工作流程 **{name}** 已成功創建",
                color=0x2ecc71
            )
            
            embed.add_field(
                name="📋 基本資訊",
                value=f"ID: `{workflow_id}`\n"
                      f"狀態: 草稿\n"
                      f"觸發類型: 手動觸發",
                inline=False
            )
            
            embed.add_field(
                name="🛠️ 下一步",
                value="使用 `/workflow_edit` 來配置觸發器和動作",
                inline=False
            )
            
            await interaction.response.send_message(embed=embed, ephemeral=True)
            
        except Exception as e:
            logger.error(f"創建工作流程失敗: {e}")
            await interaction.response.send_message(f"❌ 創建工作流程失敗: {str(e)}", ephemeral=True)
    
    @app_commands.command(name="workflow_list", description="查看工作流程列表")
    @app_commands.describe(
        status="篩選工作流程狀態"
    )
    async def list_workflows(self, interaction: discord.Interaction, 
                           status: Optional[str] = None):
        """查看工作流程列表"""
        try:
            workflows = workflow_engine.get_workflows(
                guild_id=interaction.guild.id,
                status=WorkflowStatus(status) if status else None
            )
            
            if not workflows:
                embed = EmbedBuilder.build(
                    title="📋 工作流程列表",
                    description="目前沒有工作流程",
                    color=0x95a5a6
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return
            
            embed = EmbedBuilder.build(
                title="📋 工作流程列表",
                description=f"共 {len(workflows)} 個工作流程",
                color=0x3498db
            )
            
            for workflow in workflows[:10]:  # 最多顯示10個
                status_emoji = {
                    'draft': '📝',
                    'active': '✅',
                    'paused': '⏸️',
                    'disabled': '❌',
                    'archived': '🗃️'
                }.get(workflow['status'], '❓')
                
                trigger_emoji = {
                    'manual': '👆',
                    'ticket_created': '🎫',
                    'member_joined': '👋',
                    'scheduled': '⏰'
                }.get(workflow['trigger_type'], '🔧')
                
                embed.add_field(
                    name=f"{status_emoji} {workflow['name']}",
                    value=f"{trigger_emoji} {workflow['trigger_type']}\n"
                          f"動作: {workflow['action_count']} 個\n"
                          f"執行次數: {workflow['execution_count']}",
                    inline=True
                )
            
            if len(workflows) > 10:
                embed.add_field(
                    name="📄 更多",
                    value=f"還有 {len(workflows) - 10} 個工作流程...",
                    inline=False
                )
            
            await interaction.response.send_message(embed=embed, ephemeral=True)
            
        except Exception as e:
            logger.error(f"獲取工作流程列表失敗: {e}")
            await interaction.response.send_message(f"❌ 獲取列表失敗: {str(e)}", ephemeral=True)
    
    @app_commands.command(name="workflow_execute", description="手動執行工作流程")
    @app_commands.describe(
        workflow_name="工作流程名稱"
    )
    async def execute_workflow(self, interaction: discord.Interaction, workflow_name: str):
        """手動執行工作流程"""
        try:
            # 尋找工作流程
            workflows = workflow_engine.get_workflows(guild_id=interaction.guild.id)
            target_workflow = None
            
            for workflow in workflows:
                if workflow['name'].lower() == workflow_name.lower():
                    target_workflow = workflow
                    break
            
            if not target_workflow:
                await interaction.response.send_message(f"❌ 找不到工作流程: {workflow_name}", ephemeral=True)
                return
            
            # 檢查是否為手動觸發類型
            if target_workflow['trigger_type'] != 'manual':
                await interaction.response.send_message(
                    f"❌ 此工作流程不支援手動執行 (觸發類型: {target_workflow['trigger_type']})",
                    ephemeral=True
                )
                return
            
            # 執行工作流程
            execution_id = await workflow_engine.execute_workflow(
                target_workflow['id'],
                {
                    'manual_trigger': True,
                    'triggered_by': interaction.user.id,
                    'guild_id': interaction.guild.id,
                    'channel_id': interaction.channel.id
                }
            )
            
            if execution_id:
                embed = EmbedBuilder.build(
                    title="🚀 工作流程執行中",
                    description=f"工作流程 **{target_workflow['name']}** 已開始執行",
                    color=0xf39c12
                )
                
                embed.add_field(
                    name="📋 執行資訊",
                    value=f"執行ID: `{execution_id}`\n"
                          f"動作數量: {target_workflow['action_count']}\n"
                          f"執行時間: <t:{int(datetime.now(timezone.utc).timestamp())}:R>",
                    inline=False
                )
                
                await interaction.response.send_message(embed=embed, ephemeral=True)
            else:
                await interaction.response.send_message("❌ 工作流程執行失敗", ephemeral=True)
            
        except Exception as e:
            logger.error(f"執行工作流程失敗: {e}")
            await interaction.response.send_message(f"❌ 執行失敗: {str(e)}", ephemeral=True)
    
    @app_commands.command(name="workflow_status", description="查看工作流程執行狀態")
    @app_commands.describe(
        execution_id="執行ID"
    )
    async def workflow_status(self, interaction: discord.Interaction, execution_id: str):
        """查看工作流程執行狀態"""
        try:
            status = workflow_engine.get_execution_status(execution_id)
            
            if not status:
                await interaction.response.send_message(f"❌ 找不到執行記錄: {execution_id}", ephemeral=True)
                return
            
            # 狀態圖示
            status_icons = {
                'running': '🔄',
                'completed': '✅',
                'failed': '❌',
                'cancelled': '⏹️'
            }
            
            embed = EmbedBuilder.build(
                title=f"{status_icons.get(status['status'], '❓')} 工作流程執行狀態",
                description=f"工作流程: **{status['workflow_name']}**",
                color=0x3498db if status['status'] == 'running' else 
                      0x2ecc71 if status['status'] == 'completed' else 0xe74c3c
            )
            
            embed.add_field(
                name="📋 基本資訊",
                value=f"執行ID: `{status['id']}`\n"
                      f"狀態: {status['status']}\n"
                      f"開始時間: <t:{int(datetime.fromisoformat(status['start_time'].replace('Z', '+00:00')).timestamp())}:f>",
                inline=True
            )
            
            if status['end_time']:
                embed.add_field(
                    name="⏱️ 執行時間",
                    value=f"結束時間: <t:{int(datetime.fromisoformat(status['end_time'].replace('Z', '+00:00')).timestamp())}:f>",
                    inline=True
                )
            
            # 進度資訊
            progress = status.get('progress', {})
            if progress.get('total', 0) > 0:
                embed.add_field(
                    name="📊 執行進度",
                    value=f"{progress['completed']}/{progress['total']} ({progress['percentage']}%)\n"
                          f"{'█' * int(progress['percentage'] / 10)}{'░' * (10 - int(progress['percentage'] / 10))}",
                    inline=False
                )
            
            # 錯誤資訊
            if status.get('errors'):
                embed.add_field(
                    name="⚠️ 錯誤",
                    value="\n".join(status['errors'][:3]),  # 最多顯示3個錯誤
                    inline=False
                )
            
            await interaction.response.send_message(embed=embed, ephemeral=True)
            
        except Exception as e:
            logger.error(f"獲取執行狀態失敗: {e}")
            await interaction.response.send_message(f"❌ 獲取狀態失敗: {str(e)}", ephemeral=True)
    
    @app_commands.command(name="workflow_toggle", description="啟用/停用工作流程")
    @app_commands.describe(
        workflow_name="工作流程名稱"
    )
    async def toggle_workflow(self, interaction: discord.Interaction, workflow_name: str):
        """啟用/停用工作流程"""
        try:
            # 檢查權限
            if not interaction.user.guild_permissions.manage_guild:
                await interaction.response.send_message("❌ 需要管理伺服器權限", ephemeral=True)
                return
            
            # 尋找工作流程
            workflows = workflow_engine.get_workflows(guild_id=interaction.guild.id)
            target_workflow = None
            
            for workflow in workflows:
                if workflow['name'].lower() == workflow_name.lower():
                    target_workflow = workflow
                    break
            
            if not target_workflow:
                await interaction.response.send_message(f"❌ 找不到工作流程: {workflow_name}", ephemeral=True)
                return
            
            # 切換狀態
            current_status = target_workflow['status']
            new_status = 'active' if current_status != 'active' else 'paused'
            
            success = await workflow_engine.update_workflow(
                target_workflow['id'],
                {'status': new_status}
            )
            
            if success:
                # 更新資料庫
                await self.workflow_dao.update_workflow(
                    target_workflow['id'],
                    {'status': new_status},
                    interaction.user.id
                )
                
                status_text = "啟用" if new_status == 'active' else "停用"
                status_emoji = "✅" if new_status == 'active' else "⏸️"
                
                embed = EmbedBuilder.build(
                    title=f"{status_emoji} 工作流程已{status_text}",
                    description=f"工作流程 **{target_workflow['name']}** 已{status_text}",
                    color=0x2ecc71 if new_status == 'active' else 0xf39c12
                )
                
                await interaction.response.send_message(embed=embed, ephemeral=True)
            else:
                await interaction.response.send_message("❌ 更新工作流程狀態失敗", ephemeral=True)
            
        except Exception as e:
            logger.error(f"切換工作流程狀態失敗: {e}")
            await interaction.response.send_message(f"❌ 操作失敗: {str(e)}", ephemeral=True)
    
    @app_commands.command(name="workflow_stats", description="查看工作流程統計")
    async def workflow_statistics(self, interaction: discord.Interaction):
        """查看工作流程統計"""
        try:
            stats = workflow_engine.get_workflow_statistics(guild_id=interaction.guild.id)
            
            embed = EmbedBuilder.build(
                title="📊 工作流程統計",
                description=f"伺服器工作流程使用統計",
                color=0x9b59b6
            )
            
            embed.add_field(
                name="📋 基本統計",
                value=f"總工作流程: {stats['total_workflows']}\n"
                      f"活躍工作流程: {stats['active_workflows']}\n"
                      f"總執行次數: {stats['total_executions']}\n"
                      f"執行中: {stats['running_executions']}",
                inline=True
            )
            
            # 狀態分佈
            status_dist = stats.get('status_distribution', {})
            if status_dist:
                embed.add_field(
                    name="📊 狀態分佈",
                    value="\n".join([
                        f"{status}: {count}" 
                        for status, count in status_dist.items()
                    ]),
                    inline=True
                )
            
            # 觸發類型分佈
            trigger_dist = stats.get('trigger_distribution', {})
            if trigger_dist:
                embed.add_field(
                    name="🎯 觸發類型",
                    value="\n".join([
                        f"{trigger_type}: {count}" 
                        for trigger_type, count in trigger_dist.items()
                    ]),
                    inline=True
                )
            
            # 執行統計
            if stats['total_executions'] > 0:
                embed.add_field(
                    name="⏱️ 執行統計",
                    value=f"平均執行時間: {stats['average_execution_time']:.2f}秒",
                    inline=False
                )
            
            await interaction.response.send_message(embed=embed, ephemeral=True)
            
        except Exception as e:
            logger.error(f"獲取工作流程統計失敗: {e}")
            await interaction.response.send_message(f"❌ 獲取統計失敗: {str(e)}", ephemeral=True)
    
    # ========== 快捷工作流程模板 ==========
    
    @app_commands.command(name="workflow_template", description="創建工作流程模板")
    @app_commands.describe(
        template_type="模板類型",
        name="工作流程名稱"
    )
    @app_commands.choices(template_type=[
        app_commands.Choice(name="新成員歡迎", value="member_welcome"),
        app_commands.Choice(name="票券自動指派", value="ticket_auto_assign"),
        app_commands.Choice(name="SLA警告", value="sla_warning"),
        app_commands.Choice(name="定期報告", value="scheduled_report")
    ])
    async def create_workflow_template(self, interaction: discord.Interaction, 
                                     template_type: str, name: str):
        """創建工作流程模板"""
        try:
            # 檢查權限
            if not interaction.user.guild_permissions.manage_guild:
                await interaction.response.send_message("❌ 需要管理伺服器權限", ephemeral=True)
                return
            
            # 獲取模板配置
            template = self._get_workflow_template(template_type)
            if not template:
                await interaction.response.send_message(f"❌ 未知的模板類型: {template_type}", ephemeral=True)
                return
            
            # 創建工作流程
            workflow_data = {
                'name': name,
                'description': template['description'],
                'guild_id': interaction.guild.id,
                'trigger_type': template['trigger']['type'],
                'trigger_conditions': template['trigger'].get('conditions', []),
                'trigger_parameters': template['trigger'].get('parameters', {}),
                'actions': template['actions'],
                'created_by': interaction.user.id,
                'tags': template.get('tags', [])
            }
            
            workflow_id = await workflow_engine.create_workflow(workflow_data)
            
            # 儲存到資料庫
            await self.workflow_dao.create_workflow({
                'id': workflow_id,
                **workflow_data
            })
            
            embed = EmbedBuilder.build(
                title="✅ 模板工作流程已創建",
                description=f"基於 **{template['name']}** 模板創建的工作流程已就緒",
                color=0x2ecc71
            )
            
            embed.add_field(
                name="📋 模板資訊",
                value=f"名稱: {name}\n"
                      f"類型: {template['name']}\n"
                      f"觸發器: {template['trigger']['type']}\n"
                      f"動作數: {len(template['actions'])}",
                inline=False
            )
            
            await interaction.response.send_message(embed=embed, ephemeral=True)
            
        except Exception as e:
            logger.error(f"創建模板工作流程失敗: {e}")
            await interaction.response.send_message(f"❌ 創建失敗: {str(e)}", ephemeral=True)
    
    def _get_workflow_template(self, template_type: str) -> Optional[Dict[str, Any]]:
        """獲取工作流程模板"""
        templates = {
            "member_welcome": {
                "name": "新成員歡迎",
                "description": "當新成員加入時自動發送歡迎訊息並分配身分組",
                "trigger": {
                    "type": "member_joined"
                },
                "actions": [
                    {
                        "type": "send_message",
                        "parameters": {
                            "channel_type": "welcome",
                            "message": "歡迎 {user_mention} 加入伺服器！"
                        }
                    },
                    {
                        "type": "assign_role",
                        "parameters": {
                            "role_name": "新成員"
                        }
                    }
                ],
                "tags": ["歡迎", "自動化"]
            },
            
            "ticket_auto_assign": {
                "name": "票券自動指派",
                "description": "新票券創建時自動指派給合適的客服",
                "trigger": {
                    "type": "ticket_created"
                },
                "actions": [
                    {
                        "type": "assign_ticket",
                        "parameters": {
                            "assignment_method": "least_workload"
                        }
                    },
                    {
                        "type": "add_tag",
                        "parameters": {
                            "tags": ["auto-assigned"]
                        }
                    }
                ],
                "tags": ["票券", "指派", "自動化"]
            },
            
            "sla_warning": {
                "name": "SLA警告",
                "description": "當票券接近SLA違規時發送警告",
                "trigger": {
                    "type": "sla_breach",
                    "conditions": [
                        {
                            "field": "sla_remaining_minutes",
                            "operator": "<=",
                            "value": 30
                        }
                    ]
                },
                "actions": [
                    {
                        "type": "notify_user",
                        "parameters": {
                            "target": "assigned_staff",
                            "message": "⚠️ 票券 {ticket_id} 即將違反SLA！"
                        }
                    },
                    {
                        "type": "change_priority",
                        "parameters": {
                            "priority": "high"
                        }
                    }
                ],
                "tags": ["SLA", "警告", "優先級"]
            },
            
            "scheduled_report": {
                "name": "定期報告",
                "description": "定期發送系統使用報告",
                "trigger": {
                    "type": "scheduled",
                    "parameters": {
                        "cron": "0 9 * * 1"  # 每週一早上9點
                    }
                },
                "actions": [
                    {
                        "type": "generate_report",
                        "parameters": {
                            "report_type": "weekly_summary"
                        }
                    },
                    {
                        "type": "send_message",
                        "parameters": {
                            "channel_type": "admin",
                            "message": "📊 週報已生成"
                        }
                    }
                ],
                "tags": ["報告", "定期", "統計"]
            }
        }
        
        return templates.get(template_type)

async def setup(bot):
    await bot.add_cog(WorkflowCore(bot))