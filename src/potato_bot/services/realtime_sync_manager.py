from __future__ import annotations

import enum
from dataclasses import dataclass
from typing import Any, Dict, Optional

from potato_shared.logger import logger


class SyncEventType(str, enum.Enum):
    """同步事件類型（簡化版佔位）"""

    TICKET_UPDATED = "ticket_updated"
    TICKET_CREATED = "ticket_created"
    TICKET_CLOSED = "ticket_closed"


@dataclass
class SyncEvent:
    event_type: SyncEventType
    payload: Dict[str, Any]
    guild_id: Optional[int] = None


class RealtimeSyncManager:
    """簡化版同步管理器（無外部依賴，佔位實作）"""

    async def publish_event(self, event: SyncEvent) -> None:
        logger.debug(f"[RealtimeSync] publish_event: {event.event_type} payload={event.payload}")


# 簡單工廠
realtime_sync = RealtimeSyncManager()
