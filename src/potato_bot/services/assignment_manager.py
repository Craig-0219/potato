# bot/services/assignment_manager.py - 票券指派管理服務
"""
票券指派管理服務
處理自動指派、手動指派、工作量平衡等業務邏輯
"""

from typing import Any, Dict, List, Optional, Tuple

from potato_bot.db.assignment_dao import AssignmentDAO
from potato_bot.db.ticket_dao import TicketDAO
from potato_shared.logger import logger


class AssignmentManager:
    """票券指派管理器"""

    def __init__(
        self,
        assignment_dao: AssignmentDAO = None,
        ticket_dao: TicketDAO = None,
    ):
        self.assignment_dao = assignment_dao or AssignmentDAO()
        self.ticket_dao = ticket_dao or TicketDAO()

    # ========== 核心指派功能 ==========

    async def assign_ticket(
        self,
        ticket_id: int,
        assigned_to: int,
        assigned_by: int,
        method: str = "manual",
        reason: str = "手動指派",
    ) -> Tuple[bool, str]:
        """指派票券給客服人員"""
        try:
            # 取得票券資訊
            ticket = await self.ticket_dao.get_ticket_by_id(ticket_id)
            if not ticket:
                return False, "票券不存在"

            if ticket["status"] != "open":
                return False, "只能指派開啟中的票券"

            # 檢查客服人員當前工作量
            guild_id = ticket["guild_id"]
            workload = await self.assignment_dao.get_staff_workload(guild_id, assigned_to)

            # 取得指派規則
            assignment_rule = await self.assignment_dao.get_assignment_rule(
                guild_id, ticket["type"], ticket.get("priority", "medium")
            )
            max_concurrent = assignment_rule["max_concurrent_tickets"] if assignment_rule else 5

            if workload and workload["current_tickets"] >= max_concurrent:
                return (
                    False,
                    f"客服人員當前工作量已達上限（{max_concurrent}張票券）",
                )

            # 執行指派
            original_assigned = ticket.get("assigned_to")
            success = await self.ticket_dao.assign_ticket(ticket_id, assigned_to, assigned_by)

            if success:
                # 更新工作量
                await self.assignment_dao.update_staff_workload(
                    guild_id, assigned_to, increment_assigned=True
                )

                # 如果原本有指派其他人，減少原客服的工作量
                if original_assigned and original_assigned != assigned_to:
                    original_workload = await self.assignment_dao.get_staff_workload(
                        guild_id, original_assigned
                    )
                    if original_workload:
                        new_current = max(0, original_workload["current_tickets"] - 1)
                        await self.assignment_dao.update_staff_workload(
                            guild_id,
                            original_assigned,
                            current_tickets=new_current,
                        )

                # 記錄指派歷史
                await self.assignment_dao.record_assignment(
                    ticket_id,
                    original_assigned,
                    assigned_to,
                    assigned_by,
                    reason,
                    method,
                )

                logger.info(
                    f"票券 #{ticket_id} 指派給客服 {assigned_to} by {assigned_by} ({method})"
                )
                return True, f"成功指派票券 #{ticket_id} 給客服人員"
            else:
                return False, "指派失敗，請稍後再試"

        except Exception as e:
            logger.error(f"指派票券錯誤：{e}")
            return False, f"指派過程中發生錯誤：{str(e)}"

    async def auto_assign_ticket(
        self, ticket_id: int, assigned_by: int
    ) -> Tuple[bool, str, Optional[int]]:
        """自動指派票券"""
        try:
            # 取得票券資訊
            ticket = await self.ticket_dao.get_ticket_by_id(ticket_id)
            if not ticket:
                return False, "票券不存在", None

            guild_id = ticket["guild_id"]
            ticket_type = ticket["type"]
            priority = ticket.get("priority", "medium")

            # 取得指派規則
            assignment_rule = await self.assignment_dao.get_assignment_rule(
                guild_id, ticket_type, priority
            )

            if not assignment_rule:
                # 建立預設規則
                await self.assignment_dao.create_assignment_rule(
                    guild_id, "default", None, None, "auto_least_workload", 5
                )
                assignment_rule = await self.assignment_dao.get_assignment_rule(guild_id)

            method = assignment_rule["assignment_method"]
            max_concurrent = assignment_rule["max_concurrent_tickets"]

            # 根據指派方法選擇客服
            assigned_to = None

            if method == "auto_least_workload":
                assigned_to = await self._assign_by_least_workload(guild_id, max_concurrent)
            elif method == "auto_round_robin":
                assigned_to = await self._assign_by_round_robin(guild_id, max_concurrent)
            elif method == "auto_specialty":
                assigned_to = await self._assign_by_specialty(guild_id, ticket_type, max_concurrent)

            if assigned_to:
                success, message = await self.assign_ticket(
                    ticket_id,
                    assigned_to,
                    assigned_by,
                    method,
                    f"自動指派（{method}）",
                )
                return success, message, assigned_to
            else:
                return False, "沒有可用的客服人員", None

        except Exception as e:
            logger.error(f"自動指派票券錯誤：{e}")
            return False, f"自動指派過程中發生錯誤：{str(e)}", None

    # ========== 指派演算法 ==========

    async def _assign_by_least_workload(self, guild_id: int, max_concurrent: int) -> Optional[int]:
        """根據最少工作量指派"""
        available_staff = await self.assignment_dao.get_available_staff(guild_id, max_concurrent)
        if available_staff:
            # 選擇工作量最少的客服
            return available_staff[0]["staff_id"]
        return None

    async def _assign_by_round_robin(self, guild_id: int, max_concurrent: int) -> Optional[int]:
        """輪流指派"""
        available_staff = await self.assignment_dao.get_available_staff(guild_id, max_concurrent)
        if available_staff:
            # 找出最久沒有被指派的客服
            oldest_assignment = None
            selected_staff = None

            for staff in available_staff:
                if staff["last_assigned_at"] is None:
                    # 從未被指派過的客服優先
                    return staff["staff_id"]

                if oldest_assignment is None or staff["last_assigned_at"] < oldest_assignment:
                    oldest_assignment = staff["last_assigned_at"]
                    selected_staff = staff["staff_id"]

            return selected_staff
        return None

    async def _assign_by_specialty(
        self, guild_id: int, ticket_type: str, max_concurrent: int
    ) -> Optional[int]:
        """根據專精指派"""
        # 先嘗試找專精匹配的客服
        specialty_staff = await self.assignment_dao.find_specialty_staff(guild_id, ticket_type)

        for staff in specialty_staff:
            workload = await self.assignment_dao.get_staff_workload(guild_id, staff["staff_id"])
            current_tickets = workload["current_tickets"] if workload else 0

            if current_tickets < max_concurrent:
                return staff["staff_id"]

        # 沒有專精匹配的，回退到最少工作量
        return await self._assign_by_least_workload(guild_id, max_concurrent)

    # ========== 工作量管理 ==========

    async def update_ticket_completion(self, ticket_id: int) -> bool:
        """更新票券完成狀態（當票券關閉時調用）"""
        try:
            ticket = await self.ticket_dao.get_ticket_by_id(ticket_id)
            if not ticket or not ticket.get("assigned_to"):
                return False

            guild_id = ticket["guild_id"]
            staff_id = ticket["assigned_to"]

            # 計算處理時間
            if ticket.get("created_at") and ticket.get("closed_at"):
                duration = ticket["closed_at"] - ticket["created_at"]
                completion_time_minutes = int(duration.total_seconds() / 60)
            else:
                completion_time_minutes = None

            # 更新工作量統計
            await self.assignment_dao.update_staff_workload(
                guild_id,
                int(staff_id),
                increment_completed=True,
                completion_time_minutes=completion_time_minutes,
            )

            logger.info(f"更新客服 {staff_id} 票券完成統計")
            return True

        except Exception as e:
            logger.error(f"更新票券完成狀態錯誤：{e}")
            return False

    async def get_staff_workload_summary(self, guild_id: int) -> List[Dict[str, Any]]:
        """取得所有客服工作量摘要"""
        try:
            available_staff = await self.assignment_dao.get_available_staff(
                guild_id, 999
            )  # 取得所有客服

            summary = []
            for staff in available_staff:
                workload = await self.assignment_dao.get_staff_workload(guild_id, staff["staff_id"])
                if workload:
                    # 計算效率指標
                    completion_rate = 0
                    if workload["total_assigned"] > 0:
                        completion_rate = (
                            workload["total_completed"] / workload["total_assigned"]
                        ) * 100

                    # 工作負載狀態
                    load_status = "輕鬆"
                    if workload["current_tickets"] >= 5:
                        load_status = "繁忙"
                    elif workload["current_tickets"] >= 3:
                        load_status = "適中"

                    summary.append(
                        {
                            "staff_id": staff["staff_id"],
                            "current_tickets": workload["current_tickets"],
                            "total_assigned": workload["total_assigned"],
                            "total_completed": workload["total_completed"],
                            "completion_rate": round(completion_rate, 1),
                            "avg_completion_time": workload["avg_completion_time"],
                            "load_status": load_status,
                            "last_assigned_at": workload["last_assigned_at"],
                        }
                    )

            # 按當前工作量排序
            summary.sort(key=lambda x: x["current_tickets"])
            return summary

        except Exception as e:
            logger.error(f"取得工作量摘要錯誤：{e}")
            return []

    # ========== 專精管理 ==========

    async def add_staff_specialty(
        self,
        guild_id: int,
        staff_id: int,
        specialty_type: str,
        skill_level: str = "intermediate",
    ) -> Tuple[bool, str]:
        """添加客服專精"""
        try:
            # 驗證技能等級
            valid_levels = ["beginner", "intermediate", "advanced", "expert"]
            if skill_level not in valid_levels:
                return (
                    False,
                    f"無效的技能等級，請使用：{', '.join(valid_levels)}",
                )

            success = await self.assignment_dao.add_staff_specialty(
                guild_id, staff_id, specialty_type, skill_level
            )

            if success:
                return (
                    True,
                    f"成功設定客服專精：{specialty_type} ({skill_level})",
                )
            else:
                return False, "設定專精失敗，請稍後再試"

        except Exception as e:
            logger.error(f"添加客服專精錯誤：{e}")
            return False, f"設定過程中發生錯誤：{str(e)}"

    async def get_staff_profile(self, guild_id: int, staff_id: int) -> Dict[str, Any]:
        """取得客服人員完整檔案"""
        try:
            # 取得工作量資訊
            workload = await self.assignment_dao.get_staff_workload(guild_id, staff_id)
            if not workload:
                # 初始化工作量記錄
                await self.assignment_dao.initialize_staff_workload(guild_id, staff_id)
                workload = await self.assignment_dao.get_staff_workload(guild_id, staff_id)

            # 取得專精資訊
            specialties = await self.assignment_dao.get_staff_specialties(guild_id, staff_id)

            # 組合檔案資訊
            profile = {
                "staff_id": staff_id,
                "workload": workload,
                "specialties": specialties,
                "performance_metrics": {
                    "completion_rate": 0,
                    "efficiency_score": 0,
                    "specialization_count": len(specialties),
                },
            }

            # 計算績效指標
            if workload["total_assigned"] > 0:
                profile["performance_metrics"]["completion_rate"] = (
                    workload["total_completed"] / workload["total_assigned"]
                ) * 100

            # 效率分數（基於平均完成時間和完成率）
            if workload["avg_completion_time"] > 0:
                time_score = max(0, 100 - (workload["avg_completion_time"] / 60))  # 以1小時為基準
                completion_score = profile["performance_metrics"]["completion_rate"]
                profile["performance_metrics"]["efficiency_score"] = (
                    time_score + completion_score
                ) / 2

            return profile

        except Exception as e:
            logger.error(f"取得客服檔案錯誤：{e}")
            return {}

    # ========== 統計與報告 ==========

    async def get_assignment_analytics(self, guild_id: int, days: int = 30) -> Dict[str, Any]:
        """取得指派分析報告"""
        try:
            # 基礎統計
            stats = await self.assignment_dao.get_assignment_statistics(guild_id, days)

            # 工作量摘要
            workload_summary = await self.get_staff_workload_summary(guild_id)

            # 計算整體指標
            total_current_tickets = sum(staff["current_tickets"] for staff in workload_summary)
            total_completed = sum(staff["total_completed"] for staff in workload_summary)
            avg_completion_rate = (
                sum(staff["completion_rate"] for staff in workload_summary) / len(workload_summary)
                if workload_summary
                else 0
            )

            # 工作量分佈
            load_distribution = {
                "輕鬆": len([s for s in workload_summary if s["load_status"] == "輕鬆"]),
                "適中": len([s for s in workload_summary if s["load_status"] == "適中"]),
                "繁忙": len([s for s in workload_summary if s["load_status"] == "繁忙"]),
            }

            return {
                "period_days": days,
                "assignment_methods": stats["assignment_methods"],
                "staff_count": len(workload_summary),
                "total_current_tickets": total_current_tickets,
                "total_completed_tickets": total_completed,
                "avg_completion_rate": round(avg_completion_rate, 1),
                "workload_distribution": load_distribution,
                "staff_summary": workload_summary[:10],  # 只返回前10名
            }

        except Exception as e:
            logger.error(f"取得指派分析錯誤：{e}")
            return {}
