#!/usr/bin/env python3
# quick_test.py - 快速測試第一階段修復（修復版）
"""
快速測試腳本 - 驗證第一階段修復是否成功
在實際啟動 Bot 之前，先測試所有關鍵組件
"""

import sys
import os
import traceback
import importlib
from datetime import datetime  # 修復：添加 datetime 導入
from typing import Dict, List, Any

# 添加項目根目錄到路徑
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

class QuickTester:
    def __init__(self):
        self.results = {
            'passed': [],
            'failed': [],
            'warnings': []
        }
    
    def test_basic_imports(self) -> bool:
        """測試基本模組導入"""
        print("🔍 測試基本模組導入...")
        
        basic_modules = [
            'asyncio',
            'logging',
            'datetime',
            'typing',
            'json',
            'os',
            'sys'
        ]
        
        # 可選但重要的模組
        optional_modules = [
            'discord', 
            'aiomysql',
            'dotenv'
        ]
        
        failed = []
        optional_failed = []
        
        # 測試基本模組
        for module in basic_modules:
            try:
                importlib.import_module(module)
                self.results['passed'].append(f"✅ {module}")
            except ImportError as e:
                failed.append(f"❌ {module}: {e}")
                self.results['failed'].append(f"❌ {module}: {e}")
        
        # 測試可選模組
        for module in optional_modules:
            try:
                importlib.import_module(module)
                self.results['passed'].append(f"✅ {module}")
            except ImportError as e:
                optional_failed.append(f"⚠️ {module}: {e}")
                self.results['warnings'].append(f"⚠️ {module}: {e}")
        
        if failed:
            print("❌ 基本模組導入失敗：")
            for fail in failed:
                print(f"  {fail}")
            return False
        
        if optional_failed:
            print("⚠️ 可選模組缺失（需要安裝）：")
            for fail in optional_failed:
                print(f"  {fail}")
            print("請運行：pip install discord.py aiomysql python-dotenv")
            
        print("✅ 基本模組導入成功")
        return True
    
    def test_config_loading(self) -> bool:
        """測試配置載入"""
        print("🔍 測試配置載入...")
        
        try:
            # 檢查 .env 文件是否存在
            env_path = os.path.join(project_root, '.env')
            if not os.path.exists(env_path):
                self.results['warnings'].append("⚠️ .env 文件不存在")
                print("⚠️ .env 文件不存在，將使用預設配置測試")
            
            from shared.config import (
                DISCORD_TOKEN, DB_HOST, DB_USER, DB_PASSWORD, DB_NAME
            )
            
            # 基本檢查
            if DISCORD_TOKEN:
                self.results['passed'].append("✅ DISCORD_TOKEN 已設定")
            else:
                self.results['warnings'].append("⚠️ DISCORD_TOKEN 未設定")
            
            if all([DB_HOST, DB_USER, DB_PASSWORD, DB_NAME]):
                self.results['passed'].append("✅ 資料庫配置完整")
            else:
                self.results['warnings'].append("⚠️ 資料庫配置不完整")
            
            print("✅ 配置模組載入成功")
            return True
                
        except Exception as e:
            self.results['failed'].append(f"❌ 配置載入失敗: {e}")
            print(f"❌ 配置載入失敗：{e}")
            return False
    
    def test_database_pool(self) -> bool:
        """測試資料庫連接池"""
        print("🔍 測試資料庫連接池...")
        
        try:
            from bot.db.pool import MariaDBPool, db_pool
            
            # 測試連接池類別
            pool = MariaDBPool()
            self.results['passed'].append("✅ 資料庫連接池類別可用")
            
            # 檢查方法是否存在
            required_methods = ['initialize', 'acquire', 'release', 'connection', 'health_check']
            for method in required_methods:
                if hasattr(pool, method):
                    self.results['passed'].append(f"✅ {method} 方法存在")
                else:
                    self.results['failed'].append(f"❌ 缺少 {method} 方法")
                    return False
            
            print("✅ 資料庫連接池導入成功")
            print("ℹ️  實際連接測試需要資料庫運行")
            return True
            
        except Exception as e:
            self.results['failed'].append(f"❌ 資料庫連接池失敗: {e}")
            print(f"❌ 資料庫連接池測試失敗：{e}")
            return False
    
    def test_error_handler(self) -> bool:
        """測試錯誤處理器"""
        print("🔍 測試錯誤處理器...")
        
        try:
            from bot.utils.error_handler import (
                GlobalErrorHandler, 
                setup_error_handling,
                DatabaseErrorHandler,
                UserFriendlyErrors
            )
            
            # 測試類別是否可實例化
            try:
                # 需要一個假的 bot 對象進行測試
                class MockBot:
                    def __init__(self):
                        self.tree = MockTree()
                        
                    def event(self, func):
                        return func
                
                class MockTree:
                    def error(self, func):
                        return func
                
                mock_bot = MockBot()
                handler = GlobalErrorHandler(mock_bot)
                self.results['passed'].append("✅ GlobalErrorHandler 可實例化")
                
            except Exception as e:
                self.results['warnings'].append(f"⚠️ GlobalErrorHandler 實例化測試跳過: {e}")
            
            self.results['passed'].append("✅ 錯誤處理器導入成功")
            print("✅ 錯誤處理器導入成功")
            return True
            
        except Exception as e:
            self.results['failed'].append(f"❌ 錯誤處理器失敗: {e}")
            print(f"❌ 錯誤處理器測試失敗：{e}")
            return False
    
    def test_ticket_constants(self) -> bool:
        """測試票券常數"""
        print("🔍 測試票券常數...")
        
        try:
            from bot.utils.ticket_constants import (
                TicketConstants,
                validate_text_input,
                validate_numeric_input,
                get_priority_emoji,
                ERROR_MESSAGES
            )
            
            # 測試驗證函數
            text_result = validate_text_input("測試", "ticket_type")
            numeric_result = validate_numeric_input(3, "rating")
            
            if text_result[0] and numeric_result[0]:
                self.results['passed'].append("✅ 驗證函數正常工作")
            else:
                self.results['failed'].append(f"❌ 驗證函數錯誤: text={text_result}, numeric={numeric_result}")
                return False
            
            # 測試常數
            if hasattr(TicketConstants, 'PRIORITIES') and TicketConstants.PRIORITIES:
                self.results['passed'].append("✅ TicketConstants 正常")
            else:
                self.results['failed'].append("❌ TicketConstants 缺少 PRIORITIES")
                return False
            
            # 測試工具函數
            emoji = get_priority_emoji("high")
            if emoji:
                self.results['passed'].append("✅ 工具函數正常")
            else:
                self.results['failed'].append("❌ get_priority_emoji 返回空值")
                return False
                
            print("✅ 票券常數測試成功")
            return True
                
        except Exception as e:
            self.results['failed'].append(f"❌ 票券常數失敗: {e}")
            print(f"❌ 票券常數測試失敗：{e}")
            return False
    
    def test_embed_builder(self) -> bool:
        """測試 Embed 建構器"""
        print("🔍 測試 Embed 建構器...")
        
        try:
            # 先檢查 discord 是否可用
            try:
                import discord
            except ImportError:
                self.results['warnings'].append("⚠️ discord.py 未安裝，跳過 Embed 測試")
                print("⚠️ discord.py 未安裝，跳過 Embed 測試")
                return True
            
            from bot.utils.embed_builder import EmbedBuilder
            
            # 測試建立基本 embed
            embed = EmbedBuilder.success("測試", "這是一個測試")
            
            if embed and hasattr(embed, 'title') and hasattr(embed, 'description'):
                self.results['passed'].append("✅ Embed 建構器正常")
                print("✅ Embed 建構器測試成功")
                return True
            else:
                self.results['failed'].append("❌ Embed 建構器返回無效結果")
                return False
                
        except Exception as e:
            self.results['failed'].append(f"❌ Embed 建構器失敗: {e}")
            print(f"❌ Embed 建構器測試失敗：{e}")
            return False
    
    def test_view_registry(self) -> bool:
        """測試 View 註冊"""
        print("🔍 測試 View 註冊...")
        
        try:
            from bot.register.register import (
                register_all_views,
                create_dynamic_view,
                validate_view_registration
            )
            
            # 測試函數是否可調用
            if callable(register_all_views) and callable(create_dynamic_view):
                self.results['passed'].append("✅ View 註冊函數可用")
            else:
                self.results['failed'].append("❌ View 註冊函數不可調用")
                return False
            
            print("✅ View 註冊測試成功")
            return True
            
        except Exception as e:
            self.results['failed'].append(f"❌ View 註冊失敗: {e}")
            print(f"❌ View 註冊測試失敗：{e}")
            return False
    
    def test_discord_integration(self) -> bool:
        """測試 Discord 整合（不實際連接）"""
        print("🔍 測試 Discord 整合...")
        
        try:
            import discord
            from discord.ext import commands
            
            # 創建測試 Bot 實例（不啟動）
            intents = discord.Intents.default()
            bot = commands.Bot(command_prefix='!', intents=intents)
            
            if bot and hasattr(bot, 'tree'):
                self.results['passed'].append("✅ Discord Bot 實例可創建")
                print("✅ Discord 整合測試成功")
                return True
            else:
                self.results['failed'].append("❌ Bot 實例無效")
                return False
            
        except ImportError:
            self.results['warnings'].append("⚠️ discord.py 未安裝，跳過 Discord 整合測試")
            print("⚠️ discord.py 未安裝，跳過 Discord 整合測試")
            return True
        except Exception as e:
            self.results['failed'].append(f"❌ Discord 整合失敗: {e}")
            print(f"❌ Discord 整合測試失敗：{e}")
            return False
    
    def run_all_tests(self) -> bool:
        """運行所有測試"""
        print("🚀 開始第一階段修復驗證...")
        print("=" * 50)
        
        tests = [
            ("基本模組導入", self.test_basic_imports),
            ("配置載入", self.test_config_loading),
            ("資料庫連接池", self.test_database_pool),
            ("錯誤處理器", self.test_error_handler),
            ("票券常數", self.test_ticket_constants),
            ("Embed 建構器", self.test_embed_builder),
            ("View 註冊", self.test_view_registry),
            ("Discord 整合", self.test_discord_integration)
        ]
        
        passed_count = 0
        total_count = len(tests)
        
        for test_name, test_func in tests:
            try:
                if test_func():
                    passed_count += 1
                    print(f"✅ {test_name} - 通過")
                else:
                    print(f"❌ {test_name} - 失敗")
                print()  # 空行分隔
            except Exception as e:
                print(f"❌ {test_name} - 執行錯誤：{e}")
                traceback.print_exc()
                print()
        
        print("=" * 50)
        print("📊 測試結果摘要：")
        print(f"✅ 通過：{passed_count}/{total_count}")
        print(f"❌ 失敗：{total_count - passed_count}/{total_count}")
        
        if self.results['passed']:
            print(f"\n✅ 成功項目（{len(self.results['passed'])}）：")
            for item in self.results['passed'][:10]:  # 只顯示前10個
                print(f"  {item}")
            if len(self.results['passed']) > 10:
                print(f"  ... 還有 {len(self.results['passed']) - 10} 個")
        
        if self.results['failed']:
            print(f"\n❌ 失敗項目（{len(self.results['failed'])}）：")
            for item in self.results['failed']:
                print(f"  {item}")
        
        if self.results['warnings']:
            print(f"\n⚠️ 警告項目（{len(self.results['warnings'])}）：")
            for item in self.results['warnings']:
                print(f"  {item}")
        
        success_rate = (passed_count / total_count) * 100
        print(f"\n📈 成功率：{success_rate:.1f}%")
        
        if success_rate >= 75:
            print("🎉 第一階段修復基本成功！可以嘗試啟動 Bot")
            return True
        else:
            print("⚠️ 修復尚未完成，建議先解決失敗項目")
            return False
    
    def generate_report(self) -> str:
        """生成詳細報告"""
        report = []
        report.append("# 第一階段修復驗證報告")
        report.append(f"生成時間：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        report.append("")
        
        if self.results['passed']:
            report.append("## ✅ 通過項目")
            for item in self.results['passed']:
                report.append(f"- {item}")
            report.append("")
        
        if self.results['failed']:
            report.append("## ❌ 失敗項目")
            for item in self.results['failed']:
                report.append(f"- {item}")
            report.append("")
        
        if self.results['warnings']:
            report.append("## ⚠️ 警告項目")
            for item in self.results['warnings']:
                report.append(f"- {item}")
            report.append("")
        
        report.append("## 📋 修復建議")
        if self.results['failed']:
            report.append("### 失敗項目修復建議：")
            for item in self.results['failed']:
                if "discord" in item.lower():
                    report.append("- 安裝 discord.py：`pip install discord.py`")
                elif "aiomysql" in item.lower():
                    report.append("- 安裝 aiomysql：`pip install aiomysql`")
                elif "dotenv" in item.lower():
                    report.append("- 安裝 python-dotenv：`pip install python-dotenv`")
                elif "配置" in item:
                    report.append("- 檢查 .env 文件配置")
                elif "資料庫" in item:
                    report.append("- 確保資料庫服務正在運行")
        
        if self.results['warnings']:
            report.append("### 警告項目處理建議：")
            for item in self.results['warnings']:
                if ".env" in item:
                    report.append("- 創建 .env 文件並配置必要的環境變數")
                elif "discord" in item.lower():
                    report.append("- 安裝 discord.py 以啟用完整功能")
        
        return "\n".join(report)

def main():
    """主函數"""
    print("🧪 第一階段修復快速測試")
    print("=" * 50)
    
    tester = QuickTester()
    success = tester.run_all_tests()
    
    # 生成報告
    report = tester.generate_report()
    
    # 保存報告到文件
    try:
        with open('test_report.md', 'w', encoding='utf-8') as f:
            f.write(report)
        print(f"\n📄 詳細報告已保存到：test_report.md")
    except Exception as e:
        print(f"⚠️ 無法保存報告：{e}")
    
    print("\n" + "=" * 50)
    if success:
        print("🎉 測試完成！可以嘗試啟動 Bot：python bot/main.py")
    else:
        print("⚠️ 測試未完全通過，請先修復失敗項目")
        print("💡 建議：")
        print("  1. 安裝缺失的依賴：pip install -r requirements.txt")
        print("  2. 檢查 .env 配置文件")
        print("  3. 確保所有修復文件都已正確應用")
    
    return success

if __name__ == "__main__":
    try:
        success = main()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n⏹️ 測試被中斷")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ 測試執行錯誤：{e}")
        traceback.print_exc()
        sys.exit(1)