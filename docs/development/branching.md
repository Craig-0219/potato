# 🔄 Dev 分支維護機制

## 📋 維護原則

### 🎯 Dev 分支定位
- **完整開發環境** - 包含所有開發工具和測試框架
- **最新功能集合** - 最新開發的功能和改進
- **CI/CD 試驗場** - 新的自動化流程測試
- **文檔完整性** - 包含完整的技術文檔

### 🔄 維護週期
- **每日維護** - 自動化清理和品質檢查
- **每週評估** - 功能穩定性和效能評估
- **每月整理** - 文檔更新和架構優化
- **季度審查** - 技術債務清理和架構演進

## 🛠️ 自動化維護機制

### 📅 每日自動化任務
```yaml
# .github/workflows/daily-maintenance.yml
name: 📅 Daily Dev Branch Maintenance

on:
  schedule:
    - cron: '0 2 * * *'  # 每日凌晨 2 點執行
  workflow_dispatch:

jobs:
  daily-cleanup:
    name: 🧹 每日清理作業
    runs-on: ubuntu-latest
    
    steps:
    - name: Checkout
      uses: actions/checkout@v4
    
    - name: 🗑️ 清理快取檔案
      run: |
        find . -name "*.pyc" -delete
        find . -name "__pycache__" -type d -exec rm -rf {} +
        find . -name ".pytest_cache" -type d -exec rm -rf {} +
    
    - name: 📊 生成品質報告
      run: |
        python scripts/generate_quality_report.py
    
    - name: 🔍 檢查依賴更新
      run: |
        pip-audit --desc --output=json > security_audit.json
        safety check --json --output safety_report.json
    
    - name: 📈 更新開發指標
      run: |
        python scripts/update_dev_metrics.py
```

### 🔍 品質監控
```python
# scripts/generate_quality_report.py
import subprocess
import json
from pathlib import Path
from datetime import datetime

class DevBranchQualityChecker:
    def __init__(self):
        self.report = {
            "timestamp": datetime.now().isoformat(),
            "metrics": {},
            "issues": [],
            "recommendations": []
        }
    
    def check_test_coverage(self):
        """檢查測試覆蓋率"""
        result = subprocess.run(
            ["pytest", "--cov=bot", "--cov=shared", "--cov-report=json"],
            capture_output=True, text=True
        )
        
        if result.returncode == 0:
            with open("coverage.json") as f:
                coverage_data = json.load(f)
                self.report["metrics"]["test_coverage"] = coverage_data["totals"]["percent_covered"]
        
        return self.report["metrics"]["test_coverage"]
    
    def check_code_quality(self):
        """檢查代碼品質"""
        # Black 格式檢查
        black_result = subprocess.run(["black", "--check", "."], capture_output=True)
        self.report["metrics"]["black_compliant"] = black_result.returncode == 0
        
        # flake8 語法檢查
        flake8_result = subprocess.run(["flake8", "."], capture_output=True, text=True)
        if flake8_result.returncode != 0:
            self.report["issues"].append({
                "type": "code_style",
                "tool": "flake8",
                "details": flake8_result.stdout
            })
        
        return len(self.report["issues"]) == 0
    
    def check_security(self):
        """安全檢查"""
        bandit_result = subprocess.run(
            ["bandit", "-r", "bot/", "shared/", "-f", "json"],
            capture_output=True, text=True
        )
        
        if bandit_result.returncode != 0:
            try:
                bandit_data = json.loads(bandit_result.stdout)
                high_severity = [r for r in bandit_data.get("results", []) 
                               if r.get("issue_severity") == "HIGH"]
                
                if high_severity:
                    self.report["issues"].append({
                        "type": "security",
                        "tool": "bandit",
                        "high_severity_count": len(high_severity)
                    })
            except json.JSONDecodeError:
                pass
    
    def generate_recommendations(self):
        """生成改進建議"""
        coverage = self.report["metrics"].get("test_coverage", 0)
        if coverage < 85:
            self.report["recommendations"].append(
                f"測試覆蓋率 ({coverage:.1f}%) 低於目標 85%，建議增加測試"
            )
        
        if not self.report["metrics"].get("black_compliant", True):
            self.report["recommendations"].append(
                "代碼格式不符合 Black 標準，執行 'black .' 進行格式化"
            )
        
        security_issues = [i for i in self.report["issues"] if i["type"] == "security"]
        if security_issues:
            self.report["recommendations"].append(
                f"發現 {len(security_issues)} 個安全問題，請檢查 bandit 報告"
            )
    
    def save_report(self):
        """保存報告"""
        report_path = Path("docs/reports/daily-quality-report.json")
        report_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(report_path, "w") as f:
            json.dump(self.report, f, indent=2, ensure_ascii=False)
        
        # 生成可讀性報告
        self._generate_readable_report()
    
    def _generate_readable_report(self):
        """生成人類可讀的報告"""
        coverage = self.report["metrics"].get("test_coverage", 0)
        issues_count = len(self.report["issues"])
        
        status = "🟢 良好" if coverage >= 85 and issues_count == 0 else \
                 "🟡 需要關注" if coverage >= 70 and issues_count <= 3 else \
                 "🔴 需要改進"
        
        readable_report = f"""# 📊 Dev 分支每日品質報告

**日期**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
**整體狀態**: {status}

## 📈 品質指標

- **測試覆蓋率**: {coverage:.1f}% {'✅' if coverage >= 85 else '⚠️' if coverage >= 70 else '❌'}
- **代碼格式**: {'✅ 符合標準' if self.report["metrics"].get("black_compliant") else '❌ 需要修復'}
- **發現問題**: {issues_count} 個

## 🔍 問題摘要

"""
        
        for issue in self.report["issues"]:
            readable_report += f"- **{issue['type']}**: {issue['tool']} 發現問題\n"
        
        if not self.report["issues"]:
            readable_report += "- ✅ 未發現問題\n"
        
        readable_report += "\n## 💡 改進建議\n\n"
        
        for rec in self.report["recommendations"]:
            readable_report += f"- {rec}\n"
        
        if not self.report["recommendations"]:
            readable_report += "- ✅ 目前品質良好，無需改進\n"
        
        with open("docs/reports/daily-quality-report.md", "w") as f:
            f.write(readable_report)

if __name__ == "__main__":
    checker = DevBranchQualityChecker()
    checker.check_test_coverage()
    checker.check_code_quality()
    checker.check_security()
    checker.generate_recommendations()
    checker.save_report()
    
    print("📊 品質檢查完成，報告已生成")
```

## 📚 文檔維護機制

### 📝 文檔同步檢查
```python
# scripts/check_docs_sync.py
import ast
import re
from pathlib import Path

class DocumentationSyncChecker:
    def __init__(self):
        self.issues = []
        self.suggestions = []
    
    def check_api_docs_sync(self):
        """檢查 API 文檔與代碼同步"""
        api_files = Path("bot/api/routes").glob("*.py")
        
        for api_file in api_files:
            with open(api_file) as f:
                content = f.read()
                
            # 分析 FastAPI 路由
            tree = ast.parse(content)
            endpoints = []
            
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef):
                    # 檢查是否為 API 端點
                    for decorator in node.decorator_list:
                        if hasattr(decorator, 'attr') and decorator.attr in ['get', 'post', 'put', 'delete']:
                            endpoints.append({
                                'method': decorator.attr.upper(),
                                'function': node.name,
                                'docstring': ast.get_docstring(node)
                            })
            
            # 檢查對應的文檔是否存在
            doc_file = Path(f"docs/api/{api_file.stem}-api.md")
            if not doc_file.exists() and endpoints:
                self.issues.append(f"缺少 API 文檔: {doc_file}")
    
    def check_function_documentation(self):
        """檢查函數文檔完整性"""
        python_files = list(Path("bot").rglob("*.py")) + list(Path("shared").rglob("*.py"))
        
        for py_file in python_files:
            if "__pycache__" in str(py_file):
                continue
                
            with open(py_file) as f:
                content = f.read()
            
            tree = ast.parse(content)
            
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef):
                    # 跳過私有函數和測試函數
                    if node.name.startswith('_') or node.name.startswith('test_'):
                        continue
                    
                    if not ast.get_docstring(node):
                        self.suggestions.append(
                            f"建議為 {py_file}:{node.lineno} {node.name}() 添加文檔字串"
                        )
    
    def generate_report(self):
        """生成文檔同步報告"""
        report = f"""# 📚 文檔同步檢查報告

**檢查時間**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

## ❌ 發現的問題

"""
        
        for issue in self.issues:
            report += f"- {issue}\n"
        
        if not self.issues:
            report += "- ✅ 未發現嚴重問題\n"
        
        report += "\n## 💡 改進建議\n\n"
        
        # 只顯示前 10 個建議，避免報告過長
        for suggestion in self.suggestions[:10]:
            report += f"- {suggestion}\n"
        
        if len(self.suggestions) > 10:
            report += f"- ... 還有 {len(self.suggestions) - 10} 個建議（完整列表請查看詳細報告）\n"
        
        if not self.suggestions:
            report += "- ✅ 文檔完整性良好\n"
        
        return report
```

### 🔄 依賴更新監控
```python
# scripts/dependency_monitor.py
import subprocess
import json
import requests
from packaging import version

class DependencyMonitor:
    def __init__(self):
        self.outdated_packages = []
        self.security_issues = []
        self.recommendations = []
    
    def check_outdated_packages(self):
        """檢查過時的套件"""
        result = subprocess.run(
            ["pip", "list", "--outdated", "--format=json"],
            capture_output=True, text=True
        )
        
        if result.returncode == 0:
            self.outdated_packages = json.loads(result.stdout)
    
    def check_security_vulnerabilities(self):
        """檢查安全漏洞"""
        result = subprocess.run(
            ["safety", "check", "--json"],
            capture_output=True, text=True
        )
        
        if result.stdout:
            try:
                self.security_issues = json.loads(result.stdout)
            except json.JSONDecodeError:
                pass
    
    def generate_update_plan(self):
        """生成更新計畫"""
        if self.security_issues:
            self.recommendations.append("🚨 優先修復安全漏洞")
            for issue in self.security_issues:
                self.recommendations.append(
                    f"  - 更新 {issue.get('package')} 到安全版本"
                )
        
        # 分析重要套件更新
        important_packages = ['fastapi', 'discord.py', 'pydantic', 'aiomysql']
        for pkg in self.outdated_packages:
            if pkg['name'].lower() in important_packages:
                self.recommendations.append(
                    f"📦 考慮更新重要套件: {pkg['name']} "
                    f"{pkg['version']} → {pkg['latest_version']}"
                )
    
    def save_report(self):
        """保存依賴監控報告"""
        report = {
            "timestamp": datetime.now().isoformat(),
            "outdated_count": len(self.outdated_packages),
            "security_issues_count": len(self.security_issues),
            "outdated_packages": self.outdated_packages,
            "security_issues": self.security_issues,
            "recommendations": self.recommendations
        }
        
        with open("docs/reports/dependency-monitor.json", "w") as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
```

## 🚀 效能監控機制

### 📊 效能基準追蹤
```python
# scripts/performance_monitor.py
import asyncio
import time
import statistics
from pathlib import Path
import json

class PerformanceMonitor:
    def __init__(self):
        self.benchmarks = {}
        self.alerts = []
    
    async def benchmark_api_endpoints(self):
        """API 端點效能基準測試"""
        import httpx
        
        endpoints = [
            ("GET", "/api/v1/health"),
            ("GET", "/api/v1/tickets"),
            ("POST", "/api/v1/tickets", {"title": "Test", "description": "Test"})
        ]
        
        async with httpx.AsyncClient() as client:
            for method, endpoint, *data in endpoints:
                times = []
                for _ in range(10):  # 10 次測試
                    start = time.perf_counter()
                    try:
                        if method == "GET":
                            response = await client.get(f"http://localhost:8000{endpoint}")
                        elif method == "POST":
                            response = await client.post(f"http://localhost:8000{endpoint}", json=data[0])
                        
                        times.append(time.perf_counter() - start)
                    except Exception:
                        times.append(float('inf'))  # 失敗記為無限大
                
                avg_time = statistics.mean(times)
                self.benchmarks[f"{method} {endpoint}"] = {
                    "avg_response_time": avg_time,
                    "min_time": min(times),
                    "max_time": max(times),
                    "success_rate": len([t for t in times if t != float('inf')]) / len(times)
                }
                
                # 效能警告
                if avg_time > 1.0:  # 超過 1 秒
                    self.alerts.append(f"⚠️ {method} {endpoint} 回應時間過長: {avg_time:.2f}s")
    
    async def benchmark_database_operations(self):
        """資料庫操作效能測試"""
        # 這裡可以添加資料庫效能測試
        pass
    
    def save_benchmark_results(self):
        """保存基準測試結果"""
        report = {
            "timestamp": time.time(),
            "benchmarks": self.benchmarks,
            "alerts": self.alerts,
            "summary": {
                "total_endpoints": len(self.benchmarks),
                "alerts_count": len(self.alerts),
                "avg_response_time": statistics.mean([
                    b["avg_response_time"] for b in self.benchmarks.values()
                ]) if self.benchmarks else 0
            }
        }
        
        # 保存到歷史記錄
        history_file = Path("docs/reports/performance-history.jsonl")
        with open(history_file, "a") as f:
            f.write(json.dumps(report) + "\n")
        
        # 生成當前報告
        with open("docs/reports/performance-current.json", "w") as f:
            json.dump(report, f, indent=2)
```

## 📋 維護檢查清單

### 🔄 每日檢查項目
- [ ] Python 快取檔案清理
- [ ] 測試覆蓋率維持在 85% 以上
- [ ] 代碼格式符合 Black 標準
- [ ] 無高風險安全漏洞
- [ ] CI/CD 流程正常運作
- [ ] 依賴套件安全掃描

### 📅 每週檢查項目
- [ ] 文檔與代碼同步性檢查
- [ ] 效能基準測試
- [ ] 依賴套件更新評估
- [ ] 技術債務評估
- [ ] 功能穩定性評估

### 🗓️ 每月檢查項目
- [ ] 架構設計回顧
- [ ] 開發工具鏈更新
- [ ] 測試策略優化
- [ ] 監控指標分析
- [ ] 團隊開發效率評估

## 🛡️ 分支保護規則

### 📋 自動化保護機制
```yaml
# dev 分支保護規則
branch_protection:
  dev:
    required_status_checks:
      - "tests"
      - "code-quality"
      - "security-scan"
    enforce_admins: true
    required_pull_request_reviews:
      required_approving_review_count: 1
      dismiss_stale_reviews: true
    restrictions: null
```

### 🔍 合併前檢查
- 所有測試必須通過
- 代碼覆蓋率不能降低
- 通過所有品質檢查
- 至少一位審查者批准
- 分支與 main 同步

---

**🔄 維護承諾：**
- 保持 dev 分支的高品質和穩定性
- 定期清理技術債務
- 持續優化開發體驗
- 維護完整的文檔和測試

**📅 建立日期：** 2025-08-31  
**🔄 維護週期：** 持續進行  
**📊 自動化程度：** 85%