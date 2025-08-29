# bot/db/assignment_dao.py - 票券指派系統資料存取層
"""
票券指派系統資料存取層
處理客服指派、工作量追蹤、專精匹配等功能
"""

from typing import Any, Dict, List, Optional

from bot.db.pool import db_pool
from shared.logger import logger


class AssignmentDAO:
    """票券指派系統資料存取層"""

    def __init__(self):
        self.db = db_pool
        self._initialized = False

    async def _ensure_initialized(self):
        """確保資料庫已初始化"""
        if not self._initialized:
            try:
                # 檢查指派相關表格是否存在
                async with self.db.connection() as conn:
                    async with conn.cursor() as cursor:
                        await cursor.execute(
                            """
                            SELECT COUNT(*) FROM information_schema.tables
                            WHERE table_schema = DATABASE() AND table_name = 'staff_workload'
                        """
                        )
                        exists = (await cursor.fetchone())[0] > 0

                if not exists:
                    logger.warning("📋 檢測到指派系統表格不存在，開始自動初始化...")
                    from bot.db.database_manager import get_database_manager

                    db_manager = get_database_manager()
                    await db_manager._create_assignment_tables()

                self._initialized = True
                logger.info("✅ 指派系統 DAO 初始化完成")

            except Exception as e:
                logger.error(f"❌ 指派系統 DAO 初始化失敗：{e}")
                raise

    # ========== 工作量管理 ==========

    async def get_staff_workload(
        self, guild_id: int, staff_id: int
    ) -> Optional[Dict[str, Any]]:
        """取得客服人員工作量資訊"""
        await self._ensure_initialized()
        try:
            async with self.db.connection() as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute(
                        """
                        SELECT * FROM staff_workload
                        WHERE guild_id = %s AND staff_id = %s
                    """,
                        (guild_id, staff_id),
                    )

                    result = await cursor.fetchone()
                    if result:
                        columns = [desc[0] for desc in cursor.description]
                        return dict(zip(columns, result))
                    return None

        except Exception as e:
            logger.error(f"取得客服工作量錯誤：{e}")
            return None

    async def initialize_staff_workload(self, guild_id: int, staff_id: int) -> bool:
        """初始化客服人員工作量記錄"""
        await self._ensure_initialized()
        try:
            async with self.db.connection() as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute(
                        """
                        INSERT IGNORE INTO staff_workload
                        (guild_id, staff_id, current_tickets, total_assigned, total_completed, avg_completion_time)
                        VALUES (%s, %s, 0, 0, 0, 0)
                    """,
                        (guild_id, staff_id),
                    )

                    await conn.commit()
                    return cursor.rowcount > 0

        except Exception as e:
            logger.error(f"初始化客服工作量錯誤：{e}")
            return False

    async def update_staff_workload(
        self,
        guild_id: int,
        staff_id: int,
        current_tickets: int = None,
        increment_assigned: bool = False,
        increment_completed: bool = False,
        completion_time_minutes: int = None,
    ) -> bool:
        """更新客服人員工作量"""
        await self._ensure_initialized()
        try:
            # 確保工作量記錄存在
            await self.initialize_staff_workload(guild_id, staff_id)

            async with self.db.connection() as conn:
                async with conn.cursor() as cursor:
                    updates = []
                    params = []

                    if current_tickets is not None:
                        updates.append("current_tickets = %s")
                        params.append(current_tickets)

                    if increment_assigned:
                        updates.append("total_assigned = total_assigned + 1")
                        updates.append("last_assigned_at = NOW()")

                    if increment_completed:
                        updates.append("total_completed = total_completed + 1")
                        updates.append(
                            "current_tickets = GREATEST(0, current_tickets - 1)"
                        )

                    if completion_time_minutes is not None:
                        # 更新平均完成時間 (使用移動平均)
                        updates.append(
                            """
                            avg_completion_time = CASE
                                WHEN total_completed = 0 THEN %s
                                ELSE (avg_completion_time + %s) / 2
                            END
                        """
                        )
                        params.extend(
                            [completion_time_minutes, completion_time_minutes]
                        )

                    if updates:
                        updates.append("updated_at = NOW()")
                        params.extend([guild_id, staff_id])

                        sql = f"""
                            UPDATE staff_workload
                            SET {', '.join(updates)}
                            WHERE guild_id = %s AND staff_id = %s
                        """

                        await cursor.execute(sql, params)
                        await conn.commit()
                        return cursor.rowcount > 0

                    return False

        except Exception as e:
            logger.error(f"更新客服工作量錯誤：{e}")
            return False

    async def get_available_staff(
        self, guild_id: int, max_concurrent: int = 5
    ) -> List[Dict[str, Any]]:
        """取得可用的客服人員（根據工作量排序）"""
        await self._ensure_initialized()
        try:
            async with self.db.connection() as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute(
                        """
                        SELECT
                            staff_id,
                            current_tickets,
                            total_assigned,
                            total_completed,
                            avg_completion_time,
                            last_assigned_at,
                            CASE
                                WHEN current_tickets < %s THEN 'available'
                                ELSE 'busy'
                            END as availability_status
                        FROM staff_workload
                        WHERE guild_id = %s
                        AND current_tickets < %s
                        ORDER BY
                            current_tickets ASC,
                            ISNULL(last_assigned_at), last_assigned_at ASC,
                            total_assigned ASC
                    """,
                        (max_concurrent, guild_id, max_concurrent),
                    )

                    results = await cursor.fetchall()
                    columns = [desc[0] for desc in cursor.description]

                    return [dict(zip(columns, row)) for row in results]

        except Exception as e:
            logger.error(f"取得可用客服錯誤：{e}")
            return []

    # ========== 指派歷史管理 ==========

    async def record_assignment(
        self,
        ticket_id: int,
        assigned_from: Optional[int],
        assigned_to: int,
        assigned_by: int,
        reason: str = "manual",
        method: str = "manual",
    ) -> bool:
        """記錄指派歷史"""
        await self._ensure_initialized()
        try:
            async with self.db.connection() as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute(
                        """
                        INSERT INTO assignment_history
                        (ticket_id, assigned_from, assigned_to, assigned_by, assignment_reason, assignment_method)
                        VALUES (%s, %s, %s, %s, %s, %s)
                    """,
                        (
                            ticket_id,
                            assigned_from,
                            assigned_to,
                            assigned_by,
                            reason,
                            method,
                        ),
                    )

                    await conn.commit()
                    return cursor.rowcount > 0

        except Exception as e:
            logger.error(f"記錄指派歷史錯誤：{e}")
            return False

    async def get_assignment_history(self, ticket_id: int) -> List[Dict[str, Any]]:
        """取得票券指派歷史"""
        await self._ensure_initialized()
        try:
            async with self.db.connection() as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute(
                        """
                        SELECT * FROM assignment_history
                        WHERE ticket_id = %s
                        ORDER BY assigned_at ASC
                    """,
                        (ticket_id,),
                    )

                    results = await cursor.fetchall()
                    columns = [desc[0] for desc in cursor.description]

                    return [dict(zip(columns, row)) for row in results]

        except Exception as e:
            logger.error(f"取得指派歷史錯誤：{e}")
            return []

    # ========== 專精系統管理 ==========

    async def add_staff_specialty(
        self,
        guild_id: int,
        staff_id: int,
        specialty_type: str,
        skill_level: str = "intermediate",
    ) -> bool:
        """添加客服專精"""
        await self._ensure_initialized()
        try:
            async with self.db.connection() as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute(
                        """
                        INSERT INTO staff_specialties
                        (guild_id, staff_id, specialty_type, skill_level)
                        VALUES (%s, %s, %s, %s)
                        ON DUPLICATE KEY UPDATE
                            skill_level = VALUES(skill_level),
                            is_active = TRUE,
                            updated_at = NOW()
                    """,
                        (guild_id, staff_id, specialty_type, skill_level),
                    )

                    await conn.commit()
                    return True

        except Exception as e:
            logger.error(f"添加客服專精錯誤：{e}")
            return False

    async def get_staff_specialties(
        self, guild_id: int, staff_id: int
    ) -> List[Dict[str, Any]]:
        """取得客服專精列表"""
        await self._ensure_initialized()
        try:
            async with self.db.connection() as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute(
                        """
                        SELECT * FROM staff_specialties
                        WHERE guild_id = %s AND staff_id = %s AND is_active = TRUE
                        ORDER BY skill_level DESC, specialty_type ASC
                    """,
                        (guild_id, staff_id),
                    )

                    results = await cursor.fetchall()
                    columns = [desc[0] for desc in cursor.description]

                    return [dict(zip(columns, row)) for row in results]

        except Exception as e:
            logger.error(f"取得客服專精錯誤：{e}")
            return []

    async def find_specialty_staff(
        self, guild_id: int, specialty_type: str, min_skill_level: str = "intermediate"
    ) -> List[Dict[str, Any]]:
        """根據專精查找客服人員"""
        await self._ensure_initialized()
        try:
            skill_order = {"beginner": 1, "intermediate": 2, "advanced": 3, "expert": 4}
            min_level_value = skill_order.get(min_skill_level, 2)

            async with self.db.connection() as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute(
                        """
                        SELECT
                            ss.staff_id,
                            ss.specialty_type,
                            ss.skill_level,
                            sw.current_tickets,
                            sw.avg_completion_time,
                            CASE ss.skill_level
                                WHEN 'expert' THEN 4
                                WHEN 'advanced' THEN 3
                                WHEN 'intermediate' THEN 2
                                WHEN 'beginner' THEN 1
                            END as skill_level_value
                        FROM staff_specialties ss
                        LEFT JOIN staff_workload sw ON ss.guild_id = sw.guild_id AND ss.staff_id = sw.staff_id
                        WHERE ss.guild_id = %s
                        AND ss.specialty_type = %s
                        AND ss.is_active = TRUE
                        AND CASE ss.skill_level
                            WHEN 'expert' THEN 4
                            WHEN 'advanced' THEN 3
                            WHEN 'intermediate' THEN 2
                            WHEN 'beginner' THEN 1
                        END >= %s
                        ORDER BY
                            skill_level_value DESC,
                            COALESCE(sw.current_tickets, 0) ASC,
                            COALESCE(sw.avg_completion_time, 999999) ASC
                    """,
                        (guild_id, specialty_type, min_level_value),
                    )

                    results = await cursor.fetchall()
                    columns = [desc[0] for desc in cursor.description]

                    return [dict(zip(columns, row)) for row in results]

        except Exception as e:
            logger.error(f"查找專精客服錯誤：{e}")
            return []

    # ========== 指派規則管理 ==========

    async def get_assignment_rule(
        self,
        guild_id: int,
        ticket_type: Optional[str] = None,
        priority_level: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """取得適用的指派規則"""
        await self._ensure_initialized()
        try:
            async with self.db.connection() as conn:
                async with conn.cursor() as cursor:
                    # 優先匹配精確規則，然後匹配通用規則
                    await cursor.execute(
                        """
                        SELECT * FROM assignment_rules
                        WHERE guild_id = %s
                        AND is_active = TRUE
                        AND (ticket_type = %s OR ticket_type IS NULL)
                        AND (priority_level = %s OR priority_level IS NULL)
                        ORDER BY
                            (ticket_type IS NOT NULL) DESC,
                            (priority_level IS NOT NULL) DESC,
                            created_at ASC
                        LIMIT 1
                    """,
                        (guild_id, ticket_type, priority_level),
                    )

                    result = await cursor.fetchone()
                    if result:
                        columns = [desc[0] for desc in cursor.description]
                        return dict(zip(columns, result))
                    return None

        except Exception as e:
            logger.error(f"取得指派規則錯誤：{e}")
            return None

    async def create_assignment_rule(
        self,
        guild_id: int,
        rule_name: str,
        ticket_type: Optional[str] = None,
        priority_level: Optional[str] = None,
        assignment_method: str = "auto_least_workload",
        max_concurrent_tickets: int = 5,
    ) -> bool:
        """建立指派規則"""
        await self._ensure_initialized()
        try:
            async with self.db.connection() as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute(
                        """
                        INSERT INTO assignment_rules
                        (guild_id, rule_name, ticket_type, priority_level, assignment_method, max_concurrent_tickets)
                        VALUES (%s, %s, %s, %s, %s, %s)
                        ON DUPLICATE KEY UPDATE
                            ticket_type = VALUES(ticket_type),
                            priority_level = VALUES(priority_level),
                            assignment_method = VALUES(assignment_method),
                            max_concurrent_tickets = VALUES(max_concurrent_tickets),
                            is_active = TRUE,
                            updated_at = NOW()
                    """,
                        (
                            guild_id,
                            rule_name,
                            ticket_type,
                            priority_level,
                            assignment_method,
                            max_concurrent_tickets,
                        ),
                    )

                    await conn.commit()
                    return True

        except Exception as e:
            logger.error(f"建立指派規則錯誤：{e}")
            return False

    # ========== 統計查詢 ==========

    async def get_assignment_statistics(
        self, guild_id: int, days: int = 30
    ) -> Dict[str, Any]:
        """取得指派統計資料"""
        await self._ensure_initialized()
        try:
            async with self.db.connection() as conn:
                async with conn.cursor() as cursor:
                    # 指派方法統計
                    await cursor.execute(
                        """
                        SELECT
                            assignment_method,
                            COUNT(*) as count,
                            COUNT(*) * 100.0 / (SELECT COUNT(*) FROM assignment_history
                                                WHERE assigned_at >= DATE_SUB(NOW(), INTERVAL %s DAY)) as percentage
                        FROM assignment_history ah
                        JOIN tickets t ON ah.ticket_id = t.id
                        WHERE t.guild_id = %s
                        AND ah.assigned_at >= DATE_SUB(NOW(), INTERVAL %s DAY)
                        GROUP BY assignment_method
                        ORDER BY count DESC
                    """,
                        (days, guild_id, days),
                    )

                    method_stats = await cursor.fetchall()

                    # 客服工作量統計
                    await cursor.execute(
                        """
                        SELECT
                            sw.staff_id,
                            sw.current_tickets,
                            sw.total_assigned,
                            sw.total_completed,
                            sw.avg_completion_time,
                            COALESCE(recent.recent_assignments, 0) as recent_assignments
                        FROM staff_workload sw
                        LEFT JOIN (
                            SELECT
                                ah.assigned_to,
                                COUNT(*) as recent_assignments
                            FROM assignment_history ah
                            JOIN tickets t ON ah.ticket_id = t.id
                            WHERE t.guild_id = %s
                            AND ah.assigned_at >= DATE_SUB(NOW(), INTERVAL %s DAY)
                            GROUP BY ah.assigned_to
                        ) recent ON sw.staff_id = recent.assigned_to
                        WHERE sw.guild_id = %s
                        ORDER BY sw.total_assigned DESC
                    """,
                        (guild_id, days, guild_id),
                    )

                    staff_stats = await cursor.fetchall()

                    return {
                        "assignment_methods": [
                            {
                                "method": row[0],
                                "count": row[1],
                                "percentage": float(row[2]) if row[2] else 0,
                            }
                            for row in method_stats
                        ],
                        "staff_workload": [
                            {
                                "staff_id": row[0],
                                "current_tickets": row[1],
                                "total_assigned": row[2],
                                "total_completed": row[3],
                                "avg_completion_time": row[4],
                                "recent_assignments": row[5],
                            }
                            for row in staff_stats
                        ],
                    }

        except Exception as e:
            logger.error(f"取得指派統計錯誤：{e}")
            return {"assignment_methods": [], "staff_workload": []}

    async def get_staff_performance(
        self, guild_id: int, days: int = 30
    ) -> List[Dict[str, Any]]:
        """取得工作人員表現數據"""
        await self._ensure_initialized()
        try:
            async with self.db.connection() as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute(
                        """
                        SELECT
                            sw.staff_id,
                            sw.current_tickets,
                            sw.total_assigned,
                            sw.total_completed,
                            sw.avg_completion_time,
                            sw.last_assigned_at,
                            COALESCE(recent.recent_completed, 0) as recent_completed,
                            COALESCE(recent.recent_assigned, 0) as recent_assigned,
                            CASE
                                WHEN sw.total_assigned > 0 THEN (sw.total_completed * 100.0 / sw.total_assigned)
                                ELSE 0
                            END as completion_rate,
                            CASE
                                WHEN sw.current_tickets > 0 THEN 'active'
                                WHEN sw.last_assigned_at >= DATE_SUB(NOW(), INTERVAL 7 DAY) THEN 'recent'
                                ELSE 'inactive'
                            END as status
                        FROM staff_workload sw
                        LEFT JOIN (
                            SELECT
                                ah.assigned_to,
                                COUNT(CASE WHEN t.status = 'closed' THEN 1 END) as recent_completed,
                                COUNT(*) as recent_assigned
                            FROM assignment_history ah
                            JOIN tickets t ON ah.ticket_id = t.id
                            WHERE t.guild_id = %s
                            AND ah.assigned_at >= DATE_SUB(NOW(), INTERVAL %s DAY)
                            GROUP BY ah.assigned_to
                        ) recent ON sw.staff_id = recent.assigned_to
                        WHERE sw.guild_id = %s
                        ORDER BY sw.total_completed DESC, sw.avg_completion_time ASC
                    """,
                        (guild_id, days, guild_id),
                    )

                    results = await cursor.fetchall()
                    columns = [desc[0] for desc in cursor.description]

                    performance_data = []
                    for row in results:
                        data = dict(zip(columns, row))
                        # 計算效率分數
                        completion_rate = float(data.get("completion_rate", 0))
                        avg_time = data.get("avg_completion_time", 0)
                        recent_completed = data.get("recent_completed", 0)

                        efficiency_score = 0
                        if completion_rate > 0:
                            efficiency_score = completion_rate
                            if avg_time > 0 and avg_time < 1440:  # 24小時內
                                efficiency_score += (
                                    (1440 - avg_time) / 1440 * 20
                                )  # 最多加20分
                            if recent_completed > 0:
                                efficiency_score += min(
                                    recent_completed * 5, 30
                                )  # 最多加30分

                        data["efficiency_score"] = round(efficiency_score, 2)
                        performance_data.append(data)

                    return performance_data

        except Exception as e:
            logger.error(f"取得工作人員表現錯誤：{e}")
            return []
