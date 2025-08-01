import os
from dotenv import load_dotenv

load_dotenv()

# 檢查必填變數
required_vars = ["DISCORD_TOKEN", "DB_HOST", "DB_USER", "DB_PASSWORD", "DB_NAME"]
missing = [v for v in required_vars if os.getenv(v) is None]

if missing:
    print(f"⚠️ 缺少 .env 設定：{', '.join(missing)}")
    print("請參考 .env.example 並建立 .env 後再重新啟動。")
    exit(1)

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
DB_HOST = os.getenv("DB_HOST")
DB_PORT = int(os.getenv("DB_PORT", 3306))
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")
DB_NAME = os.getenv("DB_NAME")
