# bot/db/fivem_dao.py
"""
FiveM 狀態設定資料存取
"""

import json
from typing import Any, Dict

import aiomysql

from potato_shared.logger import logger

from .base_dao import BaseDAO


class FiveMDAO(BaseDAO):
    """FiveM 狀態設定 DAO"""

    def __init__(self):
        super().__init__(table_name="fivem_settings")

    async def _initialize(self):
        try:
            async with self.db.connection() as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute("SHOW COLUMNS FROM fivem_settings LIKE 'alert_role_ids'")
                    exists = await cursor.fetchone()
                    if not exists:
                        await cursor.execute(
                            "ALTER TABLE fivem_settings ADD COLUMN alert_role_ids JSON NULL COMMENT '異常通知身分組' AFTER status_channel_id"
                        )
                        await conn.commit()
                        logger.info("✅ 已補齊 fivem_settings.alert_role_ids 欄位")

                    await cursor.execute("SHOW COLUMNS FROM fivem_settings LIKE 'dm_role_ids'")
                    exists = await cursor.fetchone()
                    if not exists:
                        await cursor.execute(
                            "ALTER TABLE fivem_settings ADD COLUMN dm_role_ids JSON NULL COMMENT 'DM 通知身分組' AFTER alert_role_ids"
                        )
                        await conn.commit()
                        logger.info("✅ 已補齊 fivem_settings.dm_role_ids 欄位")

                    await cursor.execute("SHOW COLUMNS FROM fivem_settings LIKE 'panel_message_id'")
                    exists = await cursor.fetchone()
                    if not exists:
                        await cursor.execute(
                            "ALTER TABLE fivem_settings ADD COLUMN panel_message_id BIGINT NULL COMMENT '狀態面板訊息ID' AFTER dm_role_ids"
                        )
                        await conn.commit()
                        logger.info("✅ 已補齊 fivem_settings.panel_message_id 欄位")

                    await cursor.execute("SHOW COLUMNS FROM fivem_settings LIKE 'server_link'")
                    exists = await cursor.fetchone()
                    if not exists:
                        await cursor.execute(
                            "ALTER TABLE fivem_settings ADD COLUMN server_link TEXT NULL COMMENT '伺服器連結' AFTER panel_message_id"
                        )
                        await conn.commit()
                        logger.info("✅ 已補齊 fivem_settings.server_link 欄位")

                    await cursor.execute("SHOW COLUMNS FROM fivem_settings LIKE 'status_image_url'")
                    exists = await cursor.fetchone()
                    if not exists:
                        await cursor.execute(
                            "ALTER TABLE fivem_settings ADD COLUMN status_image_url TEXT NULL COMMENT '狀態面板圖片' AFTER server_link"
                        )
                        await conn.commit()
                        logger.info("✅ 已補齊 fivem_settings.status_image_url 欄位")
        except Exception as exc:
            logger.warning("FiveMDAO 初始化檢查欄位失敗: %s", exc)

        logger.info("✅ FiveMDAO 初始化完成")

    async def get_fivem_settings(self, guild_id: int) -> Dict[str, Any]:
        """取得 FiveM 狀態設定"""
        await self._ensure_initialized()
        try:
            async with self.db.connection() as conn:
                async with conn.cursor(aiomysql.DictCursor) as cursor:
                    query = "SELECT * FROM fivem_settings WHERE guild_id = %s"
                    await cursor.execute(query, (guild_id,))
                    result = await cursor.fetchone()

                    if result:
                        result["status_channel_id"] = int(result.get("status_channel_id") or 0)
                        raw_alert_roles = result.get("alert_role_ids")
                        if isinstance(raw_alert_roles, str) and raw_alert_roles:
                            result["alert_role_ids"] = json.loads(raw_alert_roles)
                        elif isinstance(raw_alert_roles, list):
                            result["alert_role_ids"] = raw_alert_roles
                        else:
                            result["alert_role_ids"] = []
                        raw_dm_roles = result.get("dm_role_ids")
                        if isinstance(raw_dm_roles, str) and raw_dm_roles:
                            result["dm_role_ids"] = json.loads(raw_dm_roles)
                        elif isinstance(raw_dm_roles, list):
                            result["dm_role_ids"] = raw_dm_roles
                        else:
                            result["dm_role_ids"] = []
                        result["panel_message_id"] = int(result.get("panel_message_id") or 0)
                        result["server_link"] = result.get("server_link")
                        result["status_image_url"] = result.get("status_image_url")
                        result["exists"] = True
                        return result

                    return {
                        "guild_id": guild_id,
                        "info_url": None,
                        "players_url": None,
                        "status_channel_id": 0,
                        "alert_role_ids": [],
                        "dm_role_ids": [],
                        "panel_message_id": 0,
                        "server_link": None,
                        "status_image_url": None,
                        "exists": False,
                    }
        except Exception as e:
            logger.error(f"取得 FiveM 設定失敗: {e}")
            return {
                "guild_id": guild_id,
                "info_url": None,
                "players_url": None,
                "status_channel_id": 0,
                "alert_role_ids": [],
                "dm_role_ids": [],
                "panel_message_id": 0,
                "server_link": None,
                "status_image_url": None,
                "exists": False,
            }

    async def update_fivem_settings(self, guild_id: int, settings: Dict[str, Any]) -> bool:
        """更新 FiveM 狀態設定"""
        await self._ensure_initialized()
        try:
            async with self.db.connection() as conn:
                async with conn.cursor() as cursor:
                    query = """
                    INSERT INTO fivem_settings (
                        guild_id, info_url, players_url, status_channel_id, alert_role_ids, dm_role_ids, panel_message_id, server_link, status_image_url
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON DUPLICATE KEY UPDATE
                        info_url = VALUES(info_url),
                        players_url = VALUES(players_url),
                        status_channel_id = VALUES(status_channel_id),
                        alert_role_ids = VALUES(alert_role_ids),
                        dm_role_ids = VALUES(dm_role_ids),
                        panel_message_id = VALUES(panel_message_id),
                        server_link = VALUES(server_link),
                        status_image_url = VALUES(status_image_url),
                        updated_at = CURRENT_TIMESTAMP
                    """
                    await cursor.execute(
                        query,
                        (
                            guild_id,
                            settings.get("info_url"),
                            settings.get("players_url"),
                            settings.get("status_channel_id") or 0,
                            json.dumps(settings.get("alert_role_ids", [])),
                            json.dumps(settings.get("dm_role_ids", [])),
                            settings.get("panel_message_id") or 0,
                            settings.get("server_link"),
                            settings.get("status_image_url"),
                        ),
                    )
                    await conn.commit()
                    return True
        except Exception as e:
            logger.error(f"更新 FiveM 設定失敗: {e}")
            return False

    async def update_panel_message_id(self, guild_id: int, message_id: int) -> bool:
        """更新狀態面板訊息ID"""
        await self._ensure_initialized()
        try:
            async with self.db.connection() as conn:
                async with conn.cursor() as cursor:
                    query = """
                    INSERT INTO fivem_settings (guild_id, panel_message_id)
                    VALUES (%s, %s)
                    ON DUPLICATE KEY UPDATE
                        panel_message_id = VALUES(panel_message_id),
                        updated_at = CURRENT_TIMESTAMP
                    """
                    await cursor.execute(query, (guild_id, message_id))
                    await conn.commit()
                    return True
        except Exception as e:
            logger.error(f"更新 FiveM 面板訊息ID失敗: {e}")
            return False
