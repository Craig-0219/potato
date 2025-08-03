# bot/db/pool.py - v2.3 修復版
# ✅ MariaDB/MySQL 非同步連線池管理（aiomysql）修復版
# 修復：acquire/release 方法、錯誤處理、連接池管理

import aiomysql
from contextlib import asynccontextmanager
from typing import Optional, Dict, Any
import asyncio
import logging

# 設置日誌
logger = logging.getLogger(__name__)

class MariaDBPool:
    """
    MariaDB 非同步連線池管理器（修復版）
    修復點：
    1. 正確的 acquire/release 實現
    2. 添加連接池健康檢查
    3. 改善錯誤處理
    4. 添加重連機制
    """
    def __init__(self):
        self.pool: Optional[aiomysql.Pool] = None
        self._connection_params: Dict[str, Any] = {}
        self._initialized: bool = False
        self._lock = asyncio.Lock()

    async def initialize(self, host: str, port: int, user: str,
                        password: str, database: str, **kwargs):
        """
        初始化連線池，專案啟動時呼叫一次
        """
        async with self._lock:
            if self._initialized:
                logger.warning("資料庫連線池已經初始化")
                return

            try:
                self._connection_params = {
                    'host': host,
                    'port': port,
                    'user': user,
                    'password': password,
                    'db': database,
                    'charset': kwargs.get('charset', 'utf8mb4'),
                    'autocommit': kwargs.get('autocommit', True),
                    'minsize': kwargs.get('minsize', 5),
                    'maxsize': kwargs.get('maxsize', 20),
                    'pool_recycle': kwargs.get('pool_recycle', 3600),  # 1小時回收
                    'echo': kwargs.get('echo', False)
                }
                
                # 建立連線池
                self.pool = await aiomysql.create_pool(**self._connection_params)
                self._initialized = True
                logger.info("✅ 資料庫連線池已建立")
                
                # 測試連接
                await self._test_connection()
                
            except Exception as e:
                logger.error(f"❌ 資料庫連線池建立失敗：{e}")
                self._initialized = False
                raise

    async def _test_connection(self):
        """測試資料庫連接"""
        try:
            async with self.connection() as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute("SELECT 1")
                    result = await cursor.fetchone()
                    if result and result[0] == 1:
                        logger.info("✅ 資料庫連接測試成功")
                    else:
                        raise Exception("資料庫連接測試失敗")
        except Exception as e:
            logger.error(f"❌ 資料庫連接測試失敗：{e}")
            raise

    async def acquire(self):
        """
        取得一條資料庫連線（修復版）
        """
        if not self._initialized or not self.pool:
            raise RuntimeError("資料庫連線池尚未初始化")
        
        try:
            # 獲取連接，設置超時
            conn = await asyncio.wait_for(
                self.pool.acquire(), 
                timeout=10.0
            )
            return conn
        except asyncio.TimeoutError:
            logger.error("獲取資料庫連接超時")
            raise RuntimeError("獲取資料庫連接超時")
        except Exception as e:
            logger.error(f"獲取資料庫連接失敗：{e}")
            # 嘗試重新初始化連接池
            await self._reconnect()
            raise

    async def release(self, conn):
        """
        釋放資料庫連線（修復版）
        """
        if self.pool and conn:
            try:
                await self.pool.release(conn)  # 修復：添加 await
            except Exception as e:
                logger.error(f"釋放資料庫連接失敗：{e}")
                # 如果釋放失敗，強制關閉連接
                try:
                    conn.close()
                except:
                    pass

    @asynccontextmanager
    async def connection(self):
        """
        非同步上下文：用於 with 語法自動取得/釋放連線（修復版）
        """
        conn = None
        try:
            conn = await self.acquire()
            yield conn
        except Exception as e:
            logger.error(f"資料庫操作錯誤：{e}")
            raise
        finally:
            if conn:
                await self.release(conn)

    async def _reconnect(self):
        """重新連接資料庫"""
        async with self._lock:
            if self.pool:
                try:
                    self.pool.close()
                    await self.pool.wait_closed()
                except Exception as e:
                    logger.error(f"關閉舊連線池失敗：{e}")
            
            try:
                self.pool = await aiomysql.create_pool(**self._connection_params)
                logger.info("✅ 資料庫連線池重新建立成功")
            except Exception as e:
                logger.error(f"❌ 資料庫重連失敗：{e}")
                self._initialized = False
                raise

    async def health_check(self) -> Dict[str, Any]:
        """
        健康檢查（新增）
        """
        try:
            if not self._initialized or not self.pool:
                return {
                    "status": "unhealthy",
                    "error": "連線池未初始化"
                }

            # 檢查連線池狀態
            pool_info = {
                "size": self.pool.size,
                "used": self.pool.used,
                "free": self.pool.free
            }

            # 測試查詢
            async with self.connection() as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute("SELECT DATABASE(), NOW(), CONNECTION_ID()")
                    db_name, now, connection_id = await cursor.fetchone()
                    
                    # 查詢資料庫大小
                    await cursor.execute("""
                        SELECT ROUND(SUM(data_length + index_length) / 1024 / 1024, 2) 
                        FROM information_schema.tables 
                        WHERE table_schema = DATABASE()
                    """)
                    size_result = await cursor.fetchone()
                    size_mb = size_result[0] if size_result and size_result[0] else 0

            return {
                "status": "healthy",
                "database": {
                    "name": db_name,
                    "size_mb": float(size_mb),
                    "server_time": str(now),
                    "connection_id": connection_id
                },
                "pool": pool_info
            }

        except Exception as e:
            logger.error(f"健康檢查失敗：{e}")
            return {
                "status": "unhealthy",
                "error": str(e)
            }

    async def close(self):
        """正確關閉連線池"""
        async with self._lock:
            if self.pool:
                try:
                    self.pool.close()
                    await self.pool.wait_closed()
                    logger.info("✅ 資料庫連線池已關閉")
                except Exception as e:
                    logger.error(f"關閉連線池錯誤：{e}")
                finally:
                    self.pool = None
                    self._initialized = False

# ✅ 全域單例實體（專案統一使用這個變數）
db_pool = MariaDBPool()

# ====== 主程式可呼叫的初始化/關閉/健康檢查 ======

async def init_database(host, port, user, password, database, **kwargs):
    """初始化資料庫連線池"""
    try:
        await db_pool.initialize(host, port, user, password, database, **kwargs)
        logger.info("資料庫初始化完成")
    except Exception as e:
        logger.error(f"資料庫初始化失敗：{e}")
        raise

async def close_database():
    """正確關閉連線池"""
    try:
        await db_pool.close()
        logger.info("資料庫已關閉")
    except Exception as e:
        logger.error(f"關閉資料庫錯誤：{e}")

async def get_db_health():
    """
    回傳資料庫健康狀態 dict（修復版）
    """
    try:
        health_data = await db_pool.health_check()
        return {
            "overall_status": health_data["status"],
            "database": health_data.get("database", {}),
            "pool": health_data.get("pool", {})
        }
    except Exception as e:
        logger.error(f"取得資料庫健康狀態失敗：{e}")
        return {
            "overall_status": "unhealthy",
            "error": str(e)
        }

# ====== 裝飾器和工具函數 ======

def with_db_connection(func):
    """資料庫連接裝飾器"""
    async def wrapper(*args, **kwargs):
        async with db_pool.connection() as conn:
            return await func(conn, *args, **kwargs)
    return wrapper

async def execute_query(query: str, params: tuple = None, fetch_one: bool = False, fetch_all: bool = False):
    """執行查詢的便捷函數"""
    async with db_pool.connection() as conn:
        async with conn.cursor(aiomysql.DictCursor) as cursor:
            await cursor.execute(query, params)
            
            if fetch_one:
                return await cursor.fetchone()
            elif fetch_all:
                return await cursor.fetchall()
            else:
                await conn.commit()
                return cursor.rowcount

# ====== 錯誤重試機制 ======

async def execute_with_retry(func, max_retries: int = 3, delay: float = 1.0):
    """帶重試機制的執行函數"""
    last_exception = None
    
    for attempt in range(max_retries):
        try:
            return await func()
        except Exception as e:
            last_exception = e
            logger.warning(f"執行失敗，重試 {attempt + 1}/{max_retries}：{e}")
            
            if attempt < max_retries - 1:
                await asyncio.sleep(delay * (2 ** attempt))  # 指數退避
            
    logger.error(f"執行失敗，已重試 {max_retries} 次")
    raise last_exception