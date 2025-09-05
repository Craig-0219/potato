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
├── bot/           # 機器人核心功能
├── shared/        # 共用模組
├── src/           # 源碼模組
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