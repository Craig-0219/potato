# bot/services/content_analyzer.py - 內容分析服務
"""
內容分析服務 v2.2.0
提供文本情感分析、內容審核、連結分析、統計洞察等功能
"""

import asyncio
import hashlib
import re
import time
import urllib.parse
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

from shared.cache_manager import cache_manager
from shared.logger import logger


class SentimentType(Enum):
    """情感類型"""

    POSITIVE = "positive"
    NEGATIVE = "negative"
    NEUTRAL = "neutral"
    MIXED = "mixed"


class ContentRiskLevel(Enum):
    """內容風險等級"""

    SAFE = "safe"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class AnalysisType(Enum):
    """分析類型"""

    SENTIMENT = "sentiment"
    TOXICITY = "toxicity"
    SPAM = "spam"
    LANGUAGE = "language"
    KEYWORDS = "keywords"
    SUMMARY = "summary"
    LINK_SAFETY = "link_safety"


@dataclass
class SentimentResult:
    """情感分析結果"""

    sentiment: SentimentType
    confidence: float
    positive_score: float
    negative_score: float
    neutral_score: float
    keywords: List[str] = field(default_factory=list)


@dataclass
class ToxicityResult:
    """毒性分析結果"""

    is_toxic: bool
    toxicity_score: float
    categories: Dict[str, float] = field(default_factory=dict)  # 各類毒性評分
    flagged_phrases: List[str] = field(default_factory=list)


@dataclass
class LinkAnalysisResult:
    """連結分析結果"""

    url: str
    is_safe: bool
    risk_level: ContentRiskLevel
    risk_factors: List[str] = field(default_factory=list)
    domain_reputation: float = 0.0
    is_shortened: bool = False
    expanded_url: Optional[str] = None


@dataclass
class ContentAnalysisResult:
    """內容分析結果"""

    text: str
    analysis_type: AnalysisType
    timestamp: datetime
    processing_time: float
    success: bool
    sentiment: Optional[SentimentResult] = None
    toxicity: Optional[ToxicityResult] = None
    language: Optional[str] = None
    keywords: List[str] = field(default_factory=list)
    summary: Optional[str] = None
    links: List[LinkAnalysisResult] = field(default_factory=list)
    risk_level: ContentRiskLevel = ContentRiskLevel.SAFE
    confidence: float = 0.0
    error_message: Optional[str] = None


class ContentAnalyzer:
    """內容分析器"""

    def __init__(self):
        # 毒性關鍵詞庫（可擴展）
        self.toxic_keywords = {
            "harassment": ["騷擾", "霸凌", "威脅", "恐嚇", "侮辱", "羞辱", "歧視"],
            "hate_speech": ["仇恨", "種族", "歧視", "偏見", "排斥"],
            "violence": ["暴力", "傷害", "攻擊", "殺害", "毆打", "打架"],
            "inappropriate": ["色情", "淫穢", "猥褻", "不雅", "露骨"],
            "spam": ["廣告", "推銷", "買賣", "代購", "刷單", "點擊", "免費", "賺錢"],
        }

        # 情感詞庫
        self.sentiment_words = {
            "positive": [
                "好",
                "棒",
                "讚",
                "愛",
                "喜歡",
                "開心",
                "快樂",
                "滿意",
                "成功",
                "優秀",
                "美好",
                "精彩",
                "完美",
                "讚美",
                "感謝",
                "幸福",
                "溫暖",
                "友善",
                "積極",
            ],
            "negative": [
                "壞",
                "糟",
                "爛",
                "恨",
                "討厭",
                "生氣",
                "難過",
                "失望",
                "失敗",
                "糟糕",
                "可怕",
                "噁心",
                "痛苦",
                "沮喪",
                "憤怒",
                "煩躁",
                "焦慮",
                "擔心",
                "害怕",
            ],
        }

        # 危險域名清單
        self.dangerous_domains = [
            "malware-example.com",
            "phishing-site.net",
            "spam-domain.org",
        ]

        # 短網址服務清單
        self.url_shorteners = [
            "bit.ly",
            "tinyurl.com",
            "goo.gl",
            "t.co",
            "short.link",
            "ow.ly",
            "is.gd",
            "buff.ly",
            "tiny.cc",
        ]

        logger.info("📊 內容分析器初始化完成")

    # ========== 主要分析方法 ==========

    async def analyze_content(
        self, text: str, user_id: int = 0, analysis_types: List[AnalysisType] = None
    ) -> ContentAnalysisResult:
        """綜合內容分析"""
        start_time = time.time()

        try:
            if analysis_types is None:
                analysis_types = [
                    AnalysisType.SENTIMENT,
                    AnalysisType.TOXICITY,
                    AnalysisType.KEYWORDS,
                ]

            result = ContentAnalysisResult(
                text=text,
                analysis_type=AnalysisType.SENTIMENT,  # 主要類型
                timestamp=datetime.now(timezone.utc),
                processing_time=0,
                success=False,
            )

            # 執行各種分析
            tasks = []

            if AnalysisType.SENTIMENT in analysis_types:
                tasks.append(self._analyze_sentiment(text))

            if AnalysisType.TOXICITY in analysis_types:
                tasks.append(self._analyze_toxicity(text))

            if AnalysisType.LANGUAGE in analysis_types:
                tasks.append(self._detect_language(text))

            if AnalysisType.KEYWORDS in analysis_types:
                tasks.append(self._extract_keywords(text))

            if AnalysisType.LINK_SAFETY in analysis_types:
                tasks.append(self._analyze_links(text))

            # 並行執行分析任務
            results = await asyncio.gather(*tasks, return_exceptions=True)

            # 處理結果
            task_index = 0

            if AnalysisType.SENTIMENT in analysis_types:
                if not isinstance(results[task_index], Exception):
                    result.sentiment = results[task_index]
                task_index += 1

            if AnalysisType.TOXICITY in analysis_types:
                if not isinstance(results[task_index], Exception):
                    result.toxicity = results[task_index]
                task_index += 1

            if AnalysisType.LANGUAGE in analysis_types:
                if not isinstance(results[task_index], Exception):
                    result.language = results[task_index]
                task_index += 1

            if AnalysisType.KEYWORDS in analysis_types:
                if not isinstance(results[task_index], Exception):
                    result.keywords = results[task_index]
                task_index += 1

            if AnalysisType.LINK_SAFETY in analysis_types:
                if not isinstance(results[task_index], Exception):
                    result.links = results[task_index]
                task_index += 1

            # 計算整體風險等級
            result.risk_level = await self._calculate_risk_level(result)

            # 計算信心度
            result.confidence = await self._calculate_confidence(result)

            result.processing_time = time.time() - start_time
            result.success = True

            return result

        except Exception as e:
            logger.error(f"❌ 內容分析失敗: {e}")
            return ContentAnalysisResult(
                text=text,
                analysis_type=AnalysisType.SENTIMENT,
                timestamp=datetime.now(timezone.utc),
                processing_time=time.time() - start_time,
                success=False,
                error_message=str(e),
            )

    # ========== 情感分析 ==========

    async def _analyze_sentiment(self, text: str) -> SentimentResult:
        """情感分析"""
        try:
            # 檢查快取 - 使用 MD5 僅作為非安全的快取鍵生成
            cache_key = f"sentiment:{hashlib.md5(text.encode(), usedforsecurity=False).hexdigest()}"
            cached_result = await cache_manager.get(cache_key)
            if cached_result:
                return SentimentResult(**cached_result)

            # 簡單的規則基礎情感分析
            text_lower = text.lower()

            positive_count = 0
            negative_count = 0
            found_keywords = []

            # 計算正面詞彙
            for word in self.sentiment_words["positive"]:
                if word in text_lower:
                    positive_count += text_lower.count(word)
                    found_keywords.append(word)

            # 計算負面詞彙
            for word in self.sentiment_words["negative"]:
                if word in text_lower:
                    negative_count += text_lower.count(word)
                    found_keywords.append(word)

            # 特殊表情符號和標點符號分析
            positive_emojis = (
                text.count("😊") + text.count("😄") + text.count("❤️") + text.count("👍")
            )
            negative_emojis = (
                text.count("😢") + text.count("😡") + text.count("💔") + text.count("👎")
            )

            positive_count += positive_emojis
            negative_count += negative_emojis

            # 計算分數
            len(text.split())
            total_sentiment = positive_count + negative_count

            if total_sentiment == 0:
                sentiment = SentimentType.NEUTRAL
                positive_score = 0.5
                negative_score = 0.5
                confidence = 0.3
            else:
                positive_score = positive_count / total_sentiment
                negative_score = negative_count / total_sentiment

                if positive_score > negative_score:
                    sentiment = SentimentType.POSITIVE
                    confidence = min(0.9, positive_score * 0.8 + 0.1)
                elif negative_score > positive_score:
                    sentiment = SentimentType.NEGATIVE
                    confidence = min(0.9, negative_score * 0.8 + 0.1)
                else:
                    sentiment = SentimentType.MIXED
                    confidence = 0.5

            neutral_score = 1.0 - positive_score - negative_score

            result = SentimentResult(
                sentiment=sentiment,
                confidence=confidence,
                positive_score=positive_score,
                negative_score=negative_score,
                neutral_score=max(0, neutral_score),
                keywords=found_keywords[:10],  # 限制關鍵詞數量
            )

            # 快取結果
            await cache_manager.set(cache_key, result.__dict__, 1800)  # 30分鐘快取

            return result

        except Exception as e:
            logger.error(f"❌ 情感分析失敗: {e}")
            return SentimentResult(
                sentiment=SentimentType.NEUTRAL,
                confidence=0.0,
                positive_score=0.0,
                negative_score=0.0,
                neutral_score=1.0,
            )

    # ========== 毒性檢測 ==========

    async def _analyze_toxicity(self, text: str) -> ToxicityResult:
        """毒性分析"""
        try:
            text_lower = text.lower()

            toxicity_scores = {}
            flagged_phrases = []
            overall_toxicity = 0.0

            # 檢查各類毒性內容
            for category, keywords in self.toxic_keywords.items():
                category_score = 0.0
                category_count = 0

                for keyword in keywords:
                    if keyword in text_lower:
                        count = text_lower.count(keyword)
                        category_count += count
                        flagged_phrases.extend([keyword] * count)

                # 計算類別分數（基於出現頻率和文本長度）
                text_length = len(text.split())
                if text_length > 0 and category_count > 0:
                    category_score = min(1.0, (category_count / text_length) * 10)

                toxicity_scores[category] = category_score
                overall_toxicity = max(overall_toxicity, category_score)

            # 檢查重複字符（可能是spam）
            repeated_chars = re.findall(r"(.)\1{4,}", text)
            if repeated_chars:
                toxicity_scores["spam"] = min(1.0, len(repeated_chars) * 0.2)
                overall_toxicity = max(overall_toxicity, toxicity_scores["spam"])

            # 檢查過度使用大寫字母
            upper_ratio = sum(1 for c in text if c.isupper()) / max(1, len(text))
            if upper_ratio > 0.7 and len(text) > 10:
                toxicity_scores["aggressive"] = min(1.0, upper_ratio)
                overall_toxicity = max(overall_toxicity, toxicity_scores["aggressive"])

            is_toxic = overall_toxicity > 0.3

            return ToxicityResult(
                is_toxic=is_toxic,
                toxicity_score=overall_toxicity,
                categories=toxicity_scores,
                flagged_phrases=list(set(flagged_phrases)),
            )

        except Exception as e:
            logger.error(f"❌ 毒性分析失敗: {e}")
            return ToxicityResult(is_toxic=False, toxicity_score=0.0)

    # ========== 語言檢測 ==========

    async def _detect_language(self, text: str) -> str:
        """語言檢測"""
        try:
            # 簡單的語言檢測（基於字符特徵）
            chinese_chars = len([c for c in text if "\u4e00" <= c <= "\u9fff"])
            english_chars = len([c for c in text if c.isalpha() and ord(c) < 128])
            total_chars = len([c for c in text if c.isalnum()])

            if total_chars == 0:
                return "unknown"

            chinese_ratio = chinese_chars / total_chars
            english_ratio = english_chars / total_chars

            if chinese_ratio > 0.3:
                return "zh-TW"  # 繁體中文
            elif english_ratio > 0.7:
                return "en"  # 英語
            elif chinese_ratio > 0.1:
                return "zh-CN"  # 簡體中文
            else:
                return "mixed"  # 混合語言

        except Exception as e:
            logger.error(f"❌ 語言檢測失敗: {e}")
            return "unknown"

    # ========== 關鍵詞提取 ==========

    async def _extract_keywords(self, text: str) -> List[str]:
        """關鍵詞提取"""
        try:
            # 簡單的關鍵詞提取
            words = re.findall(r"\b\w+\b", text.lower())

            # 停用詞
            stop_words = {
                "的",
                "是",
                "在",
                "了",
                "和",
                "有",
                "我",
                "你",
                "他",
                "她",
                "它",
                "這",
                "那",
                "一",
                "二",
                "三",
                "會",
                "不",
                "也",
                "都",
                "就",
                "the",
                "a",
                "an",
                "and",
                "or",
                "but",
                "in",
                "on",
                "at",
                "to",
                "for",
                "of",
                "with",
                "by",
                "is",
                "are",
                "was",
                "were",
                "be",
            }

            # 過濾停用詞和短詞
            keywords = [word for word in words if len(word) > 2 and word not in stop_words]

            # 計算詞頻
            word_freq = {}
            for word in keywords:
                word_freq[word] = word_freq.get(word, 0) + 1

            # 按頻率排序並返回前10個
            sorted_keywords = sorted(word_freq.items(), key=lambda x: x[1], reverse=True)

            return [word for word, freq in sorted_keywords[:10]]

        except Exception as e:
            logger.error(f"❌ 關鍵詞提取失敗: {e}")
            return []

    # ========== 連結安全分析 ==========

    async def _analyze_links(self, text: str) -> List[LinkAnalysisResult]:
        """連結安全分析"""
        try:
            # 提取URL
            url_pattern = r'https?://[^\s<>"{}|\\^`\[\]]+'
            urls = re.findall(url_pattern, text)

            if not urls:
                return []

            results = []

            for url in urls:
                try:
                    result = await self._analyze_single_link(url)
                    results.append(result)
                except Exception as e:
                    logger.error(f"❌ 分析連結失敗 {url}: {e}")
                    results.append(
                        LinkAnalysisResult(
                            url=url,
                            is_safe=False,
                            risk_level=ContentRiskLevel.MEDIUM,
                            risk_factors=["分析失敗"],
                        )
                    )

            return results

        except Exception as e:
            logger.error(f"❌ 連結分析失敗: {e}")
            return []

    async def _analyze_single_link(self, url: str) -> LinkAnalysisResult:
        """分析單個連結"""
        try:
            parsed_url = urllib.parse.urlparse(url)
            domain = parsed_url.netloc.lower()

            risk_factors = []
            risk_level = ContentRiskLevel.SAFE
            is_safe = True
            domain_reputation = 1.0

            # 檢查是否為短網址
            is_shortened = any(shortener in domain for shortener in self.url_shorteners)
            if is_shortened:
                risk_factors.append("短網址")
                risk_level = ContentRiskLevel.LOW

            # 檢查危險域名
            if domain in self.dangerous_domains:
                risk_factors.append("已知惡意域名")
                risk_level = ContentRiskLevel.CRITICAL
                is_safe = False
                domain_reputation = 0.0

            # 檢查可疑特徵
            if re.search(r"[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}", domain):
                risk_factors.append("IP地址")
                risk_level = ContentRiskLevel.MEDIUM
                domain_reputation *= 0.7

            if len(domain) > 50:
                risk_factors.append("域名過長")
                risk_level = ContentRiskLevel.LOW
                domain_reputation *= 0.8

            # 檢查可疑子域名
            suspicious_subdomains = ["secure", "login", "verify", "update", "confirm"]
            for subdomain in suspicious_subdomains:
                if subdomain in domain:
                    risk_factors.append("可疑子域名")
                    risk_level = ContentRiskLevel.MEDIUM
                    domain_reputation *= 0.6
                    break

            # 嘗試展開短網址（模擬）
            expanded_url = None
            if is_shortened:
                expanded_url = await self._expand_url(url)

            return LinkAnalysisResult(
                url=url,
                is_safe=is_safe,
                risk_level=risk_level,
                risk_factors=risk_factors,
                domain_reputation=domain_reputation,
                is_shortened=is_shortened,
                expanded_url=expanded_url,
            )

        except Exception as e:
            logger.error(f"❌ 分析連結失敗: {e}")
            return LinkAnalysisResult(
                url=url,
                is_safe=False,
                risk_level=ContentRiskLevel.MEDIUM,
                risk_factors=["分析錯誤"],
            )

    async def _expand_url(self, url: str) -> Optional[str]:
        """展開短網址"""
        try:
            # 模擬短網址展開（實際實現需要HTTP請求）
            # 這裡返回模擬結果
            return f"https://expanded-{url.split('//')[1]}.example.com"

        except Exception as e:
            logger.error(f"❌ 展開URL失敗: {e}")
            return None

    # ========== 風險評估 ==========

    async def _calculate_risk_level(self, result: ContentAnalysisResult) -> ContentRiskLevel:
        """計算整體風險等級"""
        try:
            risk_score = 0.0

            # 毒性分析風險
            if result.toxicity:
                risk_score += result.toxicity.toxicity_score * 0.4

            # 情感分析風險（極端負面情感可能有風險）
            if result.sentiment and result.sentiment.sentiment == SentimentType.NEGATIVE:
                risk_score += result.sentiment.negative_score * 0.2

            # 連結風險
            if result.links:
                link_risk = max(
                    [self._risk_level_to_score(link.risk_level) for link in result.links]
                )
                risk_score += link_risk * 0.3

            # 其他因素
            if result.keywords:
                # 檢查關鍵詞中是否有風險詞彙
                risk_keywords = ["病毒", "駭客", "詐騙", "釣魚", "惡意"]
                for keyword in result.keywords:
                    if keyword in risk_keywords:
                        risk_score += 0.1

            # 轉換為風險等級
            if risk_score < 0.2:
                return ContentRiskLevel.SAFE
            elif risk_score < 0.4:
                return ContentRiskLevel.LOW
            elif risk_score < 0.6:
                return ContentRiskLevel.MEDIUM
            elif risk_score < 0.8:
                return ContentRiskLevel.HIGH
            else:
                return ContentRiskLevel.CRITICAL

        except Exception as e:
            logger.error(f"❌ 計算風險等級失敗: {e}")
            return ContentRiskLevel.SAFE

    def _risk_level_to_score(self, risk_level: ContentRiskLevel) -> float:
        """風險等級轉分數"""
        mapping = {
            ContentRiskLevel.SAFE: 0.0,
            ContentRiskLevel.LOW: 0.2,
            ContentRiskLevel.MEDIUM: 0.5,
            ContentRiskLevel.HIGH: 0.7,
            ContentRiskLevel.CRITICAL: 1.0,
        }
        return mapping.get(risk_level, 0.0)

    async def _calculate_confidence(self, result: ContentAnalysisResult) -> float:
        """計算分析信心度"""
        try:
            confidence_scores = []

            if result.sentiment:
                confidence_scores.append(result.sentiment.confidence)

            if result.toxicity:
                # 毒性分析的信心度基於檢測到的關鍵詞數量
                keyword_confidence = min(1.0, len(result.toxicity.flagged_phrases) * 0.2 + 0.3)
                confidence_scores.append(keyword_confidence)

            if result.language:
                # 語言檢測信心度（簡化）
                confidence_scores.append(0.8 if result.language != "unknown" else 0.3)

            if confidence_scores:
                return sum(confidence_scores) / len(confidence_scores)
            else:
                return 0.5

        except Exception as e:
            logger.error(f"❌ 計算信心度失敗: {e}")
            return 0.0

    # ========== 統計分析 ==========

    async def get_content_statistics(self, guild_id: int, days: int = 7) -> Dict[str, Any]:
        """獲取內容統計"""
        try:
            cache_key = f"content_stats:{guild_id}:{days}"
            cached_stats = await cache_manager.get(cache_key)
            if cached_stats:
                return cached_stats

            # 模擬統計數據（實際實現需要數據庫查詢）
            stats = {
                "total_messages": 1250,
                "sentiment_distribution": {
                    "positive": 45.2,
                    "negative": 12.8,
                    "neutral": 35.5,
                    "mixed": 6.5,
                },
                "toxicity_stats": {
                    "toxic_messages": 23,
                    "toxicity_rate": 1.84,
                    "most_common_issues": ["spam", "harassment", "inappropriate"],
                },
                "language_distribution": {"zh-TW": 67.3, "en": 28.7, "mixed": 4.0},
                "link_analysis": {
                    "total_links": 156,
                    "safe_links": 142,
                    "risky_links": 14,
                    "blocked_links": 3,
                },
                "top_keywords": [
                    "遊戲",
                    "音樂",
                    "電影",
                    "學習",
                    "工作",
                    "朋友",
                    "討論",
                    "分享",
                    "推薦",
                    "問題",
                ],
            }

            # 快取30分鐘
            await cache_manager.set(cache_key, stats, 1800)

            return stats

        except Exception as e:
            logger.error(f"❌ 獲取內容統計失敗: {e}")
            return {}


# 全域實例
content_analyzer = ContentAnalyzer()
