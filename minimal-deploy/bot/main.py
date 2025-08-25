#!/usr/bin/env python3
"""
Potato Bot 主程式 - 精簡版
包含基本的 Discord 機器人功能
"""

import logging
import os
import sys

import discord
from discord.ext import commands

# 設置日誌
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.FileHandler("bot.log"), logging.StreamHandler()],
)
logger = logging.getLogger(__name__)


class PotatoBot(commands.Bot):
    """Potato Bot 主類別"""

    def __init__(self):
        # 設置 intents
        intents = discord.Intents.default()
        intents.message_content = True
        intents.members = True
        intents.guilds = True

        super().__init__(command_prefix="!", intents=intents, help_command=None)

        # 基本配置
        self.start_time = None

    async def setup_hook(self):
        """機器人設置"""
        logger.info("正在設置機器人...")

        # 同步 slash commands
        try:
            synced = await self.tree.sync()
            logger.info(f"同步了 {len(synced)} 個 slash commands")
        except Exception as e:
            logger.error(f"同步 slash commands 失敗: {e}")

    async def on_ready(self):
        """機器人就緒事件"""
        self.start_time = discord.utils.utcnow()
        logger.info(f"{self.user} 已上線！")
        logger.info(f"機器人 ID: {self.user.id}")
        logger.info(f"加入了 {len(self.guilds)} 個伺服器")

        # 設置機器人狀態
        await self.change_presence(
            activity=discord.Game(name="🥔 Potato Bot | /help"), status=discord.Status.online
        )

        print("Bot is ready!")  # Pterodactyl 檢測用

    async def on_guild_join(self, guild):
        """加入新伺服器事件"""
        logger.info(f"加入了新伺服器: {guild.name} (ID: {guild.id})")

    async def on_guild_remove(self, guild):
        """離開伺服器事件"""
        logger.info(f"離開了伺服器: {guild.name} (ID: {guild.id})")

    async def on_command_error(self, ctx, error):
        """指令錯誤處理"""
        if isinstance(error, commands.CommandNotFound):
            return

        logger.error(f"指令錯誤: {error}")
        await ctx.send(f"❌ 執行指令時發生錯誤: {error}")


# 創建機器人實例
bot = PotatoBot()


# 基本指令
@bot.command(name="ping")
async def ping(ctx):
    """測試機器人延遲"""
    latency = round(bot.latency * 1000)
    embed = discord.Embed(
        title="🏓 Pong!", description=f"延遲: {latency}ms", color=discord.Color.green()
    )
    await ctx.send(embed=embed)


@bot.tree.command(name="ping", description="測試機器人延遲")
async def ping_slash(interaction: discord.Interaction):
    """Slash 版本的 ping 指令"""
    latency = round(bot.latency * 1000)
    embed = discord.Embed(
        title="🏓 Pong!", description=f"延遲: {latency}ms", color=discord.Color.green()
    )
    await interaction.response.send_message(embed=embed)


@bot.tree.command(name="info", description="顯示機器人資訊")
async def info(interaction: discord.Interaction):
    """顯示機器人基本資訊"""
    embed = discord.Embed(title="🥔 Potato Bot 資訊", color=discord.Color.blue())

    embed.add_field(name="版本", value="v3.2.0-minimal", inline=True)

    embed.add_field(name="伺服器數量", value=len(bot.guilds), inline=True)

    if bot.start_time:
        uptime = discord.utils.utcnow() - bot.start_time
        hours, remainder = divmod(int(uptime.total_seconds()), 3600)
        minutes, seconds = divmod(remainder, 60)

        embed.add_field(name="運行時間", value=f"{hours}h {minutes}m {seconds}s", inline=True)

    await interaction.response.send_message(embed=embed)


@bot.tree.command(name="help", description="顯示幫助資訊")
async def help_command(interaction: discord.Interaction):
    """幫助指令"""
    embed = discord.Embed(
        title="🥔 Potato Bot 指令列表",
        description="這是精簡版的 Potato Bot，包含基本功能。",
        color=discord.Color.gold(),
    )

    embed.add_field(
        name="基本指令",
        value="`/ping` - 測試延遲\n`/info` - 機器人資訊\n`/help` - 顯示此幫助",
        inline=False,
    )

    embed.add_field(name="狀態", value="✅ 機器人運行正常\n🔧 更多功能開發中", inline=False)

    embed.set_footer(text="Potato Bot v3.2.0-minimal | 精簡版")

    await interaction.response.send_message(embed=embed)


def run_bot():
    """啟動機器人的主函數"""
    # 檢查環境變數
    token = os.getenv("DISCORD_TOKEN")
    if not token:
        logger.error("❌ 未設置 DISCORD_TOKEN 環境變數")
        sys.exit(1)

    try:
        # 啟動機器人
        logger.info("正在啟動機器人...")
        bot.run(token, log_handler=None)  # 使用自定義日誌處理器

    except discord.LoginFailure:
        logger.error("❌ Discord Token 無效")
        sys.exit(1)
    except Exception as e:
        logger.error(f"❌ 啟動失敗: {e}")
        sys.exit(1)


if __name__ == "__main__":
    run_bot()
