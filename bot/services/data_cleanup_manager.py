# bot/services/data_cleanup_manager.py
"""
資料清理管理器
負責定期清理過期資料、日誌和優化資料庫性能
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
import aiomysql

from bot.db.pool import db_pool
from shared.logger import logger


@dataclass
class CleanupResult:
    """清理結果資料類別"""
    table_name: str
    records_before: int
    records_after: int
    deleted_count: int
    cleanup_time: datetime
    success: bool
    error_message: Optional[str] = None
    
    @property
    def deletion_percentage(self) -> float:
        """計算刪除百分比"""
        if self.records_before == 0:
            return 0.0
        return (self.deleted_count / self.records_before) * 100


@dataclass 
class CleanupSummary:
    """清理摘要結果 - 用於視圖顯示"""
    success: bool
    cleaned_items: int = 0
    space_freed_mb: float = 0.0
    duration_seconds: float = 0.0
    error: Optional[str] = None
    details: List[str] = None
    
    def __post_init__(self):
        if self.details is None:
            self.details = []


@dataclass
class CleanupConfig:
    """清理配置"""
    # 日誌清理設定
    log_retention_days: int = 30
    error_log_retention_days: int = 90
    
    # 票券系統清理設定
    closed_ticket_retention_days: int = 365
    draft_ticket_retention_days: int = 30
    
    # 統計資料清理設定
    daily_stats_retention_days: int = 90
    hourly_stats_retention_days: int = 7
    
    # 用戶活動清理設定
    inactive_user_threshold_days: int = 180
    temporary_data_retention_hours: int = 24
    
    # 安全事件清理設定
    security_event_retention_days: int = 180
    audit_log_retention_days: int = 365


class DataCleanupManager:
    """資料清理管理器"""
    
    def __init__(self, config: Optional[CleanupConfig] = None):
        self.config = config or CleanupConfig()
        self.db = db_pool
        self.cleanup_history: List[CleanupResult] = []
        
    async def run_full_cleanup(self) -> CleanupSummary:
        """執行完整的系統清理"""
        start_time = datetime.now()
        logger.info("🧹 開始執行完整系統清理...")
        results = {}
        total_cleaned = 0
        details = []
        
        try:
            # 清理系統日誌
            results['system_logs'] = await self._cleanup_system_logs()
            
            # 清理票券相關資料
            results['ticket_logs'] = await self._cleanup_ticket_logs()
            results['closed_tickets'] = await self._cleanup_old_tickets()
            
            # 清理統計資料
            results['statistics_cache'] = await self._cleanup_statistics_cache()
            
            # 清理安全事件
            results['security_events'] = await self._cleanup_security_events()
            
            # 清理臨時資料
            results['temporary_data'] = await self._cleanup_temporary_data()
            
            # 清理孤立資料
            results['orphaned_data'] = await self._cleanup_orphaned_data()
            
            # 優化資料庫
            results['database_optimization'] = await self._optimize_database()
            
            # 計算摘要統計
            success_count = 0
            for key, result in results.items():
                if result.success:
                    success_count += 1
                    total_cleaned += result.deleted_count
                    details.append(f"清理{key}: {result.deleted_count}條記錄")
                else:
                    details.append(f"清理{key}: 失敗 - {result.error_message}")
            
            # 記錄清理結果
            await self._log_cleanup_results(results)
            
            duration = (datetime.now() - start_time).total_seconds()
            
            # 估算釋放空間 (簡單估算，每條記錄約1KB)
            space_freed_mb = total_cleaned * 0.001
            
            logger.info("✅ 完整系統清理完成")
            
            return CleanupSummary(
                success=success_count > 0,
                cleaned_items=total_cleaned,
                space_freed_mb=space_freed_mb,
                duration_seconds=duration,
                details=details[:10]  # 最多顯示10個詳細項目
            )
            
        except Exception as e:
            logger.error(f"❌ 系統清理過程中發生錯誤: {e}", exc_info=True)
            duration = (datetime.now() - start_time).total_seconds()
            return CleanupSummary(
                success=False,
                duration_seconds=duration,
                error=str(e)
            )
    
    async def run_basic_cleanup(self) -> CleanupSummary:
        """執行基礎清理（快速清理常見的過期資料）"""
        start_time = datetime.now()
        logger.info("🧹 開始執行基礎清理...")
        total_cleaned = 0
        details = []
        
        try:
            # 只執行基礎清理操作
            basic_results = {}
            
            # 清理系統日誌 (僅30天前)
            basic_results['system_logs'] = await self._cleanup_system_logs()
            
            # 清理票券日誌
            basic_results['ticket_logs'] = await self._cleanup_ticket_logs()
            
            # 清理統計快取
            basic_results['statistics_cache'] = await self._cleanup_statistics_cache()
            
            # 計算結果
            success_count = 0
            for key, result in basic_results.items():
                if result.success:
                    success_count += 1
                    total_cleaned += result.deleted_count
                    details.append(f"清理{key}: {result.deleted_count}條記錄")
                else:
                    details.append(f"清理{key}: 失敗 - {result.error_message}")
            
            duration = (datetime.now() - start_time).total_seconds()
            space_freed_mb = total_cleaned * 0.001
            
            logger.info("✅ 基礎清理完成")
            
            return CleanupSummary(
                success=success_count > 0,
                cleaned_items=total_cleaned,
                space_freed_mb=space_freed_mb,
                duration_seconds=duration,
                details=details
            )
            
        except Exception as e:
            logger.error(f"❌ 基礎清理過程中發生錯誤: {e}", exc_info=True)
            duration = (datetime.now() - start_time).total_seconds()
            return CleanupSummary(
                success=False,
                duration_seconds=duration,
                error=str(e)
            )
    
    async def _cleanup_system_logs(self) -> CleanupResult:
        """清理系統日誌 - 檢查表是否存在"""
        table_name = "system_logs"
        cutoff_date = datetime.now() - timedelta(days=self.config.log_retention_days)
        
        try:
            async with self.db.connection() as conn:
                async with conn.cursor(aiomysql.DictCursor) as cursor:
                    # 檢查表是否存在
                    check_table_query = """
                    SELECT COUNT(*) as count
                    FROM information_schema.tables 
                    WHERE table_schema = DATABASE() 
                    AND table_name = %s
                    """
                    await cursor.execute(check_table_query, (table_name,))
                    result = await cursor.fetchone()
                    
                    if not result or result['count'] == 0:
                        logger.warning(f"⚠️ 表 {table_name} 不存在，跳過清理")
                        return CleanupResult(
                            table_name=table_name,
                            records_before=0,
                            records_after=0,
                            deleted_count=0,
                            cleanup_time=datetime.now(),
                            success=True
                        )
                    
                    # 檢查是否有 created_at 欄位
                    check_column_query = """
                    SELECT COUNT(*) as count
                    FROM information_schema.columns 
                    WHERE table_schema = DATABASE() 
                    AND table_name = %s
                    AND column_name = 'created_at'
                    """
                    await cursor.execute(check_column_query, (table_name,))
                    result = await cursor.fetchone()
                    
                    if not result or result['count'] == 0:
                        logger.warning(f"⚠️ 表 {table_name} 沒有 created_at 欄位，跳過清理")
                        return CleanupResult(
                            table_name=table_name,
                            records_before=0,
                            records_after=0,
                            deleted_count=0,
                            cleanup_time=datetime.now(),
                            success=True
                        )
                    
                    # 計算清理前記錄數
                    count_query = f"SELECT COUNT(*) as count FROM {table_name} WHERE created_at < %s"
                    await cursor.execute(count_query, (cutoff_date,))
                    result = await cursor.fetchone()
                    records_to_delete = result['count'] if result else 0
                    
                    # 獲取總記錄數
                    await cursor.execute(f"SELECT COUNT(*) as count FROM {table_name}")
                    result = await cursor.fetchone()
                    total_records = result['count'] if result else 0
                    
                    # 執行清理
                    if records_to_delete > 0:
                        delete_query = f"DELETE FROM {table_name} WHERE created_at < %s"
                        await cursor.execute(delete_query, (cutoff_date,))
                        await conn.commit()
                    
                    # 計算清理後記錄數
                    records_after = total_records - records_to_delete
                    
                    logger.info(f"🗑️ 系統日誌清理: 刪除 {records_to_delete} 條記錄")
                    
                    return CleanupResult(
                        table_name=table_name,
                        records_before=total_records,
                        records_after=records_after,
                        deleted_count=records_to_delete,
                        cleanup_time=datetime.now(),
                        success=True
                    )
                    
        except Exception as e:
            logger.error(f"❌ 清理系統日誌失敗: {e}")
            return CleanupResult(
                table_name=table_name,
                records_before=0,
                records_after=0,
                deleted_count=0,
                cleanup_time=datetime.now(),
                success=False,
                error_message=str(e)
            )
    
    async def _generic_cleanup_by_date(self, table_name: str, date_column: str, retention_days: int) -> CleanupResult:
        """通用的基於日期的清理方法"""
        cutoff_date = datetime.now() - timedelta(days=retention_days)
        
        try:
            async with self.db.connection() as conn:
                async with conn.cursor(aiomysql.DictCursor) as cursor:
                    # 檢查表是否存在
                    check_table_query = """
                    SELECT COUNT(*) as count
                    FROM information_schema.tables 
                    WHERE table_schema = DATABASE() 
                    AND table_name = %s
                    """
                    await cursor.execute(check_table_query, (table_name,))
                    result = await cursor.fetchone()
                    
                    if not result or result['count'] == 0:
                        logger.warning(f"⚠️ 表 {table_name} 不存在，跳過清理")
                        return CleanupResult(
                            table_name=table_name,
                            records_before=0,
                            records_after=0,
                            deleted_count=0,
                            cleanup_time=datetime.now(),
                            success=True
                        )
                    
                    # 檢查日期欄位是否存在
                    check_column_query = """
                    SELECT COUNT(*) as count
                    FROM information_schema.columns 
                    WHERE table_schema = DATABASE() 
                    AND table_name = %s
                    AND column_name = %s
                    """
                    await cursor.execute(check_column_query, (table_name, date_column))
                    result = await cursor.fetchone()
                    
                    if not result or result['count'] == 0:
                        logger.warning(f"⚠️ 表 {table_name} 沒有 {date_column} 欄位，跳過清理")
                        return CleanupResult(
                            table_name=table_name,
                            records_before=0,
                            records_after=0,
                            deleted_count=0,
                            cleanup_time=datetime.now(),
                            success=True
                        )
                    
                    # 獲取總記錄數
                    await cursor.execute(f"SELECT COUNT(*) as count FROM {table_name}")
                    result = await cursor.fetchone()
                    total_records = result['count'] if result else 0
                    
                    # 計算要刪除的記錄數
                    count_query = f"SELECT COUNT(*) as count FROM {table_name} WHERE {date_column} < %s"
                    await cursor.execute(count_query, (cutoff_date,))
                    result = await cursor.fetchone()
                    records_to_delete = result['count'] if result else 0
                    
                    # 執行清理
                    if records_to_delete > 0:
                        delete_query = f"DELETE FROM {table_name} WHERE {date_column} < %s"
                        await cursor.execute(delete_query, (cutoff_date,))
                        await conn.commit()
                    
                    records_after = total_records - records_to_delete
                    
                    logger.info(f"🗑️ {table_name} 清理: 刪除 {records_to_delete} 條記錄")
                    
                    return CleanupResult(
                        table_name=table_name,
                        records_before=total_records,
                        records_after=records_after,
                        deleted_count=records_to_delete,
                        cleanup_time=datetime.now(),
                        success=True
                    )
                    
        except Exception as e:
            logger.error(f"❌ 清理表 {table_name} 失敗: {e}")
            return CleanupResult(
                table_name=table_name,
                records_before=0,
                records_after=0,
                deleted_count=0,
                cleanup_time=datetime.now(),
                success=False,
                error_message=str(e)
            )
    
    async def _cleanup_ticket_logs(self) -> CleanupResult:
        """清理票券日誌"""
        return await self._generic_cleanup_by_date("ticket_logs", "created_at", self.config.log_retention_days)
    
    async def _cleanup_old_tickets(self) -> CleanupResult:
        """清理舊的已關閉票券"""
        table_name = "tickets"
        cutoff_date = datetime.now() - timedelta(days=self.config.closed_ticket_retention_days)
        
        try:
            async with self.db.connection() as conn:
                async with conn.cursor(aiomysql.DictCursor) as cursor:
                    # 檢查表是否存在
                    check_table_query = """
                    SELECT COUNT(*) as count
                    FROM information_schema.tables 
                    WHERE table_schema = DATABASE() 
                    AND table_name = %s
                    """
                    await cursor.execute(check_table_query, (table_name,))
                    result = await cursor.fetchone()
                    
                    if not result or result['count'] == 0:
                        logger.warning(f"⚠️ 表 {table_name} 不存在，跳過清理")
                        return CleanupResult(
                            table_name=table_name,
                            records_before=0,
                            records_after=0,
                            deleted_count=0,
                            cleanup_time=datetime.now(),
                            success=True
                        )
                    
                    # 獲取總記錄數
                    await cursor.execute(f"SELECT COUNT(*) as count FROM {table_name}")
                    result = await cursor.fetchone()
                    total_records = result['count'] if result else 0
                    
                    # 計算要刪除的已關閉票券數 (狀態為 closed, resolved, archived)
                    count_query = f"""
                    SELECT COUNT(*) as count FROM {table_name} 
                    WHERE status IN ('closed', 'resolved', 'archived') 
                    AND closed_at IS NOT NULL 
                    AND closed_at < %s
                    """
                    await cursor.execute(count_query, (cutoff_date,))
                    result = await cursor.fetchone()
                    records_to_delete = result['count'] if result else 0
                    
                    # 如果沒有 closed_at 欄位，改用 created_at
                    if records_to_delete == 0:
                        count_query = f"""
                        SELECT COUNT(*) as count FROM {table_name} 
                        WHERE status IN ('closed', 'resolved', 'archived') 
                        AND created_at < %s
                        """
                        await cursor.execute(count_query, (cutoff_date,))
                        result = await cursor.fetchone()
                        records_to_delete = result['count'] if result else 0
                    
                    # 執行清理
                    if records_to_delete > 0:
                        # 先嘗試用 closed_at
                        delete_query = f"""
                        DELETE FROM {table_name} 
                        WHERE status IN ('closed', 'resolved', 'archived') 
                        AND closed_at IS NOT NULL 
                        AND closed_at < %s
                        """
                        await cursor.execute(delete_query, (cutoff_date,))
                        deleted_with_closed_at = cursor.rowcount
                        
                        # 如果還沒刪除完，用 created_at
                        if deleted_with_closed_at == 0:
                            delete_query = f"""
                            DELETE FROM {table_name} 
                            WHERE status IN ('closed', 'resolved', 'archived') 
                            AND created_at < %s
                            """
                            await cursor.execute(delete_query, (cutoff_date,))
                        
                        await conn.commit()
                    
                    records_after = total_records - records_to_delete
                    
                    logger.info(f"🗑️ 已關閉票券清理: 刪除 {records_to_delete} 條記錄")
                    
                    return CleanupResult(
                        table_name=table_name,
                        records_before=total_records,
                        records_after=records_after,
                        deleted_count=records_to_delete,
                        cleanup_time=datetime.now(),
                        success=True
                    )
                    
        except Exception as e:
            logger.error(f"❌ 清理已關閉票券失敗: {e}")
            return CleanupResult(
                table_name=table_name,
                records_before=0,
                records_after=0,
                deleted_count=0,
                cleanup_time=datetime.now(),
                success=False,
                error_message=str(e)
            )
    
    async def _cleanup_statistics_cache(self) -> CleanupResult:
        """清理統計快取資料"""
        return await self._generic_cleanup_by_date("ticket_statistics_cache", "created_at", self.config.daily_stats_retention_days)
    
    async def _cleanup_security_events(self) -> CleanupResult:
        """清理安全事件記錄"""
        return await self._generic_cleanup_by_date("security_events", "created_at", self.config.log_retention_days)
    
    async def _cleanup_temporary_data(self) -> CleanupResult:
        """清理臨時資料 - 智能檢查每個表的結構"""
        table_name = "temporary_data"
        cutoff_date = datetime.now() - timedelta(days=1)  # 清理1天前的臨時資料
        
        try:
            # 清理各種臨時資料表
            total_deleted = 0
            total_before = 0
            
            temp_tables = [
                "user_sessions",
                "temp_uploads", 
                "cache_data",
                "rate_limit_cache",
                "temp_files",
                "session_cache"
            ]
            
            async with self.db.connection() as conn:
                async with conn.cursor(aiomysql.DictCursor) as cursor:
                    for table in temp_tables:
                        try:
                            # 檢查表是否存在
                            check_table_query = """
                            SELECT COUNT(*) as count
                            FROM information_schema.tables 
                            WHERE table_schema = DATABASE() 
                            AND table_name = %s
                            """
                            await cursor.execute(check_table_query, (table,))
                            result = await cursor.fetchone()
                            
                            if not result or result['count'] == 0:
                                logger.debug(f"表 {table} 不存在，跳過清理")
                                continue
                            
                            # 檢查可用的日期欄位
                            date_column = await self._find_date_column(cursor, table)
                            if not date_column:
                                # 如果沒有日期欄位，嘗試清理所有資料（臨時表通常可以全部清理）
                                logger.info(f"表 {table} 沒有日期欄位，執行全表清理")
                                
                                # 獲取總記錄數
                                await cursor.execute(f"SELECT COUNT(*) as count FROM {table}")
                                result = await cursor.fetchone()
                                table_total = result['count'] if result else 0
                                
                                if table_total > 0:
                                    # 清理全表
                                    await cursor.execute(f"DELETE FROM {table}")
                                    total_deleted += table_total
                                    total_before += table_total
                                    logger.info(f"🗑️ 全表清理 {table}: 刪除 {table_total} 條記錄")
                                continue
                            
                            # 獲取總記錄數
                            await cursor.execute(f"SELECT COUNT(*) as count FROM {table}")
                            result = await cursor.fetchone()
                            table_total = result['count'] if result else 0
                            
                            # 計算要刪除的記錄數
                            count_query = f"SELECT COUNT(*) as count FROM {table} WHERE {date_column} < %s"
                            await cursor.execute(count_query, (cutoff_date,))
                            result = await cursor.fetchone()
                            records_to_delete = result['count'] if result else 0
                            
                            # 執行清理
                            if records_to_delete > 0:
                                delete_query = f"DELETE FROM {table} WHERE {date_column} < %s"
                                await cursor.execute(delete_query, (cutoff_date,))
                                logger.info(f"🗑️ 按日期清理 {table}: 刪除 {records_to_delete} 條記錄")
                                
                            total_deleted += records_to_delete
                            total_before += table_total
                            
                        except Exception as table_error:
                            logger.warning(f"清理臨時表 {table} 時出現問題: {table_error}")
                            continue
                    
                    await conn.commit()
                    
                    logger.info(f"🗂️ 臨時資料清理: 刪除 {total_deleted} 條記錄")
                    
                    return CleanupResult(
                        table_name="temporary_data",
                        records_before=total_before,
                        records_after=total_before - total_deleted,
                        deleted_count=total_deleted,
                        cleanup_time=datetime.now(),
                        success=True
                    )
                    
        except Exception as e:
            logger.error(f"❌ 清理臨時資料失敗: {e}")
            return CleanupResult(
                table_name="temporary_data",
                records_before=0,
                records_after=0,
                deleted_count=0,
                cleanup_time=datetime.now(),
                success=False,
                error_message=str(e)
            )
    
    async def _find_date_column(self, cursor, table_name: str) -> Optional[str]:
        """查找表中可用的日期欄位"""
        date_columns = [
            'created_at',
            'updated_at', 
            'timestamp',
            'date_created',
            'last_activity',
            'expires_at',
            'session_start',
            'login_time'
        ]
        
        for column in date_columns:
            try:
                check_column_query = """
                SELECT COUNT(*) as count
                FROM information_schema.columns 
                WHERE table_schema = DATABASE() 
                AND table_name = %s
                AND column_name = %s
                """
                await cursor.execute(check_column_query, (table_name, column))
                result = await cursor.fetchone()
                
                if result and result['count'] > 0:
                    return column
                    
            except Exception:
                continue
        
        return None
    
    async def _cleanup_orphaned_data(self) -> CleanupResult:
        """清理孤立資料"""
        table_name = "orphaned_data"
        
        try:
            total_deleted = 0
            
            async with self.db.connection() as conn:
                async with conn.cursor(aiomysql.DictCursor) as cursor:
                    # 清理孤立的票券標籤映射
                    orphaned_tags_query = """
                    DELETE ttm FROM ticket_tag_mappings ttm
                    LEFT JOIN tickets t ON ttm.ticket_id = t.id
                    WHERE t.id IS NULL
                    """
                    await cursor.execute(orphaned_tags_query)
                    deleted_tags = cursor.rowcount
                    total_deleted += deleted_tags
                    
                    # 清理孤立的指派記錄
                    orphaned_assignments_query = """
                    DELETE ah FROM assignment_history ah
                    LEFT JOIN tickets t ON ah.ticket_id = t.id
                    WHERE t.id IS NULL
                    """
                    await cursor.execute(orphaned_assignments_query)
                    deleted_assignments = cursor.rowcount
                    total_deleted += deleted_assignments
                    
                    # 清理孤立的投票回應
                    orphaned_votes_query = """
                    DELETE vr FROM vote_responses vr
                    LEFT JOIN votes v ON vr.vote_id = v.id
                    WHERE v.id IS NULL
                    """
                    await cursor.execute(orphaned_votes_query)
                    deleted_votes = cursor.rowcount
                    total_deleted += deleted_votes
                    
                    await conn.commit()
                    
                    logger.info(f"🧹 孤立資料清理: 刪除 {total_deleted} 條記錄")
                    
                    return CleanupResult(
                        table_name="orphaned_data",
                        records_before=total_deleted,  # 概估
                        records_after=0,
                        deleted_count=total_deleted,
                        cleanup_time=datetime.now(),
                        success=True
                    )
                    
        except Exception as e:
            logger.error(f"❌ 清理孤立資料失敗: {e}")
            return CleanupResult(
                table_name="orphaned_data",
                records_before=0,
                records_after=0,
                deleted_count=0,
                cleanup_time=datetime.now(),
                success=False,
                error_message=str(e)
            )
    
    async def _optimize_database(self) -> CleanupResult:
        """優化資料庫"""
        table_name = "database_optimization"
        
        try:
            optimized_tables = 0
            
            # 獲取所有表名
            main_tables = [
                "tickets", "ticket_logs", "votes", "vote_responses",
                "ticket_statistics_cache", "security_events", "user_sessions"
            ]
            
            async with self.db.connection() as conn:
                async with conn.cursor(aiomysql.DictCursor) as cursor:
                    for table in main_tables:
                        try:
                            # 檢查表是否存在
                            check_query = f"SHOW TABLES LIKE '{table}'"
                            await cursor.execute(check_query)
                            if not await cursor.fetchone():
                                continue
                            
                            # 優化表
                            optimize_query = f"OPTIMIZE TABLE {table}"
                            await cursor.execute(optimize_query)
                            optimized_tables += 1
                            
                        except Exception as table_error:
                            logger.warning(f"優化表 {table} 時出現問題: {table_error}")
                            continue
                    
                    # 分析表統計
                    for table in main_tables:
                        try:
                            analyze_query = f"ANALYZE TABLE {table}"
                            await cursor.execute(analyze_query)
                        except Exception:
                            continue
                    
                    logger.info(f"⚡ 資料庫優化: 優化了 {optimized_tables} 個表")
                    
                    return CleanupResult(
                        table_name="database_optimization",
                        records_before=len(main_tables),
                        records_after=optimized_tables,
                        deleted_count=0,
                        cleanup_time=datetime.now(),
                        success=True
                    )
                    
        except Exception as e:
            logger.error(f"❌ 資料庫優化失敗: {e}")
            return CleanupResult(
                table_name="database_optimization",
                records_before=0,
                records_after=0,
                deleted_count=0,
                cleanup_time=datetime.now(),
                success=False,
                error_message=str(e)
            )
    
    async def _log_cleanup_results(self, results: Dict[str, CleanupResult]):
        """記錄清理結果"""
        try:
            total_deleted = sum(result.deleted_count for result in results.values())
            successful_cleanups = sum(1 for result in results.values() if result.success)
            total_cleanups = len(results)
            
            logger.info("📋 清理結果摘要:")
            logger.info(f"  總共清理: {total_deleted} 條記錄")
            logger.info(f"  成功操作: {successful_cleanups}/{total_cleanups}")
            
            for operation, result in results.items():
                if result.success:
                    percentage = result.deletion_percentage
                    logger.info(f"  ✅ {operation}: 刪除 {result.deleted_count} 條 ({percentage:.1f}%)")
                else:
                    logger.error(f"  ❌ {operation}: 失敗 - {result.error_message}")
            
            # 將結果保存到資料庫
            await self._save_cleanup_log(results)
            
        except Exception as e:
            logger.error(f"記錄清理結果失敗: {e}")
    
    async def _save_cleanup_log(self, results: Dict[str, CleanupResult]):
        """保存清理日誌到資料庫"""
        try:
            async with self.db.connection() as conn:
                async with conn.cursor(aiomysql.DictCursor) as cursor:
                    # 創建清理日誌表（如果不存在）
                    create_table_query = """
                    CREATE TABLE IF NOT EXISTS cleanup_logs (
                        id INT AUTO_INCREMENT PRIMARY KEY,
                        operation_name VARCHAR(100) NOT NULL,
                        table_name VARCHAR(100) NOT NULL,
                        records_before INT DEFAULT 0,
                        records_after INT DEFAULT 0,
                        deleted_count INT DEFAULT 0,
                        deletion_percentage DECIMAL(5,2) DEFAULT 0.00,
                        success BOOLEAN DEFAULT TRUE,
                        error_message TEXT,
                        cleanup_time DATETIME DEFAULT CURRENT_TIMESTAMP,
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
                    """
                    await cursor.execute(create_table_query)
                    
                    # 插入清理記錄
                    for operation, result in results.items():
                        insert_query = """
                        INSERT INTO cleanup_logs 
                        (operation_name, table_name, records_before, records_after, 
                         deleted_count, deletion_percentage, success, error_message, cleanup_time)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                        """
                        await cursor.execute(insert_query, (
                            operation,
                            result.table_name,
                            result.records_before,
                            result.records_after,
                            result.deleted_count,
                            result.deletion_percentage,
                            result.success,
                            result.error_message,
                            result.cleanup_time
                        ))
                    
                    await conn.commit()
                    logger.info("✅ 清理日誌已保存")
                    
        except Exception as e:
            logger.error(f"保存清理日誌失敗: {e}")
    
    async def get_cleanup_history(self, days: int = 30) -> List[Dict]:
        """獲取清理歷史記錄"""
        try:
            cutoff_date = datetime.now() - timedelta(days=days)
            
            async with self.db.connection() as conn:
                async with conn.cursor(aiomysql.DictCursor) as cursor:
                    query = """
                    SELECT * FROM cleanup_logs 
                    WHERE cleanup_time >= %s 
                    ORDER BY cleanup_time DESC
                    """
                    await cursor.execute(query, (cutoff_date,))
                    return await cursor.fetchall()
                    
        except Exception as e:
            logger.error(f"獲取清理歷史失敗: {e}")
            return []
    
    async def get_cleanup_statistics(self) -> Dict:
        """獲取清理統計資訊"""
        try:
            async with self.db.connection() as conn:
                async with conn.cursor(aiomysql.DictCursor) as cursor:
                    # 總清理統計
                    stats_query = """
                    SELECT 
                        COUNT(*) as total_operations,
                        SUM(deleted_count) as total_deleted,
                        AVG(deletion_percentage) as avg_deletion_rate,
                        COUNT(CASE WHEN success = 1 THEN 1 END) as successful_operations,
                        COUNT(CASE WHEN success = 0 THEN 1 END) as failed_operations
                    FROM cleanup_logs
                    WHERE cleanup_time >= DATE_SUB(NOW(), INTERVAL 30 DAY)
                    """
                    await cursor.execute(stats_query)
                    stats = await cursor.fetchone()
                    
                    # 最近清理統計
                    recent_query = """
                    SELECT operation_name, COUNT(*) as count, SUM(deleted_count) as total_deleted
                    FROM cleanup_logs 
                    WHERE cleanup_time >= DATE_SUB(NOW(), INTERVAL 7 DAY)
                    GROUP BY operation_name
                    ORDER BY total_deleted DESC
                    """
                    await cursor.execute(recent_query)
                    recent_stats = await cursor.fetchall()
                    
                    return {
                        'overall': stats or {},
                        'recent_operations': recent_stats or [],
                        'generated_at': datetime.now().isoformat()
                    }
                    
        except Exception as e:
            logger.error(f"獲取清理統計失敗: {e}")
            return {'error': str(e)}