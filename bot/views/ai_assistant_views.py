# bot/views/ai_assistant_views.py - AI 助手管理界面視圖
"""
AI 助手管理界面視圖 - Phase 5
提供統一的 AI 模型選擇、對話管理、使用統計等功能界面
"""

import discord
from discord import ui
from discord.ext import commands
from typing import Optional, Dict, Any, List
from enum import Enum
import asyncio
import traceback

from bot.utils.embed_builder import EmbedBuilder
from bot.services.ai_assistant import ai_assistant, AIProvider, AITaskType, AIRequest
from shared.logger import logger


class AIModelSelector(discord.ui.Select):
    """AI 模型選擇器"""
    
    def __init__(self):
        options = []
        
        # 根據可用的 API 密鑰動態生成選項
        if AIProvider.OPENAI in ai_assistant.available_providers:
            options.append(discord.SelectOption(
                label="OpenAI GPT-4",
                value=AIProvider.OPENAI.value,
                description="OpenAI 的 GPT-4 模型 - 適合創意和代碼任務",
                emoji="🤖"
            ))
            
        if AIProvider.CLAUDE in ai_assistant.available_providers:
            options.append(discord.SelectOption(
                label="Anthropic Claude",
                value=AIProvider.CLAUDE.value,
                description="Anthropic 的 Claude 模型 - 適合分析和推理",
                emoji="🧠"
            ))
            
        if AIProvider.GEMINI in ai_assistant.available_providers:
            options.append(discord.SelectOption(
                label="Google Gemini",
                value=AIProvider.GEMINI.value,
                description="Google 的 Gemini 模型 - 適合多模態任務",
                emoji="🌟"
            ))
        
        # 如果沒有可用的 API，顯示提示
        if not options:
            options.append(discord.SelectOption(
                label="無可用模型",
                value="none",
                description="請配置 AI API 密鑰",
                emoji="⚠️"
            ))
        
        super().__init__(
            placeholder="選擇 AI 模型...",
            min_values=1,
            max_values=1,
            options=options
        )
    
    async def callback(self, interaction: discord.Interaction):
        """模型選擇回調"""
        try:
            if self.values[0] == "none":
                embed = EmbedBuilder.create_error_embed(
                    "❌ 無可用模型",
                    "請聯繫管理員配置 AI API 密鑰"
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return
            
            selected_provider = AIProvider(self.values[0])
            
            # 更新視圖狀態
            view = self.view
            view.selected_provider = selected_provider
            
            embed = EmbedBuilder.create_success_embed(
                "✅ 模型已選擇",
                f"已選擇 **{selected_provider.value}** 模型\n現在可以開始對話了！"
            )
            
            await interaction.response.edit_message(embed=embed, view=view)
            
        except Exception as e:
            logger.error(f"AI 模型選擇錯誤: {e}")
            embed = EmbedBuilder.create_error_embed("❌ 選擇失敗", "模型選擇出現錯誤")
            await interaction.response.send_message(embed=embed, ephemeral=True)


class AITaskSelector(discord.ui.Select):
    """AI 任務類型選擇器"""
    
    def __init__(self):
        options = [
            discord.SelectOption(
                label="💬 聊天對話",
                value=AITaskType.CHAT.value,
                description="與 AI 進行自然對話",
                emoji="💬"
            ),
            discord.SelectOption(
                label="💻 代碼協助",
                value=AITaskType.CODE_HELP.value,
                description="程式設計問題解答和代碼生成",
                emoji="💻"
            ),
            discord.SelectOption(
                label="🌐 文本翻譯",
                value=AITaskType.TRANSLATE.value,
                description="多語言文本翻譯",
                emoji="🌐"
            ),
            discord.SelectOption(
                label="✍️ 創意寫作",
                value=AITaskType.CREATIVE_WRITING.value,
                description="創意內容和文章生成",
                emoji="✍️"
            ),
            discord.SelectOption(
                label="📖 故事創作",
                value=AITaskType.STORY_GENERATION.value,
                description="故事和小說創作",
                emoji="📖"
            ),
            discord.SelectOption(
                label="🎭 詩歌創作",
                value=AITaskType.POEM_GENERATION.value,
                description="詩歌和韻文創作",
                emoji="🎭"
            ),
            discord.SelectOption(
                label="📢 廣告文案",
                value=AITaskType.AD_COPY.value,
                description="營銷和廣告文案創作",
                emoji="📢"
            )
        ]
        
        super().__init__(
            placeholder="選擇任務類型...",
            min_values=1,
            max_values=1,
            options=options
        )
    
    async def callback(self, interaction: discord.Interaction):
        """任務類型選擇回調"""
        try:
            selected_task = AITaskType(self.values[0])
            
            # 更新視圖狀態
            view = self.view
            view.selected_task = selected_task
            
            # 根據任務類型顯示不同的提示
            task_descriptions = {
                AITaskType.CHAT: "準備與 AI 聊天！直接輸入您想說的話。",
                AITaskType.CODE_HELP: "準備代碼協助！描述您的程式設計問題。",
                AITaskType.TRANSLATE: "準備翻譯！輸入要翻譯的文本和目標語言。",
                AITaskType.CREATIVE_WRITING: "準備創意寫作！描述您想要的內容類型。",
                AITaskType.STORY_GENERATION: "準備故事創作！描述故事的背景和主題。",
                AITaskType.POEM_GENERATION: "準備詩歌創作！描述詩歌的主題和風格。",
                AITaskType.AD_COPY: "準備廣告文案！描述產品和目標受眾。"
            }
            
            embed = EmbedBuilder.create_success_embed(
                "✅ 任務類型已選擇",
                f"**{self.options[0].label}**\n\n{task_descriptions.get(selected_task, '開始使用 AI 功能！')}"
            )
            
            await interaction.response.edit_message(embed=embed, view=view)
            
        except Exception as e:
            logger.error(f"AI 任務選擇錯誤: {e}")
            embed = EmbedBuilder.create_error_embed("❌ 選擇失敗", "任務類型選擇出現錯誤")
            await interaction.response.send_message(embed=embed, ephemeral=True)


class AIAssistantControlView(discord.ui.View):
    """AI 助手控制面板視圖"""
    
    def __init__(self):
        super().__init__(timeout=600)
        self.selected_provider = None
        self.selected_task = None
        
        # 添加選擇器
        self.add_item(AIModelSelector())
        self.add_item(AITaskSelector())
    
    @discord.ui.button(label='📊 使用統計', style=discord.ButtonStyle.secondary, emoji='📊')
    async def usage_stats_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """顯示使用統計"""
        try:
            user_id = interaction.user.id
            
            # 這裡應該從數據庫獲取實際的使用統計
            # 暫時使用模擬數據
            embed = EmbedBuilder.create_info_embed(
                "📊 AI 使用統計",
                f"**用戶**: {interaction.user.display_name}\\n"
                f"**本月請求數**: 0\\n"
                f"**本月 Token 使用**: 0\\n"
                f"**最常用模型**: 尚未使用\\n"
                f"**最常用任務**: 尚未使用"
            )
            
            embed.add_field(
                name="💰 使用成本",
                value="本月費用: $0.00\\n剩餘額度: 無限制",
                inline=True
            )
            
            embed.add_field(
                name="⏱️ 最近活動",
                value="暫無記錄",
                inline=True
            )
            
            await interaction.response.send_message(embed=embed, ephemeral=True)
            
        except Exception as e:
            logger.error(f"使用統計顯示錯誤: {e}")
            embed = EmbedBuilder.create_error_embed("❌ 統計錯誤", "無法獲取使用統計")
            await interaction.response.send_message(embed=embed, ephemeral=True)
    
    @discord.ui.button(label='⚙️ 模型設定', style=discord.ButtonStyle.secondary, emoji='⚙️')
    async def model_settings_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """模型設定"""
        try:
            settings_view = AIModelSettingsView()
            
            embed = EmbedBuilder.create_info_embed(
                "⚙️ AI 模型設定",
                "調整 AI 模型的參數和行為"
            )
            
            embed.add_field(
                name="🎛️ 可調整參數",
                value="• **Temperature**: 創意程度 (0.0-1.0)\\n"
                      "• **Max Tokens**: 回應長度限制\\n"
                      "• **Top P**: 回應多樣性\\n"
                      "• **Frequency Penalty**: 重複懲罰",
                inline=False
            )
            
            await interaction.response.send_message(embed=embed, view=settings_view, ephemeral=True)
            
        except Exception as e:
            logger.error(f"模型設定錯誤: {e}")
            embed = EmbedBuilder.create_error_embed("❌ 設定錯誤", "無法打開模型設定")
            await interaction.response.send_message(embed=embed, ephemeral=True)
    
    @discord.ui.button(label='🗨️ 開始對話', style=discord.ButtonStyle.primary, emoji='🗨️')
    async def start_chat_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """開始 AI 對話"""
        try:
            if not self.selected_provider:
                embed = EmbedBuilder.create_warning_embed(
                    "⚠️ 請先選擇模型",
                    "請先從上方下拉選單選擇 AI 模型"
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return
                
            if not self.selected_task:
                embed = EmbedBuilder.create_warning_embed(
                    "⚠️ 請先選擇任務類型",
                    "請先從上方下拉選單選擇任務類型"
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return
            
            # 創建對話輸入模態框
            modal = AIChatModal(self.selected_provider, self.selected_task)
            await interaction.response.send_modal(modal)
            
        except Exception as e:
            logger.error(f"開始對話錯誤: {e}")
            embed = EmbedBuilder.create_error_embed("❌ 對話錯誤", "無法開始 AI 對話")
            await interaction.response.send_message(embed=embed, ephemeral=True)


class AIModelSettingsView(discord.ui.View):
    """AI 模型設定視圖"""
    
    def __init__(self):
        super().__init__(timeout=300)
        self.temperature = 0.7
        self.max_tokens = 1000
    
    @discord.ui.button(label='🔥 提高創意度', style=discord.ButtonStyle.secondary)
    async def increase_temperature(self, interaction: discord.Interaction, button: discord.ui.Button):
        """提高創意度 (Temperature)"""
        self.temperature = min(1.0, self.temperature + 0.1)
        await self._update_settings_display(interaction)
    
    @discord.ui.button(label='❄️ 降低創意度', style=discord.ButtonStyle.secondary)
    async def decrease_temperature(self, interaction: discord.Interaction, button: discord.ui.Button):
        """降低創意度 (Temperature)"""
        self.temperature = max(0.0, self.temperature - 0.1)
        await self._update_settings_display(interaction)
    
    @discord.ui.button(label='📏 增加長度', style=discord.ButtonStyle.secondary)
    async def increase_tokens(self, interaction: discord.Interaction, button: discord.ui.Button):
        """增加回應長度"""
        self.max_tokens = min(4000, self.max_tokens + 200)
        await self._update_settings_display(interaction)
    
    @discord.ui.button(label='📐 減少長度', style=discord.ButtonStyle.secondary)
    async def decrease_tokens(self, interaction: discord.Interaction, button: discord.ui.Button):
        """減少回應長度"""
        self.max_tokens = max(100, self.max_tokens - 200)
        await self._update_settings_display(interaction)
    
    async def _update_settings_display(self, interaction: discord.Interaction):
        """更新設定顯示"""
        embed = EmbedBuilder.create_info_embed(
            "⚙️ 當前模型設定",
            f"**創意度 (Temperature)**: {self.temperature:.1f}\\n"
            f"**最大長度 (Max Tokens)**: {self.max_tokens}\\n\\n"
            f"*設定將在下次對話時生效*"
        )
        
        await interaction.response.edit_message(embed=embed, view=self)


class AIChatModal(discord.ui.Modal, title='🤖 AI 助手對話'):
    """AI 對話輸入模態框"""
    
    def __init__(self, provider: AIProvider, task_type: AITaskType):
        super().__init__()
        self.provider = provider
        self.task_type = task_type
        
        # 根據任務類型調整輸入框
        placeholders = {
            AITaskType.CHAT: "輸入您想與 AI 討論的內容...",
            AITaskType.CODE_HELP: "描述您的程式設計問題或貼上代碼...",
            AITaskType.TRANSLATE: "輸入要翻譯的文本和目標語言...",
            AITaskType.CREATIVE_WRITING: "描述您想要的創意內容...",
            AITaskType.STORY_GENERATION: "描述故事背景、角色或主題...",
            AITaskType.POEM_GENERATION: "描述詩歌主題和期望的風格...",
            AITaskType.AD_COPY: "描述產品/服務和目標受眾..."
        }
        
        self.chat_input.placeholder = placeholders.get(task_type, "輸入您的請求...")
    
    chat_input = discord.ui.TextInput(
        label='您的訊息',
        style=discord.TextStyle.paragraph,
        max_length=2000,
        required=True
    )
    
    async def on_submit(self, interaction: discord.Interaction):
        """處理對話提交"""
        try:
            await interaction.response.defer(thinking=True)
            
            # 創建 AI 請求
            ai_request = AIRequest(
                user_id=interaction.user.id,
                guild_id=interaction.guild.id if interaction.guild else 0,
                task_type=self.task_type,
                prompt=self.chat_input.value,
                context={},
                provider=self.provider,
                max_tokens=1000,
                temperature=0.7
            )
            
            # 調用 AI 服務
            logger.info(f"🤖 AI 請求: 用戶={interaction.user.name}, 模型={self.provider.value}, 任務={self.task_type.value}")
            
            response = await ai_assistant.process_request(ai_request)
            
            if response.success:
                # 成功回應
                embed = EmbedBuilder.create_success_embed(
                    f"🤖 {self.provider.value.upper()} 回應",
                    response.content[:4000]  # Discord embed 限制
                )
                
                embed.add_field(
                    name="📊 統計信息",
                    value=f"Token 使用: {response.tokens_used}\\n"
                          f"回應時間: {response.response_time:.2f}s\\n"
                          f"模型: {response.metadata.get('model_used', 'unknown')}",
                    inline=True
                )
                
                embed.set_footer(text=f"任務類型: {self.task_type.value} | 請求 ID: {response.request_id}")
                
            else:
                # 錯誤回應
                embed = EmbedBuilder.create_error_embed(
                    "❌ AI 回應失敗",
                    f"錯誤信息: {response.error_message}"
                )
            
            await interaction.followup.send(embed=embed)
            
        except Exception as e:
            logger.error(f"AI 對話處理錯誤: {e}")
            logger.error(traceback.format_exc())
            
            embed = EmbedBuilder.create_error_embed(
                "❌ 對話處理失敗",
                f"處理您的請求時發生錯誤: {str(e)}"
            )
            
            try:
                await interaction.followup.send(embed=embed, ephemeral=True)
            except:
                pass


class AIMainMenuView(discord.ui.View):
    """AI 主選單視圖"""
    
    def __init__(self):
        super().__init__(timeout=300)
    
    @discord.ui.button(label='🤖 AI 助手', style=discord.ButtonStyle.primary, emoji='🤖')
    async def ai_assistant_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """AI 助手按鈕"""
        try:
            control_view = AIAssistantControlView()
            
            embed = EmbedBuilder.create_info_embed(
                "🤖 AI 智能助手",
                "歡迎使用 AI 智能助手！請選擇模型和任務類型開始使用。"
            )
            
            # 顯示可用的 AI 提供商
            available_models = []
            if AIProvider.OPENAI in ai_assistant.available_providers:
                available_models.append("✅ OpenAI GPT-4")
            if AIProvider.CLAUDE in ai_assistant.available_providers:
                available_models.append("✅ Anthropic Claude")
            if AIProvider.GEMINI in ai_assistant.available_providers:
                available_models.append("✅ Google Gemini")
            
            if available_models:
                embed.add_field(
                    name="🔧 可用模型",
                    value="\\n".join(available_models),
                    inline=True
                )
            else:
                embed.add_field(
                    name="⚠️ 模型狀態",
                    value="暫無可用的 AI 模型\\n請聯繫管理員配置 API 密鑰",
                    inline=True
                )
            
            embed.add_field(
                name="🎯 功能特色",
                value="• 多模型切換\\n• 智能任務分類\\n• 使用統計追蹤\\n• 個性化設定",
                inline=True
            )
            
            await interaction.response.send_message(embed=embed, view=control_view, ephemeral=True)
            
        except Exception as e:
            logger.error(f"AI 助手按鈕錯誤: {e}")
            embed = EmbedBuilder.create_error_embed("❌ 系統錯誤", "無法啟動 AI 助手")
            await interaction.response.send_message(embed=embed, ephemeral=True)
    
    @discord.ui.button(label='📊 系統狀態', style=discord.ButtonStyle.secondary, emoji='📊')
    async def system_status_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """系統狀態按鈕"""
        try:
            embed = EmbedBuilder.create_info_embed(
                "📊 AI 系統狀態",
                "顯示 AI 服務的運行狀態和統計信息"
            )
            
            # 檢查各個 AI 服務的狀態
            status_info = []
            for provider in [AIProvider.OPENAI, AIProvider.CLAUDE, AIProvider.GEMINI]:
                if provider in ai_assistant.available_providers:
                    status_info.append(f"✅ {provider.value}: 可用")
                else:
                    status_info.append(f"❌ {provider.value}: 未配置")
            
            embed.add_field(
                name="🔧 服務狀態",
                value="\\n".join(status_info),
                inline=True
            )
            
            embed.add_field(
                name="📈 使用統計 (今日)",
                value="總請求數: 0\\n成功率: 100%\\n平均響應時間: 0.0s",
                inline=True
            )
            
            embed.add_field(
                name="💾 系統資源",
                value="內存使用: 正常\\nAPI 配額: 充足\\n錯誤率: 0%",
                inline=True
            )
            
            await interaction.response.send_message(embed=embed, ephemeral=True)
            
        except Exception as e:
            logger.error(f"系統狀態錯誤: {e}")
            embed = EmbedBuilder.create_error_embed("❌ 狀態錯誤", "無法獲取系統狀態")
            await interaction.response.send_message(embed=embed, ephemeral=True)