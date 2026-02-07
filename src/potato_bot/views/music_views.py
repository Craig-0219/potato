# bot/views/music_views.py - 音樂系統視圖組件（重寫版）
"""
音樂系統 Discord GUI 視圖組件 v2.3.1
完全重寫的互動處理機制，解決超時和響應問題
"""

import traceback

import discord
import wavelink

from potato_bot.utils.embed_builder import EmbedBuilder
from potato_shared.logger import logger


def _format_track_length(length_ms: int) -> str:
    if not length_ms:
        return "未知"
    total_seconds = int(length_ms // 1000)
    hours, remainder = divmod(total_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    if hours:
        return f"{hours}:{minutes:02d}:{seconds:02d}"
    return f"{minutes}:{seconds:02d}"


def _truncate(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    return text[: max(0, limit - 3)] + "..."


def _build_queue_manage_embed(player, guild: discord.Guild) -> discord.Embed:
    embed = EmbedBuilder.create_info_embed("🗂️ 播放列表管理", "管理播放列表內容")

    if player.current:
        uploader = getattr(player.current, "author", "Unknown")
        duration = _format_track_length(getattr(player.current, "length", 0))
        requester_text = player.format_requester(player.current, guild)
        embed.add_field(
            name="🎵 正在播放",
            value=f"**{player.current.title}**\n"
            f"👤 {uploader}\n"
            f"⏱️ {duration} | 🎧 {requester_text}",
            inline=False,
        )

    queue_items = player.queue
    if queue_items:
        preview_lines = []
        for i, track in enumerate(queue_items[:20], 1):
            duration = _format_track_length(getattr(track, "length", 0))
            preview_lines.append(f"{i}. {track.title} ({duration})")
        if len(queue_items) > 20:
            preview_lines.append(f"... 還有 {len(queue_items) - 20} 首")
        embed.add_field(
            name=f"📝 待播列表 ({len(queue_items)} 首)",
            value="\n".join(preview_lines),
            inline=False,
        )
    else:
        embed.add_field(name="📝 待播列表", value="播放列表為空", inline=False)

    embed.set_footer(text="此面板僅管理員可用")
    return embed


class SafeInteractionMixin:
    """安全互動處理混入類"""

    async def safe_respond(
        self,
        interaction: discord.Interaction,
        embed: discord.Embed = None,
        content: str = None,
        ephemeral: bool = True,
        view: discord.ui.View = None,
    ):
        """安全響應處理，避免超時和重複響應"""
        try:
            # 檢查 interaction 是否仍然有效
            if not interaction or not hasattr(interaction, "response"):
                logger.error("無效的 interaction 對象")
                return

            # 檢查是否已響應
            if interaction.response.is_done():
                # 使用 followup - 檢查 view 參數
                if embed:
                    if view is not None:
                        await interaction.followup.send(embed=embed, ephemeral=ephemeral, view=view)
                    else:
                        await interaction.followup.send(embed=embed, ephemeral=ephemeral)
                else:
                    if view is not None:
                        await interaction.followup.send(
                            content=content, ephemeral=ephemeral, view=view
                        )
                    else:
                        await interaction.followup.send(content=content, ephemeral=ephemeral)
            else:
                # 使用原始響應 - 檢查 view 參數
                if embed:
                    if view is not None:
                        await interaction.response.send_message(
                            embed=embed, ephemeral=ephemeral, view=view
                        )
                    else:
                        await interaction.response.send_message(embed=embed, ephemeral=ephemeral)
                else:
                    if view is not None:
                        await interaction.response.send_message(
                            content=content, ephemeral=ephemeral, view=view
                        )
                    else:
                        await interaction.response.send_message(
                            content=content, ephemeral=ephemeral
                        )
        except discord.errors.InteractionResponded:
            # 如果仍然失敗，嘗試 followup - 檢查 view 參數
            try:
                if embed:
                    if view is not None:
                        await interaction.followup.send(embed=embed, ephemeral=ephemeral, view=view)
                    else:
                        await interaction.followup.send(embed=embed, ephemeral=ephemeral)
                else:
                    if view is not None:
                        await interaction.followup.send(
                            content=content, ephemeral=ephemeral, view=view
                        )
                    else:
                        await interaction.followup.send(content=content, ephemeral=ephemeral)
            except Exception as e:
                logger.error(f"安全響應最終失敗: {e}")
        except discord.errors.NotFound:
            logger.warning("互動已過期或無效")
        except Exception as e:
            logger.error(f"安全響應錯誤: {e}")
            logger.error(traceback.format_exc())


class MusicControlView(discord.ui.View, SafeInteractionMixin):
    """音樂控制面板視圖 - 重寫版"""

    def __init__(self, player):
        super().__init__(timeout=300)
        self.player = player

    @discord.ui.button(label="⏯️", style=discord.ButtonStyle.primary, custom_id="music_toggle")
    async def toggle_play(self, interaction: discord.Interaction, button: discord.ui.Button):
        """播放/暫停按鈕 - 重寫版"""
        try:
            logger.info(f"播放/暫停按鈕被點擊 - 用戶: {interaction.user.name}")

            if not self.player.is_connected():
                embed = EmbedBuilder.create_error_embed(
                    "❌ 未連接語音頻道", "Bot 目前未連接到任何語音頻道"
                )
                await self.safe_respond(interaction, embed=embed)
                return

            # 處理播放/暫停
            if self.player.is_playing:
                await self.player.voice_client.pause(True)
                embed = EmbedBuilder.create_success_embed("⏸️ 已暫停", "音樂播放已暫停")
                logger.info("音樂已暫停")
            elif self.player.is_paused:
                await self.player.voice_client.pause(False)
                embed = EmbedBuilder.create_success_embed("▶️ 已恢復", "音樂播放已恢復")
                logger.info("音樂已恢復")
            else:
                embed = EmbedBuilder.create_warning_embed("ℹ️ 未播放", "目前沒有音樂正在播放")

            await self.safe_respond(interaction, embed=embed)

        except Exception as e:
            logger.error(f"播放/暫停按鈕錯誤: {e}")
            logger.error(traceback.format_exc())
            embed = EmbedBuilder.create_error_embed("❌ 操作失敗", "播放控制出現錯誤")
            await self.safe_respond(interaction, embed=embed)

    @discord.ui.button(label="⏭️", style=discord.ButtonStyle.secondary, custom_id="music_skip")
    async def skip_song(self, interaction: discord.Interaction, button: discord.ui.Button):
        """跳過歌曲按鈕 - 重寫版"""
        try:
            logger.info(f"跳過按鈕被點擊 - 用戶: {interaction.user.name}")

            if not self.player.is_connected():
                embed = EmbedBuilder.create_error_embed(
                    "❌ 未連接語音頻道", "Bot 目前未連接到任何語音頻道"
                )
                await self.safe_respond(interaction, embed=embed)
                return

            if not self.player.current:
                embed = EmbedBuilder.create_warning_embed(
                    "ℹ️ 沒有播放中的音樂", "目前沒有音樂正在播放"
                )
                await self.safe_respond(interaction, embed=embed)
                return

            # 跳過當前歌曲
            current_title = self.player.current.title
            if self.player.is_playing or self.player.is_paused:
                await self.player.skip(force=True)

            embed = EmbedBuilder.create_success_embed("⏭️ 已跳過", f"已跳過：**{current_title}**")
            await self.safe_respond(interaction, embed=embed)
            logger.info(f"跳過歌曲: {current_title}")

        except Exception as e:
            logger.error(f"跳過按鈕錯誤: {e}")
            logger.error(traceback.format_exc())
            embed = EmbedBuilder.create_error_embed("❌ 操作失敗", "跳過操作出現錯誤")
            await self.safe_respond(interaction, embed=embed)

    @discord.ui.button(label="🔁", style=discord.ButtonStyle.secondary, custom_id="music_loop")
    async def toggle_loop(self, interaction: discord.Interaction, button: discord.ui.Button):
        """循環模式按鈕 - 重寫版"""
        try:
            logger.info(f"循環按鈕被點擊 - 用戶: {interaction.user.name}")

            # 切換循環模式
            from potato_bot.cogs.music_core import LoopMode

            if self.player.loop_mode == LoopMode.NONE:
                self.player.set_loop_mode(LoopMode.SINGLE)
                mode_text = "🔂 單曲循環"
            elif self.player.loop_mode == LoopMode.SINGLE:
                self.player.set_loop_mode(LoopMode.QUEUE)
                mode_text = "🔁 列表循環"
            else:
                self.player.set_loop_mode(LoopMode.NONE)
                mode_text = "➡️ 順序播放"

            embed = EmbedBuilder.create_success_embed("🔁 循環模式已變更", f"當前模式：{mode_text}")
            await self.safe_respond(interaction, embed=embed)
            logger.info(f"循環模式切換至: {mode_text}")

        except Exception as e:
            logger.error(f"循環按鈕錯誤: {e}")
            logger.error(traceback.format_exc())
            embed = EmbedBuilder.create_error_embed("❌ 操作失敗", "循環模式切換出現錯誤")
            await self.safe_respond(interaction, embed=embed)

    @discord.ui.button(
        label="🔊",
        style=discord.ButtonStyle.secondary,
        custom_id="music_volume",
    )
    async def volume_control(self, interaction: discord.Interaction, button: discord.ui.Button):
        """音量控制按鈕 - 重寫版"""
        try:
            logger.info(f"音量按鈕被點擊 - 用戶: {interaction.user.name}")

            # 創建音量控制視圖
            volume_view = VolumeControlView(self.player)

            embed = EmbedBuilder.create_info_embed(
                "🔊 音量控制",
                f"當前音量：{int(self.player.volume * 100)}%\n使用下方按鈕調整音量",
            )

            await self.safe_respond(interaction, embed=embed, ephemeral=True, view=volume_view)

        except Exception as e:
            logger.error(f"音量控制按鈕錯誤: {e}")
            logger.error(traceback.format_exc())
            embed = EmbedBuilder.create_error_embed("❌ 操作失敗", "音量控制出現錯誤")
            await self.safe_respond(interaction, embed=embed)

    @discord.ui.button(label="🛑", style=discord.ButtonStyle.danger, custom_id="music_stop")
    async def stop_music(self, interaction: discord.Interaction, button: discord.ui.Button):
        """停止音樂按鈕 - 重寫版"""
        try:
            logger.info(f"停止按鈕被點擊 - 用戶: {interaction.user.name}")

            if not self.player.is_connected():
                embed = EmbedBuilder.create_error_embed(
                    "❌ 未連接語音頻道", "Bot 目前未連接到任何語音頻道"
                )
                await self.safe_respond(interaction, embed=embed)
                return

            # 停止播放並清空隊列
            await self.player.stop()

            embed = EmbedBuilder.create_success_embed(
                "🛑 已停止播放", "音樂播放已停止，播放列表已清空"
            )
            await self.safe_respond(interaction, embed=embed)
            logger.info("音樂播放已停止")
        except Exception as e:
            logger.error(f"停止按鈕錯誤: {e}")
            logger.error(traceback.format_exc())
            embed = EmbedBuilder.create_error_embed("❌ 操作失敗", "停止播放出現錯誤")
            await self.safe_respond(interaction, embed=embed)


class QueueRemoveSelect(discord.ui.Select):
    def __init__(self, player, guild: discord.Guild):
        self.player = player
        self.guild = guild

        options = []
        queue_items = player.queue
        for i, track in enumerate(queue_items[:25], 1):
            title = _truncate(track.title, 80)
            duration = _format_track_length(getattr(track, "length", 0))
            author = _truncate(getattr(track, "author", "Unknown"), 40)
            description = _truncate(f"{author} | {duration}", 100)
            options.append(
                discord.SelectOption(
                    label=f"{i}. {title}",
                    value=str(i),
                    description=description,
                )
            )

        if not options:
            options = [
                discord.SelectOption(
                    label="播放列表為空",
                    value="0",
                    description="沒有歌曲可以移除",
                )
            ]

        super().__init__(
            placeholder="選擇要移除的歌曲",
            min_values=1,
            max_values=1,
            options=options,
            disabled=len(queue_items) == 0,
            custom_id="music_queue_remove",
        )

    async def callback(self, interaction: discord.Interaction):
        if self.values[0] == "0":
            await interaction.response.send_message("播放列表為空。", ephemeral=True)
            return

        if not self.player.voice_client:
            await interaction.response.send_message("目前未連接語音頻道。", ephemeral=True)
            return

        index = int(self.values[0]) - 1
        queue = self.player.voice_client.queue
        if index < 0 or index >= len(queue):
            await interaction.response.send_message("指定的序號不存在。", ephemeral=True)
            return

        removed = queue[index]
        del queue[index]

        embed = EmbedBuilder.create_success_embed(
            "✅ 已移除歌曲",
            f"已移除：**{removed.title}**",
        )

        view = MusicQueueManageView(self.player, self.guild)
        panel_embed = _build_queue_manage_embed(self.player, self.guild)
        await interaction.response.edit_message(embed=panel_embed, view=view)
        await interaction.followup.send(embed=embed, ephemeral=True)


class MusicQueueManageView(discord.ui.View, SafeInteractionMixin):
    """播放列表管理面板（管理員）"""

    def __init__(self, player, guild: discord.Guild):
        super().__init__(timeout=300)
        self.player = player
        self.guild = guild
        self.add_item(QueueRemoveSelect(player, guild))

    @discord.ui.button(label="🔄 重新整理", style=discord.ButtonStyle.secondary)
    async def refresh_queue(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = _build_queue_manage_embed(self.player, self.guild)
        view = MusicQueueManageView(self.player, self.guild)
        await interaction.response.edit_message(embed=embed, view=view)

    @discord.ui.button(label="🗑️ 清空列表", style=discord.ButtonStyle.danger)
    async def clear_queue(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self.player.voice_client:
            await interaction.response.send_message("目前未連接語音頻道。", ephemeral=True)
            return

        queue = self.player.voice_client.queue
        count = len(queue)
        if count == 0:
            await interaction.response.send_message("播放列表已是空的。", ephemeral=True)
            return

        queue.clear()
        embed = EmbedBuilder.create_success_embed(
            "🗑️ 已清空播放列表",
            f"已移除 {count} 首歌曲。",
        )
        panel_embed = _build_queue_manage_embed(self.player, self.guild)
        view = MusicQueueManageView(self.player, self.guild)
        await interaction.response.edit_message(embed=panel_embed, view=view)
        await interaction.followup.send(embed=embed, ephemeral=True)


class VolumeControlView(discord.ui.View, SafeInteractionMixin):
    """音量控制視圖 - 重寫版"""

    def __init__(self, player):
        super().__init__(timeout=60)
        self.player = player

    @discord.ui.button(label="🔇 靜音", style=discord.ButtonStyle.secondary)
    async def mute(self, interaction: discord.Interaction, button: discord.ui.Button):
        """靜音按鈕"""
        await self.set_volume(interaction, 0.0)

    @discord.ui.button(label="🔉 25%", style=discord.ButtonStyle.secondary)
    async def vol_25(self, interaction: discord.Interaction, button: discord.ui.Button):
        """25% 音量"""
        await self.set_volume(interaction, 0.25)

    @discord.ui.button(label="🔊 50%", style=discord.ButtonStyle.primary)
    async def vol_50(self, interaction: discord.Interaction, button: discord.ui.Button):
        """50% 音量"""
        await self.set_volume(interaction, 0.5)

    @discord.ui.button(label="🔊 75%", style=discord.ButtonStyle.secondary)
    async def vol_75(self, interaction: discord.Interaction, button: discord.ui.Button):
        """75% 音量"""
        await self.set_volume(interaction, 0.75)

    @discord.ui.button(label="🔊 100%", style=discord.ButtonStyle.danger)
    async def vol_100(self, interaction: discord.Interaction, button: discord.ui.Button):
        """100% 音量"""
        await self.set_volume(interaction, 1.0)

    async def set_volume(self, interaction: discord.Interaction, volume: float):
        """設置音量的通用方法"""
        try:
            await self.player.set_volume(volume)

            embed = EmbedBuilder.create_success_embed(
                "🔊 音量已調整", f"當前音量：{int(volume * 100)}%"
            )

            await self.safe_respond(interaction, embed=embed)

        except Exception as e:
            logger.error(f"調整音量錯誤: {e}")
            embed = EmbedBuilder.create_error_embed("❌ 調整失敗", "調整音量時發生錯誤")
            await self.safe_respond(interaction, embed=embed)


class MusicMenuView(discord.ui.View, SafeInteractionMixin):
    """音樂系統主選單視圖 - 重寫版"""

    def __init__(self, music_cog):
        super().__init__(timeout=300)
        self.music_cog = music_cog

    def _check_voice_connection(self, player, guild) -> bool:
        """增強的語音連接狀態檢測"""
        try:
            # 檢查 player 的 voice_client
            player_connected = player.is_connected()

            # 檢查 guild 的 voice_client (更可靠)
            guild_voice_client = guild.voice_client
            if guild_voice_client and hasattr(guild_voice_client, "connected"):
                guild_connected = bool(guild_voice_client.connected)
            elif guild_voice_client and hasattr(guild_voice_client, "is_connected"):
                guild_connected = guild_voice_client.is_connected()
            else:
                guild_connected = False

            # 詳細日誌
            logger.info(
                f"🔍 語音狀態檢測: player_connected={player_connected}, guild_connected={guild_connected}"
            )
            logger.info(f"🔍 Player voice_client: {player.voice_client}")
            logger.info(f"🔍 Guild voice_client: {guild_voice_client}")

            if guild_voice_client:
                logger.info(f"🔍 Guild voice_client channel: {guild_voice_client.channel}")
                if hasattr(guild_voice_client, "connected"):
                    logger.info(
                        f"🔍 Guild voice_client connected: {guild_voice_client.connected}"
                    )
                elif hasattr(guild_voice_client, "is_connected"):
                    logger.info(
                        "🔍 Guild voice_client connected: %s",
                        guild_voice_client.is_connected(),
                    )

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
            result = player_connected and guild_connected
            logger.info(f"🔍 最終結果: {result}")
            return result

        except Exception as e:
            logger.error(f"語音連接檢測錯誤: {e}")
            import traceback

            logger.error(traceback.format_exc())
            return False

    @staticmethod
    def _can_manage_queue(member: discord.Member, is_owner: bool = False) -> bool:
        if is_owner:
            return True
        perms = member.guild_permissions
        return perms.administrator or perms.manage_guild

    @discord.ui.button(
        label="🎵 播放音樂",
        style=discord.ButtonStyle.primary,
        custom_id="menu_play",
    )
    async def play_music_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """播放音樂按鈕 - 重寫版"""
        try:
            logger.info(f"播放音樂按鈕被點擊 - 用戶: {interaction.user.name}")

            # 檢查用戶是否在語音頻道
            if not interaction.user.voice or not interaction.user.voice.channel:
                embed = EmbedBuilder.create_error_embed(
                    "❌ 請先加入語音頻道",
                    "您需要先加入一個語音頻道才能播放音樂",
                )
                await self.safe_respond(interaction, embed=embed)
                return

            # 顯示音樂輸入模態框
            modal = MusicInputModal(self.music_cog)
            await interaction.response.send_modal(modal)

        except Exception as e:
            logger.error(f"播放音樂按鈕錯誤: {e}")
            logger.error(traceback.format_exc())
            embed = EmbedBuilder.create_error_embed("❌ 系統錯誤", "播放功能暫時無法使用")
            await self.safe_respond(interaction, embed=embed)

    @discord.ui.button(
        label="🎛️ 控制面板",
        style=discord.ButtonStyle.secondary,
        custom_id="menu_control",
    )
    async def control_panel_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        """控制面板按鈕 - 重寫版"""
        try:
            logger.info(f"控制面板按鈕被點擊 - 用戶: {interaction.user.name}")

            # 檢查互動是否有效
            if not interaction or not hasattr(interaction, "response"):
                logger.error("無效的 interaction 對象")
                return

            # 檢查是否已響應
            if interaction.response.is_done():
                logger.warning("互動已被處理")
                return

            # 立即延遲回應
            try:
                await interaction.response.defer(ephemeral=True)
            except discord.errors.NotFound:
                logger.warning("互動已過期")
                return

            ctx = await self.music_cog._create_context_from_interaction(interaction)
            player = self.music_cog.get_player(ctx)

            # 檢查語音連接狀態 - 增強版檢測
            is_connected = self._check_voice_connection(player, interaction.guild)

            if is_connected:
                embed = EmbedBuilder.create_info_embed("🎛️ 音樂控制面板", "使用下方按鈕控制音樂播放")
            else:
                embed = EmbedBuilder.create_warning_embed(
                    "🎛️ 音樂控制面板",
                    "Bot 目前未連接語音頻道，請先使用播放功能",
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

        except Exception as e:
            logger.error(f"控制面板按鈕錯誤: {e}")
            logger.error(traceback.format_exc())
            try:
                embed = EmbedBuilder.create_error_embed("❌ 系統錯誤", "無法顯示控制面板")
                await interaction.followup.send(embed=embed, ephemeral=True)
            except:
                pass

    @discord.ui.button(
        label="🔍 搜索音樂",
        style=discord.ButtonStyle.secondary,
        custom_id="menu_search",
    )
    async def search_music_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        """搜索音樂按鈕 - 重寫版"""
        try:
            logger.info(f"搜索音樂按鈕被點擊 - 用戶: {interaction.user.name}")

            modal = SearchInputModal(self.music_cog)
            await interaction.response.send_modal(modal)

        except Exception as e:
            logger.error(f"搜索音樂按鈕錯誤: {e}")
            logger.error(traceback.format_exc())
            embed = EmbedBuilder.create_error_embed("❌ 系統錯誤", "無法打開搜索功能")
            await self.safe_respond(interaction, embed=embed)

    @discord.ui.button(
        label="🗂️ 列表管理",
        style=discord.ButtonStyle.secondary,
        custom_id="menu_queue_manage",
    )
    async def manage_queue_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        """播放列表管理（管理員）"""
        try:
            if not interaction.guild:
                await interaction.response.send_message("❌ 僅能在伺服器中使用。", ephemeral=True)
                return

            is_owner = await interaction.client.is_owner(interaction.user)
            if not self._can_manage_queue(interaction.user, is_owner=is_owner):
                await interaction.response.send_message(
                    "❌ 此功能僅限管理員使用。", ephemeral=True
                )
                return

            if not await self.music_cog.ensure_lavalink_ready(interaction.guild.id):
                await interaction.response.send_message(
                    "❌ 音樂服務尚未連線，請稍後再試或通知管理員檢查 Lavalink。",
                    ephemeral=True,
                )
                return

            ctx = await self.music_cog._create_context_from_interaction(interaction)
            player = self.music_cog.get_player(ctx)
            embed = _build_queue_manage_embed(player, interaction.guild)
            view = MusicQueueManageView(player, interaction.guild)
            await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

        except Exception as e:
            logger.error(f"播放列表管理按鈕錯誤: {e}")
            logger.error(traceback.format_exc())
            embed = EmbedBuilder.create_error_embed("❌ 系統錯誤", "無法打開播放列表管理面板")
            await self.safe_respond(interaction, embed=embed)


class MusicInputModal(discord.ui.Modal, title="🎵 播放音樂"):
    """音樂輸入模態框 - 重寫版"""

    def __init__(self, music_cog):
        super().__init__()
        self.music_cog = music_cog

    music_input = discord.ui.TextInput(
        label="歌曲名稱或 YouTube 網址",
        placeholder="輸入歌曲名稱或貼上 YouTube 網址...",
        max_length=500,
        required=True,
    )

    async def on_submit(self, interaction: discord.Interaction):
        """提交處理 - 重寫版"""
        try:
            logger.info(
                f"音樂輸入模態框提交 - 用戶: {interaction.user.name}, 輸入: {self.music_input.value}"
            )

            # 檢查是否已響應
            if interaction.response.is_done():
                logger.warning("模態框互動已被處理")
                return

            await interaction.response.defer()

            # 檢查用戶是否在語音頻道
            if not interaction.user.voice or not interaction.user.voice.channel:
                embed = EmbedBuilder.create_error_embed(
                    "❌ 請先加入語音頻道",
                    "您需要先加入一個語音頻道才能播放音樂",
                )
                await interaction.followup.send(embed=embed, ephemeral=True)
                return

            if not await self.music_cog.ensure_lavalink_ready(interaction.guild.id):
                embed = EmbedBuilder.create_error_embed(
                    "❌ 音樂服務未就緒",
                    "Lavalink 尚未連線，請稍後再試或通知管理員檢查設定。",
                )
                await interaction.followup.send(embed=embed, ephemeral=True)
                return

            # 創建臨時context用於播放器
            ctx = await self.music_cog._create_context_from_interaction(interaction)
            player = self.music_cog.get_player(ctx)

            # 連接到語音頻道
            await player.connect_to_voice(interaction.user.voice.channel)

            # 添加歌曲
            source = await player.add_song(self.music_input.value, interaction.user)

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

            uploader = getattr(source, "author", "Unknown")
            duration = _format_track_length(getattr(source, "length", 0))
            embed = EmbedBuilder.create_success_embed(
                "✅ 已添加到播放列表",
                f"**{source.title}**\n👤 {uploader}\n⏱️ {duration}",
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
            logger.info(f"成功添加歌曲: {source.title}")

        except Exception as e:
            logger.error(f"音樂輸入模態框錯誤: {e}")
            logger.error(traceback.format_exc())
            embed = EmbedBuilder.create_error_embed("❌ 播放失敗", "播放音樂時發生錯誤")
            try:
                if not interaction.response.is_done():
                    await interaction.response.send_message(embed=embed, ephemeral=True)
                else:
                    await interaction.followup.send(embed=embed, ephemeral=True)
            except:
                pass


class SearchInputModal(discord.ui.Modal, title="🔍 搜索音樂"):
    """搜索輸入模態框 - 重寫版"""

    def __init__(self, music_cog):
        super().__init__()
        self.music_cog = music_cog
        self.last_error: str | None = None

    search_input = discord.ui.TextInput(
        label="搜索關鍵字",
        placeholder="輸入要搜索的歌曲名稱或歌手...",
        max_length=200,
        required=True,
    )

    async def on_submit(self, interaction: discord.Interaction):
        """提交處理 - 重寫版"""
        try:
            logger.info(
                f"搜索模態框提交 - 用戶: {interaction.user.name}, 搜索: {self.search_input.value}"
            )

            # 檢查互動是否已被處理
            if interaction.response.is_done():
                logger.warning("搜索互動已被處理")
                return

            # 立即延遲回應，避免超時
            await interaction.response.defer(ephemeral=True)

            if not await self.music_cog.ensure_lavalink_ready(interaction.guild.id):
                embed = EmbedBuilder.create_error_embed(
                    "❌ 音樂服務未就緒",
                    "Lavalink 尚未連線，請稍後再試或通知管理員檢查設定。",
                )
                await interaction.followup.send(embed=embed, ephemeral=True)
                return

            # 先顯示搜索中的狀態
            embed = EmbedBuilder.create_info_embed(
                "🔍 正在搜索",
                f"正在搜索 '{self.search_input.value}'，請稍候...",
            )
            search_msg = await interaction.followup.send(embed=embed, ephemeral=True)

            try:
                # 執行搜索
                search_results = await self._search_music(self.search_input.value, 5)

                if not search_results:
                    embed = EmbedBuilder.create_warning_embed(
                        "🔍 無搜索結果",
                        f"沒有找到與 '{self.search_input.value}' 相關的音樂",
                    )
                    await search_msg.edit(embed=embed)
                    return

                # 創建搜索結果列表
                result_text = ""
                for i, result in enumerate(search_results[:5], 1):
                    uploader = getattr(result, "author", "Unknown")
                    duration = _format_track_length(getattr(result, "length", 0))
                    result_text += (
                        f"{i}. **{result.title[:50]}{'...' if len(result.title) > 50 else ''}**\n"
                    )
                    result_text += f"   👤 {uploader} | ⏱️ {duration}\n\n"

                embed = EmbedBuilder.create_info_embed(
                    "🔍 搜索結果",
                    f"找到 {len(search_results)} 個結果：\n\n{result_text}",
                )

                embed.add_field(
                    name="使用方式",
                    value="請回到音樂面板點擊「播放音樂」，輸入歌曲名稱或網址播放",
                    inline=False,
                )

                await search_msg.edit(embed=embed)
                logger.info(f"搜索完成，找到 {len(search_results)} 首歌曲")

            except Exception as e:
                logger.error(f"搜索執行錯誤: {e}")
                embed = EmbedBuilder.create_error_embed("❌ 搜索失敗", f"搜索時發生錯誤: {str(e)}")
                await search_msg.edit(embed=embed)

        except Exception as e:
            logger.error(f"搜索輸入模態框錯誤: {e}")
            logger.error(traceback.format_exc())
            try:
                embed = EmbedBuilder.create_error_embed("❌ 搜索失敗", "搜索音樂時發生錯誤")
                if not interaction.response.is_done():
                    await interaction.response.send_message(embed=embed, ephemeral=True)
                else:
                    await interaction.followup.send(embed=embed, ephemeral=True)
            except:
                pass

    async def _search_music(self, query: str, count: int = 5):
        """搜索音樂 - 簡化版本"""
        try:
            logger.info(f"開始搜索音樂: {query}")
            self.last_error = None
            search_query = f"ytsearch{count}:{query}"
            tracks = await wavelink.Pool.fetch_tracks(search_query)

            if not tracks:
                logger.warning(f"無搜索結果: {query}")
                return []

            if isinstance(tracks, wavelink.Playlist):
                results = tracks.tracks
            elif isinstance(tracks, list):
                results = tracks
            else:
                results = [tracks]

            logger.info(f"搜索完成，返回 {len(results)} 首歌曲")
            return results[:count]

        except Exception as e:
            self.last_error = str(e)
            logger.error(f"音樂搜索系統錯誤: {e}")
            logger.error(traceback.format_exc())
            return []
