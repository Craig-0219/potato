# bot/db/pool.py - MariaDB 非同步連線池管理器

import aiomysql
from contextlib import asynccontextmanager

class MariaDBPool:
    def __init__(self):
        self.pool = None

    async def init_pool(self, host, port, user, password, db_name):
        self.pool = await aiomysql.create_pool(
            host=host,
            port=port,
            user=user,
            password=password,
            db=db_name,
            autocommit=True,
            minsize=1,
            maxsize=5
        )
        print("✅ 資料庫連線池已建立")

    async def acquire(self):
        return await self.pool.acquire()

    async def release(self, conn):
        self.pool.release(conn)

    @asynccontextmanager
    async def connection(self):
        conn = await self.acquire()
        try:
            yield conn
        finally:
            await self.release(conn)

# ✅ 全域單例實體（供整個專案導入使用）
db_pool = MariaDBPool()
