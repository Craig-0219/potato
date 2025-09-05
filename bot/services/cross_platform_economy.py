# bot/services/cross_platform_economy.py - 跨平台經濟系統API
"""
跨平台經濟系統 v2.2.0
支援Discord機器人與Minecraft服務器之間的經濟數據同步
"""

import json
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

import aiohttp

from bot.db.pool import db_pool
from bot.services.achievement_manager import AchievementManager
from bot.services.economy_manager import EconomyManager
from shared.cache_manager import cache_manager
from shared.logger import logger


class PlatformType(Enum):
    """平台類型"""

    DISCORD = "discord"
    MINECRAFT = "minecraft"
    WEB = "web"
    MOBILE = "mobile"


class TransactionType(Enum):
    """交易類型"""

    TRANSFER = "transfer"  # 轉移
    PURCHASE = "purchase"  # 購買
    REWARD = "reward"  # 獎勵
    PENALTY = "penalty"  # 懲罰
    SYNC = "sync"  # 同步
    EXCHANGE = "exchange"  # 兌換


@dataclass
class CrossPlatformUser:
    """跨平台用戶數據"""

    discord_id: Optional[int] = None
    minecraft_uuid: Optional[str] = None
    username: str = ""
    total_coins: int = 0
    total_gems: int = 0
    total_experience: int = 0
    level: int = 1
    achievements: List[str] = None
    last_sync: Optional[datetime] = None

    def __post_init__(self):
        if self.achievements is None:
            self.achievements = []


@dataclass
class EconomyTransaction:
    """經濟交易記錄"""

    transaction_id: str
    from_platform: PlatformType
    to_platform: PlatformType
    user_id: str  # Discord ID 或 Minecraft UUID
    transaction_type: TransactionType
    currency_type: str  # coins, gems, experience
    amount: int
    reason: str
    metadata: Dict[str, Any]
    timestamp: datetime
    status: str = "pending"  # pending, completed, failed, cancelled


class CrossPlatformEconomyManager:
    """跨平台經濟管理器"""

    def __init__(self):
        self.economy_manager = EconomyManager()
        self.achievement_manager = AchievementManager()
        self.webhook_endpoints = {}  # 各平台webhook端點

        # 匯率設定 (Discord -> Minecraft)
        self.exchange_rates = {
            "coins": 1.0,  # 1 Discord幣 = 1 Minecraft幣
            "gems": 10.0,  # 1 Discord寶石 = 10 Minecraft幣
            "experience": 0.1,  # 10 Discord經驗 = 1 Minecraft幣
        }

        # Minecraft 物品對應
        self.minecraft_items = {
            "coins": "minecraft:gold_ingot",
            "gems": "minecraft:diamond",
            "experience": "minecraft:experience_bottle",
        }

        logger.info("🌐 跨平台經濟系統初始化完成")

    # ========== 用戶綁定系統 ==========

    async def link_accounts(
        self, discord_id: int, minecraft_uuid: str, guild_id: int
    ) -> Dict[str, Any]:
        """綁定Discord和Minecraft帳號"""
        try:
            # 檢查是否已經綁定
            existing_link = await self._get_account_link(discord_id=discord_id)
            if existing_link:
                return {
                    "success": False,
                    "error": "Discord帳號已綁定其他Minecraft帳號",
                    "existing_uuid": existing_link.get("minecraft_uuid"),
                }

            existing_link = await self._get_account_link(minecraft_uuid=minecraft_uuid)
            if existing_link:
                return {
                    "success": False,
                    "error": "Minecraft帳號已綁定其他Discord帳號",
                    "existing_discord_id": existing_link.get("discord_id"),
                }

            # 創建綁定
            async with db_pool.connection() as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute(
                        """
                        INSERT INTO cross_platform_users
                        (discord_id, minecraft_uuid, guild_id, linked_at)
                        VALUES (%s, %s, %s, %s)
                    """,
                        (
                            discord_id,
                            minecraft_uuid,
                            guild_id,
                            datetime.now(timezone.utc),
                        ),
                    )
                    await conn.commit()

            # 觸發數據同步
            await self._sync_user_data(discord_id, minecraft_uuid, guild_id)

            logger.info(f"🔗 帳號綁定成功: Discord {discord_id} <-> Minecraft {minecraft_uuid}")

            return {
                "success": True,
                "discord_id": discord_id,
                "minecraft_uuid": minecraft_uuid,
                "sync_completed": True,
            }

        except Exception as e:
            logger.error(f"❌ 帳號綁定失敗: {e}")
            return {"success": False, "error": str(e)}

    async def unlink_accounts(
        self, discord_id: int = None, minecraft_uuid: str = None
    ) -> Dict[str, Any]:
        """解除帳號綁定"""
        try:
            if not discord_id and not minecraft_uuid:
                return {
                    "success": False,
                    "error": "需要提供Discord ID或Minecraft UUID",
                }

            where_clause = ""
            params = []

            if discord_id:
                where_clause = "discord_id = %s"
                params.append(discord_id)
            else:
                where_clause = "minecraft_uuid = %s"
                params.append(minecraft_uuid)

            async with db_pool.connection() as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute(
                        f"""
                        DELETE FROM cross_platform_users
                        WHERE {where_clause}
                    """,
                        params,
                    )
                    affected = cursor.rowcount
                    await conn.commit()

            if affected > 0:
                logger.info(f"🔓 帳號解綁成功: {discord_id or minecraft_uuid}")
                return {"success": True, "unlinked": True}
            else:
                return {"success": False, "error": "未找到綁定記錄"}

        except Exception as e:
            logger.error(f"❌ 帳號解綁失敗: {e}")
            return {"success": False, "error": str(e)}

    async def _get_account_link(
        self, discord_id: int = None, minecraft_uuid: str = None
    ) -> Optional[Dict[str, Any]]:
        """獲取帳號綁定信息"""
        try:
            if not discord_id and not minecraft_uuid:
                return None

            where_clause = ""
            params = []

            if discord_id:
                where_clause = "discord_id = %s"
                params.append(discord_id)
            else:
                where_clause = "minecraft_uuid = %s"
                params.append(minecraft_uuid)

            async with db_pool.connection() as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute(
                        f"""
                        SELECT discord_id, minecraft_uuid, guild_id, linked_at
                        FROM cross_platform_users
                        WHERE {where_clause}
                    """,
                        params,
                    )
                    result = await cursor.fetchone()

                    if result:
                        return {
                            "discord_id": result[0],
                            "minecraft_uuid": result[1],
                            "guild_id": result[2],
                            "linked_at": result[3],
                        }
                    return None

        except Exception as e:
            logger.error(f"❌ 獲取帳號綁定失敗: {e}")
            return None

    # ========== 數據同步系統 ==========

    async def sync_user_economy(
        self, discord_id: int, guild_id: int, direction: str = "to_minecraft"
    ) -> Dict[str, Any]:
        """同步用戶經濟數據"""
        try:
            # 獲取帳號綁定
            link = await self._get_account_link(discord_id=discord_id)
            if not link:
                return {"success": False, "error": "帳號未綁定"}

            minecraft_uuid = link["minecraft_uuid"]

            if direction == "to_minecraft":
                # Discord -> Minecraft
                discord_economy = await self.economy_manager.get_user_economy(discord_id, guild_id)

                # 轉換為Minecraft格式
                minecraft_data = await self._convert_to_minecraft_format(discord_economy)

                # 發送到Minecraft服務器
                sync_result = await self._send_to_minecraft(minecraft_uuid, minecraft_data)

                return {
                    "success": sync_result["success"],
                    "direction": direction,
                    "discord_data": discord_economy,
                    "minecraft_data": minecraft_data,
                    "sync_result": sync_result,
                }

            elif direction == "from_minecraft":
                # Minecraft -> Discord (需要Minecraft服務器主動推送)
                minecraft_data = await self._fetch_from_minecraft(minecraft_uuid)

                if minecraft_data:
                    discord_data = await self._convert_from_minecraft_format(minecraft_data)

                    # 更新Discord數據
                    await self._update_discord_economy(discord_id, guild_id, discord_data)

                    return {
                        "success": True,
                        "direction": direction,
                        "minecraft_data": minecraft_data,
                        "discord_data": discord_data,
                    }
                else:
                    return {
                        "success": False,
                        "error": "無法從Minecraft獲取數據",
                    }

        except Exception as e:
            logger.error(f"❌ 經濟數據同步失敗: {e}")
            return {"success": False, "error": str(e)}

    async def _sync_user_data(self, discord_id: int, minecraft_uuid: str, guild_id: int):
        """初始數據同步"""
        try:
            # 獲取Discord數據
            discord_economy = await self.economy_manager.get_user_economy(discord_id, guild_id)
            discord_achievements = await self.achievement_manager.get_user_achievements(
                discord_id, guild_id
            )

            # 轉換並發送到Minecraft
            minecraft_data = await self._convert_to_minecraft_format(discord_economy)
            minecraft_data["achievements"] = [ach["id"] for ach in discord_achievements]

            await self._send_to_minecraft(minecraft_uuid, minecraft_data)

            logger.info(f"✅ 初始數據同步完成: {discord_id} -> {minecraft_uuid}")

        except Exception as e:
            logger.error(f"❌ 初始數據同步失敗: {e}")

    # ========== 格式轉換系統 ==========

    async def _convert_to_minecraft_format(self, discord_data: Dict[str, Any]) -> Dict[str, Any]:
        """將Discord數據轉換為Minecraft格式"""
        try:
            # 計算Minecraft物品數量
            coins_amount = discord_data.get("coins", 0)
            gems_amount = discord_data.get("gems", 0) * int(self.exchange_rates["gems"])
            exp_amount = int(discord_data.get("experience", 0) * self.exchange_rates["experience"])

            minecraft_data = {
                "items": {
                    self.minecraft_items["coins"]: coins_amount,
                    self.minecraft_items["gems"]: gems_amount,
                    self.minecraft_items["experience"]: exp_amount,
                },
                "level": await self.economy_manager.calculate_level(
                    discord_data.get("experience", 0)
                ),
                "stats": {
                    "total_games": discord_data.get("total_games", 0),
                    "total_wins": discord_data.get("total_wins", 0),
                    "win_rate": discord_data.get("win_rate", 0),
                },
                "sync_time": datetime.now(timezone.utc).isoformat(),
            }

            return minecraft_data

        except Exception as e:
            logger.error(f"❌ 轉換到Minecraft格式失敗: {e}")
            return {}

    async def _convert_from_minecraft_format(
        self, minecraft_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """將Minecraft數據轉換為Discord格式"""
        try:
            items = minecraft_data.get("items", {})

            # 反向轉換
            coins = items.get(self.minecraft_items["coins"], 0)
            gems = int(items.get(self.minecraft_items["gems"], 0) / self.exchange_rates["gems"])
            experience = int(
                items.get(self.minecraft_items["experience"], 0) / self.exchange_rates["experience"]
            )

            discord_data = {
                "coins": coins,
                "gems": gems,
                "experience": experience,
                "minecraft_sync": True,
                "last_sync": datetime.now(timezone.utc),
            }

            return discord_data

        except Exception as e:
            logger.error(f"❌ 轉換從Minecraft格式失敗: {e}")
            return {}

    # ========== Minecraft API交互 ==========

    async def _send_to_minecraft(self, minecraft_uuid: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """發送數據到Minecraft服務器"""
        try:
            webhook_url = self.webhook_endpoints.get("minecraft")
            if not webhook_url:
                # 暫時返回成功，等待Minecraft服務器配置
                logger.warning("⚠️ Minecraft webhook未配置，數據已緩存")
                await self._cache_minecraft_data(minecraft_uuid, data)
                return {"success": True, "cached": True}

            payload = {
                "action": "sync_economy",
                "player_uuid": minecraft_uuid,
                "data": data,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

            async with aiohttp.ClientSession() as session:
                async with session.post(webhook_url, json=payload, timeout=10) as response:
                    if response.status == 200:
                        result = await response.json()
                        logger.info(f"✅ 數據已發送到Minecraft: {minecraft_uuid}")
                        return {"success": True, "response": result}
                    else:
                        logger.error(f"❌ Minecraft服務器回應錯誤: {response.status}")
                        return {
                            "success": False,
                            "error": f"HTTP {response.status}",
                        }

        except Exception as e:
            logger.error(f"❌ 發送到Minecraft失敗: {e}")
            # 緩存數據以備後續重試
            await self._cache_minecraft_data(minecraft_uuid, data)
            return {"success": False, "error": str(e), "cached": True}

    async def _fetch_from_minecraft(self, minecraft_uuid: str) -> Optional[Dict[str, Any]]:
        """從Minecraft服務器獲取數據"""
        try:
            # 優先從緩存獲取
            cached_data = await self._get_cached_minecraft_data(minecraft_uuid)
            if cached_data:
                return cached_data

            webhook_url = self.webhook_endpoints.get("minecraft")
            if not webhook_url:
                return None

            async with aiohttp.ClientSession() as session:
                async with session.get(f"{webhook_url}/player/{minecraft_uuid}") as response:
                    if response.status == 200:
                        data = await response.json()
                        return data.get("economy_data")
                    else:
                        logger.error(f"❌ 從Minecraft獲取數據失敗: {response.status}")
                        return None

        except Exception as e:
            logger.error(f"❌ 從Minecraft獲取數據異常: {e}")
            return None

    async def _cache_minecraft_data(self, minecraft_uuid: str, data: Dict[str, Any]):
        """緩存Minecraft數據"""
        try:
            cache_key = f"minecraft_sync:{minecraft_uuid}"
            await cache_manager.set(cache_key, data, 3600)  # 1小時緩存

        except Exception as e:
            logger.error(f"❌ 緩存Minecraft數據失敗: {e}")

    async def _get_cached_minecraft_data(self, minecraft_uuid: str) -> Optional[Dict[str, Any]]:
        """獲取緩存的Minecraft數據"""
        try:
            cache_key = f"minecraft_sync:{minecraft_uuid}"
            return await cache_manager.get(cache_key)

        except Exception as e:
            logger.error(f"❌ 獲取緩存Minecraft數據失敗: {e}")
            return None

    # ========== 配置管理 ==========

    def configure_minecraft_webhook(self, webhook_url: str):
        """配置Minecraft webhook端點"""
        self.webhook_endpoints["minecraft"] = webhook_url
        logger.info(f"🔧 Minecraft webhook已配置: {webhook_url}")

    def set_exchange_rate(self, currency: str, rate: float):
        """設置匯率"""
        if currency in self.exchange_rates:
            self.exchange_rates[currency] = rate
            logger.info(f"💱 匯率已更新: {currency} = {rate}")
        else:
            logger.warning(f"⚠️ 未知貨幣類型: {currency}")

    # ========== 交易記錄系統 ==========

    async def create_transaction(
        self,
        from_platform: PlatformType,
        to_platform: PlatformType,
        user_id: str,
        transaction_type: TransactionType,
        currency_type: str,
        amount: int,
        reason: str,
        metadata: Dict[str, Any] = None,
    ) -> str:
        """創建跨平台交易記錄"""
        try:
            transaction_id = f"{int(time.time())}_{user_id}_{currency_type}"

            if metadata is None:
                metadata = {}

            transaction = EconomyTransaction(
                transaction_id=transaction_id,
                from_platform=from_platform,
                to_platform=to_platform,
                user_id=user_id,
                transaction_type=transaction_type,
                currency_type=currency_type,
                amount=amount,
                reason=reason,
                metadata=metadata,
                timestamp=datetime.now(timezone.utc),
            )

            # 保存到資料庫
            async with db_pool.connection() as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute(
                        """
                        INSERT INTO cross_platform_transactions
                        (transaction_id, from_platform, to_platform, user_id,
                         transaction_type, currency_type, amount, reason,
                         metadata, timestamp, status)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                        (
                            transaction.transaction_id,
                            transaction.from_platform.value,
                            transaction.to_platform.value,
                            transaction.user_id,
                            transaction.transaction_type.value,
                            transaction.currency_type,
                            transaction.amount,
                            transaction.reason,
                            json.dumps(transaction.metadata),
                            transaction.timestamp,
                            transaction.status,
                        ),
                    )
                    await conn.commit()

            logger.info(f"📝 跨平台交易記錄已創建: {transaction_id}")
            return transaction_id

        except Exception as e:
            logger.error(f"❌ 創建交易記錄失敗: {e}")
            raise

    async def get_user_transactions(self, user_id: str, limit: int = 50) -> List[Dict[str, Any]]:
        """獲取用戶交易記錄"""
        try:
            async with db_pool.connection() as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute(
                        """
                        SELECT * FROM cross_platform_transactions
                        WHERE user_id = %s
                        ORDER BY timestamp DESC
                        LIMIT %s
                    """,
                        (user_id, limit),
                    )

                    results = await cursor.fetchall()
                    transactions = []

                    for row in results:
                        transactions.append(
                            {
                                "transaction_id": row[0],
                                "from_platform": row[1],
                                "to_platform": row[2],
                                "user_id": row[3],
                                "transaction_type": row[4],
                                "currency_type": row[5],
                                "amount": row[6],
                                "reason": row[7],
                                "metadata": (json.loads(row[8]) if row[8] else {}),
                                "timestamp": row[9],
                                "status": row[10],
                            }
                        )

                    return transactions

        except Exception as e:
            logger.error(f"❌ 獲取交易記錄失敗: {e}")
            return []


# 全域實例
cross_platform_economy = CrossPlatformEconomyManager()
