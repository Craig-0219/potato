"""System settings service for shared custom configuration."""

from typing import Any, Dict, List

from potato_bot.db.welcome_dao import WelcomeDAO


class SystemSettingsService:
    """讀寫 system_settings.custom_settings 的封裝服務"""

    def __init__(self) -> None:
        self.dao = WelcomeDAO()

    async def get_custom_settings(self, guild_id: int) -> Dict[str, Any]:
        settings = await self.dao.get_system_settings(guild_id)
        if not settings:
            return {}
        return settings.get("custom_settings", {}) or {}

    async def update_custom_settings(self, guild_id: int, patch: Dict[str, Any]) -> bool:
        current = await self.get_custom_settings(guild_id)
        merged = {**current, **patch}
        return await self.dao.update_system_settings(guild_id, "custom_settings", merged)

    async def get_admin_user_ids(self, guild_id: int) -> List[int]:
        custom = await self.get_custom_settings(guild_id)
        raw = custom.get("admin_user_ids", []) or []
        return [int(user_id) for user_id in raw if str(user_id).isdigit()]
