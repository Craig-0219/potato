# bot/cogs/music_core.py - 音樂娛樂指令模組
"""
音樂娛樂指令模組 v2.2.0
提供音樂播放、歌詞查看、音樂問答等功能的Discord指令
"""

import discord
from discord.ext import commands
from discord import app_commands
from typing import Dict, List, Optional, Any, Tuple
import asyncio
import random
import time
from datetime import datetime, timezone

from bot.services.music_player import MusicPlayer, MusicSource, PlaybackState, RepeatMode
from bot.services.economy_manager import EconomyManager
from bot.utils.embed_builder import EmbedBuilder
from shared.cache_manager import cache_manager
from shared.prometheus_metrics import prometheus_metrics, track_command_execution
from shared.logger import logger

class MusicCog(commands.Cog):
    """音樂娛樂功能"""
    
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.music_player = MusicPlayer(bot)
        self.economy_manager = EconomyManager()
        
        # 音樂服務費用 (金幣)
        self.music_costs = {
            "search": 3,
            "lyrics": 5,
            "quiz": 8,
            "playlist_create": 10,
            "premium_features": 15
        }
        
        # 每日免費額度
        self.daily_free_quota = 20
        
        logger.info("🎵 音樂娛樂指令模組初始化完成")

    # ========== 基礎播放控制 ==========

    @app_commands.command(name="play", description="播放音樂")
    @app_commands.describe(query="搜尋關鍵詞或歌曲名稱")
    async def play_music(self, interaction: discord.Interaction, query: str):
        """播放音樂"""
        try:
            await interaction.response.defer()
            
            # 檢查語音頻道
            if not interaction.user.voice:
                await interaction.followup.send("❌ 請先加入語音頻道！", ephemeral=True)
                return
            
            voice_channel = interaction.user.voice.channel
            
            # 檢查使用權限
            can_use, cost_info = await self._check_usage_permission(
                interaction.user.id, interaction.guild.id, "search"
            )
            
            if not can_use:
                embed = EmbedBuilder.build(
                    title="❌ 使用受限",
                    description=cost_info["message"],
                    color=0xFF0000
                )
                await interaction.followup.send(embed=embed, ephemeral=True)
                return
            
            # 搜尋音樂
            tracks = await self.music_player.search_youtube(query, max_results=1)
            if not tracks:
                await interaction.followup.send("❌ 找不到相關音樂，請嘗試其他關鍵詞。", ephemeral=True)
                return
            
            track = tracks[0]
            track.requested_by = interaction.user.id
            
            # 獲取或創建音樂會話
            session = await self.music_player.get_session(interaction.guild.id)
            if not session:
                session = await self.music_player.create_session(
                    interaction.guild.id,
                    interaction.channel.id,
                    voice_channel.id
                )
            
            # 添加到播放佇列或直接播放
            if session.current_track is None:
                # 直接播放
                success = await self.music_player.play_track(interaction.guild.id, track)
                if success:
                    action = "🎵 開始播放"
                else:
                    await interaction.followup.send("❌ 播放失敗，請稍後再試。", ephemeral=True)
                    return
            else:
                # 添加到佇列
                await self.music_player.add_to_queue(interaction.guild.id, track)
                action = "➕ 已添加到播放佇列"
            
            # 扣除費用
            if cost_info["cost"] > 0:
                await self.economy_manager.add_coins(
                    interaction.user.id, interaction.guild.id, -cost_info["cost"]
                )
            
            # 記錄使用量
            await self._record_daily_usage(interaction.user.id)
            
            embed = EmbedBuilder.build(
                title=action,
                description=f"**{track.title}**\n{track.artist}",
                color=0x00FF00
            )
            
            embed.set_thumbnail(url=track.thumbnail)
            
            embed.add_field(
                name="📊 播放資訊",
                value=f"時長: {self._format_duration(track.duration)}\n"
                      f"來源: {track.source.value.title()}\n"
                      f"請求者: {interaction.user.mention}" +
                      (f"\n消耗金幣: {cost_info['cost']}🪙" if cost_info["cost"] > 0 else ""),
                inline=True
            )
            
            # 顯示佇列資訊
            if session.queue:
                embed.add_field(
                    name="📋 播放佇列",
                    value=f"佇列中有 {len(session.queue)} 首歌曲",
                    inline=True
                )
            
            await interaction.followup.send(embed=embed)
            
            # 記錄指標
            track_command_execution("play", interaction.guild.id)
            
        except Exception as e:
            logger.error(f"❌ 播放音樂錯誤: {e}")
            await interaction.followup.send("❌ 播放音樂時發生錯誤，請稍後再試。", ephemeral=True)

    @app_commands.command(name="pause", description="暫停音樂播放")
    async def pause_music(self, interaction: discord.Interaction):
        """暫停音樂"""
        try:
            success = await self.music_player.pause_playback(interaction.guild.id)
            
            if success:
                embed = EmbedBuilder.build(
                    title="⏸️ 音樂已暫停",
                    description="使用 `/resume` 繼續播放",
                    color=0xFFAA00
                )
            else:
                embed = EmbedBuilder.build(
                    title="❌ 暫停失敗",
                    description="目前沒有正在播放的音樂",
                    color=0xFF0000
                )
            
            await interaction.response.send_message(embed=embed, ephemeral=True)
            
        except Exception as e:
            logger.error(f"❌ 暫停音樂錯誤: {e}")
            await interaction.response.send_message("❌ 暫停音樂時發生錯誤。", ephemeral=True)

    @app_commands.command(name="resume", description="恢復音樂播放")
    async def resume_music(self, interaction: discord.Interaction):
        """恢復音樂"""
        try:
            success = await self.music_player.resume_playback(interaction.guild.id)
            
            if success:
                embed = EmbedBuilder.build(
                    title="▶️ 音樂已恢復",
                    description="繼續播放中...",
                    color=0x00FF00
                )
            else:
                embed = EmbedBuilder.build(
                    title="❌ 恢復失敗",
                    description="沒有暫停的音樂",
                    color=0xFF0000
                )
            
            await interaction.response.send_message(embed=embed, ephemeral=True)
            
        except Exception as e:
            logger.error(f"❌ 恢復音樂錯誤: {e}")
            await interaction.response.send_message("❌ 恢復音樂時發生錯誤。", ephemeral=True)

    @app_commands.command(name="stop", description="停止音樂播放")
    async def stop_music(self, interaction: discord.Interaction):
        """停止音樂"""
        try:
            success = await self.music_player.stop_playback(interaction.guild.id)
            
            if success:
                embed = EmbedBuilder.build(
                    title="⏹️ 音樂已停止",
                    description="播放佇列已保留",
                    color=0xFF0000
                )
            else:
                embed = EmbedBuilder.build(
                    title="❌ 停止失敗",
                    description="目前沒有正在播放的音樂",
                    color=0xFF0000
                )
            
            await interaction.response.send_message(embed=embed, ephemeral=True)
            
        except Exception as e:
            logger.error(f"❌ 停止音樂錯誤: {e}")
            await interaction.response.send_message("❌ 停止音樂時發生錯誤。", ephemeral=True)

    @app_commands.command(name="skip", description="跳過當前歌曲")
    async def skip_track(self, interaction: discord.Interaction):
        """跳過歌曲"""
        try:
            next_track = await self.music_player.skip_track(interaction.guild.id)
            
            if next_track:
                embed = EmbedBuilder.build(
                    title="⏭️ 已跳過當前歌曲",
                    description=f"現在播放: **{next_track.title}**\n{next_track.artist}",
                    color=0x00AAFF
                )
                embed.set_thumbnail(url=next_track.thumbnail)
            else:
                embed = EmbedBuilder.build(
                    title="❌ 跳過失敗",
                    description="播放佇列是空的",
                    color=0xFF0000
                )
            
            await interaction.response.send_message(embed=embed)
            
        except Exception as e:
            logger.error(f"❌ 跳過歌曲錯誤: {e}")
            await interaction.response.send_message("❌ 跳過歌曲時發生錯誤。", ephemeral=True)

    # ========== 播放佇列管理 ==========

    @app_commands.command(name="queue", description="查看播放佇列")
    async def view_queue(self, interaction: discord.Interaction):
        """查看播放佇列"""
        try:
            session = await self.music_player.get_session(interaction.guild.id)
            
            if not session:
                await interaction.response.send_message("❌ 目前沒有音樂會話。", ephemeral=True)
                return
            
            embed = EmbedBuilder.build(
                title="📋 播放佇列",
                color=0x9B59B6
            )
            
            # 當前播放
            if session.current_track:
                embed.add_field(
                    name="🎵 正在播放",
                    value=f"**{session.current_track.title}**\n{session.current_track.artist}",
                    inline=False
                )
            
            # 佇列內容
            if session.queue:
                queue_text = []
                for i, track in enumerate(session.queue[:10]):  # 只顯示前10首
                    queue_text.append(f"{i+1}. **{track.title}** - {track.artist}")
                
                embed.add_field(
                    name=f"📝 佇列 ({len(session.queue)} 首)",
                    value="\n".join(queue_text) + 
                          (f"\n... 還有 {len(session.queue)-10} 首" if len(session.queue) > 10 else ""),
                    inline=False
                )
            else:
                embed.add_field(
                    name="📝 佇列",
                    value="佇列是空的",
                    inline=False
                )
            
            # 播放狀態
            embed.add_field(
                name="⚙️ 播放設定",
                value=f"狀態: {session.state.value.title()}\n"
                      f"重複: {session.repeat_mode.value.title()}\n"
                      f"隨機: {'開啟' if session.shuffle else '關閉'}\n"
                      f"音量: {int(session.volume * 100)}%",
                inline=True
            )
            
            await interaction.response.send_message(embed=embed)
            
        except Exception as e:
            logger.error(f"❌ 查看佇列錯誤: {e}")
            await interaction.response.send_message("❌ 查看佇列時發生錯誤。", ephemeral=True)

    @app_commands.command(name="shuffle", description="隨機播放佇列")
    async def shuffle_queue(self, interaction: discord.Interaction):
        """隨機播放"""
        try:
            success = await self.music_player.shuffle_queue(interaction.guild.id)
            
            if success:
                embed = EmbedBuilder.build(
                    title="🔀 佇列已隨機排列",
                    description="播放順序已打亂",
                    color=0x9B59B6
                )
            else:
                embed = EmbedBuilder.build(
                    title="❌ 隨機失敗",
                    description="佇列中歌曲不足",
                    color=0xFF0000
                )
            
            await interaction.response.send_message(embed=embed, ephemeral=True)
            
        except Exception as e:
            logger.error(f"❌ 隨機播放錯誤: {e}")
            await interaction.response.send_message("❌ 隨機播放時發生錯誤。", ephemeral=True)

    @app_commands.command(name="clear", description="清空播放佇列")
    async def clear_queue(self, interaction: discord.Interaction):
        """清空佇列"""
        try:
            cleared_count = await self.music_player.clear_queue(interaction.guild.id)
            
            embed = EmbedBuilder.build(
                title="🗑️ 佇列已清空",
                description=f"已移除 {cleared_count} 首歌曲",
                color=0xFF6B6B
            )
            
            await interaction.response.send_message(embed=embed, ephemeral=True)
            
        except Exception as e:
            logger.error(f"❌ 清空佇列錯誤: {e}")
            await interaction.response.send_message("❌ 清空佇列時發生錯誤。", ephemeral=True)

    # ========== 音樂搜尋 ==========

    @app_commands.command(name="search", description="搜尋音樂")
    @app_commands.describe(
        query="搜尋關鍵詞",
        results="結果數量 (1-10)"
    )
    async def search_music(self, interaction: discord.Interaction, query: str, results: int = 5):
        """搜尋音樂"""
        try:
            await interaction.response.defer()
            
            # 限制結果數量
            results = max(1, min(10, results))
            
            # 檢查使用權限
            can_use, cost_info = await self._check_usage_permission(
                interaction.user.id, interaction.guild.id, "search"
            )
            
            if not can_use:
                embed = EmbedBuilder.build(
                    title="❌ 使用受限",
                    description=cost_info["message"],
                    color=0xFF0000
                )
                await interaction.followup.send(embed=embed, ephemeral=True)
                return
            
            # 搜尋音樂
            tracks = await self.music_player.search_youtube(query, max_results=results)
            
            if not tracks:
                await interaction.followup.send("❌ 找不到相關音樂，請嘗試其他關鍵詞。", ephemeral=True)
                return
            
            # 扣除費用
            if cost_info["cost"] > 0:
                await self.economy_manager.add_coins(
                    interaction.user.id, interaction.guild.id, -cost_info["cost"]
                )
            
            # 記錄使用量
            await self._record_daily_usage(interaction.user.id)
            
            embed = EmbedBuilder.build(
                title=f"🔍 搜尋結果: {query}",
                description=f"找到 {len(tracks)} 個結果",
                color=0x00AAFF
            )
            
            for i, track in enumerate(tracks):
                embed.add_field(
                    name=f"{i+1}. {track.title}",
                    value=f"**{track.artist}**\n"
                          f"時長: {self._format_duration(track.duration)}\n"
                          f"使用 `/play {track.title}` 播放",
                    inline=False
                )
            
            embed.add_field(
                name="💡 提示",
                value="點擊歌曲名稱複製到 `/play` 指令中播放" +
                      (f"\n消耗金幣: {cost_info['cost']}🪙" if cost_info["cost"] > 0 else ""),
                inline=False
            )
            
            await interaction.followup.send(embed=embed)
            
            # 記錄指標
            track_command_execution("search", interaction.guild.id)
            
        except Exception as e:
            logger.error(f"❌ 搜尋音樂錯誤: {e}")
            await interaction.followup.send("❌ 搜尋音樂時發生錯誤，請稍後再試。", ephemeral=True)

    # ========== 歌詞功能 ==========

    @app_commands.command(name="lyrics", description="查看當前播放歌曲的歌詞")
    async def show_lyrics(self, interaction: discord.Interaction):
        """顯示歌詞"""
        try:
            await interaction.response.defer()
            
            session = await self.music_player.get_session(interaction.guild.id)
            if not session or not session.current_track:
                await interaction.followup.send("❌ 目前沒有正在播放的音樂。", ephemeral=True)
                return
            
            # 檢查使用權限
            can_use, cost_info = await self._check_usage_permission(
                interaction.user.id, interaction.guild.id, "lyrics"
            )
            
            if not can_use:
                embed = EmbedBuilder.build(
                    title="❌ 使用受限",
                    description=cost_info["message"],
                    color=0xFF0000
                )
                await interaction.followup.send(embed=embed, ephemeral=True)
                return
            
            # 獲取歌詞
            lyrics = await self.music_player.get_lyrics(session.current_track)
            
            if lyrics:
                # 扣除費用
                if cost_info["cost"] > 0:
                    await self.economy_manager.add_coins(
                        interaction.user.id, interaction.guild.id, -cost_info["cost"]
                    )
                
                # 記錄使用量
                await self._record_daily_usage(interaction.user.id)
                
                # 分段發送歌詞
                if len(lyrics) > 1500:
                    parts = [lyrics[i:i+1500] for i in range(0, len(lyrics), 1500)]
                    
                    for i, part in enumerate(parts):
                        embed = EmbedBuilder.build(
                            title=f"🎵 歌詞 - {session.current_track.title} ({i+1}/{len(parts)})",
                            description=f"```\n{part}\n```",
                            color=0xFF69B4
                        )
                        
                        if i == 0:
                            embed.add_field(
                                name="🎤 歌曲資訊",
                                value=f"歌手: {session.current_track.artist}\n" +
                                      (f"消耗金幣: {cost_info['cost']}🪙" if cost_info["cost"] > 0 else ""),
                                inline=True
                            )
                        
                        await interaction.followup.send(embed=embed)
                        if i < len(parts) - 1:
                            await asyncio.sleep(1)
                else:
                    embed = EmbedBuilder.build(
                        title=f"🎵 歌詞 - {session.current_track.title}",
                        description=f"```\n{lyrics}\n```",
                        color=0xFF69B4
                    )
                    
                    embed.add_field(
                        name="🎤 歌曲資訊",
                        value=f"歌手: {session.current_track.artist}\n" +
                              (f"消耗金幣: {cost_info['cost']}🪙" if cost_info["cost"] > 0 else ""),
                        inline=True
                    )
                    
                    await interaction.followup.send(embed=embed)
            else:
                embed = EmbedBuilder.build(
                    title="❌ 找不到歌詞",
                    description="這首歌曲暫時沒有歌詞資料",
                    color=0xFF0000
                )
                await interaction.followup.send(embed=embed, ephemeral=True)
            
            # 記錄指標
            track_command_execution("lyrics", interaction.guild.id)
            
        except Exception as e:
            logger.error(f"❌ 顯示歌詞錯誤: {e}")
            await interaction.followup.send("❌ 獲取歌詞時發生錯誤，請稍後再試。", ephemeral=True)

    # ========== 音樂問答 ==========

    @app_commands.command(name="music_quiz", description="開始音樂問答遊戲")
    @app_commands.describe(difficulty="問答難度")
    @app_commands.choices(difficulty=[
        app_commands.Choice(name="簡單", value="easy"),
        app_commands.Choice(name="中等", value="medium"),
        app_commands.Choice(name="困難", value="hard")
    ])
    async def music_quiz(self, interaction: discord.Interaction, difficulty: str = "medium"):
        """音樂問答"""
        try:
            await interaction.response.defer()
            
            # 檢查使用權限
            can_use, cost_info = await self._check_usage_permission(
                interaction.user.id, interaction.guild.id, "quiz"
            )
            
            if not can_use:
                embed = EmbedBuilder.build(
                    title="❌ 使用受限",
                    description=cost_info["message"],
                    color=0xFF0000
                )
                await interaction.followup.send(embed=embed, ephemeral=True)
                return
            
            # 生成問答題目
            question = await self.music_player.generate_music_quiz(difficulty)
            
            if not question:
                await interaction.followup.send("❌ 生成問答失敗，請稍後再試。", ephemeral=True)
                return
            
            # 扣除費用
            if cost_info["cost"] > 0:
                await self.economy_manager.add_coins(
                    interaction.user.id, interaction.guild.id, -cost_info["cost"]
                )
            
            # 記錄使用量
            await self._record_daily_usage(interaction.user.id)
            
            # 創建問答embed
            embed = EmbedBuilder.build(
                title="🎮 音樂問答時間！",
                description=f"**難度**: {difficulty.title()}\n\n"
                           f"**問題**: 請問這首歌的{self._get_question_type_name(question.question_type)}是什麼？",
                color=0xFFD700
            )
            
            embed.set_thumbnail(url=question.track.thumbnail)
            
            # 添加選項
            options_text = []
            for i, option in enumerate(question.options):
                options_text.append(f"{chr(65+i)}. {option}")
            
            embed.add_field(
                name="📝 選項",
                value="\n".join(options_text),
                inline=False
            )
            
            embed.add_field(
                name="🎵 歌曲提示",
                value=f"歌曲: {question.track.title}\n"
                      f"歌手: {question.track.artist if question.question_type != 'artist' else '???'}",
                inline=True
            )
            
            embed.add_field(
                name="⏱️ 答題說明",
                value="請在30秒內回答\n"
                      "使用表情符號 🅰️ 🅱️ 🇨 🇩 來回答" +
                      (f"\n消耗金幣: {cost_info['cost']}🪙" if cost_info["cost"] > 0 else ""),
                inline=True
            )
            
            message = await interaction.followup.send(embed=embed)
            
            # 添加反應
            reactions = ["🅰️", "🅱️", "🇨", "🇩"]
            for i in range(len(question.options)):
                await message.add_reaction(reactions[i])
            
            # 等待用戶回答
            def check(reaction, user):
                return (user.id == interaction.user.id and 
                       str(reaction.emoji) in reactions[:len(question.options)] and
                       reaction.message.id == message.id)
            
            try:
                reaction, user = await self.bot.wait_for('reaction_add', timeout=30.0, check=check)
                
                # 檢查答案
                answer_index = reactions.index(str(reaction.emoji))
                user_answer = question.options[answer_index]
                is_correct = user_answer == question.correct_answer
                
                # 計算獎勵
                if is_correct:
                    reward_coins = {"easy": 10, "medium": 20, "hard": 30}[difficulty]
                    await self.economy_manager.add_coins(
                        interaction.user.id, interaction.guild.id, reward_coins
                    )
                    
                    result_embed = EmbedBuilder.build(
                        title="🎉 答對了！",
                        description=f"正確答案是: **{question.correct_answer}**\n"
                                   f"獲得獎勵: {reward_coins}🪙",
                        color=0x00FF00
                    )
                else:
                    result_embed = EmbedBuilder.build(
                        title="❌ 答錯了",
                        description=f"正確答案是: **{question.correct_answer}**\n"
                                   f"您的答案: **{user_answer}**",
                        color=0xFF0000
                    )
                
                await interaction.followup.send(embed=result_embed)
                
            except asyncio.TimeoutError:
                timeout_embed = EmbedBuilder.build(
                    title="⏰ 時間到！",
                    description=f"正確答案是: **{question.correct_answer}**",
                    color=0xFFAA00
                )
                await interaction.followup.send(embed=timeout_embed)
            
            # 記錄指標
            track_command_execution("music_quiz", interaction.guild.id)
            
        except Exception as e:
            logger.error(f"❌ 音樂問答錯誤: {e}")
            await interaction.followup.send("❌ 音樂問答時發生錯誤，請稍後再試。", ephemeral=True)

    # ========== 統計和設定 ==========

    @app_commands.command(name="music_stats", description="查看音樂服務使用統計")
    async def music_stats(self, interaction: discord.Interaction):
        """音樂統計"""
        try:
            user_id = interaction.user.id
            guild_id = interaction.guild.id
            
            # 獲取使用統計
            daily_usage = await self._get_daily_usage(user_id)
            
            # 獲取經濟狀態
            economy = await self.economy_manager.get_user_economy(user_id, guild_id)
            
            # 獲取會話統計
            session_stats = await self.music_player.get_session_stats(guild_id)
            
            embed = EmbedBuilder.build(
                title="🎵 音樂服務統計",
                description=f"{interaction.user.display_name} 的音樂服務使用情況",
                color=0x9B59B6
            )
            
            embed.set_thumbnail(url=interaction.user.display_avatar.url)
            
            # 今日使用情況
            remaining_free = max(0, self.daily_free_quota - daily_usage)
            embed.add_field(
                name="📅 今日使用",
                value=f"已使用: {daily_usage}/{self.daily_free_quota} (免費)\n"
                      f"剩餘免費額度: {remaining_free}",
                inline=True
            )
            
            # 經濟狀態
            embed.add_field(
                name="💰 經濟狀態",
                value=f"金幣餘額: {economy.get('coins', 0):,}🪙\n"
                      f"可用於音樂服務",
                inline=True
            )
            
            # 當前會話狀態
            if session_stats:
                embed.add_field(
                    name="🎵 當前會話",
                    value=f"狀態: {session_stats.get('state', 'stopped').title()}\n"
                          f"佇列: {session_stats.get('queue_length', 0)} 首\n"
                          f"音量: {int(session_stats.get('volume', 0.5) * 100)}%",
                    inline=True
                )
            
            # 費用說明
            cost_text = []
            for service, cost in self.music_costs.items():
                service_name = {
                    "search": "🔍 音樂搜尋",
                    "lyrics": "🎵 歌詞查看",
                    "quiz": "🎮 音樂問答",
                    "playlist_create": "📝 建立播放清單",
                    "premium_features": "⭐ 進階功能"
                }.get(service, service)
                
                cost_text.append(f"{service_name}: {cost}🪙")
            
            embed.add_field(
                name="💳 服務費用",
                value="\n".join(cost_text),
                inline=True
            )
            
            embed.add_field(
                name="💡 費用說明",
                value=f"• 每日前{self.daily_free_quota}次免費\n"
                      "• 超出免費額度後按服務收費\n"
                      "• 問答答對可獲得金幣獎勵",
                inline=False
            )
            
            embed.add_field(
                name="🎵 可用指令",
                value="• `/play` - 播放音樂\n"
                      "• `/search` - 搜尋音樂\n"
                      "• `/lyrics` - 查看歌詞\n"
                      "• `/music_quiz` - 音樂問答\n"
                      "• `/queue` - 查看播放佇列",
                inline=False
            )
            
            await interaction.response.send_message(embed=embed, ephemeral=True)
            
        except Exception as e:
            logger.error(f"❌ 音樂統計錯誤: {e}")
            await interaction.response.send_message("❌ 獲取音樂統計時發生錯誤。", ephemeral=True)

    # ========== 輔助方法 ==========

    def _format_duration(self, seconds: int) -> str:
        """格式化時長"""
        if seconds <= 0:
            return "未知"
        
        minutes = seconds // 60
        seconds = seconds % 60
        
        if minutes >= 60:
            hours = minutes // 60
            minutes = minutes % 60
            return f"{hours}:{minutes:02d}:{seconds:02d}"
        else:
            return f"{minutes}:{seconds:02d}"

    def _get_question_type_name(self, question_type: str) -> str:
        """獲取問題類型名稱"""
        names = {
            "artist": "歌手",
            "title": "歌名",
            "genre": "音樂類型",
            "year": "發行年份"
        }
        return names.get(question_type, "相關資訊")

    async def _check_usage_permission(self, user_id: int, guild_id: int, 
                                    service_type: str) -> tuple[bool, Dict[str, Any]]:
        """檢查使用權限和費用"""
        try:
            # 檢查每日免費額度
            daily_usage = await self._get_daily_usage(user_id)
            
            if daily_usage < self.daily_free_quota:
                return True, {"cost": 0, "message": "免費額度內"}
            
            # 檢查金幣餘額
            economy = await self.economy_manager.get_user_economy(user_id, guild_id)
            cost = self.music_costs.get(service_type, 5)
            
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
            cache_key = f"music_daily_usage:{user_id}"
            usage = await cache_manager.get(cache_key)
            return usage or 0
            
        except Exception as e:
            logger.error(f"❌ 獲取每日使用量失敗: {e}")
            return 0

    async def _record_daily_usage(self, user_id: int):
        """記錄每日使用次數"""
        try:
            cache_key = f"music_daily_usage:{user_id}"
            current_usage = await self._get_daily_usage(user_id)
            
            # 設置到明天零點過期
            from datetime import timedelta
            tomorrow = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
            tomorrow += timedelta(days=1)
            ttl = int((tomorrow - datetime.now(timezone.utc)).total_seconds())
            
            await cache_manager.set(cache_key, current_usage + 1, ttl)
            
        except Exception as e:
            logger.error(f"❌ 記錄每日使用量失敗: {e}")

async def setup(bot):
    """設置 Cog"""
    await bot.add_cog(MusicCog(bot))