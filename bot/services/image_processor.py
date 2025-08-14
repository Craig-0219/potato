# bot/services/image_processor.py - 圖片處理服務
"""
圖片處理服務 v2.2.0
提供迷因製作、圖片特效、頭像生成等功能
"""

import asyncio
import aiohttp
import aiofiles
import io
import base64
import random
from typing import Dict, List, Optional, Any, Union, Tuple
from datetime import datetime, timezone
from dataclasses import dataclass
from enum import Enum
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageEnhance
import requests
import os
import tempfile

from shared.cache_manager import cache_manager, cached
from shared.logger import logger

class ImageEffect(Enum):
    """圖片特效類型"""
    BLUR = "blur"
    SHARPEN = "sharpen"
    VINTAGE = "vintage"
    GRAYSCALE = "grayscale"
    SEPIA = "sepia"
    NEON = "neon"
    EMBOSS = "emboss"
    EDGE_ENHANCE = "edge_enhance"

class MemeTemplate(Enum):
    """迷因模板類型"""
    DRAKE = "drake"
    DISTRACTED_BOYFRIEND = "distracted_boyfriend"
    TWO_BUTTONS = "two_buttons"
    BRAIN_EXPAND = "brain_expand"
    WOMAN_YELLING_CAT = "woman_yelling_cat"
    CHANGE_MY_MIND = "change_my_mind"
    CUSTOM_TEXT = "custom_text"

@dataclass
class ImageProcessRequest:
    """圖片處理請求"""
    user_id: int
    guild_id: int
    image_url: str
    operation: str
    parameters: Dict[str, Any]
    
@dataclass
class ProcessedImage:
    """處理後的圖片"""
    image_data: bytes
    format: str
    size: Tuple[int, int]
    file_size: int
    processing_time: float
    success: bool
    error_message: Optional[str] = None

class ImageProcessor:
    """圖片處理器"""
    
    def __init__(self):
        self.max_image_size = 10 * 1024 * 1024  # 10MB
        self.max_dimensions = (2000, 2000)
        self.supported_formats = ['.jpg', '.jpeg', '.png', '.gif', '.webp']
        
        # 迷因模板配置
        self.meme_templates = {
            MemeTemplate.DRAKE: {
                "width": 600,
                "height": 600,
                "text_areas": [
                    {"x": 350, "y": 150, "width": 200, "height": 100},  # 上方文字
                    {"x": 350, "y": 450, "width": 200, "height": 100}   # 下方文字
                ]
            },
            MemeTemplate.CUSTOM_TEXT: {
                "width": 800,
                "height": 600,
                "text_areas": [
                    {"x": 50, "y": 50, "width": 700, "height": 100},   # 上方文字
                    {"x": 50, "y": 450, "width": 700, "height": 100}   # 下方文字
                ]
            }
        }
        
        # 預設字體路徑（需要確保字體文件存在）
        self.font_paths = {
            "default": "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
            "chinese": "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc"  # 中文字體
        }
        
        logger.info("🖼️ 圖片處理器初始化完成")

    # ========== 圖片下載和驗證 ==========

    async def download_image(self, image_url: str) -> Optional[Image.Image]:
        """下載並驗證圖片"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(image_url, timeout=30) as response:
                    if response.status != 200:
                        logger.error(f"❌ 下載圖片失敗: HTTP {response.status}")
                        return None
                    
                    # 檢查文件大小
                    content_length = response.headers.get('content-length')
                    if content_length and int(content_length) > self.max_image_size:
                        logger.error(f"❌ 圖片太大: {content_length} bytes")
                        return None
                    
                    image_data = await response.read()
                    
                    # 檢查實際大小
                    if len(image_data) > self.max_image_size:
                        logger.error(f"❌ 圖片太大: {len(image_data)} bytes")
                        return None
                    
                    # 打開圖片
                    image = Image.open(io.BytesIO(image_data))
                    
                    # 檢查尺寸
                    if image.size[0] > self.max_dimensions[0] or image.size[1] > self.max_dimensions[1]:
                        # 自動縮放
                        image.thumbnail(self.max_dimensions, Image.Resampling.LANCZOS)
                    
                    # 轉換為RGB模式（處理RGBA等格式）
                    if image.mode != 'RGB':
                        image = image.convert('RGB')
                    
                    return image
                    
        except Exception as e:
            logger.error(f"❌ 下載圖片異常: {e}")
            return None

    def image_to_bytes(self, image: Image.Image, format: str = 'PNG') -> bytes:
        """將PIL圖片轉換為字節"""
        try:
            img_buffer = io.BytesIO()
            image.save(img_buffer, format=format, quality=85, optimize=True)
            img_buffer.seek(0)
            return img_buffer.getvalue()
            
        except Exception as e:
            logger.error(f"❌ 圖片轉換字節失敗: {e}")
            raise

    # ========== 圖片特效處理 ==========

    async def apply_effect(self, image_url: str, effect: ImageEffect, 
                          intensity: float = 1.0) -> ProcessedImage:
        """應用圖片特效"""
        start_time = datetime.now()
        
        try:
            # 下載圖片
            image = await self.download_image(image_url)
            if not image:
                return ProcessedImage(
                    image_data=b'',
                    format='PNG',
                    size=(0, 0),
                    file_size=0,
                    processing_time=0,
                    success=False,
                    error_message="無法下載或處理圖片"
                )
            
            # 應用特效
            processed_image = await self._apply_image_effect(image, effect, intensity)
            
            # 轉換為字節
            image_data = self.image_to_bytes(processed_image, 'PNG')
            
            processing_time = (datetime.now() - start_time).total_seconds()
            
            return ProcessedImage(
                image_data=image_data,
                format='PNG',
                size=processed_image.size,
                file_size=len(image_data),
                processing_time=processing_time,
                success=True
            )
            
        except Exception as e:
            logger.error(f"❌ 應用圖片特效失敗: {e}")
            processing_time = (datetime.now() - start_time).total_seconds()
            return ProcessedImage(
                image_data=b'',
                format='PNG',
                size=(0, 0),
                file_size=0,
                processing_time=processing_time,
                success=False,
                error_message=str(e)
            )

    async def _apply_image_effect(self, image: Image.Image, effect: ImageEffect, 
                                intensity: float) -> Image.Image:
        """應用具體的圖片特效"""
        try:
            if effect == ImageEffect.BLUR:
                return image.filter(ImageFilter.GaussianBlur(radius=intensity * 3))
            
            elif effect == ImageEffect.SHARPEN:
                return image.filter(ImageFilter.UnsharpMask(radius=2, percent=int(150 * intensity)))
            
            elif effect == ImageEffect.GRAYSCALE:
                return image.convert('L').convert('RGB')
            
            elif effect == ImageEffect.SEPIA:
                return self._apply_sepia(image, intensity)
            
            elif effect == ImageEffect.VINTAGE:
                return self._apply_vintage(image, intensity)
            
            elif effect == ImageEffect.NEON:
                return self._apply_neon(image, intensity)
            
            elif effect == ImageEffect.EMBOSS:
                return image.filter(ImageFilter.EMBOSS)
            
            elif effect == ImageEffect.EDGE_ENHANCE:
                return image.filter(ImageFilter.EDGE_ENHANCE_MORE)
            
            else:
                return image
                
        except Exception as e:
            logger.error(f"❌ 應用特效失敗: {e}")
            return image

    def _apply_sepia(self, image: Image.Image, intensity: float) -> Image.Image:
        """應用復古色調效果"""
        try:
            # 轉換為灰度
            grayscale = image.convert('L')
            
            # 創建復古色調
            sepia_image = Image.new('RGB', image.size)
            pixels = sepia_image.load()
            gray_pixels = grayscale.load()
            
            for y in range(image.height):
                for x in range(image.width):
                    gray_value = gray_pixels[x, y]
                    
                    # 計算復古色調
                    r = min(255, int(gray_value * (1 + 0.2 * intensity)))
                    g = min(255, int(gray_value * (1 + 0.1 * intensity)))
                    b = min(255, int(gray_value * (1 - 0.1 * intensity)))
                    
                    pixels[x, y] = (r, g, b)
            
            return sepia_image
            
        except Exception as e:
            logger.error(f"❌ 復古特效失敗: {e}")
            return image

    def _apply_vintage(self, image: Image.Image, intensity: float) -> Image.Image:
        """應用復古濾鏡"""
        try:
            # 降低飽和度
            enhancer = ImageEnhance.Color(image)
            image = enhancer.enhance(1 - 0.3 * intensity)
            
            # 增加對比度
            enhancer = ImageEnhance.Contrast(image)
            image = enhancer.enhance(1 + 0.2 * intensity)
            
            # 添加輕微的溫暖色調
            return self._apply_sepia(image, intensity * 0.5)
            
        except Exception as e:
            logger.error(f"❌ 復古濾鏡失敗: {e}")
            return image

    def _apply_neon(self, image: Image.Image, intensity: float) -> Image.Image:
        """應用霓虹特效"""
        try:
            # 邊緣檢測
            edges = image.filter(ImageFilter.FIND_EDGES)
            
            # 增強顏色
            enhancer = ImageEnhance.Color(image)
            enhanced = enhancer.enhance(1 + intensity)
            
            # 混合原圖和邊緣
            return Image.blend(enhanced, edges, 0.3 * intensity)
            
        except Exception as e:
            logger.error(f"❌ 霓虹特效失敗: {e}")
            return image

    # ========== 迷因製作 ==========

    async def create_meme(self, template: MemeTemplate, texts: List[str],
                         background_image: Optional[str] = None) -> ProcessedImage:
        """創建迷因圖片"""
        start_time = datetime.now()
        
        try:
            # 獲取模板配置
            template_config = self.meme_templates.get(template)
            if not template_config:
                raise ValueError(f"不支持的迷因模板: {template}")
            
            # 創建基礎圖片
            if background_image:
                # 使用自定義背景
                bg_image = await self.download_image(background_image)
                if bg_image:
                    bg_image = bg_image.resize((template_config["width"], template_config["height"]))
                else:
                    # 使用純色背景作為後備
                    bg_image = Image.new('RGB', (template_config["width"], template_config["height"]), 'white')
            else:
                # 使用預設模板背景
                bg_image = await self._create_template_background(template, template_config)
            
            # 添加文字
            meme_image = await self._add_meme_text(bg_image, texts, template_config)
            
            # 轉換為字節
            image_data = self.image_to_bytes(meme_image, 'PNG')
            
            processing_time = (datetime.now() - start_time).total_seconds()
            
            return ProcessedImage(
                image_data=image_data,
                format='PNG',
                size=meme_image.size,
                file_size=len(image_data),
                processing_time=processing_time,
                success=True
            )
            
        except Exception as e:
            logger.error(f"❌ 創建迷因失敗: {e}")
            processing_time = (datetime.now() - start_time).total_seconds()
            return ProcessedImage(
                image_data=b'',
                format='PNG',
                size=(0, 0),
                file_size=0,
                processing_time=processing_time,
                success=False,
                error_message=str(e)
            )

    async def _create_template_background(self, template: MemeTemplate, 
                                        config: Dict[str, Any]) -> Image.Image:
        """創建模板背景"""
        try:
            width = config["width"]
            height = config["height"]
            
            if template == MemeTemplate.DRAKE:
                # 創建Drake模板背景
                image = Image.new('RGB', (width, height), 'white')
                draw = ImageDraw.Draw(image)
                
                # 繪製分割線
                draw.line([(0, height//2), (width, height//2)], fill='black', width=3)
                draw.line([(width//3, 0), (width//3, height)], fill='black', width=3)
                
                # 添加Drake手勢區域（簡化為色塊）
                # 上方：拒絕手勢（紅色）
                draw.rectangle([(10, 10), (width//3 - 10, height//2 - 10)], fill='#ffcccb')
                # 下方：贊同手勢（綠色）
                draw.rectangle([(10, height//2 + 10), (width//3 - 10, height - 10)], fill='#90ee90')
                
                return image
                
            else:
                # 默認背景
                return Image.new('RGB', (width, height), '#f0f0f0')
                
        except Exception as e:
            logger.error(f"❌ 創建模板背景失敗: {e}")
            return Image.new('RGB', (config["width"], config["height"]), 'white')

    async def _add_meme_text(self, image: Image.Image, texts: List[str], 
                           config: Dict[str, Any]) -> Image.Image:
        """添加迷因文字"""
        try:
            draw = ImageDraw.Draw(image)
            text_areas = config["text_areas"]
            
            # 嘗試載入字體
            try:
                # 優先使用中文字體
                font_size = 40
                font = ImageFont.truetype(self.font_paths["chinese"], font_size)
            except:
                try:
                    # 後備英文字體
                    font = ImageFont.truetype(self.font_paths["default"], font_size)
                except:
                    # 使用默認字體
                    font = ImageFont.load_default()
            
            # 為每個文字區域添加文字
            for i, text in enumerate(texts):
                if i >= len(text_areas):
                    break
                
                area = text_areas[i]
                if not text.strip():
                    continue
                
                # 自動調整字體大小以適應區域
                font_size = await self._calculate_font_size(
                    text, area["width"], area["height"], font
                )
                
                try:
                    if font_size != 40:
                        font = ImageFont.truetype(self.font_paths.get("chinese", self.font_paths["default"]), font_size)
                except:
                    font = ImageFont.load_default()
                
                # 計算文字位置（居中）
                bbox = draw.textbbox((0, 0), text, font=font)
                text_width = bbox[2] - bbox[0]
                text_height = bbox[3] - bbox[1]
                
                x = area["x"] + (area["width"] - text_width) // 2
                y = area["y"] + (area["height"] - text_height) // 2
                
                # 添加文字描邊（黑色）
                stroke_width = max(1, font_size // 20)
                draw.text((x, y), text, font=font, fill='white', 
                         stroke_width=stroke_width, stroke_fill='black')
            
            return image
            
        except Exception as e:
            logger.error(f"❌ 添加迷因文字失敗: {e}")
            return image

    async def _calculate_font_size(self, text: str, max_width: int, max_height: int, 
                                 base_font: ImageFont.ImageFont) -> int:
        """計算適合的字體大小"""
        try:
            # 創建臨時繪製對象
            temp_image = Image.new('RGB', (1, 1))
            draw = ImageDraw.Draw(temp_image)
            
            # 從較大字體開始測試
            for font_size in range(60, 10, -2):
                try:
                    test_font = ImageFont.truetype(self.font_paths.get("chinese", self.font_paths["default"]), font_size)
                    bbox = draw.textbbox((0, 0), text, font=test_font)
                    text_width = bbox[2] - bbox[0]
                    text_height = bbox[3] - bbox[1]
                    
                    if text_width <= max_width * 0.9 and text_height <= max_height * 0.9:
                        return font_size
                except:
                    continue
            
            return 12  # 最小字體大小
            
        except Exception as e:
            logger.error(f"❌ 計算字體大小失敗: {e}")
            return 20

    # ========== 頭像處理 ==========

    async def create_avatar_frame(self, avatar_url: str, frame_style: str = "circle") -> ProcessedImage:
        """為頭像添加框架"""
        start_time = datetime.now()
        
        try:
            # 下載頭像
            avatar_image = await self.download_image(avatar_url)
            if not avatar_image:
                raise ValueError("無法下載頭像")
            
            # 調整頭像大小
            size = 300
            avatar_image = avatar_image.resize((size, size))
            
            # 創建框架
            if frame_style == "circle":
                framed_image = await self._create_circle_frame(avatar_image)
            elif frame_style == "square":
                framed_image = await self._create_square_frame(avatar_image)
            elif frame_style == "hexagon":
                framed_image = await self._create_hexagon_frame(avatar_image)
            else:
                framed_image = avatar_image
            
            # 轉換為字節
            image_data = self.image_to_bytes(framed_image, 'PNG')
            
            processing_time = (datetime.now() - start_time).total_seconds()
            
            return ProcessedImage(
                image_data=image_data,
                format='PNG',
                size=framed_image.size,
                file_size=len(image_data),
                processing_time=processing_time,
                success=True
            )
            
        except Exception as e:
            logger.error(f"❌ 創建頭像框架失敗: {e}")
            processing_time = (datetime.now() - start_time).total_seconds()
            return ProcessedImage(
                image_data=b'',
                format='PNG',
                size=(0, 0),
                file_size=0,
                processing_time=processing_time,
                success=False,
                error_message=str(e)
            )

    async def _create_circle_frame(self, image: Image.Image) -> Image.Image:
        """創建圓形框架"""
        try:
            size = image.size[0]
            
            # 創建遮罩
            mask = Image.new('L', (size, size), 0)
            draw = ImageDraw.Draw(mask)
            draw.ellipse((0, 0, size, size), fill=255)
            
            # 應用遮罩
            result = Image.new('RGBA', (size, size), (0, 0, 0, 0))
            result.paste(image, (0, 0))
            result.putalpha(mask)
            
            # 添加邊框
            draw = ImageDraw.Draw(result)
            draw.ellipse((2, 2, size-2, size-2), outline='white', width=4)
            
            return result
            
        except Exception as e:
            logger.error(f"❌ 創建圓形框架失敗: {e}")
            return image

    async def _create_square_frame(self, image: Image.Image) -> Image.Image:
        """創建方形框架"""
        try:
            size = image.size[0]
            
            # 創建新圖片
            result = Image.new('RGBA', (size + 20, size + 20), (255, 255, 255, 255))
            result.paste(image, (10, 10))
            
            # 添加邊框
            draw = ImageDraw.Draw(result)
            draw.rectangle((5, 5, size + 15, size + 15), outline='black', width=3)
            
            return result
            
        except Exception as e:
            logger.error(f"❌ 創建方形框架失敗: {e}")
            return image

    async def _create_hexagon_frame(self, image: Image.Image) -> Image.Image:
        """創建六邊形框架"""
        try:
            size = image.size[0]
            
            # 創建六邊形遮罩
            mask = Image.new('L', (size, size), 0)
            draw = ImageDraw.Draw(mask)
            
            # 計算六邊形頂點
            center = size // 2
            radius = size // 2 - 10
            points = []
            for i in range(6):
                angle = i * 60 * 3.14159 / 180
                x = center + radius * (angle)
                y = center + radius * (angle)
                points.append((x, y))
            
            draw.polygon(points, fill=255)
            
            # 應用遮罩
            result = Image.new('RGBA', (size, size), (0, 0, 0, 0))
            result.paste(image, (0, 0))
            result.putalpha(mask)
            
            return result
            
        except Exception as e:
            logger.error(f"❌ 創建六邊形框架失敗: {e}")
            return image

# 全域實例
image_processor = ImageProcessor()