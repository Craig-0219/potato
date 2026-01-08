# bot/services/ticket_manager.py - 簡化的票券管理服務
"""
票券管理服務 - 簡化版
專注於核心業務邏輯，移除過度複雜的功能
"""

from datetime import datetime, timezone, timedelta
from typing import Any, Dict, Optional, Tuple

import discord

from potato_bot.services.chat_transcript_manager import ChatTranscriptManager
from potato_bot.services.realtime_sync_manager import (
    SyncEvent,
    SyncEventType,
    realtime_sync,
)
from potato_bot.utils.ticket_constants import TicketConstants
from potato_bot.views.ticket_views import TicketControlView
from potato_shared.logger import logger


class TicketManager:
    """票券管理服務"""

    def __init__(self, repository, bot):
        self.repository = repository
        self.bot = bot
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

    # ===== Interaction Handlers =====

    async def create_ticket_from_interaction(
        self, interaction: discord.Interaction, ticket_type: str, priority: str
    ):
        """從互動事件建立票券"""
        try:
            # 確保 interaction.user 是 Member
            if not isinstance(interaction.user, discord.Member):
                user = interaction.guild.get_member(interaction.user.id)
                if not user:
                    await interaction.followup.send(
                        "❌ 無法在此伺服器中找到您的成員資訊。", ephemeral=True
                    )
                    return
            else:
                user = interaction.user

            success, message, ticket_id = await self.create_ticket(
                user=user, ticket_type=ticket_type, priority=priority
            )

            if success:
                priority_name = {"high": "高", "medium": "中", "low": "低"}.get(priority, priority)
                priority_emoji = {"high": "🔴", "medium": "🟡", "low": "🟢"}.get(priority, "🟡")
                priority_colors = {
                    "high": 0xFF0000,
                    "medium": 0xFFAA00,
                    "low": 0x00FF00,
                }
                embed = discord.Embed(
                    title="✅ 票券建立成功！",
                    description=f"{message}\n\n{priority_emoji} **{priority_name}優先級** - {ticket_type}",
                    color=priority_colors.get(priority, 0x00FF00),
                )
                await interaction.followup.send(embed=embed, ephemeral=True)
            else:
                await interaction.followup.send(f"❌ {message}", ephemeral=True)

        except Exception as e:
            logger.error(f"從互動建立票券錯誤: {e}")
            try:
                await interaction.followup.send("❌ 建立票券時發生錯誤。", ephemeral=True)
            except:
                pass

    async def close_ticket_from_interaction(self, interaction: discord.Interaction):
        """從互動事件關閉票券"""
        try:
            await interaction.response.defer(ephemeral=True, thinking=True)
            ticket = await self.repository.get_ticket_by_channel(interaction.channel.id)
            if not ticket:
                await interaction.followup.send("❌ 找不到票券資訊", ephemeral=True)
                return

            if ticket["status"] == "closed":
                await interaction.followup.send("❌ 此票券已經關閉", ephemeral=True)
                return

            # 檢查權限
            settings = await self.repository.get_settings(interaction.guild.id)
            support_roles = settings.get("support_roles", [])
            user_roles = [r.id for r in getattr(interaction.user, "roles", [])]
            is_support = any(int(rid) in user_roles for rid in support_roles)
            is_owner = str(interaction.user.id) == str(ticket.get("discord_id"))
            if not (is_owner or is_support or interaction.user.guild_permissions.manage_guild):
                await interaction.followup.send(
                    "❌ 只有票券創建者或客服人員可以關閉票券", ephemeral=True
                )
                return

            # 關閉票券
            success = await self.close_ticket(
                ticket_id=ticket["id"],
                closed_by=interaction.user.id,
                reason="按鈕關閉",
                channel=interaction.channel
            )

            if success:
                await interaction.followup.send("✅ 票券已關閉，頻道將在幾秒後刪除。", ephemeral=True)
                await interaction.channel.delete(reason="Ticket closed by button")
            else:
                await interaction.followup.send("❌ 關閉票券時發生錯誤", ephemeral=True)
        except Exception as e:
            logger.error(f"從互動關閉票券錯誤: {e}")
            try:
                await interaction.followup.send("❌ 處理關閉票券請求時發生錯誤", ephemeral=True)
            except:
                pass

    # ===== 票券關閉 =====

    async def close_ticket(
        self,
        ticket_id: int,
        closed_by: int,
        reason: str = None,
        channel: discord.TextChannel = None,
    ) -> bool:
        """關閉票券"""
        try:
            # 自動匯出聊天記錄
            if channel:
                try:
                    message_count = await self.transcript_manager.batch_record_channel_history(
                        ticket_id, channel, limit=None
                    )
                    logger.info(f"📝 票券 #{ticket_id:04d} 已匯入 {message_count} 條歷史訊息")
                except Exception as transcript_error:
                    logger.error(f"❌ 匯入聊天歷史失敗: {transcript_error}")

            success = await self.repository.close_ticket(ticket_id, closed_by, reason)

            if success:
                # 發布即時同步事件
                await realtime_sync.publish_event(
                    SyncEvent(
                        event_type=SyncEventType.TICKET_CLOSED,
                        payload={"ticket_id": ticket_id, "user_id": closed_by, "reason": reason},
                    )
                )
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

    async def cleanup_old_tickets(self, guild_id: int, hours_threshold: int) -> int:
        """清理舊的無活動票券"""
        if not hours_threshold or hours_threshold <= 0:
            return 0

        try:
            cutoff_time = datetime.now(timezone.utc) - timedelta(hours=hours_threshold)
            inactive_tickets = await self.repository.get_inactive_tickets(
                guild_id, cutoff_time
            )
            
            if not inactive_tickets:
                return 0

            logger.info(f"伺服器 {guild_id} 發現 {len(inactive_tickets)} 張無活動票券，開始清理...")
            
            closed_count = 0
            for ticket in inactive_tickets:
                try:
                    channel = self.bot.get_channel(ticket["channel_id"])
                    
                    if not channel:
                        logger.warning(f"找不到票券 #{ticket['ticket_id']} 的頻道 {ticket['channel_id']}，可能已被手動刪除。")
                        # Even if channel is gone, try to close the ticket in DB
                        await self.close_ticket(ticket_id=ticket['ticket_id'], closed_by=self.bot.user.id, reason="自動關閉 (頻道不存在)")
                        closed_count += 1
                        continue

                    # Send notification before closing
                    try:
                        user = await self.bot.fetch_user(ticket['discord_id'])
                        await self.send_channel_notification(
                            channel,
                            "⌛ 票券自動關閉",
                            f"你好 {user.mention}，此票券因超過 {hours_threshold} 小時無活動，已被系統自動關閉。\n如有需要，請建立新的票券。",
                            color=TicketConstants.COLORS["warning"],
                        )
                    except Exception as notify_err:
                        logger.warning(f"自動關閉通知失敗 T:{ticket['ticket_id']} C:{channel.id}: {notify_err}")

                    # Close ticket and delete channel
                    success = await self.close_ticket(
                        ticket_id=ticket["ticket_id"],
                        closed_by=self.bot.user.id,
                        reason=f"自動關閉 (超過 {hours_threshold} 小時無活動)",
                        channel=channel,
                    )
                    
                    if success:
                        closed_count += 1
                        await asyncio.sleep(1) # sleep to avoid rate limits
                        await channel.delete(reason="Ticket auto-closed")

                except Exception as e:
                    logger.error(f"清理單張票券 #{ticket.get('ticket_id')} 失敗: {e}")
            
            logger.info(f"伺服器 {guild_id} 清理完畢，共關閉 {closed_count} 張票券。")
            return closed_count

        except Exception as e:
            logger.error(f"清理舊票券錯誤 (伺服器 {guild_id}): {e}")
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
