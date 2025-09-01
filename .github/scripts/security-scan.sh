#!/bin/bash
set -e

# Security scan script for production compliance
echo "🔒 執行生產環境安全掃描..."

# Install security scanning tools
pip install bandit safety

# Scan Python code for security issues
echo "🔍 掃描代碼安全問題 (Bandit)..."
bandit -r bot/ shared/ -f json -o bandit-report.json

# Check dependency security
echo "📦 檢查依賴包安全 (Safety)..."
safety check --json --output safety-report.json

echo "✅ 安全掃描指令執行完成"

# Generate security report summary and determine exit code
echo "📋 分析安全報告..."

exit_code=0
summary=""

# Analyze Bandit report
if [ -f bandit-report.json ]; then
  # Consider issues of medium or high severity as failures
  high_issues=$(jq '[.results[] | select(.issue_severity == "HIGH")] | length' bandit-report.json)
  medium_issues=$(jq '[.results[] | select(.issue_severity == "MEDIUM")] | length' bandit-report.json)
  total_issues=$((high_issues + medium_issues))

  summary="$summary\n- Bandit: 發現 $high_issues 個 HIGH, $medium_issues 個 MEDIUM 等級問題."
  
  if [ "$total_issues" -gt 0 ]; then
    echo "❌ Bandit 發現 $total_issues 個嚴重或中等問題。"
    exit_code=1
    # Print details of high/medium issues
    jq '.results[] | select(.issue_severity == "HIGH" or .issue_severity == "MEDIUM")' bandit-report.json
  else
    echo "✅ Bandit: 未發現嚴重安全問題。"
  fi
fi

# Analyze Safety report
if [ -f safety-report.json ]; then
  vuln_count=$(jq '. | length' safety-report.json)

  summary="$summary\n- Safety: 發現 $vuln_count 個已知的依賴漏洞."

  if [ "$vuln_count" -gt 0 ]; then
    echo "❌ Safety 發現 $vuln_count 個存在漏洞的依賴。"
    exit_code=1
    # Print details of vulnerabilities
    jq '.' safety-report.json
  else
    echo "✅ Safety: 未發現依賴漏洞。"
  fi
fi

echo -e "\n--- 安全掃描總結 ---$summary\n----------------------"

if [ "$exit_code" -ne 0 ]; then
  echo "🚫 安全檢查失敗，請修正上述問題。"
  exit 1
else
  echo "✅ 安全檢查通過。"
fi