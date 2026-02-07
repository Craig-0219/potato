"""Bot presence rotation and FiveM status integration."""

from __future__ import annotations

import asyncio
from typing import Optional

import discord

from potato_bot.services.system_settings_service import SystemSettingsService
from potato_shared.logger import logger


class PresenceManager:
    DEFAULT_INTERVAL = 30
    DEFAULT_MESSAGES = ["我爸不在，現在我最大!"]

    def __init__(self, bot: discord.Client) -> None:
        self.bot = bot
        self.settings_service = SystemSettingsService()
        self._task: Optional[asyncio.Task] = None
        self._interval: int = self.DEFAULT_INTERVAL
        self._messages: list[str] = []
        self._index: int = 0
        self._priority_text: Optional[str] = None
        self._last_text: Optional[str] = None
        self._wake_event = asyncio.Event()
        self._guild_id: Optional[int] = None

    def start(self) -> None:
        if self._task and not self._task.done():
            return
        if hasattr(self.bot, "create_background_task"):
            self._task = self.bot.create_background_task(self._run(), name="presence-rotator")
        else:
            self._task = asyncio.create_task(self._run(), name="presence-rotator")

    async def stop(self) -> None:
        if self._task:
            self._task.cancel()
            self._task = None

    async def notify_fivem_update(self, guild_id: int, text: str) -> None:
        if not text:
            return
        if self._guild_id and guild_id != self._guild_id:
            return
        self._priority_text = text
        self._wake_event.set()

    async def refresh_settings(self, guild_id: Optional[int] = None) -> None:
        if guild_id:
            self._guild_id = guild_id
        self._wake_event.set()

    async def _run(self) -> None:
        await self.bot.wait_until_ready()
        while not self.bot.is_closed():
            try:
                guild = await self._get_target_guild()
                if guild:
                    await self._load_settings(guild.id)
                    message = await self._build_next_message(guild)
                    if message:
                        await self._apply_presence(message)
                self._wake_event.clear()
                await asyncio.wait_for(self._wake_event.wait(), timeout=self._interval)
            except asyncio.TimeoutError:
                continue
            except asyncio.CancelledError:
                return
            except Exception as exc:
                logger.warning("Presence 迴圈錯誤: %s", exc)
                await asyncio.sleep(5)

    async def _get_target_guild(self) -> Optional[discord.Guild]:
        if self._guild_id:
            guild = self.bot.get_guild(self._guild_id)
            if guild:
                return guild
            self._guild_id = None

        for guild in self.bot.guilds:
            custom = await self.settings_service.get_custom_settings(guild.id)
            if custom.get("presence_messages") or custom.get("presence_interval"):
                self._guild_id = guild.id
                return guild

        if self.bot.guilds:
            return self.bot.guilds[0]
        return None

    async def _load_settings(self, guild_id: int) -> None:
        custom = await self.settings_service.get_custom_settings(guild_id)
        raw_interval = custom.get("presence_interval")
        try:
            interval = int(raw_interval) if raw_interval else self.DEFAULT_INTERVAL
        except (TypeError, ValueError):
            interval = self.DEFAULT_INTERVAL
        if interval < 3:
            interval = 3
        self._interval = interval

        raw_messages = custom.get("presence_messages") or []
        if isinstance(raw_messages, str):
            messages = [line.strip() for line in raw_messages.splitlines() if line.strip()]
        elif isinstance(raw_messages, list):
            messages = [str(line).strip() for line in raw_messages if str(line).strip()]
        else:
            messages = []
        self._messages = messages or self.DEFAULT_MESSAGES

        if self._index >= len(self._messages):
            self._index = 0

    async def _build_next_message(self, guild: discord.Guild) -> Optional[str]:
        if self._priority_text:
            text = self._priority_text
            self._priority_text = None
            return text

        fivem_text = await self._get_fivem_text(guild)
        messages = []
        if fivem_text:
            messages.append(fivem_text)
        messages.extend(self._messages)

        if not messages:
            return None

        if self._index >= len(messages):
            self._index = 0
        text = messages[self._index]
        self._index = (self._index + 1) % len(messages)
        return text

    async def _get_fivem_text(self, guild: discord.Guild) -> Optional[str]:
        fivem_cog = getattr(self.bot, "get_cog", lambda name: None)("FiveMStatusCore")
        if not fivem_cog or not hasattr(fivem_cog, "get_presence_text"):
            return None
        try:
            return await fivem_cog.get_presence_text(guild)
        except Exception:
            return None

    async def _apply_presence(self, text: str) -> None:
        value = text.strip()
        if not value:
            return
        if value == self._last_text:
            return
        activity = discord.Activity(type=discord.ActivityType.watching, name=value[:128])
        try:
            await self.bot.change_presence(activity=activity)
            self._last_text = value
        except Exception as exc:
            logger.warning("更新狀態欄位失敗: %s", exc)
