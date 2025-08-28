#!/bin/bash
# 本地代碼格式修復腳本
# 自動修復常見的代碼格式問題

set -e

# 顏色定義
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 日誌函數
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# 檢查必要工具
check_tools() {
    log_info "檢查代碼格式化工具..."

    tools=("black" "isort" "autoflake")
    missing_tools=()

    for tool in "${tools[@]}"; do
        if ! command -v "$tool" &> /dev/null; then
            missing_tools+=("$tool")
        fi
    done

    if [ ${#missing_tools[@]} -ne 0 ]; then
        log_error "缺少工具: ${missing_tools[*]}"
        log_info "安裝命令: pip install black isort autoflake"
        return 1
    fi

    log_success "所有工具已安裝"
    return 0
}

# 自動修復代碼格式
fix_code_format() {
    log_info "=== 開始代碼格式修復 ==="

    # 1. 移除未使用的導入和變數
    log_info "移除未使用的導入和變數..."
    if autoflake --remove-all-unused-imports --remove-unused-variables --in-place --recursive .; then
        log_success "✅ autoflake 修復完成"
    else
        log_warning "⚠️ autoflake 執行有警告"
    fi

    # 2. 排序導入語句
    log_info "排序導入語句..."
    if isort .; then
        log_success "✅ isort 排序完成"
    else
        log_warning "⚠️ isort 執行有警告"
    fi

    # 3. 格式化代碼
    log_info "格式化代碼..."
    if black .; then
        log_success "✅ black 格式化完成"
    else
        log_warning "⚠️ black 執行有警告"
    fi

    log_success "🎉 代碼格式修復完成"
}

# 檢查修復結果
verify_fixes() {
    log_info "=== 驗證修復結果 ==="

    checks=(
        "black --check --diff ."
        "isort --check-only --diff ."
        "autoflake --check --recursive ."
    )

    all_passed=true

    for check in "${checks[@]}"; do
        log_info "執行檢查: $check"
        if eval "$check" > /dev/null 2>&1; then
            log_success "✅ 檢查通過"
        else
            log_warning "⚠️ 仍有格式問題"
            all_passed=false
        fi
    done

    if $all_passed; then
        log_success "🎉 所有格式檢查通過"
        return 0
    else
        log_warning "⚠️ 部分格式問題需要手動處理"
        return 1
    fi
}

# 主執行流程
main() {
    echo "🚀 本地代碼格式修復工具"
    echo "=========================="

    # 檢查工具
    if ! check_tools; then
        exit 1
    fi

    # 修復格式
    fix_code_format

    # 驗證結果
    if verify_fixes; then
        log_success "✅ 代碼已準備就緒，可以提交"
        exit 0
    else
        log_warning "⚠️ 請檢查剩餘的格式問題"
        exit 1
    fi
}

# 執行主函數
main "$@"
