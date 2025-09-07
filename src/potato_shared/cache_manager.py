# shared/cache_manager.py - Redis 多層快取管理系統
"""
企業級 Redis 快取管理系統 v2.2.0
功能特點：
1. 多層快取策略（L1: 記憶體，L2: Redis，L3: 資料庫）
2. 智能失效機制
3. 快取統計和監控
4. 自動預熱和清理
5. 分散式快取同步
"""

import asyncio
import hashlib
import json
import pickle
import time
from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable, Dict, List

try:
    import redis.asyncio as redis

    REDIS_AVAILABLE = True
    REDIS_TYPE = "redis-py"
    aioredis = redis  # 為了向後相容
except ImportError:
    try:
        import aioredis

        REDIS_AVAILABLE = True
        REDIS_TYPE = "aioredis"
        redis = aioredis  # 為了向後相容
    except ImportError:
        REDIS_AVAILABLE = False
        REDIS_TYPE = None
        redis = None
        aioredis = None

from src.potato_shared.logger import logger


class CacheLevel(Enum):
    """快取層級"""

    L1_MEMORY = "l1_memory"  # 本地記憶體快取
    L2_REDIS = "l2_redis"  # Redis 快取
    L3_DATABASE = "l3_database"  # 資料庫（最終數據源）


class CacheStrategy(Enum):
    """快取策略"""

    WRITE_THROUGH = "write_through"  # 寫入時同時更新快取
    WRITE_BACK = "write_back"  # 寫入時只更新快取，定期回寫
    WRITE_AROUND = "write_around"  # 寫入時跳過快取


@dataclass
class CacheConfig:
    """快取配置"""

    # L1 記憶體快取配置
    l1_max_size: int = 1000  # 最大條目數
    l1_ttl: int = 300  # 存活時間（秒）

    # L2 Redis 快取配置
    l2_ttl: int = 3600  # 存活時間（秒）
    l2_max_memory: str = "100mb"  # 最大記憶體使用

    # 其他配置
    enable_compression: bool = True  # 啟用壓縮
    enable_statistics: bool = True  # 啟用統計
    auto_preload: bool = False  # 自動預載熱點數據

    # 分散式配置
    enable_distributed_invalidation: bool = True  # 分散式失效通知


@dataclass
class CacheEntry:
    """快取條目"""

    key: str
    value: Any
    timestamp: float
    ttl: int
    access_count: int = 0
    last_access: float = 0


@dataclass
class CacheStatistics:
    """快取統計"""

    l1_hits: int = 0
    l1_misses: int = 0
    l2_hits: int = 0
    l2_misses: int = 0
    total_requests: int = 0
    total_sets: int = 0
    total_deletes: int = 0

    def hit_rate(self) -> float:
        """總命中率"""
        total_hits = self.l1_hits + self.l2_hits
        if self.total_requests == 0:
            return 0.0
        return total_hits / self.total_requests

    def l1_hit_rate(self) -> float:
        """L1 命中率"""
        l1_total = self.l1_hits + self.l1_misses
        if l1_total == 0:
            return 0.0
        return self.l1_hits / l1_total

    def l2_hit_rate(self) -> float:
        """L2 命中率"""
        l2_total = self.l2_hits + self.l2_misses
        if l2_total == 0:
            return 0.0
        return self.l2_hits / l2_total


class MultiLevelCacheManager:
    """多層快取管理器"""

    def __init__(self, redis_url: str = None, config: CacheConfig = None):
        self.redis_url = redis_url or "redis://localhost:6379"
        self.config = config or CacheConfig()
        self.redis = None
        self.is_connected = False

        # L1 記憶體快取 (LRU)
        self._l1_cache: Dict[str, CacheEntry] = {}
        self._l1_access_order: List[str] = []

        # 統計數據
        self.stats = CacheStatistics()

        # 鎖對象
        self._locks: Dict[str, asyncio.Lock] = {}
        self._global_lock = asyncio.Lock()

        # 預載和清理任務
        self._preload_task = None
        self._cleanup_task = None

        # 分散式失效通知
        self._invalidation_subscriber = None

        logger.info(f"🔧 快取管理器初始化 - Redis: {REDIS_AVAILABLE}")

    async def initialize(self):
        """初始化快取系統"""
        try:
            # 連接 Redis
            if REDIS_AVAILABLE:
                await self._connect_redis()

            # 啟動背景任務
            await self._start_background_tasks()

            logger.info("✅ 多層快取系統初始化完成")

        except Exception as e:
            logger.error(f"❌ 快取系統初始化失敗: {e}")
            raise

    async def _connect_redis(self):
        """連接 Redis"""
        try:
            if REDIS_TYPE == "aioredis":
                self.redis = await aioredis.from_url(
                    self.redis_url,
                    decode_responses=True,
                    socket_connect_timeout=5,
                    socket_timeout=5,
                )
            elif REDIS_TYPE == "redis-py":
                self.redis = await aioredis.from_url(self.redis_url, decode_responses=True)

            # 測試連接
            await self.redis.ping()
            self.is_connected = True
            logger.info(f"✅ Redis 連接成功 ({REDIS_TYPE})")

            # 設置 Redis 配置
            await self._configure_redis()

        except Exception as e:
            logger.warning(f"⚠️ Redis 連接失敗，將使用本機模式: {e}")
            self.redis = None
            self.is_connected = False

    async def _configure_redis(self):
        """配置 Redis"""
        if not self.redis:
            return

        try:
            # 設置最大記憶體
            await self.redis.config_set("maxmemory", self.config.l2_max_memory)
            await self.redis.config_set("maxmemory-policy", "allkeys-lru")

            # 啟用 RDB 快照
            await self.redis.config_set("save", "900 1 300 10 60 10000")

            logger.info("✅ Redis 配置完成")

        except Exception as e:
            logger.warning(f"⚠️ Redis 配置失敗: {e}")

    async def _start_background_tasks(self):
        """啟動背景任務"""
        # L1 快取清理任務
        self._cleanup_task = asyncio.create_task(self._cleanup_l1_cache())

        # 統計數據定期報告
        if self.config.enable_statistics:
            asyncio.create_task(self._periodic_statistics_report())

        # 分散式失效通知訂閱
        if self.config.enable_distributed_invalidation and self.redis:
            asyncio.create_task(self._start_invalidation_subscriber())

    async def get(self, key: str, default: Any = None) -> Any:
        """多層快取讀取"""
        self.stats.total_requests += 1
        start_time = time.time()

        try:
            # 1. 嘗試 L1 記憶體快取
            value = await self._get_from_l1(key)
            if value is not None:
                self.stats.l1_hits += 1
                logger.debug(f"🎯 L1 快取命中: {key}")
                return value
            else:
                self.stats.l1_misses += 1

            # 2. 嘗試 L2 Redis 快取
            if self.redis:
                value = await self._get_from_l2(key)
                if value is not None:
                    self.stats.l2_hits += 1
                    logger.debug(f"🎯 L2 快取命中: {key}")

                    # 回填 L1 快取
                    await self._set_to_l1(key, value, self.config.l1_ttl)
                    return value
                else:
                    self.stats.l2_misses += 1

            # 3. 快取未命中，返回預設值
            logger.debug(f"💨 快取未命中: {key}")
            return default

        except Exception as e:
            logger.error(f"❌ 讀取快取失敗 {key}: {e}")
            return default
        finally:
            duration = time.time() - start_time
            if duration > 0.1:  # 如果超過100ms，記錄警告
                logger.warning(f"⚠️ 快取讀取耗時過長: {key} - {duration:.3f}s")

    async def set(
        self,
        key: str,
        value: Any,
        ttl: int = None,
        strategy: CacheStrategy = CacheStrategy.WRITE_THROUGH,
    ) -> bool:
        """多層快取寫入"""
        self.stats.total_sets += 1
        start_time = time.time()

        try:
            ttl = ttl or self.config.l1_ttl

            if strategy == CacheStrategy.WRITE_THROUGH:
                # 同時寫入所有層級
                success_l1 = await self._set_to_l1(key, value, ttl)
                success_l2 = True

                if self.redis:
                    success_l2 = await self._set_to_l2(key, value, ttl)

                # 發送分散式失效通知
                if self.config.enable_distributed_invalidation:
                    await self._notify_invalidation(key, "update")

                return success_l1 and success_l2

            elif strategy == CacheStrategy.WRITE_BACK:
                # 只寫入 L1，標記為髒數據
                await self._set_to_l1(key, value, ttl, dirty=True)
                return True

            elif strategy == CacheStrategy.WRITE_AROUND:
                # 只寫入 L2
                if self.redis:
                    return await self._set_to_l2(key, value, ttl)
                return False

        except Exception as e:
            logger.error(f"❌ 寫入快取失敗 {key}: {e}")
            return False
        finally:
            duration = time.time() - start_time
            if duration > 0.05:  # 如果超過50ms，記錄警告
                logger.warning(f"⚠️ 快取寫入耗時過長: {key} - {duration:.3f}s")

    async def delete(self, key: str) -> bool:
        """刪除快取"""
        self.stats.total_deletes += 1

        try:
            # 從所有層級刪除
            success_l1 = await self._delete_from_l1(key)
            success_l2 = True

            if self.redis:
                success_l2 = await self._delete_from_l2(key)

            # 發送分散式失效通知
            if self.config.enable_distributed_invalidation:
                await self._notify_invalidation(key, "delete")

            return success_l1 or success_l2

        except Exception as e:
            logger.error(f"❌ 刪除快取失敗 {key}: {e}")
            return False

    async def clear_all(self, pattern: str = "*") -> int:
        """清空快取"""
        count = 0

        try:
            # 清空 L1
            if pattern == "*":
                count += len(self._l1_cache)
                self._l1_cache.clear()
                self._l1_access_order.clear()
            else:
                # 支援模式匹配
                keys_to_delete = [
                    k for k in self._l1_cache.keys() if self._match_pattern(k, pattern)
                ]
                for key in keys_to_delete:
                    await self._delete_from_l1(key)
                count += len(keys_to_delete)

            # 清空 L2
            if self.redis:
                if pattern == "*":
                    await self.redis.flushdb()
                else:
                    keys = await self.redis.keys(pattern)
                    if keys:
                        await self.redis.delete(*keys)
                        count += len(keys)

            logger.info(f"✅ 清空快取完成，共清理 {count} 個條目")
            return count

        except Exception as e:
            logger.error(f"❌ 清空快取失敗: {e}")
            return 0

    async def get_statistics(self) -> Dict[str, Any]:
        """獲取快取統計"""
        stats = {
            "requests": {
                "total": self.stats.total_requests,
                "hits": self.stats.l1_hits + self.stats.l2_hits,
                "misses": self.stats.l1_misses + self.stats.l2_misses,
                "hit_rate": f"{self.stats.hit_rate():.2%}",
            },
            "l1_memory": {
                "size": len(self._l1_cache),
                "max_size": self.config.l1_max_size,
                "usage": f"{len(self._l1_cache)/self.config.l1_max_size:.1%}",
                "hits": self.stats.l1_hits,
                "misses": self.stats.l1_misses,
                "hit_rate": f"{self.stats.l1_hit_rate():.2%}",
            },
            "l2_redis": {
                "connected": self.is_connected,
                "hits": self.stats.l2_hits,
                "misses": self.stats.l2_misses,
                "hit_rate": f"{self.stats.l2_hit_rate():.2%}",
            },
            "operations": {
                "sets": self.stats.total_sets,
                "deletes": self.stats.total_deletes,
            },
        }

        # 添加 Redis 詳細資訊
        if self.redis:
            try:
                info = await self.redis.info()
                stats["l2_redis"].update(
                    {
                        "memory_used": info.get("used_memory_human", "N/A"),
                        "keys": info.get("db0", {}).get("keys", 0),
                        "connections": info.get("connected_clients", 0),
                    }
                )
            except Exception as e:
                logger.warning(f"⚠️ 無法獲取 Redis 資訊: {e}")

        return stats

    # ========== L1 記憶體快取操作 ==========

    async def _get_from_l1(self, key: str) -> Any:
        """從 L1 快取讀取"""
        async with self._global_lock:
            entry = self._l1_cache.get(key)
            if not entry:
                return None

            # 檢查是否過期
            if time.time() - entry.timestamp > entry.ttl:
                del self._l1_cache[key]
                if key in self._l1_access_order:
                    self._l1_access_order.remove(key)
                return None

            # 更新存取紀錄
            entry.access_count += 1
            entry.last_access = time.time()

            # 更新 LRU 順序
            if key in self._l1_access_order:
                self._l1_access_order.remove(key)
            self._l1_access_order.append(key)

            return entry.value

    async def _set_to_l1(self, key: str, value: Any, ttl: int, dirty: bool = False) -> bool:
        """寫入 L1 快取"""
        async with self._global_lock:
            # 檢查容量限制
            if len(self._l1_cache) >= self.config.l1_max_size and key not in self._l1_cache:
                # LRU 淘汰
                if self._l1_access_order:
                    oldest_key = self._l1_access_order.pop(0)
                    del self._l1_cache[oldest_key]

            # 創建快取條目
            entry = CacheEntry(
                key=key,
                value=value,
                timestamp=time.time(),
                ttl=ttl,
                access_count=1,
                last_access=time.time(),
            )

            self._l1_cache[key] = entry

            # 更新存取順序
            if key in self._l1_access_order:
                self._l1_access_order.remove(key)
            self._l1_access_order.append(key)

            return True

    async def _delete_from_l1(self, key: str) -> bool:
        """從 L1 快取刪除"""
        async with self._global_lock:
            if key in self._l1_cache:
                del self._l1_cache[key]
                if key in self._l1_access_order:
                    self._l1_access_order.remove(key)
                return True
            return False

    # ========== L2 Redis 快取操作 ==========

    async def _get_from_l2(self, key: str) -> Any:
        """從 L2 快取讀取"""
        if not self.redis:
            return None

        try:
            data = await self.redis.get(f"cache:{key}")
            if data:
                if self.config.enable_compression:
                    # 使用 JSON 代替 pickle 以提高安全性
                    import base64
                    import gzip

                    try:
                        compressed_data = base64.b64decode(data.encode("latin-1"))
                        decompressed_data = gzip.decompress(compressed_data)
                        return json.loads(decompressed_data.decode("utf-8"))
                    except Exception:
                        # 回退到 JSON（為了兼容性）
                        return json.loads(data)
                else:
                    return json.loads(data)
            return None
        except Exception as e:
            logger.error(f"❌ L2 讀取失敗 {key}: {e}")
            return None

    async def _set_to_l2(self, key: str, value: Any, ttl: int) -> bool:
        """寫入 L2 快取"""
        if not self.redis:
            return False

        try:
            if self.config.enable_compression:
                data = pickle.dumps(value).decode("latin-1")
            else:
                data = json.dumps(value, ensure_ascii=False)

            await self.redis.setex(f"cache:{key}", ttl, data)
            return True
        except Exception as e:
            logger.error(f"❌ L2 寫入失敗 {key}: {e}")
            return False

    async def _delete_from_l2(self, key: str) -> bool:
        """從 L2 快取刪除"""
        if not self.redis:
            return False

        try:
            result = await self.redis.delete(f"cache:{key}")
            return result > 0
        except Exception as e:
            logger.error(f"❌ L2 刪除失敗 {key}: {e}")
            return False

    # ========== 背景任務 ==========

    async def _cleanup_l1_cache(self):
        """L1 快取清理任務"""
        while True:
            try:
                await asyncio.sleep(60)  # 每分鐘執行一次

                current_time = time.time()
                expired_keys = []

                async with self._global_lock:
                    for key, entry in self._l1_cache.items():
                        if current_time - entry.timestamp > entry.ttl:
                            expired_keys.append(key)

                # 清理過期條目
                for key in expired_keys:
                    await self._delete_from_l1(key)

                if expired_keys:
                    logger.debug(f"🧹 L1 快取清理完成，移除 {len(expired_keys)} 個過期條目")

            except Exception as e:
                logger.error(f"❌ L1 快取清理失敗: {e}")

    async def _periodic_statistics_report(self):
        """定期統計報告"""
        while True:
            try:
                await asyncio.sleep(300)  # 每5分鐘報告一次

                stats = await self.get_statistics()
                logger.info(
                    f"📊 快取統計 - 總命中率: {stats['requests']['hit_rate']}, "
                    f"L1: {stats['l1_memory']['hit_rate']}, "
                    f"L2: {stats['l2_redis']['hit_rate']}"
                )

            except Exception as e:
                logger.error(f"❌ 統計報告失敗: {e}")

    async def _notify_invalidation(self, key: str, action: str):
        """發送分散式失效通知"""
        if not self.redis:
            return

        try:
            message = json.dumps(
                {
                    "key": key,
                    "action": action,
                    "timestamp": time.time(),
                    "source": "cache_manager",
                }
            )

            await self.redis.publish("cache:invalidation", message)

        except Exception as e:
            logger.error(f"❌ 發送失效通知失敗: {e}")

    async def _start_invalidation_subscriber(self):
        """啟動分散式失效通知訂閱"""
        if not self.redis:
            return

        try:
            pubsub = self.redis.pubsub()
            await pubsub.subscribe("cache:invalidation")

            async for message in pubsub.listen():
                if message["type"] == "message":
                    try:
                        data = json.loads(message["data"])
                        key = data["key"]
                        action = data["action"]

                        # 處理失效通知
                        if action == "delete":
                            await self._delete_from_l1(key)
                        elif action == "update":
                            # 更新通知：從 L1 移除讓其重新載入
                            await self._delete_from_l1(key)

                    except Exception as e:
                        logger.error(f"❌ 處理失效通知失敗: {e}")

        except Exception as e:
            logger.error(f"❌ 失效通知訂閱失敗: {e}")

    @staticmethod
    def _match_pattern(text: str, pattern: str) -> bool:
        """簡單的模式匹配"""
        import fnmatch

        return fnmatch.fnmatch(text, pattern)

    async def close(self):
        """關閉快取管理器"""
        try:
            # 取消背景任務
            if self._cleanup_task:
                self._cleanup_task.cancel()
            if self._preload_task:
                self._preload_task.cancel()

            # 關閉 Redis 連接
            if self.redis:
                await self.redis.close()

            logger.info("✅ 快取管理器已關閉")

        except Exception as e:
            logger.error(f"❌ 關閉快取管理器失敗: {e}")


# ========== 全域實例和便捷函數 ==========

# 全域快取管理器實例
cache_manager = MultiLevelCacheManager()


async def init_cache(redis_url: str = None, config: CacheConfig = None):
    """初始化全域快取管理器"""
    global cache_manager
    cache_manager = MultiLevelCacheManager(redis_url, config)
    await cache_manager.initialize()


async def get_cache_manager() -> MultiLevelCacheManager:
    """獲取快取管理器實例"""
    return cache_manager


# 便捷的快取裝飾器
def cached(
    key_prefix: str = "",
    ttl: int = 300,
    strategy: CacheStrategy = CacheStrategy.WRITE_THROUGH,
):
    """快取裝飾器"""

    def decorator(func: Callable):
        async def wrapper(*args, **kwargs):
            # 生成快取鍵
            key_parts = [key_prefix, func.__name__]

            # 添加參數到鍵中
            if args:
                key_parts.extend(str(arg) for arg in args[:3])  # 只取前3個參數
            if kwargs:
                key_parts.extend(f"{k}={v}" for k, v in list(kwargs.items())[:3])

            cache_key = ":".join(filter(None, key_parts))
            cache_key = hashlib.sha256(cache_key.encode()).hexdigest()[:16]  # 使用 SHA256 代替 MD5

            # 嘗試從快取讀取
            result = await cache_manager.get(cache_key)
            if result is not None:
                return result

            # 執行函數並快取結果
            result = await func(*args, **kwargs)
            if result is not None:
                await cache_manager.set(cache_key, result, ttl, strategy)

            return result

        return wrapper

    return decorator


# 批量操作支援
async def mget(keys: List[str]) -> Dict[str, Any]:
    """批量獲取"""
    results = {}
    for key in keys:
        results[key] = await cache_manager.get(key)
    return results


async def mset(data: Dict[str, Any], ttl: int = 300) -> int:
    """批量設置"""
    success_count = 0
    for key, value in data.items():
        if await cache_manager.set(key, value, ttl):
            success_count += 1
    return success_count
