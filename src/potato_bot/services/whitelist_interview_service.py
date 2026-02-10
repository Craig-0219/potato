"""
Whitelist interview services
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, Optional
from zoneinfo import ZoneInfo

from potato_bot.db.whitelist_interview_dao import WhitelistInterviewDAO


def _to_int(value: Any) -> Optional[int]:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


@dataclass
class WhitelistInterviewSettings:
    guild_id: int
    waiting_channel_id: Optional[int] = None
    interview_channel_id: Optional[int] = None
    notify_channel_id: Optional[int] = None
    staff_role_id: Optional[int] = None
    timezone: str = "Asia/Taipei"
    session_start_hour: int = 19
    session_end_hour: int = 23
    is_enabled: bool = False

    @property
    def is_complete(self) -> bool:
        return bool(
            self.waiting_channel_id and self.interview_channel_id and self.notify_channel_id
        )

    def get_zoneinfo(self) -> ZoneInfo:
        try:
            return ZoneInfo(self.timezone)
        except Exception:
            return ZoneInfo("UTC")

    def local_now(self) -> datetime:
        return datetime.now(self.get_zoneinfo())

    def local_today(self) -> date:
        return self.local_now().date()

    def is_in_session(self, now: Optional[datetime] = None) -> bool:
        if now is None:
            now = self.local_now()
        hour = now.hour
        start = int(self.session_start_hour) % 24
        end = int(self.session_end_hour) % 24

        if start == end:
            return True
        if start < end:
            return start <= hour < end
        return hour >= start or hour < end


class WhitelistInterviewService:
    """白名單面試設定服務"""

    def __init__(self, dao: WhitelistInterviewDAO):
        self.dao = dao

    async def load_settings(self, guild_id: int) -> WhitelistInterviewSettings:
        row = await self.dao.get_settings(guild_id)
        return self._from_row(guild_id, row)

    async def save_settings(self, guild_id: int, **settings: Any) -> WhitelistInterviewSettings:
        current = await self.dao.get_settings(guild_id) or {}
        current_start_raw = current.get("session_start_hour")
        current_end_raw = current.get("session_end_hour")
        payload = {
            "waiting_channel_id": _to_int(current.get("waiting_channel_id")),
            "interview_channel_id": _to_int(current.get("interview_channel_id")),
            "notify_channel_id": _to_int(current.get("notify_channel_id")),
            "staff_role_id": _to_int(current.get("staff_role_id")),
            "timezone": current.get("timezone") or "Asia/Taipei",
            "session_start_hour": (
                int(current_start_raw) if current_start_raw is not None else 19
            ),
            "session_end_hour": int(current_end_raw) if current_end_raw is not None else 23,
            "is_enabled": bool(current.get("is_enabled", False)),
        }
        for key, value in settings.items():
            if value is not None:
                payload[key] = value
        await self.dao.upsert_settings(guild_id, **payload)
        row = await self.dao.get_settings(guild_id)
        return self._from_row(guild_id, row)

    @staticmethod
    def _from_row(guild_id: int, row: Any) -> WhitelistInterviewSettings:
        if not row:
            return WhitelistInterviewSettings(guild_id=guild_id)
        start_raw = row.get("session_start_hour")
        end_raw = row.get("session_end_hour")
        return WhitelistInterviewSettings(
            guild_id=guild_id,
            waiting_channel_id=_to_int(row.get("waiting_channel_id")),
            interview_channel_id=_to_int(row.get("interview_channel_id")),
            notify_channel_id=_to_int(row.get("notify_channel_id")),
            staff_role_id=_to_int(row.get("staff_role_id")),
            timezone=str(row.get("timezone") or "Asia/Taipei"),
            session_start_hour=int(start_raw) if start_raw is not None else 19,
            session_end_hour=int(end_raw) if end_raw is not None else 23,
            is_enabled=bool(row.get("is_enabled", False)),
        )
