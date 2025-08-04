# shared/config.py - 修復版
"""
配置管理模組 - 修復版
修復點：
1. 使用 sys.exit 而不是 exit
2. 添加更詳細的錯誤訊息
3. 添加配置驗證
"""

import os
import sys
from dotenv import load_dotenv
from typing import Optional

# 載入環境變數
load_dotenv()

# 檢查必填變數
required_vars = ["DISCORD_TOKEN", "DB_HOST", "DB_USER", "DB_PASSWORD", "DB_NAME"]
missing = [v for v in required_vars if os.getenv(v) is None]

if missing:
    print(f"⚠️ 缺少必要的環境變數：{', '.join(missing)}")
    print("請參考 .env.example 並建立 .env 檔案後再重新啟動。")
    print("\n範例 .env 內容：")
    print("DISCORD_TOKEN=your_bot_token")
    print("DB_HOST=localhost")
    print("DB_PORT=3306")
    print("DB_USER=your_db_user")
    print("DB_PASSWORD=your_db_password")
    print("DB_NAME=your_db_name")
    sys.exit(1)  # 修復：使用 sys.exit 而不是 exit

# 主要配置
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
DB_HOST = os.getenv("DB_HOST")
DB_PORT = int(os.getenv("DB_PORT", 3306))
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")
DB_NAME = os.getenv("DB_NAME")

# 可選配置
DEBUG = os.getenv("DEBUG", "false").lower() == "true"
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
REDIS_URL = os.getenv("REDIS_URL")  # 可選的 Redis 連接

# 票券系統配置
TICKET_AUTO_ASSIGNMENT = os.getenv("TICKET_AUTO_ASSIGNMENT", "true").lower() == "true"
TICKET_SLA_MONITORING = os.getenv("TICKET_SLA_MONITORING", "true").lower() == "true"
TICKET_AUTO_REPLIES = os.getenv("TICKET_AUTO_REPLIES", "true").lower() == "true"
TICKET_RATING_SYSTEM = os.getenv("TICKET_RATING_SYSTEM", "true").lower() == "true"
TICKET_ADVANCED_STATS = os.getenv("TICKET_ADVANCED_STATS", "true").lower() == "true"

# 系統參數
TICKET_DEFAULT_SLA_MINUTES = int(os.getenv("TICKET_DEFAULT_SLA_MINUTES", 60))
TICKET_DEFAULT_AUTO_CLOSE_HOURS = int(os.getenv("TICKET_DEFAULT_AUTO_CLOSE_HOURS", 24))
TICKET_MAX_PER_USER = int(os.getenv("TICKET_MAX_PER_USER", 3))

def validate_config_enhanced():
    """增強的配置驗證（修復版）"""
    errors = []
    warnings = []
    
    # 檢查必要的環境變數
    required_vars = {
        'DISCORD_TOKEN': '機器人Token',
        'DB_HOST': '資料庫主機',
        'DB_USER': '資料庫用戶',
        'DB_PASSWORD': '資料庫密碼',
        'DB_NAME': '資料庫名稱'
    }
    
    for var, desc in required_vars.items():
        value = os.getenv(var)
        if not value:
            errors.append(f"缺少{desc}環境變數：{var}")
        elif var == 'DISCORD_TOKEN' and len(value) < 50:
            errors.append(f"Discord Token格式可能不正確（長度過短）")
    
    # 檢查可選變數的預設值
    optional_vars = {
        'DB_PORT': ('3306', '資料庫端口'),
        'LOG_LEVEL': ('INFO', '日誌等級'),
        'DEBUG': ('false', '除錯模式')
    }
    
    for var, (default, desc) in optional_vars.items():
        value = os.getenv(var, default)
        if var == 'DB_PORT':
            try:
                int(value)
            except ValueError:
                warnings.append(f"{desc}格式錯誤，將使用預設值：{default}")
    
    # 回報結果
    if errors:
        print("❌ 配置錯誤：")
        for error in errors:
            print(f"  • {error}")
        return False
    
    if warnings:
        print("⚠️ 配置警告：")
        for warning in warnings:
            print(f"  • {warning}")
    
    print("✅ 配置驗證通過")
    return True

def get_config_summary() -> dict:
    """取得配置摘要（隱藏敏感資訊）"""
    return {
        "database": {
            "host": DB_HOST,
            "port": DB_PORT,
            "user": DB_USER,
            "database": DB_NAME,
            "password": "***" if DB_PASSWORD else None
        },
        "features": {
            "auto_assignment": TICKET_AUTO_ASSIGNMENT,
            "sla_monitoring": TICKET_SLA_MONITORING,
            "auto_replies": TICKET_AUTO_REPLIES,
            "rating_system": TICKET_RATING_SYSTEM,
            "advanced_stats": TICKET_ADVANCED_STATS
        },
        "parameters": {
            "default_sla_minutes": TICKET_DEFAULT_SLA_MINUTES,
            "auto_close_hours": TICKET_DEFAULT_AUTO_CLOSE_HOURS,
            "max_tickets_per_user": TICKET_MAX_PER_USER
        },
        "system": {
            "debug": DEBUG,
            "log_level": LOG_LEVEL,
            "redis_enabled": bool(REDIS_URL)
        }
    }

# 啟動時驗證配置
if __name__ == "__main__":
    print("🔍 驗證配置...")
    if validate_config_enhanced():
        print("✅ 配置驗證通過")
        
        # 顯示配置摘要
        import json
        summary = get_config_summary()
        print("\n📋 配置摘要：")
        print(json.dumps(summary, indent=2, ensure_ascii=False))
    else:
        print("❌ 配置驗證失敗")
        sys.exit(1)
else:
    # 模組被導入時自動驗證
    if not validate_config_enhanced():
        print("❌ 配置無效，請檢查 .env 檔案")
        sys.exit(1)