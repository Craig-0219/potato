# bot/db/vote_template_dao.py
"""
投票模板系統資料存取層
提供投票模板的儲存、查詢、管理功能
"""

import json
from typing import Any, Dict, List, Optional

from potato_bot.db.pool import db_pool
from potato_shared.logger import logger


class VoteTemplateDAO:
    """投票模板資料存取層"""

    def __init__(self):
        self.db = db_pool

    async def initialize_tables(self):
        """初始化投票模板相關資料表"""
        try:
            async with self.db.connection() as conn:
                async with conn.cursor() as cursor:
                    # 創建投票模板主表
                    await cursor.execute(
                        """
                        CREATE TABLE IF NOT EXISTS vote_templates (
                            id INT AUTO_INCREMENT PRIMARY KEY,
                            name VARCHAR(100) NOT NULL COMMENT '模板名稱',
                            description TEXT COMMENT '模板描述',
                            category ENUM('poll', 'schedule', 'food', 'rating', 'game', 'custom') NOT NULL DEFAULT 'custom' COMMENT '模板類別',
                            guild_id BIGINT COMMENT '所屬群組ID，NULL表示全域模板',
                            creator_id BIGINT NOT NULL COMMENT '創建者ID',
                            is_public BOOLEAN DEFAULT FALSE COMMENT '是否公開模板',
                            title_template VARCHAR(200) NOT NULL COMMENT '標題模板',
                            options_template JSON NOT NULL COMMENT '選項模板',
                            default_duration INT DEFAULT 60 COMMENT '預設持續時間（分鐘）',
                            default_is_multi BOOLEAN DEFAULT FALSE COMMENT '預設是否多選',
                            default_anonymous BOOLEAN DEFAULT FALSE COMMENT '預設是否匿名',
                            usage_count INT DEFAULT 0 COMMENT '使用次數',
                            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                            INDEX idx_guild_category (guild_id, category),
                            INDEX idx_creator (creator_id),
                            INDEX idx_public (is_public)
                        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
                        COMMENT='投票模板表'
                    """
                    )

                    # 創建模板標籤表
                    await cursor.execute(
                        """
                        CREATE TABLE IF NOT EXISTS vote_template_tags (
                            id INT AUTO_INCREMENT PRIMARY KEY,
                            template_id INT NOT NULL,
                            tag VARCHAR(50) NOT NULL COMMENT '標籤名稱',
                            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                            FOREIGN KEY (template_id) REFERENCES vote_templates(id) ON DELETE CASCADE,
                            UNIQUE KEY unique_template_tag (template_id, tag),
                            INDEX idx_tag (tag)
                        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
                        COMMENT='投票模板標籤表'
                    """
                    )

                    # 創建模板收藏表
                    await cursor.execute(
                        """
                        CREATE TABLE IF NOT EXISTS vote_template_favorites (
                            id INT AUTO_INCREMENT PRIMARY KEY,
                            template_id INT NOT NULL,
                            user_id BIGINT NOT NULL COMMENT '收藏用戶ID',
                            guild_id BIGINT NOT NULL COMMENT '群組ID',
                            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                            FOREIGN KEY (template_id) REFERENCES vote_templates(id) ON DELETE CASCADE,
                            UNIQUE KEY unique_user_template (user_id, template_id),
                            INDEX idx_user_guild (user_id, guild_id)
                        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
                        COMMENT='投票模板收藏表'
                    """
                    )

                    await conn.commit()
                    logger.info("投票模板資料表初始化完成")

        except Exception as e:
            logger.error(f"初始化投票模板資料表失敗: {e}")
            raise

    async def create_template(self, template_data: Dict[str, Any]) -> Optional[int]:
        """創建投票模板"""
        try:
            async with self.db.connection() as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute(
                        """
                        INSERT INTO vote_templates
                        (name, description, category, guild_id, creator_id, is_public,
                         title_template, options_template, default_duration,
                         default_is_multi, default_anonymous)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                        (
                            template_data["name"],
                            template_data.get("description"),
                            template_data["category"],
                            template_data.get("guild_id"),
                            template_data["creator_id"],
                            template_data.get("is_public", False),
                            template_data["title_template"],
                            json.dumps(template_data["options_template"]),
                            template_data.get("default_duration", 60),
                            template_data.get("default_is_multi", False),
                            template_data.get("default_anonymous", False),
                        ),
                    )

                    template_id = cursor.lastrowid
                    await conn.commit()

                    logger.info(f"創建投票模板成功: ID={template_id}")
                    return template_id

        except Exception as e:
            logger.error(f"創建投票模板失敗: {e}")
            return None

    async def get_templates_by_category(
        self,
        category: str,
        guild_id: Optional[int] = None,
        user_id: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """根據類別取得模板列表"""
        try:
            async with self.db.connection() as conn:
                async with conn.cursor() as cursor:
                    # 構建查詢條件
                    conditions = ["category = %s"]
                    params = [category]

                    if guild_id:
                        conditions.append("(guild_id = %s OR guild_id IS NULL OR is_public = TRUE)")
                        params.append(guild_id)
                    else:
                        conditions.append("guild_id IS NULL")

                    query = f"""
                        SELECT t.*,
                               (SELECT COUNT(*) FROM vote_template_favorites f
                                WHERE f.template_id = t.id AND f.user_id = %s) as is_favorited,
                               (SELECT GROUP_CONCAT(tag) FROM vote_template_tags vtt
                                WHERE vtt.template_id = t.id) as tags
                        FROM vote_templates t
                        WHERE {' AND '.join(conditions)}
                        ORDER BY usage_count DESC, created_at DESC
                    """

                    params.append(user_id or 0)
                    await cursor.execute(query, params)
                    rows = await cursor.fetchall()

                    templates = []
                    for row in rows:
                        template = {
                            "id": row[0],
                            "name": row[1],
                            "description": row[2],
                            "category": row[3],
                            "guild_id": row[4],
                            "creator_id": row[5],
                            "is_public": bool(row[6]),
                            "title_template": row[7],
                            "options_template": (json.loads(row[8]) if row[8] else []),
                            "default_duration": row[9],
                            "default_is_multi": bool(row[10]),
                            "default_anonymous": bool(row[11]),
                            "usage_count": row[12],
                            "created_at": row[13],
                            "updated_at": row[14],
                            "is_favorited": bool(row[15]),
                            "tags": row[16].split(",") if row[16] else [],
                        }
                        templates.append(template)

                    return templates

        except Exception as e:
            logger.error(f"取得模板列表失敗: {e}")
            return []

    async def get_template_by_id(self, template_id: int) -> Optional[Dict[str, Any]]:
        """根據ID取得模板詳細資訊"""
        try:
            async with self.db.connection() as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute(
                        """
                        SELECT t.*,
                               (SELECT GROUP_CONCAT(tag) FROM vote_template_tags vtt
                                WHERE vtt.template_id = t.id) as tags
                        FROM vote_templates t
                        WHERE t.id = %s
                    """,
                        (template_id,),
                    )

                    row = await cursor.fetchone()
                    if not row:
                        return None

                    return {
                        "id": row[0],
                        "name": row[1],
                        "description": row[2],
                        "category": row[3],
                        "guild_id": row[4],
                        "creator_id": row[5],
                        "is_public": bool(row[6]),
                        "title_template": row[7],
                        "options_template": (json.loads(row[8]) if row[8] else []),
                        "default_duration": row[9],
                        "default_is_multi": bool(row[10]),
                        "default_anonymous": bool(row[11]),
                        "usage_count": row[12],
                        "created_at": row[13],
                        "updated_at": row[14],
                        "tags": row[15].split(",") if row[15] else [],
                    }

        except Exception as e:
            logger.error(f"取得模板詳細資訊失敗: {e}")
            return None

    async def increment_usage_count(self, template_id: int):
        """增加模板使用次數"""
        try:
            async with self.db.connection() as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute(
                        """
                        UPDATE vote_templates
                        SET usage_count = usage_count + 1
                        WHERE id = %s
                    """,
                        (template_id,),
                    )
                    await conn.commit()

        except Exception as e:
            logger.error(f"更新模板使用次數失敗: {e}")

    async def add_template_favorite(self, template_id: int, user_id: int, guild_id: int) -> bool:
        """加入模板收藏"""
        try:
            async with self.db.connection() as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute(
                        """
                        INSERT IGNORE INTO vote_template_favorites
                        (template_id, user_id, guild_id)
                        VALUES (%s, %s, %s)
                    """,
                        (template_id, user_id, guild_id),
                    )

                    affected = cursor.rowcount
                    await conn.commit()

                    return affected > 0

        except Exception as e:
            logger.error(f"加入模板收藏失敗: {e}")
            return False

    async def remove_template_favorite(self, template_id: int, user_id: int) -> bool:
        """移除模板收藏"""
        try:
            async with self.db.connection() as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute(
                        """
                        DELETE FROM vote_template_favorites
                        WHERE template_id = %s AND user_id = %s
                    """,
                        (template_id, user_id),
                    )

                    affected = cursor.rowcount
                    await conn.commit()

                    return affected > 0

        except Exception as e:
            logger.error(f"移除模板收藏失敗: {e}")
            return False

    async def get_user_favorite_templates(
        self, user_id: int, guild_id: int
    ) -> List[Dict[str, Any]]:
        """取得用戶收藏的模板"""
        try:
            async with self.db.connection() as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute(
                        """
                        SELECT t.*,
                               (SELECT GROUP_CONCAT(tag) FROM vote_template_tags vtt
                                WHERE vtt.template_id = t.id) as tags
                        FROM vote_templates t
                        INNER JOIN vote_template_favorites f ON t.id = f.template_id
                        WHERE f.user_id = %s AND f.guild_id = %s
                        ORDER BY f.created_at DESC
                    """,
                        (user_id, guild_id),
                    )

                    rows = await cursor.fetchall()
                    templates = []

                    for row in rows:
                        template = {
                            "id": row[0],
                            "name": row[1],
                            "description": row[2],
                            "category": row[3],
                            "guild_id": row[4],
                            "creator_id": row[5],
                            "is_public": bool(row[6]),
                            "title_template": row[7],
                            "options_template": (json.loads(row[8]) if row[8] else []),
                            "default_duration": row[9],
                            "default_is_multi": bool(row[10]),
                            "default_anonymous": bool(row[11]),
                            "usage_count": row[12],
                            "created_at": row[13],
                            "updated_at": row[14],
                            "tags": row[15].split(",") if row[15] else [],
                        }
                        templates.append(template)

                    return templates

        except Exception as e:
            logger.error(f"取得用戶收藏模板失敗: {e}")
            return []


# 建立全域實例
vote_template_dao = VoteTemplateDAO()
