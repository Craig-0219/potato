# bot/register/register.py - 修復版
# 修復點：
# 1. 只註冊無參數的基礎 View
# 2. 避免帶參數的 Persistent View 導致錯誤
# 3. 添加錯誤處理和日誌

import discord
from typing import Dict, Any
import logging

logger = logging.getLogger(__name__)

def register_all_views(bot: discord.Client):
    """
    集中註冊所有 Persistent View（修復版）
    
    修復策略：
    1. 只註冊無參數的基礎 View
    2. 帶參數的 View 改為動態創建
    3. 添加完整的錯誤處理
    """
    try:
        # 🎫 票券相關 - 只註冊基礎無參數 View
        from bot.views.ticket_views import TicketPanelView, TicketControlView
        
        # 票券面板 - 使用空設定作為預設
        panel_view = TicketPanelView(settings={}, timeout=None)
        bot.add_view(panel_view)
        logger.info("✅ 已註冊 TicketPanelView")
        
        # 票券控制面板 - 使用預設參數
        control_view = TicketControlView(timeout=None)
        bot.add_view(control_view)
        logger.info("✅ 已註冊 TicketControlView")
        
        # 🗳 投票相關 - 只註冊基礎 View
        from bot.views.vote_views import (
            FinalStepView, DurationSelectView, RoleSelectView,
            AnonSelectView, MultiSelectView
        )
        
        # 註冊投票建立流程的基礎 View（無參數版本）
        try:
            # 這些 View 需要修改為支援無參數初始化
            # 暫時跳過需要參數的 View，改為動態創建
            logger.info("📝 投票相關 View 將採用動態創建模式")
        except Exception as e:
            logger.error(f"❌ 投票 View 註冊失敗：{e}")
        
        logger.info("✅ 所有基礎 Persistent View 註冊完成")
        
    except ImportError as e:
        logger.error(f"❌ 導入 View 模組失敗：{e}")
        logger.warning("🔄 將嘗試載入可用的 View")
        
        # 嘗試註冊基本可用的 View
        try:
            register_basic_views(bot)
        except Exception as basic_error:
            logger.error(f"❌ 基本 View 註冊也失敗：{basic_error}")
    
    except Exception as e:
        logger.error(f"❌ Persistent View 註冊失敗：{e}")
        logger.warning("⚠️ 部分功能可能無法正常使用")


def register_basic_views(bot: discord.Client):
    """
    註冊基本的備用 View（當主要 View 載入失敗時使用）
    """
    try:
        # 創建一個基本的票券面板 View
        class BasicTicketPanelView(discord.ui.View):
            def __init__(self):
                super().__init__(timeout=None)
                self.add_item(BasicTicketButton())
        
        class BasicTicketButton(discord.ui.Button):
            def __init__(self):
                super().__init__(
                    label="建立票券",
                    style=discord.ButtonStyle.primary,
                    emoji="🎫",
                    custom_id="basic_ticket_create"
                )
            
            async def callback(self, interaction: discord.Interaction):
                await interaction.response.send_message(
                    "🔧 系統正在維護中，請稍後再試或聯繫管理員。",
                    ephemeral=True
                )
        
        # 註冊基本 View
        bot.add_view(BasicTicketPanelView())
        logger.info("✅ 已註冊基本備用 View")
        
    except Exception as e:
        logger.error(f"❌ 基本 View 註冊失敗：{e}")


def create_dynamic_view(view_type: str, **kwargs) -> discord.ui.View:
    """
    動態創建帶參數的 View
    
    Args:
        view_type: View 類型 ('rating', 'vote_button', 'ticket_list' 等)
        **kwargs: View 所需的參數
    
    Returns:
        創建的 View 實例
    """
    try:
        if view_type == "rating":
            from bot.views.ticket_views import RatingView
            ticket_id = kwargs.get('ticket_id', 0)
            return RatingView(ticket_id=ticket_id)
        
        elif view_type == "vote_button":
            from bot.views.vote_views import VoteButtonView
            return VoteButtonView(
                vote_id=kwargs.get('vote_id'),
                options=kwargs.get('options', []),
                allowed_roles=kwargs.get('allowed_roles', []),
                is_multi=kwargs.get('is_multi', False),
                anonymous=kwargs.get('anonymous', False),
                stats=kwargs.get('stats', {}),
                total_votes=kwargs.get('total_votes', 0)
            )
        
        elif view_type == "ticket_list":
            from bot.views.ticket_views import TicketListView
            return TicketListView(
                tickets=kwargs.get('tickets', []),
                page=kwargs.get('page', 1),
                total_pages=kwargs.get('total_pages', 1),
                **kwargs.get('query_params', {})
            )
        
        elif view_type == "ticket_control":
            from bot.views.ticket_views import TicketControlView
            return TicketControlView(
                can_close=kwargs.get('can_close', True),
                can_assign=kwargs.get('can_assign', True),
                can_rate=kwargs.get('can_rate', False),
                ticket_id=kwargs.get('ticket_id')
            )
        
        elif view_type == "role_select":
            from bot.views.vote_views import RoleSelectView
            return RoleSelectView(
                user_id=kwargs.get('user_id'),
                roles=kwargs.get('roles', [])
            )
        
        elif view_type == "duration_select":
            from bot.views.vote_views import DurationSelectView
            return DurationSelectView(user_id=kwargs.get('user_id'))
        
        elif view_type == "anon_select":
            from bot.views.vote_views import AnonSelectView
            return AnonSelectView(user_id=kwargs.get('user_id'))
        
        elif view_type == "multi_select":
            from bot.views.vote_views import MultiSelectView
            return MultiSelectView(user_id=kwargs.get('user_id'))
        
        elif view_type == "final_step":
            from bot.views.vote_views import FinalStepView
            return FinalStepView(
                user_id=kwargs.get('user_id'),
                callback=kwargs.get('callback')
            )
        
        else:
            logger.warning(f"未知的 View 類型：{view_type}")
            return None
    
    except Exception as e:
        logger.error(f"動態創建 {view_type} View 失敗：{e}")
        return None


def get_registered_views() -> Dict[str, Any]:
    """
    取得已註冊的 Persistent View 資訊
    """
    return {
        "ticket_panel": "TicketPanelView - 票券建立面板",
        "ticket_control": "TicketControlView - 票券操作控制",
        "dynamic_views": [
            "rating - 票券評分",
            "vote_button - 投票按鈕",
            "ticket_list - 票券列表分頁",
            "role_select - 身分組選擇",
            "duration_select - 時間選擇",
            "anon_select - 匿名選擇",
            "multi_select - 多選設定",
            "final_step - 最終確認"
        ]
    }


def validate_view_registration(bot: discord.Client) -> Dict[str, bool]:
    """
    驗證 View 註冊狀態
    """
    validation_results = {}
    
    try:
        # 檢查是否有 persistent views
        persistent_views = getattr(bot, 'persistent_views', None)
        validation_results["has_persistent_views"] = persistent_views is not None
        
        if persistent_views:
            validation_results["persistent_view_count"] = len(persistent_views)
        else:
            validation_results["persistent_view_count"] = 0
        
        # 檢查基本 View 是否可用
        try:
            basic_view = create_dynamic_view("rating", ticket_id=1)
            validation_results["dynamic_view_creation"] = basic_view is not None
        except:
            validation_results["dynamic_view_creation"] = False
        
        logger.info(f"View 註冊驗證結果：{validation_results}")
        
    except Exception as e:
        logger.error(f"View 註冊驗證失敗：{e}")
        validation_results["validation_error"] = str(e)
    
    return validation_results


# ===== 工具函數 =====

async def refresh_persistent_views(bot: discord.Client):
    """
    重新註冊所有 Persistent View（用於熱重載）
    """
    try:
        # 清除現有的 persistent views
        if hasattr(bot, 'persistent_views'):
            bot.persistent_views.clear()
        
        # 重新註冊
        register_all_views(bot)
        logger.info("✅ Persistent View 重新註冊完成")
        
    except Exception as e:
        logger.error(f"❌ Persistent View 重新註冊失敗：{e}")


def setup_view_error_handler(bot: discord.Client):
    """
    設置 View 錯誤處理器
    """
    @bot.event
    async def on_error(event, *args, **kwargs):
        if 'view' in event.lower() or 'interaction' in event.lower():
            logger.error(f"View 相關錯誤在事件 {event}：{args}")
    
    logger.info("✅ View 錯誤處理器已設置")