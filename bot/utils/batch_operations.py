# bot/utils/batch_operations.py - 票券系統批次操作工具

import discord
import asyncio
import csv
import json
import io
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Any, Tuple, Union
from dataclasses import dataclass
from enum import Enum

from bot.db.ticket_dao import TicketDAO
from bot.services.ticket_manager import (
    StatisticsService, NotificationService
)
from bot.utils.ticket_constants import (
    TicketConstants, get_priority_emoji, get_status_emoji,
    SUCCESS_MESSAGES, ERROR_MESSAGES
)
from bot.utils.debug import debug_log


class BatchOperationType(Enum):
    """批次操作類型"""
    CLOSE_INACTIVE = "close_inactive"
    CLOSE_OLD = "close_old"
    ARCHIVE_CLOSED = "archive_closed"
    EXPORT_CSV = "export_csv"
    EXPORT_JSON = "export_json"
    CLEANUP_CACHE = "cleanup_cache"
    UPDATE_STATISTICS = "update_statistics"
    SEND_REMINDERS = "send_reminders"
    BULK_ASSIGN = "bulk_assign"
    BULK_PRIORITY = "bulk_priority"
    BULK_TAG = "bulk_tag"


@dataclass
class BatchOperationResult:
    """批次操作結果"""
    success: bool
    processed_count: int
    error_count: int
    total_count: int
    errors: List[str]
    data: Optional[Any] = None
    execution_time: float = 0.0
    
    @property
    def success_rate(self) -> float:
        """成功率"""
        if self.total_count == 0:
            return 100.0
        return (self.processed_count / self.total_count) * 100
    
    def add_error(self, error: str):
        """添加錯誤"""
        self.errors.append(error)
        self.error_count += 1


@dataclass
class BatchOperationConfig:
    """批次操作配置"""
    operation_type: BatchOperationType
    guild_id: int
    parameters: Dict[str, Any]
    dry_run: bool = False
    batch_size: int = 50
    delay_between_batches: float = 1.0
    max_concurrent: int = 5
    notify_on_completion: bool = True
    log_channel_id: Optional[int] = None


class BatchOperationManager:
    """批次操作管理器"""
    
    def __init__(self):
        self.dao = TicketDAO()
        self.statistics_service = StatisticsService()
        self.notification_service = NotificationService()
        
        # 操作映射
        self.operation_handlers = {
            BatchOperationType.CLOSE_INACTIVE: self._close_inactive_tickets,
            BatchOperationType.CLOSE_OLD: self._close_old_tickets,
            BatchOperationType.ARCHIVE_CLOSED: self._archive_closed_tickets,
            BatchOperationType.EXPORT_CSV: self._export_tickets_csv,
            BatchOperationType.EXPORT_JSON: self._export_tickets_json,
            BatchOperationType.CLEANUP_CACHE: self._cleanup_cache,
            BatchOperationType.UPDATE_STATISTICS: self._update_statistics,
            BatchOperationType.SEND_REMINDERS: self._send_reminders,
            BatchOperationType.BULK_ASSIGN: self._bulk_assign_tickets,
            BatchOperationType.BULK_PRIORITY: self._bulk_update_priority,
            BatchOperationType.BULK_TAG: self._bulk_update_tags
        }
    
    async def execute_operation(self, config: BatchOperationConfig) -> BatchOperationResult:
        """執行批次操作"""
        start_time = datetime.now()
        
        try:
            debug_log(f"[BatchOperation] 開始執行 {config.operation_type.value} 操作")
            
            # 驗證配置
            validation_result = await self._validate_config(config)
            if not validation_result.success:
                return validation_result
            
            # 取得操作處理器
            handler = self.operation_handlers.get(config.operation_type)
            if not handler:
                return BatchOperationResult(
                    success=False,
                    processed_count=0,
                    error_count=1,
                    total_count=0,
                    errors=[f"不支援的操作類型：{config.operation_type.value}"]
                )
            
            # 執行操作
            result = await handler(config)
            
            # 計算執行時間
            end_time = datetime.now()
            result.execution_time = (end_time - start_time).total_seconds()
            
            # 發送完成通知
            if config.notify_on_completion and result.success:
                await self._send_completion_notification(config, result)
            
            debug_log(f"[BatchOperation] 操作完成 - 處理: {result.processed_count}, 錯誤: {result.error_count}")
            
            return result
            
        except Exception as e:
            debug_log(f"[BatchOperation] 執行操作錯誤：{e}")
            
            end_time = datetime.now()
            return BatchOperationResult(
                success=False,
                processed_count=0,
                error_count=1,
                total_count=0,
                errors=[f"執行錯誤：{str(e)}"],
                execution_time=(end_time - start_time).total_seconds()
            )
    
    async def _validate_config(self, config: BatchOperationConfig) -> BatchOperationResult:
        """驗證配置"""
        errors = []
        
        # 基本驗證
        if config.batch_size < 1 or config.batch_size > 1000:
            errors.append("批次大小必須在 1-1000 之間")
        
        if config.max_concurrent < 1 or config.max_concurrent > 20:
            errors.append("併發數必須在 1-20 之間")
        
        # 特定操作驗證
        if config.operation_type in [BatchOperationType.CLOSE_INACTIVE, BatchOperationType.CLOSE_OLD]:
            if 'hours_threshold' not in config.parameters:
                errors.append("缺少必要參數：hours_threshold")
            elif not isinstance(config.parameters['hours_threshold'], (int, float)):
                errors.append("hours_threshold 必須是數字")
        
        if config.operation_type in [BatchOperationType.BULK_ASSIGN]:
            if 'staff_id' not in config.parameters:
                errors.append("缺少必要參數：staff_id")
        
        if config.operation_type in [BatchOperationType.BULK_PRIORITY]:
            if 'priority' not in config.parameters:
                errors.append("缺少必要參數：priority")
            elif config.parameters['priority'] not in TicketConstants.PRIORITIES:
                errors.append("無效的優先級")
        
        if errors:
            return BatchOperationResult(
                success=False,
                processed_count=0,
                error_count=len(errors),
                total_count=0,
                errors=errors
            )
        
        return BatchOperationResult(
            success=True,
            processed_count=0,
            error_count=0,
            total_count=0,
            errors=[]
        )
    
    # ===== 票券關閉操作 =====
    
    async def _close_inactive_tickets(self, config: BatchOperationConfig) -> BatchOperationResult:
        """關閉無活動票券"""
        try:
            hours_threshold = config.parameters['hours_threshold']
            cutoff_time = datetime.now(timezone.utc) - timedelta(hours=hours_threshold)
            
            # 取得無活動票券
            async with self.dao.db_pool.acquire() as conn:
                async with conn.cursor(dictionary=True) as cursor:
                    await cursor.execute(
                        """
                        SELECT ticket_id, channel_id, discord_id, type, priority, created_at, last_activity
                        FROM tickets
                        WHERE guild_id = %s 
                        AND status = 'open'
                        AND last_activity < %s
                        ORDER BY last_activity ASC
                        """,
                        (config.guild_id, cutoff_time)
                    )
                    tickets_to_close = await cursor.fetchall()
            
            if not tickets_to_close:
                return BatchOperationResult(
                    success=True,
                    processed_count=0,
                    error_count=0,
                    total_count=0,
                    errors=[]
                )
            
            result = BatchOperationResult(
                success=True,
                processed_count=0,
                error_count=0,
                total_count=len(tickets_to_close),
                errors=[]
            )
            
            # 如果是演習模式，只返回統計
            if config.dry_run:
                result.data = {
                    'tickets_to_close': [
                        {
                            'ticket_id': t['ticket_id'],
                            'type': t['type'],
                            'inactive_hours': (datetime.now(timezone.utc) - t['last_activity']).total_seconds() / 3600
                        }
                        for t in tickets_to_close
                    ]
                }
                return result
            
            # 批次處理
            for i in range(0, len(tickets_to_close), config.batch_size):
                batch = tickets_to_close[i:i + config.batch_size]
                
                # 處理批次
                batch_tasks = []
                for ticket in batch:
                    task = self._close_single_ticket(
                        ticket, 
                        f"自動關閉：無活動超過 {hours_threshold} 小時"
                    )
                    batch_tasks.append(task)
                
                # 併發執行
                batch_results = await asyncio.gather(*batch_tasks, return_exceptions=True)
                
                # 處理結果
                for j, batch_result in enumerate(batch_results):
                    if isinstance(batch_result, Exception):
                        result.add_error(f"票券 #{batch[j]['ticket_id']:04d}: {str(batch_result)}")
                    elif batch_result:
                        result.processed_count += 1
                    else:
                        result.add_error(f"票券 #{batch[j]['ticket_id']:04d}: 關閉失敗")
                
                # 批次間延遲
                if i + config.batch_size < len(tickets_to_close):
                    await asyncio.sleep(config.delay_between_batches)
            
            return result
            
        except Exception as e:
            debug_log(f"[BatchOperation] 關閉無活動票券錯誤：{e}")
            return BatchOperationResult(
                success=False,
                processed_count=0,
                error_count=1,
                total_count=0,
                errors=[str(e)]
            )
    
    async def _close_old_tickets(self, config: BatchOperationConfig) -> BatchOperationResult:
        """關閉舊票券"""
        try:
            hours_threshold = config.parameters['hours_threshold']
            cutoff_time = datetime.now(timezone.utc) - timedelta(hours=hours_threshold)
            
            # 取得舊票券
            async with self.dao.db_pool.acquire() as conn:
                async with conn.cursor(dictionary=True) as cursor:
                    await cursor.execute(
                        """
                        SELECT ticket_id, channel_id, discord_id, type, priority, created_at
                        FROM tickets
                        WHERE guild_id = %s 
                        AND status = 'open'
                        AND created_at < %s
                        ORDER BY created_at ASC
                        """,
                        (config.guild_id, cutoff_time)
                    )
                    tickets_to_close = await cursor.fetchall()
            
            result = BatchOperationResult(
                success=True,
                processed_count=0,
                error_count=0,
                total_count=len(tickets_to_close),
                errors=[]
            )
            
            if config.dry_run:
                result.data = {
                    'tickets_to_close': [
                        {
                            'ticket_id': t['ticket_id'],
                            'type': t['type'],
                            'age_hours': (datetime.now(timezone.utc) - t['created_at']).total_seconds() / 3600
                        }
                        for t in tickets_to_close
                    ]
                }
                return result
            
            # 批次關閉
            for i in range(0, len(tickets_to_close), config.batch_size):
                batch = tickets_to_close[i:i + config.batch_size]
                
                batch_tasks = []
                for ticket in batch:
                    task = self._close_single_ticket(
                        ticket,
                        f"自動關閉：票券超過 {hours_threshold} 小時"
                    )
                    batch_tasks.append(task)
                
                batch_results = await asyncio.gather(*batch_tasks, return_exceptions=True)
                
                for j, batch_result in enumerate(batch_results):
                    if isinstance(batch_result, Exception):
                        result.add_error(f"票券 #{batch[j]['ticket_id']:04d}: {str(batch_result)}")
                    elif batch_result:
                        result.processed_count += 1
                    else:
                        result.add_error(f"票券 #{batch[j]['ticket_id']:04d}: 關閉失敗")
                
                if i + config.batch_size < len(tickets_to_close):
                    await asyncio.sleep(config.delay_between_batches)
            
            return result
            
        except Exception as e:
            debug_log(f"[BatchOperation] 關閉舊票券錯誤：{e}")
            return BatchOperationResult(
                success=False,
                processed_count=0,
                error_count=1,
                total_count=0,
                errors=[str(e)]
            )
    
    async def _close_single_ticket(self, ticket: Dict[str, Any], reason: str) -> bool:
        """關閉單一票券"""
        try:
            success = await self.dao.close_ticket(
                ticket['channel_id'],
                'system',
                reason
            )
            
            if success:
                debug_log(f"[BatchOperation] 已關閉票券 #{ticket['ticket_id']:04d}")
            
            return success
            
        except Exception as e:
            debug_log(f"[BatchOperation] 關閉票券 #{ticket['ticket_id']:04d} 錯誤：{e}")
            return False
    
    # ===== 歸檔操作 =====
    
    async def _archive_closed_tickets(self, config: BatchOperationConfig) -> BatchOperationResult:
        """歸檔已關閉票券"""
        try:
            days_threshold = config.parameters.get('days_threshold', 30)
            cutoff_time = datetime.now(timezone.utc) - timedelta(days=days_threshold)
            
            # 取得要歸檔的票券
            async with self.dao.db_pool.acquire() as conn:
                async with conn.cursor(dictionary=True) as cursor:
                    await cursor.execute(
                        """
                        SELECT ticket_id, type, closed_at
                        FROM tickets
                        WHERE guild_id = %s 
                        AND status = 'closed'
                        AND closed_at < %s
                        ORDER BY closed_at ASC
                        """,
                        (config.guild_id, cutoff_time)
                    )
                    tickets_to_archive = await cursor.fetchall()
            
            result = BatchOperationResult(
                success=True,
                processed_count=0,
                error_count=0,
                total_count=len(tickets_to_archive),
                errors=[]
            )
            
            if config.dry_run:
                result.data = {
                    'tickets_to_archive': [
                        {
                            'ticket_id': t['ticket_id'],
                            'type': t['type'],
                            'closed_days_ago': (datetime.now(timezone.utc) - t['closed_at']).days
                        }
                        for t in tickets_to_archive
                    ]
                }
                return result
            
            # 批次歸檔
            for i in range(0, len(tickets_to_archive), config.batch_size):
                batch = tickets_to_archive[i:i + config.batch_size]
                
                # 更新狀態為歸檔
                ticket_ids = [t['ticket_id'] for t in batch]
                
                try:
                    async with self.dao.db_pool.acquire() as conn:
                        async with conn.cursor() as cursor:
                            await cursor.execute(
                                f"UPDATE tickets SET status = 'archived' WHERE ticket_id IN ({','.join(['%s'] * len(ticket_ids))})",
                                ticket_ids
                            )
                            await conn.commit()
                            
                            result.processed_count += cursor.rowcount
                
                except Exception as e:
                    result.add_error(f"歸檔批次失敗：{str(e)}")
                
                if i + config.batch_size < len(tickets_to_archive):
                    await asyncio.sleep(config.delay_between_batches)
            
            return result
            
        except Exception as e:
            debug_log(f"[BatchOperation] 歸檔票券錯誤：{e}")
            return BatchOperationResult(
                success=False,
                processed_count=0,
                error_count=1,
                total_count=0,
                errors=[str(e)]
            )
    
    # ===== 匯出操作 =====
    
    async def _export_tickets_csv(self, config: BatchOperationConfig) -> BatchOperationResult:
        """匯出票券為 CSV"""
        try:
            # 取得匯出參數
            status_filter = config.parameters.get('status', 'all')
            start_date = config.parameters.get('start_date')
            end_date = config.parameters.get('end_date')
            
            # 建立查詢條件
            where_conditions = ["guild_id = %s"]
            params = [config.guild_id]
            
            if status_filter != 'all':
                where_conditions.append("status = %s")
                params.append(status_filter)
            
            if start_date:
                where_conditions.append("created_at >= %s")
                params.append(start_date)
            
            if end_date:
                where_conditions.append("created_at <= %s")
                params.append(end_date)
            
            where_clause = " AND ".join(where_conditions)
            
            # 取得票券資料
            async with self.dao.db_pool.acquire() as conn:
                async with conn.cursor(dictionary=True) as cursor:
                    await cursor.execute(
                        f"""
                        SELECT 
                            ticket_id, discord_id, username, type, priority, status,
                            created_at, closed_at, closed_by, close_reason,
                            assigned_to, rating, rating_feedback, tags,
                            last_activity
                        FROM tickets
                        WHERE {where_clause}
                        ORDER BY ticket_id DESC
                        """,
                        params
                    )
                    tickets = await cursor.fetchall()
            
            if not tickets:
                return BatchOperationResult(
                    success=True,
                    processed_count=0,
                    error_count=0,
                    total_count=0,
                    errors=["沒有符合條件的票券資料"]
                )
            
            # 建立 CSV 內容
            csv_buffer = io.StringIO()
            fieldnames = [
                '票券ID', '用戶ID', '用戶名', '類型', '優先級', '狀態',
                '建立時間', '關閉時間', '關閉者', '關閉原因',
                '指派給', '評分', '評分回饋', '標籤', '最後活動'
            ]
            
            writer = csv.DictWriter(csv_buffer, fieldnames=fieldnames)
            writer.writeheader()
            
            for ticket in tickets:
                # 處理標籤
                tags = ""
                if ticket.get('tags'):
                    try:
                        tag_list = json.loads(ticket['tags']) if isinstance(ticket['tags'], str) else ticket['tags']
                        tags = ', '.join(tag_list) if tag_list else ""
                    except:
                        tags = str(ticket['tags'])
                
                writer.writerow({
                    '票券ID': f"#{ticket['ticket_id']:04d}",
                    '用戶ID': ticket['discord_id'],
                    '用戶名': ticket['username'],
                    '類型': ticket['type'],
                    '優先級': ticket.get('priority', ''),
                    '狀態': ticket['status'],
                    '建立時間': ticket['created_at'].strftime('%Y-%m-%d %H:%M:%S') if ticket['created_at'] else '',
                    '關閉時間': ticket['closed_at'].strftime('%Y-%m-%d %H:%M:%S') if ticket.get('closed_at') else '',
                    '關閉者': ticket.get('closed_by', ''),
                    '關閉原因': ticket.get('close_reason', ''),
                    '指派給': ticket.get('assigned_to', ''),
                    '評分': ticket.get('rating', ''),
                    '評分回饋': ticket.get('rating_feedback', ''),
                    '標籤': tags,
                    '最後活動': ticket['last_activity'].strftime('%Y-%m-%d %H:%M:%S') if ticket.get('last_activity') else ''
                })
            
            csv_content = csv_buffer.getvalue()
            csv_buffer.close()
            
            result = BatchOperationResult(
                success=True,
                processed_count=len(tickets),
                error_count=0,
                total_count=len(tickets),
                errors=[],
                data={'csv_content': csv_content, 'filename': f'tickets_{config.guild_id}_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv'}
            )
            
            return result
            
        except Exception as e:
            debug_log(f"[BatchOperation] 匯出 CSV 錯誤：{e}")
            return BatchOperationResult(
                success=False,
                processed_count=0,
                error_count=1,
                total_count=0,
                errors=[str(e)]
            )
    
    async def _export_tickets_json(self, config: BatchOperationConfig) -> BatchOperationResult:
        """匯出票券為 JSON"""
        try:
            # 取得票券資料（使用與 CSV 相同的邏輯）
            tickets_data = await self.dao.export_tickets_data(
                config.guild_id,
                config.parameters.get('status'),
                config.parameters.get('start_date'),
                config.parameters.get('end_date')
            )
            
            if not tickets_data:
                return BatchOperationResult(
                    success=True,
                    processed_count=0,
                    error_count=0,
                    total_count=0,
                    errors=["沒有符合條件的票券資料"]
                )
            
            # 處理資料格式
            processed_data = []
            for ticket in tickets_data:
                # 處理日期時間格式
                ticket_dict = dict(ticket)
                for key, value in ticket_dict.items():
                    if isinstance(value, datetime):
                        ticket_dict[key] = value.isoformat()
                
                # 處理 JSON 欄位
                if ticket_dict.get('tags') and isinstance(ticket_dict['tags'], str):
                    try:
                        ticket_dict['tags'] = json.loads(ticket_dict['tags'])
                    except:
                        pass
                
                processed_data.append(ticket_dict)
            
            # 建立匯出資料
            export_data = {
                'export_info': {
                    'guild_id': config.guild_id,
                    'export_time': datetime.now(timezone.utc).isoformat(),
                    'total_tickets': len(processed_data),
                    'filters': config.parameters
                },
                'tickets': processed_data
            }
            
            json_content = json.dumps(export_data, ensure_ascii=False, indent=2)
            
            result = BatchOperationResult(
                success=True,
                processed_count=len(tickets_data),
                error_count=0,
                total_count=len(tickets_data),
                errors=[],
                data={
                    'json_content': json_content,
                    'filename': f'tickets_{config.guild_id}_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json'
                }
            )
            
            return result
            
        except Exception as e:
            debug_log(f"[BatchOperation] 匯出 JSON 錯誤：{e}")
            return BatchOperationResult(
                success=False,
                processed_count=0,
                error_count=1,
                total_count=0,
                errors=[str(e)]
            )
    
    # ===== 系統維護操作 =====
    
    async def _cleanup_cache(self, config: BatchOperationConfig) -> BatchOperationResult:
        """清理快取"""
        try:
            cleaned_count = 0
            
            # 清理統計快取
            async with self.dao.db_pool.acquire() as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute(
                        "DELETE FROM ticket_statistics_cache WHERE expires_at < NOW() OR guild_id = %s",
                        (config.guild_id,)
                    )
                    cleaned_count += cursor.rowcount
                    
                    # 清理舊的查看記錄
                    cutoff_date = datetime.now(timezone.utc) - timedelta(days=30)
                    await cursor.execute(
                        "DELETE FROM ticket_views WHERE viewed_at < %s",
                        (cutoff_date,)
                    )
                    cleaned_count += cursor.rowcount
                    
                    # 清理自動回覆日誌
                    cutoff_date = datetime.now(timezone.utc) - timedelta(days=7)
                    await cursor.execute(
                        "DELETE FROM auto_reply_logs WHERE created_at < %s",
                        (cutoff_date,)
                    )
                    cleaned_count += cursor.rowcount
                    
                    await conn.commit()
            
            return BatchOperationResult(
                success=True,
                processed_count=cleaned_count,
                error_count=0,
                total_count=cleaned_count,
                errors=[]
            )
            
        except Exception as e:
            debug_log(f"[BatchOperation] 清理快取錯誤：{e}")
            return BatchOperationResult(
                success=False,
                processed_count=0,
                error_count=1,
                total_count=0,
                errors=[str(e)]
            )
    
    async def _update_statistics(self, config: BatchOperationConfig) -> BatchOperationResult:
        """更新統計資料"""
        try:
            # 重新計算伺服器統計
            stats = await self.statistics_service.get_server_statistics(config.guild_id)
            
            # 重新計算 SLA 統計
            sla_stats = await self.dao.get_sla_statistics(config.guild_id)
            
            # 重新計算客服表現
            staff_stats = await self.statistics_service.get_staff_performance(config.guild_id)
            
            return BatchOperationResult(
                success=True,
                processed_count=1,
                error_count=0,
                total_count=1,
                errors=[],
                data={
                    'server_stats': stats,
                    'sla_stats': sla_stats,
                    'staff_stats': staff_stats
                }
            )
            
        except Exception as e:
            debug_log(f"[BatchOperation] 更新統計錯誤：{e}")
            return BatchOperationResult(
                success=False,
                processed_count=0,
                error_count=1,
                total_count=0,
                errors=[str(e)]
            )
    
    # ===== 通知操作 =====
    
    async def _send_reminders(self, config: BatchOperationConfig) -> BatchOperationResult:
        """發送提醒通知"""
        try:
            reminder_type = config.parameters.get('type', 'sla_overdue')
            
            if reminder_type == 'sla_overdue':
                return await self._send_sla_reminders(config)
            elif reminder_type == 'inactive_tickets':
                return await self._send_inactive_reminders(config)
            else:
                return BatchOperationResult(
                    success=False,
                    processed_count=0,
                    error_count=1,
                    total_count=0,
                    errors=[f"不支援的提醒類型：{reminder_type}"]
                )
                
        except Exception as e:
            debug_log(f"[BatchOperation] 發送提醒錯誤：{e}")
            return BatchOperationResult(
                success=False,
                processed_count=0,
                error_count=1,
                total_count=0,
                errors=[str(e)]
            )
    
    async def _send_sla_reminders(self, config: BatchOperationConfig) -> BatchOperationResult:
        """發送 SLA 超時提醒"""
        try:
            # 取得超時票券
            overdue_tickets = await self.dao.get_overdue_tickets()
            guild_tickets = [t for t in overdue_tickets if t['guild_id'] == config.guild_id]
            
            result = BatchOperationResult(
                success=True,
                processed_count=0,
                error_count=0,
                total_count=len(guild_tickets),
                errors=[]
            )
            
            if not guild_tickets:
                return result
            
            # 發送提醒
            for ticket in guild_tickets:
                try:
                    # 這裡需要 bot 實例來發送訊息，實際使用時需要傳入
                    # 暫時只記錄日誌
                    debug_log(f"[BatchOperation] 需要發送 SLA 提醒：票券 #{ticket['ticket_id']:04d}")
                    result.processed_count += 1
                    
                except Exception as e:
                    result.add_error(f"票券 #{ticket['ticket_id']:04d}: {str(e)}")
            
            return result
            
        except Exception as e:
            debug_log(f"[BatchOperation] 發送 SLA 提醒錯誤：{e}")
            return BatchOperationResult(
                success=False,
                processed_count=0,
                error_count=1,
                total_count=0,
                errors=[str(e)]
            )
    
    async def _send_inactive_reminders(self, config: BatchOperationConfig) -> BatchOperationResult:
        """發送無活動提醒"""
        try:
            hours_threshold = config.parameters.get('hours_threshold', 12)
            cutoff_time = datetime.now(timezone.utc) - timedelta(hours=hours_threshold)
            
            # 取得無活動票券
            async with self.dao.db_pool.acquire() as conn:
                async with conn.cursor(dictionary=True) as cursor:
                    await cursor.execute(
                        """
                        SELECT ticket_id, discord_id, type, last_activity
                        FROM tickets
                        WHERE guild_id = %s 
                        AND status = 'open'
                        AND last_activity < %s
                        AND last_activity > %s
                        """,
                        (config.guild_id, cutoff_time, cutoff_time - timedelta(hours=24))
                    )
                    inactive_tickets = await cursor.fetchall()
            
            result = BatchOperationResult(
                success=True,
                processed_count=0,
                error_count=0,
                total_count=len(inactive_tickets),
                errors=[]
            )
            
            # 發送提醒（需要 bot 實例）
            for ticket in inactive_tickets:
                try:
                    debug_log(f"[BatchOperation] 需要發送無活動提醒：票券 #{ticket['ticket_id']:04d}")
                    result.processed_count += 1
                    
                except Exception as e:
                    result.add_error(f"票券 #{ticket['ticket_id']:04d}: {str(e)}")
            
            return result
            
        except Exception as e:
            debug_log(f"[BatchOperation] 發送無活動提醒錯誤：{e}")
            return BatchOperationResult(
                success=False,
                processed_count=0,
                error_count=1,
                total_count=0,
                errors=[str(e)]
            )
    
    # ===== 批次更新操作 =====
    
    async def _bulk_assign_tickets(self, config: BatchOperationConfig) -> BatchOperationResult:
        """批次指派票券"""
        try:
            staff_id = config.parameters['staff_id']
            ticket_ids = config.parameters.get('ticket_ids', [])
            status_filter = config.parameters.get('status_filter', 'open')
            
            # 如果沒有指定票券 ID，取得符合條件的票券
            if not ticket_ids:
                async with self.dao.db_pool.acquire() as conn:
                    async with conn.cursor() as cursor:
                        await cursor.execute(
                            """
                            SELECT ticket_id FROM tickets
                            WHERE guild_id = %s AND status = %s AND assigned_to IS NULL
                            ORDER BY created_at ASC
                            LIMIT %s
                            """,
                            (config.guild_id, status_filter, config.parameters.get('limit', 50))
                        )
                        results = await cursor.fetchall()
                        ticket_ids = [r[0] for r in results]
            
            result = BatchOperationResult(
                success=True,
                processed_count=0,
                error_count=0,
                total_count=len(ticket_ids),
                errors=[]
            )
            
            if config.dry_run:
                result.data = {'tickets_to_assign': ticket_ids}
                return result
            
            # 批次指派
            for i in range(0, len(ticket_ids), config.batch_size):
                batch_ids = ticket_ids[i:i + config.batch_size]
                
                for ticket_id in batch_ids:
                    try:
                        success = await self.dao.assign_ticket(ticket_id, staff_id, 'batch_operation')
                        if success:
                            result.processed_count += 1
                        else:
                            result.add_error(f"票券 #{ticket_id:04d}: 指派失敗")
                            
                    except Exception as e:
                        result.add_error(f"票券 #{ticket_id:04d}: {str(e)}")
                
                if i + config.batch_size < len(ticket_ids):
                    await asyncio.sleep(config.delay_between_batches)
            
            return result
            
        except Exception as e:
            debug_log(f"[BatchOperation] 批次指派錯誤：{e}")
            return BatchOperationResult(
                success=False,
                processed_count=0,
                error_count=1,
                total_count=0,
                errors=[str(e)]
            )
    
    async def _bulk_update_priority(self, config: BatchOperationConfig) -> BatchOperationResult:
        """批次更新優先級"""
        try:
            priority = config.parameters['priority']
            ticket_ids = config.parameters.get('ticket_ids', [])
            current_priority = config.parameters.get('current_priority')
            
            # 如果沒有指定票券 ID，根據當前優先級篩選
            if not ticket_ids and current_priority:
                async with self.dao.db_pool.acquire() as conn:
                    async with conn.cursor() as cursor:
                        await cursor.execute(
                            """
                            SELECT ticket_id FROM tickets
                            WHERE guild_id = %s AND status = 'open' AND priority = %s
                            ORDER BY created_at ASC
                            LIMIT %s
                            """,
                            (config.guild_id, current_priority, config.parameters.get('limit', 100))
                        )
                        results = await cursor.fetchall()
                        ticket_ids = [r[0] for r in results]
            
            result = BatchOperationResult(
                success=True,
                processed_count=0,
                error_count=0,
                total_count=len(ticket_ids),
                errors=[]
            )
            
            if config.dry_run:
                result.data = {'tickets_to_update': ticket_ids, 'new_priority': priority}
                return result
            
            # 批次更新
            for i in range(0, len(ticket_ids), config.batch_size):
                batch_ids = ticket_ids[i:i + config.batch_size]
                
                try:
                    async with self.dao.db_pool.acquire() as conn:
                        async with conn.cursor() as cursor:
                            placeholders = ','.join(['%s'] * len(batch_ids))
                            await cursor.execute(
                                f"UPDATE tickets SET priority = %s WHERE ticket_id IN ({placeholders})",
                                [priority] + batch_ids
                            )
                            await conn.commit()
                            
                            result.processed_count += cursor.rowcount
                            
                            # 記錄操作日誌
                            for ticket_id in batch_ids:
                                await cursor.execute(
                                    """
                                    INSERT INTO ticket_logs (ticket_id, action, details, created_by, created_at)
                                    VALUES (%s, 'priority_change', %s, %s, NOW())
                                    """,
                                    (ticket_id, f"批次更新優先級為 {priority}", 'batch_operation')
                                )
                            await conn.commit()
                
                except Exception as e:
                    result.add_error(f"批次更新失敗：{str(e)}")
                
                if i + config.batch_size < len(ticket_ids):
                    await asyncio.sleep(config.delay_between_batches)
            
            return result
            
        except Exception as e:
            debug_log(f"[BatchOperation] 批次更新優先級錯誤：{e}")
            return BatchOperationResult(
                success=False,
                processed_count=0,
                error_count=1,
                total_count=0,
                errors=[str(e)]
            )
    
    async def _bulk_update_tags(self, config: BatchOperationConfig) -> BatchOperationResult:
        """批次更新標籤"""
        try:
            operation = config.parameters.get('operation', 'add')  # add, remove, replace
            tags = config.parameters['tags']
            ticket_ids = config.parameters.get('ticket_ids', [])
            
            if not ticket_ids:
                # 取得所有開啟的票券
                async with self.dao.db_pool.acquire() as conn:
                    async with conn.cursor() as cursor:
                        await cursor.execute(
                            "SELECT ticket_id FROM tickets WHERE guild_id = %s AND status = 'open'",
                            (config.guild_id,)
                        )
                        results = await cursor.fetchall()
                        ticket_ids = [r[0] for r in results]
            
            result = BatchOperationResult(
                success=True,
                processed_count=0,
                error_count=0,
                total_count=len(ticket_ids),
                errors=[]
            )
            
            if config.dry_run:
                result.data = {
                    'tickets_to_update': ticket_ids,
                    'operation': operation,
                    'tags': tags
                }
                return result
            
            # 批次更新標籤
            for i in range(0, len(ticket_ids), config.batch_size):
                batch_ids = ticket_ids[i:i + config.batch_size]
                
                for ticket_id in batch_ids:
                    try:
                        if operation == 'add':
                            success = await self.dao.add_tags_to_ticket(ticket_id, tags)
                        elif operation == 'replace':
                            # 先清空再添加
                            await self._replace_ticket_tags(ticket_id, tags)
                            success = True
                        else:  # remove
                            success = await self._remove_ticket_tags(ticket_id, tags)
                        
                        if success:
                            result.processed_count += 1
                        else:
                            result.add_error(f"票券 #{ticket_id:04d}: 標籤更新失敗")
                            
                    except Exception as e:
                        result.add_error(f"票券 #{ticket_id:04d}: {str(e)}")
                
                if i + config.batch_size < len(ticket_ids):
                    await asyncio.sleep(config.delay_between_batches)
            
            return result
            
        except Exception as e:
            debug_log(f"[BatchOperation] 批次更新標籤錯誤：{e}")
            return BatchOperationResult(
                success=False,
                processed_count=0,
                error_count=1,
                total_count=0,
                errors=[str(e)]
            )
    
    async def _replace_ticket_tags(self, ticket_id: int, new_tags: List[str]) -> bool:
        """替換票券標籤"""
        try:
            async with self.dao.db_pool.acquire() as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute(
                        "UPDATE tickets SET tags = %s WHERE ticket_id = %s",
                        (json.dumps(new_tags), ticket_id)
                    )
                    await conn.commit()
                    return cursor.rowcount > 0
                    
        except Exception as e:
            debug_log(f"[BatchOperation] 替換標籤錯誤：{e}")
            return False
    
    async def _remove_ticket_tags(self, ticket_id: int, tags_to_remove: List[str]) -> bool:
        """移除票券標籤"""
        try:
            # 取得當前標籤
            current_tags = await self.dao.get_ticket_tags(ticket_id)
            
            # 移除指定標籤
            new_tags = [tag for tag in current_tags if tag not in tags_to_remove]
            
            # 更新標籤
            async with self.dao.db_pool.acquire() as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute(
                        "UPDATE tickets SET tags = %s WHERE ticket_id = %s",
                        (json.dumps(new_tags), ticket_id)
                    )
                    await conn.commit()
                    return cursor.rowcount > 0
                    
        except Exception as e:
            debug_log(f"[BatchOperation] 移除標籤錯誤：{e}")
            return False
    
    # ===== 通知方法 =====
    
    async def _send_completion_notification(self, config: BatchOperationConfig, 
                                          result: BatchOperationResult):
        """發送完成通知"""
        try:
            if config.log_channel_id:
                # 建立完成報告嵌入
                embed = discord.Embed(
                    title="🔧 批次操作完成",
                    color=discord.Color.green() if result.success else discord.Color.red()
                )
                
                embed.add_field(
                    name="操作類型",
                    value=config.operation_type.value,
                    inline=True
                )
                
                embed.add_field(
                    name="執行結果",
                    value=f"✅ 成功：{result.processed_count}\n"
                          f"❌ 錯誤：{result.error_count}\n"
                          f"📊 總數：{result.total_count}",
                    inline=True
                )
                
                embed.add_field(
                    name="執行時間",
                    value=f"{result.execution_time:.2f} 秒",
                    inline=True
                )
                
                if result.errors:
                    error_text = "\n".join(result.errors[:5])
                    if len(result.errors) > 5:
                        error_text += f"\n... 還有 {len(result.errors) - 5} 個錯誤"
                    
                    embed.add_field(
                        name="錯誤詳情",
                        value=f"```{error_text}```",
                        inline=False
                    )
                
                embed.set_footer(
                    text=f"{'演習模式' if config.dry_run else '正式執行'} | {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
                )
                
                # 這裡需要 bot 實例來發送訊息
                debug_log(f"[BatchOperation] 需要發送完成通知到頻道 {config.log_channel_id}")
            
        except Exception as e:
            debug_log(f"[BatchOperation] 發送完成通知錯誤：{e}")


# ===== 工廠函數 =====

def create_batch_operation_manager() -> BatchOperationManager:
    """建立批次操作管理器"""
    return BatchOperationManager()


def create_batch_config(operation_type: BatchOperationType, guild_id: int, 
                       parameters: Dict[str, Any], **kwargs) -> BatchOperationConfig:
    """建立批次操作配置"""
    return BatchOperationConfig(
        operation_type=operation_type,
        guild_id=guild_id,
        parameters=parameters,
        **kwargs
    )


# ===== 預設配置模板 =====

class BatchConfigTemplates:
    """批次操作配置模板"""
    
    @staticmethod
    def close_inactive_tickets(guild_id: int, hours: int, dry_run: bool = False) -> BatchOperationConfig:
        """關閉無活動票券配置"""
        return BatchOperationConfig(
            operation_type=BatchOperationType.CLOSE_INACTIVE,
            guild_id=guild_id,
            parameters={'hours_threshold': hours},
            dry_run=dry_run,
            batch_size=20,
            delay_between_batches=2.0
        )
    
    @staticmethod
    def archive_old_tickets(guild_id: int, days: int, dry_run: bool = False) -> BatchOperationConfig:
        """歸檔舊票券配置"""
        return BatchOperationConfig(
            operation_type=BatchOperationType.ARCHIVE_CLOSED,
            guild_id=guild_id,
            parameters={'days_threshold': days},
            dry_run=dry_run,
            batch_size=50,
            delay_between_batches=1.0
        )
    
    @staticmethod
    def export_tickets_csv(guild_id: int, status: str = 'all', 
                          start_date: datetime = None, end_date: datetime = None) -> BatchOperationConfig:
        """匯出票券 CSV 配置"""
        parameters = {'status': status}
        if start_date:
            parameters['start_date'] = start_date
        if end_date:
            parameters['end_date'] = end_date
            
        return BatchOperationConfig(
            operation_type=BatchOperationType.EXPORT_CSV,
            guild_id=guild_id,
            parameters=parameters
        )
    
    @staticmethod
    def bulk_assign_tickets(guild_id: int, staff_id: int, limit: int = 10) -> BatchOperationConfig:
        """批次指派票券配置"""
        return BatchOperationConfig(
            operation_type=BatchOperationType.BULK_ASSIGN,
            guild_id=guild_id,
            parameters={
                'staff_id': staff_id,
                'limit': limit,
                'status_filter': 'open'
            },
            batch_size=10,
            delay_between_batches=1.0
        )
    
    @staticmethod
    def system_maintenance(guild_id: int) -> BatchOperationConfig:
        """系統維護配置"""
        return BatchOperationConfig(
            operation_type=BatchOperationType.CLEANUP_CACHE,
            guild_id=guild_id,
            parameters={},
            notify_on_completion=True
        )


# ===== 匯出 =====

__all__ = [
    'BatchOperationType',
    'BatchOperationResult',
    'BatchOperationConfig',
    'BatchOperationManager',
    'BatchConfigTemplates',
    'create_batch_operation_manager',
    'create_batch_config'
]