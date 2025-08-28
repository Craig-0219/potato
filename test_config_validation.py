#!/usr/bin/env python3
"""
配置驗證測試腳本
用於 CI/CD 流程中驗證配置載入和基本系統初始化
"""

import sys
import os
import traceback

def test_basic_imports():
    """測試基本模組導入"""
    print("🔍 測試基本模組導入...")
    try:
        import shared.config
        import shared.logger
        print("✅ 核心模組導入成功")
        return True
    except Exception as e:
        print(f"❌ 核心模組導入失敗: {e}")
        return False

def test_config_loading():
    """測試配置載入"""
    print("🔧 測試配置載入...")
    try:
        from shared.config import DISCORD_TOKEN, DB_HOST
        
        if not DISCORD_TOKEN:
            print("❌ DISCORD_TOKEN 未設置")
            return False
            
        if not DB_HOST:
            print("❌ DB_HOST 未設置") 
            return False
            
        print("✅ 基本配置載入成功")
        print(f"  DISCORD_TOKEN: {DISCORD_TOKEN[:20]}..." if DISCORD_TOKEN else "None")
        print(f"  DB_HOST: {DB_HOST}")
        return True
        
    except Exception as e:
        print(f"❌ 配置載入失敗: {e}")
        return False

def test_database_manager():
    """測試資料庫管理器初始化"""
    print("🗄️ 測試資料庫管理器初始化...")
    try:
        from bot.db.database_manager import DatabaseManager
        print("✅ DatabaseManager 可初始化")
        return True
    except Exception as e:
        print(f"❌ DatabaseManager 初始化失敗: {e}")
        return False

def test_cache_manager():
    """測試快取管理器初始化"""
    print("💾 測試快取管理器初始化...")
    try:
        from shared.cache_manager import MultiLevelCacheManager
        cache = MultiLevelCacheManager()
        print("✅ MultiLevelCacheManager 可初始化")
        return True
    except Exception as e:
        print(f"❌ MultiLevelCacheManager 初始化失敗: {e}")
        return False

def test_core_cogs():
    """測試核心 Cogs 載入"""
    print("🧪 測試核心 Cogs 載入...")
    try:
        from unittest.mock import patch, MagicMock
        
        with patch('discord.ext.commands.Bot') as mock_bot:
            with patch('discord.Intents'):
                mock_bot.return_value = MagicMock()
                
                # 測試關鍵 Cogs
                from bot.cogs.ticket_core import TicketCore
                from bot.cogs.vote_core import VoteCore  
                from bot.cogs.language_core import LanguageManager
                
                print("✅ 核心 Cogs 可正常載入")
                return True
                
    except Exception as e:
        print(f"❌ 核心 Cogs 載入失敗: {e}")
        return False

def main():
    """主測試函數"""
    print("🚀 開始配置驗證測試...")
    print("=" * 50)
    
    # 確保測試環境
    if not os.getenv("TESTING"):
        os.environ["TESTING"] = "true"
    
    # 添加專案根目錄到路徑
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    
    tests = [
        test_basic_imports,
        test_config_loading, 
        test_database_manager,
        test_cache_manager,
        test_core_cogs
    ]
    
    passed = 0
    failed = 0
    
    for test_func in tests:
        try:
            if test_func():
                passed += 1
            else:
                failed += 1
        except Exception as e:
            print(f"❌ 測試 {test_func.__name__} 異常: {e}")
            print(traceback.format_exc())
            failed += 1
        print("-" * 30)
    
    print("📊 測試結果總結:")
    print(f"  通過: {passed}")
    print(f"  失敗: {failed}")
    print(f"  總計: {passed + failed}")
    
    if failed == 0:
        print("🎉 所有配置驗證測試通過！")
        return 0
    else:
        print(f"❌ 有 {failed} 個測試失敗")
        return 1

if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)