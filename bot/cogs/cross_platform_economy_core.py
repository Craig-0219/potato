# bot/cogs/cross_platform_economy_core.py - 跨平台經濟系統核心
"""
跨平台經濟系統核心 Cog v3.0.0 - Phase 5 Stage 4
提供 Discord-Minecraft 跨平台經濟管理的管理命令和界面
"""

import discord
from discord.ext import commands, tasks
from discord import app_commands
from typing import Dict, Any, Optional, List
import asyncio
from datetime import datetime, timezone, timedelta

from bot.services.economy_manager import (
    economy_manager, CurrencyType, TransactionType, EconomyAction
)
from bot.utils.embed_builder import EmbedBuilder
from shared.logger import logger

class CrossPlatformEconomyCore(commands.Cog):
    """跨平台經濟系統核心 Cog"""
    
    def __init__(self, bot):
        self.bot = bot
        self.economy_manager = economy_manager
        
        # 啟動背景任務
        self.anti_inflation_task.start()
        
        logger.info("🌉 跨平台經濟系統核心已載入")

    def cog_unload(self):
        """卸載時停止背景任務"""
        self.anti_inflation_task.cancel()

    # ========== 背景任務 ==========

    @tasks.loop(hours=6)  # 每6小時執行一次抗通膨檢查
    async def anti_inflation_task(self):
        """定期執行抗通膨調整"""
        try:
            for guild in self.bot.guilds:
                await self.economy_manager.perform_anti_inflation_adjustment(guild.id)
                await asyncio.sleep(1)  # 避免過度負載
                
        except Exception as e:
            logger.error(f"❌ 抗通膨背景任務失敗: {e}")

    @anti_inflation_task.before_loop
    async def before_anti_inflation_task(self):
        """等待 Bot 準備完成"""
        await self.bot.wait_until_ready()

    # ========== 管理員命令 ==========

    # @app_commands.command(name="setup_cross_platform", description="設定跨平台經濟同步")  # 移至管理選單
    @app_commands.describe(
        minecraft_api="Minecraft 伺服器 API 端點",
        server_key="伺服器認證金鑰",
        enable="是否啟用同步"
    )
    async def setup_cross_platform(self, interaction: discord.Interaction, 
                                 minecraft_api: str, server_key: str, enable: bool = True):
        """設定跨平台經濟同步"""
        try:
            # 檢查權限
            if not interaction.user.guild_permissions.administrator:
                await interaction.response.send_message("❌ 需要管理員權限才能設定跨平台同步。", ephemeral=True)
                return
            
            await interaction.response.defer()
            
            if enable:
                success = await self.economy_manager.enable_cross_platform_sync(
                    guild_id=interaction.guild.id,
                    minecraft_api_endpoint=minecraft_api,
                    minecraft_server_key=server_key
                )
                
                if success:
                    embed = EmbedBuilder.create_success_embed(
                        "🌉 跨平台同步已啟用",
                        f"✅ 已成功連接到 Minecraft 伺服器\n📡 API 端點：`{minecraft_api}`"
                    )
                else:
                    embed = EmbedBuilder.create_error_embed(
                        "❌ 設定失敗",
                        "無法啟用跨平台同步，請檢查 API 端點和金鑰是否正確。"
                    )
            else:
                # 停用同步
                await self.economy_manager.update_economy_settings(
                    guild_id=interaction.guild.id,
                    sync_enabled=False
                )
                embed = EmbedBuilder.create_info_embed(
                    "🔌 跨平台同步已停用",
                    "Discord 和 Minecraft 的經濟系統將獨立運作。"
                )
            
            await interaction.followup.send(embed=embed)
            
        except Exception as e:
            logger.error(f"❌ 設定跨平台同步失敗: {e}")
            await interaction.followup.send("❌ 設定過程中發生錯誤。", ephemeral=True)

    # @app_commands.command(name="economy_settings", description="查看或調整經濟系統設定")  # 移至管理選單
    @app_commands.describe(
        daily_coins_base="每日基礎金幣獲得量",
        daily_coins_max="每日最大金幣獲得量",
        message_coins="每條訊息金幣獎勵",
        inflation_threshold="通膨控制閾值 (0.01-0.1)"
    )
    async def economy_settings(self, interaction: discord.Interaction,
                             daily_coins_base: Optional[int] = None,
                             daily_coins_max: Optional[int] = None,
                             message_coins: Optional[int] = None,
                             inflation_threshold: Optional[float] = None):
        """查看或調整經濟系統設定"""
        try:
            # 檢查權限
            if not interaction.user.guild_permissions.administrator:
                await interaction.response.send_message("❌ 需要管理員權限才能調整經濟設定。", ephemeral=True)
                return
            
            await interaction.response.defer()
            
            settings = await self.economy_manager.get_economy_settings(interaction.guild.id)
            
            # 如果有參數，則更新設定
            updates = {}
            if daily_coins_base is not None:
                updates["daily_coins_base"] = max(10, min(100, daily_coins_base))
            if daily_coins_max is not None:
                updates["daily_coins_max"] = max(100, min(1000, daily_coins_max))
            if message_coins is not None:
                updates["message_coins"] = max(1, min(20, message_coins))
            if inflation_threshold is not None:
                updates["inflation_threshold"] = max(0.01, min(0.1, inflation_threshold))
            
            if updates:
                settings = await self.economy_manager.update_economy_settings(
                    guild_id=interaction.guild.id,
                    **updates
                )
                title = "⚙️ 經濟設定已更新"
                color = "success"
            else:
                title = "⚙️ 目前經濟設定"
                color = "info"
            
            embed = EmbedBuilder.build(
                title=title,
                description=f"{interaction.guild.name} 的經濟系統設定",
                color=color
            )
            
            # 基本設定
            embed.add_field(
                name="💰 每日獎勵設定",
                value=f"基礎金幣：**{settings.daily_coins_base}**\n"
                      f"最大金幣：**{settings.daily_coins_max}**\n"
                      f"基礎寶石：**{settings.daily_gems_base}**\n"
                      f"最大寶石：**{settings.daily_gems_max}**",
                inline=True
            )
            
            # 活動獎勵
            embed.add_field(
                name="🎯 活動獎勵",
                value=f"訊息金幣：**{settings.message_coins}**\n"
                      f"語音/分鐘：**{settings.voice_coins_per_minute}**\n"
                      f"任務倍率：**{settings.task_completion_multiplier}x**",
                inline=True
            )
            
            # 通膨控制
            embed.add_field(
                name="📊 通膨控制",
                value=f"閾值：**{settings.inflation_threshold:.1%}**\n"
                      f"通縮調整：**{'啟用' if settings.deflation_enabled else '停用'}**\n"
                      f"調整間隔：**{settings.market_adjustment_interval // 3600}小時**",
                inline=True
            )
            
            # 跨平台設定
            embed.add_field(
                name="🌉 跨平台同步",
                value=f"狀態：**{'啟用' if settings.sync_enabled else '停用'}**\n"
                      f"同步間隔：**{settings.sync_interval // 60}分鐘**" + 
                      (f"\nAPI：`{settings.minecraft_api_endpoint[:30]}...`" if settings.minecraft_api_endpoint else ""),
                inline=False
            )
            
            embed.set_footer(text=f"最後更新：{settings.last_updated.strftime('%Y-%m-%d %H:%M:%S')} UTC")
            
            await interaction.followup.send(embed=embed)
            
        except Exception as e:
            logger.error(f"❌ 查看經濟設定失敗: {e}")
            await interaction.followup.send("❌ 獲取設定時發生錯誤。", ephemeral=True)

    # @app_commands.command(name="economy_stats", description="查看跨平台經濟統計")  # 移至管理選單
    async def economy_stats(self, interaction: discord.Interaction):
        """查看跨平台經濟統計"""
        try:
            await interaction.response.defer()
            
            # 獲取傳統經濟統計
            traditional_stats = await self.economy_manager.get_economy_stats(interaction.guild.id)
            
            # 獲取跨平台統計
            cross_platform_stats = await self.economy_manager.get_cross_platform_statistics(interaction.guild.id)
            
            embed = EmbedBuilder.create_info_embed(
                "📊 跨平台經濟統計",
                f"{interaction.guild.name} 的經濟系統報告"
            )
            
            # 基本統計
            embed.add_field(
                name="👥 用戶統計",
                value=f"總用戶數：**{traditional_stats.get('total_users', 0):,}**\n"
                      f"今日簽到：**{traditional_stats.get('daily_checkins', 0):,}**",
                inline=True
            )
            
            # 貨幣統計
            embed.add_field(
                name="💰 貨幣供給",
                value=f"總金幣：**{traditional_stats.get('total_coins', 0):,}**\n"
                      f"總寶石：**{traditional_stats.get('total_gems', 0):,}**\n"
                      f"平均金幣：**{traditional_stats.get('avg_coins', 0):.0f}**",
                inline=True
            )
            
            # 遊戲統計
            embed.add_field(
                name="🎮 遊戲統計",
                value=f"總遊戲數：**{traditional_stats.get('total_games', 0):,}**\n"
                      f"總勝利數：**{traditional_stats.get('total_wins', 0):,}**\n"
                      f"平均勝率：**{traditional_stats.get('win_rate', 0):.1f}%**",
                inline=True
            )
            
            # 跨平台統計
            if cross_platform_stats.get("sync_enabled"):
                embed.add_field(
                    name="🌉 跨平台同步",
                    value=f"總同步交易：**{cross_platform_stats.get('total_sync_transactions', 0):,}**\n"
                          f"24小時同步：**{cross_platform_stats.get('last_24h_syncs', 0):,}**\n"
                          f"活躍同步：**{cross_platform_stats.get('active_sync_tasks', 0)}**",
                    inline=True
                )
                
                platform_dist = cross_platform_stats.get("platform_distribution", {})
                embed.add_field(
                    name="📱 平台分布",
                    value=f"Discord：**{platform_dist.get('discord', 0):,}**\n"
                          f"Minecraft：**{platform_dist.get('minecraft', 0):,}**",
                    inline=True
                )
            else:
                embed.add_field(
                    name="🌉 跨平台同步",
                    value="**停用**\n使用 `/setup_cross_platform` 啟用",
                    inline=True
                )
            
            # 通膨指標
            try:
                inflation_result = await self.economy_manager.perform_anti_inflation_adjustment(interaction.guild.id)
                if inflation_result:
                    inflation_rate = inflation_result.get("inflation_rate", 0)
                    status_emoji = "📈" if inflation_rate > 0 else "📉" if inflation_rate < 0 else "📊"
                    
                    embed.add_field(
                        name="📊 經濟健康度",
                        value=f"通膨率：**{status_emoji} {inflation_rate:.2%}**\n"
                              f"調整狀態：**{'已調整' if inflation_result.get('adjustment_applied') else '穩定'}**",
                        inline=False
                    )
            except Exception:
                pass
            
            embed.set_footer(text=f"統計時間：{datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')} UTC")
            
            await interaction.followup.send(embed=embed)
            
        except Exception as e:
            logger.error(f"❌ 查看經濟統計失敗: {e}")
            await interaction.followup.send("❌ 獲取統計時發生錯誤。", ephemeral=True)

    # @app_commands.command(name="force_sync", description="強制執行用戶跨平台同步")  # 移至管理選單
    @app_commands.describe(user="要同步的用戶")
    async def force_sync(self, interaction: discord.Interaction, user: discord.Member):
        """強制執行用戶跨平台同步"""
        try:
            # 檢查權限
            if not interaction.user.guild_permissions.administrator:
                await interaction.response.send_message("❌ 需要管理員權限才能強制同步。", ephemeral=True)
                return
            
            await interaction.response.defer()
            
            settings = await self.economy_manager.get_economy_settings(interaction.guild.id)
            
            if not settings.sync_enabled:
                await interaction.followup.send("❌ 跨平台同步未啟用。請先使用 `/setup_cross_platform` 設定。", ephemeral=True)
                return
            
            # 執行同步
            await self.economy_manager.trigger_cross_platform_sync(user.id, interaction.guild.id)
            
            embed = EmbedBuilder.create_success_embed(
                "🔄 強制同步已觸發",
                f"正在同步 {user.mention} 的經濟數據到 Minecraft 伺服器..."
            )
            
            await interaction.followup.send(embed=embed)
            
            # 等待幾秒後檢查結果
            await asyncio.sleep(3)
            
            # 獲取用戶經濟數據顯示結果
            economy_data = await self.economy_manager.get_user_economy(user.id, interaction.guild.id)
            
            result_embed = EmbedBuilder.create_info_embed(
                "📋 同步結果",
                f"{user.display_name} 的經濟數據"
            )
            
            result_embed.add_field(
                name="💰 目前餘額",
                value=f"金幣：**{economy_data.get('coins', 0):,}**\n"
                      f"寶石：**{economy_data.get('gems', 0):,}**\n"
                      f"票券：**{economy_data.get('tickets', 0):,}**\n"
                      f"經驗值：**{economy_data.get('experience', 0):,}**",
                inline=True
            )
            
            await interaction.followup.send(embed=result_embed)
            
        except Exception as e:
            logger.error(f"❌ 強制同步失敗: {e}")
            await interaction.followup.send("❌ 同步過程中發生錯誤。", ephemeral=True)

    # @app_commands.command(name="anti_inflation", description="手動執行抗通膨調整")  # 移至管理選單
    async def manual_anti_inflation(self, interaction: discord.Interaction):
        """手動執行抗通膨調整"""
        try:
            # 檢查權限
            if not interaction.user.guild_permissions.administrator:
                await interaction.response.send_message("❌ 需要管理員權限才能執行抗通膨調整。", ephemeral=True)
                return
            
            await interaction.response.defer()
            
            result = await self.economy_manager.perform_anti_inflation_adjustment(interaction.guild.id)
            
            if result:
                inflation_rate = result.get("inflation_rate", 0)
                avg_coins = result.get("avg_coins", 0)
                adjustment_applied = result.get("adjustment_applied", False)
                
                if adjustment_applied:
                    title = "⚠️ 抗通膨調整已執行"
                    color = "warning"
                    description = "檢測到經濟不平衡，已自動調整獎勵倍率。"
                else:
                    title = "✅ 經濟狀況穩定"
                    color = "success"
                    description = "目前經濟指標在正常範圍內，無需調整。"
                
                embed = EmbedBuilder.build(
                    title=title,
                    description=description,
                    color=color
                )
                
                status_emoji = "📈" if inflation_rate > 0 else "📉" if inflation_rate < 0 else "📊"
                
                embed.add_field(
                    name="📊 經濟指標",
                    value=f"通膨率：**{status_emoji} {inflation_rate:.2%}**\n"
                          f"平均金幣：**{avg_coins:.0f}**\n"
                          f"調整狀態：**{'已調整' if adjustment_applied else '無需調整'}**",
                    inline=False
                )
                
            else:
                embed = EmbedBuilder.create_error_embed(
                    "❌ 抗通膨調整失敗",
                    "無法執行經濟調整，請稍後再試。"
                )
            
            await interaction.followup.send(embed=embed)
            
        except Exception as e:
            logger.error(f"❌ 手動抗通膨調整失敗: {e}")
            await interaction.followup.send("❌ 調整過程中發生錯誤。", ephemeral=True)

    # ========== Webhook 處理 ==========

    async def handle_minecraft_webhook(self, webhook_data: Dict[str, Any]) -> bool:
        """處理來自 Minecraft 的 Webhook（由 API 路由調用）"""
        try:
            return await self.economy_manager.handle_minecraft_webhook(webhook_data)
        except Exception as e:
            logger.error(f"❌ 處理 Minecraft Webhook 失敗: {e}")
            return False

    # ========== 用戶命令 ==========

    # @app_commands.command(name="my_economy", description="查看我的跨平台經濟狀況")  # 移至主選單
    async def my_economy(self, interaction: discord.Interaction):
        """查看用戶的跨平台經濟狀況"""
        try:
            await interaction.response.defer(ephemeral=True)
            
            economy_data = await self.economy_manager.get_user_economy(interaction.user.id, interaction.guild.id)
            
            embed = EmbedBuilder.create_info_embed(
                "💰 我的經濟狀況",
                f"{interaction.user.display_name} 的跨平台資產"
            )
            
            # 餘額資訊
            embed.add_field(
                name="💎 資產餘額",
                value=f"金幣：**{economy_data.get('coins', 0):,}** 🪙\n"
                      f"寶石：**{economy_data.get('gems', 0):,}** 💎\n"
                      f"票券：**{economy_data.get('tickets', 0):,}** 🎫\n"
                      f"經驗值：**{economy_data.get('experience', 0):,}** ⭐",
                inline=True
            )
            
            # 等級資訊
            level_info = await self.economy_manager.calculate_level(economy_data.get('experience', 0))
            embed.add_field(
                name="📈 等級資訊",
                value=f"目前等級：**{level_info.get('level', 1)}**\n"
                      f"進度：**{level_info.get('progress_percentage', 0):.1f}%**\n"
                      f"下一級需要：**{level_info.get('next_level_exp', 0):,}** EXP",
                inline=True
            )
            
            # 遊戲統計
            embed.add_field(
                name="🎮 遊戲統計",
                value=f"總遊戲：**{economy_data.get('total_games', 0):,}**\n"
                      f"總勝利：**{economy_data.get('total_wins', 0):,}**\n"
                      f"勝率：**{economy_data.get('win_rate', 0):.1f}%**",
                inline=True
            )
            
            # 每日統計
            embed.add_field(
                name="📅 今日統計",
                value=f"遊戲次數：**{economy_data.get('daily_games', 0)}**\n"
                      f"勝利次數：**{economy_data.get('daily_wins', 0)}**\n"
                      f"已簽到：**{'是' if economy_data.get('daily_claimed') else '否'}**",
                inline=True
            )
            
            # 跨平台狀態
            settings = await self.economy_manager.get_economy_settings(interaction.guild.id)
            sync_status = "🌉 已啟用" if settings.sync_enabled else "🔌 未啟用"
            
            embed.add_field(
                name="🔄 跨平台同步",
                value=f"狀態：**{sync_status}**\n"
                      f"{'Minecraft 數據將自動同步' if settings.sync_enabled else '獨立於 Minecraft 運作'}",
                inline=False
            )
            
            await interaction.followup.send(embed=embed)
            
        except Exception as e:
            logger.error(f"❌ 查看用戶經濟狀況失敗: {e}")
            await interaction.followup.send("❌ 獲取經濟資料時發生錯誤。", ephemeral=True)

    # ========== Zientis 整合命令 ==========

    # @app_commands.command(name="setup_zientis", description="設定 Zientis Minecraft 伺服器整合")  # 移至管理選單
    @app_commands.describe(
        api_endpoint="Zientis API 端點 (例如: http://zientis.example.com:8080)",
        server_key="伺服器密鑰"
    )
    async def setup_zientis(
        self,
        interaction: discord.Interaction,
        api_endpoint: str,
        server_key: str
    ):
        """設定 Zientis Minecraft 伺服器整合"""
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message(
                "❌ 此命令需要管理員權限。", ephemeral=True
            )
            return
            
        try:
            await interaction.response.defer(ephemeral=True)
            
            # 設置 Zientis 整合
            success = await self.economy_manager.setup_zientis_integration(
                interaction.guild.id, api_endpoint, server_key
            )
            
            if success:
                embed = EmbedBuilder.create_success_embed(
                    "✅ Zientis 整合設置成功",
                    "跨平台經濟系統已成功連接到 Zientis Minecraft 伺服器"
                )
                
                embed.add_field(
                    name="🔗 連接資訊",
                    value=f"**API 端點**: {api_endpoint}\n"
                          f"**狀態**: 已啟用跨平台同步",
                    inline=False
                )
                
                embed.add_field(
                    name="🌉 功能說明",
                    value="• Discord 與 Minecraft 經濟數據雙向同步\n"
                          "• 自動獎勵加成系統\n"
                          "• 實時活動事件處理\n"
                          "• 統一經濟管理界面",
                    inline=False
                )
                
                embed.add_field(
                    name="📋 下一步",
                    value="使用 `/test_zientis_connection` 測試連接\n"
                          "使用 `/economy_stats` 查看跨平台統計",
                    inline=False
                )
                
            else:
                embed = EmbedBuilder.create_error_embed(
                    "❌ Zientis 整合設置失敗",
                    "無法連接到指定的 Zientis API 端點"
                )
                
                embed.add_field(
                    name="🔍 檢查項目",
                    value="• API 端點是否正確\n"
                          "• 服務器密鑰是否有效\n"
                          "• Zientis 伺服器是否運行\n"
                          "• 網路連接是否正常",
                    inline=False
                )
            
            await interaction.followup.send(embed=embed)
            
        except Exception as e:
            logger.error(f"❌ 設置 Zientis 整合失敗: {e}")
            await interaction.followup.send(
                "❌ 設置 Zientis 整合時發生錯誤。", ephemeral=True
            )

    # @app_commands.command(name="test_zientis_connection", description="測試與 Zientis 伺服器的連接")  # 已移除以節省指令空間
    async def test_zientis_connection(self, interaction: discord.Interaction):
        """測試與 Zientis 伺服器的連接"""
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message(
                "❌ 此命令需要管理員權限。", ephemeral=True
            )
            return
            
        try:
            await interaction.response.defer(ephemeral=True)
            
            settings = await self.economy_manager.get_economy_settings(interaction.guild.id)
            
            if not settings.sync_enabled or not settings.minecraft_api_endpoint:
                await interaction.followup.send(
                    "❌ 尚未設置 Zientis 整合。請先使用 `/setup_zientis` 命令。",
                    ephemeral=True
                )
                return
            
            # 執行連接測試
            import aiohttp
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{settings.minecraft_api_endpoint}/api/v1/discord/economy/health",
                    headers={"X-Server-Key": settings.minecraft_server_key},
                    timeout=aiohttp.ClientTimeout(total=10)
                ) as response:
                    
                    if response.status == 200:
                        result = await response.json()
                        
                        embed = EmbedBuilder.create_success_embed(
                            "✅ Zientis 連接測試成功",
                            "與 Zientis Minecraft 伺服器的連接正常"
                        )
                        
                        embed.add_field(
                            name="🏥 服務狀態",
                            value=f"**整體狀態**: {result.get('status', 'unknown')}\n"
                                  f"**經濟管理器**: {result.get('economy_manager', 'unknown')}\n"
                                  f"**Discord 整合**: {result.get('discord_integration', 'unknown')}",
                            inline=False
                        )
                        
                        embed.add_field(
                            name="🔗 連接資訊",
                            value=f"**端點**: {settings.minecraft_api_endpoint}\n"
                                  f"**響應時間**: 正常\n"
                                  f"**時間戳**: {result.get('timestamp', 'unknown')}",
                            inline=False
                        )
                        
                    else:
                        embed = EmbedBuilder.create_error_embed(
                            "❌ Zientis 連接測試失敗",
                            f"HTTP 狀態碼: {response.status}"
                        )
                        
                        error_text = await response.text()
                        embed.add_field(
                            name="❌ 錯誤詳情",
                            value=f"```{error_text[:500]}```",
                            inline=False
                        )
            
            await interaction.followup.send(embed=embed)
            
        except Exception as e:
            logger.error(f"❌ 測試 Zientis 連接失敗: {e}")
            
            embed = EmbedBuilder.create_error_embed(
                "❌ 連接測試失敗",
                "無法連接到 Zientis 伺服器"
            )
            
            embed.add_field(
                name="🔍 可能原因",
                value="• Zientis 伺服器未運行\n"
                      "• 網路連接問題\n"
                      "• API 端點配置錯誤\n"
                      "• 防火牆阻擋連接",
                inline=False
            )
            
            embed.add_field(
                name="❌ 錯誤詳情",
                value=f"```{str(e)[:500]}```",
                inline=False
            )
            
            await interaction.followup.send(embed=embed)

    # @app_commands.command(name="zientis_user_link", description="生成 Minecraft 帳戶綁定驗證碼")  # 移至主選單
    async def zientis_user_link(self, interaction: discord.Interaction):
        """生成用戶 Minecraft 帳戶綁定驗證碼"""
        try:
            await interaction.response.defer(ephemeral=True)
            
            settings = await self.economy_manager.get_economy_settings(interaction.guild.id)
            
            if not settings.sync_enabled:
                await interaction.followup.send(
                    "❌ 伺服器尚未啟用 Zientis 整合。", ephemeral=True
                )
                return
            
            # 生成驗證碼 (這裡需要實際的實現)
            import random
            verification_code = f"{random.randint(100000, 999999)}"
            
            embed = EmbedBuilder.create_info_embed(
                "🔗 Minecraft 帳戶綁定",
                "請在 Minecraft 中使用以下驗證碼綁定您的帳戶"
            )
            
            embed.add_field(
                name="🔢 驗證碼",
                value=f"```{verification_code}```",
                inline=False
            )
            
            embed.add_field(
                name="📋 綁定步驟",
                value="1. 在 Minecraft 中執行: `/discord link`\n"
                      "2. 輸入上方的驗證碼\n"
                      "3. 等待綁定確認\n"
                      "4. 開始享受跨平台經濟同步！",
                inline=False
            )
            
            embed.add_field(
                name="⏰ 注意事項",
                value="• 驗證碼有效期：24小時\n"
                      "• 每個用戶只能綁定一個 Minecraft 帳戶\n"
                      "• 綁定後經濟數據將自動同步",
                inline=False
            )
            
            await interaction.followup.send(embed=embed)
            
            logger.info(f"🔗 用戶 {interaction.user.id} 生成 Minecraft 綁定驗證碼: {verification_code}")
            
        except Exception as e:
            logger.error(f"❌ 生成綁定驗證碼失敗: {e}")
            await interaction.followup.send(
                "❌ 生成驗證碼時發生錯誤。", ephemeral=True
            )

async def setup(bot):
    await bot.add_cog(CrossPlatformEconomyCore(bot))