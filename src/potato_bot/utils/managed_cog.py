"""
Managed Cog utilities

- ManagedCog: tracks background tasks created via `create_task` and cancels them on unload
- register_persistent_view: idempotent persistent view registration to avoid duplicate add_view on reload
"""

import asyncio
from typing import Coroutine, Optional, Set

import discord
from discord.ext import commands


class ManagedCog(commands.Cog):
    """Cog base that manages background tasks for hot-reload safety."""

    def __init__(self, bot: commands.Bot):
        super().__init__()
        self.bot = bot
        self._managed_tasks: Set[asyncio.Task] = set()

    def create_task(self, coro: Coroutine, *, name: Optional[str] = None) -> asyncio.Task:
        """Create and track a background task that will be cancelled on cog_unload."""
        task = asyncio.create_task(coro, name=name)
        self._managed_tasks.add(task)
        task.add_done_callback(self._managed_tasks.discard)
        return task

    def cog_unload(self) -> None:
        for task in list(self._managed_tasks):
            if not task.done():
                task.cancel()
        self._managed_tasks.clear()
        maybe = super().cog_unload()
        if asyncio.iscoroutine(maybe):
            # discord.py 2.4+ may return a coroutine; ignore/await not needed for older versions
            asyncio.create_task(maybe)


def register_persistent_view(
    bot: discord.Client,
    view: discord.ui.View,
    key: Optional[str] = None,
) -> bool:
    """
    Idempotently register a persistent view to avoid duplicate add_view during cog reloads.

    Returns True if the view was registered this call, False if it was already registered.
    """
    registry: Set[str] = getattr(bot, "_persistent_view_registry", set())
    key = key or type(view).__name__

    if key in registry:
        return False

    # discord.py <2.4 may not accept `persistent` kw; all our views here are persistent-capable.
    try:
        bot.add_view(view, persistent=True)  # type: ignore[arg-type]
    except TypeError:
        bot.add_view(view)
    registry.add(key)
    setattr(bot, "_persistent_view_registry", registry)
    return True
