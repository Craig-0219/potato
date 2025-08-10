# api/simple_main.py
"""
簡化的 FastAPI 應用程式
用於測試基本功能
"""

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from datetime import datetime
import sys
import os

# 添加項目根目錄到 Python 路徑
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

try:
    from shared.logger import logger
except ImportError:
    import logging
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger("potato-api")

# 創建 FastAPI 應用程式
app = FastAPI(
    title="Potato Bot API (簡化版)",
    description="Discord 票券系統 API 介面",
    version="2.0.0-simple"
)

# ===== 基礎端點 =====

@app.get("/", tags=["基礎"])
async def root():
    """API 根端點"""
    try:
        return {
            "service": "Potato Bot API (Simple)",
            "version": "2.0.0-simple", 
            "status": "running",
            "timestamp": datetime.now().isoformat(),
            "docs": "/docs",
            "health": "/health"
        }
    except Exception as e:
        logger.error(f"根端點錯誤: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/health", tags=["基礎"])
async def health_check():
    """健康檢查端點"""
    try:
        return {
            "status": "healthy",
            "timestamp": datetime.now().isoformat(),
            "service": "simple-api",
            "version": "2.0.0-simple"
        }
    except Exception as e:
        logger.error(f"健康檢查錯誤: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/auth/health", tags=["認證"])
async def auth_health_check():
    """認證服務健康檢查"""
    try:
        return {
            "status": "healthy",
            "timestamp": datetime.now().isoformat(),
            "service": "authentication"
        }
    except Exception as e:
        logger.error(f"認證健康檢查錯誤: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ===== 異常處理 =====

@app.exception_handler(Exception)
async def general_exception_handler(request, exc: Exception):
    """通用異常處理器"""
    logger.error(f"未處理的異常: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "error": str(exc),
            "status_code": 500,
            "service": "simple-api"
        }
    )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)