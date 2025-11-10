# bot/main.py - 專業重構版（修復版 + 離線模式支援）
"""
Discord Bot 主程式 - 修復版
修復點：
1. 整合全局錯誤處理
2. 改善 Persistent View 註冊
3. 添加健康檢查和監控
4. 強化啟動流程
5. 新增離線模式支援
"""
import asyncio
import os
import signal
import sys
import time

# 添加專案根目錄到 Python 路徑 - 多種路徑支援
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)

# 確保專案根目錄在 Python 路徑中
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# 託管環境路徑修復 - 檢查常見的託管目錄結構
possible_roots = [
    project_root,
    os.path.dirname(project_root),  # 如果在子目錄中
    "/home/container",  # 常見託管環境路徑
    os.getcwd(),  # 當前工作目錄
]

for root_path in possible_roots:
    shared_path = os.path.join(root_path, "shared")
    if os.path.exists(shared_path) and root_path not in sys.path:
        sys.path.insert(0, root_path)
        print(f"🔧 添加路徑: {root_path}")
        break

import discord
from discord.ext import commands
from dotenv import load_dotenv

# 路徑校正（確保可本地、主機啟動）
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# logger fallback
try:
    from potato_shared.logger import logger
except ImportError:
    import logging

    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger("potato-bot")

# config fallback
try:
    from potato_shared.config import (
        DB_HOST,
        DB_NAME,
        DB_PASSWORD,
        DB_PORT,
        DB_USER,
        DISCORD_TOKEN,
        SYNC_COMMANDS,
    )
except ImportError:
    logger.error("❌ potato_shared/config.py 不存在或設定不齊全")
    sys.exit(1)

# 離線模式支援
try:
    from potato_shared.offline_mode_manager import (
        auto_configure_environment,
        is_offline_mode,
    )

    # API 功能已移除

    OFFLINE_MODE_AVAILABLE = True
except ImportError as e:
    logger.warning(f"離線模式模組不可用: {e}")
    OFFLINE_MODE_AVAILABLE = False

import threading

# API Server 已移除
API_AVAILABLE = False
from bot.db.pool import close_database, db_pool, get_db_health, init_database
from bot.services.guild_manager import GuildManager

# Views現在由各個Cog自行註冊，不需要集中註冊


COGS_PREFIX = "potato_bot.cogs."
ALL_EXTENSIONS = [
    # 核心功能模組
    "ticket_core",
    "ticket_listener",
    "vote_core",
    "vote_listener",
    "welcome_core",
    "welcome_listener",
    "system_admin_core",
    "language_core",
    "workflow_core",
    "webhook_core",
    # 娛樂功能模組
    "entertainment_core",
    "music_core",
    "image_tools_core",  # 圖片處理工具
    "security_admin_core",  # 企業級安全管理
    "guild_management_core",  # 伺服器管理與GDPR合規
    "menu_core",  # GUI 選單系統
    "fallback_commands",  # 備用前綴命令系統
    "auto_updater",  # 內部自動更新器
    # 之前移除的模組:
    # "lottery_core" - 抽獎系統
    # "game_core" - 遊戲娛樂功能
    # "web_auth_core" - Web 認證 (已移除)
    # "ai_core" - AI 核心 (已移除)
    # "ai_assistant_core" - AI 助手 (已移除)
    # "content_analysis_core" - 內容分析 (已移除)
    # "cross_platform_economy_core" - 跨平台經濟 (已移除)
    # "dashboard_core" - 儀表板 (已移除)
]

# 全域 Bot 實例
bot = None


class PotatoBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.guilds = True
        intents.guild_messages = True
        intents.dm_messages = True
        intents.members = True  # 重要：需要此權限來接收 on_member_join/remove 事件

        super().__init__(
            command_prefix=commands.when_mentioned_or("!"),
            intents=intents,
            description="Potato Bot v2.3.0 - 企業級 Discord 管理系統，整合票券、投票、歡迎系統與 Web 管理界面",
        )
        self.initial_extensions = [COGS_PREFIX + ext for ext in ALL_EXTENSIONS]
        self.error_handler = None
        self.startup_time = None
        self._shutdown_event = asyncio.Event()
        self._background_tasks = set()

        # API Server 已移除

        # 多租戶管理
        self.guild_manager = None

    async def setup_hook(self):
        """Bot 設定鉤子（修復版 + 離線模式支援）"""
        logger.info("🚀 Bot 設定開始...")
        self.start_time = time.time()  # 記錄啟動時間

        try:
            # 0. 離線模式檢測與配置
            if OFFLINE_MODE_AVAILABLE:
                await self._configure_offline_mode()

            # 1. 設置全局錯誤處理
            from potato_bot.utils.error_handler import setup_error_handling

            self.error_handler = setup_error_handling(self)
            logger.info("✅ 錯誤處理器已設置")

            # 2. 初始化資料庫
            await self._init_database_unified()

            # 3. 載入擴展
            await self._load_extensions()

            # 4. 初始化伺服器管理服務
            await self._init_guild_services()

            # 5. 註冊 Persistent Views
            await self._register_views_delayed()

            # 6. 同步命令樹
            await self._sync_commands()

            # 7. 啟動 API Server（智能選擇）
            await self._start_api_server()

            logger.info("✅ Bot 設定完成")

        except Exception as e:
            logger.error(f"❌ Bot 設定失敗：{e}")
            raise

    async def _configure_offline_mode(self):
        """配置離線模式"""
        logger.info("🔍 檢測網路環境...")

        try:
            offline_manager = await auto_configure_environment()
            mode = "內網模式" if is_offline_mode() else "外網模式"
            logger.info(f"✅ 環境檢測完成 - {mode}")

            # 記錄詳細狀態
            status = offline_manager.get_status()
            logger.debug(f"離線管理器狀態: {status}")

        except Exception as e:
            logger.error(f"❌ 離線模式配置失敗: {e}")
            logger.info("⚠️ 繼續使用預設配置...")

    async def _start_api_server(self):
        """API Server 已移除 - 保留方法以避免兼容性問題"""
        logger.info("ℹ️  Web API 功能已從此版本移除")

    async def _init_database_unified(self, max_retries=3):
        """統一資料庫初始化（修正版）"""
        logger.info("🔄 開始統一資料庫初始化...")

        for attempt in range(max_retries):
            try:
                # 1. 建立連接池
                await init_database(DB_HOST, DB_PORT, DB_USER, DB_PASSWORD, DB_NAME)
                logger.info("✅ 資料庫連接池建立成功")

                # 2. 統一初始化所有表格
                from potato_bot.db.database_manager import get_database_manager

                db_manager = get_database_manager()
                await db_manager.initialize_all_tables(force_recreate=False)
                logger.info("✅ 資料庫表格初始化完成")

                # 3. 初始化投票模板系統
                from potato_bot.services.vote_template_manager import (
                    vote_template_manager,
                )

                await vote_template_manager.initialize_predefined_templates()
                logger.info("✅ 投票模板系統初始化完成")

                # 4. 健康檢查
                health = await get_db_health()
                if health.get("status") == "healthy":
                    logger.info("✅ 資料庫健康檢查通過")
                    return
                else:
                    raise Exception(f"資料庫健康檢查失敗：{health}")

            except Exception as e:
                if attempt < max_retries - 1:
                    wait_time = 2**attempt
                    logger.warning(
                        f"⚠️ 資料庫初始化失敗（嘗試 {attempt + 1}/{max_retries}），{wait_time}秒後重試：{e}"
                    )
                    await asyncio.sleep(wait_time)
                else:
                    logger.error(f"❌ 資料庫初始化最終失敗：{e}")
                    raise

    async def _init_guild_services(self):
        """初始化伺服器管理服務"""
        logger.info("🏰 初始化伺服器管理服務...")

        try:
            # 初始化伺服器管理表格
            from potato_bot.db.migrations.guild_management_tables import (
                initialize_guild_management_system,
            )

            await initialize_guild_management_system()

            # 初始化伺服器管理器
            self.guild_manager = GuildManager(self)

            # 啟動備份服務
            from potato_bot.services.backup_service import backup_service

            await backup_service.start_backup_scheduler()
            logger.info("✅ 自動備份服務已啟動")

            logger.info("✅ 伺服器管理服務初始化完成")

        except Exception as e:
            logger.error(f"❌ 伺服器管理服務初始化失敗: {e}")
            # 不拋出異常，允許 bot 繼續運行

    async def _load_extensions(self):
        """載入擴展"""
        loaded_count = 0
        failed_extensions = []

        for extension in self.initial_extensions:
            try:
                await self.load_extension(extension)
                logger.info(f"✅ 載入擴展：{extension}")
                loaded_count += 1
            except Exception as e:
                logger.error(f"❌ 載入擴展 {extension} 失敗：{e}")
                failed_extensions.append(extension)

        logger.info(f"📦 已載入 {loaded_count}/{len(self.initial_extensions)} 個擴展")

        if failed_extensions:
            logger.warning(f"⚠️ 失敗的擴展：{', '.join(failed_extensions)}")

    async def _register_views_delayed(self):
        """延遲註冊Views（現在由Cog自行處理）"""
        try:
            # Views現在由ticket_core等Cog在初始化時自動註冊
            # 這裡只做驗證
            await asyncio.sleep(1)
            validation = self._validate_persistent_views()
            if validation.get("has_persistent_views"):
                logger.info(
                    f"✅ 成功註冊 {validation['persistent_view_count']} 個 Persistent Views"
                )
                logger.info(f"📊 View註冊驗證結果：{validation}")
            else:
                logger.warning("⚠️ 沒有找到已註冊的 Persistent Views")

        except Exception as e:
            logger.error(f"❌ Views驗證失敗：{e}")

    def _validate_persistent_views(self):
        """驗證PersistentView註冊狀態"""
        try:
            validation_results = {
                "has_persistent_views": False,
                "persistent_view_count": 0,
                "view_details": [],
            }

            if hasattr(self, "persistent_views") and self.persistent_views:
                validation_results["has_persistent_views"] = True
                validation_results["persistent_view_count"] = len(self.persistent_views)

                for view in self.persistent_views:
                    view_info = {
                        "type": type(view).__name__,
                        "timeout": getattr(view, "timeout", None),
                        "children_count": (len(view.children) if hasattr(view, "children") else 0),
                    }
                    validation_results["view_details"].append(view_info)

            return validation_results

        except Exception as e:
            logger.error(f"❌ View註冊驗證失敗：{e}")
            return {
                "has_persistent_views": False,
                "persistent_view_count": 0,
                "validation_error": str(e),
            }

    async def _sync_commands(self):
        """同步命令樹（智能速率限制處理）"""
        try:
            # 檢查是否有現有命令
            existing_commands = self.tree.get_commands()
            logger.info(f"🔍 發現 {len(existing_commands)} 個本地命令等待同步")

            # 檢查是否啟用命令同步（配置控制）
            sync_enabled = SYNC_COMMANDS

            if not sync_enabled:
                logger.info("🚫 命令同步已停用（SYNC_COMMANDS=false）")
                logger.info("💡 如需啟用同步，請設定 SYNC_COMMANDS=true")
                return

            # 先檢查現有的 Discord 命令
            try:
                discord_commands = await self.http.get_global_commands(self.application_id)
                if discord_commands and len(discord_commands) > 0:
                    logger.info(f"✅ Discord 已有 {len(discord_commands)} 個註冊命令，跳過同步")
                    return
            except Exception:
                pass  # 如果檢查失敗，繼續嘗試同步

            # 嘗試同步，但如果遇到速率限制就跳過
            synced = await self.tree.sync()
            logger.info(f"✅ 同步了 {len(synced)} 個斜線命令")

        except discord.HTTPException as e:
            if "429" in str(e) or "Too Many Requests" in str(e):
                logger.warning("⚠️ 遇到速率限制，停用自動同步")
                logger.info("💡 請等待 24 小時後重試，或設定 SYNC_COMMANDS=false 停用同步")
                # 設定環境變數停用後續同步嘗試
                import os

                os.environ["SYNC_COMMANDS"] = "false"
            else:
                logger.error(f"❌ 同步命令失敗：{e}")
        except Exception as e:
            logger.error(f"❌ 同步命令失敗：{e}")

    async def _start_integrated_api_server(self):
        """API Server 已移除"""
        pass

    async def close(self):
        """關閉 Bot 和整合服務"""
        try:
            logger.info("🔄 正在關閉 Bot 和整合服務...")

            # 關閉相關服務
            if hasattr(self, "backup_service") and self.backup_service:
                await self.backup_service.stop()

            # API 伺服器已移除

            # 關閉資料庫連接
            try:
                await close_database()
                logger.info("✅ 資料庫連接已關閉")
            except Exception as e:
                logger.error(f"❌ 關閉資料庫時發生錯誤：{e}")

            # 關閉 Discord Bot
            await super().close()
            logger.info("✅ Discord Bot 已關閉")
        except Exception as e:
            logger.error(f"❌ 關閉 Bot 時發生錯誤: {e}")

    async def on_ready(self):
        """Bot 準備完成"""
        self.startup_time = discord.utils.utcnow()

        logger.info(f"🤖 Bot 已登入：{self.user} (ID: {self.user.id})")
        logger.info(f"📊 已連接到 {len(self.guilds)} 個伺服器")

        # 設置狀態 - v2.2.0 創意內容生成版本
        activity = discord.Activity(
            type=discord.ActivityType.watching,
            name="v2.2.0 AI助手+音樂+圖片 | /help",
        )
        await self.change_presence(activity=activity)

        # 輸出啟動資訊
        await self._log_startup_info()

        # 初始化現有伺服器的多租戶設定
        if self.guild_manager:
            await self._initialize_existing_guilds()

    async def _log_startup_info(self):
        """記錄啟動資訊"""
        try:
            # 收集系統資訊
            import platform

            import psutil

            system_info = {
                "Python": platform.python_version(),
                "Discord.py": discord.__version__,
                "平台": platform.system(),
                "CPU": f"{psutil.cpu_count()} 核心",
                "記憶體": f"{psutil.virtual_memory().total // (1024**3)} GB",
            }

            logger.info("📋 系統資訊：")
            for key, value in system_info.items():
                logger.info(f"  {key}: {value}")

        except ImportError:
            logger.info("📋 系統資訊收集需要 psutil 套件")
        except Exception as e:
            logger.warning(f"收集系統資訊失敗：{e}")

    async def _initialize_existing_guilds(self):
        """初始化現有伺服器的多租戶設定"""
        try:
            logger.info(f"🏛️ 開始初始化 {len(self.guilds)} 個現有伺服器...")

            initialization_count = 0
            for guild in self.guilds:
                try:
                    # 檢查是否已存在伺服器記錄
                    async with db_pool.connection() as conn:
                        async with conn.cursor() as cursor:
                            await cursor.execute(
                                "SELECT COUNT(*) FROM guild_info WHERE guild_id = %s",
                                (guild.id,),
                            )
                            exists = (await cursor.fetchone())[0] > 0

                    if not exists:
                        # 只初始化新的伺服器
                        await self.guild_manager.initialize_guild(guild)
                        initialization_count += 1
                        logger.info(f"✅ 初始化伺服器: {guild.name}")
                    else:
                        logger.debug(f"跳過伺服器初始化: {guild.name}")

                except Exception as guild_error:
                    logger.error(f"初始化伺服器 {guild.name} 失敗: {guild_error}")

            logger.info(f"✅ 完成初始化 {initialization_count} 個新伺服器")

        except Exception as e:
            logger.error(f"初始化現有伺服器失敗: {e}")

    def get_uptime(self) -> str:
        """取得運行時間"""
        if not self.startup_time:
            return "未知"

        delta = discord.utils.utcnow() - self.startup_time
        days = delta.days
        hours, remainder = divmod(delta.seconds, 3600)
        minutes, seconds = divmod(remainder, 60)

        if days > 0:
            return f"{days}天 {hours}小時 {minutes}分鐘"
        elif hours > 0:
            return f"{hours}小時 {minutes}分鐘"
        else:
            return f"{minutes}分鐘 {seconds}秒"

    def create_background_task(self, coro):
        """創建背景任務（修復Task tracking）"""
        task = asyncio.create_task(coro)
        self._background_tasks.add(task)
        task.add_done_callback(self._background_tasks.discard)
        return task


# ===== 第一組重複指令已移除，保留後面完整版本 =====


@commands.command(name="reload")
@commands.is_owner()
async def reload_extension(ctx, extension_name: str):
    """重新載入擴展"""
    try:
        await ctx.bot.reload_extension(COGS_PREFIX + extension_name)
        await ctx.send(f"✅ 重新載入擴展：{extension_name}")
        logger.info(f"重新載入擴展：{extension_name}")
    except Exception as e:
        await ctx.send(f"❌ 重新載入失敗：{e}")
        logger.error(f"重新載入擴展失敗：{e}")


@commands.command(name="load")
@commands.is_owner()
async def load_extension(ctx, extension_name: str):
    """載入擴展"""
    try:
        await ctx.bot.load_extension(COGS_PREFIX + extension_name)
        await ctx.send(f"✅ 載入擴展：{extension_name}")
        logger.info(f"載入擴展：{extension_name}")
    except Exception as e:
        await ctx.send(f"❌ 載入失敗：{e}")
        logger.error(f"載入擴展失敗：{e}")


@commands.command(name="unload")
@commands.is_owner()
async def unload_extension(ctx, extension_name: str):
    """卸載擴展"""
    try:
        await ctx.bot.unload_extension(COGS_PREFIX + extension_name)
        await ctx.send(f"✅ 卸載擴展：{extension_name}")
        logger.info(f"卸載擴展：{extension_name}")
    except Exception as e:
        await ctx.send(f"❌ 卸載失敗：{e}")
        logger.error(f"卸載擴展失敗：{e}")


@commands.command(name="sync")
@commands.is_owner()
async def sync_commands(ctx):
    """同步命令"""
    try:
        synced = await ctx.bot.tree.sync()
        await ctx.send(f"✅ 同步了 {len(synced)} 個命令")
        logger.info(f"同步了 {len(synced)} 個命令")
    except Exception as e:
        await ctx.send(f"❌ 同步失敗：{e}")
        logger.error(f"同步命令失敗：{e}")


@commands.command(name="dbstatus")
@commands.is_owner()
async def database_status(ctx):
    """資料庫狀態"""
    try:
        from potato_bot.db.database_manager import get_database_manager

        db_manager = get_database_manager()
        status = await db_manager.get_database_status()

        embed = discord.Embed(
            title="📊 資料庫狀態",
            color=(discord.Color.green() if status.get("healthy") else discord.Color.orange()),
        )

        # 基本資訊
        embed.add_field(
            name="連接資訊",
            value=f"狀態：{'✅ 正常' if status.get('healthy') else '⚠️ 異常'}\n版本：{status.get('version', 'Unknown')}",
            inline=True,
        )

        # 表格統計
        if status.get("tables"):
            table_info = []
            for table, count in status["tables"].items():
                table_info.append(f"• {table}: {count} 筆")
            embed.add_field(
                name="資料表",
                value="\n".join(table_info[:5]),
                inline=True,  # 限制顯示數量
            )

        await ctx.send(embed=embed)

    except Exception as e:
        await ctx.send(f"❌ 取得資料庫狀態失敗：{e}")
        logger.error(f"取得資料庫狀態失敗：{e}")


@commands.command(name="status")
@commands.is_owner()
async def bot_status(ctx):
    """Bot 狀態"""
    try:
        # 收集狀態資訊
        db_health = await get_db_health()

        from potato_bot.utils.embed_builder import EmbedBuilder

        embed = EmbedBuilder.status_embed(
            {
                "overall_status": (
                    "healthy" if db_health.get("status") == "healthy" else "degraded"
                ),
                "基本資訊": {
                    "伺服器數量": len(ctx.bot.guilds),
                    "延遲": (
                        f"{round(ctx.bot.latency * 1000)}ms"
                        if ctx.bot.latency is not None and not (ctx.bot.latency != ctx.bot.latency)
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
                    "列表": ", ".join([ext.split(".")[-1] for ext in ctx.bot.extensions]),
                },
            }
        )

        # 錯誤統計
        if ctx.bot.error_handler:
            error_stats = ctx.bot.error_handler.get_error_stats()
            if error_stats["total_errors"] > 0:
                embed.add_field(
                    name="錯誤統計",
                    value=(
                        f"總錯誤數：{error_stats['total_errors']}\n"
                        f"前三錯誤：{', '.join(list(error_stats['top_errors'].keys())[:3])}"
                    ),
                    inline=False,
                )

        await ctx.send(embed=embed)

    except Exception as e:
        await ctx.send(f"❌ 取得狀態失敗：{e}")
        logger.error(f"取得狀態失敗：{e}")


@commands.command(name="health")
@commands.is_owner()
async def health_check(ctx):
    """健康檢查"""
    try:
        # 詳細健康檢查
        checks = {
            "資料庫連接": False,
            "命令同步": False,
            "Persistent Views": False,
            "擴展載入": False,
        }

        # 檢查資料庫
        try:
            db_health = await get_db_health()
            checks["資料庫連接"] = db_health.get("status") == "healthy"
        except Exception:
            pass

        # 檢查命令
        checks["命令同步"] = len(ctx.bot.tree.get_commands()) > 0

        # 檢查 Views
        validation = ctx.bot._validate_persistent_views()
        checks["Persistent Views"] = validation.get("has_persistent_views", False)

        # 檢查擴展
        checks["擴展載入"] = len(ctx.bot.extensions) > 0

        # 建立回應
        status_text = ""
        all_healthy = True

        for check_name, is_healthy in checks.items():
            emoji = "✅" if is_healthy else "❌"
            status_text += f"{emoji} {check_name}\n"
            if not is_healthy:
                all_healthy = False

        overall_emoji = "✅" if all_healthy else "⚠️"

        from potato_bot.utils.embed_builder import EmbedBuilder

        embed = EmbedBuilder.build(
            title=f"{overall_emoji} 健康檢查結果",
            description=status_text,
            color="success" if all_healthy else "warning",
        )

        await ctx.send(embed=embed)

    except Exception as e:
        await ctx.send(f"❌ 健康檢查失敗：{e}")
        logger.error(f"健康檢查失敗：{e}")


@commands.command(name="restart")
@commands.is_owner()
async def restart_bot(ctx):
    """重啟 Bot（需要外部進程管理）"""
    await ctx.send("🔄 正在重啟 Bot...")
    logger.info("收到重啟命令")

    # 優雅關閉
    await ctx.bot.close()


# ===== 信號處理 =====


def setup_signal_handlers(bot):
    """設置信號處理器"""

    def signal_handler(signum, frame):
        logger.info(f"收到信號 {signum}，正在關閉...")
        asyncio.create_task(bot.close())

    # Unix 信號
    if sys.platform != "win32":
        signal.signal(signal.SIGTERM, signal_handler)
        signal.signal(signal.SIGINT, signal_handler)


# ===== 主函數 =====


async def main():
    """主函數"""
    load_dotenv()

    # 驗證環境變數
    if not DISCORD_TOKEN:
        logger.error("❌ 未找到 DISCORD_TOKEN，請檢查 .env 設定")
        sys.exit(1)

    # 建立 Bot 實例並設為全域變數
    global bot
    bot = PotatoBot()

    # 添加管理指令
    bot.add_command(reload_extension)
    bot.add_command(load_extension)
    bot.add_command(unload_extension)
    bot.add_command(sync_commands)
    bot.add_command(database_status)
    bot.add_command(bot_status)
    bot.add_command(health_check)
    bot.add_command(restart_bot)

    # 設置信號處理
    setup_signal_handlers(bot)

    # 啟動 Bot
    async with bot:
        try:
            logger.info("🚀 正在啟動 Potato Bot...")
            await bot.start(DISCORD_TOKEN)
        except KeyboardInterrupt:
            logger.info("收到中斷信號，正在關閉...")
        except Exception as e:
            logger.error(f"❌ Bot 運行錯誤：{e}")
            raise
        finally:
            if not bot.is_closed():
                await bot.close()


# ===== 啟動檢查 =====


def pre_startup_checks():
    """啟動前檢查"""
    checks = []

    # 檢查 Python 版本
    if sys.version_info < (3, 8):
        checks.append("❌ Python 版本必須 >= 3.8")
    else:
        checks.append(f"✅ Python {sys.version_info.major}.{sys.version_info.minor}")

    # 檢查必要模組
    required_modules = ["discord", "aiomysql", "dotenv"]
    for module in required_modules:
        try:
            __import__(module)
            checks.append(f"✅ {module}")
        except ImportError:
            checks.append(f"❌ 缺少模組：{module}")

    # 檢查環境變數
    if DISCORD_TOKEN:
        checks.append("✅ DISCORD_TOKEN")
    else:
        checks.append("❌ 缺少 DISCORD_TOKEN")

    if DB_HOST and DB_USER and DB_PASSWORD and DB_NAME:
        checks.append("✅ 資料庫設定")
    else:
        checks.append("❌ 資料庫設定不完整")

    # 輸出檢查結果
    logger.info("🔍 啟動前檢查：")
    for check in checks:
        logger.info(f"  {check}")

    # 檢查是否有失敗項目
    failed_checks = [check for check in checks if check.startswith("❌")]
    if failed_checks:
        logger.error("❌ 啟動前檢查失敗，請修復以下問題：")
        for failed in failed_checks:
            logger.error(f"  {failed}")
        return False

    logger.info("✅ 啟動前檢查通過")
    return True


# ===== 入口點 =====

if __name__ == "__main__":
    # 設置事件循環策略（Windows 相容性）
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    try:
        # 啟動前檢查
        if not pre_startup_checks():
            sys.exit(1)

        # 啟動 Bot
        asyncio.run(main())

    except KeyboardInterrupt:
        logger.info("👋 程式已終止")
    except Exception as e:
        logger.error(f"❌ 程式執行錯誤：{e}")
        import traceback

        logger.error(traceback.format_exc())
        sys.exit(1)
    finally:
        logger.info("🔚 程式已結束")
