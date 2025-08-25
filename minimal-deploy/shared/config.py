#!/usr/bin/env python3
"""
共享配置模組
"""

import os
from typing import Optional


class Config:
    """配置管理類別"""

    # Discord 設置
    DISCORD_TOKEN: Optional[str] = os.getenv("DISCORD_TOKEN")

    # 資料庫設置
    DB_HOST: str = os.getenv("DB_HOST", "localhost")
    DB_PORT: int = int(os.getenv("DB_PORT", "3306"))
    DB_USER: str = os.getenv("DB_USER", "")
    DB_PASSWORD: str = os.getenv("DB_PASSWORD", "")
    DB_NAME: str = os.getenv("DB_NAME", "potato_bot")

    # JWT 設置
    JWT_SECRET: Optional[str] = os.getenv("JWT_SECRET")

    # 系統設置
    DEBUG: bool = os.getenv("DEBUG", "false").lower() == "true"
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    TIMEZONE: str = os.getenv("TIMEZONE", "UTC")

    @classmethod
    def validate(cls) -> bool:
        """驗證必要的配置"""
        required_vars = [
            ("DISCORD_TOKEN", cls.DISCORD_TOKEN),
            ("DB_HOST", cls.DB_HOST),
            ("DB_USER", cls.DB_USER),
            ("DB_PASSWORD", cls.DB_PASSWORD),
            ("DB_NAME", cls.DB_NAME),
        ]

        missing = [name for name, value in required_vars if not value]

        if missing:
            print(f"❌ 缺少必要環境變數: {', '.join(missing)}")
            return False

        return True
