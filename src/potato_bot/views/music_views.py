# bot/views/music_views.py - 音樂系統視圖組件（重寫版）
"""
音樂系統 Discord GUI 視圖組件 v2.3.1
完全重寫的互動處理機制，解決超時和響應問題
"""

import traceback

import discord

from potato_bot.utils.embed_builder import EmbedBuilder
from potato_shared.logger import logger


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

            if not self.player.voice_client or not self.player.voice_client.is_connected():
                embed = EmbedBuilder.create_error_embed(
                    "❌ 未連接語音頻道", "Bot 目前未連接到任何語音頻道"
                )
                await self.safe_respond(interaction, embed=embed)
                return

            # 處理播放/暫停
            if self.player.voice_client.is_playing():
                self.player.voice_client.pause()
                self.player.is_paused = True
                embed = EmbedBuilder.create_success_embed("⏸️ 已暫停", "音樂播放已暫停")
                logger.info("音樂已暫停")
            elif self.player.voice_client.is_paused():
                self.player.voice_client.resume()
                self.player.is_paused = False
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

            if not self.player.voice_client or not self.player.voice_client.is_connected():
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
            if self.player.voice_client.is_playing() or self.player.voice_client.is_paused():
                self.player.voice_client.stop()

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
                self.player.loop_mode = LoopMode.SINGLE
                mode_text = "🔂 單曲循環"
            elif self.player.loop_mode == LoopMode.SINGLE:
                self.player.loop_mode = LoopMode.QUEUE
                mode_text = "🔁 列表循環"
            else:
                self.player.loop_mode = LoopMode.NONE
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

            if not self.player.voice_client or not self.player.voice_client.is_connected():
                embed = EmbedBuilder.create_error_embed(
                    "❌ 未連接語音頻道", "Bot 目前未連接到任何語音頻道"
                )
                await self.safe_respond(interaction, embed=embed)
                return

            # 停止播放並清空隊列
            if self.player.voice_client.is_playing() or self.player.voice_client.is_paused():
                self.player.voice_client.stop()

            self.player.queue.clear()
            self.player.current = None
            self.player.is_playing = False
            self.player.is_paused = False

            embed = EmbedBuilder.create_success_embed(
                "🛑 已停止播放", "音樂播放已停止，播放列表已清空"
            )
            await self.safe_respond(interaction, embed=embed)
            logger.info("音樂播放已停止")

        except Exception as e:
            logger.error(f"停止按鈕錯誤: {e}")
            logger.error(traceback.format_exc())
            embed = EmbedBuilder.create_error_embed("❌ 操作失敗", "停止操作出現錯誤")
            await self.safe_respond(interaction, embed=embed)


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
    """音樂系統主菜單視圖 - 重寫版"""

    def __init__(self, music_cog):
        super().__init__(timeout=300)
        self.music_cog = music_cog

    def _check_voice_connection(self, player, guild) -> bool:
        """增強的語音連接狀態檢測"""
        try:
            # 檢查 player 的 voice_client
            player_connected = player.voice_client and player.voice_client.is_connected()

            # 檢查 guild 的 voice_client (更可靠)
            guild_voice_client = guild.voice_client
            guild_connected = guild_voice_client and guild_voice_client.is_connected()

            # 詳細日誌
            logger.info(
                f"🔍 語音狀態檢測: player_connected={player_connected}, guild_connected={guild_connected}"
            )
            logger.info(f"🔍 Player voice_client: {player.voice_client}")
            logger.info(f"🔍 Guild voice_client: {guild_voice_client}")

            if guild_voice_client:
                logger.info(f"🔍 Guild voice_client channel: {guild_voice_client.channel}")
                logger.info(
                    f"🔍 Guild voice_client is_connected: {guild_voice_client.is_connected()}"
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

            embed = EmbedBuilder.create_success_embed(
                "✅ 已添加到播放列表",
                f"**{source.title}**\n👤 {source.uploader}\n⏱️ {source.duration_str}",
            )

            if player.queue or player.current != source:
                embed.add_field(
                    name="排隊位置",
                    value=f"第 {len(player.queue)} 位",
                    inline=True,
                )

            if source.thumbnail:
                embed.set_thumbnail(url=source.thumbnail)

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
                    result_text += (
                        f"{i}. **{result.title[:50]}{'...' if len(result.title) > 50 else ''}**\n"
                    )
                    result_text += f"   👤 {result.uploader} | ⏱️ {result.duration_str}\n\n"

                embed = EmbedBuilder.create_info_embed(
                    "🔍 搜索結果",
                    f"找到 {len(search_results)} 個結果：\n\n{result_text}",
                )

                embed.add_field(
                    name="使用方式",
                    value="請使用 `/play` 指令 + 歌曲名稱來播放上述歌曲",
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
            import asyncio
            import concurrent.futures

            import yt_dlp

            logger.info(f"開始搜索音樂: {query}")

            # 簡化的 yt-dlp 配置
            ytdl_options = {
                "format": "bestaudio/best",
                "quiet": True,
                "no_warnings": True,
                "extractaudio": False,
                "noplaylist": True,
                "default_search": f"ytsearch{count}:",
                "socket_timeout": 10,
            }

            def search_videos(search_query):
                """在執行器中運行的搜索函數"""
                try:
                    ytdl = yt_dlp.YoutubeDL(ytdl_options)
                    search_url = f"ytsearch{count}:{search_query}"
                    logger.info(f"正在執行 yt-dlp 搜索: {search_url}")

                    result = ytdl.extract_info(search_url, download=False)
                    logger.info(f"搜索完成，結果數量: {len(result.get('entries', []))}")
                    return result
                except Exception as e:
                    logger.error(f"yt-dlp 搜索錯誤: {e}")
                    return None

            # 使用線程池執行搜索，設置超時
            loop = asyncio.get_event_loop()
            try:
                with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                    results = await asyncio.wait_for(
                        loop.run_in_executor(executor, search_videos, query),
                        timeout=10.0,  # 10秒超時
                    )
            except asyncio.TimeoutError:
                logger.error(f"搜索超時: {query}")
                return []
            except Exception as e:
                logger.error(f"搜索執行錯誤: {e}")
                return []

            if not results or "entries" not in results:
                logger.warning(f"無搜索結果: {query}")
                return []

            # 轉換為 MusicSource 物件
            from potato_bot.cogs.music_core import MusicSource

            # 創建假用戶作為請求者
            class FakeUser:
                def __init__(self):
                    self.mention = "搜索結果"
                    self.display_name = "搜索"

            fake_user = FakeUser()

            sources = []
            for entry in results["entries"]:
                if entry:  # 確保 entry 不為 None
                    try:
                        source = MusicSource(entry, fake_user)
                        sources.append(source)
                        logger.info(f"已轉換歌曲: {source.title}")
                    except Exception as e:
                        logger.warning(f"轉換歌曲失敗: {e}")
                        continue

            logger.info(f"搜索完成，返回 {len(sources)} 首歌曲")
            return sources

        except Exception as e:
            logger.error(f"音樂搜索系統錯誤: {e}")
            logger.error(traceback.format_exc())
            return []
