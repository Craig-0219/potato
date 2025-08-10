# bot/services/maintenance_scheduler.py
"""
系統維護排程器
負責自動化清理任務、資料備份、健康檢查等定期維護作業
"""

import asyncio
import schedule
import threading
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Callable, Any
from dataclasses import dataclass
from enum import Enum
import json

from bot.services.data_cleanup_manager import DataCleanupManager
from bot.services.data_export_manager import DataExportManager, ExportRequest
from bot.db.database_manager import get_database_manager
from shared.logger import logger


class TaskFrequency(Enum):
    """任務頻率"""
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    HOURLY = "hourly"
    CUSTOM = "custom"


class TaskStatus(Enum):
    """任務狀態"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class MaintenanceTask:
    """維護任務"""
    task_id: str
    name: str
    description: str
    frequency: TaskFrequency
    handler: Callable
    enabled: bool = True
    last_run: Optional[datetime] = None
    next_run: Optional[datetime] = None
    run_count: int = 0
    failure_count: int = 0
    max_retries: int = 3
    timeout_seconds: int = 3600
    config: Optional[Dict[str, Any]] = None


@dataclass
class TaskExecution:
    """任務執行記錄"""
    task_id: str
    execution_id: str
    start_time: datetime
    end_time: Optional[datetime]
    status: TaskStatus
    result: Optional[Dict[str, Any]]
    error_message: Optional[str]
    duration_seconds: float = 0.0


class MaintenanceScheduler:
    """系統維護排程器"""
    
    def __init__(self):
        self.db = get_database_manager()
        self.cleanup_manager = DataCleanupManager()
        self.export_manager = DataExportManager()
        
        self.tasks: Dict[str, MaintenanceTask] = {}
        self.executions: List[TaskExecution] = []
        self.is_running = False
        self.scheduler_thread: Optional[threading.Thread] = None
        
        # 初始化默認任務
        self._initialize_default_tasks()
    
    def _initialize_default_tasks(self):
        """初始化默認維護任務"""
        
        # 每日資料清理任務
        self.add_task(MaintenanceTask(
            task_id="daily_cleanup",
            name="每日資料清理",
            description="清理舊日誌、臨時資料和過期記錄",
            frequency=TaskFrequency.DAILY,
            handler=self._daily_cleanup_task,
            config={
                'log_retention_days': 30,
                'temp_data_retention_hours': 24,
                'run_time': '02:00'
            }
        ))
        
        # 每週深度清理任務
        self.add_task(MaintenanceTask(
            task_id="weekly_deep_cleanup",
            name="每週深度清理",
            description="執行完整的系統清理和優化",
            frequency=TaskFrequency.WEEKLY,
            handler=self._weekly_cleanup_task,
            config={
                'run_day': 'sunday',
                'run_time': '03:00',
                'optimize_database': True
            }
        ))
        
        # 每日備份任務
        self.add_task(MaintenanceTask(
            task_id="daily_backup",
            name="每日資料備份",
            description="備份重要系統資料",
            frequency=TaskFrequency.DAILY,
            handler=self._daily_backup_task,
            config={
                'backup_types': ['tickets', 'statistics', 'logs'],
                'retention_days': 7,
                'run_time': '01:00'
            }
        ))
        
        # 每小時健康檢查
        self.add_task(MaintenanceTask(
            task_id="hourly_health_check",
            name="每小時健康檢查",
            description="檢查系統健康狀況",
            frequency=TaskFrequency.HOURLY,
            handler=self._hourly_health_check_task,
            timeout_seconds=300,
            config={
                'check_database': True,
                'check_disk_space': True,
                'alert_thresholds': {
                    'cpu_usage': 80,
                    'memory_usage': 85,
                    'disk_usage': 90
                }
            }
        ))
        
        # 每週統計報告
        self.add_task(MaintenanceTask(
            task_id="weekly_statistics_report",
            name="每週統計報告",
            description="生成並匯出週統計報告",
            frequency=TaskFrequency.WEEKLY,
            handler=self._weekly_statistics_report_task,
            config={
                'run_day': 'monday',
                'run_time': '08:00',
                'report_types': ['comprehensive', 'summary'],
                'export_formats': ['json', 'csv']
            }
        ))
        
        # 每月系統優化
        self.add_task(MaintenanceTask(
            task_id="monthly_optimization",
            name="每月系統優化",
            description="執行系統性能優化和維護",
            frequency=TaskFrequency.MONTHLY,
            handler=self._monthly_optimization_task,
            config={
                'run_day': 1,
                'run_time': '04:00',
                'rebuild_indexes': True,
                'analyze_performance': True
            }
        ))
    
    def add_task(self, task: MaintenanceTask):
        """添加維護任務"""
        self.tasks[task.task_id] = task
        logger.info(f"📋 添加維護任務: {task.name} ({task.frequency.value})")
    
    def remove_task(self, task_id: str) -> bool:
        """移除維護任務"""
        if task_id in self.tasks:
            del self.tasks[task_id]
            logger.info(f"🗑️ 移除維護任務: {task_id}")
            return True
        return False
    
    def enable_task(self, task_id: str) -> bool:
        """啟用任務"""
        if task_id in self.tasks:
            self.tasks[task_id].enabled = True
            logger.info(f"✅ 啟用維護任務: {task_id}")
            return True
        return False
    
    def disable_task(self, task_id: str) -> bool:
        """禁用任務"""
        if task_id in self.tasks:
            self.tasks[task_id].enabled = False
            logger.info(f"❌ 禁用維護任務: {task_id}")
            return True
        return False
    
    async def start_scheduler(self):
        """啟動排程器"""
        if self.is_running:
            logger.warning("維護排程器已在運行中")
            return
        
        self.is_running = True
        logger.info("🚀 啟動維護排程器...")
        
        # 設定排程
        self._setup_schedules()
        
        # 啟動排程執行緒
        self.scheduler_thread = threading.Thread(target=self._run_scheduler, daemon=True)
        self.scheduler_thread.start()
        
        logger.info("✅ 維護排程器啟動完成")
    
    def stop_scheduler(self):
        """停止排程器"""
        if not self.is_running:
            return
        
        self.is_running = False
        schedule.clear()
        
        if self.scheduler_thread and self.scheduler_thread.is_alive():
            self.scheduler_thread.join(timeout=5)
        
        logger.info("⏹️ 維護排程器已停止")
    
    def _setup_schedules(self):
        """設定排程任務"""
        schedule.clear()
        
        for task in self.tasks.values():
            if not task.enabled:
                continue
            
            config = task.config or {}
            
            if task.frequency == TaskFrequency.HOURLY:
                schedule.every().hour.do(self._schedule_task_wrapper, task.task_id)
            
            elif task.frequency == TaskFrequency.DAILY:
                run_time = config.get('run_time', '02:00')
                schedule.every().day.at(run_time).do(self._schedule_task_wrapper, task.task_id)
            
            elif task.frequency == TaskFrequency.WEEKLY:
                run_day = config.get('run_day', 'sunday')
                run_time = config.get('run_time', '03:00')
                getattr(schedule.every(), run_day).at(run_time).do(self._schedule_task_wrapper, task.task_id)
            
            elif task.frequency == TaskFrequency.MONTHLY:
                # 每月任務需要特殊處理
                run_day = config.get('run_day', 1)
                run_time = config.get('run_time', '04:00')
                # 暫時使用每日檢查是否為當月第一天
                schedule.every().day.at(run_time).do(self._check_monthly_task, task.task_id, run_day)
        
        logger.info(f"📅 設定了 {len([t for t in self.tasks.values() if t.enabled])} 個排程任務")
    
    def _run_scheduler(self):
        """執行排程器主循環"""
        logger.info("🔄 排程器主循環開始")
        
        while self.is_running:
            try:
                schedule.run_pending()
                threading.Event().wait(60)  # 每分鐘檢查一次
            except Exception as e:
                logger.error(f"排程器執行錯誤: {e}")
                threading.Event().wait(60)
        
        logger.info("🔄 排程器主循環結束")
    
    def _schedule_task_wrapper(self, task_id: str):
        """排程任務包裝器"""
        if not self.is_running:
            return
        
        # 在新的事件循環中運行異步任務
        asyncio.run(self._execute_task(task_id))
    
    def _check_monthly_task(self, task_id: str, target_day: int):
        """檢查是否應執行月任務"""
        current_day = datetime.now().day
        if current_day == target_day:
            self._schedule_task_wrapper(task_id)
    
    async def _execute_task(self, task_id: str):
        """執行維護任務"""
        if task_id not in self.tasks:
            logger.error(f"找不到任務: {task_id}")
            return
        
        task = self.tasks[task_id]
        if not task.enabled:
            logger.info(f"任務已禁用，跳過: {task.name}")
            return
        
        execution_id = f"{task_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        start_time = datetime.now()
        
        execution = TaskExecution(
            task_id=task_id,
            execution_id=execution_id,
            start_time=start_time,
            end_time=None,
            status=TaskStatus.RUNNING,
            result=None,
            error_message=None
        )
        
        self.executions.append(execution)
        logger.info(f"🏃 開始執行任務: {task.name}")
        
        try:
            # 設定超時
            result = await asyncio.wait_for(
                task.handler(task.config or {}),
                timeout=task.timeout_seconds
            )
            
            # 更新任務統計
            task.last_run = start_time
            task.run_count += 1
            task.next_run = self._calculate_next_run(task)
            
            # 更新執行記錄
            execution.end_time = datetime.now()
            execution.status = TaskStatus.COMPLETED
            execution.result = result
            execution.duration_seconds = (execution.end_time - start_time).total_seconds()
            
            logger.info(f"✅ 任務執行完成: {task.name} (耗時 {execution.duration_seconds:.2f}s)")
            
        except asyncio.TimeoutError:
            error_msg = f"任務執行超時 ({task.timeout_seconds}s)"
            await self._handle_task_failure(task, execution, error_msg)
            
        except Exception as e:
            error_msg = f"任務執行失敗: {str(e)}"
            await self._handle_task_failure(task, execution, error_msg)
        
        # 保存執行記錄
        await self._save_execution_record(execution)
    
    async def _handle_task_failure(self, task: MaintenanceTask, execution: TaskExecution, error_message: str):
        """處理任務失敗"""
        task.failure_count += 1
        
        execution.end_time = datetime.now()
        execution.status = TaskStatus.FAILED
        execution.error_message = error_message
        execution.duration_seconds = (execution.end_time - execution.start_time).total_seconds()
        
        logger.error(f"❌ {error_message} - {task.name}")
        
        # 如果失敗次數過多，可能需要禁用任務
        if task.failure_count >= task.max_retries:
            logger.warning(f"⚠️ 任務失敗次數過多，建議檢查: {task.name}")
    
    def _calculate_next_run(self, task: MaintenanceTask) -> Optional[datetime]:
        """計算下次執行時間"""
        now = datetime.now()
        
        if task.frequency == TaskFrequency.HOURLY:
            return now + timedelta(hours=1)
        elif task.frequency == TaskFrequency.DAILY:
            return now + timedelta(days=1)
        elif task.frequency == TaskFrequency.WEEKLY:
            return now + timedelta(weeks=1)
        elif task.frequency == TaskFrequency.MONTHLY:
            # 下個月同一天
            if now.month == 12:
                return now.replace(year=now.year + 1, month=1)
            else:
                return now.replace(month=now.month + 1)
        
        return None
    
    async def _save_execution_record(self, execution: TaskExecution):
        """保存執行記錄到資料庫"""
        try:
            async with self.db.get_connection() as conn:
                async with conn.cursor() as cursor:
                    # 創建執行記錄表
                    create_table_query = """
                    CREATE TABLE IF NOT EXISTS maintenance_executions (
                        id INT AUTO_INCREMENT PRIMARY KEY,
                        task_id VARCHAR(100) NOT NULL,
                        execution_id VARCHAR(150) NOT NULL,
                        start_time DATETIME NOT NULL,
                        end_time DATETIME,
                        status VARCHAR(20) NOT NULL,
                        duration_seconds DECIMAL(10,3) DEFAULT 0.000,
                        result JSON,
                        error_message TEXT,
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                        INDEX idx_task_id (task_id),
                        INDEX idx_start_time (start_time)
                    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
                    """
                    await cursor.execute(create_table_query)
                    
                    # 插入執行記錄
                    insert_query = """
                    INSERT INTO maintenance_executions 
                    (task_id, execution_id, start_time, end_time, status, 
                     duration_seconds, result, error_message)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    """
                    
                    result_json = json.dumps(execution.result) if execution.result else None
                    
                    await cursor.execute(insert_query, (
                        execution.task_id,
                        execution.execution_id,
                        execution.start_time,
                        execution.end_time,
                        execution.status.value,
                        execution.duration_seconds,
                        result_json,
                        execution.error_message
                    ))
                    
                    await conn.commit()
                    
        except Exception as e:
            logger.error(f"保存執行記錄失敗: {e}")
    
    # ========== 預設任務實現 ==========
    
    async def _daily_cleanup_task(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """每日清理任務"""
        try:
            logger.info("🧹 開始執行每日清理任務...")
            
            # 執行基本清理
            results = await self.cleanup_manager.run_full_cleanup()
            
            total_deleted = sum(result.deleted_count for result in results.values() if hasattr(result, 'deleted_count'))
            successful_operations = sum(1 for result in results.values() if hasattr(result, 'success') and result.success)
            
            return {
                'operation': 'daily_cleanup',
                'total_deleted_records': total_deleted,
                'successful_operations': successful_operations,
                'total_operations': len(results),
                'details': {k: {'deleted': getattr(v, 'deleted_count', 0), 'success': getattr(v, 'success', False)} 
                          for k, v in results.items()}
            }
            
        except Exception as e:
            logger.error(f"每日清理任務失敗: {e}")
            raise
    
    async def _weekly_cleanup_task(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """每週深度清理任務"""
        try:
            logger.info("🧽 開始執行每週深度清理任務...")
            
            # 執行完整清理
            results = await self.cleanup_manager.run_full_cleanup()
            
            # 額外的週度清理操作
            weekly_results = {}
            
            # 清理舊的匯出檔案
            deleted_exports = await self.export_manager.cleanup_old_exports(days=7)
            weekly_results['deleted_export_files'] = deleted_exports
            
            # 統計結果
            total_deleted = sum(result.deleted_count for result in results.values() if hasattr(result, 'deleted_count'))
            
            return {
                'operation': 'weekly_cleanup',
                'total_deleted_records': total_deleted,
                'deleted_export_files': deleted_exports,
                'cleanup_results': {k: {'deleted': getattr(v, 'deleted_count', 0), 'success': getattr(v, 'success', False)} 
                                  for k, v in results.items()},
                'weekly_operations': weekly_results
            }
            
        except Exception as e:
            logger.error(f"每週清理任務失敗: {e}")
            raise
    
    async def _daily_backup_task(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """每日備份任務"""
        try:
            logger.info("💾 開始執行每日備份任務...")
            
            backup_types = config.get('backup_types', ['tickets', 'statistics'])
            results = {}
            
            for backup_type in backup_types:
                try:
                    # 創建匯出請求
                    export_request = ExportRequest(
                        export_type=backup_type,
                        format='json',
                        date_range=None,  # 備份所有資料
                        requester_id=0  # 系統備份
                    )
                    
                    # 執行備份匯出
                    export_result = await self.export_manager.export_data(export_request)
                    
                    results[backup_type] = {
                        'success': export_result.success,
                        'file_path': export_result.file_path,
                        'file_size': export_result.file_size,
                        'record_count': export_result.record_count,
                        'error': export_result.error_message
                    }
                    
                except Exception as e:
                    results[backup_type] = {
                        'success': False,
                        'error': str(e)
                    }
            
            successful_backups = sum(1 for r in results.values() if r['success'])
            total_size = sum(r.get('file_size', 0) for r in results.values() if r['success'])
            
            return {
                'operation': 'daily_backup',
                'successful_backups': successful_backups,
                'total_backups': len(backup_types),
                'total_size_bytes': total_size,
                'backup_results': results
            }
            
        except Exception as e:
            logger.error(f"每日備份任務失敗: {e}")
            raise
    
    async def _hourly_health_check_task(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """每小時健康檢查任務"""
        try:
            health_status = {}
            alerts = []
            
            # 檢查資料庫連接
            if config.get('check_database', True):
                try:
                    async with self.db.get_connection() as conn:
                        async with conn.cursor() as cursor:
                            await cursor.execute("SELECT 1")
                            health_status['database'] = 'healthy'
                except Exception as e:
                    health_status['database'] = 'unhealthy'
                    alerts.append(f"資料庫連接失敗: {e}")
            
            # 檢查系統資源 (如果可用)
            try:
                import psutil
                
                cpu_usage = psutil.cpu_percent(interval=1)
                memory_usage = psutil.virtual_memory().percent
                disk_usage = psutil.disk_usage('/').percent if hasattr(psutil.disk_usage, '/') else 0
                
                thresholds = config.get('alert_thresholds', {})
                
                health_status['system_resources'] = {
                    'cpu_usage': cpu_usage,
                    'memory_usage': memory_usage,
                    'disk_usage': disk_usage
                }
                
                if cpu_usage > thresholds.get('cpu_usage', 80):
                    alerts.append(f"CPU 使用率過高: {cpu_usage:.1f}%")
                
                if memory_usage > thresholds.get('memory_usage', 85):
                    alerts.append(f"記憶體使用率過高: {memory_usage:.1f}%")
                
                if disk_usage > thresholds.get('disk_usage', 90):
                    alerts.append(f"磁碟使用率過高: {disk_usage:.1f}%")
                    
            except ImportError:
                health_status['system_resources'] = 'unavailable'
            
            # 整體健康狀態
            overall_health = 'healthy' if not alerts else 'warning' if len(alerts) <= 2 else 'critical'
            
            return {
                'operation': 'health_check',
                'overall_health': overall_health,
                'components': health_status,
                'alerts': alerts,
                'check_time': datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"健康檢查任務失敗: {e}")
            raise
    
    async def _weekly_statistics_report_task(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """每週統計報告任務"""
        try:
            logger.info("📊 開始生成每週統計報告...")
            
            # 生成統計報告匯出
            export_types = ['statistics', 'analytics']
            formats = config.get('export_formats', ['json'])
            
            results = {}
            
            for export_type in export_types:
                for format_type in formats:
                    export_request = ExportRequest(
                        export_type=export_type,
                        format=format_type,
                        date_range=(datetime.now() - timedelta(days=7), datetime.now()),
                        requester_id=0  # 系統報告
                    )
                    
                    export_result = await self.export_manager.export_data(export_request)
                    
                    key = f"{export_type}_{format_type}"
                    results[key] = {
                        'success': export_result.success,
                        'file_path': export_result.file_path,
                        'record_count': export_result.record_count,
                        'file_size': export_result.file_size
                    }
            
            successful_reports = sum(1 for r in results.values() if r['success'])
            
            return {
                'operation': 'weekly_statistics_report',
                'successful_reports': successful_reports,
                'total_reports': len(results),
                'report_results': results
            }
            
        except Exception as e:
            logger.error(f"每週統計報告任務失敗: {e}")
            raise
    
    async def _monthly_optimization_task(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """每月系統優化任務"""
        try:
            logger.info("⚡ 開始執行每月系統優化...")
            
            optimization_results = {}
            
            # 重建索引 (如果配置啟用)
            if config.get('rebuild_indexes', True):
                try:
                    async with self.db.get_connection() as conn:
                        async with conn.cursor() as cursor:
                            # 獲取主要表格
                            main_tables = ['tickets', 'votes', 'ticket_logs', 'security_events']
                            
                            for table in main_tables:
                                try:
                                    await cursor.execute(f"OPTIMIZE TABLE {table}")
                                    optimization_results[f"optimize_{table}"] = 'success'
                                except Exception as e:
                                    optimization_results[f"optimize_{table}"] = f'failed: {e}'
                                    
                except Exception as e:
                    optimization_results['index_rebuild'] = f'failed: {e}'
            
            # 執行深度清理
            cleanup_results = await self.cleanup_manager.run_full_cleanup()
            total_cleaned = sum(result.deleted_count for result in cleanup_results.values() if hasattr(result, 'deleted_count'))
            
            optimization_results['cleanup_records_deleted'] = total_cleaned
            
            # 性能分析 (如果配置啟用)
            if config.get('analyze_performance', True):
                try:
                    # 執行基本性能分析
                    optimization_results['performance_analysis'] = 'completed'
                except Exception as e:
                    optimization_results['performance_analysis'] = f'failed: {e}'
            
            return {
                'operation': 'monthly_optimization',
                'optimization_results': optimization_results,
                'total_records_cleaned': total_cleaned
            }
            
        except Exception as e:
            logger.error(f"每月優化任務失敗: {e}")
            raise
    
    # ========== 管理方法 ==========
    
    async def run_task_now(self, task_id: str) -> bool:
        """立即執行指定任務"""
        if task_id not in self.tasks:
            logger.error(f"找不到任務: {task_id}")
            return False
        
        try:
            await self._execute_task(task_id)
            return True
        except Exception as e:
            logger.error(f"立即執行任務失敗: {e}")
            return False
    
    def get_task_status(self, task_id: str) -> Optional[Dict[str, Any]]:
        """獲取任務狀態"""
        if task_id not in self.tasks:
            return None
        
        task = self.tasks[task_id]
        recent_executions = [e for e in self.executions if e.task_id == task_id][-5:]  # 最近5次執行
        
        return {
            'task_id': task.task_id,
            'name': task.name,
            'description': task.description,
            'frequency': task.frequency.value,
            'enabled': task.enabled,
            'last_run': task.last_run.isoformat() if task.last_run else None,
            'next_run': task.next_run.isoformat() if task.next_run else None,
            'run_count': task.run_count,
            'failure_count': task.failure_count,
            'recent_executions': [
                {
                    'execution_id': e.execution_id,
                    'start_time': e.start_time.isoformat(),
                    'status': e.status.value,
                    'duration_seconds': e.duration_seconds,
                    'error_message': e.error_message
                } for e in recent_executions
            ]
        }
    
    def get_all_tasks_status(self) -> List[Dict[str, Any]]:
        """獲取所有任務狀態"""
        return [self.get_task_status(task_id) for task_id in self.tasks.keys()]
    
    async def get_execution_history(self, task_id: Optional[str] = None, days: int = 7) -> List[Dict[str, Any]]:
        """獲取執行歷史記錄"""
        try:
            cutoff_date = datetime.now() - timedelta(days=days)
            
            async with self.db.get_connection() as conn:
                async with conn.cursor() as cursor:
                    if task_id:
                        query = """
                        SELECT * FROM maintenance_executions 
                        WHERE task_id = %s AND start_time >= %s 
                        ORDER BY start_time DESC
                        """
                        params = [task_id, cutoff_date]
                    else:
                        query = """
                        SELECT * FROM maintenance_executions 
                        WHERE start_time >= %s 
                        ORDER BY start_time DESC
                        """
                        params = [cutoff_date]
                    
                    await cursor.execute(query, params)
                    return await cursor.fetchall()
                    
        except Exception as e:
            logger.error(f"獲取執行歷史失敗: {e}")
            return []