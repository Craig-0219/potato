# bot/listeners/ticket_listener.py - 票券系統事件監聽器完整版

import asyncio
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import discord
from discord.ext import commands, tasks

from potato_bot.db.ticket_dao import TicketDAO
from potato_bot.services.chat_transcript_manager import ChatTranscriptManager
from potato_bot.utils.ticket_constants import get_priority_emoji
from potato_bot.utils.ticket_utils import (
    TicketPermissionChecker,
    get_support_roles_for_ticket,
    is_ticket_channel,
)
from potato_shared.logger import logger


class TicketListener(commands.Cog):
    """票券系統事件監聽器 - 完整版"""

    def __init__(
        self,
        bot,
        auto_reply_service: Optional[Any] = None,
        notification_service: Optional[Any] = None,
    ):
        self.bot = bot
        self.dao = TicketDAO()
        self.transcript_manager = ChatTranscriptManager()

        # 可選服務
        self.auto_reply_service = auto_reply_service or getattr(bot, "auto_reply_service", None)
        self.notification_service = notification_service or getattr(
            bot, "notification_service", None
        )

        # 狀態追蹤
        self.staff_online_status = {}  # 追蹤客服在線狀態

        # 快取和限流
        self._message_cache = {}

        # 啟動背景任務
        self.cleanup_task.start()

    def cog_unload(self):
        """清理資源"""
        self.cleanup_task.cancel()

        # 停止服務
        # asyncio.create_task(self.service_coordinator.stop_services())

    def _get_ticket_id(self, ticket_info: Dict[str, Any]) -> Optional[int]:
        """統一取得票券 ID"""
        if not ticket_info:
            return None
        return ticket_info.get("ticket_id") or ticket_info.get("id")

    # ===== 訊息事件監聽 =====

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        """監聽訊息事件 - 增強版"""
        # 忽略機器人訊息和非伺服器訊息
        if message.author.bot or not message.guild:
            return

        # 檢查是否為票券頻道
        if not is_ticket_channel(message.channel):
            return

        try:
            # 取得票券資訊
            ticket_info = await self.dao.get_ticket_by_channel(message.channel.id)
            if not ticket_info or ticket_info["status"] != "open":
                return

            ticket_id = self._get_ticket_id(ticket_info)
            if not ticket_id:
                logger.warning("票券資訊缺少 ID，跳過訊息記錄")
                return

            # 記錄聊天訊息到資料庫
            await self.transcript_manager.record_message(ticket_id, message)

            # 更新票券活動時間
            await self.dao.update_last_activity(ticket_id)

            # 處理不同類型的訊息
            if str(message.author.id) == ticket_info["discord_id"]:
                await self._handle_user_message(message, ticket_info)
            else:
                await self._handle_staff_message(message, ticket_info)

        except Exception as e:
            logger.error(f"處理客服訊息失敗: {e}")

    async def _handle_user_message(self, message: discord.Message, ticket_info: Dict):
        """處理用戶訊息 - 增強版"""
        try:
            # 檢查是否需要觸發自動回覆
            if self.auto_reply_service and await self._should_trigger_auto_reply(
                message, ticket_info
            ):
                await self.auto_reply_service.process_message(message, ticket_info)

            # 檢查是否包含緊急關鍵字
            await self._check_urgent_keywords(message, ticket_info)

        except Exception as e:
            logger.error(f"處理用戶訊息失敗: {e}")

    async def _handle_staff_message(self, message: discord.Message, ticket_info: Dict):
        """處理客服訊息 - 增強版"""
        try:
            # 取得伺服器設定
            settings = await self.dao.get_guild_settings(message.guild.id)

            # 檢查是否為客服人員
            support_roles = get_support_roles_for_ticket(settings, ticket_info.get("type"))
            if not TicketPermissionChecker.is_support_staff(
                message.author, support_roles
            ):
                return

            # 檢查是否使用了模板回覆
            await self._detect_template_usage(message, ticket_info)

        except Exception as e:
            logger.error(f"處理票券回覆時發生錯誤: {e}", exc_info=True)

    async def _should_trigger_auto_reply(self, message: discord.Message, ticket_info: Dict) -> bool:
        """檢查是否應該觸發自動回覆"""
        ticket_id = self._get_ticket_id(ticket_info)
        if not ticket_id:
            return False

        # 避免過於頻繁的自動回覆
        cache_key = f"auto_reply_{ticket_id}"
        last_reply_time = self._message_cache.get(cache_key)

        if last_reply_time:
            time_diff = datetime.now(timezone.utc) - last_reply_time
            if time_diff.total_seconds() < 300:  # 5分鐘內不重複觸發
                return False

        # 記錄此次觸發時間
        self._message_cache[cache_key] = datetime.now(timezone.utc)
        return True

    async def _check_urgent_keywords(self, message: discord.Message, ticket_info: Dict):
        """檢查緊急關鍵字"""
        ticket_id = self._get_ticket_id(ticket_info)
        if not ticket_id:
            return

        urgent_keywords = [
            "緊急",
            "urgent",
            "emergency",
            "立即",
            "馬上",
            "很急",
            "停機",
            "故障",
            "無法使用",
            "down",
            "crash",
            "error",
        ]

        content_lower = message.content.lower()

        for keyword in urgent_keywords:
            if keyword in content_lower:
                # 如果當前不是高優先級，自動升級
                if ticket_info.get("priority", "medium") != "high":
                    await self.dao.update_ticket_priority(ticket_id, "high")

                    # 通知頻道
                    embed = discord.Embed(
                        title="⚡ 優先級自動升級",
                        description=f"檢測到緊急關鍵字「{keyword}」，票券優先級已升級為高優先級。",
                        color=discord.Color.red(),
                    )
                    await message.channel.send(embed=embed)

    async def _detect_template_usage(self, message: discord.Message, ticket_info: Dict):
        """檢測模板使用"""
        # 簡單的模板檢測邏輯
        content = message.content

        # 檢查是否包含常見模板標識
        template_indicators = [
            "感謝您的",
            "根據您的問題",
            "請提供以下",
            "我們建議您",
            "根據系統記錄",
            "經過檢查",
            "解決方案如下",
        ]

        for indicator in template_indicators:
            if indicator in content:
                # 記錄模板使用
                ticket_id = self._get_ticket_id(ticket_info)
                logger.info(f"檢測到模板使用: {indicator} 在票券 {ticket_id}")
                break

    # ===== 頻道事件監聽 =====

    @commands.Cog.listener()
    async def on_guild_channel_delete(self, channel: discord.TextChannel):
        """監聽頻道刪除事件 - 增強版"""
        if not is_ticket_channel(channel):
            return

        try:
            # 檢查是否為票券頻道
            ticket_info = await self.dao.get_ticket_by_channel(channel.id)
            if ticket_info and ticket_info["status"] == "open":
                # 自動關閉票券記錄
                ticket_id = self._get_ticket_id(ticket_info)
                if ticket_id:
                    await self.dao.close_ticket(ticket_id, "system", "頻道被刪除")

        except Exception as e:
            logger.error(f"處理頻道刪除事件時發生錯誤: {e}")

    # ===== 成員事件監聽 =====

    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member):
        """監聽成員離開事件 - 增強版"""
        try:
            # 檢查該成員是否有開啟的票券
            tickets, _ = await self.dao.paginate_tickets(
                user_id=str(member.id),
                status="open",
                guild_id=member.guild.id,
                page_size=50,
            )

            if not tickets:
                return

            # 自動關閉該成員的所有開啟票券
            for ticket in tickets:
                ticket_id = ticket.get("ticket_id") or ticket.get("id")
                if not ticket_id:
                    continue
                await self.dao.close_ticket(
                    ticket_id,
                    "system",
                    f"用戶 {member.display_name} 離開伺服器",
                )

                # 嘗試在頻道中通知並延遲刪除
                channel = member.guild.get_channel(ticket["channel_id"])
                if channel:
                    try:
                        embed = discord.Embed(
                            title="👋 用戶離開伺服器",
                            description=f"{member.mention} 已離開伺服器，此票券將自動關閉。\n頻道將在 30 秒後刪除。",
                            color=discord.Color.orange(),
                        )
                        await channel.send(embed=embed)

                        # 延遲刪除頻道
                        await asyncio.sleep(30)
                        await channel.delete(reason=f"用戶 {member.display_name} 離開伺服器")

                    except discord.NotFound:
                        pass  # 頻道已被刪除
                    except discord.Forbidden:
                        logger.warning(f"無權限刪除票券頻道 {channel.name}")

            # 記錄成員離開事件
            await self._log_member_departure(member, tickets)

        except Exception as e:
            logger.error(f"處理成員離開事件時發生錯誤: {e}")

    async def _log_member_departure(self, member: discord.Member, tickets: List[Dict]):
        """記錄成員離開事件"""
        try:
            settings = await self.dao.get_guild_settings(member.guild.id)
            log_channel_id = settings.get("log_channel_id")

            if not log_channel_id:
                return

            log_channel = member.guild.get_channel(log_channel_id)
            if not log_channel:
                return

            embed = discord.Embed(
                title="👋 成員離開 - 自動關閉票券",
                description=f"{member.mention} ({member.display_name}) 離開伺服器",
                color=discord.Color.orange(),
            )

            ticket_list = []
            for ticket in tickets:
                priority_emoji = get_priority_emoji(ticket.get("priority", "medium"))
                ticket_list.append(
                    f"{priority_emoji} #{ticket['ticket_id']:04d} - {ticket['type']}"
                )

            embed.add_field(
                name=f"自動關閉的票券 ({len(tickets)} 張)",
                value="\n".join(ticket_list[:10])
                + (f"\n... 還有 {len(tickets)-10} 張" if len(tickets) > 10 else ""),
                inline=False,
            )

            embed.add_field(
                name="離開時間",
                value=f"<t:{int(datetime.now(timezone.utc).timestamp())}:F>",
                inline=True,
            )

            await log_channel.send(embed=embed)

        except Exception as e:
            logger.error(f"記錄成員離開事件時發生錯誤: {e}")

    # ===== 身分組變更監聽 =====

    @commands.Cog.listener()
    async def on_member_update(self, before: discord.Member, after: discord.Member):
        """監聽成員更新事件（身分組變更）- 增強版"""
        # 檢查身分組是否有變更
        if before.roles == after.roles:
            # 檢查狀態變更
            if before.status != after.status:
                await self._handle_status_change(before, after)
            return

        # 處理身分組變更
        await self._handle_role_change(before, after)

    async def _handle_role_change(self, before: discord.Member, after: discord.Member):
        """處理身分組變更"""
        try:
            # 取得設定
            settings = await self.dao.get_guild_settings(after.guild.id)
            support_roles = set(settings.get("support_roles", []))
            sponsor_roles = set(settings.get("sponsor_support_roles", []))
            staff_roles = support_roles | sponsor_roles

            if not staff_roles:
                return

            # 檢查客服權限變更
            before_roles = {role.id for role in before.roles}
            after_roles = {role.id for role in after.roles}

            had_support_role = bool(before_roles & staff_roles)
            has_support_role = bool(after_roles & staff_roles)

            # 如果獲得客服權限
            if not had_support_role and has_support_role:
                await self._handle_staff_role_added(after)

            # 更新在線狀態追蹤
            self._update_staff_status(after, has_support_role)

        except Exception as e:
            logger.error(f"清理用戶快取時發生錯誤: {e}")

    async def _handle_status_change(self, before: discord.Member, after: discord.Member):
        """處理狀態變更"""
        # 只追蹤客服人員
        if after.id not in self.staff_online_status:
            return

        try:
            # 更新狀態記錄
            self.staff_online_status[after.id].update(
                {
                    "is_online": after.status != discord.Status.offline,
                    "last_seen": datetime.now(timezone.utc),
                    "status": str(after.status),
                }
            )

            # 若客服上線，可在此擴充其他通知邏輯

        except Exception as e:
            logger.error(f"處理狀態變更時發生錯誤: {e}")

    async def _handle_staff_role_added(self, member: discord.Member):
        """處理客服身分組被添加"""
        try:
            # 發送歡迎訊息（可選）
            try:
                embed = discord.Embed(
                    title="🎉 歡迎加入客服團隊！",
                    description="你現在可以處理票券了。",
                    color=discord.Color.green(),
                )
                embed.add_field(
                    name="🚀 快速開始",
                    value="• 在票券頻道中回覆即可開始處理\n"
                    "• 需要調整設定請聯繫管理員",
                    inline=False,
                )

                await member.send(embed=embed)

            except discord.Forbidden:
                pass  # 無法發送私訊

            # 更新客服狀態
            self._update_staff_status(member, True)

        except Exception as e:
            logger.error(f"處理客服角色添加時發生錯誤: {e}")

    def _update_staff_status(self, member: discord.Member, is_staff: bool):
        """更新客服狀態追蹤"""
        if is_staff:
            self.staff_online_status[member.id] = {
                "is_online": member.status != discord.Status.offline,
                "last_seen": datetime.now(timezone.utc),
                "status": str(member.status),
            }
        else:
            self.staff_online_status.pop(member.id, None)

    # ===== 背景任務 =====

    @tasks.loop(hours=1)
    async def cleanup_task(self):
        """定期清理任務"""
        try:
            current_time = datetime.now(timezone.utc)

            # 清理過期的訊息快取
            expired_keys = []
            for key, timestamp in self._message_cache.items():
                if isinstance(timestamp, datetime):
                    if (current_time - timestamp).total_seconds() > 3600:  # 1小時
                        expired_keys.append(key)

            for key in expired_keys:
                self._message_cache.pop(key, None)

        except Exception as e:
            logger.error(f"清理任務時發生錯誤: {e}")

    @cleanup_task.before_loop
    async def before_cleanup(self):
        await self.bot.wait_until_ready()

    # ===== 系統事件監聽 =====

    @commands.Cog.listener()
    async def on_ready(self):
        """系統準備完成"""

    # ===== 輔助方法 =====

    def get_staff_online_status(self) -> Dict[int, Dict[str, Any]]:
        """取得客服在線狀態"""
        return self.staff_online_status.copy()


# ===== 票券維護監聽器 =====


class TicketMaintenanceListener(commands.Cog):
    """票券系統維護監聽器"""

    def __init__(self, bot):
        self.bot = bot
        self.dao = TicketDAO()

        # 啟動健康檢查任務
        self.health_check_task.start()

    def cog_unload(self):
        """清理資源"""
        self.health_check_task.cancel()

    @tasks.loop(minutes=15)
    async def health_check_task(self):
        """健康檢查任務"""
        try:
            # 檢查資料庫連接
            await self._check_database_health()

            # 檢查服務狀態
            await self._check_services_health()

        except Exception as e:
            logger.error(f"後台任務監控時發生錯誤: {e}")

    async def _check_database_health(self):
        """檢查資料庫健康狀態"""
        try:
            # 簡單的資料庫連接測試
            async with self.dao.db_pool.connection() as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute("SELECT 1")
                    result = await cursor.fetchone()

                    if not result or result[0] != 1:
                        logger.warning("資料庫連接檢查失敗")

        except Exception as e:
            logger.error(f"檢查資料庫健康時發生錯誤: {e}")

    async def _check_services_health(self):
        """檢查服務健康狀態"""
        try:
            # 檢查資料庫健康狀態
            from potato_bot.db.database_manager import get_database_health

            health_status = await get_database_health()

            if health_status.get("status") != "healthy":
                logger.warning(f"服務健康檢查失敗: {health_status}")

        except Exception as e:
            logger.error(f"檢查服務健康時發生錯誤: {e}")

    @health_check_task.before_loop
    async def before_health_check(self):
        await self.bot.wait_until_ready()


# ===== 註冊系統 =====


async def setup(bot):
    """註冊監聽器"""
    await bot.add_cog(TicketListener(bot))
    await bot.add_cog(TicketMaintenanceListener(bot))


# ===== 匯出 =====

__all__ = [
    "TicketListener",
    "TicketMaintenanceListener",
]
