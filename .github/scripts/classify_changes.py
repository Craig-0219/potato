#!/usr/bin/env python3
"""
智能變更分類腳本
分析 Git 變更並決定 CI/CD 執行策略
"""

import os
import re
import sys


def classify_changes():
    """智能變更分類和影響分析"""
    
    changed_files = os.environ.get('CHANGED_FILES', '').strip().split('\n')
    changed_files = [f for f in changed_files if f.strip()]
    
    if not changed_files:
        return {
            'change_type': 'none',
            'impact_level': 'none',
            'test_strategy': 'skip',
            'cache_strategy': 'standard',
            'skip_workflows': 'all'
        }
    
    # 文件分類規則
    categories = {
        'critical': [
            r'^bot/main\.py$',
            r'^shared/config\.py$', 
            r'^requirements.*\.txt$',
            r'^\.github/workflows/.*\.yml$'
        ],
        'core_logic': [
            r'^bot/cogs/.*\.py$',
            r'^bot/services/.*\.py$',
            r'^bot/db/.*\.py$',
            r'^shared/.*\.py$'
        ],
        'api': [
            r'^bot/api/.*\.py$',
            r'^bot/views/.*\.py$'
        ],
        'tests': [
            r'^tests/.*\.py$'
        ],
        'docs': [
            r'.*\.md$',
            r'^docs/.*',
            r'README.*',
            r'CHANGELOG.*'
        ],
        'config': [
            r'^\..*rc$',
            r'^\..*\.yaml$',
            r'^\..*\.yml$',
            r'^pyproject\.toml$',
            r'^pytest\.ini$'
        ],
        'scripts': [
            r'^scripts/.*\.py$',
            r'^scripts/.*\.sh$'
        ]
    }
    
    # 分析每個文件
    file_categories = {}
    for file_path in changed_files:
        file_categories[file_path] = []
        for category, patterns in categories.items():
            for pattern in patterns:
                if re.match(pattern, file_path):
                    file_categories[file_path].append(category)
                    break
        
        # 如果沒有匹配任何類別，歸類為 other
        if not file_categories[file_path]:
            file_categories[file_path] = ['other']
    
    # 統計各類別文件數量
    category_counts = {}
    for categories_list in file_categories.values():
        for cat in categories_list:
            category_counts[cat] = category_counts.get(cat, 0) + 1
    
    print(f"📊 變更文件分類統計:")
    for cat, count in category_counts.items():
        print(f"  • {cat}: {count} 個文件")
    
    # 決定變更類型和影響等級
    change_type = 'minor'
    impact_level = 'low'
    
    if category_counts.get('critical', 0) > 0:
        change_type = 'critical'
        impact_level = 'high'
    elif category_counts.get('core_logic', 0) > 0:
        change_type = 'code'
        impact_level = 'medium'
    elif category_counts.get('api', 0) > 0:
        change_type = 'api'
        impact_level = 'medium'
    elif category_counts.get('tests', 0) > 0:
        change_type = 'test'
        impact_level = 'low'
    elif category_counts.get('docs', 0) > 0 and len(category_counts) == 1:
        change_type = 'docs'
        impact_level = 'none'
    elif category_counts.get('config', 0) > 0:
        change_type = 'config'
        impact_level = 'medium'
    
    # 決定測試策略
    test_strategies = {
        'critical': 'full',      # 完整測試套件
        'code': 'targeted',      # 針對性測試
        'api': 'api_focused',    # API 重點測試
        'test': 'test_only',     # 僅執行新的測試
        'docs': 'skip',          # 跳過測試
        'config': 'basic',       # 基礎測試
        'minor': 'quick'         # 快速測試
    }
    
    test_strategy = test_strategies.get(change_type, 'quick')
    
    # 決定快取策略
    cache_strategies = {
        'critical': 'refresh',   # 刷新所有快取
        'code': 'selective',     # 選擇性快取
        'api': 'selective',      # 選擇性快取
        'docs': 'preserve',      # 保留所有快取
        'config': 'refresh',     # 刷新配置快取
        'minor': 'standard'      # 標準快取
    }
    
    cache_strategy = cache_strategies.get(change_type, 'standard')
    
    # 決定可跳過的 workflows
    skip_workflows_map = {
        'docs': 'tests,security,quality',  # 文檔變更可跳過大部分檢查
        'test': 'security',                 # 測試變更可跳過安全掃描  
        'minor': 'none',                    # 小變更不跳過任何檢查
        'critical': 'none'                  # 關鍵變更不跳過任何檢查
    }
    
    skip_workflows = skip_workflows_map.get(change_type, 'none')
    
    result = {
        'change_type': change_type,
        'impact_level': impact_level,
        'test_strategy': test_strategy,
        'cache_strategy': cache_strategy,
        'skip_workflows': skip_workflows
    }
    
    print(f"\n🎯 智能分析結果:")
    print(f"  • 變更類型: {change_type}")
    print(f"  • 影響等級: {impact_level}")
    print(f"  • 測試策略: {test_strategy}")
    print(f"  • 快取策略: {cache_strategy}")
    print(f"  • 可跳過檢查: {skip_workflows}")
    
    return result


def main():
    """主執行函數"""
    try:
        result = classify_changes()
        
        # 輸出到 GitHub Actions
        github_output = os.environ.get('GITHUB_OUTPUT')
        if github_output:
            with open(github_output, 'a') as f:
                for key, value in result.items():
                    f.write(f"{key}={value}\n")
        else:
            # 如果沒有 GITHUB_OUTPUT，直接輸出
            for key, value in result.items():
                print(f"{key}={value}")
                
    except Exception as e:
        print(f"❌ 分析過程發生錯誤: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()