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