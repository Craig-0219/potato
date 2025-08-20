# bot/views/image_tools_views.py - 圖片處理工具視圖
"""
圖片處理工具視圖 - Phase 5
提供統一的圖片處理管理界面，包括特效、格式轉換、壓縮等功能
"""

import discord
from discord import ui
from discord.ext import commands
from typing import Optional, Dict, Any, List
from enum import Enum
import asyncio
import traceback
import io

from bot.utils.embed_builder import EmbedBuilder
from shared.logger import logger


class ImageOperation(Enum):
    """圖片操作類型"""
    RESIZE = "resize"
    COMPRESS = "compress"
    FORMAT_CONVERT = "format_convert"
    EFFECTS = "effects"
    FILTERS = "filters"
    WATERMARK = "watermark"


class ImageEffectType(Enum):
    """圖片特效類型"""
    BLUR = "blur"
    SHARPEN = "sharpen"
    VINTAGE = "vintage"
    GRAYSCALE = "grayscale"
    SEPIA = "sepia"
    BRIGHTNESS = "brightness"
    CONTRAST = "contrast"
    SATURATION = "saturation"


class ImageFormatSelector(discord.ui.Select):
    """圖片格式選擇器"""
    
    def __init__(self):
        options = [
            discord.SelectOption(
                label="PNG",
                value="png",
                description="高品質無損格式，支援透明度",
                emoji="🖼️"
            ),
            discord.SelectOption(
                label="JPEG",
                value="jpeg", 
                description="高壓縮比，適合照片",
                emoji="📸"
            ),
            discord.SelectOption(
                label="WEBP",
                value="webp",
                description="現代格式，優秀的壓縮比",
                emoji="🌐"
            ),
            discord.SelectOption(
                label="GIF",
                value="gif",
                description="支援動畫的格式",
                emoji="🎬"
            ),
            discord.SelectOption(
                label="BMP",
                value="bmp",
                description="未壓縮格式",
                emoji="🔲"
            )
        ]
        
        super().__init__(
            placeholder="選擇目標格式...",
            min_values=1,
            max_values=1,
            options=options
        )
    
    async def callback(self, interaction: discord.Interaction):
        """格式選擇回調"""
        try:
            selected_format = self.values[0]
            view = self.view
            view.selected_format = selected_format
            
            embed = EmbedBuilder.create_success_embed(
                "✅ 格式已選擇",
                f"已選擇 **{selected_format.upper()}** 格式\n請上傳圖片開始轉換！"
            )
            
            await interaction.response.edit_message(embed=embed, view=view)
            
        except Exception as e:
            logger.error(f"圖片格式選擇錯誤: {e}")
            embed = EmbedBuilder.create_error_embed("❌ 選擇失敗", "格式選擇出現錯誤")
            await interaction.response.send_message(embed=embed, ephemeral=True)


class ImageEffectSelector(discord.ui.Select):
    """圖片特效選擇器"""
    
    def __init__(self):
        options = [
            discord.SelectOption(
                label="模糊效果",
                value=ImageEffectType.BLUR.value,
                description="添加模糊效果",
                emoji="🌫️"
            ),
            discord.SelectOption(
                label="銳化效果",
                value=ImageEffectType.SHARPEN.value,
                description="增強圖片銳利度",
                emoji="🔪"
            ),
            discord.SelectOption(
                label="復古濾鏡",
                value=ImageEffectType.VINTAGE.value,
                description="復古風格效果",
                emoji="📷"
            ),
            discord.SelectOption(
                label="黑白效果",
                value=ImageEffectType.GRAYSCALE.value,
                description="轉換為黑白圖片",
                emoji="⚫"
            ),
            discord.SelectOption(
                label="懷舊棕褐色",
                value=ImageEffectType.SEPIA.value,
                description="懷舊棕褐色調",
                emoji="🟤"
            ),
            discord.SelectOption(
                label="亮度調整",
                value=ImageEffectType.BRIGHTNESS.value,
                description="調整圖片亮度",
                emoji="💡"
            ),
            discord.SelectOption(
                label="對比度調整",
                value=ImageEffectType.CONTRAST.value,
                description="調整圖片對比度",
                emoji="⚖️"
            ),
            discord.SelectOption(
                label="飽和度調整",
                value=ImageEffectType.SATURATION.value,
                description="調整色彩飽和度",
                emoji="🎨"
            )
        ]
        
        super().__init__(
            placeholder="選擇特效類型...",
            min_values=1,
            max_values=1,
            options=options
        )
    
    async def callback(self, interaction: discord.Interaction):
        """特效選擇回調"""
        try:
            selected_effect = self.values[0]
            view = self.view
            view.selected_effect = selected_effect
            
            # 根據特效類型顯示不同的說明
            effect_descriptions = {
                ImageEffectType.BLUR.value: "模糊效果強度：輕微 → 中等 → 強烈",
                ImageEffectType.SHARPEN.value: "銳化效果強度：輕微 → 適中 → 強烈",
                ImageEffectType.VINTAGE.value: "復古濾鏡強度：淡雅 → 中等 → 濃郁",
                ImageEffectType.GRAYSCALE.value: "轉換為黑白照片（無強度調整）",
                ImageEffectType.SEPIA.value: "懷舊棕褐色調（無強度調整）",
                ImageEffectType.BRIGHTNESS.value: "亮度調整：變暗 → 正常 → 變亮",
                ImageEffectType.CONTRAST.value: "對比度調整：低 → 正常 → 高",
                ImageEffectType.SATURATION.value: "飽和度調整：去色 → 正常 → 鮮豔"
            }
            
            embed = EmbedBuilder.create_success_embed(
                "✅ 特效已選擇",
                f"已選擇 **{[opt.label for opt in self.options if opt.value == selected_effect][0]}**\n\n"
                f"{effect_descriptions.get(selected_effect, '特效效果描述')}\n\n"
                f"請上傳圖片並使用下方按鈕調整強度！"
            )
            
            await interaction.response.edit_message(embed=embed, view=view)
            
        except Exception as e:
            logger.error(f"圖片特效選擇錯誤: {e}")
            embed = EmbedBuilder.create_error_embed("❌ 選擇失敗", "特效選擇出現錯誤")
            await interaction.response.send_message(embed=embed, ephemeral=True)


class ImageToolsControlView(discord.ui.View):
    """圖片工具控制面板視圖"""
    
    def __init__(self):
        super().__init__(timeout=600)
        self.selected_operation = None
        self.selected_format = None
        self.selected_effect = None
        self.effect_intensity = 1.0
        self.uploaded_image = None
    
    @discord.ui.button(label='🔄 格式轉換', style=discord.ButtonStyle.primary, emoji='🔄')
    async def format_convert_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """格式轉換按鈕"""
        try:
            self.selected_operation = ImageOperation.FORMAT_CONVERT
            
            # 清除之前的選擇器
            self.clear_items()
            
            # 添加格式選擇器
            format_selector = ImageFormatSelector()
            self.add_item(format_selector)
            
            # 添加返回按鈕
            self.add_item(self.create_back_button())
            
            embed = EmbedBuilder.create_info_embed(
                "🔄 圖片格式轉換",
                "選擇要轉換的目標格式，然後上傳圖片進行轉換。"
            )
            
            embed.add_field(
                name="📋 支援的格式",
                value="• **PNG**: 無損壓縮，支援透明度\n"
                      "• **JPEG**: 高壓縮比，適合照片\n"
                      "• **WEBP**: 現代格式，優秀壓縮比\n"
                      "• **GIF**: 支援動畫\n"
                      "• **BMP**: 未壓縮格式",
                inline=False
            )
            
            await interaction.response.edit_message(embed=embed, view=self)
            
        except Exception as e:
            logger.error(f"格式轉換按鈕錯誤: {e}")
            embed = EmbedBuilder.create_error_embed("❌ 操作失敗", "無法啟動格式轉換功能")
            await interaction.response.send_message(embed=embed, ephemeral=True)
    
    @discord.ui.button(label='🎨 特效處理', style=discord.ButtonStyle.secondary, emoji='🎨')
    async def effects_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """特效處理按鈕"""
        try:
            self.selected_operation = ImageOperation.EFFECTS
            
            # 清除之前的選擇器
            self.clear_items()
            
            # 添加特效選擇器
            effect_selector = ImageEffectSelector()
            self.add_item(effect_selector)
            
            # 添加強度調整按鈕
            self.add_intensity_controls()
            
            # 添加返回按鈕
            self.add_item(self.create_back_button())
            
            embed = EmbedBuilder.create_info_embed(
                "🎨 圖片特效處理",
                "選擇要應用的特效類型，調整強度後上傳圖片。"
            )
            
            embed.add_field(
                name="🌟 可用特效",
                value="• **模糊/銳化**: 調整圖片清晰度\n"
                      "• **濾鏡效果**: 復古、黑白、懷舊\n"
                      "• **色彩調整**: 亮度、對比度、飽和度",
                inline=False
            )
            
            await interaction.response.edit_message(embed=embed, view=self)
            
        except Exception as e:
            logger.error(f"特效處理按鈕錯誤: {e}")
            embed = EmbedBuilder.create_error_embed("❌ 操作失敗", "無法啟動特效處理功能")
            await interaction.response.send_message(embed=embed, ephemeral=True)
    
    @discord.ui.button(label='📦 圖片壓縮', style=discord.ButtonStyle.secondary, emoji='📦')
    async def compress_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """圖片壓縮按鈕"""
        try:
            self.selected_operation = ImageOperation.COMPRESS
            
            embed = EmbedBuilder.create_info_embed(
                "📦 圖片壓縮",
                "智能壓縮圖片以減少文件大小，同時保持視覺質量。"
            )
            
            embed.add_field(
                name="🔧 壓縮選項",
                value="• **高質量**: 輕微壓縮，保持高畫質\n"
                      "• **平衡模式**: 適中的壓縮和質量\n"
                      "• **高壓縮**: 最大壓縮，適合存儲",
                inline=False
            )
            
            embed.add_field(
                name="📤 使用方法",
                value="直接上傳圖片文件，系統將自動進行智能壓縮。",
                inline=False
            )
            
            await interaction.response.edit_message(embed=embed, view=self)
            
        except Exception as e:
            logger.error(f"圖片壓縮按鈕錯誤: {e}")
            embed = EmbedBuilder.create_error_embed("❌ 操作失敗", "無法啟動圖片壓縮功能")
            await interaction.response.send_message(embed=embed, ephemeral=True)
    
    @discord.ui.button(label='📏 尺寸調整', style=discord.ButtonStyle.secondary, emoji='📏')
    async def resize_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """尺寸調整按鈕"""
        try:
            self.selected_operation = ImageOperation.RESIZE
            
            embed = EmbedBuilder.create_info_embed(
                "📏 圖片尺寸調整",
                "調整圖片的尺寸和解析度。"
            )
            
            embed.add_field(
                name="📐 預設尺寸",
                value="• **Discord 頭像**: 128x128\n"
                      "• **社交媒體**: 1080x1080\n"
                      "• **桌布**: 1920x1080\n"
                      "• **自定義**: 指定寬度和高度",
                inline=False
            )
            
            embed.add_field(
                name="📤 使用方法",
                value="上傳圖片後，使用 `/image resize` 命令指定新尺寸。",
                inline=False
            )
            
            await interaction.response.edit_message(embed=embed, view=self)
            
        except Exception as e:
            logger.error(f"尺寸調整按鈕錯誤: {e}")
            embed = EmbedBuilder.create_error_embed("❌ 操作失敗", "無法啟動尺寸調整功能")
            await interaction.response.send_message(embed=embed, ephemeral=True)
    
    def add_intensity_controls(self):
        """添加強度控制按鈕"""
        # 減少強度按鈕
        decrease_button = discord.ui.Button(
            label=f'➖ 強度: {self.effect_intensity:.1f}',
            style=discord.ButtonStyle.secondary,
            custom_id='decrease_intensity'
        )
        decrease_button.callback = self.decrease_intensity
        self.add_item(decrease_button)
        
        # 增加強度按鈕
        increase_button = discord.ui.Button(
            label=f'➕ 強度: {self.effect_intensity:.1f}',
            style=discord.ButtonStyle.secondary,
            custom_id='increase_intensity'
        )
        increase_button.callback = self.increase_intensity
        self.add_item(increase_button)
    
    async def decrease_intensity(self, interaction: discord.Interaction):
        """減少特效強度"""
        self.effect_intensity = max(0.1, self.effect_intensity - 0.2)
        await self.update_intensity_display(interaction)
    
    async def increase_intensity(self, interaction: discord.Interaction):
        """增加特效強度"""
        self.effect_intensity = min(2.0, self.effect_intensity + 0.2)
        await self.update_intensity_display(interaction)
    
    async def update_intensity_display(self, interaction: discord.Interaction):
        """更新強度顯示"""
        # 更新按鈕標籤
        for item in self.children:
            if hasattr(item, 'custom_id'):
                if item.custom_id == 'decrease_intensity':
                    item.label = f'➖ 強度: {self.effect_intensity:.1f}'
                elif item.custom_id == 'increase_intensity':
                    item.label = f'➕ 強度: {self.effect_intensity:.1f}'
        
        embed = EmbedBuilder.create_info_embed(
            "🎛️ 特效強度調整",
            f"當前強度設置：**{self.effect_intensity:.1f}**\n\n"
            f"• 0.1-0.5: 輕微效果\n"
            f"• 0.6-1.0: 適中效果\n"
            f"• 1.1-2.0: 強烈效果"
        )
        
        await interaction.response.edit_message(embed=embed, view=self)
    
    def create_back_button(self):
        """創建返回按鈕"""
        back_button = discord.ui.Button(
            label='🔙 返回主選單',
            style=discord.ButtonStyle.danger,
            custom_id='back_to_main'
        )
        back_button.callback = self.back_to_main
        return back_button
    
    async def back_to_main(self, interaction: discord.Interaction):
        """返回主選單"""
        # 重置狀態
        self.selected_operation = None
        self.selected_format = None
        self.selected_effect = None
        
        # 重新創建主選單
        view = ImageToolsMainView()
        
        embed = EmbedBuilder.create_info_embed(
            "🖼️ 圖片處理工具",
            "選擇要使用的圖片處理功能。"
        )
        
        await interaction.response.edit_message(embed=embed, view=view)


class ImageToolsMainView(discord.ui.View):
    """圖片工具主選單視圖"""
    
    def __init__(self):
        super().__init__(timeout=300)
    
    @discord.ui.button(label='🖼️ 圖片工具', style=discord.ButtonStyle.primary, emoji='🖼️')
    async def image_tools_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """圖片工具按鈕"""
        try:
            control_view = ImageToolsControlView()
            
            embed = EmbedBuilder.create_info_embed(
                "🖼️ 圖片處理工具",
                "選擇要使用的圖片處理功能。"
            )
            
            embed.add_field(
                name="🔧 可用功能",
                value="• **格式轉換**: PNG, JPEG, WEBP, GIF, BMP\n"
                      "• **特效處理**: 濾鏡、色彩調整、模糊銳化\n"
                      "• **圖片壓縮**: 智能壓縮，減少文件大小\n"
                      "• **尺寸調整**: 自定義或預設尺寸",
                inline=False
            )
            
            embed.add_field(
                name="📋 支援格式",
                value="**輸入**: JPG, PNG, GIF, WEBP, BMP\n**輸出**: PNG, JPG, WEBP, GIF, BMP",
                inline=True
            )
            
            embed.add_field(
                name="📏 限制",
                value="**最大文件**: 10MB\n**最大尺寸**: 2000x2000",
                inline=True
            )
            
            await interaction.response.edit_message(embed=embed, view=control_view)
            
        except Exception as e:
            logger.error(f"圖片工具按鈕錯誤: {e}")
            embed = EmbedBuilder.create_error_embed("❌ 系統錯誤", "無法啟動圖片工具")
            await interaction.response.send_message(embed=embed, ephemeral=True)
    
    @discord.ui.button(label='📊 使用說明', style=discord.ButtonStyle.secondary, emoji='📊')
    async def usage_guide_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """使用說明按鈕"""
        try:
            embed = EmbedBuilder.create_info_embed(
                "📖 圖片工具使用說明",
                "了解如何有效使用圖片處理功能。"
            )
            
            embed.add_field(
                name="📤 上傳圖片",
                value="1. 選擇處理功能\n2. 設置參數\n3. 上傳圖片文件\n4. 等待處理完成",
                inline=False
            )
            
            embed.add_field(
                name="🎨 特效處理",
                value="• 選擇特效類型\n• 調整強度 (0.1-2.0)\n• 上傳圖片\n• 獲得處理結果",
                inline=True
            )
            
            embed.add_field(
                name="🔄 格式轉換",
                value="• 選擇目標格式\n• 上傳圖片\n• 自動轉換\n• 下載新格式",
                inline=True
            )
            
            embed.add_field(
                name="💡 使用技巧",
                value="• 較大圖片處理時間更長\n• 建議先壓縮大文件\n• 可以批量處理多張圖片\n• 保存原圖備份",
                inline=False
            )
            
            embed.add_field(
                name="⚠️ 注意事項",
                value="• 文件大小限制: 10MB\n• 尺寸限制: 2000x2000\n• 處理時間: 通常 5-30 秒\n• 支援常見圖片格式",
                inline=False
            )
            
            await interaction.response.send_message(embed=embed, ephemeral=True)
            
        except Exception as e:
            logger.error(f"使用說明錯誤: {e}")
            embed = EmbedBuilder.create_error_embed("❌ 顯示錯誤", "無法顯示使用說明")
            await interaction.response.send_message(embed=embed, ephemeral=True)