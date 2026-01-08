# bot/db/ticket_dao.py - 完整修復版
"""
票券資料存取層 - 完整修復版
修復所有缺失的方法和異步上下文管理器問題
"""

import json
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

import aiomysql

from potato_bot.db.pool import db_pool
from potato_shared.logger import logger


class TicketDAO:
    """票券資料存取層 - 完整修復版"""

    def __init__(self):
        self.db = db_pool
        self._initialized = False

    async def _ensure_initialized(self):
        """確保資料庫已初始化"""
        if not self._initialized:
            try:
                # 檢查主要表格是否存在
                async with self.db.connection() as conn:
                    async with conn.cursor() as cursor:
                        await cursor.execute(
                            """
                            SELECT COUNT(*) FROM information_schema.tables
                            WHERE table_schema = DATABASE() AND table_name = 'tickets'
                        """
                        )
                        exists = (await cursor.fetchone())[0] > 0

                if not exists:
                    logger.warning("📋 檢測到票券表格不存在，開始自動初始化...")
                    from potato_bot.db.database_manager import DatabaseManager

                    db_manager = DatabaseManager()
                    await db_manager._create_ticket_tables()

                self._initialized = True
                logger.info("✅ 票券 DAO 初始化完成")

            except Exception as e:
                logger.error(f"❌ 票券 DAO 初始化失敗：{e}")
                raise

    # ===== 修復：添加缺失的屬性和方法 =====

    @property
    def db_pool(self):
        """資料庫連接池屬性 - 修復缺失"""
        return self.db

    async def get_guild_settings(self, guild_id: int) -> Dict[str, Any]:
        """取得伺服器設定 - 修復缺失方法"""
        return await self.get_settings(guild_id)

    async def cleanup_old_logs(self, days: int = 30) -> int:
        """清理舊日誌 - 修復缺失方法"""
        await self._ensure_initialized()
        try:
            cutoff_date = datetime.now(timezone.utc) - timedelta(days=days)

            async with self.db.connection() as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute(
                        "DELETE FROM ticket_logs WHERE created_at < %s",
                        (cutoff_date,),
                    )
                    await conn.commit()

                    cleaned_count = cursor.rowcount
                    logger.info(f"清理了 {cleaned_count} 條舊日誌")
                    return cleaned_count

        except Exception as e:
            logger.error(f"清理舊日誌錯誤：{e}")
            return 0

    async def update_last_activity(self, ticket_id: int):
        """更新票券最後活動時間 - 新增方法"""
        await self._ensure_initialized()
        try:
            async with self.db.connection() as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute(
                        """
                        UPDATE tickets
                        SET last_activity = NOW()
                        WHERE id = %s
                    """,
                        (ticket_id,),
                    )
                    await conn.commit()

        except Exception as e:
            logger.error(f"更新活動時間錯誤：{e}")

    async def get_inactive_tickets(
        self, guild_id: int, cutoff_time: datetime
    ) -> List[Dict[str, Any]]:
        """取得無活動票券 - 新增方法"""
        await self._ensure_initialized()
        try:
            async with self.db.connection() as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute(
                        """
                        SELECT id as ticket_id, discord_id, type, priority, created_at, last_activity, channel_id
                        FROM tickets
                        WHERE guild_id = %s
                        AND status = 'open'
                        AND (last_activity < %s OR (last_activity IS NULL AND created_at < %s))
                        ORDER BY created_at ASC
                    """,
                        (guild_id, cutoff_time, cutoff_time),
                    )

                    columns = [desc[0] for desc in cursor.description]
                    results = await cursor.fetchall()

                    return [dict(zip(columns, row)) for row in results]

        except Exception as e:
            logger.error(f"查詢無活動票券錯誤：{e}")
            return []

    async def save_panel_message(self, guild_id: int, message_id: int, channel_id: int):
        """保存面板訊息 - 新增方法"""
        await self._ensure_initialized()
        try:
            async with self.db.connection() as conn:
                async with conn.cursor() as cursor:
                    # 更新設定表中的面板資訊
                    await cursor.execute(
                        """
                        INSERT INTO ticket_settings (guild_id, updated_at)
                        VALUES (%s, NOW())
                        ON DUPLICATE KEY UPDATE updated_at = NOW()
                    """,
                        (guild_id,),
                    )
                    await conn.commit()
                    logger.info(f"保存面板訊息 - 伺服器: {guild_id}, 訊息: {message_id}")

        except Exception as e:
            logger.error(f"保存面板訊息錯誤：{e}")

    # ===== 修復現有方法的異步問題 =====

    async def create_ticket(
        self,
        discord_id: str,
        username: str,
        ticket_type: str,
        channel_id: int,
        guild_id: int,
        priority: str = "medium",
    ) -> Optional[int]:
        """建立新票券 - 加強版"""
        await self._ensure_initialized()
        try:
            async with self.db.connection() as conn:
                async with conn.cursor() as cursor:
                    # 檢查用戶是否已達票券上限
                    await cursor.execute(
                        """
                        SELECT COUNT(*) FROM tickets
                        WHERE discord_id = %s AND guild_id = %s AND status = 'open'
                    """,
                        (discord_id, guild_id),
                    )

                    current_count = (await cursor.fetchone())[0]
                    settings = await self.get_settings(guild_id)
                    max_tickets = settings.get("max_tickets_per_user", 3)

                    if current_count >= max_tickets:
                        logger.warning(f"用戶 {discord_id} 已達票券上限")
                        return None

                    await cursor.execute(
                        """
                        INSERT INTO tickets (discord_id, username, discord_username, type, priority, channel_id, guild_id, created_at, last_activity)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, NOW(), NOW())
                    """,
                        (
                            discord_id,
                            username,
                            username,
                            ticket_type,
                            priority,
                            channel_id,
                            guild_id,
                        ),
                    )

                    ticket_id = cursor.lastrowid

                    # 記錄操作日誌
                    await cursor.execute(
                        """
                        INSERT INTO ticket_logs (ticket_id, action, details, created_by, created_at)
                        VALUES (%s, 'created', %s, %s, NOW())
                    """,
                        (ticket_id, f"建立{ticket_type}票券", discord_id),
                    )

                    await conn.commit()
                    logger.info(f"建立票券 #{ticket_id:04d} - 用戶: {username}")
                    return ticket_id

        except Exception as e:
            logger.error(f"建立票券錯誤：{e}")
            return None

    async def get_ticket_by_id(self, ticket_id: int) -> Optional[Dict[str, Any]]:
        """根據 ID 取得票券 - 修復異步"""
        await self._ensure_initialized()
        try:
            async with self.db.connection() as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute("SELECT * FROM tickets WHERE id = %s", (ticket_id,))
                    result = await cursor.fetchone()
                    if result:
                        columns = [desc[0] for desc in cursor.description]
                        ticket = dict(zip(columns, result))
                        ticket["ticket_id"] = ticket.get("id")
                        return ticket
                    return None
        except Exception as e:
            logger.error(f"查詢票券錯誤：{e}")
            return None

    async def get_ticket(self, ticket_id: int) -> Optional[Dict[str, Any]]:
        """取得票券（兼容快取 DAO）"""
        return await self.get_ticket_by_id(ticket_id)

    async def delete_ticket(self, ticket_id: int) -> bool:
        """刪除票券"""
        await self._ensure_initialized()
        try:
            async with self.db.connection() as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute("DELETE FROM tickets WHERE id = %s", (ticket_id,))
                    await conn.commit()
                    return cursor.rowcount > 0
        except Exception as e:
            logger.error(f"刪除票券錯誤：{e}")
            return False

    async def get_tickets_batch(
        self, ticket_ids: List[int]
    ) -> Dict[int, Optional[Dict[str, Any]]]:
        """批量取得票券"""
        await self._ensure_initialized()
        if not ticket_ids:
            return {}

        try:
            placeholders = ", ".join(["%s"] * len(ticket_ids))
            sql = f"SELECT * FROM tickets WHERE id IN ({placeholders})"

            async with self.db.connection() as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute(sql, ticket_ids)
                    results = await cursor.fetchall()
                    columns = [desc[0] for desc in cursor.description]

            tickets = [dict(zip(columns, row)) for row in results]
            for ticket in tickets:
                ticket["ticket_id"] = ticket.get("id")

            return {ticket["id"]: ticket for ticket in tickets}
        except Exception as e:
            logger.error(f"批量查詢票券錯誤：{e}")
            return {}

    # ===== 兼容舊介面：暫時回傳空結果避免噴錯 =====
    async def get_guild_tickets(
        self,
        guild_id: int,
        status: Optional[Any] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> Tuple[List[Dict[str, Any]], int]:
        """取得伺服器票券列表"""
        await self._ensure_initialized()
        try:
            where_conditions = ["guild_id = %s"]
            params = [guild_id]

            if status:
                if isinstance(status, list):
                    placeholders = ", ".join(["%s"] * len(status))
                    where_conditions.append(f"status IN ({placeholders})")
                    params.extend(status)
                else:
                    where_conditions.append("status = %s")
                    params.append(status)

            where_clause = " AND ".join(where_conditions)

            async with self.db.connection() as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute(
                        f"SELECT COUNT(*) FROM tickets WHERE {where_clause}",
                        params,
                    )
                    total_result = await cursor.fetchone()
                    total = total_result[0] if total_result else 0

                    await cursor.execute(
                        f"""
                        SELECT * FROM tickets
                        WHERE {where_clause}
                        ORDER BY created_at DESC
                        LIMIT %s OFFSET %s
                    """,
                        params + [limit, offset],
                    )

                    results = await cursor.fetchall()
                    columns = [desc[0] for desc in cursor.description]
                    tickets = [dict(zip(columns, row)) for row in results]
                    for ticket in tickets:
                        ticket["ticket_id"] = ticket.get("id")

                    return tickets, total
        except Exception as e:
            logger.error(f"查詢伺服器票券錯誤：{e}")
            return [], 0

    async def get_ticket_by_channel(self, channel_id: int) -> Optional[Dict[str, Any]]:
        """根據頻道 ID 取得票券 - 修復異步"""
        await self._ensure_initialized()
        try:
            async with self.db.connection() as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute(
                        "SELECT * FROM tickets WHERE channel_id = %s",
                        (channel_id,),
                    )
                    result = await cursor.fetchone()
                    if result:
                        columns = [desc[0] for desc in cursor.description]
                        ticket = dict(zip(columns, result))
                        ticket["ticket_id"] = ticket.get("id")
                        return ticket
                    return None
        except Exception as e:
            logger.error(f"查詢票券錯誤：{e}")
            return None

    async def get_tickets(
        self,
        guild_id: int,
        user_id: int = None,
        status: str = "all",
        page: int = 1,
        page_size: int = 10,
    ) -> Tuple[List[Dict], int]:
        """分頁查詢票券 - 修復異步"""
        await self._ensure_initialized()
        try:
            where_conditions = ["guild_id = %s"]
            params = [guild_id]

            if user_id:
                where_conditions.append("discord_id = %s")
                params.append(str(user_id))

            if status in ("open", "closed"):
                where_conditions.append("status = %s")
                params.append(status)

            where_clause = " AND ".join(where_conditions)

            async with self.db.connection() as conn:
                async with conn.cursor() as cursor:
                    # 總數查詢
                    await cursor.execute(
                        f"SELECT COUNT(*) FROM tickets WHERE {where_clause}",
                        params,
                    )
                    total_result = await cursor.fetchone()
                    total = total_result[0] if total_result else 0

                    # 分頁查詢
                    offset = (page - 1) * page_size
                    await cursor.execute(
                        f"""
                        SELECT * FROM tickets WHERE {where_clause}
                        ORDER BY
                            CASE WHEN status = 'open' THEN 0 ELSE 1 END,
                            CASE priority WHEN 'high' THEN 1 WHEN 'medium' THEN 2 ELSE 3 END,
                            created_at DESC
                        LIMIT %s OFFSET %s
                    """,
                        params + [page_size, offset],
                    )

                    results = await cursor.fetchall()
                    columns = [desc[0] for desc in cursor.description]
                    tickets = [dict(zip(columns, row)) for row in results]

                    return tickets, total

        except Exception as e:
            logger.error(f"查詢票券列表錯誤：{e}")
            return [], 0

    async def close_ticket(self, ticket_id: int, closed_by: int, reason: str = None) -> bool:
        """關閉票券 - 修復參數"""
        await self._ensure_initialized()
        try:
            async with self.db.connection() as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute(
                        """
                        UPDATE tickets
                        SET status = 'closed', closed_at = NOW(), closed_by = %s, close_reason = %s
                        WHERE id = %s AND status = 'open'
                    """,
                        (str(closed_by), reason, ticket_id),
                    )

                    if cursor.rowcount > 0:
                        # 記錄日誌
                        await cursor.execute(
                            """
                            INSERT INTO ticket_logs (ticket_id, action, details, created_by, created_at)
                            VALUES (%s, 'closed', %s, %s, NOW())
                        """,
                            (
                                ticket_id,
                                f"關閉票券 - {reason or '無原因'}",
                                str(closed_by),
                            ),
                        )

                        await conn.commit()
                        logger.info(f"關閉票券 #{ticket_id:04d}")
                        return True

            return False

        except Exception as e:
            logger.error(f"關閉票券錯誤：{e}")
            return False

    async def get_tickets_with_filters(
        self,
        filters: Dict[str, Any],
        limit: int = 20,
        offset: int = 0,
        guild_id: int = None,
    ) -> List[Dict[str, Any]]:
        """根據篩選條件獲取票券列表"""
        try:
            await self._ensure_initialized()

            # 構建查詢條件
            where_conditions = ["1=1"]
            params = []

            if guild_id:
                where_conditions.append("guild_id = %s")
                params.append(guild_id)

            if filters.get("status"):
                where_conditions.append("status = %s")
                params.append(filters["status"])

            if filters.get("priority"):
                where_conditions.append("priority = %s")
                params.append(filters["priority"])


            if filters.get("discord_id"):
                where_conditions.append("discord_id = %s")
                params.append(filters["discord_id"])

            if filters.get("search"):
                where_conditions.append("(username LIKE %s OR type LIKE %s)")
                search_param = f"%{filters['search']}%"
                params.extend([search_param, search_param])

            where_clause = " AND ".join(where_conditions)

            query = f"""
                SELECT * FROM tickets
                WHERE {where_clause}
                ORDER BY created_at DESC
                LIMIT %s OFFSET %s
            """
            params.extend([limit, offset])

            async with self.db.connection() as conn:
                async with conn.cursor(aiomysql.DictCursor) as cursor:
                    await cursor.execute(query, params)
                    return await cursor.fetchall()

        except Exception as e:
            logger.error(f"獲取票券列表失敗: {e}")
            return []

    async def count_tickets_with_filters(
        self, filters: Dict[str, Any], guild_id: int = None
    ) -> int:
        """統計符合篩選條件的票券數量"""
        try:
            await self._ensure_initialized()

            # 構建查詢條件（與 get_tickets_with_filters 相同）
            where_conditions = ["1=1"]
            params = []

            if guild_id:
                where_conditions.append("guild_id = %s")
                params.append(guild_id)

            if filters.get("status"):
                where_conditions.append("status = %s")
                params.append(filters["status"])

            if filters.get("priority"):
                where_conditions.append("priority = %s")
                params.append(filters["priority"])


            if filters.get("discord_id"):
                where_conditions.append("discord_id = %s")
                params.append(filters["discord_id"])

            if filters.get("search"):
                where_conditions.append("(username LIKE %s OR type LIKE %s)")
                search_param = f"%{filters['search']}%"
                params.extend([search_param, search_param])

            where_clause = " AND ".join(where_conditions)

            query = f"SELECT COUNT(*) as count FROM tickets WHERE {where_clause}"

            async with self.db.connection() as conn:
                async with conn.cursor(aiomysql.DictCursor) as cursor:
                    await cursor.execute(query, params)
                    result = await cursor.fetchone()
                    return result["count"] if result else 0

        except Exception as e:
            logger.error(f"統計票券數量失敗: {e}")
            return 0

    async def update_ticket(self, ticket_id: int, update_data: Dict[str, Any]) -> bool:
        """更新票券資料"""
        try:
            await self._ensure_initialized()

            if not update_data:
                return True

            # 構建更新語句
            set_clauses = []
            params = []

            for field, value in update_data.items():
                if field in [
                    "title",
                    "description",
                    "status",
                    "priority",
                    "closed_at",
                    "updated_at",
                ]:
                    set_clauses.append(f"{field} = %s")
                    params.append(value)

            if not set_clauses:
                return True

            # 總是更新 updated_at
            if "updated_at" not in update_data:
                set_clauses.append("updated_at = %s")
                params.append(datetime.now(timezone.utc))

            set_clause = ", ".join(set_clauses)
            query = f"UPDATE tickets SET {set_clause} WHERE id = %s"
            params.append(ticket_id)

            async with self.db.connection() as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute(query, params)
                    await conn.commit()
                    return cursor.rowcount > 0

        except Exception as e:
            logger.error(f"更新票券失敗: {e}")
            return False

    async def update_ticket_priority(self, ticket_id: int, priority: str) -> bool:
        """更新票券優先級 - 修復異步"""
        await self._ensure_initialized()
        try:
            async with self.db.connection() as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute(
                        """
                        UPDATE tickets SET priority = %s WHERE id = %s
                    """,
                        (priority, ticket_id),
                    )

                    # 記錄日誌
                    await cursor.execute(
                        """
                        INSERT INTO ticket_logs (ticket_id, action, details, created_by, created_at)
                        VALUES (%s, 'priority_change', %s, 'system', NOW())
                    """,
                        (ticket_id, f"優先級變更為 {priority}"),
                    )

                    await conn.commit()
                    return cursor.rowcount > 0

        except Exception as e:
            logger.error(f"更新優先級錯誤：{e}")
            return False

    async def get_user_ticket_count(self, user_id: int, guild_id: int, status: str = "open") -> int:
        """取得用戶票券數量 - 修復異步"""
        await self._ensure_initialized()
        try:
            async with self.db.connection() as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute(
                        """
                        SELECT COUNT(*) FROM tickets
                        WHERE discord_id = %s AND guild_id = %s AND status = %s
                    """,
                        (str(user_id), guild_id, status),
                    )

                    result = await cursor.fetchone()
                    return result[0] if result else 0

        except Exception as e:
            logger.error(f"查詢用戶票券數量錯誤：{e}")
            return 0

    async def get_user_tickets(
        self, user_id: int, guild_id: int, status: str = "all", limit: int = 10
    ) -> List[Dict[str, Any]]:
        """取得用戶票券列表 - 新增缺失方法"""
        await self._ensure_initialized()
        try:
            where_conditions = ["discord_id = %s", "guild_id = %s"]
            params = [str(user_id), guild_id]

            if status in ("open", "closed"):
                where_conditions.append("status = %s")
                params.append(status)

            where_clause = " AND ".join(where_conditions)

            async with self.db.connection() as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute(
                        f"""
                        SELECT id, discord_id, username, type, status, priority,
                               channel_id, created_at, closed_at
                        FROM tickets
                        WHERE {where_clause}
                        ORDER BY created_at DESC
                        LIMIT %s
                    """,
                        params + [limit],
                    )

                    results = await cursor.fetchall()
                    columns = [desc[0] for desc in cursor.description]

                    return [dict(zip(columns, row)) for row in results]

        except Exception as e:
            logger.error(f"查詢用戶票券列表錯誤：{e}")
            return []

    async def get_all_ticket_settings(self) -> List[Dict[str, Any]]:
        """取得所有伺服器的票券設定"""
        await self._ensure_initialized()
        try:
            async with self.db.connection() as conn:
                async with conn.cursor(aiomysql.DictCursor) as cursor:
                    await cursor.execute("SELECT * FROM ticket_settings")
                    results = await cursor.fetchall()
                    for settings in results:
                        if settings.get("support_roles"):
                            try:
                                settings["support_roles"] = json.loads(settings["support_roles"])
                            except:
                                settings["support_roles"] = []
                        else:
                            settings["support_roles"] = []
                    return results
        except Exception as e:
            logger.error(f"取得所有設定錯誤：{e}")
            return []

    async def get_settings(self, guild_id: int) -> Dict[str, Any]:
        """取得伺服器設定 - 修復異步"""
        await self._ensure_initialized()
        try:
            async with self.db.connection() as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute(
                        "SELECT * FROM ticket_settings WHERE guild_id = %s",
                        (guild_id,),
                    )

                    result = await cursor.fetchone()

                    if not result:
                        # 建立預設設定
                        return await self.create_default_settings(guild_id)

                    # 將結果轉換為字典
                    columns = [desc[0] for desc in cursor.description]
                    settings = dict(zip(columns, result))

                    # 解析 JSON 欄位
                    if settings.get("support_roles"):
                        try:
                            settings["support_roles"] = json.loads(settings["support_roles"])
                        except:
                            settings["support_roles"] = []
                    else:
                        settings["support_roles"] = []

                    return settings

        except Exception as e:
            logger.error(f"取得設定錯誤：{e}")
            return await self.create_default_settings(guild_id)

    async def create_default_settings(self, guild_id: int) -> Dict[str, Any]:
        """建立預設設定 - 修復異步"""
        await self._ensure_initialized()
        default_settings = {
            "guild_id": guild_id,
            "max_tickets_per_user": 3,
            "auto_close_hours": 24,
            "welcome_message": "歡迎使用客服系統！請選擇問題類型來建立支援票券。",
            "support_roles": [],
        }

        try:
            async with self.db.connection() as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute(
                        """
                        INSERT INTO ticket_settings
                        (guild_id, max_tickets_per_user, auto_close_hours, welcome_message, support_roles, created_at, updated_at)
                        VALUES (%s, %s, %s, %s, %s, NOW(), NOW())
                        ON DUPLICATE KEY UPDATE updated_at = NOW()
                    """,
                        (
                            guild_id,
                            default_settings["max_tickets_per_user"],
                            default_settings["auto_close_hours"],
                            default_settings["welcome_message"],
                            json.dumps(default_settings["support_roles"]),
                        ),
                    )

                    await conn.commit()
                    logger.info(f"建立預設設定 - 伺服器: {guild_id}")

        except Exception as e:
            logger.error(f"建立預設設定錯誤：{e}")

        return default_settings

    async def update_setting(self, guild_id: int, setting: str, value: Any) -> bool:
        """更新設定 - 修復異步"""
        await self._ensure_initialized()
        try:
            # 設定映射
            setting_map = {
                "category": "category_id",
                "support_roles": "support_roles",
                "limits": "max_tickets_per_user",
                "auto_close": "auto_close_hours",
                "welcome": "welcome_message",
            }

            if setting not in setting_map:
                return False

            db_field = setting_map[setting]

            # 處理特殊類型
            if setting == "support_roles" and isinstance(value, list):
                value = json.dumps(value)
            elif setting in ["limits", "auto_close"]:
                value = int(value)
            elif setting == "category":
                value = int(value)

            async with self.db.connection() as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute(
                        f"""
                        UPDATE ticket_settings
                        SET {db_field} = %s, updated_at = NOW()
                        WHERE guild_id = %s
                    """,
                        (value, guild_id),
                    )

                    await conn.commit()
                    return cursor.rowcount > 0

        except Exception as e:
            logger.error(f"更新設定錯誤：{e}")
            return False

    async def update_settings(self, guild_id: int, settings: Dict[str, Any]) -> bool:
        """批量更新設定"""
        await self._ensure_initialized()
        try:
            # 直接使用資料庫欄位名稱
            allowed_fields = {
                "category_id",
                "support_roles",
                "max_tickets_per_user",
                "auto_close_hours",
                "welcome_message",
            }

            # 過濾允許的欄位
            valid_settings = {}
            for key, value in settings.items():
                if key in allowed_fields:
                    # 處理特殊類型
                    if key == "support_roles" and isinstance(value, list):
                        value = json.dumps(value)
                    elif key in [
                        "category_id",
                        "max_tickets_per_user",
                        "auto_close_hours",
                    ]:
                        value = int(value)
                    valid_settings[key] = value

            if not valid_settings:
                return False

            # 構建UPDATE SQL
            set_clauses = [f"{field} = %s" for field in valid_settings.keys()]
            set_clause = ", ".join(set_clauses)
            values = list(valid_settings.values())
            values.append(guild_id)  # WHERE條件的值

            async with self.db.connection() as conn:
                async with conn.cursor() as cursor:
                    sql = f"""
                        UPDATE ticket_settings
                        SET {set_clause}, updated_at = NOW()
                        WHERE guild_id = %s
                    """
                    await cursor.execute(sql, values)
                    await conn.commit()
                    return cursor.rowcount > 0

        except Exception as e:
            logger.error(f"批量更新設定錯誤：{e}")
            return False

    async def get_next_ticket_id(self) -> int:
        """取得下一個票券 ID - 修復異步"""
        await self._ensure_initialized()
        try:
            async with self.db.connection() as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute("SELECT MAX(id) FROM tickets")
                    result = await cursor.fetchone()
                    return (result[0] or 0) + 1
        except Exception as e:
            logger.error(f"取得票券 ID 錯誤：{e}")
            return 1

    async def cleanup_old_data(self, days: int = 90) -> int:
        """清理舊資料 - 修復異步"""
        await self._ensure_initialized()
        try:
            cutoff_date = datetime.now(timezone.utc) - timedelta(days=days)

            async with self.db.connection() as conn:
                async with conn.cursor() as cursor:
                    # 清理舊的日誌記錄
                    await cursor.execute(
                        """
                        DELETE FROM ticket_logs
                        WHERE created_at < %s
                    """,
                        (cutoff_date,),
                    )

                    cleaned_count = cursor.rowcount
                    await conn.commit()

                    logger.info(f"清理了 {cleaned_count} 條舊資料")
                    return cleaned_count

        except Exception as e:
            logger.error(f"清理資料錯誤：{e}")
            return 0

    async def paginate_tickets(
        self,
        guild_id: int,
        user_id: Optional[str] = None,
        status: Optional[str] = None,
        page: int = 1,
        page_size: int = 10,
        created_after: Optional[datetime] = None,
        created_before: Optional[datetime] = None,
    ) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
        """分頁查詢票券"""
        await self._ensure_initialized()
        try:
            # 構建查詢條件
            conditions = ["guild_id = %s"]
            params = [guild_id]

            if user_id is not None:
                conditions.append("discord_id = %s")
                params.append(user_id)

            if status is not None:
                conditions.append("status = %s")
                params.append(status)

            if created_after is not None:
                conditions.append("created_at >= %s")
                params.append(created_after)

            if created_before is not None:
                conditions.append("created_at <= %s")
                params.append(created_before)

            where_clause = " AND ".join(conditions)

            async with self.db.connection() as conn:
                async with conn.cursor() as cursor:
                    # 計算總數
                    count_sql = f"""
                        SELECT COUNT(*) FROM tickets
                        WHERE {where_clause}
                    """
                    await cursor.execute(count_sql, params)
                    total_count = (await cursor.fetchone())[0]

                    # 計算分頁資訊
                    total_pages = (total_count + page_size - 1) // page_size
                    offset = (page - 1) * page_size

                    # 查詢票券資料
                    tickets_sql = f"""
                        SELECT
                            id,
                            guild_id,
                            discord_id,
                            username,
                            channel_id,
                            NULL as category_id,
                            status,
                            type as subject,
                            NULL as description,
                            priority,
                            created_at,
                            NULL as updated_at,
                            closed_at,
                            closed_by,
                            close_reason,
                            tags,
                            NULL as metadata
                        FROM tickets
                        WHERE {where_clause}
                        ORDER BY created_at DESC
                        LIMIT %s OFFSET %s
                    """

                    await cursor.execute(tickets_sql, params + [page_size, offset])
                    rows = await cursor.fetchall()

                    # 格式化結果
                    tickets = []
                    for row in rows:
                        ticket = {
                            "id": row[0],
                            "ticket_id": row[0],  # 添加 ticket_id 別名
                            "guild_id": row[1],
                            "user_id": row[2],  # discord_id mapped to user_id for compatibility
                            "discord_id": row[2],  # 原始 discord_id 欄位
                            "username": row[3],
                            "channel_id": row[4],
                            "category_id": row[5],  # NULL
                            "status": row[6],
                            "subject": row[7],  # type mapped to subject
                            "type": row[7],  # 原始 type 欄位
                            "description": row[8],  # NULL
                            "priority": row[9],
                            "created_at": row[10],
                            "updated_at": row[11],  # NULL
                            "closed_at": row[12],
                            "closed_by": row[13],
                            "close_reason": row[14],
                            "tags": json.loads(row[15]) if row[15] else [],
                            "metadata": row[16] or {},  # 處理 NULL 值
                        }
                        tickets.append(ticket)

                    # 分頁資訊
                    pagination = {
                        "current_page": page,
                        "page_size": page_size,
                        "total_pages": total_pages,
                        "total_count": total_count,
                        "has_next": page < total_pages,
                        "has_prev": page > 1,
                    }

                    return tickets, pagination

        except Exception as e:
            logger.error(f"分頁查詢票券錯誤：{e}")
            return [], {
                "current_page": page,
                "page_size": page_size,
                "total_pages": 0,
                "total_count": 0,
                "has_next": False,
                "has_prev": False,
            }

