import asyncio
import time
from dataclasses import dataclass, field
from typing import Optional

import discord
from discord.ext import commands, tasks

from potato_bot.db.fivem_dao import FiveMDAO
from potato_bot.services.fivem_status_service import FiveMStatusService, FiveMStatusResult
from potato_bot.utils.embed_builder import EmbedBuilder
from potato_shared.config import (
    FIVEM_OFFLINE_THRESHOLD,
    FIVEM_POLL_INTERVAL,
    FIVEM_RESTART_NOTIFY_SECONDS,
    FIVEM_STARTING_GRACE_SECONDS,
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
    dm_role_ids: list[int] = field(default_factory=list)
    panel_message_id: int = 0
    server_link: Optional[str] = None
    status_image_url: Optional[str] = None
    last_status: Optional[str] = None
    last_result: Optional[FiveMStatusResult] = None
    last_tx_state: Optional[str] = None
    last_event_type: Optional[str] = None
    last_presence_state: Optional[str] = None
    last_panel_signature: Optional[str] = None
    last_panel_status_label: Optional[str] = None
    last_announced_event_type: Optional[str] = None
    last_announced_tx_state: Optional[str] = None
    last_api_poll_at: float = 0.0
    starting_until: float = 0.0
    stop_override_until: float = 0.0
    stop_override_type: Optional[str] = None
    ftp_fail_count: int = 0
    ftp_last_alert: float = 0.0
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)


class FiveMStatusCore(commands.Cog):
    """Server狀態播報"""

    STOP_DISPLAY_SECONDS = 15
    TX_EVENT_ALLOWED = {"serverStarting", "serverStopping"}
    TX_STATE_ALLOWED = {"starting", "stopping"}
    PANEL_ANNOUNCE_MAP = {
        "🟢 在線": ("✅ Server已啟動", "伺服器已成功啟動。", "success"),
        "🔴 離線": ("🔴 Server已關閉", "伺服器已關閉或無法連線。", "error"),
        "🟡 啟動中": ("🟡 Server啟動中", "伺服器正在啟動中，請稍候。", "warning"),
        "🟠 關閉中": ("🟠 Server準備停止", "伺服器即將停止，請注意保存進度。", "warning"),
    }

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.dao = FiveMDAO()
        self._guild_states: dict[int, _FiveMGuildState] = {}
        self._settings_cache: dict[int, tuple[Optional[str], Optional[str], int]] = {}
        self._warned_missing: set[int] = set()
        self._api_poll_interval = max(3, int(FIVEM_POLL_INTERVAL or 3))
        self.monitor_task.start()
        logger.info("✅ FiveM 狀態播報已啟動（使用資料庫設定）")

    def cog_unload(self):
        if self.monitor_task.is_running():
            self.monitor_task.cancel()
        for state in list(self._guild_states.values()):
            asyncio.create_task(state.service.close())
        self._guild_states.clear()
        self._settings_cache.clear()

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
        self,
        channel_id: int,
        title: str,
        description: str,
        color: str = "info",
        content: Optional[str] = None,
        allowed_mentions: Optional[discord.AllowedMentions] = None,
        delete_after: Optional[float] = None,
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
        if delete_after is None:
            delete_after = 30

        try:
            await channel.send(
                content=content,
                embed=embed,
                allowed_mentions=allowed_mentions,
                delete_after=delete_after,
            )
        except Exception as exc:
            logger.warning("FiveM 播報發送失敗: %s", exc)

    async def _resolve_settings(self, guild_id: int) -> tuple[Optional[str], Optional[str], int]:
        settings = await self.dao.get_fivem_settings(guild_id)
        info_url = ""
        players_url = ""
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

    @staticmethod
    def _get_status_label(
        result: Optional[FiveMStatusResult],
        event_type: Optional[str],
        tx_state: Optional[str] = None,
    ) -> str:
        event_type = FiveMStatusCore._normalize_event_type(event_type)
        if event_type and event_type not in FiveMStatusCore.TX_EVENT_ALLOWED:
            event_type = None
        if tx_state and tx_state not in FiveMStatusCore.TX_STATE_ALLOWED:
            tx_state = None
        event_map = {
            "serverStarting": "🟡 啟動中",
            "serverStopping": "🟠 關閉中",
        }
        if result and result.status == "offline":
            return "🔴 離線"
        if event_type in ("serverStarting", "serverStopping"):
            return event_map[event_type]

        if result:
            if result.status == "online":
                return "🟢 在線"

        if tx_state == "starting":
            return "🟡 啟動中"
        if tx_state == "stopping":
            return "🟠 關閉中"

        if event_type in event_map:
            return event_map[event_type]
        return "❓ 未知"

    @staticmethod
    def _normalize_event_type(event_type: Optional[str]) -> Optional[str]:
        if not event_type:
            return None
        mapping = {
            "resourceStart": "serverStarting",
            "resourceStarted": "serverStarting",
            "resourceStopping": "serverStopping",
            "serverShuttingDown": "serverStopping",
            "serverStarted": "serverStarting",
            "serverStarting": "serverStarting",
            "serverStopping": "serverStopping",
        }
        return mapping.get(event_type, event_type)

    @staticmethod
    def _build_panel_signature(
        result: Optional[FiveMStatusResult],
        event_type: Optional[str],
        event_updated_at: Optional[str],
        tx_state: Optional[str],
        server_link: Optional[str],
        status_label: Optional[str],
        status_image_url: Optional[str],
    ) -> str:
        players = result.players if result else None
        max_players = result.max_players if result else None
        hostname = result.hostname if result else None
        return "|".join(
            [
                str(event_type or ""),
                str(event_updated_at or ""),
                str(tx_state or ""),
                str(server_link or ""),
                str(status_label or ""),
                str(status_image_url or ""),
                str(players or ""),
                str(max_players or ""),
                str(hostname or ""),
                str(result.info_ok if result else ""),
                str(result.players_ok if result else ""),
                str(result.status if result else ""),
            ]
        )

    @staticmethod
    def _build_status_panel_embed(
        guild: discord.Guild,
        result: Optional[FiveMStatusResult],
        event_type: Optional[str],
        event_updated_at: Optional[str],
        tx_state: Optional[str],
        status_label: Optional[str] = None,
        status_image_url: Optional[str] = None,
    ) -> discord.Embed:
        embed = discord.Embed(
            title="🛰️ Server 狀態面板",
            description="城市最新狀態",
            color=0x3498DB,
        )
        if not status_label:
            status_label = FiveMStatusCore._get_status_label(result, event_type, tx_state)
        embed.add_field(name="狀態", value=status_label, inline=True)

        if result and getattr(result, "players_ok", True):
            if result.max_players:
                player_text = f"{result.players}/{result.max_players}"
            else:
                player_text = f"{result.players}"
            embed.add_field(name="玩家", value=player_text, inline=True)

        if result and result.hostname:
            embed.add_field(name="伺服器", value=result.hostname, inline=False)
        else:
            embed.add_field(name="伺服器", value=guild.name, inline=False)

        if status_image_url:
            url = status_image_url.strip()
            if url.startswith("http://") or url.startswith("https://"):
                embed.set_image(url=url)

        now_dt = discord.utils.utcnow()
        embed.add_field(name="最後更新", value=discord.utils.format_dt(now_dt, "f"), inline=True)
        return embed

    @staticmethod
    def _build_status_panel_view(server_link: Optional[str]) -> Optional[discord.ui.View]:
        if not server_link:
            return None
        link = server_link.strip()
        if not link:
            return None
        if not (link.startswith("http://") or link.startswith("https://")):
            return None

        view = discord.ui.View(timeout=None)
        view.add_item(
            discord.ui.Button(
                label="🔗 連線伺服器",
                style=discord.ButtonStyle.link,
                url=link,
            )
        )
        return view

    def _compute_panel_status_label(
        self,
        state: _FiveMGuildState,
        result: Optional[FiveMStatusResult],
        tx_status: Optional[dict],
        now_ts: Optional[float] = None,
    ) -> str:
        event_type = None
        tx_state = None
        if isinstance(tx_status, dict):
            event = tx_status.get("event") or {}
            event_type = self._normalize_event_type(event.get("type"))
            tx_state = self._normalize_status(tx_status.get("state"))
            if event_type and event_type not in self.TX_EVENT_ALLOWED:
                event_type = None
            if tx_state and tx_state not in self.TX_STATE_ALLOWED:
                tx_state = None

        now_value = now_ts if now_ts is not None else time.time()
        starting_event = event_type == "serverStarting" or tx_state == "starting"
        if starting_event:
            if (state.starting_until and now_value < state.starting_until) or (
                not result or result.status != "online"
            ):
                return "🟡 啟動中"
            event_type = None
            tx_state = None

        if result and (event_type == "serverStopping" or tx_state == "stopping"):
            if not result.info_ok or not result.players_ok:
                return "🔴 離線"

        status_label = self._get_status_label(result, event_type, tx_state)
        if state.starting_until and now_value < state.starting_until:
            if not result or result.status != "online":
                status_label = "🟡 啟動中"
        return status_label

    async def _announce_panel_status(
        self,
        state: _FiveMGuildState,
        status_label: str,
        mention_text: str,
        allowed_mentions: Optional[discord.AllowedMentions],
    ) -> None:
        payload = self.PANEL_ANNOUNCE_MAP.get(status_label)
        if not payload:
            return
        title, description, color = payload
        await self._send_embed(
            state.channel_id,
            title,
            description,
            color,
            content=mention_text if mention_text else None,
            allowed_mentions=allowed_mentions,
        )

    async def _update_status_panel(
        self,
        guild: discord.Guild,
        state: _FiveMGuildState,
        result: Optional[FiveMStatusResult],
        tx_status: Optional[dict],
        status_label: Optional[str] = None,
        force: bool = False,
    ) -> None:
        channel = await self._get_channel(state.channel_id)
        if not channel:
            return

        event_type = None
        event_updated_at = None
        tx_state = None
        if isinstance(tx_status, dict):
            event = tx_status.get("event") or {}
            event_type = self._normalize_event_type(event.get("type"))
            event_updated_at = tx_status.get("updated_at")
            tx_state = self._normalize_status(tx_status.get("state"))
            if event_type and event_type not in self.TX_EVENT_ALLOWED:
                event_type = None
            if tx_state and tx_state not in self.TX_STATE_ALLOWED:
                tx_state = None

        if not status_label:
            status_label = self._get_status_label(result, event_type, tx_state)
            if state.starting_until and time.time() < state.starting_until:
                if not result or result.status != "online":
                    status_label = "🟡 啟動中"
        signature = self._build_panel_signature(
            result,
            event_type,
            str(event_updated_at or ""),
            tx_state,
            state.server_link,
            status_label,
            state.status_image_url,
        )
        if not force and state.last_panel_signature == signature:
            return

        embed = self._build_status_panel_embed(
            guild,
            result,
            event_type,
            str(event_updated_at or ""),
            tx_state,
            status_label,
            state.status_image_url,
        )
        view = self._build_status_panel_view(state.server_link)

        message = None
        if state.panel_message_id:
            try:
                message = await channel.fetch_message(state.panel_message_id)
            except Exception:
                message = None

        if message:
            try:
                await message.edit(embed=embed, view=view)
            except Exception as exc:
                logger.warning("更新 FiveM 狀態面板失敗: %s", exc)
        else:
            try:
                message = await channel.send(embed=embed, view=view)
                state.panel_message_id = message.id
                await self.dao.update_panel_message_id(guild.id, message.id)
            except Exception as exc:
                logger.warning("建立 FiveM 狀態面板失敗: %s", exc)
                return

        state.last_panel_signature = signature

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
            "restarting": "restarting",
        }
        return mapping.get(status, None)

    @staticmethod
    def _get_presence_state(state: _FiveMGuildState) -> Optional[str]:
        if state.last_event_type == "serverCrashed" or state.last_tx_state == "crashed":
            return "crashed"
        if state.last_status == "offline" or state.last_tx_state in ("stopping", "offline", "stopped"):
            return "offline"
        if state.last_status == "online":
            return "online"
        return None

    @staticmethod
    def _format_presence_text(state: _FiveMGuildState, presence_state: Optional[str]) -> Optional[str]:
        if presence_state == "crashed":
            return "伺服器崩潰"
        if presence_state == "offline":
            return "伺服器關閉"
        if presence_state == "online":
            players = 0
            if state.last_result:
                players = state.last_result.players
            return f"福北市城內人數 {players}"
        return None

    async def _notify_presence(self, guild: discord.Guild, text: Optional[str]) -> None:
        if not text:
            return
        manager = getattr(self.bot, "presence_manager", None)
        if manager and hasattr(manager, "notify_fivem_update"):
            await manager.notify_fivem_update(guild.id, text)

    async def get_presence_text(self, guild: discord.Guild) -> Optional[str]:
        """提供狀態欄位顯示用的 FiveM 文字"""
        state = await self._get_state(guild)
        if not state:
            return None
        presence_state = self._get_presence_state(state)
        return self._format_presence_text(state, presence_state)

    async def get_ftp_connection_status(self, guild: discord.Guild) -> Optional[bool]:
        """取得 FTP 連線狀態（None 表示未啟用或不可用）"""
        try:
            state = await self._get_state(guild)
            if not state:
                return None
            return state.service.is_ftp_connected()
        except Exception:
            return None

    async def get_txadmin_read_status(self, guild: discord.Guild) -> Optional[dict]:
        """取得 txAdmin 狀態檔讀取狀態"""
        try:
            state = await self._get_state(guild)
            if not state:
                return None
            return state.service.get_txadmin_read_status()
        except Exception:
            return None

    async def get_txadmin_payload(self, guild: discord.Guild) -> Optional[dict]:
        """取得最後一次成功讀取的 txAdmin JSON"""
        try:
            state = await self._get_state(guild)
            if not state:
                return None
            return state.service.get_last_txadmin_payload()
        except Exception:
            return None

    async def get_txadmin_payload_at(self, guild: discord.Guild) -> Optional[float]:
        """取得最後一次成功讀取 txAdmin JSON 的時間戳"""
        try:
            state = await self._get_state(guild)
            if not state:
                return None
            return state.service.get_last_txadmin_payload_at()
        except Exception:
            return None

    async def get_status_snapshot(self, guild: discord.Guild) -> Optional[dict]:
        """取得 FiveM/API 與 txAdmin 的快照狀態（不觸發輪詢）"""
        try:
            state = await self._get_state(guild)
            if not state:
                return None
            result = state.last_result
            tx_status = None
            if state.last_event_type or state.last_tx_state:
                tx_status = {
                    "event": {"type": state.last_event_type},
                    "state": state.last_tx_state,
                }
            panel_status = self._compute_panel_status_label(state, result, tx_status)
            read_status = state.service.get_txadmin_read_status()
            tx_last_at = read_status.get("last_read_at") if read_status else None
            return {
                "api_status": result.status if result else None,
                "players": result.players if result else None,
                "max_players": result.max_players if result else None,
                "api_last_at": state.last_api_poll_at or None,
                "tx_event": state.last_event_type,
                "tx_state": state.last_tx_state,
                "tx_last_at": tx_last_at,
                "panel_status": panel_status,
            }
        except Exception:
            return None

    async def reload_guild(self, guild: discord.Guild) -> bool:
        """重新讀取指定伺服器的 FiveM 設定並重建連線"""
        try:
            state = self._guild_states.pop(guild.id, None)
            if state:
                async with state.lock:
                    await state.service.close()
            self._settings_cache.pop(guild.id, None)
            self._warned_missing.discard(guild.id)
            new_state = await self._get_state(guild)
            return new_state is not None
        except Exception as exc:
            logger.warning("重讀 FiveM Core 失敗: %s", exc)
            return False

    async def deploy_status_panel(self, guild: discord.Guild) -> bool:
        """手動部署或更新狀態面板"""
        state = await self._get_state(guild)
        if not state:
            return False

        result = None
        if state.has_http:
            result = await state.service.poll_status()
        tx_status = await state.service.read_txadmin_status()

        await self._update_status_panel(guild, state, result, tx_status, force=True)
        return True

    async def _get_state(self, guild: discord.Guild) -> Optional[_FiveMGuildState]:
        if getattr(self.bot, "is_closing", False):
            return None
        settings = await self.dao.get_fivem_settings(guild.id)
        info_url = (settings.get("info_url") or "").strip() or None
        players_url = (settings.get("players_url") or "").strip() or None
        channel_id = int(settings.get("status_channel_id") or 0)
        alert_role_ids = settings.get("alert_role_ids", []) or []
        dm_role_ids = settings.get("dm_role_ids", []) or []
        panel_message_id = int(settings.get("panel_message_id") or 0)
        poll_interval = settings.get("poll_interval")
        server_link = settings.get("server_link")
        status_image_url = settings.get("status_image_url")
        has_http = bool(info_url and players_url)
        txadmin_enabled = self._txadmin_enabled()
        cache_key = (info_url, players_url, channel_id)

        try:
            poll_interval_value = int(poll_interval) if poll_interval else 0
        except (TypeError, ValueError):
            poll_interval_value = 0
        if poll_interval_value < 3:
            poll_interval_value = int(FIVEM_POLL_INTERVAL or 3)

        if poll_interval_value != self._api_poll_interval:
            self._api_poll_interval = poll_interval_value

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

        if not txadmin_enabled and not has_http:
            if guild.id not in self._warned_missing:
                self._warned_missing.add(guild.id)
                logger.warning(
                    "⚠️ FiveM 狀態播報尚未設定（等待 txAdmin / API 設定）：%s (%s)",
                    guild.name,
                    guild.id,
                )

        self._warned_missing.discard(guild.id)

        if self._settings_cache.get(guild.id) != cache_key:
            self._settings_cache[guild.id] = cache_key
            if guild.id in self._guild_states:
                await self._guild_states[guild.id].service.close()
            service = FiveMStatusService(
                info_url=info_url or "",
                players_url=players_url or "",
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
                dm_role_ids=dm_role_ids,
                panel_message_id=panel_message_id,
                server_link=server_link,
                status_image_url=status_image_url,
            )

        state = self._guild_states.get(guild.id)
        if state:
            state.channel_id = channel_id
            state.has_http = has_http
            state.alert_role_ids = alert_role_ids
            state.dm_role_ids = dm_role_ids
            state.panel_message_id = panel_message_id
            state.server_link = server_link
            state.status_image_url = status_image_url
        return state

    @tasks.loop(seconds=1.5)
    async def monitor_task(self):
        if getattr(self.bot, "is_closing", False):
            return
        if not self.bot.guilds:
            return

        for guild in list(self.bot.guilds):
            try:
                now = time.time()
                state = await self._get_state(guild)
                if not state:
                    continue

                async with state.lock:
                    mention_text = self._format_role_mentions(guild, state.alert_role_ids)
                    allowed_mentions = (
                        discord.AllowedMentions(roles=True) if mention_text else None
                    )
                    panel_result: Optional[FiveMStatusResult] = state.last_result
                    previous_api_status = state.last_result.status if state.last_result else None
                    event_type = None
                    tx_state = None
                    previous_status = state.last_status

                    previous_event_type = state.last_event_type
                    previous_tx_state = state.last_tx_state
                    tx_status = await state.service.read_txadmin_status()
                    panel_tx_status = tx_status
                    if tx_status:
                        state.ftp_fail_count = 0
                        event_type = self._normalize_event_type(
                            state.service.get_txadmin_event_type(tx_status)
                        )
                        tx_state = self._normalize_status(tx_status.get("state"))
                        if event_type and event_type not in self.TX_EVENT_ALLOWED:
                            event_type = None
                        if tx_state and tx_state not in self.TX_STATE_ALLOWED:
                            tx_state = None
                        state.last_event_type = event_type
                        state.last_tx_state = tx_state
                        if event_type != previous_event_type or tx_state != previous_tx_state:
                            state.last_panel_signature = None
                        if event_type == "serverStarting" or tx_state == "starting":
                            now = time.time()
                            state.starting_until = max(
                                state.starting_until, now + FIVEM_STARTING_GRACE_SECONDS
                            )
                            state.last_status = "starting"
                            if state.stop_override_until:
                                state.stop_override_until = 0.0
                                state.stop_override_type = None

                        if event_type == "serverStopping":
                            now = time.time()
                            state.stop_override_until = max(
                                state.stop_override_until, now + self.STOP_DISPLAY_SECONDS
                            )
                            state.stop_override_type = event_type

                        if event_type == "serverStopping" or tx_state == "stopping":
                            state.last_status = "stopping"
                    else:
                        state.last_event_type = None
                        state.last_tx_state = None
                        state.last_announced_event_type = None
                        state.last_announced_tx_state = None
                        if state.stop_override_until and time.time() >= state.stop_override_until:
                            state.stop_override_until = 0.0
                            state.stop_override_type = None

                    starting_active = bool(state.starting_until and time.time() < state.starting_until)

                    if state.has_http:
                        if not state.last_api_poll_at or (now - state.last_api_poll_at) >= self._api_poll_interval:
                            result = await state.service.poll_status()
                            state.last_api_poll_at = now
                            panel_result = result
                            state.last_result = result
                            if result.status == "online":
                                stopping_now = tx_state in ("stopping", "offline", "crashed")
                                stopping_now = stopping_now or event_type in (
                                    "serverStopping",
                                    "serverStopped",
                                    "serverCrashed",
                                )
                                if not stopping_now:
                                    if starting_active:
                                        state.starting_until = 0.0
                                    state.last_status = "online"
                            elif result.status == "offline":
                                if not starting_active:
                                    should_skip = False
                                    if tx_status and state.service.should_announce_txadmin(tx_status):
                                        if event_type in ("serverStopping", "serverStopped", "serverCrashed"):
                                            should_skip = True
                                    if not should_skip:
                                        state.last_status = "offline"
                    else:
                        state.last_result = None

                    if state.stop_override_until and time.time() < state.stop_override_until:
                        if state.stop_override_type:
                            override = dict(panel_tx_status) if isinstance(panel_tx_status, dict) else {}
                            override_event = override.get("event") or {}
                            override["event"] = {**override_event, "type": state.stop_override_type}
                            override.setdefault("updated_at", int(time.time()))
                            panel_tx_status = override

                    panel_status_label = self._compute_panel_status_label(
                        state,
                        panel_result,
                        panel_tx_status,
                        now_ts=now,
                    )
                    if panel_status_label != state.last_panel_status_label:
                        await self._announce_panel_status(
                            state,
                            panel_status_label,
                            mention_text,
                            allowed_mentions,
                        )

                    presence_state = self._get_presence_state(state)
                    if presence_state and presence_state != state.last_presence_state:
                        state.last_presence_state = presence_state
                        presence_text = self._format_presence_text(state, presence_state)
                        await self._notify_presence(guild, presence_text)

                    if not tx_status and not state.has_http:
                        read_status = state.service.get_txadmin_read_status()
                        if read_status is not None:
                            state.ftp_fail_count += 1
                            now = time.time()
                            error_text = (read_status.get("error") or "").lower()
                            is_crash = "ftp_retries_exhausted" in error_text
                            if now - state.ftp_last_alert >= 600:
                                if is_crash:
                                    await self._send_embed(
                                        state.channel_id,
                                        "🚨 Server崩潰",
                                        "伺服器異常，已通知相關單位處理，請耐心等候，謝謝。",
                                        "error",
                                        content=mention_text if mention_text else None,
                                        allowed_mentions=allowed_mentions,
                                    )
                                    await self._dm_alert_roles(
                                        guild,
                                        state.dm_role_ids,
                                        "🚨 Server崩潰",
                                        "FTP 連線重試兩次仍失敗，判定伺服器異常崩潰。",
                                        "error",
                                    )
                                else:
                                    await self._send_embed(
                                        state.channel_id,
                                        "⚠️ Server 狀態異常",
                                        "伺服器異常，已通知相關單位處理，請耐心等候，謝謝。",
                                        "warning",
                                        content=mention_text if mention_text else None,
                                        allowed_mentions=allowed_mentions,
                                    )
                                    await self._dm_alert_roles(
                                        guild,
                                        state.dm_role_ids,
                                        "⚠️ Server 狀態異常",
                                        "無法讀取 txAdmin 狀態檔（FTP/檔案）。請檢查連線或路徑設定。",
                                        "warning",
                                    )
                                state.ftp_last_alert = now

                    await self._update_status_panel(
                        guild,
                        state,
                        panel_result,
                        panel_tx_status,
                        status_label=panel_status_label,
                        force=state.panel_message_id == 0,
                    )
                    state.last_panel_status_label = panel_status_label
            except Exception as exc:
                logger.error("FiveM 狀態輪詢失敗: %s", exc)

    @monitor_task.before_loop
    async def before_monitor(self):
        await self.bot.wait_until_ready()


async def setup(bot: commands.Bot):
    await bot.add_cog(FiveMStatusCore(bot))
