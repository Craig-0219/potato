"""
自動回覆功能：提及指定成員時回覆預設訊息。
"""

from __future__ import annotations

import time

import discord
from discord.ext import commands

from potato_bot.db.auto_reply_dao import AutoReplyDAO
from potato_shared.config import AUTO_REPLY_MENTIONS
from potato_shared.logger import logger


class AutoReplyCore(commands.Cog):
    """提及指定成員時自動回覆。"""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.dao = AutoReplyDAO()
        self._cache: dict[int, tuple[float, dict[int, str]]] = {}
        self._cache_ttl = 30.0

    async def _get_guild_rules(self, guild_id: int) -> dict[int, str]:
        now = time.monotonic()
        cached = self._cache.get(guild_id)
        if cached and (now - cached[0]) < self._cache_ttl:
            return cached[1]

        rules = await self.dao.list_rules(guild_id)
        mapping = {
            int(rule["target_user_id"]): str(rule.get("reply_text", ""))
            for rule in rules
            if rule.get("reply_text")
        }
        self._cache[guild_id] = (now, mapping)
        return mapping

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot:
            return
        if not message.raw_mentions:
            return

        reply_map = dict(AUTO_REPLY_MENTIONS)
        if message.guild:
            try:
                reply_map.update(await self._get_guild_rules(message.guild.id))
            except Exception as e:
                logger.error(f"讀取自動回覆設定失敗: {e}")

        if not reply_map:
            return

        replies = []
        seen = set()
        for user_id in message.raw_mentions:
            reply = reply_map.get(user_id)
            if not reply or reply in seen:
                continue
            seen.add(reply)
            replies.append(reply)

        if not replies:
            return

        try:
            await message.channel.send(
                "\n".join(replies),
                allowed_mentions=discord.AllowedMentions.none(),
            )
        except Exception as e:
            logger.error(f"自動回覆失敗: {e}")


async def setup(bot: commands.Bot):
    await bot.add_cog(AutoReplyCore(bot))
