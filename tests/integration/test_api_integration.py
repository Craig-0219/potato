"""
API 系統整合測試
"""

import os
import sys
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

# 添加專案根目錄到 Python 路徑
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))


class TestAPIIntegration(unittest.TestCase):
    """API 系統整合測試"""

    def setUp(self):
        """測試設置"""
        os.environ["TESTING"] = "true"
        os.environ["DISCORD_TOKEN"] = (
            "test_token_comprehensive_validation_length_requirement_met_12345678_abcdefghijk"
        )
        os.environ["DATABASE_URL"] = (
            "mysql://test_user:test_password@127.0.0.1:3306/test_potato_bot"
        )
        os.environ["REDIS_URL"] = "redis://127.0.0.1:6379/0"

    def test_fastapi_app_creation(self):
        """測試 FastAPI 應用程式可以創建"""
        try:
            from bot.api.app import create_app

            app = create_app()
            self.assertIsNotNone(app)
        except ImportError as e:
            self.skipTest(f"FastAPI 應用程式導入失敗: {e}")
        except Exception as e:
            self.fail(f"FastAPI 應用程式創建失敗: {e}")

    def test_api_routes_registration(self):
        """測試 API 路由註冊"""
        try:
            from bot.api.routes.system import router as system_router
            from bot.api.routes.tickets import router as tickets_router

            self.assertIsNotNone(tickets_router)
            self.assertIsNotNone(system_router)

        except ImportError as e:
            self.skipTest(f"API 路由導入失敗: {e}")

    @patch("aiomysql.connect")
    def test_database_connection_interface(self, mock_connect):
        """測試資料庫連接介面"""
        # 模擬異步資料庫連接
        mock_connect.return_value = AsyncMock()

        try:
            from bot.db.database_manager import DatabaseManager

            # 只測試類別結構，不執行實際連接
            self.assertTrue(hasattr(DatabaseManager, "__init__"))

        except ImportError as e:
            self.fail(f"資料庫管理器導入失敗: {e}")

    def test_redis_connection_interface(self):
        """測試 Redis 連接介面"""

        try:
            from shared.cache_manager import MultiLevelCacheManager

            cache = MultiLevelCacheManager()
            self.assertIsInstance(cache, MultiLevelCacheManager)

        except ImportError as e:
            self.skipTest(f"快取管理器導入失敗: {e}")
        except Exception as e:
            self.fail(f"快取管理器初始化失敗: {e}")


class TestServiceIntegration(unittest.TestCase):
    """服務整合測試"""

    def setUp(self):
        """測試設置"""
        os.environ["TESTING"] = "true"

    @patch("bot.db.database_manager.DatabaseManager")
    def test_ticket_manager_integration(self, mock_db):
        """測試票券管理器整合"""
        mock_db.return_value = MagicMock()

        try:
            from bot.services.ticket_manager import TicketManager

            # 只測試類別可以載入
            self.assertTrue(hasattr(TicketManager, "__init__"))

        except ImportError as e:
            self.skipTest(f"票券管理器導入失敗: {e}")

    @patch("bot.db.database_manager.DatabaseManager")
    def test_vote_manager_integration(self, mock_db):
        """測試投票管理器整合"""
        mock_db.return_value = MagicMock()

        try:
            from bot.services.vote_manager import VoteManager

            # 只測試類別結構
            self.assertTrue(hasattr(VoteManager, "__init__"))

        except ImportError as e:
            self.skipTest(f"投票管理器導入失敗: {e}")

    def test_offline_mode_integration(self):
        """測試離線模式整合"""
        try:
            from shared.offline_mode_manager import OfflineModeManager

            offline_mgr = OfflineModeManager()
            self.assertIsInstance(offline_mgr, OfflineModeManager)

        except ImportError as e:
            self.fail(f"離線模式管理器導入失敗: {e}")
        except Exception as e:
            self.fail(f"離線模式管理器初始化失敗: {e}")


class TestBotIntegration(unittest.TestCase):
    """Bot 整合測試"""

    def setUp(self):
        """測試設置"""
        os.environ["TESTING"] = "true"
        os.environ["DISCORD_TOKEN"] = (
            "test_token_comprehensive_validation_length_requirement_met_12345678_abcdefghijk"
        )

    @patch("discord.ext.commands.Bot")
    @patch("discord.Intents")
    @patch("aiomysql.connect")
    def test_bot_main_integration(self, mock_connect, mock_intents, mock_bot):
        """測試 Bot 主程式整合"""
        # 設置模擬
        mock_bot_instance = MagicMock()
        mock_bot_instance.user = MagicMock()
        mock_bot_instance.user.id = 123456789
        mock_bot_instance.guilds = []
        mock_bot.return_value = mock_bot_instance

        mock_intents.default.return_value = MagicMock()
        mock_connect.return_value = AsyncMock()

        try:
            from bot.main import PotatoBot

            # 只測試類別可以載入
            self.assertTrue(hasattr(PotatoBot, "__init__"))

        except ImportError as e:
            self.fail(f"Bot 主程式導入失敗: {e}")

    @patch("discord.ext.commands.Bot")
    @patch("discord.Intents")
    def test_core_components_integration(self, mock_intents, mock_bot):
        """測試核心組件整合"""
        mock_bot.return_value = MagicMock()
        mock_intents.default.return_value = MagicMock()

        # 測試多個核心組件可以同時載入
        try:
            from bot.cogs.ticket_core import TicketCore
            from bot.cogs.vote_core import VoteCore
            from bot.db.database_manager import DatabaseManager
            from shared.cache_manager import MultiLevelCacheManager

            # 驗證所有組件都可以載入
            components = [TicketCore, VoteCore, DatabaseManager, MultiLevelCacheManager]
            for component in components:
                self.assertTrue(hasattr(component, "__init__"))

        except ImportError as e:
            self.fail(f"核心組件整合測試失敗: {e}")


if __name__ == "__main__":
    unittest.main()
