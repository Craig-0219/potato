"""
💬 Conversation Manager - 對話管理系統
管理多輪對話狀態和上下文記憶

Author: Potato Bot Development Team
Version: 3.1.0 - Phase 7 Stage 1
"""

import asyncio
import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

from .ai_engine_manager import AIEngineManager, ConversationContext
from .intent_recognition import IntentRecognizer, IntentType

logger = logging.getLogger(__name__)


class ConversationState(Enum):
    """對話狀態"""

    IDLE = "idle"  # 閒置狀態
    ACTIVE = "active"  # 活躍對話中
    WAITING_INPUT = "waiting_input"  # 等待用戶輸入
    PROCESSING = "processing"  # 處理中
    ENDED = "ended"  # 對話結束
    ERROR = "error"  # 錯誤狀態


class ConversationFlow(Enum):
    """對話流程類型"""

    SIMPLE_QA = "simple_qa"  # 簡單問答
    TICKET_CREATION = "ticket_creation"  # 票券創建流程
    VOTE_CREATION = "vote_creation"  # 投票創建流程
    WELCOME_SETUP = "welcome_setup"  # 歡迎設定流程
    TROUBLESHOOTING = "troubleshooting"  # 故障排除流程
    GUIDED_TOUR = "guided_tour"  # 導覽流程


@dataclass
class ConversationStep:
    """對話步驟"""

    step_id: str
    message: str
    expected_input: Optional[str] = None
    validation: Optional[Dict[str, Any]] = None
    next_steps: List[str] = field(default_factory=list)
    is_final: bool = False


@dataclass
class ConversationSession:
    """對話會話"""

    session_id: str
    user_id: str
    guild_id: str
    channel_id: str
    state: ConversationState
    flow: Optional[ConversationFlow]
    current_step: Optional[str]
    context: ConversationContext
    metadata: Dict[str, Any]
    created_at: float
    last_activity: float
    steps_completed: List[str] = field(default_factory=list)
    collected_data: Dict[str, Any] = field(default_factory=dict)


class ConversationManager:
    """
    💬 對話管理器

    功能:
    - 多輪對話狀態管理
    - 對話流程控制
    - 上下文記憶
    - 會話持久化
    - 智能回應生成
    """

    def __init__(
        self,
        ai_engine: AIEngineManager,
        intent_recognizer: IntentRecognizer,
        config: Dict[str, Any],
    ):
        self.ai_engine = ai_engine
        self.intent_recognizer = intent_recognizer
        self.config = config

        # 活躍會話存儲
        self.active_sessions: Dict[str, ConversationSession] = {}

        # 對話流程定義
        self.conversation_flows = {}

        # 會話清理任務
        self.cleanup_task = None

        # 初始化對話流程
        self._initialize_flows()

        # 啟動清理任務
        self._start_cleanup_task()

    def _initialize_flows(self):
        """初始化對話流程"""

        # 票券創建流程
        self.conversation_flows[ConversationFlow.TICKET_CREATION] = {
            "start": ConversationStep(
                step_id="start",
                message="我來幫您建立支援票券！請告訴我您遇到的問題類型：\n\n"
                + "1. 🐛 Bug 回報\n2. ❓ 使用問題\n3. 💡 功能建議\n4. 🔧 技術支援\n\n"
                + "請輸入數字 1-4 或描述您的問題：",
                expected_input="problem_type",
                next_steps=["priority"],
            ),
            "priority": ConversationStep(
                step_id="priority",
                message="了解了！請選擇問題的優先級：\n\n"
                + "1. 🔴 緊急 - 系統無法使用\n2. 🟡 重要 - 影響正常使用\n3. 🟢 一般 - 可以繼續使用\n\n"
                + "請輸入數字 1-3：",
                expected_input="priority_level",
                next_steps=["description"],
            ),
            "description": ConversationStep(
                step_id="description",
                message="請詳細描述您的問題，包括：\n"
                + "• 問題發生的具體情況\n• 您期望的結果\n• 如有錯誤訊息請一併提供",
                expected_input="detailed_description",
                next_steps=["confirmation"],
            ),
            "confirmation": ConversationStep(
                step_id="confirmation",
                message="請確認票券資訊：\n\n"
                + "**問題類型**: {problem_type}\n"
                + "**優先級**: {priority_level}\n"
                + "**描述**: {detailed_description}\n\n"
                + "確認建立票券嗎？（是/否）",
                expected_input="confirmation",
                next_steps=["complete"],
                is_final=True,
            ),
        }

        # 投票創建流程
        self.conversation_flows[ConversationFlow.VOTE_CREATION] = {
            "start": ConversationStep(
                step_id="start",
                message="我來幫您建立投票！首先請告訴我投票的標題：",
                expected_input="vote_title",
                next_steps=["options"],
            ),
            "options": ConversationStep(
                step_id="options",
                message="很好！現在請提供投票選項，每行一個選項：\n\n"
                + "例如：\n選項 A: 週六下午\n選項 B: 週日晚上\n選項 C: 下週平日\n\n"
                + "請輸入您的選項：",
                expected_input="vote_options",
                next_steps=["duration"],
            ),
            "duration": ConversationStep(
                step_id="duration",
                message="請選擇投票持續時間：\n\n"
                + "1. 🕐 1 小時\n2. 📅 1 天\n3. 📆 3 天\n4. 🗓️ 1 週\n5. 🔧 自訂時間\n\n"
                + "請輸入數字 1-5：",
                expected_input="vote_duration",
                next_steps=["settings"],
            ),
            "settings": ConversationStep(
                step_id="settings",
                message="投票設定：\n\n"
                + "1. 允許多選？（是/否）\n2. 匿名投票？（是/否）\n3. 顯示即時結果？（是/否）\n\n"
                + "請依序回答（例如：是 否 是）：",
                expected_input="vote_settings",
                next_steps=["confirmation"],
            ),
            "confirmation": ConversationStep(
                step_id="confirmation",
                message="投票資訊確認：\n\n"
                + "**標題**: {vote_title}\n"
                + "**選項**: {vote_options}\n"
                + "**持續時間**: {vote_duration}\n"
                + "**設定**: {vote_settings}\n\n"
                + "確認建立投票嗎？（是/否）",
                expected_input="confirmation",
                next_steps=["complete"],
                is_final=True,
            ),
        }

        # 歡迎系統設定流程
        self.conversation_flows[ConversationFlow.WELCOME_SETUP] = {
            "start": ConversationStep(
                step_id="start",
                message="歡迎設定嚮導開始！我會協助您設定新成員歡迎功能。\n\n"
                + "首先，請選擇歡迎訊息發送的頻道：\n"
                + "• 輸入頻道名稱（例如：#general）\n"
                + "• 或輸入 '當前頻道' 使用這個頻道",
                expected_input="welcome_channel",
                next_steps=["message"],
            ),
            "message": ConversationStep(
                step_id="message",
                message="很好！現在請設計您的歡迎訊息。\n\n"
                + "可以使用的變數：\n"
                + "• `{user}` - 用戶名稱\n"
                + "• `{server}` - 伺服器名稱\n"
                + "• `{memberCount}` - 成員數量\n\n"
                + "請輸入您的歡迎訊息：",
                expected_input="welcome_message",
                next_steps=["roles"],
            ),
            "roles": ConversationStep(
                step_id="roles",
                message="是否要為新成員自動分配角色？\n\n"
                + "• 輸入角色名稱（例如：@新成員）\n"
                + "• 輸入 '無' 不分配角色\n"
                + "• 可以輸入多個角色，用逗號分隔",
                expected_input="auto_roles",
                next_steps=["confirmation"],
            ),
            "confirmation": ConversationStep(
                step_id="confirmation",
                message="歡迎系統設定確認：\n\n"
                + "**頻道**: {welcome_channel}\n"
                + "**歡迎訊息**: {welcome_message}\n"
                + "**自動角色**: {auto_roles}\n\n"
                + "確認啟用歡迎系統嗎？（是/否）",
                expected_input="confirmation",
                next_steps=["complete"],
                is_final=True,
            ),
        }

        logger.info(f"✅ 對話流程初始化完成，支援 {len(self.conversation_flows)} 種流程")

    async def start_conversation(
        self,
        user_id: str,
        guild_id: str,
        channel_id: str,
        initial_message: str,
        flow: Optional[ConversationFlow] = None,
    ) -> ConversationSession:
        """
        開始新對話

        Args:
            user_id: 用戶 ID
            guild_id: 伺服器 ID
            channel_id: 頻道 ID
            initial_message: 初始訊息
            flow: 指定的對話流程

        Returns:
            對話會話
        """
        session_id = self._generate_session_id(user_id, guild_id)

        # 如果存在活躍會話，先結束它
        if session_id in self.active_sessions:
            await self.end_conversation(session_id)

        # 識別意圖和流程
        if not flow:
            intent_result = await self.intent_recognizer.recognize_intent(
                initial_message, user_id, {"guild_id": guild_id}
            )
            flow = self._intent_to_flow(intent_result.intent)

        # 建立對話上下文
        context = ConversationContext(
            user_id=user_id,
            guild_id=guild_id,
            channel_id=channel_id,
            conversation_id=session_id,
            history=[{"role": "user", "content": initial_message}],
        )

        # 建立會話
        session = ConversationSession(
            session_id=session_id,
            user_id=user_id,
            guild_id=guild_id,
            channel_id=channel_id,
            state=ConversationState.ACTIVE,
            flow=flow,
            current_step=None,
            context=context,
            metadata={"initial_message": initial_message},
            created_at=time.time(),
            last_activity=time.time(),
        )

        # 存儲會話
        self.active_sessions[session_id] = session

        logger.info(f"🎬 開始新對話: {session_id}, 流程: {flow}")

        return session

    async def process_message(self, session_id: str, message: str) -> Optional[str]:
        """
        處理對話訊息

        Args:
            session_id: 會話 ID
            message: 用戶訊息

        Returns:
            AI 回應內容
        """
        if session_id not in self.active_sessions:
            logger.warning(f"⚠️ 會話不存在: {session_id}")
            return None

        session = self.active_sessions[session_id]
        session.last_activity = time.time()
        session.state = ConversationState.PROCESSING

        try:
            # 更新對話歷史
            session.context.history.append({"role": "user", "content": message})

            # 如果有對話流程，按流程處理
            if session.flow and session.flow in self.conversation_flows:
                response = await self._process_flow_message(session, message)
            else:
                # 自由對話模式
                response = await self._process_free_conversation(session, message)

            # 更新對話歷史
            if response:
                session.context.history.append({"role": "assistant", "content": response})

            session.state = ConversationState.ACTIVE
            return response

        except Exception as e:
            logger.error(f"❌ 對話處理失敗: {e}")
            session.state = ConversationState.ERROR
            return "抱歉，我遇到了一些問題。請稍後再試或聯繫管理員協助。"

    async def _process_flow_message(self, session: ConversationSession, message: str) -> str:
        """處理流程化對話訊息"""
        flow_config = self.conversation_flows[session.flow]

        # 如果是第一次處理，開始流程
        if not session.current_step:
            session.current_step = "start"
            step = flow_config["start"]
            return step.message

        current_step = flow_config[session.current_step]

        # 驗證輸入
        if await self._validate_input(session, current_step, message):
            # 保存數據
            if current_step.expected_input:
                session.collected_data[current_step.expected_input] = message

            session.steps_completed.append(session.current_step)

            # 如果是最終步驟
            if current_step.is_final:
                return await self._complete_flow(session, message)

            # 移動到下一步
            if current_step.next_steps:
                next_step_id = current_step.next_steps[0]  # 簡化處理，取第一個下一步
                session.current_step = next_step_id
                next_step = flow_config[next_step_id]

                # 格式化訊息（替換變數）
                formatted_message = self._format_message(next_step.message, session.collected_data)
                return formatted_message
            else:
                # 流程結束
                return await self._complete_flow(session, message)
        else:
            # 輸入無效，重新提示
            return f"輸入格式不正確，請重新輸入。\n\n{current_step.message}"

    async def _process_free_conversation(self, session: ConversationSession, message: str) -> str:
        """處理自由對話"""
        # 識別意圖
        intent_result = await self.intent_recognizer.recognize_intent(
            message,
            session.user_id,
            {
                "guild_id": session.guild_id,
                "conversation_history": session.context.history[-5:],  # 最近5輪對話
            },
        )

        # 如果識別到特定意圖，可能需要切換到流程模式
        if intent_result.confidence > 0.8:
            new_flow = self._intent_to_flow(intent_result.intent)
            if new_flow and new_flow != session.flow:
                session.flow = new_flow
                session.current_step = None
                return await self._process_flow_message(session, message)

        # 生成自由對話回應
        ai_response = await self.ai_engine.generate_response(
            message, session.context, temperature=0.7
        )

        return ai_response.content

    async def _validate_input(
        self, session: ConversationSession, step: ConversationStep, message: str
    ) -> bool:
        """驗證用戶輸入"""
        if not step.expected_input:
            return True

        message_lower = message.lower().strip()

        # 基本驗證規則
        if step.expected_input == "problem_type":
            return message_lower in ["1", "2", "3", "4"] or len(message) > 5

        elif step.expected_input == "priority_level":
            return message_lower in ["1", "2", "3"]

        elif step.expected_input == "vote_duration":
            return message_lower in ["1", "2", "3", "4", "5"]

        elif step.expected_input == "confirmation":
            return message_lower in ["是", "否", "yes", "no", "y", "n", "確認", "取消"]

        elif step.expected_input in [
            "detailed_description",
            "vote_title",
            "welcome_message",
        ]:
            return len(message.strip()) >= 10  # 至少10個字符

        elif step.expected_input == "vote_options":
            # 檢查是否有多個選項
            lines = [line.strip() for line in message.split("\n") if line.strip()]
            return len(lines) >= 2

        elif step.expected_input == "vote_settings":
            # 檢查是否有三個設定值
            parts = message.split()
            return len(parts) >= 3

        return True  # 其他情況默認通過

    def _format_message(self, message: str, data: Dict[str, Any]) -> str:
        """格式化訊息，替換變數"""
        try:
            return message.format(**data)
        except KeyError:
            return message  # 如果格式化失敗，返回原訊息

    async def _complete_flow(self, session: ConversationSession, final_input: str) -> str:
        """完成對話流程"""
        try:
            if session.flow == ConversationFlow.TICKET_CREATION:
                return await self._complete_ticket_creation(session, final_input)
            elif session.flow == ConversationFlow.VOTE_CREATION:
                return await self._complete_vote_creation(session, final_input)
            elif session.flow == ConversationFlow.WELCOME_SETUP:
                return await self._complete_welcome_setup(session, final_input)
            else:
                return "對話流程已完成，感謝您的使用！"
        finally:
            # 結束會話
            session.state = ConversationState.ENDED
            await asyncio.sleep(1)  # 短暫延遲後清理
            if session.session_id in self.active_sessions:
                del self.active_sessions[session.session_id]

    async def _complete_ticket_creation(
        self, session: ConversationSession, confirmation: str
    ) -> str:
        """完成票券創建"""
        if confirmation.lower().strip() in ["是", "yes", "y", "確認"]:
            # 這裡應該調用票券系統創建票券
            data = session.collected_data

            # 轉換優先級
            priority_map = {"1": "high", "2": "medium", "3": "low"}
            priority = priority_map.get(data.get("priority_level", "3"), "low")

            # 轉換問題類型
            type_map = {
                "1": "bug_report",
                "2": "question",
                "3": "feature_request",
                "4": "technical_support",
            }
            ticket_type = type_map.get(data.get("problem_type", "2"), "question")

            return (
                f"✅ **票券建立成功！**\n\n"
                + f"📋 **票券編號**: #{int(time.time()) % 10000}\n"
                + f"🎯 **類型**: {ticket_type}\n"
                + f"⚡ **優先級**: {priority}\n"
                + f"📝 **描述**: {data.get('detailed_description', 'N/A')}\n\n"
                + f"我們會盡快處理您的票券，請留意通知訊息。"
            )
        else:
            return "❌ 票券創建已取消。如需協助，請隨時再次聯繫我們！"

    async def _complete_vote_creation(self, session: ConversationSession, confirmation: str) -> str:
        """完成投票創建"""
        if confirmation.lower().strip() in ["是", "yes", "y", "確認"]:
            # 這裡應該調用投票系統創建投票
            data = session.collected_data

            return (
                f"🗳️ **投票建立成功！**\n\n"
                + f"📊 **標題**: {data.get('vote_title', 'N/A')}\n"
                + f"⏰ **持續時間**: {data.get('vote_duration', 'N/A')}\n"
                + f"⚙️ **設定**: {data.get('vote_settings', 'N/A')}\n\n"
                + f"投票已開始，成員可以開始投票了！"
            )
        else:
            return "❌ 投票創建已取消。如需重新建立，請告訴我！"

    async def _complete_welcome_setup(self, session: ConversationSession, confirmation: str) -> str:
        """完成歡迎系統設定"""
        if confirmation.lower().strip() in ["是", "yes", "y", "確認"]:
            # 這裡應該調用歡迎系統配置
            data = session.collected_data

            return (
                f"👋 **歡迎系統設定成功！**\n\n"
                + f"📍 **頻道**: {data.get('welcome_channel', 'N/A')}\n"
                + f"💬 **訊息**: {data.get('welcome_message', 'N/A')[:100]}...\n"
                + f"🎭 **自動角色**: {data.get('auto_roles', '無')}\n\n"
                + f"歡迎系統已啟用，新成員加入時會自動觸發！"
            )
        else:
            return "❌ 歡迎系統設定已取消。如需重新設定，請告訴我！"

    def _intent_to_flow(self, intent: IntentType) -> Optional[ConversationFlow]:
        """將意圖轉換為對話流程"""
        intent_flow_map = {
            IntentType.TICKET_CREATE: ConversationFlow.TICKET_CREATION,
            IntentType.VOTE_CREATE: ConversationFlow.VOTE_CREATION,
            IntentType.WELCOME_SETUP: ConversationFlow.WELCOME_SETUP,
        }
        return intent_flow_map.get(intent)

    def _generate_session_id(self, user_id: str, guild_id: str) -> str:
        """生成會話 ID"""
        return f"{guild_id}_{user_id}_{int(time.time())}"

    async def end_conversation(self, session_id: str) -> bool:
        """結束對話"""
        if session_id not in self.active_sessions:
            return False

        session = self.active_sessions[session_id]
        session.state = ConversationState.ENDED
        del self.active_sessions[session_id]

        logger.info(f"🔚 對話結束: {session_id}")
        return True

    async def get_session(self, session_id: str) -> Optional[ConversationSession]:
        """獲取對話會話"""
        return self.active_sessions.get(session_id)

    async def list_active_sessions(
        self, user_id: Optional[str] = None
    ) -> List[ConversationSession]:
        """列出活躍會話"""
        sessions = list(self.active_sessions.values())
        if user_id:
            sessions = [s for s in sessions if s.user_id == user_id]
        return sessions

    def _start_cleanup_task(self):
        """啟動清理任務"""

        async def cleanup_expired_sessions():
            while True:
                try:
                    current_time = time.time()
                    expired_sessions = []

                    for session_id, session in self.active_sessions.items():
                        # 30分鐘無活動的會話被認為過期
                        if current_time - session.last_activity > 1800:
                            expired_sessions.append(session_id)

                    for session_id in expired_sessions:
                        await self.end_conversation(session_id)
                        logger.info(f"🧹 清理過期會話: {session_id}")

                    # 每5分鐘檢查一次
                    await asyncio.sleep(300)

                except Exception as e:
                    logger.error(f"❌ 清理任務錯誤: {e}")
                    await asyncio.sleep(60)  # 出錯時等待1分鐘

        self.cleanup_task = asyncio.create_task(cleanup_expired_sessions())

    async def get_statistics(self) -> Dict[str, Any]:
        """獲取對話統計"""
        active_count = len(self.active_sessions)

        flow_counts = {}
        state_counts = {}

        for session in self.active_sessions.values():
            flow = session.flow.value if session.flow else "free"
            flow_counts[flow] = flow_counts.get(flow, 0) + 1

            state = session.state.value
            state_counts[state] = state_counts.get(state, 0) + 1

        return {
            "active_sessions": active_count,
            "flow_distribution": flow_counts,
            "state_distribution": state_counts,
            "supported_flows": [flow.value for flow in ConversationFlow],
        }

    async def shutdown(self):
        """關閉對話管理器"""
        if self.cleanup_task:
            self.cleanup_task.cancel()

        # 結束所有活躍會話
        session_ids = list(self.active_sessions.keys())
        for session_id in session_ids:
            await self.end_conversation(session_id)

        logger.info("💬 對話管理器已關閉")
