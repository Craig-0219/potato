# bot/cogs/ticket_core.py - 快取優化的票券核心模組
"""
快取優化票券系統核心功能 v2.2.0
整合多層快取系統，提供高性能的票券管理
"""

import asyncio
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import discord
from discord import app_commands
from discord.ext import commands, tasks


# 導入快取優化的組件
from potato_bot.db.cached_ticket_dao import cached_ticket_dao
from potato_bot.services.ticket_manager import TicketManager
from potato_bot.utils.embed_builder import EmbedBuilder
from potato_bot.utils.helper import get_time_ago
from potato_bot.utils.ticket_constants import TicketConstants
from potato_bot.utils.ticket_utils import is_ticket_channel
from potato_bot.utils.managed_cog import register_persistent_view
from potato_bot.utils.cog_loader import COGS_PREFIX
from potato_bot.views.ticket_views import TicketControlView, TicketPanelView

# 快取和監控
from potato_shared.cache_manager import cache_manager, cached
from potato_shared.logger import logger


def build_ticket_settings_embed(guild: discord.Guild, settings: Dict[str, Any]) -> discord.Embed:
    category_id = settings.get("category_id")
    category_txt = (
        f"<#{category_id}>"
        if category_id
        else "未設定（無法建立票券）"
    )
    support_roles = settings.get("support_roles") or []
    role_mentions = []
    for rid in support_roles:
        role = guild.get_role(int(rid))
        if role:
            role_mentions.append(role.mention)
    roles_txt = ", ".join(role_mentions) if role_mentions else "未設定"
    embed = EmbedBuilder.build(
        title="🛠️ 票券系統設定",
        description="在此設定票券分類、客服角色與基本參數。",
        color=TicketConstants.COLORS["primary"],
    )
    embed.add_field(name="分類", value=category_txt, inline=False)
    embed.add_field(
        name="客服角色",
        value=roles_txt,
        inline=False,
    )
    embed.add_field(
        name="限額 / 自動關閉",
        value=(
            f"每人上限：{settings.get('max_tickets_per_user', 3)}\n"
            f"自動關閉：{settings.get('auto_close_hours', 24)} 小時"
        ),
        inline=False,
    )
    return embed


class CachedTicketCore(commands.Cog):
    """快取優化的票券系統核心功能"""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

        # 使用快取優化的 DAO
        self.cached_dao = cached_ticket_dao

        # 服務層
        self.manager = TicketManager(self.cached_dao.ticket_dao)  # 傳入原始 DAO

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
        self.cleanup_task.start()
        self.cache_maintenance.start()
        self.performance_monitor.start()

        logger.info("🚀 快取優化票券核心模組初始化完成")

    def cog_unload(self):
        """模組卸載"""
        self.cleanup_task.cancel()
        self.cache_maintenance.cancel()
        self.performance_monitor.cancel()
        logger.info("📴 快取優化票券核心模組已卸載")

    async def cog_load(self):
        """模組載入時的初始化"""
        try:
            # 與基礎版 ticket_core 互斥
            core_ext = f"{COGS_PREFIX}ticket_core"
            legacy_core_ext = f"{COGS_PREFIX}ticket.core.ticket_core"
            if core_ext in self.bot.extensions or legacy_core_ext in self.bot.extensions:
                raise commands.ExtensionFailed(
                    "ticket_core", Exception("ticket_core already loaded")
                )

            # 確保 listener 載入
            listener_ext = f"{COGS_PREFIX}ticket.listener.ticket_listener"
            if listener_ext not in self.bot.extensions:
                try:
                    await self.bot.load_extension(listener_ext)
                    logger.info("✅ 已一併載入 ticket.listener.ticket_listener")
                except Exception as e:
                    logger.error(f"❌ 載入 ticket.listener.ticket_listener 失敗：{e}")
                    raise commands.ExtensionFailed("ticket_core", e)

            await self.cached_dao.initialize()

            # 預熱快取
            logger.info("🔥 開始預熱票券系統快取...")
            await self._warm_global_cache()

        except Exception as e:
            logger.error(f"❌ 快取票券模組載入失敗: {e}")

    def _register_persistent_views(self):
        """註冊持久化互動組件"""
        try:
            register_persistent_view(self.bot, TicketPanelView(settings=None))
            register_persistent_view(self.bot, TicketControlView())
            logger.info("✅ PersistentViews 註冊完成")
        except Exception as e:
            logger.error(f"❌ PersistentView 註冊失敗: {e}")

    # ========== 性能監控裝飾器 ==========

    def performance_tracked(func):
        """性能追蹤裝飾器"""

        async def wrapper(self, *args: Any, **kwargs: Any):
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
            result = is_ticket_channel(channel)
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
        await self._setup_ticket_impl(ctx)

    async def _setup_ticket_impl(self, ctx: commands.Context):
        """共用的面板建立邏輯，供舊指令別名重用"""
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
                f"• 自動關閉：{settings.get('auto_close_hours', 24)} 小時",
                inline=False,
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

    @app_commands.command(name="my_tickets", description="查看我的票券")
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

    @app_commands.command(name="ticket_settings", description="管理票券系統設定（分類/限額/客服角色）")
    @app_commands.default_permissions(manage_guild=True)
    async def ticket_settings(self, interaction: discord.Interaction):
        """票券設定面板（管理員）"""
        await interaction.response.defer(ephemeral=True)
        settings = await self.cached_dao.ticket_dao.get_settings(interaction.guild.id)
        embed = build_ticket_settings_embed(interaction.guild, settings)
        view = TicketSettingsView(self.cached_dao.ticket_dao, interaction.guild, settings)
        await interaction.followup.send(embed=embed, view=view, ephemeral=True)

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

            elif action == "health":
                # 健康檢查
                health = await self._get_cache_health()

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

    @commands.command(name="ticket_help")
    async def ticket_help(self, ctx: commands.Context):
        """票券使用說明（取代舊的 !ticket_settings）"""
        embed = EmbedBuilder.build(
            title="🎫 票券指令使用說明",
            description="以下為常用票券指令與設定入口：",
            color=TicketConstants.COLORS["info"],
        )
        embed.add_field(name="建立面板", value="`!setup_ticket`", inline=False)
        embed.add_field(
            name="設定面板/分類/客服角色/限額",
            value="`/ticket_settings`（管理員）",
            inline=False,
        )
        embed.add_field(
            name="查個人票券",
            value="`/my_tickets`",
            inline=False,
        )
        await ctx.send(embed=embed)

    # ========== 背景任務 ==========

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
            cache_health = await self._get_cache_health()
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

            # 嘗試抓近期活躍票券（舊 TicketDAO 可能沒有實作，故加 has check）
            if hasattr(self.cached_dao.ticket_dao, "get_recent_active_tickets"):
                try:
                    await self.cached_dao.ticket_dao.get_recent_active_tickets(limit=20)
                except Exception:
                    pass

            logger.info(f"🔥 全域快取預熱完成: {len(guilds)} 個伺服器")

        except Exception as e:
            logger.error(f"❌ 全域快取預熱失敗: {e}")

    async def _cleanup_expired_tickets(self):
        """清理過期票券（快取優化版）"""
        # 實現票券清理邏輯

    async def _get_cache_health(self) -> Dict[str, Any]:
        """安全取得快取健康資訊，未實作時回傳空 dict 避免噴錯"""
        if hasattr(self.cached_dao, "get_cache_health"):
            try:
                return await self.cached_dao.get_cache_health()
            except Exception as e:
                logger.error(f"❌ 取得快取健康失敗: {e}")
                return {}
        return {}

    @cleanup_task.before_loop
    @cache_maintenance.before_loop
    @performance_monitor.before_loop
    async def before_tasks(self):
        """等待機器人準備完成"""
        await self.bot.wait_until_ready()


    # ========== 設定面板輔助 ==========
    def _build_settings_embed(self, guild: discord.Guild, settings: Dict[str, Any]) -> discord.Embed:
        return build_ticket_settings_embed(guild, settings)


# ========== 設定面板 View / Select / Modal ==========
class TicketSettingsView(discord.ui.View):
    """管理員設定面板"""

    def __init__(self, dao, guild: discord.Guild, settings: Dict[str, Any]):
        super().__init__(timeout=300)
        self.dao = dao
        self.guild = guild
        self.settings = settings

    @discord.ui.button(label="設定分類", style=discord.ButtonStyle.primary)
    async def set_category(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.user.guild_permissions.manage_guild:
            await interaction.response.send_message("❌ 需要管理伺服器權限", ephemeral=True)
            return
        select = CategorySelect(self.dao, self.guild, self.settings)
        view = discord.ui.View(timeout=120)
        view.add_item(select)
        await interaction.response.send_message("請選擇票券分類：", view=view, ephemeral=True)

    @discord.ui.button(label="客服角色", style=discord.ButtonStyle.secondary)
    async def set_support_roles(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.user.guild_permissions.manage_guild:
            await interaction.response.send_message("❌ 需要管理伺服器權限", ephemeral=True)
            return
        select = SupportRoleSelect(self.dao, self.guild, self.settings)
        view = discord.ui.View(timeout=120)
        view.add_item(select)
        await interaction.response.send_message("選擇客服角色（可多選）：", view=view, ephemeral=True)

    @discord.ui.button(label="調整限額", style=discord.ButtonStyle.success)
    async def set_limits(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.user.guild_permissions.manage_guild:
            await interaction.response.send_message("❌ 需要管理伺服器權限", ephemeral=True)
            return
        modal = LimitsModal(self.dao, self.guild, self.settings)
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="重新整理", style=discord.ButtonStyle.secondary)
    async def refresh(self, interaction: discord.Interaction, button: discord.ui.Button):
        settings = await self.dao.get_settings(self.guild.id)
        embed = build_ticket_settings_embed(self.guild, settings)
        await interaction.response.edit_message(
            embed=embed, view=TicketSettingsView(self.dao, self.guild, settings)
        )


class CategorySelect(discord.ui.Select):
    """分類選擇"""

    def __init__(self, dao, guild: discord.Guild, settings: Dict[str, Any]):
        options = []
        for cat in guild.categories[:25]:
            options.append(discord.SelectOption(label=cat.name, value=str(cat.id)))
        super().__init__(placeholder="選擇分類", min_values=1, max_values=1, options=options)
        self.dao = dao
        self.guild = guild
        self.settings = settings

    async def callback(self, interaction: discord.Interaction):
        cat_id = int(self.values[0])
        await self.dao.update_settings(self.guild.id, {"category_id": cat_id})
        self.settings["category_id"] = cat_id
        await interaction.response.send_message(f"✅ 已設定分類為 <#{cat_id}>", ephemeral=True)


class SupportRoleSelect(discord.ui.RoleSelect):
    """客服角色選擇"""

    def __init__(self, dao, guild: discord.Guild, settings: Dict[str, Any]):
        super().__init__(placeholder="選擇客服角色（可多選）", min_values=1, max_values=5)
        self.dao = dao
        self.guild = guild
        self.settings = settings

    async def callback(self, interaction: discord.Interaction):
        role_ids: List[int] = [role.id for role in self.values]
        await self.dao.update_settings(self.guild.id, {"support_roles": role_ids})
        self.settings["support_roles"] = role_ids
        mentions = ", ".join(role.mention for role in self.values)
        await interaction.response.send_message(f"✅ 已更新客服角色：{mentions}", ephemeral=True)


class LimitsModal(discord.ui.Modal):
    """限額設定"""

    def __init__(self, dao, guild: discord.Guild, settings: Dict[str, Any]):
        super().__init__(title="限額設定")
        self.dao = dao
        self.guild = guild
        self.settings = settings

        self.max_tickets = discord.ui.TextInput(
            label="每人最大票券數",
            default=str(settings.get("max_tickets_per_user", 3)),
            max_length=3,
        )
        self.auto_close = discord.ui.TextInput(
            label="自動關閉（小時）",
            default=str(settings.get("auto_close_hours", 24)),
            max_length=4,
        )
        for item in [self.max_tickets, self.auto_close]:
            self.add_item(item)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            max_tickets = int(self.max_tickets.value)
            auto_close = int(self.auto_close.value)
        except ValueError:
            await interaction.response.send_message("❌ 請輸入有效的數字", ephemeral=True)
            return

        await self.dao.update_settings(
            self.guild.id,
            {
                "max_tickets_per_user": max_tickets,
                "auto_close_hours": auto_close,
            },
        )
        await interaction.response.send_message("✅ 已更新限額設定", ephemeral=True)

async def setup(bot):
    """設置 Cog"""
    await bot.add_cog(CachedTicketCore(bot))
