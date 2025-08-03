import importlib
import sys
from typing import List, Dict, Any

def check_required_imports() -> Dict[str, Any]:
    """檢查所有必要的導入是否可用"""
    required_modules = {
        'discord': 'discord.py',
        'aiomysql': 'aiomysql', 
        'dotenv': 'python-dotenv',
        'asyncio': 'built-in',
        'logging': 'built-in',
        'datetime': 'built-in',
        'typing': 'built-in',
        'json': 'built-in',
        'os': 'built-in',
        'sys': 'built-in'
    }
    
    results = {
        'missing_modules': [],
        'available_modules': [],
        'import_errors': []
    }
    
    for module_name, source in required_modules.items():
        try:
            importlib.import_module(module_name)
            results['available_modules'].append(f"{module_name} ({source})")
        except ImportError as e:
            results['missing_modules'].append(f"{module_name} ({source})")
            results['import_errors'].append(str(e))
    
    return results

def check_custom_imports() -> Dict[str, Any]:
    """檢查自定義模組的導入"""
    custom_modules = [
        'shared.config',
        'shared.logger', 
        'bot.utils.ticket_constants',
        'bot.utils.error_handler',
        'bot.db.pool',
        'bot.views.ticket_views',
        'bot.views.vote_views'
    ]
    
    results = {
        'working_imports': [],
        'failed_imports': [],
        'import_errors': []
    }
    
    for module_name in custom_modules:
        try:
            importlib.import_module(module_name)
            results['working_imports'].append(module_name)
        except ImportError as e:
            results['failed_imports'].append(module_name)
            results['import_errors'].append(f"{module_name}: {str(e)}")
    
    return results

def run_import_check():
    """運行完整的導入檢查"""
    print("🔍 檢查必要模組導入...")
    required_check = check_required_imports()
    
    if required_check['missing_modules']:
        print("❌ 缺少必要模組：")
        for module in required_check['missing_modules']:
            print(f"  - {module}")
        print("\n請安裝缺少的模組：")
        print("pip install discord.py aiomysql python-dotenv")
        return False
    else:
        print("✅ 所有必要模組都已安裝")
    
    print("\n🔍 檢查自定義模組導入...")
    custom_check = check_custom_imports()
    
    if custom_check['failed_imports']:
        print("❌ 自定義模組導入失敗：")
        for error in custom_check['import_errors']:
            print(f"  - {error}")
        return False
    else:
        print("✅ 所有自定義模組導入成功")
    
    return True

if __name__ == "__main__":
    success = run_import_check()
    sys.exit(0 if success else 1)