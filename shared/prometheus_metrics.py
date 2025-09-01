# shared/prometheus_metrics.py - Prometheus 監控指標管理器
"""
Prometheus 監控指標管理器 v2.2.0
功能特點：
1. 自定義業務指標收集
2. 系統性能指標監控
3. Discord Bot 特定指標
4. 快取和資料庫性能監控
5. 自動指標匯出
6. Grafana 儀表板整合
"""

import asyncio
import os
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

try:
    from prometheus_client import (
        CONTENT_TYPE_LATEST,
        CollectorRegistry,
        Counter,
        Gauge,
        Histogram,
        Info,
        Summary,
        generate_latest,
        push_to_gateway,
        start_http_server,
    )

    PROMETHEUS_AVAILABLE = True
except ImportError:
    PROMETHEUS_AVAILABLE = False

    # 建立假的類別以避免錯誤
    class Counter:
        def __init__(self, *args, **kwargs):
            pass

        def inc(self, *args, **kwargs):
            pass

        def labels(self, *args, **kwargs):
            return self

    class Histogram:
        def __init__(self, *args, **kwargs):
            pass

        def observe(self, *args, **kwargs):
            pass

        def time(self):
            return self

        def labels(self, *args, **kwargs):
            return self

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

    class Gauge:
        def __init__(self, *args, **kwargs):
            pass

        def set(self, *args, **kwargs):
            pass

        def inc(self, *args, **kwargs):
            pass

        def dec(self, *args, **kwargs):
            pass

        def labels(self, *args, **kwargs):
            return self

    Summary = Info = CollectorRegistry = Histogram

    def generate_latest(*args):
        return ""

    def start_http_server(*args):
        pass

    def push_to_gateway(*args, **kwargs):
        pass

    CONTENT_TYPE_LATEST = "text/plain"

from shared.logger import logger


class MetricType(Enum):
    """指標類型"""

    COUNTER = "counter"  # 計數器（只增不減）
    GAUGE = "gauge"  # 儀表（可增可減）
    HISTOGRAM = "histogram"  # 直方圖（分佈統計）
    SUMMARY = "summary"  # 摘要（分位數統計）


@dataclass
class MetricConfig:
    """指標配置"""

    name: str
    help: str
    labels: List[str] = None
    buckets: List[float] = None  # 僅用於 HISTOGRAM
    registry: Any = None


class PrometheusMetricsManager:
    """Prometheus 指標管理器"""

    def __init__(self, registry: CollectorRegistry = None):
        self.registry = registry or CollectorRegistry()
        self.metrics: Dict[str, Any] = {}
        self.custom_collectors = []

        # 配置
        self.enable_push_gateway = False
        self.push_gateway_url = ""
        self.job_name = "potato_bot"

        # HTTP 服務器
        self.http_server = None
        self.http_port = int(os.getenv("PROMETHEUS_PORT", 8090))

        # 性能統計
        self.stats = {
            "metrics_collected": 0,
            "collections_per_second": 0,
            "last_collection": None,
        }

        logger.info(
            f"📊 Prometheus 監控管理器初始化 - 可用: {PROMETHEUS_AVAILABLE}"
        )

        if PROMETHEUS_AVAILABLE:
            self._create_default_metrics()

    async def initialize(
        self, start_http_server: bool = True, push_gateway_url: str = None
    ):
        """初始化監控系統"""
        try:
            if not PROMETHEUS_AVAILABLE:
                logger.warning("⚠️ prometheus_client 不可用，監控功能將被禁用")
                return

            # 配置推送網關
            if push_gateway_url:
                self.enable_push_gateway = True
                self.push_gateway_url = push_gateway_url
                logger.info(
                    f"✅ Prometheus Push Gateway 配置: {push_gateway_url}"
                )

            # 啟動 HTTP 服務器
            if start_http_server:
                await self._start_http_server()

            # 啟動指標收集任務
            asyncio.create_task(self._metrics_collection_loop())

            logger.info("✅ Prometheus 監控系統初始化完成")

        except Exception as e:
            logger.error(f"❌ Prometheus 監控系統初始化失敗: {e}")
            raise

    def _create_default_metrics(self):
        """創建預設指標"""
        if not PROMETHEUS_AVAILABLE:
            return

        try:
            # 系統基礎指標
            self.register_counter(
                "potato_bot_commands_total",
                "Total number of commands executed",
                ["command", "guild", "status"],
            )

            self.register_histogram(
                "potato_bot_command_duration_seconds",
                "Command execution duration in seconds",
                ["command", "guild"],
                buckets=[0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0],
            )

            self.register_gauge(
                "potato_bot_active_tickets",
                "Number of active tickets",
                ["guild", "status"],
            )

            self.register_counter(
                "potato_bot_tickets_total",
                "Total number of tickets created",
                ["guild", "category"],
            )

            # 快取指標
            self.register_counter(
                "potato_bot_cache_operations_total",
                "Total cache operations",
                ["operation", "level", "status"],
            )

            self.register_histogram(
                "potato_bot_cache_operation_duration_seconds",
                "Cache operation duration in seconds",
                ["operation", "level"],
                buckets=[0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5],
            )

            self.register_gauge(
                "potato_bot_cache_hit_rate",
                "Cache hit rate percentage",
                ["level"],
            )

            self.register_gauge(
                "potato_bot_cache_size", "Cache size in items", ["level"]
            )

            # 資料庫指標
            self.register_counter(
                "potato_bot_db_queries_total",
                "Total database queries",
                ["query_type", "table", "status"],
            )

            self.register_histogram(
                "potato_bot_db_query_duration_seconds",
                "Database query duration in seconds",
                ["query_type", "table"],
                buckets=[0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0],
            )

            self.register_gauge(
                "potato_bot_db_connections_active",
                "Active database connections",
            )

            self.register_gauge(
                "potato_bot_db_slow_queries",
                "Number of slow queries in the last period",
            )

            # Discord Bot 指標
            self.register_gauge(
                "potato_bot_guilds_total", "Total number of guilds"
            )

            self.register_gauge(
                "potato_bot_users_total", "Total number of users"
            )

            self.register_gauge(
                "potato_bot_latency_seconds", "Bot latency in seconds"
            )

            self.register_counter(
                "potato_bot_events_total",
                "Total Discord events received",
                ["event_type"],
            )

            # 系統資源指標
            self.register_gauge(
                "potato_bot_memory_usage_bytes",
                "Memory usage in bytes",
                ["type"],
            )

            self.register_gauge(
                "potato_bot_cpu_usage_percent", "CPU usage percentage"
            )

            # 業務指標
            self.register_histogram(
                "potato_bot_ticket_resolution_time_seconds",
                "Time to resolve tickets in seconds",
                ["category", "priority"],
                buckets=[300, 900, 1800, 3600, 7200, 14400, 28800, 86400],
            )

            self.register_gauge(
                "potato_bot_sla_violations",
                "Number of SLA violations",
                ["guild", "sla_type"],
            )

            logger.info("✅ 預設指標創建完成")

        except Exception as e:
            logger.error(f"❌ 創建預設指標失敗: {e}")

    def register_counter(
        self, name: str, help: str, labels: List[str] = None
    ) -> Counter:
        """註冊計數器指標"""
        if not PROMETHEUS_AVAILABLE:
            return Counter()

        try:
            labels = labels or []
            counter = Counter(name, help, labels, registry=self.registry)
            self.metrics[name] = counter
            logger.debug(f"📊 註冊計數器: {name}")
            return counter
        except Exception as e:
            logger.error(f"❌ 註冊計數器失敗 {name}: {e}")
            return Counter()

    def register_gauge(
        self, name: str, help: str, labels: List[str] = None
    ) -> Gauge:
        """註冊儀表指標"""
        if not PROMETHEUS_AVAILABLE:
            return Gauge()

        try:
            labels = labels or []
            gauge = Gauge(name, help, labels, registry=self.registry)
            self.metrics[name] = gauge
            logger.debug(f"📊 註冊儀表: {name}")
            return gauge
        except Exception as e:
            logger.error(f"❌ 註冊儀表失敗 {name}: {e}")
            return Gauge()

    def register_histogram(
        self,
        name: str,
        help: str,
        labels: List[str] = None,
        buckets: List[float] = None,
    ) -> Histogram:
        """註冊直方圖指標"""
        if not PROMETHEUS_AVAILABLE:
            return Histogram()

        try:
            labels = labels or []
            histogram = Histogram(
                name, help, labels, buckets=buckets, registry=self.registry
            )
            self.metrics[name] = histogram
            logger.debug(f"📊 註冊直方圖: {name}")
            return histogram
        except Exception as e:
            logger.error(f"❌ 註冊直方圖失敗 {name}: {e}")
            return Histogram()

    def register_summary(
        self, name: str, help: str, labels: List[str] = None
    ) -> Summary:
        """註冊摘要指標"""
        if not PROMETHEUS_AVAILABLE:
            return Summary()

        try:
            labels = labels or []
            summary = Summary(name, help, labels, registry=self.registry)
            self.metrics[name] = summary
            logger.debug(f"📊 註冊摘要: {name}")
            return summary
        except Exception as e:
            logger.error(f"❌ 註冊摘要失敗 {name}: {e}")
            return Summary()

    def get_metric(self, name: str) -> Optional[Any]:
        """獲取指標"""
        return self.metrics.get(name)

    # ========== 便捷方法 ==========

    def increment_counter(
        self, name: str, labels: Dict[str, str] = None, value: float = 1
    ):
        """增加計數器"""
        try:
            counter = self.get_metric(name)
            if counter and hasattr(counter, "inc"):
                if labels:
                    counter.labels(**labels).inc(value)
                else:
                    counter.inc(value)
        except Exception as e:
            logger.error(f"❌ 增加計數器失敗 {name}: {e}")

    def set_gauge(
        self, name: str, value: float, labels: Dict[str, str] = None
    ):
        """設置儀表值"""
        try:
            gauge = self.get_metric(name)
            if gauge and hasattr(gauge, "set"):
                if labels:
                    gauge.labels(**labels).set(value)
                else:
                    gauge.set(value)
        except Exception as e:
            logger.error(f"❌ 設置儀表失敗 {name}: {e}")

    def observe_histogram(
        self, name: str, value: float, labels: Dict[str, str] = None
    ):
        """觀察直方圖值"""
        try:
            histogram = self.get_metric(name)
            if histogram and hasattr(histogram, "observe"):
                if labels:
                    histogram.labels(**labels).observe(value)
                else:
                    histogram.observe(value)
        except Exception as e:
            logger.error(f"❌ 觀察直方圖失敗 {name}: {e}")

    def time_histogram(self, name: str, labels: Dict[str, str] = None):
        """計時直方圖裝飾器"""
        if not PROMETHEUS_AVAILABLE:
            return lambda func: func

        def decorator(func):
            def wrapper(*args, **kwargs):
                start_time = time.time()
                try:
                    result = func(*args, **kwargs)
                    duration = time.time() - start_time
                    self.observe_histogram(name, duration, labels)
                    return result
                except Exception:
                    duration = time.time() - start_time
                    error_labels = (labels or {}).copy()
                    error_labels["status"] = "error"
                    self.observe_histogram(name, duration, error_labels)
                    raise

            return wrapper

        return decorator

    async def time_histogram_async(
        self, name: str, labels: Dict[str, str] = None
    ):
        """異步計時直方圖上下文管理器"""

        class AsyncTimer:
            def __init__(self, metrics_manager, metric_name, metric_labels):
                self.metrics_manager = metrics_manager
                self.metric_name = metric_name
                self.metric_labels = metric_labels
                self.start_time = None

            async def __aenter__(self):
                self.start_time = time.time()
                return self

            async def __aexit__(self, exc_type, exc_val, exc_tb):
                duration = time.time() - self.start_time
                final_labels = (self.metric_labels or {}).copy()

                if exc_type:
                    final_labels["status"] = "error"
                else:
                    final_labels["status"] = "success"

                self.metrics_manager.observe_histogram(
                    self.metric_name, duration, final_labels
                )

        return AsyncTimer(self, name, labels)

    # ========== 高級功能 ==========

    async def collect_system_metrics(self):
        """收集系統指標"""
        try:
            import psutil

            # CPU 使用率
            cpu_percent = psutil.cpu_percent(interval=1)
            self.set_gauge("potato_bot_cpu_usage_percent", cpu_percent)

            # 記憶體使用
            memory = psutil.virtual_memory()
            self.set_gauge(
                "potato_bot_memory_usage_bytes", memory.used, {"type": "used"}
            )
            self.set_gauge(
                "potato_bot_memory_usage_bytes",
                memory.available,
                {"type": "available"},
            )

            # 進程資訊
            process = psutil.Process()
            process_memory = process.memory_info()
            self.set_gauge(
                "potato_bot_memory_usage_bytes",
                process_memory.rss,
                {"type": "process_rss"},
            )
            self.set_gauge(
                "potato_bot_memory_usage_bytes",
                process_memory.vms,
                {"type": "process_vms"},
            )

        except ImportError:
            logger.warning("⚠️ psutil 不可用，無法收集系統指標")
        except Exception as e:
            logger.error(f"❌ 收集系統指標失敗: {e}")

    async def collect_discord_metrics(self, bot):
        """收集 Discord Bot 指標"""
        try:
            if not bot:
                return

            # 基本統計
            guild_count = len(bot.guilds)
            user_count = sum(
                guild.member_count
                for guild in bot.guilds
                if guild.member_count
            )

            self.set_gauge("potato_bot_guilds_total", guild_count)
            self.set_gauge("potato_bot_users_total", user_count)

            # 延遲
            latency = bot.latency
            self.set_gauge("potato_bot_latency_seconds", latency)

            # 按伺服器統計活躍票券（需要從資料庫獲取）
            # 這部分需要與票券 DAO 整合

        except Exception as e:
            logger.error(f"❌ 收集 Discord 指標失敗: {e}")

    async def collect_cache_metrics(self, cache_manager):
        """收集快取指標"""
        try:
            if not cache_manager:
                return

            stats = await cache_manager.get_statistics()

            # 命中率
            hit_rate = float(stats["requests"]["hit_rate"].rstrip("%"))
            self.set_gauge(
                "potato_bot_cache_hit_rate", hit_rate, {"level": "total"}
            )

            l1_hit_rate = float(stats["l1_memory"]["hit_rate"].rstrip("%"))
            self.set_gauge(
                "potato_bot_cache_hit_rate", l1_hit_rate, {"level": "l1"}
            )

            l2_hit_rate = float(stats["l2_redis"]["hit_rate"].rstrip("%"))
            self.set_gauge(
                "potato_bot_cache_hit_rate", l2_hit_rate, {"level": "l2"}
            )

            # 快取大小
            self.set_gauge(
                "potato_bot_cache_size",
                stats["l1_memory"]["size"],
                {"level": "l1"},
            )

            # 操作統計
            self.set_gauge(
                "potato_bot_cache_operations_total",
                stats["operations"]["sets"],
                {"operation": "set", "level": "all", "status": "success"},
            )

        except Exception as e:
            logger.error(f"❌ 收集快取指標失敗: {e}")

    async def collect_database_metrics(self, db_optimizer):
        """收集資料庫指標"""
        try:
            if not db_optimizer:
                return

            metrics = await db_optimizer.collect_database_metrics()

            # 資料庫性能指標
            self.set_gauge(
                "potato_bot_db_query_cache_hit_rate",
                metrics.query_cache_hit_rate,
            )
            self.set_gauge(
                "potato_bot_db_slow_queries", metrics.slow_query_count
            )
            self.set_gauge(
                "potato_bot_db_connections_active", metrics.connections_used
            )

            # InnoDB 緩衝池命中率
            self.set_gauge(
                "potato_bot_db_innodb_buffer_pool_hit_rate",
                metrics.innodb_buffer_pool_hit_rate,
            )

        except Exception as e:
            logger.error(f"❌ 收集資料庫指標失敗: {e}")

    # ========== HTTP 服務器 ==========

    async def _start_http_server(self):
        """啟動 HTTP 指標服務器"""
        if not PROMETHEUS_AVAILABLE:
            logger.warning("⚠️ Prometheus 不可用，無法啟動 HTTP 服務器")
            return

        try:
            # 在背景線程中啟動 HTTP 服務器
            def start_server():
                start_http_server(self.http_port, registry=self.registry)
                logger.info(
                    f"✅ Prometheus HTTP 服務器啟動: http://localhost:{self.http_port}"
                )

            # 在執行器中運行以避免阻塞
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, start_server)

        except Exception as e:
            logger.error(f"❌ 啟動 HTTP 服務器失敗: {e}")

    def get_metrics_data(self) -> str:
        """獲取指標數據（Prometheus 格式）"""
        if not PROMETHEUS_AVAILABLE:
            return "# Prometheus not available\n"

        try:
            return generate_latest(self.registry)
        except Exception as e:
            logger.error(f"❌ 生成指標數據失敗: {e}")
            return f"# Error generating metrics: {e}\n"

    # ========== 推送網關 ==========

    async def push_metrics(self):
        """推送指標到 Push Gateway"""
        if not PROMETHEUS_AVAILABLE or not self.enable_push_gateway:
            return

        try:
            push_to_gateway(
                self.push_gateway_url,
                job=self.job_name,
                registry=self.registry,
            )
            logger.debug("📤 指標已推送到 Push Gateway")

        except Exception as e:
            logger.error(f"❌ 推送指標失敗: {e}")

    # ========== 自動收集循環 ==========

    async def _metrics_collection_loop(self):
        """指標收集循環"""
        while True:
            try:
                start_time = time.time()

                # 收集系統指標
                await self.collect_system_metrics()

                # 更新統計
                self.stats["metrics_collected"] += 1
                self.stats["last_collection"] = datetime.now(timezone.utc)

                collection_time = time.time() - start_time

                # 推送到 Gateway（如果啟用）
                if self.enable_push_gateway:
                    await self.push_metrics()

                logger.debug(f"📊 指標收集完成 - 耗時: {collection_time:.3f}s")

                # 等待下次收集
                await asyncio.sleep(15)  # 每15秒收集一次

            except Exception as e:
                logger.error(f"❌ 指標收集循環錯誤: {e}")
                await asyncio.sleep(30)  # 錯誤時等待更長時間

    def get_collection_stats(self) -> Dict[str, Any]:
        """獲取收集統計"""
        return self.stats.copy()


# ========== 全域實例和便捷函數 ==========

# 創建全域 Prometheus 管理器實例
prometheus_metrics = PrometheusMetricsManager()


async def init_prometheus(
    start_http_server: bool = True, push_gateway_url: str = None
):
    """初始化 Prometheus 監控"""
    await prometheus_metrics.initialize(start_http_server, push_gateway_url)


def get_prometheus_metrics() -> PrometheusMetricsManager:
    """獲取 Prometheus 指標管理器"""
    return prometheus_metrics


# 裝飾器：自動監控函數執行
def monitored(
    metric_name: str,
    labels: Dict[str, str] = None,
    metric_type: str = "histogram",
):
    """監控裝飾器"""

    def decorator(func: Callable):
        async def async_wrapper(*args, **kwargs):
            start_time = time.time()
            final_labels = (labels or {}).copy()

            try:
                result = await func(*args, **kwargs)
                final_labels["status"] = "success"

                if metric_type == "counter":
                    prometheus_metrics.increment_counter(
                        metric_name, final_labels
                    )
                elif metric_type == "histogram":
                    duration = time.time() - start_time
                    prometheus_metrics.observe_histogram(
                        metric_name, duration, final_labels
                    )

                return result

            except Exception as e:
                final_labels["status"] = "error"
                final_labels["error_type"] = type(e).__name__

                if metric_type == "counter":
                    prometheus_metrics.increment_counter(
                        metric_name, final_labels
                    )
                elif metric_type == "histogram":
                    duration = time.time() - start_time
                    prometheus_metrics.observe_histogram(
                        metric_name, duration, final_labels
                    )

                raise

        def sync_wrapper(*args, **kwargs):
            start_time = time.time()
            final_labels = (labels or {}).copy()

            try:
                result = func(*args, **kwargs)
                final_labels["status"] = "success"

                if metric_type == "counter":
                    prometheus_metrics.increment_counter(
                        metric_name, final_labels
                    )
                elif metric_type == "histogram":
                    duration = time.time() - start_time
                    prometheus_metrics.observe_histogram(
                        metric_name, duration, final_labels
                    )

                return result

            except Exception as e:
                final_labels["status"] = "error"
                final_labels["error_type"] = type(e).__name__

                if metric_type == "counter":
                    prometheus_metrics.increment_counter(
                        metric_name, final_labels
                    )
                elif metric_type == "histogram":
                    duration = time.time() - start_time
                    prometheus_metrics.observe_histogram(
                        metric_name, duration, final_labels
                    )

                raise

        # 檢查是否為異步函數
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper

    return decorator


# 快捷函數
def track_command_execution(
    command_name: str, guild_id: int, success: bool = True
):
    """追蹤指令執行"""
    labels = {
        "command": command_name,
        "guild": str(guild_id),
        "status": "success" if success else "error",
    }
    prometheus_metrics.increment_counter("potato_bot_commands_total", labels)


def track_ticket_creation(guild_id: int, category: str):
    """追蹤票券創建"""
    labels = {"guild": str(guild_id), "category": category}
    prometheus_metrics.increment_counter("potato_bot_tickets_total", labels)


def update_active_tickets(guild_id: int, status: str, count: int):
    """更新活躍票券數量"""
    labels = {"guild": str(guild_id), "status": status}
    prometheus_metrics.set_gauge("potato_bot_active_tickets", count, labels)
