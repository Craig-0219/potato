# Potato Discord Bot - Development Branch

[![Version](https://img.shields.io/badge/version-2025.08.30-blue.svg)](VERSION)
[![Discord Bot](https://img.shields.io/badge/Discord-Bot-7289DA.svg)](https://discord.com)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![CI/CD](https://img.shields.io/badge/CI/CD-Active-success.svg)](https://github.com/actions)
[![Tests](https://img.shields.io/badge/Tests-Passing-success.svg)](#testing)
[![Security](https://img.shields.io/badge/Security-Scanned-green.svg)](#security)

> **多功能社群管理機器人** - 開發分支，包含完整的 CI/CD 流程和測試框架

## 🚀 快速開始

### 跨平台啟動

```bash
# Python 啟動器 (推薦)
python start.py

# Linux/macOS
./start.sh

# Windows
start.bat
```

### 環境配置

```bash
# 複製配置範例
cp .env.example .env

# 編輯配置文件
nano .env
```

## 📦 核心功能

- 🎫 **智能客服系統** - 自動票券管理、問題分類、智能回覆
- 🗳️ **社群互動工具** - 投票民調、意見收集、活動管理
- 🌍 **多語言國際化** - 7+ 語言支援、文化適應、自動檢測
- 🎮 **遊戲社群整合** - Minecraft 整合、多遊戲支援、玩家管理
- 🤖 **AI 智能助手** - 智能問答、內容審核、社群分析
- 🔒 **社群安全管理** - 自動審核、行為分析、安全防護
- 🌐 **社群儀表板** - 數據分析、成長追蹤、管理工具

## 🏗️ 分支架構

- **`dev`** - 開發分支 (當前) - 包含完整的 CI/CD 和測試框架
- **`main`** - 生產主分支 - 穩定版本，包含託管部署流程
- **`ptero`** - 部署分支 - 純淨生產版本，無開發工具

## 🔄 CI/CD 流程

### GitHub Actions 工作流程

1. **🧠 Smart Change Detection** - 智能變更檢測
   - 自動分析變更類型和影響範圍
   - 動態調整後續檢查策略
   - 節省 40-60% 執行時間

2. **🛡️ Code Quality** - 代碼品質檢查
   - Ruff 格式化和 Lint 檢查
   - 自動代碼修復和格式化
   - 品質報告生成

3. **🧪 Test Coverage** - 測試覆蓋率
   - 完整測試套件執行
   - 覆蓋率報告生成
   - E2E 測試驗證

4. **🛡️ Security Scans** - 安全掃描
   - Bandit 靜態安全分析
   - 依賴漏洞掃描
   - Secrets 檢測

5. **🚀 Production Deployment** - 生產部署
   - 自動化部署流程
   - 健康檢查驗證
   - 回滾機制

6. **🚨 Emergency Rollback** - 緊急回滾
   - 一鍵回滾機制
   - 備份和恢復
   - 事件通知

### 部署流程

- dev → main: 合併請求觸發完整 CI/CD
- main → ptero: 自動部署到託管服務

## 📋 系統要求

### 運行環境
- Python 3.10+
- PostgreSQL 或 SQLite
- Redis (可選)
- Discord Bot Token

### 開發環境
- Git
- pytest (測試框架)
- ruff (代碼格式化和檢查)
- coverage (測試覆蓋率)

## 🛠️ 技術棧

- **Discord.py** - Discord API 整合
- **FastAPI** - 現代 Web API 框架
- **PostgreSQL** - 主要資料庫
- **Redis** - 快取和會話管理
- **Prometheus** - 監控和指標

### 開發工具
- **Ruff** - Python 代碼格式化和檢查
- **pytest** - 測試框架
- **Coverage** - 測試覆蓋率分析
- **Bandit** - 安全漏洞掃描
- **GitHub Actions** - CI/CD 自動化

## 🧪 測試 {#testing}

### 運行測試
```bash
# 完整測試套件
pytest

# 包含覆蓋率報告
pytest --cov=bot --cov=shared --cov-report=html

# E2E 測試
pytest tests/e2e/ -v
```

### 測試類型
- **單元測試** - 核心功能測試
- **整合測試** - 組件間交互測試
- **E2E 測試** - 端到端功能測試

## 🛡️ 安全 {#security}

### 安全檢查
```bash
# 靜態安全分析
bandit -r bot/ shared/

# 依賴漏洞掃描
safety check

# Secrets 檢測
detect-secrets scan --all-files
```

### 安全特性
- 自動 Secrets 檢測
- 依賴漏洞監控
- 靜態代碼安全分析
- 定時安全掃描

## 💻 開發指南

### 提交流程
1. 建立功能分支: `git checkout -b feature/xxx`
2. 開發和測試: `pytest`
3. 代碼品質檢查: `ruff check --fix .`
4. 提交變更: `git commit -m "feat: xxx"`
5. 推送和建立 PR: `git push origin feature/xxx`

### CI/CD 流程
- PR 觸發完整檢查流程
- 智能變更檢測優化執行時間
- 自動化代碼品質和安全檢查
- 測試覆蓋率驗證

---

**📝 注意：** 這是開發分支，包含完整的 CI/CD 流程和測試框架。生產部署請使用 `main` 分支。