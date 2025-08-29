"""
Minecraft RCON 管理器
提供遠端指令執行、白名單管理等功能
"""

import asyncio
from typing import Dict, Any, List, Optional
from mcrcon import MCRcon
import socket

from shared.logger import logger
from shared.config import (
    MINECRAFT_RCON_HOST, 
    MINECRAFT_RCON_PORT, 
    MINECRAFT_RCON_PASSWORD
)


class RCONManager:
    """Minecraft RCON 連線管理器"""
    
    def __init__(self):
        self.host = MINECRAFT_RCON_HOST or 'localhost'
        self.port = MINECRAFT_RCON_PORT or 25575
        self.password = MINECRAFT_RCON_PASSWORD or ''
        
        # 連線快取
        self._connection = None
        self._connection_lock = asyncio.Lock()
    
    async def _get_connection(self) -> Optional[MCRcon]:
        """獲取 RCON 連線 (含重連邏輯)"""
        async with self._connection_lock:
            try:
                # 檢查現有連線
                if self._connection:
                    try:
                        # 測試連線是否正常
                        self._connection.command("list")
                        return self._connection
                    except:
                        # 連線失效，關閉並重新連線
                        try:
                            self._connection.disconnect()
                        except:
                            pass
                        self._connection = None
                
                # 建立新連線
                if not self.password:
                    logger.error("RCON 密碼未設置")
                    return None
                
                self._connection = MCRcon(self.host, self.password, port=self.port)
                self._connection.connect()
                
                logger.info(f"RCON 連線建立成功 ({self.host}:{self.port})")
                return self._connection
                
            except socket.gaierror:
                logger.error(f"RCON 連線失敗: 無法解析主機 {self.host}")
                return None
            except ConnectionRefusedError:
                logger.error(f"RCON 連線被拒絕: {self.host}:{self.port}")
                return None
            except Exception as e:
                logger.error(f"RCON 連線失敗: {e}")
                return None
    
    async def execute_command(self, command: str) -> Dict[str, Any]:
        """執行 RCON 指令"""
        try:
            connection = await self._get_connection()
            if not connection:
                return {
                    'success': False,
                    'error': '無法建立 RCON 連線',
                    'response': None
                }
            
            # 執行指令 (在另一個執行緒中)
            response = await asyncio.to_thread(connection.command, command)
            
            logger.info(f"RCON 指令執行成功: {command}")
            
            return {
                'success': True,
                'error': None,
                'response': response.strip() if response else ''
            }
            
        except Exception as e:
            logger.error(f"RCON 指令執行失敗 ({command}): {e}")
            return {
                'success': False,
                'error': str(e),
                'response': None
            }
    
    async def get_whitelist(self) -> List[str]:
        """獲取白名單玩家列表"""
        try:
            result = await self.execute_command("whitelist list")
            
            if not result['success']:
                return []
            
            response = result['response']
            if not response:
                return []
            
            # 解析白名單回應
            # 格式: "There are X whitelisted players: player1, player2, player3"
            if "There are" in response and "whitelisted players:" in response:
                parts = response.split("whitelisted players:")
                if len(parts) > 1:
                    players_str = parts[1].strip()
                    if players_str:
                        return [p.strip() for p in players_str.split(",")]
            
            return []
            
        except Exception as e:
            logger.error(f"獲取白名單失敗: {e}")
            return []
    
    async def add_to_whitelist(self, player: str) -> Dict[str, Any]:
        """將玩家加入白名單"""
        return await self.execute_command(f"whitelist add {player}")
    
    async def remove_from_whitelist(self, player: str) -> Dict[str, Any]:
        """從白名單移除玩家"""
        return await self.execute_command(f"whitelist remove {player}")
    
    async def kick_player(self, player: str, reason: str = "已被管理員踢出") -> Dict[str, Any]:
        """踢出玩家"""
        return await self.execute_command(f"kick {player} {reason}")
    
    async def ban_player(self, player: str, reason: str = "已被管理員封禁") -> Dict[str, Any]:
        """封禁玩家"""
        return await self.execute_command(f"ban {player} {reason}")
    
    async def unban_player(self, player: str) -> Dict[str, Any]:
        """解除封禁"""
        return await self.execute_command(f"pardon {player}")
    
    async def broadcast_message(self, message: str) -> Dict[str, Any]:
        """伺服器廣播訊息"""
        return await self.execute_command(f"say {message}")
    
    async def teleport_player(self, player: str, x: int, y: int, z: int) -> Dict[str, Any]:
        """傳送玩家"""
        return await self.execute_command(f"tp {player} {x} {y} {z}")
    
    async def give_item(self, player: str, item: str, count: int = 1) -> Dict[str, Any]:
        """給予玩家物品"""
        return await self.execute_command(f"give {player} {item} {count}")
    
    async def set_weather(self, weather: str) -> Dict[str, Any]:
        """設置天氣 (clear, rain, thunder)"""
        return await self.execute_command(f"weather {weather}")
    
    async def set_time(self, time: str) -> Dict[str, Any]:
        """設置時間 (day, night, 或具體數值)"""
        return await self.execute_command(f"time set {time}")
    
    async def get_server_info(self) -> Dict[str, Any]:
        """獲取伺服器資訊"""
        try:
            # 執行多個指令獲取完整資訊
            commands = {
                'list': 'list',
                'tps': 'tps',  # 可能需要插件支援
                'memory': 'gc',  # 垃圾回收資訊
            }
            
            results = {}
            for key, cmd in commands.items():
                result = await self.execute_command(cmd)
                results[key] = result['response'] if result['success'] else None
            
            return results
            
        except Exception as e:
            logger.error(f"獲取伺服器資訊失敗: {e}")
            return {}
    
    async def disconnect(self):
        """關閉 RCON 連線"""
        if self._connection:
            try:
                self._connection.disconnect()
                logger.info("RCON 連線已關閉")
            except:
                pass
            finally:
                self._connection = None