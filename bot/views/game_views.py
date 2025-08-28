# bot/views/game_views.py - 遊戲互動視圖
"""
遊戲系統互動視圖 v2.2.0
提供各種遊戲的互動界面和用戶交互組件
"""

import random
from typing import Any, Dict

import discord
from discord import ui

from bot.utils.embed_builder import EmbedBuilder
from shared.logger import logger


class GameMenuView(ui.View):
    """遊戲選單視圖"""

    def __init__(self, game_cog, user_economy: Dict[str, Any]):
        super().__init__(timeout=300)
        self.game_cog = game_cog
        self.user_economy = user_economy

    @ui.button(label="🔢 猜數字", style=discord.ButtonStyle.primary, row=0)
    async def guess_number_button(self, interaction: discord.Interaction, button: ui.Button):
        """猜數字遊戲按鈕"""
        try:
            # 創建難度選擇視圖
            view = DifficultySelectView(self.game_cog, "guess_number")

            embed = EmbedBuilder.build(
                title="🔢 猜數字遊戲", description="選擇遊戲難度：", color=0x00AAFF
            )

            embed.add_field(
                name="🟢 簡單", value="• 範圍: 1-50\n• 機會: 8次\n• 獎勵: 50🪙", inline=True
            )

            embed.add_field(
                name="🟡 中等", value="• 範圍: 1-100\n• 機會: 6次\n• 獎勵: 100🪙", inline=True
            )

            embed.add_field(
                name="🔴 困難", value="• 範圍: 1-200\n• 機會: 5次\n• 獎勵: 200🪙", inline=True
            )

            await interaction.response.edit_message(embed=embed, view=view)

        except Exception as e:
            logger.error(f"❌ 猜數字按鈕錯誤: {e}")
            await interaction.response.send_message("❌ 開始遊戲時發生錯誤。", ephemeral=True)

    @ui.button(label="✂️ 剪刀石頭布", style=discord.ButtonStyle.secondary, row=0)
    async def rock_paper_scissors_button(self, interaction: discord.Interaction, button: ui.Button):
        """剪刀石頭布遊戲按鈕"""
        try:
            view = RockPaperScissorsView(self.game_cog)

            embed = EmbedBuilder.build(
                title="✂️ 剪刀石頭布", description="經典對戰遊戲！選擇您的招式：", color=0xFF6B6B
            )

            embed.add_field(
                name="🎯 遊戲規則",
                value="• 剪刀勝紙，紙勝石頭，石頭勝剪刀\n• 勝利獎勵: 30🪙\n• 平手獎勵: 10🪙",
                inline=False,
            )

            await interaction.response.edit_message(embed=embed, view=view)

        except Exception as e:
            logger.error(f"❌ 剪刀石頭布按鈕錯誤: {e}")
            await interaction.response.send_message("❌ 開始遊戲時發生錯誤。", ephemeral=True)

    @ui.button(label="🪙 拋硬幣", style=discord.ButtonStyle.success, row=0)
    async def coin_flip_button(self, interaction: discord.Interaction, button: ui.Button):
        """拋硬幣遊戲按鈕"""
        try:
            view = CoinFlipView(self.game_cog, self.user_economy)

            embed = EmbedBuilder.build(
                title="🪙 拋硬幣遊戲", description="猜測硬幣的正反面！", color=0xFFD700
            )

            embed.add_field(
                name="💰 您的金幣", value=f"{self.user_economy.get('coins', 0):,} 🪙", inline=True
            )

            embed.add_field(
                name="🎯 遊戲規則",
                value="• 最小下注: 10🪙\n• 最大下注: 1000🪙\n• 勝利倍率: 2倍",
                inline=True,
            )

            await interaction.response.edit_message(embed=embed, view=view)

        except Exception as e:
            logger.error(f"❌ 拋硬幣按鈕錯誤: {e}")
            await interaction.response.send_message("❌ 開始遊戲時發生錯誤。", ephemeral=True)

    @ui.button(label="🎰 輪盤", style=discord.ButtonStyle.danger, row=1)
    async def roulette_button(self, interaction: discord.Interaction, button: ui.Button):
        """輪盤遊戲按鈕"""
        try:
            if self.user_economy.get("coins", 0) < 20:
                await interaction.response.send_message(
                    "❌ 您的金幣不足！輪盤遊戲最少需要 20🪙", ephemeral=True
                )
                return

            view = RouletteView(self.game_cog, self.user_economy)

            embed = EmbedBuilder.build(
                title="🎰 輪盤遊戲", description="歡迎來到刺激的輪盤賭桌！", color=0x8B0000
            )

            embed.add_field(
                name="💰 您的金幣", value=f"{self.user_economy.get('coins', 0):,} 🪙", inline=True
            )

            embed.add_field(
                name="🎯 下注選項",
                value="• 特定數字: 35倍\n• 紅/黑: 2倍\n• 奇/偶: 2倍\n• 打組: 3倍",
                inline=True,
            )

            await interaction.response.edit_message(embed=embed, view=view)

        except Exception as e:
            logger.error(f"❌ 輪盤按鈕錯誤: {e}")
            await interaction.response.send_message("❌ 開始遊戲時發生錯誤。", ephemeral=True)

    @ui.button(label="🧠 問答競賽", style=discord.ButtonStyle.primary, row=1)
    async def trivia_button(self, interaction: discord.Interaction, button: ui.Button):
        """問答競賽按鈕"""
        try:
            view = TriviaView(self.game_cog)

            embed = EmbedBuilder.build(
                title="🧠 問答競賽", description="測試您的知識水平！", color=0x4169E1
            )

            embed.add_field(
                name="📚 題目範圍",
                value="• 一般常識\n• 科學知識\n• 歷史地理\n• 流行文化",
                inline=True,
            )

            embed.add_field(
                name="🏆 獎勵系統",
                value="• 答對: 20🪙 + 經驗\n• 連續答對有額外獎勵\n• 困難題目獎勵更高",
                inline=True,
            )

            await interaction.response.edit_message(embed=embed, view=view)

        except Exception as e:
            logger.error(f"❌ 問答競賽按鈕錯誤: {e}")
            await interaction.response.send_message("❌ 開始遊戲時發生錯誤。", ephemeral=True)

    @ui.button(label="🎲 骰子遊戲", style=discord.ButtonStyle.secondary, row=1)
    async def dice_game_button(self, interaction: discord.Interaction, button: ui.Button):
        """骰子遊戲按鈕"""
        try:
            view = DiceGameView(self.game_cog, self.user_economy)

            embed = EmbedBuilder.build(
                title="🎲 骰子遊戲", description="運氣大比拼！", color=0x32CD32
            )

            embed.add_field(
                name="🎯 遊戲方式",
                value="• 擲出兩顆骰子\n• 猜測點數總和\n• 越準確獎勵越高",
                inline=True,
            )

            embed.add_field(
                name="💰 獎勵規則",
                value="• 猜中確切數字: 10倍\n• 猜中範圍: 2-5倍\n• 特殊組合有額外獎勵",
                inline=True,
            )

            await interaction.response.edit_message(embed=embed, view=view)

        except Exception as e:
            logger.error(f"❌ 骰子遊戲按鈕錯誤: {e}")
            await interaction.response.send_message("❌ 開始遊戲時發生錯誤。", ephemeral=True)

    @ui.button(label="🔙 返回", style=discord.ButtonStyle.gray, row=2)
    async def back_button(self, interaction: discord.Interaction, button: ui.Button):
        """返回按鈕"""
        try:
            # 這裡可以返回到主選單或關閉視圖
            embed = EmbedBuilder.build(
                title="👋 感謝遊玩！",
                description="隨時可以再次使用 `/games` 指令開始遊戲！",
                color=0x95A5A6,
            )

            await interaction.response.edit_message(embed=embed, view=None)

        except Exception as e:
            logger.error(f"❌ 返回按鈕錯誤: {e}")


class DifficultySelectView(ui.View):
    """難度選擇視圖"""

    def __init__(self, game_cog, game_type: str):
        super().__init__(timeout=60)
        self.game_cog = game_cog
        self.game_type = game_type

    @ui.button(label="🟢 簡單", style=discord.ButtonStyle.success)
    async def easy_button(self, interaction: discord.Interaction, button: ui.Button):
        await self._start_game(interaction, "easy")

    @ui.button(label="🟡 中等", style=discord.ButtonStyle.primary)
    async def medium_button(self, interaction: discord.Interaction, button: ui.Button):
        await self._start_game(interaction, "medium")

    @ui.button(label="🔴 困難", style=discord.ButtonStyle.danger)
    async def hard_button(self, interaction: discord.Interaction, button: ui.Button):
        await self._start_game(interaction, "hard")

    async def _start_game(self, interaction: discord.Interaction, difficulty: str):
        """開始遊戲"""
        try:
            if self.game_type == "guess_number":
                await self.game_cog.guess_number_game(interaction, difficulty)

        except Exception as e:
            logger.error(f"❌ 開始遊戲錯誤: {e}")
            await interaction.response.send_message("❌ 開始遊戲時發生錯誤。", ephemeral=True)


class GuessNumberView(ui.View):
    """猜數字遊戲視圖"""

    def __init__(self, game_cog, session):
        super().__init__(timeout=300)
        self.game_cog = game_cog
        self.session = session
        self.current_guess = ""

    @ui.button(label="1", style=discord.ButtonStyle.secondary, row=0)
    async def number_1(self, interaction: discord.Interaction, button: ui.Button):
        await self._add_digit(interaction, "1")

    @ui.button(label="2", style=discord.ButtonStyle.secondary, row=0)
    async def number_2(self, interaction: discord.Interaction, button: ui.Button):
        await self._add_digit(interaction, "2")

    @ui.button(label="3", style=discord.ButtonStyle.secondary, row=0)
    async def number_3(self, interaction: discord.Interaction, button: ui.Button):
        await self._add_digit(interaction, "3")

    @ui.button(label="4", style=discord.ButtonStyle.secondary, row=0)
    async def number_4(self, interaction: discord.Interaction, button: ui.Button):
        await self._add_digit(interaction, "4")

    @ui.button(label="5", style=discord.ButtonStyle.secondary, row=0)
    async def number_5(self, interaction: discord.Interaction, button: ui.Button):
        await self._add_digit(interaction, "5")

    @ui.button(label="6", style=discord.ButtonStyle.secondary, row=1)
    async def number_6(self, interaction: discord.Interaction, button: ui.Button):
        await self._add_digit(interaction, "6")

    @ui.button(label="7", style=discord.ButtonStyle.secondary, row=1)
    async def number_7(self, interaction: discord.Interaction, button: ui.Button):
        await self._add_digit(interaction, "7")

    @ui.button(label="8", style=discord.ButtonStyle.secondary, row=1)
    async def number_8(self, interaction: discord.Interaction, button: ui.Button):
        await self._add_digit(interaction, "8")

    @ui.button(label="9", style=discord.ButtonStyle.secondary, row=1)
    async def number_9(self, interaction: discord.Interaction, button: ui.Button):
        await self._add_digit(interaction, "9")

    @ui.button(label="0", style=discord.ButtonStyle.secondary, row=1)
    async def number_0(self, interaction: discord.Interaction, button: ui.Button):
        await self._add_digit(interaction, "0")

    @ui.button(label="🔄 清除", style=discord.ButtonStyle.danger, row=2)
    async def clear_button(self, interaction: discord.Interaction, button: ui.Button):
        """清除輸入"""
        self.current_guess = ""
        await self._update_display(interaction, "已清除輸入")

    @ui.button(label="✅ 猜測", style=discord.ButtonStyle.success, row=2)
    async def guess_button(self, interaction: discord.Interaction, button: ui.Button):
        """提交猜測"""
        await self._submit_guess(interaction)

    @ui.button(label="❌ 放棄", style=discord.ButtonStyle.gray, row=2)
    async def give_up_button(self, interaction: discord.Interaction, button: ui.Button):
        """放棄遊戲"""
        await self._give_up(interaction)

    async def _add_digit(self, interaction: discord.Interaction, digit: str):
        """添加數字"""
        if len(self.current_guess) < 3:  # 限制最多3位數
            self.current_guess += digit
            await self._update_display(interaction, f"當前輸入: {self.current_guess}")
        else:
            await interaction.response.send_message("❌ 最多只能輸入3位數！", ephemeral=True)

    async def _update_display(self, interaction: discord.Interaction, message: str):
        """更新顯示"""
        try:
            embed = interaction.message.embeds[0].copy() if interaction.message.embeds else None

            if embed:
                # 更新狀態欄位
                for i, field in enumerate(embed.fields):
                    if "目前狀態" in field.name:
                        embed.set_field_at(
                            i,
                            name="🎯 目前狀態",
                            value=f"輸入: {self.current_guess or '(無)'}\n"
                            f"剩餘機會: {self.session.data['attempts_left']}\n"
                            f"提示: {message}",
                            inline=False,
                        )
                        break
                else:
                    # 如果沒有狀態欄位，添加一個
                    embed.add_field(
                        name="🎯 目前狀態",
                        value=f"輸入: {self.current_guess or '(無)'}\n"
                        f"剩餘機會: {self.session.data['attempts_left']}\n"
                        f"提示: {message}",
                        inline=False,
                    )

            await interaction.response.edit_message(embed=embed, view=self)

        except Exception as e:
            logger.error(f"❌ 更新顯示錯誤: {e}")

    async def _submit_guess(self, interaction: discord.Interaction):
        """提交猜測"""
        try:
            if not self.current_guess:
                await interaction.response.send_message("❌ 請先輸入數字！", ephemeral=True)
                return

            if not self.current_guess.isdigit():
                await interaction.response.send_message("❌ 請輸入有效數字！", ephemeral=True)
                return

            guess = int(self.current_guess)
            max_num = self.session.data["max_num"]

            if guess < 1 or guess > max_num:
                await interaction.response.send_message(
                    f"❌ 數字必須在 1 到 {max_num} 之間！", ephemeral=True
                )
                return

            # 處理猜測
            secret_number = self.session.data["secret_number"]
            self.session.data["attempts_left"] -= 1
            self.session.data["guesses"].append(guess)

            # 檢查結果
            if guess == secret_number:
                # 猜中了！
                score = self.session.data["attempts_left"] + 1  # 剩餘次數越多分數越高
                await self.game_cog.end_game_session(self.session, won=True, score=score)

                embed = EmbedBuilder.build(
                    title="🎉 恭喜！您猜中了！",
                    description=f"答案就是 **{secret_number}**！",
                    color=0x00FF00,
                )

                embed.add_field(
                    name="🏆 遊戲結果",
                    value=f"✅ 猜中數字: {secret_number}\n"
                    f"🎯 使用次數: {self.session.data['max_attempts'] - self.session.data['attempts_left']}\n"
                    f"💰 獲得金幣: {self.session.data['reward']}🪙\n"
                    f"⭐ 獲得經驗: {self.session.data['reward'] // 2}",
                    inline=False,
                )

                await interaction.response.edit_message(embed=embed, view=None)

            elif self.session.data["attempts_left"] <= 0:
                # 機會用完了
                await self.game_cog.end_game_session(self.session, won=False)

                embed = EmbedBuilder.build(
                    title="💔 遊戲結束！",
                    description=f"很遺憾，答案是 **{secret_number}**。",
                    color=0xFF0000,
                )

                embed.add_field(
                    name="📊 遊戲記錄",
                    value=f"🎯 您的猜測: {', '.join(map(str, self.session.data['guesses']))}\n"
                    f"✨ 答案: {secret_number}\n"
                    f"💡 別灰心，再試一次吧！",
                    inline=False,
                )

                await interaction.response.edit_message(embed=embed, view=None)

            else:
                # 繼續遊戲
                if guess < secret_number:
                    hint = "太小了！往大一點猜"
                else:
                    hint = "太大了！往小一點猜"

                self.current_guess = ""
                await self._update_display(interaction, hint)

        except Exception as e:
            logger.error(f"❌ 提交猜測錯誤: {e}")
            await interaction.response.send_message("❌ 處理猜測時發生錯誤。", ephemeral=True)

    async def _give_up(self, interaction: discord.Interaction):
        """放棄遊戲"""
        try:
            await self.game_cog.end_game_session(self.session, won=False)

            embed = EmbedBuilder.build(
                title="🏳️ 遊戲放棄",
                description=f"答案是 **{self.session.data['secret_number']}**。\n下次再來挑戰吧！",
                color=0x95A5A6,
            )

            await interaction.response.edit_message(embed=embed, view=None)

        except Exception as e:
            logger.error(f"❌ 放棄遊戲錯誤: {e}")


class RockPaperScissorsView(ui.View):
    """剪刀石頭布視圖"""

    def __init__(self, game_cog):
        super().__init__(timeout=180)
        self.game_cog = game_cog

    @ui.button(label="✂️ 剪刀", style=discord.ButtonStyle.secondary)
    async def scissors_button(self, interaction: discord.Interaction, button: ui.Button):
        await self._play_game(interaction, "scissors", "✂️")

    @ui.button(label="📄 石頭", style=discord.ButtonStyle.secondary)
    async def rock_button(self, interaction: discord.Interaction, button: ui.Button):
        await self._play_game(interaction, "rock", "🗿")

    @ui.button(label="🗞️ 布", style=discord.ButtonStyle.secondary)
    async def paper_button(self, interaction: discord.Interaction, button: ui.Button):
        await self._play_game(interaction, "paper", "📄")

    async def _play_game(
        self, interaction: discord.Interaction, player_choice: str, player_emoji: str
    ):
        """進行遊戲"""
        try:
            # 電腦隨機選擇
            choices = ["rock", "paper", "scissors"]
            emojis = {"rock": "🗿", "paper": "📄", "scissors": "✂️"}
            computer_choice = random.choice(choices)
            computer_emoji = emojis[computer_choice]

            # 判斷結果
            result = self._determine_winner(player_choice, computer_choice)

            # 計算獎勵
            reward = 0
            if result == "win":
                reward = 30
                result_text = "🎉 您贏了！"
                result_color = 0x00FF00
            elif result == "draw":
                reward = 10
                result_text = "🤝 平手！"
                result_color = 0xFFAA00
            else:
                result_text = "💔 您輸了！"
                result_color = 0xFF0000

            # 發放獎勵
            if reward > 0:
                await self.game_cog.economy_manager.add_coins(
                    interaction.user.id, interaction.guild.id, reward
                )

            # 創建結果嵌入
            embed = EmbedBuilder.build(
                title="✂️ 剪刀石頭布結果", description=result_text, color=result_color
            )

            embed.add_field(
                name="🎯 對戰結果",
                value=f"您的選擇: {player_emoji} {player_choice.title()}\n"
                f"電腦選擇: {computer_emoji} {computer_choice.title()}\n"
                f"獲得金幣: {reward}🪙",
                inline=False,
            )

            # 創建重新開始視圖
            new_view = RockPaperScissorsView(self.game_cog)

            await interaction.response.edit_message(embed=embed, view=new_view)

            # 記錄遊戲統計
            await self.game_cog.economy_manager.increment_daily_games(
                interaction.user.id, interaction.guild.id
            )

            if result == "win":
                await self.game_cog.economy_manager.increment_daily_wins(
                    interaction.user.id, interaction.guild.id
                )

        except Exception as e:
            logger.error(f"❌ 剪刀石頭布遊戲錯誤: {e}")
            await interaction.response.send_message("❌ 遊戲時發生錯誤。", ephemeral=True)

    def _determine_winner(self, player: str, computer: str) -> str:
        """判斷勝負"""
        if player == computer:
            return "draw"
        elif (
            player == "rock"
            and computer == "scissors"
            or player == "paper"
            and computer == "rock"
            or player == "scissors"
            and computer == "paper"
        ):
            return "win"
        else:
            return "lose"


class CoinFlipView(ui.View):
    """拋硬幣視圖"""

    def __init__(self, game_cog, user_economy: Dict[str, Any]):
        super().__init__(timeout=180)
        self.game_cog = game_cog
        self.user_economy = user_economy
        self.bet_amount = 50  # 預設下注金額

    @ui.button(label="🔼 增加下注", style=discord.ButtonStyle.secondary, row=0)
    async def increase_bet(self, interaction: discord.Interaction, button: ui.Button):
        """增加下注金額"""
        max_coins = self.user_economy.get("coins", 0)
        if self.bet_amount < min(1000, max_coins):
            self.bet_amount = min(self.bet_amount + 50, min(1000, max_coins))
            await self._update_bet_display(interaction)
        else:
            await interaction.response.send_message("❌ 已達到最大下注金額！", ephemeral=True)

    @ui.button(label="🔽 減少下注", style=discord.ButtonStyle.secondary, row=0)
    async def decrease_bet(self, interaction: discord.Interaction, button: ui.Button):
        """減少下注金額"""
        if self.bet_amount > 10:
            self.bet_amount = max(self.bet_amount - 50, 10)
            await self._update_bet_display(interaction)
        else:
            await interaction.response.send_message("❌ 已達到最小下注金額！", ephemeral=True)

    @ui.button(label="👑 正面", style=discord.ButtonStyle.primary, row=1)
    async def heads_button(self, interaction: discord.Interaction, button: ui.Button):
        await self._play_coin_flip(interaction, "heads", "👑")

    @ui.button(label="🪙 反面", style=discord.ButtonStyle.primary, row=1)
    async def tails_button(self, interaction: discord.Interaction, button: ui.Button):
        await self._play_coin_flip(interaction, "tails", "🪙")

    async def _update_bet_display(self, interaction: discord.Interaction):
        """更新下注顯示"""
        try:
            embed = interaction.message.embeds[0].copy() if interaction.message.embeds else None

            if embed:
                # 更新下注金額顯示
                for i, field in enumerate(embed.fields):
                    if "下注金額" in field.name:
                        embed.set_field_at(
                            i, name="💰 目前下注", value=f"{self.bet_amount}🪙", inline=True
                        )
                        break
                else:
                    embed.add_field(name="💰 目前下注", value=f"{self.bet_amount}🪙", inline=True)

            await interaction.response.edit_message(embed=embed, view=self)

        except Exception as e:
            logger.error(f"❌ 更新下注顯示錯誤: {e}")

    async def _play_coin_flip(
        self, interaction: discord.Interaction, choice: str, choice_emoji: str
    ):
        """進行拋硬幣遊戲"""
        try:
            user_coins = self.user_economy.get("coins", 0)

            if user_coins < self.bet_amount:
                await interaction.response.send_message("❌ 金幣不足！", ephemeral=True)
                return

            # 扣除下注金額
            await self.game_cog.economy_manager.add_coins(
                interaction.user.id, interaction.guild.id, -self.bet_amount
            )

            # 拋硬幣
            result = random.choice(["heads", "tails"])
            result_emoji = "👑" if result == "heads" else "🪙"

            # 判斷結果
            won = choice == result

            if won:
                winnings = self.bet_amount * 2  # 2倍獎勵
                await self.game_cog.economy_manager.add_coins(
                    interaction.user.id, interaction.guild.id, winnings
                )
                result_text = "🎉 恭喜您猜中了！"
                result_color = 0x00FF00
                await self.game_cog.economy_manager.increment_daily_wins(
                    interaction.user.id, interaction.guild.id
                )
            else:
                winnings = 0
                result_text = "💔 很遺憾，猜錯了！"
                result_color = 0xFF0000

            # 創建結果嵌入
            embed = EmbedBuilder.build(
                title="🪙 拋硬幣結果", description=result_text, color=result_color
            )

            embed.add_field(
                name="🎯 對戰結果",
                value=f"您的猜測: {choice_emoji} {choice.title()}\n"
                f"硬幣結果: {result_emoji} {result.title()}\n"
                f"下注金額: {self.bet_amount}🪙\n"
                f"獲得金額: {winnings}🪙",
                inline=False,
            )

            # 更新經濟狀態
            self.user_economy["coins"] = user_coins - self.bet_amount + winnings

            # 創建新的視圖
            new_view = CoinFlipView(self.game_cog, self.user_economy)

            await interaction.response.edit_message(embed=embed, view=new_view)

            # 記錄遊戲統計
            await self.game_cog.economy_manager.increment_daily_games(
                interaction.user.id, interaction.guild.id
            )

        except Exception as e:
            logger.error(f"❌ 拋硬幣遊戲錯誤: {e}")
            await interaction.response.send_message("❌ 遊戲時發生錯誤。", ephemeral=True)


class RouletteView(ui.View):
    """輪盤遊戲視圖"""

    def __init__(self, game_cog, user_economy: Dict[str, Any]):
        super().__init__(timeout=300)
        self.game_cog = game_cog
        self.user_economy = user_economy
        self.bet_amount = 50
        self.bet_type = None
        self.bet_value = None

    @ui.select(
        placeholder="選擇下注類型...",
        options=[
            discord.SelectOption(label="紅色", value="red", emoji="🔴"),
            discord.SelectOption(label="黑色", value="black", emoji="⚫"),
            discord.SelectOption(label="奇數", value="odd", emoji="1️⃣"),
            discord.SelectOption(label="偶數", value="even", emoji="2️⃣"),
            discord.SelectOption(label="特定數字", value="number", emoji="🎯"),
        ],
        row=0,
    )
    async def bet_type_select(self, interaction: discord.Interaction, select: ui.Select):
        """選擇下注類型"""
        self.bet_type = select.values[0]

        if self.bet_type == "number":
            await interaction.response.send_message(
                "請選擇要下注的數字 (0-36):", ephemeral=True, view=NumberSelectView(self)
            )
        else:
            await self._update_bet_display(interaction)

    @ui.button(label="🔼 增加下注", style=discord.ButtonStyle.secondary, row=1)
    async def increase_bet(self, interaction: discord.Interaction, button: ui.Button):
        max_coins = self.user_economy.get("coins", 0)
        if self.bet_amount < min(500, max_coins):
            self.bet_amount = min(self.bet_amount + 25, min(500, max_coins))
            await self._update_bet_display(interaction)
        else:
            await interaction.response.send_message("❌ 已達到最大下注金額！", ephemeral=True)

    @ui.button(label="🔽 減少下注", style=discord.ButtonStyle.secondary, row=1)
    async def decrease_bet(self, interaction: discord.Interaction, button: ui.Button):
        if self.bet_amount > 20:
            self.bet_amount = max(self.bet_amount - 25, 20)
            await self._update_bet_display(interaction)
        else:
            await interaction.response.send_message("❌ 已達到最小下注金額！", ephemeral=True)

    @ui.button(label="🎰 轉動輪盤", style=discord.ButtonStyle.danger, row=2)
    async def spin_button(self, interaction: discord.Interaction, button: ui.Button):
        await self._spin_roulette(interaction)

    async def _update_bet_display(self, interaction: discord.Interaction):
        """更新下注顯示"""
        try:
            bet_type_display = {
                "red": "🔴 紅色",
                "black": "⚫ 黑色",
                "odd": "1️⃣ 奇數",
                "even": "2️⃣ 偶數",
                "number": f"🎯 數字 {self.bet_value}",
            }

            embed = EmbedBuilder.build(
                title="🎰 輪盤遊戲", description="設定您的下注並轉動輪盤！", color=0x8B0000
            )

            embed.add_field(
                name="💰 下注資訊",
                value=f"金額: {self.bet_amount}🪙\n"
                f"類型: {bet_type_display.get(self.bet_type, '未選擇')}",
                inline=True,
            )

            embed.add_field(
                name="💳 您的金幣", value=f"{self.user_economy.get('coins', 0):,}🪙", inline=True
            )

            await interaction.response.edit_message(embed=embed, view=self)

        except Exception as e:
            logger.error(f"❌ 更新輪盤顯示錯誤: {e}")

    async def _spin_roulette(self, interaction: discord.Interaction):
        """轉動輪盤"""
        try:
            if not self.bet_type:
                await interaction.response.send_message("❌ 請先選擇下注類型！", ephemeral=True)
                return

            if self.user_economy.get("coins", 0) < self.bet_amount:
                await interaction.response.send_message("❌ 金幣不足！", ephemeral=True)
                return

            # 扣除下注金額
            await self.game_cog.economy_manager.add_coins(
                interaction.user.id, interaction.guild.id, -self.bet_amount
            )

            # 生成結果 (0-36)
            result_number = random.randint(0, 36)

            # 判斷顏色
            red_numbers = [1, 3, 5, 7, 9, 12, 14, 16, 18, 19, 21, 23, 25, 27, 30, 32, 34, 36]
            is_red = result_number in red_numbers
            is_black = result_number != 0 and not is_red
            is_odd = result_number % 2 == 1 and result_number != 0
            is_even = result_number % 2 == 0 and result_number != 0

            # 計算獎勵
            won = False
            payout_multiplier = 0

            if self.bet_type == "red" and is_red:
                won = True
                payout_multiplier = 2
            elif self.bet_type == "black" and is_black:
                won = True
                payout_multiplier = 2
            elif self.bet_type == "odd" and is_odd:
                won = True
                payout_multiplier = 2
            elif self.bet_type == "even" and is_even:
                won = True
                payout_multiplier = 2
            elif self.bet_type == "number" and self.bet_value == result_number:
                won = True
                payout_multiplier = 35

            # 發放獎勵
            winnings = 0
            if won:
                winnings = self.bet_amount * payout_multiplier
                await self.game_cog.economy_manager.add_coins(
                    interaction.user.id, interaction.guild.id, winnings
                )

            # 創建結果嵌入
            result_color = "🔴" if is_red else ("⚫" if is_black else "🟢")

            embed = EmbedBuilder.build(
                title="🎰 輪盤結果",
                description=f"輪盤停在: {result_color} **{result_number}**",
                color=0x00FF00 if won else 0xFF0000,
            )

            embed.add_field(
                name="🎯 結果詳情",
                value=f"數字: {result_number}\n"
                f"顏色: {result_color}\n"
                f"奇偶: {'奇數' if is_odd else ('偶數' if is_even else '零')}\n"
                f"您的下注: {self.bet_type}\n"
                f"結果: {'🎉 中獎！' if won else '💔 未中獎'}",
                inline=True,
            )

            embed.add_field(
                name="💰 金錢變化",
                value=f"下注金額: -{self.bet_amount}🪙\n"
                f"獲得獎金: +{winnings}🪙\n"
                f"淨收益: {winnings - self.bet_amount:+}🪙",
                inline=True,
            )

            # 更新經濟狀態
            self.user_economy["coins"] = (
                self.user_economy.get("coins", 0) - self.bet_amount + winnings
            )

            # 創建新的視圖
            new_view = RouletteView(self.game_cog, self.user_economy)

            await interaction.response.edit_message(embed=embed, view=new_view)

            # 記錄統計
            await self.game_cog.economy_manager.increment_daily_games(
                interaction.user.id, interaction.guild.id
            )

            if won:
                await self.game_cog.economy_manager.increment_daily_wins(
                    interaction.user.id, interaction.guild.id
                )

        except Exception as e:
            logger.error(f"❌ 輪盤遊戲錯誤: {e}")
            await interaction.response.send_message("❌ 遊戲時發生錯誤。", ephemeral=True)


class NumberSelectView(ui.View):
    """數字選擇視圖"""

    def __init__(self, parent_view):
        super().__init__(timeout=60)
        self.parent_view = parent_view

    @ui.select(
        placeholder="選擇數字 (0-36)...",
        options=[discord.SelectOption(label=str(i), value=str(i)) for i in range(0, 37)][
            :25
        ],  # Discord 限制最多25個選項
        row=0,
    )
    async def number_select(self, interaction: discord.Interaction, select: ui.Select):
        """選擇數字"""
        self.parent_view.bet_value = int(select.values[0])
        await self.parent_view._update_bet_display(interaction)


class TriviaView(ui.View):
    """問答競賽視圖"""

    def __init__(self, game_cog):
        super().__init__(timeout=300)
        self.game_cog = game_cog
        self.questions = [
            {
                "question": "Python 是什麼時候發布的？",
                "answers": ["1989", "1991", "1995", "2000"],
                "correct": 1,
                "difficulty": "medium",
            },
            {
                "question": "Discord 是用什麼程式語言開發的？",
                "answers": ["Python", "JavaScript", "Elixir", "Go"],
                "correct": 2,
                "difficulty": "hard",
            },
            {
                "question": "HTTP 狀態碼 404 代表什麼？",
                "answers": ["伺服器錯誤", "未找到", "禁止訪問", "請求超時"],
                "correct": 1,
                "difficulty": "easy",
            },
            {
                "question": "哪個不是資料庫管理系統？",
                "answers": ["MySQL", "PostgreSQL", "Redis", "Apache"],
                "correct": 3,
                "difficulty": "medium",
            },
        ]
        self.current_question = None

    @ui.button(label="🎯 開始問答", style=discord.ButtonStyle.primary)
    async def start_trivia(self, interaction: discord.Interaction, button: ui.Button):
        """開始問答"""
        try:
            # 隨機選擇問題
            self.current_question = random.choice(self.questions)

            embed = EmbedBuilder.build(
                title="🧠 問答競賽", description=self.current_question["question"], color=0x4169E1
            )

            # 添加答案選項
            answers_text = ""
            for i, answer in enumerate(self.current_question["answers"], 1):
                answers_text += f"{i}️⃣ {answer}\n"

            embed.add_field(name="📝 選項", value=answers_text, inline=False)

            embed.add_field(
                name="ℹ️ 說明",
                value=f"難度: {self.current_question['difficulty'].title()}\n點擊下方按鈕選擇答案",
                inline=False,
            )

            # 創建答案選擇視圖
            view = TriviaAnswerView(self.game_cog, self.current_question)

            await interaction.response.edit_message(embed=embed, view=view)

        except Exception as e:
            logger.error(f"❌ 開始問答錯誤: {e}")
            await interaction.response.send_message("❌ 開始問答時發生錯誤。", ephemeral=True)


class TriviaAnswerView(ui.View):
    """問答答案選擇視圖"""

    def __init__(self, game_cog, question_data):
        super().__init__(timeout=60)
        self.game_cog = game_cog
        self.question_data = question_data

    @ui.button(label="1️⃣", style=discord.ButtonStyle.secondary)
    async def answer_1(self, interaction: discord.Interaction, button: ui.Button):
        await self._check_answer(interaction, 0)

    @ui.button(label="2️⃣", style=discord.ButtonStyle.secondary)
    async def answer_2(self, interaction: discord.Interaction, button: ui.Button):
        await self._check_answer(interaction, 1)

    @ui.button(label="3️⃣", style=discord.ButtonStyle.secondary)
    async def answer_3(self, interaction: discord.Interaction, button: ui.Button):
        await self._check_answer(interaction, 2)

    @ui.button(label="4️⃣", style=discord.ButtonStyle.secondary)
    async def answer_4(self, interaction: discord.Interaction, button: ui.Button):
        await self._check_answer(interaction, 3)

    async def _check_answer(self, interaction: discord.Interaction, selected_index: int):
        """檢查答案"""
        try:
            correct_index = self.question_data["correct"]
            is_correct = selected_index == correct_index
            difficulty = self.question_data["difficulty"]

            # 計算獎勵
            base_reward = {"easy": 20, "medium": 35, "hard": 50}
            reward = base_reward.get(difficulty, 20)

            if is_correct:
                # 發放獎勵
                await self.game_cog.economy_manager.add_coins(
                    interaction.user.id, interaction.guild.id, reward
                )
                await self.game_cog.economy_manager.add_experience(
                    interaction.user.id, interaction.guild.id, reward // 2
                )

                embed = EmbedBuilder.build(
                    title="🎉 答對了！", description=f"恭喜您答對了問題！", color=0x00FF00
                )

                embed.add_field(
                    name="🏆 獲得獎勵",
                    value=f"💰 金幣: {reward}🪙\n⭐ 經驗: {reward // 2}",
                    inline=True,
                )

                # 記錄勝利
                await self.game_cog.economy_manager.increment_daily_wins(
                    interaction.user.id, interaction.guild.id
                )
            else:
                embed = EmbedBuilder.build(
                    title="💔 答錯了！", description=f"很遺憾答錯了。", color=0xFF0000
                )

                embed.add_field(
                    name="📚 正確答案",
                    value=f"{self.question_data['answers'][correct_index]}",
                    inline=True,
                )

            embed.add_field(
                name="📊 問題資訊",
                value=f"您的答案: {self.question_data['answers'][selected_index]}\n"
                f"正確答案: {self.question_data['answers'][correct_index]}\n"
                f"難度: {difficulty.title()}",
                inline=False,
            )

            # 記錄遊戲統計
            await self.game_cog.economy_manager.increment_daily_games(
                interaction.user.id, interaction.guild.id
            )

            # 創建新的問答視圖
            new_view = TriviaView(self.game_cog)

            await interaction.response.edit_message(embed=embed, view=new_view)

        except Exception as e:
            logger.error(f"❌ 檢查答案錯誤: {e}")
            await interaction.response.send_message("❌ 檢查答案時發生錯誤。", ephemeral=True)


class DiceGameView(ui.View):
    """骰子遊戲視圖"""

    def __init__(self, game_cog, user_economy: Dict[str, Any]):
        super().__init__(timeout=180)
        self.game_cog = game_cog
        self.user_economy = user_economy
        self.bet_amount = 30
        self.prediction = None

    @ui.select(
        placeholder="選擇預測...",
        options=[
            discord.SelectOption(label="小 (3-8)", value="small", emoji="⬇️"),
            discord.SelectOption(label="大 (9-18)", value="big", emoji="⬆️"),
            discord.SelectOption(label="豹子 (相同點數)", value="triple", emoji="💎"),
            discord.SelectOption(label="對子 (兩個相同)", value="pair", emoji="👥"),
            discord.SelectOption(label="順子 (連續數字)", value="straight", emoji="📈"),
        ],
        row=0,
    )
    async def prediction_select(self, interaction: discord.Interaction, select: ui.Select):
        """選擇預測類型"""
        self.prediction = select.values[0]
        await self._update_display(interaction)

    @ui.button(label="🔼 增加下注", style=discord.ButtonStyle.secondary, row=1)
    async def increase_bet(self, interaction: discord.Interaction, button: ui.Button):
        max_coins = self.user_economy.get("coins", 0)
        if self.bet_amount < min(300, max_coins):
            self.bet_amount = min(self.bet_amount + 30, min(300, max_coins))
            await self._update_display(interaction)
        else:
            await interaction.response.send_message("❌ 已達到最大下注金額！", ephemeral=True)

    @ui.button(label="🔽 減少下注", style=discord.ButtonStyle.secondary, row=1)
    async def decrease_bet(self, interaction: discord.Interaction, button: ui.Button):
        if self.bet_amount > 30:
            self.bet_amount = max(self.bet_amount - 30, 30)
            await self._update_display(interaction)
        else:
            await interaction.response.send_message("❌ 已達到最小下注金額！", ephemeral=True)

    @ui.button(label="🎲 擲骰子", style=discord.ButtonStyle.primary, row=2)
    async def roll_dice(self, interaction: discord.Interaction, button: ui.Button):
        """擲骰子"""
        try:
            if not self.prediction:
                await interaction.response.send_message("❌ 請先選擇預測類型！", ephemeral=True)
                return

            if self.user_economy.get("coins", 0) < self.bet_amount:
                await interaction.response.send_message("❌ 金幣不足！", ephemeral=True)
                return

            # 扣除下注金額
            await self.game_cog.economy_manager.add_coins(
                interaction.user.id, interaction.guild.id, -self.bet_amount
            )

            # 擲三顆骰子
            dice = [random.randint(1, 6) for _ in range(3)]
            total = sum(dice)

            # 判斷結果
            won = False
            multiplier = 0
            result_description = ""

            if self.prediction == "small" and 3 <= total <= 8:
                won = True
                multiplier = 2
                result_description = "小點數命中！"
            elif self.prediction == "big" and 9 <= total <= 18:
                won = True
                multiplier = 2
                result_description = "大點數命中！"
            elif self.prediction == "triple" and len(set(dice)) == 1:
                won = True
                multiplier = 10
                result_description = "豹子！三個相同！"
            elif self.prediction == "pair" and len(set(dice)) == 2:
                won = True
                multiplier = 3
                result_description = "對子！兩個相同！"
            elif self.prediction == "straight":
                sorted_dice = sorted(dice)
                if (
                    sorted_dice == [1, 2, 3]
                    or sorted_dice == [2, 3, 4]
                    or sorted_dice == [3, 4, 5]
                    or sorted_dice == [4, 5, 6]
                ):
                    won = True
                    multiplier = 5
                    result_description = "順子！連續數字！"

            # 計算獎勵
            winnings = 0
            if won:
                winnings = self.bet_amount * multiplier
                await self.game_cog.economy_manager.add_coins(
                    interaction.user.id, interaction.guild.id, winnings
                )

            # 骰子表情
            dice_emojis = {1: "⚀", 2: "⚁", 3: "⚂", 4: "⚃", 5: "⚄", 6: "⚅"}
            dice_display = " ".join([dice_emojis[d] for d in dice])

            # 創建結果嵌入
            embed = EmbedBuilder.build(
                title="🎲 骰子遊戲結果",
                description=f"骰子結果: {dice_display}\n總點數: **{total}**",
                color=0x00FF00 if won else 0xFF0000,
            )

            embed.add_field(
                name="🎯 預測結果",
                value=f"您的預測: {self._get_prediction_name(self.prediction)}\n"
                f"實際結果: {dice} (總和: {total})\n"
                f"結果: {'🎉 ' + result_description if won else '💔 未命中'}",
                inline=True,
            )

            embed.add_field(
                name="💰 金錢變化",
                value=f"下注金額: -{self.bet_amount}🪙\n"
                f"獲得獎金: +{winnings}🪙\n"
                f"淨收益: {winnings - self.bet_amount:+}🪙",
                inline=True,
            )

            # 更新經濟狀態
            self.user_economy["coins"] = (
                self.user_economy.get("coins", 0) - self.bet_amount + winnings
            )

            # 創建新的視圖
            new_view = DiceGameView(self.game_cog, self.user_economy)

            await interaction.response.edit_message(embed=embed, view=new_view)

            # 記錄統計
            await self.game_cog.economy_manager.increment_daily_games(
                interaction.user.id, interaction.guild.id
            )

            if won:
                await self.game_cog.economy_manager.increment_daily_wins(
                    interaction.user.id, interaction.guild.id
                )

        except Exception as e:
            logger.error(f"❌ 骰子遊戲錯誤: {e}")
            await interaction.response.send_message("❌ 遊戲時發生錯誤。", ephemeral=True)

    async def _update_display(self, interaction: discord.Interaction):
        """更新顯示"""
        try:
            prediction_names = {
                "small": "⬇️ 小 (3-8)",
                "big": "⬆️ 大 (9-18)",
                "triple": "💎 豹子",
                "pair": "👥 對子",
                "straight": "📈 順子",
            }

            embed = EmbedBuilder.build(
                title="🎲 骰子遊戲", description="設定您的預測和下注金額！", color=0x32CD32
            )

            embed.add_field(
                name="💰 下注資訊",
                value=f"金額: {self.bet_amount}🪙\n"
                f"預測: {prediction_names.get(self.prediction, '未選擇')}",
                inline=True,
            )

            embed.add_field(
                name="💳 您的金幣", value=f"{self.user_economy.get('coins', 0):,}🪙", inline=True
            )

            embed.add_field(
                name="🎯 賠率說明",
                value="小/大: 2倍\n對子: 3倍\n順子: 5倍\n豹子: 10倍",
                inline=True,
            )

            await interaction.response.edit_message(embed=embed, view=self)

        except Exception as e:
            logger.error(f"❌ 更新骰子顯示錯誤: {e}")

    def _get_prediction_name(self, prediction: str) -> str:
        """獲取預測名稱"""
        names = {
            "small": "小 (3-8)",
            "big": "大 (9-18)",
            "triple": "豹子",
            "pair": "對子",
            "straight": "順子",
        }
        return names.get(prediction, "未知")
