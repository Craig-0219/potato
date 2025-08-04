# bot/register/register.py - v2.1 修復版（解決PersistentView warnings）
"""
修復點：
1. 修復PersistentView註冊警告
2. 改善View參數處理
3. 添加錯誤恢復機制
"""

import discord
from typing import Dict, Any
import logging

logger = logging.getLogger(__name__)

def register_all_views(bot: discord.Client):
    """集中註冊所有 Persistent View（修復警告版）"""
    try:
        logger.info("🔄 開始註冊 Persistent Views...")
        
        # 修復：更安全的View註冊
        success_count = 0
        
        # 1. 票券系統Views
        try:
            from bot.views.ticket_views import TicketPanelView, TicketControlView
            
            # 修復：使用預設參數註冊
            panel_view = TicketPanelView(settings=None, timeout=None)
            bot.add_view(panel_view)
            success_count += 1
            logger.info("✅ TicketPanelView 註冊成功")
            
            control_view = TicketControlView(timeout=None)
            bot.add_view(control_view)
            success_count += 1
            logger.info("✅ TicketControlView 註冊成功")
            
        except ImportError as e:
            logger.warning(f"⚠️ 票券Views導入失敗：{e}")
        except Exception as e:
            logger.error(f"❌ 票券Views註冊失敗：{e}")
        
        # 2. 投票系統Views（修復：不註冊帶參數的Views）
        try:
            # 修復：投票Views改為動態創建，不在此註冊
            logger.info("📝 投票Views將採用動態創建模式")
            
        except Exception as e:
            logger.error(f"❌ 投票Views處理失敗：{e}")
        
        logger.info(f"✅ 成功註冊 {success_count} 個 Persistent Views")
        
        # 修復：驗證註冊結果
        validation = validate_view_registration(bot)
        if validation.get("has_persistent_views"):
            logger.info("✅ Persistent Views 驗證通過")
        else:
            logger.warning("⚠️ Persistent Views 驗證失敗，可能影響重啟後的互動功能")
        
    except Exception as e:
        logger.error(f"❌ Persistent View 註冊失敗：{e}")
        logger.warning("⚠️ 將使用備用View註冊機制")
        try:
            register_fallback_views(bot)
        except Exception as fallback_error:
            logger.error(f"❌ 備用View註冊也失敗：{fallback_error}")

def register_fallback_views(bot: discord.Client):
    """註冊備用Views（當主要Views失敗時）"""
    try:
        logger.info("🔄 註冊備用Views...")
        
        # 創建一個基本的備用View
        class FallbackView(discord.ui.View):
            def __init__(self):
                super().__init__(timeout=None)
                self.add_item(FallbackButton())
        
        class FallbackButton(discord.ui.Button):
            def __init__(self):
                super().__init__(
                    label="系統維護中",
                    style=discord.ButtonStyle.secondary,
                    emoji="🔧",
                    custom_id="fallback_button",
                    disabled=True
                )
            
            async def callback(self, interaction: discord.Interaction):
                await interaction.response.send_message(
                    "🔧 系統正在維護中，請稍後再試。",
                    ephemeral=True
                )
        
        bot.add_view(FallbackView())
        logger.info("✅ 備用View註冊成功")
        
    except Exception as e:
        logger.error(f"❌ 備用View註冊失敗：{e}")

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


def validate_view_registration(bot: discord.Client) -> Dict[str, Any]:
    """驗證View註冊狀態（修復版）"""
    try:
        # 修復：更好的驗證邏輯
        validation_results = {
            "has_persistent_views": False,
            "persistent_view_count": 0,
            "view_details": []
        }
        
        # 檢查bot是否有persistent_views屬性
        if hasattr(bot, 'persistent_views') and bot.persistent_views:
            validation_results["has_persistent_views"] = True
            validation_results["persistent_view_count"] = len(bot.persistent_views)
            
            # 收集View詳情
            for view in bot.persistent_views:
                view_info = {
                    "type": type(view).__name__,
                    "timeout": getattr(view, 'timeout', None),
                    "children_count": len(view.children) if hasattr(view, 'children') else 0
                }
                validation_results["view_details"].append(view_info)
        
        logger.info(f"📊 View註冊驗證結果：{validation_results}")
        return validation_results
        
    except Exception as e:
        logger.error(f"❌ View註冊驗證失敗：{e}")
        return {
            "has_persistent_views": False,
            "persistent_view_count": 0,
            "validation_error": str(e)
        }


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