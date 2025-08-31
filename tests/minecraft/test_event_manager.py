"""
測試 Minecraft 活動管理系統
"""

from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest

from bot.services.minecraft.event_manager import EventStatus, EventType, MinecraftEventManager


class TestMinecraftEventManager:
    """測試 MinecraftEventManager"""

    @pytest.fixture
    def mock_bot(self):
        """建立 Mock Bot"""
        bot = MagicMock()
        return bot

    @pytest.fixture
    def mock_db(self):
        """建立 Mock DatabaseManager"""
        db = AsyncMock()
        return db

    @pytest.fixture
    def event_manager(self, mock_bot, mock_db):
        """建立 MinecraftEventManager 實例"""
        manager = MinecraftEventManager(mock_bot)
        manager.db = mock_db
        return manager

    @pytest.mark.asyncio
    async def test_initialization(self, event_manager, mock_db):
        """測試活動管理器初始化"""
        # 準備
        mock_db.execute = AsyncMock()
        mock_db.fetchall = AsyncMock(return_value=[])

        # 執行
        await event_manager.initialize()

        # 驗證
        assert mock_db.execute.call_count >= 3  # 建立三個表格
        assert mock_db.fetchall.called  # 載入活躍活動

    @pytest.mark.asyncio
    async def test_create_event_success(self, event_manager, mock_db):
        """測試成功建立活動"""
        # 準備
        mock_db.execute = AsyncMock(return_value=123)  # 回傳活動 ID

        event_data = {
            "title": "建築比賽",
            "description": "建築主題比賽",
            "event_type": "build_contest",
            "max_participants": 20,
            "start_time": datetime.now() + timedelta(hours=2),
            "end_time": datetime.now() + timedelta(hours=26),
            "registration_end": datetime.now() + timedelta(hours=1),
        }

        # 執行
        result = await event_manager.create_event(
            organizer_id=123456, guild_id=789012, event_data=event_data
        )

        # 驗證
        assert result == 123
        mock_db.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_event_missing_fields(self, event_manager):
        """測試建立活動缺少必要欄位"""
        # 準備
        event_data = {
            "title": "建築比賽"
            # 缺少 description 和 event_type
        }

        # 執行
        result = await event_manager.create_event(
            organizer_id=123456, guild_id=789012, event_data=event_data
        )

        # 驗證
        assert result is None

    @pytest.mark.asyncio
    async def test_create_event_invalid_type(self, event_manager):
        """測試建立活動使用無效類型"""
        # 準備
        event_data = {
            "title": "測試活動",
            "description": "測試描述",
            "event_type": "invalid_type",  # 無效類型
        }

        # 執行
        result = await event_manager.create_event(
            organizer_id=123456, guild_id=789012, event_data=event_data
        )

        # 驗證
        assert result is None

    @pytest.mark.asyncio
    async def test_register_participant_success(self, event_manager, mock_db):
        """測試成功報名參加活動"""
        # 準備
        mock_event = {
            "id": 1,
            "status": "registration",
            "max_participants": 20,
            "current_participants": 5,
        }

        mock_db.fetchone = AsyncMock(
            side_effect=[mock_event, None]  # get_event 呼叫  # 檢查是否已報名 (無重複報名)
        )
        mock_db.execute = AsyncMock()

        # 執行
        result = await event_manager.register_participant(
            event_id=1, discord_id=123456, minecraft_uuid="test-uuid"
        )

        # 驗證
        assert result is True
        assert mock_db.execute.call_count == 2  # INSERT + UPDATE

    @pytest.mark.asyncio
    async def test_register_participant_event_not_found(self, event_manager, mock_db):
        """測試報名不存在的活動"""
        # 準備
        mock_db.fetchone = AsyncMock(return_value=None)  # 活動不存在

        # 執行
        result = await event_manager.register_participant(event_id=999, discord_id=123456)

        # 驗證
        assert result is False

    @pytest.mark.asyncio
    async def test_register_participant_not_registration_status(self, event_manager, mock_db):
        """測試報名狀態不正確的活動"""
        # 準備
        mock_event = {
            "id": 1,
            "status": "planned",  # 未開放報名
            "max_participants": 20,
            "current_participants": 5,
        }

        mock_db.fetchone = AsyncMock(return_value=mock_event)

        # 執行
        result = await event_manager.register_participant(event_id=1, discord_id=123456)

        # 驗證
        assert result is False

    @pytest.mark.asyncio
    async def test_register_participant_full_event(self, event_manager, mock_db):
        """測試報名已滿的活動"""
        # 準備
        mock_event = {
            "id": 1,
            "status": "registration",
            "max_participants": 20,
            "current_participants": 20,  # 已滿
        }

        mock_db.fetchone = AsyncMock(return_value=mock_event)

        # 執行
        result = await event_manager.register_participant(event_id=1, discord_id=123456)

        # 驗證
        assert result is False

    @pytest.mark.asyncio
    async def test_register_participant_already_registered(self, event_manager, mock_db):
        """測試重複報名"""
        # 準備
        mock_event = {
            "id": 1,
            "status": "registration",
            "max_participants": 20,
            "current_participants": 5,
        }

        mock_existing = {"id": 1}  # 已存在報名記錄

        mock_db.fetchone = AsyncMock(
            side_effect=[mock_event, mock_existing]  # get_event 呼叫  # 檢查重複報名
        )

        # 執行
        result = await event_manager.register_participant(event_id=1, discord_id=123456)

        # 驗證
        assert result is False

    @pytest.mark.asyncio
    async def test_withdraw_participant_success(self, event_manager, mock_db):
        """測試成功取消報名"""
        # 準備
        mock_participant = {"id": 1, "status": "registered"}

        mock_db.fetchone = AsyncMock(return_value=mock_participant)
        mock_db.execute = AsyncMock()

        # 執行
        result = await event_manager.withdraw_participant(event_id=1, discord_id=123456)

        # 驗證
        assert result is True
        assert mock_db.execute.call_count == 2  # UPDATE status + UPDATE count

    @pytest.mark.asyncio
    async def test_withdraw_participant_not_found(self, event_manager, mock_db):
        """測試取消不存在的報名"""
        # 準備
        mock_db.fetchone = AsyncMock(return_value=None)

        # 執行
        result = await event_manager.withdraw_participant(event_id=1, discord_id=123456)

        # 驗證
        assert result is False

    @pytest.mark.asyncio
    async def test_withdraw_participant_invalid_status(self, event_manager, mock_db):
        """測試取消已參與的活動報名"""
        # 準備
        mock_participant = {"id": 1, "status": "participated"}  # 已參與，不可取消

        mock_db.fetchone = AsyncMock(return_value=mock_participant)

        # 執行
        result = await event_manager.withdraw_participant(event_id=1, discord_id=123456)

        # 驗證
        assert result is False

    @pytest.mark.asyncio
    async def test_get_event_success(self, event_manager, mock_db):
        """測試成功獲取活動資訊"""
        # 準備
        mock_event = {"id": 1, "title": "測試活動", "status": "registration"}

        mock_db.fetchone = AsyncMock(return_value=mock_event)

        # 執行
        result = await event_manager.get_event(1)

        # 驗證
        assert result == mock_event
        mock_db.fetchone.assert_called_once_with(
            "SELECT * FROM minecraft_events WHERE id = %s", (1,)
        )

    @pytest.mark.asyncio
    async def test_get_event_not_found(self, event_manager, mock_db):
        """測試獲取不存在的活動"""
        # 準備
        mock_db.fetchone = AsyncMock(return_value=None)

        # 執行
        result = await event_manager.get_event(999)

        # 驗證
        assert result is None

    @pytest.mark.asyncio
    async def test_get_active_events(self, event_manager, mock_db):
        """測試獲取活躍活動列表"""
        # 準備
        mock_events = [
            {"id": 1, "title": "活動1", "status": "registration"},
            {"id": 2, "title": "活動2", "status": "active"},
            {"id": 3, "title": "活動3", "status": "planned"},
        ]

        mock_db.fetchall = AsyncMock(return_value=mock_events)

        # 執行
        result = await event_manager.get_active_events(789012)

        # 驗證
        assert len(result) == 3
        assert result[0]["title"] == "活動1"
        mock_db.fetchall.assert_called_once()

    @pytest.mark.asyncio
    async def test_start_event_success(self, event_manager, mock_db):
        """測試成功開始活動"""
        # 準備
        mock_db.execute = AsyncMock()

        # 執行
        result = await event_manager.start_event(1)

        # 驗證
        assert result is True
        mock_db.execute.assert_called_once_with(
            "UPDATE minecraft_events SET status = 'active', start_time = NOW() WHERE id = %s", (1,)
        )

    @pytest.mark.asyncio
    async def test_complete_event_success(self, event_manager, mock_db):
        """測試成功完成活動"""
        # 準備
        mock_db.execute = AsyncMock()

        results = [
            {
                "participant_id": 1,
                "final_score": 100,
                "final_rank": 1,
                "achievements": {"first_place": True},
                "rewards_claimed": {"coins": 1000},
            },
            {"participant_id": 2, "final_score": 85, "final_rank": 2},
        ]

        # 執行
        result = await event_manager.complete_event(1, results)

        # 驗證
        assert result is True
        # 應該呼叫一次 UPDATE (狀態) + 兩次 INSERT (結果)
        assert mock_db.execute.call_count == 3

    def test_get_event_type_emoji(self, event_manager):
        """測試活動類型 emoji"""
        assert event_manager.get_event_type_emoji("build_contest") == "🏗️"
        assert event_manager.get_event_type_emoji("pvp_tournament") == "⚔️"
        assert event_manager.get_event_type_emoji("exploration") == "🗺️"
        assert event_manager.get_event_type_emoji("community") == "🎉"
        assert event_manager.get_event_type_emoji("custom") == "🎮"
        assert event_manager.get_event_type_emoji("unknown") == "📅"

    def test_get_status_emoji(self, event_manager):
        """測試活動狀態 emoji"""
        assert event_manager.get_status_emoji("planned") == "📋"
        assert event_manager.get_status_emoji("registration") == "📝"
        assert event_manager.get_status_emoji("active") == "🟢"
        assert event_manager.get_status_emoji("completed") == "✅"
        assert event_manager.get_status_emoji("cancelled") == "❌"
        assert event_manager.get_status_emoji("unknown") == "❓"


class TestEventEnums:
    """測試活動相關的列舉"""

    def test_event_type_values(self):
        """測試 EventType 列舉值"""
        assert EventType.BUILD_CONTEST.value == "build_contest"
        assert EventType.PVP_TOURNAMENT.value == "pvp_tournament"
        assert EventType.EXPLORATION.value == "exploration"
        assert EventType.COMMUNITY.value == "community"
        assert EventType.CUSTOM.value == "custom"

    def test_event_status_values(self):
        """測試 EventStatus 列舉值"""
        assert EventStatus.PLANNED.value == "planned"
        assert EventStatus.REGISTRATION.value == "registration"
        assert EventStatus.ACTIVE.value == "active"
        assert EventStatus.COMPLETED.value == "completed"
        assert EventStatus.CANCELLED.value == "cancelled"


if __name__ == "__main__":
    # 執行測試
    pytest.main([__file__, "-v"])
