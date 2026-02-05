# bot/db/music_dao.py
"""
音樂系統設定資料存取
"""

import json
from typing import Any, Dict

import aiomysql

from potato_shared.logger import logger

from .base_dao import BaseDAO


class MusicDAO(BaseDAO):
    """音樂系統設定 DAO"""

    def __init__(self):
        super().__init__(table_name="music_settings")

    async def _initialize(self):
        logger.info("✅ MusicDAO 初始化完成")

    async def get_music_settings(self, guild_id: int) -> Dict[str, Any]:
        """取得音樂設定"""
        try:
            async with self.db.connection() as conn:
                async with conn.cursor(aiomysql.DictCursor) as cursor:
                    query = "SELECT * FROM music_settings WHERE guild_id = %s"
                    await cursor.execute(query, (guild_id,))
                    result = await cursor.fetchone()

                    if result:
                        if result.get("allowed_role_ids"):
                            result["allowed_role_ids"] = json.loads(result["allowed_role_ids"])
                        else:
                            result["allowed_role_ids"] = []
                        return result

                    return {
                        "guild_id": guild_id,
                        "allowed_role_ids": [],
                        "require_role_to_use": False,
                    }
        except Exception as e:
            logger.error(f"取得音樂設定失敗: {e}")
            return {
                "guild_id": guild_id,
                "allowed_role_ids": [],
                "require_role_to_use": False,
            }

    async def update_music_settings(self, guild_id: int, settings: Dict[str, Any]) -> bool:
        """更新音樂設定"""
        try:
            async with self.db.connection() as conn:
                async with conn.cursor() as cursor:
                    query = """
                    INSERT INTO music_settings (
                        guild_id, allowed_role_ids, require_role_to_use
                    ) VALUES (%s, %s, %s)
                    ON DUPLICATE KEY UPDATE
                        allowed_role_ids = VALUES(allowed_role_ids),
                        require_role_to_use = VALUES(require_role_to_use),
                        updated_at = CURRENT_TIMESTAMP
                    """
                    await cursor.execute(
                        query,
                        (
                            guild_id,
                            json.dumps(settings.get("allowed_role_ids", [])),
                            settings.get("require_role_to_use", False),
                        ),
                    )
                    await conn.commit()
                    return True
        except Exception as e:
            logger.error(f"更新音樂設定失敗: {e}")
            return False
