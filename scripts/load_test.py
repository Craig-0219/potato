#!/usr/bin/env python3
# scripts/load_test.py - 負載測試腳本
"""
簡單的負載測試框架 v2.2.0
用於測試機器人系統的性能和穩定性
"""

import asyncio
import aiohttp
import time
import random
import json
from typing import Dict, List, Any, Optional
from datetime import datetime, timezone
from dataclasses import dataclass, asdict
import concurrent.futures
import logging

# 配置日誌
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

@dataclass
class TestResult:
    """測試結果"""
    test_name: str
    start_time: datetime
    end_time: datetime
    duration: float
    success: bool
    error_message: Optional[str] = None
    response_data: Optional[Dict[str, Any]] = None

@dataclass
class LoadTestConfig:
    """負載測試配置"""
    name: str
    target_url: str
    concurrent_users: int
    test_duration: int  # 秒
    requests_per_second: int
    headers: Dict[str, str]
    payload: Optional[Dict[str, Any]] = None

class LoadTester:
    """負載測試器"""
    
    def __init__(self):
        self.results: List[TestResult] = []
        self.session: Optional[aiohttp.ClientSession] = None
        
    async def __aenter__(self):
        """異步上下文管理器入口"""
        self.session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=30),
            connector=aiohttp.TCPConnector(limit=1000)
        )
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """異步上下文管理器出口"""
        if self.session:
            await self.session.close()

    async def run_load_test(self, config: LoadTestConfig) -> Dict[str, Any]:
        """運行負載測試"""
        logger.info(f"🚀 開始負載測試: {config.name}")
        logger.info(f"📊 配置: {config.concurrent_users} 併發用戶, {config.test_duration}秒")
        
        start_time = time.time()
        
        # 創建任務列表
        tasks = []
        for i in range(config.concurrent_users):
            task = asyncio.create_task(
                self._run_user_simulation(config, i)
            )
            tasks.append(task)
        
        # 等待所有任務完成
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        end_time = time.time()
        total_duration = end_time - start_time
        
        # 統計結果
        stats = self._calculate_statistics(results, total_duration)
        
        logger.info(f"✅ 負載測試完成: {config.name}")
        logger.info(f"📈 總請求數: {stats['total_requests']}")
        logger.info(f"✅ 成功率: {stats['success_rate']:.2f}%")
        logger.info(f"⚡ 平均響應時間: {stats['avg_response_time']:.3f}秒")
        
        return stats

    async def _run_user_simulation(self, config: LoadTestConfig, user_id: int) -> List[TestResult]:
        """模擬單個用戶的請求"""
        user_results = []
        end_time = time.time() + config.test_duration
        request_interval = 1.0 / config.requests_per_second
        
        while time.time() < end_time:
            start = time.time()
            
            try:
                result = await self._make_request(
                    config.target_url,
                    config.headers,
                    config.payload,
                    f"{config.name}_user_{user_id}"
                )
                user_results.append(result)
                
            except Exception as e:
                logger.error(f"❌ 用戶 {user_id} 請求失敗: {e}")
                user_results.append(TestResult(
                    test_name=f"{config.name}_user_{user_id}",
                    start_time=datetime.now(timezone.utc),
                    end_time=datetime.now(timezone.utc),
                    duration=0,
                    success=False,
                    error_message=str(e)
                ))
            
            # 控制請求頻率
            elapsed = time.time() - start
            if elapsed < request_interval:
                await asyncio.sleep(request_interval - elapsed)
        
        return user_results

    async def _make_request(self, url: str, headers: Dict[str, str], 
                          payload: Optional[Dict[str, Any]], test_name: str) -> TestResult:
        """發送HTTP請求"""
        start_time = datetime.now(timezone.utc)
        
        try:
            if payload:
                async with self.session.post(url, headers=headers, json=payload) as response:
                    response_data = await response.json() if response.content_type == 'application/json' else await response.text()
                    success = response.status < 400
            else:
                async with self.session.get(url, headers=headers) as response:
                    response_data = await response.json() if response.content_type == 'application/json' else await response.text()
                    success = response.status < 400
            
            end_time = datetime.now(timezone.utc)
            duration = (end_time - start_time).total_seconds()
            
            return TestResult(
                test_name=test_name,
                start_time=start_time,
                end_time=end_time,
                duration=duration,
                success=success,
                response_data=response_data if isinstance(response_data, dict) else None
            )
            
        except Exception as e:
            end_time = datetime.now(timezone.utc)
            duration = (end_time - start_time).total_seconds()
            
            return TestResult(
                test_name=test_name,
                start_time=start_time,
                end_time=end_time,
                duration=duration,
                success=False,
                error_message=str(e)
            )

    def _calculate_statistics(self, results: List[List[TestResult]], total_duration: float) -> Dict[str, Any]:
        """計算統計數據"""
        all_results = []
        for user_results in results:
            if isinstance(user_results, list):
                all_results.extend(user_results)
        
        if not all_results:
            return {
                'total_requests': 0,
                'successful_requests': 0,
                'failed_requests': 0,
                'success_rate': 0.0,
                'avg_response_time': 0.0,
                'min_response_time': 0.0,
                'max_response_time': 0.0,
                'requests_per_second': 0.0,
                'total_duration': total_duration
            }
        
        successful = [r for r in all_results if r.success]
        failed = [r for r in all_results if not r.success]
        
        response_times = [r.duration for r in all_results if r.duration > 0]
        
        return {
            'total_requests': len(all_results),
            'successful_requests': len(successful),
            'failed_requests': len(failed),
            'success_rate': (len(successful) / len(all_results)) * 100,
            'avg_response_time': sum(response_times) / len(response_times) if response_times else 0,
            'min_response_time': min(response_times) if response_times else 0,
            'max_response_time': max(response_times) if response_times else 0,
            'requests_per_second': len(all_results) / total_duration if total_duration > 0 else 0,
            'total_duration': total_duration
        }

class DatabaseLoadTester:
    """資料庫負載測試器"""
    
    def __init__(self, db_pool):
        self.db_pool = db_pool
        self.results: List[TestResult] = []

    async def test_database_performance(self, concurrent_connections: int = 10, 
                                      test_duration: int = 30) -> Dict[str, Any]:
        """測試資料庫性能"""
        logger.info(f"🗄️ 開始資料庫負載測試")
        logger.info(f"📊 配置: {concurrent_connections} 併發連接, {test_duration}秒")
        
        start_time = time.time()
        
        # 創建測試任務
        tasks = []
        for i in range(concurrent_connections):
            task = asyncio.create_task(
                self._run_db_operations(test_duration, i)
            )
            tasks.append(task)
        
        # 等待所有任務完成
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        end_time = time.time()
        total_duration = end_time - start_time
        
        # 統計結果
        all_operations = []
        for ops in results:
            if isinstance(ops, list):
                all_operations.extend(ops)
        
        stats = self._calculate_db_statistics(all_operations, total_duration)
        
        logger.info(f"✅ 資料庫測試完成")
        logger.info(f"📈 總操作數: {stats['total_operations']}")
        logger.info(f"✅ 成功率: {stats['success_rate']:.2f}%")
        logger.info(f"⚡ 平均操作時間: {stats['avg_operation_time']:.3f}秒")
        
        return stats

    async def _run_db_operations(self, test_duration: int, worker_id: int) -> List[TestResult]:
        """運行資料庫操作"""
        operations = []
        end_time = time.time() + test_duration
        
        while time.time() < end_time:
            # 隨機選擇操作類型
            operation_type = random.choice(['select', 'insert', 'update'])
            
            try:
                result = await self._perform_db_operation(operation_type, worker_id)
                operations.append(result)
                
                # 短暫延遲避免過度負載
                await asyncio.sleep(0.01)
                
            except Exception as e:
                logger.error(f"❌ 資料庫操作失敗: {e}")
                operations.append(TestResult(
                    test_name=f"db_{operation_type}_worker_{worker_id}",
                    start_time=datetime.now(timezone.utc),
                    end_time=datetime.now(timezone.utc),
                    duration=0,
                    success=False,
                    error_message=str(e)
                ))
        
        return operations

    async def _perform_db_operation(self, operation_type: str, worker_id: int) -> TestResult:
        """執行資料庫操作"""
        start_time = datetime.now(timezone.utc)
        test_name = f"db_{operation_type}_worker_{worker_id}"
        
        try:
            async with self.db_pool.connection() as conn:
                async with conn.cursor() as cursor:
                    if operation_type == 'select':
                        await cursor.execute("SELECT 1 as test_value")
                        result = await cursor.fetchone()
                    elif operation_type == 'insert':
                        await cursor.execute("""
                            INSERT INTO load_test_temp (worker_id, created_at, data) 
                            VALUES (%s, NOW(), %s)
                        """, (worker_id, f"test_data_{int(time.time())}"))
                        await conn.commit()
                    elif operation_type == 'update':
                        await cursor.execute("""
                            UPDATE load_test_temp 
                            SET data = %s 
                            WHERE worker_id = %s 
                            ORDER BY created_at DESC 
                            LIMIT 1
                        """, (f"updated_{int(time.time())}", worker_id))
                        await conn.commit()
            
            end_time = datetime.now(timezone.utc)
            duration = (end_time - start_time).total_seconds()
            
            return TestResult(
                test_name=test_name,
                start_time=start_time,
                end_time=end_time,
                duration=duration,
                success=True
            )
            
        except Exception as e:
            end_time = datetime.now(timezone.utc)
            duration = (end_time - start_time).total_seconds()
            
            return TestResult(
                test_name=test_name,
                start_time=start_time,
                end_time=end_time,
                duration=duration,
                success=False,
                error_message=str(e)
            )

    def _calculate_db_statistics(self, operations: List[TestResult], total_duration: float) -> Dict[str, Any]:
        """計算資料庫統計"""
        if not operations:
            return {
                'total_operations': 0,
                'successful_operations': 0,
                'failed_operations': 0,
                'success_rate': 0.0,
                'avg_operation_time': 0.0,
                'operations_per_second': 0.0
            }
        
        successful = [op for op in operations if op.success]
        failed = [op for op in operations if not op.success]
        operation_times = [op.duration for op in operations if op.duration > 0]
        
        return {
            'total_operations': len(operations),
            'successful_operations': len(successful),
            'failed_operations': len(failed),
            'success_rate': (len(successful) / len(operations)) * 100,
            'avg_operation_time': sum(operation_times) / len(operation_times) if operation_times else 0,
            'operations_per_second': len(operations) / total_duration if total_duration > 0 else 0
        }

async def setup_load_test_tables():
    """設置負載測試所需的表格"""
    try:
        from bot.db.pool import db_pool
        
        async with db_pool.connection() as conn:
            async with conn.cursor() as cursor:
                # 創建臨時測試表
                await cursor.execute("""
                    CREATE TABLE IF NOT EXISTS load_test_temp (
                        id INT AUTO_INCREMENT PRIMARY KEY,
                        worker_id INT NOT NULL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        data VARCHAR(255),
                        INDEX idx_worker_id (worker_id),
                        INDEX idx_created_at (created_at)
                    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
                """)
                await conn.commit()
                logger.info("✅ 負載測試表格創建成功")
                
    except Exception as e:
        logger.error(f"❌ 創建負載測試表格失敗: {e}")
        raise

async def cleanup_load_test_tables():
    """清理負載測試表格"""
    try:
        from bot.db.pool import db_pool
        
        async with db_pool.connection() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute("DROP TABLE IF EXISTS load_test_temp")
                await conn.commit()
                logger.info("🧹 負載測試表格清理完成")
                
    except Exception as e:
        logger.error(f"❌ 清理負載測試表格失敗: {e}")

async def run_comprehensive_load_test():
    """運行綜合負載測試"""
    logger.info("🚀 開始綜合負載測試")
    
    try:
        # 設置測試環境
        await setup_load_test_tables()
        
        # 配置測試
        test_configs = [
            LoadTestConfig(
                name="輕量負載測試",
                target_url="http://localhost:8000/health",  # 假設的健康檢查端點
                concurrent_users=5,
                test_duration=30,
                requests_per_second=2,
                headers={"Content-Type": "application/json"}
            ),
            LoadTestConfig(
                name="中等負載測試",
                target_url="http://localhost:8000/api/stats",
                concurrent_users=20,
                test_duration=60,
                requests_per_second=5,
                headers={"Content-Type": "application/json"}
            )
        ]
        
        # 運行HTTP負載測試
        async with LoadTester() as tester:
            for config in test_configs:
                try:
                    stats = await tester.run_load_test(config)
                    logger.info(f"📊 {config.name} 完成: {stats}")
                except Exception as e:
                    logger.error(f"❌ {config.name} 失敗: {e}")
        
        # 運行資料庫負載測試
        try:
            from bot.db.pool import db_pool
            db_tester = DatabaseLoadTester(db_pool)
            db_stats = await db_tester.test_database_performance(
                concurrent_connections=10,
                test_duration=30
            )
            logger.info(f"📊 資料庫測試完成: {db_stats}")
        except Exception as e:
            logger.error(f"❌ 資料庫測試失敗: {e}")
        
        logger.info("✅ 綜合負載測試完成")
        
    finally:
        # 清理測試環境
        await cleanup_load_test_tables()

if __name__ == "__main__":
    # 運行負載測試
    asyncio.run(run_comprehensive_load_test())