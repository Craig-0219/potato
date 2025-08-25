"""
🎯 Intent Recognition System - 意圖識別系統
使用 NLP 技術識別用戶的意圖和實體

Author: Potato Bot Development Team
Version: 3.1.0 - Phase 7 Stage 1
"""

import re
import json
import logging
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
from enum import Enum
import asyncio

logger = logging.getLogger(__name__)

class IntentType(Enum):
    """用戶意圖類型"""
    # 票券相關
    TICKET_CREATE = "ticket_create"
    TICKET_CLOSE = "ticket_close"
    TICKET_LIST = "ticket_list"
    TICKET_STATUS = "ticket_status"
    
    # 投票相關
    VOTE_CREATE = "vote_create"
    VOTE_PARTICIPATE = "vote_participate"
    VOTE_RESULTS = "vote_results"
    VOTE_CLOSE = "vote_close"
    
    # 歡迎系統
    WELCOME_SETUP = "welcome_setup"
    WELCOME_TEST = "welcome_test"
    WELCOME_CONFIG = "welcome_config"
    
    # 伺服器管理
    GUILD_STATS = "guild_stats"
    GUILD_ANALYTICS = "guild_analytics"
    GUILD_PERMISSIONS = "guild_permissions"
    GUILD_SETTINGS = "guild_settings"
    
    # AI 相關
    AI_CHAT = "ai_chat"
    AI_HELP = "ai_help"
    AI_FEEDBACK = "ai_feedback"
    
    # 系統功能
    HELP = "help"
    STATUS = "status"
    SETTINGS = "settings"
    
    # 未知意圖
    UNKNOWN = "unknown"

@dataclass
class Entity:
    """識別出的實體"""
    type: str
    value: str
    confidence: float
    start_pos: int
    end_pos: int

@dataclass
class IntentResult:
    """意圖識別結果"""
    intent: IntentType
    confidence: float
    entities: List[Entity] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

class IntentRecognizer:
    """
    🎯 意圖識別器
    
    功能:
    - 使用規則和 NLP 模型識別用戶意圖
    - 提取實體信息
    - 支援多語言意圖識別
    - 學習和改進識別準確性
    """
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.intent_patterns = {}
        self.entity_patterns = {}
        self.intent_history = {}
        
        # 初始化意圖模式
        self._initialize_patterns()
        
    def _initialize_patterns(self):
        """初始化意圖識別模式"""
        
        # 票券系統意圖模式
        self.intent_patterns[IntentType.TICKET_CREATE] = [
            r"(建立|創建|開立|新增).*(票券|ticket|工單)",
            r"(需要|想要).*(幫助|協助|支援|support)",
            r"(有|遇到).*(問題|錯誤|bug|故障)",
            r"(申請|請求).*(技術支援|客服)",
        ]
        
        self.intent_patterns[IntentType.TICKET_CLOSE] = [
            r"(關閉|結束|完成).*(票券|ticket)",
            r"(解決了|處理完|搞定了)",
            r"(不需要了|取消|算了)",
        ]
        
        self.intent_patterns[IntentType.TICKET_LIST] = [
            r"(查看|顯示|列出).*(我的|all).*(票券|ticket)",
            r"(票券|ticket).*(列表|清單|list)",
            r"(有哪些|多少個).*(票券|ticket)",
        ]
        
        # 投票系統意圖模式
        self.intent_patterns[IntentType.VOTE_CREATE] = [
            r"(建立|創建|發起).*(投票|vote|poll)",
            r"(想要|需要).*(投票|表決|民調)",
            r"(大家|各位).*(選擇|決定|投票)",
        ]
        
        self.intent_patterns[IntentType.VOTE_PARTICIPATE] = [
            r"(我要|我選|投給).*(選項|候選)",
            r"(投票|vote).*([A-Za-z]|[0-9]|選項)",
            r"(支持|選擇|贊成)",
        ]
        
        self.intent_patterns[IntentType.VOTE_RESULTS] = [
            r"(投票|vote).*(結果|統計|數據)",
            r"(目前|現在).*(票數|得票)",
            r"(誰|哪個).*(領先|獲勝|最多票)",
        ]
        
        # 歡迎系統意圖模式
        self.intent_patterns[IntentType.WELCOME_SETUP] = [
            r"(設定|設置|配置).*(歡迎|welcome)",
            r"(歡迎|welcome).*(設定|設置|配置)",
            r"(新成員|新用戶).*(歡迎|迎接)",
        ]
        
        # 伺服器管理意圖模式
        self.intent_patterns[IntentType.GUILD_STATS] = [
            r"(伺服器|server|guild).*(統計|數據|stats)",
            r"(使用|活躍).*(統計|數據|情況)",
            r"(多少|幾個).*(用戶|成員|票券|投票)",
        ]
        
        self.intent_patterns[IntentType.GUILD_ANALYTICS] = [
            r"(分析|analytics|洞察|insights)",
            r"(儀表板|dashboard)",
            r"(詳細|深入).*(分析|統計|數據)",
        ]
        
        # AI 功能意圖模式
        self.intent_patterns[IntentType.AI_CHAT] = [
            r"(聊天|對話|談話)",
            r"(AI|ai|人工智慧|智能助手)",
            r"(你好|嗨|hi|hello)",
            r"(怎麼|如何|怎樣)",
        ]
        
        self.intent_patterns[IntentType.HELP] = [
            r"(幫助|help|說明|教學)",
            r"(不知道|不會|不懂)",
            r"(怎麼用|如何使用|使用方法)",
        ]
        
        # 實體識別模式
        self.entity_patterns = {
            "ticket_priority": [
                (r"(緊急|urgent|高優先|critical)", "high"),
                (r"(重要|important|中優先|medium)", "medium"),
                (r"(一般|normal|低優先|low)", "low"),
            ],
            "vote_duration": [
                (r"(\d+)\s*(小時|hours?|hrs?)", "hours"),
                (r"(\d+)\s*(天|days?)", "days"),
                (r"(\d+)\s*(分鐘|minutes?|mins?)", "minutes"),
            ],
            "user_mention": [
                (r"<@!?(\d+)>", "user_id"),
                (r"@(\w+)", "username"),
            ],
            "channel_mention": [
                (r"<#(\d+)>", "channel_id"),
            ],
            "role_mention": [
                (r"<@&(\d+)>", "role_id"),
            ]
        }
        
        logger.info(f"✅ 意圖識別模式初始化完成，支援 {len(self.intent_patterns)} 種意圖")
    
    async def recognize_intent(self, text: str, user_id: str, context: Dict[str, Any] = None) -> IntentResult:
        """
        識別用戶意圖
        
        Args:
            text: 用戶輸入文本
            user_id: 用戶 ID
            context: 上下文信息
            
        Returns:
            意圖識別結果
        """
        try:
            # 預處理文本
            processed_text = self._preprocess_text(text)
            
            # 基於規則的意圖識別
            intent_scores = await self._rule_based_recognition(processed_text)
            
            # 基於上下文的意圖調整
            if context:
                intent_scores = await self._context_adjustment(intent_scores, context)
            
            # 基於歷史的意圖調整
            intent_scores = await self._history_adjustment(intent_scores, user_id)
            
            # 選擇最可能的意圖
            best_intent, confidence = self._select_best_intent(intent_scores)
            
            # 提取實體
            entities = await self._extract_entities(processed_text, best_intent)
            
            # 記錄意圖歷史
            await self._record_intent_history(user_id, best_intent, confidence)
            
            result = IntentResult(
                intent=best_intent,
                confidence=confidence,
                entities=entities,
                metadata={
                    "processed_text": processed_text,
                    "all_scores": intent_scores,
                    "context": context
                }
            )

            return IntentResult(
                intent=IntentType.UNKNOWN,
                confidence=0.0,
                metadata={"error": str(e)}
            )
    
    def _preprocess_text(self, text: str) -> str:
        """預處理文本"""
        # 轉換為小寫
        text = text.lower().strip()
        
        # 移除多餘的空白
        text = re.sub(r'\s+', ' ', text)
        
        # 移除特殊字符（保留中文、英文、數字、基本符號）
        text = re.sub(r'[^\w\s\u4e00-\u9fff<>@#!?.,]', '', text)
        
        return text
    
    async def _rule_based_recognition(self, text: str) -> Dict[IntentType, float]:
        """基於規則的意圖識別"""
        scores = {}
        
        for intent, patterns in self.intent_patterns.items():
            score = 0.0
            matches = 0
            
            for pattern in patterns:
                if re.search(pattern, text):
                    matches += 1
                    score += 1.0
            
            if matches > 0:
                # 計算信心度：匹配數量 / 總模式數
                confidence = min(matches / len(patterns), 1.0)
                scores[intent] = confidence
            else:
                scores[intent] = 0.0
        
        return scores
    
    async def _context_adjustment(self, scores: Dict[IntentType, float], context: Dict[str, Any]) -> Dict[IntentType, float]:
        """基於上下文調整意圖分數"""
        adjusted_scores = scores.copy()
        
        # 如果在票券頻道，提高票券相關意圖分數
        if context.get('channel_type') == 'ticket':
            ticket_intents = [IntentType.TICKET_CLOSE, IntentType.TICKET_STATUS]
            for intent in ticket_intents:
                if intent in adjusted_scores:
                    adjusted_scores[intent] *= 1.5
        
        # 如果是管理員，提高管理相關意圖分數
        if context.get('is_admin', False):
            admin_intents = [IntentType.GUILD_STATS, IntentType.GUILD_ANALYTICS, IntentType.GUILD_PERMISSIONS]
            for intent in admin_intents:
                if intent in adjusted_scores:
                    adjusted_scores[intent] *= 1.3
        
        # 如果最近有投票活動，提高投票相關意圖分數
        if context.get('recent_vote_activity', False):
            vote_intents = [IntentType.VOTE_PARTICIPATE, IntentType.VOTE_RESULTS]
            for intent in vote_intents:
                if intent in adjusted_scores:
                    adjusted_scores[intent] *= 1.2
        
        return adjusted_scores
    
    async def _history_adjustment(self, scores: Dict[IntentType, float], user_id: str) -> Dict[IntentType, float]:
        """基於歷史記錄調整意圖分數"""
        adjusted_scores = scores.copy()
        
        if user_id in self.intent_history:
            user_history = self.intent_history[user_id]
            
            # 獲取最近的意圖
            recent_intents = user_history[-3:]  # 最近3次意圖
            
            for intent_record in recent_intents:
                intent = intent_record['intent']
                
                # 如果用戶經常使用某種功能，稍微提高相關意圖分數
                if intent in adjusted_scores:
                    adjusted_scores[intent] *= 1.1
        
        return adjusted_scores
    
    def _select_best_intent(self, scores: Dict[IntentType, float]) -> Tuple[IntentType, float]:
        """選擇最佳意圖"""
        if not scores:
            return IntentType.UNKNOWN, 0.0
        
        # 找到最高分數的意圖
        best_intent = max(scores.items(), key=lambda x: x[1])
        
        # 如果最高分數太低，認為是未知意圖
        if best_intent[1] < 0.3:
            return IntentType.UNKNOWN, best_intent[1]
        
        return best_intent[0], best_intent[1]
    
    async def _extract_entities(self, text: str, intent: IntentType) -> List[Entity]:
        """提取實體信息"""
        entities = []
        
        for entity_type, patterns in self.entity_patterns.items():
            for pattern, value_type in patterns:
                matches = re.finditer(pattern, text)
                
                for match in matches:
                    entity = Entity(
                        type=entity_type,
                        value=match.group(1) if match.groups() else match.group(0),
                        confidence=0.9,  # 規則匹配的信心度固定為 0.9
                        start_pos=match.start(),
                        end_pos=match.end()
                    )
                    entities.append(entity)
        
        # 根據意圖類型提取特定實體
        if intent in [IntentType.VOTE_CREATE, IntentType.VOTE_PARTICIPATE]:
            # 提取選項相關實體
            option_patterns = [
                r"選項\s*([A-Za-z]|[0-9]+)",
                r"([A-Za-z])\s*[:：]\s*(.+)",
                r"([0-9]+)\s*[.。]\s*(.+)"
            ]
            
            for pattern in option_patterns:
                matches = re.finditer(pattern, text)
                for match in matches:
                    entities.append(Entity(
                        type="vote_option",
                        value=match.group(0),
                        confidence=0.8,
                        start_pos=match.start(),
                        end_pos=match.end()
                    ))
        
        return entities
    
    async def _record_intent_history(self, user_id: str, intent: IntentType, confidence: float):
        """記錄意圖歷史"""
        if user_id not in self.intent_history:
            self.intent_history[user_id] = []
        
        # 記錄意圖
        self.intent_history[user_id].append({
            'intent': intent,
            'confidence': confidence,
            'timestamp': asyncio.get_event_loop().time()
        })
        
        # 只保留最近20條記錄
        if len(self.intent_history[user_id]) > 20:
            self.intent_history[user_id] = self.intent_history[user_id][-20:]
    
    async def get_user_intent_patterns(self, user_id: str) -> Dict[str, Any]:
        """獲取用戶意圖模式分析"""
        if user_id not in self.intent_history:
            return {"total_interactions": 0, "patterns": {}}
        
        user_history = self.intent_history[user_id]
        
        # 統計各種意圖的頻率
        intent_counts = {}
        for record in user_history:
            intent = record['intent'].value
            intent_counts[intent] = intent_counts.get(intent, 0) + 1
        
        # 計算平均信心度
        total_confidence = sum(record['confidence'] for record in user_history)
        avg_confidence = total_confidence / len(user_history) if user_history else 0
        
        return {
            "total_interactions": len(user_history),
            "intent_distribution": intent_counts,
            "average_confidence": avg_confidence,
            "most_common_intent": max(intent_counts.items(), key=lambda x: x[1])[0] if intent_counts else None
        }
    
    async def improve_recognition(self, user_feedback: Dict[str, Any]):
        """基於用戶反饋改進識別準確性"""
        # 這裡可以實現機器學習模型的在線學習
        # 暫時記錄反饋用於後續分析
        
        actual_intent = user_feedback.get('actual_intent')
        predicted_intent = user_feedback.get('predicted_intent')
        text = user_feedback.get('text', '')
        
        if actual_intent and predicted_intent and actual_intent != predicted_intent:
            logger.info(f"📚 意圖識別改進機會: '{text}' -> 預測: {predicted_intent}, 實際: {actual_intent}")
            
            # 可以在這裡實現:
            # 1. 動態調整規則權重
            # 2. 添加新的模式
            # 3. 訓練機器學習模型
    
    async def export_training_data(self) -> Dict[str, Any]:
        """導出訓練數據用於模型改進"""
        training_data = {
            "intent_patterns": {intent.value: patterns for intent, patterns in self.intent_patterns.items()},
            "entity_patterns": self.entity_patterns,
            "user_interactions": {}
        }
        
        # 匿名化用戶歷史數據
        for user_id, history in self.intent_history.items():
            anonymized_id = f"user_{hash(user_id) % 10000}"
            training_data["user_interactions"][anonymized_id] = [
                {
                    "intent": record['intent'].value,
                    "confidence": record['confidence']
                }
                for record in history
            ]
        
        return training_data