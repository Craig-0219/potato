# 🔑 管理員權限設置指南

> Potato Bot v3.0.0 - 管理員權限開啟和 API 金鑰管理

## 📋 權限等級說明

系統採用 **四級權限架構**，提供精細的權限控制：

| 權限等級 | 代碼 | 說明 | 適用範圍 |
|---------|------|------|----------|
| 🔍 **唯讀** | `read_only` | 僅可查看數據 | 一般用戶、監控工具 |
| ✏️ **讀寫** | `write` | 可修改基本設置 | 版主、內容管理員 |
| 👑 **管理員** | `admin` | 可管理大部分功能 | 伺服器管理員 |
| 🎯 **超級管理員** | `super_admin` | 完整系統控制權 | 系統管理員、開發者 |

## 🚀 快速設置管理員權限

### 方法 1：程式直接創建（推薦）

在伺服器上執行以下指令創建超級管理員 API 金鑰：

```bash
cd /root/projects/potato

# 創建超級管理員 API 金鑰
python3 -c "
import asyncio
from bot.api.auth import APIKeyManager, PermissionLevel

async def create_admin_key():
    manager = APIKeyManager()
    await manager.initialize()
    
    # 創建超級管理員金鑰
    raw_key, api_key = await manager.create_api_key(
        name='Super Admin Key',
        permission_level=PermissionLevel.SUPER_ADMIN,
        expires_days=365  # 有效期一年
    )
    
    print('=' * 50)
    print('🎉 超級管理員 API 金鑰創建成功！')
    print('=' * 50)
    print(f'🔑 API Key: {raw_key}')
    print(f'🆔 Key ID: {api_key.key_id}')
    print(f'📛 名稱: {api_key.name}')
    print(f'🎯 權限: {api_key.permission_level}')
    print(f'📅 過期時間: {api_key.expires_at}')
    print('=' * 50)
    print('⚠️  請妥善保存此 API 金鑰，系統不會再次顯示！')

asyncio.run(create_admin_key())
"
```

### 方法 2：資料庫直接操作

如果需要直接在資料庫中操作：

```sql
-- 連接到 MySQL 資料庫
USE potato_bot;

-- 插入超級管理員 API 金鑰記錄
INSERT INTO api_keys (
    key_id, 
    name, 
    hashed_key, 
    permission_level, 
    created_at, 
    expires_at, 
    is_active
) VALUES (
    'admin_key_001',
    'Initial Super Admin',
    SHA2('your_custom_api_key_here', 256),
    'super_admin',
    NOW(),
    DATE_ADD(NOW(), INTERVAL 365 DAY),
    1
);
```

## 🔧 使用 API 金鑰

### 在 Web 界面中使用

1. **登入系統**：使用創建的 API 金鑰
2. **API 管理頁面**：`http://your-server:3000/api-management`
3. **添加認證頭**：
   ```
   Authorization: Bearer pk_your_32_character_api_key_here
   ```

### 在程式中使用

```javascript
// JavaScript/TypeScript 範例
const apiKey = 'pk_your_32_character_api_key_here';

fetch('/api/v1/system/health', {
  headers: {
    'Authorization': `Bearer ${apiKey}`,
    'Content-Type': 'application/json'
  }
})
.then(response => response.json())
.then(data => console.log(data));
```

```python
# Python 範例
import requests

api_key = 'pk_your_32_character_api_key_here'
headers = {
    'Authorization': f'Bearer {api_key}',
    'Content-Type': 'application/json'
}

response = requests.get('http://localhost:8000/api/v1/system/health', headers=headers)
print(response.json())
```

## 🎯 功能權限對應表

### 超級管理員 (`super_admin`)
- ✅ 創建/撤銷 API 金鑰
- ✅ 系統維護模式
- ✅ 完整系統監控
- ✅ 用戶權限管理
- ✅ 系統配置修改

### 管理員 (`admin`)
- ✅ 票券管理
- ✅ 用戶管理
- ✅ 基本系統監控
- ❌ API 金鑰管理
- ❌ 系統維護模式

### 讀寫權限 (`write`)
- ✅ 修改票券狀態
- ✅ 回覆票券
- ✅ 查看統計數據
- ❌ 用戶管理
- ❌ 系統設置

### 唯讀權限 (`read_only`)
- ✅ 查看票券列表
- ✅ 查看統計數據
- ❌ 修改任何內容

## 🛡️ 安全最佳實踐

### API 金鑰管理
1. **定期輪換**：建議每 3-6 個月更換 API 金鑰
2. **最小權限原則**：僅授予必要的最低權限
3. **監控使用情況**：定期檢查 API 金鑰使用記錄
4. **安全儲存**：使用環境變數或安全密鑰管理服務

### 權限分離
```bash
# 建議的權限分配
# 日常管理員 - admin 權限
python3 create_api_key.py --name "Daily Admin" --level admin --days 90

# 監控系統 - read_only 權限  
python3 create_api_key.py --name "Monitoring Tool" --level read_only --days 365

# 內容管理員 - write 權限
python3 create_api_key.py --name "Content Manager" --level write --days 180
```

## 🚨 故障排除

### 常見問題

**Q: API 金鑰創建失敗**
```bash
# 檢查資料庫連接
python3 -c "from bot.db.pool import get_db_health; print(get_db_health())"

# 檢查 API 金鑰管理器
python3 -c "from bot.api.auth import get_api_key_manager; print('Manager OK')"
```

**Q: 權限被拒絕 (403 Forbidden)**
```bash
# 驗證 API 金鑰
curl -H "Authorization: Bearer your_api_key" http://localhost:8000/api/v1/system/health
```

**Q: API 金鑰過期**
```bash
# 檢查金鑰狀態
python3 -c "
from bot.api.auth import get_api_key_manager
import asyncio

async def check_key():
    manager = get_api_key_manager()
    # 檢查特定金鑰狀態
    
asyncio.run(check_key())
"
```

### 日誌檢查

```bash
# 檢查 API 認證日誌
tail -f logs/api.log | grep -i "auth\|permission"

# 檢查系統日誌
tail -f logs/system.log | grep -i "api_key"
```

## 📊 系統狀態監控

### 目前功能狀態

| 功能模組 | 認證需求 | 狀態 | 說明 |
|---------|----------|------|------|
| 🏠 **儀表板** | ❌ 無需認證 | ✅ 正常 | 使用公開 API |
| 🖥️ **系統監控** | ❌ 無需認證 | ✅ 正常 | 即時系統指標 |
| 🎫 **票券管理** | ❌ 無需認證* | ✅ 正常 | *列表查看需要認證 |
| 📊 **分析報告** | ❌ 無需認證 | ✅ 正常 | 公開統計數據 |
| 🗳️ **投票系統** | ❌ 無需認證 | ✅ 正常 | WebSocket 即時更新 |
| 🔧 **API 管理** | ✅ 需要超級管理員 | ✅ 正常 | 金鑰管理功能 |

## 📚 相關文檔

- **[🚀 快速入門指南](../user-guides/QUICKSTART_v2.2.0.md)** - 系統部署教學
- **[🛠️ API 參考文檔](../development/API_REFERENCE.md)** - 完整 API 說明
- **[🔒 安全配置指南](SECURITY_SETUP.md)** - 系統安全設置
- **[📋 使用手冊](../user-guides/USER_MANUAL.md)** - 詳細功能說明

---

## 📞 技術支援

如果遇到權限設置問題，請：

1. **檢查系統日誌**：`logs/api.log` 和 `logs/system.log`
2. **驗證資料庫連接**：確保 MySQL 服務正常運行
3. **聯繫技術支援**：提供錯誤日誌和系統環境資訊

---

<div align="center">

### 🔑 **安全的權限管理，強大的系統控制**

**[📖 完整文檔](../README.md) • [🚀 快速部署](../user-guides/QUICKSTART_v2.2.0.md) • [🛠️ 開發指南](../development/)**

</div>