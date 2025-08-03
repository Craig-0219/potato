# bot/main.py - 專業重構版（修復版）
"""
Discord Bot 主程式 - 修復版
修復點：
1. 整合全局錯誤處理
2. 改善 Persistent View 註冊
3. 添加健康檢查和監控
4. 強化啟動流程
"""
import os
import sys
import asyncio
import signal
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
from bot.utils.error_handler import setup_error_handling
from bot.register.register import register_all_views, validate_view_registration

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
            description="Potato Bot - 票券系統與投票系統（修復版）"
        )
        self.initial_extensions = [COGS_PREFIX + ext for ext in ALL_EXTENSIONS]
        self.error_handler = None
        self.startup_time = None

    async def setup_hook(self):
        """Bot 設定鉤子（修復版）"""
        logger.info("🚀 Bot 設定開始...")
        
        try:
            # 1. 設置全局錯誤處理
            self.error_handler = setup_error_handling(self)
            logger.info("✅ 錯誤處理器已設置")
            
            # 2. 初始化資料庫
            await self._init_database()
            
            # 3. 載入擴展
            await self._load_extensions()
            
            # 4. 註冊 Persistent Views
            await self._register_views()
            
            # 5. 同步命令樹
            await self._sync_commands()
            
            logger.info("✅ Bot 設定完成")
            
        except Exception as e:
            logger.error(f"❌ Bot 設定失敗：{e}")
            raise

    async def _init_database(self):
        """初始化資料庫"""
        try:
            await init_database(DB_HOST, DB_PORT, DB_USER, DB_PASSWORD, DB_NAME)
            
            # 健康檢查
            health = await get_db_health()
            if health.get("overall_status") == "healthy":
                logger.info("✅ 資料庫連接成功")
            else:
                logger.warning(f"⚠️ 資料庫狀態：{health}")
                
        except Exception as e:
            logger.error(f"❌ 資料庫連接失敗：{e}")
            raise

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

    async def _register_views(self):
        """註冊 Persistent Views"""
        try:
            register_all_views(self)
            
            # 驗證註冊結果
            validation = validate_view_registration(self)
            if validation.get("has_persistent_views"):
                logger.info(f"✅ Persistent Views 註冊完成（{validation.get('persistent_view_count', 0)} 個）")
            else:
                logger.warning("⚠️ 沒有 Persistent Views 被註冊")
                
        except Exception as e:
            logger.error(f"❌ Persistent Views 註冊失敗：{e}")

    async def _sync_commands(self):
        """同步命令樹"""
        try:
            synced = await self.tree.sync()
            logger.info(f"✅ 同步了 {len(synced)} 個斜線命令")
        except Exception as e:
            logger.error(f"❌ 同步命令失敗：{e}")

    async def on_ready(self):
        """Bot 準備完成"""
        self.startup_time = discord.utils.utcnow()
        
        logger.info(f"🤖 Bot 已登入：{self.user} (ID: {self.user.id})")
        logger.info(f"📊 已連接到 {len(self.guilds)} 個伺服器")
        
        # 設置狀態
        activity = discord.Activity(
            type=discord.ActivityType.watching,
            name="票券系統 | /help"
        )
        await self.change_presence(activity=activity)
        
        # 輸出啟動資訊
        await self._log_startup_info()

    async def _log_startup_info(self):
        """記錄啟動資訊"""
        try:
            # 收集系統資訊
            import psutil
            import platform
            
            system_info = {
                "Python": platform.python_version(),
                "Discord.py": discord.__version__,
                "平台": platform.system(),
                "CPU": f"{psutil.cpu_count()} 核心",
                "記憶體": f"{psutil.virtual_memory().total // (1024**3)} GB"
            }
            
            logger.info("📋 系統資訊：")
            for key, value in system_info.items():
                logger.info(f"  {key}: {value}")
                
        except ImportError:
            logger.info("📋 系統資訊收集需要 psutil 套件")
        except Exception as e:
            logger.warning(f"收集系統資訊失敗：{e}")

    async def on_guild_join(self, guild):
        """加入新伺服器"""
        logger.info(f"🆕 加入新伺服器：{guild.name} (ID: {guild.id}, 成員: {guild.member_count})")
        try:
            # 初始化伺服器設定
            from bot.db.ticket_dao import TicketDAO
            repository = TicketDAO()
            await repository.create_default_settings(guild.id)
            logger.info(f"✅ 已為 {guild.name} 建立預設設定")
        except Exception as e:
            logger.error(f"❌ 初始化伺服器設定失敗：{e}")

    async def on_guild_remove(self, guild):
        """離開伺服器"""
        logger.info(f"👋 離開伺服器：{guild.name} (ID: {guild.id})")

    async def close(self):
        """Bot 關閉"""
        logger.info("🔄 Bot 正在關閉...")
        try:
            # 關閉資料庫連接
            await close_database()
            logger.info("✅ 資料庫連接已關閉")
        except Exception as e:
            logger.error(f"❌ 關閉資料庫連接錯誤：{e}")
        
        # 調用父類關閉方法
        await super().close()
        logger.info("✅ Bot 已關閉")

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

# ===== 管理指令（修復版） =====

@commands.command(name='reload')
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

@commands.command(name='load')
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

@commands.command(name='unload')
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

@commands.command(name='sync')
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

@commands.command(name='status')
@commands.is_owner()
async def bot_status(ctx):
    """Bot 狀態"""
    try:
        # 收集狀態資訊
        db_health = await get_db_health()
        
        from bot.utils.embed_builder import EmbedBuilder
        
        embed = EmbedBuilder.status_embed({
            "overall_status": "healthy" if db_health.get('overall_status') == 'healthy' else "degraded",
            "基本資訊": {
                "伺服器數量": len(ctx.bot.guilds),
                "延遲": f"{round(ctx.bot.latency * 1000)}ms",
                "運行時間": ctx.bot.get_uptime()
            },
            "資料庫": {
                "狀態": db_health.get('overall_status', 'unknown'),
                "大小": f"{db_health.get('database', {}).get('size_mb', 0)} MB"
            },
            "擴展": {
                "已載入": len(ctx.bot.extensions),
                "列表": ", ".join([ext.split('.')[-1] for ext in ctx.bot.extensions])
            }
        })
        
        # 錯誤統計
        if ctx.bot.error_handler:
            error_stats = ctx.bot.error_handler.get_error_stats()
            if error_stats['total_errors'] > 0:
                embed.add_field(
                    name="錯誤統計",
                    value=f"總錯誤數：{error_stats['total_errors']}\n前三錯誤：{', '.join(list(error_stats['top_errors'].keys())[:3])}",
                    inline=False
                )
        
        await ctx.send(embed=embed)
        
    except Exception as e:
        await ctx.send(f"❌ 取得狀態失敗：{e}")
        logger.error(f"取得狀態失敗：{e}")

@commands.command(name='health')
@commands.is_owner()
async def health_check(ctx):
    """健康檢查"""
    try:
        # 詳細健康檢查
        checks = {
            "資料庫連接": False,
            "命令同步": False,
            "Persistent Views": False,
            "擴展載入": False
        }
        
        # 檢查資料庫
        try:
            db_health = await get_db_health()
            checks["資料庫連接"] = db_health.get('overall_status') == 'healthy'
        except:
            pass
        
        # 檢查命令
        checks["命令同步"] = len(ctx.bot.tree.get_commands()) > 0
        
        # 檢查 Views
        validation = validate_view_registration(ctx.bot)
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
        
        from bot.utils.embed_builder import EmbedBuilder
        embed = EmbedBuilder.build(
            title=f"{overall_emoji} 健康檢查結果",
            description=status_text,
            color='success' if all_healthy else 'warning'
        )
        
        await ctx.send(embed=embed)
        
    except Exception as e:
        await ctx.send(f"❌ 健康檢查失敗：{e}")
        logger.error(f"健康檢查失敗：{e}")

@commands.command(name='restart')
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
    
    # 建立 Bot 實例
    bot = PotatoBot()
    
    # 添加管理指令
    bot.add_command(reload_extension)
    bot.add_command(load_extension)
    bot.add_command(unload_extension)
    bot.add_command(sync_commands)
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
    required_modules = ['discord', 'aiomysql', 'dotenv']
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