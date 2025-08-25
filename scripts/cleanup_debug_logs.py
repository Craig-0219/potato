#!/usr/bin/env python3
"""
清理除錯代碼腳本
將 logger.debug 調用轉換為條件性日誌或移除
"""

import os
import re
import sys
from pathlib import Path
from typing import List, Tuple

# 添加專案根目錄到路徑
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

class DebugLogCleaner:
    """除錯日誌清理器"""
    
    def __init__(self, project_root: Path):
        self.project_root = project_root
        self.bot_dir = project_root / "bot"
        self.cleaned_files = []
        self.errors = []
        
        # 需要完全移除的 debug 模式
        self.remove_patterns = [
            r'logger\.debug\(f?"?\[.*?\].*?錯誤.*?"\)',  # 錯誤相關的 debug
            r'logger\.debug\(f?".*?錯誤.*?"\)',         # 一般錯誤 debug
            r'logger\.debug\(f?".*?失敗.*?"\)',         # 失敗相關 debug
        ]
        
        # 需要轉換為條件性 debug 的模式
        self.conditional_patterns = [
            r'logger\.debug\(f?"?\[.*?\].*?完成.*?"\)',  # 完成狀態
            r'logger\.debug\(f?"?\[.*?\].*?開始.*?"\)',  # 開始狀態
            r'logger\.debug\(f?".*?統計.*?"\)',         # 統計相關
            r'logger\.debug\(f?".*?清理.*?"\)',         # 清理相關
        ]
    
    def clean_file(self, file_path: Path) -> Tuple[int, int]:
        """清理單個文件"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            original_content = content
            removed_count = 0
            converted_count = 0
            
            # 移除特定模式的 debug 日誌
            for pattern in self.remove_patterns:
                matches = re.findall(pattern, content, re.MULTILINE | re.DOTALL)
                removed_count += len(matches)
                content = re.sub(pattern, '', content, flags=re.MULTILINE | re.DOTALL)
            
            # 轉換其他 debug 日誌為條件性日誌
            debug_pattern = r'(\s*)(logger\.debug\(.*?\))'
            matches = re.findall(debug_pattern, content, re.MULTILINE | re.DOTALL)
            
            for indent, debug_call in matches:
                # 檢查是否應該保留（重要的業務邏輯 debug）
                if self._should_convert_to_conditional(debug_call):
                    conditional_debug = f'{indent}if os.getenv("DEBUG_VERBOSE", "false").lower() == "true":\n{indent}    {debug_call}'
                    content = content.replace(f'{indent}{debug_call}', conditional_debug)
                    converted_count += 1
                else:
                    # 移除不重要的 debug 調用
                    content = content.replace(f'{indent}{debug_call}', '')
                    removed_count += 1
            
            # 清理多餘的空行
            content = re.sub(r'\n\s*\n\s*\n', '\n\n', content)
            
            # 只有內容有變化時才寫入
            if content != original_content:
                # 確保文件有導入 os 模組
                if 'if os.getenv("DEBUG_VERBOSE"' in content and 'import os' not in content:
                    # 在現有導入後添加 os 導入
                    import_match = re.search(r'(import.*?\n)', content)
                    if import_match:
                        content = content.replace(import_match.group(0), import_match.group(0) + 'import os\n')
                
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(content)
                
                self.cleaned_files.append(str(file_path))
                return removed_count, converted_count
            
            return 0, 0
            
        except Exception as e:
            self.errors.append(f"清理 {file_path} 時發生錯誤: {e}")
            return 0, 0
    
    def _should_convert_to_conditional(self, debug_call: str) -> bool:
        """判斷是否應該轉換為條件性 debug"""
        # 保留重要的業務邏輯 debug
        important_keywords = [
            '初始化', '啟動', '設置', '配置',
            '連接', '斷開', '重連',
            '創建', '刪除', '更新',
            '成功', '完成'
        ]
        
        return any(keyword in debug_call for keyword in important_keywords)
    
    def clean_project(self) -> dict:
        """清理整個專案"""
        total_removed = 0
        total_converted = 0
        files_processed = 0
        
        # 遍歷所有 Python 文件
        for py_file in self.bot_dir.rglob("*.py"):
            if self._should_process_file(py_file):
                removed, converted = self.clean_file(py_file)
                total_removed += removed
                total_converted += converted
                if removed > 0 or converted > 0:
                    files_processed += 1
                    print(f"✅ {py_file.relative_to(self.project_root)}: 移除 {removed}, 轉換 {converted}")
        
        return {
            'files_processed': files_processed,
            'total_removed': total_removed,
            'total_converted': total_converted,
            'cleaned_files': self.cleaned_files,
            'errors': self.errors
        }
    
    def _should_process_file(self, file_path: Path) -> bool:
        """判斷是否應該處理此文件"""
        # 跳過特定文件
        skip_files = {
            '__init__.py',
            'conftest.py'  # 測試配置文件
        }
        
        # 跳過測試文件
        if 'test' in str(file_path).lower():
            return False
            
        return file_path.name not in skip_files

def main():
    """主函數"""
    print("🧹 開始清理除錯代碼...")
    
    project_root = Path(__file__).parent.parent
    cleaner = DebugLogCleaner(project_root)
    
    result = cleaner.clean_project()
    
    print("\n📊 清理結果:")
    print(f"   處理文件數: {result['files_processed']}")
    print(f"   移除 debug 調用: {result['total_removed']}")
    print(f"   轉換為條件性 debug: {result['total_converted']}")
    
    if result['errors']:
        print(f"\n⚠️  發生 {len(result['errors'])} 個錯誤:")
        for error in result['errors']:
            print(f"   {error}")
    
    print(f"\n✅ 清理完成!")
    
    # 顯示環境變數提示
    print("\n💡 使用提示:")
    print("   開發環境啟用詳細 debug: export DEBUG_VERBOSE=true")
    print("   生產環境關閉詳細 debug: export DEBUG_VERBOSE=false")

if __name__ == "__main__":
    main()