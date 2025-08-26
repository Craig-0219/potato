# ⚡ Cogs 快速修復指南

## 🎯 **立即行動清單**

### **第一優先級 - 核心功能搶救**

#### 1. **票券系統修復** (ticket_core, ticket_listener)
```bash
# 檢查語法錯誤
python -m py_compile bot/cogs/ticket_core.py
python -m py_compile bot/cogs/ticket_listener.py

# 修復 language_manager.py 第 70 行
python -m py_compile bot/services/language_manager.py
```

#### 2. **投票系統修復** (vote_core, vote_listener)  
```bash
# 檢查語法錯誤
python -m py_compile bot/cogs/vote_core.py
python -m py_compile bot/cogs/vote_listener.py

# 修復 vote_dao.py 第 103 行
python -m py_compile bot/db/vote_dao.py
```

### **常見錯誤類型和修復方法**

#### **IndentationError 修復**
```python
# 錯誤示例
if condition:
pass  # ← 這行縮進不正確

# 正確修復
if condition:
    pass  # ← 使用 4 空格縮進
```

#### **SyntaxError: expected 'except' 修復**
```python
# 錯誤示例
try:
    some_code()
# ← 缺少 except 或 finally

# 正確修復
try:
    some_code()
except Exception as e:
    logger.error(f"錯誤: {e}")
```

### **批量語法檢查腳本**
```bash
#!/bin/bash
# 檢查所有失敗的 Cogs
FAILED_COGS=(
    "bot/cogs/ticket_core.py"
    "bot/cogs/ticket_listener.py" 
    "bot/cogs/vote_core.py"
    "bot/cogs/vote_listener.py"
    "bot/cogs/welcome_core.py"
    "bot/cogs/welcome_listener.py"
    "bot/cogs/web_auth_core.py"
    "bot/cogs/ai_core.py"
    "bot/cogs/language_core.py"
    "bot/cogs/workflow_core.py"
    "bot/cogs/dashboard_core.py"
    "bot/cogs/webhook_core.py"
    "bot/cogs/ai_assistant_core.py"
    "bot/cogs/guild_management_core.py"
    "bot/cogs/menu_core.py"
    "bot/cogs/fallback_commands.py"
)

for cog in "${FAILED_COGS[@]}"; do
    echo "檢查 $cog..."
    python -m py_compile "$cog" 2>&1 | grep -E "(SyntaxError|IndentationError)"
done
```

---

## 🔧 **修復工作流程**

### **步驟 1: 語法檢查**
```bash
# 單個檔案檢查
python -c "import py_compile; py_compile.compile('bot/cogs/ticket_core.py', doraise=True)"

# 批量檢查
find bot/cogs -name "*.py" -exec python -m py_compile {} \;
```

### **步驟 2: 依賴檢查**
```bash
# 檢查導入問題
python -c "
import sys
sys.path.insert(0, '.')
try:
    from bot.cogs import ticket_core
    print('✅ ticket_core 導入成功')
except Exception as e:
    print(f'❌ ticket_core 導入失敗: {e}')
"
```

### **步驟 3: 逐個測試載入**
```bash
# 測試單個 Cog 載入
python -c "
import asyncio
import discord
from discord.ext import commands

bot = commands.Bot(command_prefix='!', intents=discord.Intents.all())

async def test_cog():
    try:
        await bot.load_extension('bot.cogs.ticket_core')
        print('✅ ticket_core 載入成功')
    except Exception as e:
        print(f'❌ ticket_core 載入失敗: {e}')
    await bot.close()

asyncio.run(test_cog())
"
```

---

## 📋 **修復檢查清單**

### **每個 Cog 修復後檢查**
- [ ] **語法檢查**: `python -m py_compile cog_file.py`
- [ ] **導入測試**: 能否正常 import
- [ ] **載入測試**: Bot 能否載入該 Cog
- [ ] **功能測試**: 相關指令是否工作
- [ ] **日誌檢查**: 無錯誤訊息輸出

### **全域檢查**
- [ ] **所有 Cogs 載入**: 23/23 成功率
- [ ] **指令註冊**: 無衝突錯誤
- [ ] **系統穩定**: Bot 能正常運行
- [ ] **功能完整**: 核心功能可用

---

## 🎯 **每日修復目標**

### **Day 1 目標**
- ✅ 修復 ticket_core 和 ticket_listener
- ✅ 修復 vote_core 和 vote_listener  
- ✅ 基本票券投票功能恢復

### **Day 2 目標**
- ✅ 修復 welcome_core 和 welcome_listener
- ✅ 修復 web_auth_core 和 ai_core
- ✅ 用戶體驗功能恢復

### **Day 3+ 目標**
- ✅ 修復其餘所有 Cogs
- ✅ 100% 載入成功率
- ✅ 系統完全穩定

---

**⚡ 重要提醒**: 每次修復後立即測試，確保不會引入新問題！