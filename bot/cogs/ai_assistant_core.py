# bot/cogs/ai_assistant_core.py - AI智能助手指令模組
"""
AI智能助手指令模組 v2.2.0
提供AI對話、創意內容生成、代碼助手等功能的Discord指令
"""

import discord
from discord.ext import commands, tasks
from discord import app_commands
from typing import Dict, List, Optional, Any, Tuple
import asyncio
import random
import time
import json
from datetime import datetime, timezone, timedelta

from bot.services.ai_assistant import ai_assistant, AIProvider, AITaskType, AIRequest
from bot.services.economy_manager import EconomyManager
from bot.utils.embed_builder import EmbedBuilder
from bot.views.ai_assistant_views import AIMainMenuView, AIAssistantControlView
from shared.cache_manager import cache_manager, cached
from shared.prometheus_metrics import prometheus_metrics, track_command_execution
from shared.logger import logger

class AIAssistantCog(commands.Cog):
    """AI智能助手功能"""
    
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.economy_manager = EconomyManager()
        
        # AI使用成本 (金幣)
        self.ai_costs = {
            AITaskType.CHAT: 5,
            AITaskType.CODE_HELP: 10,
            AITaskType.TRANSLATE: 8,
            AITaskType.CREATIVE_WRITING: 15,
            AITaskType.STORY_GENERATION: 20,
            AITaskType.POEM_GENERATION: 15,
            AITaskType.AD_COPY: 12
        }
        
        # 每日免費額度
        self.daily_free_quota = 10
        
        logger.info("🤖 AI助手指令模組初始化完成")

    # ========== Phase 5 統一 AI 管理界面 ==========

    @app_commands.command(name="ai", description="🤖 AI 智能助手統一管理界面 - Phase 5")
    async def ai_assistant_menu(self, interaction: discord.Interaction):
        """AI 智能助手統一管理界面"""
        try:
            view = AIMainMenuView()
            
            embed = EmbedBuilder.create_info_embed(
                "🤖 AI 智能助手 - Phase 5",
                "歡迎使用全新的 AI 智能助手！現在支援多個 AI 模型和統一管理界面。"
            )
            
            # 顯示可用功能
            embed.add_field(
                name="🎯 核心功能",
                value="• **多模型支援**: OpenAI GPT-4, Claude, Gemini\n"
                      "• **智能任務分類**: 聊天、代碼、翻譯、創作等\n"
                      "• **統一管理界面**: 模型選擇、參數調整、統計查看\n"
                      "• **使用量監控**: 實時追蹤 API 使用情況",
                inline=False
            )
            
            # 顯示可用模型狀態
            available_models = []
            if AIProvider.OPENAI in ai_assistant.available_providers:
                available_models.append("✅ **OpenAI GPT-4**: 創意和代碼任務")
            if AIProvider.CLAUDE in ai_assistant.available_providers:
                available_models.append("✅ **Anthropic Claude**: 分析和推理")
            if AIProvider.GEMINI in ai_assistant.available_providers:
                available_models.append("✅ **Google Gemini**: 多模態任務")
            
            if available_models:
                embed.add_field(
                    name="🔧 可用模型",
                    value="\n".join(available_models),
                    inline=False
                )
            else:
                embed.add_field(
                    name="⚠️ 模型狀態",
                    value="暫無可用的 AI 模型，請聯繫管理員配置 API 密鑰",
                    inline=False
                )
            
            embed.add_field(
                name="🚀 開始使用",
                value="點擊下方按鈕開始使用 AI 助手功能！",
                inline=False
            )
            
            embed.set_footer(text="Potato Bot v3.2.0 | Phase 5 AI 整合系統")
            
            await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
            
        except Exception as e:
            logger.error(f"AI 助手選單錯誤: {e}")
            embed = EmbedBuilder.create_error_embed(
                "❌ 系統錯誤",
                "無法啟動 AI 助手管理界面"
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)

    # ========== 基礎AI對話 (兼容舊命令) ==========

    @app_commands.command(name="ask", description="與AI助手聊天對話")
    @app_commands.describe(message="您想說的話")
    async def ask_ai(self, interaction: discord.Interaction, message: str):
        """AI聊天對話"""
        try:
            await interaction.response.defer()
            
            # 檢查使用權限
            can_use, cost_info = await self._check_usage_permission(
                interaction.user.id, interaction.guild.id, AITaskType.CHAT
            )
            
            if not can_use:
                embed = EmbedBuilder.build(
                    title="❌ 使用受限",
                    description=cost_info["message"],
                    color=0xFF0000
                )
                await interaction.followup.send(embed=embed, ephemeral=True)
                return
            
            # 處理AI請求
            response = await ai_assistant.chat(
                user_id=interaction.user.id,
                guild_id=interaction.guild.id,
                message=message
            )
            
            if response.success:
                # 扣除費用
                if cost_info["cost"] > 0:
                    await self.economy_manager.add_coins(
                        interaction.user.id, interaction.guild.id, -cost_info["cost"]
                    )
                
                # 記錄使用量
                await self._record_daily_usage(interaction.user.id)
                
                embed = EmbedBuilder.build(
                    title="🤖 AI助手回應",
                    description=response.content,
                    color=0x00AAFF
                )
                
                embed.add_field(
                    name="📊 使用資訊",
                    value=f"消耗代幣: {response.tokens_used:,}\n"
                          f"回應時間: {response.response_time:.2f}秒" +
                          (f"\n消耗金幣: {cost_info['cost']}🪙" if cost_info["cost"] > 0 else ""),
                    inline=True
                )
                
                embed.set_footer(text=f"AI提供商: {response.provider.value.title()}")
                
            else:
                embed = EmbedBuilder.build(
                    title="❌ AI請求失敗",
                    description=response.error_message or "未知錯誤",
                    color=0xFF0000
                )
            
            await interaction.followup.send(embed=embed)
            
            # 記錄指標
            track_command_execution("ask", interaction.guild.id)
            
        except Exception as e:
            logger.error(f"❌ AI對話錯誤: {e}")
            await interaction.followup.send("❌ AI對話時發生錯誤，請稍後再試。", ephemeral=True)

    # ========== 代碼助手 ==========

    @app_commands.command(name="code_help", description="程式設計問題助手")
    @app_commands.describe(
        question="您的程式設計問題",
        language="程式語言"
    )
    @app_commands.choices(language=[
        app_commands.Choice(name="Python", value="python"),
        app_commands.Choice(name="JavaScript", value="javascript"),
        app_commands.Choice(name="Java", value="java"),
        app_commands.Choice(name="C++", value="cpp"),
        app_commands.Choice(name="Go", value="go"),
        app_commands.Choice(name="Rust", value="rust"),
        app_commands.Choice(name="其他", value="other")
    ])
    async def code_help(self, interaction: discord.Interaction, question: str, language: str = "python"):
        """代碼助手"""
        try:
            await interaction.response.defer()
            
            # 檢查使用權限
            can_use, cost_info = await self._check_usage_permission(
                interaction.user.id, interaction.guild.id, AITaskType.CODE_HELP
            )
            
            if not can_use:
                embed = EmbedBuilder.build(
                    title="❌ 使用受限",
                    description=cost_info["message"],
                    color=0xFF0000
                )
                await interaction.followup.send(embed=embed, ephemeral=True)
                return
            
            # 處理代碼助手請求
            response = await ai_assistant.help_with_code(
                user_id=interaction.user.id,
                guild_id=interaction.guild.id,
                code_question=question,
                language=language
            )
            
            if response.success:
                # 扣除費用
                if cost_info["cost"] > 0:
                    await self.economy_manager.add_coins(
                        interaction.user.id, interaction.guild.id, -cost_info["cost"]
                    )
                
                # 記錄使用量
                await self._record_daily_usage(interaction.user.id)
                
                # 限制回應長度以符合Discord限制
                content = response.content
                if len(content) > 1800:
                    content = content[:1800] + "...\n\n*回應內容過長，已截斷*"
                
                embed = EmbedBuilder.build(
                    title=f"💻 代碼助手 ({language.title()})",
                    description=content,
                    color=0x00FF88
                )
                
                embed.add_field(
                    name="📊 使用資訊",
                    value=f"消耗代幣: {response.tokens_used:,}\n"
                          f"回應時間: {response.response_time:.2f}秒" +
                          (f"\n消耗金幣: {cost_info['cost']}🪙" if cost_info["cost"] > 0 else ""),
                    inline=True
                )
                
            else:
                embed = EmbedBuilder.build(
                    title="❌ 代碼助手請求失敗",
                    description=response.error_message or "未知錯誤",
                    color=0xFF0000
                )
            
            await interaction.followup.send(embed=embed)
            
            # 記錄指標
            track_command_execution("code_help", interaction.guild.id)
            
        except Exception as e:
            logger.error(f"❌ 代碼助手錯誤: {e}")
            await interaction.followup.send("❌ 代碼助手請求時發生錯誤，請稍後再試。", ephemeral=True)

    # ========== 翻譯服務 ==========

    @app_commands.command(name="translate", description="AI翻譯服務")
    @app_commands.describe(
        text="要翻譯的文本",
        target_language="目標語言"
    )
    @app_commands.choices(target_language=[
        app_commands.Choice(name="英文", value="英文"),
        app_commands.Choice(name="日文", value="日文"),
        app_commands.Choice(name="韓文", value="韓文"),
        app_commands.Choice(name="法文", value="法文"),
        app_commands.Choice(name="德文", value="德文"),
        app_commands.Choice(name="西班牙文", value="西班牙文"),
        app_commands.Choice(name="繁體中文", value="繁體中文"),
        app_commands.Choice(name="簡體中文", value="簡體中文")
    ])
    async def translate(self, interaction: discord.Interaction, text: str, target_language: str = "英文"):
        """AI翻譯"""
        try:
            await interaction.response.defer()
            
            # 檢查文本長度
            if len(text) > 1000:
                await interaction.followup.send("❌ 翻譯文本過長，請限制在1000字符內。", ephemeral=True)
                return
            
            # 檢查使用權限
            can_use, cost_info = await self._check_usage_permission(
                interaction.user.id, interaction.guild.id, AITaskType.TRANSLATE
            )
            
            if not can_use:
                embed = EmbedBuilder.build(
                    title="❌ 使用受限",
                    description=cost_info["message"],
                    color=0xFF0000
                )
                await interaction.followup.send(embed=embed, ephemeral=True)
                return
            
            # 處理翻譯請求
            response = await ai_assistant.translate_text(
                user_id=interaction.user.id,
                guild_id=interaction.guild.id,
                text=text,
                target_language=target_language
            )
            
            if response.success:
                # 扣除費用
                if cost_info["cost"] > 0:
                    await self.economy_manager.add_coins(
                        interaction.user.id, interaction.guild.id, -cost_info["cost"]
                    )
                
                # 記錄使用量
                await self._record_daily_usage(interaction.user.id)
                
                embed = EmbedBuilder.build(
                    title=f"🌐 翻譯結果 → {target_language}",
                    color=0x4169E1
                )
                
                embed.add_field(
                    name="📝 原文",
                    value=text[:500] + ("..." if len(text) > 500 else ""),
                    inline=False
                )
                
                embed.add_field(
                    name="🔄 譯文",
                    value=response.content,
                    inline=False
                )
                
                embed.add_field(
                    name="📊 使用資訊",
                    value=f"消耗代幣: {response.tokens_used:,}\n"
                          f"回應時間: {response.response_time:.2f}秒" +
                          (f"\n消耗金幣: {cost_info['cost']}🪙" if cost_info["cost"] > 0 else ""),
                    inline=True
                )
                
            else:
                embed = EmbedBuilder.build(
                    title="❌ 翻譯失敗",
                    description=response.error_message or "未知錯誤",
                    color=0xFF0000
                )
            
            await interaction.followup.send(embed=embed)
            
            # 記錄指標
            track_command_execution("translate", interaction.guild.id)
            
        except Exception as e:
            logger.error(f"❌ 翻譯錯誤: {e}")
            await interaction.followup.send("❌ 翻譯時發生錯誤，請稍後再試。", ephemeral=True)

    # ========== 創意內容生成 ==========

    @app_commands.command(name="generate_story", description="AI故事生成")
    @app_commands.describe(
        theme="故事主題",
        style="故事風格"
    )
    @app_commands.choices(style=[
        app_commands.Choice(name="輕鬆幽默", value="輕鬆幽默"),
        app_commands.Choice(name="懸疑推理", value="懸疑推理"),
        app_commands.Choice(name="科幻冒險", value="科幻冒險"),
        app_commands.Choice(name="奇幻魔法", value="奇幻魔法"),
        app_commands.Choice(name="浪漫愛情", value="浪漫愛情"),
        app_commands.Choice(name="歷史故事", value="歷史故事")
    ])
    async def generate_story(self, interaction: discord.Interaction, theme: str, style: str = "輕鬆幽默"):
        """AI故事生成"""
        try:
            await interaction.response.defer()
            
            # 檢查使用權限
            can_use, cost_info = await self._check_usage_permission(
                interaction.user.id, interaction.guild.id, AITaskType.STORY_GENERATION
            )
            
            if not can_use:
                embed = EmbedBuilder.build(
                    title="❌ 使用受限",
                    description=cost_info["message"],
                    color=0xFF0000
                )
                await interaction.followup.send(embed=embed, ephemeral=True)
                return
            
            # 生成故事
            response = await ai_assistant.generate_story(
                user_id=interaction.user.id,
                guild_id=interaction.guild.id,
                theme=theme,
                style=style
            )
            
            if response.success:
                # 扣除費用
                if cost_info["cost"] > 0:
                    await self.economy_manager.add_coins(
                        interaction.user.id, interaction.guild.id, -cost_info["cost"]
                    )
                
                # 記錄使用量
                await self._record_daily_usage(interaction.user.id)
                
                # 處理長文本
                content = response.content
                if len(content) > 1500:
                    # 分段發送
                    parts = [content[i:i+1500] for i in range(0, len(content), 1500)]
                    
                    for i, part in enumerate(parts):
                        embed = EmbedBuilder.build(
                            title=f"📚 AI故事創作 - {theme} ({i+1}/{len(parts)})",
                            description=part,
                            color=0xFF6B6B
                        )
                        
                        if i == 0:
                            embed.add_field(
                                name="🎭 故事設定",
                                value=f"主題: {theme}\n風格: {style}",
                                inline=True
                            )
                            
                            embed.add_field(
                                name="📊 使用資訊",
                                value=f"消耗代幣: {response.tokens_used:,}\n"
                                      f"回應時間: {response.response_time:.2f}秒" +
                                      (f"\n消耗金幣: {cost_info['cost']}🪙" if cost_info["cost"] > 0 else ""),
                                inline=True
                            )
                        
                        await interaction.followup.send(embed=embed)
                        if i < len(parts) - 1:
                            await asyncio.sleep(1)  # 避免速率限制
                else:
                    embed = EmbedBuilder.build(
                        title=f"📚 AI故事創作 - {theme}",
                        description=content,
                        color=0xFF6B6B
                    )
                    
                    embed.add_field(
                        name="🎭 故事設定",
                        value=f"主題: {theme}\n風格: {style}",
                        inline=True
                    )
                    
                    embed.add_field(
                        name="📊 使用資訊",
                        value=f"消耗代幣: {response.tokens_used:,}\n"
                              f"回應時間: {response.response_time:.2f}秒" +
                              (f"\n消耗金幣: {cost_info['cost']}🪙" if cost_info["cost"] > 0 else ""),
                        inline=True
                    )
                    
                    await interaction.followup.send(embed=embed)
            else:
                embed = EmbedBuilder.build(
                    title="❌ 故事生成失敗",
                    description=response.error_message or "未知錯誤",
                    color=0xFF0000
                )
                await interaction.followup.send(embed=embed)
            
            # 記錄指標
            track_command_execution("generate_story", interaction.guild.id)
            
        except Exception as e:
            logger.error(f"❌ 故事生成錯誤: {e}")
            await interaction.followup.send("❌ 故事生成時發生錯誤，請稍後再試。", ephemeral=True)

    @app_commands.command(name="generate_poem", description="AI詩歌創作")
    @app_commands.describe(
        theme="詩歌主題",
        style="詩歌風格"
    )
    @app_commands.choices(style=[
        app_commands.Choice(name="現代詩", value="現代詩"),
        app_commands.Choice(name="古典詩", value="古典詩"),
        app_commands.Choice(name="打油詩", value="打油詩"),
        app_commands.Choice(name="情詩", value="情詩"),
        app_commands.Choice(name="讚美詩", value="讚美詩"),
        app_commands.Choice(name="哲理詩", value="哲理詩")
    ])
    async def generate_poem(self, interaction: discord.Interaction, theme: str, style: str = "現代詩"):
        """AI詩歌創作"""
        try:
            await interaction.response.defer()
            
            # 檢查使用權限
            can_use, cost_info = await self._check_usage_permission(
                interaction.user.id, interaction.guild.id, AITaskType.POEM_GENERATION
            )
            
            if not can_use:
                embed = EmbedBuilder.build(
                    title="❌ 使用受限",
                    description=cost_info["message"],
                    color=0xFF0000
                )
                await interaction.followup.send(embed=embed, ephemeral=True)
                return
            
            # 生成詩歌
            response = await ai_assistant.generate_poem(
                user_id=interaction.user.id,
                guild_id=interaction.guild.id,
                theme=theme,
                style=style
            )
            
            if response.success:
                # 扣除費用
                if cost_info["cost"] > 0:
                    await self.economy_manager.add_coins(
                        interaction.user.id, interaction.guild.id, -cost_info["cost"]
                    )
                
                # 記錄使用量
                await self._record_daily_usage(interaction.user.id)
                
                embed = EmbedBuilder.build(
                    title=f"🎵 AI詩歌創作 - {theme}",
                    description=f"```\n{response.content}\n```",
                    color=0x9B59B6
                )
                
                embed.add_field(
                    name="🎭 創作設定",
                    value=f"主題: {theme}\n風格: {style}",
                    inline=True
                )
                
                embed.add_field(
                    name="📊 使用資訊",
                    value=f"消耗代幣: {response.tokens_used:,}\n"
                          f"回應時間: {response.response_time:.2f}秒" +
                          (f"\n消耗金幣: {cost_info['cost']}🪙" if cost_info["cost"] > 0 else ""),
                    inline=True
                )
                
            else:
                embed = EmbedBuilder.build(
                    title="❌ 詩歌創作失敗",
                    description=response.error_message or "未知錯誤",
                    color=0xFF0000
                )
            
            await interaction.followup.send(embed=embed)
            
            # 記錄指標
            track_command_execution("generate_poem", interaction.guild.id)
            
        except Exception as e:
            logger.error(f"❌ 詩歌創作錯誤: {e}")
            await interaction.followup.send("❌ 詩歌創作時發生錯誤，請稍後再試。", ephemeral=True)

    # ========== 使用統計和管理 ==========

    @app_commands.command(name="ai_usage", description="查看AI使用統計")
    async def ai_usage_stats(self, interaction: discord.Interaction):
        """AI使用統計"""
        try:
            user_id = interaction.user.id
            
            # 獲取使用統計
            usage_stats = await ai_assistant.get_user_usage(user_id, AIProvider.OPENAI)
            daily_usage = await self._get_daily_usage(user_id)
            
            # 獲取經濟狀態
            economy = await self.economy_manager.get_user_economy(user_id, interaction.guild.id)
            
            embed = EmbedBuilder.build(
                title="🤖 AI使用統計",
                description=f"{interaction.user.display_name} 的AI服務使用情況",
                color=0x4169E1
            )
            
            embed.set_thumbnail(url=interaction.user.display_avatar.url)
            
            # 今日使用情況
            remaining_free = max(0, self.daily_free_quota - daily_usage)
            embed.add_field(
                name="📅 今日使用",
                value=f"已使用: {daily_usage}/{self.daily_free_quota} (免費)\n"
                      f"剩餘免費額度: {remaining_free}\n"
                      f"Token消耗: {usage_stats['daily_tokens']:,}",
                inline=True
            )
            
            # 本月統計
            embed.add_field(
                name="📊 本月統計",
                value=f"Token消耗: {usage_stats['monthly_tokens']:,}\n"
                      f"限制: {usage_stats['monthly_limit']:,}\n"
                      f"使用率: {(usage_stats['monthly_tokens']/usage_stats['monthly_limit']*100):.1f}%",
                inline=True
            )
            
            # 經濟狀態
            embed.add_field(
                name="💰 經濟狀態",
                value=f"金幣餘額: {economy.get('coins', 0):,}🪙\n"
                      f"可用於AI服務",
                inline=True
            )
            
            # 費用說明
            cost_text = []
            for task_type, cost in self.ai_costs.items():
                task_name = {
                    AITaskType.CHAT: "💬 聊天對話",
                    AITaskType.CODE_HELP: "💻 代碼助手", 
                    AITaskType.TRANSLATE: "🌐 翻譯服務",
                    AITaskType.CREATIVE_WRITING: "✍️ 創意寫作",
                    AITaskType.STORY_GENERATION: "📚 故事生成",
                    AITaskType.POEM_GENERATION: "🎵 詩歌創作",
                    AITaskType.AD_COPY: "📢 廣告文案"
                }.get(task_type, task_type.value)
                
                cost_text.append(f"{task_name}: {cost}🪙")
            
            embed.add_field(
                name="💳 服務費用",
                value="\n".join(cost_text[:4]),  # 只顯示前4個
                inline=True
            )
            
            embed.add_field(
                name="💳 其他服務",
                value="\n".join(cost_text[4:]),  # 顯示剩餘的
                inline=True
            )
            
            embed.add_field(
                name="💡 費用說明",
                value=f"• 每日前{self.daily_free_quota}次免費\n"
                      "• 超出免費額度後按服務收費\n"
                      "• 使用遊戲獲得的金幣支付",
                inline=False
            )
            
            await interaction.response.send_message(embed=embed, ephemeral=True)
            
        except Exception as e:
            logger.error(f"❌ AI使用統計錯誤: {e}")
            await interaction.response.send_message("❌ 獲取使用統計時發生錯誤。", ephemeral=True)

    # ========== 輔助方法 ==========

    async def _check_usage_permission(self, user_id: int, guild_id: int, 
                                    task_type: AITaskType) -> tuple[bool, Dict[str, Any]]:
        """檢查使用權限和費用"""
        try:
            # 檢查每日免費額度
            daily_usage = await self._get_daily_usage(user_id)
            
            if daily_usage < self.daily_free_quota:
                return True, {"cost": 0, "message": "免費額度內"}
            
            # 檢查金幣餘額
            economy = await self.economy_manager.get_user_economy(user_id, guild_id)
            cost = self.ai_costs.get(task_type, 10)
            
            if economy.get("coins", 0) >= cost:
                return True, {"cost": cost, "message": f"需要消耗 {cost}🪙"}
            else:
                return False, {
                    "cost": cost,
                    "message": f"金幣不足！需要 {cost}🪙，您目前有 {economy.get('coins', 0)}🪙"
                }
                
        except Exception as e:
            logger.error(f"❌ 檢查使用權限失敗: {e}")
            return False, {"cost": 0, "message": "檢查權限時發生錯誤"}

    async def _get_daily_usage(self, user_id: int) -> int:
        """獲取每日使用次數"""
        try:
            cache_key = f"ai_daily_usage:{user_id}"
            usage = await cache_manager.get(cache_key)
            return usage or 0
            
        except Exception as e:
            logger.error(f"❌ 獲取每日使用量失敗: {e}")
            return 0

    async def _record_daily_usage(self, user_id: int):
        """記錄每日使用次數"""
        try:
            cache_key = f"ai_daily_usage:{user_id}"
            current_usage = await self._get_daily_usage(user_id)
            
            # 設置到明天零點過期
            tomorrow = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
            tomorrow += timedelta(days=1)
            ttl = int((tomorrow - datetime.now(timezone.utc)).total_seconds())
            
            await cache_manager.set(cache_key, current_usage + 1, ttl)
            
        except Exception as e:
            logger.error(f"❌ 記錄每日使用量失敗: {e}")

async def setup(bot):
    """設置 Cog"""
    await bot.add_cog(AIAssistantCog(bot))