# CI/CD 問題記錄與解決方案

## 問題記錄格式
```
問題 #N - 日期: YYYY-MM-DD
標題: [簡短描述]
原因: [問題出現的根本原因]
解決方案: [具體修復步驟]
狀態: [待修復/已修復/驗證中]
影響範圍: [受影響的 workflows 或組件]
```

---

## 問題 #1 - 日期: 2025-08-28
**標題**: lightweight-ci.yml 中模組導入路徑錯誤

**原因**: 
- 開發過程中模組重構，`local_cache_manager.py` 重命名為 `cache_manager.py`
- 類別名稱從 `LocalCacheManager` 改為 `MultiLevelCacheManager`
- Workflow 文件未同步更新導入路徑

**錯誤**: 
```
ModuleNotFoundError: No module named 'shared.local_cache_manager'
ImportError: cannot import name 'LocalCacheManager' from 'shared.cache_manager'
```

**解決方案**:
1. 修復 `lightweight-ci.yml` 第 141 行: `shared.cache_manager.MultiLevelCacheManager`
2. 修復 `lightweight-ci.yml` 第 346 行: 整合測試中的相同導入
3. 更新錯誤訊息中的類別名稱

**狀態**: ✅ 已修復 (Commit: 31af8234)

**影響範圍**: 
- `.github/workflows/lightweight-ci.yml`
- 核心服務測試
- 整合功能測試

---

## 問題 #2 - 日期: 2025-08-28
**標題**: 引用不存在的測試文件 test_config_validation.py

**原因**: 
- GitHub Actions workflow 引用了不存在的測試文件
- 可能是開發過程中規劃的文件但未實際創建
- 或是文件被刪除但 workflow 引用未清理

**錯誤**:
```
python3: can't open file '/home/runner/work/potato/potato/test_config_validation.py': [Errno 2] No such file or directory
```

**影響範圍**:
- `.github/workflows/smart-auto-merge.yml` (第 207 行)
- `.github/workflows/deploy-to-production.yml` 

**解決方案**: 
1. ✅ 創建 `test_config_validation.py` 文件
2. ✅ 實現完整的配置驗證測試邏輯
3. ✅ 包含 5 個核心測試項目：
   - 基本模組導入測試
   - 配置載入測試 
   - 資料庫管理器初始化測試
   - 快取管理器初始化測試
   - 核心 Cogs 載入測試

**狀態**: ✅ 已修復

**修復驗證**:
```
🚀 開始配置驗證測試...
📊 測試結果總結:
  通過: 5
  失敗: 0
  總計: 5
🎉 所有配置驗證測試通過！
```

---

## 問題 #3 - 日期: 2025-08-28
**標題**: isort 導入排序格式錯誤

**原因**: 
- 新創建的 `test_config_validation.py` 文件導入順序不符合 isort 標準
- Python 標準庫導入未按字母順序排列
- 第三方庫導入未正確分組

**錯誤**:
```
ERROR: Imports are incorrectly sorted and/or formatted.
❌ 導入排序問題
```

**解決方案**:
1. ✅ 使用 `isort test_config_validation.py` 自動修復
2. ✅ 修正導入順序：
   - `import os` → `import sys` → `import traceback`
   - `from shared.config import DB_HOST, DISCORD_TOKEN` (按字母順序)
   - `from unittest.mock import MagicMock, patch` (按字母順序)
   - `from bot.cogs.language_core` → `from bot.cogs.ticket_core` → `from bot.cogs.vote_core`

**狀態**: ✅ 已修復

**影響範圍**: 
- `test_config_validation.py`
- GitHub Actions code-quality 檢查

**修復驗證**: 測試文件功能正常，5/5 測試通過

---

## 常見問題類別

### 1. 模組導入問題
- **原因**: 代碼重構後 workflow 未同步更新
- **預防**: 重構時同時檢查並更新所有 workflow 文件
- **檢測**: 使用本地測試模擬 CI 環境

### 2. 文件路徑問題  
- **原因**: 文件移動、重命名或刪除後引用未更新
- **預防**: 使用相對路徑，避免硬編碼路徑
- **檢測**: 定期檢查文件存在性

### 3. 環境變數配置
- **原因**: 測試環境與實際環境配置不一致
- **預防**: 統一環境變數命名和格式
- **檢測**: 配置驗證腳本

---

## 修復流程標準作業程序

### 1. 問題識別
- [ ] 記錄錯誤訊息
- [ ] 識別影響範圍
- [ ] 分析根本原因

### 2. 解決方案設計
- [ ] 評估多種修復方案
- [ ] 選擇最小影響的方案
- [ ] 考慮向後相容性

### 3. 修復實施
- [ ] 本地測試驗證
- [ ] 更新相關文檔
- [ ] 提交修復

### 4. 驗證
- [ ] GitHub Actions 執行成功
- [ ] 相關功能正常運作
- [ ] 回歸測試通過

---

## 預防措施

1. **代碼審查檢查清單**
   - 模組重構時檢查 workflow 文件
   - 文件路徑變更時檢查所有引用
   - 新增測試文件時更新相關 workflow

2. **自動化檢測**
   - Pre-commit hooks 檢查文件存在性
   - CI 流程包含路徑驗證
   - 定期掃描死鏈接

3. **文檔維護**
   - 保持 workflow 文件與代碼同步
   - 記錄重大變更和影響
   - 維護依賴關係圖

---

*最後更新: 2025-08-28*
*維護者: Claude Code Assistant*