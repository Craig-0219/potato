#!/usr/bin/env python3
"""
Discord Bot 健康檢查腳本
用於 CI/CD 流程中驗證 Bot 的完整性和功能性
"""

import asyncio
import importlib.util
import json
import os
import sys
import traceback
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Tuple
from unittest.mock import MagicMock, patch

# 添加項目路徑
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "bot"))


class BotHealthChecker:
    """Discord Bot 健康檢查器"""

    def __init__(self):
        self.results = {
            "timestamp": datetime.utcnow().isoformat(),
            "overall_status": "unknown",
            "tests": {},
            "cogs_status": {},
            "errors": [],
            "warnings": [],
        }

    async def run_all_tests(self) -> bool:
        """執行所有健康檢查測試"""
        print("🔍 開始 Discord Bot 健康檢查...")

        tests = [
            ("基礎導入測試", self.test_basic_imports),
            ("核心模組測試", self.test_core_modules),
            ("Cogs 載入測試", self.test_cogs_loading),
            ("資料庫模組測試", self.test_database_modules),
            ("服務模組測試", self.test_service_modules),
            ("配置檔案測試", self.test_config_files),
            ("Bot 初始化測試", self.test_bot_initialization),
            ("完整性驗證", self.test_integrity_check),
        ]

        all_passed = True

        for test_name, test_func in tests:
            try:
                print(f"\n📋 執行 {test_name}...")
                success = await test_func()
                self.results["tests"][test_name] = {
                    "status": "passed" if success else "failed",
                    "timestamp": datetime.utcnow().isoformat(),
                }

                if success:
                    print(f"✅ {test_name} 通過")
                else:
                    print(f"❌ {test_name} 失敗")
                    all_passed = False

            except Exception as e:
                print(f"💥 {test_name} 發生異常: {e}")
                self.results["tests"][test_name] = {
                    "status": "error",
                    "error": str(e),
                    "timestamp": datetime.utcnow().isoformat(),
                }
                self.results["errors"].append(f"{test_name}: {e}")
                all_passed = False

        self.results["overall_status"] = "passed" if all_passed else "failed"
        return all_passed

    async def test_basic_imports(self) -> bool:
        """測試基本導入"""
        try:
            import asyncio

            import aiohttp
            import asyncpg
            import discord

            print("✅ Discord.py 和基礎依賴導入成功")
            return True
        except ImportError as e:
            print(f"❌ 基礎依賴導入失敗: {e}")
            return False

    async def test_core_modules(self) -> bool:
        """測試核心模組"""
        try:
            # 測試配置模組
            from shared.config import Config

            config = Config()
            print("✅ 配置模組載入成功")

            # 測試日誌模組
            from shared.logger import setup_logger

            logger = setup_logger("test")
            print("✅ 日誌模組載入成功")

            # 測試快取管理器
            from shared.cache_manager import MultiLevelCacheManager

            print("✅ 快取管理器載入成功")

            return True
        except Exception as e:
            print(f"❌ 核心模組測試失敗: {e}")
            return False

    async def test_cogs_loading(self) -> bool:
        """測試所有 Cogs 載入"""
        cogs_dir = PROJECT_ROOT / "bot" / "cogs"
        if not cogs_dir.exists():
            print("❌ Cogs 目錄不存在")
            return False

        cog_files = [f for f in cogs_dir.glob("*.py") if not f.name.startswith("__")]
        total_cogs = len(cog_files)
        loaded_cogs = 0
        failed_cogs = []

        print(f"🔍 發現 {total_cogs} 個 Cog 文件")

        for cog_file in cog_files:
            cog_name = cog_file.stem
            try:
                # 嘗試導入 Cog 模組
                spec = importlib.util.spec_from_file_location(cog_name, cog_file)
                module = importlib.util.module_from_spec(spec)

                # 模擬必要的依賴
                with patch("discord.Bot"), patch("discord.Intents"):
                    spec.loader.exec_module(module)

                self.results["cogs_status"][cog_name] = "loaded"
                loaded_cogs += 1
                print(f"  ✅ {cog_name}")

            except Exception as e:
                self.results["cogs_status"][cog_name] = f"failed: {str(e)}"
                failed_cogs.append(cog_name)
                print(f"  ❌ {cog_name}: {e}")

        success_rate = (loaded_cogs / total_cogs) * 100
        print(f"📊 Cogs 載入統計: {loaded_cogs}/{total_cogs} ({success_rate:.1f}%)")

        if failed_cogs:
            self.results["warnings"].append(f"Failed cogs: {', '.join(failed_cogs)}")

        # 要求至少 90% 的 Cogs 能夠載入
        return success_rate >= 90.0

    async def test_database_modules(self) -> bool:
        """測試資料庫相關模組"""
        try:
            from bot.db.database_manager import DatabaseManager

            print("✅ DatabaseManager 導入成功")

            from bot.db.base_dao import BaseDAO

            print("✅ BaseDAO 導入成功")

            # 測試一些關鍵 DAO
            dao_modules = [
                "bot.db.ticket_dao",
                "bot.db.vote_dao",
                "bot.db.welcome_dao",
                "bot.db.ai_dao",
            ]

            for dao_module in dao_modules:
                try:
                    importlib.import_module(dao_module)
                    print(f"✅ {dao_module} 導入成功")
                except ImportError as e:
                    print(f"⚠️ {dao_module} 導入失敗: {e}")
                    self.results["warnings"].append(f"DAO import failed: {dao_module}")

            return True
        except Exception as e:
            print(f"❌ 資料庫模組測試失敗: {e}")
            return False

    async def test_service_modules(self) -> bool:
        """測試服務層模組"""
        try:
            service_modules = [
                "bot.services.ticket_manager",
                "bot.services.vote_template_manager",
                "bot.services.welcome_manager",
                "bot.services.ai_manager",
                "bot.services.economy_manager",
            ]

            loaded_services = 0

            for service_module in service_modules:
                try:
                    importlib.import_module(service_module)
                    loaded_services += 1
                    print(f"✅ {service_module} 導入成功")
                except ImportError as e:
                    print(f"⚠️ {service_module} 導入失敗: {e}")
                    self.results["warnings"].append(f"Service import failed: {service_module}")

            # 要求至少 80% 的服務模組能載入
            success_rate = (loaded_services / len(service_modules)) * 100
            return success_rate >= 80.0

        except Exception as e:
            print(f"❌ 服務模組測試失敗: {e}")
            return False

    async def test_config_files(self) -> bool:
        """測試配置文件"""
        try:
            # 檢查必要文件
            required_files = [
                PROJECT_ROOT / "bot" / "main.py",
                PROJECT_ROOT / "requirements.txt",
                PROJECT_ROOT / "shared" / "config.py",
            ]

            for file_path in required_files:
                if not file_path.exists():
                    print(f"❌ 缺少必要文件: {file_path}")
                    return False
                print(f"✅ {file_path.name} 存在")

            # 檢查啟動器
            startup_files = [
                PROJECT_ROOT / "start.py",
                PROJECT_ROOT / "start.sh",
                PROJECT_ROOT / "start.bat",
            ]

            startup_exists = any(f.exists() for f in startup_files)
            if not startup_exists:
                print("⚠️ 沒有找到啟動器文件")
                self.results["warnings"].append("No startup scripts found")
            else:
                print("✅ 啟動器文件存在")

            return True
        except Exception as e:
            print(f"❌ 配置文件測試失敗: {e}")
            return False

    async def test_bot_initialization(self) -> bool:
        """測試 Bot 初始化流程"""
        try:
            # 創建模擬環境
            mock_env = {
                "DISCORD_TOKEN": "test_token",
                "DATABASE_URL": "postgresql://test:test@localhost/test",
                "REDIS_URL": "redis://localhost:6379/0",
                "ENVIRONMENT": "test",
            }

            with patch.dict(os.environ, mock_env):
                with patch("discord.Bot") as mock_bot_class:
                    with patch("discord.Intents"):
                        mock_bot = MagicMock()
                        mock_bot.user.id = 123456789
                        mock_bot_class.return_value = mock_bot

                        # 嘗試導入主模組
                        from bot.main import create_bot

                        # 測試 Bot 創建
                        bot = create_bot()
                        print("✅ Bot 創建成功")

                        return True
        except Exception as e:
            print(f"❌ Bot 初始化測試失敗: {e}")
            return False

    async def test_integrity_check(self) -> bool:
        """完整性檢查"""
        try:
            # 檢查關鍵目錄結構
            required_dirs = [
                PROJECT_ROOT / "bot",
                PROJECT_ROOT / "bot" / "cogs",
                PROJECT_ROOT / "bot" / "services",
                PROJECT_ROOT / "bot" / "db",
                PROJECT_ROOT / "shared",
            ]

            for dir_path in required_dirs:
                if not dir_path.exists():
                    print(f"❌ 缺少必要目錄: {dir_path}")
                    return False
                print(f"✅ 目錄存在: {dir_path.name}")

            # 檢查 Python 語法
            python_files = list(PROJECT_ROOT.rglob("*.py"))
            python_files = [
                f for f in python_files if "venv" not in str(f) and "__pycache__" not in str(f)
            ]

            syntax_errors = 0
            for py_file in python_files[:50]:  # 限制檢查數量以節省時間
                try:
                    with open(py_file, "r", encoding="utf-8") as f:
                        compile(f.read(), py_file, "exec")
                except SyntaxError as e:
                    print(f"❌ 語法錯誤 {py_file}: {e}")
                    syntax_errors += 1

            if syntax_errors > 0:
                print(f"❌ 發現 {syntax_errors} 個語法錯誤")
                return False

            print(f"✅ {len(python_files[:50])} 個 Python 文件語法檢查通過")
            return True

        except Exception as e:
            print(f"❌ 完整性檢查失敗: {e}")
            return False

    def generate_report(self) -> Dict[str, Any]:
        """生成健康檢查報告"""
        total_tests = len(self.results["tests"])
        passed_tests = sum(
            1 for test in self.results["tests"].values() if test["status"] == "passed"
        )

        summary = {
            "total_tests": total_tests,
            "passed_tests": passed_tests,
            "success_rate": (passed_tests / total_tests * 100) if total_tests > 0 else 0,
            "total_cogs": len(self.results["cogs_status"]),
            "loaded_cogs": sum(
                1 for status in self.results["cogs_status"].values() if status == "loaded"
            ),
            "errors": len(self.results["errors"]),
            "warnings": len(self.results["warnings"]),
        }

        self.results["summary"] = summary
        return self.results

    def print_summary(self):
        """列印檢查摘要"""
        print("\n" + "=" * 60)
        print("📊 Discord Bot 健康檢查摘要")
        print("=" * 60)

        summary = self.results["summary"]

        print(f"🎯 總體狀態: {self.results['overall_status'].upper()}")
        print(
            f"📋 測試結果: {summary['passed_tests']}/{summary['total_tests']} ({summary['success_rate']:.1f}%)"
        )
        print(f"📦 Cogs 狀態: {summary['loaded_cogs']}/{summary['total_cogs']} 載入成功")

        if summary["errors"] > 0:
            print(f"❌ 錯誤數: {summary['errors']}")

        if summary["warnings"] > 0:
            print(f"⚠️ 警告數: {summary['warnings']}")

        print(f"⏰ 檢查時間: {self.results['timestamp']}")
        print("=" * 60)


async def main():
    """主執行函數"""
    checker = BotHealthChecker()

    try:
        # 執行所有測試
        success = await checker.run_all_tests()

        # 生成報告
        report = checker.generate_report()

        # 列印摘要
        checker.print_summary()

        # 保存報告到文件 (如果需要)
        if os.getenv("SAVE_REPORT", "false").lower() == "true":
            with open("bot_health_report.json", "w") as f:
                json.dump(report, f, indent=2)
            print("📄 健康檢查報告已保存到 bot_health_report.json")

        # 退出碼
        exit_code = 0 if success else 1
        print(f"\n🏁 健康檢查完成，退出碼: {exit_code}")
        sys.exit(exit_code)

    except Exception as e:
        print(f"💥 健康檢查執行失敗: {e}")
        traceback.print_exc()
        sys.exit(2)


if __name__ == "__main__":
    asyncio.run(main())
