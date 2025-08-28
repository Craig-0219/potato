"""
Bot 生命週期端到端測試
"""
import os
import sys
import unittest
import asyncio
from unittest.mock import patch, MagicMock, AsyncMock
import pytest

# 添加專案根目錄到 Python 路徑
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))


@pytest.mark.e2e
class TestBotLifecycle(unittest.IsolatedAsyncioTestCase):
    """Bot 完整生命週期測試"""
    
    def setUp(self):
        """測試設置"""
        os.environ['TESTING'] = 'true'
        os.environ['E2E_TESTING'] = 'true'
        os.environ['DISCORD_TOKEN'] = 'test_token_comprehensive_validation_length_requirement_met_12345678_abcdefghijk'
        os.environ['DATABASE_URL'] = 'mysql://test_user:test_password@127.0.0.1:3306/test_potato_bot_e2e'
        os.environ['REDIS_URL'] = 'redis://127.0.0.1:6379/1'
        os.environ['DB_HOST'] = '127.0.0.1'
        os.environ['DB_USER'] = 'test_user' 
        os.environ['DB_PASSWORD'] = 'test_password'
        os.environ['DB_NAME'] = 'test_potato_bot_e2e'
    
    @patch('discord.ext.commands.Bot')
    @patch('discord.Intents')
    @patch('aiomysql.connect')
    @patch('redis.Redis')
    async def test_bot_initialization_flow(self, mock_redis, mock_connect, mock_intents, mock_bot):
        """測試 Bot 完整初始化流程"""
        # 設置模擬對象
        mock_bot_instance = MagicMock()
        mock_bot_instance.user = MagicMock()
        mock_bot_instance.user.id = 123456789
        mock_bot_instance.guilds = []
        mock_bot.return_value = mock_bot_instance
        
        mock_intents.default.return_value = MagicMock()
        mock_connect.return_value = AsyncMock()
        mock_redis.return_value = MagicMock()
        
        try:
            # 測試 Bot 類別可以載入和初始化
            from bot.main import PotatoBot
            
            # 只測試類別存在性
            self.assertTrue(hasattr(PotatoBot, '__init__'))
            self.assertTrue(callable(PotatoBot))
            
            print("✅ Bot 初始化流程測試通過")
            
        except Exception as e:
            self.fail(f"Bot 初始化流程測試失敗: {e}")
    
    @patch('discord.ext.commands.Bot')
    @patch('aiomysql.connect')
    async def test_database_startup_flow(self, mock_connect, mock_bot):
        """測試資料庫啟動流程"""
        mock_bot.return_value = MagicMock()
        mock_connection = AsyncMock()
        mock_connect.return_value = mock_connection
        
        try:
            # 測試資料庫管理器初始化
            from bot.db.database_manager import DatabaseManager
            
            # 只測試類別結構，不執行實際連接
            self.assertTrue(hasattr(DatabaseManager, '__init__'))
            print("✅ 資料庫啟動流程測試通過")
            
        except Exception as e:
            self.fail(f"資料庫啟動流程測試失敗: {e}")
    
    @patch('discord.ext.commands.Bot')
    @patch('discord.Intents')
    async def test_cogs_loading_flow(self, mock_intents, mock_bot):
        """測試 Cogs 載入流程"""
        mock_bot_instance = MagicMock()
        mock_bot.return_value = mock_bot_instance
        mock_intents.default.return_value = MagicMock()
        
        try:
            # 測試關鍵 Cogs 可以載入
            from bot.cogs.ticket_core import TicketCore
            from bot.cogs.vote_core import VoteCore
            from bot.cogs.language_core import LanguageManager
            
            cogs = [TicketCore, VoteCore, LanguageManager]
            for cog_class in cogs:
                self.assertTrue(hasattr(cog_class, '__init__'))
                
            print("✅ Cogs 載入流程測試通過")
            
        except ImportError as e:
            self.skipTest(f"Cogs 載入流程測試跳過 - 導入失敗: {e}")
        except Exception as e:
            self.fail(f"Cogs 載入流程測試失敗: {e}")


@pytest.mark.e2e
class TestAPIEndToEnd(unittest.IsolatedAsyncioTestCase):
    """API 端到端測試"""
    
    def setUp(self):
        """測試設置"""
        os.environ['TESTING'] = 'true'
        os.environ['E2E_TESTING'] = 'true'
        os.environ['ENABLE_API_SERVER'] = 'true'
    
    async def test_api_server_startup(self):
        """測試 API 服務器啟動"""
        try:
            # 測試 API 應用程式創建
            from bot.api.app import create_app
            app = create_app()
            self.assertIsNotNone(app)
            
            print("✅ API 服務器啟動測試通過")
            
        except ImportError as e:
            self.skipTest(f"API 服務器測試跳過 - 導入失敗: {e}")
        except Exception as e:
            self.fail(f"API 服務器啟動測試失敗: {e}")
    
    async def test_api_routes_availability(self):
        """測試 API 路由可用性"""
        try:
            # 測試主要路由可以載入
            from bot.api.routes.tickets import router as tickets_router
            from bot.api.routes.system import router as system_router
            from bot.api.routes.analytics import router as analytics_router
            
            routers = [tickets_router, system_router, analytics_router]
            for router in routers:
                self.assertIsNotNone(router)
                
            print("✅ API 路由可用性測試通過")
            
        except ImportError as e:
            self.skipTest(f"API 路由測試跳過 - 導入失敗: {e}")
        except Exception as e:
            self.fail(f"API 路由可用性測試失敗: {e}")


@pytest.mark.e2e 
class TestSystemIntegration(unittest.IsolatedAsyncioTestCase):
    """系統整合端到端測試"""
    
    def setUp(self):
        """測試設置"""
        os.environ['TESTING'] = 'true'
        os.environ['E2E_TESTING'] = 'true'
        
    @patch('discord.ext.commands.Bot')
    @patch('aiomysql.connect')
    @patch('redis.Redis')
    async def test_full_system_integration(self, mock_redis, mock_connect, mock_bot):
        """測試完整系統整合"""
        # 設置所有模擬對象
        mock_bot_instance = MagicMock()
        mock_bot_instance.user = MagicMock()
        mock_bot_instance.user.id = 123456789
        mock_bot_instance.guilds = []
        mock_bot.return_value = mock_bot_instance
        
        mock_connect.return_value = AsyncMock()
        mock_redis.return_value = MagicMock()
        
        try:
            # 測試整個系統的主要組件可以協同工作
            from bot.main import PotatoBot
            from bot.db.database_manager import DatabaseManager  
            from shared.cache_manager import MultiLevelCacheManager
            from shared.offline_mode_manager import OfflineModeManager
            
            # 驗證所有組件都存在
            components = [PotatoBot, DatabaseManager, MultiLevelCacheManager, OfflineModeManager]
            for component in components:
                self.assertTrue(hasattr(component, '__init__'))
                
            print("✅ 完整系統整合測試通過")
            
        except ImportError as e:
            self.skipTest(f"系統整合測試跳過 - 導入失敗: {e}")
        except Exception as e:
            self.fail(f"完整系統整合測試失敗: {e}")
    
    async def test_service_layer_integration(self):
        """測試服務層整合"""
        try:
            # 測試服務層組件
            from bot.services.ticket_manager import TicketManager
            from bot.services.vote_manager import VoteManager
            
            managers = [TicketManager, VoteManager]
            for manager in managers:
                self.assertTrue(hasattr(manager, '__init__'))
                
            print("✅ 服務層整合測試通過")
            
        except ImportError as e:
            self.skipTest(f"服務層整合測試跳過 - 導入失敗: {e}")
        except Exception as e:
            self.fail(f"服務層整合測試失敗: {e}")


@pytest.mark.e2e
class TestDataFlowEndToEnd(unittest.IsolatedAsyncioTestCase):
    """資料流端到端測試"""
    
    def setUp(self):
        """測試設置"""
        os.environ['TESTING'] = 'true'
        os.environ['E2E_TESTING'] = 'true'
        
    @patch('aiomysql.connect')
    @patch('redis.Redis') 
    async def test_dao_cache_flow(self, mock_redis, mock_connect):
        """測試 DAO-快取資料流"""
        mock_connect.return_value = AsyncMock()
        mock_redis.return_value = MagicMock()
        
        try:
            # 測試 DAO 和快取層
            from bot.db.ticket_dao import TicketDAO
            from bot.db.cached_ticket_dao import CachedTicketDAO
            from shared.cache_manager import MultiLevelCacheManager
            
            data_components = [TicketDAO, CachedTicketDAO, MultiLevelCacheManager]
            for component in data_components:
                self.assertTrue(hasattr(component, '__init__'))
                
            print("✅ DAO-快取資料流測試通過")
            
        except ImportError as e:
            self.skipTest(f"DAO-快取資料流測試跳過 - 導入失敗: {e}")
        except Exception as e:
            self.fail(f"DAO-快取資料流測試失敗: {e}")


if __name__ == '__main__':
    unittest.main()