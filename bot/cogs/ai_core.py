# bot/cogs/ai_core.py - AI 智能回覆核心功能
"""
AI 智能回覆核心功能
提供智能回覆建議、內容分析、自動標籤建議等指令
"""

import discord
from discord.ext import commands
from discord import app_commands
from typing import Optional, List
import asyncio
from shared.logger import logger

from bot.db.ai_dao import AIDAO
from bot.services.ai_manager import AIManager
from bot.db.ticket_dao import TicketDAO
from bot.views.ai_views import AIReplyView, AITagSuggestionView

class AICore(commands.Cog):
    """AI 智能回覆核心指令"""
    
    def __init__(self, bot):
        self.bot = bot
        self.ai_dao = AIDAO()
        self.ai_manager = AIManager()
        self.ticket_dao = TicketDAO()
    
    def cog_check(self, ctx):
        """Cog檢查：確保在伺服器中使用"""
        return ctx.guild is not None
    
    async def _is_ticket_channel(self, channel: discord.TextChannel) -> bool:
        """驗證是否為票券頻道"""
        try:
            ticket = await self.ticket_dao.get_ticket_by_channel(channel.id)
            return ticket is not None
        except Exception as e:
            logger.error(f"[AI] 票券頻道驗證失敗 {getattr(channel, 'id', None)}: {e}")
            # fallback: 若資料庫失敗則比對名稱
            return hasattr(channel, 'name') and channel.name.startswith('ticket-')

    # ========== AI 智能回覆指令 ==========

    @app_commands.command(name="ai_suggest", description="為當前票券獲取 AI 智能回覆建議")
    @app_commands.describe(
        content="要分析的內容（如不提供則分析票券歷史）",
        suggestions_count="建議數量（1-5）"
    )
    async def ai_suggest_reply(self, 
                              interaction: discord.Interaction, 
                              content: Optional[str] = None,
                              suggestions_count: Optional[int] = 3):
        """AI 智能回覆建議"""
        if not await self._is_ticket_channel(interaction.channel):
            await interaction.response.send_message(
                "❌ 此指令只能在票券頻道中使用", ephemeral=True
            )
            return
        
        if suggestions_count and (suggestions_count < 1 or suggestions_count > 5):
            await interaction.response.send_message(
                "❌ 建議數量必須在 1-5 之間", ephemeral=True
            )
            return
        
        await interaction.response.defer(ephemeral=True)
        
        try:
            # 取得票券資訊
            ticket_info = await self._get_ticket_info_from_channel(interaction.channel)
            if not ticket_info:
                await interaction.followup.send(
                    "❌ 無法取得票券資訊，請確認這是有效的票券頻道", ephemeral=True
                )
                return
            
            # 如果沒有提供內容，從頻道歷史中獲取
            if not content:
                content = await self._get_channel_context(interaction.channel)
            
            # 建立票券上下文
            ticket_context = {
                'user_id': ticket_info.get('user_id'),
                'guild_id': interaction.guild.id,
                'ticket_id': ticket_info.get('id'),
                'ticket_type': ticket_info.get('subject', 'unknown')
            }
            
            # 獲取 AI 建議
            ai_result = await self.ai_manager.suggest_reply(content, ticket_context)
            
            if not ai_result['success']:
                await interaction.followup.send(
                    f"❌ AI 分析失敗：{ai_result.get('error', '未知錯誤')}", ephemeral=True
                )
                return
            
            suggestions = ai_result['suggestions'][:suggestions_count or 3]
            
            if not suggestions:
                await interaction.followup.send(
                    "❌ 無法為此內容生成建議，內容可能過於簡短或模糊", ephemeral=True
                )
                return
            
            # 儲存建議記錄
            for suggestion in suggestions:
                await self.ai_dao.save_suggestion(
                    guild_id=interaction.guild.id,
                    user_id=interaction.user.id,
                    suggestion_type='reply',
                    original_content=content[:1000],  # 限制長度
                    suggested_content=suggestion['text'][:1000],
                    confidence_score=suggestion['confidence'],
                    analysis_data=ai_result['analysis'],
                    ticket_id=ticket_info.get('id')
                )
            
            # 創建互動式回覆界面
            view = AIReplyView(suggestions, ai_result['confidence'], self.ai_dao)
            
            embed = discord.Embed(
                title="🤖 AI 智能回覆建議",
                color=0x00bfff
            )
            
            embed.add_field(
                name="📊 分析結果",
                value=f"類型: {ai_result['analysis'].get('type', '未知')}\n"
                      f"情感: {ai_result['analysis'].get('sentiment', '中性')}\n"
                      f"緊急度: {ai_result['analysis'].get('urgency_level', 1)}/3\n"
                      f"置信度: {ai_result['confidence']:.1%}",
                inline=True
            )
            
            embed.add_field(
                name="🏷️ 關鍵字",
                value=", ".join(ai_result['analysis'].get('keywords', [])) or "無",
                inline=True
            )
            
            embed.add_field(
                name="💡 建議數量",
                value=f"{len(suggestions)} 個回覆建議",
                inline=True
            )
            
            embed.set_footer(text="點擊下方按鈕查看和使用建議")
            
            await interaction.followup.send(embed=embed, view=view, ephemeral=True)
            
        except Exception as e:
            logger.error(f"AI 回覆建議錯誤: {e}")
            await interaction.followup.send(
                f"❌ 處理過程中發生錯誤：{str(e)}", ephemeral=True
            )

    @app_commands.command(name="ai_tags", description="為當前票券獲取 AI 標籤建議")
    @app_commands.describe(content="要分析的內容（如不提供則分析票券內容）")
    async def ai_suggest_tags(self, 
                             interaction: discord.Interaction, 
                             content: Optional[str] = None):
        """AI 智能標籤建議"""
        if not await self._is_ticket_channel(interaction.channel):
            await interaction.response.send_message(
                "❌ 此指令只能在票券頻道中使用", ephemeral=True
            )
            return
        
        await interaction.response.defer(ephemeral=True)
        
        try:
            # 取得票券資訊
            ticket_info = await self._get_ticket_info_from_channel(interaction.channel)
            if not ticket_info:
                await interaction.followup.send(
                    "❌ 無法取得票券資訊", ephemeral=True
                )
                return
            
            # 如果沒有提供內容，使用票券描述
            if not content:
                content = ticket_info.get('description', '') or await self._get_channel_context(interaction.channel)
            
            # 獲取標籤建議
            tag_suggestions = await self.ai_manager.suggest_tags(
                content, ticket_info.get('subject')
            )
            
            if not tag_suggestions:
                await interaction.followup.send(
                    "❌ 無法為此內容生成標籤建議", ephemeral=True
                )
                return
            
            # 儲存建議記錄
            for suggestion in tag_suggestions:
                await self.ai_dao.save_suggestion(
                    guild_id=interaction.guild.id,
                    user_id=interaction.user.id,
                    suggestion_type='tag',
                    original_content=content[:1000],
                    suggested_content=suggestion['tag_name'],
                    confidence_score=suggestion['confidence'],
                    ticket_id=ticket_info.get('id')
                )
            
            # 創建標籤建議界面
            view = AITagSuggestionView(tag_suggestions, ticket_info['id'], self.ai_dao)
            
            embed = discord.Embed(
                title="🏷️ AI 智能標籤建議",
                color=0xff6b35
            )
            
            suggestion_text = []
            for i, suggestion in enumerate(tag_suggestions, 1):
                suggestion_text.append(
                    f"{i}. **{suggestion['tag_name']}** ({suggestion['confidence']:.1%})"
                    f"\n   └ {suggestion['reason']}"
                )
            
            embed.add_field(
                name="💡 建議標籤",
                value="\n\n".join(suggestion_text),
                inline=False
            )
            
            embed.set_footer(text="點擊下方按鈕應用標籤")
            
            await interaction.followup.send(embed=embed, view=view, ephemeral=True)
            
        except Exception as e:
            logger.error(f"AI 標籤建議錯誤: {e}")
            await interaction.followup.send(
                f"❌ 處理過程中發生錯誤：{str(e)}", ephemeral=True
            )

    @app_commands.command(name="ai_priority", description="為當前票券獲取 AI 優先級評估")
    @app_commands.describe(content="要分析的內容")
    async def ai_assess_priority(self, 
                                interaction: discord.Interaction, 
                                content: Optional[str] = None):
        """AI 智能優先級評估"""
        if not await self._is_ticket_channel(interaction.channel):
            await interaction.response.send_message(
                "❌ 此指令只能在票券頻道中使用", ephemeral=True
            )
            return
        
        await interaction.response.defer(ephemeral=True)
        
        try:
            # 取得票券資訊
            ticket_info = await self._get_ticket_info_from_channel(interaction.channel)
            if not ticket_info:
                await interaction.followup.send("❌ 無法取得票券資訊", ephemeral=True)
                return
            
            # 如果沒有提供內容，使用票券描述
            if not content:
                content = ticket_info.get('description', '') or await self._get_channel_context(interaction.channel)
            
            # 建立用戶上下文
            user_context = {
                'user_id': ticket_info.get('user_id'),
                'guild_id': interaction.guild.id
            }
            
            # 評估優先級
            priority_result = await self.ai_manager.assess_priority(content, user_context)
            
            # 儲存建議記錄
            await self.ai_dao.save_suggestion(
                guild_id=interaction.guild.id,
                user_id=interaction.user.id,
                suggestion_type='priority',
                original_content=content[:1000],
                suggested_content=priority_result['suggested_priority'],
                confidence_score=priority_result['confidence'],
                analysis_data=priority_result.get('analysis', {}),
                ticket_id=ticket_info.get('id')
            )
            
            embed = discord.Embed(
                title="🎯 AI 智能優先級評估",
                color=0xff9500
            )
            
            # 優先級顏色映射
            priority_colors = {
                'low': 0x28a745,    # 綠色
                'medium': 0xffc107,  # 黃色
                'high': 0xdc3545     # 紅色
            }
            
            priority = priority_result['suggested_priority']
            embed.color = priority_colors.get(priority, 0x6c757d)
            
            # 優先級 Emoji
            priority_emojis = {
                'low': '🟢',
                'medium': '🟡',
                'high': '🔴'
            }
            
            embed.add_field(
                name="🎯 建議優先級",
                value=f"{priority_emojis.get(priority, '⚪')} **{priority.upper()}**",
                inline=True
            )
            
            embed.add_field(
                name="📊 置信度",
                value=f"{priority_result['confidence']:.1%}",
                inline=True
            )
            
            embed.add_field(
                name="🔢 評分",
                value=f"{priority_result['score']:.1f}/4.0",
                inline=True
            )
            
            if priority_result.get('adjustments'):
                embed.add_field(
                    name="⚖️ 調整因子",
                    value="\n".join([f"• {adj}" for adj in priority_result['adjustments']]),
                    inline=False
                )
            
            # 分析詳情
            analysis = priority_result.get('analysis', {})
            if analysis:
                analysis_text = []
                if analysis.get('type') != 'unknown':
                    analysis_text.append(f"類型: {analysis['type']}")
                if analysis.get('sentiment') != 'neutral':
                    analysis_text.append(f"情感: {analysis['sentiment']}")
                if analysis.get('complexity') != 'medium':
                    analysis_text.append(f"複雜度: {analysis['complexity']}")
                
                if analysis_text:
                    embed.add_field(
                        name="🔍 分析詳情",
                        value=" | ".join(analysis_text),
                        inline=False
                    )
            
            embed.set_footer(text="AI 評估僅供參考，最終決定請依實際情況判斷")
            
            await interaction.followup.send(embed=embed, ephemeral=True)
            
        except Exception as e:
            logger.error(f"AI 優先級評估錯誤: {e}")
            await interaction.followup.send(
                f"❌ 處理過程中發生錯誤：{str(e)}", ephemeral=True
            )

    # ========== AI 管理指令 ==========

    @commands.group(name='ai', invoke_without_command=True)
    @commands.has_permissions(manage_guild=True)
    async def ai_group(self, ctx):
        """AI 系統管理指令群組"""
        if ctx.invoked_subcommand is None:
            embed = discord.Embed(
                title="🤖 AI 智能回覆系統",
                description="管理和監控 AI 智能回覆功能",
                color=0x00bfff
            )
            
            embed.add_field(
                name="📊 統計指令",
                value="• `!ai stats [天數]` - 查看 AI 使用統計\n"
                      "• `!ai performance` - 查看 AI 性能指標\n"
                      "• `!ai history` - 查看建議歷史",
                inline=False
            )
            
            embed.add_field(
                name="🔧 管理指令",
                value="• `!ai cleanup [天數]` - 清理舊數據\n"
                      "• `!ai feedback` - 查看用戶回饋\n"
                      "• `!ai learn` - 手動添加學習數據",
                inline=False
            )
            
            embed.add_field(
                name="💡 斜線指令",
                value="• `/ai_suggest` - 獲取智能回覆建議\n"
                      "• `/ai_tags` - 獲取智能標籤建議\n"
                      "• `/ai_priority` - 獲取優先級評估",
                inline=False
            )
            
            await ctx.send(embed=embed)

    @ai_group.command(name='stats')
    @commands.has_permissions(manage_guild=True)
    async def ai_statistics(self, ctx, days: int = 30):
        """查看 AI 使用統計"""
        if days < 1 or days > 365:
            await ctx.send("❌ 天數必須在 1-365 之間")
            return
        
        try:
            stats = await self.ai_dao.get_statistics(ctx.guild.id, days)
            
            embed = discord.Embed(
                title=f"📊 AI 系統統計 (過去 {days} 天)",
                color=0x00bfff
            )
            
            # 基本統計
            embed.add_field(
                name="📈 使用統計",
                value=f"總建議: {stats['total_suggestions']}\n"
                      f"已採用: {stats['total_accepted']}\n"
                      f"採用率: {stats['acceptance_rate']:.1%}\n"
                      f"日均建議: {stats['daily_average']:.1f}",
                inline=True
            )
            
            embed.add_field(
                name="🎯 品質指標",
                value=f"平均置信度: {stats['avg_confidence']:.1%}\n"
                      f"期間天數: {days} 天",
                inline=True
            )
            
            # 分類統計
            if stats.get('category_breakdown'):
                category_text = []
                for category, data in stats['category_breakdown'].items():
                    rate = data['accepted'] / data['total'] if data['total'] > 0 else 0
                    category_text.append(f"• {category}: {data['total']} ({rate:.1%})")
                
                embed.add_field(
                    name="📋 分類統計",
                    value="\n".join(category_text),
                    inline=False
                )
            
            await ctx.send(embed=embed)
            
        except Exception as e:
            logger.error(f"AI 統計查詢錯誤: {e}")
            await ctx.send(f"❌ 查詢統計時發生錯誤：{str(e)}")

    @ai_group.command(name='history')
    @commands.has_permissions(manage_guild=True)
    async def ai_history(self, ctx, suggestion_type: str = None, limit: int = 10):
        """查看 AI 建議歷史"""
        if limit < 1 or limit > 50:
            await ctx.send("❌ 限制數量必須在 1-50 之間")
            return
        
        valid_types = ['reply', 'tag', 'priority']
        if suggestion_type and suggestion_type not in valid_types:
            await ctx.send(f"❌ 無效的建議類型。有效類型: {', '.join(valid_types)}")
            return
        
        try:
            history = await self.ai_dao.get_suggestion_history(
                ctx.guild.id, suggestion_type, limit
            )
            
            if not history:
                await ctx.send("📭 沒有找到建議歷史記錄")
                return
            
            embed = discord.Embed(
                title=f"📝 AI 建議歷史 ({suggestion_type or '全部'})",
                color=0xff6b35
            )
            
            for i, record in enumerate(history[:10], 1):
                status = "✅ 已採用" if record['is_accepted'] else "⏳ 待處理"
                embed.add_field(
                    name=f"{i}. {record['suggestion_type']} ({record['confidence_score']:.1%})",
                    value=f"{status}\n"
                          f"時間: {record['created_at'].strftime('%m-%d %H:%M')}\n"
                          f"內容: {record['suggested_content'][:50]}...",
                    inline=False
                )
            
            if len(history) > 10:
                embed.set_footer(text=f"顯示前 10 筆，共 {len(history)} 筆記錄")
            
            await ctx.send(embed=embed)
            
        except Exception as e:
            logger.error(f"AI 歷史查詢錯誤: {e}")
            await ctx.send(f"❌ 查詢歷史時發生錯誤：{str(e)}")

    @ai_group.command(name='cleanup')
    @commands.has_permissions(manage_guild=True)
    async def ai_cleanup(self, ctx, days: int = 90):
        """清理舊的 AI 數據"""
        if days < 30 or days > 365:
            await ctx.send("❌ 清理天數必須在 30-365 之間")
            return
        
        try:
            # 確認清理
            confirm_embed = discord.Embed(
                title="⚠️ 確認清理",
                description=f"將清理 {days} 天前的 AI 數據，此操作不可復原。\n\n"
                          f"繼續請點擊 ✅，取消請點擊 ❌",
                color=0xffa500
            )
            
            view = discord.ui.View(timeout=30)
            
            async def confirm_callback(interaction):
                if interaction.user != ctx.author:
                    await interaction.response.send_message("❌ 只有指令發起人可以確認", ephemeral=True)
                    return
                
                await interaction.response.defer()
                
                # 執行清理
                cleaned_count = await self.ai_dao.cleanup_old_data(days)
                
                result_embed = discord.Embed(
                    title="✅ 清理完成",
                    description=f"已清理 {cleaned_count} 條舊數據記錄",
                    color=0x28a745
                )
                
                await interaction.edit_original_response(embed=result_embed, view=None)
            
            async def cancel_callback(interaction):
                if interaction.user != ctx.author:
                    await interaction.response.send_message("❌ 只有指令發起人可以取消", ephemeral=True)
                    return
                
                cancel_embed = discord.Embed(
                    title="❌ 清理已取消",
                    color=0x6c757d
                )
                
                await interaction.response.edit_message(embed=cancel_embed, view=None)
            
            confirm_btn = discord.ui.Button(label="確認清理", style=discord.ButtonStyle.green, emoji="✅")
            cancel_btn = discord.ui.Button(label="取消", style=discord.ButtonStyle.red, emoji="❌")
            
            confirm_btn.callback = confirm_callback
            cancel_btn.callback = cancel_callback
            
            view.add_item(confirm_btn)
            view.add_item(cancel_btn)
            
            await ctx.send(embed=confirm_embed, view=view)
            
        except Exception as e:
            logger.error(f"AI 數據清理錯誤: {e}")
            await ctx.send(f"❌ 清理過程中發生錯誤：{str(e)}")

    # ========== 輔助方法 ==========

    async def _get_ticket_info_from_channel(self, channel: discord.TextChannel) -> Optional[dict]:
        """從頻道取得票券資訊"""
        try:
            # 優先使用頻道ID直接查詢
            ticket_info = await self.ticket_dao.get_ticket_by_channel(channel.id)
            if ticket_info:
                return ticket_info
            
            # 如果直接查詢失敗，則從頻道名稱中提取票券 ID
            if not channel.name.startswith('ticket-'):
                return None
            
            ticket_id_str = channel.name.split('-')[1]
            ticket_id = int(ticket_id_str)
            
            # 查詢票券資訊
            ticket_info = await self.ticket_dao.get_ticket_by_id(ticket_id)
            return ticket_info
            
        except (ValueError, IndexError, TypeError):
            return None

    async def _get_channel_context(self, channel: discord.TextChannel, limit: int = 10) -> str:
        """從頻道歷史中獲取上下文"""
        try:
            messages = []
            async for message in channel.history(limit=limit):
                if message.author.bot:
                    continue  # 跳過機器人訊息
                
                content = message.content.strip()
                if content and len(content) > 10:  # 過濾太短的訊息
                    messages.append(content)
            
            # 反轉順序（最舊的在前）
            messages.reverse()
            
            # 合併成上下文
            context = "\n".join(messages)
            
            # 限制長度
            if len(context) > 2000:
                context = context[:2000] + "..."
            
            return context or "無法獲取足夠的上下文資訊"
            
        except Exception as e:
            logger.error(f"獲取頻道上下文錯誤: {e}")
            return "獲取上下文時發生錯誤"

async def setup(bot):
    """載入擴展"""
    await bot.add_cog(AICore(bot))