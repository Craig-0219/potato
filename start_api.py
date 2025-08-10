#!/usr/bin/env python3
# start_api.py
"""
API 服務啟動腳本
獨立啟動 FastAPI 服務，用於 Web 介面和 API 訪問
"""

import os
import sys
import asyncio
import signal
from pathlib import Path

# 添加項目根目錄到 Python 路徑
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# 環境變數載入
from dotenv import load_dotenv
load_dotenv()

try:
    from shared.logger import logger
except ImportError:
    import logging
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger("potato-api")

async def main():
    """主程式"""
    logger.info("🚀 啟動 Potato Bot API 服務...")
    
    try:
        # 導入和啟動 FastAPI 應用程式
        import uvicorn
        from api.main import app
        
        # 配置
        config = {
            "app": app,
            "host": os.getenv("API_HOST", "0.0.0.0"),
            "port": int(os.getenv("API_PORT", "8000")),
            "log_level": os.getenv("LOG_LEVEL", "info").lower(),
            "access_log": True,
            "use_colors": True,
            "reload": os.getenv("DEBUG", "false").lower() == "true"
        }
        
        logger.info(f"🌐 API 服務將在 http://{config['host']}:{config['port']} 啟動")
        logger.info(f"📖 API 文檔: http://{config['host']}:{config['port']}/docs")
        
        # 啟動服務器
        server = uvicorn.Server(uvicorn.Config(**config))
        
        # 設置優雅關閉
        def signal_handler(signum, frame):
            logger.info("📨 收到關閉信號，正在優雅關閉...")
            server.should_exit = True
        
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
        
        # 啟動服務器
        await server.serve()
        
    except KeyboardInterrupt:
        logger.info("⚡ 用戶中斷，正在關閉服務...")
    except Exception as e:
        logger.error(f"❌ API 服務啟動失敗: {e}")
        return 1
    finally:
        logger.info("👋 API 服務已關閉")
    
    return 0

if __name__ == "__main__":
    # 檢查核心依賴
    try:
        import fastapi
        import uvicorn
        import jwt
        import websockets
        logger.info("✅ 核心依賴檢查通過")
    except ImportError as e:
        logger.error(f"❌ 缺少必要依賴: {e}")
        logger.info("請執行: pip install fastapi uvicorn[standard] python-jose[cryptography] websockets")
        sys.exit(1)
    
    # 檢查可選依賴
    optional_deps = []
    try:
        import aioredis
        optional_deps.append("aioredis")
    except ImportError:
        logger.warning("⚠️ aioredis 不可用，Redis 功能將被禁用")
    
    if optional_deps:
        logger.info(f"✅ 可選依賴: {', '.join(optional_deps)}")
    
    # 啟動
    exit_code = asyncio.run(main())
    sys.exit(exit_code)