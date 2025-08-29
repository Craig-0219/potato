# bot/db/welcome_dao.py - 歡迎系統資料存取層
"""
歡迎系統資料存取物件
處理歡迎設定、日誌記錄等資料庫操作
"""

import json
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from bot.db.base_dao import BaseDAO
from shared.logger import logger


class WelcomeDAO(BaseDAO):
    """歡迎系統資料存取物件"""

    def __init__(self):
        super().__init__()

    async def _initialize(self):
        """初始化方法 - BaseDAO要求的抽象方法"""

    # ========== 歡迎設定管理 ==========

    async def get_welcome_settings(self, guild_id: int) -> Optional[Dict[str, Any]]:
        """取得伺服器歡迎設定"""
        try:
            async with self.db.connection() as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute(
                        """
                        SELECT guild_id, welcome_channel_id, leave_channel_id,
                               welcome_message, leave_message, welcome_embed_enabled,
                               welcome_dm_enabled, welcome_dm_message, auto_role_enabled,
                               auto_roles, welcome_image_url, welcome_thumbnail_url,
                               welcome_color, is_enabled, created_at, updated_at
                        FROM welcome_settings
                        WHERE guild_id = %s
                    """,
                        (guild_id,),
                    )

                    result = await cursor.fetchone()
                    if result:
                        settings = {
                            "guild_id": result[0],
                            "welcome_channel_id": result[1],
                            "leave_channel_id": result[2],
                            "welcome_message": result[3],
                            "leave_message": result[4],
                            "welcome_embed_enabled": bool(result[5]),
                            "welcome_dm_enabled": bool(result[6]),
                            "welcome_dm_message": result[7],
                            "auto_role_enabled": bool(result[8]),
                            "auto_roles": json.loads(result[9]) if result[9] else [],
                            "welcome_image_url": result[10],
                            "welcome_thumbnail_url": result[11],
                            "welcome_color": result[12],
                            "is_enabled": bool(result[13]),
                            "created_at": result[14],
                            "updated_at": result[15],
                        }
                        return settings

                    return None

        except Exception as e:
            logger.error(f"取得歡迎設定錯誤 (guild_id: {guild_id}): {e}")
            return None

    async def upsert_welcome_settings(
        self, guild_id: int, settings: Dict[str, Any]
    ) -> bool:
        """插入或更新歡迎設定"""
        try:
            # 處理auto_roles JSON序列化
            auto_roles_json = (
                json.dumps(settings.get("auto_roles", []))
                if settings.get("auto_roles")
                else None
            )

            async with self.db.connection() as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute(
                        """
                        INSERT INTO welcome_settings (
                            guild_id, welcome_channel_id, leave_channel_id,
                            welcome_message, leave_message, welcome_embed_enabled,
                            welcome_dm_enabled, welcome_dm_message, auto_role_enabled,
                            auto_roles, welcome_image_url, welcome_thumbnail_url,
                            welcome_color, is_enabled
                        ) VALUES (
                            %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                        ) ON DUPLICATE KEY UPDATE
                            welcome_channel_id = VALUES(welcome_channel_id),
                            leave_channel_id = VALUES(leave_channel_id),
                            welcome_message = VALUES(welcome_message),
                            leave_message = VALUES(leave_message),
                            welcome_embed_enabled = VALUES(welcome_embed_enabled),
                            welcome_dm_enabled = VALUES(welcome_dm_enabled),
                            welcome_dm_message = VALUES(welcome_dm_message),
                            auto_role_enabled = VALUES(auto_role_enabled),
                            auto_roles = VALUES(auto_roles),
                            welcome_image_url = VALUES(welcome_image_url),
                            welcome_thumbnail_url = VALUES(welcome_thumbnail_url),
                            welcome_color = VALUES(welcome_color),
                            is_enabled = VALUES(is_enabled),
                            updated_at = CURRENT_TIMESTAMP
                    """,
                        (
                            guild_id,
                            settings.get("welcome_channel_id"),
                            settings.get("leave_channel_id"),
                            settings.get("welcome_message"),
                            settings.get("leave_message"),
                            settings.get("welcome_embed_enabled", True),
                            settings.get("welcome_dm_enabled", False),
                            settings.get("welcome_dm_message"),
                            settings.get("auto_role_enabled", False),
                            auto_roles_json,
                            settings.get("welcome_image_url"),
                            settings.get("welcome_thumbnail_url"),
                            settings.get("welcome_color", 0x00FF00),
                            settings.get("is_enabled", True),
                        ),
                    )

                    await conn.commit()
                    return True

        except Exception as e:
            logger.error(f"更新歡迎設定錯誤 (guild_id: {guild_id}): {e}")
            return False

    async def update_welcome_channel(
        self, guild_id: int, channel_id: Optional[int]
    ) -> bool:
        """更新歡迎頻道"""
        try:
            async with self.db.connection() as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute(
                        """
                        INSERT INTO welcome_settings (guild_id, welcome_channel_id)
                        VALUES (%s, %s)
                        ON DUPLICATE KEY UPDATE
                            welcome_channel_id = VALUES(welcome_channel_id),
                            updated_at = CURRENT_TIMESTAMP
                    """,
                        (guild_id, channel_id),
                    )

                    await conn.commit()
                    return True

        except Exception as e:
            logger.error(f"更新歡迎頻道錯誤 (guild_id: {guild_id}): {e}")
            return False

    async def update_leave_channel(
        self, guild_id: int, channel_id: Optional[int]
    ) -> bool:
        """更新離開頻道"""
        try:
            async with self.db.connection() as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute(
                        """
                        INSERT INTO welcome_settings (guild_id, leave_channel_id)
                        VALUES (%s, %s)
                        ON DUPLICATE KEY UPDATE
                            leave_channel_id = VALUES(leave_channel_id),
                            updated_at = CURRENT_TIMESTAMP
                    """,
                        (guild_id, channel_id),
                    )

                    await conn.commit()
                    return True

        except Exception as e:
            logger.error(f"更新離開頻道錯誤 (guild_id: {guild_id}): {e}")
            return False

    async def update_auto_roles(self, guild_id: int, role_ids: List[int]) -> bool:
        """更新自動身分組"""
        try:
            auto_roles_json = json.dumps(role_ids) if role_ids else None

            async with self.db.connection() as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute(
                        """
                        INSERT INTO welcome_settings (guild_id, auto_roles, auto_role_enabled)
                        VALUES (%s, %s, %s)
                        ON DUPLICATE KEY UPDATE
                            auto_roles = VALUES(auto_roles),
                            auto_role_enabled = VALUES(auto_role_enabled),
                            updated_at = CURRENT_TIMESTAMP
                    """,
                        (guild_id, auto_roles_json, bool(role_ids)),
                    )

                    await conn.commit()
                    return True

        except Exception as e:
            logger.error(f"更新自動身分組錯誤 (guild_id: {guild_id}): {e}")
            return False

    # ========== 歡迎日誌管理 ==========

    async def log_welcome_event(
        self,
        guild_id: int,
        user_id: int,
        username: str,
        action_type: str,
        welcome_sent: bool = False,
        roles_assigned: List[int] = None,
        dm_sent: bool = False,
        error_message: str = None,
    ) -> Optional[int]:
        """記錄歡迎事件"""
        try:
            roles_json = json.dumps(roles_assigned) if roles_assigned else None

            async with self.db.connection() as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute(
                        """
                        INSERT INTO welcome_logs (
                            guild_id, user_id, username, action_type,
                            welcome_sent, roles_assigned, dm_sent, error_message
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                        (
                            guild_id,
                            user_id,
                            username,
                            action_type,
                            welcome_sent,
                            roles_json,
                            dm_sent,
                            error_message,
                        ),
                    )

                    log_id = cursor.lastrowid
                    await conn.commit()
                    return log_id

        except Exception as e:
            logger.error(f"記錄歡迎事件錯誤: {e}")
            return None

    async def get_welcome_logs(
        self, guild_id: int, limit: int = 50, action_type: str = None
    ) -> List[Dict[str, Any]]:
        """取得歡迎日誌"""
        try:
            async with self.db.connection() as conn:
                async with conn.cursor() as cursor:
                    query = """
                        SELECT id, guild_id, user_id, username, action_type,
                               welcome_sent, roles_assigned, dm_sent, error_message, created_at
                        FROM welcome_logs
                        WHERE guild_id = %s
                    """
                    params = [guild_id]

                    if action_type:
                        query += " AND action_type = %s"
                        params.append(action_type)

                    query += " ORDER BY created_at DESC LIMIT %s"
                    params.append(limit)

                    await cursor.execute(query, params)
                    results = await cursor.fetchall()

                    logs = []
                    for row in results:
                        log = {
                            "id": row[0],
                            "guild_id": row[1],
                            "user_id": row[2],
                            "username": row[3],
                            "action_type": row[4],
                            "welcome_sent": bool(row[5]),
                            "roles_assigned": json.loads(row[6]) if row[6] else [],
                            "dm_sent": bool(row[7]),
                            "error_message": row[8],
                            "created_at": row[9],
                        }
                        logs.append(log)

                    return logs

        except Exception as e:
            logger.error(f"取得歡迎日誌錯誤 (guild_id: {guild_id}): {e}")
            return []

    async def get_welcome_statistics(
        self, guild_id: int, days: int = 30
    ) -> Dict[str, Any]:
        """取得歡迎統計"""
        try:
            end_date = datetime.now(timezone.utc)
            start_date = end_date - timedelta(days=days)

            async with self.db.connection() as conn:
                async with conn.cursor() as cursor:
                    # 基礎統計
                    await cursor.execute(
                        """
                        SELECT
                            COUNT(*) as total_events,
                            SUM(CASE WHEN action_type = 'join' THEN 1 ELSE 0 END) as joins,
                            SUM(CASE WHEN action_type = 'leave' THEN 1 ELSE 0 END) as leaves,
                            SUM(CASE WHEN welcome_sent = 1 THEN 1 ELSE 0 END) as welcome_sent,
                            SUM(CASE WHEN dm_sent = 1 THEN 1 ELSE 0 END) as dm_sent,
                            SUM(CASE WHEN roles_assigned IS NOT NULL AND roles_assigned != '[]' THEN 1 ELSE 0 END) as roles_assigned
                        FROM welcome_logs
                        WHERE guild_id = %s AND created_at >= %s
                    """,
                        (guild_id, start_date),
                    )

                    result = await cursor.fetchone()

                    statistics = {
                        "total_events": result[0] or 0,
                        "joins": result[1] or 0,
                        "leaves": result[2] or 0,
                        "welcome_sent": result[3] or 0,
                        "dm_sent": result[4] or 0,
                        "roles_assigned": result[5] or 0,
                        "period_days": days,
                        "net_growth": (result[1] or 0) - (result[2] or 0),
                    }

                    # 錯誤統計
                    await cursor.execute(
                        """
                        SELECT COUNT(*) as error_count
                        FROM welcome_logs
                        WHERE guild_id = %s AND created_at >= %s AND error_message IS NOT NULL
                    """,
                        (guild_id, start_date),
                    )

                    error_result = await cursor.fetchone()
                    statistics["errors"] = error_result[0] or 0

                    return statistics

        except Exception as e:
            logger.error(f"取得歡迎統計錯誤 (guild_id: {guild_id}): {e}")
            return {}

    # ========== 系統設定管理 ==========

    async def get_system_settings(self, guild_id: int) -> Optional[Dict[str, Any]]:
        """取得系統設定"""
        try:
            async with self.db.connection() as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute(
                        """
                        SELECT general_settings, channel_settings, role_settings,
                               notification_settings, feature_toggles, custom_settings
                        FROM system_settings
                        WHERE guild_id = %s
                    """,
                        (guild_id,),
                    )

                    result = await cursor.fetchone()
                    if result:
                        settings = {
                            "general_settings": (
                                json.loads(result[0]) if result[0] else {}
                            ),
                            "channel_settings": (
                                json.loads(result[1]) if result[1] else {}
                            ),
                            "role_settings": json.loads(result[2]) if result[2] else {},
                            "notification_settings": (
                                json.loads(result[3]) if result[3] else {}
                            ),
                            "feature_toggles": (
                                json.loads(result[4]) if result[4] else {}
                            ),
                            "custom_settings": (
                                json.loads(result[5]) if result[5] else {}
                            ),
                        }
                        return settings

                    return None

        except Exception as e:
            logger.error(f"取得系統設定錯誤 (guild_id: {guild_id}): {e}")
            return None

    async def update_system_settings(
        self, guild_id: int, settings_type: str, settings: Dict[str, Any]
    ) -> bool:
        """更新系統設定"""
        try:
            valid_types = [
                "general_settings",
                "channel_settings",
                "role_settings",
                "notification_settings",
                "feature_toggles",
                "custom_settings",
            ]

            if settings_type not in valid_types:
                logger.error(f"無效的設定類型: {settings_type}")
                return False

            settings_json = json.dumps(settings)

            async with self.db.connection() as conn:
                async with conn.cursor() as cursor:
                    query = f"""
                        INSERT INTO system_settings (guild_id, {settings_type})
                        VALUES (%s, %s)
                        ON DUPLICATE KEY UPDATE
                            {settings_type} = VALUES({settings_type}),
                            updated_at = CURRENT_TIMESTAMP
                    """

                    await cursor.execute(query, (guild_id, settings_json))
                    await conn.commit()
                    return True

        except Exception as e:
            logger.error(
                f"更新系統設定錯誤 (guild_id: {guild_id}, type: {settings_type}): {e}"
            )
            return False

    # ========== 實用工具方法 ==========

    async def is_welcome_enabled(self, guild_id: int) -> bool:
        """檢查歡迎系統是否啟用"""
        try:
            settings = await self.get_welcome_settings(guild_id)
            return settings and settings.get("is_enabled", False)
        except Exception as e:
            logger.error(f"檢查歡迎系統狀態錯誤 (guild_id: {guild_id}): {e}")
            return False

    async def cleanup_old_logs(self, days: int = 90) -> int:
        """清理舊的歡迎日誌"""
        try:
            cutoff_date = datetime.now(timezone.utc) - timedelta(days=days)

            async with self.db.connection() as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute(
                        """
                        DELETE FROM welcome_logs
                        WHERE created_at < %s
                    """,
                        (cutoff_date,),
                    )

                    deleted_count = cursor.rowcount
                    await conn.commit()

                    logger.info(f"清理了 {deleted_count} 條舊的歡迎日誌")
                    return deleted_count

        except Exception as e:
            logger.error(f"清理歡迎日誌錯誤: {e}")
            return 0
