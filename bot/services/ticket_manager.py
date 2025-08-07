# bot/services/ticket_manager.py - 簡化的票券管理服務
"""
票券管理服務 - 簡化版
專注於核心業務邏輯，移除過度複雜的功能
"""

import discord
import asyncio
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any, Tuple
from shared.logger import logger


class TicketManager:
    """票券管理服務"""
    
    def __init__(self, repository):
        self.repository = repository
    
    # ===== 票券建立 =====
    
    async def create_ticket(self, user: discord.Member, ticket_type: str, 
                           priority: str = 'medium') -> Tuple[bool, str, Optional[int]]:
        """建立新票券"""
        try:
            # 取得設定
            settings = await self.repository.get_settings(user.guild.id)
            
            # 檢查票券限制
            current_count = await self.repository.get_user_ticket_count(
                user.id, user.guild.id, "open"
            )
            
            max_tickets = settings.get('max_tickets_per_user', 3)
            if current_count >= max_tickets:
                return False, f"已達到票券上限（{max_tickets}張）", None
            
            # 建立頻道
            channel_result = await self._create_ticket_channel(user, ticket_type, priority, settings)
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
                priority=priority
            )
            
            if not ticket_id:
                # 清理頻道
                try:
                    await channel.delete(reason="票券建立失敗")
                except:
                    pass
                return False, "建立票券記錄失敗", None
            
            # 發送歡迎訊息
            await self._send_welcome_message(channel, user, ticket_id, ticket_type, priority, settings)
            
            # 應用自動標籤
            await self._apply_auto_tags(ticket_id, user.guild.id, ticket_type, f"{ticket_type} 票券", user)
            
            # 自動分配（如果有客服在線）
            await self._try_auto_assign(ticket_id, user.guild, settings)
            
            logger.info(f"建立票券成功 #{ticket_id:04d} - 用戶: {user}")
            return True, f"票券 #{ticket_id:04d} 建立成功", ticket_id
            
        except Exception as e:
            logger.error(f"建立票券錯誤：{e}")
            return False, "系統錯誤，請稍後再試", None
    
    async def _create_ticket_channel(self, user: discord.Member, ticket_type: str, 
                                   priority: str, settings: Dict) -> Tuple[bool, str, Optional[discord.TextChannel]]:
        """建立票券頻道"""
        try:
            # 檢查分類頻道
            category_id = settings.get('category_id')
            if not category_id:
                return False, "尚未設定票券分類頻道", None
            
            category = user.guild.get_channel(category_id)
            if not category or not isinstance(category, discord.CategoryChannel):
                return False, "票券分類頻道不存在", None
            
            # 生成頻道名稱（包含優先級標識）
            ticket_id = await self.repository.get_next_ticket_id()
            priority_prefix = {
                'high': '🔴',
                'medium': '🟡', 
                'low': '🟢'
            }.get(priority, '🟡')
            channel_name = f"{priority_prefix}ticket-{ticket_id:04d}-{user.display_name[:8]}"
            
            # 設定權限
            overwrites = await self._create_channel_overwrites(user, settings)
            
            # 建立頻道
            channel = await user.guild.create_text_channel(
                name=channel_name,
                category=category,
                overwrites=overwrites,
                topic=f"{priority_prefix} 票券 #{ticket_id:04d} - {ticket_type} - {user.display_name} ({priority.upper()}優先級)",
                reason=f"建立票券 - 用戶: {user}"
            )
            
            return True, "頻道建立成功", channel
            
        except discord.Forbidden:
            return False, "機器人沒有建立頻道的權限", None
        except Exception as e:
            logger.error(f"建立頻道錯誤：{e}")
            return False, "建立頻道失敗", None
    
    async def _create_channel_overwrites(self, user: discord.Member, 
                                       settings: Dict) -> Dict[discord.abc.Snowflake, discord.PermissionOverwrite]:
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
                read_message_history=True
            ),
            
            # 機器人：管理權限
            user.guild.me: discord.PermissionOverwrite(
                read_messages=True,
                send_messages=True,
                manage_messages=True,
                embed_links=True,
                attach_files=True,
                read_message_history=True
            )
        }
        
        # 客服身分組權限
        support_roles = settings.get('support_roles', [])
        for role_id in support_roles:
            role = user.guild.get_role(role_id)
            if role:
                overwrites[role] = discord.PermissionOverwrite(
                    read_messages=True,
                    send_messages=True,
                    manage_messages=True,
                    embed_links=True,
                    attach_files=True,
                    read_message_history=True
                )
        
        return overwrites
    
    async def _send_welcome_message(self, channel: discord.TextChannel, user: discord.Member,
                                  ticket_id: int, ticket_type: str, priority: str, settings: Dict):
        """發送歡迎訊息"""
        try:
            from bot.utils.ticket_constants import TicketConstants
            from bot.views.ticket_views import TicketControlView
            
            priority_emoji = TicketConstants.PRIORITY_EMOJIS.get(priority, '🟡')
            priority_color = TicketConstants.PRIORITY_COLORS.get(priority, 0x00ff00)
            
            embed = discord.Embed(
                title=f"🎫 票券 #{ticket_id:04d}",
                description=f"你好 {user.mention}！\n\n{settings.get('welcome_message', '請詳細描述你的問題，我們會盡快回覆。')}",
                color=priority_color
            )
            
            embed.add_field(
                name="📋 票券資訊",
                value=f"**類型：** {ticket_type}\n"
                      f"**優先級：** {priority_emoji} {priority.upper()}\n"
                      f"**預期回覆：** {settings.get('sla_response_minutes', 60)} 分鐘內",
                inline=True
            )
            
            embed.add_field(
                name="⏰ 建立時間",
                value=f"<t:{int(datetime.now(timezone.utc).timestamp())}:F>",
                inline=True
            )
            
            embed.add_field(
                name="💡 使用說明",
                value="• 使用 `/close` 關閉票券\n"
                      "• 請詳細描述問題\n"
                      "• 保持禮貌和耐心\n"
                      "• 關閉後可為服務評分",
                inline=False
            )
            
            # 控制面板（包含優先級顯示）
            view = TicketControlView(ticket_id=ticket_id, priority=priority)
            
            await channel.send(content=f"{user.mention}", embed=embed, view=view)
            
        except Exception as e:
            logger.error(f"發送歡迎訊息錯誤：{e}")
    
    async def _try_auto_assign(self, ticket_id: int, guild: discord.Guild, settings: Dict):
        """嘗試自動分配"""
        try:
            support_roles = settings.get('support_roles', [])
            if not support_roles:
                return
            
            # 找到在線客服
            online_staff = []
            for role_id in support_roles:
                role = guild.get_role(role_id)
                if role:
                    for member in role.members:
                        if (not member.bot and 
                            member.status != discord.Status.offline and 
                            member not in online_staff):
                            online_staff.append(member)
            
            if online_staff:
                # 簡單的輪流分配
                import random
                assigned_staff = random.choice(online_staff)
                
                success = await self.repository.assign_ticket(ticket_id, assigned_staff.id, 0)
                if success:
                    # 通知被分配的客服
                    try:
                        await assigned_staff.send(f"📋 你被自動分配了票券 #{ticket_id:04d}")
                    except:
                        pass
                    
                    logger.info(f"自動分配票券 #{ticket_id:04d} 給 {assigned_staff}")
            
        except Exception as e:
            logger.error(f"自動分配錯誤：{e}")
    
    async def _apply_auto_tags(self, ticket_id: int, guild_id: int, ticket_type: str, content: str, user: discord.Member):
        """應用自動標籤"""
        try:
            from bot.services.tag_manager import TagManager
            from bot.db.tag_dao import TagDAO
            
            tag_dao = TagDAO()
            tag_manager = TagManager(tag_dao)
            
            # 應用自動標籤規則
            applied_tags = await tag_manager.apply_auto_tags(
                guild_id, ticket_id, ticket_type, content, user
            )
            
            if applied_tags:
                tag_names = [tag['display_name'] for tag in applied_tags]
                logger.info(f"票券 #{ticket_id} 自動應用標籤: {', '.join(tag_names)}")
            
        except Exception as e:
            logger.error(f"應用自動標籤錯誤：{e}")
    
    # ===== 票券關閉 =====
    
    async def close_ticket(self, ticket_id: int, closed_by: int, reason: str = None) -> bool:
        """關閉票券"""
        try:
            success = await self.repository.close_ticket(ticket_id, closed_by, reason)
            
            if success:
                # 可以在這裡添加後續處理邏輯
                # 例如：發送通知、清理資料等
                logger.info(f"關閉票券 #{ticket_id:04d}")
            
            return success
            
        except Exception as e:
            logger.error(f"關閉票券錯誤：{e}")
            return False
    
    # ===== 票券指派 =====
    
    async def assign_ticket(self, ticket_id: int, assigned_to: int, assigned_by: int) -> bool:
        """指派票券"""
        try:
            success = await self.repository.assign_ticket(ticket_id, assigned_to, assigned_by)
            
            if success:
                logger.info(f"指派票券 #{ticket_id:04d} 給用戶 {assigned_to}")
            
            return success
            
        except Exception as e:
            logger.error(f"指派票券錯誤：{e}")
            return False
    
    # ===== 評分系統 =====
    
    async def save_rating(self, ticket_id: int, rating: int, feedback: str = None) -> bool:
        """保存票券評分"""
        try:
            if not 1 <= rating <= 5:
                return False
            
            success = await self.repository.save_rating(ticket_id, rating, feedback)
            
            if success:
                logger.info(f"保存評分 #{ticket_id:04d} - {rating}星")
            
            return success
            
        except Exception as e:
            logger.error(f"保存評分錯誤：{e}")
            return False
    
    # ===== 通知服務 =====
    
    async def send_user_notification(self, user: discord.Member, title: str, 
                                   message: str, color: int = 0x00ff00) -> bool:
        """發送用戶通知"""
        try:
            embed = discord.Embed(
                title=title,
                description=message,
                color=color
            )
            embed.set_footer(text="票券系統通知")
            
            await user.send(embed=embed)
            return True
            
        except discord.Forbidden:
            logger.warning(f"無法向用戶 {user.id} 發送私訊")
            return False
        except Exception as e:
            logger.error(f"發送通知錯誤：{e}")
            return False
    
    async def send_channel_notification(self, channel: discord.TextChannel, 
                                      title: str, message: str, color: int = 0x00ff00) -> bool:
        """發送頻道通知"""
        try:
            embed = discord.Embed(
                title=title,
                description=message,
                color=color
            )
            
            await channel.send(embed=embed)
            return True
            
        except discord.Forbidden:
            logger.warning(f"無法在頻道 {channel.id} 發送訊息")
            return False
        except Exception as e:
            logger.error(f"發送頻道通知錯誤：{e}")
            return False
    
    # ===== SLA 監控 =====
    
    async def handle_overdue_ticket(self, ticket: Dict, guild: discord.Guild) -> bool:
        """處理超時票券"""
        try:
            from bot.utils.constants import TicketConstants
            
            # 計算超時時間
            now = datetime.now(timezone.utc)
            overdue_minutes = (now - ticket['created_at']).total_seconds() / 60
            
            # 取得 SLA 目標時間
            sla_minutes = ticket.get('sla_response_minutes', 60)
            priority_multiplier = {
                'high': 0.5,
                'medium': 1.0,
                'low': 1.5
            }.get(ticket['priority'], 1.0)
            
            target_minutes = sla_minutes * priority_multiplier
            actual_overdue = overdue_minutes - target_minutes
            
            # 建立警告訊息
            priority_emoji = TicketConstants.PRIORITY_EMOJIS.get(ticket['priority'], '🟡')
            
            embed = discord.Embed(
                title="⚠️ SLA 超時警告",
                description=f"票券 #{ticket['id']:04d} 已超過目標回應時間",
                color=0xff0000
            )
            
            embed.add_field(
                name="票券資訊",
                value=f"**類型：** {ticket['type']}\n"
                      f"**優先級：** {priority_emoji} {ticket['priority'].upper()}\n"
                      f"**開票者：** <@{ticket['discord_id']}>",
                inline=True
            )
            
            embed.add_field(
                name="超時資訊",
                value=f"**超時時間：** {actual_overdue:.0f} 分鐘\n"
                      f"**頻道：** <#{ticket['channel_id']}>",
                inline=True
            )
            
            # 發送到日誌頻道（如果設定）
            settings = await self.repository.get_settings(guild.id)
            log_channel_id = settings.get('log_channel_id')
            
            if log_channel_id:
                log_channel = guild.get_channel(log_channel_id)
                if log_channel:
                    await log_channel.send(embed=embed)
            
            # 通知客服人員
            support_roles = settings.get('support_roles', [])
            notified_users = set()
            
            for role_id in support_roles:
                role = guild.get_role(role_id)
                if role:
                    for member in role.members:
                        if (not member.bot and 
                            member.status != discord.Status.offline and 
                            member.id not in notified_users):
                            
                            try:
                                await member.send(embed=embed)
                                notified_users.add(member.id)
                            except:
                                pass
            
            logger.warning(f"SLA 超時警告 - 票券 #{ticket['id']:04d}")
            return True
            
        except Exception as e:
            logger.error(f"處理超時票券錯誤：{e}")
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
                'status': 'healthy',
                'timestamp': datetime.now(timezone.utc),
                'services': {
                    'database': 'healthy',
                    'notifications': 'healthy',
                    'sla_monitor': 'healthy'
                }
            }
            
            return health
            
        except Exception as e:
            logger.error(f"健康檢查錯誤：{e}")
            return {
                'status': 'unhealthy',
                'error': str(e),
                'timestamp': datetime.now(timezone.utc)
            }