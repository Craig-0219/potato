#!/usr/bin/env python3
"""
CI/CD 效能分析演示 - 使用模擬數據展示分析功能
"""

import json
import statistics
from datetime import datetime, timedelta
import random

def generate_demo_data():
    """生成模擬的 CI/CD 執行數據"""
    workflows = [
        "🧪 Test Coverage & Quality",
        "🔍 Code Quality Checks", 
        "🔒 Security Scans",
        "⚡ Optimized CI Pipeline",
        "🚀 Lightweight CI"
    ]
    
    metrics = []
    base_time = datetime.now() - timedelta(days=7)
    
    # 為每個 workflow 生成執行數據
    workflow_characteristics = {
        "🧪 Test Coverage & Quality": {'base_duration': 18, 'variance': 5, 'success_rate': 0.92},
        "🔍 Code Quality Checks": {'base_duration': 8, 'variance': 2, 'success_rate': 0.96},
        "🔒 Security Scans": {'base_duration': 12, 'variance': 3, 'success_rate': 0.94},
        "⚡ Optimized CI Pipeline": {'base_duration': 15, 'variance': 4, 'success_rate': 0.89},
        "🚀 Lightweight CI": {'base_duration': 6, 'variance': 2, 'success_rate': 0.98}
    }
    
    run_id = 1000
    for workflow in workflows:
        char = workflow_characteristics[workflow]
        # 每個 workflow 生成 5-15 次執行記錄
        num_runs = random.randint(8, 15)
        
        for i in range(num_runs):
            # 生成執行時間 (正態分佈)
            duration_minutes = max(1, random.normalvariate(char['base_duration'], char['variance']))
            
            # 生成狀態 (基於成功率)
            status = 'success' if random.random() < char['success_rate'] else 'failure'
            
            # 生成時間戳
            created_at = base_time + timedelta(hours=random.randint(0, 168))  # 7天內隨機
            
            metrics.append({
                'workflow_name': workflow,
                'run_id': run_id,
                'status': status,
                'branch': 'dev',
                'duration_seconds': duration_minutes * 60,
                'duration_minutes': round(duration_minutes, 2),
                'created_at': created_at.isoformat(),
                'trigger_event': random.choice(['push', 'pull_request', 'workflow_dispatch']),
                'attempt': 1
            })
            run_id += 1
    
    return metrics

def analyze_demo_data():
    """分析演示數據"""
    print("🚀 CI/CD 效能分析報告 (演示)")
    print("=" * 60)
    
    # 生成模擬數據
    metrics = generate_demo_data()
    print(f"📊 數據範圍: 模擬 {len(metrics)} 次執行")
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
    workflow_data = {}
    for metric in metrics:
        name = metric['workflow_name']
        duration = metric['duration_minutes']
        
        if name not in workflow_data:
            workflow_data[name] = []
        workflow_data[name].append(duration)
    
    print("📊 各 Workflow 效能分析:")
    workflow_stats = {}
    
    for name, durations in workflow_data.items():
        if durations:
            stats = {
                'count': len(durations),
                'mean': statistics.mean(durations),
                'median': statistics.median(durations),
                'max': max(durations),
                'min': min(durations),
                'stdev': statistics.stdev(durations) if len(durations) > 1 else 0
            }
            workflow_stats[name] = stats
            
            print(f"• {name}:")
            print(f"  - 執行次數: {stats['count']}")
            print(f"  - 平均時間: {stats['mean']:.2f} 分鐘")
            print(f"  - 中位數: {stats['median']:.2f} 分鐘")
            print(f"  - 最長時間: {stats['max']:.2f} 分鐘")
            if stats['stdev'] > 0:
                print(f"  - 標準差: {stats['stdev']:.2f} 分鐘")
    print()
    
    # 成功率分析
    workflow_results = {}
    for metric in metrics:
        name = metric['workflow_name']
        status = metric['status']
        
        if name not in workflow_results:
            workflow_results[name] = {'total': 0, 'success': 0}
        
        workflow_results[name]['total'] += 1
        if status == 'success':
            workflow_results[name]['success'] += 1
    
    print("✅ 成功率分析:")
    success_rates = {}
    for name, results in workflow_results.items():
        rate = (results['success'] / results['total']) * 100 if results['total'] > 0 else 0
        success_rates[name] = rate
        status_icon = "✅" if rate >= 95 else "⚠️" if rate >= 90 else "❌"
        print(f"  {status_icon} {name}: {rate:.1f}%")
    print()
    
    # 瓶頸分析
    print("🚨 效能瓶頸 TOP 3:")
    sorted_workflows = sorted(workflow_stats.items(), key=lambda x: x[1]['mean'], reverse=True)
    
    bottlenecks = []
    for i, (name, stats) in enumerate(sorted_workflows[:3], 1):
        improvement_potential = max(0, stats['mean'] - 8.0)  # 目標 8 分鐘
        bottlenecks.append({
            'rank': i,
            'workflow': name,
            'avg_duration': stats['mean'],
            'improvement_potential': improvement_potential
        })
        
        print(f"  {i}. {name}")
        print(f"     平均: {stats['mean']:.2f} 分鐘 | 最長: {stats['max']:.2f} 分鐘")
        print(f"     執行次數: {stats['count']} | 改善潛力: {improvement_potential:.1f} 分鐘")
    print()
    
    # 優化建議
    print("💡 優化建議:")
    total_potential = sum(b['improvement_potential'] for b in bottlenecks)
    
    print(f"  🎯 優化前 3 大瓶頸可節省 {total_potential:.1f} 分鐘執行時間")
    
    for b in bottlenecks:
        if b['avg_duration'] > 10:
            print(f"  ⚡ {b['workflow']} 執行時間過長，建議:")
            print(f"    - 實作智能跳過機制，避免不必要的完整測試")
            print(f"    - 優化依賴安裝快取策略")
            print(f"    - 並行化測試執行")
    
    failing_workflows = [name for name, rate in success_rates.items() if rate < 95]
    if failing_workflows:
        print(f"  🔧 改善失敗率較高的 workflows: {', '.join(failing_workflows)}")
    
    print("  💡 通用優化策略:")
    print("    - 實作多層快取策略 (依賴、測試結果、工具配置)")
    print("    - 基於變更類型的智能執行策略")
    print("    - 動態測試矩陣，避免不必要的執行")
    print("    - 失敗快速恢復和重試機制")
    print()
    
    # 目標對比
    target_time = 8.0
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
    
    print()
    print("📋 下一步行動:")
    print("  1. 實施 Stage 2: 智能化策略升級")
    print("  2. 開始多層快取系統建置")
    print("  3. 建立變更檢測和智能跳過機制")
    print("  4. 持續監控和效能基準追蹤")

if __name__ == '__main__':
    analyze_demo_data()