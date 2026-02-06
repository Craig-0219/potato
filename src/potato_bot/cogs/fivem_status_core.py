import asyncio
import time
from dataclasses import dataclass, field
from typing import Optional

import discord
from discord.ext import commands, tasks

from potato_bot.db.fivem_dao import FiveMDAO
from potato_bot.services.fivem_status_service import FiveMStatusService
from potato_bot.utils.embed_builder import EmbedBuilder
from potato_shared.config import (
    FIVEM_OFFLINE_THRESHOLD,
    FIVEM_POLL_INTERVAL,
    FIVEM_RESTART_NOTIFY_SECONDS,
    FIVEM_TXADMIN_STATUS_FILE,
    FIVEM_TXADMIN_FTP_HOST,
    FIVEM_TXADMIN_FTP_PASSWORD,
    FIVEM_TXADMIN_FTP_PASSIVE,
    FIVEM_TXADMIN_FTP_PATH,
    FIVEM_TXADMIN_FTP_PORT,
    FIVEM_TXADMIN_FTP_TIMEOUT,
    FIVEM_TXADMIN_FTP_USER,
)
from potato_shared.logger import logger


def _parse_seconds_list(raw: str) -> list[int]:
    results: list[int] = []
    for part in (raw or "").split(","):
        part = part.strip()
        if not part:
            continue
        try:
            results.append(int(part))
        except ValueError:
            continue
    return results


@dataclass
class _FiveMGuildState:
    service: FiveMStatusService
    channel_id: int
    has_http: bool = True
    alert_role_ids: list[int] = field(default_factory=list)
    last_status: Optional[str] = None
    ftp_fail_count: int = 0
    ftp_last_alert: float = 0.0
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)


class FiveMStatusCore(commands.Cog):
    """FiveM 伺服器狀態播報"""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.dao = FiveMDAO()
        self._guild_states: dict[int, _FiveMGuildState] = {}
        self._settings_cache: dict[int, tuple[Optional[str], Optional[str], int]] = {}
        self._warned_missing: set[int] = set()
        self._push_last_status: dict[int, Optional[str]] = {}
        self._push_locks: dict[int, asyncio.Lock] = {}
        self._push_last_event_id: dict[int, str] = {}
        self.monitor_task.start()
        logger.info("✅ FiveM 狀態播報已啟動（使用資料庫設定）")

    def cog_unload(self):
        if self.monitor_task.is_running():
            self.monitor_task.cancel()
        for state in list(self._guild_states.values()):
            asyncio.create_task(state.service.close())
        self._guild_states.clear()
        self._settings_cache.clear()
        self._push_last_status.clear()
        self._push_locks.clear()
        self._push_last_event_id.clear()

    async def _get_channel(self, channel_id: int) -> Optional[discord.abc.Messageable]:
        if not channel_id:
            return None
        channel = self.bot.get_channel(channel_id)
        if channel is None:
            try:
                channel = await self.bot.fetch_channel(channel_id)
            except Exception:
                return None
        return channel

    async def _send_embed(
        self, channel_id: int, title: str, description: str, color: str = "info"
    ):
        channel = await self._get_channel(channel_id)
        if not channel:
            return
        if color == "success":
            embed = EmbedBuilder.create_success_embed(title, description)
        elif color == "warning":
            embed = EmbedBuilder.create_warning_embed(title, description)
        elif color == "error":
            embed = EmbedBuilder.create_error_embed(title, description)
        else:
            embed = EmbedBuilder.create_info_embed(title, description)
        try:
            await channel.send(embed=embed)
        except Exception as exc:
            logger.warning("FiveM 播報發送失敗: %s", exc)

    async def _resolve_settings(self, guild_id: int) -> tuple[Optional[str], Optional[str], int]:
        settings = await self.dao.get_fivem_settings(guild_id)
        info_url = settings.get("info_url")
        players_url = settings.get("players_url")
        channel_id = int(settings.get("status_channel_id") or 0)

        return info_url, players_url, channel_id

    @staticmethod
    def _txadmin_enabled() -> bool:
        return bool(
            FIVEM_TXADMIN_STATUS_FILE
            or (FIVEM_TXADMIN_FTP_HOST and FIVEM_TXADMIN_FTP_PATH)
        )

    @staticmethod
    def _format_role_mentions(guild: discord.Guild, role_ids: list[int]) -> str:
        mentions = [
            role.mention for role in (guild.get_role(role_id) for role_id in role_ids) if role
        ]
        return " ".join(mentions)

    async def _dm_alert_roles(
        self,
        guild: discord.Guild,
        role_ids: list[int],
        title: str,
        description: str,
        color: str = "warning",
    ) -> None:
        if not role_ids:
            return

        members: set[discord.Member] = set()
        for role_id in role_ids:
            role = guild.get_role(role_id)
            if role:
                members.update(role.members)

        if not members:
            return

        if color == "success":
            embed = EmbedBuilder.create_success_embed(title, description)
        elif color == "error":
            embed = EmbedBuilder.create_error_embed(title, description)
        elif color == "info":
            embed = EmbedBuilder.create_info_embed(title, description)
        else:
            embed = EmbedBuilder.create_warning_embed(title, description)
        embed.set_footer(text=f"伺服器：{guild.name}")

        semaphore = asyncio.Semaphore(5)

        async def _send_dm(member: discord.Member):
            if member.bot:
                return
            try:
                async with semaphore:
                    await member.send(embed=embed)
            except Exception:
                pass

        await asyncio.gather(*[_send_dm(member) for member in members], return_exceptions=True)

    def _get_push_lock(self, guild_id: int) -> asyncio.Lock:
        lock = self._push_locks.get(guild_id)
        if not lock:
            lock = asyncio.Lock()
            self._push_locks[guild_id] = lock
        return lock

    @staticmethod
    def _normalize_status(raw: Optional[str]) -> Optional[str]:
        if not raw:
            return None
        status = str(raw).strip().lower()
        mapping = {
            "online": "online",
            "up": "online",
            "running": "online",
            "started": "online",
            "offline": "offline",
            "down": "offline",
            "stopped": "offline",
            "crashed": "offline",
            "starting": "starting",
            "stopping": "stopping",
        }
        return mapping.get(status, None)

    @staticmethod
    def _parse_int(value: Optional[object]) -> Optional[int]:
        if value is None:
            return None
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _build_status_description(
        status: str,
        players: Optional[int],
        max_players: Optional[int],
        hostname: Optional[str],
    ) -> str:
        lines: list[str] = []
        if hostname:
            lines.append(f"伺服器：{hostname}")
        if status == "online":
            if players is not None and max_players:
                lines.append(f"線上玩家：{players}/{max_players}")
            elif players is not None:
                lines.append(f"線上玩家：{players}")
            else:
                lines.append("伺服器已上線。")
        elif status == "offline":
            lines.append("目前無法連線到伺服器。")
        return "\n".join(lines) if lines else "伺服器狀態更新。"

    @staticmethod
    def _build_event_description(event_type: str, hostname: Optional[str]) -> str:
        messages = {
            "serverStarting": "伺服器正在啟動中，請稍候。",
            "serverStarted": "伺服器啟動完成，現在可以加入。",
            "serverStopping": "伺服器即將停止，請注意保存進度。",
            "serverStopped": "伺服器已停止，請稍後再試。",
            "serverCrashed": "偵測到伺服器異常崩潰，請等待修復。",
        }
        base = messages.get(event_type, "伺服器狀態更新。")
        if hostname:
            return f"伺服器：{hostname}\n{base}"
        return base

    async def handle_push(self, payload: dict) -> dict:
        """接收跨機腳本推送的 FiveM 狀態"""
        guild_id = self._parse_int(payload.get("guild_id") if payload else None)
        if not guild_id:
            return {"ok": False, "error": "guild_id_required"}

        settings = await self.dao.get_fivem_settings(guild_id)
        channel_id = int(settings.get("status_channel_id") or 0)
        if not channel_id:
            return {"ok": False, "error": "status_channel_not_set"}

        event_type = payload.get("event") or payload.get("txadmin_event")
        event_id = payload.get("event_id")
        status = self._normalize_status(payload.get("status"))
        players = self._parse_int(payload.get("players"))
        max_players = self._parse_int(payload.get("max_players"))
        hostname = payload.get("hostname")

        sent: list[str] = []
        event_sent = False

        async with self._get_push_lock(guild_id):
            if event_id:
                last_event_id = self._push_last_event_id.get(guild_id)
                if last_event_id == str(event_id):
                    event_type = None
                else:
                    self._push_last_event_id[guild_id] = str(event_id)

            if event_type:
                title_map = {
                    "serverStarting": ("🟡 FiveM 伺服器啟動中", "warning"),
                    "serverStarted": ("✅ FiveM 伺服器已啟動", "success"),
                    "serverStopping": ("🟠 FiveM 伺服器準備停止", "warning"),
                    "serverStopped": ("🔴 FiveM 伺服器已停止", "error"),
                    "serverCrashed": ("🚨 FiveM 伺服器崩潰", "error"),
                }
                if event_type in title_map:
                    title, color = title_map[event_type]
                    desc = self._build_event_description(event_type, hostname)
                    await self._send_embed(channel_id, title, desc, color)
                    sent.append(event_type)
                    event_sent = True

                    if event_type == "serverStarted":
                        self._push_last_status[guild_id] = "online"
                    elif event_type in ("serverStopped", "serverCrashed"):
                        self._push_last_status[guild_id] = "offline"
                    elif event_type == "serverStarting":
                        self._push_last_status[guild_id] = "starting"
                    elif event_type == "serverStopping":
                        self._push_last_status[guild_id] = "stopping"

            if status and status in ("online", "offline"):
                last_status = self._push_last_status.get(guild_id)
                if status != last_status and not event_sent:
                    desc = self._build_status_description(status, players, max_players, hostname)
                    if status == "online":
                        await self._send_embed(channel_id, "✅ FiveM 伺服器已上線", desc, "success")
                    else:
                        await self._send_embed(channel_id, "🔴 FiveM 伺服器離線", desc, "error")
                    sent.append(status)
                self._push_last_status[guild_id] = status

        return {"ok": True, "sent": sent}

    async def _get_state(self, guild: discord.Guild) -> Optional[_FiveMGuildState]:
        settings = await self.dao.get_fivem_settings(guild.id)
        info_url = settings.get("info_url")
        players_url = settings.get("players_url")
        channel_id = int(settings.get("status_channel_id") or 0)
        alert_role_ids = settings.get("alert_role_ids", []) or []
        has_http = bool(info_url and players_url)
        txadmin_enabled = self._txadmin_enabled()
        cache_key = (info_url, players_url, channel_id)

        if not channel_id:
            if guild.id not in self._warned_missing:
                self._warned_missing.add(guild.id)
                logger.warning(
                    "⚠️ FiveM 狀態播報尚未設定（缺少播報頻道）：%s (%s)",
                    guild.name,
                    guild.id,
                )
            if guild.id in self._guild_states:
                state = self._guild_states.pop(guild.id)
                await state.service.close()
            self._settings_cache.pop(guild.id, None)
            return None

        if not has_http and not txadmin_enabled:
            if guild.id not in self._warned_missing:
                self._warned_missing.add(guild.id)
                logger.warning(
                    "⚠️ FiveM 狀態播報尚未設定（缺少 API 或 txAdmin 狀態來源）：%s (%s)",
                    guild.name,
                    guild.id,
                )
            if guild.id in self._guild_states:
                state = self._guild_states.pop(guild.id)
                await state.service.close()
            self._settings_cache.pop(guild.id, None)
            return None

        self._warned_missing.discard(guild.id)

        if self._settings_cache.get(guild.id) != cache_key:
            self._settings_cache[guild.id] = cache_key
            if guild.id in self._guild_states:
                await self._guild_states[guild.id].service.close()
            service = FiveMStatusService(
                info_url=info_url,
                players_url=players_url,
                offline_threshold=FIVEM_OFFLINE_THRESHOLD,
                txadmin_status_file=FIVEM_TXADMIN_STATUS_FILE,
                restart_notify_seconds=_parse_seconds_list(FIVEM_RESTART_NOTIFY_SECONDS),
                ftp_host=FIVEM_TXADMIN_FTP_HOST,
                ftp_port=FIVEM_TXADMIN_FTP_PORT,
                ftp_user=FIVEM_TXADMIN_FTP_USER,
                ftp_password=FIVEM_TXADMIN_FTP_PASSWORD,
                ftp_path=FIVEM_TXADMIN_FTP_PATH,
                ftp_passive=FIVEM_TXADMIN_FTP_PASSIVE,
                ftp_timeout=FIVEM_TXADMIN_FTP_TIMEOUT,
            )
            self._guild_states[guild.id] = _FiveMGuildState(
                service=service,
                channel_id=channel_id,
                has_http=has_http,
                alert_role_ids=alert_role_ids,
            )

        state = self._guild_states.get(guild.id)
        if state:
            state.channel_id = channel_id
            state.has_http = has_http
            state.alert_role_ids = alert_role_ids
        return state

    @tasks.loop(seconds=FIVEM_POLL_INTERVAL)
    async def monitor_task(self):
        if not self.bot.guilds:
            return

        for guild in list(self.bot.guilds):
            try:
                state = await self._get_state(guild)
                if not state:
                    continue

                async with state.lock:
                    if state.has_http:
                        result = await state.service.poll_status()
                        if result.status != state.last_status:
                            state.last_status = result.status
                            if result.status == "online":
                                await self._send_embed(
                                    state.channel_id,
                                    "✅ FiveM 伺服器已上線",
                                    state.service.format_status_message(result),
                                    "success",
                                )
                            elif result.status == "offline":
                                await self._send_embed(
                                    state.channel_id,
                                    "🔴 FiveM 伺服器離線",
                                    state.service.format_status_message(result),
                                    "error",
                                )

                    tx_status = await state.service.read_txadmin_status()
                    if tx_status:
                        state.ftp_fail_count = 0

                    if tx_status and state.service.should_announce_txadmin(tx_status):
                        event_type = state.service.get_txadmin_event_type(tx_status)
                        if event_type == "serverStarting":
                            await self._send_embed(
                                state.channel_id,
                                "🟡 FiveM 伺服器啟動中",
                                "伺服器正在啟動中，請稍候。",
                                "warning",
                            )
                        elif event_type == "serverStarted":
                            await self._send_embed(
                                state.channel_id,
                                "✅ FiveM 伺服器已啟動",
                                "伺服器啟動完成，現在可以加入。",
                                "success",
                            )
                        elif event_type == "serverStopping":
                            await self._send_embed(
                                state.channel_id,
                                "🟠 FiveM 伺服器準備停止",
                                "伺服器即將停止，請注意保存進度。",
                                "warning",
                            )
                        elif event_type == "serverStopped":
                            await self._send_embed(
                                state.channel_id,
                                "🔴 FiveM 伺服器已停止",
                                "伺服器已停止，請稍後再試。",
                                "error",
                            )
                        elif event_type == "serverCrashed":
                            await self._send_embed(
                                state.channel_id,
                                "🚨 FiveM 伺服器崩潰",
                                "偵測到伺服器異常崩潰，請等待修復。",
                                "error",
                            )
                    elif not tx_status and not state.has_http:
                        state.ftp_fail_count += 1
                        now = time.time()
                        if now - state.ftp_last_alert >= 600:
                            mention_text = self._format_role_mentions(
                                guild, state.alert_role_ids
                            )
                            if mention_text:
                                mention_text = f"\n{mention_text}"
                            await self._send_embed(
                                state.channel_id,
                                "⚠️ FiveM 狀態異常",
                                "無法讀取 txAdmin 狀態檔（FTP/檔案）。請檢查連線或路徑設定。"
                                + mention_text,
                                "warning",
                            )
                            await self._dm_alert_roles(
                                guild,
                                state.alert_role_ids,
                                "⚠️ FiveM 狀態異常",
                                "無法讀取 txAdmin 狀態檔（FTP/檔案）。請檢查連線或路徑設定。",
                                "warning",
                            )
                            state.ftp_last_alert = now
            except Exception as exc:
                logger.error("FiveM 狀態輪詢失敗: %s", exc)

    @monitor_task.before_loop
    async def before_monitor(self):
        await self.bot.wait_until_ready()


async def setup(bot: commands.Bot):
    await bot.add_cog(FiveMStatusCore(bot))
