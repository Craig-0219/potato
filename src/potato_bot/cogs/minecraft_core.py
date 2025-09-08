from datetime import datetime

import discord
from discord.ext import commands, tasks

from potato_bot.services.minecraft.chat_bridge import ChatBridge
from potato_bot.services.minecraft.mc_server_api import MinecraftServerAPI
from potato_bot.services.minecraft.player_manager import PlayerManager
from potato_bot.services.minecraft.rcon_manager import RCONManager
from potato_shared.config import MINECRAFT_NOTIFICATION_CHANNEL
from potato_shared.logger import logger


class MinecraftCore(commands.Cog):
    """Minecraft Server 核心整合功能"""

    def __init__(self, bot):
        self.bot = bot
        self.server_api = MinecraftServerAPI()
        self.player_manager = PlayerManager(bot)
        self.rcon_manager = RCONManager()
        self.chat_bridge = ChatBridge(bot, self.rcon_manager)

        # 伺服器狀態快取
        self.server_status = {
            "online": False,
            "players": 0,
            "max_players": 20,
            "version": "",
            "motd": "",
            "last_update": None,
        }

        # 玩家活動快取
        self.player_cache = {}

        # 初始化標記
        self._initialized = False

        # 啟動背景任務
        self.server_monitor.start()
        self.player_activity_tracker.start()

    def cog_unload(self):
        """停用 Cog 時清理資源"""
        self.server_monitor.cancel()
        self.player_activity_tracker.cancel()

    @tasks.loop(minutes=1)
    async def server_monitor(self):
        """每分鐘監控伺服器狀態"""
        try:
            status = await self.server_api.get_server_status()
            if status:
                self.server_status.update(status)
                self.server_status["last_update"] = datetime.now()

                # 如果伺服器狀態變化，發送通知
                await self._check_server_status_changes(status)

        except Exception as e:
            logger.error(f"伺服器監控錯誤: {e}")

    @tasks.loop(minutes=5)
    async def player_activity_tracker(self):
        """追蹤玩家活動"""
        try:
            if self.server_status["online"]:
                players = await self.server_api.get_online_players()
                await self.player_manager.update_player_activity(players)

        except Exception as e:
            logger.error(f"玩家活動追蹤錯誤: {e}")

    @server_monitor.before_loop
    async def before_server_monitor(self):
        await self.bot.wait_until_ready()

        # 初始化 PlayerManager
        if not self._initialized:
            await self.player_manager.initialize()
            self._initialized = True

    @player_activity_tracker.before_loop
    async def before_player_activity_tracker(self):
        await self.bot.wait_until_ready()

    # =============================================================================
    # Discord 斜線指令
    # =============================================================================

    @commands.slash_command(name="mc-status", description="查看 Minecraft 伺服器狀態")
    async def minecraft_status(self, ctx):
        """顯示 Minecraft 伺服器狀態"""
        try:
            await ctx.defer()

            # 獲取最新狀態
            status = await self.server_api.get_server_status()
            if not status:
                embed = discord.Embed(
                    title="🔴 Minecraft 伺服器狀態",
                    description="無法連接到伺服器",
                    color=0xFF0000,
                )
                await ctx.followup.send(embed=embed)
                return

            # 建立狀態嵌入訊息
            embed = discord.Embed(
                title=(
                    "🟢 Minecraft 伺服器狀態" if status["online"] else "🔴 Minecraft 伺服器狀態"
                ),
                color=0x00FF00 if status["online"] else 0xFF0000,
            )

            if status["online"]:
                embed.add_field(
                    name="📊 基本資訊",
                    value=f"""
                    **狀態**: 🟢 在線
                    **玩家**: {status['players']}/{status['max_players']}
                    **版本**: {status.get('version', 'Unknown')}
                    **延遲**: {status.get('ping', 'N/A')}ms
                    """,
                    inline=False,
                )

                embed.add_field(
                    name="💬 伺服器描述",
                    value=f"```{status.get('motd', '歡迎來到我們的 Minecraft 伺服器！')}```",
                    inline=False,
                )

                # 獲取在線玩家列表
                if status["players"] > 0:
                    online_players = await self.server_api.get_online_players()
                    if online_players:
                        player_list = ", ".join([p["name"] for p in online_players[:10]])
                        if len(online_players) > 10:
                            player_list += f" 和其他 {len(online_players) - 10} 位玩家"

                        embed.add_field(name="👥 在線玩家", value=player_list, inline=False)

                # 伺服器效能資訊
                performance = await self.server_api.get_server_performance()
                if performance:
                    embed.add_field(
                        name="⚡ 伺服器效能",
                        value=f"""
                        **TPS**: {performance.get('tps', 'N/A')}/20.0
                        **記憶體**: {performance.get('memory_used', 0)}/{performance.get('memory_max', 0)}MB
                        **CPU**: {performance.get('cpu_usage', 'N/A')}%
                        """,
                        inline=True,
                    )
            else:
                embed.add_field(
                    name="❌ 伺服器離線",
                    value="伺服器目前不在線，請稍後再試",
                    inline=False,
                )

            embed.timestamp = datetime.now()
            embed.set_footer(text="最後更新")

            await ctx.followup.send(embed=embed)

        except Exception as e:
            logger.error(f"minecraft_status 指令錯誤: {e}")
            embed = discord.Embed(
                title="❌ 錯誤",
                description="無法獲取伺服器狀態，請稍後再試",
                color=0xFF0000,
            )
            await ctx.followup.send(embed=embed)

    @commands.slash_command(name="mc-players", description="查看在線玩家詳細資訊")
    async def minecraft_players(self, ctx):
        """顯示詳細的在線玩家資訊"""
        try:
            await ctx.defer()

            players = await self.server_api.get_online_players_detailed()
            if not players:
                embed = discord.Embed(
                    title="👥 在線玩家",
                    description="目前沒有玩家在線",
                    color=0xFFFF00,
                )
                await ctx.followup.send(embed=embed)
                return

            embed = discord.Embed(title=f"👥 在線玩家 ({len(players)})", color=0x00FF00)

            for player in players:
                player_info = f"""
                **遊戲時間**: {player.get('playtime', 'N/A')}
                **位置**: {player.get('location', 'Unknown')}
                **等級**: {player.get('level', 0)}
                **血量**: {player.get('health', 20)}/20 ❤️
                """

                embed.add_field(name=f"🎮 {player['name']}", value=player_info, inline=True)

            embed.timestamp = datetime.now()
            await ctx.followup.send(embed=embed)

        except Exception as e:
            logger.error(f"minecraft_players 指令錯誤: {e}")
            await ctx.followup.send("❌ 無法獲取玩家資訊")

    @commands.slash_command(name="mc-bind", description="綁定您的 Discord 帳號到 Minecraft 玩家")
    async def bind_minecraft(self, ctx, minecraft_username: str):
        """綁定 Discord 用戶到 Minecraft 玩家"""
        try:
            await ctx.defer()

            # 驗證 Minecraft 用戶名
            player_data = await self.server_api.get_player_info(minecraft_username)
            if not player_data:
                embed = discord.Embed(
                    title="❌ 綁定失敗",
                    description=f"找不到 Minecraft 玩家 `{minecraft_username}`",
                    color=0xFF0000,
                )
                await ctx.followup.send(embed=embed)
                return

            # 執行綁定
            success = await self.player_manager.bind_player(
                discord_id=ctx.author.id,
                minecraft_uuid=player_data["uuid"],
                minecraft_username=player_data["name"],
            )

            if success:
                embed = discord.Embed(
                    title="✅ 綁定成功",
                    description=f"已成功綁定到 Minecraft 玩家 `{player_data['name']}`",
                    color=0x00FF00,
                )
                embed.add_field(
                    name="🎮 玩家資訊",
                    value=f"""
                    **Minecraft 用戶名**: {player_data['name']}
                    **UUID**: `{player_data['uuid']}`
                    **Discord**: {ctx.author.mention}
                    """,
                    inline=False,
                )
            else:
                embed = discord.Embed(
                    title="❌ 綁定失敗",
                    description="該 Discord 帳號已綁定其他 Minecraft 玩家，或該 Minecraft 玩家已被其他人綁定",
                    color=0xFF0000,
                )

            await ctx.followup.send(embed=embed)

        except Exception as e:
            logger.error(f"bind_minecraft 指令錯誤: {e}")
            await ctx.followup.send("❌ 綁定過程中發生錯誤")

    @commands.slash_command(name="mc-cmd", description="執行 Minecraft 伺服器指令 (需要管理員權限)")
    @commands.has_permissions(administrator=True)
    async def minecraft_command(self, ctx, command: str):
        """執行 Minecraft 伺服器指令"""
        try:
            await ctx.defer()

            # 執行 RCON 指令
            result = await self.rcon_manager.execute_command(command)

            embed = discord.Embed(
                title="🎮 Minecraft 指令執行",
                color=0x00FF00 if result["success"] else 0xFF0000,
            )

            embed.add_field(name="📝 執行指令", value=f"`/{command}`", inline=False)

            if result["success"]:
                embed.add_field(
                    name="✅ 執行結果",
                    value=(
                        f"```\n{result['response'][:1000]}\n```"
                        if result["response"]
                        else "指令執行成功"
                    ),
                    inline=False,
                )
            else:
                embed.add_field(
                    name="❌ 執行失敗",
                    value=f"```\n{result['error']}\n```",
                    inline=False,
                )

            embed.set_footer(text=f"執行者: {ctx.author.display_name}")
            embed.timestamp = datetime.now()

            await ctx.followup.send(embed=embed)

            # 記錄管理操作
            logger.info(f"管理員 {ctx.author.display_name} 執行 MC 指令: /{command}")

        except Exception as e:
            logger.error(f"minecraft_command 指令錯誤: {e}")
            await ctx.followup.send("❌ 指令執行失敗")

    @commands.slash_command(name="mc-whitelist", description="管理白名單 (需要管理員權限)")
    @commands.has_permissions(administrator=True)
    async def whitelist_management(
        self,
        ctx,
        action: discord.Option(str, choices=["add", "remove", "list"]),
        player: str = None,
    ):
        """管理 Minecraft 伺服器白名單"""
        try:
            await ctx.defer()

            if action == "list":
                whitelist = await self.rcon_manager.get_whitelist()
                if whitelist:
                    embed = discord.Embed(
                        title="📋 白名單玩家",
                        description="\n".join([f"• {player}" for player in whitelist]),
                        color=0x0099FF,
                    )
                else:
                    embed = discord.Embed(
                        title="📋 白名單玩家",
                        description="白名單為空",
                        color=0xFFFF00,
                    )

                await ctx.followup.send(embed=embed)
                return

            if not player:
                await ctx.followup.send("❌ 請提供玩家名稱")
                return

            if action == "add":
                result = await self.rcon_manager.execute_command(f"whitelist add {player}")
                title = (
                    f"✅ 已將 {player} 加入白名單"
                    if result["success"]
                    else f"❌ 無法將 {player} 加入白名單"
                )
            elif action == "remove":
                result = await self.rcon_manager.execute_command(f"whitelist remove {player}")
                title = (
                    f"✅ 已將 {player} 從白名單移除"
                    if result["success"]
                    else f"❌ 無法將 {player} 從白名單移除"
                )

            embed = discord.Embed(title=title, color=0x00FF00 if result["success"] else 0xFF0000)

            if result["response"]:
                embed.add_field(
                    name="回應",
                    value=f"```{result['response']}```",
                    inline=False,
                )

            await ctx.followup.send(embed=embed)

        except Exception as e:
            logger.error(f"whitelist_management 指令錯誤: {e}")
            await ctx.followup.send("❌ 白名單操作失敗")

    @commands.slash_command(
        name="mc-chat-bridge",
        description="設置 Discord ↔ Minecraft 聊天橋接 (需要管理員權限)",
    )
    @commands.has_permissions(administrator=True)
    async def chat_bridge_control(
        self,
        ctx,
        action: discord.Option(str, choices=["enable", "disable", "status"]),
    ):
        """控制聊天橋接功能"""
        try:
            await ctx.defer()

            if action == "enable":
                # 啟用聊天橋接到當前頻道
                result = self.chat_bridge.enable_bridge(ctx.channel.id)

                embed = discord.Embed(
                    title="🌉 聊天橋接" + ("已啟用" if result else "啟用失敗"),
                    color=0x00FF00 if result else 0xFF0000,
                )

                if result:
                    embed.description = (
                        f"已在 {ctx.channel.mention} 啟用 Discord ↔ Minecraft 聊天橋接"
                    )
                    embed.add_field(
                        name="使用說明",
                        value="""
                        • 在此頻道發送的訊息會同步到 Minecraft 伺服器
                        • Minecraft 玩家的聊天會同步到此頻道
                        • 機器人訊息和指令會自動過濾
                        """,
                        inline=False,
                    )
                else:
                    embed.description = "聊天橋接啟用失敗，請檢查 RCON 連線設定"

            elif action == "disable":
                self.chat_bridge.disable_bridge()

                embed = discord.Embed(
                    title="🌉 聊天橋接已停用",
                    description="Discord ↔ Minecraft 聊天橋接已停用",
                    color=0xFFFF00,
                )

            elif action == "status":
                status = self.chat_bridge.get_bridge_status()

                embed = discord.Embed(
                    title="🌉 聊天橋接狀態",
                    color=0x00FF00 if status["enabled"] else 0xFFFF00,
                )

                embed.add_field(
                    name="狀態",
                    value="🟢 已啟用" if status["enabled"] else "🟡 已停用",
                    inline=True,
                )

                if status["enabled"] and status["discord_channel_id"]:
                    channel = self.bot.get_channel(status["discord_channel_id"])
                    embed.add_field(
                        name="橋接頻道",
                        value=(
                            channel.mention if channel else f"ID: {status['discord_channel_id']}"
                        ),
                        inline=True,
                    )

                embed.add_field(
                    name="聊天過濾",
                    value=("🟢 已啟用" if status["chat_filter_enabled"] else "🔴 已停用"),
                    inline=True,
                )

            await ctx.followup.send(embed=embed)

        except Exception as e:
            logger.error(f"chat_bridge_control 指令錯誤: {e}")
            await ctx.followup.send("❌ 聊天橋接操作失敗")

    @commands.Cog.listener()
    async def on_message(self, message):
        """監聽 Discord 訊息以進行聊天橋接"""
        try:
            # 讓聊天橋接處理訊息
            await self.chat_bridge.handle_discord_message(message)

        except Exception as e:
            logger.error(f"聊天橋接訊息處理錯誤: {e}")

    # =============================================================================
    # 內部輔助方法
    # =============================================================================

    async def _check_server_status_changes(self, new_status):
        """檢查伺服器狀態變化並發送通知"""
        try:
            old_online = self.server_status.get("online", False)
            new_online = new_status.get("online", False)

            # 伺服器上線/離線通知
            if old_online != new_online:
                embed = discord.Embed(
                    title="🎮 Minecraft 伺服器狀態變化",
                    color=0x00FF00 if new_online else 0xFF0000,
                )

                if new_online:
                    embed.description = "✅ 伺服器已上線！"
                    embed.add_field(
                        name="伺服器資訊",
                        value=f"**玩家**: {new_status['players']}/{new_status['max_players']}\n**版本**: {new_status.get('version', 'Unknown')}",
                        inline=False,
                    )
                else:
                    embed.description = "❌ 伺服器已離線"

                embed.timestamp = datetime.now()

                # 發送到指定頻道 (需要在配置中設定)
                if MINECRAFT_NOTIFICATION_CHANNEL:
                    try:
                        channel_id = int(MINECRAFT_NOTIFICATION_CHANNEL)
                        channel = self.bot.get_channel(channel_id)
                        if channel:
                            await channel.send(embed=embed)
                    except (ValueError, TypeError):
                        logger.error(f"無效的 Discord 頻道 ID: {MINECRAFT_NOTIFICATION_CHANNEL}")

        except Exception as e:
            logger.error(f"伺服器狀態變化通知錯誤: {e}")


def setup(bot):
    bot.add_cog(MinecraftCore(bot))
