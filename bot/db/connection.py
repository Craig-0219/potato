# bot/db/connection.py - 票券系統資料庫連接池
"""
資料庫連接池管理 - 簡化版
提供穩定的資料庫連接管理
"""

import aiomysql
import asyncio
from contextlib import asynccontextmanager
from typing import Optional, Dict, Any
from datetime import datetime, timezone
from shared.logger import logger


class DatabasePool:
    """資料庫連接池管理器"""
    
    def __init__(self):
        self.pool: Optional[aiomysql.Pool] = None
        self._connection_params: Dict[str, Any] = {}
        self._initialized = False
    
    async def initialize(self, host: str, port: int, user: str, 
                        password: str, database: str, **kwargs):
        """初始化連接池"""
        try:
            self._connection_params = {
                'host': host,
                'port': port,
                'user': user,
                'password': password,
                'db': database,
                'charset': kwargs.get('charset', 'utf8mb4'),
                'autocommit': kwargs.get('autocommit', True),
                'minsize': kwargs.get('minsize', 1),
                'maxsize': kwargs.get('maxsize', 10),
                'echo': kwargs.get('echo', False)
            }
            
            self.pool = await aiomysql.create_pool(**self._connection_params)
            self._initialized = True
            
            logger.info("資料庫連接池初始化成功")
            
            # 建立必要的資料表
            await self._create_tables()
            
        except Exception as e:
            logger.error(f"資料庫連接池初始化失敗：{e}")
            raise
    
    async def close(self):
        """關閉連接池"""
        if self.pool:
            self.pool.close()
            await self.pool.wait_closed()
            self._initialized = False
            logger.info("資料庫連接池已關閉")
    
    @asynccontextmanager
    async def acquire(self):
        """取得資料庫連接"""
        if not self._initialized or not self.pool:
            raise RuntimeError("資料庫連接池未初始化")
        
        async with self.pool.acquire() as conn:
            try:
                yield conn
            except Exception as e:
                # 嘗試回滾事務
                try:
                    await conn.rollback()
                except:
                    pass
                raise e
    
    async def execute(self, query: str, params: tuple = None) -> int:
        """執行單一查詢"""
        async with self.acquire() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute(query, params)
                return cursor.rowcount
    
    async def fetch_one(self, query: str, params: tuple = None) -> Optional[Dict]:
        """取得單筆記錄"""
        async with self.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cursor:
                await cursor.execute(query, params)
                return await cursor.fetchone()
    
    async def fetch_all(self, query: str, params: tuple = None) -> list:
        """取得所有記錄"""
        async with self.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cursor:
                await cursor.execute(query, params)
                return await cursor.fetchall()
    
    async def fetch_many(self, query: str, params: tuple = None, size: int = None) -> list:
        """取得多筆記錄"""
        async with self.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cursor:
                await cursor.execute(query, params)
                return await cursor.fetchmany(size)
    
    async def execute_many(self, query: str, params_list: list) -> int:
        """批次執行查詢"""
        async with self.acquire() as conn:
            async with conn.cursor() as cursor:
                await cursor.executemany(query, params_list)
                return cursor.rowcount
    
    async def call_procedure(self, proc_name: str, params: tuple = None) -> list:
        """呼叫儲存程序"""
        async with self.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cursor:
                await cursor.callproc(proc_name, params)
                return await cursor.fetchall()
    
    async def get_connection_info(self) -> Dict[str, Any]:
        """取得連接資訊"""
        if not self.pool:
            return {"status": "未連接"}
        
        return {
            "status": "已連接",
            "minsize": self.pool.minsize,
            "maxsize": self.pool.maxsize,
            "size": self.pool.size,
            "freesize": self.pool.freesize,
            "host": self._connection_params.get('host'),
            "database": self._connection_params.get('db')
        }
    
    async def test_connection(self) -> bool:
        """測試連接"""
        try:
            async with self.acquire() as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute("SELECT 1")
                    result = await cursor.fetchone()
                    return result[0] == 1
        except Exception as e:
            logger.error(f"資料庫連接測試失敗：{e}")
            return False
    
    async def _create_tables(self):
        """建立必要的資料表"""
        tables = [
            # 票券主表
            """
            CREATE TABLE IF NOT EXISTS tickets (
                id INT AUTO_INCREMENT PRIMARY KEY,
                discord_id VARCHAR(20) NOT NULL COMMENT '開票者 Discord ID',
                username VARCHAR(100) NOT NULL COMMENT '開票者用戶名',
                type VARCHAR(50) NOT NULL COMMENT '票券類型',
                priority ENUM('high', 'medium', 'low') DEFAULT 'medium' COMMENT '優先級',
                status ENUM('open', 'closed') DEFAULT 'open' COMMENT '狀態',
                channel_id BIGINT NOT NULL COMMENT '頻道 ID',
                guild_id BIGINT NOT NULL COMMENT '伺服器 ID', 
                assigned_to BIGINT NULL COMMENT '指派的客服 ID',
                rating INT NULL CHECK (rating BETWEEN 1 AND 5) COMMENT '評分',
                rating_feedback TEXT NULL COMMENT '評分回饋',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '建立時間',
                closed_at TIMESTAMP NULL COMMENT '關閉時間',
                closed_by VARCHAR(20) NULL COMMENT '關閉者 ID',
                close_reason TEXT NULL COMMENT '關閉原因',
                
                INDEX idx_guild_status (guild_id, status),
                INDEX idx_assigned (assigned_to),
                INDEX idx_created (created_at),
                INDEX idx_channel (channel_id),
                INDEX idx_discord_id (discord_id)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            """,
            
            # 系統設定表
            """
            CREATE TABLE IF NOT EXISTS ticket_settings (
                guild_id BIGINT PRIMARY KEY COMMENT '伺服器 ID',
                category_id BIGINT NULL COMMENT '分類頻道 ID',
                support_roles JSON NULL COMMENT '客服身分組列表',
                max_tickets_per_user INT DEFAULT 3 COMMENT '每人最大票券數',
                auto_close_hours INT DEFAULT 24 COMMENT '自動關閉小時數',
                sla_response_minutes INT DEFAULT 60 COMMENT 'SLA 回應時間',
                welcome_message TEXT NULL COMMENT '歡迎訊息',
                log_channel_id BIGINT NULL COMMENT '日誌頻道 ID',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            """,
            
            # 操作日誌表
            """
            CREATE TABLE IF NOT EXISTS ticket_logs (
                id INT AUTO_INCREMENT PRIMARY KEY,
                ticket_id INT NOT NULL COMMENT '票券 ID',
                action VARCHAR(50) NOT NULL COMMENT '操作類型',
                details TEXT NULL COMMENT '操作詳情',
                user_id VARCHAR(20) NULL COMMENT '操作者 ID',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                
                FOREIGN KEY (ticket_id) REFERENCES tickets(id) ON DELETE CASCADE,
                INDEX idx_ticket (ticket_id),
                INDEX idx_action (action),
                INDEX idx_created (created_at)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            """,
            
            # SLA 監控表
            """
            CREATE TABLE IF NOT EXISTS ticket_sla (
                id INT AUTO_INCREMENT PRIMARY KEY,
                ticket_id INT NOT NULL COMMENT '票券 ID',
                first_response_at TIMESTAMP NULL COMMENT '首次回應時間',
                response_time_minutes INT NULL COMMENT '回應時間（分鐘）',
                sla_target_minutes INT NOT NULL COMMENT 'SLA 目標時間',
                is_met BOOLEAN DEFAULT FALSE COMMENT '是否達標',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                
                FOREIGN KEY (ticket_id) REFERENCES tickets(id) ON DELETE CASCADE,
                INDEX idx_ticket (ticket_id),
                INDEX idx_is_met (is_met)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            """
        ]
        
        try:
            async with self.acquire() as conn:
                async with conn.cursor() as cursor:
                    for table_sql in tables:
                        await cursor.execute(table_sql)
                    await conn.commit()
            
            logger.info("資料表建立完成")
            
        except Exception as e:
            logger.error(f"建立資料表錯誤：{e}")
            raise
    
    async def get_table_info(self, table_name: str) -> Dict[str, Any]:
        """取得資料表資訊"""
        try:
            # 取得資料表結構
            columns = await self.fetch_all(f"DESCRIBE {table_name}")
            
            # 取得索引資訊
            indexes = await self.fetch_all(f"SHOW INDEX FROM {table_name}")
            
            # 取得資料表狀態
            status = await self.fetch_one(f"SHOW TABLE STATUS LIKE '{table_name}'")
            
            return {
                "columns": columns,
                "indexes": indexes,
                "status": status
            }
            
        except Exception as e:
            logger.error(f"取得資料表資訊錯誤：{e}")
            return {}
    
    async def optimize_tables(self) -> Dict[str, str]:
        """優化資料表"""
        tables = ['tickets', 'ticket_settings', 'ticket_logs', 'ticket_sla']
        results = {}
        
        try:
            async with self.acquire() as conn:
                async with conn.cursor() as cursor:
                    for table in tables:
                        await cursor.execute(f"OPTIMIZE TABLE {table}")
                        result = await cursor.fetchone()
                        results[table] = result[3] if result else "未知"
            
            logger.info("資料表優化完成")
            return results
            
        except Exception as e:
            logger.error(f"資料表優化錯誤：{e}")
            return {table: "錯誤" for table in tables}
    
    async def backup_table(self, table_name: str, backup_name: str = None) -> bool:
        """備份資料表"""
        if not backup_name:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_name = f"{table_name}_backup_{timestamp}"
        
        try:
            async with self.acquire() as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute(f"CREATE TABLE {backup_name} AS SELECT * FROM {table_name}")
            
            logger.info(f"資料表 {table_name} 備份為 {backup_name}")
            return True
            
        except Exception as e:
            logger.error(f"備份資料表錯誤：{e}")
            return False
    
    async def get_database_size(self) -> Dict[str, Any]:
        """取得資料庫大小資訊"""
        try:
            db_name = self._connection_params.get('db')
            
            query = """
            SELECT 
                table_name,
                ROUND(((data_length + index_length) / 1024 / 1024), 2) AS 'size_mb',
                table_rows
            FROM information_schema.tables 
            WHERE table_schema = %s
            ORDER BY (data_length + index_length) DESC
            """
            
            tables = await self.fetch_all(query, (db_name,))
            
            total_size = sum(table.get('size_mb', 0) for table in tables)
            
            return {
                "total_size_mb": round(total_size, 2),
                "tables": tables,
                "database": db_name
            }
            
        except Exception as e:
            logger.error(f"取得資料庫大小錯誤：{e}")
            return {"total_size_mb": 0, "tables": [], "database": "未知"}
    
    async def health_check(self) -> Dict[str, Any]:
        """健康檢查"""
        health_info = {
            "timestamp": datetime.now(timezone.utc),
            "connection_pool": {},
            "database": {},
            "tables": {},
            "overall_status": "healthy"
        }
        
        try:
            # 連接池狀態
            health_info["connection_pool"] = await self.get_connection_info()
            
            # 資料庫連接測試
            connection_ok = await self.test_connection()
            health_info["database"]["connection"] = "ok" if connection_ok else "failed"
            
            if not connection_ok:
                health_info["overall_status"] = "unhealthy"
                return health_info
            
            # 檢查主要資料表
            tables = ['tickets', 'ticket_settings', 'ticket_logs']
            for table in tables:
                try:
                    count = await self.fetch_one(f"SELECT COUNT(*) as count FROM {table}")
                    health_info["tables"][table] = {
                        "status": "ok",
                        "row_count": count.get('count', 0) if count else 0
                    }
                except Exception as e:
                    health_info["tables"][table] = {
                        "status": "error",
                        "error": str(e)
                    }
                    health_info["overall_status"] = "degraded"
            
            # 資料庫大小資訊
            size_info = await self.get_database_size()
            health_info["database"]["size_mb"] = size_info.get("total_size_mb", 0)
            
        except Exception as e:
            logger.error(f"健康檢查錯誤：{e}")
            health_info["overall_status"] = "unhealthy"
            health_info["error"] = str(e)
        
        return health_info


# ===== 全域資料庫實例 =====
database = DatabasePool()


# ===== 輔助函數 =====

async def init_database(host: str, port: int, user: str, password: str, database_name: str):
    """初始化資料庫"""
    await database.initialize(host, port, user, password, database_name)


async def close_database():
    """關閉資料庫連接"""
    await database.close()


async def get_db_health():
    """取得資料庫健康狀態"""
    return await database.health_check()


# ===== 資料庫工具 =====

class DatabaseMaintenance:
    """資