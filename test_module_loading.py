#!/usr/bin/env python3
"""
模組載入測試腳本 - v2.2.0
測試所有新增的 Cogs 是否能夠正確載入
"""

import sys
import os
import asyncio
import importlib.util

# 添加路徑
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# 新增的模組列表
NEW_MODULES = [
    "bot.cogs.ai_assistant_core",
    "bot.cogs.image_tools_core", 
    "bot.cogs.music_core",
    "bot.cogs.content_analysis_core",
    "bot.cogs.game_core"
]

# 相關服務模組
SERVICE_MODULES = [
    "bot.services.ai_assistant",
    "bot.services.image_processor",
    "bot.services.music_player",
    "bot.services.content_analyzer", 
    "bot.services.cross_platform_economy"
]

def test_module_import(module_name: str) -> tuple[bool, str]:
    """測試模組導入"""
    try:
        spec = importlib.util.find_spec(module_name)
        if spec is None:
            return False, f"模組規範未找到: {module_name}"
        
        # 嘗試導入
        module = importlib.import_module(module_name)
        
        # 檢查是否有 setup 函數（針對 Cogs）
        if module_name.startswith("bot.cogs"):
            if hasattr(module, 'setup'):
                return True, f"✅ 模組載入成功 (含setup函數): {module_name}"
            else:
                return False, f"❌ 缺少setup函數: {module_name}"
        else:
            return True, f"✅ 服務模組載入成功: {module_name}"
            
    except ImportError as e:
        return False, f"❌ 導入錯誤: {module_name} - {str(e)}"
    except Exception as e:
        return False, f"❌ 未知錯誤: {module_name} - {str(e)}"

def test_shared_dependencies():
    """測試共享依賴"""
    shared_modules = [
        "shared.config",
        "shared.logger", 
        "shared.cache_manager",
        "shared.prometheus_metrics"
    ]
    
    results = []
    for module in shared_modules:
        success, message = test_module_import(module)
        results.append((success, message))
    
    return results

def main():
    """主函數"""
    print("🧪 Potato Bot v2.2.0 模組載入測試")
    print("=" * 50)
    
    all_success = True
    
    # 測試共享依賴
    print("\n📦 測試共享依賴模組:")
    shared_results = test_shared_dependencies()
    for success, message in shared_results:
        print(f"  {message}")
        if not success:
            all_success = False
    
    # 測試服務模組
    print("\n🔧 測試服務模組:")
    for module in SERVICE_MODULES:
        success, message = test_module_import(module)
        print(f"  {message}")
        if not success:
            all_success = False
    
    # 測試 Cog 模組
    print("\n🎮 測試 Cog 模組:")
    for module in NEW_MODULES:
        success, message = test_module_import(module)
        print(f"  {message}")
        if not success:
            all_success = False
    
    # 總結
    print("\n" + "=" * 50)
    if all_success:
        print("🎉 所有模組載入測試通過！")
        print("✅ v2.2.0 新功能模組已準備就緒")
    else:
        print("❌ 部分模組載入失敗")
        print("請檢查依賴項和模組路徑")
    
    print("\n💡 提示:")
    print("- 如果看到 Discord 相關錯誤，這是正常的（測試環境沒有 discord.py）")
    print("- 重點關注模組結構和語法錯誤")
    print("- 在實際運行環境中需要安裝完整的 requirements.txt")

if __name__ == "__main__":
    main()