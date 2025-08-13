#!/usr/bin/env python3
# fix_database_schema.py
"""
資料庫表格結構修復腳本
修復tickets表格缺少title/description欄位
修復lottery_participants表格問題
"""

import asyncio
import sys
import os

# 添加專案路徑
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from bot.db.pool import init_database, db_pool
from shared.logger import logger
import shared.config as config
import aiomysql

async def check_and_fix_database():
    """檢查並修復資料庫表格結構"""
    
    try:
        # 初始化資料庫連線
        await init_database(
            host=config.DB_HOST,
            port=config.DB_PORT, 
            user=config.DB_USER,
            password=config.DB_PASSWORD,
            database=config.DB_NAME
        )
        
        logger.info("🔍 開始檢查資料庫表格結構...")
        
        async with db_pool.connection() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cursor:
                
                # 1. 檢查並修復tickets表格
                await check_and_fix_tickets_table(cursor, conn)
                
                # 2. 檢查並修復lottery表格
                await check_and_fix_lottery_tables(cursor, conn)
                
                # 3. 檢查其他重要表格
                await check_other_tables(cursor, conn)
                
        logger.info("✅ 資料庫表格結構檢查和修復完成")
        
    except Exception as e:
        logger.error(f"❌ 資料庫修復失敗: {e}")
        raise
    finally:
        try:
            await db_pool.close()
        except:
            pass

async def check_and_fix_tickets_table(cursor, conn):
    """檢查並修復tickets表格"""
    logger.info("🎫 檢查tickets表格結構...")
    
    try:
        # 檢查表格是否存在
        await cursor.execute("SHOW TABLES LIKE 'tickets'")
        if not await cursor.fetchone():
            logger.warning("tickets表格不存在，創建新表格...")
            await create_tickets_table(cursor, conn)
            return
        
        # 檢查表格欄位
        await cursor.execute("DESCRIBE tickets")
        columns = await cursor.fetchall()
        existing_columns = {col['Field'] for col in columns}
        
        logger.info(f"現有欄位: {list(existing_columns)}")
        
        # 需要的欄位
        required_columns = {
            'title': "VARCHAR(255) NOT NULL COMMENT '票券標題'",
            'description': "TEXT NOT NULL COMMENT '票券描述'",
            'subject': "VARCHAR(255) NULL COMMENT '票券主旨'"
        }
        
        # 添加缺少的欄位
        for column, definition in required_columns.items():
            if column not in existing_columns:
                logger.info(f"添加缺少的欄位: {column}")
                await cursor.execute(f"ALTER TABLE tickets ADD COLUMN {column} {definition}")
                await conn.commit()
                logger.info(f"✅ 成功添加欄位 {column}")
        
        logger.info("✅ tickets表格結構檢查完成")
        
    except Exception as e:
        logger.error(f"❌ tickets表格修復失敗: {e}")
        raise

async def create_tickets_table(cursor, conn):
    """創建完整的tickets表格"""
    create_sql = """
    CREATE TABLE tickets (
        id INT AUTO_INCREMENT PRIMARY KEY,
        discord_id VARCHAR(20) NOT NULL COMMENT '開票者 Discord ID',
        username VARCHAR(100) NOT NULL COMMENT '開票者用戶名',
        discord_username VARCHAR(100) NOT NULL COMMENT '開票者 Discord 用戶名',
        title VARCHAR(255) NOT NULL COMMENT '票券標題',
        description TEXT NOT NULL COMMENT '票券描述',
        subject VARCHAR(255) NULL COMMENT '票券主旨',
        type VARCHAR(50) NOT NULL COMMENT '票券類型',
        priority ENUM('urgent', 'high', 'medium', 'low') DEFAULT 'medium' COMMENT '優先級',
        status ENUM('open', 'in_progress', 'pending', 'resolved', 'closed', 'archived') DEFAULT 'open' COMMENT '狀態',
        channel_id BIGINT NOT NULL COMMENT '頻道 ID',
        guild_id BIGINT NOT NULL COMMENT '伺服器 ID',
        assigned_to BIGINT NULL COMMENT '指派的客服 ID',
        assigned_at TIMESTAMP NULL COMMENT '指派時間',
        first_response_at TIMESTAMP NULL COMMENT '首次回應時間',
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
    """
    
    await cursor.execute(create_sql)
    await conn.commit()
    logger.info("✅ tickets表格創建成功")

async def check_and_fix_lottery_tables(cursor, conn):
    """檢查並修復抽獎相關表格"""
    logger.info("🎲 檢查lottery表格結構...")
    
    # 檢查lottery_participants是否存在
    await cursor.execute("SHOW TABLES LIKE 'lottery_participants'")
    if await cursor.fetchone():
        logger.info("發現lottery_participants表格，需要重命名為lottery_entries")
        try:
            # 檢查lottery_entries是否已存在
            await cursor.execute("SHOW TABLES LIKE 'lottery_entries'")
            if not await cursor.fetchone():
                # 重命名表格
                await cursor.execute("RENAME TABLE lottery_participants TO lottery_entries")
                await conn.commit()
                logger.info("✅ lottery_participants已重命名為lottery_entries")
            else:
                # 如果都存在，需要遷移數據
                logger.warning("lottery_entries已存在，需要遷移數據")
                await migrate_lottery_data(cursor, conn)
        except Exception as e:
            logger.error(f"重命名lottery_participants失敗: {e}")
    
    # 檢查lottery_entries表格結構
    await cursor.execute("SHOW TABLES LIKE 'lottery_entries'")
    if await cursor.fetchone():
        await cursor.execute("DESCRIBE lottery_entries")
        columns = await cursor.fetchall()
        existing_columns = {col['Field'] for col in columns}
        logger.info(f"lottery_entries現有欄位: {list(existing_columns)}")
        
        # 檢查是否需要修復joined_at欄位
        if 'joined_at' in existing_columns and 'entry_time' not in existing_columns:
            logger.info("修復joined_at欄位為entry_time")
            await cursor.execute("ALTER TABLE lottery_entries CHANGE joined_at entry_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '參與時間'")
            await conn.commit()
        elif 'joined_at' not in existing_columns and 'entry_time' not in existing_columns:
            logger.info("添加entry_time欄位")
            await cursor.execute("ALTER TABLE lottery_entries ADD COLUMN entry_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '參與時間'")
            await conn.commit()
    else:
        # 創建lottery_entries表格
        logger.info("創建lottery_entries表格")
        await create_lottery_entries_table(cursor, conn)
    
    # 檢查lotteries主表
    await cursor.execute("SHOW TABLES LIKE 'lotteries'")
    if not await cursor.fetchone():
        logger.info("創建lotteries主表")
        await create_lotteries_table(cursor, conn)

async def create_lottery_entries_table(cursor, conn):
    """創建lottery_entries表格"""
    create_sql = """
    CREATE TABLE lottery_entries (
        id INT AUTO_INCREMENT PRIMARY KEY COMMENT '參賽ID',
        lottery_id INT NOT NULL COMMENT '抽獎ID',
        user_id BIGINT NOT NULL COMMENT '用戶ID',
        username VARCHAR(100) NOT NULL COMMENT '用戶名稱',
        entry_method ENUM('reaction', 'command') NOT NULL DEFAULT 'command' COMMENT '參與方式',
        entry_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '參與時間',
        is_valid BOOLEAN DEFAULT TRUE COMMENT '是否有效',
        validation_notes TEXT NULL COMMENT '驗證備註',
        
        UNIQUE KEY unique_entry (lottery_id, user_id),
        INDEX idx_lottery (lottery_id),
        INDEX idx_user (user_id),
        INDEX idx_entry_time (entry_time)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """
    
    await cursor.execute(create_sql)
    await conn.commit()
    logger.info("✅ lottery_entries表格創建成功")

async def create_lotteries_table(cursor, conn):
    """創建lotteries主表"""
    create_sql = """
    CREATE TABLE lotteries (
        id INT AUTO_INCREMENT PRIMARY KEY COMMENT '抽獎ID',
        title VARCHAR(255) NOT NULL COMMENT '抽獎標題',
        description TEXT NULL COMMENT '抽獎描述',
        prize_description TEXT NOT NULL COMMENT '獎品描述',
        winner_count INT NOT NULL DEFAULT 1 COMMENT '中獎人數',
        channel_id BIGINT NOT NULL COMMENT '頻道ID',
        guild_id BIGINT NOT NULL COMMENT '伺服器ID',
        creator_id BIGINT NOT NULL COMMENT '創建者ID',
        message_id BIGINT NULL COMMENT '訊息ID',
        status ENUM('active', 'ended', 'cancelled') DEFAULT 'active' COMMENT '狀態',
        requirements JSON NULL COMMENT '參與要求',
        start_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '開始時間',
        end_time TIMESTAMP NOT NULL COMMENT '結束時間',
        draw_time TIMESTAMP NULL COMMENT '開獎時間',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '創建時間',
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新時間',
        
        INDEX idx_guild_status (guild_id, status),
        INDEX idx_creator (creator_id),
        INDEX idx_end_time (end_time),
        INDEX idx_channel (channel_id)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """
    
    await cursor.execute(create_sql)
    await conn.commit()
    logger.info("✅ lotteries表格創建成功")

async def migrate_lottery_data(cursor, conn):
    """遷移lottery_participants數據到lottery_entries"""
    try:
        logger.info("開始遷移lottery_participants數據...")
        
        # 檢查lottery_participants的數據
        await cursor.execute("SELECT COUNT(*) as count FROM lottery_participants")
        result = await cursor.fetchone()
        count = result['count']
        
        if count > 0:
            logger.info(f"發現{count}筆數據需要遷移")
            
            # 遷移數據
            await cursor.execute("""
            INSERT IGNORE INTO lottery_entries 
            (lottery_id, user_id, username, entry_method, entry_time, is_valid)
            SELECT lottery_id, user_id, username, 'command', 
                   COALESCE(joined_at, NOW()), TRUE
            FROM lottery_participants
            """)
            
            migrated = cursor.rowcount
            await conn.commit()
            logger.info(f"✅ 成功遷移{migrated}筆數據")
            
            # 刪除舊表格
            await cursor.execute("DROP TABLE lottery_participants")
            await conn.commit()
            logger.info("✅ 舊表格lottery_participants已刪除")
        else:
            # 直接刪除空表格
            await cursor.execute("DROP TABLE lottery_participants")
            await conn.commit()
            logger.info("✅ 空的lottery_participants表格已刪除")
            
    except Exception as e:
        logger.error(f"數據遷移失敗: {e}")
        raise

async def check_other_tables(cursor, conn):
    """檢查其他重要表格"""
    logger.info("🔍 檢查其他重要表格...")
    
    # 檢查api_users表格
    await cursor.execute("SHOW TABLES LIKE 'api_users'")
    if not await cursor.fetchone():
        logger.info("創建api_users表格...")
        create_sql = """
        CREATE TABLE api_users (
            id INT AUTO_INCREMENT PRIMARY KEY,
            discord_id VARCHAR(20) NOT NULL UNIQUE COMMENT 'Discord 用戶 ID',
            username VARCHAR(100) NOT NULL COMMENT '用戶名',
            discord_username VARCHAR(100) NOT NULL COMMENT 'Discord 用戶名',
            password_hash VARCHAR(255) NULL COMMENT '密碼雜湊',
            permission_level ENUM('read_only', 'write', 'admin', 'super_admin') DEFAULT 'read_only' COMMENT '權限等級',
            guild_id BIGINT NULL COMMENT '所屬伺服器 ID',
            roles JSON NULL COMMENT 'Discord 角色列表',
            permissions JSON NULL COMMENT '權限列表',
            is_admin BOOLEAN DEFAULT FALSE COMMENT '是否為管理員',
            is_staff BOOLEAN DEFAULT FALSE COMMENT '是否為客服人員',
            is_active BOOLEAN DEFAULT TRUE COMMENT '是否啟用',
            last_login TIMESTAMP NULL COMMENT '最後登入時間',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '創建時間',
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新時間',
            
            INDEX idx_discord_id (discord_id),
            INDEX idx_guild (guild_id),
            INDEX idx_permission (permission_level),
            INDEX idx_active (is_active)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """
        await cursor.execute(create_sql)
        await conn.commit()
        logger.info("✅ api_users表格創建成功")

async def main():
    """主函數"""
    logger.info("🚀 開始資料庫表格結構修復...")
    
    try:
        await check_and_fix_database()
        logger.info("🎉 資料庫表格結構修復完成！")
    except Exception as e:
        logger.error(f"💥 修復失敗: {e}")
        return 1
    
    return 0

if __name__ == "__main__":
    exit_code = asyncio.run(main())
    exit(exit_code)