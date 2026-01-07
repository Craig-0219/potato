import asyncio

import discord
from discord.ext import commands

from potato_bot.utils.cog_loader import (
    COGS_PREFIX,
    discover_cog_modules,
    normalize_cog_name,
)
from potato_bot.db.pool import close_database, init_database
from potato_shared.config import DB_HOST, DB_NAME, DB_PASSWORD, DB_PORT, DB_USER
from potato_shared.logger import logger
from potato_bot.db.pool import get_db_health
from potato_bot.utils.embed_builder import EmbedBuilder


class OwnerCore(commands.Cog):
    """Owner 專用管理指令（熱插拔 / 狀態 / 同步命令）"""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self._ext_lock = asyncio.Lock()

    async def _refresh_cogs(self) -> None:
        self.bot.available_cogs = discover_cog_modules()

    def _loaded_cog_names(self) -> set[str]:
        # ctx.bot.extensions keys are like: "potato_bot.cogs.xxx"
        loaded = set()
        for ext in self.bot.extensions.keys():
            if ext.startswith(COGS_PREFIX):
                loaded.add(ext[len(COGS_PREFIX):])
            else:
                loaded.add(ext.split(".")[-1])
        return loaded

    async def _safe_reply(self, ctx: commands.Context, msg: str, *, code: bool = False) -> None:
        # Discord 文字長度上限保護
        max_len = 1900 if code else 2000
        if len(msg) > max_len:
            msg = msg[:max_len] + "\n...(truncated)"
        if code:
            await ctx.send(f"```{msg}```")
        else:
            await ctx.send(msg)

    @commands.command(name="cogs")
    @commands.is_owner()
    async def list_cogs(self, ctx: commands.Context):
        """列出可用的 cogs 及載入狀態"""
        await self._refresh_cogs()

        loaded = self._loaded_cog_names()
        lines: list[str] = []

        for cog in sorted(set(self.bot.available_cogs)):
            status = "Loaded" if cog in loaded else "Disabled"
            emoji = "🟢" if status == "Loaded" else "⚪"
            lines.append(f"{emoji} {cog} - {status}")

        if not lines:
            await ctx.send("⚠️ 沒有可用的 cogs")
            return

        # 避免超長訊息（簡單截斷）
        text = "📦 Cogs:\n" + "\n".join(lines)
        if len(text) > 1800:
            text = text[:1800] + "\n...(truncated)"
        await ctx.send(text)

    @commands.command(name="load")
    @commands.is_owner()
    async def load_extension(self, ctx: commands.Context, extension_name: str):
        """載入擴展"""
        async with self._ext_lock:
            await self._refresh_cogs()
            normalized = normalize_cog_name(extension_name)

            full = COGS_PREFIX + normalized

            try:
                await ctx.bot.load_extension(full)
                await ctx.send(f"✅ 載入擴展：{normalized}")
                logger.info(f"載入擴展：{normalized}")
            except commands.ExtensionAlreadyLoaded:
                await ctx.send(f"⚠️ 已載入：{normalized}")
            except commands.ExtensionFailed as e:
                logger.exception(f"載入失敗：{full}")
                await self._safe_reply(ctx, f"❌ 載入失敗：{normalized}\n{e}", code=True)
            except Exception as e:
                logger.exception(f"載入未知錯誤：{full}")
                await self._safe_reply(ctx, f"❌ 載入錯誤：{normalized}\n{e}", code=True)

    @commands.command(name="unload")
    @commands.is_owner()
    async def unload_extension(self, ctx: commands.Context, extension_name: str):
        """卸載擴展"""
        async with self._ext_lock:
            await self._refresh_cogs()
            normalized = normalize_cog_name(extension_name)

            full = COGS_PREFIX + normalized

            try:
                await ctx.bot.unload_extension(full)
                await ctx.send(f"✅ 卸載擴展：{normalized}")
                logger.info(f"卸載擴展：{normalized}")
            except commands.ExtensionNotLoaded:
                await ctx.send(f"⚠️ 未載入：{normalized}")
            except Exception as e:
                logger.exception(f"卸載錯誤：{full}")
                await self._safe_reply(ctx, f"❌ 卸載錯誤：{normalized}\n{e}", code=True)

    @commands.command(name="reload")
    @commands.is_owner()
    async def reload_extension(self, ctx: commands.Context, extension_name: str):
        """重新載入擴展（熱插拔核心之一）"""
        async with self._ext_lock:
            await self._refresh_cogs()
            normalized = normalize_cog_name(extension_name)

            full = COGS_PREFIX + normalized

            try:
                await ctx.bot.reload_extension(full)
                await ctx.send(f"✅ 重新載入擴展：{normalized}")
                logger.info(f"重新載入擴展：{normalized}")
            except commands.ExtensionNotLoaded:
                await ctx.send(f"⚠️ 未載入：{normalized}（你要不要先 !load {normalized}）")
            except commands.ExtensionFailed as e:
                logger.exception(f"重載失敗：{full}")
                await self._safe_reply(ctx, f"❌ 重載失敗：{normalized}\n{e}", code=True)
            except Exception as e:
                logger.exception(f"重載未知錯誤：{full}")
                await self._safe_reply(ctx, f"❌ 重載錯誤：{normalized}\n{e}", code=True)

    @commands.command(name="sync")
    @commands.is_owner()
    async def sync_commands_cmd(self, ctx: commands.Context, scope: str | None = None):
        """
        手動同步斜線命令
        用法：
        - !sync           -> 只同步當前 guild（預設避免 429）
        - !sync here      -> 同上，guild sync
        - !sync global    -> 全域 sync（可能 429，請謹慎使用）
        """
        try:
            if scope != "global":
                if not ctx.guild:
                    await ctx.send("⚠️ 這個模式只能在伺服器頻道使用：!sync 或 !sync here")
                    return
                synced = await ctx.bot.tree.sync(guild=discord.Object(id=ctx.guild.id))
                await ctx.send(f"✅ 已同步（Guild {ctx.guild.id}）{len(synced)} 個命令")
                logger.info(f"Guild sync {ctx.guild.id}: {len(synced)}")
            else:
                synced = await ctx.bot.tree.sync()
                await ctx.send(f"✅ 已同步（Global）{len(synced)} 個命令")
                logger.info(f"Global sync: {len(synced)}")

        except Exception as e:
            logger.exception("sync 失敗")
            await self._safe_reply(ctx, f"❌ 同步失敗：{e}", code=True)

    @commands.command(name="status")
    @commands.is_owner()
    async def status_command(self, ctx: commands.Context):
        """Bot 平台級狀態（Infra + Cogs）"""
        try:
            db_health = await get_db_health()
        except Exception as e:
            logger.error(f"取得 DB 健康失敗: {e}")
            db_health = {"status": "unknown", "pool": {}}

        ext_list = ", ".join([ext.split(".")[-1] for ext in ctx.bot.extensions])
        if len(ext_list) > 900:
            ext_list = ext_list[:900] + " ..."

        embed = EmbedBuilder.status_embed(
            {
                "overall_status": (
                    "healthy" if db_health.get("status") == "healthy" else "degraded"
                ),
                "基本資訊": {
                    "伺服器數量": len(ctx.bot.guilds),
                    "延遲": (
                        f"{round(ctx.bot.latency * 1000)}ms"
                        if ctx.bot.latency is not None
                        else "N/A"
                    ),
                    "運行時間": ctx.bot.get_uptime(),
                },
                "資料庫": {
                    "狀態": db_health.get("status", "unknown"),
                    "連接池": f"{db_health.get('pool', {}).get('free', 0)} 可用",
                },
                "擴展": {
                    "已載入": len(ctx.bot.extensions),
                    "列表": ext_list,
                },
            }
        )

        if getattr(ctx.bot, "error_handler", None):
            stats = ctx.bot.error_handler.get_error_stats()
            if stats.get("total_errors", 0) > 0:
                embed.add_field(
                    name="錯誤統計",
                    value=(
                        f"總錯誤數：{stats['total_errors']}\n"
                        f"前三錯誤：{', '.join(list(stats['top_errors'].keys())[:3])}"
                    ),
                    inline=False,
                )

        await ctx.send(embed=embed)

    @commands.command(name="restart")
    @commands.is_owner()
    async def restart_bot(self, ctx: commands.Context):
        """重新載入所有已載入的擴展並重連資料庫，保持 Bot 在線"""
        async with self._ext_lock:
            await self._refresh_cogs()

            # 先重連資料庫
            await ctx.send("🔄 正在重連資料庫並重新載入模組，請稍候...")
            try:
                await close_database()
                await init_database(DB_HOST, DB_PORT, DB_USER, DB_PASSWORD, DB_NAME)
                logger.info("✅ restart: 資料庫已重連")
            except Exception as e:
                logger.exception("restart: 重連資料庫失敗")
                await self._safe_reply(ctx, f"❌ 資料庫重連失敗：{e}")
                return

            extensions = [
                ext for ext in ctx.bot.extensions.keys() if ext.startswith(COGS_PREFIX)
            ]

            if not extensions:
                await ctx.send("ℹ️ 目前沒有已載入的擴展可重載（資料庫已重連）")
                return

            await ctx.send("🔄 資料庫已重連，正在重新載入所有模組（不中斷連線）...")
            failures: list[str] = []

            for ext in extensions:
                try:
                    await ctx.bot.reload_extension(ext)
                    logger.info(f"重載模組：{ext}")
                except Exception as e:
                    failures.append(f"{ext}: {e}")
                    logger.exception(f"重載模組失敗：{ext}")

            if failures:
                message = "⚠️ 部分模組重載失敗：\n" + "\n".join(failures[:5])
                if len(failures) > 5:
                    message += f"\n... 其餘 {len(failures) - 5} 項略過"
                await self._safe_reply(ctx, message)
            else:
                await ctx.send(f"✅ 已重新載入 {len(extensions)} 個模組，Bot 持續在線")


async def setup(bot: commands.Bot):
    await bot.add_cog(OwnerCore(bot))
