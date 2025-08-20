# Minecraft 插件架構設計文檔

## 📋 專案概述

**插件名稱**: PotatoEconomy  
**版本**: v1.0.0  
**Minecraft 版本**: 1.19.4+  
**服務端**: Bukkit/Spigot/Paper  
**開發語言**: Java  
**開發目標**: 與 Discord Bot 跨平台經濟同步

---

## 🎯 核心功能

### 主要功能模組
- [x] **經濟系統管理** - 貨幣、寶石、經驗值管理
- [x] **跨平台同步** - 與 Discord Bot 實時數據同步
- [x] **活動獎勵系統** - 挖礦、建築、PvP 獎勵機制
- [x] **抗通膨機制** - 動態調整獎勵倍率
- [x] **用戶界面** - GUI 商店和經濟管理界面
- [x] **API 端點** - RESTful API 提供數據交換

### 技術規格
- **數據庫**: MySQL 8.0+ (與 Discord Bot 共享)
- **框架**: Bukkit API 1.19+
- **網絡**: HTTP REST API + WebSocket (可選)
- **認證**: JWT Token + Server Key
- **序列化**: JSON (Jackson Library)

---

## 📁 插件結構

```
PotatoEconomy/
├── src/main/java/com/potato/economy/
│   ├── PotatoEconomy.java              # 主插件類
│   ├── config/
│   │   ├── EconomyConfig.java          # 經濟配置管理
│   │   └── DatabaseConfig.java         # 數據庫配置
│   ├── managers/
│   │   ├── EconomyManager.java         # 經濟系統管理器
│   │   ├── SyncManager.java            # 跨平台同步管理
│   │   ├── RewardManager.java          # 獎勵系統管理
│   │   └── AntiInflationManager.java   # 抗通膨管理
│   ├── database/
│   │   ├── DatabaseConnection.java     # 數據庫連接池
│   │   ├── EconomyDAO.java            # 經濟數據訪問
│   │   └── SyncDAO.java               # 同步記錄訪問
│   ├── api/
│   │   ├── EconomyAPI.java            # 經濟 API 接口
│   │   ├── RestServer.java            # REST 服務器
│   │   └── WebhookHandler.java        # Webhook 處理器
│   ├── listeners/
│   │   ├── PlayerJoinListener.java     # 玩家加入監聽
│   │   ├── BlockBreakListener.java     # 挖礦獎勵監聽
│   │   ├── BlockPlaceListener.java     # 建築獎勵監聽
│   │   └── PlayerDeathListener.java    # PvP 獎勵監聽
│   ├── commands/
│   │   ├── EconomyCommand.java        # 經濟命令處理
│   │   ├── SyncCommand.java           # 同步命令處理
│   │   └── AdminCommand.java          # 管理員命令
│   ├── gui/
│   │   ├── EconomyGUI.java            # 經濟界面
│   │   ├── ShopGUI.java               # 商店界面
│   │   └── StatsGUI.java              # 統計界面
│   ├── models/
│   │   ├── PlayerEconomy.java         # 玩家經濟模型
│   │   ├── Transaction.java           # 交易記錄模型
│   │   └── SyncRecord.java            # 同步記錄模型
│   └── utils/
│       ├── JSONUtil.java              # JSON 工具類
│       ├── HttpUtil.java              # HTTP 工具類
│       └── MessageUtil.java           # 消息工具類
├── src/main/resources/
│   ├── plugin.yml                     # 插件描述文件
│   ├── config.yml                     # 默認配置文件
│   ├── database.yml                   # 數據庫配置文件
│   └── messages.yml                   # 消息配置文件
└── pom.xml                           # Maven 項目文件
```

---

## 🔧 核心類設計

### 1. 主插件類 (PotatoEconomy.java)

```java
public class PotatoEconomy extends JavaPlugin {
    private EconomyManager economyManager;
    private SyncManager syncManager;
    private RestServer restServer;
    private DatabaseConnection database;
    
    @Override
    public void onEnable() {
        // 初始化配置
        loadConfigs();
        
        // 初始化數據庫
        initializeDatabase();
        
        // 初始化管理器
        initializeManagers();
        
        // 註冊監聽器和命令
        registerListenersAndCommands();
        
        // 啟動 REST API 服務器
        startRestServer();
        
        getLogger().info("PotatoEconomy v1.0.0 已啟用");
    }
    
    @Override
    public void onDisable() {
        // 執行跨平台同步
        syncManager.performFinalSync();
        
        // 關閉 REST 服務器
        restServer.shutdown();
        
        // 關閉數據庫連接
        database.close();
        
        getLogger().info("PotatoEconomy 已停用");
    }
}
```

### 2. 經濟管理器 (EconomyManager.java)

```java
public class EconomyManager {
    private final PotatoEconomy plugin;
    private final EconomyDAO economyDAO;
    private final Map<UUID, PlayerEconomy> playerCache;
    
    // 貨幣操作
    public boolean addCoins(UUID playerId, int amount);
    public boolean subtractCoins(UUID playerId, int amount);
    public boolean addGems(UUID playerId, int amount);
    public boolean addExperience(UUID playerId, int amount);
    
    // 獲取玩家經濟數據
    public PlayerEconomy getPlayerEconomy(UUID playerId);
    
    // 每日限制檢查
    public boolean checkDailyLimit(UUID playerId, CurrencyType type, int amount);
    
    // 交易記錄
    public void recordTransaction(UUID playerId, TransactionType type, 
                                CurrencyType currency, int amount, String description);
}
```

### 3. 跨平台同步管理器 (SyncManager.java)

```java
public class SyncManager {
    private final PotatoEconomy plugin;
    private final SyncDAO syncDAO;
    private final HttpUtil httpUtil;
    private final ScheduledExecutorService syncScheduler;
    
    // 同步到 Discord
    public CompletableFuture<Boolean> syncToDiscord(UUID playerId);
    
    // 處理來自 Discord 的同步請求
    public boolean handleDiscordSync(SyncRequest request);
    
    // 定期同步任務
    public void startPeriodicSync();
    
    // 即時同步觸發
    public void triggerImmediateSync(UUID playerId, String reason);
    
    // 同步失敗重試
    public void retryFailedSyncs();
}
```

### 4. 獎勵系統管理器 (RewardManager.java)

```java
public class RewardManager {
    private final EconomyManager economyManager;
    private final AntiInflationManager inflationManager;
    
    // 挖礦獎勵
    public void handleMiningReward(Player player, Material blockType);
    
    // 建築獎勵
    public void handleBuildingReward(Player player, Material blockType);
    
    // PvP 獎勵
    public void handlePvPReward(Player winner, Player loser);
    
    // 每日登入獎勵
    public void handleDailyReward(Player player);
    
    // 成就獎勵
    public void handleAchievementReward(Player player, String achievement);
    
    // 計算動態獎勵倍率
    private double calculateRewardMultiplier(RewardType type);
}
```

---

## 🌐 API 端點設計

### REST API 路由

```java
// 基礎路徑: http://minecraft-server:8080/api/economy/

GET    /player/{uuid}              // 獲取玩家經濟數據
POST   /sync                       // 接收 Discord 同步請求
GET    /stats/{server}             // 獲取服務器經濟統計
POST   /reward                     // 記錄獎勵事件
GET    /transactions/{uuid}        // 獲取玩家交易記錄
POST   /admin/adjust               // 管理員調整
GET    /health                     // 健康檢查端點
```

### 同步請求格式

```json
{
  "user_id": "123456789012345678",
  "guild_id": "987654321098765432",
  "server_key": "minecraft_server_auth_key",
  "timestamp": "2024-01-15T10:30:00Z",
  "balances": {
    "coins": 1500,
    "gems": 25,
    "tickets": 10,
    "experience": 5000
  },
  "sync_type": "discord_to_minecraft"
}
```

### 同步回應格式

```json
{
  "status": "success",
  "message": "同步完成",
  "timestamp": "2024-01-15T10:30:05Z",
  "adjusted_balances": {
    "coins": 1500,
    "gems": 25,
    "tickets": 10,
    "experience": 5000
  },
  "minecraft_adjustments": {
    "reason": "服務器獎勵加成",
    "bonus_coins": 50
  }
}
```

---

## 💾 數據庫設計

### 玩家經濟表 (player_economy_mc)

```sql
CREATE TABLE player_economy_mc (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    player_uuid VARCHAR(36) NOT NULL,
    discord_user_id BIGINT,
    guild_id BIGINT,
    server_name VARCHAR(50),
    
    -- 貨幣餘額
    coins INT DEFAULT 0,
    gems INT DEFAULT 0,
    tickets INT DEFAULT 0,
    experience INT DEFAULT 0,
    
    -- 統計數據
    total_playtime BIGINT DEFAULT 0,
    blocks_mined INT DEFAULT 0,
    blocks_placed INT DEFAULT 0,
    pvp_wins INT DEFAULT 0,
    pvp_deaths INT DEFAULT 0,
    
    -- 每日數據
    daily_coins_earned INT DEFAULT 0,
    daily_blocks_mined INT DEFAULT 0,
    last_daily_reset DATETIME,
    last_login DATETIME,
    
    -- 同步狀態
    last_sync_time DATETIME,
    sync_version INT DEFAULT 1,
    sync_pending BOOLEAN DEFAULT FALSE,
    
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    
    UNIQUE KEY unique_player_server (player_uuid, server_name),
    INDEX idx_discord_user (discord_user_id),
    INDEX idx_guild (guild_id),
    INDEX idx_sync_pending (sync_pending),
    INDEX idx_last_sync (last_sync_time)
);
```

### 跨平台交易記錄表 (cross_platform_transactions)

```sql
CREATE TABLE cross_platform_transactions (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    transaction_id VARCHAR(64) UNIQUE NOT NULL,
    
    -- 玩家信息
    player_uuid VARCHAR(36),
    discord_user_id BIGINT,
    guild_id BIGINT,
    
    -- 交易詳情
    currency_type ENUM('coins', 'gems', 'tickets', 'experience'),
    transaction_type ENUM('earn', 'spend', 'transfer', 'sync', 'penalty', 'bonus'),
    amount INT NOT NULL,
    balance_before INT,
    balance_after INT,
    
    -- 平台信息
    source_platform ENUM('discord', 'minecraft'),
    minecraft_server VARCHAR(50),
    description TEXT,
    
    -- 同步狀態
    sync_status ENUM('pending', 'completed', 'failed'),
    sync_attempts INT DEFAULT 0,
    last_sync_attempt DATETIME,
    
    -- 元數據
    metadata JSON,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    
    INDEX idx_player_uuid (player_uuid),
    INDEX idx_discord_user (discord_user_id),
    INDEX idx_transaction_type (transaction_type),
    INDEX idx_source_platform (source_platform),
    INDEX idx_sync_status (sync_status),
    INDEX idx_created_at (created_at)
);
```

---

## ⚙️ 配置文件

### config.yml

```yaml
# PotatoEconomy 插件配置

# 基本設定
economy:
  # 貨幣設定
  currency:
    coins:
      name: "金幣"
      symbol: "🪙"
      daily_max: 500
    gems:
      name: "寶石"
      symbol: "💎"
      daily_max: 20
    experience:
      name: "經驗值"
      symbol: "⭐"
      multiplier: 1.0

  # 獎勵設定
  rewards:
    mining:
      enabled: true
      base_coins: 2
      rare_blocks_multiplier: 5
      daily_limit: 200
    building:
      enabled: true
      base_experience: 1
      daily_limit: 100
    pvp:
      enabled: true
      winner_gems: 5
      loser_penalty: 0
    daily_login:
      enabled: true
      base_coins: 50
      streak_bonus: 10
      max_streak: 7

# 跨平台同步設定
sync:
  enabled: true
  discord_api_url: "http://discord-bot:8000"
  server_key: "your_minecraft_server_key"
  sync_interval: 300  # 5分鐘
  retry_attempts: 3
  retry_delay: 60     # 1分鐘

# 抗通膨設定
anti_inflation:
  enabled: true
  check_interval: 3600  # 1小時
  inflation_threshold: 0.03  # 3%
  adjustment_factor: 0.1     # 10%調整
  min_reward_multiplier: 0.5
  max_reward_multiplier: 2.0

# REST API 設定
api:
  enabled: true
  port: 8080
  host: "0.0.0.0"
  cors_enabled: true
  rate_limit: 100  # 每分鐘請求數

# 數據庫設定 (繼承自 database.yml)
database:
  host: "localhost"
  port: 3306
  database: "potato_bot"
  username: "potato_user"
  password: "your_password"
  pool_size: 10
  connection_timeout: 30000

# GUI 設定
gui:
  economy_menu:
    title: "經濟系統"
    size: 27
  shop_menu:
    title: "商店"
    size: 54
  stats_menu:
    title: "統計信息"
    size: 36

# 調試設定
debug:
  enabled: false
  log_transactions: true
  log_sync_events: true
  performance_monitoring: false
```

---

## 🚀 開發階段規劃

### Phase 1: 基礎架構 (週 1-2)
- [x] 插件基礎架構搭建
- [x] 數據庫連接和 DAO 層
- [x] 基本經濟系統功能
- [x] 配置文件系統

### Phase 2: 獎勵系統 (週 3-4)
- [x] 挖礦獎勵監聽器
- [x] 建築獎勵監聽器
- [x] PvP 獎勵系統
- [x] 每日登入獎勵

### Phase 3: 跨平台同步 (週 5-6)
- [x] REST API 服務器
- [x] Discord Bot 通信接口
- [x] 同步管理器和重試機制
- [x] Webhook 處理器

### Phase 4: 抗通膨系統 (週 7-8)
- [x] 經濟指標監控
- [x] 動態獎勵調整
- [x] 通膨控制算法
- [x] 管理員控制面板

### Phase 5: 用戶界面 (週 9-10)
- [x] 經濟狀況 GUI
- [x] 商店系統 GUI
- [x] 統計信息界面
- [x] 管理員工具界面

### Phase 6: 測試和優化 (週 11)
- [x] 單元測試和集成測試
- [x] 性能優化
- [x] 安全性檢查
- [x] 文檔完善

---

## 🔒 安全考慮

### 認證和授權
1. **Server Key 驗證**: 所有 API 請求必須包含有效的服務器金鑰
2. **JWT Token**: 用於用戶身份驗證
3. **IP 白名單**: 限制 API 訪問來源
4. **請求簽名**: 防止請求被篡改

### 數據安全
1. **SQL 注入防護**: 使用預處理語句
2. **輸入驗證**: 嚴格驗證所有輸入參數
3. **數據加密**: 敏感數據加密存儲
4. **訪問日誌**: 記錄所有 API 訪問

### 經濟安全
1. **交易驗證**: 所有交易都經過雙重驗證
2. **異常檢測**: 自動檢測異常經濟活動
3. **回滾機制**: 支持錯誤交易回滾
4. **限制機制**: 單日交易和獎勵限制

---

## 📊 監控和日誌

### 性能監控
- REST API 響應時間
- 數據庫查詢性能
- 同步成功率
- 內存和 CPU 使用率

### 業務監控
- 每日活躍玩家數
- 貨幣發行和流通量
- 通膨率趨勢
- 跨平台同步頻率

### 日誌級別
- **ERROR**: 系統錯誤和異常
- **WARN**: 警告和風險事件
- **INFO**: 一般業務事件
- **DEBUG**: 詳細調試信息

---

## 🔧 部署和維護

### 部署需求
- **Java**: JDK 17+
- **Minecraft**: 1.19.4+
- **內存**: 最少 2GB RAM
- **存儲**: 最少 1GB 可用空間
- **網絡**: 穩定的網絡連接

### 維護任務
1. **每日**: 檢查同步狀態和錯誤日誌
2. **每週**: 數據庫優化和清理
3. **每月**: 性能分析和調優
4. **每季**: 安全性檢查和更新

### 備份策略
- **數據庫**: 每日自動備份
- **配置文件**: 版本控制管理
- **交易記錄**: 定期歸檔
- **日誌文件**: 滾動備份策略

---

這個架構設計為 Minecraft 插件提供了完整的跨平台經濟系統基礎，支援與 Discord Bot 的無縫集成，並具備強大的抗通膨和安全機制。