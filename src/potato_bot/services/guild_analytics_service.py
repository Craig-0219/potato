# bot/services/guild_analytics_service.py - v1.0.0
# 📊 伺服器分析服務
# Guild Analytics and Monitoring Service

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List

from bot.db.pool import db_pool

logger = logging.getLogger(__name__)


class MetricType(Enum):
    """指標類型"""

    COUNTER = "counter"  # 計數器
    GAUGE = "gauge"  # 測量值
    HISTOGRAM = "histogram"  # 直方圖
    RATE = "rate"  # 比率


class AlertSeverity(Enum):
    """警告嚴重程度"""

    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"
    EMERGENCY = "emergency"


@dataclass
class MetricData:
    """指標數據"""

    name: str
    value: float
    type: MetricType
    timestamp: datetime
    labels: Dict[str, str] = None

    def __post_init__(self):
        if self.labels is None:
            self.labels = {}


@dataclass
class AlertRule:
    """警告規則"""

    name: str
    metric: str
    condition: str  # ">" | "<" | "==" | "!="
    threshold: float
    severity: AlertSeverity
    duration_minutes: int = 5
    enabled: bool = True


class GuildAnalyticsService:
    """伺服器分析服務"""

    def __init__(self):
        self.db = db_pool
        self._metric_cache: Dict[str, List[MetricData]] = {}
        self._alert_rules: Dict[int, List[AlertRule]] = {}
        self._active_alerts: Dict[str, datetime] = {}

        # 初始化預設警告規則
        self._initialize_default_alerts()

    def _initialize_default_alerts(self):
        """初始化預設警告規則"""
        self.default_alert_rules = [
            AlertRule(
                name="高錯誤率警告",
                metric="error_rate",
                condition=">",
                threshold=0.05,  # 5%
                severity=AlertSeverity.WARNING,
                duration_minutes=5,
            ),
            AlertRule(
                name="票券積壓警告",
                metric="open_tickets_count",
                condition=">",
                threshold=50,
                severity=AlertSeverity.WARNING,
                duration_minutes=10,
            ),
            AlertRule(
                name="API 速率限制警告",
                metric="api_rate_limit_exceeded",
                condition=">",
                threshold=10,
                severity=AlertSeverity.CRITICAL,
                duration_minutes=1,
            ),
            AlertRule(
                name="資料庫連接警告",
                metric="db_connection_errors",
                condition=">",
                threshold=5,
                severity=AlertSeverity.EMERGENCY,
                duration_minutes=2,
            ),
        ]

    async def collect_guild_metrics(self, guild_id: int) -> Dict[str, Any]:
        """收集伺服器指標"""
        try:
            metrics = {}
            datetime.now(timezone.utc)

            # 基本統計
            metrics.update(await self._collect_basic_stats(guild_id))

            # 活動指標
            metrics.update(await self._collect_activity_metrics(guild_id))

            # 性能指標
            metrics.update(await self._collect_performance_metrics(guild_id))

            # 安全指標
            metrics.update(await self._collect_security_metrics(guild_id))

            # 用戶參與度指標
            metrics.update(await self._collect_engagement_metrics(guild_id))

            # 存儲到統計表
            await self._store_daily_stats(guild_id, metrics)

            # 檢查警告
            await self._check_alerts(guild_id, metrics)

            return metrics

        except Exception as e:
            logger.error(f"收集伺服器指標時發生錯誤: {e}")
            return {}


# 全域實例
guild_analytics_service = GuildAnalyticsService()
