#!/bin/bash
# monitor-sync.sh - ptero 分支同步監控腳本

set -euo pipefail

# 配置
MAIN_BRANCH="main"
PTERO_BRANCH="ptero"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
LOG_FILE="${PROJECT_ROOT}/logs/sync-monitor.log"
WEBHOOK_URL="${DISCORD_WEBHOOK_URL:-}"

# 顏色輸出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# 日誌函數
log_with_timestamp() {
    local level=$1
    local message=$2
    local timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    echo -e "${timestamp} [${level}] ${message}" | tee -a "${LOG_FILE}"
}

log_info() {
    log_with_timestamp "INFO" "$1"
}

log_warning() {
    log_with_timestamp "WARNING" "$1"
}

log_error() {
    log_with_timestamp "ERROR" "$1"
}

log_success() {
    log_with_timestamp "SUCCESS" "$1"
}

# 創建日誌目錄
mkdir -p "$(dirname "$LOG_FILE")"

# 發送 Discord 通知
send_discord_notification() {
    local title=$1
    local description=$2
    local color=$3  # 可選: success=green, warning=yellow, error=red
    
    if [ -z "$WEBHOOK_URL" ]; then
        return 0
    fi
    
    local color_code="3447003"  # 默認藍色
    case $color in
        success) color_code="3066993" ;;  # 綠色
        warning) color_code="15844367" ;; # 黃色  
        error) color_code="15158332" ;;   # 紅色
    esac
    
    local payload=$(cat <<EOF
{
  "embeds": [{
    "title": "$title",
    "description": "$description",
    "color": $color_code,
    "timestamp": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
    "footer": {
      "text": "Potato Bot 同步監控"
    }
  }]
}
EOF
)
    
    curl -H "Content-Type: application/json" \
         -X POST \
         -d "$payload" \
         "$WEBHOOK_URL" \
         --silent || true
}

# 檢查分支同步狀態
check_sync_status() {
    # 更新遠程資訊
    git fetch origin --prune --quiet
    
    # 檢查分支是否存在
    if ! git show-ref --verify --quiet refs/remotes/origin/$PTERO_BRANCH; then
        echo "ERROR: 遠程 $PTERO_BRANCH 分支不存在" >&2
        return 1
    fi
    
    if ! git show-ref --verify --quiet refs/remotes/origin/$MAIN_BRANCH; then
        echo "ERROR: 遠程 $MAIN_BRANCH 分支不存在" >&2
        return 1
    fi
    
    # 計算分支差異
    local commits_behind=$(git rev-list --count origin/$PTERO_BRANCH..origin/$MAIN_BRANCH 2>/dev/null || echo "0")
    local commits_ahead=$(git rev-list --count origin/$MAIN_BRANCH..origin/$PTERO_BRANCH 2>/dev/null || echo "0")
    
    local main_commit=$(git rev-parse --short origin/$MAIN_BRANCH)
    local ptero_commit=$(git rev-parse --short origin/$PTERO_BRANCH)
    
    # 返回狀態 (不使用log函數避免輸出混合)
    echo "$commits_behind:$commits_ahead:$main_commit:$ptero_commit"
}

# 檢查最後同步時間
check_last_sync_time() {
    local last_sync_commit=$(git log --oneline origin/$PTERO_BRANCH | grep -E "(🔄|merge)" | head -1 | awk '{print $1}' || echo "")
    
    if [ -n "$last_sync_commit" ]; then
        local last_sync_time=$(git log -1 --format="%cd" --date=iso $last_sync_commit 2>/dev/null || echo "未知")
        echo "$last_sync_time"
    else
        echo "未知"
    fi
}

# 檢查工作流程狀態
check_workflow_status() {
    # 使用 GitHub CLI 檢查最近的工作流程運行
    if command -v gh &> /dev/null; then
        local workflow_runs=$(gh run list --workflow="auto-sync-ptero.yml" --limit=1 --json=status,conclusion,createdAt,headBranch 2>/dev/null || echo "[]")
        
        if [ "$workflow_runs" != "[]" ]; then
            local status=$(echo "$workflow_runs" | jq -r '.[0].status // "unknown"' 2>/dev/null || echo "unknown")
            local conclusion=$(echo "$workflow_runs" | jq -r '.[0].conclusion // "unknown"' 2>/dev/null || echo "unknown")
            local created_at=$(echo "$workflow_runs" | jq -r '.[0].createdAt // "unknown"' 2>/dev/null || echo "unknown")
            
            echo "$status:$conclusion:$created_at"
        else
            echo "none:none:none"
        fi
    else
        echo "unknown:unknown:unknown"
    fi
}

# 生成同步報告
generate_report() {
    local sync_status=$1
    local last_sync_time=$2
    local workflow_status=$3
    
    IFS=':' read -r commits_behind commits_ahead main_commit ptero_commit <<< "$sync_status"
    IFS=':' read -r wf_status wf_conclusion wf_time <<< "$workflow_status"
    
    local report_file="${PROJECT_ROOT}/logs/sync-report-$(date +%Y%m%d).md"
    
    cat > "$report_file" << EOF
# 🔄 Potato Bot ptero 分支同步報告

**生成時間**: $(date '+%Y-%m-%d %H:%M:%S')

## 📊 同步狀態概覽

| 指標 | 值 |
|------|-----|
| ptero 落後提交數 | $commits_behind |
| ptero 領先提交數 | $commits_ahead |
| main 最新提交 | \`$main_commit\` |
| ptero 最新提交 | \`$ptero_commit\` |
| 最後同步時間 | $last_sync_time |

## 🤖 工作流程狀態

| 指標 | 值 |
|------|-----|
| 狀態 | $wf_status |
| 結果 | $wf_conclusion |
| 最近運行時間 | $wf_time |

## 📋 同步建議

EOF

    # 根據狀態添加建議
    if [ "$commits_behind" -gt 0 ]; then
        cat >> "$report_file" << EOF
⚠️ **需要同步**: ptero 分支落後 $commits_behind 個提交

**建議操作**:
1. 檢查自動同步工作流程是否正常
2. 如果自動同步失敗，手動執行同步:
   \`\`\`bash
   ./scripts/sync-ptero.sh
   \`\`\`

EOF
    else
        cat >> "$report_file" << EOF
✅ **狀態正常**: ptero 分支已是最新

EOF
    fi
    
    if [ "$wf_conclusion" = "failure" ]; then
        cat >> "$report_file" << EOF
🚨 **工作流程異常**: 自動同步工作流程執行失敗

**建議操作**:
1. 檢查 GitHub Actions 運行日誌
2. 手動執行同步並檢查衝突
3. 必要時聯繫開發團隊

EOF
    fi
    
    log_info "同步報告已生成: $report_file"
}

# 主監控函數
monitor() {
    log_info "🔍 開始 ptero 分支同步監控..."
    
    # 檢查是否在 Git 倉庫中
    if ! git rev-parse --is-inside-work-tree > /dev/null 2>&1; then
        log_error "當前目錄不是 Git 倉庫"
        exit 1
    fi
    
    # 檢查同步狀態
    local sync_status
    if sync_status=$(check_sync_status); then
        log_success "同步狀態檢查完成"
    else
        log_error "同步狀態檢查失敗"
        send_discord_notification "🚨 ptero 分支監控異常" "同步狀態檢查失敗，請檢查分支配置" "error"
        exit 1
    fi
    
    # 檢查最後同步時間
    local last_sync_time
    last_sync_time=$(check_last_sync_time)
    
    # 檢查工作流程狀態
    local workflow_status
    workflow_status=$(check_workflow_status)
    
    # 生成報告
    generate_report "$sync_status" "$last_sync_time" "$workflow_status"
    
    # 解析狀態
    IFS=':' read -r commits_behind commits_ahead main_commit ptero_commit <<< "$sync_status"
    
    # 發送通知 (如果需要)
    if [ "$commits_behind" -gt 5 ]; then
        send_discord_notification \
            "⚠️ ptero 分支同步延遲" \
            "ptero 分支落後 $commits_behind 個提交，建議檢查自動同步狀態" \
            "warning"
    elif [ "$commits_behind" -gt 0 ]; then
        log_info "ptero 分支有輕微延遲 ($commits_behind 個提交)，屬於正常範圍"
    else
        log_success "✅ ptero 分支同步狀態正常"
    fi
    
    log_info "🎉 監控檢查完成"
}

# 顯示幫助
show_help() {
    cat << EOF
🔍 Potato Bot ptero 分支同步監控工具

用法: $0 [選項]

選項:
  -h, --help          顯示此幫助訊息
  -r, --report        僅生成報告
  -q, --quiet         靜默模式
  -v, --verbose       詳細輸出

環境變數:
  DISCORD_WEBHOOK_URL  Discord 通知 Webhook URL

範例:
  $0                  # 執行完整監控
  $0 -r               # 僅生成報告
  $0 -q               # 靜默監控

EOF
}

# 主函數
main() {
    local REPORT_ONLY=false
    local QUIET=false
    local VERBOSE=false
    
    # 解析參數
    while [[ $# -gt 0 ]]; do
        case $1 in
            -r|--report)
                REPORT_ONLY=true
                shift
                ;;
            -q|--quiet)
                QUIET=true
                shift
                ;;
            -v|--verbose)
                VERBOSE=true
                set -x
                shift
                ;;
            -h|--help)
                show_help
                exit 0
                ;;
            *)
                echo "未知參數: $1"
                show_help
                exit 1
                ;;
        esac
    done
    
    # 設置日誌級別
    if [ "$QUIET" = "true" ]; then
        exec > /dev/null
    fi
    
    # 執行監控
    monitor
}

# 執行主函數
main "$@"