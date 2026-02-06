# shared/config.py - 清理版
"""
配置管理模組
負責載入和驗證所有環境變數配置
"""

import json
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
# 自動回覆配置
# ======================
DEFAULT_AUTO_REPLY_MENTIONS = {292993868092276736: "找我爸幹嘛???"}
AUTO_REPLY_MENTIONS_RAW = os.getenv("AUTO_REPLY_MENTIONS")
AUTO_REPLY_MENTIONS: dict[int, str] = {}
if AUTO_REPLY_MENTIONS_RAW is None:
    AUTO_REPLY_MENTIONS = DEFAULT_AUTO_REPLY_MENTIONS
elif AUTO_REPLY_MENTIONS_RAW:
    try:
        parsed = json.loads(AUTO_REPLY_MENTIONS_RAW)
    except json.JSONDecodeError:
        print("⚠️ AUTO_REPLY_MENTIONS 格式錯誤，已忽略")
    else:
        if isinstance(parsed, dict):
            for key, value in parsed.items():
                try:
                    user_id = int(key)
                except (TypeError, ValueError):
                    continue
                if value is None:
                    continue
                AUTO_REPLY_MENTIONS[user_id] = str(value)
        else:
            print("⚠️ AUTO_REPLY_MENTIONS 必須是 JSON object")

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

# ======================
# FiveM 狀態監控
# ======================
FIVEM_INFO_URL = os.getenv("FIVEM_INFO_URL")
FIVEM_PLAYERS_URL = os.getenv("FIVEM_PLAYERS_URL")
FIVEM_POLL_INTERVAL = int(os.getenv("FIVEM_POLL_INTERVAL", 3))
FIVEM_OFFLINE_THRESHOLD = int(os.getenv("FIVEM_OFFLINE_THRESHOLD", 3))
FIVEM_STATUS_CHANNEL_ID = int(os.getenv("FIVEM_STATUS_CHANNEL_ID", "0") or 0)
FIVEM_TXADMIN_STATUS_FILE = os.getenv("FIVEM_TXADMIN_STATUS_FILE")
FIVEM_RESTART_NOTIFY_SECONDS = os.getenv(
    "FIVEM_RESTART_NOTIFY_SECONDS", "600,300,180,120,60,10"
)
# txAdmin 狀態檔（FTP 讀取）
FIVEM_TXADMIN_FTP_HOST = os.getenv("FIVEM_TXADMIN_FTP_HOST")
FIVEM_TXADMIN_FTP_PORT = int(os.getenv("FIVEM_TXADMIN_FTP_PORT", "21") or 21)
FIVEM_TXADMIN_FTP_USER = os.getenv("FIVEM_TXADMIN_FTP_USER")
FIVEM_TXADMIN_FTP_PASSWORD = os.getenv("FIVEM_TXADMIN_FTP_PASSWORD")
FIVEM_TXADMIN_FTP_PATH = os.getenv("FIVEM_TXADMIN_FTP_PATH")
FIVEM_TXADMIN_FTP_PASSIVE = os.getenv("FIVEM_TXADMIN_FTP_PASSIVE", "true").lower() == "true"
FIVEM_TXADMIN_FTP_TIMEOUT = int(os.getenv("FIVEM_TXADMIN_FTP_TIMEOUT", "10") or 10)
# FiveM 推送 API（跨機上報）
FIVEM_PUSH_API_PORT = int(os.getenv("FIVEM_PUSH_API_PORT", "0") or 0)
FIVEM_PUSH_API_BIND = os.getenv("FIVEM_PUSH_API_BIND", "0.0.0.0")
FIVEM_PUSH_API_KEY = os.getenv("FIVEM_PUSH_API_KEY")
# Lavalink 連線設定
LAVALINK_HOST = os.getenv("LAVALINK_HOST")
LAVALINK_PORT = int(os.getenv("LAVALINK_PORT", 2333))
LAVALINK_PASSWORD = os.getenv("LAVALINK_PASSWORD")
LAVALINK_SECURE = os.getenv("LAVALINK_SECURE", "false").lower() == "true"
LAVALINK_URI = os.getenv("LAVALINK_URI")


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
            "mention_auto_replies": len(AUTO_REPLY_MENTIONS),
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
        "lavalink": {
            "host": LAVALINK_HOST,
            "port": LAVALINK_PORT,
            "secure": LAVALINK_SECURE,
            "uri": LAVALINK_URI,
            "password": "***" if LAVALINK_PASSWORD else None,
        },
        "fivem_push": {
            "bind": FIVEM_PUSH_API_BIND,
            "port": FIVEM_PUSH_API_PORT,
            "api_key": "***" if FIVEM_PUSH_API_KEY else None,
        },
        "fivem_txadmin_ftp": {
            "host": FIVEM_TXADMIN_FTP_HOST,
            "port": FIVEM_TXADMIN_FTP_PORT,
            "user": "***" if FIVEM_TXADMIN_FTP_USER else None,
            "password": "***" if FIVEM_TXADMIN_FTP_PASSWORD else None,
            "path": FIVEM_TXADMIN_FTP_PATH,
            "passive": FIVEM_TXADMIN_FTP_PASSIVE,
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
