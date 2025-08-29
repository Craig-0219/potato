# shared/db_optimizer.py - 資料庫查詢優化管理器
"""
資料庫查詢優化管理器 v2.2.0
功能特點：
1. 查詢執行計劃分析
2. 自動索引建議和管理
3. 慢查詢檢測和優化
4. 資料庫性能監控
5. 查詢快取管理
6. 資料庫統計更新
"""

import hashlib
import json
import re
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Tuple

from bot.db.pool import db_pool
from shared.logger import logger


class QueryType(Enum):
    """查詢類型"""

    SELECT = "SELECT"
    INSERT = "INSERT"
    UPDATE = "UPDATE"
    DELETE = "DELETE"
    CREATE = "CREATE"
    ALTER = "ALTER"


class OptimizationLevel(Enum):
    """優化等級"""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class QueryAnalysis:
    """查詢分析結果"""

    query_hash: str
    original_query: str
    query_type: QueryType
    execution_time: float
    rows_examined: int
    rows_sent: int
    tables_used: List[str]
    indexes_used: List[str]
    optimization_level: OptimizationLevel
    suggestions: List[str]
    explain_plan: Dict[str, Any]
    timestamp: datetime


@dataclass
class IndexRecommendation:
    """索引建議"""

    table_name: str
    columns: List[str]
    index_type: str  # BTREE, HASH, FULLTEXT
    reason: str
    estimated_benefit: float
    create_sql: str


@dataclass
class DatabaseMetrics:
    """資料庫性能指標"""

    query_cache_hit_rate: float
    slow_query_count: int
    connections_used: int
    max_connections: int
    innodb_buffer_pool_hit_rate: float
    table_scan_rate: float
    temp_table_rate: float
    key_read_hit_rate: float
    timestamp: datetime


class DatabaseOptimizer:
    """資料庫優化管理器"""

    def __init__(self):
        self.slow_query_threshold = 1.0  # 1秒為慢查詢閾值
        self.query_cache = {}
        self.optimization_history = []
        self.metrics_cache = None
        self.metrics_cache_time = None

        # 索引優化配置
        self.index_recommendations = []
        self.auto_create_indexes = False  # 預設不自動創建索引

        logger.info("🔧 資料庫優化管理器初始化完成")

    async def initialize(self):
        """初始化優化器"""
        try:
            # 檢查並建立優化相關的表格
            await self._create_optimization_tables()

            # 載入現有的優化記錄
            await self._load_optimization_history()

            # 分析現有表結構
            await self._analyze_existing_tables()

            logger.info("✅ 資料庫優化器初始化完成")

        except Exception as e:
            logger.error(f"❌ 資料庫優化器初始化失敗: {e}")
            raise

    async def _create_optimization_tables(self):
        """建立優化相關的表格"""
        try:
            async with db_pool.connection() as conn:
                async with conn.cursor() as cursor:
                    # 查詢分析記錄表
                    await cursor.execute(
                        """
                        CREATE TABLE IF NOT EXISTS query_analysis_log (
                            id INT AUTO_INCREMENT PRIMARY KEY,
                            query_hash VARCHAR(64) NOT NULL,
                            query_text TEXT NOT NULL,
                            query_type VARCHAR(20) NOT NULL,
                            execution_time DECIMAL(10,4) NOT NULL,
                            rows_examined INT NOT NULL DEFAULT 0,
                            rows_sent INT NOT NULL DEFAULT 0,
                            tables_used JSON,
                            indexes_used JSON,
                            optimization_level VARCHAR(20) NOT NULL,
                            suggestions JSON,
                            explain_plan JSON,
                            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                            INDEX idx_query_hash (query_hash),
                            INDEX idx_execution_time (execution_time),
                            INDEX idx_created_at (created_at)
                        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
                    """
                    )

                    # 索引建議記錄表
                    await cursor.execute(
                        """
                        CREATE TABLE IF NOT EXISTS index_recommendations (
                            id INT AUTO_INCREMENT PRIMARY KEY,
                            table_name VARCHAR(100) NOT NULL,
                            columns JSON NOT NULL,
                            index_type VARCHAR(20) NOT NULL DEFAULT 'BTREE',
                            reason TEXT NOT NULL,
                            estimated_benefit DECIMAL(5,2) NOT NULL DEFAULT 0,
                            create_sql TEXT NOT NULL,
                            status ENUM('pending', 'applied', 'rejected') DEFAULT 'pending',
                            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                            applied_at TIMESTAMP NULL,
                            INDEX idx_table_name (table_name),
                            INDEX idx_status (status),
                            INDEX idx_created_at (created_at)
                        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
                    """
                    )

                    # 性能指標記錄表
                    await cursor.execute(
                        """
                        CREATE TABLE IF NOT EXISTS db_performance_metrics (
                            id INT AUTO_INCREMENT PRIMARY KEY,
                            query_cache_hit_rate DECIMAL(5,2),
                            slow_query_count INT,
                            connections_used INT,
                            max_connections INT,
                            innodb_buffer_pool_hit_rate DECIMAL(5,2),
                            table_scan_rate DECIMAL(5,2),
                            temp_table_rate DECIMAL(5,2),
                            key_read_hit_rate DECIMAL(5,2),
                            recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                            INDEX idx_recorded_at (recorded_at)
                        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
                    """
                    )

                    await conn.commit()
                    logger.info("✅ 優化相關表格建立完成")

        except Exception as e:
            logger.error(f"❌ 建立優化表格失敗: {e}")
            raise

    # ========== 查詢分析和監控 ==========

    async def analyze_query(self, query: str, params: tuple = None) -> QueryAnalysis:
        """分析單個查詢"""
        start_time = time.time()
        query_hash = hashlib.sha256(query.encode()).hexdigest()[:32]  # 使用 SHA256

        try:
            # 執行 EXPLAIN 分析
            explain_result = await self._explain_query(query, params)

            # 分析查詢類型
            query_type = self._detect_query_type(query)

            # 執行查詢並測量性能
            execution_time, rows_examined, rows_sent = await self._execute_and_measure(
                query, params
            )

            # 提取表格和索引信息
            tables_used = self._extract_tables_from_explain(explain_result)
            indexes_used = self._extract_indexes_from_explain(explain_result)

            # 生成優化建議
            optimization_level, suggestions = (
                await self._generate_optimization_suggestions(
                    explain_result, execution_time, query_type, query
                )
            )

            # 創建分析結果
            analysis = QueryAnalysis(
                query_hash=query_hash,
                original_query=query,
                query_type=query_type,
                execution_time=execution_time,
                rows_examined=rows_examined,
                rows_sent=rows_sent,
                tables_used=tables_used,
                indexes_used=indexes_used,
                optimization_level=optimization_level,
                suggestions=suggestions,
                explain_plan=explain_result,
                timestamp=datetime.now(timezone.utc),
            )

            # 記錄分析結果
            await self._log_query_analysis(analysis)

            # 如果是慢查詢，記錄警告
            if execution_time > self.slow_query_threshold:
                logger.warning(
                    f"🐌 慢查詢檢測: {execution_time:.3f}s - {query[:100]}..."
                )

            return analysis

        except Exception as e:
            logger.error(f"❌ 查詢分析失敗: {e}")
            # 返回基本分析結果
            return QueryAnalysis(
                query_hash=query_hash,
                original_query=query,
                query_type=self._detect_query_type(query),
                execution_time=time.time() - start_time,
                rows_examined=0,
                rows_sent=0,
                tables_used=[],
                indexes_used=[],
                optimization_level=OptimizationLevel.LOW,
                suggestions=["查詢分析失敗，請檢查語法"],
                explain_plan={},
                timestamp=datetime.now(timezone.utc),
            )

    async def _explain_query(self, query: str, params: tuple = None) -> Dict[str, Any]:
        """執行 EXPLAIN 分析"""
        try:
            async with db_pool.connection() as conn:
                async with conn.cursor() as cursor:
                    explain_query = f"EXPLAIN FORMAT=JSON {query}"
                    await cursor.execute(explain_query, params)
                    result = await cursor.fetchone()

                    if result and result[0]:
                        return json.loads(result[0])
                    return {}

        except Exception as e:
            logger.error(f"❌ EXPLAIN 分析失敗: {e}")
            return {}

    async def _execute_and_measure(
        self, query: str, params: tuple = None
    ) -> Tuple[float, int, int]:
        """執行查詢並測量性能"""
        start_time = time.time()
        rows_examined = 0
        rows_sent = 0

        try:
            async with db_pool.connection() as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute(query, params)

                    # 獲取執行統計
                    await cursor.execute("SHOW SESSION STATUS LIKE 'Handler_read%'")
                    handler_stats = await cursor.fetchall()

                    for stat_name, stat_value in handler_stats:
                        if "read" in stat_name.lower():
                            rows_examined += int(stat_value)

                    rows_sent = cursor.rowcount if cursor.rowcount > 0 else 0

            execution_time = time.time() - start_time
            return execution_time, rows_examined, rows_sent

        except Exception as e:
            execution_time = time.time() - start_time
            logger.error(f"❌ 查詢執行測量失敗: {e}")
            return execution_time, 0, 0

    def _detect_query_type(self, query: str) -> QueryType:
        """檢測查詢類型"""
        query_upper = query.strip().upper()

        if query_upper.startswith("SELECT"):
            return QueryType.SELECT
        elif query_upper.startswith("INSERT"):
            return QueryType.INSERT
        elif query_upper.startswith("UPDATE"):
            return QueryType.UPDATE
        elif query_upper.startswith("DELETE"):
            return QueryType.DELETE
        elif query_upper.startswith("CREATE"):
            return QueryType.CREATE
        elif query_upper.startswith("ALTER"):
            return QueryType.ALTER
        else:
            return QueryType.SELECT  # 預設為 SELECT

    def _extract_tables_from_explain(self, explain_result: Dict) -> List[str]:
        """從 EXPLAIN 結果中提取表格名稱"""
        tables = []

        try:
            query_block = explain_result.get("query_block", {})

            # 處理簡單查詢
            if "table" in query_block:
                table_info = query_block["table"]
                if isinstance(table_info, dict) and "table_name" in table_info:
                    tables.append(table_info["table_name"])

            # 處理複雜查詢（嵌套、聯接等）
            if "nested_loop" in query_block:
                nested_tables = self._extract_nested_tables(query_block["nested_loop"])
                tables.extend(nested_tables)

        except Exception as e:
            logger.debug(f"提取表格名稱失敗: {e}")

        return list(set(tables))  # 去重

    def _extract_indexes_from_explain(self, explain_result: Dict) -> List[str]:
        """從 EXPLAIN 結果中提取使用的索引"""
        indexes = []

        try:

            def extract_from_block(block):
                if isinstance(block, dict):
                    if "key" in block and block["key"] != "NULL":
                        indexes.append(block["key"])

                    # 遞歸處理子塊
                    for key, value in block.items():
                        if isinstance(value, (dict, list)):
                            extract_from_block(value)
                elif isinstance(block, list):
                    for item in block:
                        extract_from_block(item)

            extract_from_block(explain_result)

        except Exception as e:
            logger.debug(f"提取索引名稱失敗: {e}")

        return list(set(indexes))  # 去重

    def _extract_nested_tables(self, nested_loop: List) -> List[str]:
        """從嵌套循環中提取表格"""
        tables = []

        for item in nested_loop:
            if isinstance(item, dict) and "table" in item:
                table_info = item["table"]
                if "table_name" in table_info:
                    tables.append(table_info["table_name"])

        return tables

    async def _generate_optimization_suggestions(
        self,
        explain_result: Dict,
        execution_time: float,
        query_type: QueryType,
        query: str,
    ) -> Tuple[OptimizationLevel, List[str]]:
        """生成優化建議"""
        suggestions = []
        optimization_level = OptimizationLevel.LOW

        try:
            # 基於執行時間判斷優化等級
            if execution_time > 5.0:
                optimization_level = OptimizationLevel.CRITICAL
            elif execution_time > 2.0:
                optimization_level = OptimizationLevel.HIGH
            elif execution_time > 1.0:
                optimization_level = OptimizationLevel.MEDIUM

            # 分析 EXPLAIN 結果
            query_block = explain_result.get("query_block", {})

            # 檢查是否使用了索引
            if self._has_full_table_scan(query_block):
                suggestions.append("檢測到全表掃描，建議添加適當的索引")
                optimization_level = max(optimization_level, OptimizationLevel.HIGH)

            # 檢查是否使用了臨時表
            if self._uses_temporary_table(query_block):
                suggestions.append("查詢使用了臨時表，考慮優化排序或分組條件")
                optimization_level = max(optimization_level, OptimizationLevel.MEDIUM)

            # 檢查是否使用了檔案排序
            if self._uses_filesort(query_block):
                suggestions.append("檢測到檔案排序，建議為排序欄位添加索引")
                optimization_level = max(optimization_level, OptimizationLevel.MEDIUM)

            # 檢查查詢結構
            if query_type == QueryType.SELECT:
                if re.search(r'\bLIKE\s+[\'"]%.*%[\'"]', query, re.IGNORECASE):
                    suggestions.append(
                        "避免使用前導萬用字元的 LIKE 查詢，考慮使用全文搜索"
                    )

                if re.search(r"\bORDER BY\b.*\bRAND\(\)", query, re.IGNORECASE):
                    suggestions.append("避免使用 ORDER BY RAND()，考慮其他隨機化方案")

            # 預設建議
            if not suggestions:
                if execution_time > self.slow_query_threshold:
                    suggestions.append("查詢執行時間較長，建議檢查表結構和索引使用")
                else:
                    suggestions.append("查詢性能良好")

        except Exception as e:
            logger.error(f"❌ 生成優化建議失敗: {e}")
            suggestions = ["分析過程中發生錯誤，建議手動檢查查詢"]

        return optimization_level, suggestions

    def _has_full_table_scan(self, query_block: Dict) -> bool:
        """檢查是否有全表掃描"""
        try:

            def check_block(block):
                if isinstance(block, dict):
                    if "access_type" in block and block["access_type"] == "ALL":
                        return True

                    for value in block.values():
                        if isinstance(value, (dict, list)) and check_block(value):
                            return True
                elif isinstance(block, list):
                    for item in block:
                        if check_block(item):
                            return True
                return False

            return check_block(query_block)
        except:
            return False

    def _uses_temporary_table(self, query_block: Dict) -> bool:
        """檢查是否使用臨時表"""
        try:
            return "using_temporary_table" in json.dumps(query_block).lower()
        except:
            return False

    def _uses_filesort(self, query_block: Dict) -> bool:
        """檢查是否使用檔案排序"""
        try:
            return "using_filesort" in json.dumps(query_block).lower()
        except:
            return False

    async def _log_query_analysis(self, analysis: QueryAnalysis):
        """記錄查詢分析結果"""
        try:
            async with db_pool.connection() as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute(
                        """
                        INSERT INTO query_analysis_log
                        (query_hash, query_text, query_type, execution_time,
                         rows_examined, rows_sent, tables_used, indexes_used,
                         optimization_level, suggestions, explain_plan)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                        (
                            analysis.query_hash,
                            analysis.original_query,
                            analysis.query_type.value,
                            analysis.execution_time,
                            analysis.rows_examined,
                            analysis.rows_sent,
                            json.dumps(analysis.tables_used),
                            json.dumps(analysis.indexes_used),
                            analysis.optimization_level.value,
                            json.dumps(analysis.suggestions),
                            json.dumps(analysis.explain_plan),
                        ),
                    )
                    await conn.commit()

        except Exception as e:
            logger.error(f"❌ 記錄查詢分析失敗: {e}")

    # ========== 索引管理 ==========

    async def analyze_index_usage(
        self, table_name: str = None
    ) -> List[IndexRecommendation]:
        """分析索引使用並生成建議"""
        try:
            recommendations = []

            # 獲取所有表格或指定表格
            tables = await self._get_tables(table_name)

            for table in tables:
                # 分析現有索引使用情況
                index_stats = await self._get_index_statistics(table)

                # 分析查詢模式
                query_patterns = await self._get_query_patterns(table)

                # 生成索引建議
                table_recommendations = await self._generate_index_recommendations(
                    table, index_stats, query_patterns
                )

                recommendations.extend(table_recommendations)

            return recommendations

        except Exception as e:
            logger.error(f"❌ 索引分析失敗: {e}")
            return []

    async def _get_tables(self, table_name: str = None) -> List[str]:
        """獲取表格清單"""
        try:
            async with db_pool.connection() as conn:
                async with conn.cursor() as cursor:
                    if table_name:
                        await cursor.execute(
                            """
                            SELECT table_name FROM information_schema.tables
                            WHERE table_schema = DATABASE() AND table_name = %s
                        """,
                            (table_name,),
                        )
                    else:
                        await cursor.execute(
                            """
                            SELECT table_name FROM information_schema.tables
                            WHERE table_schema = DATABASE() AND table_type = 'BASE TABLE'
                        """
                        )

                    return [row[0] for row in await cursor.fetchall()]

        except Exception as e:
            logger.error(f"❌ 獲取表格清單失敗: {e}")
            return []

    async def _get_index_statistics(self, table_name: str) -> Dict[str, Any]:
        """獲取索引統計資訊"""
        try:
            async with db_pool.connection() as conn:
                async with conn.cursor() as cursor:
                    # 獲取索引資訊
                    await cursor.execute(
                        """
                        SELECT
                            index_name,
                            column_name,
                            cardinality,
                            sub_part,
                            nullable,
                            index_type
                        FROM information_schema.statistics
                        WHERE table_schema = DATABASE() AND table_name = %s
                        ORDER BY index_name, seq_in_index
                    """,
                        (table_name,),
                    )

                    index_info = await cursor.fetchall()

                    # 獲取索引使用統計
                    await cursor.execute(
                        """
                        SELECT
                            index_name,
                            COUNT(*) as usage_count
                        FROM information_schema.statistics s
                        WHERE table_schema = DATABASE() AND table_name = %s
                        GROUP BY index_name
                    """,
                        (table_name,),
                    )

                    usage_stats = dict(await cursor.fetchall())

                    return {"index_info": index_info, "usage_stats": usage_stats}

        except Exception as e:
            logger.error(f"❌ 獲取索引統計失敗 {table_name}: {e}")
            return {}

    async def _get_query_patterns(self, table_name: str) -> List[Dict[str, Any]]:
        """獲取查詢模式"""
        try:
            async with db_pool.connection() as conn:
                async with conn.cursor() as cursor:
                    # 從查詢分析記錄中獲取模式
                    await cursor.execute(
                        """
                        SELECT
                            query_text,
                            COUNT(*) as frequency,
                            AVG(execution_time) as avg_execution_time,
                            MAX(execution_time) as max_execution_time
                        FROM query_analysis_log
                        WHERE JSON_CONTAINS(tables_used, %s)
                        AND created_at > DATE_SUB(NOW(), INTERVAL 7 DAY)
                        GROUP BY query_hash
                        ORDER BY frequency DESC, avg_execution_time DESC
                        LIMIT 50
                    """,
                        (json.dumps([table_name]),),
                    )

                    patterns = []
                    for row in await cursor.fetchall():
                        patterns.append(
                            {
                                "query": row[0],
                                "frequency": row[1],
                                "avg_time": row[2],
                                "max_time": row[3],
                            }
                        )

                    return patterns

        except Exception as e:
            logger.error(f"❌ 獲取查詢模式失敗 {table_name}: {e}")
            return []

    async def _generate_index_recommendations(
        self, table_name: str, index_stats: Dict, query_patterns: List[Dict]
    ) -> List[IndexRecommendation]:
        """生成索引建議"""
        recommendations = []

        try:
            # 分析 WHERE 條件中常用的欄位
            where_columns = self._extract_where_columns(query_patterns)

            # 分析 ORDER BY 中常用的欄位
            self._extract_order_columns(query_patterns)

            # 分析 JOIN 條件中的欄位
            self._extract_join_columns(query_patterns)

            # 獲取現有索引
            existing_indexes = self._get_existing_indexes(index_stats)

            # 生成 WHERE 條件索引建議
            for column, frequency in where_columns.items():
                if not self._has_index_on_column(existing_indexes, column):
                    recommendation = IndexRecommendation(
                        table_name=table_name,
                        columns=[column],
                        index_type="BTREE",
                        reason=f"WHERE 條件中高頻使用 ({frequency} 次)",
                        estimated_benefit=min(frequency * 0.1, 10.0),
                        create_sql=f"CREATE INDEX idx_{table_name}_{column} ON {table_name} ({column})",
                    )
                    recommendations.append(recommendation)

            # 生成複合索引建議
            composite_candidates = self._identify_composite_index_candidates(
                query_patterns
            )
            for columns in composite_candidates:
                if not self._has_composite_index(existing_indexes, columns):
                    columns_str = "_".join(columns)
                    recommendation = IndexRecommendation(
                        table_name=table_name,
                        columns=columns,
                        index_type="BTREE",
                        reason="複合查詢條件優化",
                        estimated_benefit=5.0,
                        create_sql=f"CREATE INDEX idx_{table_name}_{columns_str} ON {table_name} ({', '.join(columns)})",
                    )
                    recommendations.append(recommendation)

        except Exception as e:
            logger.error(f"❌ 生成索引建議失敗 {table_name}: {e}")

        return recommendations

    def _extract_where_columns(self, query_patterns: List[Dict]) -> Dict[str, int]:
        """提取 WHERE 條件中的欄位"""
        columns = {}

        for pattern in query_patterns:
            query = pattern["query"].upper()
            frequency = pattern["frequency"]

            # 簡單的正則匹配 WHERE 條件
            where_matches = re.findall(r"WHERE\s+.*?(\w+)\s*[=<>!]", query)
            and_matches = re.findall(r"AND\s+(\w+)\s*[=<>!]", query)

            for match in where_matches + and_matches:
                columns[match] = columns.get(match, 0) + frequency

        return columns

    def _extract_order_columns(self, query_patterns: List[Dict]) -> Dict[str, int]:
        """提取 ORDER BY 中的欄位"""
        columns = {}

        for pattern in query_patterns:
            query = pattern["query"].upper()
            frequency = pattern["frequency"]

            order_matches = re.findall(r"ORDER\s+BY\s+(\w+)", query)

            for match in order_matches:
                columns[match] = columns.get(match, 0) + frequency

        return columns

    def _extract_join_columns(self, query_patterns: List[Dict]) -> Dict[str, int]:
        """提取 JOIN 條件中的欄位"""
        columns = {}

        for pattern in query_patterns:
            query = pattern["query"].upper()
            frequency = pattern["frequency"]

            join_matches = re.findall(r"JOIN\s+\w+\s+ON\s+.*?(\w+)\s*=", query)

            for match in join_matches:
                columns[match] = columns.get(match, 0) + frequency

        return columns

    def _get_existing_indexes(self, index_stats: Dict) -> List[Dict]:
        """獲取現有索引資訊"""
        indexes = []

        try:
            index_info = index_stats.get("index_info", [])

            current_index = None
            for info in index_info:
                index_name, column_name = info[0], info[1]

                if current_index is None or current_index["name"] != index_name:
                    if current_index:
                        indexes.append(current_index)

                    current_index = {"name": index_name, "columns": [column_name]}
                else:
                    current_index["columns"].append(column_name)

            if current_index:
                indexes.append(current_index)

        except Exception as e:
            logger.error(f"❌ 解析現有索引失敗: {e}")

        return indexes

    def _has_index_on_column(self, existing_indexes: List[Dict], column: str) -> bool:
        """檢查是否已存在該欄位的索引"""
        for index in existing_indexes:
            if column in index["columns"]:
                return True
        return False

    def _has_composite_index(
        self, existing_indexes: List[Dict], columns: List[str]
    ) -> bool:
        """檢查是否已存在複合索引"""
        for index in existing_indexes:
            if set(columns).issubset(set(index["columns"])):
                return True
        return False

    def _identify_composite_index_candidates(
        self, query_patterns: List[Dict]
    ) -> List[List[str]]:
        """識別複合索引候選"""
        candidates = []

        for pattern in query_patterns:
            query = pattern["query"].upper()

            # 找出同時出現在 WHERE 條件中的欄位
            where_pattern = r"WHERE\s+(.*?)(?:ORDER\s+BY|GROUP\s+BY|HAVING|LIMIT|$)"
            where_match = re.search(where_pattern, query)

            if where_match:
                where_clause = where_match.group(1)
                columns = re.findall(r"(\w+)\s*[=<>!]", where_clause)

                if len(columns) > 1:
                    candidates.append(columns[:3])  # 最多3個欄位的複合索引

        return candidates

    # ========== 性能監控 ==========

    async def collect_database_metrics(self) -> DatabaseMetrics:
        """收集資料庫性能指標"""
        try:
            async with db_pool.connection() as conn:
                async with conn.cursor() as cursor:
                    # 獲取各種性能指標
                    metrics_queries = {
                        "query_cache_hit_rate": """
                            SELECT
                                ROUND(
                                    100 * (1 - Qcache_hits / (Qcache_hits + Qcache_inserts)), 2
                                ) as hit_rate
                            FROM
                                (SELECT
                                    VARIABLE_VALUE as Qcache_hits
                                 FROM information_schema.GLOBAL_STATUS
                                 WHERE VARIABLE_NAME = 'Qcache_hits') qh,
                                (SELECT
                                    VARIABLE_VALUE as Qcache_inserts
                                 FROM information_schema.GLOBAL_STATUS
                                 WHERE VARIABLE_NAME = 'Qcache_inserts') qi
                        """,
                        "slow_queries": """
                            SELECT VARIABLE_VALUE
                            FROM information_schema.GLOBAL_STATUS
                            WHERE VARIABLE_NAME = 'Slow_queries'
                        """,
                        "connections": """
                            SELECT
                                (SELECT VARIABLE_VALUE FROM information_schema.GLOBAL_STATUS WHERE VARIABLE_NAME = 'Threads_connected') as used,
                                (SELECT VARIABLE_VALUE FROM information_schema.GLOBAL_VARIABLES WHERE VARIABLE_NAME = 'max_connections') as max_conn
                        """,
                        "innodb_buffer_pool": """
                            SELECT
                                ROUND(
                                    100 * (
                                        (SELECT VARIABLE_VALUE FROM information_schema.GLOBAL_STATUS WHERE VARIABLE_NAME = 'Innodb_buffer_pool_read_requests') -
                                        (SELECT VARIABLE_VALUE FROM information_schema.GLOBAL_STATUS WHERE VARIABLE_NAME = 'Innodb_buffer_pool_reads')
                                    ) /
                                    (SELECT VARIABLE_VALUE FROM information_schema.GLOBAL_STATUS WHERE VARIABLE_NAME = 'Innodb_buffer_pool_read_requests'), 2
                                ) as buffer_hit_rate
                        """,
                    }

                    metrics_data = {}

                    for metric_name, query in metrics_queries.items():
                        try:
                            await cursor.execute(query)
                            result = await cursor.fetchone()

                            if metric_name == "connections":
                                metrics_data["connections_used"] = (
                                    int(result[0]) if result else 0
                                )
                                metrics_data["max_connections"] = (
                                    int(result[1]) if result else 0
                                )
                            else:
                                metrics_data[metric_name] = (
                                    float(result[0]) if result and result[0] else 0.0
                                )

                        except Exception as e:
                            logger.warning(f"⚠️ 收集指標失敗 {metric_name}: {e}")
                            metrics_data[metric_name] = 0.0

                    # 創建指標物件
                    metrics = DatabaseMetrics(
                        query_cache_hit_rate=metrics_data.get(
                            "query_cache_hit_rate", 0.0
                        ),
                        slow_query_count=int(metrics_data.get("slow_queries", 0)),
                        connections_used=metrics_data.get("connections_used", 0),
                        max_connections=metrics_data.get("max_connections", 0),
                        innodb_buffer_pool_hit_rate=metrics_data.get(
                            "innodb_buffer_pool", 0.0
                        ),
                        table_scan_rate=0.0,  # 需要額外計算
                        temp_table_rate=0.0,  # 需要額外計算
                        key_read_hit_rate=0.0,  # 需要額外計算
                        timestamp=datetime.now(timezone.utc),
                    )

                    # 快取指標
                    self.metrics_cache = metrics
                    self.metrics_cache_time = datetime.now(timezone.utc)

                    return metrics

        except Exception as e:
            logger.error(f"❌ 收集資料庫指標失敗: {e}")
            return DatabaseMetrics(
                query_cache_hit_rate=0.0,
                slow_query_count=0,
                connections_used=0,
                max_connections=0,
                innodb_buffer_pool_hit_rate=0.0,
                table_scan_rate=0.0,
                temp_table_rate=0.0,
                key_read_hit_rate=0.0,
                timestamp=datetime.now(timezone.utc),
            )

    async def get_optimization_summary(self, days: int = 7) -> Dict[str, Any]:
        """獲取優化摘要報告"""
        try:
            async with db_pool.connection() as conn:
                async with conn.cursor() as cursor:
                    # 慢查詢統計
                    await cursor.execute(
                        """
                        SELECT
                            COUNT(*) as total_slow_queries,
                            AVG(execution_time) as avg_slow_time,
                            MAX(execution_time) as max_slow_time,
                            COUNT(DISTINCT query_hash) as unique_slow_queries
                        FROM query_analysis_log
                        WHERE execution_time > %s
                        AND created_at > DATE_SUB(NOW(), INTERVAL %s DAY)
                    """,
                        (self.slow_query_threshold, days),
                    )

                    slow_query_stats = await cursor.fetchone()

                    # 優化等級分佈
                    await cursor.execute(
                        """
                        SELECT
                            optimization_level,
                            COUNT(*) as count
                        FROM query_analysis_log
                        WHERE created_at > DATE_SUB(NOW(), INTERVAL %s DAY)
                        GROUP BY optimization_level
                    """,
                        (days,),
                    )

                    optimization_levels = dict(await cursor.fetchall())

                    # 最頻繁的查詢
                    await cursor.execute(
                        """
                        SELECT
                            query_text,
                            COUNT(*) as frequency,
                            AVG(execution_time) as avg_time,
                            optimization_level
                        FROM query_analysis_log
                        WHERE created_at > DATE_SUB(NOW(), INTERVAL %s DAY)
                        GROUP BY query_hash
                        ORDER BY frequency DESC
                        LIMIT 10
                    """,
                        (days,),
                    )

                    frequent_queries = await cursor.fetchall()

                    # 索引建議統計
                    await cursor.execute(
                        """
                        SELECT
                            status,
                            COUNT(*) as count,
                            AVG(estimated_benefit) as avg_benefit
                        FROM index_recommendations
                        WHERE created_at > DATE_SUB(NOW(), INTERVAL %s DAY)
                        GROUP BY status
                    """,
                        (days,),
                    )

                    index_stats = await cursor.fetchall()

                    return {
                        "period_days": days,
                        "slow_queries": {
                            "total": slow_query_stats[0] if slow_query_stats else 0,
                            "avg_time": (
                                float(slow_query_stats[1])
                                if slow_query_stats and slow_query_stats[1]
                                else 0
                            ),
                            "max_time": (
                                float(slow_query_stats[2])
                                if slow_query_stats and slow_query_stats[2]
                                else 0
                            ),
                            "unique_count": (
                                slow_query_stats[3] if slow_query_stats else 0
                            ),
                        },
                        "optimization_levels": optimization_levels,
                        "frequent_queries": [
                            {
                                "query": (
                                    query[:100] + "..." if len(query) > 100 else query
                                ),
                                "frequency": freq,
                                "avg_time": float(avg_time),
                                "level": level,
                            }
                            for query, freq, avg_time, level in frequent_queries
                        ],
                        "index_recommendations": dict(index_stats),
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    }

        except Exception as e:
            logger.error(f"❌ 獲取優化摘要失敗: {e}")
            return {}

    async def _load_optimization_history(self):
        """載入優化歷史"""
        # 實現載入歷史記錄的邏輯

    async def _analyze_existing_tables(self):
        """分析現有表結構"""
        # 實現分析表結構的邏輯


# ========== 全域實例 ==========

# 創建全域資料庫優化器實例
db_optimizer = DatabaseOptimizer()


async def get_db_optimizer() -> DatabaseOptimizer:
    """獲取資料庫優化器實例"""
    return db_optimizer


# 裝飾器：自動分析查詢性能
def query_analyzed(func):
    """查詢分析裝飾器"""

    async def wrapper(*args, **kwargs):
        start_time = time.time()

        try:
            result = await func(*args, **kwargs)

            # 如果執行時間超過閾值，記錄分析
            execution_time = time.time() - start_time
            if execution_time > db_optimizer.slow_query_threshold:
                # 這裡需要獲取實際的查詢語句，可能需要修改函數簽名
                logger.warning(f"慢查詢檢測: {func.__name__} - {execution_time:.3f}s")

            return result

        except Exception as e:
            logger.error(f"查詢執行失敗 {func.__name__}: {e}")
            raise

    return wrapper
