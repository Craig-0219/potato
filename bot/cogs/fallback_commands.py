"""
備用前綴命令 - 當斜線命令不可用時使用
用於解決 Discord API 速率限制問題
"""

import logging

import discord
from discord.ext import commands

logger = logging.getLogger(__name__)


class FallbackCommands(commands.Cog):
    """備用命令系統"""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        logger.info("🔄 備用命令系統已載入")

    @commands.command(name="menu", aliases=["m"])
    async def menu_fallback(self, ctx):
        """開啟主選單 (備用命令)"""
        try:
            # 檢查是否有 menu_core cog
            menu_cog = self.bot.get_cog("MenuCore")
            if menu_cog:
                # 創建假的 interaction 來使用現有的 menu 系統
                from bot.ui.menu_system import MenuSystemManager

                embed = discord.Embed(
                    title="🏠 Potato Bot 主選單",
                    description="歡迎使用 Potato Bot！\n由於技術限制，目前使用備用模式。",
                    color=0x00FF88,
                )

                embed.add_field(
                    name="📋 可用功能",
                    value=(
                        "• `!ticket` - 開啟票券系統\n"
                        "• `!vote` - 開啟投票系統\n"
                        "• `!welcome` - 設定歡迎系統\n"
                        "• `!ai` - AI 助手\n"
                        "• `!status` - 系統狀態"
                    ),
                    inline=False,
                )

                embed.add_field(
                    name="ℹ️ 說明", value="斜線命令暫時不可用，請使用上述前綴命令。", inline=False
                )

                await ctx.send(embed=embed)
            else:
                await ctx.send("❌ 選單系統暫時不可用")

        except Exception as e:
            logger.error(f"備用選單命令錯誤: {e}")
            await ctx.send("❌ 選單載入失敗")

    @commands.command(name="ticket", aliases=["t"])
    async def ticket_fallback(self, ctx):
        """票券系統 (備用命令)"""
        try:
            ticket_cog = self.bot.get_cog("TicketCore")
            if ticket_cog:
                embed = discord.Embed(
                    title="🎫 票券系統", description="票券系統功能", color=0x3498DB
                )
                embed.add_field(
                    name="可用指令",
                    value=(
                        "• `!ticket create` - 建立新票券\n"
                        "• `!ticket list` - 我的票券列表\n"
                        "• `!ticket close` - 關閉當前票券"
                    ),
                    inline=False,
                )
                await ctx.send(embed=embed)
            else:
                await ctx.send("❌ 票券系統暫時不可用")
        except Exception as e:
            logger.error(f"備用票券命令錯誤: {e}")
            await ctx.send("❌ 票券系統錯誤")

    @commands.command(name="vote", aliases=["v"])
    async def vote_fallback(self, ctx):
        """投票系統 (備用命令)"""
        try:
            vote_cog = self.bot.get_cog("VoteCore")
            if vote_cog:
                embed = discord.Embed(
                    title="🗳️ 投票系統", description="投票系統功能", color=0xE74C3C
                )
                embed.add_field(
                    name="可用指令",
                    value=(
                        "• `!vote create` - 建立新投票\n"
                        "• `!vote list` - 查看活躍投票\n"
                        "• `!vote stats` - 投票統計"
                    ),
                    inline=False,
                )
                await ctx.send(embed=embed)
            else:
                await ctx.send("❌ 投票系統暫時不可用")
        except Exception as e:
            logger.error(f"備用投票命令錯誤: {e}")
            await ctx.send("❌ 投票系統錯誤")

    @commands.command(name="welcome_menu", aliases=["wm"])
    async def welcome_fallback(self, ctx):
        """歡迎系統 (備用命令)"""
        try:
            welcome_cog = self.bot.get_cog("WelcomeCore")
            if welcome_cog:
                embed = discord.Embed(
                    title="👋 歡迎系統", description="歡迎系統設定", color=0xF39C12
                )
                embed.add_field(
                    name="可用指令",
                    value=(
                        "• `!welcome setup` - 設定歡迎系統\n"
                        "• `!welcome test` - 測試歡迎訊息\n"
                        "• `!welcome toggle` - 開啟/關閉"
                    ),
                    inline=False,
                )
                await ctx.send(embed=embed)
            else:
                await ctx.send("❌ 歡迎系統暫時不可用")
        except Exception as e:
            logger.error(f"備用歡迎命令錯誤: {e}")
            await ctx.send("❌ 歡迎系統錯誤")

    @commands.command(name="ai", aliases=["ask"])
    async def ai_fallback(self, ctx, *, question=None):
        """AI 助手 (備用命令)"""
        if not question:
            embed = discord.Embed(
                title="🤖 AI 智能助手", description="使用方式：`!ai <你的問題>`", color=0x9B59B6
            )
            embed.add_field(name="範例", value="`!ai 你好` 或 `!ask 天氣如何`", inline=False)
            await ctx.send(embed=embed)
            return

        try:
            ai_cog = self.bot.get_cog("AIAssistantCore")
            if ai_cog:
                # 簡化的 AI 回應
                response = f"🤖 收到您的問題：{question}\n\n由於目前使用備用模式，AI 功能受限。請稍後使用完整的 `/ai` 命令。"
                await ctx.send(response)
            else:
                await ctx.send("❌ AI 助手暫時不可用")
        except Exception as e:
            logger.error(f"備用 AI 命令錯誤: {e}")
            await ctx.send("❌ AI 助手錯誤")

    @commands.command(name="status", aliases=["info"])
    async def status_fallback(self, ctx):
        """系統狀態 (備用命令)"""
        try:
            embed = discord.Embed(
                title="📊 系統狀態", description="Potato Bot 運行狀態", color=0x2ECC71
            )

            embed.add_field(name="🤖 Bot 狀態", value="✅ 運行正常", inline=True)

            embed.add_field(
                name="📡 延遲", value=f"{round(self.bot.latency * 1000)}ms", inline=True
            )

            embed.add_field(name="🏛️ 伺服器數", value=f"{len(self.bot.guilds)}", inline=True)

            embed.add_field(
                name="⚠️ 注意事項", value="目前使用備用命令模式\n斜線命令暫時不可用", inline=False
            )

            await ctx.send(embed=embed)

        except Exception as e:
            logger.error(f"備用狀態命令錯誤: {e}")
            await ctx.send("❌ 狀態查詢錯誤")

    @commands.command(name="guide")
    async def help_fallback(self, ctx):
        """說明 (備用命令)"""
        embed = discord.Embed(
            title="📚 Potato Bot 說明",
            description="備用命令列表 (斜線命令暫時不可用)",
            color=0x34495E,
        )

        embed.add_field(
            name="🏠 主要功能",
            value=(
                "`!menu` - 主選單\n"
                "`!ticket` - 票券系統\n"
                "`!vote` - 投票系統\n"
                "`!welcome_menu` - 歡迎系統\n"
                "`!ai <問題>` - AI 助手"
            ),
            inline=True,
        )

        embed.add_field(
            name="ℹ️ 系統功能",
            value=("`!status` - 系統狀態\n" "`!guide` - 說明頁面\n" "`!sync` - 同步命令 (管理員)"),
            inline=True,
        )

        embed.add_field(
            name="📝 說明",
            value=(
                "由於 Discord API 速率限制，\n"
                "斜線命令暫時不可用。\n"
                "請使用上述前綴命令作為替代。"
            ),
            inline=False,
        )

        await ctx.send(embed=embed)


async def setup(bot):
    await bot.add_cog(FallbackCommands(bot))
