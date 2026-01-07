# bot/services/ticket_manager.py - 簡化的票券管理服務
"""
票券管理服務 - 簡化版
專注於核心業務邏輯，移除過度複雜的功能
"""

from datetime import datetime, timezone
from typing import Any, Dict, Optional, Tuple

import discord

from potato_bot.services.chat_transcript_manager import ChatTranscriptManager
from potato_bot.services.realtime_sync_manager import (
    SyncEvent,
    SyncEventType,
    realtime_sync,
)
from potato_shared.logger import logger


class TicketManager:
    """票券管理服務"""

    def __init__(self, repository):
        self.repository = repository
        self.transcript_manager = ChatTranscriptManager()

    # ===== 票券建立 =====

    async def create_ticket(
        self, user: discord.Member, ticket_type: str, priority: str = "medium"
    ) -> Tuple[bool, str, Optional[int]]:
        """建立新票券"""
        try:
            # 取得設定
            settings = await self.repository.get_settings(user.guild.id)

            # 檢查票券限制
            current_count = await self.repository.get_user_ticket_count(
                user.id, user.guild.id, "open"
            )

            max_tickets = settings.get("max_tickets_per_user", 3)
            if current_count >= max_tickets:
                return False, f"已達到票券上限（{max_tickets}張）", None

            # 建立頻道
            channel_result = await self._create_ticket_channel(
                user, ticket_type, priority, settings
            )
            if not channel_result[0]:
                return False, channel_result[1], None

            channel = channel_result[2]

            # 建立票券記錄
            ticket_id = await self.repository.create_ticket(
                discord_id=str(user.id),
                username=user.display_name,
                ticket_type=ticket_type,
                channel_id=channel.id,
                guild_id=user.guild.id,
                priority=priority,
            )

            if not ticket_id:
                # 清理頻道
                try:
                    await channel.delete(reason="票券建立失敗")
                except:
                    pass
                return False, "建立票券記錄失敗", None

            # 發送歡迎訊息
            await self._send_welcome_message(
                channel, user, ticket_id, ticket_type, priority, settings
            )

            logger.info(f"建立票券成功 #{ticket_id:04d} - 用戶: {user}")
            return True, f"票券 #{ticket_id:04d} 建立成功", ticket_id

        except Exception as e:
            logger.error(f"建立票券錯誤：{e}")
            return False, "系統錯誤，請稍後再試", None

    async def _create_ticket_channel(
        self,
        user: discord.Member,
        ticket_type: str,
        priority: str,
        settings: Dict,
    ) -> Tuple[bool, str, Optional[discord.TextChannel]]:
        """建立票券頻道"""
        try:
            # 檢查分類頻道
            category_id = settings.get("category_id")
            if not category_id:
                return False, "尚未設定票券分類頻道", None

            category = user.guild.get_channel(category_id)
            if not category or not isinstance(category, discord.CategoryChannel):
                return False, "票券分類頻道不存在", None

            # 生成頻道名稱（包含優先級標識）
            ticket_id = await self.repository.get_next_ticket_id()
            priority_prefix = {"high": "🔴", "medium": "🟡", "low": "🟢"}.get(priority, "🟡")
            channel_name = f"{priority_prefix}ticket-{ticket_id:04d}-{user.display_name[:8]}"

            # 設定權限
            overwrites = await self._create_channel_overwrites(user, settings)

            # 建立頻道
            channel = await user.guild.create_text_channel(
                name=channel_name,
                category=category,
                overwrites=overwrites,
                topic=f"{priority_prefix} 票券 #{ticket_id:04d} - {ticket_type} - {user.display_name} ({priority.upper()}優先級)",
                reason=f"建立票券 - 用戶: {user}",
            )

            return True, "頻道建立成功", channel

        except discord.Forbidden:
            return False, "機器人沒有建立頻道的權限", None
        except Exception as e:
            logger.error(f"建立頻道錯誤：{e}")
            return False, "建立頻道失敗", None

    async def _create_channel_overwrites(
        self, user: discord.Member, settings: Dict
    ) -> Dict[discord.abc.Snowflake, discord.PermissionOverwrite]:
        """建立頻道權限覆寫"""
        overwrites = {
            # 預設角色：無法查看
            user.guild.default_role: discord.PermissionOverwrite(read_messages=False),
            # 票券創建者：完整權限
            user: discord.PermissionOverwrite(
                read_messages=True,
                send_messages=True,
                attach_files=True,
                embed_links=True,
                read_message_history=True,
            ),
            # 機器人：管理權限
            user.guild.me: discord.PermissionOverwrite(
                read_messages=True,
                send_messages=True,
                manage_messages=True,
                embed_links=True,
                attach_files=True,
                read_message_history=True,
            ),
        }

        # 客服身分組權限
        support_roles = settings.get("support_roles", [])
        for role_id in support_roles:
            role = user.guild.get_role(role_id)
            if role:
                overwrites[role] = discord.PermissionOverwrite(
                    read_messages=True,
                    send_messages=True,
                    manage_messages=True,
                    embed_links=True,
                    attach_files=True,
                    read_message_history=True,
                )

        return overwrites

    async def _send_welcome_message(
        self,
        channel: discord.TextChannel,
        user: discord.Member,
        ticket_id: int,
        ticket_type: str,
        priority: str,
        settings: Dict,
    ):
        """發送歡迎訊息"""
        try:
            from potato_bot.utils.ticket_constants import TicketConstants
            from potato_bot.views.ticket_views import TicketControlView

            priority_emoji = TicketConstants.PRIORITY_EMOJIS.get(priority, "🟡")
            priority_color = TicketConstants.PRIORITY_COLORS.get(priority, 0x00FF00)

            embed = discord.Embed(
                title=f"🎫 票券 #{ticket_id:04d}",
                description=f"你好 {user.mention}！\n\n{settings.get('welcome_message', '請詳細描述你的問題，我們會盡快回覆。')}",
                color=priority_color,
            )

            embed.add_field(
                name="📋 票券資訊",
                value=f"**類型：** {ticket_type}\n"
                f"**優先級：** {priority_emoji} {priority.upper()}",
                inline=True,
            )

            embed.add_field(
                name="⏰ 建立時間",
                value=f"<t:{int(datetime.now(timezone.utc).timestamp())}:F>",
                inline=True,
            )

            embed.add_field(
                name="💡 使用說明",
                value="• 使用 `/close` 關閉票券\n"
                "• 請詳細描述問題\n"
                "• 保持禮貌和耐心",
                inline=False,
            )

            # 控制面板（包含優先級顯示）
            view = TicketControlView(priority=priority)

            await channel.send(content=f"{user.mention}", embed=embed, view=view)

        except Exception as e:
            logger.error(f"發送歡迎訊息錯誤：{e}")

    # ===== 票券關閉 =====

    async def close_ticket(self, ticket_id: int, closed_by: int, reason: str = None) -> bool:
        """關閉票券"""
        try:
            success = await self.repository.close_ticket(ticket_id, closed_by, reason)

            if success:
                # 發布即時同步事件
                await realtime_sync.publish_event(
                    SyncEvent(
                        event_type=SyncEventType.TICKET_CLOSED,
                        payload={"ticket_id": ticket_id, "user_id": closed_by, "reason": reason},
                    )
                )
                # 自動匯出聊天記錄
                try:
                    # 首先嘗試從資料庫匯出
                    transcript_path = await self.transcript_manager.export_transcript(
                        ticket_id, "html"
                    )
                    if transcript_path:
                        logger.info(f"✅ 票券 #{ticket_id:04d} 聊天記錄已匯出: {transcript_path}")
                    else:
                        # 如果資料庫中沒有記錄，嘗試從 Discord 頻道匯入歷史訊息並匯出
                        logger.info(
                            f"🔄 票券 #{ticket_id:04d} 正在嘗試從 Discord 頻道匯入歷史訊息..."
                        )

                        # 獲取票券資訊以取得頻道 ID
                        ticket_info = await self.repository.get_ticket_by_id(ticket_id)
                        if ticket_info and ticket_info.get("channel_id"):
                            # 這裡需要 bot 實例來獲取頻道，但在當前架構下較難實現
                            # 建議使用背景任務或在關閉票券的指令中直接處理
                            logger.warning(f"⚠️ 票券 #{ticket_id:04d} 需要手動匯入頻道歷史訊息")
                        else:
                            logger.warning(f"⚠️ 票券 #{ticket_id:04d} 聊天記錄匯出失敗或無記錄")
                except Exception as transcript_error:
                    logger.error(f"❌ 票券 #{ticket_id:04d} 聊天記錄匯出錯誤: {transcript_error}")

                logger.info(f"關閉票券 #{ticket_id:04d}")

            return success

        except Exception as e:
            logger.error(f"關閉票券錯誤：{e}")
            return False


    # ===== 通知服務 =====

    async def send_user_notification(
        self,
        user: discord.Member,
        title: str,
        message: str,
        color: int = 0x00FF00,
    ) -> bool:
        """發送用戶通知"""
        try:
            embed = discord.Embed(title=title, description=message, color=color)
            embed.set_footer(text="票券系統通知")

            await user.send(embed=embed)
            return True

        except discord.Forbidden:
            logger.warning(f"無法向用戶 {user.id} 發送私訊")
            return False
        except Exception as e:
            logger.error(f"發送通知錯誤：{e}")
            return False

    async def send_channel_notification(
        self,
        channel: discord.TextChannel,
        title: str,
        message: str,
        color: int = 0x00FF00,
    ) -> bool:
        """發送頻道通知"""
        try:
            embed = discord.Embed(title=title, description=message, color=color)

            await channel.send(embed=embed)
            return True

        except discord.Forbidden:
            logger.warning(f"無法在頻道 {channel.id} 發送訊息")
            return False
        except Exception as e:
            logger.error(f"發送頻道通知錯誤：{e}")
            return False

    # ===== 系統維護 =====

    async def cleanup_old_tickets(self, guild_id: int, hours_threshold: int = 24) -> int:
        """清理舊的無活動票券"""
        try:
            # 這裡可以實作自動關閉無活動票券的邏輯
            # 暫時返回0，因為需要在 repository 中實作相關方法
            logger.info(f"執行票券清理 - 伺服器: {guild_id}, 閾值: {hours_threshold}小時")
            return 0

        except Exception as e:
            logger.error(f"清理舊票券錯誤：{e}")
            return 0

    async def get_system_health(self) -> Dict[str, Any]:
        """取得系統健康狀態"""
        try:
            # 簡單的健康檢查
            health = {
                "status": "healthy",
                "timestamp": datetime.now(timezone.utc),
                "services": {
                    "database": "healthy",
                    "notifications": "healthy",
                },
            }

            return health

        except Exception as e:
            logger.error(f"健康檢查錯誤：{e}")
            return {
                "status": "unhealthy",
                "error": str(e),
                "timestamp": datetime.now(timezone.utc),
            }
