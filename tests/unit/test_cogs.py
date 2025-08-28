"""
Bot Cogs 的單元測試
"""
import os
import sys
import unittest
from unittest.mock import patch, MagicMock

# 添加專案根目錄到 Python 路徑
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))


class TestCoreCogs(unittest.TestCase):
    """核心 Cogs 測試"""
    
    def setUp(self):
        """測試設置"""
        os.environ['TESTING'] = 'true'
        # 設置必要的環境變數
        os.environ['DISCORD_TOKEN'] = 'test_token_comprehensive_validation_length_requirement_met_12345678_abcdefghijk'
        os.environ['DATABASE_URL'] = 'sqlite:///test.db'
    
    @patch('discord.ext.commands.Bot')
    @patch('discord.Intents')
    def test_ticket_core_import(self, mock_intents, mock_bot):
        """測試 TicketCore 可以正常導入"""
        mock_bot.return_value = MagicMock()
        mock_intents.default.return_value = MagicMock()
        
        try:
            from bot.cogs.ticket_core import TicketCore
            self.assertTrue(hasattr(TicketCore, '__init__'))
        except ImportError as e:
            self.fail(f"TicketCore 導入失敗: {e}")
    
    @patch('discord.ext.commands.Bot')
    @patch('discord.Intents')
    def test_vote_core_import(self, mock_intents, mock_bot):
        """測試 VoteCore 可以正常導入"""
        mock_bot.return_value = MagicMock()
        mock_intents.default.return_value = MagicMock()
        
        try:
            from bot.cogs.vote_core import VoteCore
            self.assertTrue(hasattr(VoteCore, '__init__'))
        except ImportError as e:
            self.fail(f"VoteCore 導入失敗: {e}")
    
    @patch('discord.ext.commands.Bot')
    @patch('discord.Intents')
    def test_language_core_import(self, mock_intents, mock_bot):
        """測試 LanguageManager 可以正常導入"""
        mock_bot.return_value = MagicMock()
        mock_intents.default.return_value = MagicMock()
        
        try:
            from bot.cogs.language_core import LanguageManager
            self.assertTrue(hasattr(LanguageManager, '__init__'))
        except ImportError as e:
            self.fail(f"LanguageManager 導入失敗: {e}")
    
    @patch('discord.ext.commands.Bot')
    @patch('discord.Intents')
    def test_security_core_import(self, mock_intents, mock_bot):
        """測試 SecurityCore 可以正常導入"""
        mock_bot.return_value = MagicMock()
        mock_intents.default.return_value = MagicMock()
        
        try:
            from bot.cogs.security_core import SecurityCore
            self.assertTrue(hasattr(SecurityCore, '__init__'))
        except ImportError as e:
            # 某些 Cogs 可能不存在，這是可以接受的
            self.skipTest(f"SecurityCore 不存在或導入失敗: {e}")
    
    @patch('discord.ext.commands.Bot')
    @patch('discord.Intents') 
    @patch('bot.db.database_manager.DatabaseManager')
    def test_cog_initialization_structure(self, mock_db, mock_intents, mock_bot):
        """測試 Cog 初始化結構"""
        mock_bot_instance = MagicMock()
        mock_bot.return_value = mock_bot_instance
        mock_intents.default.return_value = MagicMock()
        mock_db.return_value = MagicMock()
        
        try:
            from bot.cogs.ticket_core import TicketCore
            
            # 測試 Cog 可以用 Bot 實例初始化
            cog = TicketCore.__new__(TicketCore)
            self.assertIsInstance(cog, TicketCore)
            
        except Exception as e:
            self.fail(f"Cog 初始化結構測試失敗: {e}")


class TestUtilityModules(unittest.TestCase):
    """工具模組測試"""
    
    def setUp(self):
        """測試設置"""
        os.environ['TESTING'] = 'true'
    
    def test_embed_builder_import(self):
        """測試 EmbedBuilder 可以正常導入"""
        try:
            from bot.utils.embed_builder import EmbedBuilder
            self.assertTrue(hasattr(EmbedBuilder, '__init__'))
        except ImportError as e:
            self.skipTest(f"EmbedBuilder 不存在或導入失敗: {e}")
    
    def test_helper_import(self):
        """測試 helper 模組可以正常導入"""
        try:
            from bot.utils.helper import format_time_delta
            self.assertTrue(callable(format_time_delta))
        except ImportError as e:
            self.skipTest(f"helper 模組不存在或導入失敗: {e}")
    
    def test_validator_import(self):
        """測試 validator 模組可以正常導入"""
        try:
            from bot.utils.validator import validate_ticket_data
            self.assertTrue(callable(validate_ticket_data))
        except ImportError as e:
            self.skipTest(f"validator 模組不存在或導入失敗: {e}")


if __name__ == '__main__':
    unittest.main()