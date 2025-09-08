"""
Discord ↔ Minecraft 聊天橋接系統
實現雙向聊天同步功能
"""

import re
from typing import Any, Dict, List

import discord

from potato_shared.logger import logger

from .rcon_manager import RCONManager


class ChatBridge:
    """Discord 與 Minecraft 聊天橋接管理器"""

    def __init__(self, bot, rcon_manager: RCONManager):
        self.bot = bot
        self.rcon = rcon_manager

        # 橋接設定
        self.bridge_enabled = False
        self.discord_channel_id = None
        self.minecraft_chat_filter = True  # 過濾特殊訊息

        # 訊息過濾規則
        self.filter_patterns = [
            r"^\[.*?\]",  # 忽略帶 [prefix] 的系統訊息
            r"Server thread/",  # 忽略伺服器執行緒訊息
            r"^\d{4}-\d{2}-\d{2}",  # 忽略時間戳開始的訊息
        ]

        # 避免無限循環的標記
        self._last_discord_message = None
        self._last_minecraft_message = None

    def enable_bridge(self, discord_channel_id: int) -> bool:
        """啟用聊天橋接"""
        try:
            self.discord_channel_id = discord_channel_id
            self.bridge_enabled = True
            logger.info(f"聊天橋接已啟用 - Discord 頻道: {discord_channel_id}")
            return True
        except Exception as e:
            logger.error(f"啟用聊天橋接失敗: {e}")
            return False

    def disable_bridge(self):
        """停用聊天橋接"""
        self.bridge_enabled = False
        self.discord_channel_id = None
        logger.info("聊天橋接已停用")

    async def send_to_minecraft(self, message: str, username: str = None) -> bool:
        """發送 Discord 訊息到 Minecraft"""
        try:
            if not self.bridge_enabled:
                return False

            # 格式化訊息
            if username:
                formatted_message = f"[Discord] {username}: {message}"
            else:
                formatted_message = f"[Discord] {message}"

            # 清理訊息內容
            clean_message = self._clean_discord_message(formatted_message)

            # 避免無限循環
            if clean_message == self._last_minecraft_message:
                return False

            # 發送到 Minecraft
            result = await self.rcon.broadcast_message(clean_message)

            if result["success"]:
                self._last_minecraft_message = clean_message
                logger.debug(f"Discord → Minecraft: {clean_message}")
                return True
            else:
                logger.error(f"發送到 Minecraft 失敗: {result.get('error', 'Unknown error')}")
                return False

        except Exception as e:
            logger.error(f"發送到 Minecraft 錯誤: {e}")
            return False

    async def send_to_discord(self, message: str, player_name: str = None) -> bool:
        """發送 Minecraft 訊息到 Discord"""
        try:
            if not self.bridge_enabled or not self.discord_channel_id:
                return False

            # 獲取 Discord 頻道
            channel = self.bot.get_channel(self.discord_channel_id)
            if not channel:
                logger.error(f"找不到 Discord 頻道: {self.discord_channel_id}")
                return False

            # 格式化訊息
            if player_name:
                formatted_message = f"**[Minecraft]** `{player_name}`: {message}"
            else:
                formatted_message = f"**[Minecraft]** {message}"

            # 避免無限循環
            if formatted_message == self._last_discord_message:
                return False

            # 發送到 Discord
            await channel.send(formatted_message)
            self._last_discord_message = formatted_message
            logger.debug(f"Minecraft → Discord: {formatted_message}")
            return True

        except Exception as e:
            logger.error(f"發送到 Discord 錯誤: {e}")
            return False

    async def handle_discord_message(self, message: discord.Message) -> bool:
        """處理來自 Discord 的訊息"""
        try:
            # 檢查是否為橋接頻道
            if not self.bridge_enabled or message.channel.id != self.discord_channel_id:
                return False

            # 忽略機器人訊息
            if message.author.bot:
                return False

            # 忽略包含 [Minecraft] 的訊息 (避免循環)
            if "[Minecraft]" in message.content:
                return False

            # 忽略空訊息或指令
            if not message.content or message.content.startswith("/"):
                return False

            # 發送到 Minecraft
            return await self.send_to_minecraft(message.content, message.author.display_name)

        except Exception as e:
            logger.error(f"處理 Discord 訊息錯誤: {e}")
            return False

    async def poll_minecraft_chat(self) -> List[Dict[str, str]]:
        """輪詢 Minecraft 聊天記錄 (需要插件支援或日誌監控)"""
        try:
            # 這裡需要實際的 Minecraft 聊天監控
            # 可能需要：
            # 1. Minecraft 插件支援
            # 2. 日誌檔案監控
            # 3. 特殊的 RCON 查詢指令

            # 暫時返回空列表，實際實施時需要根據具體環境調整
            return []

        except Exception as e:
            logger.error(f"輪詢 Minecraft 聊天失敗: {e}")
            return []

    def _clean_discord_message(self, message: str) -> str:
        """清理 Discord 訊息以適應 Minecraft"""
        try:
            # 移除 Discord 特殊標記
            cleaned = re.sub(r"<@!?(\d+)>", r"@\\1", message)  # @mentions
            cleaned = re.sub(r"<#(\d+)>", r"#\\1", cleaned)  # #channels
            cleaned = re.sub(r"<:(\w+):\d+>", r":\\1:", cleaned)  # :emojis:

            # 限制訊息長度
            if len(cleaned) > 100:
                cleaned = cleaned[:97] + "..."

            # 移除可能導致問題的字符
            cleaned = cleaned.replace("§", "")  # Minecraft 顏色代碼
            cleaned = cleaned.replace("\n", " ")  # 換行符

            return cleaned

        except Exception as e:
            logger.error(f"清理 Discord 訊息失敗: {e}")
            return message

    def _is_system_message(self, message: str) -> bool:
        """判斷是否為系統訊息"""
        if not self.minecraft_chat_filter:
            return False

        for pattern in self.filter_patterns:
            if re.match(pattern, message):
                return True

        return False

    def get_bridge_status(self) -> Dict[str, Any]:
        """獲取橋接狀態"""
        return {
            "enabled": self.bridge_enabled,
            "discord_channel_id": self.discord_channel_id,
            "chat_filter_enabled": self.minecraft_chat_filter,
            "last_discord_message": self._last_discord_message,
            "last_minecraft_message": self._last_minecraft_message,
        }

    def set_chat_filter(self, enabled: bool):
        """設置聊天過濾"""
        self.minecraft_chat_filter = enabled
        logger.info(f"聊天過濾已{'啟用' if enabled else '停用'}")

    def add_filter_pattern(self, pattern: str):
        """新增過濾規則"""
        try:
            re.compile(pattern)  # 驗證正則表達式
            self.filter_patterns.append(pattern)
            logger.info(f"新增過濾規則: {pattern}")
            return True
        except re.error as e:
            logger.error(f"無效的正則表達式 ({pattern}): {e}")
            return False

    def remove_filter_pattern(self, pattern: str):
        """移除過濾規則"""
        if pattern in self.filter_patterns:
            self.filter_patterns.remove(pattern)
            logger.info(f"移除過濾規則: {pattern}")
            return True
        return False
