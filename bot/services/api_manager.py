# bot/services/api_manager.py - API 基礎架構管理服務
"""
API 基礎架構管理服務
提供 RESTful API 端點、認證、限流等功能的統一管理
"""

import asyncio
import base64
import hashlib
import hmac
import json
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Dict, List, Optional

from bot.db.ticket_dao import TicketDAO
from bot.db.vote_dao import VoteDAO
from bot.services.ai_manager import AIManager
from bot.services.language_manager import LanguageManager
from bot.services.statistics_manager import StatisticsManager
from bot.services.ticket_manager import TicketManager
from shared.logger import logger


@dataclass
class APIKey:
    """API 金鑰結構"""

    key_id: str
    key_secret: str
    guild_id: int
    permissions: List[str]
    rate_limit: int
    created_at: datetime
    expires_at: Optional[datetime] = None
    is_active: bool = True


@dataclass
class APIRequest:
    """API 請求結構"""

    endpoint: str
    method: str
    guild_id: int
    user_id: Optional[int]
    parameters: Dict[str, Any]
    headers: Dict[str, str]
    timestamp: datetime
    api_key_id: Optional[str] = None


@dataclass
class APIResponse:
    """API 回應結構"""

    status_code: int
    data: Any
    message: str
    timestamp: datetime
    request_id: Optional[str] = None
    rate_limit_remaining: int = 0


class APIManager:
    """API 基礎架構管理器"""

    def __init__(self, bot):
        self.bot = bot
        self.statistics_manager = StatisticsManager()
        self.ai_manager = AIManager()
        self.language_manager = LanguageManager()
        self.ticket_manager = TicketManager(TicketDAO())
        self.vote_dao = VoteDAO()

        # API 金鑰存儲（實際應用中應使用資料庫）
        self.api_keys: Dict[str, APIKey] = {}

        # 速率限制追蹤
        self.rate_limits: Dict[str, Dict[str, Any]] = {}

        # 支援的端點
        self.endpoints = self._register_endpoints()

    # ========== API 金鑰管理 ==========

    def generate_api_key(
        self, guild_id: int, permissions: List[str], rate_limit: int = 100, expires_days: int = None
    ) -> APIKey:
        """生成 API 金鑰"""
        try:
            import secrets

            key_id = f"pk_{secrets.token_urlsafe(16)}"
            key_secret = secrets.token_urlsafe(32)

            expires_at = None
            if expires_days:
                expires_at = datetime.now(timezone.utc) + timedelta(days=expires_days)

            api_key = APIKey(
                key_id=key_id,
                key_secret=key_secret,
                guild_id=guild_id,
                permissions=permissions,
                rate_limit=rate_limit,
                created_at=datetime.now(timezone.utc),
                expires_at=expires_at,
            )

            self.api_keys[key_id] = api_key
            logger.info(f"API 金鑰已生成: {key_id} for guild {guild_id}")

            return api_key

        except Exception as e:
            logger.error(f"生成 API 金鑰錯誤: {e}")
            raise

    def revoke_api_key(self, key_id: str) -> bool:
        """撤銷 API 金鑰"""
        try:
            if key_id in self.api_keys:
                self.api_keys[key_id].is_active = False
                logger.info(f"API 金鑰已撤銷: {key_id}")
                return True
            return False

        except Exception as e:
            logger.error(f"撤銷 API 金鑰錯誤: {e}")
            return False

    def validate_api_key(self, key_id: str, signature: str, request_data: str) -> Optional[APIKey]:
        """驗證 API 金鑰和簽名"""
        try:
            if key_id not in self.api_keys:
                return None

            api_key = self.api_keys[key_id]

            # 檢查金鑰是否有效
            if not api_key.is_active:
                return None

            # 檢查是否過期
            if api_key.expires_at and datetime.now(timezone.utc) > api_key.expires_at:
                api_key.is_active = False
                return None

            # 驗證簽名
            expected_signature = self._generate_signature(api_key.key_secret, request_data)
            if not hmac.compare_digest(signature, expected_signature):
                return None

            return api_key

        except Exception as e:
            logger.error(f"驗證 API 金鑰錯誤: {e}")
            return None

    def _generate_signature(self, secret: str, data: str) -> str:
        """生成請求簽名"""
        signature = hmac.new(
            secret.encode("utf-8"), data.encode("utf-8"), hashlib.sha256
        ).hexdigest()
        return signature

    # ========== 速率限制 ==========

    def check_rate_limit(self, key_id: str) -> Tuple[bool, int]:
        """檢查速率限制"""
        try:
            now = datetime.now(timezone.utc)
            window_start = now.replace(minute=0, second=0, microsecond=0)

            if key_id not in self.rate_limits:
                self.rate_limits[key_id] = {"count": 0, "window_start": window_start}

            rate_data = self.rate_limits[key_id]

            # 重置窗口
            if now >= rate_data["window_start"] + timedelta(hours=1):
                rate_data["count"] = 0
                rate_data["window_start"] = window_start

            api_key = self.api_keys.get(key_id)
            if not api_key:
                return False, 0

            # 檢查是否超過限制
            if rate_data["count"] >= api_key.rate_limit:
                return False, 0

            # 增加計數
            rate_data["count"] += 1
            remaining = api_key.rate_limit - rate_data["count"]

            return True, remaining

        except Exception as e:
            logger.error(f"檢查速率限制錯誤: {e}")
            return False, 0

    # ========== API 端點註冊 ==========

    def _register_endpoints(self) -> Dict[str, Dict[str, Any]]:
        """註冊 API 端點"""
        return {
            # 統計端點
            "GET /api/v1/statistics/overview": {
                "handler": self._handle_statistics_overview,
                "permissions": ["statistics:read"],
                "description": "取得系統統計概覽",
            },
            "GET /api/v1/statistics/performance": {
                "handler": self._handle_statistics_performance,
                "permissions": ["statistics:read"],
                "description": "取得性能報告",
            },
            "GET /api/v1/statistics/trends": {
                "handler": self._handle_statistics_trends,
                "permissions": ["statistics:read"],
                "description": "取得趨勢分析",
            },
            # 票券端點
            "GET /api/v1/tickets": {
                "handler": self._handle_tickets_list,
                "permissions": ["tickets:read"],
                "description": "取得票券列表",
            },
            "GET /api/v1/tickets/{id}": {
                "handler": self._handle_tickets_get,
                "permissions": ["tickets:read"],
                "description": "取得特定票券",
            },
            "POST /api/v1/tickets": {
                "handler": self._handle_tickets_create,
                "permissions": ["tickets:write"],
                "description": "創建票券",
            },
            "PUT /api/v1/tickets/{id}": {
                "handler": self._handle_tickets_update,
                "permissions": ["tickets:write"],
                "description": "更新票券",
            },
            # AI 端點
            "POST /api/v1/ai/suggest": {
                "handler": self._handle_ai_suggest,
                "permissions": ["ai:use"],
                "description": "AI 智能建議",
            },
            "GET /api/v1/ai/statistics": {
                "handler": self._handle_ai_statistics,
                "permissions": ["ai:read"],
                "description": "AI 使用統計",
            },
            # 語言端點
            "GET /api/v1/language/stats": {
                "handler": self._handle_language_stats,
                "permissions": ["language:read"],
                "description": "語言使用統計",
            },
            "POST /api/v1/language/detect": {
                "handler": self._handle_language_detect,
                "permissions": ["language:use"],
                "description": "語言偵測",
            },
            # 投票端點
            "GET /api/v1/votes": {
                "handler": self._handle_votes_list,
                "permissions": ["votes:read"],
                "description": "取得投票列表",
            },
            "GET /api/v1/votes/{id}": {
                "handler": self._handle_votes_get,
                "permissions": ["votes:read"],
                "description": "取得特定投票",
            },
        }

    # ========== 請求處理 ==========

    async def handle_api_request(self, request: APIRequest) -> APIResponse:
        """處理 API 請求"""
        try:
            # 1. 驗證端點
            endpoint_key = f"{request.method} {request.endpoint}"
            if endpoint_key not in self.endpoints:
                return APIResponse(
                    status_code=404,
                    data=None,
                    message="端點不存在",
                    timestamp=datetime.now(timezone.utc),
                )

            endpoint_config = self.endpoints[endpoint_key]

            # 2. 驗證 API 金鑰（如果需要）
            if request.api_key_id:
                # 從 headers 取得簽名
                signature = request.headers.get("X-Signature", "")
                request_data = json.dumps(request.parameters, sort_keys=True)

                api_key = self.validate_api_key(request.api_key_id, signature, request_data)
                if not api_key:
                    return APIResponse(
                        status_code=401,
                        data=None,
                        message="API 金鑰無效",
                        timestamp=datetime.now(timezone.utc),
                    )

                # 3. 檢查權限
                required_permissions = endpoint_config.get("permissions", [])
                if not self._check_permissions(api_key.permissions, required_permissions):
                    return APIResponse(
                        status_code=403,
                        data=None,
                        message="權限不足",
                        timestamp=datetime.now(timezone.utc),
                    )

                # 4. 檢查速率限制
                allowed, remaining = self.check_rate_limit(request.api_key_id)
                if not allowed:
                    return APIResponse(
                        status_code=429,
                        data=None,
                        message="速率限制超過",
                        timestamp=datetime.now(timezone.utc),
                        rate_limit_remaining=0,
                    )
            else:
                remaining = 0

            # 5. 處理請求
            handler = endpoint_config["handler"]
            response_data = await handler(request)

            return APIResponse(
                status_code=200,
                data=response_data,
                message="成功",
                timestamp=datetime.now(timezone.utc),
                rate_limit_remaining=remaining,
            )

        except Exception as e:
            logger.error(f"處理 API 請求錯誤: {e}")
            return APIResponse(
                status_code=500,
                data=None,
                message=f"內部伺服器錯誤: {str(e)}",
                timestamp=datetime.now(timezone.utc),
            )

    def _check_permissions(
        self, user_permissions: List[str], required_permissions: List[str]
    ) -> bool:
        """檢查權限"""
        if "admin" in user_permissions:
            return True

        for required in required_permissions:
            if required not in user_permissions:
                return False

        return True

    # ========== API 處理器 ==========

    async def _handle_statistics_overview(self, request: APIRequest) -> Dict[str, Any]:
        """處理統計概覽請求"""
        days = request.parameters.get("days", 30)
        return await self.statistics_manager.get_system_overview(request.guild_id, days)

    async def _handle_statistics_performance(self, request: APIRequest) -> Dict[str, Any]:
        """處理性能報告請求"""
        days = request.parameters.get("days", 30)
        # 需要在 StatisticsManager 中實現 get_performance_report 方法
        return {"message": "Performance report not implemented yet"}

    async def _handle_statistics_trends(self, request: APIRequest) -> Dict[str, Any]:
        """處理趨勢分析請求"""
        metric = request.parameters.get("metric", "tickets")
        days = request.parameters.get("days", 30)
        # 需要在 StatisticsManager 中實現 get_trend_analysis 方法
        return {"message": "Trend analysis not implemented yet"}

    async def _handle_tickets_list(self, request: APIRequest) -> Dict[str, Any]:
        """處理票券列表請求"""
        page = request.parameters.get("page", 1)
        page_size = request.parameters.get("page_size", 50)
        status = request.parameters.get("status")

        tickets, total_count = await self.ticket_manager.dao.paginate_tickets(
            guild_id=request.guild_id, page=page, page_size=page_size, status=status
        )

        return {
            "tickets": tickets,
            "pagination": {
                "page": page,
                "page_size": page_size,
                "total": total_count,
                "pages": (total_count + page_size - 1) // page_size,
            },
        }

    async def _handle_tickets_get(self, request: APIRequest) -> Dict[str, Any]:
        """處理取得特定票券請求"""
        ticket_id = request.parameters.get("id")
        if not ticket_id:
            raise ValueError("缺少票券 ID")

        ticket = await self.ticket_manager.dao.get_ticket_by_id(int(ticket_id))
        if not ticket:
            raise ValueError("票券不存在")

        return ticket

    async def _handle_tickets_create(self, request: APIRequest) -> Dict[str, Any]:
        """處理創建票券請求"""
        # 這裡需要實現票券創建邏輯
        return {"message": "Ticket creation via API not implemented yet"}

    async def _handle_tickets_update(self, request: APIRequest) -> Dict[str, Any]:
        """處理更新票券請求"""
        # 這裡需要實現票券更新邏輯
        return {"message": "Ticket update via API not implemented yet"}

    async def _handle_ai_suggest(self, request: APIRequest) -> Dict[str, Any]:
        """處理 AI 建議請求"""
        content = request.parameters.get("content")
        if not content:
            raise ValueError("缺少內容參數")

        context = {"guild_id": request.guild_id, "user_id": request.user_id}

        return await self.ai_manager.suggest_reply(content, context)

    async def _handle_ai_statistics(self, request: APIRequest) -> Dict[str, Any]:
        """處理 AI 統計請求"""
        days = request.parameters.get("days", 30)
        return await self.ai_manager.get_ai_statistics(request.guild_id, days)

    async def _handle_language_stats(self, request: APIRequest) -> Dict[str, Any]:
        """處理語言統計請求"""
        # 需要實現語言統計邏輯
        return {"message": "Language statistics not implemented yet"}

    async def _handle_language_detect(self, request: APIRequest) -> Dict[str, Any]:
        """處理語言偵測請求"""
        text = request.parameters.get("text")
        if not text:
            raise ValueError("缺少文本參數")

        detected_language = self.language_manager.detect_language(text)
        confidence = 0.8  # 簡單的置信度

        return {
            "detected_language": detected_language,
            "confidence": confidence,
            "supported_languages": self.language_manager.get_supported_languages(),
        }

    async def _handle_votes_list(self, request: APIRequest) -> Dict[str, Any]:
        """處理投票列表請求"""
        limit = request.parameters.get("limit", 50)
        active_only = request.parameters.get("active_only", False)

        # 這裡需要實現投票列表查詢
        return {"message": "Vote list API not implemented yet"}

    async def _handle_votes_get(self, request: APIRequest) -> Dict[str, Any]:
        """處理取得特定投票請求"""
        vote_id = request.parameters.get("id")
        if not vote_id:
            raise ValueError("缺少投票 ID")

        # 這裡需要實現投票查詢
        return {"message": "Vote get API not implemented yet"}

    # ========== 實用工具 ==========

    def get_api_documentation(self) -> Dict[str, Any]:
        """取得 API 文檔"""
        documentation = {
            "version": "1.0.0",
            "title": "Potato Bot API",
            "description": "Discord Bot API 服務",
            "base_url": "/api/v1",
            "authentication": {
                "type": "API Key + Signature",
                "description": "使用 API Key 和 HMAC 簽名進行認證",
            },
            "rate_limits": {"description": "每小時限制請求次數", "default_limit": 100},
            "endpoints": {},
        }

        for endpoint, config in self.endpoints.items():
            method, path = endpoint.split(" ", 1)

            documentation["endpoints"][endpoint] = {
                "method": method,
                "path": path,
                "description": config.get("description", ""),
                "permissions": config.get("permissions", []),
                "parameters": self._get_endpoint_parameters(endpoint),
            }

        return documentation

    def _get_endpoint_parameters(self, endpoint: str) -> Dict[str, Any]:
        """取得端點參數描述"""
        # 這裡可以根據不同端點返回參數描述
        parameter_docs = {
            "GET /api/v1/statistics/overview": {
                "days": {"type": "integer", "default": 30, "description": "統計天數"}
            },
            "GET /api/v1/tickets": {
                "page": {"type": "integer", "default": 1, "description": "頁碼"},
                "page_size": {"type": "integer", "default": 50, "description": "每頁數量"},
                "status": {"type": "string", "description": "票券狀態篩選"},
            },
            "POST /api/v1/ai/suggest": {
                "content": {"type": "string", "required": True, "description": "要分析的內容"}
            },
            "POST /api/v1/language/detect": {
                "text": {"type": "string", "required": True, "description": "要偵測的文本"}
            },
        }

        return parameter_docs.get(endpoint, {})

    def get_api_key_info(self, key_id: str) -> Optional[Dict[str, Any]]:
        """取得 API 金鑰資訊"""
        if key_id not in self.api_keys:
            return None

        api_key = self.api_keys[key_id]

        return {
            "key_id": api_key.key_id,
            "guild_id": api_key.guild_id,
            "permissions": api_key.permissions,
            "rate_limit": api_key.rate_limit,
            "created_at": api_key.created_at.isoformat(),
            "expires_at": api_key.expires_at.isoformat() if api_key.expires_at else None,
            "is_active": api_key.is_active,
            "current_usage": self.rate_limits.get(key_id, {}).get("count", 0),
        }

    def list_api_keys(self, guild_id: int) -> List[Dict[str, Any]]:
        """列出伺服器的所有 API 金鑰"""
        keys = []
        for key_id, api_key in self.api_keys.items():
            if api_key.guild_id == guild_id:
                key_info = self.get_api_key_info(key_id)
                if key_info:
                    # 不回傳密鑰
                    key_info.pop("key_secret", None)
                    keys.append(key_info)

        return keys
