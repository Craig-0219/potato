#!/usr/bin/env python3
"""
共享日誌模組
"""

import logging
import os


def setup_logger(name: str, level: str = None) -> logging.Logger:
    """設置日誌記錄器"""

    # 確定日誌級別
    if level is None:
        level = os.getenv("LOG_LEVEL", "INFO")

    log_level = getattr(logging, level.upper(), logging.INFO)

    # 創建記錄器
    logger = logging.getLogger(name)
    logger.setLevel(log_level)

    # 避免重複添加處理器
    if logger.handlers:
        return logger

    # 創建格式化器
    formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")

    # 控制台處理器
    console_handler = logging.StreamHandler()
    console_handler.setLevel(log_level)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # 文件處理器
    try:
        file_handler = logging.FileHandler("bot.log", encoding="utf-8")
        file_handler.setLevel(log_level)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    except Exception as e:
        logger.warning(f"無法創建日誌文件: {e}")

    return logger


# 預設日誌記錄器
logger = setup_logger("potato_bot")
