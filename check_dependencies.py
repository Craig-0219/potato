#!/usr/bin/env python3
"""
依賴項檢查工具 - v2.2.0
檢查所有新功能所需的依賴項是否正確安裝
"""

import sys
import subprocess
import importlib.util
from typing import Dict, List, Tuple

# v2.2.0 新功能所需的依賴項
REQUIRED_DEPENDENCIES = {
    # 核心依賴（必需）
    'core': {
        'discord': 'discord.py>=2.3.2',
        'aiomysql': 'aiomysql>=0.1.1', 
        'dotenv': 'python-dotenv>=1.0.0',
        'aioredis': 'aioredis>=2.0.0'
    },
    
    # v2.2.0 新功能依賴
    'v2.2.0': {
        'PIL': 'Pillow>=9.0.0',  # 圖片處理
        'aiohttp': 'aiohttp>=3.8.0',  # HTTP請求
        'requests': 'requests>=2.28.0',  # HTTP請求
        'aiofiles': 'aiofiles>=0.8.0'  # 異步文件操作
    },
    
    # 可選依賴（增強功能）
    'optional': {
        'yt_dlp': 'yt-dlp>=2023.1.6',  # YouTube下載
        'youtube_dl': 'youtube-dl>=2021.12.17',  # YouTube下載（備用）
        'PyNaCl': 'PyNaCl>=1.5.0',  # Discord語音
        'beautifulsoup4': 'beautifulsoup4>=4.11.0',  # HTML解析
        'lxml': 'lxml>=4.9.0'  # XML/HTML解析
    }
}

def check_dependency(module_name: str) -> Tuple[bool, str]:
    """檢查單個依賴項"""
    try:
        # 特殊處理一些模組名稱映射
        import_name = {
            'PIL': 'PIL',
            'youtube_dl': 'youtube_dl',
            'yt_dlp': 'yt_dlp',
            'PyNaCl': 'nacl',
            'beautifulsoup4': 'bs4'
        }.get(module_name, module_name)
        
        spec = importlib.util.find_spec(import_name)
        if spec is None:
            return False, f"模組未找到: {import_name}"
            
        # 嘗試導入
        module = importlib.import_module(import_name)
        
        # 獲取版本資訊（如果可用）
        version = "未知版本"
        if hasattr(module, '__version__'):
            version = module.__version__
        elif hasattr(module, 'version'):
            version = module.version
        elif hasattr(module, 'VERSION'):
            version = module.VERSION
            
        return True, f"✅ {module_name} ({version})"
        
    except ImportError as e:
        return False, f"❌ 導入失敗: {module_name} - {str(e)}"
    except Exception as e:
        return False, f"❌ 檢查錯誤: {module_name} - {str(e)}"

def generate_install_command(missing_deps: Dict[str, List[str]]) -> List[str]:
    """生成安裝命令"""
    commands = []
    
    # 收集所有缺失的套件
    all_missing = []
    for category, deps in missing_deps.items():
        if category != 'optional':  # 可選依賴不自動安裝
            for dep in deps:
                # 從依賴字典中找到正確的套件名稱
                for cat, dep_dict in REQUIRED_DEPENDENCIES.items():
                    if dep in dep_dict:
                        all_missing.append(dep_dict[dep])
                        break
    
    if all_missing:
        commands.append(f"pip install {' '.join(all_missing)}")
        
    return commands

def main():
    """主函數"""
    print("🔍 Potato Bot v2.2.0 依賴項檢查")
    print("=" * 50)
    
    all_ok = True
    missing_deps = {'core': [], 'v2.2.0': [], 'optional': []}
    
    # 檢查各類依賴項
    for category, deps in REQUIRED_DEPENDENCIES.items():
        print(f"\n📦 檢查 {category.upper()} 依賴項:")
        
        category_ok = True
        for module_name, package_spec in deps.items():
            is_available, message = check_dependency(module_name)
            print(f"  {message}")
            
            if not is_available:
                missing_deps[category].append(module_name)
                if category != 'optional':
                    category_ok = False
                    all_ok = False
        
        if category_ok:
            print(f"  ✅ {category.upper()} 依賴項檢查通過")
        elif category != 'optional':
            print(f"  ❌ {category.upper()} 依賴項有缺失")
    
    # 功能可用性報告
    print("\n" + "=" * 50)
    print("🎯 功能可用性報告:")
    
    features_status = {
        "🤖 AI智能助手": missing_deps['core'] == [] and 'aiohttp' not in missing_deps['v2.2.0'],
        "🎨 圖片處理工具": 'PIL' not in missing_deps['v2.2.0'],
        "🎵 音樂娛樂系統": 'aiohttp' not in missing_deps['v2.2.0'],
        "📊 內容分析工具": 'aiohttp' not in missing_deps['v2.2.0'] and 'requests' not in missing_deps['v2.2.0'],
        "🔄 跨平台經濟整合": missing_deps['core'] == []
    }
    
    for feature, available in features_status.items():
        status = "✅ 可用" if available else "❌ 不可用"
        print(f"  {feature}: {status}")
    
    # 生成修復建議
    if not all_ok:
        print("\n" + "=" * 50)
        print("🔧 修復建議:")
        
        install_commands = generate_install_command(missing_deps)
        if install_commands:
            print("\n執行以下命令安裝缺失的依賴項:")
            for cmd in install_commands:
                print(f"  {cmd}")
        
        if missing_deps['optional']:
            print(f"\n可選功能（增強體驗）:")
            for dep in missing_deps['optional']:
                package = REQUIRED_DEPENDENCIES['optional'][dep]
                print(f"  pip install {package}")
    
    # 總結
    print("\n" + "=" * 50)
    if all_ok:
        print("🎉 所有核心依賴項檢查通過！")
        print("✅ v2.2.0 新功能已準備就緒")
        
        if missing_deps['optional']:
            print(f"\n💡 提示: 有 {len(missing_deps['optional'])} 個可選依賴項未安裝")
            print("這些不會影響基本功能，但可以提供更好的使用體驗")
    else:
        print("❌ 發現缺失的核心依賴項")
        print("請安裝缺失的套件後重新啟動機器人")
        
        return False
        
    return True

if __name__ == "__main__":
    try:
        success = main()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n👋 檢查已取消")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ 檢查過程中發生錯誤: {e}")
        sys.exit(1)