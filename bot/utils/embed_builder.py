# bot/utils/embed_builder.py - 修復版
"""
Embed 建構器 - 修復版
修復點：
1. 修正 datetime 導入問題
2. 添加錯誤處理
3. 統一嵌入樣式
4. 添加更多嵌入類型
"""

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Union

import discord

logger = logging.getLogger(__name__)


class EmbedBuilder:
    """Discord Embed 建構器"""

    # 預定義顏色
    COLORS = {
        "success": discord.Color.green(),
        "error": discord.Color.red(),
        "warning": discord.Color.orange(),
        "info": discord.Color.blue(),
        "primary": discord.Color.blurple(),
        "secondary": discord.Color.greyple(),
    }

    @staticmethod
    def build(
        title: str = None,
        description: str = None,
        color: Union[discord.Color, int] = None,
        timestamp: bool = True,
        **kwargs,
    ) -> discord.Embed:
        """
        建立基礎 Embed

        Args:
            title: 標題
            description: 描述
            color: 顏色
            timestamp: 是否添加時間戳
            **kwargs: 其他 Embed 參數
        """
        try:
            # 設定預設顏色
            if color is None:
                color = EmbedBuilder.COLORS["info"]
            elif isinstance(color, str) and color in EmbedBuilder.COLORS:
                color = EmbedBuilder.COLORS[color]

            # 建立 Embed
            embed = discord.Embed(title=title, description=description, color=color, **kwargs)

            # 添加時間戳
            if timestamp:
                embed.timestamp = datetime.now(timezone.utc)  # 修復：使用 timezone.utc

            return embed

        except Exception as e:
            logger.error(f"建立 Embed 失敗：{e}")
            # 返回基本 Embed 作為後備
            return discord.Embed(
                title="系統錯誤",
                description="建立訊息時發生錯誤",
                color=discord.Color.red(),
            )

    @staticmethod
    def success(title: str, description: str = None, **kwargs) -> discord.Embed:
        """建立成功嵌入"""
        return EmbedBuilder.build(
            title=f"✅ {title}", description=description, color="success", **kwargs
        )

    @staticmethod
    def error(title: str, description: str = None, **kwargs) -> discord.Embed:
        """建立錯誤嵌入"""
        return EmbedBuilder.build(
            title=f"❌ {title}", description=description, color="error", **kwargs
        )

    @staticmethod
    def warning(title: str, description: str = None, **kwargs) -> discord.Embed:
        """建立警告嵌入"""
        return EmbedBuilder.build(
            title=f"⚠️ {title}", description=description, color="warning", **kwargs
        )

    @staticmethod
    def info(title: str, description: str = None, **kwargs) -> discord.Embed:
        """建立資訊嵌入"""
        return EmbedBuilder.build(
            title=f"ℹ️ {title}", description=description, color="info", **kwargs
        )

    @staticmethod
    def loading(title: str = "處理中", description: str = "請稍候...") -> discord.Embed:
        """建立載入中嵌入"""
        return EmbedBuilder.build(title=f"⏳ {title}", description=description, color="secondary")

    @staticmethod
    def ticket_embed(ticket_info: Dict[str, Any], **kwargs) -> discord.Embed:
        """建立票券專用嵌入"""
        try:
            from bot.utils.ticket_constants import (
                get_priority_color,
                get_priority_emoji,
                get_status_emoji,
            )

            priority = ticket_info.get("priority", "medium")
            status = ticket_info.get("status", "open")

            embed = EmbedBuilder.build(
                title=f"🎫 票券 #{ticket_info.get('id', 0):04d}",
                color=get_priority_color(priority),
                **kwargs,
            )

            # 基本資訊
            priority_emoji = get_priority_emoji(priority)
            status_emoji = get_status_emoji(status)

            embed.add_field(
                name="📋 基本資訊",
                value=f"**類型：** {ticket_info.get('type', '未知')}\n"
                f"**狀態：** {status_emoji} {status.upper()}\n"
                f"**優先級：** {priority_emoji} {priority.upper()}",
                inline=True,
            )

            # 用戶資訊
            embed.add_field(
                name="👤 用戶資訊",
                value=f"**開票者：** <@{ticket_info.get('discord_id', '0')}>\n"
                f"**用戶名：** {ticket_info.get('username', '未知')}",
                inline=True,
            )

            return embed

        except Exception as e:
            logger.error(f"建立票券 Embed 失敗：{e}")
            return EmbedBuilder.error("票券資訊載入失敗", "無法顯示票券詳細資訊")

    @staticmethod
    def vote_embed(vote_info: Dict[str, Any], **kwargs) -> discord.Embed:
        """建立投票專用嵌入"""
        try:
            embed = EmbedBuilder.build(
                title=f"🗳️ 投票：{vote_info.get('title', '未知投票')}",
                color="primary",
                **kwargs,
            )

            # 投票資訊
            total_votes = vote_info.get("total_votes", 0)
            is_multi = vote_info.get("is_multi", False)
            anonymous = vote_info.get("anonymous", False)

            embed.add_field(
                name="📊 投票資訊",
                value=f"**總票數：** {total_votes}\n"
                f"**模式：** {'多選' if is_multi else '單選'}\n"
                f"**類型：** {'匿名' if anonymous else '公開'}",
                inline=True,
            )

            # 時間資訊
            if "end_time" in vote_info:
                end_time = vote_info["end_time"]
                if isinstance(end_time, datetime):
                    embed.add_field(
                        name="⏰ 結束時間",
                        value=f"<t:{int(end_time.timestamp())}:R>",
                        inline=True,
                    )

            return embed

        except Exception as e:
            logger.error(f"建立投票 Embed 失敗：{e}")
            return EmbedBuilder.error("投票資訊載入失敗", "無法顯示投票詳細資訊")

    @staticmethod
    def stats_embed(stats: Dict[str, Any], title: str = "📊 統計資訊", **kwargs) -> discord.Embed:
        """建立統計嵌入"""
        try:
            embed = EmbedBuilder.build(title=title, color="info", **kwargs)

            # 基本統計
            if "total" in stats:
                embed.add_field(name="📈 總計", value=f"**總數：** {stats['total']:,}", inline=True)

            # 處理其他統計數據
            for key, value in stats.items():
                if key == "total":
                    continue

                field_name = key.replace("_", " ").title()

                if isinstance(value, (int, float)):
                    if key.endswith("_rate") or key.endswith("_percentage"):
                        field_value = f"{value:.1f}%"
                    else:
                        field_value = f"{value:,}"
                else:
                    field_value = str(value)

                embed.add_field(name=field_name, value=field_value, inline=True)

            return embed

        except Exception as e:
            logger.error(f"建立統計 Embed 失敗：{e}")
            return EmbedBuilder.error("統計載入失敗", "無法顯示統計資訊")

    @staticmethod
    def help_embed(
        commands_data: List[Dict[str, Any]], title: str = "📋 命令幫助", **kwargs
    ) -> discord.Embed:
        """建立幫助嵌入"""
        try:
            embed = EmbedBuilder.build(title=title, color="primary", **kwargs)

            for cmd_data in commands_data:
                name = cmd_data.get("name", "未知命令")
                description = cmd_data.get("description", "沒有描述")
                usage = cmd_data.get("usage", "")

                field_value = description
                if usage:
                    field_value += f"\n**用法：** `{usage}`"

                embed.add_field(name=f"/{name}", value=field_value, inline=False)

            return embed

        except Exception as e:
            logger.error(f"建立幫助 Embed 失敗：{e}")
            return EmbedBuilder.error("幫助載入失敗", "無法顯示命令幫助")

    @staticmethod
    def pagination_embed(
        items: List[Any],
        page: int,
        total_pages: int,
        title: str = "📋 列表",
        formatter=None,
        **kwargs,
    ) -> discord.Embed:
        """建立分頁嵌入"""
        try:
            embed = EmbedBuilder.build(
                title=f"{title} (第 {page}/{total_pages} 頁)", color="info", **kwargs
            )

            if not items:
                embed.description = "📭 沒有找到任何項目"
                return embed

            # 格式化項目
            if formatter:
                for item in items:
                    formatted = formatter(item)
                    if isinstance(formatted, dict):
                        embed.add_field(**formatted)
                    else:
                        embed.add_field(
                            name=f"項目 {items.index(item) + 1}",
                            value=str(formatted),
                            inline=False,
                        )
            else:
                # 預設格式化
                for i, item in enumerate(items, 1):
                    embed.add_field(name=f"項目 {i}", value=str(item), inline=False)

            # 分頁資訊
            embed.set_footer(text=f"第 {page} 頁，共 {total_pages} 頁")

            return embed

        except Exception as e:
            logger.error(f"建立分頁 Embed 失敗：{e}")
            return EmbedBuilder.error("分頁載入失敗", "無法顯示分頁內容")

    @staticmethod
    def settings_embed(
        settings: Dict[str, Any], title: str = "⚙️ 系統設定", **kwargs
    ) -> discord.Embed:
        """建立設定嵌入"""
        try:
            embed = EmbedBuilder.build(title=title, color="secondary", **kwargs)

            for key, value in settings.items():
                # 格式化設定名稱
                field_name = key.replace("_", " ").title()

                # 格式化設定值
                if isinstance(value, bool):
                    field_value = "✅ 啟用" if value else "❌ 停用"
                elif isinstance(value, list):
                    if value:
                        field_value = f"{len(value)} 個項目"
                    else:
                        field_value = "未設定"
                elif value is None:
                    field_value = "未設定"
                else:
                    field_value = str(value)

                embed.add_field(name=field_name, value=field_value, inline=True)

            return embed

        except Exception as e:
            logger.error(f"建立設定 Embed 失敗：{e}")
            return EmbedBuilder.error("設定載入失敗", "無法顯示系統設定")

    @staticmethod
    def status_embed(
        status_data: Dict[str, Any], title: str = "📊 系統狀態", **kwargs
    ) -> discord.Embed:
        """建立狀態嵌入"""
        try:
            # 根據整體狀態決定顏色
            overall_status = status_data.get("overall_status", "unknown")
            if overall_status == "healthy":
                color = "success"
            elif overall_status == "degraded":
                color = "warning"
            else:
                color = "error"

            embed = EmbedBuilder.build(title=title, color=color, **kwargs)

            # 整體狀態
            status_emoji = {"healthy": "✅", "degraded": "⚠️", "unhealthy": "❌"}.get(
                overall_status, "❓"
            )

            embed.add_field(
                name="📈 整體狀態",
                value=f"{status_emoji} {overall_status.title()}",
                inline=True,
            )

            # 其他狀態資訊
            for key, value in status_data.items():
                if key == "overall_status":
                    continue

                field_name = key.replace("_", " ").title()

                if isinstance(value, dict):
                    # 嵌套狀態
                    field_value = ""
                    for sub_key, sub_value in value.items():
                        field_value += f"**{sub_key.title()}:** {sub_value}\n"
                else:
                    field_value = str(value)

                embed.add_field(name=field_name, value=field_value, inline=True)

            return embed

        except Exception as e:
            logger.error(f"建立狀態 Embed 失敗：{e}")
            return EmbedBuilder.error("狀態載入失敗", "無法顯示系統狀態")

    @staticmethod
    def create_field_list(items: List[str], max_per_field: int = 10) -> List[Dict[str, Any]]:
        """將長列表分割為多個欄位"""
        fields = []
        for i in range(0, len(items), max_per_field):
            chunk = items[i : i + max_per_field]
            field_num = (i // max_per_field) + 1

            fields.append({"name": f"項目 {field_num}", "value": "\n".join(chunk), "inline": True})

        return fields

    @staticmethod
    def safe_add_field(embed: discord.Embed, name: str, value: str, inline: bool = False):
        """安全添加欄位（避免超過 Discord 限制）"""
        try:
            # Discord 限制
            MAX_FIELD_NAME = 256
            MAX_FIELD_VALUE = 1024
            MAX_FIELDS = 25

            # 檢查欄位數量
            if len(embed.fields) >= MAX_FIELDS:
                return False

            # 截斷過長的文字
            if len(name) > MAX_FIELD_NAME:
                name = name[: MAX_FIELD_NAME - 3] + "..."

            if len(value) > MAX_FIELD_VALUE:
                value = value[: MAX_FIELD_VALUE - 3] + "..."

            embed.add_field(name=name, value=value, inline=inline)
            return True

        except Exception as e:
            logger.error(f"添加欄位失敗：{e}")
            return False


# ===== 便捷函數 =====


def quick_embed(text: str, type: str = "info") -> discord.Embed:
    """快速建立簡單嵌入"""
    builders = {
        "success": EmbedBuilder.success,
        "error": EmbedBuilder.error,
        "warning": EmbedBuilder.warning,
        "info": EmbedBuilder.info,
    }

    builder = builders.get(type, EmbedBuilder.info)
    return builder("訊息", text)


def embed_from_dict(data: Dict[str, Any]) -> discord.Embed:
    """從字典建立嵌入"""
    try:
        embed = EmbedBuilder.build(
            title=data.get("title"),
            description=data.get("description"),
            color=data.get("color"),
        )

        # 添加欄位
        for field in data.get("fields", []):
            EmbedBuilder.safe_add_field(
                embed,
                field.get("name", ""),
                field.get("value", ""),
                field.get("inline", False),
            )

        # 設定其他屬性
        if "footer" in data:
            embed.set_footer(text=data["footer"])

        if "thumbnail" in data:
            embed.set_thumbnail(url=data["thumbnail"])

        if "image" in data:
            embed.set_image(url=data["image"])

        return embed

    except Exception as e:
        logger.error(f"從字典建立 Embed 失敗：{e}")
        return EmbedBuilder.error("格式錯誤", "無法解析嵌入格式")


# ===== 新增方法以支持抽獎系統 =====
# 為了向後兼容添加的靜態方法


def add_static_methods():
    """為 EmbedBuilder 添加靜態方法"""

    @staticmethod
    def create_info_embed(title: str, description: str = None) -> discord.Embed:
        """創建信息嵌入"""
        return EmbedBuilder.build(title=title, description=description, color="info")

    @staticmethod
    def create_success_embed(title: str, description: str = None) -> discord.Embed:
        """創建成功嵌入"""
        return EmbedBuilder.build(title=title, description=description, color="success")

    @staticmethod
    def create_error_embed(title: str, description: str = None) -> discord.Embed:
        """創建錯誤嵌入"""
        return EmbedBuilder.build(title=title, description=description, color="error")

    @staticmethod
    def create_warning_embed(title: str, description: str = None) -> discord.Embed:
        """創建警告嵌入"""
        return EmbedBuilder.build(title=title, description=description, color="warning")

    # 動態添加方法到 EmbedBuilder 類
    EmbedBuilder.create_info_embed = create_info_embed
    EmbedBuilder.create_success_embed = create_success_embed
    EmbedBuilder.create_error_embed = create_error_embed
    EmbedBuilder.create_warning_embed = create_warning_embed


# 執行添加
add_static_methods()
