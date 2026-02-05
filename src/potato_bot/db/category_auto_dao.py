"""
Category auto-create settings DAO.
"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from potato_bot.db.base_dao import BaseDAO
from potato_bot.db.pool import db_pool
from potato_shared.logger import logger


def _normalize_role_ids(value: Any) -> List[int]:
    if value is None:
        return []
    if isinstance(value, list):
        return [int(role_id) for role_id in value]
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
            if isinstance(parsed, list):
                return [int(role_id) for role_id in parsed]
        except json.JSONDecodeError:
            return []
    return []


class CategoryAutoDAO(BaseDAO):
    """Category auto-create settings data access."""

    def __init__(self):
        super().__init__(table_name="category_auto_settings")
        self._tables_initialized = False

    async def _initialize(self):
        if self._tables_initialized:
            return
        await self._ensure_tables()
        self._tables_initialized = True

    async def _ensure_tables(self) -> None:
        try:
            async with db_pool.connection() as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute("SHOW TABLES LIKE 'category_auto_settings'")
                    if not await cursor.fetchone():
                        raise RuntimeError("category_auto_settings 表不存在，請先初始化資料庫")
            logger.info("✅ category_auto_settings 資料表檢查完成")
        except Exception as e:
            logger.error(f"❌ 檢查 category_auto_settings 資料表失敗: {e}")
            raise

    async def get_settings(self, guild_id: int) -> Dict[str, Any]:
        await self._ensure_initialized()
        query = """
            SELECT allowed_role_ids, manager_role_ids
            FROM category_auto_settings
            WHERE guild_id=%s
        """
        row = await self.execute_query(query, (guild_id,), fetch_one=True, dictionary=True)
        if not row:
            return {"guild_id": guild_id, "allowed_role_ids": [], "manager_role_ids": []}
        return {
            "guild_id": guild_id,
            "allowed_role_ids": _normalize_role_ids(row.get("allowed_role_ids")),
            "manager_role_ids": _normalize_role_ids(row.get("manager_role_ids")),
        }

    async def save_settings(
        self,
        guild_id: int,
        *,
        allowed_role_ids: Optional[List[int]] = None,
        manager_role_ids: Optional[List[int]] = None,
    ) -> Dict[str, Any]:
        await self._ensure_initialized()
        current = await self.get_settings(guild_id)
        if allowed_role_ids is None:
            allowed_role_ids = current.get("allowed_role_ids", [])
        if manager_role_ids is None:
            manager_role_ids = current.get("manager_role_ids", [])

        allowed_json = json.dumps(allowed_role_ids, ensure_ascii=False)
        manager_json = json.dumps(manager_role_ids, ensure_ascii=False)

        query = """
            INSERT INTO category_auto_settings (guild_id, allowed_role_ids, manager_role_ids)
            VALUES (%s, %s, %s)
            ON DUPLICATE KEY UPDATE
                allowed_role_ids=VALUES(allowed_role_ids),
                manager_role_ids=VALUES(manager_role_ids),
                updated_at=CURRENT_TIMESTAMP
        """
        await self.execute_query(query, (guild_id, allowed_json, manager_json))
        return {
            "guild_id": guild_id,
            "allowed_role_ids": allowed_role_ids,
            "manager_role_ids": manager_role_ids,
        }
