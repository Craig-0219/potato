"""
資料庫相關組件的單元測試
"""

import os
import sys
import unittest
from unittest.mock import patch, MagicMock, AsyncMock

# 添加專案根目錄到 Python 路徑
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))


class TestDatabaseManager(unittest.TestCase):
    """資料庫管理器測試"""

    def setUp(self):
        """測試設置"""
        os.environ["TESTING"] = "true"
        os.environ["DATABASE_URL"] = "sqlite:///test.db"

    @patch("aiomysql.connect")
    def test_database_manager_import(self, mock_connect):
        """測試資料庫管理器可以正常導入"""
        mock_connect.return_value = AsyncMock()

        try:
            from bot.db.database_manager import DatabaseManager

            self.assertTrue(hasattr(DatabaseManager, "__init__"))
        except ImportError as e:
            self.fail(f"資料庫管理器導入失敗: {e}")

    @patch("aiomysql.connect")
    def test_database_manager_initialization(self, mock_connect):
        """測試資料庫管理器初始化"""
        mock_connect.return_value = AsyncMock()

        try:
            from bot.db.database_manager import DatabaseManager

            # 只測試類別可以實例化，不執行實際資料庫連接
            manager = DatabaseManager.__new__(DatabaseManager)
            self.assertIsInstance(manager, DatabaseManager)
        except Exception as e:
            self.fail(f"資料庫管理器初始化失敗: {e}")


class TestBaseDAO(unittest.TestCase):
    """基礎 DAO 測試"""

    def setUp(self):
        """測試設置"""
        os.environ["TESTING"] = "true"

    def test_base_dao_import(self):
        """測試基礎 DAO 可以正常導入"""
        try:
            from bot.db.base_dao import BaseDAO

            self.assertTrue(hasattr(BaseDAO, "__init__"))
        except ImportError as e:
            self.fail(f"BaseDAO 導入失敗: {e}")

    @patch("bot.db.database_manager.DatabaseManager")
    def test_ticket_dao_import(self, mock_db):
        """測試 TicketDAO 可以正常導入"""
        mock_db.return_value = MagicMock()

        try:
            from bot.db.ticket_dao import TicketDAO

            self.assertTrue(hasattr(TicketDAO, "__init__"))
        except ImportError as e:
            self.fail(f"TicketDAO 導入失敗: {e}")

    @patch("bot.db.database_manager.DatabaseManager")
    def test_vote_dao_import(self, mock_db):
        """測試 VoteDAO 可以正常導入"""
        mock_db.return_value = MagicMock()

        try:
            from bot.db.vote_dao import VoteDAO

            self.assertTrue(hasattr(VoteDAO, "__init__"))
        except ImportError as e:
            self.fail(f"VoteDAO 導入失敗: {e}")


class TestCacheManager(unittest.TestCase):
    """快取管理器測試"""

    def setUp(self):
        """測試設置"""
        os.environ["TESTING"] = "true"

    def test_cache_manager_import(self):
        """測試快取管理器可以正常導入"""
        try:
            from shared.cache_manager import MultiLevelCacheManager

            self.assertTrue(hasattr(MultiLevelCacheManager, "__init__"))
        except ImportError as e:
            self.fail(f"MultiLevelCacheManager 導入失敗: {e}")

    def test_cache_manager_initialization(self):
        """測試快取管理器初始化"""
        try:
            from shared.cache_manager import MultiLevelCacheManager

            cache = MultiLevelCacheManager()
            self.assertIsInstance(cache, MultiLevelCacheManager)
        except Exception as e:
            self.fail(f"MultiLevelCacheManager 初始化失敗: {e}")


if __name__ == "__main__":
    unittest.main()
