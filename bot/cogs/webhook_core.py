# bot/cogs/webhook_core.py - Webhook整合核心 v1.7.0
"""
Webhook整合核心功能
提供Discord指令介面來管理和配置Webhook
"""

import discord
from discord.ext import commands
from discord import app_commands
from typing import Dict, List, Optional, Any
import json
import asyncio
from datetime import datetime, timezone

from bot.services.webhook_manager import webhook_manager, WebhookType, WebhookEvent, WebhookStatus
from bot.views.webhook_views import WebhookManagerView, WebhookConfigModal
from bot.utils.embed_builder import EmbedBuilder
from shared.logger import logger

class WebhookCore(commands.Cog):
    """Webhook整合核心功能"""
    
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.webhook_manager = webhook_manager
        logger.info("✅ Webhook系統已初始化")
    
    async def cog_load(self):
        """Cog載入時初始化Webhook系統"""
        try:
            await self.webhook_manager.initialize()
            logger.info("✅ Webhook系統Cog載入完成")
        except Exception as e:
            logger.error(f"❌ Webhook系統Cog載入失敗: {e}")
    
    async def cog_unload(self):
        """Cog卸載時關閉Webhook系統"""
        try:
            await self.webhook_manager.shutdown()
            logger.info("✅ Webhook系統已關閉")
        except Exception as e:
            logger.error(f"❌ Webhook系統關閉失敗: {e}")
    
    # ========== Webhook管理指令 ==========
    
    # @app_commands.command(name="webhook_create", description="創庺新的Webhook")  # 移至管理選單
    @app_commands.describe(
        name="Webhook名稱",
        url="目標URL",
        webhook_type="Webhook類型"
    )
    @app_commands.choices(webhook_type=[
        app_commands.Choice(name="發送 (Outgoing)", value="outgoing"),
        app_commands.Choice(name="接收 (Incoming)", value="incoming"),
        app_commands.Choice(name="雙向 (Both)", value="both")
    ])
    async def create_webhook(
        self, 
        interaction: discord.Interaction, 
        name: str,
        url: str,
        webhook_type: str = "outgoing"
    ):
        """創建Webhook"""
        try:
            # 檢查權限
            if not interaction.user.guild_permissions.administrator:
                await interaction.response.send_message("❌ 需要管理員權限才能創建Webhook", ephemeral=True)
                return
            
            # 驗證URL格式
            if not url.startswith(('http://', 'https://')):
                await interaction.response.send_message("❌ 請提供有效的URL (必須以http://或https://開頭)", ephemeral=True)
                return
            
            await interaction.response.defer(ephemeral=True)
            
            # 創建Webhook配置數據
            config_data = {
                'name': name,
                'url': url,
                'type': webhook_type,
                'events': ['custom_event'],  # 默認事件，用戶後續可以修改
                'guild_id': interaction.guild.id,
                'created_by': interaction.user.id
            }
            
            # 創建Webhook
            webhook_id = await self.webhook_manager.create_webhook(config_data)
            
            # 獲取創建的Webhook信息
            webhook_info = self.webhook_manager.webhooks[webhook_id]
            
            embed = EmbedBuilder.build(
                title="✅ Webhook已創建",
                description=f"Webhook **{name}** 已成功創建",
                color=0x2ecc71
            )
            
            embed.add_field(
                name="📋 基本資訊",
                value=f"ID: `{webhook_id}`\n"
                      f"類型: {webhook_type.title()}\n"
                      f"URL: {url[:50]}{'...' if len(url) > 50 else ''}\n"
                      f"狀態: 啟用",
                inline=False
            )
            
            if webhook_info.secret:
                embed.add_field(
                    name="🔐 安全資訊",
                    value=f"密鑰: `{webhook_info.secret[:16]}...`\n"
                          f"簽名驗證: 已啟用",
                    inline=False
                )
            
            embed.add_field(
                name="🛠️ 下一步",
                value="使用 `/webhook_config` 配置事件和其他設定",
                inline=False
            )
            
            await interaction.followup.send(embed=embed, ephemeral=True)
            
        except Exception as e:
            logger.error(f"創建Webhook失敗: {e}")
            await interaction.followup.send(f"❌ 創建Webhook失敗: {str(e)}", ephemeral=True)
    
    # @app_commands.command(name="webhook_list", description="查看Webhook列表")  # 移至管理選單
    @app_commands.describe(
        status="篩選Webhook狀態"
    )
    @app_commands.choices(status=[
        app_commands.Choice(name="全部", value="all"),
        app_commands.Choice(name="啟用", value="active"),
        app_commands.Choice(name="停用", value="inactive"),
        app_commands.Choice(name="暫停", value="paused"),
        app_commands.Choice(name="錯誤", value="error")
    ])
    async def list_webhooks(self, interaction: discord.Interaction, status: str = "all"):
        """查看Webhook列表"""
        try:
            # 檢查權限
            if not interaction.user.guild_permissions.manage_guild:
                await interaction.response.send_message("❌ 需要管理伺服器權限", ephemeral=True)
                return
            
            webhooks = self.webhook_manager.get_webhooks(guild_id=interaction.guild.id)
            
            if status != "all":
                webhooks = [w for w in webhooks if w['status'] == status]
            
            if not webhooks:
                embed = EmbedBuilder.build(
                    title="📋 Webhook列表",
                    description="目前沒有Webhook",
                    color=0x95a5a6
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return
            
            embed = EmbedBuilder.build(
                title="📋 Webhook列表",
                description=f"共 {len(webhooks)} 個Webhook",
                color=0x3498db
            )
            
            for webhook in webhooks[:10]:  # 最多顯示10個
                status_emoji = {
                    'active': '✅',
                    'inactive': '⏸️',
                    'paused': '⏸️',
                    'error': '❌'
                }.get(webhook['status'], '❓')
                
                type_emoji = {
                    'outgoing': '📤',
                    'incoming': '📥',
                    'both': '🔄'
                }.get(webhook['type'], '🔧')
                
                embed.add_field(
                    name=f"{status_emoji} {webhook['name']}",
                    value=f"{type_emoji} {webhook['type'].title()}\n"
                          f"事件: {len(webhook['events'])} 個\n"
                          f"成功率: {webhook['success_count']}/{webhook['success_count'] + webhook['failure_count']}",
                    inline=True
                )
            
            if len(webhooks) > 10:
                embed.add_field(
                    name="📄 更多",
                    value=f"還有 {len(webhooks) - 10} 個Webhook...",
                    inline=False
                )
            
            # 添加管理界面
            view = WebhookManagerView(interaction.user.id, interaction.guild.id)
            
            await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
            
        except Exception as e:
            logger.error(f"獲取Webhook列表失敗: {e}")
            await interaction.response.send_message(f"❌ 獲取列表失敗: {str(e)}", ephemeral=True)
    
    # @app_commands.command(name="webhook_config", description="配置Webhook設定")  # 移至管理選單
    @app_commands.describe(
        webhook_name="Webhook名稱"
    )
    async def config_webhook(self, interaction: discord.Interaction, webhook_name: str):
        """配置Webhook"""
        try:
            # 檢查權限
            if not interaction.user.guild_permissions.administrator:
                await interaction.response.send_message("❌ 需要管理員權限才能配置Webhook", ephemeral=True)
                return
            
            # 尋找Webhook
            webhooks = self.webhook_manager.get_webhooks(guild_id=interaction.guild.id)
            target_webhook = None
            
            for webhook in webhooks:
                if webhook['name'].lower() == webhook_name.lower():
                    target_webhook = webhook
                    break
            
            if not target_webhook:
                await interaction.response.send_message(f"❌ 找不到Webhook: {webhook_name}", ephemeral=True)
                return
            
            # 顯示配置介面
            modal = WebhookConfigModal(target_webhook['id'], target_webhook)
            await interaction.response.send_modal(modal)
            
        except Exception as e:
            logger.error(f"配置Webhook失敗: {e}")
            await interaction.response.send_message(f"❌ 配置失敗: {str(e)}", ephemeral=True)
    
    # @app_commands.command(name="webhook_test", description="測試Webhook")  # 已移除以節省指令空間
    @app_commands.describe(
        webhook_name="Webhook名稱"
    )
    async def test_webhook(self, interaction: discord.Interaction, webhook_name: str):
        """測試Webhook"""
        try:
            # 檢查權限
            if not interaction.user.guild_permissions.manage_guild:
                await interaction.response.send_message("❌ 需要管理伺服器權限", ephemeral=True)
                return
            
            await interaction.response.defer(ephemeral=True)
            
            # 尋找Webhook
            webhooks = self.webhook_manager.get_webhooks(guild_id=interaction.guild.id)
            target_webhook = None
            
            for webhook in webhooks:
                if webhook['name'].lower() == webhook_name.lower():
                    target_webhook = webhook
                    break
            
            if not target_webhook:
                await interaction.followup.send(f"❌ 找不到Webhook: {webhook_name}", ephemeral=True)
                return
            
            # 發送測試事件
            test_data = {
                'test': True,
                'message': 'This is a test webhook from Potato Bot',
                'timestamp': datetime.now(timezone.utc).isoformat(),
                'triggered_by': interaction.user.name,
                'guild_name': interaction.guild.name
            }
            
            await self.webhook_manager.trigger_webhook_event(
                WebhookEvent.CUSTOM_EVENT,
                interaction.guild.id,
                test_data
            )
            
            embed = EmbedBuilder.build(
                title="🧪 Webhook測試",
                description=f"測試事件已發送到 **{target_webhook['name']}**",
                color=0xf39c12
            )
            
            embed.add_field(
                name="📋 測試資料",
                value=f"事件類型: custom_event\n"
                      f"觸發者: {interaction.user.name}\n"
                      f"時間戳: {datetime.now(timezone.utc).strftime('%H:%M:%S UTC')}",
                inline=False
            )
            
            embed.add_field(
                name="ℹ️ 說明",
                value="請檢查目標端點是否收到測試數據",
                inline=False
            )
            
            await interaction.followup.send(embed=embed, ephemeral=True)
            
        except Exception as e:
            logger.error(f"測試Webhook失敗: {e}")
            await interaction.followup.send(f"❌ 測試失敗: {str(e)}", ephemeral=True)
    
    # @app_commands.command(name="webhook_stats", description="查看Webhook統計")  # 移至管理選單
    @app_commands.describe(
        webhook_name="Webhook名稱 (可選)"
    )
    async def webhook_stats(self, interaction: discord.Interaction, webhook_name: str = None):
        """查看Webhook統計"""
        try:
            # 檢查權限
            if not interaction.user.guild_permissions.manage_guild:
                await interaction.response.send_message("❌ 需要管理伺服器權限", ephemeral=True)
                return
            
            if webhook_name:
                # 顯示特定Webhook統計
                webhooks = self.webhook_manager.get_webhooks(guild_id=interaction.guild.id)
                target_webhook = None
                
                for webhook in webhooks:
                    if webhook['name'].lower() == webhook_name.lower():
                        target_webhook = webhook
                        break
                
                if not target_webhook:
                    await interaction.response.send_message(f"❌ 找不到Webhook: {webhook_name}", ephemeral=True)
                    return
                
                embed = EmbedBuilder.build(
                    title=f"📊 {target_webhook['name']} 統計",
                    description="Webhook詳細統計資訊",
                    color=0x9b59b6
                )
                
                embed.add_field(
                    name="📋 基本統計",
                    value=f"成功執行: {target_webhook['success_count']}\n"
                          f"失敗執行: {target_webhook['failure_count']}\n"
                          f"成功率: {(target_webhook['success_count'] / max(target_webhook['success_count'] + target_webhook['failure_count'], 1) * 100):.1f}%",
                    inline=True
                )
                
                embed.add_field(
                    name="⚙️ 配置資訊",
                    value=f"類型: {target_webhook['type'].title()}\n"
                          f"事件: {len(target_webhook['events'])} 個\n"
                          f"狀態: {target_webhook['status'].title()}",
                    inline=True
                )
                
                if target_webhook.get('last_triggered'):
                    last_triggered = datetime.fromisoformat(target_webhook['last_triggered'].replace('Z', '+00:00'))
                    embed.add_field(
                        name="⏰ 最後觸發",
                        value=f"<t:{int(last_triggered.timestamp())}:R>",
                        inline=False
                    )
            
            else:
                # 顯示系統整體統計
                system_stats = self.webhook_manager.get_webhook_statistics()
                
                embed = EmbedBuilder.build(
                    title="📊 Webhook系統統計",
                    description="系統整體Webhook使用統計",
                    color=0x9b59b6
                )
                
                embed.add_field(
                    name="📋 基本統計",
                    value=f"總Webhook數: {system_stats['total_webhooks']}\n"
                          f"啟用中: {system_stats['active_webhooks']}\n"
                          f"總請求數: {system_stats['total_sent'] + system_stats['total_received']}",
                    inline=True
                )
                
                embed.add_field(
                    name="📊 執行統計",
                    value=f"發送請求: {system_stats['total_sent']}\n"
                          f"接收請求: {system_stats['total_received']}\n"
                          f"成功率: {system_stats['success_rate']:.1f}%",
                    inline=True
                )
                
                # 事件分佈
                if system_stats['event_distribution']:
                    event_info = []
                    for event, count in list(system_stats['event_distribution'].items())[:5]:
                        event_info.append(f"• {event}: {count}")
                    
                    embed.add_field(
                        name="🎯 熱門事件",
                        value="\n".join(event_info),
                        inline=False
                    )
            
            await interaction.response.send_message(embed=embed, ephemeral=True)
            
        except Exception as e:
            logger.error(f"獲取Webhook統計失敗: {e}")
            await interaction.response.send_message(f"❌ 獲取統計失敗: {str(e)}", ephemeral=True)
    
    # @app_commands.command(name="webhook_delete", description="刪除Webhook")  # 移至管理選單
    @app_commands.describe(
        webhook_name="要刪除的Webhook名稱"
    )
    async def delete_webhook(self, interaction: discord.Interaction, webhook_name: str):
        """刪除Webhook"""
        try:
            # 檢查權限
            if not interaction.user.guild_permissions.administrator:
                await interaction.response.send_message("❌ 需要管理員權限才能刪除Webhook", ephemeral=True)
                return
            
            # 尋找Webhook
            webhooks = self.webhook_manager.get_webhooks(guild_id=interaction.guild.id)
            target_webhook = None
            
            for webhook in webhooks:
                if webhook['name'].lower() == webhook_name.lower():
                    target_webhook = webhook
                    break
            
            if not target_webhook:
                await interaction.response.send_message(f"❌ 找不到Webhook: {webhook_name}", ephemeral=True)
                return
            
            # 確認刪除
            embed = EmbedBuilder.build(
                title="⚠️ 確認刪除",
                description=f"確定要刪除Webhook **{target_webhook['name']}** 嗎？",
                color=0xe74c3c
            )
            
            embed.add_field(
                name="ℹ️ 警告",
                value="此操作無法復原，所有相關設定和統計數據將被永久刪除",
                inline=False
            )
            
            # 創建確認按鈕
            class ConfirmDeleteView(discord.ui.View):
                def __init__(self, webhook_id: str, webhook_name: str):
                    super().__init__(timeout=60)
                    self.webhook_id = webhook_id
                    self.webhook_name = webhook_name
                
                @discord.ui.button(label="確認刪除", style=discord.ButtonStyle.danger)
                async def confirm_delete(self, interaction: discord.Interaction, button: discord.ui.Button):
                    success = await webhook_manager.delete_webhook(self.webhook_id)
                    
                    if success:
                        embed = EmbedBuilder.build(
                            title="✅ Webhook已刪除",
                            description=f"Webhook **{self.webhook_name}** 已成功刪除",
                            color=0x2ecc71
                        )
                    else:
                        embed = EmbedBuilder.build(
                            title="❌ 刪除失敗",
                            description="刪除Webhook時發生錯誤",
                            color=0xe74c3c
                        )
                    
                    await interaction.response.edit_message(embed=embed, view=None)
                
                @discord.ui.button(label="取消", style=discord.ButtonStyle.secondary)
                async def cancel_delete(self, interaction: discord.Interaction, button: discord.ui.Button):
                    embed = EmbedBuilder.build(
                        title="❌ 已取消",
                        description="Webhook刪除已取消",
                        color=0x95a5a6
                    )
                    await interaction.response.edit_message(embed=embed, view=None)
            
            view = ConfirmDeleteView(target_webhook['id'], target_webhook['name'])
            await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
            
        except Exception as e:
            logger.error(f"刪除Webhook失敗: {e}")
            await interaction.response.send_message(f"❌ 刪除失敗: {str(e)}", ephemeral=True)
    
    # ========== 事件監聽器 ==========
    
    @commands.Cog.listener()
    async def on_message(self, message):
        """監聽消息事件並觸發相應的Webhook"""
        # 可以根據需要添加自動觸發邏輯
        pass
    
    # ========== 錯誤處理 ==========
    
    async def cog_app_command_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        """處理應用指令錯誤"""
        logger.error(f"Webhook指令錯誤: {error}")
        
        if not interaction.response.is_done():
            await interaction.response.send_message("❌ 指令執行時發生錯誤，請稍後再試", ephemeral=True)
        else:
            await interaction.followup.send("❌ 操作失敗，請檢查系統狀態", ephemeral=True)

async def setup(bot):
    await bot.add_cog(WebhookCore(bot))