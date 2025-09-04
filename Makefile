# Potato Bot 重構後 Makefile
.PHONY: help install dev-install format lint test security clean run

# 預設目標
.DEFAULT_GOAL := help

# 變數定義
PYTHON := python3
PIP := pip3
SRC_DIR := src
TEST_DIR := tests
VENV_DIR := .venv

# 說明
help: ## 顯示可用命令
	@echo "Potato Bot 開發命令："
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-15s\033[0m %s\n", $$1, $$2}'

# 安裝依賴
install: ## 安裝生產依賴
	$(PIP) install -r requirements.txt

dev-install: ## 安裝開發依賴
	$(PIP) install -r requirements.txt
	$(PIP) install pre-commit pytest-cov black isort flake8 mypy bandit
	pre-commit install

# 虛擬環境
venv: ## 創建虛擬環境
	$(PYTHON) -m venv $(VENV_DIR)
	@echo "請執行: source $(VENV_DIR)/bin/activate"

# 程式碼格式化
format: ## 格式化程式碼
	@echo "🎨 格式化程式碼..."
	black $(SRC_DIR)/ $(TEST_DIR)/
	isort $(SRC_DIR)/ $(TEST_DIR)/
	@echo "✅ 格式化完成"

# 程式碼檢查
lint: ## 程式碼品質檢查
	@echo "🔍 執行程式碼檢查..."
	flake8 $(SRC_DIR)/ $(TEST_DIR)/
	mypy $(SRC_DIR)/
	@echo "✅ 程式碼檢查完成"

# 安全掃描
security: ## 安全漏洞掃描
	@echo "🛡️ 執行安全掃描..."
	bandit -r $(SRC_DIR)/ -f json -o bandit-report.json
	safety check
	@echo "✅ 安全掃描完成"

# 執行測試
test: ## 執行測試
	@echo "🧪 執行測試..."
	pytest $(TEST_DIR)/ -v --cov=$(SRC_DIR) --cov-report=html --cov-report=term-missing
	@echo "✅ 測試完成"

# 快速測試 (無覆蓋率)
test-quick: ## 快速測試 (無覆蓋率報告)
	@echo "⚡ 快速測試..."
	pytest $(TEST_DIR)/ -v
	@echo "✅ 快速測試完成"

# 執行特定測試
test-unit: ## 執行單元測試
	pytest $(TEST_DIR)/unit/ -v

test-integration: ## 執行整合測試
	pytest $(TEST_DIR)/integration/ -v

# 品質檢查 (全套)
quality: format lint security ## 執行完整品質檢查

# 清理
clean: ## 清理產生的檔案
	@echo "🧹 清理檔案..."
	find . -type f -name "*.pyc" -delete
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type d -name "*.egg-info" -exec rm -rf {} +
	rm -rf htmlcov/
	rm -rf .coverage
	rm -rf .pytest_cache/
	rm -rf bandit-report.json
	@echo "✅ 清理完成"

# 啟動機器人
run: ## 啟動 Potato Bot
	@echo "🚀 啟動 Potato Bot..."
	$(PYTHON) start.py

# 開發模式啟動
dev-run: ## 開發模式啟動 (自動重載)
	@echo "🔧 開發模式啟動..."
	$(PYTHON) start.py --dev

# Docker 相關 (如果需要)
docker-build: ## 建構 Docker 映像
	docker build -t potato-bot .

docker-run: ## 執行 Docker 容器
	docker run --env-file .env potato-bot

# Pre-commit 相關
pre-commit-install: ## 安裝 pre-commit hooks
	pre-commit install

pre-commit-run: ## 執行 pre-commit 檢查
	pre-commit run --all-files

# 重置開發環境
reset-dev: clean dev-install ## 重置開發環境

# CI/CD 模擬
ci-test: quality test ## 模擬 CI 流程

# 部署相關
build: quality test ## 建構檢查
	@echo "🏗️ 建構檢查完成，可以部署"

# 版本管理
version: ## 顯示版本資訊
	@grep version pyproject.toml