# bot/utils/localization.py - 多語言指令支援工具
"""
多語言指令支援工具
提供動態語言切換和指令描述本地化
"""

from functools import wraps
from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands

from bot.db.language_dao import LanguageDAO
from bot.services.language_manager import LanguageManager
from shared.logger import logger


class LocalizedCommand:
    """本地化指令裝飾器"""

    def __init__(self):
        self.language_manager = LanguageManager()
        self.language_dao = LanguageDAO()

    def command(self, name_key: str, description_key: str, **kwargs):
        """創建支持多語言的斜線指令裝飾器"""

        def decorator(func):
            # 使用預設語言創建指令
            default_lang = self.language_manager.default_language

            # 從語言包獲取名稱和描述
            name = (
                self.language_manager.get_string(f"commands.names.{name_key}", default_lang)
                or name_key
            )
            description = self.language_manager.get_string(
                f"commands.descriptions.{description_key}", default_lang
            )

            # 創建 app_commands.command 裝飾器
            command_decorator = app_commands.command(name=name, description=description, **kwargs)

            @wraps(func)
            async def wrapper(interaction: discord.Interaction, *args, **kwargs):
                # 獲取用戶語言設定
                try:
                    user_lang_info = await self.language_dao.get_user_language(
                        user_id=interaction.user.id,
                        guild_id=(interaction.guild.id if interaction.guild else None),
                    )

                    user_lang = user_lang_info["language_code"] if user_lang_info else default_lang

                    # 將語言代碼添加到 interaction 中供指令使用
                    interaction.user_language = user_lang

                except Exception as e:
                    logger.error(f"獲取用戶語言設定錯誤: {e}")
                    interaction.user_language = default_lang

                # 執行原始指令
                return await func(interaction, *args, **kwargs)

            # 應用裝飾器
            return command_decorator(wrapper)

        return decorator

    def group(self, name_key: str, description_key: str, **kwargs):
        """創建支持多語言的指令群組裝飾器"""

        def decorator(func):
            # 使用預設語言創建指令群組
            default_lang = self.language_manager.default_language

            name = (
                self.language_manager.get_string(f"commands.names.{name_key}", default_lang)
                or name_key
            )
            description = self.language_manager.get_string(
                f"commands.descriptions.{description_key}", default_lang
            )

            # 創建 app_commands.Group
            group_decorator = app_commands.Group(name=name, description=description, **kwargs)

            @wraps(func)
            async def wrapper(interaction: discord.Interaction, *args, **kwargs):
                # 獲取用戶語言設定
                try:
                    user_lang_info = await self.language_dao.get_user_language(
                        user_id=interaction.user.id,
                        guild_id=(interaction.guild.id if interaction.guild else None),
                    )

                    user_lang = user_lang_info["language_code"] if user_lang_info else default_lang
                    interaction.user_language = user_lang

                except Exception as e:
                    logger.error(f"獲取用戶語言設定錯誤: {e}")
                    interaction.user_language = default_lang

                return await func(interaction, *args, **kwargs)

            return group_decorator(wrapper)

        return decorator


class LocalizedResponse:
    """本地化回應工具"""

    def __init__(self):
        self.language_manager = LanguageManager()
        self.language_dao = LanguageDAO()

    async def get_user_language(self, user_id: int, guild_id: Optional[int] = None) -> str:
        """獲取用戶語言設定"""
        try:
            user_lang_info = await self.language_dao.get_user_language(user_id, guild_id)
            return (
                user_lang_info["language_code"]
                if user_lang_info
                else self.language_manager.default_language
            )
        except Exception as e:
            logger.error(f"獲取用戶語言設定錯誤: {e}")
            return self.language_manager.default_language

    def get_text(self, key: str, lang_code: str, **kwargs) -> str:
        """獲取本地化文字"""
        return self.language_manager.get_string(key, lang_code, **kwargs)

    async def create_embed(
        self,
        interaction: discord.Interaction,
        title_key: str,
        description_key: str = None,
        color: int = 0x3498DB,
        **kwargs,
    ) -> discord.Embed:
        """創建本地化的 Embed"""
        user_lang = getattr(
            interaction,
            "user_language",
            self.language_manager.default_language,
        )

        title = self.get_text(title_key, user_lang, **kwargs)

        embed = discord.Embed(title=title, color=color)

        if description_key:
            description = self.get_text(description_key, user_lang, **kwargs)
            embed.description = description

        return embed

    async def send_localized_response(
        self,
        interaction: discord.Interaction,
        message_key: str,
        ephemeral: bool = False,
        embed: bool = True,
        **kwargs,
    ) -> None:
        """發送本地化回應"""
        user_lang = getattr(
            interaction,
            "user_language",
            self.language_manager.default_language,
        )
        message = self.get_text(message_key, user_lang, **kwargs)

        if embed:
            color = (
                0x28A745
                if "success" in message_key
                else 0xDC3545 if "error" in message_key else 0x3498DB
            )
            embed_obj = discord.Embed(description=message, color=color)

            if interaction.response.is_done():
                await interaction.followup.send(embed=embed_obj, ephemeral=ephemeral)
            else:
                await interaction.response.send_message(embed=embed_obj, ephemeral=ephemeral)
        else:
            if interaction.response.is_done():
                await interaction.followup.send(message, ephemeral=ephemeral)
            else:
                await interaction.response.send_message(message, ephemeral=ephemeral)


class CommandReloader:
    """指令重新載入器，用於語言更新後重新註冊指令"""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.language_manager = LanguageManager()

    async def reload_command_descriptions(self, guild_id: Optional[int] = None):
        """重新載入指令描述（需要重新同步指令樹）"""
        try:
            # 這需要重新同步整個指令樹，比較耗費資源
            # 建議只在伺服器設定變更時使用

            if guild_id:
                guild = discord.Object(id=guild_id)
                await self.bot.tree.sync(guild=guild)
                logger.info(f"已為伺服器 {guild_id} 重新同步指令樹")
            else:
                await self.bot.tree.sync()
                logger.info("已重新同步全域指令樹")

        except Exception as e:
            logger.error(f"重新載入指令描述錯誤: {e}")

    async def update_command_for_user(self, user_id: int, guild_id: Optional[int] = None):
        """為特定用戶更新指令（Discord 不支持，只能記錄語言變更）"""
        try:
            # Discord 不支援為特定用戶更新指令描述
            # 我們只能在指令執行時動態處理語言
            logger.info(f"用戶 {user_id} 在伺服器 {guild_id} 更新語言設定")

        except Exception as e:
            logger.error(f"更新用戶指令錯誤: {e}")


# 全域實例
localized_command = LocalizedCommand()
localized_response = LocalizedResponse()


def get_user_text(interaction: discord.Interaction, key: str, **kwargs) -> str:
    """快速獲取用戶語言的文字"""
    user_lang = getattr(interaction, "user_language", "zh-TW")
    return localized_response.get_text(key, user_lang, **kwargs)


def create_localized_embed(
    interaction: discord.Interaction,
    title_key: str,
    description_key: str = None,
    color: int = 0x3498DB,
    **kwargs,
) -> discord.Embed:
    """快速創建本地化 Embed"""
    user_lang = getattr(interaction, "user_language", "zh-TW")

    title = localized_response.get_text(title_key, user_lang, **kwargs)
    embed = discord.Embed(title=title, color=color)

    if description_key:
        description = localized_response.get_text(description_key, user_lang, **kwargs)
        embed.description = description

    return embed
