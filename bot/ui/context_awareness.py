"""
🎯 Context Awareness System - 情境感知系統
為 GUI 選單提供智能情境感知和個性化推薦

Author: Potato Bot Development Team
Version: 3.2.0 - Phase 7 Stage 2
Date: 2025-08-20
"""

import discord
from discord.ext import commands
from typing import Dict, List, Optional, Any, Tuple
import logging
import asyncio
import time
from datetime import datetime, timezone, timedelta
from dataclasses import dataclass, field
from enum import Enum
import json

logger = logging.getLogger(__name__)

class ContextType(Enum):
    """情境類型"""
    SERVER = "server"
    CHANNEL = "channel"
    USER = "user"
    TIME = "time"
    ACTIVITY = "activity"

class RecommendationLevel(Enum):
    """推薦等級"""
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"

@dataclass
class ContextInfo:
    """情境資訊"""
    context_type: ContextType
    value: Any
    confidence: float
    timestamp: float
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class UserPreference:
    """用戶偏好"""
    user_id: str
    feature: str
    usage_count: int
    last_used: float
    preference_score: float
    context_tags: List[str] = field(default_factory=list)

@dataclass
class SmartRecommendation:
    """智能推薦"""
    action: str
    title: str
    description: str
    level: RecommendationLevel
    confidence: float
    reason: str
    context: Dict[str, Any] = field(default_factory=dict)

class ContextAwarenessEngine:
    """
    🎯 情境感知引擎
    
    功能:
    - 分析伺服器當前狀態
    - 學習用戶行為模式
    - 提供智能推薦
    - 個性化選單體驗
    """
    
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.user_preferences: Dict[str, List[UserPreference]] = {}
        self.server_contexts: Dict[str, List[ContextInfo]] = {}
        self.activity_patterns: Dict[str, Any] = {}
        
        # 推薦規則
        self.recommendation_rules = self._initialize_recommendation_rules()
        
        # 清理任務
        self.cleanup_task = None
        self._start_cleanup_task()
    
    def _initialize_recommendation_rules(self) -> Dict[str, Any]:
        """初始化推薦規則"""
        return {
            "new_member_spike": {
                "condition": lambda ctx: ctx.get("new_members_last_hour", 0) > 5,
                "recommendation": SmartRecommendation(
                    action="welcome_setup",
                    title="🚀 新成員激增！",
                    description="檢測到大量新成員加入，建議設定自動歡迎系統",
                    level=RecommendationLevel.HIGH,
                    confidence=0.9,
                    reason="新成員活動激增"
                )
            },
            "support_tickets_high": {
                "condition": lambda ctx: ctx.get("open_tickets", 0) > 10,
                "recommendation": SmartRecommendation(
                    action="admin_dashboard",
                    title="📋 支援票券堆積",
                    description="有多個未處理的支援票券，建議進入管理面板處理",
                    level=RecommendationLevel.HIGH,
                    confidence=0.85,
                    reason="支援負載過高"
                )
            },
            "voting_activity": {
                "condition": lambda ctx: ctx.get("active_votes", 0) > 2,
                "recommendation": SmartRecommendation(
                    action="vote_management", 
                    title="🗳️ 投票活動熱烈",
                    description="多個投票正在進行中，查看投票統計和管理",
                    level=RecommendationLevel.MEDIUM,
                    confidence=0.7,
                    reason="投票活動頻繁"
                )
            },
            "ai_usage_trend": {
                "condition": lambda ctx: ctx.get("ai_interactions_today", 0) > 20,
                "recommendation": SmartRecommendation(
                    action="ai_analytics",
                    title="🤖 AI 使用活躍",
                    description="AI 助手使用頻繁，查看使用分析和優化建議",
                    level=RecommendationLevel.MEDIUM,
                    confidence=0.75,
                    reason="AI 互動增加"
                )
            },
            "quiet_period": {
                "condition": lambda ctx: ctx.get("messages_last_hour", 0) < 5,
                "recommendation": SmartRecommendation(
                    action="engagement_tools",
                    title="💬 互動較少",
                    description="伺服器相對安靜，考慮使用互動工具提升活躍度",
                    level=RecommendationLevel.LOW,
                    confidence=0.6,
                    reason="活動度偏低"
                )
            }
        }
    
    async def analyze_server_context(self, guild_id: str) -> Dict[str, Any]:
        """分析伺服器情境"""
        try:
            guild = self.bot.get_guild(int(guild_id))
            if not guild:
                return {}
            
            context = {
                "guild_id": guild_id,
                "member_count": guild.member_count,
                "channel_count": len(guild.channels),
                "role_count": len(guild.roles),
                "online_members": len([m for m in guild.members if m.status != discord.Status.offline]),
                "timestamp": time.time()
            }
            
            # 獲取最近活動數據（模擬）
            context.update({
                "messages_last_hour": await self._get_recent_message_count(guild_id),
                "new_members_last_hour": await self._get_new_member_count(guild_id),
                "open_tickets": await self._get_open_ticket_count(guild_id),
                "active_votes": await self._get_active_vote_count(guild_id),
                "ai_interactions_today": await self._get_ai_interaction_count(guild_id)
            })
            
            # 儲存情境資訊
            if guild_id not in self.server_contexts:
                self.server_contexts[guild_id] = []
            
            self.server_contexts[guild_id].append(
                ContextInfo(
                    context_type=ContextType.SERVER,
                    value=context,
                    confidence=0.95,
                    timestamp=time.time()
                )
            )
            
            # 只保留最近的情境資訊
            self.server_contexts[guild_id] = self.server_contexts[guild_id][-10:]
            
            return context
            
        except Exception as e:
            logger.error(f"❌ 伺服器情境分析失敗: {e}")
            return {}
    
    async def analyze_user_behavior(self, user_id: str, guild_id: str) -> Dict[str, Any]:
        """分析用戶行為模式"""
        try:
            user_key = f"{guild_id}_{user_id}"
            
            # 獲取用戶偏好
            preferences = self.user_preferences.get(user_key, [])
            
            # 分析使用模式
            behavior_analysis = {
                "user_id": user_id,
                "guild_id": guild_id,
                "total_interactions": len(preferences),
                "most_used_features": self._get_top_features(preferences),
                "usage_frequency": self._calculate_usage_frequency(preferences),
                "time_patterns": self._analyze_time_patterns(preferences),
                "last_activity": max([p.last_used for p in preferences]) if preferences else 0
            }
            
            return behavior_analysis
            
        except Exception as e:
            logger.error(f"❌ 用戶行為分析失敗: {e}")
            return {}
    
    async def generate_smart_recommendations(self, user_id: str, guild_id: str) -> List[SmartRecommendation]:
        """生成智能推薦"""
        try:
            recommendations = []
            
            # 獲取伺服器情境
            server_context = await self.analyze_server_context(guild_id)
            
            # 獲取用戶行為
            user_behavior = await self.analyze_user_behavior(user_id, guild_id)
            
            # 應用推薦規則
            for rule_name, rule_config in self.recommendation_rules.items():
                try:
                    condition = rule_config["condition"]
                    recommendation = rule_config["recommendation"]
                    
                    if condition(server_context):
                        # 根據用戶行為調整推薦
                        adjusted_recommendation = self._adjust_recommendation_for_user(
                            recommendation, user_behavior
                        )
                        recommendations.append(adjusted_recommendation)
                        
                except Exception as e:
                    logger.debug(f"推薦規則 {rule_name} 處理失敗: {e}")
                    continue
            
            # 根據用戶偏好生成個人化推薦
            personal_recommendations = await self._generate_personal_recommendations(user_id, guild_id)
            recommendations.extend(personal_recommendations)
            
            # 排序推薦（高優先級優先）
            recommendations.sort(key=lambda r: (r.level.value, r.confidence), reverse=True)
            
            return recommendations[:5]  # 最多返回5個推薦
            
        except Exception as e:
            logger.error(f"❌ 智能推薦生成失敗: {e}")
            return []
    
    async def record_user_action(self, user_id: str, guild_id: str, action: str, context: Dict[str, Any] = None):
        """記錄用戶行為"""
        try:
            user_key = f"{guild_id}_{user_id}"
            
            if user_key not in self.user_preferences:
                self.user_preferences[user_key] = []
            
            # 尋找現有偏好或創建新的
            existing_pref = None
            for pref in self.user_preferences[user_key]:
                if pref.feature == action:
                    existing_pref = pref
                    break
            
            if existing_pref:
                # 更新現有偏好
                existing_pref.usage_count += 1
                existing_pref.last_used = time.time()
                existing_pref.preference_score = self._calculate_preference_score(existing_pref)
            else:
                # 創建新偏好
                new_pref = UserPreference(
                    user_id=user_id,
                    feature=action,
                    usage_count=1,
                    last_used=time.time(),
                    preference_score=1.0,
                    context_tags=self._extract_context_tags(context or {})
                )
                self.user_preferences[user_key].append(new_pref)
            
            logger.debug(f"📝 記錄用戶行為: {user_id} -> {action}")
            
        except Exception as e:
            logger.error(f"❌ 用戶行為記錄失敗: {e}")
    
    async def get_contextual_menu_options(self, user_id: str, guild_id: str) -> Dict[str, Any]:
        """獲取情境化選單選項"""
        try:
            # 獲取推薦
            recommendations = await self.generate_smart_recommendations(user_id, guild_id)
            
            # 獲取用戶偏好
            user_behavior = await self.analyze_user_behavior(user_id, guild_id)
            
            # 獲取伺服器狀態
            server_context = await self.analyze_server_context(guild_id)
            
            return {
                "recommendations": recommendations,
                "user_preferences": user_behavior,
                "server_status": server_context,
                "suggested_actions": self._get_suggested_actions(recommendations),
                "quick_access": self._get_quick_access_features(user_behavior)
            }
            
        except Exception as e:
            logger.error(f"❌ 情境化選單選項獲取失敗: {e}")
            return {}
    
    # Helper methods
    async def _get_recent_message_count(self, guild_id: str) -> int:
        """獲取最近訊息數量（模擬）"""
        # 實際實現應該從資料庫查詢
        return 15  # 模擬數據
    
    async def _get_new_member_count(self, guild_id: str) -> int:
        """獲取新成員數量（模擬）"""
        return 3  # 模擬數據
    
    async def _get_open_ticket_count(self, guild_id: str) -> int:
        """獲取開放票券數量（模擬）"""
        return 7  # 模擬數據
    
    async def _get_active_vote_count(self, guild_id: str) -> int:
        """獲取活躍投票數量（模擬）"""
        return 2  # 模擬數據
    
    async def _get_ai_interaction_count(self, guild_id: str) -> int:
        """獲取 AI 互動數量（模擬）"""
        return 25  # 模擬數據
    
    def _get_top_features(self, preferences: List[UserPreference]) -> List[str]:
        """獲取最常用功能"""
        sorted_prefs = sorted(preferences, key=lambda p: p.usage_count, reverse=True)
        return [p.feature for p in sorted_prefs[:3]]
    
    def _calculate_usage_frequency(self, preferences: List[UserPreference]) -> float:
        """計算使用頻率"""
        if not preferences:
            return 0.0
        
        total_usage = sum(p.usage_count for p in preferences)
        time_span = time.time() - min(p.last_used for p in preferences)
        
        # 避免除以零
        if time_span == 0:
            return float(total_usage)
        
        return total_usage / (time_span / 86400)  # 每日平均使用次數
    
    def _analyze_time_patterns(self, preferences: List[UserPreference]) -> Dict[str, Any]:
        """分析時間模式"""
        if not preferences:
            return {}
        
        # 簡化的時間分析
        recent_usage = [p for p in preferences if time.time() - p.last_used < 86400]
        
        return {
            "recent_activity": len(recent_usage),
            "active_features": len(set(p.feature for p in recent_usage)),
            "last_active": max(p.last_used for p in preferences) if preferences else 0
        }
    
    def _calculate_preference_score(self, preference: UserPreference) -> float:
        """計算偏好分數"""
        # 基於使用次數和最近使用時間
        usage_score = min(preference.usage_count / 10, 1.0)  # 標準化到 0-1
        
        # 時間衰減因子
        time_factor = max(0.1, 1.0 - (time.time() - preference.last_used) / (86400 * 7))  # 7天衰減
        
        return usage_score * time_factor
    
    def _extract_context_tags(self, context: Dict[str, Any]) -> List[str]:
        """提取情境標籤"""
        tags = []
        
        if context.get("is_admin"):
            tags.append("admin")
        if context.get("channel_type"):
            tags.append(f"channel_{context['channel_type']}")
        if context.get("time_of_day"):
            tags.append(f"time_{context['time_of_day']}")
        
        return tags
    
    def _adjust_recommendation_for_user(self, recommendation: SmartRecommendation, user_behavior: Dict[str, Any]) -> SmartRecommendation:
        """根據用戶行為調整推薦"""
        # 如果用戶經常使用相關功能，提高信心度
        most_used = user_behavior.get("most_used_features", [])
        
        adjusted_recommendation = SmartRecommendation(
            action=recommendation.action,
            title=recommendation.title,
            description=recommendation.description,
            level=recommendation.level,
            confidence=recommendation.confidence,
            reason=recommendation.reason,
            context=recommendation.context
        )
        
        if recommendation.action in most_used:
            adjusted_recommendation.confidence = min(1.0, adjusted_recommendation.confidence + 0.1)
            adjusted_recommendation.reason += " (基於您的使用習慣)"
        
        return adjusted_recommendation
    
    async def _generate_personal_recommendations(self, user_id: str, guild_id: str) -> List[SmartRecommendation]:
        """生成個人化推薦"""
        recommendations = []
        
        user_key = f"{guild_id}_{user_id}"
        preferences = self.user_preferences.get(user_key, [])
        
        # 如果用戶很少使用某些功能，推薦嘗試
        all_features = ["ai_chat", "ticket_system", "vote_create", "welcome_setup", "admin_tools"]
        unused_features = [f for f in all_features if not any(p.feature == f for p in preferences)]
        
        for feature in unused_features[:2]:  # 最多推薦2個未使用的功能
            recommendations.append(
                SmartRecommendation(
                    action=feature,
                    title=f"✨ 探索 {feature}",
                    description=f"您還沒有使用過 {feature} 功能，不妨試試看！",
                    level=RecommendationLevel.LOW,
                    confidence=0.5,
                    reason="個人化探索建議"
                )
            )
        
        return recommendations
    
    def _get_suggested_actions(self, recommendations: List[SmartRecommendation]) -> List[str]:
        """獲取建議行動"""
        return [r.action for r in recommendations if r.level in [RecommendationLevel.HIGH, RecommendationLevel.MEDIUM]]
    
    def _get_quick_access_features(self, user_behavior: Dict[str, Any]) -> List[str]:
        """獲取快速存取功能"""
        return user_behavior.get("most_used_features", [])[:3]
    
    def _start_cleanup_task(self):
        """啟動清理任務"""
        async def cleanup_old_data():
            while True:
                try:
                    current_time = time.time()
                    
                    # 清理過期的情境資訊（超過24小時）
                    for guild_id in list(self.server_contexts.keys()):
                        self.server_contexts[guild_id] = [
                            ctx for ctx in self.server_contexts[guild_id]
                            if current_time - ctx.timestamp < 86400
                        ]
                        
                        if not self.server_contexts[guild_id]:
                            del self.server_contexts[guild_id]
                    
                    # 清理過期的用戶偏好（超過30天未使用）
                    for user_key in list(self.user_preferences.keys()):
                        self.user_preferences[user_key] = [
                            pref for pref in self.user_preferences[user_key]
                            if current_time - pref.last_used < 2592000  # 30天
                        ]
                        
                        if not self.user_preferences[user_key]:
                            del self.user_preferences[user_key]
                    
                    # 每小時清理一次
                    await asyncio.sleep(3600)
                    
                except Exception as e:
                    logger.error(f"❌ 清理任務錯誤: {e}")
                    await asyncio.sleep(300)  # 錯誤時等待5分鐘
        
        self.cleanup_task = asyncio.create_task(cleanup_old_data())
    
    async def shutdown(self):
        """關閉情境感知引擎"""
        if self.cleanup_task:
            self.cleanup_task.cancel()
        
        logger.info("🎯 情境感知引擎已關閉")

# 全域實例
context_engine = None

def get_context_engine(bot: commands.Bot) -> ContextAwarenessEngine:
    """獲取情境感知引擎實例"""
    global context_engine
    if context_engine is None:
        context_engine = ContextAwarenessEngine(bot)
    return context_engine