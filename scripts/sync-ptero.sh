#!/bin/bash
# sync-ptero.sh - 手動同步 main 到 ptero 分支的腳本

set -euo pipefail

# 配置
MAIN_BRANCH="main"
PTERO_BRANCH="ptero"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# 顏色輸出
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

# 顯示幫助資訊
show_help() {
    cat << EOF
🔄 Potato Bot ptero 分支同步工具

用法: $0 [選項]

選項:
  -f, --force         強制同步 (重置 ptero 分支)
  -d, --dry-run       模擬運行，不實際修改
  -s, --status        顯示分支狀態
  -h, --help          顯示此幫助訊息
  -v, --verbose       詳細輸出
  --reset-ptero       完全重置 ptero 分支到簡化版本

範例:
  $0                  # 標準同步
  $0 -f               # 強制同步
  $0 -d               # 預覽同步內容
  $0 -s               # 檢查狀態
  $0 --reset-ptero    # 重置 ptero 分支

EOF
}

# 檢查 Git 狀態
check_git_status() {
    log_info "檢查 Git 狀態..."
    
    if ! git rev-parse --is-inside-work-tree > /dev/null 2>&1; then
        log_error "當前目錄不是 Git 倉庫"
        exit 1
    fi
    
    # 檢查工作目錄是否乾淨
    if [ -n "$(git status --porcelain)" ]; then
        log_warning "工作目錄有未提交的變更"
        echo "未提交的檔案:"
        git status --short
        echo
        read -p "是否繼續? (y/N): " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            log_info "操作已取消"
            exit 0
        fi
    fi
}

# 檢查分支狀態
check_branch_status() {
    log_info "檢查分支狀態..."
    
    # 獲取最新的遠程資訊
    git fetch origin --prune
    
    # 檢查分支是否存在
    if ! git show-ref --verify --quiet refs/heads/$MAIN_BRANCH; then
        if git show-ref --verify --quiet refs/remotes/origin/$MAIN_BRANCH; then
            log_info "本地沒有 $MAIN_BRANCH 分支，從遠程創建..."
            git checkout -b $MAIN_BRANCH origin/$MAIN_BRANCH
        else
            log_error "$MAIN_BRANCH 分支不存在"
            exit 1
        fi
    fi
    
    if ! git show-ref --verify --quiet refs/heads/$PTERO_BRANCH; then
        if git show-ref --verify --quiet refs/remotes/origin/$PTERO_BRANCH; then
            log_info "本地沒有 $PTERO_BRANCH 分支，從遠程創建..."
            git checkout -b $PTERO_BRANCH origin/$PTERO_BRANCH
        else
            log_error "$PTERO_BRANCH 分支不存在"
            exit 1
        fi
    fi
    
    # 計算分支差異
    local commits_behind=$(git rev-list --count $PTERO_BRANCH..$MAIN_BRANCH 2>/dev/null || echo "0")
    local commits_ahead=$(git rev-list --count $MAIN_BRANCH..$PTERO_BRANCH 2>/dev/null || echo "0")
    
    log_info "$PTERO_BRANCH 分支落後 $MAIN_BRANCH 分支 $commits_behind 個提交"
    log_info "$PTERO_BRANCH 分支領先 $MAIN_BRANCH 分支 $commits_ahead 個提交"
    
    if [ "$commits_behind" -eq 0 ]; then
        log_success "$PTERO_BRANCH 分支已是最新"
        return 1
    fi
    
    return 0
}

# 顯示即將同步的內容
show_sync_preview() {
    log_info "即將同步的內容預覽:"
    echo
    
    # 顯示新的提交
    log_info "📝 新的提交:"
    git log --oneline --graph $PTERO_BRANCH..$MAIN_BRANCH | head -10
    echo
    
    # 顯示變更的檔案
    log_info "📁 變更的檔案:"
    git diff --name-status $PTERO_BRANCH..$MAIN_BRANCH | head -20
    echo
}

# 創建 ptero 特有的檔案
create_ptero_files() {
    log_info "創建 ptero 分支特有的檔案..."
    
    # 確保 bot 目錄存在
    mkdir -p bot/services bot/utils
    
    # 創建簡化的 vote_manager.py
    if [ ! -f "bot/services/vote_manager.py" ]; then
        cat > bot/services/vote_manager.py << 'EOF'
# bot/services/vote_manager.py - Ptero 託管版
"""投票管理服務 - 託管部署版本"""

from datetime import datetime
from typing import Dict, Any, List
import discord

class VoteManager:
    """簡化的投票管理器 - 適用於託管環境"""
    
    def __init__(self):
        self.active_votes = {}
    
    async def create_simple_vote(self, title: str, options: List[str]) -> Dict[str, Any]:
        """創建簡單投票"""
        return {
            "title": title,
            "options": options,
            "created_at": datetime.utcnow(),
            "status": "active"
        }
    
    def get_vote_embed(self, vote_data: Dict[str, Any]) -> discord.Embed:
        """生成投票嵌入訊息"""
        embed = discord.Embed(title=vote_data.get("title", "投票"), color=discord.Color.blue())
        options = vote_data.get("options", [])
        for i, option in enumerate(options, 1):
            embed.add_field(name=f"選項 {i}", value=option, inline=False)
        return embed
EOF
        log_success "創建 bot/services/vote_manager.py"
    fi
    
    # 創建簡化的 validator.py
    if [ ! -f "bot/utils/validator.py" ]; then
        cat > bot/utils/validator.py << 'EOF'
# bot/utils/validator.py - Ptero 託管版
"""基本驗證工具 - 託管部署版本"""

import re
from typing import Tuple

def validate_discord_id(discord_id) -> bool:
    """驗證 Discord ID 格式"""
    try:
        if isinstance(discord_id, str):
            if not discord_id.isdigit():
                return False
            discord_id = int(discord_id)
        return 10000000000000000 <= discord_id <= 999999999999999999999
    except (ValueError, TypeError):
        return False

def validate_basic_input(text: str, max_length: int = 1000) -> Tuple[bool, str]:
    """基本輸入驗證"""
    if not text or not isinstance(text, str):
        return False, "輸入不能為空"
    
    if len(text) > max_length:
        return False, f"輸入長度不能超過 {max_length} 字符"
    
    return True, ""

def sanitize_input(text: str, max_length: int = 1000) -> str:
    """清理輸入文本"""
    if not text or not isinstance(text, str):
        return ""
    
    # 移除危險字符
    sanitized = re.sub(r'[<>"\'&]', "", text)
    sanitized = sanitized.strip()
    
    if len(sanitized) > max_length:
        sanitized = sanitized[:max_length]
    
    return sanitized
EOF
        log_success "創建 bot/utils/validator.py"
    fi
}

# 標準同步
sync_standard() {
    log_info "執行標準同步..."
    
    # 切換到 ptero 分支
    git checkout $PTERO_BRANCH
    
    # 嘗試合併 main 分支
    if git merge $MAIN_BRANCH --no-edit; then
        log_success "成功合併 $MAIN_BRANCH 到 $PTERO_BRANCH"
    else
        log_warning "發現合併衝突，嘗試自動解決..."
        
        # 智能衝突解決
        resolve_conflicts
        
        if git add . && git commit --no-edit; then
            log_success "衝突已自動解決並提交"
        else
            log_error "無法自動解決衝突，需要手動處理"
            return 1
        fi
    fi
    
    # 確保 ptero 特有檔案存在
    create_ptero_files
    
    return 0
}

# 強制同步
sync_force() {
    log_info "執行強制同步..."
    
    # 切換到 ptero 分支
    git checkout $PTERO_BRANCH
    
    # 從 main 分支選擇性同步檔案
    log_info "同步核心檔案..."
    git checkout $MAIN_BRANCH -- src/ .env.example requirements.txt pyproject.toml 2>/dev/null || true
    
    # 恢復 ptero 特有的檔案
    log_info "恢復 ptero 特有檔案..."
    if [ -f "README.md.backup" ]; then
        cp README.md.backup README.md
    fi
    
    # 確保 bot 目錄和特有檔案
    create_ptero_files
    
    # 提交變更
    if [ -n "$(git status --porcelain)" ]; then
        git add .
        git commit -m "🔄 強制同步: 更新至 main@$(git rev-parse --short $MAIN_BRANCH)"
        log_success "強制同步完成"
    else
        log_info "沒有變更需要提交"
    fi
    
    return 0
}

# 重置 ptero 分支
reset_ptero() {
    log_warning "這將完全重置 ptero 分支！"
    read -p "確定要繼續嗎? (yes/no): " -r
    if [[ ! $REPLY =~ ^[Yy][Ee][Ss]$ ]]; then
        log_info "操作已取消"
        exit 0
    fi
    
    log_info "重置 ptero 分支..."
    
    # 備份當前的 README.md (如果存在)
    if [ -f "README.md" ]; then
        cp README.md README.md.backup
        log_info "已備份當前的 README.md"
    fi
    
    # 切換到 ptero 分支並重置
    git checkout $PTERO_BRANCH
    git reset --hard $MAIN_BRANCH
    
    # 創建 ptero 專用的 README.md
    cat > README.md << 'EOF'
# 🥔 Potato Bot - 託管部署版

> **精簡的 Discord 機器人託管部署包** - 僅包含運行核心

## 🚀 快速啟動

### 環境需求
- Python 3.10+
- MySQL 8.0+
- Redis (可選)

### 安裝與運行

```bash
# 1. 安裝依賴
pip install -r requirements.txt

# 2. 配置環境變數
cp .env.example .env
# 編輯 .env 填入你的設置

# 3. 啟動機器人
python start.py
```

## 📁 結構說明

```
├── bot/           # 機器人核心功能 (託管版)
├── src/           # 完整源碼模組
├── start.py       # 啟動腳本
├── .env.example   # 環境變數範例
└── requirements.txt # 依賴列表
```

## ⚙️ 主要功能

- 🎫 票券系統
- 🗳️ 投票系統  
- 🤖 AI 助手
- 🎮 遊戲整合
- 📊 數據分析

## 📝 License

MIT License - 詳見 LICENSE 檔案
EOF
    
    # 創建 ptero 特有檔案
    create_ptero_files
    
    # 提交重置後的變更
    git add .
    git commit -m "🔄 重置 ptero 分支: 精簡託管部署版本"
    
    log_success "ptero 分支重置完成"
}

# 解決衝突
resolve_conflicts() {
    log_info "智能解決合併衝突..."
    
    # ptero 特有檔案 - 保留 ptero 版本
    if [ -f "README.md" ]; then
        git checkout --theirs README.md || true
        log_info "保留 ptero 版本的 README.md"
    fi
    
    if [ -f "start.py" ]; then
        git checkout --theirs start.py || true
        log_info "保留 ptero 版本的 start.py"
    fi
    
    # 對於 bot 目錄，保留 ptero 版本
    if [ -d "bot" ]; then
        git checkout --theirs bot/ 2>/dev/null || true
        log_info "保留 ptero 版本的 bot 目錄"
    fi
    
    # 其他檔案使用 main 版本
    git checkout --ours src/ .env.example requirements.txt pyproject.toml 2>/dev/null || true
}

# 推送變更
push_changes() {
    if [ "$DRY_RUN" = "true" ]; then
        log_info "[DRY RUN] 將推送以下變更:"
        git log --oneline origin/$PTERO_BRANCH..$PTERO_BRANCH 2>/dev/null || true
        return 0
    fi
    
    read -p "是否推送變更到遠程? (y/N): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        git push origin $PTERO_BRANCH
        log_success "變更已推送到遠程 $PTERO_BRANCH 分支"
    else
        log_info "變更僅在本地，未推送到遠程"
    fi
}

# 主函數
main() {
    local FORCE=false
    local DRY_RUN=false
    local STATUS_ONLY=false
    local VERBOSE=false
    local RESET_PTERO=false
    
    # 解析參數
    while [[ $# -gt 0 ]]; do
        case $1 in
            -f|--force)
                FORCE=true
                shift
                ;;
            -d|--dry-run)
                DRY_RUN=true
                shift
                ;;
            -s|--status)
                STATUS_ONLY=true
                shift
                ;;
            -v|--verbose)
                VERBOSE=true
                set -x
                shift
                ;;
            --reset-ptero)
                RESET_PTERO=true
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
    
    log_info "🔄 Potato Bot ptero 分支同步工具"
    echo
    
    # 檢查 Git 狀態
    check_git_status
    
    # 檢查分支狀態
    if ! check_branch_status && [ "$STATUS_ONLY" = "false" ]; then
        exit 0
    fi
    
    # 如果只是查看狀態，到此結束
    if [ "$STATUS_ONLY" = "true" ]; then
        exit 0
    fi
    
    # 顯示同步預覽
    if [ "$DRY_RUN" = "true" ] || [ "$VERBOSE" = "true" ]; then
        show_sync_preview
    fi
    
    # 如果是 dry run，到此結束
    if [ "$DRY_RUN" = "true" ]; then
        log_info "[DRY RUN] 預覽完成，沒有實際修改"
        exit 0
    fi
    
    # 執行同步
    if [ "$RESET_PTERO" = "true" ]; then
        reset_ptero
    elif [ "$FORCE" = "true" ]; then
        sync_force
    else
        sync_standard
    fi
    
    # 推送變更
    push_changes
    
    log_success "🎉 同步完成！"
}

# 執行主函數
main "$@"