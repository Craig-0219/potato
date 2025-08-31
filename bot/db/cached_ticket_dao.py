# bot/db/cached_ticket_dao.py - 快取優化的票券 DAO
"""
整合多層快取的票券資料存取層 v2.2.0
功能特點：
1. 智能快取策略
2. 查詢結果快取
3. 熱點數據預載
4. 快取失效同步
5. 性能監控整合
"""

import asyncio
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from bot.db.ticket_dao import TicketDAO
from shared.cache_manager import CacheStrategy, cache_manager, cached
from shared.logger import logger


class CachedTicketDAO:
    """快取優化的票券 DAO"""

    def __init__(self):
        self.ticket_dao = TicketDAO()
        self.cache = cache_manager

        # 快取配置
        self.DEFAULT_TTL = 300  # 5分鐘
        self.STATS_TTL = 60  # 統計數據1分鐘
        self.LIST_TTL = 180  # 列表數據3分鐘
        self.DETAIL_TTL = 600  # 詳細數據10分鐘

        logger.info("🚀 快取優化票券 DAO 初始化完成")

    async def initialize(self):
        """初始化"""
        await self.ticket_dao._ensure_initialized()

        # 預載熱點數據
        asyncio.create_task(self._preload_hot_data())

    # ========== 快取優化的基礎 CRUD 操作 ==========

    @cached("ticket", ttl=600, strategy=CacheStrategy.WRITE_THROUGH)
    async def get_ticket(self, ticket_id: int) -> Optional[Dict]:
        """獲取票券詳情（帶快取）"""
        try:
            ticket = await self.ticket_dao.get_ticket(ticket_id)

            if ticket:
                # 記錄存取，用於熱點分析
                await self._record_access(f"ticket:{ticket_id}")

                # 預載相關數據
                asyncio.create_task(self._preload_related_data(ticket))

            return ticket

        except Exception as e:
            logger.error(f"❌ 獲取票券失敗 {ticket_id}: {e}")
            # 快取穿透保護：快取空結果短時間
            await self.cache.set(f"ticket:empty:{ticket_id}", None, 60)
            return None

    async def create_ticket(self, ticket_data: Dict) -> Optional[int]:
        """創建票券（帶快取失效）"""
        try:
            # 創建票券
            ticket_id = await self.ticket_dao.create_ticket(ticket_data)

            if ticket_id:
                # 失效相關快取
                await self._invalidate_related_caches(
                    ticket_data.get("guild_id")
                )

                # 快取新創建的票券
                new_ticket = await self.ticket_dao.get_ticket(ticket_id)
                if new_ticket:
                    cache_key = f"ticket:{ticket_id}"
                    await self.cache.set(
                        cache_key, new_ticket, self.DETAIL_TTL
                    )

            return ticket_id

        except Exception as e:
            logger.error(f"❌ 創建票券失敗: {e}")
            return None

    async def update_ticket(self, ticket_id: int, update_data: Dict) -> bool:
        """更新票券（帶快取同步）"""
        try:
            success = await self.ticket_dao.update_ticket(
                ticket_id, update_data
            )

            if success:
                # 獲取更新後的數據
                updated_ticket = await self.ticket_dao.get_ticket(ticket_id)

                if updated_ticket:
                    # 更新快取
                    cache_key = f"ticket:{ticket_id}"
                    await self.cache.set(
                        cache_key, updated_ticket, self.DETAIL_TTL
                    )

                    # 失效相關快取
                    await self._invalidate_related_caches(
                        updated_ticket.get("guild_id")
                    )

            return success

        except Exception as e:
            logger.error(f"❌ 更新票券失敗 {ticket_id}: {e}")
            return False

    async def delete_ticket(self, ticket_id: int) -> bool:
        """刪除票券（帶快取清理）"""
        try:
            # 先獲取票券資訊用於快取失效
            ticket = await self.ticket_dao.get_ticket(ticket_id)

            success = await self.ticket_dao.delete_ticket(ticket_id)

            if success and ticket:
                # 清理快取
                await self.cache.delete(f"ticket:{ticket_id}")
                await self._invalidate_related_caches(ticket.get("guild_id"))

            return success

        except Exception as e:
            logger.error(f"❌ 刪除票券失敗 {ticket_id}: {e}")
            return False

    # ========== 快取優化的查詢操作 ==========

    async def get_user_tickets(
        self, user_id: int, guild_id: int, status: str = None, limit: int = 50
    ) -> List[Dict]:
        """獲取用戶票券列表（帶快取）"""
        # 生成快取鍵
        cache_key = f"user_tickets:{user_id}:{guild_id}:{status}:{limit}"

        # 嘗試從快取獲取
        cached_result = await self.cache.get(cache_key)
        if cached_result is not None:

            return []

    @cached("guild_tickets", ttl=180)
    async def get_guild_tickets(
        self,
        guild_id: int,
        status: str = None,
        limit: int = 100,
        offset: int = 0,
    ) -> Tuple[List[Dict], int]:
        """獲取伺服器票券列表（帶快取和分頁）"""
        try:
            tickets, total = await self.ticket_dao.get_guild_tickets(
                guild_id, status, limit, offset
            )

            # 快取個別票券
            for ticket in tickets:
                cache_key = f"ticket:{ticket['id']}"
                await self.cache.set(cache_key, ticket, self.DETAIL_TTL)

            return tickets, total

        except Exception as e:
            logger.error(f"❌ 獲取伺服器票券失敗 {guild_id}: {e}")
            return [], 0

    # ========== 快取優化的統計查詢 ==========

    @cached("ticket_stats", ttl=60)
    async def get_ticket_statistics(
        self, guild_id: int, period_days: int = 7
    ) -> Dict[str, Any]:
        """獲取票券統計（帶快取）"""
        try:
            stats = await self.ticket_dao.get_ticket_statistics(
                guild_id, period_days
            )

            # 添加快取資訊到統計中
            cache_stats = await self.cache.get_statistics()
            stats["cache_performance"] = {
                "hit_rate": cache_stats["requests"]["hit_rate"],
                "l1_usage": cache_stats["l1_memory"]["usage"],
                "redis_connected": cache_stats["l2_redis"]["connected"],
            }

            return stats

        except Exception as e:
            logger.error(f"❌ 獲取票券統計失敗 {guild_id}: {e}")
            return {}

    @cached("daily_stats", ttl=3600)  # 每小時更新
    async def get_daily_statistics(
        self, guild_id: int, date: str
    ) -> Dict[str, Any]:
        """獲取每日統計（帶長時間快取）"""
        try:
            return await self.ticket_dao.get_daily_statistics(guild_id, date)
        except Exception as e:
            logger.error(f"❌ 獲取每日統計失敗 {guild_id}, {date}: {e}")
            return {}

    async def get_performance_metrics(self, guild_id: int) -> Dict[str, Any]:
        """獲取性能指標（實時數據，不快取）"""
        try:
            # 組合多個數據源
            db_metrics = await self.ticket_dao.get_performance_metrics(
                guild_id
            )
            cache_stats = await self.cache.get_statistics()

            return {
                "database": db_metrics,
                "cache": cache_stats,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

        except Exception as e:
            logger.error(f"❌ 獲取性能指標失敗: {e}")
            return {}

    # ========== 快取管理操作 ==========

    async def _invalidate_related_caches(self, guild_id: int):
        """失效相關快取"""
        try:
            # 清理伺服器相關快取
            patterns = [
                f"guild_tickets:{guild_id}:*",
                f"ticket_stats:{guild_id}:*",
                f"daily_stats:{guild_id}:*",
                f"user_tickets:*:{guild_id}:*",
            ]

            for pattern in patterns:
                await self.cache.clear_all(pattern)

        except Exception as e:
            logger.error(f"❌ 失效相關快取失敗: {e}")

    async def _preload_hot_data(self):
        """預載熱點數據"""
        try:
            # 預載最近活躍的票券
            recent_tickets = await self.ticket_dao.get_recent_active_tickets(
                limit=50
            )

            for ticket in recent_tickets:
                cache_key = f"ticket:{ticket['id']}"
                await self.cache.set(cache_key, ticket, self.DETAIL_TTL)

            logger.info(f"🔥 預載熱點數據完成: {len(recent_tickets)} 個票券")

        except Exception as e:
            logger.error(f"❌ 預載熱點數據失敗: {e}")

    async def _preload_related_data(self, ticket: Dict):
        """預載相關數據"""
        try:
            # 預載同用戶的其他票券
            user_id = ticket.get("user_id")
            guild_id = ticket.get("guild_id")

            if user_id and guild_id:
                asyncio.create_task(
                    self.get_user_tickets(user_id, guild_id, limit=10)
                )

        except Exception as e:
            logger.error(f"❌ 紀錄熱點數據失敗: {e}")

    async def _record_access(self, cache_key: str):
        """記錄存取，用於熱點分析"""
        try:
            access_key = f"access_count:{cache_key}"
            current_count = await self.cache.get(access_key) or 0
            await self.cache.set(
                access_key, current_count + 1, 3600
            )  # 1小時統計

        except Exception as e:
            logger.error(f"❌ 記錄訪問統計失敗: {e}")

    # ========== 批量操作優化 ==========

    async def get_tickets_batch(
        self, ticket_ids: List[int]
    ) -> Dict[int, Optional[Dict]]:
        """批量獲取票券（快取優化）"""
        results = {}
        cache_misses = []

        # 先從快取獲取
        for ticket_id in ticket_ids:
            cache_key = f"ticket:{ticket_id}"
            cached_ticket = await self.cache.get(cache_key)

            if cached_ticket is not None:
                results[ticket_id] = cached_ticket
            else:
                cache_misses.append(ticket_id)

        # 批量查詢未命中的數據
        if cache_misses:
            try:
                db_results = await self.ticket_dao.get_tickets_batch(
                    cache_misses
                )

                # 更新快取並添加到結果
                for ticket_id, ticket_data in db_results.items():
                    results[ticket_id] = ticket_data

                    if ticket_data:  # 只快取有效數據
                        cache_key = f"ticket:{ticket_id}"
                        await self.cache.set(
                            cache_key, ticket_data, self.DETAIL_TTL
                        )

            except Exception as e:
                logger.error(f"❌ 批量查詢失敗: {e}")
                # 將未查詢到的設置為 None
                for ticket_id in cache_misses:
                    if ticket_id not in results:
                        results[ticket_id] = None

        return results

    def _get_cache_recommendations(self, stats: Dict) -> List[str]:
        """生成快取優化建議"""
        recommendations = []

        hit_rate = float(stats["requests"]["hit_rate"].rstrip("%")) / 100

        if hit_rate < 0.6:
            recommendations.append("考慮增加快取 TTL 時間")

        if not stats["l2_redis"]["connected"]:
            recommendations.append("建議啟用 Redis 以提升性能")

        l1_usage = float(stats["l1_memory"]["usage"].rstrip("%")) / 100
        if l1_usage > 0.9:
            recommendations.append("L1 記憶體快取接近滿載，考慮增加容量")

        if len(recommendations) == 0:
            recommendations.append("快取性能良好，無需調整")

        return recommendations

    async def warm_cache(self, guild_id: int):
        """手動預熱快取"""
        try:
            logger.info(f"🔥 開始預熱快取: {guild_id}")

            # 預熱活躍票券
            active_tickets, _ = await self.get_guild_tickets(
                guild_id, "open", limit=20
            )
            logger.info(f"預熱活躍票券: {len(active_tickets)} 個")

            # 預熱統計數據
            await self.get_ticket_statistics(guild_id)

            # 預熱今日統計
            today = datetime.now().strftime("%Y-%m-%d")
            await self.get_daily_statistics(guild_id, today)

            logger.info(f"✅ 快取預熱完成: {guild_id}")

        except Exception as e:
            logger.error(f"❌ 快取預熱失敗: {e}")


# ========== 全域實例 ==========

# 創建全域實例
cached_ticket_dao = CachedTicketDAO()


async def get_cached_ticket_dao() -> CachedTicketDAO:
    """獲取快取優化的票券 DAO 實例."""
    return cached_ticket_dao
