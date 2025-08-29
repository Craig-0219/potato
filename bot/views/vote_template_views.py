# bot/views/vote_template_views.py
"""
投票模板系統視圖組件
提供模板選擇、自定義、應用等UI功能
"""

from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional

import discord
from discord import ui

from bot.db import vote_dao
from bot.services.vote_template_manager import vote_template_manager
from bot.utils.embed_builder import EmbedBuilder
from bot.utils.vote_utils import build_vote_embed
from bot.views.vote_views import VoteButtonView
from shared.logger import logger


class TemplateSelectionView(ui.View):
    """模板選擇主視圖"""

    def __init__(self, user_id: int, guild_id: int):
        super().__init__(timeout=300)
        self.user_id = user_id
        self.guild_id = guild_id
        self._build_components()

    def _build_components(self):
        """構建UI組件"""
        # 模板類別選擇下拉選單
        self.add_item(TemplateCategorySelect())

        # 收藏模板按鈕
        self.add_item(FavoriteTemplatesButton())

        # 創建自定義模板按鈕
        self.add_item(CreateCustomTemplateButton())

    def create_embed(self) -> discord.Embed:
        """創建主要嵌入"""
        embed = EmbedBuilder.create_info_embed(
            "🗳️ 投票模板系統", "選擇一個模板來快速創建投票，或創建你自己的模板！"
        )

        embed.add_field(
            name="📋 如何使用",
            value=(
                "1. 從下拉選單選擇模板類別\n"
                "2. 選擇喜歡的模板\n"
                "3. 自定義標題和選項\n"
                "4. 創建投票！"
            ),
            inline=False,
        )

        embed.add_field(
            name="⭐ 模板類別",
            value=(
                "📊 民意調查 - 快速收集意見\n"
                "🗓️ 活動安排 - 時間選擇投票\n"
                "🍕 聚餐選擇 - 地點菜單投票\n"
                "⭐ 評分投票 - 滿意度調查\n"
                "🎮 遊戲選擇 - 遊戲投票\n"
                "🛠️ 自定義 - 創建專屬模板"
            ),
            inline=False,
        )

        embed.set_footer(text="💡 提示：收藏常用模板，下次使用更方便！")
        return embed


class TemplateCategorySelect(ui.Select):
    """模板類別選擇下拉選單"""

    def __init__(self):
        options = [
            discord.SelectOption(
                label="📊 民意調查",
                description="快速收集意見的投票模板",
                value="poll",
                emoji="📊",
            ),
            discord.SelectOption(
                label="🗓️ 活動安排",
                description="時間選擇和活動安排模板",
                value="schedule",
                emoji="🗓️",
            ),
            discord.SelectOption(
                label="🍕 聚餐選擇",
                description="地點、菜單選擇模板",
                value="food",
                emoji="🍕",
            ),
            discord.SelectOption(
                label="⭐ 評分投票",
                description="滿意度和評分調查模板",
                value="rating",
                emoji="⭐",
            ),
            discord.SelectOption(
                label="🎮 遊戲選擇",
                description="遊戲和娛樂相關模板",
                value="game",
                emoji="🎮",
            ),
            discord.SelectOption(
                label="🛠️ 自定義",
                description="用戶創建的自定義模板",
                value="custom",
                emoji="🛠️",
            ),
        ]

        super().__init__(
            placeholder="選擇模板類別...",
            options=options,
            custom_id="template_category_select",
        )

    async def callback(self, interaction: discord.Interaction):
        """處理類別選擇"""
        try:
            view: TemplateSelectionView = self.view
            category = self.values[0]

            # 取得該類別的模板
            templates = await vote_template_manager.get_templates_by_category(
                category, view.guild_id, view.user_id
            )

            if not templates:
                await interaction.response.send_message(
                    f"❌ 該類別目前沒有可用的模板", ephemeral=True
                )
                return

            # 顯示模板列表
            template_view = TemplateListView(templates, view.user_id, view.guild_id)
            embed = template_view.create_embed(category)

            await interaction.response.send_message(
                embed=embed, view=template_view, ephemeral=True
            )

        except Exception as e:
            logger.error(f"處理模板類別選擇失敗: {e}")
            await interaction.response.send_message(
                "❌ 載入模板時發生錯誤", ephemeral=True
            )


class FavoriteTemplatesButton(ui.Button):
    """收藏模板按鈕"""

    def __init__(self):
        super().__init__(
            label="⭐ 我的收藏", style=discord.ButtonStyle.secondary, emoji="⭐"
        )

    async def callback(self, interaction: discord.Interaction):
        """顯示收藏的模板"""
        try:
            view: TemplateSelectionView = self.view

            # 取得收藏模板
            from bot.db.vote_template_dao import vote_template_dao

            favorites = await vote_template_dao.get_user_favorite_templates(
                view.user_id, view.guild_id
            )

            if not favorites:
                await interaction.response.send_message(
                    "📭 你還沒有收藏任何模板\n💡 在模板詳情中點擊 ⭐ 可以收藏模板",
                    ephemeral=True,
                )
                return

            # 顯示收藏模板列表
            template_view = TemplateListView(favorites, view.user_id, view.guild_id)
            embed = template_view.create_embed("收藏")

            await interaction.response.send_message(
                embed=embed, view=template_view, ephemeral=True
            )

        except Exception as e:
            logger.error(f"載入收藏模板失敗: {e}")
            await interaction.response.send_message(
                "❌ 載入收藏模板時發生錯誤", ephemeral=True
            )


class CreateCustomTemplateButton(ui.Button):
    """創建自定義模板按鈕"""

    def __init__(self):
        super().__init__(
            label="🛠️ 創建模板", style=discord.ButtonStyle.success, emoji="🛠️"
        )

    async def callback(self, interaction: discord.Interaction):
        """顯示創建自定義模板的模態框"""
        try:
            modal = CreateCustomTemplateModal()
            await interaction.response.send_modal(modal)

        except Exception as e:
            logger.error(f"顯示創建模板模態框失敗: {e}")
            await interaction.response.send_message(
                "❌ 創建模板功能暫時無法使用", ephemeral=True
            )


class TemplateListView(ui.View):
    """模板列表視圖"""

    def __init__(self, templates: List[Dict], user_id: int, guild_id: int):
        super().__init__(timeout=300)
        self.templates = templates
        self.user_id = user_id
        self.guild_id = guild_id
        self.current_page = 0
        self.templates_per_page = 5
        self._build_components()

    def _build_components(self):
        """構建UI組件"""
        # 模板選擇下拉選單
        if self.templates:
            self.add_item(TemplateSelectMenu(self.get_current_templates()))

        # 分頁按鈕
        total_pages = (
            len(self.templates) + self.templates_per_page - 1
        ) // self.templates_per_page
        if total_pages > 1:
            self.add_item(PreviousPageButton(enabled=self.current_page > 0))
            self.add_item(NextPageButton(enabled=self.current_page < total_pages - 1))

    def get_current_templates(self) -> List[Dict]:
        """取得當前頁面的模板"""
        start = self.current_page * self.templates_per_page
        end = start + self.templates_per_page
        return self.templates[start:end]

    def create_embed(self, category: str) -> discord.Embed:
        """創建模板列表嵌入"""
        total_pages = (
            len(self.templates) + self.templates_per_page - 1
        ) // self.templates_per_page

        embed = EmbedBuilder.create_info_embed(
            f"📋 {category}模板列表", f"找到 {len(self.templates)} 個模板"
        )

        current_templates = self.get_current_templates()
        for template in current_templates:
            usage_text = f"使用 {template['usage_count']} 次"
            favorite_text = " ⭐" if template.get("is_favorited") else ""

            embed.add_field(
                name=f"{template['name']}{favorite_text}",
                value=f"{template.get('description', '無描述')}\n📊 {usage_text}",
                inline=False,
            )

        if total_pages > 1:
            embed.set_footer(text=f"第 {self.current_page + 1}/{total_pages} 頁")

        return embed


class TemplateSelectMenu(ui.Select):
    """模板選擇下拉選單"""

    def __init__(self, templates: List[Dict]):
        options = []
        for i, template in enumerate(templates):
            if i >= 25:  # Discord限制
                break

            description = template.get("description", "")[:100]  # 限制描述長度
            emoji = self._get_category_emoji(template["category"])

            options.append(
                discord.SelectOption(
                    label=template["name"][:100],  # 限制標籤長度
                    description=description,
                    value=str(template["id"]),
                    emoji=emoji,
                )
            )

        super().__init__(
            placeholder="選擇要使用的模板...",
            options=options,
            custom_id="template_select_menu",
        )

    def _get_category_emoji(self, category: str) -> str:
        """根據類別取得emoji"""
        emoji_map = {
            "poll": "📊",
            "schedule": "🗓️",
            "food": "🍕",
            "rating": "⭐",
            "game": "🎮",
            "custom": "🛠️",
        }
        return emoji_map.get(category, "📋")

    async def callback(self, interaction: discord.Interaction):
        """處理模板選擇"""
        try:
            template_id = int(self.values[0])

            # 顯示模板詳情和自定義選項
            detail_view = TemplateDetailView(
                template_id, interaction.user.id, interaction.guild.id
            )
            embed = await detail_view.create_embed()

            if embed:
                await interaction.response.send_message(
                    embed=embed, view=detail_view, ephemeral=True
                )
            else:
                await interaction.response.send_message(
                    "❌ 無法載入模板詳情", ephemeral=True
                )

        except Exception as e:
            logger.error(f"處理模板選擇失敗: {e}")
            await interaction.response.send_message(
                "❌ 載入模板時發生錯誤", ephemeral=True
            )


class PreviousPageButton(ui.Button):
    """上一頁按鈕"""

    def __init__(self, enabled: bool = True):
        super().__init__(
            label="⬅️ 上一頁", style=discord.ButtonStyle.secondary, disabled=not enabled
        )

    async def callback(self, interaction: discord.Interaction):
        """處理上一頁"""
        view: TemplateListView = self.view
        view.current_page -= 1

        # 重建視圖
        view.clear_items()
        view._build_components()

        embed = view.create_embed("模板")
        await interaction.response.edit_message(embed=embed, view=view)


class NextPageButton(ui.Button):
    """下一頁按鈕"""

    def __init__(self, enabled: bool = True):
        super().__init__(
            label="下一頁 ➡️", style=discord.ButtonStyle.secondary, disabled=not enabled
        )

    async def callback(self, interaction: discord.Interaction):
        """處理下一頁"""
        view: TemplateListView = self.view
        view.current_page += 1

        # 重建視圖
        view.clear_items()
        view._build_components()

        embed = view.create_embed("模板")
        await interaction.response.edit_message(embed=embed, view=view)


class TemplateDetailView(ui.View):
    """模板詳情視圖"""

    def __init__(self, template_id: int, user_id: int, guild_id: int):
        super().__init__(timeout=300)
        self.template_id = template_id
        self.user_id = user_id
        self.guild_id = guild_id

        # 添加使用模板按鈕
        self.add_item(UseTemplateButton(template_id))
        self.add_item(FavoriteToggleButton(template_id))

    async def create_embed(self) -> Optional[discord.Embed]:
        """創建模板詳情嵌入"""
        try:
            from bot.db.vote_template_dao import vote_template_dao

            template = await vote_template_dao.get_template_by_id(self.template_id)

            if not template:
                return None

            embed = EmbedBuilder.create_info_embed(
                f"📋 模板詳情：{template['name']}",
                template.get("description", "無描述"),
            )

            # 模板資訊
            category_emoji = self._get_category_emoji(template["category"])
            embed.add_field(
                name="📊 基本資訊",
                value=(
                    f"**類別**: {category_emoji} {template['category']}\n"
                    f"**使用次數**: {template['usage_count']}\n"
                    f"**預設時長**: {template['default_duration']} 分鐘\n"
                    f"**投票類型**: {'多選' if template['default_is_multi'] else '單選'}\n"
                    f"**匿名模式**: {'是' if template['default_anonymous'] else '否'}"
                ),
                inline=True,
            )

            # 標題模板
            embed.add_field(
                name="📝 標題模板",
                value=f"```{template['title_template']}```",
                inline=False,
            )

            # 選項模板
            options_text = "\n".join(
                [f"{i+1}. {opt}" for i, opt in enumerate(template["options_template"])]
            )
            embed.add_field(
                name="📋 選項模板", value=f"```{options_text}```", inline=False
            )

            # 標籤
            if template["tags"]:
                tags_text = " ".join([f"`{tag}`" for tag in template["tags"]])
                embed.add_field(name="🏷️ 標籤", value=tags_text, inline=False)

            embed.set_footer(text="💡 點擊「使用模板」開始創建投票")
            return embed

        except Exception as e:
            logger.error(f"創建模板詳情嵌入失敗: {e}")
            return None

    def _get_category_emoji(self, category: str) -> str:
        """根據類別取得emoji"""
        emoji_map = {
            "poll": "📊",
            "schedule": "🗓️",
            "food": "🍕",
            "rating": "⭐",
            "game": "🎮",
            "custom": "🛠️",
        }
        return emoji_map.get(category, "📋")


class UseTemplateButton(ui.Button):
    """使用模板按鈕"""

    def __init__(self, template_id: int):
        super().__init__(
            label="✅ 使用模板", style=discord.ButtonStyle.success, emoji="✅"
        )
        self.template_id = template_id

    async def callback(self, interaction: discord.Interaction):
        """處理使用模板"""
        try:
            # 顯示模板自定義模態框
            modal = TemplateCustomizationModal(self.template_id)
            await interaction.response.send_modal(modal)

        except Exception as e:
            logger.error(f"使用模板失敗: {e}")
            await interaction.response.send_message(
                "❌ 使用模板時發生錯誤", ephemeral=True
            )


class FavoriteToggleButton(ui.Button):
    """收藏切換按鈕"""

    def __init__(self, template_id: int):
        super().__init__(
            label="⭐ 收藏", style=discord.ButtonStyle.secondary, emoji="⭐"
        )
        self.template_id = template_id

    async def callback(self, interaction: discord.Interaction):
        """切換收藏狀態"""
        try:
            from bot.db.vote_template_dao import vote_template_dao

            # 嘗試加入收藏
            success = await vote_template_dao.add_template_favorite(
                self.template_id, interaction.user.id, interaction.guild.id
            )

            if success:
                self.label = "⭐ 已收藏"
                self.style = discord.ButtonStyle.success
                message = "✅ 已加入收藏"
            else:
                # 如果加入失敗，可能已經收藏了，嘗試移除
                success = await vote_template_dao.remove_template_favorite(
                    self.template_id, interaction.user.id
                )
                if success:
                    self.label = "⭐ 收藏"
                    self.style = discord.ButtonStyle.secondary
                    message = "❌ 已移除收藏"
                else:
                    message = "❌ 收藏操作失敗"

            await interaction.response.edit_message(view=self.view)
            await interaction.followup.send(message, ephemeral=True)

        except Exception as e:
            logger.error(f"切換收藏狀態失敗: {e}")
            await interaction.response.send_message(
                "❌ 收藏操作時發生錯誤", ephemeral=True
            )


class TemplateCustomizationModal(ui.Modal):
    """模板自定義模態框"""

    def __init__(self, template_id: int):
        super().__init__(title="🎨 自定義投票內容", timeout=300)
        self.template_id = template_id

        # 自定義變數輸入
        self.custom_vars = ui.TextInput(
            label="自定義變數（可選）",
            placeholder="例如：topic=環保議題,event_name=年終聚會",
            style=discord.TextStyle.short,
            required=False,
            max_length=200,
        )
        self.add_item(self.custom_vars)

        # 持續時間調整
        self.duration = ui.TextInput(
            label="投票持續時間（分鐘）",
            placeholder="預設使用模板設定，留空不修改",
            style=discord.TextStyle.short,
            required=False,
            max_length=4,
        )
        self.add_item(self.duration)

    async def on_submit(self, interaction: discord.Interaction):
        """處理模板應用"""
        try:
            # 解析自定義變數
            custom_values = {}
            if self.custom_vars.value:
                try:
                    for pair in self.custom_vars.value.split(","):
                        if "=" in pair:
                            key, value = pair.split("=", 1)
                            custom_values[key.strip()] = value.strip()
                except:
                    logger.warning(f"無法解析自定義變數: {self.custom_vars.value}")

            # 應用模板
            vote_config = await vote_template_manager.apply_template(
                self.template_id, custom_values
            )

            if not vote_config:
                await interaction.response.send_message(
                    "❌ 無法應用模板", ephemeral=True
                )
                return

            # 處理持續時間調整
            if self.duration.value:
                try:
                    custom_duration = int(self.duration.value)
                    if 1 <= custom_duration <= 10080:  # 1分鐘到1週
                        vote_config["duration"] = custom_duration
                except ValueError:
                    pass  # 忽略無效輸入，使用預設值

            await interaction.response.defer(ephemeral=True)

            # 創建投票
            start_time = datetime.now(timezone.utc)
            end_time = start_time + timedelta(minutes=vote_config["duration"])

            session_data = {
                "title": vote_config["title"],
                "options": vote_config["options"],
                "is_multi": vote_config["is_multi"],
                "anonymous": vote_config["anonymous"],
                "allowed_roles": [],
                "start_time": start_time,
                "end_time": end_time,
                "origin_channel": interaction.channel,
                "guild_id": interaction.guild.id,
            }

            # 創建投票
            vote_id = await vote_dao.create_vote(session_data, interaction.user.id)

            if vote_id:
                # 創建選項
                for option in vote_config["options"]:
                    await vote_dao.add_vote_option(vote_id, option)

                # 創建投票視圖
                vote_embed = build_vote_embed(
                    session_data["title"],
                    session_data["start_time"],
                    session_data["end_time"],
                    session_data["is_multi"],
                    session_data["anonymous"],
                    0,
                    vote_id=vote_id,
                )

                vote_view = VoteButtonView(
                    vote_id,
                    session_data["options"],
                    session_data["allowed_roles"],
                    session_data["is_multi"],
                    session_data["anonymous"],
                )

                # 發布投票
                await interaction.channel.send(embed=vote_embed, view=vote_view)

                await interaction.followup.send(
                    f"✅ 使用模板「{vote_config['template_name']}」成功創建投票！\n"
                    f"投票ID: {vote_id}",
                    ephemeral=True,
                )
            else:
                await interaction.followup.send(
                    "❌ 創建投票失敗，請稍後再試", ephemeral=True
                )

        except Exception as e:
            logger.error(f"模板應用失敗: {e}")
            if not interaction.response.is_done():
                await interaction.response.send_message(
                    "❌ 應用模板時發生錯誤", ephemeral=True
                )
            else:
                await interaction.followup.send("❌ 應用模板時發生錯誤", ephemeral=True)


class CreateCustomTemplateModal(ui.Modal):
    """創建自定義模板模態框"""

    def __init__(self):
        super().__init__(title="🛠️ 創建自定義模板", timeout=300)

        self.name = ui.TextInput(
            label="模板名稱",
            placeholder="例如：每週例會時間投票",
            max_length=100,
            required=True,
        )
        self.add_item(self.name)

        self.description = ui.TextInput(
            label="模板描述",
            placeholder="簡短描述這個模板的用途...",
            style=discord.TextStyle.paragraph,
            max_length=500,
            required=False,
        )
        self.add_item(self.description)

        self.title_template = ui.TextInput(
            label="標題模板",
            placeholder="例如：{week}週例會時間安排",
            max_length=200,
            required=True,
        )
        self.add_item(self.title_template)

        self.options_template = ui.TextInput(
            label="選項模板（用逗號分隔）",
            placeholder="選項1, 選項2, 選項3",
            style=discord.TextStyle.paragraph,
            max_length=500,
            required=True,
        )
        self.add_item(self.options_template)

    async def on_submit(self, interaction: discord.Interaction):
        """處理自定義模板創建"""
        try:
            # 解析選項
            options = [
                opt.strip()
                for opt in self.options_template.value.split(",")
                if opt.strip()
            ]

            if len(options) < 2:
                await interaction.response.send_message(
                    "❌ 至少需要2個選項", ephemeral=True
                )
                return

            # 準備模板數據
            template_data = {
                "name": self.name.value,
                "description": self.description.value or None,
                "category": "custom",
                "guild_id": interaction.guild.id,
                "creator_id": interaction.user.id,
                "is_public": False,
                "title_template": self.title_template.value,
                "options_template": options,
                "default_duration": 60,
                "default_is_multi": False,
                "default_anonymous": False,
            }

            # 創建模板
            template_id = await vote_template_manager.create_custom_template(
                template_data
            )

            if template_id:
                await interaction.response.send_message(
                    f"✅ 成功創建自定義模板「{self.name.value}」！\n"
                    f"模板ID: {template_id}\n"
                    f"你可以在自定義類別中找到這個模板。",
                    ephemeral=True,
                )
            else:
                await interaction.response.send_message(
                    "❌ 創建模板失敗，請稍後再試", ephemeral=True
                )

        except Exception as e:
            logger.error(f"創建自定義模板失敗: {e}")
            await interaction.response.send_message(
                "❌ 創建模板時發生錯誤", ephemeral=True
            )
