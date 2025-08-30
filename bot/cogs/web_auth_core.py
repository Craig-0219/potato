# bot/cogs/web_auth_core.py
"""
Web 認證相關指令
提供 Discord 用戶設定 Web 密碼和管理 API 金鑰的功能
"""


import discord
from discord import app_commands
from discord.ext import commands

from bot.services.auth_manager import auth_manager
from bot.utils.embed_builder import EmbedBuilder
from bot.utils.interaction_helper import SafeInteractionHandler
from shared.logger import logger


class WebAuthCommands(commands.Cog):
    """Web 認證指令組"""

    def __init__(self, bot):
        self.bot = bot
        self.web_auth_manager = auth_manager

    @app_commands.command(name="setup-web-password", description="設定 Web 介面登入密碼")
    @app_commands.describe(password="設定的密碼 (至少 6 個字元)")
    async def setup_web_password(self, interaction: discord.Interaction, password: str):
        """設定 Web 介面登入密碼"""
        try:
            if not await SafeInteractionHandler.safe_defer(interaction, ephemeral=True):
                return

            # 驗證密碼長度
            if len(password) < 6:
                await interaction.followup.send("❌ 密碼長度至少需要 6 個字元", ephemeral=True)
                return

            # 設定密碼邏輯
            success = await auth_manager.set_user_password(interaction.user.id, password)
            if success:
                await interaction.followup.send("✅ Web 密碼設定成功", ephemeral=True)
            else:
                await interaction.followup.send("❌ Web 密碼設定失敗", ephemeral=True)

        except Exception as e:
            await SafeInteractionHandler.handle_interaction_error(interaction, e, "設定 Web 密碼")

    @app_commands.command(name="create-api-key", description="創建 API 金鑰")
    @app_commands.describe(
        name="API 金鑰名稱", expires_days="過期天數 (0 表示永不過期，預設 30 天)"
    )
    async def create_api_key(
        self, interaction: discord.Interaction, name: str, expires_days: int = 30
    ):
        """創建 API 金鑰"""
        try:
            if not await SafeInteractionHandler.safe_defer(interaction, ephemeral=True):
                return

            # 驗證金鑰名稱
            if not name or len(name.strip()) == 0:
                await interaction.followup.send("❌ API 金鑰名稱不能為空", ephemeral=True)
                return

            # 創建 API 金鑰
            api_key = await auth_manager.create_api_key(
                user_id=interaction.user.id,
                name=name.strip(),
                expires_days=expires_days if expires_days > 0 else None,
            )

            if api_key:
                embed = EmbedBuilder.success(
                    title="✅ API 金鑰創建成功",
                    description=f"**金鑰名稱:** {name}\n**金鑰:** `{api_key}`\n\n⚠️ 請妥善保存此金鑰，離開後將無法再次查看",
                )
                await interaction.followup.send(embed=embed, ephemeral=True)
            else:
                await interaction.followup.send("❌ API 金鑰創建失敗", ephemeral=True)

        except Exception as e:
            logger.error(f"創建 API 金鑰時發生錯誤: {e}")
            await SafeInteractionHandler.handle_interaction_error(interaction, e, "創建 API 金鑰")

    @app_commands.command(name="list-api-keys", description="列出我的 API 金鑰")
    async def list_api_keys(self, interaction: discord.Interaction):
        """列出用戶的 API 金鑰"""
        try:
            if not await SafeInteractionHandler.safe_defer(interaction, ephemeral=True):
                return

            # 取得用戶的 API 金鑰列表
            api_keys = await auth_manager.get_user_api_keys(interaction.user.id)

            if not api_keys:
                embed = EmbedBuilder.info(
                    title="📋 API 金鑰列表",
                    description="您還沒有創建任何 API 金鑰\n使用 `/create-api-key` 指令來創建一個",
                )
                await interaction.followup.send(embed=embed, ephemeral=True)
                return

            # 構建金鑰列表
            key_list = []
            for key_info in api_keys:
                status = "🟢 有效" if key_info.get("is_active", True) else "🔴 已撤銷"
                expires = key_info.get("expires_at")
                expires_str = expires.strftime("%Y-%m-%d %H:%M") if expires else "永不過期"

                key_list.append(
                    f"**{key_info['name']}** (ID: `{key_info['id'][:8]}...`)\n"
                    f"└ 狀態: {status} | 過期: {expires_str}"
                )

            embed = EmbedBuilder.info(
                title="📋 您的 API 金鑰列表", description="\n\n".join(key_list)
            )
            embed.add_field(
                name="💡 提示",
                value="使用 `/revoke-api-key` 指令可以撤銷不需要的金鑰",
                inline=False,
            )
            await interaction.followup.send(embed=embed, ephemeral=True)

        except Exception as e:
            logger.error(f"列出 API 金鑰時發生錯誤: {e}")
            await SafeInteractionHandler.handle_interaction_error(interaction, e, "列出 API 金鑰")

    @app_commands.command(name="revoke-api-key", description="撤銷 API 金鑰")
    @app_commands.describe(key_id="要撤銷的 API 金鑰 ID")
    async def revoke_api_key(self, interaction: discord.Interaction, key_id: str):
        """撤銷 API 金鑰"""
        try:
            if not await SafeInteractionHandler.safe_defer(interaction, ephemeral=True):
                return

            # 驗證金鑰 ID
            if not key_id or len(key_id.strip()) == 0:
                await interaction.followup.send("❌ API 金鑰 ID 不能為空", ephemeral=True)
                return

            # 撤銷 API 金鑰
            success = await auth_manager.revoke_api_key(
                user_id=interaction.user.id, key_id=key_id.strip()
            )

            if success:
                embed = EmbedBuilder.success(
                    title="✅ API 金鑰已撤銷",
                    description=f"ID 為 `{key_id[:8]}...` 的 API 金鑰已成功撤銷",
                )
                await interaction.followup.send(embed=embed, ephemeral=True)
            else:
                await interaction.followup.send(
                    "❌ API 金鑰撤銷失敗，請確認 ID 是否正確", ephemeral=True
                )

        except Exception as e:
            logger.error(f"撤銷 API 金鑰時發生錯誤: {e}")
            await SafeInteractionHandler.handle_interaction_error(interaction, e, "撤銷 API 金鑰")

    @app_commands.command(name="web-login-info", description="顯示 Web 登入資訊")
    async def web_login_info(self, interaction: discord.Interaction):
        """顯示 Web 登入資訊"""
        try:
            if not await SafeInteractionHandler.safe_defer(interaction, ephemeral=True):
                return

            # 取得用戶 Web 登入資訊
            user_info = await auth_manager.get_user_web_info(interaction.user.id)

            if not user_info or not user_info.get("has_password", False):
                embed = EmbedBuilder.warning(
                    title="⚠️ 尚未設定 Web 密碼",
                    description="您還沒有設定 Web 介面登入密碼\n請使用 `/setup-web-password` 指令來設定",
                )
                await interaction.followup.send(embed=embed, ephemeral=True)
                return

            # 構建登入資訊
            username = f"user_{interaction.user.id}"
            web_url = "https://your-web-interface.com"  # 這應該從配置中取得

            embed = EmbedBuilder.info(
                title="🌐 Web 登入資訊",
                description=f"**登入網址:** {web_url}\n**用戶名:** `{username}`\n**密碼:** 您設定的密碼",
            )
            embed.add_field(
                name="💡 安全提醒",
                value="• 請不要將登入資訊分享給他人\n• 如需更改密碼，請重新執行 `/setup-web-password`",
                inline=False,
            )

            # 顯示最後登入時間（如果有的話）
            last_login = user_info.get("last_login")
            if last_login:
                embed.add_field(
                    name="📅 最後登入",
                    value=last_login.strftime("%Y-%m-%d %H:%M:%S"),
                    inline=True,
                )

            await interaction.followup.send(embed=embed, ephemeral=True)

        except Exception as e:
            logger.error(f"顯示 Web 登入資訊時發生錯誤: {e}")
            await SafeInteractionHandler.handle_interaction_error(
                interaction, e, "顯示 Web 登入資訊"
            )


async def setup(bot):
    """載入 Cog"""
    await bot.add_cog(WebAuthCommands(bot))
