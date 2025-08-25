# bot/cogs/web_auth_core.py
"""
Web 認證相關指令
提供 Discord 用戶設定 Web 密碼和管理 API 金鑰的功能
"""

import discord
from discord.ext import commands
from discord import app_commands
from typing import Optional, List
from datetime import datetime, timezone

from shared.logger import logger
from bot.services.auth_manager import auth_manager
from bot.utils.interaction_helper import SafeInteractionHandler
from bot.utils.embed_builder import EmbedBuilder

class WebAuthCommands(commands.Cog):
    """Web 認證指令組"""
    
    def __init__(self, bot):
        self.bot = bot
    
    @app_commands.command(name="setup-web-password", description="設定 Web 介面登入密碼")
    @app_commands.describe(password="設定的密碼 (至少 6 個字元)")
    async def setup_web_password(self, interaction: discord.Interaction, password: str):
        """設定 Web 介面登入密碼"""
        try:
            if not await SafeInteractionHandler.safe_defer(interaction, ephemeral=True):
                
            await SafeInteractionHandler.handle_interaction_error(interaction, e, "設定 Web 密碼")
    
    @app_commands.command(name="create-api-key", description="創建 API 金鑰")
    @app_commands.describe(
        name="API 金鑰名稱",
        expires_days="過期天數 (0 表示永不過期，預設 30 天)"
    )
    async def create_api_key(self, interaction: discord.Interaction, 
                           name: str, expires_days: int = 30):
        """創建 API 金鑰"""
        try:
            if not await SafeInteractionHandler.safe_defer(interaction, ephemeral=True):
                
            await SafeInteractionHandler.handle_interaction_error(interaction, e, "創建 API 金鑰")
    
    @app_commands.command(name="list-api-keys", description="列出我的 API 金鑰")
    async def list_api_keys(self, interaction: discord.Interaction):
        """列出用戶的 API 金鑰"""
        try:
            if not await SafeInteractionHandler.safe_defer(interaction, ephemeral=True):
                
            await SafeInteractionHandler.handle_interaction_error(interaction, e, "列出 API 金鑰")
    
    @app_commands.command(name="revoke-api-key", description="撤銷 API 金鑰")
    @app_commands.describe(key_id="要撤銷的 API 金鑰 ID")
    async def revoke_api_key(self, interaction: discord.Interaction, key_id: str):
        """撤銷 API 金鑰"""
        try:
            if not await SafeInteractionHandler.safe_defer(interaction, ephemeral=True):
                
            await SafeInteractionHandler.handle_interaction_error(interaction, e, "撤銷 API 金鑰")
    
    @app_commands.command(name="web-login-info", description="顯示 Web 登入資訊")
    async def web_login_info(self, interaction: discord.Interaction):
        """顯示 Web 登入資訊"""
        try:
            if not await SafeInteractionHandler.safe_defer(interaction, ephemeral=True):
                
            await SafeInteractionHandler.handle_interaction_error(interaction, e, "顯示 Web 登入資訊")

async def setup(bot):
    """載入 Cog"""
    await bot.add_cog(WebAuthCommands(bot))