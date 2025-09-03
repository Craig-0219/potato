# bot/db/base_dao.py - 新建檔案
"""
DAO 基底類別 - 統一資料存取介面
提供通用的資料庫操作和錯誤處理機制
"""

import json
from abc import ABC, abstractmethod
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple, Union

import aiomysql

from bot.db.pool import db_pool
from shared.logger import logger


class BaseDAO(ABC):
    """DAO 基底抽象類別"""

    def __init__(self, table_name: str = None):
        self.db = db_pool
        self.table_name = table_name
        self._initialized = False
        self._cache = {}
        self._cache_timeout = 300  # 5分鐘快取

    async def _ensure_initialized(self):
        """確保 DAO 已初始化（由子類實現具體邏輯）"""
        if not self._initialized:
            await self._initialize()
            self._initialized = True

    @abstractmethod
    async def _initialize(self):
        """初始化邏輯（由子類實現）"""

    # ===== 通用資料庫操作 =====

    async def execute_query(
        self,
        query: str,
        params: Tuple = None,
        fetch_one: bool = False,
        fetch_all: bool = False,
        dictionary: bool = False,
    ) -> Any:
        """執行 SQL 查詢的通用方法"""
        await self._ensure_initialized()

        try:
            async with self.db.connection() as conn:
                cursor_class = (
                    conn.cursor if not dictionary else lambda: conn.cursor(aiomysql.DictCursor)
                )
                async with cursor_class() as cursor:
                    await cursor.execute(query, params or ())

                    if fetch_one:
                        return await cursor.fetchone()
                    elif fetch_all:
                        return await cursor.fetchall()
                    else:
                        await conn.commit()
                        return cursor.rowcount

        except Exception as e:
            logger.error(f"[{self.__class__.__name__}] 查詢執行失敗：{query[:100]}... - {e}")
            raise

    async def insert(self, data: Dict[str, Any]) -> Optional[int]:
        """通用插入方法"""
        if not self.table_name:
            raise NotImplementedError("table_name 必須被設定")

        await self._ensure_initialized()

        try:
            columns = list(data.keys())
            placeholders = ", ".join(["%s"] * len(columns))
            query = f"INSERT INTO {self.table_name} ({', '.join(columns)}) VALUES ({placeholders})"

            async with self.db.connection() as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute(query, tuple(data.values()))
                    await conn.commit()
                    return cursor.lastrowid

        except Exception as e:
            logger.error(f"[{self.__class__.__name__}] 插入失敗：{e}")
            raise

    async def update_by_id(self, record_id: Union[int, str], data: Dict[str, Any]) -> bool:
        """通用更新方法（依ID）"""
        if not self.table_name:
            raise NotImplementedError("table_name 必須被設定")

        await self._ensure_initialized()

        try:
            set_clause = ", ".join([f"{key} = %s" for key in data.keys()])
            query = f"UPDATE {self.table_name} SET {set_clause} WHERE id = %s"
            params = tuple(data.values()) + (record_id,)

            result = await self.execute_query(query, params)
            return result > 0

        except Exception as e:
            logger.error(f"[{self.__class__.__name__}] 更新失敗：{e}")
            return False

    async def delete_by_id(self, record_id: Union[int, str]) -> bool:
        """通用刪除方法（依ID）"""
        if not self.table_name:
            raise NotImplementedError("table_name 必須被設定")

        await self._ensure_initialized()

        try:
            query = f"DELETE FROM {self.table_name} WHERE id = %s"
            result = await self.execute_query(query, (record_id,))
            return result > 0

        except Exception as e:
            logger.error(f"[{self.__class__.__name__}] 刪除失敗：{e}")
            return False

    async def get_by_id(self, record_id: Union[int, str]) -> Optional[Dict[str, Any]]:
        """通用查詢方法（依ID）"""
        if not self.table_name:
            raise NotImplementedError("table_name 必須被設定")

        await self._ensure_initialized()

        # 檢查快取
        cache_key = f"{self.table_name}:{record_id}"
        cached_result = self._get_from_cache(cache_key)
        if cached_result is not None:
            return cached_result

        try:
            query = f"SELECT * FROM {self.table_name} WHERE id = %s"
            result = await self.execute_query(query, (record_id,), fetch_one=True, dictionary=True)

            # 快取結果
            if result:
                self._set_cache(cache_key, result)

            return result

        except Exception as e:
            logger.error(f"[{self.__class__.__name__}] 查詢失敗：{e}")
            return None

    async def get_all(
        self,
        where_clause: str = None,
        params: Tuple = None,
        order_by: str = None,
        limit: int = None,
    ) -> List[Dict[str, Any]]:
        """通用查詢所有記錄方法"""
        if not self.table_name:
            raise NotImplementedError("table_name 必須被設定")

        await self._ensure_initialized()

        try:
            query = f"SELECT * FROM {self.table_name}"

            if where_clause:
                query += f" WHERE {where_clause}"

            if order_by:
                query += f" ORDER BY {order_by}"

            if limit:
                query += f" LIMIT {limit}"

            return await self.execute_query(query, params, fetch_all=True, dictionary=True)

        except Exception as e:
            logger.error(f"[{self.__class__.__name__}] 查詢所有記錄失敗：{e}")
            return []

    async def count(self, where_clause: str = None, params: Tuple = None) -> int:
        """計算記錄數量"""
        if not self.table_name:
            raise NotImplementedError("table_name 必須被設定")

        await self._ensure_initialized()

        try:
            query = f"SELECT COUNT(*) FROM {self.table_name}"

            if where_clause:
                query += f" WHERE {where_clause}"

            result = await self.execute_query(query, params, fetch_one=True)
            return result[0] if result else 0

        except Exception as e:
            logger.error(f"[{self.__class__.__name__}] 計算記錄數失敗：{e}")
            return 0

    async def exists(self, where_clause: str, params: Tuple = None) -> bool:
        """檢查記錄是否存在"""
        count = await self.count(where_clause, params)
        return count > 0

    # ===== 分頁查詢 =====

    async def paginate(
        self,
        page: int = 1,
        page_size: int = 10,
        where_clause: str = None,
        params: Tuple = None,
        order_by: str = "id DESC",
    ) -> Tuple[List[Dict[str, Any]], int]:
        """分頁查詢"""
        if not self.table_name:
            raise NotImplementedError("table_name 必須被設定")

        await self._ensure_initialized()

        try:
            # 計算總數
            total = await self.count(where_clause, params)

            # 分頁查詢
            offset = (page - 1) * page_size
            query = f"SELECT * FROM {self.table_name}"

            if where_clause:
                query += f" WHERE {where_clause}"

            if order_by:
                query += f" ORDER BY {order_by}"

            query += f" LIMIT {page_size} OFFSET {offset}"

            records = await self.execute_query(query, params, fetch_all=True, dictionary=True)

            return records, total

        except Exception as e:
            logger.error(f"[{self.__class__.__name__}] 分頁查詢失敗：{e}")
            return [], 0

    # ===== 快取管理 =====

    def _get_from_cache(self, key: str) -> Any:
        """從快取取得資料"""
        if key not in self._cache:
            return None

        cached_item = self._cache[key]

        # 檢查是否過期
        if (
            datetime.now(timezone.utc) - cached_item["timestamp"]
        ).total_seconds() > self._cache_timeout:
            del self._cache[key]
            return None

        return cached_item["data"]

    def _set_cache(self, key: str, data: Any):
        """設定快取"""
        self._cache[key] = {
            "data": data,
            "timestamp": datetime.now(timezone.utc),
        }

    def _clear_cache(self, pattern: str = None):
        """清除快取"""
        if pattern is None:
            self._cache.clear()
        else:
            keys_to_remove = [key for key in self._cache.keys() if pattern in key]
            for key in keys_to_remove:
                del self._cache[key]

    # ===== JSON 處理工具 =====

    @staticmethod
    def safe_json_loads(json_str: Union[str, None], default: Any = None) -> Any:
        """安全的 JSON 解析"""
        if not json_str:
            return default

        try:
            return json.loads(json_str)
        except (json.JSONDecodeError, TypeError):
            return default

    @staticmethod
    def safe_json_dumps(data: Any) -> str:
        """安全的 JSON 序列化"""
        try:
            return json.dumps(data, ensure_ascii=False, default=str)
        except (TypeError, ValueError):
            return "{}"

    # ===== 時間處理工具 =====

    @staticmethod
    def ensure_timezone(dt: datetime) -> datetime:
        """確保 datetime 對象有時區資訊"""
        if dt and dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc)
        return dt

    @staticmethod
    def datetime_to_timestamp(dt: datetime) -> int:
        """將 datetime 轉換為時間戳"""
        if dt:
            return int(dt.timestamp())
        return 0

    # ===== 批次操作 =====

    async def bulk_insert(
        self, data_list: List[Dict[str, Any]], batch_size: int = 100
    ) -> List[int]:
        """批次插入"""
        if not self.table_name or not data_list:
            return []

        await self._ensure_initialized()

        inserted_ids = []

        try:
            for i in range(0, len(data_list), batch_size):
                batch = data_list[i : i + batch_size]

                async with self.db.connection() as conn:
                    async with conn.cursor() as cursor:
                        for data in batch:
                            columns = list(data.keys())
                            placeholders = ", ".join(["%s"] * len(columns))
                            query = f"INSERT INTO {self.table_name} ({', '.join(columns)}) VALUES ({placeholders})"

                            await cursor.execute(query, tuple(data.values()))
                            inserted_ids.append(cursor.lastrowid)

                        await conn.commit()

            return inserted_ids

        except Exception as e:
            logger.error(f"[{self.__class__.__name__}] 批次插入失敗：{e}")
            return []

    async def bulk_update(
        self,
        updates: List[Tuple[Union[int, str], Dict[str, Any]]],
        batch_size: int = 100,
    ) -> int:
        """批次更新"""
        if not self.table_name or not updates:
            return 0

        await self._ensure_initialized()

        updated_count = 0

        try:
            for i in range(0, len(updates), batch_size):
                batch = updates[i : i + batch_size]

                async with self.db.connection() as conn:
                    async with conn.cursor() as cursor:
                        for record_id, data in batch:
                            set_clause = ", ".join([f"{key} = %s" for key in data.keys()])
                            query = f"UPDATE {self.table_name} SET {set_clause} WHERE id = %s"
                            params = tuple(data.values()) + (record_id,)

                            await cursor.execute(query, params)
                            updated_count += cursor.rowcount

                        await conn.commit()

            return updated_count

        except Exception as e:
            logger.error(f"[{self.__class__.__name__}] 批次更新失敗：{e}")
            return 0

    # ===== 統計和分析 =====

    async def get_statistics(self) -> Dict[str, Any]:
        """取得基本統計資訊（由子類擴展）"""
        if not self.table_name:
            return {}

        try:
            total_count = await self.count()

            return {"total_count": total_count, "table_name": self.table_name}

        except Exception as e:
            logger.error(f"[{self.__class__.__name__}] 取得統計失敗：{e}")
            return {}

    # ===== 資料驗證 =====

    def validate_data(
        self, data: Dict[str, Any], required_fields: List[str] = None
    ) -> Tuple[bool, str]:
        """驗證資料完整性"""
        if required_fields:
            missing_fields = [
                field for field in required_fields if field not in data or data[field] is None
            ]
            if missing_fields:
                return False, f"缺少必要欄位：{', '.join(missing_fields)}"

        return True, ""

    # ===== 清理和維護 =====

    async def cleanup_old_records(self, days: int = 90, date_field: str = "created_at") -> int:
        """清理舊記錄"""
        if not self.table_name:
            return 0

        await self._ensure_initialized()

        try:
            cutoff_date = datetime.now(timezone.utc) - timedelta(days=days)
            query = f"DELETE FROM {self.table_name} WHERE {date_field} < %s"

            return await self.execute_query(query, (cutoff_date,))

        except Exception as e:
            logger.error(f"[{self.__class__.__name__}] 清理舊記錄失敗：{e}")
            return 0

    # ===== 健康檢查 =====

    async def health_check(self) -> Dict[str, Any]:
        """DAO 健康檢查"""
        try:
            await self._ensure_initialized()

            # 基本連接測試
            test_query = "SELECT 1"
            await self.execute_query(test_query, fetch_one=True)

            # 表格檢查
            table_exists = False
            if self.table_name:
                exists_query = """
                    SELECT COUNT(*) FROM information_schema.tables
                    WHERE table_schema = DATABASE() AND table_name = %s
                """
                result = await self.execute_query(exists_query, (self.table_name,), fetch_one=True)
                table_exists = result[0] > 0 if result else False

            return {
                "status": "healthy",
                "initialized": self._initialized,
                "table_name": self.table_name,
                "table_exists": table_exists,
                "cache_size": len(self._cache),
            }

        except Exception as e:
            logger.error(f"[{self.__class__.__name__}] 健康檢查失敗：{e}")
            return {
                "status": "unhealthy",
                "error": str(e),
                "initialized": self._initialized,
            }


# ===== DAO 工廠類別 =====


class DAOFactory:
    """DAO 工廠類別 - 管理所有 DAO 實例"""

    _instances = {}

    @classmethod
    def get_dao(cls, dao_class: type) -> BaseDAO:
        """取得 DAO 實例（單例模式）"""
        dao_name = dao_class.__name__

        if dao_name not in cls._instances:
            cls._instances[dao_name] = dao_class()

        return cls._instances[dao_name]

    @classmethod
    def get_all_daos(cls) -> Dict[str, BaseDAO]:
        """取得所有 DAO 實例"""
        return cls._instances.copy()

    @classmethod
    async def health_check_all(cls) -> Dict[str, Dict[str, Any]]:
        """檢查所有 DAO 的健康狀態"""
        results = {}

        for dao_name, dao_instance in cls._instances.items():
            results[dao_name] = await dao_instance.health_check()

        return results

    @classmethod
    def clear_all_caches(cls):
        """清除所有 DAO 的快取"""
        for dao_instance in cls._instances.values():
            dao_instance._clear_cache()


# ===== 資料庫遷移基底類別 =====


class BaseMigration(ABC):
    """資料庫遷移基底類別"""

    def __init__(self, version: str, description: str):
        self.version = version
        self.description = description
        self.db = db_pool

    @abstractmethod
    async def up(self) -> bool:
        """執行遷移"""

    @abstractmethod
    async def down(self) -> bool:
        """回滾遷移"""

    async def execute_sql(self, sql: str, params: Tuple = None) -> bool:
        """執行 SQL"""
        try:
            async with self.db.connection() as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute(sql, params or ())
                    await conn.commit()
            return True
        except Exception as e:
            logger.error(f"遷移 SQL 執行失敗：{e}")
            return False


# ===== 錯誤處理裝飾器 =====


def dao_error_handler(default_return=None):
    """DAO 錯誤處理裝飾器"""

    def decorator(func):
        async def wrapper(*args, **kwargs):
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                logger.error(f"DAO 操作 {func.__name__} 失敗：{e}")
                return default_return

        return wrapper

    return decorator


# ===== 效能監控裝飾器 =====


def dao_performance_monitor(func):
    """DAO 效能監控裝飾器"""

    async def wrapper(*args, **kwargs):
        start_time = datetime.now()
        try:
            result = await func(*args, **kwargs)
            execution_time = (datetime.now() - start_time).total_seconds()

            if execution_time > 1.0:  # 超過1秒記錄警告
                logger.warning(f"DAO 操作 {func.__name__} 執行時間過長：{execution_time:.2f}秒")

            return result
        except Exception as e:
            execution_time = (datetime.now() - start_time).total_seconds()
            logger.error(f"DAO 操作 {func.__name__} 失敗（執行時間：{execution_time:.2f}秒）：{e}")
            raise

    return wrapper
