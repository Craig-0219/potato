"""
pytest 全局配置文件
為所有測試設置一致的環境和行為
"""

import os
import pytest
import sys
from pathlib import Path

# 添加專案根目錄到 Python 路徑
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))


def pytest_configure(config):
    """pytest 配置初始化"""
    # 設置測試環境標記
    os.environ["TESTING"] = "true"
    
    # 設置一致的測試環境變數
    test_env = {
        "DISCORD_TOKEN": "test_token_minimum_50_characters_for_testing_purposes_12345",
        "DB_HOST": "localhost",
        "DB_USER": "test_user",
        "DB_PASSWORD": "test_password",
        "DB_NAME": "test_database",
        "DB_PORT": "3306",
        "DATABASE_URL": "mysql://test_user:test_password@localhost:3306/test_database",
        "REDIS_URL": "redis://localhost:6379/1",
        "REDIS_HOST": "localhost",
        "REDIS_PORT": "6379",
        "REDIS_DB": "1",
        "API_PORT": "5001",
        "API_HOST": "127.0.0.1",
        "DEBUG": "true",
        "LOG_LEVEL": "DEBUG",
        "ENABLE_METRICS": "false",
        "ENABLE_MONITORING": "false",
        "ENABLE_EXTERNAL_APIS": "false",
        "JWT_SECRET": "test_jwt_secret_for_automated_testing_purposes_only",
        "E2E_TESTING": "false"  # 預設為false，E2E測試會自己設置
    }
    
    # 只設置尚未設置的環境變數
    for key, value in test_env.items():
        if key not in os.environ:
            os.environ[key] = value


@pytest.fixture(scope="session", autouse=True)
def setup_test_environment():
    """設置測試環境的 fixture"""
    # 確保測試環境設置
    os.environ["TESTING"] = "true"
    
    # 導入測試配置模組
    try:
        from shared.test_config import test_config
        test_config.setup_test_environment()
        
        yield
        
        # 清理測試環境
        test_config.teardown_test_environment()
    except ImportError:
        # 如果測試配置模組不可用，使用基本設置
        yield


@pytest.fixture
def mock_discord_bot():
    """模擬 Discord Bot 的 fixture"""
    from unittest.mock import MagicMock
    
    bot = MagicMock()
    bot.user.id = 123456789
    bot.user.name = "TestBot"
    bot.guilds = []
    
    return bot


@pytest.fixture
def mock_database():
    """模擬資料庫連接的 fixture"""
    from unittest.mock import AsyncMock, MagicMock
    
    mock_pool = AsyncMock()
    mock_connection = AsyncMock()
    mock_cursor = AsyncMock()
    
    mock_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_connection)
    mock_pool.acquire.return_value.__aexit__ = AsyncMock(return_value=None)
    mock_connection.cursor.return_value.__aenter__ = AsyncMock(return_value=mock_cursor)
    mock_connection.cursor.return_value.__aexit__ = AsyncMock(return_value=None)
    
    return {
        "pool": mock_pool,
        "connection": mock_connection,
        "cursor": mock_cursor
    }


@pytest.fixture
def mock_redis():
    """模擬 Redis 連接的 fixture"""
    from unittest.mock import AsyncMock
    
    redis = AsyncMock()
    redis.get.return_value = None
    redis.set.return_value = True
    redis.delete.return_value = True
    redis.exists.return_value = False
    
    return redis


def pytest_runtest_setup(item):
    """每個測試運行前的設置"""
    # 確保每個測試都在乾淨的環境中運行
    if hasattr(item, "pytestmark"):
        for mark in item.pytestmark:
            if mark.name == "e2e":
                # E2E 測試的特殊設置
                os.environ["E2E_TESTING"] = "true"


def pytest_runtest_teardown(item):
    """每個測試運行後的清理"""
    # 重置 E2E 標記
    if "E2E_TESTING" in os.environ and os.environ["E2E_TESTING"] == "true":
        os.environ["E2E_TESTING"] = "false"


# 設置 pytest 標記
pytest_plugins = []

# pytest 配置已在 pytest.ini 中設置標記
# 無需額外的自定義標記配置函數