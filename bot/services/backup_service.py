# bot/services/backup_service.py - v1.0.0
# 📦 自動備份服務
# Automated Backup Service

import asyncio
import gzip
import json
import logging
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from bot.db.pool import db_pool
from bot.services.data_management_service import data_management_service
from bot.utils.multi_tenant_security import secure_query_builder

logger = logging.getLogger(__name__)


class BackupService:
    """自動備份服務"""

    def __init__(self):
        self.db = db_pool
        self.query_builder = secure_query_builder
        self.data_service = data_management_service
        self.backup_path = Path("backups")
        self.backup_path.mkdir(exist_ok=True)

        # 備份設定
        self.backup_config = {
            "daily_backups_retain": 7,  # 保留 7 天的每日備份
            "weekly_backups_retain": 4,  # 保留 4 週的週備份
            "monthly_backups_retain": 12,  # 保留 12 個月的月備份
            "compression_enabled": True,
            "include_logs": False,  # 預設不包含日誌以節省空間
        }

    async def start_backup_scheduler(self):
        """啟動備份排程器"""
        logger.info("📦 啟動自動備份服務")

        async def backup_scheduler():
            while True:
                try:
                    now = datetime.now(timezone.utc)

                    # 每日備份 (每天凌晨 2:00 UTC)
                    if now.hour == 2 and now.minute < 5:
                        await self.perform_daily_backup()

                        # 週日執行週備份
                        if now.weekday() == 6:  # 0=週一, 6=週日
                            await self.perform_weekly_backup()

                        # 每月1日執行月備份
                        if now.day == 1:
                            await self.perform_monthly_backup()

                    # 清理過期備份 (每天執行)
                    if now.hour == 3 and now.minute < 5:
                        await self.cleanup_old_backups()

                    # 每5分鐘檢查一次
                    await asyncio.sleep(300)

                except Exception as e:
                    logger.error(f"❌ 備份排程器錯誤: {e}")
                    await asyncio.sleep(60)  # 錯誤時等待1分鐘

        # 在背景執行
        asyncio.create_task(backup_scheduler())

    async def perform_daily_backup(self):
        """執行每日備份"""
        try:
            logger.info("🗓️ 開始每日備份")

            backup_time = datetime.now(timezone.utc)
            backup_name = f"daily_backup_{backup_time.strftime('%Y%m%d_%H%M%S')}"

            # 獲取所有活躍伺服器
            guild_ids = await self._get_active_guilds()

            # 執行備份
            backup_result = await self._backup_guild_data(guild_ids, backup_name, "daily")

            # 記錄備份結果
            await self._log_backup_event(backup_name, "daily", backup_result)

            logger.info(f"✅ 每日備份完成: {backup_name}")

        except Exception as e:
            logger.error(f"❌ 每日備份失敗: {e}")

    async def perform_weekly_backup(self):
        """執行週備份"""
        try:
            logger.info("📅 開始週備份")

            backup_time = datetime.now(timezone.utc)
            backup_name = f"weekly_backup_{backup_time.strftime('%Y_W%U')}"

            guild_ids = await self._get_active_guilds()
            backup_result = await self._backup_guild_data(guild_ids, backup_name, "weekly")

            await self._log_backup_event(backup_name, "weekly", backup_result)

            logger.info(f"✅ 週備份完成: {backup_name}")

        except Exception as e:
            logger.error(f"❌ 週備份失敗: {e}")

    async def perform_monthly_backup(self):
        """執行月備份"""
        try:
            logger.info("📆 開始月備份")

            backup_time = datetime.now(timezone.utc)
            backup_name = f"monthly_backup_{backup_time.strftime('%Y_%m')}"

            guild_ids = await self._get_active_guilds()
            backup_result = await self._backup_guild_data(guild_ids, backup_name, "monthly")

            await self._log_backup_event(backup_name, "monthly", backup_result)

            logger.info(f"✅ 月備份完成: {backup_name}")

        except Exception as e:
            logger.error(f"❌ 月備份失敗: {e}")

    async def _get_active_guilds(self) -> List[int]:
        """獲取活躍伺服器列表"""
        try:
            async with self.db.connection() as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute(
                        """
                        SELECT guild_id FROM guild_info
                        WHERE status = 'active'
                    """
                    )
                    results = await cursor.fetchall()
                    return [row[0] for row in results]

        except Exception as e:
            logger.error(f"❌ 獲取活躍伺服器失敗: {e}")
            return []

    async def _backup_guild_data(
        self, guild_ids: List[int], backup_name: str, backup_type: str
    ) -> Dict[str, Any]:
        """備份伺服器數據"""
        try:
            backup_data = {
                "backup_info": {
                    "name": backup_name,
                    "type": backup_type,
                    "created_at": datetime.now(timezone.utc).isoformat(),
                    "guild_count": len(guild_ids),
                    "version": "3.0.1",
                },
                "guilds": {},
            }

            total_records = 0
            successful_guilds = 0

            # 備份每個伺服器的數據
            for guild_id in guild_ids:
                try:
                    guild_backup = await self._backup_single_guild(guild_id)
                    if guild_backup:
                        backup_data["guilds"][str(guild_id)] = guild_backup
                        total_records += guild_backup.get("record_count", 0)
                        successful_guilds += 1

                except Exception as e:
                    logger.error(f"❌ 備份伺服器 {guild_id} 失敗: {e}")
                    continue

            # 儲存備份檔案
            backup_file = self.backup_path / f"{backup_name}.json"

            if self.backup_config["compression_enabled"]:
                backup_file = backup_file.with_suffix(".json.gz")
                with gzip.open(backup_file, "wt", encoding="utf-8") as f:
                    json.dump(backup_data, f, indent=2, ensure_ascii=False, default=str)
            else:
                with open(backup_file, "w", encoding="utf-8") as f:
                    json.dump(backup_data, f, indent=2, ensure_ascii=False, default=str)

            # 計算檔案大小
            file_size_mb = backup_file.stat().st_size / 1024 / 1024

            backup_result = {
                "backup_name": backup_name,
                "backup_type": backup_type,
                "file_path": str(backup_file),
                "file_size_mb": round(file_size_mb, 2),
                "total_guilds": len(guild_ids),
                "successful_guilds": successful_guilds,
                "total_records": total_records,
                "compressed": self.backup_config["compression_enabled"],
            }

            logger.info(f"📦 備份檔案已建立: {backup_file} ({file_size_mb:.1f}MB)")
            return backup_result

        except Exception as e:
            logger.error(f"❌ 備份伺服器數據失敗: {e}")
            return {}

    async def _backup_single_guild(self, guild_id: int) -> Optional[Dict[str, Any]]:
        """備份單一伺服器數據"""
        try:
            guild_data = {
                "guild_id": guild_id,
                "backup_time": datetime.now(timezone.utc).isoformat(),
                "tables": {},
                "record_count": 0,
            }

            # 要備份的表格列表 (不包含敏感數據)
            backup_tables = [
                "guild_info",
                "guild_settings",
                "guild_quotas",
                "guild_statistics",
                "tickets",
                "ticket_settings",
                "votes",
                "vote_settings",
                "workflows",
                "welcome_settings",
            ]

            async with self.db.connection() as conn:
                async with conn.cursor() as cursor:
                    for table in backup_tables:
                        try:
                            # 檢查表格是否存在
                            await cursor.execute(f"SHOW TABLES LIKE '{table}'")
                            if not await cursor.fetchone():
                                continue

                            # 檢查是否有 guild_id 欄位
                            await cursor.execute(f"SHOW COLUMNS FROM {table} LIKE 'guild_id'")
                            has_guild_id = await cursor.fetchone() is not None

                            if has_guild_id:
                                # 有 guild_id 的表格，使用安全查詢
                                query, params = self.query_builder.build_select(
                                    table=table, guild_id=guild_id
                                )
                                await cursor.execute(query, params)
                            else:
                                # 沒有 guild_id 的表格，跳過或使用其他條件
                                continue

                            results = await cursor.fetchall()
                            if results:
                                # 轉換為字典格式
                                columns = [desc[0] for desc in cursor.description]
                                table_data = [dict(zip(columns, row)) for row in results]

                                guild_data["tables"][table] = table_data
                                guild_data["record_count"] += len(table_data)

                        except Exception as e:
                            logger.warning(f"⚠️ 備份表格 {table} 跳過: {e}")
                            continue

            return guild_data if guild_data["record_count"] > 0 else None

        except Exception as e:
            logger.error(f"❌ 備份伺服器 {guild_id} 失敗: {e}")
            return None

    async def cleanup_old_backups(self):
        """清理過期備份"""
        try:
            logger.info("🧹 開始清理過期備份")

            current_time = datetime.now(timezone.utc)
            cleaned_files = 0

            for backup_file in self.backup_path.glob("*.json*"):
                try:
                    # 解析檔案名稱確定備份類型和時間
                    file_age = current_time - datetime.fromtimestamp(
                        backup_file.stat().st_mtime, tz=timezone.utc
                    )

                    should_delete = False

                    if "daily_backup" in backup_file.name:
                        if file_age.days > self.backup_config["daily_backups_retain"]:
                            should_delete = True
                    elif "weekly_backup" in backup_file.name:
                        if file_age.days > (self.backup_config["weekly_backups_retain"] * 7):
                            should_delete = True
                    elif "monthly_backup" in backup_file.name:
                        if file_age.days > (self.backup_config["monthly_backups_retain"] * 30):
                            should_delete = True

                    if should_delete:
                        backup_file.unlink()
                        cleaned_files += 1
                        logger.info(f"🗑️ 已刪除過期備份: {backup_file.name}")

                except Exception as e:
                    logger.warning(f"⚠️ 清理備份檔案 {backup_file.name} 失敗: {e}")
                    continue

            if cleaned_files > 0:
                logger.info(f"✅ 清理完成，共刪除 {cleaned_files} 個過期備份檔案")
            else:
                logger.info("✅ 沒有需要清理的過期備份")

        except Exception as e:
            logger.error(f"❌ 清理過期備份失敗: {e}")

    async def _log_backup_event(
        self, backup_name: str, backup_type: str, backup_result: Dict[str, Any]
    ):
        """記錄備份事件"""
        try:
            event_data = {
                "guild_id": None,  # 系統事件
                "user_id": None,
                "event_type": "backup_completed",
                "event_category": "system",
                "event_name": f"{backup_type.title()} Backup",
                "description": f"自動備份完成: {backup_name}",
                "metadata": json.dumps(backup_result),
                "source": "backup_service",
                "status": "success" if backup_result else "failed",
            }

            columns = ", ".join(event_data.keys())
            placeholders = ", ".join(["%s"] * len(event_data))

            async with self.db.connection() as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute(
                        f"""
                        INSERT INTO guild_event_logs ({columns})
                        VALUES ({placeholders})
                    """,
                        list(event_data.values()),
                    )
                    await conn.commit()

        except Exception as e:
            logger.warning(f"⚠️ 記錄備份事件失敗: {e}")

    async def restore_from_backup(
        self, backup_file_path: str, guild_id: Optional[int] = None
    ) -> bool:
        """從備份還原數據 (手動操作用)"""
        try:
            logger.info(f"📂 開始從備份還原: {backup_file_path}")

            # 讀取備份檔案
            backup_path = Path(backup_file_path)
            if not backup_path.exists():
                logger.error(f"❌ 備份檔案不存在: {backup_file_path}")
                return False

            # 根據副檔名決定如何讀取
            if backup_path.suffix == ".gz":
                with gzip.open(backup_path, "rt", encoding="utf-8") as f:
                    backup_data = json.load(f)
            else:
                with open(backup_path, "r", encoding="utf-8") as f:
                    backup_data = json.load(f)

            # 還原指定伺服器或所有伺服器
            guilds_to_restore = [str(guild_id)] if guild_id else backup_data["guilds"].keys()

            for guild_id_str in guilds_to_restore:
                if guild_id_str in backup_data["guilds"]:
                    await self._restore_single_guild(
                        int(guild_id_str), backup_data["guilds"][guild_id_str]
                    )

            logger.info("✅ 備份還原完成")
            return True

        except Exception as e:
            logger.error(f"❌ 備份還原失敗: {e}")
            return False

    async def _restore_single_guild(self, guild_id: int, guild_data: Dict[str, Any]):
        """還原單一伺服器數據 (謹慎使用)"""
        try:
            logger.info(f"📋 還原伺服器 {guild_id} 的數據")

            async with self.db.connection() as conn:
                async with conn.cursor() as cursor:
                    for table_name, records in guild_data["tables"].items():
                        if not records:
                            continue

                        try:
                            # 清空現有數據 (危險操作！)
                            await cursor.execute(
                                f"""
                                DELETE FROM {table_name} WHERE guild_id = %s
                            """,
                                (guild_id,),
                            )

                            # 插入備份數據
                            for record in records:
                                columns = ", ".join(record.keys())
                                placeholders = ", ".join(["%s"] * len(record))

                                await cursor.execute(
                                    f"""
                                    INSERT INTO {table_name} ({columns})
                                    VALUES ({placeholders})
                                """,
                                    list(record.values()),
                                )

                            logger.info(f"✅ 還原表格 {table_name}: {len(records)} 筆記錄")

                        except Exception as e:
                            logger.error(f"❌ 還原表格 {table_name} 失敗: {e}")
                            continue

                    await conn.commit()

            logger.info(f"✅ 伺服器 {guild_id} 數據還原完成")

        except Exception as e:
            logger.error(f"❌ 還原伺服器 {guild_id} 失敗: {e}")


# 全域實例
backup_service = BackupService()
