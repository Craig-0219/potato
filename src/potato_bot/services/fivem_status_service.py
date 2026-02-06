import asyncio
import json
import os
import time
from dataclasses import dataclass
from typing import Any, Optional

import aiohttp

from potato_shared.logger import logger


@dataclass
class FiveMStatusResult:
    status: str
    players: int
    max_players: Optional[int]
    hostname: Optional[str]
    info_ok: bool
    players_ok: bool


class FiveMStatusService:
    def __init__(
        self,
        info_url: str,
        players_url: str,
        offline_threshold: int = 3,
        txadmin_status_file: Optional[str] = None,
        restart_notify_seconds: Optional[list[int]] = None,
    ):
        self.info_url = info_url
        self.players_url = players_url
        self.offline_threshold = max(1, offline_threshold)
        self.txadmin_status_file = txadmin_status_file
        self.restart_notify_seconds = restart_notify_seconds or []

        self._fail_count = 0
        self._last_status: Optional[str] = None
        self._last_txadmin_updated_at: Optional[int] = None
        self._last_restart_seconds: Optional[int] = None

        timeout = aiohttp.ClientTimeout(total=6)
        self._session = aiohttp.ClientSession(timeout=timeout)

    async def close(self):
        if not self._session.closed:
            await self._session.close()

    async def fetch_json(self, url: str) -> Optional[Any]:
        try:
            async with self._session.get(url) as response:
                if response.status != 200:
                    return None
                return await response.json()
        except asyncio.TimeoutError:
            return None
        except Exception as exc:
            logger.error("FiveM 狀態請求失敗: %s", exc)
            return None

    async def poll_status(self) -> FiveMStatusResult:
        info_data = await self.fetch_json(self.info_url)
        players_data = await self.fetch_json(self.players_url)

        info_ok = info_data is not None
        players_ok = players_data is not None

        if info_ok and players_ok:
            self._fail_count = 0
            status = "online"
        else:
            self._fail_count += 1
            status = self._last_status or "unknown"
            if self._fail_count >= self.offline_threshold:
                status = "offline"

        players = 0
        max_players = None
        hostname = None

        if players_ok:
            if isinstance(players_data, list):
                players = len(players_data)
            elif isinstance(players_data, dict):
                players = int(players_data.get("players", 0) or 0)

        if info_ok and isinstance(info_data, dict):
            max_players = info_data.get("vars", {}).get("sv_maxClients")
            hostname = info_data.get("vars", {}).get("sv_projectName") or info_data.get("vars", {}).get(
                "sv_hostname"
            )
            try:
                max_players = int(max_players) if max_players is not None else None
            except (TypeError, ValueError):
                max_players = None

        result = FiveMStatusResult(
            status=status,
            players=players,
            max_players=max_players,
            hostname=hostname,
            info_ok=info_ok,
            players_ok=players_ok,
        )

        self._last_status = status
        return result

    def read_txadmin_status(self) -> Optional[dict]:
        if not self.txadmin_status_file:
            return None
        path = os.path.expandvars(os.path.expanduser(self.txadmin_status_file))
        if not os.path.isfile(path):
            return None
        try:
            with open(path, "r", encoding="utf-8") as handle:
                return json.load(handle)
        except Exception as exc:
            logger.error("讀取 txAdmin 狀態檔失敗: %s", exc)
            return None

    def should_announce_txadmin(self, tx_status: dict) -> bool:
        if not tx_status:
            return False
        updated_at = tx_status.get("updated_at")
        if not updated_at:
            return False
        if self._last_txadmin_updated_at == updated_at:
            return False
        self._last_txadmin_updated_at = updated_at
        return True

    def is_restart_notice(self, tx_status: dict) -> bool:
        if not tx_status:
            return False
        event = tx_status.get("event") or {}
        if event.get("type") != "scheduledRestart":
            return False
        data = event.get("data") or {}
        seconds = data.get("secondsRemaining")
        if seconds is None:
            return False
        try:
            seconds = int(seconds)
        except (TypeError, ValueError):
            return False

        if self.restart_notify_seconds and seconds not in self.restart_notify_seconds:
            return False

        if self._last_restart_seconds == seconds:
            return False
        self._last_restart_seconds = seconds
        return True

    @staticmethod
    def get_txadmin_event_type(tx_status: dict) -> Optional[str]:
        event = tx_status.get("event") or {}
        event_type = event.get("type")
        return event_type

    @staticmethod
    def format_restart_message(tx_status: dict) -> str:
        event = tx_status.get("event") or {}
        data = event.get("data") or {}
        seconds = int(data.get("secondsRemaining", 0) or 0)
        minutes = seconds // 60 if seconds else 0
        if minutes > 0:
            return f"伺服器預計 {minutes} 分鐘後重啟。"
        if seconds > 0:
            return f"伺服器即將在 {seconds} 秒內重啟。"
        return "伺服器即將重啟。"

    @staticmethod
    def format_status_message(result: FiveMStatusResult) -> str:
        if result.status == "online":
            if result.max_players:
                return f"線上玩家：{result.players}/{result.max_players}"
            return f"線上玩家：{result.players}"
        if result.status == "offline":
            return "目前無法連線到伺服器。"
        return "伺服器狀態未知。"
