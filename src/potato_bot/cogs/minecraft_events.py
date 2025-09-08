"""
Minecraft 活動管理 Discord 指令系統
提供建築比賽、PvP 錦標賽、社群活動等管理功能
"""

from datetime import datetime, timedelta

import discord
from discord.ext import commands

from potato_bot.services.minecraft.event_manager import (
    EventStatus,
    EventType,
    MinecraftEventManager,
)
from potato_shared.logger import logger


class MinecraftEvents(commands.Cog):
    """Minecraft 活動管理指令系統"""

    def __init__(self, bot):
        self.bot = bot
        self.event_manager = MinecraftEventManager(bot)
        self._initialized = False

        # 活動類型中文映射
        self.event_type_names = {
            EventType.BUILD_CONTEST.value: "建築比賽",
            EventType.PVP_TOURNAMENT.value: "PvP 錦標賽",
            EventType.EXPLORATION.value: "探險隊",
            EventType.COMMUNITY.value: "社群活動",
            EventType.CUSTOM.value: "自訂活動",
        }

        # 活動狀態中文映射
        self.status_names = {
            EventStatus.PLANNED.value: "已規劃",
            EventStatus.REGISTRATION.value: "報名中",
            EventStatus.ACTIVE.value: "進行中",
            EventStatus.COMPLETED.value: "已完成",
            EventStatus.CANCELLED.value: "已取消",
        }

    async def cog_load(self):
        """Cog 載入時初始化"""
        if not self._initialized:
            await self.event_manager.initialize()
            self._initialized = True
            logger.info("MinecraftEvents Cog 初始化完成")

    # =============================================================================
    # 活動管理指令
    # =============================================================================

    @commands.hybrid_command(name="event-create", description="建立新的 Minecraft 活動")
    @commands.has_permissions(manage_guild=True)
    async def create_event(
        self,
        ctx,
        title: str,
        event_type: str,
        description: str,
        max_participants: int = 0,
        duration_hours: int = 24,
        registration_hours: int = 12,
    ):
        """建立新活動"""
        try:
            await ctx.defer()

            # 準備活動資料
            start_time = datetime.now() + timedelta(hours=registration_hours)
            end_time = start_time + timedelta(hours=duration_hours)
            registration_end = start_time - timedelta(minutes=30)  # 報名在活動開始前30分鐘結束

            event_data = {
                "title": title,
                "description": description,
                "event_type": event_type,
                "max_participants": max_participants,
                "start_time": start_time,
                "end_time": end_time,
                "registration_end": registration_end,
                "requirements": {},
                "rewards": {},
                "rules": "",
                "location_data": {},
            }

            # 建立活動
            event_id = await self.event_manager.create_event(
                organizer_id=ctx.author.id,
                guild_id=ctx.guild.id,
                event_data=event_data,
            )

            if event_id:
                embed = discord.Embed(
                    title="✅ 活動建立成功！",
                    description=f"**{title}** 已成功建立",
                    color=0x00FF00,
                )

                embed.add_field(
                    name=f"{self.event_manager.get_event_type_emoji(event_type)} 基本資訊",
                    value=f"""
                    **類型**: {self.event_type_names[event_type]}
                    **活動 ID**: `{event_id}`
                    **主辦人**: {ctx.author.mention}
                    **最大參與者**: {max_participants if max_participants > 0 else '無限制'}
                    """,
                    inline=False,
                )

                embed.add_field(
                    name="⏰ 時程安排",
                    value=f"""
                    **報名截止**: <t:{int(registration_end.timestamp())}:F>
                    **活動開始**: <t:{int(start_time.timestamp())}:F>
                    **活動結束**: <t:{int(end_time.timestamp())}:F>
                    """,
                    inline=False,
                )

                embed.add_field(
                    name="📝 描述",
                    value=description[:500] + ("..." if len(description) > 500 else ""),
                    inline=False,
                )

                embed.add_field(
                    name="🎯 下一步",
                    value=f"""
                    使用 `/event open {event_id}` 開放報名
                    使用 `/event edit {event_id}` 編輯活動設定
                    使用 `/event info {event_id}` 查看活動詳情
                    """,
                    inline=False,
                )

                embed.set_footer(text=f"活動 ID: {event_id}")
                embed.timestamp = datetime.now()

                await ctx.followup.send(embed=embed)

                # 記錄活動建立
                logger.info(
                    f"新活動建立 - ID: {event_id}, 標題: {title}, 主辦人: {ctx.author.display_name}"
                )

            else:
                embed = discord.Embed(
                    title="❌ 活動建立失敗",
                    description="建立活動時發生錯誤，請稍後再試",
                    color=0xFF0000,
                )
                await ctx.followup.send(embed=embed)

        except Exception as e:
            logger.error(f"create_event 指令錯誤: {e}")
            embed = discord.Embed(
                title="❌ 錯誤",
                description="建立活動時發生錯誤",
                color=0xFF0000,
            )
            await ctx.followup.send(embed=embed)

    @commands.hybrid_command(name="event-list", description="查看伺服器的所有活動")
    async def list_events(self, ctx):
        """列出伺服器活動"""
        try:
            await ctx.defer()

            events = await self.event_manager.get_active_events(ctx.guild.id)

            if not events:
                embed = discord.Embed(
                    title="📅 伺服器活動",
                    description="目前沒有進行中的活動",
                    color=0xFFFF00,
                )
                await ctx.followup.send(embed=embed)
                return

            embed = discord.Embed(
                title=f"📅 {ctx.guild.name} 的活動清單",
                description=f"共有 {len(events)} 個活動",
                color=0x0099FF,
            )

            for event in events[:10]:  # 最多顯示 10 個活動
                status_emoji = self.event_manager.get_status_emoji(event["status"])
                type_emoji = self.event_manager.get_event_type_emoji(event["event_type"])

                event_info = f"""
                **類型**: {type_emoji} {self.event_type_names.get(event['event_type'], event['event_type'])}
                **狀態**: {status_emoji} {self.status_names.get(event['status'], event['status'])}
                **參與者**: {event['current_participants']}/{event['max_participants'] if event['max_participants'] > 0 else '∞'}
                """

                if event["start_time"]:
                    event_info += f"\n**開始時間**: <t:{int(event['start_time'].timestamp())}:R>"

                embed.add_field(
                    name=f"`{event['id']}` {event['title']}",
                    value=event_info,
                    inline=True,
                )

            if len(events) > 10:
                embed.set_footer(
                    text=f"顯示 10/{len(events)} 個活動，使用 `/event info <ID>` 查看詳細資訊"
                )

            embed.timestamp = datetime.now()
            await ctx.followup.send(embed=embed)

        except Exception as e:
            logger.error(f"list_events 指令錯誤: {e}")
            await ctx.followup.send("❌ 無法獲取活動清單")

    @commands.hybrid_command(name="event-info", description="查看活動詳細資訊")
    async def event_info(self, ctx, event_id: int):
        """顯示活動詳細資訊"""
        try:
            await ctx.defer()

            event = await self.event_manager.get_event(event_id)
            if not event:
                embed = discord.Embed(
                    title="❌ 找不到活動",
                    description=f"活動 ID `{event_id}` 不存在",
                    color=0xFF0000,
                )
                await ctx.followup.send(embed=embed)
                return

            # 檢查活動是否屬於當前伺服器
            if event["guild_id"] != ctx.guild.id:
                embed = discord.Embed(
                    title="❌ 權限不足",
                    description="該活動不屬於此伺服器",
                    color=0xFF0000,
                )
                await ctx.followup.send(embed=embed)
                return

            status_emoji = self.event_manager.get_status_emoji(event["status"])
            type_emoji = self.event_manager.get_event_type_emoji(event["event_type"])

            embed = discord.Embed(
                title=f"{type_emoji} {event['title']}",
                description=event["description"],
                color=self._get_status_color(event["status"]),
            )

            embed.add_field(
                name="📋 基本資訊",
                value=f"""
                **活動 ID**: `{event['id']}`
                **類型**: {self.event_type_names.get(event['event_type'], event['event_type'])}
                **狀態**: {status_emoji} {self.status_names.get(event['status'], event['status'])}
                **主辦人**: <@{event['organizer_id']}>
                """,
                inline=True,
            )

            embed.add_field(
                name="👥 參與資訊",
                value=f"""
                **當前參與者**: {event['current_participants']}
                **最大參與者**: {event['max_participants'] if event['max_participants'] > 0 else '無限制'}
                **可用名額**: {event['max_participants'] - event['current_participants'] if event['max_participants'] > 0 else '無限制'}
                """,
                inline=True,
            )

            embed.add_field(name="\u200b", value="\u200b", inline=True)  # 空欄位用於對齊

            # 時間資訊
            time_info = ""
            if event["registration_end"]:
                time_info += f"**報名截止**: <t:{int(event['registration_end'].timestamp())}:F>\n"
            if event["start_time"]:
                time_info += f"**活動開始**: <t:{int(event['start_time'].timestamp())}:F>\n"
            if event["end_time"]:
                time_info += f"**活動結束**: <t:{int(event['end_time'].timestamp())}:F>\n"

            if time_info:
                embed.add_field(name="⏰ 時程安排", value=time_info, inline=False)

            # 獲取參與者清單
            participants = await self.event_manager.get_event_participants(event_id)
            if participants:
                participant_list = []
                for i, p in enumerate(participants[:10], 1):
                    status_icon = "✅" if p["status"] == "confirmed" else "📝"
                    mc_name = p.get("minecraft_username", "Unknown")
                    participant_list.append(f"{i}. {status_icon} <@{p['discord_id']}> ({mc_name})")

                participant_text = "\n".join(participant_list)
                if len(participants) > 10:
                    participant_text += f"\n... 和其他 {len(participants) - 10} 位參與者"

                embed.add_field(name="👥 參與者列表", value=participant_text, inline=False)

            # 管理操作提示
            if event["status"] in ["planned", "registration"]:
                action_text = f"使用 `/event join {event_id}` 參加活動"
                if event["status"] == "planned":
                    action_text = f"使用 `/event open {event_id}` 開放報名"

                embed.add_field(name="🎯 可執行操作", value=action_text, inline=False)

            embed.set_footer(text=f"建立時間: {event['created_at'].strftime('%Y/%m/%d %H:%M')}")
            embed.timestamp = datetime.now()

            await ctx.followup.send(embed=embed)

        except Exception as e:
            logger.error(f"event_info 指令錯誤: {e}")
            await ctx.followup.send("❌ 無法獲取活動資訊")

    @commands.hybrid_command(name="event-join", description="參加活動")
    async def join_event(self, ctx, event_id: int):
        """參加活動"""
        try:
            await ctx.defer()

            event = await self.event_manager.get_event(event_id)
            if not event:
                embed = discord.Embed(
                    title="❌ 找不到活動",
                    description=f"活動 ID `{event_id}` 不存在",
                    color=0xFF0000,
                )
                await ctx.followup.send(embed=embed)
                return

            # 檢查活動是否屬於當前伺服器
            if event["guild_id"] != ctx.guild.id:
                embed = discord.Embed(
                    title="❌ 權限不足",
                    description="該活動不屬於此伺服器",
                    color=0xFF0000,
                )
                await ctx.followup.send(embed=embed)
                return

            # 檢查活動狀態
            if event["status"] != EventStatus.REGISTRATION.value:
                status_name = self.status_names.get(event["status"], event["status"])
                embed = discord.Embed(
                    title="❌ 無法參加",
                    description=f"活動目前狀態為 `{status_name}`，無法參加",
                    color=0xFF0000,
                )
                await ctx.followup.send(embed=embed)
                return

            # 報名參加
            success = await self.event_manager.register_participant(
                event_id=event_id, discord_id=ctx.author.id
            )

            if success:
                embed = discord.Embed(
                    title="✅ 報名成功！",
                    description=f"已成功報名參加 **{event['title']}**",
                    color=0x00FF00,
                )

                embed.add_field(
                    name="🎮 活動資訊",
                    value=f"""
                    **類型**: {self.event_type_names.get(event['event_type'])}
                    **開始時間**: <t:{int(event['start_time'].timestamp())}:F>
                    **主辦人**: <@{event['organizer_id']}>
                    """,
                    inline=False,
                )

                embed.add_field(
                    name="📝 注意事項",
                    value="""
                    • 請準時參加活動
                    • 活動開始前會收到提醒通知
                    • 使用 `/event leave <ID>` 可以取消報名
                    """,
                    inline=False,
                )

                await ctx.followup.send(embed=embed)

                # 記錄參與
                logger.info(f"玩家 {ctx.author.display_name} 參加活動 {event_id}")

            else:
                embed = discord.Embed(
                    title="❌ 報名失敗",
                    description="可能原因：已經報名過、活動已滿員，或活動不開放報名",
                    color=0xFF0000,
                )
                await ctx.followup.send(embed=embed)

        except Exception as e:
            logger.error(f"join_event 指令錯誤: {e}")
            await ctx.followup.send("❌ 報名過程中發生錯誤")

    @commands.hybrid_command(name="event-leave", description="取消參加活動")
    async def leave_event(self, ctx, event_id: int):
        """取消參加活動"""
        try:
            await ctx.defer()

            success = await self.event_manager.withdraw_participant(
                event_id=event_id, discord_id=ctx.author.id
            )

            if success:
                event = await self.event_manager.get_event(event_id)
                embed = discord.Embed(
                    title="✅ 取消報名成功",
                    description=f"已取消參加 **{event['title'] if event else f'活動 {event_id}'}**",
                    color=0x00FF00,
                )
                await ctx.followup.send(embed=embed)

                logger.info(f"玩家 {ctx.author.display_name} 取消參加活動 {event_id}")

            else:
                embed = discord.Embed(
                    title="❌ 取消失敗",
                    description="可能原因：未報名該活動、活動已開始，或活動不存在",
                    color=0xFF0000,
                )
                await ctx.followup.send(embed=embed)

        except Exception as e:
            logger.error(f"leave_event 指令錯誤: {e}")
            await ctx.followup.send("❌ 取消報名過程中發生錯誤")

    # =============================================================================
    # 活動管理指令 (需要權限)
    # =============================================================================

    @commands.hybrid_command(name="event-open", description="開放活動報名 (需要管理權限)")
    @commands.has_permissions(manage_guild=True)
    async def open_registration(self, ctx, event_id: int):
        """開放活動報名"""
        try:
            await ctx.defer()

            event = await self.event_manager.get_event(event_id)
            if not event:
                embed = discord.Embed(
                    title="❌ 找不到活動",
                    description=f"活動 ID `{event_id}` 不存在",
                    color=0xFF0000,
                )
                await ctx.followup.send(embed=embed)
                return

            if event["guild_id"] != ctx.guild.id:
                embed = discord.Embed(
                    title="❌ 權限不足",
                    description="該活動不屬於此伺服器",
                    color=0xFF0000,
                )
                await ctx.followup.send(embed=embed)
                return

            # 更新活動狀態為報名中
            await self.event_manager.db.execute(
                "UPDATE minecraft_events SET status = 'registration' WHERE id = %s",
                (event_id,),
            )

            embed = discord.Embed(
                title="✅ 報名已開放",
                description=f"**{event['title']}** 現在開放報名！",
                color=0x00FF00,
            )

            embed.add_field(
                name="🎯 活動資訊",
                value=f"""
                **類型**: {self.event_type_names.get(event['event_type'])}
                **最大參與者**: {event['max_participants'] if event['max_participants'] > 0 else '無限制'}
                **報名截止**: <t:{int(event['registration_end'].timestamp())}:F>
                **活動開始**: <t:{int(event['start_time'].timestamp())}:F>
                """,
                inline=False,
            )

            embed.add_field(
                name="📝 如何參加",
                value=f"使用指令 `/event join {event_id}` 參加活動",
                inline=False,
            )

            await ctx.followup.send(embed=embed)

            # 可以在這裡添加公告功能，通知所有成員
            logger.info(f"活動 {event_id} 開放報名 - 操作者: {ctx.author.display_name}")

        except Exception as e:
            logger.error(f"open_registration 指令錯誤: {e}")
            await ctx.followup.send("❌ 開放報名失敗")

    @commands.hybrid_command(name="event-start", description="開始活動 (需要管理權限)")
    @commands.has_permissions(manage_guild=True)
    async def start_event(self, ctx, event_id: int):
        """開始活動"""
        try:
            await ctx.defer()

            event = await self.event_manager.get_event(event_id)
            if not event or event["guild_id"] != ctx.guild.id:
                await ctx.followup.send("❌ 找不到活動或權限不足")
                return

            success = await self.event_manager.start_event(event_id)

            if success:
                embed = discord.Embed(
                    title="🎉 活動開始！",
                    description=f"**{event['title']}** 正式開始！",
                    color=0x00FF00,
                )

                participants = await self.event_manager.get_event_participants(event_id)
                if participants:
                    embed.add_field(
                        name="👥 參與者",
                        value=f"共有 {len(participants)} 位玩家參與",
                        inline=False,
                    )

                await ctx.followup.send(embed=embed)
                logger.info(f"活動 {event_id} 開始 - 操作者: {ctx.author.display_name}")
            else:
                await ctx.followup.send("❌ 開始活動失敗")

        except Exception as e:
            logger.error(f"start_event 指令錯誤: {e}")
            await ctx.followup.send("❌ 開始活動時發生錯誤")

    # =============================================================================
    # 輔助方法
    # =============================================================================

    def _get_status_color(self, status: str) -> int:
        """根據活動狀態取得對應顏色"""
        color_map = {
            "planned": 0x808080,  # 灰色
            "registration": 0x0099FF,  # 藍色
            "active": 0x00FF00,  # 綠色
            "completed": 0x800080,  # 紫色
            "cancelled": 0xFF0000,  # 紅色
        }
        return color_map.get(status, 0x808080)


def setup(bot):
    bot.add_cog(MinecraftEvents(bot))
