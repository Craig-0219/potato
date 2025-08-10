# bot/api/routes/system.py
"""
系統管理 API 端點
提供系統狀態監控、配置管理和維護功能
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from slowapi import Limiter
from slowapi.util import get_remote_address
from typing import Optional, List, Dict, Any
from datetime import datetime
import psutil
import os

from ..auth import APIUser, require_read_permission, require_admin_permission, require_super_admin_permission
from ..models import BaseResponse, SystemHealth, SystemMetrics, APIKeyResponse, APIKeyCreate
from shared.logger import logger

router = APIRouter()
limiter = Limiter(key_func=get_remote_address)

@router.get("/health", response_model=SystemHealth, summary="系統健康檢查")
@limiter.limit("30/minute")
async def get_system_health(
    user: APIUser = Depends(require_read_permission)
):
    """獲取系統整體健康狀況"""
    try:
        # 獲取系統運行時間
        boot_time = psutil.boot_time()
        uptime = datetime.now().timestamp() - boot_time
        
        # 檢查各組件狀態
        components = {
            "database": "healthy",  # TODO: 實際檢查資料庫
            "discord_bot": "healthy",  # TODO: 檢查 Discord 連接
            "api_server": "healthy",
            "cache": "healthy"  # TODO: 檢查快取系統
        }
        
        # 性能指標
        cpu_percent = psutil.cpu_percent(interval=1)
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage('/')
        
        metrics = {
            "cpu_usage": cpu_percent,
            "memory_usage": memory.percent,
            "disk_usage": disk.percent,
            "process_count": len(psutil.pids()),
            "network_io": 0  # TODO: 實際網路 I/O 統計
        }
        
        # 判斷整體狀態
        status = "healthy"
        if cpu_percent > 80 or memory.percent > 85:
            status = "warning"
        if cpu_percent > 95 or memory.percent > 95:
            status = "critical"
        
        return {
            "status": status,
            "timestamp": datetime.now(),
            "uptime": uptime,
            "version": "1.8.0",
            "components": components,
            "metrics": metrics
        }
        
    except Exception as e:
        logger.error(f"系統健康檢查錯誤: {e}")
        raise HTTPException(status_code=500, detail="系統健康檢查失敗")

@router.get("/metrics", response_model=SystemMetrics, summary="獲取系統性能指標")
@limiter.limit("20/minute") 
async def get_system_metrics(
    user: APIUser = Depends(require_read_permission)
):
    """獲取詳細的系統性能指標"""
    try:
        # CPU 和記憶體使用情況
        cpu_percent = psutil.cpu_percent(interval=1)
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage('/')
        
        # 網路統計 (簡化版)
        network = psutil.net_io_counters()
        
        # TODO: 從資料庫獲取業務指標
        database_connections = 10  # 模擬數據
        active_tickets = 25
        api_requests_per_minute = 150
        bot_latency = 45.2
        
        return {
            "cpu_usage": cpu_percent,
            "memory_usage": memory.percent,
            "disk_usage": disk.percent,
            "database_connections": database_connections,
            "active_tickets": active_tickets,
            "api_requests_per_minute": api_requests_per_minute,
            "bot_latency": bot_latency,
            "timestamp": datetime.now()
        }
        
    except Exception as e:
        logger.error(f"獲取系統指標錯誤: {e}")
        raise HTTPException(status_code=500, detail="獲取系統指標失敗")

@router.get("/info", summary="獲取系統信息")
@limiter.limit("10/minute")
async def get_system_info(
    user: APIUser = Depends(require_read_permission)
):
    """獲取系統基本信息"""
    try:
        return {
            "success": True,
            "data": {
                "name": "Potato Discord Bot API",
                "version": "1.8.0",
                "python_version": f"{os.sys.version_info.major}.{os.sys.version_info.minor}.{os.sys.version_info.micro}",
                "platform": os.name,
                "architecture": psutil.WINDOWS if os.name == 'nt' else psutil.LINUX,
                "start_time": datetime.now(),  # TODO: 實際啟動時間
                "timezone": str(datetime.now().astimezone().tzinfo),
                "features": [
                    "ticket_management",
                    "automation_engine", 
                    "analytics_dashboard",
                    "security_audit",
                    "api_management"
                ]
            }
        }
        
    except Exception as e:
        logger.error(f"獲取系統信息錯誤: {e}")
        raise HTTPException(status_code=500, detail="獲取系統信息失敗")

# API 金鑰管理端點
@router.get("/api-keys", response_model=List[APIKeyResponse], summary="獲取 API 金鑰列表")
@limiter.limit("10/minute")
async def get_api_keys(
    user: APIUser = Depends(require_super_admin_permission)
):
    """獲取所有 API 金鑰（不包含實際金鑰值）"""
    try:
        from ..auth import get_api_key_manager
        
        manager = get_api_key_manager()
        
        # TODO: 從資料庫獲取 API 金鑰列表
        api_keys = []
        for api_key in manager.api_keys.values():
            api_keys.append({
                "key_id": api_key.key_id,
                "name": api_key.name,
                "permission_level": api_key.permission_level,
                "guild_id": api_key.guild_id,
                "created_at": api_key.created_at,
                "last_used_at": api_key.last_used_at,
                "expires_at": api_key.expires_at,
                "is_active": api_key.is_active,
                "usage_count": api_key.usage_count
            })
        
        return api_keys
        
    except Exception as e:
        logger.error(f"獲取 API 金鑰列表錯誤: {e}")
        raise HTTPException(status_code=500, detail="獲取 API 金鑰列表失敗")

@router.post("/api-keys", response_model=BaseResponse, summary="創建 API 金鑰", status_code=201)
@limiter.limit("5/minute")
async def create_api_key(
    key_data: APIKeyCreate,
    user: APIUser = Depends(require_super_admin_permission)
):
    """創建新的 API 金鑰"""
    try:
        from ..auth import get_api_key_manager, PermissionLevel
        
        manager = get_api_key_manager()
        
        # 創建 API 金鑰
        raw_key, api_key = await manager.create_api_key(
            name=key_data.name,
            permission_level=PermissionLevel(key_data.permission_level),
            guild_id=key_data.guild_id,
            expires_days=key_data.expires_days
        )
        
        return {
            "success": True,
            "message": "API 金鑰創建成功",
            "data": {
                "key_id": api_key.key_id,
                "api_key": raw_key,  # 只在創建時返回一次
                "name": api_key.name,
                "permission_level": api_key.permission_level,
                "expires_at": api_key.expires_at
            }
        }
        
    except Exception as e:
        logger.error(f"創建 API 金鑰錯誤: {e}")
        raise HTTPException(status_code=500, detail="創建 API 金鑰失敗")

@router.delete("/api-keys/{key_id}", response_model=BaseResponse, summary="撤銷 API 金鑰")
@limiter.limit("10/minute")
async def revoke_api_key(
    key_id: str,
    user: APIUser = Depends(require_super_admin_permission)
):
    """撤銷指定的 API 金鑰"""
    try:
        from ..auth import get_api_key_manager
        
        manager = get_api_key_manager()
        
        success = await manager.revoke_api_key(key_id)
        if not success:
            raise HTTPException(status_code=404, detail="API 金鑰不存在")
        
        return {
            "success": True,
            "message": "API 金鑰已撤銷"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"撤銷 API 金鑰錯誤: {e}")
        raise HTTPException(status_code=500, detail="撤銷 API 金鑰失敗")

@router.post("/maintenance", response_model=BaseResponse, summary="進入維護模式")
@limiter.limit("2/hour")
async def enter_maintenance_mode(
    reason: Optional[str] = Query(None, description="維護原因"),
    duration_minutes: Optional[int] = Query(None, description="預計維護時間（分鐘）"),
    user: APIUser = Depends(require_super_admin_permission)
):
    """將系統設置為維護模式"""
    try:
        # TODO: 實現維護模式邏輯
        
        return {
            "success": True,
            "message": "系統已進入維護模式",
            "data": {
                "maintenance_start": datetime.now(),
                "estimated_end": datetime.now() if not duration_minutes else datetime.now(),
                "reason": reason or "系統維護"
            }
        }
        
    except Exception as e:
        logger.error(f"進入維護模式錯誤: {e}")
        raise HTTPException(status_code=500, detail="進入維護模式失敗")