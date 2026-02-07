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
        try:
            async with self.db.connection() as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute("SHOW COLUMNS FROM music_settings LIKE 'lavalink_host'")
                    exists = await cursor.fetchone()
                    if not exists:
                        await cursor.execute(
                            "ALTER TABLE music_settings ADD COLUMN lavalink_host TEXT NULL COMMENT 'Lavalink 主機' AFTER require_role_to_use"
                        )
                        await conn.commit()
                        logger.info("✅ 已補齊 music_settings.lavalink_host 欄位")

                    await cursor.execute("SHOW COLUMNS FROM music_settings LIKE 'lavalink_port'")
                    exists = await cursor.fetchone()
                    if not exists:
                        await cursor.execute(
                            "ALTER TABLE music_settings ADD COLUMN lavalink_port INT NULL COMMENT 'Lavalink 連接埠' AFTER lavalink_host"
                        )
                        await conn.commit()
                        logger.info("✅ 已補齊 music_settings.lavalink_port 欄位")

                    await cursor.execute("SHOW COLUMNS FROM music_settings LIKE 'lavalink_password'")
                    exists = await cursor.fetchone()
                    if not exists:
                        await cursor.execute(
                            "ALTER TABLE music_settings ADD COLUMN lavalink_password TEXT NULL COMMENT 'Lavalink 密碼' AFTER lavalink_port"
                        )
                        await conn.commit()
                        logger.info("✅ 已補齊 music_settings.lavalink_password 欄位")

                    await cursor.execute("SHOW COLUMNS FROM music_settings LIKE 'lavalink_secure'")
                    exists = await cursor.fetchone()
                    if not exists:
                        await cursor.execute(
                            "ALTER TABLE music_settings ADD COLUMN lavalink_secure BOOLEAN DEFAULT FALSE COMMENT 'Lavalink HTTPS' AFTER lavalink_password"
                        )
                        await conn.commit()
                        logger.info("✅ 已補齊 music_settings.lavalink_secure 欄位")

                    await cursor.execute("SHOW COLUMNS FROM music_settings LIKE 'lavalink_uri'")
                    exists = await cursor.fetchone()
                    if not exists:
                        await cursor.execute(
                            "ALTER TABLE music_settings ADD COLUMN lavalink_uri TEXT NULL COMMENT 'Lavalink URI' AFTER lavalink_secure"
                        )
                        await conn.commit()
                        logger.info("✅ 已補齊 music_settings.lavalink_uri 欄位")
        except Exception as exc:
            logger.warning("MusicDAO 初始化檢查欄位失敗: %s", exc)

        logger.info("✅ MusicDAO 初始化完成")

    async def get_music_settings(self, guild_id: int) -> Dict[str, Any]:
        """取得音樂設定"""
        await self._ensure_initialized()
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
                        result["lavalink_host"] = result.get("lavalink_host")
                        result["lavalink_port"] = (
                            int(result.get("lavalink_port"))
                            if result.get("lavalink_port") is not None
                            else None
                        )
                        result["lavalink_password"] = result.get("lavalink_password")
                        if result.get("lavalink_secure") is None:
                            result["lavalink_secure"] = None
                        else:
                            result["lavalink_secure"] = bool(result.get("lavalink_secure"))
                        result["lavalink_uri"] = result.get("lavalink_uri")
                        return result

                    return {
                        "guild_id": guild_id,
                        "allowed_role_ids": [],
                        "require_role_to_use": False,
                        "lavalink_host": None,
                        "lavalink_port": None,
                        "lavalink_password": None,
                        "lavalink_secure": None,
                        "lavalink_uri": None,
                    }
        except Exception as e:
            logger.error(f"取得音樂設定失敗: {e}")
            return {
                "guild_id": guild_id,
                "allowed_role_ids": [],
                "require_role_to_use": False,
                "lavalink_host": None,
                "lavalink_port": None,
                "lavalink_password": None,
                "lavalink_secure": None,
                "lavalink_uri": None,
            }

    async def update_music_settings(self, guild_id: int, settings: Dict[str, Any]) -> bool:
        """更新音樂設定"""
        await self._ensure_initialized()
        try:
            async with self.db.connection() as conn:
                async with conn.cursor() as cursor:
                    query = """
                    INSERT INTO music_settings (
                        guild_id,
                        allowed_role_ids,
                        require_role_to_use,
                        lavalink_host,
                        lavalink_port,
                        lavalink_password,
                        lavalink_secure,
                        lavalink_uri
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    ON DUPLICATE KEY UPDATE
                        allowed_role_ids = VALUES(allowed_role_ids),
                        require_role_to_use = VALUES(require_role_to_use),
                        lavalink_host = VALUES(lavalink_host),
                        lavalink_port = VALUES(lavalink_port),
                        lavalink_password = VALUES(lavalink_password),
                        lavalink_secure = VALUES(lavalink_secure),
                        lavalink_uri = VALUES(lavalink_uri),
                        updated_at = CURRENT_TIMESTAMP
                    """
                    await cursor.execute(
                        query,
                        (
                            guild_id,
                            json.dumps(settings.get("allowed_role_ids", [])),
                            settings.get("require_role_to_use", False),
                            settings.get("lavalink_host"),
                            settings.get("lavalink_port"),
                            settings.get("lavalink_password"),
                            settings.get("lavalink_secure"),
                            settings.get("lavalink_uri"),
                        ),
                    )
                    await conn.commit()
                    return True
        except Exception as e:
            logger.error(f"更新音樂設定失敗: {e}")
            return False
