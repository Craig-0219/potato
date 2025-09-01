# bot/services/auth_manager.py
"""
API 認證管理器
提供 JWT 令牌生成、驗證和用戶認證功能
"""

import hashlib
import json
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

import aiomysql
import discord
from jose import jwt

from bot.db.pool import db_pool
from shared.logger import logger


@dataclass
class AuthUser:
    """認證用戶資料結構"""

    user_id: int
    discord_id: str
    username: str
    guild_id: int
    roles: List[str]
    permissions: List[str]
    is_admin: bool = False
    is_staff: bool = False
    created_at: datetime = None


class AuthenticationManager:
    """API 認證管理器"""

    def __init__(self, secret_key: str = None, token_expiry_hours: int = 24):
        self.secret_key = secret_key or secrets.token_urlsafe(64)
        self.token_expiry_hours = token_expiry_hours
        self.algorithm = "HS256"
        self.db = db_pool
        self.bot = None

    async def initialize(self, bot=None):
        """初始化認證管理器"""
        try:
            self.bot = bot
            await self._ensure_auth_tables()
            logger.info("✅ API 認證管理器初始化完成")
        except Exception as e:
            logger.error(f"❌ API 認證管理器初始化失敗: {e}")

    async def _ensure_auth_tables(self):
        """確保認證相關資料表存在"""
        try:
            async with self.db.connection() as conn:
                async with conn.cursor() as cursor:
                    # API 用戶表
                    await cursor.execute(
                        """
                        CREATE TABLE IF NOT EXISTS api_users (
                            id INT AUTO_INCREMENT PRIMARY KEY,
                            discord_id VARCHAR(20) NOT NULL UNIQUE,
                            username VARCHAR(100) NOT NULL,
                            password_hash VARCHAR(255),
                            guild_id BIGINT NOT NULL,
                            roles JSON,
                            permissions JSON,
                            is_admin BOOLEAN DEFAULT FALSE,
                            is_staff BOOLEAN DEFAULT FALSE,
                            last_login DATETIME,
                            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                            INDEX idx_discord_id (discord_id),
                            INDEX idx_guild_id (guild_id)
                        )
                    """
                    )

                    # API 金鑰表
                    await cursor.execute(
                        """
                        CREATE TABLE IF NOT EXISTS api_keys (
                            id INT AUTO_INCREMENT PRIMARY KEY,
                            key_id VARCHAR(32) NOT NULL UNIQUE,
                            key_hash VARCHAR(255) NOT NULL,
                            user_id INT,
                            name VARCHAR(100),
                            permissions JSON,
                            expires_at DATETIME,
                            last_used DATETIME,
                            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                            is_active BOOLEAN DEFAULT TRUE,
                            FOREIGN KEY (user_id) REFERENCES api_users(id) ON DELETE CASCADE,
                            INDEX idx_key_id (key_id),
                            INDEX idx_user_id (user_id)
                        )
                    """
                    )

                    # 登入會話表
                    await cursor.execute(
                        """
                        CREATE TABLE IF NOT EXISTS login_sessions (
                            id INT AUTO_INCREMENT PRIMARY KEY,
                            session_token VARCHAR(255) NOT NULL UNIQUE,
                            user_id INT NOT NULL,
                            ip_address VARCHAR(45),
                            user_agent TEXT,
                            expires_at DATETIME NOT NULL,
                            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                            last_activity DATETIME DEFAULT CURRENT_TIMESTAMP,
                            is_active BOOLEAN DEFAULT TRUE,
                            FOREIGN KEY (user_id) REFERENCES api_users(id) ON DELETE CASCADE,
                            INDEX idx_token (session_token),
                            INDEX idx_user_id (user_id),
                            INDEX idx_expires (expires_at)
                        )
                    """
                    )

                    await conn.commit()
                    logger.info("認證資料表檢查完成")

        except Exception as e:
            logger.error(f"建立認證資料表失敗: {e}")

    # ===== Discord 用戶同步 =====

    async def sync_discord_user(
        self, discord_user: discord.Member, password: str = None
    ) -> Tuple[bool, str, Optional[AuthUser]]:
        """同步 Discord 用戶到 API 認證系統"""
        try:
            # 檢查用戶角色和權限
            roles = [
                role.name
                for role in discord_user.roles
                if role.name != "@everyone"
            ]

            # 判斷是否為管理員或客服（支援模糊匹配）
            admin_keywords = ["管理員", "admin", "owner", "服主", "commander"]
            staff_keywords = [
                "客服",
                "staff",
                "support",
                "moderator",
                "mod",
            ] + admin_keywords

            is_admin = any(
                any(
                    keyword.lower() in role.lower()
                    for keyword in admin_keywords
                )
                for role in roles
            )
            is_staff = any(
                any(
                    keyword.lower() in role.lower()
                    for keyword in staff_keywords
                )
                for role in roles
            )

            # 基於角色設定權限
            permissions = []
            if is_admin:
                permissions = ["all"]
            elif is_staff:
                permissions = [
                    "tickets.read",
                    "tickets.write",
                    "tickets.assign",
                    "tickets.close",
                    "statistics.read",
                    "users.read",
                ]
            else:
                permissions = ["tickets.read_own"]

            # 插入或更新用戶
            async with self.db.connection() as conn:
                async with conn.cursor(aiomysql.DictCursor) as cursor:
                    # 檢查用戶是否已存在
                    await cursor.execute(
                        "SELECT * FROM api_users WHERE discord_id = %s AND guild_id = %s",
                        (str(discord_user.id), discord_user.guild.id),
                    )
                    existing_user = await cursor.fetchone()

                    if existing_user:
                        # 更新現有用戶
                        await cursor.execute(
                            """
                            UPDATE api_users SET
                                username = %s,
                                roles = %s,
                                permissions = %s,
                                is_admin = %s,
                                is_staff = %s,
                                updated_at = NOW()
                            WHERE discord_id = %s AND guild_id = %s
                        """,
                            (
                                discord_user.display_name,
                                json.dumps(roles, ensure_ascii=False),
                                json.dumps(permissions, ensure_ascii=False),
                                is_admin,
                                is_staff,
                                str(discord_user.id),
                                discord_user.guild.id,
                            ),
                        )
                        user_id = existing_user["id"]
                    else:
                        # 創建新用戶
                        password_hash = (
                            self._hash_password(password) if password else None
                        )
                        # 根據權限設定permission_level
                        if is_admin:
                            permission_level = "admin"
                        elif is_staff:
                            permission_level = "write"
                        else:
                            permission_level = "read_only"

                        await cursor.execute(
                            """
                            INSERT INTO api_users
                            (discord_id, username, discord_username, password_hash, guild_id, permission_level)
                            VALUES (%s, %s, %s, %s, %s, %s)
                        """,
                            (
                                str(discord_user.id),
                                discord_user.display_name,
                                discord_user.name,
                                password_hash,
                                discord_user.guild.id,
                                permission_level,
                            ),
                        )
                        user_id = cursor.lastrowid

                    await conn.commit()

                    # 返回用戶資料
                    auth_user = AuthUser(
                        user_id=user_id,
                        discord_id=str(discord_user.id),
                        username=discord_user.display_name,
                        guild_id=discord_user.guild.id,
                        roles=roles,
                        permissions=permissions,
                        is_admin=is_admin,
                        is_staff=is_staff,
                    )

                    logger.info(
                        f"Discord 用戶同步成功: {discord_user.display_name}"
                    )
                    return True, "用戶同步成功", auth_user

        except Exception as e:
            logger.error(f"同步 Discord 用戶失敗: {e}")
            return False, f"同步失敗: {str(e)}", None

    # ===== 密碼認證 =====

    def _hash_password(self, password: str) -> str:
        """密碼雜湊"""
        salt = secrets.token_hex(32)
        pwd_hash = hashlib.pbkdf2_hmac(
            "sha256", password.encode("utf-8"), salt.encode("utf-8"), 100000
        )
        return f"{salt}:{pwd_hash.hex()}"

    def _verify_password(self, password: str, password_hash: str) -> bool:
        """驗證密碼"""
        try:
            salt, stored_hash = password_hash.split(":")
            pwd_hash = hashlib.pbkdf2_hmac(
                "sha256",
                password.encode("utf-8"),
                salt.encode("utf-8"),
                100000,
            )
            return pwd_hash.hex() == stored_hash
        except:
            return False

    async def authenticate_user(
        self, discord_id: str, password: str, guild_id: int
    ) -> Tuple[bool, str, Optional[AuthUser]]:
        """用戶密碼認證"""
        try:
            async with self.db.connection() as conn:
                async with conn.cursor(aiomysql.DictCursor) as cursor:
                    await cursor.execute(
                        """
                        SELECT * FROM api_users
                        WHERE discord_id = %s AND guild_id = %s
                    """,
                        (discord_id, guild_id),
                    )
                    user_data = await cursor.fetchone()

                    if not user_data:
                        return False, "用戶不存在", None

                    if not user_data["password_hash"]:
                        return False, "用戶尚未設定密碼", None

                    if not self._verify_password(
                        password, user_data["password_hash"]
                    ):
                        return False, "密碼錯誤", None

                    # 更新最後登入時間
                    await cursor.execute(
                        "UPDATE api_users SET last_login = NOW() WHERE id = %s",
                        (user_data["id"],),
                    )
                    await conn.commit()

                    # 創建 AuthUser 物件
                    auth_user = AuthUser(
                        user_id=user_data["id"],
                        discord_id=user_data["discord_id"],
                        username=user_data["username"],
                        guild_id=user_data["guild_id"],
                        roles=(
                            json.loads(user_data["roles"])
                            if user_data["roles"]
                            else []
                        ),
                        permissions=(
                            json.loads(user_data["permissions"])
                            if user_data["permissions"]
                            else []
                        ),
                        is_admin=user_data["is_admin"],
                        is_staff=user_data["is_staff"],
                        created_at=user_data["created_at"],
                    )

                    return True, "認證成功", auth_user

        except Exception as e:
            logger.error(f"用戶認證失敗: {e}")
            return False, f"認證錯誤: {str(e)}", None

    # ===== JWT 令牌管理 =====

    def generate_jwt_token(self, auth_user: AuthUser) -> str:
        """生成 JWT 令牌"""
        try:
            payload = {
                "user_id": auth_user.user_id,
                "discord_id": auth_user.discord_id,
                "username": auth_user.username,
                "guild_id": auth_user.guild_id,
                "roles": auth_user.roles,
                "permissions": auth_user.permissions,
                "is_admin": auth_user.is_admin,
                "is_staff": auth_user.is_staff,
                "exp": datetime.now(timezone.utc)
                + timedelta(hours=self.token_expiry_hours),
                "iat": datetime.now(timezone.utc),
            }

            token = jwt.encode(
                payload, self.secret_key, algorithm=self.algorithm
            )
            logger.info(f"JWT 令牌已生成 for user: {auth_user.username}")
            return token

        except Exception as e:
            logger.error(f"生成 JWT 令牌失敗: {e}")
            return None

    def verify_jwt_token(
        self, token: str
    ) -> Tuple[bool, Optional[Dict[str, Any]], str]:
        """驗證 JWT 令牌"""
        try:
            payload = jwt.decode(
                token, self.secret_key, algorithms=[self.algorithm]
            )
            return True, payload, "令牌有效"

        except jwt.ExpiredSignatureError:
            return False, None, "令牌已過期"
        except jwt.InvalidTokenError:
            return False, None, "令牌無效"
        except Exception as e:
            logger.error(f"驗證 JWT 令牌失敗: {e}")
            return False, None, f"驗證錯誤: {str(e)}"

    # ===== API 金鑰管理 =====

    async def create_api_key(
        self,
        user_id: int,
        name: str,
        permissions: List[str] = None,
        expires_days: int = 30,
    ) -> Tuple[bool, str, Optional[str]]:
        """創建 API 金鑰"""
        try:
            # 生成金鑰
            key_id = secrets.token_urlsafe(16)
            key_secret = secrets.token_urlsafe(32)
            key_hash = hashlib.sha256(key_secret.encode()).hexdigest()

            expires_at = (
                datetime.now(timezone.utc) + timedelta(days=expires_days)
                if expires_days > 0
                else None
            )

            async with self.db.connection() as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute(
                        """
                        INSERT INTO api_keys
                        (key_id, key_secret, key_hash, user_id, name, permissions, expires_at)
                        VALUES (%s, %s, %s, %s, %s, %s, %s)
                    """,
                        (
                            key_id,
                            key_secret,
                            key_hash,
                            user_id,
                            name,
                            json.dumps(permissions or [], ensure_ascii=False),
                            expires_at,
                        ),
                    )
                    await conn.commit()

                    # 返回完整的 API 金鑰（只顯示一次）
                    full_key = f"{key_id}.{key_secret}"

                    logger.info(f"API 金鑰已創建: {name} (user_id: {user_id})")
                    return True, "API 金鑰創建成功", full_key

        except Exception as e:
            logger.error(f"創建 API 金鑰失敗: {e}")
            return False, f"創建失敗: {str(e)}", None

    async def verify_api_key(
        self, api_key: str
    ) -> Tuple[bool, Optional[AuthUser], str]:
        """驗證 API 金鑰"""
        try:
            if "." not in api_key:
                return False, None, "API 金鑰格式錯誤"

            key_id, key_secret = api_key.split(".", 1)
            key_hash = hashlib.sha256(key_secret.encode()).hexdigest()

            async with self.db.connection() as conn:
                async with conn.cursor(aiomysql.DictCursor) as cursor:
                    # 驗證金鑰並獲取用戶資訊
                    await cursor.execute(
                        """
                        SELECT ak.id, ak.key_id, ak.user_id, ak.permissions as key_permissions,
                               au.discord_id, au.username, au.guild_id,
                               au.roles, au.permissions as user_permissions, au.is_admin, au.is_staff
                        FROM api_keys ak
                        JOIN api_users au ON ak.user_id = au.id
                        WHERE ak.key_id = %s AND ak.key_hash = %s
                        AND ak.is_active = TRUE
                        AND (ak.expires_at IS NULL OR ak.expires_at > NOW())
                    """,
                        (key_id, key_hash),
                    )

                    result = await cursor.fetchone()
                    if not result:
                        return False, None, "API 金鑰無效或已過期"

                    # 更新最後使用時間
                    await cursor.execute(
                        "UPDATE api_keys SET last_used = NOW() WHERE id = %s",
                        (result["id"],),
                    )
                    await conn.commit()

                    # 合併用戶權限和金鑰權限
                    user_permissions = (
                        json.loads(result["user_permissions"])
                        if result["user_permissions"]
                        else []
                    )
                    key_permissions = (
                        json.loads(result["key_permissions"])
                        if result["key_permissions"]
                        else []
                    )

                    # 如果金鑰有特定權限，使用金鑰權限；否則使用用戶權限
                    final_permissions = (
                        key_permissions
                        if key_permissions
                        else user_permissions
                    )

                    auth_user = AuthUser(
                        user_id=result["user_id"],
                        discord_id=result["discord_id"],
                        username=result["username"],
                        guild_id=result["guild_id"],
                        roles=(
                            json.loads(result["roles"])
                            if result["roles"]
                            else []
                        ),
                        permissions=final_permissions,
                        is_admin=result["is_admin"],
                        is_staff=result["is_staff"],
                    )

                    return True, auth_user, "API 金鑰有效"

        except Exception as e:
            logger.error(f"驗證 API 金鑰失敗: {e}")
            return False, None, f"驗證錯誤: {str(e)}"

    # ===== 會話管理 =====

    async def create_login_session(
        self,
        user_id: int,
        ip_address: str = None,
        user_agent: str = None,
        expires_hours: int = 24,
    ) -> Optional[str]:
        """創建登入會話"""
        try:
            session_token = secrets.token_urlsafe(64)
            expires_at = datetime.now(timezone.utc) + timedelta(
                hours=expires_hours
            )

            async with self.db.connection() as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute(
                        """
                        INSERT INTO login_sessions
                        (session_token, user_id, ip_address, user_agent, expires_at)
                        VALUES (%s, %s, %s, %s, %s)
                    """,
                        (
                            session_token,
                            user_id,
                            ip_address,
                            user_agent,
                            expires_at,
                        ),
                    )
                    await conn.commit()

                    logger.info(f"登入會話已創建 for user_id: {user_id}")
                    return session_token

        except Exception as e:
            logger.error(f"創建登入會話失敗: {e}")
            return None

    async def verify_session(
        self, session_token: str
    ) -> Tuple[bool, Optional[AuthUser], str]:
        """驗證登入會話"""
        try:
            async with self.db.connection() as conn:
                async with conn.cursor(aiomysql.DictCursor) as cursor:
                    await cursor.execute(
                        """
                        SELECT ls.*, au.discord_id, au.username, au.guild_id,
                               au.roles, au.permissions, au.is_admin, au.is_staff
                        FROM login_sessions ls
                        JOIN api_users au ON ls.user_id = au.id
                        WHERE ls.session_token = %s
                        AND ls.is_active = TRUE
                        AND ls.expires_at > NOW()
                    """,
                        (session_token,),
                    )

                    result = await cursor.fetchone()
                    if not result:
                        return False, None, "會話無效或已過期"

                    # 更新最後活動時間
                    await cursor.execute(
                        "UPDATE login_sessions SET last_activity = NOW() WHERE id = %s",
                        (result["id"],),
                    )
                    await conn.commit()

                    auth_user = AuthUser(
                        user_id=result["user_id"],
                        discord_id=result["discord_id"],
                        username=result["username"],
                        guild_id=result["guild_id"],
                        roles=(
                            json.loads(result["roles"])
                            if result["roles"]
                            else []
                        ),
                        permissions=(
                            json.loads(result["permissions"])
                            if result["permissions"]
                            else []
                        ),
                        is_admin=result["is_admin"],
                        is_staff=result["is_staff"],
                    )

                    return True, auth_user, "會話有效"

        except Exception as e:
            logger.error(f"驗證會話失敗: {e}")
            return False, None, f"驗證錯誤: {str(e)}"

    # ===== 權限檢查 =====

    def check_permission(
        self, auth_user: AuthUser, required_permission: str
    ) -> bool:
        """檢查用戶權限"""
        if auth_user.is_admin or "all" in auth_user.permissions:
            return True

        if required_permission in auth_user.permissions:
            return True

        # 檢查通配符權限
        for permission in auth_user.permissions:
            if permission.endswith("*"):
                prefix = permission[:-1]
                if required_permission.startswith(prefix):
                    return True

        return False

    async def get_user_api_keys(self, user_id: int) -> List[Dict[str, Any]]:
        """獲取用戶的 API 金鑰列表"""
        try:
            async with self.db.connection() as conn:
                async with conn.cursor(aiomysql.DictCursor) as cursor:
                    await cursor.execute(
                        """
                        SELECT id, key_id, name, permissions, permission_level, expires_at,
                               last_used, created_at, is_active
                        FROM api_keys
                        WHERE user_id = %s
                        ORDER BY created_at DESC
                    """,
                        (user_id,),
                    )

                    results = await cursor.fetchall()

                    # 格式化結果
                    api_keys = []
                    for row in results:
                        api_keys.append(
                            {
                                "id": row["id"],
                                "key_id": row["key_id"],
                                "name": row["name"],
                                "permissions": (
                                    json.loads(row["permissions"])
                                    if row["permissions"]
                                    else []
                                ),
                                "expires_at": (
                                    row["expires_at"].isoformat()
                                    if row["expires_at"]
                                    else None
                                ),
                                "last_used": (
                                    row["last_used"].isoformat()
                                    if row["last_used"]
                                    else None
                                ),
                                "created_at": row["created_at"].isoformat(),
                                "is_active": row["is_active"],
                            }
                        )

                    return api_keys

        except Exception as e:
            logger.error(f"獲取用戶 API 金鑰失敗: {e}")
            return []

    async def revoke_api_key(self, user_id: int, key_id: str) -> bool:
        """撤銷 API 金鑰"""
        try:
            async with self.db.connection() as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute(
                        """
                        UPDATE api_keys
                        SET is_active = FALSE
                        WHERE user_id = %s AND key_id = %s
                    """,
                        (user_id, key_id),
                    )

                    if cursor.rowcount > 0:
                        await conn.commit()
                        logger.info(f"API 金鑰已撤銷: {key_id}")
                        return True

                    return False

        except Exception as e:
            logger.error(f"撤銷 API 金鑰失敗: {e}")
            return False


# 全局認證管理器實例
auth_manager = AuthenticationManager()
