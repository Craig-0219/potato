# bot/cogs/welcome_core.py - 歡迎系統核心指令
"""
歡迎系統核心功能
包含歡迎系統設定、管理、測試等指令
"""

from typing import Optional

import discord
from discord.ext import commands

from bot.db.welcome_dao import WelcomeDAO
from bot.services.welcome_manager import WelcomeManager
from shared.logger import logger


class WelcomeCore(commands.Cog):
    """歡迎系統核心指令"""

    def __init__(self, bot):
        self.bot = bot
        self.welcome_dao = WelcomeDAO()
        self.welcome_manager = WelcomeManager(self.welcome_dao)

    def cog_check(self, ctx):
        """Cog檢查：確保在伺服器中使用"""
        return ctx.guild is not None

    # ========== 歡迎系統管理指令 ==========

    @commands.group(name="welcome", invoke_without_command=True)
    @commands.has_permissions(manage_guild=True)
    async def welcome_group(self, ctx):
        """歡迎系統管理指令群組"""
        if ctx.invoked_subcommand is None:
            embed = discord.Embed(
                title="🎉 歡迎系統管理",
                description="管理伺服器的歡迎和離開訊息系統",
                color=0x00FF00,
            )

            embed.add_field(
                name="📋 設定指令",
                value="• `!welcome setup` - 初始化歡迎系統\n"
                "• `!welcome channel <頻道>` - 設定歡迎頻道\n"
                "• `!welcome leave_channel <頻道>` - 設定離開頻道\n"
                "• `!welcome message <訊息>` - 設定歡迎訊息\n"
                "• `!welcome leave_message <訊息>` - 設定離開訊息",
                inline=False,
            )

            embed.add_field(
                name="👥 身分組管理",
                value="• `!welcome autorole add <身分組>` - 添加自動身分組\n"
                "• `!welcome autorole remove <身分組>` - 移除自動身分組\n"
                "• `!welcome autorole list` - 查看自動身分組",
                inline=False,
            )

            embed.add_field(
                name="🔧 系統管理",
                value="• `!welcome enable` - 啟用歡迎系統\n"
                "• `!welcome disable` - 停用歡迎系統\n"
                "• `!welcome test <用戶>` - 測試歡迎訊息\n"
                "• `!welcome status` - 查看系統狀態\n"
                "• `!welcome stats` - 查看統計資料",
                inline=False,
            )

            await ctx.send(embed=embed)

    @welcome_group.command(name="setup")
    @commands.has_permissions(manage_guild=True)
    async def welcome_setup(self, ctx):
        """初始化歡迎系統"""
        try:
            # 創建預設設定
            default_settings = {
                "is_enabled": True,
                "welcome_embed_enabled": True,
                "welcome_dm_enabled": False,
                "auto_role_enabled": False,
                "welcome_color": 0x00FF00,
            }

            success, message = await self.welcome_manager.update_welcome_settings(
                ctx.guild.id, **default_settings
            )

            if success:
                embed = discord.Embed(
                    title="✅ 歡迎系統初始化完成",
                    description="歡迎系統已成功初始化！請使用以下指令進行進一步設定：",
                    color=0x00FF00,
                )

                embed.add_field(
                    name="📋 下一步設定",
                    value="• `!welcome channel #歡迎頻道` - 設定歡迎頻道\n"
                    "• `!welcome message <訊息>` - 自定義歡迎訊息\n"
                    "• `!welcome autorole add @身分組` - 設定自動身分組",
                    inline=False,
                )

                await ctx.send(embed=embed)
            else:
                await ctx.send(f"❌ 初始化失敗：{message}")

        except Exception as e:
            logger.error(f"歡迎系統初始化錯誤: {e}")
            await ctx.send("❌ 初始化過程中發生錯誤")

    @welcome_group.command(name="channel")
    @commands.has_permissions(manage_guild=True)
    async def welcome_channel(self, ctx, channel: Optional[discord.TextChannel] = None):
        """設定歡迎頻道"""
        try:
            channel_id = channel.id if channel else None
            success, message = await self.welcome_manager.set_welcome_channel(
                ctx.guild.id, channel_id
            )

            if success:
                await ctx.send(f"✅ {message}")
            else:
                await ctx.send(f"❌ {message}")

        except Exception as e:
            logger.error(f"設定歡迎頻道錯誤: {e}")
            await ctx.send("❌ 設定過程中發生錯誤")

    @welcome_group.command(name="leave_channel")
    @commands.has_permissions(manage_guild=True)
    async def leave_channel(self, ctx, channel: Optional[discord.TextChannel] = None):
        """設定離開頻道"""
        try:
            channel_id = channel.id if channel else None
            success, message = await self.welcome_manager.set_leave_channel(
                ctx.guild.id, channel_id
            )

            if success:
                await ctx.send(f"✅ {message}")
            else:
                await ctx.send(f"❌ {message}")

        except Exception as e:
            logger.error(f"設定離開頻道錯誤: {e}")
            await ctx.send("❌ 設定過程中發生錯誤")

    @welcome_group.command(name="message")
    @commands.has_permissions(manage_guild=True)
    async def welcome_message(self, ctx, *, message: str):
        """設定歡迎訊息"""
        try:
            success, result = await self.welcome_manager.update_welcome_settings(
                ctx.guild.id, welcome_message=message
            )

            if success:
                embed = discord.Embed(
                    title="✅ 歡迎訊息已更新", description="新的歡迎訊息已儲存", color=0x00FF00
                )

                embed.add_field(
                    name="📝 可用變數",
                    value="• `{user_mention}` - 用戶提及\n"
                    "• `{user_name}` - 用戶暱稱\n"
                    "• `{guild_name}` - 伺服器名稱\n"
                    "• `{member_count}` - 成員數量\n"
                    "• `{current_date}` - 當前日期",
                    inline=False,
                )

                await ctx.send(embed=embed)
            else:
                await ctx.send(f"❌ 更新失敗：{result}")

        except Exception as e:
            logger.error(f"設定歡迎訊息錯誤: {e}")
            await ctx.send("❌ 設定過程中發生錯誤")

    @welcome_group.command(name="leave_message")
    @commands.has_permissions(manage_guild=True)
    async def leave_message(self, ctx, *, message: str):
        """設定離開訊息"""
        try:
            success, result = await self.welcome_manager.update_welcome_settings(
                ctx.guild.id, leave_message=message
            )

            if success:
                await ctx.send("✅ 離開訊息已更新")
            else:
                await ctx.send(f"❌ 更新失敗：{result}")

        except Exception as e:
            logger.error(f"設定離開訊息錯誤: {e}")
            await ctx.send("❌ 設定過程中發生錯誤")

    # ========== 自動身分組管理 ==========

    @welcome_group.group(name="autorole", invoke_without_command=True)
    @commands.has_permissions(manage_guild=True)
    async def autorole_group(self, ctx):
        """自動身分組管理"""
        if ctx.invoked_subcommand is None:
            await ctx.send("請使用 `!welcome autorole add/remove/list` 管理自動身分組")

    @autorole_group.command(name="add")
    @commands.has_permissions(manage_guild=True)
    async def autorole_add(self, ctx, role: discord.Role):
        """添加自動身分組"""
        try:
            # 檢查身分組階層
            if role >= ctx.guild.me.top_role:
                await ctx.send("❌ 無法分配比機器人更高階層的身分組")
                return

            if role.managed:
                await ctx.send("❌ 無法分配系統管理的身分組")
                return

            # 取得現有設定
            settings = await self.welcome_dao.get_welcome_settings(ctx.guild.id)
            current_roles = settings.get("auto_roles", []) if settings else []

            if role.id in current_roles:
                await ctx.send(f"❌ 身分組 {role.mention} 已在自動分配清單中")
                return

            # 添加身分組
            current_roles.append(role.id)
            success, message = await self.welcome_manager.set_auto_roles(
                ctx.guild.id, current_roles
            )

            if success:
                await ctx.send(f"✅ 已添加自動身分組：{role.mention}")
            else:
                await ctx.send(f"❌ 添加失敗：{message}")

        except Exception as e:
            logger.error(f"添加自動身分組錯誤: {e}")
            await ctx.send("❌ 添加過程中發生錯誤")

    @autorole_group.command(name="remove")
    @commands.has_permissions(manage_guild=True)
    async def autorole_remove(self, ctx, role: discord.Role):
        """移除自動身分組"""
        try:
            # 取得現有設定
            settings = await self.welcome_dao.get_welcome_settings(ctx.guild.id)
            current_roles = settings.get("auto_roles", []) if settings else []

            if role.id not in current_roles:
                await ctx.send(f"❌ 身分組 {role.mention} 不在自動分配清單中")
                return

            # 移除身分組
            current_roles.remove(role.id)
            success, message = await self.welcome_manager.set_auto_roles(
                ctx.guild.id, current_roles
            )

            if success:
                await ctx.send(f"✅ 已移除自動身分組：{role.mention}")
            else:
                await ctx.send(f"❌ 移除失敗：{message}")

        except Exception as e:
            logger.error(f"移除自動身分組錯誤: {e}")
            await ctx.send("❌ 移除過程中發生錯誤")

    @autorole_group.command(name="list")
    @commands.has_permissions(manage_guild=True)
    async def autorole_list(self, ctx):
        """查看自動身分組清單"""
        try:
            settings = await self.welcome_dao.get_welcome_settings(ctx.guild.id)

            if not settings or not settings.get("auto_roles"):
                await ctx.send("📋 目前沒有設定自動身分組")
                return

            embed = discord.Embed(title="👥 自動身分組清單", color=0x3498DB)

            role_list = []
            for role_id in settings["auto_roles"]:
                role = ctx.guild.get_role(role_id)
                if role:
                    role_list.append(f"• {role.mention} (`{role.name}`)")
                else:
                    role_list.append(f"• <已刪除的身分組> (ID: {role_id})")

            embed.description = "\n".join(role_list) if role_list else "沒有有效的自動身分組"
            embed.set_footer(
                text=f"啟用狀態: {'✅ 已啟用' if settings.get('auto_role_enabled') else '❌ 已停用'}"
            )

            await ctx.send(embed=embed)

        except Exception as e:
            logger.error(f"查看自動身分組錯誤: {e}")
            await ctx.send("❌ 查看過程中發生錯誤")

    # ========== 系統管理指令 ==========

    @welcome_group.command(name="enable")
    @commands.has_permissions(manage_guild=True)
    async def welcome_enable(self, ctx):
        """啟用歡迎系統"""
        try:
            success, message = await self.welcome_manager.update_welcome_settings(
                ctx.guild.id, is_enabled=True
            )

            if success:
                await ctx.send("✅ 歡迎系統已啟用")
            else:
                await ctx.send(f"❌ 啟用失敗：{message}")

        except Exception as e:
            logger.error(f"啟用歡迎系統錯誤: {e}")
            await ctx.send("❌ 啟用過程中發生錯誤")

    @welcome_group.command(name="disable")
    @commands.has_permissions(manage_guild=True)
    async def welcome_disable(self, ctx):
        """停用歐迎系統"""
        try:
            success, message = await self.welcome_manager.update_welcome_settings(
                ctx.guild.id, is_enabled=False
            )

            if success:
                await ctx.send("⚠️ 歡迎系統已停用")
            else:
                await ctx.send(f"❌ 停用失敗：{message}")

        except Exception as e:
            logger.error(f"停用歡迎系統錯誤: {e}")
            await ctx.send("❌ 停用過程中發生錯誤")

    @welcome_group.command(name="test")
    @commands.has_permissions(manage_guild=True)
    async def welcome_test(self, ctx, member: Optional[discord.Member] = None):
        """測試歡迎訊息"""
        try:
            test_member = member or ctx.author
            result = await self.welcome_manager.test_welcome_message(ctx.guild, test_member)

            if not result["success"]:
                await ctx.send(f"❌ 測試失敗：{result['message']}")
                return

            embed = discord.Embed(title="🧪 歡迎訊息測試", color=0xFFA500)

            embed.add_field(
                name="🎯 測試用戶", value=f"{test_member.mention} (`{test_member}`)", inline=False
            )

            embed.add_field(
                name="📝 格式化後的訊息",
                value=result["formatted_message"][:1024],  # Discord限制
                inline=False,
            )

            settings = result["settings"]
            status_list = [
                f"📢 歡迎頻道: {'✅' if settings.get('welcome_channel_id') else '❌'}",
                f"💌 私訊歡迎: {'✅' if settings.get('welcome_dm_enabled') else '❌'}",
                f"👥 自動身分組: {'✅' if settings.get('auto_role_enabled') else '❌'}",
                f"🎨 嵌入訊息: {'✅' if settings.get('welcome_embed_enabled') else '❌'}",
            ]

            embed.add_field(name="⚙️ 設定狀態", value="\n".join(status_list), inline=False)

            await ctx.send(embed=embed)

        except Exception as e:
            logger.error(f"測試歡迎訊息錯誤: {e}")
            await ctx.send("❌ 測試過程中發生錯誤")

    @welcome_group.command(name="simulate")
    @commands.has_permissions(manage_guild=True)
    async def welcome_simulate(self, ctx, member: Optional[discord.Member] = None):
        """模擬成員加入事件（用於測試歡迎系統）"""
        try:
            test_member = member or ctx.author
            await ctx.send(f"🔄 正在模擬 {test_member.mention} 的加入事件...")

            # 直接調用歡迎管理器的處理方法
            result = await self.welcome_manager.handle_member_join(test_member)

            # 創建結果報告
            embed = discord.Embed(
                title="🧪 歡迎事件模擬結果", color=0x00FF00 if result["success"] else 0xFF0000
            )

            embed.add_field(
                name="📋 處理狀態", value="✅ 成功" if result["success"] else "❌ 失敗", inline=True
            )

            embed.add_field(
                name="📨 歡迎訊息",
                value="✅ 已發送" if result["welcome_sent"] else "❌ 未發送",
                inline=True,
            )

            embed.add_field(
                name="📩 私訊歡迎",
                value="✅ 已發送" if result["dm_sent"] else "❌ 未發送",
                inline=True,
            )

            if result["roles_assigned"]:
                role_list = []
                for role_id in result["roles_assigned"]:
                    role = ctx.guild.get_role(role_id)
                    role_list.append(role.mention if role else f"未知身分組 ({role_id})")

                embed.add_field(name="🎭 分配身分組", value="\n".join(role_list), inline=False)
            else:
                embed.add_field(name="🎭 分配身分組", value="❌ 無身分組分配", inline=False)

            if result["errors"]:
                embed.add_field(name="❌ 錯誤訊息", value="\n".join(result["errors"]), inline=False)

            embed.set_footer(text=f"測試對象: {test_member}")
            await ctx.send(embed=embed)

        except Exception as e:
            logger.error(f"模擬歡迎事件錯誤: {e}")
            await ctx.send(f"❌ 模擬過程中發生錯誤：{str(e)}")

    @welcome_group.command(name="force")
    @commands.has_permissions(manage_guild=True)
    async def welcome_force(self, ctx, member: discord.Member):
        """強制觸發成員的歡迎處理（忽略重複檢查）"""
        try:
            await ctx.send(f"🔄 強制處理 {member.mention} 的歡迎事件...")

            # 取得 WelcomeListener 實例
            welcome_listener = ctx.bot.get_cog("WelcomeListener")
            if not welcome_listener:
                await ctx.send("❌ 找不到 WelcomeListener 組件")
                return

            # 清除可能的追蹤記錄
            welcome_listener.recent_joins.discard(member.id)
            welcome_listener.recent_updates.discard(member.id)

            # 強制處理歡迎事件
            await welcome_listener._handle_welcome_with_tracking(member, "強制處理")

            await ctx.send(f"✅ 已強制處理 {member.mention} 的歡迎事件")

        except Exception as e:
            logger.error(f"強制處理歡迎事件錯誤: {e}")
            await ctx.send(f"❌ 強制處理過程中發生錯誤：{str(e)}")

    @welcome_group.command(name="status")
    @commands.has_permissions(manage_guild=True)
    async def welcome_status(self, ctx):
        """查看歡迎系統狀態"""
        try:
            settings = await self.welcome_dao.get_welcome_settings(ctx.guild.id)

            embed = discord.Embed(
                title="🎉 歡迎系統狀態",
                color=0x00FF00 if settings and settings.get("is_enabled") else 0xFF6B6B,
            )

            if not settings:
                embed.description = "❌ 歡迎系統尚未設定\n使用 `!welcome setup` 初始化系統"
                await ctx.send(embed=embed)
                return

            # 系統狀態
            embed.add_field(
                name="🔧 系統狀態",
                value=f"啟用狀態: {'✅ 已啟用' if settings.get('is_enabled') else '❌ 已停用'}",
                inline=False,
            )

            # 頻道設定
            welcome_channel = (
                f"<#{settings['welcome_channel_id']}>"
                if settings.get("welcome_channel_id")
                else "❌ 未設定"
            )
            leave_channel = (
                f"<#{settings['leave_channel_id']}>"
                if settings.get("leave_channel_id")
                else "❌ 未設定"
            )

            embed.add_field(
                name="📺 頻道設定",
                value=f"歡迎頻道: {welcome_channel}\n離開頻道: {leave_channel}",
                inline=True,
            )

            # 功能設定
            features = [
                f"嵌入訊息: {'✅' if settings.get('welcome_embed_enabled') else '❌'}",
                f"私訊歡迎: {'✅' if settings.get('welcome_dm_enabled') else '❌'}",
                f"自動身分組: {'✅' if settings.get('auto_role_enabled') else '❌'}",
            ]

            embed.add_field(name="⚙️ 功能設定", value="\n".join(features), inline=True)

            # 自動身分組數量
            auto_roles_count = len(settings.get("auto_roles", []))
            embed.add_field(name="👥 自動身分組", value=f"{auto_roles_count} 個身分組", inline=True)

            embed.set_footer(
                text=f"最後更新: {settings['updated_at'].strftime('%Y-%m-%d %H:%M:%S')}"
            )

            await ctx.send(embed=embed)

        except Exception as e:
            logger.error(f"查看歡迎系統狀態錯誤: {e}")
            await ctx.send("❌ 查看狀態時發生錯誤")

    @welcome_group.command(name="refresh")
    @commands.has_permissions(manage_guild=True)
    async def welcome_refresh(self, ctx):
        """刷新歡迎系統監聽器（修復 RESUME 後的問題）"""
        try:
            await ctx.send("🔄 正在刷新歡迎系統監聽器...")

            # 取得 WelcomeListener 實例
            welcome_listener = ctx.bot.get_cog("WelcomeListener")
            if not welcome_listener:
                await ctx.send("❌ 找不到 WelcomeListener 組件")
                return

            # 清理追蹤記錄
            welcome_listener.recent_joins.clear()
            welcome_listener.recent_updates.clear()

            # 檢查最近加入的成員（最近5分鐘）
            from datetime import datetime, timedelta, timezone

            current_time = datetime.now(timezone.utc)
            recent_threshold = current_time - timedelta(minutes=5)

            checked_members = 0
            processed_members = 0

            for member in ctx.guild.members:
                if not member.bot and member.joined_at and member.joined_at > recent_threshold:

                    checked_members += 1
                    logger.info(f"🔍 刷新檢查成員: {member}")

                    # 使用延遲避免大量處理
                    import asyncio

                    await asyncio.sleep(0.1)
                    await welcome_listener._handle_welcome_with_tracking(member, "手動刷新")
                    processed_members += 1

            embed = discord.Embed(title="✅ 歡迎系統已刷新", color=0x00FF00)

            embed.add_field(
                name="🔄 處理結果",
                value=f"檢查成員: {checked_members} 位\n處理成員: {processed_members} 位\n追蹤記錄已清理",
                inline=False,
            )

            embed.add_field(
                name="📋 使用場景",
                value="• Bot RESUME 後事件監聽器異常\n• 懷疑有成員加入但未觸發歡迎\n• 手動重新初始化歡迎系統",
                inline=False,
            )

            await ctx.send(embed=embed)

        except Exception as e:
            logger.error(f"刷新歡迎系統錯誤: {e}")
            await ctx.send(f"❌ 刷新過程中發生錯誤：{str(e)}")

    @welcome_group.command(name="diagnose")
    @commands.has_permissions(manage_guild=True)
    async def welcome_diagnose(self, ctx):
        """診斷歡迎系統問題（檢查權限、Intents、設定等）"""
        try:
            embed = discord.Embed(title="🔍 歡迎系統診斷報告", color=0x3498DB)

            # 1. 檢查 Bot Intents
            intents = ctx.bot.intents
            intents_status = []

            critical_intents = {
                "members": intents.members,
                "guilds": intents.guilds,
                "guild_messages": intents.guild_messages,
            }

            all_intents_ok = True
            for intent_name, enabled in critical_intents.items():
                if enabled:
                    intents_status.append(f"✅ {intent_name}")
                else:
                    intents_status.append(f"❌ {intent_name}")
                    all_intents_ok = False

            embed.add_field(name="🎭 Bot Intents", value="\n".join(intents_status), inline=True)

            # 2. 檢查事件監聽器
            welcome_listener = ctx.bot.get_cog("WelcomeListener")
            listener_status = []

            if welcome_listener:
                listener_status.append("✅ WelcomeListener 已載入")

                # 檢查事件監聽器數量
                member_events = ["on_member_join", "on_member_remove", "on_member_update"]
                for event_name in member_events:
                    listeners = ctx.bot.extra_events.get(event_name, [])
                    if listeners:
                        listener_status.append(f"✅ {event_name}: {len(listeners)} 個")
                    else:
                        listener_status.append(f"❌ {event_name}: 無監聽器")
            else:
                listener_status.append("❌ WelcomeListener 未載入")

            embed.add_field(name="🎧 事件監聽器", value="\n".join(listener_status), inline=True)

            # 3. 檢查 Bot 權限
            bot_member = ctx.guild.get_member(ctx.bot.user.id)
            permissions = bot_member.guild_permissions if bot_member else None

            perm_status = []
            if permissions:
                required_perms = {
                    "view_channel": permissions.view_channel,
                    "send_messages": permissions.send_messages,
                    "manage_roles": permissions.manage_roles,
                    "embed_links": permissions.embed_links,
                }

                for perm_name, has_perm in required_perms.items():
                    if has_perm:
                        perm_status.append(f"✅ {perm_name}")
                    else:
                        perm_status.append(f"❌ {perm_name}")
            else:
                perm_status.append("❌ 無法檢查權限")

            embed.add_field(name="🔐 Bot 權限", value="\n".join(perm_status), inline=True)

            # 4. 檢查歡迎設定
            settings = await self.welcome_dao.get_welcome_settings(ctx.guild.id)
            settings_status = []

            if settings:
                if settings.get("is_enabled"):
                    settings_status.append("✅ 歡迎系統已啟用")
                else:
                    settings_status.append("❌ 歡迎系統已停用")

                if settings.get("welcome_channel_id"):
                    channel = ctx.guild.get_channel(settings["welcome_channel_id"])
                    if channel:
                        settings_status.append(f"✅ 歡迎頻道: {channel.mention}")
                    else:
                        settings_status.append("❌ 歡迎頻道不存在")
                else:
                    settings_status.append("⚠️ 未設定歡迎頻道")

                if settings.get("auto_role_enabled") and settings.get("auto_roles"):
                    settings_status.append("✅ 自動身分組已設定")
                else:
                    settings_status.append("⚠️ 未設定自動身分組")
            else:
                settings_status.append("❌ 未找到歡迎設定")

            embed.add_field(name="⚙️ 歡迎設定", value="\n".join(settings_status), inline=False)

            # 5. 給出建議
            suggestions = []

            if not intents.members:
                suggestions.append(
                    "🚨 **關鍵問題**：需要在 Discord Developer Portal 啟用 `Server Members Intent`"
                )

            if not welcome_listener:
                suggestions.append("🔄 重新載入歡迎監聽器：`!reload welcome_listener`")

            if not settings or not settings.get("is_enabled"):
                suggestions.append("⚙️ 設定歡迎系統：`!welcome setup`")

            if not suggestions and all_intents_ok:
                suggestions.append("✅ 系統配置正常，使用 `!welcome simulate` 測試功能")

            if suggestions:
                embed.add_field(name="💡 建議修復步驟", value="\n".join(suggestions), inline=False)

            # 設定顏色
            if not intents.members or not welcome_listener:
                embed.color = 0xFF0000  # 紅色 - 嚴重問題
            elif not all_intents_ok or not settings:
                embed.color = 0xFFA500  # 橙色 - 警告
            else:
                embed.color = 0x00FF00  # 綠色 - 正常

            await ctx.send(embed=embed)

        except Exception as e:
            logger.error(f"歡迎系統診斷錯誤: {e}")
            await ctx.send(f"❌ 診斷過程中發生錯誤：{str(e)}")

    @welcome_group.command(name="stats")
    @commands.has_permissions(manage_guild=True)
    async def welcome_stats(self, ctx, days: int = 30):
        """查看歡迎統計"""
        try:
            if days < 1 or days > 365:
                await ctx.send("❌ 天數必須在 1-365 之間")
                return

            stats = await self.welcome_manager.get_welcome_statistics(ctx.guild.id, days)

            if not stats:
                await ctx.send("❌ 無法取得統計資料")
                return

            embed = discord.Embed(title=f"📊 歡迎系統統計 (過去 {days} 天)", color=0x3498DB)

            # 基礎統計
            embed.add_field(
                name="📈 成員變化",
                value=f"加入: {stats.get('joins', 0)}\n"
                f"離開: {stats.get('leaves', 0)}\n"
                f"淨增長: {stats.get('net_growth', 0)}",
                inline=True,
            )

            # 功能使用統計
            embed.add_field(
                name="💌 訊息發送",
                value=f"歡迎訊息: {stats.get('welcome_sent', 0)}\n"
                f"私訊發送: {stats.get('dm_sent', 0)}",
                inline=True,
            )

            # 身分組統計
            embed.add_field(
                name="👥 身分組分配",
                value=f"成功分配: {stats.get('roles_assigned', 0)}",
                inline=True,
            )

            # 錯誤統計
            if stats.get("errors", 0) > 0:
                embed.add_field(
                    name="⚠️ 錯誤統計", value=f"錯誤次數: {stats.get('errors', 0)}", inline=True
                )

            embed.set_footer(text=f"總事件數: {stats.get('total_events', 0)}")

            await ctx.send(embed=embed)

        except Exception as e:
            logger.error(f"查看歡迎統計錯誤: {e}")
            await ctx.send("❌ 查看統計時發生錯誤")


async def setup(bot):
    """載入擴展"""
    await bot.add_cog(WelcomeCore(bot))
