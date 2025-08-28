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

## 問題 #9 - 日期: 2025-08-28
**標題**: 代碼品質問題 - bot/api/app.py undefined names

**原因**: 
- `bot/api/app.py` 中使用了 Hypercorn 的 `Config` 和 `serve` 但缺少導入
- 生產環境實際使用 `uvicorn` 而不是 `hypercorn`

**解決方案**: 
1. 添加 `import uvicorn` 導入
2. 將 Hypercorn 配置改為 uvicorn 配置：
   ```python
   # 修改前 (Hypercorn)
   config = Config()
   server = serve(app, config)
   
   # 修改後 (uvicorn)  
   config = uvicorn.Config(app, host=host, port=port, log_level="info", access_log=True)
   server = uvicorn.Server(config)
   ```

**驗證**: 
```bash
python3 -m flake8 bot/api/app.py --select=F821  # 無 undefined name 錯誤
```

**狀態**: 已修復 ✅

**影響範圍**: 
- bot/api/app.py 的 API 服務器啟動功能
- F821 flake8 檢查通過

---

## 問題 #10 - 日期: 2025-08-28
**標題**: prometheus_metrics.py 中未使用的 global 宣告

**原因**: 
- `init_prometheus` 函數中使用 `global prometheus_metrics` 但從未重新賦值
- 造成 F824 flake8 錯誤: "global is unused: name is never assigned in scope"

**解決方案**: 
移除不必要的 global 宣告：
```python
# 修改前
async def init_prometheus(start_http_server: bool = True, push_gateway_url: str = None):
    global prometheus_metrics  # 未使用的 global
    await prometheus_metrics.initialize(start_http_server, push_gateway_url)

# 修改後  
async def init_prometheus(start_http_server: bool = True, push_gateway_url: str = None):
    await prometheus_metrics.initialize(start_http_server, push_gateway_url)
```

**驗證**: 
```bash
python3 -m flake8 shared/ --max-line-length=100 --count  # 返回 0 錯誤
```

**狀態**: 已修復 ✅

**影響範圍**: 
- shared/prometheus_metrics.py
- F824 flake8 檢查通過

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

## 問題 #4 - 日期: 2025-08-28
**標題**: GitHub Actions 環境缺少 redis-cli 命令

**原因**: 
- GitHub Actions Ubuntu 環境默認未安裝 redis-tools 包
- test-coverage.yml 工作流程嘗試使用 redis-cli 驗證 Redis 服務連接
- 雖然 Redis 服務容器正在運行，但主機環境缺少客戶端工具

**錯誤**:
```
/home/runner/work/_temp/5a0ede25-6ab0-4a8d-9689-3bfa53fba472.sh: line 6: redis-cli: command not found
```

**解決方案**:
1. ✅ 在使用 redis-cli 之前先安裝 redis-tools 包
2. ✅ 添加安裝步驟：`sudo apt-get update && sudo apt-get install -y redis-tools`
3. ✅ 修復 test-coverage.yml 第 117 行

**狀態**: ✅ 已修復

**影響範圍**: 
- `.github/workflows/test-coverage.yml`
- 整合測試中的服務連接驗證

**修復位置**: 
- test-coverage.yml 第 116-117 行：添加 redis-tools 安裝步驟

---

## 🚨 安全問題 #5-8 - 日期: 2025-08-28
**標題**: 使用弱 MD5 哈希的高危安全問題 (4個)

**嚴重級別**: HIGH (高危)  
**CWE**: CWE-327 - 使用弱加密算法

**問題清單**:

### 問題 #5: content_analyzer.py MD5 哈希用於快取鍵
- **位置**: `./bot/services/content_analyzer.py:288`
- **代碼**: `cache_key = f"sentiment:{hashlib.md5(text.encode()).hexdigest()}"`
- **風險**: 用戶文本內容可能被暴力破解

### 問題 #6: data_management_service.py 用戶ID匿名化
- **位置**: `./bot/services/data_management_service.py:316`  
- **代碼**: `f"anon_user_{hashlib.md5(str(guild_id).encode()).hexdigest()[:8]}"`
- **風險**: Guild ID 可能被反向工程

### 問題 #7: data_management_service.py Discord ID匿名化
- **位置**: `./bot/services/data_management_service.py:521`
- **代碼**: `f"anon_{hashlib.md5(str(row['discord_id']).encode()).hexdigest()[:8]}"`
- **風險**: Discord ID 可能被反向工程

### 問題 #8: economy_manager.py 交易ID生成
- **位置**: `./bot/services/economy_manager.py:1122`
- **代碼**: `hashlib.md5(f"{timestamp}{time.time()}".encode()).hexdigest()[:8]`
- **風險**: 交易ID 可能被預測或碰撞

**修復方案**:
1. ✅ **非安全用途**: 使用 `usedforsecurity=False` 參數 (快取鍵)
2. ✅ **安全用途**: 替換為 SHA-256 或更強的哈希算法  
3. ✅ **隨機生成**: 使用 `secrets` 模組生成安全隨機值

**修復詳情**:
- **問題 #5**: 添加 `usedforsecurity=False` 參數到快取鍵生成
- **問題 #6**: Guild ID 匿名化改用 SHA-256，輸出長度增加到16字符
- **問題 #7**: Discord ID 匿名化改用 SHA-256，輸出長度增加到16字符  
- **問題 #8**: 交易ID 改用 `secrets.token_hex(4)` 生成安全隨機字符串

**驗證結果**: 
```
bandit 掃描結果: High: 0 (之前: High: 4)
✅ 所有高危安全問題已修復
```

**狀態**: ✅ 已修復

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