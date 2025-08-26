#!/usr/bin/env python3
"""
環境檢查工具 - 託管環境診斷
"""
import os
import sys

def check_environment():
    print("🔍 環境檢查開始...")
    
    # 基本路徑資訊
    print(f"📁 當前工作目錄: {os.getcwd()}")
    print(f"📁 腳本所在目錄: {os.path.dirname(os.path.abspath(__file__))}")
    print(f"🐍 Python 版本: {sys.version}")
    print(f"🐍 Python 路徑: {sys.executable}")
    
    # Python 路徑
    print("\n📚 Python 模組搜索路徑:")
    for i, path in enumerate(sys.path):
        print(f"  {i}: {path}")
    
    # 檢查專案結構
    print("\n📦 專案結構檢查:")
    current_dir = os.getcwd()
    important_paths = [
        "bot",
        "shared", 
        "requirements.txt",
        "docs/requirements/requirements-production.txt"
    ]
    
    for path in important_paths:
        full_path = os.path.join(current_dir, path)
        exists = "✅" if os.path.exists(full_path) else "❌"
        print(f"  {exists} {path}")
    
    # 檢查關鍵模組
    print("\n🔧 關鍵模組檢查:")
    
    # 添加專案根目錄到路徑
    if current_dir not in sys.path:
        sys.path.insert(0, current_dir)
    
    modules_to_check = [
        ("shared.local_cache_manager", "本地快取管理"),
        ("shared.offline_mode", "離線模式"), 
        ("bot.services.local_api_server", "本地 API 伺服器"),
        ("aiofiles", "異步檔案處理"),
        ("jose.jwt", "JWT 處理"),
    ]
    
    # 特殊處理 shared.config（需要環境變數）
    print("  🔧 shared.config - 配置模組（需要環境變數）")
    
    # 檢查 .env 檔案
    env_path = os.path.join(current_dir, '.env')
    env_example_path = os.path.join(current_dir, '.env.example')
    
    if os.path.exists(env_path):
        print(f"  ✅ .env 檔案存在")
    elif os.path.exists(env_example_path):
        print(f"  ⚠️ 只有 .env.example，缺少 .env 檔案")
    else:
        print(f"  ❌ 缺少 .env 和 .env.example 檔案")
    
    for module_name, description in modules_to_check:
        try:
            __import__(module_name)
            print(f"  ✅ {module_name} - {description}")
        except ImportError as e:
            print(f"  ❌ {module_name} - {description} 錯誤: {e}")
    
    print("\n🎉 環境檢查完成")

if __name__ == "__main__":
    check_environment()