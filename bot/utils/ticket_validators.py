# bot/utils/ticket_validators.py - 票券系統輸入驗證器

import discord
import re
from typing import Dict, List, Optional, Any, Tuple, Union
from datetime import datetime, timezone

from bot.utils.ticket_constants import (
    TicketConstants, is_valid_priority, is_valid_status,
    validate_text_input, validate_numeric_input, ERROR_MESSAGES
)
from bot.utils.debug import debug_log


class ValidationResult:
    """驗證結果類別"""
    
    def __init__(self, is_valid: bool, error_message: str = "", cleaned_value: Any = None):
        self.is_valid = is_valid
        self.error_message = error_message
        self.cleaned_value = cleaned_value
    
    def __bool__(self):
        return self.is_valid


class TextInputValidator:
    """文字輸入驗證器"""
    
    @staticmethod
    def validate_ticket_type(ticket_type: str) -> ValidationResult:
        """驗證票券類型"""
        if not ticket_type or not ticket_type.strip():
            return ValidationResult(False, "票券類型不能為空")
        
        cleaned_type = ticket_type.strip()
        is_valid, error = validate_text_input(cleaned_type, 'ticket_type')
        
        if not is_valid:
            return ValidationResult(False, f"票券類型格式錯誤：{error}")
        
        return ValidationResult(True, cleaned_value=cleaned_type)
    
    @staticmethod
    def validate_username(username: str) -> ValidationResult:
        """驗證用戶名"""
        if not username or not username.strip():
            return ValidationResult(False, "用戶名不能為空")
        
        cleaned_username = username.strip()
        is_valid, error = validate_text_input(cleaned_username, 'username')
        
        if not is_valid:
            return ValidationResult(False, f"用戶名格式錯誤：{error}")
        
        # 檢查特殊字符
        if any(char in cleaned_username for char in ['@', '#', ':']):
            return ValidationResult(False, "用戶名不能包含 @、# 或 : 字符")
        
        return ValidationResult(True, cleaned_value=cleaned_username)
    
    @staticmethod
    def validate_close_reason(reason: str) -> ValidationResult:
        """驗證關閉原因"""
        if not reason:
            return ValidationResult(True, cleaned_value="")
        
        cleaned_reason = reason.strip()
        is_valid, error = validate_text_input(cleaned_reason, 'close_reason')
        
        if not is_valid:
            return ValidationResult(False, f"關閉原因格式錯誤：{error}")
        
        return ValidationResult(True, cleaned_value=cleaned_reason)
    
    @staticmethod
    def validate_rating_feedback(feedback: str) -> ValidationResult:
        """驗證評分回饋"""
        if not feedback:
            return ValidationResult(True, cleaned_value="")
        
        cleaned_feedback = feedback.strip()
        is_valid, error = validate_text_input(cleaned_feedback, 'rating_feedback')
        
        if not is_valid:
            return ValidationResult(False, f"評分回饋格式錯誤：{error}")
        
        # 檢查是否包含不當內容
        inappropriate_words = ['spam', 'test', '測試']  # 可以擴展
        if any(word.lower() in cleaned_feedback.lower() for word in inappropriate_words):
            # 這裡只是警告，不阻止提交
            debug_log(f"[Validator] 評分回饋可能包含不當內容：{cleaned_feedback}")
        
        return ValidationResult(True, cleaned_value=cleaned_feedback)
    
    @staticmethod
    def validate_template_name(name: str) -> ValidationResult:
        """驗證模板名稱"""
        if not name or not name.strip():
            return ValidationResult(False, "模板名稱不能為空")
        
        cleaned_name = name.strip()
        is_valid, error = validate_text_input(cleaned_name, 'template_name')
        
        if not is_valid:
            return ValidationResult(False, f"模板名稱格式錯誤：{error}")
        
        return ValidationResult(True, cleaned_value=cleaned_name)
    
    @staticmethod
    def validate_template_content(content: str) -> ValidationResult:
        """驗證模板內容"""
        if not content or not content.strip():
            return ValidationResult(False, "模板內容不能為空")
        
        cleaned_content = content.strip()
        is_valid, error = validate_text_input(cleaned_content, 'template_content')
        
        if not is_valid:
            return ValidationResult(False, f"模板內容格式錯誤：{error}")
        
        return ValidationResult(True, cleaned_value=cleaned_content)
    
    @staticmethod
    def validate_tag_name(tag: str) -> ValidationResult:
        """驗證標籤名稱"""
        if not tag or not tag.strip():
            return ValidationResult(False, "標籤名稱不能為空")
        
        cleaned_tag = tag.strip()
        is_valid, error = validate_text_input(cleaned_tag, 'tag_name')
        
        if not is_valid:
            return ValidationResult(False, f"標籤名稱格式錯誤：{error}")
        
        return ValidationResult(True, cleaned_value=cleaned_tag)
    
    @staticmethod
    def validate_search_keyword(keyword: str) -> ValidationResult:
        """驗證搜尋關鍵字"""
        if not keyword or not keyword.strip():
            return ValidationResult(False, "搜尋關鍵字不能為空")
        
        cleaned_keyword = keyword.strip()
        
        if len(cleaned_keyword) < 2:
            return ValidationResult(False, "搜尋關鍵字至少需要2個字元")
        
        if len(cleaned_keyword) > 100:
            return ValidationResult(False, "搜尋關鍵字不能超過100個字元")
        
        # 移除特殊SQL字符以防注入
        dangerous_chars = ['\'', '"', ';', '--', '/*', '*/', 'DROP', 'DELETE', 'UPDATE']
        for char in dangerous_chars:
            if char.lower() in cleaned_keyword.lower():
                return ValidationResult(False, "搜尋關鍵字包含不允許的字符")
        
        return ValidationResult(True, cleaned_value=cleaned_keyword)
    
    @staticmethod
    def validate_auto_reply_name(name: str) -> ValidationResult:
        """驗證自動回覆規則名稱"""
        if not name or not name.strip():
            return ValidationResult(False, "自動回覆規則名稱不能為空")
        
        cleaned_name = name.strip()
        is_valid, error = validate_text_input(cleaned_name, 'auto_reply_name')
        
        if not is_valid:
            return ValidationResult(False, f"自動回覆規則名稱格式錯誤：{error}")
        
        return ValidationResult(True, cleaned_value=cleaned_name)
    
    @staticmethod
    def validate_keywords_list(keywords_text: str) -> ValidationResult:
        """驗證關鍵字列表"""
        if not keywords_text or not keywords_text.strip():
            return ValidationResult(False, "關鍵字不能為空")
        
        # 解析關鍵字
        keywords = re.split(r'[,\s]+', keywords_text.strip())
        keywords = [kw.strip() for kw in keywords if kw.strip()]
        
        if not keywords:
            return ValidationResult(False, "請至少提供一個有效關鍵字")
        
        if len(keywords) > 20:
            return ValidationResult(False, "關鍵字數量不能超過20個")
        
        # 驗證每個關鍵字
        cleaned_keywords = []
        for keyword in keywords:
            result = TextInputValidator.validate_keyword(keyword)
            if not result.is_valid:
                return ValidationResult(False, f"關鍵字 '{keyword}' 格式錯誤：{result.error_message}")
            cleaned_keywords.append(result.cleaned_value)
        
        return ValidationResult(True, cleaned_value=cleaned_keywords)
    
    @staticmethod
    def validate_keyword(keyword: str) -> ValidationResult:
        """驗證單個關鍵字"""
        if not keyword or not keyword.strip():
            return ValidationResult(False, "關鍵字不能為空")
        
        cleaned_keyword = keyword.strip()
        is_valid, error = validate_text_input(cleaned_keyword, 'keyword')
        
        if not is_valid:
            return ValidationResult(False, f"關鍵字格式錯誤：{error}")
        
        return ValidationResult(True, cleaned_value=cleaned_keyword)


class NumericInputValidator:
    """數值輸入驗證器"""
    
    @staticmethod
    def validate_rating(rating: Union[str, int]) -> ValidationResult:
        """驗證評分"""
        try:
            rating_int = int(rating)
        except (ValueError, TypeError):
            return ValidationResult(False, "評分必須是數字")
        
        is_valid, error = validate_numeric_input(rating_int, 'rating')
        if not is_valid:
            return ValidationResult(False, f"評分範圍錯誤：{error}")
        
        return ValidationResult(True, cleaned_value=rating_int)
    
    @staticmethod
    def validate_ticket_limit(limit: Union[str, int]) -> ValidationResult:
        """驗證票券限制數量"""
        try:
            limit_int = int(limit)
        except (ValueError, TypeError):
            return ValidationResult(False, "票券限制必須是數字")
        
        is_valid, error = validate_numeric_input(limit_int, 'max_tickets_per_user')
        if not is_valid:
            return ValidationResult(False, f"票券限制範圍錯誤：{error}")
        
        return ValidationResult(True, cleaned_value=limit_int)
    
    @staticmethod
    def validate_sla_minutes(minutes: Union[str, int]) -> ValidationResult:
        """驗證SLA時間（分鐘）"""
        try:
            minutes_int = int(minutes)
        except (ValueError, TypeError):
            return ValidationResult(False, "SLA時間必須是數字")
        
        is_valid, error = validate_numeric_input(minutes_int, 'sla_response_minutes')
        if not is_valid:
            return ValidationResult(False, f"SLA時間範圍錯誤：{error}")
        
        return ValidationResult(True, cleaned_value=minutes_int)
    
    @staticmethod
    def validate_auto_close_hours(hours: Union[str, int]) -> ValidationResult:
        """驗證自動關閉時間（小時）"""
        try:
            hours_int = int(hours)
        except (ValueError, TypeError):
            return ValidationResult(False, "自動關閉時間必須是數字")
        
        is_valid, error = validate_numeric_input(hours_int, 'auto_close_hours')
        if not is_valid:
            return ValidationResult(False, f"自動關閉時間範圍錯誤：{error}")
        
        return ValidationResult(True, cleaned_value=hours_int)
    
    @staticmethod
    def validate_page_number(page: Union[str, int], max_page: int = None) -> ValidationResult:
        """驗證頁碼"""
        try:
            page_int = int(page)
        except (ValueError, TypeError):
            return ValidationResult(False, "頁碼必須是數字")
        
        if page_int < 1:
            return ValidationResult(False, "頁碼必須大於0")
        
        if max_page and page_int > max_page:
            return ValidationResult(False, f"頁碼不能超過{max_page}")
        
        return ValidationResult(True, cleaned_value=page_int)
    
    @staticmethod
    def validate_ticket_id(ticket_id: Union[str, int]) -> ValidationResult:
        """驗證票券ID"""
        try:
            ticket_id_int = int(ticket_id)
        except (ValueError, TypeError):
            return ValidationResult(False, "票券ID必須是數字")
        
        if ticket_id_int < 1:
            return ValidationResult(False, "票券ID必須大於0")
        
        if ticket_id_int > 999999:  # 6位數限制
            return ValidationResult(False, "票券ID過大")
        
        return ValidationResult(True, cleaned_value=ticket_id_int)


class PermissionValidator:
    """權限驗證器"""
    
    @staticmethod
    def validate_user_permissions(user: discord.Member, required_permissions: List[str]) -> ValidationResult:
        """驗證用戶權限"""
        if not user:
            return ValidationResult(False, "用戶不存在")
        
        user_permissions = user.guild_permissions
        
        missing_permissions = []
        for perm_name in required_permissions:
            if not hasattr(user_permissions, perm_name):
                missing_permissions.append(perm_name)
                continue
            
            if not getattr(user_permissions, perm_name):
                missing_permissions.append(perm_name)
        
        if missing_permissions:
            return ValidationResult(
                False, 
                f"缺少必要權限：{', '.join(missing_permissions)}"
            )
        
        return ValidationResult(True)
    
    @staticmethod
    def validate_bot_permissions(guild: discord.Guild, required_permissions: List[str]) -> ValidationResult:
        """驗證機器人權限"""
        if not guild:
            return ValidationResult(False, "伺服器不存在")
        
        bot_member = guild.me
        if not bot_member:
            return ValidationResult(False, "機器人不在此伺服器中")
        
        bot_permissions = bot_member.guild_permissions
        
        missing_permissions = []
        for perm_name in required_permissions:
            if not hasattr(bot_permissions, perm_name):
                missing_permissions.append(perm_name)
                continue
            
            if not getattr(bot_permissions, perm_name):
                missing_permissions.append(perm_name)
        
        if missing_permissions:
            return ValidationResult(
                False,
                f"機器人缺少必要權限：{', '.join(missing_permissions)}"
            )
        
        return ValidationResult(True)
    
    @staticmethod
    def validate_channel_permissions(user: discord.Member, channel: discord.TextChannel, 
                                   required_permissions: List[str]) -> ValidationResult:
        """驗證頻道權限"""
        if not user or not channel:
            return ValidationResult(False, "用戶或頻道不存在")
        
        user_permissions = channel.permissions_for(user)
        
        missing_permissions = []
        for perm_name in required_permissions:
            if not hasattr(user_permissions, perm_name):
                missing_permissions.append(perm_name)
                continue
            
            if not getattr(user_permissions, perm_name):
                missing_permissions.append(perm_name)
        
        if missing_permissions:
            return ValidationResult(
                False,
                f"在頻道 {channel.mention} 中缺少權限：{', '.join(missing_permissions)}"
            )
        
        return ValidationResult(True)
    
    @staticmethod
    def validate_support_staff(user: discord.Member, support_roles: List[int]) -> ValidationResult:
        """驗證是否為客服人員"""
        if not user:
            return ValidationResult(False, "用戶不存在")
        
        # 檢查管理員權限
        if user.guild_permissions.manage_guild:
            return ValidationResult(True)
        
        # 檢查客服身分組
        user_role_ids = {role.id for role in user.roles}
        if any(role_id in user_role_ids for role_id in support_roles):
            return ValidationResult(True)
        
        return ValidationResult(False, "不是客服人員")


class SettingValidator:
    """設定值驗證器"""
    
    @staticmethod
    def validate_category_channel(guild: discord.Guild, channel_input: str) -> ValidationResult:
        """驗證分類頻道"""
        if not channel_input.strip():
            return ValidationResult(False, "頻道不能為空")
        
        # 解析頻道提及
        channel = ChannelValidator.parse_channel_mention(channel_input, guild)
        if not channel:
            return ValidationResult(False, "找不到指定的頻道")
        
        if not isinstance(channel, discord.CategoryChannel):
            return ValidationResult(False, "必須是分類頻道")
        
        return ValidationResult(True, cleaned_value=channel.id)
    
    @staticmethod
    def validate_log_channel(guild: discord.Guild, channel_input: str) -> ValidationResult:
        """驗證日誌頻道"""
        if not channel_input.strip():
            return ValidationResult(False, "頻道不能為空")
        
        channel = ChannelValidator.parse_channel_mention(channel_input, guild)
        if not channel:
            return ValidationResult(False, "找不到指定的頻道")
        
        if not isinstance(channel, discord.TextChannel):
            return ValidationResult(False, "必須是文字頻道")
        
        # 檢查機器人是否有發送訊息權限
        bot_permissions = channel.permissions_for(guild.me)
        if not bot_permissions.send_messages:
            return ValidationResult(False, f"機器人在 {channel.mention} 中沒有發送訊息權限")
        
        return ValidationResult(True, cleaned_value=channel.id)
    
    @staticmethod
    def validate_support_roles(guild: discord.Guild, roles_input: str) -> ValidationResult:
        """驗證客服身分組"""
        if not roles_input.strip():
            return ValidationResult(False, "身分組不能為空")
        
        # 解析多個身分組
        role_strings = [r.strip() for r in roles_input.split(',')]
        role_ids = []
        
        for role_string in role_strings:
            if not role_string:
                continue
            
            role = RoleValidator.parse_role_mention(role_string, guild)
            if not role:
                return ValidationResult(False, f"找不到身分組：{role_string}")
            
            role_ids.append(role.id)
        
        if not role_ids:
            return ValidationResult(False, "請至少指定一個有效的身分組")
        
        return ValidationResult(True, cleaned_value=role_ids)
    
    @staticmethod
    def validate_welcome_message(message: str) -> ValidationResult:
        """驗證歡迎訊息"""
        if not message:
            return ValidationResult(True, cleaned_value="")  # 允許空白
        
        cleaned_message = message.strip()
        
        if len(cleaned_message) > 2000:
            return ValidationResult(False, "歡迎訊息不能超過2000個字元")
        
        return ValidationResult(True, cleaned_value=cleaned_message)


class ChannelValidator:
    """頻道驗證器"""
    
    @staticmethod
    def parse_channel_mention(channel_input: str, guild: discord.Guild) -> Optional[discord.abc.GuildChannel]:
        """解析頻道提及"""
        if not channel_input or not guild:
            return None
        
        channel_input = channel_input.strip()
        
        # 直接頻道ID
        if channel_input.isdigit():
            return guild.get_channel(int(channel_input))
        
        # 頻道提及格式 <#123456>
        mention_match = re.match(r'<#(\d+)>', channel_input)
        if mention_match:
            channel_id = int(mention_match.group(1))
            return guild.get_channel(channel_id)
        
        # 頻道名稱
        for channel in guild.channels:
            if channel.name.lower() == channel_input.lower():
                return channel
        
        return None
    
    @staticmethod
    def validate_ticket_channel(channel: discord.TextChannel) -> ValidationResult:
        """驗證是否為票券頻道"""
        if not channel:
            return ValidationResult(False, "頻道不存在")
        
        if not channel.name.startswith('ticket-'):
            return ValidationResult(False, "不是票券頻道")
        
        return ValidationResult(True)
    
    @staticmethod
    def validate_channel_name(name: str) -> ValidationResult:
        """驗證頻道名稱"""
        if not name or not name.strip():
            return ValidationResult(False, "頻道名稱不能為空")
        
        cleaned_name = name.strip().lower()
        
        # Discord 頻道名稱規則
        if not re.match(r'^[a-z0-9\-_]{1,100}# bot/utils/ticket_validators.py - 票券系統輸入驗證器

import discord
import re
from typing import Dict, List, Optional, Any, Tuple, Union
from datetime import datetime, timezone

from bot.utils.ticket_constants import (
    TicketConstants, is_valid_priority, is_valid_status,, cleaned_name):
            return ValidationResult(False, "頻道名稱只能包含小寫字母、數字、連字符和底線")
        
        is_valid, error = validate_text_input(cleaned_name, 'channel_name_length')
        if not is_valid:
            return ValidationResult(False, f"頻道名稱長度錯誤：{error}")
        
        return ValidationResult(True, cleaned_value=cleaned_name)


class RoleValidator:
    """身分組驗證器"""
    
    @staticmethod
    def parse_role_mention(role_input: str, guild: discord.Guild) -> Optional[discord.Role]:
        """解析身分組提及"""
        if not role_input or not guild:
            return None
        
        role_input = role_input.strip()
        
        # 直接身分組ID
        if role_input.isdigit():
            return guild.get_role(int(role_input))
        
        # 身分組提及格式 <@&123456>
        mention_match = re.match(r'<@&(\d+)>', role_input)
        if mention_match:
            role_id = int(mention_match.group(1))
            return guild.get_role(role_id)
        
        # 身分組名稱
        for role in guild.roles:
            if role.name.lower() == role_input.lower():
                return role
        
        return None
    
    @staticmethod
    def validate_assignable_role(role: discord.Role, guild: discord.Guild) -> ValidationResult:
        """驗證身分組是否可分配"""
        if not role:
            return ValidationResult(False, "身分組不存在")
        
        if role.is_default():
            return ValidationResult(False, "不能使用 @everyone 身分組")
        
        if role.managed:
            return ValidationResult(False, "不能使用由機器人管理的身分組")
        
        # 檢查機器人是否能管理此身分組
        bot_top_role = guild.me.top_role
        if role >= bot_top_role:
            return ValidationResult(False, f"機器人無法管理身分組 {role.name}（權限層級過高）")
        
        return ValidationResult(True)


class PriorityStatusValidator:
    """優先級和狀態驗證器"""
    
    @staticmethod
    def validate_priority(priority: str) -> ValidationResult:
        """驗證優先級"""
        if not priority:
            return ValidationResult(False, "優先級不能為空")
        
        priority = priority.lower().strip()
        
        if not is_valid_priority(priority):
            valid_priorities = ', '.join(TicketConstants.PRIORITIES)
            return ValidationResult(False, f"無效的優先級。有效值：{valid_priorities}")
        
        return ValidationResult(True, cleaned_value=priority)
    
    @staticmethod
    def validate_status(status: str) -> ValidationResult:
        """驗證狀態"""
        if not status:
            return ValidationResult(False, "狀態不能為空")
        
        status = status.lower().strip()
        
        if not is_valid_status(status):
            valid_statuses = ', '.join(TicketConstants.STATUSES)
            return ValidationResult(False, f"無效的狀態。有效值：{valid_statuses}")
        
        return ValidationResult(True, cleaned_value=status)


class BatchOperationValidator:
    """批次操作驗證器"""
    
    @staticmethod
    def validate_batch_size(size: Union[str, int]) -> ValidationResult:
        """驗證批次操作大小"""
        try:
            size_int = int(size)
        except (ValueError, TypeError):
            return ValidationResult(False, "批次大小必須是數字")
        
        is_valid, error = validate_numeric_input(size_int, 'batch_operation_size')
        if not is_valid:
            return ValidationResult(False, f"批次大小範圍錯誤：{error}")
        
        return ValidationResult(True, cleaned_value=size_int)
    
    @staticmethod
    def validate_inactive_threshold(hours: Union[str, int]) -> ValidationResult:
        """驗證無活動時間閾值"""
        try:
            hours_int = int(hours)
        except (ValueError, TypeError):
            return ValidationResult(False, "時間閾值必須是數字")
        
        if hours_int < 1:
            return ValidationResult(False, "時間閾值必須大於0小時")
        
        if hours_int > 8760:  # 一年
            return ValidationResult(False, "時間閾值不能超過一年")
        
        return ValidationResult(True, cleaned_value=hours_int)


class DateTimeValidator:
    """日期時間驗證器"""
    
    @staticmethod
    def validate_date_range(start_date: str, end_date: str) -> ValidationResult:
        """驗證日期範圍"""
        try:
            start_dt = datetime.fromisoformat(start_date.replace('T', ' '))
            end_dt = datetime.fromisoformat(end_date.replace('T', ' '))
        except ValueError:
            return ValidationResult(False, "日期格式錯誤，請使用 YYYY-MM-DD 格式")
        
        if start_dt >= end_dt:
            return ValidationResult(False, "開始日期必須早於結束日期")
        
        # 檢查日期範圍不能太大（避免性能問題）
        if (end_dt - start_dt).days > 365:
            return ValidationResult(False, "日期範圍不能超過一年")
        
        return ValidationResult(True, cleaned_value=(start_dt, end_dt))


# ===== 複合驗證器 =====

class TicketCreationValidator:
    """票券建立驗證器"""
    
    @staticmethod
    def validate_creation_request(user: discord.Member, ticket_type: str, priority: str,
                                guild_settings: Dict[str, Any], current_tickets: int) -> ValidationResult:
        """驗證票券建立請求"""
        # 驗證票券類型
        type_result = TextInputValidator.validate_ticket_type(ticket_type)
        if not type_result:
            return type_result
        
        # 驗證優先級
        priority_result = PriorityStatusValidator.validate_priority(priority)
        if not priority_result:
            return priority_result
        
        # 檢查票券限制
        max_tickets = guild_settings.get('max_tickets_per_user', 3)
        if current_tickets >= max_tickets:
            return ValidationResult(
                False,
                f"已達到票券上限（{max_tickets}張）！請先關閉現有票券。"
            )
        
        # 檢查分類頻道設定
        if not guild_settings.get('category_id'):
            return ValidationResult(False, "尚未設定票券分類頻道，請聯繫管理員")
        
        return ValidationResult(True)


class SettingsUpdateValidator:
    """設定更新驗證器"""
    
    @staticmethod
    def validate_setting_update(setting_name: str, value: str, guild: discord.Guild) -> ValidationResult:
        """驗證設定更新"""
        if setting_name == 'category':
            return SettingValidator.validate_category_channel(guild, value)
        elif setting_name == 'log_channel':
            return SettingValidator.validate_log_channel(guild, value)
        elif setting_name == 'sla_alert_channel':
            return SettingValidator.validate_log_channel(guild, value)  # 使用相同驗證
        elif setting_name == 'support_roles':
            return SettingValidator.validate_support_roles(guild, value)
        elif setting_name == 'welcome':
            return SettingValidator.validate_welcome_message(value)
        elif setting_name == 'limits':
            return NumericInputValidator.validate_ticket_limit(value)
        elif setting_name == 'auto_close':
            return NumericInputValidator.validate_auto_close_hours(value)
        elif setting_name == 'sla_response':
            return NumericInputValidator.validate_sla_minutes(value)
        elif setting_name == 'auto_assign':
            # 布林值驗證
            bool_value = value.lower() in ['true', '1', 'yes', 'on', '啟用', 'enable']
            return ValidationResult(True, cleaned_value=bool_value)
        else:
            return ValidationResult(False, f"未知的設定項目：{setting_name}")


# ===== 工具函數 =====

def create_validation_error_embed(title: str, error_message: str) -> discord.Embed:
    """建立驗證錯誤嵌入"""
    embed = discord.Embed(
        title=f"❌ {title}",
        description=error_message,
        color=discord.Color.red()
    )
    return embed


def validate_discord_limits(content: str, content_type: str) -> ValidationResult:
    """驗證Discord內容限制"""
    limits = {
        'embed_title': 256,
        'embed_description': 4096,
        'embed_field_name': 256,
        'embed_field_value': 1024,
        'embed_footer': 2048,
        'message_content': 2000,
        'modal_text_short': 4000,
        'modal_text_paragraph': 4000
    }
    
    if content_type not in limits:
        return ValidationResult(True, cleaned_value=content)
    
    max_length = limits[content_type]
    if len(content) > max_length:
        return ValidationResult(
            False,
            f"{content_type} 長度不能超過 {max_length} 個字元（當前：{len(content)}）"
        )
    
    return ValidationResult(True, cleaned_value=content)


def sanitize_user_input(text: str) -> str:
    """清理用戶輸入"""
    if not text:
        return ""
    
    # 移除控制字符
    text = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', text)
    
    # 限制連續空白字符
    text = re.sub(r'\s+', ' ', text)
    
    # 移除前後空白
    text = text.strip()
    
    return text


def validate_file_upload(filename: str, file_size: int) -> ValidationResult:
    """驗證檔案上傳"""
    # 檢查檔案名稱
    if not filename or len(filename) > 255:
        return ValidationResult(False, "檔案名稱無效或過長")
    
    # 檢查檔案大小（Discord限制8MB）
    max_size = 8 * 1024 * 1024  # 8MB
    if file_size > max_size:
        return ValidationResult(False, f"檔案大小不能超過 {max_size // (1024*1024)}MB")
    
    # 檢查檔案擴展名
    allowed_extensions = ['.txt', '.log', '.csv', '.json', '.png', '.jpg', '.jpeg', '.gif', '.pdf']
    file_ext = '.' + filename.split('.')[-1].lower() if '.' in filename else ''
    
    if file_ext not in allowed_extensions:
        return ValidationResult(False, f"不支援的檔案類型：{file_ext}")
    
    return ValidationResult(True)


def check_rate_limit(user_id: int, action: str, limit_per_minute: int = 10) -> ValidationResult:
    """檢查速率限制"""
    # 這裡可以實現簡單的記憶體快取速率限制
    # 實際應用中建議使用Redis或資料庫
    import time
    from collections import defaultdict
    
    # 簡單的記憶體速率限制（重啟後重置）
    if not hasattr(check_rate_limit, 'rate_cache'):
        check_rate_limit.rate_cache = defaultdict(list)
    
    now = time.time()
    cache_key = f"{user_id}:{action}"
    
    # 清理過期記錄
    check_rate_limit.rate_cache[cache_key] = [
        timestamp for timestamp in check_rate_limit.rate_cache[cache_key]
        if now - timestamp < 60  # 保留最近1分鐘的記錄
    ]
    
    # 檢查是否超過限制
    if len(check_rate_limit.rate_cache[cache_key]) >= limit_per_minute:
        return ValidationResult(False, f"操作太頻繁，請稍後再試（每分鐘限制{limit_per_minute}次）")
    
    # 記錄此次操作
    check_rate_limit.rate_cache[cache_key].append(now)
    
    return ValidationResult(True)


def validate_json_field(json_str: str, field_name: str) -> ValidationResult:
    """驗證JSON欄位"""
    if not json_str:
        return ValidationResult(True, cleaned_value=None)
    
    try:
        import json
        parsed_data = json.loads(json_str)
        return ValidationResult(True, cleaned_value=parsed_data)
    except json.JSONDecodeError as e:
        return ValidationResult(False, f"{field_name} JSON格式錯誤：{str(e)}")


def validate_guild_context(guild: discord.Guild) -> ValidationResult:
    """驗證伺服器環境"""
    if not guild:
        return ValidationResult(False, "找不到伺服器")
    
    if not guild.me:
        return ValidationResult(False, "機器人不在此伺服器中")
    
    # 檢查基本權限
    required_permissions = ['read_messages', 'send_messages', 'embed_links']
    bot_permissions = guild.me.guild_permissions
    
    missing_permissions = []
    for perm in required_permissions:
        if not getattr(bot_permissions, perm, False):
            missing_permissions.append(perm)
    
    if missing_permissions:
        return ValidationResult(
            False,
            f"機器人缺少基本權限：{', '.join(missing_permissions)}"
        )
    
    return ValidationResult(True)


# ===== 預設驗證器集合 =====

class DefaultValidators:
    """預設驗證器集合"""
    
    @staticmethod
    def get_ticket_creation_validators() -> List[Callable]:
        """取得票券建立驗證器列表"""
        return [
            lambda user, **kwargs: PermissionValidator.validate_user_permissions(
                user, ['read_messages', 'send_messages']
            ),
            lambda **kwargs: validate_guild_context(kwargs.get('guild')),
            lambda user_id, **kwargs: check_rate_limit(user_id, 'create_ticket', 5)
        ]
    
    @staticmethod
    def get_admin_operation_validators() -> List[Callable]:
        """取得管理操作驗證器列表"""
        return [
            lambda user, **kwargs: PermissionValidator.validate_user_permissions(
                user, ['manage_guild']
            ),
            lambda **kwargs: validate_guild_context(kwargs.get('guild')),
            lambda user_id, **kwargs: check_rate_limit(user_id, 'admin_operation', 20)
        ]
    
    @staticmethod
    def get_staff_operation_validators() -> List[Callable]:
        """取得客服操作驗證器列表"""
        return [
            lambda user, support_roles, **kwargs: PermissionValidator.validate_support_staff(
                user, support_roles
            ),
            lambda **kwargs: validate_guild_context(kwargs.get('guild')),
            lambda user_id, **kwargs: check_rate_limit(user_id, 'staff_operation', 30)
        ]


# ===== 主要驗證協調器 =====

class TicketValidationCoordinator:
    """票券驗證協調器"""
    
    def __init__(self):
        self.text_validator = TextInputValidator()
        self.numeric_validator = NumericInputValidator()
        self.permission_validator = PermissionValidator()
        self.setting_validator = SettingValidator()
        self.channel_validator = ChannelValidator()
        self.role_validator = RoleValidator()
    
    async def validate_ticket_creation(self, user: discord.Member, ticket_type: str, 
                                     priority: str, guild_settings: Dict[str, Any], 
                                     current_tickets: int) -> ValidationResult:
        """全面驗證票券建立"""
        # 執行所有相關驗證
        validators = [
            lambda: TicketCreationValidator.validate_creation_request(
                user, ticket_type, priority, guild_settings, current_tickets
            ),
            lambda: check_rate_limit(user.id, 'create_ticket', 5),
            lambda: validate_guild_context(user.guild)
        ]
        
        for validator in validators:
            result = validator()
            if not result.is_valid:
                return result
        
        return ValidationResult(True)
    
    async def validate_settings_update(self, user: discord.Member, setting_name: str, 
                                     value: str, guild: discord.Guild) -> ValidationResult:
        """全面驗證設定更新"""
        # 權限檢查
        perm_result = self.permission_validator.validate_user_permissions(
            user, ['manage_guild']
        )
        if not perm_result.is_valid:
            return perm_result
        
        # 速率限制
        rate_result = check_rate_limit(user.id, 'update_settings', 10)
        if not rate_result.is_valid:
            return rate_result
        
        # 設定值驗證
        setting_result = SettingsUpdateValidator.validate_setting_update(
            setting_name, value, guild
        )
        if not setting_result.is_valid:
            return setting_result
        
        return ValidationResult(True, cleaned_value=setting_result.cleaned_value)
    
    async def validate_ticket_operation(self, user: discord.Member, operation: str, 
                                      ticket_info: Dict[str, Any], 
                                      support_roles: List[int]) -> ValidationResult:
        """驗證票券操作"""
        # 基本檢查
        if not ticket_info:
            return ValidationResult(False, ERROR_MESSAGES['ticket_not_found'])
        
        # 權限檢查
        if operation in ['close', 'rate']:
            # 只有票券創建者可以關閉和評分
            if str(user.id) != ticket_info['discord_id']:
                # 客服也可以關閉
                if operation == 'close':
                    staff_result = self.permission_validator.validate_support_staff(
                        user, support_roles
                    )
                    if not staff_result.is_valid:
                        return ValidationResult(False, ERROR_MESSAGES['no_permission'])
                else:
                    return ValidationResult(False, ERROR_MESSAGES['no_permission'])
        
        elif operation in ['assign', 'priority', 'transfer']:
            # 只有客服可以執行
            staff_result = self.permission_validator.validate_support_staff(
                user, support_roles
            )
            if not staff_result.is_valid:
                return ValidationResult(False, ERROR_MESSAGES['no_permission'])
        
        # 狀態檢查
        if operation == 'rate' and ticket_info['status'] != 'closed':
            return ValidationResult(False, ERROR_MESSAGES['cannot_rate_open_ticket'])
        
        if operation in ['assign', 'priority'] and ticket_info['status'] == 'closed':
            return ValidationResult(False, "無法操作已關閉的票券")
        
        # 速率限制
        rate_result = check_rate_limit(user.id, f'ticket_{operation}', 15)
        if not rate_result.is_valid:
            return rate_result
        
        return ValidationResult(True)
    
    def create_validation_summary(self, results: List[ValidationResult]) -> Dict[str, Any]:
        """建立驗證結果摘要"""
        summary = {
            'all_valid': all(result.is_valid for result in results),
            'total_checks': len(results),
            'passed_checks': sum(1 for result in results if result.is_valid),
            'failed_checks': [],
            'warnings': []
        }
        
        for i, result in enumerate(results):
            if not result.is_valid:
                summary['failed_checks'].append({
                    'check_index': i,
                    'error_message': result.error_message
                })
        
        return summary


# ===== 輔助函數 =====

def quick_validate_text(text: str, field_type: str) -> bool:
    """快速文字驗證（只返回布林值）"""
    result = TextInputValidator.validate_ticket_type(text) if field_type == 'ticket_type' else ValidationResult(True)
    return result.is_valid


def quick_validate_numeric(value: Union[str, int], field_type: str) -> bool:
    """快速數值驗證（只返回布林值）"""
    if field_type == 'rating':
        result = NumericInputValidator.validate_rating(value)
    elif field_type == 'ticket_limit':
        result = NumericInputValidator.validate_ticket_limit(value)
    else:
        result = ValidationResult(True)
    
    return result.is_valid


def get_validation_error_message(field_type: str, value: Any) -> str:
    """取得驗證錯誤訊息"""
    if field_type == 'ticket_type':
        result = TextInputValidator.validate_ticket_type(str(value))
    elif field_type == 'rating':
        result = NumericInputValidator.validate_rating(value)
    elif field_type == 'priority':
        result = PriorityStatusValidator.validate_priority(str(value))
    else:
        return "未知的驗證錯誤"
    
    return result.error_message if not result.is_valid else ""


# ===== 驗證裝飾器 =====

def validate_input(field_type: str):
    """輸入驗證裝飾器"""
    def decorator(func):
        async def wrapper(*args, **kwargs):
            # 這裡可以實現自動驗證邏輯
            # 根據函數參數自動進行驗證
            return await func(*args, **kwargs)
        return wrapper
    return decorator


def require_permissions(*permissions):
    """權限要求裝飾器"""
    def decorator(func):
        async def wrapper(interaction: discord.Interaction, *args, **kwargs):
            user = interaction.user
            
            # 檢查權限
            result = PermissionValidator.validate_user_permissions(user, list(permissions))
            if not result.is_valid:
                await interaction.response.send_message(
                    f"❌ {result.error_message}",
                    ephemeral=True
                )
                return
            
            return await func(interaction, *args, **kwargs)
        return wrapper
    return decorator


def validate_rate_limit(action: str, limit: int = 10):
    """速率限制驗證裝飾器"""
    def decorator(func):
        async def wrapper(interaction: discord.Interaction, *args, **kwargs):
            result = check_rate_limit(interaction.user.id, action, limit)
            if not result.is_valid:
                await interaction.response.send_message(
                    f"❌ {result.error_message}",
                    ephemeral=True
                )
                return
            
            return await func(interaction, *args, **kwargs)
        return wrapper
    return decorator