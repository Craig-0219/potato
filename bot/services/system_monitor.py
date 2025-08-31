# bot/services/system_monitor.py
"""
系統監控管理器
提供即時系統狀態監控和效能指標追蹤
"""

import asyncio
from datetime import datetime
from typing import Any, Dict, List, Optional

import aiomysql
import psutil

from bot.db.pool import db_pool
from shared.logger import logger


class SystemMonitor:
    """系統監控管理器"""

    def __init__(self):
        self.db = db_pool
        self.monitoring_active = False
        self.start_time = datetime.now()
        self.metrics_cache = {}
        self.bot = None

    async def initialize(self, bot=None):
        """初始化監控器"""
        try:
            self.bot = bot
            self.monitoring_active = True

            # 啟動監控任務
            asyncio.create_task(self._monitor_loop())

            logger.info("✅ 系統監控器初始化完成")

        except Exception as e:
            logger.error(f"❌ 系統監控器初始化失敗: {e}")

    async def _monitor_loop(self):
        """監控循環"""
        while self.monitoring_active:
            try:
                # 收集系統指標
                await self._collect_system_metrics()

                # 收集 Discord Bot 指標
                if self.bot:
                    await self._collect_bot_metrics()

                # 收集票券系統指標
                await self._collect_ticket_metrics()

                # 每 30 秒執行一次
                await asyncio.sleep(30)

            except Exception as e:
                logger.error(f"監控循環錯誤: {e}")
                await asyncio.sleep(60)  # 錯誤時等待更長時間

    async def _collect_system_metrics(self):
        """收集系統效能指標"""
        try:
            # CPU 使用率
            cpu_percent = psutil.cpu_percent(interval=1)
            await self._record_metric(
                "system", "cpu_usage", cpu_percent, "percent", "system"
            )

            # 記憶體使用率
            memory = psutil.virtual_memory()
            memory_percent = memory.percent
            memory_mb = memory.used / 1024 / 1024
            await self._record_metric(
                "system", "memory_usage", memory_percent, "percent", "system"
            )
            await self._record_metric(
                "system", "memory_mb", memory_mb, "mb", "system"
            )

            # 磁碟使用率
            disk = psutil.disk_usage("/")
            disk_percent = (disk.used / disk.total) * 100
            await self._record_metric(
                "system", "disk_usage", disk_percent, "percent", "system"
            )

            # 系統運行時間
            uptime_seconds = (datetime.now() - self.start_time).total_seconds()
            await self._record_metric(
                "system", "uptime", uptime_seconds, "seconds", "system"
            )

            # 負載平均
            if hasattr(psutil, "getloadavg"):
                load_avg = psutil.getloadavg()[0]  # 1分鐘負載
                await self._record_metric(
                    "system", "load_average", load_avg, "ratio", "system"
                )

        except Exception as e:
            logger.error(f"收集系統指標失敗: {e}")

    async def _collect_bot_metrics(self):
        """收集 Discord Bot 指標"""
        try:
            # Bot 延遲
            latency_ms = self.bot.latency * 1000
            await self._record_metric(
                "bot", "latency", latency_ms, "ms", "performance"
            )

            # 伺服器數量
            guild_count = len(self.bot.guilds)
            await self._record_metric(
                "bot", "guild_count", guild_count, "count", "bot"
            )

            # 用戶數量
            user_count = len(self.bot.users)
            await self._record_metric(
                "bot", "user_count", user_count, "count", "bot"
            )

            # 快取統計
            if hasattr(self.bot, "_connection"):
                connection = self.bot._connection
                if hasattr(connection, "_messages"):
                    cached_messages = len(connection._messages)
                    await self._record_metric(
                        "bot",
                        "cached_messages",
                        cached_messages,
                        "count",
                        "cache",
                    )

            # 每個伺服器的統計
            for guild in self.bot.guilds:
                guild_id = str(guild.id)
                member_count = guild.member_count
                await self._record_metric(
                    guild_id, "member_count", member_count, "count", "guild"
                )

                # 在線成員數
                online_members = len(
                    [
                        m
                        for m in guild.members
                        if m.status != discord.Status.offline
                    ]
                )
                await self._record_metric(
                    guild_id,
                    "online_members",
                    online_members,
                    "count",
                    "guild",
                )

        except Exception as e:
            logger.error(f"收集 Bot 指標失敗: {e}")

    async def _collect_ticket_metrics(self):
        """收集票券系統指標"""
        try:
            async with self.db.connection() as conn:
                async with conn.cursor(aiomysql.DictCursor) as cursor:
                    # 活躍票券數
                    await cursor.execute(
                        "SELECT COUNT(*) as count FROM tickets WHERE status = 'open'"
                    )
                    result = await cursor.fetchone()
                    active_tickets = result["count"] if result else 0
                    await self._record_metric(
                        "tickets",
                        "active_tickets",
                        active_tickets,
                        "count",
                        "tickets",
                    )

                    # 今日新建票券數
                    await cursor.execute(
                        """
                        SELECT COUNT(*) as count FROM tickets
                        WHERE DATE(created_at) = CURDATE()
                    """
                    )
                    result = await cursor.fetchone()
                    today_tickets = result["count"] if result else 0
                    await self._record_metric(
                        "tickets",
                        "today_new_tickets",
                        today_tickets,
                        "count",
                        "tickets",
                    )

                    # 今日關閉票券數
                    await cursor.execute(
                        """
                        SELECT COUNT(*) as count FROM tickets
                        WHERE DATE(closed_at) = CURDATE() AND status = 'closed'
                    """
                    )
                    result = await cursor.fetchone()
                    today_closed = result["count"] if result else 0
                    await self._record_metric(
                        "tickets",
                        "today_closed_tickets",
                        today_closed,
                        "count",
                        "tickets",
                    )

                    # 平均回應時間（分鐘）
                    await cursor.execute(
                        """
                        SELECT AVG(TIMESTAMPDIFF(MINUTE, created_at,
                            COALESCE(first_response_at, assigned_at, updated_at))) as avg_response
                        FROM tickets
                        WHERE created_at >= DATE_SUB(NOW(), INTERVAL 24 HOUR)
                        AND (first_response_at IS NOT NULL OR assigned_at IS NOT NULL)
                    """
                    )
                    result = await cursor.fetchone()
                    avg_response = (
                        result["avg_response"]
                        if result and result["avg_response"]
                        else 0
                    )
                    await self._record_metric(
                        "tickets",
                        "avg_response_time",
                        float(avg_response),
                        "minutes",
                        "performance",
                    )

                    # 平均解決時間（小時）
                    await cursor.execute(
                        """
                        SELECT AVG(TIMESTAMPDIFF(HOUR, created_at, closed_at)) as avg_resolution
                        FROM tickets
                        WHERE closed_at >= DATE_SUB(NOW(), INTERVAL 24 HOUR)
                        AND status = 'closed'
                    """
                    )
                    result = await cursor.fetchone()
                    avg_resolution = (
                        result["avg_resolution"]
                        if result and result["avg_resolution"]
                        else 0
                    )
                    await self._record_metric(
                        "tickets",
                        "avg_resolution_time",
                        float(avg_resolution),
                        "hours",
                        "performance",
                    )

                    # 用戶滿意度（平均評分）
                    await cursor.execute(
                        """
                        SELECT AVG(rating) as avg_rating, COUNT(*) as rating_count
                        FROM tickets
                        WHERE rating IS NOT NULL
                        AND closed_at >= DATE_SUB(NOW(), INTERVAL 7 DAY)
                    """
                    )
                    result = await cursor.fetchone()
                    if result and result["avg_rating"]:
                        await self._record_metric(
                            "tickets",
                            "avg_rating",
                            float(result["avg_rating"]),
                            "stars",
                            "satisfaction",
                        )
                        await self._record_metric(
                            "tickets",
                            "rating_count_7d",
                            result["rating_count"],
                            "count",
                            "satisfaction",
                        )

        except Exception as e:
            logger.error(f"收集票券指標失敗: {e}")

    async def _record_metric(
        self,
        guild_id: str,
        metric_name: str,
        value: float,
        unit: str = None,
        category: str = None,
    ):
        """記錄指標到資料庫"""
        try:
            # 更新快取
            cache_key = f"{guild_id}:{metric_name}"
            self.metrics_cache[cache_key] = {
                "value": value,
                "timestamp": datetime.now(),
                "unit": unit,
                "category": category,
            }

            # 插入資料庫（只保留最近的記錄）
            async with self.db.connection() as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute(
                        """
                        INSERT INTO system_metrics
                        (guild_id, metric_name, metric_value, metric_unit, metric_category, recorded_at)
                        VALUES (%s, %s, %s, %s, %s, NOW())
                    """,
                        (
                            (
                                None
                                if guild_id in ["system", "bot", "tickets"]
                                else int(guild_id)
                            ),
                            metric_name,
                            value,
                            unit,
                            category,
                        ),
                    )

                    # 清理舊記錄（保留最近 24 小時）
                    await cursor.execute(
                        """
                        DELETE FROM system_metrics
                        WHERE recorded_at < DATE_SUB(NOW(), INTERVAL 24 HOUR)
                        AND guild_id = %s AND metric_name = %s
                    """,
                        (
                            (
                                None
                                if guild_id in ["system", "bot", "tickets"]
                                else int(guild_id)
                            ),
                            metric_name,
                        ),
                    )

                    await conn.commit()

        except Exception as e:
            logger.error(f"記錄指標失敗 ({guild_id}:{metric_name}): {e}")

    async def get_current_metrics(
        self, guild_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """獲取當前系統指標"""
        try:
            metrics = {}

            # 從快取獲取最新指標
            for cache_key, data in self.metrics_cache.items():
                key_guild_id, metric_name = cache_key.split(":", 1)

                if guild_id and key_guild_id != guild_id:
                    continue

                # 只返回最近 5 分鐘內的數據
                if (datetime.now() - data["timestamp"]).total_seconds() <= 300:
                    if key_guild_id not in metrics:
                        metrics[key_guild_id] = {}

                    metrics[key_guild_id][metric_name] = {
                        "value": data["value"],
                        "unit": data["unit"],
                        "category": data["category"],
                        "timestamp": data["timestamp"].isoformat(),
                    }

            return metrics

        except Exception as e:
            logger.error(f"獲取系統指標失敗: {e}")
            return {}

    async def get_metric_history(
        self, guild_id: str, metric_name: str, hours: int = 24
    ) -> List[Dict[str, Any]]:
        """獲取指標歷史數據"""
        try:
            async with self.db.connection() as conn:
                async with conn.cursor(aiomysql.DictCursor) as cursor:
                    await cursor.execute(
                        """
                        SELECT metric_value, recorded_at
                        FROM system_metrics
                        WHERE (%s IS NULL AND guild_id IS NULL) OR guild_id = %s
                        AND metric_name = %s
                        AND recorded_at >= DATE_SUB(NOW(), INTERVAL %s HOUR)
                        ORDER BY recorded_at ASC
                    """,
                        (
                            (
                                None
                                if guild_id in ["system", "bot", "tickets"]
                                else guild_id
                            ),
                            (
                                None
                                if guild_id in ["system", "bot", "tickets"]
                                else int(guild_id)
                            ),
                            metric_name,
                            hours,
                        ),
                    )

                    results = await cursor.fetchall()
                    return [
                        {
                            "value": float(row["metric_value"]),
                            "timestamp": row["recorded_at"].isoformat(),
                        }
                        for row in results
                    ]

        except Exception as e:
            logger.error(f"獲取指標歷史失敗: {e}")
            return []

    async def get_system_health_score(self) -> Dict[str, Any]:
        """計算系統健康評分"""
        try:
            health_score = 100
            issues = []

            current_metrics = await self.get_current_metrics()
            system_metrics = current_metrics.get("system", {})

            # CPU 檢查
            cpu_usage = system_metrics.get("cpu_usage", {}).get("value", 0)
            if cpu_usage > 80:
                health_score -= 20
                issues.append(f"CPU 使用率過高: {cpu_usage:.1f}%")
            elif cpu_usage > 60:
                health_score -= 10
                issues.append(f"CPU 使用率較高: {cpu_usage:.1f}%")

            # 記憶體檢查
            memory_usage = system_metrics.get("memory_usage", {}).get(
                "value", 0
            )
            if memory_usage > 85:
                health_score -= 20
                issues.append(f"記憶體使用率過高: {memory_usage:.1f}%")
            elif memory_usage > 70:
                health_score -= 10
                issues.append(f"記憶體使用率較高: {memory_usage:.1f}%")

            # Bot 延遲檢查
            bot_metrics = current_metrics.get("bot", {})
            latency = bot_metrics.get("latency", {}).get("value", 0)
            if latency > 500:
                health_score -= 15
                issues.append(f"Bot 延遲過高: {latency:.1f}ms")
            elif latency > 200:
                health_score -= 5
                issues.append(f"Bot 延遲較高: {latency:.1f}ms")

            # 票券系統檢查
            ticket_metrics = current_metrics.get("tickets", {})
            avg_response = ticket_metrics.get("avg_response_time", {}).get(
                "value", 0
            )
            if avg_response > 60:  # 超過 60 分鐘
                health_score -= 15
                issues.append(f"平均回應時間過長: {avg_response:.1f} 分鐘")

            health_score = max(0, health_score)  # 不低於 0

            return {
                "score": health_score,
                "status": (
                    "excellent"
                    if health_score >= 90
                    else (
                        "good"
                        if health_score >= 70
                        else "warning" if health_score >= 50 else "critical"
                    )
                ),
                "issues": issues,
                "timestamp": datetime.now().isoformat(),
            }

        except Exception as e:
            logger.error(f"計算系統健康評分失敗: {e}")
            return {
                "score": 0,
                "status": "unknown",
                "issues": ["無法計算健康評分"],
                "timestamp": datetime.now().isoformat(),
            }

    async def generate_performance_report(
        self, hours: int = 24
    ) -> Dict[str, Any]:
        """生成效能報告"""
        try:
            report = {
                "period": f"最近 {hours} 小時",
                "generated_at": datetime.now().isoformat(),
                "system_health": await self.get_system_health_score(),
                "metrics_summary": {},
                "trends": {},
            }

            # 關鍵指標摘要
            key_metrics = [
                ("system", "cpu_usage"),
                ("system", "memory_usage"),
                ("bot", "latency"),
                ("tickets", "active_tickets"),
                ("tickets", "avg_response_time"),
                ("tickets", "avg_rating"),
            ]

            for guild_id, metric_name in key_metrics:
                history = await self.get_metric_history(
                    guild_id, metric_name, hours
                )
                if history:
                    values = [h["value"] for h in history]
                    report["metrics_summary"][f"{guild_id}_{metric_name}"] = {
                        "current": values[-1] if values else 0,
                        "average": sum(values) / len(values),
                        "min": min(values),
                        "max": max(values),
                        "trend": (
                            "up"
                            if len(values) > 1 and values[-1] > values[0]
                            else (
                                "down"
                                if len(values) > 1 and values[-1] < values[0]
                                else "stable"
                            )
                        ),
                    }

            return report

        except Exception as e:
            logger.error(f"生成效能報告失敗: {e}")
            return {"error": str(e)}

    async def shutdown(self):
        """關閉監控器"""
        self.monitoring_active = False
        logger.info("系統監控器已關閉")


# 全局監控器實例
system_monitor = SystemMonitor()
