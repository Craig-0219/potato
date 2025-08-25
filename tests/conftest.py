# tests/conftest.py
"""
pytest 配置和共用測試夾具
"""

import pytest
import asyncio
import os
import tempfile
import shutil
from typing import AsyncGenerator, Generator
from unittest.mock import AsyncMock, MagicMock

# 設置測試環境變數
os.environ.update({
    'TESTING': 'true',
    'DB_HOST': 'localhost',
    'DB_PORT': '3306',
    'DB_USER': 'test_user',
    'DB_PASSWORD': 'test_password',
    'DB_NAME': 'test_potato_bot',
    'DISCORD_TOKEN': 'test_token_' + 'x' * 50,
    'JWT_SECRET': 'test_jwt_secret_key_for_testing_only',
    'LOG_LEVEL': 'DEBUG',
    'DEBUG': 'true'
})

import sys
sys.path.insert(0, '/root/projects/potato')

# Pytest asyncio 配置
pytest_plugins = ['pytest_asyncio']


@pytest.fixture(scope="session")
def event_loop():
    """創建事件循環供整個測試會話使用"""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session")
def temp_dir() -> Generator[str, None, None]:
    """創建臨時目錄"""
    temp_path = tempfile.mkdtemp(prefix="potato_bot_test_")
    yield temp_path
    shutil.rmtree(temp_path, ignore_errors=True)


@pytest.fixture
def mock_discord_bot():
    """模擬 Discord Bot 實例"""
    bot = MagicMock()
    bot.user = MagicMock()
    bot.user.id = 12345
    bot.user.name = "TestBot"
    bot.guilds = []
    return bot


@pytest.fixture
def mock_discord_guild():
    """模擬 Discord Guild 實例"""
    guild = MagicMock()
    guild.id = 1392536804355014676
    guild.name = "Test Guild"
    guild.members = []
    guild.roles = []
    guild.channels = []
    return guild


@pytest.fixture
def mock_discord_user():
    """模擬 Discord User 實例"""
    user = MagicMock()
    user.id = 98765
    user.name = "TestUser"
    user.discriminator = "0001"
    user.bot = False
    return user


@pytest.fixture
async def mock_db_connection():
    """模擬資料庫連接"""
    connection = AsyncMock()
    cursor = AsyncMock()
    connection.cursor.return_value.__aenter__.return_value = cursor
    cursor.fetchone = AsyncMock(return_value=None)
    cursor.fetchall = AsyncMock(return_value=[])
    cursor.execute = AsyncMock()
    return connection


@pytest.fixture
def mock_logger():
    """模擬日誌記錄器"""
    logger = MagicMock()
    logger.info = MagicMock()
    logger.error = MagicMock() 
    logger.warning = MagicMock()
    logger.debug = MagicMock()
    return logger


@pytest.fixture
def sample_ticket_data():
    """樣本票券資料"""
    return {
        'id': 1,
        'guild_id': 1392536804355014676,
        'user_id': 98765,
        'channel_id': 1234567890,
        'category': 'general',
        'subject': 'Test Ticket',
        'status': 'open',
        'priority': 'medium',
        'created_at': '2025-08-25 10:00:00',
        'updated_at': '2025-08-25 10:00:00'
    }


@pytest.fixture  
def sample_vote_data():
    """樣本投票資料"""
    return {
        'id': 1,
        'guild_id': 1392536804355014676,
        'user_id': 98765,
        'title': 'Test Vote',
        'description': 'This is a test vote',
        'options': ['Option A', 'Option B', 'Option C'],
        'vote_type': 'single_choice',
        'status': 'active',
        'created_at': '2025-08-25 10:00:00',
        'ends_at': '2025-08-26 10:00:00'
    }


@pytest.fixture
def api_headers():
    """API 請求標頭"""
    return {
        'Content-Type': 'application/json',
        'Authorization': 'Bearer test_jwt_token'
    }


@pytest.fixture
def mock_fastapi_request():
    """模擬 FastAPI 請求"""
    from fastapi import Request
    request = MagicMock(spec=Request)
    request.headers = {'Authorization': 'Bearer test_token'}
    request.client = MagicMock()
    request.client.host = '127.0.0.1'
    return request


# 測試資料庫設置
@pytest.fixture(scope="session")
async def setup_test_database():
    """設置測試資料庫（如果需要）"""
    # 這裡可以設置實際的測試資料庫
    # 目前使用模擬，如果需要真實資料庫測試，可以在此實作
    yield
    # 清理資料庫


# 自動使用的夾具
@pytest.fixture(autouse=True)
def isolate_tests():
    """確保每個測試獨立運行"""
    # 在每個測試前/後執行的清理工作
    yield
    # 清理工作


# Pytest 標記
def pytest_configure(config):
    """pytest 配置"""
    config.addinivalue_line(
        "markers", 
        "unit: 標記為單元測試"
    )
    config.addinivalue_line(
        "markers", 
        "integration: 標記為整合測試"
    )
    config.addinivalue_line(
        "markers", 
        "e2e: 標記為端到端測試"
    )
    config.addinivalue_line(
        "markers",
        "slow: 標記為慢速測試"
    )


# 跳過條件
def pytest_collection_modifyitems(config, items):
    """修改測試項目收集"""
    # 如果沒有指定標記，添加預設標記
    for item in items:
        # 根據路徑自動添加標記
        if "unit" in str(item.fspath):
            item.add_marker(pytest.mark.unit)
        elif "integration" in str(item.fspath):
            item.add_marker(pytest.mark.integration)
        elif "e2e" in str(item.fspath):
            item.add_marker(pytest.mark.e2e)