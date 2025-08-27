# bot/cogs/music_core.py - 音樂系統核心
"""
Discord Bot 音樂系統 v2.3.0
支援 YouTube 直接播放和 Discord GUI 控制介面
"""

import asyncio
import logging
import re
import urllib.parse
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Union

import discord
import yt_dlp
from discord import FFmpegOpusAudio, FFmpegPCMAudio, app_commands
from discord.ext import commands

from bot.utils.embed_builder import EmbedBuilder
from shared.logger import logger

# 禁用yt-dlp日誌
logging.getLogger("yt_dlp").setLevel(logging.ERROR)


class LoopMode(Enum):
    """循環模式"""

    NONE = "none"
    SINGLE = "single"
    QUEUE = "queue"


class MusicSource:
    """音樂來源"""

    def __init__(self, data: dict, requester: discord.Member):
        self.title = data.get("title", "Unknown")
        self.url = data.get("url", "")
        self.webpage_url = data.get("webpage_url", "")
        self.duration = data.get("duration", 0)
        self.thumbnail = data.get("thumbnail", "")
        self.uploader = data.get("uploader", "Unknown")
        self.requester = requester
        self.stream_url = data.get("formats", [{}])[0].get("url", "") if data.get("formats") else ""

    def __str__(self):
        return f"**{self.title}** - {self.requester.mention}"

    @property
    def duration_str(self) -> str:
        """格式化時長"""
        if not self.duration:
            return "未知"
        hours, remainder = divmod(self.duration, 3600)
        minutes, seconds = divmod(remainder, 60)
        if hours:
            return f"{hours}:{minutes:02d}:{seconds:02d}"
        return f"{minutes}:{seconds:02d}"


class MusicPlayer:
    """音樂播放器"""

    def __init__(self, ctx: commands.Context):
        self.bot = ctx.bot
        self.guild = ctx.guild
        self.channel = ctx.channel
        self.cog = ctx.cog

        self.queue: List[MusicSource] = []
        self.current: Optional[MusicSource] = None
        self.voice_client: Optional[discord.VoiceClient] = None
        self.loop_mode = LoopMode.NONE
        self.volume = 0.5
        self.is_playing = False
        self.is_paused = False
        self.skip_votes = set()

        # YT-DLP 配置
        self.ytdl_format_options = {
            "format": "bestaudio/best",
            "extractaudio": True,
            "audioformat": "mp3",
            "outtmpl": "%(extractor)s-%(id)s-%(title)s.%(ext)s",
            "restrictfilenames": True,
            "noplaylist": True,
            "nocheckcertificate": True,
            "ignoreerrors": False,
            "logtostderr": False,
            "quiet": True,
            "no_warnings": True,
            "default_search": "auto",
            "source_address": "0.0.0.0",
        }

        self.ffmpeg_options = {
            "before_options": "-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5",
            "options": "-vn",
        }

        self.ytdl = yt_dlp.YoutubeDL(self.ytdl_format_options)

    async def connect_to_voice(self, channel: discord.VoiceChannel):
        """連接到語音頻道"""
        try:
            # 檢查是否已經連接到相同頻道
            if self.voice_client and self.voice_client.is_connected():
                if self.voice_client.channel == channel:
                    logger.info(f"✅ 已在語音頻道: {channel.name}")
                    return
                else:
                    # 移動到新頻道
                    try:
                        await self.voice_client.move_to(channel)
                        logger.info(f"🔄 移動到語音頻道: {channel.name}")
                        return
                    except Exception as move_error:
                        logger.warning(f"移動失敗，嘗試重新連接: {move_error}")
                        await self.disconnect()

            # 檢查是否有殘留的語音客戶端
            guild_voice_client = channel.guild.voice_client
            if guild_voice_client:
                try:
                    await guild_voice_client.disconnect()
                    logger.info("清理殘留的語音連接")
                except:
                    pass

            # 建立新連接
            self.voice_client = await channel.connect()
            logger.info(f"🔗 連接到語音頻道: {channel.name}")

        except discord.errors.ClientException as e:
            if "Already connected" in str(e):
                logger.warning("語音客戶端已連接，嘗試使用現有連接")
                guild_voice_client = channel.guild.voice_client
                if guild_voice_client and guild_voice_client.is_connected():
                    self.voice_client = guild_voice_client
                    logger.info(f"✅ 使用現有語音連接: {channel.name}")
                    return
                else:
                    logger.warning("現有連接無效，重新嘗試連接")
                    # 清理無效連接並重試
                    try:
                        if guild_voice_client:
                            await guild_voice_client.disconnect()
                        self.voice_client = await channel.connect()
                        logger.info(f"🔗 重新連接成功: {channel.name}")
                        return
                    except Exception as retry_error:
                        logger.error(f"重新連接失敗: {retry_error}")
            logger.error(f"❌ 語音連接失敗: {e}")
            raise
        except Exception as e:
            logger.error(f"❌ 語音連接失敗: {e}")
            await self.send_embed("❌ 連接失敗", f"無法連接到語音頻道: {str(e)}", "error")
            raise

    async def disconnect(self):
        """斷開語音連接"""
        if self.voice_client:
            await self.voice_client.disconnect()
            self.voice_client = None

    async def add_song(
        self, url_or_search: str, requester: discord.Member
    ) -> Optional[MusicSource]:
        """添加歌曲到播放列表"""
        try:
            # 檢查是否為 YouTube URL
            if not self.is_youtube_url(url_or_search):
                # 如果不是URL，進行搜索
                url_or_search = f"ytsearch:{url_or_search}"

            # 提取音樂信息
            data = await self.extract_info(url_or_search)
            if not data:
                return None

            # 如果是播放列表，取第一首歌
            if "entries" in data:
                if not data["entries"]:
                    return None
                data = data["entries"][0]

            source = MusicSource(data, requester)
            self.queue.append(source)

            return source

        except Exception as e:
            logger.error(f"添加歌曲失敗: {e}")
            return None

    async def extract_info(self, url: str) -> Optional[dict]:
        """提取音樂信息"""
        try:
            loop = asyncio.get_event_loop()
            data = await loop.run_in_executor(
                None, lambda: self.ytdl.extract_info(url, download=False)
            )
            return data
        except Exception as e:
            logger.error(f"提取音樂信息失敗: {e}")
            return None

    def is_youtube_url(self, url: str) -> bool:
        """檢查是否為有效的 YouTube URL"""
        youtube_regex = re.compile(
            r"(https?://)?(www\.)?(youtube|youtu|youtube-nocookie)\.(com|be)/"
            r"(watch\?v=|embed/|v/|.+\?v=)?([^&=%\?]{11})"
        )
        return bool(youtube_regex.match(url))

    async def play_next(self):
        """播放下一首歌曲"""
        if self.loop_mode == LoopMode.SINGLE and self.current:
            # 單曲循環
            next_song = self.current
        elif self.queue:
            # 播放列表中的下一首
            next_song = self.queue.pop(0)
            if self.loop_mode == LoopMode.QUEUE and self.current:
                # 隊列循環，將當前歌曲加回列表末尾
                self.queue.append(self.current)
        else:
            # 沒有更多歌曲
            self.current = None
            self.is_playing = False
            await self.send_embed("🎵 播放列表已結束", "所有歌曲播放完畢", "info")
            return

        self.current = next_song

        try:
            # 獲取音頻流
            data = await self.extract_info(self.current.webpage_url)
            if not data:
                await self.play_next()
                return

            # 找到最佳音頻格式
            formats = data.get("formats", [])
            audio_url = None

            for fmt in formats:
                if fmt.get("acodec") != "none":  # 確保有音頻
                    audio_url = fmt.get("url")
                    break

            if not audio_url:
                await self.play_next()
                return

            # 創建音頻源
            try:
                source = FFmpegPCMAudio(audio_url, **self.ffmpeg_options)
                logger.info(f"🎵 創建音頻源成功: {self.current.title}")
            except Exception as e:
                logger.error(f"❌ 創建音頻源失敗: {e}")
                await self.send_embed("❌ 播放錯誤", f"音頻源創建失敗: {str(e)}", "error")
                await self.play_next()
                return

            # 播放音樂
            try:
                self.voice_client.play(
                    source,
                    after=lambda e: (
                        asyncio.run_coroutine_threadsafe(self.play_next(), self.bot.loop).result()
                        if not e
                        else logger.error(f"播放錯誤: {e}")
                    ),
                )
                logger.info(f"🎵 開始播放: {self.current.title}")
            except Exception as e:
                logger.error(f"❌ 播放失敗: {e}")
                await self.send_embed("❌ 播放錯誤", f"無法播放音樂: {str(e)}", "error")
                await self.play_next()
                return

            self.is_playing = True
            self.is_paused = False

            # 發送正在播放信息
            await self.send_now_playing()

        except Exception as e:
            logger.error(f"播放錯誤: {e}")
            await self.send_embed("❌ 播放錯誤", str(e), "error")
            await self.play_next()

    async def pause(self):
        """暫停播放"""
        if self.voice_client and self.voice_client.is_playing():
            self.voice_client.pause()
            self.is_paused = True

    async def resume(self):
        """恢復播放"""
        if self.voice_client and self.voice_client.is_paused():
            self.voice_client.resume()
            self.is_paused = False

    async def stop(self):
        """停止播放"""
        if self.voice_client:
            self.voice_client.stop()
            self.queue.clear()
            self.current = None
            self.is_playing = False
            self.is_paused = False

    async def skip(self, force: bool = False):
        """跳過當前歌曲"""
        if not force:
            # 需要投票跳過
            return False

        if self.voice_client and self.voice_client.is_playing():
            self.voice_client.stop()

        return True

    async def set_volume(self, volume: float):
        """設置音量"""
        self.volume = max(0.0, min(1.0, volume))
        if self.voice_client and hasattr(self.voice_client.source, "volume"):
            self.voice_client.source.volume = self.volume

    async def send_embed(self, title: str, description: str, color: str = "info"):
        """發送嵌入消息"""
        if color == "success":
            embed = EmbedBuilder.create_success_embed(title, description)
        elif color == "error":
            embed = EmbedBuilder.create_error_embed(title, description)
        elif color == "warning":
            embed = EmbedBuilder.create_warning_embed(title, description)
        else:
            embed = EmbedBuilder.create_info_embed(title, description)

        await self.channel.send(embed=embed)

    async def send_now_playing(self):
        """發送正在播放信息"""
        if not self.current:
            return

        embed = EmbedBuilder.create_info_embed("🎵 正在播放", f"**{self.current.title}**")

        embed.add_field(
            name="詳細信息",
            value=f"👤 上傳者: {self.current.uploader}\n"
            f"⏱️ 時長: {self.current.duration_str}\n"
            f"🎧 點播者: {self.current.requester.mention}",
            inline=True,
        )

        if self.queue:
            embed.add_field(
                name="播放列表", value=f"📝 還有 {len(self.queue)} 首歌曲等待播放", inline=True
            )

        embed.add_field(name="播放模式", value=f"🔁 {self.loop_mode.value}", inline=True)

        if self.current.thumbnail:
            embed.set_thumbnail(url=self.current.thumbnail)

        await self.channel.send(embed=embed)


class MusicCore(commands.Cog):
    """音樂系統核心"""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.players: Dict[int, MusicPlayer] = {}
        logger.info("🎵 音樂系統核心初始化完成")

    def get_player(self, ctx: commands.Context) -> MusicPlayer:
        """獲取音樂播放器"""
        if ctx.guild.id not in self.players:
            self.players[ctx.guild.id] = MusicPlayer(ctx)
        return self.players[ctx.guild.id]

    def _check_voice_connection(self, player: MusicPlayer, guild) -> bool:
        """增強的語音連接狀態檢測"""
        try:
            # 檢查 player 的 voice_client
            player_connected = player.voice_client and player.voice_client.is_connected()

            # 檢查 guild 的 voice_client (更可靠)
            guild_voice_client = guild.voice_client
            guild_connected = guild_voice_client and guild_voice_client.is_connected()

            # 如果有不一致，同步 player 狀態
            if guild_connected and not player_connected:
                logger.info("🔄 同步語音客戶端狀態")
                player.voice_client = guild_voice_client
                return True
            elif player_connected and not guild_connected:
                logger.warning("⚠️ 語音客戶端狀態不一致，清理 player 狀態")
                player.voice_client = None
                return False

            # 兩者一致的情況
            return player_connected and guild_connected

        except Exception as e:
            logger.error(f"語音連接檢測錯誤: {e}")
            return False

    async def _create_context_from_interaction(self, interaction: discord.Interaction):
        """從互動創建context"""

        # 創建一個假的 context 對象
        class FakeContext:
            def __init__(self, interaction, cog):
                self.bot = interaction.client
                self.guild = interaction.guild
                self.channel = interaction.channel
                self.cog = cog
                self.user = interaction.user
                self.author = interaction.user

        return FakeContext(interaction, self)

    def cog_check(self, ctx):
        """Cog檢查：確保在伺服器中使用"""
        return ctx.guild is not None

    async def cog_command_error(self, ctx, error):
        """Cog錯誤處理"""
        logger.error(f"音樂指令錯誤: {error}")

    @app_commands.command(name="play", description="🎵 播放音樂 - 支援 YouTube 網址或搜索關鍵字")
    async def play(self, interaction: discord.Interaction, url_or_search: str):
        """播放音樂指令"""
        try:
            await interaction.response.defer()

            # 檢查用戶是否在語音頻道
            if not interaction.user.voice or not interaction.user.voice.channel:
                embed = EmbedBuilder.create_error_embed(
                    "❌ 請先加入語音頻道", "您需要先加入一個語音頻道才能播放音樂"
                )
                await interaction.followup.send(embed=embed, ephemeral=True)
                return

            # 創建臨時context用於播放器
            ctx = await self._create_context_from_interaction(interaction)
            player = self.get_player(ctx)

            # 連接到語音頻道
            await player.connect_to_voice(interaction.user.voice.channel)

            # 添加歌曲
            source = await player.add_song(url_or_search, interaction.user)

            if not source:
                embed = EmbedBuilder.create_error_embed(
                    "❌ 無法播放", "無法找到或播放此音樂，請檢查網址或搜索關鍵字"
                )
                await interaction.followup.send(embed=embed, ephemeral=True)
                return

            # 如果沒有正在播放，開始播放
            if not player.is_playing:
                await player.play_next()

            embed = EmbedBuilder.create_success_embed(
                "✅ 已添加到播放列表",
                f"**{source.title}**\n👤 {source.uploader}\n⏱️ {source.duration_str}",
            )

            if player.queue or player.current != source:
                embed.add_field(name="排隊位置", value=f"第 {len(player.queue)} 位", inline=True)

            if source.thumbnail:
                embed.set_thumbnail(url=source.thumbnail)

            await interaction.followup.send(embed=embed)

        except Exception as e:
            logger.error(f"播放指令錯誤: {e}")
            embed = EmbedBuilder.create_error_embed(
                "❌ 系統錯誤", "音樂播放系統暫時無法使用，請稍後再試"
            )
            await interaction.followup.send(embed=embed, ephemeral=True)

    @app_commands.command(name="music_control", description="🎛️ 音樂控制面板")
    async def music_control(self, interaction: discord.Interaction):
        """音樂控制面板"""
        try:
            # 檢查互動是否已被處理
            if interaction.response.is_done():
                logger.warning("音樂控制面板互動已被處理")
                return

            # 立即延遲回應，避免超時
            await interaction.response.defer()

            ctx = await self._create_context_from_interaction(interaction)
            player = self.get_player(ctx)

            # 檢查語音連接狀態（但不阻止進入控制面板）- 增強版檢測
            is_connected = self._check_voice_connection(player, interaction.guild)

            # 創建控制面板
            from bot.views.music_views import MusicControlView

            if is_connected:
                embed = EmbedBuilder.create_info_embed("🎛️ 音樂控制面板", "使用下方按鈕控制音樂播放")
            else:
                embed = EmbedBuilder.create_warning_embed(
                    "🎛️ 音樂控制面板", "Bot 目前未連接語音頻道，請先使用 `/play` 播放音樂"
                )

            if player.current:
                embed.add_field(
                    name="🎵 正在播放",
                    value=f"**{player.current.title}**\n"
                    f"👤 {player.current.uploader}\n"
                    f"🎧 {player.current.requester.mention}",
                    inline=False,
                )

            # 播放狀態
            if is_connected:
                status = f"{'⏸️ 暫停' if player.is_paused else '▶️ 播放' if player.is_playing else '⏹️ 停止'}"
            else:
                status = "🔌 未連接"

            embed.add_field(
                name="📊 播放狀態",
                value=f"{status}\n"
                f"🔊 音量: {int(player.volume * 100)}%\n"
                f"🔁 循環: {getattr(player.loop_mode, 'value', 'none')}",
                inline=True,
            )

            if player.queue:
                queue_preview = "\n".join(
                    [
                        (
                            f"{i+1}. {song.title[:30]}..."
                            if len(song.title) > 30
                            else f"{i+1}. {song.title}"
                        )
                        for i, song in enumerate(player.queue[:5])
                    ]
                )
                if len(player.queue) > 5:
                    queue_preview += f"\n... 還有 {len(player.queue) - 5} 首"

                embed.add_field(name="📝 播放列表", value=queue_preview, inline=True)
            else:
                embed.add_field(name="📝 播放列表", value="播放列表為空", inline=True)

            view = MusicControlView(player)
            await interaction.followup.send(embed=embed, view=view)

        except discord.InteractionResponded:
            logger.warning("音樂控制面板互動已被回應")
        except Exception as e:
            logger.error(f"音樂控制面板錯誤: {e}")
            try:
                embed = EmbedBuilder.create_error_embed("❌ 系統錯誤", "無法顯示音樂控制面板")
                if not interaction.response.is_done():
                    await interaction.response.send_message(embed=embed, ephemeral=True)
                else:
                    await interaction.followup.send(embed=embed, ephemeral=True)
            except:
                pass

    @app_commands.command(name="queue", description="📝 查看播放列表")
    async def queue(self, interaction: discord.Interaction):
        """查看播放列表"""
        try:
            if interaction.response.is_done():
                logger.warning("播放列表互動已被處理")
                return

            ctx = await self._create_context_from_interaction(interaction)
            player = self.get_player(ctx)

            if not player.current and not player.queue:
                embed = EmbedBuilder.create_info_embed("📝 播放列表", "播放列表目前為空")
                await interaction.response.send_message(embed=embed)
                return

            embed = EmbedBuilder.create_info_embed("📝 播放列表", "")

            if player.current:
                embed.add_field(
                    name="🎵 正在播放",
                    value=f"**{player.current.title}**\n"
                    f"⏱️ {player.current.duration_str} | 🎧 {player.current.requester.mention}",
                    inline=False,
                )

            if player.queue:
                queue_text = ""
                for i, song in enumerate(player.queue[:10], 1):
                    queue_text += f"{i}. **{song.title}**\n"
                    queue_text += f"   ⏱️ {song.duration_str} | 🎧 {song.requester.mention}\n\n"

                if len(player.queue) > 10:
                    queue_text += f"... 還有 {len(player.queue) - 10} 首歌曲"

                embed.add_field(name="📋 接下來播放", value=queue_text, inline=False)
            else:
                embed.add_field(name="📋 接下來播放", value="沒有更多歌曲", inline=False)

            await interaction.response.send_message(embed=embed)

        except discord.InteractionResponded:
            logger.warning("播放列表互動已被回應")
        except Exception as e:
            logger.error(f"播放列表指令錯誤: {e}")
            try:
                embed = EmbedBuilder.create_error_embed("❌ 系統錯誤", "無法顯示播放列表")
                if not interaction.response.is_done():
                    await interaction.response.send_message(embed=embed, ephemeral=True)
                else:
                    await interaction.followup.send(embed=embed, ephemeral=True)
            except:
                pass

    @app_commands.command(name="voice_debug", description="🔍 語音狀態調試")
    async def voice_debug(self, interaction: discord.Interaction):
        """語音狀態調試命令"""
        try:
            await interaction.response.defer()

            ctx = await self._create_context_from_interaction(interaction)
            player = self.get_player(ctx)

            logger.info("🔍 開始語音狀態調試...")

            # 直接檢測，不調用複雜函數
            logger.info("🔍 直接檢查 player.voice_client...")
            player_vc = player.voice_client
            logger.info(f"🔍 player.voice_client = {player_vc}")

            logger.info("🔍 直接檢查 guild.voice_client...")
            guild_vc = interaction.guild.voice_client
            logger.info(f"🔍 guild.voice_client = {guild_vc}")

            # 檢查連接狀態
            player_connected = False
            guild_connected = False

            if player_vc:
                logger.info(f"🔍 player_vc.is_connected() = {player_vc.is_connected()}")
                player_connected = player_vc.is_connected()

            if guild_vc:
                logger.info(f"🔍 guild_vc.is_connected() = {guild_vc.is_connected()}")
                logger.info(f"🔍 guild_vc.channel = {guild_vc.channel}")
                guild_connected = guild_vc.is_connected()

            logger.info(
                f"🔍 最終結果: player_connected={player_connected}, guild_connected={guild_connected}"
            )

            embed = EmbedBuilder.create_info_embed("🔍 語音狀態調試報告", "詳細的語音連接狀態分析")

            # 詳細狀態信息
            player_status = "✅ 已連接" if player_connected else "❌ 未連接"
            guild_status = "✅ 已連接" if guild_connected else "❌ 未連接"

            embed.add_field(
                name="連接狀態",
                value=f"Player Voice Client: {player_status}\n"
                f"Guild Voice Client: {guild_status}",
                inline=False,
            )

            embed.add_field(
                name="對象詳情",
                value=f"Player 對象: {player_vc}\n" f"Guild 對象: {guild_vc}",
                inline=False,
            )

            if guild_vc:
                embed.add_field(
                    name="Guild Voice Client 詳情",
                    value=f"頻道: {guild_vc.channel}\n" f"連接狀態: {guild_vc.is_connected()}",
                    inline=False,
                )

            # 問題診斷
            if guild_connected and not player_connected:
                embed.add_field(
                    name="🚨 發現問題",
                    value="Guild 已連接但 Player 未同步！\n這就是狀態顯示錯誤的原因。",
                    inline=False,
                )
            elif player_connected and not guild_connected:
                embed.add_field(
                    name="🚨 發現問題",
                    value="Player 認為已連接但 Guild 未連接！\n這是異常狀態。",
                    inline=False,
                )
            elif not player_connected and not guild_connected:
                embed.add_field(name="ℹ️ 狀態正常", value="兩者都未連接，狀態一致。", inline=False)
            else:
                embed.add_field(name="✅ 狀態正常", value="兩者都已連接，狀態一致。", inline=False)

            await interaction.followup.send(embed=embed)
            logger.info("🔍 語音狀態調試完成")

        except Exception as e:
            logger.error(f"語音狀態調試錯誤: {e}")
            import traceback

            logger.error(traceback.format_exc())
            embed = EmbedBuilder.create_error_embed("❌ 調試失敗", str(e))
            try:
                await interaction.followup.send(embed=embed)
            except:
                pass

    @app_commands.command(name="voice_connect", description="🔗 強制連接到語音頻道")
    async def voice_connect(self, interaction: discord.Interaction):
        """強制連接到語音頻道"""
        try:
            await interaction.response.defer()

            # 檢查用戶是否在語音頻道
            if not interaction.user.voice or not interaction.user.voice.channel:
                embed = EmbedBuilder.create_error_embed(
                    "❌ 請先加入語音頻道", "您需要先加入一個語音頻道"
                )
                await interaction.followup.send(embed=embed)
                return

            channel = interaction.user.voice.channel
            logger.info(f"🔗 嘗試連接到語音頻道: {channel.name}")

            ctx = await self._create_context_from_interaction(interaction)
            player = self.get_player(ctx)

            # 強制連接
            try:
                await player.connect_to_voice(channel)

                # 驗證連接
                guild_vc = interaction.guild.voice_client
                if guild_vc and guild_vc.is_connected():
                    # 同步 player 狀態
                    player.voice_client = guild_vc

                    embed = EmbedBuilder.create_success_embed(
                        "✅ 語音連接成功", f"Bot 已連接到 **{channel.name}**"
                    )

                    embed.add_field(
                        name="連接詳情",
                        value=f"頻道: {guild_vc.channel}\n"
                        f"延遲: {guild_vc.latency:.2f}ms\n"
                        f"連接狀態: {guild_vc.is_connected()}",
                        inline=False,
                    )
                else:
                    embed = EmbedBuilder.create_error_embed("❌ 連接失敗", "無法建立語音連接")

                await interaction.followup.send(embed=embed)

            except Exception as e:
                logger.error(f"語音連接錯誤: {e}")
                import traceback

                logger.error(traceback.format_exc())

                embed = EmbedBuilder.create_error_embed(
                    "❌ 連接失敗", f"語音連接時發生錯誤: {str(e)}"
                )
                await interaction.followup.send(embed=embed)

        except Exception as e:
            logger.error(f"語音連接命令錯誤: {e}")
            import traceback

            logger.error(traceback.format_exc())

    @app_commands.command(name="connection_status", description="🤖 檢查 Bot 連接狀態")
    async def connection_status(self, interaction: discord.Interaction):
        """檢查 Bot 的連接狀態"""
        try:
            await interaction.response.defer()

            # 基本信息
            bot = self.bot
            guild_count = len(bot.guilds)
            user_count = sum(guild.member_count for guild in bot.guilds)

            embed = EmbedBuilder.create_info_embed(
                "🤖 Bot 狀態報告", f"Bot: {bot.user.name}#{bot.user.discriminator}"
            )

            embed.add_field(
                name="連接統計",
                value=f"🏰 伺服器數量: {guild_count}\n"
                f"👥 用戶數量: {user_count}\n"
                f"📡 延遲: {round(bot.latency * 1000)}ms",
                inline=True,
            )

            # 當前伺服器信息
            if interaction.guild:
                guild = interaction.guild
                embed.add_field(
                    name="當前伺服器",
                    value=f"📋 名稱: {guild.name}\n"
                    f"🆔 ID: {guild.id}\n"
                    f"👑 擁有者: {guild.owner}\n"
                    f"👥 成員數: {guild.member_count}",
                    inline=True,
                )

                # 語音頻道信息
                voice_channels = [
                    ch for ch in guild.channels if isinstance(ch, discord.VoiceChannel)
                ]
                embed.add_field(
                    name="語音頻道",
                    value=f"🎤 總數: {len(voice_channels)}\n"
                    f"🔗 Bot 連接: {'是' if guild.voice_client else '否'}",
                    inline=True,
                )
            else:
                embed.add_field(name="❌ 錯誤", value="無法獲取當前伺服器信息", inline=False)

            # 所有伺服器列表
            if guild_count > 0:
                guilds_info = []
                for i, guild in enumerate(bot.guilds[:5]):  # 只顯示前5個
                    guilds_info.append(f"{i+1}. {guild.name} (ID: {guild.id})")

                if guild_count > 5:
                    guilds_info.append(f"... 還有 {guild_count - 5} 個伺服器")

                embed.add_field(name="伺服器列表", value="\n".join(guilds_info), inline=False)
            else:
                embed.add_field(
                    name="⚠️ 警告",
                    value="Bot 目前未連接到任何伺服器！\n這可能是語音問題的原因。",
                    inline=False,
                )

            await interaction.followup.send(embed=embed)

        except Exception as e:
            logger.error(f"Bot 狀態檢查錯誤: {e}")
            import traceback

            logger.error(traceback.format_exc())
            embed = EmbedBuilder.create_error_embed("❌ 檢查失敗", str(e))
            try:
                await interaction.followup.send(embed=embed)
            except:
                pass

    @app_commands.command(name="music_menu", description="🎵 音樂系統主菜單")
    async def music_menu(self, interaction: discord.Interaction):
        """音樂系統主菜單"""
        try:
            # 檢查互動是否已被處理
            if interaction.response.is_done():
                logger.warning("音樂菜單互動已被處理")
                return

            from bot.views.music_views import MusicMenuView

            embed = EmbedBuilder.create_info_embed(
                "🎵 音樂系統", "歡迎使用 Potato Bot 音樂系統！\n支援 YouTube 直接播放"
            )

            embed.add_field(
                name="🎯 主要功能",
                value="🎵 播放音樂\n🎛️ 控制面板\n📝 播放列表\n🔍 搜索音樂",
                inline=True,
            )

            embed.add_field(
                name="💡 使用提示",
                value="• 直接貼上 YouTube 網址\n• 輸入歌曲名稱搜索\n• 支援完整播放控制",
                inline=True,
            )

            view = MusicMenuView(self)
            await interaction.response.send_message(embed=embed, view=view)

        except discord.InteractionResponded:
            logger.warning("音樂菜單互動已被回應")
        except Exception as e:
            logger.error(f"音樂菜單錯誤: {e}")
            try:
                embed = EmbedBuilder.create_error_embed("❌ 系統錯誤", "無法顯示音樂菜單")
                if not interaction.response.is_done():
                    await interaction.response.send_message(embed=embed, ephemeral=True)
                else:
                    await interaction.followup.send(embed=embed, ephemeral=True)
            except:
                pass


async def setup(bot):
    await bot.add_cog(MusicCore(bot))
    logger.info("✅ 音樂系統核心已載入")
