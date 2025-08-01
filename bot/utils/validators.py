# bot/utils/validators.py - 票券系統輸入驗證器
"""
票券系統輸入驗證器 - 簡化版
提供必要的輸入驗證功能
"""

import discord
import re
from typing import Dict, List, Optional, Any, Tuple, Union
from datetime import datetime, timezone
from dataclasses import dataclass

from bot.utils.constants import TicketConstants
from shared.logger import logger


@dataclass
class ValidationResult:
    """驗證結果"""
    is_valid: bool
    error_message: str = ""
    cleaned_value: Any = None
    
    def __bool__(self):
        return self.is_valid


class BaseValidator:
    """基礎驗證器"""
    
    @staticmethod
    def validate_text(text: str, min_length: int = 1, max_length: int = 1000,
                     field_name: str = "文字") -> ValidationResult:
        """驗證文字輸入"""
        if not text or not text.strip():
            return ValidationResult(False, f"{field_name}不能為空")
        
        cleaned_text = text.strip()
        
        if len(cleaned_text) < min_length:
            return ValidationResult(False, f"{field_name}至少需要{min_length}個字元")
        
        if len(cleaned_text) > max_length:
            return ValidationResult(False, f"{field_name}不能超過{max_length}個字元")
        
        return ValidationResult(True, cleaned_value=cleaned_text)
    
    @staticmethod
    def validate_number(value: Union[str, int], min_value: int = None, 
                       max_value: int = None, field_name: str = "數字") -> ValidationResult:
        """驗證數字輸入"""
        try:
            number = int(value)
        except (ValueError, TypeError):
            return ValidationResult(False, f"{field_name}必須是數字")
        
        if min_value is not None and number < min_value:
            return ValidationResult(False, f"{field_name}不能小於{min_value}")
        
        if max_value is not None and number > max_value:
            return ValidationResult(False, f"{field_name}不能大於{max_value}")
        
        return ValidationResult(True, cleaned_value=number)
    
    @staticmethod
    def validate_discord_id(discord_id: Union[str, int]) -> ValidationResult:
        """驗證Discord ID"""
        try:
            id_int = int(discord_id)
            # Discord ID應該是18位數字
            if 100000000000000000 <= id_int <= 999999999999999999:
                return ValidationResult(True, cleaned_value=id_int)
            else:
                return ValidationResult(False, "無效的Discord ID格式")
        except (ValueError, TypeError):
            return ValidationResult(False, "Discord ID必須是數字")


class TicketValidator:
    """票券驗證器"""
    
    @staticmethod
    def validate_ticket_type(ticket_type: str) -> ValidationResult:
        """驗證票券類型"""
        result = BaseValidator.validate_text(
            ticket_type, 
            min_length=2, 
            max_length=50, 
            field_name="票券類型"
        )
        
        if not result.is_valid:
            return result
        
        # 檢查是否包含非法字符
        if re.search(r'[<>@#&]', result.cleaned_value):
            return ValidationResult(False, "票券類型不能包含特殊字符")
        
        return result
    
    @staticmethod
    def validate_priority(priority: str) -> ValidationResult:
        """驗證優先級"""
        if not priority:
            return ValidationResult(False, "優先級不能為空")
        
        priority = priority.lower().strip()
        
        if priority not in TicketConstants.PRIORITIES:
            valid_priorities = ", ".join(TicketConstants.PRIORITIES)
            return ValidationResult(False, f"無效的優先級。有效值：{valid_priorities}")
        
        return ValidationResult(True, cleaned_value=priority)
    
    @staticmethod
    def validate_status(status: str) -> ValidationResult:
        """驗證狀態"""
        if not status:
            return ValidationResult(False, "狀態不能為空")
        
        status = status.lower().strip()
        
        if status not in TicketConstants.STATUSES:
            valid_statuses = ", ".join(TicketConstants.STATUSES)
            return ValidationResult(False, f"無效的狀態。有效值：{valid_statuses}")
        
        return ValidationResult(True, cleaned_value=status)
    
    @staticmethod
    def validate_rating(rating: Union[str, int]) -> ValidationResult:
        """驗證評分"""
        result = BaseValidator.validate_number(
            rating,
            min_value=1,
            max_value=5,
            field_name="評分"
        )
        
        return result
    
    @staticmethod
    def validate_close_reason(reason: str) -> ValidationResult:
        """驗證關閉原因"""
        if not reason:
            return ValidationResult(True, cleaned_value="")
        
        return BaseValidator.validate_text(
            reason,
            min_length=0,
            max_length=200,
            field_name="關閉原因"
        )
    
    @staticmethod
    def validate_feedback(feedback: str) -> ValidationResult:
        """驗證回饋"""
        if not feedback:
            return ValidationResult(True, cleaned_value="")
        
        return BaseValidator.validate_text(
            feedback,
            min_length=0,
            max_length=1000,
            field_name="回饋"
        )


class SettingsValidator:
    """設定驗證器"""
    
    @staticmethod
    def validate_max_tickets(value: Union[str, int]) -> ValidationResult:
        """驗證最大票券數"""
        return BaseValidator.validate_number(
            value,
            min_value=1,
            max_value=20,
            field_name="最大票券數"
        )
    
    @staticmethod
    def validate_auto_close_hours(value: Union[str, int]) -> ValidationResult:
        """驗證自動關閉時間"""
        return BaseValidator.validate_number(
            value,
            min_value=1,
            max_value=168,  # 一週
            field_name="自動關閉時間"
        )
    
    @staticmethod
    def validate_sla_minutes(value: Union[str, int]) -> ValidationResult:
        """驗證SLA時間"""
        return BaseValidator.validate_number(
            value,
            min_value=5,
            max_value=1440,  # 24小時
            field_name="SLA時間"
        )
    
    @staticmethod
    def validate_welcome_message(message: str) -> ValidationResult:
        """驗證歡迎訊息"""
        if not message:
            return ValidationResult(True, cleaned_value="")
        
        return BaseValidator.validate_text(
            message,
            min_length=0,
            max_length=2000,
            field_name="歡迎訊息"
        )
    
    @staticmethod
    def validate_category_channel(guild: discord.Guild, channel_input: str) -> ValidationResult:
        """驗證分類頻道"""
        from bot.utils.helpers import parse_channel_mention
        
        if not channel_input.strip():
            return ValidationResult(False, "頻道不能為空")
        
        channel_id = parse_channel_mention(channel_input)
        if not channel_id:
            return ValidationResult(False, "無效的頻道格式")
        
        channel = guild.get_channel(channel_id)
        if not channel:
            return ValidationResult(False, "找不到指定的頻道")
        
        if not isinstance(channel, discord.CategoryChannel):
            return ValidationResult(False, "必須是分類頻道")
        
        return ValidationResult(True, cleaned_value=channel_id)
    
    @staticmethod
    def validate_text_channel(guild: discord.Guild, channel_input: str) -> ValidationResult:
        """驗證文字頻道"""
        from bot.utils.helpers import parse_channel_mention
        
        if not channel_input.strip():
            return ValidationResult(False, "頻道不能為空")
        
        channel_id = parse_channel_mention(channel_input)
        if not channel_id:
            return ValidationResult(False, "無效的頻道格式")
        
        channel = guild.get_channel(channel_id)
        if not channel:
            return ValidationResult(False, "找不到指定的頻道")
        
        if not isinstance(channel, discord.TextChannel):
            return ValidationResult(False, "必須是文字頻道")
        
        # 檢查權限
        bot_permissions = channel.permissions_for(guild.me)
        if not bot_permissions.send_messages:
            return ValidationResult(False, f"機器人在{channel.mention}沒有發送訊息權限")
        
        return ValidationResult(True, cleaned_value=channel_id)
    
    @staticmethod
    def validate_support_roles(guild: discord.Guild, roles_input: str) -> ValidationResult:
        """驗證客服身分組"""
        from bot.utils.helpers import parse_role_mention
        
        if not roles_input.strip():
            return ValidationResult(False, "身分組不能為空")
        
        role_strings = [r.strip() for r in roles_input.split(',')]
        role_ids = []
        
        for role_string in role_strings:
            if not role_string:
                continue
            
            role_id = parse_role_mention(role_string)
            if not role_id:
                return ValidationResult(False, f"無效的身分組格式：{role_string}")
            
            role = guild.get_role(role_id)
            if not role:
                return ValidationResult(False, f"找不到身分組：{role_string}")
            
            if role.is_default():
                return ValidationResult(False, "不能使用@everyone身分組")
            
            role_ids.append(role_id)
        
        if not role_ids:
            return ValidationResult(False, "請至少指定一個有效的身分組")
        
        return ValidationResult(True, cleaned_value=role_ids)


class PermissionValidator:
    """權限驗證器"""
    
    @staticmethod
    def validate_user_permissions(user: discord.Member, 
                                required_permissions: List[str]) -> ValidationResult:
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
            perm_names = [p.replace('_', ' ').title() for p in missing_permissions]
            return ValidationResult(False, f"機器人缺少權限：{', '.join(perm_names)}")
        
        return ValidationResult(True)
    
    @staticmethod
    def validate_channel_permissions(user: discord.Member, 
                                   channel: discord.TextChannel,
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
            perm_names = [p.replace('_', ' ').title() for p in missing_permissions]
            return ValidationResult(
                False, 
                f"在{channel.mention}缺少權限：{', '.join(perm_names)}"
            )
        
        return ValidationResult(True)
    
    @staticmethod
    def validate_support_staff(user: discord.Member, 
                             support_roles: List[int]) -> ValidationResult:
        """驗證是否為客服人員"""
        if not user:
            return ValidationResult(False, "用戶不存在")
        
        # 管理員自動視為客服
        if user.guild_permissions.manage_guild:
            return ValidationResult(True)
        
        # 檢查客服身分組
        user_role_ids = {role.id for role in user.roles}
        if any(role_id in user_role_ids for role_id in support_roles):
            return ValidationResult(True)
        
        return ValidationResult(False, "不是客服人員")


class TicketCreationValidator:
    """票券建立驗證器"""
    
    @staticmethod
    async def validate_creation_request(user: discord.Member, ticket_type: str,
                                      priority: str, settings: Dict[str, Any],
                                      current_ticket_count: int) -> ValidationResult:
        """驗證票券建立請求"""
        # 驗證票券類型
        type_result = TicketValidator.validate_ticket_type(ticket_type)
        if not type_result.is_valid:
            return type_result
        
        # 驗證優先級
        priority_result = TicketValidator.validate_priority(priority)
        if not priority_result.is_valid:
            return priority_result
        
        # 檢查票券限制
        max_tickets = settings.get('max_tickets_per_user', 3)
        if current_ticket_count >= max_tickets:
            return ValidationResult(
                False,
                f"已達到票券上限（{max_tickets}張）！請先關閉現有票券。"
            )
        
        # 檢查必要設定
        if not settings.get('category_id'):
            return ValidationResult(False, "尚未設定票券分類頻道，請聯繫管理員")
        
        return ValidationResult(True)


class QuickValidator:
    """快速驗證器（用於裝飾器）"""
    
    @staticmethod
    def validate_ticket_operation(user: discord.Member, ticket: Dict[str, Any],
                                operation: str, settings: Dict[str, Any]) -> ValidationResult:
        """驗證票券操作"""
        if not ticket:
            return ValidationResult(False, "找不到票券")
        
        support_roles = settings.get('support_roles', [])
        
        # 檢查基本權限
        if operation in ['close', 'info']:
            # 票券創建者或客服可以操作
            if (str(user.id) == ticket['discord_id'] or 
                PermissionValidator.validate_support_staff(user, support_roles).is_valid):
                return ValidationResult(True)
            else:
                return ValidationResult(False, "沒有權限操作此票券")
        
        elif operation in ['assign', 'priority']:
            # 只有客服可以操作
            staff_result = PermissionValidator.validate_support_staff(user, support_roles)
            if not staff_result.is_valid:
                return ValidationResult(False, "只有客服人員可以執行此操作")
        
        elif operation == 'rate':
            # 只有票券創建者可以評分
            if str(user.id) != ticket['discord_id']:
                return ValidationResult(False, "只有票券創建者可以評分")
            
            if ticket['status'] != 'closed':
                return ValidationResult(False, "只能為已關閉的票券評分")
            
            if ticket.get('rating'):
                return ValidationResult(False, "此票券已經評分過了")
        
        return ValidationResult(True)


# ===== 驗證裝飾器 =====

def validate_permissions(*permissions):
    """權限驗證裝飾器"""
    def decorator(func):
        async def wrapper(interaction: discord.Interaction, *args, **kwargs):
            result = PermissionValidator.validate_user_permissions(
                interaction.user, 
                list(permissions)
            )
            
            if not result.is_valid:
                await interaction.response.send_message(
                    f"❌ {result.error_message}",
                    ephemeral=True
                )
                return
            
            return await func(interaction, *args, **kwargs)
        return wrapper
    return decorator


def validate_support_staff(func):
    """客服人員驗證裝飾器"""
    async def wrapper(interaction: discord.Interaction, *args, **kwargs):
        from bot.db.ticket_repository import TicketRepository
        
        repository = TicketRepository()
        settings = await repository.get_settings(interaction.guild.id)
        support_roles = settings.get('support_roles', [])
        
        result = PermissionValidator.validate_support_staff(
            interaction.user, 
            support_roles
        )
        
        if not result.is_valid:
            await interaction.response.send_message(
                "❌ 只有客服人員可以使用此功能。",
                ephemeral=True
            )
            return
        
        return await func(interaction, *args, **kwargs)
    return wrapper


def validate_admin(func):
    """管理員驗證裝飾器"""
    async def wrapper(interaction: discord.Interaction, *args, **kwargs):
        if not interaction.user.guild_permissions.manage_guild:
            await interaction.response.send_message(
                "❌ 只有管理員可以使用此功能。",
                ephemeral=True
            )
            return
        
        return await func(interaction, *args, **kwargs)
    return wrapper


def validate_ticket_channel(func):
    """票券頻道驗證裝飾器"""
    async def wrapper(interaction: discord.Interaction, *args, **kwargs):
        from bot.utils.helpers import is_ticket_channel
        
        if not is_ticket_channel(interaction.channel):
            await interaction.response.send_message(
                "❌ 此指令只能在票券頻道中使用。",
                ephemeral=True
            )
            return
        
        return await func(interaction, *args, **kwargs)
    return wrapper


# ===== 批次驗證 =====

class BatchValidator:
    """批次驗證器"""
    
    @staticmethod
    def validate_multiple(validators: List[ValidationResult]) -> ValidationResult:
        """驗證多個結果"""
        errors = []
        
        for result in validators:
            if not result.is_valid:
                errors.append(result.error_message)
        
        if errors:
            return ValidationResult(False, "; ".join(errors))
        
        return ValidationResult(True)
    
    @staticmethod
    async def validate_ticket_list(tickets: List[Dict[str, Any]]) -> Dict[int, ValidationResult]:
        """批次驗證票券列表"""
        results = {}
        
        for ticket in tickets:
            ticket_id = ticket.get('id')
            if not ticket_id:
                continue
            
            # 驗證基本資料
            required_fields = ['discord_id', 'username', 'type', 'status']
            missing_fields = [f for f in required_fields if f not in ticket or not ticket[f]]
            
            if missing_fields:
                results[ticket_id] = ValidationResult(
                    False, 
                    f"缺少欄位：{', '.join(missing_fields)}"
                )
            else:
                results[ticket_id] = ValidationResult(True)
        
        return results


# ===== 工廠函數 =====

def create_ticket_validator() -> TicketValidator:
    """建立票券驗證器"""
    return TicketValidator()


def create_settings_validator() -> SettingsValidator:
    """建立設定驗證器"""
    return SettingsValidator()


def create_permission_validator() -> PermissionValidator:
    """建立權限驗證器"""
    return PermissionValidator()


# ===== 輔助函數 =====

def validate_input(input_value: Any, validator_type: str, **kwargs) -> ValidationResult:
    """統一驗證入口"""
    try:
        if validator_type == 'text':
            return BaseValidator.validate_text(input_value, **kwargs)
        elif validator_type == 'number':
            return BaseValidator.validate_number(input_value, **kwargs)
        elif validator_type == 'discord_id':
            return BaseValidator.validate_discord_id(input_value)
        elif validator_type == 'ticket_type':
            return TicketValidator.validate_ticket_type(input_value)
        elif validator_type == 'priority':
            return TicketValidator.validate_priority(input_value)
        elif validator_type == 'rating':
            return TicketValidator.validate_rating(input_value)
        else:
            return ValidationResult(False, f"未知的驗證器類型：{validator_type}")
    
    except Exception as e:
        logger.error(f"驗證錯誤：{e}")
        return ValidationResult(False, "驗證過程發生錯誤")


def create_validation_embed(result: ValidationResult, title: str = "驗證結果") -> discord.Embed:
    """建立驗證結果嵌入"""
    if result.is_valid:
        return discord.Embed(
            title=f"✅ {title}",
            description="驗證通過",
            color=discord.Color.green()
        )
    else:
        return discord.Embed(
            title=f"❌ {title}",
            description=result.error_message,
            color=discord.Color.red()
        )


# ===== 常用驗證組合 =====

class CommonValidations:
    """常用驗證組合"""
    
    @staticmethod
    async def validate_ticket_creation(user: discord.Member, ticket_type: str,
                                     priority: str) -> ValidationResult:
        """票券建立完整驗證"""
        from bot.db.ticket_repository import TicketRepository
        
        try:
            repository = TicketRepository()
            settings = await repository.get_settings(user.guild.id)
            current_count = await repository.get_user_ticket_count(
                user.id, user.guild.id, "open"
            )
            
            return await TicketCreationValidator.validate_creation_request(
                user, ticket_type, priority, settings, current_count
            )
        
        except Exception as e:
            logger.error(f"票券建立驗證錯誤：{e}")
            return ValidationResult(False, "驗證過程發生錯誤")
    
    @staticmethod
    async def validate_settings_update(user: discord.Member, setting_name: str,
                                     value: str) -> ValidationResult:
        """設定更新完整驗證"""
        # 權限檢查
        perm_result = PermissionValidator.validate_user_permissions(
            user, ['manage_guild']
        )
        if not perm_result.is_valid:
            return perm_result
        
        # 設定值驗證
        if setting_name == 'max_tickets':
            return SettingsValidator.validate_max_tickets(value)
        elif setting_name == 'auto_close':
            return SettingsValidator.validate_auto_close_hours(value)
        elif setting_name == 'sla_response':
            return SettingsValidator.validate_sla_minutes(value)
        elif setting_name == 'welcome':
            return SettingsValidator.validate_welcome_message(value)
        elif setting_name == 'category':
            return SettingsValidator.validate_category_channel(user.guild, value)
        elif setting_name == 'support_roles':
            return SettingsValidator.validate_support_roles(user.guild, value)
        else:
            return ValidationResult(False, f"未知的設定項目：{setting_name}")


# ===== 匯出 =====
__all__ = [
    'ValidationResult',
    'BaseValidator',
    'TicketValidator', 
    'SettingsValidator',
    'PermissionValidator',
    'TicketCreationValidator',
    'QuickValidator',
    'BatchValidator',
    'CommonValidations',
    'validate_permissions',
    'validate_support_staff',
    'validate_admin',
    'validate_ticket_channel',
    'validate_input',
    'create_validation_embed'
]_names = [p.replace('_', ' ').title() for p in missing_permissions]
            return ValidationResult(False, f"缺少權限：{', '.join(perm_names)}")
        
        return ValidationResult(True)
    
    @staticmethod
    def validate_bot_permissions(guild: discord.Guild,
                               required_permissions: List[str]) -> ValidationResult:
        """驗證機器人權限"""
        if not guild or not guild.me:
            return ValidationResult(False, "機器人不在此伺服器中")
        
        bot_permissions = guild.me.guild_permissions
        missing_permissions = []
        
        for perm_name in required_permissions:
            if not hasattr(bot_permissions, perm_name):
                missing_permissions.append(perm_name)
                continue
            
            if not getattr(bot_permissions, perm_name):
                missing_permissions.append(perm_name)
        
        if missing_permissions:
            perm