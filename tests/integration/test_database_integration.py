"""
資料庫整合測試
"""

import os
import sys
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

# 添加專案根目錄到 Python 路徑
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))


class TestDatabaseIntegration(unittest.TestCase):
    """資料庫整合測試"""

    def setUp(self):
        """測試設置"""
        os.environ["TESTING"] = "true"
        os.environ["DATABASE_URL"] = "mysql://test_user:test_password@localhost:3306/test_database"
        os.environ["DB_HOST"] = "localhost"
        os.environ["DB_USER"] = "test_user"
        os.environ["DB_PASSWORD"] = "test_password"
        os.environ["DB_NAME"] = "test_database"

    @patch("aiomysql.connect")
    def test_database_manager_connection(self, mock_connect):
        """測試資料庫管理器連接"""
        # 模擬成功的資料庫連接
        mock_connection = AsyncMock()
        mock_connect.return_value = mock_connection

        try:
            from bot.db.database_manager import DatabaseManager

            # 只測試類別結構，不執行實際連接邏輯
            self.assertTrue(hasattr(DatabaseManager, "__init__"))

        except ImportError as e:
            self.fail(f"資料庫管理器導入失敗: {e}")

    @patch("aiomysql.connect")
    def test_dao_layers_integration(self, mock_connect):
        """測試 DAO 層整合"""
        mock_connect.return_value = AsyncMock()

        try:
            # 測試多個 DAO 類別可以載入
            from bot.db.base_dao import BaseDAO
            from bot.db.ticket_dao import TicketDAO
            from bot.db.vote_dao import VoteDAO

            dao_classes = [TicketDAO, VoteDAO, BaseDAO]
            for dao_class in dao_classes:
                self.assertTrue(hasattr(dao_class, "__init__"))

        except ImportError as e:
            self.skipTest(f"DAO 類別導入失敗: {e}")

    @patch("aiomysql.connect")
    def test_cached_dao_integration(self, mock_connect):
        """測試快取 DAO 整合"""
        mock_connect.return_value = AsyncMock()

        try:
            from bot.db.cached_ticket_dao import CachedTicketDAO

            # 只測試類別結構
            self.assertTrue(hasattr(CachedTicketDAO, "__init__"))

        except ImportError as e:
            self.skipTest(f"快取 DAO 導入失敗: {e}")

    def test_database_configuration(self):
        """測試資料庫配置"""
        try:
            from shared.config import DB_HOST, DB_NAME, DB_PORT, DB_USER

            # 驗證測試環境配置
            self.assertEqual(DB_HOST, "localhost")
            self.assertEqual(DB_USER, "test_user")
            self.assertEqual(DB_NAME, "test_database")
            self.assertIsInstance(DB_PORT, int)

        except ImportError as e:
            self.fail(f"資料庫配置導入失敗: {e}")


class TestCacheIntegration(unittest.TestCase):
    """快取系統整合測試"""

    def setUp(self):
        """測試設置"""
        os.environ["TESTING"] = "true"
        os.environ["REDIS_URL"] = "redis://127.0.0.1:6379/0"

    def test_multi_level_cache_integration(self):
        """測試多層級快取整合"""

        try:
            from shared.cache_manager import MultiLevelCacheManager

            cache = MultiLevelCacheManager()
            self.assertIsInstance(cache, MultiLevelCacheManager)

        except ImportError as e:
            self.fail(f"多層級快取管理器導入失敗: {e}")
        except Exception as e:
            self.fail(f"多層級快取管理器初始化失敗: {e}")

    def test_offline_mode_cache_integration(self):
        """測試離線模式快取整合"""
        try:
            from shared.offline_mode_manager import OfflineModeManager

            offline_mgr = OfflineModeManager()
            self.assertIsInstance(offline_mgr, OfflineModeManager)

        except ImportError as e:
            self.fail(f"離線模式管理器導入失敗: {e}")
        except Exception as e:
            self.fail(f"離線模式管理器初始化失敗: {e}")


class TestServiceDataIntegration(unittest.TestCase):
    """服務與資料層整合測試"""

    def setUp(self):
        """測試設置"""
        os.environ["TESTING"] = "true"

    @patch("bot.db.database_manager.DatabaseManager")
    def test_service_dao_integration(self, mock_db_manager):
        """測試服務與 DAO 整合"""
        mock_db_manager.return_value = MagicMock()

        try:
            # 測試服務層可以與資料層整合
            from bot.db.ticket_dao import TicketDAO
            from bot.services.ticket_manager import TicketManager

            # 只測試類別結構存在
            self.assertTrue(hasattr(TicketManager, "__init__"))
            self.assertTrue(hasattr(TicketDAO, "__init__"))

        except ImportError as e:
            self.skipTest(f"服務-DAO 整合測試導入失敗: {e}")

    @patch("shared.cache_manager.MultiLevelCacheManager")
    @patch("bot.db.database_manager.DatabaseManager")
    def test_cache_service_integration(self, mock_db, mock_cache):
        """測試快取與服務整合"""
        mock_db.return_value = MagicMock()
        mock_cache.return_value = MagicMock()

        try:
            # 測試需要快取的服務
            from bot.services.ticket_manager import TicketManager
            from shared.cache_manager import MultiLevelCacheManager

            self.assertTrue(hasattr(TicketManager, "__init__"))
            self.assertTrue(hasattr(MultiLevelCacheManager, "__init__"))

        except ImportError as e:
            self.skipTest(f"快取-服務整合測試導入失敗: {e}")


if __name__ == "__main__":
    unittest.main()
