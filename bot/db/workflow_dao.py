# bot/db/workflow_dao.py - 工作流程資料存取層 v1.6.0
"""
工作流程資料存取層
處理工作流程定義、執行記錄等資料庫操作
"""

import json
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timezone, timedelta
from bot.db.base_dao import BaseDAO
from shared.logger import logger


class WorkflowDAO(BaseDAO):
    """工作流程資料存取物件"""
    
    def __init__(self):
        super().__init__()
    
    async def _initialize(self):
        """初始化資料庫表格"""
        try:
            await self._create_workflow_tables()
            logger.info("✅ 工作流程資料庫表格初始化完成")
        except Exception as e:
            logger.error(f"❌ 工作流程資料庫初始化失敗: {e}")
            raise
    
    async def _create_workflow_tables(self):
        """創建工作流程相關表格"""
        async with self.db.connection() as conn:
            async with conn.cursor() as cursor:
                
                # 工作流程定義表
                await cursor.execute("""
                    CREATE TABLE IF NOT EXISTS workflows (
                        id VARCHAR(36) PRIMARY KEY,
                        name VARCHAR(255) NOT NULL,
                        description TEXT,
                        guild_id BIGINT NOT NULL,
                        status ENUM('draft', 'active', 'paused', 'disabled', 'archived') DEFAULT 'draft',
                        trigger_type VARCHAR(50) NOT NULL,
                        trigger_conditions JSON,
                        trigger_parameters JSON,
                        actions JSON NOT NULL,
                        created_by BIGINT DEFAULT 0,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                        execution_count INT DEFAULT 0,
                        last_executed TIMESTAMP NULL,
                        tags JSON,
                        version INT DEFAULT 1,
                        
                        INDEX idx_guild_id (guild_id),
                        INDEX idx_status (status),
                        INDEX idx_trigger_type (trigger_type),
                        INDEX idx_created_by (created_by),
                        INDEX idx_last_executed (last_executed)
                    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
                """)
                
                # 工作流程執行記錄表
                await cursor.execute("""
                    CREATE TABLE IF NOT EXISTS workflow_executions (
                        id VARCHAR(36) PRIMARY KEY,
                        workflow_id VARCHAR(36) NOT NULL,
                        trigger_data JSON,
                        start_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        end_time TIMESTAMP NULL,
                        status ENUM('running', 'completed', 'failed', 'cancelled') DEFAULT 'running',
                        current_action VARCHAR(36),
                        results JSON,
                        errors JSON,
                        
                        INDEX idx_workflow_id (workflow_id),
                        INDEX idx_status (status),
                        INDEX idx_start_time (start_time),
                        INDEX idx_end_time (end_time),
                        
                        FOREIGN KEY (workflow_id) REFERENCES workflows(id) ON DELETE CASCADE
                    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
                """)
                
                # 工作流程變更歷史表
                await cursor.execute("""
                    CREATE TABLE IF NOT EXISTS workflow_history (
                        id INT AUTO_INCREMENT PRIMARY KEY,
                        workflow_id VARCHAR(36) NOT NULL,
                        version INT NOT NULL,
                        changed_by BIGINT NOT NULL,
                        change_type ENUM('created', 'updated', 'activated', 'deactivated', 'deleted') NOT NULL,
                        changes JSON,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        
                        INDEX idx_workflow_id (workflow_id),
                        INDEX idx_changed_by (changed_by),
                        INDEX idx_change_type (change_type),
                        INDEX idx_created_at (created_at),
                        
                        FOREIGN KEY (workflow_id) REFERENCES workflows(id) ON DELETE CASCADE
                    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
                """)
                
                # 工作流程統計表
                await cursor.execute("""
                    CREATE TABLE IF NOT EXISTS workflow_statistics (
                        id INT AUTO_INCREMENT PRIMARY KEY,
                        workflow_id VARCHAR(36) NOT NULL,
                        date DATE NOT NULL,
                        executions_count INT DEFAULT 0,
                        success_count INT DEFAULT 0,
                        failure_count INT DEFAULT 0,
                        avg_execution_time DECIMAL(10,2) DEFAULT 0.00,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                        
                        UNIQUE KEY unique_workflow_date (workflow_id, date),
                        INDEX idx_workflow_id (workflow_id),
                        INDEX idx_date (date),
                        
                        FOREIGN KEY (workflow_id) REFERENCES workflows(id) ON DELETE CASCADE
                    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
                """)
                
                await conn.commit()
    
    # ========== 工作流程CRUD操作 ==========
    
    async def create_workflow(self, workflow_data: Dict[str, Any]) -> str:
        """創建工作流程"""
        try:
            async with self.db.connection() as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute("""
                        INSERT INTO workflows (
                            id, name, description, guild_id, status, trigger_type,
                            trigger_conditions, trigger_parameters, actions,
                            created_by, tags, version
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """, (
                        workflow_data['id'],
                        workflow_data['name'],
                        workflow_data.get('description', ''),
                        workflow_data['guild_id'],
                        workflow_data.get('status', 'draft'),
                        workflow_data['trigger_type'],
                        json.dumps(workflow_data.get('trigger_conditions', [])),
                        json.dumps(workflow_data.get('trigger_parameters', {})),
                        json.dumps(workflow_data['actions']),
                        workflow_data.get('created_by', 0),
                        json.dumps(workflow_data.get('tags', [])),
                        workflow_data.get('version', 1)
                    ))
                    
                    await conn.commit()
                    
                    # 記錄變更歷史
                    await self._log_workflow_history(
                        workflow_data['id'], 
                        workflow_data.get('version', 1),
                        workflow_data.get('created_by', 0),
                        'created',
                        workflow_data
                    )
                    
                    return workflow_data['id']
                    
        except Exception as e:
            logger.error(f"創建工作流程失敗: {e}")
            raise
    
    async def update_workflow(self, workflow_id: str, updates: Dict[str, Any], updated_by: int) -> bool:
        """更新工作流程"""
        try:
            async with self.db.connection() as conn:
                async with conn.cursor() as cursor:
                    # 獲取當前版本
                    await cursor.execute("SELECT version FROM workflows WHERE id = %s", (workflow_id,))
                    result = await cursor.fetchone()
                    if not result:
                        return False
                    
                    current_version = result[0]
                    new_version = current_version + 1
                    
                    # 構建更新SQL
                    set_clauses = []
                    params = []
                    
                    if 'name' in updates:
                        set_clauses.append("name = %s")
                        params.append(updates['name'])
                    
                    if 'description' in updates:
                        set_clauses.append("description = %s")
                        params.append(updates['description'])
                    
                    if 'status' in updates:
                        set_clauses.append("status = %s")
                        params.append(updates['status'])
                    
                    if 'trigger_type' in updates:
                        set_clauses.append("trigger_type = %s")
                        params.append(updates['trigger_type'])
                    
                    if 'trigger_conditions' in updates:
                        set_clauses.append("trigger_conditions = %s")
                        params.append(json.dumps(updates['trigger_conditions']))
                    
                    if 'trigger_parameters' in updates:
                        set_clauses.append("trigger_parameters = %s")
                        params.append(json.dumps(updates['trigger_parameters']))
                    
                    if 'actions' in updates:
                        set_clauses.append("actions = %s")
                        params.append(json.dumps(updates['actions']))
                    
                    if 'tags' in updates:
                        set_clauses.append("tags = %s")
                        params.append(json.dumps(updates['tags']))
                    
                    # 總是更新版本號
                    set_clauses.append("version = %s")
                    params.append(new_version)
                    
                    if not set_clauses:
                        return True
                    
                    params.append(workflow_id)
                    
                    await cursor.execute(
                        f"UPDATE workflows SET {', '.join(set_clauses)}, updated_at = CURRENT_TIMESTAMP WHERE id = %s",
                        params
                    )
                    
                    await conn.commit()
                    
                    # 記錄變更歷史
                    await self._log_workflow_history(
                        workflow_id, new_version, updated_by, 'updated', updates
                    )
                    
                    return cursor.rowcount > 0
                    
        except Exception as e:
            logger.error(f"更新工作流程失敗: {e}")
            return False
    
    async def get_workflow(self, workflow_id: str) -> Optional[Dict[str, Any]]:
        """獲取單個工作流程"""
        try:
            async with self.db.connection() as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute("""
                        SELECT id, name, description, guild_id, status, trigger_type,
                               trigger_conditions, trigger_parameters, actions,
                               created_by, created_at, updated_at, execution_count,
                               last_executed, tags, version
                        FROM workflows WHERE id = %s
                    """, (workflow_id,))
                    
                    result = await cursor.fetchone()
                    if not result:
                        return None
                    
                    return {
                        'id': result[0],
                        'name': result[1],
                        'description': result[2],
                        'guild_id': result[3],
                        'status': result[4],
                        'trigger_type': result[5],
                        'trigger_conditions': json.loads(result[6]) if result[6] else [],
                        'trigger_parameters': json.loads(result[7]) if result[7] else {},
                        'actions': json.loads(result[8]) if result[8] else [],
                        'created_by': result[9],
                        'created_at': result[10],
                        'updated_at': result[11],
                        'execution_count': result[12],
                        'last_executed': result[13],
                        'tags': json.loads(result[14]) if result[14] else [],
                        'version': result[15]
                    }
                    
        except Exception as e:
            logger.error(f"獲取工作流程失敗: {e}")
            return None
    
    async def get_workflows(self, guild_id: int = None, status: str = None, 
                           created_by: int = None, page: int = 1, page_size: int = 20) -> Tuple[List[Dict[str, Any]], int]:
        """獲取工作流程列表"""
        try:
            conditions = []
            params = []
            
            if guild_id:
                conditions.append("guild_id = %s")
                params.append(guild_id)
            
            if status:
                conditions.append("status = %s")
                params.append(status)
            
            if created_by:
                conditions.append("created_by = %s")
                params.append(created_by)
            
            where_clause = "WHERE " + " AND ".join(conditions) if conditions else ""
            
            async with self.db.connection() as conn:
                async with conn.cursor() as cursor:
                    # 獲取總數
                    count_sql = f"SELECT COUNT(*) FROM workflows {where_clause}"
                    await cursor.execute(count_sql, params)
                    total_count = (await cursor.fetchone())[0]
                    
                    # 獲取分頁數據
                    offset = (page - 1) * page_size
                    params.extend([page_size, offset])
                    
                    data_sql = f"""
                        SELECT id, name, description, guild_id, status, trigger_type,
                               created_by, created_at, updated_at, execution_count,
                               last_executed, tags, version
                        FROM workflows {where_clause}
                        ORDER BY updated_at DESC
                        LIMIT %s OFFSET %s
                    """
                    
                    await cursor.execute(data_sql, params)
                    results = await cursor.fetchall()
                    
                    workflows = []
                    for result in results:
                        workflows.append({
                            'id': result[0],
                            'name': result[1],
                            'description': result[2],
                            'guild_id': result[3],
                            'status': result[4],
                            'trigger_type': result[5],
                            'created_by': result[6],
                            'created_at': result[7],
                            'updated_at': result[8],
                            'execution_count': result[9],
                            'last_executed': result[10],
                            'tags': json.loads(result[11]) if result[11] else [],
                            'version': result[12]
                        })
                    
                    return workflows, total_count
                    
        except Exception as e:
            logger.error(f"獲取工作流程列表失敗: {e}")
            return [], 0
    
    async def delete_workflow(self, workflow_id: str, deleted_by: int) -> bool:
        """刪除工作流程"""
        try:
            async with self.db.connection() as conn:
                async with conn.cursor() as cursor:
                    # 記錄刪除歷史
                    await self._log_workflow_history(
                        workflow_id, 0, deleted_by, 'deleted', {}
                    )
                    
                    # 刪除工作流程（級聯刪除相關記錄）
                    await cursor.execute("DELETE FROM workflows WHERE id = %s", (workflow_id,))
                    await conn.commit()
                    
                    return cursor.rowcount > 0
                    
        except Exception as e:
            logger.error(f"刪除工作流程失敗: {e}")
            return False
    
    # ========== 執行記錄操作 ==========
    
    async def create_execution(self, execution_data: Dict[str, Any]) -> str:
        """創建執行記錄"""
        try:
            async with self.db.connection() as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute("""
                        INSERT INTO workflow_executions (
                            id, workflow_id, trigger_data, start_time, status
                        ) VALUES (%s, %s, %s, %s, %s)
                    """, (
                        execution_data['id'],
                        execution_data['workflow_id'],
                        json.dumps(execution_data.get('trigger_data', {})),
                        execution_data.get('start_time', datetime.now(timezone.utc)),
                        execution_data.get('status', 'running')
                    ))
                    
                    await conn.commit()
                    return execution_data['id']
                    
        except Exception as e:
            logger.error(f"創建執行記錄失敗: {e}")
            raise
    
    async def update_execution(self, execution_id: str, updates: Dict[str, Any]) -> bool:
        """更新執行記錄"""
        try:
            async with self.db.connection() as conn:
                async with conn.cursor() as cursor:
                    set_clauses = []
                    params = []
                    
                    if 'status' in updates:
                        set_clauses.append("status = %s")
                        params.append(updates['status'])
                    
                    if 'current_action' in updates:
                        set_clauses.append("current_action = %s")
                        params.append(updates['current_action'])
                    
                    if 'results' in updates:
                        set_clauses.append("results = %s")
                        params.append(json.dumps(updates['results']))
                    
                    if 'errors' in updates:
                        set_clauses.append("errors = %s")
                        params.append(json.dumps(updates['errors']))
                    
                    if 'end_time' in updates:
                        set_clauses.append("end_time = %s")
                        params.append(updates['end_time'])
                    
                    if not set_clauses:
                        return True
                    
                    params.append(execution_id)
                    
                    await cursor.execute(
                        f"UPDATE workflow_executions SET {', '.join(set_clauses)} WHERE id = %s",
                        params
                    )
                    
                    await conn.commit()
                    return cursor.rowcount > 0
                    
        except Exception as e:
            logger.error(f"更新執行記錄失敗: {e}")
            return False
    
    async def get_execution(self, execution_id: str) -> Optional[Dict[str, Any]]:
        """獲取執行記錄"""
        try:
            async with self.db.connection() as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute("""
                        SELECT id, workflow_id, trigger_data, start_time, end_time,
                               status, current_action, results, errors
                        FROM workflow_executions WHERE id = %s
                    """, (execution_id,))
                    
                    result = await cursor.fetchone()
                    if not result:
                        return None
                    
                    return {
                        'id': result[0],
                        'workflow_id': result[1],
                        'trigger_data': json.loads(result[2]) if result[2] else {},
                        'start_time': result[3],
                        'end_time': result[4],
                        'status': result[5],
                        'current_action': result[6],
                        'results': json.loads(result[7]) if result[7] else {},
                        'errors': json.loads(result[8]) if result[8] else []
                    }
                    
        except Exception as e:
            logger.error(f"獲取執行記錄失敗: {e}")
            return None
    
    async def get_executions(self, workflow_id: str = None, status: str = None,
                           days: int = 30, page: int = 1, page_size: int = 50) -> Tuple[List[Dict[str, Any]], int]:
        """獲取執行記錄列表"""
        try:
            conditions = []
            params = []
            
            if workflow_id:
                conditions.append("workflow_id = %s")
                params.append(workflow_id)
            
            if status:
                conditions.append("status = %s")
                params.append(status)
            
            if days > 0:
                start_date = datetime.now(timezone.utc) - timedelta(days=days)
                conditions.append("start_time >= %s")
                params.append(start_date)
            
            where_clause = "WHERE " + " AND ".join(conditions) if conditions else ""
            
            async with self.db.connection() as conn:
                async with conn.cursor() as cursor:
                    # 獲取總數
                    count_sql = f"SELECT COUNT(*) FROM workflow_executions {where_clause}"
                    await cursor.execute(count_sql, params)
                    total_count = (await cursor.fetchone())[0]
                    
                    # 獲取分頁數據
                    offset = (page - 1) * page_size
                    params.extend([page_size, offset])
                    
                    data_sql = f"""
                        SELECT e.id, e.workflow_id, w.name as workflow_name, e.start_time, 
                               e.end_time, e.status, e.current_action
                        FROM workflow_executions e
                        LEFT JOIN workflows w ON e.workflow_id = w.id
                        {where_clause}
                        ORDER BY e.start_time DESC
                        LIMIT %s OFFSET %s
                    """
                    
                    await cursor.execute(data_sql, params)
                    results = await cursor.fetchall()
                    
                    executions = []
                    for result in results:
                        execution_time = None
                        if result[4]:  # end_time
                            execution_time = (result[4] - result[3]).total_seconds()
                        
                        executions.append({
                            'id': result[0],
                            'workflow_id': result[1],
                            'workflow_name': result[2],
                            'start_time': result[3],
                            'end_time': result[4],
                            'status': result[5],
                            'current_action': result[6],
                            'execution_time': execution_time
                        })
                    
                    return executions, total_count
                    
        except Exception as e:
            logger.error(f"獲取執行記錄列表失敗: {e}")
            return [], 0
    
    # ========== 統計操作 ==========
    
    async def update_workflow_statistics(self, workflow_id: str, execution_time: float, success: bool):
        """更新工作流程統計"""
        try:
            today = datetime.now(timezone.utc).date()
            
            async with self.db.connection() as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute("""
                        INSERT INTO workflow_statistics 
                        (workflow_id, date, executions_count, success_count, failure_count, avg_execution_time)
                        VALUES (%s, %s, 1, %s, %s, %s)
                        ON DUPLICATE KEY UPDATE
                        executions_count = executions_count + 1,
                        success_count = success_count + %s,
                        failure_count = failure_count + %s,
                        avg_execution_time = (avg_execution_time * (executions_count - 1) + %s) / executions_count
                    """, (
                        workflow_id, today,
                        1 if success else 0,
                        0 if success else 1,
                        execution_time,
                        1 if success else 0,
                        0 if success else 1,
                        execution_time
                    ))
                    
                    # 更新工作流程執行計數
                    await cursor.execute("""
                        UPDATE workflows 
                        SET execution_count = execution_count + 1, last_executed = CURRENT_TIMESTAMP
                        WHERE id = %s
                    """, (workflow_id,))
                    
                    await conn.commit()
                    
        except Exception as e:
            logger.error(f"更新工作流程統計失敗: {e}")
    
    async def get_workflow_statistics(self, workflow_id: str, days: int = 30) -> Dict[str, Any]:
        """獲取工作流程統計"""
        try:
            end_date = datetime.now(timezone.utc).date()
            start_date = end_date - timedelta(days=days)
            
            async with self.db.connection() as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute("""
                        SELECT 
                            SUM(executions_count) as total_executions,
                            SUM(success_count) as total_success,
                            SUM(failure_count) as total_failures,
                            AVG(avg_execution_time) as avg_execution_time,
                            DATE(date) as stat_date
                        FROM workflow_statistics
                        WHERE workflow_id = %s AND date BETWEEN %s AND %s
                        GROUP BY DATE(date)
                        ORDER BY date DESC
                    """, (workflow_id, start_date, end_date))
                    
                    daily_stats = await cursor.fetchall()
                    
                    # 計算總體統計
                    await cursor.execute("""
                        SELECT 
                            SUM(executions_count) as total_executions,
                            SUM(success_count) as total_success,
                            SUM(failure_count) as total_failures,
                            AVG(avg_execution_time) as avg_execution_time
                        FROM workflow_statistics
                        WHERE workflow_id = %s AND date BETWEEN %s AND %s
                    """, (workflow_id, start_date, end_date))
                    
                    overall_stats = await cursor.fetchone()
                    
                    return {
                        'workflow_id': workflow_id,
                        'period_days': days,
                        'total_executions': overall_stats[0] or 0,
                        'success_count': overall_stats[1] or 0,
                        'failure_count': overall_stats[2] or 0,
                        'success_rate': (overall_stats[1] / overall_stats[0] * 100) if overall_stats[0] else 0,
                        'avg_execution_time': float(overall_stats[3]) if overall_stats[3] else 0.0,
                        'daily_stats': [
                            {
                                'date': str(stat[4]),
                                'executions': stat[0],
                                'success': stat[1],
                                'failures': stat[2],
                                'avg_time': float(stat[3]) if stat[3] else 0.0
                            } for stat in daily_stats
                        ]
                    }
                    
        except Exception as e:
            logger.error(f"獲取工作流程統計失敗: {e}")
            return {}
    
    async def get_guild_workflow_statistics(self, guild_id: int, days: int = 30) -> Dict[str, Any]:
        """獲取伺服器工作流程統計"""
        try:
            end_date = datetime.now(timezone.utc).date()
            start_date = end_date - timedelta(days=days)
            
            async with self.db.connection() as conn:
                async with conn.cursor() as cursor:
                    # 獲取伺服器內所有工作流程的統計
                    await cursor.execute("""
                        SELECT 
                            COUNT(DISTINCT w.id) as total_workflows,
                            COUNT(DISTINCT CASE WHEN w.status = 'active' THEN w.id END) as active_workflows,
                            SUM(COALESCE(s.executions_count, 0)) as total_executions,
                            SUM(COALESCE(s.success_count, 0)) as total_success,
                            SUM(COALESCE(s.failure_count, 0)) as total_failures,
                            AVG(COALESCE(s.avg_execution_time, 0)) as avg_execution_time
                        FROM workflows w
                        LEFT JOIN workflow_statistics s ON w.id = s.workflow_id 
                                                        AND s.date BETWEEN %s AND %s
                        WHERE w.guild_id = %s
                    """, (start_date, end_date, guild_id))
                    
                    overall_stats = await cursor.fetchone()
                    
                    # 獲取觸發類型分佈
                    await cursor.execute("""
                        SELECT trigger_type, COUNT(*) as count
                        FROM workflows
                        WHERE guild_id = %s
                        GROUP BY trigger_type
                        ORDER BY count DESC
                    """, (guild_id,))
                    
                    trigger_distribution = await cursor.fetchall()
                    
                    # 獲取最活躍的工作流程
                    await cursor.execute("""
                        SELECT w.id, w.name, w.execution_count, w.last_executed
                        FROM workflows w
                        WHERE w.guild_id = %s AND w.execution_count > 0
                        ORDER BY w.execution_count DESC
                        LIMIT 10
                    """, (guild_id,))
                    
                    top_workflows = await cursor.fetchall()
                    
                    return {
                        'guild_id': guild_id,
                        'period_days': days,
                        'total_workflows': overall_stats[0] or 0,
                        'active_workflows': overall_stats[1] or 0,
                        'total_executions': overall_stats[2] or 0,
                        'success_count': overall_stats[3] or 0,
                        'failure_count': overall_stats[4] or 0,
                        'success_rate': (overall_stats[3] / overall_stats[2] * 100) if overall_stats[2] else 0,
                        'avg_execution_time': float(overall_stats[5]) if overall_stats[5] else 0.0,
                        'trigger_distribution': [
                            {'type': trigger[0], 'count': trigger[1]} 
                            for trigger in trigger_distribution
                        ],
                        'top_workflows': [
                            {
                                'id': workflow[0],
                                'name': workflow[1],
                                'execution_count': workflow[2],
                                'last_executed': workflow[3]
                            } for workflow in top_workflows
                        ]
                    }
                    
        except Exception as e:
            logger.error(f"獲取伺服器工作流程統計失敗: {e}")
            return {}
    
    # ========== 歷史記錄 ==========
    
    async def _log_workflow_history(self, workflow_id: str, version: int, changed_by: int, 
                                   change_type: str, changes: Dict[str, Any]):
        """記錄工作流程變更歷史"""
        try:
            async with self.db.connection() as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute("""
                        INSERT INTO workflow_history (
                            workflow_id, version, changed_by, change_type, changes
                        ) VALUES (%s, %s, %s, %s, %s)
                    """, (
                        workflow_id, version, changed_by, change_type, json.dumps(changes)
                    ))
                    
                    await conn.commit()
                    
        except Exception as e:
            logger.error(f"記錄工作流程歷史失敗: {e}")
    
    async def get_workflow_history(self, workflow_id: str, page: int = 1, page_size: int = 20) -> Tuple[List[Dict[str, Any]], int]:
        """獲取工作流程變更歷史"""
        try:
            async with self.db.connection() as conn:
                async with conn.cursor() as cursor:
                    # 獲取總數
                    await cursor.execute(
                        "SELECT COUNT(*) FROM workflow_history WHERE workflow_id = %s",
                        (workflow_id,)
                    )
                    total_count = (await cursor.fetchone())[0]
                    
                    # 獲取分頁數據
                    offset = (page - 1) * page_size
                    await cursor.execute("""
                        SELECT id, version, changed_by, change_type, changes, created_at
                        FROM workflow_history
                        WHERE workflow_id = %s
                        ORDER BY created_at DESC
                        LIMIT %s OFFSET %s
                    """, (workflow_id, page_size, offset))
                    
                    results = await cursor.fetchall()
                    
                    history = []
                    for result in results:
                        history.append({
                            'id': result[0],
                            'version': result[1],
                            'changed_by': result[2],
                            'change_type': result[3],
                            'changes': json.loads(result[4]) if result[4] else {},
                            'created_at': result[5]
                        })
                    
                    return history, total_count
                    
        except Exception as e:
            logger.error(f"獲取工作流程歷史失敗: {e}")
            return [], 0
    
    # ========== 實時數據查詢 ==========
    
    async def get_active_workflows(self, guild_id: int) -> List[Dict[str, Any]]:
        """獲取活躍的工作流程"""
        try:
            async with self.db.connection() as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute("""
                        SELECT id, name, trigger_type, execution_count, last_executed
                        FROM workflows
                        WHERE guild_id = %s AND status = 'active'
                        ORDER BY last_executed DESC
                    """, (guild_id,))
                    
                    results = await cursor.fetchall()
                    
                    workflows = []
                    for result in results:
                        workflows.append({
                            'id': result[0],
                            'name': result[1],
                            'trigger_type': result[2],
                            'execution_count': result[3],
                            'last_executed': result[4]
                        })
                    
                    return workflows
                    
        except Exception as e:
            logger.error(f"獲取活躍工作流程失敗: {e}")
            return []
    
    async def get_executions_count(self, guild_id: int = None, workflow_id: str = None, 
                                 start_time: datetime = None, end_time: datetime = None) -> int:
        """獲取執行數量"""
        try:
            conditions = []
            params = []
            
            if guild_id is not None:
                # 通過工作流程表關聯獲取伺服器ID
                conditions.append("e.workflow_id IN (SELECT id FROM workflows WHERE guild_id = %s)")
                params.append(guild_id)
            
            if workflow_id:
                conditions.append("e.workflow_id = %s")
                params.append(workflow_id)
            
            if start_time:
                conditions.append("e.start_time >= %s")
                params.append(start_time)
            
            if end_time:
                conditions.append("e.start_time <= %s")
                params.append(end_time)
            
            where_clause = "WHERE " + " AND ".join(conditions) if conditions else ""
            
            async with self.db.connection() as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute(f"""
                        SELECT COUNT(*) 
                        FROM workflow_executions e
                        {where_clause}
                    """, params)
                    
                    result = await cursor.fetchone()
                    return result[0] if result else 0
                    
        except Exception as e:
            logger.error(f"獲取執行數量失敗: {e}")
            return 0
    
    async def get_running_executions_count(self, guild_id: int = None) -> int:
        """獲取執行中的工作流程數量"""
        try:
            conditions = ["e.status = 'running'"]
            params = []
            
            if guild_id is not None:
                conditions.append("e.workflow_id IN (SELECT id FROM workflows WHERE guild_id = %s)")
                params.append(guild_id)
            
            where_clause = "WHERE " + " AND ".join(conditions)
            
            async with self.db.connection() as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute(f"""
                        SELECT COUNT(*) 
                        FROM workflow_executions e
                        {where_clause}
                    """, params)
                    
                    result = await cursor.fetchone()
                    return result[0] if result else 0
                    
        except Exception as e:
            logger.error(f"獲取執行中工作流程數量失敗: {e}")
            return 0
    
    async def get_workflow_activity_summary(self, guild_id: int, days: int = 7) -> Dict[str, Any]:
        """獲取工作流程活動摘要"""
        try:
            start_date = datetime.now(timezone.utc) - timedelta(days=days)
            
            async with self.db.connection() as conn:
                async with conn.cursor() as cursor:
                    # 獲取基本統計
                    await cursor.execute("""
                        SELECT 
                            COUNT(DISTINCT w.id) as total_workflows,
                            COUNT(DISTINCT CASE WHEN w.status = 'active' THEN w.id END) as active_workflows,
                            COUNT(e.id) as total_executions,
                            COUNT(CASE WHEN e.status = 'running' THEN e.id END) as running_executions,
                            COUNT(CASE WHEN e.status = 'completed' THEN e.id END) as completed_executions,
                            COUNT(CASE WHEN e.status = 'failed' THEN e.id END) as failed_executions
                        FROM workflows w
                        LEFT JOIN workflow_executions e ON w.id = e.workflow_id 
                                                        AND e.start_time >= %s
                        WHERE w.guild_id = %s
                    """, (start_date, guild_id))
                    
                    result = await cursor.fetchone()
                    
                    if not result:
                        return {
                            'total_workflows': 0,
                            'active_workflows': 0,
                            'total_executions': 0,
                            'running_executions': 0,
                            'completed_executions': 0,
                            'failed_executions': 0,
                            'success_rate': 0.0
                        }
                    
                    total_executions = result[2] or 0
                    completed_executions = result[4] or 0
                    success_rate = (completed_executions / total_executions * 100) if total_executions > 0 else 0.0
                    
                    return {
                        'total_workflows': result[0] or 0,
                        'active_workflows': result[1] or 0,
                        'total_executions': total_executions,
                        'running_executions': result[3] or 0,
                        'completed_executions': completed_executions,
                        'failed_executions': result[5] or 0,
                        'success_rate': success_rate
                    }
                    
        except Exception as e:
            logger.error(f"獲取工作流程活動摘要失敗: {e}")
            return {
                'total_workflows': 0,
                'active_workflows': 0,
                'total_executions': 0,
                'running_executions': 0,
                'completed_executions': 0,
                'failed_executions': 0,
                'success_rate': 0.0
            }
    
    # ========== 清理操作 ==========
    
    async def cleanup_old_executions(self, days: int = 90) -> int:
        """清理舊的執行記錄"""
        try:
            cutoff_date = datetime.now(timezone.utc) - timedelta(days=days)
            
            async with self.db.connection() as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute("""
                        DELETE FROM workflow_executions 
                        WHERE start_time < %s AND status IN ('completed', 'failed', 'cancelled')
                    """, (cutoff_date,))
                    
                    deleted_count = cursor.rowcount
                    await conn.commit()
                    
                    logger.info(f"清理了 {deleted_count} 條舊的工作流程執行記錄")
                    return deleted_count
                    
        except Exception as e:
            logger.error(f"清理執行記錄失敗: {e}")
            return 0
    
    async def cleanup_old_statistics(self, days: int = 365) -> int:
        """清理舊的統計數據"""
        try:
            cutoff_date = datetime.now(timezone.utc).date() - timedelta(days=days)
            
            async with self.db.connection() as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute("""
                        DELETE FROM workflow_statistics WHERE date < %s
                    """, (cutoff_date,))
                    
                    deleted_count = cursor.rowcount
                    await conn.commit()
                    
                    logger.info(f"清理了 {deleted_count} 條舊的統計數據")
                    return deleted_count
                    
        except Exception as e:
            logger.error(f"清理統計數據失敗: {e}")
            return 0