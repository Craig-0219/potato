#!/usr/bin/env python3
"""
Potato Bot - 精簡版啟動文件
適用於 Pterodactyl 部署的最小版本
"""

import os
import sys
from pathlib import Path

# 設置環境
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))
os.environ.setdefault("PYTHONPATH", str(project_root))
os.environ.setdefault("PYTHONUNBUFFERED", "1")


def main():
    print("🚀 啟動 Potato Bot 精簡版...")
    print(f"Python 版本: {sys.version}")
    print(f"工作目錄: {os.getcwd()}")

    try:
        # 檢查必要的環境變數 (只需要 DISCORD_TOKEN)
        if not os.getenv("DISCORD_TOKEN"):
            print("❌ 缺少必要環境變數: DISCORD_TOKEN")
            print("請在 Pterodactyl 面板設置 DISCORD_TOKEN")
            sys.exit(1)

        print("✅ 環境變數檢查通過")

        # 導入主程式
        from bot.main import run_bot

        print("✅ 成功導入主程式")

        # 啟動機器人
        run_bot()

    except ImportError as e:
        print(f"❌ 導入錯誤: {e}")
        print("\n📁 當前目錄結構:")
        for root, dirs, files in os.walk("."):
            level = root.replace(".", "").count(os.sep)
            indent = " " * 2 * level
            print(f"{indent}{os.path.basename(root)}/")
            subindent = " " * 2 * (level + 1)
            for file in files[:5]:  # 只顯示前5個文件
                print(f"{subindent}{file}")
        sys.exit(1)

    except Exception as e:
        print(f"❌ 啟動失敗: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
