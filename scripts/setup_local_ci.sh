#!/bin/bash
# 設置本地 CI/CD 環境腳本
# 安裝所有必要的工具和依賴

set -e

# 顏色定義
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
NC='\033[0m' # No Color

# 日誌函數
log_header() {
    echo -e "${PURPLE}========================${NC}"
    echo -e "${PURPLE}$1${NC}"
    echo -e "${PURPLE}========================${NC}"
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

# 檢查 Python 環境
check_python_environment() {
    log_header "檢查 Python 環境"

    # 檢查 Python 版本
    if command -v python3 &> /dev/null; then
        PYTHON_VERSION=$(python3 --version | cut -d' ' -f2)
        log_info "Python 版本: $PYTHON_VERSION"

        # 檢查是否為 Python 3.10+
        if python3 -c "import sys; exit(0 if sys.version_info >= (3, 10) else 1)" 2>/dev/null; then
            log_success "✅ Python 版本符合要求 (≥3.10)"
        else
            log_warning "⚠️ Python 版本較舊，建議升級到 3.10+"
        fi
    else
        log_error "❌ Python3 未安裝"
        return 1
    fi

    # 檢查 pip
    if command -v pip3 &> /dev/null; then
        PIP_VERSION=$(pip3 --version | cut -d' ' -f2)
        log_info "pip 版本: $PIP_VERSION"
        log_success "✅ pip 已安裝"
    else
        log_error "❌ pip3 未安裝"
        return 1
    fi

    return 0
}

# 安裝代碼品質工具
install_code_quality_tools() {
    log_header "安裝代碼品質工具"

    TOOLS=(
        "black>=23.0.0"          # 代碼格式化
        "isort>=5.12.0"          # 導入排序
        "autoflake>=2.0.0"       # 移除未使用導入
        "flake8>=6.0.0"          # 語法檢查
        "mypy>=1.5.0"            # 類型檢查
        "types-requests"         # requests 類型註解
        "types-PyYAML"           # PyYAML 類型註解
    )

    log_info "安裝代碼品質工具..."
    for tool in "${TOOLS[@]}"; do
        log_info "安裝: $tool"
        if pip3 install "$tool" --upgrade; then
            log_success "✅ $tool 安裝成功"
        else
            log_warning "⚠️ $tool 安裝失敗"
        fi
    done
}

# 安裝安全掃描工具
install_security_tools() {
    log_header "安裝安全掃描工具"

    SECURITY_TOOLS=(
        "bandit[toml]>=1.7.0"    # SAST 掃描
        "safety>=2.0.0"          # 依賴漏洞掃描
        "pip-audit>=2.6.0"       # 官方依賴審計
        "detect-secrets>=1.4.0"  # 敏感資訊檢測
    )

    log_info "安裝安全掃描工具..."
    for tool in "${SECURITY_TOOLS[@]}"; do
        log_info "安裝: $tool"
        if pip3 install "$tool" --upgrade; then
            log_success "✅ $tool 安裝成功"
        else
            log_warning "⚠️ $tool 安裝失敗"
        fi
    done
}

# 安裝測試工具
install_testing_tools() {
    log_header "安裝測試工具"

    TEST_TOOLS=(
        "pytest>=7.0.0"         # 測試框架
        "pytest-cov>=4.0.0"     # 覆蓋率
        "pytest-asyncio>=0.21.0" # 異步測試
        "pytest-mock>=3.10.0"   # Mock 支援
        "coverage[toml]>=7.0.0"  # 覆蓋率工具
    )

    log_info "安裝測試工具..."
    for tool in "${TEST_TOOLS[@]}"; do
        log_info "安裝: $tool"
        if pip3 install "$tool" --upgrade; then
            log_success "✅ $tool 安裝成功"
        else
            log_warning "⚠️ $tool 安裝失敗"
        fi
    done
}

# 安裝 pre-commit
install_precommit() {
    log_header "安裝 Pre-commit Hooks"

    # 安裝 pre-commit
    if pip3 install pre-commit --upgrade; then
        log_success "✅ pre-commit 安裝成功"
    else
        log_error "❌ pre-commit 安裝失敗"
        return 1
    fi

    # 安裝 hooks
    if pre-commit install; then
        log_success "✅ pre-commit hooks 已安裝"
    else
        log_error "❌ pre-commit hooks 安裝失敗"
        return 1
    fi

    # 安裝 pre-push hooks
    if pre-commit install --hook-type pre-push; then
        log_success "✅ pre-push hooks 已安裝"
    else
        log_warning "⚠️ pre-push hooks 安裝失敗"
    fi

    return 0
}

# 創建配置文件
create_config_files() {
    log_header "創建配置文件"

    # 創建 .flake8 配置
    if [ ! -f ".flake8" ]; then
        log_info "創建 .flake8 配置文件..."
        cat > .flake8 << 'EOF'
[flake8]
max-line-length = 100
max-complexity = 12
ignore =
    E203,  # whitespace before ':'
    W503,  # line break before binary operator
extend-ignore = E203, W503
exclude =
    .git,
    __pycache__,
    migrations,
    archive,
    .venv,
    venv,
    .pytest_cache
per-file-ignores =
    __init__.py:F401  # 允許 __init__.py 中未使用的導入
EOF
        log_success "✅ .flake8 配置文件已創建"
    else
        log_info ".flake8 配置文件已存在"
    fi

    # 創建 .bandit 配置
    if [ ! -f ".bandit" ]; then
        log_info "創建 .bandit 配置文件..."
        cat > .bandit << 'EOF'
[bandit]
exclude_dirs = ["tests", "migrations", "archive"]
skips = ["B101", "B601"]  # 跳過 assert 和 shell 檢查
EOF
        log_success "✅ .bandit 配置文件已創建"
    else
        log_info ".bandit 配置文件已存在"
    fi

    # 創建 .coveragerc 配置
    if [ ! -f ".coveragerc" ]; then
        log_info "創建 .coveragerc 配置文件..."
        cat > .coveragerc << 'EOF'
[run]
source = bot, shared
omit =
    */migrations/*
    */tests/*
    */venv/*
    */__pycache__/*
    */archive/*

[report]
exclude_lines =
    pragma: no cover
    def __repr__
    raise AssertionError
    raise NotImplementedError
    if __name__ == .__main__.:
    if TYPE_CHECKING:

[html]
directory = htmlcov

[xml]
output = coverage.xml
EOF
        log_success "✅ .coveragerc 配置文件已創建"
    else
        log_info ".coveragerc 配置文件已存在"
    fi
}

# 初始化 secrets baseline
initialize_secrets_baseline() {
    log_header "初始化 Secrets Baseline"

    if [ ! -f ".secrets.baseline" ]; then
        log_info "創建 secrets baseline..."
        if detect-secrets scan --all-files --force-use-all-plugins > .secrets.baseline; then
            log_success "✅ Secrets baseline 已創建"
        else
            log_warning "⚠️ Secrets baseline 創建失敗"
        fi
    else
        log_info "Secrets baseline 已存在"

        # 更新 baseline
        log_info "更新 secrets baseline..."
        if detect-secrets scan --baseline .secrets.baseline; then
            log_success "✅ Secrets baseline 已更新"
        else
            log_warning "⚠️ Secrets baseline 更新失敗"
        fi
    fi
}

# 驗證安裝
verify_installation() {
    log_header "驗證安裝"

    TOOLS_TO_CHECK=(
        "black --version"
        "isort --version"
        "autoflake --version"
        "flake8 --version"
        "mypy --version"
        "bandit --version"
        "safety --version"
        "pip-audit --version"
        "detect-secrets --version"
        "pytest --version"
        "coverage --version"
        "pre-commit --version"
    )

    log_info "檢查已安裝的工具..."

    success_count=0
    total_count=${#TOOLS_TO_CHECK[@]}

    for tool_cmd in "${TOOLS_TO_CHECK[@]}"; do
        tool_name=$(echo "$tool_cmd" | cut -d' ' -f1)
        if eval "$tool_cmd" > /dev/null 2>&1; then
            log_success "✅ $tool_name"
            ((success_count++))
        else
            log_error "❌ $tool_name"
        fi
    done

    log_info "安裝檢查完成: $success_count/$total_count 工具可用"

    if [ $success_count -eq $total_count ]; then
        log_success "🎉 所有工具安裝成功！"
        return 0
    else
        log_warning "⚠️ 部分工具安裝失敗"
        return 1
    fi
}

# 創建使用指南
create_usage_guide() {
    log_header "創建使用指南"

    cat > LOCAL_CI_USAGE.md << 'EOF'
# 本地 CI/CD 使用指南

## 🚀 快速開始

### 1. 執行完整本地測試
```bash
# 執行所有 CI/CD 檢查
python scripts/local_ci_test.py

# 或使用簡化命令
./scripts/local_ci_test.py
```

### 2. 代碼格式修復
```bash
# 自動修復代碼格式問題
./scripts/local_format_fix.sh

# 手動格式化
black .
isort .
autoflake --remove-all-unused-imports --in-place --recursive .
```

### 3. 安全檢查
```bash
# 執行安全掃描
python scripts/local_security_check.py

# 或手動執行
bandit -r . -f json
safety check --json
detect-secrets scan --all-files
```

### 4. 測試執行
```bash
# 執行所有測試
pytest tests/ -v

# 帶覆蓋率的測試
pytest tests/ --cov=bot --cov=shared --cov-report=html

# 快速測試
pytest tests/ -x --tb=short
```

### 5. Pre-commit Hooks
```bash
# 手動執行所有 hooks
pre-commit run --all-files

# 更新 hooks
pre-commit autoupdate

# 跳過特定 hook
SKIP=mypy git commit -m "提交訊息"
```

## 🛠️ 工具說明

### 代碼品質工具
- **Black**: 代碼格式化
- **isort**: 導入排序
- **autoflake**: 移除未使用導入
- **flake8**: 語法檢查
- **mypy**: 類型檢查

### 安全工具
- **Bandit**: Python SAST 掃描
- **Safety**: 依賴漏洞掃描
- **pip-audit**: 官方依賴審計
- **detect-secrets**: 敏感資訊檢測

### 測試工具
- **pytest**: 測試框架
- **coverage**: 覆蓋率分析
- **pytest-cov**: 測試覆蓋率整合

## 📋 常見問題

### Q: Pre-commit hooks 太慢怎麼辦？
A: 可以跳過耗時的檢查：
```bash
SKIP=mypy,bandit git commit -m "快速提交"
```

### Q: 如何修復格式問題？
A: 使用自動修復腳本：
```bash
./scripts/local_format_fix.sh
```

### Q: 測試失敗怎麼辦？
A: 查看詳細錯誤並修復：
```bash
pytest tests/ -v --tb=long
```

### Q: 如何更新工具版本？
A: 重新執行安裝腳本：
```bash
./scripts/setup_local_ci.sh
```

## 📊 生成的報告

- **覆蓋率報告**: `htmlcov/index.html`
- **安全掃描報告**: `security_reports/`
- **測試報告**: 控制台輸出

## ⚡ 提示

1. **提交前**: 執行 `python scripts/local_ci_test.py` 確保通過所有檢查
2. **格式問題**: 使用 `./scripts/local_format_fix.sh` 快速修復
3. **安全問題**: 查看 `security_reports/` 目錄的詳細報告
4. **覆蓋率**: 目標保持在 70% 以上

---
🎯 **目標**: 在本地環境中達到與 CI/CD 相同的品質標準
EOF

    log_success "✅ 使用指南已創建: LOCAL_CI_USAGE.md"
}

# 主執行流程
main() {
    log_header "本地 CI/CD 環境設置"
    echo "此腳本將安裝所有必要的代碼品質、安全和測試工具"
    echo

    # 檢查 Python 環境
    if ! check_python_environment; then
        log_error "Python 環境檢查失敗，請先安裝 Python 3.10+"
        exit 1
    fi

    # 安裝工具
    install_code_quality_tools
    install_security_tools
    install_testing_tools
    install_precommit

    # 創建配置文件
    create_config_files
    initialize_secrets_baseline

    # 驗證安裝
    if verify_installation; then
        create_usage_guide

        log_header "設置完成"
        log_success "🎉 本地 CI/CD 環境設置完成！"
        log_info "📖 查看使用指南: LOCAL_CI_USAGE.md"
        log_info "🧪 執行測試: python scripts/local_ci_test.py"
        log_info "🎨 修復格式: ./scripts/local_format_fix.sh"
        log_info "🛡️ 安全檢查: python scripts/local_security_check.py"

        exit 0
    else
        log_error "❌ 部分工具安裝失敗，請檢查錯誤訊息"
        exit 1
    fi
}

# 執行主函數
main "$@"
