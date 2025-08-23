"""
🤖 AI Services Package - Phase 7 AI 智能助手系統

This package contains all AI-related services for Potato Bot:
- AI Engine Manager: 多 AI 提供商管理
- Intent Recognition: 意圖識別系統  
- Conversation Manager: 對話管理
- Knowledge Base: 知識庫系統
- Personalization Engine: 個性化引擎

Version: 3.1.0 - Phase 7
"""

from .ai_engine_manager import AIEngineManager, AIProvider, AIResponse, ConversationContext

__all__ = [
    'AIEngineManager',
    'AIProvider', 
    'AIResponse',
    'ConversationContext'
]