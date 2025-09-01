# bot/services/ai_assistant.py - AI智能助手服務
"""
AI智能助手服務 v2.2.0
整合ChatGPT和其他AI服務，提供智能對話、創意內容生成等功能
"""

import re
import time
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional

import aiohttp

from shared.cache_manager import cache_manager
from shared.config import (
    ANTHROPIC_API_KEY,
    GEMINI_API_KEY,
    OPENAI_API_KEY,
)
from shared.logger import logger

# 引入 Phase 7 新的 AI 服務
from .ai.ai_engine_manager import AIEngineManager
from .ai.conversation_manager import ConversationFlow, ConversationManager
from .ai.intent_recognition import IntentRecognizer, IntentType


class AIProvider(Enum):
    """AI服務提供商"""

    OPENAI = "openai"
    CLAUDE = "claude"
    GEMINI = "gemini"
    LOCAL = "local"


class AITaskType(Enum):
    """AI任務類型"""

    CHAT = "chat"  # 聊天對話
    CODE_HELP = "code_help"  # 代碼助手
    TRANSLATE = "translate"  # 翻譯
    CREATIVE_WRITING = "creative"  # 創意寫作
    SUMMARY = "summary"  # 內容摘要
    EXPLANATION = "explanation"  # 解釋說明
    STORY_GENERATION = "story"  # 故事生成
    POEM_GENERATION = "poem"  # 詩歌生成
    AD_COPY = "ad_copy"  # 廣告文案


@dataclass
class AIRequest:
    """AI請求"""

    user_id: int
    guild_id: int
    task_type: AITaskType
    prompt: str
    context: Dict[str, Any]
    provider: AIProvider = AIProvider.OPENAI
    max_tokens: int = 1000
    temperature: float = 0.7


@dataclass
class AIResponse:
    """AI回應"""

    request_id: str
    content: str
    tokens_used: int
    response_time: float
    provider: AIProvider
    success: bool
    error_message: Optional[str] = None
    metadata: Dict[str, Any] = None

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


class AIAssistantManager:
    """AI助手管理器 - Phase 5 增強版"""

    def __init__(self):
        # 初始化 API 密鑰
        self.api_keys = {
            AIProvider.OPENAI: OPENAI_API_KEY,
            AIProvider.CLAUDE: ANTHROPIC_API_KEY,
            AIProvider.GEMINI: GEMINI_API_KEY,
        }

        # 檢查 API 密鑰可用性
        self.available_providers = []
        for provider, key in self.api_keys.items():
            if key:
                self.available_providers.append(provider)
                logger.info(f"✅ {provider.value} API 密鑰已配置")
            else:
                logger.warning(f"⚠️ {provider.value} API 密鑰未配置")

        self.rate_limits = {
            AIProvider.OPENAI: {
                "rpm": 60,
                "tpm": 50000,
            },  # 每分鐘請求數和token數
            AIProvider.CLAUDE: {"rpm": 30, "tpm": 30000},
            AIProvider.GEMINI: {"rpm": 100, "tpm": 100000},
        }

        # 用戶使用統計 (內存快取)
        self.usage_stats = {}
        self.rate_limit_cache = {}

        # AI模型配置 - Phase 5 更新
        self.models = {
            AIProvider.OPENAI: {
                "chat": "gpt-3.5-turbo",
                "creative": "gpt-4",
                "code": "gpt-4",
                "analysis": "gpt-4-turbo-preview",
            },
            AIProvider.CLAUDE: {
                "chat": "claude-3-haiku-20240307",
                "creative": "claude-3-sonnet-20240229",
                "code": "claude-3-sonnet-20240229",
                "analysis": "claude-3-opus-20240229",
            },
            AIProvider.GEMINI: {
                "chat": "gemini-pro",
                "creative": "gemini-pro",
                "code": "gemini-pro",
            },
        }

        # API 端點配置
        self.api_endpoints = {
            AIProvider.OPENAI: "https://api.openai.com/v1/chat/completions",
            AIProvider.CLAUDE: "https://api.anthropic.com/v1/messages",
            AIProvider.GEMINI: "https://generativelanguage.googleapis.com/v1beta/models/gemini-pro:generateContent",
        }

        # 預設提示詞模板
        self.prompt_templates = {
            AITaskType.CHAT: {
                "system": "你是一個友善、有幫助的Discord機器人助手。請用繁體中文回答用戶問題，保持回答簡潔而有用。",
                "user": "{prompt}",
            },
            AITaskType.CODE_HELP: {
                "system": "你是一個專業的程式設計助手。請幫助用戶解決程式設計問題，提供清晰的解釋和可執行的代碼範例。",
                "user": "請幫我解決這個程式設計問題：{prompt}",
            },
            AITaskType.TRANSLATE: {
                "system": "你是一個專業的翻譯助手。請提供準確、自然的翻譯。",
                "user": "請將以下內容翻譯為{target_language}：{prompt}",
            },
            AITaskType.CREATIVE_WRITING: {
                "system": "你是一個創意寫作助手。請根據用戶的要求創作有趣、引人入勝的內容。",
                "user": "請根據以下要求進行創意寫作：{prompt}",
            },
            AITaskType.STORY_GENERATION: {
                "system": "你是一個故事創作大師。請創作引人入勝、情節豐富的故事。",
                "user": "請根據以下設定創作一個故事：{prompt}",
            },
            AITaskType.POEM_GENERATION: {
                "system": "你是一個詩歌創作專家。請創作優美、有韻律的詩歌。",
                "user": "請根據以下主題創作詩歌：{prompt}",
            },
            AITaskType.AD_COPY: {
                "system": "你是一個廣告文案專家。請創作吸引人、有說服力的廣告文案。",
                "user": "請為以下產品/服務創作廣告文案：{prompt}",
            },
        }

        # 內容過濾規則
        self.content_filters = [
            r"(暴力|血腥|殺害)",
            r"(色情|性[行為暗示]|裸體)",
            r"(毒品|吸毒|販毒)",
            r"(自殺|自殘|死亡威脅)",
            r"(恐怖主義|極端思想)",
            r"(種族歧視|仇恨言論)",
        ]

        logger.info("🤖 AI助手管理器初始化完成")

    def configure_api_key(self, provider: AIProvider, api_key: str):
        """配置API密鑰"""
        self.api_keys[provider] = api_key
        logger.info(f"🔑 {provider.value} API密鑰已配置")

    # ========== 核心AI請求處理 ==========

    async def process_request(self, ai_request: AIRequest) -> AIResponse:
        """處理AI請求"""
        start_time = time.time()
        request_id = f"{ai_request.user_id}_{int(start_time)}"

        try:
            # 檢查速率限制
            if not await self._check_rate_limit(
                ai_request.user_id, ai_request.provider
            ):
                return AIResponse(
                    request_id=request_id,
                    content="",
                    tokens_used=0,
                    response_time=0,
                    provider=ai_request.provider,
                    success=False,
                    error_message="超過速率限制，請稍後再試",
                )

            # 內容過濾
            if not await self._filter_content(ai_request.prompt):
                return AIResponse(
                    request_id=request_id,
                    content="",
                    tokens_used=0,
                    response_time=0,
                    provider=ai_request.provider,
                    success=False,
                    error_message="請求內容不適當，已被過濾",
                )

            # 構建提示詞
            formatted_prompt = await self._build_prompt(ai_request)

            # 發送到AI服務
            response_content, tokens_used = await self._call_ai_service(
                ai_request.provider, formatted_prompt, ai_request
            )

            response_time = time.time() - start_time

            # 記錄使用量
            await self._record_usage(
                ai_request.user_id, tokens_used, ai_request.provider
            )

            return AIResponse(
                request_id=request_id,
                content=response_content,
                tokens_used=tokens_used,
                response_time=response_time,
                provider=ai_request.provider,
                success=True,
                metadata={
                    "task_type": ai_request.task_type.value,
                    "model_used": self.models.get(ai_request.provider, {}).get(
                        "chat", "unknown"
                    ),
                },
            )

        except Exception as e:
            logger.error(f"❌ AI請求處理失敗: {e}")
            return AIResponse(
                request_id=request_id,
                content="",
                tokens_used=0,
                response_time=time.time() - start_time,
                provider=ai_request.provider,
                success=False,
                error_message=str(e),
            )

    async def _build_prompt(
        self, ai_request: AIRequest
    ) -> List[Dict[str, str]]:
        """構建格式化的提示詞"""
        try:
            template = self.prompt_templates.get(ai_request.task_type)
            if not template:
                template = self.prompt_templates[AITaskType.CHAT]

            # 替換模板變量
            context = ai_request.context or {}
            user_prompt = template["user"].format(
                prompt=ai_request.prompt, **context
            )

            messages = [
                {"role": "system", "content": template["system"]},
                {"role": "user", "content": user_prompt},
            ]

            return messages

        except Exception as e:
            logger.error(f"❌ 構建提示詞失敗: {e}")
            raise

    async def _call_ai_service(
        self,
        provider: AIProvider,
        messages: List[Dict[str, str]],
        ai_request: AIRequest,
    ) -> tuple[str, int]:
        """調用AI服務"""
        if provider == AIProvider.OPENAI:
            return await self._call_openai(messages, ai_request)
        elif provider == AIProvider.CLAUDE:
            return await self._call_claude(messages, ai_request)
        elif provider == AIProvider.GEMINI:
            return await self._call_gemini(messages, ai_request)
        else:
            raise ValueError(f"不支持的AI提供商: {provider}")

    async def _call_openai(
        self, messages: List[Dict[str, str]], ai_request: AIRequest
    ) -> tuple[str, int]:
        """調用OpenAI API"""
        try:
            api_key = self.api_keys.get(AIProvider.OPENAI)
            if not api_key:
                raise ValueError("OpenAI API密鑰未配置")

            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            }

            # 選擇模型
            model = self.models[AIProvider.OPENAI].get(
                ai_request.task_type.value.split("_")[0],
                self.models[AIProvider.OPENAI]["chat"],
            )

            payload = {
                "model": model,
                "messages": messages,
                "max_tokens": ai_request.max_tokens,
                "temperature": ai_request.temperature,
                "stream": False,
            }

            async with aiohttp.ClientSession() as session:
                async with session.post(
                    "https://api.openai.com/v1/chat/completions",
                    headers=headers,
                    json=payload,
                    timeout=30,
                ) as response:

                    if response.status != 200:
                        error_text = await response.text()
                        raise Exception(
                            f"OpenAI API錯誤 {response.status}: {error_text}"
                        )

                    result = await response.json()

                    content = result["choices"][0]["message"]["content"]
                    tokens_used = result["usage"]["total_tokens"]

                    return content, tokens_used

        except Exception as e:
            logger.error(f"❌ OpenAI API調用失敗: {e}")
            raise

    async def _call_claude(
        self, messages: List[Dict[str, str]], ai_request: AIRequest
    ) -> tuple[str, int]:
        """調用Claude API - Phase 5 實現"""
        try:
            api_key = self.api_keys.get(AIProvider.CLAUDE)
            if not api_key:
                raise ValueError("Claude API密鑰未配置")

            headers = {
                "x-api-key": api_key,
                "content-type": "application/json",
                "anthropic-version": "2023-06-01",
            }

            # 選擇模型
            model = self.models[AIProvider.CLAUDE].get(
                ai_request.task_type.value.split("_")[0],
                self.models[AIProvider.CLAUDE]["chat"],
            )

            # 將 OpenAI 格式的 messages 轉換為 Claude 格式
            system_message = ""
            claude_messages = []

            for msg in messages:
                if msg["role"] == "system":
                    system_message = msg["content"]
                else:
                    claude_messages.append(
                        {"role": msg["role"], "content": msg["content"]}
                    )

            payload = {
                "model": model,
                "max_tokens": ai_request.max_tokens,
                "temperature": ai_request.temperature,
                "messages": claude_messages,
            }

            if system_message:
                payload["system"] = system_message

            async with aiohttp.ClientSession() as session:
                async with session.post(
                    "https://api.anthropic.com/v1/messages",
                    headers=headers,
                    json=payload,
                    timeout=30,
                ) as response:

                    if response.status != 200:
                        error_text = await response.text()
                        raise Exception(
                            f"Claude API錯誤 {response.status}: {error_text}"
                        )

                    result = await response.json()

                    content = result["content"][0]["text"]
                    tokens_used = (
                        result["usage"]["input_tokens"]
                        + result["usage"]["output_tokens"]
                    )

                    return content, tokens_used

        except Exception as e:
            logger.error(f"❌ Claude API調用失敗: {e}")
            raise

    async def _call_gemini(
        self, messages: List[Dict[str, str]], ai_request: AIRequest
    ) -> tuple[str, int]:
        """調用Gemini API (預留接口)"""
        # 預留給未來Gemini API整合
        raise NotImplementedError("Gemini API整合開發中")

    # ========== 內容過濾和安全 ==========

    async def _filter_content(self, content: str) -> bool:
        """內容過濾"""
        try:
            content_lower = content.lower()

            for filter_pattern in self.content_filters:
                if re.search(filter_pattern, content_lower):
                    logger.warning(f"⚠️ 內容被過濾: {filter_pattern}")
                    return False

            return True

        except Exception as e:
            logger.error(f"❌ 內容過濾失敗: {e}")
            return True  # 過濾失敗時允許通過

    # ========== 速率限制和使用統計 ==========

    async def _check_rate_limit(
        self, user_id: int, provider: AIProvider
    ) -> bool:
        """檢查速率限制"""
        try:
            cache_key = f"ai_rate_limit:{provider.value}:{user_id}"

            # 獲取當前計數
            current_count = await cache_manager.get(cache_key)
            if current_count is None:
                current_count = 0

            rate_limit = self.rate_limits.get(provider, {"rpm": 10})["rpm"]

            if current_count >= rate_limit:
                return False

            # 增加計數
            await cache_manager.set(
                cache_key, current_count + 1, 60
            )  # 1分鐘過期

            return True

        except Exception as e:
            logger.error(f"❌ 檢查速率限制失敗: {e}")
            return True  # 檢查失敗時允許通過

    async def _record_usage(
        self, user_id: int, tokens_used: int, provider: AIProvider
    ):
        """記錄使用量"""
        try:
            # 記錄到緩存
            daily_key = f"ai_usage_daily:{provider.value}:{user_id}"
            monthly_key = f"ai_usage_monthly:{provider.value}:{user_id}"

            daily_usage = await cache_manager.get(daily_key) or 0
            monthly_usage = await cache_manager.get(monthly_key) or 0

            await cache_manager.set(
                daily_key, daily_usage + tokens_used, 86400
            )  # 24小時
            await cache_manager.set(
                monthly_key, monthly_usage + tokens_used, 2592000
            )  # 30天

        except Exception as e:
            logger.error(f"❌ 記錄使用量失敗: {e}")

    async def get_user_usage(
        self, user_id: int, provider: AIProvider
    ) -> Dict[str, int]:
        """獲取用戶使用量統計"""
        try:
            daily_key = f"ai_usage_daily:{provider.value}:{user_id}"
            monthly_key = f"ai_usage_monthly:{provider.value}:{user_id}"

            daily_usage = await cache_manager.get(daily_key) or 0
            monthly_usage = await cache_manager.get(monthly_key) or 0

            return {
                "daily_tokens": daily_usage,
                "monthly_tokens": monthly_usage,
                "daily_limit": self.rate_limits.get(provider, {"rpm": 10})[
                    "rpm"
                ],
                "monthly_limit": self.rate_limits.get(
                    provider, {"tpm": 10000}
                )["tpm"],
            }

        except Exception as e:
            logger.error(f"❌ 獲取使用量統計失敗: {e}")
            return {"daily_tokens": 0, "monthly_tokens": 0}

    # ========== 便捷方法 ==========

    async def chat(
        self,
        user_id: int,
        guild_id: int,
        message: str,
        provider: AIProvider = AIProvider.OPENAI,
    ) -> AIResponse:
        """簡單聊天"""
        request = AIRequest(
            user_id=user_id,
            guild_id=guild_id,
            task_type=AITaskType.CHAT,
            prompt=message,
            context={},
            provider=provider,
        )
        return await self.process_request(request)

    async def help_with_code(
        self,
        user_id: int,
        guild_id: int,
        code_question: str,
        language: str = "python",
    ) -> AIResponse:
        """代碼助手"""
        request = AIRequest(
            user_id=user_id,
            guild_id=guild_id,
            task_type=AITaskType.CODE_HELP,
            prompt=code_question,
            context={"language": language},
            provider=AIProvider.OPENAI,
        )
        return await self.process_request(request)

    async def translate_text(
        self,
        user_id: int,
        guild_id: int,
        text: str,
        target_language: str = "英文",
    ) -> AIResponse:
        """翻譯文本"""
        request = AIRequest(
            user_id=user_id,
            guild_id=guild_id,
            task_type=AITaskType.TRANSLATE,
            prompt=text,
            context={"target_language": target_language},
            provider=AIProvider.OPENAI,
        )
        return await self.process_request(request)

    async def generate_story(
        self, user_id: int, guild_id: int, theme: str, style: str = "輕鬆幽默"
    ) -> AIResponse:
        """生成故事"""
        request = AIRequest(
            user_id=user_id,
            guild_id=guild_id,
            task_type=AITaskType.STORY_GENERATION,
            prompt=f"主題：{theme}，風格：{style}",
            context={"style": style},
            provider=AIProvider.OPENAI,
            max_tokens=1500,
            temperature=0.8,
        )
        return await self.process_request(request)

    async def generate_poem(
        self, user_id: int, guild_id: int, theme: str, style: str = "現代詩"
    ) -> AIResponse:
        """生成詩歌"""
        request = AIRequest(
            user_id=user_id,
            guild_id=guild_id,
            task_type=AITaskType.POEM_GENERATION,
            prompt=f"主題：{theme}，詩歌類型：{style}",
            context={"style": style},
            provider=AIProvider.OPENAI,
            max_tokens=800,
            temperature=0.9,
        )
        return await self.process_request(request)

    async def create_ad_copy(
        self,
        user_id: int,
        guild_id: int,
        product_info: str,
        target_audience: str = "一般大眾",
    ) -> AIResponse:
        """創建廣告文案"""
        request = AIRequest(
            user_id=user_id,
            guild_id=guild_id,
            task_type=AITaskType.AD_COPY,
            prompt=f"產品信息：{product_info}，目標受眾：{target_audience}",
            context={"target_audience": target_audience},
            provider=AIProvider.OPENAI,
            max_tokens=500,
            temperature=0.7,
        )
        return await self.process_request(request)


class EnhancedAIAssistant:
    """
    🤖 Phase 7 增強型 AI 智能助手
    整合意圖識別、對話管理和企業級 AI 引擎
    """

    def __init__(self):
        # Phase 7 新組件
        self.ai_engine: Optional[AIEngineManager] = None
        self.intent_recognizer: Optional[IntentRecognizer] = None
        self.conversation_manager: Optional[ConversationManager] = None

        # 向後兼容的舊組件
        self.legacy_manager = AIAssistantManager()

        # 初始化狀態
        self.is_initialized = False

    async def initialize(self, config: Optional[Dict[str, Any]] = None):
        """初始化增強型 AI 助手"""
        if self.is_initialized:
            return

        try:
            # 默認配置
            if not config:
                config = {
                    "openai_api_key": OPENAI_API_KEY,
                    "anthropic_api_key": ANTHROPIC_API_KEY,
                    "daily_cost_limit": 10.0,
                    "max_tokens_per_request": 1000,
                    "content_filter_enabled": True,
                    "rate_limit_per_user": 10,
                }

            # 初始化 AI 引擎管理器
            if config.get("openai_api_key") or config.get("anthropic_api_key"):
                self.ai_engine = AIEngineManager(config)
                await self.ai_engine.__aenter__()

            # 初始化意圖識別器
            self.intent_recognizer = IntentRecognizer(config)

            # 初始化對話管理器
            if self.ai_engine and self.intent_recognizer:
                self.conversation_manager = ConversationManager(
                    self.ai_engine, self.intent_recognizer, config
                )

            self.is_initialized = True
            logger.info("✅ Phase 7 增強型 AI 助手初始化完成")

        except Exception as e:
            logger.error(f"❌ AI 助手初始化失敗: {e}")
            raise

    async def smart_chat(
        self,
        user_id: str,
        guild_id: str,
        channel_id: str,
        message: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        智能對話 - 支援意圖識別和多輪對話

        Args:
            user_id: 用戶 ID
            guild_id: 伺服器 ID
            channel_id: 頻道 ID
            message: 用戶訊息
            context: 額外上下文

        Returns:
            AI 回應內容
        """
        if not self.is_initialized:
            await self.initialize()

        try:
            # 如果新組件可用，使用智能對話管理
            if self.conversation_manager:
                # 獲取或創建對話會話
                session_id = f"{guild_id}_{user_id}"
                existing_session = await self.conversation_manager.get_session(
                    session_id
                )

                if not existing_session:
                    # 創建新會話
                    session = (
                        await self.conversation_manager.start_conversation(
                            user_id=user_id,
                            guild_id=guild_id,
                            channel_id=channel_id,
                            initial_message=message,
                        )
                    )
                    session_id = session.session_id

                # 處理訊息
                response = await self.conversation_manager.process_message(
                    session_id, message
                )
                if response:
                    return response

            # 回退到舊版 AI 助手
            request = AIRequest(
                user_id=int(user_id),
                guild_id=int(guild_id),
                task_type=AITaskType.CHAT,
                prompt=message,
                context=context or {},
                provider=AIProvider.OPENAI,
            )

            legacy_response = await self.legacy_manager.process_request(
                request
            )
            return (
                legacy_response.content
                if legacy_response.success
                else "抱歉，我無法處理您的請求。"
            )

        except Exception as e:
            logger.error(f"❌ 智能對話處理失敗: {e}")
            return "抱歉，我遇到了一些技術問題。請稍後再試。"

    async def recognize_intent(
        self, text: str, user_id: str, context: Optional[Dict[str, Any]] = None
    ) -> Optional[IntentType]:
        """識別用戶意圖"""
        if not self.intent_recognizer:
            return None

        try:
            result = await self.intent_recognizer.recognize_intent(
                text, user_id, context or {}
            )
            return result.intent if result.confidence > 0.5 else None
        except Exception as e:
            logger.error(f"❌ 意圖識別失敗: {e}")
            return None

    async def start_guided_conversation(
        self,
        user_id: str,
        guild_id: str,
        channel_id: str,
        flow: ConversationFlow,
    ) -> Optional[str]:
        """開始引導式對話"""
        if not self.conversation_manager:
            return None

        try:
            session = await self.conversation_manager.start_conversation(
                user_id=user_id,
                guild_id=guild_id,
                channel_id=channel_id,
                initial_message="",
                flow=flow,
            )

            # 返回流程開始訊息
            if flow == ConversationFlow.TICKET_CREATION:
                return "🎫 我來幫您建立支援票券！請告訴我您遇到的問題..."
            elif flow == ConversationFlow.VOTE_CREATION:
                return "🗳️ 我來幫您建立投票！首先請告訴我投票的標題..."
            elif flow == ConversationFlow.WELCOME_SETUP:
                return "👋 歡迎系統設定開始！我會協助您設定新成員歡迎功能..."
            else:
                return "✨ 我來協助您完成這個任務！"

        except Exception as e:
            logger.error(f"❌ 引導式對話開始失敗: {e}")
            return None

    async def get_conversation_stats(
        self, user_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """獲取對話統計"""
        stats = {
            "legacy_available": True,
            "enhanced_available": self.is_initialized,
        }

        if self.conversation_manager:
            sessions = await self.conversation_manager.list_active_sessions(
                user_id
            )
            stats.update(
                {
                    "active_sessions": len(sessions),
                    "conversation_manager_stats": await self.conversation_manager.get_statistics(),
                }
            )

        if self.ai_engine:
            stats["ai_engine_stats"] = (
                await self.ai_engine.get_usage_statistics()
            )

        return stats

    async def health_check(self) -> Dict[str, Any]:
        """健康檢查"""
        health = {
            "legacy_manager": True,
            "enhanced_features": self.is_initialized,
            "components": {},
        }

        if self.ai_engine:
            health["components"][
                "ai_engine"
            ] = await self.ai_engine.health_check()

        if self.conversation_manager:
            health["components"]["conversation_manager"] = {
                "active_sessions": len(
                    await self.conversation_manager.list_active_sessions()
                ),
                "status": "healthy",
            }

        return health

    async def shutdown(self):
        """關閉 AI 助手"""
        try:
            if self.conversation_manager:
                await self.conversation_manager.shutdown()

            if self.ai_engine:
                await self.ai_engine.__aexit__(None, None, None)

            logger.info("🤖 增強型 AI 助手已關閉")
        except Exception as e:
            logger.error(f"❌ AI 助手關閉失敗: {e}")


# 全域實例
ai_assistant = AIAssistantManager()

# Phase 7 增強型實例
enhanced_ai_assistant = EnhancedAIAssistant()
