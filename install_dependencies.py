#!/usr/bin/env python3
"""
依賴項自動安裝工具 - v2.2.0
自動安裝 Potato Bot v2.2.0 所需的所有依賴項
"""

import sys
import subprocess
import os
from typing import List, Dict

def run_command(command: List[str]) -> tuple[bool, str]:
    """執行命令並返回結果"""
    try:
        result = subprocess.run(
            command, 
            capture_output=True, 
            text=True, 
            check=True
        )
        return True, result.stdout
    except subprocess.CalledProcessError as e:
        return False, f"命令失敗: {e.stderr}"
    except Exception as e:
        return False, f"執行錯誤: {str(e)}"

def install_requirements():
    """安裝 requirements.txt 中的依賴項"""
    print("📦 正在安裝 requirements.txt 中的依賴項...")
    
    if not os.path.exists("requirements.txt"):
        print("❌ 找不到 requirements.txt 檔案")
        return False
    
    success, output = run_command([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"])
    
    if success:
        print("✅ requirements.txt 安裝完成")
        return True
    else:
        print(f"❌ requirements.txt 安裝失敗: {output}")
        return False

def install_individual_packages():
    """逐個安裝關鍵依賴項"""
    critical_packages = [
        "discord.py>=2.3.2",
        "Pillow>=9.0.0", 
        "aiohttp>=3.8.0",
        "aiomysql>=0.1.1",
        "python-dotenv>=1.0.0",
        "aioredis>=2.0.0"
    ]
    
    print("\n🔧 逐個安裝關鍵依賴項...")
    failed_packages = []
    
    for package in critical_packages:
        print(f"  安裝 {package}...")
        success, output = run_command([sys.executable, "-m", "pip", "install", package])
        
        if success:
            print(f"  ✅ {package} 安裝成功")
        else:
            print(f"  ❌ {package} 安裝失敗")
            failed_packages.append(package)
    
    return len(failed_packages) == 0, failed_packages

def install_optional_packages():
    """安裝可選依賴項"""
    optional_packages = [
        "yt-dlp>=2023.1.6",
        "PyNaCl>=1.5.0",
        "beautifulsoup4>=4.11.0", 
        "lxml>=4.9.0",
        "requests>=2.28.0"
    ]
    
    print("\n🌟 安裝可選依賴項（增強功能）:")
    
    for package in optional_packages:
        print(f"  安裝 {package}...")
        success, output = run_command([sys.executable, "-m", "pip", "install", package])
        
        if success:
            print(f"  ✅ {package} 安裝成功")
        else:
            print(f"  ⚠️ {package} 安裝失敗（可選功能，不影響核心功能）")

def upgrade_pip():
    """升級 pip"""
    print("🔄 升級 pip...")
    success, output = run_command([sys.executable, "-m", "pip", "install", "--upgrade", "pip"])
    
    if success:
        print("✅ pip 升級完成")
        return True
    else:
        print(f"⚠️ pip 升級失敗: {output}")
        return False

def main():
    """主函數"""
    print("🚀 Potato Bot v2.2.0 依賴項自動安裝")
    print("=" * 50)
    
    # 檢查 Python 版本
    if sys.version_info < (3, 8):
        print("❌ Python 版本必須 >= 3.8")
        print(f"   當前版本: {sys.version}")
        return False
    
    print(f"✅ Python 版本: {sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}")
    
    # 升級 pip
    upgrade_pip()
    
    # 嘗試安裝 requirements.txt
    requirements_success = install_requirements()
    
    if not requirements_success:
        print("\n🔄 requirements.txt 安裝失敗，嘗試逐個安裝...")
        individual_success, failed_packages = install_individual_packages()
        
        if not individual_success:
            print("\n❌ 以下關鍵依賴項安裝失敗:")
            for package in failed_packages:
                print(f"  - {package}")
            print("\n請檢查網路連接或手動安裝這些套件")
            return False
    
    # 安裝可選依賴項
    install_optional_packages()
    
    # 最終檢查
    print("\n" + "=" * 50)
    print("🔍 執行依賴項檢查...")
    
    try:
        # 嘗試導入關鍵模組
        test_imports = {
            'discord': 'Discord.py',
            'PIL': 'Pillow (圖片處理)',
            'aiohttp': 'aiohttp (HTTP請求)',
            'aiomysql': 'aiomysql (資料庫)',
            'dotenv': 'python-dotenv (環境變數)'
        }
        
        all_imported = True
        for module, description in test_imports.items():
            try:
                __import__(module)
                print(f"✅ {description}")
            except ImportError:
                print(f"❌ {description} - 安裝失敗或不可用")
                all_imported = False
        
        if all_imported:
            print("\n🎉 所有關鍵依賴項安裝成功！")
            print("✅ Potato Bot v2.2.0 已準備就緒")
            
            print("\n🚀 下一步:")
            print("1. 設定 .env 檔案 (參考 .env.example)")
            print("2. 執行 python bot/main.py 啟動機器人")
            print("3. 執行 python check_dependencies.py 進行完整檢查")
            
            return True
        else:
            print("\n❌ 部分關鍵依賴項安裝失敗")
            print("請檢查上述錯誤訊息並手動安裝缺失的套件")
            return False
            
    except Exception as e:
        print(f"\n❌ 依賴項檢查過程中發生錯誤: {e}")
        return False

if __name__ == "__main__":
    try:
        success = main()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n👋 安裝已取消")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ 安裝過程中發生錯誤: {e}")
        sys.exit(1)