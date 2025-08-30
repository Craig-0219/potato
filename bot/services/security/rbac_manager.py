# bot/services/security/rbac_manager.py - v1.0.0
# 🔒 基於角色的存取控制 (RBAC) 管理系統
# Role-Based Access Control Framework

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Set

from bot.db.pool import db_pool

logger = logging.getLogger(__name__)


class Permission(Enum):
    """系統權限枚舉"""

    # 系統管理
    SYSTEM_ADMIN = "system:admin"
    SYSTEM_VIEW = "system:view"
    SYSTEM_CONFIG = "system:config"

    # 用戶管理
    USER_MANAGE = "user:manage"
    USER_VIEW = "user:view"
    USER_BAN = "user:ban"
    USER_MUTE = "user:mute"

    # 票券系統
    TICKET_ADMIN = "ticket:admin"
    TICKET_MANAGE = "ticket:manage"
    TICKET_VIEW = "ticket:view"
    TICKET_CLOSE = "ticket:close"

    # 投票系統
    VOTE_ADMIN = "vote:admin"
    VOTE_CREATE = "vote:create"
    VOTE_MANAGE = "vote:manage"
    VOTE_PARTICIPATE = "vote:participate"

    # 經濟系統
    ECONOMY_ADMIN = "economy:admin"
    ECONOMY_MANAGE = "economy:manage"
    ECONOMY_VIEW = "economy:view"
    ECONOMY_TRANSACTION = "economy:transaction"

    # AI 助手
    AI_ADMIN = "ai:admin"
    AI_USE = "ai:use"
    AI_CONFIG = "ai:config"

    # 內容分析
    CONTENT_ADMIN = "content:admin"
    CONTENT_ANALYZE = "content:analyze"
    CONTENT_MODERATE = "content:moderate"

    # 工作流程
    WORKFLOW_ADMIN = "workflow:admin"
    WORKFLOW_MANAGE = "workflow:manage"
    WORKFLOW_EXECUTE = "workflow:execute"

    # API 存取
    API_ADMIN = "api:admin"
    API_READ = "api:read"
    API_WRITE = "api:write"
    API_DELETE = "api:delete"


class RoleLevel(Enum):
    """角色層級"""

    SUPER_ADMIN = 100  # 超級管理員
    GUILD_ADMIN = 80  # 伺服器管理員
    MODERATOR = 60  # 版主
    STAFF = 40  # 工作人員
    VIP = 20  # VIP 用戶
    MEMBER = 10  # 普通成員
    GUEST = 0  # 訪客


@dataclass
class Role:
    """角色定義"""

    id: int
    name: str
    description: str
    level: RoleLevel
    permissions: Set[Permission] = field(default_factory=set)
    is_system: bool = False
    is_active: bool = True
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)

    def has_permission(self, permission: Permission) -> bool:
        """檢查角色是否有特定權限"""
        return permission in self.permissions

    def add_permission(self, permission: Permission):
        """添加權限"""
        self.permissions.add(permission)
        self.updated_at = datetime.now()

    def remove_permission(self, permission: Permission):
        """移除權限"""
        self.permissions.discard(permission)
        self.updated_at = datetime.now()


@dataclass
class UserRoleAssignment:
    """用戶角色分配"""

    user_id: int
    guild_id: int
    role_id: int
    assigned_by: int
    assigned_at: datetime = field(default_factory=datetime.now)
    expires_at: Optional[datetime] = None
    is_active: bool = True


class RBACManager:
    """
    基於角色的存取控制管理器

    功能：
    - 角色定義與管理
    - 權限分配與繼承
    - 用戶角色分配
    - 動態權限驗證
    - 權限審計日誌
    """

    def __init__(self):
        self._roles_cache: Dict[int, Role] = {}
        self._user_roles_cache: Dict[str, List[int]] = {}
        self._permissions_cache: Dict[int, Set[Permission]] = {}
        self.cache_ttl = 300  # 快取 5 分鐘
        self._last_cache_update = {}

        logger.info("🔒 RBAC 管理器初始化完成")

    async def initialize_default_roles(self):
        """初始化預設角色"""
        try:
            default_roles = [
                {
                    "name": "Super Admin",
                    "description": "系統超級管理員，擁有所有權限",
                    "level": RoleLevel.SUPER_ADMIN,
                    "permissions": list(Permission),
                    "is_system": True,
                },
                {
                    "name": "Guild Admin",
                    "description": "伺服器管理員",
                    "level": RoleLevel.GUILD_ADMIN,
                    "permissions": [
                        Permission.SYSTEM_VIEW,
                        Permission.USER_MANAGE,
                        Permission.USER_VIEW,
                        Permission.USER_BAN,
                        Permission.USER_MUTE,
                        Permission.TICKET_ADMIN,
                        Permission.VOTE_ADMIN,
                        Permission.ECONOMY_ADMIN,
                        Permission.AI_CONFIG,
                        Permission.CONTENT_ADMIN,
                        Permission.WORKFLOW_ADMIN,
                        Permission.API_READ,
                        Permission.API_WRITE,
                    ],
                    "is_system": True,
                },
                {
                    "name": "Moderator",
                    "description": "版主，負責內容審核",
                    "level": RoleLevel.MODERATOR,
                    "permissions": [
                        Permission.USER_VIEW,
                        Permission.USER_MUTE,
                        Permission.TICKET_MANAGE,
                        Permission.VOTE_MANAGE,
                        Permission.CONTENT_MODERATE,
                        Permission.AI_USE,
                        Permission.API_READ,
                    ],
                    "is_system": True,
                },
                {
                    "name": "Staff",
                    "description": "工作人員",
                    "level": RoleLevel.STAFF,
                    "permissions": [
                        Permission.USER_VIEW,
                        Permission.TICKET_VIEW,
                        Permission.TICKET_CLOSE,
                        Permission.VOTE_CREATE,
                        Permission.VOTE_PARTICIPATE,
                        Permission.ECONOMY_VIEW,
                        Permission.AI_USE,
                        Permission.CONTENT_ANALYZE,
                        Permission.WORKFLOW_EXECUTE,
                        Permission.API_READ,
                    ],
                    "is_system": True,
                },
                {
                    "name": "VIP Member",
                    "description": "VIP 會員",
                    "level": RoleLevel.VIP,
                    "permissions": [
                        Permission.VOTE_CREATE,
                        Permission.VOTE_PARTICIPATE,
                        Permission.ECONOMY_TRANSACTION,
                        Permission.AI_USE,
                        Permission.CONTENT_ANALYZE,
                        Permission.WORKFLOW_EXECUTE,
                    ],
                    "is_system": True,
                },
                {
                    "name": "Member",
                    "description": "普通成員",
                    "level": RoleLevel.MEMBER,
                    "permissions": [
                        Permission.VOTE_PARTICIPATE,
                        Permission.ECONOMY_TRANSACTION,
                        Permission.AI_USE,
                    ],
                    "is_system": True,
                },
            ]

            for role_data in default_roles:
                await self.create_role(
                    name=role_data["name"],
                    description=role_data["description"],
                    level=role_data["level"],
                    permissions=role_data["permissions"],
                    is_system=role_data["is_system"],
                )

            logger.info(f"✅ 初始化了 {len(default_roles)} 個預設角色")

        except Exception as e:
            logger.error(f"❌ 預設角色初始化失敗: {e}")

    async def create_role(
        self,
        name: str,
        description: str,
        level: RoleLevel,
        permissions: List[Permission] = None,
        is_system: bool = False,
    ) -> Optional[Role]:
        """
        創建角色

        Args:
            name: 角色名稱
            description: 角色描述
            level: 角色層級
            permissions: 權限列表
            is_system: 是否為系統角色

        Returns:
            Optional[Role]: 創建的角色對象
        """
        try:
            # 檢查角色是否已存在
            async with db_pool.connection() as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute(
                        """
                        SELECT id FROM rbac_roles WHERE name = %s
                    """,
                        (name,),
                    )
                    if await cursor.fetchone():
                        logger.warning(f"⚠️ 角色已存在: {name}")
                        return None

                    # 創建角色
                    await cursor.execute(
                        """
                        INSERT INTO rbac_roles (name, description, level, is_system, is_active, created_at)
                        VALUES (%s, %s, %s, %s, %s, %s)
                    """,
                        (
                            name,
                            description,
                            level.value,
                            is_system,
                            True,
                            datetime.now(),
                        ),
                    )

                    role_id = cursor.lastrowid

                    # 添加權限
                    if permissions:
                        for permission in permissions:
                            await cursor.execute(
                                """
                                INSERT INTO rbac_role_permissions (role_id, permission, created_at)
                                VALUES (%s, %s, %s)
                            """,
                                (role_id, permission.value, datetime.now()),
                            )

                    await conn.commit()

            # 創建角色對象
            role = Role(
                id=role_id,
                name=name,
                description=description,
                level=level,
                permissions=set(permissions) if permissions else set(),
                is_system=is_system,
            )

            # 更新快取
            self._roles_cache[role_id] = role

            logger.info(f"✅ 角色創建成功: {name} (ID: {role_id})")
            return role

        except Exception as e:
            logger.error(f"❌ 角色創建失敗: {e}")
            return None

    async def assign_role(
        self,
        user_id: int,
        guild_id: int,
        role_id: int,
        assigned_by: int,
        expires_at: Optional[datetime] = None,
    ) -> bool:
        """
        為用戶分配角色

        Args:
            user_id: Discord 用戶 ID
            guild_id: 伺服器 ID
            role_id: 角色 ID
            assigned_by: 分配者 ID
            expires_at: 過期時間

        Returns:
            bool: 分配是否成功
        """
        try:
            async with db_pool.connection() as conn:
                async with conn.cursor() as cursor:
                    # 檢查是否已分配
                    await cursor.execute(
                        """
                        SELECT id FROM rbac_user_roles
                        WHERE user_id = %s AND guild_id = %s AND role_id = %s AND is_active = TRUE
                    """,
                        (user_id, guild_id, role_id),
                    )

                    if await cursor.fetchone():
                        logger.warning(f"⚠️ 用戶已有此角色: user_id={user_id}, role_id={role_id}")
                        return False

                    # 分配角色
                    await cursor.execute(
                        """
                        INSERT INTO rbac_user_roles
                        (user_id, guild_id, role_id, assigned_by, assigned_at, expires_at, is_active)
                        VALUES (%s, %s, %s, %s, %s, %s, %s)
                    """,
                        (
                            user_id,
                            guild_id,
                            role_id,
                            assigned_by,
                            datetime.now(),
                            expires_at,
                            True,
                        ),
                    )

                    await conn.commit()

            # 清除快取
            cache_key = f"{user_id}_{guild_id}"
            if cache_key in self._user_roles_cache:
                del self._user_roles_cache[cache_key]

            # 記錄操作日誌
            await self._log_rbac_event(
                user_id,
                guild_id,
                "role_assigned",
                {
                    "role_id": role_id,
                    "assigned_by": assigned_by,
                    "expires_at": expires_at.isoformat() if expires_at else None,
                },
            )

            logger.info(f"✅ 角色分配成功: user_id={user_id}, role_id={role_id}")
            return True

        except Exception as e:
            logger.error(f"❌ 角色分配失敗: {e}")
            return False

    async def revoke_role(self, user_id: int, guild_id: int, role_id: int, revoked_by: int) -> bool:
        """
        撤銷用戶角色

        Args:
            user_id: Discord 用戶 ID
            guild_id: 伺服器 ID
            role_id: 角色 ID
            revoked_by: 撤銷者 ID

        Returns:
            bool: 撤銷是否成功
        """
        try:
            async with db_pool.connection() as conn:
                async with conn.cursor() as cursor:
                    # 撤銷角色 (軟刪除)
                    await cursor.execute(
                        """
                        UPDATE rbac_user_roles
                        SET is_active = FALSE, revoked_by = %s, revoked_at = %s
                        WHERE user_id = %s AND guild_id = %s AND role_id = %s AND is_active = TRUE
                    """,
                        (revoked_by, datetime.now(), user_id, guild_id, role_id),
                    )

                    affected_rows = cursor.rowcount
                    await conn.commit()

            if affected_rows == 0:
                logger.warning(f"⚠️ 未找到要撤銷的角色: user_id={user_id}, role_id={role_id}")
                return False

            # 清除快取
            cache_key = f"{user_id}_{guild_id}"
            if cache_key in self._user_roles_cache:
                del self._user_roles_cache[cache_key]

            # 記錄操作日誌
            await self._log_rbac_event(
                user_id,
                guild_id,
                "role_revoked",
                {"role_id": role_id, "revoked_by": revoked_by},
            )

            logger.info(f"✅ 角色撤銷成功: user_id={user_id}, role_id={role_id}")
            return True

        except Exception as e:
            logger.error(f"❌ 角色撤銷失敗: {e}")
            return False

    async def check_permission(self, user_id: int, guild_id: int, permission: Permission) -> bool:
        """
        檢查用戶是否有特定權限

        Args:
            user_id: Discord 用戶 ID
            guild_id: 伺服器 ID
            permission: 要檢查的權限

        Returns:
            bool: 是否有權限
        """
        try:
            user_permissions = await self.get_user_permissions(user_id, guild_id)
            return permission in user_permissions

        except Exception as e:
            logger.error(f"❌ 權限檢查失敗: {e}")
            return False

    async def get_user_permissions(self, user_id: int, guild_id: int) -> Set[Permission]:
        """
        獲取用戶所有權限

        Args:
            user_id: Discord 用戶 ID
            guild_id: 伺服器 ID

        Returns:
            Set[Permission]: 用戶權限集合
        """
        try:
            cache_key = f"{user_id}_{guild_id}"

            # 檢查快取
            if cache_key in self._permissions_cache:
                if self._is_cache_valid(cache_key):
                    return self._permissions_cache[cache_key]

            # 獲取用戶角色
            user_roles = await self.get_user_roles(user_id, guild_id)

            # 收集所有權限
            all_permissions = set()

            for role_id in user_roles:
                role = await self.get_role(role_id)
                if role and role.is_active:
                    all_permissions.update(role.permissions)

            # 更新快取
            self._permissions_cache[cache_key] = all_permissions
            self._last_cache_update[cache_key] = datetime.now()

            return all_permissions

        except Exception as e:
            logger.error(f"❌ 獲取用戶權限失敗: {e}")
            return set()

    async def get_user_roles(self, user_id: int, guild_id: int) -> List[int]:
        """
        獲取用戶角色 ID 列表

        Args:
            user_id: Discord 用戶 ID
            guild_id: 伺服器 ID

        Returns:
            List[int]: 角色 ID 列表
        """
        try:
            cache_key = f"{user_id}_{guild_id}"

            # 檢查快取
            if cache_key in self._user_roles_cache:
                if self._is_cache_valid(cache_key):
                    return self._user_roles_cache[cache_key]

            async with db_pool.connection() as conn:
                async with conn.cursor() as cursor:
                    # 獲取有效的角色分配
                    await cursor.execute(
                        """
                        SELECT role_id FROM rbac_user_roles
                        WHERE user_id = %s AND guild_id = %s AND is_active = TRUE
                        AND (expires_at IS NULL OR expires_at > %s)
                    """,
                        (user_id, guild_id, datetime.now()),
                    )

                    role_ids = [row[0] for row in await cursor.fetchall()]

            # 更新快取
            self._user_roles_cache[cache_key] = role_ids
            self._last_cache_update[cache_key] = datetime.now()

            return role_ids

        except Exception as e:
            logger.error(f"❌ 獲取用戶角色失敗: {e}")
            return []

    async def get_role(self, role_id: int) -> Optional[Role]:
        """
        獲取角色對象

        Args:
            role_id: 角色 ID

        Returns:
            Optional[Role]: 角色對象
        """
        try:
            # 檢查快取
            if role_id in self._roles_cache:
                return self._roles_cache[role_id]

            async with db_pool.connection() as conn:
                async with conn.cursor() as cursor:
                    # 獲取角色基本資訊
                    await cursor.execute(
                        """
                        SELECT id, name, description, level, is_system, is_active, created_at, updated_at
                        FROM rbac_roles WHERE id = %s
                    """,
                        (role_id,),
                    )

                    role_data = await cursor.fetchone()
                    if not role_data:
                        return None

                    # 獲取角色權限
                    await cursor.execute(
                        """
                        SELECT permission FROM rbac_role_permissions WHERE role_id = %s
                    """,
                        (role_id,),
                    )

                    permissions = set()
                    for (perm,) in await cursor.fetchall():
                        try:
                            permissions.add(Permission(perm))
                        except ValueError:
                            logger.warning(f"⚠️ 未知權限: {perm}")

            # 創建角色對象
            role = Role(
                id=role_data[0],
                name=role_data[1],
                description=role_data[2],
                level=RoleLevel(role_data[3]),
                permissions=permissions,
                is_system=role_data[4],
                is_active=role_data[5],
                created_at=role_data[6],
                updated_at=role_data[7] or role_data[6],
            )

            # 更新快取
            self._roles_cache[role_id] = role

            return role

        except Exception as e:
            logger.error(f"❌ 獲取角色失敗: {e}")
            return None

    async def list_roles(self, include_inactive: bool = False) -> List[Role]:
        """
        列出所有角色

        Args:
            include_inactive: 是否包含非活躍角色

        Returns:
            List[Role]: 角色列表
        """
        try:
            async with db_pool.connection() as conn:
                async with conn.cursor() as cursor:
                    if include_inactive:
                        await cursor.execute("SELECT id FROM rbac_roles ORDER BY level DESC, name")
                    else:
                        await cursor.execute(
                            "SELECT id FROM rbac_roles WHERE is_active = TRUE ORDER BY level DESC, name"
                        )

                    role_ids = [row[0] for row in await cursor.fetchall()]

            # 獲取角色對象
            roles = []
            for role_id in role_ids:
                role = await self.get_role(role_id)
                if role:
                    roles.append(role)

            return roles

        except Exception as e:
            logger.error(f"❌ 列出角色失敗: {e}")
            return []

    async def get_user_role_assignments(self, user_id: int, guild_id: int) -> List[Dict[str, Any]]:
        """
        獲取用戶角色分配詳情

        Args:
            user_id: Discord 用戶 ID
            guild_id: 伺服器 ID

        Returns:
            List[Dict[str, Any]]: 角色分配列表
        """
        try:
            async with db_pool.connection() as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute(
                        """
                        SELECT ur.role_id, r.name, r.description, ur.assigned_by,
                               ur.assigned_at, ur.expires_at, ur.is_active
                        FROM rbac_user_roles ur
                        JOIN rbac_roles r ON ur.role_id = r.id
                        WHERE ur.user_id = %s AND ur.guild_id = %s
                        ORDER BY r.level DESC, ur.assigned_at DESC
                    """,
                        (user_id, guild_id),
                    )

                    assignments = []
                    for row in await cursor.fetchall():
                        assignments.append(
                            {
                                "role_id": row[0],
                                "role_name": row[1],
                                "role_description": row[2],
                                "assigned_by": row[3],
                                "assigned_at": row[4].isoformat(),
                                "expires_at": row[5].isoformat() if row[5] else None,
                                "is_active": row[6],
                            }
                        )

                    return assignments

        except Exception as e:
            logger.error(f"❌ 獲取用戶角色分配失敗: {e}")
            return []

    def permission_required(self, permission: Permission):
        """權限檢查裝飾器"""

        def decorator(func):
            async def wrapper(self, interaction, *args, **kwargs):
                user_id = interaction.user.id
                guild_id = interaction.guild.id if interaction.guild else 0

                if not await self.check_permission(user_id, guild_id, permission):
                    await interaction.response.send_message(
                        f"❌ 您沒有執行此操作的權限 ({permission.value})",
                        ephemeral=True,
                    )
                    return

                return await func(self, interaction, *args, **kwargs)

            return wrapper

        return decorator

    # 私有方法

    def _is_cache_valid(self, cache_key: str) -> bool:
        """檢查快取是否有效"""
        if cache_key not in self._last_cache_update:
            return False

        return (
            datetime.now() - self._last_cache_update[cache_key]
        ).total_seconds() < self.cache_ttl

    async def _log_rbac_event(
        self, user_id: int, guild_id: int, event_type: str, details: Dict[str, Any]
    ):
        """記錄 RBAC 事件"""
        try:
            async with db_pool.connection() as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute(
                        """
                        INSERT INTO security_events (
                            user_id, guild_id, event_type, details, timestamp
                        ) VALUES (%s, %s, %s, %s, %s)
                    """,
                        (
                            user_id,
                            guild_id,
                            f"rbac_{event_type}",
                            json.dumps(details),
                            datetime.now(),
                        ),
                    )
                    await conn.commit()
        except Exception as e:
            logger.error(f"❌ RBAC 事件記錄失敗: {e}")


# 全域單例
rbac_manager = RBACManager()
