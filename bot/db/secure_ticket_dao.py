# bot/db/secure_ticket_dao.py - v1.0.0
# 🔐 安全的票券資料存取層
# Secure Ticket Data Access Object

from bot.db.pool import db_pool
from bot.utils.multi_tenant_security import (
    multi_tenant_security, secure_query_builder, 
    enforce_isolation, TenantIsolationViolation
)
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Any, Tuple
import json
import logging
import aiomysql

logger = logging.getLogger(__name__)

class SecureTicketDAO:
    """安全的票券資料存取層 - 具備完整的多租戶隔離"""
    
    def __init__(self):
        self.db = db_pool
        self.security = multi_tenant_security
        self.query_builder = secure_query_builder
        self._initialized = False

    async def _ensure_initialized(self):
        """確保資料庫已初始化"""
        if not self._initialized:
            try:
                async with self.db.connection() as conn:
                    async with conn.cursor() as cursor:
                        await cursor.execute("""
                            SELECT COUNT(*) FROM information_schema.tables 
                            WHERE table_schema = DATABASE() AND table_name = 'tickets'
                        """)
                        exists = (await cursor.fetchone())[0] > 0
                
                if not exists:
                    logger.warning("📋 票券表格不存在，開始初始化...")
                    from bot.db.database_manager import DatabaseManager
                    db_manager = DatabaseManager()
                    await db_manager._create_ticket_tables()
                
                self._initialized = True
                logger.info("✅ 安全票券 DAO 初始化完成")
                
            except Exception as e:
                logger.error(f"❌ 安全票券 DAO 初始化失敗: {e}")
                raise

    @enforce_isolation("tickets")
    async def get_ticket_by_id(self, ticket_id: int, guild_id: int, 
                              user_id: Optional[int] = None) -> Optional[Dict[str, Any]]:
        """安全取得票券 - 強制 guild_id 隔離"""
        await self._ensure_initialized()
        
        try:
            # 驗證用戶對該伺服器的存取權限
            if user_id and not await self.security.validate_guild_access(user_id, guild_id):
                raise TenantIsolationViolation(f"用戶 {user_id} 無權存取伺服器 {guild_id} 的票券")
            
            # 建構安全查詢
            query, params = self.query_builder.build_select(
                table="tickets",
                guild_id=guild_id,
                additional_where={"id": ticket_id}
            )
            
            async with self.db.connection() as conn:
                async with conn.cursor(aiomysql.DictCursor) as cursor:
                    await cursor.execute(query, params)
                    result = await cursor.fetchone()
                    
                    if result:
                        # 記錄安全事件
                        await self._log_data_access(
                            user_id, guild_id, "read", "tickets", 
                            ticket_id, True
                        )
                        return dict(result)
                    
                    return None
                    
        except Exception as e:
            logger.error(f"❌ 安全取得票券失敗: {e}")
            await self._log_data_access(
                user_id, guild_id, "read", "tickets", 
                ticket_id, False, str(e)
            )
            raise

    @enforce_isolation("tickets")  
    async def get_tickets_by_guild(self, guild_id: int, user_id: int,
                                  status: Optional[str] = None,
                                  assigned_to: Optional[int] = None,
                                  page: int = 1, page_size: int = 20) -> Dict[str, Any]:
        """安全取得伺服器票券列表 - 完整隔離"""
        await self._ensure_initialized()
        
        try:
            # 驗證權限
            if not await self.security.validate_guild_access(user_id, guild_id):
                raise TenantIsolationViolation(f"用戶 {user_id} 無權存取伺服器 {guild_id} 的票券")
            
            # 建構查詢條件
            additional_where = {}
            if status:
                additional_where["status"] = status
            if assigned_to:
                additional_where["assigned_to"] = assigned_to
            
            # 計算總數
            count_query, count_params = self.query_builder.build_select(
                table="tickets",
                columns="COUNT(*) as total",
                guild_id=guild_id,
                additional_where=additional_where
            )
            
            # 分頁查詢
            offset = (page - 1) * page_size
            data_query, data_params = self.query_builder.build_select(
                table="tickets", 
                guild_id=guild_id,
                additional_where=additional_where
            )
            data_query += f" ORDER BY created_at DESC LIMIT {page_size} OFFSET {offset}"
            
            async with self.db.connection() as conn:
                async with conn.cursor(aiomysql.DictCursor) as cursor:
                    # 查詢總數
                    await cursor.execute(count_query, count_params)
                    total_result = await cursor.fetchone()
                    total = total_result["total"] if total_result else 0
                    
                    # 查詢資料
                    await cursor.execute(data_query, data_params)
                    tickets = await cursor.fetchall()
                    
                    result = {
                        "tickets": [dict(ticket) for ticket in tickets],
                        "total": total,
                        "page": page,
                        "page_size": page_size,
                        "total_pages": (total + page_size - 1) // page_size
                    }
                    
                    # 記錄存取日誌
                    await self._log_data_access(
                        user_id, guild_id, "read", "tickets", 
                        f"list_page_{page}", True
                    )
                    
                    return result
                    
        except Exception as e:
            logger.error(f"❌ 安全取得票券列表失敗: {e}")
            await self._log_data_access(
                user_id, guild_id, "read", "tickets", 
                f"list_page_{page}", False, str(e)
            )
            raise

    @enforce_isolation("tickets")
    async def create_ticket(self, guild_id: int, user_id: int, 
                           ticket_data: Dict[str, Any]) -> Optional[int]:
        """安全建立票券 - 強制 guild_id 隔離"""
        await self._ensure_initialized()
        
        try:
            # 驗證權限
            if not await self.security.validate_guild_access(user_id, guild_id):
                raise TenantIsolationViolation(f"用戶 {user_id} 無權在伺服器 {guild_id} 建立票券")
            
            # 準備安全資料
            safe_data = {
                "discord_id": str(user_id),
                "username": ticket_data.get("username", "Unknown"),
                "discord_username": ticket_data.get("discord_username", "Unknown"),
                "type": ticket_data.get("type", "general"),
                "priority": ticket_data.get("priority", "medium"),
                "status": "open",
                "channel_id": ticket_data.get("channel_id"),
                "created_at": datetime.now(timezone.utc)
            }
            
            # 建構安全插入查詢
            query, params = self.query_builder.build_insert(
                table="tickets",
                data=safe_data,
                guild_id=guild_id
            )
            
            async with self.db.connection() as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute(query, params)
                    ticket_id = cursor.lastrowid
                    await conn.commit()
                    
                    # 記錄建立日誌
                    await self.add_ticket_log(
                        ticket_id, guild_id, "created", 
                        f"票券由用戶 {user_id} 建立", user_id
                    )
                    
                    # 記錄存取日誌
                    await self._log_data_access(
                        user_id, guild_id, "create", "tickets", 
                        ticket_id, True
                    )
                    
                    logger.info(f"✅ 票券建立成功: ID={ticket_id}, Guild={guild_id}")
                    return ticket_id
                    
        except Exception as e:
            logger.error(f"❌ 安全建立票券失敗: {e}")
            await self._log_data_access(
                user_id, guild_id, "create", "tickets", 
                None, False, str(e)
            )
            raise

    @enforce_isolation("tickets")
    async def update_ticket(self, ticket_id: int, guild_id: int, 
                           user_id: int, updates: Dict[str, Any]) -> bool:
        """安全更新票券 - 強制 guild_id 隔離"""
        await self._ensure_initialized()
        
        try:
            # 驗證權限
            if not await self.security.validate_guild_access(user_id, guild_id):
                raise TenantIsolationViolation(f"用戶 {user_id} 無權更新伺服器 {guild_id} 的票券")
            
            # 過濾安全更新欄位
            allowed_fields = [
                "status", "priority", "assigned_to", "rating", 
                "rating_feedback", "close_reason", "tags"
            ]
            safe_updates = {k: v for k, v in updates.items() if k in allowed_fields}
            
            if not safe_updates:
                logger.warning("沒有有效的更新欄位")
                return False
            
            # 添加更新時間
            safe_updates["last_activity"] = datetime.now(timezone.utc)
            
            # 建構安全更新查詢
            query, params = self.query_builder.build_update(
                table="tickets",
                data=safe_updates,
                where_conditions={"id": ticket_id},
                guild_id=guild_id
            )
            
            async with self.db.connection() as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute(query, params)
                    rows_affected = cursor.rowcount
                    await conn.commit()
                    
                    if rows_affected > 0:
                        # 記錄更新日誌
                        await self.add_ticket_log(
                            ticket_id, guild_id, "updated",
                            f"票券更新: {', '.join(safe_updates.keys())}", user_id
                        )
                        
                        # 記錄存取日誌
                        await self._log_data_access(
                            user_id, guild_id, "update", "tickets",
                            ticket_id, True
                        )
                        
                        logger.info(f"✅ 票券更新成功: ID={ticket_id}")
                        return True
                    else:
                        logger.warning(f"票券更新失敗: 沒有找到票券 ID={ticket_id}")
                        return False
                        
        except Exception as e:
            logger.error(f"❌ 安全更新票券失敗: {e}")
            await self._log_data_access(
                user_id, guild_id, "update", "tickets",
                ticket_id, False, str(e)
            )
            raise

    @enforce_isolation("ticket_logs")
    async def add_ticket_log(self, ticket_id: int, guild_id: int, 
                            action: str, details: str, 
                            user_id: Optional[int] = None) -> bool:
        """安全新增票券日誌"""
        try:
            log_data = {
                "ticket_id": ticket_id,
                "action": action,
                "details": details,
                "created_by": str(user_id) if user_id else None,
                "created_at": datetime.now(timezone.utc)
            }
            
            # 票券日誌不直接存儲 guild_id，但透過 ticket_id 關聯
            # 這裡我們需要驗證 ticket_id 確實屬於指定的 guild_id
            ticket = await self.get_ticket_by_id(ticket_id, guild_id, user_id)
            if not ticket:
                raise TenantIsolationViolation(f"票券 {ticket_id} 不屬於伺服器 {guild_id}")
            
            async with self.db.connection() as conn:
                async with conn.cursor() as cursor:
                    # 直接插入，因為已驗證票券所屬權
                    columns = ", ".join(log_data.keys())
                    placeholders = ", ".join(["%s"] * len(log_data))
                    query = f"INSERT INTO ticket_logs ({columns}) VALUES ({placeholders})"
                    
                    await cursor.execute(query, list(log_data.values()))
                    await conn.commit()
                    
                    return True
                    
        except Exception as e:
            logger.error(f"❌ 新增票券日誌失敗: {e}")
            return False

    async def get_guild_settings(self, guild_id: int, user_id: int) -> Dict[str, Any]:
        """安全取得伺服器設定"""
        try:
            # 驗證權限
            if not await self.security.validate_guild_access(user_id, guild_id):
                raise TenantIsolationViolation(f"用戶 {user_id} 無權存取伺服器 {guild_id} 設定")
            
            query, params = self.query_builder.build_select(
                table="ticket_settings",
                guild_id=guild_id
            )
            
            async with self.db.connection() as conn:
                async with conn.cursor(aiomysql.DictCursor) as cursor:
                    await cursor.execute(query, params)
                    result = await cursor.fetchone()
                    
                    if result:
                        return dict(result)
                    else:
                        # 如果沒有設定，返回預設值
                        return await self.create_default_settings(guild_id, user_id)
                        
        except Exception as e:
            logger.error(f"❌ 取得伺服器設定失敗: {e}")
            raise

    async def create_default_settings(self, guild_id: int, user_id: int) -> Dict[str, Any]:
        """建立預設伺服器設定"""
        try:
            default_settings = {
                "max_tickets_per_user": 3,
                "auto_close_hours": 24,
                "sla_response_minutes": 60,
                "welcome_message": "感謝您建立票券，我們會盡快為您處理。",
                "auto_assign_enabled": False,
                "created_at": datetime.now(timezone.utc),
                "updated_at": datetime.now(timezone.utc)
            }
            
            query, params = self.query_builder.build_insert(
                table="ticket_settings",
                data=default_settings,
                guild_id=guild_id
            )
            
            async with self.db.connection() as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute(query, params)
                    await conn.commit()
                    
                    # 添加 guild_id 到返回資料
                    default_settings["guild_id"] = guild_id
                    
                    logger.info(f"✅ 建立預設設定: Guild={guild_id}")
                    return default_settings
                    
        except Exception as e:
            logger.error(f"❌ 建立預設設定失敗: {e}")
            raise

    async def _log_data_access(self, user_id: Optional[int], guild_id: int, 
                              action: str, resource_type: str, 
                              resource_id: Any, success: bool, 
                              error_message: Optional[str] = None):
        """記錄資料存取日誌"""
        try:
            log_data = {
                "user_id": user_id,
                "guild_id": guild_id,
                "resource_type": resource_type,
                "resource_id": str(resource_id) if resource_id else None,
                "action": action,
                "success": success,
                "error_message": error_message,
                "created_at": datetime.now(timezone.utc)
            }
            
            # 直接插入到 data_access_logs 表格
            async with self.db.connection() as conn:
                async with conn.cursor() as cursor:
                    columns = ", ".join(log_data.keys())
                    placeholders = ", ".join(["%s"] * len(log_data))
                    query = f"INSERT INTO data_access_logs ({columns}) VALUES ({placeholders})"
                    
                    await cursor.execute(query, list(log_data.values()))
                    await conn.commit()
                    
        except Exception as e:
            # 日誌記錄失敗不應該影響主要功能
            logger.warning(f"資料存取日誌記錄失敗: {e}")

# 向後兼容的別名
TicketDAO = SecureTicketDAO