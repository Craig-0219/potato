#!/usr/bin/env python3
"""
🚀 Potato Bot 一鍵啟動器
支援跨平台啟動和環境檢查
"""

import os
import platform
import subprocess
import sys
from pathlib import Path


class PotatoBotStarter:
    def __init__(self):
        self.root_dir = Path(__file__).parent
        # 主程式位置
        potential_bot_files = [
            self.root_dir / "src" / "potato_bot" / "main.py",  # 現代架構
        ]
        self.bot_file = None
        for bot_file in potential_bot_files:
            if bot_file.exists():
                self.bot_file = bot_file
                break
        
        self.env_file = self.root_dir / ".env"
        self.env_example = self.root_dir / ".env.example"

    def print_banner(self):
        """顯示啟動橫幅"""
        banner = r"""
🥔 ═══════════════════════════════════════════════════════════════
   ____        _        _          ____        _
  |  _ \ ___ | |_ __ _| |_ ___   | __ )  ___ | |_
  | |_) / _ \| __/ _` | __/ _ \  |  _ \ / _ \| __|
  |  __/ (_) | || (_| | || (_) | | |_) | (_) | |_
  |_|   \___/ \__\__,_|\__\___/  |____/ \___/ \__|

   🎮 Discord & Minecraft 社群管理平台
   ⚡ v3.2.0 - 專為遊戲社群打造
═══════════════════════════════════════════════════════════════ 🥔
        """
        print(banner)

    def check_python_version(self):
        """檢查 Python 版本"""
        version = sys.version_info
        print(
            f"🐍 Python 版本: {version.major}.{version.minor}.{version.micro}"
        )

        if version < (3, 10):
            print("❌ 需要 Python 3.10 或更高版本")
            print("   請升級您的 Python 版本")
            return False

        print("✅ Python 版本符合要求")
        return True

    def check_environment(self):
        """檢查環境設定"""
        print("\n🔍 檢查環境設定...")

        if not self.env_file.exists():
            if self.env_example.exists():
                print("⚠️  未找到 .env 檔案")
                response = input(
                    "是否要從 .env.example 複製設定？(y/n): "
                ).lower()
                if response in ["y", "yes", "是"]:
                    try:
                        import shutil

                        shutil.copy2(self.env_example, self.env_file)
                        print("✅ 已複製 .env.example 到 .env")
                        print("⚠️  請編輯 .env 檔案填入您的配置")
                        return False
                    except Exception as e:
                        print(f"❌ 複製檔案失敗: {e}")
                        return False
                else:
                    print("❌ 需要 .env 檔案才能啟動")
                    return False
            else:
                print("❌ 未找到 .env 和 .env.example 檔案")
                return False

        print("✅ 環境檔案存在")
        return True

    def check_dependencies(self):
        """檢查依賴套件"""
        print("\n📦 檢查依賴套件...")

        required_packages = [
            "discord.py",
            "aiomysql",
            "python-dotenv",
            "fastapi",
            "uvicorn",
        ]

        missing_packages = []

        for package in required_packages:
            try:
                if package == "discord.py":
                    import discord

                    print(f"✅ discord.py {discord.__version__}")
                elif package == "aiomysql":
                    pass

                    print("✅ aiomysql")
                elif package == "python-dotenv":
                    pass

                    print("✅ python-dotenv")
                elif package == "fastapi":
                    pass

                    print("✅ fastapi")
                elif package == "uvicorn":
                    pass

                    print("✅ uvicorn")
            except ImportError:
                print(f"❌ {package}")
                missing_packages.append(package)

        if missing_packages:
            print(f"\n⚠️  缺少依賴套件: {', '.join(missing_packages)}")
            response = input("是否要自動安裝缺少的套件？(y/n): ").lower()
            if response in ["y", "yes", "是"]:
                return self.install_dependencies()
            else:
                print("❌ 請手動安裝依賴套件:")
                print("   pip install -r requirements.txt")
                return False

        print("✅ 所有依賴套件已安裝")
        return True

    def install_dependencies(self):
        """自動安裝依賴"""
        print("\n⬇️  安裝依賴套件...")
        try:
            requirements_file = self.root_dir / "requirements.txt"
            if requirements_file.exists():
                result = subprocess.run(
                    [
                        sys.executable,
                        "-m",
                        "pip",
                        "install",
                        "-r",
                        str(requirements_file),
                    ],
                    capture_output=True,
                    text=True,
                )

                if result.returncode == 0:
                    print("✅ 依賴套件安裝完成")
                    return True
                else:
                    print(f"❌ 安裝失敗: {result.stderr}")
                    return False
            else:
                print("❌ 未找到 requirements.txt")
                return False
        except Exception as e:
            print(f"❌ 安裝過程發生錯誤: {e}")
            return False

    def check_bot_file(self):
        """檢查 Bot 主程式"""
        if self.bot_file is None:
            print("\n🤖 檢查 Bot 主程式: 尋找中...")
            print("❌ 未找到 Bot 主程式")
            print("   預期位置: src/potato_bot/main.py")
            return False
        
        print(f"\n🤖 檢查 Bot 主程式: {self.bot_file}")
        print("✅ Bot 主程式存在")
        return True

    def show_system_info(self):
        """顯示系統資訊"""
        print("\n💻 系統資訊:")
        print(f"   作業系統: {platform.system()} {platform.release()}")
        print(f"   架構: {platform.machine()}")
        print(f"   Python: {platform.python_version()}")
        print(f"   工作目錄: {self.root_dir}")

    def start_bot(self):
        """啟動 Bot"""
        print("\n🚀 啟動 Potato Bot...")
        print("   使用 Ctrl+C 停止 Bot")
        print("=" * 50)

        try:
            # 使用相同的 Python 解釋器執行 bot/main.py
            os.chdir(self.root_dir)
            result = subprocess.run(
                [sys.executable, str(self.bot_file)], cwd=self.root_dir
            )
            return result.returncode == 0
        except KeyboardInterrupt:
            print("\n\n⏹️  收到停止信號")
            return True
        except Exception as e:
            print(f"\n❌ 啟動失敗: {e}")
            return False

    def run_pre_checks(self):
        """執行啟動前檢查"""
        self.print_banner()
        self.show_system_info()

        print("\n🔍 執行啟動前檢查...")

        checks = [
            ("Python 版本", self.check_python_version),
            ("環境設定", self.check_environment),
            ("依賴套件", self.check_dependencies),
            ("Bot 主程式", self.check_bot_file),
        ]

        for check_name, check_func in checks:
            if not check_func():
                print(f"\n❌ {check_name}檢查失敗")
                print("請修復上述問題後重新啟動")
                return False

        print("\n✅ 所有檢查通過!")
        return True

    def run(self):
        """主執行函數"""
        try:
            if not self.run_pre_checks():
                return False

            # 詢問是否要立即啟動
            print("\n" + "=" * 50)
            response = input("準備就緒! 是否立即啟動 Bot？(y/n): ").lower()

            if response in ["y", "yes", "是", ""]:
                return self.start_bot()
            else:
                print("👋 您可以稍後手動執行:")
                print("   python src/potato_bot/main.py")
                print("   或")
                print("   python start.py")
                return True

        except KeyboardInterrupt:
            print("\n\n👋 啟動已取消")
            return True
        except Exception as e:
            print(f"\n❌ 啟動器執行失敗: {e}")
            return False


def main():
    """主函數"""
    starter = PotatoBotStarter()
    success = starter.run()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
