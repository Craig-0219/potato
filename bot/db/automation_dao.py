# bot/db/automation_dao.py - 自動化規則資料存取層 v1.7.0
"""
自動化規則資料存取層
處理自動化規則、執行記錄等資料庫操作
"""

import json
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timezone, timedelta
from bot.db.base_dao import BaseDAO
from shared.logger import logger

class AutomationDAO(BaseDAO):
    """自動化規則資料存取物件"""
    
    def __init__(self):
        super().__init__()
    
    async def _initialize(self):
        """初始化資料庫表格"""
        try:
            await self._create_automation_tables()
            logger.info("✅ 自動化規則資料庫表格初始化完成")
        except Exception as e:
            logger.error(f"❌ 自動化規則資料庫初始化失敗: {e}")
            raise
    
    async def _create_automation_tables(self):
        """創建自動化規則相關表格"""
        async with self.db.connection() as conn:
            async with conn.cursor() as cursor:
                
                # 自動化規則表
                await cursor.execute("""
                    CREATE TABLE IF NOT EXISTS automation_rules (
                        id VARCHAR(36) PRIMARY KEY,
                        name VARCHAR(255) NOT NULL,
                        description TEXT,
                        guild_id BIGINT NOT NULL,
                        status ENUM('draft', 'active', 'paused', 'disabled', 'error') DEFAULT 'draft',
                        trigger_type VARCHAR(50) NOT NULL,
                        trigger_conditions JSON,
                        trigger_parameters JSON,
                        actions JSON NOT NULL,
                        created_by BIGINT DEFAULT 0,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                        last_executed TIMESTAMP NULL,
                        execution_count INT DEFAULT 0,
                        success_count INT DEFAULT 0,
                        failure_count INT DEFAULT 0,
                        tags JSON,
                        priority INT DEFAULT 5,
                        cooldown_seconds INT DEFAULT 0,
                        
                        INDEX idx_guild_id (guild_id),
                        INDEX idx_status (status),
                        INDEX idx_trigger_type (trigger_type),
                        INDEX idx_created_by (created_by),
                        INDEX idx_last_executed (last_executed),
                        INDEX idx_priority (priority)
                    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
                """)
                
                # 規則執行記錄表
                await cursor.execute("""
                    CREATE TABLE IF NOT EXISTS automation_executions (
                        id VARCHAR(36) PRIMARY KEY,
                        rule_id VARCHAR(36) NOT NULL,
                        guild_id BIGINT NOT NULL,
                        trigger_event JSON,
                        started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        completed_at TIMESTAMP NULL,
                        success BOOLEAN DEFAULT FALSE,
                        executed_actions INT DEFAULT 0,
                        failed_actions INT DEFAULT 0,
                        execution_time DECIMAL(8,3) DEFAULT 0.000,
                        error_message TEXT NULL,
                        details JSON,
                        user_id BIGINT NULL,
                        channel_id BIGINT NULL,
                        message_id BIGINT NULL,
                        
                        INDEX idx_rule_id (rule_id),
                        INDEX idx_guild_id (guild_id),
                        INDEX idx_started_at (started_at),
                        INDEX idx_success (success),
                        INDEX idx_completed_at (completed_at),
                        
                        FOREIGN KEY (rule_id) REFERENCES automation_rules(id) ON DELETE CASCADE
                    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
                """)
                
                # 規則變更歷史表
                await cursor.execute("""
                    CREATE TABLE IF NOT EXISTS automation_rule_history (
                        id INT AUTO_INCREMENT PRIMARY KEY,
                        rule_id VARCHAR(36) NOT NULL,
                        changed_by BIGINT NOT NULL,
                        change_type ENUM('created', 'updated', 'activated', 'deactivated', 'deleted') NOT NULL,
                        changes JSON,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        
                        INDEX idx_rule_id (rule_id),
                        INDEX idx_changed_by (changed_by),
                        INDEX idx_change_type (change_type),
                        INDEX idx_created_at (created_at),
                        
                        FOREIGN KEY (rule_id) REFERENCES automation_rules(id) ON DELETE CASCADE
                    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
                """)
                
                # 規則統計表
                await cursor.execute("""
                    CREATE TABLE IF NOT EXISTS automation_statistics (
                        id INT AUTO_INCREMENT PRIMARY KEY,
                        rule_id VARCHAR(36) NOT NULL,
                        date DATE NOT NULL,
                        execution_count INT DEFAULT 0,
                        success_count INT DEFAULT 0,
                        failure_count INT DEFAULT 0,
                        avg_execution_time DECIMAL(8,3) DEFAULT 0.000,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                        
                        UNIQUE KEY unique_rule_date (rule_id, date),
                        INDEX idx_rule_id (rule_id),
                        INDEX idx_date (date),
                        
                        FOREIGN KEY (rule_id) REFERENCES automation_rules(id) ON DELETE CASCADE
                    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
                """)
                
                await conn.commit()
    
    # ========== 規則CRUD操作 ==========
    
    async def create_rule(self, rule_data: Dict[str, Any]) -> str:
        """創建自動化規則"""
        try:
            async with self.db.connection() as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute("""
                        INSERT INTO automation_rules (
                            id, name, description, guild_id, status, trigger_type,
                            trigger_conditions, trigger_parameters, actions,
                            created_by, tags, priority, cooldown_seconds
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """, (
                        rule_data['id'],
                        rule_data['name'],
                        rule_data.get('description', ''),
                        rule_data['guild_id'],
                        rule_data.get('status', 'draft'),
                        rule_data['trigger_type'],
                        json.dumps(rule_data.get('trigger_conditions', [])),
                        json.dumps(rule_data.get('trigger_parameters', {})),
                        json.dumps(rule_data['actions']),
                        rule_data.get('created_by', 0),
                        json.dumps(rule_data.get('tags', [])),
                        rule_data.get('priority', 5),
                        rule_data.get('cooldown_seconds', 0)
                    ))
                    
                    await conn.commit()
                    
                    # 記錄變更歷史
                    await self._log_rule_history(
                        rule_data['id'], 
                        rule_data.get('created_by', 0),
                        'created',
                        rule_data
                    )
                    
                    return rule_data['id']
                    
        except Exception as e:
            logger.error(f"創建自動化規則失敗: {e}")
            raise
    
    async def update_rule(self, rule_id: str, updates: Dict[str, Any], updated_by: int) -> bool:
        """更新自動化規則"""
        try:
            async with self.db.connection() as conn:
                async with conn.cursor() as cursor:
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
                    
                    if 'priority' in updates:
                        set_clauses.append("priority = %s")
                        params.append(updates['priority'])
                    
                    if 'cooldown_seconds' in updates:
                        set_clauses.append("cooldown_seconds = %s")
                        params.append(updates['cooldown_seconds'])
                    
                    if not set_clauses:
                        return True
                    
                    params.append(rule_id)
                    
                    await cursor.execute(
                        f"UPDATE automation_rules SET {', '.join(set_clauses)}, updated_at = CURRENT_TIMESTAMP WHERE id = %s",
                        params
                    )
                    
                    await conn.commit()
                    
                    # 記錄變更歷史
                    await self._log_rule_history(rule_id, updated_by, 'updated', updates)
                    
                    return cursor.rowcount > 0
                    
        except Exception as e:
            logger.error(f"更新自動化規則失敗: {e}")
            return False
    
    async def get_rule(self, rule_id: str) -> Optional[Dict[str, Any]]:
        """獲取單個自動化規則"""
        try:
            async with self.db.connection() as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute("""
                        SELECT id, name, description, guild_id, status, trigger_type,
                               trigger_conditions, trigger_parameters, actions,
                               created_by, created_at, updated_at, last_executed,
                               execution_count, success_count, failure_count,
                               tags, priority, cooldown_seconds
                        FROM automation_rules WHERE id = %s
                    """, (rule_id,))
                    
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
                        'last_executed': result[12],
                        'execution_count': result[13],
                        'success_count': result[14],
                        'failure_count': result[15],
                        'tags': json.loads(result[16]) if result[16] else [],
                        'priority': result[17],
                        'cooldown_seconds': result[18]
                    }
                    
        except Exception as e:
            logger.error(f"獲取自動化規則失敗: {e}")
            return None
    
    async def get_rules(self, guild_id: int = None, status: str = None, 
                       trigger_type: str = None, page: int = 1, page_size: int = 20) -> Tuple[List[Dict[str, Any]], int]:
        """獲取自動化規則列表"""
        try:
            conditions = []
            params = []
            
            if guild_id:
                conditions.append("guild_id = %s")
                params.append(guild_id)
            
            if status:
                conditions.append("status = %s")
                params.append(status)
            
            if trigger_type:
                conditions.append("trigger_type = %s")
                params.append(trigger_type)
            
            where_clause = "WHERE " + " AND ".join(conditions) if conditions else ""
            
            async with self.db.connection() as conn:
                async with conn.cursor() as cursor:
                    # 獲取總數
                    count_sql = f"SELECT COUNT(*) FROM automation_rules {where_clause}"
                    await cursor.execute(count_sql, params)
                    total_count = (await cursor.fetchone())[0]
                    
                    # 獲取分頁數據
                    offset = (page - 1) * page_size
                    params.extend([page_size, offset])
                    
                    data_sql = f"""
                        SELECT id, name, description, guild_id, status, trigger_type,
                               created_by, created_at, updated_at, last_executed,
                               execution_count, success_count, failure_count,
                               tags, priority
                        FROM automation_rules {where_clause}
                        ORDER BY priority DESC, updated_at DESC
                        LIMIT %s OFFSET %s
                    """
                    
                    await cursor.execute(data_sql, params)
                    results = await cursor.fetchall()
                    
                    rules = []
                    for result in results:
                        rules.append({
                            'id': result[0],
                            'name': result[1],
                            'description': result[2],
                            'guild_id': result[3],
                            'status': result[4],
                            'trigger_type': result[5],
                            'created_by': result[6],
                            'created_at': result[7],
                            'updated_at': result[8],
                            'last_executed': result[9],
                            'execution_count': result[10],
                            'success_count': result[11],
                            'failure_count': result[12],
                            'tags': json.loads(result[13]) if result[13] else [],
                            'priority': result[14]
                        })
                    
                    return rules, total_count
                    
        except Exception as e:
            logger.error(f"獲取自動化規則列表失敗: {e}")
            return [], 0
    
    async def delete_rule(self, rule_id: str, deleted_by: int) -> bool:
        """刪除自動化規則"""
        try:
            async with self.db.connection() as conn:
                async with conn.cursor() as cursor:
                    # 記錄刪除歷史
                    await self._log_rule_history(rule_id, deleted_by, 'deleted', {})
                    
                    # 刪除規則（級聯刪除相關記錄）
                    await cursor.execute("DELETE FROM automation_rules WHERE id = %s", (rule_id,))
                    await conn.commit()
                    
                    return cursor.rowcount > 0
                    
        except Exception as e:
            logger.error(f"刪除自動化規則失敗: {e}")
            return False
    
    # ========== 執行記錄操作 ==========
    
    async def create_execution(self, execution_data: Dict[str, Any]) -> str:
        """創建執行記錄"""
        try:
            async with self.db.connection() as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute("""
                        INSERT INTO automation_executions (
                            id, rule_id, guild_id, trigger_event, started_at,
                            user_id, channel_id, message_id
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    """, (
                        execution_data['id'],
                        execution_data['rule_id'],
                        execution_data['guild_id'],
                        json.dumps(execution_data.get('trigger_event', {})),
                        execution_data.get('started_at', datetime.now(timezone.utc)),
                        execution_data.get('user_id'),
                        execution_data.get('channel_id'),
                        execution_data.get('message_id')
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
                    
                    if 'completed_at' in updates:
                        set_clauses.append("completed_at = %s")
                        params.append(updates['completed_at'])
                    
                    if 'success' in updates:
                        set_clauses.append("success = %s")
                        params.append(updates['success'])
                    
                    if 'executed_actions' in updates:
                        set_clauses.append("executed_actions = %s")
                        params.append(updates['executed_actions'])
                    
                    if 'failed_actions' in updates:
                        set_clauses.append("failed_actions = %s")
                        params.append(updates['failed_actions'])
                    
                    if 'execution_time' in updates:
                        set_clauses.append("execution_time = %s")
                        params.append(updates['execution_time'])
                    
                    if 'error_message' in updates:
                        set_clauses.append("error_message = %s")
                        params.append(updates['error_message'])
                    
                    if 'details' in updates:
                        set_clauses.append("details = %s")
                        params.append(json.dumps(updates['details']))
                    
                    if not set_clauses:
                        return True
                    
                    params.append(execution_id)
                    
                    await cursor.execute(
                        f"UPDATE automation_executions SET {', '.join(set_clauses)} WHERE id = %s",
                        params
                    )
                    
                    await conn.commit()
                    return cursor.rowcount > 0
                    
        except Exception as e:
            logger.error(f"更新執行記錄失敗: {e}")
            return False
    
    async def get_executions(self, rule_id: str = None, guild_id: int = None,
                           days: int = 30, page: int = 1, page_size: int = 50) -> Tuple[List[Dict[str, Any]], int]:
        """獲取執行記錄列表"""
        try:
            conditions = []
            params = []
            
            if rule_id:
                conditions.append("rule_id = %s")
                params.append(rule_id)
            
            if guild_id:
                conditions.append("guild_id = %s")
                params.append(guild_id)
            
            if days > 0:
                start_date = datetime.now(timezone.utc) - timedelta(days=days)
                conditions.append("started_at >= %s")
                params.append(start_date)
            
            where_clause = "WHERE " + " AND ".join(conditions) if conditions else ""
            
            async with self.db.connection() as conn:
                async with conn.cursor() as cursor:
                    # 獲取總數
                    count_sql = f"SELECT COUNT(*) FROM automation_executions {where_clause}"
                    await cursor.execute(count_sql, params)
                    total_count = (await cursor.fetchone())[0]
                    
                    # 獲取分頁數據
                    offset = (page - 1) * page_size
                    params.extend([page_size, offset])
                    
                    data_sql = f"""
                        SELECT e.id, e.rule_id, r.name as rule_name, e.guild_id,
                               e.started_at, e.completed_at, e.success,
                               e.executed_actions, e.failed_actions, e.execution_time,
                               e.error_message, e.user_id, e.channel_id
                        FROM automation_executions e
                        LEFT JOIN automation_rules r ON e.rule_id = r.id
                        {where_clause}
                        ORDER BY e.started_at DESC
                        LIMIT %s OFFSET %s
                    """
                    
                    await cursor.execute(data_sql, params)
                    results = await cursor.fetchall()
                    
                    executions = []
                    for result in results:
                        executions.append({
                            'id': result[0],
                            'rule_id': result[1],
                            'rule_name': result[2],
                            'guild_id': result[3],
                            'started_at': result[4],
                            'completed_at': result[5],
                            'success': result[6],
                            'executed_actions': result[7],
                            'failed_actions': result[8],
                            'execution_time': float(result[9]) if result[9] else 0.0,
                            'error_message': result[10],
                            'user_id': result[11],
                            'channel_id': result[12]
                        })
                    
                    return executions, total_count
                    
        except Exception as e:
            logger.error(f"獲取執行記錄列表失敗: {e}")
            return [], 0
    
    # ========== 統計操作 ==========
    
    async def update_rule_statistics(self, rule_id: str, execution_time: float, success: bool):
        """更新規則統計"""
        try:
            today = datetime.now(timezone.utc).date()
            
            async with self.db.connection() as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute("""
                        INSERT INTO automation_statistics 
                        (rule_id, date, execution_count, success_count, failure_count, avg_execution_time)
                        VALUES (%s, %s, 1, %s, %s, %s)
                        ON DUPLICATE KEY UPDATE
                        execution_count = execution_count + 1,
                        success_count = success_count + %s,
                        failure_count = failure_count + %s,
                        avg_execution_time = (avg_execution_time * (execution_count - 1) + %s) / execution_count
                    """, (
                        rule_id, today,
                        1 if success else 0,
                        0 if success else 1,
                        execution_time,
                        1 if success else 0,
                        0 if success else 1,
                        execution_time
                    ))
                    
                    # 更新規則統計計數
                    await cursor.execute("""
                        UPDATE automation_rules 
                        SET execution_count = execution_count + 1,
                            success_count = success_count + %s,
                            failure_count = failure_count + %s,
                            last_executed = CURRENT_TIMESTAMP
                        WHERE id = %s
                    """, (
                        1 if success else 0,
                        0 if success else 1,
                        rule_id
                    ))
                    
                    await conn.commit()
                    
        except Exception as e:
            logger.error(f"更新規則統計失敗: {e}")
    
    async def get_rule_statistics(self, rule_id: str, days: int = 30) -> Dict[str, Any]:
        """獲取規則統計"""
        try:
            end_date = datetime.now(timezone.utc).date()
            start_date = end_date - timedelta(days=days)
            
            async with self.db.connection() as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute("""
                        SELECT 
                            SUM(execution_count) as total_executions,
                            SUM(success_count) as total_success,
                            SUM(failure_count) as total_failures,
                            AVG(avg_execution_time) as avg_execution_time,
                            DATE(date) as stat_date
                        FROM automation_statistics
                        WHERE rule_id = %s AND date BETWEEN %s AND %s
                        GROUP BY DATE(date)
                        ORDER BY date DESC
                    """, (rule_id, start_date, end_date))
                    
                    daily_stats = await cursor.fetchall()
                    
                    # 計算總體統計
                    await cursor.execute("""
                        SELECT 
                            SUM(execution_count) as total_executions,
                            SUM(success_count) as total_success,
                            SUM(failure_count) as total_failures,
                            AVG(avg_execution_time) as avg_execution_time
                        FROM automation_statistics
                        WHERE rule_id = %s AND date BETWEEN %s AND %s
                    """, (rule_id, start_date, end_date))
                    
                    overall_stats = await cursor.fetchone()
                    
                    return {
                        'rule_id': rule_id,
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
            logger.error(f"獲取規則統計失敗: {e}")
            return {}
    
    async def get_guild_automation_statistics(self, guild_id: int, days: int = 30) -> Dict[str, Any]:
        """獲取伺服器自動化統計"""
        try:
            end_date = datetime.now(timezone.utc).date()
            start_date = end_date - timedelta(days=days)
            
            async with self.db.connection() as conn:
                async with conn.cursor() as cursor:
                    # 獲取伺服器內所有規則的統計
                    await cursor.execute("""
                        SELECT 
                            COUNT(DISTINCT r.id) as total_rules,
                            COUNT(DISTINCT CASE WHEN r.status = 'active' THEN r.id END) as active_rules,
                            SUM(COALESCE(s.execution_count, 0)) as total_executions,
                            SUM(COALESCE(s.success_count, 0)) as total_success,
                            SUM(COALESCE(s.failure_count, 0)) as total_failures,
                            AVG(COALESCE(s.avg_execution_time, 0)) as avg_execution_time
                        FROM automation_rules r
                        LEFT JOIN automation_statistics s ON r.id = s.rule_id 
                                                        AND s.date BETWEEN %s AND %s
                        WHERE r.guild_id = %s
                    """, (start_date, end_date, guild_id))
                    
                    overall_stats = await cursor.fetchone()
                    
                    # 獲取觸發類型分佈
                    await cursor.execute("""
                        SELECT trigger_type, COUNT(*) as count
                        FROM automation_rules
                        WHERE guild_id = %s
                        GROUP BY trigger_type
                        ORDER BY count DESC
                    """, (guild_id,))
                    
                    trigger_distribution = await cursor.fetchall()
                    
                    # 獲取最活躍的規則
                    await cursor.execute("""
                        SELECT r.id, r.name, r.execution_count, r.last_executed
                        FROM automation_rules r
                        WHERE r.guild_id = %s AND r.execution_count > 0
                        ORDER BY r.execution_count DESC
                        LIMIT 10
                    """, (guild_id,))
                    
                    top_rules = await cursor.fetchall()
                    
                    return {
                        'guild_id': guild_id,
                        'period_days': days,
                        'total_rules': overall_stats[0] or 0,
                        'active_rules': overall_stats[1] or 0,
                        'total_executions': overall_stats[2] or 0,
                        'success_count': overall_stats[3] or 0,
                        'failure_count': overall_stats[4] or 0,
                        'success_rate': (overall_stats[3] / overall_stats[2] * 100) if overall_stats[2] else 0,
                        'avg_execution_time': float(overall_stats[5]) if overall_stats[5] else 0.0,
                        'trigger_distribution': [
                            {'type': trigger[0], 'count': trigger[1]} 
                            for trigger in trigger_distribution
                        ],
                        'top_rules': [
                            {
                                'id': rule[0],
                                'name': rule[1],
                                'execution_count': rule[2],
                                'last_executed': rule[3]
                            } for rule in top_rules
                        ]
                    }
                    
        except Exception as e:
            logger.error(f"獲取伺服器自動化統計失敗: {e}")
            return {}
    
    # ========== 歷史記錄 ==========
    
    async def _log_rule_history(self, rule_id: str, changed_by: int, change_type: str, changes: Dict[str, Any]):
        """記錄規則變更歷史"""
        try:
            async with self.db.connection() as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute("""
                        INSERT INTO automation_rule_history (
                            rule_id, changed_by, change_type, changes
                        ) VALUES (%s, %s, %s, %s)
                    """, (
                        rule_id, changed_by, change_type, json.dumps(changes)
                    ))
                    
                    await conn.commit()
                    
        except Exception as e:
            logger.error(f"記錄規則歷史失敗: {e}")
    
    async def get_rule_history(self, rule_id: str, page: int = 1, page_size: int = 20) -> Tuple[List[Dict[str, Any]], int]:
        """獲取規則變更歷史"""
        try:
            async with self.db.connection() as conn:
                async with conn.cursor() as cursor:
                    # 獲取總數
                    await cursor.execute(
                        "SELECT COUNT(*) FROM automation_rule_history WHERE rule_id = %s",
                        (rule_id,)
                    )
                    total_count = (await cursor.fetchone())[0]
                    
                    # 獲取分頁數據
                    offset = (page - 1) * page_size
                    await cursor.execute("""
                        SELECT id, changed_by, change_type, changes, created_at
                        FROM automation_rule_history
                        WHERE rule_id = %s
                        ORDER BY created_at DESC
                        LIMIT %s OFFSET %s
                    """, (rule_id, page_size, offset))
                    
                    results = await cursor.fetchall()
                    
                    history = []
                    for result in results:
                        history.append({
                            'id': result[0],
                            'changed_by': result[1],
                            'change_type': result[2],
                            'changes': json.loads(result[3]) if result[3] else {},
                            'created_at': result[4]
                        })
                    
                    return history, total_count
                    
        except Exception as e:
            logger.error(f"獲取規則歷史失敗: {e}")
            return [], 0
    
    # ========== 清理操作 ==========
    
    async def cleanup_old_executions(self, days: int = 90) -> int:
        """清理舊的執行記錄"""
        try:
            cutoff_date = datetime.now(timezone.utc) - timedelta(days=days)
            
            async with self.db.connection() as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute("""
                        DELETE FROM automation_executions 
                        WHERE started_at < %s AND completed_at IS NOT NULL
                    """, (cutoff_date,))
                    
                    deleted_count = cursor.rowcount
                    await conn.commit()
                    
                    logger.info(f"清理了 {deleted_count} 條舊的自動化執行記錄")
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
                        DELETE FROM automation_statistics WHERE date < %s
                    """, (cutoff_date,))
                    
                    deleted_count = cursor.rowcount
                    await conn.commit()
                    
                    logger.info(f"清理了 {deleted_count} 條舊的自動化統計數據")
                    return deleted_count
                    
        except Exception as e:
            logger.error(f"清理統計數據失敗: {e}")
            return 0