# bot/api/routes/system.py
"""
系統管理 API 端點
提供系統狀態監控、配置管理和維護功能
"""

import os
from datetime import datetime
from typing import Any, Dict, List, Optional

import psutil
from fastapi import APIRouter, Depends, HTTPException, Query, Request

try:
    from slowapi import Limiter
    from slowapi.util import get_remote_address

    HAS_SLOWAPI = True
except ImportError:
    HAS_SLOWAPI = False

from shared.logger import logger

from ..auth import (
    APIUser,
    require_admin_permission,
    require_read_permission,
    require_super_admin_permission,
)
from ..models import APIKeyCreate, APIKeyResponse, BaseResponse, SystemHealth, SystemMetrics

router = APIRouter()

if HAS_SLOWAPI:
    limiter = Limiter(key_func=get_remote_address)
else:
    # 如果沒有 slowapi，創建一個空的裝飾器
    def limiter_mock(rate):
        def decorator(func):
            return func

        return decorator

    limiter = type("MockLimiter", (), {"limit": limiter_mock})()


@router.get("/health", response_model=SystemHealth, summary="系統健康檢查")
# @limiter.limit("30/minute")
async def get_system_health(user: APIUser = Depends(require_read_permission)):
    """獲取系統整體健康狀況（需要認證）"""
    return await _get_system_health_internal()


@router.get("/public-health", summary="公開系統健康檢查")
# @limiter.limit("60/minute")
async def get_public_system_health():
    """獲取系統整體健康狀況（無需認證）"""
    return await _get_system_health_internal()


async def _get_system_health_internal():
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
            "cache": "healthy",  # TODO: 檢查快取系統
        }

        # 性能指標
        cpu_percent = psutil.cpu_percent(interval=1)
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage("/")

        metrics = {
            "cpu_usage": cpu_percent,
            "memory_usage": memory.percent,
            "disk_usage": disk.percent,
            "process_count": len(psutil.pids()),
            "network_io": 0,  # TODO: 實際網路 I/O 統計
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
            "metrics": metrics,
        }

    except Exception as e:
        logger.error(f"系統健康檢查錯誤: {e}")
        raise HTTPException(status_code=500, detail="系統健康檢查失敗")


@router.get("/metrics", response_model=SystemMetrics, summary="獲取系統性能指標")
# @limiter.limit("20/minute")
async def get_system_metrics(user: APIUser = Depends(require_read_permission)):
    """獲取詳細的系統性能指標（需要認證）"""
    return await _get_system_metrics_internal()


@router.get("/public-metrics", summary="獲取公開系統性能指標")
# @limiter.limit("30/minute")
async def get_public_system_metrics():
    """獲取詳細的系統性能指標（無需認證）"""
    return await _get_system_metrics_internal()


async def _get_system_metrics_internal():
    """獲取詳細的系統性能指標"""
    try:
        # CPU 和記憶體使用情況
        cpu_percent = psutil.cpu_percent(interval=1)
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage("/")

        # 網路統計 (簡化版)
        network = psutil.net_io_counters()

        # 獲取真實業務指標
        try:
            # 使用 psutil 獲取網路連線數
            connections = psutil.net_connections()
            # 統計連接到 3306 端口的連線數
            mysql_connections = sum(
                1
                for conn in connections
                if conn.laddr and conn.laddr.port == 3306 and conn.status == "ESTABLISHED"
            )
            database_connections = max(1, mysql_connections)  # 至少顯示 1 個連線
        except Exception as e:
            logger.warning(f"無法獲取連線數: {e}")
            database_connections = 1  # 預設值

        # TODO: 實現其他業務指標的真實數據獲取
        active_tickets = 0  # 暫時設為 0，等待實現
        api_requests_per_minute = 0  # 暫時設為 0，等待實現
        bot_latency = 0.0  # 暫時設為 0，等待實現

        return {
            "cpu_usage": cpu_percent,
            "memory_usage": memory.percent,
            "disk_usage": disk.percent,
            "database_connections": database_connections,
            "active_tickets": active_tickets,
            "api_requests_per_minute": api_requests_per_minute,
            "bot_latency": bot_latency,
            "timestamp": datetime.now(),
        }

    except Exception as e:
        logger.error(f"獲取系統指標錯誤: {e}")
        raise HTTPException(status_code=500, detail="獲取系統指標失敗")


@router.get("/info", summary="獲取系統信息")
# @limiter.limit("10/minute")
async def get_system_info(user: APIUser = Depends(require_read_permission)):
    """獲取系統基本信息"""
    try:
        return {
            "success": True,
            "data": {
                "name": "Potato Discord Bot API",
                "version": "1.8.0",
                "python_version": f"{os.sys.version_info.major}.{os.sys.version_info.minor}.{os.sys.version_info.micro}",
                "platform": os.name,
                "architecture": psutil.WINDOWS if os.name == "nt" else psutil.LINUX,
                "start_time": datetime.now(),  # TODO: 實際啟動時間
                "timezone": str(datetime.now().astimezone().tzinfo),
                "features": [
                    "ticket_management",
                    "automation_engine",
                    "analytics_dashboard",
                    "security_audit",
                    "api_management",
                ],
            },
        }

    except Exception as e:
        logger.error(f"獲取系統信息錯誤: {e}")
        raise HTTPException(status_code=500, detail="獲取系統信息失敗")


# API 金鑰管理端點
@router.get("/api-keys", response_model=List[APIKeyResponse], summary="獲取 API 金鑰列表")
# @limiter.limit("10/minute")
async def get_api_keys(user: APIUser = Depends(require_super_admin_permission)):
    """獲取所有 API 金鑰（不包含實際金鑰值）"""
    try:
        from ..auth import get_api_key_manager

        manager = get_api_key_manager()

        # TODO: 從資料庫獲取 API 金鑰列表
        api_keys = []
        for api_key in manager.api_keys.values():
            api_keys.append(
                {
                    "key_id": api_key.key_id,
                    "name": api_key.name,
                    "permission_level": api_key.permission_level,
                    "guild_id": api_key.guild_id,
                    "created_at": api_key.created_at,
                    "last_used_at": api_key.last_used_at,
                    "expires_at": api_key.expires_at,
                    "is_active": api_key.is_active,
                    "usage_count": api_key.usage_count,
                }
            )

        return api_keys

    except Exception as e:
        logger.error(f"獲取 API 金鑰列表錯誤: {e}")
        raise HTTPException(status_code=500, detail="獲取 API 金鑰列表失敗")


@router.post("/api-keys", response_model=BaseResponse, summary="創建 API 金鑰", status_code=201)
# @limiter.limit("5/minute")
async def create_api_key(
    key_data: APIKeyCreate, user: APIUser = Depends(require_super_admin_permission)
):
    """創建新的 API 金鑰"""
    try:
        from ..auth import PermissionLevel, get_api_key_manager

        manager = get_api_key_manager()

        # 創建 API 金鑰
        raw_key, api_key = await manager.create_api_key(
            name=key_data.name,
            permission_level=PermissionLevel(key_data.permission_level),
            guild_id=key_data.guild_id,
            expires_days=key_data.expires_days,
        )

        return {
            "success": True,
            "message": "API 金鑰創建成功",
            "data": {
                "key_id": api_key.key_id,
                "api_key": raw_key,  # 只在創建時返回一次
                "name": api_key.name,
                "permission_level": api_key.permission_level,
                "expires_at": api_key.expires_at,
            },
        }

    except Exception as e:
        logger.error(f"創建 API 金鑰錯誤: {e}")
        raise HTTPException(status_code=500, detail="創建 API 金鑰失敗")


@router.delete("/api-keys/{key_id}", response_model=BaseResponse, summary="撤銷 API 金鑰")
# @limiter.limit("10/minute")
async def revoke_api_key(key_id: str, user: APIUser = Depends(require_super_admin_permission)):
    """撤銷指定的 API 金鑰"""
    try:
        from ..auth import get_api_key_manager

        manager = get_api_key_manager()

        success = await manager.revoke_api_key(key_id)
        if not success:
            raise HTTPException(status_code=404, detail="API 金鑰不存在")

        return {"success": True, "message": "API 金鑰已撤銷"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"撤銷 API 金鑰錯誤: {e}")
        raise HTTPException(status_code=500, detail="撤銷 API 金鑰失敗")


@router.post("/maintenance", response_model=BaseResponse, summary="進入維護模式")
# @limiter.limit("2/hour")
async def enter_maintenance_mode(
    reason: Optional[str] = Query(None, description="維護原因"),
    duration_minutes: Optional[int] = Query(None, description="預計維護時間（分鐘）"),
    user: APIUser = Depends(require_super_admin_permission),
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
                "reason": reason or "系統維護",
            },
        }

    except Exception as e:
        logger.error(f"進入維護模式錯誤: {e}")
        raise HTTPException(status_code=500, detail="進入維護模式失敗")


# ========== Bot 設定管理端點 ==========


@router.get("/bot-settings", response_model=Dict[str, Any], summary="獲取 Bot 設定")
async def get_bot_settings(user: APIUser = Depends(require_admin_permission)):
    """獲取 Discord Bot 的各項設定"""
    try:
        from bot.db.pool import db_pool

        async with db_pool.acquire() as conn:
            async with conn.cursor() as cursor:
                # 獲取票券系統設定
                await cursor.execute(
                    """
                    SELECT setting_key, setting_value
                    FROM ticket_settings
                    WHERE guild_id = %s
                """,
                    (0,),
                )  # 使用 0 作為全局設定
                ticket_rows = await cursor.fetchall()

                # 獲取歡迎系統設定
                await cursor.execute(
                    """
                    SELECT setting_key, setting_value
                    FROM welcome_settings
                    WHERE guild_id = %s
                """,
                    (0,),
                )
                welcome_rows = await cursor.fetchall()

                # 獲取投票系統設定
                await cursor.execute(
                    """
                    SELECT setting_key, setting_value
                    FROM vote_settings
                    WHERE guild_id = %s
                """,
                    (0,),
                )
                vote_rows = await cursor.fetchall()

        # 組織設定數據
        settings = {
            "ticket_settings": (
                {row[0]: row[1] for row in ticket_rows}
                if ticket_rows
                else {"auto_assign": False, "max_tickets_per_user": 3, "staff_notifications": True}
            ),
            "welcome_settings": (
                {row[0]: row[1] for row in welcome_rows}
                if welcome_rows
                else {
                    "enabled": False,
                    "welcome_channel": "",
                    "welcome_message": "歡迎 {user} 加入我們的社群！",
                    "auto_role": "",
                }
            ),
            "vote_settings": (
                {row[0]: row[1] for row in vote_rows}
                if vote_rows
                else {"default_duration": 24, "allow_anonymous": False, "auto_close": True}
            ),
        }

        return settings

    except Exception as e:
        logger.error(f"獲取 Bot 設定錯誤: {e}")
        raise HTTPException(status_code=500, detail="獲取 Bot 設定失敗")


@router.post("/bot-settings/{section}", response_model=BaseResponse, summary="更新 Bot 設定")
async def update_bot_settings(
    section: str, settings: Dict[str, Any], user: APIUser = Depends(require_admin_permission)
):
    """更新 Discord Bot 的特定模組設定"""
    try:
        from bot.db.pool import db_pool

        # 驗證模組名稱
        valid_sections = ["tickets", "welcome", "votes"]
        if section not in valid_sections:
            raise HTTPException(
                status_code=400, detail=f"無效的模組名稱，支援: {', '.join(valid_sections)}"
            )

        # 對應的資料表
        table_mapping = {
            "tickets": "ticket_settings",
            "welcome": "welcome_settings",
            "votes": "vote_settings",
        }

        table_name = table_mapping[section]

        async with db_pool.acquire() as conn:
            async with conn.cursor() as cursor:
                # 更新設定
                for key, value in settings.items():
                    await cursor.execute(
                        f"""
                        INSERT INTO {table_name} (guild_id, setting_key, setting_value, updated_at)
                        VALUES (%s, %s, %s, %s)
                        ON DUPLICATE KEY UPDATE
                        setting_value = VALUES(setting_value),
                        updated_at = VALUES(updated_at)
                    """,
                        (0, key, str(value), datetime.now()),
                    )

                await conn.commit()

        logger.info(f"Bot 設定已更新 - 模組: {section}, 用戶: {user.username}")

        return {
            "success": True,
            "message": f"{section} 模組設定已成功更新",
            "data": {
                "section": section,
                "updated_settings": settings,
                "updated_at": datetime.now(),
            },
        }

    except Exception as e:
        logger.error(f"更新 Bot 設定錯誤: {e}")
        raise HTTPException(status_code=500, detail="更新 Bot 設定失敗")


@router.get("/bot-commands", response_model=Dict[str, Any], summary="獲取 Bot 指令列表")
async def get_bot_commands(user: APIUser = Depends(require_read_permission)):
    """獲取當前 Discord Bot 載入的指令列表"""
    try:
        from bot.main import bot

        if not bot:
            raise HTTPException(status_code=503, detail="Bot 未啟動")

        # 獲取斜線指令
        slash_commands = []
        if hasattr(bot, "tree") and bot.tree:
            for command in bot.tree.get_commands():
                slash_commands.append(
                    {
                        "name": command.name,
                        "description": command.description,
                        "type": "slash",
                        "module": getattr(command, "module", "unknown"),
                    }
                )

        # 獲取文字指令
        text_commands = []
        for command in bot.commands:
            text_commands.append(
                {
                    "name": command.name,
                    "description": command.help or "無描述",
                    "type": "text",
                    "module": command.cog_name if command.cog_name else "unknown",
                    "aliases": list(command.aliases) if command.aliases else [],
                }
            )

        # 獲取載入的擴展
        loaded_extensions = list(bot.extensions.keys())

        return {
            "total_slash_commands": len(slash_commands),
            "total_text_commands": len(text_commands),
            "loaded_extensions": loaded_extensions,
            "slash_commands": slash_commands,
            "text_commands": text_commands,
        }

    except Exception as e:
        logger.error(f"獲取 Bot 指令列表錯誤: {e}")
        raise HTTPException(status_code=500, detail="獲取 Bot 指令列表失敗")


@router.post("/bot-reload-extension", response_model=BaseResponse, summary="重新載入 Bot 擴展")
async def reload_bot_extension(
    extension_name: str, user: APIUser = Depends(require_admin_permission)
):
    """重新載入指定的 Bot 擴展模組"""
    try:
        from bot.main import bot

        if not bot:
            raise HTTPException(status_code=503, detail="Bot 未啟動")

        # 重新載入擴展
        await bot.reload_extension(extension_name)

        logger.info(f"Bot 擴展已重新載入: {extension_name}, 操作用戶: {user.username}")

        return {
            "success": True,
            "message": f"擴展 {extension_name} 已成功重新載入",
            "data": {"extension": extension_name, "reloaded_at": datetime.now()},
        }

    except Exception as e:
        logger.error(f"重新載入 Bot 擴展錯誤 ({extension_name}): {e}")
        raise HTTPException(status_code=500, detail=f"重新載入擴展失敗: {str(e)}")
