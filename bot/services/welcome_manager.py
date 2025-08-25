# bot/services/welcome_manager.py - 歡迎系統管理服務
"""
歡迎系統管理服務
處理成員加入/離開、自動身分組分配、歡迎訊息發送等業務邏輯
"""

import discord
import re
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timezone
from shared.logger import logger

from bot.db.welcome_dao import WelcomeDAO

class WelcomeManager:
    """歡迎系統管理器"""
    
    def __init__(self, welcome_dao: WelcomeDAO = None):
        self.welcome_dao = welcome_dao or WelcomeDAO()
        
        # 預設訊息模板
        self.default_welcome_message = """🎉 歡迎 {user_mention} 加入 **{guild_name}**！

你是我們的第 **{member_count}** 位成員！

📋 請確認你已閱讀規則
🎯 如有問題請建立票券尋求協助
💬 在頻道中與大家互動交流

希望你在這裡有愉快的體驗！ ✨"""

        self.default_leave_message = """👋 **{username}** 離開了 **{guild_name}**

加入時間：{join_date}
成員編號：#{member_count}

希望未來有機會再見！"""

        self.default_dm_message = """👋 歡迎加入 **{guild_name}**！

感謝你成為我們社群的一員。如果你有任何問題或需要協助，請隨時在伺服器中建立票券。

我們期待與你的互動！ 🎉"""

    # ========== 成員事件處理 ==========
    
    async def handle_member_join(self, member: discord.Member) -> Dict[str, Any]:
        """處理成員加入事件"""
        guild_id = member.guild.id
        user_id = member.id
        username = str(member)
        
        result = {
            'success': True,
            'welcome_sent': False,
            'dm_sent': False,
            'roles_assigned': [],
            'errors': []
        }
        
        try:
            # 取得歡迎設定
            settings = await self.welcome_dao.get_welcome_settings(guild_id)
            
            if not settings:
                logger.info(f"📋 歡迎設定不存在，建議設定歡迎系統 - 伺服器: {guild_id}")
                return result
            
            if not settings.get('is_enabled'):
                
            result['success'] = False
            result['errors'].append(str(e))
            
            # 記錄錯誤事件
            await self.welcome_dao.log_welcome_event(
                guild_id=guild_id,
                user_id=user_id,
                username=username,
                action_type='join',
                error_message=str(e)
            )
        
        return result
    
    async def handle_member_leave(self, member: discord.Member) -> Dict[str, Any]:
        """處理成員離開事件"""
        guild_id = member.guild.id
        user_id = member.id
        username = str(member)
        
        result = {
            'success': True,
            'leave_sent': False,
            'errors': []
        }
        
        try:
            # 取得歡迎設定
            settings = await self.welcome_dao.get_welcome_settings(guild_id)
            
            if not settings or not settings.get('is_enabled'):
                return result
            
            # 發送離開訊息
            if settings.get('leave_channel_id') and settings.get('leave_message'):
                leave_sent = await self._send_leave_message(member, settings)
                result['leave_sent'] = leave_sent
                
                if not leave_sent:
                    result['errors'].append("無法發送離開訊息")
            
            # 記錄事件
            await self.welcome_dao.log_welcome_event(
                guild_id=guild_id,
                user_id=user_id,
                username=username,
                action_type='leave',
                welcome_sent=result['leave_sent'],
                error_message='; '.join(result['errors']) if result['errors'] else None
            )
            
            logger.info(f"處理成員離開完成: {username} <- {guild_id}")
            
        except Exception as e:
            logger.error(f"處理成員離開錯誤: {e}")
            result['success'] = False
            result['errors'].append(str(e))
            
            # 記錄錯誤事件
            await self.welcome_dao.log_welcome_event(
                guild_id=guild_id,
                user_id=user_id,
                username=username,
                action_type='leave',
                error_message=str(e)
            )
        
        return result
    
    # ========== 內部方法 ==========
    
    async def _assign_auto_roles(self, member: discord.Member, role_ids: List[int]) -> List[int]:
        """分配自動身分組"""
        assigned_roles = []
        
        try:
            for role_id in role_ids:
                role = member.guild.get_role(role_id)
                if role and role < member.guild.me.top_role:  # 檢查階層
                    try:
                        await member.add_roles(role, reason="自動身分組分配")
                        assigned_roles.append(role_id)

        except Exception as e:
            logger.error(f"自動身分組分配錯誤: {e}")
        
        return assigned_roles
    
    async def _send_welcome_message(self, member: discord.Member, settings: Dict[str, Any]) -> bool:
        """發送歡迎訊息到頻道"""
        try:
            channel = member.guild.get_channel(settings['welcome_channel_id'])
            if not channel:
                logger.warning(f"歡迎頻道不存在: {settings['welcome_channel_id']}")
                return False
            
            # 格式化訊息
            message_content = await self._format_message(
                settings['welcome_message'], 
                member, 
                'welcome'
            )
            
            # 根據設定決定發送格式
            if settings.get('welcome_embed_enabled', True):
                embed = await self._create_welcome_embed(member, message_content, settings)
                await channel.send(content=member.mention, embed=embed)
            else:
                await channel.send(message_content)
            
            return True
            
        except discord.Forbidden:
            logger.warning(f"沒有權限發送歡迎訊息到頻道: {settings['welcome_channel_id']}")
            return False
        except Exception as e:
            logger.error(f"發送歡迎訊息錯誤: {e}")
            return False
    
    async def _send_leave_message(self, member: discord.Member, settings: Dict[str, Any]) -> bool:
        """發送離開訊息到頻道"""
        try:
            channel = member.guild.get_channel(settings['leave_channel_id'])
            if not channel:
                logger.warning(f"離開頻道不存在: {settings['leave_channel_id']}")
                return False
            
            # 格式化訊息
            message_content = await self._format_message(
                settings['leave_message'], 
                member, 
                'leave'
            )
            
            # 創建離開嵌入訊息
            embed = discord.Embed(
                description=message_content,
                color=0xff6b6b,  # 紅色調
                timestamp=datetime.now(timezone.utc)
            )
            
            embed.set_author(
                name=f"{member.display_name} 離開了伺服器",
                icon_url=member.display_avatar.url
            )
            
            embed.set_footer(text=f"成員 ID: {member.id}")
            
            await channel.send(embed=embed)
            return True
            
        except discord.Forbidden:
            logger.warning(f"沒有權限發送離開訊息到頻道: {settings['leave_channel_id']}")
            return False
        except Exception as e:
            logger.error(f"發送離開訊息錯誤: {e}")
            return False
    
    async def _send_welcome_dm(self, member: discord.Member, settings: Dict[str, Any]) -> bool:
        """發送私訊歡迎"""
        try:
            # 格式化私訊內容
            dm_content = await self._format_message(
                settings['welcome_dm_message'], 
                member, 
                'dm'
            )
            
            embed = discord.Embed(
                title=f"歡迎加入 {member.guild.name}！",
                description=dm_content,
                color=settings.get('welcome_color', 0x00ff00),
                timestamp=datetime.now(timezone.utc)
            )
            
            if settings.get('welcome_thumbnail_url'):
                embed.set_thumbnail(url=settings['welcome_thumbnail_url'])
            elif member.guild.icon:
                embed.set_thumbnail(url=member.guild.icon.url)
            
            embed.set_footer(text=f"來自 {member.guild.name}")
            
            await member.send(embed=embed)
            return True
            
        except discord.Forbidden:
            
            return False
    
    async def _create_welcome_embed(self, member: discord.Member, content: str, 
                                  settings: Dict[str, Any]) -> discord.Embed:
        """創建歡迎嵌入訊息"""
        embed = discord.Embed(
            description=content,
            color=settings.get('welcome_color', 0x00ff00),
            timestamp=datetime.now(timezone.utc)
        )
        
        embed.set_author(
            name=f"歡迎 {member.display_name}！",
            icon_url=member.display_avatar.url
        )
        
        # 設定圖片
        if settings.get('welcome_image_url'):
            embed.set_image(url=settings['welcome_image_url'])
        
        if settings.get('welcome_thumbnail_url'):
            embed.set_thumbnail(url=settings['welcome_thumbnail_url'])
        elif member.guild.icon:
            embed.set_thumbnail(url=member.guild.icon.url)
        
        embed.set_footer(
            text=f"成員 #{member.guild.member_count} • 加入於",
            icon_url=member.guild.icon.url if member.guild.icon else None
        )
        
        return embed
    
    async def _format_message(self, message: str, member: discord.Member, 
                            message_type: str) -> str:
        """格式化訊息模板"""
        if not message:
            if message_type == 'welcome':
                message = self.default_welcome_message
            elif message_type == 'leave':
                message = self.default_leave_message
            elif message_type == 'dm':
                message = self.default_dm_message
        
        # 變數替換
        variables = {
            '{user_mention}': member.mention,
            '{user_name}': member.display_name,
            '{username}': str(member),
            '{user_id}': str(member.id),
            '{guild_name}': member.guild.name,
            '{guild_id}': str(member.guild.id),
            '{member_count}': str(member.guild.member_count),
            '{join_date}': member.joined_at.strftime('%Y-%m-%d %H:%M:%S') if member.joined_at else '未知',
            '{current_date}': datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S'),
            '{current_time}': datetime.now(timezone.utc).strftime('%H:%M:%S')
        }
        
        formatted_message = message
        for variable, value in variables.items():
            formatted_message = formatted_message.replace(variable, value)
        
        return formatted_message
    
    # ========== 設定管理 ==========
    
    async def update_welcome_settings(self, guild_id: int, **kwargs) -> Tuple[bool, str]:
        """更新歡迎設定"""
        try:
            # 取得現有設定
            current_settings = await self.welcome_dao.get_welcome_settings(guild_id)
            if not current_settings:
                current_settings = {}
            
            # 更新設定
            current_settings.update(kwargs)
            
            success = await self.welcome_dao.upsert_welcome_settings(guild_id, current_settings)
            
            if success:
                return True, "歡迎設定更新成功"
            else:
                return False, "更新歡迎設定失敗"
                
        except Exception as e:
            logger.error(f"更新歡迎設定錯誤: {e}")
            return False, f"更新過程中發生錯誤：{str(e)}"
    
    async def set_welcome_channel(self, guild_id: int, channel_id: Optional[int]) -> Tuple[bool, str]:
        """設定歡迎頻道"""
        try:
            success = await self.welcome_dao.update_welcome_channel(guild_id, channel_id)
            
            if success:
                if channel_id:
                    return True, f"已設定歡迎頻道：<#{channel_id}>"
                else:
                    return True, "已清除歡迎頻道設定"
            else:
                return False, "設定歡迎頻道失敗"
                
        except Exception as e:
            logger.error(f"設定歡迎頻道錯誤: {e}")
            return False, f"設定過程中發生錯誤：{str(e)}"
    
    async def set_leave_channel(self, guild_id: int, channel_id: Optional[int]) -> Tuple[bool, str]:
        """設定離開頻道"""
        try:
            success = await self.welcome_dao.update_leave_channel(guild_id, channel_id)
            
            if success:
                if channel_id:
                    return True, f"已設定離開頻道：<#{channel_id}>"
                else:
                    return True, "已清除離開頻道設定"
            else:
                return False, "設定離開頻道失敗"
                
        except Exception as e:
            logger.error(f"設定離開頻道錯誤: {e}")
            return False, f"設定過程中發生錯誤：{str(e)}"
    
    async def set_auto_roles(self, guild_id: int, role_ids: List[int]) -> Tuple[bool, str]:
        """設定自動身分組"""
        try:
            success = await self.welcome_dao.update_auto_roles(guild_id, role_ids)
            
            if success:
                if role_ids:
                    role_mentions = [f"<@&{role_id}>" for role_id in role_ids]
                    return True, f"已設定自動身分組：{', '.join(role_mentions)}"
                else:
                    return True, "已清除自動身分組設定"
            else:
                return False, "設定自動身分組失敗"
                
        except Exception as e:
            logger.error(f"設定自動身分組錯誤: {e}")
            return False, f"設定過程中發生錯誤：{str(e)}"
    
    # ========== 統計與查詢 ==========
    
    async def get_welcome_statistics(self, guild_id: int, days: int = 30) -> Dict[str, Any]:
        """取得歡迎統計"""
        try:
            return await self.welcome_dao.get_welcome_statistics(guild_id, days)
        except Exception as e:
            logger.error(f"取得歡迎統計錯誤: {e}")
            return {}
    
    async def get_welcome_logs(self, guild_id: int, limit: int = 20) -> List[Dict[str, Any]]:
        """取得歡迎日誌"""
        try:
            return await self.welcome_dao.get_welcome_logs(guild_id, limit)
        except Exception as e:
            logger.error(f"取得歡迎日誌錯誤: {e}")
            return []
    
    async def test_welcome_message(self, guild: discord.Guild, user: discord.Member) -> Dict[str, Any]:
        """測試歡迎訊息"""
        try:
            settings = await self.welcome_dao.get_welcome_settings(guild.id)
            if not settings:
                return {'success': False, 'message': '未找到歡迎設定'}
            
            # 格式化測試訊息
            test_message = await self._format_message(
                settings.get('welcome_message', self.default_welcome_message),
                user,
                'welcome'
            )
            
            return {
                'success': True,
                'formatted_message': test_message,
                'settings': settings
            }
            
        except Exception as e:
            logger.error(f"測試歡迎訊息錯誤: {e}")
            return {'success': False, 'message': str(e)}