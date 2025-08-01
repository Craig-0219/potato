# bot/utils/ticket_constants.py - 票券系統完整常數定義

import discord
from typing import Dict, List, Any, Tuple, Optional
from enum import Enum
from datetime import datetime, timezone

# ===== 枚舉定義 =====

class Priority(Enum):
    """優先級枚舉"""
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class Status(Enum):
    """狀態枚舉"""
    OPEN = "open"
    CLOSED = "closed"
    ARCHIVED = "archived"


class ActionType(Enum):
    """操作類型枚舉"""
    CREATED = "created"
    CLOSED = "closed"
    ASSIGNED = "assigned"
    PRIORITY_CHANGE = "priority_change"
    STATUS_CHANGE = "status_change"
    RATING_ADDED = "rating_added"
    TAG_ADDED = "tag_added"
    TAG_REMOVED = "tag_removed"
    TRANSFERRED = "transferred"
    ESCALATED = "escalated"
    MESSAGE_ADDED = "message_added"
    AUTO_REPLY = "auto_reply"

# ===== 票券系統常數區 =====

class TicketConstants:
    """票券系統常數定義"""

    # ===== 優先級定義 =====
    PRIORITIES = [Priority.HIGH.value, Priority.MEDIUM.value, Priority.LOW.value]
    PRIORITY_EMOJIS = {
        Priority.HIGH.value: '🔴',
        Priority.MEDIUM.value: '🟡',
        Priority.LOW.value: '🟢'
    }
    PRIORITY_COLORS = {
        Priority.HIGH.value: discord.Color.red(),
        Priority.MEDIUM.value: discord.Color.orange(),
        Priority.LOW.value: discord.Color.green()
    }
    PRIORITY_NAMES = {
        Priority.HIGH.value: '高優先級',
        Priority.MEDIUM.value: '中優先級',
        Priority.LOW.value: '低優先級'
    }
    PRIORITY_DESCRIPTIONS = {
        Priority.HIGH.value: '緊急問題，需要立即處理',
        Priority.MEDIUM.value: '一般問題，正常處理時間',
        Priority.LOW.value: '非緊急問題，可稍後處理'
    }
    PRIORITY_SLA_MULTIPLIERS = {
        Priority.HIGH.value: 0.5,
        Priority.MEDIUM.value: 1.0,
        Priority.LOW.value: 1.5
    }

    # ===== 狀態定義 =====
    STATUSES = [Status.OPEN.value, Status.CLOSED.value, Status.ARCHIVED.value]
    STATUS_EMOJIS = {
        Status.OPEN.value: '🟢',
        Status.CLOSED.value: '🔴',
        Status.ARCHIVED.value: '⚫'
    }
    STATUS_COLORS = {
        Status.OPEN.value: discord.Color.green(),
        Status.CLOSED.value: discord.Color.red(),
        Status.ARCHIVED.value: discord.Color.dark_grey()
    }
    STATUS_NAMES = {
        Status.OPEN.value: '開啟中',
        Status.CLOSED.value: '已關閉',
        Status.ARCHIVED.value: '已歸檔'
    }
    STATUS_DESCRIPTIONS = {
        Status.OPEN.value: '票券正在處理中',
        Status.CLOSED.value: '票券已處理完成',
        Status.ARCHIVED.value: '票券已歸檔保存'
    }

    # ===== 票券類型定義 =====
    DEFAULT_TICKET_TYPES = [
        {
            "name": "技術支援",
            "emoji": "🔧",
            "style": discord.ButtonStyle.primary,
            "description": "技術問題、Bug 回報、系統故障",
            "priority": Priority.MEDIUM.value,
            "auto_tags": ["技術", "支援"]
        },
        {
            "name": "帳號問題",
            "emoji": "👤",
            "style": discord.ButtonStyle.secondary,
            "description": "登入問題、權限問題、個人資料",
            "priority": Priority.HIGH.value,
            "auto_tags": ["帳號", "權限"]
        },
        {
            "name": "檢舉回報",
            "emoji": "⚠️",
            "style": discord.ButtonStyle.danger,
            "description": "違規行為、不當內容、騷擾舉報",
            "priority": Priority.HIGH.value,
            "auto_tags": ["檢舉", "違規"]
        },
        {
            "name": "功能建議",
            "emoji": "💡",
            "style": discord.ButtonStyle.success,
            "description": "新功能建議、改進意見",
            "priority": Priority.LOW.value,
            "auto_tags": ["建議", "功能"]
        },
        {
            "name": "其他問題",
            "emoji": "❓",
            "style": discord.ButtonStyle.secondary,
            "description": "其他未分類的問題或疑問",
            "priority": Priority.MEDIUM.value,
            "auto_tags": ["其他"]
        }
    ]

    # ===== 系統設定預設值 =====
    DEFAULT_SETTINGS = {
        'max_tickets_per_user': 3,
        'auto_close_hours': 24,
        'sla_response_minutes': 60,
        'auto_assign_enabled': False,
        'welcome_message': "歡迎使用客服系統！請選擇你的問題類型，我們會為你建立專屬支援頻道。",
        'closure_message': "感謝你使用我們的客服系統！如果問題已解決，請為此次服務評分。",
        'rating_prompt_message': "請為此次客服體驗評分，你的回饋對我們很重要！",
        'auto_assignment_algorithm': 'least_loaded',
        'enable_sla_monitoring': True,
        'enable_auto_replies': True,
        'enable_rating_system': True,
        'enable_tag_system': True,
        'require_rating_on_close': False,
        'delete_channel_on_close': True,
        'channel_deletion_delay': 30,
        'transcript_enabled': True,
        'transcript_format': 'html'
    }

    # ===== 權限等級定義 =====
    PERMISSION_LEVELS = {
        'user': 0,
        'support': 1,
        'admin': 2,
        'owner': 3
    }

    # ===== 操作類型定義 =====
    ACTION_TYPES = [action.value for action in ActionType]
    ACTION_EMOJIS = {
        ActionType.CREATED.value: '🎫',
        ActionType.CLOSED.value: '🔒',
        ActionType.ASSIGNED.value: '👥',
        ActionType.PRIORITY_CHANGE.value: '⚡',
        ActionType.STATUS_CHANGE.value: '🔄',
        ActionType.RATING_ADDED.value: '⭐',
        ActionType.TAG_ADDED.value: '🏷️',
        ActionType.TAG_REMOVED.value: '🗑️',
        ActionType.TRANSFERRED.value: '📤',
        ActionType.ESCALATED.value: '⬆️',
        ActionType.MESSAGE_ADDED.value: '💬',
        ActionType.AUTO_REPLY.value: '🤖'
    }
    ACTION_DESCRIPTIONS = {
        ActionType.CREATED.value: '票券已建立',
        ActionType.CLOSED.value: '票券已關閉',
        ActionType.ASSIGNED.value: '票券已指派',
        ActionType.PRIORITY_CHANGE.value: '優先級已變更',
        ActionType.STATUS_CHANGE.value: '狀態已變更',
        ActionType.RATING_ADDED.value: '用戶已評分',
        ActionType.TAG_ADDED.value: '標籤已添加',
        ActionType.TAG_REMOVED.value: '標籤已移除',
        ActionType.TRANSFERRED.value: '票券已轉移',
        ActionType.ESCALATED.value: '票券已升級',
        ActionType.MESSAGE_ADDED.value: '消息已添加',
        ActionType.AUTO_REPLY.value: '自動回覆已觸發'
    }

    # ===== SLA 相關常數 =====
    SLA_WARNING_THRESHOLDS = {
        Priority.HIGH.value: 0.8,
        Priority.MEDIUM.value: 0.9,
        Priority.LOW.value: 0.95
    }
    SLA_ESCALATION_THRESHOLDS = {
        Priority.HIGH.value: 1.2,
        Priority.MEDIUM.value: 1.5,
        Priority.LOW.value: 2.0
    }

    # ===== 評分相關常數 =====
    RATING_EMOJIS = {i: "⭐" * i for i in range(1, 6)}
    RATING_DESCRIPTIONS = {
        1: "非常不滿意 - 服務需要大幅改善",
        2: "不滿意 - 服務有明顯問題",
        3: "普通 - 服務基本符合預期",
        4: "滿意 - 服務良好",
        5: "非常滿意 - 服務超出預期"
    }
    RATING_COLORS = {
        1: discord.Color.dark_red(),
        2: discord.Color.red(),
        3: discord.Color.orange(),
        4: discord.Color.green(),
        5: discord.Color.dark_green()
    }

    # ===== UI 相關常數 =====
    PAGINATION_SIZE = 5
    MAX_EMBED_FIELDS = 25
    MAX_SELECT_OPTIONS = 25
    MODAL_TIMEOUT = 600
    VIEW_TIMEOUT = 300
    BUTTON_TIMEOUT = 300
    EMBED_TITLE_MAX = 256
    EMBED_DESCRIPTION_MAX = 4096
    EMBED_FIELD_NAME_MAX = 256
    EMBED_FIELD_VALUE_MAX = 1024
    EMBED_FOOTER_MAX = 2048
    EMBED_AUTHOR_MAX = 256

    # ===== 限制常數 =====
    LIMITS = {
        'max_tickets_per_user': (1, 20),
        'max_tags_per_ticket': (0, 15),
        'max_template_length': (10, 4000),
        'max_feedback_length': (0, 1000),
        'max_reason_length': (0, 500),
        'max_search_results': (5, 100),
        'sla_response_minutes': (5, 1440),
        'auto_close_hours': (1, 168),
        'rating': (1, 5),
        'template_name_length': (2, 100),
        'auto_reply_keywords': (1, 20),
        'channel_name_length': (3, 50),
        'tag_name_length': (1, 30),
        'batch_operation_size': (1, 100)
    }

    # ===== 快取相關常數 =====
    CACHE_TIMEOUTS = {
        'settings': 300,
        'auto_replies': 300,
        'statistics': 180,
        'sla_data': 60,
        'staff_workload': 120,
        'templates': 600,
        'specialties': 300
    }
    CACHE_KEYS = {
        'guild_settings': 'settings_{guild_id}',
        'auto_replies': 'auto_reply_{guild_id}',
        'staff_workload': 'workload_{guild_id}_{period}',
        'sla_stats': 'sla_{guild_id}_{period}',
        'ticket_stats': 'stats_{guild_id}_{type}_{period}',
        'templates': 'templates_{guild_id}',
        'specialties': 'specialties_{guild_id}'
    }

    # ... 其餘區塊（自動回覆、專精領域、模板等）照你的設計補上即可 ...


# ===== 錯誤和成功訊息 =====

ERROR_MESSAGES = {
    'no_permission': "❌ 你沒有權限執行此操作。",
    'ticket_not_found': "❌ 找不到指定的票券。",
    'not_ticket_channel': "❌ 此頻道不是票券頻道。",
    'already_rated': "❌ 此票券已經評分過了。",
    'invalid_rating': "❌ 評分必須在 1-5 之間。",
    'ticket_limit_reached': "❌ 你已達到票券上限！請先關閉現有票券。",
    'invalid_priority': "❌ 優先級必須是：high、medium 或 low",
    'database_error': "❌ 資料庫操作失敗，請稍後再試。",
    'channel_creation_failed': "❌ 建立票券頻道失敗。",
    'assignment_failed': "❌ 指派票券失敗。",
    'template_not_found': "❌ 找不到指定的模板。",
    'template_exists': "❌ 模板名稱已存在。",
    'auto_reply_exists': "❌ 自動回覆規則名稱已存在。",
    'invalid_setting': "❌ 無效的設定項目。",
    'invalid_value': "❌ 無效的設定值。",
    'user_not_found': "❌ 找不到指定的用戶。",
    'role_not_found': "❌ 找不到指定的身分組。",
    'channel_not_found': "❌ 找不到指定的頻道。",
    'search_too_short': "❌ 搜尋關鍵字太短，至少需要 2 個字元。",
    'no_search_results': "❌ 沒有找到符合條件的結果。",
    'operation_timeout': "❌ 操作超時，請重試。",
    'rate_limit_exceeded': "❌ 操作太頻繁，請稍後再試。",
    'ticket_already_closed': "❌ 此票券已經關閉。",
    'cannot_rate_open_ticket': "❌ 只能為已關閉的票券評分。",
    'invalid_ticket_type': "❌ 無效的票券類型。",
    'category_not_set': "❌ 尚未設定票券分類頻道。",
    'no_support_roles': "❌ 尚未設定客服身分組。",
    'template_too_long': "❌ 模板內容過長。",
    'too_many_tags': "❌ 標籤數量超過限制。",
    'invalid_tag_name': "❌ 標籤名稱格式無效。",
    'staff_not_available': "❌ 目前沒有可用的客服人員。",
    'auto_assign_disabled': "❌ 自動分配功能已停用。"
}

SUCCESS_MESSAGES = {
    'ticket_created': "✅ 票券已成功建立！",
    'ticket_closed': "✅ 票券已成功關閉。",
    'priority_updated': "✅ 優先級已更新。",
    'assignment_completed': "✅ 票券指派完成。",
    'rating_saved': "✅ 評分已保存，感謝你的回饋！",
    'setting_updated': "✅ 設定已更新。",
    'template_created': "✅ 模板已建立。",
    'template_updated': "✅ 模板已更新。",
    'template_deleted': "✅ 模板已刪除。",
    'auto_reply_created': "✅ 自動回覆規則已建立。",
    'auto_reply_updated': "✅ 自動回覆規則已更新。",
    'auto_reply_deleted': "✅ 自動回覆規則已刪除。",
    'specialties_updated': "✅ 客服專精已更新。",
    'tags_added': "✅ 標籤已添加。",
    'tags_removed': "✅ 標籤已移除。",
    'data_exported': "✅ 資料匯出完成。",
    'cache_cleared': "✅ 快取已清理。",
    'batch_operation_completed': "✅ 批次操作已完成。",
    'ticket_transferred': "✅ 票券已轉移。",
    'ticket_escalated': "✅ 票券已升級。",
    'notification_updated': "✅ 通知設定已更新。",
    'backup_created': "✅ 備份已建立。",
    'backup_restored': "✅ 備份已還原。",
    'system_optimized': "✅ 系統已最佳化。"
}

# ===== 其餘 class / 工具函數 / 模板等... =====
# 請將原本所有 class、方法、選項模板、嵌入模板、各類工具函式一併放到本檔案下（如 get_priority_emoji, format_duration_chinese, 等等）
# 註解、docstring 與型別註記可參考前方簡化版本、或直接問我要自動產生。

# ===== 環境變數預設值 =====

DEFAULT_ENV_VALUES = {
    'TICKET_MAX_PER_USER': '10',
    'TICKET_MAX_PER_GUILD': '1000',
    'TICKET_MAX_TEMPLATE_LENGTH': '2000',
    'TICKET_MAX_AUTO_REPLY_RULES': '50',
    'TICKET_MAX_TAGS': '10',
    'TICKET_DEFAULT_SLA_MINUTES': '60',
    'TICKET_MAX_SLA_MINUTES': '1440',
    'TICKET_MIN_SLA_MINUTES': '5',
    'TICKET_DEFAULT_AUTO_CLOSE_HOURS': '24',
    'TICKET_MAX_AUTO_CLOSE_HOURS': '168',
    'TICKET_CACHE_SETTINGS': '300',
    'TICKET_CACHE_STATS': '180',
    'TICKET_CACHE_AUTO_REPLY': '300',
    'TICKET_DEFAULT_PAGE_SIZE': '5',
    'TICKET_MAX_PAGE_SIZE': '20',
    'TICKET_MAX_SEARCH_RESULTS': '50',
    'TICKET_AUTO_ASSIGNMENT': 'true',
    'TICKET_SLA_MONITORING': 'true',
    'TICKET_AUTO_REPLIES': 'true',
    'TICKET_RATING_SYSTEM': 'true',
    'TICKET_ADVANCED_STATS': 'true',
    'TICKET_TEMPLATE_SYSTEM': 'true',
    'TICKET_TAG_SYSTEM': 'true',
    'TICKET_EXPORT_SYSTEM': 'false',
    'TICKET_BACKUP_SYSTEM': 'false',
    'TICKET_DEBUG': 'false',
    'TICKET_VERBOSE_LOG': 'false',
    'TICKET_SQL_LOG': 'false',
    'TICKET_PERF_LOG': 'false',
    'DISCORD_VIEW_TIMEOUT': '300',
    'DISCORD_MODAL_TIMEOUT': '600',
    'DISCORD_BUTTON_TIMEOUT': '300',
    'DISCORD_EMBED_DEFAULT': '0x00ff00',
    'DISCORD_EMBED_ERROR': '0xff0000',
    'DISCORD_EMBED_WARNING': '0xffaa00',
    'DISCORD_EMBED_INFO': '0x0099ff',
    'DISCORD_CHANNEL_NAME_MAX': '50',
    'DISCORD_CHANNEL_PREFIX': 'ticket-',
    'DISCORD_EPHEMERAL': 'true',
    'DISCORD_DELETE_COMMANDS': 'true',
    'DISCORD_CLEANUP_DELAY': '10'
}

# --- END ---
