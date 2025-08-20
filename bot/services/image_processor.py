# bot/services/image_processor.py - 圖片處理服務
"""
圖片處理服務 - Phase 5
提供格式轉換、特效處理、壓縮等完整圖片處理功能
"""

import asyncio
import aiohttp
import io
import time
from typing import Dict, List, Optional, Any, Union, Tuple
from datetime import datetime, timezone
from dataclasses import dataclass
from enum import Enum
import os
import tempfile

# 嘗試導入 PIL，提供友善的錯誤訊息
try:
    from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageEnhance
    PIL_AVAILABLE = True
except ImportError as e:
    PIL_AVAILABLE = False
    PIL_ERROR = str(e)

from shared.logger import logger


class ImageFormat(Enum):
    """支援的圖片格式"""
    PNG = "png"
    JPEG = "jpeg"
    WEBP = "webp" 
    GIF = "gif"
    BMP = "bmp"


class ImageEffect(Enum):
    """圖片特效類型"""
    BLUR = "blur"
    SHARPEN = "sharpen"
    VINTAGE = "vintage"
    GRAYSCALE = "grayscale"
    SEPIA = "sepia"
    BRIGHTNESS = "brightness"
    CONTRAST = "contrast"
    SATURATION = "saturation"


class ImageOperation(Enum):
    """圖片處理操作"""
    RESIZE = "resize"
    COMPRESS = "compress"
    FORMAT_CONVERT = "format_convert"
    APPLY_EFFECT = "apply_effect"
    WATERMARK = "watermark"


@dataclass
class ImageProcessRequest:
    """圖片處理請求"""
    image_url: str
    operation: ImageOperation
    parameters: Dict[str, Any]
    output_format: ImageFormat = ImageFormat.PNG
    quality: int = 85


@dataclass
class ProcessedImage:
    """處理後的圖片結果"""
    success: bool
    image_data: Optional[bytes] = None
    file_size: int = 0
    size: Tuple[int, int] = (0, 0)
    processing_time: float = 0.0
    error_message: Optional[str] = None
    format: str = "png"


class ImageProcessor:
    """圖片處理器"""
    
    def __init__(self):
        # 檢查 PIL 可用性
        if not PIL_AVAILABLE:
            logger.error(f"❌ PIL/Pillow 未安裝: {PIL_ERROR}")
            logger.error("請安裝: pip install Pillow")
        
        # 支援的輸入格式
        self.supported_input_formats = {
            'image/jpeg', 'image/jpg', 'image/png', 'image/gif', 
            'image/webp', 'image/bmp', 'image/tiff'
        }
        
        # 壓縮品質設定
        self.quality_presets = {
            "high": 90,
            "medium": 75,
            "low": 60
        }
        
        logger.info("🖼️ 圖片處理器初始化完成")
    
    async def process_image(self, request: ImageProcessRequest) -> ProcessedImage:
        """處理圖片的主要方法"""
        if not PIL_AVAILABLE:
            return ProcessedImage(
                success=False,
                error_message=f"PIL/Pillow 未安裝: {PIL_ERROR}"
            )
        
        start_time = time.time()
        
        try:
            # 下載圖片
            image_data = await self._download_image(request.image_url)
            if not image_data:
                return ProcessedImage(
                    success=False,
                    error_message="無法下載圖片"
                )
            
            # 載入圖片
            image = Image.open(io.BytesIO(image_data))
            original_size = image.size
            
            # 根據操作類型處理圖片
            processed_image = await self._apply_operation(image, request)
            
            if not processed_image:
                return ProcessedImage(
                    success=False,
                    error_message="圖片處理失敗"
                )
            
            # 轉換輸出格式
            output_data = await self._convert_format(
                processed_image, 
                request.output_format,
                request.quality
            )
            
            processing_time = time.time() - start_time
            
            return ProcessedImage(
                success=True,
                image_data=output_data,
                file_size=len(output_data),
                size=processed_image.size,
                processing_time=processing_time,
                format=request.output_format.value
            )
            
        except Exception as e:
            logger.error(f"❌ 圖片處理錯誤: {e}")
            return ProcessedImage(
                success=False,
                error_message=f"處理失敗: {str(e)}"
            )
    
    async def _download_image(self, url: str) -> Optional[bytes]:
        """下載圖片"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as response:
                    if response.status == 200:
                        return await response.read()
                    else:
                        logger.error(f"❌ 下載圖片失敗: HTTP {response.status}")
                        return None
                        
        except Exception as e:
            logger.error(f"❌ 下載圖片錯誤: {e}")
            return None
    
    async def _apply_operation(self, image: Image.Image, request: ImageProcessRequest) -> Optional[Image.Image]:
        """應用處理操作"""
        try:
            operation = request.operation
            params = request.parameters
            
            if operation == ImageOperation.RESIZE:
                return await self._resize_image(image, params)
            elif operation == ImageOperation.COMPRESS:
                return image  # 壓縮在格式轉換時處理
            elif operation == ImageOperation.FORMAT_CONVERT:
                return image  # 格式轉換在後續處理
            elif operation == ImageOperation.APPLY_EFFECT:
                return await self._apply_effect(image, params)
            else:
                logger.warning(f"⚠️ 不支援的操作: {operation}")
                return image
                
        except Exception as e:
            logger.error(f"❌ 應用操作失敗: {e}")
            return None
    
    async def _resize_image(self, image: Image.Image, params: Dict[str, Any]) -> Image.Image:
        """調整圖片尺寸"""
        try:
            width = params.get('width', image.width)
            height = params.get('height', image.height)
            maintain_aspect = params.get('maintain_aspect', True)
            
            if maintain_aspect:
                # 保持寬高比
                image.thumbnail((width, height), Image.Resampling.LANCZOS)
                return image
            else:
                # 強制尺寸
                return image.resize((width, height), Image.Resampling.LANCZOS)
                
        except Exception as e:
            logger.error(f"❌ 調整尺寸失敗: {e}")
            return image
    
    async def _apply_effect(self, image: Image.Image, params: Dict[str, Any]) -> Image.Image:
        """應用圖片特效"""
        try:
            effect_type = params.get('effect_type', ImageEffect.VINTAGE)
            intensity = params.get('intensity', 1.0)
            
            if isinstance(effect_type, str):
                effect_type = ImageEffect(effect_type)
            
            # 轉換為 RGB 模式（如果需要）
            if image.mode != 'RGB':
                image = image.convert('RGB')
            
            if effect_type == ImageEffect.BLUR:
                return image.filter(ImageFilter.GaussianBlur(radius=intensity * 2))
            
            elif effect_type == ImageEffect.SHARPEN:
                return image.filter(ImageFilter.UnsharpMask(
                    radius=intensity, 
                    percent=150, 
                    threshold=3
                ))
            
            elif effect_type == ImageEffect.GRAYSCALE:
                return image.convert('L').convert('RGB')
            
            elif effect_type == ImageEffect.SEPIA:
                return self._apply_sepia(image, intensity)
            
            elif effect_type == ImageEffect.VINTAGE:
                return self._apply_vintage(image, intensity)
            
            elif effect_type == ImageEffect.BRIGHTNESS:
                enhancer = ImageEnhance.Brightness(image)
                return enhancer.enhance(intensity)
            
            elif effect_type == ImageEffect.CONTRAST:
                enhancer = ImageEnhance.Contrast(image)
                return enhancer.enhance(intensity)
            
            elif effect_type == ImageEffect.SATURATION:
                enhancer = ImageEnhance.Color(image)
                return enhancer.enhance(intensity)
            
            else:
                logger.warning(f"⚠️ 不支援的特效: {effect_type}")
                return image
                
        except Exception as e:
            logger.error(f"❌ 應用特效失敗: {e}")
            return image
    
    def _apply_sepia(self, image: Image.Image, intensity: float) -> Image.Image:
        """應用懷舊棕褐色效果"""
        try:
            # 轉換為灰階
            grayscale = image.convert('L')
            
            # 創建棕褐色調色板
            sepia_palette = []
            for i in range(256):
                r = min(255, int(i * 1.0))
                g = min(255, int(i * 0.8))
                b = min(255, int(i * 0.4))
                sepia_palette.extend([r, g, b])
            
            # 應用調色板
            sepia_image = grayscale.quantize(palette=Image.new('P', (1, 1)))
            sepia_image.putpalette(sepia_palette)
            sepia_image = sepia_image.convert('RGB')
            
            # 混合原圖和棕褐色效果
            return Image.blend(image, sepia_image, intensity * 0.7)
            
        except Exception as e:
            logger.error(f"❌ 棕褐色效果失敗: {e}")
            return image
    
    def _apply_vintage(self, image: Image.Image, intensity: float) -> Image.Image:
        """應用復古濾鏡效果"""
        try:
            # 降低飽和度
            enhancer = ImageEnhance.Color(image)
            desaturated = enhancer.enhance(0.7)
            
            # 調整對比度
            enhancer = ImageEnhance.Contrast(desaturated)
            contrasted = enhancer.enhance(1.2)
            
            # 添加輕微的暖色調
            warm_filter = Image.new('RGB', contrasted.size, (255, 240, 200))
            vintage = Image.blend(contrasted, warm_filter, 0.1 * intensity)
            
            return vintage
            
        except Exception as e:
            logger.error(f"❌ 復古效果失敗: {e}")
            return image
    
    async def _convert_format(self, image: Image.Image, output_format: ImageFormat, quality: int) -> bytes:
        """轉換圖片格式"""
        try:
            output = io.BytesIO()
            format_name = output_format.value.upper()
            
            # 處理特殊格式
            if format_name == 'JPEG':
                # JPEG 不支援透明度
                if image.mode in ('RGBA', 'LA'):
                    # 創建白色背景
                    background = Image.new('RGB', image.size, (255, 255, 255))
                    if image.mode == 'RGBA':
                        background.paste(image, mask=image.split()[-1])
                    else:
                        background.paste(image)
                    image = background
                image.save(output, format='JPEG', quality=quality, optimize=True)
            
            elif format_name == 'PNG':
                image.save(output, format='PNG', optimize=True)
            
            elif format_name == 'WEBP':
                image.save(output, format='WEBP', quality=quality, optimize=True)
            
            elif format_name == 'GIF':
                # GIF 需要調色板模式
                if image.mode != 'P':
                    image = image.quantize(colors=256)
                image.save(output, format='GIF', optimize=True)
            
            elif format_name == 'BMP':
                image.save(output, format='BMP')
            
            else:
                # 預設使用 PNG
                image.save(output, format='PNG', optimize=True)
            
            return output.getvalue()
            
        except Exception as e:
            logger.error(f"❌ 格式轉換失敗: {e}")
            # 回退到 PNG
            output = io.BytesIO()
            image.save(output, format='PNG')
            return output.getvalue()
    
    async def batch_process(self, requests: List[ImageProcessRequest]) -> List[ProcessedImage]:
        """批量處理圖片"""
        try:
            tasks = []
            for request in requests:
                tasks.append(self.process_image(request))
            
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # 處理異常結果
            processed_results = []
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    processed_results.append(ProcessedImage(
                        success=False,
                        error_message=f"批量處理錯誤: {str(result)}"
                    ))
                else:
                    processed_results.append(result)
            
            return processed_results
            
        except Exception as e:
            logger.error(f"❌ 批量處理失敗: {e}")
            return [ProcessedImage(
                success=False,
                error_message=f"批量處理失敗: {str(e)}"
            )]


# 全域實例
image_processor = ImageProcessor()