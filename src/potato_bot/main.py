"""
Potato Bot Core v1 - Minimal 版本
---------------------------------
定位：
- ✅ 提供 Discord Bot 的「平台與底層邏輯」
- ✅ 管理 Cogs 的載入 / 卸載 / 重載（當作 Plugin 容器）
- ✅ 初始化共同 Infra（DB、錯誤處理、基本服務註冊）
- 🔁 保留部分 Domain 初始化（加上 TODO 標記，方便未來移出到各 Cog）

目標：
- 先讓機器人穩定上線
- 之後可以逐步把 TODO 區塊移回各自的 cogs / services
"""

import asyncio
import signal
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Coroutine, Set, TypeVar

# Ensure src root is on sys.path when running as a script (python src/potato_bot/main.py)
_CURRENT_FILE = Path(__file__).resolve()
_SRC_ROOT = _CURRENT_FILE.parent.parent
if str(_SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(_SRC_ROOT))

import discord
from discord.ext import commands
from dotenv import load_dotenv

from potato_bot.utils.boot import bootstrap_paths
from potato_bot.utils.interaction_helper import apply_ephemeral_delete_after_policy

# 路徑/別名初始化（先跑，後續模組才能正常 import shared/bot）
CURRENT_FILE_DIR, PROJECT_ROOT = bootstrap_paths(__file__)

from potato_bot.utils.cog_loader import COGS_PREFIX, discover_cog_modules
from potato_bot.utils.persistent_views import log_persistent_views
from potato_bot.utils.command_translator import PotatoTranslator

# 提前載入 .env，讓 shared.config 能吃到
load_dotenv()

# Auto-delete ephemeral dialogs without views after 30 seconds.
apply_ephemeral_delete_after_policy()

# ==============================
# ✅ 3. Logger / Config
# ==============================

try:
    from potato_shared.logger import logger
except ImportError:
    import logging

    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger("potato-bot")

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
    logger.error("❌ shared/config.py 不存在或設定不齊全")
    sys.exit(1)

# ==============================
# ✅ 5. DB Infra (連線層)
# ==============================

from potato_bot.db.pool import close_database, get_db_health, init_database

# 全域 Bot 實例（給部分舊代碼用）
bot: "PotatoBot | None" = None


# ==============================
# ✅ 7. PotatoBot 核心類別
# ==============================

class PotatoBot(commands.Bot):
    """
    ✅ Discord 應用核心
    - 管理啟動流程（setup_hook）
    - 管理 Cogs 載入 / 卸載 / Reload（透過 commands + extension API）
    - 管理 Infra 初始化（DB / Error handler / Offline mode）
    - 提供 services registry 給各 Cog 使用
    """

    def __init__(self) -> None:
        intents = discord.Intents.default()
        intents.message_content = True
        intents.guilds = True
        intents.guild_messages = True
        intents.dm_messages = True
        intents.members = True  # on_member_join / remove 需要

        super().__init__(
            command_prefix=commands.when_mentioned_or("!"),
            intents=intents,
            description="Potato Bot Core v1 - 模組化管理與熱插拔架構",
        )

        # Cog / Plugin 管理
        self.available_cogs = discover_cog_modules()
        self.initial_extensions = [COGS_PREFIX + ext for ext in self.available_cogs]

        # Error handler / Uptime
        self.error_handler = None
        self.startup_time: datetime | None = None

        # 背景任務追蹤
        self._background_tasks: Set[asyncio.Task[Any]] = set()

        # Service Registry：給 Cogs 拿共用服務用
        self.services: dict[str, Any] = {}

        # Guild 多租戶入口（已停用）
        self.guild_manager: None = None

    # --------------------------
    # ✅ 啟動鉤子：統一 async 初始化流程
    # --------------------------
    async def setup_hook(self) -> None:
        logger.info("🚀 Bot setup_hook 開始執行...")

        # 1) 全域錯誤處理（cross-cutting concern）
        await self._setup_error_handler()

        # 2) DB 連線池 + 全域 migrations + health check
        await self._init_database_infra()

        # 3) 初始化核心服務（已停用 guild 管理）

        # 4) 載入所有 Cogs（Plugin Orchestrator）
        await self._load_extensions()

        # 5) 指令翻譯器（本地化指令名稱/描述）
        await self._setup_translator()

        # 6) 驗證 Persistent Views（註冊在各 Cog，自這裡只檢查並記錄）
        await log_persistent_views(self)

        # 7) 同步斜線命令（依 SYNC_COMMANDS 控制）
        await self._sync_commands()

        logger.info("✅ Bot setup_hook 完成")

    # --------------------------
    # ✅ 全域錯誤處理掛載
    # --------------------------
    async def _setup_error_handler(self) -> None:
        try:
            from potato_bot.utils.error_handler import setup_error_handling

            self.error_handler = setup_error_handling(self)
            logger.info("✅ 全域錯誤處理器已設置")
        except Exception as e:
            logger.error(f"❌ 設置錯誤處理器失敗：{e}")

    # --------------------------
    # ✅ DB Infra 初始化（連線池 + migrations + health）
    # --------------------------
    async def _init_database_infra(self, max_retries: int = 3) -> None:
        logger.info("🔄 開始資料庫初始化（Infra 層）...")

        for attempt in range(max_retries):
            try:
                # 1) 建立連線池
                await init_database(DB_HOST, DB_PORT, DB_USER, DB_PASSWORD, DB_NAME)
                logger.info("✅ DB 連線池建立成功")

                # 2) 全域 migrations（初始化所有資料表架構）
                from potato_bot.db.database_manager import get_database_manager

                db_manager = get_database_manager()
                await db_manager.initialize_all_tables(force_recreate=False)
                logger.info("✅ DB 資料表初始化完成")

                # 3) DB Health Check
                health = await get_db_health()
                if health.get("status") == "healthy":
                    logger.info("✅ DB 健康檢查通過")
                    return

                raise RuntimeError(f"DB 健康檢查失敗：{health}")

            except Exception as e:
                if attempt < max_retries - 1:
                    wait_time = 2**attempt
                    logger.warning(
                        f"⚠️ DB 初始化失敗（嘗試 {attempt + 1}/{max_retries}）：{e}，"
                        f"{wait_time} 秒後重試"
                    )
                    await asyncio.sleep(wait_time)
                else:
                    logger.error(f"❌ DB 初始化最終失敗：{e}")
                    raise

    # --------------------------
    # ✅ Cogs 載入（Plugin Orchestrator）
    # --------------------------
    async def _load_extensions(self) -> None:
        loaded = 0
        failed: list[str] = []

        for ext in self.initial_extensions:
            try:
                await self.load_extension(ext)
                logger.info(f"✅ 載入 Cog：{ext}")
                loaded += 1
            except Exception as e:
                logger.error(f"❌ 載入 Cog 失敗 {ext}：{e}")
                failed.append(ext)

        logger.info(f"📦 Cog 載入結果：{loaded}/{len(self.initial_extensions)}")

        if failed:
            logger.warning(f"⚠️ 未載入的 Cogs：{', '.join(failed)}")

    async def _setup_translator(self) -> None:
        """設定指令翻譯器（支援中文指令名稱）"""
        try:
            await self.tree.set_translator(PotatoTranslator())
            logger.info("✅ 指令翻譯器已設置")
        except Exception as e:
            logger.error(f"❌ 設置指令翻譯器失敗：{e}")

    # --------------------------
    # ✅ 指令同步（平台級）
    # --------------------------
    async def _sync_commands(self) -> None:
        try:
            local_cmds = self.tree.get_commands()
            logger.info(f"🔍 本地斜線命令數量：{len(local_cmds)}")
            logger.info("📝 本地指令列表：" + ", ".join(sorted([c.qualified_name for c in local_cmds])))

            should_sync = SYNC_COMMANDS
            remote_count = 0
            try:
                remote_cmds = await self.http.get_global_commands(self.application_id)
                remote_count = len(remote_cmds or [])
            except Exception:
                remote_count = 0

            # 若本地有指令而雲端 0，強制同步一次（即使 SYNC_COMMANDS=false）
            if not should_sync and len(local_cmds) > 0 and remote_count == 0:
                logger.warning("⚠️ 雲端沒有斜線命令，本地存在，強制同步一次")
                should_sync = True

            if not should_sync:
                logger.info("🚫 SYNC_COMMANDS=false，跳過自動同步")
                return

            # 全域同步
            synced = await self.tree.sync()
            logger.info(f"✅ 成功同步 {len(synced)} 個全域斜線命令")

            # 對當前 guilds 再做一次 guild sync，加速生效
            for guild in self.guilds:
                try:
                    guild_synced = await self.tree.sync(guild=guild)
                    logger.info(
                        f"🏠 Guild sync {guild.id}: {len(guild_synced)} ("
                        + ", ".join(sorted([c.qualified_name for c in guild_synced]))
                        + ")"
                    )
                except Exception as ge:
                    logger.warning(f"⚠️ Guild sync 失敗 {guild.id}: {ge}")

        except discord.HTTPException as e:
            if "429" in str(e) or "Too Many Requests" in str(e):
                logger.warning("⚠️ 斜線命令同步遭遇 rate limit，建議暫停自動同步")
            else:
                logger.error(f"❌ 同步斜線命令失敗：{e}")
        except Exception as e:
            logger.error(f"❌ 同步斜線命令失敗：{e}")

    # --------------------------
    # ✅ 優雅關閉：Infra + Service
    # --------------------------
    async def close(self) -> None:
        logger.info("🔄 正在關閉 Potato Bot...")

        # 取消背景任務
        try:
            await self._cancel_background_tasks()
        except Exception as e:
            logger.error(f"❌ 取消背景任務時發生錯誤：{e}")

        # 關閉 DB Pool
        try:
            await close_database()
            logger.info("✅ DB 連線已關閉")
        except Exception as e:
            logger.error(f"❌ 關閉 DB 時發生錯誤：{e}")

        await super().close()
        logger.info("✅ Discord 連線已關閉")

    # --------------------------
    # ✅ lifecycle event：on_ready
    #    只放「平台級」邏輯（狀態 / Uptime / 基本 log）
    # --------------------------
    async def on_ready(self) -> None:
        if self.startup_time is None:
            self.startup_time = discord.utils.utcnow()
        logger.info(f"🤖 Bot 已登入：{self.user} (ID: {self.user.id})")
        logger.info(f"🏠 已連接 {len(self.guilds)} 個伺服器")
        if self.guilds:
            guild_list = ", ".join([f"{g.name}({g.id})" for g in self.guilds])
            logger.info(f"🧾 伺服器清單：{guild_list}")

        activity = discord.Activity(
            type=discord.ActivityType.watching,
            name="V3.0雞毛云：讀萬卷書，不如先把公告認真讀完。",
        )
        await self.change_presence(activity=activity)

    # --------------------------
    # ✅ 工具：Uptime 
    # --------------------------
    def get_uptime(self) -> str:
        if not self.startup_time:
            return "未知"

        delta = discord.utils.utcnow() - self.startup_time
        days = delta.days
        hours, rem = divmod(delta.seconds, 3600)
        minutes, seconds = divmod(rem, 60)

        if days > 0:
            return f"{days}天 {hours}小時 {minutes}分鐘"
        if hours > 0:
            return f"{hours}小時 {minutes}分鐘"
        return f"{minutes}分鐘 {seconds}秒"

    T = TypeVar("T")

    def create_background_task(
        self, coro: Coroutine[Any, Any, T], *, name: str | None = None
    ) -> asyncio.Task[T]:
        """建立並追蹤背景任務，確保關閉時能統一取消。"""
        task = asyncio.create_task(coro, name=name)
        self._background_tasks.add(task)
        task.add_done_callback(self._background_tasks.discard)
        return task

    async def _cancel_background_tasks(self) -> None:
        """優雅取消已追蹤的背景任務。"""
        if not self._background_tasks:
            return
        for task in list(self._background_tasks):
            if not task.done():
                task.cancel()
        await asyncio.gather(*self._background_tasks, return_exceptions=True)
        self._background_tasks.clear()

# ==============================
# ✅ 9. Signal / 啟動入口
# ==============================


def setup_signal_handlers(bot: PotatoBot) -> None:
    """Unix signal handler（非 Windows）。Windows fallback 使用同步 signal。"""
    if sys.platform == "win32":
        loop = asyncio.get_running_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            signal.signal(
                sig,
                lambda *_: loop.call_soon_threadsafe(loop.create_task, bot.close()),
            )
        return

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        try:
            loop.add_signal_handler(sig, lambda s=sig: loop.create_task(bot.close()))
        except NotImplementedError:
            signal.signal(sig, lambda *_: loop.create_task(bot.close()))


async def run_bot() -> None:
    """給 asyncio.run 使用的真正入口"""
    global bot

    if not DISCORD_TOKEN:
        logger.error("❌ 未設定 DISCORD_TOKEN，無法啟動 Bot")
        sys.exit(1)

    bot = PotatoBot()
    setup_signal_handlers(bot)

    try:
        async with bot:
            logger.info("🚀 正在啟動 Potato Bot Core v1...")
            await bot.start(DISCORD_TOKEN)
    except KeyboardInterrupt:
        logger.info("🧷 收到 KeyboardInterrupt，正在關閉...")
    except Exception as e:
        logger.error(f"❌ Bot 運行錯誤：{e}")
        raise


def pre_startup_checks() -> bool:
    """啟動前檢查（Python 版本 / 模組 / DB Config）"""
    checks: list[str] = []

    # Python 版本
    if sys.version_info < (3, 8):
        checks.append("❌ Python 版本必須 >= 3.8")
    else:
        checks.append(f"✅ Python {sys.version_info.major}.{sys.version_info.minor}")

    # 必要模組
    for module in ["discord", "aiomysql", "dotenv"]:
        try:
            __import__(module)
            checks.append(f"✅ {module}")
        except ImportError:
            checks.append(f"❌ 缺少模組：{module}")

    # Token / DB
    checks.append("✅ DISCORD_TOKEN" if DISCORD_TOKEN else "❌ 缺少 DISCORD_TOKEN")

    if DB_HOST and DB_USER and DB_PASSWORD and DB_NAME:
        checks.append("✅ 資料庫設定")
    else:
        checks.append("❌ 資料庫設定不完整")

    logger.info("🔍 啟動前檢查：")
    for c in checks:
        logger.info(f"  {c}")

    failed = [c for c in checks if c.startswith("❌")]
    if failed:
        logger.error("❌ 啟動前檢查失敗：")
        for f in failed:
            logger.error(f"  {f}")
        return False

    logger.info("✅ 啟動前檢查通過")
    return True


if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    try:
        if not pre_startup_checks():
            sys.exit(1)

        asyncio.run(run_bot())
    except KeyboardInterrupt:
        logger.info("👋 程式已終止")
    except Exception as e:
        logger.error(f"❌ 程式執行錯誤：{e}")
        import traceback

        logger.error(traceback.format_exc())
        sys.exit(1)
    finally:
        logger.info("🔚 程式已結束")
