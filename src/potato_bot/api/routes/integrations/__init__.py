# bot/api/routes/integrations/__init__.py
"""
企業平台整合 API 路由
"""

from .slack import router as slack_router

__all__ = ["slack_router"]
