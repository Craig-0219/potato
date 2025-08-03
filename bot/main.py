# bot/main.py - 專業重構版
"""
Discord Bot 主程式 - 專業修正版
支援票券/投票多模組，自動載入、指令熱更新、資料庫健康檢查
"""
import os
import sys
import asyncio
import discord
from discord.ext import commands
from dotenv import load_dotenv

# 路徑校正（確保可本地、主機啟動）
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# logger fallback
try:
    from shared.logger import logger
except ImportError:
    import logging
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger("potato-bot")

# config fallback
try:
    from shared.config import (
        DISCORD_TOKEN, DB_HOST, DB_PORT, DB_USER, DB_PASSWORD, DB_NAME
    )
except ImportError:
    logger.error("❌ shared/config.py 不存在或設定不齊全")
    sys.exit(1)

from bot.db.pool import init_database, close_database, get_db_health
from bot.views.ticket_views import TicketPanelView, RatingView, TicketControlView
from bot.register.register import register_all_views

COGS_PREFIX = "bot.cogs."
ALL_EXTENSIONS = [
    "ticket_core",
    "ticket_listener",
    "vote",
    "vote_listener"
]

class PotatoBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.guilds = True
        intents.guild_messages = True
        intents.dm_messages = True

        super().__init__(
            command_prefix=commands.when_mentioned_or('!'),
            intents=intents,
            description="Potato Bot - 票券系統與投票系統"
        )
        self.initial_extensions = [COGS_PREFIX + ext for ext in ALL_EXTENSIONS]

    async def setup_hook(self):
        logger.info("Bot 設定開始...")

        # 初始化資料庫
        try:
            await init_database(DB_HOST, DB_PORT, DB_USER, DB_PASSWORD, DB_NAME)
            logger.info("資料庫連接成功")
        except Exception as e:
            logger.error(f"資料庫連接失敗：{e}")
            raise

        # 載入擴展
        for extension in self.initial_extensions:
            try:
                await self.load_extension(extension)
                logger.info(f"載入擴展：{extension}")
            except Exception as e:
                logger.error(f"載入擴展 {extension} 失敗：{e}")

        # 同步命令樹
        try:
            synced = await self.tree.sync()
            logger.info(f"同步了 {len(synced)} 個斜線命令")
        except Exception as e:
            logger.error(f"同步命令失敗：{e}")

        register_all_views(self)  # Persistent Views 註冊

    async def on_ready(self):
        logger.info(f"Bot 已登入：{self.user} (ID: {self.user.id})")
        logger.info(f"已連接到 {len(self.guilds)} 個伺服器")
        activity = discord.Activity(
            type=discord.ActivityType.watching,
            name="票券系統 | /help"
        )
        await self.change_presence(activity=activity)

    async def on_guild_join(self, guild):
        logger.info(f"加入新伺服器：{guild.name} (ID: {guild.id})")
        try:
            from bot.db.ticket_dao import TicketDAO
            repository = TicketDAO()
            await repository.create_default_settings(guild.id)
        except Exception as e:
            logger.error(f"初始化伺服器設定失敗：{e}")

    async def on_guild_remove(self, guild):
        logger.info(f"離開伺服器：{guild.name} (ID: {guild.id})")

    async def on_command_error(self, ctx, error):
        if isinstance(error, commands.CommandNotFound):
            return
        if isinstance(error, commands.MissingPermissions):
            await ctx.send("❌ 你沒有權限使用此命令。")
            return
        if isinstance(error, commands.MissingRequiredArgument):
            await ctx.send(f"❌ 缺少必要參數：{error.param}")
            return
        logger.error(f"命令錯誤：{error}")
        await ctx.send("❌ 執行命令時發生錯誤。")

    async def on_error(self, event, *args, **kwargs):
        logger.error(f"事件 {event} 發生錯誤", exc_info=True)

    async def close(self):
        logger.info("Bot 正在關閉...")
        try:
            await close_database()
            logger.info("資料庫連接已關閉")
        except Exception as e:
            logger.error(f"關閉資料庫連接錯誤：{e}")
        await super().close()


# ===== 管理指令 =====

@commands.command(name='reload')
@commands.is_owner()
async def reload_extension(ctx, extension_name: str):
    try:
        await ctx.bot.reload_extension(COGS_PREFIX + extension_name)
        await ctx.send(f"✅ 重新載入擴展：{extension_name}")
    except Exception as e:
        await ctx.send(f"❌ 重新載入失敗：{e}")

@commands.command(name='load')
@commands.is_owner()
async def load_extension(ctx, extension_name: str):
    try:
        await ctx.bot.load_extension(COGS_PREFIX + extension_name)
        await ctx.send(f"✅ 載入擴展：{extension_name}")
    except Exception as e:
        await ctx.send(f"❌ 載入失敗：{e}")

@commands.command(name='unload')
@commands.is_owner()
async def unload_extension(ctx, extension_name: str):
    try:
        await ctx.bot.unload_extension(COGS_PREFIX + extension_name)
        await ctx.send(f"✅ 卸載擴展：{extension_name}")
    except Exception as e:
        await ctx.send(f"❌ 卸載失敗：{e}")

@commands.command(name='sync')
@commands.is_owner()
async def sync_commands(ctx):
    try:
        synced = await ctx.bot.tree.sync()
        await ctx.send(f"✅ 同步了 {len(synced)} 個命令")
    except Exception as e:
        await ctx.send(f"❌ 同步失敗：{e}")

@commands.command(name='status')
@commands.is_owner()
async def bot_status(ctx):
    # 依你的 pool.py 定義，如無請另外寫 get_db_health
    from bot.db.pool import get_db_health

    try:
        db_health = await get_db_health()
        embed = discord.Embed(
            title="🤖 Bot 狀態",
            color=discord.Color.blue()
        )
        embed.add_field(
            name="🔧 基本資訊",
            value=f"**伺服器數量：** {len(ctx.bot.guilds)}\n"
                  f"**延遲：** {round(ctx.bot.latency * 1000)}ms\n"
                  f"**Python：** {sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
            inline=True
        )
        db_status = db_health.get('overall_status', 'unknown')
        db_emoji = "✅" if db_status == 'healthy' else "❌"
        embed.add_field(
            name="🗄️ 資料庫",
            value=f"**狀態：** {db_emoji} {db_status}\n"
                  f"**大小：** {db_health.get('database', {}).get('size_mb', 0)} MB",
            inline=True
        )
        extensions = []
        for ext_name in ctx.bot.extensions:
            extensions.append(f"✅ {ext_name.split('.')[-1]}")
        if extensions:
            embed.add_field(
                name="📦 已載入擴展",
                value="\n".join(extensions),
                inline=False
            )
        await ctx.send(embed=embed)
    except Exception as e:
        await ctx.send(f"❌ 取得狀態失敗：{e}")

# ===== 主函數 =====

async def main():
    load_dotenv()
    if not DISCORD_TOKEN:
        logger.error("未找到 DISCORD_TOKEN，請檢查 .env 設定")
        sys.exit(1)

    bot = PotatoBot()
    bot.add_command(reload_extension)
    bot.add_command(load_extension)
    bot.add_command(unload_extension)
    bot.add_command(sync_commands)
    bot.add_command(bot_status)

    async with bot:
        try:
            await bot.start(DISCORD_TOKEN)
        except KeyboardInterrupt:
            logger.info("收到中斷信號，正在關閉...")
        except Exception as e:
            logger.error(f"Bot 運行錯誤：{e}")
        finally:
            if not bot.is_closed():
                await bot.close()


if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("程式已終止")
    except Exception as e:
        logger.error(f"程式執行錯誤：{e}")
        sys.exit(1)
