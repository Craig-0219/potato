# bot/utils/helpers.py - 票券系統輔助工具函數
"""
票券系統輔助工具函數 - 簡化版
提供常用的格式化和工具函數
"""

import asyncio
import re
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple, Union

import discord

from potato_shared.logger import logger


def format_duration(duration: Union[timedelta, int]) -> str:
    """格式化時間長度"""
    if isinstance(duration, int):
        total_seconds = duration
    else:
        total_seconds = int(duration.total_seconds())

    if total_seconds < 60:
        return f"{total_seconds} 秒"

    minutes = total_seconds // 60
    if minutes < 60:
        return f"{minutes} 分鐘"

    hours = minutes // 60
    if hours < 24:
        remaining_minutes = minutes % 60
        if remaining_minutes > 0:
            return f"{hours} 小時 {remaining_minutes} 分鐘"
        return f"{hours} 小時"

    days = hours // 24
    remaining_hours = hours % 24
    if remaining_hours > 0:
        return f"{days} 天 {remaining_hours} 小時"
    return f"{days} 天"


def format_time_delta(delta: timedelta) -> str:
    """格式化時間差 - format_duration的別名

    Args:
        delta: 時間差對象

    Returns:
        str: 格式化的時間差字符串
    """
    return format_duration(delta)


def get_time_ago(timestamp: datetime) -> str:
    """取得相對時間"""
    if not timestamp:
        return "未知"

    now = datetime.now(timezone.utc)

    # 確保時間戳有時區資訊
    if timestamp.tzinfo is None:
        timestamp = timestamp.replace(tzinfo=timezone.utc)

    diff = now - timestamp
    total_seconds = int(diff.total_seconds())

    if total_seconds < 60:
        return "剛剛"

    minutes = total_seconds // 60
    if minutes < 60:
        return f"{minutes} 分鐘前"

    hours = minutes // 60
    if hours < 24:
        return f"{hours} 小時前"

    days = hours // 24
    if days < 30:
        return f"{days} 天前"

    months = days // 30
    if months < 12:
        return f"{months} 個月前"

    years = months // 12
    return f"{years} 年前"


def truncate_text(text: str, max_length: int, suffix: str = "...") -> str:
    """截斷文字"""
    if not text:
        return ""

    if len(text) <= max_length:
        return text

    return text[: max_length - len(suffix)] + suffix


def escape_markdown(text: str) -> str:
    """轉義 Markdown 特殊字符"""
    if not text:
        return ""

    # Discord Markdown 特殊字符
    markdown_chars = ["*", "_", "`", "~", "\\", ">", "|"]

    for char in markdown_chars:
        text = text.replace(char, f"\\{char}")

    return text


def sanitize_channel_name(name: str) -> str:
    """清理頻道名稱"""
    if not name:
        return "ticket"

    # 轉換為小寫
    name = name.lower()

    # 移除非法字符，只保留字母、數字、連字符和底線
    name = re.sub(r"[^a-z0-9\-_]", "-", name)

    # 移除連續的連字符
    name = re.sub(r"-+", "-", name)

    # 移除開頭和結尾的連字符
    name = name.strip("-")

    # 限制長度
    name = name[:50]

    return name or "ticket"


def parse_user_mention(mention: str) -> Optional[int]:
    """解析用戶提及"""
    if not mention:
        return None

    # 直接用戶ID
    if mention.isdigit():
        return int(mention)

    # 用戶提及格式 <@123456> 或 <@!123456>
    match = re.match(r"<@!?(\d+)>", mention)
    if match:
        return int(match.group(1))

    return None


def parse_channel_mention(mention: str) -> Optional[int]:
    """解析頻道提及"""
    if not mention:
        return None

    # 直接頻道ID
    if mention.isdigit():
        return int(mention)

    # 頻道提及格式 <#123456>
    match = re.match(r"<#(\d+)>", mention)
    if match:
        return int(match.group(1))

    return None


def parse_role_mention(mention: str) -> Optional[int]:
    """解析身分組提及"""
    if not mention:
        return None

    # 直接身分組ID
    if mention.isdigit():
        return int(mention)

    # 身分組提及格式 <@&123456>
    match = re.match(r"<@&(\d+)>", mention)
    if match:
        return int(match.group(1))

    return None


def format_user_list(user_ids: List[int], max_display: int = 5) -> str:
    """格式化用戶列表"""
    if not user_ids:
        return "無"

    mentions = [f"<@{user_id}>" for user_id in user_ids[:max_display]]

    if len(user_ids) > max_display:
        mentions.append(f"...還有 {len(user_ids) - max_display} 人")

    return ", ".join(mentions)


def format_channel_list(channel_ids: List[int], max_display: int = 3) -> str:
    """格式化頻道列表"""
    if not channel_ids:
        return "無"

    mentions = [f"<#{channel_id}>" for channel_id in channel_ids[:max_display]]

    if len(channel_ids) > max_display:
        mentions.append(f"...還有 {len(channel_ids) - max_display} 個")

    return ", ".join(mentions)


def format_role_list(role_ids: List[int], max_display: int = 3) -> str:
    """格式化身分組列表"""
    if not role_ids:
        return "無"

    mentions = [f"<@&{role_id}>" for role_id in role_ids[:max_display]]

    if len(role_ids) > max_display:
        mentions.append(f"...還有 {len(role_ids) - max_display} 個")

    return ", ".join(mentions)


def create_progress_bar(
    current: int,
    total: int,
    length: int = 10,
    filled_char: str = "█",
    empty_char: str = "░",
) -> str:
    """建立進度條"""
    if total <= 0:
        return empty_char * length

    filled_length = int((current / total) * length)
    filled_length = max(0, min(length, filled_length))

    return filled_char * filled_length + empty_char * (length - filled_length)


def format_percentage(current: int, total: int, decimal_places: int = 1) -> str:
    """格式化百分比"""
    if total <= 0:
        return "0%"

    percentage = (current / total) * 100
    return f"{percentage:.{decimal_places}f}%"


def validate_discord_id(discord_id: Union[str, int]) -> bool:
    """驗證 Discord ID 格式"""
    try:
        id_int = int(discord_id)
        # Discord ID 應該是18位數字
        return 100000000000000000 <= id_int <= 999999999999999999
    except (ValueError, TypeError):
        return False


def format_ticket_id(ticket_id: int, padding: int = 4) -> str:
    """格式化票券ID"""
    return f"#{ticket_id:0{padding}d}"


def parse_time_string(time_str: str) -> Optional[int]:
    """解析時間字符串，返回分鐘數"""
    if not time_str:
        return None

    time_str = time_str.lower().strip()

    # 匹配數字和單位
    match = re.match(r"(\d+)\s*(m|min|mins|minutes?|h|hr|hrs|hours?|d|day|days?)", time_str)

    if not match:
        # 嘗試只匹配數字（默認分鐘）
        if time_str.isdigit():
            return int(time_str)
        return None

    value = int(match.group(1))
    unit = match.group(2)

    # 轉換為分鐘
    if unit in ("m", "min", "mins", "minute", "minutes"):
        return value
    elif unit in ("h", "hr", "hrs", "hour", "hours"):
        return value * 60
    elif unit in ("d", "day", "days"):
        return value * 24 * 60

    return None


def format_time_remaining(end_time: datetime) -> str:
    """格式化剩餘時間"""
    now = datetime.now(timezone.utc)

    # 確保時間有時區資訊
    if end_time.tzinfo is None:
        end_time = end_time.replace(tzinfo=timezone.utc)

    diff = end_time - now

    if diff.total_seconds() <= 0:
        return "已結束"

    return format_duration(diff)


def create_embed_field_value(items: Dict[str, Any], max_length: int = 1024) -> str:
    """建立嵌入欄位值"""
    lines = []
    current_length = 0

    for key, value in items.items():
        line = f"**{key}：** {value}\n"

        if current_length + len(line) > max_length:
            if current_length == 0:  # 單行就超過限制
                line = truncate_text(line, max_length - 3) + "...\n"
                lines.append(line)
            else:
                lines.append("...")
            break

        lines.append(line)
        current_length += len(line)

    return "".join(lines).rstrip()


def is_ticket_channel(channel: discord.TextChannel) -> bool:
    """檢查是否為票券頻道"""
    if not channel or not hasattr(channel, "name"):
        return False

    return channel.name.startswith("ticket-")


def extract_ticket_id_from_channel(
    channel: discord.TextChannel,
) -> Optional[int]:
    """從頻道名稱提取票券ID"""
    if not is_ticket_channel(channel):
        return None

    # 嘗試從頻道名稱提取ID
    match = re.search(r"ticket-(\d+)", channel.name)
    if match:
        return int(match.group(1))

    return None


def check_permissions(
    member: discord.Member,
    channel: discord.TextChannel,
    permissions: List[str],
) -> Dict[str, bool]:
    """檢查用戶權限"""
    if not member or not channel:
        return {perm: False for perm in permissions}

    member_permissions = channel.permissions_for(member)
    result = {}

    for perm in permissions:
        result[perm] = getattr(member_permissions, perm, False)

    return result


def format_permission_list(permissions: Dict[str, bool]) -> str:
    """格式化權限列表"""
    lines = []

    for perm, has_perm in permissions.items():
        emoji = "✅" if has_perm else "❌"
        perm_name = perm.replace("_", " ").title()
        lines.append(f"{emoji} {perm_name}")

    return "\n".join(lines)


def clean_content(content: str, max_length: int = 2000) -> str:
    """清理內容"""
    if not content:
        return ""

    # 移除多餘的空白字符
    content = re.sub(r"\s+", " ", content.strip())

    # 限制長度
    if len(content) > max_length:
        content = content[: max_length - 3] + "..."

    return content


def format_file_size(size_bytes: int) -> str:
    """格式化檔案大小"""
    if size_bytes == 0:
        return "0 B"

    units = ["B", "KB", "MB", "GB"]
    unit_index = 0
    size = float(size_bytes)

    while size >= 1024 and unit_index < len(units) - 1:
        size /= 1024
        unit_index += 1

    if unit_index == 0:
        return f"{int(size)} {units[unit_index]}"
    else:
        return f"{size:.1f} {units[unit_index]}"


def create_simple_embed(
    title: str, description: str = None, color: discord.Color = None
) -> discord.Embed:
    """建立簡單的嵌入"""
    embed = discord.Embed(title=title, color=color or discord.Color.blue())

    if description:
        embed.description = description

    return embed


def create_error_embed(message: str) -> discord.Embed:
    """建立錯誤嵌入"""
    return discord.Embed(title="❌ 錯誤", description=message, color=discord.Color.red())


def create_success_embed(message: str) -> discord.Embed:
    """建立成功嵌入"""
    return discord.Embed(title="✅ 成功", description=message, color=discord.Color.green())


def create_warning_embed(message: str) -> discord.Embed:
    """建立警告嵌入"""
    return discord.Embed(title="⚠️ 警告", description=message, color=discord.Color.orange())


def create_info_embed(message: str) -> discord.Embed:
    """建立資訊嵌入"""
    return discord.Embed(title="ℹ️ 資訊", description=message, color=discord.Color.blue())


async def safe_send_message(
    channel: discord.TextChannel,
    content: str = None,
    embed: discord.Embed = None,
    **kwargs,
) -> Optional[discord.Message]:
    """安全發送訊息"""
    try:
        return await channel.send(content=content, embed=embed, **kwargs)
    except discord.Forbidden:
        logger.warning(f"沒有權限在頻道 {channel.id} 發送訊息")
    except discord.HTTPException as e:
        logger.error(f"發送訊息HTTP錯誤：{e}")
    except Exception as e:
        logger.error(f"發送訊息未知錯誤：{e}")

    return None


async def safe_edit_message(
    message: discord.Message,
    content: str = None,
    embed: discord.Embed = None,
    **kwargs,
) -> bool:
    """安全編輯訊息"""
    try:
        await message.edit(content=content, embed=embed, **kwargs)
        return True
    except discord.NotFound:
        logger.warning(f"訊息 {message.id} 不存在")
    except discord.Forbidden:
        logger.warning(f"沒有權限編輯訊息 {message.id}")
    except discord.HTTPException as e:
        logger.error(f"編輯訊息HTTP錯誤：{e}")
    except Exception as e:
        logger.error(f"編輯訊息未知錯誤：{e}")

    return False


async def safe_delete_message(message: discord.Message, delay: float = 0) -> bool:
    """安全刪除訊息"""
    try:
        if delay > 0:
            await asyncio.sleep(delay)

        await message.delete()
        return True
    except discord.NotFound:
        logger.warning(f"訊息 {message.id} 已被刪除")
    except discord.Forbidden:
        logger.warning(f"沒有權限刪除訊息 {message.id}")
    except discord.HTTPException as e:
        logger.error(f"刪除訊息HTTP錯誤：{e}")
    except Exception as e:
        logger.error(f"刪除訊息未知錯誤：{e}")

    return False


def batch_process(items: List[Any], batch_size: int = 50):
    """批次處理項目"""
    for i in range(0, len(items), batch_size):
        yield items[i : i + batch_size]


def get_guild_icon_url(guild: discord.Guild) -> Optional[str]:
    """取得伺服器圖標URL"""
    if guild.icon:
        return guild.icon.url
    return None


def get_user_avatar_url(user: discord.User) -> str:
    """取得用戶頭像URL"""
    if user.avatar:
        return user.avatar.url
    return user.default_avatar.url


def format_timestamp(timestamp: datetime, style: str = "F") -> str:
    """格式化時間戳為Discord時間戳"""
    if timestamp.tzinfo is None:
        timestamp = timestamp.replace(tzinfo=timezone.utc)

    unix_timestamp = int(timestamp.timestamp())
    return f"<t:{unix_timestamp}:{style}>"


def get_relative_timestamp(timestamp: datetime) -> str:
    """取得相對時間戳"""
    return format_timestamp(timestamp, "R")


def get_datetime_timestamp(timestamp: datetime) -> str:
    """取得完整日期時間戳"""
    return format_timestamp(timestamp, "F")


# ===== 資料驗證工具 =====


def validate_ticket_data(data: Dict[str, Any]) -> Tuple[bool, str]:
    """驗證票券資料"""
    required_fields = [
        "discord_id",
        "username",
        "type",
        "channel_id",
        "guild_id",
    ]

    for field in required_fields:
        if field not in data or not data[field]:
            return False, f"缺少必要欄位：{field}"

    # 驗證ID格式
    id_fields = ["discord_id", "channel_id", "guild_id"]
    for field in id_fields:
        if not validate_discord_id(data[field]):
            return False, f"無效的{field}格式"

    return True, ""


def validate_settings_data(data: Dict[str, Any]) -> Tuple[bool, str]:
    """驗證設定資料"""
    # 數值範圍驗證
    numeric_limits = {
        "max_tickets_per_user": (1, 20),
        "auto_close_hours": (1, 168),
        "sla_response_minutes": (5, 1440),
    }

    for field, (min_val, max_val) in numeric_limits.items():
        if field in data:
            try:
                value = int(data[field])
                if not (min_val <= value <= max_val):
                    return False, f"{field}必須在{min_val}-{max_val}之間"
            except (ValueError, TypeError):
                return False, f"{field}必須是數字"

    return True, ""


# ===== 快取工具 =====


class SimpleCache:
    """簡單的記憶體快取"""

    def __init__(self, timeout: int = 300):
        self.cache = {}
        self.timeout = timeout
        self.timestamps = {}

    def get(self, key: str) -> Any:
        """取得快取值"""
        if key not in self.cache:
            return None

        # 檢查是否過期
        if self._is_expired(key):
            self.delete(key)
            return None

        return self.cache[key]

    def set(self, key: str, value: Any) -> None:
        """設定快取值"""
        self.cache[key] = value
        self.timestamps[key] = datetime.now(timezone.utc)

    def delete(self, key: str) -> None:
        """刪除快取值"""
        self.cache.pop(key, None)
        self.timestamps.pop(key, None)

    def clear(self) -> None:
        """清空快取"""
        self.cache.clear()
        self.timestamps.clear()

    def _is_expired(self, key: str) -> bool:
        """檢查是否過期"""
        if key not in self.timestamps:
            return True

        elapsed = datetime.now(timezone.utc) - self.timestamps[key]
        return elapsed.total_seconds() > self.timeout

    def cleanup(self) -> int:
        """清理過期項目"""
        expired_keys = [key for key in self.cache.keys() if self._is_expired(key)]

        for key in expired_keys:
            self.delete(key)

        return len(expired_keys)


# ===== 全域快取實例 =====
settings_cache = SimpleCache(timeout=600)  # 10分鐘
statistics_cache = SimpleCache(timeout=300)  # 5分鐘
