# bot/cogs/welcome_listener.py - 歡迎系統事件監聽器
"""
歡迎系統事件監聽器
監聽成員加入/離開事件，處理歡迎訊息和自動身分組分配
"""

import discord
from discord.ext import commands
from typing import Optional, Set
from shared.logger import logger
from datetime import datetime, timezone, timedelta

from bot.db.welcome_dao import WelcomeDAO
from bot.services.welcome_manager import WelcomeManager


class WelcomeListener(commands.Cog):
    """歡迎系統事件監聽器"""
    
    def __init__(self, bot):
        self.bot = bot
        self.welcome_dao = WelcomeDAO()
        self.welcome_manager = WelcomeManager(self.welcome_dao)
        
        # 追蹤最近處理的成員，避免重複處理
        self.recent_joins: Set[int] = set()
        self.recent_updates: Set[int] = set()
    
    async def _handle_welcome_with_tracking(self, member: discord.Member, event_type: str = "join"):
        """處理歡迎事件並進行追蹤，避免重複處理"""
        member_id = member.id
        current_time = datetime.now(timezone.utc)
        
        # 檢查是否在最近 30 秒內已處理過此成員
        if member_id in self.recent_joins:
            logger.debug(f"⏭️ 跳過重複處理 - {member} ({event_type})")
            return
        
        # 添加到追蹤列表
        self.recent_joins.add(member_id)
        
        try:
            logger.info(f"🎉 處理{event_type}事件: {member} ({member.id}) -> {member.guild.name} ({member.guild.id})")
            
            # 處理歡迎事件
            result = await self.welcome_manager.handle_member_join(member)
            
            # 記錄結果
            if result['success']:
                actions = []
                if result['welcome_sent']:
                    actions.append("歡迎訊息已發送")
                if result['dm_sent']:
                    actions.append("私訊已發送")
                if result['roles_assigned']:
                    actions.append(f"分配了 {len(result['roles_assigned'])} 個身分組")
                
                if actions:
                    logger.info(f"✅ 歡迎處理完成 - {member}: {', '.join(actions)}")
                else:
                    logger.info(f"ℹ️ 歡迎系統未啟用或未設定 - {member}")
            else:
                logger.error(f"❌ 歡迎處理失敗 - {member}: {result.get('errors', [])}")
                
        except Exception as e:
            logger.error(f"❌ 處理{event_type}事件錯誤: {e}")
            import traceback
            logger.error(traceback.format_exc())
        finally:
            # 30 秒後移除追蹤
            import asyncio
            asyncio.create_task(self._cleanup_tracking(member_id, 30))
    
    async def _cleanup_tracking(self, member_id: int, delay: int):
        """清理追蹤記錄"""
        import asyncio
        await asyncio.sleep(delay)
        self.recent_joins.discard(member_id)
        self.recent_updates.discard(member_id)
    
    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        """成員加入事件 - 主要處理方法"""
        if member.bot:
            logger.debug(f"忽略機器人加入: {member}")
            return  # 忽略機器人
        
        logger.info(f"🎯 on_member_join 事件觸發: {member} -> {member.guild.name}")
        await self._handle_welcome_with_tracking(member, "加入")
    
    @commands.Cog.listener()
    async def on_member_update(self, before: discord.Member, after: discord.Member):
        """成員更新事件 - 可能捕捉到重新加入的情況"""
        if after.bot:
            return  # 忽略機器人
        
        # 檢查是否是因為身分組或狀態變化而觸發的更新
        # 這裡我們主要關注可能是重新加入的情況
        member_id = after.id
        
        # 如果最近沒有處理過此成員，且成員狀態符合新加入條件
        if (member_id not in self.recent_joins and 
            member_id not in self.recent_updates and
            after.joined_at and 
            (datetime.now(timezone.utc) - after.joined_at).total_seconds() < 300):  # 5分鐘內
            
            logger.info(f"🔄 檢測到可能的重新加入: {after}")
            self.recent_updates.add(member_id)
            await self._handle_welcome_with_tracking(after, "重新加入")
            
            # 清理追蹤
            import asyncio
            asyncio.create_task(self._cleanup_tracking(member_id, 30))
    
    @commands.Cog.listener()
    async def on_guild_available(self, guild: discord.Guild):
        """伺服器可用事件 - 檢查新成員"""
        try:
            logger.debug(f"伺服器 {guild.name} 變為可用，檢查新成員...")
            
            # 檢查是否有在 Bot 離線期間加入的新成員
            current_time = datetime.now(timezone.utc)
            recent_threshold = current_time - timedelta(minutes=10)
            
            for member in guild.members:
                if (member.bot or 
                    not member.joined_at or 
                    member.joined_at < recent_threshold or
                    member.id in self.recent_joins):
                    continue
                
                logger.info(f"🔍 發現可能錯過的新成員: {member}")
                await self._handle_welcome_with_tracking(member, "延遲處理")
                
        except Exception as e:
            logger.error(f"處理伺服器可用事件錯誤: {e}")
    
    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member):
        """成員離開事件"""
        if member.bot:
            return  # 忽略機器人
        
        try:
            logger.info(f"成員離開: {member} ({member.id}) <- {member.guild.name}")
            
            # 處理離開事件
            result = await self.welcome_manager.handle_member_leave(member)
            
            # 記錄結果
            if result['success']:
                if result['leave_sent']:
                    logger.info(f"離開訊息已發送 - {member}")
            else:
                logger.warning(f"離開處理失敗 - {member}: {result.get('errors', [])}")
                
        except Exception as e:
            logger.error(f"處理成員離開事件錯誤: {e}")
    
    @commands.Cog.listener()
    async def on_ready(self):
        """Bot準備完成事件 - 處理 RESUME 情況"""
        logger.info("🎉 歡迎系統監聽器已啟動")
        
        # 清理追蹤記錄（重要：RESUME 後重置狀態）
        self.recent_joins.clear()
        self.recent_updates.clear()
        logger.info("🧹 已清理歡迎系統追蹤記錄")
        
        # 檢查是否有錯過的新成員（最近10分鐘內加入的）
        try:
            from datetime import datetime, timezone, timedelta
            current_time = datetime.now(timezone.utc)
            recent_threshold = current_time - timedelta(minutes=10)
            
            for guild in self.bot.guilds:
                for member in guild.members:
                    if (not member.bot and 
                        member.joined_at and 
                        member.joined_at > recent_threshold):
                        
                        logger.info(f"🔍 檢查可能錯過的新成員: {member} in {guild.name}")
                        # 給一點延遲避免大量同時處理
                        import asyncio
                        await asyncio.sleep(0.1)
                        await self._handle_welcome_with_tracking(member, "RESUME後檢查")
                        
        except Exception as e:
            logger.error(f"❌ RESUME後檢查新成員時發生錯誤: {e}")


async def setup(bot):
    """載入擴展"""
    await bot.add_cog(WelcomeListener(bot))