#!/usr/bin/env python3
"""
Workflow dependency and flow analysis script
Analyzes the workflow chain: dev push -> tests -> auto-merge -> main protection -> deployment
"""

import json
import sys

def analyze_workflow_flow():
    """分析 workflow 流程和依賴關係"""
    
    print("🔄 Workflow Flow Analysis")
    print("=" * 50)
    
    workflow_flow = {
        "1_dev_push": {
            "trigger": "push to dev branch",
            "workflows": [
                "test-coverage.yml (自動)",
                "code-quality.yml (自動)", 
                "smart-change-detection.yml (自動)"
            ],
            "description": "開發者推送到 dev 分支時自動觸發"
        },
        
        "2_quality_checks": {
            "trigger": "triggered by dev push",
            "workflows": [
                "test-coverage.yml: 執行單元測試、整合測試、E2E測試",
                "code-quality.yml: Black、isort、flake8 檢查",
                "security-scans.yml: 安全掃描 (如果變更觸發)"
            ],
            "description": "平行執行品質檢查"
        },
        
        "3_auto_merge": {
            "trigger": "dev quality checks pass",
            "workflows": [
                "auto-merge-dev-to-main.yml: 品質檢查通過後自動合併"
            ],
            "condition": "所有品質檢查必須通過",
            "description": "自動合併 dev 到 main"
        },
        
        "4_main_protection": {
            "trigger": "merge/push to main", 
            "workflows": [
                "main-branch-protection.yml: 生產檔案合規檢查"
            ],
            "description": "保護 main 分支，確保生產就緒"
        },
        
        "5_deployment": {
            "trigger": "main branch updated",
            "workflows": [
                "deploy-to-production.yml: 部署到生產環境",
                "deploy-to-ptero.yml: 同步到 ptero 分支"
            ],
            "description": "自動部署到生產環境"
        }
    }
    
    print("📋 Workflow 執行順序:")
    print()
    
    for step, info in workflow_flow.items():
        step_num = step.split('_')[0]
        step_name = ' '.join(step.split('_')[1:]).title()
        
        print(f"階段 {step_num}: {step_name}")
        print(f"  觸發條件: {info['trigger']}")
        
        if 'condition' in info:
            print(f"  執行條件: {info['condition']}")
            
        print(f"  執行workflows:")
        for workflow in info['workflows']:
            print(f"    • {workflow}")
            
        print(f"  說明: {info['description']}")
        print()
    
    # 檢查潛在問題
    print("⚠️  潛在流程問題分析:")
    print()
    
    issues = [
        {
            "issue": "測試失敗後重新觸發",
            "current": "dev 分支 push 總是觸發 auto-merge workflow",
            "problem": "如果測試失敗，修復後 push 到 dev 會再次觸發完整流程",
            "solution": "auto-merge workflow 內建品質檢查，失敗會阻止合併"
        },
        {
            "issue": "並發執行問題", 
            "current": "多個 workflows 同時執行",
            "problem": "可能造成資源競爭或狀態不一致",
            "solution": "使用 concurrency groups 限制並發"
        },
        {
            "issue": "失敗通知",
            "current": "各 workflow 獨立通知",
            "problem": "開發者可能錯過關鍵失敗通知",
            "solution": "整合通知機制或使用 GitHub 環境保護"
        }
    ]
    
    for i, issue in enumerate(issues, 1):
        print(f"{i}. {issue['issue']}:")
        print(f"   現狀: {issue['current']}")
        print(f"   問題: {issue['problem']}")
        print(f"   解決: {issue['solution']}")
        print()
    
    print("✅ 建議的改進措施:")
    recommendations = [
        "為 auto-merge workflow 添加 concurrency group",
        "確保 GitHub Secrets 正確配置",
        "設置分支保護規則要求 status checks",
        "監控 workflow 執行狀況和成功率",
        "建立失敗後的手動介入流程"
    ]
    
    for i, rec in enumerate(recommendations, 1):
        print(f"{i}. {rec}")
    
    return True

def main():
    """主執行函數"""
    try:
        result = analyze_workflow_flow()
        if result:
            print("\n🎯 Workflow 流程分析完成")
            return 0
        else:
            print("\n❌ 分析過程發現問題") 
            return 1
    except Exception as e:
        print(f"\n💥 分析失敗: {e}")
        return 1

if __name__ == '__main__':
    sys.exit(main())