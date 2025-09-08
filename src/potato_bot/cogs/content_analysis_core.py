# bot/cogs/content_analysis_core.py - 內容分析工具指令模組
"""
內容分析工具指令模組 v2.2.0
提供文本情感分析、內容安全檢查、連結分析等功能的Discord指令
"""

from datetime import datetime, timezone
from typing import Any, Dict

import discord
from discord import app_commands
from discord.ext import commands

from potato_bot.services.content_analyzer import (
    AnalysisType,
    ContentRiskLevel,
    SentimentType,
    content_analyzer,
)
from potato_bot.services.economy_manager import EconomyManager
from potato_bot.utils.embed_builder import EmbedBuilder
from potato_shared.cache_manager import cache_manager
from potato_shared.logger import logger
from potato_shared.prometheus_metrics import track_command_execution


class ContentAnalysisCog(commands.Cog):
    """內容分析工具功能"""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.economy_manager = EconomyManager()

        # 分析服務費用 (金幣)
        self.analysis_costs = {
            "sentiment": 3,
            "toxicity": 5,
            "link_safety": 4,
            "comprehensive": 10,
            "statistics": 8,
        }

        # 每日免費額度
        self.daily_free_quota = 15

        logger.info("📊 內容分析工具指令模組初始化完成")

    # ========== 統一內容分析界面 ==========

    @app_commands.command(name="content_analysis", description="打開內容分析工具管理界面")
    async def content_analysis_interface(self, interaction: discord.Interaction):
        """統一內容分析管理界面"""
        try:
            from potato_bot.views.content_analysis_views import (
                ContentAnalysisMainView,
            )

            view = ContentAnalysisMainView()

            embed = EmbedBuilder.create_info_embed("📊 內容分析工具", "選擇要使用的內容分析功能。")

            embed.add_field(
                name="🔧 可用功能",
                value="• **情感分析**: 檢測文本情感傾向和關鍵詞\n"
                "• **安全檢測**: 識別有害內容和風險評估\n"
                "• **連結檢測**: 分析URL安全性和信譽\n"
                "• **內容統計**: 伺服器內容分析報告",
                inline=False,
            )

            embed.add_field(
                name="🌐 支援語言",
                value="**主要**: 繁體中文、英語\n**其他**: 簡體中文、混合語言",
                inline=True,
            )

            embed.add_field(
                name="📏 限制",
                value="**文本長度**: 最大 1000 字符\n**處理時間**: 通常 1-3 秒",
                inline=True,
            )

            await interaction.response.send_message(embed=embed, view=view)

        except Exception as e:
            logger.error(f"❌ 內容分析界面錯誤: {e}")
            await interaction.response.send_message(
                "❌ 啟動內容分析工具時發生錯誤。", ephemeral=True
            )

    # ========== 情感分析 ==========

    @app_commands.command(name="analyze_sentiment", description="分析文本情感傾向")
    @app_commands.describe(text="要分析的文本內容")
    async def analyze_sentiment(self, interaction: discord.Interaction, text: str):
        """情感分析"""
        try:
            await interaction.response.defer()

            # 檢查文本長度
            if len(text) > 2000:
                await interaction.followup.send("❌ 文本過長，請限制在2000字符內。", ephemeral=True)
                return

            # 檢查使用權限
            can_use, cost_info = await self._check_usage_permission(
                interaction.user.id, interaction.guild.id, "sentiment"
            )

            if not can_use:
                embed = EmbedBuilder.build(
                    title="❌ 使用受限",
                    description=cost_info["message"],
                    color=0xFF0000,
                )
                await interaction.followup.send(embed=embed, ephemeral=True)
                return

            # 執行情感分析
            result = await content_analyzer.analyze_content(
                text, interaction.user.id, [AnalysisType.SENTIMENT]
            )

            if result.success and result.sentiment:
                # 扣除費用
                if cost_info["cost"] > 0:
                    await self.economy_manager.add_coins(
                        interaction.user.id,
                        interaction.guild.id,
                        -cost_info["cost"],
                    )

                # 記錄使用量
                await self._record_daily_usage(interaction.user.id)

                sentiment = result.sentiment

                # 設定顏色和表情符號
                color_map = {
                    SentimentType.POSITIVE: 0x00FF00,
                    SentimentType.NEGATIVE: 0xFF0000,
                    SentimentType.NEUTRAL: 0x808080,
                    SentimentType.MIXED: 0xFFAA00,
                }

                emoji_map = {
                    SentimentType.POSITIVE: "😊",
                    SentimentType.NEGATIVE: "😢",
                    SentimentType.NEUTRAL: "😐",
                    SentimentType.MIXED: "🤔",
                }

                embed = EmbedBuilder.build(
                    title=f"📊 情感分析結果 {emoji_map[sentiment.sentiment]}",
                    description=f"**情感傾向**: {sentiment.sentiment.value.title()}",
                    color=color_map[sentiment.sentiment],
                )

                # 分析的文本（截取顯示）
                display_text = text[:200] + ("..." if len(text) > 200 else "")
                embed.add_field(
                    name="📝 分析文本",
                    value=f"```{display_text}```",
                    inline=False,
                )

                # 詳細分數
                embed.add_field(
                    name="📈 情感分數",
                    value=f"正面: {sentiment.positive_score:.1%}\n"
                    f"負面: {sentiment.negative_score:.1%}\n"
                    f"中性: {sentiment.neutral_score:.1%}",
                    inline=True,
                )

                # 信心度和關鍵詞
                embed.add_field(
                    name="🎯 分析詳情",
                    value=f"信心度: {sentiment.confidence:.1%}\n"
                    f"處理時間: {result.processing_time:.2f}秒",
                    inline=True,
                )

                # 關鍵詞
                if sentiment.keywords:
                    keywords_text = ", ".join(sentiment.keywords[:5])
                    embed.add_field(name="🔑 關鍵詞", value=keywords_text, inline=False)

                # 費用信息
                if cost_info["cost"] > 0:
                    embed.add_field(
                        name="💰 費用",
                        value=f"消耗金幣: {cost_info['cost']}🪙",
                        inline=True,
                    )

                embed.set_footer(text=f"分析者: {interaction.user.display_name}")

            else:
                embed = EmbedBuilder.build(
                    title="❌ 情感分析失敗",
                    description=result.error_message or "分析過程中發生未知錯誤",
                    color=0xFF0000,
                )

            await interaction.followup.send(embed=embed)

            # 記錄指標
            track_command_execution("analyze_sentiment", interaction.guild.id)

        except Exception as e:
            logger.error(f"❌ 情感分析錯誤: {e}")
            await interaction.followup.send("❌ 情感分析時發生錯誤，請稍後再試。", ephemeral=True)

    # ========== 內容安全檢查 ==========

    @app_commands.command(name="check_content", description="檢查內容安全性和毒性")
    @app_commands.describe(text="要檢查的文本內容")
    async def check_content_safety(self, interaction: discord.Interaction, text: str):
        """內容安全檢查"""
        try:
            await interaction.response.defer()

            # 檢查文本長度
            if len(text) > 2000:
                await interaction.followup.send("❌ 文本過長，請限制在2000字符內。", ephemeral=True)
                return

            # 檢查使用權限
            can_use, cost_info = await self._check_usage_permission(
                interaction.user.id, interaction.guild.id, "toxicity"
            )

            if not can_use:
                embed = EmbedBuilder.build(
                    title="❌ 使用受限",
                    description=cost_info["message"],
                    color=0xFF0000,
                )
                await interaction.followup.send(embed=embed, ephemeral=True)
                return

            # 執行毒性分析
            result = await content_analyzer.analyze_content(
                text, interaction.user.id, [AnalysisType.TOXICITY]
            )

            if result.success and result.toxicity:
                # 扣除費用
                if cost_info["cost"] > 0:
                    await self.economy_manager.add_coins(
                        interaction.user.id,
                        interaction.guild.id,
                        -cost_info["cost"],
                    )

                # 記錄使用量
                await self._record_daily_usage(interaction.user.id)

                toxicity = result.toxicity

                # 設定顏色
                if toxicity.is_toxic:
                    color = 0xFF0000 if toxicity.toxicity_score > 0.7 else 0xFFAA00
                    status_emoji = "⚠️" if toxicity.toxicity_score > 0.7 else "⚡"
                    status_text = (
                        "檢測到有害內容" if toxicity.toxicity_score > 0.7 else "檢測到潛在問題"
                    )
                else:
                    color = 0x00FF00
                    status_emoji = "✅"
                    status_text = "內容安全"

                embed = EmbedBuilder.build(
                    title=f"🛡️ 內容安全檢查 {status_emoji}",
                    description=f"**檢查結果**: {status_text}",
                    color=color,
                )

                # 分析的文本（截取顯示）
                display_text = text[:200] + ("..." if len(text) > 200 else "")
                embed.add_field(
                    name="📝 檢查文本",
                    value=f"```{display_text}```",
                    inline=False,
                )

                # 毒性分數
                embed.add_field(
                    name="📊 安全評分",
                    value=f"毒性分數: {toxicity.toxicity_score:.1%}\n"
                    f"是否有害: {'是' if toxicity.is_toxic else '否'}\n"
                    f"風險等級: {result.risk_level.value.title()}",
                    inline=True,
                )

                # 類別分析
                if toxicity.categories:
                    category_text = []
                    for category, score in toxicity.categories.items():
                        if score > 0:
                            category_name = {
                                "harassment": "騷擾",
                                "hate_speech": "仇恨言論",
                                "violence": "暴力",
                                "inappropriate": "不當內容",
                                "spam": "垃圾信息",
                                "aggressive": "攻擊性",
                            }.get(category, category)
                            category_text.append(f"{category_name}: {score:.1%}")

                    if category_text:
                        embed.add_field(
                            name="⚠️ 問題類別",
                            value="\n".join(category_text),
                            inline=True,
                        )

                # 標記的詞彙
                if toxicity.flagged_phrases:
                    flagged_text = ", ".join(list(set(toxicity.flagged_phrases))[:5])
                    embed.add_field(
                        name="🚩 標記詞彙",
                        value=f"```{flagged_text}```",
                        inline=False,
                    )

                # 處理信息
                embed.add_field(
                    name="📈 處理信息",
                    value=f"處理時間: {result.processing_time:.2f}秒\n"
                    f"分析信心度: {result.confidence:.1%}"
                    + (f"\n消耗金幣: {cost_info['cost']}🪙" if cost_info["cost"] > 0 else ""),
                    inline=True,
                )

                embed.set_footer(text=f"檢查者: {interaction.user.display_name}")

            else:
                embed = EmbedBuilder.build(
                    title="❌ 內容檢查失敗",
                    description=result.error_message or "檢查過程中發生未知錯誤",
                    color=0xFF0000,
                )

            await interaction.followup.send(embed=embed)

            # 記錄指標
            track_command_execution("check_content", interaction.guild.id)

        except Exception as e:
            logger.error(f"❌ 內容檢查錯誤: {e}")
            await interaction.followup.send("❌ 內容檢查時發生錯誤，請稍後再試。", ephemeral=True)

    # ========== 連結安全分析 ==========

    @app_commands.command(name="analyze_links", description="分析文本中連結的安全性")
    @app_commands.describe(text="包含連結的文本")
    async def analyze_links(self, interaction: discord.Interaction, text: str):
        """連結安全分析"""
        try:
            await interaction.response.defer()

            # 檢查使用權限
            can_use, cost_info = await self._check_usage_permission(
                interaction.user.id, interaction.guild.id, "link_safety"
            )

            if not can_use:
                embed = EmbedBuilder.build(
                    title="❌ 使用受限",
                    description=cost_info["message"],
                    color=0xFF0000,
                )
                await interaction.followup.send(embed=embed, ephemeral=True)
                return

            # 執行連結分析
            result = await content_analyzer.analyze_content(
                text, interaction.user.id, [AnalysisType.LINK_SAFETY]
            )

            if result.success:
                # 扣除費用
                if cost_info["cost"] > 0:
                    await self.economy_manager.add_coins(
                        interaction.user.id,
                        interaction.guild.id,
                        -cost_info["cost"],
                    )

                # 記錄使用量
                await self._record_daily_usage(interaction.user.id)

                if not result.links:
                    embed = EmbedBuilder.build(
                        title="🔍 連結分析結果",
                        description="文本中沒有發現連結",
                        color=0x808080,
                    )
                else:
                    # 計算整體安全性
                    safe_links = sum(1 for link in result.links if link.is_safe)
                    total_links = len(result.links)
                    safety_rate = safe_links / total_links

                    if safety_rate == 1.0:
                        color = 0x00FF00
                        status = "所有連結安全 ✅"
                    elif safety_rate >= 0.8:
                        color = 0xFFAA00
                        status = "大部分連結安全 ⚠️"
                    else:
                        color = 0xFF0000
                        status = "發現風險連結 ⛔"

                    embed = EmbedBuilder.build(
                        title="🔍 連結安全分析",
                        description=f"**分析結果**: {status}",
                        color=color,
                    )

                    embed.add_field(
                        name="📊 總體統計",
                        value=f"總連結數: {total_links}\n"
                        f"安全連結: {safe_links}\n"
                        f"風險連結: {total_links - safe_links}\n"
                        f"安全率: {safety_rate:.1%}",
                        inline=True,
                    )

                    # 詳細分析每個連結
                    for i, link in enumerate(result.links[:3]):  # 只顯示前3個
                        risk_emoji = {
                            ContentRiskLevel.SAFE: "✅",
                            ContentRiskLevel.LOW: "⚠️",
                            ContentRiskLevel.MEDIUM: "🔶",
                            ContentRiskLevel.HIGH: "⚡",
                            ContentRiskLevel.CRITICAL: "⛔",
                        }

                        link_info = f"安全性: {link.risk_level.value.title()} {risk_emoji[link.risk_level]}\n"

                        if link.is_shortened:
                            link_info += "類型: 短網址\n"

                        if link.risk_factors:
                            link_info += f"風險因素: {', '.join(link.risk_factors[:2])}\n"

                        link_info += f"域名信譽: {link.domain_reputation:.1%}"

                        # 截取URL顯示
                        display_url = link.url if len(link.url) <= 50 else link.url[:47] + "..."

                        embed.add_field(
                            name=f"🔗 連結 {i+1}: {display_url}",
                            value=link_info,
                            inline=False,
                        )

                    if len(result.links) > 3:
                        embed.add_field(
                            name="ℹ️ 提示",
                            value=f"還有 {len(result.links) - 3} 個連結未顯示",
                            inline=False,
                        )

                # 處理信息
                embed.add_field(
                    name="📈 處理信息",
                    value=f"處理時間: {result.processing_time:.2f}秒"
                    + (f"\n消耗金幣: {cost_info['cost']}🪙" if cost_info["cost"] > 0 else ""),
                    inline=True,
                )

                embed.set_footer(text=f"分析者: {interaction.user.display_name}")

            else:
                embed = EmbedBuilder.build(
                    title="❌ 連結分析失敗",
                    description=result.error_message or "分析過程中發生未知錯誤",
                    color=0xFF0000,
                )

            await interaction.followup.send(embed=embed)

            # 記錄指標
            track_command_execution("analyze_links", interaction.guild.id)

        except Exception as e:
            logger.error(f"❌ 連結分析錯誤: {e}")
            await interaction.followup.send("❌ 連結分析時發生錯誤，請稍後再試。", ephemeral=True)

    # ========== 綜合分析 ==========

    @app_commands.command(name="comprehensive_analysis", description="對文本進行全面分析")
    @app_commands.describe(text="要分析的文本內容")
    async def comprehensive_analysis(self, interaction: discord.Interaction, text: str):
        """綜合分析"""
        try:
            await interaction.response.defer()

            # 檢查文本長度
            if len(text) > 1500:
                await interaction.followup.send("❌ 文本過長，請限制在1500字符內。", ephemeral=True)
                return

            # 檢查使用權限
            can_use, cost_info = await self._check_usage_permission(
                interaction.user.id, interaction.guild.id, "comprehensive"
            )

            if not can_use:
                embed = EmbedBuilder.build(
                    title="❌ 使用受限",
                    description=cost_info["message"],
                    color=0xFF0000,
                )
                await interaction.followup.send(embed=embed, ephemeral=True)
                return

            # 執行綜合分析
            result = await content_analyzer.analyze_content(
                text,
                interaction.user.id,
                [
                    AnalysisType.SENTIMENT,
                    AnalysisType.TOXICITY,
                    AnalysisType.LANGUAGE,
                    AnalysisType.KEYWORDS,
                    AnalysisType.LINK_SAFETY,
                ],
            )

            if result.success:
                # 扣除費用
                if cost_info["cost"] > 0:
                    await self.economy_manager.add_coins(
                        interaction.user.id,
                        interaction.guild.id,
                        -cost_info["cost"],
                    )

                # 記錄使用量
                await self._record_daily_usage(interaction.user.id)

                # 設定顏色基於風險等級
                color_map = {
                    ContentRiskLevel.SAFE: 0x00FF00,
                    ContentRiskLevel.LOW: 0x90EE90,
                    ContentRiskLevel.MEDIUM: 0xFFAA00,
                    ContentRiskLevel.HIGH: 0xFF6600,
                    ContentRiskLevel.CRITICAL: 0xFF0000,
                }

                embed = EmbedBuilder.build(
                    title="📊 綜合內容分析報告",
                    description=f"**整體風險等級**: {result.risk_level.value.title()}",
                    color=color_map[result.risk_level],
                )

                # 分析的文本（截取顯示）
                display_text = text[:300] + ("..." if len(text) > 300 else "")
                embed.add_field(
                    name="📝 分析文本",
                    value=f"```{display_text}```",
                    inline=False,
                )

                # 情感分析結果
                if result.sentiment:
                    sentiment_emoji = {
                        SentimentType.POSITIVE: "😊",
                        SentimentType.NEGATIVE: "😢",
                        SentimentType.NEUTRAL: "😐",
                        SentimentType.MIXED: "🤔",
                    }

                    embed.add_field(
                        name="💭 情感分析",
                        value=f"傾向: {result.sentiment.sentiment.value.title()} {sentiment_emoji[result.sentiment.sentiment]}\n"
                        f"正面: {result.sentiment.positive_score:.1%}\n"
                        f"負面: {result.sentiment.negative_score:.1%}",
                        inline=True,
                    )

                # 安全性檢查
                if result.toxicity:
                    safety_status = "⚠️ 有問題" if result.toxicity.is_toxic else "✅ 安全"
                    embed.add_field(
                        name="🛡️ 安全檢查",
                        value=f"狀態: {safety_status}\n"
                        f"毒性分數: {result.toxicity.toxicity_score:.1%}\n"
                        f"問題類別: {len(result.toxicity.categories)}",
                        inline=True,
                    )

                # 語言和關鍵詞
                language_name = {
                    "zh-TW": "繁體中文",
                    "zh-CN": "簡體中文",
                    "en": "英語",
                    "mixed": "混合語言",
                    "unknown": "未知",
                }.get(result.language, result.language)

                embed.add_field(
                    name="🌐 語言分析",
                    value=f"語言: {language_name}\n"
                    f"關鍵詞數: {len(result.keywords)}\n"
                    f"連結數: {len(result.links)}",
                    inline=True,
                )

                # 關鍵詞
                if result.keywords:
                    keywords_text = ", ".join(result.keywords[:8])
                    embed.add_field(name="🔑 主要關鍵詞", value=keywords_text, inline=False)

                # 連結安全性
                if result.links:
                    safe_links = sum(1 for link in result.links if link.is_safe)
                    embed.add_field(
                        name="🔗 連結安全",
                        value=f"總數: {len(result.links)}\n"
                        f"安全: {safe_links}\n"
                        f"風險: {len(result.links) - safe_links}",
                        inline=True,
                    )

                # 分析詳情
                embed.add_field(
                    name="📈 分析詳情",
                    value=f"處理時間: {result.processing_time:.2f}秒\n"
                    f"分析信心度: {result.confidence:.1%}"
                    + (f"\n消耗金幣: {cost_info['cost']}🪙" if cost_info["cost"] > 0 else ""),
                    inline=True,
                )

                embed.set_footer(text=f"分析者: {interaction.user.display_name}")

            else:
                embed = EmbedBuilder.build(
                    title="❌ 綜合分析失敗",
                    description=result.error_message or "分析過程中發生未知錯誤",
                    color=0xFF0000,
                )

            await interaction.followup.send(embed=embed)

            # 記錄指標
            track_command_execution("comprehensive_analysis", interaction.guild.id)

        except Exception as e:
            logger.error(f"❌ 綜合分析錯誤: {e}")
            await interaction.followup.send("❌ 綜合分析時發生錯誤，請稍後再試。", ephemeral=True)

    # ========== 統計功能 ==========

    @app_commands.command(name="content_stats", description="查看伺服器內容分析統計")
    @app_commands.describe(days="統計天數 (1-30)")
    async def content_statistics(self, interaction: discord.Interaction, days: int = 7):
        """內容統計"""
        try:
            await interaction.response.defer()

            # 限制天數範圍
            days = max(1, min(30, days))

            # 檢查使用權限
            can_use, cost_info = await self._check_usage_permission(
                interaction.user.id, interaction.guild.id, "statistics"
            )

            if not can_use:
                embed = EmbedBuilder.build(
                    title="❌ 使用受限",
                    description=cost_info["message"],
                    color=0xFF0000,
                )
                await interaction.followup.send(embed=embed, ephemeral=True)
                return

            # 獲取統計數據
            stats = await content_analyzer.get_content_statistics(interaction.guild.id, days)

            if stats:
                # 扣除費用
                if cost_info["cost"] > 0:
                    await self.economy_manager.add_coins(
                        interaction.user.id,
                        interaction.guild.id,
                        -cost_info["cost"],
                    )

                # 記錄使用量
                await self._record_daily_usage(interaction.user.id)

                embed = EmbedBuilder.build(
                    title=f"📊 {interaction.guild.name} 內容分析統計",
                    description=f"過去 {days} 天的內容分析數據",
                    color=0x4169E1,
                )

                # 基本統計
                embed.add_field(
                    name="📝 消息統計",
                    value=f"總消息數: {stats['total_messages']:,}\n"
                    f"平均每天: {stats['total_messages']//days:,}",
                    inline=True,
                )

                # 情感分佈
                sentiment_dist = stats["sentiment_distribution"]
                embed.add_field(
                    name="💭 情感分佈",
                    value=f"😊 正面: {sentiment_dist['positive']:.1f}%\n"
                    f"😢 負面: {sentiment_dist['negative']:.1f}%\n"
                    f"😐 中性: {sentiment_dist['neutral']:.1f}%\n"
                    f"🤔 混合: {sentiment_dist['mixed']:.1f}%",
                    inline=True,
                )

                # 安全統計
                toxicity_stats = stats["toxicity_stats"]
                embed.add_field(
                    name="🛡️ 安全統計",
                    value=f"有害消息: {toxicity_stats['toxic_messages']}\n"
                    f"有害率: {toxicity_stats['toxicity_rate']:.2f}%\n"
                    f"主要問題: {', '.join(toxicity_stats['most_common_issues'][:2])}",
                    inline=True,
                )

                # 語言分佈
                lang_dist = stats["language_distribution"]
                embed.add_field(
                    name="🌐 語言分佈",
                    value=f"繁體中文: {lang_dist['zh-TW']:.1f}%\n"
                    f"英語: {lang_dist['en']:.1f}%\n"
                    f"混合: {lang_dist['mixed']:.1f}%",
                    inline=True,
                )

                # 連結分析
                link_stats = stats["link_analysis"]
                embed.add_field(
                    name="🔗 連結分析",
                    value=f"總連結數: {link_stats['total_links']}\n"
                    f"安全連結: {link_stats['safe_links']}\n"
                    f"風險連結: {link_stats['risky_links']}\n"
                    f"封鎖連結: {link_stats['blocked_links']}",
                    inline=True,
                )

                # 熱門關鍵詞
                keywords = stats["top_keywords"]
                embed.add_field(
                    name="🔑 熱門關鍵詞",
                    value=", ".join(keywords[:10]),
                    inline=False,
                )

                # 費用信息
                if cost_info["cost"] > 0:
                    embed.add_field(
                        name="💰 費用",
                        value=f"消耗金幣: {cost_info['cost']}🪙",
                        inline=True,
                    )

                embed.set_footer(text=f"統計生成者: {interaction.user.display_name}")

            else:
                embed = EmbedBuilder.build(
                    title="❌ 獲取統計失敗",
                    description="無法獲取統計數據，請稍後再試",
                    color=0xFF0000,
                )

            await interaction.followup.send(embed=embed)

            # 記錄指標
            track_command_execution("content_stats", interaction.guild.id)

        except Exception as e:
            logger.error(f"❌ 內容統計錯誤: {e}")
            await interaction.followup.send(
                "❌ 獲取內容統計時發生錯誤，請稍後再試。", ephemeral=True
            )

    # ========== 使用統計 ==========

    @app_commands.command(name="analysis_usage", description="查看內容分析服務使用統計")
    async def analysis_usage_stats(self, interaction: discord.Interaction):
        """分析使用統計"""
        try:
            user_id = interaction.user.id

            # 獲取使用統計
            daily_usage = await self._get_daily_usage(user_id)

            # 獲取經濟狀態
            economy = await self.economy_manager.get_user_economy(user_id, interaction.guild.id)

            embed = EmbedBuilder.build(
                title="📊 內容分析使用統計",
                description=f"{interaction.user.display_name} 的內容分析服務使用情況",
                color=0x4169E1,
            )

            embed.set_thumbnail(url=interaction.user.display_avatar.url)

            # 今日使用情況
            remaining_free = max(0, self.daily_free_quota - daily_usage)
            embed.add_field(
                name="📅 今日使用",
                value=f"已使用: {daily_usage}/{self.daily_free_quota} (免費)\n"
                f"剩餘免費額度: {remaining_free}",
                inline=True,
            )

            # 經濟狀態
            embed.add_field(
                name="💰 經濟狀態",
                value=f"金幣餘額: {economy.get('coins', 0):,}🪙\n" f"可用於分析服務",
                inline=True,
            )

            # 費用說明
            cost_text = []
            for service, cost in self.analysis_costs.items():
                service_name = {
                    "sentiment": "💭 情感分析",
                    "toxicity": "🛡️ 安全檢查",
                    "link_safety": "🔗 連結分析",
                    "comprehensive": "📊 綜合分析",
                    "statistics": "📈 統計數據",
                }.get(service, service)

                cost_text.append(f"{service_name}: {cost}🪙")

            embed.add_field(name="💳 服務費用", value="\n".join(cost_text), inline=True)

            embed.add_field(
                name="💡 費用說明",
                value=f"• 每日前{self.daily_free_quota}次免費\n"
                "• 超出免費額度後按服務收費\n"
                "• 使用遊戲獲得的金幣支付",
                inline=False,
            )

            embed.add_field(
                name="🛠️ 可用功能",
                value="• `/analyze_sentiment` - 情感分析\n"
                "• `/check_content` - 安全檢查\n"
                "• `/analyze_links` - 連結分析\n"
                "• `/comprehensive_analysis` - 綜合分析\n"
                "• `/content_stats` - 統計數據",
                inline=False,
            )

            await interaction.response.send_message(embed=embed, ephemeral=True)

        except Exception as e:
            logger.error(f"❌ 分析使用統計錯誤: {e}")
            await interaction.response.send_message("❌ 獲取使用統計時發生錯誤。", ephemeral=True)

    # ========== 輔助方法 ==========

    async def _check_usage_permission(
        self, user_id: int, guild_id: int, service_type: str
    ) -> tuple[bool, Dict[str, Any]]:
        """檢查使用權限和費用"""
        try:
            # 檢查每日免費額度
            daily_usage = await self._get_daily_usage(user_id)

            if daily_usage < self.daily_free_quota:
                return True, {"cost": 0, "message": "免費額度內"}

            # 檢查金幣餘額
            economy = await self.economy_manager.get_user_economy(user_id, guild_id)
            cost = self.analysis_costs.get(service_type, 5)

            if economy.get("coins", 0) >= cost:
                return True, {"cost": cost, "message": f"需要消耗 {cost}🪙"}
            else:
                return False, {
                    "cost": cost,
                    "message": f"金幣不足！需要 {cost}🪙，您目前有 {economy.get('coins', 0)}🪙",
                }

        except Exception as e:
            logger.error(f"❌ 檢查使用權限失敗: {e}")
            return False, {"cost": 0, "message": "檢查權限時發生錯誤"}

    async def _get_daily_usage(self, user_id: int) -> int:
        """獲取每日使用次數"""
        try:
            cache_key = f"analysis_daily_usage:{user_id}"
            usage = await cache_manager.get(cache_key)
            return usage or 0

        except Exception as e:
            logger.error(f"❌ 獲取每日使用量失敗: {e}")
            return 0

    async def _record_daily_usage(self, user_id: int):
        """記錄每日使用次數"""
        try:
            cache_key = f"analysis_daily_usage:{user_id}"
            current_usage = await self._get_daily_usage(user_id)

            # 設置到明天零點過期
            from datetime import timedelta

            tomorrow = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
            tomorrow += timedelta(days=1)
            ttl = int((tomorrow - datetime.now(timezone.utc)).total_seconds())

            await cache_manager.set(cache_key, current_usage + 1, ttl)

        except Exception as e:
            logger.error(f"❌ 記錄每日使用量失敗: {e}")


async def setup(bot):
    """設置 Cog"""
    await bot.add_cog(ContentAnalysisCog(bot))
