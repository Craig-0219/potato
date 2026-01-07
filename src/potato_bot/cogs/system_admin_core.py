# bot/cogs/system_admin_core.py
"""
系統管理 Cog - 簡化版（移除備份指令）
提供基本的系統管理入口與狀態查詢
"""

import discord
from discord import app_commands
from discord.ext import commands

from potato_shared.logger import logger


class SystemAdmin(commands.Cog):
    """系統管理功能 - 簡化版"""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="admin", description="系統管理面板")
    @app_commands.default_permissions(administrator=True)
    async def admin_panel(self, interaction: discord.Interaction):
        """系統管理面板"""
        try:
            from potato_bot.views.system_admin_views import SystemAdminPanel

            embed = discord.Embed(
                title="🔧 系統管理面板",
                description="選擇要執行的管理操作",
                color=0x3498DB,
            )

            embed.add_field(
                name="📊 功能模組",
                value="• 🎫 票券系統設定\n• 🎉 歡迎系統設定\n• 🗳️ 投票系統設定\n• 🛂 入境審核設定\n• 🧾 履歷系統設定\n• 🔧 系統工具",
                inline=False,
            )

            embed.add_field(
                name="💡 使用說明",
                value="點擊下方按鈕進入相應的設定頁面",
                inline=False,
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


async def setup(bot: commands.Bot):
    await bot.add_cog(SystemAdmin(bot))
