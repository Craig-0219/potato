# bot/listeners/ticket_listener.py - 票券系統事件監聽器完整版

import discord
from discord.ext import commands, tasks
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Any
import asyncio
import re
import aiomysql

from bot.db.ticket_dao import TicketDAO
from bot.services.ticket_manager import TicketManager
from bot.services.chat_transcript_manager import ChatTranscriptManager
from bot.services.realtime_sync_manager import realtime_sync, SyncEvent, SyncEventType
from bot.utils.ticket_utils import is_ticket_channel, TicketPermissionChecker
from bot.utils.ticket_constants import get_priority_emoji, ERROR_MESSAGES
from shared.logger import logger
from bot.utils.helper import format_duration


class TicketListener(commands.Cog):
    """票券系統事件監聽器 - 完整版"""

    def __init__(
        self,
        bot,
        auto_reply_service: Optional[Any] = None,
        sla_service: Optional[Any] = None,
        notification_service: Optional[Any] = None,
        assignment_service: Optional[Any] = None,
    ):
        self.bot = bot
        self.dao = TicketDAO()
        self.manager = TicketManager(self.dao)
        self.transcript_manager = ChatTranscriptManager()

        # 可選服務
        self.auto_reply_service = auto_reply_service or getattr(bot, "auto_reply_service", None)
        self.sla_service = sla_service or getattr(bot, "sla_service", None)
        self.notification_service = notification_service or getattr(bot, "notification_service", None)
        self.assignment_service = assignment_service or getattr(bot, "assignment_service", None)

        # 狀態追蹤
        self.user_activity = {}  # 追蹤用戶活動
        self.staff_online_status = {}  # 追蹤客服在線狀態

        # 快取和限流
        self._message_cache = {}
        self._rate_limits = {}

        # 啟動背景任務
        self.cleanup_task.start()
        self.activity_tracker.start()

    def cog_unload(self):
        """清理資源"""
        self.cleanup_task.cancel()
        self.activity_tracker.cancel()
        
        # 停止服務
        #asyncio.create_task(self.service_coordinator.stop_services())

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
            if not ticket_info or ticket_info['status'] != 'open':
                return
            
            # 記錄聊天訊息到資料庫
            await self.transcript_manager.record_message(ticket_info['ticket_id'], message)
            
            # 發布訊息接收事件
            await realtime_sync.publish_event(SyncEvent(
                event_type=SyncEventType.MESSAGE_RECEIVED,
                ticket_id=ticket_info['ticket_id'],
                user_id=message.author.id,
                guild_id=message.guild.id,
                data={'content': message.content[:100], 'author': message.author.display_name}
            ))
            
            # 更新票券活動時間
            await self.dao.update_last_activity(ticket_info['ticket_id'])
            
            # 記錄用戶活動
            self._record_user_activity(message.author.id, message.guild.id)
            
            # 處理不同類型的訊息
            if str(message.author.id) == ticket_info['discord_id']:
                await self._handle_user_message(message, ticket_info)
            else:
                await self._handle_staff_message(message, ticket_info)
            
            # 分析訊息內容（情感分析、關鍵字檢測等）
            await self._analyze_message_content(message, ticket_info)
            
        except Exception as e:
            logger.debug(f"[TicketListener] on_message 錯誤：{e}")

    async def _handle_user_message(self, message: discord.Message, ticket_info: Dict):
        """處理用戶訊息 - 增強版"""
        try:
            # 檢查是否需要觸發自動回覆
            if (
                self.auto_reply_service
                and await self._should_trigger_auto_reply(message, ticket_info)
            ):
                auto_reply_triggered = await self.auto_reply_service.process_message(
                    message, ticket_info
                )

                if auto_reply_triggered:
                    logger.debug(
                        f"[TicketListener] 票券 #{ticket_info['ticket_id']:04d} 觸發自動回覆"
                    )
            
            # 檢查是否包含緊急關鍵字
            await self._check_urgent_keywords(message, ticket_info)
            
            # 檢查是否需要升級優先級
            await self._check_priority_escalation(message, ticket_info)
            
        except Exception as e:
            logger.debug(f"[TicketListener] 處理用戶訊息錯誤：{e}")

    async def _handle_staff_message(self, message: discord.Message, ticket_info: Dict):
        """處理客服訊息 - 增強版"""
        try:
            # 取得伺服器設定
            settings = await self.dao.get_guild_settings(message.guild.id)
            
            # 檢查是否為客服人員
            if not TicketPermissionChecker.is_support_staff(message.author, settings.get('support_roles', [])):
                return
            
            # 記錄首次回應（SLA 監控）
            if (
                self.sla_service
                and not await self.dao.has_staff_response(ticket_info['ticket_id'])
            ):
                await self.sla_service.record_first_response(
                    ticket_info['ticket_id'], message.author.id
                )

                # 發送 SLA 達標通知
                await self._send_sla_compliance_notification(
                    message, ticket_info, settings
                )
            
            # 自動指派票券（如果尚未指派）
            if not ticket_info.get('assigned_to'):
                await self._auto_assign_responding_staff(message, ticket_info)
            
            # 檢查是否使用了模板回覆
            await self._detect_template_usage(message, ticket_info)
            
        except Exception as e:
            logger.debug(f"[TicketListener] 處理客服訊息錯誤：{e}")

    async def _should_trigger_auto_reply(self, message: discord.Message, ticket_info: Dict) -> bool:
        """檢查是否應該觸發自動回覆"""
        # 避免過於頻繁的自動回覆
        cache_key = f"auto_reply_{ticket_info['ticket_id']}"
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
        urgent_keywords = [
            "緊急", "urgent", "emergency", "立即", "馬上", "很急", 
            "停機", "故障", "無法使用", "down", "crash", "error"
        ]
        
        content_lower = message.content.lower()
        
        for keyword in urgent_keywords:
            if keyword in content_lower:
                # 如果當前不是高優先級，自動升級
                if ticket_info.get('priority', 'medium') != 'high':
                    await self.dao.update_ticket_priority(
                        ticket_info['ticket_id'], 
                        'high', 
                        message.author.id
                    )
                    
                    # 通知頻道
                    embed = discord.Embed(
                        title="⚡ 優先級自動升級",
                        description=f"檢測到緊急關鍵字「{keyword}」，票券優先級已升級為高優先級。",
                        color=discord.Color.red()
                    )
                    await message.channel.send(embed=embed)
                    
                    logger.debug(f"[TicketListener] 票券 #{ticket_info['ticket_id']:04d} 因關鍵字自動升級優先級")
                
                break

    async def _check_priority_escalation(self, message: discord.Message, ticket_info: Dict):
        """檢查是否需要優先級升級"""
        # 檢查票券年齡
        created_at = ticket_info['created_at']
        # 確保時間戳有時區資訊
        if created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=timezone.utc)
        ticket_age = datetime.now(timezone.utc) - created_at
        
        # 如果票券超過24小時且仍是低優先級，升級到中優先級
        if (ticket_age.total_seconds() > 86400 and  # 24小時
            ticket_info.get('priority', 'medium') == 'low'):
            
            await self.dao.update_ticket_priority(
                ticket_info['ticket_id'], 
                'medium', 
                'system'
            )
            
            embed = discord.Embed(
                title="📈 優先級自動升級",
                description="票券已超過24小時，優先級自動升級為中優先級。",
                color=discord.Color.orange()
            )
            await message.channel.send(embed=embed)

    async def _send_sla_compliance_notification(self, message: discord.Message, 
                                              ticket_info: Dict, settings: Dict):
        """發送 SLA 合規通知"""
        try:
            # 計算回應時間
            created_at = ticket_info['created_at']
            # 確保時間戳有時區資訊
            if created_at.tzinfo is None:
                created_at = created_at.replace(tzinfo=timezone.utc)
            response_time = datetime.now(timezone.utc) - created_at
            response_minutes = response_time.total_seconds() / 60
            
            # 計算目標時間
            from bot.utils.ticket_constants import calculate_sla_time
            target_minutes = calculate_sla_time(
                ticket_info.get('priority', 'medium'),
                settings.get('sla_response_minutes', 60)
            )
            
            # 判斷是否達標
            is_compliant = response_minutes <= target_minutes
            
            if is_compliant:
                embed = discord.Embed(
                    title="✅ SLA 達標",
                    description=f"首次回應時間：{response_minutes:.1f} 分鐘",
                    color=discord.Color.green()
                )
            else:
                embed = discord.Embed(
                    title="⚠️ SLA 超時",
                    description=f"首次回應時間：{response_minutes:.1f} 分鐘\n目標時間：{target_minutes} 分鐘",
                    color=discord.Color.red()
                )
            
            embed.add_field(
                name="回應客服",
                value=message.author.mention,
                inline=True
            )
            
            # 發送到日誌頻道
            log_channel_id = settings.get('log_channel_id')
            if log_channel_id:
                log_channel = message.guild.get_channel(log_channel_id)
                if log_channel:
                    await log_channel.send(embed=embed)
            
        except Exception as e:
            logger.debug(f"[TicketListener] 發送 SLA 通知錯誤：{e}")

    async def _auto_assign_responding_staff(self, message: discord.Message, ticket_info: Dict):
        """自動指派回應的客服"""
        try:
            success = await self.dao.assign_ticket(
                ticket_info['ticket_id'],
                message.author.id,
                'auto_system'
            )
            
            if success:
                embed = discord.Embed(
                    title="👥 自動指派",
                    description=f"{message.author.mention} 已被自動指派為此票券的負責客服。",
                    color=discord.Color.blue()
                )
                await message.channel.send(embed=embed)
                
                logger.debug(f"[TicketListener] 票券 #{ticket_info['ticket_id']:04d} 自動指派給 {message.author.id}")
            
        except Exception as e:
            logger.debug(f"[TicketListener] 自動指派錯誤：{e}")

    async def _detect_template_usage(self, message: discord.Message, ticket_info: Dict):
        """檢測模板使用"""
        # 簡單的模板檢測邏輯
        content = message.content
        
        # 檢查是否包含常見模板標識
        template_indicators = [
            "感謝您的", "根據您的問題", "請提供以下", "我們建議您",
            "根據系統記錄", "經過檢查", "解決方案如下"
        ]
        
        for indicator in template_indicators:
            if indicator in content:
                # 記錄模板使用（可用於統計）
                logger.debug(f"[TicketListener] 檢測到可能的模板使用：{indicator}")
                break

    async def _analyze_message_content(self, message: discord.Message, ticket_info: Dict):
        """分析訊息內容"""
        try:
            content = message.content.lower()
            
            # 情感分析（簡化版）
            positive_words = ["謝謝", "感謝", "滿意", "好的", "解決", "完美", "excellent", "thanks", "perfect"]
            negative_words = ["生氣", "憤怒", "不滿", "糟糕", "問題", "錯誤", "angry", "bad", "terrible", "issue"]
            
            sentiment_score = 0
            for word in positive_words:
                sentiment_score += content.count(word)
            for word in negative_words:
                sentiment_score -= content.count(word)
            
            # 如果情感過於負面，標記需要關注
            if sentiment_score < -2:
                await self._flag_negative_sentiment(message, ticket_info, sentiment_score)
            
            # 檢測重複問題
            await self._detect_repetitive_issues(message, ticket_info)
            
        except Exception as e:
            logger.debug(f"[TicketListener] 內容分析錯誤：{e}")

    async def _flag_negative_sentiment(self, message: discord.Message, ticket_info: Dict, score: int):
        """標記負面情感"""
        try:
            # 取得設定
            settings = await self.dao.get_guild_settings(message.guild.id)
            log_channel_id = settings.get('log_channel_id')
            
            if log_channel_id:
                log_channel = message.guild.get_channel(log_channel_id)
                if log_channel:
                    embed = discord.Embed(
                        title="😟 情感警告",
                        description=f"票券 #{ticket_info['ticket_id']:04d} 檢測到負面情感",
                        color=discord.Color.orange()
                    )
                    embed.add_field(
                        name="詳情",
                        value=f"**用戶：** <@{message.author.id}>\n"
                              f"**情感分數：** {score}\n"
                              f"**頻道：** {message.channel.mention}",
                        inline=False
                    )
                    embed.add_field(
                        name="建議",
                        value="建議主管或資深客服介入處理",
                        inline=False
                    )
                    
                    await log_channel.send(embed=embed)
            
        except Exception as e:
            logger.debug(f"[TicketListener] 標記負面情感錯誤：{e}")

    async def _detect_repetitive_issues(self, message: discord.Message, ticket_info: Dict):
        """檢測重複問題"""
        # 簡化的重複檢測邏輯
        cache_key = f"messages_{ticket_info['ticket_id']}"
        
        if cache_key not in self._message_cache:
            self._message_cache[cache_key] = []
        
        # 保存最近10條訊息
        messages_history = self._message_cache[cache_key]
        messages_history.append(message.content)
        
        if len(messages_history) > 10:
            messages_history.pop(0)
        
        # 檢查重複度
        if len(messages_history) >= 3:
            recent_messages = messages_history[-3:]
            similarity_count = sum(1 for msg in recent_messages if 
                                 self._calculate_similarity(message.content, msg) > 0.7)
            
            if similarity_count >= 2:
                await self._handle_repetitive_issue(message, ticket_info)

    def _calculate_similarity(self, text1: str, text2: str) -> float:
        """計算文字相似度（簡化版）"""
        if not text1 or not text2:
            return 0.0
        
        words1 = set(text1.lower().split())
        words2 = set(text2.lower().split())
        
        if not words1 or not words2:
            return 0.0
        
        intersection = words1.intersection(words2)
        union = words1.union(words2)
        
        return len(intersection) / len(union)

    async def _handle_repetitive_issue(self, message: discord.Message, ticket_info: Dict):
        """處理重複問題"""
        embed = discord.Embed(
            title="🔄 重複問題檢測",
            description="檢測到重複的問題描述，建議：\n"
                       "1. 檢查是否遺漏重要資訊\n"
                       "2. 考慮提供更詳細的解決方案\n"
                       "3. 確認用戶理解了建議的解決步驟",
            color=discord.Color.yellow()
        )
        
        await message.channel.send(embed=embed)

    def _record_user_activity(self, user_id: int, guild_id: int):
        """記錄用戶活動"""
        key = f"{user_id}_{guild_id}"
        self.user_activity[key] = datetime.now(timezone.utc)

    # ===== 頻道事件監聽 =====

    @commands.Cog.listener()
    async def on_guild_channel_delete(self, channel: discord.TextChannel):
        """監聽頻道刪除事件 - 增強版"""
        if not is_ticket_channel(channel):
            return
        
        try:
            # 檢查是否為票券頻道
            ticket_info = await self.dao.get_ticket_by_channel(channel.id)
            if ticket_info and ticket_info['status'] == 'open':
                # 自動關閉票券記錄
                await self.dao.close_ticket(
                    channel.id, 
                    "system", 
                    "頻道被刪除"
                )
                
                logger.debug(f"[TicketListener] 票券 #{ticket_info['ticket_id']:04d} 因頻道刪除而自動關閉")
                
                # 通知用戶
                if self.notification_service:
                    try:
                        user = self.bot.get_user(int(ticket_info['discord_id']))
                        if user:
                            await self.notification_service.send_ticket_notification(
                                user,
                                "ticket_closed",
                                ticket_info,
                                {"close_reason": "票券頻道被刪除"},
                            )
                    except Exception:
                        pass
                
                # 記錄到日誌
                await self._log_channel_deletion(channel, ticket_info)
                
        except Exception as e:
            logger.debug(f"[TicketListener] 處理頻道刪除錯誤：{e}")

    async def _log_channel_deletion(self, channel: discord.TextChannel, ticket_info: Dict):
        """記錄頻道刪除事件"""
        try:
            settings = await self.dao.get_guild_settings(channel.guild.id)
            log_channel_id = settings.get('log_channel_id')
            
            if not log_channel_id:
                return
            
            log_channel = channel.guild.get_channel(log_channel_id)
            if not log_channel:
                return
            
            embed = discord.Embed(
                title="🗑️ 票券頻道被刪除",
                color=discord.Color.orange()
            )
            embed.add_field(name="票券編號", value=f"#{ticket_info['ticket_id']:04d}", inline=True)
            embed.add_field(name="類型", value=ticket_info['type'], inline=True)
            embed.add_field(name="開票者", value=f"<@{ticket_info['discord_id']}>", inline=True)
            embed.add_field(name="頻道名稱", value=channel.name, inline=True)
            embed.add_field(name="刪除時間", value=f"<t:{int(datetime.now(timezone.utc).timestamp())}:F>", inline=True)
            
            # 計算持續時間
            created_at = ticket_info['created_at']
            # 確保時間戳有時區資訊
            if created_at.tzinfo is None:
                created_at = created_at.replace(tzinfo=timezone.utc)
            duration = datetime.now(timezone.utc) - created_at
            from bot.utils.ticket_constants import format_duration
            embed.add_field(name="持續時間", value=format_duration(int(duration.total_seconds())), inline=True)
            
            await log_channel.send(embed=embed)
            
        except Exception as e:
            logger.debug(f"[TicketListener] 記錄頻道刪除錯誤：{e}")

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
                page_size=50
            )
            
            if not tickets:
                return
            
            # 自動關閉該成員的所有開啟票券
            for ticket in tickets:
                await self.dao.close_ticket(
                    ticket['channel_id'],
                    "system",
                    f"用戶 {member.display_name} 離開伺服器"
                )
                
                # 嘗試在頻道中通知並延遲刪除
                channel = member.guild.get_channel(ticket['channel_id'])
                if channel:
                    try:
                        embed = discord.Embed(
                            title="👋 用戶離開伺服器",
                            description=f"{member.mention} 已離開伺服器，此票券將自動關閉。\n頻道將在 30 秒後刪除。",
                            color=discord.Color.orange()
                        )
                        await channel.send(embed=embed)
                        
                        # 延遲刪除頻道
                        await asyncio.sleep(30)
                        await channel.delete(reason=f"用戶 {member.display_name} 離開伺服器")
                        
                    except discord.NotFound:
                        pass  # 頻道已被刪除
                    except discord.Forbidden:
                        logger.debug(f"[TicketListener] 沒有權限刪除頻道：{channel.name}")
            
            # 記錄到日誌
            if tickets:
                await self._log_member_departure(member, tickets)
            
            # 清理用戶相關快取
            self._cleanup_user_cache(member.id, member.guild.id)
                
        except Exception as e:
            logger.debug(f"[TicketListener] 處理成員離開錯誤：{e}")

    async def _log_member_departure(self, member: discord.Member, tickets: List[Dict]):
        """記錄成員離開事件"""
        try:
            settings = await self.dao.get_guild_settings(member.guild.id)
            log_channel_id = settings.get('log_channel_id')
            
            if not log_channel_id:
                return
            
            log_channel = member.guild.get_channel(log_channel_id)
            if not log_channel:
                return
            
            embed = discord.Embed(
                title="👋 成員離開 - 自動關閉票券",
                description=f"{member.mention} ({member.display_name}) 離開伺服器",
                color=discord.Color.orange()
            )
            
            ticket_list = []
            for ticket in tickets:
                priority_emoji = get_priority_emoji(ticket.get('priority', 'medium'))
                ticket_list.append(f"{priority_emoji} #{ticket['ticket_id']:04d} - {ticket['type']}")
            
            embed.add_field(
                name=f"自動關閉的票券 ({len(tickets)} 張)",
                value="\n".join(ticket_list[:10]) + (f"\n... 還有 {len(tickets)-10} 張" if len(tickets) > 10 else ""),
                inline=False
            )
            
            embed.add_field(name="離開時間", value=f"<t:{int(datetime.now(timezone.utc).timestamp())}:F>", inline=True)
            
            await log_channel.send(embed=embed)
            
        except Exception as e:
            logger.debug(f"[TicketListener] 記錄成員離開錯誤：{e}")

    def _cleanup_user_cache(self, user_id: int, guild_id: int):
        """清理用戶相關快取"""
        keys_to_remove = []
        
        # 清理活動記錄
        activity_key = f"{user_id}_{guild_id}"
        self.user_activity.pop(activity_key, None)
        
        # 清理訊息快取
        for key in self._message_cache:
            if str(user_id) in key:
                keys_to_remove.append(key)
        
        for key in keys_to_remove:
            self._message_cache.pop(key, None)

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
            support_roles = set(settings.get('support_roles', []))
            
            if not support_roles:
                return
            
            # 檢查客服權限變更
            before_roles = {role.id for role in before.roles}
            after_roles = {role.id for role in after.roles}
            
            had_support_role = bool(before_roles & support_roles)
            has_support_role = bool(after_roles & support_roles)
            
            # 如果失去客服權限
            if had_support_role and not has_support_role:
                await self._handle_staff_role_removed(after)
            
            # 如果獲得客服權限
            elif not had_support_role and has_support_role:
                await self._handle_staff_role_added(after)
            
            # 更新在線狀態追蹤
            self._update_staff_status(after, has_support_role)
                
        except Exception as e:
            logger.debug(f"[TicketListener] 處理身分組變更錯誤：{e}")

    async def _handle_status_change(self, before: discord.Member, after: discord.Member):
        """處理狀態變更"""
        # 只追蹤客服人員
        if after.id not in self.staff_online_status:
            return
        
        try:
            # 更新狀態記錄
            self.staff_online_status[after.id].update({
                'is_online': after.status != discord.Status.offline,
                'last_seen': datetime.now(timezone.utc),
                'status': str(after.status)
            })
            
            # 如果客服上線且有待分配的票券，發送通知
            if (before.status == discord.Status.offline and 
                after.status != discord.Status.offline):
                
                await self._notify_staff_of_pending_tickets(after)
            
        except Exception as e:
            logger.debug(f"[TicketListener] 處理狀態更新錯誤：{e}")

    async def _handle_staff_role_removed(self, member: discord.Member):
        """處理客服身分組被移除"""
        try:
            # 查找該成員被指派的票券
            tickets, _ = await self.dao.paginate_tickets(
                guild_id=member.guild.id,
                page_size=100
            )
            
            assigned_tickets = [
                ticket for ticket in tickets 
                if ticket.get('assigned_to') == member.id and ticket['status'] == 'open'
            ]
            
            if not assigned_tickets:
                return
            
            # 取消指派並重新分配
            assignment_service = self.assignment_service
            
            for ticket in assigned_tickets:
                # 取消當前指派
                await self.dao.assign_ticket(ticket['ticket_id'], None, None)
                
                # 嘗試重新自動分配
                settings = await self.dao.get_guild_settings(member.guild.id)
                if assignment_service and settings.get('auto_assign_enabled'):
                    await assignment_service.auto_assign_ticket(
                        ticket['ticket_id'], member.guild, settings
                    )
                
                # 通知票券頻道
                channel = member.guild.get_channel(ticket['channel_id'])
                if channel:
                    embed = discord.Embed(
                        title="👤 指派變更",
                        description=f"{member.mention} 已失去客服權限，票券指派已取消。",
                        color=discord.Color.orange()
                    )
                    await channel.send(embed=embed)
            
            logger.debug(f"[TicketListener] 已處理 {member.display_name} 失去客服權限的 {len(assigned_tickets)} 張票券")
            
        except Exception as e:
            logger.debug(f"[TicketListener] 處理客服身分組移除錯誤：{e}")

    async def _handle_staff_role_added(self, member: discord.Member):
        """處理客服身分組被添加"""
        try:
            # 發送歡迎訊息（可選）
            try:
                embed = discord.Embed(
                    title="🎉 歡迎加入客服團隊！",
                    description="你現在可以處理票券了。",
                    color=discord.Color.green()
                )
                embed.add_field(
                    name="🚀 快速開始",
                    value="• 使用 `/tickets` 查看待處理票券\n"
                          "• 使用 `/ticket_assign` 指派票券給自己\n"
                          "• 在票券頻道中回覆即可開始處理",
                    inline=False
                )
                embed.add_field(
                    name="💡 實用功能",
                    value="• `/ticket_template` - 使用回覆模板\n"
                          "• `/ticket_priority` - 調整優先級\n"
                          "• `/sla_dashboard` - 查看 SLA 狀態",
                    inline=False
                )
                
                await member.send(embed=embed)
                
            except discord.Forbidden:
                pass  # 無法發送私訊
            
            # 更新客服統計
            self._update_staff_status(member, True)
            
            logger.debug(f"[TicketListener] {member.display_name} 獲得客服權限")
            
        except Exception as e:
            logger.debug(f"[TicketListener] 處理客服身分組添加錯誤：{e}")

    def _update_staff_status(self, member: discord.Member, is_staff: bool):
        """更新客服狀態追蹤"""
        if is_staff:
            self.staff_online_status[member.id] = {
                'is_online': member.status != discord.Status.offline,
                'last_seen': datetime.now(timezone.utc),
                'status': str(member.status)
            }
        else:
            self.staff_online_status.pop(member.id, None)

    async def _notify_staff_of_pending_tickets(self, member: discord.Member):
        """通知客服待處理票券"""
        try:
            # 取得未分配的票券
            tickets, _ = await self.dao.paginate_tickets(
                guild_id=member.guild.id,
                status="open",
                page_size=10
            )
            
            unassigned_tickets = [t for t in tickets if not t.get('assigned_to')]
            
            if unassigned_tickets:
                embed = discord.Embed(
                    title="📋 待處理票券",
                    description=f"歡迎回來！目前有 {len(unassigned_tickets)} 張待分配的票券。",
                    color=discord.Color.blue()
                )
                
                # 顯示前5張票券
                ticket_list = []
                for ticket in unassigned_tickets[:5]:
                    priority_emoji = get_priority_emoji(ticket.get('priority', 'medium'))
                    ticket_list.append(f"{priority_emoji} #{ticket['ticket_id']:04d} - {ticket['type']}")
                
                embed.add_field(
                    name="票券列表",
                    value="\n".join(ticket_list),
                    inline=False
                )
                
                await member.send(embed=embed)
                
        except discord.Forbidden:
            pass  # 無法發送私訊
        except Exception as e:
            logger.debug(f"[TicketListener] 通知待處理票券錯誤：{e}")

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
                elif isinstance(timestamp, list):
                    # 處理訊息歷史列表
                    continue
            
            for key in expired_keys:
                self._message_cache.pop(key, None)
            
            # 清理用戶活動記錄
            expired_activity = []
            for key, timestamp in self.user_activity.items():
                if (current_time - timestamp).total_seconds() > 86400:  # 24小時
                    expired_activity.append(key)
            
            for key in expired_activity:
                self.user_activity.pop(key, None)
            
            # 清理速率限制記錄
            self._rate_limits = {
                k: v for k, v in self._rate_limits.items()
                if (current_time - v).total_seconds() < 300  # 5分鐘
            }
            
            logger.debug(f"[TicketListener] 清理任務完成 - 清理了 {len(expired_keys)} 個快取項目")
            
        except Exception as e:
            logger.debug(f"[TicketListener] 清理任務錯誤：{e}")

    @tasks.loop(minutes=30)
    async def activity_tracker(self):
        """活動追蹤任務"""
        try:
            # 統計活躍用戶數
            current_time = datetime.now(timezone.utc)
            active_users = sum(
                1 for timestamp in self.user_activity.values()
                if (current_time - timestamp).total_seconds() < 1800  # 30分鐘內活躍
            )
            
            # 統計在線客服數
            online_staff = sum(
                1 for status in self.staff_online_status.values()
                if status.get('is_online', False)
            )
            
            logger.debug(f"[TicketListener] 活動統計 - 活躍用戶: {active_users}, 在線客服: {online_staff}")
            
        except Exception as e:
            logger.debug(f"[TicketListener] 活動追蹤錯誤：{e}")

    @cleanup_task.before_loop
    async def before_cleanup(self):
        await self.bot.wait_until_ready()

    @activity_tracker.before_loop
    async def before_activity_tracker(self):
        await self.bot.wait_until_ready()

    # ===== 系統事件監聽 =====

    @commands.Cog.listener()
    async def on_ready(self):
        """系統準備完成"""
        logger.debug("[TicketListener] 票券系統監聽器已啟動")
        
        # 啟動服務協調器
        #await self.service_coordinator.start_services()
        
        # 初始化客服狀態追蹤
        await self._initialize_staff_tracking()

    async def _initialize_staff_tracking(self):
        """初始化客服狀態追蹤"""
        try:
            for guild in self.bot.guilds:
                settings = await self.dao.get_guild_settings(guild.id)
                support_roles = settings.get('support_roles', [])
                
                for role_id in support_roles:
                    role = guild.get_role(role_id)
                    if role:
                        for member in role.members:
                            if not member.bot:
                                self._update_staff_status(member, True)
            
            logger.debug(f"[TicketListener] 已初始化 {len(self.staff_online_status)} 個客服狀態追蹤")
            
        except Exception as e:
            logger.debug(f"[TicketListener] 初始化客服追蹤錯誤：{e}")

    # ===== 輔助方法 =====

    def get_activity_stats(self) -> Dict[str, Any]:
        """取得活動統計"""
        current_time = datetime.now(timezone.utc)
        
        return {
            'active_users_30min': sum(
                1 for timestamp in self.user_activity.values()
                if (current_time - timestamp).total_seconds() < 1800
            ),
            'online_staff': sum(
                1 for status in self.staff_online_status.values()
                if status.get('is_online', False)
            ),
            'total_tracked_staff': len(self.staff_online_status),
            'cache_size': len(self._message_cache)
        }

    def get_staff_online_status(self) -> Dict[int, Dict[str, Any]]:
        """取得客服在線狀態"""
        return self.staff_online_status.copy()

    def get_user_activity(self, guild_id: int) -> Dict[int, datetime]:
        """取得指定伺服器的用戶活動"""
        guild_activity = {}
        for key, timestamp in self.user_activity.items():
            if key.endswith(f"_{guild_id}"):
                user_id = int(key.split('_')[0])
                guild_activity[user_id] = timestamp
        return guild_activity


# ===== 票券維護監聽器 =====

class TicketMaintenanceListener(commands.Cog):
    """票券系統維護監聽器"""
    
    def __init__(self, bot):
        self.bot = bot
        self.dao = TicketDAO()
        
        # 啟動定期任務
        self.maintenance_task.start()
        self.health_check_task.start()

    def cog_unload(self):
        """清理資源"""
        self.maintenance_task.cancel()
        self.health_check_task.cancel()

    @tasks.loop(hours=6)
    async def maintenance_task(self):
        """定期維護任務"""
        try:
            logger.debug("[TicketMaintenance] 開始執行維護任務")
            
            # 清理過期的統計快取
            await self._cleanup_statistics_cache()
            
            # 清理舊的票券查看記錄
            await self._cleanup_old_ticket_views()
            
            # 清理舊的自動回覆日誌 (暫時停用 - 表格不存在)
            # await self._cleanup_auto_reply_logs()
            
            # 更新票券統計
            await self._update_ticket_statistics()
            
            logger.debug("[TicketMaintenance] 維護任務完成")
            
        except Exception as e:
            logger.debug(f"[TicketMaintenance] 維護任務錯誤：{e}")

    @tasks.loop(minutes=15)
    async def health_check_task(self):
        """健康檢查任務"""
        try:
            # 檢查資料庫連接
            await self._check_database_health()
            
            # 檢查服務狀態
            await self._check_services_health()
            
        except Exception as e:
            logger.debug(f"[TicketMaintenance] 健康檢查錯誤：{e}")

    async def _cleanup_statistics_cache(self):
        """清理統計快取"""
        try:
            async with self.dao.db_pool.connection() as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute(
                        "DELETE FROM ticket_statistics_cache WHERE expires_at < NOW()"
                    )
                    await conn.commit()
                    
                    if cursor.rowcount > 0:
                        logger.debug(f"[TicketMaintenance] 清理了 {cursor.rowcount} 個過期統計快取")
                        
        except Exception as e:
            logger.debug(f"[TicketMaintenance] 清理統計快取錯誤：{e}")

    async def _cleanup_old_ticket_views(self):
        """清理舊的票券查看記錄"""
        try:
            # 清理30天前的查看記錄
            cutoff_date = datetime.now(timezone.utc) - timedelta(days=30)
            
            async with self.dao.db_pool.connection() as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute(
                        "DELETE FROM ticket_views WHERE viewed_at < %s",
                        (cutoff_date,)
                    )
                    await conn.commit()
                    
                    if cursor.rowcount > 0:
                        logger.debug(f"[TicketMaintenance] 清理了 {cursor.rowcount} 個舊票券查看記錄")
                        
        except Exception as e:
            logger.debug(f"[TicketMaintenance] 清理票券查看記錄錯誤：{e}")

    async def _cleanup_auto_reply_logs(self):
        """清理自動回覆日誌"""
        try:
            # 清理7天前的自動回覆日誌
            cutoff_date = datetime.now(timezone.utc) - timedelta(days=7)
            
            async with self.dao.db_pool.connection() as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute(
                        "DELETE FROM auto_reply_logs WHERE created_at < %s",
                        (cutoff_date,)
                    )
                    await conn.commit()
                    
                    if cursor.rowcount > 0:
                        logger.debug(f"[TicketMaintenance] 清理了 {cursor.rowcount} 個舊自動回覆日誌")
                        
        except Exception as e:
            logger.debug(f"[TicketMaintenance] 清理自動回覆日誌錯誤：{e}")

    async def _update_ticket_statistics(self):
        """更新票券統計"""
        try:
            # 為所有活躍的伺服器更新統計
            for guild in self.bot.guilds:
                try:
                    # 更新基本統計
                    stats = await self.dao.get_server_statistics(guild.id)
                    
                    # 更新 SLA 統計
                    sla_stats = await self.dao.get_sla_statistics(guild.id)
                    
                    # 可以在這裡添加更多統計更新邏輯
                    
                except Exception as e:
                    logger.debug(f"[TicketMaintenance] 更新伺服器 {guild.id} 統計錯誤：{e}")
                    
        except Exception as e:
            logger.debug(f"[TicketMaintenance] 更新統計錯誤：{e}")

    async def _check_database_health(self):
        """檢查資料庫健康狀態"""
        try:
            # 簡單的資料庫連接測試
            async with self.dao.db_pool.connection() as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute("SELECT 1")
                    result = await cursor.fetchone()
                    
                    if not result or result[0] != 1:
                        logger.debug("[TicketMaintenance] 資料庫健康檢查失敗")
                        
        except Exception as e:
            logger.debug(f"[TicketMaintenance] 資料庫健康檢查錯誤：{e}")

    async def _check_services_health(self):
        """檢查服務健康狀態"""
        try:
            # 檢查資料庫健康狀態
            from bot.db.database_manager import get_database_health
            
            health_status = await get_database_health()
            
            if health_status.get('status') != 'healthy':
                logger.debug(f"[TicketMaintenance] 服務健康狀態警告：{health_status}")
            else:
                logger.debug("[TicketMaintenance] 服務健康狀態正常")
                
        except Exception as e:
            logger.debug(f"[TicketMaintenance] 服務健康檢查錯誤：{e}")

    @maintenance_task.before_loop
    async def before_maintenance(self):
        await self.bot.wait_until_ready()

    @health_check_task.before_loop
    async def before_health_check(self):
        await self.bot.wait_until_ready()

    def get_maintenance_stats(self) -> Dict[str, Any]:
        """取得維護統計"""
        return {
            'maintenance_task_running': not self.maintenance_task.is_being_cancelled(),
            'health_check_running': not self.health_check_task.is_being_cancelled(),
            'next_maintenance': self.maintenance_task.next_iteration,
            'next_health_check': self.health_check_task.next_iteration
        }


# ===== 擴展功能監聽器 =====

class TicketAnalyticsListener(commands.Cog):
    """票券分析監聽器"""
    
    def __init__(self, bot):
        self.bot = bot
        self.dao = TicketDAO()
        
        # 分析資料收集
        self.response_times = {}
        self.user_interactions = {}
        self.peak_hours_data = {}
        
        # 啟動分析任務
        self.analytics_task.start()

    def cog_unload(self):
        """清理資源"""
        self.analytics_task.cancel()

    @tasks.loop(hours=1)
    async def analytics_task(self):
        """分析任務"""
        try:
            current_hour = datetime.now(timezone.utc).hour
            
            # 收集當前小時的數據
            for guild in self.bot.guilds:
                guild_data = await self._collect_hourly_data(guild.id, current_hour)
                self.peak_hours_data[f"{guild.id}_{current_hour}"] = guild_data
            
            # 清理舊數據（保留24小時）
            cutoff_key = f"_{(current_hour - 24) % 24}"
            keys_to_remove = [key for key in self.peak_hours_data.keys() if key.endswith(cutoff_key)]
            for key in keys_to_remove:
                self.peak_hours_data.pop(key, None)
            
            logger.debug(f"[TicketAnalytics] 收集了 {len(self.bot.guilds)} 個伺服器的分析數據")
            
        except Exception as e:
            logger.debug(f"[TicketAnalytics] 分析任務錯誤：{e}")

    async def _collect_hourly_data(self, guild_id: int, hour: int) -> Dict[str, Any]:
        """收集每小時數據"""
        try:
            # 取得當前小時的活動票券
            current_time = datetime.now(timezone.utc)
            hour_start = current_time.replace(minute=0, second=0, microsecond=0)
            
            async with self.dao.db_pool.connection() as conn:
                async with conn.cursor(aiomysql.DictCursor) as cursor:
                    # 本小時建立的票券
                    await cursor.execute(
                        """
                        SELECT COUNT(*) as created_count, 
                               AVG(CASE WHEN priority = 'high' THEN 1 ELSE 0 END) as high_priority_rate
                        FROM tickets 
                        WHERE guild_id = %s AND created_at >= %s AND created_at < %s
                        """,
                        (guild_id, hour_start, hour_start + timedelta(hours=1))
                    )
                    creation_data = await cursor.fetchone()
                    
                    # 本小時關閉的票券
                    await cursor.execute(
                        "SELECT COUNT(*) as closed_count FROM tickets WHERE guild_id = %s AND closed_at >= %s AND closed_at < %s",
                        (guild_id, hour_start, hour_start + timedelta(hours=1))
                    )
                    close_data = await cursor.fetchone()
            
            return {
                'hour': hour,
                'created_tickets': creation_data.get('created_count', 0),
                'closed_tickets': close_data.get('closed_count', 0), 
                'high_priority_rate': creation_data.get('high_priority_rate', 0),
                'timestamp': current_time
            }
            
        except Exception as e:
            logger.debug(f"[TicketAnalytics] 收集數據錯誤：{e}")
            return {'hour': hour, 'created_tickets': 0, 'closed_tickets': 0, 'high_priority_rate': 0}

    @analytics_task.before_loop
    async def before_analytics(self):
        await self.bot.wait_until_ready()

    def get_peak_hours_analysis(self, guild_id: int) -> Dict[str, Any]:
        """取得高峰時段分析"""
        guild_data = {k: v for k, v in self.peak_hours_data.items() if k.startswith(f"{guild_id}_")}
        
        if not guild_data:
            return {'peak_hours': [], 'total_activity': 0}
        
        # 分析高峰時段
        hourly_activity = {}
        for data in guild_data.values():
            hour = data['hour']
            activity = data['created_tickets'] + data['closed_tickets']
            hourly_activity[hour] = hourly_activity.get(hour, 0) + activity
        
        # 找出前3個高峰時段
        peak_hours = sorted(hourly_activity.items(), key=lambda x: x[1], reverse=True)[:3]
        
        return {
            'peak_hours': [{'hour': h, 'activity': a} for h, a in peak_hours],
            'total_activity': sum(hourly_activity.values()),
            'average_activity': sum(hourly_activity.values()) / len(hourly_activity) if hourly_activity else 0
        }


# ===== 註冊系統 =====

async def setup(bot):
    """註冊監聽器"""
    await bot.add_cog(TicketListener(bot))
    await bot.add_cog(TicketMaintenanceListener(bot))
    await bot.add_cog(TicketAnalyticsListener(bot))
    logger.debug("✅ 票券系統監聽器已載入")


# ===== 匯出 =====

__all__ = [
    'TicketListener',
    'TicketMaintenanceListener', 
    'TicketAnalyticsListener'
]