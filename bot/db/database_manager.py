# bot/db/database_manager.py - 新建檔案
"""
資料庫管理器 - 自動初始化和遷移
統一管理所有資料表的創建和更新
"""

import asyncio
from typing import Dict, List, Tuple, Optional, Any
from bot.db.pool import db_pool
from shared.logger import logger
import json


class DatabaseManager:
    """資料庫管理器 - 負責資料表初始化和遷移"""
    
    def __init__(self):
        self.db = db_pool
        self.current_version = "1.0.0"
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
            current_db_version = await self._get_database_version()
            
            if force_recreate:
                logger.warning("⚠️ 強制重建模式 - 將刪除所有現存表格")
                await self._drop_all_tables()
                current_db_version = None
            
            # 創建各系統的表格
            await self._create_ticket_tables()
            await self._create_assignment_tables()
            await self._create_vote_tables()
            await self._create_tag_tables()
            await self._create_welcome_tables()
            await self._create_workflow_tables()
            await self._create_webhook_tables()
            
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
                    rating INT NULL COMMENT '評分' CHECK (rating BETWEEN 1 AND 5),
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
        
        # 創建票券指派系統表格
        await self._create_assignment_tables()
    
    async def _create_assignment_tables(self):
        """創建票券指派系統相關表格"""
        logger.info("👥 創建指派系統表格...")
        
        tables = {
            'staff_workload': """
                CREATE TABLE IF NOT EXISTS staff_workload (
                    id INT PRIMARY KEY AUTO_INCREMENT COMMENT '主鍵',
                    guild_id BIGINT NOT NULL COMMENT '伺服器 ID',
                    staff_id BIGINT NOT NULL COMMENT '客服人員 ID',
                    current_tickets INT DEFAULT 0 COMMENT '當前處理票券數',
                    total_assigned INT DEFAULT 0 COMMENT '總指派票券數',
                    total_completed INT DEFAULT 0 COMMENT '總完成票券數',
                    avg_completion_time INT DEFAULT 0 COMMENT '平均完成時間(分鐘)',
                    last_assigned_at TIMESTAMP NULL COMMENT '最後指派時間',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '建立時間',
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新時間',
                    
                    UNIQUE KEY uk_guild_staff (guild_id, staff_id),
                    INDEX idx_guild (guild_id),
                    INDEX idx_workload (current_tickets),
                    INDEX idx_last_assigned (last_assigned_at)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            """,
            
            'assignment_history': """
                CREATE TABLE IF NOT EXISTS assignment_history (
                    id INT PRIMARY KEY AUTO_INCREMENT COMMENT '主鍵',
                    ticket_id INT NOT NULL COMMENT '票券 ID',
                    assigned_from BIGINT NULL COMMENT '原指派對象 (NULL表示首次指派)',
                    assigned_to BIGINT NOT NULL COMMENT '新指派對象',
                    assigned_by BIGINT NOT NULL COMMENT '指派執行者',
                    assignment_reason VARCHAR(255) DEFAULT 'manual' COMMENT '指派原因',
                    assignment_method ENUM('manual', 'auto_least_workload', 'auto_round_robin', 'auto_specialty') DEFAULT 'manual' COMMENT '指派方式',
                    assigned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '指派時間',
                    
                    INDEX idx_ticket (ticket_id),
                    INDEX idx_assigned_to (assigned_to),
                    INDEX idx_assigned_by (assigned_by),
                    INDEX idx_assigned_at (assigned_at),
                    INDEX idx_method (assignment_method)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            """,
            
            'staff_specialties': """
                CREATE TABLE IF NOT EXISTS staff_specialties (
                    id INT PRIMARY KEY AUTO_INCREMENT COMMENT '主鍵',
                    guild_id BIGINT NOT NULL COMMENT '伺服器 ID',
                    staff_id BIGINT NOT NULL COMMENT '客服人員 ID',
                    specialty_type VARCHAR(100) NOT NULL COMMENT '專精類型',
                    skill_level ENUM('beginner', 'intermediate', 'advanced', 'expert') DEFAULT 'intermediate' COMMENT '技能等級',
                    is_active BOOLEAN DEFAULT TRUE COMMENT '是否啟用',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '建立時間',
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新時間',
                    
                    UNIQUE KEY uk_guild_staff_specialty (guild_id, staff_id, specialty_type),
                    INDEX idx_guild (guild_id),
                    INDEX idx_staff (staff_id),
                    INDEX idx_specialty (specialty_type),
                    INDEX idx_active (is_active)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            """,
            
            'assignment_rules': """
                CREATE TABLE IF NOT EXISTS assignment_rules (
                    id INT PRIMARY KEY AUTO_INCREMENT COMMENT '主鍵',
                    guild_id BIGINT NOT NULL COMMENT '伺服器 ID',
                    rule_name VARCHAR(100) NOT NULL COMMENT '規則名稱',
                    ticket_type VARCHAR(100) NULL COMMENT '適用票券類型 (NULL表示全部)',
                    priority_level ENUM('low', 'medium', 'high') NULL COMMENT '適用優先級 (NULL表示全部)',
                    assignment_method ENUM('manual', 'auto_least_workload', 'auto_round_robin', 'auto_specialty') DEFAULT 'auto_least_workload' COMMENT '指派方法',
                    max_concurrent_tickets INT DEFAULT 5 COMMENT '單人最大並發票券數',
                    is_active BOOLEAN DEFAULT TRUE COMMENT '是否啟用',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '建立時間',
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新時間',
                    
                    UNIQUE KEY uk_guild_rule (guild_id, rule_name),
                    INDEX idx_guild (guild_id),
                    INDEX idx_ticket_type (ticket_type),
                    INDEX idx_priority (priority_level),
                    INDEX idx_active (is_active)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            """
        }
        
        await self._create_tables_batch(tables, "指派系統")
    
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
                    
                    INDEX idx_guild_active (guild_id),
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
            """,
            
            'vote_settings': """
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
    
    async def get_database_status(self) -> Dict[str, Any]:
        """取得資料庫狀態（為了兼容性）"""
        try:
            status = await self.get_system_status()
            return {
                "healthy": True,
                "version": status.get("database_version"),
                "tables": {k: v.get("row_count", 0) for k, v in status.get("tables", {}).items()}
            }
        except Exception as e:
            logger.error(f"取得資料庫狀態失敗：{e}")
            return {"healthy": False, "error": str(e)}
    
    async def cleanup_old_data(self, days: int = 90) -> Dict[str, int]:
        """清理舊資料"""
        cleanup_results = {}
        
        try:
            async with self.db.connection() as conn:
                async with conn.cursor() as cursor:
                    # 清理舊的票券日誌
                    await cursor.execute("""
                        DELETE FROM ticket_logs 
                        WHERE created_at < DATE_SUB(NOW(), INTERVAL %s DAY)
                    """, (days,))
                    cleanup_results["ticket_logs"] = cursor.rowcount
                    
                    # 清理舊的票券檢視記錄
                    await cursor.execute("""
                        DELETE FROM ticket_views 
                        WHERE viewed_at < DATE_SUB(NOW(), INTERVAL %s DAY)
                    """, (days,))
                    cleanup_results["ticket_views"] = cursor.rowcount
                    
                    # 清理過期的統計快取
                    await cursor.execute("""
                        DELETE FROM ticket_statistics_cache 
                        WHERE expires_at < NOW()
                    """, ())
                    cleanup_results["expired_cache"] = cursor.rowcount
                    
                    # 清理已結束的投票回應（超過指定天數）
                    await cursor.execute("""
                        DELETE vr FROM vote_responses vr
                        JOIN votes v ON vr.vote_id = v.id
                        WHERE v.end_time < DATE_SUB(NOW(), INTERVAL %s DAY)
                    """, (days,))
                    cleanup_results["old_vote_responses"] = cursor.rowcount
                    
                    await conn.commit()
                    logger.info(f"資料清理完成：{cleanup_results}")
                    
        except Exception as e:
            logger.error(f"資料清理失敗：{e}")
            
        return cleanup_results
    
    async def migrate_database(self, target_version: str = None) -> bool:
        """資料庫遷移"""
        try:
            current_version = await self._get_database_version()
            target = target_version or self.current_version
            
            logger.info(f"資料庫遷移：{current_version} -> {target}")
            
            # 目前只有一個版本，直接更新版本號
            await self._update_database_version(target)
            
            logger.info("✅ 資料庫遷移完成")
            return True
            
        except Exception as e:
            logger.error(f"資料庫遷移失敗：{e}")
            return False
    
    async def validate_database_integrity(self) -> Dict[str, Any]:
        """驗證資料庫完整性"""
        result = {
            "valid": True,
            "issues": [],
            "checks": {}
        }
        
        try:
            async with self.db.connection() as conn:
                async with conn.cursor() as cursor:
                    # 檢查必要表格是否存在
                    required_tables = ['tickets', 'ticket_settings', 'votes', 'vote_options', 'vote_responses']
                    missing_tables = []
                    
                    for table in required_tables:
                        exists = await self.check_table_exists(table)
                        if not exists:
                            missing_tables.append(table)
                    
                    if missing_tables:
                        result["valid"] = False
                        result["issues"].append(f"缺少表格：{', '.join(missing_tables)}")
                    
                    result["checks"]["required_tables"] = len(required_tables) - len(missing_tables)
                    
                    # 檢查外鍵約束
                    await cursor.execute("""
                        SELECT COUNT(*) FROM information_schema.TABLE_CONSTRAINTS 
                        WHERE CONSTRAINT_TYPE = 'FOREIGN KEY' AND TABLE_SCHEMA = DATABASE()
                    """)
                    fk_count = (await cursor.fetchone())[0]
                    result["checks"]["foreign_keys"] = fk_count
                    
                    # 檢查資料一致性（投票選項是否有對應的投票）
                    await cursor.execute("""
                        SELECT COUNT(*) FROM vote_options vo 
                        LEFT JOIN votes v ON vo.vote_id = v.id 
                        WHERE v.id IS NULL
                    """)
                    orphaned_options = (await cursor.fetchone())[0]
                    
                    if orphaned_options > 0:
                        result["valid"] = False
                        result["issues"].append(f"發現 {orphaned_options} 個孤立的投票選項")
                    
                    result["checks"]["orphaned_vote_options"] = orphaned_options
                    
        except Exception as e:
            result["valid"] = False
            result["issues"].append(f"驗證過程錯誤：{e}")
            logger.error(f"資料庫完整性驗證失敗：{e}")
        
        return result
    
    async def _create_tag_tables(self):
        """創建標籤系統相關表格"""
        logger.info("🏷️ 創建標籤系統表格...")
        
        tables = {
            'ticket_tags': """
                CREATE TABLE IF NOT EXISTS ticket_tags (
                    id INT PRIMARY KEY AUTO_INCREMENT COMMENT '主鍵',
                    guild_id BIGINT NOT NULL COMMENT '伺服器 ID',
                    name VARCHAR(50) NOT NULL COMMENT '標籤名稱',
                    display_name VARCHAR(100) NOT NULL COMMENT '顯示名稱',
                    color VARCHAR(7) DEFAULT '#808080' COMMENT '標籤顏色（HEX格式）',
                    emoji VARCHAR(10) NULL COMMENT '標籤表情符號',
                    description TEXT NULL COMMENT '標籤描述',
                    category ENUM('system', 'department', 'custom', 'priority', 'status') DEFAULT 'custom' COMMENT '標籤分類',
                    is_active TINYINT(1) DEFAULT 1 COMMENT '是否活躍',
                    created_by BIGINT NOT NULL COMMENT '建立者 ID',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '建立時間',
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新時間',
                    
                    UNIQUE KEY uk_guild_name (guild_id, name),
                    INDEX idx_guild (guild_id),
                    INDEX idx_category (category),
                    INDEX idx_active (is_active),
                    INDEX idx_created_by (created_by)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            """,
            
            'ticket_tag_mappings': """
                CREATE TABLE IF NOT EXISTS ticket_tag_mappings (
                    id INT PRIMARY KEY AUTO_INCREMENT COMMENT '主鍵',
                    ticket_id INT NOT NULL COMMENT '票券 ID',
                    tag_id INT NOT NULL COMMENT '標籤 ID',
                    added_by BIGINT NOT NULL COMMENT '添加者 ID',
                    added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '添加時間',
                    
                    UNIQUE KEY uk_ticket_tag (ticket_id, tag_id),
                    INDEX idx_ticket (ticket_id),
                    INDEX idx_tag (tag_id),
                    INDEX idx_added_by (added_by),
                    INDEX idx_added_at (added_at),
                    
                    FOREIGN KEY (ticket_id) REFERENCES tickets(id) ON DELETE CASCADE,
                    FOREIGN KEY (tag_id) REFERENCES ticket_tags(id) ON DELETE CASCADE
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            """,
            
            'tag_usage_stats': """
                CREATE TABLE IF NOT EXISTS tag_usage_stats (
                    id INT PRIMARY KEY AUTO_INCREMENT COMMENT '主鍵',
                    guild_id BIGINT NOT NULL COMMENT '伺服器 ID',
                    tag_id INT NOT NULL COMMENT '標籤 ID',
                    usage_count INT DEFAULT 0 COMMENT '使用次數',
                    last_used_at TIMESTAMP NULL COMMENT '最後使用時間',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '建立時間',
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新時間',
                    
                    UNIQUE KEY uk_guild_tag (guild_id, tag_id),
                    INDEX idx_guild (guild_id),
                    INDEX idx_tag (tag_id),
                    INDEX idx_usage_count (usage_count),
                    INDEX idx_last_used (last_used_at),
                    
                    FOREIGN KEY (tag_id) REFERENCES ticket_tags(id) ON DELETE CASCADE
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            """,
            
            'tag_auto_rules': """
                CREATE TABLE IF NOT EXISTS tag_auto_rules (
                    id INT PRIMARY KEY AUTO_INCREMENT COMMENT '主鍵',
                    guild_id BIGINT NOT NULL COMMENT '伺服器 ID',
                    rule_name VARCHAR(100) NOT NULL COMMENT '規則名稱',
                    tag_id INT NOT NULL COMMENT '要添加的標籤 ID',
                    trigger_type ENUM('keyword', 'ticket_type', 'user_role', 'channel') DEFAULT 'keyword' COMMENT '觸發類型',
                    trigger_value TEXT NOT NULL COMMENT '觸發條件值',
                    is_active TINYINT(1) DEFAULT 1 COMMENT '是否活躍',
                    priority INT DEFAULT 1 COMMENT '規則優先級',
                    created_by BIGINT NOT NULL COMMENT '建立者 ID',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '建立時間',
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新時間',
                    
                    INDEX idx_guild (guild_id),
                    INDEX idx_tag (tag_id),
                    INDEX idx_trigger_type (trigger_type),
                    INDEX idx_active (is_active),
                    INDEX idx_priority (priority),
                    
                    FOREIGN KEY (tag_id) REFERENCES ticket_tags(id) ON DELETE CASCADE
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            """
        }
        
        try:
            async with self.db.connection() as conn:
                async with conn.cursor() as cursor:
                    for table_name, create_sql in tables.items():
                        logger.debug(f"創建表格：{table_name}")
                        await cursor.execute(create_sql)
                    
                    await conn.commit()
                    logger.info(f"✅ 標籤系統表格創建完成：{', '.join(tables.keys())}")
                    
        except Exception as e:
            logger.error(f"❌ 標籤系統表格創建失敗：{e}")
            raise

    async def _create_welcome_tables(self):
        """創建歡迎系統相關表格"""
        logger.info("🎉 創建歡迎系統表格...")
        
        tables = {
            'welcome_settings': """
                CREATE TABLE IF NOT EXISTS welcome_settings (
                    guild_id BIGINT PRIMARY KEY COMMENT '伺服器 ID',
                    welcome_channel_id BIGINT NULL COMMENT '歡迎頻道 ID',
                    leave_channel_id BIGINT NULL COMMENT '離開頻道 ID',
                    welcome_message TEXT NULL COMMENT '歡迎訊息模板',
                    leave_message TEXT NULL COMMENT '離開訊息模板',
                    welcome_embed_enabled TINYINT(1) DEFAULT 1 COMMENT '是否使用嵌入式訊息',
                    welcome_dm_enabled TINYINT(1) DEFAULT 0 COMMENT '是否發送私訊歡迎',
                    welcome_dm_message TEXT NULL COMMENT '私訊歡迎訊息',
                    auto_role_enabled TINYINT(1) DEFAULT 0 COMMENT '是否啟用自動身分組',
                    auto_roles JSON NULL COMMENT '自動分配的身分組列表',
                    welcome_image_url TEXT NULL COMMENT '歡迎圖片 URL',
                    welcome_thumbnail_url TEXT NULL COMMENT '歡迎縮圖 URL',
                    welcome_color INT DEFAULT 0x00ff00 COMMENT '嵌入訊息顏色',
                    is_enabled TINYINT(1) DEFAULT 1 COMMENT '系統是否啟用',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '建立時間',
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新時間',
                    
                    INDEX idx_welcome_channel (welcome_channel_id),
                    INDEX idx_leave_channel (leave_channel_id),
                    INDEX idx_enabled (is_enabled)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            """,
            
            'welcome_logs': """
                CREATE TABLE IF NOT EXISTS welcome_logs (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    guild_id BIGINT NOT NULL COMMENT '伺服器 ID',
                    user_id BIGINT NOT NULL COMMENT '用戶 ID',
                    username VARCHAR(100) NOT NULL COMMENT '用戶名稱',
                    action_type ENUM('join', 'leave') NOT NULL COMMENT '動作類型',
                    welcome_sent TINYINT(1) DEFAULT 0 COMMENT '是否已發送歡迎訊息',
                    roles_assigned JSON NULL COMMENT '分配的身分組',
                    dm_sent TINYINT(1) DEFAULT 0 COMMENT '是否已發送私訊',
                    error_message TEXT NULL COMMENT '錯誤訊息',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '建立時間',
                    
                    INDEX idx_guild (guild_id),
                    INDEX idx_user (user_id),
                    INDEX idx_action (action_type),
                    INDEX idx_created (created_at)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            """,
            
            'system_settings': """
                CREATE TABLE IF NOT EXISTS system_settings (
                    guild_id BIGINT PRIMARY KEY COMMENT '伺服器 ID',
                    general_settings JSON NULL COMMENT '一般設定',
                    channel_settings JSON NULL COMMENT '頻道設定',
                    role_settings JSON NULL COMMENT '角色設定',
                    notification_settings JSON NULL COMMENT '通知設定',
                    feature_toggles JSON NULL COMMENT '功能開關',
                    custom_settings JSON NULL COMMENT '自定義設定',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '建立時間',
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新時間',
                    
                    INDEX idx_updated (updated_at)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            """
        }
        
        try:
            async with self.db.connection() as conn:
                async with conn.cursor() as cursor:
                    for table_name, create_sql in tables.items():
                        logger.debug(f"創建表格：{table_name}")
                        await cursor.execute(create_sql)
                    
                    await conn.commit()
                    logger.info(f"✅ 歡迎系統表格創建完成：{', '.join(tables.keys())}")
                    
        except Exception as e:
            logger.error(f"❌ 歡迎系統表格創建失敗：{e}")
            raise
    
    async def _create_workflow_tables(self):
        """創建工作流程系統相關表格"""
        logger.info("⚙️ 創建工作流程系統表格...")
        
        from bot.db.workflow_dao import WorkflowDAO
        try:
            workflow_dao = WorkflowDAO()
            await workflow_dao._initialize()
            logger.info("✅ 工作流程系統表格創建完成")
        except Exception as e:
            logger.error(f"❌ 工作流程系統表格創建失敗：{e}")
            raise
    
    async def _create_webhook_tables(self):
        """創建Webhook整合系統相關表格"""
        logger.info("🔗 創建Webhook整合系統表格...")
        
        from bot.db.webhook_dao import WebhookDAO
        try:
            webhook_dao = WebhookDAO()
            await webhook_dao._initialize()
            logger.info("✅ Webhook整合系統表格創建完成")
        except Exception as e:
            logger.error(f"❌ Webhook整合系統表格創建失敗：{e}")
            raise


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
            "connection": "active"
        }
        
    except Exception as e:
        logger.error(f"資料庫健康檢查失敗：{e}")
        return {
            "status": "unhealthy",
            "error": str(e),
            "connection": "failed"
        }
