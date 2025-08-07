# vote_views.py - v5.1（支援即時更新統計視覺化 + 完整互動模組）

import discord
from discord.utils import MISSING
from shared.logger import logger

# ✅ 投票主互動 UI
class VoteButtonView(discord.ui.View):
    def __init__(self, vote_id, options, allowed_roles, is_multi, anonymous, stats=None, total_votes=0):
        super().__init__(timeout=None)
        self.vote_id = vote_id
        self.options = options  # ✅ 保存原始選項列表
        self.allowed_roles = allowed_roles
        self.is_multi = is_multi
        self.anonymous = anonymous
        self.stats = stats or {}
        self.total_votes = total_votes
        self.selection = []  # 多選時暫存使用者選擇

        if is_multi:
            self.add_item(MultiChoiceSelect(vote_id, options, allowed_roles))
            self.add_item(ClearSelectionButton(vote_id))
            self.add_item(VoteSubmitButton(vote_id))
        else:
            for i, opt in enumerate(options):
                label = self._format_option_label(opt)
                self.add_item(VoteButton(label=label, vote_id=vote_id, opt=opt, option_index=i))

    def _format_option_label(self, option):
        """格式化選項標籤，移除進度條"""
        count = self.stats.get(option, 0)
        percent = (count / self.total_votes * 100) if self.total_votes else 0
        return f"{option} | {count} 票 ({percent:.1f}%)"

    async def refresh(self, interaction: discord.Interaction):
        """重新載入按鈕 UI 內容（票數與百分比）"""
        from bot.db import vote_dao
        stats = await vote_dao.get_vote_statistics(self.vote_id)
        total = sum(stats.values())
        self.clear_items()
        self.stats = stats
        self.total_votes = total

        if self.is_multi:
            # ✅ 使用原始選項列表而不是 stats.keys()
            self.add_item(MultiChoiceSelect(self.vote_id, self.options, self.allowed_roles))
            self.add_item(ClearSelectionButton(self.vote_id))
            self.add_item(VoteSubmitButton(self.vote_id))
        else:
            # ✅ 使用原始選項列表確保所有選項都顯示
            for i, opt in enumerate(self.options):
                label = self._format_option_label(opt)
                self.add_item(VoteButton(label=label, vote_id=self.vote_id, opt=opt, option_index=i))

        # 更新 Embed 顯示
        from bot.utils.vote_utils import build_vote_embed
        vote = await vote_dao.get_vote_by_id(self.vote_id)
        embed = build_vote_embed(
            vote['title'], vote['start_time'], vote['end_time'],
            vote['is_multi'], vote['anonymous'], total, vote_id=self.vote_id
        )
        await interaction.message.edit(embed=embed, view=self)


# ✅ 多選：選項選擇元件
class MultiChoiceSelect(discord.ui.Select):
    def __init__(self, vote_id, options, allowed_roles):
        self.vote_id = vote_id
        self.allowed_roles = allowed_roles
        super().__init__(
            placeholder="請選擇你想投的選項...",
            min_values=1,
            max_values=len(options),
            options=[discord.SelectOption(label=opt) for opt in options],
            custom_id=f"multi_select_{vote_id}"
        )

    async def callback(self, interaction: discord.Interaction):
        # 避免循環導入
        from bot.cogs.vote import VoteCog
        cog = interaction.client.get_cog("VoteCog")
        
        if not self._check_permission(interaction):
            await interaction.response.send_message("❌ 你沒有權限參與此投票。", ephemeral=True)
            return

        self.view.selection = self.values
        await interaction.response.send_message(
            f"✅ 你已選擇：{', '.join(self.values)}，請點擊下方確認送出。",
            ephemeral=True
        )
        logger.debug(f"[Vote] 使用者選擇：{self.values}")

    def _check_permission(self, interaction):
        return not self.allowed_roles or any(role.id in self.allowed_roles for role in interaction.user.roles)


# ✅ 多選：清除選擇
class ClearSelectionButton(discord.ui.Button):
    def __init__(self, vote_id):
        super().__init__(label="清除選擇", style=discord.ButtonStyle.secondary, custom_id=f"clear_selection_{vote_id}")
        self.vote_id = vote_id

    async def callback(self, interaction: discord.Interaction):
        self.view.selection = []
        await interaction.response.send_message("✅ 已清除你所有的選擇，請重新選擇。", ephemeral=True)
        logger.debug("[Vote] 使用者清除了所有選擇")


# ✅ 多選：確認送出按鈕
class VoteSubmitButton(discord.ui.Button):
    def __init__(self, vote_id):
        super().__init__(label="確認送出", style=discord.ButtonStyle.success, custom_id=f"submit_vote_{vote_id}")

    async def callback(self, interaction: discord.Interaction):
        from bot.cogs.vote import VoteCog  # 避免循環匯入
        cog = interaction.client.get_cog("VoteCog")
        if not cog:
            return
        view: VoteButtonView = self.view
        await cog.handle_vote_submit(interaction, view.vote_id, view.selection)
        await view.refresh(interaction)


# ✅ 單選：選項按鈕
class VoteButton(discord.ui.Button):
    def __init__(self, label, vote_id, opt, option_index):
        super().__init__(label=label, style=discord.ButtonStyle.primary, custom_id=f"vote_{vote_id}_opt_{option_index}")
        self.vote_id = vote_id
        self.option = opt

    async def callback(self, interaction: discord.Interaction):
        from bot.cogs.vote import VoteCog
        cog = interaction.client.get_cog("VoteCog")
        if not cog:
            return
        await cog.handle_vote_submit(interaction, self.vote_id, [self.option])
        await self.view.refresh(interaction)


# ✅ 投票建立流程互動元件（選擇身分組）
class RoleSelectView(discord.ui.View):
    def __init__(self, user_id, roles):
        super().__init__(timeout=None)
        options = [
            discord.SelectOption(label=r.name, value=str(r.id))
            for r in roles if not r.is_bot_managed() and r.name != "@everyone"
        ]
        self.add_item(discord.ui.Select(
            placeholder="選擇可投票的身分組（可多選）",
            options=options,
            custom_id=f"role_select_{user_id}",
            min_values=1,
            max_values=min(25, len(options))
        ))


class AnonSelectView(discord.ui.View):
    def __init__(self, user_id):
        super().__init__(timeout=None)
        self.add_item(discord.ui.Select(
            placeholder="是否為匿名投票？",
            options=[
                discord.SelectOption(label="✅ 是", value="true"),
                discord.SelectOption(label="❌ 否", value="false")
            ],
            custom_id=f"anon_select_{user_id}",
            min_values=1,
            max_values=1
        ))


class MultiSelectView(discord.ui.View):
    def __init__(self, user_id):
        super().__init__(timeout=None)
        self.add_item(discord.ui.Select(
            placeholder="投票方式：單選 / 多選",
            options=[
                discord.SelectOption(label="單選", value="false"),
                discord.SelectOption(label="多選", value="true")
            ],
            custom_id=f"multi_select_{user_id}",
            min_values=1,
            max_values=1
        ))


class DurationSelectView(discord.ui.View):
    def __init__(self, user_id):
        super().__init__(timeout=None)
        self.add_item(discord.ui.Select(
            placeholder="選擇投票持續時間",
            options=[
                discord.SelectOption(label="5 分鐘", value="5"),
                discord.SelectOption(label="15 分鐘", value="15"),
                discord.SelectOption(label="30 分鐘", value="30"),
                discord.SelectOption(label="1 小時", value="60"),
                discord.SelectOption(label="2 小時", value="120"),
                discord.SelectOption(label="6 小時", value="360"),
                discord.SelectOption(label="12 小時", value="720"),
                discord.SelectOption(label="24 小時", value="1440")
            ],
            custom_id=f"duration_select_{user_id}",
            min_values=1,
            max_values=1
        ))


class FinalStepView(discord.ui.View):
    def __init__(self, user_id, callback):
        super().__init__(timeout=None)
        self.add_item(discord.ui.Button(
            label="✅ 確認建立投票",
            style=discord.ButtonStyle.success,
            custom_id=f"confirm_vote_{user_id}"
        ))