#!/usr/bin/env python3
"""
互動處理幫助工具
提供統一的互動錯誤處理和安全回應方法
"""

import discord
from shared.logger import logger
from typing import Optional, Union, Any

class SafeInteractionHandler:
    """安全互動處理器"""
    
    @staticmethod
    async def safe_respond(interaction: discord.Interaction, content: Optional[str] = None, 
                          embed: Optional[discord.Embed] = None, 
                          view: Optional[discord.ui.View] = None,
                          ephemeral: bool = True) -> bool:
        """安全回應互動，處理所有可能的錯誤情況"""
        try:
            # 檢查互動是否仍然有效
            if not interaction or not hasattr(interaction, 'response'):
                
                return False
            elif "Interaction has already been acknowledged" in str(e) or "40060" in str(e):
                
                return False
                
        except Exception as e:
            logger.error(f"安全回應互動失敗: {e}")
            return False
    
    @staticmethod
    async def safe_followup(interaction: discord.Interaction, content: Optional[str] = None,
                           embed: Optional[discord.Embed] = None,
                           view: Optional[discord.ui.View] = None,
                           ephemeral: bool = True) -> bool:
        """安全發送 followup 訊息"""
        try:
            if not interaction or not hasattr(interaction, 'followup'):
                
                return False
                
        except Exception as e:
            logger.error(f"安全 followup 失敗: {e}")
            return False
    
    @staticmethod
    async def safe_defer(interaction: discord.Interaction, ephemeral: bool = True) -> bool:
        """安全延遲互動回應"""
        try:
            if not interaction or not hasattr(interaction, 'response'):
                return False
                
            if interaction.response.is_done():
                
                return
            
            if "already been acknowledged" in str(error) or "40060" in str(error):

        except Exception as handle_error:

class InteractionContext:
    """互動上下文管理器"""
    
    def __init__(self, interaction: discord.Interaction, operation_name: str = "操作"):
        self.interaction = interaction
        self.operation_name = operation_name
        self.deferred = False
    
    async def __aenter__(self):
        """進入上下文管理器"""
        if SafeInteractionHandler.is_interaction_valid(self.interaction):
            self.deferred = await SafeInteractionHandler.safe_defer(self.interaction)
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """離開上下文管理器"""
        if exc_type is not None:
            # 有異常發生，處理錯誤
            await SafeInteractionHandler.handle_interaction_error(
                self.interaction, 
                exc_val, 
                self.operation_name
            )
            return True  # 抑制異常
        return False
    
    async def respond(self, content: Optional[str] = None, 
                     embed: Optional[discord.Embed] = None,
                     view: Optional[discord.ui.View] = None,
                     ephemeral: bool = True) -> bool:
        """在上下文中安全回應"""
        return await SafeInteractionHandler.safe_respond(
            self.interaction,
            content=content,
            embed=embed,
            view=view,
            ephemeral=ephemeral
        )
    
    def is_valid(self) -> bool:
        """檢查上下文是否有效"""
        return SafeInteractionHandler.is_interaction_valid(self.interaction)

# 裝飾器版本
def safe_interaction(operation_name: str = "操作"):
    """安全互動裝飾器"""
    def decorator(func):
        async def wrapper(self, interaction: discord.Interaction, *args, **kwargs):
            async with InteractionContext(interaction, operation_name) as ctx:
                if not ctx.is_valid():
                    
                except discord.Forbidden:
                    
        except Exception as e:
            logger.error(f"處理 View 超時時發生錯誤: {e}")
    
    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        """檢查用戶權限"""
        if self.user_id and interaction.user.id != self.user_id:
            await SafeInteractionHandler.safe_respond(
                interaction,
                content="❌ 你沒有權限使用此面板", 
                ephemeral=True
            )
            return False
        return True
    
    async def on_error(self, interaction: discord.Interaction, error: Exception, item):
        """處理互動錯誤"""
        logger.error(f"View 互動錯誤: {error}")
        await SafeInteractionHandler.handle_interaction_error(
            interaction, error, "面板互動"
        )

# 使用範例：
# @safe_interaction("獲取實時數據")
# async def dashboard_realtime(self, interaction: discord.Interaction):
#     # 函數內容
#     pass