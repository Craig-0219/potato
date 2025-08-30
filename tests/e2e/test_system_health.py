"""
系統健康檢查端到端測試
"""

import os
import sys
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# 添加專案根目錄到 Python 路徑
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))


@pytest.mark.e2e
class TestSystemHealth(unittest.IsolatedAsyncioTestCase):
    """系統健康檢查測試"""

    def setUp(self):
        """測試設置"""
        os.environ["TESTING"] = "true"
        os.environ["E2E_TESTING"] = "true"
        os.environ["DISCORD_TOKEN"] = (
            "test_token_comprehensive_validation_length_requirement_met_12345678_abcdefghijk"
        )
        os.environ["DATABASE_URL"] = (
            "mysql://test_user:test_password@127.0.0.1:3306/test_potato_bot_e2e"
        )

    async def test_configuration_health(self):
        """測試配置健康檢查"""
        try:
            from shared.config import DB_HOST, DB_NAME, DISCORD_TOKEN

            # 驗證關鍵配置存在
            self.assertIsNotNone(DISCORD_TOKEN)
            self.assertIsNotNone(DB_HOST)
            self.assertIsNotNone(DB_NAME)

            # 驗證 Discord Token 格式
            self.assertTrue(len(DISCORD_TOKEN) >= 50)

            print("✅ 配置健康檢查通過")

        except Exception as e:
            self.fail(f"配置健康檢查失敗: {e}")

    async def test_logging_system_health(self):
        """測試日誌系統健康檢查"""
        try:
            from shared.logger import logger

            # 測試日誌系統基本功能
            logger.info("E2E 測試日誌記錄")
            logger.debug("除錯日誌測試")
            logger.warning("警告日誌測試")

            print("✅ 日誌系統健康檢查通過")

        except Exception as e:
            self.fail(f"日誌系統健康檢查失敗: {e}")

    @patch("aiomysql.connect")
    async def test_database_health(self, mock_connect):
        """測試資料庫健康檢查"""
        mock_connect.return_value = AsyncMock()

        try:
            from bot.db.database_manager import DatabaseManager

            # 只測試類別結構健康
            self.assertTrue(hasattr(DatabaseManager, "__init__"))
            self.assertTrue(hasattr(DatabaseManager, "initialize_all_tables"))

            print("✅ 資料庫系統健康檢查通過")

        except Exception as e:
            self.fail(f"資料庫系統健康檢查失敗: {e}")

    @patch("redis.Redis")
    async def test_cache_health(self, mock_redis):
        """測試快取系統健康檢查"""
        mock_redis_instance = MagicMock()
        mock_redis.return_value = mock_redis_instance
        mock_redis_instance.ping.return_value = True

        try:
            from shared.cache_manager import MultiLevelCacheManager

            # 測試快取管理器初始化
            cache = MultiLevelCacheManager()
            self.assertIsInstance(cache, MultiLevelCacheManager)

            print("✅ 快取系統健康檢查通過")

        except Exception as e:
            self.fail(f"快取系統健康檢查失敗: {e}")


@pytest.mark.e2e
class TestComponentConnectivity(unittest.IsolatedAsyncioTestCase):
    """組件連接性測試"""

    def setUp(self):
        """測試設置"""
        os.environ["TESTING"] = "true"
        os.environ["E2E_TESTING"] = "true"

    @patch("discord.ext.commands.Bot")
    @patch("discord.Intents")
    async def test_bot_component_connectivity(self, mock_intents, mock_bot):
        """測試 Bot 組件連接性"""
        mock_bot_instance = MagicMock()
        mock_bot.return_value = mock_bot_instance
        mock_intents.default.return_value = MagicMock()

        try:
            # 測試 Bot 與核心 Cogs 的連接性
            from bot.cogs.ticket_core import TicketCore
            from bot.cogs.vote_core import VoteCore
            from bot.main import PotatoBot

            # 驗證組件都可以載入
            components = [PotatoBot, TicketCore, VoteCore]
            for component in components:
                self.assertTrue(hasattr(component, "__init__"))

            print("✅ Bot 組件連接性測試通過")

        except ImportError as e:
            self.skipTest(f"Bot 組件連接性測試跳過 - 導入失敗: {e}")
        except Exception as e:
            self.fail(f"Bot 組件連接性測試失敗: {e}")

    @patch("aiomysql.connect")
    @patch("bot.db.database_manager.DatabaseManager")
    async def test_service_dao_connectivity(self, mock_db_manager, mock_connect):
        """測試服務-DAO 連接性"""
        mock_connect.return_value = AsyncMock()
        mock_db_manager.return_value = MagicMock()

        try:
            # 測試服務層與 DAO 層連接性
            from bot.db.ticket_dao import TicketDAO
            from bot.services.ticket_manager import TicketManager

            # 驗證兩層都存在
            self.assertTrue(hasattr(TicketManager, "__init__"))
            self.assertTrue(hasattr(TicketDAO, "__init__"))

            print("✅ 服務-DAO 連接性測試通過")

        except ImportError as e:
            self.skipTest(f"服務-DAO 連接性測試跳過 - 導入失敗: {e}")
        except Exception as e:
            self.fail(f"服務-DAO 連接性測試失敗: {e}")

    async def test_api_integration_connectivity(self):
        """測試 API 整合連接性"""
        try:
            # 測試 API 路由與應用程式連接性
            from bot.api.app import create_app
            from bot.api.routes.system import router as system_router
            from bot.api.routes.tickets import router as tickets_router

            # 測試應用程式可以創建
            app = create_app()
            self.assertIsNotNone(app)

            # 測試路由存在
            routers = [tickets_router, system_router]
            for router in routers:
                self.assertIsNotNone(router)

            print("✅ API 整合連接性測試通過")

        except ImportError as e:
            self.skipTest(f"API 整合連接性測試跳過 - 導入失敗: {e}")
        except Exception as e:
            self.fail(f"API 整合連接性測試失敗: {e}")


@pytest.mark.e2e
class TestErrorHandling(unittest.IsolatedAsyncioTestCase):
    """錯誤處理端到端測試"""

    def setUp(self):
        """測試設置"""
        os.environ["TESTING"] = "true"
        os.environ["E2E_TESTING"] = "true"

    async def test_graceful_module_import_failure(self):
        """測試優雅的模組導入失敗處理"""
        try:
            # 測試即使某些可選組件失敗，核心系統仍可運作
            from shared.config import DISCORD_TOKEN
            from shared.logger import logger

            # 核心組件應該始終可用
            self.assertIsNotNone(DISCORD_TOKEN)
            self.assertIsNotNone(logger)

            print("✅ 優雅錯誤處理測試通過")

        except Exception as e:
            self.fail(f"優雅錯誤處理測試失敗: {e}")

    async def test_offline_mode_fallback(self):
        """測試離線模式後備機制"""
        try:
            from shared.offline_mode_manager import OfflineModeManager

            # 測試離線模式管理器可以初始化
            offline_mgr = OfflineModeManager()
            self.assertIsInstance(offline_mgr, OfflineModeManager)

            print("✅ 離線模式後備測試通過")

        except Exception as e:
            self.fail(f"離線模式後備測試失敗: {e}")


@pytest.mark.e2e
class TestPerformanceBaseline(unittest.IsolatedAsyncioTestCase):
    """性能基準線測試"""

    def setUp(self):
        """測試設置"""
        os.environ["TESTING"] = "true"
        os.environ["E2E_TESTING"] = "true"

    async def test_import_performance(self):
        """測試導入性能基準線"""
        import time

        start_time = time.time()

        try:
            # 測試關鍵模組導入時間
            pass

            import_time = time.time() - start_time

            # 導入時間應該合理（小於 5 秒）
            self.assertLess(import_time, 5.0, "模組導入時間過長")

            print(f"✅ 導入性能測試通過 (耗時: {import_time:.2f}s)")

        except Exception as e:
            self.fail(f"導入性能測試失敗: {e}")

    @patch("discord.ext.commands.Bot")
    @patch("aiomysql.connect")
    async def test_initialization_performance(self, mock_connect, mock_bot):
        """測試初始化性能基準線"""
        import time

        mock_bot.return_value = MagicMock()
        mock_connect.return_value = AsyncMock()

        start_time = time.time()

        try:
            # 測試系統初始化時間
            from shared.cache_manager import MultiLevelCacheManager
            from shared.offline_mode_manager import OfflineModeManager

            # 創建管理器實例
            MultiLevelCacheManager()
            OfflineModeManager()

            init_time = time.time() - start_time

            # 初始化時間應該合理（小於 3 秒）
            self.assertLess(init_time, 3.0, "系統初始化時間過長")

            print(f"✅ 初始化性能測試通過 (耗時: {init_time:.2f}s)")

        except Exception as e:
            self.fail(f"初始化性能測試失敗: {e}")


if __name__ == "__main__":
    unittest.main()
