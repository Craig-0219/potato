#!/bin/bash
# 🚀 Potato Bot Linux/macOS 啟動腳本
# 支援自動環境檢查和依賴安裝

set -e  # 遇到錯誤立即停止

# 顏色定義
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# 獲取腳本目錄
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BOT_FILE="$SCRIPT_DIR/bot/main.py"
ENV_FILE="$SCRIPT_DIR/.env"
ENV_EXAMPLE="$SCRIPT_DIR/.env.example"

print_banner() {
    echo -e "${CYAN}"
    cat << "EOF"
🥔 ═══════════════════════════════════════════════════════════════
   ____        _        _          ____        _
  |  _ \ ___ | |_ __ _| |_ ___   | __ )  ___ | |_
  | |_) / _ \| __/ _` | __/ _ \  |  _ \ / _ \| __|
  |  __/ (_) | || (_| | || (_) | | |_) | (_) | |_
  |_|   \___/ \__\__,_|\__\___/  |____/ \___/ \__|

   🎮 Discord & Minecraft 社群管理平台
   ⚡ v3.2.0 - 專為遊戲社群打造
═══════════════════════════════════════════════════════════════ 🥔
EOF
    echo -e "${NC}"
}

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

check_system() {
    log_info "檢查系統環境..."

    # 檢查作業系統
    case "$(uname -s)" in
        Linux*)
            SYSTEM="Linux"
            log_success "作業系統: Linux"
            ;;
        Darwin*)
            SYSTEM="macOS"
            log_success "作業系統: macOS"
            ;;
        *)
            log_error "不支援的作業系統: $(uname -s)"
            exit 1
            ;;
    esac
}

check_python() {
    log_info "檢查 Python 環境..."

    # 檢查 Python 是否存在
    if ! command -v python3 &> /dev/null; then
        log_error "未找到 python3"
        log_error "請安裝 Python 3.10 或更高版本"
        exit 1
    fi

    # 檢查 Python 版本
    PYTHON_VERSION=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
    log_success "Python 版本: $PYTHON_VERSION"

    # 檢查版本是否符合要求 (>= 3.10)
    if ! python3 -c "import sys; exit(0 if sys.version_info >= (3, 10) else 1)"; then
        log_error "需要 Python 3.10 或更高版本"
        exit 1
    fi

    log_success "Python 版本符合要求"
}

check_environment() {
    log_info "檢查環境設定..."

    if [[ ! -f "$ENV_FILE" ]]; then
        if [[ -f "$ENV_EXAMPLE" ]]; then
            log_warning "未找到 .env 檔案"
            echo -n "是否要從 .env.example 複製設定？(y/n): "
            read -r response
            case "$response" in
                [yY][eE][sS]|[yY]|是)
                    cp "$ENV_EXAMPLE" "$ENV_FILE"
                    log_success "已複製 .env.example 到 .env"
                    log_warning "請編輯 .env 檔案填入您的配置"
                    echo -n "是否要現在編輯 .env 檔案？(y/n): "
                    read -r edit_response
                    case "$edit_response" in
                        [yY][eE][sS]|[yY]|是)
                            ${EDITOR:-nano} "$ENV_FILE"
                            ;;
                    esac
                    ;;
                *)
                    log_error "需要 .env 檔案才能啟動"
                    exit 1
                    ;;
            esac
        else
            log_error "未找到 .env 和 .env.example 檔案"
            exit 1
        fi
    else
        log_success "環境檔案存在"
    fi
}

check_dependencies() {
    log_info "檢查依賴套件..."

    # 檢查 requirements.txt 是否存在
    REQUIREMENTS_FILE="$SCRIPT_DIR/requirements.txt"
    if [[ ! -f "$REQUIREMENTS_FILE" ]]; then
        log_warning "未找到 requirements.txt"
        return 0
    fi

    # 檢查是否需要安裝依賴
    if ! python3 -c "import discord, aiomysql, dotenv, fastapi, uvicorn" 2>/dev/null; then
        log_warning "部分依賴套件缺失"
        echo -n "是否要自動安裝依賴套件？(y/n): "
        read -r response
        case "$response" in
            [yY][eE][sS]|[yY]|是)
                install_dependencies
                ;;
            *)
                log_error "請手動安裝依賴套件: pip3 install -r requirements.txt"
                exit 1
                ;;
        esac
    else
        log_success "所有必要依賴套件已安裝"
    fi
}

install_dependencies() {
    log_info "安裝依賴套件..."

    # 檢查 pip
    if ! command -v pip3 &> /dev/null; then
        log_error "未找到 pip3"
        exit 1
    fi

    # 安裝依賴
    if pip3 install -r "$SCRIPT_DIR/requirements.txt"; then
        log_success "依賴套件安裝完成"
    else
        log_error "依賴套件安裝失敗"
        exit 1
    fi
}

check_bot_file() {
    log_info "檢查 Bot 主程式..."

    if [[ ! -f "$BOT_FILE" ]]; then
        log_error "未找到 bot/main.py"
        exit 1
    fi

    log_success "Bot 主程式存在"
}

show_system_info() {
    echo -e "${CYAN}💻 系統資訊:${NC}"
    echo "   作業系統: $SYSTEM"
    echo "   Python: $PYTHON_VERSION"
    echo "   工作目錄: $SCRIPT_DIR"
    echo "   時間: $(date '+%Y-%m-%d %H:%M:%S')"
}

start_bot() {
    log_info "啟動 Potato Bot..."
    echo -e "${YELLOW}使用 Ctrl+C 停止 Bot${NC}"
    echo "$(printf '=%.0s' {1..50})"

    cd "$SCRIPT_DIR"

    # 設置陷阱來優雅處理中斷信號
    trap 'echo -e "\n\n⏹️  收到停止信號"; exit 0' INT TERM

    if python3 "$BOT_FILE"; then
        log_success "Bot 已正常停止"
        return 0
    else
        log_error "Bot 執行失敗"
        return 1
    fi
}

run_pre_checks() {
    print_banner
    show_system_info

    echo
    log_info "執行啟動前檢查..."

    check_system
    check_python
    check_environment
    check_dependencies
    check_bot_file

    echo
    log_success "所有檢查通過!"
}

show_help() {
    cat << EOF
🚀 Potato Bot 啟動腳本

用法:
    $0 [選項]

選項:
    start, -s          立即啟動 Bot (跳過互動)
    check, -c          只執行環境檢查
    install, -i        只安裝依賴套件
    help, -h, --help   顯示此幫助訊息

範例:
    $0                 # 互動模式啟動
    $0 start          # 直接啟動
    $0 check          # 只檢查環境
    $0 install        # 只安裝依賴

EOF
}

main() {
    # 解析命令列參數
    case "${1:-}" in
        start|-s)
            run_pre_checks
            start_bot
            ;;
        check|-c)
            run_pre_checks
            ;;
        install|-i)
            check_python
            install_dependencies
            ;;
        help|-h|--help)
            show_help
            ;;
        "")
            # 互動模式
            if ! run_pre_checks; then
                exit 1
            fi

            echo "$(printf '=%.0s' {1..50})"
            echo -n "準備就緒! 是否立即啟動 Bot？(y/n): "
            read -r response

            case "$response" in
                [yY][eE][sS]|[yY]|是|"")
                    start_bot
                    ;;
                *)
                    echo
                    log_info "您可以稍後手動執行:"
                    echo "   python3 bot/main.py"
                    echo "   或"
                    echo "   ./start.sh start"
                    ;;
            esac
            ;;
        *)
            log_error "未知選項: $1"
            echo
            show_help
            exit 1
            ;;
    esac
}

# 檢查是否直接執行此腳本
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi
