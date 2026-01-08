# shared/config.py - 清理版
"""
配置管理模組
負責載入和驗證所有環境變數配置
"""

import os
import sys
import tempfile

from dotenv import load_dotenv

# 載入環境變數
if not os.getenv("TESTING"):
    load_dotenv()
else:
    # 測試環境：嘗試載入 .env.test 文件（如果存在）
    if os.path.exists(".env.test"):
        load_dotenv(".env.test")

# 檢查必填變數
required_vars = [
    "DISCORD_TOKEN",
    "DB_HOST",
    "DB_USER",
    "DB_PASSWORD",
    "DB_NAME",
]
missing = [v for v in required_vars if os.getenv(v) is None]

# 只有在非測試環境且有缺少變數時才退出
if missing and not os.getenv("TESTING"):
    print(f"⚠️ 缺少必要的環境變數：{', '.join(missing)}")
    print("請參考 .env.example 並建立 .env 檔案後再重新啟動。")
    print("\n範例 .env 內容：")
    print("DISCORD_TOKEN=your_bot_token")
    print("DB_HOST=localhost")
    print("DB_PORT=3306")
    print("DB_USER=your_db_user")
    print("DB_PASSWORD=your_db_password")
    print("DB_NAME=your_db_name")
    sys.exit(1)

# ======================
# Discord 配置
# ======================
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")

# ======================
# 資料庫配置
# ======================
DB_HOST = os.getenv("DB_HOST")
DB_PORT = int(os.getenv("DB_PORT", 3306))
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")
DB_NAME = os.getenv("DB_NAME")

# ======================
# 系統配置
# ======================
DEBUG = os.getenv("DEBUG", "false").lower() == "true"
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
ENVIRONMENT = os.getenv("ENVIRONMENT", "production")

# ======================
# 開發工具配置
# ======================
SYNC_COMMANDS = os.getenv("SYNC_COMMANDS", "true").lower() == "true"

# ======================
# 票券系統配置
# ======================
TICKET_AUTO_REPLIES = os.getenv("TICKET_AUTO_REPLIES", "true").lower() == "true"
TICKET_DEFAULT_AUTO_CLOSE_HOURS = int(os.getenv("TICKET_DEFAULT_AUTO_CLOSE_HOURS", 24))
TICKET_MAX_PER_USER = int(os.getenv("TICKET_MAX_PER_USER", 3))

# ======================
# 圖片處理配置
# ======================
IMAGE_MAX_SIZE = int(os.getenv("IMAGE_MAX_SIZE", "50"))  # MB
IMAGE_STORAGE_PATH = os.getenv(
    "IMAGE_STORAGE_PATH", os.path.join(tempfile.gettempdir(), "bot_images")
)
IMAGE_DAILY_FREE_QUOTA = int(os.getenv("IMAGE_DAILY_FREE_QUOTA", 5))
IMAGE_MAX_SIZE_MB = int(os.getenv("IMAGE_MAX_SIZE_MB", 10))
IMAGE_SUPPORTED_FORMATS = os.getenv("IMAGE_SUPPORTED_FORMATS", "jpg,jpeg,png,gif,webp").split(",")
CLOUD_STORAGE_BUCKET = os.getenv("CLOUD_STORAGE_BUCKET")  # 可選的雲端存儲

# ======================
# 音樂系統配置
# ======================
YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY")
MUSIC_DAILY_FREE_QUOTA = int(os.getenv("MUSIC_DAILY_FREE_QUOTA", 20))
MUSIC_MAX_QUEUE_SIZE = int(os.getenv("MUSIC_MAX_QUEUE_SIZE", 50))
MUSIC_SEARCH_RESULTS_LIMIT = int(os.getenv("MUSIC_SEARCH_RESULTS_LIMIT", 10))


def validate_config_enhanced():
    """增強的配置驗證"""
    errors = []
    warnings = []

    # 檢查必要的環境變數
    required_vars = {
        "DISCORD_TOKEN": "機器人Token",
        "DB_HOST": "資料庫主機",
        "DB_USER": "資料庫用戶",
        "DB_PASSWORD": "資料庫密碼",
        "DB_NAME": "資料庫名稱",
    }

    for var, desc in required_vars.items():
        value = os.getenv(var)
        if not value:
            errors.append(f"缺少{desc}環境變數：{var}")
        elif var == "DISCORD_TOKEN" and len(value) < 50 and not os.getenv("TESTING"):
            errors.append("Discord Token格式可能不正確（長度過短）")

    # 檢查可選變數的預設值
    optional_vars = {
        "DB_PORT": ("3306", "資料庫端口"),
        "LOG_LEVEL": ("INFO", "日誌等級"),
        "DEBUG": ("false", "除錯模式"),
    }

    for var, (default, desc) in optional_vars.items():
        value = os.getenv(var, default)
        if var == "DB_PORT":
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
            "password": "***" if DB_PASSWORD else None,
        },
        "features": {
            "auto_replies": TICKET_AUTO_REPLIES,
        },
        "parameters": {
            "auto_close_hours": TICKET_DEFAULT_AUTO_CLOSE_HOURS,
            "max_tickets_per_user": TICKET_MAX_PER_USER,
        },
        "system": {
            "debug": DEBUG,
            "log_level": LOG_LEVEL,
            "environment": ENVIRONMENT,
        },
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
    # 模組被導入時自動驗證 (跳過測試環境)
    if not os.getenv("TESTING") and not validate_config_enhanced():
        print("❌ 配置無效，請檢查 .env 檔案")
        sys.exit(1)
