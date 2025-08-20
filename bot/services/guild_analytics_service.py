# bot/services/guild_analytics_service.py - v1.0.0
# 📊 伺服器分析服務
# Guild Analytics and Monitoring Service

import logging
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timedelta, timezone
import asyncio
import json
from dataclasses import dataclass
from enum import Enum
import statistics

from bot.db.pool import db_pool
from bot.utils.multi_tenant_security import secure_query_builder
import aiomysql

logger = logging.getLogger(__name__)

class MetricType(Enum):
    """指標類型"""
    COUNTER = "counter"      # 計數器
    GAUGE = "gauge"         # 測量值
    HISTOGRAM = "histogram"  # 直方圖
    RATE = "rate"           # 比率

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
        self.query_builder = secure_query_builder
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
                duration_minutes=5
            ),
            AlertRule(
                name="票券積壓警告",
                metric="open_tickets_count",
                condition=">",
                threshold=50,
                severity=AlertSeverity.WARNING,
                duration_minutes=10
            ),
            AlertRule(
                name="API 速率限制警告",
                metric="api_rate_limit_exceeded",
                condition=">",
                threshold=10,
                severity=AlertSeverity.CRITICAL,
                duration_minutes=1
            ),
            AlertRule(
                name="資料庫連接警告",
                metric="db_connection_errors",
                condition=">",
                threshold=5,
                severity=AlertSeverity.EMERGENCY,
                duration_minutes=2
            )
        ]
    
    async def collect_guild_metrics(self, guild_id: int) -> Dict[str, Any]:
        """收集伺服器指標"""
        try:
            metrics = {}
            current_time = datetime.now(timezone.utc)
            
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
            
            logger.debug(f"✅ 伺服器 {guild_id} 指標收集完成")
            return metrics
            
        except Exception as e:
            logger.error(f"❌ 收集伺服器指標失敗: {e}")
            return {}
    
    async def _collect_basic_stats(self, guild_id: int) -> Dict[str, Any]:
        """收集基本統計"""
        try:
            stats = {}
            
            async with self.db.connection() as conn:
                async with conn.cursor() as cursor:
                    # 票券統計
                    await cursor.execute("""
                        SELECT 
                            COUNT(*) as total_tickets,
                            SUM(CASE WHEN status = 'open' THEN 1 ELSE 0 END) as open_tickets,
                            SUM(CASE WHEN status = 'closed' THEN 1 ELSE 0 END) as closed_tickets,
                            AVG(CASE WHEN first_response_at IS NOT NULL AND created_at IS NOT NULL 
                                THEN TIMESTAMPDIFF(MINUTE, created_at, first_response_at) END) as avg_response_time
                        FROM tickets WHERE guild_id = %s AND created_at >= CURDATE()
                    """, (guild_id,))
                    
                    ticket_stats = await cursor.fetchone()
                    if ticket_stats:
                        stats.update({
                            "total_tickets": ticket_stats[0] or 0,
                            "open_tickets_count": ticket_stats[1] or 0,
                            "closed_tickets_count": ticket_stats[2] or 0,
                            "avg_response_time_minutes": round(ticket_stats[3] or 0, 2)
                        })
                    
                    # 投票統計
                    await cursor.execute("""
                        SELECT 
                            COUNT(*) as total_votes,
                            SUM(CASE WHEN status = 'active' THEN 1 ELSE 0 END) as active_votes,
                            AVG(total_votes) as avg_participation
                        FROM votes WHERE guild_id = %s AND created_at >= CURDATE()
                    """, (guild_id,))
                    
                    vote_stats = await cursor.fetchone()
                    if vote_stats:
                        stats.update({
                            "total_votes_today": vote_stats[0] or 0,
                            "active_votes_count": vote_stats[1] or 0,
                            "avg_vote_participation": round(vote_stats[2] or 0, 2)
                        })
            
            return stats
            
        except Exception as e:
            logger.error(f"❌ 收集基本統計失敗: {e}")
            return {}
    
    async def _collect_activity_metrics(self, guild_id: int) -> Dict[str, Any]:
        """收集活動指標"""
        try:
            metrics = {}
            now = datetime.now(timezone.utc)
            today = now.date()
            
            async with self.db.connection() as conn:
                async with conn.cursor() as cursor:
                    # API 調用統計
                    await cursor.execute("""
                        SELECT 
                            COUNT(*) as total_calls,
                            SUM(CASE WHEN success = 1 THEN 1 ELSE 0 END) as successful_calls,
                            AVG(execution_time_ms) as avg_execution_time
                        FROM data_access_logs 
                        WHERE guild_id = %s AND DATE(created_at) = %s
                    """, (guild_id, today))
                    
                    api_stats = await cursor.fetchone()
                    if api_stats:
                        total_calls = api_stats[0] or 0
                        successful_calls = api_stats[1] or 0
                        error_rate = (total_calls - successful_calls) / total_calls if total_calls > 0 else 0
                        
                        metrics.update({
                            "api_calls_today": total_calls,
                            "api_success_rate": round(successful_calls / total_calls if total_calls > 0 else 1, 4),
                            "error_rate": round(error_rate, 4),
                            "avg_api_response_time": round(api_stats[2] or 0, 2)
                        })
                    
                    # 命令使用統計
                    await cursor.execute("""
                        SELECT COUNT(*) FROM guild_event_logs 
                        WHERE guild_id = %s AND event_category = 'user_action' 
                        AND DATE(timestamp) = %s
                    """, (guild_id, today))
                    
                    command_count = await cursor.fetchone()
                    metrics["commands_used_today"] = command_count[0] if command_count else 0
            
            return metrics
            
        except Exception as e:
            logger.error(f"❌ 收集活動指標失敗: {e}")
            return {}
    
    async def _collect_performance_metrics(self, guild_id: int) -> Dict[str, Any]:
        """收集性能指標"""
        try:
            metrics = {}
            
            async with self.db.connection() as conn:
                async with conn.cursor() as cursor:
                    # 查詢性能統計
                    await cursor.execute("""
                        SELECT 
                            AVG(execution_time_ms) as avg_query_time,
                            MAX(execution_time_ms) as max_query_time,
                            COUNT(*) as total_queries
                        FROM data_access_logs 
                        WHERE guild_id = %s AND created_at >= DATE_SUB(NOW(), INTERVAL 1 HOUR)
                    """, (guild_id,))
                    
                    perf_stats = await cursor.fetchone()
                    if perf_stats:
                        metrics.update({
                            "avg_query_time_ms": round(perf_stats[0] or 0, 2),
                            "max_query_time_ms": perf_stats[1] or 0,
                            "queries_per_hour": perf_stats[2] or 0
                        })
                    
                    # 記憶體和資源使用 (模擬數據)
                    metrics.update({
                        "memory_usage_mb": 150.5,  # 實際部署時需要真實的系統指標
                        "cpu_usage_percent": 12.3,
                        "disk_usage_mb": 45.2
                    })
            
            return metrics
            
        except Exception as e:
            logger.error(f"❌ 收集性能指標失敗: {e}")
            return {}
    
    async def _collect_security_metrics(self, guild_id: int) -> Dict[str, Any]:
        """收集安全指標"""
        try:
            metrics = {}
            today = datetime.now(timezone.utc).date()
            
            async with self.db.connection() as conn:
                async with conn.cursor() as cursor:
                    # 安全事件統計
                    await cursor.execute("""
                        SELECT 
                            COUNT(*) as total_events,
                            SUM(CASE WHEN severity = 'critical' THEN 1 ELSE 0 END) as critical_events,
                            SUM(CASE WHEN severity = 'high' THEN 1 ELSE 0 END) as high_events
                        FROM security_events 
                        WHERE guild_id = %s AND DATE(timestamp) = %s
                    """, (guild_id, today))
                    
                    security_stats = await cursor.fetchone()
                    if security_stats:
                        metrics.update({
                            "security_events_today": security_stats[0] or 0,
                            "critical_security_events": security_stats[1] or 0,
                            "high_security_events": security_stats[2] or 0
                        })
                    
                    # MFA 採用率
                    await cursor.execute("""
                        SELECT 
                            COUNT(DISTINCT user_id) as total_users,
                            COUNT(DISTINCT CASE WHEN is_enabled = 1 THEN user_id END) as mfa_users
                        FROM user_mfa um
                        JOIN guild_user_permissions gup ON um.user_id = gup.user_id
                        WHERE gup.guild_id = %s
                    """, (guild_id,))
                    
                    mfa_stats = await cursor.fetchone()
                    if mfa_stats and mfa_stats[0]:
                        mfa_adoption = (mfa_stats[1] or 0) / mfa_stats[0]
                        metrics["mfa_adoption_rate"] = round(mfa_adoption, 4)
                    else:
                        metrics["mfa_adoption_rate"] = 0.0
            
            return metrics
            
        except Exception as e:
            logger.error(f"❌ 收集安全指標失敗: {e}")
            return {}
    
    async def _collect_engagement_metrics(self, guild_id: int) -> Dict[str, Any]:
        """收集用戶參與度指標"""
        try:
            metrics = {}
            today = datetime.now(timezone.utc).date()
            
            async with self.db.connection() as conn:
                async with conn.cursor() as cursor:
                    # 活躍用戶統計
                    await cursor.execute("""
                        SELECT COUNT(DISTINCT user_id) 
                        FROM data_access_logs 
                        WHERE guild_id = %s AND DATE(created_at) = %s
                    """, (guild_id, today))
                    
                    active_users = await cursor.fetchone()
                    metrics["daily_active_users"] = active_users[0] if active_users else 0
                    
                    # 票券參與度
                    await cursor.execute("""
                        SELECT 
                            COUNT(DISTINCT discord_id) as ticket_users,
                            AVG(CASE WHEN status = 'closed' AND rating IS NOT NULL 
                                THEN rating END) as avg_satisfaction
                        FROM tickets 
                        WHERE guild_id = %s AND DATE(created_at) = %s
                    """, (guild_id, today))
                    
                    engagement_stats = await cursor.fetchone()
                    if engagement_stats:
                        metrics.update({
                            "ticket_active_users": engagement_stats[0] or 0,
                            "avg_satisfaction_rating": round(engagement_stats[1] or 0, 2)
                        })
            
            return metrics
            
        except Exception as e:
            logger.error(f"❌ 收集參與度指標失敗: {e}")
            return {}
    
    async def _store_daily_stats(self, guild_id: int, metrics: Dict[str, Any]):
        """存儲每日統計數據"""
        try:
            today = datetime.now(timezone.utc).date()
            
            # 準備統計數據
            stats_data = {
                "guild_id": guild_id,
                "date": today,
                "member_count": 0,  # 實際值需要從 Discord API 獲取
                "active_members": metrics.get("daily_active_users", 0),
                "tickets_created": metrics.get("total_tickets", 0),
                "tickets_closed": metrics.get("closed_tickets_count", 0),
                "votes_created": metrics.get("total_votes_today", 0),
                "commands_used": metrics.get("commands_used_today", 0),
                "api_calls": metrics.get("api_calls_today", 0),
                "security_events": metrics.get("security_events_today", 0),
                "uptime_minutes": 1440  # 24小時，實際需要計算
            }
            
            async with self.db.connection() as conn:
                async with conn.cursor() as cursor:
                    # 使用 REPLACE INTO 來更新當日統計
                    columns = ", ".join(stats_data.keys())
                    placeholders = ", ".join(["%s"] * len(stats_data))
                    
                    await cursor.execute(f"""
                        REPLACE INTO guild_statistics ({columns})
                        VALUES ({placeholders})
                    """, list(stats_data.values()))
                    
                    await conn.commit()
                    
        except Exception as e:
            logger.error(f"❌ 存儲統計數據失敗: {e}")
    
    async def _check_alerts(self, guild_id: int, metrics: Dict[str, Any]):
        """檢查警告條件"""
        try:
            alert_rules = self._alert_rules.get(guild_id, self.default_alert_rules)
            
            for rule in alert_rules:
                if not rule.enabled:
                    continue
                
                if rule.metric not in metrics:
                    continue
                
                current_value = metrics[rule.metric]
                alert_key = f"{guild_id}_{rule.name}"
                
                # 檢查條件
                alert_triggered = False
                if rule.condition == ">" and current_value > rule.threshold:
                    alert_triggered = True
                elif rule.condition == "<" and current_value < rule.threshold:
                    alert_triggered = True
                elif rule.condition == "==" and current_value == rule.threshold:
                    alert_triggered = True
                elif rule.condition == "!=" and current_value != rule.threshold:
                    alert_triggered = True
                
                if alert_triggered:
                    # 檢查是否已經在警告狀態
                    if alert_key not in self._active_alerts:
                        self._active_alerts[alert_key] = datetime.now(timezone.utc)
                    
                    # 檢查持續時間
                    alert_duration = datetime.now(timezone.utc) - self._active_alerts[alert_key]
                    if alert_duration.total_seconds() >= rule.duration_minutes * 60:
                        await self._send_alert(guild_id, rule, current_value)
                else:
                    # 清除警告狀態
                    if alert_key in self._active_alerts:
                        del self._active_alerts[alert_key]
                        await self._clear_alert(guild_id, rule)
                        
        except Exception as e:
            logger.error(f"❌ 檢查警告失敗: {e}")
    
    async def _send_alert(self, guild_id: int, rule: AlertRule, current_value: float):
        """發送警告"""
        try:
            alert_data = {
                "guild_id": guild_id,
                "user_id": None,
                "event_type": "alert_triggered",
                "event_category": "system",
                "event_name": rule.name,
                "description": f"警告觸發: {rule.metric} = {current_value} {rule.condition} {rule.threshold}",
                "metadata": json.dumps({
                    "metric": rule.metric,
                    "current_value": current_value,
                    "threshold": rule.threshold,
                    "condition": rule.condition,
                    "severity": rule.severity.value
                }),
                "source": "analytics_service",
                "status": "success"
            }
            
            async with self.db.connection() as conn:
                async with conn.cursor() as cursor:
                    columns = ", ".join(alert_data.keys())
                    placeholders = ", ".join(["%s"] * len(alert_data))
                    
                    await cursor.execute(f"""
                        INSERT INTO guild_event_logs ({columns})
                        VALUES ({placeholders})
                    """, list(alert_data.values()))
                    
                    await conn.commit()
            
            logger.warning(f"🚨 警告觸發 [{rule.severity.value.upper()}]: {rule.name} - {current_value}")
            
        except Exception as e:
            logger.error(f"❌ 發送警告失敗: {e}")
    
    async def _clear_alert(self, guild_id: int, rule: AlertRule):
        """清除警告"""
        logger.info(f"✅ 警告清除: {rule.name}")
    
    async def get_guild_analytics_dashboard(self, guild_id: int, 
                                          days: int = 7) -> Dict[str, Any]:
        """獲取伺服器分析儀表板數據"""
        try:
            end_date = datetime.now(timezone.utc).date()
            start_date = end_date - timedelta(days=days)
            
            dashboard_data = {}
            
            async with self.db.connection() as conn:
                async with conn.cursor(aiomysql.DictCursor) as cursor:
                    # 歷史趨勢數據
                    await cursor.execute("""
                        SELECT * FROM guild_statistics 
                        WHERE guild_id = %s AND date >= %s AND date <= %s
                        ORDER BY date DESC
                    """, (guild_id, start_date, end_date))
                    
                    historical_data = await cursor.fetchall()
                    dashboard_data["historical_stats"] = [dict(row) for row in historical_data]
                    
                    # 今日實時數據
                    current_metrics = await self.collect_guild_metrics(guild_id)
                    dashboard_data["current_metrics"] = current_metrics
                    
                    # 趨勢分析
                    dashboard_data["trends"] = await self._calculate_trends(historical_data)
                    
                    # 性能指標
                    dashboard_data["performance"] = await self._get_performance_summary(guild_id)
                    
                    # 最近警告
                    await cursor.execute("""
                        SELECT * FROM guild_event_logs 
                        WHERE guild_id = %s AND event_type = 'alert_triggered'
                        AND timestamp >= %s
                        ORDER BY timestamp DESC LIMIT 10
                    """, (guild_id, start_date))
                    
                    recent_alerts = await cursor.fetchall()
                    dashboard_data["recent_alerts"] = [dict(row) for row in recent_alerts]
            
            return dashboard_data
            
        except Exception as e:
            logger.error(f"❌ 獲取分析儀表板失敗: {e}")
            return {}
    
    async def _calculate_trends(self, historical_data: List[Dict]) -> Dict[str, Any]:
        """計算趨勢數據"""
        if len(historical_data) < 2:
            return {}
        
        trends = {}
        numeric_fields = ["tickets_created", "votes_created", "commands_used", "api_calls"]
        
        for field in numeric_fields:
            values = [row.get(field, 0) for row in historical_data if row.get(field) is not None]
            if len(values) >= 2:
                # 計算變化率
                recent_avg = statistics.mean(values[:3]) if len(values) >= 3 else values[0]
                older_avg = statistics.mean(values[-3:]) if len(values) >= 3 else values[-1]
                
                if older_avg > 0:
                    change_rate = (recent_avg - older_avg) / older_avg
                    trends[f"{field}_trend"] = {
                        "change_rate": round(change_rate, 4),
                        "direction": "up" if change_rate > 0 else "down" if change_rate < 0 else "stable"
                    }
        
        return trends
    
    async def _get_performance_summary(self, guild_id: int) -> Dict[str, Any]:
        """獲取性能摘要"""
        try:
            async with self.db.connection() as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute("""
                        SELECT 
                            AVG(execution_time_ms) as avg_response,
                            MAX(execution_time_ms) as max_response,
                            MIN(execution_time_ms) as min_response,
                            COUNT(*) as total_requests
                        FROM data_access_logs 
                        WHERE guild_id = %s AND created_at >= DATE_SUB(NOW(), INTERVAL 24 HOUR)
                    """, (guild_id,))
                    
                    perf_data = await cursor.fetchone()
                    if perf_data:
                        return {
                            "avg_response_time": round(perf_data[0] or 0, 2),
                            "max_response_time": perf_data[1] or 0,
                            "min_response_time": perf_data[2] or 0,
                            "total_requests_24h": perf_data[3] or 0
                        }
                    
            return {}
            
        except Exception as e:
            logger.error(f"❌ 獲取性能摘要失敗: {e}")
            return {}
    
    async def start_monitoring(self):
        """啟動監控任務"""
        logger.info("📊 啟動伺服器監控服務")
        
        async def monitoring_loop():
            while True:
                try:
                    # 獲取所有活躍伺服器
                    async with self.db.connection() as conn:
                        async with conn.cursor() as cursor:
                            await cursor.execute("""
                                SELECT guild_id FROM guild_info 
                                WHERE status = 'active'
                            """)
                            active_guilds = await cursor.fetchall()
                    
                    # 收集每個伺服器的指標
                    for guild_row in active_guilds:
                        guild_id = guild_row[0]
                        try:
                            await self.collect_guild_metrics(guild_id)
                        except Exception as e:
                            logger.error(f"❌ 收集伺服器 {guild_id} 指標失敗: {e}")
                    
                    # 等待下次收集 (每5分鐘)
                    await asyncio.sleep(300)
                    
                except Exception as e:
                    logger.error(f"❌ 監控循環錯誤: {e}")
                    await asyncio.sleep(60)  # 錯誤時等待1分鐘
        
        # 在背景執行監控
        asyncio.create_task(monitoring_loop())

# 全域實例
guild_analytics_service = GuildAnalyticsService()