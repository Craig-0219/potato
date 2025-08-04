# bot/db/ticket_dao.py - 簡化的票券資料存取層
"""
票券資料存取層 - 簡化版
專注於核心的 CRUD 操作，移除過度複雜的查詢
"""

from bot.db.pool import db_pool
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Any, Tuple
import json
from shared.logger import logger


class TicketDAO:
    """票券資料存取層"""
    
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
                    await db_manager._create_ticket_tables()
                
                self._initialized = True
                logger.info("✅ 票券 DAO 初始化完成")
                
            except Exception as e:
                logger.error(f"❌ 票券 DAO 初始化失敗：{e}")
                raise
    # ===== 資料表管理 =====
    
    async def create_tables(self):
        await self._ensure_initialized()
        """建立資料表"""
        async with self.db.acquire() as conn:
            async with conn.cursor() as cursor:
                # 主票券表
                await cursor.execute("""
                    CREATE TABLE IF NOT EXISTS tickets (
                        id INT AUTO_INCREMENT PRIMARY KEY,
                        discord_id VARCHAR(20) NOT NULL COMMENT '開票者 Discord ID',
                        username VARCHAR(100) NOT NULL COMMENT '開票者用戶名',
                        type VARCHAR(50) NOT NULL COMMENT '票券類型',
                        priority ENUM('high', 'medium', 'low') DEFAULT 'medium' COMMENT '優先級',
                        status ENUM('open', 'closed') DEFAULT 'open' COMMENT '狀態',
                        channel_id BIGINT NOT NULL COMMENT '頻道 ID',
                        guild_id BIGINT NOT NULL COMMENT '伺服器 ID',
                        assigned_to BIGINT NULL COMMENT '指派的客服 ID',
                        rating INT NULL CHECK (rating BETWEEN 1 AND 5) COMMENT '評分',
                        rating_feedback TEXT NULL COMMENT '評分回饋',
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '建立時間',
                        closed_at TIMESTAMP NULL COMMENT '關閉時間',
                        closed_by VARCHAR(20) NULL COMMENT '關閉者 ID',
                        close_reason TEXT NULL COMMENT '關閉原因',
                        
                        INDEX idx_guild_status (guild_id, status),
                        INDEX idx_assigned (assigned_to),
                        INDEX idx_created (created_at),
                        INDEX idx_channel (channel_id)
                    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
                """)
                
                # 系統設定表
                await cursor.execute("""
                    CREATE TABLE IF NOT EXISTS ticket_settings (
                        guild_id BIGINT PRIMARY KEY COMMENT '伺服器 ID',
                        category_id BIGINT NULL COMMENT '分類頻道 ID',
                        support_roles JSON NULL COMMENT '客服身分組列表',
                        max_tickets_per_user INT DEFAULT 3 COMMENT '每人最大票券數',
                        auto_close_hours INT DEFAULT 24 COMMENT '自動關閉小時數',
                        sla_response_minutes INT DEFAULT 60 COMMENT 'SLA 回應時間',
                        welcome_message TEXT NULL COMMENT '歡迎訊息',
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
                    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
                """)
                
                # 操作日誌表
                await cursor.execute("""
                    CREATE TABLE IF NOT EXISTS ticket_logs (
                        id INT AUTO_INCREMENT PRIMARY KEY,
                        ticket_id INT NOT NULL COMMENT '票券 ID',
                        action VARCHAR(50) NOT NULL COMMENT '操作類型',
                        details TEXT NULL COMMENT '操作詳情',
                        created_by VARCHAR(20) NULL COMMENT '操作者 ID',
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        
                        FOREIGN KEY (ticket_id) REFERENCES tickets(id) ON DELETE CASCADE,
                        INDEX idx_ticket (ticket_id),
                        INDEX idx_action (action)
                    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
                """)
                
                await conn.commit()
                logger.info("票券資料表建立完成")

    # ===== 票券 CRUD 操作 =====
    
    async def create_ticket(self, discord_id: str, username: str, ticket_type: str, 
                           channel_id: int, guild_id: int, priority: str = 'medium') -> Optional[int]:
            await self._ensure_initialized()
        """建立新票券"""
        try:
            async with self.db.acquire() as conn:
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
    
    async def get_ticket_by_id(self, ticket_id: int) -> Optional[Dict[str, Any]]:
        await self._ensure_initialized()
        """根據 ID 取得票券"""
        try:
            async with self.db.acquire() as conn:
                async with conn.cursor(dictionary=True) as cursor:
                    await cursor.execute(
                        "SELECT * FROM tickets WHERE id = %s", (ticket_id,)
                    )
                    return await cursor.fetchone()
        except Exception as e:
            logger.error(f"查詢票券錯誤：{e}")
            return None
    
    async def get_ticket_by_channel(self, channel_id: int) -> Optional[Dict[str, Any]]:
        await self._ensure_initialized()
        """根據頻道 ID 取得票券"""
        try:
            async with self.db.acquire() as conn:
                async with conn.cursor(dictionary=True) as cursor:
                    await cursor.execute(
                        "SELECT * FROM tickets WHERE channel_id = %s", (channel_id,)
                    )
                    return await cursor.fetchone()
        except Exception as e:
            logger.error(f"查詢票券錯誤：{e}")
            return None
    
    async def get_tickets(self, guild_id: int, user_id: int = None, status: str = "all", 
                         page: int = 1, page_size: int = 10) -> Tuple[List[Dict], int]:
        await self._ensure_initialized()
        """分頁查詢票券"""
        try:
            where_conditions = ["guild_id = %s"]
            params = [guild_id]
            
            if user_id:
                where_conditions.append("discord_id = %s")
                params.append(str(user_id))
            
            if status in ("open", "closed"):
                where_conditions.append("status = %s")
                params.append(status)
            
            where_clause = " AND ".join(where_conditions)
            
            async with self.db.acquire() as conn:
                async with conn.cursor(dictionary=True) as cursor:
                    # 總數查詢
                    await cursor.execute(f"SELECT COUNT(*) as total FROM tickets WHERE {where_clause}", params)
                    total = (await cursor.fetchone())["total"]
                    
                    # 分頁查詢
                    offset = (page - 1) * page_size
                    await cursor.execute(f"""
                        SELECT * FROM tickets WHERE {where_clause}
                        ORDER BY 
                            CASE WHEN status = 'open' THEN 0 ELSE 1 END,
                            CASE priority WHEN 'high' THEN 1 WHEN 'medium' THEN 2 ELSE 3 END,
                            created_at DESC
                        LIMIT %s OFFSET %s
                    """, params + [page_size, offset])
                    
                    tickets = await cursor.fetchall()
                    return tickets, total
                    
        except Exception as e:
            logger.error(f"查詢票券列表錯誤：{e}")
            return [], 0
    
    async def close_ticket(self, ticket_id: int, closed_by: int, reason: str = None) -> bool:
        await self._ensure_initialized()
        """關閉票券"""
        try:
            async with self.db.acquire() as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute("""
                        UPDATE tickets 
                        SET status = 'closed', closed_at = NOW(), closed_by = %s, close_reason = %s
                        WHERE id = %s AND status = 'open'
                    """, (str(closed_by), reason, ticket_id))
                    
                    if cursor.rowcount > 0:
                        # 記錄日誌
                        await cursor.execute("""
                            INSERT INTO ticket_logs (ticket_id, action, details, created_by)
                            VALUES (%s, 'closed', %s, %s)
                        """, (ticket_id, f"關閉票券 - {reason or '無原因'}", str(closed_by)))
                        
                        await conn.commit()
                        logger.info(f"關閉票券 #{ticket_id:04d}")
                        return True
                    
            return False
            
        except Exception as e:
            logger.error(f"關閉票券錯誤：{e}")
            return False
    
    async def assign_ticket(self, ticket_id: int, assigned_to: int, assigned_by: int) -> bool:
        await self._ensure_initialized()
        """指派票券"""
        try:
            async with self.db.acquire() as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute("""
                        UPDATE tickets SET assigned_to = %s WHERE id = %s
                    """, (assigned_to, ticket_id))
                    
                    # 記錄日誌
                    await cursor.execute("""
                        INSERT INTO ticket_logs (ticket_id, action, details, created_by)
                        VALUES (%s, 'assigned', %s, %s)
                    """, (ticket_id, f"指派給 {assigned_to}", str(assigned_by)))
                    
                    await conn.commit()
                    return cursor.rowcount > 0
                    
        except Exception as e:
            logger.error(f"指派票券錯誤：{e}")
            return False
    
    async def update_ticket_priority(self, ticket_id: int, priority: str) -> bool:
        await self._ensure_initialized()
        """更新票券優先級"""
        try:
            async with self.db.acquire() as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute("""
                        UPDATE tickets SET priority = %s WHERE id = %s
                    """, (priority, ticket_id))
                    
                    # 記錄日誌
                    await cursor.execute("""
                        INSERT INTO ticket_logs (ticket_id, action, details, created_by)
                        VALUES (%s, 'priority_change', %s, 'system')
                    """, (ticket_id, f"優先級變更為 {priority}"))
                    
                    await conn.commit()
                    return cursor.rowcount > 0
                    
        except Exception as e:
            logger.error(f"更新優先級錯誤：{e}")
            return False
    
    async def save_rating(self, ticket_id: int, rating: int, feedback: str = None) -> bool:
        await self._ensure_initialized()
        """保存評分"""
        try:
            async with self.db.acquire() as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute("""
                        UPDATE tickets SET rating = %s, rating_feedback = %s 
                        WHERE id = %s AND status = 'closed'
                    """, (rating, feedback, ticket_id))
                    
                    if cursor.rowcount > 0:
                        # 記錄日誌
                        await cursor.execute("""
                            INSERT INTO ticket_logs (ticket_id, action, details, created_by)
                            VALUES (%s, 'rating', %s, 'user')
                        """, (ticket_id, f"評分 {rating}/5"))
                        
                        await conn.commit()
                        return True
                    
            return False
            
        except Exception as e:
            logger.error(f"保存評分錯誤：{e}")
            return False
    
    # ===== 統計查詢 =====
    
    async def get_statistics(self, guild_id: int) -> Dict[str, Any]:
        await self._ensure_initialized()
        """取得基本統計"""
        try:
            async with self.db.acquire() as conn:
                async with conn.cursor(dictionary=True) as cursor:
                    await cursor.execute("""
                        SELECT 
                            COUNT(*) as total,
                            SUM(CASE WHEN status = 'open' THEN 1 ELSE 0 END) as open,
                            SUM(CASE WHEN status = 'closed' THEN 1 ELSE 0 END) as closed,
                            SUM(CASE WHEN DATE(created_at) = CURDATE() THEN 1 ELSE 0 END) as today,
                            AVG(CASE WHEN rating IS NOT NULL THEN rating END) as avg_rating,
                            COUNT(CASE WHEN rating IS NOT NULL THEN 1 END) as total_ratings,
                            COUNT(CASE WHEN rating >= 4 THEN 1 END) as satisfied_ratings
                        FROM tickets WHERE guild_id = %s
                    """, (guild_id,))
                    
                    stats = await cursor.fetchone()
                    
                    # 計算滿意度
                    if stats['total_ratings'] > 0:
                        stats['satisfaction_rate'] = (stats['satisfied_ratings'] / stats['total_ratings']) * 100
                    else:
                        stats['satisfaction_rate'] = 0
                    
                    return stats or {}
                    
        except Exception as e:
            logger.error(f"取得統計錯誤：{e}")
            return {}
    
    async def get_user_ticket_count(self, user_id: int, guild_id: int, status: str = "open") -> int:
        await self._ensure_initialized()
        """取得用戶票券數量"""
        try:
            async with self.db.acquire() as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute("""
                        SELECT COUNT(*) FROM tickets 
                        WHERE discord_id = %s AND guild_id = %s AND status = %s
                    """, (str(user_id), guild_id, status))
                    
                    result = await cursor.fetchone()
                    return result[0] if result else 0
                    
        except Exception as e:
            logger.error(f"查詢用戶票券數量錯誤：{e}")
            return 0
    
    async def get_overdue_tickets(self) -> List[Dict[str, Any]]:
        await self._ensure_initialized()
        """取得超時票券"""
        try:
            async with self.db.acquire() as conn:
                async with conn.cursor(dictionary=True) as cursor:
                    await cursor.execute("""
                        SELECT t.*, ts.sla_response_minutes
                        FROM tickets t
                        JOIN ticket_settings ts ON t.guild_id = ts.guild_id
                        WHERE t.status = 'open'
                        AND TIMESTAMPDIFF(MINUTE, t.created_at, NOW()) > (
                            CASE t.priority 
                                WHEN 'high' THEN ts.sla_response_minutes * 0.5
                                WHEN 'medium' THEN ts.sla_response_minutes
                                WHEN 'low' THEN ts.sla_response_minutes * 1.5
                            END
                        )
                        AND t.assigned_to IS NULL
                    """)
                    
                    return await cursor.fetchall()
                    
        except Exception as e:
            logger.error(f"查詢超時票券錯誤：{e}")
            return []
    
    # ===== 設定管理 =====
    
    async def get_settings(self, guild_id: int) -> Dict[str, Any]:
        await self._ensure_initialized()
        """取得伺服器設定"""
        try:
            async with self.db.acquire() as conn:
                async with conn.cursor(dictionary=True) as cursor:
                    await cursor.execute(
                        "SELECT * FROM ticket_settings WHERE guild_id = %s", (guild_id,)
                    )
                    
                    settings = await cursor.fetchone()
                    
                    if not settings:
                        # 建立預設設定
                        return await self.create_default_settings(guild_id)
                    
                    # 解析 JSON 欄位
                    if settings.get('support_roles'):
                        try:
                            settings['support_roles'] = json.loads(settings['support_roles'])
                        except:
                            settings['support_roles'] = []
                    
                    return settings
                    
        except Exception as e:
            logger.error(f"取得設定錯誤：{e}")
            return await self.create_default_settings(guild_id)
    
    async def create_default_settings(self, guild_id: int) -> Dict[str, Any]:
        await self._ensure_initialized()
        """建立預設設定"""
        default_settings = {
            'guild_id': guild_id,
            'max_tickets_per_user': 3,
            'auto_close_hours': 24,
            'sla_response_minutes': 60,
            'welcome_message': "歡迎使用客服系統！請選擇問題類型來建立支援票券。",
            'support_roles': []
        }
        
        try:
            async with self.db.acquire() as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute("""
                        INSERT INTO ticket_settings 
                        (guild_id, max_tickets_per_user, auto_close_hours, sla_response_minutes, welcome_message, support_roles)
                        VALUES (%s, %s, %s, %s, %s, %s)
                    """, (
                        guild_id,
                        default_settings['max_tickets_per_user'],
                        default_settings['auto_close_hours'],
                        default_settings['sla_response_minutes'],
                        default_settings['welcome_message'],
                        json.dumps(default_settings['support_roles'])
                    ))
                    
                    await conn.commit()
                    logger.info(f"建立預設設定 - 伺服器: {guild_id}")
                    
        except Exception as e:
            logger.error(f"建立預設設定錯誤：{e}")
        
        return default_settings
    
    async def update_setting(self, guild_id: int, setting: str, value: Any) -> bool:
        await self._ensure_initialized()
        """更新設定"""
        try:
            # 設定映射
            setting_map = {
                'category': 'category_id',
                'support_roles': 'support_roles',
                'limits': 'max_tickets_per_user',
                'auto_close': 'auto_close_hours',
                'sla_response': 'sla_response_minutes',
                'welcome': 'welcome_message'
            }
            
            if setting not in setting_map:
                return False
            
            db_field = setting_map[setting]
            
            # 處理特殊類型
            if setting == 'support_roles' and isinstance(value, list):
                value = json.dumps(value)
            elif setting in ['limits', 'auto_close', 'sla_response']:
                value = int(value)
            elif setting == 'category':
                value = int(value)
            
            async with self.db.acquire() as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute(f"""
                        UPDATE ticket_settings 
                        SET {db_field} = %s, updated_at = NOW() 
                        WHERE guild_id = %s
                    """, (value, guild_id))
                    
                    await conn.commit()
                    return cursor.rowcount > 0
                    
        except Exception as e:
            logger.error(f"更新設定錯誤：{e}")
            return False
    
    # ===== 工具方法 =====
    
    async def get_next_ticket_id(self) -> int:
        await self._ensure_initialized()
        """取得下一個票券 ID"""
        try:
            async with self.db.acquire() as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute("SELECT MAX(id) FROM tickets")
                    result = await cursor.fetchone()
                    return (result[0] or 0) + 1
        except Exception as e:
            logger.error(f"取得票券 ID 錯誤：{e}")
            return 1
    
    async def cleanup_old_data(self, days: int = 90) -> int:
        await self._ensure_initialized()
        """清理舊資料"""
        try:
            cutoff_date = datetime.now(timezone.utc) - timedelta(days=days)
            
            async with self.db.acquire() as conn:
                async with conn.cursor() as cursor:
                    # 清理舊的日誌記錄
                    await cursor.execute("""
                        DELETE FROM ticket_logs 
                        WHERE created_at < %s
                    """, (cutoff_date,))
                    
                    cleaned_count = cursor.rowcount
                    await conn.commit()
                    
                    logger.info(f"清理了 {cleaned_count} 條舊資料")
                    return cleaned_count
                    
        except Exception as e:
            logger.error(f"清理資料錯誤：{e}")
            return 0
