# bot/views/vote_views_consolidated.py
"""
統一的投票系統視圖模組
整合所有投票相關的 UI 組件
"""

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List

import discord
from discord import ui

from potato_bot.db import vote_dao
from potato_bot.utils.embed_builder import EmbedBuilder
from potato_shared.logger import logger

# ============ 基礎投票 UI 組件 ============


class VoteButtonView(discord.ui.View):
    """基礎投票按鈕視圖 - 用於用戶投票互動"""

    def __init__(
        self,
        vote_id,
        options,
        allowed_roles,
        is_multi,
        anonymous,
        stats=None,
        total=0,
    ):
        super().__init__(timeout=None)
        self.vote_id = vote_id
        self.options = options
        self.allowed_roles = allowed_roles or []
        self.is_multi = is_multi
        self.anonymous = anonymous
        self.stats = stats or {}
        self.total = total

        # 動態生成投票按鈕
        self._add_vote_buttons()

    def _add_vote_buttons(self):
        """添加投票選項按鈕"""
        if self.is_multi:
            self.add_item(MultiSelectVoteMenu(self.vote_id, self.options, self.stats, self.total))
            return

        for i, option in enumerate(self.options):
            if i < 25:
                count = self.stats.get(option, 0)
                percentage = (count / self.total * 100) if self.total > 0 else 0
                button = SingleSelectVoteButton(
                    option=option,
                    option_index=i,
                    vote_id=self.vote_id,
                    anonymous=self.anonymous,
                    count=count,
                    percentage=percentage,
                )
                self.add_item(button)


class SingleSelectVoteButton(discord.ui.Button):
    """單選投票按鈕"""

    def __init__(
        self,
        option: str,
        option_index: int,
        vote_id: int,
        anonymous: bool,
        count: int = 0,
        percentage: float = 0,
    ):
        # 限制標籤長度並添加百分比顯示
        base_label = option[:15] + "..." if len(option) > 15 else option
        label = f"{base_label} ({percentage:.1f}%)" if count > 0 else base_label

        super().__init__(
            label=label,
            style=discord.ButtonStyle.primary,
            custom_id=f"single_vote_{vote_id}_{option_index}",
        )

        self.option = option
        self.option_index = option_index
        self.vote_id = vote_id
        self.anonymous = anonymous
        self.count = count
        self.percentage = percentage

    async def callback(self, interaction: discord.Interaction):
        """處理單選投票按鈕點擊"""
        try:
            cog = interaction.client.get_cog("VoteCore")
            if cog:
                await cog.handle_vote_submit(interaction, self.vote_id, [self.option])
            else:
                await interaction.response.send_message("❌ 投票系統暫時無法使用", ephemeral=True)

        except Exception as e:
            logger.error(f"單選投票按鈕回調失敗: {e}")
            await interaction.response.send_message("❌ 投票時發生錯誤", ephemeral=True)

class MultiSelectVoteMenu(discord.ui.Select):
    """多選投票選單（避免跨使用者共享狀態）"""

    def __init__(self, vote_id: int, options: List[str], stats: dict, total: int):
        self.vote_id = vote_id
        self._options = list(options)
        select_options = []

        for index, option in enumerate(self._options):
            count = stats.get(option, 0) if stats else 0
            percentage = (count / total * 100) if total > 0 else 0
            label = option if len(option) <= 80 else f"{option[:77]}..."
            description = f"{count} 票 ({percentage:.1f}%)"
            select_options.append(
                discord.SelectOption(
                    label=label,
                    value=str(index),
                    description=description,
                )
            )

        super().__init__(
            placeholder="選擇投票選項（可多選）",
            min_values=1,
            max_values=min(len(select_options), 25),
            options=select_options,
            custom_id=f"multi_vote_select_{vote_id}",
        )

    async def callback(self, interaction: discord.Interaction):
        """處理多選投票"""
        try:
            selected_options = []
            for value in self.values:
                if value.isdigit():
                    index = int(value)
                    if 0 <= index < len(self._options):
                        selected_options.append(self._options[index])

            if not selected_options:
                await interaction.response.send_message("❌ 請至少選擇一個選項", ephemeral=True)
                return

            cog = interaction.client.get_cog("VoteCore")
            if cog:
                await cog.handle_vote_submit(interaction, self.vote_id, selected_options)
            else:
                await interaction.response.send_message("❌ 投票系統暫時無法使用", ephemeral=True)

        except Exception as e:
            logger.error(f"多選投票選單回調失敗: {e}")
            await interaction.response.send_message("❌ 投票時發生錯誤", ephemeral=True)


class VoteButton(discord.ui.Button):
    """舊版投票選項按鈕 - 保持向後相容性"""

    def __init__(
        self,
        option: str,
        option_index: int,
        vote_id: int,
        is_multi: bool,
        anonymous: bool,
    ):
        # 限制標籤長度
        label = option[:20] + "..." if len(option) > 20 else option

        super().__init__(
            label=label,
            style=discord.ButtonStyle.primary,
            custom_id=f"vote_{vote_id}_{option_index}",
        )

        self.option = option
        self.option_index = option_index
        self.vote_id = vote_id
        self.is_multi = is_multi
        self.anonymous = anonymous

    async def callback(self, interaction: discord.Interaction):
        """處理投票按鈕點擊"""
        try:
            # 檢查是否已投票
            if await vote_dao.has_voted(self.vote_id, interaction.user.id):
                await interaction.response.send_message("❌ 您已經投過票了", ephemeral=True)
                return

            # 記錄投票

            cog = interaction.client.get_cog("VoteCore")
            if cog:
                await cog.handle_vote_submit(interaction, self.vote_id, [self.option])
            else:
                await interaction.response.send_message("❌ 投票系統暫時無法使用", ephemeral=True)

        except Exception as e:
            logger.error(f"投票按鈕回調失敗: {e}")
            await interaction.response.send_message("❌ 投票時發生錯誤", ephemeral=True)


class VoteSubmitButton(discord.ui.Button):
    """投票提交按鈕 - 用於多選投票"""

    def __init__(self, vote_id: int, selected_options: List[str]):
        super().__init__(label="提交投票", style=discord.ButtonStyle.success, emoji="✅")
        self.vote_id = vote_id
        self.selected_options = selected_options

    async def callback(self, interaction: discord.Interaction):
        """處理投票提交"""
        try:
            pass

            cog = interaction.client.get_cog("VoteCore")
            if cog:
                await cog.handle_vote_submit(interaction, self.vote_id, self.selected_options)
            else:
                await interaction.response.send_message("❌ 投票系統暫時無法使用", ephemeral=True)
        except Exception as e:
            logger.error(f"投票提交失敗: {e}")
            await interaction.response.send_message("❌ 投票提交時發生錯誤", ephemeral=True)


# ============ 現代化投票創建 UI ============


class ComprehensiveVoteModal(ui.Modal):
    """完整的投票創建模態框"""

    def __init__(self):
        super().__init__(title="🗳️ 創建投票", timeout=300)

        # 投票標題
        self.title_input = ui.TextInput(
            label="投票標題",
            placeholder="例：今晚聚餐地點投票",
            max_length=100,
            required=True,
        )
        self.add_item(self.title_input)

        # 投票選項
        self.options_input = ui.TextInput(
            label="投票選項 (用逗號分隔)",
            placeholder="選項1, 選項2, 選項3",
            style=discord.TextStyle.paragraph,
            max_length=500,
            required=True,
        )
        self.add_item(self.options_input)

        # 持續時間
        self.duration_input = ui.TextInput(
            label="持續時間 (分鐘)",
            placeholder="60",
            default="60",
            max_length=4,
            required=True,
        )
        self.add_item(self.duration_input)

    async def on_submit(self, interaction: discord.Interaction):
        """處理完整投票創建 - 顯示配置選項"""
        try:
            # 解析選項
            options = [opt.strip() for opt in self.options_input.value.split(",") if opt.strip()]

            if len(options) < 2:
                await interaction.response.send_message("❌ 至少需要2個選項", ephemeral=True)
                return

            if len(options) > 10:
                await interaction.response.send_message("❌ 最多只能有10個選項", ephemeral=True)
                return

            # 驗證持續時間
            try:
                duration = int(self.duration_input.value)
                if duration < 1 or duration > 10080:  # 最多一週
                    await interaction.response.send_message(
                        "❌ 持續時間必須在1-10080分鐘之間", ephemeral=True
                    )
                    return
            except ValueError:
                await interaction.response.send_message("❌ 持續時間必須是數字", ephemeral=True)
                return

            # 創建投票配置
            vote_config = {
                "title": self.title_input.value,
                "options": options,
                "duration_minutes": duration,
                "creator_id": interaction.user.id,
                "guild_id": interaction.guild.id,
                "channel_id": interaction.channel.id,
            }

            # 顯示配置選項視圖
            config_view = VoteConfigurationView(vote_config)
            embed = self._create_preview_embed(vote_config)

            await interaction.response.send_message(embed=embed, view=config_view, ephemeral=True)

        except Exception as e:
            logger.error(f"完整投票創建失敗: {e}")
            if not interaction.response.is_done():
                await interaction.response.send_message("❌ 創建投票時發生錯誤", ephemeral=True)
            else:
                await interaction.followup.send("❌ 創建投票時發生錯誤", ephemeral=True)

    def _create_preview_embed(self, config: Dict[str, Any]) -> discord.Embed:
        """創建預覽嵌入"""
        embed = EmbedBuilder.create_info_embed(
            "🗳️ 投票配置",
            f"**標題**: {config['title']}\n" f"**持續時間**: {config['duration_minutes']} 分鐘",
        )

        options_text = "\n".join(f"{i+1}. {opt}" for i, opt in enumerate(config["options"]))
        embed.add_field(name="📋 選項列表", value=options_text, inline=False)

        embed.add_field(
            name="⚙️ 接下來",
            value="請使用下方的選項來配置投票設定",
            inline=False,
        )

        embed.set_footer(text="配置完成後點擊「創建投票」")
        return embed


class QuickVoteModal(ui.Modal):
    """快速投票創建模態框"""

    def __init__(self):
        super().__init__(title="🗳️ 快速創建投票", timeout=300)

        # 投票標題
        self.title_input = ui.TextInput(
            label="投票標題",
            placeholder="例：今晚聚餐地點投票",
            max_length=100,
            required=True,
        )
        self.add_item(self.title_input)

        # 投票選項
        self.options_input = ui.TextInput(
            label="投票選項 (用逗號分隔)",
            placeholder="選項1, 選項2, 選項3",
            style=discord.TextStyle.paragraph,
            max_length=500,
            required=True,
        )
        self.add_item(self.options_input)

        # 持續時間
        self.duration_input = ui.TextInput(
            label="持續時間 (分鐘)",
            placeholder="60",
            default="60",
            max_length=4,
            required=True,
        )
        self.add_item(self.duration_input)

    async def on_submit(self, interaction: discord.Interaction):
        """處理快速投票創建"""
        try:
            # 解析選項
            options = [opt.strip() for opt in self.options_input.value.split(",") if opt.strip()]

            if len(options) < 2:
                await interaction.response.send_message("❌ 至少需要2個選項", ephemeral=True)
                return

            if len(options) > 10:
                await interaction.response.send_message("❌ 最多只能有10個選項", ephemeral=True)
                return

            # 驗證持續時間
            try:
                duration = int(self.duration_input.value)
                if duration < 1 or duration > 10080:  # 最多一週
                    await interaction.response.send_message(
                        "❌ 持續時間必須在1-10080分鐘之間", ephemeral=True
                    )
                    return
            except ValueError:
                await interaction.response.send_message("❌ 持續時間必須是數字", ephemeral=True)
                return

            await interaction.response.defer()

            # 創建投票配置
            vote_config = {
                "title": self.title_input.value,
                "options": options,
                "is_multi": False,  # 快速投票預設單選
                "anonymous": False,  # 快速投票預設公開
                "duration_minutes": duration,
                "allowed_roles": [],  # 快速投票預設所有人可投
                "creator_id": interaction.user.id,
                "guild_id": interaction.guild.id,
                "channel_id": interaction.channel.id,
            }

            # 顯示確認視圖
            confirm_view = VoteCreationConfirmView(vote_config)
            embed = self._create_preview_embed(vote_config)

            await interaction.followup.send(embed=embed, view=confirm_view, ephemeral=True)

        except Exception as e:
            logger.error(f"快速投票創建失敗: {e}")
            if not interaction.response.is_done():
                await interaction.response.send_message("❌ 創建投票時發生錯誤", ephemeral=True)
            else:
                await interaction.followup.send("❌ 創建投票時發生錯誤", ephemeral=True)

    def _create_preview_embed(self, config: Dict[str, Any]) -> discord.Embed:
        """創建預覽嵌入"""
        embed = EmbedBuilder.create_info_embed(
            "🗳️ 投票預覽",
            f"**標題**: {config['title']}\n"
            f"**持續時間**: {config['duration_minutes']} 分鐘\n"
            f"**投票類型**: {'多選' if config['is_multi'] else '單選'}\n"
            f"**匿名**: {'是' if config['anonymous'] else '否'}",
        )

        options_text = "\n".join(f"{i+1}. {opt}" for i, opt in enumerate(config["options"]))
        embed.add_field(name="📋 選項列表", value=options_text, inline=False)

        embed.set_footer(text="請確認設定後點擊「創建投票」")
        return embed


class VoteConfigurationView(ui.View):
    """投票配置視圖 - 包含單選/多選和匿名選項"""

    def __init__(self, vote_config: Dict[str, Any]):
        super().__init__(timeout=180)
        self.vote_config = vote_config
        self.is_multi = False  # 預設單選
        self.anonymous = False  # 預設公開
        self._build_components()

    def _build_components(self):
        """構建UI組件"""
        # 第一行：投票類型選擇
        self.add_item(VoteTypeSelectMenu())

        # 第二行：匿名選項
        self.add_item(AnonymityToggleButton(self.anonymous))

        # 第三行：確認和取消按鈕
        self.add_item(CreateVoteButton())
        self.add_item(CancelConfigButton())

    def update_embed(self, interaction: discord.Interaction):
        """更新嵌入以顯示當前配置"""
        embed = EmbedBuilder.create_info_embed(
            "🗳️ 投票配置",
            f"**標題**: {self.vote_config['title']}\n"
            f"**持續時間**: {self.vote_config['duration_minutes']} 分鐘",
        )

        options_text = "\n".join(
            f"{i+1}. {opt}" for i, opt in enumerate(self.vote_config["options"])
        )
        embed.add_field(name="📋 選項列表", value=options_text, inline=False)

        # 顯示當前配置
        config_text = (
            f"**投票類型**: {'多選投票' if self.is_multi else '單選投票'}\n"
            f"**匿名設定**: {'匿名投票' if self.anonymous else '公開投票'}"
        )
        embed.add_field(name="⚙️ 當前配置", value=config_text, inline=False)

        embed.set_footer(text="配置完成後點擊「✅ 創建投票」")
        return embed


class VoteTypeSelectMenu(ui.Select):
    """投票類型選擇下拉選單"""

    def __init__(self):
        options = [
            discord.SelectOption(
                label="單選投票",
                description="每人只能選擇一個選項",
                emoji="1️⃣",
                value="single",
            ),
            discord.SelectOption(
                label="多選投票",
                description="每人可以選擇多個選項",
                emoji="🔢",
                value="multi",
            ),
        ]

        super().__init__(
            placeholder="選擇投票類型...",
            min_values=1,
            max_values=1,
            options=options,
            custom_id="vote_type_select",
        )

    async def callback(self, interaction: discord.Interaction):
        """處理投票類型選擇"""
        view: VoteConfigurationView = self.view
        view.is_multi = self.values[0] == "multi"

        # 更新匿名按鈕狀態
        for item in view.children:
            if isinstance(item, AnonymityToggleButton):
                item.label = "🔒 匿名投票" if view.anonymous else "👁️ 公開投票"
                break

        embed = view.update_embed(interaction)
        await interaction.response.edit_message(embed=embed, view=view)


class AnonymityToggleButton(ui.Button):
    """匿名選項切換按鈕"""

    def __init__(self, anonymous: bool):
        super().__init__(
            label="👁️ 公開投票" if not anonymous else "🔒 匿名投票",
            style=discord.ButtonStyle.secondary,
            custom_id="anonymity_toggle",
        )
        self.anonymous = anonymous

    async def callback(self, interaction: discord.Interaction):
        """切換匿名選項"""
        view: VoteConfigurationView = self.view
        view.anonymous = not view.anonymous

        # 更新按鈕標籤
        self.label = "🔒 匿名投票" if view.anonymous else "👁️ 公開投票"

        embed = view.update_embed(interaction)
        await interaction.response.edit_message(embed=embed, view=view)


class CreateVoteButton(ui.Button):
    """創建投票按鈕"""

    def __init__(self):
        super().__init__(
            label="創建投票",
            style=discord.ButtonStyle.success,
            emoji="✅",
            custom_id="create_vote",
        )

    async def callback(self, interaction: discord.Interaction):
        """創建投票"""
        view: VoteConfigurationView = self.view

        try:
            await interaction.response.defer(ephemeral=True)

            # 準備會話數據
            start_time = datetime.now(timezone.utc)
            end_time = start_time + timedelta(minutes=view.vote_config["duration_minutes"])

            session_data = {
                "title": view.vote_config["title"],
                "options": view.vote_config["options"],
                "is_multi": view.is_multi,
                "anonymous": view.anonymous,
                "allowed_roles": [],  # 預設所有人可投
                "start_time": start_time,
                "end_time": end_time,
                "origin_channel": interaction.channel,
                "guild_id": view.vote_config["guild_id"],
            }

            # 創建投票
            vote_id = await vote_dao.create_vote(session_data, view.vote_config["creator_id"])

            if vote_id:
                # 創建投票選項
                for option in view.vote_config["options"]:
                    await vote_dao.add_vote_option(vote_id, option)

                # 創建投票視圖
                from potato_bot.utils.vote_utils import build_vote_embed

                empty_stats = {opt: 0 for opt in session_data["options"]}
                vote_embed = build_vote_embed(
                    session_data["title"],
                    session_data["start_time"],
                    session_data["end_time"],
                    session_data["is_multi"],
                    session_data["anonymous"],
                    0,
                    vote_id=vote_id,
                    stats=empty_stats,
                    participants=0,
                )

                vote_view = VoteButtonView(
                    vote_id,
                    session_data["options"],
                    session_data["allowed_roles"],
                    session_data["is_multi"],
                    session_data["anonymous"],
                    empty_stats,
                    0,
                )

                # 發布投票
                await interaction.channel.send(embed=vote_embed, view=vote_view)

                await interaction.followup.send(
                    f"✅ 投票已成功創建！投票ID: {vote_id}", ephemeral=True
                )

                # 禁用所有按鈕
                for item in view.children:
                    item.disabled = True
                await interaction.edit_original_response(view=view)
            else:
                await interaction.followup.send("❌ 創建投票失敗，請稍後再試", ephemeral=True)

        except Exception as e:
            logger.error(f"創建投票失敗: {e}")
            await interaction.followup.send("❌ 創建投票時發生錯誤", ephemeral=True)


class CancelConfigButton(ui.Button):
    """取消配置按鈕"""

    def __init__(self):
        super().__init__(
            label="取消",
            style=discord.ButtonStyle.danger,
            emoji="❌",
            custom_id="cancel_config",
        )

    async def callback(self, interaction: discord.Interaction):
        """取消配置"""
        await interaction.response.send_message("❌ 已取消投票創建", ephemeral=True)
        for item in self.view.children:
            item.disabled = True
        await interaction.edit_original_response(view=self.view)


class VoteCreationConfirmView(ui.View):
    """投票創建確認視圖"""

    def __init__(self, vote_config: Dict[str, Any]):
        super().__init__(timeout=120)
        self.vote_config = vote_config

    @ui.button(label="創建投票", style=discord.ButtonStyle.green, emoji="✅")
    async def confirm_creation(self, interaction: discord.Interaction, button: ui.Button):
        """確認創建投票"""
        try:
            await interaction.response.defer(ephemeral=True)

            # 準備會話數據
            start_time = datetime.now(timezone.utc)
            end_time = start_time + timedelta(minutes=self.vote_config["duration_minutes"])

            session_data = {
                "title": self.vote_config["title"],
                "options": self.vote_config["options"],
                "is_multi": self.vote_config["is_multi"],
                "anonymous": self.vote_config["anonymous"],
                "allowed_roles": self.vote_config["allowed_roles"],
                "start_time": start_time,
                "end_time": end_time,
                "origin_channel": interaction.channel,
                "guild_id": self.vote_config["guild_id"],
            }

            # 創建投票
            vote_id = await vote_dao.create_vote(session_data, self.vote_config["creator_id"])

            if vote_id:
                # 創建投票選項
                for option in self.vote_config["options"]:
                    await vote_dao.add_vote_option(vote_id, option)

                # 創建投票視圖
                from potato_bot.utils.vote_utils import build_vote_embed

                empty_stats = {opt: 0 for opt in self.vote_config["options"]}
                vote_embed = build_vote_embed(
                    session_data["title"],
                    session_data["start_time"],
                    session_data["end_time"],
                    session_data["is_multi"],
                    session_data["anonymous"],
                    0,
                    vote_id=vote_id,
                    stats=empty_stats,
                    participants=0,
                )

                vote_view = VoteButtonView(
                    vote_id,
                    session_data["options"],
                    session_data["allowed_roles"],
                    session_data["is_multi"],
                    session_data["anonymous"],
                    empty_stats,
                    0,
                )

                # 發布投票
                await interaction.channel.send(embed=vote_embed, view=vote_view)

                await interaction.followup.send(
                    f"✅ 投票已成功創建！投票ID: {vote_id}", ephemeral=True
                )

                # 禁用確認按鈕
                for item in self.children:
                    item.disabled = True
                await interaction.edit_original_response(view=self)
            else:
                await interaction.followup.send("❌ 創建投票失敗，請稍後再試", ephemeral=True)

        except Exception as e:
            logger.error(f"確認創建投票失敗: {e}")
            await interaction.followup.send("❌ 創建投票時發生錯誤", ephemeral=True)

    @ui.button(label="取消", style=discord.ButtonStyle.grey, emoji="❌")
    async def cancel_creation(self, interaction: discord.Interaction, button: ui.Button):
        """取消創建"""
        await interaction.response.send_message("❌ 已取消創建投票", ephemeral=True)
        for item in self.children:
            item.disabled = True
        await interaction.edit_original_response(view=self)


# ============ 投票管理面板 ============


class VoteManagementView(ui.View):
    """簡化的投票管理視圖 - 用於基本管理功能"""

    def __init__(self):
        super().__init__(timeout=300)

    @ui.button(label="創建投票", style=discord.ButtonStyle.primary, emoji="🗳️", row=0)
    async def create_vote(self, interaction: discord.Interaction, button: ui.Button):
        """創建新投票"""
        try:
            modal = ComprehensiveVoteModal()
            await interaction.response.send_modal(modal)
        except Exception as e:
            logger.error(f"創建投票按鈕錯誤: {e}")
            await interaction.response.send_message("❌ 創建投票時發生錯誤", ephemeral=True)

    @ui.button(
        label="查看統計",
        style=discord.ButtonStyle.secondary,
        emoji="📊",
        row=0,
    )
    async def view_stats(self, interaction: discord.Interaction, button: ui.Button):
        """查看投票統計"""
        try:
            guild = interaction.guild
            if not guild:
                await interaction.response.send_message("❌ 僅能在伺服器中使用。", ephemeral=True)
                return

            # 獲取當前進行中的投票
            votes = await vote_dao.get_active_votes(guild.id)

            if not votes:
                await interaction.response.send_message("📭 目前沒有進行中的投票", ephemeral=True)
                return

            embed = EmbedBuilder.create_info_embed(
                "📊 進行中的投票", f"目前有 {len(votes)} 個進行中的投票"
            )

            for vote in votes[:5]:  # 只顯示前5個
                stats = await vote_dao.get_vote_statistics(vote["id"])
                total_votes = sum(stats.values())

                embed.add_field(
                    name=f"#{vote['id']} - {vote['title'][:30]}{'...' if len(vote['title']) > 30 else ''}",
                    value=f"🗳 總票數: {total_votes}\n⏱ 結束: <t:{int(vote['end_time'].timestamp())}:R>",
                    inline=False,
                )

            await interaction.response.send_message(embed=embed, ephemeral=True)

        except Exception as e:
            logger.error(f"查看統計錯誤: {e}")
            await interaction.response.send_message("❌ 查看統計時發生錯誤", ephemeral=True)


class VoteManagementPanelView(ui.View):
    """完整的投票系統管理面板"""

    def __init__(self, guild_id: int, user_permissions: discord.Permissions):
        super().__init__(timeout=300)
        self.guild_id = guild_id
        self.permissions = user_permissions
        self._build_panel()

    def _build_panel(self):
        """根據權限構建管理面板"""
        # 基礎功能（所有人可用）
        self.add_item(ActiveVotesButton(self.guild_id))
        self.add_item(VoteHistoryButton(self.guild_id))

        # 管理員功能
        if self.permissions.manage_guild:
            self.add_item(VoteAnalyticsButton(self.guild_id))
            self.add_item(ExportDataButton(self.guild_id))


class ActiveVotesButton(ui.Button):
    """查看活動投票按鈕"""

    def __init__(self, guild_id: int):
        super().__init__(
            label="活動投票",
            style=discord.ButtonStyle.primary,
            emoji="🗳️",
            row=0,
        )
        self.guild_id = guild_id

    async def callback(self, interaction: discord.Interaction):
        """顯示活動投票列表"""
        await interaction.response.defer(ephemeral=True)

        try:
            # 獲取活動投票
            active_votes = await vote_dao.get_active_votes(self.guild_id)

            if not active_votes:
                embed = EmbedBuilder.create_info_embed("🗳️ 活動投票", "目前沒有進行中的投票")
                await interaction.followup.send(embed=embed, ephemeral=True)
                return

            embed = EmbedBuilder.create_info_embed(
                "🗳️ 活動投票列表", f"目前有 {len(active_votes)} 個進行中的投票"
            )

            for vote in active_votes[:10]:  # 限制顯示數量
                stats = await vote_dao.get_vote_statistics(vote["id"])
                total_votes = sum(stats.values())

                embed.add_field(
                    name=f"#{vote['id']} - {vote['title'][:40]}",
                    value=f"🗳 總票數: {total_votes}\n⏱ 結束: <t:{int(vote['end_time'].timestamp())}:R>",
                    inline=True,
                )

            await interaction.followup.send(embed=embed, ephemeral=True)

        except Exception as e:
            logger.error(f"獲取活動投票失敗: {e}")
            await interaction.followup.send("❌ 獲取活動投票時發生錯誤", ephemeral=True)


class VoteHistoryButton(ui.Button):
    """投票歷史按鈕"""

    def __init__(self, guild_id: int):
        super().__init__(
            label="投票歷史",
            style=discord.ButtonStyle.secondary,
            emoji="📋",
            row=0,
        )
        self.guild_id = guild_id

    async def callback(self, interaction: discord.Interaction):
        """顯示投票歷史"""
        await interaction.response.defer(ephemeral=True)

        try:
            # 獲取最近的投票歷史
            history = await vote_dao.get_vote_history(1, "all", guild_id=self.guild_id)

            if not history:
                embed = EmbedBuilder.create_info_embed("📋 投票歷史", "沒有找到投票歷史記錄")
                await interaction.followup.send(embed=embed, ephemeral=True)
                return

            embed = EmbedBuilder.create_info_embed(
                "📋 投票歷史", f"顯示最近 {len(history)} 筆投票記錄"
            )

            for vote in history:
                is_active = vote["end_time"] > datetime.now(timezone.utc)
                status = "🟢 進行中" if is_active else "🔴 已結束"

                embed.add_field(
                    name=f"#{vote['id']} - {vote['title'][:30]}",
                    value=f"{status}\n📅 開始: {vote['start_time'].strftime('%m/%d %H:%M')}",
                    inline=True,
                )

            await interaction.followup.send(embed=embed, ephemeral=True)

        except Exception as e:
            logger.error(f"獲取投票歷史失敗: {e}")
            await interaction.followup.send("❌ 獲取投票歷史時發生錯誤", ephemeral=True)


class VoteAnalyticsButton(ui.Button):
    """投票分析按鈕"""

    def __init__(self, guild_id: int):
        super().__init__(
            label="數據分析",
            style=discord.ButtonStyle.secondary,
            emoji="📈",
            row=1,
        )
        self.guild_id = guild_id

    async def callback(self, interaction: discord.Interaction):
        """顯示投票分析"""
        await interaction.response.send_message("📈 數據分析功能開發中...", ephemeral=True)


class ExportDataButton(ui.Button):
    """資料匯出按鈕"""

    def __init__(self, guild_id: int):
        super().__init__(
            label="匯出資料",
            style=discord.ButtonStyle.secondary,
            emoji="📥",
            row=1,
        )
        self.guild_id = guild_id

    async def callback(self, interaction: discord.Interaction):
        """匯出投票資料"""
        await interaction.response.send_message("📥 資料匯出功能開發中...", ephemeral=True)
