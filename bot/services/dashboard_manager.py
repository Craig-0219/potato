# bot/services/dashboard_manager.py - 高級分析儀表板管理器 v1.7.0
"""
高級分析儀表板管理器
提供實時圖表、效能指標、預測分析等企業級分析功能
"""

import asyncio
import json
import math
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timezone, timedelta
from dataclasses import dataclass, field
from enum import Enum

from bot.db.ticket_dao import TicketDAO
from bot.db.vote_dao import VoteDAO  
from bot.db.workflow_dao import WorkflowDAO
# from bot.db.welcome_dao import WelcomeDAO  # 暫時註解，如果不存在的話
from bot.services.statistics_manager import StatisticsManager
from shared.logger import logger

class ChartType(Enum):
    """圖表類型"""
    LINE = "line"           # 折線圖
    BAR = "bar"            # 柱狀圖
    PIE = "pie"            # 圓餅圖
    AREA = "area"          # 面積圖
    SCATTER = "scatter"    # 散點圖
    HEATMAP = "heatmap"    # 熱力圖

class MetricType(Enum):
    """指標類型"""
    TICKET_VOLUME = "ticket_volume"           # 票券量
    RESPONSE_TIME = "response_time"           # 回應時間
    RESOLUTION_RATE = "resolution_rate"       # 解決率
    CUSTOMER_SATISFACTION = "satisfaction"    # 客戶滿意度
    WORKFLOW_EFFICIENCY = "workflow_eff"     # 工作流程效率
    SYSTEM_PERFORMANCE = "system_perf"       # 系統性能
    USER_ENGAGEMENT = "user_engagement"      # 用戶參與度
    SLA_COMPLIANCE = "sla_compliance"        # SLA合規性

@dataclass
class ChartData:
    """圖表數據結構"""
    chart_type: ChartType
    title: str
    labels: List[str]
    datasets: List[Dict[str, Any]]
    options: Dict[str, Any] = field(default_factory=dict)

@dataclass
class MetricSummary:
    """指標摘要"""
    current_value: float
    previous_value: float
    change_percentage: float
    trend: str  # "up", "down", "stable"
    status: str  # "good", "warning", "critical"

@dataclass
class DashboardData:
    """儀表板數據"""
    title: str
    charts: List[ChartData]
    metrics: Dict[str, MetricSummary]
    insights: List[str]
    generated_at: datetime
    refresh_interval: int = 300  # 秒

class DashboardManager:
    """高級分析儀表板管理器"""
    
    def __init__(self):
        self.ticket_dao = TicketDAO()
        self.vote_dao = VoteDAO()
        self.workflow_dao = WorkflowDAO()
        # self.welcome_dao = WelcomeDAO()  # 暫時註解
        self.stats_manager = StatisticsManager()
        
        # 快取系統
        self._dashboard_cache: Dict[str, DashboardData] = {}
        self._cache_ttl = 300  # 5分鐘快取
        
        # 預測模型參數
        self._prediction_window = 30  # 預測30天
        self._min_data_points = 7   # 最少需要7天數據進行預測
    
    # ========== 儀表板生成 ==========
    
    async def generate_overview_dashboard(self, guild_id: int, days: int = 30) -> DashboardData:
        """生成系統概覽儀表板"""
        cache_key = f"overview_{guild_id}_{days}"
        
        # 檢查快取
        if cache_key in self._dashboard_cache:
            cached = self._dashboard_cache[cache_key]
            if (datetime.now(timezone.utc) - cached.generated_at).seconds < self._cache_ttl:
                return cached
        
        logger.info(f"生成系統概覽儀表板: guild_id={guild_id}, days={days}")
        
        try:
            # 並行獲取各系統數據
            tasks = [
                self._get_ticket_analytics(guild_id, days),
                self._get_workflow_analytics(guild_id, days),
                self._get_user_engagement_analytics(guild_id, days),
                self._get_system_performance_metrics(guild_id, days)
            ]
            
            ticket_data, workflow_data, engagement_data, performance_data = await asyncio.gather(*tasks)
            
            # 生成圖表
            charts = []
            
            # 1. 票券趨勢圖 (折線圖)
            charts.append(await self._create_ticket_trend_chart(ticket_data))
            
            # 2. 工作流程效率圖 (柱狀圖)  
            charts.append(await self._create_workflow_efficiency_chart(workflow_data))
            
            # 3. 用戶參與度圖 (面積圖)
            charts.append(await self._create_engagement_chart(engagement_data))
            
            # 4. 系統性能熱力圖
            charts.append(await self._create_performance_heatmap(performance_data))
            
            # 生成關鍵指標摘要
            metrics = await self._generate_key_metrics(guild_id, days)
            
            # 生成智能洞察
            insights = await self._generate_insights(ticket_data, workflow_data, engagement_data)
            
            dashboard = DashboardData(
                title=f"系統概覽儀表板 - 最近{days}天",
                charts=charts,
                metrics=metrics,
                insights=insights,
                generated_at=datetime.now(timezone.utc)
            )
            
            # 更新快取
            self._dashboard_cache[cache_key] = dashboard
            
            logger.info("✅ 系統概覽儀表板生成完成")
            return dashboard
            
        except Exception as e:
            logger.error(f"❌ 生成系統概覽儀表板失敗: {e}")
            raise
    
    async def generate_performance_dashboard(self, guild_id: int, days: int = 30) -> DashboardData:
        """生成性能分析儀表板"""
        logger.info(f"生成性能分析儀表板: guild_id={guild_id}")
        
        try:
            # 獲取性能數據
            performance_data = await self._get_detailed_performance_data(guild_id, days)
            
            charts = []
            
            # 1. 回應時間趨勢 (折線圖)
            charts.append(await self._create_response_time_chart(performance_data))
            
            # 2. 系統負載分佈 (柱狀圖)
            charts.append(await self._create_load_distribution_chart(performance_data))
            
            # 3. SLA合規性圓餅圖
            charts.append(await self._create_sla_compliance_chart(performance_data))
            
            # 4. 客服工作量熱力圖
            charts.append(await self._create_workload_heatmap(performance_data))
            
            # 生成性能指標
            metrics = await self._generate_performance_metrics(performance_data)
            
            # 生成性能建議
            insights = await self._generate_performance_insights(performance_data)
            
            return DashboardData(
                title=f"性能分析儀表板 - 最近{days}天",
                charts=charts,
                metrics=metrics,
                insights=insights,
                generated_at=datetime.now(timezone.utc)
            )
            
        except Exception as e:
            logger.error(f"❌ 生成性能分析儀表板失敗: {e}")
            raise
    
    async def generate_predictive_dashboard(self, guild_id: int) -> DashboardData:
        """生成預測分析儀表板"""
        logger.info(f"生成預測分析儀表板: guild_id={guild_id}")
        
        try:
            # 獲取歷史數據進行預測
            historical_data = await self._get_historical_data_for_prediction(guild_id)
            
            charts = []
            
            # 1. 票券量預測 (面積圖)
            charts.append(await self._create_volume_prediction_chart(historical_data))
            
            # 2. 工作負載預測 (折線圖)  
            charts.append(await self._create_workload_prediction_chart(historical_data))
            
            # 3. 資源需求預測 (柱狀圖)
            charts.append(await self._create_resource_prediction_chart(historical_data))
            
            # 4. 趨勢分析散點圖
            charts.append(await self._create_trend_analysis_chart(historical_data))
            
            # 生成預測指標
            metrics = await self._generate_predictive_metrics(historical_data)
            
            # 生成預測洞察
            insights = await self._generate_predictive_insights(historical_data)
            
            return DashboardData(
                title="智能預測分析儀表板",
                charts=charts,
                metrics=metrics,
                insights=insights,
                generated_at=datetime.now(timezone.utc),
                refresh_interval=3600  # 預測儀表板每小時更新一次
            )
            
        except Exception as e:
            logger.error(f"❌ 生成預測分析儀表板失敗: {e}")
            raise
    
    # ========== 數據獲取方法 ==========
    
    async def _get_ticket_analytics(self, guild_id: int, days: int) -> Dict[str, Any]:
        """獲取票券分析數據"""
        end_date = datetime.now(timezone.utc).date()
        start_date = end_date - timedelta(days=days)
        
        try:
            # 使用現有的統計管理器
            stats = await self.stats_manager.generate_comprehensive_report(guild_id, days)
            
            # 獲取詳細的每日數據
            daily_data = await self.ticket_dao.get_daily_ticket_stats(guild_id, start_date, end_date)
            
            return {
                'overall_stats': stats.get('ticket_stats', {}),
                'daily_data': daily_data,
                'trends': await self._calculate_trends(daily_data)
            }
            
        except Exception as e:
            logger.error(f"獲取票券分析數據失敗: {e}")
            return {}
    
    async def _get_workflow_analytics(self, guild_id: int, days: int) -> Dict[str, Any]:
        """獲取工作流程分析數據"""
        try:
            # 獲取工作流程統計
            workflow_stats = await self.workflow_dao.get_guild_workflow_statistics(guild_id, days)
            
            # 獲取執行趨勢
            executions, _ = await self.workflow_dao.get_executions(days=days)
            guild_executions = [e for e in executions if self.workflow_dao.get_workflow(e['workflow_id']) and self.workflow_dao.get_workflow(e['workflow_id'])['guild_id'] == guild_id]
            
            return {
                'overall_stats': workflow_stats,
                'executions': guild_executions,
                'efficiency_metrics': await self._calculate_workflow_efficiency(guild_executions)
            }
            
        except Exception as e:
            logger.error(f"獲取工作流程分析數據失敗: {e}")
            return {}
    
    async def _get_user_engagement_analytics(self, guild_id: int, days: int) -> Dict[str, Any]:
        """獲取用戶參與度分析數據"""
        try:
            # 暫時使用模擬數據
            welcome_stats = {'total_welcomes': 50, 'auto_roles_assigned': 45}
            vote_stats = {'total_votes': 25, 'participant_count': 120}
            
            return {
                'welcome_stats': welcome_stats,
                'vote_stats': vote_stats,
                'engagement_score': await self._calculate_engagement_score(welcome_stats, vote_stats)
            }
            
        except Exception as e:
            logger.error(f"獲取用戶參與度數據失敗: {e}")
            return {}
    
    async def _get_system_performance_metrics(self, guild_id: int, days: int) -> Dict[str, Any]:
        """獲取系統性能指標"""
        try:
            # 這裡可以集成實際的系統監控數據
            # 目前使用模擬數據展示概念
            
            performance_data = {
                'avg_response_time': 1.2,  # 平均回應時間(秒)
                'system_uptime': 99.8,    # 系統正常運行時間(%)
                'memory_usage': 75.5,     # 記憶體使用率(%)
                'cpu_usage': 45.2,        # CPU使用率(%)
                'database_performance': 98.5,  # 資料庫性能分數
                'api_success_rate': 99.9,      # API成功率(%)
                'concurrent_users': 150,        # 並發用戶數
                'data_processing_speed': 95.8   # 數據處理速度分數
            }
            
            return performance_data
            
        except Exception as e:
            logger.error(f"獲取系統性能指標失敗: {e}")
            return {}
    
    # ========== 圖表生成方法 ==========
    
    async def _create_ticket_trend_chart(self, ticket_data: Dict[str, Any]) -> ChartData:
        """創建票券趨勢圖表"""
        daily_data = ticket_data.get('daily_data', [])
        
        if not daily_data:
            return ChartData(
                chart_type=ChartType.LINE,
                title="📈 票券趨勢分析",
                labels=[],
                datasets=[]
            )
        
        # 準備數據
        dates = [str(day['date']) for day in daily_data]
        created = [day.get('created_count', 0) for day in daily_data]
        closed = [day.get('closed_count', 0) for day in daily_data]
        
        datasets = [
            {
                'label': '新建票券',
                'data': created,
                'borderColor': '#3498db',
                'backgroundColor': 'rgba(52, 152, 219, 0.1)',
                'fill': True
            },
            {
                'label': '已關閉票券', 
                'data': closed,
                'borderColor': '#2ecc71',
                'backgroundColor': 'rgba(46, 204, 113, 0.1)',
                'fill': True
            }
        ]
        
        return ChartData(
            chart_type=ChartType.LINE,
            title="📈 票券趨勢分析",
            labels=dates,
            datasets=datasets,
            options={
                'responsive': True,
                'scales': {
                    'y': {'beginAtZero': True}
                }
            }
        )
    
    async def _create_response_time_chart(self, performance_data: Dict[str, Any]) -> ChartData:
        """創建回應時間趨勢圖表"""
        ticket_metrics = performance_data.get('ticket_metrics', {})
        system_metrics = performance_data.get('system_metrics', {})
        
        # 創建回應時間數據（模擬基於實際數據的時間序列）
        days_labels = []
        avg_response_times = []
        target_response_time = 120  # 2小時目標
        
        # 從系統指標獲取數據，如果沒有則使用默認值
        for i in range(7):  # 最近7天
            day = f"第{i+1}天"
            days_labels.append(day)
            
            # 基於實際票券指標計算模擬回應時間
            base_time = ticket_metrics.get('avg_resolution_time', 180)
            # 添加一些變化來模擬真實趨勢
            variation = 20 * (0.5 - (i % 3) * 0.15)
            response_time = max(30, base_time + variation - i * 5)  # 逐漸改善的趨勢
            avg_response_times.append(response_time)
        
        # 目標線數據
        target_line = [target_response_time] * len(days_labels)
        
        datasets = [
            {
                'label': '平均回應時間 (分鐘)',
                'data': avg_response_times,
                'borderColor': '#e74c3c',
                'backgroundColor': 'rgba(231, 76, 60, 0.1)',
                'fill': True,
                'tension': 0.4
            },
            {
                'label': 'SLA目標 (2小時)',
                'data': target_line,
                'borderColor': '#f39c12',
                'backgroundColor': 'transparent',
                'borderDash': [5, 5],
                'pointRadius': 0,
                'fill': False
            }
        ]
        
        return ChartData(
            chart_type=ChartType.LINE,
            title="⏱️ 回應時間趨勢分析",
            labels=days_labels,
            datasets=datasets
        )
    
    async def _create_load_distribution_chart(self, performance_data: Dict[str, Any]) -> ChartData:
        """創建系統負載分佈圖表"""
        ticket_metrics = performance_data.get('ticket_metrics', {})
        
        # 模擬系統負載數據
        hours = [f"{i:02d}:00" for i in range(0, 24, 3)]  # 每3小時一個點
        load_values = [15, 25, 35, 65, 85, 90, 70, 45]  # 模擬一天的負載變化
        
        datasets = [
            {
                'label': '系統負載 (%)',
                'data': load_values,
                'backgroundColor': [
                    '#2ecc71' if v < 50 else '#f39c12' if v < 80 else '#e74c3c'
                    for v in load_values
                ],
                'borderColor': '#34495e',
                'borderWidth': 1
            }
        ]
        
        return ChartData(
            chart_type=ChartType.BAR,
            title="📊 系統負載分佈 (24小時)",
            labels=hours,
            datasets=datasets
        )
    
    async def _create_sla_compliance_chart(self, performance_data: Dict[str, Any]) -> ChartData:
        """創建SLA合規性圓餅圖"""
        ticket_metrics = performance_data.get('ticket_metrics', {})
        resolution_rate = ticket_metrics.get('resolution_rate', 75)
        
        # SLA合規性數據
        compliant = resolution_rate
        non_compliant = 100 - resolution_rate
        
        datasets = [
            {
                'label': 'SLA合規性',
                'data': [compliant, non_compliant],
                'backgroundColor': ['#2ecc71', '#e74c3c'],
                'borderColor': ['#27ae60', '#c0392b'],
                'borderWidth': 2
            }
        ]
        
        return ChartData(
            chart_type=ChartType.PIE,
            title="🎯 SLA合規性分析",
            labels=['符合SLA', '未符合SLA'],
            datasets=datasets
        )
    
    async def _create_workload_heatmap(self, performance_data: Dict[str, Any]) -> ChartData:
        """創建客服工作量熱力圖"""
        # 模擬客服工作量數據 (7天 x 24小時)
        days = ['週一', '週二', '週三', '週四', '週五', '週六', '週日']
        hours = [f"{i}時" for i in range(0, 24, 2)]  # 每2小時一個點
        
        # 生成熱力圖數據 (模擬工作量強度 0-100)
        heatmap_data = []
        for day_idx in range(7):
            for hour_idx in range(12):
                # 工作日白天工作量較高，週末較低
                base_workload = 40 if day_idx < 5 else 20
                time_factor = 1.5 if 4 <= hour_idx <= 10 else 0.5  # 白天較忙
                workload = min(100, base_workload * time_factor + (day_idx * 5))
                heatmap_data.append(workload)
        
        # 轉換為適合圖表的格式
        datasets = [
            {
                'label': '工作量強度',
                'data': heatmap_data,
                'backgroundColor': 'rgba(231, 76, 60, 0.6)',
                'borderColor': '#e74c3c',
                'borderWidth': 1
            }
        ]
        
        # 創建標籤組合 (day-hour)
        labels = []
        for day in days:
            for hour in hours:
                labels.append(f"{day} {hour}")
        
        return ChartData(
            chart_type=ChartType.BAR,
            title="🔥 客服工作量熱力圖 (7天)",
            labels=labels[:len(heatmap_data)],  # 確保標籤數量匹配
            datasets=datasets
        )
    
    async def _create_workflow_efficiency_chart(self, workflow_data: Dict[str, Any]) -> ChartData:
        """創建工作流程效率圖表"""
        overall_stats = workflow_data.get('overall_stats', {})
        
        # 模擬工作流程效率數據
        workflow_names = ['自動歡迎', '票券指派', 'SLA監控', '報告生成', '用戶通知']
        efficiency_scores = [95.2, 87.8, 92.5, 89.3, 94.1]
        
        return ChartData(
            chart_type=ChartType.BAR,
            title="⚙️ 工作流程效率分析",
            labels=workflow_names,
            datasets=[{
                'label': '效率分數(%)',
                'data': efficiency_scores,
                'backgroundColor': [
                    '#3498db', '#e74c3c', '#f39c12', '#2ecc71', '#9b59b6'
                ]
            }],
            options={
                'responsive': True,
                'scales': {
                    'y': {
                        'beginAtZero': True,
                        'max': 100
                    }
                }
            }
        )
    
    async def _create_engagement_chart(self, engagement_data: Dict[str, Any]) -> ChartData:
        """創建用戶參與度圖表"""
        # 模擬30天的參與度數據
        days = list(range(1, 31))
        engagement_scores = [
            75 + 15 * math.sin(i * 0.2) + 5 * (i % 7) / 7 + (i % 3) * 2
            for i in days
        ]
        
        return ChartData(
            chart_type=ChartType.AREA,
            title="👥 用戶參與度趨勢",
            labels=[f"第{day}天" for day in days],
            datasets=[{
                'label': '參與度分數',
                'data': engagement_scores,
                'borderColor': '#e74c3c',
                'backgroundColor': 'rgba(231, 76, 60, 0.2)',
                'fill': True
            }],
            options={
                'responsive': True,
                'scales': {
                    'y': {
                        'beginAtZero': True,
                        'max': 100
                    }
                }
            }
        )
    
    async def _create_performance_heatmap(self, performance_data: Dict[str, Any]) -> ChartData:
        """創建系統性能熱力圖"""
        # 模擬24小時x7天的性能數據
        hours = list(range(24))
        days = ['週一', '週二', '週三', '週四', '週五', '週六', '週日']
        
        # 生成模擬的性能數據 (0-100分)
        heatmap_data = []
        for day_idx in range(7):
            day_data = []
            for hour in range(24):
                # 模擬工作時間性能較高，夜晚較低
                base_score = 80
                if 9 <= hour <= 17:  # 工作時間
                    score = base_score + (20 * (1 - abs(hour - 13) / 8))
                else:  # 非工作時間
                    score = base_score - 20 + (10 * (1 - min(hour, 24 - hour) / 6))
                
                # 添加一些隨機變動
                score += (hash(f"{day_idx}_{hour}") % 20) - 10
                score = max(0, min(100, score))
                day_data.append(round(score, 1))
            heatmap_data.append(day_data)
        
        return ChartData(
            chart_type=ChartType.HEATMAP,
            title="🔥 系統性能熱力圖 (24x7)",
            labels=hours,
            datasets=[{
                'label': '性能分數',
                'data': heatmap_data,
                'backgroundColor': lambda value: self._get_heatmap_color(value)
            }],
            options={
                'responsive': True,
                'plugins': {
                    'tooltip': {
                        'callbacks': {
                            'title': lambda context: f"{days[context[0].datasetIndex]} {context[0].label}:00",
                            'label': lambda context: f"性能分數: {context.parsed.v}"
                        }
                    }
                }
            }
        )
    
    # ========== 預測分析方法 ==========
    
    async def _create_volume_prediction_chart(self, historical_data: Dict[str, Any]) -> ChartData:
        """創建票券量預測圖表"""
        # 獲取歷史數據
        historical_volumes = historical_data.get('daily_volumes', [])
        
        if len(historical_volumes) < self._min_data_points:
            return ChartData(
                chart_type=ChartType.AREA,
                title="📊 票券量預測 (數據不足)",
                labels=[],
                datasets=[]
            )
        
        # 簡單的線性預測模型
        predicted_volumes = self._predict_linear_trend(historical_volumes, self._prediction_window)
        
        # 準備圖表數據
        historical_dates = [(datetime.now(timezone.utc) - timedelta(days=len(historical_volumes)-i-1)).strftime('%m-%d') 
                           for i in range(len(historical_volumes))]
        prediction_dates = [(datetime.now(timezone.utc) + timedelta(days=i+1)).strftime('%m-%d') 
                           for i in range(len(predicted_volumes))]
        
        all_dates = historical_dates + prediction_dates
        historical_data_extended = historical_volumes + [None] * len(predicted_volumes)
        prediction_data_extended = [None] * len(historical_volumes) + predicted_volumes
        
        return ChartData(
            chart_type=ChartType.AREA,
            title="📊 票券量預測 (30天)",
            labels=all_dates,
            datasets=[
                {
                    'label': '歷史數據',
                    'data': historical_data_extended,
                    'borderColor': '#3498db',
                    'backgroundColor': 'rgba(52, 152, 219, 0.2)',
                    'fill': True
                },
                {
                    'label': '預測數據',
                    'data': prediction_data_extended,
                    'borderColor': '#e74c3c',
                    'backgroundColor': 'rgba(231, 76, 60, 0.1)',
                    'borderDash': [5, 5],
                    'fill': True
                }
            ]
        )
    
    async def _create_workload_prediction_chart(self, historical_data: Dict[str, Any]) -> ChartData:
        """創建工作負載預測圖表"""
        # 獲取歷史工作負載數據
        historical_workload = historical_data.get('daily_workload', [])
        
        if len(historical_workload) < self._min_data_points:
            return ChartData(
                chart_type=ChartType.LINE,
                title="📈 工作負載預測 (數據不足)",
                labels=[],
                datasets=[]
            )
        
        # 預測工作負載趨勢
        predicted_workload = self._predict_linear_trend(historical_workload, self._prediction_window)
        
        # 準備圖表數據
        historical_dates = [(datetime.now(timezone.utc) - timedelta(days=len(historical_workload)-i-1)).strftime('%m-%d') 
                           for i in range(len(historical_workload))]
        prediction_dates = [(datetime.now(timezone.utc) + timedelta(days=i+1)).strftime('%m-%d') 
                           for i in range(len(predicted_workload))]
        
        all_dates = historical_dates + prediction_dates
        historical_data_extended = historical_workload + [None] * len(predicted_workload)
        prediction_data_extended = [None] * len(historical_workload) + predicted_workload
        
        # 警告閾值線
        warning_threshold = max(historical_workload) * 0.8 if historical_workload else 80
        threshold_line = [warning_threshold] * len(all_dates)
        
        return ChartData(
            chart_type=ChartType.LINE,
            title="📈 工作負載預測 (30天)",
            labels=all_dates,
            datasets=[
                {
                    'label': '歷史工作負載',
                    'data': historical_data_extended,
                    'borderColor': '#2ecc71',
                    'backgroundColor': 'rgba(46, 204, 113, 0.1)',
                    'fill': True,
                    'tension': 0.4
                },
                {
                    'label': '預測工作負載',
                    'data': prediction_data_extended,
                    'borderColor': '#f39c12',
                    'backgroundColor': 'rgba(243, 156, 18, 0.1)',
                    'borderDash': [5, 5],
                    'fill': True,
                    'tension': 0.4
                },
                {
                    'label': '警告閾值',
                    'data': threshold_line,
                    'borderColor': '#e74c3c',
                    'backgroundColor': 'transparent',
                    'borderDash': [10, 5],
                    'pointRadius': 0,
                    'fill': False
                }
            ]
        )
    
    async def _create_resource_prediction_chart(self, historical_data: Dict[str, Any]) -> ChartData:
        """創建資源需求預測圖表"""
        # 模擬資源需求預測數據
        resource_types = ['CPU使用率', '記憶體使用率', '網路頻寬', '儲存空間', '資料庫連線']
        current_usage = [65, 72, 45, 58, 80]  # 當前使用率
        predicted_usage = [75, 85, 55, 68, 90]  # 預測使用率 (30天後)
        
        # 計算變化趨勢
        trend_colors = []
        for current, predicted in zip(current_usage, predicted_usage):
            if predicted > current * 1.2:  # 增長超過20%
                trend_colors.append('#e74c3c')  # 紅色 - 需要關注
            elif predicted > current * 1.1:  # 增長超過10%
                trend_colors.append('#f39c12')  # 橙色 - 需要監控
            else:
                trend_colors.append('#2ecc71')  # 綠色 - 正常
        
        return ChartData(
            chart_type=ChartType.BAR,
            title="📊 資源需求預測 (30天)",
            labels=resource_types,
            datasets=[
                {
                    'label': '當前使用率 (%)',
                    'data': current_usage,
                    'backgroundColor': 'rgba(52, 152, 219, 0.7)',
                    'borderColor': '#3498db',
                    'borderWidth': 1
                },
                {
                    'label': '預測使用率 (%)',
                    'data': predicted_usage,
                    'backgroundColor': trend_colors,
                    'borderColor': trend_colors,
                    'borderWidth': 1
                }
            ]
        )
    
    async def _create_trend_analysis_chart(self, historical_data: Dict[str, Any]) -> ChartData:
        """創建趨勢分析散點圖"""
        # 模擬趨勢分析數據 (票券創建時間 vs 解決時間)
        ticket_counts = []
        resolution_times = []
        colors = []
        
        # 生成30天的模擬數據
        for day in range(30):
            # 模擬每日票券數量和平均解決時間的關係
            daily_tickets = 10 + (day % 7) * 5 + (day // 10) * 2  # 週期性變化
            avg_resolution = 120 + daily_tickets * 2 - (day * 0.5)  # 隨時間改善
            
            ticket_counts.append(daily_tickets)
            resolution_times.append(max(30, avg_resolution))  # 最少30分鐘
            
            # 根據效率着色
            if avg_resolution < 90:  # 很快
                colors.append('rgba(46, 204, 113, 0.7)')
            elif avg_resolution < 150:  # 一般
                colors.append('rgba(52, 152, 219, 0.7)')
            else:  # 較慢
                colors.append('rgba(231, 76, 60, 0.7)')
        
        # 創建散點數據
        scatter_data = []
        for i in range(len(ticket_counts)):
            scatter_data.append({
                'x': ticket_counts[i],
                'y': resolution_times[i]
            })
        
        return ChartData(
            chart_type=ChartType.SCATTER,
            title="🔍 趨勢分析：票券量 vs 解決時間",
            labels=[''],  # 散點圖不需要標籤
            datasets=[
                {
                    'label': '票券處理效率',
                    'data': scatter_data,
                    'backgroundColor': colors,
                    'borderColor': colors,
                    'borderWidth': 2,
                    'pointRadius': 6
                }
            ]
        )
    
    # ========== 輔助方法 ==========
    
    def _predict_linear_trend(self, data: List[float], prediction_days: int) -> List[float]:
        """簡單的線性趨勢預測"""
        if len(data) < 2:
            return [data[-1]] * prediction_days if data else [0] * prediction_days
        
        # 計算線性回歸
        n = len(data)
        x = list(range(n))
        y = data
        
        # 計算斜率和截距
        sum_x = sum(x)
        sum_y = sum(y)
        sum_xy = sum(x[i] * y[i] for i in range(n))
        sum_x2 = sum(x[i] ** 2 for i in range(n))
        
        slope = (n * sum_xy - sum_x * sum_y) / (n * sum_x2 - sum_x ** 2)
        intercept = (sum_y - slope * sum_x) / n
        
        # 生成預測
        predictions = []
        for i in range(prediction_days):
            predicted_value = slope * (n + i) + intercept
            # 確保預測值不為負數
            predictions.append(max(0, round(predicted_value, 1)))
        
        return predictions
    
    def _get_heatmap_color(self, value: float) -> str:
        """根據數值獲取熱力圖顏色"""
        if value >= 90:
            return '#2ecc71'  # 綠色 - 優秀
        elif value >= 70:
            return '#f39c12'  # 橙色 - 良好
        elif value >= 50:
            return '#e67e22'  # 深橙 - 一般
        else:
            return '#e74c3c'  # 紅色 - 需改善
    
    async def _generate_key_metrics(self, guild_id: int, days: int) -> Dict[str, MetricSummary]:
        """生成關鍵指標摘要"""
        try:
            # 獲取當前期間和前一期間的數據進行比較
            current_stats = await self.stats_manager.generate_comprehensive_report(guild_id, days)
            previous_stats = await self.stats_manager.generate_comprehensive_report(guild_id, days)
            
            metrics = {}
            
            # 票券處理效率
            current_tickets = current_stats.get('ticket_stats', {}).get('total_tickets', 0)
            previous_tickets = previous_stats.get('ticket_stats', {}).get('total_tickets', 0)
            
            metrics['ticket_efficiency'] = MetricSummary(
                current_value=current_tickets,
                previous_value=previous_tickets,
                change_percentage=self._calculate_change_percentage(current_tickets, previous_tickets),
                trend=self._determine_trend(current_tickets, previous_tickets),
                status=self._determine_status('tickets', current_tickets, previous_tickets)
            )
            
            # 平均回應時間 (模擬數據)
            current_response_time = 1.2
            previous_response_time = 1.5
            
            metrics['response_time'] = MetricSummary(
                current_value=current_response_time,
                previous_value=previous_response_time,
                change_percentage=self._calculate_change_percentage(current_response_time, previous_response_time),
                trend=self._determine_trend(previous_response_time, current_response_time),  # 反向，越低越好
                status='good' if current_response_time < 2.0 else 'warning'
            )
            
            # 用戶滿意度 (模擬數據)
            current_satisfaction = 4.2
            previous_satisfaction = 4.0
            
            metrics['satisfaction'] = MetricSummary(
                current_value=current_satisfaction,
                previous_value=previous_satisfaction,
                change_percentage=self._calculate_change_percentage(current_satisfaction, previous_satisfaction),
                trend=self._determine_trend(current_satisfaction, previous_satisfaction),
                status='good' if current_satisfaction >= 4.0 else 'warning'
            )
            
            return metrics
            
        except Exception as e:
            logger.error(f"生成關鍵指標失敗: {e}")
            return {}
    
    async def _generate_insights(self, ticket_data: Dict[str, Any], workflow_data: Dict[str, Any], 
                               engagement_data: Dict[str, Any]) -> List[str]:
        """生成智能洞察"""
        insights = []
        
        try:
            # 分析票券趨勢
            daily_data = ticket_data.get('daily_data', [])
            if daily_data:
                recent_avg = sum(day.get('created_count', 0) for day in daily_data[-7:]) / 7
                overall_avg = sum(day.get('created_count', 0) for day in daily_data) / len(daily_data)
                
                if recent_avg > overall_avg * 1.2:
                    insights.append("📈 最近7天的票券量比平均水準高20%，建議增加客服人力")
                elif recent_avg < overall_avg * 0.8:
                    insights.append("📉 最近7天票券量下降，系統運行平穩或用戶問題減少")
            
            # 分析工作流程效率
            workflow_stats = workflow_data.get('overall_stats', {})
            if workflow_stats.get('total_workflows', 0) > 0:
                success_rate = workflow_stats.get('success_rate', 0)
                if success_rate >= 95:
                    insights.append("🎯 工作流程自動化效率優秀，成功率超過95%")
                elif success_rate < 80:
                    insights.append("⚠️ 工作流程成功率較低，建議檢查自動化規則設定")
            
            # 分析用戶參與度
            engagement_score = engagement_data.get('engagement_score', 0)
            if engagement_score >= 80:
                insights.append("👥 社群參與度很高，用戶活躍度良好")
            elif engagement_score < 60:
                insights.append("📢 建議加強社群互動活動，提升用戶參與度")
            
            # 添加一些通用建議
            if len(insights) == 0:
                insights.append("📊 系統運行狀態良好，各項指標正常")
            
            insights.append("💡 建議定期檢查儀表板數據，及時調整運營策略")
            
            return insights
            
        except Exception as e:
            logger.error(f"生成智能洞察失敗: {e}")
            return ["❌ 智能洞察生成失敗，請檢查數據完整性"]
    
    def _calculate_change_percentage(self, current: float, previous: float) -> float:
        """計算變化百分比"""
        if previous == 0:
            return 100.0 if current > 0 else 0.0
        return round(((current - previous) / previous) * 100, 1)
    
    def _determine_trend(self, current: float, previous: float) -> str:
        """確定趨勢方向"""
        if current > previous * 1.05:  # 增長超過5%
            return "up"
        elif current < previous * 0.95:  # 下降超過5%
            return "down"
        else:
            return "stable"
    
    def _determine_status(self, metric_type: str, current: float, previous: float) -> str:
        """確定指標狀態"""
        change_rate = abs((current - previous) / previous) if previous > 0 else 0
        
        if metric_type == 'tickets':
            if change_rate < 0.1:  # 變化小於10%
                return 'good'
            elif change_rate < 0.3:  # 變化小於30%
                return 'warning'
            else:
                return 'critical'
        
        return 'good'  # 默認狀態
    
    def _determine_performance_status(self, metric_key: str, current_value: float) -> str:
        """根據性能指標確定狀態"""
        status_thresholds = {
            # 票券相關指標 (越低越好)
            'avg_resolution_time': {'good': 2.0, 'warning': 4.0},  # 小時
            'first_response_time': {'good': 10.0, 'warning': 30.0},  # 分鐘
            
            # 成功率類指標 (越高越好) 
            'resolution_rate': {'critical': 70.0, 'warning': 85.0},  # %
            'workflow_success_rate': {'critical': 80.0, 'warning': 90.0},  # %
            'system_uptime': {'critical': 95.0, 'warning': 98.0},  # %
            'automation_coverage': {'critical': 50.0, 'warning': 70.0},  # %
            
            # 滿意度類指標
            'customer_satisfaction': {'critical': 3.0, 'warning': 4.0},  # 1-5分
            
            # 系統性能指標
            'response_latency': {'good': 100.0, 'warning': 300.0},  # ms
            'error_rate': {'good': 0.5, 'warning': 2.0},  # %
            'avg_workflow_time': {'good': 20.0, 'warning': 60.0},  # 秒
        }
        
        thresholds = status_thresholds.get(metric_key, {})
        if not thresholds:
            return 'good'  # 默認狀態
        
        # 對於"越低越好"的指標
        if metric_key in ['avg_resolution_time', 'first_response_time', 'response_latency', 'error_rate', 'avg_workflow_time']:
            if current_value <= thresholds.get('good', float('inf')):
                return 'good'
            elif current_value <= thresholds.get('warning', float('inf')):
                return 'warning'
            else:
                return 'critical'
        
        # 對於"越高越好"的指標
        else:
            if current_value >= thresholds.get('warning', 0):
                return 'good'
            elif current_value >= thresholds.get('critical', 0):
                return 'warning'
            else:
                return 'critical'
    
    async def _calculate_engagement_score(self, welcome_stats: Dict[str, Any], vote_stats: Dict[str, Any]) -> float:
        """計算用戶參與度分數"""
        try:
            # 基於歡迎和投票數據計算參與度
            welcome_score = min(welcome_stats.get('total_welcomes', 0) / 10, 50)  # 最多50分
            vote_score = min(vote_stats.get('total_votes', 0) / 5, 30)  # 最多30分
            participant_score = min(vote_stats.get('participant_count', 0) / 20, 20)  # 最多20分
            
            total_score = welcome_score + vote_score + participant_score
            return min(total_score, 100)  # 最多100分
            
        except Exception as e:
            logger.error(f"計算參與度分數失敗: {e}")
            return 75.0  # 默認分數
    
    async def _calculate_trends(self, daily_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """計算數據趨勢"""
        try:
            if len(daily_data) < 7:
                return {'trend': 'insufficient_data', 'direction': 'stable'}
            
            # 取最近7天和前7天的數據進行比較
            recent_values = [day.get('created_count', 0) for day in daily_data[-7:]]
            previous_values = [day.get('created_count', 0) for day in daily_data[-14:-7]] if len(daily_data) >= 14 else recent_values
            
            recent_avg = sum(recent_values) / len(recent_values)
            previous_avg = sum(previous_values) / len(previous_values)
            
            if recent_avg > previous_avg * 1.1:
                direction = 'increasing'
            elif recent_avg < previous_avg * 0.9:
                direction = 'decreasing'
            else:
                direction = 'stable'
            
            change_rate = ((recent_avg - previous_avg) / previous_avg * 100) if previous_avg > 0 else 0
            
            return {
                'trend': 'calculated',
                'direction': direction,
                'recent_average': round(recent_avg, 2),
                'previous_average': round(previous_avg, 2),
                'change_rate': round(change_rate, 2)
            }
            
        except Exception as e:
            logger.error(f"計算趨勢失敗: {e}")
            return {'trend': 'error', 'direction': 'stable'}
    
    async def _calculate_workflow_efficiency(self, executions: List[Dict[str, Any]]) -> Dict[str, Any]:
        """計算工作流程效率"""
        try:
            if not executions:
                return {'efficiency_score': 0, 'success_rate': 0, 'avg_execution_time': 0}
            
            successful_executions = [e for e in executions if e.get('status') == 'completed']
            failed_executions = [e for e in executions if e.get('status') == 'failed']
            
            success_rate = (len(successful_executions) / len(executions)) * 100
            
            # 計算平均執行時間
            execution_times = []
            for execution in successful_executions:
                if execution.get('execution_time'):
                    execution_times.append(execution['execution_time'])
            
            avg_execution_time = sum(execution_times) / len(execution_times) if execution_times else 0
            
            # 效率分數 (基於成功率和執行時間)
            efficiency_score = success_rate * 0.7 + max(0, (100 - avg_execution_time)) * 0.3
            
            return {
                'efficiency_score': round(efficiency_score, 2),
                'success_rate': round(success_rate, 2),
                'avg_execution_time': round(avg_execution_time, 2),
                'total_executions': len(executions),
                'successful_executions': len(successful_executions),
                'failed_executions': len(failed_executions)
            }
            
        except Exception as e:
            logger.error(f"計算工作流程效率失敗: {e}")
            return {'efficiency_score': 0, 'success_rate': 0, 'avg_execution_time': 0}
    
    async def _get_detailed_performance_data(self, guild_id: int, days: int) -> Dict[str, Any]:
        """獲取詳細性能數據"""
        try:
            # 獲取票券性能指標
            ticket_metrics = await self.ticket_dao.get_ticket_performance_metrics(guild_id, days)
            
            # 獲取工作流程性能
            workflow_stats = await self.workflow_dao.get_guild_workflow_statistics(guild_id, days)
            
            # 整合性能數據
            performance_data = {
                'ticket_metrics': ticket_metrics,
                'workflow_stats': workflow_stats,
                'system_metrics': await self._get_system_performance_metrics(guild_id, days)
            }
            
            return performance_data
            
        except Exception as e:
            logger.error(f"獲取詳細性能數據失敗: {e}")
            return {}
    
    async def _get_historical_data_for_prediction(self, guild_id: int) -> Dict[str, Any]:
        """獲取用於預測的歷史數據"""
        try:
            # 獲取60天的歷史數據用於預測
            end_date = datetime.now(timezone.utc).date()
            start_date = end_date - timedelta(days=60)
            
            daily_stats = await self.ticket_dao.get_daily_ticket_stats(guild_id, start_date, end_date)
            
            # 提取票券量數據
            daily_volumes = [stats.get('created_count', 0) for stats in daily_stats]
            
            return {
                'daily_volumes': daily_volumes,
                'date_range': {'start': start_date, 'end': end_date},
                'data_quality': 'good' if len(daily_volumes) >= 30 else 'limited'
            }
            
        except Exception as e:
            logger.error(f"獲取歷史預測數據失敗: {e}")
            return {'daily_volumes': [], 'data_quality': 'poor'}
    
    async def _generate_predictive_metrics(self, historical_data: Dict[str, Any]) -> Dict[str, MetricSummary]:
        """生成預測指標 (返回 MetricSummary 對象)"""
        try:
            daily_volumes = historical_data.get('daily_volumes', [])
            
            if not daily_volumes:
                return {
                    'prediction_confidence': MetricSummary(
                        current_value=0.0,
                        previous_value=0.0, 
                        change_percentage=0.0,
                        trend='stable',
                        status='warning'
                    ),
                    'forecasted_trend': MetricSummary(
                        current_value=0.0,
                        previous_value=0.0,
                        change_percentage=0.0,
                        trend='stable', 
                        status='warning'
                    )
                }
            
            # 計算趨勢方向
            recent_avg = sum(daily_volumes[-7:]) / min(7, len(daily_volumes)) if daily_volumes else 0
            overall_avg = sum(daily_volumes) / len(daily_volumes) if daily_volumes else 0
            
            if recent_avg > overall_avg * 1.15:
                trend_direction = 'up'
                forecasted_growth = ((recent_avg - overall_avg) / overall_avg) * 100
                status = 'warning'  # 可能需要關注
            elif recent_avg > overall_avg * 1.05:
                trend_direction = 'up'
                forecasted_growth = ((recent_avg - overall_avg) / overall_avg) * 100
                status = 'good'
            elif recent_avg < overall_avg * 0.85:
                trend_direction = 'down'
                forecasted_growth = ((recent_avg - overall_avg) / overall_avg) * 100
                status = 'good'  # 下降可能是好事
            elif recent_avg < overall_avg * 0.95:
                trend_direction = 'down'
                forecasted_growth = ((recent_avg - overall_avg) / overall_avg) * 100
                status = 'good'
            else:
                trend_direction = 'stable'
                forecasted_growth = 0.0
                status = 'good'
            
            # 計算預測信心度
            data_variance = self._calculate_variance(daily_volumes)
            data_consistency = 1.0 / (1.0 + data_variance) if data_variance > 0 else 1.0
            data_completeness = len(daily_volumes) / 60.0  # 基於60天完整度
            prediction_confidence = min(data_consistency * data_completeness, 1.0)
            
            # 評估信心度狀態
            if prediction_confidence >= 0.8:
                confidence_status = 'good'
            elif prediction_confidence >= 0.5:
                confidence_status = 'warning'
            else:
                confidence_status = 'critical'
            
            return {
                'prediction_confidence': MetricSummary(
                    current_value=round(prediction_confidence * 100, 1),
                    previous_value=50.0,  # 基準值
                    change_percentage=round((prediction_confidence - 0.5) * 200, 1),
                    trend='up' if prediction_confidence > 0.5 else 'down',
                    status=confidence_status
                ),
                'forecasted_trend': MetricSummary(
                    current_value=round(recent_avg, 1),
                    previous_value=round(overall_avg, 1),
                    change_percentage=round(forecasted_growth, 1),
                    trend=trend_direction,
                    status=status
                )
            }
            
        except Exception as e:
            logger.error(f"生成預測指標失敗: {e}")
            return {
                'prediction_confidence': MetricSummary(
                    current_value=0.0,
                    previous_value=0.0,
                    change_percentage=0.0,
                    trend='stable',
                    status='critical'
                ),
                'forecasted_trend': MetricSummary(
                    current_value=0.0,
                    previous_value=0.0,
                    change_percentage=0.0,
                    trend='stable',
                    status='critical'
                )
            }
    
    async def _generate_predictive_insights(self, historical_data: Dict[str, Any]) -> List[str]:
        """生成預測洞察"""
        try:
            insights = []
            daily_volumes = historical_data.get('daily_volumes', [])
            
            if not daily_volumes:
                insights.append("📊 數據不足：無法生成可靠的預測分析")
                return insights
            
            # 生成基於數據的洞察
            recent_avg = sum(daily_volumes[-7:]) / min(7, len(daily_volumes))
            overall_avg = sum(daily_volumes) / len(daily_volumes)
            max_volume = max(daily_volumes) if daily_volumes else 0
            min_volume = min(daily_volumes) if daily_volumes else 0
            
            # 趨勢洞察
            if recent_avg > overall_avg * 1.15:
                insights.append("📈 強烈上升趨勢：最近一週的票券量比平均值高15%以上，建議增加人力配置")
            elif recent_avg > overall_avg * 1.05:
                insights.append("📊 輕微上升趨勢：票券量呈現溫和增長，請密切關注資源需求")
            elif recent_avg < overall_avg * 0.85:
                insights.append("📉 強烈下降趨勢：票券量顯著減少，可考慮調整服務策略")
            elif recent_avg < overall_avg * 0.95:
                insights.append("📊 輕微下降趨勢：票券量略有下降，可能是積極的改善信號")
            else:
                insights.append("➡️ 穩定狀態：票券量保持相對穩定，系統運作良好")
            
            # 容量洞察
            volume_range = max_volume - min_volume
            if volume_range > overall_avg * 2:
                insights.append("⚠️ 高波動性：票券量波動較大，建議建立彈性處理機制")
            
            # 預測建議
            predicted_volume = self._predict_linear_trend(daily_volumes, 7)
            if predicted_volume and len(predicted_volume) > 0:
                next_week_avg = sum(predicted_volume) / len(predicted_volume)
                if next_week_avg > overall_avg * 1.2:
                    insights.append("🚨 預警：預測下週票券量可能大幅增加，建議提前準備")
                elif next_week_avg > overall_avg * 1.1:
                    insights.append("⚡ 準備：預測票券量將略有增加，建議適度調整資源")
            
            # 數據品質洞察
            data_quality = historical_data.get('data_quality', 'unknown')
            if data_quality == 'limited':
                insights.append("📋 數據提醒：歷史數據有限，預測準確性可能受到影響")
            elif data_quality == 'poor':
                insights.append("⚠️ 數據警告：數據品質不佳，建議改善數據收集機制")
            
            return insights[:5]  # 限制最多5個洞察
            
        except Exception as e:
            logger.error(f"生成預測洞察失敗: {e}")
            return ["❌ 洞察生成失敗，請檢查數據完整性"]
    
    def _calculate_variance(self, data: List[float]) -> float:
        """計算數據變異數"""
        if len(data) < 2:
            return 0.0
        
        mean = sum(data) / len(data)
        variance = sum((x - mean) ** 2 for x in data) / len(data)
        return variance
    
    # ========== 快取管理 ==========
    
    async def clear_dashboard_cache(self, cache_key: Optional[str] = None):
        """清除儀表板快取"""
        if cache_key:
            if cache_key in self._dashboard_cache:
                del self._dashboard_cache[cache_key]
                logger.info(f"已清除儀表板快取: {cache_key}")
        else:
            self._dashboard_cache.clear()
            logger.info("已清除所有儀表板快取")
    
    async def get_dashboard_cache_info(self) -> Dict[str, Any]:
        """獲取快取資訊"""
        return {
            'cache_count': len(self._dashboard_cache),
            'cache_keys': list(self._dashboard_cache.keys()),
            'cache_ttl': self._cache_ttl,
            'memory_usage': sum(len(str(dashboard)) for dashboard in self._dashboard_cache.values())
        }
    
    async def _generate_performance_metrics(self, performance_data: Dict[str, Any]) -> Dict[str, MetricSummary]:
        """生成性能指標"""
        try:
            ticket_metrics = performance_data.get('ticket_metrics', {})
            system_metrics = performance_data.get('system_metrics', {})
            workflow_metrics = performance_data.get('workflow_metrics', {})
            
            # 計算關鍵性能指標的原始值
            raw_metrics = {
                # 票券相關指標
                'avg_resolution_time': ticket_metrics.get('avg_resolution_hours', 2.5),
                'resolution_rate': ticket_metrics.get('resolution_rate', 85.0),
                'customer_satisfaction': ticket_metrics.get('satisfaction_score', 4.2),
                'first_response_time': ticket_metrics.get('avg_first_response_minutes', 15.0),
                
                # 系統性能指標
                'system_uptime': system_metrics.get('uptime_percentage', 99.5),
                'response_latency': system_metrics.get('avg_response_ms', 150.0),
                'error_rate': system_metrics.get('error_rate', 0.1),
                
                # 工作流程效率指標
                'workflow_success_rate': workflow_metrics.get('success_rate', 95.0),
                'avg_workflow_time': workflow_metrics.get('avg_execution_time', 30.0),
                'automation_coverage': workflow_metrics.get('automation_rate', 75.0),
            }
            
            # 模擬前一期間的數據（實際應該從歷史數據中獲取）
            previous_metrics = {
                'avg_resolution_time': raw_metrics['avg_resolution_time'] * 1.1,
                'resolution_rate': raw_metrics['resolution_rate'] * 0.95,
                'customer_satisfaction': raw_metrics['customer_satisfaction'] * 0.98,
                'first_response_time': raw_metrics['first_response_time'] * 1.2,
                'system_uptime': raw_metrics['system_uptime'] * 0.995,
                'response_latency': raw_metrics['response_latency'] * 1.1,
                'error_rate': raw_metrics['error_rate'] * 0.8,
                'workflow_success_rate': raw_metrics['workflow_success_rate'] * 0.96,
                'avg_workflow_time': raw_metrics['avg_workflow_time'] * 1.05,
                'automation_coverage': raw_metrics['automation_coverage'] * 0.95,
            }
            
            # 轉換為 MetricSummary 對象
            metrics = {}
            for key, current_value in raw_metrics.items():
                previous_value = previous_metrics.get(key, current_value)
                
                # 計算變化百分比
                change_percentage = self._calculate_change_percentage(current_value, previous_value)
                
                # 確定趨勢（對於某些指標，越低越好）
                reverse_trend_metrics = {'avg_resolution_time', 'response_latency', 'error_rate', 'first_response_time', 'avg_workflow_time'}
                if key in reverse_trend_metrics:
                    trend = self._determine_trend(previous_value, current_value)  # 反向趨勢
                else:
                    trend = self._determine_trend(current_value, previous_value)
                
                # 確定狀態
                status = self._determine_performance_status(key, current_value)
                
                metrics[key] = MetricSummary(
                    current_value=current_value,
                    previous_value=previous_value,
                    change_percentage=change_percentage,
                    trend=trend,
                    status=status
                )
            
            # 計算綜合性能評分
            score_components = [
                min(100, max(0, 100 - (raw_metrics['avg_resolution_time'] - 2) * 10)),
                raw_metrics['resolution_rate'],
                raw_metrics['customer_satisfaction'] * 20,  # 轉換為百分比
                raw_metrics['system_uptime'],
                min(100, max(0, 100 - raw_metrics['response_latency'] / 10)),
                raw_metrics['workflow_success_rate'],
            ]
            
            overall_score = sum(score_components) / len(score_components)
            previous_overall_score = overall_score * 0.95  # 模擬前一期間數據
            
            metrics['overall_performance_score'] = MetricSummary(
                current_value=overall_score,
                previous_value=previous_overall_score,
                change_percentage=self._calculate_change_percentage(overall_score, previous_overall_score),
                trend=self._determine_trend(overall_score, previous_overall_score),
                status='good' if overall_score >= 80 else 'warning' if overall_score >= 60 else 'critical'
            )
            
            return metrics
            
        except Exception as e:
            logger.error(f"生成性能指標失敗: {e}")
            return {
                'avg_resolution_time': 0,
                'resolution_rate': 0,
                'customer_satisfaction': 0,
                'first_response_time': 0,
                'system_uptime': 0,
                'response_latency': 0,
                'error_rate': 0,
                'workflow_success_rate': 0,
                'avg_workflow_time': 0,
                'automation_coverage': 0,
                'overall_performance_score': 0
            }
    
    async def _generate_performance_insights(self, performance_data: Dict[str, Any]) -> List[str]:
        """生成性能洞察建議"""
        try:
            insights = []
            ticket_metrics = performance_data.get('ticket_metrics', {})
            system_metrics = performance_data.get('system_metrics', {})
            workflow_metrics = performance_data.get('workflow_metrics', {})
            
            # 票券處理建議
            resolution_rate = ticket_metrics.get('resolution_rate', 0)
            if resolution_rate < 80:
                insights.append("⚠️ 票券解決率偏低，建議檢查處理流程和客服培訓")
            elif resolution_rate > 95:
                insights.append("✅ 票券解決率表現優秀，維持當前服務品質")
            
            avg_resolution_time = ticket_metrics.get('avg_resolution_hours', 0)
            if avg_resolution_time > 4:
                insights.append("⏱️ 平均解決時間較長，建議優化工作流程或增加人力")
            elif avg_resolution_time < 1:
                insights.append("🚀 回應時間優秀，客戶體驗良好")
            
            # 系統性能建議
            uptime = system_metrics.get('uptime_percentage', 99.5)
            if uptime < 99:
                insights.append("🔧 系統正常運行時間需要改善，建議檢查基礎設施")
            elif uptime > 99.9:
                insights.append("💪 系統穩定性極佳，基礎設施運行良好")
            
            response_latency = system_metrics.get('avg_response_ms', 150)
            if response_latency > 300:
                insights.append("📡 系統回應延遲較高，建議優化網路或伺服器配置")
            elif response_latency < 100:
                insights.append("⚡ 系統回應速度優秀，用戶體驗良好")
            
            # 工作流程建議
            success_rate = workflow_metrics.get('success_rate', 95)
            if success_rate < 90:
                insights.append("🔄 工作流程成功率需要改善，建議檢查自動化邏輯")
            elif success_rate > 98:
                insights.append("🎯 工作流程運行穩定，自動化效果優秀")
            
            automation_rate = workflow_metrics.get('automation_rate', 75)
            if automation_rate < 50:
                insights.append("🤖 自動化覆蓋率較低，建議增加更多自動化流程")
            elif automation_rate > 90:
                insights.append("🏆 自動化程度很高，有效提升工作效率")
            
            # 如果沒有特別的建議，提供通用建議
            if not insights:
                insights.append("📊 系統整體運行正常，持續監控各項指標")
                insights.append("💡 建議定期檢視性能趨勢，持續優化服務品質")
            
            return insights[:5]  # 最多返回5條建議
            
        except Exception as e:
            logger.error(f"生成性能洞察失敗: {e}")
            return ["❌ 無法生成性能建議，請檢查系統狀態"]

# 全域儀表板管理器實例
dashboard_manager = DashboardManager()