# bot/views/entertainment_views.py - 娛樂模組互動視圖
"""
Discord Bot 娛樂模組互動視圖組件
使用 Discord UI 組件提供豐富的遊戲體驗
"""

import asyncio
import random

import discord

from bot.utils.embed_builder import EmbedBuilder


class EntertainmentMenuView(discord.ui.View):
    """娛樂中心主菜單視圖"""

    def __init__(self, cog, user_id: int):
        super().__init__(timeout=300)  # 5分鐘超時
        self.cog = cog
        self.user_id = user_id

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        """確保只有原始用戶可以使用"""
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("這不是您的遊戲面板！", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="🔢 猜數字", style=discord.ButtonStyle.primary, row=0)
    async def guess_number_game(self, interaction: discord.Interaction, button: discord.ui.Button):
        """猜數字遊戲"""
        view = GuessNumberView(self.cog, self.user_id)
        embed = view.create_game_embed()
        await interaction.response.edit_message(embed=embed, view=view)

    @discord.ui.button(label="✂️ 剪刀石頭布", style=discord.ButtonStyle.primary, row=0)
    async def rock_paper_scissors(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        """剪刀石頭布遊戲"""
        view = RockPaperScissorsView(self.cog, self.user_id)
        embed = view.create_game_embed()
        await interaction.response.edit_message(embed=embed, view=view)

    @discord.ui.button(label="🪙 拋硬幣", style=discord.ButtonStyle.primary, row=0)
    async def coin_flip(self, interaction: discord.Interaction, button: discord.ui.Button):
        """拋硬幣遊戲"""
        view = CoinFlipView(self.cog, self.user_id)
        embed = view.create_game_embed()
        await interaction.response.edit_message(embed=embed, view=view)

    @discord.ui.button(label="🎲 骰子遊戲", style=discord.ButtonStyle.primary, row=0)
    async def dice_roll(self, interaction: discord.Interaction, button: discord.ui.Button):
        """骰子遊戲"""
        view = DiceRollView(self.cog, self.user_id)
        embed = view.create_game_embed()
        await interaction.response.edit_message(embed=embed, view=view)

    @discord.ui.button(label="❓ 真心話大冒險", style=discord.ButtonStyle.secondary, row=1)
    async def truth_dare(self, interaction: discord.Interaction, button: discord.ui.Button):
        """真心話大冒險"""
        view = TruthDareView(self.cog, self.user_id)
        embed = view.create_game_embed()
        await interaction.response.edit_message(embed=embed, view=view)

    @discord.ui.button(label="🧠 知識問答", style=discord.ButtonStyle.secondary, row=1)
    async def quiz_game(self, interaction: discord.Interaction, button: discord.ui.Button):
        """知識問答遊戲"""
        view = QuizView(self.cog, self.user_id)
        embed = view.create_game_embed()
        await interaction.response.edit_message(embed=embed, view=view)

    @discord.ui.button(label="🎮 小遊戲合集", style=discord.ButtonStyle.secondary, row=1)
    async def mini_games(self, interaction: discord.Interaction, button: discord.ui.Button):
        """小遊戲合集"""
        view = MiniGameView(self.cog, self.user_id)
        embed = view.create_game_embed()
        await interaction.response.edit_message(embed=embed, view=view)

    @discord.ui.button(label="🏆 排行榜", style=discord.ButtonStyle.secondary, row=1)
    async def leaderboard(self, interaction: discord.Interaction, button: discord.ui.Button):
        """顯示排行榜"""
        view = GameLeaderboardView(self.cog)
        embed = await view.create_leaderboard_embed()
        await interaction.response.edit_message(embed=embed, view=view)

    @discord.ui.button(label="🔙 返回", style=discord.ButtonStyle.danger, row=2)
    async def back_to_menu(self, interaction: discord.Interaction, button: discord.ui.Button):
        """返回主菜單"""
        await interaction.response.edit_message(view=None)
        self.stop()


class GuessNumberView(discord.ui.View):
    """猜數字遊戲視圖"""

    def __init__(self, cog, user_id: int):
        super().__init__(timeout=180)
        self.cog = cog
        self.user_id = user_id
        self.target_number = random.randint(1, 100)
        self.attempts = 0
        self.max_attempts = 7
        self.game_over = False

    def create_game_embed(self) -> discord.Embed:
        """創建遊戲嵌入"""
        embed = EmbedBuilder.create_info_embed(
            "🔢 猜數字遊戲", "我想了一個 1 到 100 之間的數字，你能猜中嗎？"
        )

        embed.add_field(
            name="🎯 遊戲規則",
            value=f"• 數字範圍：1-100\n• 最多嘗試：{self.max_attempts} 次\n• 我會告訴你數字的大小提示",
            inline=False,
        )

        embed.add_field(
            name="📊 當前狀態",
            value=f"剩餘嘗試：{self.max_attempts - self.attempts} 次",
            inline=True,
        )

        return embed

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("這不是您的遊戲！", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="1-25", style=discord.ButtonStyle.primary, row=0)
    async def guess_1_25(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.make_guess(interaction, random.randint(1, 25))

    @discord.ui.button(label="26-50", style=discord.ButtonStyle.primary, row=0)
    async def guess_26_50(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.make_guess(interaction, random.randint(26, 50))

    @discord.ui.button(label="51-75", style=discord.ButtonStyle.primary, row=0)
    async def guess_51_75(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.make_guess(interaction, random.randint(51, 75))

    @discord.ui.button(label="76-100", style=discord.ButtonStyle.primary, row=0)
    async def guess_76_100(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.make_guess(interaction, random.randint(76, 100))

    @discord.ui.button(label="🎲 隨機猜測", style=discord.ButtonStyle.secondary, row=1)
    async def random_guess(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.make_guess(interaction, random.randint(1, 100))

    @discord.ui.button(label="🔙 返回菜單", style=discord.ButtonStyle.danger, row=1)
    async def back_to_menu(self, interaction: discord.Interaction, button: discord.ui.Button):
        view = EntertainmentMenuView(self.cog, self.user_id)
        await self.cog.get_user_stats(self.user_id)
        embed = EmbedBuilder.create_info_embed("🎮 娛樂中心", "選擇您想要的遊戲：")
        await interaction.response.edit_message(embed=embed, view=view)

    async def make_guess(self, interaction: discord.Interaction, guess: int):
        """處理猜測"""
        if self.game_over:
            return

        self.attempts += 1

        if guess == self.target_number:
            # 猜中了！
            points = max(10, 50 - (self.attempts * 5))
            await self.cog.update_user_stats(self.user_id, "guess_number", True, points)

            embed = EmbedBuilder.create_success_embed(
                "🎉 恭喜猜中！",
                f"數字就是 **{self.target_number}**！\n你用了 {self.attempts} 次嘗試",
            )
            embed.add_field(name="獲得積分", value=f"+{points} 分", inline=True)
            self.game_over = True

        elif self.attempts >= self.max_attempts:
            # 用完嘗試次數
            await self.cog.update_user_stats(self.user_id, "guess_number", False, 0)

            embed = EmbedBuilder.create_error_embed(
                "💥 遊戲結束",
                f"很遺憾，正確答案是 **{self.target_number}**\n下次加油！",
            )
            self.game_over = True

        else:
            # 繼續遊戲
            hint = "太大了！" if guess > self.target_number else "太小了！"
            embed = EmbedBuilder.create_warning_embed(
                f"第 {self.attempts} 次嘗試", f"你猜的是 **{guess}**，{hint}"
            )
            embed.add_field(
                name="📊 狀態",
                value=f"剩餘嘗試：{self.max_attempts - self.attempts} 次",
                inline=True,
            )

        if self.game_over:
            # 禁用所有按鈕
            for item in self.children:
                if isinstance(item, discord.ui.Button) and item.label != "🔙 返回菜單":
                    item.disabled = True

        await interaction.response.edit_message(embed=embed, view=self)


class RockPaperScissorsView(discord.ui.View):
    """剪刀石頭布遊戲視圖"""

    def __init__(self, cog, user_id: int):
        super().__init__(timeout=180)
        self.cog = cog
        self.user_id = user_id
        self.games_played = 0
        self.user_score = 0
        self.bot_score = 0
        self.max_games = 5

    def create_game_embed(self) -> discord.Embed:
        """創建遊戲嵌入"""
        embed = EmbedBuilder.create_info_embed("✂️ 剪刀石頭布", f"五局三勝制！選擇你的出招：")

        embed.add_field(
            name="📊 當前比分",
            value=f"你：{self.user_score} | Bot：{self.bot_score}",
            inline=True,
        )

        embed.add_field(name="🎯 局數", value=f"{self.games_played}/{self.max_games}", inline=True)

        return embed

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("這不是您的遊戲！", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="✂️ 剪刀", style=discord.ButtonStyle.primary, emoji="✂️")
    async def scissors(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.play_round(interaction, "scissors", "✂️")

    @discord.ui.button(label="🗿 石頭", style=discord.ButtonStyle.primary, emoji="🗿")
    async def rock(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.play_round(interaction, "rock", "🗿")

    @discord.ui.button(label="📄 布", style=discord.ButtonStyle.primary, emoji="📄")
    async def paper(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.play_round(interaction, "paper", "📄")

    @discord.ui.button(label="🔙 返回菜單", style=discord.ButtonStyle.danger, row=1)
    async def back_to_menu(self, interaction: discord.Interaction, button: discord.ui.Button):
        view = EntertainmentMenuView(self.cog, self.user_id)
        embed = EmbedBuilder.create_info_embed("🎮 娛樂中心", "選擇您想要的遊戲：")
        await interaction.response.edit_message(embed=embed, view=view)

    async def play_round(self, interaction: discord.Interaction, user_choice: str, user_emoji: str):
        """進行一輪遊戲"""
        choices = {"scissors": "✂️", "rock": "🗿", "paper": "📄"}
        bot_choice = random.choice(list(choices.keys()))
        bot_emoji = choices[bot_choice]

        # 判斷勝負
        result = self.determine_winner(user_choice, bot_choice)

        if result == "user":
            self.user_score += 1
            result_text = "🎉 你贏了這一局！"
            result_color = discord.Color.green()
        elif result == "bot":
            self.bot_score += 1
            result_text = "😅 Bot 贏了這一局！"
            result_color = discord.Color.red()
        else:
            result_text = "🤝 平局！"
            result_color = discord.Color.yellow()

        self.games_played += 1

        # 創建結果嵌入
        embed = discord.Embed(title="✂️ 剪刀石頭布", color=result_color)
        embed.add_field(
            name="本局結果",
            value=f"你：{user_emoji} vs Bot：{bot_emoji}\n{result_text}",
            inline=False,
        )
        embed.add_field(
            name="📊 總比分",
            value=f"你：{self.user_score} | Bot：{self.bot_score}",
            inline=True,
        )
        embed.add_field(name="🎯 局數", value=f"{self.games_played}/{self.max_games}", inline=True)

        # 檢查遊戲是否結束
        if (
            self.games_played >= self.max_games
            or self.user_score > self.max_games // 2
            or self.bot_score > self.max_games // 2
        ):
            winner = (
                "user"
                if self.user_score > self.bot_score
                else "bot" if self.bot_score > self.user_score else "tie"
            )

            if winner == "user":
                embed.add_field(name="🏆 最終結果", value="恭喜你獲得勝利！", inline=False)
                points = 30
                await self.cog.update_user_stats(self.user_id, "rock_paper_scissors", True, points)
            elif winner == "bot":
                embed.add_field(name="💔 最終結果", value="很遺憾，Bot 獲勝了！", inline=False)
                await self.cog.update_user_stats(self.user_id, "rock_paper_scissors", False, 0)
            else:
                embed.add_field(name="🤝 最終結果", value="平局！", inline=False)
                points = 10
                await self.cog.update_user_stats(self.user_id, "rock_paper_scissors", False, points)

            # 禁用遊戲按鈕
            for item in self.children:
                if isinstance(item, discord.ui.Button) and item.label != "🔙 返回菜單":
                    item.disabled = True

        await interaction.response.edit_message(embed=embed, view=self)

    def determine_winner(self, user_choice: str, bot_choice: str) -> str:
        """判斷勝負"""
        if user_choice == bot_choice:
            return "tie"

        winning_combinations = {
            "rock": "scissors",
            "paper": "rock",
            "scissors": "paper",
        }

        if winning_combinations[user_choice] == bot_choice:
            return "user"
        else:
            return "bot"


class CoinFlipView(discord.ui.View):
    """拋硬幣遊戲視圖"""

    def __init__(self, cog, user_id: int):
        super().__init__(timeout=180)
        self.cog = cog
        self.user_id = user_id
        self.bet_amount = 10

    def create_game_embed(self) -> discord.Embed:
        embed = EmbedBuilder.create_info_embed("🪙 拋硬幣遊戲", "選擇正面或反面，猜對了獲得積分！")
        embed.add_field(name="賭注", value=f"{self.bet_amount} 積分", inline=True)
        embed.add_field(name="獎勵", value=f"{self.bet_amount * 2} 積分", inline=True)
        return embed

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("這不是您的遊戲！", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="🪙 正面", style=discord.ButtonStyle.primary)
    async def heads(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.flip_coin(interaction, "heads")

    @discord.ui.button(label="⚫ 反面", style=discord.ButtonStyle.primary)
    async def tails(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.flip_coin(interaction, "tails")

    @discord.ui.button(label="🔙 返回菜單", style=discord.ButtonStyle.danger)
    async def back_to_menu(self, interaction: discord.Interaction, button: discord.ui.Button):
        view = EntertainmentMenuView(self.cog, self.user_id)
        embed = EmbedBuilder.create_info_embed("🎮 娛樂中心", "選擇您想要的遊戲：")
        await interaction.response.edit_message(embed=embed, view=view)

    async def flip_coin(self, interaction: discord.Interaction, choice: str):
        # 模擬拋硬幣動畫
        embed = EmbedBuilder.create_info_embed("🪙 拋硬幣中...", "硬幣在空中旋轉...")
        await interaction.response.edit_message(embed=embed, view=None)

        await asyncio.sleep(2)  # 增加懸念

        result = random.choice(["heads", "tails"])
        won = choice == result

        result_emoji = "🪙" if result == "heads" else "⚫"
        result_text = "正面" if result == "heads" else "反面"

        if won:
            points = self.bet_amount * 2
            await self.cog.update_user_stats(self.user_id, "coin_flip", True, points)
            embed = EmbedBuilder.create_success_embed(
                f"🎉 猜對了！硬幣是{result_text} {result_emoji}",
                f"獲得 {points} 積分！",
            )
        else:
            await self.cog.update_user_stats(self.user_id, "coin_flip", False, 0)
            embed = EmbedBuilder.create_error_embed(
                f"😅 猜錯了！硬幣是{result_text} {result_emoji}", "下次再來！"
            )

        # 添加再玩一次按鈕
        new_view = CoinFlipView(self.cog, self.user_id)
        embed.add_field(name="想再玩一次嗎？", value="點擊下方按鈕繼續遊戲", inline=False)

        await interaction.edit_original_response(embed=embed, view=new_view)


class DiceRollView(discord.ui.View):
    """骰子遊戲視圖"""

    def __init__(self, cog, user_id: int):
        super().__init__(timeout=180)
        self.cog = cog
        self.user_id = user_id

    def create_game_embed(self) -> discord.Embed:
        embed = EmbedBuilder.create_info_embed("🎲 骰子遊戲", "擲骰子比大小！選擇骰子數量：")
        embed.add_field(
            name="🎯 遊戲規則",
            value="• 擲出的點數總和越大越好\n• 單顆骰子：1-6點\n• 雙骰子：2-12點\n• 三骰子：3-18點",
            inline=False,
        )
        return embed

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("這不是您的遊戲！", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="🎲 單骰子", style=discord.ButtonStyle.primary)
    async def single_dice(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.roll_dice(interaction, 1)

    @discord.ui.button(label="🎲🎲 雙骰子", style=discord.ButtonStyle.primary)
    async def double_dice(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.roll_dice(interaction, 2)

    @discord.ui.button(label="🎲🎲🎲 三骰子", style=discord.ButtonStyle.primary)
    async def triple_dice(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.roll_dice(interaction, 3)

    @discord.ui.button(label="🔙 返回菜單", style=discord.ButtonStyle.danger, row=1)
    async def back_to_menu(self, interaction: discord.Interaction, button: discord.ui.Button):
        view = EntertainmentMenuView(self.cog, self.user_id)
        embed = EmbedBuilder.create_info_embed("🎮 娛樂中心", "選擇您想要的遊戲：")
        await interaction.response.edit_message(embed=embed, view=view)

    async def roll_dice(self, interaction: discord.Interaction, dice_count: int):
        # 擲骰子動畫
        embed = EmbedBuilder.create_info_embed("🎲 擲骰中...", "骰子正在滾動...")
        await interaction.response.edit_message(embed=embed, view=None)

        await asyncio.sleep(1.5)

        # 擲骰子
        user_rolls = [random.randint(1, 6) for _ in range(dice_count)]
        bot_rolls = [random.randint(1, 6) for _ in range(dice_count)]

        user_total = sum(user_rolls)
        bot_total = sum(bot_rolls)

        # 骰子表情符號
        dice_emojis = ["", "⚀", "⚁", "⚂", "⚃", "⚄", "⚅"]
        user_dice_display = " ".join([dice_emojis[roll] for roll in user_rolls])
        bot_dice_display = " ".join([dice_emojis[roll] for roll in bot_rolls])

        # 判斷勝負
        if user_total > bot_total:
            result = "win"
            title = "🎉 你贏了！"
            color = discord.Color.green()
            points = dice_count * 15
        elif user_total < bot_total:
            result = "lose"
            title = "😅 你輸了！"
            color = discord.Color.red()
            points = 0
        else:
            result = "tie"
            title = "🤝 平局！"
            color = discord.Color.yellow()
            points = dice_count * 5

        embed = discord.Embed(title=title, color=color)
        embed.add_field(
            name="你的骰子",
            value=f"{user_dice_display}\n總計：{user_total}",
            inline=True,
        )
        embed.add_field(
            name="Bot的骰子",
            value=f"{bot_dice_display}\n總計：{bot_total}",
            inline=True,
        )

        if points > 0:
            embed.add_field(name="獲得積分", value=f"+{points} 分", inline=False)

        await self.cog.update_user_stats(self.user_id, "dice_roll", result == "win", points)

        # 再玩一次視圖
        new_view = DiceRollView(self.cog, self.user_id)
        await interaction.edit_original_response(embed=embed, view=new_view)


class TruthDareView(discord.ui.View):
    """真心話大冒險視圖"""

    def __init__(self, cog, user_id: int):
        super().__init__(timeout=300)
        self.cog = cog
        self.user_id = user_id

        # 真心話問題庫
        self.truth_questions = [
            "你最尷尬的經歷是什麼？",
            "你最害怕什麼？",
            "你的第一個暗戀對象是誰？",
            "你做過最瘋狂的事情是什麼？",
            "你最大的秘密是什麼？",
            "你最不想讓人知道的事情是什麼？",
            "你覺得自己最大的缺點是什麼？",
            "你最想改變自己的哪一點？",
            "你最珍惜的回憶是什麼？",
            "你最後悔的決定是什麼？",
        ]

        # 大冒險任務庫
        self.dare_challenges = [
            "在頻道中分享一張你的寵物照片（如果有的話）",
            "用表情符號描述你今天的心情",
            "說出三個你欣賞的人",
            "分享一個你最喜歡的笑話",
            "用五個詞描述你自己",
            "說出你最喜歡的一首歌",
            "分享一個你的小技能",
            "說出你最想去的地方",
            "用表情符號寫一句話",
            "說出你最感謝的一個人",
        ]

    def create_game_embed(self) -> discord.Embed:
        embed = EmbedBuilder.create_info_embed("❓ 真心話大冒險", "選擇真心話或大冒險！")
        embed.add_field(name="🤔 真心話", value="回答一個私人問題", inline=True)
        embed.add_field(name="😎 大冒險", value="完成一個有趣的挑戰", inline=True)
        return embed

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("這不是您的遊戲！", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="🤔 真心話", style=discord.ButtonStyle.primary)
    async def truth(self, interaction: discord.Interaction, button: discord.ui.Button):
        question = random.choice(self.truth_questions)
        embed = EmbedBuilder.create_info_embed("🤔 真心話時間", question)
        embed.add_field(name="提示", value="勇敢地說出真相吧！", inline=False)

        await self.cog.update_user_stats(self.user_id, "truth_dare", True, 5)

        new_view = TruthDareView(self.cog, self.user_id)
        await interaction.response.edit_message(embed=embed, view=new_view)

    @discord.ui.button(label="😎 大冒險", style=discord.ButtonStyle.primary)
    async def dare(self, interaction: discord.Interaction, button: discord.ui.Button):
        challenge = random.choice(self.dare_challenges)
        embed = EmbedBuilder.create_info_embed("😎 大冒險時間", challenge)
        embed.add_field(name="提示", value="接受挑戰，展現你的勇氣！", inline=False)

        await self.cog.update_user_stats(self.user_id, "truth_dare", True, 10)

        new_view = TruthDareView(self.cog, self.user_id)
        await interaction.response.edit_message(embed=embed, view=new_view)

    @discord.ui.button(label="🔙 返回菜單", style=discord.ButtonStyle.danger)
    async def back_to_menu(self, interaction: discord.Interaction, button: discord.ui.Button):
        view = EntertainmentMenuView(self.cog, self.user_id)
        embed = EmbedBuilder.create_info_embed("🎮 娛樂中心", "選擇您想要的遊戲：")
        await interaction.response.edit_message(embed=embed, view=view)


class QuizView(discord.ui.View):
    """知識問答視圖"""

    def __init__(self, cog, user_id: int):
        super().__init__(timeout=300)
        self.cog = cog
        self.user_id = user_id
        self.current_question = None
        self.score = 0
        self.question_count = 0
        self.max_questions = 5

        # 問題庫
        self.questions = [
            {
                "question": "世界上最高的山峰是？",
                "options": ["聖母峰", "K2峰", "干城章嘉峰", "洛子峰"],
                "correct": 0,
                "explanation": "聖母峰（珠穆朗瑪峰）高度為8,848.86公尺",
            },
            {
                "question": "Python 是哪一年發布的？",
                "options": ["1989", "1991", "1993", "1995"],
                "correct": 1,
                "explanation": "Python 由 Guido van Rossum 於1991年發布",
            },
            {
                "question": "日本的首都是？",
                "options": ["大阪", "京都", "東京", "橫濱"],
                "correct": 2,
                "explanation": "東京是日本的首都和最大城市",
            },
            {
                "question": "一年有多少天？",
                "options": ["364", "365", "366", "平年365天，閏年366天"],
                "correct": 3,
                "explanation": "一般年份365天，閏年366天",
            },
            {
                "question": "Discord 是什麼類型的平台？",
                "options": ["遊戲平台", "通訊平台", "購物平台", "學習平台"],
                "correct": 1,
                "explanation": "Discord 是一個專為社群設計的通訊平台",
            },
        ]

    def create_game_embed(self) -> discord.Embed:
        if self.current_question is None:
            embed = EmbedBuilder.create_info_embed(
                "🧠 知識問答", f"準備好測試你的知識了嗎？共 {self.max_questions} 題"
            )
            embed.add_field(name="積分規則", value="每答對一題得 20 分", inline=False)
        else:
            embed = EmbedBuilder.create_info_embed(
                f"🧠 問題 {self.question_count}/{self.max_questions}",
                self.current_question["question"],
            )
            embed.add_field(name="當前積分", value=f"{self.score} 分", inline=True)

        return embed

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("這不是您的遊戲！", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="🚀 開始問答", style=discord.ButtonStyle.success)
    async def start_quiz(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.next_question(interaction)

    @discord.ui.button(label="A", style=discord.ButtonStyle.secondary, row=1)
    async def option_a(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.answer_question(interaction, 0)

    @discord.ui.button(label="B", style=discord.ButtonStyle.secondary, row=1)
    async def option_b(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.answer_question(interaction, 1)

    @discord.ui.button(label="C", style=discord.ButtonStyle.secondary, row=1)
    async def option_c(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.answer_question(interaction, 2)

    @discord.ui.button(label="D", style=discord.ButtonStyle.secondary, row=1)
    async def option_d(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.answer_question(interaction, 3)

    @discord.ui.button(label="🔙 返回菜單", style=discord.ButtonStyle.danger, row=2)
    async def back_to_menu(self, interaction: discord.Interaction, button: discord.ui.Button):
        view = EntertainmentMenuView(self.cog, self.user_id)
        embed = EmbedBuilder.create_info_embed("🎮 娛樂中心", "選擇您想要的遊戲：")
        await interaction.response.edit_message(embed=embed, view=view)

    async def next_question(self, interaction: discord.Interaction):
        if self.question_count >= self.max_questions:
            await self.end_quiz(interaction)
            return

        self.question_count += 1
        self.current_question = random.choice(self.questions)

        embed = self.create_game_embed()

        # 更新選項按鈕
        options = ["A", "B", "C", "D"]
        for i, option in enumerate(options):
            button = discord.utils.get(self.children, label=option)
            if button:
                button.label = f"{option}: {self.current_question['options'][i]}"
                button.disabled = False

        # 隱藏開始按鈕
        start_button = discord.utils.get(self.children, label="🚀 開始問答")
        if start_button:
            start_button.disabled = True
            start_button.style = discord.ButtonStyle.secondary

        await interaction.response.edit_message(embed=embed, view=self)

    async def answer_question(self, interaction: discord.Interaction, choice: int):
        correct = choice == self.current_question["correct"]

        if correct:
            self.score += 20
            title = "🎉 答對了！"
            color = discord.Color.green()
        else:
            title = "❌ 答錯了！"
            color = discord.Color.red()

        correct_answer = self.current_question["options"][self.current_question["correct"]]

        embed = discord.Embed(title=title, color=color)
        embed.add_field(name="正確答案", value=f"{correct_answer}", inline=False)
        embed.add_field(name="解釋", value=self.current_question["explanation"], inline=False)
        embed.add_field(name="目前積分", value=f"{self.score} 分", inline=True)
        embed.add_field(
            name="進度",
            value=f"{self.question_count}/{self.max_questions}",
            inline=True,
        )

        # 禁用選項按鈕
        for button in self.children:
            if isinstance(button, discord.ui.Button) and button.label.startswith(
                ("A:", "B:", "C:", "D:")
            ):
                button.disabled = True

        await interaction.response.edit_message(embed=embed, view=self)

        # 等待後進入下一題
        await asyncio.sleep(3)
        if self.question_count < self.max_questions:
            await self.next_question(interaction)
        else:
            await self.end_quiz(interaction)

    async def end_quiz(self, interaction: discord.Interaction):
        percentage = (self.score / (self.max_questions * 20)) * 100

        if percentage >= 80:
            title = "🏆 優秀！"
            color = discord.Color.gold()
        elif percentage >= 60:
            title = "👍 不錯！"
            color = discord.Color.green()
        else:
            title = "📚 加油！"
            color = discord.Color.blue()

        embed = discord.Embed(title=f"{title} 問答結束", color=color)
        embed.add_field(name="最終得分", value=f"{self.score} 分", inline=True)
        embed.add_field(name="正確率", value=f"{percentage:.1f}%", inline=True)

        await self.cog.update_user_stats(self.user_id, "quiz", percentage >= 60, self.score)

        # 重置所有按鈕
        for button in self.children:
            if isinstance(button, discord.ui.Button) and button.label != "🔙 返回菜單":
                button.disabled = True

        try:
            await interaction.edit_original_response(embed=embed, view=self)
        except:
            await interaction.followup.edit_message(interaction.message.id, embed=embed, view=self)


class MiniGameView(discord.ui.View):
    """小遊戲合集視圖"""

    def __init__(self, cog, user_id: int):
        super().__init__(timeout=300)
        self.cog = cog
        self.user_id = user_id

    def create_game_embed(self) -> discord.Embed:
        embed = EmbedBuilder.create_info_embed("🎮 小遊戲合集", "選擇一個快速小遊戲：")

        embed.add_field(name="🎯 射箭遊戲", value="測試你的準確度", inline=True)
        embed.add_field(name="🧩 記憶遊戲", value="挑戰你的記憶力", inline=True)
        embed.add_field(name="🔤 文字遊戲", value="創造力和語言能力", inline=True)

        return embed

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("這不是您的遊戲！", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="🎯 射箭遊戲", style=discord.ButtonStyle.primary)
    async def archery_game(self, interaction: discord.Interaction, button: discord.ui.Button):
        # 簡單的射箭遊戲
        target_zones = [
            "❌ 脫靶",
            "⚪ 外圈 (1分)",
            "🔵 中圈 (3分)",
            "🔴 內圈 (5分)",
            "🎯 正中 (10分)",
        ]
        weights = [20, 30, 25, 15, 10]  # 機率權重

        result = random.choices(target_zones, weights=weights, k=1)[0]

        # 提取分數
        if "10分" in result:
            points = 10
        elif "5分" in result:
            points = 5
        elif "3分" in result:
            points = 3
        elif "1分" in result:
            points = 1
        else:
            points = 0

        embed = EmbedBuilder.create_info_embed("🏹 射箭結果", f"你射中了：{result}")
        if points > 0:
            embed.add_field(name="獲得積分", value=f"+{points} 分", inline=True)

        await self.cog.update_user_stats(self.user_id, "archery", points > 0, points)

        new_view = MiniGameView(self.cog, self.user_id)
        await interaction.response.edit_message(embed=embed, view=new_view)

    @discord.ui.button(label="🧩 記憶遊戲", style=discord.ButtonStyle.primary)
    async def memory_game(self, interaction: discord.Interaction, button: discord.ui.Button):
        # 生成隨機序列讓用戶記住
        sequence_length = random.randint(3, 6)
        emojis = ["🐶", "🐱", "🐭", "🐹", "🐰", "🦊", "🐻", "🐼"]
        sequence = [random.choice(emojis) for _ in range(sequence_length)]

        embed = EmbedBuilder.create_info_embed("🧩 記憶挑戰", f"記住這個序列：{''.join(sequence)}")
        embed.add_field(name="指示", value="記住後點擊完成按鈕！", inline=False)

        # 創建簡化的記憶遊戲（自動完成）
        await asyncio.sleep(1)

        # 隨機決定是否"記住"
        remembered = random.choice([True, False, True])  # 66% 成功率

        if remembered:
            points = sequence_length * 5
            result_embed = EmbedBuilder.create_success_embed(
                "🎉 記憶成功！", f"你成功記住了 {sequence_length} 個符號！"
            )
            result_embed.add_field(name="獲得積分", value=f"+{points} 分", inline=True)
        else:
            points = 0
            result_embed = EmbedBuilder.create_error_embed(
                "😅 記憶失敗", "沒關係，多練習就會進步的！"
            )

        await self.cog.update_user_stats(self.user_id, "memory", remembered, points)

        new_view = MiniGameView(self.cog, self.user_id)
        await interaction.response.edit_message(embed=result_embed, view=new_view)

    @discord.ui.button(label="🔤 文字遊戲", style=discord.ButtonStyle.primary)
    async def word_game(self, interaction: discord.Interaction, button: discord.ui.Button):
        # 隨機生成字母，讓用戶組詞
        letters = random.sample("ABCDEFGHIJKLMNOPQRSTUVWXYZ", 6)

        embed = EmbedBuilder.create_info_embed(
            "🔤 文字創造", f"用這些字母創造單詞：{''.join(letters)}"
        )
        embed.add_field(name="挑戰", value="想像你能組成什麼有趣的詞彙！", inline=False)

        # 自動給予積分（鼓勵創造力）
        points = 15
        await self.cog.update_user_stats(self.user_id, "word_game", True, points)

        embed.add_field(name="創意獎勵", value=f"+{points} 分", inline=True)

        new_view = MiniGameView(self.cog, self.user_id)
        await interaction.response.edit_message(embed=embed, view=new_view)

    @discord.ui.button(label="🔙 返回菜單", style=discord.ButtonStyle.danger)
    async def back_to_menu(self, interaction: discord.Interaction, button: discord.ui.Button):
        view = EntertainmentMenuView(self.cog, self.user_id)
        embed = EmbedBuilder.create_info_embed("🎮 娛樂中心", "選擇您想要的遊戲：")
        await interaction.response.edit_message(embed=embed, view=view)


class GameLeaderboardView(discord.ui.View):
    """遊戲排行榜視圖"""

    def __init__(self, cog):
        super().__init__(timeout=300)
        self.cog = cog

    async def create_leaderboard_embed(self) -> discord.Embed:
        """創建排行榜嵌入"""
        # 這個方法在實際的排行榜命令中會被調用
        embed = EmbedBuilder.create_info_embed("🏆 遊戲排行榜", "最強玩家排名")
        return embed

    @discord.ui.button(label="🔄 刷新排行榜", style=discord.ButtonStyle.primary)
    async def refresh_leaderboard(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        # 這裡會重新獲取排行榜數據
        embed = await self.create_leaderboard_embed()
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="📊 個人統計", style=discord.ButtonStyle.secondary)
    async def personal_stats(self, interaction: discord.Interaction, button: discord.ui.Button):
        stats = await self.cog.get_user_stats(interaction.user.id)

        embed = EmbedBuilder.create_info_embed(f"📊 {interaction.user.display_name} 的統計", "")

        win_rate = (stats["wins"] / stats["total_games"] * 100) if stats["total_games"] > 0 else 0
        embed.add_field(
            name="🎮 遊戲統計",
            value=f"總遊戲: {stats['total_games']}\n"
            f"勝利: {stats['wins']}\n"
            f"勝率: {win_rate:.1f}%\n"
            f"積分: {stats['points']}",
            inline=True,
        )

        await interaction.response.send_message(embed=embed, ephemeral=True)

    @discord.ui.button(label="🔙 返回娛樂中心", style=discord.ButtonStyle.danger)
    async def back_to_entertainment(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        view = EntertainmentMenuView(self.cog, interaction.user.id)
        embed = EmbedBuilder.create_info_embed("🎮 娛樂中心", "選擇您想要的遊戲：")
        await interaction.response.edit_message(embed=embed, view=view)
