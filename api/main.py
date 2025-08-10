# api/main.py
"""
FastAPI 主應用程式
整合所有 API 路由和中介軟體
"""

import asyncio
import uvicorn
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.openapi.utils import get_openapi

# 導入路由
from api.auth_routes import router as auth_router
from api.ticket_routes import router as ticket_router

# 導入中介軟體
from api.middleware.auth_middleware import (
    AuthMiddleware, 
    SecurityHeadersMiddleware, 
    RateLimitMiddleware,
    get_cors_middleware_config
)

# 導入服務
from bot.services.auth_manager import auth_manager
from bot.services.system_monitor import system_monitor
from bot.services.realtime_sync_manager import realtime_sync
from shared.logger import logger


@asynccontextmanager
async def lifespan(app: FastAPI):
    """應用程式生命週期管理"""
    # 啟動時初始化服務
    logger.info("🚀 啟動 API 服務...")
    
    try:
        # 初始化認證管理器（不依賴資料庫連接）
        try:
            await auth_manager.initialize()
            logger.info("✅ 認證管理器初始化完成")
        except Exception as e:
            logger.warning(f"⚠️ 認證管理器初始化失敗，將在本機模式運行: {e}")
        
        # 初始化系統監控器（不依賴資料庫連接）
        try:
            await system_monitor.initialize()
            logger.info("✅ 系統監控器初始化完成")
        except Exception as e:
            logger.warning(f"⚠️ 系統監控器初始化失敗: {e}")
        
        # 初始化即時同步管理器（不依賴資料庫連接）
        try:
            await realtime_sync.initialize()
            logger.info("✅ 即時同步管理器初始化完成")
        except Exception as e:
            logger.warning(f"⚠️ 即時同步管理器初始化失敗: {e}")
        
        logger.info("✅ API 服務啟動完成")
        
        yield
        
    except Exception as e:
        logger.error(f"❌ 服務初始化失敗: {e}")
        # 不再拋出異常，允許 API 在部分功能下運行
        yield
    
    finally:
        # 關閉時清理資源
        logger.info("🔄 關閉 API 服務...")
        
        try:
            if hasattr(system_monitor, 'shutdown'):
                await system_monitor.shutdown()
            if hasattr(realtime_sync, 'shutdown'):
                await realtime_sync.shutdown()
            logger.info("✅ 所有服務已關閉")
        except Exception as e:
            logger.error(f"❌ 服務關閉失敗: {e}")


# 創建 FastAPI 應用程式
app = FastAPI(
    title="Potato Bot API",
    description="Discord 票券系統 API 介面",
    version="2.0.0",
    docs_url=None,  # 禁用預設文檔頁面
    redoc_url=None, # 禁用 ReDoc
    lifespan=lifespan
)

# ===== 中介軟體設定 =====

# CORS 中介軟體
app.add_middleware(
    CORSMiddleware,
    **get_cors_middleware_config()
)

# 安全標頭中介軟體
app.add_middleware(SecurityHeadersMiddleware)

# 速率限制中介軟體
app.add_middleware(RateLimitMiddleware, requests_per_minute=120)

# 認證中介軟體
app.add_middleware(AuthMiddleware)

# ===== 異常處理 =====

@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """HTTP 異常處理器"""
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": exc.detail,
            "status_code": exc.status_code,
            "path": request.url.path,
            "method": request.method
        }
    )

@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """通用異常處理器"""
    logger.error(f"未處理的異常: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "error": "內部服務器錯誤",
            "status_code": 500,
            "path": request.url.path,
            "method": request.method
        }
    )

# ===== 路由註冊 =====

# 路由註冊
app.include_router(auth_router)  # 認證相關路由
app.include_router(ticket_router)  # 票券管理路由

# ===== 基礎端點 =====

@app.get("/", tags=["基礎"])
async def root():
    """API 根端點"""
    return {
        "service": "Potato Bot API",
        "version": "2.0.0",
        "status": "running",
        "docs": "/docs",
        "health": "/health"
    }

@app.get("/health", tags=["基礎"])
async def health_check():
    """健康檢查端點"""
    try:
        # 檢查各服務狀態
        health_status = {
            "status": "healthy",
            "timestamp": system_monitor.start_time.isoformat(),
            "services": {
                "auth": "healthy" if auth_manager else "unavailable",
                "monitoring": "healthy" if system_monitor.monitoring_active else "inactive",
                "realtime_sync": "healthy" if realtime_sync.is_running else "inactive"
            }
        }
        
        # 獲取基本系統指標
        if system_monitor.monitoring_active:
            current_metrics = await system_monitor.get_current_metrics()
            if current_metrics:
                health_status["metrics"] = {
                    "active_tickets": len(current_metrics.get("tickets", {})),
                    "system_health_score": (await system_monitor.get_system_health_score())["score"]
                }
        
        return health_status
        
    except Exception as e:
        logger.error(f"健康檢查失敗: {e}")
        return JSONResponse(
            status_code=503,
            content={
                "status": "unhealthy", 
                "error": str(e),
                "timestamp": system_monitor.start_time.isoformat()
            }
        )

# ===== 自訂文檔頁面 =====

@app.get("/docs", include_in_schema=False)
async def custom_swagger_ui_html():
    """自訂 Swagger UI 頁面"""
    return get_swagger_ui_html(
        openapi_url="/openapi.json",
        title="Potato Bot API - 文檔",
        swagger_js_url="https://cdn.jsdelivr.net/npm/swagger-ui-dist@4.15.5/swagger-ui-bundle.js",
        swagger_css_url="https://cdn.jsdelivr.net/npm/swagger-ui-dist@4.15.5/swagger-ui.css",
    )

def custom_openapi():
    """自訂 OpenAPI schema"""
    if app.openapi_schema:
        return app.openapi_schema
    
    openapi_schema = get_openapi(
        title="Potato Bot API",
        version="2.0.0",
        description="""
        ## Discord 票券系統 API
        
        提供完整的票券管理、用戶認證和系統監控功能。
        
        ### 認證方式
        
        支援多種認證方式：
        - **JWT 令牌**: 用於 Web 介面登入
        - **API 金鑰**: 用於程式化訪問  
        - **會話令牌**: 用於持久會話
        
        ### 權限系統
        
        - **管理員**: 完整系統管理權限
        - **客服**: 票券處理和統計查看權限
        - **一般用戶**: 基本票券操作權限
        
        ### 使用流程
        
        1. 通過 `/auth/login` 登入獲取令牌
        2. 在請求標頭中包含 `Authorization: Bearer <token>`
        3. 根據權限訪問相應的 API 端點
        """,
        routes=app.routes,
    )
    
    # 添加安全性定義
    openapi_schema["components"]["securitySchemes"] = {
        "BearerAuth": {
            "type": "http",
            "scheme": "bearer",
            "bearerFormat": "JWT",
            "description": "JWT 令牌認證"
        },
        "ApiKeyAuth": {
            "type": "http", 
            "scheme": "bearer",
            "description": "API 金鑰認證 (格式: key_id.secret)"
        }
    }
    
    # 為所有端點添加安全性要求
    for path in openapi_schema["paths"]:
        for method in openapi_schema["paths"][path]:
            if method != "options":
                openapi_schema["paths"][path][method]["security"] = [
                    {"BearerAuth": []},
                    {"ApiKeyAuth": []}
                ]
    
    app.openapi_schema = openapi_schema
    return app.openapi_schema

app.openapi = custom_openapi

# ===== WebSocket 支援 =====

@app.websocket("/ws")
async def websocket_endpoint(websocket):
    """WebSocket 端點用於即時更新"""
    await websocket.accept()
    
    # 添加到即時同步訂閱者
    await realtime_sync.add_websocket_subscriber(websocket)
    
    try:
        while True:
            # 保持連接活躍
            data = await websocket.receive_text()
            # 處理客戶端訊息（如果需要）
            
    except Exception as e:
        logger.error(f"WebSocket 錯誤: {e}")
    finally:
        # 移除訂閱者
        await realtime_sync.remove_websocket_subscriber(websocket)

# ===== 開發模式啟動 =====

if __name__ == "__main__":
    # 開發模式配置
    uvicorn.run(
        "api.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info",
        access_log=True
    )