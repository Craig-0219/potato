# bot/db/migrations/guild_management_tables.py - v1.0.0
# 🔐 伺服器管理系統資料庫表格
# Guild Management Database Tables

import logging

from potato_bot.db.pool import db_pool

logger = logging.getLogger(__name__)


async def create_guild_management_tables():
    """創建伺服器管理相關的資料庫表格"""
    try:
        async with db_pool.connection() as conn:
            async with conn.cursor() as cursor:

                # 1. 伺服器資訊表
                logger.info("🏛️ 創建伺服器資訊表格...")

                await cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS guild_info (
                        guild_id BIGINT PRIMARY KEY,
                        guild_name VARCHAR(100) NOT NULL,
                        owner_id BIGINT NOT NULL,
                        member_count INT DEFAULT 0,
                        premium_tier INT DEFAULT 0,
                        features JSON,
                        icon_hash VARCHAR(32),
                        banner_hash VARCHAR(32),
                        description TEXT,
                        preferred_locale VARCHAR(10) DEFAULT 'zh-TW',
                        verification_level ENUM('none', 'low', 'medium', 'high', 'very_high') DEFAULT 'none',
                        mfa_level ENUM('none', 'elevated') DEFAULT 'none',
                        explicit_content_filter ENUM('disabled', 'members_without_roles', 'all_members') DEFAULT 'disabled',

                        # 伺服器狀態
                        status ENUM('active', 'inactive', 'suspended', 'banned') DEFAULT 'active',
                        bot_joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        bot_left_at TIMESTAMP NULL,
                        last_activity TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

                        # 資料保留設定
                        data_retention_days INT DEFAULT 365,
                        privacy_level ENUM('strict', 'normal', 'relaxed') DEFAULT 'normal',

                        # 整合設定
                        allowed_integrations JSON,
                        webhook_settings JSON,
                        api_settings JSON,

                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

                        INDEX idx_owner_id (owner_id),
                        INDEX idx_status (status),
                        INDEX idx_bot_joined (bot_joined_at),
                        INDEX idx_last_activity (last_activity)
                    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
                """
                )

                # 2. 伺服器用戶權限表
                logger.info("👥 創建伺服器用戶權限表格...")

                await cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS guild_user_permissions (
                        id INT AUTO_INCREMENT PRIMARY KEY,
                        user_id BIGINT NOT NULL,
                        guild_id BIGINT NOT NULL,

                        # 角色資訊
                        roles JSON NOT NULL COMMENT '用戶角色列表 ["owner", "admin", "moderator", "staff", "user", "guest"]',
                        direct_permissions JSON COMMENT '直接分配的權限列表',

                        # 權限元資料
                        assigned_by BIGINT NOT NULL,
                        assigned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        expires_at TIMESTAMP NULL,
                        is_active BOOLEAN DEFAULT TRUE,

                        # 限制設定
                        max_tickets INT DEFAULT NULL COMMENT '最大票券數限制',
                        max_votes INT DEFAULT NULL COMMENT '最大投票數限制',
                        rate_limit_overrides JSON COMMENT '速率限制覆蓋設定',

                        # 審計資訊
                        last_permission_change TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                        permission_change_log JSON,

                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

                        UNIQUE KEY unique_user_guild (user_id, guild_id),
                        FOREIGN KEY (guild_id) REFERENCES guild_info(guild_id) ON DELETE CASCADE,
                        INDEX idx_user_id (user_id),
                        INDEX idx_guild_id (guild_id),
                        INDEX idx_active (is_active),
                        INDEX idx_expires (expires_at)
                    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
                """
                )

                # 3. 伺服器設定表
                logger.info("⚙️ 創建伺服器設定表格...")

                await cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS guild_settings (
                        guild_id BIGINT PRIMARY KEY,

                        # 基本設定
                        language VARCHAR(10) DEFAULT 'zh-TW',
                        timezone VARCHAR(50) DEFAULT 'Asia/Taipei',
                        currency VARCHAR(3) DEFAULT 'TWD',

                        # 功能開關
                        modules_enabled JSON DEFAULT ('["ticket", "vote", "welcome", "workflow"]'),
                        features_disabled JSON DEFAULT ('[]'),

                        # 通知設定
                        notification_channels JSON COMMENT '各種通知的頻道設定',
                        alert_settings JSON COMMENT '警告設定',

                        # 安全設定
                        security_level ENUM('low', 'medium', 'high', 'strict') DEFAULT 'medium',
                        require_mfa_for_admin BOOLEAN DEFAULT FALSE,
                        audit_all_actions BOOLEAN DEFAULT TRUE,
                        data_export_enabled BOOLEAN DEFAULT TRUE,
                        cross_channel_access BOOLEAN DEFAULT FALSE,
                        ip_whitelist JSON,

                        # 自動化設定
                        auto_moderation JSON,
                        auto_cleanup_settings JSON,
                        scheduled_tasks JSON,

                        # 整合設定
                        external_integrations JSON,
                        api_keys JSON,
                        webhook_urls JSON,

                        # 客製化設定
                        custom_commands JSON,
                        custom_responses JSON,
                        branding_settings JSON,

                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

                        FOREIGN KEY (guild_id) REFERENCES guild_info(guild_id) ON DELETE CASCADE,
                        INDEX idx_security_level (security_level),
                        INDEX idx_updated (updated_at)
                    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
                """
                )

                # 4. 伺服器統計表
                logger.info("📊 創建伺服器統計表格...")

                await cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS guild_statistics (
                        id INT AUTO_INCREMENT PRIMARY KEY,
                        guild_id BIGINT NOT NULL,
                        date DATE NOT NULL,

                        # 基本統計
                        member_count INT DEFAULT 0,
                        active_members INT DEFAULT 0,
                        new_members INT DEFAULT 0,
                        left_members INT DEFAULT 0,

                        # 功能使用統計
                        tickets_created INT DEFAULT 0,
                        tickets_closed INT DEFAULT 0,
                        votes_created INT DEFAULT 0,
                        votes_participated INT DEFAULT 0,
                        commands_used INT DEFAULT 0,

                        # 參與度統計
                        messages_sent INT DEFAULT 0,
                        voice_minutes INT DEFAULT 0,
                        reactions_added INT DEFAULT 0,

                        # 系統統計
                        api_calls INT DEFAULT 0,
                        webhook_triggers INT DEFAULT 0,
                        errors_occurred INT DEFAULT 0,
                        uptime_minutes INT DEFAULT 0,

                        # 安全統計
                        security_events INT DEFAULT 0,
                        failed_logins INT DEFAULT 0,
                        permission_changes INT DEFAULT 0,

                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

                        UNIQUE KEY unique_guild_date (guild_id, date),
                        FOREIGN KEY (guild_id) REFERENCES guild_info(guild_id) ON DELETE CASCADE,
                        INDEX idx_guild_id (guild_id),
                        INDEX idx_date (date),
                        INDEX idx_created_at (created_at)
                    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
                """
                )

                # 5. 伺服器配額限制表
                logger.info("📏 創建伺服器配額限制表格...")

                await cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS guild_quotas (
                        guild_id BIGINT PRIMARY KEY,

                        # 基本配額
                        max_tickets_per_user INT DEFAULT 5,
                        max_votes_per_user INT DEFAULT 10,
                        max_workflows INT DEFAULT 50,
                        max_webhooks INT DEFAULT 20,
                        max_api_calls_per_day INT DEFAULT 10000,
                        max_storage_mb INT DEFAULT 100,

                        # 進階配額
                        max_custom_commands INT DEFAULT 20,
                        max_scheduled_tasks INT DEFAULT 10,
                        max_integrations INT DEFAULT 5,
                        max_audit_retention_days INT DEFAULT 30,

                        # 速率限制
                        commands_per_minute INT DEFAULT 60,
                        api_calls_per_minute INT DEFAULT 100,
                        webhook_calls_per_minute INT DEFAULT 30,

                        # 計費資訊
                        plan_type ENUM('free', 'basic', 'premium', 'enterprise') DEFAULT 'free',
                        billing_cycle_start DATE,
                        billing_cycle_end DATE,
                        overage_alerts_enabled BOOLEAN DEFAULT TRUE,

                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

                        FOREIGN KEY (guild_id) REFERENCES guild_info(guild_id) ON DELETE CASCADE,
                        INDEX idx_plan_type (plan_type),
                        INDEX idx_billing_cycle (billing_cycle_start, billing_cycle_end)
                    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
                """
                )

                # 6. 伺服器事件日誌表
                logger.info("📝 創建伺服器事件日誌表格...")

                await cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS guild_event_logs (
                        id BIGINT AUTO_INCREMENT PRIMARY KEY,
                        guild_id BIGINT NOT NULL,
                        user_id BIGINT NULL,

                        # 事件資訊
                        event_type VARCHAR(50) NOT NULL,
                        event_category ENUM('guild_management', 'user_action', 'system', 'security', 'integration') NOT NULL,
                        event_name VARCHAR(100) NOT NULL,

                        # 事件詳情
                        description TEXT,
                        metadata JSON,
                        before_data JSON COMMENT '變更前的資料',
                        after_data JSON COMMENT '變更後的資料',

                        # 來源資訊
                        source VARCHAR(50) NOT NULL COMMENT '事件來源: bot, web, api, webhook等',
                        ip_address VARCHAR(45),
                        user_agent TEXT,

                        # 狀態資訊
                        status ENUM('success', 'failed', 'partial') DEFAULT 'success',
                        error_message TEXT,

                        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

                        FOREIGN KEY (guild_id) REFERENCES guild_info(guild_id) ON DELETE CASCADE,
                        INDEX idx_guild_id (guild_id),
                        INDEX idx_user_id (user_id),
                        INDEX idx_event_type (event_type),
                        INDEX idx_event_category (event_category),
                        INDEX idx_timestamp (timestamp),
                        INDEX idx_source (source),
                        INDEX idx_status (status)
                    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
                """
                )

                # 7. 伺服器備份與恢復表
                logger.info("💾 創建伺服器備份表格...")

                await cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS guild_backups (
                        id INT AUTO_INCREMENT PRIMARY KEY,
                        guild_id BIGINT NOT NULL,

                        # 備份資訊
                        backup_name VARCHAR(100) NOT NULL,
                        backup_type ENUM('manual', 'scheduled', 'migration', 'emergency') NOT NULL,
                        backup_scope ENUM('full', 'settings_only', 'data_only', 'custom') NOT NULL,

                        # 備份內容
                        included_tables JSON NOT NULL COMMENT '包含的資料表列表',
                        backup_size_mb DECIMAL(10,2) DEFAULT 0,
                        record_count INT DEFAULT 0,

                        # 檔案資訊
                        file_path VARCHAR(255),
                        file_hash VARCHAR(64),
                        compression_type VARCHAR(20),
                        encrypted BOOLEAN DEFAULT FALSE,

                        # 狀態資訊
                        status ENUM('creating', 'completed', 'failed', 'expired', 'corrupted') DEFAULT 'creating',
                        progress_percentage INT DEFAULT 0,
                        error_message TEXT,

                        # 元資料
                        created_by BIGINT NOT NULL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        expires_at TIMESTAMP,
                        last_verified TIMESTAMP,
                        restoration_count INT DEFAULT 0,

                        FOREIGN KEY (guild_id) REFERENCES guild_info(guild_id) ON DELETE CASCADE,
                        INDEX idx_guild_id (guild_id),
                        INDEX idx_backup_type (backup_type),
                        INDEX idx_status (status),
                        INDEX idx_created_at (created_at),
                        INDEX idx_expires_at (expires_at)
                    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
                """
                )

                await conn.commit()
                logger.info("✅ 伺服器管理系統資料庫表格創建完成")

                # 插入預設資料
                await _insert_default_guild_data(cursor)
                await conn.commit()

                return True

    except Exception as e:
        logger.error(f"❌ 伺服器管理表格創建失敗: {e}")
        return False


async def _insert_default_guild_data(cursor):
    """插入預設伺服器管理資料"""
    try:
        # 插入預設配額模板
        default_quotas = [
            {
                "plan": "free",
                "max_tickets_per_user": 3,
                "max_votes_per_user": 5,
                "max_workflows": 10,
                "max_webhooks": 5,
                "max_api_calls_per_day": 1000,
                "max_storage_mb": 50,
                "commands_per_minute": 30,
            },
            {
                "plan": "basic",
                "max_tickets_per_user": 10,
                "max_votes_per_user": 20,
                "max_workflows": 50,
                "max_webhooks": 20,
                "max_api_calls_per_day": 10000,
                "max_storage_mb": 200,
                "commands_per_minute": 100,
            },
            {
                "plan": "premium",
                "max_tickets_per_user": 50,
                "max_votes_per_user": 100,
                "max_workflows": 200,
                "max_webhooks": 100,
                "max_api_calls_per_day": 50000,
                "max_storage_mb": 1000,
                "commands_per_minute": 300,
            },
            {
                "plan": "enterprise",
                "max_tickets_per_user": -1,  # 無限制
                "max_votes_per_user": -1,
                "max_workflows": -1,
                "max_webhooks": -1,
                "max_api_calls_per_day": -1,
                "max_storage_mb": -1,
                "commands_per_minute": 1000,
            },
        ]

        # 這些作為模板，實際的配額會在伺服器加入時根據方案建立

        logger.info("✅ 預設伺服器管理資料已準備")

    except Exception as e:
        logger.error(f"❌ 預設伺服器管理資料插入失敗: {e}")


# 主要初始化函數
async def initialize_guild_management_system():
    """初始化伺服器管理系統"""
    try:
        logger.info("🏛️ 開始初始化伺服器管理系統...")

        success = await create_guild_management_tables()

        if success:
            logger.info("✅ 伺服器管理系統初始化完成")
            return True
        else:
            logger.error("❌ 伺服器管理系統初始化失敗")
            return False

    except Exception as e:
        logger.error(f"❌ 伺服器管理系統初始化異常: {e}")
        return False
