# bot/services/guild_permission_manager.py - v1.0.0
# 🔐 伺服器級權限管理系統
# Guild-Level Permission Management System

import json
import logging
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Set

import aiomysql
import discord

from bot.db.pool import db_pool

logger = logging.getLogger(__name__)


class GuildPermission(Enum):
    """伺服器權限類型"""

    # 系統管理權限
    SYSTEM_ADMIN = "system:admin"
    SYSTEM_CONFIG = "system:config"
    SYSTEM_MONITOR = "system:monitor"

    # 票券系統權限
    TICKET_ADMIN = "ticket:admin"
    TICKET_MANAGE = "ticket:manage"
    TICKET_VIEW_ALL = "ticket:view_all"
    TICKET_ASSIGN = "ticket:assign"
    TICKET_CLOSE = "ticket:close"

    # 投票系統權限
    VOTE_ADMIN = "vote:admin"
    VOTE_CREATE = "vote:create"
    VOTE_MANAGE = "vote:manage"
    VOTE_VIEW_RESULTS = "vote:view_results"

    # 歡迎系統權限
    WELCOME_ADMIN = "welcome:admin"
    WELCOME_CONFIG = "welcome:config"

    # 工作流程權限
    WORKFLOW_ADMIN = "workflow:admin"
    WORKFLOW_CREATE = "workflow:create"
    WORKFLOW_EXECUTE = "workflow:execute"

    # 安全管理權限
    SECURITY_ADMIN = "security:admin"
    SECURITY_AUDIT = "security:audit"
    SECURITY_CONFIG = "security:config"

    # 資料管理權限
    DATA_EXPORT = "data:export"
    DATA_DELETE = "data:delete"
    DATA_VIEW = "data:view"

    # API 存取權限
    API_ADMIN = "api:admin"
    API_READ = "api:read"
    API_WRITE = "api:write"


class GuildRole(Enum):
    """伺服器角色類型"""

    OWNER = "owner"  # 伺服器擁有者
    ADMIN = "admin"  # 伺服器管理員
    MODERATOR = "moderator"  # 版主
    STAFF = "staff"  # 工作人員
    USER = "user"  # 一般用戶
    GUEST = "guest"  # 訪客


@dataclass
class GuildUserPermissions:
    """伺服器用戶權限資料"""

    user_id: int
    guild_id: int
    roles: List[GuildRole]
    permissions: Set[GuildPermission]
    is_owner: bool = False
    is_admin: bool = False
    assigned_at: datetime = None
    expires_at: Optional[datetime] = None


class GuildPermissionManager:
    """伺服器權限管理器"""

    def __init__(self):
        self.db = db_pool
        self._permission_cache: Dict[str, GuildUserPermissions] = {}
        self._role_permissions: Dict[GuildRole, Set[GuildPermission]] = {}
        self._initialize_role_permissions()

    def _initialize_role_permissions(self):
        """初始化角色權限對應"""
        self._role_permissions = {
            GuildRole.OWNER: {
                # 擁有者擁有所有權限
                *list(GuildPermission)
            },
            GuildRole.ADMIN: {
                GuildPermission.SYSTEM_ADMIN,
                GuildPermission.SYSTEM_CONFIG,
                GuildPermission.SYSTEM_MONITOR,
                GuildPermission.TICKET_ADMIN,
                GuildPermission.VOTE_ADMIN,
                GuildPermission.WELCOME_ADMIN,
                GuildPermission.WORKFLOW_ADMIN,
                GuildPermission.SECURITY_CONFIG,
                GuildPermission.DATA_VIEW,
                GuildPermission.DATA_EXPORT,
                GuildPermission.API_ADMIN,
            },
            GuildRole.MODERATOR: {
                GuildPermission.TICKET_MANAGE,
                GuildPermission.TICKET_VIEW_ALL,
                GuildPermission.TICKET_ASSIGN,
                GuildPermission.TICKET_CLOSE,
                GuildPermission.VOTE_CREATE,
                GuildPermission.VOTE_MANAGE,
                GuildPermission.WELCOME_CONFIG,
                GuildPermission.WORKFLOW_EXECUTE,
                GuildPermission.DATA_VIEW,
                GuildPermission.API_READ,
            },
            GuildRole.STAFF: {
                GuildPermission.TICKET_MANAGE,
                GuildPermission.TICKET_ASSIGN,
                GuildPermission.VOTE_CREATE,
                GuildPermission.WORKFLOW_EXECUTE,
                GuildPermission.API_READ,
            },
            GuildRole.USER: {
                GuildPermission.DATA_VIEW,
                GuildPermission.API_READ,
            },
            GuildRole.GUEST: set(),  # 訪客沒有特殊權限
        }

    async def initialize_guild_permissions(self, guild: discord.Guild) -> bool:
        """初始化伺服器權限系統"""
        try:
            # 註冊伺服器到多租戶系統
            guild_info = {
                "name": guild.name,
                "member_count": guild.member_count,
                "owner_id": guild.owner_id,
                "features": guild.features,
            }

# Register tenant functionality removed with multi-tenant security framework

            # 初始化擁有者權限
            if guild.owner_id:
                await self._assign_role_to_user(
                    guild.owner_id, guild.id, GuildRole.OWNER, guild.owner_id
                )

            # 掃描現有管理員
            admin_members = [
                member
                for member in guild.members
                if member.guild_permissions.administrator and member.id != guild.owner_id
            ]

            for admin in admin_members:
                await self._assign_role_to_user(admin.id, guild.id, GuildRole.ADMIN, guild.owner_id)

            logger.info(f"✅ 伺服器權限系統初始化完成: {guild.name} (ID: {guild.id})")
            return True

        except Exception as e:
            logger.error(f"❌ 伺服器權限初始化失敗: {e}")
            return False

    async def check_permission(
        self,
        user_id: int,
        guild_id: int,
        permission: GuildPermission,
        check_discord_perms: bool = True,
    ) -> bool:
        """檢查用戶是否擁有特定權限"""
        try:
            # 獲取用戶權限
            user_perms = await self.get_user_permissions(user_id, guild_id)

            # 檢查直接權限
            if permission in user_perms.permissions:
                return True

            # 檢查 Discord 原生權限（可選）
            if check_discord_perms:
                discord_perm = await self._check_discord_permission(user_id, guild_id, permission)
                if discord_perm:
                    return True

            # 檢查是否為系統全域管理員
            if await self._is_global_admin(user_id):
                return True

            return False

        except Exception as e:
            logger.error(f"❌ 權限檢查失敗: {e}")
            return False

    async def get_user_permissions(self, user_id: int, guild_id: int) -> GuildUserPermissions:
        """獲取用戶在伺服器的權限"""
        cache_key = f"{user_id}:{guild_id}"

        # 檢查快取
        if cache_key in self._permission_cache:
            cached = self._permission_cache[cache_key]
            # 檢查快取是否過期（5分鐘）
            if cached.assigned_at and (datetime.now() - cached.assigned_at).total_seconds() < 300:
                return cached

        try:
            # 從資料庫載入
            permissions = await self._load_user_permissions(user_id, guild_id)

            # 更新快取
            self._permission_cache[cache_key] = permissions

            return permissions

        except Exception as e:
            logger.error(f"❌ 載入用戶權限失敗: {e}")
            # 返回預設權限
            return GuildUserPermissions(
                user_id=user_id,
                guild_id=guild_id,
                roles=[GuildRole.USER],
                permissions=self._role_permissions[GuildRole.USER],
                assigned_at=datetime.now(),
            )

    async def _load_user_permissions(self, user_id: int, guild_id: int) -> GuildUserPermissions:
        """從資料庫載入用戶權限"""
        try:
            # 查詢用戶在該伺服器的角色
            async with self.db.connection() as conn:
                async with conn.cursor(aiomysql.DictCursor) as cursor:
                    await cursor.execute(
                        """
                        SELECT * FROM guild_user_permissions 
                        WHERE guild_id = %s AND user_id = %s AND is_active = %s
                        """,
                        (guild_id, user_id, True),
                    )
                    result = await cursor.fetchone()

                    if result:
                        roles = [GuildRole(r) for r in result["roles"]]
                        permissions = set()

                        # 從角色計算權限
                        for role in roles:
                            permissions.update(self._role_permissions.get(role, set()))

                        # 添加直接權限
                        if result.get("direct_permissions"):
                            direct_perms = json.loads(result["direct_permissions"])
                            for perm in direct_perms:
                                try:
                                    permissions.add(GuildPermission(perm))
                                except ValueError:
                                    continue

                        return GuildUserPermissions(
                            user_id=user_id,
                            guild_id=guild_id,
                            roles=roles,
                            permissions=permissions,
                            is_owner=GuildRole.OWNER in roles,
                            is_admin=GuildRole.ADMIN in roles or GuildRole.OWNER in roles,
                            assigned_at=result.get("assigned_at"),
                            expires_at=result.get("expires_at"),
                        )

            # 沒有記錄，檢查是否為伺服器擁有者
            guild_info = await self._get_guild_info(guild_id)
            if guild_info and guild_info.get("owner_id") == user_id:
                # 自動分配擁有者角色
                await self._assign_role_to_user(user_id, guild_id, GuildRole.OWNER, user_id)
                return GuildUserPermissions(
                    user_id=user_id,
                    guild_id=guild_id,
                    roles=[GuildRole.OWNER],
                    permissions=self._role_permissions[GuildRole.OWNER],
                    is_owner=True,
                    is_admin=True,
                    assigned_at=datetime.now(),
                )

            # 預設為一般用戶
            return GuildUserPermissions(
                user_id=user_id,
                guild_id=guild_id,
                roles=[GuildRole.USER],
                permissions=self._role_permissions[GuildRole.USER],
                assigned_at=datetime.now(),
            )

        except Exception as e:
            logger.error(f"❌ 載入用戶權限失敗: {e}")
            raise

    async def assign_role(
        self,
        user_id: int,
        guild_id: int,
        role: GuildRole,
        assigned_by: int,
        expires_at: Optional[datetime] = None,
    ) -> bool:
        """分配角色給用戶"""
        try:
            # 檢查分配者權限
            if not await self.check_permission(assigned_by, guild_id, GuildPermission.SYSTEM_ADMIN):
                logger.warning(f"用戶 {assigned_by} 沒有權限分配角色")
                return False

            return await self._assign_role_to_user(user_id, guild_id, role, assigned_by, expires_at)

        except Exception as e:
            logger.error(f"❌ 分配角色失敗: {e}")
            return False

    async def _assign_role_to_user(
        self,
        user_id: int,
        guild_id: int,
        role: GuildRole,
        assigned_by: int,
        expires_at: Optional[datetime] = None,
    ) -> bool:
        """內部角色分配方法"""
        try:
            # 檢查是否已有記錄
            existing = await self.get_user_permissions(user_id, guild_id)

            if role not in existing.roles:
                # 添加新角色
                new_roles = existing.roles + [role]
            else:
                # 角色已存在，更新過期時間
                new_roles = existing.roles

            # 準備資料
            permission_data = {
                "user_id": user_id,
                "roles": json.dumps([r.value for r in new_roles]),
                "assigned_by": assigned_by,
                "assigned_at": datetime.now(),
                "expires_at": expires_at,
                "is_active": True,
            }

            # 使用 UPSERT 語法
            async with self.db.connection() as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute(
                        """
                        INSERT INTO guild_user_permissions
                        (user_id, guild_id, roles, assigned_by, assigned_at, expires_at, is_active)
                        VALUES (%s, %s, %s, %s, %s, %s, %s)
                        ON DUPLICATE KEY UPDATE
                        roles = VALUES(roles),
                        assigned_by = VALUES(assigned_by),
                        assigned_at = VALUES(assigned_at),
                        expires_at = VALUES(expires_at),
                        is_active = VALUES(is_active)
                    """,
                        (
                            user_id,
                            guild_id,
                            permission_data["roles"],
                            assigned_by,
                            permission_data["assigned_at"],
                            expires_at,
                            True,
                        ),
                    )
                    await conn.commit()

            # 清除快取
            cache_key = f"{user_id}:{guild_id}"
            if cache_key in self._permission_cache:
                del self._permission_cache[cache_key]

            logger.info(
                f"✅ 角色分配成功: 用戶 {user_id} 在伺服器 {guild_id} 獲得 {role.value} 角色"
            )
            return True

        except Exception as e:
            logger.error(f"❌ 內部角色分配失敗: {e}")
            return False

    async def remove_role(
        self, user_id: int, guild_id: int, role: GuildRole, removed_by: int
    ) -> bool:
        """移除用戶角色"""
        try:
            # 檢查權限
            if not await self.check_permission(removed_by, guild_id, GuildPermission.SYSTEM_ADMIN):
                return False

            # 獲取現有權限
            existing = await self.get_user_permissions(user_id, guild_id)

            if role in existing.roles:
                new_roles = [r for r in existing.roles if r != role]

                # 更新資料庫
                role_data = json.dumps([r.value for r in new_roles])

                async with self.db.connection() as conn:
                    async with conn.cursor() as cursor:
                        await cursor.execute(
                            """
                            UPDATE guild_user_permissions 
                            SET roles = %s, updated_at = %s 
                            WHERE user_id = %s AND guild_id = %s
                            """,
                            (role_data, datetime.now(), user_id, guild_id),
                        )
                        await conn.commit()

                # 清除快取
                cache_key = f"{user_id}:{guild_id}"
                if cache_key in self._permission_cache:
                    del self._permission_cache[cache_key]

                logger.info(f"✅ 角色移除成功: 用戶 {user_id} 失去 {role.value} 角色")
                return True

            return False

        except Exception as e:
            logger.error(f"❌ 移除角色失敗: {e}")
            return False

    async def _check_discord_permission(
        self, user_id: int, guild_id: int, permission: GuildPermission
    ) -> bool:
        """檢查 Discord 原生權限"""
        try:
            # 這裡需要從 Discord API 獲取用戶權限
            # 暫時返回 False，需要整合 Discord bot 實例
            return False

        except Exception as e:
            logger.error(f"❌ Discord 權限檢查失敗: {e}")
            return False

    async def _is_global_admin(self, user_id: int) -> bool:
        """檢查是否為系統全域管理員"""
        try:
            # 檢查全域管理員列表
            global_admins = [
                # 在這裡添加全域管理員的 Discord ID
            ]

            return user_id in global_admins

        except Exception as e:
            logger.error(f"❌ 全域管理員檢查失敗: {e}")
            return False

    async def _get_guild_info(self, guild_id: int) -> Optional[Dict[str, Any]]:
        """獲取伺服器資訊"""
        try:
            async with self.db.connection() as conn:
                async with conn.cursor(aiomysql.DictCursor) as cursor:
                    await cursor.execute(
                        "SELECT * FROM guild_info WHERE guild_id = %s", (guild_id,)
                    )
                    result = await cursor.fetchone()
                    return dict(result) if result else None
        except Exception as e:
            logger.error(f"❌ 獲取伺服器資訊失敗: {e}")
            return None

    async def get_guild_stats(self, guild_id: int) -> Dict[str, Any]:
        """獲取伺服器統計資訊"""
        try:
            stats_query = """
                SELECT
                    COUNT(DISTINCT user_id) as total_users,
                    COUNT(CASE WHEN JSON_CONTAINS(roles, '"admin"') THEN 1 END) as admin_count,
                    COUNT(CASE WHEN JSON_CONTAINS(roles, '"moderator"') THEN 1 END) as moderator_count,
                    COUNT(CASE WHEN JSON_CONTAINS(roles, '"staff"') THEN 1 END) as staff_count
                FROM guild_user_permissions
                WHERE guild_id = %s AND is_active = TRUE
            """

            async with self.db.connection() as conn:
                async with conn.cursor(aiomysql.DictCursor) as cursor:
                    await cursor.execute(stats_query, (guild_id,))
                    result = await cursor.fetchone()

                    return dict(result) if result else {}

        except Exception as e:
            logger.error(f"❌ 獲取伺服器統計失敗: {e}")
            return {}

    def clear_cache(self, user_id: Optional[int] = None, guild_id: Optional[int] = None):
        """清除權限快取"""
        if user_id and guild_id:
            # 清除特定用戶快取
            cache_key = f"{user_id}:{guild_id}"
            if cache_key in self._permission_cache:
                del self._permission_cache[cache_key]
        elif guild_id:
            # 清除整個伺服器的快取
            keys_to_remove = [
                key for key in self._permission_cache.keys() if key.endswith(f":{guild_id}")
            ]
            for key in keys_to_remove:
                del self._permission_cache[key]
        else:
            # 清除全部快取
            self._permission_cache.clear()


# 全域實例
guild_permission_manager = GuildPermissionManager()
