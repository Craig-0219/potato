# bot/utils/command_translator.py
from __future__ import annotations

from typing import Optional

import discord
from discord import app_commands


class PotatoTranslator(app_commands.Translator):
    """指令名稱/描述的本地化翻譯器。"""

    _COMMAND_NAME_LOCALIZATIONS = {
        "company_roles": {
            discord.Locale.taiwan_chinese: "公司身分組",
            discord.Locale.chinese: "公司身份组",
        }
    }

    async def translate(
        self,
        string: app_commands.locale_str,
        locale: discord.Locale,
        context: app_commands.TranslationContext,
    ) -> Optional[str]:
        if context.location == app_commands.TranslationContextLocation.command_name:
            localized = self._COMMAND_NAME_LOCALIZATIONS.get(string.message)
            if localized:
                return localized.get(locale)
        return None
