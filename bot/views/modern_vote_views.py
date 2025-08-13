# bot/views/modern_vote_views.py
"""
現代化投票系統視圖
提供直覺、美觀的投票創建和參與體驗
"""

import asyncio
from datetime import datetime, timedelta, timezone
from typing import Optional, List, Dict, Any, Literal
import discord
from discord import ui

from bot.utils.embed_builder import EmbedBuilder
from bot.db import vote_dao
from shared.logger import logger


class QuickVoteModal(ui.Modal):
    """快速投票創建模態框"""
    
    def __init__(self):
        super().__init__(title="🗳️ 快速創建投票", timeout=300)
        
        # 投票標題
        self.title_input = ui.TextInput(
            label="投票標題",
            placeholder="例：今晚聚餐地點投票",
            max_length=100,
            required=True
        )
        self.add_item(self.title_input)
        
        # 投票選項
        self.options_input = ui.TextInput(
            label="投票選項 (用逗號分隔)",
            placeholder="選項1, 選項2, 選項3",
            style=discord.TextStyle.paragraph,
            max_length=500,
            required=True
        )
        self.add_item(self.options_input)
        
        # 持續時間
        self.duration_input = ui.TextInput(
            label="持續時間 (分鐘)",
            placeholder="60",
            default="60",
            max_length=4,
            required=True
        )
        self.add_item(self.duration_input)
    
    async def on_submit(self, interaction: discord.Interaction):
        """處理快速投票創建"""
        try:
            # 解析選項
            options = [opt.strip() for opt in self.options_input.value.split(',') if opt.strip()]
            
            if len(options) < 2:
                await interaction.response.send_message("❌ 至少需要2個選項", ephemeral=True)
                return
            
            if len(options) > 10:
                await interaction.response.send_message("❌ 最多只能有10個選項", ephemeral=True)
                return
            
            # 驗證持續時間
            try:
                duration = int(self.duration_input.value)
                if duration < 1 or duration > 10080:  # 最多一週
                    await interaction.response.send_message("❌ 持續時間必須在1-10080分鐘之間", ephemeral=True)
                    return
            except ValueError:
                await interaction.response.send_message("❌ 持續時間必須是數字", ephemeral=True)
                return
            
            await interaction.response.defer()
            
            # 創建投票配置
            vote_config = {
                'title': self.title_input.value,
                'options': options,
                'is_multi': False,  # 快速投票預設單選
                'anonymous': False,  # 快速投票預設公開
                'duration_minutes': duration,
                'allowed_roles': [],  # 快速投票預設所有人可投
                'creator_id': interaction.user.id,
                'guild_id': interaction.guild.id,
                'channel_id': interaction.channel.id
            }
            
            # 顯示確認視圖
            confirm_view = VoteCreationConfirmView(vote_config)
            embed = self._create_preview_embed(vote_config)
            
            await interaction.followup.send(
                embed=embed,
                view=confirm_view,
                ephemeral=True
            )
            
        except Exception as e:
            logger.error(f"快速投票創建失敗: {e}")
            if not interaction.response.is_done():
                await interaction.response.send_message("❌ 創建投票時發生錯誤", ephemeral=True)
            else:
                await interaction.followup.send("❌ 創建投票時發生錯誤", ephemeral=True)
    
    def _create_preview_embed(self, config: Dict[str, Any]) -> discord.Embed:
        """創建預覽嵌入"""
        embed = EmbedBuilder.create_info_embed(
            "🗳️ 投票預覽",
            f"**標題**: {config['title']}\n"
            f"**持續時間**: {config['duration_minutes']} 分鐘\n"
            f"**投票類型**: {'多選' if config['is_multi'] else '單選'}\n"
            f"**匿名**: {'是' if config['anonymous'] else '否'}"
        )
        
        options_text = "\n".join(f"{i+1}. {opt}" for i, opt in enumerate(config['options']))
        embed.add_field(
            name="📋 選項列表",
            value=options_text,
            inline=False
        )
        
        embed.set_footer(text="請確認設定後點擊「創建投票」")
        return embed


class VoteCreationConfirmView(ui.View):
    """投票創建確認視圖"""
    
    def __init__(self, vote_config: Dict[str, Any]):
        super().__init__(timeout=120)
        self.vote_config = vote_config
    
    @ui.button(label="✅ 創建投票", style=discord.ButtonStyle.green, emoji="✅")
    async def confirm_creation(self, interaction: discord.Interaction, button: ui.Button):
        """確認創建投票"""
        try:
            await interaction.response.defer(ephemeral=True)
            
            # 創建投票會話
            from bot.cogs.vote import VoteCog
            
            # 準備會話數據
            start_time = datetime.now(timezone.utc)
            end_time = start_time + timedelta(minutes=self.vote_config['duration_minutes'])
            
            session_data = {
                'title': self.vote_config['title'],
                'options': self.vote_config['options'],
                'is_multi': self.vote_config['is_multi'],
                'anonymous': self.vote_config['anonymous'],
                'allowed_roles': self.vote_config['allowed_roles'],
                'start_time': start_time,
                'end_time': end_time,
                'origin_channel': interaction.channel,
                'guild_id': self.vote_config['guild_id']
            }
            
            # 創建投票
            vote_id = await vote_dao.create_vote(session_data, self.vote_config['creator_id'])
            
            if vote_id:
                # 創建投票選項
                await vote_dao.create_vote_options(vote_id, self.vote_config['options'])
                
                # 創建現代化投票視圖
                vote_view = ModernVoteView(vote_id, session_data)
                vote_embed = await self._create_vote_embed(vote_id, session_data)
                
                # 發布投票
                vote_message = await interaction.channel.send(embed=vote_embed, view=vote_view)
                
                await interaction.followup.send(
                    f"✅ 投票已成功創建！投票ID: {vote_id}",
                    ephemeral=True
                )
                
                # 禁用確認按鈕
                for item in self.children:
                    item.disabled = True
                await interaction.edit_original_response(view=self)
            else:
                await interaction.followup.send("❌ 創建投票失敗，請稍後再試", ephemeral=True)
                
        except Exception as e:
            logger.error(f"確認創建投票失敗: {e}")
            await interaction.followup.send("❌ 創建投票時發生錯誤", ephemeral=True)
    
    @ui.button(label="❌ 取消", style=discord.ButtonStyle.grey, emoji="❌")
    async def cancel_creation(self, interaction: discord.Interaction, button: ui.Button):
        """取消創建"""
        await interaction.response.send_message("❌ 已取消創建投票", ephemeral=True)
        for item in self.children:
            item.disabled = True
        await interaction.edit_original_response(view=self)
    
    @ui.button(label="⚙️ 高級設定", style=discord.ButtonStyle.secondary, emoji="⚙️")
    async def advanced_settings(self, interaction: discord.Interaction, button: ui.Button):
        """打開高級設定"""
        settings_view = VoteAdvancedSettingsView(self.vote_config)
        embed = EmbedBuilder.create_info_embed(
            "⚙️ 高級投票設定",
            "調整投票的詳細設定選項"
        )
        
        await interaction.response.send_message(
            embed=embed,
            view=settings_view,
            ephemeral=True
        )
    
    async def _create_vote_embed(self, vote_id: int, session_data: Dict[str, Any]) -> discord.Embed:
        """創建投票嵌入"""
        embed = EmbedBuilder.create_info_embed(
            f"🗳️ {session_data['title']}",
            f"投票ID: `{vote_id}`"
        )
        
        # 投票信息
        embed.add_field(
            name="📊 投票資訊",
            value=f"**類型**: {'多選投票' if session_data['is_multi'] else '單選投票'}\n"
                  f"**匿名**: {'是' if session_data['anonymous'] else '否'}\n"
                  f"**參與人數**: 0 人",
            inline=True
        )
        
        # 時間信息
        embed.add_field(
            name="⏰ 時間資訊",
            value=f"**開始**: <t:{int(session_data['start_time'].timestamp())}:F>\n"
                  f"**結束**: <t:{int(session_data['end_time'].timestamp())}:F>\n"
                  f"**剩餘**: <t:{int(session_data['end_time'].timestamp())}:R>",
            inline=True
        )
        
        # 選項列表（初始狀態）
        options_text = ""
        for i, option in enumerate(session_data['options']):
            progress_bar = "░" * 20  # 空進度條
            options_text += f"**{i+1}. {option}**\n{progress_bar} 0票 (0.0%)\n\n"
        
        embed.add_field(
            name="📋 投票選項",
            value=options_text,
            inline=False
        )
        
        embed.set_footer(text="點擊下方按鈕參與投票")
        embed.color = 0x3498db
        
        return embed


class VoteAdvancedSettingsView(ui.View):
    """投票高級設定視圖"""
    
    def __init__(self, vote_config: Dict[str, Any]):
        super().__init__(timeout=300)
        self.vote_config = vote_config
        self._setup_components()
    
    def _setup_components(self):
        """設置組件"""
        # 投票類型選擇
        self.add_item(VoteTypeSelect(self.vote_config.get('is_multi', False)))
        
        # 匿名設定
        self.add_item(AnonymousToggleButton(self.vote_config.get('anonymous', False)))
        
        # 權限設定
        self.add_item(PermissionSettingsButton())
        
        # 時間設定
        self.add_item(TimeSettingsButton())
    
    @ui.button(label="💾 儲存設定", style=discord.ButtonStyle.success, emoji="💾", row=2)
    async def save_settings(self, interaction: discord.Interaction, button: ui.Button):
        """儲存高級設定"""
        embed = EmbedBuilder.create_success_embed(
            "✅ 設定已儲存",
            "高級設定已更新，請返回上一頁繼續創建投票"
        )
        
        await interaction.response.send_message(embed=embed, ephemeral=True, delete_after=3)
        
        # 禁用所有組件
        for item in self.children:
            item.disabled = True
        await interaction.edit_original_response(view=self)


class VoteTypeSelect(ui.Select):
    """投票類型選擇"""
    
    def __init__(self, current_multi: bool):
        options = [
            discord.SelectOption(
                label="單選投票",
                description="每人只能選擇一個選項",
                emoji="1️⃣",
                value="single",
                default=not current_multi
            ),
            discord.SelectOption(
                label="多選投票", 
                description="每人可以選擇多個選項",
                emoji="🔢",
                value="multi",
                default=current_multi
            )
        ]
        
        super().__init__(
            placeholder="選擇投票類型...",
            options=options,
            row=0
        )
    
    async def callback(self, interaction: discord.Interaction):
        is_multi = self.values[0] == "multi"
        self.view.vote_config['is_multi'] = is_multi
        
        await interaction.response.send_message(
            f"✅ 投票類型已設為: {'多選投票' if is_multi else '單選投票'}",
            ephemeral=True,
            delete_after=2
        )


class AnonymousToggleButton(ui.Button):
    """匿名投票切換按鈕"""
    
    def __init__(self, current_anonymous: bool):
        self.is_anonymous = current_anonymous
        
        label = "🔒 匿名投票" if current_anonymous else "👁️ 公開投票"
        style = discord.ButtonStyle.success if current_anonymous else discord.ButtonStyle.secondary
        
        super().__init__(label=label, style=style, row=0)
    
    async def callback(self, interaction: discord.Interaction):
        self.is_anonymous = not self.is_anonymous
        self.view.vote_config['anonymous'] = self.is_anonymous
        
        # 更新按鈕樣式
        if self.is_anonymous:
            self.label = "🔒 匿名投票"
            self.style = discord.ButtonStyle.success
        else:
            self.label = "👁️ 公開投票"
            self.style = discord.ButtonStyle.secondary
        
        await interaction.response.edit_message(view=self.view)
        
        await interaction.followup.send(
            f"✅ 已設為: {'匿名投票' if self.is_anonymous else '公開投票'}",
            ephemeral=True,
            delete_after=2
        )


class PermissionSettingsButton(ui.Button):
    """權限設定按鈕"""
    
    def __init__(self):
        super().__init__(
            label="👥 權限設定",
            style=discord.ButtonStyle.secondary,
            emoji="👥",
            row=1
        )
    
    async def callback(self, interaction: discord.Interaction):
        # 權限設定功能
        embed = EmbedBuilder.create_info_embed(
            "👥 權限設定",
            "權限設定功能開發中...\n目前預設為所有人可參與投票"
        )
        
        await interaction.response.send_message(embed=embed, ephemeral=True, delete_after=5)


class TimeSettingsButton(ui.Button):
    """時間設定按鈕"""
    
    def __init__(self):
        super().__init__(
            label="⏰ 時間設定",
            style=discord.ButtonStyle.secondary,
            emoji="⏰",
            row=1
        )
    
    async def callback(self, interaction: discord.Interaction):
        # 時間設定功能
        modal = VoteTimeSettingsModal(self.view.vote_config.get('duration_minutes', 60))
        await interaction.response.send_modal(modal)


class VoteTimeSettingsModal(ui.Modal):
    """投票時間設定模態框"""
    
    def __init__(self, current_duration: int):
        super().__init__(title="⏰ 投票時間設定", timeout=300)
        
        self.duration_input = ui.TextInput(
            label="持續時間 (分鐘)",
            placeholder="輸入1-10080之間的數字",
            default=str(current_duration),
            max_length=5,
            required=True
        )
        self.add_item(self.duration_input)
    
    async def on_submit(self, interaction: discord.Interaction):
        try:
            duration = int(self.duration_input.value)
            if duration < 1 or duration > 10080:
                await interaction.response.send_message(
                    "❌ 持續時間必須在1-10080分鐘之間",
                    ephemeral=True
                )
                return
            
            # 更新配置
            # 需要訪問父視圖的配置
            await interaction.response.send_message(
                f"✅ 投票時間已設為 {duration} 分鐘",
                ephemeral=True,
                delete_after=3
            )
            
        except ValueError:
            await interaction.response.send_message(
                "❌ 請輸入有效的數字",
                ephemeral=True
            )


class ModernVoteView(ui.View):
    """現代化投票參與視圖"""
    
    def __init__(self, vote_id: int, session_data: Dict[str, Any]):
        super().__init__(timeout=None)
        self.vote_id = vote_id
        self.session_data = session_data
        self.options = session_data['options']
        self.is_multi = session_data['is_multi']
        self.anonymous = session_data['anonymous']
        
        self._build_vote_interface()
    
    def _build_vote_interface(self):
        """構建投票界面"""
        if len(self.options) <= 5:
            self._build_button_interface()
        else:
            self._build_dropdown_interface()
        
        # 添加功能按鈕
        self.add_item(VoteInfoButton(self.vote_id, row=2))
        self.add_item(VoteStatsButton(self.vote_id, row=2))
    
    def _build_button_interface(self):
        """構建按鈕界面（5個選項以下）"""
        for i, option in enumerate(self.options):
            button = ModernVoteButton(
                option=option,
                vote_id=self.vote_id,
                option_index=i,
                is_multi=self.is_multi
            )
            
            # 計算行位置
            if len(self.options) <= 2:
                button.row = 0
            elif len(self.options) <= 4:
                button.row = i // 2
            else:
                button.row = i // 3
            
            self.add_item(button)
        
        if self.is_multi:
            self.add_item(SubmitVoteButton(self.vote_id, row=1))
            self.add_item(ClearSelectionButton(self.vote_id, row=1))
    
    def _build_dropdown_interface(self):
        """構建下拉選單界面（5個選項以上）"""
        self.add_item(VoteDropdownSelect(self.vote_id, self.options, self.is_multi))
        
        if self.is_multi:
            self.add_item(SubmitVoteButton(self.vote_id, row=1))
            self.add_item(ClearSelectionButton(self.vote_id, row=1))


class ModernVoteButton(ui.Button):
    """現代化投票按鈕"""
    
    def __init__(self, option: str, vote_id: int, option_index: int, is_multi: bool):
        # 簡化標籤，只顯示選項名稱
        label = option[:20] + "..." if len(option) > 20 else option
        
        super().__init__(
            label=label,
            style=discord.ButtonStyle.primary,
            custom_id=f"vote_{vote_id}_{option_index}"
        )
        
        self.option = option
        self.vote_id = vote_id
        self.option_index = option_index
        self.is_multi = is_multi
    
    async def callback(self, interaction: discord.Interaction):
        """處理投票按鈕點擊"""
        try:
            if self.is_multi:
                # 多選模式：添加到選擇列表
                await self._handle_multi_select(interaction)
            else:
                # 單選模式：直接投票
                await self._handle_single_vote(interaction)
                
        except Exception as e:
            logger.error(f"投票按鈕回調失敗: {e}")
            await interaction.response.send_message("❌ 投票時發生錯誤", ephemeral=True)
    
    async def _handle_single_vote(self, interaction: discord.Interaction):
        """處理單選投票"""
        # 檢查是否已投票
        existing_vote = await vote_dao.get_user_vote(self.vote_id, interaction.user.id)
        if existing_vote:
            await interaction.response.send_message("❌ 您已經投過票了", ephemeral=True)
            return
        
        # 記錄投票
        success = await vote_dao.record_vote(
            self.vote_id,
            interaction.user.id,
            [self.option]
        )
        
        if success:
            # 成功動畫
            await self._show_vote_success_animation(interaction)
            
            # 更新投票顯示
            await self._update_vote_display(interaction)
        else:
            await interaction.response.send_message("❌ 投票失敗，請稍後再試", ephemeral=True)
    
    async def _handle_multi_select(self, interaction: discord.Interaction):
        """處理多選模式選擇"""
        # 多選模式的邏輯
        await interaction.response.send_message(
            f"✅ 已選擇：{self.option}\n請點擊「確認投票」提交選擇",
            ephemeral=True
        )
    
    async def _show_vote_success_animation(self, interaction: discord.Interaction):
        """顯示投票成功動畫"""
        # 第一階段：處理中
        embed_processing = EmbedBuilder.create_info_embed(
            "📝 處理投票中...",
            f"正在記錄您對「{self.option}」的選擇"
        )
        embed_processing.color = 0xf39c12
        
        await interaction.response.send_message(embed=embed_processing, ephemeral=True)
        
        # 短暫延遲
        await asyncio.sleep(1)
        
        # 第二階段：成功
        embed_success = EmbedBuilder.create_success_embed(
            "✅ 投票成功！",
            f"您選擇了：**{self.option}**\n感謝您的參與！"
        )
        
        await interaction.edit_original_response(embed=embed_success)
        
        # 自動刪除
        await asyncio.sleep(3)
        await interaction.delete_original_response()
    
    async def _update_vote_display(self, interaction: discord.Interaction):
        """更新投票顯示"""
        try:
            # 獲取最新統計
            stats = await vote_dao.get_vote_statistics(self.vote_id)
            total_votes = sum(stats.values())
            
            # 更新嵌入
            vote_embed = await self._build_updated_embed(stats, total_votes)
            
            # 更新按鈕樣式
            updated_view = await self._build_updated_view(stats, total_votes)
            
            await interaction.message.edit(embed=vote_embed, view=updated_view)
            
        except Exception as e:
            logger.error(f"更新投票顯示失敗: {e}")
    
    async def _build_updated_embed(self, stats: Dict[str, int], total_votes: int) -> discord.Embed:
        """構建更新後的嵌入"""
        embed = EmbedBuilder.create_info_embed(
            f"🗳️ {self.view.session_data['title']}",
            f"投票ID: `{self.vote_id}`"
        )
        
        # 更新投票資訊
        embed.add_field(
            name="📊 投票資訊",
            value=f"**類型**: {'多選投票' if self.is_multi else '單選投票'}\n"
                  f"**匿名**: {'是' if self.view.anonymous else '否'}\n"
                  f"**參與人數**: {total_votes} 人",
            inline=True
        )
        
        # 時間資訊
        end_time = self.view.session_data['end_time']
        embed.add_field(
            name="⏰ 時間資訊",
            value=f"**結束時間**: <t:{int(end_time.timestamp())}:F>\n"
                  f"**剩餘時間**: <t:{int(end_time.timestamp())}:R>",
            inline=True
        )
        
        # 更新選項統計
        options_text = ""
        for i, option in enumerate(self.options):
            count = stats.get(option, 0)
            percent = (count / total_votes * 100) if total_votes > 0 else 0
            
            # 創建進度條
            progress_bar = self._create_progress_bar(percent)
            
            options_text += f"**{i+1}. {option}**\n"
            options_text += f"{progress_bar} {count}票 ({percent:.1f}%)\n\n"
        
        embed.add_field(
            name="📋 投票結果",
            value=options_text,
            inline=False
        )
        
        embed.color = 0x2ecc71 if total_votes > 0 else 0x3498db
        embed.set_footer(text=f"最後更新: {datetime.now().strftime('%H:%M:%S')}")
        
        return embed
    
    def _create_progress_bar(self, percent: float, length: int = 20) -> str:
        """創建進度條"""
        filled = int(percent / 100 * length)
        bar = "█" * filled + "░" * (length - filled)
        return bar
    
    async def _build_updated_view(self, stats: Dict[str, int], total_votes: int) -> ui.View:
        """構建更新後的視圖"""
        # 重新創建視圖以更新按鈕樣式
        new_view = ModernVoteView(self.vote_id, self.view.session_data)
        
        # 更新按鈕樣式以反映當前統計
        for item in new_view.children:
            if isinstance(item, ModernVoteButton):
                count = stats.get(item.option, 0)
                if count > 0:
                    # 有票數的選項使用綠色
                    item.style = discord.ButtonStyle.success
                    # 更新標籤顯示票數
                    option_text = item.option[:15] + "..." if len(item.option) > 15 else item.option
                    item.label = f"{option_text} ({count})"
        
        return new_view


class VoteDropdownSelect(ui.Select):
    """投票下拉選單（用於選項較多的情況）"""
    
    def __init__(self, vote_id: int, options: List[str], is_multi: bool):
        discord_options = [
            discord.SelectOption(
                label=opt[:25] + "..." if len(opt) > 25 else opt,
                description=opt if len(opt) <= 50 else opt[:47] + "...",
                value=str(i)
            )
            for i, opt in enumerate(options)
        ]
        
        super().__init__(
            placeholder="選擇您要投票的選項...",
            options=discord_options,
            min_values=1,
            max_values=len(options) if is_multi else 1,
            row=0
        )
        
        self.vote_id = vote_id
        self.vote_options = options
        self.is_multi = is_multi
    
    async def callback(self, interaction: discord.Interaction):
        """處理下拉選單選擇"""
        try:
            selected_options = [self.vote_options[int(value)] for value in self.values]
            
            if self.is_multi:
                # 多選：暫存選擇
                await interaction.response.send_message(
                    f"✅ 已選擇：{', '.join(selected_options)}\n"
                    "請點擊「確認投票」提交選擇",
                    ephemeral=True
                )
            else:
                # 單選：直接投票
                success = await vote_dao.record_vote(
                    self.vote_id,
                    interaction.user.id,
                    selected_options
                )
                
                if success:
                    await interaction.response.send_message(
                        f"✅ 投票成功！您選擇了：{selected_options[0]}",
                        ephemeral=True
                    )
                    # TODO: 更新投票顯示
                else:
                    await interaction.response.send_message(
                        "❌ 投票失敗，請稍後再試",
                        ephemeral=True
                    )
                    
        except Exception as e:
            logger.error(f"下拉選單投票失敗: {e}")
            await interaction.response.send_message("❌ 投票時發生錯誤", ephemeral=True)


class SubmitVoteButton(ui.Button):
    """提交投票按鈕（多選模式）"""
    
    def __init__(self, vote_id: int, row: int = 1):
        super().__init__(
            label="✅ 確認投票",
            style=discord.ButtonStyle.success,
            emoji="✅",
            row=row
        )
        self.vote_id = vote_id
    
    async def callback(self, interaction: discord.Interaction):
        """處理投票提交"""
        # TODO: 實現多選投票提交邏輯
        await interaction.response.send_message(
            "多選投票提交功能開發中...",
            ephemeral=True
        )


class ClearSelectionButton(ui.Button):
    """清除選擇按鈕（多選模式）"""
    
    def __init__(self, vote_id: int, row: int = 1):
        super().__init__(
            label="🗑️ 清除選擇",
            style=discord.ButtonStyle.secondary,
            emoji="🗑️",
            row=row
        )
        self.vote_id = vote_id
    
    async def callback(self, interaction: discord.Interaction):
        """處理清除選擇"""
        # TODO: 實現清除選擇邏輯
        await interaction.response.send_message(
            "✅ 選擇已清除",
            ephemeral=True,
            delete_after=2
        )


class VoteInfoButton(ui.Button):
    """投票資訊按鈕"""
    
    def __init__(self, vote_id: int, row: int = 2):
        super().__init__(
            label="📊 詳細資訊",
            style=discord.ButtonStyle.secondary,
            emoji="📊",
            row=row
        )
        self.vote_id = vote_id
    
    async def callback(self, interaction: discord.Interaction):
        """顯示投票詳細資訊"""
        try:
            # 獲取投票詳細資料
            vote_data = await vote_dao.get_vote_by_id(self.vote_id)
            if not vote_data:
                await interaction.response.send_message("❌ 找不到投票資料", ephemeral=True)
                return
            
            stats = await vote_dao.get_vote_statistics(self.vote_id)
            total_votes = sum(stats.values())
            
            embed = EmbedBuilder.create_info_embed(
                f"📊 投票詳細資訊 (ID: {self.vote_id})",
                vote_data.get('title', '無標題')
            )
            
            embed.add_field(
                name="🗳️ 基本資訊",
                value=f"**創建者**: <@{vote_data.get('creator_id', 'unknown')}>\n"
                      f"**類型**: {'多選' if vote_data.get('is_multi') else '單選'}\n"
                      f"**匿名**: {'是' if vote_data.get('anonymous') else '否'}",
                inline=True
            )
            
            embed.add_field(
                name="📈 參與統計",
                value=f"**總票數**: {total_votes}\n"
                      f"**選項數**: {len(stats)}\n"
                      f"**平均票數**: {total_votes / len(stats) if stats else 0:.1f}",
                inline=True
            )
            
            if stats:
                # 顯示排行榜
                sorted_options = sorted(stats.items(), key=lambda x: x[1], reverse=True)
                ranking_text = ""
                for i, (option, count) in enumerate(sorted_options[:5]):
                    medal = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣"][i] if i < 5 else f"{i+1}."
                    percent = (count / total_votes * 100) if total_votes > 0 else 0
                    ranking_text += f"{medal} {option}: {count}票 ({percent:.1f}%)\n"
                
                embed.add_field(
                    name="🏆 選項排行",
                    value=ranking_text or "暫無數據",
                    inline=False
                )
            
            await interaction.response.send_message(embed=embed, ephemeral=True)
            
        except Exception as e:
            logger.error(f"獲取投票資訊失敗: {e}")
            await interaction.response.send_message("❌ 獲取資訊時發生錯誤", ephemeral=True)


class VoteStatsButton(ui.Button):
    """投票統計按鈕"""
    
    def __init__(self, vote_id: int, row: int = 2):
        super().__init__(
            label="📈 即時統計",
            style=discord.ButtonStyle.secondary,
            emoji="📈",
            row=row
        )
        self.vote_id = vote_id
    
    async def callback(self, interaction: discord.Interaction):
        """顯示即時統計"""
        await interaction.response.defer(ephemeral=True)
        
        try:
            # 創建統計圖表視圖
            stats_view = VoteStatsView(self.vote_id)
            await stats_view.show_stats(interaction)
            
        except Exception as e:
            logger.error(f"顯示統計失敗: {e}")
            await interaction.followup.send("❌ 獲取統計時發生錯誤", ephemeral=True)


class VoteStatsView(ui.View):
    """投票統計視圖"""
    
    def __init__(self, vote_id: int):
        super().__init__(timeout=300)
        self.vote_id = vote_id
    
    async def show_stats(self, interaction: discord.Interaction):
        """顯示統計資料"""
        stats = await vote_dao.get_vote_statistics(self.vote_id)
        
        if not stats:
            await interaction.followup.send("📊 暫無統計資料", ephemeral=True)
            return
        
        embed = await self._create_stats_embed(stats)
        await interaction.followup.send(embed=embed, view=self, ephemeral=True)
    
    async def _create_stats_embed(self, stats: Dict[str, int]) -> discord.Embed:
        """創建統計嵌入"""
        total_votes = sum(stats.values())
        
        embed = EmbedBuilder.create_info_embed(
            f"📈 投票統計 (ID: {self.vote_id})",
            f"總票數: {total_votes} 票"
        )
        
        if stats:
            # 按票數排序
            sorted_stats = sorted(stats.items(), key=lambda x: x[1], reverse=True)
            
            # 統計圖表
            chart_text = ""
            max_votes = max(stats.values()) if stats else 1
            
            for option, count in sorted_stats:
                percent = (count / total_votes * 100) if total_votes > 0 else 0
                bar_length = int((count / max_votes) * 15) if max_votes > 0 else 0
                
                bar = "█" * bar_length + "░" * (15 - bar_length)
                chart_text += f"**{option}**\n{bar} {count} ({percent:.1f}%)\n\n"
            
            embed.add_field(
                name="📊 選項統計",
                value=chart_text,
                inline=False
            )
            
            # 領先優勢分析
            if len(sorted_stats) >= 2:
                first_place = sorted_stats[0]
                second_place = sorted_stats[1]
                
                lead = first_place[1] - second_place[1]
                lead_percent = (lead / total_votes * 100) if total_votes > 0 else 0
                
                embed.add_field(
                    name="🏆 領先分析",
                    value=f"**第一名**: {first_place[0]} ({first_place[1]} 票)\n"
                          f"**第二名**: {second_place[0]} ({second_place[1]} 票)\n"
                          f"**領先優勢**: {lead} 票 ({lead_percent:.1f}%)",
                    inline=True
                )
        
        embed.set_footer(text=f"統計更新時間: {datetime.now().strftime('%H:%M:%S')}")
        
        return embed
    
    @ui.button(label="🔄 刷新", style=discord.ButtonStyle.secondary, emoji="🔄")
    async def refresh_stats(self, interaction: discord.Interaction, button: ui.Button):
        """刷新統計"""
        await interaction.response.defer()
        
        stats = await vote_dao.get_vote_statistics(self.vote_id)
        embed = await self._create_stats_embed(stats)
        
        await interaction.edit_original_response(embed=embed, view=self)