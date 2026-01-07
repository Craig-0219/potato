# shared/cache_manager.py - 精簡版（僅保留 L1 記憶體快取）
"""
單層 L1 記憶體快取管理器
Redis 相關功能已完全移除
"""

import asyncio
import hashlib
import json
import time
from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable, Dict, List

from potato_shared.logger import logger


class CacheStrategy(Enum):
    """快取策略（目前僅影響語義）"""

    WRITE_THROUGH = "write_through"
    WRITE_BACK = "write_back"
    WRITE_AROUND = "write_around"


@dataclass
class CacheConfig:
    """快取配置"""

    l1_max_size: int = 1000  # 最大條目數
    l1_ttl: int = 300  # 秒
    enable_statistics: bool = True


@dataclass
class CacheEntry:
    key: str
    value: Any
    timestamp: float
    ttl: int
    access_count: int = 0
    last_access: float = 0.0


@dataclass
class CacheStatistics:
    l1_hits: int = 0
    l1_misses: int = 0
    total_requests: int = 0
    total_sets: int = 0
    total_deletes: int = 0

    def hit_rate(self) -> float:
        total_hits = self.l1_hits
        if self.total_requests == 0:
            return 0.0
        return total_hits / self.total_requests

    def l1_hit_rate(self) -> float:
        total = self.l1_hits + self.l1_misses
        if total == 0:
            return 0.0
        return self.l1_hits / total


class MultiLevelCacheManager:
    """單層 L1 快取管理器（保留原介面）"""

    def __init__(self, config: CacheConfig = None):
        self.config = config or CacheConfig()
        self._l1_cache: Dict[str, CacheEntry] = {}
        self._l1_access_order: List[str] = []
        self.stats = CacheStatistics()

        self._locks: Dict[str, asyncio.Lock] = {}
        self._global_lock = asyncio.Lock()

        self._preload_task = None
        self._cleanup_task = None

        logger.info("🔧 快取管理器初始化（僅 L1 記憶體）")

    async def initialize(self):
        """啟動背景任務"""
        try:
            await self._start_background_tasks()
            logger.info("✅ 快取系統初始化完成")
        except Exception as e:
            logger.error(f"❌ 快取系統初始化失敗: {e}")
            raise

    async def _start_background_tasks(self):
        """啟動背景任務"""
        self._cleanup_task = asyncio.create_task(self._cleanup_l1_cache())
        if self.config.enable_statistics:
            asyncio.create_task(self._periodic_statistics_report())

    async def get(self, key: str, default: Any = None) -> Any:
        """讀取快取"""
        self.stats.total_requests += 1
        start = time.time()
        try:
            value = await self._get_from_l1(key)
            if value is not None:
                self.stats.l1_hits += 1
                return value

            self.stats.l1_misses += 1
            return default
        except Exception as e:
            logger.error(f"❌ 讀取快取失敗 {key}: {e}")
            return default
        finally:
            duration = time.time() - start
            if duration > 0.1:
                logger.warning(f"⚠️ 快取讀取耗時過長: {key} - {duration:.3f}s")

    async def set(
        self,
        key: str,
        value: Any,
        ttl: int = None,
        strategy: CacheStrategy = CacheStrategy.WRITE_THROUGH,
    ) -> bool:
        """寫入快取（策略僅保留兼容性）"""
        self.stats.total_sets += 1
        start = time.time()
        try:
            ttl = ttl or self.config.l1_ttl

            if strategy == CacheStrategy.WRITE_AROUND:
                # 已無 L2，直接返回 False
                return False

            await self._set_to_l1(key, value, ttl)
            return True
        except Exception as e:
            logger.error(f"❌ 寫入快取失敗 {key}: {e}")
            return False
        finally:
            duration = time.time() - start
            if duration > 0.05:
                logger.warning(f"⚠️ 快取寫入耗時過長: {key} - {duration:.3f}s")

    async def delete(self, key: str) -> bool:
        """刪除快取"""
        self.stats.total_deletes += 1
        try:
            return await self._delete_from_l1(key)
        except Exception as e:
            logger.error(f"❌ 刪除快取失敗 {key}: {e}")
            return False

    async def clear_all(self, pattern: str = "*") -> int:
        """清空快取（支援模式匹配）"""
        count = 0
        try:
            if pattern == "*":
                count = len(self._l1_cache)
                self._l1_cache.clear()
                self._l1_access_order.clear()
            else:
                keys_to_delete = [k for k in self._l1_cache if self._match_pattern(k, pattern)]
                for key in keys_to_delete:
                    await self._delete_from_l1(key)
                count = len(keys_to_delete)

            logger.info(f"✅ 清空快取完成，共清理 {count} 個條目")
            return count
        except Exception as e:
            logger.error(f"❌ 清空快取失敗: {e}")
            return 0

    async def get_statistics(self) -> Dict[str, Any]:
        """取得快取統計（僅 L1）"""
        return {
            "requests": {
                "total": self.stats.total_requests,
                "hits": self.stats.l1_hits,
                "misses": self.stats.l1_misses,
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
            "operations": {
                "sets": self.stats.total_sets,
                "deletes": self.stats.total_deletes,
            },
        }

    # ===== L1 操作 =====
    async def _get_from_l1(self, key: str) -> Any:
        async with self._global_lock:
            entry = self._l1_cache.get(key)
            if not entry:
                return None
            if time.time() - entry.timestamp > entry.ttl:
                del self._l1_cache[key]
                if key in self._l1_access_order:
                    self._l1_access_order.remove(key)
                return None
            entry.access_count += 1
            entry.last_access = time.time()
            if key in self._l1_access_order:
                self._l1_access_order.remove(key)
            self._l1_access_order.append(key)
            return entry.value

    async def _set_to_l1(self, key: str, value: Any, ttl: int) -> bool:
        async with self._global_lock:
            if len(self._l1_cache) >= self.config.l1_max_size and key not in self._l1_cache:
                if self._l1_access_order:
                    oldest = self._l1_access_order.pop(0)
                    self._l1_cache.pop(oldest, None)

            entry = CacheEntry(
                key=key,
                value=value,
                timestamp=time.time(),
                ttl=ttl,
                access_count=1,
                last_access=time.time(),
            )
            self._l1_cache[key] = entry
            if key in self._l1_access_order:
                self._l1_access_order.remove(key)
            self._l1_access_order.append(key)
            return True

    async def _delete_from_l1(self, key: str) -> bool:
        async with self._global_lock:
            if key in self._l1_cache:
                del self._l1_cache[key]
                if key in self._l1_access_order:
                    self._l1_access_order.remove(key)
                return True
            return False

    # ===== 背景任務 =====
    async def _cleanup_l1_cache(self):
        while True:
            try:
                await asyncio.sleep(60)
                current = time.time()
                expired = []
                async with self._global_lock:
                    for key, entry in list(self._l1_cache.items()):
                        if current - entry.timestamp > entry.ttl:
                            expired.append(key)
                for key in expired:
                    await self._delete_from_l1(key)
                if expired:
                    logger.debug(f"🧹 L1 快取清理完成，移除 {len(expired)} 個過期條目")
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"❌ L1 快取清理失敗: {e}")

    async def _periodic_statistics_report(self):
        while True:
            try:
                await asyncio.sleep(300)
                stats = await self.get_statistics()
                logger.info(
                    f"📊 快取統計 - 總命中率: {stats['requests']['hit_rate']}, "
                    f"L1: {stats['l1_memory']['hit_rate']}"
                )
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"❌ 統計報告失敗: {e}")

    @staticmethod
    def _match_pattern(text: str, pattern: str) -> bool:
        import fnmatch

        return fnmatch.fnmatch(text, pattern)

    async def close(self):
        """關閉管理器"""
        try:
            if self._cleanup_task:
                self._cleanup_task.cancel()
            if self._preload_task:
                self._preload_task.cancel()
            logger.info("✅ 快取管理器已關閉")
        except Exception as e:
            logger.error(f"❌ 關閉快取管理器失敗: {e}")


# 全域實例與便捷函式
cache_manager = MultiLevelCacheManager()


async def init_cache(config: CacheConfig = None):
    global cache_manager
    cache_manager = MultiLevelCacheManager(config)
    await cache_manager.initialize()


async def get_cache_manager() -> MultiLevelCacheManager:
    return cache_manager


def cached(
    key_prefix: str = "",
    ttl: int = 300,
    strategy: CacheStrategy = CacheStrategy.WRITE_THROUGH,
):
    """簡易快取裝飾器"""

    def decorator(func: Callable):
        async def wrapper(*args, **kwargs):
            key_parts = [key_prefix, func.__name__]
            if args:
                key_parts.extend(str(arg) for arg in args[:3])
            if kwargs:
                key_parts.extend(f"{k}={v}" for k, v in list(kwargs.items())[:3])

            cache_key = ":".join(filter(None, key_parts))
            cache_key = hashlib.sha256(cache_key.encode()).hexdigest()[:16]

            result = await cache_manager.get(cache_key)
            if result is not None:
                return result

            result = await func(*args, **kwargs)
            if result is not None:
                await cache_manager.set(cache_key, result, ttl, strategy)
            return result

        return wrapper

    return decorator


async def mget(keys: List[str]) -> Dict[str, Any]:
    return {key: await cache_manager.get(key) for key in keys}


async def mset(data: Dict[str, Any], ttl: int = 300) -> int:
    count = 0
    for key, value in data.items():
        if await cache_manager.set(key, value, ttl):
            count += 1
    return count

