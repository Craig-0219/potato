# vote.py - v5.2 (效能優化版 + 歷史查詢功能)
# ✅ 功能更新紀錄：
# - 修正投票 UI 無法互動（交互失敗）問題
# - 修正投票模式顯示錯誤（公開/匿名、單選/多選）
# - 導入 handle_vote_submit() 並接收按鈕事件處理
# - 統一使用 vote_utils 格式化顯示，進度條統一模組
# - 投票後自動更新統計資料，保留原有選項
# - 新增歷史查詢功能：/vote_history, /vote_detail, /my_votes, /vote_search
# - 效能優化：資料庫查詢批次化、快取機制、併發安全性

import asyncio
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import discord
from discord import app_commands
from discord.ext import commands, tasks

from bot.db import vote_dao
from bot.utils.vote_utils import build_result_embed, build_vote_embed
from bot.views.vote_views import (
    VoteButtonView,
    VoteManagementView,
)
from shared.logger import logger


class VoteCore(commands.Cog):
    vote_sessions: Dict[int, Dict[str, Any]] = {}  # 類型提示
    _vote_cache: Dict[int, Dict[str, Any]] = {}  # 投票資料快取
    _cache_timeout = 300  # 快取 5 分鐘

    def __init__(self, bot):
        self.bot = bot
        self._session_lock = asyncio.Lock()  # 防止併發問題

    async def cog_load(self):
        """Cog 載入時執行的異步初始化"""
        try:
            self.announce_expired_votes.start()
            logger.info("VoteCore 背景任務已啟動")
        except Exception as e:
            logger.warning(f"VoteCore 背景任務啟動失敗: {e}")

    def cog_unload(self):
        if hasattr(self, "announce_expired_votes"):
            self.announce_expired_votes.cancel()
        # 清理資源
        VoteCore.vote_sessions.clear()
        VoteCore._vote_cache.clear()

    # ✅ 快取機制：減少重複資料庫查詢
    async def _get_vote_with_cache(self, vote_id: int) -> Optional[Dict[str, Any]]:
        """取得投票資料（含快取機制）"""
        cache_key = f"vote_{vote_id}"
        now = datetime.now(timezone.utc)

        # 檢查快取
        if cache_key in self._vote_cache:
            cached_data = self._vote_cache[cache_key]
            if (now - cached_data["cached_at"]).total_seconds() < self._cache_timeout:
                return cached_data["data"]

        # 快取過期或不存在，從資料庫取得
        vote = await vote_dao.get_vote_by_id(vote_id)
        if vote:
            self._vote_cache[cache_key] = {"data": vote, "cached_at": now}
        return vote

    # ✅ 批次取得投票相關資料
    async def _get_vote_full_data(self, vote_id: int) -> Optional[Dict[str, Any]]:
        """批次取得投票完整資料（投票、選項、統計）"""
        try:
            # 並行執行多個資料庫查詢
            vote_task = self._get_vote_with_cache(vote_id)
            options_task = vote_dao.get_vote_options(vote_id)
            stats_task = vote_dao.get_vote_statistics(vote_id)

            vote, options, stats = await asyncio.gather(
                vote_task, options_task, stats_task, return_exceptions=True
            )

            # 檢查是否有例外
            if (
                isinstance(vote, Exception)
                or isinstance(options, Exception)
                or isinstance(stats, Exception)
            ):

                return None

            if not vote:
                return None

            return {
                "vote": vote,
                "options": options,
                "stats": stats,
                "total": sum(stats.values()),
            }
        except Exception:

            return None

    @app_commands.command(name="vote", description="開始建立一個投票 | Create a new vote")
    async def vote(self, interaction: discord.Interaction):
        """現代化 GUI 投票創建指令"""
        try:
            # ✅ 檢查投票系統是否啟用
            if not await vote_dao.is_vote_system_enabled(interaction.guild.id):
                await interaction.response.send_message("❌ 投票系統已被停用。", ephemeral=True)
                return

            # ✅ 檢查是否在指定投票頻道中
            vote_settings = await vote_dao.get_vote_settings(interaction.guild.id)
            if vote_settings and vote_settings.get("default_vote_channel_id"):
                allowed_channel_id = vote_settings["default_vote_channel_id"]
                if interaction.channel.id != allowed_channel_id:
                    allowed_channel = interaction.guild.get_channel(allowed_channel_id)
                    channel_mention = (
                        allowed_channel.mention if allowed_channel else f"<#{allowed_channel_id}>"
                    )
                    await interaction.response.send_message(
                        f"❌ 投票只能在指定的投票頻道 {channel_mention} 中建立。",
                        ephemeral=True,
                    )
                    return

            # ✅ 直接顯示 GUI 模態框
            from bot.views.vote_views import ComprehensiveVoteModal

            modal = ComprehensiveVoteModal()
            await interaction.response.send_modal(modal)
        except Exception as e:
            logger.error(f"投票創建失敗: {e}")
            if not interaction.response.is_done():
                await interaction.response.send_message(
                    "❌ 啟動投票創建時發生錯誤。", ephemeral=True
                )

    @app_commands.command(
        name="votes",
        description="查看目前進行中的投票 | View current active votes",
    )
    async def votes(self, interaction: discord.Interaction):
        try:
            votes = await vote_dao.get_active_votes()
            if not votes:
                await interaction.response.send_message("目前沒有進行中的投票。", ephemeral=True)
                return

            embed = discord.Embed(title="📋 進行中的投票", color=0x00BFFF)

            # ✅ 批量處理時間格式化
            now = datetime.now(timezone.utc)
            for v in votes:
                time_left = self._calculate_time_left(v["end_time"], now)
                embed.add_field(
                    name=f"#{v['id']} - {v['title'][:50]}{'...' if len(v['title']) > 50 else ''}",
                    value=f"⏳ 剩餘：{time_left}",
                    inline=False,
                )

            await interaction.response.send_message(embed=embed)
        except Exception:

            await interaction.response.send_message("❌ 查詢投票時發生錯誤。", ephemeral=True)

    @app_commands.command(name="vote_result", description="查詢投票結果 | Query vote results")
    @app_commands.describe(vote_id="投票編號")
    async def vote_result(self, interaction: discord.Interaction, vote_id: int):
        try:
            data = await self._get_vote_full_data(vote_id)
            if not data:
                await interaction.response.send_message("❌ 找不到該投票。", ephemeral=True)
                return

            embed = build_result_embed(
                data["vote"]["title"],
                data["stats"],
                data["total"],
                vote_id=vote_id,
            )
            await interaction.response.send_message(embed=embed)
        except Exception:

            await interaction.response.send_message("❌ 查詢結果時發生錯誤。", ephemeral=True)

    @app_commands.command(name="vote_open", description="補發互動式投票 UI (限管理員)")
    @app_commands.describe(vote_id="要補發的投票 ID")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def vote_open(self, interaction: discord.Interaction, vote_id: int):
        try:
            data = await self._get_vote_full_data(vote_id)
            if not data:
                await interaction.response.send_message("❌ 找不到該投票。", ephemeral=True)
                return

            vote = data["vote"]
            options = data["options"]
            stats = data["stats"]
            total = data["total"]

            embed = build_vote_embed(
                vote["title"],
                vote["start_time"],
                vote["end_time"],
                vote["is_multi"],
                vote["anonymous"],
                total,
                vote_id=vote_id,
            )
            view = VoteButtonView(
                vote_id,
                options,
                vote["allowed_roles"],
                vote["is_multi"],
                vote["anonymous"],
                stats,
                total,
            )
            await interaction.response.send_message(embed=embed, view=view)
        except Exception:

            await interaction.response.send_message("❌ 補發 UI 時發生錯誤。", ephemeral=True)

    # ===== 新增：歷史查詢功能 =====

    @app_commands.command(name="vote_history", description="查看投票歷史記錄 | View vote history")
    @app_commands.describe(
        page="頁數（每頁10筆，預設第1頁）",
        status="篩選狀態：all(全部) / active(進行中) / finished(已結束)",
    )
    async def vote_history(
        self,
        interaction: discord.Interaction,
        page: int = 1,
        status: str = "all",
    ):
        try:
            await interaction.response.defer()

            # 參數驗證
            page = max(1, page)  # 確保頁數至少為1
            if status not in ["all", "active", "finished"]:
                status = "all"

            # 查詢歷史記錄
            votes = await vote_dao.get_vote_history(page, status)
            total_count = await vote_dao.get_vote_count(status)

            if not votes:
                await interaction.followup.send("📭 沒有找到符合條件的投票記錄。")
                return

            # 建立分頁顯示
            per_page = 10
            total_pages = (total_count + per_page - 1) // per_page

            embed = discord.Embed(
                title=f"📚 投票歷史記錄 ({self._get_status_name(status)})",
                color=0x9B59B6,
            )
            embed.set_footer(text=f"第 {page}/{total_pages} 頁 • 共 {total_count} 筆記錄")

            now = datetime.now(timezone.utc)
            for vote in votes:
                # 計算狀態
                is_active = vote["end_time"] > now
                status_emoji = "🟢" if is_active else "🔴"
                status_text = "進行中" if is_active else "已結束"

                # 計算持續時間或剩餘時間
                if is_active:
                    time_info = self._calculate_time_left(vote["end_time"], now)
                    time_label = "剩餘"
                else:
                    duration = vote["end_time"] - vote["start_time"]
                    time_info = self._format_duration(duration)
                    time_label = "持續了"

                # 取得投票統計
                stats = await vote_dao.get_vote_statistics(vote["id"])
                total_votes = sum(stats.values())

                field_value = (
                    f"{status_emoji} **{status_text}**\n"
                    f"🗳 總票數：{total_votes}\n"
                    f"⏱ {time_label}：{time_info}\n"
                    f"📅 開始：{vote['start_time'].strftime('%m/%d %H:%M')}"
                )

                embed.add_field(
                    name=f"#{vote['id']} - {vote['title'][:40]}{'...' if len(vote['title']) > 40 else ''}",
                    value=field_value,
                    inline=True,
                )

            # 添加分頁按鈕
            view = HistoryPaginationView(page, total_pages, status)
            await interaction.followup.send(embed=embed, view=view)

        except Exception:

            await interaction.followup.send("❌ 查詢歷史記錄時發生錯誤。")

    @app_commands.command(name="vote_detail", description="查看特定投票的詳細資訊")
    @app_commands.describe(vote_id="投票編號")
    async def vote_detail(self, interaction: discord.Interaction, vote_id: int):
        try:
            await interaction.response.defer()

            # 取得完整投票資料
            data = await self._get_vote_full_data(vote_id)
            if not data:
                await interaction.followup.send("❌ 找不到該投票。")
                return

            vote = data["vote"]
            options = data["options"]
            stats = data["stats"]
            total = data["total"]

            # 建立詳細資訊 Embed
            now = datetime.now(timezone.utc)
            is_active = vote["end_time"] > now

            embed = discord.Embed(
                title=f"🗳 #{vote_id} - {vote['title']}",
                color=0x3498DB if is_active else 0xE74C3C,
            )

            # 基本資訊
            status = "🟢 進行中" if is_active else "🔴 已結束"
            mode = f"{'匿名' if vote['anonymous'] else '公開'}、{'多選' if vote['is_multi'] else '單選'}"

            embed.add_field(
                name="📊 基本資訊",
                value=(f"**狀態：** {status}\n" f"**模式：** {mode}\n" f"**總票數：** {total} 票"),
                inline=False,
            )

            # 時間資訊
            start_time = vote["start_time"].strftime("%Y-%m-%d %H:%M UTC")
            end_time = vote["end_time"].strftime("%Y-%m-%d %H:%M UTC")

            if is_active:
                time_left = self._calculate_time_left(vote["end_time"], now)
                time_field = (
                    f"**開始：** {start_time}\n**結束：** {end_time}\n**剩餘：** {time_left}"
                )
            else:
                duration = self._format_duration(vote["end_time"] - vote["start_time"])
                time_field = (
                    f"**開始：** {start_time}\n**結束：** {end_time}\n**持續：** {duration}"
                )

            embed.add_field(name="⏰ 時間資訊", value=time_field, inline=False)

            # 投票結果（含進度條）
            if total > 0:
                result_text = ""
                for opt in options:
                    count = stats.get(opt, 0)
                    percent = (count / total * 100) if total > 0 else 0
                    bar = "█" * int(percent / 10) + "░" * (10 - int(percent / 10))
                    result_text += f"**{opt}**\n{count} 票 ({percent:.1f}%) {bar}\n\n"

                embed.add_field(name="📈 投票結果", value=result_text, inline=False)
            else:
                embed.add_field(name="📈 投票結果", value="尚無投票", inline=False)

            # 權限資訊
            if vote["allowed_roles"]:
                try:
                    guild = interaction.guild
                    role_names = []
                    for role_id in vote["allowed_roles"]:
                        role = guild.get_role(role_id)
                        if role:
                            role_names.append(role.name)

                    if role_names:
                        embed.add_field(
                            name="👥 允許投票的身分組",
                            value=", ".join(role_names),
                            inline=False,
                        )
                except:
                    pass

            await interaction.followup.send(embed=embed)

        except Exception:

            await interaction.followup.send("❌ 查詢投票詳情時發生錯誤。")

    @app_commands.command(
        name="my_votes",
        description="查看我參與過的投票 | View my participated votes",
    )
    async def my_votes(self, interaction: discord.Interaction):
        try:
            await interaction.response.defer()

            user_votes = await vote_dao.get_user_vote_history(interaction.user.id)
            if not user_votes:
                await interaction.followup.send("📭 你還沒有參與過任何投票。")
                return

            embed = discord.Embed(
                title=f"🙋‍♂️ {interaction.user.display_name} 的投票記錄",
                color=0x2ECC71,
            )

            for vote_info in user_votes[:10]:  # 限制顯示最近10筆
                vote_id = vote_info["vote_id"]
                title = vote_info["vote_title"]
                my_choices = vote_info["my_choices"]
                vote_date = (
                    vote_info["vote_time"].strftime("%m/%d %H:%M")
                    if vote_info["vote_time"]
                    else "未知"
                )

                embed.add_field(
                    name=f"#{vote_id} - {title[:30]}{'...' if len(title) > 30 else ''}",
                    value=f"✅ 我的選擇：{', '.join(my_choices)}\n📅 投票時間：{vote_date}",
                    inline=False,
                )

            if len(user_votes) > 10:
                embed.set_footer(text=f"顯示最近 10 筆，共參與 {len(user_votes)} 次投票")

            await interaction.followup.send(embed=embed)

        except Exception:

            await interaction.followup.send("❌ 查詢個人投票記錄時發生錯誤。")

    @app_commands.command(name="vote_search", description="搜尋投票")
    @app_commands.describe(keyword="搜尋關鍵字（投票標題）")
    async def vote_search(self, interaction: discord.Interaction, keyword: str):
        try:
            await interaction.response.defer()

            if len(keyword.strip()) < 2:
                await interaction.followup.send("❌ 搜尋關鍵字至少需要2個字元。")
                return

            results = await vote_dao.search_votes(keyword.strip())
            if not results:
                await interaction.followup.send(f"🔍 沒有找到包含「{keyword}」的投票。")
                return

            embed = discord.Embed(title=f"🔍 搜尋結果：「{keyword}」", color=0xF39C12)
            embed.set_footer(text=f"找到 {len(results)} 筆符合的投票")

            datetime.now(timezone.utc)
            for vote in results:
                is_active = vote["is_active"] == 1
                status_emoji = "🟢" if is_active else "🔴"
                status_text = "進行中" if is_active else "已結束"

                # 取得投票統計
                stats = await vote_dao.get_vote_statistics(vote["id"])
                total_votes = sum(stats.values())

                field_value = (
                    f"{status_emoji} {status_text} • {total_votes} 票\n"
                    f"📅 {vote['start_time'].strftime('%Y/%m/%d %H:%M')}"
                )

                embed.add_field(
                    name=f"#{vote['id']} - {vote['title']}",
                    value=field_value,
                    inline=False,
                )

            await interaction.followup.send(embed=embed)

        except Exception:

            await interaction.followup.send("❌ 搜尋時發生錯誤。")

    # ===== 診斷功能 =====

    # @app_commands.command(name="vote_debug", description="診斷投票系統問題（管理員用）")  # 已移除以節省指令空間
    @app_commands.checks.has_permissions(manage_guild=True)
    async def vote_debug(self, interaction: discord.Interaction):
        await interaction.response.defer()

        try:
            debug_info = []

            # 1. 測試資料庫連線
            debug_info.append("🔍 **資料庫連線測試**")
            try:
                from bot.db.pool import db_pool

                async with db_pool.connection() as conn:
                    async with conn.cursor() as cur:
                        await cur.execute("SELECT VERSION()")
                        version = await cur.fetchone()
                        debug_info.append(f"✅ 資料庫連線成功：{version[0]}")
            except Exception as e:
                debug_info.append(f"❌ 資料庫連線失敗：{e}")
                await interaction.followup.send("\n".join(debug_info))
                return

            # 2. 檢查資料表
            debug_info.append("\n🔍 **資料表檢查**")
            try:
                async with db_pool.connection() as conn:
                    async with conn.cursor() as cur:
                        # 檢查 votes 表
                        await cur.execute("SELECT COUNT(*) FROM votes")
                        total_votes = await cur.fetchone()
                        debug_info.append(f"📊 votes 表總記錄數：{total_votes[0]}")

                        # 檢查最近的投票
                        await cur.execute(
                            "SELECT id, title, end_time, NOW() as current_time FROM votes ORDER BY id DESC LIMIT 3"
                        )
                        recent_votes = await cur.fetchall()
                        for vote in recent_votes:
                            vote_id, title, end_time, current_time = vote
                            debug_info.append(f"🗳 #{vote_id}: {title}")
                            debug_info.append(f"   結束時間: {end_time}")
                            debug_info.append(f"   現在時間: {current_time}")
                            debug_info.append(f"   是否過期: {end_time <= current_time}")

                        # 檢查進行中的投票（原始 SQL）
                        await cur.execute("SELECT COUNT(*) FROM votes WHERE end_time > NOW()")
                        active_count = await cur.fetchone()
                        debug_info.append(f"🟢 進行中投票數（SQL）：{active_count[0]}")

            except Exception as e:
                debug_info.append(f"❌ 資料表檢查失敗：{e}")

            # 3. 測試 DAO 函數
            debug_info.append("\n🔍 **DAO 函數測試**")
            try:
                votes = await vote_dao.get_active_votes()
                debug_info.append(
                    f"📋 get_active_votes() 返回：{len(votes) if votes else 0} 個投票"
                )
                if votes:
                    for v in votes[:3]:  # 只顯示前3個
                        debug_info.append(f"   #{v['id']}: {v['title']} (結束: {v['end_time']})")
            except Exception as e:
                debug_info.append(f"❌ get_active_votes() 錯誤：{e}")

            # 4. 檢查當前 sessions
            debug_info.append("\n🔍 **Session 狀態**")
            debug_info.append(f"📝 當前活躍 session 數：{len(VoteCore.vote_sessions)}")
            for user_id, session in list(VoteCore.vote_sessions.items())[:3]:
                debug_info.append(f"   用戶 {user_id}: {session.get('title', '無標題')}")

            # 5. 檢查時區設定
            debug_info.append("\n🔍 **時區檢查**")
            now_utc = datetime.now(timezone.utc)
            debug_info.append(f"🕐 Python UTC 時間：{now_utc}")

            # 分批發送（Discord 有字數限制）
            message = "\n".join(debug_info)
            if len(message) > 2000:
                chunks = [message[i : i + 1900] for i in range(0, len(message), 1900)]
                for i, chunk in enumerate(chunks):
                    if i == 0:
                        await interaction.followup.send(f"```\n{chunk}\n```")
                    else:
                        await interaction.followup.send(f"```\n{chunk}\n```")
            else:
                await interaction.followup.send(f"```\n{message}\n```")

        except Exception as e:
            await interaction.followup.send(f"❌ 診斷過程發生錯誤：{e}")

    # ===== 核心功能方法 =====

    async def finalize_vote(self, user_id: int, guild: discord.Guild):
        """✅ 修復版本：正確的參數傳遞"""
        async with self._session_lock:
            session = VoteCore.vote_sessions.get(user_id)
            if not session:
                return

    async def handle_vote_submit(
        self,
        interaction: discord.Interaction,
        vote_id: int,
        selected_options: List[str],
    ):
        """✅ 優化版本：更好的錯誤處理和效能"""
        try:
            # ✅ 批次取得資料
            data = await self._get_vote_full_data(vote_id)
            if not data:
                await interaction.response.send_message("❌ 找不到此投票。", ephemeral=True)
                return

            vote = data["vote"]

            # ✅ 權限檢查優化
            if vote["allowed_roles"] and not self._check_user_permission(
                interaction.user, vote["allowed_roles"]
            ):
                await interaction.response.send_message("❌ 你沒有權限參與此投票。", ephemeral=True)
                return

            # ✅ 重複投票檢查
            if await vote_dao.has_voted(vote_id, interaction.user.id):
                await interaction.response.send_message(
                    "❗ 你已參與過此投票，不能重複投票。", ephemeral=True
                )
                return

            # ✅ 批次插入投票結果
            await asyncio.gather(
                *[
                    vote_dao.insert_vote_response(vote_id, interaction.user.id, opt)
                    for opt in selected_options
                ]
            )

            await interaction.response.send_message(
                f"🎉 投票成功！你選擇了：{', '.join(selected_options)}",
                ephemeral=True,
            )

            # ✅ 清除快取，強制重新載入
            cache_key = f"vote_{vote_id}"
            if cache_key in self._vote_cache:
                del self._vote_cache[cache_key]

            # ✅ 更新 UI（非阻塞）
            asyncio.create_task(self._update_vote_ui(interaction, vote_id))

        except Exception:

            if not interaction.response.is_done():
                await interaction.response.send_message(
                    "❌ 投票時發生錯誤，請稍後再試。", ephemeral=True
                )

    async def _update_vote_ui(self, interaction: discord.Interaction, vote_id: int):
        """✅ 非同步更新投票 UI"""
        try:
            data = await self._get_vote_full_data(vote_id)
            if not data:
                return

            vote = data["vote"]
            embed = build_vote_embed(
                vote["title"],
                vote["start_time"],
                vote["end_time"],
                vote["is_multi"],
                vote["anonymous"],
                data["total"],
                vote_id=vote_id,
            )

            view = VoteButtonView(
                vote_id,
                data["options"],
                vote["allowed_roles"],
                vote["is_multi"],
                vote["anonymous"],
                data["stats"],
                data["total"],
            )

            await interaction.message.edit(embed=embed, view=view)
        except Exception as e:
            logger.error(f"投票結果更新失敗: {e}")

    async def _process_expired_vote(self, vote: Dict[str, Any]):
        """處理單個過期投票"""
        try:
            stats = await vote_dao.get_vote_statistics(vote["id"])
            total = sum(stats.values())
            embed = build_result_embed(vote["title"], stats, total, vote_id=vote["id"])

            channel = self.bot.get_channel(vote["channel_id"])
            if channel:
                await channel.send(embed=embed)

            await vote_dao.mark_vote_announced(vote["id"])
        except Exception as e:
            logger.error(f"處理過期投票失敗: {e}")

    async def _cleanup_expired_sessions(self):
        """✅ 清理過期的建立投票 session"""
        try:
            now = datetime.now(timezone.utc)
            expired_users = []

            async with self._session_lock:
                for user_id, session in list(VoteCore.vote_sessions.items()):
                    last_activity = session.get("last_activity", session.get("start_time"))
                    if (now - last_activity).total_seconds() > 1800:  # 30 分鐘過期
                        expired_users.append(user_id)

                for user_id in expired_users:
                    VoteCore.vote_sessions.pop(user_id, None)

            if expired_users:
                logger.info(f"清理了 {len(expired_users)} 個過期的投票會話")

        except Exception as e:
            logger.error(f"清理過期會話時發生錯誤: {e}")

    # ✅ 輔助方法優化
    def _check_user_permission(self, user: discord.Member, allowed_roles: List[int]) -> bool:
        """檢查用戶權限（優化版）"""
        if not allowed_roles:
            return True
        user_role_ids = {role.id for role in user.roles}
        return bool(user_role_ids & set(allowed_roles))

    def _calculate_time_left(self, end_time: datetime, current_time: datetime) -> str:
        """計算剩餘時間（優化版）"""
        delta = end_time - current_time
        if delta.total_seconds() <= 0:
            return "已結束"

        total_minutes = int(delta.total_seconds() // 60)
        if total_minutes < 60:
            return f"{total_minutes} 分鐘"

        hours = total_minutes // 60
        if hours < 24:
            return f"{hours} 小時"

        days = hours // 24
        return f"{days} 天"

    def _get_status_name(self, status: str) -> str:
        """取得狀態顯示名稱"""
        status_map = {"all": "全部", "active": "進行中", "finished": "已結束"}
        return status_map.get(status, "全部")

    def _format_duration(self, delta) -> str:
        """格式化持續時間"""
        total_seconds = int(delta.total_seconds())
        days = total_seconds // 86400
        hours = (total_seconds % 86400) // 3600
        minutes = (total_seconds % 3600) // 60

        if days > 0:
            return f"{days}天{hours}小時"
        elif hours > 0:
            return f"{hours}小時{minutes}分鐘"
        else:
            return f"{minutes}分鐘"

    # ✅ 保持向後相容性
    def time_left(self, end_time):
        """向後相容性方法"""
        return self._calculate_time_left(end_time, datetime.now(timezone.utc))

    # ===== 背景任務 =====

    @tasks.loop(minutes=5)
    async def announce_expired_votes(self):
        """定期檢查並公告過期投票結果"""
        try:
            expired_votes = await vote_dao.get_expired_votes_to_announce()
            if not expired_votes:
                return

            logger.info(f"發現 {len(expired_votes)} 個需要公告的過期投票")

            # 並行處理過期投票
            tasks = [self._process_expired_vote(vote) for vote in expired_votes]
            await asyncio.gather(*tasks, return_exceptions=True)

        except Exception as e:
            logger.error(f"檢查過期投票時發生錯誤: {e}")

    @announce_expired_votes.before_loop
    async def before_announce_expired_votes(self):
        """等待 bot 準備完成"""
        await self.bot.wait_until_ready()


# ✅ 分頁控制 View
class HistoryPaginationView(discord.ui.View):
    def __init__(self, current_page: int, total_pages: int, status: str):
        super().__init__(timeout=300)
        self.current_page = current_page
        self.total_pages = total_pages
        self.status = status

        # 根據頁數決定是否顯示按鈕
        if current_page > 1:
            self.add_item(PreviousPageButton())
        if current_page < total_pages:
            self.add_item(NextPageButton())


class PreviousPageButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label="⬅️ 上一頁", style=discord.ButtonStyle.secondary)

    async def callback(self, interaction: discord.Interaction):
        view: HistoryPaginationView = self.view
        new_page = view.current_page - 1

        # 重新執行歷史查詢
        cog = interaction.client.get_cog("VoteCore")
        if cog:
            await cog.vote_history.callback(cog, interaction, new_page, view.status)


class NextPageButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label="下一頁 ➡️", style=discord.ButtonStyle.secondary)

    async def callback(self, interaction: discord.Interaction):
        view: HistoryPaginationView = self.view
        new_page = view.current_page + 1

        # 重新執行歷史查詢
        cog = interaction.client.get_cog("VoteCore")
        if cog:
            await cog.vote_history.callback(cog, interaction, new_page, view.status)

    # ===== 投票系統設定指令 =====

    @commands.group(name="vote_settings", aliases=["投票設定"])
    @commands.has_permissions(manage_guild=True)
    async def vote_settings_group(self, ctx):
        """投票系統設定指令群組"""
        if ctx.invoked_subcommand is None:
            # 顯示當前設定
            settings = await vote_dao.get_vote_settings(ctx.guild.id)

            embed = discord.Embed(
                title="🗳️ 投票系統設定",
                description=f"**{ctx.guild.name}** 的投票系統設定",
                color=0x3498DB,
            )

            if settings:
                # 預設投票頻道
                vote_channel = (
                    f"<#{settings['default_vote_channel_id']}>"
                    if settings.get("default_vote_channel_id")
                    else "未設定"
                )
                embed.add_field(name="📺 預設投票頻道", value=vote_channel, inline=True)

                # 結果公告頻道
                announce_channel = (
                    f"<#{settings['announcement_channel_id']}>"
                    if settings.get("announcement_channel_id")
                    else "未設定"
                )
                embed.add_field(name="📢 結果公告頻道", value=announce_channel, inline=True)

                # 系統狀態
                status = "✅ 啟用" if settings.get("is_enabled") else "❌ 停用"
                embed.add_field(name="🔧 系統狀態", value=status, inline=True)

                # 時間限制
                embed.add_field(
                    name="⏰ 時間限制",
                    value=f"最長: {settings.get('max_vote_duration_hours', 72)}小時\n"
                    f"最短: {settings.get('min_vote_duration_minutes', 60)}分鐘",
                    inline=True,
                )

                # 功能開關
                features = []
                features.append(
                    f"匿名投票: {'✅' if settings.get('allow_anonymous_votes') else '❌'}"
                )
                features.append(f"多選投票: {'✅' if settings.get('allow_multi_choice') else '❌'}")
                features.append(
                    f"自動公告: {'✅' if settings.get('auto_announce_results') else '❌'}"
                )

                embed.add_field(name="⚙️ 功能狀態", value="\n".join(features), inline=True)

                # 創建權限
                if settings.get("require_role_to_create"):
                    role_count = len(settings.get("allowed_creator_roles", []))
                    embed.add_field(
                        name="👥 創建權限",
                        value=f"需要指定角色 ({role_count} 個角色)",
                        inline=True,
                    )
                else:
                    embed.add_field(
                        name="👥 創建權限",
                        value="所有用戶皆可建立",
                        inline=True,
                    )
            else:
                embed.add_field(
                    name="⚠️ 系統狀態",
                    value="投票系統尚未設定，使用預設配置",
                    inline=False,
                )

            embed.add_field(
                name="🔧 可用指令",
                value="• `!vote_settings channel <頻道>` - 設定預設投票頻道\n"
                "• `!vote_settings announce <頻道>` - 設定結果公告頻道\n"
                "• `!vote_settings enable/disable` - 啟用/停用系統\n"
                "• `!vote_settings reset` - 重置所有設定",
                inline=False,
            )

            await ctx.send(embed=embed)

    @vote_settings_group.command(name="channel")
    @commands.has_permissions(manage_guild=True)
    async def set_vote_channel(self, ctx, channel: discord.TextChannel = None):
        """設定預設投票頻道"""
        if not channel:
            await ctx.send("❌ 請指定一個文字頻道")
            return

        success = await vote_dao.set_default_vote_channel(ctx.guild.id, channel.id)
        if success:
            embed = discord.Embed(
                title="✅ 設定成功",
                description=f"預設投票頻道已設定為 {channel.mention}",
                color=0x2ECC71,
            )
            embed.add_field(
                name="📋 說明",
                value="新建立的投票將自動發布到此頻道",
                inline=False,
            )
        else:
            embed = discord.Embed(
                title="❌ 設定失敗",
                description="設定預設投票頻道時發生錯誤",
                color=0xE74C3C,
            )

        await ctx.send(embed=embed)

    @vote_settings_group.command(name="announce")
    @commands.has_permissions(manage_guild=True)
    async def set_announce_channel(self, ctx, channel: discord.TextChannel = None):
        """設定投票結果公告頻道"""
        if not channel:
            await ctx.send("❌ 請指定一個文字頻道")
            return

        success = await vote_dao.set_announcement_channel(ctx.guild.id, channel.id)
        if success:
            embed = discord.Embed(
                title="✅ 設定成功",
                description=f"投票結果公告頻道已設定為 {channel.mention}",
                color=0x2ECC71,
            )
            embed.add_field(
                name="📋 說明",
                value="投票結束後的結果將自動公告到此頻道",
                inline=False,
            )
        else:
            embed = discord.Embed(
                title="❌ 設定失敗",
                description="設定結果公告頻道時發生錯誤",
                color=0xE74C3C,
            )

        await ctx.send(embed=embed)

    @vote_settings_group.command(name="enable")
    @commands.has_permissions(manage_guild=True)
    async def enable_vote_system(self, ctx):
        """啟用投票系統"""
        success = await vote_dao.update_vote_settings(ctx.guild.id, {"is_enabled": True})
        if success:
            embed = discord.Embed(
                title="✅ 系統已啟用",
                description="投票系統現在已啟用",
                color=0x2ECC71,
            )
        else:
            embed = discord.Embed(
                title="❌ 操作失敗",
                description="啟用投票系統時發生錯誤",
                color=0xE74C3C,
            )

        await ctx.send(embed=embed)

    @vote_settings_group.command(name="disable")
    @commands.has_permissions(manage_guild=True)
    async def disable_vote_system(self, ctx):
        """停用投票系統"""
        success = await vote_dao.update_vote_settings(ctx.guild.id, {"is_enabled": False})
        if success:
            embed = discord.Embed(
                title="⚠️ 系統已停用",
                description="投票系統現在已停用，用戶無法建立新投票",
                color=0xF39C12,
            )
        else:
            embed = discord.Embed(
                title="❌ 操作失敗",
                description="停用投票系統時發生錯誤",
                color=0xE74C3C,
            )

        await ctx.send(embed=embed)

    @vote_settings_group.command(name="reset")
    @commands.has_permissions(administrator=True)
    async def reset_vote_settings(self, ctx):
        """重置投票系統設定（管理員限定）"""
        # 這裡可以添加重置邏輯
        embed = discord.Embed(
            title="🔄 重置功能",
            description="重置功能開發中，如需重置請聯繫系統管理員",
            color=0x95A5A6,
        )
        await ctx.send(embed=embed)

    # ============ 現代化 GUI 投票系統 ============

    @app_commands.command(name="quick_vote", description="🗳️ 快速創建投票 (現代GUI)")
    async def quick_vote(self, interaction: discord.Interaction):
        """快速創建投票的現代GUI界面"""
        try:
            # 檢查投票系統是否啟用
            vote_settings = await vote_dao.get_vote_settings(interaction.guild.id)
            if not vote_settings or not vote_settings.get("is_enabled", True):
                await interaction.response.send_message(
                    "❌ 投票系統目前已停用，請聯絡管理員", ephemeral=True
                )
                return

            # 顯示快速投票模態
            from bot.views.vote_views import QuickVoteModal

            modal = QuickVoteModal()
            await interaction.response.send_modal(modal)

        except Exception as e:
            logger.error(f"快速投票命令錯誤: {e}")
            await interaction.response.send_message("❌ 啟動快速投票時發生錯誤", ephemeral=True)

    @app_commands.command(name="vote_template", description="🗳️ 使用投票模板快速創建投票")
    async def vote_template(self, interaction: discord.Interaction):
        """投票模板系統入口"""
        try:
            # ✅ 檢查投票系統是否啟用
            if not await vote_dao.is_vote_system_enabled(interaction.guild.id):
                await interaction.response.send_message("❌ 投票系統已被停用。", ephemeral=True)
                return

            # ✅ 檢查是否在指定投票頻道中
            vote_settings = await vote_dao.get_vote_settings(interaction.guild.id)
            if vote_settings and vote_settings.get("default_vote_channel_id"):
                allowed_channel_id = vote_settings["default_vote_channel_id"]
                if interaction.channel.id != allowed_channel_id:
                    allowed_channel = interaction.guild.get_channel(allowed_channel_id)
                    channel_mention = (
                        allowed_channel.mention if allowed_channel else f"<#{allowed_channel_id}>"
                    )
                    await interaction.response.send_message(
                        f"❌ 投票只能在指定的投票頻道 {channel_mention} 中建立。",
                        ephemeral=True,
                    )
                    return

            # 顯示模板選擇界面
            from bot.views.vote_template_views import TemplateSelectionView

            template_view = TemplateSelectionView(interaction.user.id, interaction.guild.id)
            embed = template_view.create_embed()

            await interaction.response.send_message(embed=embed, view=template_view, ephemeral=True)

        except Exception as e:
            logger.error(f"啟動投票模板系統時發生錯誤: {e}")
            await interaction.response.send_message(
                "❌ 啟動投票模板系統時發生錯誤。", ephemeral=True
            )

    @app_commands.command(name="vote_panel", description="📊 投票管理面板 (現代GUI)")
    @app_commands.default_permissions(manage_messages=True)
    async def vote_panel(self, interaction: discord.Interaction):
        """顯示投票管理面板"""
        try:
            embed = discord.Embed(
                title="🗳️ 投票系統管理面板",
                description="使用現代化GUI界面管理投票系統",
                color=0x3498DB,
            )

            embed.add_field(
                name="🎯 主要功能",
                value="• 🗳️ 創建新投票\n• ⚙️ 管理現有投票\n• 📊 查看投票統計",
                inline=False,
            )

            embed.add_field(
                name="💡 使用說明",
                value="點擊下方按鈕開始使用投票系統",
                inline=False,
            )

            view = VoteManagementView()
            await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

        except Exception as e:
            logger.error(f"投票面板命令錯誤: {e}")
            await interaction.response.send_message("❌ 載入投票面板時發生錯誤", ephemeral=True)


async def setup(bot):
    await bot.add_cog(VoteCore(bot))
