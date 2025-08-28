"""
測試配置模組的單元測試
"""

import os
import sys
import unittest
from unittest.mock import patch, MagicMock

# 添加專案根目錄到 Python 路徑
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))


class TestConfig(unittest.TestCase):
    """配置模組測試"""

    def setUp(self):
        """測試設置"""
        os.environ["TESTING"] = "true"
        # 設置測試環境變數
        os.environ["DISCORD_TOKEN"] = (
            "test_token_comprehensive_validation_length_requirement_met_12345678_abcdefghijk"
        )
        os.environ["DB_HOST"] = "localhost"
        os.environ["DB_USER"] = "test_user"
        os.environ["DB_PASSWORD"] = "test_password"
        os.environ["DB_NAME"] = "test_database"
        os.environ["JWT_SECRET"] = "test_jwt_secret_for_automated_testing_purposes_only"

    def test_config_import(self):
        """測試配置模組可以正常導入"""
        try:
            from shared.config import DISCORD_TOKEN, DB_HOST

            self.assertIsNotNone(DISCORD_TOKEN)
            self.assertIsNotNone(DB_HOST)
        except ImportError as e:
            self.fail(f"配置模組導入失敗: {e}")

    def test_environment_variables(self):
        """測試環境變數是否正確載入"""
        from shared.config import DISCORD_TOKEN, DB_HOST, DB_USER

        self.assertEqual(DB_HOST, "localhost")
        self.assertEqual(DB_USER, "test_user")
        self.assertTrue(DISCORD_TOKEN.startswith("test_token"))

    def test_database_config(self):
        """測試資料庫配置"""
        from shared.config import DB_HOST, DB_PORT, DB_NAME

        self.assertEqual(DB_HOST, "localhost")
        self.assertEqual(DB_NAME, "test_database")
        self.assertIsInstance(DB_PORT, (int, str))


class TestLogger(unittest.TestCase):
    """日誌系統測試"""

    def test_logger_import(self):
        """測試日誌模組可以正常導入"""
        try:
            from shared.logger import logger

            self.assertIsNotNone(logger)
        except ImportError as e:
            self.fail(f"日誌模組導入失敗: {e}")

    def test_logger_functionality(self):
        """測試日誌功能"""
        from shared.logger import logger

        # 測試基本日誌方法
        try:
            logger.info("Test info message")
            logger.debug("Test debug message")
            logger.warning("Test warning message")
        except Exception as e:
            self.fail(f"日誌記錄失敗: {e}")


if __name__ == "__main__":
    unittest.main()
