# bot/db/pool.py - v2.0
# ✅ MariaDB/MySQL 非同步連線池管理（aiomysql）
# 整合初始化、單例、上下文管理、連線取得與釋放

import aiomysql
from contextlib import asynccontextmanager
from typing import Optional, Dict, Any
from shared.logger import logger  # 你的專案 logger

class MariaDBPool:
    """
    MariaDB 非同步連線池管理器
    負責：初始化連線池、取得/釋放連線、上下文管理
    """
    def __init__(self):
        self.pool: Optional[aiomysql.Pool] = None
        self._connection_params: Dict[str, Any] = {}
        self._initialized: bool = False

    async def initialize(self, host: str, port: int, user: str,
                        password: str, database: str, **kwargs):
        """
        初始化連線池，專案啟動時呼叫一次
        """
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
                'maxsize': kwargs.get('maxsize', 5),
            }
            self.pool = await aiomysql.create_pool(**self._connection_params)
            self._initialized = True
            logger.info("✅ 資料庫連線池已建立")
        except Exception as e:
            logger.error(f"❌ 資料庫連線池建立失敗：{e}")
            raise

    async def acquire(self):
        """
        取得一條資料庫連線
        """
        if not self._initialized or not self.pool:
            raise RuntimeError("資料庫連線池尚未初始化")
        return await self.pool.acquire()

    async def release(self, conn):
        """
        釋放資料庫連線
        """
        if self.pool:
            self.pool.release(conn)

    @asynccontextmanager
    async def connection(self):
        """
        非同步上下文：用於 with 語法自動取得/釋放連線
        用法：
            async with db_pool.connection() as conn:
                # 使用 conn 做資料操作
        """
        conn = await self.acquire()
        try:
            yield conn
        finally:
            await self.release(conn)

# ✅ 全域單例實體（專案統一使用這個變數）
db_pool = MariaDBPool()
