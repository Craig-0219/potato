# bot/services/vote_template_manager.py
"""
投票模板管理服務
負責投票模板的初始化、管理和應用
"""

from typing import Any, Dict, List, Optional

from bot.db.vote_template_dao import vote_template_dao
from shared.logger import logger


class VoteTemplateManager:
    """投票模板管理器"""

    def __init__(self):
        self.predefined_templates = self._get_predefined_templates()

    def _get_predefined_templates(self) -> List[Dict[str, Any]]:
        """取得預定義的模板列表"""
        return [
            # 民意調查模板
            {
                "name": "📊 簡單民意調查",
                "description": "適合快速收集意見的單選投票模板",
                "category": "poll",
                "title_template": "📊 關於{topic}的意見調查",
                "options_template": ["贊成", "反對", "中立"],
                "default_duration": 120,
                "default_is_multi": False,
                "default_anonymous": True,
                "is_public": True,
            },
            {
                "name": "📋 多選民調",
                "description": "允許多選的民意調查模板",
                "category": "poll",
                "title_template": "📋 {topic}多選調查（可複選）",
                "options_template": ["選項A", "選項B", "選項C", "選項D"],
                "default_duration": 180,
                "default_is_multi": True,
                "default_anonymous": False,
                "is_public": True,
            },
            # 活動安排模板
            {
                "name": "🗓️ 活動時間投票",
                "description": "用於選擇最適合的活動時間",
                "category": "schedule",
                "title_template": "🗓️ {event_name}最佳時間投票",
                "options_template": [
                    "週六上午 (09:00-12:00)",
                    "週六下午 (14:00-17:00)",
                    "週日上午 (09:00-12:00)",
                    "週日下午 (14:00-17:00)",
                ],
                "default_duration": 240,
                "default_is_multi": True,
                "default_anonymous": False,
                "is_public": True,
            },
            {
                "name": "📅 會議時段選擇",
                "description": "選擇最佳會議時間",
                "category": "schedule",
                "title_template": "📅 {meeting_name}時間安排",
                "options_template": [
                    "週一 10:00",
                    "週二 10:00",
                    "週三 10:00",
                    "週四 10:00",
                    "週五 10:00",
                ],
                "default_duration": 120,
                "default_is_multi": True,
                "default_anonymous": False,
                "is_public": True,
            },
            # 聚餐選擇模板
            {
                "name": "🍕 聚餐地點投票",
                "description": "選擇聚餐地點的模板",
                "category": "food",
                "title_template": "🍕 {occasion}聚餐地點選擇",
                "options_template": [
                    "🍔 漢堡店",
                    "🍕 披薩店",
                    "🍜 拉麵店",
                    "🍱 便當店",
                    "🥘 火鍋店",
                ],
                "default_duration": 180,
                "default_is_multi": False,
                "default_anonymous": False,
                "is_public": True,
            },
            {
                "name": "🥤 飲料選擇",
                "description": "團購飲料時的選擇模板",
                "category": "food",
                "title_template": "🥤 {event}飲料團購",
                "options_template": [
                    "🧋 珍珠奶茶",
                    "☕ 咖啡",
                    "🥤 汽水",
                    "🧃 果汁",
                    "🍵 茶類",
                ],
                "default_duration": 60,
                "default_is_multi": True,
                "default_anonymous": False,
                "is_public": True,
            },
            # 評分投票模板
            {
                "name": "⭐ 滿意度調查",
                "description": "1-5星評分調查模板",
                "category": "rating",
                "title_template": "⭐ {subject}滿意度評分",
                "options_template": [
                    "⭐ 1星 - 非常不滿意",
                    "⭐⭐ 2星 - 不滿意",
                    "⭐⭐⭐ 3星 - 普通",
                    "⭐⭐⭐⭐ 4星 - 滿意",
                    "⭐⭐⭐⭐⭐ 5星 - 非常滿意",
                ],
                "default_duration": 240,
                "default_is_multi": False,
                "default_anonymous": True,
                "is_public": True,
            },
            # 遊戲選擇模板
            {
                "name": "🎮 遊戲選擇投票",
                "description": "選擇要一起玩的遊戲",
                "category": "game",
                "title_template": "🎮 今晚一起玩什麼遊戲？",
                "options_template": [
                    "🎯 Among Us",
                    "🏰 Minecraft",
                    "🎲 狼人殺",
                    "🏆 LOL",
                    "🔫 Valorant",
                ],
                "default_duration": 30,
                "default_is_multi": False,
                "default_anonymous": False,
                "is_public": True,
            },
            {
                "name": "🏆 電競比賽預測",
                "description": "預測電競比賽結果",
                "category": "game",
                "title_template": "🏆 {match_name}比賽結果預測",
                "options_template": ["🔥 A隊勝利", "⚔️ B隊勝利", "🤝 平局"],
                "default_duration": 60,
                "default_is_multi": False,
                "default_anonymous": False,
                "is_public": True,
            },
        ]

    async def initialize_predefined_templates(self):
        """初始化預定義模板（系統啟動時執行）"""
        try:
            # 先初始化資料表
            await vote_template_dao.initialize_tables()

            # 檢查是否已經初始化過
            existing_templates = (
                await vote_template_dao.get_templates_by_category("poll")
            )
            if existing_templates:
                logger.info("預定義模板已存在，跳過初始化")
                return

            # 創建預定義模板
            created_count = 0
            for template_data in self.predefined_templates:
                template_data["creator_id"] = 0  # 系統創建
                template_data["guild_id"] = None  # 全域模板

                template_id = await vote_template_dao.create_template(
                    template_data
                )
                if template_id:
                    created_count += 1
                    logger.info(
                        f"創建預定義模板: {template_data['name']} (ID: {template_id})"
                    )

            logger.info(f"成功創建 {created_count} 個預定義投票模板")

        except Exception as e:
            logger.error(f"初始化預定義模板失敗: {e}")

    async def create_custom_template(
        self, template_data: Dict[str, Any]
    ) -> Optional[int]:
        """創建自定義模板"""
        try:
            # 驗證必要欄位
            required_fields = [
                "name",
                "title_template",
                "options_template",
                "creator_id",
            ]
            for field in required_fields:
                if field not in template_data:
                    logger.error(f"創建模板失敗: 缺少必要欄位 {field}")
                    return None

            # 設定預設值
            template_data.setdefault("category", "custom")
            template_data.setdefault("is_public", False)
            template_data.setdefault("default_duration", 60)
            template_data.setdefault("default_is_multi", False)
            template_data.setdefault("default_anonymous", False)

            return await vote_template_dao.create_template(template_data)

        except Exception as e:
            logger.error(f"創建自定義模板失敗: {e}")
            return None

    async def apply_template(
        self, template_id: int, custom_values: Optional[Dict[str, str]] = None
    ) -> Optional[Dict[str, Any]]:
        """應用模板，生成投票配置"""
        try:
            template = await vote_template_dao.get_template_by_id(template_id)
            if not template:
                logger.error(f"找不到模板: ID={template_id}")
                return None

            # 增加使用次數
            await vote_template_dao.increment_usage_count(template_id)

            # 處理模板變數替換
            title = template["title_template"]
            options = template["options_template"].copy()

            if custom_values:
                # 替換標題中的變數
                for key, value in custom_values.items():
                    title = title.replace(f"{{{key}}}", value)

                # 替換選項中的變數
                for i, option in enumerate(options):
                    for key, value in custom_values.items():
                        options[i] = option.replace(f"{{{key}}}", value)

            return {
                "template_id": template_id,
                "template_name": template["name"],
                "title": title,
                "options": options,
                "duration": template["default_duration"],
                "is_multi": template["default_is_multi"],
                "anonymous": template["default_anonymous"],
                "category": template["category"],
            }

        except Exception as e:
            logger.error(f"應用模板失敗: {e}")
            return None

    async def get_templates_by_category(
        self,
        category: str,
        guild_id: Optional[int] = None,
        user_id: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """根據類別取得模板"""
        return await vote_template_dao.get_templates_by_category(
            category, guild_id, user_id
        )

    async def get_all_categories(self) -> List[Dict[str, str]]:
        """取得所有模板類別"""
        return [
            {"value": "poll", "label": "📊 民意調查", "emoji": "📊"},
            {"value": "schedule", "label": "🗓️ 活動安排", "emoji": "🗓️"},
            {"value": "food", "label": "🍕 聚餐選擇", "emoji": "🍕"},
            {"value": "rating", "label": "⭐ 評分投票", "emoji": "⭐"},
            {"value": "game", "label": "🎮 遊戲選擇", "emoji": "🎮"},
            {"value": "custom", "label": "🛠️ 自定義", "emoji": "🛠️"},
        ]

    async def search_templates(
        self,
        query: str,
        guild_id: Optional[int] = None,
        user_id: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """搜尋模板"""
        try:
            all_templates = []
            categories = [
                "poll",
                "schedule",
                "food",
                "rating",
                "game",
                "custom",
            ]

            for category in categories:
                templates = await self.get_templates_by_category(
                    category, guild_id, user_id
                )
                all_templates.extend(templates)

            # 簡單的關鍵字搜尋
            query_lower = query.lower()
            filtered_templates = []

            for template in all_templates:
                if (
                    query_lower in template["name"].lower()
                    or query_lower in template.get("description", "").lower()
                    or any(
                        query_lower in tag.lower() for tag in template["tags"]
                    )
                ):
                    filtered_templates.append(template)

            # 按使用次數排序
            filtered_templates.sort(
                key=lambda x: x["usage_count"], reverse=True
            )
            return filtered_templates[:10]  # 限制結果數量

        except Exception as e:
            logger.error(f"搜尋模板失敗: {e}")
            return []


# 建立全域實例
vote_template_manager = VoteTemplateManager()
