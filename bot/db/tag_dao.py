# bot/db/tag_dao.py - 標籤系統資料存取層
"""
標籤系統資料存取層
處理標籤CRUD、標籤映射、使用統計、自動規則等功能
"""

from bot.db.pool import db_pool
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any, Tuple
import json
from shared.logger import logger


class TagDAO:
    """標籤系統資料存取層"""
    
    def __init__(self):
        self.db = db_pool
        self._initialized = False
    
    async def _ensure_initialized(self):
        """確保資料庫已初始化"""
        if not self._initialized:
            try:
                # 檢查標籤相關表格是否存在
                async with self.db.connection() as conn:
                    async with conn.cursor() as cursor:
                        await cursor.execute("""
                            SELECT COUNT(*) FROM information_schema.tables 
                            WHERE table_schema = DATABASE() AND table_name = 'ticket_tags'
                        """)
                        exists = (await cursor.fetchone())[0] > 0
                
                if not exists:
                    logger.warning("📋 檢測到標籤系統表格不存在，開始自動初始化...")
                    from bot.db.database_manager import get_database_manager
                    db_manager = get_database_manager()
                    await db_manager._create_tag_tables()
                
                self._initialized = True
                logger.info("✅ 標籤系統 DAO 初始化完成")
                
            except Exception as e:
                logger.error(f"❌ 標籤系統 DAO 初始化失敗：{e}")
                raise

    # ========== 標籤管理 ==========
    
    async def create_tag(self, guild_id: int, name: str, display_name: str,
                        color: str = "#808080", emoji: str = None, description: str = None,
                        category: str = "custom", created_by: int = None) -> Optional[int]:
        """創建新標籤"""
        await self._ensure_initialized()
        try:
            async with self.db.connection() as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute("""
                        INSERT INTO ticket_tags 
                        (guild_id, name, display_name, color, emoji, description, category, created_by)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    """, (guild_id, name, display_name, color, emoji, description, category, created_by))
                    
                    tag_id = cursor.lastrowid
                    
                    # 初始化使用統計
                    await cursor.execute("""
                        INSERT INTO tag_usage_stats (guild_id, tag_id, usage_count)
                        VALUES (%s, %s, 0)
                    """, (guild_id, tag_id))
                    
                    await conn.commit()
                    logger.info(f"創建標籤成功: {name} (ID: {tag_id})")
                    return tag_id
                    
        except Exception as e:
            logger.error(f"創建標籤錯誤：{e}")
            return None

    async def get_tag_by_id(self, tag_id: int) -> Optional[Dict[str, Any]]:
        """根據ID取得標籤"""
        await self._ensure_initialized()
        try:
            async with self.db.connection() as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute("""
                        SELECT * FROM ticket_tags WHERE id = %s AND is_active = 1
                    """, (tag_id,))
                    
                    result = await cursor.fetchone()
                    if result:
                        columns = [desc[0] for desc in cursor.description]
                        return dict(zip(columns, result))
                    return None
                    
        except Exception as e:
            logger.error(f"取得標籤錯誤：{e}")
            return None

    async def get_tags_by_guild(self, guild_id: int, category: str = None,
                               is_active: bool = True) -> List[Dict[str, Any]]:
        """取得伺服器的所有標籤"""
        await self._ensure_initialized()
        try:
            async with self.db.connection() as conn:
                async with conn.cursor() as cursor:
                    where_clauses = ["guild_id = %s"]
                    params = [guild_id]
                    
                    if category:
                        where_clauses.append("category = %s")
                        params.append(category)
                    
                    if is_active is not None:
                        where_clauses.append("is_active = %s")
                        params.append(is_active)
                    
                    sql = f"""
                        SELECT t.*, 
                               COALESCE(s.usage_count, 0) as usage_count,
                               s.last_used_at
                        FROM ticket_tags t
                        LEFT JOIN tag_usage_stats s ON t.id = s.tag_id
                        WHERE {' AND '.join(where_clauses)}
                        ORDER BY t.category ASC, s.usage_count DESC, t.display_name ASC
                    """
                    
                    await cursor.execute(sql, params)
                    results = await cursor.fetchall()
                    columns = [desc[0] for desc in cursor.description]
                    
                    return [dict(zip(columns, row)) for row in results]
                    
        except Exception as e:
            logger.error(f"取得標籤列表錯誤：{e}")
            return []

    async def update_tag(self, tag_id: int, **kwargs) -> bool:
        """更新標籤"""
        await self._ensure_initialized()
        try:
            if not kwargs:
                return False
            
            # 構建更新語句
            update_fields = []
            params = []
            
            for field, value in kwargs.items():
                if field in ['display_name', 'color', 'emoji', 'description', 'category', 'is_active']:
                    update_fields.append(f"{field} = %s")
                    params.append(value)
            
            if not update_fields:
                return False
            
            params.append(tag_id)
            
            async with self.db.connection() as conn:
                async with conn.cursor() as cursor:
                    sql = f"""
                        UPDATE ticket_tags 
                        SET {', '.join(update_fields)}, updated_at = NOW()
                        WHERE id = %s
                    """
                    
                    await cursor.execute(sql, params)
                    await conn.commit()
                    return cursor.rowcount > 0
                    
        except Exception as e:
            logger.error(f"更新標籤錯誤：{e}")
            return False

    async def delete_tag(self, tag_id: int) -> bool:
        """刪除標籤（軟刪除）"""
        await self._ensure_initialized()
        try:
            async with self.db.connection() as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute("""
                        UPDATE ticket_tags 
                        SET is_active = 0, updated_at = NOW()
                        WHERE id = %s
                    """, (tag_id,))
                    
                    await conn.commit()
                    return cursor.rowcount > 0
                    
        except Exception as e:
            logger.error(f"刪除標籤錯誤：{e}")
            return False

    # ========== 標籤映射管理 ==========
    
    async def add_tag_to_ticket(self, ticket_id: int, tag_id: int, added_by: int) -> bool:
        """為票券添加標籤"""
        await self._ensure_initialized()
        try:
            async with self.db.connection() as conn:
                async with conn.cursor() as cursor:
                    # 檢查是否已存在此映射
                    await cursor.execute("""
                        SELECT id FROM ticket_tag_mappings 
                        WHERE ticket_id = %s AND tag_id = %s
                    """, (ticket_id, tag_id))
                    
                    if await cursor.fetchone():
                        return True  # 已存在，視為成功
                    
                    # 添加新映射
                    await cursor.execute("""
                        INSERT INTO ticket_tag_mappings (ticket_id, tag_id, added_by)
                        VALUES (%s, %s, %s)
                    """, (ticket_id, tag_id, added_by))
                    
                    # 更新使用統計
                    await cursor.execute("""
                        UPDATE tag_usage_stats 
                        SET usage_count = usage_count + 1, 
                            last_used_at = NOW(),
                            updated_at = NOW()
                        WHERE tag_id = %s
                    """, (tag_id,))
                    
                    await conn.commit()
                    return True
                    
        except Exception as e:
            logger.error(f"添加標籤到票券錯誤：{e}")
            return False

    async def remove_tag_from_ticket(self, ticket_id: int, tag_id: int) -> bool:
        """從票券移除標籤"""
        await self._ensure_initialized()
        try:
            async with self.db.connection() as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute("""
                        DELETE FROM ticket_tag_mappings 
                        WHERE ticket_id = %s AND tag_id = %s
                    """, (ticket_id, tag_id))
                    
                    await conn.commit()
                    return cursor.rowcount > 0
                    
        except Exception as e:
            logger.error(f"從票券移除標籤錯誤：{e}")
            return False

    async def get_ticket_tags(self, ticket_id: int) -> List[Dict[str, Any]]:
        """取得票券的所有標籤"""
        await self._ensure_initialized()
        try:
            async with self.db.connection() as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute("""
                        SELECT t.*, m.added_by, m.added_at
                        FROM ticket_tags t
                        JOIN ticket_tag_mappings m ON t.id = m.tag_id
                        WHERE m.ticket_id = %s AND t.is_active = 1
                        ORDER BY t.category ASC, t.display_name ASC
                    """, (ticket_id,))
                    
                    results = await cursor.fetchall()
                    columns = [desc[0] for desc in cursor.description]
                    
                    return [dict(zip(columns, row)) for row in results]
                    
        except Exception as e:
            logger.error(f"取得票券標籤錯誤：{e}")
            return []

    async def get_tickets_by_tag(self, tag_id: int, limit: int = 50) -> List[Dict[str, Any]]:
        """取得使用特定標籤的票券列表"""
        await self._ensure_initialized()
        try:
            async with self.db.connection() as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute("""
                        SELECT t.*, m.added_by, m.added_at
                        FROM tickets t
                        JOIN ticket_tag_mappings m ON t.id = m.ticket_id
                        WHERE m.tag_id = %s
                        ORDER BY m.added_at DESC
                        LIMIT %s
                    """, (tag_id, limit))
                    
                    results = await cursor.fetchall()
                    columns = [desc[0] for desc in cursor.description]
                    
                    return [dict(zip(columns, row)) for row in results]
                    
        except Exception as e:
            logger.error(f"根據標籤取得票券錯誤：{e}")
            return []

    # ========== 使用統計 ==========
    
    async def get_tag_usage_stats(self, guild_id: int, days: int = 30) -> List[Dict[str, Any]]:
        """取得標籤使用統計"""
        await self._ensure_initialized()
        try:
            async with self.db.connection() as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute("""
                        SELECT 
                            t.id,
                            t.name,
                            t.display_name,
                            t.color,
                            t.emoji,
                            t.category,
                            s.usage_count,
                            s.last_used_at,
                            COUNT(CASE WHEN m.added_at >= DATE_SUB(NOW(), INTERVAL %s DAY) 
                                  THEN 1 END) as recent_usage
                        FROM ticket_tags t
                        LEFT JOIN tag_usage_stats s ON t.id = s.tag_id
                        LEFT JOIN ticket_tag_mappings m ON t.id = m.tag_id
                        WHERE t.guild_id = %s AND t.is_active = 1
                        GROUP BY t.id, t.name, t.display_name, t.color, t.emoji, t.category,
                                 s.usage_count, s.last_used_at
                        ORDER BY s.usage_count DESC, recent_usage DESC
                    """, (days, guild_id))
                    
                    results = await cursor.fetchall()
                    columns = [desc[0] for desc in cursor.description]
                    
                    return [dict(zip(columns, row)) for row in results]
                    
        except Exception as e:
            logger.error(f"取得標籤使用統計錯誤：{e}")
            return []

    # ========== 自動標籤規則 ==========
    
    async def create_auto_rule(self, guild_id: int, rule_name: str, tag_id: int,
                              trigger_type: str, trigger_value: str, created_by: int,
                              priority: int = 1) -> Optional[int]:
        """創建自動標籤規則"""
        await self._ensure_initialized()
        try:
            async with self.db.connection() as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute("""
                        INSERT INTO tag_auto_rules 
                        (guild_id, rule_name, tag_id, trigger_type, trigger_value, priority, created_by)
                        VALUES (%s, %s, %s, %s, %s, %s, %s)
                    """, (guild_id, rule_name, tag_id, trigger_type, trigger_value, priority, created_by))
                    
                    rule_id = cursor.lastrowid
                    await conn.commit()
                    
                    logger.info(f"創建自動標籤規則成功: {rule_name} (ID: {rule_id})")
                    return rule_id
                    
        except Exception as e:
            logger.error(f"創建自動標籤規則錯誤：{e}")
            return None

    async def get_auto_rules(self, guild_id: int, is_active: bool = True) -> List[Dict[str, Any]]:
        """取得自動標籤規則"""
        await self._ensure_initialized()
        try:
            async with self.db.connection() as conn:
                async with conn.cursor() as cursor:
                    where_clause = "r.guild_id = %s"
                    params = [guild_id]
                    
                    if is_active is not None:
                        where_clause += " AND r.is_active = %s"
                        params.append(is_active)
                    
                    await cursor.execute(f"""
                        SELECT r.*, t.name as tag_name, t.display_name as tag_display_name
                        FROM tag_auto_rules r
                        JOIN ticket_tags t ON r.tag_id = t.id
                        WHERE {where_clause}
                        ORDER BY r.priority DESC, r.created_at ASC
                    """, params)
                    
                    results = await cursor.fetchall()
                    columns = [desc[0] for desc in cursor.description]
                    
                    return [dict(zip(columns, row)) for row in results]
                    
        except Exception as e:
            logger.error(f"取得自動標籤規則錯誤：{e}")
            return []

    async def apply_auto_rules(self, guild_id: int, ticket_id: int, ticket_type: str,
                              content: str, user_roles: List[int] = None) -> List[int]:
        """應用自動標籤規則，返回添加的標籤ID列表"""
        await self._ensure_initialized()
        try:
            rules = await self.get_auto_rules(guild_id, True)
            applied_tags = []
            
            for rule in rules:
                should_apply = False
                
                if rule['trigger_type'] == 'keyword':
                    keywords = rule['trigger_value'].lower().split(',')
                    content_lower = content.lower()
                    should_apply = any(keyword.strip() in content_lower for keyword in keywords)
                
                elif rule['trigger_type'] == 'ticket_type':
                    target_types = rule['trigger_value'].split(',')
                    should_apply = ticket_type in [t.strip() for t in target_types]
                
                elif rule['trigger_type'] == 'user_role' and user_roles:
                    target_roles = [int(r.strip()) for r in rule['trigger_value'].split(',') if r.strip().isdigit()]
                    should_apply = bool(set(user_roles) & set(target_roles))
                
                if should_apply:
                    success = await self.add_tag_to_ticket(ticket_id, rule['tag_id'], 0)  # 系統自動添加
                    if success:
                        applied_tags.append(rule['tag_id'])
                        logger.info(f"自動應用標籤規則: {rule['rule_name']} -> 票券 #{ticket_id}")
            
            return applied_tags
            
        except Exception as e:
            logger.error(f"應用自動標籤規則錯誤：{e}")
            return []

    # ========== 搜索和過濾 ==========
    
    async def search_tags(self, guild_id: int, query: str, limit: int = 20) -> List[Dict[str, Any]]:
        """搜索標籤"""
        await self._ensure_initialized()
        try:
            async with self.db.connection() as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute("""
                        SELECT t.*, 
                               COALESCE(s.usage_count, 0) as usage_count,
                               s.last_used_at
                        FROM ticket_tags t
                        LEFT JOIN tag_usage_stats s ON t.id = s.tag_id
                        WHERE t.guild_id = %s 
                        AND t.is_active = 1
                        AND (t.name LIKE %s OR t.display_name LIKE %s OR t.description LIKE %s)
                        ORDER BY s.usage_count DESC, t.display_name ASC
                        LIMIT %s
                    """, (guild_id, f"%{query}%", f"%{query}%", f"%{query}%", limit))
                    
                    results = await cursor.fetchall()
                    columns = [desc[0] for desc in cursor.description]
                    
                    return [dict(zip(columns, row)) for row in results]
                    
        except Exception as e:
            logger.error(f"搜索標籤錯誤：{e}")
            return []

    async def get_popular_tags(self, guild_id: int, limit: int = 10) -> List[Dict[str, Any]]:
        """取得熱門標籤"""
        await self._ensure_initialized()
        try:
            async with self.db.connection() as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute("""
                        SELECT t.*, s.usage_count, s.last_used_at
                        FROM ticket_tags t
                        JOIN tag_usage_stats s ON t.id = s.tag_id
                        WHERE t.guild_id = %s AND t.is_active = 1
                        ORDER BY s.usage_count DESC, s.last_used_at DESC
                        LIMIT %s
                    """, (guild_id, limit))
                    
                    results = await cursor.fetchall()
                    columns = [desc[0] for desc in cursor.description]
                    
                    return [dict(zip(columns, row)) for row in results]
                    
        except Exception as e:
            logger.error(f"取得熱門標籤錯誤：{e}")
            return []