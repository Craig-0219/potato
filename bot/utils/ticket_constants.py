# bot/utils/constants.py - 簡化的票券常數定義
"""
票券系統常數 - 簡化版
只保留核心必要的常數定義
"""

import discord
from typing import Dict, List, Any


class TicketConstants:
    """票券系統常數"""
    
    # ===== 基本常數 =====
    PRIORITIES = ['high', 'medium', 'low']
    STATUSES = ['open', 'closed']
    
    # ===== 顯示常數 =====
    PRIORITY_EMOJIS = {
        'high': '🔴',
        'medium': '🟡',
        'low': '🟢'
    }
    
    STATUS_EMOJIS = {
        'open': '🟢',
        'closed': '🔴'
    }
    
    PRIORITY_COLORS = {
        'high': 0xff0000,      # 紅色
        'medium': 0xffaa00,    # 橙色
        'low': 0x00ff00        # 綠色
    }
    
    STATUS_COLORS = {
        'open': 0x00ff00,      # 綠色
        'closed': 0xff0000     # 紅色
    }
    
    # ===== 系統顏色 =====
    COLORS = {
        'primary': 0x3498db,   # 藍色
        'success': 0x2ecc71,   # 綠色
        'warning': 0xf39c12,   # 橙色
        'danger': 0xe74c3c,    # 紅色
        'info': 0x9b59b6       # 紫色
    }
    
    # ===== 評分系統 =====
    RATING_EMOJIS = {
        1: "⭐",
        2: "⭐⭐", 
        3: "⭐⭐⭐",
        4: "⭐⭐⭐⭐",
        5: "⭐⭐⭐⭐⭐"
    }
    
    RATING_COLORS = {
        1: 0xe74c3c,  # 紅色
        2: 0xf39c12,  # 橙色
        3: 0xf1c40f,  # 黃色
        4: 0x2ecc71,  # 綠色
        5: 0x27ae60   # 深綠色
    }
    
    # ===== 票券類型 =====
    DEFAULT_TICKET_TYPES = [
        {
            'name': '技術支援',
            'emoji': '🔧',
            'style': discord.ButtonStyle.primary,
            'description': '技術問題、Bug 回報、系統故障'
        },
        {
            'name': '帳號問題', 
            'emoji': '👤',
            'style': discord.ButtonStyle.secondary,
            'description': '登入問題、權限問題、個人資料'
        },
        {
            'name': '檢舉回報',
            'emoji': '⚠️', 
            'style': discord.ButtonStyle.danger,
            'description': '違規行為、不當內容、騷擾舉報'
        },
        {
            'name': '功能建議',
            'emoji': '💡',
            'style': discord.ButtonStyle.success,
            'description': '新功能建議、改進意見'
        },
        {
            'name': '其他問題',
            'emoji': '❓',
            'style': discord.ButtonStyle.secondary, 
            'description': '其他未分類的問題或疑問'
        }
    ]
    
    # ===== SLA 設定 =====
    SLA_MULTIPLIERS = {
        'high': 0.5,    # 高優先級：時間減半
        'medium': 1.0,  # 中優先級：標準時間
        'low': 1.5      # 低優先級：時間增加50%
    }
    
    # ===== 預設設定 =====
    DEFAULT_SETTINGS = {
        'max_tickets_per_user': 3,
        'auto_close_hours': 24,
        'sla_response_minutes': 60,
        'welcome_message': "歡迎使用客服系統！請選擇問題類型來建立支援票券。"
    }
    
    # ===== 限制常數 =====
    LIMITS = {
        'max_tickets_per_user': (1, 10),
        'auto_close_hours': (1, 168),      # 1小時到1週
        'sla_response_minutes': (5, 1440), # 5分鐘到24小時
        'feedback_length': (0, 500),
        'reason_length': (0, 200)
    }


# ===== 錯誤訊息 =====
class TicketError:
    """票券錯誤訊息"""
    
    # 權限錯誤
    NO_PERMISSION = "❌ 你沒有權限執行此操作。"
    NOT_SUPPORT_STAFF = "❌ 只有客服人員可以執行此操作。"
    NOT_ADMIN = "❌ 只有管理員可以執行此操作。"
    
    # 票券錯誤
    TICKET_NOT_FOUND = "❌ 找不到指定的票券。"
    NOT_TICKET_CHANNEL = "❌ 此指令只能在票券頻道中使用。"
    TICKET_LIMIT_REACHED = "❌ 你已達到票券上限！請先關閉現有票券。"
    TICKET_ALREADY_CLOSED = "❌ 此票券已經關閉。"
    
    # 評分錯誤
    INVALID_RATING = "❌ 評分必須在 1-5 之間。"
    ALREADY_RATED = "❌ 此票券已經評分過了。"
    CANNOT_RATE_OPEN = "❌ 只能為已關閉的票券評分。"
    
    # 設定錯誤
    CATEGORY_NOT_SET = "❌ 尚未設定票券分類頻道。"
    INVALID_SETTING = "❌ 無效的設定項目。"
    INVALID_VALUE = "❌ 無效的設定值。"
    
    # 系統錯誤
    DATABASE_ERROR = "❌ 資料庫操作失敗，請稍後再試。"
    CHANNEL_CREATE_FAILED = "❌ 建立票券頻道失敗。"
    SYSTEM_ERROR = "❌ 系統錯誤，請稍後再試。"


# ===== 成功訊息 =====
class TicketSuccess:
    """票券成功訊息"""
    
    TICKET_CREATED = "✅ 票券建立成功！"
    TICKET_CLOSED = "✅ 票券已關閉。"
    TICKET_ASSIGNED = "✅ 票券指派完成。"
    PRIORITY_UPDATED = "✅ 優先級已更新。"
    RATING_SAVED = "✅ 評分已保存，感謝你的回饋！"
    SETTING_UPDATED = "✅ 設定已更新。"


# ===== 工具函數 =====

def get_priority_emoji(priority: str) -> str:
    """取得優先級表情符號"""
    return TicketConstants.PRIORITY_EMOJIS.get(priority, '🟡')


def get_status_emoji(status: str) -> str:
    """取得狀態表情符號"""
    return TicketConstants.STATUS_EMOJIS.get(status, '🟢')


def get_priority_color(priority: str) -> int:
    """取得優先級顏色"""
    return TicketConstants.PRIORITY_COLORS.get(priority, 0xffaa00)


def get_status_color(status: str) -> int:
    """取得狀態顏色"""
    return TicketConstants.STATUS_COLORS.get(status, 0x00ff00)


def get_rating_stars(rating: int) -> str:
    """取得評分星星"""
    return TicketConstants.RATING_EMOJIS.get(rating, "⭐")


def calculate_sla_time(priority: str, base_minutes: int) -> int:
    """計算 SLA 時間"""
    multiplier = TicketConstants.SLA_MULTIPLIERS.get(priority, 1.0)
    return int(base_minutes * multiplier)


def is_valid_priority(priority: str) -> bool:
    """驗證優先級是否有效"""
    return priority in TicketConstants.PRIORITIES


def is_valid_status(status: str) -> bool:
    """驗證狀態是否有效"""
    return status in TicketConstants.STATUSES


def is_valid_rating(rating: int) -> bool:
    """驗證評分是否有效"""
    return 1 <= rating <= 5


def get_ticket_type_info(type_name: str) -> Dict[str, Any]:
    """取得票券類型資訊"""
    for ticket_type in TicketConstants.DEFAULT_TICKET_TYPES:
        if ticket_type['name'] == type_name:
            return ticket_type
    return TicketConstants.DEFAULT_TICKET_TYPES[0]  # 預設返回第一個


def validate_setting_value(setting: str, value: Any) -> bool:
    """驗證設定值"""
    if setting == 'max_tickets_per_user':
        min_val, max_val = TicketConstants.LIMITS['max_tickets_per_user']
        return isinstance(value, int) and min_val <= value <= max_val
    
    elif setting == 'auto_close_hours':
        min_val, max_val = TicketConstants.LIMITS['auto_close_hours']
        return isinstance(value, int) and min_val <= value <= max_val
    
    elif setting == 'sla_response_minutes':
        min_val, max_val = TicketConstants.LIMITS['sla_response_minutes']
        return isinstance(value, int) and min_val <= value <= max_val
    
    elif setting == 'welcome_message':
        return isinstance(value, str) and len(value) <= 2000
    
    elif setting == 'support_roles':
        return isinstance(value, list) and len(value) <= 10
    
    return True


# ===== 選項生成器 =====

def create_priority_options() -> List[discord.SelectOption]:
    """建立優先級選項"""
    return [
        discord.SelectOption(
            label="🔴 高優先級",
            value="high", 
            description="緊急問題，需要立即處理",
            emoji="🔴"
        ),
        discord.SelectOption(
            label="🟡 中優先級",
            value="medium",
            description="一般問題，正常處理時間",
            emoji="🟡"
        ),
        discord.SelectOption(
            label="🟢 低優先級", 
            value="low",
            description="非緊急問題，可稍後處理",
            emoji="🟢"
        )
    ]


def create_rating_options() -> List[discord.SelectOption]:
    """建立評分選項"""
    return [
        discord.SelectOption(label="⭐ 1星 - 非常不滿意", value="1", emoji="⭐"),
        discord.SelectOption(label="⭐⭐ 2星 - 不滿意", value="2", emoji="⭐"),
        discord.SelectOption(label="⭐⭐⭐ 3星 - 普通", value="3", emoji="⭐"),
        discord.SelectOption(label="⭐⭐⭐⭐ 4星 - 滿意", value="4", emoji="⭐"),
        discord.SelectOption(label="⭐⭐⭐⭐⭐ 5星 - 非常滿意", value="5", emoji="⭐")
    ]


def create_status_filter_options() -> List[discord.SelectOption]:
    """建立狀態篩選選項"""
    return [
        discord.SelectOption(label="📋 全部", value="all", emoji="📋"),
        discord.SelectOption(label="🟢 開啟中", value="open", emoji="🟢"),
        discord.SelectOption(label="🔴 已關閉", value="closed", emoji="🔴")
    ]