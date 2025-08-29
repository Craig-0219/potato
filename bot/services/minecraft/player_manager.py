"""
Minecraft 玩家管理器
處理玩家綁定、活動追蹤、統計等功能
"""

import asyncio
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timedelta
import discord

from shared.logger import logger
from bot.db.database_manager import DatabaseManager


class PlayerManager:
    """Minecraft 玩家管理器"""
    
    def __init__(self, bot):
        self.bot = bot
        self.db = DatabaseManager()
        
        # 玩家活動快取
        self._player_cache = {}
        self._activity_cache = {}
    
    async def initialize(self):
        """初始化玩家管理器"""
        try:
            await self._create_tables()
            logger.info("PlayerManager 初始化完成")
        except Exception as e:
            logger.error(f"PlayerManager 初始化失敗: {e}")
    
    async def _create_tables(self):
        """建立必要的資料庫表格"""
        tables = [
            # Minecraft 玩家綁定表
            """
            CREATE TABLE IF NOT EXISTS minecraft_players (
                discord_id BIGINT PRIMARY KEY,
                minecraft_uuid VARCHAR(36) UNIQUE NOT NULL,
                minecraft_username VARCHAR(16) NOT NULL,
                first_join TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                playtime_hours INTEGER DEFAULT 0,
                is_active BOOLEAN DEFAULT TRUE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
            )
            """,
            
            # 玩家活動記錄表
            """
            CREATE TABLE IF NOT EXISTS player_activity (
                id INT AUTO_INCREMENT PRIMARY KEY,
                minecraft_uuid VARCHAR(36) NOT NULL,
                activity_type ENUM('join', 'leave', 'chat', 'command', 'death', 'achievement') NOT NULL,
                activity_data JSON,
                server_name VARCHAR(50) DEFAULT 'main',
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                INDEX idx_uuid_time (minecraft_uuid, timestamp),
                INDEX idx_activity_type (activity_type),
                FOREIGN KEY (minecraft_uuid) REFERENCES minecraft_players(minecraft_uuid) ON DELETE CASCADE
            )
            """,
            
            # 玩家統計表
            """
            CREATE TABLE IF NOT EXISTS player_statistics (
                minecraft_uuid VARCHAR(36) PRIMARY KEY,
                total_playtime BIGINT DEFAULT 0,
                blocks_placed BIGINT DEFAULT 0,
                blocks_broken BIGINT DEFAULT 0,
                distance_traveled BIGINT DEFAULT 0,
                deaths INTEGER DEFAULT 0,
                kills INTEGER DEFAULT 0,
                achievements INTEGER DEFAULT 0,
                level INTEGER DEFAULT 0,
                experience BIGINT DEFAULT 0,
                last_location_x DOUBLE DEFAULT 0,
                last_location_y DOUBLE DEFAULT 64,
                last_location_z DOUBLE DEFAULT 0,
                last_location_world VARCHAR(50) DEFAULT 'world',
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                FOREIGN KEY (minecraft_uuid) REFERENCES minecraft_players(minecraft_uuid) ON DELETE CASCADE
            )
            """
        ]
        
        for table_sql in tables:
            await self.db.execute(table_sql)
    
    async def bind_player(self, discord_id: int, minecraft_uuid: str, minecraft_username: str) -> bool:
        """綁定 Discord 用戶到 Minecraft 玩家"""
        try:
            # 檢查是否已經綁定
            existing = await self.get_bound_player(discord_id)
            if existing:
                logger.warning(f"Discord 用戶 {discord_id} 已綁定到 {existing['minecraft_username']}")
                return False
            
            # 檢查 Minecraft 玩家是否已被綁定
            existing_discord = await self.db.fetchone(
                "SELECT discord_id FROM minecraft_players WHERE minecraft_uuid = %s",
                (minecraft_uuid,)
            )
            if existing_discord:
                logger.warning(f"Minecraft 玩家 {minecraft_username} 已被 Discord 用戶 {existing_discord['discord_id']} 綁定")
                return False
            
            # 執行綁定
            await self.db.execute(
                """
                INSERT INTO minecraft_players 
                (discord_id, minecraft_uuid, minecraft_username, first_join, last_seen) 
                VALUES (%s, %s, %s, NOW(), NOW())
                """,
                (discord_id, minecraft_uuid, minecraft_username)
            )
            
            # 初始化玩家統計
            await self.db.execute(
                """
                INSERT INTO player_statistics (minecraft_uuid) 
                VALUES (%s) ON DUPLICATE KEY UPDATE minecraft_uuid = minecraft_uuid
                """,
                (minecraft_uuid,)
            )
            
            # 記錄活動
            await self._record_activity(
                minecraft_uuid, 
                'join', 
                {'action': 'bind', 'discord_id': discord_id}
            )
            
            logger.info(f"成功綁定 Discord {discord_id} ↔ Minecraft {minecraft_username} ({minecraft_uuid})")
            return True
            
        except Exception as e:
            logger.error(f"玩家綁定失敗: {e}")
            return False
    
    async def unbind_player(self, discord_id: int) -> bool:
        """解除 Discord 用戶的 Minecraft 綁定"""
        try:
            player = await self.get_bound_player(discord_id)
            if not player:
                return False
            
            await self.db.execute(
                "UPDATE minecraft_players SET is_active = FALSE WHERE discord_id = %s",
                (discord_id,)
            )
            
            logger.info(f"已解除 Discord {discord_id} 的 Minecraft 綁定")
            return True
            
        except Exception as e:
            logger.error(f"解除綁定失敗: {e}")
            return False
    
    async def get_bound_player(self, discord_id: int) -> Optional[Dict[str, Any]]:
        """獲取 Discord 用戶綁定的 Minecraft 玩家資訊"""
        try:
            result = await self.db.fetchone(
                """
                SELECT mp.*, ps.* 
                FROM minecraft_players mp
                LEFT JOIN player_statistics ps ON mp.minecraft_uuid = ps.minecraft_uuid
                WHERE mp.discord_id = %s AND mp.is_active = TRUE
                """,
                (discord_id,)
            )
            
            return dict(result) if result else None
            
        except Exception as e:
            logger.error(f"獲取綁定玩家失敗: {e}")
            return None
    
    async def get_player_by_uuid(self, minecraft_uuid: str) -> Optional[Dict[str, Any]]:
        """根據 UUID 獲取玩家資訊"""
        try:
            result = await self.db.fetchone(
                """
                SELECT mp.*, ps.* 
                FROM minecraft_players mp
                LEFT JOIN player_statistics ps ON mp.minecraft_uuid = ps.minecraft_uuid
                WHERE mp.minecraft_uuid = %s AND mp.is_active = TRUE
                """,
                (minecraft_uuid,)
            )
            
            return dict(result) if result else None
            
        except Exception as e:
            logger.error(f"獲取玩家資訊失敗 ({minecraft_uuid}): {e}")
            return None
    
    async def update_player_activity(self, online_players: List[Dict[str, Any]]):
        """更新玩家活動狀態"""
        try:
            current_time = datetime.now()
            
            for player in online_players:
                player_name = player.get('name')
                if not player_name:
                    continue
                
                # 更新最後見到時間
                await self.db.execute(
                    "UPDATE minecraft_players SET last_seen = %s WHERE minecraft_username = %s",
                    (current_time, player_name)
                )
                
                # 記錄在線活動
                player_data = await self.db.fetchone(
                    "SELECT minecraft_uuid FROM minecraft_players WHERE minecraft_username = %s",
                    (player_name,)
                )
                
                if player_data:
                    await self._record_activity(
                        player_data['minecraft_uuid'],
                        'join',
                        {'status': 'online', 'timestamp': current_time.isoformat()}
                    )
            
        except Exception as e:
            logger.error(f"更新玩家活動失敗: {e}")
    
    async def get_player_statistics(self, minecraft_uuid: str) -> Dict[str, Any]:
        """獲取玩家統計資訊"""
        try:
            stats = await self.db.fetchone(
                "SELECT * FROM player_statistics WHERE minecraft_uuid = %s",
                (minecraft_uuid,)
            )
            
            if not stats:
                return {}
            
            # 計算額外統計
            recent_activity = await self.db.fetchall(
                """
                SELECT activity_type, COUNT(*) as count 
                FROM player_activity 
                WHERE minecraft_uuid = %s AND timestamp > DATE_SUB(NOW(), INTERVAL 7 DAY)
                GROUP BY activity_type
                """,
                (minecraft_uuid,)
            )
            
            activity_summary = {row['activity_type']: row['count'] for row in recent_activity}
            
            result = dict(stats)
            result['recent_activity'] = activity_summary
            result['playtime_formatted'] = self._format_playtime(stats['total_playtime'])
            
            return result
            
        except Exception as e:
            logger.error(f"獲取玩家統計失敗 ({minecraft_uuid}): {e}")
            return {}
    
    async def update_player_stats(self, minecraft_uuid: str, stats_data: Dict[str, Any]):
        """更新玩家統計資料"""
        try:
            # 建構更新語句
            update_fields = []
            values = []
            
            stat_mappings = {
                'playtime': 'total_playtime',
                'blocks_placed': 'blocks_placed',
                'blocks_broken': 'blocks_broken',
                'distance_traveled': 'distance_traveled',
                'deaths': 'deaths',
                'kills': 'kills',
                'level': 'level',
                'experience': 'experience',
                'location_x': 'last_location_x',
                'location_y': 'last_location_y',
                'location_z': 'last_location_z',
                'world': 'last_location_world'
            }
            
            for key, db_field in stat_mappings.items():
                if key in stats_data:
                    update_fields.append(f"{db_field} = %s")
                    values.append(stats_data[key])
            
            if update_fields:
                values.append(minecraft_uuid)
                await self.db.execute(
                    f"UPDATE player_statistics SET {', '.join(update_fields)} WHERE minecraft_uuid = %s",
                    tuple(values)
                )
            
        except Exception as e:
            logger.error(f"更新玩家統計失敗 ({minecraft_uuid}): {e}")
    
    async def get_top_players(self, stat_type: str = 'total_playtime', limit: int = 10) -> List[Dict[str, Any]]:
        """獲取排行榜玩家"""
        try:
            valid_stats = ['total_playtime', 'blocks_placed', 'blocks_broken', 'kills', 'level']
            if stat_type not in valid_stats:
                stat_type = 'total_playtime'
            
            results = await self.db.fetchall(
                f"""
                SELECT mp.minecraft_username, mp.discord_id, ps.{stat_type}, ps.level, ps.total_playtime
                FROM minecraft_players mp
                JOIN player_statistics ps ON mp.minecraft_uuid = ps.minecraft_uuid
                WHERE mp.is_active = TRUE
                ORDER BY ps.{stat_type} DESC
                LIMIT %s
                """,
                (limit,)
            )
            
            return [dict(row) for row in results]
            
        except Exception as e:
            logger.error(f"獲取排行榜失敗 ({stat_type}): {e}")
            return []
    
    async def _record_activity(self, minecraft_uuid: str, activity_type: str, activity_data: Dict[str, Any]):
        """記錄玩家活動"""
        try:
            await self.db.execute(
                "INSERT INTO player_activity (minecraft_uuid, activity_type, activity_data) VALUES (%s, %s, %s)",
                (minecraft_uuid, activity_type, str(activity_data))
            )
        except Exception as e:
            logger.error(f"記錄玩家活動失敗: {e}")
    
    def _format_playtime(self, seconds: int) -> str:
        """格式化遊戲時間"""
        if not seconds:
            return "0 小時"
        
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        
        if hours > 0:
            return f"{hours} 小時 {minutes} 分鐘"
        else:
            return f"{minutes} 分鐘"