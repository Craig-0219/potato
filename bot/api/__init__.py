# bot/api/__init__.py
"""
Potato Discord Bot - API 管理系統
提供 RESTful API 和 GraphQL 端點，支援第三方整合
"""

__version__ = "1.8.0"
__author__ = "Potato Bot Development Team"

# API 版本控制
API_VERSION = "v1"
API_BASE_PATH = f"/api/{API_VERSION}"

# 支援的 API 格式
SUPPORTED_FORMATS = ["json", "xml", "csv", "txt"]

# API 限流設定
DEFAULT_RATE_LIMITS = {
    "requests_per_minute": 60,
    "requests_per_hour": 1000,
    "requests_per_day": 10000
}