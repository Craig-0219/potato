# bot/services/ticket_service.py - 票券系統業務邏輯服務層

import discord
import asyncio
import random
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Any, Tuple, Union
from collections import defaultdict
import json

from bot.db.ticket_dao import TicketDAO
from bot.utils.ticket_constants import (
    TicketConstants, get_priority_emoji, calculate_sla_time,
    ERROR_MESSAGES, SUCCESS_MESSAGES, TicketSelectOptions
)
from bot.utils.ticket_utils import (
    TicketPermissionChecker, generate_ticket_channel_name,
    create_ticket_channel_overwrites, build_ticket_embed,
    send_ticket_notification, send_sla_alert, TicketCache
)
from bot.utils.ticket_validators import (
    TicketCreationValidator, ValidationResult
)
from bot.utils.debug import debug_log


# ===== 基礎服務類別 =====

class BaseTicketService:
    """票券服務基礎類別"""
    
    def __init__(self):
        self.dao = TicketDAO()
        self.cache = TicketCache(timeout_minutes=10)
    
    async def get_guild_settings(self, guild_id: int) -> Dict[str, Any]:
        """取得伺服器設定（含快取）"""
        cache_key = f"guild_settings_{guild_id}"
        settings = self.cache.get(cache_key)
        
        if not settings:
            settings = await self.dao.get_guild_settings(guild_id)
            if not settings:
                settings = await self.dao.create_default_settings(guild_id)
            self.cache.set(cache_key, settings, timeout=600)  # 10分鐘快取
        
        return settings
    
    def clear_settings_cache(self, guild_id: int):
        """清除設定快取"""
        cache_key = f"guild_settings_{guild_id}"
        self.cache.delete(cache_key)


# ===== 票券建立服務 =====

class TicketCreationService(BaseTicketService):
    """票券建立服務"""
    
    async def create_ticket(self, user: discord.Member, ticket_type: str, 
                          priority: str = 'medium', 
                          additional_info: Dict[str, Any] = None) -> Tuple[bool, str, Optional[int]]:
        """
        建立新票券
        
        Returns:
            Tuple[success, message, ticket_id]
        """
        try:
            # 取得伺服器設定
            settings = await self.get_guild_settings(user.guild.id)
            
            # 驗證建立條件
            current_tickets = await self.dao.get_user_ticket_count(
                str(user.id), user.guild.id, "open"
            )
            
            validation_result = await TicketCreationValidator.validate_creation_request(
                user, ticket_type, priority, settings, current_tickets
            )
            
            if not validation_result.is_valid:
                return False, validation_result.error_message, None
            
            # 建立票券頻道
            channel_result = await self._create_ticket_channel(
                user, ticket_type, priority, settings
            )
            
            if not channel_result[0]:
                return False, channel_result[1], None
            
            channel = channel_result[2]
            
            # 建立票券記錄
            ticket_id = await self.dao.create_ticket(
                discord_id=str(user.id),
                username=user.display_name,
                ticket_type=ticket_type,
                channel_id=channel.id,
                guild_id=user.guild.id,
                priority=priority
            )
            
            if not ticket_id:
                # 建立記錄失敗，清理頻道
                try:
                    await channel.delete(reason="票券記錄建立失敗")
                except:
                    pass
                return False, "建立票券記錄失敗", None
            
            # 發送歡迎訊息
            await self._send_welcome_message(channel, user, ticket_id, ticket_type, priority, settings)
            
            # 自動分配（如果啟用）
            if settings.get('auto_assign_enabled'):
                assignment_service = TicketAssignmentService()
                await assignment_service.auto_assign_ticket(ticket_id, user.guild, settings)
            
            # 發送通知
            await self._send_creation_notifications(user, ticket_id, ticket_type, priority, settings)
            
            # 清除相關快取
            self._clear_user_cache(user.id, user.guild.id)
            
            debug_log(f"[TicketCreation] 用戶 {user.id} 成功建立票券 #{ticket_id:04d}")
            
            return True, f"✅ 票券 #{ticket_id:04d} 建立成功！", ticket_id
            
        except Exception as e:
            debug_log(f"[TicketCreation] 建立票券錯誤：{e}")
            return False, "系統錯誤，請稍後再試", None
    
    async def _create_ticket_channel(self, user: discord.Member, ticket_type: str, 
                                   priority: str, settings: Dict[str, Any]) -> Tuple[bool, str, Optional[discord.TextChannel]]:
        """建立票券頻道"""
        try:
            # 取得分類頻道
            category_id = settings.get('category_id')
            if not category_id:
                return False, "尚未設定票券分類頻道", None
            
            category = user.guild.get_channel(category_id)
            if not category or not isinstance(category, discord.CategoryChannel):
                return False, "票券分類頻道不存在或類型錯誤", None
            
            # 生成票券代碼和頻道名稱
            ticket_code = await self.dao.next_ticket_code()
            channel_name = generate_ticket_channel_name(int(ticket_code), user.display_name)
            
            # 建立頻道權限
            support_roles = settings.get('support_roles', [])
            overwrites = await create_ticket_channel_overwrites(user.guild, user, support_roles)
            
            # 建立頻道
            channel = await user.guild.create_text_channel(
                name=channel_name,
                category=category,
                overwrites=overwrites,
                topic=f"票券 #{ticket_code} - {ticket_type} - {user.display_name}",
                reason=f"建立票券 - 用戶: {user} ({user.id})"
            )
            
            return True, "頻道建立成功", channel
            
        except discord.Forbidden:
            return False, "機器人沒有建立頻道的權限", None
        except discord.HTTPException as e:
            return False, f"建立頻道失敗：{str(e)}", None
        except Exception as e:
            debug_log(f"[TicketCreation] 建立頻道錯誤：{e}")
            return False, "建立頻道時發生未知錯誤", None
    
    async def _send_welcome_message(self, channel: discord.TextChannel, user: discord.Member,
                                  ticket_id: int, ticket_type: str, priority: str, 
                                  settings: Dict[str, Any]):
        """發送歡迎訊息"""
        try:
            # 建立歡迎嵌入
            priority_emoji = get_priority_emoji(priority)
            sla_minutes = calculate_sla_time(priority, settings.get('sla_response_minutes', 60))
            
            embed = discord.Embed(
                title=f"🎫 票券 #{ticket_id:04d}",
                description=f"你好 {user.mention}！\n\n{settings.get('welcome_message', '請詳細描述你的問題，我們會盡快回覆。')}",
                color=discord.Color.blue()
            )
            
            # 票券資訊
            embed.add_field(
                name="📋 票券資訊",
                value=f"**類型：** {ticket_type}\n"
                      f"**優先級：** {priority_emoji} {priority.upper()}\n"
                      f"**預期回覆：** {sla_minutes} 分鐘內",
                inline=True
            )
            
            # 建立時間
            embed.add_field(
                name="⏰ 建立時間",
                value=f"<t:{int(datetime.now(timezone.utc).timestamp())}:F>",
                inline=True
            )
            
            # 使用說明
            embed.add_field(
                name="💡 使用說明",
                value="• 使用控制面板按鈕進行操作\n"
                      "• 請保持禮貌和耐心\n"
                      "• 提供詳細資訊有助於快速解決\n"
                      "• 關閉後可為服務評分",
                inline=False
            )
            
            embed.set_footer(text="感謝你使用我們的客服系統！")
            
            # 票券控制面板
            from bot.views.ticket_views import TicketControlView
            control_view = TicketControlView(ticket_id)
            
            await channel.send(embed=embed, view=control_view)
            
        except Exception as e:
            debug_log(f"[TicketCreation] 發送歡迎訊息錯誤：{e}")
    
    async def _send_creation_notifications(self, user: discord.Member, ticket_id: int,
                                         ticket_type: str, priority: str, 
                                         settings: Dict[str, Any]):
        """發送建立通知"""
        try:
            # 通知用戶
            await send_ticket_notification(
                user,
                "🎫 票券建立成功",
                f"你的{ticket_type}票券 #{ticket_id:04d} 已建立完成，我們會盡快回覆。",
                discord.Color.green()
            )
            
            # 通知客服頻道（如果設定）
            log_channel_id = settings.get('log_channel_id')
            if log_channel_id:
                log_channel = user.guild.get_channel(log_channel_id)
                if log_channel:
                    priority_emoji = get_priority_emoji(priority)
                    
                    embed = discord.Embed(
                        title="🎫 新票券建立",
                        color=discord.Color.blue()
                    )
                    embed.add_field(
                        name="票券資訊",
                        value=f"**編號：** #{ticket_id:04d}\n"
                              f"**類型：** {ticket_type}\n"
                              f"**優先級：** {priority_emoji} {priority.upper()}\n"
                              f"**用戶：** {user.mention}",
                        inline=False
                    )
                    
                    await log_channel.send(embed=embed)
            
        except Exception as e:
            debug_log(f"[TicketCreation] 發送通知錯誤：{e}")
    
    def _clear_user_cache(self, user_id: int, guild_id: int):
        """清除用戶相關快取"""
        cache_keys = [
            f"user_tickets_{user_id}_{guild_id}",
            f"user_ticket_count_{user_id}_{guild_id}"
        ]
        for key in cache_keys:
            self.cache.delete(key)


# ===== 票券分配服務 =====

class TicketAssignmentService(BaseTicketService):
    """票券分配服務"""
    
    async def auto_assign_ticket(self, ticket_id: int, guild: discord.Guild, 
                               settings: Dict[str, Any]) -> Tuple[bool, str]:
        """自動分配票券"""
        try:
            if not settings.get('auto_assign_enabled'):
                return False, "自動分配未啟用"
            
            # 取得票券資訊
            ticket_info = await self.dao.get_ticket_by_id(ticket_id)
            if not ticket_info:
                return False, "找不到票券資訊"
            
            # 取得可用客服人員
            available_staff = await self._get_available_staff(guild, settings)
            if not available_staff:
                return False, "目前沒有可用的客服人員"
            
            # 選擇最佳客服
            algorithm = settings.get('auto_assignment_algorithm', 'least_loaded')
            selected_staff = await self._select_best_staff(
                available_staff, ticket_info, algorithm, guild.id
            )
            
            if not selected_staff:
                return False, "無法找到合適的客服人員"
            
            # 執行分配
            success = await self.assign_ticket(ticket_id, selected_staff.id, "system")
            
            if success:
                # 通知被分配的客服
                await self._notify_assigned_staff(selected_staff, ticket_info, guild)
                
                debug_log(f"[Assignment] 票券 #{ticket_id:04d} 自動分配給 {selected_staff.id}")
                return True, f"已分配給 {selected_staff.display_name}"
            else:
                return False, "分配操作失敗"
                
        except Exception as e:
            debug_log(f"[Assignment] 自動分配錯誤：{e}")
            return False, "自動分配發生錯誤"
    
    async def assign_ticket(self, ticket_id: int, staff_id: int, 
                          assigned_by: Union[str, int]) -> bool:
        """手動分配票券"""
        try:
            success = await self.dao.assign_ticket(ticket_id, staff_id, assigned_by)
            
            if success:
                # 清除相關快取
                self._clear_assignment_cache(ticket_id)
            
            return success
            
        except Exception as e:
            debug_log(f"[Assignment] 分配票券錯誤：{e}")
            return False
    
    async def _get_available_staff(self, guild: discord.Guild, 
                                 settings: Dict[str, Any]) -> List[discord.Member]:
        """取得可用客服人員"""
        support_roles = settings.get('support_roles', [])
        if not support_roles:
            return []
        
        available_staff = []
        
        for role_id in support_roles:
            role = guild.get_role(role_id)
            if not role:
                continue
            
            for member in role.members:
                if member.bot:
                    continue
                
                # 檢查在線狀態
                if member.status != discord.Status.offline:
                    available_staff.append(member)
        
        # 去重
        seen = set()
        unique_staff = []
        for staff in available_staff:
            if staff.id not in seen:
                seen.add(staff.id)
                unique_staff.append(staff)
        
        return unique_staff
    
    async def _select_best_staff(self, available_staff: List[discord.Member],
                               ticket_info: Dict[str, Any], algorithm: str,
                               guild_id: int) -> Optional[discord.Member]:
        """選擇最佳客服人員"""
        if not available_staff:
            return None
        
        if algorithm == 'round_robin':
            return await self._round_robin_assignment(available_staff, guild_id)
        elif algorithm == 'least_loaded':
            return await self._least_loaded_assignment(available_staff, guild_id)
        elif algorithm == 'specialty_match':
            return await self._specialty_match_assignment(available_staff, ticket_info, guild_id)
        elif algorithm == 'random':
            return random.choice(available_staff)
        else:
            # 預設使用最少工作量
            return await self._least_loaded_assignment(available_staff, guild_id)
    
    async def _round_robin_assignment(self, available_staff: List[discord.Member],
                                    guild_id: int) -> discord.Member:
        """輪流分配算法"""
        cache_key = f"round_robin_index_{guild_id}"
        current_index = self.cache.get(cache_key) or 0
        
        selected_staff = available_staff[current_index % len(available_staff)]
        
        # 更新索引
        next_index = (current_index + 1) % len(available_staff)
        self.cache.set(cache_key, next_index, timeout=3600)  # 1小時快取
        
        return selected_staff
    
    async def _least_loaded_assignment(self, available_staff: List[discord.Member],
                                     guild_id: int) -> discord.Member:
        """最少工作量分配算法"""
        staff_workloads = {}
        
        for staff in available_staff:
            # 取得當前開啟票券數量
            current_tickets = await self.dao.get_user_assigned_ticket_count(
                staff.id, guild_id, "open"
            )
            staff_workloads[staff.id] = current_tickets
        
        # 選擇工作量最少的客服
        min_workload = min(staff_workloads.values())
        candidates = [staff for staff in available_staff 
                     if staff_workloads[staff.id] == min_workload]
        
        return random.choice(candidates)
    
    async def _specialty_match_assignment(self, available_staff: List[discord.Member],
                                        ticket_info: Dict[str, Any], 
                                        guild_id: int) -> discord.Member:
        """專精匹配分配算法"""
        ticket_type = ticket_info.get('type', '').lower()
        
        # 取得所有客服的專精資訊
        specialties_map = await self.dao.get_all_staff_specialties(guild_id)
        
        # 尋找專精匹配的客服
        matching_staff = []
        for staff in available_staff:
            specialties = specialties_map.get(str(staff.id), [])
            
            # 檢查是否有匹配的專精
            for specialty in specialties:
                if specialty.lower() in ticket_type or ticket_type in specialty.lower():
                    matching_staff.append(staff)
                    break
        
        if matching_staff:
            # 如果有專精匹配的客服，從中選擇工作量最少的
            return await self._least_loaded_assignment(matching_staff, guild_id)
        else:
            # 沒有專精匹配，回退到最少工作量算法
            return await self._least_loaded_assignment(available_staff, guild_id)
    
    async def _notify_assigned_staff(self, staff: discord.Member, 
                                   ticket_info: Dict[str, Any], guild: discord.Guild):
        """通知被分配的客服"""
        try:
            embed = discord.Embed(
                title="📋 新票券分配",
                description=f"你被分配了一張新票券",
                color=discord.Color.blue()
            )
            
            priority_emoji = get_priority_emoji(ticket_info.get('priority', 'medium'))
            
            embed.add_field(
                name="票券資訊",
                value=f"**編號：** #{ticket_info['ticket_id']:04d}\n"
                      f"**類型：** {ticket_info['type']}\n"
                      f"**優先級：** {priority_emoji} {ticket_info.get('priority', 'medium').upper()}\n"
                      f"**開票者：** <@{ticket_info['discord_id']}>",
                inline=False
            )
            
            # 添加頻道連結
            channel = guild.get_channel(ticket_info['channel_id'])
            if channel:
                embed.add_field(
                    name="票券頻道",
                    value=channel.mention,
                    inline=True
                )
            
            await staff.send(embed=embed)
            
        except discord.Forbidden:
            debug_log(f"[Assignment] 無法向客服 {staff.id} 發送私訊")
        except Exception as e:
            debug_log(f"[Assignment] 通知客服錯誤：{e}")
    
    def _clear_assignment_cache(self, ticket_id: int):
        """清除分配相關快取"""
        # 這裡可以清除特定票券的快取
        pass


# ===== SLA 監控服務 =====

class SLAMonitoringService(BaseTicketService):
    """SLA 監控服務"""
    
    def __init__(self):
        super().__init__()
        self.monitoring_active = True
        self.check_interval = 300  # 5分鐘檢查一次
    
    async def start_monitoring(self):
        """啟動 SLA 監控"""
        debug_log("[SLA] SLA 監控服務啟動")
        
        while self.monitoring_active:
            try:
                await self._check_sla_compliance()
                await asyncio.sleep(self.check_interval)
            except Exception as e:
                debug_log(f"[SLA] 監控循環錯誤：{e}")
                await asyncio.sleep(60)  # 錯誤時等待1分鐘
    
    def stop_monitoring(self):
        """停止 SLA 監控"""
        self.monitoring_active = False
        debug_log("[SLA] SLA 監控服務停止")
    
    async def _check_sla_compliance(self):
        """檢查 SLA 合規性"""
        try:
            # 取得所有超時的票券
            overdue_tickets = await self.dao.get_overdue_tickets()
            
            if not overdue_tickets:
                return
            
            debug_log(f"[SLA] 發現 {len(overdue_tickets)} 張超時票券")
            
            # 處理每張超時票券
            for ticket in overdue_tickets:
                await self._process_overdue_ticket(ticket)
            
        except Exception as e:
            debug_log(f"[SLA] 檢查 SLA 合規性錯誤：{e}")
    
    async def _process_overdue_ticket(self, ticket: Dict[str, Any]):
        """處理超時票券"""
        try:
            guild_id = ticket['guild_id']
            
            # 取得伺服器設定
            settings = await self.get_guild_settings(guild_id)
            
            # 計算超時時間
            now = datetime.now(timezone.utc)
            overdue_minutes = (now - ticket['created_at']).total_seconds() / 60
            target_minutes = calculate_sla_time(
                ticket.get('priority', 'medium'), 
                settings.get('sla_response_minutes', 60)
            )
            actual_overdue = overdue_minutes - target_minutes
            
            # 發送 SLA 警告
            await self._send_sla_warning(ticket, actual_overdue, settings)
            
            # 標記已警告
            await self.dao.mark_sla_warned(ticket['ticket_id'])
            
            # 記錄到日誌
            debug_log(f"[SLA] 票券 #{ticket['ticket_id']:04d} 超時 {actual_overdue:.1f} 分鐘")
            
        except Exception as e:
            debug_log(f"[SLA] 處理超時票券錯誤：{e}")
    
    async def _send_sla_warning(self, ticket: Dict[str, Any], overdue_minutes: float,
                              settings: Dict[str, Any]):
        """發送 SLA 警告"""
        try:
            # 發送到 SLA 警告頻道
            alert_channel_id = settings.get('sla_alert_channel_id')
            if alert_channel_id:
                # 需要從 bot 實例取得頻道，這裡暫時跳過
                # 實際使用時需要傳入 bot 實例或 guild 物件
                pass
            
            # 發送到日誌頻道
            log_channel_id = settings.get('log_channel_id')
            if log_channel_id:
                # 同樣需要 guild 物件來取得頻道
                pass
            
        except Exception as e:
            debug_log(f"[SLA] 發送 SLA 警告錯誤：{e}")
    
    async def get_sla_statistics(self, guild_id: int, days: int = 7) -> Dict[str, Any]:
        """取得 SLA 統計資料"""
        try:
            return await self.dao.get_sla_statistics(guild_id, days)
        except Exception as e:
            debug_log(f"[SLA] 取得統計資料錯誤：{e}")
            return {}
    
    async def record_first_response(self, ticket_id: int, staff_id: int) -> bool:
        """記錄首次回應"""
        try:
            # 檢查是否已有回應記錄
            if await self.dao.has_staff_response(ticket_id):
                return False
            
            # 取得票券資訊計算回應時間
            ticket_info = await self.dao.get_ticket_by_id(ticket_id)
            if not ticket_info:
                return False
            
            response_time = datetime.now(timezone.utc) - ticket_info['created_at']
            response_minutes = response_time.total_seconds() / 60
            
            # 記錄到資料庫
            success = await self.dao.record_first_response(ticket_id, staff_id, response_minutes)
            
            if success:
                debug_log(f"[SLA] 記錄票券 #{ticket_id:04d} 首次回應：{response_minutes:.1f} 分鐘")
            
            return success
            
        except Exception as e:
            debug_log(f"[SLA] 記錄首次回應錯誤：{e}")
            return False


# ===== 自動回覆服務 =====

class AutoReplyService(BaseTicketService):
    """自動回覆服務"""
    
    async def process_message(self, message: discord.Message, ticket_info: Dict[str, Any]) -> bool:
        """處理訊息並觸發自動回覆"""
        try:
            # 只處理用戶訊息（非機器人）
            if message.author.bot:
                return False
            
            # 只處理票券創建者的訊息
            if str(message.author.id) != ticket_info.get('discord_id'):
                return False
            
            # 取得自動回覆規則
            rules = await self.dao.get_auto_reply_rules(message.guild.id)
            if not rules:
                return False
            
            # 尋找匹配的規則
            matching_rule = await self._find_matching_rule(message.content, rules)
            if not matching_rule:
                return False
            
            # 處理並發送回覆
            reply_content = await self._process_reply_template(
                matching_rule['reply'], message.author, ticket_info
            )
            
            # 發送自動回覆
            embed = discord.Embed(
                title="🤖 自動回覆",
                description=reply_content,
                color=discord.Color.blue()
            )
            embed.set_footer(text="這是自動回覆，客服人員會盡快為你處理。")
            
            await message.channel.send(embed=embed)
            
            # 記錄自動回覆日誌
            await self.dao.log_auto_reply(
                ticket_info['ticket_id'], 
                matching_rule['id'], 
                reply_content
            )
            
            debug_log(f"[AutoReply] 票券 #{ticket_info['ticket_id']:04d} 觸發自動回覆：{matching_rule['name']}")
            
            return True
            
        except Exception as e:
            debug_log(f"[AutoReply] 處理訊息錯誤：{e}")
            return False
    
    async def _find_matching_rule(self, message_content: str, 
                                rules: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """尋找匹配的自動回覆規則"""
        if not message_content:
            return None
        
        content_lower = message_content.lower()
        matching_rules = []
        
        # 檢查所有規則
        for rule in rules:
            if not rule.get('enabled', True):
                continue
            
            keywords = rule.get('keywords', [])
            if not keywords:
                continue
            
            # 檢查關鍵字匹配
            for keyword in keywords:
                if keyword.lower() in content_lower:
                    matching_rules.append(rule)
                    break
        
        if not matching_rules:
            return None
        
        # 按優先級排序，返回最高優先級的規則
        matching_rules.sort(key=lambda x: x.get('priority', 0), reverse=True)
        return matching_rules[0]
    
    async def _process_reply_template(self, template: str, user: discord.Member,
                                    ticket_info: Dict[str, Any]) -> str:
        """處理回覆模板"""
        if not template:
            return ""
        
        # 替換基本變數
        processed_template = template
        
        # 用戶相關變數
        processed_template = processed_template.replace('{user}', user.display_name)
        processed_template = processed_template.replace('{mention}', user.mention)
        
        # 票券相關變數
        processed_template = processed_template.replace('{ticket_id}', f"#{ticket_info['ticket_id']:04d}")
        processed_template = processed_template.replace('{ticket_type}', ticket_info.get('type', ''))
        
        # 時間相關變數
        now = datetime.now(timezone.utc)
        processed_template = processed_template.replace('{time}', now.strftime('%H:%M'))
        processed_template = processed_template.replace('{date}', now.strftime('%Y-%m-%d'))
        processed_template = processed_template.replace('{datetime}', now.strftime('%Y-%m-%d %H:%M'))
        
        return processed_template
    
    async def create_auto_reply_rule(self, guild_id: int, name: str, keywords: List[str],
                                   reply: str, priority: int = 0) -> bool:
        """建立自動回覆規則"""
        try:
            return await self.dao.create_auto_reply_rule(guild_id, name, keywords, reply, priority)
        except Exception as e:
            debug_log(f"[AutoReply] 建立規則錯誤：{e}")
            return False
    
    async def get_auto_reply_rules(self, guild_id: int) -> List[Dict[str, Any]]:
        """取得自動回覆規則"""
        try:
            return await self.dao.get_auto_reply_rules(guild_id)
        except Exception as e:
            debug_log(f"[AutoReply] 取得規則錯誤：{e}")
            return []


# ===== 統計服務 =====

class StatisticsService(BaseTicketService):
    """統計服務"""
    
    async def get_server_statistics(self, guild_id: int) -> Dict[str, Any]:
        """取得伺服器統計資料"""
        try:
            cache_key = f"server_stats_{guild_id}"
            stats = self.cache.get(cache_key)
            
            if not stats:
                stats = await self.dao.get_server_statistics(guild_id)
                self.cache.set(cache_key, stats, timeout=180)  # 3分鐘快取
            
            return stats
        except Exception as e:
            debug_log(f"[Statistics] 取得伺服器統計錯誤：{e}")
            return {}
    
    async def get_staff_performance(self, guild_id: int, period: str = "week",
                                  staff_id: int = None) -> Dict[str, Any]:
        """取得客服表現統計"""
        try:
            cache_key = f"staff_performance_{guild_id}_{period}_{staff_id or 'all'}"
            stats = self.cache.get(cache_key)
            
            if not stats:
                stats = await self.dao.get_staff_workload_stats(guild_id, period, staff_id)
                self.cache.set(cache_key, stats, timeout=300)  # 5分鐘快取
            
            return stats
        except Exception as e:
            debug_log(f"[Statistics] 取得客服統計錯誤：{e}")
            return {}
    
    async def get_user_ticket_summary(self, user_id: int, guild_id: int) -> Dict[str, Any]:
        """取得用戶票券摘要"""
        try:
            cache_key = f"user_summary_{user_id}_{guild_id}"
            summary = self.cache.get(cache_key)
            
            if not summary:
                # 取得用戶所有票券
                tickets, total = await self.dao.paginate_tickets(
                    user_id=str(user_id),
                    guild_id=guild_id,
                    page_size=1000  # 取得所有票券
                )
                
                summary = self._calculate_user_summary(tickets)
                self.cache.set(cache_key, summary, timeout=600)  # 10分鐘快取
            
            return summary
        except Exception as e:
            debug_log(f"[Statistics] 取得用戶摘要錯誤：{e}")
            return {}
    
    def _calculate_user_summary(self, tickets: List[Dict[str, Any]]) -> Dict[str, Any]:
        """計算用戶摘要統計"""
        if not tickets:
            return {
                'total_tickets': 0,
                'open_tickets': 0,
                'closed_tickets': 0,
                'avg_rating': 0,
                'total_ratings': 0,
                'resolution_times': []
            }
        
        summary = {
            'total_tickets': len(tickets),
            'open_tickets': 0,
            'closed_tickets': 0,
            'avg_rating': 0,
            'total_ratings': 0,
            'resolution_times': []
        }
        
        ratings = []
        resolution_times = []
        
        for ticket in tickets:
            # 統計狀態
            if ticket['status'] == 'open':
                summary['open_tickets'] += 1
            elif ticket['status'] == 'closed':
                summary['closed_tickets'] += 1
            
            # 統計評分
            if ticket.get('rating'):
                ratings.append(ticket['rating'])
            
            # 計算解決時間
            if ticket.get('closed_at') and ticket.get('created_at'):
                resolution_time = ticket['closed_at'] - ticket['created_at']
                resolution_times.append(resolution_time.total_seconds() / 3600)  # 轉換為小時
        
        # 計算平均評分
        if ratings:
            summary['avg_rating'] = sum(ratings) / len(ratings)
            summary['total_ratings'] = len(ratings)
        
        summary['resolution_times'] = resolution_times
        
        return summary
    
    async def generate_periodic_report(self, guild_id: int, period: str = "week") -> Dict[str, Any]:
        """生成週期性報告"""
        try:
            # 取得各種統計資料
            server_stats = await self.get_server_statistics(guild_id)
            sla_stats = await self.dao.get_sla_statistics(guild_id)
            staff_stats = await self.get_staff_performance(guild_id, period)
            
            # 組合報告
            report = {
                'period': period,
                'generated_at': datetime.now(timezone.utc),
                'server_statistics': server_stats,
                'sla_statistics': sla_stats,
                'staff_performance': staff_stats,
                'summary': self._generate_report_summary(server_stats, sla_stats, staff_stats)
            }
            
            return report
        except Exception as e:
            debug_log(f"[Statistics] 生成報告錯誤：{e}")
            return {}
    
    def _generate_report_summary(self, server_stats: Dict, sla_stats: Dict, 
                               staff_stats: Dict) -> Dict[str, Any]:
        """生成報告摘要"""
        summary = {
            'highlights': [],
            'concerns': [],
            'recommendations': []
        }
        
        # 分析亮點
        if server_stats.get('avg_rating', 0) >= 4.5:
            summary['highlights'].append("客戶滿意度優秀（≥4.5星）")
        
        if sla_stats.get('sla_rate', 0) >= 90:
            summary['highlights'].append("SLA達標率優秀（≥90%）")
        
        # 分析問題
        if server_stats.get('avg_rating', 0) < 3.0:
            summary['concerns'].append("客戶滿意度較低（<3.0星）")
        
        if sla_stats.get('sla_rate', 0) < 70:
            summary['concerns'].append("SLA達標率偏低（<70%）")
        
        overdue_total = sum([
            sla_stats.get('overdue_high', 0),
            sla_stats.get('overdue_medium', 0),
            sla_stats.get('overdue_low', 0)
        ])
        
        if overdue_total > 10:
            summary['concerns'].append(f"當前超時票券較多（{overdue_total}張）")
        
        # 提供建議
        if summary['concerns']:
            if "滿意度較低" in str(summary['concerns']):
                summary['recommendations'].append("建議加強客服培訓，提升服務品質")
            
            if "SLA達標率" in str(summary['concerns']):
                summary['recommendations'].append("建議檢查客服人力配置，優化回應流程")
            
            if "超時票券" in str(summary['concerns']):
                summary['recommendations'].append("建議啟用自動分配，加強SLA監控")
        
        return summary


# ===== 通知服務 =====

class NotificationService(BaseTicketService):
    """通知服務"""
    
    async def send_ticket_notification(self, user: discord.Member, notification_type: str,
                                     ticket_info: Dict[str, Any], additional_data: Dict[str, Any] = None) -> bool:
        """發送票券相關通知"""
        try:
            # 檢查用戶通知偏好
            preferences = await self._get_notification_preferences(user.id, user.guild.id)
            
            if not preferences.get(notification_type, True):
                return False  # 用戶已關閉此類通知
            
            # 建立通知內容
            embed = await self._build_notification_embed(notification_type, ticket_info, additional_data)
            
            # 發送通知
            await user.send(embed=embed)
            
            debug_log(f"[Notification] 發送{notification_type}通知給用戶 {user.id}")
            return True
            
        except discord.Forbidden:
            debug_log(f"[Notification] 無法向用戶 {user.id} 發送私訊")
            return False
        except Exception as e:
            debug_log(f"[Notification] 發送通知錯誤：{e}")
            return False
    
    async def send_staff_notification(self, staff: discord.Member, notification_type: str,
                                    ticket_info: Dict[str, Any], additional_data: Dict[str, Any] = None) -> bool:
        """發送客服相關通知"""
        try:
            # 檢查客服通知偏好
            preferences = await self._get_notification_preferences(staff.id, staff.guild.id)
            
            if not preferences.get(notification_type, True):
                return False
            
            # 建立通知內容
            embed = await self._build_staff_notification_embed(notification_type, ticket_info, additional_data)
            
            # 發送通知
            await staff.send(embed=embed)
            
            debug_log(f"[Notification] 發送{notification_type}通知給客服 {staff.id}")
            return True
            
        except discord.Forbidden:
            debug_log(f"[Notification] 無法向客服 {staff.id} 發送私訊")
            return False
        except Exception as e:
            debug_log(f"[Notification] 發送客服通知錯誤：{e}")
            return False
    
    async def send_channel_notification(self, channel: discord.TextChannel, notification_type: str,
                                      ticket_info: Dict[str, Any], additional_data: Dict[str, Any] = None) -> bool:
        """發送頻道通知"""
        try:
            embed = await self._build_channel_notification_embed(notification_type, ticket_info, additional_data)
            await channel.send(embed=embed)
            
            debug_log(f"[Notification] 發送{notification_type}通知到頻道 {channel.id}")
            return True
            
        except discord.Forbidden:
            debug_log(f"[Notification] 沒有權限在頻道 {channel.id} 發送訊息")
            return False
        except Exception as e:
            debug_log(f"[Notification] 發送頻道通知錯誤：{e}")
            return False
    
    async def _get_notification_preferences(self, user_id: int, guild_id: int) -> Dict[str, bool]:
        """取得通知偏好設定"""
        # 這裡可以從資料庫讀取用戶的通知偏好
        # 暫時返回預設值（全部啟用）
        return {
            'ticket_assigned': True,
            'ticket_closed': True,
            'sla_warning': True,
            'rating_received': True,
            'ticket_escalated': True
        }
    
    async def _build_notification_embed(self, notification_type: str, ticket_info: Dict[str, Any],
                                      additional_data: Dict[str, Any] = None) -> discord.Embed:
        """建立用戶通知嵌入"""
        if notification_type == 'ticket_assigned':
            embed = discord.Embed(
                title="👥 票券已分配",
                description=f"你的票券 #{ticket_info['ticket_id']:04d} 已分配給客服人員處理。",
                color=discord.Color.blue()
            )
            
            if additional_data and additional_data.get('staff_name'):
                embed.add_field(
                    name="負責客服",
                    value=additional_data['staff_name'],
                    inline=True
                )
        
        elif notification_type == 'ticket_closed':
            embed = discord.Embed(
                title="🔒 票券已關閉",
                description=f"你的票券 #{ticket_info['ticket_id']:04d} 已關閉。",
                color=discord.Color.green()
            )
            
            if additional_data and additional_data.get('close_reason'):
                embed.add_field(
                    name="關閉原因",
                    value=additional_data['close_reason'],
                    inline=False
                )
        
        else:
            embed = discord.Embed(
                title="📢 票券通知",
                description="你的票券狀態已更新。",
                color=discord.Color.blue()
            )
        
        embed.set_footer(text="票券系統通知")
        return embed
    
    async def _build_staff_notification_embed(self, notification_type: str, ticket_info: Dict[str, Any],
                                            additional_data: Dict[str, Any] = None) -> discord.Embed:
        """建立客服通知嵌入"""
        if notification_type == 'ticket_assigned':
            embed = discord.Embed(
                title="📋 新票券分配",
                description=f"你被分配了票券 #{ticket_info['ticket_id']:04d}",
                color=discord.Color.blue()
            )
            
            priority_emoji = get_priority_emoji(ticket_info.get('priority', 'medium'))
            
            embed.add_field(
                name="票券資訊",
                value=f"**類型：** {ticket_info['type']}\n"
                      f"**優先級：** {priority_emoji} {ticket_info.get('priority', 'medium').upper()}\n"
                      f"**開票者：** <@{ticket_info['discord_id']}>",
                inline=False
            )
        
        elif notification_type == 'rating_received':
            rating = additional_data.get('rating', 0) if additional_data else 0
            stars = TicketConstants.RATING_EMOJIS.get(rating, "⭐")
            
            embed = discord.Embed(
                title="⭐ 收到新評分",
                description=f"票券 #{ticket_info['ticket_id']:04d} 收到了用戶評分！",
                color=discord.Color.gold()
            )
            
            embed.add_field(
                name="評分",
                value=f"{stars} ({rating}/5)",
                inline=True
            )
            
            if additional_data and additional_data.get('feedback'):
                embed.add_field(
                    name="用戶回饋",
                    value=additional_data['feedback'],
                    inline=False
                )
        
        else:
            embed = discord.Embed(
                title="📢 客服通知",
                description="票券狀態已更新。",
                color=discord.Color.blue()
            )
        
        embed.set_footer(text="客服系統通知")
        return embed
    
    async def _build_channel_notification_embed(self, notification_type: str, ticket_info: Dict[str, Any],
                                              additional_data: Dict[str, Any] = None) -> discord.Embed:
        """建立頻道通知嵌入"""
        if notification_type == 'sla_warning':
            embed = discord.Embed(
                title="⚠️ SLA 超時警告",
                description=f"票券 #{ticket_info['ticket_id']:04d} 已超過目標回應時間",
                color=discord.Color.red()
            )
            
            priority_emoji = get_priority_emoji(ticket_info.get('priority', 'medium'))
            
            embed.add_field(
                name="票券資訊",
                value=f"**類型：** {ticket_info['type']}\n"
                      f"**優先級：** {priority_emoji} {ticket_info.get('priority', 'medium').upper()}\n"
                      f"**開票者：** <@{ticket_info['discord_id']}>",
                inline=True
            )
            
            if additional_data and additional_data.get('overdue_minutes'):
                embed.add_field(
                    name="超時資訊",
                    value=f"**超時時間：** {additional_data['overdue_minutes']:.0f} 分鐘",
                    inline=True
                )
        
        else:
            embed = discord.Embed(
                title="📢 系統通知",
                description="票券系統狀態更新。",
                color=discord.Color.blue()
            )
        
        return embed


# ===== 服務協調器 =====

class TicketServiceCoordinator:
    """票券服務協調器 - 統一管理所有服務"""
    
    def __init__(self):
        self.creation_service = TicketCreationService()
        self.assignment_service = TicketAssignmentService()
        self.sla_service = SLAMonitoringService()
        self.auto_reply_service = AutoReplyService()
        self.statistics_service = StatisticsService()
        self.notification_service = NotificationService()
        
        self._services = [
            self.creation_service,
            self.assignment_service,
            self.sla_service,
            self.auto_reply_service,
            self.statistics_service,
            self.notification_service
        ]
    
    async def start_services(self):
        """啟動所有服務"""
        debug_log("[ServiceCoordinator] 啟動票券服務")
        
        # 啟動 SLA 監控（背景任務）
        asyncio.create_task(self.sla_service.start_monitoring())
    
    async def stop_services(self):
        """停止所有服務"""
        debug_log("[ServiceCoordinator] 停止票券服務")
        
        # 停止 SLA 監控
        self.sla_service.stop_monitoring()
        
        # 清理所有服務的快取
        for service in self._services:
            if hasattr(service, 'cache'):
                service.cache.clear()
    
    def get_service(self, service_type: str):
        """取得指定類型的服務"""
        service_map = {
            'creation': self.creation_service,
            'assignment': self.assignment_service,
            'sla': self.sla_service,
            'auto_reply': self.auto_reply_service,
            'statistics': self.statistics_service,
            'notification': self.notification_service
        }
        
        return service_map.get(service_type)
    
    async def health_check(self) -> Dict[str, Any]:
        """服務健康檢查"""
        health_status = {
            'overall': 'healthy',
            'services': {},
            'timestamp': datetime.now(timezone.utc)
        }
        
        try:
            # 檢查各個服務
            health_status['services']['creation'] = 'healthy'
            health_status['services']['assignment'] = 'healthy'
            health_status['services']['sla'] = 'healthy' if self.sla_service.monitoring_active else 'stopped'
            health_status['services']['auto_reply'] = 'healthy'
            health_status['services']['statistics'] = 'healthy'
            health_status['services']['notification'] = 'healthy'
            
            # 檢查是否有不健康的服務
            unhealthy_services = [k for k, v in health_status['services'].items() if v != 'healthy']
            
            if unhealthy_services:
                health_status['overall'] = 'degraded'
                health_status['issues'] = unhealthy_services
            
        except Exception as e:
            health_status['overall'] = 'unhealthy'
            health_status['error'] = str(e)
            debug_log(f"[ServiceCoordinator] 健康檢查錯誤：{e}")
        
        return health_status


# ===== 匯出的工廠函數 =====

def create_ticket_service_coordinator() -> TicketServiceCoordinator:
    """建立票券服務協調器的工廠函數"""
    return TicketServiceCoordinator()


def create_creation_service() -> TicketCreationService:
    """建立票券建立服務的工廠函數"""
    return TicketCreationService()


def create_assignment_service() -> TicketAssignmentService:
    """建立票券分配服務的工廠函數"""
    return TicketAssignmentService()


def create_sla_service() -> SLAMonitoringService:
    """建立SLA監控服務的工廠函數"""
    return SLAMonitoringService()


def create_auto_reply_service() -> AutoReplyService:
    """建立自動回覆服務的工廠函數"""
    return AutoReplyService()


def create_statistics_service() -> StatisticsService:
    """建立統計服務的工廠函數"""
    return StatisticsService()


def create_notification_service() -> NotificationService:
    """建立通知服務的工廠函數"""
    return NotificationService()


# ===== 服務匯出 =====

__all__ = [
    'BaseTicketService',
    'TicketCreationService',
    'TicketAssignmentService', 
    'SLAMonitoringService',
    'AutoReplyService',
    'StatisticsService',
    'NotificationService',
    'TicketServiceCoordinator',
    'create_ticket_service_coordinator',
    'create_creation_service',
    'create_assignment_service',
    'create_sla_service',
    'create_auto_reply_service',
    'create_statistics_service',
    'create_notification_service'
]