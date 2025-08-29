# bot/api/auth.py
"""
API 認證和授權系統
支援 API 金鑰認證、JWT 令牌和權限管理
"""

import hashlib
import os
import secrets
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

from fastapi import Depends, HTTPException, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import jwt
from pydantic import BaseModel

from shared.logger import logger


# 權限等級枚舉
class PermissionLevel(str, Enum):
    READ_ONLY = "read_only"  # 只讀權限
    WRITE = "write"  # 讀寫權限
    ADMIN = "admin"  # 管理員權限
    SUPER_ADMIN = "super_admin"  # 超級管理員權限


# API 金鑰模型
class APIKey(BaseModel):
    key_id: str
    name: str
    hashed_key: str
    permission_level: PermissionLevel
    guild_id: Optional[int] = None
    created_at: datetime
    last_used_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    is_active: bool = True
    usage_count: int = 0
    rate_limit_overrides: Optional[Dict[str, int]] = None


# 用戶信息模型
class APIUser(BaseModel):
    user_id: str
    username: str
    permission_level: PermissionLevel
    guild_id: Optional[int] = None
    api_key_id: str
    scopes: List[str] = []
    metadata: Dict[str, Any] = {}


class APIKeyManager:
    """API 金鑰管理器"""

    def __init__(self):
        self.api_keys: Dict[str, APIKey] = {}
        # 使用與 OAuth 系統相同的 JWT 密鑰
        self.jwt_secret = os.getenv("JWT_SECRET", secrets.token_urlsafe(32))

    async def initialize(self):
        """初始化 API 金鑰管理器"""
        try:
            # 這裡可以從資料庫載入現有的 API 金鑰
            logger.info("✅ API 金鑰管理器初始化完成")
        except Exception as e:
            logger.error(f"❌ API 金鑰管理器初始化失敗: {e}")
            raise

    def generate_api_key(self) -> str:
        """生成新的 API 金鑰"""
        return f"pk_{''.join(secrets.choice('abcdefghijklmnopqrstuvwxyz0123456789') for _ in range(32))}"

    def hash_key(self, key: str) -> str:
        """對 API 金鑰進行雜湊處理"""
        return hashlib.sha256(key.encode()).hexdigest()

    async def create_api_key(
        self,
        name: str,
        permission_level: PermissionLevel,
        guild_id: Optional[int] = None,
        expires_days: Optional[int] = None,
    ) -> tuple[str, APIKey]:
        """創建新的 API 金鑰"""
        try:
            raw_key = self.generate_api_key()
            key_id = secrets.token_urlsafe(16)
            hashed_key = self.hash_key(raw_key)

            expires_at = None
            if expires_days:
                expires_at = datetime.now(timezone.utc) + timedelta(days=expires_days)

            api_key = APIKey(
                key_id=key_id,
                name=name,
                hashed_key=hashed_key,
                permission_level=permission_level,
                guild_id=guild_id,
                created_at=datetime.now(timezone.utc),
                expires_at=expires_at,
            )

            self.api_keys[hashed_key] = api_key

            # 這裡應該將金鑰保存到資料庫
            # await self._save_api_key_to_db(api_key)

            logger.info(f"✅ 創建 API 金鑰: {name} (權限: {permission_level})")
            return raw_key, api_key

        except Exception as e:
            logger.error(f"❌ 創建 API 金鑰失敗: {e}")
            raise

    async def verify_api_key(self, raw_key: str) -> Optional[APIKey]:
        """驗證 API 金鑰"""
        try:
            if not raw_key:
                return None

            hashed_key = self.hash_key(raw_key)
            api_key = self.api_keys.get(hashed_key)

            if not api_key:
                return None

            # 檢查金鑰是否啟用
            if not api_key.is_active:
                return None

            # 檢查過期時間
            if api_key.expires_at and datetime.now(timezone.utc) > api_key.expires_at:
                api_key.is_active = False
                return None

            # 更新使用記錄
            api_key.last_used_at = datetime.now(timezone.utc)
            api_key.usage_count += 1

            return api_key

        except Exception as e:
            logger.error(f"❌ API 金鑰驗證失敗: {e}")
            return None

    async def revoke_api_key(self, key_id: str) -> bool:
        """撤銷 API 金鑰"""
        try:
            for api_key in self.api_keys.values():
                if api_key.key_id == key_id:
                    api_key.is_active = False
                    logger.info(f"✅ API 金鑰已撤銷: {api_key.name}")
                    return True
            return False
        except Exception as e:
            logger.error(f"❌ 撤銷 API 金鑰失敗: {e}")
            return False

    def generate_jwt_token(self, user_data: Dict[str, Any]) -> str:
        """生成 JWT 令牌"""
        payload = {
            **user_data,
            "exp": datetime.now(timezone.utc) + timedelta(hours=24),
            "iat": datetime.now(timezone.utc),
        }
        return jwt.encode(payload, self.jwt_secret, algorithm="HS256")

    def verify_jwt_token(self, token: str) -> Optional[Dict[str, Any]]:
        """驗證 JWT 令牌"""
        try:
            payload = jwt.decode(token, self.jwt_secret, algorithms=["HS256"])
            return payload
        except jwt.ExpiredSignatureError:
            logger.warning("JWT 令牌已過期")
            return None
        except jwt.InvalidTokenError as e:
            logger.warning(f"無效的 JWT 令牌: {e}")
            return None


# 全域 API 金鑰管理器實例
_api_key_manager: Optional[APIKeyManager] = None


def get_api_key_manager() -> APIKeyManager:
    """獲取 API 金鑰管理器實例"""
    global _api_key_manager
    if _api_key_manager is None:
        _api_key_manager = APIKeyManager()
    return _api_key_manager


# HTTP Bearer 安全方案
bearer_security = HTTPBearer()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Security(bearer_security),
) -> APIUser:
    """獲取當前認證用戶"""
    try:
        token = credentials.credentials
        manager = get_api_key_manager()

        # 嘗試驗證 API 金鑰
        api_key = await manager.verify_api_key(token)
        if api_key:
            return APIUser(
                user_id=api_key.key_id,
                username=api_key.name,
                permission_level=api_key.permission_level,
                guild_id=api_key.guild_id,
                api_key_id=api_key.key_id,
                scopes=["api_access"],
            )

        # 嘗試驗證 JWT 令牌
        jwt_payload = manager.verify_jwt_token(token)
        if jwt_payload:
            # 獲取權限等級，優先使用明確的 permission_level
            permission_level = jwt_payload.get("permission_level")

            # 如果沒有明確的 permission_level，則根據 permissions 推導
            if not permission_level:
                permissions = jwt_payload.get("permissions", {})
                if permissions.get("is_owner"):
                    permission_level = "super_admin"  # 伺服器擁有者獲得最高權限
                elif permissions.get("is_admin"):
                    permission_level = "admin"
                elif permissions.get("is_staff"):
                    permission_level = "write"
                else:
                    permission_level = "read_only"

            return APIUser(
                user_id=jwt_payload.get("user_id", "unknown"),
                username=jwt_payload.get("username", "JWT User"),
                permission_level=PermissionLevel(permission_level),
                guild_id=jwt_payload.get("guild_id"),
                api_key_id="jwt",
                scopes=jwt_payload.get("scopes", []),
            )

        raise HTTPException(status_code=401, detail="無效的認證憑據")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"用戶認證錯誤: {e}")
        raise HTTPException(status_code=500, detail="認證服務錯誤")


def require_permission(required_level: PermissionLevel):
    """權限檢查裝飾器"""

    def permission_checker(user: APIUser = Depends(get_current_user)) -> APIUser:
        permission_hierarchy = {
            PermissionLevel.READ_ONLY: 0,
            PermissionLevel.WRITE: 1,
            PermissionLevel.ADMIN: 2,
            PermissionLevel.SUPER_ADMIN: 3,
        }

        user_level = permission_hierarchy.get(user.permission_level, 0)
        required_level_value = permission_hierarchy.get(required_level, 999)

        if user_level < required_level_value:
            raise HTTPException(
                status_code=403, detail=f"需要 {required_level} 或更高權限"
            )

        return user

    return permission_checker


# 常用權限檢查器
require_read_permission = require_permission(PermissionLevel.READ_ONLY)
require_write_permission = require_permission(PermissionLevel.WRITE)
require_admin_permission = require_permission(PermissionLevel.ADMIN)
require_super_admin_permission = require_permission(PermissionLevel.SUPER_ADMIN)
