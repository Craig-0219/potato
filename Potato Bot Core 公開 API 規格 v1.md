# Potato Bot Core 公開 API 規格 v1（更新版）

## 目標

- Core 負責啟動、關閉、Infra、Cogs 載入與 Service Registry
- 所有功能一律透過 Cogs + Services 擴充，不直接修改 `src/potato_bot/main.py`

## 名詞定義

- Core：`src/potato_bot/main.py`
- PotatoBot：`class PotatoBot(commands.Bot)`
- Service：`src/potato_bot/services/*_manager.py` 或 `*_service.py`
- Cog：`src/potato_bot/cogs/*.py`
- DAO：`src/potato_bot/db/*_dao.py`
- Shared：`src/potato_shared/*`

## 1. Core 啟動流程與生命週期

### 1.1 啟動前檢查 `pre_startup_checks()`

檢查項目：
- Python 版本（目前最低檢查 3.8，專案需求為 3.10+）
- `discord` / `aiomysql` / `dotenv` 模組是否存在
- `DISCORD_TOKEN` 與 DB 設定是否齊全（從 `potato_shared.config` 讀取）

### 1.2 啟動流程

- 建立 `PotatoBot()`
- 註冊 signal handler（`setup_signal_handlers`）
- `async with bot: await bot.start(DISCORD_TOKEN)`

### 1.3 `PotatoBot.setup_hook()` 執行順序

1. `_setup_error_handler()`：註冊全域錯誤處理器
2. `_init_database_infra()`：初始化 DB 連線池、建立資料表、健康檢查
3. `_load_extensions()`：自動載入 Cogs（`discover_cog_modules` + `COGS_PREFIX`）
4. `log_persistent_views()`：只檢查 Persistent Views 註冊狀態
5. `_sync_commands()`：同步斜線命令（遵循 `SYNC_COMMANDS`）

### 1.4 `on_ready()`

- 設定 `startup_time`
- 更新 bot presence
- 輸出已連接的 guild 數量

### 1.5 `close()`

- 取消背景任務
- 關閉 DB pool
- 關閉 Discord 連線

### 1.6 Cogs 可依賴的假設

在 Cog `__init__` 被呼叫時：
- DB 連線池已建立
- `bot.error_handler` 已設置
- `bot.services` 已存在

## 2. PotatoBot 對 Cogs 暴露的 API

### 2.1 公開屬性（可依賴）

```
class PotatoBot(commands.Bot):
    # discord.py
    user: discord.ClientUser
    guilds: list[discord.Guild]
    latency: float | None

    # Core
    error_handler: Any | None
    startup_time: datetime | None
    services: dict[str, Any]
```

### 2.2 公開方法

- `get_uptime() -> str`
  - 取得 Bot 運行時間（人類可讀格式）

- `create_background_task(coro: Coroutine, *, name: str | None = None) -> asyncio.Task`
  - 建立背景任務並納入 Core 生命週期管理

## 3. Service Registry 規格

Core 目前不預設註冊任何 Service。
若某 Service 需要跨多個 Cog 共用，請遵守以下規則：

- 建立實例
- 掛在 `bot.services["key"]`
- 需要時可同步提供快捷屬性

範例：

```
self.my_service = MyService(self)
bot.services["my_service"] = self.my_service
```

Cog 端使用方式：

```
self.my_service = bot.services.get("my_service")
```

## 4. Cog 實作規範

### 4.1 基本結構

```
# src/potato_bot/cogs/example_core.py

from discord.ext import commands
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from potato_bot.main import PotatoBot

class ExampleCore(commands.Cog):
    def __init__(self, bot: "PotatoBot"):
        self.bot = bot

    async def cog_load(self):
        # 初始化功能專屬資源
        ...

    async def cog_unload(self):
        # 取消背景任務、清理狀態
        ...

async def setup(bot: "PotatoBot"):
    await bot.add_cog(ExampleCore(bot))
```

### 4.2 Persistent View

- 請使用 `potato_bot.utils.managed_cog.register_persistent_view`
- Core 只負責檢查，不負責註冊

### 4.3 禁止事項

- 不可呼叫：`init_database()` / `close_database()` / `initialize_all_tables()`
- 不可呼叫：`bot.start()` / `bot.close()`（除非是 owner 管理功能）
- 不可自行 `bot.tree.sync()`（除非是 owner 管理功能）
- 不可直接 import 其他 Cog 內部實作

跨功能需求請改用：
- 共用 Service
- `bot.dispatch()` + Listener

## 5. Error Handling 與 Logging

- 一律使用 `potato_shared.logger`
- 盡量讓例外往外拋，交給全域 error handler

## 6. DB 與 DAO 使用規範

允許：
- 使用 DAO（`src/potato_bot/db/*_dao.py`）
- 直接使用 `db_pool` 進行 SQL 操作

禁止：
- 在 Cog 內做 DB 初始化/關閉

## 7. Owner / 管理 Cog 的特例

`owner_core` 允許：
- `bot.load_extension` / `bot.reload_extension`
- `bot.tree.sync()`（手動同步）
- `bot.close()`（交由外部 process manager 重啟）
- 讀取 `bot.get_uptime()` / `bot.latency` / `len(bot.guilds)` / `get_db_health()`

## 8. 允許修改 Core 的範圍

允許（Infra 級）：
- 替換 DB 連線層（介面不變）
- 新增共用 Service（需掛入 `bot.services`）
- 調整錯誤處理實作（`bot.error_handler` 仍需存在）

不允許：
- 在 Core 內新增功能專屬初始化
- 在 Core 內直接 import 任一 Cog 或 feature 內部 class
- 在 Core 寫死 guild/channel 或功能邏輯
