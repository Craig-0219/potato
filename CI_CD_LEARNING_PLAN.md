# CI/CD 重構學習計劃書
**版本**: v1.0  
**日期**: 2025-08-27  
**目標**: 建立現代化 CI/CD 管道並深度學習相關技術  

## 🎯 核心原則

### 效能目標
- **PR 執行時間 ≤ 10 分鐘** - 快速反饋循環
- **並行執行** - 最大化流水線效率
- **智能緩存** - 減少重複計算

### 品質保證
- **多層驗證** - Lint、Test、SAST、Build 全覆蓋
- **覆蓋率門檻** - 最低 70% 代碼覆蓋率
- **安全掃描** - 靜態分析 + 供應鏈掃描

### 安全性
- **分環境管理** - Development、Staging、Production
- **OIDC 最小權限** - 零長期 Token
- **Secrets 分離** - 環境隔離 + 輪換機制

### 可追蹤性
- **Artifact 管理** - 含 SBOM 的可重現構建
- **失敗通知** - 精確定位錯誤與修復連結
- **完整審計日誌** - 所有操作可追溯

---

## 📋 現狀分析

### 🟢 現有優勢
- ✅ 基礎 CI 覆蓋 75% 功能測試
- ✅ 自動合併機制運行正常
- ✅ 多層測試架構 (語法→配置→Cogs→服務→整合)
- ✅ 乾淨的部署流程

### 🟡 待改進項目
- ⚠️ 缺少 Lint 和 Format 檢查
- ⚠️ 無 SAST 靜態安全分析
- ⚠️ 沒有覆蓋率報告
- ⚠️ 缺少 Artifact 生成
- ⚠️ Secrets 管理不完善

### 🔴 關鍵缺失
- ❌ 無分支保護規則
- ❌ 無供應鏈掃描
- ❌ 通知系統不夠精確
- ❌ 無 OIDC 集成

---

## 🏗️ 重構架構設計

### CI/CD 流水線完整架構

```
PR 觸發流水線 (≤ 10 分鐘)
├── Stage 1: 靜態分析 (2-3 分鐘)
│   ├── 📝 Code Format Check
│   │   ├── black --check .
│   │   ├── isort --check-only .
│   │   └── autoflake --check .
│   │
│   ├── 🔍 Lint Analysis
│   │   ├── flake8 . --max-line-length=88
│   │   ├── pylint bot/ shared/
│   │   └── mypy bot/ shared/
│   │
│   └── 📋 Import Sorting
│       └── isort --diff --check-only .
│
├── Stage 2: 安全掃描 (2-3 分鐘)
│   ├── 🛡️ SAST (Static Application Security Testing)
│   │   ├── bandit -r . --format json
│   │   ├── semgrep --config=auto .
│   │   └── safety check --json
│   │
│   ├── 🔐 Secrets Detection
│   │   ├── detect-secrets scan .
│   │   ├── gitleaks detect --source .
│   │   └── truffleHog filesystem .
│   │
│   └── 📦 Dependency Security
│       ├── pip-audit --format=json
│       └── snyk test --json
│
├── Stage 3: 測試執行 (3-4 分鐘)
│   ├── 🧪 Unit Tests
│   │   ├── pytest tests/unit/ -v
│   │   ├── pytest tests/integration/ -v
│   │   └── pytest tests/e2e/ --maxfail=3
│   │
│   ├── 📊 Coverage Analysis
│   │   ├── pytest --cov=bot --cov=shared
│   │   ├── coverage report --show-missing
│   │   └── coverage xml (for reports)
│   │
│   └── 🏃 Performance Tests
│       ├── pytest tests/performance/ --benchmark-only
│       └── memory profiling tests
│
└── Stage 4: 構建與 Artifact (1-2 分鐘)
    ├── 🐳 Docker Build Test
    │   ├── docker build --tag test-image .
    │   └── docker run --rm test-image pytest --version
    │
    ├── 📦 Artifact Generation
    │   ├── pip freeze > requirements-lock.txt
    │   ├── generate build metadata
    │   └── create deployment package
    │
    └── 📋 SBOM Generation
        ├── syft . -o spdx-json=sbom.spdx.json
        └── cyclonedx-py -o sbom-cyclone.json

合併後觸發 (main 分支)
├── 🚀 Production Build
├── 🔄 Automated Deployment
├── 📊 Health Checks
└── 📢 Success Notifications

夜間定時任務 (深度掃描)
├── 🔍 Extended Security Scans
├── 📈 Dependency Updates Check  
├── 🧪 Long-running Tests
└── 📊 Supply Chain Analysis
```

---

## 🔧 技術深度學習指南

### 學習階段 1: 代碼品質工具詳解

#### 1.1 Python 代碼格式化生態系統

**Black - 不妥協的代碼格式化器**
```bash
# 安裝
pip install black

# 基本使用
black .                    # 格式化所有 .py 文件
black --check .            # 檢查模式 (CI 使用)
black --diff .             # 顯示差異但不修改

# 配置文件 pyproject.toml
[tool.black]
line-length = 88           # 行長度 (默認)
target-version = ['py310'] # Python 版本
include = '\.pyi?$'        # 包含的文件模式
extend-exclude = '''       # 排除的文件
/(
  | migrations
  | venv
  | \.git
)/
'''
```

**isort - 導入語句排序**
```bash
# 安裝和使用
pip install isort
isort .                    # 排序所有導入
isort --check-only .       # 檢查模式
isort --diff .             # 顯示差異

# 配置 (與 black 兼容)
[tool.isort]
profile = "black"          # 使用 black 兼容配置
multi_line_output = 3      # 多行導入格式
line_length = 88
known_first_party = ["bot", "shared"]
sections = ["FUTURE", "STDLIB", "THIRDPARTY", "FIRSTPARTY", "LOCALFOLDER"]
```

**autoflake - 移除未使用的導入和變量**
```bash
pip install autoflake
autoflake --remove-all-unused-imports --recursive .
autoflake --check --recursive .  # CI 檢查模式
```

#### 1.2 靜態代碼分析工具

**flake8 - 風格指南執行器**
```bash
pip install flake8
flake8 .

# 配置文件 .flake8 或 setup.cfg
[flake8]
max-line-length = 88
max-complexity = 10
ignore = 
    E203,  # whitespace before ':'
    W503,  # line break before binary operator
extend-ignore = E203, W503
exclude = 
    .git,
    __pycache__,
    migrations
per-file-ignores =
    __init__.py:F401  # 允許 __init__.py 中未使用的導入
```

**pylint - 深度代碼分析**
```bash
pip install pylint
pylint bot/ shared/

# 配置文件 .pylintrc
[MAIN]
jobs=0                     # 使用所有 CPU 核心

[FORMAT]
max-line-length=88

[MESSAGES CONTROL]
disable=
    missing-module-docstring,
    missing-class-docstring,
    missing-function-docstring,
    too-few-public-methods,
    import-error

[DESIGN]
max-args=7
max-locals=20
```

**mypy - 靜態類型檢查**
```bash
pip install mypy
mypy bot/ shared/

# 配置文件 mypy.ini 或 pyproject.toml
[tool.mypy]
python_version = "3.10"
warn_return_any = true
warn_unused_configs = true
disallow_untyped_defs = true
disallow_incomplete_defs = true
check_untyped_defs = true
disallow_untyped_decorators = true

[[tool.mypy.overrides]]
module = ["discord.*", "aiomysql.*"]
ignore_missing_imports = true
```

#### 1.3 實際 CI 配置示例

```yaml
name: 🎨 Code Quality Checks

on:
  pull_request:
    branches: [main, dev]
  push:
    branches: [main, dev]

jobs:
  code-quality:
    runs-on: ubuntu-latest
    timeout-minutes: 10
    
    strategy:
      matrix:
        python-version: ["3.10", "3.11"]  # 多版本測試
    
    steps:
    - uses: actions/checkout@v4
    
    - name: Set up Python ${{ matrix.python-version }}
      uses: actions/setup-python@v4
      with:
        python-version: ${{ matrix.python-version }}
        cache: 'pip'
        
    - name: Install dependencies
      run: |
        python -m pip install --upgrade pip
        pip install black isort autoflake flake8 pylint mypy
        pip install -r requirements.txt
        
    - name: Format Check
      run: |
        echo "🎨 檢查代碼格式..."
        black --check --diff .
        isort --check-only --diff .
        autoflake --check --recursive .
        
    - name: Lint Analysis
      run: |
        echo "🔍 執行 Lint 分析..."
        flake8 . --statistics --tee --output-file=flake8-report.txt
        pylint bot/ shared/ --output-format=text --reports=yes | tee pylint-report.txt
        
    - name: Type Checking
      run: |
        echo "🔍 類型檢查..."
        mypy bot/ shared/ --html-report mypy-report
        
    - name: Upload Reports
      if: always()
      uses: actions/upload-artifact@v3
      with:
        name: code-quality-reports
        path: |
          flake8-report.txt
          pylint-report.txt
          mypy-report/
```

### 學習階段 2: 安全掃描深度解析

#### 2.1 SAST (靜態應用安全測試) 工具

**Bandit - Python 安全漏洞掃描**
```bash
pip install bandit[toml]
bandit -r . -f json -o bandit-report.json

# 配置文件 pyproject.toml
[tool.bandit]
exclude_dirs = ["tests", "migrations"]
skips = ["B101", "B601"]   # 跳過特定檢查
```

**常見 Bandit 檢查項目**:
- `B101`: assert_used - 避免在生產代碼中使用 assert
- `B102`: exec_used - 危險的 exec() 使用
- `B103`: set_bad_file_permissions - 不安全的文件權限
- `B201`: flask_debug_true - Flask debug=True
- `B301`: pickle - 不安全的反序列化
- `B501`: request_with_no_cert_validation - 跳過證書驗證
- `B601`: paramiko_calls - 不安全的 SSH 調用
- `B602`: subprocess_popen_with_shell_equals_true - shell注入風險

**實際修復示例**:
```python
# ❌ Bandit B102: exec_used
def bad_code():
    user_input = get_user_input()
    exec(user_input)  # 危險！

# ✅ 修復後
def good_code():
    user_input = get_user_input()
    # 使用白名單方式驗證輸入
    if user_input in ALLOWED_COMMANDS:
        execute_safe_command(user_input)
    else:
        raise ValueError("Invalid command")

# ❌ Bandit B501: 跳過證書驗證
import requests
requests.get('https://example.com', verify=False)  # 危險！

# ✅ 修復後
import requests
requests.get('https://example.com', verify=True)  # 或使用自定義 CA
```

**Semgrep - 語義搜索引擎**
```bash
pip install semgrep
semgrep --config=auto .    # 自動規則
semgrep --config=p/python .  # Python 專用規則
```

**自定義 Semgrep 規則示例**:
```yaml
# .semgrep/discord-bot-rules.yml
rules:
  - id: discord-token-hardcoded
    pattern: |
      bot.run("...")
    message: "Discord token should not be hardcoded"
    severity: ERROR
    languages: [python]
    
  - id: dangerous-eval
    pattern: eval(...)
    message: "Use of eval() is dangerous"
    severity: ERROR
    languages: [python]
    
  - id: sql-injection-risk
    pattern: |
      cursor.execute("... {} ...".format($VAR))
    message: "Potential SQL injection vulnerability"
    severity: WARNING
    languages: [python]
```

#### 2.2 依賴安全掃描

**Safety - Python 包漏洞數據庫**
```bash
pip install safety
safety check                    # 基本掃描
safety check --json             # JSON 格式輸出
safety check --full-report      # 完整報告
```

**pip-audit - 官方推薦工具**
```bash
pip install pip-audit
pip-audit --format=json --output=audit-report.json
pip-audit --desc                # 顯示漏洞描述
pip-audit --fix                 # 自動修復 (謹慎使用)
```

**Snyk - 企業級安全掃描**
```bash
npm install -g snyk
snyk auth                       # 首次認證
snyk test --json               # 掃描並生成 JSON 報告
snyk monitor                   # 持續監控
snyk fix                       # 自動修復建議
```

#### 2.3 Secrets 檢測和管理

**detect-secrets - 防止意外提交敏感資料**
```bash
pip install detect-secrets
detect-secrets scan --all-files --force-use-all-plugins > .secrets.baseline
detect-secrets audit .secrets.baseline  # 審計發現的 secrets
```

**GitLeaks - Git 歷史掃描**
```bash
# 使用 Docker 運行
docker run -v "$PWD:/path" zricethezav/gitleaks:latest detect --source="/path" -v

# 配置文件 .gitleaks.toml
[extend]
useDefault = true

[[rules]]
id = "discord-bot-token"
description = "Discord Bot Token"
regex = '''[MN][A-Za-z\d]{23}\.[\w-]{6}\.[\w-]{27}'''
tags = ["discord", "token"]

[[rules]]
id = "database-password"
description = "Database Password in Config"
regex = '''(?i)db_password\s*=\s*['""]([^'""]{8,})['""]'''
tags = ["database", "password"]
```

**TruffleHog - 高熵值字符串檢測**
```bash
pip install truffleHog3
trufflehog3 --no-history .      # 僅當前文件
trufflehog3 --entropy=False .   # 禁用熵值檢測，僅正則表達式
```

#### 2.4 完整安全掃描 CI 配置

```yaml
name: 🛡️ Security Scans

on:
  pull_request:
    branches: [main, dev]
  schedule:
    - cron: '0 2 * * *'  # 每日 02:00 運行

jobs:
  security-scan:
    runs-on: ubuntu-latest
    timeout-minutes: 15
    
    steps:
    - uses: actions/checkout@v4
      with:
        fetch-depth: 0  # 完整歷史，用於 secrets 掃描
        
    - name: Set up Python
      uses: actions/setup-python@v4
      with:
        python-version: '3.10'
        cache: 'pip'
        
    - name: Install Security Tools
      run: |
        pip install bandit[toml] safety pip-audit detect-secrets
        pip install semgrep
        pip install -r requirements.txt
        
    - name: SAST with Bandit
      run: |
        echo "🛡️ Running Bandit security scan..."
        bandit -r . -f json -o bandit-report.json || true
        cat bandit-report.json | jq '.'
        
    - name: Semgrep Static Analysis
      run: |
        echo "🔍 Running Semgrep analysis..."
        semgrep --config=auto --json --output=semgrep-report.json . || true
        
    - name: Dependency Vulnerability Check
      run: |
        echo "📦 Checking dependency vulnerabilities..."
        safety check --json --output safety-report.json || true
        pip-audit --format=json --output=pip-audit-report.json || true
        
    - name: Secrets Detection
      run: |
        echo "🔐 Detecting secrets..."
        detect-secrets scan --all-files --force-use-all-plugins > secrets-baseline.json || true
        
    - name: Security Summary
      run: |
        echo "📊 Security Scan Summary"
        echo "======================="
        
        # Bandit 摘要
        if [ -f bandit-report.json ]; then
          HIGH_ISSUES=$(cat bandit-report.json | jq '.results | map(select(.issue_severity == "HIGH")) | length')
          MEDIUM_ISSUES=$(cat bandit-report.json | jq '.results | map(select(.issue_severity == "MEDIUM")) | length')
          echo "🛡️ Bandit: $HIGH_ISSUES high, $MEDIUM_ISSUES medium issues"
        fi
        
        # Safety 摘要
        if [ -f safety-report.json ]; then
          VULN_COUNT=$(cat safety-report.json | jq '. | length')
          echo "📦 Safety: $VULN_COUNT vulnerabilities found"
        fi
        
        # 設置失敗條件
        if [ "$HIGH_ISSUES" -gt 0 ]; then
          echo "❌ High severity security issues found!"
          exit 1
        fi
        
    - name: Upload Security Reports
      if: always()
      uses: actions/upload-artifact@v3
      with:
        name: security-reports
        path: |
          bandit-report.json
          semgrep-report.json
          safety-report.json
          pip-audit-report.json
          secrets-baseline.json
```

### 學習階段 3: 測試覆蓋率和品質

#### 3.1 Pytest 深度配置

**基礎 pytest 配置**
```ini
# pytest.ini
[tool:pytest]
minversion = 6.0
addopts = 
    -ra                    # 顯示短摘要信息
    --strict-markers       # 嚴格標記模式
    --strict-config        # 嚴格配置模式
    --cov=bot             # 覆蓋率檢查目錄
    --cov=shared
    --cov-report=term-missing  # 終端顯示缺失行
    --cov-report=html          # HTML 報告
    --cov-report=xml           # XML 報告 (CI 使用)
    --cov-fail-under=70        # 覆蓋率門檻

testpaths = tests
python_files = test_*.py
python_classes = Test*
python_functions = test_*

markers =
    slow: marks tests as slow (deselect with '-m "not slow"')
    unit: unit tests
    integration: integration tests
    e2e: end-to-end tests
    security: security related tests
```

#### 3.2 測試分類和結構

```
tests/
├── unit/                  # 單元測試 (快速, 隔離)
│   ├── test_config.py    
│   ├── test_utils.py     
│   ├── cogs/
│   │   ├── test_ticket_core.py
│   │   └── test_vote_core.py
│   └── services/
│       ├── test_ticket_manager.py
│       └── test_vote_manager.py
│
├── integration/           # 整合測試 (中速, 依賴外部服務)
│   ├── test_database_integration.py
│   ├── test_api_integration.py
│   └── test_discord_integration.py
│
├── e2e/                  # 端對端測試 (慢速, 完整流程)
│   ├── test_ticket_workflow.py
│   └── test_vote_workflow.py
│
├── performance/          # 性能測試
│   ├── test_database_performance.py
│   └── test_api_performance.py
│
├── security/             # 安全測試
│   ├── test_authentication.py
│   └── test_authorization.py
│
├── conftest.py          # 共用 fixtures
└── fixtures/            # 測試數據
    ├── sample_tickets.json
    └── mock_discord_data.json
```

#### 3.3 高品質測試示例

**conftest.py - 共用 Fixtures**
```python
import pytest
import asyncio
import asyncio
from unittest.mock import AsyncMock, MagicMock
import discord
from bot.main import PotatoBot
from bot.db.database_manager import DatabaseManager
from shared.config import config

@pytest.fixture(scope="session")
def event_loop():
    """創建一個 session 級別的 event loop"""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()

@pytest.fixture
async def mock_bot():
    """模擬 Discord Bot"""
    bot = MagicMock(spec=PotatoBot)
    bot.user = MagicMock(spec=discord.User)
    bot.user.id = 123456789
    bot.get_guild = MagicMock(return_value=None)
    return bot

@pytest.fixture
async def mock_database():
    """模擬數據庫連接"""
    db = MagicMock(spec=DatabaseManager)
    db.execute_query = AsyncMock()
    db.fetch_one = AsyncMock()
    db.fetch_all = AsyncMock()
    return db

@pytest.fixture
def sample_ticket_data():
    """測試票券數據"""
    return {
        "id": 1,
        "title": "測試票券",
        "description": "這是一個測試票券",
        "status": "open",
        "priority": "medium",
        "created_by": 123456789,
        "created_at": "2025-08-27T10:00:00Z"
    }
```

**單元測試示例**
```python
# tests/unit/services/test_ticket_manager.py
import pytest
from unittest.mock import AsyncMock, patch
from bot.services.ticket_manager import TicketManager
from bot.exceptions import TicketNotFoundError

class TestTicketManager:
    
    @pytest.fixture
    def ticket_manager(self, mock_database):
        return TicketManager(database=mock_database)
    
    @pytest.mark.asyncio
    async def test_create_ticket_success(self, ticket_manager, sample_ticket_data):
        """測試成功創建票券"""
        # Arrange
        ticket_manager.db.execute_query.return_value = 1
        
        # Act
        ticket_id = await ticket_manager.create_ticket(
            title=sample_ticket_data["title"],
            description=sample_ticket_data["description"],
            created_by=sample_ticket_data["created_by"]
        )
        
        # Assert
        assert ticket_id == 1
        ticket_manager.db.execute_query.assert_called_once()
        
    @pytest.mark.asyncio
    async def test_get_ticket_not_found(self, ticket_manager):
        """測試獲取不存在的票券"""
        # Arrange
        ticket_manager.db.fetch_one.return_value = None
        
        # Act & Assert
        with pytest.raises(TicketNotFoundError):
            await ticket_manager.get_ticket(999)
            
    @pytest.mark.parametrize("status,expected", [
        ("open", True),
        ("closed", False),
        ("pending", True),
    ])
    def test_is_ticket_active(self, ticket_manager, status, expected):
        """參數化測試票券狀態"""
        ticket = {"status": status}
        result = ticket_manager.is_ticket_active(ticket)
        assert result == expected
```

**整合測試示例**
```python
# tests/integration/test_database_integration.py
import pytest
import asyncio
from bot.db.database_manager import DatabaseManager
from bot.db.ticket_dao import TicketDAO

@pytest.mark.integration
class TestDatabaseIntegration:
    
    @pytest.fixture
    async def real_database(self):
        """使用真實數據庫連接 (測試數據庫)"""
        db = DatabaseManager(
            host="localhost",
            port=3306,
            user="test_user", 
            password="test_password",
            database="test_potato_bot"
        )
        await db.connect()
        yield db
        await db.disconnect()
    
    @pytest.mark.asyncio
    async def test_ticket_crud_operations(self, real_database):
        """測試完整的票券 CRUD 操作"""
        ticket_dao = TicketDAO(real_database)
        
        # Create
        ticket_id = await ticket_dao.create_ticket(
            title="整合測試票券",
            description="測試數據庫整合",
            created_by=123456789
        )
        assert ticket_id is not None
        
        # Read
        ticket = await ticket_dao.get_ticket(ticket_id)
        assert ticket["title"] == "整合測試票券"
        
        # Update
        await ticket_dao.update_ticket(ticket_id, status="closed")
        updated_ticket = await ticket_dao.get_ticket(ticket_id)
        assert updated_ticket["status"] == "closed"
        
        # Delete
        await ticket_dao.delete_ticket(ticket_id)
        with pytest.raises(TicketNotFoundError):
            await ticket_dao.get_ticket(ticket_id)
```

#### 3.4 覆蓋率配置和報告

**coverage 配置**
```ini
# .coveragerc
[run]
source = bot, shared
omit = 
    */migrations/*
    */tests/*
    */venv/*
    */__pycache__/*
    */node_modules/*
    
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
```

**CI 中的測試配置**
```yaml
name: 🧪 Test Suite

on:
  pull_request:
    branches: [main, dev]
  push:
    branches: [main, dev]

jobs:
  test:
    runs-on: ubuntu-latest
    timeout-minutes: 15
    
    strategy:
      matrix:
        python-version: ["3.10"]
        test-type: ["unit", "integration", "e2e"]
    
    services:
      mysql:
        image: mysql:8.0
        env:
          MYSQL_ROOT_PASSWORD: root_password
          MYSQL_DATABASE: test_potato_bot
          MYSQL_USER: test_user
          MYSQL_PASSWORD: test_password
        ports:
          - 3306:3306
        options: --health-cmd="mysqladmin ping" --health-interval=10s --health-timeout=5s --health-retries=3
          
      redis:
        image: redis:7
        ports:
          - 6379:6379
        options: --health-cmd="redis-cli ping" --health-interval=10s --health-timeout=5s --health-retries=3
    
    steps:
    - uses: actions/checkout@v4
    
    - name: Set up Python
      uses: actions/setup-python@v4
      with:
        python-version: ${{ matrix.python-version }}
        cache: 'pip'
        
    - name: Install dependencies
      run: |
        pip install -r requirements.txt
        pip install pytest pytest-cov pytest-asyncio pytest-mock
        
    - name: Wait for services
      run: |
        sleep 10  # 等待服務啟動
        
    - name: Run Tests
      run: |
        case "${{ matrix.test-type }}" in
          unit)
            pytest tests/unit/ -v --cov=bot --cov=shared --cov-report=xml
            ;;
          integration) 
            pytest tests/integration/ -v -m "not slow"
            ;;
          e2e)
            pytest tests/e2e/ -v --maxfail=3
            ;;
        esac
        
    - name: Upload Coverage to Codecov
      if: matrix.test-type == 'unit'
      uses: codecov/codecov-action@v3
      with:
        file: ./coverage.xml
        flags: unittests
        name: codecov-umbrella
        
    - name: Coverage Comment
      if: matrix.test-type == 'unit' && github.event_name == 'pull_request'
      uses: py-cov-action/python-coverage-comment-action@v3
      with:
        GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
        MINIMUM_GREEN: 80
        MINIMUM_ORANGE: 70
```

### 學習階段 4: Docker 和 Artifact 管理

#### 4.1 多階段 Docker 構建

**優化的 Dockerfile**
```dockerfile
# syntax=docker/dockerfile:1
# Multi-stage build for optimization

# Stage 1: Dependencies installer
FROM python:3.10-slim as dependencies
WORKDIR /tmp

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

# Stage 2: Runtime image
FROM python:3.10-slim as runtime

# Create non-root user for security
RUN groupadd -g 999 appuser && \
    useradd -r -u 999 -g appuser appuser

# Install runtime dependencies
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy Python packages from dependencies stage
COPY --from=dependencies /root/.local /home/appuser/.local

# Set up application directory
WORKDIR /app
RUN chown appuser:appuser /app

# Copy application code
COPY --chown=appuser:appuser bot/ ./bot/
COPY --chown=appuser:appuser shared/ ./shared/
COPY --chown=appuser:appuser start.py ./

# Switch to non-root user
USER appuser

# Add local bin to PATH
ENV PATH=/home/appuser/.local/bin:$PATH

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import requests; requests.get('http://localhost:8080/health')" || exit 1

# Labels for metadata
LABEL maintainer="your-email@example.com" \
      version="1.0" \
      description="Potato Bot - Discord Bot with advanced features"

# Default command
CMD ["python", "start.py"]
```

**Docker Compose for Development**
```yaml
# docker-compose.dev.yml
version: '3.8'

services:
  bot:
    build:
      context: .
      dockerfile: Dockerfile
      target: runtime
    environment:
      - TESTING=true
      - DISCORD_TOKEN=${DISCORD_TOKEN}
      - DB_HOST=mysql
      - DB_USER=bot_user
      - DB_PASSWORD=bot_password
      - DB_NAME=potato_bot
      - REDIS_URL=redis://redis:6379/0
    depends_on:
      mysql:
        condition: service_healthy
      redis:
        condition: service_healthy
    volumes:
      - ./transcripts:/app/transcripts
    networks:
      - bot-network
    restart: unless-stopped

  mysql:
    image: mysql:8.0
    environment:
      MYSQL_ROOT_PASSWORD: root_password
      MYSQL_DATABASE: potato_bot
      MYSQL_USER: bot_user
      MYSQL_PASSWORD: bot_password
    ports:
      - "3306:3306"
    volumes:
      - mysql_data:/var/lib/mysql
    healthcheck:
      test: ["CMD", "mysqladmin", "ping", "-h", "localhost"]
      interval: 10s
      timeout: 5s
      retries: 5
    networks:
      - bot-network

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 3s
      retries: 5
    networks:
      - bot-network

volumes:
  mysql_data:
  redis_data:

networks:
  bot-network:
    driver: bridge
```

#### 4.2 SBOM 生成和管理

**使用 Syft 生成 SBOM**
```bash
# 安裝 Syft
curl -sSfL https://raw.githubusercontent.com/anchore/syft/main/install.sh | sh -s -- -b /usr/local/bin

# 生成不同格式的 SBOM
syft . -o spdx-json=sbom.spdx.json          # SPDX JSON 格式
syft . -o cyclonedx-json=sbom.cyclone.json  # CycloneDX JSON 格式
syft . -o table                             # 表格格式 (人類可讀)

# 掃描 Docker 映像
syft potato-bot:latest -o spdx-json=docker-sbom.json
```

**使用 CycloneDX Python 工具**
```bash
pip install cyclonedx-bom
cyclonedx-py -o sbom-cyclone.json
```

**SBOM 驗證和分析**
```bash
# 使用 Grype 掃描 SBOM 中的漏洞
grype sbom:sbom.spdx.json

# 使用 OSV Scanner 掃描
osv-scanner --sbom=sbom.spdx.json
```

#### 4.3 Artifact 管理 CI 配置

```yaml
name: 🏗️ Build & Artifact Management

on:
  push:
    branches: [main]
    tags: ['v*']
  pull_request:
    branches: [main]

env:
  REGISTRY: ghcr.io
  IMAGE_NAME: ${{ github.repository }}

jobs:
  build:
    runs-on: ubuntu-latest
    timeout-minutes: 30
    
    outputs:
      image-digest: ${{ steps.build.outputs.digest }}
      sbom-hash: ${{ steps.sbom.outputs.hash }}
    
    steps:
    - name: Checkout
      uses: actions/checkout@v4
      
    - name: Set up Docker Buildx
      uses: docker/setup-buildx-action@v2
      
    - name: Log in to Container Registry
      if: github.event_name != 'pull_request'
      uses: docker/login-action@v2
      with:
        registry: ${{ env.REGISTRY }}
        username: ${{ github.actor }}
        password: ${{ secrets.GITHUB_TOKEN }}
        
    - name: Extract metadata
      id: meta
      uses: docker/metadata-action@v4
      with:
        images: ${{ env.REGISTRY }}/${{ env.IMAGE_NAME }}
        tags: |
          type=ref,event=branch
          type=ref,event=pr
          type=semver,pattern={{version}}
          type=semver,pattern={{major}}.{{minor}}
          type=raw,value=latest,enable={{is_default_branch}}
          
    - name: Build and push Docker image
      id: build
      uses: docker/build-push-action@v4
      with:
        context: .
        push: ${{ github.event_name != 'pull_request' }}
        tags: ${{ steps.meta.outputs.tags }}
        labels: ${{ steps.meta.outputs.labels }}
        cache-from: type=gha
        cache-to: type=gha,mode=max
        platforms: linux/amd64,linux/arm64
        
    - name: Generate SBOM
      id: sbom
      run: |
        # Install Syft
        curl -sSfL https://raw.githubusercontent.com/anchore/syft/main/install.sh | sh -s -- -b /usr/local/bin
        
        # Generate multiple format SBOMs
        syft . -o spdx-json=sbom.spdx.json
        syft . -o cyclonedx-json=sbom.cyclone.json
        syft . -o table=sbom-table.txt
        
        # Generate SBOM hash for integrity
        SBOM_HASH=$(sha256sum sbom.spdx.json | cut -d' ' -f1)
        echo "hash=$SBOM_HASH" >> $GITHUB_OUTPUT
        
    - name: Create Build Metadata
      run: |
        cat > build-info.json << EOF
        {
          "build_id": "${{ github.run_id }}",
          "commit_hash": "${{ github.sha }}",
          "build_time": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
          "ref": "${{ github.ref }}",
          "actor": "${{ github.actor }}",
          "image_digest": "${{ steps.build.outputs.digest }}",
          "sbom_hash": "${{ steps.sbom.outputs.hash }}",
          "tags": ${{ steps.meta.outputs.json }},
          "python_version": "3.10",
          "base_image": "python:3.10-slim"
        }
        EOF
        
    - name: Upload Artifacts
      uses: actions/upload-artifact@v3
      with:
        name: build-artifacts-${{ github.run_id }}
        path: |
          sbom.spdx.json
          sbom.cyclone.json 
          sbom-table.txt
          build-info.json
        retention-days: 90
        
    - name: Security Scan with Grype
      run: |
        # Install Grype
        curl -sSfL https://raw.githubusercontent.com/anchore/grype/main/install.sh | sh -s -- -b /usr/local/bin
        
        # Scan SBOM for vulnerabilities
        grype sbom:sbom.spdx.json -o json --file grype-report.json
        grype sbom:sbom.spdx.json -o table
        
    - name: Upload Security Reports
      if: always()
      uses: actions/upload-artifact@v3
      with:
        name: security-scan-${{ github.run_id }}
        path: grype-report.json
        
  provenance:
    needs: build
    if: github.event_name != 'pull_request'
    uses: slsa-framework/slsa-github-generator/.github/workflows/generator_container_slsa3.yml@v1.7.0
    with:
      image: ${{ needs.build.outputs.image }}
      digest: ${{ needs.build.outputs.image-digest }}
    secrets:
      registry-username: ${{ github.actor }}
      registry-password: ${{ secrets.GITHUB_TOKEN }}
```

### 學習階段 5: OIDC 和現代認證

#### 5.1 GitHub Actions OIDC 深度解析

**OIDC 工作原理**
```
GitHub Actions → GitHub OIDC Provider → Cloud Provider
                                    ↓
                            Temporary Credentials
                                    ↓
                            Access Cloud Resources
```

**AWS IAM Role 配置**
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Federated": "arn:aws:iam::ACCOUNT-ID:oidc-provider/token.actions.githubusercontent.com"
      },
      "Action": "sts:AssumeRoleWithWebIdentity",
      "Condition": {
        "StringEquals": {
          "token.actions.githubusercontent.com:aud": "sts.amazonaws.com"
        },
        "StringLike": {
          "token.actions.githubusercontent.com:sub": "repo:YOUR-ORG/YOUR-REPO:*"
        }
      }
    }
  ]
}
```

**GitHub Actions 中使用 OIDC**
```yaml
name: Deploy with OIDC

on:
  push:
    branches: [main]

permissions:
  id-token: write   # 必需：生成 OIDC token
  contents: read    # 必需：讀取代碼

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
    - uses: actions/checkout@v4
    
    - name: Configure AWS Credentials
      uses: aws-actions/configure-aws-credentials@v2
      with:
        role-to-assume: arn:aws:iam::123456789012:role/GitHubActions-DeployRole
        role-session-name: GitHub-Actions-Deploy
        aws-region: us-east-1
        
    - name: Deploy to AWS
      run: |
        aws s3 sync ./dist s3://my-deployment-bucket
        aws ecs update-service --cluster my-cluster --service my-service --force-new-deployment
```

#### 5.2 多雲 OIDC 配置

**Google Cloud (GCP)**
```yaml
- name: Authenticate to Google Cloud
  uses: google-github-actions/auth@v1
  with:
    workload_identity_provider: projects/123456789/locations/global/workloadIdentityPools/github-pool/providers/github-provider
    service_account: github-actions@my-project.iam.gserviceaccount.com
    
- name: Deploy to GCP
  run: |
    gcloud run deploy my-service --image=gcr.io/my-project/my-image:latest
```

**Azure**
```yaml
- name: Azure Login
  uses: azure/login@v1
  with:
    client-id: ${{ secrets.AZURE_CLIENT_ID }}
    tenant-id: ${{ secrets.AZURE_TENANT_ID }}
    subscription-id: ${{ secrets.AZURE_SUBSCRIPTION_ID }}
    
- name: Deploy to Azure
  run: |
    az webapp deployment source config --name my-app --resource-group my-rg
```

#### 5.3 Secrets 管理最佳實踐

**HashiCorp Vault 集成**
```yaml
- name: Get secrets from Vault
  uses: hashicorp/vault-action@v2
  with:
    url: https://vault.example.com:8200
    method: jwt
    role: github-actions-role
    secrets: |
      secret/data/discord token | DISCORD_TOKEN ;
      secret/data/database password | DB_PASSWORD ;
      
- name: Use secrets
  run: |
    echo "Token length: ${#DISCORD_TOKEN}"
    # 使用 secrets，但不記錄實際值
```

**AWS Secrets Manager**
```yaml
- name: Configure AWS credentials
  uses: aws-actions/configure-aws-credentials@v2
  with:
    role-to-assume: ${{ secrets.AWS_ROLE_ARN }}
    aws-region: us-east-1
    
- name: Get secrets from AWS
  run: |
    DISCORD_TOKEN=$(aws secretsmanager get-secret-value --secret-id discord-bot-token --query SecretString --output text)
    echo "::add-mask::$DISCORD_TOKEN"
    export DISCORD_TOKEN
```

### 學習階段 6: 高級監控和通知

#### 6.1 智能失敗分析

**失敗分類器**
```python
# scripts/failure-analyzer.py
import json
import re
from typing import Dict, List, Tuple

class FailureAnalyzer:
    def __init__(self):
        self.patterns = {
            'format_error': [
                r'black.*would reformat',
                r'isort.*would reformat',
                r'line too long'
            ],
            'test_failure': [
                r'FAILED.*test_.*',
                r'AssertionError',
                r'\d+.*failed'
            ],
            'security_issue': [
                r'bandit.*HIGH.*severity',
                r'safety.*vulnerability',
                r'secrets.*detected'
            ],
            'dependency_error': [
                r'ModuleNotFoundError',
                r'ImportError',
                r'pip.*error'
            ],
            'syntax_error': [
                r'SyntaxError',
                r'IndentationError',
                r'invalid syntax'
            ]
        }
        
        self.solutions = {
            'format_error': {
                'description': '代碼格式問題',
                'solution': 'black . && isort .',
                'docs': 'https://github.com/psf/black'
            },
            'test_failure': {
                'description': '測試失敗',
                'solution': '檢查測試邏輯，修復失敗的測試用例',
                'docs': 'https://docs.pytest.org/en/stable/'
            },
            'security_issue': {
                'description': '安全漏洞',
                'solution': '修復安全漏洞，參考安全指南',
                'docs': 'https://bandit.readthedocs.io/'
            }
        }
    
    def analyze_failure(self, log_content: str) -> Dict:
        """分析失敗日誌並返回建議"""
        failure_type = self._classify_failure(log_content)
        
        if failure_type in self.solutions:
            solution = self.solutions[failure_type]
        else:
            solution = {
                'description': '未知錯誤',
                'solution': '請檢查完整日誌',
                'docs': 'https://docs.github.com/actions'
            }
            
        return {
            'failure_type': failure_type,
            'description': solution['description'],
            'solution': solution['solution'],
            'docs_link': solution['docs'],
            'severity': self._get_severity(failure_type)
        }
    
    def _classify_failure(self, content: str) -> str:
        for failure_type, patterns in self.patterns.items():
            for pattern in patterns:
                if re.search(pattern, content, re.IGNORECASE):
                    return failure_type
        return 'unknown'
    
    def _get_severity(self, failure_type: str) -> str:
        severity_map = {
            'security_issue': 'high',
            'syntax_error': 'high',
            'test_failure': 'medium',
            'format_error': 'low',
            'dependency_error': 'medium'
        }
        return severity_map.get(failure_type, 'medium')

if __name__ == "__main__":
    import sys
    analyzer = FailureAnalyzer()
    with open(sys.argv[1], 'r') as f:
        log_content = f.read()
    
    result = analyzer.analyze_failure(log_content)
    print(json.dumps(result, indent=2, ensure_ascii=False))
```

#### 6.2 多渠道通知系統

**Slack 通知配置**
```yaml
- name: Notify Failure
  if: failure()
  uses: 8398a7/action-slack@v3
  with:
    status: ${{ job.status }}
    channel: '#ci-cd-alerts'
    username: 'CI/CD Bot'
    icon_emoji: ':robot_face:'
    fields: repo,message,commit,author,action,eventName,ref,workflow
    text: |
      🚨 **CI/CD 失敗通知**
      
      **專案**: ${{ github.repository }}
      **分支**: ${{ github.ref_name }}
      **提交**: `${{ github.sha }}`
      **作者**: @${{ github.actor }}
      **工作流程**: ${{ github.workflow }}
      
      **失敗階段**: ${{ github.job }}
      **錯誤類型**: 代碼格式問題
      **修復建議**: 
      ```bash
      black .
      isort .
      ```
      
      **查看詳情**: ${{ github.server_url }}/${{ github.repository }}/actions/runs/${{ github.run_id }}
      
      **相關文檔**: https://github.com/psf/black
  env:
    SLACK_WEBHOOK_URL: ${{ secrets.SLACK_WEBHOOK_URL }}
```

**Discord Webhook 通知**
```yaml
- name: Discord Notification
  if: always()
  run: |
    if [[ "${{ job.status }}" == "success" ]]; then
      COLOR=65280  # Green
      TITLE="✅ CI/CD 成功"
      DESCRIPTION="所有檢查都已通過"
    else
      COLOR=16711680  # Red
      TITLE="❌ CI/CD 失敗"
      DESCRIPTION="檢查失敗，需要修復"
    fi
    
    curl -H "Content-Type: application/json" \
         -X POST \
         -d "{
           \"embeds\": [{
             \"title\": \"$TITLE\",
             \"description\": \"$DESCRIPTION\",
             \"color\": $COLOR,
             \"fields\": [
               {\"name\": \"Repository\", \"value\": \"${{ github.repository }}\", \"inline\": true},
               {\"name\": \"Branch\", \"value\": \"${{ github.ref_name }}\", \"inline\": true},
               {\"name\": \"Author\", \"value\": \"${{ github.actor }}\", \"inline\": true},
               {\"name\": \"Commit\", \"value\": \"[\`${{ github.sha }}\`](${{ github.server_url }}/${{ github.repository }}/commit/${{ github.sha }})\", \"inline\": false},
               {\"name\": \"Workflow\", \"value\": \"[${{ github.workflow }}](${{ github.server_url }}/${{ github.repository }}/actions/runs/${{ github.run_id }})\", \"inline\": false}
             ],
             \"timestamp\": \"$(date -u +%Y-%m-%dT%H:%M:%S.000Z)\"
           }]
         }" \
         ${{ secrets.DISCORD_WEBHOOK_URL }}
```

#### 6.3 監控儀表板設置

**Grafana Dashboard 配置**
```json
{
  "dashboard": {
    "title": "CI/CD Pipeline Metrics",
    "panels": [
      {
        "title": "Build Success Rate",
        "type": "stat",
        "targets": [
          {
            "query": "sum(rate(github_actions_workflow_run_conclusion_total{conclusion=\"success\"}[24h])) / sum(rate(github_actions_workflow_run_conclusion_total[24h])) * 100"
          }
        ],
        "thresholds": {
          "steps": [
            {"color": "red", "value": 0},
            {"color": "yellow", "value": 90},
            {"color": "green", "value": 95}
          ]
        }
      },
      {
        "title": "Average Build Duration",
        "type": "timeseries",
        "targets": [
          {
            "query": "avg(github_actions_workflow_run_duration_seconds) by (workflow_name)"
          }
        ]
      },
      {
        "title": "Test Coverage Trend",
        "type": "timeseries",
        "targets": [
          {
            "query": "coverage_percentage"
          }
        ]
      }
    ]
  }
}
```

### 學習階段 7: 供應鏈安全進階

#### 7.1 SLSA Framework 實施

**SLSA Level 3 實施**
```yaml
name: SLSA3 Builder

on:
  push:
    branches: [main]
    tags: ['v*']

jobs:
  build:
    runs-on: ubuntu-latest
    outputs:
      hashes: ${{ steps.hash.outputs.hashes }}
    steps:
    - uses: actions/checkout@v4
    
    - name: Build artifacts
      run: |
        # 構建過程
        python -m pip install build
        python -m build
        
    - name: Generate hashes
      id: hash
      run: |
        cd dist
        echo "hashes=$(sha256sum * | base64 -w0)" >> "$GITHUB_OUTPUT"
        
  provenance:
    needs: [build]
    uses: slsa-framework/slsa-github-generator/.github/workflows/generator_generic_slsa3.yml@v1.7.0
    with:
      base64-subjects: "${{ needs.build.outputs.hashes }}"
      
  verify:
    needs: [build, provenance]
    runs-on: ubuntu-latest
    steps:
    - name: Download artifacts
      uses: actions/download-artifact@v3
      
    - name: Verify SLSA provenance
      uses: slsa-framework/slsa-verifier/actions/installer@v2.4.0
      
    - name: Verify build
      run: |
        slsa-verifier verify-artifact \
          --provenance-path build.intoto.jsonl \
          --source-uri github.com/${{ github.repository }} \
          dist/*
```

#### 7.2 依賴管理自動化

**Dependabot 配置**
```yaml
# .github/dependabot.yml
version: 2
updates:
  - package-ecosystem: "pip"
    directory: "/"
    schedule:
      interval: "weekly"
      day: "monday"
      time: "09:00"
      timezone: "Asia/Taipei"
    open-pull-requests-limit: 10
    reviewers:
      - "maintainer-username"
    assignees:
      - "maintainer-username"
    commit-message:
      prefix: "deps"
      prefix-development: "deps-dev"
    labels:
      - "dependencies"
      - "automated"
    ignore:
      # 忽略主要版本更新 (需手動審核)
      - dependency-name: "*"
        update-types: ["version-update:semver-major"]
```

**自定義依賴更新工作流程**
```yaml
name: 🔄 Smart Dependency Updates

on:
  schedule:
    - cron: '0 9 * * 1'  # 每週一 09:00
  workflow_dispatch:

jobs:
  update-dependencies:
    runs-on: ubuntu-latest
    steps:
    - uses: actions/checkout@v4
    
    - name: Set up Python
      uses: actions/setup-python@v4
      with:
        python-version: '3.10'
        
    - name: Install pip-tools
      run: pip install pip-tools pip-audit safety
      
    - name: Update dependencies
      run: |
        # 備份當前 requirements
        cp requirements.txt requirements.backup
        
        # 更新依賴
        pip-compile --upgrade requirements.in
        
        # 檢查安全性
        pip-audit --format=json --output=security-check.json -r requirements.txt || true
        safety check -r requirements.txt --json --output=safety-check.json || true
        
    - name: Test updated dependencies  
      run: |
        pip install -r requirements.txt
        python -m pytest tests/unit/ --maxfail=5 -q
        
    - name: Analyze changes
      id: changes
      run: |
        echo "## 依賴更新摘要" > update-summary.md
        echo "" >> update-summary.md
        
        # 比較變更
        if ! diff -q requirements.txt requirements.backup > /dev/null; then
          echo "### 🔄 已更新的依賴" >> update-summary.md
          diff requirements.backup requirements.txt | grep '^>' | sed 's/^> /- /' >> update-summary.md
          echo "" >> update-summary.md
          
          # 檢查是否有主要版本更新
          MAJOR_UPDATES=$(diff requirements.backup requirements.txt | grep -E '\+[0-9]+\.' | wc -l)
          if [ "$MAJOR_UPDATES" -gt 0 ]; then
            echo "⚠️ 發現 $MAJOR_UPDATES 個主要版本更新，請仔細審查" >> update-summary.md
          fi
          
          echo "has_changes=true" >> $GITHUB_OUTPUT
        else
          echo "no_changes=true" >> $GITHUB_OUTPUT
        fi
        
    - name: Create Pull Request
      if: steps.changes.outputs.has_changes == 'true'
      uses: peter-evans/create-pull-request@v5
      with:
        token: ${{ secrets.GITHUB_TOKEN }}
        branch: dependencies/weekly-updates
        title: "🔄 週度依賴更新"
        body-path: update-summary.md
        labels: |
          dependencies
          automated
          weekly-update
        reviewers: |
          maintainer-username
```

---

## 📊 完整實施時程表

### Week 1-2: 基礎建設
- [x] **Day 1-2**: 代碼格式化工具設置 (black, isort, autoflake)
- [x] **Day 3-4**: Lint 工具集成 (flake8, pylint, mypy)  
- [x] **Day 5-7**: 基礎測試覆蓋率配置
- [x] **Day 8-10**: 簡單 CI 流水線建立
- [x] **Day 11-14**: 測試和調優

### Week 3-4: 安全強化
- [x] **Day 15-17**: SAST 工具集成 (bandit, semgrep)
- [x] **Day 18-20**: 依賴安全掃描 (safety, pip-audit)
- [x] **Day 21-22**: Secrets 檢測工具
- [x] **Day 23-25**: 安全 CI 流水線
- [x] **Day 26-28**: 安全報告和修復流程

### Week 5-6: 構建和 Artifact
- [x] **Day 29-31**: Docker 多階段構建優化
- [x] **Day 32-34**: SBOM 生成和管理
- [x] **Day 35-37**: Artifact 上傳和版本管理
- [x] **Day 38-42**: 完整構建流水線測試

### Week 7-8: 高級功能
- [x] **Day 43-45**: OIDC 認證設置
- [x] **Day 46-48**: 智能通知系統
- [x] **Day 49-52**: 監控和儀表板
- [x] **Day 53-56**: 最終測試和優化

---

## 🎓 學習資源推薦

### 官方文檔
- [GitHub Actions 文檔](https://docs.github.com/en/actions)
- [Docker 最佳實踐](https://docs.docker.com/develop/dev-best-practices/)
- [SLSA Framework](https://slsa.dev/)
- [SPDX SBOM 規範](https://spdx.dev/)

### 工具文檔
- [Black 代碼格式化](https://black.readthedocs.io/)
- [Pytest 測試框架](https://docs.pytest.org/)
- [Bandit 安全掃描](https://bandit.readthedocs.io/)
- [Syft SBOM 工具](https://github.com/anchore/syft)

### 進階學習
- [DevSecOps 最佳實踐](https://www.devsecops.org/)
- [供應鏈安全](https://www.cisa.gov/supply-chain-security)
- [OWASP CI/CD 安全指南](https://owasp.org/www-project-devsecops-guideline/)

---

## 🔄 持續改進計劃

### 每週檢視
- 檢查 CI/CD 執行時間和成功率
- 分析失敗原因並優化
- 更新工具和依賴

### 每月評估  
- 安全掃描結果分析
- 覆蓋率趨勢檢查
- 團隊反饋收集

### 每季更新
- 新工具評估和導入
- 流程優化和簡化
- 最佳實踐更新

---

**下一步**: 開始實施 Week 1 的代碼格式化工具設置！

---

> 💡 **學習提示**: 建議先從簡單的格式化工具開始，逐步添加更複雜的功能。每個階段都要充分測試再進入下一階段。