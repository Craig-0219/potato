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
                logger.debug("互動對象無效")
                return False
            
            # 檢查互動是否已過期（超過15分鐘）
            import datetime
            if hasattr(interaction, 'created_at'):
                age = datetime.datetime.now(datetime.timezone.utc) - interaction.created_at
                if age.total_seconds() > 900:  # 15分鐘
                    logger.debug(f"互動已過期 ({age.total_seconds()}秒)")
                    return False
            
            # 決定使用哪種回應方法
            # 準備參數，過濾掉 None 值
            kwargs = {}
            if content is not None:
                kwargs['content'] = content
            if embed is not None:
                kwargs['embed'] = embed
            if view is not None:
                kwargs['view'] = view
            kwargs['ephemeral'] = ephemeral
            
            if not interaction.response.is_done():
                # 尚未回應，使用 response
                await interaction.response.send_message(**kwargs)
            else:
                # 已經回應過，使用 followup
                await interaction.followup.send(**kwargs)
            
            return True
            
        except discord.HTTPException as e:
            # Discord API 相關錯誤
            if "Unknown interaction" in str(e) or "10062" in str(e):
                logger.debug("互動已失效或過期")
                return False
            elif "Interaction has already been acknowledged" in str(e) or "40060" in str(e):
                logger.debug("互動已被確認")
                return False
            else:
                logger.warning(f"Discord API 錯誤: {e}")
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
                logger.debug("互動對象無效或沒有 followup 屬性")
                return False
            
            # 準備參數，過濾掉 None 值
            kwargs = {}
            if content is not None:
                kwargs['content'] = content
            if embed is not None:
                kwargs['embed'] = embed
            if view is not None:
                kwargs['view'] = view
            kwargs['ephemeral'] = ephemeral
            
            await interaction.followup.send(**kwargs)
            return True
            
        except discord.HTTPException as e:
            if "Unknown interaction" in str(e) or "10062" in str(e):
                logger.debug("互動已失效或過期")
                return False
            elif "Interaction has already been acknowledged" in str(e) or "40060" in str(e):
                logger.debug("互動已被確認")
                return False
            else:
                logger.warning(f"Discord API 錯誤: {e}")
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
                logger.debug("互動已被確認，無法延遲")
                return False
            
            await interaction.response.defer(ephemeral=ephemeral)
            return True
            
        except discord.HTTPException as e:
            if "Unknown interaction" in str(e) or "10062" in str(e):
                logger.debug("互動已失效，無法延遲")
                return False
            elif "Interaction has already been acknowledged" in str(e) or "40060" in str(e):
                logger.debug("互動已被確認，無法延遲")
                return False
            else:
                logger.warning(f"延遲互動失敗: {e}")
                return False
                
        except Exception as e:
            logger.error(f"安全延遲互動失敗: {e}")
            return False
    
    @staticmethod
    def is_interaction_valid(interaction: discord.Interaction) -> bool:
        """檢查互動是否仍然有效"""
        try:
            if not interaction or not hasattr(interaction, 'response'):
                return False
            
            # 檢查互動是否已過期
            import datetime
            if hasattr(interaction, 'created_at'):
                age = datetime.datetime.now(datetime.timezone.utc) - interaction.created_at
                if age.total_seconds() > 900:  # 15分鐘
                    return False
            
            return True
            
        except Exception:
            return False
    
    @staticmethod
    async def handle_interaction_error(interaction: discord.Interaction, error: Exception, operation_name: str = "操作"):
        """統一處理互動錯誤"""
        try:
            # 檢查是否是已知的互動錯誤
            if "Unknown interaction" in str(error) or "10062" in str(error):
                logger.debug(f"{operation_name}互動已過期，靜默處理")
                return
            
            if "already been acknowledged" in str(error) or "40060" in str(error):
                logger.debug(f"{operation_name}互動已被確認，靜默處理")
                return
            
            # 嘗試回應錯誤訊息
            error_message = f"❌ {operation_name}時發生錯誤，請稍後再試"
            
            success = await SafeInteractionHandler.safe_respond(
                interaction, 
                content=error_message,
                ephemeral=True
            )
            
            if not success:
                logger.debug(f"無法回應{operation_name}錯誤，互動可能已失效")
            
        except Exception as handle_error:
            logger.debug(f"處理{operation_name}錯誤時發生異常: {handle_error}")


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
                    logger.debug(f"{operation_name}互動無效，跳過執行")
                    return
                
                return await func(self, interaction, *args, **kwargs)
        
        return wrapper
    return decorator


# 基礎 View 類
class BaseView(discord.ui.View):
    """
    基礎 View 類，包含通用的超時和錯誤處理
    """
    
    def __init__(self, user_id: int = None, timeout: float = 300):
        super().__init__(timeout=timeout)
        self.user_id = user_id
        self._message = None
    
    def set_message(self, message: discord.Message):
        """設置關聯的訊息物件"""
        self._message = message
    
    async def on_timeout(self):
        """處理超時情況"""
        try:
            # 禁用所有互動元素
            for item in self.children:
                if hasattr(item, 'disabled'):
                    item.disabled = True
            
            # 嘗試編輯訊息
            if self._message:
                try:
                    embed = discord.Embed(
                        title="⏰ 互動已超時",
                        description="此面板已過期，請重新使用相應命令開啟。",
                        color=0x95a5a6
                    )
                    await self._message.edit(embed=embed, view=self)
                except discord.NotFound:
                    logger.debug("訊息已被刪除，無法編輯超時狀態")
                except discord.Forbidden:
                    logger.debug("沒有權限編輯訊息")
                except Exception as e:
                    logger.warning(f"編輯超時訊息時發生錯誤: {e}")
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