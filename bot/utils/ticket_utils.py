# bot/utils/ticket_utils.py - 票券系統工具函數完善版

import asyncio
import json
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple, Union

import discord

from bot.utils.ticket_constants import (
    TicketConstants,
    create_progress_indicator,
    format_duration_chinese,
    get_priority_color,
    get_priority_emoji,
    get_status_emoji,
    get_time_ago_chinese,
    truncate_text,
)

# ===== 權限檢查器 =====


class TicketPermissionChecker:
    """票券權限檢查器"""

    @staticmethod
    def is_admin(user: discord.Member) -> bool:
        """檢查是否為管理員"""
        if not user:
            return False
        return user.guild_permissions.manage_guild or user.guild_permissions.administrator

    @staticmethod
    def is_support_staff(user: discord.Member, support_roles: List[int]) -> bool:
        """檢查是否為客服人員"""
        if not user:
            return False

        # 管理員自動視為客服
        if TicketPermissionChecker.is_admin(user):
            return True

        # 檢查客服身分組
        user_role_ids = {role.id for role in user.roles}
        return any(role_id in user_role_ids for role_id in support_roles)

    @staticmethod
    def can_manage_ticket(
        user: discord.Member, ticket_info: Dict[str, Any], support_roles: List[int]
    ) -> bool:
        """檢查是否可以管理票券"""
        if not user or not ticket_info:
            return False

        # 票券創建者可以管理
        if str(user.id) == ticket_info.get("discord_id"):
            return True

        # 客服人員可以管理
        return TicketPermissionChecker.is_support_staff(user, support_roles)

    @staticmethod
    def can_close_ticket(
        user: discord.Member, ticket_info: Dict[str, Any], support_roles: List[int]
    ) -> bool:
        """檢查是否可以關閉票券"""
        return TicketPermissionChecker.can_manage_ticket(user, ticket_info, support_roles)

    @staticmethod
    def can_rate_ticket(user: discord.Member, ticket_info: Dict[str, Any]) -> bool:
        """檢查是否可以評分票券"""
        if not user or not ticket_info:
            return False

        # 只有票券創建者可以評分
        if str(user.id) != ticket_info.get("discord_id"):
            return False

        # 只能為已關閉的票券評分
        if ticket_info.get("status") != "closed":
            return False

        # 不能重複評分
        if ticket_info.get("rating"):
            return False

        return True

    @staticmethod
    def can_assign_ticket(user: discord.Member, support_roles: List[int]) -> bool:
        """檢查是否可以指派票券"""
        return TicketPermissionChecker.is_support_staff(user, support_roles)

    @staticmethod
    def can_view_ticket(
        user: discord.Member, ticket_info: Dict[str, Any], support_roles: List[int]
    ) -> bool:
        """檢查是否可以查看票券"""
        if not user or not ticket_info:
            return False

        # 票券創建者可以查看
        if str(user.id) == ticket_info.get("discord_id"):
            return True

        # 客服人員可以查看所有票券
        return TicketPermissionChecker.is_support_staff(user, support_roles)

    @staticmethod
    def get_permission_level(user: discord.Member, support_roles: List[int]) -> str:
        """取得權限等級"""
        if not user:
            return "none"

        if user.guild_permissions.administrator:
            return "admin"
        elif user.guild_permissions.manage_guild:
            return "manager"
        elif TicketPermissionChecker.is_support_staff(user, support_roles):
            return "support"
        else:
            return "user"


# ===== 頻道工具 =====


def is_ticket_channel(channel: discord.TextChannel) -> bool:
    """檢查是否為票券頻道"""
    if not channel or not hasattr(channel, "name"):
        return False
    return channel.name.startswith("ticket-")


def parse_ticket_id_from_channel(channel: discord.TextChannel) -> Optional[int]:
    """從頻道名稱解析票券ID"""
    if not is_ticket_channel(channel):
        return None

    try:
        # 從 ticket-0001 格式解析
        ticket_code = channel.name.replace("ticket-", "")
        return int(ticket_code)
    except (ValueError, AttributeError):
        return None


def generate_ticket_channel_name(ticket_id: int, username: str = None) -> str:
    """生成票券頻道名稱"""
    base_name = f"ticket-{ticket_id:04d}"

    if username:
        # 清理用戶名，只保留安全字符
        clean_username = re.sub(r"[^a-zA-Z0-9\u4e00-\u9fff]", "", username)
        if clean_username:
            base_name += f"-{clean_username[:10]}"  # 限制長度

    return base_name.lower()


async def create_ticket_channel_overwrites(
    guild: discord.Guild, user: discord.Member, support_roles: List[int]
) -> Dict[Union[discord.Role, discord.Member], discord.PermissionOverwrite]:
    """建立票券頻道權限覆寫"""
    overwrites = {
        guild.default_role: discord.PermissionOverwrite(read_messages=False),
        user: discord.PermissionOverwrite(
            read_messages=True,
            send_messages=True,
            attach_files=True,
            embed_links=True,
            read_message_history=True,
        ),
        guild.me: discord.PermissionOverwrite(
            read_messages=True,
            send_messages=True,
            manage_messages=True,
            embed_links=True,
            attach_files=True,
            read_message_history=True,
        ),
    }

    # 添加客服身分組權限
    for role_id in support_roles:
        role = guild.get_role(role_id)
        if role:
            overwrites[role] = discord.PermissionOverwrite(
                read_messages=True,
                send_messages=True,
                manage_messages=True,
                embed_links=True,
                attach_files=True,
                read_message_history=True,
            )

    return overwrites


def parse_channel_mention(
    channel_input: str, guild: discord.Guild
) -> Optional[discord.abc.GuildChannel]:
    """解析頻道提及"""
    if not channel_input or not guild:
        return None

    channel_input = channel_input.strip()

    # 直接頻道ID
    if channel_input.isdigit():
        return guild.get_channel(int(channel_input))

    # 頻道提及格式 <#123456>
    mention_match = re.match(r"<#(\d+)>", channel_input)
    if mention_match:
        channel_id = int(mention_match.group(1))
        return guild.get_channel(channel_id)

    # 頻道名稱搜尋
    for channel in guild.channels:
        if channel.name.lower() == channel_input.lower():
            return channel

    return None


def parse_role_mention(role_input: str, guild: discord.Guild) -> Optional[discord.Role]:
    """解析身分組提及"""
    if not role_input or not guild:
        return None

    role_input = role_input.strip()

    # 直接身分組ID
    if role_input.isdigit():
        return guild.get_role(int(role_input))

    # 身分組提及格式 <@&123456>
    mention_match = re.match(r"<@&(\d+)>", role_input)
    if mention_match:
        role_id = int(mention_match.group(1))
        return guild.get_role(role_id)

    # 身分組名稱搜尋
    for role in guild.roles:
        if role.name.lower() == role_input.lower():
            return role

    return None


# ===== Embed 建構器 =====


def build_ticket_embed(ticket_info: Dict[str, Any], include_stats: bool = False) -> discord.Embed:
    """建立票券資訊嵌入"""
    priority = ticket_info.get("priority", "medium")
    status = ticket_info.get("status", "open")

    priority_emoji = get_priority_emoji(priority)
    status_emoji = get_status_emoji(status)

    embed = discord.Embed(
        title=f"🎫 票券 #{ticket_info['ticket_id']:04d}", color=get_priority_color(priority)
    )

    # 基本資訊
    embed.add_field(
        name="📋 基本資訊",
        value=f"**類型：** {ticket_info['type']}\n"
        f"**狀態：** {status_emoji} {status.upper()}\n"
        f"**優先級：** {priority_emoji} {priority.upper()}",
        inline=True,
    )

    # 用戶資訊
    embed.add_field(
        name="👤 用戶資訊",
        value=f"**開票者：** <@{ticket_info['discord_id']}>\n"
        f"**用戶名：** {ticket_info['username']}",
        inline=True,
    )

    # 時間資訊
    created_time = get_time_ago_chinese(ticket_info["created_at"])
    time_info = f"**建立時間：** {created_time}"

    if ticket_info.get("closed_at"):
        closed_time = get_time_ago_chinese(ticket_info["closed_at"])
        duration = ticket_info["closed_at"] - ticket_info["created_at"]
        time_info += f"\n**關閉時間：** {closed_time}"
        time_info += f"\n**持續時間：** {format_duration_chinese(int(duration.total_seconds()))}"

    embed.add_field(name="⏰ 時間資訊", value=time_info, inline=False)

    # 指派資訊
    if ticket_info.get("assigned_to"):
        embed.add_field(
            name="👥 指派資訊", value=f"**負責客服：** <@{ticket_info['assigned_to']}>", inline=True
        )

    # 評分資訊
    if ticket_info.get("rating"):
        stars = TicketConstants.RATING_EMOJIS.get(ticket_info["rating"], "⭐")
        rating_text = f"**評分：** {stars} ({ticket_info['rating']}/5)"

        if ticket_info.get("rating_feedback"):
            feedback = truncate_text(ticket_info["rating_feedback"], 100)
            rating_text += f"\n**回饋：** {feedback}"

        embed.add_field(name="⭐ 評分資訊", value=rating_text, inline=True)

    # 標籤資訊
    if ticket_info.get("tags"):
        try:
            tags = (
                json.loads(ticket_info["tags"])
                if isinstance(ticket_info["tags"], str)
                else ticket_info["tags"]
            )
            if tags:
                tags_text = " ".join([f"`{tag}`" for tag in tags[:10]])  # 限制顯示數量
                embed.add_field(name="🏷️ 標籤", value=tags_text, inline=False)
        except:
            pass

    # 統計資訊（可選）
    if include_stats:
        embed.add_field(
            name="📊 統計資訊",
            value=f"**最後活動：** {get_time_ago_chinese(ticket_info.get('last_activity', ticket_info['created_at']))}",
            inline=True,
        )

    return embed


def build_stats_embed(
    stats: Dict[str, Any], title: str = "📊 統計資訊", color: discord.Color = discord.Color.blue()
) -> discord.Embed:
    """建立統計資訊嵌入"""
    embed = discord.Embed(title=title, color=color)

    # 基本統計
    total_count = stats.get("total_count", 0)
    open_count = stats.get("open_count", 0)
    closed_count = stats.get("closed_count", 0)

    embed.add_field(
        name="📋 票券統計",
        value=f"**總數：** {total_count}\n"
        f"**開啟中：** {open_count}\n"
        f"**已關閉：** {closed_count}\n"
        f"**今日新增：** {stats.get('today_count', 0)}",
        inline=True,
    )

    # 評分統計
    avg_rating = stats.get("avg_rating", 0)
    total_ratings = stats.get("total_ratings", 0)
    five_star_count = stats.get("five_star_count", 0)

    if total_ratings > 0:
        five_star_rate = (five_star_count / total_ratings) * 100
        embed.add_field(
            name="⭐ 評分統計",
            value=f"**平均評分：** {avg_rating:.1f}/5\n"
            f"**評分總數：** {total_ratings}\n"
            f"**五星評價：** {five_star_count} ({five_star_rate:.1f}%)",
            inline=True,
        )

    # 進度指示器
    if total_count > 0:
        close_rate = (closed_count / total_count) * 100
        progress_bar = create_progress_indicator(closed_count, total_count, 10)
        embed.add_field(
            name="📈 完成進度", value=f"```{progress_bar}``` {close_rate:.1f}%", inline=False
        )

    return embed


def build_sla_embed(sla_stats: Dict[str, Any], guild: discord.Guild) -> discord.Embed:
    """建立SLA統計嵌入"""
    embed = discord.Embed(title="📈 SLA 監控面板", color=discord.Color.blue())

    # SLA 總體統計
    total_tickets = sla_stats.get("total_tickets", 0)
    sla_rate = sla_stats.get("sla_rate", 0)
    avg_response_time = sla_stats.get("avg_response_time", 0)

    # SLA 指示器顏色
    if sla_rate >= 90:
        sla_color = "🟢"
    elif sla_rate >= 75:
        sla_color = "🟡"
    else:
        sla_color = "🔴"

    embed.add_field(
        name="📊 本週SLA統計",
        value=f"**總票券：** {total_tickets}\n"
        f"**已回應：** {sla_stats.get('responded_tickets', 0)}\n"
        f"**達標率：** {sla_color} {sla_rate:.1f}%\n"
        f"**平均回應：** {avg_response_time:.1f} 分鐘",
        inline=True,
    )

    # 當前超時統計
    overdue_high = sla_stats.get("overdue_high", 0)
    overdue_medium = sla_stats.get("overdue_medium", 0)
    overdue_low = sla_stats.get("overdue_low", 0)

    embed.add_field(
        name="⚠️ 當前超時",
        value=f"🔴 **高優先級：** {overdue_high}\n"
        f"🟡 **中優先級：** {overdue_medium}\n"
        f"🟢 **低優先級：** {overdue_low}",
        inline=True,
    )

    # SLA 進度條
    sla_progress = create_progress_indicator(int(sla_rate), 100, 15)
    embed.add_field(
        name="📈 SLA 達標率", value=f"```{sla_progress}``` **{sla_rate:.1f}%**", inline=False
    )

    embed.set_footer(
        text=f"統計期間：最近7天 | 更新時間：{datetime.now(timezone.utc).strftime('%H:%M:%S')} UTC"
    )

    return embed


def build_staff_performance_embed(
    staff_stats: Dict[str, Any], guild: discord.Guild, period: str = "week"
) -> discord.Embed:
    """建立客服表現嵌入"""
    period_names = {"today": "今日", "week": "本週", "month": "本月"}
    period_name = period_names.get(period, period)

    embed = discord.Embed(title=f"👥 客服團隊表現 - {period_name}", color=discord.Color.green())

    if not staff_stats:
        embed.description = "📊 此期間尚無客服活動記錄。"
        return embed

    # 排序客服（按處理票券數）
    sorted_staff = sorted(
        staff_stats.items(), key=lambda x: x[1].get("handled_tickets", 0), reverse=True
    )

    # 顯示前10名客服
    for i, (staff_id, stats) in enumerate(sorted_staff[:10]):
        try:
            member = guild.get_member(int(staff_id))
            if not member:
                continue

            # 計算績效指標
            handled_tickets = stats.get("handled_tickets", 0)
            avg_rating = stats.get("avg_rating", 0)
            sla_rate = stats.get("sla_rate", 0)

            # 績效等級
            if sla_rate >= 90 and avg_rating >= 4.5:
                performance_emoji = "🏆"
            elif sla_rate >= 80 and avg_rating >= 4.0:
                performance_emoji = "🥇"
            elif sla_rate >= 70 and avg_rating >= 3.5:
                performance_emoji = "🥈"
            else:
                performance_emoji = "📊"

            embed.add_field(
                name=f"{performance_emoji} {member.display_name}",
                value=f"**處理：** {handled_tickets} 張\n"
                f"**評分：** {avg_rating:.1f}⭐\n"
                f"**SLA：** {sla_rate:.1f}%",
                inline=True,
            )

        except (ValueError, AttributeError):
            continue

    return embed


def build_user_tickets_embed(
    tickets: List[Dict[str, Any]], user: discord.Member, page: int = 1, total_pages: int = 1
) -> discord.Embed:
    """建立用戶票券列表嵌入"""
    embed = discord.Embed(title=f"🎫 {user.display_name} 的票券", color=discord.Color.blue())

    if not tickets:
        embed.description = "📭 沒有找到票券記錄。"
        return embed

    for ticket in tickets:
        status_emoji = get_status_emoji(ticket["status"])
        priority_emoji = get_priority_emoji(ticket.get("priority", "medium"))

        # 建立狀態指示
        status_text = f"{status_emoji} {ticket['status'].upper()}"
        if ticket["status"] == "open":
            # 計算開啟時間
            created_at = ticket["created_at"]
            # 確保時間戳有時區資訊
            if created_at.tzinfo is None:
                created_at = created_at.replace(tzinfo=timezone.utc)
            open_duration = datetime.now(timezone.utc) - created_at
            status_text += f" ({format_duration_chinese(int(open_duration.total_seconds()))})"

        field_value = f"**狀態：** {status_text}\n"
        field_value += f"**優先級：** {priority_emoji} {ticket.get('priority', 'medium').upper()}\n"
        field_value += f"**建立：** {get_time_ago_chinese(ticket['created_at'])}"

        # 添加評分資訊
        if ticket.get("rating"):
            stars = TicketConstants.RATING_EMOJIS.get(ticket["rating"], "⭐")
            field_value += f"\n**評分：** {stars}"

        # 添加指派資訊
        if ticket.get("assigned_to"):
            field_value += f"\n**客服：** <@{ticket['assigned_to']}>"

        embed.add_field(
            name=f"#{ticket['ticket_id']:04d} - {ticket['type']}", value=field_value, inline=True
        )

    # 分頁資訊
    if total_pages > 1:
        embed.set_footer(text=f"頁面 {page}/{total_pages}")

    return embed


# ===== 自動回覆系統 =====


def check_auto_reply_keywords(message_content: str, keywords: List[str]) -> bool:
    """檢查訊息是否匹配自動回覆關鍵字"""
    if not message_content or not keywords:
        return False

    content_lower = message_content.lower()

    # 檢查是否包含任一關鍵字
    for keyword in keywords:
        if keyword.lower() in content_lower:
            return True

    return False


def process_auto_reply_message(
    message_content: str, reply_template: str, user: discord.Member = None
) -> str:
    """處理自動回覆訊息模板"""
    if not reply_template:
        return ""

    # 替換基本變數
    processed_message = reply_template

    if user:
        processed_message = processed_message.replace("{user}", user.display_name)
        processed_message = processed_message.replace("{mention}", user.mention)

    # 替換時間變數
    now = datetime.now(timezone.utc)
    processed_message = processed_message.replace("{time}", now.strftime("%H:%M"))
    processed_message = processed_message.replace("{date}", now.strftime("%Y-%m-%d"))

    return processed_message


async def get_best_auto_reply(
    message_content: str, rules: List[Dict[str, Any]], user: discord.Member = None
) -> Optional[str]:
    """取得最佳自動回覆"""
    if not message_content or not rules:
        return None

    matching_rules = []

    # 找出所有匹配的規則
    for rule in rules:
        if not rule.get("enabled", True):
            continue

        keywords = rule.get("keywords", [])
        if check_auto_reply_keywords(message_content, keywords):
            matching_rules.append(rule)

    if not matching_rules:
        return None

    # 按優先級排序，取最高優先級的規則
    matching_rules.sort(key=lambda x: x.get("priority", 0), reverse=True)
    best_rule = matching_rules[0]

    # 處理回覆模板
    reply = process_auto_reply_message(best_rule.get("reply", ""), user)
    return reply


# ===== 格式化工具 =====


def format_settings_value(field_name: str, value: Any, guild: discord.Guild = None) -> str:
    """格式化設定值顯示"""
    if value is None:
        return "未設定"

    if field_name in ["category_id", "log_channel_id", "sla_alert_channel_id"]:
        if guild:
            channel = guild.get_channel(value)
            return channel.mention if channel else f"<#{value}> (已刪除)"
        return f"<#{value}>"

    elif field_name == "support_roles":
        if not value:
            return "未設定"
        if guild:
            role_mentions = []
            for role_id in value:
                role = guild.get_role(role_id)
                if role:
                    role_mentions.append(role.mention)
                else:
                    role_mentions.append(f"<@&{role_id}> (已刪除)")
            return ", ".join(role_mentions) if role_mentions else "未設定"
        return f"共 {len(value)} 個身分組"

    elif field_name == "auto_assign_enabled":
        return "啟用" if value else "停用"

    elif field_name in ["max_tickets_per_user", "auto_close_hours", "sla_response_minutes"]:
        units = {
            "max_tickets_per_user": "張",
            "auto_close_hours": "小時",
            "sla_response_minutes": "分鐘",
        }
        return f"{value} {units.get(field_name, '')}"

    elif field_name == "welcome_message":
        return truncate_text(str(value), 100) if value else "使用預設訊息"

    else:
        return str(value)


def format_ticket_status_summary(tickets: List[Dict[str, Any]]) -> Dict[str, Any]:
    """格式化票券狀態摘要"""
    summary = {
        "total": len(tickets),
        "open": 0,
        "closed": 0,
        "archived": 0,
        "by_priority": {"high": 0, "medium": 0, "low": 0},
        "with_rating": 0,
        "avg_rating": 0,
        "overdue": 0,
    }

    total_rating = 0
    rated_count = 0

    for ticket in tickets:
        status = ticket.get("status", "open")
        priority = ticket.get("priority", "medium")
        rating = ticket.get("rating")

        # 統計狀態
        if status in summary:
            summary[status] += 1

        # 統計優先級
        if priority in summary["by_priority"]:
            summary["by_priority"][priority] += 1

        # 統計評分
        if rating:
            summary["with_rating"] += 1
            total_rating += rating
            rated_count += 1

    # 計算平均評分
    if rated_count > 0:
        summary["avg_rating"] = total_rating / rated_count

    return summary


# format_duration 函數已移至 bot.utils.helper 模組以避免重複


def format_timestamp(timestamp: datetime, format_type: str = "relative") -> str:
    """格式化時間戳"""
    if format_type == "relative":
        return get_time_ago_chinese(timestamp)
    elif format_type == "absolute":
        return timestamp.strftime("%Y-%m-%d %H:%M:%S")
    elif format_type == "discord":
        return f"<t:{int(timestamp.timestamp())}:F>"
    else:
        return str(timestamp)


def format_user_mention(user_id: Union[str, int]) -> str:
    """格式化用戶提及"""
    return f"<@{user_id}>"


def format_channel_mention(channel_id: Union[str, int]) -> str:
    """格式化頻道提及"""
    return f"<#{channel_id}>"


def format_role_mention(role_id: Union[str, int]) -> str:
    """格式化身分組提及"""
    return f"<@&{role_id}>"


# ===== 快取管理 =====


class TicketCache:
    """票券系統快取管理器"""

    def __init__(self, timeout_minutes: int = 5):
        self.cache = {}
        self.timeout_seconds = timeout_minutes * 60
        self.access_times = {}

    def set(self, key: str, value: Any, timeout: int = None) -> None:
        """設定快取"""
        self.cache[key] = value
        self.access_times[key] = datetime.now(timezone.utc)

        if timeout:
            # 自訂過期時間
            asyncio.create_task(self._expire_key(key, timeout))

    def get(self, key: str) -> Any:
        """取得快取"""
        if key not in self.cache:
            return None

        # 檢查是否過期
        if self._is_expired(key):
            self.delete(key)
            return None

        # 更新存取時間
        self.access_times[key] = datetime.now(timezone.utc)
        return self.cache[key]

    def delete(self, key: str) -> None:
        """刪除快取"""
        self.cache.pop(key, None)
        self.access_times.pop(key, None)

    def clear(self) -> None:
        """清空快取"""
        self.cache.clear()
        self.access_times.clear()

    def _is_expired(self, key: str) -> bool:
        """檢查快取是否過期"""
        if key not in self.access_times:
            return True

        last_access = self.access_times[key]
        return (datetime.now(timezone.utc) - last_access).total_seconds() > self.timeout_seconds

    async def _expire_key(self, key: str, timeout: int) -> None:
        """延遲刪除快取鍵"""
        await asyncio.sleep(timeout)
        self.delete(key)

    def get_stats(self) -> Dict[str, Any]:
        """取得快取統計"""
        total_keys = len(self.cache)
        expired_keys = sum(1 for key in self.cache.keys() if self._is_expired(key))

        return {
            "total_keys": total_keys,
            "active_keys": total_keys - expired_keys,
            "expired_keys": expired_keys,
            "hit_rate": 0,  # 可以實現更詳細的命中率統計
        }

    def cleanup_expired(self) -> int:
        """清理過期快取"""
        expired_keys = [key for key in self.cache.keys() if self._is_expired(key)]
        for key in expired_keys:
            self.delete(key)
        return len(expired_keys)


# ===== 通知工具 =====


async def send_ticket_notification(
    user: discord.Member, title: str, description: str, color: discord.Color = discord.Color.blue()
) -> bool:
    """發送票券通知"""
    try:
        embed = discord.Embed(title=title, description=description, color=color)
        embed.set_footer(text="票券系統通知")

        await user.send(embed=embed)
        return True
    except discord.Forbidden:

        return False


async def send_sla_alert(
    channel: discord.TextChannel, ticket_info: Dict[str, Any], overdue_minutes: float
) -> bool:
    """發送SLA超時警告"""
    try:
        priority_emoji = get_priority_emoji(ticket_info.get("priority", "medium"))

        embed = discord.Embed(
            title="⚠️ SLA 超時警告",
            description=f"票券 #{ticket_info['ticket_id']:04d} 已超過目標回應時間",
            color=discord.Color.red(),
        )

        embed.add_field(
            name="票券資訊",
            value=f"**類型：** {ticket_info['type']}\n"
            f"**優先級：** {priority_emoji} {ticket_info.get('priority', 'medium').upper()}\n"
            f"**開票者：** <@{ticket_info['discord_id']}>",
            inline=True,
        )

        embed.add_field(
            name="超時資訊",
            value=f"**超時時間：** {overdue_minutes:.0f} 分鐘\n"
            f"**頻道：** <#{ticket_info['channel_id']}>",
            inline=True,
        )

        await channel.send(embed=embed)
        return True
    except Exception:

        return False


# ===== 資料驗證工具 =====


def validate_ticket_data(ticket_data: Dict[str, Any]) -> Tuple[bool, str]:
    """驗證票券資料完整性"""
    required_fields = ["discord_id", "username", "type", "channel_id", "guild_id"]

    for field in required_fields:
        if field not in ticket_data or not ticket_data[field]:
            return False, f"缺少必要欄位：{field}"

    # 驗證資料類型
    try:
        int(ticket_data["discord_id"])
        int(ticket_data["channel_id"])
        int(ticket_data["guild_id"])
    except (ValueError, TypeError):
        return False, "ID欄位必須是數字"

    # 驗證優先級
    if "priority" in ticket_data:
        if ticket_data["priority"] not in TicketConstants.PRIORITIES:
            return False, f"無效的優先級：{ticket_data['priority']}"

    return True, ""


def sanitize_ticket_input(input_text: str) -> str:
    """清理票券輸入文字"""
    if not input_text:
        return ""

    # 移除危險字符
    sanitized = re.sub(r"[<>@#&]", "", input_text)

    # 限制長度
    sanitized = sanitized[:500]

    # 清理多餘空白
    sanitized = re.sub(r"\s+", " ", sanitized).strip()

    return sanitized


# ===== 統計工具 =====


def calculate_ticket_metrics(tickets: List[Dict[str, Any]]) -> Dict[str, Any]:
    """計算票券指標"""
    if not tickets:
        return {
            "total_count": 0,
            "avg_resolution_time": 0,
            "satisfaction_rate": 0,
            "sla_compliance_rate": 0,
        }

    total_count = len(tickets)
    resolution_times = []
    ratings = []

    for ticket in tickets:
        # 計算解決時間
        if ticket.get("closed_at") and ticket.get("created_at"):
            closed_at = ticket["closed_at"]
            created_at = ticket["created_at"]
            # 確保時間戳有時區資訊
            if closed_at.tzinfo is None:
                closed_at = closed_at.replace(tzinfo=timezone.utc)
            if created_at.tzinfo is None:
                created_at = created_at.replace(tzinfo=timezone.utc)
            resolution_time = closed_at - created_at
            resolution_times.append(resolution_time.total_seconds() / 3600)  # 轉換為小時

        # 收集評分
        if ticket.get("rating"):
            ratings.append(ticket["rating"])

    # 計算平均解決時間
    avg_resolution_time = sum(resolution_times) / len(resolution_times) if resolution_times else 0

    # 計算滿意度（4星以上視為滿意）
    satisfied_count = sum(1 for rating in ratings if rating >= 4)
    satisfaction_rate = (satisfied_count / len(ratings)) * 100 if ratings else 0

    return {
        "total_count": total_count,
        "avg_resolution_time": avg_resolution_time,
        "satisfaction_rate": satisfaction_rate,
        "total_ratings": len(ratings),
        "avg_rating": sum(ratings) / len(ratings) if ratings else 0,
    }


def generate_ticket_report(tickets: List[Dict[str, Any]], period: str = "week") -> str:
    """生成票券報告"""
    metrics = calculate_ticket_metrics(tickets)
    status_summary = format_ticket_status_summary(tickets)

    report = f"# 票券系統報告 - {period}\n\n"

    report += "## 📊 總體統計\n"
    report += f"- 總票券數：{status_summary['total']}\n"
    report += f"- 開啟中：{status_summary['open']}\n"
    report += f"- 已關閉：{status_summary['closed']}\n"
    report += f"- 平均解決時間：{metrics['avg_resolution_time']:.1f} 小時\n\n"

    report += "## ⭐ 滿意度分析\n"
    report += f"- 總評分數：{metrics['total_ratings']}\n"
    report += f"- 平均評分：{metrics['avg_rating']:.1f}/5\n"
    report += f"- 滿意度：{metrics['satisfaction_rate']:.1f}%\n\n"

    report += "## 🎯 優先級分布\n"
    for priority, count in status_summary["by_priority"].items():
        emoji = get_priority_emoji(priority)
        report += f"- {emoji} {priority.upper()}：{count} 張\n"

    return report


# ===== 工具函數導出 =====

__all__ = [
    "TicketPermissionChecker",
    "is_ticket_channel",
    "parse_ticket_id_from_channel",
    "generate_ticket_channel_name",
    "create_ticket_channel_overwrites",
    "parse_channel_mention",
    "parse_role_mention",
    "build_ticket_embed",
    "build_stats_embed",
    "build_sla_embed",
    "build_staff_performance_embed",
    "build_user_tickets_embed",
    "check_auto_reply_keywords",
    "process_auto_reply_message",
    "get_best_auto_reply",
    "format_settings_value",
    "format_ticket_status_summary",
    "format_duration",
    "format_timestamp",
    "format_user_mention",
    "format_channel_mention",
    "format_role_mention",
    "TicketCache",
    "send_ticket_notification",
    "send_sla_alert",
    "validate_ticket_data",
    "sanitize_ticket_input",
    "calculate_ticket_metrics",
    "generate_ticket_report",
]
