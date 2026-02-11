# bot/db/database_manager.py - 新建檔案
"""
資料庫管理器 - 自動初始化和遷移
統一管理所有資料表的創建和更新
"""

from typing import Any, Dict, Optional

from potato_bot.db.pool import db_pool
from potato_shared.logger import logger


class DatabaseManager:
    """資料庫管理器 - 負責資料表初始化和遷移"""

    def __init__(self):
        self.db = db_pool
        self.current_version = "1.0.5"
        self._initialized = False

    async def initialize_all_tables(self, force_recreate: bool = False):
        """初始化所有資料表"""
        if self._initialized and not force_recreate:
            logger.info("資料庫已初始化，跳過重複初始化")
            return

        logger.info("🔄 開始初始化資料庫表格...")
        try:
            # 創建版本管理表
            await self._create_version_table()

            # 檢查資料庫版本
            db_version = await self._get_database_version()

            if db_version == self.current_version and not force_recreate:
                self._initialized = True
                logger.info("✅ 資料庫版本一致，跳過資料表初始化")
                return

            if force_recreate:
                logger.warning("⚠️ 強制重建模式 - 將刪除所有現存表格")
                await self._drop_all_tables()

            # 移除已停用的娛樂系統資料表（若存在）
            await self._drop_entertainment_tables()

            # 創建各系統的表格
            await self._create_ticket_tables()
            await self._create_vote_tables()
            await self._create_welcome_tables()
            await self._create_system_settings_table()
            await self._create_resume_tables()
            await self._create_whitelist_tables()
            await self._create_whitelist_interview_tables()
            await self._create_lottery_tables()
            await self._create_music_tables()
            await self._create_fivem_tables()
            await self._create_auto_reply_tables()
            await self._create_category_auto_tables()
            await self._create_webhook_tables()
            await self._create_cleanup_tables()

            # 更新資料庫版本
            await self._update_database_version(self.current_version)

            self._initialized = True
            logger.info("✅ 資料庫表格初始化完成")

        except Exception as e:
            logger.error(f"❌ 資料庫初始化失敗：{e}")
            raise


    async def _create_version_table(self):
        """創建版本管理表"""
        async with self.db.connection() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS database_version (
                        id INT PRIMARY KEY DEFAULT 1,
                        version VARCHAR(20) NOT NULL,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                        CONSTRAINT single_row CHECK (id = 1)
                    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
                """
                )
                await conn.commit()

    async def _get_database_version(self) -> Optional[str]:
        """獲取當前資料庫版本"""
        try:
            async with self.db.connection() as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute("SELECT version FROM database_version WHERE id = 1")
                    result = await cursor.fetchone()
                    return result[0] if result else None
        except Exception as e:
            logger.debug(f"獲取資料庫版本失敗（可能是第一次初始化）: {e}")
            return None

    async def _update_database_version(self, version: str):
        """更新資料庫版本"""
        try:
            async with self.db.connection() as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute(
                        """
                        INSERT INTO database_version (id, version)
                        VALUES (1, %s)
                        ON DUPLICATE KEY UPDATE version = %s, updated_at = CURRENT_TIMESTAMP
                        """,
                        (version, version),
                    )
                    await conn.commit()
                    logger.info(f"✅ 資料庫版本已更新至 {version}")
        except Exception as e:
            logger.error(f"❌ 更新資料庫版本失敗: {e}")
            raise

    async def _drop_all_tables(self):
        """刪除所有表格（強制重建時使用）"""
        logger.warning("⚠️ 開始刪除所有表格...")
        try:
            async with self.db.connection() as conn:
                async with conn.cursor() as cursor:
                    # 取得所有表格名稱
                    await cursor.execute(
                        """
                        SELECT table_name
                        FROM information_schema.tables
                        WHERE table_schema = DATABASE()
                        AND table_type = 'BASE TABLE'
                        """
                    )
                    tables = await cursor.fetchall()

                    # 停用外鍵檢查
                    await cursor.execute("SET FOREIGN_KEY_CHECKS = 0")

                    # 刪除所有表格
                    for (table_name,) in tables:
                        try:
                            await cursor.execute(f"DROP TABLE IF EXISTS {table_name}")
                            logger.debug(f"已刪除表格: {table_name}")
                        except Exception as e:
                            logger.error(f"刪除表格 {table_name} 失敗: {e}")

                    # 重新啟用外鍵檢查
                    await cursor.execute("SET FOREIGN_KEY_CHECKS = 1")
                    await conn.commit()

                    logger.info(f"✅ 已刪除 {len(tables)} 個表格")
        except Exception as e:
            logger.error(f"❌ 刪除表格失敗: {e}")
            raise

    async def _drop_entertainment_tables(self):
        """移除娛樂系統相關表格（若存在）"""
        logger.info("🧹 檢查娛樂系統資料表...")
        try:
            async with self.db.connection() as conn:
                async with conn.cursor() as cursor:
                    patterns = ["entertainment_%", "game_%"]
                    tables_to_drop: list[str] = []

                    for pattern in patterns:
                        await cursor.execute(
                            """
                            SELECT table_name
                            FROM information_schema.tables
                            WHERE table_schema = DATABASE()
                              AND table_name LIKE %s
                            """,
                            (pattern,),
                        )
                        rows = await cursor.fetchall()
                        tables_to_drop.extend([row[0] for row in rows])

                    for table_name in sorted(set(tables_to_drop)):
                        await cursor.execute(f"DROP TABLE IF EXISTS `{table_name}`")
                        logger.info(f"✅ 已移除娛樂資料表：{table_name}")

                    await conn.commit()
        except Exception as e:
            logger.error(f"❌ 移除娛樂資料表失敗: {e}")

    async def _create_music_tables(self):
        """創建音樂系統相關表格"""
        logger.info("🎵 創建音樂系統表格...")
        tables = {
            "music_settings": """
                CREATE TABLE IF NOT EXISTS music_settings (
                    guild_id BIGINT PRIMARY KEY COMMENT '伺服器ID',
                    allowed_role_ids JSON NULL COMMENT '允許使用音樂系統的身分組',
                    require_role_to_use BOOLEAN DEFAULT FALSE COMMENT '是否需要角色才能使用',
                    lavalink_host TEXT NULL COMMENT 'Lavalink 主機',
                    lavalink_port INT NULL COMMENT 'Lavalink 連接埠',
                    lavalink_password TEXT NULL COMMENT 'Lavalink 密碼',
                    lavalink_secure BOOLEAN DEFAULT FALSE COMMENT 'Lavalink HTTPS',
                    lavalink_uri TEXT NULL COMMENT 'Lavalink URI',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '創建時間',
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新時間'
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            """,
        }

        await self._create_tables_batch(tables, "音樂系統")

    async def _create_fivem_tables(self):
        """創建 FiveM 狀態設定表格"""
        logger.info("🛰️ 創建 FiveM 狀態設定表格...")
        tables = {
            "fivem_settings": """
                CREATE TABLE IF NOT EXISTS fivem_settings (
                    guild_id BIGINT PRIMARY KEY COMMENT '伺服器ID',
                    info_url TEXT NULL COMMENT 'info.json URL',
                    players_url TEXT NULL COMMENT 'players.json URL',
                    status_channel_id BIGINT NULL COMMENT '播報頻道ID',
                    alert_role_ids JSON NULL COMMENT '異常通知身分組',
                    dm_role_ids JSON NULL COMMENT 'DM 通知身分組',
                    panel_message_id BIGINT NULL COMMENT '狀態面板訊息ID',
                    poll_interval INT NULL COMMENT '輪詢間隔(秒)',
                    starting_timeout INT NULL COMMENT '啟動超時(秒)',
                    maintenance_mode BOOLEAN NOT NULL DEFAULT FALSE COMMENT '維修模式',
                    server_link TEXT NULL COMMENT '伺服器連結',
                    status_image_url TEXT NULL COMMENT '狀態面板圖片',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '創建時間',
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新時間'
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            """,
        }

        await self._create_tables_batch(tables, "FiveM 狀態")

    async def get_system_status(self) -> Dict[str, Any]:
        """獲取系統狀態"""
        try:
            async with self.db.connection() as conn:
                async with conn.cursor() as cursor:
                    # 獲取資料庫版本
                    version = await self._get_database_version()

                    # 獲取表格數量
                    await cursor.execute(
                        """
                        SELECT COUNT(*) as table_count
                        FROM information_schema.tables
                        WHERE table_schema = DATABASE()
                        """
                    )
                    result = await cursor.fetchone()
                    table_count = result[0] if result else 0

                    return {
                        "database_version": version or "未知",
                        "current_version": self.current_version,
                        "tables": {
                            "count": table_count,
                            "initialized": self._initialized,
                        },
                        "status": ("healthy" if self._initialized else "initializing"),
                    }
        except Exception as e:
            logger.error(f"獲取系統狀態失敗: {e}")
            return {
                "database_version": "錯誤",
                "current_version": self.current_version,
                "tables": {"count": 0, "initialized": False},
                "status": "error",
                "error": str(e),
            }

    async def _create_ticket_tables(self):
        """創建票券系統相關表格"""
        logger.info("📋 創建票券系統表格...")

        tables = {
            "tickets": """
                CREATE TABLE IF NOT EXISTS tickets (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    discord_id VARCHAR(20) NOT NULL COMMENT '開票者 Discord ID',
                    username VARCHAR(100) NOT NULL COMMENT '開票者用戶名',
                    discord_username VARCHAR(100) NOT NULL COMMENT '開票者 Discord 用戶名',
                    type VARCHAR(50) NOT NULL COMMENT '票券類型',
                    priority ENUM('urgent', 'high', 'medium', 'low') DEFAULT 'medium' COMMENT '優先級',
                    status ENUM('open', 'in_progress', 'pending', 'resolved', 'closed', 'archived') DEFAULT 'open' COMMENT '狀態',
                    channel_id BIGINT NOT NULL COMMENT '頻道 ID',
                    guild_id BIGINT NOT NULL COMMENT '伺服器 ID',
                    tags JSON NULL COMMENT '標籤',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '建立時間',
                    closed_at TIMESTAMP NULL COMMENT '關閉時間',
                    closed_by VARCHAR(20) NULL COMMENT '關閉者 ID',
                    close_reason TEXT NULL COMMENT '關閉原因',
                    last_activity TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '最後活動時間',

                    INDEX idx_guild_status (guild_id, status),
                    INDEX idx_created (created_at),
                    INDEX idx_channel (channel_id),
                    INDEX idx_discord_id (discord_id)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            """,
            "ticket_settings": """
                CREATE TABLE IF NOT EXISTS ticket_settings (
                    guild_id BIGINT PRIMARY KEY COMMENT '伺服器 ID',
                    category_id BIGINT NULL COMMENT '分類頻道 ID',
                    support_roles JSON NULL COMMENT '客服身分組列表',
                    sponsor_support_roles JSON NULL COMMENT '贊助處理身分組列表',
                    max_tickets_per_user INT DEFAULT 3 COMMENT '每人最大票券數',
                    auto_close_hours INT DEFAULT 24 COMMENT '自動關閉小時數',
                    welcome_message TEXT NULL COMMENT '歡迎訊息',
                    log_channel_id BIGINT NULL COMMENT '日誌頻道 ID',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            """,
            "ticket_logs": """
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
            "ticket_messages": """
                CREATE TABLE IF NOT EXISTS ticket_messages (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    ticket_id INT NOT NULL COMMENT '票券 ID',
                    message_id BIGINT NOT NULL COMMENT 'Discord 訊息 ID',
                    author_id BIGINT NOT NULL COMMENT '發送者 Discord ID',
                    author_name VARCHAR(100) NOT NULL COMMENT '發送者名稱',
                    content TEXT COMMENT '訊息內容',
                    attachments JSON COMMENT '附件資訊',
                    message_type ENUM('user', 'staff', 'system', 'bot') DEFAULT 'user' COMMENT '訊息類型',
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '訊息時間',
                    edited_timestamp TIMESTAMP NULL COMMENT '編輯時間',
                    reply_to BIGINT NULL COMMENT '回覆的訊息 ID',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '建立時間',

                    INDEX idx_ticket_id (ticket_id),
                    INDEX idx_message_id (message_id),
                    INDEX idx_timestamp (timestamp),
                    FOREIGN KEY (ticket_id) REFERENCES tickets(id) ON DELETE CASCADE
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            """,
            "ticket_transcripts": """
                CREATE TABLE IF NOT EXISTS ticket_transcripts (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    ticket_id INT NOT NULL COMMENT '票券 ID',
                    transcript_html LONGTEXT COMMENT 'HTML 格式記錄',
                    transcript_text LONGTEXT COMMENT '純文字記錄',
                    transcript_json LONGTEXT COMMENT 'JSON 格式記錄',
                    message_count INT DEFAULT 0 COMMENT '訊息數量',
                    file_path VARCHAR(500) COMMENT '檔案路徑',
                    file_size BIGINT DEFAULT 0 COMMENT '檔案大小',
                    export_format VARCHAR(20) DEFAULT 'html' COMMENT '匯出格式',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '建立時間',

                    UNIQUE KEY unique_ticket_transcript (ticket_id),
                    FOREIGN KEY (ticket_id) REFERENCES tickets(id) ON DELETE CASCADE
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            """,
        }

        await self._create_tables_batch(tables, "票券系統")

    async def _create_vote_tables(self):
        """創建投票系統相關表格"""
        logger.info("🗳️ 創建投票系統表格...")

        tables = {
            "votes": """
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

                    INDEX idx_guild_active (guild_id),
                    INDEX idx_creator (creator_id),
                    INDEX idx_end_time (end_time),
                    INDEX idx_announced (announced)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            """,
            "vote_options": """
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
            "vote_responses": """
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
            """,
            "vote_settings": """
                CREATE TABLE IF NOT EXISTS vote_settings (
                    guild_id BIGINT PRIMARY KEY COMMENT '伺服器 ID',
                    default_vote_channel_id BIGINT NULL COMMENT '預設投票頻道 ID',
                    announcement_channel_id BIGINT NULL COMMENT '投票結果公告頻道 ID',
                    max_vote_duration_hours INT DEFAULT 72 COMMENT '最大投票時長(小時)',
                    min_vote_duration_minutes INT DEFAULT 60 COMMENT '最小投票時長(分鐘)',
                    require_role_to_create BOOLEAN DEFAULT FALSE COMMENT '是否需要角色才能建立投票',
                    allowed_creator_roles JSON NULL COMMENT '允許建立投票的角色列表',
                    auto_announce_results BOOLEAN DEFAULT TRUE COMMENT '是否自動公告結果',
                    allow_anonymous_votes BOOLEAN DEFAULT TRUE COMMENT '是否允許匿名投票',
                    allow_multi_choice BOOLEAN DEFAULT TRUE COMMENT '是否允許多選投票',
                    is_enabled BOOLEAN DEFAULT TRUE COMMENT '投票系統是否啟用',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '建立時間',
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新時間',

                    INDEX idx_default_channel (default_vote_channel_id),
                    INDEX idx_announcement_channel (announcement_channel_id),
                    INDEX idx_enabled (is_enabled)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            """,
        }

        await self._create_tables_batch(tables, "投票系統")

    async def _create_tables_batch(self, tables: Dict[str, str], system_name: str):
        """批次創建表格"""
        success_count = 0
        try:
            async with self.db.connection() as conn:
                async with conn.cursor() as cursor:
                    for table_name, sql in tables.items():
                        try:
                            await cursor.execute(sql)
                            logger.debug(f"✅ 表格 {table_name} 創建成功")
                            success_count += 1
                        except Exception as table_error:
                            logger.error(f"❌ 創建表格 {table_name} 失敗: {table_error}")

                    await conn.commit()
                    logger.info(f"🎯 {system_name} 表格批次創建完成: {success_count}/{len(tables)}")

        except Exception as e:
            logger.error(f"❌ {system_name} 資料庫批次操作失敗: {e}")

        return success_count

    async def _create_welcome_tables(self):
        """創建歡迎系統相關表格"""
        logger.info("🎉 創建歡迎系統表格...")

        tables = {
            "welcome_settings": """
                CREATE TABLE IF NOT EXISTS welcome_settings (
                    guild_id BIGINT PRIMARY KEY COMMENT '伺服器 ID',
                    welcome_channel_id BIGINT NULL COMMENT '歡迎頻道 ID',
                    leave_channel_id BIGINT NULL COMMENT '離開頻道 ID',
                    welcome_message TEXT NULL COMMENT '歡迎訊息',
                    leave_message TEXT NULL COMMENT '離開訊息',
                    welcome_embed_enabled BOOLEAN DEFAULT TRUE COMMENT '啟用嵌入式歡迎訊息',
                    welcome_dm_enabled BOOLEAN DEFAULT FALSE COMMENT '啟用私訊歡迎',
                    welcome_dm_message TEXT NULL COMMENT '私訊歡迎訊息',
                    auto_role_enabled BOOLEAN DEFAULT FALSE COMMENT '啟用自動角色指派',
                    auto_roles JSON NULL COMMENT '自動指派的角色列表',
                    welcome_image_url VARCHAR(500) NULL COMMENT '歡迎圖片 URL',
                    welcome_thumbnail_url VARCHAR(500) NULL COMMENT '歡迎縮圖 URL',
                    welcome_color VARCHAR(7) DEFAULT '#2ecc71' COMMENT '歡迎訊息顏色',
                    is_enabled BOOLEAN DEFAULT TRUE COMMENT '是否啟用歡迎系統',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '創建時間',
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新時間',

                    INDEX idx_welcome_channel (welcome_channel_id),
                    INDEX idx_leave_channel (leave_channel_id),
                    INDEX idx_enabled (is_enabled)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            """,
            "welcome_logs": """
                CREATE TABLE IF NOT EXISTS welcome_logs (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    guild_id BIGINT NOT NULL COMMENT '伺服器 ID',
                    user_id BIGINT NOT NULL COMMENT '用戶 ID',
                    username VARCHAR(100) NOT NULL COMMENT '用戶名稱',
                    event_type ENUM('member_join', 'member_leave') NOT NULL COMMENT '事件類型',
                    welcome_sent BOOLEAN DEFAULT FALSE COMMENT '是否已發送歡迎訊息',
                    dm_sent BOOLEAN DEFAULT FALSE COMMENT '是否已發送私訊',
                    roles_assigned JSON NULL COMMENT '已指派的角色',
                    error_message TEXT NULL COMMENT '錯誤訊息',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '事件時間',

                    INDEX idx_guild_user (guild_id, user_id),
                    INDEX idx_event_type (event_type),
                    INDEX idx_created_at (created_at)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            """,
        }

        await self._create_tables_batch(tables, "歡迎系統")

    async def _create_system_settings_table(self):
        """創建 system_settings 表格"""
        logger.info("🛠️ 創建 system_settings 表格...")
        tables = {
            "system_settings": """
                CREATE TABLE IF NOT EXISTS system_settings (
                    guild_id BIGINT PRIMARY KEY COMMENT '伺服器ID',
                    general_settings JSON NULL COMMENT '一般設定',
                    channel_settings JSON NULL COMMENT '頻道設定',
                    role_settings JSON NULL COMMENT '角色設定',
                    notification_settings JSON NULL COMMENT '通知設定',
                    feature_toggles JSON NULL COMMENT '功能開關',
                    custom_settings JSON NULL COMMENT '自定義設定',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '創建時間',
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新時間'
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            """,
        }
        await self._create_tables_batch(tables, "system_settings")

    async def _create_resume_tables(self):
        """創建履歷系統相關表格"""
        logger.info("🧾 創建履歷系統表格...")

        tables = {
            "resume_companies": """
                CREATE TABLE IF NOT EXISTS resume_companies (
                    id BIGINT AUTO_INCREMENT PRIMARY KEY,
                    guild_id BIGINT NOT NULL,
                    company_name VARCHAR(100) NOT NULL,
                    panel_channel_id BIGINT NULL,
                    review_channel_id BIGINT NULL,
                    review_role_ids JSON NULL,
                    approved_role_ids JSON NULL,
                    manageable_role_ids JSON NULL,
                    panel_message_id BIGINT NULL,
                    is_enabled BOOLEAN DEFAULT TRUE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

                    UNIQUE KEY uniq_guild_company (guild_id, company_name),
                    INDEX idx_guild (guild_id)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            """,
            "resume_applications": """
                CREATE TABLE IF NOT EXISTS resume_applications (
                    id BIGINT AUTO_INCREMENT PRIMARY KEY,
                    guild_id BIGINT NOT NULL,
                    company_id BIGINT NOT NULL,
                    user_id BIGINT NOT NULL,
                    username VARCHAR(255),
                    answers_json JSON,
                    status VARCHAR(20) DEFAULT 'PENDING',
                    reviewer_id BIGINT NULL,
                    reviewer_note TEXT NULL,
                    review_message_id BIGINT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    reviewed_at TIMESTAMP NULL,

                    INDEX idx_guild_user_status (guild_id, user_id, status),
                    INDEX idx_company_status (company_id, status),
                    FOREIGN KEY (company_id) REFERENCES resume_companies(id) ON DELETE CASCADE
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            """,
        }

        await self._create_tables_batch(tables, "履歷系統")

    async def _create_whitelist_tables(self):
        """創建入境審核相關表格"""
        logger.info("🛂 創建入境審核表格...")

        tables = {
            "whitelist_applications": """
                CREATE TABLE IF NOT EXISTS whitelist_applications (
                    id BIGINT AUTO_INCREMENT PRIMARY KEY,
                    guild_id BIGINT NOT NULL,
                    user_id BIGINT NOT NULL,
                    username VARCHAR(255),
                    answers_json JSON,
                    status VARCHAR(20) DEFAULT 'PENDING',
                    reviewer_id BIGINT NULL,
                    reviewer_note TEXT NULL,
                    review_message_id BIGINT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    reviewed_at TIMESTAMP NULL,

                    INDEX idx_guild_user_status (guild_id, user_id, status),
                    INDEX idx_status (status)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            """,
            "whitelist_settings": """
                CREATE TABLE IF NOT EXISTS whitelist_settings (
                    guild_id BIGINT PRIMARY KEY,
                    panel_channel_id BIGINT NULL,
                    review_channel_id BIGINT NULL,
                    result_channel_id BIGINT NULL,
                    role_newcomer_ids JSON NULL,
                    role_citizen_id BIGINT NULL,
                    role_staff_id BIGINT NULL,
                    nickname_role_id BIGINT NULL,
                    nickname_prefix VARCHAR(32) NULL,
                    panel_message_id BIGINT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            """,
        }

        await self._create_tables_batch(tables, "入境審核")

    async def _create_whitelist_interview_tables(self):
        """創建入境語音面試相關表格"""
        logger.info("🎙️ 創建入境語音面試表格...")

        tables = {
            "whitelist_interview_settings": """
                CREATE TABLE IF NOT EXISTS whitelist_interview_settings (
                    guild_id BIGINT PRIMARY KEY,
                    waiting_channel_id BIGINT NULL,
                    interview_channel_id BIGINT NULL,
                    notify_channel_id BIGINT NULL,
                    staff_role_id BIGINT NULL,
                    timezone VARCHAR(64) NOT NULL DEFAULT 'Asia/Taipei',
                    session_start_hour TINYINT NOT NULL DEFAULT 19,
                    session_end_hour TINYINT NOT NULL DEFAULT 23,
                    is_enabled BOOLEAN DEFAULT FALSE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            """,
            "whitelist_interview_counters": """
                CREATE TABLE IF NOT EXISTS whitelist_interview_counters (
                    guild_id BIGINT NOT NULL,
                    queue_date DATE NOT NULL,
                    next_number INT NOT NULL DEFAULT 1,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                    PRIMARY KEY (guild_id, queue_date)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            """,
            "whitelist_interview_queue": """
                CREATE TABLE IF NOT EXISTS whitelist_interview_queue (
                    id BIGINT AUTO_INCREMENT PRIMARY KEY,
                    guild_id BIGINT NOT NULL,
                    user_id BIGINT NOT NULL,
                    username VARCHAR(255) NULL,
                    original_nickname VARCHAR(255) NULL,
                    queue_date DATE NOT NULL,
                    queue_number INT NOT NULL,
                    status VARCHAR(20) NOT NULL DEFAULT 'WAITING',
                    notified_message_id BIGINT NULL,
                    called_at TIMESTAMP NULL,
                    done_at TIMESTAMP NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

                    UNIQUE KEY uniq_guild_user_date (guild_id, user_id, queue_date),
                    UNIQUE KEY uniq_guild_date_number (guild_id, queue_date, queue_number),
                    INDEX idx_guild_date_status (guild_id, queue_date, status),
                    INDEX idx_guild_date_number (guild_id, queue_date, queue_number)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            """,
        }

        await self._create_tables_batch(tables, "入境語音面試")

    async def _create_lottery_tables(self):
        """創建抽獎系統相關表格"""
        logger.info("🎲 創建抽獎系統表格...")

        tables = {
            "lotteries": """
                CREATE TABLE IF NOT EXISTS lotteries (
                    id INT AUTO_INCREMENT PRIMARY KEY COMMENT '抽獎ID',
                    guild_id BIGINT NOT NULL COMMENT '伺服器ID',
                    name VARCHAR(255) NOT NULL COMMENT '抽獎名稱',
                    description TEXT NULL COMMENT '抽獎描述',
                    creator_id BIGINT NOT NULL COMMENT '創建者ID',
                    channel_id BIGINT NOT NULL COMMENT '抽獎頻道ID',
                    message_id BIGINT NULL COMMENT '抽獎訊息ID',

                    prize_type ENUM('role', 'item', 'custom') DEFAULT 'custom' COMMENT '獎品類型',
                    prize_data JSON NULL COMMENT '獎品資料',
                    winner_count INT DEFAULT 1 COMMENT '中獎人數',

                    entry_method ENUM('reaction', 'command', 'both') DEFAULT 'reaction' COMMENT '參與方式',
                    required_roles JSON NULL COMMENT '參與所需角色',
                    excluded_roles JSON NULL COMMENT '排除的角色',
                    min_account_age_days INT DEFAULT 0 COMMENT '最小帳號年齡(天)',
                    min_server_join_days INT DEFAULT 0 COMMENT '最小加入伺服器天數',

                    start_time TIMESTAMP NOT NULL COMMENT '開始時間',
                    end_time TIMESTAMP NOT NULL COMMENT '結束時間',
                    status ENUM('pending', 'active', 'ended', 'cancelled') DEFAULT 'pending' COMMENT '狀態',
                    auto_end BOOLEAN DEFAULT TRUE COMMENT '自動結束',

                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '創建時間',
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新時間',

                    INDEX idx_guild_status (guild_id, status),
                    INDEX idx_creator (creator_id),
                    INDEX idx_end_time (end_time),
                    INDEX idx_channel (channel_id)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            """,
            "lottery_entries": """
                CREATE TABLE IF NOT EXISTS lottery_entries (
                    id INT AUTO_INCREMENT PRIMARY KEY COMMENT '參賽ID',
                    lottery_id INT NOT NULL COMMENT '抽獎ID',
                    user_id BIGINT NOT NULL COMMENT '用戶ID',
                    username VARCHAR(100) NOT NULL COMMENT '用戶名稱',
                    entry_method ENUM('reaction', 'command') NOT NULL COMMENT '參與方式',
                    entry_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '參與時間',
                    is_valid BOOLEAN DEFAULT TRUE COMMENT '是否有效',
                    validation_notes TEXT NULL COMMENT '驗證備註',

                    UNIQUE KEY unique_entry (lottery_id, user_id),
                    FOREIGN KEY (lottery_id) REFERENCES lotteries(id) ON DELETE CASCADE,
                    INDEX idx_lottery (lottery_id),
                    INDEX idx_user (user_id),
                    INDEX idx_entry_time (entry_time)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            """,
            "lottery_winners": """
                CREATE TABLE IF NOT EXISTS lottery_winners (
                    id INT AUTO_INCREMENT PRIMARY KEY COMMENT '中獎ID',
                    lottery_id INT NOT NULL COMMENT '抽獎ID',
                    user_id BIGINT NOT NULL COMMENT '中獎用戶ID',
                    username VARCHAR(100) NOT NULL COMMENT '中獎用戶名稱',
                    prize_data JSON NULL COMMENT '獎品資料',
                    win_position INT NOT NULL COMMENT '中獎順位',
                    selected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '選中時間',
                    claimed_at TIMESTAMP NULL COMMENT '領取時間',
                    claim_status ENUM('pending', 'claimed', 'expired') DEFAULT 'pending' COMMENT '領取狀態',
                    claim_notes TEXT NULL COMMENT '領取備註',

                    FOREIGN KEY (lottery_id) REFERENCES lotteries(id) ON DELETE CASCADE,
                    INDEX idx_lottery (lottery_id),
                    INDEX idx_user (user_id),
                    INDEX idx_claim_status (claim_status)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            """,
            "lottery_settings": """
                CREATE TABLE IF NOT EXISTS lottery_settings (
                    guild_id BIGINT PRIMARY KEY COMMENT '伺服器ID',
                    default_duration_hours INT DEFAULT 24 COMMENT '預設抽獎時長(小時)',
                    max_concurrent_lotteries INT DEFAULT 3 COMMENT '最大同時抽獎數',
                    allow_self_entry BOOLEAN DEFAULT TRUE COMMENT '允許自己參與抽獎',
                    require_boost BOOLEAN DEFAULT FALSE COMMENT '需要加速才能參與',
                    log_channel_id BIGINT NULL COMMENT '日誌頻道ID',
                    announcement_channel_id BIGINT NULL COMMENT '公告頻道ID',
                    admin_roles JSON NULL COMMENT '管理員角色',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '創建時間',
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新時間'
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            """,
        }

        async with self.db.connection() as conn:
            async with conn.cursor() as cursor:
                for table_name, create_sql in tables.items():
                    try:
                        await cursor.execute(create_sql)
                        logger.info(f"✅ {table_name} 表格創建成功")
                    except Exception as e:
                        logger.error(f"❌ 創建 {table_name} 表格失敗: {e}")
                        raise
                await conn.commit()
                logger.info("✅ 抽獎系統表格創建完成")

    async def _create_auto_reply_tables(self):
        """創建自動回覆相關表格"""
        logger.info("💬 創建自動回覆表格...")

        tables = {
            "mention_auto_replies": """
                CREATE TABLE IF NOT EXISTS mention_auto_replies (
                    id BIGINT AUTO_INCREMENT PRIMARY KEY,
                    guild_id BIGINT NOT NULL,
                    target_user_id BIGINT NOT NULL,
                    reply_text VARCHAR(500) NOT NULL,
                    created_by BIGINT NULL,
                    updated_by BIGINT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

                    UNIQUE KEY uniq_guild_target (guild_id, target_user_id),
                    INDEX idx_guild (guild_id)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            """,
        }

        await self._create_tables_batch(tables, "自動回覆")

    async def _create_category_auto_tables(self):
        """創建類別自動建立相關表格"""
        logger.info("🗂️ 創建類別自動建立表格...")

        tables = {
            "category_auto_settings": """
                CREATE TABLE IF NOT EXISTS category_auto_settings (
                    guild_id BIGINT PRIMARY KEY COMMENT '伺服器 ID',
                    allowed_role_ids JSON NULL COMMENT '可使用身分組',
                    manager_role_ids JSON NULL COMMENT '預設管理身分組',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            """,
        }

        await self._create_tables_batch(tables, "類別自動建立")

    async def _create_webhook_tables(self):
        """創建 Webhook 相關表格"""
        logger.info("🔗 創建 Webhook 表格...")
        tables = {
            "webhooks": """
                CREATE TABLE IF NOT EXISTS webhooks (
                    id VARCHAR(32) PRIMARY KEY,
                    name VARCHAR(255) NOT NULL,
                    url TEXT NOT NULL,
                    type ENUM('incoming', 'outgoing', 'both') NOT NULL DEFAULT 'outgoing',
                    events JSON NOT NULL,
                    secret VARCHAR(64) NULL,
                    headers JSON NULL,
                    timeout INT DEFAULT 30,
                    retry_count INT DEFAULT 3,
                    retry_interval INT DEFAULT 5,
                    status ENUM('active', 'inactive', 'paused', 'error') DEFAULT 'active',
                    guild_id BIGINT NOT NULL,
                    created_by BIGINT DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                    last_triggered TIMESTAMP NULL,
                    success_count INT DEFAULT 0,
                    failure_count INT DEFAULT 0,

                    INDEX idx_guild_id (guild_id),
                    INDEX idx_status (status),
                    INDEX idx_type (type),
                    INDEX idx_created_by (created_by),
                    INDEX idx_last_triggered (last_triggered)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            """,
            "webhook_logs": """
                CREATE TABLE IF NOT EXISTS webhook_logs (
                    id BIGINT AUTO_INCREMENT PRIMARY KEY,
                    webhook_id VARCHAR(32) NOT NULL,
                    event_type VARCHAR(50) NOT NULL,
                    direction ENUM('incoming','outgoing') NOT NULL,
                    payload JSON NOT NULL,
                    response JSON NULL,
                    status ENUM('success', 'failure', 'timeout', 'error') NOT NULL,
                    http_status INT NULL,
                    error_message TEXT NULL,
                    execution_time DECIMAL(8,3) DEFAULT 0.000,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

                    INDEX idx_webhook_id (webhook_id),
                    INDEX idx_event_type (event_type),
                    INDEX idx_direction (direction),
                    INDEX idx_status (status),
                    INDEX idx_created_at (created_at),
                    FOREIGN KEY (webhook_id) REFERENCES webhooks(id) ON DELETE CASCADE
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            """,
            "webhook_statistics": """
                CREATE TABLE IF NOT EXISTS webhook_statistics (
                    id BIGINT AUTO_INCREMENT PRIMARY KEY,
                    webhook_id VARCHAR(32) NOT NULL,
                    date DATE NOT NULL,
                    total_requests INT DEFAULT 0,
                    successful_requests INT DEFAULT 0,
                    failed_requests INT DEFAULT 0,
                    avg_response_time DECIMAL(8,3) DEFAULT 0.000,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                    UNIQUE KEY unique_webhook_date (webhook_id, date),
                    INDEX idx_webhook_id (webhook_id),
                    INDEX idx_date (date),
                    FOREIGN KEY (webhook_id) REFERENCES webhooks(id) ON DELETE CASCADE
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            """,
        }

        async with self.db.connection() as conn:
            async with conn.cursor() as cursor:
                for table_name, create_sql in tables.items():
                    try:
                        await cursor.execute(create_sql)
                        logger.info(f"✅ {table_name} 表格創建成功")
                    except Exception as e:
                        logger.error(f"❌ 創建 {table_name} 表格失敗: {e}")
                        raise
                await conn.commit()
                logger.info("✅ Webhook 表格創建完成")

    async def _create_cleanup_tables(self):
        """創建清理日誌相關表格"""
        logger.info("🧹 創建清理日誌表格...")

        tables = {
            "cleanup_logs": """
                CREATE TABLE IF NOT EXISTS cleanup_logs (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    operation_name VARCHAR(100) NOT NULL,
                    table_name VARCHAR(100) NOT NULL,
                    records_before INT DEFAULT 0,
                    records_after INT DEFAULT 0,
                    deleted_count INT DEFAULT 0,
                    deletion_percentage DECIMAL(5,2) DEFAULT 0.00,
                    success BOOLEAN DEFAULT TRUE,
                    error_message TEXT,
                    cleanup_time DATETIME DEFAULT CURRENT_TIMESTAMP,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            """,
        }

        await self._create_tables_batch(tables, "清理日誌")

# ===== 單例模式實現 =====

_database_manager_instance = None


def get_database_manager() -> DatabaseManager:
    """
    取得資料庫管理器單例
    使用單例模式確保整個應用只有一個DatabaseManager實例
    """
    global _database_manager_instance
    if _database_manager_instance is None:
        _database_manager_instance = DatabaseManager()
    return _database_manager_instance


# ===== 便利函數 =====


async def initialize_database_system():
    """初始化整個資料庫系統的便利函數"""
    try:
        logger.info("🔄 開始初始化資料庫系統...")
        db_manager = get_database_manager()
        await db_manager.initialize_all_tables()
        logger.info("✅ 資料庫系統初始化完成")
        return True
    except Exception as e:
        logger.error(f"❌ 資料庫系統初始化失敗：{e}")
        return False


async def get_database_health() -> Dict[str, Any]:
    """取得資料庫健康狀態"""
    try:
        db_manager = get_database_manager()

        # 檢查連接
        async with db_manager.db.connection() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute("SELECT 1")
                await cursor.fetchone()

        # 取得系統狀態
        status = await db_manager.get_system_status()

        return {
            "status": "healthy",
            "database_version": status.get("database_version"),
            "tables": status.get("tables", {}),
            "connection": "active",
        }

    except Exception as e:
        logger.error(f"資料庫健康檢查失敗：{e}")
        return {"status": "unhealthy", "error": str(e), "connection": "failed"}
