# listener.py - v5.0（整合進投票系統 v5.0，修正交互、清除選擇、匿名與多選設定流程）

import discord
from discord.ext import commands
from datetime import timedelta, timezone
from bot.views.vote_views import (
    RoleSelectView, AnonSelectView, DurationSelectView,
    FinalStepView, MultiSelectView
)
from shared.logger import logger

class VoteListener(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or not message.guild:
            return

        cog = self.bot.get_cog("VoteCore")
        if not cog:
            return
        sessions = cog.vote_sessions
        user_id = message.author.id
        if user_id not in sessions:
            return

        session = sessions[user_id]
        logger.debug(f"[Listener] 接收到訊息：{message.content}")

        # Step 1 - 輸入標題
        if 'title' not in session:
            session['title'] = message.content.strip()
            await message.channel.send("請輸入投票選項，每行一個（2~20 個）...", delete_after=15)
            try:
                await message.delete()
            except discord.Forbidden:
                pass
            logger.debug(f"[Listener] 設定標題：{session['title']}")
            return

        # Step 2 - 輸入選項
        if 'options' not in session:
            options = [line.strip() for line in message.content.strip().splitlines() if line.strip()]
            if not 2 <= len(options) <= 20:
                await message.channel.send("請輸入 2~20 個有效選項。", delete_after=10)
                return
            session['options'] = options
            await message.channel.send(
                "請選擇可投票的身分組：",
                view=RoleSelectView(user_id, message.guild.roles),
                delete_after=60
            )
            try:
                await message.delete()
            except discord.Forbidden:
                pass
            logger.debug(f"[Listener] 設定選項：{session['options']}")
            return

    @commands.Cog.listener()
    async def on_interaction(self, interaction: discord.Interaction):
        if interaction.type != discord.InteractionType.component:
            return

        cog = self.bot.get_cog("VoteCore")
        if not cog:
            return
        sessions = cog.vote_sessions
        user_id = interaction.user.id
        if user_id not in sessions:
            return

        session = sessions[user_id]
        logger.debug(f"[Listener] 處理互動：{interaction.data}")

        component_type = interaction.data.get("component_type")
        values = interaction.data.get("values", [])
        custom_id = interaction.data.get("custom_id", "")

        # Step 3 - 選擇身分組
        if 'allowed_roles' not in session and component_type == 3 and custom_id.startswith("role_select"):
            session['allowed_roles'] = [int(v) for v in values]
            await interaction.response.send_message("請選擇是否匿名投票：", view=AnonSelectView(user_id), ephemeral=True)
            logger.debug(f"[Listener] 選擇身分組：{session['allowed_roles']}")
            return

        # Step 4 - 匿名設定
        if 'anonymous' not in session and component_type == 3 and custom_id.startswith("anon_select"):
            session['anonymous'] = values[0] == 'true'
            await interaction.response.send_message("請選擇投票方式（單選或多選）：", view=MultiSelectView(user_id), ephemeral=True)
            logger.debug(f"[Listener] 匿名設定：{session['anonymous']}")
            return

        # Step 5 - 是否多選
        if 'is_multi' not in session and component_type == 3 and custom_id.startswith("multi_select"):
            session['is_multi'] = values[0] == 'true'
            await interaction.response.send_message("請選擇投票時效：", view=DurationSelectView(user_id), ephemeral=True)
            logger.debug(f"[Listener] 是否為多選：{session['is_multi']}")
            return

        # Step 6 - 時效設定
        if 'end_time' not in session and component_type == 3 and custom_id.startswith("duration_select"):
            minutes = int(values[0])
            session['end_time'] = interaction.created_at.replace(tzinfo=timezone.utc) + timedelta(minutes=minutes)
            session['duration'] = minutes
            await interaction.response.send_message(
                "✅ 所有項目已完成，請點擊下方按鈕建立投票：",
                view=FinalStepView(user_id, cog.finalize_vote),
                ephemeral=True
            )
            logger.debug(f"[Listener] 時效設定完成：{session['end_time']}")
            return

        # Step 7 - 建立投票（按鈕確認）
        if component_type == 2 and custom_id.startswith("confirm_vote_"):
            await interaction.response.defer(ephemeral=True)
            await cog.finalize_vote(user_id, interaction.guild)
            await interaction.followup.send("🎉 投票已建立完成！", ephemeral=True)
            logger.debug(f"[Listener] 透過 listener 建立投票完成")
            return

async def setup(bot):
    await bot.add_cog(VoteListener(bot))