# bot/services/realtime_sync_manager.py
"""
即時同步管理器
負責在 Discord、Web UI 和 API 之間同步票券狀態
"""

import asyncio
import json
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any, Dict, Optional

# 可選依賴導入
try:
    import websockets

    WEBSOCKETS_AVAILABLE = True
except ImportError:
    WEBSOCKETS_AVAILABLE = False
    websockets = None

try:
    import aioredis

    REDIS_AVAILABLE = True
    REDIS_TYPE = "aioredis"
except ImportError:
    try:
        import redis.asyncio as redis

        REDIS_AVAILABLE = True
        REDIS_TYPE = "redis-py"
    except ImportError:
        REDIS_AVAILABLE = False
        REDIS_TYPE = None
        redis = None

import aiomysql

from bot.db.pool import db_pool
from shared.logger import logger


class SyncEventType(Enum):
    """同步事件類型"""

    TICKET_CREATED = "ticket_created"
    TICKET_UPDATED = "ticket_updated"
    TICKET_CLOSED = "ticket_closed"
    TICKET_ASSIGNED = "ticket_assigned"
    TICKET_RATED = "ticket_rated"
    MESSAGE_RECEIVED = "message_received"
    USER_JOINED = "user_joined"
    USER_LEFT = "user_left"
    STAFF_STATUS_CHANGED = "staff_status_changed"


@dataclass
class SyncEvent:
    """同步事件資料結構"""

    event_type: SyncEventType
    ticket_id: Optional[int] = None
    user_id: Optional[int] = None
    guild_id: Optional[int] = None
    data: Optional[Dict[str, Any]] = None
    timestamp: datetime = None

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now()


class RealtimeSyncManager:
    """即時同步管理器"""

    def __init__(self, redis_url: str = "redis://localhost:6379"):
        self.redis_url = redis_url
        self.redis = None
        self.subscribers = set()  # 將類型提示移除以避免 websockets 依賴
        self.bot = None
        self.event_queue = asyncio.Queue()
        self.is_running = False

    async def initialize(self, bot=None):
        """初始化同步管理器"""
        try:
            self.bot = bot

            # 嘗試連接 Redis (可選)
            if REDIS_AVAILABLE:
                try:
                    if REDIS_TYPE == "aioredis":
                        self.redis = await aioredis.from_url(self.redis_url, decode_responses=True)
                    elif REDIS_TYPE == "redis-py":
                        self.redis = await redis.from_url(self.redis_url, decode_responses=True)
                    logger.info(f"✅ Redis 連接成功 ({REDIS_TYPE})")
                except Exception as e:
                    logger.warning(f"⚠️ Redis 連接失敗，將使用本機模式: {e}")
                    self.redis = None
            else:
                logger.info("ℹ️ Redis 不可用，將使用本機模式")
                self.redis = None

            # 啟動事件處理器
            self.is_running = True
            asyncio.create_task(self._event_processor())

            logger.info("✅ 即時同步管理器初始化完成")

        except Exception as e:
            logger.error(f"❌ 即時同步管理器初始化失敗: {e}")
            # 即使初始化失敗也要能正常運行
            self.redis = None
            self.is_running = True

    async def publish_event(self, event: SyncEvent):
        """發布同步事件"""
        try:
            # 加入事件佇列
            await self.event_queue.put(event)

            # 如果有 Redis，也發布到 Redis
            if self.redis:
                event_data = {
                    "event_type": event.event_type.value,
                    "ticket_id": event.ticket_id,
                    "user_id": event.user_id,
                    "guild_id": event.guild_id,
                    "data": event.data,
                    "timestamp": event.timestamp.isoformat(),
                }

                await self.redis.publish(
                    (f"ticket_sync:{event.guild_id}" if event.guild_id else "ticket_sync:global"),
                    json.dumps(event_data, ensure_ascii=False),
                )

        except Exception as e:
            logger.error(f"發布同步事件失敗: {e}")

    async def _event_processor(self):
        """事件處理器"""
        while self.is_running:
            try:
                # 等待事件
                event = await asyncio.wait_for(self.event_queue.get(), timeout=1.0)

                # 處理事件
                await self._handle_sync_event(event)

            except asyncio.TimeoutError:
                continue
            except Exception as e:
                logger.error(f"事件處理器錯誤: {e}")

    async def _handle_sync_event(self, event: SyncEvent):
        """處理同步事件"""
        try:
            # 廣播給所有 WebSocket 連接
            await self._broadcast_to_websockets(event)

            # 更新 Discord 狀態（如果需要）
            await self._update_discord_status(event)

            # 記錄事件日誌
            await self._log_sync_event(event)

        except Exception as e:
            logger.error(f"處理同步事件失敗: {e}")

    async def _broadcast_to_websockets(self, event: SyncEvent):
        """廣播事件給所有 WebSocket 連接"""
        if not self.subscribers:
            return

        message = {
            "type": "sync_event",
            "event_type": event.event_type.value,
            "ticket_id": event.ticket_id,
            "user_id": event.user_id,
            "guild_id": event.guild_id,
            "data": event.data,
            "timestamp": event.timestamp.isoformat(),
        }

        # 發送給所有連接的客戶端
        disconnected = set()
        for websocket in self.subscribers.copy():
            try:
                await websocket.send(json.dumps(message, ensure_ascii=False))
            except Exception as e:
                if (
                    WEBSOCKETS_AVAILABLE
                    and hasattr(e, "__class__")
                    and "ConnectionClosed" in str(e.__class__)
                ):
                    disconnected.add(websocket)
                else:
                    logger.warning(f"WebSocket 廣播失敗: {e}")
                    disconnected.add(websocket)

        # 清理斷開的連接
        self.subscribers -= disconnected

    async def _update_discord_status(self, event: SyncEvent):
        """更新 Discord 中的狀態顯示"""
        if not self.bot or not event.ticket_id:
            return

        try:
            # 根據事件類型更新對應的 Discord 界面
            if event.event_type == SyncEventType.TICKET_UPDATED:
                await self._update_ticket_embed(event)
            elif event.event_type == SyncEventType.TICKET_ASSIGNED:
                await self._notify_assignment(event)
            elif event.event_type == SyncEventType.TICKET_CLOSED:
                await self._notify_closure(event)

        except Exception as e:
            logger.error(f"更新 Discord 狀態失敗: {e}")

    async def _update_ticket_embed(self, event: SyncEvent):
        """更新票券 Embed 顯示"""
        try:
            # 獲取票券資訊
            ticket_info = await self._get_ticket_info(event.ticket_id)
            if not ticket_info:
                return

            # 找到對應的頻道
            channel = self.bot.get_channel(ticket_info["channel_id"])
            if not channel:
                return

            # 更新頻道中的票券狀態訊息
            from bot.utils.ticket_utils import create_ticket_status_embed

            embed = await create_ticket_status_embed(ticket_info)

            # 尋找並更新狀態訊息
            async for message in channel.history(limit=50):
                if message.author == self.bot.user and message.embeds:
                    if "票券狀態" in message.embeds[0].title:
                        await message.edit(embed=embed)
                        break

        except Exception as e:
            logger.error(f"更新票券 Embed 失敗: {e}")

    async def _notify_assignment(self, event: SyncEvent):
        """通知票券指派"""
        try:
            if not event.data or "assigned_to" not in event.data:
                return

            assigned_to = event.data["assigned_to"]
            ticket_info = await self._get_ticket_info(event.ticket_id)

            # 發送 DM 通知被指派者
            user = self.bot.get_user(assigned_to)
            if user:
                from bot.utils.embed_builder import EmbedBuilder

                embed = EmbedBuilder.build(
                    title="🎫 新票券指派",
                    description=f"您被指派處理票券 #{event.ticket_id:04d}",
                    color=0x3498DB,
                )
                if ticket_info:
                    embed.add_field(name="票券類型", value=ticket_info["type"], inline=True)
                    embed.add_field(name="優先級", value=ticket_info["priority"], inline=True)

                try:
                    await user.send(embed=embed)
                except:
                    pass  # 如果無法發送 DM，忽略錯誤

        except Exception as e:
            logger.error(f"通知票券指派失敗: {e}")

    async def _notify_closure(self, event: SyncEvent):
        """通知票券關閉"""
        try:
            ticket_info = await self._get_ticket_info(event.ticket_id)
            if not ticket_info:
                return

            # 通知票券創建者
            user = self.bot.get_user(int(ticket_info["discord_id"]))
            if user and event.data and "closed_by" in event.data:
                from bot.utils.embed_builder import EmbedBuilder

                embed = EmbedBuilder.build(
                    title="✅ 票券已關閉",
                    description=f"您的票券 #{event.ticket_id:04d} 已被關閉",
                    color=0x2ECC71,
                )

                if event.data.get("reason"):
                    embed.add_field(name="關閉原因", value=event.data["reason"], inline=False)

                try:
                    await user.send(embed=embed)
                except:
                    pass

        except Exception as e:
            logger.error(f"通知票券關閉失敗: {e}")

    async def _get_ticket_info(self, ticket_id: int) -> Optional[Dict[str, Any]]:
        """獲取票券資訊"""
        try:
            async with db_pool.connection() as conn:
                async with conn.cursor(aiomysql.DictCursor) as cursor:
                    await cursor.execute("SELECT * FROM tickets WHERE id = %s", (ticket_id,))
                    return await cursor.fetchone()
        except Exception as e:
            logger.error(f"獲取票券資訊失敗: {e}")
            return None

    async def _log_sync_event(self, event: SyncEvent):
        """記錄同步事件日誌"""
        try:
            # 記錄到資料庫
            async with db_pool.connection() as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute(
                        """
                        INSERT INTO sync_events
                        (event_type, ticket_id, user_id, guild_id, event_data, created_at)
                        VALUES (%s, %s, %s, %s, %s, %s)
                        ON DUPLICATE KEY UPDATE created_at = VALUES(created_at)
                    """,
                        (
                            event.event_type.value,
                            event.ticket_id,
                            event.user_id,
                            event.guild_id,
                            (json.dumps(event.data, ensure_ascii=False) if event.data else None),
                            event.timestamp,
                        ),
                    )
                    await conn.commit()

        except Exception as e:
            # 即使日誌記錄失敗也不影響主要功能
            logger.debug(f"即時同步日誌記錄失敗: {e}")

    async def add_websocket_subscriber(self, websocket):
        """添加 WebSocket 訂閱者"""
        self.subscribers.add(websocket)
        logger.info(f"WebSocket 客戶端已連接，目前連接數: {len(self.subscribers)}")

    async def remove_websocket_subscriber(self, websocket):
        """移除 WebSocket 訂閱者"""
        self.subscribers.discard(websocket)
        logger.info(f"WebSocket 客戶端已斷開，目前連接數: {len(self.subscribers)}")

    async def get_active_tickets_count(self, guild_id: Optional[int] = None) -> int:
        """獲取活躍票券數量"""
        try:
            async with db_pool.connection() as conn:
                async with conn.cursor() as cursor:
                    if guild_id:
                        await cursor.execute(
                            "SELECT COUNT(*) FROM tickets WHERE status = 'open' AND guild_id = %s",
                            (guild_id,),
                        )
                    else:
                        await cursor.execute("SELECT COUNT(*) FROM tickets WHERE status = 'open'")

                    result = await cursor.fetchone()
                    return result[0] if result else 0

        except Exception as e:
            logger.error(f"獲取活躍票券數量失敗: {e}")
            return 0

    async def get_online_staff_count(self, guild_id: int) -> int:
        """獲取在線客服數量"""
        try:
            if not self.bot:
                return 0

            guild = self.bot.get_guild(guild_id)
            if not guild:
                return 0

            online_staff = 0
            for member in guild.members:
                # 檢查是否有客服角色且在線
                if any(role.name in ["客服", "Staff", "管理員", "Admin"] for role in member.roles):
                    if member.status != discord.Status.offline:
                        online_staff += 1

            return online_staff

        except Exception as e:
            logger.error(f"獲取在線客服數量失敗: {e}")
            return 0

    async def shutdown(self):
        """關閉同步管理器"""
        self.is_running = False

        if self.redis:
            await self.redis.close()

        # 關閉所有 WebSocket 連接
        for websocket in self.subscribers.copy():
            try:
                await websocket.close()
            except:
                pass

        self.subscribers.clear()
        logger.info("即時同步管理器已關閉")


# 全局同步管理器實例
realtime_sync = RealtimeSyncManager()
