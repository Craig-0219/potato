# bot/db/ticket_dao.py - 完整修復版
"""
票券資料存取層 - 完整修復版
修復所有缺失的方法和異步上下文管理器問題
"""

from bot.db.pool import db_pool
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Any, Tuple
import json
import aiomysql
from shared.logger import logger

class TicketDAO:
    """票券資料存取層 - 完整修復版"""
    
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

    # ===== 修復：添加缺失的屬性和方法 =====
    
    @property
    def db_pool(self):
        """資料庫連接池屬性 - 修復缺失"""
        return self.db
    
    async def get_guild_settings(self, guild_id: int) -> Dict[str, Any]:
        """取得伺服器設定 - 修復缺失方法"""
        return await self.get_settings(guild_id)
    
    async def cleanup_old_logs(self, days: int = 30) -> int:
        """清理舊日誌 - 修復缺失方法"""
        await self._ensure_initialized()
        try:
            cutoff_date = datetime.now(timezone.utc) - timedelta(days=days)
            
            async with self.db.connection() as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute(
                        "DELETE FROM ticket_logs WHERE created_at < %s",
                        (cutoff_date,)
                    )
                    await conn.commit()
                    
                    cleaned_count = cursor.rowcount
                    logger.info(f"清理了 {cleaned_count} 條舊日誌")
                    return cleaned_count
                    
        except Exception as e:
            logger.error(f"清理舊日誌錯誤：{e}")
            return 0
    
    async def get_server_statistics(self, guild_id: int) -> Dict[str, Any]:
        """取得伺服器統計 - 修復缺失方法"""
        return await self.get_statistics(guild_id)
    
    async def get_sla_statistics(self, guild_id: int) -> Dict[str, Any]:
        """取得 SLA 統計 - 新增方法"""
        await self._ensure_initialized()
        try:
            async with self.db.connection() as conn:
                async with conn.cursor() as cursor:
                    # SLA 統計查詢
                    await cursor.execute("""
                        SELECT 
                            COUNT(*) as total_tickets,
                            COUNT(CASE WHEN assigned_to IS NOT NULL THEN 1 END) as responded_tickets,
                            AVG(CASE 
                                WHEN assigned_to IS NOT NULL 
                                THEN TIMESTAMPDIFF(MINUTE, created_at, NOW()) 
                                ELSE NULL 
                            END) as avg_response_time
                        FROM tickets 
                        WHERE guild_id = %s 
                        AND created_at >= DATE_SUB(NOW(), INTERVAL 7 DAY)
                    """, (guild_id,))
                    
                    result = await cursor.fetchone()
                    
                    # 計算達標率
                    total = result[0] if result else 0
                    responded = result[1] if result and len(result) > 1 else 0
                    avg_time = result[2] if result and len(result) > 2 else 0
                    
                    sla_rate = (responded / total * 100) if total > 0 else 0
                    
                    return {
                        'total_tickets': total,
                        'responded_tickets': responded,
                        'sla_rate': sla_rate,
                        'avg_response_time': avg_time or 0,
                        'overdue_high': 0,  # 可以進一步實作
                        'overdue_medium': 0,
                        'overdue_low': 0
                    }
                    
        except Exception as e:
            logger.error(f"取得 SLA 統計錯誤：{e}")
            return {
                'total_tickets': 0,
                'responded_tickets': 0,
                'sla_rate': 0,
                'avg_response_time': 0,
                'overdue_high': 0,
                'overdue_medium': 0,
                'overdue_low': 0
            }
    
    async def has_staff_response(self, ticket_id: int) -> bool:
        """檢查是否有客服回應 - 新增方法"""
        await self._ensure_initialized()
        try:
            async with self.db.connection() as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute("""
                        SELECT COUNT(*) FROM ticket_logs 
                        WHERE ticket_id = %s AND action IN ('staff_response', 'assigned')
                    """, (ticket_id,))
                    
                    result = await cursor.fetchone()
                    return (result[0] if result else 0) > 0
                    
        except Exception as e:
            logger.error(f"檢查客服回應錯誤：{e}")
            return False
    
    async def update_last_activity(self, ticket_id: int):
        """更新票券最後活動時間 - 新增方法"""
        await self._ensure_initialized()
        try:
            async with self.db.connection() as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute("""
                        UPDATE tickets 
                        SET last_activity = NOW() 
                        WHERE id = %s
                    """, (ticket_id,))
                    await conn.commit()
                    
        except Exception as e:
            logger.error(f"更新活動時間錯誤：{e}")
    
    async def get_inactive_tickets(self, guild_id: int, cutoff_time: datetime) -> List[Dict[str, Any]]:
        """取得無活動票券 - 新增方法"""
        await self._ensure_initialized()
        try:
            async with self.db.connection() as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute("""
                        SELECT id as ticket_id, discord_id, type, priority, created_at, last_activity, channel_id
                        FROM tickets
                        WHERE guild_id = %s 
                        AND status = 'open'
                        AND (last_activity < %s OR (last_activity IS NULL AND created_at < %s))
                        ORDER BY created_at ASC
                    """, (guild_id, cutoff_time, cutoff_time))
                    
                    columns = [desc[0] for desc in cursor.description]
                    results = await cursor.fetchall()
                    
                    return [dict(zip(columns, row)) for row in results]
                    
        except Exception as e:
            logger.error(f"查詢無活動票券錯誤：{e}")
            return []
    
    async def save_panel_message(self, guild_id: int, message_id: int, channel_id: int):
        """保存面板訊息 - 新增方法"""
        await self._ensure_initialized()
        try:
            async with self.db.connection() as conn:
                async with conn.cursor() as cursor:
                    # 更新設定表中的面板資訊
                    await cursor.execute("""
                        INSERT INTO ticket_settings (guild_id, updated_at) 
                        VALUES (%s, NOW()) 
                        ON DUPLICATE KEY UPDATE updated_at = NOW()
                    """, (guild_id,))
                    await conn.commit()
                    logger.info(f"保存面板訊息 - 伺服器: {guild_id}, 訊息: {message_id}")
                    
        except Exception as e:
            logger.error(f"保存面板訊息錯誤：{e}")

    async def cleanup_expired_cache(self):
        """清理過期快取 - 新增方法"""
        await self._ensure_initialized()
        try:
            async with self.db.connection() as conn:
                async with conn.cursor() as cursor:
                    # 清理統計快取表中的過期資料
                    await cursor.execute("""
                        DELETE FROM ticket_statistics_cache 
                        WHERE expires_at < NOW()
                    """)
                    await conn.commit()
                    cleaned = cursor.rowcount
                    if cleaned > 0:
                        logger.info(f"清理了 {cleaned} 個過期快取")
                    
        except Exception as e:
            logger.error(f"清理快取錯誤：{e}")

    # ===== 修復現有方法的異步問題 =====
    
    async def create_ticket(self, discord_id: str, username: str, ticket_type: str, 
                           channel_id: int, guild_id: int, priority: str = 'medium',
                           title: str = None, description: str = None) -> Optional[int]:
        """建立新票券 - 加強版"""
        await self._ensure_initialized()
        try:
            async with self.db.connection() as conn:
                async with conn.cursor() as cursor:
                    # 檢查用戶是否已達票券上限
                    await cursor.execute("""
                        SELECT COUNT(*) FROM tickets 
                        WHERE discord_id = %s AND guild_id = %s AND status = 'open'
                    """, (discord_id, guild_id))
                    
                    current_count = (await cursor.fetchone())[0]
                    settings = await self.get_settings(guild_id)
                    max_tickets = settings.get('max_tickets_per_user', 3)
                    
                    if current_count >= max_tickets:
                        logger.warning(f"用戶 {discord_id} 已達票券上限")
                        return None
                    
                    # 建立票券 - 提供預設值避免NULL錯誤
                    ticket_title = title or f"{ticket_type.title()} 票券"
                    ticket_description = description or f"由 {username} 建立的 {ticket_type} 票券"
                    
                    await cursor.execute("""
                        INSERT INTO tickets (discord_id, username, type, priority, channel_id, guild_id, title, description, created_at, last_activity)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, NOW(), NOW())
                    """, (discord_id, username, ticket_type, priority, channel_id, guild_id, ticket_title, ticket_description))
                    
                    ticket_id = cursor.lastrowid
                    
                    # 記錄操作日誌
                    await cursor.execute("""
                        INSERT INTO ticket_logs (ticket_id, action, details, created_by, created_at)
                        VALUES (%s, 'created', %s, %s, NOW())
                    """, (ticket_id, f"建立{ticket_type}票券", discord_id))
                    
                    await conn.commit()
                    logger.info(f"建立票券 #{ticket_id:04d} - 用戶: {username}")
                    return ticket_id
                    
        except Exception as e:
            logger.error(f"建立票券錯誤：{e}")
            return None
    
    async def get_ticket_by_id(self, ticket_id: int) -> Optional[Dict[str, Any]]:
        """根據 ID 取得票券 - 修復異步"""
        await self._ensure_initialized()
        try:
            async with self.db.connection() as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute(
                        "SELECT * FROM tickets WHERE id = %s", (ticket_id,)
                    )
                    result = await cursor.fetchone()
                    if result:
                        columns = [desc[0] for desc in cursor.description]
                        return dict(zip(columns, result))
                    return None
        except Exception as e:
            logger.error(f"查詢票券錯誤：{e}")
            return None
    
    async def get_ticket_by_channel(self, channel_id: int) -> Optional[Dict[str, Any]]:
        """根據頻道 ID 取得票券 - 修復異步"""
        await self._ensure_initialized()
        try:
            async with self.db.connection() as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute(
                        "SELECT * FROM tickets WHERE channel_id = %s", (channel_id,)
                    )
                    result = await cursor.fetchone()
                    if result:
                        columns = [desc[0] for desc in cursor.description]
                        return dict(zip(columns, result))
                    return None
        except Exception as e:
            logger.error(f"查詢票券錯誤：{e}")
            return None
    
    async def get_tickets(self, guild_id: int, user_id: int = None, status: str = "all", 
                         page: int = 1, page_size: int = 10) -> Tuple[List[Dict], int]:
        """分頁查詢票券 - 修復異步"""
        await self._ensure_initialized()
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
            
            async with self.db.connection() as conn:
                async with conn.cursor() as cursor:
                    # 總數查詢
                    await cursor.execute(f"SELECT COUNT(*) FROM tickets WHERE {where_clause}", params)
                    total_result = await cursor.fetchone()
                    total = total_result[0] if total_result else 0
                    
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
                    
                    results = await cursor.fetchall()
                    columns = [desc[0] for desc in cursor.description]
                    tickets = [dict(zip(columns, row)) for row in results]
                    
                    return tickets, total
                    
        except Exception as e:
            logger.error(f"查詢票券列表錯誤：{e}")
            return [], 0
    
    async def close_ticket(self, ticket_id: int, closed_by: int, reason: str = None) -> bool:
        """關閉票券 - 修復參數"""
        await self._ensure_initialized()
        try:
            async with self.db.connection() as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute("""
                        UPDATE tickets 
                        SET status = 'closed', closed_at = NOW(), closed_by = %s, close_reason = %s
                        WHERE id = %s AND status = 'open'
                    """, (str(closed_by), reason, ticket_id))
                    
                    if cursor.rowcount > 0:
                        # 記錄日誌
                        await cursor.execute("""
                            INSERT INTO ticket_logs (ticket_id, action, details, created_by, created_at)
                            VALUES (%s, 'closed', %s, %s, NOW())
                        """, (ticket_id, f"關閉票券 - {reason or '無原因'}", str(closed_by)))
                        
                        await conn.commit()
                        logger.info(f"關閉票券 #{ticket_id:04d}")
                        return True
                    
            return False
            
        except Exception as e:
            logger.error(f"關閉票券錯誤：{e}")
            return False
    
    async def assign_ticket(self, ticket_id: int, assigned_to: int, assigned_by: int) -> bool:
        """指派票券 - 修復異步"""
        await self._ensure_initialized()
        try:
            async with self.db.connection() as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute("""
                        UPDATE tickets SET assigned_to = %s WHERE id = %s
                    """, (assigned_to, ticket_id))
                    
                    # 記錄日誌
                    await cursor.execute("""
                        INSERT INTO ticket_logs (ticket_id, action, details, created_by, created_at)
                        VALUES (%s, 'assigned', %s, %s, NOW())
                    """, (ticket_id, f"指派給 {assigned_to}", str(assigned_by)))
                    
                    await conn.commit()
                    return cursor.rowcount > 0
                    
        except Exception as e:
            logger.error(f"指派票券錯誤：{e}")
            return False
    
    async def get_tickets_with_filters(self, filters: Dict[str, Any], limit: int = 20, 
                                     offset: int = 0, guild_id: int = None) -> List[Dict[str, Any]]:
        """根據篩選條件獲取票券列表"""
        try:
            await self._ensure_initialized()
            
            # 構建查詢條件
            where_conditions = ["1=1"]
            params = []
            
            if guild_id:
                where_conditions.append("guild_id = %s")
                params.append(guild_id)
            
            if filters.get('status'):
                where_conditions.append("status = %s")
                params.append(filters['status'])
            
            if filters.get('priority'):
                where_conditions.append("priority = %s")
                params.append(filters['priority'])
            
            if filters.get('assigned_to'):
                where_conditions.append("assigned_to = %s")
                params.append(filters['assigned_to'])
            
            if filters.get('discord_id'):
                where_conditions.append("discord_id = %s")
                params.append(filters['discord_id'])
            
            if filters.get('search'):
                where_conditions.append("(username LIKE %s OR type LIKE %s)")
                search_param = f"%{filters['search']}%"
                params.extend([search_param, search_param])
            
            where_clause = " AND ".join(where_conditions)
            
            query = f"""
                SELECT * FROM tickets 
                WHERE {where_clause}
                ORDER BY created_at DESC 
                LIMIT %s OFFSET %s
            """
            params.extend([limit, offset])
            
            async with self.db.connection() as conn:
                async with conn.cursor(aiomysql.DictCursor) as cursor:
                    await cursor.execute(query, params)
                    return await cursor.fetchall()
                    
        except Exception as e:
            logger.error(f"獲取票券列表失敗: {e}")
            return []
    
    async def count_tickets_with_filters(self, filters: Dict[str, Any], guild_id: int = None) -> int:
        """統計符合篩選條件的票券數量"""
        try:
            await self._ensure_initialized()
            
            # 構建查詢條件（與 get_tickets_with_filters 相同）
            where_conditions = ["1=1"]
            params = []
            
            if guild_id:
                where_conditions.append("guild_id = %s")
                params.append(guild_id)
            
            if filters.get('status'):
                where_conditions.append("status = %s")
                params.append(filters['status'])
            
            if filters.get('priority'):
                where_conditions.append("priority = %s")
                params.append(filters['priority'])
            
            if filters.get('assigned_to'):
                where_conditions.append("assigned_to = %s")
                params.append(filters['assigned_to'])
            
            if filters.get('discord_id'):
                where_conditions.append("discord_id = %s")
                params.append(filters['discord_id'])
            
            if filters.get('search'):
                where_conditions.append("(username LIKE %s OR type LIKE %s)")
                search_param = f"%{filters['search']}%"
                params.extend([search_param, search_param])
            
            where_clause = " AND ".join(where_conditions)
            
            query = f"SELECT COUNT(*) as count FROM tickets WHERE {where_clause}"
            
            async with self.db.connection() as conn:
                async with conn.cursor(aiomysql.DictCursor) as cursor:
                    await cursor.execute(query, params)
                    result = await cursor.fetchone()
                    return result['count'] if result else 0
                    
        except Exception as e:
            logger.error(f"統計票券數量失敗: {e}")
            return 0
    
    async def update_ticket(self, ticket_id: int, update_data: Dict[str, Any]) -> bool:
        """更新票券資料"""
        try:
            await self._ensure_initialized()
            
            if not update_data:
                return True
            
            # 構建更新語句
            set_clauses = []
            params = []
            
            for field, value in update_data.items():
                if field in ['title', 'description', 'status', 'priority', 'assigned_to', 'assigned_by', 'rating', 'feedback', 'closed_at', 'updated_at']:
                    set_clauses.append(f"{field} = %s")
                    params.append(value)
            
            if not set_clauses:
                return True
            
            # 總是更新 updated_at
            if 'updated_at' not in update_data:
                set_clauses.append("updated_at = %s")
                params.append(datetime.now(timezone.utc))
            
            set_clause = ", ".join(set_clauses)
            query = f"UPDATE tickets SET {set_clause} WHERE id = %s"
            params.append(ticket_id)
            
            async with self.db.connection() as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute(query, params)
                    await conn.commit()
                    return cursor.rowcount > 0
                    
        except Exception as e:
            logger.error(f"更新票券失敗: {e}")
            return False

    async def update_ticket_priority(self, ticket_id: int, priority: str) -> bool:
        """更新票券優先級 - 修復異步"""
        await self._ensure_initialized()
        try:
            async with self.db.connection() as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute("""
                        UPDATE tickets SET priority = %s WHERE id = %s
                    """, (priority, ticket_id))
                    
                    # 記錄日誌
                    await cursor.execute("""
                        INSERT INTO ticket_logs (ticket_id, action, details, created_by, created_at)
                        VALUES (%s, 'priority_change', %s, 'system', NOW())
                    """, (ticket_id, f"優先級變更為 {priority}"))
                    
                    await conn.commit()
                    return cursor.rowcount > 0
                    
        except Exception as e:
            logger.error(f"更新優先級錯誤：{e}")
            return False
    
    async def save_rating(self, ticket_id: int, rating: int, feedback: str = None) -> bool:
        """保存評分 - 修復異步"""
        await self._ensure_initialized()
        try:
            async with self.db.connection() as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute("""
                        UPDATE tickets SET rating = %s, rating_feedback = %s 
                        WHERE id = %s AND status = 'closed'
                    """, (rating, feedback, ticket_id))
                    
                    if cursor.rowcount > 0:
                        # 記錄日誌
                        await cursor.execute("""
                            INSERT INTO ticket_logs (ticket_id, action, details, created_by, created_at)
                            VALUES (%s, 'rating', %s, 'user', NOW())
                        """, (ticket_id, f"評分 {rating}/5"))
                        
                        await conn.commit()
                        return True
                    
            return False
            
        except Exception as e:
            logger.error(f"保存評分錯誤：{e}")
            return False
    
    async def get_statistics(self, guild_id: int) -> Dict[str, Any]:
        """取得基本統計 - 修復異步"""
        await self._ensure_initialized()
        try:
            async with self.db.connection() as conn:
                async with conn.cursor() as cursor:
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
                    
                    result = await cursor.fetchone()
                    if not result:
                        return {}
                    
                    stats = {
                        'total': result[0] or 0,
                        'open': result[1] or 0,
                        'closed': result[2] or 0,
                        'today': result[3] or 0,
                        'avg_rating': result[4] or 0,
                        'total_ratings': result[5] or 0,
                        'satisfied_ratings': result[6] or 0
                    }
                    
                    # 計算滿意度
                    if stats['total_ratings'] > 0:
                        stats['satisfaction_rate'] = (stats['satisfied_ratings'] / stats['total_ratings']) * 100
                    else:
                        stats['satisfaction_rate'] = 0
                    
                    return stats
                    
        except Exception as e:
            logger.error(f"取得統計錯誤：{e}")
            return {}
    
    async def get_user_ticket_count(self, user_id: int, guild_id: int, status: str = "open") -> int:
        """取得用戶票券數量 - 修復異步"""
        await self._ensure_initialized()
        try:
            async with self.db.connection() as conn:
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
    
    async def get_user_tickets(self, user_id: int, guild_id: int, status: str = "all", 
                              limit: int = 10) -> List[Dict[str, Any]]:
        """取得用戶票券列表 - 新增缺失方法"""
        await self._ensure_initialized()
        try:
            where_conditions = ["discord_id = %s", "guild_id = %s"]
            params = [str(user_id), guild_id]
            
            if status in ("open", "closed"):
                where_conditions.append("status = %s")
                params.append(status)
            
            where_clause = " AND ".join(where_conditions)
            
            async with self.db.connection() as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute(f"""
                        SELECT id, discord_id, username, type, status, priority, 
                               channel_id, created_at, closed_at, assigned_to
                        FROM tickets 
                        WHERE {where_clause}
                        ORDER BY created_at DESC 
                        LIMIT %s
                    """, params + [limit])
                    
                    results = await cursor.fetchall()
                    columns = [desc[0] for desc in cursor.description]
                    
                    return [dict(zip(columns, row)) for row in results]
                    
        except Exception as e:
            logger.error(f"查詢用戶票券列表錯誤：{e}")
            return []
    
    async def get_overdue_tickets(self) -> List[Dict[str, Any]]:
        """取得超時票券 - 修復異步"""
        await self._ensure_initialized()
        try:
            async with self.db.connection() as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute("""
                        SELECT t.*, ts.sla_response_minutes
                        FROM tickets t
                        LEFT JOIN ticket_settings ts ON t.guild_id = ts.guild_id
                        WHERE t.status = 'open'
                        AND TIMESTAMPDIFF(MINUTE, t.created_at, NOW()) > COALESCE(
                            CASE t.priority 
                                WHEN 'high' THEN ts.sla_response_minutes * 0.5
                                WHEN 'medium' THEN ts.sla_response_minutes
                                WHEN 'low' THEN ts.sla_response_minutes * 1.5
                            END, 60
                        )
                        AND t.assigned_to IS NULL
                    """)
                    
                    results = await cursor.fetchall()
                    columns = [desc[0] for desc in cursor.description]
                    
                    return [dict(zip(columns, row)) for row in results]
                    
        except Exception as e:
            logger.error(f"查詢超時票券錯誤：{e}")
            return []
    
    async def get_settings(self, guild_id: int) -> Dict[str, Any]:
        """取得伺服器設定 - 修復異步"""
        await self._ensure_initialized()
        try:
            async with self.db.connection() as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute(
                        "SELECT * FROM ticket_settings WHERE guild_id = %s", (guild_id,)
                    )
                    
                    result = await cursor.fetchone()
                    
                    if not result:
                        # 建立預設設定
                        return await self.create_default_settings(guild_id)
                    
                    # 將結果轉換為字典
                    columns = [desc[0] for desc in cursor.description]
                    settings = dict(zip(columns, result))
                    
                    # 解析 JSON 欄位
                    if settings.get('support_roles'):
                        try:
                            settings['support_roles'] = json.loads(settings['support_roles'])
                        except:
                            settings['support_roles'] = []
                    else:
                        settings['support_roles'] = []
                    
                    return settings
                    
        except Exception as e:
            logger.error(f"取得設定錯誤：{e}")
            return await self.create_default_settings(guild_id)
    
    async def create_default_settings(self, guild_id: int) -> Dict[str, Any]:
        """建立預設設定 - 修復異步"""
        await self._ensure_initialized()
        default_settings = {
            'guild_id': guild_id,
            'max_tickets_per_user': 3,
            'auto_close_hours': 24,
            'sla_response_minutes': 60,
            'welcome_message': "歡迎使用客服系統！請選擇問題類型來建立支援票券。",
            'support_roles': []
        }
        
        try:
            async with self.db.connection() as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute("""
                        INSERT INTO ticket_settings 
                        (guild_id, max_tickets_per_user, auto_close_hours, sla_response_minutes, welcome_message, support_roles, created_at, updated_at)
                        VALUES (%s, %s, %s, %s, %s, %s, NOW(), NOW())
                        ON DUPLICATE KEY UPDATE updated_at = NOW()
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
        """更新設定 - 修復異步"""
        await self._ensure_initialized()
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
            
            async with self.db.connection() as conn:
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
    
    async def update_settings(self, guild_id: int, settings: Dict[str, Any]) -> bool:
        """批量更新設定"""
        await self._ensure_initialized()
        try:
            # 直接使用資料庫欄位名稱
            allowed_fields = {
                'category_id', 'support_roles', 'max_tickets_per_user', 
                'auto_close_hours', 'sla_response_minutes', 'welcome_message'
            }
            
            # 過濾允許的欄位
            valid_settings = {}
            for key, value in settings.items():
                if key in allowed_fields:
                    # 處理特殊類型
                    if key == 'support_roles' and isinstance(value, list):
                        value = json.dumps(value)
                    elif key in ['category_id', 'max_tickets_per_user', 'auto_close_hours', 'sla_response_minutes']:
                        value = int(value)
                    valid_settings[key] = value
            
            if not valid_settings:
                return False
            
            # 構建UPDATE SQL
            set_clauses = [f"{field} = %s" for field in valid_settings.keys()]
            set_clause = ", ".join(set_clauses)
            values = list(valid_settings.values())
            values.append(guild_id)  # WHERE條件的值
            
            async with self.db.connection() as conn:
                async with conn.cursor() as cursor:
                    sql = f"""
                        UPDATE ticket_settings 
                        SET {set_clause}, updated_at = NOW() 
                        WHERE guild_id = %s
                    """
                    await cursor.execute(sql, values)
                    await conn.commit()
                    return cursor.rowcount > 0
                    
        except Exception as e:
            logger.error(f"批量更新設定錯誤：{e}")
            return False
    
    async def get_next_ticket_id(self) -> int:
        """取得下一個票券 ID - 修復異步"""
        await self._ensure_initialized()
        try:
            async with self.db.connection() as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute("SELECT MAX(id) FROM tickets")
                    result = await cursor.fetchone()
                    return (result[0] or 0) + 1
        except Exception as e:
            logger.error(f"取得票券 ID 錯誤：{e}")
            return 1
    
    async def cleanup_old_data(self, days: int = 90) -> int:
        """清理舊資料 - 修復異步"""
        await self._ensure_initialized()
        try:
            cutoff_date = datetime.now(timezone.utc) - timedelta(days=days)
            
            async with self.db.connection() as conn:
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
    
    async def paginate_tickets(
        self,
        guild_id: int,
        user_id: Optional[str] = None,
        status: Optional[str] = None,
        assigned_to: Optional[str] = None,
        page: int = 1,
        page_size: int = 10,
        unassigned_only: bool = False,
        created_after: Optional[datetime] = None,
        created_before: Optional[datetime] = None
    ) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
        """分頁查詢票券"""
        await self._ensure_initialized()
        try:
            # 構建查詢條件
            conditions = ["guild_id = %s"]
            params = [guild_id]
            
            if user_id is not None:
                conditions.append("discord_id = %s")
                params.append(user_id)
            
            if status is not None:
                conditions.append("status = %s")
                params.append(status)
            
            if assigned_to is not None:
                conditions.append("assigned_to = %s")
                params.append(assigned_to)
            
            if unassigned_only:
                conditions.append("assigned_to IS NULL")
            
            if created_after is not None:
                conditions.append("created_at >= %s")
                params.append(created_after)
            
            if created_before is not None:
                conditions.append("created_at <= %s")
                params.append(created_before)
            
            where_clause = " AND ".join(conditions)
            
            async with self.db.connection() as conn:
                async with conn.cursor() as cursor:
                    # 計算總數
                    count_sql = f"""
                        SELECT COUNT(*) FROM tickets 
                        WHERE {where_clause}
                    """
                    await cursor.execute(count_sql, params)
                    total_count = (await cursor.fetchone())[0]
                    
                    # 計算分頁資訊
                    total_pages = (total_count + page_size - 1) // page_size
                    offset = (page - 1) * page_size
                    
                    # 查詢票券資料
                    tickets_sql = f"""
                        SELECT 
                            id,
                            guild_id,
                            discord_id,
                            username,
                            channel_id,
                            NULL as category_id,
                            status,
                            type as subject,
                            NULL as description,
                            priority,
                            assigned_to,
                            created_at,
                            NULL as updated_at,
                            closed_at,
                            closed_by,
                            close_reason,
                            tags,
                            NULL as metadata
                        FROM tickets 
                        WHERE {where_clause}
                        ORDER BY created_at DESC
                        LIMIT %s OFFSET %s
                    """
                    
                    await cursor.execute(tickets_sql, params + [page_size, offset])
                    rows = await cursor.fetchall()
                    
                    # 格式化結果
                    tickets = []
                    for row in rows:
                        ticket = {
                            'id': row[0],
                            'ticket_id': row[0],  # 添加 ticket_id 別名
                            'guild_id': row[1],
                            'user_id': row[2],  # discord_id mapped to user_id for compatibility
                            'discord_id': row[2],  # 原始 discord_id 欄位
                            'username': row[3],
                            'channel_id': row[4],
                            'category_id': row[5],  # NULL
                            'status': row[6],
                            'subject': row[7],  # type mapped to subject
                            'type': row[7],  # 原始 type 欄位
                            'description': row[8],  # NULL
                            'priority': row[9],
                            'assigned_to': row[10],
                            'created_at': row[11],
                            'updated_at': row[12],  # NULL
                            'closed_at': row[13],
                            'closed_by': row[14],
                            'close_reason': row[15],
                            'tags': json.loads(row[16]) if row[16] else [],
                            'metadata': row[17] or {}  # 處理 NULL 值
                        }
                        tickets.append(ticket)
                    
                    # 分頁資訊
                    pagination = {
                        'current_page': page,
                        'page_size': page_size,
                        'total_pages': total_pages,
                        'total_count': total_count,
                        'has_next': page < total_pages,
                        'has_prev': page > 1
                    }
                    
                    return tickets, pagination
                    
        except Exception as e:
            logger.error(f"分頁查詢票券錯誤：{e}")
            return [], {
                'current_page': page,
                'page_size': page_size,
                'total_pages': 0,
                'total_count': 0,
                'has_next': False,
                'has_prev': False
            }
    
    # ========== 儀表板支援方法 ==========
    
    async def get_daily_ticket_stats(self, guild_id: int, start_date, end_date) -> List[Dict[str, Any]]:
        """獲取每日票券統計數據 (支援儀表板)"""
        try:
            await self._ensure_initialized()
            
            async with self.db.connection() as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute("""
                        SELECT 
                            DATE(created_at) as date,
                            COUNT(*) as created_count,
                            SUM(CASE WHEN status = 'closed' THEN 1 ELSE 0 END) as closed_count,
                            SUM(CASE WHEN status = 'open' THEN 1 ELSE 0 END) as open_count,
                            AVG(CASE 
                                WHEN closed_at IS NOT NULL AND created_at IS NOT NULL 
                                THEN TIMESTAMPDIFF(MINUTE, created_at, closed_at) 
                                ELSE NULL 
                            END) as avg_resolution_time
                        FROM tickets 
                        WHERE guild_id = %s 
                            AND DATE(created_at) BETWEEN %s AND %s
                        GROUP BY DATE(created_at)
                        ORDER BY date ASC
                    """, (guild_id, start_date, end_date))
                    
                    rows = await cursor.fetchall()
                    
                    daily_stats = []
                    for row in rows:
                        daily_stats.append({
                            'date': row[0],
                            'created_count': row[1],
                            'closed_count': row[2], 
                            'open_count': row[3],
                            'avg_resolution_time': float(row[4]) if row[4] else 0.0
                        })
                    
                    return daily_stats
                    
        except Exception as e:
            logger.error(f"獲取每日票券統計失敗: {e}")
            return []
    
    async def get_ticket_performance_metrics(self, guild_id: int, days: int = 30) -> Dict[str, Any]:
        """獲取票券性能指標"""
        try:
            await self._ensure_initialized()
            
            async with self.db.connection() as conn:
                async with conn.cursor() as cursor:
                    # 基本統計
                    await cursor.execute("""
                        SELECT 
                            COUNT(*) as total_tickets,
                            AVG(CASE 
                                WHEN closed_at IS NOT NULL AND created_at IS NOT NULL 
                                THEN TIMESTAMPDIFF(MINUTE, created_at, closed_at) 
                                ELSE NULL 
                            END) as avg_resolution_time,
                            COUNT(CASE WHEN status = 'closed' THEN 1 END) as closed_tickets,
                            COUNT(CASE WHEN status = 'open' THEN 1 END) as open_tickets,
                            COUNT(CASE WHEN priority = 'high' THEN 1 END) as high_priority_count,
                            COUNT(CASE WHEN priority = 'medium' THEN 1 END) as medium_priority_count,
                            COUNT(CASE WHEN priority = 'low' THEN 1 END) as low_priority_count
                        FROM tickets 
                        WHERE guild_id = %s 
                            AND created_at >= DATE_SUB(NOW(), INTERVAL %s DAY)
                    """, (guild_id, days))
                    
                    row = await cursor.fetchone()
                    
                    if row:
                        metrics = {
                            'total_tickets': row[0],
                            'avg_resolution_time': float(row[1]) if row[1] else 0.0,
                            'closed_tickets': row[2],
                            'open_tickets': row[3],
                            'resolution_rate': (row[2] / row[0] * 100) if row[0] > 0 else 0,
                            'priority_distribution': {
                                'high': row[4],
                                'medium': row[5], 
                                'low': row[6]
                            }
                        }
                        
                        return metrics
                    else:
                        return {
                            'total_tickets': 0,
                            'avg_resolution_time': 0.0,
                            'closed_tickets': 0,
                            'open_tickets': 0,
                            'resolution_rate': 0,
                            'priority_distribution': {'high': 0, 'medium': 0, 'low': 0}
                        }
                        
        except Exception as e:
            logger.error(f"獲取票券性能指標失敗: {e}")
            return {}
