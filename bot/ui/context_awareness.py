"""
🎯 Context Awareness System - 情境感知系統
為 GUI 選單提供智能情境感知和個性化推薦

Author: Potato Bot Development Team
Version: 3.2.0 - Phase 7 Stage 2
Date: 2025-08-20
"""

import asyncio
import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List

import discord
from discord.ext import commands

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
                    reason="新成員活動激增",
                ),
            },
            "support_tickets_high": {
                "condition": lambda ctx: ctx.get("open_tickets", 0) > 10,
                "recommendation": SmartRecommendation(
                    action="admin_dashboard",
                    title="📋 支援票券堆積",
                    description="有多個未處理的支援票券，建議進入管理面板處理",
                    level=RecommendationLevel.HIGH,
                    confidence=0.85,
                    reason="支援負載過高",
                ),
            },
            "voting_activity": {
                "condition": lambda ctx: ctx.get("active_votes", 0) > 2,
                "recommendation": SmartRecommendation(
                    action="vote_management",
                    title="🗳️ 投票活動熱烈",
                    description="多個投票正在進行中，查看投票統計和管理",
                    level=RecommendationLevel.MEDIUM,
                    confidence=0.7,
                    reason="投票活動頻繁",
                ),
            },
            "ai_usage_trend": {
                "condition": lambda ctx: ctx.get("ai_interactions_today", 0) > 20,
                "recommendation": SmartRecommendation(
                    action="ai_analytics",
                    title="🤖 AI 使用活躍",
                    description="AI 助手使用頻繁，查看使用分析和優化建議",
                    level=RecommendationLevel.MEDIUM,
                    confidence=0.75,
                    reason="AI 互動增加",
                ),
            },
            "quiet_period": {
                "condition": lambda ctx: ctx.get("messages_last_hour", 0) < 5,
                "recommendation": SmartRecommendation(
                    action="engagement_tools",
                    title="💬 互動較少",
                    description="伺服器相對安靜，考慮使用互動工具提升活躍度",
                    level=RecommendationLevel.LOW,
                    confidence=0.6,
                    reason="活動度偏低",
                ),
            },
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
                "online_members": len(
                    [m for m in guild.members if m.status != discord.Status.offline]
                ),
                "timestamp": time.time(),
            }

            # 獲取最近活動數據（模擬）
            context.update(
                {
                    "messages_last_hour": await self._get_recent_message_count(guild_id),
                    "new_members_last_hour": await self._get_new_member_count(guild_id),
                    "open_tickets": await self._get_open_ticket_count(guild_id),
                    "active_votes": await self._get_active_vote_count(guild_id),
                    "ai_interactions_today": await self._get_ai_interaction_count(guild_id),
                }
            )

            # 儲存情境資訊
            if guild_id not in self.server_contexts:
                self.server_contexts[guild_id] = []

            self.server_contexts[guild_id].append(
                ContextInfo(
                    context_type=ContextType.SERVER,
                    value=context,
                    confidence=0.95,
                    timestamp=time.time(),
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
                "last_activity": (max([p.last_used for p in preferences]) if preferences else 0),
            }

            return behavior_analysis

        except Exception as e:
            logger.error(f"❌ 用戶行為分析失敗: {e}")
            return {}

    async def generate_smart_recommendations(
        self, user_id: str, guild_id: str
    ) -> List[SmartRecommendation]:
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
                    logger.error(f"❌ 推薦規則處理失敗: {e}")
                    continue

            return recommendations

        except Exception as e:
            logger.error(f"❌ 智能推薦生成失敗: {e}")
            return []

    def _adjust_recommendation_for_user(
        self, recommendation: SmartRecommendation, user_behavior: Dict[str, Any]
    ) -> SmartRecommendation:
        """根據用戶行為調整推薦"""
        try:
            # 根據用戶使用頻率調整信心度
            if user_behavior.get("total_interactions", 0) > 100:
                recommendation.confidence = min(1.0, recommendation.confidence + 0.1)

            # 根據最近活動調整優先級
            last_activity = user_behavior.get("last_activity", 0)
            if time.time() - last_activity < 3600:  # 最近一小時內活躍
                if recommendation.level == RecommendationLevel.LOW:
                    recommendation.level = RecommendationLevel.MEDIUM

            return recommendation

        except Exception as e:
            logger.error(f"❌ 推薦調整失敗: {e}")
            return recommendation

    def _get_top_features(self, preferences: List[UserPreference]) -> List[str]:
        """獲取最常用功能"""
        try:
            sorted_prefs = sorted(preferences, key=lambda p: p.usage_count, reverse=True)
            return [p.feature for p in sorted_prefs[:5]]
        except Exception as e:
            logger.error(f"❌ 獲取熱門功能失敗: {e}")
            return []

    def _calculate_usage_frequency(self, preferences: List[UserPreference]) -> float:
        """計算使用頻率"""
        try:
            if not preferences:
                return 0.0

            total_usage = sum(p.usage_count for p in preferences)
            time_span = max(p.last_used for p in preferences) - min(
                p.last_used for p in preferences
            )

            if time_span == 0:
                return total_usage

            return total_usage / max(1, time_span / 86400)  # 每日平均使用次數

        except Exception as e:
            logger.error(f"❌ 計算使用頻率失敗: {e}")
            return 0.0

    def _analyze_time_patterns(self, preferences: List[UserPreference]) -> Dict[str, Any]:
        """分析時間模式"""
        try:
            if not preferences:
                return {}

            # 簡化的時間分析
            recent_usage = [p for p in preferences if time.time() - p.last_used < 7 * 86400]

            return {
                "recent_activity": len(recent_usage),
                "most_active_period": "unknown",  # 可以進一步實現
                "usage_trend": "stable",  # 可以進一步實現
            }

        except Exception as e:
            logger.error(f"❌ 時間模式分析失敗: {e}")
            return {}

    async def _get_recent_message_count(self, guild_id: str) -> int:
        """獲取最近訊息數量（模擬）"""
        # 這裡應該從資料庫獲取真實數據
        return 0

    async def _get_new_member_count(self, guild_id: str) -> int:
        """獲取新成員數量（模擬）"""
        # 這裡應該從資料庫獲取真實數據
        return 0

    async def _get_open_ticket_count(self, guild_id: str) -> int:
        """獲取開放票券數量（模擬）"""
        # 這裡應該從資料庫獲取真實數據
        return 0

    async def _get_active_vote_count(self, guild_id: str) -> int:
        """獲取活躍投票數量（模擬）"""
        # 這裡應該從資料庫獲取真實數據
        return 0

    async def _get_ai_interaction_count(self, guild_id: str) -> int:
        """獲取AI互動數量（模擬）"""
        # 這裡應該從資料庫獲取真實數據
        return 0

    def _start_cleanup_task(self):
        """啟動清理任務"""

        async def cleanup_old_data():
            """清理舊數據"""
            while True:
                try:
                    current_time = time.time()

                    # 清理舊的情境資訊
                    for guild_id in list(self.server_contexts.keys()):
                        contexts = self.server_contexts[guild_id]
                        self.server_contexts[guild_id] = [
                            ctx
                            for ctx in contexts
                            if current_time - ctx.timestamp < 86400  # 保留24小時內的數據
                        ]

                    # 清理舊的用戶偏好
                    for user_key in list(self.user_preferences.keys()):
                        preferences = self.user_preferences[user_key]
                        self.user_preferences[user_key] = [
                            pref
                            for pref in preferences
                            if current_time - pref.last_used < 7 * 86400  # 保留7天內的偏好
                        ]

                    await asyncio.sleep(3600)  # 每小時清理一次

                except Exception as e:
                    logger.error(f"❌ 清理任務失敗: {e}")
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
