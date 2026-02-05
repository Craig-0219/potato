# bot/utils/error_handler.py - 全局異常處理器
"""
全局異常處理器 - 統一處理所有錯誤
提供錯誤分類、日誌記錄、用戶友善回應
"""

import asyncio
import logging
import traceback
from datetime import datetime, timezone
from typing import Any, Dict, Union

import discord
from discord.ext import commands

logger = logging.getLogger(__name__)


class GlobalErrorHandler:
    """全局錯誤處理器"""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.error_counts = {}  # 錯誤統計
        self.setup_handlers()

    def setup_handlers(self):
        """設置所有錯誤處理器"""

        @self.bot.event
        async def on_command_error(ctx, error):
            await self.handle_command_error(ctx, error)

        @self.bot.event
        async def on_error(event, *args, **kwargs):
            await self.handle_generic_error(event, *args, **kwargs)

        @self.bot.tree.error
        async def on_app_command_error(
            interaction: discord.Interaction,
            error: discord.app_commands.AppCommandError,
        ):
            await self.handle_interaction_error(interaction, error)

    async def handle_command_error(self, ctx: commands.Context, error: Exception):
        """處理傳統命令錯誤"""
        error_type = type(error).__name__
        self._log_error(error_type, error, ctx)

        # 如果是互動，檢查是否已經回應過
        if (
            hasattr(ctx, "interaction")
            and ctx.interaction
            and hasattr(ctx.interaction, "response")
            and ctx.interaction.response.is_done()
        ):
            return

        try:
            if isinstance(error, commands.CommandNotFound):
                # 檢查是否是票券相關指令的常見錯誤
                if ctx.message and ctx.message.content:
                    content = ctx.message.content.lower()
                    if any(
                        keyword in content
                        for keyword in [
                            "set_ticket_category",
                            "ticket",
                            "category",
                        ]
                    ):
                        await self._handle_ticket_command_help(ctx, content)
                        return
                # 其他命令不存在，靜默處理
                return

            elif isinstance(error, commands.MissingPermissions):
                embed = self._create_error_embed(
                    "權限不足",
                    f"❌ 你需要以下權限才能使用此命令：\n`{', '.join(error.missing_permissions)}`",
                )
                await ctx.send(embed=embed)

            elif isinstance(error, commands.MissingRequiredArgument):
                embed = self._create_error_embed(
                    "參數缺失",
                    f"❌ 缺少必要參數：`{error.param.name}`\n\n使用 `{ctx.prefix}help {ctx.command.name}` 查看正確用法",
                )
                await ctx.send(embed=embed)

            elif isinstance(error, commands.BadArgument):
                embed = self._create_error_embed("參數錯誤", f"❌ 參數格式錯誤：{str(error)}")
                await ctx.send(embed=embed)

            elif isinstance(error, commands.CommandOnCooldown):
                embed = self._create_error_embed(
                    "命令冷卻中",
                    f"⏰ 命令冷卻中，請在 {error.retry_after:.1f} 秒後重試",
                )
                await ctx.send(embed=embed)

            elif isinstance(error, commands.BotMissingPermissions):
                embed = self._create_error_embed(
                    "機器人權限不足",
                    f"❌ 機器人缺少以下權限：\n`{', '.join(error.missing_permissions)}`\n\n請聯繫伺服器管理員",
                )
                await ctx.send(embed=embed)

            elif isinstance(error, commands.NotOwner):
                embed = self._create_error_embed("權限不足", "❌ 此命令只有機器人擁有者可以使用")
                await ctx.send(embed=embed)

            else:
                # 未知錯誤
                error_id = self._generate_error_id()
                embed = self._create_error_embed(
                    "系統錯誤",
                    f"❌ 執行命令時發生錯誤\n\n錯誤ID：`{error_id}`\n如問題持續，請聯繫管理員",
                )
                await ctx.send(embed=embed)

                # 記錄詳細錯誤
                logger.error(f"命令錯誤 [{error_id}] - {ctx.command.name}: {error}")
                logger.error(traceback.format_exc())

        except Exception as e:
            logger.error(f"處理命令錯誤時發生錯誤：{e}")

    async def handle_interaction_error(
        self,
        interaction: discord.Interaction,
        error: discord.app_commands.AppCommandError,
    ):
        """處理斜線命令/互動錯誤"""
        error_type = type(error).__name__
        self._log_error(error_type, error, interaction)

        try:
            # 檢查是否是互動超時或已失效
            if "Unknown interaction" in str(error) or "10062" in str(error):
                logger.warning(f"互動已超時或失效: {error}")
                return  # 靜默處理，不嘗試回應

            # 檢查是否已經確認互動
            if "already been acknowledged" in str(error) or "40060" in str(error):
                logger.warning(f"互動已被確認: {error}")
                return  # 靜默處理

            # 檢查是否已經回應
            if interaction.response.is_done():
                send_func = interaction.followup.send
            else:
                send_func = interaction.response.send_message

            if isinstance(error, discord.app_commands.MissingPermissions):
                embed = self._create_error_embed("權限不足", "❌ 你沒有權限使用此命令")
                await send_func(embed=embed, ephemeral=True)

            elif isinstance(error, discord.app_commands.CommandOnCooldown):
                embed = self._create_error_embed(
                    "命令冷卻中",
                    f"⏰ 命令冷卻中，請在 {error.retry_after:.1f} 秒後重試",
                )
                await send_func(embed=embed, ephemeral=True)

            elif isinstance(error, discord.app_commands.BotMissingPermissions):
                embed = self._create_error_embed(
                    "機器人權限不足",
                    "❌ 機器人缺少必要權限\n請聯繫伺服器管理員",
                )
                await send_func(embed=embed, ephemeral=True)

            elif isinstance(error, discord.app_commands.TransformerError):
                embed = self._create_error_embed("參數錯誤", f"❌ 參數格式錯誤：{str(error)}")
                await send_func(embed=embed, ephemeral=True)

            else:
                # 未知錯誤
                error_id = self._generate_error_id()
                embed = self._create_error_embed(
                    "系統錯誤",
                    f"❌ 執行命令時發生錯誤\n\n錯誤ID：`{error_id}`\n如問題持續，請聯繫管理員",
                )
                await send_func(embed=embed, ephemeral=True)

                # 記錄詳細錯誤
                command_name = getattr(interaction.command, "name", "unknown")
                logger.error(f"互動錯誤 [{error_id}] - {command_name}: {error}")
                logger.error(traceback.format_exc())

        except Exception as e:
            # 如果是互動相關的錯誤，不記錄為嚴重錯誤
            if any(
                keyword in str(e).lower()
                for keyword in [
                    "unknown interaction",
                    "already been acknowledged",
                    "interaction has already",
                ]
            ):
                logger.debug(f"忽略互動相關錯誤: {e}")
                return

            logger.error(f"處理命令錯誤時發生異常: {e}")

    async def handle_generic_error(self, event: str, *args, **kwargs):
        """處理一般事件錯誤"""
        error_id = self._generate_error_id()
        logger.error(f"事件錯誤 [{error_id}] - {event}: {args}")

        # 記錄錯誤統計
        self.error_counts[event] = self.error_counts.get(event, 0) + 1

        # 如果是 View 相關錯誤，嘗試處理
        if "view" in event.lower() or "interaction" in event.lower():
            await self._handle_view_error(event, *args, **kwargs)

    async def _handle_view_error(self, event: str, *args, **kwargs):
        """處理 View 相關錯誤"""
        try:
            # 如果是互動失敗，嘗試回應用戶
            if args and isinstance(args[0], discord.Interaction):
                interaction = args[0]
                if not interaction.response.is_done():
                    embed = self._create_error_embed(
                        "互動失敗", "❌ 互動處理失敗，請重試或聯繫管理員"
                    )
                    await interaction.response.send_message(embed=embed, ephemeral=True)
        except Exception as e:
            logger.error(f"處理 View 錯誤時發生錯誤：{e}")

    async def _handle_ticket_command_help(self, ctx: commands.Context, content: str):
        """處理票券指令錯誤並提供幫助"""
        # 忽略已移除的舊指令名稱，避免多餘提示
        if "ticket_settings" in content:
            return
        embed = discord.Embed(
            title="❓ 票券指令使用說明",
            description="看起來您在使用票券指令時遇到了問題，以下是正確的使用方式：",
            color=0x3498DB,
            timestamp=datetime.now(timezone.utc),
        )

        if "set_ticket_category" in content:
            embed.add_field(
                name="🎯 設定票券分類頻道",
                value="已改為使用 `/ticket_settings` 進行分類/客服角色/限額設定。\n請使用 `/ticket_settings` 進入設定面板。",
                inline=False,
            )
        else:
            embed.add_field(
                name="🎫 常用票券指令",
                value="`!setup_ticket` - 建立票券面板\n"
                "`!ticket_help` - 查看票券使用說明\n"
                "`/ticket_settings` - 設定分類/客服角色/限額",
                inline=False,
            )

        embed.set_footer(text="💡 確保指令和參數之間有空格")
        await ctx.send(embed=embed)

    def _create_error_embed(self, title: str, description: str) -> discord.Embed:
        """創建錯誤嵌入"""
        embed = discord.Embed(
            title=title,
            description=description,
            color=discord.Color.red(),
            timestamp=datetime.now(timezone.utc),
        )
        embed.set_footer(text="如問題持續，請聯繫伺服器管理員")
        return embed

    def _generate_error_id(self) -> str:
        """生成錯誤ID"""
        import random
        import string

        return "".join(random.choices(string.ascii_uppercase + string.digits, k=8))

    def _log_error(
        self,
        error_type: str,
        error: Exception,
        context: Union[commands.Context, discord.Interaction],
    ):
        """記錄錯誤"""
        # 更新錯誤統計
        self.error_counts[error_type] = self.error_counts.get(error_type, 0) + 1

        # 構建上下文信息
        if isinstance(context, commands.Context):
            ctx_info = f"Guild: {context.guild.id if context.guild else 'DM'}, User: {context.author.id}, Command: {context.command.name if context.command else 'unknown'}"
        elif isinstance(context, discord.Interaction):
            command_name = getattr(context.command, "name", "unknown")
            ctx_info = f"Guild: {context.guild.id if context.guild else 'DM'}, User: {context.user.id}, Command: {command_name}"
        else:
            ctx_info = "Unknown context"

        logger.error(f"錯誤類型: {error_type} | 上下文: {ctx_info} | 錯誤: {str(error)}")

    def get_error_stats(self) -> Dict[str, Any]:
        """取得錯誤統計"""
        total_errors = sum(self.error_counts.values())
        return {
            "total_errors": total_errors,
            "error_types": dict(
                sorted(self.error_counts.items(), key=lambda x: x[1], reverse=True)
            ),
            "top_errors": dict(
                list(
                    sorted(
                        self.error_counts.items(),
                        key=lambda x: x[1],
                        reverse=True,
                    )
                )[:5]
            ),
        }

    def reset_error_stats(self):
        """重置錯誤統計"""
        self.error_counts.clear()
        logger.info("錯誤統計已重置")


# ===== 數據庫錯誤包裝器 =====


class DatabaseErrorHandler:
    """資料庫錯誤處理器"""

    @staticmethod
    def wrap_db_operation(func):
        """資料庫操作錯誤包裝裝飾器"""

        async def wrapper(*args, **kwargs):
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                operation_name = func.__name__
                logger.error(f"資料庫操作失敗 [{operation_name}]: {e}")
                logger.error(traceback.format_exc())

                # 返回標準化錯誤結果
                return {
                    "success": False,
                    "error": str(e),
                    "error_type": type(e).__name__,
                    "operation": operation_name,
                }

        return wrapper

    @staticmethod
    async def execute_with_fallback(primary_func, fallback_func, *args, **kwargs):
        """帶後備方案的執行"""
        try:
            return await primary_func(*args, **kwargs)
        except Exception as e:
            logger.warning(f"主要操作失敗，使用後備方案: {e}")
            try:
                return await fallback_func(*args, **kwargs)
            except Exception as fallback_error:
                logger.error(f"後備方案也失敗: {fallback_error}")
                raise


# ===== 服務錯誤處理器 =====


class ServiceErrorHandler:
    """服務層錯誤處理器"""

    @staticmethod
    def handle_service_error(service_name: str):
        """服務錯誤處理裝飾器"""

        def decorator(func):
            async def wrapper(*args, **kwargs):
                try:
                    result = await func(*args, **kwargs)
                    if isinstance(result, dict) and result.get("success") is False:
                        logger.warning(
                            f"服務操作返回失敗 [{service_name}.{func.__name__}]: {result.get('error')}"
                        )
                    return result
                except Exception as e:
                    error_msg = f"服務錯誤 [{service_name}.{func.__name__}]: {str(e)}"
                    logger.error(error_msg)
                    logger.error(traceback.format_exc())

                    return {
                        "success": False,
                        "error": str(e),
                        "error_type": type(e).__name__,
                        "service": service_name,
                        "operation": func.__name__,
                    }

            return wrapper

        return decorator


# ===== 用戶友善錯誤回應 =====


class UserFriendlyErrors:
    """用戶友善錯誤訊息"""

    ERROR_TRANSLATIONS = {
        "ConnectionError": "🔌 網路連接問題，請稍後再試",
        "TimeoutError": "⏰ 操作超時，請稍後再試",
        "PermissionError": "🔒 權限不足，請聯繫管理員",
        "ValidationError": "📝 輸入格式錯誤，請檢查後重試",
        "DatabaseError": "💾 資料庫暫時無法使用，請稍後再試",
        "RateLimitError": "🚀 操作太頻繁，請稍後再試",
    }

    @classmethod
    def get_user_message(cls, error_type: str, default_message: str = None) -> str:
        """取得用戶友善的錯誤訊息"""
        user_message = cls.ERROR_TRANSLATIONS.get(error_type)
        if user_message:
            return user_message

        if default_message:
            return f"❌ {default_message}"

        return "❌ 發生未知錯誤，請稍後再試或聯繫管理員"


# ===== 錯誤恢復機制 =====


class ErrorRecovery:
    """錯誤恢復機制"""

    @staticmethod
    async def retry_with_backoff(func, max_retries: int = 3, base_delay: float = 1.0):
        """指數退避重試機制"""
        for attempt in range(max_retries):
            try:
                return await func()
            except Exception as e:
                if attempt == max_retries - 1:
                    raise e

                delay = base_delay * (2**attempt)
                logger.warning(f"操作失敗，{delay}秒後重試 ({attempt + 1}/{max_retries}): {e}")
                await asyncio.sleep(delay)

    @staticmethod
    async def graceful_shutdown(bot: commands.Bot, error: Exception):
        """優雅關機"""
        logger.critical(f"嚴重錯誤，執行優雅關機: {error}")

        try:
            # 嘗試通知重要頻道
            for guild in bot.guilds:
                for channel in guild.text_channels:
                    if channel.name in [
                        "general",
                        "announcements",
                        "bot-status",
                    ]:
                        try:
                            embed = discord.Embed(
                                title="🚨 系統維護",
                                description="機器人正在進行緊急維護，請稍後再試",
                                color=discord.Color.red(),
                            )
                            await channel.send(embed=embed)
                            break
                        except:
                            continue
                break
        except:
            pass

        # 關閉機器人
        await bot.close()


# ===== 初始化函數 =====


def setup_error_handling(bot: commands.Bot) -> GlobalErrorHandler:
    """設置全局錯誤處理"""
    error_handler = GlobalErrorHandler(bot)
    logger.info("✅ 全局錯誤處理器已設置")
    return error_handler
