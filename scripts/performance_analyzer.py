#!/usr/bin/env python3
"""
CI/CD 效能分析工具
分析 GitHub Actions workflow 執行時間和瓶頸
"""

import os
import sys
import json
import requests
from datetime import datetime, timedelta
import argparse
import statistics
from typing import List, Dict, Any

class CICDPerformanceAnalyzer:
    def __init__(self, repo: str = "Craig-0219/potato", token: str = None):
        self.repo = repo
        self.token = token or os.environ.get('GITHUB_TOKEN')
        self.headers = {
            'Authorization': f'token {self.token}' if self.token else '',
            'Accept': 'application/vnd.github.v3+json'
        }
        self.workflows_of_interest = [
            "🧪 Test Coverage & Quality",
            "🔍 Code Quality Checks", 
            "🔒 Security Scans",
            "⚡ Optimized CI Pipeline",
            "🚀 Lightweight CI"
        ]
    
    def fetch_workflow_runs(self, days: int = 7, limit: int = 50) -> List[Dict[str, Any]]:
        """獲取 workflow 執行數據"""
        if not self.token:
            print("❌ 需要 GITHUB_TOKEN 環境變數")
            return []
        
        url = f'https://api.github.com/repos/{self.repo}/actions/runs'
        params = {
            'per_page': limit,
            'branch': 'dev',
            'status': 'completed'
        }
        
        try:
            response = requests.get(url, headers=self.headers, params=params)
            response.raise_for_status()
            
            runs_data = response.json()
            metrics = []
            cutoff_date = datetime.now() - timedelta(days=days)
            
            for run in runs_data.get('workflow_runs', []):
                created_at = datetime.fromisoformat(run['created_at'].replace('Z', '+00:00'))
                
                # 只分析最近指定天數的數據
                if created_at < cutoff_date:
                    continue
                
                updated_at = datetime.fromisoformat(run['updated_at'].replace('Z', '+00:00'))
                duration_seconds = (updated_at - created_at).total_seconds()
                
                metrics.append({
                    'workflow_name': run['name'],
                    'run_id': run['id'],
                    'status': run['conclusion'],
                    'branch': run['head_branch'],
                    'duration_seconds': duration_seconds,
                    'duration_minutes': round(duration_seconds / 60, 2),
                    'created_at': run['created_at'],
                    'trigger_event': run['event'],
                    'attempt': run['run_attempt']
                })
            
            return metrics
            
        except Exception as e:
            print(f"❌ API 請求失敗: {e}")
            return []
    
    def analyze_by_workflow(self, metrics: List[Dict[str, Any]]) -> Dict[str, Dict[str, float]]:
        """按 workflow 分析效能"""
        workflow_data = {}
        
        for metric in metrics:
            name = metric['workflow_name']
            duration = metric['duration_minutes']
            
            if name not in workflow_data:
                workflow_data[name] = []
            workflow_data[name].append(duration)
        
        # 計算統計數據
        analysis = {}
        for name, durations in workflow_data.items():
            if durations:
                analysis[name] = {
                    'count': len(durations),
                    'mean': statistics.mean(durations),
                    'median': statistics.median(durations),
                    'max': max(durations),
                    'min': min(durations),
                    'stdev': statistics.stdev(durations) if len(durations) > 1 else 0
                }
        
        return analysis
    
    def calculate_success_rates(self, metrics: List[Dict[str, Any]]) -> Dict[str, float]:
        """計算成功率"""
        workflow_results = {}
        
        for metric in metrics:
            name = metric['workflow_name']
            status = metric['status']
            
            if name not in workflow_results:
                workflow_results[name] = {'total': 0, 'success': 0}
            
            workflow_results[name]['total'] += 1
            if status == 'success':
                workflow_results[name]['success'] += 1
        
        success_rates = {}
        for name, results in workflow_results.items():
            success_rates[name] = (results['success'] / results['total']) * 100 if results['total'] > 0 else 0
        
        return success_rates
    
    def identify_bottlenecks(self, analysis: Dict[str, Dict[str, float]]) -> List[Dict[str, Any]]:
        """識別效能瓶頸"""
        bottlenecks = []
        
        # 按平均執行時間排序
        sorted_workflows = sorted(analysis.items(), key=lambda x: x[1]['mean'], reverse=True)
        
        for i, (name, stats) in enumerate(sorted_workflows[:3], 1):
            improvement_potential = max(0, stats['mean'] - 5.0)  # 目標 5 分鐘
            
            bottlenecks.append({
                'rank': i,
                'workflow': name,
                'avg_duration': stats['mean'],
                'max_duration': stats['max'],
                'execution_count': stats['count'],
                'improvement_potential': improvement_potential,
                'variability': stats['stdev']
            })
        
        return bottlenecks
    
    def generate_optimization_suggestions(self, bottlenecks: List[Dict[str, Any]], 
                                        success_rates: Dict[str, float]) -> List[str]:
        """生成優化建議"""
        suggestions = []
        
        # 基於瓶頸的建議
        total_potential = sum(b['improvement_potential'] for b in bottlenecks)
        if total_potential > 0:
            suggestions.append(f"🎯 優化前 3 大瓶頸可節省 {total_potential:.1f} 分鐘執行時間")
        
        # 基於執行時間的建議
        for b in bottlenecks:
            if b['avg_duration'] > 10:
                suggestions.append(f"⚡ {b['workflow']} 平均執行時間過長 ({b['avg_duration']:.1f}分鐘)，建議:")
                suggestions.append(f"  - 實作智能跳過機制")
                suggestions.append(f"  - 優化依賴安裝快取")
                suggestions.append(f"  - 並行化測試執行")
            
            if b['variability'] > 2:
                suggestions.append(f"📊 {b['workflow']} 執行時間變異大 (±{b['variability']:.1f}分鐘)，需要穩定性優化")
        
        # 基於成功率的建議
        failing_workflows = [name for name, rate in success_rates.items() if rate < 95]
        if failing_workflows:
            suggestions.append(f"🔧 改善失敗率較高的 workflows: {', '.join(failing_workflows)}")
        
        # 通用建議
        suggestions.extend([
            "💡 通用優化策略:",
            "  - 實作多層快取策略 (依賴、測試結果、工具配置)",
            "  - 基於變更類型的智能執行策略", 
            "  - 動態測試矩陣，避免不必要的執行",
            "  - 失敗快速恢復和重試機制"
        ])
        
        return suggestions
    
    def print_analysis_report(self, metrics: List[Dict[str, Any]]) -> None:
        """輸出分析報告"""
        if not metrics:
            print("❌ 沒有可分析的數據")
            return
        
        print("🚀 CI/CD 效能分析報告")
        print("=" * 60)
        print(f"📊 數據範圍: 最近 {len(metrics)} 次執行")
        print(f"📅 分析時間: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print()
        
        # 整體統計
        durations = [m['duration_minutes'] for m in metrics]
        overall_avg = statistics.mean(durations)
        overall_median = statistics.median(durations)
        overall_max = max(durations)
        
        print("📈 整體效能指標:")
        print(f"  • 平均執行時間: {overall_avg:.2f} 分鐘")
        print(f"  • 中位數執行時間: {overall_median:.2f} 分鐘") 
        print(f"  • 最長執行時間: {overall_max:.2f} 分鐘")
        print()
        
        # 按 workflow 分析
        analysis = self.analyze_by_workflow(metrics)
        print("📊 各 Workflow 效能分析:")
        
        for name, stats in sorted(analysis.items(), key=lambda x: x[1]['mean'], reverse=True):
            print(f"• {name}:")
            print(f"  - 執行次數: {stats['count']}")
            print(f"  - 平均時間: {stats['mean']:.2f} 分鐘")
            print(f"  - 中位數: {stats['median']:.2f} 分鐘")
            print(f"  - 最長時間: {stats['max']:.2f} 分鐘")
            if stats['stdev'] > 0:
                print(f"  - 標準差: {stats['stdev']:.2f} 分鐘")
        print()
        
        # 成功率分析
        success_rates = self.calculate_success_rates(metrics)
        print("✅ 成功率分析:")
        for name, rate in sorted(success_rates.items(), key=lambda x: x[1], reverse=True):
            status = "✅" if rate >= 95 else "⚠️" if rate >= 90 else "❌"
            print(f"  {status} {name}: {rate:.1f}%")
        print()
        
        # 瓶頸分析
        bottlenecks = self.identify_bottlenecks(analysis)
        print("🚨 效能瓶頸 TOP 3:")
        for b in bottlenecks:
            print(f"  {b['rank']}. {b['workflow']}")
            print(f"     平均: {b['avg_duration']:.2f} 分鐘 | 最長: {b['max_duration']:.2f} 分鐘")
            print(f"     執行次數: {b['execution_count']} | 改善潛力: {b['improvement_potential']:.1f} 分鐘")
        print()
        
        # 優化建議
        suggestions = self.generate_optimization_suggestions(bottlenecks, success_rates)
        print("💡 優化建議:")
        for suggestion in suggestions:
            print(f"  {suggestion}")
        print()
        
        # 目標對比
        target_time = 8.0  # 目標執行時間
        current_avg = overall_avg
        if current_avg > target_time:
            improvement_needed = current_avg - target_time
            improvement_percent = (improvement_needed / current_avg) * 100
            print(f"🎯 優化目標:")
            print(f"  • 當前平均: {current_avg:.2f} 分鐘")
            print(f"  • 目標時間: {target_time} 分鐘")
            print(f"  • 需要改善: {improvement_needed:.2f} 分鐘 ({improvement_percent:.1f}%)")
        else:
            print(f"🎉 已達成目標! 當前平均執行時間 {current_avg:.2f} 分鐘 < 目標 {target_time} 分鐘")

def main():
    parser = argparse.ArgumentParser(description='CI/CD 效能分析工具')
    parser.add_argument('--days', type=int, default=7, help='分析最近N天的數據 (默認: 7)')
    parser.add_argument('--limit', type=int, default=50, help='最大分析記錄數 (默認: 50)')
    parser.add_argument('--repo', default='Craig-0219/potato', help='GitHub 倉庫 (默認: Craig-0219/potato)')
    parser.add_argument('--output', help='輸出報告到文件')
    
    args = parser.parse_args()
    
    analyzer = CICDPerformanceAnalyzer(repo=args.repo)
    
    print(f"📡 正在獲取最近 {args.days} 天的 CI/CD 數據...")
    metrics = analyzer.fetch_workflow_runs(days=args.days, limit=args.limit)
    
    if not metrics:
        print("❌ 未獲取到數據，請檢查:")
        print("  • GITHUB_TOKEN 環境變數是否設置") 
        print("  • 倉庫名稱是否正確")
        print("  • 網路連接是否正常")
        return
    
    # 生成分析報告
    if args.output:
        # 重定向輸出到文件
        import io
        from contextlib import redirect_stdout
        
        with open(args.output, 'w', encoding='utf-8') as f:
            with redirect_stdout(f):
                analyzer.print_analysis_report(metrics)
        print(f"📁 報告已保存到: {args.output}")
    else:
        analyzer.print_analysis_report(metrics)

if __name__ == '__main__':
    main()