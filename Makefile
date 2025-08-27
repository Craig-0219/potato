# Makefile
# 專案自動化任務

.PHONY: help install dev-install test lint format security clean docs pre-commit-install run-bot run-api health-check

# 預設目標
help: ## 顯示可用命令
	@echo "Potato Bot - 可用命令："
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

# 安裝依賴
install: ## 安裝生產依賴
	pip install -r requirements.txt

dev-install: ## 安裝開發依賴
	pip install -e ".[dev]"
	pre-commit install

# 測試相關
test: ## 運行所有測試
	python -m pytest tests/ -v

test-unit: ## 運行單元測試
	python -m pytest tests/unit/ -v -m "unit"

test-integration: ## 運行整合測試
	python -m pytest tests/integration/ -v -m "integration"

test-coverage: ## 運行測試並生成覆蓋率報告
	python -m pytest tests/ --cov=bot --cov-report=html --cov-report=term-missing

# 代碼品質
lint: ## 檢查代碼風格
	flake8 bot/ shared/ tests/
	mypy bot/ shared/

format: ## 格式化代碼
	black bot/ shared/ tests/
	isort bot/ shared/ tests/

format-check: ## 檢查代碼格式
	black --check bot/ shared/ tests/
	isort --check-only bot/ shared/ tests/

security: ## 安全性檢查
	bandit -r bot/ shared/ -f json -o bandit-report.json
	@echo "安全檢查完成，報告已生成：bandit-report.json"

# Pre-commit hooks
pre-commit-install: ## 安裝 pre-commit hooks
	pre-commit install

pre-commit-run: ## 手動運行 pre-commit 檢查
	pre-commit run --all-files

# 運行服務
run-bot: ## 啟動 Discord Bot
	python bot/main.py

run-api: ## 啟動 API 服務
	uvicorn bot.api.app:app --host 0.0.0.0 --port 8000 --reload

run-web: ## 啟動 Web 界面 (開發模式)
	cd web-ui && npm run dev

# 健康檢查
health-check: ## 檢查系統健康狀態
	python -c "from bot.services.system_monitor import SystemMonitor; import asyncio; asyncio.run(SystemMonitor().get_system_health())"

# 資料庫相關
db-migrate: ## 執行資料庫遷移
	python -c "from bot.db.database_manager import DatabaseManager; import asyncio; asyncio.run(DatabaseManager().run_migrations())"

db-backup: ## 創建資料庫備份
	python -c "from bot.services.backup_service import BackupService; import asyncio; asyncio.run(BackupService().create_backup())"

# 清理
clean: ## 清理臨時文件
	find . -type f -name "*.pyc" -delete
	find . -type d -name "__pycache__" -delete
	find . -type d -name ".pytest_cache" -delete
	find . -type f -name ".coverage" -delete
	find . -type d -name "htmlcov" -delete
	find . -type f -name "bandit-report.json" -delete

clean-logs: ## 清理日誌文件
	find . -name "*.log" -type f -delete
	find . -name "*.log.*" -type f -delete

# 開發工具
debug-logs: ## 啟用除錯日誌
	@echo "設置除錯環境變數..."
	@echo "export DEBUG=true"
	@echo "export DEBUG_VERBOSE=true"
	@echo "export LOG_LEVEL=DEBUG"

setup-env: ## 創建環境變數範例文件
	@if [ ! -f .env ]; then \
		cp .env.example .env; \
		echo "已創建 .env 文件，請編輯配置"; \
	else \
		echo ".env 文件已存在"; \
	fi

# 文檔相關
docs-serve: ## 啟動文檔服務器
	mkdocs serve

docs-build: ## 構建文檔
	mkdocs build

# Git 相關
git-hooks: ## 設置 Git hooks
	pre-commit install
	@echo "Git hooks 已安裝"

# 部署相關
docker-build: ## 構建 Docker 映像
	docker build -t potato-bot:latest .

docker-run: ## 運行 Docker 容器
	docker run -d --name potato-bot --env-file .env -p 8000:8000 potato-bot:latest

# 品質檢查
quality-check: format-check lint security test ## 完整品質檢查

# CI/CD 相關
ci-test: ## CI 環境測試
	python -m pytest tests/ --cov=bot --cov-report=xml --cov-fail-under=70

ci-build: ## CI 環境構建檢查
	python -m pip install --upgrade pip
	pip install -e ".[dev]"
	make quality-check

# 開發工作流程
dev-setup: dev-install pre-commit-install setup-env ## 完整開發環境設置
	@echo "開發環境設置完成！"
	@echo "下一步："
	@echo "1. 編輯 .env 文件配置"
	@echo "2. 運行 'make test' 確保測試通過"
	@echo "3. 運行 'make run-bot' 啟動機器人"

# 技術債務處理
tech-debt-check: ## 檢查技術債務
	@echo "檢查技術債務..."
	@echo "代碼複雜度："
	@find bot/ -name "*.py" -exec wc -l {} + | sort -n | tail -10
	@echo ""
	@echo "TODO 項目："
	@grep -r "TODO\|FIXME\|XXX" bot/ || echo "沒有發現 TODO 項目"

debug-cleanup: ## 清理除錯代碼
	python scripts/cleanup_debug_logs.py

# 監控和分析
analyze-performance: ## 性能分析
	@echo "生成性能分析報告..."
	python -c "from bot.services.system_monitor import SystemMonitor; import asyncio; asyncio.run(SystemMonitor().generate_performance_report())"

monitor-memory: ## 記憶體使用監控
	@echo "記憶體使用情況："
	ps aux | grep python | grep -v grep

# 專案統計
stats: ## 專案統計
	@echo "專案統計："
	@echo "Python 文件數：" $(shell find bot/ shared/ -name "*.py" | wc -l)
	@echo "代碼行數：" $(shell find bot/ shared/ -name "*.py" -exec wc -l {} + | tail -1 | cut -d' ' -f1)
	@echo "測試文件數：" $(shell find tests/ -name "*.py" | wc -l)
	@echo "函數定義：" $(shell grep -r "def " bot/ shared/ | wc -l)
	@echo "類別定義：" $(shell grep -r "class " bot/ shared/ | wc -l)
