# Potato Discord Bot - Production Branch

[![Version](https://img.shields.io/badge/version-2025.08.30-blue.svg)](VERSION)
[![Discord Bot](https://img.shields.io/badge/Discord-Bot-7289DA.svg)](https://discord.com)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

> **企業級 Discord 機器人系統** - 功能完整的生產版本

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

- 🎫 **智能票券系統** - 自動分派、統計分析
- 🗳️ **投票管理** - 範本系統、即時統計、多語言支援
- 🌍 **多語言支援** - 中文、英文、日文、韓文
- 🎮 **遊戲娛樂** - 經濟系統、抽獎、音樂播放
- 🤖 **AI 助手** - 智能對話、內容分析、意圖識別
- 🔒 **安全管理** - 權限控制、審計日誌、多重驗證
- 🌐 **API 服務** - RESTful API、即時通訊、Web 介面

## 🏗️ 分支架構

- **`main`** - 生產主分支 (當前)
- **`dev`** - 開發分支 (包含 CI/CD)
- **`ptero`** - 部署分支 (純淨生產版本)

## 🔄 自動部署

### 生產部署流程
- **main** 分支包含穩定的生產版本
- 自動觸發 `deploy-to-ptero.yml` 工作流程
- 部署到託管服務平台

### 安全機制
- 緊急回滾機制 (`emergency-rollback.yml`)
- 自動安全掃描 (`security-scans.yml`)
- 生產環境健康檢查

## 📋 系統要求

- Python 3.10+
- PostgreSQL 或 SQLite
- Redis (可選)
- Discord Bot Token

## 🛠️ 技術棧

- **Discord.py** - Discord API 整合
- **FastAPI** - 現代 Web API 框架
- **PostgreSQL** - 主要資料庫
- **Redis** - 快取和會話管理
- **Prometheus** - 監控和指標

---

**📝 注意：** 這是生產主分支，包含穩定的發布版本。開發工作請使用 `dev` 分支。