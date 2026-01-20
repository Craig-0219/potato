"""
Auto reply DAO.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from potato_bot.db.base_dao import BaseDAO
from potato_bot.db.pool import db_pool
from potato_shared.logger import logger


class AutoReplyDAO(BaseDAO):
    """Auto reply data access."""

    def __init__(self):
        super().__init__(table_name="mention_auto_replies")
        self._tables_initialized = False

    async def _initialize(self):
        if self._tables_initialized:
            return
        await self._ensure_tables()
        self._tables_initialized = True

    async def _ensure_tables(self) -> None:
        """Check required tables exist."""
        try:
            async with db_pool.connection() as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute("SHOW TABLES LIKE 'mention_auto_replies'")
                    if not await cursor.fetchone():
                        raise RuntimeError("mention_auto_replies 表不存在，請先初始化資料庫")
            logger.info("✅ mention_auto_replies 資料表檢查完成")
        except Exception as e:
            logger.error(f"❌ 檢查 mention_auto_replies 資料表失敗: {e}")
            raise

    async def list_rules(self, guild_id: int) -> List[Dict[str, Any]]:
        await self._ensure_initialized()
        query = """
            SELECT target_user_id, reply_text, updated_at
            FROM mention_auto_replies
            WHERE guild_id=%s
            ORDER BY updated_at DESC
        """
        rows = await self.execute_query(query, (guild_id,), fetch_all=True, dictionary=True)
        return rows or []

    async def upsert_rule(
        self,
        guild_id: int,
        target_user_id: int,
        reply_text: str,
        actor_id: Optional[int] = None,
    ) -> None:
        await self._ensure_initialized()
        query = """
            INSERT INTO mention_auto_replies (
                guild_id, target_user_id, reply_text, created_by, updated_by
            ) VALUES (%s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE
                reply_text=VALUES(reply_text),
                updated_by=VALUES(updated_by),
                updated_at=CURRENT_TIMESTAMP
        """
        await self.execute_query(
            query,
            (guild_id, target_user_id, reply_text, actor_id, actor_id),
        )

    async def delete_rule(self, guild_id: int, target_user_id: int) -> bool:
        await self._ensure_initialized()
        query = "DELETE FROM mention_auto_replies WHERE guild_id=%s AND target_user_id=%s"
        result = await self.execute_query(query, (guild_id, target_user_id))
        return result > 0
