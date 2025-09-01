# bot/services/tag_manager.py - 標籤系統管理服務
"""
標籤系統管理服務
處理標籤的業務邏輯、自動應用、搜索等功能
"""

import re
from typing import Any, Dict, List, Optional, Tuple

import discord

from bot.db.tag_dao import TagDAO
from shared.logger import logger


class TagManager:
    """標籤系統管理器"""

    def __init__(self, tag_dao: TagDAO = None):
        self.tag_dao = tag_dao or TagDAO()

        # 預設標籤分類配置
        self.default_categories = {
            "system": {"name": "系統", "emoji": "⚙️", "color": "#666666"},
            "department": {"name": "部門", "emoji": "🏢", "color": "#3498db"},
            "custom": {"name": "自定義", "emoji": "🏷️", "color": "#9b59b6"},
            "priority": {"name": "優先級", "emoji": "⚡", "color": "#e74c3c"},
            "status": {"name": "狀態", "emoji": "📊", "color": "#2ecc71"},
        }

        # 預設系統標籤
        self.system_tags = [
            {
                "name": "urgent",
                "display_name": "緊急",
                "color": "#e74c3c",
                "emoji": "🚨",
                "category": "priority",
            },
            {
                "name": "bug",
                "display_name": "錯誤回報",
                "color": "#e67e22",
                "emoji": "🐛",
                "category": "system",
            },
            {
                "name": "feature",
                "display_name": "功能請求",
                "color": "#3498db",
                "emoji": "✨",
                "category": "system",
            },
            {
                "name": "question",
                "display_name": "一般問題",
                "color": "#f39c12",
                "emoji": "❓",
                "category": "system",
            },
            {
                "name": "resolved",
                "display_name": "已解決",
                "color": "#27ae60",
                "emoji": "✅",
                "category": "status",
            },
            {
                "name": "pending",
                "display_name": "等待回覆",
                "color": "#f1c40f",
                "emoji": "⏳",
                "category": "status",
            },
        ]

    # ========== 標籤創建與管理 ==========

    async def create_tag(
        self,
        guild_id: int,
        name: str,
        display_name: str,
        color: str = None,
        emoji: str = None,
        description: str = None,
        category: str = "custom",
        created_by: int = None,
    ) -> Tuple[bool, str, Optional[int]]:
        """創建新標籤"""
        try:
            # 驗證標籤名稱
            if not self._validate_tag_name(name):
                return (
                    False,
                    "標籤名稱只能包含字母、數字、底線和連字符，長度 2-50 字元",
                    None,
                )

            # 驗證顏色格式
            if color and not self._validate_color(color):
                return (
                    False,
                    "顏色格式無效，請使用 HEX 格式（如 #FF0000）",
                    None,
                )

            # 檢查標籤是否已存在
            existing_tags = await self.tag_dao.get_tags_by_guild(guild_id)
            if any(
                tag["name"].lower() == name.lower() for tag in existing_tags
            ):
                return False, f"標籤名稱 '{name}' 已存在", None

            # 設定預設值
            if not color:
                color = self.default_categories.get(category, {}).get(
                    "color", "#808080"
                )

            if not emoji and category in self.default_categories:
                emoji = self.default_categories[category]["emoji"]

            # 創建標籤
            tag_id = await self.tag_dao.create_tag(
                guild_id,
                name,
                display_name,
                color,
                emoji,
                description,
                category,
                created_by,
            )

            if tag_id:
                logger.info(
                    f"標籤創建成功: {display_name} ({name}) by {created_by}"
                )
                return True, f"標籤 '{display_name}' 創建成功", tag_id
            else:
                return False, "創建標籤失敗，請稍後再試", None

        except Exception as e:
            logger.error(f"創建標籤錯誤：{e}")
            return False, f"創建過程中發生錯誤：{str(e)}", None

    async def update_tag(self, tag_id: int, **kwargs) -> Tuple[bool, str]:
        """更新標籤"""
        try:
            # 驗證更新欄位
            valid_fields = [
                "display_name",
                "color",
                "emoji",
                "description",
                "category",
                "is_active",
            ]
            filtered_kwargs = {
                k: v for k, v in kwargs.items() if k in valid_fields
            }

            if not filtered_kwargs:
                return False, "沒有有效的更新欄位"

            # 驗證顏色格式
            if "color" in filtered_kwargs and not self._validate_color(
                filtered_kwargs["color"]
            ):
                return False, "顏色格式無效，請使用 HEX 格式"

            success = await self.tag_dao.update_tag(tag_id, **filtered_kwargs)

            if success:
                return True, "標籤更新成功"
            else:
                return False, "標籤更新失敗"

        except Exception as e:
            logger.error(f"更新標籤錯誤：{e}")
            return False, f"更新過程中發生錯誤：{str(e)}"

    async def delete_tag(self, tag_id: int) -> Tuple[bool, str]:
        """刪除標籤"""
        try:
            # 檢查標籤是否存在
            tag = await self.tag_dao.get_tag_by_id(tag_id)
            if not tag:
                return False, "標籤不存在"

            success = await self.tag_dao.delete_tag(tag_id)

            if success:
                logger.info(
                    f"標籤已刪除: {tag['display_name']} (ID: {tag_id})"
                )
                return True, f"標籤 '{tag['display_name']}' 已刪除"
            else:
                return False, "刪除標籤失敗"

        except Exception as e:
            logger.error(f"刪除標籤錯誤：{e}")
            return False, f"刪除過程中發生錯誤：{str(e)}"

    # ========== 標籤應用與移除 ==========

    async def add_tag_to_ticket(
        self, ticket_id: int, tag_id: int, added_by: int
    ) -> Tuple[bool, str]:
        """為票券添加標籤"""
        try:
            # 檢查標籤是否存在
            tag = await self.tag_dao.get_tag_by_id(tag_id)
            if not tag:
                return False, "標籤不存在"

            success = await self.tag_dao.add_tag_to_ticket(
                ticket_id, tag_id, added_by
            )

            if success:
                logger.info(
                    f"標籤添加成功: 票券 #{ticket_id} + {tag['display_name']}"
                )
                return True, f"已為票券添加標籤 '{tag['display_name']}'"
            else:
                return False, "添加標籤失敗"

        except Exception as e:
            logger.error(f"添加標籤錯誤：{e}")
            return False, f"添加過程中發生錯誤：{str(e)}"

    async def remove_tag_from_ticket(
        self, ticket_id: int, tag_id: int
    ) -> Tuple[bool, str]:
        """從票券移除標籤"""
        try:
            # 檢查標籤是否存在
            tag = await self.tag_dao.get_tag_by_id(tag_id)
            if not tag:
                return False, "標籤不存在"

            success = await self.tag_dao.remove_tag_from_ticket(
                ticket_id, tag_id
            )

            if success:
                logger.info(
                    f"標籤移除成功: 票券 #{ticket_id} - {tag['display_name']}"
                )
                return True, f"已從票券移除標籤 '{tag['display_name']}'"
            else:
                return False, "移除標籤失敗"

        except Exception as e:
            logger.error(f"移除標籤錯誤：{e}")
            return False, f"移除過程中發生錯誤：{str(e)}"

    # ========== 自動標籤系統 ==========

    async def apply_auto_tags(
        self,
        guild_id: int,
        ticket_id: int,
        ticket_type: str,
        content: str,
        user: discord.Member = None,
    ) -> List[Dict[str, Any]]:
        """應用自動標籤規則"""
        try:
            user_roles = [role.id for role in user.roles] if user else []

            # 應用自動規則
            applied_tag_ids = await self.tag_dao.apply_auto_rules(
                guild_id, ticket_id, ticket_type, content, user_roles
            )

            # 取得應用的標籤詳細資訊
            applied_tags = []
            for tag_id in applied_tag_ids:
                tag = await self.tag_dao.get_tag_by_id(tag_id)
                if tag:
                    applied_tags.append(tag)

            if applied_tags:
                tag_names = [tag["display_name"] for tag in applied_tags]
                logger.info(
                    f"自動應用標籤: 票券 #{ticket_id} -> {', '.join(tag_names)}"
                )

            return applied_tags

        except Exception as e:
            logger.error(f"應用自動標籤錯誤：{e}")
            return []

    async def create_auto_rule(
        self,
        guild_id: int,
        rule_name: str,
        tag_id: int,
        trigger_type: str,
        trigger_value: str,
        created_by: int,
        priority: int = 1,
    ) -> Tuple[bool, str, Optional[int]]:
        """創建自動標籤規則"""
        try:
            # 驗證觸發類型
            valid_trigger_types = [
                "keyword",
                "ticket_type",
                "user_role",
                "channel",
            ]
            if trigger_type not in valid_trigger_types:
                return (
                    False,
                    f"無效的觸發類型，支援：{', '.join(valid_trigger_types)}",
                    None,
                )

            # 檢查標籤是否存在
            tag = await self.tag_dao.get_tag_by_id(tag_id)
            if not tag:
                return False, "指定的標籤不存在", None

            rule_id = await self.tag_dao.create_auto_rule(
                guild_id,
                rule_name,
                tag_id,
                trigger_type,
                trigger_value,
                created_by,
                priority,
            )

            if rule_id:
                return True, f"自動標籤規則 '{rule_name}' 創建成功", rule_id
            else:
                return False, "創建自動標籤規則失敗", None

        except Exception as e:
            logger.error(f"創建自動標籤規則錯誤：{e}")
            return False, f"創建過程中發生錯誤：{str(e)}", None

    # ========== 搜索與統計 ==========

    async def search_tags(
        self, guild_id: int, query: str, limit: int = 20
    ) -> List[Dict[str, Any]]:
        """搜索標籤"""
        try:
            if len(query.strip()) < 2:
                return []

            tags = await self.tag_dao.search_tags(
                guild_id, query.strip(), limit
            )
            return tags

        except Exception as e:
            logger.error(f"搜索標籤錯誤：{e}")
            return []

    async def get_tag_statistics(
        self, guild_id: int, days: int = 30
    ) -> Dict[str, Any]:
        """取得標籤使用統計"""
        try:
            # 取得使用統計
            usage_stats = await self.tag_dao.get_tag_usage_stats(
                guild_id, days
            )

            # 計算總體統計
            total_tags = len(usage_stats)
            total_usage = sum(tag["usage_count"] or 0 for tag in usage_stats)
            active_tags = len(
                [tag for tag in usage_stats if (tag["usage_count"] or 0) > 0]
            )

            # 分類統計
            category_stats = {}
            for tag in usage_stats:
                category = tag["category"]
                if category not in category_stats:
                    category_stats[category] = {"count": 0, "usage": 0}
                category_stats[category]["count"] += 1
                category_stats[category]["usage"] += tag["usage_count"] or 0

            # 熱門標籤
            popular_tags = sorted(
                usage_stats,
                key=lambda x: (x["usage_count"] or 0),
                reverse=True,
            )[:10]

            return {
                "total_tags": total_tags,
                "active_tags": active_tags,
                "total_usage": total_usage,
                "category_stats": category_stats,
                "popular_tags": popular_tags,
                "usage_stats": usage_stats,
            }

        except Exception as e:
            logger.error(f"取得標籤統計錯誤：{e}")
            return {}

    # ========== 初始化與預設標籤 ==========

    async def initialize_default_tags(
        self, guild_id: int, created_by: int
    ) -> Tuple[bool, str, int]:
        """初始化預設標籤"""
        try:
            created_count = 0

            for tag_data in self.system_tags:
                # 檢查標籤是否已存在
                existing_tags = await self.tag_dao.get_tags_by_guild(guild_id)
                if any(
                    tag["name"] == tag_data["name"] for tag in existing_tags
                ):
                    continue

                tag_id = await self.tag_dao.create_tag(
                    guild_id=guild_id,
                    name=tag_data["name"],
                    display_name=tag_data["display_name"],
                    color=tag_data["color"],
                    emoji=tag_data["emoji"],
                    category=tag_data["category"],
                    created_by=created_by,
                )

                if tag_id:
                    created_count += 1

            logger.info(
                f"初始化預設標籤完成: 伺服器 {guild_id}，創建 {created_count} 個標籤"
            )
            return (
                True,
                f"成功初始化 {created_count} 個預設標籤",
                created_count,
            )

        except Exception as e:
            logger.error(f"初始化預設標籤錯誤：{e}")
            return False, f"初始化過程中發生錯誤：{str(e)}", 0

    # ========== 工具方法 ==========

    def _validate_tag_name(self, name: str) -> bool:
        """驗證標籤名稱格式"""
        if not name or len(name) < 2 or len(name) > 50:
            return False

        # 只允許字母、數字、底線和連字符
        pattern = r"^[a-zA-Z0-9_-]+$"
        return bool(re.match(pattern, name))

    def _validate_color(self, color: str) -> bool:
        """驗證顏色格式"""
        if not color:
            return True

        # 檢查 HEX 格式
        pattern = r"^#[0-9A-Fa-f]{6}$"
        return bool(re.match(pattern, color))

    def format_tag_display(
        self, tag: Dict[str, Any], include_usage: bool = False
    ) -> str:
        """格式化標籤顯示"""
        emoji = tag.get("emoji", "")
        display_name = tag.get("display_name", tag.get("name", ""))

        result = f"{emoji} {display_name}" if emoji else display_name

        if include_usage and "usage_count" in tag:
            usage = tag["usage_count"] or 0
            result += f" ({usage})"

        return result

    def get_category_info(self, category: str) -> Dict[str, str]:
        """取得分類資訊"""
        return self.default_categories.get(
            category, {"name": category, "emoji": "🏷️", "color": "#808080"}
        )

    async def get_formatted_tag_list(
        self, guild_id: int, category: str = None
    ) -> str:
        """取得格式化的標籤列表"""
        try:
            tags = await self.tag_dao.get_tags_by_guild(guild_id, category)

            if not tags:
                return "沒有找到標籤" if category else "還沒有任何標籤"

            # 按分類分組
            categories = {}
            for tag in tags:
                cat = tag["category"]
                if cat not in categories:
                    categories[cat] = []
                categories[cat].append(tag)

            # 格式化輸出
            lines = []
            for cat, cat_tags in categories.items():
                cat_info = self.get_category_info(cat)
                lines.append(f"\n**{cat_info['emoji']} {cat_info['name']}**")

                for tag in cat_tags:
                    tag_display = self.format_tag_display(
                        tag, include_usage=True
                    )
                    lines.append(f"• {tag_display}")

            return "\n".join(lines)

        except Exception as e:
            logger.error(f"格式化標籤列表錯誤：{e}")
            return "無法取得標籤列表"
