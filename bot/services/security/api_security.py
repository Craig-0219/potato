# bot/services/security/api_security.py - v1.0.0
# 🛡️ API 安全與速率限制系統
# API Security & Rate Limiting Framework

import ipaddress
import logging
import secrets
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

from jose import jwt

from bot.db.pool import db_pool
from bot.services.security.audit_manager import (
    EventCategory,
    EventSeverity,
    SecurityEvent,
    audit_manager,
)

logger = logging.getLogger(__name__)


class RateLimitType(Enum):
    """速率限制類型"""

    PER_SECOND = "per_second"
    PER_MINUTE = "per_minute"
    PER_HOUR = "per_hour"
    PER_DAY = "per_day"


class APIKeyType(Enum):
    """API 密鑰類型"""

    READ_ONLY = "read_only"
    READ_WRITE = "read_write"
    ADMIN = "admin"
    SERVICE = "service"


@dataclass
class RateLimitRule:
    """速率限制規則"""

    limit_type: RateLimitType
    max_requests: int
    window_seconds: int
    burst_allowance: int = 0  # 突發請求允許量

    def get_window_size(self) -> int:
        """獲取時間窗口大小（秒）"""
        if self.limit_type == RateLimitType.PER_SECOND:
            return 1
        elif self.limit_type == RateLimitType.PER_MINUTE:
            return 60
        elif self.limit_type == RateLimitType.PER_HOUR:
            return 3600
        elif self.limit_type == RateLimitType.PER_DAY:
            return 86400
        return self.window_seconds


@dataclass
class APIKey:
    """API 密鑰"""

    id: int
    key: str
    name: str
    key_type: APIKeyType
    user_id: Optional[int]
    guild_id: Optional[int]
    permissions: List[str] = field(default_factory=list)
    rate_limits: List[RateLimitRule] = field(default_factory=list)
    is_active: bool = True
    created_at: datetime = field(default_factory=datetime.now)
    expires_at: Optional[datetime] = None
    last_used: Optional[datetime] = None
    usage_count: int = 0


class APISecurityManager:
    """
    API 安全管理器

    功能：
    - API 密鑰管理
    - JWT 令牌驗證
    - 速率限制控制
    - IP 白名單/黑名單
    - API 存取審計
    - 安全頭部檢查
    """

    def __init__(self):
        # JWT 配置
        self.jwt_secret = secrets.token_urlsafe(64)
        self.jwt_algorithm = "HS256"
        self.token_expiry = 3600  # 1 小時

        # 速率限制快取
        self._rate_limit_cache: Dict[str, deque] = defaultdict(
            lambda: deque(maxlen=1000)
        )
        self._api_keys_cache: Dict[str, APIKey] = {}

        # IP 控制
        self._ip_whitelist: set = set()
        self._ip_blacklist: set = set()

        # 安全設定
        self.require_https = True
        self.require_user_agent = True
        self.max_request_size = 10 * 1024 * 1024  # 10MB

        # 預設速率限制
        self.default_rate_limits = {
            APIKeyType.READ_ONLY: [
                RateLimitRule(RateLimitType.PER_MINUTE, 60, 60),
                RateLimitRule(RateLimitType.PER_HOUR, 1000, 3600),
            ],
            APIKeyType.READ_WRITE: [
                RateLimitRule(RateLimitType.PER_MINUTE, 100, 60),
                RateLimitRule(RateLimitType.PER_HOUR, 2000, 3600),
            ],
            APIKeyType.ADMIN: [
                RateLimitRule(RateLimitType.PER_MINUTE, 200, 60),
                RateLimitRule(RateLimitType.PER_HOUR, 5000, 3600),
            ],
            APIKeyType.SERVICE: [
                RateLimitRule(RateLimitType.PER_SECOND, 10, 1),
                RateLimitRule(RateLimitType.PER_HOUR, 10000, 3600),
            ],
        }

        logger.info("🛡️ API 安全管理器初始化完成")

    async def create_api_key(
        self,
        name: str,
        key_type: APIKeyType,
        user_id: Optional[int] = None,
        guild_id: Optional[int] = None,
        permissions: List[str] = None,
        expires_at: Optional[datetime] = None,
    ) -> Optional[APIKey]:
        """
        創建 API 密鑰

        Args:
            name: 密鑰名稱
            key_type: 密鑰類型
            user_id: 關聯的用戶 ID
            guild_id: 關聯的伺服器 ID
            permissions: 權限列表
            expires_at: 過期時間

        Returns:
            Optional[APIKey]: 創建的 API 密鑰
        """
        try:
            # 生成安全的 API 密鑰
            key_value = self._generate_api_key()

            # 獲取預設速率限制
            rate_limits = self.default_rate_limits.get(key_type, [])

            async with db_pool.connection() as conn:
                async with conn.cursor() as cursor:
                    # 插入 API 密鑰
                    await cursor.execute(
                        """
                        INSERT INTO api_keys (
                            key_value, name, key_type, user_id, guild_id,
                            permissions, is_active, created_at, expires_at
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                        (
                            key_value,
                            name,
                            key_type.value,
                            user_id,
                            guild_id,
                            ",".join(permissions or []),
                            True,
                            datetime.now(),
                            expires_at,
                        ),
                    )

                    api_key_id = cursor.lastrowid

                    # 插入速率限制規則
                    for rule in rate_limits:
                        await cursor.execute(
                            """
                            INSERT INTO api_rate_limits (
                                api_key_id, limit_type, max_requests, window_seconds, burst_allowance
                            ) VALUES (%s, %s, %s, %s, %s)
                        """,
                            (
                                api_key_id,
                                rule.limit_type.value,
                                rule.max_requests,
                                rule.window_seconds,
                                rule.burst_allowance,
                            ),
                        )

                    await conn.commit()

            # 創建 API 密鑰對象
            api_key = APIKey(
                id=api_key_id,
                key=key_value,
                name=name,
                key_type=key_type,
                user_id=user_id,
                guild_id=guild_id,
                permissions=permissions or [],
                rate_limits=rate_limits,
            )

            # 更新快取
            self._api_keys_cache[key_value] = api_key

            # 記錄安全事件
            await audit_manager.log_event(
                SecurityEvent(
                    user_id=user_id,
                    guild_id=guild_id,
                    event_type="api_key_created",
                    category=EventCategory.SYSTEM_CONFIG,
                    severity=EventSeverity.INFO,
                    message=f"API 密鑰已創建: {name}",
                    details={"api_key_id": api_key_id, "key_type": key_type.value},
                )
            )

            logger.info(f"🔑 API 密鑰已創建: {name} (ID: {api_key_id})")
            return api_key

        except Exception as e:
            logger.error(f"❌ API 密鑰創建失敗: {e}")
            return None

    async def validate_api_key(self, api_key: str) -> Optional[APIKey]:
        """
        驗證 API 密鑰

        Args:
            api_key: API 密鑰字符串

        Returns:
            Optional[APIKey]: 驗證成功的 API 密鑰對象
        """
        try:
            # 檢查快取
            if api_key in self._api_keys_cache:
                key_obj = self._api_keys_cache[api_key]

                # 檢查是否過期
                if key_obj.expires_at and datetime.now() > key_obj.expires_at:
                    return None

                # 更新使用統計
                key_obj.last_used = datetime.now()
                key_obj.usage_count += 1

                return key_obj

            # 從資料庫查詢
            async with db_pool.connection() as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute(
                        """
                        SELECT id, key_value, name, key_type, user_id, guild_id,
                               permissions, is_active, created_at, expires_at,
                               last_used, usage_count
                        FROM api_keys
                        WHERE key_value = %s AND is_active = TRUE
                    """,
                        (api_key,),
                    )

                    result = await cursor.fetchone()
                    if not result:
                        return None

                    # 檢查是否過期
                    expires_at = result[9]
                    if expires_at and datetime.now() > expires_at:
                        return None

                    # 獲取速率限制規則
                    await cursor.execute(
                        """
                        SELECT limit_type, max_requests, window_seconds, burst_allowance
                        FROM api_rate_limits
                        WHERE api_key_id = %s
                    """,
                        (result[0],),
                    )

                    rate_limits = []
                    for limit_row in await cursor.fetchall():
                        rate_limits.append(
                            RateLimitRule(
                                limit_type=RateLimitType(limit_row[0]),
                                max_requests=limit_row[1],
                                window_seconds=limit_row[2],
                                burst_allowance=limit_row[3],
                            )
                        )

                    # 更新使用統計
                    await cursor.execute(
                        """
                        UPDATE api_keys
                        SET last_used = %s, usage_count = usage_count + 1
                        WHERE id = %s
                    """,
                        (datetime.now(), result[0]),
                    )
                    await conn.commit()

            # 創建 API 密鑰對象
            api_key_obj = APIKey(
                id=result[0],
                key=result[1],
                name=result[2],
                key_type=APIKeyType(result[3]),
                user_id=result[4],
                guild_id=result[5],
                permissions=result[6].split(",") if result[6] else [],
                rate_limits=rate_limits,
                is_active=result[7],
                created_at=result[8],
                expires_at=result[9],
                last_used=datetime.now(),
                usage_count=result[11] + 1,
            )

            # 更新快取
            self._api_keys_cache[api_key] = api_key_obj

            return api_key_obj

        except Exception as e:
            logger.error(f"❌ API 密鑰驗證失敗: {e}")
            return None

    async def check_rate_limit(
        self, api_key: str, client_ip: str = None
    ) -> Tuple[bool, Dict[str, Any]]:
        """
        檢查速率限制

        Args:
            api_key: API 密鑰
            client_ip: 客戶端 IP

        Returns:
            Tuple[bool, Dict[str, Any]]: (是否允許, 限制資訊)
        """
        try:
            api_key_obj = await self.validate_api_key(api_key)
            if not api_key_obj:
                return False, {"error": "invalid_api_key"}

            current_time = time.time()
            rate_limit_info = {}

            # 檢查每個速率限制規則
            for rule in api_key_obj.rate_limits:
                cache_key = f"{api_key}:{rule.limit_type.value}"
                window_size = rule.get_window_size()

                # 獲取請求歷史
                request_times = self._rate_limit_cache[cache_key]

                # 清理過期的請求記錄
                cutoff_time = current_time - window_size
                while request_times and request_times[0] < cutoff_time:
                    request_times.popleft()

                # 檢查是否超過限制
                current_requests = len(request_times)

                rate_limit_info[rule.limit_type.value] = {
                    "limit": rule.max_requests,
                    "remaining": max(0, rule.max_requests - current_requests - 1),
                    "reset_time": int(current_time + window_size),
                    "window_size": window_size,
                }

                # 檢查突發限制
                if rule.burst_allowance > 0:
                    recent_requests = sum(
                        1 for t in request_times if current_time - t <= 1
                    )
                    if recent_requests >= rule.burst_allowance:
                        return False, {
                            "error": "rate_limit_exceeded",
                            "type": "burst_limit",
                            "rule": rule.limit_type.value,
                            "retry_after": 1,
                        }

                # 檢查常規限制
                if current_requests >= rule.max_requests:
                    await audit_manager.log_event(
                        SecurityEvent(
                            user_id=api_key_obj.user_id,
                            event_type="rate_limit_exceeded",
                            category=EventCategory.SECURITY_VIOLATION,
                            severity=EventSeverity.MEDIUM,
                            message=f"API 速率限制超過: {rule.limit_type.value}",
                            details={
                                "api_key_id": api_key_obj.id,
                                "rule": rule.limit_type.value,
                                "requests": current_requests,
                                "limit": rule.max_requests,
                            },
                            ip_address=client_ip,
                        )
                    )

                    return False, {
                        "error": "rate_limit_exceeded",
                        "rule": rule.limit_type.value,
                        "retry_after": (
                            window_size - (current_time - min(request_times))
                            if request_times
                            else 0
                        ),
                        "rate_limits": rate_limit_info,
                    }

                # 記錄新請求
                request_times.append(current_time)

            return True, {"rate_limits": rate_limit_info}

        except Exception as e:
            logger.error(f"❌ 速率限制檢查失敗: {e}")
            return False, {"error": "internal_error"}

    async def generate_jwt_token(
        self, user_id: int, permissions: List[str] = None, expires_in: int = None
    ) -> str:
        """
        生成 JWT 令牌

        Args:
            user_id: 用戶 ID
            permissions: 權限列表
            expires_in: 過期時間（秒）

        Returns:
            str: JWT 令牌
        """
        try:
            if not expires_in:
                expires_in = self.token_expiry

            payload = {
                "user_id": user_id,
                "permissions": permissions or [],
                "iat": datetime.utcnow(),
                "exp": datetime.utcnow() + timedelta(seconds=expires_in),
                "jti": secrets.token_hex(16),  # JWT ID for token revocation
            }

            token = jwt.encode(payload, self.jwt_secret, algorithm=self.jwt_algorithm)

            # 記錄令牌生成事件
            await audit_manager.log_event(
                SecurityEvent(
                    user_id=user_id,
                    event_type="jwt_token_generated",
                    category=EventCategory.AUTHENTICATION,
                    severity=EventSeverity.INFO,
                    message="JWT 令牌已生成",
                    details={
                        "expires_in": expires_in,
                        "permissions": permissions or [],
                    },
                )
            )

            return token

        except Exception as e:
            logger.error(f"❌ JWT 令牌生成失敗: {e}")
            return ""

    async def verify_jwt_token(self, token: str) -> Optional[Dict[str, Any]]:
        """
        驗證 JWT 令牌

        Args:
            token: JWT 令牌

        Returns:
            Optional[Dict[str, Any]]: 解碼的令牌內容
        """
        try:
            payload = jwt.decode(
                token, self.jwt_secret, algorithms=[self.jwt_algorithm]
            )
            return payload

        except jwt.ExpiredSignatureError:
            logger.warning("JWT 令牌已過期")
            return None
        except jwt.InvalidTokenError as e:
            logger.warning(f"JWT 令牌無效: {e}")
            return None
        except Exception as e:
            logger.error(f"❌ JWT 令牌驗證失敗: {e}")
            return None

    async def check_ip_access(self, ip_address: str) -> bool:
        """
        檢查 IP 存取權限

        Args:
            ip_address: IP 地址

        Returns:
            bool: 是否允許存取
        """
        try:
            ipaddress.ip_address(ip_address)

            # 檢查黑名單
            if ip_address in self._ip_blacklist:
                await audit_manager.log_event(
                    SecurityEvent(
                        event_type="ip_blocked",
                        category=EventCategory.SECURITY_VIOLATION,
                        severity=EventSeverity.HIGH,
                        message=f"被封鎖的 IP 嘗試存取: {ip_address}",
                        ip_address=ip_address,
                    )
                )
                return False

            # 檢查白名單 (如果設定了白名單)
            if self._ip_whitelist:
                if ip_address not in self._ip_whitelist:
                    await audit_manager.log_event(
                        SecurityEvent(
                            event_type="ip_not_whitelisted",
                            category=EventCategory.SECURITY_VIOLATION,
                            severity=EventSeverity.MEDIUM,
                            message=f"非白名單 IP 嘗試存取: {ip_address}",
                            ip_address=ip_address,
                        )
                    )
                    return False

            return True

        except ValueError:
            logger.warning(f"無效的 IP 地址: {ip_address}")
            return False
        except Exception as e:
            logger.error(f"❌ IP 存取檢查失敗: {e}")
            return False

    async def revoke_api_key(self, api_key_id: int, revoked_by: int) -> bool:
        """
        撤銷 API 密鑰

        Args:
            api_key_id: API 密鑰 ID
            revoked_by: 撤銷者 ID

        Returns:
            bool: 撤銷是否成功
        """
        try:
            async with db_pool.connection() as conn:
                async with conn.cursor() as cursor:
                    # 獲取 API 密鑰資訊
                    await cursor.execute(
                        """
                        SELECT key_value, name, user_id FROM api_keys WHERE id = %s
                    """,
                        (api_key_id,),
                    )
                    result = await cursor.fetchone()

                    if not result:
                        return False

                    key_value, name, user_id = result

                    # 撤銷 API 密鑰
                    await cursor.execute(
                        """
                        UPDATE api_keys
                        SET is_active = FALSE, revoked_at = %s, revoked_by = %s
                        WHERE id = %s
                    """,
                        (datetime.now(), revoked_by, api_key_id),
                    )
                    await conn.commit()

            # 從快取中移除
            if key_value in self._api_keys_cache:
                del self._api_keys_cache[key_value]

            # 記錄安全事件
            await audit_manager.log_event(
                SecurityEvent(
                    user_id=user_id,
                    event_type="api_key_revoked",
                    category=EventCategory.SYSTEM_CONFIG,
                    severity=EventSeverity.INFO,
                    message=f"API 密鑰已撤銷: {name}",
                    details={"api_key_id": api_key_id, "revoked_by": revoked_by},
                )
            )

            logger.info(f"🔑 API 密鑰已撤銷: {name} (ID: {api_key_id})")
            return True

        except Exception as e:
            logger.error(f"❌ API 密鑰撤銷失敗: {e}")
            return False

    def _generate_api_key(self) -> str:
        """生成安全的 API 密鑰"""
        # 生成 32 字節的隨機數據
        secrets.token_bytes(32)
        # 使用 base64 編碼並添加前綴
        key = f"pk_{''.join(secrets.choice('abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789') for _ in range(48))}"
        return key

    async def add_ip_to_whitelist(self, ip_address: str) -> bool:
        """添加 IP 到白名單"""
        try:
            ipaddress.ip_address(ip_address)  # 驗證 IP 格式
            self._ip_whitelist.add(ip_address)
            logger.info(f"✅ IP 已添加到白名單: {ip_address}")
            return True
        except ValueError:
            logger.error(f"❌ 無效的 IP 地址: {ip_address}")
            return False

    async def add_ip_to_blacklist(self, ip_address: str) -> bool:
        """添加 IP 到黑名單"""
        try:
            ipaddress.ip_address(ip_address)  # 驗證 IP 格式
            self._ip_blacklist.add(ip_address)
            logger.info(f"✅ IP 已添加到黑名單: {ip_address}")
            return True
        except ValueError:
            logger.error(f"❌ 無效的 IP 地址: {ip_address}")
            return False


# 全域單例
api_security = APISecurityManager()
