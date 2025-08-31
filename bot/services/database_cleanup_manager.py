# bot/services/database_cleanup_manager.py
"""
資料庫清理與格式化管理器
負責歷史資料的歸檔、清理和維護工作
"""

from datetime import datetime
from typing import Any, Dict, List

from discord.ext import tasks

from bot.db.archive_dao import ArchiveDAO
from shared.logger import logger


class DatabaseCleanupManager:
    """資料庫清理與格式化管理器"""

    def __init__(self, bot=None):
        self.bot = bot
        self.dao = ArchiveDAO()
        self._cleanup_in_progress = {}  # guild_id -> bool

        # 啟動背景清理任務
        if bot:
            self.cleanup_scheduler.start()

    async def perform_comprehensive_cleanup(
        self, guild_id: int, cleanup_config: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """執行全面的資料庫清理"""
        if guild_id in self._cleanup_in_progress:
            return {"error": "清理作業正在進行中，請稍候"}

        try:
            self._cleanup_in_progress[guild_id] = True
            logger.info(f"開始執行伺服器 {guild_id} 的全面資料庫清理")

            # 預設清理配置
            default_config = {
                "ticket_retention_days": 90,
                "vote_retention_days": 60,
                "log_retention_days": 30,
                "archive_before_delete": True,
                "batch_size": 1000,
            }

            config = {**default_config, **(cleanup_config or {})}
            results = {}

            # 1. 歸檔舊票券
            logger.info(
                f"歸檔 {config['ticket_retention_days']} 天前的票券..."
            )
            ticket_result = await self.dao.archive_old_tickets(
                guild_id, config["ticket_retention_days"], config["batch_size"]
            )
            results["tickets_archived"] = ticket_result

            # 2. 歸檔舊投票
            logger.info(f"歸檔 {config['vote_retention_days']} 天前的投票...")
            vote_result = await self.dao.archive_old_votes(
                guild_id, config["vote_retention_days"], config["batch_size"]
            )
            results["votes_archived"] = vote_result

            # 3. 歸檔用戶活動
            logger.info("歸檔月度用戶活動資料...")
            activity_result = await self.dao.archive_user_activity(
                guild_id, "monthly"
            )
            results["activities_archived"] = activity_result

            # 4. 清理日誌
            if config.get("clean_logs", True):
                logger.info(
                    f"清理 {config['log_retention_days']} 天前的日誌..."
                )
                log_result = await self.dao.cleanup_old_data(
                    guild_id,
                    "logs",
                    config["log_retention_days"],
                    False,  # 日誌不需要歸檔
                )
                results["logs_cleaned"] = log_result

            # 5. 清理已歸檔的原始資料（如果啟用）
            if config["archive_before_delete"]:
                logger.info("清理已歸檔的原始票券資料...")
                ticket_cleanup = await self.dao.cleanup_old_data(
                    guild_id, "tickets", config["ticket_retention_days"], True
                )
                results["tickets_cleaned"] = ticket_cleanup

                logger.info("清理已歸檔的原始投票資料...")
                vote_cleanup = await self.dao.cleanup_old_data(
                    guild_id, "votes", config["vote_retention_days"], True
                )
                results["votes_cleaned"] = vote_cleanup

            # 6. 統計結果
            total_archived = (
                ticket_result.get("archived", 0)
                + vote_result.get("archived", 0)
                + activity_result.get("archived", 0)
            )

            total_cleaned = (
                results.get("logs_cleaned", {}).get("deleted", 0)
                + results.get("tickets_cleaned", {}).get("deleted", 0)
                + results.get("votes_cleaned", {}).get("deleted", 0)
            )

            cleanup_summary = {
                "guild_id": guild_id,
                "cleanup_completed_at": datetime.now().isoformat(),
                "config_used": config,
                "total_items_archived": total_archived,
                "total_items_deleted": total_cleaned,
                "detailed_results": results,
                "success": True,
            }

            logger.info(
                f"伺服器 {guild_id} 資料庫清理完成 - 歸檔: {total_archived}, 刪除: {total_cleaned}"
            )
            return cleanup_summary

        except Exception as e:
            logger.error(f"執行資料庫清理失敗: {e}")
            return {
                "guild_id": guild_id,
                "cleanup_completed_at": datetime.now().isoformat(),
                "success": False,
                "error": str(e),
            }
        finally:
            self._cleanup_in_progress.pop(guild_id, None)

    async def archive_specific_period(
        self,
        guild_id: int,
        data_type: str,
        start_date: datetime,
        end_date: datetime,
    ) -> Dict[str, Any]:
        """歸檔特定時期的資料"""
        try:
            logger.info(
                f"歸檔 {guild_id} 的 {data_type} 資料: {start_date} 到 {end_date}"
            )

            if data_type == "tickets":
                # 自定義查詢歸檔特定期間的票券
                result = await self._archive_tickets_by_period(
                    guild_id, start_date, end_date
                )
            elif data_type == "votes":
                # 自定義查詢歸檔特定期間的投票
                result = await self._archive_votes_by_period(
                    guild_id, start_date, end_date
                )
            else:
                return {"error": f"不支援的資料類型: {data_type}"}

            return {
                "data_type": data_type,
                "period_start": start_date.isoformat(),
                "period_end": end_date.isoformat(),
                "result": result,
                "success": True,
            }

        except Exception as e:
            logger.error(f"歸檔特定期間資料失敗: {e}")
            return {"success": False, "error": str(e)}

    async def _archive_tickets_by_period(
        self, guild_id: int, start_date: datetime, end_date: datetime
    ) -> Dict[str, Any]:
        """歸檔特定期間的票券"""
        # 這裡可以實現更精確的期間歸檔邏輯
        # 目前使用現有的方法，但可以擴展為更靈活的查詢
        return await self.dao.archive_old_tickets(
            guild_id, 0, 1000
        )  # 暫時實現

    async def _archive_votes_by_period(
        self, guild_id: int, start_date: datetime, end_date: datetime
    ) -> Dict[str, Any]:
        """歸檔特定期間的投票"""
        # 這裡可以實現更精確的期間歸檔邏輯
        return await self.dao.archive_old_votes(guild_id, 0, 1000)  # 暫時實現

    async def setup_cleanup_schedule(
        self, guild_id: int, schedule_config: Dict[str, Any]
    ) -> Dict[str, Any]:
        """設置清理排程"""
        try:
            schedule_id = await self.dao.create_cleanup_schedule(
                guild_id, schedule_config
            )

            if schedule_id:
                logger.info(f"創建清理排程成功: {schedule_id}")
                return {
                    "success": True,
                    "schedule_id": schedule_id,
                    "config": schedule_config,
                }
            else:
                return {"success": False, "error": "創建清理排程失敗"}

        except Exception as e:
            logger.error(f"設置清理排程失敗: {e}")
            return {"success": False, "error": str(e)}

    async def get_cleanup_schedules(self, guild_id: int) -> List[Dict]:
        """獲取清理排程列表"""
        try:
            return await self.dao.get_cleanup_schedules(guild_id)
        except Exception as e:
            logger.error(f"獲取清理排程失敗: {e}")
            return []

    async def optimize_database_storage(self, guild_id: int) -> Dict[str, Any]:
        """優化資料庫儲存"""
        try:
            logger.info(f"開始優化伺服器 {guild_id} 的資料庫儲存")

            optimization_results = {}

            # 1. 壓縮歷史資料（移除重複和不必要的欄位）
            compression_result = await self._compress_archived_data(guild_id)
            optimization_results["compression"] = compression_result

            # 2. 重建索引（理論上的操作，實際可能需要DBA權限）
            index_result = await self._optimize_database_indexes(guild_id)
            optimization_results["indexes"] = index_result

            # 3. 統計和分析
            stats_result = await self.get_storage_statistics(guild_id)
            optimization_results["statistics"] = stats_result

            return {
                "guild_id": guild_id,
                "optimization_completed_at": datetime.now().isoformat(),
                "results": optimization_results,
                "success": True,
            }

        except Exception as e:
            logger.error(f"優化資料庫儲存失敗: {e}")
            return {"guild_id": guild_id, "success": False, "error": str(e)}

    async def _compress_archived_data(self, guild_id: int) -> Dict[str, Any]:
        """壓縮歷史歸檔資料"""
        try:
            # 這裡可以實現資料壓縮邏輯
            # 例如：移除重複資料、壓縮JSON格式、合併相似記錄等
            logger.info("執行資料壓縮...")

            # 模擬壓縮結果
            return {
                "compressed_archives": 0,  # 實際實現時需要真實數據
                "space_saved_mb": 0,
                "compression_ratio": 1.0,
            }
        except Exception as e:
            return {"error": str(e)}

    async def _optimize_database_indexes(
        self, guild_id: int
    ) -> Dict[str, Any]:
        """優化資料庫索引"""
        try:
            # 這裡可以分析並優化資料庫索引
            logger.info("分析資料庫索引使用情況...")

            # 模擬索引優化結果
            return {
                "indexes_analyzed": 0,
                "indexes_optimized": 0,
                "query_performance_improvement": 0,
            }
        except Exception as e:
            return {"error": str(e)}

    async def get_storage_statistics(self, guild_id: int) -> Dict[str, Any]:
        """獲取儲存統計資訊"""
        try:
            # 獲取歷史資料統計
            archive_stats = await self.dao.get_archive_statistics(guild_id)

            # 添加額外統計資訊
            stats = {
                **archive_stats,
                "storage_analysis": await self._analyze_storage_usage(
                    guild_id
                ),
                "recommendations": await self._generate_cleanup_recommendations(
                    guild_id
                ),
            }

            return stats

        except Exception as e:
            logger.error(f"獲取儲存統計失敗: {e}")
            return {}

    async def _analyze_storage_usage(self, guild_id: int) -> Dict[str, Any]:
        """分析儲存使用情況"""
        try:
            # 分析不同資料類型的儲存使用
            return {
                "active_data_size_mb": 0,  # 實際實現時需要查詢
                "archived_data_size_mb": 0,
                "log_data_size_mb": 0,
                "total_size_mb": 0,
                "growth_trend": "stable",  # stable, growing, declining
            }
        except Exception as e:
            return {"error": str(e)}

    async def _generate_cleanup_recommendations(
        self, guild_id: int
    ) -> List[str]:
        """生成清理建議"""
        try:
            recommendations = []

            # 基於資料分析生成建議
            archive_stats = await self.dao.get_archive_statistics(guild_id)

            if (
                archive_stats.get("ticket_archives", {}).get(
                    "total_archived_tickets", 0
                )
                > 1000
            ):
                recommendations.append("考慮設置更短的票券保留期間")

            if (
                archive_stats.get("vote_archives", {}).get(
                    "total_archived_votes", 0
                )
                > 500
            ):
                recommendations.append("建議定期清理舊投票資料")

            # 如果沒有特殊建議，提供通用建議
            if not recommendations:
                recommendations.append("資料量在正常範圍內，維持現有清理策略")

            return recommendations

        except Exception as e:
            logger.error(f"生成清理建議失敗: {e}")
            return ["無法生成建議，請檢查系統狀態"]

    @tasks.loop(hours=24)  # 每天執行一次
    async def cleanup_scheduler(self):
        """自動清理排程器"""
        try:
            logger.info("開始執行定期資料庫清理檢查...")

            if not self.bot:
                return

            # 獲取所有需要清理的伺服器
            for guild in self.bot.guilds:
                try:
                    # 檢查是否有需要執行的清理排程
                    schedules = await self.dao.get_cleanup_schedules(guild.id)

                    for schedule in schedules:
                        if (
                            schedule.get("next_run")
                            and datetime.now() >= schedule["next_run"]
                            and schedule.get("is_enabled", True)
                        ):

                            await self._execute_scheduled_cleanup(
                                guild.id, schedule
                            )

                except Exception as e:
                    logger.error(f"處理伺服器 {guild.id} 的清理排程失敗: {e}")
                    continue

        except Exception as e:
            logger.error(f"自動清理排程器錯誤: {e}")

    async def _execute_scheduled_cleanup(self, guild_id: int, schedule: Dict):
        """執行排程清理"""
        try:
            logger.info(
                f"執行排程清理: {schedule['id']} - {schedule['cleanup_type']}"
            )

            cleanup_config = {
                "ticket_retention_days": schedule.get("retention_days", 90),
                "vote_retention_days": schedule.get("retention_days", 90),
                "log_retention_days": schedule.get("retention_days", 30),
                "archive_before_delete": schedule.get(
                    "archive_before_delete", True
                ),
            }

            # 執行清理
            await self.perform_comprehensive_cleanup(guild_id, cleanup_config)

            # 更新排程的下次執行時間
            await self._update_schedule_next_run(
                schedule["id"], schedule["schedule_type"]
            )

            logger.info(f"排程清理完成: {schedule['id']}")

        except Exception as e:
            logger.error(f"執行排程清理失敗: {e}")

    async def _update_schedule_next_run(
        self, schedule_id: int, schedule_type: str
    ):
        """更新排程下次執行時間"""
        # 這裡需要在ArchiveDAO中實現相應的更新方法

    @cleanup_scheduler.before_loop
    async def before_cleanup_scheduler(self):
        if self.bot:
            await self.bot.wait_until_ready()

    async def get_cleanup_status(self, guild_id: int) -> Dict[str, Any]:
        """獲取清理狀態"""
        return {
            "guild_id": guild_id,
            "cleanup_in_progress": guild_id in self._cleanup_in_progress,
            "last_cleanup": "unknown",  # 可以從資料庫查詢
            "next_scheduled_cleanup": "unknown",  # 可以從排程表查詢
            "storage_stats": await self.get_storage_statistics(guild_id),
        }

    def stop_cleanup_scheduler(self):
        """停止清理排程器"""
        if hasattr(self, "cleanup_scheduler"):
            self.cleanup_scheduler.cancel()
