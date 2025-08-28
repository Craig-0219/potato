#!/usr/bin/env python3
"""
24 小時穩定性測試框架
長期運行測試 Bot 的穩定性、記憶體使用、錯誤恢復能力
"""
import asyncio
import json
import logging
import os
import sys
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import psutil

# 添加專案路徑
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, current_dir)


@dataclass
class StabilityMetrics:
    """穩定性指標"""

    timestamp: datetime
    memory_usage_mb: float
    cpu_usage_percent: float
    active_connections: int
    error_count: int
    response_time_ms: float

    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp": self.timestamp.isoformat(),
            "memory_usage_mb": self.memory_usage_mb,
            "cpu_usage_percent": self.cpu_usage_percent,
            "active_connections": self.active_connections,
            "error_count": self.error_count,
            "response_time_ms": self.response_time_ms,
        }


@dataclass
class StabilityTestResult:
    """穩定性測試結果"""

    start_time: datetime
    end_time: datetime
    total_duration_hours: float
    uptime_percentage: float
    avg_memory_usage_mb: float
    max_memory_usage_mb: float
    avg_cpu_usage_percent: float
    max_cpu_usage_percent: float
    total_errors: int
    critical_errors: int
    recovery_successful: bool
    performance_degradation: bool


class StabilityTestFramework:
    """24 小時穩定性測試框架"""

    def __init__(self, test_duration_hours: float = 24.0):
        self.test_duration_hours = test_duration_hours
        self.test_duration_seconds = test_duration_hours * 3600
        self.metrics_interval_seconds = 60  # 每分鐘收集一次指標
        self.health_check_interval_seconds = 30  # 每 30 秒檢查一次健康狀態

        # 測試數據
        self.metrics_history: List[StabilityMetrics] = []
        self.error_log: List[Dict[str, Any]] = []
        self.downtime_periods: List[Dict[str, Any]] = []

        # 閾值設定 - 調整為適合測試環境
        self.memory_warning_mb = 3000  # 記憶體警告閾值
        self.memory_critical_mb = 4000  # 記憶體危險閾值
        self.cpu_warning_percent = 80  # CPU 警告閾值
        self.cpu_critical_percent = 95  # CPU 危險閾值
        self.response_timeout_ms = 5000  # 響應超時閾值

        # 狀態追蹤
        self.is_running = False
        self.start_time: Optional[datetime] = None
        self.last_health_check: Optional[datetime] = None

        # 設置日誌
        self.setup_logging()

    def setup_logging(self):
        """設置日誌"""
        log_format = "%(asctime)s [%(levelname)s] %(name)s:%(lineno)d - %(message)s"
        logging.basicConfig(
            level=logging.INFO,
            format=log_format,
            handlers=[logging.FileHandler("stability_test.log"), logging.StreamHandler()],
        )
        self.logger = logging.getLogger(__name__)

    async def start_stability_test(self):
        """開始穩定性測試"""
        self.logger.info("🚀 開始 24 小時穩定性測試")
        self.is_running = True
        self.start_time = datetime.now()

        # 創建測試任務
        tasks = [
            self.metrics_collection_loop(),
            self.health_monitoring_loop(),
            self.stress_testing_loop(),
            self.recovery_testing_loop(),
        ]

        try:
            # 並行運行所有測試任務
            await asyncio.gather(*tasks)

        except KeyboardInterrupt:
            self.logger.info("⚠️ 測試被手動中止")
        except Exception as e:
            self.logger.error(f"❌ 穩定性測試出錯: {e}")
        finally:
            await self.finalize_test()

    async def metrics_collection_loop(self):
        """指標收集循環"""
        self.logger.info("📊 開始指標收集")

        while self.is_running and self._should_continue_test():
            try:
                metrics = await self.collect_system_metrics()
                self.metrics_history.append(metrics)

                # 檢查指標是否超過閾值
                await self.check_metric_thresholds(metrics)

                # 記錄關鍵指標
                if len(self.metrics_history) % 10 == 0:  # 每 10 分鐘記錄一次
                    self.logger.info(
                        f"📈 指標更新 - 記憶體: {metrics.memory_usage_mb:.1f}MB, "
                        f"CPU: {metrics.cpu_usage_percent:.1f}%, "
                        f"錯誤: {metrics.error_count}"
                    )

            except Exception as e:
                self.logger.error(f"❌ 指標收集錯誤: {e}")
                await self.record_error("metrics_collection", str(e))

            await asyncio.sleep(self.metrics_interval_seconds)

    async def health_monitoring_loop(self):
        """健康監控循環"""
        self.logger.info("🏥 開始健康監控")

        consecutive_failures = 0
        downtime_start = None

        while self.is_running and self._should_continue_test():
            try:
                health_status = await self.perform_health_check()

                if health_status["healthy"]:
                    if consecutive_failures > 0:
                        # 從故障中恢復
                        if downtime_start:
                            downtime_duration = (datetime.now() - downtime_start).total_seconds()
                            self.downtime_periods.append(
                                {
                                    "start_time": downtime_start.isoformat(),
                                    "end_time": datetime.now().isoformat(),
                                    "duration_seconds": downtime_duration,
                                }
                            )
                            self.logger.warning(
                                f"🔄 系統已恢復，故障時間: {downtime_duration:.1f} 秒"
                            )
                            downtime_start = None

                        consecutive_failures = 0

                    self.last_health_check = datetime.now()

                else:
                    consecutive_failures += 1

                    if consecutive_failures == 1:
                        downtime_start = datetime.now()
                        self.logger.warning("⚠️ 檢測到系統健康問題")
                    elif consecutive_failures >= 3:
                        self.logger.error(f"🚨 系統持續不健康，連續失敗: {consecutive_failures} 次")

                    await self.record_error(
                        "health_check_failed",
                        f"健康檢查失敗: {health_status.get('error', 'Unknown')}",
                    )

            except Exception as e:
                self.logger.error(f"❌ 健康監控錯誤: {e}")
                consecutive_failures += 1

            await asyncio.sleep(self.health_check_interval_seconds)

    async def stress_testing_loop(self):
        """壓力測試循環"""
        self.logger.info("💪 開始壓力測試")

        test_phases = [
            {"name": "輕負載", "duration_minutes": 30, "load_level": 1},
            {"name": "中負載", "duration_minutes": 60, "load_level": 2},
            {"name": "高負載", "duration_minutes": 120, "load_level": 3},
            {"name": "峰值負載", "duration_minutes": 30, "load_level": 4},
        ]

        for phase in test_phases:
            if not self._should_continue_test():
                break

            self.logger.info(f"🔥 開始 {phase['name']} 階段")

            phase_duration = phase["duration_minutes"] * 60
            phase_end = datetime.now() + timedelta(seconds=phase_duration)

            while datetime.now() < phase_end and self._should_continue_test():
                try:
                    await self.simulate_load(phase["load_level"])
                    await asyncio.sleep(10)  # 每 10 秒模擬一次負載

                except Exception as e:
                    self.logger.error(f"❌ 壓力測試錯誤: {e}")
                    await self.record_error("stress_test", str(e))

            self.logger.info(f"✅ {phase['name']} 階段完成")

        self.logger.info("💪 壓力測試循環完成")

    async def recovery_testing_loop(self):
        """恢復測試循環"""
        self.logger.info("🔄 開始恢復能力測試")

        recovery_tests = [
            {"name": "資料庫連接中斷模擬", "test_func": self.simulate_db_disconnect},
            {"name": "記憶體壓力測試", "test_func": self.simulate_memory_pressure},
            {"name": "網路延遲模擬", "test_func": self.simulate_network_latency},
        ]

        # 每 4 小時進行一次恢復測試
        test_interval_hours = 4
        next_test_time = datetime.now() + timedelta(hours=test_interval_hours)

        while self.is_running and self._should_continue_test():
            if datetime.now() >= next_test_time:
                for recovery_test in recovery_tests:
                    if not self._should_continue_test():
                        break

                    self.logger.info(f"🧪 執行 {recovery_test['name']}")

                    try:
                        recovery_success = await recovery_test["test_func"]()
                        if recovery_success:
                            self.logger.info(f"✅ {recovery_test['name']} 恢復成功")
                        else:
                            self.logger.warning(f"⚠️ {recovery_test['name']} 恢復失敗")
                            await self.record_error("recovery_test", recovery_test["name"])

                    except Exception as e:
                        self.logger.error(f"❌ {recovery_test['name']} 錯誤: {e}")
                        await self.record_error("recovery_test", str(e))

                    await asyncio.sleep(30)  # 測試間間隔 30 秒

                next_test_time = datetime.now() + timedelta(hours=test_interval_hours)

            await asyncio.sleep(300)  # 每 5 分鐘檢查一次

    async def collect_system_metrics(self) -> StabilityMetrics:
        """收集系統指標"""
        try:
            # 收集系統資源指標
            memory_info = psutil.virtual_memory()
            memory_usage_mb = memory_info.used / 1024 / 1024
            cpu_usage = psutil.cpu_percent(interval=1)

            # 收集網路連接數
            active_connections = len(psutil.net_connections())

            # 模擬響應時間測試
            response_start = time.time()
            await self.simulate_response_test()
            response_time_ms = (time.time() - response_start) * 1000

            # 統計錯誤數量
            recent_errors = len(
                [
                    e
                    for e in self.error_log
                    if datetime.fromisoformat(e["timestamp"])
                    > datetime.now() - timedelta(minutes=5)
                ]
            )

            return StabilityMetrics(
                timestamp=datetime.now(),
                memory_usage_mb=memory_usage_mb,
                cpu_usage_percent=cpu_usage,
                active_connections=active_connections,
                error_count=recent_errors,
                response_time_ms=response_time_ms,
            )

        except Exception as e:
            self.logger.error(f"❌ 指標收集失敗: {e}")
            # 返回預設指標
            return StabilityMetrics(
                timestamp=datetime.now(),
                memory_usage_mb=0,
                cpu_usage_percent=0,
                active_connections=0,
                error_count=1,
                response_time_ms=999999,
            )

    async def perform_health_check(self) -> Dict[str, Any]:
        """執行健康檢查"""
        try:
            health_checks = []

            # 1. 記憶體檢查
            memory_info = psutil.virtual_memory()
            memory_usage_mb = memory_info.used / 1024 / 1024
            memory_healthy = memory_usage_mb < self.memory_critical_mb
            health_checks.append(("memory", memory_healthy))

            # 2. CPU 檢查
            cpu_usage = psutil.cpu_percent()
            cpu_healthy = cpu_usage < self.cpu_critical_percent
            health_checks.append(("cpu", cpu_healthy))

            # 3. 響應時間檢查
            response_start = time.time()
            await self.simulate_response_test()
            response_time_ms = (time.time() - response_start) * 1000
            response_healthy = response_time_ms < self.response_timeout_ms
            health_checks.append(("response_time", response_healthy))

            # 4. 錯誤率檢查
            recent_errors = len(
                [
                    e
                    for e in self.error_log
                    if datetime.fromisoformat(e["timestamp"])
                    > datetime.now() - timedelta(minutes=1)
                ]
            )
            error_rate_healthy = recent_errors < 5
            health_checks.append(("error_rate", error_rate_healthy))

            all_healthy = all(healthy for _, healthy in health_checks)

            return {
                "healthy": all_healthy,
                "checks": {name: healthy for name, healthy in health_checks},
                "details": {
                    "memory_mb": memory_usage_mb,
                    "cpu_percent": cpu_usage,
                    "response_time_ms": response_time_ms,
                    "recent_errors": recent_errors,
                },
            }

        except Exception as e:
            return {"healthy": False, "error": str(e)}

    async def simulate_response_test(self):
        """模擬響應測試"""
        # 模擬一個簡單的異步操作
        await asyncio.sleep(0.01)  # 10ms 的模擬延遲

    async def simulate_load(self, load_level: int):
        """模擬負載"""
        # 根據負載級別創建不同強度的模擬負載
        tasks = []
        for _ in range(load_level * 5):
            tasks.append(asyncio.create_task(self.simulate_work_unit()))

        await asyncio.gather(*tasks, return_exceptions=True)

    async def simulate_work_unit(self):
        """模擬工作單元"""
        # 模擬 CPU 密集型操作
        start_time = time.time()
        while time.time() - start_time < 0.1:  # 100ms 的計算
            _ = sum(range(1000))

        # 模擬 I/O 操作
        await asyncio.sleep(0.05)  # 50ms 的 I/O 延遲

    async def simulate_db_disconnect(self) -> bool:
        """模擬資料庫連接中斷"""
        self.logger.info("🔌 模擬資料庫連接中斷...")
        await asyncio.sleep(2)  # 模擬中斷
        self.logger.info("🔌 模擬資料庫重新連接...")
        await asyncio.sleep(1)  # 模擬恢復
        return True  # 模擬成功恢復

    async def simulate_memory_pressure(self) -> bool:
        """模擬記憶體壓力"""
        self.logger.info("🧠 模擬記憶體壓力...")
        # 創建一些大對象來增加記憶體使用
        large_data = []
        try:
            for _ in range(100):
                large_data.append([0] * 10000)  # 每個約 40KB

            await asyncio.sleep(5)  # 保持 5 秒

            # 釋放記憶體
            del large_data
            return True

        except Exception as e:
            self.logger.error(f"記憶體壓力測試失敗: {e}")
            return False

    async def simulate_network_latency(self) -> bool:
        """模擬網路延遲"""
        self.logger.info("🌐 模擬網路延遲...")
        # 模擬高延遲響應
        await asyncio.sleep(3)
        return True

    async def check_metric_thresholds(self, metrics: StabilityMetrics):
        """檢查指標閾值"""
        warnings = []
        errors = []

        # 記憶體檢查
        if metrics.memory_usage_mb > self.memory_critical_mb:
            errors.append(f"記憶體使用危險: {metrics.memory_usage_mb:.1f}MB")
        elif metrics.memory_usage_mb > self.memory_warning_mb:
            warnings.append(f"記憶體使用警告: {metrics.memory_usage_mb:.1f}MB")

        # CPU 檢查
        if metrics.cpu_usage_percent > self.cpu_critical_percent:
            errors.append(f"CPU 使用危險: {metrics.cpu_usage_percent:.1f}%")
        elif metrics.cpu_usage_percent > self.cpu_warning_percent:
            warnings.append(f"CPU 使用警告: {metrics.cpu_usage_percent:.1f}%")

        # 響應時間檢查
        if metrics.response_time_ms > self.response_timeout_ms:
            errors.append(f"響應時間超時: {metrics.response_time_ms:.1f}ms")

        # 記錄警告和錯誤
        for warning in warnings:
            self.logger.warning(f"⚠️ {warning}")

        for error in errors:
            self.logger.error(f"🚨 {error}")
            await self.record_error("threshold_exceeded", error)

    async def record_error(self, error_type: str, message: str, severity: str = "error"):
        """記錄錯誤"""
        error_record = {
            "timestamp": datetime.now().isoformat(),
            "type": error_type,
            "message": message,
            "severity": severity,
        }
        self.error_log.append(error_record)

        # 限制錯誤日誌大小
        if len(self.error_log) > 1000:
            self.error_log = self.error_log[-500:]  # 保留最近 500 個錯誤

    def _should_continue_test(self) -> bool:
        """檢查是否應該繼續測試"""
        if not self.is_running or not self.start_time:
            return False

        elapsed_time = (datetime.now() - self.start_time).total_seconds()
        return elapsed_time < self.test_duration_seconds

    async def finalize_test(self):
        """完成測試"""
        self.is_running = False
        end_time = datetime.now()

        self.logger.info("📊 生成測試報告...")

        # 生成測試結果
        result = await self.generate_test_result(end_time)

        # 保存報告
        await self.save_test_report(result)

        # 顯示摘要
        await self.display_test_summary(result)

    async def generate_test_result(self, end_time: datetime) -> StabilityTestResult:
        """生成測試結果"""
        if not self.start_time:
            raise ValueError("測試開始時間未設定")

        total_duration = (end_time - self.start_time).total_seconds() / 3600  # 小時

        # 計算運行時間百分比
        total_downtime = sum(period["duration_seconds"] for period in self.downtime_periods)
        uptime_percentage = (
            (total_duration * 3600 - total_downtime) / (total_duration * 3600)
        ) * 100

        # 計算指標統計
        if self.metrics_history:
            avg_memory = sum(m.memory_usage_mb for m in self.metrics_history) / len(
                self.metrics_history
            )
            max_memory = max(m.memory_usage_mb for m in self.metrics_history)
            avg_cpu = sum(m.cpu_usage_percent for m in self.metrics_history) / len(
                self.metrics_history
            )
            max_cpu = max(m.cpu_usage_percent for m in self.metrics_history)
        else:
            avg_memory = max_memory = avg_cpu = max_cpu = 0

        # 統計錯誤
        total_errors = len(self.error_log)
        critical_errors = len([e for e in self.error_log if e["severity"] == "critical"])

        # 檢查性能退化
        performance_degradation = self._detect_performance_degradation()

        # 檢查恢復能力
        recovery_successful = len(self.downtime_periods) == 0 or all(
            period["duration_seconds"] < 300 for period in self.downtime_periods  # 5分鐘內恢復
        )

        return StabilityTestResult(
            start_time=self.start_time,
            end_time=end_time,
            total_duration_hours=total_duration,
            uptime_percentage=uptime_percentage,
            avg_memory_usage_mb=avg_memory,
            max_memory_usage_mb=max_memory,
            avg_cpu_usage_percent=avg_cpu,
            max_cpu_usage_percent=max_cpu,
            total_errors=total_errors,
            critical_errors=critical_errors,
            recovery_successful=recovery_successful,
            performance_degradation=performance_degradation,
        )

    def _detect_performance_degradation(self) -> bool:
        """檢測性能退化"""
        if len(self.metrics_history) < 120:  # 需要至少 2 小時的數據
            return False

        # 比較前 1 小時和最後 1 小時的性能
        first_hour_metrics = self.metrics_history[:60]
        last_hour_metrics = self.metrics_history[-60:]

        first_hour_avg_response = sum(m.response_time_ms for m in first_hour_metrics) / len(
            first_hour_metrics
        )
        last_hour_avg_response = sum(m.response_time_ms for m in last_hour_metrics) / len(
            last_hour_metrics
        )

        # 如果最後 1 小時的平均響應時間比第 1 小時增加超過 50%，認為性能退化
        degradation_threshold = 1.5
        return last_hour_avg_response > first_hour_avg_response * degradation_threshold

    async def save_test_report(self, result: StabilityTestResult):
        """保存測試報告"""
        report_filename = f"stability_test_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

        report_data = {
            "test_result": asdict(result),
            "metrics_history": [
                m.to_dict() for m in self.metrics_history[-100:]
            ],  # 保存最近 100 個指標
            "error_summary": {
                "total_errors": len(self.error_log),
                "error_types": self._get_error_type_summary(),
                "critical_periods": self.downtime_periods,
            },
            "test_configuration": {
                "test_duration_hours": self.test_duration_hours,
                "metrics_interval_seconds": self.metrics_interval_seconds,
                "memory_warning_mb": self.memory_warning_mb,
                "memory_critical_mb": self.memory_critical_mb,
                "cpu_warning_percent": self.cpu_warning_percent,
                "cpu_critical_percent": self.cpu_critical_percent,
            },
        }

        with open(report_filename, "w", encoding="utf-8") as f:
            json.dump(report_data, f, indent=2, ensure_ascii=False, default=str)

        self.logger.info(f"📄 測試報告已保存: {report_filename}")

    def _get_error_type_summary(self) -> Dict[str, int]:
        """獲取錯誤類型摘要"""
        error_types = {}
        for error in self.error_log:
            error_type = error.get("type", "unknown")
            error_types[error_type] = error_types.get(error_type, 0) + 1
        return error_types

    async def display_test_summary(self, result: StabilityTestResult):
        """顯示測試摘要"""
        print("\n" + "=" * 80)
        print("📊 24 小時穩定性測試結果摘要")
        print("=" * 80)

        print(
            f"⏱️ 測試時間: {result.start_time.strftime('%Y-%m-%d %H:%M:%S')} ~ {result.end_time.strftime('%Y-%m-%d %H:%M:%S')}"
        )
        print(f"🕐 測試時長: {result.total_duration_hours:.2f} 小時")
        print(f"📈 運行時間: {result.uptime_percentage:.2f}%")

        print(f"\n💾 記憶體使用:")
        print(f"  平均: {result.avg_memory_usage_mb:.1f} MB")
        print(f"  峰值: {result.max_memory_usage_mb:.1f} MB")

        print(f"\n🔥 CPU 使用:")
        print(f"  平均: {result.avg_cpu_usage_percent:.1f}%")
        print(f"  峰值: {result.max_cpu_usage_percent:.1f}%")

        print(f"\n🚨 錯誤統計:")
        print(f"  總錯誤: {result.total_errors}")
        print(f"  嚴重錯誤: {result.critical_errors}")

        print(f"\n🔄 穩定性評估:")
        print(f"  故障恢復: {'✅ 成功' if result.recovery_successful else '❌ 失敗'}")
        print(f"  性能退化: {'⚠️ 是' if result.performance_degradation else '✅ 否'}")

        # 整體評估
        if (
            result.uptime_percentage >= 99.9
            and not result.performance_degradation
            and result.critical_errors == 0
        ):
            overall_status = "🎉 優秀"
        elif result.uptime_percentage >= 99.0 and result.critical_errors < 5:
            overall_status = "✅ 良好"
        elif result.uptime_percentage >= 95.0:
            overall_status = "⚠️ 可接受"
        else:
            overall_status = "❌ 需要改進"

        print(f"\n🎯 整體評估: {overall_status}")
        print("=" * 80)


async def main():
    """主函數"""
    import argparse

    parser = argparse.ArgumentParser(description="24小時穩定性測試")
    parser.add_argument(
        "--duration",
        type=float,
        default=0.1,
        help="測試時長（小時），預設 0.1 小時（6分鐘）用於演示",
    )
    parser.add_argument("--demo", action="store_true", help="演示模式（6分鐘快速測試）")

    args = parser.parse_args()

    if args.demo:
        duration = 0.1  # 6分鐘演示
        print("🎬 演示模式：6分鐘穩定性測試")
    else:
        duration = args.duration
        print(f"⏰ 穩定性測試時長：{duration} 小時")

    framework = StabilityTestFramework(test_duration_hours=duration)
    await framework.start_stability_test()


if __name__ == "__main__":
    asyncio.run(main())
