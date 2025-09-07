"""
資料庫優化器模組測試
測試 shared/db_optimizer.py 的基本功能
"""

import pytest
import unittest
from unittest.mock import Mock, patch, MagicMock
import hashlib
from datetime import datetime, timezone

from src.potato_shared.db_optimizer import (
    QueryType, OptimizationLevel, 
    QueryAnalysis, IndexRecommendation, DatabaseOptimizer
)


class TestQueryType(unittest.TestCase):
    """測試查詢類型枚舉"""
    
    def test_query_types(self):
        """測試查詢類型定義"""
        self.assertEqual(QueryType.SELECT.value, "SELECT")
        self.assertEqual(QueryType.INSERT.value, "INSERT")
        self.assertEqual(QueryType.UPDATE.value, "UPDATE")
        self.assertEqual(QueryType.DELETE.value, "DELETE")
        self.assertEqual(QueryType.CREATE.value, "CREATE")
        self.assertEqual(QueryType.ALTER.value, "ALTER")


class TestOptimizationLevel(unittest.TestCase):
    """測試優化等級枚舉"""
    
    def test_optimization_levels(self):
        """測試優化等級定義"""
        self.assertEqual(OptimizationLevel.LOW.value, "low")
        self.assertEqual(OptimizationLevel.MEDIUM.value, "medium")
        self.assertEqual(OptimizationLevel.HIGH.value, "high")
        self.assertEqual(OptimizationLevel.CRITICAL.value, "critical")


class TestQueryAnalysis(unittest.TestCase):
    """測試查詢分析結果數據類"""
    
    def test_create_query_analysis(self):
        """測試創建查詢分析結果"""
        query_hash = "test_hash"
        original_query = "SELECT * FROM users"
        query_type = QueryType.SELECT
        execution_time = 1.5
        rows_examined = 1000
        rows_sent = 10
        timestamp = datetime.now(timezone.utc)
        
        analysis = QueryAnalysis(
            query_hash=query_hash,
            original_query=original_query,
            query_type=query_type,
            execution_time=execution_time,
            rows_examined=rows_examined,
            rows_sent=rows_sent,
            tables_used=["users"],
            indexes_used=["PRIMARY"],
            optimization_level=OptimizationLevel.LOW,
            suggestions=["Test suggestion"],
            explain_plan={},
            timestamp=timestamp
        )
        
        self.assertEqual(analysis.query_hash, query_hash)
        self.assertEqual(analysis.original_query, original_query)
        self.assertEqual(analysis.query_type, query_type)
        self.assertEqual(analysis.execution_time, execution_time)
        self.assertEqual(analysis.rows_examined, rows_examined)
        self.assertEqual(analysis.rows_sent, rows_sent)
        self.assertEqual(analysis.timestamp, timestamp)


class TestIndexRecommendation(unittest.TestCase):
    """測試索引建議數據類"""
    
    def test_create_index_recommendation(self):
        """測試創建索引建議"""
        table_name = "test_table"
        columns = ["col1", "col2"]
        index_type = "BTREE"
        reason = "Test reason"
        estimated_benefit = 0.8
        create_sql = "CREATE INDEX idx_test ON test_table (col1, col2)"
        
        recommendation = IndexRecommendation(
            table_name=table_name,
            columns=columns,
            index_type=index_type,
            reason=reason,
            estimated_benefit=estimated_benefit,
            create_sql=create_sql
        )
        
        self.assertEqual(recommendation.table_name, table_name)
        self.assertEqual(recommendation.columns, columns)
        self.assertEqual(recommendation.index_type, index_type)
        self.assertEqual(recommendation.reason, reason)
        self.assertEqual(recommendation.estimated_benefit, estimated_benefit)
        self.assertEqual(recommendation.create_sql, create_sql)


class TestDatabaseOptimizer(unittest.TestCase):
    """測試資料庫優化器主類"""
    
    def setUp(self):
        """設置測試環境"""
        with patch('src.potato_shared.db_optimizer.db_pool'):
            self.optimizer = DatabaseOptimizer()
    
    def test_init(self):
        """測試初始化"""
        self.assertEqual(self.optimizer.slow_query_threshold, 1.0)
        self.assertIsInstance(self.optimizer.query_cache, dict)
        self.assertIsInstance(self.optimizer.optimization_history, list)
        self.assertIsNone(self.optimizer.metrics_cache)
        self.assertIsNone(self.optimizer.metrics_cache_time)
        
    def test_slow_query_threshold(self):
        """測試慢查詢閾值設定"""
        # 測試預設閾值
        self.assertEqual(self.optimizer.slow_query_threshold, 1.0)
        
        # 測試設定新閾值
        self.optimizer.slow_query_threshold = 2.0
        self.assertEqual(self.optimizer.slow_query_threshold, 2.0)

    @patch('src.potato_shared.db_optimizer.logger')
    def test_basic_functionality(self, mock_logger):
        """測試基本功能存在"""
        # 測試優化器初始化成功
        self.assertIsNotNone(self.optimizer)
        
        # 測試基本屬性存在
        self.assertTrue(hasattr(self.optimizer, 'query_cache'))
        self.assertTrue(hasattr(self.optimizer, 'optimization_history'))
        self.assertTrue(hasattr(self.optimizer, 'slow_query_threshold'))


if __name__ == '__main__':
    unittest.main()