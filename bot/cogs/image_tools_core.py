# bot/cogs/image_tools_core.py - 圖片處理工具指令模組
"""
圖片處理工具指令模組 - Phase 5
提供圖片格式轉換、特效處理、壓縮等功能的Discord指令
"""

import io
import time
from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands

from bot.services.image_processor import (
    ImageFormat,
    ImageOperation,
    ImageProcessRequest,
    image_processor,
)
from bot.utils.embed_builder import EmbedBuilder
from bot.views.image_tools_views import ImageToolsMainView
from shared.logger import logger


class ImageToolsCog(commands.Cog):
    """圖片處理工具功能"""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        logger.info("🖼️ 圖片處理工具指令模組初始化完成")

    # ========== 統一圖片工具界面 ==========

    @app_commands.command(name="image", description="打開圖片處理工具管理界面")
    async def image_tools_interface(self, interaction: discord.Interaction):
        """統一圖片工具管理界面"""
        try:
            view = ImageToolsMainView()

            embed = EmbedBuilder.create_info_embed("🖼️ 圖片處理工具", "選擇要使用的圖片處理功能。")

            embed.add_field(
                name="🔧 可用功能",
                value="• **格式轉換**: PNG, JPEG, WEBP, GIF, BMP\n"
                "• **特效處理**: 濾鏡、色彩調整、模糊銳化\n"
                "• **圖片壓縮**: 智能壓縮，減少文件大小\n"
                "• **尺寸調整**: 自定義或預設尺寸",
                inline=False,
            )

            embed.add_field(
                name="📋 支援格式",
                value="**輸入**: JPG, PNG, GIF, WEBP, BMP\n**輸出**: PNG, JPG, WEBP, GIF, BMP",
                inline=True,
            )

            embed.add_field(
                name="📏 限制", value="**最大文件**: 10MB\n**最大尺寸**: 2000x2000", inline=True
            )

            await interaction.response.send_message(embed=embed, view=view)

        except Exception as e:
            logger.error(f"❌ 圖片工具界面錯誤: {e}")
            await interaction.response.send_message("❌ 啟動圖片工具時發生錯誤。", ephemeral=True)

    # ========== 圖片格式轉換 ==========

    @app_commands.command(name="convert_format", description="轉換圖片格式")
    @app_commands.describe(
        image="要轉換的圖片附件",
        target_format="目標格式",
        quality="輸出品質 (1-100，僅適用於 JPEG/WEBP)",
    )
    @app_commands.choices(
        target_format=[
            app_commands.Choice(name="PNG", value="png"),
            app_commands.Choice(name="JPEG", value="jpeg"),
            app_commands.Choice(name="WEBP", value="webp"),
            app_commands.Choice(name="GIF", value="gif"),
            app_commands.Choice(name="BMP", value="bmp"),
        ]
    )
    async def convert_format(
        self,
        interaction: discord.Interaction,
        image: discord.Attachment,
        target_format: str,
        quality: int = 85,
    ):
        """轉換圖片格式"""
        try:
            await interaction.response.defer()

            # 驗證圖片
            if not image.content_type or not image.content_type.startswith("image/"):
                await interaction.followup.send("❌ 請上傳有效的圖片文件！", ephemeral=True)
                return

            # 檢查文件大小
            if image.size > 10 * 1024 * 1024:  # 10MB
                await interaction.followup.send(
                    "❌ 圖片文件過大！請使用小於 10MB 的圖片。", ephemeral=True
                )
                return

            # 驗證品質參數
            quality = max(1, min(100, quality))

            # 創建處理請求
            request = ImageProcessRequest(
                image_url=image.url,
                operation=ImageOperation.FORMAT_CONVERT,
                parameters={},
                output_format=ImageFormat(target_format),
                quality=quality,
            )

            # 處理圖片
            result = await image_processor.process_image(request)

            if result.success:
                # 創建輸出文件
                filename = f"converted_{int(time.time())}.{target_format}"
                file = discord.File(io.BytesIO(result.image_data), filename=filename)

                embed = EmbedBuilder.create_success_embed(
                    "✅ 格式轉換完成", f"已成功轉換為 **{target_format.upper()}** 格式"
                )

                embed.add_field(
                    name="📊 處理資訊",
                    value=f"原始格式: {image.content_type.split('/')[-1].upper()}\n"
                    f"目標格式: {target_format.upper()}\n"
                    f"處理時間: {result.processing_time:.2f}秒\n"
                    f"輸出大小: {result.file_size/1024:.1f} KB\n"
                    f"解析度: {result.size[0]}×{result.size[1]}",
                    inline=True,
                )

                if target_format in ["jpeg", "webp"]:
                    embed.add_field(name="🎚️ 品質設定", value=f"壓縮品質: {quality}%", inline=True)

                embed.set_footer(text=f"處理者: {interaction.user.display_name}")

                await interaction.followup.send(embed=embed, file=file)

            else:
                embed = EmbedBuilder.create_error_embed(
                    "❌ 轉換失敗", result.error_message or "格式轉換過程中發生未知錯誤"
                )
                await interaction.followup.send(embed=embed, ephemeral=True)

        except Exception as e:
            logger.error(f"❌ 格式轉換錯誤: {e}")
            await interaction.followup.send("❌ 轉換圖片時發生錯誤，請稍後再試。", ephemeral=True)

    # ========== 圖片特效 ==========

    @app_commands.command(name="apply_effect", description="為圖片添加特效")
    @app_commands.describe(
        image="要處理的圖片附件", effect="特效類型", intensity="特效強度 (0.1-2.0)"
    )
    @app_commands.choices(
        effect=[
            app_commands.Choice(name="模糊", value="blur"),
            app_commands.Choice(name="銳化", value="sharpen"),
            app_commands.Choice(name="復古", value="vintage"),
            app_commands.Choice(name="黑白", value="grayscale"),
            app_commands.Choice(name="復古色調", value="sepia"),
            app_commands.Choice(name="亮度調整", value="brightness"),
            app_commands.Choice(name="對比度調整", value="contrast"),
            app_commands.Choice(name="飽和度調整", value="saturation"),
        ]
    )
    async def apply_effect(
        self,
        interaction: discord.Interaction,
        image: discord.Attachment,
        effect: str,
        intensity: float = 1.0,
    ):
        """應用圖片特效"""
        try:
            await interaction.response.defer()

            # 驗證圖片
            if not image.content_type or not image.content_type.startswith("image/"):
                await interaction.followup.send("❌ 請上傳有效的圖片文件！", ephemeral=True)
                return

            # 檢查文件大小
            if image.size > 10 * 1024 * 1024:  # 10MB
                await interaction.followup.send(
                    "❌ 圖片文件過大！請使用小於 10MB 的圖片。", ephemeral=True
                )
                return

            # 驗證強度參數
            intensity = max(0.1, min(2.0, intensity))

            # 創建處理請求
            request = ImageProcessRequest(
                image_url=image.url,
                operation=ImageOperation.APPLY_EFFECT,
                parameters={"effect_type": effect, "intensity": intensity},
                output_format=ImageFormat.PNG,
            )

            # 處理圖片
            result = await image_processor.process_image(request)

            if result.success:
                # 創建輸出文件
                filename = f"effect_{effect}_{int(time.time())}.png"
                file = discord.File(io.BytesIO(result.image_data), filename=filename)

                embed = EmbedBuilder.create_success_embed(
                    f"🎨 {effect.title()} 特效已套用", f"特效強度: **{intensity}**"
                )

                embed.add_field(
                    name="📊 處理資訊",
                    value=f"特效類型: {effect.title()}\n"
                    f"強度: {intensity}\n"
                    f"處理時間: {result.processing_time:.2f}秒\n"
                    f"輸出大小: {result.file_size/1024:.1f} KB\n"
                    f"解析度: {result.size[0]}×{result.size[1]}",
                    inline=True,
                )

                embed.set_footer(text=f"處理者: {interaction.user.display_name}")

                await interaction.followup.send(embed=embed, file=file)

            else:
                embed = EmbedBuilder.create_error_embed(
                    "❌ 特效處理失敗", result.error_message or "特效處理過程中發生未知錯誤"
                )
                await interaction.followup.send(embed=embed, ephemeral=True)

        except Exception as e:
            logger.error(f"❌ 特效處理錯誤: {e}")
            await interaction.followup.send("❌ 處理圖片時發生錯誤，請稍後再試。", ephemeral=True)

    # ========== 圖片壓縮 ==========

    @app_commands.command(name="compress_image", description="壓縮圖片以減少文件大小")
    @app_commands.describe(image="要壓縮的圖片附件", quality="壓縮品質 (1-100，數值越低壓縮越大)")
    async def compress_image(
        self, interaction: discord.Interaction, image: discord.Attachment, quality: int = 75
    ):
        """壓縮圖片"""
        try:
            await interaction.response.defer()

            # 驗證圖片
            if not image.content_type or not image.content_type.startswith("image/"):
                await interaction.followup.send("❌ 請上傳有效的圖片文件！", ephemeral=True)
                return

            # 檢查文件大小
            if image.size > 10 * 1024 * 1024:  # 10MB
                await interaction.followup.send(
                    "❌ 圖片文件過大！請使用小於 10MB 的圖片。", ephemeral=True
                )
                return

            # 驗證品質參數
            quality = max(1, min(100, quality))

            # 根據原始格式選擇輸出格式
            output_format = ImageFormat.JPEG  # 預設使用 JPEG 以獲得更好的壓縮
            if "png" in image.content_type and quality > 80:
                output_format = ImageFormat.PNG  # 高品質時保持 PNG

            # 創建處理請求
            request = ImageProcessRequest(
                image_url=image.url,
                operation=ImageOperation.COMPRESS,
                parameters={},
                output_format=output_format,
                quality=quality,
            )

            # 處理圖片
            result = await image_processor.process_image(request)

            if result.success:
                # 計算壓縮比
                compression_ratio = (1 - result.file_size / image.size) * 100

                # 創建輸出文件
                filename = f"compressed_{int(time.time())}.{output_format.value}"
                file = discord.File(io.BytesIO(result.image_data), filename=filename)

                embed = EmbedBuilder.create_success_embed(
                    "📦 圖片壓縮完成", f"壓縮品質: **{quality}%**"
                )

                embed.add_field(
                    name="📊 壓縮結果",
                    value=f"原始大小: {image.size/1024:.1f} KB\n"
                    f"壓縮後: {result.file_size/1024:.1f} KB\n"
                    f"壓縮比: {compression_ratio:.1f}%\n"
                    f"處理時間: {result.processing_time:.2f}秒",
                    inline=True,
                )

                embed.add_field(
                    name="🔧 技術資訊",
                    value=f"輸出格式: {output_format.value.upper()}\n"
                    f"解析度: {result.size[0]}×{result.size[1]}\n"
                    f"品質設定: {quality}%",
                    inline=True,
                )

                # 根據壓縮效果調整顏色
                color = (
                    0x00FF00
                    if compression_ratio > 30
                    else 0xFFFF00 if compression_ratio > 10 else 0xFF0000
                )
                embed.color = color

                embed.set_footer(text=f"處理者: {interaction.user.display_name}")

                await interaction.followup.send(embed=embed, file=file)

            else:
                embed = EmbedBuilder.create_error_embed(
                    "❌ 壓縮失敗", result.error_message or "壓縮過程中發生未知錯誤"
                )
                await interaction.followup.send(embed=embed, ephemeral=True)

        except Exception as e:
            logger.error(f"❌ 圖片壓縮錯誤: {e}")
            await interaction.followup.send("❌ 壓縮圖片時發生錯誤，請稍後再試。", ephemeral=True)

    # ========== 圖片調整尺寸 ==========

    @app_commands.command(name="resize_image", description="調整圖片尺寸")
    @app_commands.describe(
        image="要調整的圖片附件",
        width="目標寬度（像素）",
        height="目標高度（像素，可選）",
        maintain_aspect="是否保持寬高比",
    )
    async def resize_image(
        self,
        interaction: discord.Interaction,
        image: discord.Attachment,
        width: int,
        height: Optional[int] = None,
        maintain_aspect: bool = True,
    ):
        """調整圖片尺寸"""
        try:
            await interaction.response.defer()

            # 驗證圖片
            if not image.content_type or not image.content_type.startswith("image/"):
                await interaction.followup.send("❌ 請上傳有效的圖片文件！", ephemeral=True)
                return

            # 檢查文件大小
            if image.size > 10 * 1024 * 1024:  # 10MB
                await interaction.followup.send(
                    "❌ 圖片文件過大！請使用小於 10MB 的圖片。", ephemeral=True
                )
                return

            # 驗證尺寸參數
            width = max(1, min(2000, width))
            if height:
                height = max(1, min(2000, height))

            # 創建處理請求
            request = ImageProcessRequest(
                image_url=image.url,
                operation=ImageOperation.RESIZE,
                parameters={"width": width, "height": height, "maintain_aspect": maintain_aspect},
                output_format=ImageFormat.PNG,
            )

            # 處理圖片
            result = await image_processor.process_image(request)

            if result.success:
                # 創建輸出文件
                filename = f"resized_{width}x{result.size[1]}_{int(time.time())}.png"
                file = discord.File(io.BytesIO(result.image_data), filename=filename)

                embed = EmbedBuilder.create_success_embed(
                    "📏 圖片尺寸調整完成", f"新尺寸: **{result.size[0]}×{result.size[1]}**"
                )

                embed.add_field(
                    name="📊 調整資訊",
                    value=f"目標寬度: {width}px\n"
                    + (f"目標高度: {height}px\n" if height else "")
                    + f"保持比例: {'是' if maintain_aspect else '否'}\n"
                    f"實際尺寸: {result.size[0]}×{result.size[1]}\n"
                    f"處理時間: {result.processing_time:.2f}秒",
                    inline=True,
                )

                embed.add_field(
                    name="💾 文件資訊",
                    value=f"輸出大小: {result.file_size/1024:.1f} KB\n" f"格式: PNG",
                    inline=True,
                )

                embed.set_footer(text=f"處理者: {interaction.user.display_name}")

                await interaction.followup.send(embed=embed, file=file)

            else:
                embed = EmbedBuilder.create_error_embed(
                    "❌ 尺寸調整失敗", result.error_message or "尺寸調整過程中發生未知錯誤"
                )
                await interaction.followup.send(embed=embed, ephemeral=True)

        except Exception as e:
            logger.error(f"❌ 尺寸調整錯誤: {e}")
            await interaction.followup.send("❌ 調整圖片時發生錯誤，請稍後再試。", ephemeral=True)


async def setup(bot):
    """設置 Cog"""
    await bot.add_cog(ImageToolsCog(bot))
    logger.info("✅ ImageToolsCog 已載入")
