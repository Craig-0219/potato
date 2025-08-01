# bot/db/ticket_dao.py - v7.0 完整修復版
# 票券資料操作層（DAO）：完整功能資料庫操作

from bot.db.pool import db_pool
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Any, Tuple
import json
from bot.utils.debug import debug_log

class TicketDAO:
    """票券資料存取物件 (DAO) - 完整版"""

    def __init__(self):
        pass

    # ===== 資料表管理 =====
    
    @staticmethod
    async def create_tables():
        """建立所有必要的資料表"""
        async with db_pool.acquire() as conn:
            async with conn.cursor() as cursor:
                # 主票券表
                await cursor.execute("""
                    CREATE TABLE IF NOT EXISTS tickets (
                        ticket_id INT AUTO_INCREMENT PRIMARY KEY,
                        discord_id VARCHAR(20) NOT NULL COMMENT '開票者 Discord ID',
                        username VARCHAR(100) NOT NULL COMMENT '開票者用戶名',
                        type VARCHAR(100) NOT NULL COMMENT '票券類型',
                        channel_id BIGINT NOT NULL COMMENT '票券頻道 ID',
                        guild_id BIGINT NOT NULL COMMENT '伺服器 ID',
                        priority ENUM('high', 'medium', 'low') DEFAULT 'medium' COMMENT '優先級',
                        status ENUM('open', 'closed', 'archived') DEFAULT 'open' COMMENT '狀態',
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '建立時間',
                        closed_at TIMESTAMP NULL COMMENT '關閉時間',
                        closed_by VARCHAR(20) NULL COMMENT '關閉者 ID',
                        close_reason TEXT NULL COMMENT '關閉原因',
                        assigned_to BIGINT NULL COMMENT '被指派的客服 ID',
                        rating INT NULL CHECK (rating BETWEEN 1 AND 5) COMMENT '用戶評分',
                        rating_feedback TEXT NULL COMMENT '評分回饋',
                        last_activity TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '最後活動時間',
                        sla_warned BOOLEAN DEFAULT FALSE COMMENT '是否已發送 SLA 警告',
                        tags JSON NULL COMMENT '票券標籤',
                        
                        INDEX idx_discord_id (discord_id),
                        INDEX idx_guild_id (guild_id),
                        INDEX idx_status (status),
                        INDEX idx_priority (priority),
                        INDEX idx_channel_id (channel_id),
                        INDEX idx_created_at (created_at),
                        INDEX idx_assigned_to (assigned_to),
                        INDEX idx_compound_search (guild_id, status, priority, created_at)
                    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
                """)
                
                # 伺服器設定表
                await cursor.execute("""
                    CREATE TABLE IF NOT EXISTS ticket_settings (
                        guild_id BIGINT PRIMARY KEY COMMENT '伺服器 ID',
                        category_id BIGINT NULL COMMENT '票券分類頻道 ID',
                        log_channel_id BIGINT NULL COMMENT '日誌頻道 ID',
                        sla_alert_channel_id BIGINT NULL COMMENT 'SLA 警告頻道 ID',
                        max_tickets_per_user INT DEFAULT 3 COMMENT '每用戶最大票券數',
                        auto_close_hours INT DEFAULT 24 COMMENT '自動關閉小時數',
                        sla_response_minutes INT DEFAULT 60 COMMENT 'SLA 回應時間（分鐘）',
                        auto_assign_enabled BOOLEAN DEFAULT FALSE COMMENT '啟用自動分配',
                        welcome_message TEXT COMMENT '歡迎訊息',
                        support_roles JSON NULL COMMENT '客服身分組 ID 列表',
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
                    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
                """)
                
                # 票券回應記錄表
                await cursor.execute("""
                    CREATE TABLE IF NOT EXISTS ticket_responses (
                        id INT AUTO_INCREMENT PRIMARY KEY,
                        ticket_id INT NOT NULL COMMENT '票券 ID',
                        staff_id BIGINT NOT NULL COMMENT '客服 ID',
                        response_time_minutes DECIMAL(10,2) NOT NULL COMMENT '回應時間（分鐘）',
                        response_type ENUM('staff', 'auto') DEFAULT 'staff' COMMENT '回應類型',
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        
                        FOREIGN KEY (ticket_id) REFERENCES tickets(ticket_id) ON DELETE CASCADE,
                        INDEX idx_ticket_id (ticket_id),
                        INDEX idx_staff_id (staff_id)
                    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
                """)
                
                # 票券查看記錄表
                await cursor.execute("""
                    CREATE TABLE IF NOT EXISTS ticket_views (
                        ticket_id INT NOT NULL COMMENT '票券 ID',
                        viewer_id BIGINT NOT NULL COMMENT '查看者 ID',
                        viewed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '查看時間',
                        
                        PRIMARY KEY (ticket_id, viewer_id),
                        FOREIGN KEY (ticket_id) REFERENCES tickets(ticket_id) ON DELETE CASCADE,
                        INDEX idx_viewed_at (viewed_at)
                    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
                """)
                
                # 票券操作日誌表
                await cursor.execute("""
                    CREATE TABLE IF NOT EXISTS ticket_logs (
                        id INT AUTO_INCREMENT PRIMARY KEY,
                        ticket_id INT NOT NULL COMMENT '票券 ID',
                        action VARCHAR(50) NOT NULL COMMENT '操作類型',
                        details TEXT COMMENT '操作詳情',
                        created_by VARCHAR(20) COMMENT '操作者 ID',
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        
                        FOREIGN KEY (ticket_id) REFERENCES tickets(ticket_id) ON DELETE CASCADE,
                        INDEX idx_ticket_id (ticket_id),
                        INDEX idx_action (action)
                    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
                """)
                
                # 回覆模板表
                await cursor.execute("""
                    CREATE TABLE IF NOT EXISTS ticket_templates (
                        id INT AUTO_INCREMENT PRIMARY KEY,
                        guild_id BIGINT NOT NULL COMMENT '伺服器 ID',
                        name VARCHAR(100) NOT NULL COMMENT '模板名稱',
                        content TEXT NOT NULL COMMENT '模板內容',
                        description TEXT COMMENT '模板描述',
                        usage_count INT DEFAULT 0 COMMENT '使用次數',
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                        
                        UNIQUE KEY unique_template (guild_id, name),
                        INDEX idx_guild_id (guild_id)
                    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
                """)
                
                # 自動回覆規則表
                await cursor.execute("""
                    CREATE TABLE IF NOT EXISTS auto_reply_rules (
                        id INT AUTO_INCREMENT PRIMARY KEY,
                        guild_id BIGINT NOT NULL COMMENT '伺服器 ID',
                        name VARCHAR(100) NOT NULL COMMENT '規則名稱',
                        keywords JSON NOT NULL COMMENT '觸發關鍵字',
                        reply TEXT NOT NULL COMMENT '回覆內容',
                        priority INT DEFAULT 0 COMMENT '優先級',
                        enabled BOOLEAN DEFAULT TRUE COMMENT '是否啟用',
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        
                        UNIQUE KEY unique_rule (guild_id, name),
                        INDEX idx_guild_id (guild_id)
                    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
                """)
                
                # 自動回覆日誌表
                await cursor.execute("""
                    CREATE TABLE IF NOT EXISTS auto_reply_logs (
                        id INT AUTO_INCREMENT PRIMARY KEY,
                        ticket_id INT NOT NULL COMMENT '票券 ID',
                        rule_id INT NOT NULL COMMENT '規則 ID',
                        reply_content TEXT NOT NULL COMMENT '回覆內容',
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        
                        FOREIGN KEY (ticket_id) REFERENCES tickets(ticket_id) ON DELETE CASCADE,
                        INDEX idx_ticket_id (ticket_id)
                    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
                """)
                
                # 客服專精表
                await cursor.execute("""
                    CREATE TABLE IF NOT EXISTS staff_specialties (
                        guild_id BIGINT NOT NULL COMMENT '伺服器 ID',
                        staff_id BIGINT NOT NULL COMMENT '客服 ID',
                        specialties JSON NOT NULL COMMENT '專精領域',
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                        
                        PRIMARY KEY (guild_id, staff_id)
                    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
                """)
                
                # 統計快取表
                await cursor.execute("""
                    CREATE TABLE IF NOT EXISTS ticket_statistics_cache (
                        guild_id BIGINT NOT NULL,
                        stat_type VARCHAR(50) NOT NULL,
                        data JSON NOT NULL,
                        expires_at TIMESTAMP NOT NULL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        
                        PRIMARY KEY (guild_id, stat_type),
                        INDEX idx_expires_at (expires_at)
                    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
                """)
                
                # 通知偏好表
                await cursor.execute("""
                    CREATE TABLE IF NOT EXISTS notification_preferences (
                        guild_id BIGINT NOT NULL,
                        user_id BIGINT NOT NULL,
                        ticket_assigned BOOLEAN DEFAULT TRUE,
                        sla_warning BOOLEAN DEFAULT TRUE,
                        ticket_closed BOOLEAN DEFAULT TRUE,
                        rating_received BOOLEAN DEFAULT TRUE,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                        
                        PRIMARY KEY (guild_id, user_id)
                    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
                """)
                
                await conn.commit()
                debug_log("[TicketDAO] 所有資料表建立/檢查完成")

    # ===== 基礎票券操作 =====

    @staticmethod
    async def next_ticket_code():
        """取得下一張票券的流水號"""
        async with db_pool.acquire() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute("SELECT MAX(ticket_id) FROM tickets")
                row = await cursor.fetchone()
                next_id = (row[0] or 0) + 1
                return f"{next_id:04d}"

    @staticmethod
    async def create_ticket(discord_id: str, username: str, ticket_type: str, channel_id: int, guild_id: int, priority: str = 'medium'):
        """建立新票券記錄"""
        async with db_pool.acquire() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute(
                    """
                    INSERT INTO tickets (discord_id, username, type, channel_id, guild_id, priority, status, created_at, last_activity)
                    VALUES (%s, %s, %s, %s, %s, %s, 'open', NOW(), NOW())
                    """,
                    (discord_id, username, ticket_type, channel_id, guild_id, priority)
                )
                await conn.commit()
                
                # 返回新建立的票券 ID
                await cursor.execute("SELECT LAST_INSERT_ID()")
                result = await cursor.fetchone()
                ticket_id = result[0] if result else None
                
                # 記錄建立日誌
                if ticket_id:
                    await cursor.execute(
                        """
                        INSERT INTO ticket_logs (ticket_id, action, details, created_by, created_at)
                        VALUES (%s, 'created', %s, %s, NOW())
                        """,
                        (ticket_id, f"票券建立 - 類型: {ticket_type}, 優先級: {priority}", discord_id)
                    )
                    await conn.commit()
                
                return ticket_id

    @staticmethod
    async def close_ticket(channel_id: int, closer_id: str, reason: str = None):
        """關閉票券"""
        async with db_pool.acquire() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute(
                    """
                    UPDATE tickets
                    SET status = 'closed', closed_at = NOW(), closed_by = %s, close_reason = %s
                    WHERE channel_id = %s AND status = 'open'
                    """,
                    (closer_id, reason, channel_id)
                )
                
                if cursor.rowcount > 0:
                    # 取得票券 ID
                    await cursor.execute(
                        "SELECT ticket_id FROM tickets WHERE channel_id = %s",
                        (channel_id,)
                    )
                    result = await cursor.fetchone()
                    
                    if result:
                        ticket_id = result[0]
                        # 記錄關閉日誌
                        await cursor.execute(
                            """
                            INSERT INTO ticket_logs (ticket_id, action, details, created_by, created_at)
                            VALUES (%s, 'closed', %s, %s, NOW())
                            """,
                            (ticket_id, f"票券關閉 - 原因: {reason or '無'}", closer_id)
                        )
                
                await conn.commit()
                return cursor.rowcount > 0

    @staticmethod
    async def get_ticket_by_id(ticket_id: int):
        """查詢單一票券資訊"""
        async with db_pool.acquire() as conn:
            async with conn.cursor(dictionary=True) as cursor:
                await cursor.execute(
                    "SELECT * FROM tickets WHERE ticket_id = %s", (ticket_id,)
                )
                return await cursor.fetchone()

    @staticmethod
    async def get_ticket_by_channel(channel_id: int):
        """根據頻道 ID 查詢票券"""
        async with db_pool.acquire() as conn:
            async with conn.cursor(dictionary=True) as cursor:
                await cursor.execute(
                    "SELECT * FROM tickets WHERE channel_id = %s", (channel_id,)
                )
                return await cursor.fetchone()

    # ===== 系統設定管理 =====
    
    @staticmethod
    async def get_guild_settings(guild_id: int) -> Optional[Dict[str, Any]]:
        """取得伺服器設定"""
        async with db_pool.acquire() as conn:
            async with conn.cursor(dictionary=True) as cursor:
                await cursor.execute(
                    "SELECT * FROM ticket_settings WHERE guild_id = %s",
                    (guild_id,)
                )
                result = await cursor.fetchone()
                
                if result and result.get('support_roles'):
                    try:
                        result['support_roles'] = json.loads(result['support_roles'])
                    except:
                        result['support_roles'] = []
                
                return result

    @staticmethod
    async def create_default_settings(guild_id: int) -> Dict[str, Any]:
        """建立預設設定"""
        default_settings = {
            'guild_id': guild_id,
            'max_tickets_per_user': 3,
            'auto_close_hours': 24,
            'sla_response_minutes': 60,
            'auto_assign_enabled': False,
            'welcome_message': "歡迎使用客服系統！請選擇你的問題類型，我們會為你建立專屬支援頻道。",
            'support_roles': []
        }
        
        async with db_pool.acquire() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute(
                    """
                    INSERT INTO ticket_settings 
                    (guild_id, max_tickets_per_user, auto_close_hours, sla_response_minutes, 
                     auto_assign_enabled, welcome_message, support_roles, created_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, NOW())
                    """,
                    (
                        guild_id,
                        default_settings['max_tickets_per_user'],
                        default_settings['auto_close_hours'], 
                        default_settings['sla_response_minutes'],
                        default_settings['auto_assign_enabled'],
                        default_settings['welcome_message'],
                        json.dumps(default_settings['support_roles'])
                    )
                )
                await conn.commit()
                
        return default_settings

    @staticmethod
    async def update_guild_setting(guild_id: int, setting_name: str, value: Any) -> bool:
        """更新單一伺服器設定"""
        # 處理特殊類型的值
        if setting_name == 'support_roles' and isinstance(value, list):
            value = json.dumps(value)
        
        async with db_pool.acquire() as conn:
            async with conn.cursor() as cursor:
                try:
                    # 先檢查設定是否存在
                    await cursor.execute(
                        "SELECT COUNT(*) FROM ticket_settings WHERE guild_id = %s",
                        (guild_id,)
                    )
                    exists = (await cursor.fetchone())[0] > 0
                    
                    if exists:
                        # 更新現有設定
                        sql = f"UPDATE ticket_settings SET {setting_name} = %s, updated_at = NOW() WHERE guild_id = %s"
                        await cursor.execute(sql, (value, guild_id))
                    else:
                        # 建立預設設定然後更新
                        await TicketDAO.create_default_settings(guild_id)
                        sql = f"UPDATE ticket_settings SET {setting_name} = %s, updated_at = NOW() WHERE guild_id = %s"
                        await cursor.execute(sql, (value, guild_id))
                    
                    await conn.commit()
                    return cursor.rowcount > 0
                except Exception as e:
                    debug_log(f"[TicketDAO] 更新設定錯誤：{e}")
                    return False

    # ===== 分頁查詢 =====
    
    @staticmethod
    async def paginate_tickets(user_id: str = None, status: str = "all", page: int = 1, page_size: int = 5, 
                             guild_id: int = None, priority: str = None):
        """分頁查詢票券"""
        where = []
        params = []
        
        if guild_id:
            where.append("guild_id = %s")
            params.append(guild_id)
            
        if user_id:
            where.append("discord_id = %s")
            params.append(user_id)
            
        if status in ("open", "closed", "archived"):
            where.append("status = %s")
            params.append(status)
        
        if priority in ("high", "medium", "low"):
            where.append("priority = %s")
            params.append(priority)
            
        where_clause = ""
        if where:
            where_clause = "WHERE " + " AND ".join(where)

        async with db_pool.acquire() as conn:
            async with conn.cursor(dictionary=True) as cursor:
                # 總數查詢
                await cursor.execute(f"SELECT COUNT(*) as cnt FROM tickets {where_clause}", params)
                total = (await cursor.fetchone())["cnt"]
                
                # 分頁查詢
                offset = (page - 1) * page_size
                await cursor.execute(
                    f"""
                    SELECT * FROM tickets {where_clause} 
                    ORDER BY 
                        CASE priority 
                            WHEN 'high' THEN 1 
                            WHEN 'medium' THEN 2 
                            WHEN 'low' THEN 3 
                        END,
                        ticket_id DESC 
                    LIMIT %s OFFSET %s
                    """,
                    params + [page_size, offset]
                )
                tickets = await cursor.fetchall()
                return tickets, total

    # ===== 用戶相關操作 =====
    
    @staticmethod
    async def get_user_ticket_count(user_id: str, guild_id: int, status: str = "open"):
        """取得用戶票券數量"""
        async with db_pool.acquire() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute(
                    "SELECT COUNT(*) FROM tickets WHERE discord_id = %s AND guild_id = %s AND status = %s",
                    (user_id, guild_id, status)
                )
                result = await cursor.fetchone()
                return result[0] if result else 0

    @staticmethod
    async def update_last_activity(ticket_id: int):
        """更新票券最後活動時間"""
        async with db_pool.acquire() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute(
                    "UPDATE tickets SET last_activity = NOW() WHERE ticket_id = %s",
                    (ticket_id,)
                )
                await conn.commit()
                return cursor.rowcount > 0

    # ===== 優先級與指派 =====
    
    @staticmethod
    async def update_ticket_priority(ticket_id: int, priority: str, updated_by: int):
        """更新票券優先級"""
        async with db_pool.acquire() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute(
                    "UPDATE tickets SET priority = %s WHERE ticket_id = %s",
                    (priority, ticket_id)
                )
                
                # 記錄優先級變更日誌
                await cursor.execute(
                    """
                    INSERT INTO ticket_logs (ticket_id, action, details, created_by, created_at)
                    VALUES (%s, 'priority_change', %s, %s, NOW())
                    """,
                    (ticket_id, f"優先級變更為 {priority}", updated_by)
                )
                
                await conn.commit()
                return cursor.rowcount > 0

    @staticmethod
    async def assign_ticket(ticket_id: int, assigned_to: int, assigned_by: int = None):
        """指派票券"""
        async with db_pool.acquire() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute(
                    "UPDATE tickets SET assigned_to = %s WHERE ticket_id = %s",
                    (assigned_to, ticket_id)
                )
                
                # 記錄指派日誌
                details = f"指派給用戶 {assigned_to}" if assigned_to else "取消指派"
                action_by = assigned_by if assigned_by else "system"
                
                await cursor.execute(
                    """
                    INSERT INTO ticket_logs (ticket_id, action, details, created_by, created_at)
                    VALUES (%s, 'assigned', %s, %s, NOW())
                    """,
                    (ticket_id, details, action_by)
                )
                
                await conn.commit()
                return cursor.rowcount > 0

    # ===== 統計相關方法 =====
    
    @staticmethod
    async def get_server_statistics(guild_id: int) -> Dict[str, Any]:
        """取得伺服器統計資料"""
        async with db_pool.acquire() as conn:
            async with conn.cursor(dictionary=True) as cursor:
                await cursor.execute(
                    """
                    SELECT 
                        COUNT(*) as total_count,
                        SUM(CASE WHEN status = 'open' THEN 1 ELSE 0 END) as open_count,
                        SUM(CASE WHEN status = 'closed' THEN 1 ELSE 0 END) as closed_count,
                        SUM(CASE WHEN status = 'archived' THEN 1 ELSE 0 END) as archived_count,
                        SUM(CASE WHEN DATE(created_at) = CURDATE() THEN 1 ELSE 0 END) as today_count,
                        AVG(CASE WHEN rating IS NOT NULL THEN rating ELSE NULL END) as avg_rating,
                        SUM(CASE WHEN rating IS NOT NULL THEN 1 ELSE 0 END) as total_ratings,
                        SUM(CASE WHEN rating = 5 THEN 1 ELSE 0 END) as five_star_count
                    FROM tickets
                    WHERE guild_id = %s
                    """,
                    (guild_id,)
                )
                stats = await cursor.fetchone()
                
                # 填充預設值
                if not stats:
                    stats = {
                        'total_count': 0, 'open_count': 0, 'closed_count': 0,
                        'archived_count': 0, 'today_count': 0, 'avg_rating': 0,
                        'total_ratings': 0, 'five_star_count': 0
                    }
                
                return stats

    # ===== SLA 監控功能 =====
    
    @staticmethod
    async def has_staff_response(ticket_id: int):
        """檢查是否已有客服回覆"""
        async with db_pool.acquire() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute(
                    "SELECT COUNT(*) FROM ticket_responses WHERE ticket_id = %s AND response_type = 'staff'",
                    (ticket_id,)
                )
                result = await cursor.fetchone()
                return result[0] > 0 if result else False

    @staticmethod
    async def record_first_response(ticket_id: int, staff_id: int, response_time_minutes: float):
        """記錄首次回覆"""
        async with db_pool.acquire() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute(
                    """
                    INSERT INTO ticket_responses (ticket_id, staff_id, response_time_minutes, response_type, created_at)
                    VALUES (%s, %s, %s, 'staff', NOW())
                    """,
                    (ticket_id, staff_id, response_time_minutes)
                )
                await conn.commit()
                return cursor.rowcount > 0

    @staticmethod
    async def get_overdue_tickets():
        """取得超時的票券"""
        async with db_pool.acquire() as conn:
            async with conn.cursor(dictionary=True) as cursor:
                await cursor.execute(
                    """
                    SELECT t.*, ts.sla_response_minutes 
                    FROM tickets t
                    JOIN ticket_settings ts ON t.guild_id = ts.guild_id
                    LEFT JOIN ticket_responses tr ON t.ticket_id = tr.ticket_id AND tr.response_type = 'staff'
                    WHERE t.status = 'open' 
                    AND tr.ticket_id IS NULL
                    AND TIMESTAMPDIFF(MINUTE, t.created_at, NOW()) > (
                        CASE t.priority 
                            WHEN 'high' THEN ts.sla_response_minutes * 0.5
                            WHEN 'medium' THEN ts.sla_response_minutes
                            WHEN 'low' THEN ts.sla_response_minutes * 1.5
                        END
                    )
                    AND (t.sla_warned IS NULL OR t.sla_warned = 0)
                    """
                )
                return await cursor.fetchall()

    @staticmethod
    async def mark_sla_warned(ticket_id: int):
        """標記 SLA 已警告"""
        async with db_pool.acquire() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute(
                    "UPDATE tickets SET sla_warned = 1 WHERE ticket_id = %s",
                    (ticket_id,)
                )
                await conn.commit()
                return cursor.rowcount > 0

    # ===== 評分系統 =====
    
    @staticmethod
    async def save_ticket_rating(ticket_id: int, rating: int, feedback: str = None):
        """保存票券評分"""
        async with db_pool.acquire() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute(
                    "UPDATE tickets SET rating = %s, rating_feedback = %s WHERE ticket_id = %s",
                    (rating, feedback, ticket_id)
                )
                
                # 記錄評分日誌
                await cursor.execute(
                    """
                    INSERT INTO ticket_logs (ticket_id, action, details, created_by, created_at)
                    VALUES (%s, 'rating_added', %s, %s, NOW())
                    """,
                    (ticket_id, f"用戶評分: {rating}/5", "user")
                )
                
                await conn.commit()
                return cursor.rowcount > 0

    # ===== 查看記錄 =====
    
    @staticmethod
    async def record_ticket_view(ticket_id: int, viewer_id: int):
        """記錄票券查看"""
        async with db_pool.acquire() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute(
                    """
                    INSERT INTO ticket_views (ticket_id, viewer_id, viewed_at)
                    VALUES (%s, %s, NOW())
                    ON DUPLICATE KEY UPDATE viewed_at = NOW()
                    """,
                    (ticket_id, viewer_id)
                )
                await conn.commit()
                return cursor.rowcount > 0

    @staticmethod
    async def get_ticket_viewers(ticket_id: int) -> List[Dict[str, Any]]:
        """取得票券查看記錄"""
        async with db_pool.acquire() as conn:
            async with conn.cursor(dictionary=True) as cursor:
                await cursor.execute(
                    """
                    SELECT viewer_id, viewed_at
                    FROM ticket_views 
                    WHERE ticket_id = %s 
                    ORDER BY viewed_at DESC
                    LIMIT 10
                    """,
                    (ticket_id,)
                )
                return await cursor.fetchall()

    # ===== 搜尋功能 =====
    
    @staticmethod
    async def search_tickets_by_content(guild_id: int, keyword: str) -> List[Dict[str, Any]]:
        """根據內容搜尋票券"""
        async with db_pool.acquire() as conn:
            async with conn.cursor(dictionary=True) as cursor:
                search_pattern = f"%{keyword}%"
                await cursor.execute(
                    """
                    SELECT * FROM tickets
                    WHERE guild_id = %s 
                    AND (
                        type LIKE %s OR 
                        close_reason LIKE %s OR 
                        rating_feedback LIKE %s OR
                        username LIKE %s
                    )
                    ORDER BY created_at DESC
                    LIMIT 50
                    """,
                    (guild_id, search_pattern, search_pattern, search_pattern, search_pattern)
                )
                return await cursor.fetchall()

    # ===== 模板系統 =====
    
    @staticmethod
    async def get_template(guild_id: int, template_name: str):
        """取得指定模板"""
        async with db_pool.acquire() as conn:
            async with conn.cursor(dictionary=True) as cursor:
                await cursor.execute(
                    "SELECT * FROM ticket_templates WHERE guild_id = %s AND name = %s",
                    (guild_id, template_name)
                )
                return await cursor.fetchone()

    @staticmethod
    async def get_templates(guild_id: int):
        """取得所有模板"""
        async with db_pool.acquire() as conn:
            async with conn.cursor(dictionary=True) as cursor:
                await cursor.execute(
                    "SELECT * FROM ticket_templates WHERE guild_id = %s ORDER BY usage_count DESC, name",
                    (guild_id,)
                )
                return await cursor.fetchall()

    @staticmethod
    async def create_template(guild_id: int, name: str, content: str, description: str = None):
        """建立模板"""
        async with db_pool.acquire() as conn:
            async with conn.cursor() as cursor:
                try:
                    await cursor.execute(
                        """
                        INSERT INTO ticket_templates (guild_id, name, content, description, created_at)
                        VALUES (%s, %s, %s, %s, NOW())
                        """,
                        (guild_id, name, content, description)
                    )
                    await conn.commit()
                    return True
                except Exception as e:
                    debug_log(f"[TicketDAO] 建立模板錯誤：{e}")
                    return False

    @staticmethod
    async def increment_template_usage(template_id: int):
        """增加模板使用次數"""
        async with db_pool.acquire() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute(
                    "UPDATE ticket_templates SET usage_count = usage_count + 1 WHERE id = %s",
                    (template_id,)
                )
                await conn.commit()
                return cursor.rowcount > 0

    # ===== 自動回覆系統 =====
    
    @staticmethod
    async def get_auto_reply_rules(guild_id: int):
        """取得自動回覆規則"""
        async with db_pool.acquire() as conn:
            async with conn.cursor(dictionary=True) as cursor:
                await cursor.execute(
                    "SELECT * FROM auto_reply_rules WHERE guild_id = %s AND enabled = 1 ORDER BY priority DESC",
                    (guild_id,)
                )
                rules = await cursor.fetchall()
                
                # 解析關鍵字
                for rule in rules:
                    if rule['keywords']:
                        try:
                            rule['keywords'] = json.loads(rule['keywords'])
                        except:
                            rule['keywords'] = []
                
                return rules

    @staticmethod
    async def create_auto_reply_rule(guild_id: int, name: str, keywords: List[str], reply: str, priority: int = 0):
        """建立自動回覆規則"""
        async with db_pool.acquire() as conn:
            async with conn.cursor() as cursor:
                try:
                    await cursor.execute(
                        """
                        INSERT INTO auto_reply_rules (guild_id, name, keywords, reply, priority, created_at)
                        VALUES (%s, %s, %s, %s, %s, NOW())
                        """,
                        (guild_id, name, json.dumps(keywords), reply, priority)
                    )
                    await conn.commit()
                    return True
                except Exception as e:
                    debug_log(f"[TicketDAO] 建立自動回覆規則錯誤：{e}")
                    return False

    @staticmethod
    async def log_auto_reply(ticket_id: int, rule_id: int, reply_content: str):
        """記錄自動回覆日誌"""
        async with db_pool.acquire() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute(
                    """
                    INSERT INTO auto_reply_logs (ticket_id, rule_id, reply_content, created_at)
                    VALUES (%s, %s, %s, NOW())
                    """,
                    (ticket_id, rule_id, reply_content)
                )
                await conn.commit()
                return cursor.rowcount > 0

    # ===== SLA 統計功能 =====
    
    @staticmethod
    async def get_sla_statistics(guild_id: int, days: int = 7):
        """取得 SLA 統計資料"""
        start_date = datetime.now(timezone.utc) - timedelta(days=days)
        
        async with db_pool.acquire() as conn:
            async with conn.cursor(dictionary=True) as cursor:
                # 基本 SLA 統計
                await cursor.execute(
                    """
                    SELECT 
                        COUNT(DISTINCT t.ticket_id) as total_tickets,
                        COUNT(DISTINCT tr.ticket_id) as responded_tickets,
                        AVG(tr.response_time_minutes) as avg_response_time,
                        SUM(CASE WHEN tr.response_time_minutes <= (
                            CASE t.priority 
                                WHEN 'high' THEN ts.sla_response_minutes * 0.5
                                WHEN 'medium' THEN ts.sla_response_minutes
                                WHEN 'low' THEN ts.sla_response_minutes * 1.5
                            END
                        ) THEN 1 ELSE 0 END) as met_sla,
                        SUM(CASE WHEN tr.response_time_minutes > (
                            CASE t.priority 
                                WHEN 'high' THEN ts.sla_response_minutes * 0.5
                                WHEN 'medium' THEN ts.sla_response_minutes
                                WHEN 'low' THEN ts.sla_response_minutes * 1.5
                            END
                        ) THEN 1 ELSE 0 END) as missed_sla
                    FROM tickets t
                    LEFT JOIN ticket_settings ts ON t.guild_id = ts.guild_id
                    LEFT JOIN ticket_responses tr ON t.ticket_id = tr.ticket_id AND tr.response_type = 'staff'
                    WHERE t.guild_id = %s AND t.created_at >= %s
                    """,
                    (guild_id, start_date)
                )
                basic_stats = await cursor.fetchone()
                
                # 當前超時統計（按優先級）
                await cursor.execute(
                    """
                    SELECT 
                        t.priority,
                        COUNT(*) as count
                    FROM tickets t
                    JOIN ticket_settings ts ON t.guild_id = ts.guild_id
                    LEFT JOIN ticket_responses tr ON t.ticket_id = tr.ticket_id AND tr.response_type = 'staff'
                    WHERE t.guild_id = %s 
                    AND t.status = 'open'
                    AND tr.ticket_id IS NULL
                    AND TIMESTAMPDIFF(MINUTE, t.created_at, NOW()) > (
                        CASE t.priority 
                            WHEN 'high' THEN ts.sla_response_minutes * 0.5
                            WHEN 'medium' THEN ts.sla_response_minutes
                            WHEN 'low' THEN ts.sla_response_minutes * 1.5
                        END
                    )
                    GROUP BY t.priority
                    """,
                    (guild_id,)
                )
                overdue_by_priority = await cursor.fetchall()
                
                # 組裝統計結果
                stats = {
                    'total_tickets': basic_stats['total_tickets'] or 0,
                    'responded_tickets': basic_stats['responded_tickets'] or 0,
                    'avg_response_time': float(basic_stats['avg_response_time'] or 0),
                    'met_sla': basic_stats['met_sla'] or 0,
                    'missed_sla': basic_stats['missed_sla'] or 0,
                    'overdue_high': 0,
                    'overdue_medium': 0,
                    'overdue_low': 0
                }
                
                # 計算 SLA 達標率
                if stats['responded_tickets'] > 0:
                    stats['sla_rate'] = (stats['met_sla'] / stats['responded_tickets']) * 100
                else:
                    stats['sla_rate'] = 0
                
                # 填入超時統計
                for row in overdue_by_priority:
                    stats[f"overdue_{row['priority']}"] = row['count']
                
                return stats

    @staticmethod
    async def get_ticket_sla_info(ticket_id: int):
        """取得票券 SLA 資訊"""
        async with db_pool.acquire() as conn:
            async with conn.cursor(dictionary=True) as cursor:
                await cursor.execute(
                    """
                    SELECT 
                        tr.response_time_minutes as first_response_time,
                        CASE WHEN tr.response_time_minutes <= (
                            CASE t.priority 
                                WHEN 'high' THEN ts.sla_response_minutes * 0.5
                                WHEN 'medium' THEN ts.sla_response_minutes
                                WHEN 'low' THEN ts.sla_response_minutes * 1.5
                            END
                        ) THEN 1 ELSE 0 END as met_sla,
                        (CASE t.priority 
                            WHEN 'high' THEN ts.sla_response_minutes * 0.5
                            WHEN 'medium' THEN ts.sla_response_minutes
                            WHEN 'low' THEN ts.sla_response_minutes * 1.5
                        END) as target_time
                    FROM ticket_responses tr
                    JOIN tickets t ON tr.ticket_id = t.ticket_id
                    JOIN ticket_settings ts ON t.guild_id = ts.guild_id
                    WHERE tr.ticket_id = %s AND tr.response_type = 'staff'
                    ORDER BY tr.created_at ASC
                    LIMIT 1
                    """,
                    (ticket_id,)
                )
                return await cursor.fetchone()

    # ===== 工作量統計 =====
    
    @staticmethod
    async def get_staff_workload_stats(guild_id: int, period: str, staff_id: int = None):
        """取得客服人員工作量統計"""
        # 計算時間範圍
        now = datetime.now(timezone.utc)
        if period == "today":
            start_time = now.replace(hour=0, minute=0, second=0, microsecond=0)
        elif period == "week":
            start_time = now - timedelta(days=7)
        elif period == "month":
            start_time = now - timedelta(days=30)
        else:
            start_time = datetime.min.replace(tzinfo=timezone.utc)
        
        async with db_pool.acquire() as conn:
            async with conn.cursor(dictionary=True) as cursor:
                where_clause = "WHERE t.guild_id = %s AND t.created_at >= %s"
                params = [guild_id, start_time]
                
                if staff_id:
                    where_clause += " AND t.assigned_to = %s"
                    params.append(staff_id)
                
                await cursor.execute(
                    f"""
                    SELECT 
                        t.assigned_to as staff_id,
                        COUNT(*) as handled_tickets,
                        SUM(CASE WHEN t.status = 'closed' THEN 1 ELSE 0 END) as closed_tickets,
                        AVG(CASE WHEN t.closed_at IS NOT NULL THEN 
                            TIMESTAMPDIFF(HOUR, t.created_at, t.closed_at) ELSE NULL END) as avg_handling_time,
                        AVG(CASE WHEN t.rating IS NOT NULL THEN t.rating ELSE NULL END) as avg_rating,
                        SUM(CASE WHEN t.rating = 5 THEN 1 ELSE 0 END) as five_star_count,
                        SUM(CASE WHEN t.rating IS NOT NULL THEN 1 ELSE 0 END) as total_ratings
                    FROM tickets t
                    {where_clause}
                    AND t.assigned_to IS NOT NULL
                    GROUP BY t.assigned_to
                    """,
                    params
                )
                workload_data = await cursor.fetchall()
                
                # 加入 SLA 統計
                stats = {}
                for row in workload_data:
                    if row['staff_id']:
                        staff_id_str = str(row['staff_id'])
                        
                        # 取得該客服的 SLA 統計
                        await cursor.execute(
                            """
                            SELECT 
                                COUNT(*) as total_responses,
                                SUM(CASE WHEN tr.response_time_minutes <= (
                                    CASE t.priority 
                                        WHEN 'high' THEN ts.sla_response_minutes * 0.5
                                        WHEN 'medium' THEN ts.sla_response_minutes
                                        WHEN 'low' THEN ts.sla_response_minutes * 1.5
                                    END
                                ) THEN 1 ELSE 0 END) as met_sla
                            FROM ticket_responses tr
                            JOIN tickets t ON tr.ticket_id = t.ticket_id
                            JOIN ticket_settings ts ON t.guild_id = ts.guild_id
                            WHERE t.guild_id = %s AND tr.staff_id = %s AND tr.created_at >= %s
                            """,
                            (guild_id, row['staff_id'], start_time)
                        )
                        sla_data = await cursor.fetchone()
                        
                        sla_rate = 0
                        if sla_data and sla_data['total_responses'] > 0:
                            sla_rate = (sla_data['met_sla'] / sla_data['total_responses']) * 100
                        
                        stats[staff_id_str] = {
                            'handled_tickets': row['handled_tickets'],
                            'closed_tickets': row['closed_tickets'], 
                            'avg_handling_time': float(row['avg_handling_time']) if row['avg_handling_time'] else 0,
                            'avg_rating': float(row['avg_rating']) if row['avg_rating'] else 0,
                            'five_star_count': row['five_star_count'],
                            'total_ratings': row['total_ratings'],
                            'sla_rate': sla_rate
                        }
                
                return stats

    # ===== 客服專精系統 =====
    
    @staticmethod
    async def get_staff_specialties(staff_id: int, guild_id: int = None):
        """取得客服人員專精"""
        async with db_pool.acquire() as conn:
            async with conn.cursor(dictionary=True) as cursor:
                if guild_id:
                    await cursor.execute(
                        "SELECT specialties FROM staff_specialties WHERE guild_id = %s AND staff_id = %s",
                        (guild_id, staff_id)
                    )
                else:
                    await cursor.execute(
                        "SELECT specialties FROM staff_specialties WHERE staff_id = %s",
                        (staff_id,)
                    )
                
                result = await cursor.fetchone()
                if result and result['specialties']:
                    try:
                        return json.loads(result['specialties'])
                    except:
                        return []
                return []

    @staticmethod
    async def set_staff_specialties(guild_id: int, staff_id: int, specialties: List[str]):
        """設定客服專精"""
        async with db_pool.acquire() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute(
                    """
                    INSERT INTO staff_specialties (guild_id, staff_id, specialties, created_at) 
                    VALUES (%s, %s, %s, NOW()) 
                    ON DUPLICATE KEY UPDATE specialties = %s, updated_at = NOW()
                    """,
                    (guild_id, staff_id, json.dumps(specialties), json.dumps(specialties))
                )
                await conn.commit()
                return cursor.rowcount > 0

    @staticmethod
    async def get_all_staff_specialties(guild_id: int):
        """取得所有客服專精"""
        async with db_pool.acquire() as conn:
            async with conn.cursor(dictionary=True) as cursor:
                await cursor.execute(
                    "SELECT staff_id, specialties FROM staff_specialties WHERE guild_id = %s",
                    (guild_id,)
                )
                results = await cursor.fetchall()
                
                specialties_map = {}
                for row in results:
                    if row['specialties']:
                        try:
                            specialties_map[str(row['staff_id'])] = json.loads(row['specialties'])
                        except:
                            specialties_map[str(row['staff_id'])] = []
                
                return specialties_map

    # ===== 標籤系統 =====
    
    @staticmethod
    async def add_tags_to_ticket(ticket_id: int, tags: List[str]):
        """為票券添加標籤"""
        async with db_pool.acquire() as conn:
            async with conn.cursor() as cursor:
                # 取得現有標籤
                await cursor.execute("SELECT tags FROM tickets WHERE ticket_id = %s", (ticket_id,))
                result = await cursor.fetchone()
                
                if not result:
                    return False
                
                existing_tags = json.loads(result[0]) if result[0] else []
                
                # 合併新標籤並去重
                new_tags = list(set(existing_tags + tags))
                
                # 更新標籤
                await cursor.execute(
                    "UPDATE tickets SET tags = %s WHERE ticket_id = %s",
                    (json.dumps(new_tags), ticket_id)
                )
                
                # 記錄標籤添加日誌
                await cursor.execute(
                    """
                    INSERT INTO ticket_logs (ticket_id, action, details, created_by, created_at)
                    VALUES (%s, 'tag_added', %s, %s, NOW())
                    """,
                    (ticket_id, f"添加標籤: {', '.join(tags)}", "system")
                )
                
                await conn.commit()
                return cursor.rowcount > 0

    @staticmethod
    async def get_ticket_tags(ticket_id: int) -> List[str]:
        """取得票券標籤"""
        async with db_pool.acquire() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute(
                    "SELECT tags FROM tickets WHERE ticket_id = %s",
                    (ticket_id,)
                )
                result = await cursor.fetchone()
                
                if result and result[0]:
                    try:
                        return json.loads(result[0])
                    except:
                        return []
                return []

    # ===== 批次操作 =====
    
    @staticmethod
    async def close_inactive_tickets(guild_id: int, hours_threshold: int) -> int:
        """關閉無活動的票券"""
        cutoff_time = datetime.now(timezone.utc) - timedelta(hours=hours_threshold)
        
        async with db_pool.acquire() as conn:
            async with conn.cursor() as cursor:
                # 先獲取要關閉的票券列表
                await cursor.execute(
                    """
                    SELECT ticket_id FROM tickets
                    WHERE guild_id = %s 
                    AND status = 'open'
                    AND last_activity < %s
                    """,
                    (guild_id, cutoff_time)
                )
                tickets_to_close = await cursor.fetchall()
                
                if not tickets_to_close:
                    return 0
                
                # 批次關閉
                await cursor.execute(
                    """
                    UPDATE tickets 
                    SET status = 'closed', closed_at = NOW(), closed_by = 'system',
                        close_reason = '自動關閉：超過無活動時間限制'
                    WHERE guild_id = %s 
                    AND status = 'open'
                    AND last_activity < %s
                    """,
                    (guild_id, cutoff_time)
                )
                closed_count = cursor.rowcount
                
                # 記錄批次關閉日誌
                for ticket in tickets_to_close:
                    await cursor.execute(
                        """
                        INSERT INTO ticket_logs (ticket_id, action, details, created_by, created_at)
                        VALUES (%s, 'closed', %s, %s, NOW())
                        """,
                        (ticket[0], f"自動關閉：無活動超過 {hours_threshold} 小時", "system")
                    )
                
                await conn.commit()
                return closed_count

    # ===== 匯出功能 =====
    
    @staticmethod
    async def export_tickets_data(guild_id: int, status: str = None, start_date: datetime = None, end_date: datetime = None) -> List[Dict[str, Any]]:
        """匯出票券資料"""
        where_conditions = ["guild_id = %s"]
        params = [guild_id]
        
        if status and status != "all":
            where_conditions.append("status = %s")
            params.append(status)
        
        if start_date:
            where_conditions.append("created_at >= %s")
            params.append(start_date)
        
        if end_date:
            where_conditions.append("created_at <= %s")
            params.append(end_date)
        
        where_clause = " AND ".join(where_conditions)
        
        async with db_pool.acquire() as conn:
            async with conn.cursor(dictionary=True) as cursor:
                await cursor.execute(
                    f"""
                    SELECT 
                        ticket_id, discord_id, username, type, priority, status,
                        created_at, closed_at, closed_by, close_reason,
                        assigned_to, rating, rating_feedback, tags
                    FROM tickets
                    WHERE {where_clause}
                    ORDER BY ticket_id DESC
                    """,
                    params
                )
                return await cursor.fetchall()

    # ===== 清理維護 =====
    
    @staticmethod
    async def cleanup_old_data(days_threshold: int = 90):
        """清理舊資料"""
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=days_threshold)
        
        async with db_pool.acquire() as conn:
            async with conn.cursor() as cursor:
                cleaned_count = 0
                
                # 清理舊的查看記錄
                await cursor.execute(
                    "DELETE FROM ticket_views WHERE viewed_at < %s",
                    (cutoff_date,)
                )
                cleaned_count += cursor.rowcount
                
                # 清理舊的自動回覆日誌
                await cursor.execute(
                    "DELETE FROM auto_reply_logs WHERE created_at < %s",
                    (cutoff_date,)
                )
                cleaned_count += cursor.rowcount
                
                # 清理過期的統計快取
                await cursor.execute(
                    "DELETE FROM ticket_statistics_cache WHERE expires_at < NOW()"
                )
                cleaned_count += cursor.rowcount
                
                await conn.commit()
                debug_log(f"[TicketDAO] 清理了 {cleaned_count} 條舊資料")
                return cleaned_count