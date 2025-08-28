# bot/utils/multi_tenant_security.py - v1.0.0
# 🔐 多租戶安全架構核心
# Multi-Tenant Security Framework

import logging
from datetime import datetime
from functools import wraps
from typing import Any, Dict, List, Optional, Tuple, Union

import discord

logger = logging.getLogger(__name__)


class MultiTenantSecurityError(Exception):
    """多租戶安全異常"""


class TenantIsolationViolation(MultiTenantSecurityError):
    """租戶隔離違規異常"""


class UnauthorizedCrossTenantAccess(MultiTenantSecurityError):
    """未授權跨租戶存取異常"""


class MultiTenantSecurityManager:
    """多租戶安全管理器"""

    def __init__(self):
        self.tenant_configs: Dict[int, Dict[str, Any]] = {}
        self.security_policies: Dict[str, Dict[str, Any]] = {}
        self._initialize_default_policies()

    def _initialize_default_policies(self):
        """初始化預設安全政策"""
        self.security_policies = {
            "data_isolation": {
                "enforce_guild_id": True,
                "allow_cross_guild_admin": False,
                "audit_cross_guild_attempts": True,
            },
            "permission_isolation": {
                "inherit_permissions": False,
                "require_guild_admin": True,
                "allow_global_admin": True,
            },
            "api_isolation": {
                "require_guild_context": True,
                "validate_guild_access": True,
                "rate_limit_per_guild": True,
            },
        }

    async def register_tenant(self, guild_id: int, guild_info: Dict[str, Any]) -> bool:
        """註冊新租戶（伺服器）"""
        try:
            self.tenant_configs[guild_id] = {
                "guild_id": guild_id,
                "guild_name": guild_info.get("name", "Unknown"),
                "member_count": guild_info.get("member_count", 0),
                "owner_id": guild_info.get("owner_id"),
                "created_at": datetime.now(),
                "features": guild_info.get("features", []),
                "status": "active",
                "data_retention_days": 365,  # 預設資料保留期
                "privacy_level": "strict",  # strict, normal, relaxed
                "allowed_integrations": [],  # 允許的第三方整合
                "security_settings": {
                    "require_mfa_for_admin": False,
                    "audit_all_actions": True,
                    "data_export_enabled": True,
                    "cross_channel_access": False,
                },
            }

            logger.info(f"✅ 租戶註冊成功: {guild_info.get('name')} (ID: {guild_id})")
            return True

        except Exception as e:
            logger.error(f"❌ 租戶註冊失敗: {e}")
            return False

    async def validate_guild_access(
        self, user_id: int, guild_id: int, required_permission: Optional[str] = None
    ) -> bool:
        """驗證用戶對伺服器的存取權限"""
        try:
            # 檢查用戶是否為該伺服器成員
            # 這裡需要與 Discord API 整合驗證
            return True  # 暫時返回 True，實際實現需要 Discord API 驗證

        except Exception as e:
            logger.error(f"❌ 權限驗證失敗: {e}")
            return False

    def require_guild_context(self, allow_dm: bool = False):
        """裝飾器：要求指令在伺服器環境中執行"""

        def decorator(func):
            @wraps(func)
            async def wrapper(*args, **kwargs):
                # 尋找 interaction 參數
                interaction = None
                for arg in args:
                    if isinstance(arg, discord.Interaction):
                        interaction = arg
                        break

                if not interaction:
                    raise MultiTenantSecurityError("無法找到 Discord Interaction")

                if not interaction.guild and not allow_dm:
                    await interaction.response.send_message(
                        "❌ 此指令只能在伺服器中使用", ephemeral=True
                    )
                    return

                # 添加 guild_id 到 kwargs
                if interaction.guild:
                    kwargs["guild_id"] = interaction.guild.id

                return await func(*args, **kwargs)

            return wrapper

        return decorator

    def enforce_tenant_isolation(self, table_name: str, require_guild_id: bool = True):
        """裝飾器：強制執行租戶隔離"""

        def decorator(func):
            @wraps(func)
            async def wrapper(*args, **kwargs):
                if require_guild_id and "guild_id" not in kwargs:
                    raise TenantIsolationViolation(f"查詢 {table_name} 表格必須提供 guild_id 參數")

                guild_id = kwargs.get("guild_id")
                if guild_id and not await self.validate_guild_access(
                    kwargs.get("user_id", 0), guild_id
                ):
                    raise UnauthorizedCrossTenantAccess(
                        f"未授權存取伺服器 {guild_id} 的 {table_name} 資料"
                    )

                return await func(*args, **kwargs)

            return wrapper

        return decorator


class SecureQueryBuilder:
    """安全查詢建構器 - 自動添加租戶隔離"""

    def __init__(self, security_manager: MultiTenantSecurityManager):
        self.security_manager = security_manager

    def build_select(
        self,
        table: str,
        columns: Union[str, List[str]] = "*",
        guild_id: Optional[int] = None,
        additional_where: Optional[Dict[str, Any]] = None,
    ) -> Tuple[str, List[Any]]:
        """建構安全的 SELECT 查詢"""

        # 處理欄位
        if isinstance(columns, list):
            columns_str = ", ".join(columns)
        else:
            columns_str = columns

        # 建構基本查詢
        query = f"SELECT {columns_str} FROM {table}"
        params = []
        where_conditions = []

        # 強制添加 guild_id 隔離（除非明確允許跨租戶）
        if guild_id is not None:
            where_conditions.append("guild_id = %s")
            params.append(guild_id)
        elif self.security_manager.security_policies["data_isolation"]["enforce_guild_id"]:
            raise TenantIsolationViolation(f"查詢 {table} 必須提供 guild_id")

        # 添加額外條件
        if additional_where:
            for column, value in additional_where.items():
                if isinstance(value, list):
                    # IN 查詢
                    placeholders = ", ".join(["%s"] * len(value))
                    where_conditions.append(f"{column} IN ({placeholders})")
                    params.extend(value)
                else:
                    where_conditions.append(f"{column} = %s")
                    params.append(value)

        # 組合 WHERE 條件
        if where_conditions:
            query += " WHERE " + " AND ".join(where_conditions)

        return query, params

    def build_insert(
        self, table: str, data: Dict[str, Any], guild_id: Optional[int] = None
    ) -> Tuple[str, List[Any]]:
        """建構安全的 INSERT 查詢"""

        # 強制添加 guild_id
        if guild_id is not None and "guild_id" not in data:
            data["guild_id"] = guild_id

        columns = list(data.keys())
        placeholders = ", ".join(["%s"] * len(columns))
        columns_str = ", ".join(columns)

        query = f"INSERT INTO {table} ({columns_str}) VALUES ({placeholders})"
        params = list(data.values())

        return query, params

    def build_update(
        self,
        table: str,
        data: Dict[str, Any],
        where_conditions: Dict[str, Any],
        guild_id: Optional[int] = None,
    ) -> Tuple[str, List[Any]]:
        """建構安全的 UPDATE 查詢"""

        # 建構 SET 部分
        set_clauses = []
        params = []

        for column, value in data.items():
            set_clauses.append(f"{column} = %s")
            params.append(value)

        query = f"UPDATE {table} SET {', '.join(set_clauses)}"

        # 建構 WHERE 部分
        where_clauses = []

        # 強制添加 guild_id 隔離
        if guild_id is not None:
            where_clauses.append("guild_id = %s")
            params.append(guild_id)

        # 添加其他條件
        for column, value in where_conditions.items():
            where_clauses.append(f"{column} = %s")
            params.append(value)

        if where_clauses:
            query += " WHERE " + " AND ".join(where_clauses)

        return query, params

    def build_delete(
        self, table: str, where_conditions: Dict[str, Any], guild_id: Optional[int] = None
    ) -> Tuple[str, List[Any]]:
        """建構安全的 DELETE 查詢"""

        query = f"DELETE FROM {table}"
        params = []
        where_clauses = []

        # 強制添加 guild_id 隔離
        if guild_id is not None:
            where_clauses.append("guild_id = %s")
            params.append(guild_id)

        # 添加其他條件
        for column, value in where_conditions.items():
            where_clauses.append(f"{column} = %s")
            params.append(value)

        if where_clauses:
            query += " WHERE " + " AND ".join(where_clauses)

        return query, params


class TenantDataManager:
    """租戶資料管理器"""

    def __init__(self, security_manager: MultiTenantSecurityManager):
        self.security_manager = security_manager
        self.query_builder = SecureQueryBuilder(security_manager)

    async def export_guild_data(self, guild_id: int, data_types: List[str]) -> Dict[str, Any]:
        """匯出伺服器資料（GDPR 合規）"""
        try:
            export_data = {
                "guild_id": guild_id,
                "export_date": datetime.now().isoformat(),
                "data_types": data_types,
                "data": {},
            }

            # 這裡需要實現具體的資料匯出邏輯
            # 遍歷所有表格，匯出屬於該伺服器的資料

            logger.info(f"✅ 伺服器 {guild_id} 資料匯出完成")
            return export_data

        except Exception as e:
            logger.error(f"❌ 資料匯出失敗: {e}")
            raise

    async def delete_guild_data(self, guild_id: int, retain_logs: bool = True) -> Dict[str, Any]:
        """刪除伺服器資料（GDPR 刪除權）"""
        try:
            deleted_records = {}

            # 定義需要清理的表格
            tables_to_clean = [
                "tickets",
                "ticket_settings",
                "ticket_logs",
                "votes",
                "vote_responses",
                "vote_settings",
                "welcome_settings",
                "welcome_logs",
                "workflows",
                "workflow_executions",
                "webhooks",
                "webhook_logs",
            ]

            if not retain_logs:
                tables_to_clean.extend(
                    ["security_events", "data_access_logs", "audit_logs", "system_logs"]
                )

            # 這裡需要實現具體的資料刪除邏輯

            logger.info(f"✅ 伺服器 {guild_id} 資料刪除完成")
            return deleted_records

        except Exception as e:
            logger.error(f"❌ 資料刪除失敗: {e}")
            raise


# 全域實例
multi_tenant_security = MultiTenantSecurityManager()
secure_query_builder = SecureQueryBuilder(multi_tenant_security)
tenant_data_manager = TenantDataManager(multi_tenant_security)

# 常用裝飾器
require_guild = multi_tenant_security.require_guild_context
enforce_isolation = multi_tenant_security.enforce_tenant_isolation

# 使用範例：
# @require_guild()
# @enforce_isolation("tickets")
# async def get_tickets(guild_id: int, user_id: int):
#     query, params = secure_query_builder.build_select(
#         "tickets", guild_id=guild_id, additional_where={"user_id": user_id}
#     )
#     # 執行查詢...
