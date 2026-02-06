import asyncio
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
    last_status: Optional[str] = None
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)


class FiveMStatusCore(commands.Cog):
    """FiveM 伺服器狀態播報"""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.dao = FiveMDAO()
        self._guild_states: dict[int, _FiveMGuildState] = {}
        self._settings_cache: dict[int, tuple[Optional[str], Optional[str], int]] = {}
        self._warned_missing: set[int] = set()
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

    async def _get_state(self, guild: discord.Guild) -> Optional[_FiveMGuildState]:
        info_url, players_url, channel_id = await self._resolve_settings(guild.id)
        cache_key = (info_url, players_url, channel_id)

        if not info_url or not players_url or not channel_id:
            if guild.id not in self._warned_missing:
                self._warned_missing.add(guild.id)
                logger.warning(
                    "⚠️ FiveM 狀態播報尚未設定：%s (%s)",
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
            )
            self._guild_states[guild.id] = _FiveMGuildState(
                service=service,
                channel_id=channel_id,
            )

        return self._guild_states.get(guild.id)

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

                    tx_status = state.service.read_txadmin_status()
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
            except Exception as exc:
                logger.error("FiveM 狀態輪詢失敗: %s", exc)

    @monitor_task.before_loop
    async def before_monitor(self):
        await self.bot.wait_until_ready()


async def setup(bot: commands.Bot):
    await bot.add_cog(FiveMStatusCore(bot))
