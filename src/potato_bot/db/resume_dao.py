"""
Resume DAO
Handles resume company settings and applications.
"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from potato_bot.db.base_dao import BaseDAO
from potato_bot.db.pool import db_pool
from potato_shared.logger import logger


class ResumeDAO(BaseDAO):
    """Resume system data access."""

    def __init__(self):
        super().__init__(table_name="resume_applications")
        self._tables_initialized = False

    async def _initialize(self):
        if self._tables_initialized:
            return
        await self._ensure_tables()
        self._tables_initialized = True

    async def _ensure_tables(self) -> None:
        """Create required tables if missing."""
        try:
            async with db_pool.connection() as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute(
                        """
                        CREATE TABLE IF NOT EXISTS resume_companies (
                            id BIGINT AUTO_INCREMENT PRIMARY KEY,
                            guild_id BIGINT NOT NULL,
                            company_name VARCHAR(100) NOT NULL,
                            panel_channel_id BIGINT NULL,
                            review_channel_id BIGINT NULL,
                            review_role_ids JSON NULL,
                            panel_message_id BIGINT NULL,
                            is_enabled BOOLEAN DEFAULT TRUE,
                            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                            UNIQUE KEY uniq_guild_company (guild_id, company_name),
                            INDEX idx_guild (guild_id)
                        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
                        """
                    )

                    await cursor.execute(
                        """
                        CREATE TABLE IF NOT EXISTS resume_applications (
                            id BIGINT AUTO_INCREMENT PRIMARY KEY,
                            guild_id BIGINT NOT NULL,
                            company_id BIGINT NOT NULL,
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
                            INDEX idx_company_status (company_id, status),
                            FOREIGN KEY (company_id) REFERENCES resume_companies(id) ON DELETE CASCADE
                        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
                        """
                    )

                    await conn.commit()
            logger.info("✅ resume 資料表檢查完成")
        except Exception as e:
            logger.error(f"❌ 建立 resume 資料表失敗: {e}")
            raise

    # --------- Company settings ----------
    async def get_company(self, company_id: int) -> Optional[Dict[str, Any]]:
        await self._ensure_initialized()
        query = "SELECT * FROM resume_companies WHERE id=%s"
        return await self.execute_query(query, (company_id,), fetch_one=True, dictionary=True)

    async def get_company_by_name(self, guild_id: int, company_name: str) -> Optional[Dict[str, Any]]:
        await self._ensure_initialized()
        query = "SELECT * FROM resume_companies WHERE guild_id=%s AND company_name=%s"
        return await self.execute_query(
            query, (guild_id, company_name), fetch_one=True, dictionary=True
        )

    async def list_companies(self, guild_id: int) -> List[Dict[str, Any]]:
        await self._ensure_initialized()
        query = "SELECT * FROM resume_companies WHERE guild_id=%s ORDER BY company_name"
        rows = await self.execute_query(query, (guild_id,), fetch_all=True, dictionary=True)
        return rows or []

    async def upsert_company(self, guild_id: int, company_name: str, **settings: Any) -> None:
        await self._ensure_initialized()
        review_role_ids = settings.get("review_role_ids")
        if review_role_ids is not None:
            review_role_ids = json.dumps(review_role_ids, ensure_ascii=False)

        query = """
            INSERT INTO resume_companies (
                guild_id, company_name, panel_channel_id, review_channel_id,
                review_role_ids, panel_message_id, is_enabled
            ) VALUES (%s, %s, %s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE
                panel_channel_id=VALUES(panel_channel_id),
                review_channel_id=VALUES(review_channel_id),
                review_role_ids=VALUES(review_role_ids),
                panel_message_id=VALUES(panel_message_id),
                is_enabled=VALUES(is_enabled)
        """
        await self.execute_query(
            query,
            (
                guild_id,
                company_name,
                settings.get("panel_channel_id"),
                settings.get("review_channel_id"),
                review_role_ids,
                settings.get("panel_message_id"),
                settings.get("is_enabled", True),
            ),
        )

    async def update_panel_message_id(self, company_id: int, message_id: int) -> None:
        await self._ensure_initialized()
        query = "UPDATE resume_companies SET panel_message_id=%s WHERE id=%s"
        await self.execute_query(query, (message_id, company_id))

    # --------- Applications ----------
    async def has_pending(self, guild_id: int, company_id: int, user_id: int) -> bool:
        await self._ensure_initialized()
        query = """
            SELECT 1 FROM resume_applications
            WHERE guild_id=%s AND company_id=%s AND user_id=%s AND status='PENDING'
            LIMIT 1
        """
        result = await self.execute_query(query, (guild_id, company_id, user_id), fetch_one=True)
        return bool(result)

    async def get_latest_application(
        self, guild_id: int, company_id: int, user_id: int, statuses: Optional[List[str]] = None
    ) -> Optional[Dict[str, Any]]:
        await self._ensure_initialized()
        if statuses:
            placeholders = ", ".join(["%s"] * len(statuses))
            query = f"""
                SELECT * FROM resume_applications
                WHERE guild_id=%s AND company_id=%s AND user_id=%s AND status IN ({placeholders})
                ORDER BY created_at DESC
                LIMIT 1
            """
            params = (guild_id, company_id, user_id, *statuses)
        else:
            query = """
                SELECT * FROM resume_applications
                WHERE guild_id=%s AND company_id=%s AND user_id=%s
                ORDER BY created_at DESC
                LIMIT 1
            """
            params = (guild_id, company_id, user_id)

        return await self.execute_query(query, params, fetch_one=True, dictionary=True)

    async def create_application(
        self,
        guild_id: int,
        company_id: int,
        user_id: int,
        username: str,
        answers: Dict[str, Any],
    ) -> int:
        await self._ensure_initialized()
        async with db_pool.connection() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute(
                    """
                    INSERT INTO resume_applications
                    (guild_id, company_id, user_id, username, answers_json, status)
                    VALUES (%s, %s, %s, %s, %s, 'PENDING')
                    """,
                    (guild_id, company_id, user_id, username, json.dumps(answers, ensure_ascii=False)),
                )
                await conn.commit()
                return cursor.lastrowid

    async def update_application(self, app_id: int, username: str, answers: Dict[str, Any]) -> bool:
        await self._ensure_initialized()
        query = """
            UPDATE resume_applications
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
        query = "SELECT * FROM resume_applications WHERE id=%s"
        return await self.execute_query(query, (app_id,), fetch_one=True, dictionary=True)

    async def set_status(
        self, app_id: int, status: str, reviewer_id: int, note: Optional[str] = None
    ) -> bool:
        await self._ensure_initialized()
        query = """
            UPDATE resume_applications
            SET status=%s, reviewer_id=%s, reviewer_note=%s, reviewed_at=CURRENT_TIMESTAMP
            WHERE id=%s AND status IN ('PENDING','NEED_MORE')
        """
        rows = await self.execute_query(query, (status, reviewer_id, note, app_id))
        return rows > 0

    async def set_review_message_id(self, app_id: int, message_id: int) -> None:
        await self._ensure_initialized()
        query = "UPDATE resume_applications SET review_message_id=%s WHERE id=%s"
        await self.execute_query(query, (message_id, app_id))

    async def list_pending_with_message(self) -> List[Dict[str, Any]]:
        await self._ensure_initialized()
        query = """
            SELECT id, guild_id, company_id, review_message_id
            FROM resume_applications
            WHERE status IN ('PENDING','NEED_MORE') AND review_message_id IS NOT NULL
        """
        rows = await self.execute_query(query, fetch_all=True, dictionary=True)
        return rows or []
