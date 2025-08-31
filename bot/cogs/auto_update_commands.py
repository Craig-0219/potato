# bot/cogs/auto_update_commands.py
# 🔄 自動更新指令
# Auto Update Commands

import logging
import os
from datetime import datetime

import discord
from discord import app_commands
from discord.ext import commands

from bot.services.github_update_checker import AutoUpdateManager
from bot.utils.interaction_helper import SafeInteractionHandler

logger = logging.getLogger(__name__)


class AutoUpdateCommands(commands.Cog):
    """自動更新指令"""

    def __init__(self, bot):
        self.bot = bot
        self.update_manager = None
        self._init_update_manager()

    def _init_update_manager(self):
        """初始化更新管理器"""
        try:
            owner = os.getenv("GITHUB_REPO_OWNER", "Craig-0219")
            repo = os.getenv("GITHUB_REPO_NAME", "potato")
            current_version = os.getenv("CURRENT_VERSION", "v2025.08.30")
            token = os.getenv("GITHUB_TOKEN")  # 可選

            self.update_manager = AutoUpdateManager(owner, repo, current_version, token)
            logger.info(f"✅ 更新管理器初始化完成: {owner}/{repo} v{current_version}")

        except Exception as e:
            logger.error(f"❌ 更新管理器初始化失敗: {e}")

    @app_commands.command(name="check_updates", description="🔄 檢查系統更新")
    @app_commands.default_permissions(administrator=True)
    async def check_updates(self, interaction: discord.Interaction):
        """檢查系統更新"""
        try:
            if not await SafeInteractionHandler.safe_defer(interaction, ephemeral=True):
                return

            if not self.update_manager:
                await SafeInteractionHandler.safe_followup(
                    interaction, "❌ 更新管理器未初始化", ephemeral=True
                )
                return

            # 強制檢查更新
            update_info = await self.update_manager.check_for_updates(force=True)
            
            if not update_info:
                await SafeInteractionHandler.safe_followup(
                    interaction, "❌ 無法檢查更新，請檢查網路連線", ephemeral=True
                )
                return

            # 處理錯誤
            if "error" in update_info:
                await SafeInteractionHandler.safe_followup(
                    interaction, f"❌ 檢查更新失敗: {update_info['error']}", ephemeral=True
                )
                return

            # 建立回應 Embed
            if update_info.get("has_update"):
                embed = await self._create_update_embed(update_info)
            else:
                embed = discord.Embed(
                    title="✅ 系統已是最新版本",
                    description=f"目前版本: **{update_info['current_version']}**",
                    color=discord.Color.green(),
                    timestamp=datetime.now()
                )
                embed.add_field(
                    name="檢查時間",
                    value=f"<t:{int(datetime.now().timestamp())}:R>",
                    inline=False
                )

            await SafeInteractionHandler.safe_followup(
                interaction, embed=embed, ephemeral=True
            )

        except Exception as e:
            logger.error(f"❌ 檢查更新指令錯誤: {e}")
            await SafeInteractionHandler.safe_followup(
                interaction, f"❌ 檢查更新失敗: {str(e)}", ephemeral=True
            )

    @app_commands.command(name="update_info", description="📋 顯示更新資訊")
    @app_commands.default_permissions(administrator=True)
    async def update_info(self, interaction: discord.Interaction):
        """顯示更新資訊"""
        try:
            if not await SafeInteractionHandler.safe_defer(interaction, ephemeral=True):
                return

            if not self.update_manager:
                await SafeInteractionHandler.safe_followup(
                    interaction, "❌ 更新管理器未初始化", ephemeral=True
                )
                return

            # 獲取更新摘要
            summary = await self.update_manager.get_update_summary()
            
            if "error" in summary:
                await SafeInteractionHandler.safe_followup(
                    interaction, f"❌ 獲取更新資訊失敗: {summary['error']}", ephemeral=True
                )
                return

            embed = discord.Embed(
                title="🔄 系統更新資訊",
                color=discord.Color.blue(),
                timestamp=datetime.now()
            )

            if summary.get("update_available"):
                embed.color = discord.Color.orange()
                embed.add_field(
                    name="📦 版本資訊",
                    value=f"**目前版本**: {summary['current_version']}\n"
                          f"**最新版本**: {summary['latest_version']}\n"
                          f"**發布名稱**: {summary['release_name']}",
                    inline=False
                )

                embed.add_field(
                    name="📅 發布資訊",
                    value=f"**發布時間**: {summary['published_at'][:10]}\n"
                          f"**更新類型**: {'🔴 主要更新' if summary['is_major_update'] else '🟡 次要更新'}\n"
                          f"**提交數量**: {summary['commits_count']} 個變更",
                    inline=False
                )

                if summary['release_notes']:
                    embed.add_field(
                        name="📝 更新說明",
                        value=summary['release_notes'],
                        inline=False
                    )

                embed.add_field(
                    name="🔗 相關連結",
                    value=f"[查看完整更新說明]({summary['download_url']})",
                    inline=False
                )
            else:
                embed.add_field(
                    name="✅ 狀態",
                    value=summary.get("message", "系統已是最新版本"),
                    inline=False
                )

            # 顯示 API 使用情況
            if "rate_limit" in summary:
                rate_limit = summary["rate_limit"]
                if rate_limit:
                    embed.add_field(
                        name="📊 API 使用情況",
                        value=f"已使用: {rate_limit.get('used', 0)}/{rate_limit.get('limit', 5000)}\n"
                              f"重置時間: <t:{int(rate_limit.get('reset_at', datetime.now()).timestamp())}:R>",
                        inline=True
                    )

            await SafeInteractionHandler.safe_followup(
                interaction, embed=embed, ephemeral=True
            )

        except Exception as e:
            logger.error(f"❌ 更新資訊指令錯誤: {e}")
            await SafeInteractionHandler.safe_followup(
                interaction, f"❌ 獲取更新資訊失敗: {str(e)}", ephemeral=True
            )

    async def _create_update_embed(self, update_info: dict) -> discord.Embed:
        """建立更新通知 Embed"""
        release_info = update_info["release_info"]
        comparison = update_info["comparison"]
        
        embed = discord.Embed(
            title="🆕 發現系統更新",
            description=f"**{release_info['name']}** 現已發布！",
            color=discord.Color.gold(),
            timestamp=datetime.now()
        )

        embed.add_field(
            name="📦 版本資訊",
            value=f"**目前版本**: {comparison['current']}\n"
                  f"**最新版本**: {comparison['target']}\n"
                  f"**發布時間**: {release_info['published_at'][:10]}",
            inline=True
        )

        # 更新類型
        update_type = "🔴 主要更新" if comparison.get("is_major_update") else \
                     "🟡 次要更新" if comparison.get("is_minor_update") else \
                     "🟢 修復更新"
        
        embed.add_field(
            name="🏷️ 更新類型",
            value=update_type,
            inline=True
        )

        if comparison.get("commits_count", 0) > 0:
            embed.add_field(
                name="📈 變更統計",
                value=f"{comparison['commits_count']} 個提交",
                inline=True
            )

        # 發布說明（限制長度）
        if release_info.get("body"):
            notes = release_info["body"]
            if len(notes) > 1000:
                notes = notes[:1000] + "..."
            
            embed.add_field(
                name="📝 發布說明",
                value=notes,
                inline=False
            )

        embed.add_field(
            name="🔗 更多資訊",
            value=f"[查看完整更新說明]({release_info['html_url']})",
            inline=False
        )

        return embed


async def setup(bot):
    await bot.add_cog(AutoUpdateCommands(bot))