# bot/db/archive_dao.py
"""
歷史資料歸檔資料存取物件
處理資料歸檔、清理和格式化功能
"""

import json
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Dict, List

import aiomysql

from potato_shared.logger import logger

from .base_dao import BaseDAO


@dataclass
class ArchiveConfig:
    """歸檔配置"""

    retain_days: int = 90
    archive_before_delete: bool = True
    batch_size: int = 1000
    include_attachments: bool = True
    compress_data: bool = True


class ArchiveDAO(BaseDAO):
    """歷史資料歸檔資料存取物件"""

    def __init__(self):
        super().__init__()

    async def _initialize(self):
        """初始化歷史歸檔DAO"""
        logger.info("✅ 歷史歸檔 DAO 初始化完成")

    async def archive_old_tickets(
        self, guild_id: int, days_old: int = 90, batch_size: int = 1000
    ) -> Dict[str, int]:
        """歸檔舊票券"""
        try:
            async with self.db.connection() as conn:
                async with conn.cursor(aiomysql.DictCursor) as cursor:
                    cutoff_date = datetime.now() - timedelta(days=days_old)

                    # 查詢需要歸檔的票券
                    query = """
                    SELECT t.*,
                           GROUP_CONCAT(tm.content ORDER BY tm.created_at SEPARATOR '\\n---\\n') as messages,
                           COUNT(tm.id) as message_count
                    FROM tickets t
                    LEFT JOIN ticket_messages tm ON t.id = tm.ticket_id
                    WHERE t.guild_id = %s
                    AND t.status = 'closed'
                    AND t.closed_at <= %s
                    GROUP BY t.id
                    LIMIT %s
                    """

                    await cursor.execute(query, (guild_id, cutoff_date, batch_size))
                    tickets_to_archive = await cursor.fetchall()

                    archived_count = 0

                    for ticket in tickets_to_archive:
                        # 準備歸檔資料
                        ticket_data = {
                            "id": ticket["id"],
                            "discord_id": ticket["discord_id"],
                            "username": ticket["username"],
                            "type": ticket["type"],
                            "priority": ticket["priority"],
                            "status": ticket["status"],
                            "channel_id": ticket["channel_id"],
                            "assigned_to": ticket["assigned_to"],
                            "rating": ticket["rating"],
                            "rating_feedback": ticket["rating_feedback"],
                            "created_at": (
                                ticket["created_at"].isoformat() if ticket["created_at"] else None
                            ),
                            "closed_at": (
                                ticket["closed_at"].isoformat() if ticket["closed_at"] else None
                            ),
                            "closed_by": ticket["closed_by"],
                            "close_reason": ticket["close_reason"],
                            "message_count": ticket["message_count"],
                        }

                        messages_data = {
                            "messages": (ticket["messages"] if ticket["messages"] else ""),
                            "message_count": ticket["message_count"],
                        }

                        # 插入到歸檔表
                        archive_query = """
                        INSERT INTO ticket_archive (
                            original_ticket_id, guild_id, ticket_data,
                            messages_data, archive_reason
                        ) VALUES (%s, %s, %s, %s, %s)
                        """

                        await cursor.execute(
                            archive_query,
                            (
                                ticket["id"],
                                guild_id,
                                json.dumps(ticket_data, ensure_ascii=False),
                                json.dumps(messages_data, ensure_ascii=False),
                                f"auto_cleanup_{days_old}_days",
                            ),
                        )

                        archived_count += 1

                    await conn.commit()

                    logger.info(f"成功歸檔 {archived_count} 個票券")
                    return {
                        "archived": archived_count,
                        "processed": len(tickets_to_archive),
                        "cutoff_date": cutoff_date.isoformat(),
                    }

        except Exception as e:
            logger.error(f"歸檔舊票券失敗: {e}")
            return {"error": str(e)}

    async def archive_old_votes(
        self, guild_id: int, days_old: int = 90, batch_size: int = 1000
    ) -> Dict[str, int]:
        """歸檔舊投票"""
        try:
            async with self.db.connection() as conn:
                async with conn.cursor(aiomysql.DictCursor) as cursor:
                    cutoff_date = datetime.now() - timedelta(days=days_old)

                    # 查詢需要歸檔的投票
                    query = """
                    SELECT v.*,
                           JSON_ARRAYAGG(
                               JSON_OBJECT(
                                   'id', vo.id,
                                   'text', vo.option_text,
                                   'emoji', vo.emoji,
                                   'votes', vo.vote_count
                               )
                           ) as options_data,
                           COUNT(DISTINCT vr.user_id) as total_voters
                    FROM votes v
                    LEFT JOIN vote_options vo ON v.id = vo.vote_id
                    LEFT JOIN vote_responses vr ON v.id = vr.vote_id
                    WHERE v.guild_id = %s
                    AND v.status = 'ended'
                    AND v.end_time <= %s
                    GROUP BY v.id
                    LIMIT %s
                    """

                    await cursor.execute(query, (guild_id, cutoff_date, batch_size))
                    votes_to_archive = await cursor.fetchall()

                    archived_count = 0

                    for vote in votes_to_archive:
                        # 獲取投票回應詳細資料
                        responses_query = """
                        SELECT vr.user_id, vr.username, vr.selected_option, vr.voted_at
                        FROM vote_responses vr
                        WHERE vr.vote_id = %s
                        ORDER BY vr.voted_at
                        """

                        await cursor.execute(responses_query, (vote["id"],))
                        responses = await cursor.fetchall()

                        # 準備歸檔資料
                        vote_data = {
                            "id": vote["id"],
                            "title": vote["title"],
                            "description": vote["description"],
                            "creator_id": vote["creator_id"],
                            "channel_id": vote["channel_id"],
                            "message_id": vote["message_id"],
                            "vote_type": vote["vote_type"],
                            "multiple_choice": vote["multiple_choice"],
                            "anonymous": vote["anonymous"],
                            "created_at": (
                                vote["created_at"].isoformat() if vote["created_at"] else None
                            ),
                            "end_time": (
                                vote["end_time"].isoformat() if vote["end_time"] else None
                            ),
                            "status": vote["status"],
                            "total_voters": vote["total_voters"],
                        }

                        options_data = (
                            json.loads(vote["options_data"]) if vote["options_data"] else []
                        )
                        responses_data = [
                            {
                                "user_id": str(r["user_id"]),
                                "username": r["username"],
                                "selected_option": r["selected_option"],
                                "voted_at": (r["voted_at"].isoformat() if r["voted_at"] else None),
                            }
                            for r in responses
                        ]

                        # 計算結果統計
                        results_data = {
                            "total_votes": len(responses),
                            "options_results": options_data,
                            "participation_rate": len(responses)
                            / max(vote["total_voters"], 1)
                            * 100,
                        }

                        # 插入到歸檔表
                        archive_query = """
                        INSERT INTO vote_archive (
                            original_vote_id, guild_id, vote_data,
                            options_data, responses_data, results_data, archive_reason
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s)
                        """

                        await cursor.execute(
                            archive_query,
                            (
                                vote["id"],
                                guild_id,
                                json.dumps(vote_data, ensure_ascii=False),
                                json.dumps(options_data, ensure_ascii=False),
                                json.dumps(responses_data, ensure_ascii=False),
                                json.dumps(results_data, ensure_ascii=False),
                                f"auto_cleanup_{days_old}_days",
                            ),
                        )

                        archived_count += 1

                    await conn.commit()

                    logger.info(f"成功歸檔 {archived_count} 個投票")
                    return {
                        "archived": archived_count,
                        "processed": len(votes_to_archive),
                        "cutoff_date": cutoff_date.isoformat(),
                    }

        except Exception as e:
            logger.error(f"歸檔舊投票失敗: {e}")
            return {"error": str(e)}

    async def archive_user_activity(self, guild_id: int, period: str = "monthly") -> Dict[str, int]:
        """歸檔用戶活動資料"""
        try:
            async with self.db.connection() as conn:
                async with conn.cursor(aiomysql.DictCursor) as cursor:

                    # 根據期間設定日期範圍
                    if period == "monthly":
                        start_date = datetime.now().replace(day=1) - timedelta(days=32)
                        start_date = start_date.replace(day=1)
                        end_date = datetime.now().replace(day=1) - timedelta(days=1)
                    elif period == "weekly":
                        start_date = datetime.now() - timedelta(days=14)
                        end_date = datetime.now() - timedelta(days=7)
                    else:
                        start_date = datetime.now() - timedelta(days=30)
                        end_date = datetime.now()

                    # 查詢用戶活動統計
                    activity_query = """
                    SELECT
                        t.discord_id as user_id,
                        t.username,
                        COUNT(DISTINCT t.id) as tickets_count,
                        COUNT(DISTINCT v.id) as votes_count,
                        MIN(t.created_at) as first_activity,
                        MAX(GREATEST(t.created_at, IFNULL(v.created_at, t.created_at))) as last_activity
                    FROM tickets t
                    LEFT JOIN vote_responses vr ON t.discord_id = vr.user_id::CHAR
                    LEFT JOIN votes v ON vr.vote_id = v.id AND v.guild_id = %s
                    WHERE t.guild_id = %s
                    AND t.created_at BETWEEN %s AND %s
                    GROUP BY t.discord_id, t.username
                    HAVING tickets_count > 0 OR votes_count > 0
                    """

                    await cursor.execute(
                        activity_query,
                        (guild_id, guild_id, start_date, end_date),
                    )
                    user_activities = await cursor.fetchall()

                    archived_count = 0

                    for activity in user_activities:
                        activity_data = {
                            "tickets_count": activity["tickets_count"],
                            "votes_count": activity["votes_count"],
                            "total_interactions": activity["tickets_count"]
                            + activity["votes_count"],
                            "period_start": start_date.isoformat(),
                            "period_end": end_date.isoformat(),
                        }

                        # 插入到用戶活動歸檔
                        archive_query = """
                        INSERT INTO user_activity_archive (
                            user_id, guild_id, activity_period, activity_data,
                            tickets_count, votes_count, first_activity, last_activity
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                        ON DUPLICATE KEY UPDATE
                            activity_data = VALUES(activity_data),
                            tickets_count = VALUES(tickets_count),
                            votes_count = VALUES(votes_count),
                            last_activity = VALUES(last_activity)
                        """

                        period_key = f"{period}_{start_date.strftime('%Y_%m')}"

                        await cursor.execute(
                            archive_query,
                            (
                                activity["user_id"],
                                guild_id,
                                period_key,
                                json.dumps(activity_data, ensure_ascii=False),
                                activity["tickets_count"],
                                activity["votes_count"],
                                activity["first_activity"],
                                activity["last_activity"],
                            ),
                        )

                        archived_count += 1

                    await conn.commit()

                    logger.info(f"成功歸檔 {archived_count} 個用戶活動記錄")
                    return {
                        "archived": archived_count,
                        "period": period,
                        "start_date": start_date.isoformat(),
                        "end_date": end_date.isoformat(),
                    }

        except Exception as e:
            logger.error(f"歸檔用戶活動失敗: {e}")
            return {"error": str(e)}

    async def cleanup_old_data(
        self,
        guild_id: int,
        data_type: str,
        days_old: int = 90,
        delete_after_archive: bool = True,
    ) -> Dict[str, int]:
        """清理舊資料"""
        try:
            async with self.db.connection() as conn:
                async with conn.cursor() as cursor:
                    cutoff_date = datetime.now() - timedelta(days=days_old)
                    deleted_count = 0

                    if data_type == "tickets":
                        if delete_after_archive:
                            # 刪除已歸檔的舊票券
                            delete_query = """
                            DELETE t FROM tickets t
                            WHERE t.guild_id = %s
                            AND t.status = 'closed'
                            AND t.closed_at <= %s
                            AND EXISTS (
                                SELECT 1 FROM ticket_archive ta
                                WHERE ta.original_ticket_id = t.id
                            )
                            """
                            await cursor.execute(delete_query, (guild_id, cutoff_date))
                            deleted_count = cursor.rowcount

                    elif data_type == "votes":
                        if delete_after_archive:
                            # 刪除已歸檔的舊投票
                            delete_query = """
                            DELETE v FROM votes v
                            WHERE v.guild_id = %s
                            AND v.status = 'ended'
                            AND v.end_time <= %s
                            AND EXISTS (
                                SELECT 1 FROM vote_archive va
                                WHERE va.original_vote_id = v.id
                            )
                            """
                            await cursor.execute(delete_query, (guild_id, cutoff_date))
                            deleted_count = cursor.rowcount

                    elif data_type == "logs":
                        # 清理舊日誌
                        tables_to_clean = [
                            "ticket_logs",
                            "vote_logs",
                            "cleanup_logs",
                            "webhook_logs",
                            "export_logs",
                        ]

                        for table in tables_to_clean:
                            try:
                                clean_query = f"""
                                DELETE FROM {table}
                                WHERE guild_id = %s AND created_at <= %s
                                """
                                await cursor.execute(clean_query, (guild_id, cutoff_date))
                                deleted_count += cursor.rowcount
                            except Exception:
                                continue  # 如果表不存在就跳過

                    await conn.commit()

                    # 記錄清理動作
                    log_query = """
                    INSERT INTO cleanup_logs (guild_id, cleanup_type, items_cleaned, cutoff_date)
                    VALUES (%s, %s, %s, %s)
                    """
                    await cursor.execute(
                        log_query,
                        (guild_id, data_type, deleted_count, cutoff_date),
                    )
                    await conn.commit()

                    logger.info(f"清理 {data_type} 資料完成: 刪除了 {deleted_count} 筆記錄")
                    return {
                        "deleted": deleted_count,
                        "data_type": data_type,
                        "cutoff_date": cutoff_date.isoformat(),
                    }

        except Exception as e:
            logger.error(f"清理舊資料失敗: {e}")
            return {"error": str(e)}

    async def get_cleanup_schedules(self, guild_id: int) -> List[Dict]:
        """獲取清理排程"""
        try:
            async with self.db.connection() as conn:
                async with conn.cursor(aiomysql.DictCursor) as cursor:
                    query = """
                    SELECT * FROM cleanup_schedules
                    WHERE guild_id = %s AND is_enabled = TRUE
                    ORDER BY next_run ASC
                    """

                    await cursor.execute(query, (guild_id,))
                    schedules = await cursor.fetchall()

                    # 解析JSON欄位
                    for schedule in schedules:
                        if schedule["conditions"]:
                            schedule["conditions"] = json.loads(schedule["conditions"])

                    return schedules

        except Exception as e:
            logger.error(f"獲取清理排程失敗: {e}")
            return []

    async def create_cleanup_schedule(self, guild_id: int, schedule_config: Dict[str, Any]) -> int:
        """創建清理排程"""
        try:
            async with self.db.connection() as conn:
                async with conn.cursor() as cursor:
                    # 計算下次執行時間
                    now = datetime.now()
                    if schedule_config["schedule_type"] == "daily":
                        next_run = now + timedelta(days=1)
                    elif schedule_config["schedule_type"] == "weekly":
                        next_run = now + timedelta(weeks=1)
                    elif schedule_config["schedule_type"] == "monthly":
                        next_run = now + timedelta(days=30)
                    else:
                        next_run = now + timedelta(days=schedule_config.get("custom_days", 7))

                    query = """
                    INSERT INTO cleanup_schedules (
                        guild_id, cleanup_type, schedule_type, retention_days,
                        archive_before_delete, conditions, next_run
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s)
                    """

                    await cursor.execute(
                        query,
                        (
                            guild_id,
                            schedule_config["cleanup_type"],
                            schedule_config["schedule_type"],
                            schedule_config.get("retention_days", 90),
                            schedule_config.get("archive_before_delete", True),
                            json.dumps(schedule_config.get("conditions", {})),
                            next_run,
                        ),
                    )

                    schedule_id = cursor.lastrowid
                    await conn.commit()

                    logger.info(f"創建清理排程成功: {schedule_id}")
                    return schedule_id

        except Exception as e:
            logger.error(f"創建清理排程失敗: {e}")
            return 0

    async def get_archive_statistics(self, guild_id: int) -> Dict[str, Any]:
        """獲取歷史資料統計"""
        try:
            async with self.db.connection() as conn:
                async with conn.cursor(aiomysql.DictCursor) as cursor:

                    # 票券歷史統計
                    ticket_stats_query = """
                    SELECT
                        COUNT(*) as total_archived_tickets,
                        COUNT(CASE WHEN archived_at >= DATE_SUB(NOW(), INTERVAL 30 DAY) THEN 1 END) as recent_archived_tickets
                    FROM ticket_archive
                    WHERE guild_id = %s
                    """

                    await cursor.execute(ticket_stats_query, (guild_id,))
                    ticket_stats = await cursor.fetchone()

                    # 投票歷史統計
                    vote_stats_query = """
                    SELECT
                        COUNT(*) as total_archived_votes,
                        COUNT(CASE WHEN archived_at >= DATE_SUB(NOW(), INTERVAL 30 DAY) THEN 1 END) as recent_archived_votes
                    FROM vote_archive
                    WHERE guild_id = %s
                    """

                    await cursor.execute(vote_stats_query, (guild_id,))
                    vote_stats = await cursor.fetchone()

                    # 活動歷史統計
                    activity_stats_query = """
                    SELECT
                        COUNT(*) as total_archived_activities,
                        COUNT(DISTINCT user_id) as unique_users_archived,
                        COUNT(CASE WHEN archived_at >= DATE_SUB(NOW(), INTERVAL 30 DAY) THEN 1 END) as recent_archived_activities
                    FROM user_activity_archive
                    WHERE guild_id = %s
                    """

                    await cursor.execute(activity_stats_query, (guild_id,))
                    activity_stats = await cursor.fetchone()

                    return {
                        "guild_id": guild_id,
                        "ticket_archives": ticket_stats or {},
                        "vote_archives": vote_stats or {},
                        "activity_archives": activity_stats or {},
                        "generated_at": datetime.now().isoformat(),
                    }

        except Exception as e:
            logger.error(f"獲取歷史資料統計失敗: {e}")
            return {}
