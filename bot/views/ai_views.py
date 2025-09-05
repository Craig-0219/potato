# bot/views/ai_views.py - AI 系統互動界面
"""
AI 智能回覆系統互動界面
包含回覆建議選擇、標籤建議應用等 UI 元件
"""

from typing import Any, Dict, List

import discord

from shared.logger import logger


class AIReplyView(discord.ui.View):
    """AI 回覆建議選擇界面"""

    def __init__(self, suggestions: List[Dict[str, Any]], confidence: float, ai_dao):
        super().__init__(timeout=300)  # 5分鐘超時
        self.suggestions = suggestions
        self.confidence = confidence
        self.ai_dao = ai_dao
        self.suggestion_ids = {}

        # 添加建議按鈕（最多3個）
        for i, suggestion in enumerate(suggestions[:3]):
            button = discord.ui.Button(
                label=f"建議 {i+1} ({suggestion['confidence']:.1%})",
                style=discord.ButtonStyle.primary,
                custom_id=f"ai_reply_{i}",
                emoji="💡",
            )
            button.callback = self._create_reply_callback(i)
            self.add_item(button)

        # 添加查看詳細按鈕
        detail_button = discord.ui.Button(
            label="查看詳細",
            style=discord.ButtonStyle.secondary,
            custom_id="ai_reply_detail",
            emoji="📝",
        )
        detail_button.callback = self._show_detail_callback
        self.add_item(detail_button)

        # 添加不採用按鈕
        reject_button = discord.ui.Button(
            label="不採用",
            style=discord.ButtonStyle.danger,
            custom_id="ai_reply_reject",
            emoji="❌",
        )
        reject_button.callback = self._reject_callback
        self.add_item(reject_button)

    def _create_reply_callback(self, index: int):
        """創建回覆按鈕的回調函數"""

        async def callback(interaction: discord.Interaction):
            if index >= len(self.suggestions):
                await interaction.response.send_message("❌ 無效的建議選擇", ephemeral=True)
                return

            suggestion = self.suggestions[index]

            # 創建模態對話框讓用戶編輯回覆
            modal = AIReplyEditModal(suggestion["text"], suggestion, self.ai_dao)
            await interaction.response.send_modal(modal)

        return callback

    async def _show_detail_callback(self, interaction: discord.Interaction):
        """顯示詳細建議"""
        embed = discord.Embed(title="📝 AI 回覆建議詳細", color=0x00BFFF)

        for i, suggestion in enumerate(self.suggestions, 1):
            embed.add_field(
                name=f"建議 {i} - {suggestion.get('type', '標準')} ({suggestion['confidence']:.1%})",
                value=f"```{suggestion['text'][:200]}{'...' if len(suggestion['text']) > 200 else ''}```",
                inline=False,
            )

        embed.set_footer(text="選擇一個建議來編輯和使用")

        await interaction.response.send_message(embed=embed, ephemeral=True)

    async def _reject_callback(self, interaction: discord.Interaction):
        """拒絕所有建議"""
        # 這裡可以記錄用戶拒絕的回饋
        embed = discord.Embed(
            title="❌ 已拒絕建議",
            description="感謝您的回饋，我們會持續改進 AI 建議的品質。",
            color=0x6C757D,
        )

        # 禁用所有按鈕
        for item in self.children:
            item.disabled = True

        await interaction.response.edit_message(embed=embed, view=self)

    async def on_timeout(self):
        """處理超時"""
        for item in self.children:
            item.disabled = True


class AIReplyEditModal(discord.ui.Modal):
    """AI 回覆編輯模態對話框"""

    def __init__(self, suggested_text: str, suggestion: Dict[str, Any], ai_dao):
        super().__init__(title="編輯 AI 建議回覆")
        self.suggestion = suggestion
        self.ai_dao = ai_dao

        # 回覆內容輸入框
        self.reply_input = discord.ui.TextInput(
            label="回覆內容",
            placeholder="編輯或直接使用 AI 建議的回覆...",
            default=suggested_text,
            style=discord.TextStyle.paragraph,
            max_length=2000,
            required=True,
        )
        self.add_item(self.reply_input)

        # 評分輸入框
        self.rating_input = discord.ui.TextInput(
            label="AI 建議評分 (1-5，可選)",
            placeholder="為這個 AI 建議評分（1=很差，5=很好）",
            style=discord.TextStyle.short,
            max_length=1,
            required=False,
        )
        self.add_item(self.rating_input)

    async def on_submit(self, interaction: discord.Interaction):
        """提交編輯後的回覆"""
        try:
            reply_content = self.reply_input.value.strip()

            if not reply_content:
                await interaction.response.send_message("❌ 回覆內容不能為空", ephemeral=True)
                return

            # 處理評分
            rating = None
            if self.rating_input.value.strip():
                try:
                    rating = int(self.rating_input.value.strip())
                    if rating < 1 or rating > 5:
                        rating = None
                except ValueError:
                    rating = None

            # 發送回覆到票券頻道
            await interaction.channel.send(reply_content)

            # 記錄建議被採用的回饋（如果有建議ID的話）
            # 這裡可以添加實際的回饋記錄邏輯

            success_embed = discord.Embed(
                title="✅ 回覆已發送",
                description="AI 建議回覆已成功發送到票券頻道",
                color=0x28A745,
            )

            if rating:
                success_embed.add_field(
                    name="📊 評分記錄",
                    value=f"您的評分：{rating}/5 ⭐",
                    inline=False,
                )

            await interaction.response.send_message(embed=success_embed, ephemeral=True)

        except Exception as e:
            logger.error(f"AI 回覆提交錯誤: {e}")
            await interaction.response.send_message(
                f"❌ 發送回覆時發生錯誤：{str(e)}", ephemeral=True
            )


class AITagSuggestionView(discord.ui.View):
    """AI 標籤建議應用界面"""

    def __init__(self, tag_suggestions: List[Dict[str, Any]], ticket_id: int, ai_dao):
        super().__init__(timeout=300)
        self.tag_suggestions = tag_suggestions
        self.ticket_id = ticket_id
        self.ai_dao = ai_dao

        # 添加標籤選擇下拉選單
        if tag_suggestions:
            select = AITagSelect(tag_suggestions, ticket_id)
            self.add_item(select)

        # 添加應用所有建議按鈕
        apply_all_button = discord.ui.Button(
            label=f"應用全部 ({len(tag_suggestions)})",
            style=discord.ButtonStyle.success,
            custom_id="apply_all_tags",
            emoji="✅",
        )
        apply_all_button.callback = self._apply_all_callback
        self.add_item(apply_all_button)

        # 添加拒絕按鈕
        reject_button = discord.ui.Button(
            label="不採用",
            style=discord.ButtonStyle.danger,
            custom_id="reject_tags",
            emoji="❌",
        )
        reject_button.callback = self._reject_callback
        self.add_item(reject_button)

    async def _apply_all_callback(self, interaction: discord.Interaction):
        """應用所有標籤建議"""
        try:
            # 這裡需要實現標籤應用邏輯
            # 暫時模擬成功
            applied_tags = [tag["tag_name"] for tag in self.tag_suggestions]

            embed = discord.Embed(
                title="✅ 標籤已應用",
                description=f"已成功應用 {len(applied_tags)} 個標籤：\n"
                + ", ".join([f"`{tag}`" for tag in applied_tags]),
                color=0x28A745,
            )

            # 禁用所有按鈕
            for item in self.children:
                item.disabled = True

            await interaction.response.edit_message(embed=embed, view=self)

        except Exception as e:
            logger.error(f"應用標籤錯誤: {e}")
            await interaction.response.send_message(
                f"❌ 應用標籤時發生錯誤：{str(e)}", ephemeral=True
            )

    async def _reject_callback(self, interaction: discord.Interaction):
        """拒絕標籤建議"""
        embed = discord.Embed(
            title="❌ 已拒絕標籤建議",
            description="感謝您的回饋，我們會改進標籤建議的準確性。",
            color=0x6C757D,
        )

        # 禁用所有按鈕
        for item in self.children:
            item.disabled = True

        await interaction.response.edit_message(embed=embed, view=self)

    async def on_timeout(self):
        """處理超時"""
        for item in self.children:
            item.disabled = True


class AITagSelect(discord.ui.Select):
    """AI 標籤選擇下拉選單"""

    def __init__(self, tag_suggestions: List[Dict[str, Any]], ticket_id: int):
        self.ticket_id = ticket_id

        options = []
        for i, suggestion in enumerate(tag_suggestions[:10]):  # 最多10個選項
            options.append(
                discord.SelectOption(
                    label=suggestion["tag_name"],
                    description=f"{suggestion['reason']} ({suggestion['confidence']:.1%})",
                    value=str(i),
                    emoji="🏷️",
                )
            )

        super().__init__(
            placeholder="選擇要應用的標籤...",
            min_values=1,
            max_values=min(len(options), 5),  # 最多選5個
            options=options,
        )

        self.tag_suggestions = tag_suggestions

    async def callback(self, interaction: discord.Interaction):
        """標籤選擇回調"""
        try:
            selected_indices = [int(value) for value in self.values]
            selected_tags = [self.tag_suggestions[i] for i in selected_indices]

            # 這裡需要實現實際的標籤應用邏輯
            # 暫時模擬成功
            [tag["tag_name"] for tag in selected_tags]

            embed = discord.Embed(
                title="✅ 標籤已應用",
                description=f"已成功應用以下標籤：\n"
                + "\n".join(
                    [f"• `{tag['tag_name']}` ({tag['confidence']:.1%})" for tag in selected_tags]
                ),
                color=0x28A745,
            )

            await interaction.response.send_message(embed=embed, ephemeral=True)

        except Exception as e:
            logger.error(f"標籤選擇錯誤: {e}")
            await interaction.response.send_message(
                f"❌ 應用標籤時發生錯誤：{str(e)}", ephemeral=True
            )


class AIPriorityView(discord.ui.View):
    """AI 優先級評估結果界面"""

    def __init__(self, priority_result: Dict[str, Any], ticket_id: int):
        super().__init__(timeout=300)
        self.priority_result = priority_result
        self.ticket_id = ticket_id

        # 添加應用優先級按鈕
        priority = priority_result["suggested_priority"]
        apply_button = discord.ui.Button(
            label=f"應用優先級: {priority.upper()}",
            style=self._get_priority_style(priority),
            custom_id="apply_priority",
            emoji=self._get_priority_emoji(priority),
        )
        apply_button.callback = self._apply_priority_callback
        self.add_item(apply_button)

        # 添加查看詳細按鈮
        detail_button = discord.ui.Button(
            label="查看詳細分析",
            style=discord.ButtonStyle.secondary,
            custom_id="priority_detail",
            emoji="📊",
        )
        detail_button.callback = self._show_detail_callback
        self.add_item(detail_button)

    def _get_priority_style(self, priority: str) -> discord.ButtonStyle:
        """根據優先級返回按鈕樣式"""
        styles = {
            "low": discord.ButtonStyle.success,
            "medium": discord.ButtonStyle.primary,
            "high": discord.ButtonStyle.danger,
        }
        return styles.get(priority, discord.ButtonStyle.secondary)

    def _get_priority_emoji(self, priority: str) -> str:
        """根據優先級返回 Emoji"""
        emojis = {"low": "🟢", "medium": "🟡", "high": "🔴"}
        return emojis.get(priority, "⚪")

    async def _apply_priority_callback(self, interaction: discord.Interaction):
        """應用優先級"""
        try:
            priority = self.priority_result["suggested_priority"]

            # 這裡需要實現實際的優先級更新邏輯
            # 暫時模擬成功

            embed = discord.Embed(
                title="✅ 優先級已更新",
                description=f"票券優先級已更新為：{self._get_priority_emoji(priority)} **{priority.upper()}**",
                color=0x28A745,
            )

            embed.add_field(
                name="📊 AI 評估資訊",
                value=f"置信度: {self.priority_result['confidence']:.1%}\n"
                f"評分: {self.priority_result['score']:.1f}/4.0",
                inline=False,
            )

            # 禁用按鈕
            for item in self.children:
                item.disabled = True

            await interaction.response.edit_message(embed=embed, view=self)

        except Exception as e:
            logger.error(f"應用優先級錯誤: {e}")
            await interaction.response.send_message(
                f"❌ 更新優先級時發生錯誤：{str(e)}", ephemeral=True
            )

    async def _show_detail_callback(self, interaction: discord.Interaction):
        """顯示詳細分析"""
        embed = discord.Embed(title="📊 AI 優先級評估詳細分析", color=0xFF9500)

        analysis = self.priority_result.get("analysis", {})

        if analysis:
            embed.add_field(
                name="🔍 內容分析",
                value=f"類型: {analysis.get('type', '未知')}\n"
                f"情感: {analysis.get('sentiment', '中性')}\n"
                f"複雜度: {analysis.get('complexity', '中等')}\n"
                f"緊急度: {analysis.get('urgency_level', 1)}/3",
                inline=True,
            )

        if self.priority_result.get("adjustments"):
            embed.add_field(
                name="⚖️ 調整因子",
                value="\n".join([f"• {adj}" for adj in self.priority_result["adjustments"]]),
                inline=True,
            )

        embed.add_field(
            name="🎯 最終評估",
            value=f"建議優先級: **{self.priority_result['suggested_priority'].upper()}**\n"
            f"置信度: {self.priority_result['confidence']:.1%}\n"
            f"綜合評分: {self.priority_result['score']:.1f}/4.0",
            inline=False,
        )

        embed.set_footer(text="AI 評估僅供參考，請根據實際情況決定")

        await interaction.response.send_message(embed=embed, ephemeral=True)

    async def on_timeout(self):
        """處理超時"""
        for item in self.children:
            item.disabled = True


class AIFeedbackModal(discord.ui.Modal):
    """AI 建議回饋模態對話框"""

    def __init__(self, suggestion_id: int, ai_dao):
        super().__init__(title="AI 建議回饋")
        self.suggestion_id = suggestion_id
        self.ai_dao = ai_dao

        # 評分輸入
        self.rating_input = discord.ui.TextInput(
            label="評分 (1-5)",
            placeholder="1=很差, 2=差, 3=普通, 4=好, 5=很好",
            style=discord.TextStyle.short,
            max_length=1,
            required=True,
        )
        self.add_item(self.rating_input)

        # 評論輸入
        self.comment_input = discord.ui.TextInput(
            label="評論 (可選)",
            placeholder="請描述這個 AI 建議的優缺點...",
            style=discord.TextStyle.paragraph,
            max_length=500,
            required=False,
        )
        self.add_item(self.comment_input)

    async def on_submit(self, interaction: discord.Interaction):
        """提交回饋"""
        try:
            # 驗證評分
            try:
                rating = int(self.rating_input.value)
                if rating < 1 or rating > 5:
                    raise ValueError
            except ValueError:
                await interaction.response.send_message(
                    "❌ 評分必須是 1-5 之間的數字", ephemeral=True
                )
                return

            comment = self.comment_input.value.strip() or None

            # 更新回饋
            success = await self.ai_dao.update_suggestion_feedback(
                self.suggestion_id, True, rating, comment
            )

            if success:
                embed = discord.Embed(
                    title="✅ 回饋已提交",
                    description="感謝您的回饋！這將幫助我們改進 AI 建議的品質。",
                    color=0x28A745,
                )

                embed.add_field(name="您的評分", value=f"{rating}/5 ⭐", inline=True)

                if comment:
                    embed.add_field(
                        name="您的評論",
                        value=comment[:100] + ("..." if len(comment) > 100 else ""),
                        inline=False,
                    )
            else:
                embed = discord.Embed(
                    title="❌ 提交失敗",
                    description="提交回饋時發生錯誤，請稍後再試。",
                    color=0xDC3545,
                )

            await interaction.response.send_message(embed=embed, ephemeral=True)

        except Exception as e:
            logger.error(f"AI 回饋提交錯誤: {e}")
            await interaction.response.send_message(
                f"❌ 提交回饋時發生錯誤：{str(e)}", ephemeral=True
            )
