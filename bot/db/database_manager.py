# bot/db/database_manager.py - 新建檔案
"""
資料庫管理器 - 自動初始化和遷移
統一管理所有資料表的創建和更新
"""

import asyncio
from typing import Dict, List, Tuple, Optional, Any
from bot.db.pool import db_pool
from shared.logger import logger


class DatabaseManager:
    """資料庫管理器 - 負責資料表初始化和遷移"""
    
    def __init__(self):
        self.db = db_pool
        self.current_version = "1.0.0"
        
    async def initialize_all_tables(self, force_recreate: bool = False):
        """初始化所有資料表"""
        logger.info("🔄 開始初始化資料庫表格...")
        
        try:
            # 創建版本管理表
            await self._create_version_table()
            
            # 檢查資料庫版本
            current_db_version = await self._get_database_version()
            
            if force_recreate:
                logger.warning("⚠️ 強制重建模式 - 將刪除所有現存表格")
                await self._drop_all_tables()
                current_db_version = None
            
            # 創建各系統的表格
            await self._create_ticket_tables()
            await self._create_vote_tables()
            
            # 更新資料庫版本
            await self._update_database_version(self.current_version)
            
            logger.info("✅ 資料庫表格初始化完成")
            
        except Exception as e:
            logger.error(f"❌ 資料庫初始化失敗：{e}")
            raise
    
    async def _create_version_table(self):
        """創建版本管理表"""
        async with self.db.connection() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute("""
                    CREATE TABLE IF NOT EXISTS database_version (
                        id INT PRIMARY KEY DEFAULT 1,
                        version VARCHAR(20) NOT NULL,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                        CONSTRAINT single_row CHECK (id = 1)
                    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
                """)
                await conn.commit()
    
    async def _create_ticket_tables(self):
        """創建票券系統相關表格"""
        logger.info("📋 創建票券系統表格...")
        
        tables = {
            'tickets': """
                CREATE TABLE IF NOT EXISTS tickets (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    discord_id VARCHAR(20) NOT NULL COMMENT '開票者 Discord ID',
                    username VARCHAR(100) NOT NULL COMMENT '開票者用戶名',
                    type VARCHAR(50) NOT NULL COMMENT '票券類型',
                    priority ENUM('high', 'medium', 'low') DEFAULT 'medium' COMMENT '優先級',
                    status ENUM('open', 'closed', 'archived') DEFAULT 'open' COMMENT '狀態',
                    channel_id BIGINT NOT NULL COMMENT '頻道 ID',
                    guild_id BIGINT NOT NULL COMMENT '伺服器 ID',
                    assigned_to BIGINT NULL COMMENT '指派的客服 ID',
                    rating INT NULL CHECK (rating BETWEEN 1 AND 5) COMMENT '評分',
                    rating_feedback TEXT NULL COMMENT '評分回饋',
                    tags JSON NULL COMMENT '標籤',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '建立時間',
                    closed_at TIMESTAMP NULL COMMENT '關閉時間',
                    closed_by VARCHAR(20) NULL COMMENT '關閉者 ID',
                    close_reason TEXT NULL COMMENT '關閉原因',
                    last_activity TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '最後活動時間',
                    
                    INDEX idx_guild_status (guild_id, status),
                    INDEX idx_assigned (assigned_to),
                    INDEX idx_created (created_at),
                    INDEX idx_channel (channel_id),
                    INDEX idx_discord_id (discord_id)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            """,
            
            'ticket_settings': """
                CREATE TABLE IF NOT EXISTS ticket_settings (
                    guild_id BIGINT PRIMARY KEY COMMENT '伺服器 ID',
                    category_id BIGINT NULL COMMENT '分類頻道 ID',
                    support_roles JSON NULL COMMENT '客服身分組列表',
                    max_tickets_per_user INT DEFAULT 3 COMMENT '每人最大票券數',
                    auto_close_hours INT DEFAULT 24 COMMENT '自動關閉小時數',
                    sla_response_minutes INT DEFAULT 60 COMMENT 'SLA 回應時間',
                    welcome_message TEXT NULL COMMENT '歡迎訊息',
                    log_channel_id BIGINT NULL COMMENT '日誌頻道 ID',
                    sla_alert_channel_id BIGINT NULL COMMENT 'SLA 警告頻道 ID',
                    auto_assign_enabled BOOLEAN DEFAULT FALSE COMMENT '自動分配啟用',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            """,
            
            'ticket_logs': """
                CREATE TABLE IF NOT EXISTS ticket_logs (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    ticket_id INT NOT NULL COMMENT '票券 ID',
                    action VARCHAR(50) NOT NULL COMMENT '操作類型',
                    details TEXT NULL COMMENT '操作詳情',
                    created_by VARCHAR(20) NULL COMMENT '操作者 ID',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    
                    INDEX idx_ticket (ticket_id),
                    INDEX idx_action (action),
                    INDEX idx_created (created_at)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            """,
            
            'ticket_statistics_cache': """
                CREATE TABLE IF NOT EXISTS ticket_statistics_cache (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    guild_id BIGINT NOT NULL COMMENT '伺服器 ID',
                    cache_key VARCHAR(100) NOT NULL COMMENT '快取鍵',
                    cache_data JSON NOT NULL COMMENT '快取資料',
                    expires_at TIMESTAMP NOT NULL COMMENT '過期時間',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    
                    UNIQUE KEY unique_cache (guild_id, cache_key),
                    INDEX idx_expires (expires_at)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            """,
            
            'ticket_views': """
                CREATE TABLE IF NOT EXISTS ticket_views (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    ticket_id INT NOT NULL COMMENT '票券 ID',
                    user_id VARCHAR(20) NOT NULL COMMENT '查看者 ID',
                    viewed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    
                    INDEX idx_ticket (ticket_id),
                    INDEX idx_user (user_id),
                    INDEX idx_viewed (viewed_at)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            """
        }
        
        await self._create_tables_batch(tables, "票券系統")
    
    async def _create_vote_tables(self):
        """創建投票系統相關表格"""
        logger.info("🗳️ 創建投票系統表格...")
        
        tables = {
            'votes': """
                CREATE TABLE IF NOT EXISTS votes (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    title VARCHAR(255) NOT NULL COMMENT '投票標題',
                    is_multi BOOLEAN DEFAULT FALSE COMMENT '是否多選',
                    anonymous BOOLEAN DEFAULT FALSE COMMENT '是否匿名',
                    allowed_roles JSON NULL COMMENT '允許投票的身分組',
                    channel_id BIGINT NOT NULL COMMENT '頻道 ID',
                    guild_id BIGINT NOT NULL COMMENT '伺服器 ID',
                    creator_id VARCHAR(20) NOT NULL COMMENT '創建者 ID',
                    start_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '開始時間',
                    end_time TIMESTAMP NOT NULL COMMENT '結束時間',
                    announced BOOLEAN DEFAULT FALSE COMMENT '是否已公告結果',
                    is_active BOOLEAN GENERATED ALWAYS AS (end_time > NOW()) STORED COMMENT '是否進行中',
                    
                    INDEX idx_guild_active (guild_id, is_active),
                    INDEX idx_creator (creator_id),
                    INDEX idx_end_time (end_time),
                    INDEX idx_announced (announced)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            """,
            
            'vote_options': """
                CREATE TABLE IF NOT EXISTS vote_options (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    vote_id INT NOT NULL COMMENT '投票 ID',
                    option_text VARCHAR(255) NOT NULL COMMENT '選項文字',
                    option_order INT DEFAULT 0 COMMENT '選項順序',
                    
                    FOREIGN KEY (vote_id) REFERENCES votes(id) ON DELETE CASCADE,
                    INDEX idx_vote (vote_id),
                    INDEX idx_order (vote_id, option_order)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            """,
            
            'vote_responses': """
                CREATE TABLE IF NOT EXISTS vote_responses (
                    vote_id INT NOT NULL COMMENT '投票 ID',
                    user_id BIGINT NOT NULL COMMENT '用戶 ID',
                    option_text VARCHAR(255) NOT NULL COMMENT '選擇的選項',
                    voted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '投票時間',
                    
                    PRIMARY KEY (vote_id, user_id, option_text),
                    FOREIGN KEY (vote_id) REFERENCES votes(id) ON DELETE CASCADE,
                    INDEX idx_user (user_id),
                    INDEX idx_voted (voted_at)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            """
        }
        
        await self._create_tables_batch(tables, "投票系統")
    
    async def _create_tables_batch(self, tables: Dict[str, str], system_name: str):
        """批次創建表格"""
        async with self.db.connection() as conn:
            async with conn.cursor() as cursor:
                for table_name, sql in tables.items():
                    try:
                        await cursor.execute(sql)
                        logger.debug(f"✅ 創建表格：{table_name}")
                    except Exception as e:
                        logger.error(f"❌ 創建表格 {table_name} 失敗：{e}")
                        raise
                
                await conn.commit()
                logger.info(f"✅ {system_name}表格創建完成")
    
    async def check_table_exists(self, table_name: str) -> bool:
        """檢查表格是否存在"""
        async with self.db.connection() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute("""
                    SELECT COUNT(*) FROM information_schema.tables 
                    WHERE table_schema = DATABASE() AND table_name = %s
                """, (table_name,))
                result = await cursor.fetchone()
                return result[0] > 0
    
    async def get_table_info(self, table_name: str) -> Dict:
        """取得表格資訊"""
        async with self.db.connection() as conn:
            async with conn.cursor() as cursor:
                # 檢查表格是否存在
                exists = await self.check_table_exists(table_name)
                if not exists:
                    return {"exists": False}
                
                # 取得行數
                await cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
                row_count = (await cursor.fetchone())[0]
                
                # 取得欄位資訊
                await cursor.execute(f"DESCRIBE {table_name}")
                columns = await cursor.fetchall()
                
                return {
                    "exists": True,
                    "row_count": row_count,
                    "columns": len(columns),
                    "column_details": columns
                }
    
    async def _get_database_version(self) -> str:
        """取得資料庫版本"""
        try:
            async with self.db.connection() as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute("SELECT version FROM database_version WHERE id = 1")
                    result = await cursor.fetchone()
                    return result[0] if result else None
        except:
            return None
    
    async def _update_database_version(self, version: str):
        """更新資料庫版本"""
        async with self.db.connection() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute("""
                    INSERT INTO database_version (id, version) VALUES (1, %s)
                    ON DUPLICATE KEY UPDATE version = %s, updated_at = NOW()
                """, (version, version))
                await conn.commit()
    
    async def _drop_all_tables(self):
        """刪除所有表格（謹慎使用）"""
        tables_to_drop = [
            'vote_responses', 'vote_options', 'votes',
            'ticket_views', 'ticket_statistics_cache', 'ticket_logs', 
            'tickets', 'ticket_settings', 'database_version'
        ]
        
        async with self.db.connection() as conn:
            async with conn.cursor() as cursor:
                # 暫時禁用外鍵檢查
                await cursor.execute("SET FOREIGN_KEY_CHECKS = 0")
                
                for table in tables_to_drop:
                    try:
                        await cursor.execute(f"DROP TABLE IF EXISTS {table}")
                        logger.warning(f"🗑️ 已刪除表格：{table}")
                    except Exception as e:
                        logger.error(f"刪除表格 {table} 失敗：{e}")
                
                # 重新啟用外鍵檢查
                await cursor.execute("SET FOREIGN_KEY_CHECKS = 1")
                await conn.commit()
    
    async def get_system_status(self) -> Dict:
        """取得系統狀態"""
        status = {
            "database_version": await self._get_database_version(),
            "tables": {}
        }
        
        # 檢查主要表格
        important_tables = ['tickets', 'ticket_settings', 'votes', 'vote_options', 'vote_responses']
        
        for table in important_tables:
            status["tables"][table] = await self.get_table_info(table)
        
        return status


# 修改 bot/db/ticket_dao.py - 添加自動初始化
class TicketDAO:
    """票券資料存取層 - 帶自動初始化"""
    
    def __init__(self):
        self.db = db_pool
        self._initialized = False
    
    async def _ensure_initialized(self):
        """確保資料庫已初始化"""
        if not self._initialized:
            try:
                # 檢查主要表格是否存在
                async with self.db.connection() as conn:
                    async with conn.cursor() as cursor:
                        await cursor.execute("""
                            SELECT COUNT(*) FROM information_schema.tables 
                            WHERE table_schema = DATABASE() AND table_name = 'tickets'
                        """)
                        exists = (await cursor.fetchone())[0] > 0
                
                if not exists:
                    logger.warning("📋 檢測到票券表格不存在，開始自動初始化...")
                    from bot.db.database_manager import DatabaseManager
                    db_manager = DatabaseManager()
                    await db_manager.initialize_all_tables()
                
                self._initialized = True
                logger.info("✅ 票券 DAO 初始化完成")
                
            except Exception as e:
                logger.error(f"❌ 票券 DAO 初始化失敗：{e}")
                raise
    
    async def create_ticket(self, discord_id: str, username: str, ticket_type: str, 
                           channel_id: int, guild_id: int, priority: str = 'medium') -> Optional[int]:
        """建立新票券"""
        await self._ensure_initialized()  # 確保初始化
        
        try:
            async with self.db.connection() as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute("""
                        INSERT INTO tickets (discord_id, username, type, priority, channel_id, guild_id)
                        VALUES (%s, %s, %s, %s, %s, %s)
                    """, (discord_id, username, ticket_type, priority, channel_id, guild_id))
                    
                    ticket_id = cursor.lastrowid
                    
                    # 記錄操作日誌
                    await cursor.execute("""
                        INSERT INTO ticket_logs (ticket_id, action, details, created_by)
                        VALUES (%s, 'created', %s, %s)
                    """, (ticket_id, f"建立{ticket_type}票券", discord_id))
                    
                    await conn.commit()
                    logger.info(f"建立票券 #{ticket_id:04d} - 用戶: {username}")
                    return ticket_id
                    
        except Exception as e:
            logger.error(f"建立票券錯誤：{e}")
            return None
    
    # 添加缺少的方法
    async def get_guild_settings(self, guild_id: int) -> Dict[str, Any]:
        """取得伺服器設定（別名方法）"""
        return await self.get_settings(guild_id)
    
    async def cleanup_old_logs(self, days: int = 30) -> int:
        """清理舊日誌"""
        return await self.cleanup_old_data(days)
    
    @property
    def db_pool(self):
        """資料庫連接池屬性"""
        return self.db
    
    # 其他現有方法保持不變...


# 修改 bot/db/vote_dao.py - 添加自動初始化
_vote_initialized = False

async def _ensure_vote_tables():
    """確保投票表格存在"""
    global _vote_initialized
    if not _vote_initialized:
        try:
            # 檢查投票表格是否存在
            async with db_pool.connection() as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute("""
                        SELECT COUNT(*) FROM information_schema.tables 
                        WHERE table_schema = DATABASE() AND table_name = 'votes'
                    """)
                    exists = (await cursor.fetchone())[0] > 0
            
            if not exists:
                logger.warning("🗳️ 檢測到投票表格不存在，開始自動初始化...")
                from bot.db.database_manager import DatabaseManager
                db_manager = DatabaseManager()
                await db_manager.initialize_all_tables()
            
            _vote_initialized = True
            logger.info("✅ 投票 DAO 初始化完成")
            
        except Exception as e:
            logger.error(f"❌ 投票 DAO 初始化失敗：{e}")
            raise

# 修改所有投票相關函數，在開始時調用初始化
async def create_vote(session, creator_id):
    await _ensure_vote_tables()  # 確保表格存在
    
    try:
        async with db_pool.connection() as conn:
            async with conn.cursor() as cur:
                print(f"[DEBUG] 準備插入投票：{session['title']}")
                await cur.execute("""
                    INSERT INTO votes (title, is_multi, anonymous, allowed_roles, channel_id, guild_id, creator_id, end_time, start_time)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    session['title'],
                    bool(session['is_multi']),
                    bool(session['anonymous']),
                    json.dumps(session['allowed_roles']),
                    session['origin_channel'].id,
                    session['guild_id'],
                    str(creator_id),
                    session['end_time'],
                    session['start_time']
                ))
                await conn.commit()
                vote_id = cur.lastrowid
                print(f"[DEBUG] 投票插入成功，ID：{vote_id}")
                return vote_id
    except Exception as e:
        print(f"[ERROR] create_vote 失敗：{e}")
        raise
