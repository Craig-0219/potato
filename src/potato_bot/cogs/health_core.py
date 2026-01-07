import asyncio
from typing import Dict, List

import discord
from discord.ext import commands

from potato_bot.db.pool import get_db_health
from potato_bot.utils.cog_loader import discover_cog_modules
from potato_shared.logger import logger


class HealthCore(commands.Cog):
    """基礎健康檢查與啟動狀態回報"""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.command(name="health")
    @commands.has_permissions(manage_guild=True)
    async def health(self, ctx: commands.Context):
        """檢查 Bot 健康狀態（DB、延遲、Cogs）"""
        try:
            # DB 健康檢查
            db_health = await get_db_health()
            db_status = db_health.get("status", "unknown")

            # 延遲
            latency_ms = f"{round(self.bot.latency * 1000)}ms" if self.bot.latency else "N/A"

            # Cog 狀態
            available = discover_cog_modules()
            loaded = {name.split(".")[-1] for name in self.bot.extensions.keys()}
            disabled = [c for c in available if c not in loaded]

            embed = discord.Embed(
                title="🩺 Bot 健康檢查",
                description="啟動與健康狀態摘要",
                color=discord.Color.green() if db_status == "healthy" else discord.Color.orange(),
            )

            embed.add_field(
                name="🗄️ 資料庫",
                value=f"狀態: {db_status}\n連接池: {db_health.get('pool', {})}",
                inline=False,
            )
            embed.add_field(
                name="🌐 延遲",
                value=f"WebSocket 延遲: {latency_ms}",
                inline=True,
            )
            embed.add_field(
                name="🧩 Cogs",
                value=f"已載入: {len(loaded)}\n未載入: {len(disabled)}",
                inline=True,
            )
            if disabled:
                embed.add_field(name="未載入的 Cogs", value=", ".join(disabled), inline=False)

            await ctx.send(embed=embed)
        except Exception as e:
            logger.error(f"健康檢查失敗: {e}")
            await ctx.send(f"❌ 健康檢查失敗：{e}")


async def setup(bot):
    await bot.add_cog(HealthCore(bot))
