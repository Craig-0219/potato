# bot/services/ai_manager.py - AI 智能回覆管理服務
"""
AI 智能回覆管理服務
提供智能回覆建議、內容分析、自動標籤建議等 AI 功能
"""

from datetime import datetime
from typing import Any, Dict, List

from potato_bot.db.tag_dao import TagDAO
from potato_bot.db.ticket_dao import TicketDAO
from potato_shared.logger import logger


class AIManager:
    """AI 智能回覆管理器"""

    def __init__(self, ticket_dao: TicketDAO = None, tag_dao: TagDAO = None):
        self.ticket_dao = ticket_dao or TicketDAO()
        self.tag_dao = tag_dao or TagDAO()

        # 智能回覆模板庫
        self.response_templates = self._load_response_templates()

        # 關鍵字分析規則
        self.keyword_rules = self._load_keyword_rules()

        # 情感分析規則
        self.sentiment_rules = self._load_sentiment_rules()

    # ========== AI 智能回覆建議 ==========

    async def suggest_reply(
        self, ticket_content: str, ticket_context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """分析票券內容並建議回覆"""
        try:
            # 1. 內容分析
            analysis = await self._analyze_content(ticket_content)

            # 2. 上下文分析
            context_analysis = await self._analyze_context(ticket_context)

            # 3. 生成回覆建議
            suggestions = await self._generate_reply_suggestions(analysis, context_analysis)

            # 4. 計算置信度
            confidence_score = self._calculate_confidence(analysis, context_analysis)

            return {
                "success": True,
                "suggestions": suggestions,
                "confidence": confidence_score,
                "analysis": analysis,
                "context": context_analysis,
            }

        except Exception as e:
            logger.error(f"AI 回覆建議錯誤: {e}")
            return {
                "success": False,
                "error": str(e),
                "suggestions": [],
                "confidence": 0.0,
            }

    async def _analyze_content(self, content: str) -> Dict[str, Any]:
        """分析票券內容"""
        analysis = {
            "type": "unknown",
            "priority": "medium",
            "sentiment": "neutral",
            "keywords": [],
            "intent": "inquiry",
            "urgency_level": 1,
            "complexity": "medium",
        }

        content_lower = content.lower()

        # 類型識別
        if any(word in content_lower for word in ["bug", "錯誤", "壞了", "不能", "無法"]):
            analysis["type"] = "bug_report"
            analysis["priority"] = "high"
        elif any(word in content_lower for word in ["建議", "feature", "功能", "新增"]):
            analysis["type"] = "feature_request"
            analysis["priority"] = "low"
        elif any(word in content_lower for word in ["問題", "如何", "怎麼", "教學"]):
            analysis["type"] = "question"
            analysis["priority"] = "medium"
        elif any(word in content_lower for word in ["申訴", "檢舉", "投訴", "不滿"]):
            analysis["type"] = "complaint"
            analysis["priority"] = "high"

        # 情感分析
        if any(word in content_lower for word in ["急", "緊急", "馬上", "立即", "火急"]):
            analysis["sentiment"] = "urgent"
            analysis["urgency_level"] = 3
            analysis["priority"] = "high"
        elif any(word in content_lower for word in ["謝謝", "感謝", "很好", "棒"]):
            analysis["sentiment"] = "positive"
        elif any(word in content_lower for word in ["生氣", "憤怒", "爛", "糟糕", "討厭"]):
            analysis["sentiment"] = "negative"
            analysis["urgency_level"] = 2

        # 複雜度評估
        word_count = len(content.split())
        if word_count > 100:
            analysis["complexity"] = "high"
        elif word_count < 20:
            analysis["complexity"] = "low"

        # 關鍵字提取
        analysis["keywords"] = self._extract_keywords(content)

        return analysis

    async def _analyze_context(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """分析票券上下文"""
        context_analysis = {
            "user_history": "new_user",
            "similar_tickets": [],
            "peak_time": False,
            "staff_availability": "normal",
        }

        try:
            user_id = context.get("user_id")
            guild_id = context.get("guild_id")

            if user_id and guild_id:
                # 查找用戶歷史票券
                user_tickets, _ = await self.ticket_dao.paginate_tickets(
                    guild_id=guild_id, user_id=str(user_id), page_size=5
                )

                if len(user_tickets) > 3:
                    context_analysis["user_history"] = "frequent_user"
                elif len(user_tickets) > 1:
                    context_analysis["user_history"] = "returning_user"

                # 查找相似票券
                context_analysis["similar_tickets"] = user_tickets[:3]

            # 時間分析
            current_hour = datetime.now().hour
            if 9 <= current_hour <= 17:
                context_analysis["peak_time"] = True

        except Exception as e:
            logger.error(f"上下文分析錯誤: {e}")

        return context_analysis

    async def _generate_reply_suggestions(
        self, analysis: Dict[str, Any], context: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """生成回覆建議"""
        suggestions = []

        ticket_type = analysis.get("type", "unknown")
        sentiment = analysis.get("sentiment", "neutral")
        urgency = analysis.get("urgency_level", 1)

        # 根據類型選擇模板
        templates = self.response_templates.get(
            ticket_type, self.response_templates.get("general", [])
        )

        for template in templates:
            # 根據情感調整語調
            adjusted_template = self._adjust_tone_by_sentiment(template, sentiment)

            # 根據緊急度調整回覆
            if urgency >= 2:
                adjusted_template = self._add_urgency_response(adjusted_template)

            # 個人化回覆
            personalized = self._personalize_response(adjusted_template, context)

            suggestions.append(
                {
                    "text": personalized,
                    "type": template.get("type", "standard"),
                    "confidence": template.get("base_confidence", 0.7),
                    "category": ticket_type,
                }
            )

        # 排序建議（按置信度）
        suggestions.sort(key=lambda x: x["confidence"], reverse=True)

        return suggestions[:3]  # 返回前3個建議

    def _calculate_confidence(self, analysis: Dict[str, Any], context: Dict[str, Any]) -> float:
        """計算整體置信度"""
        base_confidence = 0.5

        # 根據類型識別的確定性調整
        if analysis.get("type") != "unknown":
            base_confidence += 0.2

        # 根據情感分析調整
        if analysis.get("sentiment") != "neutral":
            base_confidence += 0.1

        # 根據用戶歷史調整
        user_history = context.get("user_history", "new_user")
        if user_history == "frequent_user":
            base_confidence += 0.1
        elif user_history == "returning_user":
            base_confidence += 0.05

        # 根據關鍵字數量調整
        keywords_count = len(analysis.get("keywords", []))
        if keywords_count > 3:
            base_confidence += 0.1

        return min(base_confidence, 1.0)

    # ========== 智能標籤建議 ==========

    async def suggest_tags(
        self, ticket_content: str, ticket_type: str = None
    ) -> List[Dict[str, Any]]:
        """建議適合的標籤"""
        try:
            suggestions = []
            ticket_content.lower()

            # 基於內容分析的標籤建議
            content_analysis = await self._analyze_content(ticket_content)

            # 根據票券類型建議標籤
            if content_analysis["type"] != "unknown":
                suggestions.append(
                    {
                        "tag_name": content_analysis["type"],
                        "confidence": 0.8,
                        "reason": "基於內容分析",
                    }
                )

            # 根據優先級建議標籤
            priority = content_analysis.get("priority", "medium")
            if priority == "high":
                suggestions.append(
                    {
                        "tag_name": "urgent",
                        "confidence": 0.7,
                        "reason": "內容顯示高優先級",
                    }
                )

            # 基於關鍵字的標籤建議
            keywords = content_analysis.get("keywords", [])
            for keyword in keywords:
                # 查找相關標籤
                related_tags = self._find_related_tags(keyword)
                for tag in related_tags:
                    suggestions.append(
                        {
                            "tag_name": tag,
                            "confidence": 0.6,
                            "reason": f"關鍵字匹配: {keyword}",
                        }
                    )

            # 去重並排序
            unique_suggestions = {}
            for suggestion in suggestions:
                tag_name = suggestion["tag_name"]
                if (
                    tag_name not in unique_suggestions
                    or suggestion["confidence"] > unique_suggestions[tag_name]["confidence"]
                ):
                    unique_suggestions[tag_name] = suggestion

            result = list(unique_suggestions.values())
            result.sort(key=lambda x: x["confidence"], reverse=True)

            return result[:5]  # 返回前5個建議

        except Exception as e:
            logger.error(f"智能標籤建議錯誤: {e}")
            return []

    # ========== 優先級智能評估 ==========

    async def assess_priority(
        self, ticket_content: str, user_context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """智能評估票券優先級"""
        try:
            analysis = await self._analyze_content(ticket_content)

            # 基礎優先級
            base_priority = analysis.get("priority", "medium")
            priority_score = {"low": 1, "medium": 2, "high": 3}[base_priority]

            # 調整因子
            adjustments = []

            # 緊急度調整
            urgency = analysis.get("urgency_level", 1)
            if urgency >= 3:
                priority_score += 1
                adjustments.append("緊急關鍵字")

            # 用戶類型調整
            user_history = user_context.get("user_history", "new_user")
            if user_history == "frequent_user":
                priority_score += 0.5
                adjustments.append("常客用戶")

            # 情感調整
            sentiment = analysis.get("sentiment", "neutral")
            if sentiment == "negative":
                priority_score += 0.5
                adjustments.append("負面情感")

            # 複雜度調整
            complexity = analysis.get("complexity", "medium")
            if complexity == "high":
                priority_score += 0.3
                adjustments.append("複雜內容")

            # 最終優先級
            if priority_score >= 3.5:
                final_priority = "high"
            elif priority_score >= 2.0:
                final_priority = "medium"
            else:
                final_priority = "low"

            return {
                "suggested_priority": final_priority,
                "confidence": min(priority_score / 4.0, 1.0),
                "score": priority_score,
                "adjustments": adjustments,
                "analysis": analysis,
            }

        except Exception as e:
            logger.error(f"優先級評估錯誤: {e}")
            return {
                "suggested_priority": "medium",
                "confidence": 0.5,
                "score": 2.0,
                "adjustments": [],
                "error": str(e),
            }

    # ========== 輔助方法 ==========

    def _extract_keywords(self, content: str) -> List[str]:
        """提取關鍵字"""
        # 簡單的關鍵字提取（基於規則）
        keywords = []
        content_lower = content.lower()

        # 技術相關關鍵字
        tech_keywords = [
            "api",
            "database",
            "server",
            "client",
            "bug",
            "error",
            "錯誤",
            "伺服器",
            "資料庫",
        ]
        for keyword in tech_keywords:
            if keyword in content_lower:
                keywords.append(keyword)

        # 功能相關關鍵字
        feature_keywords = [
            "login",
            "登入",
            "register",
            "註冊",
            "payment",
            "付款",
            "profile",
            "個人資料",
        ]
        for keyword in feature_keywords:
            if keyword in content_lower:
                keywords.append(keyword)

        return keywords

    def _find_related_tags(self, keyword: str) -> List[str]:
        """根據關鍵字查找相關標籤"""
        tag_mapping = {
            "bug": ["bug", "error", "issue"],
            "login": ["authentication", "account", "security"],
            "payment": ["billing", "finance", "transaction"],
            "api": ["technical", "integration", "development"],
            "server": ["infrastructure", "technical", "performance"],
        }

        for key, tags in tag_mapping.items():
            if key in keyword.lower():
                return tags

        return []

    def _adjust_tone_by_sentiment(self, template: Dict[str, Any], sentiment: str) -> Dict[str, Any]:
        """根據情感調整語調"""
        adjusted = template.copy()

        if sentiment == "negative":
            # 對負面情感使用更同理心的語調
            adjusted["text"] = adjusted["text"].replace("你好", "您好，很抱歉您遇到了困擾")
            adjusted["confidence"] = adjusted.get("base_confidence", 0.7) + 0.1
        elif sentiment == "urgent":
            # 對緊急情況表示重視
            adjusted["text"] = "我們已收到您的緊急請求。" + adjusted["text"]
            adjusted["confidence"] = adjusted.get("base_confidence", 0.7) + 0.05

        return adjusted

    def _add_urgency_response(self, template: Dict[str, Any]) -> Dict[str, Any]:
        """添加緊急回覆元素"""
        adjusted = template.copy()
        adjusted["text"] = adjusted["text"] + "\\n\\n我們會優先處理您的問題，感謝您的耐心。"
        return adjusted

    def _personalize_response(self, template: Dict[str, Any], context: Dict[str, Any]) -> str:
        """個人化回覆"""
        response = template["text"]

        user_history = context.get("user_history", "new_user")
        if user_history == "frequent_user":
            response = response.replace("您好", "您好，感謝您一直以來的支持")
        elif user_history == "returning_user":
            response = response.replace("您好", "您好，很高興再次為您服務")

        return response

    def _load_response_templates(self) -> Dict[str, List[Dict[str, Any]]]:
        """載入回覆模板"""
        return {
            "bug_report": [
                {
                    "text": "您好！感謝您回報這個問題。我們已經收到您的錯誤報告，技術團隊會立即進行調查。請問您能提供更多詳細資訊嗎？例如：\\n1. 發生錯誤的具體步驟\\n2. 錯誤訊息截圖\\n3. 您使用的裝置和瀏覽器版本\\n\\n這些資訊將幫助我們更快地解決問題。",
                    "type": "information_request",
                    "base_confidence": 0.8,
                },
                {
                    "text": "非常感謝您的回報！我們已將此問題記錄並轉交給技術團隊。預計會在24小時內提供初步回應。如果這是影響您正常使用的緊急問題，請告知我們，我們會優先處理。",
                    "type": "acknowledgment",
                    "base_confidence": 0.7,
                },
            ],
            "feature_request": [
                {
                    "text": "您好！感謝您的寶貴建議。我們很重視用戶的意見回饋，您提到的功能確實很有價值。我們會將您的建議轉達給產品團隊進行評估。\\n\\n請問您能詳細說明一下這個功能的使用場景嗎？這將幫助我們更好地理解需求。",
                    "type": "feature_inquiry",
                    "base_confidence": 0.75,
                },
                {
                    "text": "很棒的建議！我們會將您的功能請求加入產品規劃中。雖然無法承諾具體的實現時間，但我們會在後續版本中考慮加入此功能。請持續關注我們的更新公告。",
                    "type": "feature_acknowledgment",
                    "base_confidence": 0.7,
                },
            ],
            "question": [
                {
                    "text": "您好！我很樂意為您解答這個問題。根據您的描述，我建議您可以嘗試以下步驟：\\n\\n[請根據具體問題提供步驟]\\n\\n如果您需要更詳細的說明，或者遇到其他困難，請隨時告知我。",
                    "type": "solution_guidance",
                    "base_confidence": 0.7,
                },
                {
                    "text": "感謝您的提問！這是個很好的問題。請容我為您詳細說明相關資訊。如果您需要實際操作指導，我也可以安排專人為您提供協助。",
                    "type": "detailed_explanation",
                    "base_confidence": 0.65,
                },
            ],
            "complaint": [
                {
                    "text": "非常抱歉造成您的困擾！我們深刻理解您的感受，並會認真對待您提出的問題。請允許我們深入了解情況，以便為您提供最適當的解決方案。\\n\\n您能詳細說明發生了什麼事情嗎？我們會盡全力改善這個問題。",
                    "type": "apology_inquiry",
                    "base_confidence": 0.8,
                },
                {
                    "text": "我們對給您造成的不便深感抱歉。您的意見對我們非常重要，我們會立即著手調查並改善相關問題。我會親自跟進這個案例，確保得到妥善處理。",
                    "type": "personal_attention",
                    "base_confidence": 0.75,
                },
            ],
            "general": [
                {
                    "text": "您好！感謝您聯繫我們。我們已收到您的訊息，會盡快為您處理。如果您有任何緊急需求，請告知我們以便優先處理。",
                    "type": "general_acknowledgment",
                    "base_confidence": 0.6,
                }
            ],
        }

    def _load_keyword_rules(self) -> Dict[str, Any]:
        """載入關鍵字分析規則"""
        return {
            "urgency_keywords": [
                "急",
                "緊急",
                "馬上",
                "立即",
                "火急",
                "urgent",
                "asap",
                "emergency",
            ],
            "positive_keywords": [
                "謝謝",
                "感謝",
                "很好",
                "棒",
                "滿意",
                "thanks",
                "good",
                "great",
            ],
            "negative_keywords": [
                "生氣",
                "憤怒",
                "爛",
                "糟糕",
                "討厭",
                "angry",
                "bad",
                "terrible",
            ],
            "technical_keywords": [
                "api",
                "bug",
                "error",
                "server",
                "database",
                "錯誤",
                "伺服器",
                "資料庫",
            ],
            "feature_keywords": [
                "建議",
                "feature",
                "功能",
                "新增",
                "suggest",
                "add",
                "improve",
            ],
        }

    def _load_sentiment_rules(self) -> Dict[str, Any]:
        """載入情感分析規則"""
        return {
            "sentiment_patterns": {
                "positive": [
                    r"(很|非常|真的)?(好|棒|不錯|滿意|喜歡)",
                    r"thank(s|you)",
                    r"great|excellent|wonderful",
                ],
                "negative": [
                    r"(很|非常|真的)?(爛|差|糟|討厭|生氣)",
                    r"(不|沒有|無法)(滿意|高興|喜歡)",
                    r"terrible|awful|horrible|angry",
                ],
                "urgent": [
                    r"(很|非常|真的)?(急|緊急)",
                    r"(馬上|立即|立刻|趕快)",
                    r"urgent|asap|emergency|immediately",
                ],
            }
        }

    # ========== 統計和分析 ==========

    async def get_ai_statistics(self, guild_id: int, days: int = 30) -> Dict[str, Any]:
        """取得 AI 系統使用統計"""
        try:
            # 這裡暫時返回模擬數據，後續可以加入實際的使用記錄
            stats = {
                "total_suggestions": 125,
                "accepted_suggestions": 89,
                "acceptance_rate": 0.71,
                "avg_confidence": 0.73,
                "top_categories": [
                    {"category": "question", "count": 45},
                    {"category": "bug_report", "count": 32},
                    {"category": "feature_request", "count": 28},
                    {"category": "complaint", "count": 20},
                ],
                "confidence_distribution": {
                    "high": 42,  # > 0.8
                    "medium": 67,  # 0.5-0.8
                    "low": 16,  # < 0.5
                },
                "tag_suggestions": {
                    "total": 156,
                    "accepted": 112,
                    "rate": 0.72,
                },
            }

            return stats

        except Exception as e:
            logger.error(f"取得 AI 統計錯誤: {e}")
            return {}
