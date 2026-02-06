# bot/cogs/system_admin_core.py
"""
系統管理 Cog - 簡化版（移除備份指令）
提供基本的系統管理入口與狀態查詢
"""
from typing import Any, Dict
import discord
from discord import app_commands
from discord.ext import commands

from potato_shared.logger import logger
from potato_shared.cache_manager import cache_manager
from potato_bot.db.cached_ticket_dao import cached_ticket_dao
from potato_bot.utils.embed_builder import EmbedBuilder
from potato_bot.utils.ticket_constants import TicketConstants


class SystemAdmin(commands.Cog):
    """系統管理功能 - 簡化版"""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="admin", description="系統管理面板")
    async def admin_panel(self, interaction: discord.Interaction):
        """系統管理面板"""
        try:
            if not await self.bot.is_owner(interaction.user):
                await interaction.response.send_message(
                    "❌ 此功能僅限機器人擁有者使用", ephemeral=True
                )
                return

            from potato_bot.views.system_admin_views import SystemAdminPanel

            embed = discord.Embed(
                title="🔧 系統管理面板",
                description="選擇要執行的管理操作",
                color=0x3498DB,
            )

            embed.add_field(
                name="📊 功能模組",
                value="• 🎫 票券系統設定\n• 🎉 歡迎系統設定\n• 🗳️ 投票系統設定\n• 🎲 抽獎系統設定\n• 🎵 音樂系統設定\n• 🛂 入境審核設定\n• 🧾 履歷系統設定\n• 🛰️ FiveM 狀態設定\n• 📊 系統狀態\n• 🔧 系統工具\n• 🗂️ 類別自動建立",
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

    @app_commands.command(name="cache_control", description="快取控制（管理員專用）")
    @app_commands.describe(action="執行的動作", target="目標範圍")
    @app_commands.choices(
        action=[
            app_commands.Choice(name="清空快取", value="clear"),
            app_commands.Choice(name="預熱票券快取", value="warm_ticket"),
            app_commands.Choice(name="快取統計", value="stats"),
            app_commands.Choice(name="健康檢查", value="health"),
        ]
    )
    @app_commands.default_permissions(administrator=True)
    async def cache_control(
        self,
        interaction: discord.Interaction,
        action: str,
        target: str = "all",
    ):
        """快取控制命令"""
        try:
            await interaction.response.defer(ephemeral=True)

            if action == "clear":
                pattern = f"*{interaction.guild.id}*" if target == "guild" else "*"
                count = await cache_manager.clear_all(pattern)
                embed = EmbedBuilder.build(
                    title="🧹 快取清理完成",
                    description=f"已清理 {count} 個與 '{target}' 相關的快取條目",
                    color=TicketConstants.COLORS["success"],
                )

            elif action == "warm_ticket":
                await cached_ticket_dao.warm_cache(interaction.guild.id)
                embed = EmbedBuilder.build(
                    title="🔥 票券快取預熱完成",
                    description=f"已為伺服器 {interaction.guild.name} 預載熱點票券數據到快取",
                    color=TicketConstants.COLORS["success"],
                )

            elif action == "stats":
                stats = await cache_manager.get_statistics()
                embed = EmbedBuilder.build(
                    title="📊 快取詳細統計",
                    color=TicketConstants.COLORS["info"],
                )
                embed.add_field(
                    name="請求統計",
                    value=f"總請求：{stats['requests']['total']}\n"
                    f"命中：{stats['requests']['hits']}\n"
                    f"未命中：{stats['requests']['misses']}\n"
                    f"命中率：{stats['requests']['hit_rate']}",
                    inline=True,
                )
                l1_stats = stats.get("l1_memory", {})
                embed.add_field(
                    name="L1 記憶體快取",
                    value=f"大小：{l1_stats.get('size', 'N/A')}/{l1_stats.get('max_size', 'N/A')}\n"
                    f"使用率：{l1_stats.get('usage', 'N/A')}\n"
                    f"命中率：{l1_stats.get('hit_rate', 'N/A')}",
                    inline=True,
                )

            elif action == "health":
                health = await self._get_cache_health()
                status_colors = {
                    "healthy": TicketConstants.COLORS["success"],
                    "warning": TicketConstants.COLORS["warning"],
                    "critical": TicketConstants.COLORS["error"],
                }
                embed = EmbedBuilder.build(
                    title="🏥 快取健康檢查",
                    description=f"狀態：**{health.get('status', '未知').upper()}**",
                    color=status_colors.get(health.get("status"), TicketConstants.COLORS["secondary"]),
                )
                embed.add_field(
                    name="關鍵指標",
                    value=f"命中率：{health.get('hit_rate', 'N/A')}\n"
                    f"總請求：{health.get('total_requests', 0)}",
                    inline=True,
                )
                if recommendations := health.get("recommendations"):
                    embed.add_field(
                        name="建議",
                        value="\n".join([f"• {rec}" for rec in recommendations]),
                        inline=False,
                    )

            await interaction.followup.send(embed=embed, ephemeral=True)

        except Exception as e:
            logger.error(f"❌ 快取控制操作失敗: {e}")
            await interaction.followup.send("❌ 快取控制操作失敗。", ephemeral=True)

    async def _get_cache_health(self) -> Dict[str, Any]:
        """取得快取健康狀態"""
        try:
            stats = await cache_manager.get_statistics()

            total_requests = stats.get("requests", {}).get("total", 0)
            if total_requests < 100:
                return {
                    "status": "initializing",
                    "hit_rate": "N/A",
                    "total_requests": total_requests,
                    "recommendations": ["快取預熱中，等待收集足夠數據..."],
                }

            hit_rate_str = stats.get("requests", {}).get("hit_rate", "0.0%")
            hit_rate = float(hit_rate_str.rstrip('%')) / 100.0
            
            status = "healthy"
            if hit_rate < 0.8:
                status = "warning"
            if hit_rate < 0.6:
                status = "critical"
            
            recommendations = []
            if status == "warning":
                recommendations.append("快取命中率偏低，可考慮增加常用查詢的 TTL。")
            elif status == "critical":
                recommendations.append("快取命中率嚴重偏低，建議檢查快取策略或增加預熱。")

            l1_usage_str = stats.get("l1_memory", {}).get("usage", "0.0%")
            l1_usage = float(l1_usage_str.rstrip('%')) / 100.0
            if l1_usage > 0.9:
                recommendations.append("L1 記憶體快取接近滿載，考慮增加容量。")
            
            if not recommendations:
                recommendations.append("快取性能良好。")

            return {
                "status": status,
                "hit_rate": f"{hit_rate:.2%}",
                "total_requests": stats.get("requests", {}).get("total", 0),
                "recommendations": recommendations,
            }
        except Exception as e:
            logger.error(f"❌ 取得快取健康狀態失敗: {e}")
            return {"status": "error", "recommendations": ["無法獲取快取狀態。"]}


async def setup(bot: commands.Bot):
    cog = SystemAdmin(bot)
    await bot.add_cog(cog)
    try:
        bot.tree.remove_command("cache_control", type=discord.AppCommandType.chat_input)
    except Exception:
        pass
