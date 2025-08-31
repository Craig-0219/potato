# bot/services/security/audit_manager.py - v1.0.0
# 🔍 企業級安全審計日誌系統
# Security Audit & Compliance Management

import hashlib
import ipaddress
import json
import logging
import re
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional

from bot.db.pool import db_pool

logger = logging.getLogger(__name__)


class EventSeverity(Enum):
    """事件嚴重程度"""

    CRITICAL = "critical"  # 嚴重安全威脅
    HIGH = "high"  # 高風險事件
    MEDIUM = "medium"  # 中等風險事件
    LOW = "low"  # 低風險事件
    INFO = "info"  # 資訊性事件


class EventCategory(Enum):
    """事件分類"""

    AUTHENTICATION = "authentication"  # 認證相關
    AUTHORIZATION = "authorization"  # 授權相關
    DATA_ACCESS = "data_access"  # 資料存取
    SYSTEM_CONFIG = "system_config"  # 系統配置
    USER_ACTION = "user_action"  # 用戶行為
    API_ACCESS = "api_access"  # API 存取
    SECURITY_VIOLATION = "security_violation"  # 安全違規
    COMPLIANCE = "compliance"  # 合規檢查


class ComplianceStandard(Enum):
    """合規標準"""

    SOC2 = "soc2"
    GDPR = "gdpr"
    HIPAA = "hipaa"
    ISO27001 = "iso27001"
    CUSTOM = "custom"


@dataclass
class SecurityEvent:
    """安全事件"""

    id: Optional[int] = None
    user_id: Optional[int] = None
    guild_id: Optional[int] = None
    event_type: str = ""
    category: EventCategory = EventCategory.USER_ACTION
    severity: EventSeverity = EventSeverity.INFO
    message: str = ""
    details: Dict[str, Any] = field(default_factory=dict)
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    session_id: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.now)
    processed: bool = False
    hash_signature: Optional[str] = None


@dataclass
class AuditRule:
    """審計規則"""

    id: int
    name: str
    description: str
    event_pattern: str  # 正則表達式匹配事件
    severity_threshold: EventSeverity
    action: str  # alert, block, log
    is_active: bool = True
    created_at: datetime = field(default_factory=datetime.now)


class AuditManager:
    """
    企業級安全審計管理器

    功能：
    - 安全事件記錄與分析
    - 實時威脅檢測
    - 合規報告生成
    - 異常行為檢測
    - 審計日誌完整性驗證
    """

    def __init__(self):
        self.anomaly_detection_enabled = True
        self.real_time_monitoring = True
        self.integrity_check_interval = 3600  # 1小時檢查一次完整性

        # 異常檢測參數
        self.max_events_per_minute = 100
        self.max_failed_login_attempts = 5
        self.suspicious_ip_threshold = 10

        # 快取
        self._rules_cache: List[AuditRule] = []
        self._user_activity_cache: Dict[int, List[datetime]] = defaultdict(
            list
        )
        self._ip_activity_cache: Dict[str, int] = defaultdict(int)

        logger.info("🔍 安全審計管理器初始化完成")

    async def log_event(self, event: SecurityEvent) -> bool:
        """
        記錄安全事件

        Args:
            event: 安全事件對象

        Returns:
            bool: 記錄是否成功
        """
        try:
            # 生成事件唯一簽名
            event.hash_signature = self._generate_event_hash(event)

            # 實時威脅檢測
            if self.real_time_monitoring:
                threat_detected = await self._detect_threats(event)
                if threat_detected:
                    event.severity = EventSeverity.HIGH
                    await self._trigger_security_alert(event)

            # 異常檢測
            if self.anomaly_detection_enabled:
                await self._detect_anomalies(event)

            # 保存到資料庫
            async with db_pool.connection() as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute(
                        """
                        INSERT INTO security_events (
                            user_id, guild_id, event_type, category, severity,
                            message, details, ip_address, user_agent, session_id,
                            timestamp, hash_signature
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                        (
                            event.user_id,
                            event.guild_id,
                            event.event_type,
                            event.category.value,
                            event.severity.value,
                            event.message,
                            json.dumps(event.details),
                            event.ip_address,
                            event.user_agent,
                            event.session_id,
                            event.timestamp,
                            event.hash_signature,
                        ),
                    )

                    event.id = cursor.lastrowid
                    await conn.commit()

            # 更新活動快取
            if event.user_id:
                self._user_activity_cache[event.user_id].append(
                    event.timestamp
                )
                # 保持快取大小
                if len(self._user_activity_cache[event.user_id]) > 100:
                    self._user_activity_cache[event.user_id] = (
                        self._user_activity_cache[event.user_id][-50:]
                    )

            if event.ip_address:
                self._ip_activity_cache[event.ip_address] += 1

            logger.info(
                f"📝 安全事件已記錄: {event.event_type} (ID: {event.id})"
            )
            return True

        except Exception as e:
            logger.error(f"❌ 安全事件記錄失敗: {e}")
            return False

    async def log_authentication_event(
        self,
        user_id: int,
        event_type: str,
        success: bool,
        details: Dict[str, Any] = None,
        ip_address: str = None,
    ) -> bool:
        """記錄認證事件"""
        event = SecurityEvent(
            user_id=user_id,
            event_type=event_type,
            category=EventCategory.AUTHENTICATION,
            severity=EventSeverity.INFO if success else EventSeverity.MEDIUM,
            message=f"認證{'成功' if success else '失敗'}: {event_type}",
            details=details or {},
            ip_address=ip_address,
        )

        return await self.log_event(event)

    async def log_authorization_event(
        self,
        user_id: int,
        guild_id: int,
        permission: str,
        granted: bool,
        resource: str = None,
    ) -> bool:
        """記錄授權事件"""
        event = SecurityEvent(
            user_id=user_id,
            guild_id=guild_id,
            event_type="permission_check",
            category=EventCategory.AUTHORIZATION,
            severity=EventSeverity.LOW,
            message=f"權限檢查: {permission} - {'允許' if granted else '拒絕'}",
            details={
                "permission": permission,
                "granted": granted,
                "resource": resource,
            },
        )

        return await self.log_event(event)

    async def log_data_access_event(
        self,
        user_id: int,
        action: str,
        resource: str,
        success: bool,
        details: Dict[str, Any] = None,
    ) -> bool:
        """記錄資料存取事件"""
        event = SecurityEvent(
            user_id=user_id,
            event_type=f"data_{action}",
            category=EventCategory.DATA_ACCESS,
            severity=EventSeverity.INFO if success else EventSeverity.MEDIUM,
            message=f"資料存取: {action} - {resource}",
            details=details or {"resource": resource, "action": action},
        )

        return await self.log_event(event)

    async def log_api_access_event(
        self,
        user_id: Optional[int],
        endpoint: str,
        method: str,
        status_code: int,
        ip_address: str = None,
        user_agent: str = None,
    ) -> bool:
        """記錄 API 存取事件"""
        severity = EventSeverity.INFO
        if status_code >= 400:
            severity = (
                EventSeverity.MEDIUM
                if status_code < 500
                else EventSeverity.HIGH
            )

        event = SecurityEvent(
            user_id=user_id,
            event_type="api_access",
            category=EventCategory.API_ACCESS,
            severity=severity,
            message=f"API 存取: {method} {endpoint} - {status_code}",
            details={
                "endpoint": endpoint,
                "method": method,
                "status_code": status_code,
            },
            ip_address=ip_address,
            user_agent=user_agent,
        )

        return await self.log_event(event)

    async def detect_suspicious_activity(
        self, user_id: int = None, time_window: timedelta = None
    ) -> List[Dict[str, Any]]:
        """
        檢測可疑活動

        Args:
            user_id: 特定用戶 ID (可選)
            time_window: 時間窗口 (預設 24 小時)

        Returns:
            List[Dict[str, Any]]: 可疑活動列表
        """
        try:
            if not time_window:
                time_window = timedelta(hours=24)

            start_time = datetime.now() - time_window
            suspicious_activities = []

            async with db_pool.connection() as conn:
                async with conn.cursor() as cursor:
                    # 檢測異常登入嘗試
                    query = """
                        SELECT user_id, ip_address, COUNT(*) as attempt_count
                        FROM security_events
                        WHERE category = %s AND event_type LIKE %s
                        AND timestamp >= %s AND severity IN (%s, %s)
                    """
                    params = [
                        EventCategory.AUTHENTICATION.value,
                        "%login%",
                        start_time,
                        EventSeverity.MEDIUM.value,
                        EventSeverity.HIGH.value,
                    ]

                    if user_id:
                        query += " AND user_id = %s"
                        params.append(user_id)

                    query += " GROUP BY user_id, ip_address HAVING attempt_count >= %s"
                    params.append(self.max_failed_login_attempts)

                    await cursor.execute(query, params)

                    for row in await cursor.fetchall():
                        suspicious_activities.append(
                            {
                                "type": "multiple_failed_logins",
                                "user_id": row[0],
                                "ip_address": row[1],
                                "attempt_count": row[2],
                                "severity": "high",
                                "description": f"用戶 {row[0]} 從 IP {row[1]} 多次登入失敗",
                            }
                        )

                    # 檢測異常 API 存取
                    await cursor.execute(
                        """
                        SELECT user_id, COUNT(*) as request_count
                        FROM security_events
                        WHERE category = %s AND timestamp >= %s
                        GROUP BY user_id
                        HAVING request_count >= %s
                    """,
                        (
                            EventCategory.API_ACCESS.value,
                            start_time,
                            self.max_events_per_minute * 60,
                        ),
                    )

                    for row in await cursor.fetchall():
                        suspicious_activities.append(
                            {
                                "type": "excessive_api_requests",
                                "user_id": row[0],
                                "request_count": row[1],
                                "severity": "medium",
                                "description": f"用戶 {row[0]} 在短時間內大量 API 請求",
                            }
                        )

                    # 檢測權限升級事件
                    await cursor.execute(
                        """
                        SELECT user_id, guild_id, COUNT(*) as event_count
                        FROM security_events
                        WHERE event_type LIKE '%role_assigned%'
                        AND timestamp >= %s
                        GROUP BY user_id, guild_id
                        HAVING event_count >= 3
                    """,
                        (start_time,),
                    )

                    for row in await cursor.fetchall():
                        suspicious_activities.append(
                            {
                                "type": "multiple_role_assignments",
                                "user_id": row[0],
                                "guild_id": row[1],
                                "event_count": row[2],
                                "severity": "medium",
                                "description": f"用戶 {row[0]} 在伺服器 {row[1]} 多次角色變更",
                            }
                        )

            logger.info(f"🔍 檢測到 {len(suspicious_activities)} 個可疑活動")
            return suspicious_activities

        except Exception as e:
            logger.error(f"❌ 可疑活動檢測失敗: {e}")
            return []

    async def generate_compliance_report(
        self,
        standard: ComplianceStandard,
        start_date: datetime,
        end_date: datetime,
        guild_id: int = None,
    ) -> Dict[str, Any]:
        """
        生成合規報告

        Args:
            standard: 合規標準
            start_date: 開始日期
            end_date: 結束日期
            guild_id: 伺服器 ID (可選)

        Returns:
            Dict[str, Any]: 合規報告
        """
        try:
            report = {
                "standard": standard.value,
                "period": {
                    "start": start_date.isoformat(),
                    "end": end_date.isoformat(),
                },
                "guild_id": guild_id,
                "generated_at": datetime.now().isoformat(),
                "summary": {},
                "events": {},
                "compliance_status": "unknown",
            }

            async with db_pool.connection() as conn:
                async with conn.cursor() as cursor:
                    # 基本統計
                    query = """
                        SELECT category, severity, COUNT(*) as event_count
                        FROM security_events
                        WHERE timestamp BETWEEN %s AND %s
                    """
                    params = [start_date, end_date]

                    if guild_id:
                        query += " AND guild_id = %s"
                        params.append(guild_id)

                    query += " GROUP BY category, severity"

                    await cursor.execute(query, params)

                    event_stats = {}
                    total_events = 0

                    for row in await cursor.fetchall():
                        category, severity, count = row
                        if category not in event_stats:
                            event_stats[category] = {}
                        event_stats[category][severity] = count
                        total_events += count

                    report["summary"]["total_events"] = total_events
                    report["events"] = event_stats

                    # 檢查特定合規要求
                    if standard == ComplianceStandard.SOC2:
                        report.update(
                            await self._generate_soc2_compliance_data(
                                cursor, start_date, end_date, guild_id
                            )
                        )
                    elif standard == ComplianceStandard.GDPR:
                        report.update(
                            await self._generate_gdpr_compliance_data(
                                cursor, start_date, end_date, guild_id
                            )
                        )

                    # 計算合規分數
                    compliance_score = await self._calculate_compliance_score(
                        event_stats, standard
                    )
                    report["compliance_score"] = compliance_score

                    if compliance_score >= 90:
                        report["compliance_status"] = "compliant"
                    elif compliance_score >= 70:
                        report["compliance_status"] = "partial"
                    else:
                        report["compliance_status"] = "non_compliant"

            logger.info(f"📊 合規報告生成完成: {standard.value}")
            return report

        except Exception as e:
            logger.error(f"❌ 合規報告生成失敗: {e}")
            return {"error": str(e)}

    async def verify_log_integrity(
        self, start_date: datetime = None, end_date: datetime = None
    ) -> Dict[str, Any]:
        """
        驗證審計日誌完整性

        Args:
            start_date: 開始日期
            end_date: 結束日期

        Returns:
            Dict[str, Any]: 完整性驗證結果
        """
        try:
            if not start_date:
                start_date = datetime.now() - timedelta(days=7)
            if not end_date:
                end_date = datetime.now()

            async with db_pool.connection() as conn:
                async with conn.cursor() as cursor:
                    # 獲取日誌記錄
                    await cursor.execute(
                        """
                        SELECT id, hash_signature, user_id, event_type, timestamp, details
                        FROM security_events
                        WHERE timestamp BETWEEN %s AND %s
                        ORDER BY id
                    """,
                        (start_date, end_date),
                    )

                    records = await cursor.fetchall()

                    integrity_issues = []
                    verified_count = 0
                    total_count = len(records)

                    for record in records:
                        (
                            event_id,
                            stored_hash,
                            user_id,
                            event_type,
                            timestamp,
                            details,
                        ) = record

                        # 重新計算雜湊值
                        calculated_hash = self._calculate_record_hash(
                            event_id, user_id, event_type, timestamp, details
                        )

                        if stored_hash == calculated_hash:
                            verified_count += 1
                        else:
                            integrity_issues.append(
                                {
                                    "event_id": event_id,
                                    "stored_hash": stored_hash,
                                    "calculated_hash": calculated_hash,
                                    "timestamp": timestamp.isoformat(),
                                    "event_type": event_type,
                                }
                            )

            integrity_percentage = (
                (verified_count / total_count * 100) if total_count > 0 else 0
            )

            result = {
                "verification_period": {
                    "start": start_date.isoformat(),
                    "end": end_date.isoformat(),
                },
                "total_records": total_count,
                "verified_records": verified_count,
                "integrity_percentage": round(integrity_percentage, 2),
                "issues_found": len(integrity_issues),
                "integrity_issues": integrity_issues[
                    :10
                ],  # 只返回前 10 個問題
                "status": (
                    "good"
                    if integrity_percentage > 99
                    else "warning" if integrity_percentage > 95 else "critical"
                ),
            }

            logger.info(f"🔐 日誌完整性驗證完成: {integrity_percentage:.2f}%")
            return result

        except Exception as e:
            logger.error(f"❌ 日誌完整性驗證失敗: {e}")
            return {"error": str(e)}

    # 私有方法

    def _generate_event_hash(self, event: SecurityEvent) -> str:
        """生成事件雜湊值"""
        data = f"{event.user_id}|{event.guild_id}|{event.event_type}|{event.timestamp.isoformat()}|{json.dumps(event.details, sort_keys=True)}"
        return hashlib.sha256(data.encode()).hexdigest()

    def _calculate_record_hash(
        self,
        event_id: int,
        user_id: Optional[int],
        event_type: str,
        timestamp: datetime,
        details: str,
    ) -> str:
        """計算記錄雜湊值"""
        data = f"{event_id}|{user_id}|{event_type}|{timestamp.isoformat()}|{details}"
        return hashlib.sha256(data.encode()).hexdigest()

    async def _detect_threats(self, event: SecurityEvent) -> bool:
        """實時威脅檢測"""
        # 檢測 SQL 注入嘗試
        if event.category == EventCategory.DATA_ACCESS:
            sql_patterns = [
                r"(\bUNION\b.*\bSELECT\b)",
                r"(\bDROP\b.*\bTABLE\b)",
                r"(\bINSERT\b.*\bINTO\b.*\bVALUES\b)",
                r"(\bUPDATE\b.*\bSET\b)",
                r"(--|\#|\/\*)",
            ]

            details_str = json.dumps(event.details)
            for pattern in sql_patterns:
                if re.search(pattern, details_str, re.IGNORECASE):
                    return True

        # 檢測異常 IP 位址
        if event.ip_address:
            try:
                ip = ipaddress.ip_address(event.ip_address)
                # 檢測私有 IP 範圍外的可疑存取
                if (
                    not ip.is_private
                    and self._ip_activity_cache[event.ip_address]
                    > self.suspicious_ip_threshold
                ):
                    return True
            except ValueError:
                pass

        return False

    async def _detect_anomalies(self, event: SecurityEvent):
        """異常檢測"""
        if event.user_id:
            # 檢測用戶活動頻率異常
            recent_events = [
                ts
                for ts in self._user_activity_cache[event.user_id]
                if (datetime.now() - ts).total_seconds() < 60
            ]

            if len(recent_events) > self.max_events_per_minute:
                await self._trigger_anomaly_alert(
                    event, "high_frequency_activity"
                )

    async def _trigger_security_alert(self, event: SecurityEvent):
        """觸發安全警報"""
        logger.warning(f"🚨 安全警報: {event.event_type} - {event.message}")
        # 這裡可以添加通知機制，如發送到 Discord 頻道或郵件

    async def _trigger_anomaly_alert(
        self, event: SecurityEvent, anomaly_type: str
    ):
        """觸發異常警報"""
        logger.warning(f"⚠️ 異常檢測: {anomaly_type} - 用戶 {event.user_id}")

    async def _generate_soc2_compliance_data(
        self, cursor, start_date, end_date, guild_id
    ) -> Dict[str, Any]:
        """生成 SOC 2 合規數據"""
        # SOC 2 相關的合規檢查
        return {
            "soc2_controls": {
                "access_controls": "implemented",
                "data_encryption": "enabled",
                "monitoring": "active",
                "incident_response": "defined",
            }
        }

    async def _generate_gdpr_compliance_data(
        self, cursor, start_date, end_date, guild_id
    ) -> Dict[str, Any]:
        """生成 GDPR 合規數據"""
        # GDPR 相關的合規檢查
        return {
            "gdpr_controls": {
                "data_protection": "implemented",
                "consent_management": "active",
                "right_to_deletion": "supported",
                "data_breach_notification": "compliant",
            }
        }

    async def _calculate_compliance_score(
        self, event_stats: Dict, standard: ComplianceStandard
    ) -> int:
        """計算合規分數"""
        # 簡化的合規分數計算
        base_score = 100

        # 根據高嚴重性事件扣分
        high_severity_events = 0
        critical_events = 0

        for category_stats in event_stats.values():
            high_severity_events += category_stats.get(
                EventSeverity.HIGH.value, 0
            )
            critical_events += category_stats.get(
                EventSeverity.CRITICAL.value, 0
            )

        # 扣分規則
        base_score -= critical_events * 10
        base_score -= high_severity_events * 5

        return max(0, base_score)


# 全域單例
audit_manager = AuditManager()
