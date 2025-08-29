# bot/db/security_dao.py - 安全審計數據存取層 v1.7.0
"""
安全審計數據存取層
處理安全事件、審計日誌、合規報告等數據庫操作
"""

import json
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Tuple

from bot.db.base_dao import BaseDAO
from shared.logger import logger


class SecurityDAO(BaseDAO):
    """安全審計數據存取物件"""

    def __init__(self):
        super().__init__()

    async def _initialize(self):
        """初始化資料庫表格"""
        try:
            await self._create_security_tables()
            logger.info("✅ 安全審計資料庫表格初始化完成")
        except Exception as e:
            logger.error(f"❌ 安全審計資料庫初始化失敗: {e}")
            raise

    async def _create_security_tables(self):
        """創建安全審計相關表格"""
        async with self.db.connection() as conn:
            async with conn.cursor() as cursor:

                # 安全事件日誌表
                await cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS security_events (
                        id VARCHAR(36) PRIMARY KEY,
                        event_type VARCHAR(50) NOT NULL,
                        timestamp TIMESTAMP NOT NULL,
                        user_id BIGINT NOT NULL,
                        guild_id BIGINT NULL,
                        risk_level ENUM('low', 'medium', 'high', 'critical') DEFAULT 'low',
                        action VARCHAR(20) NOT NULL,
                        resource VARCHAR(255) NOT NULL,
                        details JSON,
                        ip_address VARCHAR(45) NULL,
                        user_agent TEXT NULL,
                        session_id VARCHAR(36) NULL,
                        correlation_id VARCHAR(36) NULL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

                        INDEX idx_event_type (event_type),
                        INDEX idx_timestamp (timestamp),
                        INDEX idx_user_id (user_id),
                        INDEX idx_guild_id (guild_id),
                        INDEX idx_risk_level (risk_level),
                        INDEX idx_session_id (session_id),
                        INDEX idx_correlation_id (correlation_id),
                        INDEX idx_created_at (created_at)
                    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
                """
                )

                # 安全規則表
                await cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS security_rules (
                        id VARCHAR(36) PRIMARY KEY,
                        name VARCHAR(255) NOT NULL,
                        description TEXT,
                        rule_type VARCHAR(50) NOT NULL,
                        conditions JSON NOT NULL,
                        actions JSON NOT NULL,
                        enabled BOOLEAN DEFAULT TRUE,
                        severity ENUM('low', 'medium', 'high', 'critical') DEFAULT 'medium',
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                        created_by BIGINT DEFAULT 0,
                        updated_by BIGINT DEFAULT 0,
                        last_triggered TIMESTAMP NULL,
                        trigger_count INT DEFAULT 0,

                        INDEX idx_rule_type (rule_type),
                        INDEX idx_enabled (enabled),
                        INDEX idx_severity (severity),
                        INDEX idx_created_by (created_by),
                        INDEX idx_last_triggered (last_triggered)
                    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
                """
                )

                # 安全警報表
                await cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS security_alerts (
                        id VARCHAR(36) PRIMARY KEY,
                        rule_id VARCHAR(36) NOT NULL,
                        event_id VARCHAR(36) NOT NULL,
                        alert_type VARCHAR(50) NOT NULL,
                        severity ENUM('low', 'medium', 'high', 'critical') DEFAULT 'medium',
                        title VARCHAR(255) NOT NULL,
                        description TEXT,
                        status ENUM('open', 'investigating', 'resolved', 'false_positive') DEFAULT 'open',
                        assigned_to BIGINT NULL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                        resolved_at TIMESTAMP NULL,
                        resolution_note TEXT NULL,

                        INDEX idx_rule_id (rule_id),
                        INDEX idx_event_id (event_id),
                        INDEX idx_severity (severity),
                        INDEX idx_status (status),
                        INDEX idx_assigned_to (assigned_to),
                        INDEX idx_created_at (created_at),

                        FOREIGN KEY (rule_id) REFERENCES security_rules(id) ON DELETE CASCADE,
                        FOREIGN KEY (event_id) REFERENCES security_events(id) ON DELETE CASCADE
                    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
                """
                )

                # 用戶會話表
                await cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS user_sessions (
                        id VARCHAR(36) PRIMARY KEY,
                        user_id BIGINT NOT NULL,
                        guild_id BIGINT NULL,
                        session_start TIMESTAMP NOT NULL,
                        session_end TIMESTAMP NULL,
                        ip_address VARCHAR(45) NULL,
                        user_agent TEXT NULL,
                        is_active BOOLEAN DEFAULT TRUE,
                        last_activity TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        activity_count INT DEFAULT 0,
                        risk_score DECIMAL(3,2) DEFAULT 0.00,

                        INDEX idx_user_id (user_id),
                        INDEX idx_guild_id (guild_id),
                        INDEX idx_session_start (session_start),
                        INDEX idx_is_active (is_active),
                        INDEX idx_last_activity (last_activity),
                        INDEX idx_risk_score (risk_score)
                    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
                """
                )

                # 合規報告表
                await cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS compliance_reports (
                        id VARCHAR(36) PRIMARY KEY,
                        standard VARCHAR(20) NOT NULL,
                        period_start DATE NOT NULL,
                        period_end DATE NOT NULL,
                        guild_id BIGINT NOT NULL,
                        generated_by BIGINT NOT NULL,
                        generated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        summary JSON,
                        violations JSON,
                        recommendations JSON,
                        status ENUM('draft', 'final', 'archived') DEFAULT 'draft',
                        file_path VARCHAR(500) NULL,

                        INDEX idx_standard (standard),
                        INDEX idx_guild_id (guild_id),
                        INDEX idx_generated_by (generated_by),
                        INDEX idx_generated_at (generated_at),
                        INDEX idx_status (status),
                        INDEX idx_period (period_start, period_end)
                    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
                """
                )

                # 權限變更歷史表
                await cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS permission_history (
                        id INT AUTO_INCREMENT PRIMARY KEY,
                        user_id BIGINT NOT NULL,
                        guild_id BIGINT NOT NULL,
                        changed_by BIGINT NOT NULL,
                        change_type ENUM('role_added', 'role_removed', 'permission_granted', 'permission_revoked') NOT NULL,
                        old_permissions JSON,
                        new_permissions JSON,
                        reason TEXT NULL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

                        INDEX idx_user_id (user_id),
                        INDEX idx_guild_id (guild_id),
                        INDEX idx_changed_by (changed_by),
                        INDEX idx_change_type (change_type),
                        INDEX idx_created_at (created_at)
                    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
                """
                )

                # 資料存取日誌表
                await cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS data_access_logs (
                        id VARCHAR(36) PRIMARY KEY,
                        user_id BIGINT NOT NULL,
                        guild_id BIGINT NULL,
                        table_name VARCHAR(100) NOT NULL,
                        operation ENUM('SELECT', 'INSERT', 'UPDATE', 'DELETE') NOT NULL,
                        record_count INT DEFAULT 0,
                        query_hash VARCHAR(64) NULL,
                        execution_time DECIMAL(8,3) DEFAULT 0.000,
                        filters JSON,
                        sensitive_data BOOLEAN DEFAULT FALSE,
                        accessed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

                        INDEX idx_user_id (user_id),
                        INDEX idx_guild_id (guild_id),
                        INDEX idx_table_name (table_name),
                        INDEX idx_operation (operation),
                        INDEX idx_sensitive_data (sensitive_data),
                        INDEX idx_accessed_at (accessed_at)
                    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
                """
                )

                await conn.commit()

    # ========== 安全事件操作 ==========

    async def create_security_event(self, event_data: Dict[str, Any]) -> str:
        """創建安全事件記錄"""
        try:
            async with self.db.connection() as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute(
                        """
                        INSERT INTO security_events (
                            id, event_type, timestamp, user_id, guild_id, risk_level,
                            action, resource, details, ip_address, user_agent,
                            session_id, correlation_id
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                        (
                            event_data["id"],
                            event_data["event_type"],
                            event_data["timestamp"],
                            event_data["user_id"],
                            event_data.get("guild_id"),
                            event_data["risk_level"],
                            event_data["action"],
                            event_data["resource"],
                            json.dumps(event_data.get("details", {})),
                            event_data.get("ip_address"),
                            event_data.get("user_agent"),
                            event_data.get("session_id"),
                            event_data.get("correlation_id"),
                        ),
                    )

                    await conn.commit()
                    return event_data["id"]

        except Exception as e:
            logger.error(f"創建安全事件記錄失敗: {e}")
            raise

    async def get_security_events(
        self,
        guild_id: int = None,
        user_id: int = None,
        event_type: str = None,
        risk_level: str = None,
        start_date: datetime = None,
        end_date: datetime = None,
        page: int = 1,
        page_size: int = 50,
    ) -> Tuple[List[Dict[str, Any]], int]:
        """獲取安全事件列表"""
        try:
            conditions = []
            params = []

            if guild_id:
                conditions.append("guild_id = %s")
                params.append(guild_id)

            if user_id:
                conditions.append("user_id = %s")
                params.append(user_id)

            if event_type:
                conditions.append("event_type = %s")
                params.append(event_type)

            if risk_level:
                conditions.append("risk_level = %s")
                params.append(risk_level)

            if start_date:
                conditions.append("timestamp >= %s")
                params.append(start_date)

            if end_date:
                conditions.append("timestamp <= %s")
                params.append(end_date)

            where_clause = "WHERE " + " AND ".join(conditions) if conditions else ""

            async with self.db.connection() as conn:
                async with conn.cursor() as cursor:
                    # 獲取總數
                    count_sql = f"SELECT COUNT(*) FROM security_events {where_clause}"
                    await cursor.execute(count_sql, params)
                    total_count = (await cursor.fetchone())[0]

                    # 獲取分頁數據
                    offset = (page - 1) * page_size
                    params.extend([page_size, offset])

                    data_sql = f"""
                        SELECT id, event_type, timestamp, user_id, guild_id, risk_level,
                               action, resource, details, ip_address, user_agent,
                               session_id, correlation_id, created_at
                        FROM security_events {where_clause}
                        ORDER BY timestamp DESC
                        LIMIT %s OFFSET %s
                    """

                    await cursor.execute(data_sql, params)
                    results = await cursor.fetchall()

                    events = []
                    for result in results:
                        events.append(
                            {
                                "id": result[0],
                                "event_type": result[1],
                                "timestamp": result[2],
                                "user_id": result[3],
                                "guild_id": result[4],
                                "risk_level": result[5],
                                "action": result[6],
                                "resource": result[7],
                                "details": json.loads(result[8]) if result[8] else {},
                                "ip_address": result[9],
                                "user_agent": result[10],
                                "session_id": result[11],
                                "correlation_id": result[12],
                                "created_at": result[13],
                            }
                        )

                    return events, total_count

        except Exception as e:
            logger.error(f"獲取安全事件列表失敗: {e}")
            return [], 0

    # ========== 安全規則操作 ==========

    async def create_security_rule(self, rule_data: Dict[str, Any]) -> str:
        """創建安全規則"""
        try:
            async with self.db.connection() as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute(
                        """
                        INSERT INTO security_rules (
                            id, name, description, rule_type, conditions, actions,
                            enabled, severity, created_by
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                        (
                            rule_data["id"],
                            rule_data["name"],
                            rule_data.get("description", ""),
                            rule_data["rule_type"],
                            json.dumps(rule_data["conditions"]),
                            json.dumps(rule_data["actions"]),
                            rule_data.get("enabled", True),
                            rule_data["severity"],
                            rule_data.get("created_by", 0),
                        ),
                    )

                    await conn.commit()
                    return rule_data["id"]

        except Exception as e:
            logger.error(f"創建安全規則失敗: {e}")
            raise

    async def get_security_rules(
        self, enabled_only: bool = False
    ) -> List[Dict[str, Any]]:
        """獲取安全規則列表"""
        try:
            async with self.db.connection() as conn:
                async with conn.cursor() as cursor:
                    sql = """
                        SELECT id, name, description, rule_type, conditions, actions,
                               enabled, severity, created_at, updated_at, created_by,
                               last_triggered, trigger_count
                        FROM security_rules
                    """

                    params = []
                    if enabled_only:
                        sql += " WHERE enabled = %s"
                        params.append(True)

                    sql += " ORDER BY severity DESC, created_at DESC"

                    await cursor.execute(sql, params)
                    results = await cursor.fetchall()

                    rules = []
                    for result in results:
                        rules.append(
                            {
                                "id": result[0],
                                "name": result[1],
                                "description": result[2],
                                "rule_type": result[3],
                                "conditions": json.loads(result[4]),
                                "actions": json.loads(result[5]),
                                "enabled": result[6],
                                "severity": result[7],
                                "created_at": result[8],
                                "updated_at": result[9],
                                "created_by": result[10],
                                "last_triggered": result[11],
                                "trigger_count": result[12],
                            }
                        )

                    return rules

        except Exception as e:
            logger.error(f"獲取安全規則列表失敗: {e}")
            return []

    async def update_rule_trigger_stats(self, rule_id: str):
        """更新規則觸發統計"""
        try:
            async with self.db.connection() as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute(
                        """
                        UPDATE security_rules
                        SET last_triggered = CURRENT_TIMESTAMP,
                            trigger_count = trigger_count + 1
                        WHERE id = %s
                    """,
                        (rule_id,),
                    )

                    await conn.commit()

        except Exception as e:
            logger.error(f"更新規則觸發統計失敗: {e}")

    # ========== 安全警報操作 ==========

    async def create_security_alert(self, alert_data: Dict[str, Any]) -> str:
        """創建安全警報"""
        try:
            async with self.db.connection() as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute(
                        """
                        INSERT INTO security_alerts (
                            id, rule_id, event_id, alert_type, severity,
                            title, description, status, assigned_to
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                        (
                            alert_data["id"],
                            alert_data["rule_id"],
                            alert_data["event_id"],
                            alert_data["alert_type"],
                            alert_data["severity"],
                            alert_data["title"],
                            alert_data.get("description", ""),
                            alert_data.get("status", "open"),
                            alert_data.get("assigned_to"),
                        ),
                    )

                    await conn.commit()
                    return alert_data["id"]

        except Exception as e:
            logger.error(f"創建安全警報失敗: {e}")
            raise

    async def get_active_alerts(
        self, guild_id: int = None, severity: str = None
    ) -> List[Dict[str, Any]]:
        """獲取活躍的安全警報"""
        try:
            conditions = ["status IN ('open', 'investigating')"]
            params = []

            if guild_id:
                conditions.append("e.guild_id = %s")
                params.append(guild_id)

            if severity:
                conditions.append("a.severity = %s")
                params.append(severity)

            where_clause = " AND ".join(conditions)

            async with self.db.connection() as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute(
                        f"""
                        SELECT a.id, a.rule_id, a.event_id, a.alert_type, a.severity,
                               a.title, a.description, a.status, a.assigned_to,
                               a.created_at, r.name as rule_name, e.user_id, e.guild_id
                        FROM security_alerts a
                        LEFT JOIN security_rules r ON a.rule_id = r.id
                        LEFT JOIN security_events e ON a.event_id = e.id
                        WHERE {where_clause}
                        ORDER BY a.severity DESC, a.created_at DESC
                        LIMIT 100
                    """,
                        params,
                    )

                    results = await cursor.fetchall()

                    alerts = []
                    for result in results:
                        alerts.append(
                            {
                                "id": result[0],
                                "rule_id": result[1],
                                "event_id": result[2],
                                "alert_type": result[3],
                                "severity": result[4],
                                "title": result[5],
                                "description": result[6],
                                "status": result[7],
                                "assigned_to": result[8],
                                "created_at": result[9],
                                "rule_name": result[10],
                                "user_id": result[11],
                                "guild_id": result[12],
                            }
                        )

                    return alerts

        except Exception as e:
            logger.error(f"獲取活躍警報失敗: {e}")
            return []

    # ========== 用戶會話操作 ==========

    async def create_user_session(self, session_data: Dict[str, Any]) -> str:
        """創建用戶會話記錄"""
        try:
            async with self.db.connection() as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute(
                        """
                        INSERT INTO user_sessions (
                            id, user_id, guild_id, session_start, ip_address, user_agent
                        ) VALUES (%s, %s, %s, %s, %s, %s)
                    """,
                        (
                            session_data["id"],
                            session_data["user_id"],
                            session_data.get("guild_id"),
                            session_data["session_start"],
                            session_data.get("ip_address"),
                            session_data.get("user_agent"),
                        ),
                    )

                    await conn.commit()
                    return session_data["id"]

        except Exception as e:
            logger.error(f"創建用戶會話記錄失敗: {e}")
            raise

    async def update_session_activity(
        self, session_id: str, activity_count: int = 1, risk_score: float = 0.0
    ):
        """更新會話活動"""
        try:
            async with self.db.connection() as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute(
                        """
                        UPDATE user_sessions
                        SET last_activity = CURRENT_TIMESTAMP,
                            activity_count = activity_count + %s,
                            risk_score = GREATEST(risk_score, %s)
                        WHERE id = %s
                    """,
                        (activity_count, risk_score, session_id),
                    )

                    await conn.commit()

        except Exception as e:
            logger.error(f"更新會話活動失敗: {e}")

    # ========== 合規報告操作 ==========

    async def create_compliance_report(self, report_data: Dict[str, Any]) -> str:
        """創建合規報告"""
        try:
            async with self.db.connection() as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute(
                        """
                        INSERT INTO compliance_reports (
                            id, standard, period_start, period_end, guild_id,
                            generated_by, summary, violations, recommendations
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                        (
                            report_data["id"],
                            report_data["standard"],
                            report_data["period_start"].date(),
                            report_data["period_end"].date(),
                            report_data["guild_id"],
                            report_data["generated_by"],
                            json.dumps(report_data["summary"]),
                            json.dumps(report_data["violations"]),
                            json.dumps(report_data["recommendations"]),
                        ),
                    )

                    await conn.commit()
                    return report_data["id"]

        except Exception as e:
            logger.error(f"創建合規報告失敗: {e}")
            raise

    async def get_compliance_reports(
        self, guild_id: int, standard: str = None
    ) -> List[Dict[str, Any]]:
        """獲取合規報告列表"""
        try:
            conditions = ["guild_id = %s"]
            params = [guild_id]

            if standard:
                conditions.append("standard = %s")
                params.append(standard)

            where_clause = " AND ".join(conditions)

            async with self.db.connection() as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute(
                        f"""
                        SELECT id, standard, period_start, period_end, generated_by,
                               generated_at, summary, violations, recommendations, status
                        FROM compliance_reports
                        WHERE {where_clause}
                        ORDER BY generated_at DESC
                        LIMIT 50
                    """,
                        params,
                    )

                    results = await cursor.fetchall()

                    reports = []
                    for result in results:
                        reports.append(
                            {
                                "id": result[0],
                                "standard": result[1],
                                "period_start": result[2],
                                "period_end": result[3],
                                "generated_by": result[4],
                                "generated_at": result[5],
                                "summary": json.loads(result[6]) if result[6] else {},
                                "violations": (
                                    json.loads(result[7]) if result[7] else []
                                ),
                                "recommendations": (
                                    json.loads(result[8]) if result[8] else []
                                ),
                                "status": result[9],
                            }
                        )

                    return reports

        except Exception as e:
            logger.error(f"獲取合規報告列表失敗: {e}")
            return []

    # ========== 權限歷史操作 ==========

    async def log_permission_change(self, change_data: Dict[str, Any]):
        """記錄權限變更"""
        try:
            async with self.db.connection() as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute(
                        """
                        INSERT INTO permission_history (
                            user_id, guild_id, changed_by, change_type,
                            old_permissions, new_permissions, reason
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s)
                    """,
                        (
                            change_data["user_id"],
                            change_data["guild_id"],
                            change_data["changed_by"],
                            change_data["change_type"],
                            json.dumps(change_data.get("old_permissions", {})),
                            json.dumps(change_data.get("new_permissions", {})),
                            change_data.get("reason", ""),
                        ),
                    )

                    await conn.commit()

        except Exception as e:
            logger.error(f"記錄權限變更失敗: {e}")

    # ========== 資料存取日誌操作 ==========

    async def log_data_access(self, access_data: Dict[str, Any]) -> str:
        """記錄資料存取"""
        try:
            async with self.db.connection() as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute(
                        """
                        INSERT INTO data_access_logs (
                            id, user_id, guild_id, table_name, operation,
                            record_count, query_hash, execution_time, filters,
                            sensitive_data
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                        (
                            access_data["id"],
                            access_data["user_id"],
                            access_data.get("guild_id"),
                            access_data["table_name"],
                            access_data["operation"],
                            access_data.get("record_count", 0),
                            access_data.get("query_hash"),
                            access_data.get("execution_time", 0.0),
                            json.dumps(access_data.get("filters", {})),
                            access_data.get("sensitive_data", False),
                        ),
                    )

                    await conn.commit()
                    return access_data["id"]

        except Exception as e:
            logger.error(f"記錄資料存取失敗: {e}")
            return ""

    # ========== 統計和分析 ==========

    async def get_security_statistics(
        self, guild_id: int, days: int = 30
    ) -> Dict[str, Any]:
        """獲取安全統計"""
        try:
            start_date = datetime.now(timezone.utc) - timedelta(days=days)

            async with self.db.connection() as conn:
                async with conn.cursor() as cursor:
                    # 總體統計
                    await cursor.execute(
                        """
                        SELECT
                            COUNT(*) as total_events,
                            COUNT(DISTINCT user_id) as unique_users,
                            COUNT(CASE WHEN risk_level = 'high' THEN 1 END) as high_risk_events,
                            COUNT(CASE WHEN risk_level = 'critical' THEN 1 END) as critical_events
                        FROM security_events
                        WHERE guild_id = %s AND timestamp >= %s
                    """,
                        (guild_id, start_date),
                    )

                    overall_stats = await cursor.fetchone()

                    # 事件類型分佈
                    await cursor.execute(
                        """
                        SELECT event_type, COUNT(*) as count
                        FROM security_events
                        WHERE guild_id = %s AND timestamp >= %s
                        GROUP BY event_type
                        ORDER BY count DESC
                        LIMIT 10
                    """,
                        (guild_id, start_date),
                    )

                    event_types = await cursor.fetchall()

                    # 活躍警報
                    await cursor.execute(
                        """
                        SELECT COUNT(*) as active_alerts
                        FROM security_alerts a
                        JOIN security_events e ON a.event_id = e.id
                        WHERE e.guild_id = %s AND a.status IN ('open', 'investigating')
                    """,
                        (guild_id,),
                    )

                    active_alerts = (await cursor.fetchone())[0]

                    return {
                        "total_events": overall_stats[0] or 0,
                        "unique_users": overall_stats[1] or 0,
                        "high_risk_events": overall_stats[2] or 0,
                        "critical_events": overall_stats[3] or 0,
                        "active_alerts": active_alerts or 0,
                        "event_type_distribution": [
                            {"type": event[0], "count": event[1]}
                            for event in event_types
                        ],
                    }

        except Exception as e:
            logger.error(f"獲取安全統計失敗: {e}")
            return {}

    # ========== 清理操作 ==========

    async def cleanup_old_events(self, days: int = 90) -> int:
        """清理舊的安全事件"""
        try:
            cutoff_date = datetime.now(timezone.utc) - timedelta(days=days)

            async with self.db.connection() as conn:
                async with conn.cursor() as cursor:
                    # 清理低風險的舊事件
                    await cursor.execute(
                        """
                        DELETE FROM security_events
                        WHERE timestamp < %s AND risk_level = 'low'
                    """,
                        (cutoff_date,),
                    )

                    deleted_count = cursor.rowcount
                    await conn.commit()

                    logger.info(f"清理了 {deleted_count} 條舊的安全事件")
                    return deleted_count

        except Exception as e:
            logger.error(f"清理安全事件失敗: {e}")
            return 0

    async def cleanup_old_sessions(self, days: int = 30) -> int:
        """清理舊的用戶會話"""
        try:
            cutoff_date = datetime.now(timezone.utc) - timedelta(days=days)

            async with self.db.connection() as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute(
                        """
                        DELETE FROM user_sessions
                        WHERE last_activity < %s AND is_active = FALSE
                    """,
                        (cutoff_date,),
                    )

                    deleted_count = cursor.rowcount
                    await conn.commit()

                    logger.info(f"清理了 {deleted_count} 條舊的用戶會話")
                    return deleted_count

        except Exception as e:
            logger.error(f"清理用戶會話失敗: {e}")
            return 0
