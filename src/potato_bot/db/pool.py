# bot/db/pool.py - v2.3 修復版
# ✅ MariaDB/MySQL 非同步連線池管理（aiomysql）修復版
# 修復：acquire/release 方法、錯誤處理、連接池管理

import asyncio
import logging
from contextlib import asynccontextmanager
from typing import Any, Dict, Optional

import aiomysql

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
        self._closing = False
        self._tasks = set()  # 追蹤活躍的任務

    async def initialize(
        self,
        host: str,
        port: int,
        user: str,
        password: str,
        database: str,
        **kwargs,
    ):
        """初始化連線池（修復版）"""
        async with self._lock:
            if self._initialized:
                logger.warning("資料庫連線池已經初始化")
                return

            try:
                # 修復：添加更好的連接池參數
                self._connection_params = {
                    "host": host,
                    "port": port,
                    "user": user,
                    "password": password,
                    "db": database,
                    "charset": kwargs.get("charset", "utf8mb4"),
                    "autocommit": kwargs.get("autocommit", True),
                    "minsize": kwargs.get("minsize", 1),  # 修復：從5改為1
                    "maxsize": kwargs.get("maxsize", 10),  # 修復：從20改為10
                    "pool_recycle": kwargs.get("pool_recycle", 3600),
                    "echo": kwargs.get("echo", False),
                    # 修復：添加超時設定
                    "connect_timeout": kwargs.get("connect_timeout", 10),
                }

                # 修復：不再傳遞 loop 參數（discord.py 2.x 不需要）
                if "loop" in self._connection_params:
                    del self._connection_params["loop"]

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
        """測試資料庫連接（修復版）"""
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
            conn = await asyncio.wait_for(self.pool.acquire(), timeout=10.0)
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
        """釋放連線（修復版）"""
        if self.pool and conn and not self._closing:
            try:
                # 修復：正確的釋放方式
                await self.pool.release(conn)
            except Exception as e:
                logger.error(f"釋放資料庫連接失敗：{e}")
                # 強制關閉連接
                try:
                    if hasattr(conn, "close"):
                        conn.close()
                except:
                    pass

    @asynccontextmanager
    async def connection(self):
        """非同步上下文管理器（修復版）"""
        if self._closing:
            raise RuntimeError("連線池正在關閉中")

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
        """健康檢查（修復版）"""
        try:
            if not self._initialized or not self.pool or self._closing:
                return {
                    "status": "unhealthy",
                    "error": "連線池未初始化或正在關閉",
                    "latency": "N/A",
                    "pool_status": "N/A",
                }

            # 測量延遲
            start_time = asyncio.get_event_loop().time()

            # 修復：添加連線池狀態檢查
            pool_info = {
                "size": getattr(self.pool, "_size", getattr(self.pool, "size", 0)),
                "used": getattr(self.pool, "_used_size", getattr(self.pool, "used_size", 0)),
                "free": getattr(self.pool, "_free_size", getattr(self.pool, "free_size", 0)),
                "minsize": getattr(self.pool, "_minsize", getattr(self.pool, "minsize", 0)),
                "maxsize": getattr(self.pool, "_maxsize", getattr(self.pool, "maxsize", 0)),
            }

            # 快速測試查詢
            async with self.connection() as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute("SELECT DATABASE(), NOW(), CONNECTION_ID()")
                    db_name, now, connection_id = await cursor.fetchone()

            # 計算延遲
            end_time = asyncio.get_event_loop().time()
            latency_ms = round((end_time - start_time) * 1000, 2)

            # 建構連線池狀態描述
            pool_status = f"{pool_info['used']}/{pool_info['maxsize']} (已使用/最大)"

            return {
                "status": "healthy",
                "latency": f"{latency_ms}ms",
                "pool_status": pool_status,
                "database": {
                    "name": db_name,
                    "server_time": str(now),
                    "connection_id": connection_id,
                },
                "pool": pool_info,
            }

        except Exception as e:
            logger.error(f"健康檢查失敗：{e}")
            return {
                "status": "unhealthy",
                "error": str(e),
                "latency": "N/A",
                "pool_status": "N/A",
            }

    async def close(self):
        """關閉連線池（修復Task warnings）"""
        async with self._lock:
            if not self._initialized or not self.pool:
                return

            self._closing = True

            try:
                # 修復：等待所有活躍任務完成
                if self._tasks:
                    logger.info(f"等待 {len(self._tasks)} 個資料庫任務完成...")
                    await asyncio.gather(*self._tasks, return_exceptions=True)

                # 關閉連線池
                self.pool.close()
                await self.pool.wait_closed()

                logger.info("✅ 資料庫連線池已關閉")

            except Exception as e:
                logger.error(f"關閉連線池錯誤：{e}")
            finally:
                self.pool = None
                self._initialized = False
                self._closing = False


# ✅ 全域單例實體（專案統一使用這個變數）
db_pool = MariaDBPool()

# ====== 主程式可呼叫的初始化/關閉/健康檢查 ======


async def init_database(host, port, user, password, database, **kwargs):
    """初始化資料庫連線池（修復版）"""
    try:
        await db_pool.initialize(host, port, user, password, database, **kwargs)
        logger.info("✅ 資料庫初始化完成")
    except Exception as e:
        logger.error(f"❌ 資料庫初始化失敗：{e}")
        raise


async def close_database():
    """正確關閉連線池（修復版）"""
    try:
        await db_pool.close()
        logger.info("✅ 資料庫已關閉")
    except Exception as e:
        logger.error(f"❌ 關閉資料庫錯誤：{e}")


async def get_db_health():
    """回傳資料庫健康狀態（修復版）"""
    try:
        health_data = await db_pool.health_check()
        return health_data
    except Exception as e:
        logger.error(f"取得資料庫健康狀態失敗：{e}")
        return {"status": "unhealthy", "error": str(e)}


# ====== 裝飾器和工具函數 ======


def with_db_connection(func):
    """資料庫連接裝飾器"""

    async def wrapper(*args, **kwargs):
        async with db_pool.connection() as conn:
            return await func(conn, *args, **kwargs)

    return wrapper


async def execute_query(
    query: str,
    params: tuple = None,
    fetch_one: bool = False,
    fetch_all: bool = False,
):
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
                await asyncio.sleep(delay * (2**attempt))  # 指數退避

    logger.error(f"執行失敗，已重試 {max_retries} 次")
    raise last_exception
