# bot/utils/ticket_constants.py - 票券系統常數與工具完整版（修復版）
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Tuple  # 添加缺失的導入

import discord

# ===== 基礎驗證函數實現 =====


def validate_text_input(text: str, field_type: str) -> tuple[bool, str]:
    """驗證文字輸入"""
    if not text or not text.strip():
        return False, f"{field_type} 不能為空"

    text = text.strip()

    # 長度限制
    limits = {
        "ticket_type": 50,
        "username": 32,
        "close_reason": 200,
        "rating_feedback": 500,
        "template_name": 100,
        "template_content": 2000,
        "tag_name": 30,
        "keyword": 50,
        "auto_reply_name": 100,
        "channel_name_length": 100,
    }

    max_length = limits.get(field_type, 100)
    if len(text) > max_length:
        return False, f"長度不能超過 {max_length} 個字元"

    # 特殊字符檢查
    if field_type in ["username", "tag_name", "template_name"]:
        import re

        if re.search(r"[<>@#&]", text):
            return False, "不能包含特殊字符 <>@#&"

    return True, ""


def validate_numeric_input(value: int, field_type: str) -> tuple[bool, str]:
    """驗證數值輸入"""
    limits = {
        "rating": (1, 5),
        "max_tickets_per_user": (1, 20),
        "auto_close_hours": (1, 168),
        "sla_response_minutes": (5, 1440),
        "batch_operation_size": (1, 100),
    }

    if field_type not in limits:
        return True, ""

    min_val, max_val = limits[field_type]
    if not (min_val <= value <= max_val):
        return False, f"必須在 {min_val} 到 {max_val} 之間"

    return True, ""


# ===== 票券常數類 =====


class TicketConstants:
    """票券系統常數與全域選項"""

    PRIORITIES = ["high", "medium", "low"]
    STATUSES = ["open", "closed", "archived"]

    PRIORITY_EMOJIS = {"high": "🔴", "medium": "🟡", "low": "🟢"}

    PRIORITY_COLORS = {"high": 0xFF0000, "medium": 0xFFAA00, "low": 0x00FF00}

    STATUS_EMOJIS = {"open": "🟢", "closed": "🔒", "archived": "🗄️"}

    STATUS_COLORS = {"open": 0x00FF00, "closed": 0xFF0000, "archived": 0x607D8B}

    COLORS = {
        "primary": 0x3498DB,  # 藍
        "success": 0x2ECC71,  # 綠
        "warning": 0xF39C12,  # 橘
        "danger": 0xE74C3C,  # 紅
        "info": 0x9B59B6,  # 紫
    }

    RATING_EMOJIS = {1: "⭐", 2: "⭐⭐", 3: "⭐⭐⭐", 4: "⭐⭐⭐⭐", 5: "⭐⭐⭐⭐⭐"}

    RATING_COLORS = {1: 0xE74C3C, 2: 0xF39C12, 3: 0xF1C40F, 4: 0x2ECC71, 5: 0x27AE60}

    DEFAULT_TICKET_TYPES = [
        {
            "name": "技術支援",
            "emoji": "🔧",
            "style": discord.ButtonStyle.primary,
            "description": "技術問題、Bug 回報、系統故障",
        },
        {
            "name": "帳號問題",
            "emoji": "👤",
            "style": discord.ButtonStyle.secondary,
            "description": "登入、權限、個人資料",
        },
        {
            "name": "合作夥伴",
            "emoji": "🤝",
            "style": discord.ButtonStyle.primary,
            "description": "商業合作、夥伴關係、聯名活動",
        },
        {
            "name": "檢舉回報",
            "emoji": "⚠️",
            "style": discord.ButtonStyle.danger,
            "description": "違規、不當內容、騷擾舉報",
        },
        {
            "name": "功能建議",
            "emoji": "💡",
            "style": discord.ButtonStyle.success,
            "description": "新功能建議、改進意見",
        },
        {
            "name": "其他問題",
            "emoji": "❓",
            "style": discord.ButtonStyle.secondary,
            "description": "未分類問題或疑問",
        },
    ]

    SLA_MULTIPLIERS = {"high": 0.5, "medium": 1.0, "low": 1.5}

    DEFAULT_SETTINGS = {
        "max_tickets_per_user": 3,
        "auto_close_hours": 24,
        "sla_response_minutes": 60,
        "welcome_message": "歡迎使用客服系統！請選擇問題類型來建立支援票券。",
    }

    LIMITS = {
        "max_tickets_per_user": (1, 10),
        "auto_close_hours": (1, 168),
        "sla_response_minutes": (5, 1440),
        "feedback_length": (0, 500),
        "reason_length": (0, 200),
    }


# ===== 錯誤訊息 =====

ERROR_MESSAGES = {
    "no_permission": "❌ 你沒有權限執行此操作。",
    "not_support_staff": "❌ 只有客服人員可以執行此操作。",
    "not_admin": "❌ 只有管理員可以執行此操作。",
    "ticket_not_found": "❌ 找不到指定的票券。",
    "not_ticket_channel": "❌ 此指令只能在票券頻道中使用。",
    "ticket_limit_reached": "❌ 你已達到票券上限！請先關閉現有票券。",
    "ticket_already_closed": "❌ 此票券已經關閉。",
    "invalid_rating": "❌ 評分必須在 1-5 之間。",
    "already_rated": "❌ 此票券已經評分過了。",
    "cannot_rate_open": "❌ 只能為已關閉的票券評分。",
    "cannot_rate_open_ticket": "❌ 只能為已關閉的票券評分。",
    "category_not_set": "❌ 尚未設定票券分類頻道。",
    "invalid_setting": "❌ 無效的設定項目。",
    "invalid_value": "❌ 無效的設定值。",
    "database_error": "❌ 資料庫操作失敗，請稍後再試。",
    "channel_create_failed": "❌ 建立票券頻道失敗。",
    "system_error": "❌ 系統錯誤，請稍後再試。",
}

SUCCESS_MESSAGES = {
    "ticket_created": "✅ 票券建立成功！",
    "ticket_closed": "✅ 票券已關閉。",
    "ticket_assigned": "✅ 票券指派完成。",
    "priority_updated": "✅ 優先級已更新。",
    "rating_saved": "✅ 評分已保存，感謝你的回饋！",
    "setting_updated": "✅ 設定已更新。",
}

# ===== 常用工具 =====


def get_priority_emoji(priority: str) -> str:
    return TicketConstants.PRIORITY_EMOJIS.get(priority, "🟡")


def get_status_emoji(status: str) -> str:
    return TicketConstants.STATUS_EMOJIS.get(status, "🟢")


def get_priority_color(priority: str) -> int:
    return TicketConstants.PRIORITY_COLORS.get(priority, 0xFFAA00)


def get_status_color(status: str) -> int:
    return TicketConstants.STATUS_COLORS.get(status, 0x00FF00)


def get_rating_emoji(rating: int) -> str:
    return TicketConstants.RATING_EMOJIS.get(rating, "⭐")


def calculate_sla_time(priority: str, base_minutes: int = 60) -> int:
    multiplier = TicketConstants.SLA_MULTIPLIERS.get(priority, 1.0)
    return int(base_minutes * multiplier)


def is_valid_priority(priority: str) -> bool:
    return priority in TicketConstants.PRIORITIES


def is_valid_status(status: str) -> bool:
    return status in TicketConstants.STATUSES


def is_valid_rating(rating: int) -> bool:
    return 1 <= rating <= 5


def get_ticket_type_info(type_name: str) -> Dict[str, Any]:
    for t in TicketConstants.DEFAULT_TICKET_TYPES:
        if t["name"] == type_name:
            return t
    return TicketConstants.DEFAULT_TICKET_TYPES[0]


def validate_setting_value(setting: str, value: Any) -> bool:
    if setting == "max_tickets_per_user":
        min_val, max_val = TicketConstants.LIMITS["max_tickets_per_user"]
        return isinstance(value, int) and min_val <= value <= max_val
    elif setting == "auto_close_hours":
        min_val, max_val = TicketConstants.LIMITS["auto_close_hours"]
        return isinstance(value, int) and min_val <= value <= max_val
    elif setting == "sla_response_minutes":
        min_val, max_val = TicketConstants.LIMITS["sla_response_minutes"]
        return isinstance(value, int) and min_val <= value <= max_val
    elif setting == "welcome_message":
        return isinstance(value, str) and len(value) <= 2000
    elif setting == "support_roles":
        return isinstance(value, list) and len(value) <= 10
    return True


# ===== Discord Select Options =====


def create_priority_options() -> List[discord.SelectOption]:
    return [
        discord.SelectOption(
            label="🔴 高優先級",
            value="high",
            description="緊急問題，需要立即處理",
            emoji="🔴",
        ),
        discord.SelectOption(
            label="🟡 中優先級",
            value="medium",
            description="一般問題，正常處理時間",
            emoji="🟡",
        ),
        discord.SelectOption(
            label="🟢 低優先級",
            value="low",
            description="非緊急問題，可稍後處理",
            emoji="🟢",
        ),
    ]


def create_rating_options() -> List[discord.SelectOption]:
    return [
        discord.SelectOption(label="⭐ 1星 - 非常不滿意", value="1", emoji="⭐"),
        discord.SelectOption(label="⭐⭐ 2星 - 不滿意", value="2", emoji="⭐"),
        discord.SelectOption(label="⭐⭐⭐ 3星 - 普通", value="3", emoji="⭐"),
        discord.SelectOption(label="⭐⭐⭐⭐ 4星 - 滿意", value="4", emoji="⭐"),
        discord.SelectOption(label="⭐⭐⭐⭐⭐ 5星 - 非常滿意", value="5", emoji="⭐"),
    ]


def create_status_filter_options() -> List[discord.SelectOption]:
    return [
        discord.SelectOption(label="📋 全部", value="all", emoji="📋"),
        discord.SelectOption(label="🟢 開啟中", value="open", emoji="🟢"),
        discord.SelectOption(label="🔒 已關閉", value="closed", emoji="🔒"),
    ]


# ===== 進階格式化工具 =====


def format_duration_chinese(seconds: int) -> str:
    """將秒數轉為中文時長：天x小時x分鐘x秒"""
    days, rem = divmod(seconds, 86400)
    hours, rem = divmod(rem, 3600)
    minutes, sec = divmod(rem, 60)
    parts = []
    if days:
        parts.append(f"{days}天")
    if hours:
        parts.append(f"{hours}小時")
    if minutes:
        parts.append(f"{minutes}分")
    if not parts:
        parts.append(f"{sec}秒")
    return "".join(parts)


def get_time_ago_chinese(dt: datetime) -> str:
    now = datetime.now(timezone.utc)
    delta = now - dt if now > dt else dt - now
    seconds = int(delta.total_seconds())
    if seconds < 60:
        return f"{seconds}秒前"
    elif seconds < 3600:
        return f"{seconds//60}分鐘前"
    elif seconds < 86400:
        return f"{seconds//3600}小時前"
    elif seconds < 2592000:
        return f"{seconds//86400}天前"
    else:
        return dt.strftime("%Y-%m-%d")


def truncate_text(text: str, length: int = 100) -> str:
    if not text:
        return ""
    return text[:length] + ("..." if len(text) > length else "")


def escape_markdown(text: str) -> str:
    """轉義 Discord markdown 字元"""
    if not text:
        return ""
    for c in ["*", "_", "`", "~", "|", ">", "[", "]", "(", ")", "#"]:
        text = text.replace(c, f"\\{c}")
    return text


def create_progress_indicator(current: int, total: int, length: int = 10) -> str:
    if total == 0:
        bar = "□" * length
    else:
        filled = int((current / total) * length)
        bar = "■" * filled + "□" * (length - filled)
    return bar


# ===== 導出所有 =====

__all__ = [
    "TicketConstants",
    "ERROR_MESSAGES",
    "SUCCESS_MESSAGES",
    "validate_text_input",
    "validate_numeric_input",
    "get_priority_emoji",
    "get_status_emoji",
    "get_priority_color",
    "get_status_color",
    "get_rating_emoji",
    "calculate_sla_time",
    "is_valid_priority",
    "is_valid_status",
    "is_valid_rating",
    "get_ticket_type_info",
    "validate_setting_value",
    "create_priority_options",
    "create_rating_options",
    "create_status_filter_options",
    "format_duration_chinese",
    "get_time_ago_chinese",
    "truncate_text",
    "escape_markdown",
    "create_progress_indicator",
]
