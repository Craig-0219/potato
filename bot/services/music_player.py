# bot/services/music_player.py - 音樂播放服務
"""
音樂播放服務 v2.2.0
提供音樂播放、歌詞顯示、音樂問答等功能
"""

import asyncio
import aiohttp
import re
import random
import json
from typing import Dict, List, Optional, Any, Union
from datetime import datetime, timezone, timedelta
from dataclasses import dataclass, field
from enum import Enum
import discord
from discord.ext import commands

from shared.cache_manager import cache_manager, cached
from shared.logger import logger

class MusicSource(Enum):
    """音樂來源"""
    YOUTUBE = "youtube"
    SPOTIFY = "spotify"
    SOUNDCLOUD = "soundcloud"
    LOCAL = "local"

class PlaybackState(Enum):
    """播放狀態"""
    PLAYING = "playing"
    PAUSED = "paused"
    STOPPED = "stopped"
    LOADING = "loading"

class RepeatMode(Enum):
    """重複模式"""
    OFF = "off"
    TRACK = "track"
    QUEUE = "queue"

@dataclass
class Track:
    """音樂軌道"""
    title: str
    artist: str
    duration: int  # 秒
    url: str
    thumbnail: str
    source: MusicSource
    requested_by: int  # Discord用戶ID
    search_query: str = ""
    lyrics: Optional[str] = None
    
@dataclass
class Playlist:
    """播放清單"""
    name: str
    tracks: List[Track] = field(default_factory=list)
    owner_id: int = 0
    guild_id: int = 0
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    is_public: bool = True

@dataclass
class MusicSession:
    """音樂會話"""
    guild_id: int
    channel_id: int
    voice_channel_id: int
    current_track: Optional[Track] = None
    queue: List[Track] = field(default_factory=list)
    state: PlaybackState = PlaybackState.STOPPED
    repeat_mode: RepeatMode = RepeatMode.OFF
    shuffle: bool = False
    volume: float = 0.5
    position: int = 0  # 當前播放位置（秒）
    last_activity: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

class MusicQuizQuestion:
    """音樂問答題目"""
    def __init__(self, track: Track, question_type: str, options: List[str], correct_answer: str):
        self.track = track
        self.question_type = question_type  # "artist", "title", "year", "genre"
        self.options = options
        self.correct_answer = correct_answer
        self.difficulty = "medium"

class MusicPlayer:
    """音樂播放器"""
    
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.sessions: Dict[int, MusicSession] = {}  # guild_id -> MusicSession
        self.playlists: Dict[str, Playlist] = {}  # playlist_id -> Playlist
        
        # 音樂問答題庫
        self.quiz_questions = []
        
        # YouTube API相關（需要配置API密鑰）
        self.youtube_api_key = ""
        
        # 預設播放清單
        self.default_tracks = [
            Track(
                title="Lofi Hip Hop",
                artist="ChilledCow",
                duration=180,
                url="https://www.youtube.com/watch?v=5qap5aO4i9A",
                thumbnail="https://i.ytimg.com/vi/5qap5aO4i9A/default.jpg",
                source=MusicSource.YOUTUBE,
                requested_by=0,
                search_query="lofi hip hop"
            )
        ]
        
        logger.info("🎵 音樂播放器初始化完成")

    def configure_youtube_api(self, api_key: str):
        """配置YouTube API密鑰"""
        self.youtube_api_key = api_key
        logger.info("🔑 YouTube API密鑰已配置")

    # ========== 音樂會話管理 ==========

    async def get_session(self, guild_id: int) -> Optional[MusicSession]:
        """獲取音樂會話"""
        return self.sessions.get(guild_id)

    async def create_session(self, guild_id: int, channel_id: int, 
                           voice_channel_id: int) -> MusicSession:
        """創建音樂會話"""
        session = MusicSession(
            guild_id=guild_id,
            channel_id=channel_id,
            voice_channel_id=voice_channel_id
        )
        self.sessions[guild_id] = session
        logger.info(f"🎵 創建音樂會話: {guild_id}")
        return session

    async def remove_session(self, guild_id: int):
        """移除音樂會話"""
        if guild_id in self.sessions:
            del self.sessions[guild_id]
            logger.info(f"🎵 移除音樂會話: {guild_id}")

    # ========== 音樂搜尋 ==========

    async def search_youtube(self, query: str, max_results: int = 5) -> List[Track]:
        """搜尋YouTube音樂"""
        try:
            if not self.youtube_api_key:
                # 如果沒有API密鑰，返回模擬結果
                return await self._mock_search_results(query, max_results)
            
            # 使用YouTube API搜尋
            url = "https://www.googleapis.com/youtube/v3/search"
            params = {
                "part": "snippet",
                "q": query,
                "type": "video",
                "videoCategoryId": "10",  # 音樂類別
                "maxResults": max_results,
                "key": self.youtube_api_key
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params) as response:
                    if response.status == 200:
                        data = await response.json()
                        tracks = []
                        
                        for item in data.get("items", []):
                            track = Track(
                                title=item["snippet"]["title"],
                                artist=item["snippet"]["channelTitle"],
                                duration=0,  # 需要額外API調用獲取時長
                                url=f"https://www.youtube.com/watch?v={item['id']['videoId']}",
                                thumbnail=item["snippet"]["thumbnails"]["default"]["url"],
                                source=MusicSource.YOUTUBE,
                                requested_by=0,
                                search_query=query
                            )
                            tracks.append(track)
                        
                        return tracks
                    else:
                        logger.error(f"❌ YouTube API錯誤: {response.status}")
                        return await self._mock_search_results(query, max_results)
                        
        except Exception as e:
            logger.error(f"❌ YouTube搜尋失敗: {e}")
            return await self._mock_search_results(query, max_results)

    async def _mock_search_results(self, query: str, max_results: int) -> List[Track]:
        """模擬搜尋結果（用於開發和演示）"""
        mock_results = [
            Track(
                title=f"搜尋結果: {query} - 歌曲 1",
                artist="未知歌手",
                duration=210,
                url="https://www.youtube.com/watch?v=dQw4w9WgXcQ",
                thumbnail="https://i.ytimg.com/vi/dQw4w9WgXcQ/default.jpg",
                source=MusicSource.YOUTUBE,
                requested_by=0,
                search_query=query
            ),
            Track(
                title=f"搜尋結果: {query} - 歌曲 2",
                artist="另一個歌手",
                duration=195,
                url="https://www.youtube.com/watch?v=dQw4w9WgXcQ",
                thumbnail="https://i.ytimg.com/vi/dQw4w9WgXcQ/default.jpg",
                source=MusicSource.YOUTUBE,
                requested_by=0,
                search_query=query
            )
        ]
        
        return mock_results[:max_results]

    # ========== 播放控制 ==========

    async def play_track(self, guild_id: int, track: Track) -> bool:
        """播放音樂軌道"""
        try:
            session = await self.get_session(guild_id)
            if not session:
                logger.error(f"❌ 找不到音樂會話: {guild_id}")
                return False
            
            # 模擬播放（實際實現需要discord.py的voice功能）
            session.current_track = track
            session.state = PlaybackState.PLAYING
            session.position = 0
            session.last_activity = datetime.now(timezone.utc)
            
            logger.info(f"🎵 開始播放: {track.title} - {track.artist}")
            return True
            
        except Exception as e:
            logger.error(f"❌ 播放音樂失敗: {e}")
            return False

    async def pause_playback(self, guild_id: int) -> bool:
        """暫停播放"""
        try:
            session = await self.get_session(guild_id)
            if session and session.state == PlaybackState.PLAYING:
                session.state = PlaybackState.PAUSED
                logger.info(f"⏸️ 暫停播放: {guild_id}")
                return True
            return False
            
        except Exception as e:
            logger.error(f"❌ 暫停播放失敗: {e}")
            return False

    async def resume_playback(self, guild_id: int) -> bool:
        """恢復播放"""
        try:
            session = await self.get_session(guild_id)
            if session and session.state == PlaybackState.PAUSED:
                session.state = PlaybackState.PLAYING
                logger.info(f"▶️ 恢復播放: {guild_id}")
                return True
            return False
            
        except Exception as e:
            logger.error(f"❌ 恢復播放失敗: {e}")
            return False

    async def stop_playback(self, guild_id: int) -> bool:
        """停止播放"""
        try:
            session = await self.get_session(guild_id)
            if session:
                session.state = PlaybackState.STOPPED
                session.current_track = None
                session.position = 0
                logger.info(f"⏹️ 停止播放: {guild_id}")
                return True
            return False
            
        except Exception as e:
            logger.error(f"❌ 停止播放失敗: {e}")
            return False

    async def skip_track(self, guild_id: int) -> Optional[Track]:
        """跳過當前曲目"""
        try:
            session = await self.get_session(guild_id)
            if not session or not session.queue:
                return None
            
            # 獲取下一首
            next_track = session.queue.pop(0)
            
            # 如果是重複模式，處理重複邏輯
            if session.repeat_mode == RepeatMode.TRACK and session.current_track:
                session.queue.insert(0, session.current_track)
            elif session.repeat_mode == RepeatMode.QUEUE and session.current_track:
                session.queue.append(session.current_track)
            
            # 播放下一首
            await self.play_track(guild_id, next_track)
            return next_track
            
        except Exception as e:
            logger.error(f"❌ 跳過曲目失敗: {e}")
            return None

    # ========== 播放清單管理 ==========

    async def add_to_queue(self, guild_id: int, track: Track) -> bool:
        """添加到播放佇列"""
        try:
            session = await self.get_session(guild_id)
            if not session:
                return False
            
            session.queue.append(track)
            logger.info(f"➕ 添加到佇列: {track.title}")
            return True
            
        except Exception as e:
            logger.error(f"❌ 添加到佇列失敗: {e}")
            return False

    async def remove_from_queue(self, guild_id: int, index: int) -> Optional[Track]:
        """從佇列移除曲目"""
        try:
            session = await self.get_session(guild_id)
            if not session or index < 0 or index >= len(session.queue):
                return None
            
            removed_track = session.queue.pop(index)
            logger.info(f"➖ 從佇列移除: {removed_track.title}")
            return removed_track
            
        except Exception as e:
            logger.error(f"❌ 從佇列移除失敗: {e}")
            return None

    async def shuffle_queue(self, guild_id: int) -> bool:
        """隨機播放佇列"""
        try:
            session = await self.get_session(guild_id)
            if not session or len(session.queue) < 2:
                return False
            
            random.shuffle(session.queue)
            session.shuffle = True
            logger.info(f"🔀 隨機播放佇列: {guild_id}")
            return True
            
        except Exception as e:
            logger.error(f"❌ 隨機播放失敗: {e}")
            return False

    async def clear_queue(self, guild_id: int) -> int:
        """清空播放佇列"""
        try:
            session = await self.get_session(guild_id)
            if not session:
                return 0
            
            cleared_count = len(session.queue)
            session.queue.clear()
            logger.info(f"🗑️ 清空佇列: {guild_id} ({cleared_count} 首)")
            return cleared_count
            
        except Exception as e:
            logger.error(f"❌ 清空佇列失敗: {e}")
            return 0

    # ========== 播放清單功能 ==========

    async def create_playlist(self, name: str, owner_id: int, guild_id: int) -> str:
        """創建播放清單"""
        try:
            playlist_id = f"{guild_id}_{owner_id}_{int(datetime.now().timestamp())}"
            playlist = Playlist(
                name=name,
                owner_id=owner_id,
                guild_id=guild_id
            )
            
            self.playlists[playlist_id] = playlist
            logger.info(f"📝 創建播放清單: {name} ({playlist_id})")
            return playlist_id
            
        except Exception as e:
            logger.error(f"❌ 創建播放清單失敗: {e}")
            return ""

    async def add_track_to_playlist(self, playlist_id: str, track: Track) -> bool:
        """添加曲目到播放清單"""
        try:
            playlist = self.playlists.get(playlist_id)
            if not playlist:
                return False
            
            playlist.tracks.append(track)
            logger.info(f"➕ 添加曲目到播放清單: {track.title} -> {playlist.name}")
            return True
            
        except Exception as e:
            logger.error(f"❌ 添加曲目到播放清單失敗: {e}")
            return False

    async def load_playlist(self, guild_id: int, playlist_id: str) -> bool:
        """載入播放清單到佇列"""
        try:
            playlist = self.playlists.get(playlist_id)
            if not playlist:
                return False
            
            session = await self.get_session(guild_id)
            if not session:
                return False
            
            # 添加所有曲目到佇列
            session.queue.extend(playlist.tracks.copy())
            logger.info(f"📂 載入播放清單: {playlist.name} ({len(playlist.tracks)} 首)")
            return True
            
        except Exception as e:
            logger.error(f"❌ 載入播放清單失敗: {e}")
            return False

    # ========== 音樂問答 ==========

    async def generate_music_quiz(self, difficulty: str = "medium") -> Optional[MusicQuizQuestion]:
        """生成音樂問答題目"""
        try:
            # 從預設曲目中隨機選擇
            if not self.default_tracks:
                return None
            
            track = random.choice(self.default_tracks)
            
            # 隨機選擇問答類型
            question_types = ["artist", "title", "genre"]
            question_type = random.choice(question_types)
            
            if question_type == "artist":
                correct_answer = track.artist
                options = [track.artist, "未知歌手", "隨機歌手", "另一個歌手"]
            elif question_type == "title":
                correct_answer = track.title
                options = [track.title, "隨機歌名", "另一首歌", "未知歌曲"]
            else:  # genre
                correct_answer = "Lo-fi Hip Hop"
                options = ["Lo-fi Hip Hop", "Pop", "Rock", "Jazz"]
            
            # 隨機打亂選項
            random.shuffle(options)
            
            question = MusicQuizQuestion(track, question_type, options, correct_answer)
            question.difficulty = difficulty
            
            return question
            
        except Exception as e:
            logger.error(f"❌ 生成音樂問答失敗: {e}")
            return None

    # ========== 歌詞功能 ==========

    async def get_lyrics(self, track: Track) -> Optional[str]:
        """獲取歌詞"""
        try:
            # 檢查快取
            cache_key = f"lyrics:{track.artist}:{track.title}"
            cached_lyrics = await cache_manager.get(cache_key)
            if cached_lyrics:
                return cached_lyrics
            
            # 模擬歌詞獲取（實際實現可以整合歌詞API）
            mock_lyrics = f"""
[verse 1]
這是 {track.title} 的歌詞
由 {track.artist} 演唱
一首美妙的音樂作品

[chorus]
La la la la la
Music makes the world go round
La la la la la
感受音樂的力量

[verse 2]
歌詞展示功能演示
讓音樂更有意義
享受這美好的時光

[outro]
感謝聆聽這首歌曲
希望您喜歡這次的音樂體驗
            """.strip()
            
            # 快取歌詞
            await cache_manager.set(cache_key, mock_lyrics, 3600)  # 1小時快取
            
            return mock_lyrics
            
        except Exception as e:
            logger.error(f"❌ 獲取歌詞失敗: {e}")
            return None

    # ========== 統計功能 ==========

    async def get_session_stats(self, guild_id: int) -> Dict[str, Any]:
        """獲取會話統計"""
        try:
            session = await self.get_session(guild_id)
            if not session:
                return {}
            
            return {
                "current_track": session.current_track.title if session.current_track else None,
                "queue_length": len(session.queue),
                "state": session.state.value,
                "repeat_mode": session.repeat_mode.value,
                "shuffle": session.shuffle,
                "volume": session.volume,
                "position": session.position,
                "last_activity": session.last_activity
            }
            
        except Exception as e:
            logger.error(f"❌ 獲取會話統計失敗: {e}")
            return {}

    async def get_popular_tracks(self, guild_id: int, limit: int = 10) -> List[Track]:
        """獲取熱門曲目"""
        try:
            # 模擬熱門曲目（實際實現可以基於播放統計）
            popular_tracks = self.default_tracks.copy()
            
            # 添加更多模擬曲目
            for i in range(min(limit, 5)):
                track = Track(
                    title=f"熱門歌曲 {i+1}",
                    artist=f"熱門歌手 {i+1}",
                    duration=180 + i * 30,
                    url="https://www.youtube.com/watch?v=dQw4w9WgXcQ",
                    thumbnail="https://i.ytimg.com/vi/dQw4w9WgXcQ/default.jpg",
                    source=MusicSource.YOUTUBE,
                    requested_by=0
                )
                popular_tracks.append(track)
            
            return popular_tracks[:limit]
            
        except Exception as e:
            logger.error(f"❌ 獲取熱門曲目失敗: {e}")
            return []

# 全域實例將在cog中創建