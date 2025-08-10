# bot/cogs/web_auth.py
"""
Web 認證相關指令
提供 Discord 用戶設定 Web 密碼和管理 API 金鑰的功能
"""

import discord
from discord.ext import commands
from discord import app_commands
from typing import Optional, List
from datetime import datetime, timezone

from shared.logger import logger
from bot.services.auth_manager import auth_manager
from bot.utils.embed_builder import EmbedBuilder


class WebAuthCommands(commands.Cog):
    """Web 認證指令組"""
    
    def __init__(self, bot):
        self.bot = bot
    
    @app_commands.command(name="setup-web-password", description="設定 Web 介面登入密碼")
    @app_commands.describe(password="設定的密碼 (至少 6 個字元)")
    async def setup_web_password(self, interaction: discord.Interaction, password: str):
        """設定 Web 介面登入密碼"""
        try:
            await interaction.response.defer(ephemeral=True)
            
            # 驗證密碼長度
            if len(password) < 6:
                embed = EmbedBuilder.error(
                    title="❌ 密碼設定失敗",
                    description="密碼長度至少需要 6 個字元"
                )
                await interaction.followup.send(embed=embed, ephemeral=True)
                return
            
            # 同步用戶到認證系統
            success, message, auth_user = await auth_manager.sync_discord_user(
                interaction.user, password
            )
            
            if success:
                embed = EmbedBuilder.success(
                    title="✅ Web 密碼設定成功", 
                    description=f"你現在可以使用以下資訊登入 Web 介面："
                )
                
                embed.add_field(
                    name="🔑 登入資訊",
                    value=f"**Discord ID**: `{interaction.user.id}`\n"
                          f"**用戶名稱**: `{interaction.user.display_name}`\n"
                          f"**伺服器 ID**: `{interaction.guild_id}`",
                    inline=False
                )
                
                embed.add_field(
                    name="🌐 Web 介面",
                    value="http://localhost:8000/docs\n"
                          "*請使用 Discord ID 和設定的密碼登入*",
                    inline=False
                )
                
                if auth_user.is_admin:
                    embed.add_field(
                        name="👑 管理員權限",
                        value="你擁有完整的系統管理權限",
                        inline=True
                    )
                elif auth_user.is_staff:
                    embed.add_field(
                        name="🛠️ 客服權限", 
                        value="你擁有票券處理和統計查看權限",
                        inline=True
                    )
                
                embed.set_footer(text="⚠️ 請妥善保管密碼，不要與他人分享")
                
            else:
                embed = EmbedBuilder.error(
                    title="❌ 密碼設定失敗",
                    description=message
                )
            
            await interaction.followup.send(embed=embed, ephemeral=True)
            logger.info(f"用戶 {interaction.user} 設定 Web 密碼: {success}")
            
        except Exception as e:
            logger.error(f"設定 Web 密碼錯誤: {e}")
            embed = EmbedBuilder.error(
                title="❌ 系統錯誤",
                description="設定密碼時發生錯誤，請稍後再試"
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
    
    @app_commands.command(name="create-api-key", description="創建 API 金鑰")
    @app_commands.describe(
        name="API 金鑰名稱",
        expires_days="過期天數 (0 表示永不過期，預設 30 天)"
    )
    async def create_api_key(self, interaction: discord.Interaction, 
                           name: str, expires_days: int = 30):
        """創建 API 金鑰"""
        try:
            await interaction.response.defer(ephemeral=True)
            
            # 先同步用戶以確保存在於認證系統中
            success, message, auth_user = await auth_manager.sync_discord_user(interaction.user)
            if not success or not auth_user:
                embed = EmbedBuilder.error(
                    title="❌ 用戶同步失敗",
                    description="請先使用 `/setup-web-password` 設定 Web 密碼"
                )
                await interaction.followup.send(embed=embed, ephemeral=True)
                return
            
            # 檢查是否有權限創建 API 金鑰
            if not (auth_user.is_staff or auth_user.is_admin):
                embed = EmbedBuilder.error(
                    title="❌ 權限不足",
                    description="只有客服人員和管理員可以創建 API 金鑰"
                )
                await interaction.followup.send(embed=embed, ephemeral=True)
                return
            
            # 設定權限
            permissions = []
            if auth_user.is_admin:
                permissions = ['all']
            elif auth_user.is_staff:
                permissions = ['tickets.read', 'tickets.write', 'statistics.read']
            
            # 創建 API 金鑰
            success, message, api_key = await auth_manager.create_api_key(
                auth_user.user_id, name, permissions, expires_days
            )
            
            if success and api_key:
                embed = EmbedBuilder.success(
                    title="✅ API 金鑰創建成功",
                    description="請妥善保存以下 API 金鑰，它只會顯示一次！"
                )
                
                embed.add_field(
                    name="🔑 API 金鑰",
                    value=f"```\n{api_key}\n```",
                    inline=False
                )
                
                embed.add_field(
                    name="📋 金鑰資訊",
                    value=f"**名稱**: {name}\n"
                          f"**權限**: {', '.join(permissions)}\n"
                          f"**過期**: {'永不過期' if expires_days == 0 else f'{expires_days} 天後'}",
                    inline=False
                )
                
                embed.add_field(
                    name="🌐 使用方式",
                    value="在 HTTP 請求標頭中加入：\n"
                          f"```\nAuthorization: Bearer {api_key}\n```",
                    inline=False
                )
                
                embed.set_footer(text="⚠️ 請立即複製並安全保存此金鑰")
                
            else:
                embed = EmbedBuilder.error(
                    title="❌ 創建失敗",
                    description=message
                )
            
            await interaction.followup.send(embed=embed, ephemeral=True)
            logger.info(f"用戶 {interaction.user} 創建 API 金鑰: {success}")
            
        except Exception as e:
            logger.error(f"創建 API 金鑰錯誤: {e}")
            embed = EmbedBuilder.error(
                title="❌ 系統錯誤",
                description="創建 API 金鑰時發生錯誤，請稍後再試"
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
    
    @app_commands.command(name="list-api-keys", description="列出我的 API 金鑰")
    async def list_api_keys(self, interaction: discord.Interaction):
        """列出用戶的 API 金鑰"""
        try:
            await interaction.response.defer(ephemeral=True)
            
            # 獲取用戶認證資訊
            success, message, auth_user = await auth_manager.sync_discord_user(interaction.user)
            if not success or not auth_user:
                embed = EmbedBuilder.error(
                    title="❌ 用戶不存在",
                    description="請先使用 `/setup-web-password` 設定 Web 密碼"
                )
                await interaction.followup.send(embed=embed, ephemeral=True)
                return
            
            # 獲取 API 金鑰列表
            api_keys = await auth_manager.get_user_api_keys(auth_user.user_id)
            
            if not api_keys:
                embed = EmbedBuilder.info(
                    title="📋 API 金鑰列表",
                    description="你尚未創建任何 API 金鑰\n\n"
                               "使用 `/create-api-key` 創建新的 API 金鑰"
                )
            else:
                embed = EmbedBuilder.info(
                    title="📋 你的 API 金鑰",
                    description=f"共找到 {len(api_keys)} 個 API 金鑰："
                )
                
                for i, key in enumerate(api_keys[:10], 1):  # 最多顯示 10 個
                    status = "🟢 活躍" if key['is_active'] else "🔴 已撤銷"
                    expires = "永不過期" if not key['expires_at'] else f"<t:{int(datetime.fromisoformat(key['expires_at'].replace('Z', '+00:00')).timestamp())}:R>"
                    last_used = "從未使用" if not key['last_used'] else f"<t:{int(datetime.fromisoformat(key['last_used'].replace('Z', '+00:00')).timestamp())}:R>"
                    
                    embed.add_field(
                        name=f"{i}. {key['name']}",
                        value=f"**狀態**: {status}\n"
                              f"**金鑰 ID**: `{key['key_id']}`\n"
                              f"**過期時間**: {expires}\n"
                              f"**最後使用**: {last_used}",
                        inline=False
                    )
                
                if len(api_keys) > 10:
                    embed.set_footer(text=f"僅顯示前 10 個金鑰，共 {len(api_keys)} 個")
            
            await interaction.followup.send(embed=embed, ephemeral=True)
            
        except Exception as e:
            logger.error(f"列出 API 金鑰錯誤: {e}")
            embed = EmbedBuilder.error(
                title="❌ 系統錯誤",
                description="獲取 API 金鑰列表時發生錯誤"
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
    
    @app_commands.command(name="revoke-api-key", description="撤銷 API 金鑰")
    @app_commands.describe(key_id="要撤銷的 API 金鑰 ID")
    async def revoke_api_key(self, interaction: discord.Interaction, key_id: str):
        """撤銷 API 金鑰"""
        try:
            await interaction.response.defer(ephemeral=True)
            
            # 獲取用戶認證資訊
            success, message, auth_user = await auth_manager.sync_discord_user(interaction.user)
            if not success or not auth_user:
                embed = EmbedBuilder.error(
                    title="❌ 用戶不存在",
                    description="請先使用 `/setup-web-password` 設定 Web 密碼"
                )
                await interaction.followup.send(embed=embed, ephemeral=True)
                return
            
            # 撤銷 API 金鑰
            success = await auth_manager.revoke_api_key(auth_user.user_id, key_id)
            
            if success:
                embed = EmbedBuilder.success(
                    title="✅ API 金鑰已撤銷",
                    description=f"API 金鑰 `{key_id}` 已成功撤銷\n\n"
                               "此金鑰將無法再用於 API 訪問"
                )
            else:
                embed = EmbedBuilder.error(
                    title="❌ 撤銷失敗",
                    description="找不到指定的 API 金鑰或撤銷失敗"
                )
            
            await interaction.followup.send(embed=embed, ephemeral=True)
            logger.info(f"用戶 {interaction.user} 撤銷 API 金鑰 {key_id}: {success}")
            
        except Exception as e:
            logger.error(f"撤銷 API 金鑰錯誤: {e}")
            embed = EmbedBuilder.error(
                title="❌ 系統錯誤",
                description="撤銷 API 金鑰時發生錯誤"
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
    
    @app_commands.command(name="web-login-info", description="顯示 Web 登入資訊")
    async def web_login_info(self, interaction: discord.Interaction):
        """顯示 Web 登入資訊"""
        try:
            await interaction.response.defer(ephemeral=True)
            
            # 獲取用戶認證資訊
            success, message, auth_user = await auth_manager.sync_discord_user(interaction.user)
            
            embed = EmbedBuilder.info(
                title="🌐 Web 介面登入資訊",
                description="以下是你的 Web 介面登入相關資訊："
            )
            
            if success and auth_user:
                embed.add_field(
                    name="🔑 登入憑證",
                    value=f"**Discord ID**: `{interaction.user.id}`\n"
                          f"**伺服器 ID**: `{interaction.guild_id}`\n"
                          f"**狀態**: ✅ 已設定密碼",
                    inline=False
                )
                
                embed.add_field(
                    name="👤 用戶角色",
                    value=f"**管理員**: {'是' if auth_user.is_admin else '否'}\n"
                          f"**客服人員**: {'是' if auth_user.is_staff else '否'}\n"
                          f"**Discord 角色**: {', '.join(auth_user.roles[:5])}",
                    inline=False
                )
                
                embed.add_field(
                    name="🔐 權限",
                    value=', '.join(auth_user.permissions[:10]) if auth_user.permissions else "無特殊權限",
                    inline=False
                )
            else:
                embed.add_field(
                    name="❌ 尚未設定",
                    value="你尚未設定 Web 登入密碼\n\n"
                          "請使用 `/setup-web-password` 設定密碼",
                    inline=False
                )
            
            embed.add_field(
                name="🌐 Web 介面網址",
                value="http://localhost:8000/docs\n"
                      "*API 文檔和測試介面*",
                inline=False
            )
            
            embed.add_field(
                name="📖 相關指令",
                value="• `/setup-web-password` - 設定/更新密碼\n"
                      "• `/create-api-key` - 創建 API 金鑰\n"
                      "• `/list-api-keys` - 查看 API 金鑰\n"
                      "• `/revoke-api-key` - 撤銷 API 金鑰",
                inline=False
            )
            
            await interaction.followup.send(embed=embed, ephemeral=True)
            
        except Exception as e:
            logger.error(f"顯示 Web 登入資訊錯誤: {e}")
            embed = EmbedBuilder.error(
                title="❌ 系統錯誤",
                description="獲取登入資訊時發生錯誤"
            )
            await interaction.followup.send(embed=embed, ephemeral=True)


async def setup(bot):
    """載入 Cog"""
    await bot.add_cog(WebAuthCommands(bot))