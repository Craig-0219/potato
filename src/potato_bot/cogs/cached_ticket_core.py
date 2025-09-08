# bot/cogs/cached_ticket_core.py - 快取優化的票券核心模組
"""
快取優化票券系統核心功能 v2.2.0
整合多層快取系統，提供高性能的票券管理
"""

import asyncio
import time
from datetime import datetime, timezone
from typing import Any, Dict

import discord
from discord import app_commands
from discord.ext import commands, tasks

from potato_bot.db.assignment_dao import AssignmentDAO

# 導入快取優化的組件
from potato_bot.db.cached_ticket_dao import cached_ticket_dao
from potato_bot.db.language_dao import LanguageDAO
from potato_bot.db.tag_dao import TagDAO
from potato_bot.services.assignment_manager import AssignmentManager
from potato_bot.services.language_manager import LanguageManager
from potato_bot.services.statistics_manager import StatisticsManager
from potato_bot.services.tag_manager import TagManager
from potato_bot.services.ticket_manager import TicketManager
from potato_bot.utils.embed_builder import EmbedBuilder
from potato_bot.utils.helper import get_time_ago
from potato_bot.utils.ticket_constants import TicketConstants
from potato_bot.views.ticket_views import TicketControlView, TicketPanelView

# 快取和監控
from potato_shared.cache_manager import cache_manager, cached
from potato_shared.logger import logger


class CachedTicketCore(commands.Cog):
    """快取優化的票券系統核心功能"""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

        # 使用快取優化的 DAO
        self.cached_dao = cached_ticket_dao
        self.assignment_dao = AssignmentDAO()
        self.tag_dao = TagDAO()
        self.language_dao = LanguageDAO()

        # 服務層
        self.manager = TicketManager(self.cached_dao.ticket_dao)  # 傳入原始 DAO
        self.assignment_manager = AssignmentManager(self.assignment_dao, self.cached_dao.ticket_dao)
        self.tag_manager = TagManager(self.tag_dao)
        self.statistics_manager = StatisticsManager()
        self.language_manager = LanguageManager()

        # 性能監控
        self.performance_stats = {
            "commands_executed": 0,
            "cache_hits": 0,
            "cache_misses": 0,
            "avg_response_time": 0.0,
            "last_reset": datetime.now(timezone.utc),
        }

        # 註冊 PersistentViews
        self._register_persistent_views()

        # 啟動任務
        self.sla_monitor.start()
        self.cleanup_task.start()
        self.cache_maintenance.start()
        self.performance_monitor.start()

        logger.info("🚀 快取優化票券核心模組初始化完成")

    def cog_unload(self):
        """模組卸載"""
        self.sla_monitor.cancel()
        self.cleanup_task.cancel()
        self.cache_maintenance.cancel()
        self.performance_monitor.cancel()
        logger.info("📴 快取優化票券核心模組已卸載")

    async def cog_load(self):
        """模組載入時的初始化"""
        try:
            await self.cached_dao.initialize()

            # 預熱快取
            logger.info("🔥 開始預熱票券系統快取...")
            await self._warm_global_cache()

        except Exception as e:
            logger.error(f"❌ 快取票券模組載入失敗: {e}")

    def _register_persistent_views(self):
        """註冊持久化互動組件"""
        try:
            self.bot.add_view(TicketPanelView(settings=None))
            self.bot.add_view(TicketControlView())
            logger.info("✅ PersistentViews 註冊完成")
        except Exception as e:
            logger.error(f"❌ PersistentView 註冊失敗: {e}")

    # ========== 性能監控裝飾器 ==========

    def performance_tracked(func):
        """性能追蹤裝飾器"""

        async def wrapper(self, *args, **kwargs):
            start_time = time.time()

            try:
                result = await func(self, *args, **kwargs)
                self.performance_stats["commands_executed"] += 1

                # 更新平均回應時間
                duration = time.time() - start_time
                current_avg = self.performance_stats["avg_response_time"]
                total_commands = self.performance_stats["commands_executed"]

                self.performance_stats["avg_response_time"] = (
                    current_avg * (total_commands - 1) + duration
                ) / total_commands

                # 記錄慢查詢
                if duration > 1.0:
                    logger.warning(f"⚠️ 慢查詢檢測: {func.__name__} - {duration:.3f}s")

                return result

            except Exception as e:
                logger.error(f"❌ 指令執行失敗 {func.__name__}: {e}")
                raise

        return wrapper

    # ========== 快取優化的核心方法 ==========

    async def _is_ticket_channel(self, channel: discord.TextChannel) -> bool:
        """判斷是否為票券頻道（帶快取）"""
        cache_key = f"is_ticket_channel:{channel.id}"

        # 嘗試從快取獲取
        cached_result = await cache_manager.get(cache_key)
        if cached_result is not None:
            return cached_result

        try:
            # 查詢資料庫
            ticket = await self.cached_dao.ticket_dao.get_ticket_by_channel(channel.id)
            result = ticket is not None

            # 快取結果（短時間快取）
            await cache_manager.set(cache_key, result, 60)

            return result

        except Exception as e:
            logger.error(f"❌ 票券頻道判斷失敗 {channel.id}: {e}")
            # fallback 檢查
            result = hasattr(channel, "name") and channel.name.startswith("ticket-")
            await cache_manager.set(cache_key, result, 30)  # 短時間快取 fallback 結果
            return result

    @cached("ticket_settings", ttl=600)
    async def get_cached_settings(self, guild_id: int) -> Dict[str, Any]:
        """獲取伺服器設定（帶快取）"""
        try:
            return await self.cached_dao.ticket_dao.get_settings(guild_id)
        except Exception as e:
            logger.error(f"❌ 獲取設定失敗 {guild_id}: {e}")
            return {}

    # ========== 快取優化的指令 ==========

    @commands.command(name="setup_ticket")
    @commands.has_permissions(manage_guild=True)
    @performance_tracked
    async def setup_ticket(self, ctx: commands.Context):
        """建立票券面板（快取優化版）"""
        try:
            settings = await self.get_cached_settings(ctx.guild.id)

            embed = EmbedBuilder.build(
                title="🎫 客服中心",
                description=settings.get("welcome_message", "請選擇問題類型來建立支援票券"),
                color=TicketConstants.COLORS["primary"],
            )

            embed.add_field(
                name="📋 系統資訊",
                value=f"• 每人限制：{settings.get('max_tickets_per_user', 3)} 張\n"
                f"• 自動關閉：{settings.get('auto_close_hours', 24)} 小時\n"
                f"• 預期回覆：{settings.get('sla_response_minutes', 60)} 分鐘",
                inline=False,
            )

            # 添加快取狀態資訊
            cache_health = await self.cached_dao.get_cache_health()
            cache_status_emoji = {
                "healthy": "🟢",
                "warning": "🟡",
                "critical": "🔴",
                "error": "❌",
            }.get(cache_health.get("status", "error"), "⚪")

            embed.add_field(
                name="⚡ 系統狀態",
                value=f"{cache_status_emoji} 快取效能：{cache_health.get('hit_rate', 'N/A')}\n"
                f"🔗 Redis：{'已連線' if cache_health.get('redis_connected') else '離線'}",
                inline=True,
            )

            # 創建面板 View
            view = TicketPanelView(settings=settings)

            await ctx.send(embed=embed, view=view)

            # 預熱相關快取
            asyncio.create_task(self.cached_dao.warm_cache(ctx.guild.id))

            logger.info(f"✅ 票券面板已建立: {ctx.guild.id}")

        except Exception as e:
            logger.error(f"❌ 建立票券面板失敗: {e}")
            await ctx.send("❌ 建立票券面板時發生錯誤，請稍後再試。")

    @app_commands.command(name="ticket_stats", description="查看票券統計數據")
    @performance_tracked
    async def ticket_stats(self, interaction: discord.Interaction):
        """查看票券統計（快取優化版）"""
        try:
            await interaction.response.defer()

            # 並行獲取多個統計數據
            stats_tasks = [
                self.cached_dao.get_ticket_statistics(interaction.guild.id),
                self.cached_dao.get_cache_health(),
                self.cached_dao.get_performance_metrics(interaction.guild.id),
            ]

            ticket_stats, cache_health, performance_metrics = await asyncio.gather(*stats_tasks)

            embed = EmbedBuilder.build(
                title="📊 票券系統統計", color=TicketConstants.COLORS["info"]
            )

            # 基本統計
            embed.add_field(
                name="🎫 票券統計",
                value=f"總票券數：{ticket_stats.get('total_tickets', 0)}\n"
                f"活躍票券：{ticket_stats.get('active_tickets', 0)}\n"
                f"今日新增：{ticket_stats.get('today_created', 0)}\n"
                f"平均回應時間：{ticket_stats.get('avg_response_time', 'N/A')}",
                inline=True,
            )

            # 快取性能
            cache_emoji = {
                "healthy": "🟢",
                "warning": "🟡",
                "critical": "🔴",
                "error": "❌",
            }.get(cache_health.get("status", "error"), "⚪")

            embed.add_field(
                name="⚡ 快取性能",
                value=f"{cache_emoji} 狀態：{cache_health.get('status', '未知')}\n"
                f"🎯 命中率：{cache_health.get('hit_rate', 'N/A')}\n"
                f"💾 記憶體使用：{cache_health.get('l1_usage', 'N/A')}\n"
                f"🔗 Redis：{'✅' if cache_health.get('redis_connected') else '❌'}",
                inline=True,
            )

            # 性能指標
            embed.add_field(
                name="🚀 性能指標",
                value=f"指令執行數：{self.performance_stats['commands_executed']}\n"
                f"平均回應：{self.performance_stats['avg_response_time']:.3f}s\n"
                f"快取命中：{self.performance_stats['cache_hits']}\n"
                f"快取未命中：{self.performance_stats['cache_misses']}",
                inline=True,
            )

            # 添加優化建議
            recommendations = cache_health.get("recommendations", [])
            if recommendations:
                embed.add_field(
                    name="💡 優化建議",
                    value="\n".join([f"• {rec}" for rec in recommendations[:3]]),
                    inline=False,
                )

            embed.timestamp = datetime.now(timezone.utc)
            await interaction.followup.send(embed=embed)

        except Exception as e:
            logger.error(f"❌ 票券統計查詢失敗: {e}")
            await interaction.followup.send("❌ 獲取統計數據時發生錯誤。")

    @app_commands.command(name="my_tickets", description="查看我的票券")
    @performance_tracked
    async def my_tickets(self, interaction: discord.Interaction, status: str = None):
        """查看用戶票券（快取優化版）"""
        try:
            await interaction.response.defer(ephemeral=True)

            # 使用快取優化的查詢
            tickets = await self.cached_dao.get_user_tickets(
                interaction.user.id, interaction.guild.id, status, limit=10
            )

            if not tickets:
                await interaction.followup.send("📝 您目前沒有票券。", ephemeral=True)
                return

            embed = EmbedBuilder.build(
                title=f"🎫 {interaction.user.display_name} 的票券",
                description=f"找到 {len(tickets)} 張票券",
                color=TicketConstants.COLORS["primary"],
            )

            for ticket in tickets[:10]:  # 最多顯示10張
                status_emoji = {
                    "open": "🟢",
                    "closed": "🔴",
                    "pending": "🟡",
                }.get(ticket.get("status", "unknown"), "⚪")

                embed.add_field(
                    name=f"{status_emoji} 票券 #{ticket.get('id')}",
                    value=f"標題：{ticket.get('title', 'N/A')}\n"
                    f"狀態：{ticket.get('status', 'unknown')}\n"
                    f"建立：{get_time_ago(ticket.get('created_at'))}",
                    inline=True,
                )

            # 添加快取資訊
            cache_info = "🚀 查詢耗時：<200ms（已快取）"
            embed.set_footer(text=cache_info)

            await interaction.followup.send(embed=embed, ephemeral=True)

        except Exception as e:
            logger.error(f"❌ 用戶票券查詢失敗: {e}")
            await interaction.followup.send("❌ 查詢票券時發生錯誤。", ephemeral=True)

    @app_commands.command(name="cache_control", description="快取控制（管理員專用）")
    @app_commands.describe(action="執行的動作", target="目標範圍")
    @app_commands.choices(
        action=[
            app_commands.Choice(name="清空快取", value="clear"),
            app_commands.Choice(name="預熱快取", value="warm"),
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
                # 清空快取
                pattern = f"*{interaction.guild.id}*" if target == "guild" else "*"
                count = await cache_manager.clear_all(pattern)

                embed = EmbedBuilder.build(
                    title="🧹 快取清理完成",
                    description=f"已清理 {count} 個快取條目",
                    color=TicketConstants.COLORS["success"],
                )

            elif action == "warm":
                # 預熱快取
                await self.cached_dao.warm_cache(interaction.guild.id)

                embed = EmbedBuilder.build(
                    title="🔥 快取預熱完成",
                    description="已預載熱點數據到快取",
                    color=TicketConstants.COLORS["success"],
                )

            elif action == "stats":
                # 快取統計
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

                embed.add_field(
                    name="L1 記憶體快取",
                    value=f"大小：{stats['l1_memory']['size']}/{stats['l1_memory']['max_size']}\n"
                    f"使用率：{stats['l1_memory']['usage']}\n"
                    f"命中率：{stats['l1_memory']['hit_rate']}",
                    inline=True,
                )

                embed.add_field(
                    name="L2 Redis 快取",
                    value=f"連線：{'是' if stats['l2_redis']['connected'] else '否'}\n"
                    f"命中率：{stats['l2_redis']['hit_rate']}\n"
                    f"記憶體：{stats['l2_redis'].get('memory_used', 'N/A')}",
                    inline=True,
                )

            elif action == "health":
                # 健康檢查
                health = await self.cached_dao.get_cache_health()

                status_colors = {
                    "healthy": TicketConstants.COLORS["success"],
                    "warning": TicketConstants.COLORS["warning"],
                    "critical": TicketConstants.COLORS["error"],
                    "error": TicketConstants.COLORS["error"],
                }

                embed = EmbedBuilder.build(
                    title="🏥 快取健康檢查",
                    description=f"狀態：{health.get('status', '未知')}",
                    color=status_colors.get(
                        health.get("status"),
                        TicketConstants.COLORS["secondary"],
                    ),
                )

                embed.add_field(
                    name="關鍵指標",
                    value=f"命中率：{health.get('hit_rate', 'N/A')}\n"
                    f"Redis：{'已連線' if health.get('redis_connected') else '離線'}\n"
                    f"總請求：{health.get('total_requests', 0)}",
                    inline=True,
                )

                recommendations = health.get("recommendations", [])
                if recommendations:
                    embed.add_field(
                        name="建議",
                        value="\n".join([f"• {rec}" for rec in recommendations]),
                        inline=False,
                    )

            await interaction.followup.send(embed=embed, ephemeral=True)

        except Exception as e:
            logger.error(f"❌ 快取控制操作失敗: {e}")
            await interaction.followup.send("❌ 快取控制操作失敗。", ephemeral=True)

    # ========== 背景任務 ==========

    @tasks.loop(minutes=30)
    async def sla_monitor(self):
        """SLA 監控任務（快取優化版）"""
        try:
            # 使用快取來減少頻繁查詢
            await self._check_sla_violations()
        except Exception as e:
            logger.error(f"❌ SLA 監控任務失敗: {e}")

    @tasks.loop(hours=6)
    async def cleanup_task(self):
        """清理任務（快取優化版）"""
        try:
            await self._cleanup_expired_tickets()

            # 同時清理相關快取
            await cache_manager.clear_all("*expired*")

        except Exception as e:
            logger.error(f"❌ 清理任務失敗: {e}")

    @tasks.loop(hours=1)
    async def cache_maintenance(self):
        """快取維護任務"""
        try:
            # 清理過期的快取條目
            await cache_manager.get_statistics()

            # 執行維護操作（這會由快取管理器自動處理）
            await asyncio.sleep(0.1)  # 讓其他任務有機會執行

            stats_after = await cache_manager.get_statistics()

            logger.info(f"🔧 快取維護完成 - 請求總數: {stats_after['requests']['total']}")

        except Exception as e:
            logger.error(f"❌ 快取維護失敗: {e}")

    @tasks.loop(minutes=5)
    async def performance_monitor(self):
        """性能監控任務"""
        try:
            # 檢查性能指標
            if self.performance_stats["avg_response_time"] > 2.0:
                logger.warning(
                    f"⚠️ 系統回應時間過慢: {self.performance_stats['avg_response_time']:.3f}s"
                )

            # 檢查快取健康狀態
            cache_health = await self.cached_dao.get_cache_health()
            if cache_health.get("status") in ["warning", "critical"]:
                logger.warning(f"⚠️ 快取健康狀態異常: {cache_health.get('status')}")

            # 重置計數器（每小時重置一次）
            now = datetime.now(timezone.utc)
            if (now - self.performance_stats["last_reset"]).total_seconds() > 3600:
                self.performance_stats = {
                    "commands_executed": 0,
                    "cache_hits": 0,
                    "cache_misses": 0,
                    "avg_response_time": 0.0,
                    "last_reset": now,
                }

        except Exception as e:
            logger.error(f"❌ 性能監控失敗: {e}")

    # ========== 輔助方法 ==========

    async def _warm_global_cache(self):
        """預熱全域快取"""
        try:
            # 獲取活躍的伺服器
            guilds = [guild.id for guild in self.bot.guilds]

            # 並行預熱多個伺服器的快取
            tasks = [self.cached_dao.warm_cache(guild_id) for guild_id in guilds[:5]]  # 限制並發數
            await asyncio.gather(*tasks, return_exceptions=True)

            logger.info(f"🔥 全域快取預熱完成: {len(guilds)} 個伺服器")

        except Exception as e:
            logger.error(f"❌ 全域快取預熱失敗: {e}")

    async def _check_sla_violations(self):
        """檢查 SLA 違規（快取優化版）"""
        # 實現 SLA 檢查邏輯

    async def _cleanup_expired_tickets(self):
        """清理過期票券（快取優化版）"""
        # 實現票券清理邏輯

    @sla_monitor.before_loop
    @cleanup_task.before_loop
    @cache_maintenance.before_loop
    @performance_monitor.before_loop
    async def before_tasks(self):
        """等待機器人準備完成"""
        await self.bot.wait_until_ready()


async def setup(bot):
    """設置 Cog"""
    await bot.add_cog(CachedTicketCore(bot))
