# bot/api/routes/__init__.py
"""
API 路由模組
包含所有 API 端點的路由定義
"""

# 路由模組列表
ROUTE_MODULES = [
    "tickets",      # 票券管理 API
    "analytics",    # 分析統計 API
    "automation",   # 自動化規則 API
    "security",     # 安全監控 API
    "system"        # 系統管理 API
]

__all__ = ROUTE_MODULES