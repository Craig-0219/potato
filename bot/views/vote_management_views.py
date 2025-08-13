# bot/views/vote_management_views.py
"""
投票系統管理面板
提供完整的投票管理、統計分析和可視化功能
"""

import asyncio
from datetime import datetime, timedelta, timezone
from typing import Optional, List, Dict, Any, Literal
import discord
from discord import ui

from bot.utils.embed_builder import EmbedBuilder
from bot.db import vote_dao
from shared.logger import logger


class VoteManagementPanelView(ui.View):
    """投票系統管理面板"""
    
    def __init__(self, guild_id: int, user_permissions: discord.Permissions):
        super().__init__(timeout=300)
        self.guild_id = guild_id
        self.permissions = user_permissions
        self._build_panel()
    
    def _build_panel(self):
        """根據權限構建管理面板"""
        # 基礎功能（所有人可用）
        self.add_item(ActiveVotesButton(self.guild_id))
        self.add_item(VoteHistoryButton(self.guild_id))
        
        # 管理員功能
        if self.permissions.manage_guild:
            self.add_item(VoteAnalyticsButton(self.guild_id))
            self.add_item(BatchManageButton(self.guild_id))
            self.add_item(ExportDataButton(self.guild_id))
        
        # 系統管理員功能
        if self.permissions.administrator:
            self.add_item(SystemSettingsButton(self.guild_id))
            self.add_item(DatabaseCleanupButton(self.guild_id))


class ActiveVotesButton(ui.Button):
    """查看活動投票按鈕"""
    
    def __init__(self, guild_id: int):
        super().__init__(
            label="🗳️ 活動投票",
            style=discord.ButtonStyle.primary,
            emoji="🗳️",
            row=0
        )
        self.guild_id = guild_id
    
    async def callback(self, interaction: discord.Interaction):
        """顯示活動投票列表"""
        await interaction.response.defer(ephemeral=True)
        
        try:
            # 獲取活動投票
            now = datetime.now(timezone.utc)
            active_votes = await vote_dao.get_votes_by_status(self.guild_id, "active")
            
            if not active_votes:
                embed = EmbedBuilder.create_info_embed(
                    "🗳️ 活動投票",
                    "目前沒有進行中的投票"
                )
                await interaction.followup.send(embed=embed, ephemeral=True)
                return
            
            # 創建活動投票列表視圖
            active_view = ActiveVotesListView(active_votes)
            embed = await active_view.create_list_embed()
            
            await interaction.followup.send(embed=embed, view=active_view, ephemeral=True)
            
        except Exception as e:
            logger.error(f"獲取活動投票失敗: {e}")
            await interaction.followup.send("❌ 獲取活動投票時發生錯誤", ephemeral=True)


class VoteHistoryButton(ui.Button):
    """投票歷史按鈕"""
    
    def __init__(self, guild_id: int):
        super().__init__(
            label="📋 投票歷史",
            style=discord.ButtonStyle.secondary,
            emoji="📋",
            row=0
        )
        self.guild_id = guild_id
    
    async def callback(self, interaction: discord.Interaction):
        """顯示投票歷史"""
        await interaction.response.defer(ephemeral=True)
        
        try:
            # 獲取最近的投票歷史
            end_date = datetime.now(timezone.utc)
            start_date = end_date - timedelta(days=30)  # 最近30天
            
            votes = await vote_dao.get_votes_by_date_range(
                self.guild_id, start_date, end_date
            )
            
            if not votes:
                embed = EmbedBuilder.create_info_embed(
                    "📋 投票歷史",
                    "最近30天沒有投票記錄"
                )
                await interaction.followup.send(embed=embed, ephemeral=True)
                return
            
            # 創建歷史列表視圖
            history_view = VoteHistoryListView(votes)
            embed = await history_view.create_history_embed()
            
            await interaction.followup.send(embed=embed, view=history_view, ephemeral=True)
            
        except Exception as e:
            logger.error(f"獲取投票歷史失敗: {e}")
            await interaction.followup.send("❌ 獲取投票歷史時發生錯誤", ephemeral=True)


class VoteAnalyticsButton(ui.Button):
    """投票分析按鈕"""
    
    def __init__(self, guild_id: int):
        super().__init__(
            label="📊 統計分析",
            style=discord.ButtonStyle.success,
            emoji="📊",
            row=0
        )
        self.guild_id = guild_id
    
    async def callback(self, interaction: discord.Interaction):
        """打開統計分析面板"""
        await interaction.response.defer(ephemeral=True)
        
        try:
            analytics_view = VoteAnalyticsView(self.guild_id)
            embed = await analytics_view.create_analytics_embed()
            
            await interaction.followup.send(embed=embed, view=analytics_view, ephemeral=True)
            
        except Exception as e:
            logger.error(f"打開統計分析失敗: {e}")
            await interaction.followup.send("❌ 打開統計分析時發生錯誤", ephemeral=True)


class BatchManageButton(ui.Button):
    """批量管理按鈕"""
    
    def __init__(self, guild_id: int):
        super().__init__(
            label="⚙️ 批量管理",
            style=discord.ButtonStyle.secondary,
            emoji="⚙️",
            row=1
        )
        self.guild_id = guild_id
    
    async def callback(self, interaction: discord.Interaction):
        """打開批量管理面板"""
        # 批量管理功能
        embed = EmbedBuilder.create_info_embed(
            "⚙️ 批量管理",
            "批量管理功能開發中...\n\n將包含：\n• 批量關閉投票\n• 批量匯出結果\n• 批量權限設定"
        )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)


class ExportDataButton(ui.Button):
    """匯出資料按鈕"""
    
    def __init__(self, guild_id: int):
        super().__init__(
            label="📤 匯出資料",
            style=discord.ButtonStyle.secondary,
            emoji="📤",
            row=1
        )
        self.guild_id = guild_id
    
    async def callback(self, interaction: discord.Interaction):
        """匯出投票資料"""
        await interaction.response.defer(ephemeral=True)
        
        try:
            export_view = VoteExportView(self.guild_id)
            embed = EmbedBuilder.create_info_embed(
                "📤 資料匯出",
                "選擇要匯出的資料類型和格式"
            )
            
            await interaction.followup.send(embed=embed, view=export_view, ephemeral=True)
            
        except Exception as e:
            logger.error(f"打開匯出面板失敗: {e}")
            await interaction.followup.send("❌ 打開匯出面板時發生錯誤", ephemeral=True)


class SystemSettingsButton(ui.Button):
    """系統設定按鈕"""
    
    def __init__(self, guild_id: int):
        super().__init__(
            label="🔧 系統設定",
            style=discord.ButtonStyle.danger,
            emoji="🔧",
            row=1
        )
        self.guild_id = guild_id
    
    async def callback(self, interaction: discord.Interaction):
        """系統設定"""
        embed = EmbedBuilder.create_warning_embed(
            "🔧 系統設定",
            "系統設定功能開發中...\n\n將包含：\n• 預設投票設定\n• 權限管理\n• 通知設定"
        )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)


class DatabaseCleanupButton(ui.Button):
    """資料庫清理按鈕"""
    
    def __init__(self, guild_id: int):
        super().__init__(
            label="🧹 資料清理",
            style=discord.ButtonStyle.danger,
            emoji="🧹",
            row=2
        )
        self.guild_id = guild_id
    
    async def callback(self, interaction: discord.Interaction):
        """資料庫清理"""
        embed = EmbedBuilder.create_warning_embed(
            "🧹 資料庫清理",
            "⚠️ 此功能會清理過期的投票資料\n\n功能開發中..."
        )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)


class ActiveVotesListView(ui.View):
    """活動投票列表視圖"""
    
    def __init__(self, votes: List[Dict[str, Any]]):
        super().__init__(timeout=300)
        self.votes = votes
        self.current_page = 0
        self.votes_per_page = 5
        
        self._setup_navigation()
    
    def _setup_navigation(self):
        """設置導航按鈕"""
        total_pages = (len(self.votes) - 1) // self.votes_per_page + 1
        
        if total_pages > 1:
            if self.current_page > 0:
                self.add_item(PreviousPageButton())
            
            self.add_item(PageInfoButton(self.current_page + 1, total_pages))
            
            if self.current_page < total_pages - 1:
                self.add_item(NextPageButton())
        
        # 添加操作按鈕
        self.add_item(RefreshVotesButton())
        self.add_item(VoteManageSelectMenu(self._get_current_votes()))
    
    def _get_current_votes(self) -> List[Dict[str, Any]]:
        """獲取當前頁的投票"""
        start_idx = self.current_page * self.votes_per_page
        end_idx = start_idx + self.votes_per_page
        return self.votes[start_idx:end_idx]
    
    async def create_list_embed(self) -> discord.Embed:
        """創建投票列表嵌入"""
        current_votes = self._get_current_votes()
        total_pages = (len(self.votes) - 1) // self.votes_per_page + 1
        
        embed = EmbedBuilder.create_info_embed(
            f"🗳️ 活動投票 ({len(self.votes)} 個)",
            f"第 {self.current_page + 1} 頁，共 {total_pages} 頁"
        )
        
        for vote in current_votes:
            # 計算剩餘時間
            end_time = vote.get('end_time')
            if end_time:
                if isinstance(end_time, str):
                    end_time = datetime.fromisoformat(end_time.replace('Z', '+00:00'))
                
                now = datetime.now(timezone.utc)
                time_left = end_time - now
                
                if time_left.total_seconds() > 0:
                    hours = int(time_left.total_seconds() // 3600)
                    minutes = int((time_left.total_seconds() % 3600) // 60)
                    time_text = f"{hours}小時 {minutes}分鐘"
                else:
                    time_text = "已結束"
            else:
                time_text = "未設定"
            
            # 獲取投票統計
            total_votes = vote.get('total_votes', 0)
            options_count = vote.get('options', {}).get('count', 0)
            
            embed.add_field(
                name=f"📊 {vote.get('title', '無標題')} (ID: {vote.get('id')})",
                value=f"**類型**: {'多選' if vote.get('is_multi') else '單選'}\n"
                      f"**參與人數**: {total_votes} 人\n"
                      f"**選項數**: {options_count}\n"
                      f"**剩餘時間**: {time_text}",
                inline=False
            )
        
        if not current_votes:
            embed.description = "目前沒有活動投票"
        
        return embed


class PreviousPageButton(ui.Button):
    """上一頁按鈕"""
    
    def __init__(self):
        super().__init__(
            label="⬅️ 上一頁",
            style=discord.ButtonStyle.secondary,
            emoji="⬅️"
        )
    
    async def callback(self, interaction: discord.Interaction):
        if self.view.current_page > 0:
            self.view.current_page -= 1
            await self._update_page(interaction)
    
    async def _update_page(self, interaction: discord.Interaction):
        """更新頁面"""
        self.view.clear_items()
        self.view._setup_navigation()
        
        embed = await self.view.create_list_embed()
        await interaction.response.edit_message(embed=embed, view=self.view)


class NextPageButton(ui.Button):
    """下一頁按鈕"""
    
    def __init__(self):
        super().__init__(
            label="➡️ 下一頁",
            style=discord.ButtonStyle.secondary,
            emoji="➡️"
        )
    
    async def callback(self, interaction: discord.Interaction):
        total_pages = (len(self.view.votes) - 1) // self.view.votes_per_page + 1
        if self.view.current_page < total_pages - 1:
            self.view.current_page += 1
            await self._update_page(interaction)
    
    async def _update_page(self, interaction: discord.Interaction):
        """更新頁面"""
        self.view.clear_items()
        self.view._setup_navigation()
        
        embed = await self.view.create_list_embed()
        await interaction.response.edit_message(embed=embed, view=self.view)


class PageInfoButton(ui.Button):
    """頁面資訊按鈕"""
    
    def __init__(self, current_page: int, total_pages: int):
        super().__init__(
            label=f"第 {current_page}/{total_pages} 頁",
            style=discord.ButtonStyle.secondary,
            disabled=True
        )


class RefreshVotesButton(ui.Button):
    """刷新按鈕"""
    
    def __init__(self):
        super().__init__(
            label="🔄 刷新",
            style=discord.ButtonStyle.secondary,
            emoji="🔄"
        )
    
    async def callback(self, interaction: discord.Interaction):
        """刷新投票列表"""
        await interaction.response.send_message("🔄 資料已刷新", ephemeral=True, delete_after=2)
        # TODO: 重新獲取投票資料並更新顯示


class VoteManageSelectMenu(ui.Select):
    """投票管理選單"""
    
    def __init__(self, votes: List[Dict[str, Any]]):
        options = []
        for vote in votes[:25]:  # Discord 限制最多25個選項
            vote_id = vote.get('id')
            title = vote.get('title', '無標題')[:50]  # 限制長度
            
            options.append(discord.SelectOption(
                label=f"ID:{vote_id} - {title}",
                description=f"管理投票 {vote_id}",
                value=str(vote_id)
            ))
        
        if not options:
            options.append(discord.SelectOption(
                label="無可管理投票",
                description="目前沒有可管理的投票",
                value="none"
            ))
        
        super().__init__(
            placeholder="選擇要管理的投票...",
            options=options,
            row=1
        )
    
    async def callback(self, interaction: discord.Interaction):
        """處理投票管理選擇"""
        if self.values[0] == "none":
            await interaction.response.send_message("沒有可管理的投票", ephemeral=True)
            return
        
        vote_id = int(self.values[0])
        
        # 創建投票管理面板
        manage_view = VoteManageView(vote_id)
        embed = EmbedBuilder.create_info_embed(
            f"🛠️ 管理投票 {vote_id}",
            "選擇要執行的管理操作"
        )
        
        await interaction.response.send_message(embed=embed, view=manage_view, ephemeral=True)


class VoteManageView(ui.View):
    """單個投票管理視圖"""
    
    def __init__(self, vote_id: int):
        super().__init__(timeout=300)
        self.vote_id = vote_id
        self._setup_management_options()
    
    def _setup_management_options(self):
        """設置管理選項"""
        self.add_item(ViewVoteDetailsButton(self.vote_id))
        self.add_item(EndVoteButton(self.vote_id))
        self.add_item(ExportVoteResultsButton(self.vote_id))
        self.add_item(GenerateChartButton(self.vote_id))


class ViewVoteDetailsButton(ui.Button):
    """查看投票詳情按鈕"""
    
    def __init__(self, vote_id: int):
        super().__init__(
            label="📊 查看詳情",
            style=discord.ButtonStyle.primary,
            emoji="📊"
        )
        self.vote_id = vote_id
    
    async def callback(self, interaction: discord.Interaction):
        """顯示投票詳情"""
        await interaction.response.defer(ephemeral=True)
        
        try:
            # 獲取投票詳細資料
            vote_data = await vote_dao.get_vote_by_id(self.vote_id)
            if not vote_data:
                await interaction.followup.send("❌ 找不到投票資料", ephemeral=True)
                return
            
            options = await vote_dao.get_vote_options(self.vote_id)
            stats = await vote_dao.get_vote_statistics(self.vote_id)
            
            embed = await self._create_details_embed(vote_data, options, stats)
            await interaction.followup.send(embed=embed, ephemeral=True)
            
        except Exception as e:
            logger.error(f"查看投票詳情失敗: {e}")
            await interaction.followup.send("❌ 查看詳情時發生錯誤", ephemeral=True)
    
    async def _create_details_embed(self, vote_data: Dict[str, Any], 
                                   options: List[str], stats: Dict[str, int]) -> discord.Embed:
        """創建詳情嵌入"""
        total_votes = sum(stats.values())
        
        embed = EmbedBuilder.create_info_embed(
            f"📊 投票詳情 (ID: {self.vote_id})",
            vote_data.get('title', '無標題')
        )
        
        # 基本資訊
        embed.add_field(
            name="🗳️ 基本資訊",
            value=f"**創建者**: <@{vote_data.get('creator_id', 'unknown')}>\n"
                  f"**類型**: {'多選' if vote_data.get('is_multi') else '單選'}\n"
                  f"**匿名**: {'是' if vote_data.get('anonymous') else '否'}\n"
                  f"**總票數**: {total_votes}",
            inline=True
        )
        
        # 時間資訊
        start_time = vote_data.get('start_time')
        end_time = vote_data.get('end_time')
        
        if start_time and end_time:
            embed.add_field(
                name="⏰ 時間資訊",
                value=f"**開始時間**: <t:{int(start_time.timestamp())}:F>\n"
                      f"**結束時間**: <t:{int(end_time.timestamp())}:F>\n"
                      f"**狀態**: {'進行中' if datetime.now(timezone.utc) < end_time else '已結束'}",
                inline=True
            )
        
        # 選項統計
        if stats:
            sorted_stats = sorted(stats.items(), key=lambda x: x[1], reverse=True)
            stats_text = ""
            
            for i, (option, count) in enumerate(sorted_stats):
                percent = (count / total_votes * 100) if total_votes > 0 else 0
                medal = ["🥇", "🥈", "🥉"][i] if i < 3 else "📊"
                
                progress_bar = self._create_progress_bar(percent)
                stats_text += f"{medal} **{option}**\n"
                stats_text += f"{progress_bar} {count} 票 ({percent:.1f}%)\n\n"
            
            embed.add_field(
                name="📈 投票結果",
                value=stats_text,
                inline=False
            )
        
        return embed
    
    def _create_progress_bar(self, percent: float, length: int = 15) -> str:
        """創建進度條"""
        filled = int(percent / 100 * length)
        return "█" * filled + "░" * (length - filled)


class EndVoteButton(ui.Button):
    """結束投票按鈕"""
    
    def __init__(self, vote_id: int):
        super().__init__(
            label="🛑 結束投票",
            style=discord.ButtonStyle.danger,
            emoji="🛑"
        )
        self.vote_id = vote_id
    
    async def callback(self, interaction: discord.Interaction):
        """結束投票確認"""
        confirm_view = ConfirmEndVoteView(self.vote_id)
        
        embed = EmbedBuilder.create_warning_embed(
            "⚠️ 確認結束投票",
            f"您確定要結束投票 {self.vote_id} 嗎？\n\n此操作無法撤銷！"
        )
        
        await interaction.response.send_message(embed=embed, view=confirm_view, ephemeral=True)


class ConfirmEndVoteView(ui.View):
    """確認結束投票視圖"""
    
    def __init__(self, vote_id: int):
        super().__init__(timeout=60)
        self.vote_id = vote_id
    
    @ui.button(label="✅ 確認結束", style=discord.ButtonStyle.danger, emoji="✅")
    async def confirm_end(self, interaction: discord.Interaction, button: ui.Button):
        """確認結束投票"""
        try:
            # 結束投票
            success = await vote_dao.end_vote(self.vote_id, "管理員手動結束")
            
            if success:
                await interaction.response.send_message(
                    f"✅ 投票 {self.vote_id} 已成功結束",
                    ephemeral=True
                )
            else:
                await interaction.response.send_message(
                    f"❌ 結束投票 {self.vote_id} 失敗",
                    ephemeral=True
                )
            
            # 禁用按鈕
            for item in self.children:
                item.disabled = True
            await interaction.edit_original_response(view=self)
            
        except Exception as e:
            logger.error(f"結束投票失敗: {e}")
            await interaction.response.send_message("❌ 結束投票時發生錯誤", ephemeral=True)
    
    @ui.button(label="❌ 取消", style=discord.ButtonStyle.secondary, emoji="❌")
    async def cancel_end(self, interaction: discord.Interaction, button: ui.Button):
        """取消結束"""
        await interaction.response.send_message("❌ 已取消結束投票", ephemeral=True)
        
        for item in self.children:
            item.disabled = True
        await interaction.edit_original_response(view=self)


class ExportVoteResultsButton(ui.Button):
    """匯出投票結果按鈕"""
    
    def __init__(self, vote_id: int):
        super().__init__(
            label="📤 匯出結果",
            style=discord.ButtonStyle.secondary,
            emoji="📤"
        )
        self.vote_id = vote_id
    
    async def callback(self, interaction: discord.Interaction):
        """匯出投票結果"""
        await interaction.response.defer(ephemeral=True)
        
        try:
            # 獲取投票資料
            vote_data = await vote_dao.get_vote_by_id(self.vote_id)
            options = await vote_dao.get_vote_options(self.vote_id)
            stats = await vote_dao.get_vote_statistics(self.vote_id)
            
            # 創建CSV內容
            csv_content = self._create_csv_content(vote_data, options, stats)
            
            # 創建檔案
            file = discord.File(
                fp=csv_content,
                filename=f"vote_{self.vote_id}_results.csv"
            )
            
            embed = EmbedBuilder.create_success_embed(
                "📤 匯出完成",
                f"投票 {self.vote_id} 的結果已匯出為CSV格式"
            )
            
            await interaction.followup.send(embed=embed, file=file, ephemeral=True)
            
        except Exception as e:
            logger.error(f"匯出投票結果失敗: {e}")
            await interaction.followup.send("❌ 匯出結果時發生錯誤", ephemeral=True)
    
    def _create_csv_content(self, vote_data: Dict[str, Any], 
                           options: List[str], stats: Dict[str, int]) -> bytes:
        """創建CSV內容"""
        import io
        import csv
        
        output = io.StringIO()
        writer = csv.writer(output)
        
        # 寫入標題資訊
        writer.writerow(['投票資訊'])
        writer.writerow(['投票ID', self.vote_id])
        writer.writerow(['標題', vote_data.get('title', '無標題')])
        writer.writerow(['類型', '多選' if vote_data.get('is_multi') else '單選'])
        writer.writerow(['匿名', '是' if vote_data.get('anonymous') else '否'])
        writer.writerow(['創建者ID', vote_data.get('creator_id', 'unknown')])
        writer.writerow([])  # 空行
        
        # 寫入結果
        writer.writerow(['投票結果'])
        writer.writerow(['選項', '票數', '百分比'])
        
        total_votes = sum(stats.values())
        for option in options:
            count = stats.get(option, 0)
            percent = (count / total_votes * 100) if total_votes > 0 else 0
            writer.writerow([option, count, f"{percent:.1f}%"])
        
        # 轉換為bytes
        csv_bytes = output.getvalue().encode('utf-8-sig')  # 使用UTF-8 BOM以確保Excel正確顯示
        return io.BytesIO(csv_bytes)


class GenerateChartButton(ui.Button):
    """生成圖表按鈕"""
    
    def __init__(self, vote_id: int):
        super().__init__(
            label="📊 生成圖表",
            style=discord.ButtonStyle.success,
            emoji="📊"
        )
        self.vote_id = vote_id
    
    async def callback(self, interaction: discord.Interaction):
        """生成投票圖表"""
        await interaction.response.defer(ephemeral=True)
        
        try:
            # 獲取投票資料
            vote_data = await vote_dao.get_vote_by_id(self.vote_id)
            stats = await vote_dao.get_vote_statistics(self.vote_id)
            
            if not stats:
                await interaction.followup.send("❌ 暫無投票資料，無法生成圖表", ephemeral=True)
                return
            
            # 創建圖表視圖
            chart_view = VoteChartGeneratorView(self.vote_id, vote_data, stats)
            embed = EmbedBuilder.create_info_embed(
                f"📊 生成投票圖表 (ID: {self.vote_id})",
                "選擇要生成的圖表類型"
            )
            
            await interaction.followup.send(embed=embed, view=chart_view, ephemeral=True)
            
        except Exception as e:
            logger.error(f"生成圖表失敗: {e}")
            await interaction.followup.send("❌ 生成圖表時發生錯誤", ephemeral=True)


class VoteChartGeneratorView(ui.View):
    """投票圖表生成器視圖"""
    
    def __init__(self, vote_id: int, vote_data: Dict[str, Any], stats: Dict[str, int]):
        super().__init__(timeout=300)
        self.vote_id = vote_id
        self.vote_data = vote_data
        self.stats = stats
    
    @ui.button(label="🥧 餅圖", style=discord.ButtonStyle.primary, emoji="🥧")
    async def generate_pie_chart(self, interaction: discord.Interaction, button: ui.Button):
        """生成餅圖"""
        await interaction.response.send_message("🥧 餅圖生成功能開發中...", ephemeral=True)
    
    @ui.button(label="📊 柱狀圖", style=discord.ButtonStyle.primary, emoji="📊")
    async def generate_bar_chart(self, interaction: discord.Interaction, button: ui.Button):
        """生成柱狀圖"""
        await interaction.response.send_message("📊 柱狀圖生成功能開發中...", ephemeral=True)
    
    @ui.button(label="📈 折線圖", style=discord.ButtonStyle.primary, emoji="📈")
    async def generate_line_chart(self, interaction: discord.Interaction, button: ui.Button):
        """生成趨勢折線圖"""
        await interaction.response.send_message("📈 趨勢圖生成功能開發中...", ephemeral=True)


class VoteHistoryListView(ui.View):
    """投票歷史列表視圖"""
    
    def __init__(self, votes: List[Dict[str, Any]]):
        super().__init__(timeout=300)
        self.votes = votes
        self.current_page = 0
        self.votes_per_page = 10
    
    async def create_history_embed(self) -> discord.Embed:
        """創建歷史嵌入"""
        start_idx = self.current_page * self.votes_per_page
        end_idx = start_idx + self.votes_per_page
        current_votes = self.votes[start_idx:end_idx]
        
        total_pages = (len(self.votes) - 1) // self.votes_per_page + 1
        
        embed = EmbedBuilder.create_info_embed(
            f"📋 投票歷史 ({len(self.votes)} 個)",
            f"第 {self.current_page + 1} 頁，共 {total_pages} 頁"
        )
        
        for vote in current_votes:
            status = "✅ 已結束" if vote.get('ended_at') else "🔄 進行中"
            total_votes = vote.get('total_votes', 0)
            
            embed.add_field(
                name=f"{status} {vote.get('title', '無標題')} (ID: {vote.get('id')})",
                value=f"**類型**: {'多選' if vote.get('is_multi') else '單選'}\n"
                      f"**參與人數**: {total_votes} 人\n"
                      f"**開始時間**: <t:{int(vote.get('start_time', datetime.now()).timestamp())}:F>",
                inline=False
            )
        
        return embed


class VoteAnalyticsView(ui.View):
    """投票分析視圖"""
    
    def __init__(self, guild_id: int):
        super().__init__(timeout=300)
        self.guild_id = guild_id
    
    async def create_analytics_embed(self) -> discord.Embed:
        """創建分析嵌入"""
        # 獲取統計資料
        total_votes = await self._get_total_votes_count()
        active_votes = await self._get_active_votes_count()
        monthly_votes = await self._get_monthly_votes_count()
        total_participants = await self._get_total_participants_count()
        
        embed = EmbedBuilder.create_info_embed(
            f"📊 投票系統統計分析",
            f"伺服器ID: {self.guild_id}"
        )
        
        embed.add_field(
            name="🗳️ 基本統計",
            value=f"**總投票數**: {total_votes}\n"
                  f"**活動投票**: {active_votes}\n"
                  f"**本月投票**: {monthly_votes}",
            inline=True
        )
        
        embed.add_field(
            name="👥 參與統計",
            value=f"**總參與人次**: {total_participants}\n"
                  f"**平均參與數**: {total_participants / total_votes if total_votes > 0 else 0:.1f}\n"
                  f"**參與率**: 計算中...",
            inline=True
        )
        
        embed.add_field(
            name="📈 趨勢分析",
            value="**本週增長**: 計算中...\n"
                  "**熱門投票**: 分析中...\n"
                  "**活躍時段**: 分析中...",
            inline=True
        )
        
        return embed
    
    async def _get_total_votes_count(self) -> int:
        """獲取總投票數"""
        try:
            # 這裡應該調用DAO方法獲取總投票數
            return 0  # 臨時返回
        except:
            return 0
    
    async def _get_active_votes_count(self) -> int:
        """獲取活動投票數"""
        try:
            # 這裡應該調用DAO方法獲取活動投票數
            return 0  # 臨時返回
        except:
            return 0
    
    async def _get_monthly_votes_count(self) -> int:
        """獲取本月投票數"""
        try:
            # 這裡應該調用DAO方法獲取本月投票數
            return 0  # 臨時返回
        except:
            return 0
    
    async def _get_total_participants_count(self) -> int:
        """獲取總參與人次"""
        try:
            # 這裡應該調用DAO方法獲取總參與人次
            return 0  # 臨時返回
        except:
            return 0


class VoteExportView(ui.View):
    """投票資料匯出視圖"""
    
    def __init__(self, guild_id: int):
        super().__init__(timeout=300)
        self.guild_id = guild_id
        
        # 添加匯出選項
        self.add_item(ExportFormatSelect())
        self.add_item(ExportTimeRangeSelect())
    
    @ui.button(label="📤 開始匯出", style=discord.ButtonStyle.success, emoji="📤", row=2)
    async def start_export(self, interaction: discord.Interaction, button: ui.Button):
        """開始匯出"""
        await interaction.response.send_message("📤 匯出功能開發中...", ephemeral=True)


class ExportFormatSelect(ui.Select):
    """匯出格式選擇"""
    
    def __init__(self):
        options = [
            discord.SelectOption(
                label="CSV 格式",
                description="適合 Excel 和數據分析",
                emoji="📊",
                value="csv"
            ),
            discord.SelectOption(
                label="JSON 格式", 
                description="適合程式處理",
                emoji="🔧",
                value="json"
            ),
            discord.SelectOption(
                label="PDF 報告",
                description="適合列印和分享",
                emoji="📄",
                value="pdf"
            )
        ]
        
        super().__init__(
            placeholder="選擇匯出格式...",
            options=options,
            row=0
        )
    
    async def callback(self, interaction: discord.Interaction):
        await interaction.response.send_message(
            f"✅ 已選擇匯出格式: {self.values[0].upper()}",
            ephemeral=True,
            delete_after=2
        )


class ExportTimeRangeSelect(ui.Select):
    """匯出時間範圍選擇"""
    
    def __init__(self):
        options = [
            discord.SelectOption(
                label="最近7天",
                description="匯出過去一週的投票資料",
                emoji="📅",
                value="7d"
            ),
            discord.SelectOption(
                label="最近30天",
                description="匯出過去一個月的投票資料",
                emoji="📆",
                value="30d"
            ),
            discord.SelectOption(
                label="最近90天",
                description="匯出過去三個月的投票資料",
                emoji="🗓️",
                value="90d"
            ),
            discord.SelectOption(
                label="全部資料",
                description="匯出所有歷史投票資料",
                emoji="📚",
                value="all"
            )
        ]
        
        super().__init__(
            placeholder="選擇時間範圍...",
            options=options,
            row=1
        )
    
    async def callback(self, interaction: discord.Interaction):
        await interaction.response.send_message(
            f"✅ 已選擇時間範圍: {self.values[0]}",
            ephemeral=True,
            delete_after=2
        )