# bot/utils/validator.py
"""
資料驗證工具模組
提供各種資料驗證函數
"""

import re
from typing import Any, Dict, List, Optional, Tuple, Union
from datetime import datetime
import discord

from shared.logger import logger


def validate_ticket_data(data: Dict[str, Any]) -> Tuple[bool, str]:
    """驗證票券資料
    
    Args:
        data: 票券資料字典
        
    Returns:
        Tuple[bool, str]: (是否有效, 錯誤訊息)
    """
    try:
        # 檢查必需字段
        required_fields = ['title', 'description', 'guild_id', 'creator_id']
        for field in required_fields:
            if field not in data or not data[field]:
                return False, f"缺少必需字段: {field}"
        
        # 驗證標題長度
        title = data.get('title', '')
        if len(title) > 100:
            return False, "標題長度不能超過100字符"
        
        # 驗證描述長度
        description = data.get('description', '')
        if len(description) > 2000:
            return False, "描述長度不能超過2000字符"
            
        # 驗證ID格式
        guild_id = data.get('guild_id')
        creator_id = data.get('creator_id')
        if not isinstance(guild_id, int) or guild_id <= 0:
            return False, "無效的伺服器ID"
        if not isinstance(creator_id, int) or creator_id <= 0:
            return False, "無效的創建者ID"
            
        return True, ""
        
    except Exception as e:
        logger.error(f"驗證票券資料時發生錯誤: {e}")
        return False, f"驗證過程發生錯誤: {str(e)}"


def validate_vote_data(data: Dict[str, Any]) -> Tuple[bool, str]:
    """驗證投票資料
    
    Args:
        data: 投票資料字典
        
    Returns:
        Tuple[bool, str]: (是否有效, 錯誤訊息)
    """
    try:
        # 檢查必需字段
        required_fields = ['title', 'options', 'guild_id', 'creator_id']
        for field in required_fields:
            if field not in data or not data[field]:
                return False, f"缺少必需字段: {field}"
        
        # 驗證選項
        options = data.get('options', [])
        if not isinstance(options, list) or len(options) < 2:
            return False, "至少需要2個投票選項"
        if len(options) > 10:
            return False, "投票選項不能超過10個"
            
        # 驗證每個選項
        for i, option in enumerate(options):
            if not option or len(option.strip()) == 0:
                return False, f"選項 {i+1} 不能為空"
            if len(option) > 100:
                return False, f"選項 {i+1} 長度不能超過100字符"
                
        return True, ""
        
    except Exception as e:
        logger.error(f"驗證投票資料時發生錯誤: {e}")
        return False, f"驗證過程發生錯誤: {str(e)}"


def validate_discord_id(discord_id: Union[str, int]) -> bool:
    """驗證Discord ID格式
    
    Args:
        discord_id: Discord ID (字符串或整數)
        
    Returns:
        bool: 是否為有效的Discord ID
    """
    try:
        if isinstance(discord_id, str):
            if not discord_id.isdigit():
                return False
            discord_id = int(discord_id)
            
        # Discord ID通常是17-19位的數字
        return 10000000000000000 <= discord_id <= 999999999999999999999
        
    except (ValueError, TypeError):
        return False


def validate_email(email: str) -> bool:
    """驗證電子郵件格式
    
    Args:
        email: 電子郵件地址
        
    Returns:
        bool: 是否為有效的電子郵件格式
    """
    if not email or not isinstance(email, str):
        return False
        
    # 簡單的電子郵件正規表達式
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None


def validate_url(url: str) -> bool:
    """驗證URL格式
    
    Args:
        url: URL地址
        
    Returns:
        bool: 是否為有效的URL格式
    """
    if not url or not isinstance(url, str):
        return False
        
    # 簡單的URL正規表達式
    pattern = r'^https?://[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}(/.*)?$'
    return re.match(pattern, url) is not None


def validate_username(username: str) -> Tuple[bool, str]:
    """驗證用戶名格式
    
    Args:
        username: 用戶名
        
    Returns:
        Tuple[bool, str]: (是否有效, 錯誤訊息)
    """
    if not username or not isinstance(username, str):
        return False, "用戶名不能為空"
        
    username = username.strip()
    
    if len(username) < 2:
        return False, "用戶名長度至少需要2個字符"
    if len(username) > 32:
        return False, "用戶名長度不能超過32個字符"
        
    # 只允許字母、數字、底線和連字號
    if not re.match(r'^[a-zA-Z0-9_-]+$', username):
        return False, "用戶名只能包含字母、數字、底線和連字號"
        
    return True, ""


def sanitize_input(text: str, max_length: int = 1000) -> str:
    """清理和限制輸入文本
    
    Args:
        text: 要清理的文本
        max_length: 最大長度限制
        
    Returns:
        str: 清理後的文本
    """
    if not text or not isinstance(text, str):
        return ""
        
    # 移除危險字符並限制長度
    sanitized = re.sub(r'[<>"\']', '', text)
    sanitized = sanitized.strip()
    
    if len(sanitized) > max_length:
        sanitized = sanitized[:max_length]
        
    return sanitized