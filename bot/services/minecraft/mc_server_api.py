"""
Minecraft Server API 整合模組
提供 Minecraft 伺服器狀態查詢、玩家資訊獲取等功能
"""

import asyncio
import aiohttp
from typing import Optional, Dict, List, Any
from datetime import datetime

from mcstatus import JavaServer
from shared.logger import logger
from shared.config import MINECRAFT_SERVER_HOST, MINECRAFT_SERVER_PORT


class MinecraftServerAPI:
    """Minecraft Server API 管理器"""

    def __init__(self):
        self.server_host = MINECRAFT_SERVER_HOST or "localhost"
        self.server_port = MINECRAFT_SERVER_PORT or 25565
        self.server = None

        # 狀態快取
        self._status_cache = None
        self._status_cache_time = None
        self._cache_timeout = 30  # 30秒快取

    async def connect(self) -> bool:
        """連接到 Minecraft 伺服器"""
        try:
            self.server = JavaServer.lookup(f"{self.server_host}:{self.server_port}")
            return True
        except Exception as e:
            logger.error(f"無法連接到 Minecraft 伺服器: {e}")
            return False

    async def get_server_status(self) -> Optional[Dict[str, Any]]:
        """獲取伺服器狀態"""
        try:
            # 檢查快取
            if self._is_cache_valid():
                return self._status_cache

            if not self.server:
                await self.connect()

            if not self.server:
                return None

            # 查詢伺服器狀態
            status = await asyncio.to_thread(self.server.status)

            result = {
                "online": True,
                "players": status.players.online,
                "max_players": status.players.max,
                "version": status.version.name if status.version else "Unknown",
                "motd": status.description if hasattr(status, "description") else "",
                "ping": round(status.latency, 2) if status.latency else None,
                "timestamp": datetime.now().isoformat(),
            }

            # 更新快取
            self._status_cache = result
            self._status_cache_time = datetime.now()

            return result

        except Exception as e:
            logger.error(f"獲取伺服器狀態失敗: {e}")
            # 返回離線狀態
            return {
                "online": False,
                "players": 0,
                "max_players": 20,
                "version": "Unknown",
                "motd": "",
                "ping": None,
                "timestamp": datetime.now().isoformat(),
            }

    async def get_server_performance(self) -> Optional[Dict[str, Any]]:
        """獲取伺服器效能資訊 (需要 RCON 或外部監控)"""
        try:
            # 這裡可以整合其他監控系統或 RCON 指令
            # 目前返回模擬數據
            return {
                "tps": 20.0,
                "memory_used": 2048,
                "memory_max": 4096,
                "cpu_usage": 15.5,
            }
        except Exception as e:
            logger.error(f"獲取伺服器效能失敗: {e}")
            return None

    async def get_online_players(self) -> List[Dict[str, Any]]:
        """獲取在線玩家列表"""
        try:
            if not self.server:
                await self.connect()

            if not self.server:
                return []

            # 查詢玩家資訊
            query = await asyncio.to_thread(self.server.query)

            if query.players.names:
                return [{"name": name} for name in query.players.names]
            else:
                return []

        except Exception as e:
            logger.error(f"獲取在線玩家失敗: {e}")
            return []

    async def get_online_players_detailed(self) -> List[Dict[str, Any]]:
        """獲取詳細的在線玩家資訊"""
        try:
            basic_players = await self.get_online_players()

            # 為每個玩家獲取詳細資訊
            detailed_players = []
            for player in basic_players:
                player_detail = await self.get_player_info(player["name"])
                if player_detail:
                    detailed_players.append(
                        {
                            "name": player["name"],
                            "uuid": player_detail.get("uuid", ""),
                            "playtime": player_detail.get("playtime", "N/A"),
                            "location": player_detail.get("location", "Unknown"),
                            "level": player_detail.get("level", 0),
                            "health": player_detail.get("health", 20),
                        }
                    )
                else:
                    detailed_players.append(
                        {
                            "name": player["name"],
                            "uuid": "",
                            "playtime": "N/A",
                            "location": "Unknown",
                            "level": 0,
                            "health": 20,
                        }
                    )

            return detailed_players

        except Exception as e:
            logger.error(f"獲取詳細玩家資訊失敗: {e}")
            return []

    async def get_player_info(self, username: str) -> Optional[Dict[str, Any]]:
        """獲取玩家資訊 (使用 Mojang API)"""
        try:
            async with aiohttp.ClientSession() as session:
                # 獲取 UUID
                async with session.get(
                    f"https://api.mojang.com/users/profiles/minecraft/{username}"
                ) as resp:
                    if resp.status != 200:
                        return None

                    data = await resp.json()
                    uuid = data.get("id")
                    name = data.get("name")

                    return {
                        "name": name,
                        "uuid": uuid,
                        "skin_url": f"https://crafatar.com/avatars/{uuid}",
                        "playtime": "N/A",  # 需要從遊戲內或資料庫獲取
                        "location": "Unknown",
                        "level": 0,
                        "health": 20,
                    }

        except Exception as e:
            logger.error(f"獲取玩家資訊失敗 ({username}): {e}")
            return None

    def _is_cache_valid(self) -> bool:
        """檢查快取是否有效"""
        if not self._status_cache or not self._status_cache_time:
            return False

        time_diff = datetime.now() - self._status_cache_time
        return time_diff.total_seconds() < self._cache_timeout
