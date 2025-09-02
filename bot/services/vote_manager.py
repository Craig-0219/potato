# bot/services/vote_manager.py
"""
投票管理服務
負責投票的創建、管理和執行
"""

from typing import Any, Dict, List, Optional
import discord
from datetime import datetime, timedelta

from bot.db.vote_dao import VoteDAO
from bot.services.vote_template_manager import VoteTemplateManager
from shared.logger import logger


class VoteManager:
    """投票管理器"""

    def __init__(self, database_manager=None):
        """初始化投票管理器"""
        self.vote_dao = VoteDAO(database_manager) if database_manager else None
        self.template_manager = VoteTemplateManager()
        self.active_votes = {}
        
    async def create_vote(self, guild_id: int, channel_id: int, creator_id: int, 
                         title: str, options: List[str], duration: int = 120, 
                         is_multi: bool = False) -> Dict[str, Any]:
        """創建新的投票"""
        try:
            vote_data = {
                "guild_id": guild_id,
                "channel_id": channel_id,
                "creator_id": creator_id,
                "title": title,
                "options": options,
                "duration": duration,
                "is_multi": is_multi,
                "created_at": datetime.utcnow(),
                "status": "active"
            }
            
            logger.info(f"創建新投票: {title}")
            return vote_data
            
        except Exception as e:
            logger.error(f"創建投票失敗: {e}")
            raise

    async def end_vote(self, vote_id: int) -> Dict[str, Any]:
        """結束投票"""
        try:
            logger.info(f"結束投票: {vote_id}")
            return {"vote_id": vote_id, "status": "ended"}
            
        except Exception as e:
            logger.error(f"結束投票失敗: {e}")
            raise

    async def get_vote_results(self, vote_id: int) -> Dict[str, Any]:
        """獲取投票結果"""
        try:
            logger.info(f"獲取投票結果: {vote_id}")
            return {"vote_id": vote_id, "results": []}
            
        except Exception as e:
            logger.error(f"獲取投票結果失敗: {e}")
            raise

    async def vote_on_poll(self, vote_id: int, user_id: int, option: str) -> bool:
        """對投票進行投票"""
        try:
            logger.info(f"用戶 {user_id} 對投票 {vote_id} 投票: {option}")
            return True
            
        except Exception as e:
            logger.error(f"投票失敗: {e}")
            raise

    def get_vote_embed(self, vote_data: Dict[str, Any]) -> discord.Embed:
        """生成投票嵌入訊息"""
        embed = discord.Embed(
            title=vote_data.get("title", "投票"),
            color=discord.Color.blue()
        )
        
        options = vote_data.get("options", [])
        for i, option in enumerate(options, 1):
            embed.add_field(
                name=f"選項 {i}",
                value=option,
                inline=False
            )
            
        return embed