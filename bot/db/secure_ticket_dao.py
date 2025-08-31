# bot/db/secure_ticket_dao.py - v2.0.0
# 🔐 票券資料存取層 (簡化版)
# Ticket Data Access Object - Simplified

import logging
from datetime import datetime
from typing import Any, Dict, Optional

import aiomysql

from bot.db.pool import db_pool

logger = logging.getLogger(__name__)


class SecureTicketDAO:
    """票券資料存取層 - 標準版"""

    def __init__(self):
        self.db = db_pool
        self._initialized = False

    async def _ensure_initialized(self):
        """確保資料庫已初始化"""
        if not self._initialized:
            # 初始化相關表格
            self._initialized = True

    async def get_tickets_by_guild(
        self, guild_id: int, user_id: Optional[int] = None, status: Optional[str] = None
    ) -> list[Dict[str, Any]]:
        """獲取伺服器的票券列表"""
        try:
            await self._ensure_initialized()

            conditions = ["guild_id = %s"]
            params = [guild_id]

            if user_id:
                conditions.append("user_id = %s")
                params.append(user_id)

            if status:
                conditions.append("status = %s")
                params.append(status)

            where_clause = " AND ".join(conditions)

            async with self.db.connection() as conn:
                async with conn.cursor(aiomysql.DictCursor) as cursor:
                    await cursor.execute(
                        f"SELECT * FROM tickets WHERE {where_clause} ORDER BY created_at DESC",
                        params,
                    )
                    results = await cursor.fetchall()
                    return [dict(row) for row in results]

        except Exception as e:
            logger.error(f"❌ 獲取票券列表失敗: {e}")
            return []

    async def get_tickets_paginated(
        self, guild_id: int, user_id: int, page: int = 1, per_page: int = 10
    ) -> Dict[str, Any]:
        """分頁獲取票券"""
        try:
            await self._ensure_initialized()

            offset = (page - 1) * per_page

            async with self.db.connection() as conn:
                async with conn.cursor(aiomysql.DictCursor) as cursor:
                    # 計算總數
                    await cursor.execute(
                        "SELECT COUNT(*) as total FROM tickets WHERE guild_id = %s",
                        (guild_id,),
                    )
                    total = (await cursor.fetchone())["total"]

                    # 獲取分頁數據
                    await cursor.execute(
                        """
                        SELECT * FROM tickets
                        WHERE guild_id = %s
                        ORDER BY created_at DESC
                        LIMIT %s OFFSET %s
                        """,
                        (guild_id, per_page, offset),
                    )
                    tickets = await cursor.fetchall()

                    return {
                        "tickets": [dict(row) for row in tickets],
                        "total": total,
                        "page": page,
                        "per_page": per_page,
                        "total_pages": (total + per_page - 1) // per_page,
                    }

        except Exception as e:
            logger.error(f"❌ 分頁獲取票券失敗: {e}")
            return {"tickets": [], "total": 0, "page": 1, "per_page": per_page, "total_pages": 0}

    async def create_ticket(
        self, guild_id: int, user_id: int, ticket_data: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """建立新票券"""
        try:
            await self._ensure_initialized()

            # 準備票券數據
            insert_data = {
                "guild_id": guild_id,
                "user_id": user_id,
                "channel_id": ticket_data.get("channel_id"),
                "category": ticket_data.get("category", "general"),
                "subject": ticket_data.get("subject", ""),
                "description": ticket_data.get("description", ""),
                "status": "open",
                "priority": ticket_data.get("priority", "medium"),
                "created_at": datetime.now(),
                "updated_at": datetime.now(),
            }

            async with self.db.connection() as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute(
                        """
                        INSERT INTO tickets
                        (guild_id, user_id, channel_id, category, subject, description, status, priority, created_at, updated_at)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        """,
                        (
                            insert_data["guild_id"],
                            insert_data["user_id"],
                            insert_data["channel_id"],
                            insert_data["category"],
                            insert_data["subject"],
                            insert_data["description"],
                            insert_data["status"],
                            insert_data["priority"],
                            insert_data["created_at"],
                            insert_data["updated_at"],
                        ),
                    )

                    # 獲取插入的 ID
                    ticket_id = cursor.lastrowid
                    await conn.commit()

                    # 返回完整票券數據
                    await cursor.execute("SELECT * FROM tickets WHERE id = %s", (ticket_id,))
                    result = await cursor.fetchone()

                    if result:
                        return dict(zip([desc[0] for desc in cursor.description], result))

        except Exception as e:
            logger.error(f"❌ 建立票券失敗: {e}")
            return None

    async def update_ticket(
        self,
        ticket_id: int,
        guild_id: int,
        user_id: int,
        update_data: Dict[str, Any],
        admin_override: bool = False,
    ) -> bool:
        """更新票券"""
        try:
            await self._ensure_initialized()

            # 設置更新數據
            update_data["updated_at"] = datetime.now()

            # 建構 SET 子句
            set_clauses = []
            params = []

            for key, value in update_data.items():
                set_clauses.append(f"{key} = %s")
                params.append(value)

            # 添加 WHERE 條件參數
            params.extend([ticket_id, guild_id])

            async with self.db.connection() as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute(
                        f"""
                        UPDATE tickets
                        SET {', '.join(set_clauses)}
                        WHERE id = %s AND guild_id = %s
                        """,
                        params,
                    )

                    affected_rows = cursor.rowcount
                    await conn.commit()

                    return affected_rows > 0

        except Exception as e:
            logger.error(f"❌ 更新票券失敗: {e}")
            return False


# 全域實例
secure_ticket_dao = SecureTicketDAO()
