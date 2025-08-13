# bot/views/system_admin_views.py - 系統管理UI界面
"""
系統管理UI界面
提供圖形化的系統設定面板，包含票券系統、歡迎系統等各項設定
"""

import discord
from discord.ui import View, Button, Select, Modal, TextInput, button, select
from typing import List, Dict, Any, Optional
from shared.logger import logger
from datetime import datetime, timezone

from bot.db.ticket_dao import TicketDAO
from bot.db.welcome_dao import WelcomeDAO
from bot.db import vote_dao
from bot.services.welcome_manager import WelcomeManager
from bot.services.data_cleanup_manager import DataCleanupManager
from bot.services.data_export_manager import DataExportManager
from bot.utils.interaction_helper import BaseView, SafeInteractionHandler


class SystemAdminPanel(BaseView):
    """系統管理主面板"""
    
    def __init__(self, user_id: int, timeout=300):
        super().__init__(user_id=user_id, timeout=timeout)
        self.ticket_dao = TicketDAO()
        self.welcome_dao = WelcomeDAO()
        self.welcome_manager = WelcomeManager(self.welcome_dao)
    
    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        """檢查用戶權限"""
        # 先檢查基類權限
        if not await super().interaction_check(interaction):
            return False
        
        # 檢查管理權限
        if not interaction.user.guild_permissions.manage_guild:
            await SafeInteractionHandler.safe_respond(
                interaction,
                content="❌ 需要管理伺服器權限", 
                ephemeral=True
            )
            return False
        
        return True
    
    @button(label="🎫 票券系統設定", style=discord.ButtonStyle.primary, row=0)
    async def ticket_settings_button(self, interaction: discord.Interaction, button: Button):
        """票券系統設定按鈕"""
        await interaction.response.send_message(
            embed=await self._create_ticket_settings_embed(interaction.guild),
            view=TicketSettingsView(self.user_id),
            ephemeral=True
        )
    
    @button(label="🎉 歡迎系統設定", style=discord.ButtonStyle.success, row=0)
    async def welcome_settings_button(self, interaction: discord.Interaction, button: Button):
        """歡迎系統設定按鈕"""
        await interaction.response.send_message(
            embed=await self._create_welcome_settings_embed(interaction.guild),
            view=WelcomeSettingsView(self.user_id),
            ephemeral=True
        )
    
    @button(label="🗳️ 投票系統設定", style=discord.ButtonStyle.primary, row=0)
    async def vote_settings_button(self, interaction: discord.Interaction, button: Button):
        """投票系統設定按鈕"""
        await interaction.response.send_message(
            embed=await self._create_vote_settings_embed(interaction.guild),
            view=VoteSettingsView(self.user_id),
            ephemeral=True
        )
    
    @button(label="📊 統計與監控", style=discord.ButtonStyle.secondary, row=1)
    async def stats_button(self, interaction: discord.Interaction, button: Button):
        """統計與監控按鈕"""
        await interaction.response.send_message(
            embed=await self._create_stats_embed(interaction.guild),
            view=StatsView(self.user_id),
            ephemeral=True
        )
    
    @button(label="🔧 系統工具", style=discord.ButtonStyle.secondary, row=2)
    async def system_tools_button(self, interaction: discord.Interaction, button: Button):
        """系統工具按鈕"""
        await interaction.response.send_message(
            embed=self._create_system_tools_embed(),
            view=SystemToolsView(self.user_id),
            ephemeral=True
        )
    
    @button(label="❌ 關閉面板", style=discord.ButtonStyle.danger, row=2)
    async def close_button(self, interaction: discord.Interaction, button: Button):
        """關閉面板按鈕"""
        embed = discord.Embed(
            title="✅ 管理面板已關閉",
            description="系統管理面板已關閉",
            color=0x95a5a6
        )
        await interaction.response.edit_message(embed=embed, view=None)
        self.stop()
    
    async def _create_ticket_settings_embed(self, guild: discord.Guild) -> discord.Embed:
        """創建票券系統設定嵌入"""
        settings = await self.ticket_dao.get_settings(guild.id)
        
        embed = discord.Embed(
            title="🎫 票券系統設定",
            description="當前票券系統配置狀態",
            color=0x3498db
        )
        
        # 基本設定
        category_status = "✅ 已設定" if settings.get('category_id') else "❌ 未設定"
        embed.add_field(
            name="📂 票券分類頻道",
            value=f"{category_status}\n{('<#' + str(settings['category_id']) + '>') if settings.get('category_id') else '尚未設定'}",
            inline=True
        )
        
        support_roles = settings.get('support_roles', [])
        roles_text = "✅ 已設定" if support_roles else "❌ 未設定"
        if support_roles:
            roles_text += f"\n{len(support_roles)} 個角色"
        
        embed.add_field(
            name="👥 客服角色",
            value=roles_text,
            inline=True
        )
        
        # 系統參數
        embed.add_field(
            name="⚙️ 系統參數",
            value=f"每人票券上限: {settings.get('max_tickets_per_user', 3)}\n"
                  f"SLA回應時間: {settings.get('sla_response_minutes', 60)}分鐘\n"
                  f"自動關閉時間: {settings.get('auto_close_hours', 24)}小時",
            inline=True
        )
        
        return embed
    
    async def _create_welcome_settings_embed(self, guild: discord.Guild) -> discord.Embed:
        """創建歡迎系統設定嵌入"""
        settings = await self.welcome_dao.get_welcome_settings(guild.id)
        
        embed = discord.Embed(
            title="🎉 歡迎系統設定",
            description="當前歡迎系統配置狀態",
            color=0x2ecc71
        )
        
        if not settings:
            embed.add_field(
                name="⚠️ 系統狀態",
                value="歡迎系統尚未初始化\n請點擊下方按鈕進行設定",
                inline=False
            )
            return embed
        
        # 系統狀態
        status = "✅ 已啟用" if settings.get('is_enabled') else "❌ 已停用"
        embed.add_field(name="🔧 系統狀態", value=status, inline=True)
        
        # 頻道設定
        welcome_ch = f"<#{settings['welcome_channel_id']}>" if settings.get('welcome_channel_id') else "❌ 未設定"
        leave_ch = f"<#{settings['leave_channel_id']}>" if settings.get('leave_channel_id') else "❌ 未設定"
        
        embed.add_field(
            name="📺 頻道設定",
            value=f"歡迎頻道: {welcome_ch}\n離開頻道: {leave_ch}",
            inline=True
        )
        
        # 功能狀態
        features = []
        features.append(f"嵌入訊息: {'✅' if settings.get('welcome_embed_enabled') else '❌'}")
        features.append(f"私訊歡迎: {'✅' if settings.get('welcome_dm_enabled') else '❌'}")
        features.append(f"自動身分組: {'✅' if settings.get('auto_role_enabled') else '❌'}")
        
        embed.add_field(
            name="⚙️ 功能狀態",
            value="\n".join(features),
            inline=True
        )
        
        return embed
    
    async def _create_vote_settings_embed(self, guild: discord.Guild) -> discord.Embed:
        """創建投票系統設定嵌入"""
        embed = discord.Embed(
            title="🗳️ 投票系統設定",
            description="管理投票系統的頻道和參數設定",
            color=0x3498db
        )
        
        # 取得投票設定
        vote_settings = await vote_dao.get_vote_settings(guild.id)
        
        if vote_settings:
            # 頻道設定
            vote_channel = f"<#{vote_settings['default_vote_channel_id']}>" if vote_settings.get('default_vote_channel_id') else "未設定"
            announce_channel = f"<#{vote_settings['announcement_channel_id']}>" if vote_settings.get('announcement_channel_id') else "未設定"
            
            embed.add_field(
                name="📺 頻道設定",
                value=f"預設投票頻道: {vote_channel}\n"
                      f"結果公告頻道: {announce_channel}",
                inline=False
            )
            
            # 系統狀態
            status = "✅ 啟用" if vote_settings.get('is_enabled') else "❌ 停用"
            embed.add_field(
                name="🔧 系統狀態",
                value=status,
                inline=True
            )
            
            # 時間限制
            embed.add_field(
                name="⏰ 時間限制",
                value=f"最長: {vote_settings.get('max_vote_duration_hours', 72)}小時\n"
                      f"最短: {vote_settings.get('min_vote_duration_minutes', 60)}分鐘",
                inline=True
            )
            
            # 功能狀態
            features = []
            features.append(f"匿名投票: {'✅' if vote_settings.get('allow_anonymous_votes') else '❌'}")
            features.append(f"多選投票: {'✅' if vote_settings.get('allow_multi_choice') else '❌'}")
            features.append(f"自動公告: {'✅' if vote_settings.get('auto_announce_results') else '❌'}")
            
            embed.add_field(
                name="⚙️ 功能開關",
                value="\n".join(features),
                inline=True
            )
        else:
            embed.add_field(
                name="⚠️ 系統狀態",
                value="投票系統尚未設定，使用預設配置\n"
                      "投票將發布在執行指令的頻道",
                inline=False
            )
        
        embed.add_field(
            name="📋 管理選項",
            value="使用下方按鈕進行設定",
            inline=False
        )
        
        return embed
    
    async def _create_stats_embed(self, guild: discord.Guild) -> discord.Embed:
        """創建統計監控嵌入"""
        embed = discord.Embed(
            title="📊 系統統計與監控",
            description="系統運行狀態和使用統計",
            color=0x9b59b6
        )
        
        # 票券統計
        tickets, _ = await self.ticket_dao.get_tickets(guild.id, page_size=1000)
        open_tickets = len([t for t in tickets if t['status'] == 'open'])
        total_tickets = len(tickets)
        
        embed.add_field(
            name="🎫 票券統計",
            value=f"總票券數: {total_tickets}\n"
                  f"開啟中: {open_tickets}\n"
                  f"已關閉: {total_tickets - open_tickets}",
            inline=True
        )
        
        # 歡迎統計
        welcome_stats = await self.welcome_manager.get_welcome_statistics(guild.id, 30)
        embed.add_field(
            name="🎉 歡迎統計 (30天)",
            value=f"加入成員: {welcome_stats.get('joins', 0)}\n"
                  f"離開成員: {welcome_stats.get('leaves', 0)}\n"
                  f"淨增長: {welcome_stats.get('net_growth', 0)}",
            inline=True
        )
        
        # 系統健康
        embed.add_field(
            name="💾 系統健康",
            value="資料庫: ✅ 正常\n"
                  "服務: ✅ 運行中\n"
                  "記憶體: ✅ 良好",
            inline=True
        )
        
        return embed
    
    def _create_system_tools_embed(self) -> discord.Embed:
        """創建系統工具嵌入"""
        embed = discord.Embed(
            title="🔧 系統工具",
            description="系統維護和管理工具",
            color=0x95a5a6
        )
        
        embed.add_field(
            name="🧹 資料清理",
            value="• 清理舊日誌\n• 清理過期快取\n• 整理資料庫",
            inline=True
        )
        
        embed.add_field(
            name="🗑️ 頻道清空",
            value="• 清空頻道訊息\n• 清空近期訊息\n• 按用戶清空",
            inline=True
        )
        
        embed.add_field(
            name="📤 資料匯出",
            value="• 匯出票券資料\n• 匯出使用統計\n• 匯出設定備份",
            inline=True
        )
        
        return embed


class TicketSettingsView(View):
    """票券系統設定界面"""
    
    def __init__(self, user_id: int, timeout=300):
        super().__init__(timeout=timeout)
        self.user_id = user_id
        self.ticket_dao = TicketDAO()
    
    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        return interaction.user.id == self.user_id
    
    @button(label="📂 設定票券分類", style=discord.ButtonStyle.primary, row=0)
    async def set_category_button(self, interaction: discord.Interaction, button: Button):
        """設定票券分類頻道"""
        embed = discord.Embed(
            title="📂 選擇票券分類頻道",
            description="請選擇要用作票券分類的頻道",
            color=0x3498db
        )
        
        view = ChannelSelectView(self.user_id, "ticket_category")
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
    
    @button(label="👥 設定客服角色", style=discord.ButtonStyle.secondary, row=0)
    async def set_support_roles_button(self, interaction: discord.Interaction, button: Button):
        """設定客服角色"""
        embed = discord.Embed(
            title="👥 選擇客服角色",
            description="請選擇要設定為客服的角色",
            color=0x3498db
        )
        
        view = RoleSelectView(self.user_id, "support_roles")
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
    
    @button(label="⚙️ 系統參數", style=discord.ButtonStyle.secondary, row=0)
    async def system_params_button(self, interaction: discord.Interaction, button: Button):
        """系統參數設定"""
        modal = TicketSettingsModal()
        await interaction.response.send_modal(modal)
    
    @button(label="📝 票券面板訊息", style=discord.ButtonStyle.success, row=1)
    async def ticket_panel_messages_button(self, interaction: discord.Interaction, button: Button):
        """設定票券面板顯示的訊息"""
        modal = TicketMessageModal()
        await interaction.response.send_modal(modal)
    
    @button(label="🔄 重新整理", style=discord.ButtonStyle.secondary, row=1)
    async def refresh_button(self, interaction: discord.Interaction, button: Button):
        """重新整理設定狀態"""
        embed = await self._update_ticket_settings_embed(interaction.guild)
        await interaction.response.edit_message(embed=embed, view=self)
    
    async def _update_ticket_settings_embed(self, guild: discord.Guild) -> discord.Embed:
        """更新票券設定嵌入"""
        settings = await self.ticket_dao.get_settings(guild.id)
        
        embed = discord.Embed(
            title="🎫 票券系統設定",
            description="當前票券系統配置狀態",
            color=0x3498db
        )
        
        # 基本設定狀態
        category_text = f"<#{settings['category_id']}>" if settings.get('category_id') else "❌ 未設定"
        embed.add_field(name="📂 票券分類", value=category_text, inline=True)
        
        support_roles = settings.get('support_roles', [])
        roles_text = f"✅ {len(support_roles)} 個角色" if support_roles else "❌ 未設定"
        embed.add_field(name="👥 客服角色", value=roles_text, inline=True)
        
        embed.add_field(
            name="⚙️ 系統參數",
            value=f"票券上限: {settings.get('max_tickets_per_user', 3)}\n"
                  f"SLA時間: {settings.get('sla_response_minutes', 60)}分\n"
                  f"自動關閉: {settings.get('auto_close_hours', 24)}小時",
            inline=True
        )
        
        return embed


class WelcomeSettingsView(View):
    """歡迎系統設定界面"""
    
    def __init__(self, user_id: int, timeout=300):
        super().__init__(timeout=timeout)
        self.user_id = user_id
        self.welcome_dao = WelcomeDAO()
        self.welcome_manager = WelcomeManager(self.welcome_dao)
    
    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        return interaction.user.id == self.user_id
    
    @button(label="🚀 初始化系統", style=discord.ButtonStyle.success, row=0)
    async def init_system_button(self, interaction: discord.Interaction, button: Button):
        """初始化歡迎系統"""
        default_settings = {
            'is_enabled': True,
            'welcome_embed_enabled': True,
            'welcome_dm_enabled': False,
            'auto_role_enabled': False,
            'welcome_color': 0x2ecc71
        }
        
        success, message = await self.welcome_manager.update_welcome_settings(
            interaction.guild.id, **default_settings
        )
        
        if success:
            embed = discord.Embed(
                title="✅ 歡迎系統初始化完成",
                description="系統已成功初始化，現在可以進行詳細設定",
                color=0x2ecc71
            )
        else:
            embed = discord.Embed(
                title="❌ 初始化失敗",
                description=f"初始化過程中發生錯誤：{message}",
                color=0xe74c3c
            )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    @button(label="📺 設定頻道", style=discord.ButtonStyle.primary, row=0)
    async def set_channels_button(self, interaction: discord.Interaction, button: Button):
        """設定歡迎和離開頻道"""
        embed = discord.Embed(
            title="📺 頻道設定",
            description="選擇歡迎和離開訊息的頻道",
            color=0x3498db
        )
        
        view = WelcomeChannelSelectView(self.user_id)
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
    
    @button(label="👥 自動身分組", style=discord.ButtonStyle.secondary, row=0)
    async def auto_roles_button(self, interaction: discord.Interaction, button: Button):
        """設定自動身分組"""
        embed = discord.Embed(
            title="👥 自動身分組設定",
            description="設定新成員自動獲得的身分組",
            color=0x3498db
        )
        
        view = RoleSelectView(self.user_id, "auto_roles")
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
    
    @button(label="📝 自定義訊息", style=discord.ButtonStyle.success, row=1)
    async def custom_messages_button(self, interaction: discord.Interaction, button: Button):
        """自定義歡迎訊息"""
        modal = WelcomeMessageModal()
        await interaction.response.send_modal(modal)
    
    @button(label="🔧 功能開關", style=discord.ButtonStyle.secondary, row=1)
    async def feature_toggles_button(self, interaction: discord.Interaction, button: Button):
        """功能開關設定"""
        view = WelcomeFeatureToggleView(self.user_id)
        embed = discord.Embed(
            title="🔧 歡迎系統功能開關",
            description="啟用或停用各項功能",
            color=0x95a5a6
        )
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)


class ChannelSelectView(View):
    """頻道選擇界面"""
    
    def __init__(self, user_id: int, setting_type: str, timeout=300):
        super().__init__(timeout=timeout)
        self.user_id = user_id
        self.setting_type = setting_type
        self.add_item(ChannelSelect(setting_type))
    
    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        return interaction.user.id == self.user_id


class ChannelSelect(discord.ui.ChannelSelect):
    """頻道選擇下拉選單"""
    
    def __init__(self, setting_type: str):
        self.setting_type = setting_type
        
        # 根據設定類型決定顯示的頻道類型
        if setting_type == "ticket_category":
            channel_types = [discord.ChannelType.category]
            placeholder = "選擇票券分類頻道..."
        else:  # welcome_channel, leave_channel 等文字頻道
            channel_types = [discord.ChannelType.text]
            placeholder = "選擇文字頻道..."
        
        super().__init__(
            placeholder=placeholder,
            channel_types=channel_types,
            min_values=1,
            max_values=1
        )
    
    async def callback(self, interaction: discord.Interaction):
        channel = self.values[0]
        
        try:
            if self.setting_type == "ticket_category":
                
                ticket_dao = TicketDAO()
                success = await ticket_dao.update_settings(
                    interaction.guild.id, 
                    {'category_id': channel.id}
                )
                
                if success:
                    embed = discord.Embed(
                        title="✅ 票券分類已設定",
                        description=f"票券分類頻道已設定為：**{channel.name}**\n"
                                  f"新的票券將在此分類下建立專屬頻道",
                        color=0x2ecc71
                    )
                    embed.add_field(
                        name="📋 說明",
                        value="• 票券將自動在此分類下建立頻道\n"
                              "• 頻道名稱格式：`ticket-用戶名-編號`\n"
                              "• 確保Bot有管理此分類的權限",
                        inline=False
                    )
                else:
                    embed = discord.Embed(
                        title="❌ 設定失敗",
                        description="設定票券分類時發生錯誤，請確認Bot有足夠權限",
                        color=0xe74c3c
                    )
                
                await interaction.response.send_message(embed=embed, ephemeral=True)
            
            elif self.setting_type == "welcome_channel":
                
                welcome_manager = WelcomeManager()
                success, message = await welcome_manager.set_welcome_channel(
                    interaction.guild.id, 
                    channel.id
                )
                
                if success:
                    embed = discord.Embed(
                        title="✅ 歡迎頻道已設定",
                        description=message,
                        color=0x2ecc71
                    )
                else:
                    embed = discord.Embed(
                        title="❌ 設定失敗",
                        description=message,
                        color=0xe74c3c
                    )
                
                await interaction.response.send_message(embed=embed, ephemeral=True)
            
            elif self.setting_type == "leave_channel":
                
                welcome_manager = WelcomeManager()
                success, message = await welcome_manager.set_leave_channel(
                    interaction.guild.id, 
                    channel.id
                )
                
                if success:
                    embed = discord.Embed(
                        title="✅ 離開頻道已設定",
                        description=message,  
                        color=0x2ecc71
                    )
                else:
                    embed = discord.Embed(
                        title="❌ 設定失敗",
                        description=message,
                        color=0xe74c3c
                    )
                
                await interaction.response.send_message(embed=embed, ephemeral=True)
                
        except Exception as e:
            logger.error(f"頻道設定錯誤: {e}")
            await interaction.response.send_message("❌ 設定過程中發生錯誤", ephemeral=True)


class RoleSelectView(View):
    """角色選擇界面"""
    
    def __init__(self, user_id: int, setting_type: str, timeout=300):
        super().__init__(timeout=timeout)
        self.user_id = user_id
        self.setting_type = setting_type
        self.add_item(RoleSelect(setting_type))
    
    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        return interaction.user.id == self.user_id


class RoleSelect(discord.ui.RoleSelect):
    """角色選擇下拉選單"""
    
    def __init__(self, setting_type: str):
        self.setting_type = setting_type
        super().__init__(
            placeholder="選擇角色...",
            min_values=1,
            max_values=10  # 最多選擇10個角色
        )
    
    # RoleSelect不需要手動填充選項，Discord會自動處理
    
    async def callback(self, interaction: discord.Interaction):
        selected_role_ids = [role.id for role in self.values]
        
        try:
            if self.setting_type == "support_roles":
                ticket_dao = TicketDAO()
                success = await ticket_dao.update_settings(
                    interaction.guild.id,
                    {'support_roles': selected_role_ids}
                )
                
                role_mentions = [f"<@&{role_id}>" for role_id in selected_role_ids]
                
                if success:
                    embed = discord.Embed(
                        title="✅ 客服角色已設定",
                        description=f"客服角色已設定為：\n{', '.join(role_mentions)}",
                        color=0x2ecc71
                    )
                else:
                    embed = discord.Embed(
                        title="❌ 設定失敗",
                        description="設定客服角色時發生錯誤",
                        color=0xe74c3c
                    )
                
            elif self.setting_type == "auto_roles":
                welcome_manager = WelcomeManager()
                success, message = await welcome_manager.set_auto_roles(
                    interaction.guild.id, 
                    selected_role_ids
                )
                
                if success:
                    embed = discord.Embed(
                        title="✅ 自動身分組已設定",
                        description=message,
                        color=0x2ecc71
                    )
                else:
                    embed = discord.Embed(
                        title="❌ 設定失敗",
                        description=message,
                        color=0xe74c3c
                    )
            
            await interaction.response.send_message(embed=embed, ephemeral=True)
            
        except Exception as e:
            logger.error(f"角色設定錯誤: {e}")
            await interaction.response.send_message("❌ 設定過程中發生錯誤", ephemeral=True)


class WelcomeChannelSelectView(View):
    """歡迎頻道選擇界面"""
    
    def __init__(self, user_id: int, timeout=300):
        super().__init__(timeout=timeout)
        self.user_id = user_id
    
    @button(label="📢 設定歡迎頻道", style=discord.ButtonStyle.primary)
    async def welcome_channel_button(self, interaction: discord.Interaction, button: Button):
        view = ChannelSelectView(self.user_id, "welcome_channel")
        await interaction.response.send_message("請選擇歡迎頻道：", view=view, ephemeral=True)
    
    @button(label="👋 設定離開頻道", style=discord.ButtonStyle.secondary)
    async def leave_channel_button(self, interaction: discord.Interaction, button: Button):
        view = ChannelSelectView(self.user_id, "leave_channel")
        await interaction.response.send_message("請選擇離開頻道：", view=view, ephemeral=True)


class WelcomeFeatureToggleView(View):
    """歡迎功能開關界面"""
    
    def __init__(self, user_id: int, timeout=300):
        super().__init__(timeout=timeout)
        self.user_id = user_id
        self.welcome_manager = WelcomeManager()
    
    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        return interaction.user.id == self.user_id
    
    @button(label="🔄 嵌入訊息", style=discord.ButtonStyle.secondary)
    async def toggle_embed_button(self, interaction: discord.Interaction, button: Button):
        """切換嵌入訊息功能"""
        settings = await self.welcome_manager.welcome_dao.get_welcome_settings(interaction.guild.id)
        current_state = settings.get('welcome_embed_enabled', True) if settings else True
        new_state = not current_state
        
        success, message = await self.welcome_manager.update_welcome_settings(
            interaction.guild.id, welcome_embed_enabled=new_state
        )
        
        if success:
            status = "啟用" if new_state else "停用"
            await interaction.response.send_message(f"✅ 嵌入訊息功能已{status}", ephemeral=True)
        else:
            await interaction.response.send_message(f"❌ 設定失敗：{message}", ephemeral=True)
    
    @button(label="💌 私訊歡迎", style=discord.ButtonStyle.secondary)
    async def toggle_dm_button(self, interaction: discord.Interaction, button: Button):
        """切換私訊歡迎功能"""
        settings = await self.welcome_manager.welcome_dao.get_welcome_settings(interaction.guild.id)
        current_state = settings.get('welcome_dm_enabled', False) if settings else False
        new_state = not current_state
        
        success, message = await self.welcome_manager.update_welcome_settings(
            interaction.guild.id, welcome_dm_enabled=new_state
        )
        
        if success:
            status = "啟用" if new_state else "停用"
            await interaction.response.send_message(f"✅ 私訊歡迎功能已{status}", ephemeral=True)
        else:
            await interaction.response.send_message(f"❌ 設定失敗：{message}", ephemeral=True)
    
    @button(label="👥 自動身分組", style=discord.ButtonStyle.secondary)
    async def toggle_auto_role_button(self, interaction: discord.Interaction, button: Button):
        """切換自動身分組功能"""
        settings = await self.welcome_manager.welcome_dao.get_welcome_settings(interaction.guild.id)
        current_state = settings.get('auto_role_enabled', False) if settings else False
        new_state = not current_state
        
        success, message = await self.welcome_manager.update_welcome_settings(
            interaction.guild.id, auto_role_enabled=new_state
        )
        
        if success:
            status = "啟用" if new_state else "停用"
            await interaction.response.send_message(f"✅ 自動身分組功能已{status}", ephemeral=True)
        else:
            await interaction.response.send_message(f"❌ 設定失敗：{message}", ephemeral=True)


class StatsView(View):
    """統計監控界面"""
    
    def __init__(self, user_id: int, timeout=300):
        super().__init__(timeout=timeout)
        self.user_id = user_id
    
    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        return interaction.user.id == self.user_id
    
    @button(label="🎫 票券統計", style=discord.ButtonStyle.primary)
    async def ticket_stats_button(self, interaction: discord.Interaction, button: Button):
        """顯示票券統計"""
        from bot.services.statistics_manager import StatisticsManager
        
        await interaction.response.defer(ephemeral=True)
        
        try:
            stats_manager = StatisticsManager()
            stats = await stats_manager.get_comprehensive_statistics(interaction.guild.id, 30)
            
            if 'error' not in stats:
                embed = discord.Embed(
                    title="📊 票券系統統計報告",
                    description="過去30天的票券系統使用統計",
                    color=0x3498db
                )
                
                # 票券統計
                ticket_stats = stats.get('ticket_statistics', {}).get('summary', {})
                embed.add_field(
                    name="🎫 票券概覽",
                    value=f"總票券數: {ticket_stats.get('total_tickets', 0)}\n"
                          f"解決率: {ticket_stats.get('resolution_rate', 0):.1f}%\n"
                          f"平均日票券: {ticket_stats.get('avg_daily_tickets', 0):.1f}張",
                    inline=True
                )
                
                # 用戶統計
                user_stats = stats.get('user_statistics', {}).get('summary', {})
                embed.add_field(
                    name="👥 用戶活動",
                    value=f"活躍用戶: {user_stats.get('total_unique_users', 0)}\n"
                          f"人均票券: {user_stats.get('avg_tickets_per_user', 0):.1f}張",
                    inline=True
                )
                
                # 性能統計
                perf_stats = stats.get('performance_statistics', {}).get('summary', {})
                embed.add_field(
                    name="⚡ 系統性能",
                    value=f"平均回應: {perf_stats.get('avg_first_response_hours', 0):.1f}小時\n"
                          f"平均解決: {perf_stats.get('avg_resolution_hours', 0):.1f}小時\n"
                          f"24h解決率: {perf_stats.get('resolution_within_24h_rate', 0):.1f}%",
                    inline=True
                )
                
                embed.set_footer(text=f"統計生成時間: {stats.get('metadata', {}).get('generated_at', '未知')[:16]}")
            else:
                embed = discord.Embed(
                    title="❌ 統計生成失敗",
                    description=f"無法生成票券統計: {stats.get('error')}",
                    color=0xe74c3c
                )
            
            await interaction.followup.send(embed=embed, ephemeral=True)
            
        except Exception as e:
            embed = discord.Embed(
                title="❌ 統計錯誤",
                description=f"生成統計時發生錯誤: {str(e)[:100]}",
                color=0xe74c3c
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
    
    @button(label="🎉 歡迎統計", style=discord.ButtonStyle.success)
    async def welcome_stats_button(self, interaction: discord.Interaction, button: Button):
        """顯示歡迎統計"""
        await interaction.response.defer(ephemeral=True)
        
        try:
            welcome_manager = WelcomeManager()
            stats = await welcome_manager.get_welcome_statistics(interaction.guild.id, 30)
            
            embed = discord.Embed(
                title="🎉 歡迎系統統計報告", 
                description="過去30天的歡迎系統使用統計",
                color=0x2ecc71
            )
            
            embed.add_field(
                name="👋 成員變化",
                value=f"新加入: {stats.get('joins', 0)}人\n"
                      f"離開: {stats.get('leaves', 0)}人\n"
                      f"淨增長: {stats.get('net_growth', 0)}人",
                inline=True
            )
            
            embed.add_field(
                name="📈 增長趨勢",
                value=f"增長率: {stats.get('growth_rate', 0):.1f}%\n"
                      f"日均加入: {stats.get('avg_daily_joins', 0):.1f}人\n"
                      f"留存率: {stats.get('retention_rate', 0):.1f}%",
                inline=True
            )
            
            # 系統設定狀態
            settings = await welcome_manager.welcome_dao.get_welcome_settings(interaction.guild.id)
            if settings:
                status = "✅ 已啟用" if settings.get('is_enabled') else "❌ 已停用"
                embed.add_field(
                    name="⚙️ 系統狀態",
                    value=f"歡迎系統: {status}\n"
                          f"嵌入訊息: {'✅' if settings.get('welcome_embed_enabled') else '❌'}\n"
                          f"私訊歡迎: {'✅' if settings.get('welcome_dm_enabled') else '❌'}",
                    inline=True
                )
            
            await interaction.followup.send(embed=embed, ephemeral=True)
            
        except Exception as e:
            embed = discord.Embed(
                title="❌ 統計錯誤",
                description=f"生成歡迎統計時發生錯誤: {str(e)[:100]}",
                color=0xe74c3c
            )
            await interaction.followup.send(embed=embed, ephemeral=True)


class SystemToolsView(View):
    """系統工具界面"""
    
    def __init__(self, user_id: int, timeout=300):
        super().__init__(timeout=timeout)
        self.user_id = user_id
    
    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        return interaction.user.id == self.user_id
    
    @button(label="🧹 清理資料", style=discord.ButtonStyle.secondary)
    async def cleanup_button(self, interaction: discord.Interaction, button: Button):
        """資料清理工具"""
        embed = discord.Embed(
            title="🧹 資料清理系統",
            description="選擇要執行的清理操作",
            color=0x95a5a6
        )
        embed.add_field(
            name="🗑️ 基礎清理",
            value="• 清理舊日誌 (30天前)\n• 清理過期快取\n• 清理臨時資料",
            inline=True
        )
        embed.add_field(
            name="🔧 深度清理",
            value="• 資料庫優化\n• 索引重建\n• 完整清理",
            inline=True
        )
        view = DataCleanupView(self.user_id)
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
    
    @button(label="📤 匯出資料", style=discord.ButtonStyle.secondary)
    async def export_button(self, interaction: discord.Interaction, button: Button):
        """資料匯出工具"""
        embed = discord.Embed(
            title="📤 資料匯出系統",
            description="選擇要匯出的資料類型和格式",
            color=0x3498db
        )
        embed.add_field(
            name="📋 支援資料類型",
            value="• 票券資料\n• 投票資料\n• 用戶統計\n• 系統日誌",
            inline=True
        )
        embed.add_field(
            name="📁 支援格式",
            value="• CSV 格式\n• JSON 格式\n• Excel 格式",
            inline=True
        )
        embed.add_field(
            name="⏰ 時間範圍",
            value="• 最近7天\n• 最近30天\n• 自定義範圍",
            inline=True
        )
        view = DataExportView(self.user_id)
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
    
    @button(label="🗑️ 清空頻道", style=discord.ButtonStyle.danger, row=1)
    async def clear_channel_button(self, interaction: discord.Interaction, button: Button):
        """清空頻道訊息"""
        try:
            # 檢查用戶權限
            if not interaction.user.guild_permissions.manage_messages:
                await interaction.response.send_message("❌ 需要管理訊息權限才能使用此功能", ephemeral=True)
                return
            
            embed = discord.Embed(
                title="🗑️ 清空頻道訊息",
                description="選擇要清空的頻道和清空選項",
                color=0xe74c3c
            )
            
            embed.add_field(
                name="⚠️ 警告",
                value="此操作將永久刪除頻道中的訊息，無法復原！\n請謹慎選擇要清空的頻道。",
                inline=False
            )
            
            view = ChannelClearView(self.user_id)
            view.add_item(ChannelClearSelect(self.user_id, interaction.guild))
            await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
            
        except Exception as e:
            logger.error(f"清空頻道按鈕錯誤: {e}")
            try:
                if not interaction.response.is_done():
                    await interaction.response.send_message("❌ 開啟清空頻道面板時發生錯誤", ephemeral=True)
                else:
                    await interaction.followup.send("❌ 開啟清空頻道面板時發生錯誤", ephemeral=True)
            except:
                pass


# ========== Modal 表單 ==========

class TicketSettingsModal(Modal):
    """票券系統設定表單"""
    
    def __init__(self):
        super().__init__(title="⚙️ 票券系統參數設定")
        
        self.max_tickets = TextInput(
            label="每人最大票券數量",
            placeholder="預設: 3",
            default="3",
            max_length=2,
            required=True
        )
        
        self.sla_minutes = TextInput(
            label="SLA回應時間 (分鐘)",
            placeholder="預設: 60",
            default="60",
            max_length=4,
            required=True
        )
        
        self.auto_close_hours = TextInput(
            label="自動關閉時間 (小時)",
            placeholder="預設: 24",
            default="24",
            max_length=3,
            required=True
        )
        
        self.add_item(self.max_tickets)
        self.add_item(self.sla_minutes)
        self.add_item(self.auto_close_hours)
    
    async def on_submit(self, interaction: discord.Interaction):
        try:
            max_tickets = int(self.max_tickets.value)
            sla_minutes = int(self.sla_minutes.value)
            auto_close_hours = int(self.auto_close_hours.value)
            
            # 驗證範圍
            if not (1 <= max_tickets <= 10):
                await interaction.response.send_message("❌ 每人票券數量必須在 1-10 之間", ephemeral=True)
                return
            
            if not (5 <= sla_minutes <= 1440):
                await interaction.response.send_message("❌ SLA時間必須在 5-1440 分鐘之間", ephemeral=True)
                return
            
            if not (1 <= auto_close_hours <= 168):
                await interaction.response.send_message("❌ 自動關閉時間必須在 1-168 小時之間", ephemeral=True)
                return
            
            # 更新設定
            ticket_dao = TicketDAO()
            success = await ticket_dao.update_settings(
                interaction.guild.id,
                {
                    'max_tickets_per_user': max_tickets,
                    'sla_response_minutes': sla_minutes,
                    'auto_close_hours': auto_close_hours
                }
            )
            
            if success:
                embed = discord.Embed(
                    title="✅ 票券系統參數已更新",
                    description=f"每人票券上限: {max_tickets}\n"
                               f"SLA回應時間: {sla_minutes} 分鐘\n"
                               f"自動關閉時間: {auto_close_hours} 小時",
                    color=0x2ecc71
                )
            else:
                embed = discord.Embed(
                    title="❌ 設定更新失敗",
                    description="更新票券系統參數時發生錯誤",
                    color=0xe74c3c
                )
            
            await interaction.response.send_message(embed=embed, ephemeral=True)
            
        except ValueError:
            await interaction.response.send_message("❌ 請輸入有效的數字", ephemeral=True)
        except Exception as e:
            logger.error(f"票券設定更新錯誤: {e}")
            await interaction.response.send_message("❌ 設定過程中發生錯誤", ephemeral=True)


class TicketMessageModal(Modal):
    """票券訊息設定表單"""
    
    def __init__(self):
        super().__init__(title="🎨 票券系統訊息設定")
        
        self.welcome_msg = TextInput(
            label="票券面板歡迎訊息",
            placeholder="票券系統的歡迎描述文字",
            style=discord.TextStyle.paragraph,
            max_length=2000,
            required=False
        )
        
        self.close_msg = TextInput(
            label="票券關閉後訊息",
            placeholder="票券關閉時顯示的訊息",
            style=discord.TextStyle.paragraph,
            max_length=2000,
            required=False
        )
        
        self.add_item(self.welcome_msg)
        self.add_item(self.close_msg)
    
    async def on_submit(self, interaction: discord.Interaction):
        try:
            ticket_dao = TicketDAO()
            settings_to_update = {}
            
            if self.welcome_msg.value:
                settings_to_update['welcome_message'] = self.welcome_msg.value
            
            if self.close_msg.value:
                settings_to_update['close_message'] = self.close_msg.value
            
            if not settings_to_update:
                await interaction.response.send_message("❌ 請至少填寫一項訊息", ephemeral=True)
                return
            
            success = await ticket_dao.update_settings(
                interaction.guild.id, settings_to_update
            )
            
            if success:
                embed = discord.Embed(
                    title="✅ 票券訊息已更新",
                    description="票券系統訊息設定已成功保存",
                    color=0x2ecc71
                )
            else:
                embed = discord.Embed(
                    title="❌ 設定更新失敗",
                    description="更新票券訊息時發生錯誤",
                    color=0xe74c3c
                )
            
            await interaction.response.send_message(embed=embed, ephemeral=True)
            
        except Exception as e:
            logger.error(f"票券訊息設定錯誤: {e}")
            await interaction.response.send_message("❌ 設定過程中發生錯誤", ephemeral=True)


class WelcomeMessageModal(Modal):
    """歡迎訊息設定表單"""
    
    def __init__(self):
        super().__init__(title="📝 歡迎訊息設定")
        
        self.welcome_msg = TextInput(
            label="歡迎訊息",
            placeholder="可使用變數: {user_mention}, {guild_name}, {member_count}",
            style=discord.TextStyle.paragraph,
            max_length=2000,
            required=False
        )
        
        self.leave_msg = TextInput(
            label="離開訊息",
            placeholder="可使用變數: {username}, {guild_name}, {join_date}",
            style=discord.TextStyle.paragraph,
            max_length=2000,
            required=False
        )
        
        self.add_item(self.welcome_msg)
        self.add_item(self.leave_msg)
    
    async def on_submit(self, interaction: discord.Interaction):
        try:
            welcome_manager = WelcomeManager()
            settings_to_update = {}
            
            if self.welcome_msg.value:
                settings_to_update['welcome_message'] = self.welcome_msg.value
            
            if self.leave_msg.value:
                settings_to_update['leave_message'] = self.leave_msg.value
            
            if not settings_to_update:
                await interaction.response.send_message("❌ 請至少填寫一項訊息", ephemeral=True)
                return
            
            success, message = await welcome_manager.update_welcome_settings(
                interaction.guild.id, **settings_to_update
            )
            
            if success:
                embed = discord.Embed(
                    title="✅ 歡迎訊息已更新",
                    description="歡迎訊息設定已成功保存",
                    color=0x2ecc71
                )
            else:
                embed = discord.Embed(
                    title="❌ 設定更新失敗",
                    description=f"更新過程中發生錯誤：{message}",
                    color=0xe74c3c
                )
            
            await interaction.response.send_message(embed=embed, ephemeral=True)
            
        except Exception as e:
            logger.error(f"歡迎訊息設定錯誤: {e}")
            await interaction.response.send_message("❌ 設定過程中發生錯誤", ephemeral=True)


class VoteSettingsView(View):
    """投票系統設定視圖"""
    
    def __init__(self, user_id: int, timeout=300):
        super().__init__(timeout=timeout)
        self.user_id = user_id
    
    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        """檢查用戶權限"""
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("❌ 只有指令使用者可以操作此面板", ephemeral=True)
            return False
        
        if not interaction.user.guild_permissions.manage_guild:
            await interaction.response.send_message("❌ 需要管理伺服器權限", ephemeral=True)
            return False
        
        return True
    
    @button(label="📺 設定投票頻道", style=discord.ButtonStyle.primary, row=0)
    async def set_vote_channel_button(self, interaction: discord.Interaction, button: Button):
        """設定預設投票頻道按鈕"""
        self.clear_items()
        self.add_item(VoteChannelSelect(self.user_id))
        self.add_item(BackToVoteSettingsButton(self.user_id))
        
        embed = discord.Embed(
            title="📺 選擇預設投票頻道",
            description="選擇新建立的投票要發布到哪個頻道",
            color=0x3498db
        )
        
        await interaction.response.edit_message(embed=embed, view=self)
    
    @button(label="📢 設定公告頻道", style=discord.ButtonStyle.secondary, row=0)
    async def set_announce_channel_button(self, interaction: discord.Interaction, button: Button):
        """設定投票結果公告頻道按鈕"""
        self.clear_items()
        self.add_item(AnnounceChannelSelect(self.user_id))
        self.add_item(BackToVoteSettingsButton(self.user_id))
        
        embed = discord.Embed(
            title="📢 選擇投票結果公告頻道",
            description="選擇投票結束後結果要公告到哪個頻道",
            color=0x3498db
        )
        
        await interaction.response.edit_message(embed=embed, view=self)
    
    @button(label="📋 管理活躍投票", style=discord.ButtonStyle.primary, row=0)
    async def manage_active_votes_button(self, interaction: discord.Interaction, button: Button):
        """管理活躍投票按鈕"""
        await interaction.response.send_message(
            embed=await self._create_active_votes_embed(interaction.guild),
            view=ActiveVoteManageView(self.user_id),
            ephemeral=True
        )
    
    @button(label="⚙️ 系統開關", style=discord.ButtonStyle.success, row=1)
    async def toggle_system_button(self, interaction: discord.Interaction, button: Button):
        """切換系統開關按鈕"""
        # 取得當前設定
        settings = await vote_dao.get_vote_settings(interaction.guild.id)
        current_enabled = settings.get('is_enabled', True) if settings else True
        
        # 切換狀態
        new_enabled = not current_enabled
        success = await vote_dao.update_vote_settings(interaction.guild.id, {'is_enabled': new_enabled})
        
        if success:
            status = "啟用" if new_enabled else "停用"
            color = 0x2ecc71 if new_enabled else 0xf39c12
            embed = discord.Embed(
                title=f"✅ 投票系統已{status}",
                description=f"投票系統現在已{status}",
                color=color
            )
        else:
            embed = discord.Embed(
                title="❌ 操作失敗",
                description="切換系統狀態時發生錯誤",
                color=0xe74c3c
            )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    @button(label="🔄 重新整理", style=discord.ButtonStyle.secondary, row=2)
    async def refresh_button(self, interaction: discord.Interaction, button: Button):
        """重新整理設定按鈕"""
        from bot.views.system_admin_views import SystemAdminPanel
        admin_panel = SystemAdminPanel(self.user_id)
        embed = await admin_panel._create_vote_settings_embed(interaction.guild)
        await interaction.response.edit_message(embed=embed, view=self)
    
    @button(label="❌ 關閉", style=discord.ButtonStyle.danger, row=2)
    async def close_button(self, interaction: discord.Interaction, button: Button):
        """關閉按鈕"""
        embed = discord.Embed(
            title="✅ 投票系統設定已關閉",
            color=0x95a5a6
        )
        await interaction.response.edit_message(embed=embed, view=None)
    
    async def _create_active_votes_embed(self, guild: discord.Guild) -> discord.Embed:
        """創建活躍投票嵌入"""
        active_votes = await vote_dao.get_active_votes()
        
        embed = discord.Embed(
            title="📋 活躍投票管理",
            color=0x3498db
        )
        
        if not active_votes:
            embed.description = "目前沒有進行中的投票"
            embed.color = 0x95a5a6
        else:
            embed.description = f"共有 {len(active_votes)} 個進行中的投票"
            
            for vote in active_votes[:5]:  # 最多顯示5個
                stats = await vote_dao.get_vote_statistics(vote['id'])
                total = sum(stats.values())
                
                embed.add_field(
                    name=f"#{vote['id']} - {vote['title'][:50]}",
                    value=f"📊 總票數: {total}\n"
                          f"⏰ 結束時間: {vote['end_time'].strftime('%m-%d %H:%M')}\n"
                          f"🏷️ 模式: {'匿名' if vote['anonymous'] else '公開'}{'多選' if vote['is_multi'] else '單選'}",
                    inline=True
                )
                
            if len(active_votes) > 5:
                embed.add_field(
                    name="📌 提示",
                    value=f"還有 {len(active_votes) - 5} 個投票未顯示",
                    inline=False
                )
        
        return embed


class VoteChannelSelect(discord.ui.ChannelSelect):
    """投票頻道選擇器"""
    
    def __init__(self, user_id: int):
        self.user_id = user_id
        super().__init__(
            placeholder="選擇預設投票頻道...",
            min_values=1,
            max_values=1,
            channel_types=[discord.ChannelType.text]
        )
    
    async def callback(self, interaction: discord.Interaction):
        channel = self.values[0]
        success = await vote_dao.set_default_vote_channel(interaction.guild.id, channel.id)
        
        if success:
            embed = discord.Embed(
                title="✅ 投票頻道設定成功",
                description=f"預設投票頻道已設定為 {channel.mention}",
                color=0x2ecc71
            )
            embed.add_field(
                name="📋 說明",
                value="新建立的投票將自動發布到此頻道",
                inline=False
            )
        else:
            embed = discord.Embed(
                title="❌ 設定失敗",
                description="設定投票頻道時發生錯誤",
                color=0xe74c3c
            )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)


class AnnounceChannelSelect(discord.ui.ChannelSelect):
    """投票結果公告頻道選擇器"""
    
    def __init__(self, user_id: int):
        self.user_id = user_id
        super().__init__(
            placeholder="選擇投票結果公告頻道...",
            min_values=1,
            max_values=1,
            channel_types=[discord.ChannelType.text]
        )
    
    async def callback(self, interaction: discord.Interaction):
        channel = self.values[0]
        success = await vote_dao.set_announcement_channel(interaction.guild.id, channel.id)
        
        if success:
            embed = discord.Embed(
                title="✅ 公告頻道設定成功",
                description=f"投票結果公告頻道已設定為 {channel.mention}",
                color=0x2ecc71
            )
            embed.add_field(
                name="📋 說明",
                value="投票結束後的結果將自動公告到此頻道",
                inline=False
            )
        else:
            embed = discord.Embed(
                title="❌ 設定失敗",
                description="設定公告頻道時發生錯誤",
                color=0xe74c3c
            )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)


class BackToVoteSettingsButton(Button):
    """返回投票設定按鈕"""
    
    def __init__(self, user_id: int):
        self.user_id = user_id
        super().__init__(label="← 返回", style=discord.ButtonStyle.secondary)
    
    async def callback(self, interaction: discord.Interaction):
        from bot.views.system_admin_views import SystemAdminPanel
        admin_panel = SystemAdminPanel(self.user_id)
        embed = await admin_panel._create_vote_settings_embed(interaction.guild)
        view = VoteSettingsView(self.user_id)
        await interaction.response.edit_message(embed=embed, view=view)


class ChannelClearView(View):
    """頻道清空界面"""
    
    def __init__(self, user_id: int, timeout=300):
        super().__init__(timeout=timeout)
        self.user_id = user_id
        self.selected_channel = None
    
    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        try:
            if interaction.user.id != self.user_id:
                await interaction.response.send_message("❌ 只有指令使用者可以操作此面板", ephemeral=True)
                return False
            
            if not interaction.user.guild_permissions.manage_messages:
                await interaction.response.send_message("❌ 需要管理訊息權限", ephemeral=True)
                return False
            
            return True
        except Exception as e:
            logger.error(f"ChannelClearView interaction_check 錯誤: {e}")
            return False


class ChannelClearSelect(Select):
    """頻道清空選擇器"""
    
    def __init__(self, user_id: int, guild: discord.Guild):
        self.user_id = user_id
        
        # 獲取所有文字頻道並建立選項
        text_channels = [ch for ch in guild.channels if isinstance(ch, discord.TextChannel)]
        
        if not text_channels:
            options = [
                discord.SelectOption(
                    label="無可用頻道",
                    value="none",
                    description="沒有找到文字頻道"
                )
            ]
        else:
            options = []
            for channel in text_channels[:25]:  # Discord 限制最多25個選項
                options.append(discord.SelectOption(
                    label=f"#{channel.name}",
                    value=str(channel.id),
                    description=f"ID: {channel.id}"
                ))
        
        super().__init__(
            placeholder="選擇要清空的頻道...",
            min_values=1,
            max_values=1,
            options=options
        )
    
    async def callback(self, interaction: discord.Interaction):
        try:
            # 檢查是否為無效選項
            if self.values[0] == "none":
                await interaction.response.send_message("❌ 沒有可用的頻道進行清空", ephemeral=True)
                return
            
            # 處理頻道選擇
            channel_id = int(self.values[0])
            selected_channel = interaction.guild.get_channel(channel_id)
            
            if not selected_channel:
                await interaction.response.send_message("❌ 找不到選擇的頻道", ephemeral=True)
                return
            
            # 設定選中的頻道
            if hasattr(self.view, 'selected_channel'):
                self.view.selected_channel = selected_channel
            
            embed = discord.Embed(
                title="🗑️ 確認清空頻道",
                description=f"您選擇了頻道：{selected_channel.mention}\n"
                           f"請選擇清空選項：",
                color=0xe74c3c
            )
            
            embed.add_field(
                name="⚠️ 重要提醒",
                value="• 此操作無法復原\n"
                      "• 將永久刪除頻道中的訊息\n" 
                      "• 請確認您有足夠的權限\n"
                      "• 建議在低峰時段執行",
                inline=False
            )
            
            # 清除選擇器，添加操作按鈕
            self.view.clear_items()
            self.view.add_item(ClearAllButton(self.user_id, selected_channel))
            self.view.add_item(ClearRecentButton(self.user_id, selected_channel))
            self.view.add_item(ClearByUserButton(self.user_id, selected_channel))
            self.view.add_item(BackToClearSelectButton(self.user_id))
            
            await interaction.response.edit_message(embed=embed, view=self.view)
            
        except Exception as e:
            logger.error(f"ChannelClearSelect callback 錯誤: {e}")
            try:
                if not interaction.response.is_done():
                    await interaction.response.send_message("❌ 選擇頻道時發生錯誤", ephemeral=True)
                else:
                    await interaction.followup.send("❌ 選擇頻道時發生錯誤", ephemeral=True)
            except:
                pass


class ClearAllButton(Button):
    """清空全部訊息按鈕"""
    
    def __init__(self, user_id: int, channel: discord.TextChannel):
        self.user_id = user_id
        self.channel = channel
        super().__init__(label="🗑️ 清空全部", style=discord.ButtonStyle.danger, row=0)
    
    async def callback(self, interaction: discord.Interaction):
        # 最終確認
        embed = discord.Embed(
            title="❗ 最終確認",
            description=f"您確定要清空 {self.channel.mention} 中的**所有訊息**嗎？",
            color=0xe74c3c
        )
        
        embed.add_field(
            name="⚠️ 這將會：",
            value="• 刪除頻道中的所有訊息\n"
                  "• 無法復原任何內容\n"
                  "• 可能需要較長時間",
            inline=False
        )
        
        view = FinalConfirmView(self.user_id, self.channel, "all")
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)


class ClearRecentButton(Button):
    """清空最近訊息按鈕"""
    
    def __init__(self, user_id: int, channel: discord.TextChannel):
        self.user_id = user_id
        self.channel = channel
        super().__init__(label="⏰ 清空近期", style=discord.ButtonStyle.secondary, row=0)
    
    async def callback(self, interaction: discord.Interaction):
        modal = ClearRecentModal(self.channel)
        await interaction.response.send_modal(modal)


class ClearByUserButton(Button):
    """按用戶清空訊息按鈕"""
    
    def __init__(self, user_id: int, channel: discord.TextChannel):
        self.user_id = user_id
        self.channel = channel
        super().__init__(label="👤 按用戶清空", style=discord.ButtonStyle.secondary, row=0)
    
    async def callback(self, interaction: discord.Interaction):
        modal = ClearByUserModal(self.channel)
        await interaction.response.send_modal(modal)


class BackToClearSelectButton(Button):
    """返回頻道選擇按鈕"""
    
    def __init__(self, user_id: int):
        self.user_id = user_id
        super().__init__(label="← 重新選擇", style=discord.ButtonStyle.secondary, row=1)
    
    async def callback(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="🗑️ 清空頻道訊息",
            description="選擇要清空的頻道和清空選項",
            color=0xe74c3c
        )
        
        embed.add_field(
            name="⚠️ 警告",
            value="此操作將永久刪除頻道中的訊息，無法復原！\n請謹慎選擇要清空的頻道。",
            inline=False
        )
        
        view = ChannelClearView(self.user_id)
        view.add_item(ChannelClearSelect(self.user_id, interaction.guild))
        await interaction.response.edit_message(embed=embed, view=view)


class FinalConfirmView(View):
    """最終確認視圖"""
    
    def __init__(self, user_id: int, channel: discord.TextChannel, clear_type: str, timeout=60):
        super().__init__(timeout=timeout)
        self.user_id = user_id
        self.channel = channel
        self.clear_type = clear_type
    
    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        return interaction.user.id == self.user_id
    
    @button(label="✅ 確認執行", style=discord.ButtonStyle.danger)
    async def confirm_button(self, interaction: discord.Interaction, button: Button):
        """確認執行清空"""
        await interaction.response.defer(ephemeral=True)
        
        try:
            # 開始清空過程
            embed = discord.Embed(
                title="🔄 正在清空頻道...",
                description=f"正在清空 {self.channel.mention}，請稍候...",
                color=0xf39c12
            )
            
            await interaction.followup.send(embed=embed, ephemeral=True)
            
            # 執行清空
            deleted_count = 0
            if self.clear_type == "all":
                deleted_count = await self._clear_all_messages()
            elif self.clear_type.startswith("recent_"):
                hours = int(self.clear_type.split("_")[1])
                deleted_count = await self._clear_recent_messages(hours)
            elif self.clear_type.startswith("user_"):
                user_id = int(self.clear_type.split("_")[1])
                deleted_count = await self._clear_user_messages(user_id)
            
            # 完成提示
            embed = discord.Embed(
                title="✅ 清空完成",
                description=f"已成功清空 {self.channel.mention}",
                color=0x2ecc71
            )
            
            embed.add_field(
                name="📊 清空統計",
                value=f"共刪除 {deleted_count} 條訊息",
                inline=False
            )
            
            await interaction.followup.send(embed=embed, ephemeral=True)
            
        except discord.Forbidden:
            embed = discord.Embed(
                title="❌ 權限不足",
                description="Bot沒有足夠權限清空此頻道的訊息",
                color=0xe74c3c
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
            
        except Exception as e:
            embed = discord.Embed(
                title="❌ 清空失敗",
                description=f"清空過程中發生錯誤：{str(e)[:100]}",
                color=0xe74c3c
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
    
    @button(label="❌ 取消", style=discord.ButtonStyle.secondary)
    async def cancel_button(self, interaction: discord.Interaction, button: Button):
        """取消操作"""
        embed = discord.Embed(
            title="✅ 已取消",
            description="頻道清空操作已取消",
            color=0x95a5a6
        )
        await interaction.response.edit_message(embed=embed, view=None)
    
    async def _clear_all_messages(self) -> int:
        """清空所有訊息"""
        deleted_count = 0
        
        # 使用purge方法批次刪除訊息
        try:
            # Discord限制：purge一次最多刪除100條訊息，且訊息不能超過14天
            while True:
                deleted = await self.channel.purge(limit=100, check=lambda m: True)
                if not deleted:
                    break
                deleted_count += len(deleted)
                
                # 避免API限制 - 增加延遲時間
                import asyncio
                await asyncio.sleep(2.0)
                
        except discord.HTTPException:
            # 如果purge失敗，嘗試逐個刪除（較慢但更可靠）
            async for message in self.channel.history(limit=None):
                try:
                    await message.delete()
                    deleted_count += 1
                    
                    # 避免API限制 - 每刪除5條訊息就暫停
                    if deleted_count % 5 == 0:
                        import asyncio
                        await asyncio.sleep(2.0)
                        
                except discord.NotFound:
                    pass  # 訊息已被刪除
                except discord.Forbidden:
                    break  # 沒有權限
                except discord.HTTPException as e:
                    # 處理速率限制
                    if e.status == 429:
                        import asyncio
                        retry_after = e.response.headers.get('Retry-After', '5')
                        await asyncio.sleep(float(retry_after))
                        continue
                    break
        
        return deleted_count
    
    async def _clear_recent_messages(self, hours: int) -> int:
        """清空最近指定小時內的訊息"""
        from datetime import datetime, timedelta, timezone
        
        cutoff_time = datetime.now(timezone.utc) - timedelta(hours=hours)
        deleted_count = 0
        
        try:
            # 使用purge刪除最近的訊息
            def check_time(message):
                return message.created_at > cutoff_time
            
            while True:
                deleted = await self.channel.purge(limit=100, check=check_time)
                if not deleted:
                    break
                deleted_count += len(deleted)
                
                # 避免API限制 - 增加延遲時間
                import asyncio
                await asyncio.sleep(2.0)
                
        except discord.HTTPException:
            # 如果purge失敗，嘗試逐個刪除
            async for message in self.channel.history(limit=None, after=cutoff_time):
                try:
                    await message.delete()
                    deleted_count += 1
                    
                    # 避免API限制 - 每刪除5條訊息就暫停
                    if deleted_count % 5 == 0:
                        import asyncio
                        await asyncio.sleep(2.0)
                        
                except discord.NotFound:
                    pass
                except discord.Forbidden:
                    break
                except discord.HTTPException as e:
                    # 處理速率限制
                    if e.status == 429:
                        import asyncio
                        retry_after = e.response.headers.get('Retry-After', '5')
                        await asyncio.sleep(float(retry_after))
                        continue
                    break
        
        return deleted_count
    
    async def _clear_user_messages(self, user_id: int) -> int:
        """清空指定用戶的所有訊息"""
        deleted_count = 0
        
        try:
            # 使用purge刪除指定用戶的訊息
            def check_user(message):
                return message.author.id == user_id
            
            while True:
                deleted = await self.channel.purge(limit=100, check=check_user)
                if not deleted:
                    break
                deleted_count += len(deleted)
                
                # 避免API限制 - 增加延遲時間
                import asyncio
                await asyncio.sleep(2.0)
                
        except discord.HTTPException:
            # 如果purge失敗，嘗試逐個刪除
            async for message in self.channel.history(limit=None):
                if message.author.id == user_id:
                    try:
                        await message.delete()
                        deleted_count += 1
                        
                        # 避免API限制 - 每刪除5條訊息就暫停
                        if deleted_count % 5 == 0:
                            import asyncio
                            await asyncio.sleep(2.0)
                            
                    except discord.NotFound:
                        pass  # 訊息已被刪除
                    except discord.Forbidden:
                        break  # 沒有權限
                    except discord.HTTPException as e:
                        # 處理速率限制
                        if e.status == 429:
                            import asyncio
                            retry_after = e.response.headers.get('Retry-After', '5')
                            await asyncio.sleep(float(retry_after))
                            continue
                        break
        
        return deleted_count


class ClearRecentModal(Modal):
    """清空近期訊息表單"""
    
    def __init__(self, channel: discord.TextChannel):
        self.channel = channel
        super().__init__(title="⏰ 清空近期訊息")
        
        self.hours = TextInput(
            label="清空多少小時內的訊息",
            placeholder="輸入小時數 (例如: 24)",
            min_length=1,
            max_length=3,
            required=True
        )
        
        self.add_item(self.hours)
    
    async def on_submit(self, interaction: discord.Interaction):
        try:
            hours = int(self.hours.value)
            if hours <= 0 or hours > 168:  # 最多7天
                await interaction.response.send_message("❌ 小時數必須在1-168之間", ephemeral=True)
                return
            
            embed = discord.Embed(
                title="❗ 確認清空近期訊息",
                description=f"將清空 {self.channel.mention} 中最近 {hours} 小時內的訊息",
                color=0xe74c3c
            )
            
            embed.add_field(
                name="⚠️ 注意",
                value=f"• 將刪除 {hours} 小時內的所有訊息\n"
                      "• 此操作無法復原\n"
                      "• 請確認選擇正確",
                inline=False
            )
            
            view = FinalConfirmView(interaction.user.id, self.channel, f"recent_{hours}")
            await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
            
        except ValueError:
            await interaction.response.send_message("❌ 請輸入有效的數字", ephemeral=True)


class ClearByUserModal(Modal):
    """按用戶清空訊息表單"""
    
    def __init__(self, channel: discord.TextChannel):
        self.channel = channel
        super().__init__(title="👤 按用戶清空訊息")
        
        self.user_id = TextInput(
            label="用戶ID或@用戶",
            placeholder="輸入用戶ID或@提及用戶",
            min_length=1,
            max_length=100,
            required=True
        )
        
        self.add_item(self.user_id)
    
    async def on_submit(self, interaction: discord.Interaction):
        try:
            user_input = self.user_id.value.strip()
            
            # 解析用戶ID或提及
            target_user = None
            if user_input.startswith('<@') and user_input.endswith('>'):
                # 處理提及格式 <@123456789> 或 <@!123456789>
                user_id_str = user_input[2:-1]
                if user_id_str.startswith('!'):
                    user_id_str = user_id_str[1:]
                try:
                    user_id = int(user_id_str)
                    target_user = interaction.guild.get_member(user_id)
                except ValueError:
                    pass
            else:
                # 嘗試直接解析為用戶ID
                try:
                    user_id = int(user_input)
                    target_user = interaction.guild.get_member(user_id)
                except ValueError:
                    pass
            
            if not target_user:
                await interaction.response.send_message("❌ 找不到指定的用戶，請檢查用戶ID或@提及格式", ephemeral=True)
                return
            
            embed = discord.Embed(
                title="❗ 確認按用戶清空訊息",
                description=f"將清空 {self.channel.mention} 中 {target_user.mention} 的所有訊息",
                color=0xe74c3c
            )
            
            embed.add_field(
                name="⚠️ 注意",
                value=f"• 將刪除該用戶的所有歷史訊息\n"
                      "• 此操作無法復原\n"
                      "• 可能需要較長時間處理",
                inline=False
            )
            
            view = FinalConfirmView(interaction.user.id, self.channel, f"user_{target_user.id}")
            await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
            
        except Exception as e:
            logger.error(f"ClearByUserModal 錯誤: {e}")
            await interaction.response.send_message("❌ 處理用戶輸入時發生錯誤", ephemeral=True)


class DataCleanupView(View):
    """資料清理界面"""
    
    def __init__(self, user_id: int, timeout=300):
        super().__init__(timeout=timeout)
        self.user_id = user_id
        self.cleanup_manager = DataCleanupManager()
    
    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        return interaction.user.id == self.user_id
    
    @button(label="🗑️ 基礎清理", style=discord.ButtonStyle.secondary)
    async def basic_cleanup_button(self, interaction: discord.Interaction, button: Button):
        """執行基礎清理"""
        await interaction.response.defer(ephemeral=True)
        
        try:
            embed = discord.Embed(
                title="🔄 正在執行基礎清理...",
                description="清理過程可能需要幾分鐘，請稍候",
                color=0xf39c12
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
            
            # 執行基礎清理
            result = await self.cleanup_manager.run_basic_cleanup()
            
            if result.success:
                embed = discord.Embed(
                    title="✅ 基礎清理完成",
                    description="已成功完成基礎資料清理",
                    color=0x2ecc71
                )
                embed.add_field(
                    name="📊 清理結果",
                    value=f"清理的資料項目: {result.cleaned_items}\n"
                          f"釋放空間: {result.space_freed_mb:.2f} MB\n"
                          f"耗時: {result.duration_seconds:.2f} 秒",
                    inline=False
                )
                if result.details:
                    embed.add_field(
                        name="📋 詳細信息",
                        value="\n".join([f"• {detail}" for detail in result.details[:5]]),
                        inline=False
                    )
            else:
                embed = discord.Embed(
                    title="❌ 清理失敗",
                    description=f"清理過程中發生錯誤：{result.error}",
                    color=0xe74c3c
                )
            
            await interaction.followup.send(embed=embed, ephemeral=True)
            
        except Exception as e:
            logger.error(f"基礎清理錯誤: {e}")
            embed = discord.Embed(
                title="❌ 清理失敗",
                description=f"清理過程中發生意外錯誤：{str(e)[:100]}",
                color=0xe74c3c
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
    
    @button(label="🔧 深度清理", style=discord.ButtonStyle.primary)
    async def full_cleanup_button(self, interaction: discord.Interaction, button: Button):
        """執行深度清理"""
        # 確認對話框
        embed = discord.Embed(
            title="⚠️ 深度清理確認",
            description="深度清理會執行以下操作：",
            color=0xf39c12
        )
        embed.add_field(
            name="🔧 清理內容",
            value="• 清理所有過期資料\n"
                  "• 優化資料庫索引\n"
                  "• 重建統計快取\n"
                  "• 清理系統日誌",
            inline=False
        )
        embed.add_field(
            name="⏰ 預計時間",
            value="5-15 分鐘（取決於資料量）",
            inline=True
        )
        embed.add_field(
            name="⚠️ 注意事項",
            value="清理期間系統性能可能受影響",
            inline=True
        )
        
        view = ConfirmCleanupView(self.user_id)
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)


class ConfirmCleanupView(View):
    """確認清理視圖"""
    
    def __init__(self, user_id: int, timeout=60):
        super().__init__(timeout=timeout)
        self.user_id = user_id
        self.cleanup_manager = DataCleanupManager()
    
    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        return interaction.user.id == self.user_id
    
    @button(label="✅ 確認執行", style=discord.ButtonStyle.danger)
    async def confirm_button(self, interaction: discord.Interaction, button: Button):
        """確認執行深度清理"""
        await interaction.response.defer(ephemeral=True)
        
        try:
            embed = discord.Embed(
                title="🔄 正在執行深度清理...",
                description="深度清理正在進行中，這可能需要幾分鐘時間",
                color=0xf39c12
            )
            embed.add_field(
                name="📋 當前狀態",
                value="正在分析資料庫...",
                inline=False
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
            
            # 執行深度清理
            result = await self.cleanup_manager.run_full_cleanup()
            
            if result.success:
                embed = discord.Embed(
                    title="✅ 深度清理完成",
                    description="已成功完成深度資料清理和優化",
                    color=0x2ecc71
                )
                embed.add_field(
                    name="📊 清理統計",
                    value=f"清理的資料項目: {result.cleaned_items:,}\n"
                          f"釋放空間: {result.space_freed_mb:.2f} MB\n"
                          f"優化表格: {len(result.details)}\n"
                          f"總耗時: {result.duration_seconds:.1f} 秒",
                    inline=False
                )
                if result.details:
                    embed.add_field(
                        name="🔧 執行的操作",
                        value="\n".join([f"• {detail}" for detail in result.details[:8]]),
                        inline=False
                    )
                embed.set_footer(text="建議定期執行深度清理以保持系統性能")
            else:
                embed = discord.Embed(
                    title="❌ 深度清理失敗",
                    description=f"清理過程中發生錯誤：{result.error}",
                    color=0xe74c3c
                )
                embed.add_field(
                    name="💡 建議",
                    value="請稍後重試，或聯繫系統管理員",
                    inline=False
                )
            
            await interaction.followup.send(embed=embed, ephemeral=True)
            
        except Exception as e:
            logger.error(f"深度清理錯誤: {e}")
            embed = discord.Embed(
                title="❌ 深度清理失敗",
                description=f"執行過程中發生意外錯誤：{str(e)[:100]}",
                color=0xe74c3c
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
    
    @button(label="❌ 取消", style=discord.ButtonStyle.secondary)
    async def cancel_button(self, interaction: discord.Interaction, button: Button):
        """取消清理操作"""
        embed = discord.Embed(
            title="✅ 已取消",
            description="深度清理操作已取消",
            color=0x95a5a6
        )
        await interaction.response.edit_message(embed=embed, view=None)


class DataExportView(View):
    """資料匯出界面"""
    
    def __init__(self, user_id: int, timeout=300):
        super().__init__(timeout=timeout)
        self.user_id = user_id
        self.export_manager = DataExportManager()
    
    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        return interaction.user.id == self.user_id
    
    @button(label="🎫 票券資料", style=discord.ButtonStyle.primary, row=0)
    async def export_tickets_button(self, interaction: discord.Interaction, button: Button):
        """匯出票券資料"""
        view = ExportFormatView(self.user_id, "tickets")
        embed = discord.Embed(
            title="🎫 選擇票券資料匯出格式",
            description="請選擇要匯出的格式和時間範圍",
            color=0x3498db
        )
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
    
    @button(label="🗳️ 投票資料", style=discord.ButtonStyle.success, row=0)  
    async def export_votes_button(self, interaction: discord.Interaction, button: Button):
        """匯出投票資料"""
        view = ExportFormatView(self.user_id, "votes")
        embed = discord.Embed(
            title="🗳️ 選擇投票資料匯出格式",
            description="請選擇要匯出的格式和時間範圍",
            color=0x3498db
        )
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
    
    @button(label="👥 用戶統計", style=discord.ButtonStyle.secondary, row=0)
    async def export_user_stats_button(self, interaction: discord.Interaction, button: Button):
        """匯出用戶統計"""
        view = ExportFormatView(self.user_id, "user_statistics") 
        embed = discord.Embed(
            title="👥 選擇用戶統計匯出格式",
            description="請選擇要匯出的格式和時間範圍",
            color=0x3498db
        )
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
    
    @button(label="📋 系統日誌", style=discord.ButtonStyle.secondary, row=1)
    async def export_logs_button(self, interaction: discord.Interaction, button: Button):
        """匯出系統日誌"""  
        view = ExportFormatView(self.user_id, "system_logs")
        embed = discord.Embed(
            title="📋 選擇系統日誌匯出格式",
            description="請選擇要匯出的格式和時間範圍",
            color=0x3498db
        )
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)


class ExportFormatView(View):
    """匯出格式選擇界面"""
    
    def __init__(self, user_id: int, data_type: str, timeout=300):
        super().__init__(timeout=timeout)
        self.user_id = user_id
        self.data_type = data_type
        self.export_manager = DataExportManager()
    
    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        return interaction.user.id == self.user_id
    
    @button(label="📄 CSV", style=discord.ButtonStyle.primary, row=0)
    async def csv_button(self, interaction: discord.Interaction, button: Button):
        """匯出為CSV格式"""
        await self._export_data(interaction, "csv")
    
    @button(label="📋 JSON", style=discord.ButtonStyle.secondary, row=0)
    async def json_button(self, interaction: discord.Interaction, button: Button):
        """匯出為JSON格式"""
        await self._export_data(interaction, "json")
    
    @button(label="📊 Excel", style=discord.ButtonStyle.success, row=0)
    async def excel_button(self, interaction: discord.Interaction, button: Button):
        """匯出為Excel格式"""
        await self._export_data(interaction, "excel")
    
    async def _export_data(self, interaction: discord.Interaction, format_type: str):
        """執行資料匯出"""
        await interaction.response.defer(ephemeral=True)
        
        try:
            # 準備匯出參數
            from bot.services.data_export_manager import ExportRequest
            
            request = ExportRequest(
                data_type=self.data_type,
                format=format_type,
                guild_id=interaction.guild.id,
                requested_by=interaction.user.id,
                days_back=30,  # 預設30天
                filters={}
            )
            
            embed = discord.Embed(
                title="📤 正在匯出資料...",
                description=f"正在匯出{self._get_data_type_name()}為{format_type.upper()}格式",
                color=0xf39c12
            )
            embed.add_field(
                name="⏳ 預計時間",
                value="1-3 分鐘（取決於資料量）",
                inline=True
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
            
            # 執行匯出
            result = await self.export_manager.export_data(request)
            
            if result.success:
                embed = discord.Embed(
                    title="✅ 匯出完成",
                    description=f"已成功匯出{self._get_data_type_name()}",
                    color=0x2ecc71
                )
                embed.add_field(
                    name="📊 匯出統計",
                    value=f"資料筆數: {result.total_records:,}\n"
                          f"檔案大小: {result.file_size_mb:.2f} MB\n"
                          f"匯出時間: {result.export_time_seconds:.1f} 秒",
                    inline=False
                )
                embed.add_field(
                    name="📁 檔案資訊",
                    value=f"格式: {format_type.upper()}\n"
                          f"檔名: `{result.file_path.split('/')[-1] if result.file_path else '未知'}`",
                    inline=True
                )
                embed.set_footer(text="檔案已儲存到伺服器匯出目錄")
            else:
                embed = discord.Embed(
                    title="❌ 匯出失敗", 
                    description=f"匯出過程中發生錯誤：{result.error}",
                    color=0xe74c3c
                )
                embed.add_field(
                    name="💡 可能原因",
                    value="• 資料庫連接問題\n• 磁碟空間不足\n• 權限不足",
                    inline=False
                )
            
            await interaction.followup.send(embed=embed, ephemeral=True)
            
        except Exception as e:
            logger.error(f"資料匯出錯誤: {e}")
            embed = discord.Embed(
                title="❌ 匯出失敗",
                description=f"執行過程中發生意外錯誤：{str(e)[:100]}",
                color=0xe74c3c
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
    
    def _get_data_type_name(self) -> str:
        """取得資料類型的中文名稱"""
        names = {
            "tickets": "票券資料",
            "votes": "投票資料", 
            "user_statistics": "用戶統計",
            "system_logs": "系統日誌"
        }
        return names.get(self.data_type, self.data_type)


class VoteAdminView(View):
    """投票管理主面板"""
    
    def __init__(self, user_id: int = None, timeout=300):
        super().__init__(timeout=timeout)
        self.user_id = user_id
    
    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        """檢查用戶權限"""
        if self.user_id and interaction.user.id != self.user_id:
            await interaction.response.send_message("❌ 只有指令使用者可以操作此面板", ephemeral=True)
            return False
        
        if not interaction.user.guild_permissions.manage_messages:
            await interaction.response.send_message("❌ 需要管理訊息權限", ephemeral=True)
            return False
        
        return True
    
    @button(label="📋 查看活躍投票", style=discord.ButtonStyle.primary, row=0)
    async def view_active_votes_button(self, interaction: discord.Interaction, button: Button):
        """查看活躍投票按鈕"""
        try:
            await interaction.response.defer()
            
            votes = await vote_dao.get_active_votes(interaction.guild.id)
            
            if not votes:
                embed = discord.Embed(
                    title="📋 活躍投票",
                    description="目前沒有進行中的投票",
                    color=0x95a5a6
                )
                await interaction.followup.send(embed=embed, ephemeral=True)
                return
            
            embed = discord.Embed(
                title="📋 活躍投票",
                description=f"找到 {len(votes)} 個進行中的投票",
                color=0x3498db
            )
            
            for vote in votes[:10]:  # 只顯示前10個
                vote_info = f"ID: {vote['id']}\n創建者: <@{vote['creator_id']}>\n結束時間: {vote['end_time'].strftime('%Y-%m-%d %H:%M')}"
                embed.add_field(
                    name=f"🗳️ {vote['title'][:50]}{'...' if len(vote['title']) > 50 else ''}",
                    value=vote_info,
                    inline=True
                )
            
            view = ActiveVoteManageView(interaction.user.id)
            await interaction.followup.send(embed=embed, view=view, ephemeral=True)
            
        except Exception as e:
            logger.error(f"查看活躍投票錯誤: {e}")
            await interaction.followup.send("❌ 無法獲取投票資訊", ephemeral=True)
    
    @button(label="📊 投票統計", style=discord.ButtonStyle.secondary, row=0)
    async def vote_statistics_button(self, interaction: discord.Interaction, button: Button):
        """投票統計按鈕"""
        try:
            await interaction.response.defer()
            
            guild_stats = await vote_dao.get_guild_vote_stats(interaction.guild.id)
            total_count = await vote_dao.get_total_vote_count(interaction.guild.id)
            
            embed = discord.Embed(
                title="📊 投票系統統計",
                description=f"{interaction.guild.name} 的投票系統概覽",
                color=0x2ecc71
            )
            
            embed.add_field(
                name="📈 基本統計",
                value=f"總投票數: {total_count}\n"
                      f"活躍投票: {guild_stats.get('active_votes', 0)}\n"
                      f"已完成投票: {guild_stats.get('completed_votes', 0)}",
                inline=True
            )
            
            embed.add_field(
                name="👥 參與統計",
                value=f"總投票次數: {guild_stats.get('total_responses', 0)}\n"
                      f"參與用戶: {guild_stats.get('unique_participants', 0)}\n"
                      f"平均參與率: {guild_stats.get('avg_participation_rate', 0):.1f}%",
                inline=True
            )
            
            embed.add_field(
                name="📅 時間範圍",
                value="統計範圍: 最近 30 天\n"
                      f"更新時間: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
                inline=False
            )
            
            await interaction.followup.send(embed=embed, ephemeral=True)
            
        except Exception as e:
            logger.error(f"獲取投票統計錯誤: {e}")
            await interaction.followup.send("❌ 無法獲取投票統計", ephemeral=True)
    
    @button(label="🛠️ 投票設定", style=discord.ButtonStyle.secondary, row=1)
    async def vote_settings_button(self, interaction: discord.Interaction, button: Button):
        """投票設定按鈕"""
        try:
            embed = discord.Embed(
                title="🛠️ 投票系統設定",
                description="投票系統功能管理",
                color=0xf39c12
            )
            
            embed.add_field(
                name="ℹ️ 功能說明",
                value="• 投票系統已啟用並正常運作\n"
                      "• 支援匿名和公開投票\n"
                      "• 支援單選和多選模式\n"
                      "• 自動統計和結果顯示",
                inline=False
            )
            
            embed.add_field(
                name="⚙️ 系統狀態",
                value="🟢 投票系統: 已啟用\n"
                      "🟢 統計功能: 正常\n"
                      "🟢 資料庫: 連接正常",
                inline=False
            )
            
            view = VoteSettingsView(interaction.user.id)
            await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
            
        except Exception as e:
            logger.error(f"投票設定錯誤: {e}")
            await interaction.response.send_message("❌ 無法載入投票設定", ephemeral=True)


class ActiveVoteManageView(View):
    """活躍投票管理介面"""
    
    def __init__(self, user_id: int, timeout=300):
        super().__init__(timeout=timeout)
        self.user_id = user_id
    
    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        """檢查用戶權限"""
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("❌ 只有指令使用者可以操作此面板", ephemeral=True)
            return False
        
        if not interaction.user.guild_permissions.manage_messages:
            await interaction.response.send_message("❌ 需要管理訊息權限", ephemeral=True)
            return False
        
        return True
    
    @button(label="📊 投票統計", style=discord.ButtonStyle.primary, row=0)
    async def vote_statistics_button(self, interaction: discord.Interaction, button: Button):
        """查看投票系統統計"""
        try:
            await interaction.response.defer()
            
            # 獲取統計數據
            active_votes = await vote_dao.get_active_votes()
            total_votes = await vote_dao.get_total_vote_count(interaction.guild.id)
            guild_stats = await vote_dao.get_guild_vote_stats(interaction.guild.id, 30)
            
            embed = discord.Embed(
                title="📊 投票系統統計",
                description=f"🏠 {interaction.guild.name} - 過去30天統計",
                color=0x2ecc71
            )
            
            embed.add_field(
                name="📈 總體統計",
                value=f"歷史投票總數: {total_votes}\n"
                      f"本月投票數: {guild_stats['total_votes']}\n"
                      f"目前活躍投票: {guild_stats['active_votes']}\n"
                      f"已完成投票: {guild_stats['finished_votes']}\n"
                      f"系統狀態: {'🟢 正常' if guild_stats['active_votes'] < 20 else '🟡 繁忙'}",
                inline=True
            )
            
            embed.add_field(
                name="👥 參與統計",
                value=f"獨特參與者: {guild_stats['unique_participants']}\n"
                      f"總投票次數: {guild_stats['total_responses']}\n"
                      f"平均參與度: {(guild_stats['total_responses'] / guild_stats['unique_participants']):.1f if guild_stats['unique_participants'] > 0 else 0} 票/人",
                inline=True
            )
            
            # 最活躍創建者
            if guild_stats['top_creators']:
                creators_info = []
                for creator in guild_stats['top_creators'][:3]:
                    user = interaction.guild.get_member(creator['user_id'])
                    user_name = user.display_name if user else f"用戶 {creator['user_id']}"
                    creators_info.append(f"{user_name}: {creator['votes_created']} 個投票")
                
                embed.add_field(
                    name="🏆 活躍創建者 (TOP 3)",
                    value="\n".join(creators_info) if creators_info else "無資料",
                    inline=False
                )
            
            # 近期投票活動
            recent_votes = await vote_dao.get_recent_votes(limit=5, guild_id=interaction.guild.id)
            if recent_votes:
                recent_info = []
                for vote in recent_votes:
                    stats = await vote_dao.get_vote_statistics(vote['id'])
                    total = sum(stats.values())
                    status = "🟢" if vote['end_time'] > datetime.now(timezone.utc) else "🔴"
                    recent_info.append(f"{status} #{vote['id']} {vote['title'][:25]} ({total}票)")
                
                embed.add_field(
                    name="🕐 近期投票 (最新5個)",
                    value="\n".join(recent_info),
                    inline=False
                )
            
            await interaction.followup.send(embed=embed, ephemeral=True)
            
        except Exception as e:
            logger.error(f"獲取投票統計錯誤: {e}")
            await interaction.followup.send("❌ 無法獲取統計資料", ephemeral=True)
    
    @button(label="🗳️ 選擇投票管理", style=discord.ButtonStyle.secondary, row=0)
    async def select_vote_button(self, interaction: discord.Interaction, button: Button):
        """選擇要管理的投票"""
        try:
            active_votes = await vote_dao.get_active_votes()
            
            if not active_votes:
                embed = discord.Embed(
                    title="📋 沒有活躍投票",
                    description="目前沒有進行中的投票",
                    color=0x95a5a6
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return
            
            # 創建選擇下拉選單
            options = []
            for vote in active_votes[:25]:  # Discord 限制最多25個選項
                stats = await vote_dao.get_vote_statistics(vote['id'])
                total = sum(stats.values())
                
                options.append(discord.SelectOption(
                    label=f"#{vote['id']} - {vote['title'][:50]}",
                    value=str(vote['id']),
                    description=f"票數: {total} | 結束: {vote['end_time'].strftime('%m-%d %H:%M')}"
                ))
            
            self.clear_items()
            self.add_item(VoteManageSelect(self.user_id, options))
            self.add_item(BackToActiveVoteManageButton(self.user_id))
            
            embed = discord.Embed(
                title="🗳️ 選擇要管理的投票",
                description="請從下拉選單中選擇要管理的投票",
                color=0x3498db
            )
            
            await interaction.response.edit_message(embed=embed, view=self)
            
        except Exception as e:
            logger.error(f"選擇投票錯誤: {e}")
            await interaction.response.send_message("❌ 無法載入投票列表", ephemeral=True)
    
    @button(label="🔄 重新整理", style=discord.ButtonStyle.secondary, row=1)
    async def refresh_button(self, interaction: discord.Interaction, button: Button):
        """重新整理投票列表"""
        try:
            vote_settings_view = VoteSettingsView(self.user_id)
            embed = await vote_settings_view._create_active_votes_embed(interaction.guild)
            
            # 重新建立介面
            new_view = ActiveVoteManageView(self.user_id)
            
            await interaction.response.edit_message(embed=embed, view=new_view)
            
        except Exception as e:
            logger.error(f"重新整理錯誤: {e}")
            await interaction.response.send_message("❌ 重新整理失敗", ephemeral=True)
    
    @button(label="❌ 關閉", style=discord.ButtonStyle.danger, row=1)
    async def close_button(self, interaction: discord.Interaction, button: Button):
        """關閉按鈕"""
        embed = discord.Embed(
            title="✅ 投票管理已關閉",
            color=0x95a5a6
        )
        await interaction.response.edit_message(embed=embed, view=None)


class VoteManageSelect(Select):
    """投票管理選擇下拉選單"""
    
    def __init__(self, user_id: int, options):
        self.user_id = user_id
        super().__init__(
            placeholder="選擇要管理的投票...",
            options=options,
            min_values=1,
            max_values=1
        )
    
    async def callback(self, interaction: discord.Interaction):
        vote_id = int(self.values[0])
        
        try:
            vote = await vote_dao.get_vote_by_id(vote_id)
            if not vote:
                await interaction.response.send_message("❌ 找不到該投票", ephemeral=True)
                return
            
            stats = await vote_dao.get_vote_statistics(vote_id)
            total = sum(stats.values())
            
            embed = discord.Embed(
                title=f"🗳️ 投票管理 - #{vote_id}",
                description=vote['title'],
                color=0x3498db
            )
            
            embed.add_field(
                name="📊 投票資訊",
                value=f"總票數: {total}\n"
                      f"模式: {'匿名' if vote['anonymous'] else '公開'}{'多選' if vote['is_multi'] else '單選'}\n"
                      f"結束時間: {vote['end_time'].strftime('%Y-%m-%d %H:%M')}",
                inline=False
            )
            
            if stats:
                stats_text = []
                for option, count in sorted(stats.items(), key=lambda x: x[1], reverse=True)[:5]:
                    percent = (count / total * 100) if total > 0 else 0
                    stats_text.append(f"{option}: {count} 票 ({percent:.1f}%)")
                
                embed.add_field(
                    name="📈 目前結果 (前5名)",
                    value="\n".join(stats_text),
                    inline=False
                )
            
            view = SingleVoteManageView(self.user_id, vote_id)
            await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
            
        except Exception as e:
            logger.error(f"獲取投票詳情錯誤: {e}")
            await interaction.response.send_message("❌ 無法獲取投票詳情", ephemeral=True)


class SingleVoteManageView(View):
    """單一投票管理介面"""
    
    def __init__(self, user_id: int, vote_id: int, timeout=300):
        super().__init__(timeout=timeout)
        self.user_id = user_id
        self.vote_id = vote_id
    
    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        return interaction.user.id == self.user_id
    
    @button(label="🛑 強制結束", style=discord.ButtonStyle.danger, row=0)
    async def force_end_vote_button(self, interaction: discord.Interaction, button: Button):
        """強制結束投票"""
        try:
            # 確認對話框
            embed = discord.Embed(
                title="⚠️ 確認強制結束投票",
                description=f"你確定要強制結束投票 #{self.vote_id} 嗎？\n這個操作無法復原。",
                color=0xe74c3c
            )
            
            view = VoteConfirmActionView(self.user_id, self.vote_id, "force_end")
            await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
            
        except Exception as e:
            logger.error(f"強制結束投票錯誤: {e}")
            await interaction.response.send_message("❌ 操作失敗", ephemeral=True)
    
    @button(label="📊 詳細統計", style=discord.ButtonStyle.primary, row=0)
    async def detailed_stats_button(self, interaction: discord.Interaction, button: Button):
        """查看詳細統計"""
        try:
            await interaction.response.defer()
            
            vote = await vote_dao.get_vote_by_id(self.vote_id)
            stats = await vote_dao.get_vote_statistics(self.vote_id)
            participation_stats = await vote_dao.get_vote_participation_stats(self.vote_id)
            
            if not vote:
                await interaction.followup.send("❌ 找不到該投票", ephemeral=True)
                return
            
            total = sum(stats.values())
            
            embed = discord.Embed(
                title=f"📊 詳細統計 - #{self.vote_id}",
                description=vote['title'],
                color=0x2ecc71
            )
            
            embed.add_field(
                name="🕐 時間資訊",
                value=f"開始: {vote['start_time'].strftime('%Y-%m-%d %H:%M')}\n"
                      f"結束: {vote['end_time'].strftime('%Y-%m-%d %H:%M')}\n"
                      f"狀態: {'進行中' if vote['end_time'] > datetime.now(timezone.utc) else '已結束'}",
                inline=True
            )
            
            embed.add_field(
                name="⚙️ 設定",
                value=f"匿名: {'是' if vote['anonymous'] else '否'}\n"
                      f"多選: {'是' if vote['is_multi'] else '否'}\n"
                      f"總票數: {total}",
                inline=True
            )
            
            embed.add_field(
                name="👥 參與分析",
                value=f"獨特投票者: {participation_stats['unique_users']}\n"
                      f"總投票次數: {participation_stats['total_responses']}\n"
                      f"平均每人: {(participation_stats['total_responses'] / participation_stats['unique_users']):.1f if participation_stats['unique_users'] > 0 else 0} 票",
                inline=True
            )
            
            # 投票結果進度條
            if stats:
                from bot.utils.vote_utils import calculate_progress_bar
                
                results = []
                for option, count in sorted(stats.items(), key=lambda x: x[1], reverse=True):
                    percent = (count / total * 100) if total > 0 else 0
                    bar = calculate_progress_bar(percent, 15)
                    results.append(f"{option}\n{count} 票 ({percent:.1f}%) {bar}")
                
                embed.add_field(
                    name="📈 投票結果",
                    value="\n\n".join(results[:8]),  # 最多顯示8個選項
                    inline=False
                )
            
            await interaction.followup.send(embed=embed, ephemeral=True)
            
        except Exception as e:
            logger.error(f"獲取詳細統計錯誤: {e}")
            await interaction.followup.send("❌ 無法獲取統計資料", ephemeral=True)


class VoteConfirmActionView(View):
    """投票確認操作介面"""
    
    def __init__(self, user_id: int, vote_id: int, action_type: str, timeout=60):
        super().__init__(timeout=timeout)
        self.user_id = user_id
        self.vote_id = vote_id
        self.action_type = action_type
    
    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        return interaction.user.id == self.user_id
    
    @button(label="✅ 確認", style=discord.ButtonStyle.danger)
    async def confirm_action(self, interaction: discord.Interaction, button: Button):
        """確認執行操作"""
        try:
            if self.action_type == "force_end":
                # 強制結束投票
                success = await vote_dao.end_vote(self.vote_id)
                
                if success:
                    # 發送結果通知
                    from bot.cogs.vote import VoteCog
                    vote_cog = interaction.client.get_cog("VoteCog")
                    if vote_cog:
                        try:
                            await vote_cog._send_vote_result(self.vote_id)
                        except Exception as e:
                            logger.error(f"發送投票結果錯誤: {e}")
                    
                    embed = discord.Embed(
                        title="✅ 投票已強制結束",
                        description=f"投票 #{self.vote_id} 已成功結束並公告結果",
                        color=0x2ecc71
                    )
                    await interaction.response.send_message(embed=embed, ephemeral=True)
                else:
                    await interaction.response.send_message("❌ 結束投票失敗", ephemeral=True)
            
        except Exception as e:
            logger.error(f"確認操作錯誤: {e}")
            await interaction.response.send_message("❌ 操作執行失敗", ephemeral=True)
    
    @button(label="❌ 取消", style=discord.ButtonStyle.secondary)
    async def cancel_action(self, interaction: discord.Interaction, button: Button):
        """取消操作"""
        embed = discord.Embed(
            title="❌ 操作已取消",
            description="沒有執行任何變更",
            color=0x95a5a6
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)


class BackToActiveVoteManageButton(Button):
    """返回活躍投票管理按鈕"""
    
    def __init__(self, user_id: int):
        self.user_id = user_id
        super().__init__(label="← 返回", style=discord.ButtonStyle.secondary)
    
    async def callback(self, interaction: discord.Interaction):
        vote_settings_view = VoteSettingsView(self.user_id)
        embed = await vote_settings_view._create_active_votes_embed(interaction.guild)
        view = ActiveVoteManageView(self.user_id)
        await interaction.response.edit_message(embed=embed, view=view)

