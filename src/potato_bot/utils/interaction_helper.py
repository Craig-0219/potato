#!/usr/bin/env python3
"""
互動處理幫助工具
提供統一的互動錯誤處理和安全回應方法
"""

from typing import Optional

import discord

from potato_shared.logger import logger


class SafeInteractionHandler:
    """安全互動處理器"""

    @staticmethod
    async def safe_respond(
        interaction: discord.Interaction,
        content: Optional[str] = None,
        embed: Optional[discord.Embed] = None,
        view: Optional[discord.ui.View] = None,
        ephemeral: bool = True,
    ) -> bool:
        """安全回應互動，處理所有可能的錯誤情況"""
        try:
            # 檢查互動是否仍然有效
            if not interaction or not hasattr(interaction, "response"):
                logger.warning("互動對象無效或缺少response屬性")
                return False

            # 如果互動已經完成，使用 followup
            if interaction.response.is_done():
                kwargs = {"content": content, "embed": embed, "ephemeral": ephemeral}
                if view is not None:
                    kwargs["view"] = view
                await interaction.followup.send(**kwargs)
            else:
                kwargs = {"content": content, "embed": embed, "ephemeral": ephemeral}
                if view is not None:
                    kwargs["view"] = view
                await interaction.response.send_message(**kwargs)

            return True

        except discord.InteractionResponded:
            logger.debug("互動已被回應，嘗試使用 followup")
            try:
                kwargs = {"content": content, "embed": embed, "ephemeral": ephemeral}
                if view is not None:
                    kwargs["view"] = view
                await interaction.followup.send(**kwargs)
                return True
            except Exception as followup_error:
                logger.error(f"Followup 失敗: {followup_error}")
                return False
        except Exception as e:
            if "Interaction has already been acknowledged" in str(e) or "40060" in str(e):
                logger.debug("互動已被確認，忽略錯誤")
                return False
            logger.error(f"安全回應互動失敗: {e}")
            return False

    @staticmethod
    async def safe_followup(
        interaction: discord.Interaction,
        content: Optional[str] = None,
        embed: Optional[discord.Embed] = None,
        view: Optional[discord.ui.View] = None,
        ephemeral: bool = True,
    ) -> bool:
        """安全發送 followup 訊息"""
        try:
            if not interaction or not hasattr(interaction, "followup"):
                logger.warning("互動對象無效或缺少followup屬性")
                return False

            kwargs = {"content": content, "embed": embed, "ephemeral": ephemeral}
            if view is not None:
                kwargs["view"] = view
            await interaction.followup.send(**kwargs)
            return True

        except Exception as e:
            logger.error(f"安全 followup 失敗: {e}")
            return False

    @staticmethod
    async def safe_defer(interaction: discord.Interaction, ephemeral: bool = True) -> bool:
        """安全延遲互動回應"""
        try:
            if not interaction or not hasattr(interaction, "response"):
                logger.warning("互動對象無效")
                return False

            if interaction.response.is_done():
                logger.debug("互動回應已完成，無需defer")
                return True

            await interaction.response.defer(ephemeral=ephemeral)
            return True

        except discord.InteractionResponded:
            logger.debug("互動已被回應，defer 被忽略")
            return True
        except Exception as e:
            if "already been acknowledged" in str(e) or "40060" in str(e):
                logger.debug("互動已被確認，defer 被忽略")
                return True
            logger.error(f"延遲互動回應失敗: {e}")
            return False

    @staticmethod
    async def handle_interaction_error(
        interaction: discord.Interaction,
        error: Exception,
        operation_name: str = "操作",
    ) -> None:
        """統一處理互動錯誤"""
        try:
            error_message = f"❌ {operation_name}執行失敗，請稍後再試"

            # 根據錯誤類型提供不同的回應
            if isinstance(error, discord.Forbidden):
                error_message = f"❌ 沒有權限執行{operation_name}"
            elif isinstance(error, discord.NotFound):
                error_message = f"❌ {operation_name}的目標不存在"
            elif isinstance(error, discord.HTTPException):
                error_message = f"❌ {operation_name}網路請求失敗"

            # 嘗試回應錯誤訊息
            await SafeInteractionHandler.safe_respond(
                interaction, content=error_message, ephemeral=True
            )

        except Exception as handle_error:
            logger.error(f"處理互動錯誤時發生異常: {handle_error}")

    @staticmethod
    def is_interaction_valid(interaction: discord.Interaction) -> bool:
        """檢查互動是否有效"""
        try:
            return (
                interaction is not None
                and hasattr(interaction, "response")
                and hasattr(interaction, "user")
            )
        except Exception:
            return False


def apply_ephemeral_delete_after_policy(delete_after: float = 30.0) -> None:
    """Auto-delete ephemeral messages without views after a short delay."""
    if getattr(discord, "_ephemeral_delete_policy_applied", False):
        return

    setattr(discord, "_ephemeral_delete_policy_applied", True)

    original_send_message = discord.InteractionResponse.send_message

    async def patched_send_message(self, *args, **kwargs):
        if (
            kwargs.get("ephemeral")
            and kwargs.get("delete_after") is None
            and kwargs.get("view") is None
        ):
            kwargs["delete_after"] = delete_after
        return await original_send_message(self, *args, **kwargs)

    discord.InteractionResponse.send_message = patched_send_message


class InteractionContext:
    """互動上下文管理器"""

    def __init__(self, interaction: discord.Interaction, operation_name: str = "操作"):
        self.interaction = interaction
        self.operation_name = operation_name
        self.deferred = False

    async def __aenter__(self):
        """進入上下文管理器"""
        try:
            if SafeInteractionHandler.is_interaction_valid(self.interaction):
                self.deferred = await SafeInteractionHandler.safe_defer(self.interaction)
            return self
        except Exception as e:
            logger.error(f"進入互動上下文失敗: {e}")
            return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """退出上下文管理器"""
        try:
            if exc_type is not None:
                # 有例外發生時的處理
                await SafeInteractionHandler.handle_interaction_error(
                    self.interaction, exc_val, self.operation_name
                )
        except Exception as e:
            logger.error(f"退出互動上下文時發生錯誤: {e}")

    def is_valid(self) -> bool:
        """檢查上下文是否有效"""
        return SafeInteractionHandler.is_interaction_valid(self.interaction)


# 裝飾器版本
def safe_interaction(operation_name: str = "操作"):
    """安全互動裝飾器"""

    def decorator(func):
        async def wrapper(self, interaction: discord.Interaction, *args, **kwargs):
            try:
                async with InteractionContext(interaction, operation_name) as ctx:
                    if not ctx.is_valid():
                        logger.warning(f"無效的互動上下文: {operation_name}")
                        return

                    return await func(self, interaction, *args, **kwargs)

            except discord.Forbidden:
                await SafeInteractionHandler.safe_respond(
                    interaction,
                    content=f"❌ 沒有權限執行{operation_name}",
                    ephemeral=True,
                )
            except Exception as e:
                logger.error(f"{operation_name}執行失敗: {e}")
                await SafeInteractionHandler.handle_interaction_error(
                    interaction, e, operation_name
                )

        return wrapper

    return decorator


class SafeView(discord.ui.View):
    """安全的 Discord UI View 基礎類別"""

    def __init__(self, *, timeout: float = 180.0, user_id: Optional[int] = None):
        super().__init__(timeout=timeout)
        self.user_id = user_id

    async def on_timeout(self) -> None:
        """處理 View 超時"""
        try:
            # 禁用所有組件
            for item in self.children:
                item.disabled = True

            logger.debug("View 超時，已禁用所有組件")

        except Exception as e:
            logger.error(f"處理 View 超時時發生錯誤: {e}")

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        """檢查用戶權限"""
        if self.user_id and interaction.user.id != self.user_id:
            await SafeInteractionHandler.safe_respond(
                interaction, content="❌ 你沒有權限使用此面板", ephemeral=True
            )
            return False
        return True

    async def on_error(self, interaction: discord.Interaction, error: Exception, item) -> None:
        """處理 View 錯誤"""
        logger.error(f"View 組件錯誤: {error}")
        await SafeInteractionHandler.handle_interaction_error(interaction, error, "面板操作")


# 兼容舊版名稱
class BaseView(SafeView):
    """兼容舊代碼的 BaseView 別名"""