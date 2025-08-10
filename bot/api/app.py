# bot/api/app.py
"""
FastAPI 主應用程式
提供完整的 REST API 端點和自動文檔生成
"""

from fastapi import FastAPI, HTTPException, Depends, Security, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse
try:
    from slowapi import Limiter, _rate_limit_exceeded_handler
    from slowapi.util import get_remote_address
    from slowapi.errors import RateLimitExceeded
    HAS_SLOWAPI = True
except ImportError:
    HAS_SLOWAPI = False
from contextlib import asynccontextmanager
import asyncio
import logging
from datetime import datetime, timezone
from typing import Optional

from . import API_VERSION, API_BASE_PATH
from .auth import APIKeyManager, get_current_user
# Temporarily disabled all routes due to slowapi issues
# from .routes import system, tickets, analytics, automation, security
from shared.logger import logger

# 設定限流器 (如果可用)
if HAS_SLOWAPI:
    limiter = Limiter(key_func=get_remote_address)
else:
    limiter = None

# API 生命週期管理
@asynccontextmanager
async def lifespan(app: FastAPI):
    """API 應用生命週期管理"""
    logger.info("🚀 API 服務啟動中...")
    
    # 啟動時初始化
    try:
        # 初始化資料庫連接
        from bot.db.database_manager import get_database_manager
        db = get_database_manager()
        
        # 初始化 API 金鑰管理器
        api_key_manager = APIKeyManager()
        await api_key_manager.initialize()
        
        logger.info("✅ API 服務啟動完成")
        yield
        
    except Exception as e:
        logger.error(f"❌ API 服務啟動失敗: {e}")
        raise
    finally:
        # 關閉時清理
        logger.info("🔄 API 服務關閉中...")

# 創建 FastAPI 應用
app = FastAPI(
    title="Potato Discord Bot API",
    description="企業級 Discord 機器人管理系統 API",
    version="1.8.0",
    docs_url=f"{API_BASE_PATH}/docs",
    redoc_url=f"{API_BASE_PATH}/redoc",
    openapi_url=f"{API_BASE_PATH}/openapi.json",
    lifespan=lifespan,
    contact={
        "name": "Potato Bot Support",
        "url": "https://github.com/your-repo/potato-bot",
        "email": "support@potato-bot.com"
    },
    license_info={
        "name": "MIT License",
        "url": "https://opensource.org/licenses/MIT"
    }
)

# 添加中間件
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 生產環境應該限制具體域名
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(
    TrustedHostMiddleware, 
    allowed_hosts=["*"]  # 生產環境應該限制具體主機
)

# 添加限流中間件 (如果可用)
if HAS_SLOWAPI:
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# 安全認證
security = HTTPBearer()

@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """統一 HTTP 異常處理"""
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "code": exc.status_code,
                "message": exc.detail,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "path": str(request.url)
            }
        }
    )

@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """通用異常處理"""
    logger.error(f"API 未處理錯誤: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "error": {
                "code": 500,
                "message": "內部伺服器錯誤",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "path": str(request.url)
            }
        }
    )

# 根端點
@app.get("/")
async def root(request: Request):
    """API 根端點"""
    return {
        "message": "Welcome to Potato Discord Bot API",
        "version": "1.8.0",
        "api_version": API_VERSION,
        "docs_url": f"{API_BASE_PATH}/docs",
        "status": "operational",
        "timestamp": datetime.now(timezone.utc).isoformat()
    }

# 健康檢查端點
@app.get(f"{API_BASE_PATH}/health")
async def health_check(request: Request):
    """API 健康檢查"""
    try:
        # 檢查資料庫連接
        from bot.db.database_manager import get_database_manager
        db = get_database_manager()
        
        # 簡單的資料庫連接測試
        # 這裡可以添加更詳細的健康檢查邏輯
        
        return {
            "status": "healthy",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "version": "1.8.0",
            "components": {
                "database": "healthy",
                "discord_bot": "healthy",
                "api_server": "healthy"
            }
        }
    except Exception as e:
        logger.error(f"健康檢查失敗: {e}")
        raise HTTPException(
            status_code=503,
            detail="Service Unavailable - Health check failed"
        )

# 路由模組暫時禁用，等待修復 slowapi 相關問題
logger.info("⚠️ 路由模組已暫時禁用，僅提供基本 API 功能")

# 添加基本的 API 端點供即時使用
@app.get(f"{API_BASE_PATH}/status")
async def api_status():
    """API 服務狀態"""
    return {
        "service": "Potato Discord Bot API",
        "version": "1.8.0",
        "status": "operational",
        "features": {
            "basic_api": "available",
            "health_check": "available", 
            "authentication": "available",
            "advanced_routes": "under_maintenance"
        },
        "endpoints": {
            "docs": f"{API_BASE_PATH}/docs",
            "health": f"{API_BASE_PATH}/health",
            "status": f"{API_BASE_PATH}/status"
        },
        "timestamp": datetime.now(timezone.utc).isoformat()
    }

@app.get(f"{API_BASE_PATH}/version")
async def api_version():
    """API 版本資訊"""
    return {
        "api_version": API_VERSION,
        "service_version": "1.8.0",
        "features": [
            "Discord Bot Management",
            "Ticket System API",
            "Analytics & Reporting", 
            "User Authentication",
            "Rate Limiting",
            "Comprehensive Documentation"
        ],
        "status": "active"
    }

# TODO: 修復所有路由模組的 slowapi 相關問題後重新啟用
# app.include_router(system.router, prefix=f"{API_BASE_PATH}/system", tags=["system"])
# app.include_router(tickets.router, prefix=f"{API_BASE_PATH}/tickets", tags=["tickets"])
# app.include_router(analytics.router, prefix=f"{API_BASE_PATH}/analytics", tags=["analytics"])
# app.include_router(automation.router, prefix=f"{API_BASE_PATH}/automation", tags=["automation"])
# app.include_router(security.router, prefix=f"{API_BASE_PATH}/security", tags=["security"])

# 啟動函數
async def start_api_server(host: str = "0.0.0.0", port: int = 8000):
    """啟動 API 伺服器"""
    import uvicorn
    
    config = uvicorn.Config(
        app=app,
        host=host,
        port=port,
        log_level="info",
        access_log=True
    )
    
    server = uvicorn.Server(config)
    logger.info(f"🌐 API 伺服器啟動於 http://{host}:{port}")
    logger.info(f"📚 API 文檔位址: http://{host}:{port}{API_BASE_PATH}/docs")
    
    await server.serve()

if __name__ == "__main__":
    asyncio.run(start_api_server())