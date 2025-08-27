# bot/services/guild_manager.py - v1.0.0
# 🏛️ 伺服器管理器
# Guild Management Service

import asyncio
import json
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import aiomysql
import discord
from discord.ext import commands

from bot.db.pool import db_pool
from bot.services.guild_permission_manager import (
    GuildPermission,
    GuildRole,
    guild_permission_manager,
)
from bot.utils.multi_tenant_security import multi_tenant_security, secure_query_builder

logger = logging.getLogger(__name__)


class GuildManager:
    """伺服器管理器 - 處理伺服器生命週期管理"""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.db = db_pool
        self.security = multi_tenant_security
        self.query_builder = secure_query_builder
        self.permission_manager = guild_permission_manager
        self._initialization_lock = asyncio.Lock()

        # 註冊事件處理器
        self.bot.add_listener(self.on_guild_join, "on_guild_join")
        self.bot.add_listener(self.on_guild_remove, "on_guild_remove")
        self.bot.add_listener(self.on_guild_update, "on_guild_update")

    async def on_guild_join(self, guild: discord.Guild):
        """處理 Bot 加入新伺服器"""
        try:
            logger.info(
                f"🆕 Bot 加入新伺服器: {guild.name} (ID: {guild.id}, 成員: {guild.member_count})"
            )

            async with self._initialization_lock:
                # 初始化伺服器
                success = await self.initialize_guild(guild)

                if success:
                    logger.info(f"✅ 伺服器 {guild.name} 初始化完成")

                    # 發送歡迎訊息給伺服器擁有者
                    await self._send_welcome_message(guild)

                    # 記錄伺服器加入事件
                    await self._log_guild_event(
                        guild.id,
                        None,
                        "guild_join",
                        "guild_management",
                        "Bot joined guild",
                        {"member_count": guild.member_count},
                    )
                else:
                    logger.error(f"❌ 伺服器 {guild.name} 初始化失敗")

        except Exception as e:
            logger.error(f"❌ 處理伺服器加入失敗: {e}")

    async def on_guild_remove(self, guild: discord.Guild):
        """處理 Bot 離開伺服器"""
        try:
            logger.info(f"👋 Bot 離開伺服器: {guild.name} (ID: {guild.id})")

            # 更新伺服器狀態
            await self._update_guild_status(guild.id, "inactive")

            # 記錄離開事件
            await self._log_guild_event(
                guild.id, None, "guild_leave", "guild_management", "Bot left guild", {}
            )

            # 可選：清理快取
            self.permission_manager.clear_cache(guild_id=guild.id)

            logger.info(f"✅ 伺服器 {guild.name} 離開處理完成")

        except Exception as e:
            logger.error(f"❌ 處理伺服器離開失敗: {e}")

    async def on_guild_update(self, before: discord.Guild, after: discord.Guild):
        """處理伺服器更新"""
        try:
            changes = []

            # 檢查名稱變更
            if before.name != after.name:
                changes.append(f"名稱: {before.name} -> {after.name}")

            # 檢查成員數變化
            if before.member_count != after.member_count:
                changes.append(f"成員數: {before.member_count} -> {after.member_count}")

            # 檢查擁有者變更
            if before.owner_id != after.owner_id:
                changes.append(f"擁有者: {before.owner_id} -> {after.owner_id}")
                # 更新權限系統
                await self._handle_owner_change(after.id, before.owner_id, after.owner_id)

            if changes:
                logger.info(f"🔄 伺服器更新: {after.name} - {', '.join(changes)}")

                # 更新資料庫資訊
                await self._update_guild_info(after)

                # 記錄更新事件
                await self._log_guild_event(
                    after.id,
                    None,
                    "guild_update",
                    "guild_management",
                    f"Guild updated: {', '.join(changes)}",
                    {
                        "before": self._serialize_guild(before),
                        "after": self._serialize_guild(after),
                    },
                )

        except Exception as e:
            logger.error(f"❌ 處理伺服器更新失敗: {e}")

    async def initialize_guild(self, guild: discord.Guild) -> bool:
        """初始化新伺服器"""
        try:
            # 1. 創建伺服器資訊記錄
            await self._create_guild_info(guild)

            # 2. 初始化權限系統
            await self.permission_manager.initialize_guild_permissions(guild)

            # 3. 創建預設設定
            await self._create_default_settings(guild)

            # 4. 初始化配額限制
            await self._create_default_quotas(guild)

            # 5. 初始化各系統的預設設定
            await self._initialize_system_defaults(guild)

            # 6. 創建初始統計記錄
            await self._create_initial_statistics(guild)

            logger.info(f"✅ 伺服器 {guild.name} 完整初始化完成")
            return True

        except Exception as e:
            logger.error(f"❌ 伺服器初始化失敗: {e}")
            return False

    async def _create_guild_info(self, guild: discord.Guild):
        """創建伺服器資訊記錄"""
        try:
            guild_data = {
                "guild_id": guild.id,
                "guild_name": guild.name,
                "owner_id": guild.owner_id,
                "member_count": guild.member_count,
                "premium_tier": guild.premium_tier,
                "features": json.dumps(guild.features),
                "icon_hash": guild.icon.key if guild.icon else None,
                "banner_hash": guild.banner.key if guild.banner else None,
                "description": guild.description,
                "preferred_locale": (
                    str(guild.preferred_locale) if guild.preferred_locale else "zh-TW"
                ),
                "verification_level": guild.verification_level.name,
                "mfa_level": guild.mfa_level.name if guild.mfa_level.name == "none" else "elevated",
                "explicit_content_filter": guild.explicit_content_filter.name,
                "status": "active",
                "bot_joined_at": datetime.now(),
            }

            # 使用 REPLACE INTO 避免重複加入問題
            columns = ", ".join(guild_data.keys())
            placeholders = ", ".join(["%s"] * len(guild_data))

            async with self.db.connection() as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute(
                        f"""
                        REPLACE INTO guild_info ({columns})
                        VALUES ({placeholders})
                    """,
                        list(guild_data.values()),
                    )
                    await conn.commit()

            logger.info(f"✅ 伺服器資訊記錄已創建: {guild.name}")

        except Exception as e:
            logger.error(f"❌ 創建伺服器資訊失敗: {e}")
            raise

    async def _create_default_settings(self, guild: discord.Guild):
        """創建預設伺服器設定"""
        try:
            default_settings = {
                "guild_id": guild.id,
                "language": "zh-TW",
                "timezone": "Asia/Taipei",
                "currency": "TWD",
                "modules_enabled": json.dumps(["ticket", "vote", "welcome", "workflow"]),
                "features_disabled": json.dumps([]),
                "notification_channels": json.dumps({}),
                "alert_settings": json.dumps(
                    {"sla_alerts": True, "error_alerts": True, "security_alerts": True}
                ),
                "security_level": "medium",
                "require_mfa_for_admin": False,
                "audit_all_actions": True,
                "data_export_enabled": True,
                "cross_channel_access": False,
                "auto_moderation": json.dumps({"enabled": False, "rules": []}),
                "auto_cleanup_settings": json.dumps(
                    {"enabled": True, "cleanup_logs_days": 30, "cleanup_tickets_days": 90}
                ),
            }

            columns = ", ".join(default_settings.keys())
            placeholders = ", ".join(["%s"] * len(default_settings))

            async with self.db.connection() as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute(
                        f"""
                        INSERT IGNORE INTO guild_settings ({columns})
                        VALUES ({placeholders})
                    """,
                        list(default_settings.values()),
                    )
                    await conn.commit()

            logger.info(f"✅ 預設設定已創建: {guild.name}")

        except Exception as e:
            logger.error(f"❌ 創建預設設定失敗: {e}")
            raise

    async def _create_default_quotas(self, guild: discord.Guild):
        """創建預設配額限制"""
        try:
            # 根據伺服器大小決定初始方案
            if guild.member_count > 10000:
                plan_type = "premium"
            elif guild.member_count > 1000:
                plan_type = "basic"
            else:
                plan_type = "free"

            quotas_map = {
                "free": {
                    "max_tickets_per_user": 3,
                    "max_votes_per_user": 5,
                    "max_workflows": 10,
                    "max_webhooks": 5,
                    "max_api_calls_per_day": 1000,
                    "max_storage_mb": 50,
                    "commands_per_minute": 30,
                },
                "basic": {
                    "max_tickets_per_user": 10,
                    "max_votes_per_user": 20,
                    "max_workflows": 50,
                    "max_webhooks": 20,
                    "max_api_calls_per_day": 10000,
                    "max_storage_mb": 200,
                    "commands_per_minute": 100,
                },
                "premium": {
                    "max_tickets_per_user": 50,
                    "max_votes_per_user": 100,
                    "max_workflows": 200,
                    "max_webhooks": 100,
                    "max_api_calls_per_day": 50000,
                    "max_storage_mb": 1000,
                    "commands_per_minute": 300,
                },
            }

            quota_data = quotas_map[plan_type]
            quota_data.update(
                {
                    "guild_id": guild.id,
                    "plan_type": plan_type,
                    "billing_cycle_start": datetime.now().date(),
                    "billing_cycle_end": (datetime.now() + timedelta(days=30)).date(),
                    "overage_alerts_enabled": True,
                }
            )

            columns = ", ".join(quota_data.keys())
            placeholders = ", ".join(["%s"] * len(quota_data))

            async with self.db.connection() as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute(
                        f"""
                        INSERT IGNORE INTO guild_quotas ({columns})
                        VALUES ({placeholders})
                    """,
                        list(quota_data.values()),
                    )
                    await conn.commit()

            logger.info(f"✅ 配額限制已創建: {guild.name} ({plan_type} 方案)")

        except Exception as e:
            logger.error(f"❌ 創建配額限制失敗: {e}")
            raise

    async def _initialize_system_defaults(self, guild: discord.Guild):
        """初始化各系統的預設設定"""
        try:
            # 1. 票券系統預設設定
            from bot.db.ticket_dao import TicketDAO

            ticket_dao = TicketDAO()
            await ticket_dao.create_default_settings(guild.id)

            # 2. 投票系統預設設定
            await self._create_vote_settings(guild.id)

            # 3. 歡迎系統預設設定
            await self._create_welcome_settings(guild.id)

            logger.info(f"✅ 系統預設設定已初始化: {guild.name}")

        except Exception as e:
            logger.error(f"❌ 初始化系統預設設定失敗: {e}")
            # 不拋出異常，因為這不是關鍵錯誤

    async def _create_vote_settings(self, guild_id: int):
        """創建投票系統預設設定"""
        try:
            vote_settings = {
                "guild_id": guild_id,
                "default_duration_hours": 24,
                "allow_anonymous": True,
                "allow_multiple_choice": True,
                "require_role_to_create": False,
                "auto_end_enabled": True,
                "results_visible": "after_end",
            }

            columns = ", ".join(vote_settings.keys())
            placeholders = ", ".join(["%s"] * len(vote_settings))

            async with self.db.connection() as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute(
                        f"""
                        INSERT IGNORE INTO vote_settings ({columns})
                        VALUES ({placeholders})
                    """,
                        list(vote_settings.values()),
                    )
                    await conn.commit()

        except Exception as e:
            logger.error(f"❌ 創建投票設定失敗: {e}")

    async def _create_welcome_settings(self, guild_id: int):
        """創建歡迎系統預設設定"""
        try:
            welcome_settings = {
                "guild_id": guild_id,
                "welcome_enabled": False,  # 預設關閉，讓用戶手動開啟
                "welcome_channel_id": None,
                "welcome_message": "歡迎 {user_mention} 加入 {guild_name}！",
                "farewell_enabled": False,
                "farewell_message": "{user_name} 已離開伺服器。",
                "dm_welcome_enabled": False,
                "auto_role_enabled": False,
            }

            columns = ", ".join(welcome_settings.keys())
            placeholders = ", ".join(["%s"] * len(welcome_settings))

            async with self.db.connection() as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute(
                        f"""
                        INSERT IGNORE INTO welcome_settings ({columns})
                        VALUES ({placeholders})
                    """,
                        list(welcome_settings.values()),
                    )
                    await conn.commit()

        except Exception as e:
            logger.error(f"❌ 創建歡迎設定失敗: {e}")

    async def _create_initial_statistics(self, guild: discord.Guild):
        """創建初始統計記錄"""
        try:
            today = datetime.now().date()

            stats_data = {
                "guild_id": guild.id,
                "date": today,
                "member_count": guild.member_count,
                "active_members": 0,
                "new_members": guild.member_count,  # 假設所有成員都是新的
                "left_members": 0,
            }

            columns = ", ".join(stats_data.keys())
            placeholders = ", ".join(["%s"] * len(stats_data))

            async with self.db.connection() as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute(
                        f"""
                        INSERT IGNORE INTO guild_statistics ({columns})
                        VALUES ({placeholders})
                    """,
                        list(stats_data.values()),
                    )
                    await conn.commit()

            logger.info(f"✅ 初始統計記錄已創建: {guild.name}")

        except Exception as e:
            logger.error(f"❌ 創建初始統計失敗: {e}")

    async def _send_welcome_message(self, guild: discord.Guild):
        """發送歡迎訊息給伺服器擁有者"""
        try:
            if not guild.owner:
                return

            embed = discord.Embed(
                title="🎉 感謝邀請 Potato Bot！",
                description=f"Bot 已成功加入 **{guild.name}**",
                color=discord.Color.green(),
            )

            embed.add_field(
                name="🚀 快速開始",
                value="• 使用 `/help` 查看所有可用指令\n"
                "• 使用 `/ticket_settings` 設定票券系統\n"
                "• 使用 `/welcome_setup` 設定歡迎系統",
                inline=False,
            )

            embed.add_field(
                name="🔧 管理面板",
                value=f"訪問 Web 管理介面: http://your-domain.com/guild/{guild.id}",
                inline=False,
            )

            embed.add_field(
                name="📚 需要幫助？",
                value="• 查看文檔: https://docs.your-domain.com\n"
                "• 加入支援伺服器: https://discord.gg/your-support",
                inline=False,
            )

            embed.set_footer(
                text="Potato Bot - 企業級 Discord 管理系統",
                icon_url=self.bot.user.avatar.url if self.bot.user.avatar else None,
            )

            await guild.owner.send(embed=embed)
            logger.info(f"✅ 歡迎訊息已發送給 {guild.owner.name}")

        except discord.Forbidden:
            logger.warning(f"無法發送私訊給 {guild.owner.name}")
        except Exception as e:
            logger.error(f"❌ 發送歡迎訊息失敗: {e}")

    async def _update_guild_status(self, guild_id: int, status: str):
        """更新伺服器狀態"""
        try:
            async with self.db.connection() as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute(
                        """
                        UPDATE guild_info
                        SET status = %s, bot_left_at = %s, last_activity = %s
                        WHERE guild_id = %s
                    """,
                        (status, datetime.now(), datetime.now(), guild_id),
                    )
                    await conn.commit()

        except Exception as e:
            logger.error(f"❌ 更新伺服器狀態失敗: {e}")

    async def _update_guild_info(self, guild: discord.Guild):
        """更新伺服器資訊"""
        try:
            update_data = {
                "guild_name": guild.name,
                "member_count": guild.member_count,
                "owner_id": guild.owner_id,
                "premium_tier": guild.premium_tier,
                "features": json.dumps(guild.features),
                "icon_hash": guild.icon.key if guild.icon else None,
                "banner_hash": guild.banner.key if guild.banner else None,
                "description": guild.description,
                "last_activity": datetime.now(),
            }

            query, params = self.query_builder.build_update(
                table="guild_info", data=update_data, where_conditions={"guild_id": guild.id}
            )

            async with self.db.connection() as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute(query, params)
                    await conn.commit()

        except Exception as e:
            logger.error(f"❌ 更新伺服器資訊失敗: {e}")

    async def _handle_owner_change(self, guild_id: int, old_owner_id: int, new_owner_id: int):
        """處理伺服器擁有者變更"""
        try:
            # 移除舊擁有者的擁有者角色，改為管理員
            if old_owner_id:
                await self.permission_manager.remove_role(
                    old_owner_id, guild_id, GuildRole.OWNER, new_owner_id
                )
                await self.permission_manager.assign_role(
                    old_owner_id, guild_id, GuildRole.ADMIN, new_owner_id
                )

            # 分配新擁有者角色
            await self.permission_manager.assign_role(
                new_owner_id, guild_id, GuildRole.OWNER, new_owner_id
            )

            logger.info(f"✅ 伺服器擁有者變更處理完成: {old_owner_id} -> {new_owner_id}")

        except Exception as e:
            logger.error(f"❌ 處理擁有者變更失敗: {e}")

    async def _log_guild_event(
        self,
        guild_id: int,
        user_id: Optional[int],
        event_type: str,
        category: str,
        description: str,
        metadata: Dict[str, Any],
    ):
        """記錄伺服器事件"""
        try:
            event_data = {
                "guild_id": guild_id,
                "user_id": user_id,
                "event_type": event_type,
                "event_category": category,
                "event_name": event_type,
                "description": description,
                "metadata": json.dumps(metadata),
                "source": "bot",
                "status": "success",
            }

            columns = ", ".join(event_data.keys())
            placeholders = ", ".join(["%s"] * len(event_data))

            async with self.db.connection() as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute(
                        f"""
                        INSERT INTO guild_event_logs ({columns})
                        VALUES ({placeholders})
                    """,
                        list(event_data.values()),
                    )
                    await conn.commit()

        except Exception as e:
            logger.error(f"❌ 記錄伺服器事件失敗: {e}")

    def _serialize_guild(self, guild: discord.Guild) -> Dict[str, Any]:
        """序列化伺服器資訊供日誌使用"""
        return {
            "id": guild.id,
            "name": guild.name,
            "owner_id": guild.owner_id,
            "member_count": guild.member_count,
            "premium_tier": guild.premium_tier,
        }

    async def get_guild_stats(self, guild_id: int) -> Dict[str, Any]:
        """獲取伺服器統計資訊"""
        try:
            async with self.db.connection() as conn:
                async with conn.cursor(aiomysql.DictCursor) as cursor:
                    # 基本資訊
                    await cursor.execute(
                        """
                        SELECT gi.*, gs.language, gs.timezone, gs.security_level,
                               gq.plan_type, gq.max_tickets_per_user
                        FROM guild_info gi
                        LEFT JOIN guild_settings gs ON gi.guild_id = gs.guild_id
                        LEFT JOIN guild_quotas gq ON gi.guild_id = gq.guild_id
                        WHERE gi.guild_id = %s
                    """,
                        (guild_id,),
                    )

                    guild_info = await cursor.fetchone()

                    # 權限統計
                    permission_stats = await self.permission_manager.get_guild_stats(guild_id)

                    # 最近統計
                    await cursor.execute(
                        """
                        SELECT * FROM guild_statistics
                        WHERE guild_id = %s
                        ORDER BY date DESC
                        LIMIT 7
                    """,
                        (guild_id,),
                    )

                    recent_stats = await cursor.fetchall()

                    return {
                        "guild_info": dict(guild_info) if guild_info else {},
                        "permission_stats": permission_stats,
                        "recent_stats": [dict(stat) for stat in recent_stats],
                    }

        except Exception as e:
            logger.error(f"❌ 獲取伺服器統計失敗: {e}")
            return {}


# 此管理器會在 bot 初始化時創建
# guild_manager = GuildManager(bot)  # 在 main.py 中創建
