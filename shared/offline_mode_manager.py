# shared/offline_mode.py
"""
內網/離線模式管理器
自動檢測網路環境並啟用對應功能
"""

import os
import socket
from dataclasses import dataclass
from typing import Any, Dict

from shared.logger import logger


@dataclass
class OfflineConfig:
    """離線模式配置"""

    local_api_enabled: bool = True
    local_cache_enabled: bool = True
    external_apis_disabled: bool = True
    websocket_fallback: bool = True
    database_only_mode: bool = True


class OfflineModeManager:
    """離線模式管理器"""

    def __init__(self):
        self.is_offline_mode = False
        self.config = OfflineConfig()
        self._detection_results = {}
        self._fallback_services = {}

    async def detect_environment(self) -> Dict[str, Any]:
        """檢測網路環境"""
        detection = {
            "internet_available": await self._check_internet(),
            "redis_available": await self._check_redis(),
            "external_apis_available": await self._check_external_apis(),
            "local_network_only": False,
        }

        # 判斷是否為內網環境
        detection["local_network_only"] = (
            not detection["internet_available"] or not detection["external_apis_available"]
        )

        self._detection_results = detection
        self.is_offline_mode = detection["local_network_only"]

        logger.info(f"環境檢測結果: {'內網模式' if self.is_offline_mode else '外網模式'}")
        logger.debug(f"檢測詳情: {detection}")

        return detection

    async def _check_internet(self) -> bool:
        """檢查網際網路連接"""
        try:
            # 嘗試連接 DNS 伺服器
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(3)
            result = sock.connect_ex(("8.8.8.8", 53))
            sock.close()
            return result == 0
        except Exception:
            return False

    async def _check_redis(self) -> bool:
        """檢查 Redis 連接"""
        redis_url = os.getenv("REDIS_URL")
        if not redis_url:
            return False

        try:
            import aioredis

            redis = aioredis.from_url(redis_url)
            await redis.ping()
            await redis.close()
            return True
        except Exception:
            try:
                import redis.asyncio as redis_async

                redis = redis_async.from_url(redis_url)
                await redis.ping()
                await redis.close()
                return True
            except Exception:
                return False

    async def _check_external_apis(self) -> bool:
        """檢查外部 API 可用性"""
        test_urls = ["https://httpbin.org/status/200", "https://api.github.com/status"]

        for url in test_urls:
            try:
                import aiohttp

                timeout = aiohttp.ClientTimeout(total=5)
                async with aiohttp.ClientSession(timeout=timeout) as session:
                    async with session.get(url) as response:
                        if response.status == 200:
                            return True
            except Exception:
                continue

        return False

    def configure_offline_mode(self):
        """配置離線模式"""
        if not self.is_offline_mode:
            logger.info("當前為外網模式，無需特殊配置")
            return

        logger.info("配置內網/離線模式...")

        # 設定環境變數
        os.environ["FORCE_LOCAL_API"] = "true"
        os.environ["DISABLE_EXTERNAL_APIS"] = "true"
        os.environ["USE_LOCAL_CACHE"] = "true"

        # 註冊回調服務
        self._setup_fallback_services()

        logger.info("內網模式配置完成")

    def _setup_fallback_services(self):
        """設置後備服務"""
        from shared.local_cache_manager import get_local_cache_manager

        # 本地快取管理器
        self._fallback_services["cache"] = get_local_cache_manager()

        # 本地 API 服務器將在機器人啟動時啟動
        logger.info("後備服務設置完成")

    def get_service_config(self) -> Dict[str, Any]:
        """獲取服務配置"""
        return {
            "api_server": {
                "type": "local" if self.is_offline_mode else "external",
                "enabled": True,
            },
            "cache": {"type": "memory" if self.is_offline_mode else "redis", "enabled": True},
            "websocket": {"type": "local" if self.is_offline_mode else "external", "enabled": True},
            "external_apis": {"enabled": not self.is_offline_mode},
        }

    def get_status(self) -> Dict[str, Any]:
        """獲取狀態信息"""
        return {
            "mode": "offline" if self.is_offline_mode else "online",
            "detection_results": self._detection_results,
            "config": {
                "local_api_enabled": self.config.local_api_enabled,
                "local_cache_enabled": self.config.local_cache_enabled,
                "external_apis_disabled": self.config.external_apis_disabled,
                "websocket_fallback": self.config.websocket_fallback,
                "database_only_mode": self.config.database_only_mode,
            },
            "fallback_services": list(self._fallback_services.keys()),
        }


# 全局實例
_offline_manager = None


def get_offline_manager() -> OfflineModeManager:
    """獲取離線模式管理器實例"""
    global _offline_manager
    if _offline_manager is None:
        _offline_manager = OfflineModeManager()
    return _offline_manager


async def auto_configure_environment():
    """自動配置環境"""
    manager = get_offline_manager()
    await manager.detect_environment()
    manager.configure_offline_mode()
    return manager


def is_offline_mode() -> bool:
    """檢查是否為離線模式"""
    manager = get_offline_manager()
    return manager.is_offline_mode
