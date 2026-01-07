# bot/db/webhook_dao.py - Webhook資料存取層 v1.7.0
"""
Webhook資料存取層
處理Webhook配置、執行記錄等資料庫操作
"""

import json
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

from potato_bot.db.base_dao import BaseDAO
from potato_shared.logger import logger


class WebhookDAO(BaseDAO):
    """Webhook資料存取物件"""

    def __init__(self):
        super().__init__()
        self._column_checked = False

    async def _initialize(self):
        """初始化資料庫表格"""
        try:
            await self._create_webhook_tables()
            logger.info("✅ Webhook資料庫表格檢查完成")
        except Exception as e:
            logger.error(f"❌ Webhook資料庫檢查失敗: {e}")
            raise

    async def _create_webhook_tables(self):
        """檢查Webhook相關表格"""
        async with self.db.connection() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute("SHOW TABLES LIKE 'webhooks'")
                if not await cursor.fetchone():
                    raise RuntimeError("webhooks 表不存在，請先初始化資料庫")

                await cursor.execute("SHOW TABLES LIKE 'webhook_logs'")
                if not await cursor.fetchone():
                    raise RuntimeError("webhook_logs 表不存在，請先初始化資料庫")

                await cursor.execute("SHOW TABLES LIKE 'webhook_statistics'")
                if not await cursor.fetchone():
                    raise RuntimeError("webhook_statistics 表不存在，請先初始化資料庫")

                # 確保新欄位存在（向後相容：last_triggered）
                await cursor.execute("SHOW COLUMNS FROM webhooks LIKE 'last_triggered'")
                column_exists = await cursor.fetchone()
                if not column_exists:
                    await cursor.execute(
                        "ALTER TABLE webhooks ADD COLUMN last_triggered TIMESTAMP NULL AFTER failure_count"
                    )
                    logger.info("✅ 已補齊 webhooks.last_triggered 欄位")
                self._column_checked = True

                await conn.commit()

    # ========== Webhook CRUD操作 ==========

    async def create_webhook(self, config) -> str:
        """創建Webhook配置"""
        try:
            async with self.db.connection() as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute(
                        """
                        INSERT INTO webhooks (
                            id, name, url, type, events, secret, headers,
                            timeout, retry_count, retry_interval, status,
                            guild_id, created_by
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                        (
                            config.id,
                            config.name,
                            config.url,
                            config.type.value,
                            json.dumps([event.value for event in config.events]),
                            config.secret,
                            json.dumps(config.headers),
                            config.timeout,
                            config.retry_count,
                            config.retry_interval,
                            config.status.value,
                            config.guild_id,
                            config.created_by,
                        ),
                    )

                    await conn.commit()
                    return config.id

        except Exception as e:
            logger.error(f"創建Webhook配置失敗: {e}")
            raise

    async def update_webhook(self, webhook_id: str, updates: Dict[str, Any]) -> bool:
        """更新Webhook配置"""
        try:
            async with self.db.connection() as conn:
                async with conn.cursor() as cursor:
                    set_clauses = []
                    params = []

                    if "name" in updates:
                        set_clauses.append("name = %s")
                        params.append(updates["name"])

                    if "url" in updates:
                        set_clauses.append("url = %s")
                        params.append(updates["url"])

                    if "events" in updates:
                        set_clauses.append("events = %s")
                        params.append(json.dumps(updates["events"]))

                    if "headers" in updates:
                        set_clauses.append("headers = %s")
                        params.append(json.dumps(updates["headers"]))

                    if "timeout" in updates:
                        set_clauses.append("timeout = %s")
                        params.append(updates["timeout"])

                    if "status" in updates:
                        set_clauses.append("status = %s")
                        params.append(updates["status"])

                    if "success_count" in updates:
                        set_clauses.append("success_count = %s")
                        params.append(updates["success_count"])

                    if "failure_count" in updates:
                        set_clauses.append("failure_count = %s")
                        params.append(updates["failure_count"])

                    if "last_triggered" in updates:
                        set_clauses.append("last_triggered = %s")
                        params.append(updates["last_triggered"])

                    if not set_clauses:
                        return True

                    params.append(webhook_id)

                    await cursor.execute(
                        f"UPDATE webhooks SET {', '.join(set_clauses)}, updated_at = CURRENT_TIMESTAMP WHERE id = %s",
                        params,
                    )

                    await conn.commit()
                    return cursor.rowcount > 0

        except Exception as e:
            logger.error(f"更新Webhook配置失敗: {e}")
            return False

    async def get_webhook(self, webhook_id: str) -> Optional[Dict[str, Any]]:
        """獲取單個Webhook配置"""
        try:
            await self._ensure_last_triggered_column()
            async with self.db.connection() as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute(
                        """
                        SELECT id, name, url, type, events, secret, headers,
                               timeout, retry_count, retry_interval, status,
                               guild_id, created_by, created_at, updated_at,
                               last_triggered, success_count, failure_count
                        FROM webhooks WHERE id = %s
                    """,
                        (webhook_id,),
                    )

                    result = await cursor.fetchone()
                    if not result:
                        return None

                    return {
                        "id": result[0],
                        "name": result[1],
                        "url": result[2],
                        "type": result[3],
                        "events": json.loads(result[4]) if result[4] else [],
                        "secret": result[5],
                        "headers": json.loads(result[6]) if result[6] else {},
                        "timeout": result[7],
                        "retry_count": result[8],
                        "retry_interval": result[9],
                        "status": result[10],
                        "guild_id": result[11],
                        "created_by": result[12],
                        "created_at": result[13],
                        "updated_at": result[14],
                        "last_triggered": result[15],
                        "success_count": result[16],
                        "failure_count": result[17],
                    }

        except Exception as e:
            logger.error(f"獲取Webhook配置失敗: {e}")
            return None

    async def get_webhooks(
        self, guild_id: Optional[int] = None, status: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """獲取Webhook列表"""
        try:
            await self._ensure_last_triggered_column()
            conditions = []
            params = []

            if guild_id:
                conditions.append("guild_id = %s")
                params.append(guild_id)

            if status:
                conditions.append("status = %s")
                params.append(status)

            where_clause = "WHERE " + " AND ".join(conditions) if conditions else ""

            async with self.db.connection() as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute(
                        f"""
                        SELECT id, name, url, type, events, status,
                               guild_id, created_by, created_at, updated_at,
                               last_triggered, success_count, failure_count
                        FROM webhooks {where_clause}
                        ORDER BY created_at DESC
                    """,
                        params,
                    )

                    results = await cursor.fetchall()

                    webhooks = []
                    for result in results:
                        webhooks.append(
                            {
                                "id": result[0],
                                "name": result[1],
                                "url": result[2],
                                "type": result[3],
                                "events": (json.loads(result[4]) if result[4] else []),
                                "status": result[5],
                                "guild_id": result[6],
                                "created_by": result[7],
                                "created_at": result[8],
                                "updated_at": result[9],
                                "last_triggered": result[10],
                                "success_count": result[11],
                                "failure_count": result[12],
                            }
                        )

                    return webhooks

        except Exception as e:
            logger.error(f"獲取Webhook列表失敗: {e}")
            return []

    async def _ensure_last_triggered_column(self):
        """確保 last_triggered 欄位存在（防呆）"""
        if self._column_checked:
            return
        async with self.db.connection() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute("SHOW COLUMNS FROM webhooks LIKE 'last_triggered'")
                column_exists = await cursor.fetchone()
                if not column_exists:
                    await cursor.execute(
                        "ALTER TABLE webhooks ADD COLUMN last_triggered TIMESTAMP NULL AFTER failure_count"
                    )
                    logger.info("✅ 已補齊 webhooks.last_triggered 欄位（runtime）")
                self._column_checked = True

    async def get_all_webhooks(self) -> List[Dict[str, Any]]:
        """獲取所有Webhook配置"""
        return await self.get_webhooks()

    async def delete_webhook(self, webhook_id: str) -> bool:
        """刪除Webhook配置"""
        try:
            async with self.db.connection() as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute("DELETE FROM webhooks WHERE id = %s", (webhook_id,))
                    await conn.commit()

                    return cursor.rowcount > 0

        except Exception as e:
            logger.error(f"刪除Webhook配置失敗: {e}")
            return False

    # ========== 執行日誌操作 ==========

    async def log_webhook_execution(self, log_data: Dict[str, Any]) -> int:
        """記錄Webhook執行"""
        try:
            async with self.db.connection() as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute(
                        """
                        INSERT INTO webhook_logs (
                            webhook_id, event_type, direction, payload, response,
                            status, http_status, error_message, execution_time
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                        (
                            log_data["webhook_id"],
                            log_data["event_type"],
                            log_data["direction"],
                            json.dumps(log_data.get("payload", {})),
                            json.dumps(log_data.get("response", {})),
                            log_data["status"],
                            log_data.get("http_status"),
                            log_data.get("error_message"),
                            log_data.get("execution_time", 0.0),
                        ),
                    )

                    log_id = cursor.lastrowid
                    await conn.commit()

                    return log_id

        except Exception as e:
            logger.error(f"記錄Webhook執行失敗: {e}")
            return 0

    async def get_webhook_logs(
        self,
        webhook_id: Optional[str] = None,
        days: int = 7,
        page: int = 1,
        page_size: int = 50,
    ) -> Tuple[List[Dict[str, Any]], int]:
        """獲取Webhook執行日誌"""
        try:
            conditions = []
            params = []

            if webhook_id:
                conditions.append("webhook_id = %s")
                params.append(webhook_id)

            if days > 0:
                start_date = datetime.now(timezone.utc) - timedelta(days=days)
                conditions.append("created_at >= %s")
                params.append(start_date)

            where_clause = "WHERE " + " AND ".join(conditions) if conditions else ""

            async with self.db.connection() as conn:
                async with conn.cursor() as cursor:
                    # 獲取總數
                    count_sql = f"SELECT COUNT(*) FROM webhook_logs {where_clause}"
                    await cursor.execute(count_sql, params)
                    total_count = (await cursor.fetchone())[0]

                    # 獲取分頁數據
                    offset = (page - 1) * page_size
                    params.extend([page_size, offset])

                    data_sql = f"""
                        SELECT l.id, l.webhook_id, w.name as webhook_name, l.event_type,
                               l.direction, l.status, l.http_status, l.error_message,
                               l.execution_time, l.created_at
                        FROM webhook_logs l
                        LEFT JOIN webhooks w ON l.webhook_id = w.id
                        {where_clause}
                        ORDER BY l.created_at DESC
                        LIMIT %s OFFSET %s
                    """

                    await cursor.execute(data_sql, params)
                    results = await cursor.fetchall()

                    logs = []
                    for result in results:
                        logs.append(
                            {
                                "id": result[0],
                                "webhook_id": result[1],
                                "webhook_name": result[2],
                                "event_type": result[3],
                                "direction": result[4],
                                "status": result[5],
                                "http_status": result[6],
                                "error_message": result[7],
                                "execution_time": float(result[8]),
                                "created_at": result[9],
                            }
                        )

                    return logs, total_count

        except Exception as e:
            logger.error(f"獲取Webhook執行日誌失敗: {e}")
            return [], 0

    # ========== 統計操作 ==========

    async def update_webhook_statistics(
        self, webhook_id: str, execution_time: float, success: bool
    ):
        """更新Webhook統計"""
        try:
            today = datetime.now(timezone.utc).date()

            async with self.db.connection() as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute(
                        """
                        INSERT INTO webhook_statistics
                        (webhook_id, date, total_requests, successful_requests, failed_requests, avg_response_time)
                        VALUES (%s, %s, 1, %s, %s, %s)
                        ON DUPLICATE KEY UPDATE
                        total_requests = total_requests + 1,
                        successful_requests = successful_requests + %s,
                        failed_requests = failed_requests + %s,
                        avg_response_time = (avg_response_time * (total_requests - 1) + %s) / total_requests
                    """,
                        (
                            webhook_id,
                            today,
                            1 if success else 0,
                            0 if success else 1,
                            execution_time,
                            1 if success else 0,
                            0 if success else 1,
                            execution_time,
                        ),
                    )

                    # 更新Webhook計數
                    if success:
                        await cursor.execute(
                            """
                            UPDATE webhooks
                            SET success_count = success_count + 1, last_triggered = CURRENT_TIMESTAMP
                            WHERE id = %s
                        """,
                            (webhook_id,),
                        )
                    else:
                        await cursor.execute(
                            """
                            UPDATE webhooks
                            SET failure_count = failure_count + 1
                            WHERE id = %s
                        """,
                            (webhook_id,),
                        )

                    await conn.commit()

        except Exception as e:
            logger.error(f"更新Webhook統計失敗: {e}")

    async def get_webhook_statistics(self, webhook_id: str, days: int = 30) -> Dict[str, Any]:
        """獲取Webhook統計"""
        try:
            end_date = datetime.now(timezone.utc).date()
            start_date = end_date - timedelta(days=days)

            async with self.db.connection() as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute(
                        """
                        SELECT
                            SUM(total_requests) as total_requests,
                            SUM(successful_requests) as successful_requests,
                            SUM(failed_requests) as failed_requests,
                            AVG(avg_response_time) as avg_response_time
                        FROM webhook_statistics
                        WHERE webhook_id = %s AND date BETWEEN %s AND %s
                    """,
                        (webhook_id, start_date, end_date),
                    )

                    result = await cursor.fetchone()

                    return {
                        "webhook_id": webhook_id,
                        "period_days": days,
                        "total_requests": result[0] or 0,
                        "successful_requests": result[1] or 0,
                        "failed_requests": result[2] or 0,
                        "success_rate": ((result[1] / result[0] * 100) if result[0] else 0),
                        "avg_response_time": (float(result[3]) if result[3] else 0.0),
                    }

        except Exception as e:
            logger.error(f"獲取Webhook統計失敗: {e}")
            return {}

    # ========== 清理操作 ==========

    async def cleanup_old_logs(self, days: int = 30) -> int:
        """清理舊的執行日誌"""
        try:
            cutoff_date = datetime.now(timezone.utc) - timedelta(days=days)

            async with self.db.connection() as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute(
                        """
                        DELETE FROM webhook_logs WHERE created_at < %s
                    """,
                        (cutoff_date,),
                    )

                    deleted_count = cursor.rowcount
                    await conn.commit()

                    logger.info(f"清理了 {deleted_count} 條Webhook執行日誌")
                    return deleted_count

        except Exception as e:
            logger.error(f"清理Webhook日誌失敗: {e}")
            return 0
