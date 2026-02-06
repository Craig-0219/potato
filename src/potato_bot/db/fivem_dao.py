# bot/db/fivem_dao.py
"""
FiveM 狀態設定資料存取
"""

from typing import Any, Dict

import aiomysql

from potato_shared.logger import logger

from .base_dao import BaseDAO


class FiveMDAO(BaseDAO):
    """FiveM 狀態設定 DAO"""

    def __init__(self):
        super().__init__(table_name="fivem_settings")

    async def _initialize(self):
        logger.info("✅ FiveMDAO 初始化完成")

    async def get_fivem_settings(self, guild_id: int) -> Dict[str, Any]:
        """取得 FiveM 狀態設定"""
        try:
            async with self.db.connection() as conn:
                async with conn.cursor(aiomysql.DictCursor) as cursor:
                    query = "SELECT * FROM fivem_settings WHERE guild_id = %s"
                    await cursor.execute(query, (guild_id,))
                    result = await cursor.fetchone()

                    if result:
                        result["status_channel_id"] = int(result.get("status_channel_id") or 0)
                        result["exists"] = True
                        return result

                    return {
                        "guild_id": guild_id,
                        "info_url": None,
                        "players_url": None,
                        "status_channel_id": 0,
                        "exists": False,
                    }
        except Exception as e:
            logger.error(f"取得 FiveM 設定失敗: {e}")
            return {
                "guild_id": guild_id,
                "info_url": None,
                "players_url": None,
                "status_channel_id": 0,
                "exists": False,
            }

    async def update_fivem_settings(self, guild_id: int, settings: Dict[str, Any]) -> bool:
        """更新 FiveM 狀態設定"""
        try:
            async with self.db.connection() as conn:
                async with conn.cursor() as cursor:
                    query = """
                    INSERT INTO fivem_settings (
                        guild_id, info_url, players_url, status_channel_id
                    ) VALUES (%s, %s, %s, %s)
                    ON DUPLICATE KEY UPDATE
                        info_url = VALUES(info_url),
                        players_url = VALUES(players_url),
                        status_channel_id = VALUES(status_channel_id),
                        updated_at = CURRENT_TIMESTAMP
                    """
                    await cursor.execute(
                        query,
                        (
                            guild_id,
                            settings.get("info_url"),
                            settings.get("players_url"),
                            settings.get("status_channel_id") or 0,
                        ),
                    )
                    await conn.commit()
                    return True
        except Exception as e:
            logger.error(f"更新 FiveM 設定失敗: {e}")
            return False
