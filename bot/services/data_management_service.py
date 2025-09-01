# bot/services/data_management_service.py - v1.0.0
# 🗄️ 數據管理服務
# Data Management Service for GDPR Compliance

import hashlib
import json
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

import aiomysql

from bot.db.pool import db_pool
from bot.services.guild_permission_manager import (
    GuildPermission,
    guild_permission_manager,
)

logger = logging.getLogger(__name__)


class DataRetentionPolicy(Enum):
    """數據保留政策"""

    IMMEDIATE = "immediate"  # 立即刪除
    SHORT_TERM = "short_term"  # 30 天
    MEDIUM_TERM = "medium_term"  # 90 天
    LONG_TERM = "long_term"  # 365 天
    PERMANENT = "permanent"  # 永久保存


class ExportFormat(Enum):
    """導出格式"""

    JSON = "json"
    CSV = "csv"
    XML = "xml"


@dataclass
class DataExportRequest:
    """數據導出請求"""

    guild_id: int
    user_id: int
    data_types: List[str]
    format: ExportFormat
    include_personal_data: bool = True
    include_system_logs: bool = False
    date_range: Optional[tuple] = None
    request_time: datetime = None

    def __post_init__(self):
        if self.request_time is None:
            self.request_time = datetime.now(timezone.utc)


class DataManagementService:
    """數據管理服務 - GDPR 合規"""

    def __init__(self):
        self.db = db_pool
        self.permission_manager = guild_permission_manager

        # 定義數據表分類和保留政策
        self.table_policies = {
            # 用戶個人數據 - 嚴格 GDPR 管理
            "personal_data": {
                "tables": [
                    "api_users",
                    "user_mfa",
                    "guild_user_permissions",
                    "user_sessions",
                ],
                "retention": DataRetentionPolicy.MEDIUM_TERM,
                "requires_consent": True,
                "auto_anonymize": True,
            },
            # 業務數據 - 中期保留
            "business_data": {
                "tables": [
                    "tickets",
                    "votes",
                    "vote_responses",
                    "workflows",
                    "workflow_executions",
                ],
                "retention": DataRetentionPolicy.LONG_TERM,
                "requires_consent": False,
                "auto_anonymize": False,
            },
            # 系統日誌 - 安全需要
            "system_logs": {
                "tables": [
                    "ticket_logs",
                    "security_events",
                    "data_access_logs",
                    "guild_event_logs",
                ],
                "retention": DataRetentionPolicy.LONG_TERM,
                "requires_consent": False,
                "auto_anonymize": True,
            },
            # 統計數據 - 匿名化保存
            "analytics_data": {
                "tables": [
                    "guild_statistics",
                    "ticket_statistics_cache",
                    "tag_usage_stats",
                ],
                "retention": DataRetentionPolicy.PERMANENT,
                "requires_consent": False,
                "auto_anonymize": True,
            },
            # 設定數據 - 中期保留
            "configuration_data": {
                "tables": [
                    "ticket_settings",
                    "vote_settings",
                    "welcome_settings",
                    "guild_settings",
                ],
                "retention": DataRetentionPolicy.LONG_TERM,
                "requires_consent": False,
                "auto_anonymize": False,
            },
        }

    async def export_guild_data(
        self, export_request: DataExportRequest
    ) -> Dict[str, Any]:
        """導出伺服器數據 (GDPR Article 20)"""
        try:
            # 驗證權限
            if not await self.permission_manager.check_permission(
                export_request.user_id,
                export_request.guild_id,
                GuildPermission.DATA_EXPORT,
            ):
                raise PermissionError("用戶沒有導出數據的權限")

            logger.info(f"開始導出伺服器 {export_request.guild_id} 的數據")

            export_data = {
                "export_metadata": {
                    "guild_id": export_request.guild_id,
                    "export_date": export_request.request_time.isoformat(),
                    "format": export_request.format.value,
                    "data_types": export_request.data_types,
                    "requested_by": export_request.user_id,
                },
                "data": {},
            }

            # 導出各類數據
            for data_type in export_request.data_types:
                if data_type in self.table_policies:
                    policy = self.table_policies[data_type]
                    data_category = {}

                    for table in policy["tables"]:
                        table_data = await self._export_table_data(
                            table, export_request.guild_id, export_request
                        )
                        if table_data:
                            data_category[table] = table_data

                    if data_category:
                        export_data["data"][data_type] = data_category

            # 記錄導出事件
            await self._log_export_event(
                export_request, len(export_data["data"])
            )

            # 根據格式處理數據
            if export_request.format == ExportFormat.JSON:
                return export_data
            elif export_request.format == ExportFormat.CSV:
                return await self._convert_to_csv(export_data)
            elif export_request.format == ExportFormat.XML:
                return await self._convert_to_xml(export_data)

        except Exception as e:
            logger.error(f"❌ 數據導出失敗: {e}")
            await self._log_export_event(export_request, 0, error=str(e))
            raise

    async def _export_table_data(
        self, table: str, guild_id: int, export_request: DataExportRequest
    ) -> List[Dict]:
        """導出特定表格數據"""
        try:
            # 建構查詢條件
            additional_where = {}

            # 日期範圍過濾
            if export_request.date_range:
                start_date, end_date = export_request.date_range
                if self._has_date_column(table):
                    additional_where.update(
                        {
                            "created_at >=": start_date,
                            "created_at <=": end_date,
                        }
                    )

            # 個人數據過濾
            if (
                not export_request.include_personal_data
                and self._is_personal_data_table(table)
            ):
                return []

            # 系統日誌過濾
            if (
                not export_request.include_system_logs
                and self._is_system_log_table(table)
            ):
                return []

            # 建構安全查詢
            query, params = self.query_builder.build_select(
                table=table,
                guild_id=guild_id,
                additional_where=additional_where,
            )
            query += " ORDER BY created_at DESC LIMIT 10000"  # 限制導出數量

            async with self.db.connection() as conn:
                async with conn.cursor(aiomysql.DictCursor) as cursor:
                    await cursor.execute(query, params)
                    results = await cursor.fetchall()

                    # 處理敏感數據
                    processed_results = []
                    for row in results:
                        processed_row = dict(row)
                        processed_row = await self._anonymize_if_needed(
                            processed_row, table
                        )
                        processed_results.append(processed_row)

                    return processed_results

        except Exception as e:
            logger.error(f"❌ 導出表格 {table} 失敗: {e}")
            return []

    async def delete_guild_data(
        self,
        guild_id: int,
        user_id: int,
        data_types: List[str] = None,
        hard_delete: bool = False,
    ) -> Dict[str, Any]:
        """刪除伺服器數據 (GDPR Article 17)"""
        try:
            # 驗證權限
            if not await self.permission_manager.check_permission(
                user_id, guild_id, GuildPermission.DATA_DELETE
            ):
                raise PermissionError("用戶沒有刪除數據的權限")

            logger.info(f"開始刪除伺服器 {guild_id} 的數據")

            deletion_summary = {
                "guild_id": guild_id,
                "deletion_date": datetime.now(timezone.utc).isoformat(),
                "deleted_by": user_id,
                "hard_delete": hard_delete,
                "deleted_records": {},
                "retained_records": {},
            }

            # 如果沒有指定，則刪除所有可刪除的數據
            if not data_types:
                data_types = list(self.table_policies.keys())

            for data_type in data_types:
                if data_type in self.table_policies:
                    policy = self.table_policies[data_type]

                    for table in policy["tables"]:
                        try:
                            if hard_delete or data_type == "personal_data":
                                # 硬刪除
                                deleted_count = (
                                    await self._hard_delete_table_data(
                                        table, guild_id
                                    )
                                )
                                deletion_summary["deleted_records"][
                                    table
                                ] = deleted_count
                            else:
                                # 軟刪除或匿名化
                                if policy["auto_anonymize"]:
                                    anonymized_count = (
                                        await self._anonymize_table_data(
                                            table, guild_id
                                        )
                                    )
                                    deletion_summary["retained_records"][
                                        table
                                    ] = f"{anonymized_count} 筆已匿名化"
                                else:
                                    archived_count = (
                                        await self._archive_table_data(
                                            table, guild_id
                                        )
                                    )
                                    deletion_summary["retained_records"][
                                        table
                                    ] = f"{archived_count} 筆已歸檔"

                        except Exception as e:
                            logger.error(f"❌ 處理表格 {table} 失敗: {e}")
                            continue

            # 記錄刪除事件
            await self._log_deletion_event(guild_id, user_id, deletion_summary)

            logger.info(f"✅ 伺服器 {guild_id} 數據刪除完成")
            return deletion_summary

        except Exception as e:
            logger.error(f"❌ 數據刪除失敗: {e}")
            raise

    async def _hard_delete_table_data(self, table: str, guild_id: int) -> int:
        """硬刪除表格數據"""
        try:
            query, params = self.query_builder.build_delete(
                table=table, where_conditions={}, guild_id=guild_id
            )

            async with self.db.connection() as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute(query, params)
                    deleted_count = cursor.rowcount
                    await conn.commit()

                    logger.info(f"✅ 硬刪除 {table}: {deleted_count} 筆記錄")
                    return deleted_count

        except Exception as e:
            logger.error(f"❌ 硬刪除 {table} 失敗: {e}")
            return 0

    async def _anonymize_table_data(self, table: str, guild_id: int) -> int:
        """匿名化表格數據"""
        try:
            # 定義需要匿名化的欄位
            anonymize_fields = {
                "discord_id": f"anon_user_{hashlib.sha256(str(guild_id).encode()).hexdigest()[:16]}",
                "username": "Anonymous User",
                "discord_username": "Anonymous#0000",
                "ip_address": "0.0.0.0",
                "user_agent": "Anonymized",
                "email": "anonymous@example.com",
            }

            # 檢查表格有哪些欄位需要匿名化
            async with self.db.connection() as conn:
                async with conn.cursor() as cursor:
                    # 獲取表格結構
                    await cursor.execute(f"SHOW COLUMNS FROM {table}")
                    columns = [row[0] for row in await cursor.fetchall()]

                    # 建構更新查詢
                    update_fields = {}
                    for field, anon_value in anonymize_fields.items():
                        if field in columns:
                            update_fields[field] = anon_value

                    if update_fields:
                        query, params = self.query_builder.build_update(
                            table=table,
                            data=update_fields,
                            where_conditions={},
                            guild_id=guild_id,
                        )

                        await cursor.execute(query, params)
                        anonymized_count = cursor.rowcount
                        await conn.commit()

                        logger.info(
                            f"✅ 匿名化 {table}: {anonymized_count} 筆記錄"
                        )
                        return anonymized_count

                    return 0

        except Exception as e:
            logger.error(f"❌ 匿名化 {table} 失敗: {e}")
            return 0

    async def _archive_table_data(self, table: str, guild_id: int) -> int:
        """歸檔表格數據"""
        try:
            # 移動數據到歷史表
            archive_table = f"{table}_archive"

            async with self.db.connection() as conn:
                async with conn.cursor() as cursor:
                    # 檢查歷史表是否存在
                    await cursor.execute(
                        f"""
                        CREATE TABLE IF NOT EXISTS {archive_table}
                        LIKE {table}
                    """
                    )

                    # 移動數據
                    if "guild_id" in await self._get_table_columns(table):
                        await cursor.execute(
                            f"""
                            INSERT INTO {archive_table}
                            SELECT * FROM {table}
                            WHERE guild_id = %s
                        """,
                            (guild_id,),
                        )

                        archived_count = cursor.rowcount

                        # 刪除原始數據
                        query, params = self.query_builder.build_delete(
                            table=table, where_conditions={}, guild_id=guild_id
                        )
                        await cursor.execute(query, params)

                        await conn.commit()

                        logger.info(
                            f"✅ 歸檔 {table}: {archived_count} 筆記錄"
                        )
                        return archived_count

                    return 0

        except Exception as e:
            logger.error(f"❌ 歸檔 {table} 失敗: {e}")
            return 0

    async def schedule_data_cleanup(self):
        """排程數據清理任務"""
        try:
            logger.info("🧹 開始執行數據清理任務")

            current_time = datetime.now(timezone.utc)
            cleanup_summary = {}

            for data_type, policy in self.table_policies.items():
                if policy["retention"] == DataRetentionPolicy.PERMANENT:
                    continue

                # 計算保留期限
                retention_days = {
                    DataRetentionPolicy.IMMEDIATE: 0,
                    DataRetentionPolicy.SHORT_TERM: 30,
                    DataRetentionPolicy.MEDIUM_TERM: 90,
                    DataRetentionPolicy.LONG_TERM: 365,
                }

                cutoff_date = current_time - timedelta(
                    days=retention_days[policy["retention"]]
                )

                for table in policy["tables"]:
                    try:
                        cleaned_count = await self._cleanup_expired_data(
                            table, cutoff_date
                        )
                        if cleaned_count > 0:
                            cleanup_summary[table] = cleaned_count

                    except Exception as e:
                        logger.error(f"❌ 清理表格 {table} 失敗: {e}")
                        continue

            # 記錄清理結果
            if cleanup_summary:
                logger.info(f"✅ 數據清理完成: {cleanup_summary}")
            else:
                logger.info("✅ 沒有需要清理的過期數據")

            return cleanup_summary

        except Exception as e:
            logger.error(f"❌ 數據清理任務失敗: {e}")
            return {}

    async def _cleanup_expired_data(
        self, table: str, cutoff_date: datetime
    ) -> int:
        """清理過期數據"""
        try:
            # 檢查表格是否有時間欄位
            date_column = await self._get_date_column(table)
            if not date_column:
                return 0

            async with self.db.connection() as conn:
                async with conn.cursor() as cursor:
                    # 刪除過期數據
                    await cursor.execute(
                        f"""
                        DELETE FROM {table}
                        WHERE {date_column} < %s
                    """,
                        (cutoff_date,),
                    )

                    cleaned_count = cursor.rowcount
                    await conn.commit()

                    if cleaned_count > 0:
                        logger.info(
                            f"✅ 清理 {table} 過期數據: {cleaned_count} 筆"
                        )

                    return cleaned_count

        except Exception as e:
            logger.error(f"❌ 清理 {table} 過期數據失敗: {e}")
            return 0

    async def _get_table_columns(self, table: str) -> List[str]:
        """獲取表格欄位列表"""
        try:
            async with self.db.connection() as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute(f"SHOW COLUMNS FROM {table}")
                    columns = [row[0] for row in await cursor.fetchall()]
                    return columns
        except Exception as e:
            logger.error(f"❌ 獲取 {table} 欄位失敗: {e}")
            return []

    async def _get_date_column(self, table: str) -> Optional[str]:
        """獲取表格的時間欄位"""
        date_columns = [
            "created_at",
            "timestamp",
            "updated_at",
            "last_activity",
        ]
        columns = await self._get_table_columns(table)

        for date_col in date_columns:
            if date_col in columns:
                return date_col

        return None

    def _has_date_column(self, table: str) -> bool:
        """檢查表格是否有時間欄位"""
        # 這裡可以根據已知的表格結構返回
        return True  # 大多數表格都有 created_at

    def _is_personal_data_table(self, table: str) -> bool:
        """檢查是否為個人數據表格"""
        return table in self.table_policies["personal_data"]["tables"]

    def _is_system_log_table(self, table: str) -> bool:
        """檢查是否為系統日誌表格"""
        return table in self.table_policies["system_logs"]["tables"]

    async def _anonymize_if_needed(self, row: Dict, table: str) -> Dict:
        """根據需要匿名化數據"""
        if not self._is_personal_data_table(table):
            return row

        # 匿名化個人識別資訊
        if "discord_id" in row:
            row["discord_id"] = (
                f"anon_{hashlib.sha256(str(row['discord_id']).encode()).hexdigest()[:16]}"
            )
        if "username" in row:
            row["username"] = "Anonymous User"
        if "discord_username" in row:
            row["discord_username"] = "Anonymous#0000"
        if "ip_address" in row:
            row["ip_address"] = "0.0.0.0"

        return row

    async def _convert_to_csv(self, data: Dict) -> str:
        """轉換為 CSV 格式"""
        # 簡化版，實際實現需要更完整的 CSV 處理
        import io

        output = io.StringIO()
        # 這裡需要實現完整的 CSV 轉換邏輯
        return output.getvalue()

    async def _convert_to_xml(self, data: Dict) -> str:
        """轉換為 XML 格式"""
        # 簡化版，實際實現需要 XML 生成
        return f"<export>{json.dumps(data, indent=2, ensure_ascii=False)}</export>"

    async def _log_export_event(
        self,
        export_request: DataExportRequest,
        exported_categories: int,
        error: str = None,
    ):
        """記錄導出事件"""
        try:
            event_data = {
                "guild_id": export_request.guild_id,
                "user_id": export_request.user_id,
                "event_type": "data_export",
                "event_category": "data_management",
                "event_name": "GDPR Data Export",
                "description": f"用戶請求導出數據，格式: {export_request.format.value}",
                "metadata": json.dumps(
                    {
                        "data_types": export_request.data_types,
                        "exported_categories": exported_categories,
                        "include_personal_data": export_request.include_personal_data,
                        "error": error,
                    }
                ),
                "source": "data_management_service",
                "status": "failed" if error else "success",
            }

            columns = ", ".join(event_data.keys())
            placeholders = ", ".join(["%s"] * len(event_data))

            async with self.db.connection() as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute(
                        f"""
                        INSERT INTO guild_event_logs ({columns})
                        VALUES ({placeholders})
                    """,
                        list(event_data.values()),
                    )
                    await conn.commit()

        except Exception as e:
            logger.error(f"❌ 記錄導出事件失敗: {e}")

    async def _log_deletion_event(
        self, guild_id: int, user_id: int, summary: Dict
    ):
        """記錄刪除事件"""
        try:
            event_data = {
                "guild_id": guild_id,
                "user_id": user_id,
                "event_type": "data_deletion",
                "event_category": "data_management",
                "event_name": "GDPR Data Deletion",
                "description": "用戶請求刪除數據 (被遺忘權)",
                "metadata": json.dumps(summary),
                "source": "data_management_service",
                "status": "success",
            }

            columns = ", ".join(event_data.keys())
            placeholders = ", ".join(["%s"] * len(event_data))

            async with self.db.connection() as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute(
                        f"""
                        INSERT INTO guild_event_logs ({columns})
                        VALUES ({placeholders})
                    """,
                        list(event_data.values()),
                    )
                    await conn.commit()

        except Exception as e:
            logger.error(f"❌ 記錄刪除事件失敗: {e}")


# 全域實例
data_management_service = DataManagementService()
