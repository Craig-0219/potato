#!/bin/bash
set -e

# Production compliance check script for main branch protection
echo "🔍 執行生產檔案白名單驗證..."

# Create production whitelist
cat > production_whitelist.txt << 'EOF'
# 核心程式檔案
bot/**/*.py
shared/**/*.py
web-ui/**/*.js
web-ui/**/*.ts
web-ui/**/*.tsx
web-ui/**/*.json
web-ui/**/*.css
web-ui/**/*.html

# 配置檔案
requirements.txt
pyproject.toml
.env.example
.gitignore
.gitattributes
.gitconfig

# 啟動腳本
start.py
start.sh
start.bat

# 文檔 (僅基本文檔)
README.md
docs/system/ADMIN_PERMISSION_SETUP.md
docs/user-guides/COMMANDS.md
docs/user-guides/USER_MANUAL.md

# CI/CD 流程 (僅生產相關)
.github/workflows/deploy-to-production.yml
.github/workflows/deploy-to-ptero.yml
.github/workflows/emergency-rollback.yml
.github/workflows/main-branch-protection.yml
.github/workflows/security-scans.yml
.github/workflows/smart-change-detection.yml
.github/workflows/code-quality.yml
.github/workflows/test-coverage.yml
.github/scripts/*.py
.github/scripts/*.sh
EOF

# Create production blacklist
cat > production_blacklist.txt << 'EOF'
# 開發工具配置
.bandit
.flake8
.pre-commit-config.yaml
.safety-policy.json
.secrets.baseline
.semgrepignore
pytest.ini

# 測試檔案
tests/**/*
**/test_*.py
**/*_test.py
**/*_tests.py

# 開發腳本
scripts/**/*
tools/**/*

# 構建檔案
Dockerfile*
docker-compose*.yml
Makefile

# 開發文檔
docs/development/**/*
docs/plans/**/*
docs/archives/**/*
docs/reports/**/*
docs/issues/**/*
DEVELOPMENT*.md
CONTRIBUTING.md

# 臨時檔案
*.tmp
*.temp
*.log
*.cache
.pytest_cache/**/*
__pycache__/**/*
*.pyc

# IDE 配置
.vscode/**/*
.idea/**/*
*.swp
*.swo
.DS_Store

# 實驗性檔案
experimental/**/*
prototype/**/*
demo/**/*
sandbox/**/*

# 備份檔案
*.bak
*.backup
*.old
EOF

echo "✅ 白名單和黑名單準備完成"

# Check for prohibited files
echo "🔍 檢查是否存在禁止的開發檔案..."

violation_found=false
violations_list=""

# Check blacklist for prohibited files
while IFS= read -r pattern; do
  # Skip comments and empty lines
  if [[ "$pattern" =~ ^[[:space:]]*# ]] || [[ -z "$pattern" ]]; then
    continue
  fi
  
  # Check if files exist (handle globbing carefully)
  if compgen -G "$pattern" > /dev/null 2>&1; then
    echo "❌ 發現禁止的檔案類型: $pattern"
    violations_list="$violations_list\n- $pattern"
    violation_found=true
  fi
done < production_blacklist.txt

if [ "$violation_found" = true ]; then
  echo "🚨 MAIN 分支汙染檢測！"
  echo "=============================="
  echo "發現以下不應該存在於 main 分支的檔案："
  echo -e "$violations_list"
  echo ""
  echo "💡 解決方案："
  echo "1. 將這些檔案移至 dev 分支"
  echo "2. 或者完全移除這些開發用檔案"
  echo "3. main 分支應該只包含生產環境必需的檔案"
  echo ""
  echo "🚫 PR 被拒絕 - main 分支保護啟動"
  exit 1
else
  echo "✅ 未發現禁止的檔案類型"
fi

# File structure compliance check
echo "📁 檢查檔案結構是否符合生產標準..."

# Check required directories
required_dirs=("bot" "shared" ".github/workflows")
missing_dirs=""

for dir in "${required_dirs[@]}"; do
  if [ ! -d "$dir" ]; then
    echo "❌ 缺少必需目錄: $dir"
    missing_dirs="$missing_dirs $dir"
  else
    echo "✅ 目錄存在: $dir"
  fi
done

if [ -n "$missing_dirs" ]; then
  echo "🚨 缺少必需的核心目錄: $missing_dirs"
  exit 1
fi

# Check required files
required_files=(
  "bot/main.py"
  "requirements.txt"
  ".env.example"
  "README.md"
  "start.py"
)

missing_files=""
for file in "${required_files[@]}"; do
  if [ ! -f "$file" ]; then
    echo "❌ 缺少必需檔案: $file"
    missing_files="$missing_files $file"
  else
    echo "✅ 檔案存在: $file"
  fi
done

if [ -n "$missing_files" ]; then
  echo "🚨 缺少必需的核心檔案: $missing_files"
  exit 1
fi

echo "✅ 檔案結構符合生產標準"

# Production readiness assessment
echo "📊 評估 main 分支生產就緒性..."

# Count file types
total_files=$(find . -type f -not -path "./.git/*" | wc -l)
python_files=$(find . -name "*.py" -not -path "./.git/*" | wc -l)
config_files=$(find . -name "*.txt" -o -name "*.toml" -o -name "*.yml" -o -name "*.yaml" | grep -v ".github" | wc -l)

echo "📈 檔案統計："
echo "  總檔案數: $total_files"
echo "  Python 檔案: $python_files"  
echo "  配置檔案: $config_files"

# Check if within reasonable range (production should be lean)
if [ $total_files -gt 500 ]; then
  echo "⚠️ 警告: 檔案數量過多 ($total_files > 500)"
  echo "💡 建議清理不必要的檔案以保持精簡"
fi

echo "✅ Main 分支生產就緒性評估完成"
echo "📋 評估結果: 符合生產標準"