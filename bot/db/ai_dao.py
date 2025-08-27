# bot/db/ai_dao.py - AI 系統資料存取層
"""
AI 系統資料存取層
處理 AI 建議、使用記錄、學習數據的資料庫操作
"""

from bot.db.pool import db_pool
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Any, Tuple
import json
from shared.logger import logger

class AIDAO:
    """AI 系統資料存取層"""
    
    def __init__(self):
        self.db = db_pool
        self._initialized = False

    async def _ensure_initialized(self):
        """確保資料庫已初始化"""
        if not self._initialized:
            try:
                # 檢查 AI 相關表格是否存在
                async with self.db.connection() as conn:
                    async with conn.cursor() as cursor:
                        await cursor.execute("""
                            SELECT COUNT(*) FROM information_schema.tables 
                            WHERE table_schema = DATABASE() AND table_name = 'ai_suggestions'
                        """)
                        exists = (await cursor.fetchone())[0] > 0
                
                if not exists:
                    logger.warning("📋 檢測到 AI 表格不存在，開始自動初始化...")
                    await self._create_ai_tables()
                
                self._initialized = True
                logger.info("✅ AI DAO 初始化完成")
                
            except Exception as e:
                logger.error(f"❌ AI DAO 初始化失敗：{e}")
                raise

    async def _create_ai_tables(self):
        """創建 AI 相關資料表"""
        try:
            async with self.db.connection() as conn:
                async with conn.cursor() as cursor:
                    # AI 建議記錄表
                    await cursor.execute("""
                        CREATE TABLE IF NOT EXISTS ai_suggestions (
                            id INT PRIMARY KEY AUTO_INCREMENT,
                            guild_id BIGINT NOT NULL,
                            ticket_id INT,
                            user_id BIGINT NOT NULL,
                            suggestion_type ENUM('reply', 'tag', 'priority') NOT NULL,
                            original_content TEXT NOT NULL,
                            suggested_content TEXT NOT NULL,
                            confidence_score DECIMAL(3,2) NOT NULL,
                            analysis_data JSON,
                            is_accepted BOOLEAN DEFAULT FALSE,
                            feedback_rating INT DEFAULT NULL,
                            feedback_comment TEXT DEFAULT NULL,
                            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                            accepted_at TIMESTAMP NULL,
                            INDEX idx_guild_ticket (guild_id, ticket_id),
                            INDEX idx_type_date (suggestion_type, created_at),
                            INDEX idx_confidence (confidence_score)
                        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
                    """)
                    
                    # AI 學習記錄表
                    await cursor.execute("""
                        CREATE TABLE IF NOT EXISTS ai_learning_data (
                            id INT PRIMARY KEY AUTO_INCREMENT,
                            guild_id BIGINT NOT NULL,
                            category VARCHAR(50) NOT NULL,
                            input_data TEXT NOT NULL,
                            expected_output TEXT NOT NULL,
                            actual_output TEXT,
                            success_rate DECIMAL(3,2),
                            learning_context JSON,
                            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                            INDEX idx_guild_category (guild_id, category),
                            INDEX idx_success_rate (success_rate)
                        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
                    """)
                    
                    # AI 統計摘要表
                    await cursor.execute("""
                        CREATE TABLE IF NOT EXISTS ai_statistics (
                            id INT PRIMARY KEY AUTO_INCREMENT,
                            guild_id BIGINT NOT NULL,
                            stat_date DATE NOT NULL,
                            suggestions_count INT DEFAULT 0,
                            accepted_count INT DEFAULT 0,
                            avg_confidence DECIMAL(3,2) DEFAULT 0.00,
                            category_breakdown JSON,
                            performance_metrics JSON,
                            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                            UNIQUE KEY unique_guild_date (guild_id, stat_date),
                            INDEX idx_stat_date (stat_date)
                        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
                    """)
                    
                    await conn.commit()
                    logger.info("✅ AI 資料表創建完成")
                    
        except Exception as e:
            logger.error(f"創建 AI 資料表錯誤：{e}")
            raise

    # ========== AI 建議記錄 ==========

    async def save_suggestion(self, 
                            guild_id: int,
                            user_id: int, 
                            suggestion_type: str,
                            original_content: str,
                            suggested_content: str,
                            confidence_score: float,
                            analysis_data: Dict[str, Any] = None,
                            ticket_id: int = None) -> Optional[int]:
        """儲存 AI 建議記錄"""
        await self._ensure_initialized()
        try:
            async with self.db.connection() as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute("""
                        INSERT INTO ai_suggestions (
                            guild_id, ticket_id, user_id, suggestion_type,
                            original_content, suggested_content, confidence_score,
                            analysis_data
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    """, (
                        guild_id, ticket_id, user_id, suggestion_type,
                        original_content, suggested_content, confidence_score,
                        json.dumps(analysis_data) if analysis_data else None
                    ))
                    
                    suggestion_id = cursor.lastrowid
                    await conn.commit()
                    return suggestion_id
        except Exception as e:
            logger.error(f"儲存 AI 建議記錄失敗: {e}")
            return None

    async def update_suggestion_feedback(self,
                                       suggestion_id: int,
                                       is_accepted: bool,
                                       feedback_rating: int = None,
                                       feedback_comment: str = None) -> bool:
        """更新建議的回饋記錄"""
        await self._ensure_initialized()
        try:
            async with self.db.connection() as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute("""
                        UPDATE ai_suggestions 
                        SET is_accepted = %s, 
                            feedback_rating = %s,
                            feedback_comment = %s,
                            accepted_at = %s
                        WHERE id = %s
                    """, (
                        is_accepted, feedback_rating, feedback_comment,
                        datetime.now(timezone.utc) if is_accepted else None,
                        suggestion_id
                    ))
                    
                    await conn.commit()
                    return cursor.rowcount > 0
                    
        except Exception as e:
            logger.error(f"更新建議回饋錯誤: {e}")
            return False

    async def get_suggestion_history(self, 
                                   guild_id: int,
                                   suggestion_type: str = None,
                                   limit: int = 50) -> List[Dict[str, Any]]:
        """取得建議歷史記錄"""
        await self._ensure_initialized()
        try:
            async with self.db.connection() as conn:
                async with conn.cursor() as cursor:
                    
                    conditions = ["guild_id = %s"]
                    params = [guild_id]
                    
                    if suggestion_type:
                        conditions.append("suggestion_type = %s")
                        params.append(suggestion_type)
                    
                    where_clause = " AND ".join(conditions)
                    params.append(limit)
                    
                    await cursor.execute(f"""
                        SELECT 
                            id, ticket_id, user_id, suggestion_type,
                            original_content, suggested_content, confidence_score,
                            analysis_data, is_accepted, feedback_rating,
                            feedback_comment, created_at, accepted_at
                        FROM ai_suggestions 
                        WHERE {where_clause}
                        ORDER BY created_at DESC
                        LIMIT %s
                    """, params)
                    
                    rows = await cursor.fetchall()
                    
                    suggestions = []
                    for row in rows:
                        suggestion = {
                            'id': row[0],
                            'ticket_id': row[1],
                            'user_id': row[2],
                            'suggestion_type': row[3],
                            'original_content': row[4],
                            'suggested_content': row[5],
                            'confidence_score': float(row[6]),
                            'analysis_data': json.loads(row[7]) if row[7] else {},
                            'is_accepted': bool(row[8]),
                            'feedback_rating': row[9],
                            'feedback_comment': row[10],
                            'created_at': row[11],
                            'accepted_at': row[12]
                        }
                        suggestions.append(suggestion)
                    
                    return suggestions
                    
        except Exception as e:
            logger.error(f"取得建議歷史錯誤: {e}")
            return []

    # ========== AI 學習數據 ==========

    async def save_learning_data(self,
                               guild_id: int,
                               category: str,
                               input_data: str,
                               expected_output: str,
                               actual_output: str = None,
                               success_rate: float = None,
                               learning_context: Dict[str, Any] = None) -> bool:
        """儲存學習數據"""
        await self._ensure_initialized()
        try:
            async with self.db.connection() as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute("""
                        INSERT INTO ai_learning_data (
                            guild_id, category, input_data, expected_output,
                            actual_output, success_rate, learning_context
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s)
                    """, (
                        guild_id, category, input_data, expected_output,
                        actual_output, success_rate,
                        json.dumps(learning_context) if learning_context else None
                    ))
                    
                    await conn.commit()
                    return True
                    
        except Exception as e:
            logger.error(f"儲存學習數據錯誤: {e}")
            return False

    async def get_learning_data(self, 
                              guild_id: int,
                              category: str = None,
                              limit: int = 100) -> List[Dict[str, Any]]:
        """取得學習數據"""
        await self._ensure_initialized()
        try:
            async with self.db.connection() as conn:
                async with conn.cursor() as cursor:
                    
                    conditions = ["guild_id = %s"]
                    params = [guild_id]
                    
                    if category:
                        conditions.append("category = %s")
                        params.append(category)
                    
                    where_clause = " AND ".join(conditions)
                    params.append(limit)
                    
                    await cursor.execute(f"""
                        SELECT 
                            id, category, input_data, expected_output,
                            actual_output, success_rate, learning_context,
                            created_at, updated_at
                        FROM ai_learning_data 
                        WHERE {where_clause}
                        ORDER BY created_at DESC
                        LIMIT %s
                    """, params)
                    
                    rows = await cursor.fetchall()
                    
                    learning_data = []
                    for row in rows:
                        data = {
                            'id': row[0],
                            'category': row[1],
                            'input_data': row[2],
                            'expected_output': row[3],
                            'actual_output': row[4],
                            'success_rate': float(row[5]) if row[5] else None,
                            'learning_context': json.loads(row[6]) if row[6] else {},
                            'created_at': row[7],
                            'updated_at': row[8]
                        }
                        learning_data.append(data)
                    
                    return learning_data
                    
        except Exception as e:
            logger.error(f"取得學習數據錯誤: {e}")
            return []

    # ========== AI 統計 ==========

    async def update_daily_statistics(self, guild_id: int, stat_date: str = None) -> bool:
        """更新每日統計"""
        await self._ensure_initialized()
        try:
            if not stat_date:
                stat_date = datetime.now(timezone.utc).date()
            
            async with self.db.connection() as conn:
                async with conn.cursor() as cursor:
                    # 計算當日統計
                    await cursor.execute("""
                        SELECT 
                            COUNT(*) as total_suggestions,
                            SUM(CASE WHEN is_accepted THEN 1 ELSE 0 END) as accepted_count,
                            AVG(confidence_score) as avg_confidence,
                            suggestion_type,
                            COUNT(*) as type_count
                        FROM ai_suggestions 
                        WHERE guild_id = %s 
                          AND DATE(created_at) = %s
                        GROUP BY suggestion_type
                    """, (guild_id, stat_date))
                    
                    results = await cursor.fetchall()
                    
                    if not results:
                        return True  # 沒有數據也算成功
                    
                    # 計算總統計
                    total_suggestions = sum(row[0] for row in results)
                    total_accepted = sum(row[1] for row in results)
                    avg_confidence = sum(row[2] * row[0] for row in results if row[2]) / total_suggestions if total_suggestions > 0 else 0.0
                    
                    # 建立分類分解數據
                    category_breakdown = {}
                    for row in results:
                        suggestion_type = row[3]
                        category_breakdown[suggestion_type] = {
                            'total': row[0],
                            'accepted': row[1],
                            'avg_confidence': float(row[2]) if row[2] else 0.0
                        }
                    
                    # 計算性能指標
                    performance_metrics = {
                        'acceptance_rate': total_accepted / total_suggestions if total_suggestions > 0 else 0.0,
                        'avg_confidence': float(avg_confidence),
                        'total_suggestions': total_suggestions,
                        'total_accepted': total_accepted
                    }
                    
                    # 插入或更新統計記錄
                    await cursor.execute("""
                        INSERT INTO ai_statistics (
                            guild_id, stat_date, suggestions_count, accepted_count,
                            avg_confidence, category_breakdown, performance_metrics
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s)
                        ON DUPLICATE KEY UPDATE
                            suggestions_count = VALUES(suggestions_count),
                            accepted_count = VALUES(accepted_count),
                            avg_confidence = VALUES(avg_confidence),
                            category_breakdown = VALUES(category_breakdown),
                            performance_metrics = VALUES(performance_metrics),
                            updated_at = CURRENT_TIMESTAMP
                    """, (
                        guild_id, stat_date, total_suggestions, total_accepted,
                        avg_confidence, json.dumps(category_breakdown),
                        json.dumps(performance_metrics)
                    ))
                    
                    await conn.commit()
                    return True
                    
        except Exception as e:
            logger.error(f"更新每日統計錯誤: {e}")
            return False

    async def get_statistics(self, 
                           guild_id: int, 
                           days: int = 30) -> Dict[str, Any]:
        """取得 AI 統計數據"""
        await self._ensure_initialized()
        try:
            end_date = datetime.now(timezone.utc).date()
            start_date = end_date - timedelta(days=days)
            
            async with self.db.connection() as conn:
                async with conn.cursor() as cursor:
                    # 取得期間內的統計數據
                    await cursor.execute("""
                        SELECT 
                            stat_date,
                            suggestions_count,
                            accepted_count,
                            avg_confidence,
                            category_breakdown,
                            performance_metrics
                        FROM ai_statistics
                        WHERE guild_id = %s 
                          AND stat_date BETWEEN %s AND %s
                        ORDER BY stat_date DESC
                    """, (guild_id, start_date, end_date))
                    
                    rows = await cursor.fetchall()
                    
                    if not rows:
                        return self._get_default_statistics()
                    
                    # 計算累積統計
                    total_suggestions = sum(row[1] for row in rows)
                    total_accepted = sum(row[2] for row in rows)
                    
                    # 計算平均置信度（加權平均）
                    weighted_confidence = sum(row[3] * row[1] for row in rows if row[3] and row[1]) 
                    avg_confidence = weighted_confidence / total_suggestions if total_suggestions > 0 else 0.0
                    
                    # 合併分類統計
                    combined_categories = {}
                    for row in rows:
                        if row[4]:  # category_breakdown
                            categories = json.loads(row[4])
                            for category, stats in categories.items():
                                if category not in combined_categories:
                                    combined_categories[category] = {'total': 0, 'accepted': 0}
                                combined_categories[category]['total'] += stats['total']
                                combined_categories[category]['accepted'] += stats['accepted']
                    
                    # 生成最終統計
                    statistics = {
                        'period_days': days,
                        'total_suggestions': total_suggestions,
                        'total_accepted': total_accepted,
                        'acceptance_rate': total_accepted / total_suggestions if total_suggestions > 0 else 0.0,
                        'avg_confidence': round(avg_confidence, 3),
                        'daily_average': round(total_suggestions / days, 1),
                        'category_breakdown': combined_categories,
                        'trend_data': [
                            {
                                'date': str(row[0]),
                                'suggestions': row[1],
                                'accepted': row[2],
                                'confidence': float(row[3]) if row[3] else 0.0
                            }
                            for row in rows
                        ]
                    }
                    
                    return statistics
                    
        except Exception as e:
            logger.error(f"取得 AI 統計錯誤: {e}")
            return self._get_default_statistics()

    def _get_default_statistics(self) -> Dict[str, Any]:
        """取得預設統計數據"""
        return {
            'period_days': 30,
            'total_suggestions': 0,
            'total_accepted': 0,
            'acceptance_rate': 0.0,
            'avg_confidence': 0.0,
            'daily_average': 0.0,
            'category_breakdown': {},
            'trend_data': []
        }

    # ========== 清理和維護 ==========

    async def cleanup_old_data(self, days: int = 90) -> int:
        """清理舊資料"""
        await self._ensure_initialized()
        try:
            cutoff_date = datetime.now(timezone.utc) - timedelta(days=days)
            cleaned_count = 0
            
            async with self.db.connection() as conn:
                async with conn.cursor() as cursor:
                    # 清理舊的建議記錄
                    await cursor.execute("""
                        DELETE FROM ai_suggestions 
                        WHERE created_at < %s
                    """, (cutoff_date,))
                    
                    cleaned_count += cursor.rowcount
                    
                    # 清理舊的學習數據
                    await cursor.execute("""
                        DELETE FROM ai_learning_data 
                        WHERE created_at < %s
                    """, (cutoff_date,))
                    
                    cleaned_count += cursor.rowcount
                    
                    await conn.commit()
                    logger.info(f"清理了 {cleaned_count} 條舊 AI 資料")
                    
                    return cleaned_count
                    
        except Exception as e:
            logger.error(f"清理 AI 資料錯誤: {e}")
            return 0