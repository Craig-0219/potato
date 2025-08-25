# bot/cogs/language_core.py - 多語言核心管理功能
"""
多語言核心管理功能
提供語言設定、統計、管理等指令
"""

import asyncio
from typing import List, Optional

import discord
from discord import app_commands
from discord.ext import commands

from bot.db.language_dao import LanguageDAO
from bot.services.language_manager import LanguageManager
from shared.logger import logger


class LanguageCore(commands.Cog):
    """多語言核心管理指令"""

    def __init__(self, bot):
        self.bot = bot
        self.language_manager = LanguageManager()
        self.language_dao = LanguageDAO()

    def cog_check(self, ctx):
        """Cog檢查：確保在伺服器中使用"""
        return ctx.guild is not None

    # ========== 用戶語言設定指令 ==========

    @app_commands.command(
        name="set_language", description="設定您的語言偏好 | Set your language preference"
    )
    @app_commands.describe(language="選擇語言 | Choose language")
    @app_commands.choices(
        language=[
            app_commands.Choice(name="繁體中文 | Traditional Chinese", value="zh-TW"),
            app_commands.Choice(name="简体中文 | Simplified Chinese", value="zh-CN"),
            app_commands.Choice(name="English", value="en"),
            app_commands.Choice(name="日本語 | Japanese", value="ja"),
            app_commands.Choice(name="한국어 | Korean", value="ko"),
        ]
    )
    async def set_user_language(self, interaction: discord.Interaction, language: str):
        """設定用戶語言偏好"""
        await interaction.response.defer(ephemeral=True)

        try:
            # 設定用戶語言
            success = await self.language_dao.set_user_language(
                user_id=interaction.user.id,
                guild_id=interaction.guild.id,
                language_code=language,
                auto_detected=False,
            )

            if success:
                # 使用新設定的語言回覆
                message = self.language_manager.get_string(
                    "common.language_set_success",
                    language,
                    language=self.language_manager.get_language_name(language),
                )

                embed = discord.Embed(
                    title="✅ " + self.language_manager.get_string("common.success", language),
                    description=message,
                    color=0x28A745,
                )

                # 添加指令更新提示
                if language == "zh-TW":
                    update_hint = "💡 **提示**: 指令描述將在下次使用時自動更新為新語言"
                elif language == "zh-CN":
                    update_hint = "💡 **提示**: 命令描述将在下次使用时自动更新为新语言"
                elif language == "ja":
                    update_hint = (
                        "💡 **ヒント**: コマンドの説明は次回使用時に新しい言語に自動更新されます"
                    )
                elif language == "ko":
                    update_hint = (
                        "💡 **힌트**: 명령어 설명은 다음 사용 시 새 언어로 자동 업데이트됩니다"
                    )
                else:
                    update_hint = "💡 **Hint**: Command descriptions will auto-update to the new language on next use"

                embed.add_field(name="", value=update_hint, inline=False)

                # 記錄使用統計
                await self.language_dao.update_language_usage(
                    guild_id=interaction.guild.id,
                    language_code=language,
                    user_count=1,
                    message_count=1,
                )
            else:
                embed = discord.Embed(
                    title="❌ " + self.language_manager.get_string("common.error", language),
                    description=self.language_manager.get_string(
                        "common.operation_failed", language
                    ),
                    color=0xDC3545,
                )

            await interaction.followup.send(embed=embed, ephemeral=True)

        except Exception as e:
            logger.error(f"設定用戶語言錯誤: {e}")
            await interaction.followup.send(f"❌ 設定語言時發生錯誤：{str(e)}", ephemeral=True)

    @app_commands.command(
        name="my_language", description="查看您的語言設定 | View your language settings"
    )
    async def get_user_language(self, interaction: discord.Interaction):
        """查看用戶語言設定"""
        await interaction.response.defer(ephemeral=True)

        try:
            # 取得用戶語言設定
            language_info = await self.language_dao.get_user_language(
                user_id=interaction.user.id, guild_id=interaction.guild.id
            )

            if language_info:
                lang_code = language_info["language_code"]
                lang_name = self.language_manager.get_language_name(lang_code)

                embed = discord.Embed(
                    title="🌐 "
                    + self.language_manager.get_string("language.your_setting", lang_code),
                    color=0x007BFF,
                )

                embed.add_field(
                    name=self.language_manager.get_string("language.current_language", lang_code),
                    value=f"**{lang_name}** (`{lang_code}`)",
                    inline=True,
                )

                if language_info["auto_detected"]:
                    embed.add_field(
                        name=self.language_manager.get_string("language.detection_type", lang_code),
                        value=self.language_manager.get_string("language.auto_detected", lang_code),
                        inline=True,
                    )

                    if language_info["confidence"]:
                        embed.add_field(
                            name=self.language_manager.get_string("language.confidence", lang_code),
                            value=f"{language_info['confidence']:.1%}",
                            inline=True,
                        )
                else:
                    embed.add_field(
                        name=self.language_manager.get_string("language.detection_type", lang_code),
                        value=self.language_manager.get_string("language.manually_set", lang_code),
                        inline=True,
                    )

                embed.add_field(
                    name=self.language_manager.get_string("common.set_at", lang_code),
                    value=f"<t:{int(language_info['created_at'].timestamp())}:F>",
                    inline=False,
                )

                embed.set_footer(
                    text=self.language_manager.get_string("language.change_hint", lang_code)
                )

            else:
                # 沒有設定，使用預設語言
                default_lang = self.language_manager.default_language

                embed = discord.Embed(
                    title="🌐 "
                    + self.language_manager.get_string("language.no_setting", default_lang),
                    description=self.language_manager.get_string(
                        "language.using_default",
                        default_lang,
                        default=self.language_manager.get_language_name(default_lang),
                    ),
                    color=0x6C757D,
                )

                embed.set_footer(
                    text=self.language_manager.get_string(
                        "language.set_language_hint", default_lang
                    )
                )

            await interaction.followup.send(embed=embed, ephemeral=True)

        except Exception as e:
            logger.error(f"查看用戶語言錯誤: {e}")
            await interaction.followup.send(f"❌ 查看語言設定時發生錯誤：{str(e)}", ephemeral=True)

    @app_commands.command(
        name="reset_language", description="重置您的語言設定 | Reset your language settings"
    )
    async def reset_user_language(self, interaction: discord.Interaction):
        """重置用戶語言設定"""
        await interaction.response.defer(ephemeral=True)

        try:
            # 取得當前語言用於回覆
            current_lang_info = await self.language_dao.get_user_language(
                user_id=interaction.user.id, guild_id=interaction.guild.id
            )

            lang_code = (
                current_lang_info["language_code"]
                if current_lang_info
                else self.language_manager.default_language
            )

            # 刪除用戶語言設定
            success = await self.language_dao.delete_user_language(interaction.user.id)

            if success:
                embed = discord.Embed(
                    title="✅ " + self.language_manager.get_string("common.success", lang_code),
                    description=self.language_manager.get_string(
                        "language.reset_success", lang_code
                    ),
                    color=0x28A745,
                )

                embed.add_field(
                    name=self.language_manager.get_string("language.now_using", lang_code),
                    value=f"**{self.language_manager.get_language_name(self.language_manager.default_language)}** (預設)",
                    inline=False,
                )
            else:
                embed = discord.Embed(
                    title="❌ " + self.language_manager.get_string("common.error", lang_code),
                    description=self.language_manager.get_string(
                        "common.operation_failed", lang_code
                    ),
                    color=0xDC3545,
                )

            await interaction.followup.send(embed=embed, ephemeral=True)

        except Exception as e:
            logger.error(f"重置用戶語言錯誤: {e}")
            await interaction.followup.send(f"❌ 重置語言設定時發生錯誤：{str(e)}", ephemeral=True)

    # ========== 伺服器語言管理指令 ==========

    @commands.group(name="language", invoke_without_command=True)
    @commands.has_permissions(manage_guild=True)
    async def language_group(self, ctx):
        """語言系統管理指令群組"""
        if ctx.invoked_subcommand is None:
            embed = discord.Embed(
                title="🌐 多語言支援系統",
                description="管理伺服器的多語言設定和統計",
                color=0x007BFF,
            )

            embed.add_field(
                name="🔧 管理指令",
                value="• `!language server <語言>` - 設定伺服器預設語言\n"
                "• `!language sync_commands` - 同步指令描述\n"
                "• `!language stats` - 查看語言使用統計\n"
                "• `!language popular` - 查看熱門語言\n"
                "• `!language detection` - 查看偵測準確率",
                inline=False,
            )

            embed.add_field(
                name="📊 統計指令",
                value="• `!language usage [語言]` - 查看特定語言使用情況\n"
                "• `!language users [語言]` - 查看使用特定語言的用戶\n"
                "• `!language cleanup [天數]` - 清理舊數據",
                inline=False,
            )

            embed.add_field(
                name="💡 斜線指令",
                value="• `/set_language` - 設定個人語言偏好\n"
                "• `/my_language` - 查看個人語言設定\n"
                "• `/reset_language` - 重置語言設定",
                inline=False,
            )

            await ctx.send(embed=embed)

    @language_group.command(name="server")
    @commands.has_permissions(manage_guild=True)
    async def set_server_language(self, ctx, language_code: str):
        """設定伺服器預設語言"""
        if not self.language_manager.is_supported_language(language_code):
            supported = ", ".join(self.language_manager.supported_languages.keys())
            await ctx.send(f"❌ 不支援的語言代碼。支援的語言：{supported}")
            return

        try:
            success = await self.language_dao.set_guild_language(ctx.guild.id, language_code)

            if success:
                lang_name = self.language_manager.get_language_name(language_code)
                embed = discord.Embed(
                    title="✅ 伺服器語言已設定",
                    description=f"伺服器預設語言已設定為：**{lang_name}** (`{language_code}`)",
                    color=0x28A745,
                )

                embed.add_field(
                    name="📝 說明",
                    value="• 這會影響系統訊息的語言\n"
                    "• 用戶仍可設定個人語言偏好\n"
                    "• 新用戶將使用此預設語言",
                    inline=False,
                )
            else:
                embed = discord.Embed(
                    title="❌ 設定失敗", description="設定伺服器語言時發生錯誤", color=0xDC3545
                )

            await ctx.send(embed=embed)

        except Exception as e:
            logger.error(f"設定伺服器語言錯誤: {e}")
            await ctx.send(f"❌ 設定伺服器語言時發生錯誤：{str(e)}")

    @language_group.command(name="stats")
    @commands.has_permissions(manage_guild=True)
    async def language_statistics(self, ctx, days: int = 30):
        """查看語言使用統計"""
        if days < 1 or days > 365:
            await ctx.send("❌ 天數必須在 1-365 之間")
            return

        try:
            stats = await self.language_dao.get_language_usage_stats(ctx.guild.id, days)

            if not stats:
                await ctx.send("📭 沒有找到語言使用統計數據")
                return

            embed = discord.Embed(title=f"📊 語言使用統計 (過去 {days} 天)", color=0x007BFF)

            total_messages = sum(stat["total_messages"] for stat in stats)

            for i, stat in enumerate(stats[:10], 1):
                lang_name = self.language_manager.get_language_name(stat["language_code"])
                percentage = (
                    (stat["total_messages"] / total_messages * 100) if total_messages > 0 else 0
                )

                value = f"訊息: {stat['total_messages']} ({percentage:.1f}%)\n"
                value += f"用戶: {stat['total_users']}\n"
                value += f"活躍天數: {stat['days_active']}\n"

                if stat["avg_accuracy"]:
                    value += f"偵測準確率: {stat['avg_accuracy']:.1%}"

                embed.add_field(
                    name=f"{i}. {lang_name} (`{stat['language_code']}`)", value=value, inline=True
                )

            embed.set_footer(text=f"總訊息數: {total_messages}")
            await ctx.send(embed=embed)

        except Exception as e:
            logger.error(f"查看語言統計錯誤: {e}")
            await ctx.send(f"❌ 查看統計時發生錯誤：{str(e)}")

    @language_group.command(name="popular")
    @commands.has_permissions(manage_guild=True)
    async def popular_languages(self, ctx, limit: int = 5):
        """查看熱門語言"""
        if limit < 1 or limit > 20:
            await ctx.send("❌ 限制數量必須在 1-20 之間")
            return

        try:
            popular = await self.language_dao.get_popular_languages(ctx.guild.id, limit)

            if not popular:
                await ctx.send("📭 沒有找到語言使用數據")
                return

            embed = discord.Embed(title="🔥 熱門語言排行榜", color=0xFF6B35)

            for i, lang in enumerate(popular, 1):
                lang_name = self.language_manager.get_language_name(lang["language_code"])

                # 排名 Emoji
                rank_emoji = {1: "🥇", 2: "🥈", 3: "🥉"}.get(i, "📍")

                embed.add_field(
                    name=f"{rank_emoji} {i}. {lang_name}",
                    value=f"總訊息: {lang['total_messages']}\n"
                    f"活躍天數: {lang['active_days']}\n"
                    f"用戶偏好: {lang['user_preferences']}",
                    inline=True,
                )

            await ctx.send(embed=embed)

        except Exception as e:
            logger.error(f"查看熱門語言錯誤: {e}")
            await ctx.send(f"❌ 查看熱門語言時發生錯誤：{str(e)}")

    @language_group.command(name="detection")
    @commands.has_permissions(manage_guild=True)
    async def detection_accuracy(self, ctx, days: int = 30):
        """查看語言偵測準確率"""
        if days < 1 or days > 365:
            await ctx.send("❌ 天數必須在 1-365 之間")
            return

        try:
            accuracy = await self.language_dao.get_detection_accuracy(ctx.guild.id, days=days)

            embed = discord.Embed(title=f"🎯 語言偵測準確率 (過去 {days} 天)", color=0x28A745)

            if accuracy["total_detections"] == 0:
                embed.description = "📭 沒有足夠的偵測數據"
                await ctx.send(embed=embed)
                return

            # 整體統計
            embed.add_field(
                name="📊 整體統計",
                value=f"總偵測次數: {accuracy['total_detections']}\n"
                f"正確偵測: {accuracy['total_correct']}\n"
                f"整體準確率: {accuracy['overall_accuracy']:.1%}",
                inline=False,
            )

            # 各語言準確率
            if accuracy["by_language"]:
                accuracy_text = []
                for lang, stats in accuracy["by_language"].items():
                    lang_name = self.language_manager.get_language_name(lang)
                    accuracy_text.append(
                        f"• **{lang_name}**: {stats['accuracy_rate']:.1%} "
                        f"({stats['correct_detections']}/{stats['total_detections']})"
                    )

                embed.add_field(
                    name="🌐 各語言準確率", value="\n".join(accuracy_text[:10]), inline=False
                )

            await ctx.send(embed=embed)

        except Exception as e:
            logger.error(f"查看偵測準確率錯誤: {e}")
            await ctx.send(f"❌ 查看偵測準確率時發生錯誤：{str(e)}")

    @language_group.command(name="sync_commands")
    @commands.has_permissions(manage_guild=True)
    async def sync_command_descriptions(self, ctx):
        """同步指令描述（管理員用）"""
        try:
            # 發送同步開始訊息
            embed = discord.Embed(
                title="🔄 同步指令描述",
                description="正在更新指令樹以反映新的語言設定...",
                color=0xFFA500,
            )

            message = await ctx.send(embed=embed)

            # 同步指令樹
            synced = await self.bot.tree.sync(guild=ctx.guild)

            # 發送完成訊息
            embed = discord.Embed(
                title="✅ 同步完成",
                description=f"已成功同步 {len(synced)} 個指令\n" "指令描述現在會顯示伺服器預設語言",
                color=0x28A745,
            )

            embed.add_field(
                name="📝 說明",
                value="• 指令名稱和描述已更新\n"
                "• 用戶個人語言設定仍然有效\n"
                "• 建議在更改伺服器語言後執行此操作",
                inline=False,
            )

            await message.edit(embed=embed)

        except Exception as e:
            logger.error(f"同步指令描述錯誤: {e}")

            embed = discord.Embed(
                title="❌ 同步失敗", description=f"同步指令時發生錯誤：{str(e)}", color=0xDC3545
            )

            await ctx.send(embed=embed)

    @language_group.command(name="cleanup")
    @commands.has_permissions(manage_guild=True)
    async def cleanup_language_data(self, ctx, days: int = 90):
        """清理舊的語言數據"""
        if days < 30 or days > 365:
            await ctx.send("❌ 清理天數必須在 30-365 之間")
            return

        try:
            # 確認清理
            confirm_embed = discord.Embed(
                title="⚠️ 確認清理",
                description=f"將清理 {days} 天前的語言偵測記錄，此操作不可復原。\n\n"
                f"繼續請點擊 ✅，取消請點擊 ❌",
                color=0xFFA500,
            )

            view = discord.ui.View(timeout=30)

            async def confirm_callback(interaction):
                if interaction.user != ctx.author:
                    await interaction.response.send_message(
                        "❌ 只有指令發起人可以確認", ephemeral=True
                    )
                    return

                await interaction.response.defer()

                # 執行清理
                cleaned_count = await self.language_dao.cleanup_old_detection_logs(days)

                result_embed = discord.Embed(
                    title="✅ 清理完成",
                    description=f"已清理 {cleaned_count} 條舊語言偵測記錄",
                    color=0x28A745,
                )

                await interaction.edit_original_response(embed=result_embed, view=None)

            async def cancel_callback(interaction):
                if interaction.user != ctx.author:
                    await interaction.response.send_message(
                        "❌ 只有指令發起人可以取消", ephemeral=True
                    )
                    return

                cancel_embed = discord.Embed(title="❌ 清理已取消", color=0x6C757D)

                await interaction.response.edit_message(embed=cancel_embed, view=None)

            confirm_btn = discord.ui.Button(
                label="確認清理", style=discord.ButtonStyle.green, emoji="✅"
            )
            cancel_btn = discord.ui.Button(label="取消", style=discord.ButtonStyle.red, emoji="❌")

            confirm_btn.callback = confirm_callback
            cancel_btn.callback = cancel_callback

            view.add_item(confirm_btn)
            view.add_item(cancel_btn)

            await ctx.send(embed=confirm_embed, view=view)

        except Exception as e:
            logger.error(f"語言數據清理錯誤: {e}")
            await ctx.send(f"❌ 清理過程中發生錯誤：{str(e)}")

    # ========== 事件監聽器 ==========

    @commands.Cog.listener()
    async def on_message(self, message):
        """監聽訊息進行語言偵測和統計"""
        # 忽略機器人訊息和私訊
        if message.author.bot or not message.guild or len(message.content.strip()) < 10:
            return

        try:
            # 取得用戶語言設定
            user_lang = await self.language_dao.get_user_language(
                user_id=message.author.id, guild_id=message.guild.id
            )

            if user_lang:
                # 用戶已設定語言，更新統計
                await self.language_dao.update_language_usage(
                    guild_id=message.guild.id,
                    language_code=user_lang["language_code"],
                    user_count=1,
                    message_count=1,
                )
            else:
                # 偵測語言
                detected_lang = self.language_manager.detect_language(message.content)

                if detected_lang:
                    # 記錄偵測結果
                    await self.language_dao.log_language_detection(
                        guild_id=message.guild.id,
                        user_id=message.author.id,
                        text=message.content,
                        detected_language=detected_lang,
                        confidence=0.7,  # 基礎置信度
                        method="pattern_based",
                    )

                    # 更新統計
                    await self.language_dao.update_language_usage(
                        guild_id=message.guild.id,
                        language_code=detected_lang,
                        user_count=1,
                        message_count=1,
                    )

        except Exception as e:
            logger.error(f"語言偵測事件錯誤: {e}")


async def setup(bot):
    """載入擴展"""
    await bot.add_cog(LanguageCore(bot))
