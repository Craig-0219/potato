# bot/cogs/image_tools_core.py - 圖片處理工具指令模組
"""
圖片處理工具指令模組 v2.2.0
提供迷因製作、圖片特效、頭像處理等功能的Discord指令
"""

import discord
from discord.ext import commands
from discord import app_commands
from typing import Dict, List, Optional, Any, Tuple
import asyncio
import time
import io
from datetime import datetime, timezone

from bot.services.image_processor import image_processor, ImageEffect, MemeTemplate
from bot.services.economy_manager import EconomyManager
from bot.utils.embed_builder import EmbedBuilder
from shared.cache_manager import cache_manager
from shared.prometheus_metrics import prometheus_metrics, track_command_execution
from shared.logger import logger

class ImageToolsCog(commands.Cog):
    """圖片處理工具功能"""
    
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.economy_manager = EconomyManager()
        
        # 圖片處理費用 (金幣)
        self.processing_costs = {
            "effect": 8,
            "meme": 12,
            "avatar_frame": 10,
            "custom_edit": 15
        }
        
        # 每日免費額度
        self.daily_free_quota = 5
        
        logger.info("🖼️ 圖片處理工具指令模組初始化完成")

    # ========== 圖片特效 ==========

    @app_commands.command(name="image_effect", description="為圖片添加特效")
    @app_commands.describe(
        image="要處理的圖片 (可以是附件或圖片URL)",
        effect="特效類型",
        intensity="特效強度 (0.1-2.0)"
    )
    @app_commands.choices(effect=[
        app_commands.Choice(name="模糊", value="blur"),
        app_commands.Choice(name="銳化", value="sharpen"),
        app_commands.Choice(name="復古", value="vintage"),
        app_commands.Choice(name="黑白", value="grayscale"),
        app_commands.Choice(name="復古色調", value="sepia"),
        app_commands.Choice(name="霓虹", value="neon"),
        app_commands.Choice(name="浮雕", value="emboss"),
        app_commands.Choice(name="邊緣增強", value="edge_enhance")
    ])
    async def apply_image_effect(self, interaction: discord.Interaction, 
                               image: discord.Attachment = None,
                               effect: str = "vintage", 
                               intensity: float = 1.0):
        """應用圖片特效"""
        try:
            await interaction.response.defer()
            
            # 檢查使用權限
            can_use, cost_info = await self._check_usage_permission(
                interaction.user.id, interaction.guild.id, "effect"
            )
            
            if not can_use:
                embed = EmbedBuilder.build(
                    title="❌ 使用受限",
                    description=cost_info["message"],
                    color=0xFF0000
                )
                await interaction.followup.send(embed=embed, ephemeral=True)
                return
            
            # 獲取圖片URL
            image_url = await self._get_image_url(interaction, image)
            if not image_url:
                await interaction.followup.send(
                    "❌ 請提供圖片附件或在有圖片的消息上使用此指令！", 
                    ephemeral=True
                )
                return
            
            # 驗證強度參數
            intensity = max(0.1, min(2.0, intensity))
            
            # 處理圖片
            try:
                effect_enum = ImageEffect(effect)
            except ValueError:
                effect_enum = ImageEffect.VINTAGE
            
            result = await image_processor.apply_effect(image_url, effect_enum, intensity)
            
            if result.success:
                # 扣除費用
                if cost_info["cost"] > 0:
                    await self.economy_manager.add_coins(
                        interaction.user.id, interaction.guild.id, -cost_info["cost"]
                    )
                
                # 記錄使用量
                await self._record_daily_usage(interaction.user.id)
                
                # 創建文件
                file = discord.File(
                    io.BytesIO(result.image_data),
                    filename=f"effect_{effect}_{int(time.time())}.png"
                )
                
                embed = EmbedBuilder.build(
                    title=f"🎨 圖片特效 - {effect.title()}",
                    description=f"特效強度: {intensity}",
                    color=0x9B59B6
                )
                
                embed.add_field(
                    name="📊 處理資訊",
                    value=f"處理時間: {result.processing_time:.2f}秒\n"
                          f"圖片大小: {result.file_size/1024:.1f} KB\n"
                          f"解析度: {result.size[0]}×{result.size[1]}" +
                          (f"\n消耗金幣: {cost_info['cost']}🪙" if cost_info["cost"] > 0 else ""),
                    inline=True
                )
                
                embed.set_footer(text=f"處理者: {interaction.user.display_name}")
                
                await interaction.followup.send(embed=embed, file=file)
                
            else:
                embed = EmbedBuilder.build(
                    title="❌ 圖片處理失敗",
                    description=result.error_message or "處理過程中發生未知錯誤",
                    color=0xFF0000
                )
                await interaction.followup.send(embed=embed, ephemeral=True)
            
            # 記錄指標
            track_command_execution("image_effect", interaction.guild.id)
            
        except Exception as e:
            logger.error(f"❌ 圖片特效錯誤: {e}")
            await interaction.followup.send("❌ 處理圖片時發生錯誤，請稍後再試。", ephemeral=True)

    # ========== 迷因製作 ==========

    @app_commands.command(name="create_meme", description="創建迷因圖片")
    @app_commands.describe(
        template="迷因模板",
        top_text="上方文字",
        bottom_text="下方文字",
        background_image="背景圖片 (可選)"
    )
    @app_commands.choices(template=[
        app_commands.Choice(name="Drake指向", value="drake"),
        app_commands.Choice(name="自定義文字", value="custom_text"),
        app_commands.Choice(name="兩個按鈕", value="two_buttons"),
        app_commands.Choice(name="改變我的想法", value="change_my_mind")
    ])
    async def create_meme(self, interaction: discord.Interaction,
                         template: str,
                         top_text: str,
                         bottom_text: str = "",
                         background_image: discord.Attachment = None):
        """創建迷因圖片"""
        try:
            await interaction.response.defer()
            
            # 檢查使用權限
            can_use, cost_info = await self._check_usage_permission(
                interaction.user.id, interaction.guild.id, "meme"
            )
            
            if not can_use:
                embed = EmbedBuilder.build(
                    title="❌ 使用受限",
                    description=cost_info["message"],
                    color=0xFF0000
                )
                await interaction.followup.send(embed=embed, ephemeral=True)
                return
            
            # 檢查文字長度
            if len(top_text) > 100 or len(bottom_text) > 100:
                await interaction.followup.send(
                    "❌ 文字過長！每行文字請限制在100字符內。", 
                    ephemeral=True
                )
                return
            
            # 獲取背景圖片URL（如果有）
            background_url = None
            if background_image:
                if background_image.content_type.startswith('image/'):
                    background_url = background_image.url
                else:
                    await interaction.followup.send(
                        "❌ 背景文件必須是圖片格式！", 
                        ephemeral=True
                    )
                    return
            
            # 準備文字列表
            texts = [top_text]
            if bottom_text.strip():
                texts.append(bottom_text)
            
            # 創建迷因
            try:
                template_enum = MemeTemplate(template)
            except ValueError:
                template_enum = MemeTemplate.CUSTOM_TEXT
            
            result = await image_processor.create_meme(
                template_enum, texts, background_url
            )
            
            if result.success:
                # 扣除費用
                if cost_info["cost"] > 0:
                    await self.economy_manager.add_coins(
                        interaction.user.id, interaction.guild.id, -cost_info["cost"]
                    )
                
                # 記錄使用量
                await self._record_daily_usage(interaction.user.id)
                
                # 創建文件
                file = discord.File(
                    io.BytesIO(result.image_data),
                    filename=f"meme_{template}_{int(time.time())}.png"
                )
                
                embed = EmbedBuilder.build(
                    title="😂 迷因創作完成！",
                    description=f"模板: {template.title()}",
                    color=0xE74C3C
                )
                
                embed.add_field(
                    name="📝 文字內容",
                    value=f"上方: {top_text}\n" + 
                          (f"下方: {bottom_text}" if bottom_text else ""),
                    inline=True
                )
                
                embed.add_field(
                    name="📊 處理資訊",
                    value=f"處理時間: {result.processing_time:.2f}秒\n"
                          f"圖片大小: {result.file_size/1024:.1f} KB" +
                          (f"\n消耗金幣: {cost_info['cost']}🪙" if cost_info["cost"] > 0 else ""),
                    inline=True
                )
                
                embed.set_footer(text=f"創作者: {interaction.user.display_name}")
                
                await interaction.followup.send(embed=embed, file=file)
                
            else:
                embed = EmbedBuilder.build(
                    title="❌ 迷因創建失敗",
                    description=result.error_message or "創建過程中發生未知錯誤",
                    color=0xFF0000
                )
                await interaction.followup.send(embed=embed, ephemeral=True)
            
            # 記錄指標
            track_command_execution("create_meme", interaction.guild.id)
            
        except Exception as e:
            logger.error(f"❌ 迷因創建錯誤: {e}")
            await interaction.followup.send("❌ 創建迷因時發生錯誤，請稍後再試。", ephemeral=True)

    # ========== 頭像處理 ==========

    @app_commands.command(name="avatar_frame", description="為頭像添加炫酷框架")
    @app_commands.describe(
        user="要處理頭像的用戶 (默認為自己)",
        frame_style="框架樣式"
    )
    @app_commands.choices(frame_style=[
        app_commands.Choice(name="圓形", value="circle"),
        app_commands.Choice(name="方形", value="square"),
        app_commands.Choice(name="六邊形", value="hexagon")
    ])
    async def create_avatar_frame(self, interaction: discord.Interaction,
                                user: discord.User = None,
                                frame_style: str = "circle"):
        """創建頭像框架"""
        try:
            await interaction.response.defer()
            
            # 檢查使用權限
            can_use, cost_info = await self._check_usage_permission(
                interaction.user.id, interaction.guild.id, "avatar_frame"
            )
            
            if not can_use:
                embed = EmbedBuilder.build(
                    title="❌ 使用受限",
                    description=cost_info["message"],
                    color=0xFF0000
                )
                await interaction.followup.send(embed=embed, ephemeral=True)
                return
            
            # 獲取目標用戶
            target_user = user or interaction.user
            avatar_url = target_user.display_avatar.url
            
            # 處理頭像
            result = await image_processor.create_avatar_frame(avatar_url, frame_style)
            
            if result.success:
                # 扣除費用
                if cost_info["cost"] > 0:
                    await self.economy_manager.add_coins(
                        interaction.user.id, interaction.guild.id, -cost_info["cost"]
                    )
                
                # 記錄使用量
                await self._record_daily_usage(interaction.user.id)
                
                # 創建文件
                file = discord.File(
                    io.BytesIO(result.image_data),
                    filename=f"avatar_{frame_style}_{target_user.id}.png"
                )
                
                embed = EmbedBuilder.build(
                    title=f"🖼️ {target_user.display_name} 的炫酷頭像",
                    description=f"框架樣式: {frame_style.title()}",
                    color=0x3498DB
                )
                
                embed.add_field(
                    name="📊 處理資訊",
                    value=f"處理時間: {result.processing_time:.2f}秒\n"
                          f"圖片大小: {result.file_size/1024:.1f} KB" +
                          (f"\n消耗金幣: {cost_info['cost']}🪙" if cost_info["cost"] > 0 else ""),
                    inline=True
                )
                
                embed.set_footer(text=f"處理者: {interaction.user.display_name}")
                
                await interaction.followup.send(embed=embed, file=file)
                
            else:
                embed = EmbedBuilder.build(
                    title="❌ 頭像處理失敗",
                    description=result.error_message or "處理過程中發生未知錯誤",
                    color=0xFF0000
                )
                await interaction.followup.send(embed=embed, ephemeral=True)
            
            # 記錄指標
            track_command_execution("avatar_frame", interaction.guild.id)
            
        except Exception as e:
            logger.error(f"❌ 頭像處理錯誤: {e}")
            await interaction.followup.send("❌ 處理頭像時發生錯誤，請稍後再試。", ephemeral=True)

    # ========== 使用統計 ==========

    @app_commands.command(name="image_usage", description="查看圖片處理使用統計")
    async def image_usage_stats(self, interaction: discord.Interaction):
        """圖片處理使用統計"""
        try:
            user_id = interaction.user.id
            
            # 獲取使用統計
            daily_usage = await self._get_daily_usage(user_id)
            
            # 獲取經濟狀態
            economy = await self.economy_manager.get_user_economy(user_id, interaction.guild.id)
            
            embed = EmbedBuilder.build(
                title="🖼️ 圖片處理使用統計",
                description=f"{interaction.user.display_name} 的圖片處理服務使用情況",
                color=0x9B59B6
            )
            
            embed.set_thumbnail(url=interaction.user.display_avatar.url)
            
            # 今日使用情況
            remaining_free = max(0, self.daily_free_quota - daily_usage)
            embed.add_field(
                name="📅 今日使用",
                value=f"已使用: {daily_usage}/{self.daily_free_quota} (免費)\n"
                      f"剩餘免費額度: {remaining_free}",
                inline=True
            )
            
            # 經濟狀態
            embed.add_field(
                name="💰 經濟狀態",
                value=f"金幣餘額: {economy.get('coins', 0):,}🪙\n"
                      f"可用於圖片處理服務",
                inline=True
            )
            
            # 費用說明
            cost_text = []
            for service, cost in self.processing_costs.items():
                service_name = {
                    "effect": "🎨 圖片特效",
                    "meme": "😂 迷因製作",
                    "avatar_frame": "🖼️ 頭像框架",
                    "custom_edit": "✨ 自定義編輯"
                }.get(service, service)
                
                cost_text.append(f"{service_name}: {cost}🪙")
            
            embed.add_field(
                name="💳 服務費用",
                value="\n".join(cost_text),
                inline=True
            )
            
            embed.add_field(
                name="💡 費用說明",
                value=f"• 每日前{self.daily_free_quota}次免費\n"
                      "• 超出免費額度後按服務收費\n"
                      "• 使用遊戲獲得的金幣支付",
                inline=False
            )
            
            embed.add_field(
                name="🛠️ 可用功能",
                value="• `/image_effect` - 圖片特效\n"
                      "• `/create_meme` - 迷因製作\n"
                      "• `/avatar_frame` - 頭像框架\n"
                      "• 更多功能開發中...",
                inline=False
            )
            
            await interaction.response.send_message(embed=embed, ephemeral=True)
            
        except Exception as e:
            logger.error(f"❌ 圖片處理使用統計錯誤: {e}")
            await interaction.response.send_message("❌ 獲取使用統計時發生錯誤。", ephemeral=True)

    # ========== 輔助方法 ==========

    async def _get_image_url(self, interaction: discord.Interaction, 
                           attachment: discord.Attachment = None) -> Optional[str]:
        """獲取圖片URL"""
        try:
            # 優先使用附件
            if attachment:
                if attachment.content_type and attachment.content_type.startswith('image/'):
                    return attachment.url
                else:
                    return None
            
            # 檢查最近的消息中是否有圖片
            async for message in interaction.channel.history(limit=20):
                # 檢查附件
                for att in message.attachments:
                    if att.content_type and att.content_type.startswith('image/'):
                        return att.url
                
                # 檢查嵌入圖片
                for embed in message.embeds:
                    if embed.image:
                        return embed.image.url
                    if embed.thumbnail:
                        return embed.thumbnail.url
            
            return None
            
        except Exception as e:
            logger.error(f"❌ 獲取圖片URL失敗: {e}")
            return None

    async def _check_usage_permission(self, user_id: int, guild_id: int, 
                                    service_type: str) -> tuple[bool, Dict[str, Any]]:
        """檢查使用權限和費用"""
        try:
            # 檢查每日免費額度
            daily_usage = await self._get_daily_usage(user_id)
            
            if daily_usage < self.daily_free_quota:
                return True, {"cost": 0, "message": "免費額度內"}
            
            # 檢查金幣餘額
            economy = await self.economy_manager.get_user_economy(user_id, guild_id)
            cost = self.processing_costs.get(service_type, 10)
            
            if economy.get("coins", 0) >= cost:
                return True, {"cost": cost, "message": f"需要消耗 {cost}🪙"}
            else:
                return False, {
                    "cost": cost,
                    "message": f"金幣不足！需要 {cost}🪙，您目前有 {economy.get('coins', 0)}🪙"
                }
                
        except Exception as e:
            logger.error(f"❌ 檢查使用權限失敗: {e}")
            return False, {"cost": 0, "message": "檢查權限時發生錯誤"}

    async def _get_daily_usage(self, user_id: int) -> int:
        """獲取每日使用次數"""
        try:
            cache_key = f"image_daily_usage:{user_id}"
            usage = await cache_manager.get(cache_key)
            return usage or 0
            
        except Exception as e:
            logger.error(f"❌ 獲取每日使用量失敗: {e}")
            return 0

    async def _record_daily_usage(self, user_id: int):
        """記錄每日使用次數"""
        try:
            cache_key = f"image_daily_usage:{user_id}"
            current_usage = await self._get_daily_usage(user_id)
            
            # 設置到明天零點過期
            from datetime import timedelta
            tomorrow = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
            tomorrow += timedelta(days=1)
            ttl = int((tomorrow - datetime.now(timezone.utc)).total_seconds())
            
            await cache_manager.set(cache_key, current_usage + 1, ttl)
            
        except Exception as e:
            logger.error(f"❌ 記錄每日使用量失敗: {e}")

async def setup(bot):
    """設置 Cog"""
    await bot.add_cog(ImageToolsCog(bot))