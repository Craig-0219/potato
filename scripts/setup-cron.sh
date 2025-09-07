#!/bin/bash
# setup-cron.sh - 設置定期同步監控的 cron 任務

set -euo pipefail

# 配置
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
MONITOR_SCRIPT="$SCRIPT_DIR/monitor-sync.sh"
SYNC_SCRIPT="$SCRIPT_DIR/sync-ptero.sh"

# 顏色輸出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

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

# 顯示幫助
show_help() {
    cat << EOF
🕐 Potato Bot ptero 分支同步監控 Cron 設置工具

用法: $0 [選項]

選項:
  --install           安裝 cron 任務
  --remove            移除 cron 任務
  --status            顯示當前 cron 任務狀態
  --test              測試腳本功能
  -h, --help          顯示此幫助訊息

預設 Cron 計畫:
  - 每4小時監控同步狀態
  - 每日凌晨2點自動同步 (如果需要)
  - 每週日生成詳細報告

EOF
}

# 檢查腳本權限
check_scripts() {
    log_info "檢查腳本權限..."
    
    if [ ! -x "$MONITOR_SCRIPT" ]; then
        log_warning "monitor-sync.sh 不可執行，正在修復..."
        chmod +x "$MONITOR_SCRIPT"
    fi
    
    if [ ! -x "$SYNC_SCRIPT" ]; then
        log_warning "sync-ptero.sh 不可執行，正在修復..."
        chmod +x "$SYNC_SCRIPT"
    fi
    
    log_success "腳本權限檢查完成"
}

# 創建日誌目錄
create_log_dirs() {
    log_info "創建日誌目錄..."
    mkdir -p "$PROJECT_ROOT/logs/cron"
    log_success "日誌目錄已創建: $PROJECT_ROOT/logs/cron"
}

# 安裝 cron 任務
install_cron() {
    log_info "安裝 ptero 分支同步監控 cron 任務..."
    
    # 檢查是否已存在相關任務
    if crontab -l 2>/dev/null | grep -q "potato.*ptero.*sync"; then
        log_warning "發現現有的 ptero 同步 cron 任務"
        read -p "是否要替換現有任務? (y/N): " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            log_info "安裝已取消"
            return 0
        fi
        
        # 移除現有任務
        crontab -l 2>/dev/null | grep -v "potato.*ptero.*sync" | crontab - || true
        log_info "已移除現有任務"
    fi
    
    # 準備新的 cron 任務
    local cron_jobs="
# Potato Bot ptero 分支自動同步監控
# 每4小時檢查同步狀態
0 */4 * * * $MONITOR_SCRIPT --quiet >> $PROJECT_ROOT/logs/cron/monitor.log 2>&1

# 每日凌晨2點執行自動同步檢查
30 2 * * * $SYNC_SCRIPT --status >> $PROJECT_ROOT/logs/cron/sync.log 2>&1

# 每週日早上生成詳細報告
0 6 * * 0 $MONITOR_SCRIPT --report >> $PROJECT_ROOT/logs/cron/weekly-report.log 2>&1"
    
    # 合併現有 crontab (如果有) 和新任務
    {
        crontab -l 2>/dev/null || true
        echo "$cron_jobs"
    } | crontab -
    
    log_success "cron 任務已安裝"
    log_info "已安裝的任務:"
    crontab -l | grep -A3 -B1 "Potato Bot ptero"
}

# 移除 cron 任務
remove_cron() {
    log_info "移除 ptero 分支同步監控 cron 任務..."
    
    if ! crontab -l 2>/dev/null | grep -q "potato.*ptero.*sync\|Potato Bot ptero"; then
        log_warning "沒有找到相關的 cron 任務"
        return 0
    fi
    
    # 移除相關任務
    crontab -l 2>/dev/null | grep -v -E "potato.*ptero.*sync|Potato Bot ptero|每.*小時檢查同步狀態|每日凌晨.*自動同步|每週.*生成.*報告" | crontab - || true
    
    log_success "cron 任務已移除"
}

# 顯示 cron 狀態
show_status() {
    log_info "當前 ptero 同步相關 cron 任務:"
    echo
    
    if crontab -l 2>/dev/null | grep -q -E "potato.*ptero|Potato Bot ptero"; then
        crontab -l | grep -A5 -B1 -E "potato.*ptero|Potato Bot ptero" || true
        echo
        log_info "相關日誌文件:"
        ls -la "$PROJECT_ROOT/logs/cron/" 2>/dev/null || log_warning "日誌目錄不存在"
    else
        log_warning "沒有找到 ptero 同步相關的 cron 任務"
    fi
}

# 測試腳本功能
test_scripts() {
    log_info "測試同步監控腳本功能..."
    
    log_info "1. 測試監控腳本..."
    if "$MONITOR_SCRIPT" --help > /dev/null; then
        log_success "監控腳本功能正常"
    else
        log_error "監控腳本測試失敗"
        return 1
    fi
    
    log_info "2. 測試同步腳本..."
    if "$SYNC_SCRIPT" --help > /dev/null; then
        log_success "同步腳本功能正常"
    else
        log_error "同步腳本測試失敗"
        return 1
    fi
    
    log_info "3. 測試監控報告生成..."
    if "$MONITOR_SCRIPT" --report --quiet; then
        log_success "監控報告生成功能正常"
    else
        log_error "監控報告生成失敗"
        return 1
    fi
    
    log_success "🎉 所有腳本功能測試通過"
}

# 創建服務配置文件 (systemd timer 替代方案)
create_systemd_timer() {
    log_info "創建 systemd timer 配置 (cron 的替代方案)..."
    
    local service_file="/etc/systemd/system/potato-ptero-sync.service"
    local timer_file="/etc/systemd/system/potato-ptero-sync.timer"
    
    # 檢查權限
    if [ "$EUID" -ne 0 ]; then
        log_error "需要 root 權限才能創建 systemd 服務"
        log_info "請使用 sudo 運行此腳本，或使用 cron 模式"
        return 1
    fi
    
    # 創建服務文件
    cat > "$service_file" << EOF
[Unit]
Description=Potato Bot ptero 分支同步監控
After=network.target

[Service]
Type=oneshot
User=$(whoami)
WorkingDirectory=$PROJECT_ROOT
ExecStart=$MONITOR_SCRIPT --quiet
StandardOutput=journal
StandardError=journal
EOF
    
    # 創建定時器文件
    cat > "$timer_file" << EOF
[Unit]
Description=Potato Bot ptero 同步監控定時器
Requires=potato-ptero-sync.service

[Timer]
OnCalendar=*-*-* 02,06,10,14,18,22:00:00
Persistent=true

[Install]
WantedBy=timers.target
EOF
    
    # 重新載入 systemd 並啟用
    systemctl daemon-reload
    systemctl enable potato-ptero-sync.timer
    systemctl start potato-ptero-sync.timer
    
    log_success "systemd timer 已創建並啟用"
    log_info "查看狀態: systemctl status potato-ptero-sync.timer"
    log_info "查看日誌: journalctl -u potato-ptero-sync.service"
}

# 主函數
main() {
    local ACTION=""
    
    # 解析參數
    while [[ $# -gt 0 ]]; do
        case $1 in
            --install)
                ACTION="install"
                shift
                ;;
            --remove)
                ACTION="remove"
                shift
                ;;
            --status)
                ACTION="status"
                shift
                ;;
            --test)
                ACTION="test"
                shift
                ;;
            --systemd)
                ACTION="systemd"
                shift
                ;;
            -h|--help)
                show_help
                exit 0
                ;;
            *)
                log_error "未知參數: $1"
                show_help
                exit 1
                ;;
        esac
    done
    
    # 如果沒有指定動作，顯示幫助
    if [ -z "$ACTION" ]; then
        show_help
        exit 0
    fi
    
    log_info "🕐 Potato Bot ptero 分支同步監控 Cron 設置"
    echo
    
    # 預備工作
    check_scripts
    create_log_dirs
    
    # 執行相應動作
    case $ACTION in
        install)
            install_cron
            ;;
        remove)
            remove_cron
            ;;
        status)
            show_status
            ;;
        test)
            test_scripts
            ;;
        systemd)
            create_systemd_timer
            ;;
        *)
            log_error "未實現的動作: $ACTION"
            exit 1
            ;;
    esac
    
    log_success "操作完成！"
}

# 執行主函數
main "$@"