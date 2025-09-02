#!/bin/bash
set -e

# Code quality check script for production compliance
echo "🧹 檢查 Python 代碼品質..."

# Install check tools
pip install black isort flake8

# Check for formatting issues
echo "🔍 檢查 Black 格式化..."
if ! black --check --diff . > black_report.txt 2>&1; then
  echo "❌ 發現代碼格式問題："
  head -20 black_report.txt
  echo "💡 請在 dev 分支中執行 'black .' 修復格式問題"
  exit 1
fi

echo "🔍 檢查 import 排序..."
if ! isort --check --diff . > isort_report.txt 2>&1; then
  echo "❌ 發現 import 排序問題："
  head -20 isort_report.txt  
  echo "💡 請在 dev 分支中執行 'isort .' 修復 import 排序"
  exit 1
fi

echo "✅ 代碼品質檢查通過"