import asyncio
import io
import json
import os
import time
from dataclasses import dataclass
from typing import Any, Optional

import aiohttp
from aiohttp import ClientConnectionError, ServerDisconnectedError
from ftplib import FTP, error_perm

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
        ftp_host: Optional[str] = None,
        ftp_port: int = 21,
        ftp_user: Optional[str] = None,
        ftp_password: Optional[str] = None,
        ftp_path: Optional[str] = None,
        ftp_passive: bool = True,
        ftp_timeout: int = 10,
    ):
        self.info_url = info_url
        self.players_url = players_url
        self.offline_threshold = max(1, offline_threshold)
        self.txadmin_status_file = txadmin_status_file
        self.restart_notify_seconds = restart_notify_seconds or []
        self.ftp_host = ftp_host
        self.ftp_port = ftp_port
        self.ftp_user = ftp_user
        self.ftp_password = ftp_password
        self.ftp_path = ftp_path
        self.ftp_passive = ftp_passive
        self.ftp_timeout = max(3, int(ftp_timeout or 10))

        self._ftp: Optional[FTP] = None
        self._ftp_last_used = 0.0
        self._ftp_lock = asyncio.Lock()

        self._last_txadmin_read_ok: Optional[bool] = None
        self._last_txadmin_read_at: Optional[float] = None
        self._last_txadmin_read_error: Optional[str] = None
        self._last_txadmin_payload: Optional[dict] = None
        self._last_txadmin_payload_at: Optional[float] = None

        self._fail_count = 0
        self._last_status: Optional[str] = None
        self._last_txadmin_updated_at: Optional[int] = None
        self._last_restart_seconds: Optional[int] = None

        timeout = aiohttp.ClientTimeout(total=6)
        self._session = aiohttp.ClientSession(timeout=timeout)

    async def close(self):
        if not self._session.closed:
            await self._session.close()
        if self._ftp_enabled() and self._ftp:
            async with self._ftp_lock:
                await asyncio.to_thread(self._disconnect_ftp)

    async def fetch_json(self, url: str) -> Optional[Any]:
        if not url:
            return None
        last_exc: Optional[Exception] = None
        for attempt in range(2):
            try:
                async with self._session.get(url) as response:
                    if response.status != 200:
                        return None
                    return await response.json(content_type=None)
            except (asyncio.TimeoutError, ClientConnectionError, ServerDisconnectedError) as exc:
                last_exc = exc
                if attempt == 0:
                    await asyncio.sleep(0.3)
                continue
            except Exception as exc:
                last_exc = exc
                break
        if last_exc:
            logger.warning("FiveM 狀態請求失敗: %s (url=%s)", last_exc, url)
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

    async def read_txadmin_status(self) -> Optional[dict]:
        if self._ftp_enabled():
            async with self._ftp_lock:
                return await asyncio.to_thread(self._read_txadmin_status_ftp)
        return self._read_txadmin_status_local()

    def get_txadmin_read_status(self) -> Optional[dict]:
        """取得 txAdmin 狀態檔讀取狀態（None 表示未啟用）"""
        if not self._ftp_enabled() and not self.txadmin_status_file:
            return None
        return {
            "ok": self._last_txadmin_read_ok,
            "last_read_at": self._last_txadmin_read_at,
            "error": self._last_txadmin_read_error,
        }

    def get_last_txadmin_payload(self) -> Optional[dict]:
        """取得最後一次成功讀取的 txAdmin JSON"""
        return self._last_txadmin_payload

    def get_last_txadmin_payload_at(self) -> Optional[float]:
        """取得最後一次成功讀取 txAdmin JSON 的時間戳"""
        return self._last_txadmin_payload_at

    def _ftp_enabled(self) -> bool:
        return bool(self.ftp_host and self.ftp_path)

    def _read_txadmin_status_local(self) -> Optional[dict]:
        if not self.txadmin_status_file:
            self._mark_txadmin_read(None)
            return None
        path = os.path.expandvars(os.path.expanduser(self.txadmin_status_file))
        if not os.path.isfile(path):
            self._mark_txadmin_read(False, "file_not_found")
            return None
        try:
            with open(path, "r", encoding="utf-8") as handle:
                data = json.load(handle)
                self._mark_txadmin_read(True, payload=data)
                return data
        except Exception as exc:
            logger.error("讀取 txAdmin 狀態檔失敗: %s", exc)
            self._mark_txadmin_read(False, str(exc))
            return None

    def _read_txadmin_status_ftp(self) -> Optional[dict]:
        if not self._ftp_enabled():
            self._mark_txadmin_read(None)
            return None

        last_error: Optional[str] = None
        for attempt in range(3):  # 1 次 + 2 次重試
            try:
                ftp = self._ensure_ftp_connection()
                if not ftp:
                    raise RuntimeError("ftp_connect_failed")

                # 若連線過久未使用，先發 NOOP 保持連線
                now = time.time()
                if self._ftp_last_used and now - self._ftp_last_used > 30:
                    try:
                        ftp.voidcmd("NOOP")
                    except Exception:
                        self._disconnect_ftp()
                        ftp = self._ensure_ftp_connection()
                        if not ftp:
                            raise RuntimeError("ftp_reconnect_failed")

                buffer = io.BytesIO()
                ftp.retrbinary(f"RETR {self.ftp_path}", buffer.write)
                self._ftp_last_used = time.time()
                data = buffer.getvalue().decode("utf-8")
                parsed = json.loads(data)
                self._mark_txadmin_read(True, payload=parsed)
                return parsed
            except error_perm as exc:
                last_error = str(exc)
                logger.warning("FTP 取檔失敗（權限/路徑）：%s", exc)
                self._disconnect_ftp()
            except Exception as exc:
                last_error = str(exc)
                logger.error("FTP 讀取 txAdmin 狀態檔失敗: %s", exc)
                self._disconnect_ftp()

            if attempt < 2:
                time.sleep(0.2 * (attempt + 1))

        self._mark_txadmin_read(False, f"ftp_retries_exhausted:{last_error}")
        return None

    def _ensure_ftp_connection(self) -> Optional[FTP]:
        if self._ftp:
            return self._ftp
        try:
            ftp = FTP()
            ftp.connect(self.ftp_host, self.ftp_port, timeout=self.ftp_timeout)
            ftp.login(self.ftp_user, self.ftp_password)
            ftp.set_pasv(self.ftp_passive)
            self._ftp = ftp
            self._ftp_last_used = time.time()
            return ftp
        except Exception as exc:
            logger.error("FTP 連線失敗: %s", exc)
            self._ftp = None
            return None

    def _disconnect_ftp(self) -> None:
        if not self._ftp:
            return
        try:
            self._ftp.quit()
        except Exception:
            try:
                self._ftp.close()
            except Exception:
                pass
        self._ftp = None
        self._ftp_last_used = 0.0

    def is_ftp_connected(self) -> Optional[bool]:
        """回報 FTP 連線狀態（None 表示未啟用）"""
        if not self._ftp_enabled():
            return None
        return self._ftp is not None

    def _mark_txadmin_read(
        self, ok: Optional[bool], error: Optional[str] = None, payload: Optional[dict] = None
    ) -> None:
        if ok is None:
            self._last_txadmin_read_ok = None
            self._last_txadmin_read_at = None
            self._last_txadmin_read_error = None
            return
        self._last_txadmin_read_ok = ok
        self._last_txadmin_read_at = time.time()
        self._last_txadmin_read_error = error
        if ok and payload is not None:
            self._last_txadmin_payload = payload
            self._last_txadmin_payload_at = self._last_txadmin_read_at

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
