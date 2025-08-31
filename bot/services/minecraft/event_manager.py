"""
Minecraft 活動管理系統
管理建築比賽、PvP 錦標賽、探險隊等社群活動
"""

import json
from enum import Enum
from typing import Any, Dict, List, Optional

from bot.db.database_manager import DatabaseManager
from shared.logger import logger


class EventType(Enum):
    """活動類型"""

    BUILD_CONTEST = "build_contest"  # 建築比賽
    PVP_TOURNAMENT = "pvp_tournament"  # PvP 錦標賽
    EXPLORATION = "exploration"  # 探險隊
    COMMUNITY = "community"  # 社群活動
    CUSTOM = "custom"  # 自訂活動


class EventStatus(Enum):
    """活動狀態"""

    PLANNED = "planned"  # 已規劃
    REGISTRATION = "registration"  # 報名中
    ACTIVE = "active"  # 進行中
    COMPLETED = "completed"  # 已完成
    CANCELLED = "cancelled"  # 已取消


class MinecraftEventManager:
    """Minecraft 活動管理器"""

    def __init__(self, bot):
        self.bot = bot
        self.db = DatabaseManager()

        # 活動快取
        self._active_events = {}
        self._event_participants = {}

    async def initialize(self):
        """初始化活動管理器"""
        try:
            await self._create_tables()
            await self._load_active_events()
            logger.info("MinecraftEventManager 初始化完成")
        except Exception as e:
            logger.error(f"MinecraftEventManager 初始化失敗: {e}")

    async def _create_tables(self):
        """建立活動相關資料庫表格"""
        tables = [
            # 活動主表
            """
            CREATE TABLE IF NOT EXISTS minecraft_events (
                id INT AUTO_INCREMENT PRIMARY KEY,
                title VARCHAR(200) NOT NULL,
                description TEXT,
                event_type ENUM('build_contest', 'pvp_tournament', 'exploration', 'community', 'custom') NOT NULL,
                status ENUM('planned', 'registration', 'active', 'completed', 'cancelled') DEFAULT 'planned',
                organizer_id BIGINT NOT NULL,
                guild_id BIGINT NOT NULL,
                max_participants INT DEFAULT 0,
                current_participants INT DEFAULT 0,
                start_time TIMESTAMP NULL,
                end_time TIMESTAMP NULL,
                registration_end TIMESTAMP NULL,
                requirements JSON,
                rewards JSON,
                rules TEXT,
                location_data JSON,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                INDEX idx_status_type (status, event_type),
                INDEX idx_guild_time (guild_id, start_time)
            )
            """,
            # 活動參與者表
            """
            CREATE TABLE IF NOT EXISTS event_participants (
                id INT AUTO_INCREMENT PRIMARY KEY,
                event_id INT NOT NULL,
                discord_id BIGINT NOT NULL,
                minecraft_uuid VARCHAR(36),
                registration_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                status ENUM('registered', 'confirmed', 'participated', 'withdrawn', 'disqualified') DEFAULT 'registered',
                score INT DEFAULT 0,
                rank_position INT DEFAULT 0,
                additional_data JSON,
                UNIQUE KEY unique_participant (event_id, discord_id),
                FOREIGN KEY (event_id) REFERENCES minecraft_events(id) ON DELETE CASCADE,
                INDEX idx_event_status (event_id, status)
            )
            """,
            # 活動結果表
            """
            CREATE TABLE IF NOT EXISTS event_results (
                id INT AUTO_INCREMENT PRIMARY KEY,
                event_id INT NOT NULL,
                participant_id INT NOT NULL,
                final_score INT NOT NULL,
                final_rank INT NOT NULL,
                achievements JSON,
                rewards_claimed JSON,
                completion_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (event_id) REFERENCES minecraft_events(id) ON DELETE CASCADE,
                FOREIGN KEY (participant_id) REFERENCES event_participants(id) ON DELETE CASCADE,
                INDEX idx_event_rank (event_id, final_rank)
            )
            """,
        ]

        for table_sql in tables:
            await self.db.execute(table_sql)

    async def create_event(
        self, organizer_id: int, guild_id: int, event_data: Dict[str, Any]
    ) -> Optional[int]:
        """建立新活動"""
        try:
            # 驗證必要欄位
            required_fields = ["title", "event_type", "description"]
            for field in required_fields:
                if field not in event_data:
                    raise ValueError(f"缺少必要欄位: {field}")

            # 驗證活動類型
            if event_data["event_type"] not in [e.value for e in EventType]:
                raise ValueError(f"無效的活動類型: {event_data['event_type']}")

            # 插入活動記錄
            event_id = await self.db.execute(
                """
                INSERT INTO minecraft_events
                (title, description, event_type, organizer_id, guild_id, max_participants,
                 start_time, end_time, registration_end, requirements, rewards, rules, location_data)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    event_data["title"],
                    event_data["description"],
                    event_data["event_type"],
                    organizer_id,
                    guild_id,
                    event_data.get("max_participants", 0),
                    event_data.get("start_time"),
                    event_data.get("end_time"),
                    event_data.get("registration_end"),
                    json.dumps(event_data.get("requirements", {})),
                    json.dumps(event_data.get("rewards", {})),
                    event_data.get("rules", ""),
                    json.dumps(event_data.get("location_data", {})),
                ),
            )

            logger.info(
                f"活動建立成功 - ID: {event_id}, 標題: {event_data['title']}"
            )
            return event_id

        except Exception as e:
            logger.error(f"建立活動失敗: {e}")
            return None

    async def register_participant(
        self, event_id: int, discord_id: int, minecraft_uuid: str = None
    ) -> bool:
        """玩家報名參與活動"""
        try:
            # 檢查活動是否存在且開放報名
            event = await self.get_event(event_id)
            if not event:
                return False

            if event["status"] != EventStatus.REGISTRATION.value:
                return False

            # 檢查是否已達參與人數上限
            if (
                event["max_participants"] > 0
                and event["current_participants"] >= event["max_participants"]
            ):
                return False

            # 檢查是否已經報名
            existing = await self.db.fetchone(
                "SELECT id FROM event_participants WHERE event_id = %s AND discord_id = %s",
                (event_id, discord_id),
            )

            if existing:
                return False

            # 新增參與者記錄
            await self.db.execute(
                """
                INSERT INTO event_participants (event_id, discord_id, minecraft_uuid)
                VALUES (%s, %s, %s)
                """,
                (event_id, discord_id, minecraft_uuid),
            )

            # 更新活動參與人數
            await self.db.execute(
                "UPDATE minecraft_events SET current_participants = current_participants + 1 WHERE id = %s",
                (event_id,),
            )

            logger.info(
                f"玩家報名成功 - 活動ID: {event_id}, 玩家: {discord_id}"
            )
            return True

        except Exception as e:
            logger.error(f"玩家報名失敗: {e}")
            return False

    async def withdraw_participant(
        self, event_id: int, discord_id: int
    ) -> bool:
        """玩家取消報名"""
        try:
            # 檢查參與記錄
            participant = await self.db.fetchone(
                "SELECT id, status FROM event_participants WHERE event_id = %s AND discord_id = %s",
                (event_id, discord_id),
            )

            if not participant:
                return False

            # 只允許報名狀態的玩家取消
            if participant["status"] not in ["registered", "confirmed"]:
                return False

            # 更新狀態為已退出
            await self.db.execute(
                "UPDATE event_participants SET status = 'withdrawn' WHERE id = %s",
                (participant["id"],),
            )

            # 減少活動參與人數
            await self.db.execute(
                "UPDATE minecraft_events SET current_participants = current_participants - 1 WHERE id = %s",
                (event_id,),
            )

            logger.info(
                f"玩家取消報名成功 - 活動ID: {event_id}, 玩家: {discord_id}"
            )
            return True

        except Exception as e:
            logger.error(f"取消報名失敗: {e}")
            return False

    async def get_event(self, event_id: int) -> Optional[Dict[str, Any]]:
        """獲取活動詳細資訊"""
        try:
            event = await self.db.fetchone(
                "SELECT * FROM minecraft_events WHERE id = %s", (event_id,)
            )

            return dict(event) if event else None

        except Exception as e:
            logger.error(f"獲取活動資訊失敗 ({event_id}): {e}")
            return None

    async def get_active_events(self, guild_id: int) -> List[Dict[str, Any]]:
        """獲取伺服器的活躍活動"""
        try:
            events = await self.db.fetchall(
                """
                SELECT * FROM minecraft_events
                WHERE guild_id = %s AND status IN ('planned', 'registration', 'active')
                ORDER BY start_time ASC
                """,
                (guild_id,),
            )

            return [dict(event) for event in events]

        except Exception as e:
            logger.error(f"獲取活躍活動失敗 ({guild_id}): {e}")
            return []

    async def get_event_participants(
        self, event_id: int
    ) -> List[Dict[str, Any]]:
        """獲取活動參與者列表"""
        try:
            participants = await self.db.fetchall(
                """
                SELECT ep.*, mp.minecraft_username
                FROM event_participants ep
                LEFT JOIN minecraft_players mp ON ep.minecraft_uuid = mp.minecraft_uuid
                WHERE ep.event_id = %s AND ep.status != 'withdrawn'
                ORDER BY ep.registration_time ASC
                """,
                (event_id,),
            )

            return [dict(p) for p in participants]

        except Exception as e:
            logger.error(f"獲取活動參與者失敗 ({event_id}): {e}")
            return []

    async def start_event(self, event_id: int) -> bool:
        """開始活動"""
        try:
            await self.db.execute(
                "UPDATE minecraft_events SET status = 'active', start_time = NOW() WHERE id = %s",
                (event_id,),
            )

            logger.info(f"活動開始 - ID: {event_id}")
            return True

        except Exception as e:
            logger.error(f"開始活動失敗 ({event_id}): {e}")
            return False

    async def complete_event(
        self, event_id: int, results: List[Dict[str, Any]] = None
    ) -> bool:
        """完成活動並記錄結果"""
        try:
            # 更新活動狀態
            await self.db.execute(
                "UPDATE minecraft_events SET status = 'completed', end_time = NOW() WHERE id = %s",
                (event_id,),
            )

            # 記錄活動結果
            if results:
                for result in results:
                    await self.db.execute(
                        """
                        INSERT INTO event_results
                        (event_id, participant_id, final_score, final_rank, achievements, rewards_claimed)
                        VALUES (%s, %s, %s, %s, %s, %s)
                        """,
                        (
                            event_id,
                            result["participant_id"],
                            result["final_score"],
                            result["final_rank"],
                            json.dumps(result.get("achievements", {})),
                            json.dumps(result.get("rewards_claimed", {})),
                        ),
                    )

            logger.info(f"活動完成 - ID: {event_id}")
            return True

        except Exception as e:
            logger.error(f"完成活動失敗 ({event_id}): {e}")
            return False

    async def _load_active_events(self):
        """載入活躍活動到快取"""
        try:
            events = await self.db.fetchall(
                "SELECT * FROM minecraft_events WHERE status IN ('planned', 'registration', 'active')"
            )

            self._active_events = {
                event["id"]: dict(event) for event in events
            }
            logger.info(f"載入 {len(self._active_events)} 個活躍活動")

        except Exception as e:
            logger.error(f"載入活躍活動失敗: {e}")

    def get_event_type_emoji(self, event_type: str) -> str:
        """根據活動類型回傳對應的 emoji"""
        emoji_map = {
            "build_contest": "🏗️",
            "pvp_tournament": "⚔️",
            "exploration": "🗺️",
            "community": "🎉",
            "custom": "🎮",
        }
        return emoji_map.get(event_type, "📅")

    def get_status_emoji(self, status: str) -> str:
        """根據活動狀態回傳對應的 emoji"""
        emoji_map = {
            "planned": "📋",
            "registration": "📝",
            "active": "🟢",
            "completed": "✅",
            "cancelled": "❌",
        }
        return emoji_map.get(status, "❓")
