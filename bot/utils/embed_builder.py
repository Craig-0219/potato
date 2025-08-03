# bot/utils/embed_builder.py

import discord
from datetime import datetime

class EmbedBuilder:

    @staticmethod
    def success(title: str, description: str = None) -> discord.Embed:
        return EmbedBuilder._build(title, description, discord.Color.green())

    @staticmethod
    def error(title: str, description: str = None) -> discord.Embed:
        return EmbedBuilder._build(title, description, discord.Color.red())

    @staticmethod
    def info(title: str, description: str = None) -> discord.Embed:
        return EmbedBuilder._build(title, description, discord.Color.blue())

    @staticmethod
    def warning(title: str, description: str = None) -> discord.Embed:
        return EmbedBuilder._build(title, description, discord.Color.orange())

    @staticmethod
    def _build(title: str, description: str, color: discord.Color) -> discord.Embed:
        embed = discord.Embed(
            title=title,
            description=description or "",
            color=color,
            timestamp=datetime.utcnow()
        )
        return embed
