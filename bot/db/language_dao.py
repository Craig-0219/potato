# bot/db/language_dao.py - 語言偏好資料存取層
"""
語言偏好資料存取層
處理用戶和伺服器的語言設定存儲與查詢
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from bot.db.pool import db_pool
from shared.logger import logger


class LanguageDAO:
    """語言偏好資料存取層"""

    def __init__(self):
        self.db = db_pool
        self._initialized = False

    async def _ensure_initialized(self):
        """確保資料庫已初始化"""
        if not self._initialized:
            try:
                # 檢查語言相關表格是否存在
                async with self.db.connection() as conn:
                    async with conn.cursor() as cursor:
                        await cursor.execute(
                            """
                            SELECT COUNT(*) FROM information_schema.tables
                            WHERE table_schema = DATABASE() AND table_name = 'language_preferences'
                        """
                        )
                        exists = (await cursor.fetchone())[0] > 0

                if not exists:
                    logger.warning(
                        "📋 檢測到語言表格不存在，開始自動初始化..."
                    )
                    await self._create_language_tables()

                self._initialized = True
                logger.info("✅ 語言 DAO 初始化完成")

            except Exception as e:
                logger.error(f"❌ 語言 DAO 初始化失敗：{e}")
                raise

    async def _create_language_tables(self):
        """創建語言相關資料表"""
        try:
            async with self.db.connection() as conn:
                async with conn.cursor() as cursor:
                    # 語言偏好表
                    await cursor.execute(
                        """
                        CREATE TABLE IF NOT EXISTS language_preferences (
                            id INT PRIMARY KEY AUTO_INCREMENT,
                            entity_type ENUM('user', 'guild') NOT NULL,
                            entity_id BIGINT NOT NULL,
                            language_code VARCHAR(10) NOT NULL,
                            is_active BOOLEAN DEFAULT TRUE,
                            auto_detected BOOLEAN DEFAULT FALSE,
                            detection_confidence DECIMAL(3,2) DEFAULT NULL,
                            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                            UNIQUE KEY unique_entity (entity_type, entity_id),
                            INDEX idx_language_code (language_code),
                            INDEX idx_entity_active (entity_type, entity_id, is_active)
                        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
                    """
                    )

                    # 語言使用統計表
                    await cursor.execute(
                        """
                        CREATE TABLE IF NOT EXISTS language_usage_stats (
                            id INT PRIMARY KEY AUTO_INCREMENT,
                            guild_id BIGINT NOT NULL,
                            language_code VARCHAR(10) NOT NULL,
                            usage_date DATE NOT NULL,
                            message_count INT DEFAULT 0,
                            unique_users INT DEFAULT 0,
                            detection_accuracy DECIMAL(3,2) DEFAULT NULL,
                            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                            UNIQUE KEY unique_guild_lang_date (guild_id, language_code, usage_date),
                            INDEX idx_usage_date (usage_date),
                            INDEX idx_guild_date (guild_id, usage_date)
                        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
                    """
                    )

                    # 語言偵測記錄表
                    await cursor.execute(
                        """
                        CREATE TABLE IF NOT EXISTS language_detection_logs (
                            id INT PRIMARY KEY AUTO_INCREMENT,
                            guild_id BIGINT NOT NULL,
                            user_id BIGINT NOT NULL,
                            original_text TEXT NOT NULL,
                            detected_language VARCHAR(10) NOT NULL,
                            confidence_score DECIMAL(3,2) NOT NULL,
                            detection_method VARCHAR(50) NOT NULL,
                            is_correct BOOLEAN DEFAULT NULL,
                            feedback_provided_at TIMESTAMP NULL,
                            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                            INDEX idx_guild_user (guild_id, user_id),
                            INDEX idx_detected_lang (detected_language),
                            INDEX idx_confidence (confidence_score)
                        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
                    """
                    )

                    await conn.commit()
                    logger.info("✅ 語言資料表創建完成")

        except Exception as e:
            logger.error(f"創建語言資料表錯誤：{e}")
            raise

    # ========== 語言偏好管理 ==========

    async def set_user_language(
        self,
        user_id: int,
        guild_id: int,
        language_code: str,
        auto_detected: bool = False,
        confidence: float = None,
    ) -> bool:
        """設定用戶語言偏好"""
        await self._ensure_initialized()
        try:
            async with self.db.connection() as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute(
                        """
                        INSERT INTO language_preferences (
                            entity_type, entity_id, language_code, auto_detected, detection_confidence
                        ) VALUES ('user', %s, %s, %s, %s)
                        ON DUPLICATE KEY UPDATE
                            language_code = VALUES(language_code),
                            auto_detected = VALUES(auto_detected),
                            detection_confidence = VALUES(detection_confidence),
                            updated_at = CURRENT_TIMESTAMP
                    """,
                        (user_id, language_code, auto_detected, confidence),
                    )

                    await conn.commit()
                    return True
        except Exception:
            return False

    async def get_user_language(
        self, user_id: int, guild_id: int = None
    ) -> Optional[Dict[str, Any]]:
        """取得用戶語言偏好"""
        await self._ensure_initialized()
        try:
            async with self.db.connection() as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute(
                        """
                        SELECT language_code, auto_detected, detection_confidence, created_at, updated_at
                        FROM language_preferences
                        WHERE entity_type = 'user' AND entity_id = %s AND is_active = TRUE
                    """,
                        (user_id,),
                    )

                    row = await cursor.fetchone()
                    if row:
                        return {
                            "language_code": row[0],
                            "auto_detected": bool(row[1]),
                            "confidence": float(row[2]) if row[2] else None,
                            "created_at": row[3],
                            "updated_at": row[4],
                        }

                    return None

        except Exception as e:
            logger.error(f"取得用戶語言錯誤: {e}")
            return None

    async def set_guild_language(
        self, guild_id: int, language_code: str
    ) -> bool:
        """設定伺服器預設語言"""
        await self._ensure_initialized()
        try:
            async with self.db.connection() as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute(
                        """
                        INSERT INTO language_preferences (
                            entity_type, entity_id, language_code, auto_detected
                        ) VALUES ('guild', %s, %s, FALSE)
                        ON DUPLICATE KEY UPDATE
                            language_code = VALUES(language_code),
                            updated_at = CURRENT_TIMESTAMP
                    """,
                        (guild_id, language_code),
                    )

                    await conn.commit()
                    return True

        except Exception as e:
            logger.error(f"設定伺服器語言錯誤: {e}")
            return False

    async def get_guild_language(
        self, guild_id: int
    ) -> Optional[Dict[str, Any]]:
        """取得伺服器語言設定"""
        await self._ensure_initialized()
        try:
            async with self.db.connection() as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute(
                        """
                        SELECT language_code, created_at, updated_at
                        FROM language_preferences
                        WHERE entity_type = 'guild' AND entity_id = %s AND is_active = TRUE
                    """,
                        (guild_id,),
                    )

                    row = await cursor.fetchone()
                    if row:
                        return {
                            "language_code": row[0],
                            "created_at": row[1],
                            "updated_at": row[2],
                        }

                    return None

        except Exception as e:
            logger.error(f"取得伺服器語言錯誤: {e}")
            return None

    async def delete_user_language(self, user_id: int) -> bool:
        """刪除用戶語言設定"""
        await self._ensure_initialized()
        try:
            async with self.db.connection() as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute(
                        """
                        UPDATE language_preferences
                        SET is_active = FALSE, updated_at = CURRENT_TIMESTAMP
                        WHERE entity_type = 'user' AND entity_id = %s
                    """,
                        (user_id,),
                    )

                    await conn.commit()
                    return cursor.rowcount > 0

        except Exception as e:
            logger.error(f"刪除用戶語言設定錯誤: {e}")
            return False

    # ========== 語言使用統計 ==========

    async def update_language_usage(
        self,
        guild_id: int,
        language_code: str,
        user_count: int = 1,
        message_count: int = 1,
    ) -> bool:
        """更新語言使用統計"""
        await self._ensure_initialized()
        try:
            today = datetime.now(timezone.utc).date()

            async with self.db.connection() as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute(
                        """
                        INSERT INTO language_usage_stats (
                            guild_id, language_code, usage_date, message_count, unique_users
                        ) VALUES (%s, %s, %s, %s, %s)
                        ON DUPLICATE KEY UPDATE
                            message_count = message_count + VALUES(message_count),
                            unique_users = GREATEST(unique_users, VALUES(unique_users)),
                            updated_at = CURRENT_TIMESTAMP
                    """,
                        (
                            guild_id,
                            language_code,
                            today,
                            message_count,
                            user_count,
                        ),
                    )

                    await conn.commit()
                    return True

        except Exception as e:
            logger.error(f"更新語言使用統計錯誤: {e}")
            return False

    async def get_language_usage_stats(
        self, guild_id: int, days: int = 30
    ) -> List[Dict[str, Any]]:
        """取得語言使用統計"""
        await self._ensure_initialized()
        try:
            from datetime import timedelta

            end_date = datetime.now(timezone.utc).date()
            start_date = end_date - timedelta(days=days)

            async with self.db.connection() as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute(
                        """
                        SELECT
                            language_code,
                            SUM(message_count) as total_messages,
                            SUM(unique_users) as total_users,
                            AVG(detection_accuracy) as avg_accuracy,
                            COUNT(*) as days_active
                        FROM language_usage_stats
                        WHERE guild_id = %s AND usage_date BETWEEN %s AND %s
                        GROUP BY language_code
                        ORDER BY total_messages DESC
                    """,
                        (guild_id, start_date, end_date),
                    )

                    rows = await cursor.fetchall()

                    stats = []
                    for row in rows:
                        stats.append(
                            {
                                "language_code": row[0],
                                "total_messages": row[1],
                                "total_users": row[2],
                                "avg_accuracy": (
                                    float(row[3]) if row[3] else None
                                ),
                                "days_active": row[4],
                            }
                        )

                    return stats

        except Exception as e:
            logger.error(f"取得語言使用統計錯誤: {e}")
            return []

    # ========== 語言偵測記錄 ==========

    async def log_language_detection(
        self,
        guild_id: int,
        user_id: int,
        text: str,
        detected_language: str,
        confidence: float,
        method: str = "pattern_based",
    ) -> Optional[int]:
        """記錄語言偵測結果"""
        await self._ensure_initialized()
        try:
            async with self.db.connection() as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute(
                        """
                        INSERT INTO language_detection_logs (
                            guild_id, user_id, original_text, detected_language,
                            confidence_score, detection_method
                        ) VALUES (%s, %s, %s, %s, %s, %s)
                    """,
                        (
                            guild_id,
                            user_id,
                            text[:500],
                            detected_language,
                            confidence,
                            method,
                        ),
                    )

                    log_id = cursor.lastrowid
                    await conn.commit()
                    return log_id

        except Exception as e:
            logger.error(f"記錄語言偵測錯誤: {e}")
            return None

    async def update_detection_feedback(
        self, log_id: int, is_correct: bool
    ) -> bool:
        """更新偵測回饋"""
        await self._ensure_initialized()
        try:
            async with self.db.connection() as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute(
                        """
                        UPDATE language_detection_logs
                        SET is_correct = %s, feedback_provided_at = CURRENT_TIMESTAMP
                        WHERE id = %s
                    """,
                        (is_correct, log_id),
                    )

                    await conn.commit()
                    return cursor.rowcount > 0

        except Exception as e:
            logger.error(f"更新偵測回饋錯誤: {e}")
            return False

    async def get_detection_accuracy(
        self, guild_id: int = None, language_code: str = None, days: int = 30
    ) -> Dict[str, Any]:
        """取得偵測準確率統計"""
        await self._ensure_initialized()
        try:
            from datetime import timedelta

            cutoff_date = datetime.now(timezone.utc) - timedelta(days=days)

            async with self.db.connection() as conn:
                async with conn.cursor() as cursor:
                    conditions = [
                        "created_at >= %s",
                        "feedback_provided_at IS NOT NULL",
                    ]
                    params = [cutoff_date]

                    if guild_id:
                        conditions.append("guild_id = %s")
                        params.append(guild_id)

                    if language_code:
                        conditions.append("detected_language = %s")
                        params.append(language_code)

                    where_clause = " AND ".join(conditions)

                    await cursor.execute(
                        f"""
                        SELECT
                            detected_language,
                            COUNT(*) as total_detections,
                            SUM(CASE WHEN is_correct THEN 1 ELSE 0 END) as correct_detections,
                            AVG(confidence_score) as avg_confidence
                        FROM language_detection_logs
                        WHERE {where_clause}
                        GROUP BY detected_language
                        ORDER BY total_detections DESC
                    """,
                        params,
                    )

                    rows = await cursor.fetchall()

                    accuracy_stats = {}
                    total_detections = 0
                    total_correct = 0

                    for row in rows:
                        lang = row[0]
                        total = row[1]
                        correct = row[2]
                        avg_conf = float(row[3])

                        accuracy_stats[lang] = {
                            "total_detections": total,
                            "correct_detections": correct,
                            "accuracy_rate": (
                                correct / total if total > 0 else 0.0
                            ),
                            "avg_confidence": avg_conf,
                        }

                        total_detections += total
                        total_correct += correct

                    overall_accuracy = (
                        total_correct / total_detections
                        if total_detections > 0
                        else 0.0
                    )

                    return {
                        "overall_accuracy": overall_accuracy,
                        "total_detections": total_detections,
                        "total_correct": total_correct,
                        "by_language": accuracy_stats,
                        "period_days": days,
                    }

        except Exception as e:
            logger.error(f"取得偵測準確率統計錯誤: {e}")
            return {
                "overall_accuracy": 0.0,
                "total_detections": 0,
                "total_correct": 0,
                "by_language": {},
                "period_days": days,
            }

    # ========== 批次操作 ==========

    async def get_popular_languages(
        self, guild_id: int, limit: int = 10
    ) -> List[Dict[str, Any]]:
        """取得熱門語言列表"""
        await self._ensure_initialized()
        try:
            async with self.db.connection() as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute(
                        """
                        SELECT
                            lus.language_code,
                            SUM(lus.message_count) as total_messages,
                            COUNT(DISTINCT lus.usage_date) as active_days,
                            COUNT(lp.entity_id) as user_preferences
                        FROM language_usage_stats lus
                        LEFT JOIN language_preferences lp ON (
                            lp.language_code = lus.language_code
                            AND lp.entity_type = 'user'
                            AND lp.is_active = TRUE
                        )
                        WHERE lus.guild_id = %s
                        GROUP BY lus.language_code
                        ORDER BY total_messages DESC
                        LIMIT %s
                    """,
                        (guild_id, limit),
                    )

                    rows = await cursor.fetchall()

                    popular_languages = []
                    for row in rows:
                        popular_languages.append(
                            {
                                "language_code": row[0],
                                "total_messages": row[1],
                                "active_days": row[2],
                                "user_preferences": row[3],
                            }
                        )

                    return popular_languages

        except Exception as e:
            logger.error(f"取得熱門語言列表錯誤: {e}")
            return []

    async def cleanup_old_detection_logs(self, days: int = 90) -> int:
        """清理舊的偵測記錄"""
        await self._ensure_initialized()
        try:
            from datetime import timedelta

            cutoff_date = datetime.now(timezone.utc) - timedelta(days=days)

            async with self.db.connection() as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute(
                        """
                        DELETE FROM language_detection_logs
                        WHERE created_at < %s
                    """,
                        (cutoff_date,),
                    )

                    deleted_count = cursor.rowcount
                    await conn.commit()

                    logger.info(f"清理了 {deleted_count} 條舊語言偵測記錄")
                    return deleted_count

        except Exception as e:
            logger.error(f"清理語言偵測記錄錯誤: {e}")
            return 0
