"""
Whitelist interview DAO
管理白名單語音面試設定與排隊資料
"""

from __future__ import annotations

from datetime import date
from typing import Any, Dict, List, Optional

from potato_bot.db.base_dao import BaseDAO
from potato_bot.db.pool import db_pool
from potato_shared.logger import logger


class WhitelistInterviewDAO(BaseDAO):
    """白名單語音面試資料存取"""

    def __init__(self):
        super().__init__(table_name="whitelist_interview_queue")
        self._tables_initialized = False

    async def _initialize(self):
        if self._tables_initialized:
            return
        await self._ensure_tables()
        self._tables_initialized = True

    async def _ensure_tables(self) -> None:
        """檢查所需資料表"""
        try:
            async with db_pool.connection() as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute("SHOW TABLES LIKE 'whitelist_interview_settings'")
                    if not await cursor.fetchone():
                        raise RuntimeError(
                            "whitelist_interview_settings 表不存在，請先初始化資料庫"
                        )

                    await cursor.execute("SHOW TABLES LIKE 'whitelist_interview_counters'")
                    if not await cursor.fetchone():
                        raise RuntimeError(
                            "whitelist_interview_counters 表不存在，請先初始化資料庫"
                        )

                    await cursor.execute("SHOW TABLES LIKE 'whitelist_interview_queue'")
                    if not await cursor.fetchone():
                        raise RuntimeError(
                            "whitelist_interview_queue 表不存在，請先初始化資料庫"
                        )
            logger.info("✅ whitelist interview 資料表檢查完成")
        except Exception as e:
            logger.error(f"❌ 檢查 whitelist interview 資料表失敗: {e}")
            raise

    # --------- Settings ----------
    async def get_settings(self, guild_id: int) -> Dict[str, Any]:
        await self._ensure_initialized()
        query = "SELECT * FROM whitelist_interview_settings WHERE guild_id=%s"
        result = await self.execute_query(query, (guild_id,), fetch_one=True, dictionary=True)
        return result or {}

    async def upsert_settings(self, guild_id: int, **settings: Any) -> None:
        await self._ensure_initialized()
        keys = [
            "waiting_channel_id",
            "interview_channel_id",
            "notify_channel_id",
            "staff_role_id",
            "timezone",
            "session_start_hour",
            "session_end_hour",
            "is_enabled",
        ]
        values = [settings.get(key) for key in keys]
        query = """
            INSERT INTO whitelist_interview_settings (
                guild_id, waiting_channel_id, interview_channel_id, notify_channel_id,
                staff_role_id, timezone, session_start_hour, session_end_hour, is_enabled
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE
                waiting_channel_id=VALUES(waiting_channel_id),
                interview_channel_id=VALUES(interview_channel_id),
                notify_channel_id=VALUES(notify_channel_id),
                staff_role_id=VALUES(staff_role_id),
                timezone=VALUES(timezone),
                session_start_hour=VALUES(session_start_hour),
                session_end_hour=VALUES(session_end_hour),
                is_enabled=VALUES(is_enabled)
        """
        await self.execute_query(query, (guild_id, *values))

    async def update_enabled(self, guild_id: int, enabled: bool) -> None:
        await self._ensure_initialized()
        query = """
            INSERT INTO whitelist_interview_settings (guild_id, is_enabled)
            VALUES (%s, %s)
            ON DUPLICATE KEY UPDATE is_enabled=VALUES(is_enabled)
        """
        await self.execute_query(query, (guild_id, enabled))

    # --------- Queue ----------
    async def get_or_create_queue_entry(
        self,
        guild_id: int,
        user_id: int,
        username: str,
        original_nickname: Optional[str],
        queue_date: date,
    ) -> Dict[str, Any]:
        """取得或建立當日排隊號碼（同一人一天只會有一個號碼）"""
        await self._ensure_initialized()
        async with db_pool.connection() as conn:
            async with conn.cursor() as cursor:
                try:
                    await cursor.execute("START TRANSACTION")

                    await cursor.execute(
                        """
                        SELECT queue_number, notified_message_id, status
                        FROM whitelist_interview_queue
                        WHERE guild_id=%s AND user_id=%s AND queue_date=%s
                        LIMIT 1
                        FOR UPDATE
                        """,
                        (guild_id, user_id, queue_date),
                    )
                    existing = await cursor.fetchone()
                    if existing:
                        await conn.commit()
                        return {
                            "queue_number": int(existing[0]),
                            "notified_message_id": existing[1],
                            "status": str(existing[2] or "WAITING"),
                            "created": False,
                        }

                    await cursor.execute(
                        """
                        INSERT INTO whitelist_interview_counters (guild_id, queue_date, next_number)
                        VALUES (%s, %s, 2)
                        ON DUPLICATE KEY UPDATE next_number = next_number + 1
                        """,
                        (guild_id, queue_date),
                    )
                    await cursor.execute(
                        """
                        SELECT next_number
                        FROM whitelist_interview_counters
                        WHERE guild_id=%s AND queue_date=%s
                        FOR UPDATE
                        """,
                        (guild_id, queue_date),
                    )
                    counter_row = await cursor.fetchone()
                    next_number = int(counter_row[0]) if counter_row else 2
                    queue_number = max(1, next_number - 1)

                    await cursor.execute(
                        """
                        INSERT INTO whitelist_interview_queue (
                            guild_id, user_id, username, original_nickname,
                            queue_date, queue_number, status
                        ) VALUES (%s, %s, %s, %s, %s, %s, 'WAITING')
                        """,
                        (
                            guild_id,
                            user_id,
                            username,
                            original_nickname,
                            queue_date,
                            queue_number,
                        ),
                    )
                    await conn.commit()
                    return {
                        "queue_number": queue_number,
                        "notified_message_id": None,
                        "status": "WAITING",
                        "created": True,
                    }
                except Exception:
                    await conn.rollback()
                    raise

    async def get_queue_entry(
        self, guild_id: int, user_id: int, queue_date: date
    ) -> Optional[Dict[str, Any]]:
        await self._ensure_initialized()
        query = """
            SELECT * FROM whitelist_interview_queue
            WHERE guild_id=%s AND user_id=%s AND queue_date=%s
            LIMIT 1
        """
        return await self.execute_query(
            query,
            (guild_id, user_id, queue_date),
            fetch_one=True,
            dictionary=True,
        )

    async def list_queue(self, guild_id: int, queue_date: date) -> List[Dict[str, Any]]:
        await self._ensure_initialized()
        query = """
            SELECT * FROM whitelist_interview_queue
            WHERE guild_id=%s AND queue_date=%s
            ORDER BY queue_number ASC
        """
        rows = await self.execute_query(
            query,
            (guild_id, queue_date),
            fetch_all=True,
            dictionary=True,
        )
        return rows or []

    async def list_waiting_queue(self, guild_id: int, queue_date: date) -> List[Dict[str, Any]]:
        await self._ensure_initialized()
        query = """
            SELECT * FROM whitelist_interview_queue
            WHERE guild_id=%s AND queue_date=%s AND status='WAITING'
            ORDER BY queue_number ASC
        """
        rows = await self.execute_query(
            query,
            (guild_id, queue_date),
            fetch_all=True,
            dictionary=True,
        )
        return rows or []

    async def set_status(
        self, guild_id: int, user_id: int, queue_date: date, status: str
    ) -> bool:
        await self._ensure_initialized()
        query = """
            UPDATE whitelist_interview_queue
            SET
                status=%s,
                called_at=CASE
                    WHEN %s='CALLED' THEN COALESCE(called_at, CURRENT_TIMESTAMP)
                    ELSE called_at
                END,
                done_at=CASE
                    WHEN %s='DONE' THEN CURRENT_TIMESTAMP
                    ELSE done_at
                END
            WHERE guild_id=%s AND user_id=%s AND queue_date=%s
        """
        rows = await self.execute_query(
            query,
            (status, status, status, guild_id, user_id, queue_date),
        )
        return rows > 0

    async def set_notified_message_id(
        self, guild_id: int, user_id: int, queue_date: date, message_id: int
    ) -> bool:
        await self._ensure_initialized()
        query = """
            UPDATE whitelist_interview_queue
            SET notified_message_id=%s
            WHERE guild_id=%s AND user_id=%s AND queue_date=%s
        """
        rows = await self.execute_query(
            query,
            (message_id, guild_id, user_id, queue_date),
        )
        return rows > 0

    async def reset_today_queue(self, guild_id: int, queue_date: date) -> None:
        await self._ensure_initialized()
        async with db_pool.connection() as conn:
            async with conn.cursor() as cursor:
                try:
                    await cursor.execute("START TRANSACTION")
                    await cursor.execute(
                        """
                        DELETE FROM whitelist_interview_queue
                        WHERE guild_id=%s AND queue_date=%s
                        """,
                        (guild_id, queue_date),
                    )
                    await cursor.execute(
                        """
                        DELETE FROM whitelist_interview_counters
                        WHERE guild_id=%s AND queue_date=%s
                        """,
                        (guild_id, queue_date),
                    )
                    await conn.commit()
                except Exception:
                    await conn.rollback()
                    raise
