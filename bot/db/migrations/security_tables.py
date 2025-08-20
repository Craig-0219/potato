# bot/db/migrations/security_tables.py - v1.0.0
# 🔐 安全系統資料庫表格初始化
# Security System Database Tables

import logging
from bot.db.pool import db_pool

logger = logging.getLogger(__name__)

async def create_security_tables():
    """創建安全系統相關的資料庫表格"""
    try:
        async with db_pool.connection() as conn:
            async with conn.cursor() as cursor:
                
                # 1. MFA 多因素認證表
                logger.info("🔐 創建 MFA 相關表格...")
                
                await cursor.execute("""
                    CREATE TABLE IF NOT EXISTS user_mfa (
                        id INT AUTO_INCREMENT PRIMARY KEY,
                        user_id BIGINT NOT NULL,
                        method_type ENUM('totp', 'sms', 'email', 'backup_codes') NOT NULL,
                        secret_key TEXT,
                        is_enabled BOOLEAN DEFAULT FALSE,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                        INDEX idx_user_method (user_id, method_type),
                        INDEX idx_user_enabled (user_id, is_enabled)
                    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
                """)
                
                # 2. RBAC 角色表
                logger.info("🔒 創建 RBAC 相關表格...")
                
                await cursor.execute("""
                    CREATE TABLE IF NOT EXISTS rbac_roles (
                        id INT AUTO_INCREMENT PRIMARY KEY,
                        name VARCHAR(100) NOT NULL UNIQUE,
                        description TEXT,
                        level INT NOT NULL DEFAULT 10,
                        is_system BOOLEAN DEFAULT FALSE,
                        is_active BOOLEAN DEFAULT TRUE,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                        INDEX idx_name (name),
                        INDEX idx_level (level),
                        INDEX idx_active (is_active)
                    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
                """)
                
                await cursor.execute("""
                    CREATE TABLE IF NOT EXISTS rbac_role_permissions (
                        id INT AUTO_INCREMENT PRIMARY KEY,
                        role_id INT NOT NULL,
                        permission VARCHAR(100) NOT NULL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (role_id) REFERENCES rbac_roles(id) ON DELETE CASCADE,
                        UNIQUE KEY unique_role_permission (role_id, permission),
                        INDEX idx_role_id (role_id),
                        INDEX idx_permission (permission)
                    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
                """)
                
                await cursor.execute("""
                    CREATE TABLE IF NOT EXISTS rbac_user_roles (
                        id INT AUTO_INCREMENT PRIMARY KEY,
                        user_id BIGINT NOT NULL,
                        guild_id BIGINT NOT NULL,
                        role_id INT NOT NULL,
                        assigned_by BIGINT,
                        assigned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        expires_at TIMESTAMP NULL,
                        is_active BOOLEAN DEFAULT TRUE,
                        revoked_by BIGINT NULL,
                        revoked_at TIMESTAMP NULL,
                        FOREIGN KEY (role_id) REFERENCES rbac_roles(id) ON DELETE CASCADE,
                        INDEX idx_user_guild (user_id, guild_id),
                        INDEX idx_role_id (role_id),
                        INDEX idx_active (is_active),
                        INDEX idx_expires (expires_at)
                    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
                """)
                
                # 3. 安全事件審計表
                logger.info("🔍 創建安全審計表格...")
                
                await cursor.execute("""
                    CREATE TABLE IF NOT EXISTS security_events (
                        id BIGINT AUTO_INCREMENT PRIMARY KEY,
                        user_id BIGINT NULL,
                        guild_id BIGINT NULL,
                        event_type VARCHAR(100) NOT NULL,
                        category ENUM('authentication', 'authorization', 'data_access', 
                                    'system_config', 'user_action', 'api_access', 
                                    'security_violation', 'compliance') NOT NULL,
                        severity ENUM('critical', 'high', 'medium', 'low', 'info') NOT NULL,
                        message TEXT NOT NULL,
                        details JSON,
                        ip_address VARCHAR(45),
                        user_agent TEXT,
                        session_id VARCHAR(128),
                        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        processed BOOLEAN DEFAULT FALSE,
                        hash_signature VARCHAR(64),
                        INDEX idx_user_id (user_id),
                        INDEX idx_guild_id (guild_id),
                        INDEX idx_event_type (event_type),
                        INDEX idx_category (category),
                        INDEX idx_severity (severity),
                        INDEX idx_timestamp (timestamp),
                        INDEX idx_ip_address (ip_address),
                        INDEX idx_processed (processed),
                        INDEX idx_hash (hash_signature)
                    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
                """)
                
                # 4. API 密鑰管理表
                logger.info("🛡️ 創建 API 安全表格...")
                
                await cursor.execute("""
                    CREATE TABLE IF NOT EXISTS api_keys (
                        id INT AUTO_INCREMENT PRIMARY KEY,
                        key_value VARCHAR(100) NOT NULL UNIQUE,
                        name VARCHAR(100) NOT NULL,
                        key_type ENUM('read_only', 'read_write', 'admin', 'service') NOT NULL,
                        user_id BIGINT NULL,
                        guild_id BIGINT NULL,
                        permissions TEXT,
                        is_active BOOLEAN DEFAULT TRUE,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        expires_at TIMESTAMP NULL,
                        last_used TIMESTAMP NULL,
                        usage_count INT DEFAULT 0,
                        revoked_by BIGINT NULL,
                        revoked_at TIMESTAMP NULL,
                        INDEX idx_key_value (key_value),
                        INDEX idx_user_id (user_id),
                        INDEX idx_guild_id (guild_id),
                        INDEX idx_active (is_active),
                        INDEX idx_expires (expires_at)
                    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
                """)
                
                await cursor.execute("""
                    CREATE TABLE IF NOT EXISTS api_rate_limits (
                        id INT AUTO_INCREMENT PRIMARY KEY,
                        api_key_id INT NOT NULL,
                        limit_type ENUM('per_second', 'per_minute', 'per_hour', 'per_day') NOT NULL,
                        max_requests INT NOT NULL,
                        window_seconds INT NOT NULL,
                        burst_allowance INT DEFAULT 0,
                        FOREIGN KEY (api_key_id) REFERENCES api_keys(id) ON DELETE CASCADE,
                        INDEX idx_api_key_id (api_key_id)
                    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
                """)
                
                # 5. 安全規則表
                await cursor.execute("""
                    CREATE TABLE IF NOT EXISTS security_rules (
                        id INT AUTO_INCREMENT PRIMARY KEY,
                        name VARCHAR(100) NOT NULL,
                        description TEXT,
                        rule_type ENUM('rate_limit', 'ip_filter', 'content_filter', 'behavior_analysis') NOT NULL,
                        pattern TEXT,
                        action ENUM('allow', 'block', 'alert', 'throttle') NOT NULL,
                        severity_threshold ENUM('critical', 'high', 'medium', 'low', 'info') NOT NULL,
                        is_active BOOLEAN DEFAULT TRUE,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                        INDEX idx_rule_type (rule_type),
                        INDEX idx_active (is_active)
                    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
                """)
                
                # 6. 安全警報表
                await cursor.execute("""
                    CREATE TABLE IF NOT EXISTS security_alerts (
                        id INT AUTO_INCREMENT PRIMARY KEY,
                        event_id BIGINT NOT NULL,
                        alert_type ENUM('threat_detected', 'anomaly_detected', 'compliance_violation', 'system_breach') NOT NULL,
                        severity ENUM('critical', 'high', 'medium', 'low') NOT NULL,
                        title VARCHAR(200) NOT NULL,
                        description TEXT,
                        affected_resources JSON,
                        recommended_actions TEXT,
                        status ENUM('open', 'investigating', 'resolved', 'false_positive') DEFAULT 'open',
                        assigned_to BIGINT NULL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                        resolved_at TIMESTAMP NULL,
                        FOREIGN KEY (event_id) REFERENCES security_events(id) ON DELETE CASCADE,
                        INDEX idx_event_id (event_id),
                        INDEX idx_alert_type (alert_type),
                        INDEX idx_severity (severity),
                        INDEX idx_status (status),
                        INDEX idx_created_at (created_at)
                    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
                """)
                
                # 7. 合規報告表
                await cursor.execute("""
                    CREATE TABLE IF NOT EXISTS compliance_reports (
                        id INT AUTO_INCREMENT PRIMARY KEY,
                        standard ENUM('soc2', 'gdpr', 'hipaa', 'iso27001', 'custom') NOT NULL,
                        report_type ENUM('monthly', 'quarterly', 'annual', 'ad_hoc') NOT NULL,
                        guild_id BIGINT NULL,
                        period_start DATE NOT NULL,
                        period_end DATE NOT NULL,
                        compliance_score INT,
                        status ENUM('draft', 'review', 'approved', 'published') DEFAULT 'draft',
                        report_data JSON,
                        findings TEXT,
                        recommendations TEXT,
                        generated_by BIGINT,
                        generated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        approved_by BIGINT NULL,
                        approved_at TIMESTAMP NULL,
                        INDEX idx_standard (standard),
                        INDEX idx_guild_id (guild_id),
                        INDEX idx_period (period_start, period_end),
                        INDEX idx_status (status)
                    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
                """)
                
                # 8. 用戶會話表
                await cursor.execute("""
                    CREATE TABLE IF NOT EXISTS user_sessions (
                        id VARCHAR(128) PRIMARY KEY,
                        user_id BIGINT NOT NULL,
                        guild_id BIGINT NULL,
                        session_type ENUM('web', 'api', 'bot', 'mobile') NOT NULL,
                        ip_address VARCHAR(45),
                        user_agent TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        last_activity TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                        expires_at TIMESTAMP NOT NULL,
                        is_active BOOLEAN DEFAULT TRUE,
                        login_method ENUM('password', 'oauth', 'mfa', 'api_key') NOT NULL,
                        device_info JSON,
                        INDEX idx_user_id (user_id),
                        INDEX idx_guild_id (guild_id),
                        INDEX idx_expires (expires_at),
                        INDEX idx_active (is_active),
                        INDEX idx_ip_address (ip_address)
                    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
                """)
                
                # 9. 權限變更歷史表
                await cursor.execute("""
                    CREATE TABLE IF NOT EXISTS permission_history (
                        id BIGINT AUTO_INCREMENT PRIMARY KEY,
                        user_id BIGINT NOT NULL,
                        guild_id BIGINT NOT NULL,
                        action ENUM('granted', 'revoked', 'modified') NOT NULL,
                        permission_type ENUM('role', 'direct', 'temporary') NOT NULL,
                        old_permissions JSON,
                        new_permissions JSON,
                        changed_by BIGINT,
                        reason TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        INDEX idx_user_guild (user_id, guild_id),
                        INDEX idx_action (action),
                        INDEX idx_changed_by (changed_by),
                        INDEX idx_created_at (created_at)
                    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
                """)
                
                # 10. 資料存取日誌表
                await cursor.execute("""
                    CREATE TABLE IF NOT EXISTS data_access_logs (
                        id BIGINT AUTO_INCREMENT PRIMARY KEY,
                        user_id BIGINT NOT NULL,
                        guild_id BIGINT NULL,
                        resource_type VARCHAR(50) NOT NULL,
                        resource_id VARCHAR(100),
                        action ENUM('create', 'read', 'update', 'delete', 'export', 'import') NOT NULL,
                        table_name VARCHAR(64),
                        affected_rows INT DEFAULT 0,
                        query_hash VARCHAR(64),
                        ip_address VARCHAR(45),
                        user_agent TEXT,
                        success BOOLEAN DEFAULT TRUE,
                        error_message TEXT,
                        execution_time_ms INT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        INDEX idx_user_id (user_id),
                        INDEX idx_guild_id (guild_id),
                        INDEX idx_resource (resource_type, resource_id),
                        INDEX idx_action (action),
                        INDEX idx_table_name (table_name),
                        INDEX idx_created_at (created_at),
                        INDEX idx_ip_address (ip_address)
                    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
                """)
                
                await conn.commit()
                
                logger.info("✅ 安全系統資料庫表格創建完成")
                
                # 創建預設資料
                await _insert_default_security_data(cursor)
                await conn.commit()
                
                return True
                
    except Exception as e:
        logger.error(f"❌ 安全系統表格創建失敗: {e}")
        return False

async def _insert_default_security_data(cursor):
    """插入預設安全數據"""
    try:
        # 插入預設安全規則
        default_rules = [
            {
                "name": "API Rate Limit - High Volume",
                "description": "檢測 API 高頻率存取",
                "rule_type": "rate_limit",
                "pattern": "api_requests_per_minute > 1000",
                "action": "throttle",
                "severity": "medium"
            },
            {
                "name": "Failed Login Detection",
                "description": "檢測多次登入失敗",
                "rule_type": "behavior_analysis", 
                "pattern": "failed_login_count >= 5",
                "action": "block",
                "severity": "high"
            },
            {
                "name": "Suspicious IP Activity",
                "description": "檢測可疑 IP 活動",
                "rule_type": "ip_filter",
                "pattern": "requests_from_ip > 100",
                "action": "alert",
                "severity": "medium"
            },
            {
                "name": "SQL Injection Attempt",
                "description": "檢測 SQL 注入嘗試",
                "rule_type": "content_filter",
                "pattern": "(UNION.*SELECT|DROP.*TABLE|INSERT.*INTO)",
                "action": "block",
                "severity": "critical"
            }
        ]
        
        for rule in default_rules:
            await cursor.execute("""
                INSERT IGNORE INTO security_rules 
                (name, description, rule_type, pattern, action, severity_threshold)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (
                rule["name"], rule["description"], rule["rule_type"],
                rule["pattern"], rule["action"], rule["severity"]
            ))
        
        logger.info("✅ 預設安全規則已插入")
        
    except Exception as e:
        logger.error(f"❌ 預設安全數據插入失敗: {e}")

# 用於主程序初始化時調用
async def initialize_security_system():
    """初始化安全系統"""
    try:
        logger.info("🔐 開始初始化企業級安全系統...")
        
        # 創建安全表格
        success = await create_security_tables()
        
        if success:
            logger.info("✅ 企業級安全系統初始化完成")
            return True
        else:
            logger.error("❌ 安全系統初始化失敗")
            return False
            
    except Exception as e:
        logger.error(f"❌ 安全系統初始化異常: {e}")
        return False