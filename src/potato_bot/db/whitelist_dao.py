"""
Whitelist DAO
管理入境審核申請與設定
"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from potato_bot.db.pool import db_pool
from potato_bot.db.base_dao import BaseDAO
from potato_shared.logger import logger


class WhitelistDAO(BaseDAO):
    """入境審核資料存取"""

    def __init__(self):
        super().__init__(table_name="whitelist_applications")
        self._tables_initialized = False

    async def _initialize(self):
        if self._tables_initialized:
            return
        await self._ensure_tables()
        self._tables_initialized = True

    async def _ensure_tables(self) -> None:
        """建立所需資料表"""
        try:
            async with db_pool.connection() as conn:
                async with conn.cursor() as cursor:
                    # 申請表
                    await cursor.execute(
                        """
                        CREATE TABLE IF NOT EXISTS whitelist_applications (
                            id BIGINT AUTO_INCREMENT PRIMARY KEY,
                            guild_id BIGINT NOT NULL,
                            user_id BIGINT NOT NULL,
                            username VARCHAR(255),
                            answers_json JSON,
                            status VARCHAR(20) DEFAULT 'PENDING',
                            reviewer_id BIGINT NULL,
                            reviewer_note TEXT NULL,
                            review_message_id BIGINT NULL,
                            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                            reviewed_at TIMESTAMP NULL,
                            INDEX idx_guild_user_status (guild_id, user_id, status),
                            INDEX idx_status (status)
                        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
                        """
                    )

                    # 設定表
                    await cursor.execute(
                        """
                        CREATE TABLE IF NOT EXISTS whitelist_settings (
                            guild_id BIGINT PRIMARY KEY,
                            panel_channel_id BIGINT NULL,
                            review_channel_id BIGINT NULL,
                            result_channel_id BIGINT NULL,
                            role_newcomer_ids JSON NULL,
                            role_citizen_id BIGINT NULL,
                            role_staff_id BIGINT NULL,
                            nickname_role_id BIGINT NULL,
                            nickname_prefix VARCHAR(32) NULL,
                            panel_message_id BIGINT NULL,
                            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
                        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
                        """
                    )

                    # 向後相容：補齊暱稱設定欄位
                    await cursor.execute(
                        "SHOW COLUMNS FROM whitelist_settings LIKE 'role_newcomer_ids'"
                    )
                    column_exists = await cursor.fetchone()
                    if not column_exists:
                        await cursor.execute(
                            "ALTER TABLE whitelist_settings ADD COLUMN role_newcomer_ids JSON NULL AFTER result_channel_id"
                        )

                    # 向後相容：將舊 role_newcomer_id 轉移到 role_newcomer_ids 後移除
                    await cursor.execute(
                        "SHOW COLUMNS FROM whitelist_settings LIKE 'role_newcomer_id'"
                    )
                    old_column_exists = await cursor.fetchone()
                    if old_column_exists:
                        try:
                            await cursor.execute(
                                """
                                UPDATE whitelist_settings
                                SET role_newcomer_ids = JSON_ARRAY(role_newcomer_id)
                                WHERE role_newcomer_id IS NOT NULL
                                  AND (role_newcomer_ids IS NULL)
                                """
                            )
                            await cursor.execute(
                                "ALTER TABLE whitelist_settings DROP COLUMN role_newcomer_id"
                            )
                            logger.info("✅ 已移除舊欄位 role_newcomer_id")
                        except Exception as e:
                            logger.error(f"❌ 移除 role_newcomer_id 失敗: {e}")

                    await cursor.execute(
                        "SHOW COLUMNS FROM whitelist_settings LIKE 'nickname_role_id'"
                    )
                    column_exists = await cursor.fetchone()
                    if not column_exists:
                        await cursor.execute(
                            "ALTER TABLE whitelist_settings ADD COLUMN nickname_role_id BIGINT NULL AFTER role_staff_id"
                        )

                    await cursor.execute(
                        "SHOW COLUMNS FROM whitelist_settings LIKE 'nickname_prefix'"
                    )
                    column_exists = await cursor.fetchone()
                    if not column_exists:
                        await cursor.execute(
                            "ALTER TABLE whitelist_settings ADD COLUMN nickname_prefix VARCHAR(32) NULL AFTER nickname_role_id"
                        )

                    await conn.commit()
            logger.info("✅ whitelist 資料表檢查完成")
        except Exception as e:
            logger.error(f"❌ 建立 whitelist 資料表失敗: {e}")
            raise

    # --------- Applications ----------
    async def has_pending(self, guild_id: int, user_id: int) -> bool:
        await self._ensure_initialized()
        query = """
            SELECT 1 FROM whitelist_applications
            WHERE guild_id=%s AND user_id=%s AND status='PENDING'
            LIMIT 1
        """
        result = await self.execute_query(query, (guild_id, user_id), fetch_one=True)
        return bool(result)

    async def get_latest_application(
        self, guild_id: int, user_id: int, statuses: Optional[List[str]] = None
    ) -> Optional[Dict[str, Any]]:
        await self._ensure_initialized()
        if statuses:
            placeholders = ", ".join(["%s"] * len(statuses))
            query = f"""
                SELECT * FROM whitelist_applications
                WHERE guild_id=%s AND user_id=%s AND status IN ({placeholders})
                ORDER BY created_at DESC
                LIMIT 1
            """
            params = (guild_id, user_id, *statuses)
        else:
            query = """
                SELECT * FROM whitelist_applications
                WHERE guild_id=%s AND user_id=%s
                ORDER BY created_at DESC
                LIMIT 1
            """
            params = (guild_id, user_id)

        result = await self.execute_query(query, params, fetch_one=True, dictionary=True)
        return result

    async def create_application(
        self,
        guild_id: int,
        user_id: int,
        username: str,
        answers: Dict[str, Any],
    ) -> int:
        await self._ensure_initialized()
        async with db_pool.connection() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute(
                    """
                    INSERT INTO whitelist_applications
                    (guild_id, user_id, username, answers_json, status)
                    VALUES (%s, %s, %s, %s, 'PENDING')
                    """,
                    (guild_id, user_id, username, json.dumps(answers, ensure_ascii=False)),
                )
                await conn.commit()
                return cursor.lastrowid

    async def update_application(
        self, app_id: int, username: str, answers: Dict[str, Any]
    ) -> bool:
        await self._ensure_initialized()
        query = """
            UPDATE whitelist_applications
            SET username=%s, answers_json=%s,
                status='PENDING', reviewer_id=NULL, reviewer_note=NULL, reviewed_at=NULL
            WHERE id=%s
        """
        rows = await self.execute_query(
            query,
            (username, json.dumps(answers, ensure_ascii=False), app_id),
        )
        return rows > 0

    async def get_application(self, app_id: int) -> Optional[Dict[str, Any]]:
        await self._ensure_initialized()
        query = "SELECT * FROM whitelist_applications WHERE id=%s"
        result = await self.execute_query(query, (app_id,), fetch_one=True, dictionary=True)
        return result

    async def set_status(
        self,
        app_id: int,
        status: str,
        reviewer_id: int,
        note: Optional[str] = None,
    ) -> bool:
        await self._ensure_initialized()
        query = """
            UPDATE whitelist_applications
            SET status=%s, reviewer_id=%s, reviewer_note=%s, reviewed_at=CURRENT_TIMESTAMP
            WHERE id=%s AND status IN ('PENDING','NEED_MORE')
        """
        rows = await self.execute_query(query, (status, reviewer_id, note, app_id))
        return rows > 0

    async def set_review_message_id(self, app_id: int, message_id: int) -> None:
        await self._ensure_initialized()
        query = "UPDATE whitelist_applications SET review_message_id=%s WHERE id=%s"
        await self.execute_query(query, (message_id, app_id))

    async def list_pending_with_message(self) -> List[Dict[str, Any]]:
        await self._ensure_initialized()
        query = """
            SELECT id, guild_id, review_message_id
            FROM whitelist_applications
            WHERE status IN ('PENDING','NEED_MORE') AND review_message_id IS NOT NULL
        """
        rows = await self.execute_query(query, fetch_all=True, dictionary=True)
        return rows or []

    # --------- Settings ----------
    async def get_settings(self, guild_id: int) -> Dict[str, Any]:
        await self._ensure_initialized()
        query = "SELECT * FROM whitelist_settings WHERE guild_id=%s"
        result = await self.execute_query(query, (guild_id,), fetch_one=True, dictionary=True)
        return result or {}

    async def upsert_settings(self, guild_id: int, **settings) -> None:
        await self._ensure_initialized()
        keys = [
            "panel_channel_id",
            "review_channel_id",
            "result_channel_id",
            "role_newcomer_ids",
            "role_citizen_id",
            "role_staff_id",
            "nickname_role_id",
            "nickname_prefix",
            "panel_message_id",
        ]
        values = []
        for key in keys:
            value = settings.get(key)
            if key == "role_newcomer_ids" and value is not None:
                value = json.dumps(value, ensure_ascii=False)
            values.append(value)
        query = """
            INSERT INTO whitelist_settings (
                guild_id, panel_channel_id, review_channel_id, result_channel_id,
                role_newcomer_ids, role_citizen_id, role_staff_id,
                nickname_role_id, nickname_prefix, panel_message_id
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE
                panel_channel_id=VALUES(panel_channel_id),
                review_channel_id=VALUES(review_channel_id),
                result_channel_id=VALUES(result_channel_id),
                role_newcomer_ids=VALUES(role_newcomer_ids),
                role_citizen_id=VALUES(role_citizen_id),
                role_staff_id=VALUES(role_staff_id),
                nickname_role_id=VALUES(nickname_role_id),
                nickname_prefix=VALUES(nickname_prefix),
                panel_message_id=VALUES(panel_message_id)
        """
        await self.execute_query(query, (guild_id, *values))

    async def update_panel_message_id(self, guild_id: int, message_id: int) -> None:
        await self.upsert_settings(guild_id, panel_message_id=message_id)
