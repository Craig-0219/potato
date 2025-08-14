#!/usr/bin/env python3
# scripts/create_cross_platform_tables.py - 跨平台經濟系統資料庫表格
"""
創建跨平台經濟系統所需的資料庫表格
支援Discord與Minecraft之間的數據同步
"""

import asyncio
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bot.db.pool import db_pool
from shared.logger import logger

async def create_cross_platform_tables():
    """創建跨平台相關表格"""
    try:
        async with db_pool.connection() as conn:
            async with conn.cursor() as cursor:
                
                # 1. 跨平台用戶綁定表
                await cursor.execute("""
                    CREATE TABLE IF NOT EXISTS cross_platform_users (
                        id INT AUTO_INCREMENT PRIMARY KEY,
                        discord_id BIGINT NOT NULL,
                        minecraft_uuid VARCHAR(36) NOT NULL,
                        guild_id BIGINT NOT NULL,
                        username VARCHAR(255) DEFAULT '',
                        linked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        last_sync TIMESTAMP NULL,
                        sync_enabled BOOLEAN DEFAULT TRUE,
                        
                        UNIQUE KEY unique_discord (discord_id),
                        UNIQUE KEY unique_minecraft (minecraft_uuid),
                        INDEX idx_guild_id (guild_id),
                        INDEX idx_last_sync (last_sync)
                    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
                """)
                
                # 2. 跨平台交易記錄表
                await cursor.execute("""
                    CREATE TABLE IF NOT EXISTS cross_platform_transactions (
                        id INT AUTO_INCREMENT PRIMARY KEY,
                        transaction_id VARCHAR(255) NOT NULL UNIQUE,
                        from_platform ENUM('discord', 'minecraft', 'web', 'mobile') NOT NULL,
                        to_platform ENUM('discord', 'minecraft', 'web', 'mobile') NOT NULL,
                        user_id VARCHAR(255) NOT NULL, -- Discord ID 或 Minecraft UUID
                        transaction_type ENUM('transfer', 'purchase', 'reward', 'penalty', 'sync', 'exchange') NOT NULL,
                        currency_type VARCHAR(50) NOT NULL, -- coins, gems, experience
                        amount BIGINT NOT NULL,
                        reason VARCHAR(500) NOT NULL,
                        metadata JSON,
                        timestamp TIMESTAMP NOT NULL,
                        status ENUM('pending', 'completed', 'failed', 'cancelled') DEFAULT 'pending',
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                        
                        INDEX idx_user_id (user_id),
                        INDEX idx_transaction_type (transaction_type),
                        INDEX idx_currency_type (currency_type),
                        INDEX idx_timestamp (timestamp),
                        INDEX idx_status (status),
                        INDEX idx_platforms (from_platform, to_platform)
                    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
                """)
                
                # 3. 平台配置表
                await cursor.execute("""
                    CREATE TABLE IF NOT EXISTS platform_configs (
                        id INT AUTO_INCREMENT PRIMARY KEY,
                        platform_type ENUM('discord', 'minecraft', 'web', 'mobile') NOT NULL,
                        config_key VARCHAR(100) NOT NULL,
                        config_value TEXT,
                        description VARCHAR(500),
                        is_active BOOLEAN DEFAULT TRUE,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                        
                        UNIQUE KEY unique_platform_key (platform_type, config_key),
                        INDEX idx_platform (platform_type),
                        INDEX idx_active (is_active)
                    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
                """)
                
                # 4. 跨平台成就同步表
                await cursor.execute("""
                    CREATE TABLE IF NOT EXISTS cross_platform_achievements (
                        id INT AUTO_INCREMENT PRIMARY KEY,
                        user_binding_id INT NOT NULL,
                        achievement_id VARCHAR(50) NOT NULL,
                        platform_source ENUM('discord', 'minecraft', 'web', 'mobile') NOT NULL,
                        unlocked_at TIMESTAMP NOT NULL,
                        synced_to_platforms JSON, -- 已同步到的平台列表
                        sync_status ENUM('pending', 'synced', 'failed') DEFAULT 'pending',
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        
                        FOREIGN KEY (user_binding_id) REFERENCES cross_platform_users(id) ON DELETE CASCADE,
                        INDEX idx_user_binding (user_binding_id),
                        INDEX idx_achievement (achievement_id),
                        INDEX idx_platform_source (platform_source),
                        INDEX idx_sync_status (sync_status)
                    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
                """)
                
                # 5. 同步日誌表
                await cursor.execute("""
                    CREATE TABLE IF NOT EXISTS sync_logs (
                        id INT AUTO_INCREMENT PRIMARY KEY,
                        user_binding_id INT NOT NULL,
                        sync_type ENUM('full', 'incremental', 'manual') NOT NULL,
                        from_platform ENUM('discord', 'minecraft', 'web', 'mobile') NOT NULL,
                        to_platform ENUM('discord', 'minecraft', 'web', 'mobile') NOT NULL,
                        data_synced JSON, -- 同步的數據
                        result ENUM('success', 'partial', 'failed') NOT NULL,
                        error_message TEXT,
                        sync_duration INT, -- 同步耗時（毫秒）
                        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        
                        FOREIGN KEY (user_binding_id) REFERENCES cross_platform_users(id) ON DELETE CASCADE,
                        INDEX idx_user_binding (user_binding_id),
                        INDEX idx_sync_type (sync_type),
                        INDEX idx_platforms_sync (from_platform, to_platform),
                        INDEX idx_result (result),
                        INDEX idx_timestamp (timestamp)
                    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
                """)
                
                # 6. 插入預設配置
                await cursor.execute("""
                    INSERT IGNORE INTO platform_configs (platform_type, config_key, config_value, description) VALUES
                    ('minecraft', 'webhook_url', '', 'Minecraft服務器webhook端點'),
                    ('minecraft', 'server_key', '', 'Minecraft服務器認證密鑰'),
                    ('minecraft', 'sync_interval', '300', '自動同步間隔（秒）'),
                    ('discord', 'sync_notifications', 'true', '是否發送同步通知'),
                    ('discord', 'auto_sync_enabled', 'true', '是否啟用自動同步'),
                    ('global', 'coin_exchange_rate', '1.0', 'Discord金幣 -> Minecraft金幣匯率'),
                    ('global', 'gem_exchange_rate', '10.0', 'Discord寶石 -> Minecraft金幣匯率'),
                    ('global', 'exp_exchange_rate', '0.1', 'Discord經驗 -> Minecraft金幣匯率')
                """)
                
                await conn.commit()
                logger.info("✅ 跨平台經濟系統表格創建完成")
                
    except Exception as e:
        logger.error(f"❌ 創建跨平台表格失敗: {e}")
        raise

async def main():
    """主函數"""
    try:
        logger.info("🚀 開始創建跨平台經濟系統表格...")
        await create_cross_platform_tables()
        logger.info("🎉 跨平台經濟系統表格創建成功！")
        
    except Exception as e:
        logger.error(f"❌ 執行失敗: {e}")
        return 1
    
    return 0

if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)