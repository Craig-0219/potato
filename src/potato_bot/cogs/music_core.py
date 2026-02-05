# bot/cogs/music_core.py - 音樂系統核心
"""
Discord Bot 音樂系統 v2.3.0
支援 YouTube 直接播放和 Discord GUI 控制介面
"""

import asyncio
import re
from enum import Enum
from typing import Dict, List, Optional

import discord
import wavelink
from discord import app_commands
from discord.ext import commands

from potato_bot.db.music_dao import MusicDAO
from potato_bot.utils.embed_builder import EmbedBuilder
from potato_shared.config import (
    LAVALINK_HOST,
    LAVALINK_PASSWORD,
    LAVALINK_PORT,
    LAVALINK_SECURE,
    LAVALINK_URI,
)
from potato_shared.logger import logger


def _ensure_voice_ws_mode_fallback() -> None:
    """Apply a small patch for empty voice gateway modes to avoid IndexError."""
    try:
        from discord import gateway as discord_gateway
        if getattr(discord_gateway, "_potato_voice_modes_patch", False):
            return
        original_initial_connection = discord_gateway.DiscordVoiceWebSocket.initial_connection
    except Exception as exc:
        logger.warning("Voice WS patch skipped: %s", exc)
        return

    async def patched_initial_connection(self, data):
        modes = data.get("modes")
        if not modes:
            fallback_mode = data.get("mode") or "xsalsa20_poly1305"
            data = dict(data)
            data["modes"] = [fallback_mode]
            logger.warning(
                "Voice gateway returned empty modes; falling back to %s",
                fallback_mode,
            )
        return await original_initial_connection(self, data)

    discord_gateway.DiscordVoiceWebSocket.initial_connection = patched_initial_connection
    discord_gateway._potato_voice_modes_patch = True


class LoopMode(Enum):
    """循環模式"""

    NONE = "none"
    SINGLE = "single"
    QUEUE = "queue"


class MusicPlayer:
    """音樂播放器"""

    def __init__(self, ctx: commands.Context):
        self.bot = ctx.bot
        self.guild = ctx.guild
        self.channel = ctx.channel
        self.cog = ctx.cog

        self.voice_client: Optional[wavelink.Player] = None
        self.loop_mode = LoopMode.NONE
        self.volume = 0.5
        self.last_error: Optional[str] = None

    @property
    def current(self) -> Optional[wavelink.Playable]:
        return self.voice_client.current if self.voice_client else None

    @property
    def queue(self) -> List[wavelink.Playable]:
        if self.voice_client:
            return list(self.voice_client.queue)
        return []

    @property
    def is_playing(self) -> bool:
        return bool(self.voice_client and self.voice_client.playing)

    @property
    def is_paused(self) -> bool:
        return bool(self.voice_client and self.voice_client.paused)

    def is_connected(self) -> bool:
        if not self.voice_client:
            return False
        if hasattr(self.voice_client, "connected"):
            return bool(self.voice_client.connected)
        if hasattr(self.voice_client, "is_connected"):
            return self.voice_client.is_connected()
        return False

    def _get_existing_voice_client(
        self, guild: discord.Guild
    ) -> Optional[wavelink.Player]:
        """取得既有的語音連線"""
        existing = guild.voice_client
        if isinstance(existing, wavelink.Player):
            return existing
        return None

    @staticmethod
    def _format_duration_ms(length_ms: int) -> str:
        """格式化毫秒長度"""
        if not length_ms:
            return "未知"
        total_seconds = int(length_ms // 1000)
        hours, remainder = divmod(total_seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        if hours:
            return f"{hours}:{minutes:02d}:{seconds:02d}"
        return f"{minutes}:{seconds:02d}"

    @staticmethod
    def _attach_requester(track: wavelink.Playable, requester: discord.Member) -> None:
        extras = {}
        if hasattr(track, "extras") and isinstance(track.extras, dict):
            extras = dict(track.extras)
        extras["requester_id"] = requester.id
        extras["requester_name"] = requester.display_name
        track.extras = extras

    @staticmethod
    def _get_requester_info(track: wavelink.Playable) -> tuple[Optional[int], Optional[str]]:
        if hasattr(track, "extras") and isinstance(track.extras, dict):
            requester_id = track.extras.get("requester_id")
            requester_name = track.extras.get("requester_name")
            return requester_id, requester_name
        return None, None

    def format_requester(self, track: wavelink.Playable, guild: Optional[discord.Guild] = None) -> str:
        requester_id, requester_name = self._get_requester_info(track)
        if requester_id:
            guild = guild or self.guild
            if guild:
                member = guild.get_member(requester_id)
                if member:
                    return member.mention
            return f"<@{requester_id}>"
        if requester_name:
            return requester_name
        return "未知"

    async def connect_to_voice(self, channel: discord.VoiceChannel):
        """連接到語音頻道"""
        try:
            _ensure_voice_ws_mode_fallback()

            guild_voice_client = self._get_existing_voice_client(channel.guild)

            if guild_voice_client and self._is_connected(guild_voice_client):
                if guild_voice_client.channel == channel:
                    self.voice_client = guild_voice_client
                    logger.info(f"✅ 已在語音頻道: {channel.name}")
                    return
                try:
                    await guild_voice_client.move_to(channel)
                    self.voice_client = guild_voice_client
                    logger.info(f"🔄 移動到語音頻道: {channel.name}")
                    return
                except Exception as move_error:
                    logger.warning(f"移動失敗，嘗試重新連接: {move_error}")

            if self.voice_client and self._is_connected(self.voice_client):
                if self.voice_client.channel == channel:
                    logger.info(f"✅ 已在語音頻道: {channel.name}")
                    return
                try:
                    await self.voice_client.move_to(channel)
                    logger.info(f"🔄 移動到語音頻道: {channel.name}")
                    return
                except Exception as move_error:
                    logger.warning(f"移動失敗，嘗試重新連接: {move_error}")
                    await self.disconnect()

            self.voice_client = await channel.connect(cls=wavelink.Player)
            await self.set_volume(self.volume)
            self.set_loop_mode(self.loop_mode)
            logger.info(f"🔗 連接到語音頻道: {channel.name}")

        except Exception as e:
            logger.error(f"❌ 語音連接失敗: {e}")
            await self.send_embed("❌ 連接失敗", f"無法連接到語音頻道: {str(e)}", "error")
            raise

    @staticmethod
    def _is_connected(client: Optional[wavelink.Player]) -> bool:
        if not client:
            return False
        if hasattr(client, "connected"):
            return bool(client.connected)
        if hasattr(client, "is_connected"):
            return client.is_connected()
        return False

    async def disconnect(self):
        """斷開語音連接"""
        if self.voice_client:
            await self.voice_client.disconnect()
            self.voice_client = None

    async def add_song(
        self, url_or_search: str, requester: discord.Member
    ) -> Optional[wavelink.Playable]:
        """添加歌曲到播放列表"""
        try:
            self.last_error = None
            if not self.voice_client:
                return None

            if not self._is_url(url_or_search):
                url_or_search = f"ytsearch:{url_or_search}"

            tracks = await wavelink.Pool.fetch_tracks(url_or_search)
            if not tracks:
                return None

            if isinstance(tracks, wavelink.Playlist):
                if not tracks.tracks:
                    return None
                for track in tracks.tracks:
                    self._attach_requester(track, requester)
                    self.voice_client.queue.put(track)
                return tracks.tracks[0]

            if isinstance(tracks, list):
                track = tracks[0]
            else:
                track = tracks

            if not track:
                return None

            self._attach_requester(track, requester)
            self.voice_client.queue.put(track)
            return track
        except Exception as e:
            self.last_error = str(e)
            logger.error(f"添加歌曲失敗: {e}")
            return None

    @staticmethod
    def _is_url(url: str) -> bool:
        return bool(re.match(r"https?://", url))

    async def play_next(self):
        """播放下一首歌曲"""
        if not self.voice_client:
            return

        if len(self.voice_client.queue) == 0:
            await self.send_embed("🎵 播放列表已結束", "所有歌曲播放完畢", "info")
            return

        try:
            track = self.voice_client.queue.get()
            await self.voice_client.play(track, volume=int(self.volume * 100))
            logger.info(f"🎵 開始播放: {track.title}")
            await self.send_now_playing()
        except Exception as e:
            logger.error(f"播放錯誤: {e}")
            await self.send_embed("❌ 播放錯誤", str(e), "error")

    async def pause(self):
        """暫停播放"""
        if self.voice_client and self.voice_client.playing:
            await self.voice_client.pause(True)

    async def resume(self):
        """恢復播放"""
        if self.voice_client and self.voice_client.paused:
            await self.voice_client.pause(False)

    async def stop(self):
        """停止播放"""
        if self.voice_client:
            self.voice_client.queue.clear()
            if self.voice_client.playing or self.voice_client.paused:
                if hasattr(self.voice_client, "stop"):
                    await self.voice_client.stop()
                else:
                    await self.voice_client.skip()

    async def skip(self, force: bool = False):
        """跳過當前歌曲"""
        if not force:
            # 需要投票跳過
            return False

        if self.voice_client and (self.voice_client.playing or self.voice_client.paused):
            await self.voice_client.skip()

        return True

    async def set_volume(self, volume: float):
        """設置音量"""
        self.volume = max(0.0, min(1.0, volume))
        if self.voice_client:
            await self.voice_client.set_volume(int(self.volume * 100))

    def set_loop_mode(self, mode: LoopMode) -> None:
        self.loop_mode = mode
        if self.voice_client:
            mode_map = {
                LoopMode.NONE: wavelink.QueueMode.normal,
                LoopMode.SINGLE: wavelink.QueueMode.loop,
                LoopMode.QUEUE: wavelink.QueueMode.loop_all,
            }
            self.voice_client.queue.mode = mode_map.get(mode, wavelink.QueueMode.normal)

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
        requester_text = self.format_requester(self.current)
        duration_str = self._format_duration_ms(getattr(self.current, "length", 0))
        uploader = getattr(self.current, "author", "Unknown")

        embed.add_field(
            name="詳細信息",
            value=f"👤 上傳者: {uploader}\n"
            f"⏱️ 時長: {duration_str}\n"
            f"🎧 點播者: {requester_text}",
            inline=True,
        )

        if self.queue:
            embed.add_field(
                name="播放列表",
                value=f"📝 還有 {len(self.queue)} 首歌曲等待播放",
                inline=True,
            )

        embed.add_field(name="播放模式", value=f"🔁 {self.loop_mode.value}", inline=True)

        thumbnail = (
            getattr(self.current, "artwork", None)
            or getattr(self.current, "thumbnail", None)
            or getattr(self.current, "thumb", None)
        )
        if thumbnail:
            embed.set_thumbnail(url=thumbnail)

        await self.channel.send(embed=embed)


class MusicCore(commands.Cog):
    """音樂系統核心"""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.players: Dict[int, MusicPlayer] = {}
        self.settings_dao = MusicDAO()
        self._lavalink_connected = False
        self._lavalink_lock = asyncio.Lock()
        self._lavalink_error: Optional[str] = None
        self.DISABLED_SLASH_COMMANDS = {
            "play",
            "music_control",
            "queue",
            "voice_debug",
            "voice_connect",
            "connection_status",
        }
        logger.info("🎵 音樂系統核心初始化完成")

    def _build_lavalink_uri(self) -> Optional[str]:
        if LAVALINK_URI:
            return LAVALINK_URI
        if not LAVALINK_HOST:
            return None
        scheme = "https" if LAVALINK_SECURE else "http"
        return f"{scheme}://{LAVALINK_HOST}:{LAVALINK_PORT}"

    async def ensure_lavalink_ready(self) -> bool:
        nodes = getattr(wavelink.Pool, "nodes", None)
        if self._lavalink_connected and nodes:
            return True

        async with self._lavalink_lock:
            nodes = getattr(wavelink.Pool, "nodes", None)
            if self._lavalink_connected and nodes:
                return True

            uri = self._build_lavalink_uri()
            if not uri or not LAVALINK_PASSWORD:
                self._lavalink_error = "缺少 Lavalink 連線設定"
                logger.error("❌ Lavalink 連線設定不足，請檢查環境變數")
                return False

            try:
                node = wavelink.Node(
                    uri=uri,
                    password=LAVALINK_PASSWORD,
                    identifier="main",
                )
                await wavelink.Pool.connect(nodes=[node], client=self.bot)
                self._lavalink_connected = True
                self._lavalink_error = None
                logger.info("✅ Lavalink 連線成功")
                return True
            except Exception as exc:
                self._lavalink_connected = False
                self._lavalink_error = str(exc)
                logger.error("❌ Lavalink 連線失敗: %s", exc)
                return False

    @staticmethod
    def _can_use_music_menu(
        member: discord.Member,
        allowed_role_ids: list[int],
        require_role: bool,
        is_owner: bool = False,
    ) -> bool:
        if is_owner:
            return True
        if member.guild_permissions.administrator or member.guild_permissions.manage_guild:
            return True
        if not require_role:
            return True
        if not allowed_role_ids:
            return False
        member_role_ids = {role.id for role in member.roles}
        return bool(member_role_ids & set(allowed_role_ids))

    @commands.Cog.listener()
    async def on_ready(self):
        await self.ensure_lavalink_ready()

    @commands.Cog.listener()
    async def on_wavelink_node_ready(self, *args, **kwargs):
        """支援不同版本的 NodeReady 事件 payload"""
        try:
            payload = args[0] if args else kwargs.get("payload") or kwargs.get("node")
            node = getattr(payload, "node", None) or payload
            identifier = getattr(node, "identifier", "unknown")
            logger.info("✅ Lavalink Node 已就緒: %s", identifier)
        except Exception as exc:
            logger.error("處理 Lavalink NodeReady 事件失敗: %s", exc)

    @commands.Cog.listener()
    async def on_wavelink_track_end(self, payload):
        try:
            player = getattr(payload, "player", None)
            if not player:
                return

            queue = player.queue
            queue_empty = len(queue) == 0

            music_player = self.players.get(player.guild.id)
            if queue_empty:
                if music_player:
                    await music_player.send_embed("🎵 播放列表已結束", "所有歌曲播放完畢", "info")
                return

            next_track = queue.get()
            await player.play(next_track, volume=player.volume)

            if music_player:
                music_player.voice_client = player
                await music_player.send_now_playing()
        except Exception as exc:
            logger.error("播放下一首時發生錯誤: %s", exc)

    def get_player(self, ctx: commands.Context) -> MusicPlayer:
        """獲取音樂播放器"""
        if ctx.guild.id not in self.players:
            self.players[ctx.guild.id] = MusicPlayer(ctx)
        return self.players[ctx.guild.id]

    def _check_voice_connection(self, player: MusicPlayer, guild) -> bool:
        """增強的語音連接狀態檢測"""
        try:
            # 檢查 player 的 voice_client
            player_connected = player.is_connected()

            # 檢查 guild 的 voice_client (更可靠)
            guild_voice_client = guild.voice_client
            if isinstance(guild_voice_client, wavelink.Player):
                guild_connected = MusicPlayer._is_connected(guild_voice_client)
            else:
                guild_connected = False

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

            if not await self.ensure_lavalink_ready():
                embed = EmbedBuilder.create_error_embed(
                    "❌ 音樂服務未就緒",
                    "Lavalink 尚未連線，請稍後再試或聯絡管理員檢查設定",
                )
                await interaction.followup.send(embed=embed, ephemeral=True)
                return

            # 檢查用戶是否在語音頻道
            if not interaction.user.voice or not interaction.user.voice.channel:
                embed = EmbedBuilder.create_error_embed(
                    "❌ 請先加入語音頻道",
                    "您需要先加入一個語音頻道才能播放音樂",
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
                    "❌ 無法播放",
                    "無法找到或播放此音樂，請檢查網址或搜索關鍵字",
                )
                await interaction.followup.send(embed=embed, ephemeral=True)
                return

            # 如果沒有正在播放，開始播放
            if not player.is_playing:
                await player.play_next()

            duration_str = player._format_duration_ms(getattr(source, "length", 0))
            uploader = getattr(source, "author", "Unknown")

            embed = EmbedBuilder.create_success_embed(
                "✅ 已添加到播放列表",
                f"**{source.title}**\n👤 {uploader}\n⏱️ {duration_str}",
            )

            if player.queue or player.current != source:
                embed.add_field(
                    name="排隊位置",
                    value=f"第 {len(player.queue)} 位",
                    inline=True,
                )

            thumbnail = (
                getattr(source, "artwork", None)
                or getattr(source, "thumbnail", None)
                or getattr(source, "thumb", None)
            )
            if thumbnail:
                embed.set_thumbnail(url=thumbnail)

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
            from potato_bot.views.music_views import MusicControlView

            if is_connected:
                embed = EmbedBuilder.create_info_embed("🎛️ 音樂控制面板", "使用下方按鈕控制音樂播放")
            else:
                embed = EmbedBuilder.create_warning_embed(
                    "🎛️ 音樂控制面板",
                    "Bot 目前未連接語音頻道，請先使用音樂面板的播放功能",
                )

            if player.current:
                uploader = getattr(player.current, "author", "Unknown")
                requester_text = player.format_requester(player.current, interaction.guild)
                embed.add_field(
                    name="🎵 正在播放",
                    value=f"**{player.current.title}**\n"
                    f"👤 {uploader}\n"
                    f"🎧 {requester_text}",
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
                current_duration = player._format_duration_ms(getattr(player.current, "length", 0))
                requester_text = player.format_requester(player.current, interaction.guild)
                embed.add_field(
                    name="🎵 正在播放",
                    value=f"**{player.current.title}**\n"
                    f"⏱️ {current_duration} | 🎧 {requester_text}",
                    inline=False,
                )

            if player.queue:
                queue_text = ""
                for i, song in enumerate(player.queue[:10], 1):
                    song_duration = player._format_duration_ms(getattr(song, "length", 0))
                    song_requester_text = player.format_requester(song, interaction.guild)
                    queue_text += f"{i}. **{song.title}**\n"
                    queue_text += f"   ⏱️ {song_duration} | 🎧 {song_requester_text}\n\n"

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
                logger.info(
                    f"🔍 player_vc.connected = {MusicPlayer._is_connected(player_vc)}"
                )
                player_connected = MusicPlayer._is_connected(player_vc)

            if guild_vc:
                logger.info(
                    f"🔍 guild_vc.connected = {MusicPlayer._is_connected(guild_vc)}"
                )
                logger.info(f"🔍 guild_vc.channel = {guild_vc.channel}")
                guild_connected = MusicPlayer._is_connected(guild_vc)

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
                    value=f"頻道: {guild_vc.channel}\n"
                    f"連接狀態: {MusicPlayer._is_connected(guild_vc)}",
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
                embed.add_field(
                    name="ℹ️ 狀態正常",
                    value="兩者都未連接，狀態一致。",
                    inline=False,
                )
            else:
                embed.add_field(
                    name="✅ 狀態正常",
                    value="兩者都已連接，狀態一致。",
                    inline=False,
                )

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
                if guild_vc and MusicPlayer._is_connected(guild_vc):
                    # 同步 player 狀態
                    player.voice_client = guild_vc

                    embed = EmbedBuilder.create_success_embed(
                        "✅ 語音連接成功", f"Bot 已連接到 **{channel.name}**"
                    )

                    latency = getattr(guild_vc, "latency", None)
                    latency_text = f"{latency:.2f}ms" if latency is not None else "未知"
                    embed.add_field(
                        name="連接詳情",
                        value=f"頻道: {guild_vc.channel}\n"
                        f"延遲: {latency_text}\n"
                        f"連接狀態: {MusicPlayer._is_connected(guild_vc)}",
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
    @app_commands.checks.has_permissions(administrator=True)
    async def connection_status(self, interaction: discord.Interaction):
        """檢查 Bot 的連接狀態"""
        try:
            await interaction.response.defer()

            # 基本信息
            bot = self.bot
            guild_count = len(bot.guilds)
            user_count = sum(guild.member_count for guild in bot.guilds)

            embed = EmbedBuilder.create_info_embed(
                "🤖 Bot 狀態報告",
                f"Bot: {bot.user.name}#{bot.user.discriminator}",
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
                embed.add_field(
                    name="❌ 錯誤",
                    value="無法獲取當前伺服器信息",
                    inline=False,
                )

            # 所有伺服器列表
            if guild_count > 0:
                guilds_info = []
                for i, guild in enumerate(bot.guilds[:5]):  # 只顯示前5個
                    guilds_info.append(f"{i+1}. {guild.name} (ID: {guild.id})")

                if guild_count > 5:
                    guilds_info.append(f"... 還有 {guild_count - 5} 個伺服器")

                embed.add_field(
                    name="伺服器列表",
                    value="\n".join(guilds_info),
                    inline=False,
                )
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

            if not interaction.guild:
                await interaction.response.send_message("❌ 僅能在伺服器中使用。", ephemeral=True)
                return

            settings = await self.settings_dao.get_music_settings(interaction.guild.id)
            allowed_roles = settings.get("allowed_role_ids", []) if settings else []
            require_role = settings.get("require_role_to_use", False) if settings else False
            is_owner = await interaction.client.is_owner(interaction.user)

            if not self._can_use_music_menu(
                interaction.user, allowed_roles, require_role, is_owner=is_owner
            ):
                await interaction.response.send_message(
                    "❌ 你沒有使用音樂面板的權限，請聯絡管理員設定可使用身分組。",
                    ephemeral=True,
                )
                return

            if not await self.ensure_lavalink_ready():
                await interaction.response.send_message(
                    "❌ 音樂服務尚未連線，請稍後再試或通知管理員檢查 Lavalink。",
                    ephemeral=True,
                )
                return

            from potato_bot.views.music_views import MusicMenuView

            embed = EmbedBuilder.create_info_embed(
                "🎵 音樂系統",
                "歡迎使用 Potato Bot 音樂系統！\n支援 YouTube 直接播放",
            )

            embed.add_field(
                name="🎯 主要功能",
                value="🎵 播放音樂\n🎛️ 控制面板\n📝 播放列表\n🔍 搜索音樂\n🗂️ 列表管理（管理員）",
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
    cog = MusicCore(bot)
    await bot.add_cog(cog)

    try:
        for name in cog.DISABLED_SLASH_COMMANDS:
            bot.tree.remove_command(name, type=discord.AppCommandType.chat_input)
    except Exception:
        pass

    logger.info("✅ 音樂系統核心已載入")
