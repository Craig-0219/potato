#!/usr/bin/env python3
"""
Slash Commands 測試腳本 - v2.2.0
檢查所有新增的 slash commands 定義是否正確
"""

import sys
import os
import re
import glob

# 添加路徑
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# 新增的 Cog 文件
COG_FILES = [
    "bot/cogs/ai_assistant_cog.py",
    "bot/cogs/image_tools_cog.py", 
    "bot/cogs/music_cog.py",
    "bot/cogs/content_analysis_cog.py",
    "bot/cogs/game_entertainment.py"
]

def extract_slash_commands(file_path: str) -> list:
    """從文件中提取 slash commands"""
    commands = []
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # 查找 @app_commands.command 裝飾器
        pattern = r'@app_commands\.command\(name="([^"]+)".*?description="([^"]+)".*?\)\s*async\s+def\s+(\w+)'
        matches = re.findall(pattern, content, re.DOTALL)
        
        for name, description, function_name in matches:
            commands.append({
                'name': name,
                'description': description,
                'function': function_name,
                'file': os.path.basename(file_path)
            })
            
    except Exception as e:
        print(f"❌ 讀取文件失敗 {file_path}: {e}")
        
    return commands

def check_command_conflicts(all_commands: list) -> list:
    """檢查指令名稱衝突"""
    name_count = {}
    conflicts = []
    
    for cmd in all_commands:
        name = cmd['name']
        if name in name_count:
            name_count[name].append(cmd)
        else:
            name_count[name] = [cmd]
    
    for name, cmds in name_count.items():
        if len(cmds) > 1:
            conflicts.append({
                'name': name,
                'commands': cmds
            })
    
    return conflicts

def validate_command_descriptions(commands: list) -> list:
    """驗證指令描述"""
    issues = []
    
    for cmd in commands:
        desc = cmd['description']
        
        # 檢查描述長度（Discord 限制 1-100 字符）
        if len(desc) > 100:
            issues.append({
                'command': cmd['name'],
                'issue': f'描述過長 ({len(desc)} 字符，限制 100)',
                'file': cmd['file']
            })
        elif len(desc) < 1:
            issues.append({
                'command': cmd['name'],
                'issue': '描述不能為空',
                'file': cmd['file']
            })
    
    return issues

def analyze_command_categories(commands: list) -> dict:
    """分析指令分類"""
    categories = {}
    
    for cmd in commands:
        file_name = cmd['file'].replace('_cog.py', '').replace('.py', '')
        category_name = {
            'ai_assistant': '🤖 AI智能助手',
            'image_tools': '🎨 圖片處理工具',
            'music': '🎵 音樂娛樂系統',
            'content_analysis': '📊 內容分析工具',
            'game_entertainment': '🎮 遊戲娛樂系統'
        }.get(file_name, file_name)
        
        if category_name not in categories:
            categories[category_name] = []
        categories[category_name].append(cmd)
    
    return categories

def main():
    """主函數"""
    print("🎯 Potato Bot v2.2.0 Slash Commands 分析")
    print("=" * 60)
    
    all_commands = []
    
    # 提取所有指令
    print("\n📋 提取 Slash Commands:")
    for cog_file in COG_FILES:
        if os.path.exists(cog_file):
            commands = extract_slash_commands(cog_file)
            all_commands.extend(commands)
            print(f"  ✅ {os.path.basename(cog_file)}: {len(commands)} 個指令")
        else:
            print(f"  ❌ 文件不存在: {cog_file}")
    
    print(f"\n📊 總計發現 {len(all_commands)} 個 Slash Commands")
    
    # 檢查指令衝突
    print("\n🔍 檢查指令名稱衝突:")
    conflicts = check_command_conflicts(all_commands)
    if conflicts:
        for conflict in conflicts:
            print(f"  ❌ 指令名稱衝突: '{conflict['name']}'")
            for cmd in conflict['commands']:
                print(f"    - {cmd['file']} :: {cmd['function']}")
    else:
        print("  ✅ 沒有發現指令名稱衝突")
    
    # 檢查描述問題
    print("\n📝 檢查指令描述:")
    desc_issues = validate_command_descriptions(all_commands)
    if desc_issues:
        for issue in desc_issues:
            print(f"  ❌ {issue['file']}: {issue['command']} - {issue['issue']}")
    else:
        print("  ✅ 所有指令描述都符合規範")
    
    # 按類別顯示指令
    print("\n🗂️ 指令分類總覽:")
    categories = analyze_command_categories(all_commands)
    
    for category, cmds in categories.items():
        print(f"\n  {category} ({len(cmds)} 個指令):")
        for cmd in sorted(cmds, key=lambda x: x['name']):
            print(f"    /{cmd['name']} - {cmd['description']}")
    
    # 生成指令清單
    print("\n" + "=" * 60)
    print("📋 v2.2.0 完整指令清單:")
    print("=" * 60)
    
    for category, cmds in categories.items():
        print(f"\n{category}:")
        for cmd in sorted(cmds, key=lambda x: x['name']):
            print(f"  /{cmd['name']} - {cmd['description']}")
    
    # 總結
    print("\n" + "=" * 60)
    if conflicts or desc_issues:
        print("⚠️ 發現問題，需要修復後才能正常使用")
        return False
    else:
        print("🎉 所有 Slash Commands 檢查通過！")
        print("✅ v2.2.0 指令系統已準備就緒")
        return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)