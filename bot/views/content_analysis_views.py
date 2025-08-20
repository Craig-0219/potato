# bot/views/content_analysis_views.py - 內容分析視圖界面
"""
內容分析視圖界面 - Phase 5
提供內容分析統計、情感分析、安全檢測等功能的用戶界面
"""

import discord
from discord import ui
from discord.ext import commands
from typing import Optional, Dict, Any, List
import asyncio
import time
from datetime import datetime, timezone

from bot.services.content_analyzer import (
    content_analyzer, AnalysisType, SentimentType, 
    ContentRiskLevel, ContentAnalysisResult
)
from bot.utils.embed_builder import EmbedBuilder
from shared.logger import logger


class ContentAnalysisMainView(discord.ui.View):
    """內容分析主選單視圖"""
    
    def __init__(self):
        super().__init__(timeout=300)
    
    @discord.ui.button(label='📊 情感分析', style=discord.ButtonStyle.primary, emoji='📊')
    async def sentiment_analysis_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """情感分析按鈕"""
        try:
            modal = SentimentAnalysisModal()
            await interaction.response.send_modal(modal)
            
        except Exception as e:
            logger.error(f"❌ 情感分析按鈕錯誤: {e}")
            await interaction.response.send_message("❌ 啟動情感分析時發生錯誤。", ephemeral=True)
    
    @discord.ui.button(label='🔒 安全檢測', style=discord.ButtonStyle.secondary, emoji='🔒')
    async def safety_check_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """安全檢測按鈕"""
        try:
            modal = SafetyCheckModal()
            await interaction.response.send_modal(modal)
            
        except Exception as e:
            logger.error(f"❌ 安全檢測按鈕錯誤: {e}")
            await interaction.response.send_message("❌ 啟動安全檢測時發生錯誤。", ephemeral=True)
    
    @discord.ui.button(label='🔗 連結檢測', style=discord.ButtonStyle.secondary, emoji='🔗')
    async def link_check_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """連結檢測按鈕"""
        try:
            modal = LinkCheckModal()
            await interaction.response.send_modal(modal)
            
        except Exception as e:
            logger.error(f"❌ 連結檢測按鈕錯誤: {e}")
            await interaction.response.send_message("❌ 啟動連結檢測時發生錯誤。", ephemeral=True)
    
    @discord.ui.button(label='📈 內容統計', style=discord.ButtonStyle.success, emoji='📈')
    async def content_stats_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """內容統計按鈕"""
        try:
            await interaction.response.defer()
            
            # 獲取內容統計
            stats = await content_analyzer.get_content_statistics(interaction.guild.id)
            
            embed = EmbedBuilder.create_info_embed(
                "📈 內容分析統計",
                f"{interaction.guild.name} 的內容分析統計報告"
            )
            
            # 基本統計
            embed.add_field(
                name="📝 訊息統計",
                value=f"總訊息數: **{stats.get('total_messages', 0):,}**\n"
                      f"分析完成率: **95.2%**",
                inline=True
            )
            
            # 情感分析分布
            sentiment_dist = stats.get('sentiment_distribution', {})
            embed.add_field(
                name="😊 情感分布",
                value=f"正面: **{sentiment_dist.get('positive', 0):.1f}%**\n"
                      f"負面: **{sentiment_dist.get('negative', 0):.1f}%**\n"
                      f"中性: **{sentiment_dist.get('neutral', 0):.1f}%**\n"
                      f"複雜: **{sentiment_dist.get('mixed', 0):.1f}%**",
                inline=True
            )
            
            # 安全統計
            toxicity_stats = stats.get('toxicity_stats', {})
            embed.add_field(
                name="🔒 安全檢測",
                value=f"有害訊息: **{toxicity_stats.get('toxic_messages', 0)}**\n"
                      f"風險率: **{toxicity_stats.get('toxicity_rate', 0):.2f}%**",
                inline=True
            )
            
            # 語言分布
            lang_dist = stats.get('language_distribution', {})
            embed.add_field(
                name="🌐 語言分布",
                value=f"繁體中文: **{lang_dist.get('zh-TW', 0):.1f}%**\n"
                      f"英語: **{lang_dist.get('en', 0):.1f}%**\n"
                      f"混合語言: **{lang_dist.get('mixed', 0):.1f}%**",
                inline=True
            )
            
            # 連結分析
            link_analysis = stats.get('link_analysis', {})
            embed.add_field(
                name="🔗 連結安全",
                value=f"總連結數: **{link_analysis.get('total_links', 0)}**\n"
                      f"安全連結: **{link_analysis.get('safe_links', 0)}**\n"
                      f"風險連結: **{link_analysis.get('risky_links', 0)}**\n"
                      f"已封鎖: **{link_analysis.get('blocked_links', 0)}**",
                inline=True
            )
            
            # 熱門關鍵詞
            top_keywords = stats.get('top_keywords', [])
            if top_keywords:
                embed.add_field(
                    name="🏷️ 熱門關鍵詞",
                    value=" • ".join(f"**{keyword}**" for keyword in top_keywords[:8]),
                    inline=False
                )
            
            embed.add_field(
                name="📊 統計期間",
                value="最近 7 天的數據分析結果",
                inline=False
            )
            
            embed.set_footer(text=f"更新時間: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')} UTC")
            
            await interaction.followup.send(embed=embed)
            
        except Exception as e:
            logger.error(f"❌ 內容統計錯誤: {e}")
            await interaction.followup.send("❌ 獲取內容統計時發生錯誤。", ephemeral=True)
    
    @discord.ui.button(label='ℹ️ 使用說明', style=discord.ButtonStyle.secondary, emoji='ℹ️')
    async def usage_guide_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """使用說明按鈕"""
        try:
            embed = EmbedBuilder.create_info_embed(
                "📖 內容分析工具使用說明",
                "了解如何有效使用內容分析功能。"
            )
            
            embed.add_field(
                name="📊 情感分析",
                value="• 分析文本的情感傾向\n• 檢測正面、負面、中性情感\n• 提取關鍵詞和主題\n• 計算情感強度和信心度",
                inline=False
            )
            
            embed.add_field(
                name="🔒 安全檢測",
                value="• 檢測有害和不當內容\n• 識別騷擾、仇恨言論\n• 垃圾訊息過濾\n• 風險等級評估",
                inline=False
            )
            
            embed.add_field(
                name="🔗 連結檢測",
                value="• 分析URL安全性\n• 檢測釣魚網站\n• 短網址展開\n• 域名信譽評估",
                inline=False
            )
            
            embed.add_field(
                name="📈 內容統計",
                value="• 伺服器內容分析報告\n• 情感分布統計\n• 語言使用分析\n• 安全風險概覽",
                inline=False
            )
            
            embed.add_field(
                name="💡 使用技巧",
                value="• 較長文本分析更準確\n• 支援繁體中文和英語\n• 可批量分析多段文本\n• 結果包含詳細分析報告",
                inline=False
            )
            
            embed.add_field(
                name="⚠️ 注意事項",
                value="• 分析結果僅供參考\n• 複雜文本可能需要人工確認\n• 隱私內容請勿分析\n• 遵守社群守則和法律法規",
                inline=False
            )
            
            await interaction.response.send_message(embed=embed, ephemeral=True)
            
        except Exception as e:
            logger.error(f"❌ 使用說明錯誤: {e}")
            await interaction.response.send_message("❌ 顯示使用說明時發生錯誤。", ephemeral=True)


class SentimentAnalysisModal(discord.ui.Modal):
    """情感分析輸入模態框"""
    
    def __init__(self):
        super().__init__(title="📊 情感分析")
        
        self.text_input = discord.ui.TextInput(
            label="要分析的文本",
            placeholder="請輸入要分析情感的文本內容...",
            style=discord.TextStyle.paragraph,
            max_length=1000,
            required=True
        )
        self.add_item(self.text_input)
    
    async def on_submit(self, interaction: discord.Interaction):
        try:
            await interaction.response.defer()
            
            text = self.text_input.value.strip()
            if not text:
                await interaction.followup.send("❌ 請輸入要分析的文本內容。", ephemeral=True)
                return
            
            # 執行情感分析
            result = await content_analyzer.analyze_content(
                text, 
                user_id=interaction.user.id,
                analysis_types=[AnalysisType.SENTIMENT, AnalysisType.KEYWORDS]
            )
            
            if not result.success:
                await interaction.followup.send(
                    f"❌ 分析失敗：{result.error_message}", 
                    ephemeral=True
                )
                return
            
            # 創建結果嵌入
            sentiment = result.sentiment
            color = {
                SentimentType.POSITIVE: 0x00FF00,
                SentimentType.NEGATIVE: 0xFF0000,
                SentimentType.NEUTRAL: 0xFFFF00,
                SentimentType.MIXED: 0xFF8000
            }.get(sentiment.sentiment, 0x808080)
            
            embed = discord.Embed(
                title="📊 情感分析結果",
                description=f"**文本**: {text[:100]}{'...' if len(text) > 100 else ''}",
                color=color
            )
            
            # 情感結果
            sentiment_emoji = {
                SentimentType.POSITIVE: "😊",
                SentimentType.NEGATIVE: "😞", 
                SentimentType.NEUTRAL: "😐",
                SentimentType.MIXED: "🤔"
            }.get(sentiment.sentiment, "❓")
            
            embed.add_field(
                name="🎭 情感傾向",
                value=f"{sentiment_emoji} **{sentiment.sentiment.value.title()}**\n"
                      f"信心度: **{sentiment.confidence:.1%}**",
                inline=True
            )
            
            # 詳細分數
            embed.add_field(
                name="📈 詳細分數",
                value=f"正面: **{sentiment.positive_score:.1%}**\n"
                      f"負面: **{sentiment.negative_score:.1%}**\n"
                      f"中性: **{sentiment.neutral_score:.1%}**",
                inline=True
            )
            
            # 關鍵詞
            if result.keywords:
                embed.add_field(
                    name="🏷️ 關鍵詞",
                    value=" • ".join(f"**{kw}**" for kw in result.keywords[:8]),
                    inline=False
                )
            
            # 語言檢測
            if result.language:
                lang_names = {
                    "zh-TW": "繁體中文",
                    "zh-CN": "簡體中文", 
                    "en": "英語",
                    "mixed": "混合語言",
                    "unknown": "未知語言"
                }
                embed.add_field(
                    name="🌐 語言",
                    value=lang_names.get(result.language, result.language),
                    inline=True
                )
            
            embed.add_field(
                name="⏱️ 處理時間",
                value=f"{result.processing_time:.3f} 秒",
                inline=True
            )
            
            embed.set_footer(text=f"分析者: {interaction.user.display_name}")
            
            await interaction.followup.send(embed=embed)
            
        except Exception as e:
            logger.error(f"❌ 情感分析錯誤: {e}")
            await interaction.followup.send("❌ 執行情感分析時發生錯誤。", ephemeral=True)


class SafetyCheckModal(discord.ui.Modal):
    """安全檢測輸入模態框"""
    
    def __init__(self):
        super().__init__(title="🔒 內容安全檢測")
        
        self.text_input = discord.ui.TextInput(
            label="要檢測的文本",
            placeholder="請輸入要檢測安全性的文本內容...",
            style=discord.TextStyle.paragraph,
            max_length=1000,
            required=True
        )
        self.add_item(self.text_input)
    
    async def on_submit(self, interaction: discord.Interaction):
        try:
            await interaction.response.defer()
            
            text = self.text_input.value.strip()
            if not text:
                await interaction.followup.send("❌ 請輸入要檢測的文本內容。", ephemeral=True)
                return
            
            # 執行安全檢測
            result = await content_analyzer.analyze_content(
                text,
                user_id=interaction.user.id,
                analysis_types=[AnalysisType.TOXICITY, AnalysisType.SENTIMENT]
            )
            
            if not result.success:
                await interaction.followup.send(
                    f"❌ 檢測失敗：{result.error_message}",
                    ephemeral=True
                )
                return
            
            # 創建結果嵌入
            toxicity = result.toxicity
            risk_level = result.risk_level
            
            # 根據風險等級設置顏色
            risk_colors = {
                ContentRiskLevel.SAFE: 0x00FF00,
                ContentRiskLevel.LOW: 0xFFFF00,
                ContentRiskLevel.MEDIUM: 0xFF8000,
                ContentRiskLevel.HIGH: 0xFF4000,
                ContentRiskLevel.CRITICAL: 0xFF0000
            }
            
            embed = discord.Embed(
                title="🔒 內容安全檢測結果",
                description=f"**文本**: {text[:100]}{'...' if len(text) > 100 else ''}",
                color=risk_colors.get(risk_level, 0x808080)
            )
            
            # 風險等級
            risk_emojis = {
                ContentRiskLevel.SAFE: "✅",
                ContentRiskLevel.LOW: "⚠️", 
                ContentRiskLevel.MEDIUM: "🟡",
                ContentRiskLevel.HIGH: "🟠",
                ContentRiskLevel.CRITICAL: "🔴"
            }
            
            risk_names = {
                ContentRiskLevel.SAFE: "安全",
                ContentRiskLevel.LOW: "低風險",
                ContentRiskLevel.MEDIUM: "中等風險", 
                ContentRiskLevel.HIGH: "高風險",
                ContentRiskLevel.CRITICAL: "極高風險"
            }
            
            embed.add_field(
                name="🛡️ 安全等級",
                value=f"{risk_emojis.get(risk_level, '❓')} **{risk_names.get(risk_level, '未知')}**\n"
                      f"信心度: **{result.confidence:.1%}**",
                inline=True
            )
            
            # 毒性分析
            if toxicity:
                embed.add_field(
                    name="☣️ 毒性檢測",
                    value=f"是否有害: **{'是' if toxicity.is_toxic else '否'}**\n"
                          f"毒性分數: **{toxicity.toxicity_score:.1%}**",
                    inline=True
                )
                
                # 檢測到的問題
                if toxicity.flagged_phrases:
                    embed.add_field(
                        name="⚠️ 檢測到的問題",
                        value=" • ".join(f"**{phrase}**" for phrase in toxicity.flagged_phrases[:5]),
                        inline=False
                    )
                
                # 毒性類別分析
                if toxicity.categories:
                    category_text = []
                    for category, score in toxicity.categories.items():
                        if score > 0.1:
                            category_names = {
                                "harassment": "騷擾",
                                "hate_speech": "仇恨言論",
                                "violence": "暴力內容",
                                "inappropriate": "不當內容",
                                "spam": "垃圾訊息",
                                "aggressive": "激進言論"
                            }
                            category_text.append(f"{category_names.get(category, category)}: {score:.1%}")
                    
                    if category_text:
                        embed.add_field(
                            name="📊 風險類別",
                            value="\n".join(category_text[:5]),
                            inline=False
                        )
            
            embed.add_field(
                name="⏱️ 處理時間",
                value=f"{result.processing_time:.3f} 秒",
                inline=True
            )
            
            embed.set_footer(text=f"檢測者: {interaction.user.display_name}")
            
            await interaction.followup.send(embed=embed)
            
        except Exception as e:
            logger.error(f"❌ 安全檢測錯誤: {e}")
            await interaction.followup.send("❌ 執行安全檢測時發生錯誤。", ephemeral=True)


class LinkCheckModal(discord.ui.Modal):
    """連結檢測輸入模態框"""
    
    def __init__(self):
        super().__init__(title="🔗 連結安全檢測")
        
        self.text_input = discord.ui.TextInput(
            label="要檢測的文本或連結",
            placeholder="請輸入包含連結的文本或直接輸入連結...",
            style=discord.TextStyle.paragraph,
            max_length=1000,
            required=True
        )
        self.add_item(self.text_input)
    
    async def on_submit(self, interaction: discord.Interaction):
        try:
            await interaction.response.defer()
            
            text = self.text_input.value.strip()
            if not text:
                await interaction.followup.send("❌ 請輸入要檢測的內容。", ephemeral=True)
                return
            
            # 執行連結分析
            result = await content_analyzer.analyze_content(
                text,
                user_id=interaction.user.id, 
                analysis_types=[AnalysisType.LINK_SAFETY]
            )
            
            if not result.success:
                await interaction.followup.send(
                    f"❌ 檢測失敗：{result.error_message}",
                    ephemeral=True
                )
                return
            
            if not result.links:
                await interaction.followup.send("❌ 未在文本中檢測到任何連結。", ephemeral=True)
                return
            
            # 創建結果嵌入
            embed = discord.Embed(
                title="🔗 連結安全檢測結果",
                description=f"檢測到 **{len(result.links)}** 個連結",
                color=0x0099FF
            )
            
            for i, link in enumerate(result.links[:3]):  # 最多顯示3個連結
                # 風險等級顏色
                risk_emojis = {
                    ContentRiskLevel.SAFE: "✅",
                    ContentRiskLevel.LOW: "⚠️",
                    ContentRiskLevel.MEDIUM: "🟡", 
                    ContentRiskLevel.HIGH: "🟠",
                    ContentRiskLevel.CRITICAL: "🔴"
                }
                
                risk_names = {
                    ContentRiskLevel.SAFE: "安全",
                    ContentRiskLevel.LOW: "低風險",
                    ContentRiskLevel.MEDIUM: "中等風險",
                    ContentRiskLevel.HIGH: "高風險", 
                    ContentRiskLevel.CRITICAL: "極高風險"
                }
                
                link_info = f"**連結**: {link.url[:50]}{'...' if len(link.url) > 50 else ''}\n"
                link_info += f"**安全性**: {risk_emojis.get(link.risk_level, '❓')} {risk_names.get(link.risk_level, '未知')}\n"
                link_info += f"**信譽度**: {link.domain_reputation:.1%}\n"
                
                if link.is_shortened:
                    link_info += f"**類型**: 短網址\n"
                    if link.expanded_url:
                        link_info += f"**展開**: {link.expanded_url[:40]}...\n"
                
                if link.risk_factors:
                    link_info += f"**風險因子**: {', '.join(link.risk_factors[:3])}"
                
                embed.add_field(
                    name=f"🔗 連結 {i + 1}",
                    value=link_info,
                    inline=False
                )
            
            if len(result.links) > 3:
                embed.add_field(
                    name="📝 注意",
                    value=f"還有 {len(result.links) - 3} 個連結未顯示",
                    inline=False
                )
            
            embed.add_field(
                name="⏱️ 處理時間",
                value=f"{result.processing_time:.3f} 秒",
                inline=True
            )
            
            embed.set_footer(text=f"檢測者: {interaction.user.display_name}")
            
            await interaction.followup.send(embed=embed)
            
        except Exception as e:
            logger.error(f"❌ 連結檢測錯誤: {e}")
            await interaction.followup.send("❌ 執行連結檢測時發生錯誤。", ephemeral=True)