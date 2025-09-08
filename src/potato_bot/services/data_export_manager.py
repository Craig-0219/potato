# bot/services/data_export_manager.py
"""
資料匯出管理器
支援多種格式的資料匯出功能 (CSV, JSON, Excel)
"""

import asyncio
import csv
import json
import zipfile
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

import aiomysql

try:
    import pandas as pd

    HAS_PANDAS = True
except ImportError:
    HAS_PANDAS = False

from potato_bot.db.pool import db_pool
from potato_shared.logger import logger


@dataclass
class ExportRequest:
    """匯出請求資料類別"""

    data_type: str  # 'tickets', 'users', 'votes', 'logs', 'statistics'
    format: str  # 'csv', 'json', 'excel'
    guild_id: Optional[int] = None
    requested_by: int = 0
    days_back: int = 30
    filters: Optional[Dict[str, Any]] = None
    date_range: Optional[tuple] = None
    include_fields: Optional[List[str]] = None
    exclude_fields: Optional[List[str]] = None
    limit: Optional[int] = None

    # 支援舊的參數名稱以保持相容性
    @property
    def export_type(self) -> str:
        return self.data_type

    @property
    def requester_id(self) -> int:
        return self.requested_by


@dataclass
class ExportResult:
    """匯出結果資料類別"""

    success: bool
    file_path: Optional[str] = None
    file_size: int = 0
    record_count: int = 0
    export_time: float = 0.0
    error_message: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None

    # 提供視圖中使用的屬性名稱
    @property
    def total_records(self) -> int:
        return self.record_count

    @property
    def file_size_mb(self) -> float:
        return self.file_size / (1024 * 1024) if self.file_size else 0.0

    @property
    def export_time_seconds(self) -> float:
        return self.export_time

    @property
    def error(self) -> Optional[str]:
        return self.error_message


class DataExportManager:
    """資料匯出管理器"""

    def __init__(self, export_dir: Optional[str] = None):
        self.db = db_pool
        self.export_dir = Path(export_dir or "exports")
        self.export_dir.mkdir(exist_ok=True)

        # 支援的匯出類型
        self.export_handlers = {
            "tickets": self._export_tickets,
            "users": self._export_users,
            "votes": self._export_votes,
            "logs": self._export_logs,
            "statistics": self._export_statistics,
            "analytics": self._export_analytics,
            "assignments": self._export_assignments,
            "tags": self._export_tags,
            "webhooks": self._export_webhooks,
            "security_events": self._export_security_events,
        }

    async def export_data(self, request: ExportRequest) -> ExportResult:
        """執行資料匯出"""
        start_time = datetime.now()

        try:
            logger.info(f"🚀 開始匯出 {request.export_type} 資料 ({request.format} 格式)")

            # 檢查匯出類型是否支援
            if request.export_type not in self.export_handlers:
                return ExportResult(
                    success=False,
                    error_message=f"不支援的匯出類型: {request.export_type}",
                )

            # 檢查格式是否支援
            if request.format not in ["csv", "json", "excel"]:
                return ExportResult(
                    success=False,
                    error_message=f"不支援的匯出格式: {request.format}",
                )

            # 執行資料查詢
            handler = self.export_handlers[request.export_type]
            data, metadata = await handler(request)

            if not data:
                return ExportResult(success=False, error_message="沒有找到符合條件的資料")

            # 生成檔案名稱
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"{request.export_type}_{timestamp}.{request.format}"
            file_path = self.export_dir / filename

            # 匯出資料
            actual_file_path = await self._write_export_file(
                data, file_path, request.format, metadata
            )

            # 如果檔案路徑被更改（例如 Excel 降級為 CSV），使用實際的檔案路徑
            if actual_file_path:
                file_path = Path(actual_file_path)

            # 計算匯出時間和檔案大小
            export_time = (datetime.now() - start_time).total_seconds()
            file_size = file_path.stat().st_size

            # 記錄匯出日誌
            await self._log_export(request, str(file_path), len(data), export_time)

            logger.info(f"✅ 匯出完成: {filename} ({file_size} bytes, {len(data)} 條記錄)")

            return ExportResult(
                success=True,
                file_path=str(file_path),
                file_size=file_size,
                record_count=len(data),
                export_time=export_time,
                metadata=metadata,
            )

        except Exception as e:
            logger.error(f"❌ 匯出失敗: {e}", exc_info=True)
            return ExportResult(success=False, error_message=str(e))

    async def _export_tickets(self, request: ExportRequest) -> tuple[List[Dict], Dict]:
        """匯出票券資料"""
        query_parts = ["SELECT * FROM tickets WHERE 1=1"]
        params = []

        # 日期範圍篩選
        if request.date_range:
            start_date, end_date = request.date_range
            query_parts.append("AND created_at BETWEEN %s AND %s")
            params.extend([start_date, end_date])

        # 伺服器篩選
        if request.guild_id:
            query_parts.append("AND guild_id = %s")
            params.append(request.guild_id)

        # 其他篩選條件
        if request.filters:
            if "status" in request.filters:
                query_parts.append("AND status = %s")
                params.append(request.filters["status"])

            if "priority" in request.filters:
                query_parts.append("AND priority = %s")
                params.append(request.filters["priority"])

            if "assigned_to" in request.filters:
                query_parts.append("AND assigned_to = %s")
                params.append(request.filters["assigned_to"])

        # 限制數量
        if request.limit:
            query_parts.append("LIMIT %s")
            params.append(request.limit)

        query = " ".join(query_parts)

        async with self.db.connection() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cursor:
                await cursor.execute(query, params)
                tickets = await cursor.fetchall()

                # 獲取相關的標籤資訊
                for ticket in tickets:
                    try:
                        tag_query = """
                        SELECT tt.name FROM ticket_tags tt
                        JOIN ticket_tag_mappings ttm ON tt.id = ttm.tag_id
                        WHERE ttm.ticket_id = %s
                        """
                        await cursor.execute(tag_query, (ticket["id"],))
                        tags = await cursor.fetchall()
                        ticket["tags"] = [tag["name"] for tag in tags] if tags else []
                    except Exception:
                        # 如果標籤查詢失敗，設為空列表
                        ticket["tags"] = []

        # 元資料
        metadata = {
            "export_type": "tickets",
            "total_records": len(tickets),
            "filters_applied": request.filters or {},
            "date_range": request.date_range,
            "export_timestamp": datetime.now().isoformat(),
        }

        return tickets, metadata

    async def _export_users(self, request: ExportRequest) -> tuple[List[Dict], Dict]:
        """匯出用戶資料"""
        # 從票券系統中提取用戶統計資料
        query = """
        SELECT
            discord_id,
            COALESCE(discord_username, username) as discord_username,
            COUNT(*) as total_tickets,
            COUNT(CASE WHEN status = 'open' THEN 1 END) as open_tickets,
            COUNT(CASE WHEN status = 'closed' THEN 1 END) as closed_tickets,
            AVG(CASE WHEN rating IS NOT NULL THEN rating END) as avg_rating,
            MIN(created_at) as first_ticket_date,
            MAX(created_at) as last_ticket_date
        FROM tickets
        WHERE 1=1
        """
        params = []

        if request.guild_id:
            query += " AND guild_id = %s"
            params.append(request.guild_id)

        if request.date_range:
            start_date, end_date = request.date_range
            query += " AND created_at BETWEEN %s AND %s"
            params.extend([start_date, end_date])

        query += " GROUP BY discord_id, COALESCE(discord_username, username)"

        if request.limit:
            query += " LIMIT %s"
            params.append(request.limit)

        async with self.db.connection() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cursor:
                await cursor.execute(query, params)
                users = await cursor.fetchall()

        metadata = {
            "export_type": "users",
            "total_records": len(users),
            "export_timestamp": datetime.now().isoformat(),
        }

        return users, metadata

    async def _export_votes(self, request: ExportRequest) -> tuple[List[Dict], Dict]:
        """匯出投票資料"""
        query = """
        SELECT
            v.*,
            COUNT(vr.id) as total_responses,
            vo.option_text,
            COUNT(CASE WHEN vr.vote_option_id = vo.id THEN 1 END) as option_votes
        FROM votes v
        LEFT JOIN vote_responses vr ON v.id = vr.vote_id
        LEFT JOIN vote_options vo ON v.id = vo.vote_id
        WHERE 1=1
        """
        params = []

        if request.guild_id:
            query += " AND v.guild_id = %s"
            params.append(request.guild_id)

        if request.date_range:
            start_date, end_date = request.date_range
            query += " AND v.created_at BETWEEN %s AND %s"
            params.extend([start_date, end_date])

        query += " GROUP BY v.id, vo.id"

        if request.limit:
            query += " LIMIT %s"
            params.append(request.limit)

        async with self.db.connection() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cursor:
                await cursor.execute(query, params)
                votes = await cursor.fetchall()

        metadata = {
            "export_type": "votes",
            "total_records": len(votes),
            "export_timestamp": datetime.now().isoformat(),
        }

        return votes, metadata

    async def _export_logs(self, request: ExportRequest) -> tuple[List[Dict], Dict]:
        """匯出日誌資料"""
        # 合併多個日誌表的資料
        queries = [
            ("ticket_logs", "SELECT * FROM ticket_logs WHERE 1=1"),
            ("system_logs", "SELECT * FROM system_logs WHERE 1=1"),
            ("security_events", "SELECT * FROM security_events WHERE 1=1"),
        ]

        all_logs = []
        params = []

        # 構建日期篩選
        date_filter = ""
        if request.date_range:
            start_date, end_date = request.date_range
            date_filter = " AND created_at BETWEEN %s AND %s"
            params.extend([start_date, end_date])

        async with self.db.connection() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cursor:
                for log_type, base_query in queries:
                    try:
                        query = base_query + date_filter
                        if request.limit:
                            query += " LIMIT %s"
                            current_params = params + [request.limit // len(queries)]
                        else:
                            current_params = params

                        await cursor.execute(query, current_params)
                        logs = await cursor.fetchall()

                        # 添加日誌類型標識
                        for log in logs:
                            log["log_type"] = log_type
                            all_logs.append(log)

                    except Exception as e:
                        logger.warning(f"讀取 {log_type} 日誌時出錯: {e}")
                        continue

        # 按時間排序
        all_logs.sort(key=lambda x: x.get("created_at", datetime.min), reverse=True)

        metadata = {
            "export_type": "logs",
            "total_records": len(all_logs),
            "log_types_included": [q[0] for q in queries],
            "export_timestamp": datetime.now().isoformat(),
        }

        return all_logs, metadata

    async def _export_statistics(self, request: ExportRequest) -> tuple[List[Dict], Dict]:
        """匯出統計資料"""
        statistics = []

        async with self.db.connection() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cursor:
                # 票券統計
                ticket_stats_query = """
                SELECT
                    'ticket_statistics' as stat_type,
                    guild_id,
                    COUNT(*) as total_count,
                    COUNT(CASE WHEN status = 'open' THEN 1 END) as open_count,
                    COUNT(CASE WHEN status = 'closed' THEN 1 END) as closed_count,
                    COUNT(CASE WHEN priority = 'high' THEN 1 END) as high_priority,
                    COUNT(CASE WHEN priority = 'medium' THEN 1 END) as medium_priority,
                    COUNT(CASE WHEN priority = 'low' THEN 1 END) as low_priority,
                    AVG(CASE WHEN rating IS NOT NULL THEN rating END) as avg_rating,
                    DATE(created_at) as stat_date
                FROM tickets
                WHERE 1=1
                """
                params = []

                if request.guild_id:
                    ticket_stats_query += " AND guild_id = %s"
                    params.append(request.guild_id)

                if request.date_range:
                    start_date, end_date = request.date_range
                    ticket_stats_query += " AND created_at BETWEEN %s AND %s"
                    params.extend([start_date, end_date])

                ticket_stats_query += " GROUP BY guild_id, DATE(created_at)"

                await cursor.execute(ticket_stats_query, params)
                ticket_stats = await cursor.fetchall()
                statistics.extend(ticket_stats)

                # 投票統計
                vote_stats_query = """
                SELECT
                    'vote_statistics' as stat_type,
                    guild_id,
                    COUNT(*) as total_votes,
                    COUNT(CASE WHEN status = 'active' THEN 1 END) as active_votes,
                    COUNT(CASE WHEN status = 'closed' THEN 1 END) as closed_votes,
                    AVG(total_responses) as avg_responses,
                    DATE(created_at) as stat_date
                FROM votes
                WHERE 1=1
                """
                params = []

                if request.guild_id:
                    vote_stats_query += " AND guild_id = %s"
                    params.append(request.guild_id)

                if request.date_range:
                    start_date, end_date = request.date_range
                    vote_stats_query += " AND created_at BETWEEN %s AND %s"
                    params.extend([start_date, end_date])

                vote_stats_query += " GROUP BY guild_id, DATE(created_at)"

                await cursor.execute(vote_stats_query, params)
                vote_stats = await cursor.fetchall()
                statistics.extend(vote_stats)

        metadata = {
            "export_type": "statistics",
            "total_records": len(statistics),
            "statistics_types": ["ticket_statistics", "vote_statistics"],
            "export_timestamp": datetime.now().isoformat(),
        }

        return statistics, metadata

    async def _export_analytics(self, request: ExportRequest) -> tuple[List[Dict], Dict]:
        """匯出分析資料"""
        analytics = []

        async with self.db.connection() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cursor:
                # 每日趨勢分析
                trend_query = """
                SELECT
                    DATE(created_at) as date,
                    'daily_trend' as analytics_type,
                    COUNT(*) as ticket_count,
                    COUNT(CASE WHEN status = 'closed' THEN 1 END) as closed_count,
                    AVG(CASE WHEN closed_at IS NOT NULL AND created_at IS NOT NULL
                        THEN TIMESTAMPDIFF(HOUR, created_at, closed_at) END) as avg_resolution_hours
                FROM tickets
                WHERE created_at >= DATE_SUB(NOW(), INTERVAL 30 DAY)
                """
                params = []

                if request.guild_id:
                    trend_query += " AND guild_id = %s"
                    params.append(request.guild_id)

                trend_query += " GROUP BY DATE(created_at) ORDER BY date DESC"

                await cursor.execute(trend_query, params)
                trends = await cursor.fetchall()
                analytics.extend(trends)

                # 工作負載分析
                workload_query = """
                SELECT
                    assigned_to,
                    'workload_analysis' as analytics_type,
                    COUNT(*) as assigned_tickets,
                    COUNT(CASE WHEN status = 'closed' THEN 1 END) as completed_tickets,
                    AVG(CASE WHEN rating IS NOT NULL THEN rating END) as avg_rating,
                    AVG(CASE WHEN closed_at IS NOT NULL AND created_at IS NOT NULL
                        THEN TIMESTAMPDIFF(HOUR, created_at, closed_at) END) as avg_resolution_hours
                FROM tickets
                WHERE assigned_to IS NOT NULL
                """
                params = []

                if request.guild_id:
                    workload_query += " AND guild_id = %s"
                    params.append(request.guild_id)

                workload_query += " GROUP BY assigned_to"

                await cursor.execute(workload_query, params)
                workloads = await cursor.fetchall()
                analytics.extend(workloads)

        metadata = {
            "export_type": "analytics",
            "total_records": len(analytics),
            "analytics_types": ["daily_trend", "workload_analysis"],
            "export_timestamp": datetime.now().isoformat(),
        }

        return analytics, metadata

    async def _export_assignments(self, request: ExportRequest) -> tuple[List[Dict], Dict]:
        """匯出指派記錄"""
        query = """
        SELECT
            ah.*,
            t.title as ticket_title,
            t.status as current_status,
            t.priority as ticket_priority
        FROM assignment_history ah
        LEFT JOIN tickets t ON ah.ticket_id = t.id
        WHERE 1=1
        """
        params = []

        if request.guild_id:
            query += " AND t.guild_id = %s"
            params.append(request.guild_id)

        if request.date_range:
            start_date, end_date = request.date_range
            query += " AND ah.assigned_at BETWEEN %s AND %s"
            params.extend([start_date, end_date])

        query += " ORDER BY ah.assigned_at DESC"

        if request.limit:
            query += " LIMIT %s"
            params.append(request.limit)

        async with self.db.connection() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cursor:
                await cursor.execute(query, params)
                assignments = await cursor.fetchall()

        metadata = {
            "export_type": "assignments",
            "total_records": len(assignments),
            "export_timestamp": datetime.now().isoformat(),
        }

        return assignments, metadata

    async def _export_tags(self, request: ExportRequest) -> tuple[List[Dict], Dict]:
        """匯出標籤資料"""
        query = """
        SELECT
            tt.*,
            COUNT(ttm.ticket_id) as usage_count,
            tus.usage_stats
        FROM ticket_tags tt
        LEFT JOIN ticket_tag_mappings ttm ON tt.id = ttm.tag_id
        LEFT JOIN tag_usage_stats tus ON tt.id = tus.tag_id
        WHERE 1=1
        """
        params = []

        if request.guild_id:
            query += " AND tt.guild_id = %s"
            params.append(request.guild_id)

        query += " GROUP BY tt.id ORDER BY usage_count DESC"

        async with self.db.connection() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cursor:
                await cursor.execute(query, params)
                tags = await cursor.fetchall()

        metadata = {
            "export_type": "tags",
            "total_records": len(tags),
            "export_timestamp": datetime.now().isoformat(),
        }

        return tags, metadata

    async def _export_webhooks(self, request: ExportRequest) -> tuple[List[Dict], Dict]:
        """匯出 Webhook 配置"""
        query = "SELECT * FROM webhook_configs WHERE 1=1"
        params = []

        if request.guild_id:
            query += " AND guild_id = %s"
            params.append(request.guild_id)

        # 移除敏感資訊
        async with self.db.connection() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cursor:
                await cursor.execute(query, params)
                webhooks = await cursor.fetchall()

                # 隱藏敏感的 URL 和 token 資訊
                for webhook in webhooks:
                    if "webhook_url" in webhook and webhook["webhook_url"]:
                        webhook["webhook_url"] = "***REDACTED***"
                    if "secret_token" in webhook and webhook["secret_token"]:
                        webhook["secret_token"] = "***REDACTED***"

        metadata = {
            "export_type": "webhooks",
            "total_records": len(webhooks),
            "note": "Sensitive information has been redacted",
            "export_timestamp": datetime.now().isoformat(),
        }

        return webhooks, metadata

    async def _export_security_events(self, request: ExportRequest) -> tuple[List[Dict], Dict]:
        """匯出安全事件"""
        query = "SELECT * FROM security_events WHERE 1=1"
        params = []

        if request.guild_id:
            query += " AND guild_id = %s"
            params.append(request.guild_id)

        if request.date_range:
            start_date, end_date = request.date_range
            query += " AND created_at BETWEEN %s AND %s"
            params.extend([start_date, end_date])

        # 只匯出非敏感的安全事件
        if not request.filters or not request.filters.get("include_sensitive"):
            query += " AND event_type NOT IN ('password_reset', 'token_refresh', 'private_message')"

        query += " ORDER BY created_at DESC"

        if request.limit:
            query += " LIMIT %s"
            params.append(request.limit)

        async with self.db.connection() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cursor:
                await cursor.execute(query, params)
                events = await cursor.fetchall()

        metadata = {
            "export_type": "security_events",
            "total_records": len(events),
            "filtered_sensitive": not (
                request.filters and request.filters.get("include_sensitive")
            ),
            "export_timestamp": datetime.now().isoformat(),
        }

        return events, metadata

    async def _write_export_file(
        self, data: List[Dict], file_path: Path, format: str, metadata: Dict
    ):
        """寫入匯出檔案"""
        if format == "csv":
            await self._write_csv(data, file_path, metadata)
            return str(file_path)
        elif format == "json":
            await self._write_json(data, file_path, metadata)
            return str(file_path)
        elif format == "excel":
            actual_path = await self._write_excel(data, file_path, metadata)
            return actual_path or str(file_path)

    async def _write_csv(self, data: List[Dict], file_path: Path, metadata: Dict):
        """寫入 CSV 檔案"""
        if not data:
            return

        # 使用 asyncio 在執行緒中執行 CSV 寫入
        def write_csv_sync():
            # 使用 utf-8-sig 編碼，包含 BOM 頭，確保 Excel 能正確識別 UTF-8 編碼
            with open(file_path, "w", newline="", encoding="utf-8-sig") as csvfile:
                if data:
                    fieldnames = list(data[0].keys())
                    writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                    writer.writeheader()

                    for row in data:
                        # 處理複雜的資料類型
                        processed_row = {}
                        for key, value in row.items():
                            if isinstance(value, (list, dict)):
                                processed_row[key] = json.dumps(value, ensure_ascii=False)
                            elif isinstance(value, datetime):
                                processed_row[key] = value.isoformat()
                            else:
                                processed_row[key] = value
                        writer.writerow(processed_row)

        await asyncio.get_event_loop().run_in_executor(None, write_csv_sync)

    async def _write_json(self, data: List[Dict], file_path: Path, metadata: Dict):
        """寫入 JSON 檔案"""

        def write_json_sync():
            export_data = {"metadata": metadata, "data": data}

            with open(file_path, "w", encoding="utf-8") as jsonfile:
                json.dump(
                    export_data,
                    jsonfile,
                    ensure_ascii=False,
                    indent=2,
                    default=str,
                )

        await asyncio.get_event_loop().run_in_executor(None, write_json_sync)

    async def _write_excel(self, data: List[Dict], file_path: Path, metadata: Dict):
        """寫入 Excel 檔案"""
        if not HAS_PANDAS:
            # 降級到 CSV 格式
            csv_path = file_path.with_suffix(".csv")
            await self._write_csv(data, csv_path, metadata)
            logger.warning("pandas 未安裝，Excel 匯出降級為 CSV 格式")
            # 返回實際創建的檔案路徑
            return str(csv_path)

        def write_excel_sync():
            # 處理資料中的複雜類型
            processed_data = []
            for row in data:
                processed_row = {}
                for key, value in row.items():
                    if isinstance(value, (list, dict)):
                        processed_row[key] = json.dumps(value, ensure_ascii=False)
                    elif isinstance(value, datetime):
                        processed_row[key] = value.isoformat()
                    else:
                        processed_row[key] = value
                processed_data.append(processed_row)

            # 創建 DataFrame，確保正確處理中文
            df = pd.DataFrame(processed_data)

            # 寫入 Excel，使用 openpyxl 引擎確保中文支援
            with pd.ExcelWriter(file_path, engine="openpyxl") as writer:
                # 寫入主要資料
                df.to_excel(writer, sheet_name="票券資料", index=False)

                # 添加元資料工作表
                metadata_df = pd.DataFrame(
                    [
                        {
                            "匯出類型": metadata.get("export_type", ""),
                            "總記錄數": metadata.get("total_records", 0),
                            "匯出時間": metadata.get("export_timestamp", ""),
                            "日期範圍": str(metadata.get("date_range", "全部")),
                            "篩選條件": json.dumps(
                                metadata.get("filters_applied", {}),
                                ensure_ascii=False,
                            ),
                        }
                    ]
                )
                metadata_df.to_excel(writer, sheet_name="匯出資訊", index=False)

                # 自動調整列寬
                for sheet_name in writer.sheets:
                    worksheet = writer.sheets[sheet_name]
                    for col in worksheet.columns:
                        max_length = 0
                        column = col[0].column_letter
                        for cell in col:
                            try:
                                if len(str(cell.value)) > max_length:
                                    max_length = len(str(cell.value))
                            except:
                                pass
                        adjusted_width = min(max_length + 2, 50)  # 限制最大寬度
                        worksheet.column_dimensions[column].width = adjusted_width

        await asyncio.get_event_loop().run_in_executor(None, write_excel_sync)
        return str(file_path)

    async def _log_export(
        self,
        request: ExportRequest,
        file_path: str,
        record_count: int,
        export_time: float,
    ):
        """記錄匯出日誌"""
        try:
            async with self.db.connection() as conn:
                async with conn.cursor() as cursor:
                    # 創建匯出日誌表
                    create_table_query = """
                    CREATE TABLE IF NOT EXISTS export_logs (
                        id INT AUTO_INCREMENT PRIMARY KEY,
                        export_type VARCHAR(50) NOT NULL,
                        format VARCHAR(10) NOT NULL,
                        file_path TEXT NOT NULL,
                        record_count INT DEFAULT 0,
                        file_size BIGINT DEFAULT 0,
                        export_time DECIMAL(10,3) DEFAULT 0.000,
                        requester_id BIGINT DEFAULT 0,
                        guild_id BIGINT,
                        filters JSON,
                        date_range_start DATETIME,
                        date_range_end DATETIME,
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
                    """
                    await cursor.execute(create_table_query)

                    # 插入日誌記錄
                    file_size = Path(file_path).stat().st_size if Path(file_path).exists() else 0

                    insert_query = """
                    INSERT INTO export_logs
                    (export_type, format, file_path, record_count, file_size, export_time,
                     requester_id, guild_id, filters, date_range_start, date_range_end)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """

                    filters_json = json.dumps(request.filters) if request.filters else None
                    date_start = request.date_range[0] if request.date_range else None
                    date_end = request.date_range[1] if request.date_range else None

                    await cursor.execute(
                        insert_query,
                        (
                            request.export_type,
                            request.format,
                            file_path,
                            record_count,
                            file_size,
                            export_time,
                            request.requester_id,
                            request.guild_id,
                            filters_json,
                            date_start,
                            date_end,
                        ),
                    )

                    await conn.commit()

        except Exception as e:
            logger.error(f"記錄匯出日誌失敗: {e}")

    async def create_bulk_export(
        self,
        export_types: List[str],
        format: str = "json",
        guild_id: Optional[int] = None,
        date_range: Optional[tuple] = None,
    ) -> ExportResult:
        """創建批量匯出（ZIP 壓縮檔）"""
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            zip_filename = f"bulk_export_{timestamp}.zip"
            zip_path = self.export_dir / zip_filename

            total_records = 0
            successful_exports = 0

            with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zipf:
                for export_type in export_types:
                    try:
                        request = ExportRequest(
                            export_type=export_type,
                            format=format,
                            guild_id=guild_id,
                            date_range=date_range,
                        )

                        result = await self.export_data(request)
                        if result.success and result.file_path:
                            # 添加檔案到 ZIP
                            arcname = f"{export_type}.{format}"
                            zipf.write(result.file_path, arcname)
                            total_records += result.record_count
                            successful_exports += 1

                            # 刪除臨時檔案
                            Path(result.file_path).unlink()

                    except Exception as e:
                        logger.error(f"批量匯出 {export_type} 失敗: {e}")
                        continue

                # 添加摘要資訊
                summary = {
                    "bulk_export_summary": {
                        "timestamp": datetime.now().isoformat(),
                        "total_export_types": len(export_types),
                        "successful_exports": successful_exports,
                        "failed_exports": len(export_types) - successful_exports,
                        "total_records": total_records,
                        "export_types": export_types,
                        "guild_id": guild_id,
                        "date_range": date_range,
                    }
                }

                zipf.writestr(
                    "export_summary.json",
                    json.dumps(summary, ensure_ascii=False, indent=2, default=str),
                )

            file_size = zip_path.stat().st_size

            logger.info(
                f"✅ 批量匯出完成: {zip_filename} ({successful_exports}/{len(export_types)} 成功)"
            )

            return ExportResult(
                success=True,
                file_path=str(zip_path),
                file_size=file_size,
                record_count=total_records,
                metadata={
                    "export_type": "bulk_export",
                    "successful_exports": successful_exports,
                    "total_export_types": len(export_types),
                },
            )

        except Exception as e:
            logger.error(f"❌ 批量匯出失敗: {e}")
            return ExportResult(success=False, error_message=str(e))

    async def get_export_history(
        self, days: int = 30, guild_id: Optional[int] = None
    ) -> List[Dict]:
        """獲取匯出歷史記錄"""
        try:
            cutoff_date = datetime.now() - timedelta(days=days)

            query = """
            SELECT * FROM export_logs
            WHERE created_at >= %s
            """
            params = [cutoff_date]

            if guild_id:
                query += " AND guild_id = %s"
                params.append(guild_id)

            query += " ORDER BY created_at DESC"

            async with self.db.connection() as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute(query, params)
                    return await cursor.fetchall()

        except Exception as e:
            logger.error(f"獲取匯出歷史失敗: {e}")
            return []

    async def cleanup_old_exports(self, days: int = 7) -> int:
        """清理舊的匯出檔案"""
        try:
            cutoff_date = datetime.now() - timedelta(days=days)
            deleted_count = 0

            for file_path in self.export_dir.iterdir():
                if file_path.is_file():
                    file_time = datetime.fromtimestamp(file_path.stat().st_mtime)
                    if file_time < cutoff_date:
                        try:
                            file_path.unlink()
                            deleted_count += 1
                            logger.info(f"🗑️ 已刪除舊匯出檔案: {file_path.name}")
                        except Exception as e:
                            logger.warning(f"刪除檔案 {file_path.name} 失敗: {e}")

            return deleted_count

        except Exception as e:
            logger.error(f"清理舊匯出檔案失敗: {e}")
            return 0
