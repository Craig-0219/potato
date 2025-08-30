# Potato Discord Bot - Production Branch

[![Version](https://img.shields.io/badge/version-2025.08.28-blue.svg)](VERSION)
[![Discord Bot](https://img.shields.io/badge/Discord-Bot-7289DA.svg)](https://discord.com)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

> **多功能社群管理機器人** - 智能化的 Discord 社群管理解決方案

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

- **`main`** - 生產主分支 (當前)
- **`dev`** - 開發分支 (包含 CI/CD)
- **`ptero`** - 部署分支 (純淨生產版本)

## 🔄 自動部署

main 分支會自動部署到 ptero 分支：
- ✅ 移除開發文件
- ✅ 清理測試程式
- ✅ 生成生產版本

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

**📝 注意：** 這是多功能社群管理機器人的生產主分支，提供穩定的社群管理解決方案。開發工作請使用 `dev` 分支。