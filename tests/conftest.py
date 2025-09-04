"""
Test configuration and fixtures for Potato Bot tests.
"""
import asyncio
import pytest
import pytest_asyncio
from unittest.mock import MagicMock, AsyncMock
from typing import AsyncGenerator


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture
async def mock_bot():
    """Mock Discord bot instance."""
    bot = MagicMock()
    bot.user = MagicMock()
    bot.user.id = 123456789
    bot.user.name = "TestBot"
    bot.guilds = []
    return bot


@pytest_asyncio.fixture
async def mock_db_pool():
    """Mock database pool for testing."""
    pool = AsyncMock()
    pool.acquire = AsyncMock()
    pool.release = AsyncMock()
    return pool


@pytest_asyncio.fixture
async def mock_redis_client():
    """Mock Redis client for testing."""
    redis = AsyncMock()
    redis.get = AsyncMock(return_value=None)
    redis.set = AsyncMock(return_value=True)
    redis.delete = AsyncMock(return_value=1)
    redis.exists = AsyncMock(return_value=0)
    return redis


@pytest.fixture
def mock_settings():
    """Mock application settings."""
    class MockSettings:
        database_url = "sqlite:///:memory:"
        redis_url = "redis://localhost:6379/0"
        discord_token = "test_token"
        jwt_secret = "test_secret_key_for_testing_only"
        environment = "test"
        debug = True
        
    return MockSettings()


@pytest.fixture
def sample_user_data():
    """Sample user data for testing."""
    return {
        "user_id": "123456789",
        "guild_id": "987654321",
        "username": "testuser",
        "display_name": "Test User",
        "joined_at": "2024-01-01T00:00:00Z"
    }


@pytest.fixture
def sample_ticket_data():
    """Sample ticket data for testing."""
    return {
        "ticket_id": "ticket_123",
        "user_id": "123456789",
        "guild_id": "987654321", 
        "category": "support",
        "title": "Test Ticket",
        "description": "This is a test ticket",
        "status": "open",
        "priority": "medium",
        "created_at": "2024-01-01T00:00:00Z"
    }


@pytest.fixture
def sample_economy_data():
    """Sample economy data for testing."""
    return {
        "user_id": "123456789",
        "guild_id": "987654321",
        "balance": 1000,
        "daily_claimed_at": None,
        "total_earned": 1000,
        "total_spent": 0
    }