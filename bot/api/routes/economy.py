# bot/api/routes/economy.py - 跨平台經濟系統 API 路由
"""
跨平台經濟系統 API 路由 v3.0.0 - Phase 5 Stage 4
提供 Minecraft 插件與 Discord Bot 之間的經濟數據同步接口
"""

from datetime import datetime, timezone
from typing import Any, Dict, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field

from bot.services.economy_manager import economy_manager
from shared.logger import logger

router = APIRouter(prefix="/api/economy", tags=["economy"])
security = HTTPBearer()

# ========== 請求/回應模型 ==========


class SyncRequest(BaseModel):
    """跨平台同步請求模型"""

    user_id: int = Field(..., description="Discord 用戶 ID")
    guild_id: int = Field(..., description="Discord 伺服器 ID")
    server_key: str = Field(..., description="Minecraft 伺服器認證金鑰")
    timestamp: str = Field(..., description="請求時間戳")
    balances: Dict[str, int] = Field(..., description="貨幣餘額")
    sync_type: str = Field(default="discord_to_minecraft", description="同步類型")
    minecraft_server_id: Optional[str] = Field(None, description="Minecraft 伺服器 ID")


class SyncResponse(BaseModel):
    """跨平台同步回應模型"""

    status: str = Field(..., description="同步狀態")
    message: str = Field(..., description="回應訊息")
    timestamp: str = Field(..., description="回應時間戳")
    adjusted_balances: Optional[Dict[str, int]] = Field(
        None, description="調整後的餘額"
    )
    minecraft_adjustments: Optional[Dict[str, Any]] = Field(
        None, description="Minecraft 端調整"
    )


class WebhookRequest(BaseModel):
    """Minecraft Webhook 請求模型"""

    event_type: str = Field(..., description="事件類型")
    user_id: int = Field(..., description="Discord 用戶 ID")
    guild_id: int = Field(..., description="Discord 伺服器 ID")
    server_key: str = Field(..., description="認證金鑰")
    activity_type: Optional[str] = Field(None, description="活動類型")
    reward_amount: Optional[int] = Field(None, description="獎勵數量")
    metadata: Optional[Dict[str, Any]] = Field(None, description="額外數據")


class PlayerEconomyResponse(BaseModel):
    """玩家經濟數據回應模型"""

    user_id: int
    guild_id: int
    balances: Dict[str, int]
    level_info: Dict[str, Any]
    daily_stats: Dict[str, Any]
    sync_status: Dict[str, Any]


class EconomyStatsResponse(BaseModel):
    """經濟統計回應模型"""

    server_info: Dict[str, Any]
    currency_supply: Dict[str, int]
    user_stats: Dict[str, Any]
    inflation_data: Dict[str, Any]
    sync_stats: Dict[str, Any]


# ========== 認證函數 ==========


async def verify_server_key(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> str:
    """驗證 Minecraft 伺服器金鑰"""
    try:
        # 這裡應該實現真正的金鑰驗證邏輯
        # 暫時接受任何非空的 Bearer token
        if not credentials.credentials:
            raise HTTPException(status_code=401, detail="無效的認證金鑰")

        return credentials.credentials

    except Exception as e:
        logger.error(f"❌ 伺服器金鑰驗證失敗: {e}")
        raise HTTPException(status_code=401, detail="認證失敗")


# ========== API 端點 ==========


@router.post("/sync", response_model=SyncResponse)
async def sync_economy_data(
    request: SyncRequest,
    background_tasks: BackgroundTasks,
    server_key: str = Depends(verify_server_key),
):
    """處理跨平台經濟數據同步"""
    try:
        logger.info(f"🔄 收到同步請求：用戶 {request.user_id} 來自 {request.sync_type}")

        # 驗證請求數據
        if not all([request.user_id, request.guild_id, request.balances]):
            raise HTTPException(status_code=400, detail="請求數據不完整")

        # 獲取當前用戶經濟數據
        current_economy = await economy_manager.get_user_economy(
            request.user_id, request.guild_id
        )

        # 準備回應數據
        response_data = {
            "status": "success",
            "message": "同步完成",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "adjusted_balances": request.balances.copy(),
        }

        # 檢查是否需要調整餘額
        adjustments = {}
        minecraft_adjustments = {}

        for currency, new_amount in request.balances.items():
            current_amount = current_economy.get(currency, 0)

            if current_amount != new_amount:
                difference = new_amount - current_amount

                # 更新本地餘額
                try:
                    if currency == "coins":
                        if difference > 0:
                            await economy_manager.add_coins(
                                request.user_id, request.guild_id, difference
                            )
                        else:
                            await economy_manager.subtract_coins(
                                request.user_id, request.guild_id, abs(difference)
                            )
                    elif currency == "gems":
                        await economy_manager.add_gems(
                            request.user_id, request.guild_id, difference
                        )
                    elif currency == "experience":
                        await economy_manager.add_experience(
                            request.user_id, request.guild_id, difference
                        )

                    adjustments[currency] = difference

                except Exception as e:
                    logger.error(f"❌ 更新 {currency} 餘額失敗: {e}")
                    response_data["status"] = "partial_success"
                    response_data["message"] = f"部分同步失敗：{currency}"

        # 如果有 Minecraft 端的特殊調整（如服務器獎勵加成）
        settings = await economy_manager.get_economy_settings(request.guild_id)
        if (
            hasattr(settings, "minecraft_bonus_enabled")
            and settings.minecraft_bonus_enabled
        ):
            # 計算 Minecraft 端獎勵加成
            bonus_coins = sum(request.balances.values()) // 100  # 1% 獎勵加成
            if bonus_coins > 0:
                await economy_manager.add_coins(
                    request.user_id, request.guild_id, bonus_coins
                )
                minecraft_adjustments = {
                    "reason": "Minecraft 伺服器獎勵加成",
                    "bonus_coins": bonus_coins,
                }
                response_data["adjusted_balances"]["coins"] += bonus_coins

        if adjustments:
            response_data["minecraft_adjustments"] = minecraft_adjustments

        # 背景任務：觸發反向同步和統計更新
        background_tasks.add_task(
            _update_sync_statistics,
            request.guild_id,
            request.sync_type,
            len(adjustments),
        )

        logger.info(
            f"✅ 同步完成：用戶 {request.user_id} 調整了 {len(adjustments)} 項餘額"
        )

        return SyncResponse(**response_data)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ 同步處理失敗: {e}")
        raise HTTPException(status_code=500, detail=f"同步失敗：{str(e)}")


@router.post("/webhook")
async def handle_minecraft_webhook(
    request: WebhookRequest,
    background_tasks: BackgroundTasks,
    server_key: str = Depends(verify_server_key),
):
    """處理來自 Minecraft 的 Webhook 事件"""
    try:
        logger.info(
            f"📨 收到 Minecraft Webhook：{request.event_type} 用戶 {request.user_id}"
        )

        # 轉換為經濟管理器可處理的格式
        webhook_data = {
            "event_type": request.event_type,
            "user_id": request.user_id,
            "guild_id": request.guild_id,
            "activity_type": request.activity_type,
            "reward_amount": request.reward_amount,
            "metadata": request.metadata or {},
        }

        # 調用經濟管理器處理 Webhook
        success = await economy_manager.handle_minecraft_webhook(webhook_data)

        if success:
            # 背景任務：觸發跨平台同步
            background_tasks.add_task(
                economy_manager.trigger_cross_platform_sync,
                request.user_id,
                request.guild_id,
            )

            return {
                "status": "success",
                "message": "Webhook 處理成功",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        else:
            raise HTTPException(status_code=400, detail="Webhook 處理失敗")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Minecraft Webhook 處理失敗: {e}")
        raise HTTPException(status_code=500, detail=f"Webhook 處理失敗：{str(e)}")


@router.get("/player/{user_id}", response_model=PlayerEconomyResponse)
async def get_player_economy(
    user_id: int, guild_id: int, server_key: str = Depends(verify_server_key)
):
    """獲取玩家經濟數據"""
    try:
        # 獲取用戶經濟數據
        economy_data = await economy_manager.get_user_economy(user_id, guild_id)

        # 獲取等級資訊
        level_info = await economy_manager.calculate_level(
            economy_data.get("experience", 0)
        )

        # 獲取同步狀態
        settings = await economy_manager.get_economy_settings(guild_id)

        return PlayerEconomyResponse(
            user_id=user_id,
            guild_id=guild_id,
            balances={
                "coins": economy_data.get("coins", 0),
                "gems": economy_data.get("gems", 0),
                "tickets": economy_data.get("tickets", 0),
                "experience": economy_data.get("experience", 0),
            },
            level_info=level_info,
            daily_stats={
                "daily_games": economy_data.get("daily_games", 0),
                "daily_wins": economy_data.get("daily_wins", 0),
                "daily_claimed": economy_data.get("daily_claimed", False),
            },
            sync_status={
                "enabled": settings.sync_enabled,
                "last_sync": economy_manager._last_sync_time.get(user_id),
                "pending_syncs": len(
                    [t for t in economy_manager._sync_tasks.keys() if t == user_id]
                ),
            },
        )

    except Exception as e:
        logger.error(f"❌ 獲取玩家經濟數據失敗: {e}")
        raise HTTPException(status_code=500, detail=f"獲取數據失敗：{str(e)}")


@router.get("/stats/{guild_id}", response_model=EconomyStatsResponse)
async def get_economy_stats(
    guild_id: int, server_key: str = Depends(verify_server_key)
):
    """獲取伺服器經濟統計"""
    try:
        # 獲取傳統經濟統計
        traditional_stats = await economy_manager.get_economy_stats(guild_id)

        # 獲取跨平台統計
        cross_platform_stats = await economy_manager.get_cross_platform_statistics(
            guild_id
        )

        # 獲取設定資訊
        settings = await economy_manager.get_economy_settings(guild_id)

        return EconomyStatsResponse(
            server_info={
                "guild_id": guild_id,
                "sync_enabled": settings.sync_enabled,
                "inflation_threshold": settings.inflation_threshold,
                "last_updated": settings.last_updated.isoformat(),
            },
            currency_supply={
                "total_coins": traditional_stats.get("total_coins", 0),
                "total_gems": traditional_stats.get("total_gems", 0),
                "avg_coins": traditional_stats.get("avg_coins", 0),
            },
            user_stats={
                "total_users": traditional_stats.get("total_users", 0),
                "daily_checkins": traditional_stats.get("daily_checkins", 0),
                "total_games": traditional_stats.get("total_games", 0),
                "win_rate": traditional_stats.get("win_rate", 0),
            },
            inflation_data=economy_manager._inflation_data.get(guild_id, {}),
            sync_stats=cross_platform_stats,
        )

    except Exception as e:
        logger.error(f"❌ 獲取經濟統計失敗: {e}")
        raise HTTPException(status_code=500, detail=f"獲取統計失敗：{str(e)}")


@router.post("/admin/adjust")
async def admin_economy_adjust(
    request: Dict[str, Any], server_key: str = Depends(verify_server_key)
):
    """管理員經濟調整接口"""
    try:
        action = request.get("action")
        guild_id = request.get("guild_id")

        if not all([action, guild_id]):
            raise HTTPException(status_code=400, detail="請求參數不完整")

        result = {}

        if action == "anti_inflation":
            # 執行抗通膨調整
            result = await economy_manager.perform_anti_inflation_adjustment(guild_id)

        elif action == "update_settings":
            # 更新經濟設定
            settings_update = request.get("settings", {})
            updated_settings = await economy_manager.update_economy_settings(
                guild_id, **settings_update
            )
            result = {
                "status": "success",
                "updated_settings": {
                    "inflation_threshold": updated_settings.inflation_threshold,
                    "sync_enabled": updated_settings.sync_enabled,
                    "last_updated": updated_settings.last_updated.isoformat(),
                },
            }

        elif action == "force_sync_all":
            # 強制同步所有用戶
            user_ids = request.get("user_ids", [])
            sync_results = []

            for user_id in user_ids:
                try:
                    await economy_manager.trigger_cross_platform_sync(user_id, guild_id)
                    sync_results.append({"user_id": user_id, "status": "triggered"})
                except Exception as e:
                    sync_results.append(
                        {"user_id": user_id, "status": "failed", "error": str(e)}
                    )

            result = {"sync_results": sync_results}

        else:
            raise HTTPException(status_code=400, detail=f"不支援的操作：{action}")

        logger.info(f"✅ 管理員操作完成：{action} for guild {guild_id}")

        return {
            "status": "success",
            "action": action,
            "guild_id": guild_id,
            "result": result,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ 管理員操作失敗: {e}")
        raise HTTPException(status_code=500, detail=f"操作失敗：{str(e)}")


@router.get("/health")
async def health_check():
    """健康檢查端點"""
    try:
        # 檢查經濟管理器狀態
        await economy_manager.get_economy_settings(0)

        # 檢查活躍同步任務
        active_syncs = len(economy_manager._sync_tasks)

        # 檢查交易記錄數量
        total_transactions = len(economy_manager._cross_platform_transactions)

        return {
            "status": "healthy",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "service": "cross_platform_economy",
            "version": "3.0.0",
            "metrics": {
                "active_sync_tasks": active_syncs,
                "total_transactions": total_transactions,
                "configured_guilds": len(economy_manager._economy_settings),
            },
        }

    except Exception as e:
        logger.error(f"❌ 健康檢查失敗: {e}")
        return {
            "status": "unhealthy",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "error": str(e),
        }


# ========== 輔助函數 ==========


async def _update_sync_statistics(
    guild_id: int, sync_type: str, adjustments_count: int
):
    """更新同步統計（背景任務）"""
    try:
        # 這裡可以實現更詳細的同步統計記錄
        logger.info(
            f"📊 同步統計更新：伺服器 {guild_id} {sync_type} 調整 {adjustments_count} 項"
        )

    except Exception as e:
        logger.error(f"❌ 更新同步統計失敗: {e}")


# 將路由添加到主 API 應用
def register_economy_routes(app):
    """註冊經濟系統路由到主應用"""
    app.include_router(router)
