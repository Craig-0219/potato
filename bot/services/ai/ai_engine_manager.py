"""
🤖 AI Engine Manager - 企業級 AI 引擎管理系統
負責管理多個 AI 提供商的整合和調度

Author: Potato Bot Development Team
Version: 3.1.0 - Phase 7 Stage 1
"""

import asyncio
import json
import logging
import time
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional, Union

import aiohttp
import openai
from anthropic import AsyncAnthropic

logger = logging.getLogger(__name__)


class AIProvider(Enum):
    """AI 提供商枚舉"""

    OPENAI_GPT4 = "openai_gpt4"
    OPENAI_GPT35 = "openai_gpt35"
    CLAUDE_3_OPUS = "claude_3_opus"
    CLAUDE_3_SONNET = "claude_3_sonnet"
    LOCAL_MODEL = "local_model"


@dataclass
class AIResponse:
    """AI 回應數據結構"""

    content: str
    provider: AIProvider
    model: str
    tokens_used: int
    response_time: float
    confidence: float
    cost: float
    metadata: Dict[str, Any]


@dataclass
class ConversationContext:
    """對話上下文"""

    user_id: str
    guild_id: str
    channel_id: str
    conversation_id: str
    history: List[Dict[str, str]]
    intent: Optional[str] = None
    entities: Dict[str, Any] = None
    user_preferences: Dict[str, Any] = None


class AIEngineManager:
    """
    🤖 AI 引擎管理器

    功能:
    - 多 AI 提供商整合
    - 智能路由和負載均衡
    - 成本控制和配額管理
    - 錯誤處理和容災
    """

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.providers = {}
        self.usage_stats = {}
        self.rate_limits = {}
        self.session = None

        # 初始化 AI 提供商
        self._initialize_providers()

    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()

    def _initialize_providers(self):
        """初始化 AI 提供商"""
        try:
            # OpenAI GPT-4
            if self.config.get("openai_api_key"):
                openai.api_key = self.config["openai_api_key"]
                self.providers[AIProvider.OPENAI_GPT4] = {
                    "client": openai,
                    "model": "gpt-4-1106-preview",
                    "max_tokens": 4000,
                    "cost_per_1k_tokens": 0.03,
                    "rate_limit": 3000,  # RPM
                    "priority": 1,
                }

                self.providers[AIProvider.OPENAI_GPT35] = {
                    "client": openai,
                    "model": "gpt-3.5-turbo-1106",
                    "max_tokens": 4000,
                    "cost_per_1k_tokens": 0.001,
                    "rate_limit": 10000,  # RPM
                    "priority": 2,
                }

            # Anthropic Claude
            if self.config.get("anthropic_api_key"):
                self.providers[AIProvider.CLAUDE_3_OPUS] = {
                    "client": AsyncAnthropic(api_key=self.config["anthropic_api_key"]),
                    "model": "claude-3-opus-20240229",
                    "max_tokens": 4000,
                    "cost_per_1k_tokens": 0.015,
                    "rate_limit": 1000,  # RPM
                    "priority": 1,
                }

                self.providers[AIProvider.CLAUDE_3_SONNET] = {
                    "client": AsyncAnthropic(api_key=self.config["anthropic_api_key"]),
                    "model": "claude-3-sonnet-20240229",
                    "max_tokens": 4000,
                    "cost_per_1k_tokens": 0.003,
                    "rate_limit": 2000,  # RPM
                    "priority": 2,
                }

            logger.info(f"✅ AI 引擎初始化完成，支援 {len(self.providers)} 個提供商")

        except Exception as e:
            logger.error(f"❌ AI 引擎初始化失敗: {e}")
            raise

    async def generate_response(
        self,
        prompt: str,
        context: ConversationContext,
        preferred_provider: Optional[AIProvider] = None,
        max_tokens: Optional[int] = None,
        temperature: float = 0.7,
    ) -> AIResponse:
        """
        生成 AI 回應

        Args:
            prompt: 用戶輸入
            context: 對話上下文
            preferred_provider: 優先使用的提供商
            max_tokens: 最大 token 數
            temperature: 創造性參數

        Returns:
            AI 回應結果
        """
        start_time = time.time()

        try:
            # 選擇最佳 AI 提供商
            provider = await self._select_best_provider(prompt, context, preferred_provider)

            # 建構完整提示詞
            full_prompt = await self._build_full_prompt(prompt, context)

            # 生成回應
            response = await self._call_ai_provider(provider, full_prompt, max_tokens, temperature)

            # 記錄使用統計
            await self._update_usage_stats(provider, response)

            return AIResponse(
                content=response["content"],
                provider=provider,
                model=self.providers[provider]["model"],
                tokens_used=response.get("tokens_used", 0),
                response_time=time.time() - start_time,
                confidence=response.get("confidence", 0.8),
                cost=self._calculate_cost(provider, response.get("tokens_used", 0)),
                metadata=response.get("metadata", {}),
            )

        except Exception as e:
            logger.error(f"❌ AI 回應生成失敗: {e}")

            # 容災處理：嘗試備用提供商
            return await self._fallback_response(prompt, context, e)

    async def _select_best_provider(
        self,
        prompt: str,
        context: ConversationContext,
        preferred_provider: Optional[AIProvider] = None,
    ) -> AIProvider:
        """選擇最佳 AI 提供商"""

        if preferred_provider and preferred_provider in self.providers:
            if await self._check_rate_limit(preferred_provider):
                return preferred_provider

        # 根據提示詞複雜度選擇
        complexity_score = await self._analyze_prompt_complexity(prompt, context)

        # 排序提供商（優先級、可用性、成本）
        available_providers = []
        for provider, config in self.providers.items():
            if await self._check_rate_limit(provider):
                score = (
                    config["priority"] * 0.4
                    + (1.0 / config["cost_per_1k_tokens"]) * 0.3
                    + config["rate_limit"] / 10000 * 0.3
                )
                available_providers.append((provider, score))

        if not available_providers:
            raise Exception("沒有可用的 AI 提供商")

        # 選擇最高分的提供商
        available_providers.sort(key=lambda x: x[1], reverse=True)

        # 對於複雜問題，優先使用高級模型
        if complexity_score > 0.7:
            for provider, _ in available_providers:
                if provider in [AIProvider.OPENAI_GPT4, AIProvider.CLAUDE_3_OPUS]:
                    return provider

        return available_providers[0][0]

    async def _build_full_prompt(self, user_prompt: str, context: ConversationContext) -> str:
        """建構完整的提示詞"""

        system_prompt = f"""你是 Potato Bot 的 AI 智能助手，專門協助用戶管理 Discord 伺服器。

【你的身份】
- 名稱：Potato AI
- 版本：v3.1.0
- 專長：Discord 伺服器管理、票券系統、投票系統、歡迎系統

【當前環境】
- 伺服器 ID：{context.guild_id}
- 頻道 ID：{context.channel_id}
- 用戶 ID：{context.user_id}

【功能能力】
1. 票券系統：建立、管理、追蹤支援票券
2. 投票系統：建立投票、統計結果、分析趨勢
3. 歡迎系統：設定歡迎訊息、自動角色分配
4. 安全管理：權限設定、安全監控、GDPR 合規
5. 數據分析：使用統計、性能監控、洞察報告

【回應原則】
1. 友善專業，用繁體中文回應
2. 提供具體可執行的建議
3. 如需執行指令，請提供完整的指令格式
4. 不確定時，引導用戶到正確的幫助資源
5. 保護用戶隱私，不洩露敏感資訊

【對話歷史】
{self._format_conversation_history(context.history)}

現在請回應用戶的問題：{user_prompt}"""

        return system_prompt

    def _format_conversation_history(self, history: List[Dict[str, str]]) -> str:
        """格式化對話歷史"""
        if not history:
            return "（這是新的對話）"

        formatted = []
        for msg in history[-5:]:  # 只保留最近5條對話
            role = "用戶" if msg.get("role") == "user" else "AI"
            content = msg.get("content", "")[:200]  # 限制長度
            formatted.append(f"{role}：{content}")

        return "\n".join(formatted)

    async def _call_ai_provider(
        self,
        provider: AIProvider,
        prompt: str,
        max_tokens: Optional[int] = None,
        temperature: float = 0.7,
    ) -> Dict[str, Any]:
        """呼叫指定的 AI 提供商"""

        provider_config = self.providers[provider]
        max_tokens = max_tokens or provider_config["max_tokens"]

        try:
            if provider in [AIProvider.OPENAI_GPT4, AIProvider.OPENAI_GPT35]:
                return await self._call_openai(provider_config, prompt, max_tokens, temperature)
            elif provider in [AIProvider.CLAUDE_3_OPUS, AIProvider.CLAUDE_3_SONNET]:
                return await self._call_claude(provider_config, prompt, max_tokens, temperature)
            else:
                raise ValueError(f"不支援的 AI 提供商: {provider}")

        except Exception as e:
            logger.error(f"❌ AI 提供商調用失敗 ({provider}): {e}")
            raise

    async def _call_openai(
        self, config: Dict[str, Any], prompt: str, max_tokens: int, temperature: float
    ) -> Dict[str, Any]:
        """呼叫 OpenAI API"""

        try:
            response = await openai.ChatCompletion.acreate(
                model=config["model"],
                messages=[{"role": "system", "content": prompt}],
                max_tokens=max_tokens,
                temperature=temperature,
                timeout=30,
            )

            return {
                "content": response.choices[0].message.content,
                "tokens_used": response.usage.total_tokens,
                "confidence": 0.9,  # OpenAI 不提供信心分數，設為固定值
                "metadata": {
                    "model": config["model"],
                    "finish_reason": response.choices[0].finish_reason,
                },
            }

        except Exception as e:
            logger.error(f"❌ OpenAI API 調用失敗: {e}")
            raise

    async def _call_claude(
        self, config: Dict[str, Any], prompt: str, max_tokens: int, temperature: float
    ) -> Dict[str, Any]:
        """呼叫 Claude API"""

        try:
            client = config["client"]
            response = await client.messages.create(
                model=config["model"],
                max_tokens=max_tokens,
                temperature=temperature,
                messages=[{"role": "user", "content": prompt}],
            )

            return {
                "content": response.content[0].text,
                "tokens_used": response.usage.input_tokens + response.usage.output_tokens,
                "confidence": 0.85,  # Claude 不提供信心分數，設為固定值
                "metadata": {"model": config["model"], "stop_reason": response.stop_reason},
            }

        except Exception as e:
            logger.error(f"❌ Claude API 調用失敗: {e}")
            raise

    async def _analyze_prompt_complexity(self, prompt: str, context: ConversationContext) -> float:
        """分析提示詞複雜度"""

        complexity_score = 0.0

        # 長度複雜度
        if len(prompt) > 200:
            complexity_score += 0.2
        elif len(prompt) > 500:
            complexity_score += 0.4

        # 技術關鍵詞複雜度
        technical_keywords = [
            "api",
            "資料庫",
            "配置",
            "安全",
            "權限",
            "分析",
            "統計",
            "webhook",
            "json",
            "sql",
            "regex",
            "腳本",
            "自動化",
        ]

        technical_count = sum(1 for keyword in technical_keywords if keyword in prompt.lower())
        complexity_score += min(technical_count * 0.1, 0.3)

        # 對話歷史複雜度
        if len(context.history) > 5:
            complexity_score += 0.1

        return min(complexity_score, 1.0)

    async def _check_rate_limit(self, provider: AIProvider) -> bool:
        """檢查速率限制"""
        current_time = time.time()

        if provider not in self.rate_limits:
            self.rate_limits[provider] = {"requests": [], "daily_cost": 0}

        rate_data = self.rate_limits[provider]

        # 清理過期的請求記錄
        rate_data["requests"] = [
            req_time
            for req_time in rate_data["requests"]
            if current_time - req_time < 60  # 1分鐘內的請求
        ]

        provider_config = self.providers[provider]
        requests_per_minute = len(rate_data["requests"])

        # 檢查每分鐘請求限制
        if requests_per_minute >= provider_config["rate_limit"] / 60:
            logger.warning(f"⚠️ {provider} 達到速率限制")
            return False

        # 檢查每日成本限制
        daily_limit = self.config.get("daily_cost_limit", 50.0)  # $50/day
        if rate_data["daily_cost"] >= daily_limit:
            logger.warning(f"⚠️ {provider} 達到每日成本限制")
            return False

        return True

    async def _update_usage_stats(self, provider: AIProvider, response: Dict[str, Any]):
        """更新使用統計"""
        current_time = time.time()

        if provider not in self.rate_limits:
            self.rate_limits[provider] = {"requests": [], "daily_cost": 0}

        # 記錄請求時間
        self.rate_limits[provider]["requests"].append(current_time)

        # 更新成本
        tokens_used = response.get("tokens_used", 0)
        cost = self._calculate_cost(provider, tokens_used)
        self.rate_limits[provider]["daily_cost"] += cost

        # 記錄到使用統計
        if provider not in self.usage_stats:
            self.usage_stats[provider] = {
                "total_requests": 0,
                "total_tokens": 0,
                "total_cost": 0.0,
                "avg_response_time": 0.0,
            }

        stats = self.usage_stats[provider]
        stats["total_requests"] += 1
        stats["total_tokens"] += tokens_used
        stats["total_cost"] += cost

    def _calculate_cost(self, provider: AIProvider, tokens_used: int) -> float:
        """計算 API 調用成本"""
        if provider not in self.providers:
            return 0.0

        cost_per_1k = self.providers[provider]["cost_per_1k_tokens"]
        return (tokens_used / 1000) * cost_per_1k

    async def _fallback_response(
        self, prompt: str, context: ConversationContext, error: Exception
    ) -> AIResponse:
        """容災回應"""

        fallback_content = f"""抱歉，我目前遇到一些技術問題無法正常回應。

🔧 **可以嘗試的解決方案：**
1. 請稍後再次詢問
2. 使用更具體的問題描述
3. 查看幫助文檔：`/help`
4. 聯繫管理員獲得人工協助

❓ **如果您需要幫助：**
- 票券系統：`/ticket create`
- 投票功能：`/vote create`
- 歡迎設定：`/welcome_setup`

錯誤 ID：{int(time.time())}"""

        return AIResponse(
            content=fallback_content,
            provider=AIProvider.LOCAL_MODEL,
            model="fallback",
            tokens_used=0,
            response_time=0.1,
            confidence=0.5,
            cost=0.0,
            metadata={"error": str(error)},
        )

    async def get_usage_statistics(self) -> Dict[str, Any]:
        """獲取使用統計"""
        return {
            "providers": list(self.providers.keys()),
            "usage_stats": self.usage_stats,
            "rate_limits": self.rate_limits,
            "total_requests": sum(
                stats.get("total_requests", 0) for stats in self.usage_stats.values()
            ),
            "total_cost": sum(stats.get("total_cost", 0.0) for stats in self.usage_stats.values()),
        }

    async def health_check(self) -> Dict[str, Any]:
        """健康檢查"""
        health_status = {}

        for provider in self.providers:
            try:
                # 簡單的 API 可用性測試
                test_response = await self.generate_response(
                    "測試",
                    ConversationContext(
                        user_id="test",
                        guild_id="test",
                        channel_id="test",
                        conversation_id="test",
                        history=[],
                    ),
                    preferred_provider=provider,
                )
                health_status[provider.value] = {
                    "status": "healthy",
                    "response_time": test_response.response_time,
                }
            except Exception as e:
                health_status[provider.value] = {"status": "unhealthy", "error": str(e)}

        return health_status
