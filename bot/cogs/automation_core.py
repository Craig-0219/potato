# bot/cogs/automation_core.py - 進階自動化規則引擎核心 v1.7.0
"""
進階自動化規則引擎核心功能
提供Discord指令介面來管理和執行自動化規則
"""


import discord
from discord import app_commands
from discord.ext import commands

from bot.db.automation_dao import AutomationDAO
from bot.services.automation_engine import (
    TriggerType,
    automation_engine,
)
from bot.utils.embed_builder import EmbedBuilder
from bot.views.automation_views import AutomationView, RuleBuilderModal
from shared.logger import logger


class AutomationCore(commands.Cog):
    """進階自動化規則引擎核心功能"""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.engine = automation_engine
        self.dao = AutomationDAO()
        logger.info("✅ 進階自動化規則引擎核心已初始化")

    # ========== 規則管理指令 ==========

    @app_commands.command(name="automation_list", description="查看自動化規則列表")
    @app_commands.describe(status="篩選規則狀態", trigger_type="篩選觸發類型")
    @app_commands.choices(
        status=[
            app_commands.Choice(name="全部", value="all"),
            app_commands.Choice(name="啟用", value="active"),
            app_commands.Choice(name="草稿", value="draft"),
            app_commands.Choice(name="暫停", value="paused"),
            app_commands.Choice(name="停用", value="disabled"),
        ],
        trigger_type=[
            app_commands.Choice(name="全部", value="all"),
            app_commands.Choice(name="票券創建", value="ticket_created"),
            app_commands.Choice(name="票券關閉", value="ticket_closed"),
            app_commands.Choice(name="用戶加入", value="user_join"),
            app_commands.Choice(name="用戶離開", value="user_leave"),
            app_commands.Choice(name="訊息發送", value="message_sent"),
            app_commands.Choice(name="排程", value="scheduled"),
            app_commands.Choice(name="Webhook", value="webhook"),
        ],
    )
    async def automation_list(
        self,
        interaction: discord.Interaction,
        status: str = "all",
        trigger_type: str = "all",
    ):
        """查看自動化規則列表"""
        try:
            # 檢查權限
            if not interaction.user.guild_permissions.manage_guild:
                await interaction.response.send_message(
                    "❌ 需要管理伺服器權限才能查看自動化規則", ephemeral=True
                )
                return

            await interaction.response.defer(ephemeral=True)

            # 構建查詢參數
            query_status = status if status != "all" else None
            query_trigger = trigger_type if trigger_type != "all" else None

            # 獲取規則列表
            rules, total_count = await self.dao.get_rules(
                guild_id=interaction.guild.id,
                status=query_status,
                trigger_type=query_trigger,
                page=1,
                page_size=20,
            )

            # 創建嵌入式訊息
            embed = EmbedBuilder.build(
                title="🤖 自動化規則列表",
                description=f"伺服器自動化規則管理 - {interaction.guild.name}",
                color=0x9B59B6,
            )

            if not rules:
                embed.add_field(
                    name="📋 規則狀態",
                    value="目前沒有符合條件的自動化規則\n使用 `/automation_create` 創建新規則",
                    inline=False,
                )
            else:
                # 按狀態分組顯示規則
                status_groups = {}
                for rule in rules:
                    rule_status = rule["status"]
                    if rule_status not in status_groups:
                        status_groups[rule_status] = []
                    status_groups[rule_status].append(rule)

                status_emojis = {
                    "active": "🟢",
                    "draft": "⚪",
                    "paused": "🟡",
                    "disabled": "🔴",
                    "error": "❌",
                }

                for rule_status, status_rules in status_groups.items():
                    emoji = status_emojis.get(rule_status, "⚪")
                    status_name = {
                        "active": "啟用",
                        "draft": "草稿",
                        "paused": "暫停",
                        "disabled": "停用",
                        "error": "錯誤",
                    }.get(rule_status, rule_status)

                    rule_list = []
                    for rule in status_rules[:5]:  # 限制顯示5個
                        trigger_name = self._get_trigger_display_name(rule["trigger_type"])
                        rule_list.append(
                            f"• **{rule['name']}** (優先級: {rule['priority']})\n"
                            f"  觸發: {trigger_name} | 執行: {rule['execution_count']}次"
                        )

                    embed.add_field(
                        name=f"{emoji} {status_name} ({len(status_rules)})",
                        value="\n".join(rule_list) if rule_list else "無規則",
                        inline=False,
                    )

            # 添加統計資訊
            embed.add_field(
                name="📊 統計資訊",
                value=f"總規則數: {total_count}\n篩選結果: {len(rules)}",
                inline=True,
            )

            embed.set_footer(text=f"使用 /automation_detail [規則ID] 查看詳細資訊")

            # 創建互動視圖
            view = AutomationView(interaction.user.id, rules[:10])  # 限制10個規則的操作按鈕

            await interaction.followup.send(embed=embed, view=view, ephemeral=True)

        except Exception as e:
            logger.error(f"查看自動化規則列表失敗: {e}")
            await interaction.followup.send(f"❌ 獲取規則列表失敗: {str(e)}", ephemeral=True)

    @app_commands.command(name="automation_create", description="創建新的自動化規則")
    @app_commands.describe(name="規則名稱", description="規則描述")
    async def automation_create(
        self,
        interaction: discord.Interaction,
        name: str,
        description: str = "",
    ):
        """創建新的自動化規則"""
        try:
            # 檢查權限
            if not interaction.user.guild_permissions.manage_guild:
                await interaction.response.send_message(
                    "❌ 需要管理伺服器權限才能創建自動化規則", ephemeral=True
                )
                return

            # 創建規則建構器模態框
            modal = RuleBuilderModal(name, description, interaction.guild.id, interaction.user.id)
            await interaction.response.send_modal(modal)

        except Exception as e:
            logger.error(f"創建自動化規則失敗: {e}")
            await interaction.response.send_message(f"❌ 創建規則失敗: {str(e)}", ephemeral=True)

    @app_commands.command(name="automation_detail", description="查看自動化規則詳細資訊")
    @app_commands.describe(rule_id="規則ID")
    async def automation_detail(self, interaction: discord.Interaction, rule_id: str):
        """查看自動化規則詳細資訊"""
        try:
            # 檢查權限
            if not interaction.user.guild_permissions.manage_guild:
                await interaction.response.send_message(
                    "❌ 需要管理伺服器權限才能查看規則詳情", ephemeral=True
                )
                return

            await interaction.response.defer(ephemeral=True)

            # 獲取規則詳情
            rule = await self.dao.get_rule(rule_id)
            if not rule:
                await interaction.followup.send("❌ 找不到指定的規則", ephemeral=True)
                return

            # 檢查權限（只能查看同伺服器的規則）
            if rule["guild_id"] != interaction.guild.id:
                await interaction.followup.send("❌ 無權查看此規則", ephemeral=True)
                return

            # 創建詳細資訊嵌入式訊息
            embed = EmbedBuilder.build(
                title=f"🤖 {rule['name']}",
                description=rule["description"] or "無描述",
                color=0x9B59B6,
            )

            # 基本資訊
            status_emoji = {
                "active": "🟢",
                "draft": "⚪",
                "paused": "🟡",
                "disabled": "🔴",
                "error": "❌",
            }.get(rule["status"], "⚪")
            status_name = {
                "active": "啟用",
                "draft": "草稿",
                "paused": "暫停",
                "disabled": "停用",
                "error": "錯誤",
            }.get(rule["status"], rule["status"])

            embed.add_field(
                name="📋 基本資訊",
                value=f"狀態: {status_emoji} {status_name}\n"
                f"優先級: {rule['priority']}/10\n"
                f"創建時間: {rule['created_at'].strftime('%Y-%m-%d %H:%M')}\n"
                f"更新時間: {rule['updated_at'].strftime('%Y-%m-%d %H:%M')}",
                inline=True,
            )

            # 觸發器資訊
            trigger_name = self._get_trigger_display_name(rule["trigger_type"])
            conditions_text = ""
            if rule["trigger_conditions"]:
                conditions_text = "\n".join(
                    [
                        f"• {cond['field']} {cond['operator']} {cond['value']}"
                        for cond in rule["trigger_conditions"][:3]
                    ]
                )
                if len(rule["trigger_conditions"]) > 3:
                    conditions_text += f"\n...還有 {len(rule['trigger_conditions']) - 3} 個條件"

            embed.add_field(
                name="⚡ 觸發器",
                value=f"類型: {trigger_name}\n"
                f"冷卻時間: {rule['cooldown_seconds']}秒\n"
                f"條件: {conditions_text if conditions_text else '無條件'}",
                inline=True,
            )

            # 動作資訊
            actions_text = ""
            if rule["actions"]:
                actions_text = "\n".join(
                    [
                        f"• {self._get_action_display_name(action['type'])}"
                        for action in rule["actions"][:3]
                    ]
                )
                if len(rule["actions"]) > 3:
                    actions_text += f"\n...還有 {len(rule['actions']) - 3} 個動作"

            embed.add_field(
                name="🎯 動作",
                value=f"動作數: {len(rule['actions'])}\n{actions_text}",
                inline=True,
            )

            # 執行統計
            success_rate = 0
            if rule["execution_count"] > 0:
                success_rate = (rule["success_count"] / rule["execution_count"]) * 100

            last_executed = "從未執行"
            if rule["last_executed"]:
                last_executed = rule["last_executed"].strftime("%Y-%m-%d %H:%M")

            embed.add_field(
                name="📊 執行統計",
                value=f"總執行: {rule['execution_count']}\n"
                f"成功: {rule['success_count']}\n"
                f"失敗: {rule['failure_count']}\n"
                f"成功率: {success_rate:.1f}%\n"
                f"最後執行: {last_executed}",
                inline=False,
            )

            # 標籤
            if rule["tags"]:
                embed.add_field(
                    name="🏷️ 標籤",
                    value=" | ".join(f"`{tag}`" for tag in rule["tags"]),
                    inline=False,
                )

            embed.set_footer(text=f"規則ID: {rule['id']}")

            await interaction.followup.send(embed=embed, ephemeral=True)

        except Exception as e:
            logger.error(f"查看規則詳情失敗: {e}")
            await interaction.followup.send(f"❌ 獲取規則詳情失敗: {str(e)}", ephemeral=True)

    @app_commands.command(name="automation_toggle", description="啟用/停用自動化規則")
    @app_commands.describe(rule_id="規則ID", status="新狀態")
    @app_commands.choices(
        status=[
            app_commands.Choice(name="啟用", value="active"),
            app_commands.Choice(name="暫停", value="paused"),
            app_commands.Choice(name="停用", value="disabled"),
        ]
    )
    async def automation_toggle(self, interaction: discord.Interaction, rule_id: str, status: str):
        """啟用/停用自動化規則"""
        try:
            # 檢查權限
            if not interaction.user.guild_permissions.manage_guild:
                await interaction.response.send_message(
                    "❌ 需要管理伺服器權限才能管理規則狀態", ephemeral=True
                )
                return

            await interaction.response.defer(ephemeral=True)

            # 獲取規則
            rule = await self.dao.get_rule(rule_id)
            if not rule or rule["guild_id"] != interaction.guild.id:
                await interaction.followup.send("❌ 找不到指定的規則", ephemeral=True)
                return

            # 更新狀態
            success = await self.dao.update_rule(rule_id, {"status": status}, interaction.user.id)

            if success:
                # 同步更新引擎中的規則
                engine_rule = await self.engine.get_rule(rule_id)
                if engine_rule:
                    await self.engine.update_rule(rule_id, {"status": status})

                status_names = {
                    "active": "啟用",
                    "paused": "暫停",
                    "disabled": "停用",
                }
                status_name = status_names.get(status, status)

                embed = EmbedBuilder.build(
                    title="✅ 規則狀態已更新",
                    description=f"規則 **{rule['name']}** 已{status_name}",
                    color=0x2ECC71,
                )

                await interaction.followup.send(embed=embed, ephemeral=True)
            else:
                await interaction.followup.send("❌ 更新規則狀態失敗", ephemeral=True)

        except Exception as e:
            logger.error(f"切換規則狀態失敗: {e}")
            await interaction.followup.send(f"❌ 操作失敗: {str(e)}", ephemeral=True)

    # ========== 執行記錄指令 ==========

    @app_commands.command(name="automation_history", description="查看自動化執行記錄")
    @app_commands.describe(rule_id="規則ID（可選）", days="查看天數")
    async def automation_history(
        self,
        interaction: discord.Interaction,
        rule_id: str = None,
        days: int = 7,
    ):
        """查看自動化執行記錄"""
        try:
            # 檢查權限
            if not interaction.user.guild_permissions.manage_guild:
                await interaction.response.send_message(
                    "❌ 需要管理伺服器權限才能查看執行記錄", ephemeral=True
                )
                return

            if not 1 <= days <= 30:
                await interaction.response.send_message("❌ 天數必須在1-30之間", ephemeral=True)
                return

            await interaction.response.defer(ephemeral=True)

            # 獲取執行記錄
            executions, total_count = await self.dao.get_executions(
                rule_id=rule_id,
                guild_id=interaction.guild.id,
                days=days,
                page=1,
                page_size=20,
            )

            # 創建嵌入式訊息
            title = "📜 自動化執行記錄"
            if rule_id:
                rule = await self.dao.get_rule(rule_id)
                if rule:
                    title += f" - {rule['name']}"

            embed = EmbedBuilder.build(
                title=title,
                description=f"最近 {days} 天的執行記錄",
                color=0x3498DB,
            )

            if not executions:
                embed.add_field(
                    name="📋 執行狀態",
                    value="在指定時間範圍內沒有執行記錄",
                    inline=False,
                )
            else:
                # 統計資訊
                success_count = len([e for e in executions if e["success"]])
                failure_count = len([e for e in executions if not e["success"]])
                success_rate = (success_count / len(executions) * 100) if executions else 0

                embed.add_field(
                    name="📊 執行統計",
                    value=f"總執行: {total_count}\n"
                    f"成功: {success_count}\n"
                    f"失敗: {failure_count}\n"
                    f"成功率: {success_rate:.1f}%",
                    inline=True,
                )

                # 最近執行記錄
                recent_executions = []
                for execution in executions[:10]:
                    status_emoji = "✅" if execution["success"] else "❌"
                    time_str = execution["started_at"].strftime("%m-%d %H:%M")
                    exec_time = execution["execution_time"]

                    recent_executions.append(
                        f"{status_emoji} **{execution['rule_name']}**\n"
                        f"時間: {time_str} | 耗時: {exec_time:.2f}s"
                    )

                embed.add_field(
                    name="🕐 最近執行",
                    value="\n\n".join(recent_executions),
                    inline=False,
                )

            embed.set_footer(text=f"共 {total_count} 條記錄 | 顯示前 {min(20, len(executions))} 條")

            await interaction.followup.send(embed=embed, ephemeral=True)

        except Exception as e:
            logger.error(f"查看執行記錄失敗: {e}")
            await interaction.followup.send(f"❌ 獲取執行記錄失敗: {str(e)}", ephemeral=True)

    @app_commands.command(name="automation_stats", description="查看自動化統計資訊")
    @app_commands.describe(days="統計天數")
    async def automation_stats(self, interaction: discord.Interaction, days: int = 30):
        """查看自動化統計資訊"""
        try:
            # 檢查權限
            if not interaction.user.guild_permissions.manage_guild:
                await interaction.response.send_message(
                    "❌ 需要管理伺服器權限才能查看統計資訊", ephemeral=True
                )
                return

            if not 1 <= days <= 365:
                await interaction.response.send_message("❌ 天數必須在1-365之間", ephemeral=True)
                return

            await interaction.response.defer(ephemeral=True)

            # 獲取統計資訊
            stats = await self.dao.get_guild_automation_statistics(interaction.guild.id, days)

            # 創建嵌入式訊息
            embed = EmbedBuilder.build(
                title="📊 自動化統計資訊",
                description=f"伺服器自動化系統統計 - 最近 {days} 天",
                color=0x9B59B6,
            )

            # 基本統計
            embed.add_field(
                name="📋 規則統計",
                value=f"總規則數: {stats.get('total_rules', 0)}\n"
                f"啟用規則: {stats.get('active_rules', 0)}\n"
                f"啟用率: {(stats.get('active_rules', 0) / max(stats.get('total_rules', 1), 1) * 100):.1f}%",
                inline=True,
            )

            # 執行統計
            embed.add_field(
                name="⚡ 執行統計",
                value=f"總執行: {stats.get('total_executions', 0)}\n"
                f"成功: {stats.get('success_count', 0)}\n"
                f"失敗: {stats.get('failure_count', 0)}\n"
                f"成功率: {stats.get('success_rate', 0):.1f}%\n"
                f"平均耗時: {stats.get('avg_execution_time', 0):.2f}s",
                inline=True,
            )

            # 觸發類型分佈
            if stats.get("trigger_distribution"):
                trigger_text = []
                for trigger in stats["trigger_distribution"][:5]:
                    trigger_name = self._get_trigger_display_name(trigger["type"])
                    trigger_text.append(f"• {trigger_name}: {trigger['count']}")

                embed.add_field(
                    name="🎯 觸發類型分佈",
                    value="\n".join(trigger_text),
                    inline=True,
                )

            # 最活躍規則
            if stats.get("top_rules"):
                top_rules_text = []
                for rule in stats["top_rules"][:5]:
                    last_exec = "從未"
                    if rule["last_executed"]:
                        last_exec = rule["last_executed"].strftime("%m-%d")

                    top_rules_text.append(
                        f"• {rule['name']}: {rule['execution_count']}次 (最後: {last_exec})"
                    )

                embed.add_field(
                    name="🏆 最活躍規則",
                    value="\n".join(top_rules_text),
                    inline=False,
                )

            embed.set_footer(text=f"統計期間: {days} 天 | 數據實時更新")

            await interaction.followup.send(embed=embed, ephemeral=True)

        except Exception as e:
            logger.error(f"查看統計資訊失敗: {e}")
            await interaction.followup.send(f"❌ 獲取統計資訊失敗: {str(e)}", ephemeral=True)

    # ========== 輔助方法 ==========

    def _get_trigger_display_name(self, trigger_type: str) -> str:
        """獲取觸發類型顯示名稱"""
        names = {
            "ticket_created": "票券創建",
            "ticket_closed": "票券關閉",
            "ticket_updated": "票券更新",
            "user_join": "用戶加入",
            "user_leave": "用戶離開",
            "message_sent": "訊息發送",
            "reaction_added": "表情回應",
            "scheduled": "定時排程",
            "webhook": "Webhook",
            "custom": "自定義",
        }
        return names.get(trigger_type, trigger_type)

    def _get_action_display_name(self, action_type: str) -> str:
        """獲取動作類型顯示名稱"""
        names = {
            "send_message": "發送訊息",
            "assign_role": "分配角色",
            "remove_role": "移除角色",
            "send_dm": "發送私訊",
            "create_channel": "創建頻道",
            "delete_channel": "刪除頻道",
            "move_ticket": "移動票券",
            "close_ticket": "關閉票券",
            "send_webhook": "發送Webhook",
            "execute_script": "執行腳本",
            "update_database": "更新資料庫",
            "send_email": "發送郵件",
        }
        return names.get(action_type, action_type)

    # ========== 事件監聽器 ==========

    @commands.Cog.listener()
    async def on_member_join(self, member):
        """用戶加入事件"""
        try:
            event_data = {
                "guild_id": member.guild.id,
                "user_id": member.id,
                "user": {
                    "id": member.id,
                    "name": member.name,
                    "display_name": member.display_name,
                    "joined_at": (member.joined_at.isoformat() if member.joined_at else None),
                },
            }

            # 處理事件
            await self.engine.process_event(TriggerType.USER_JOIN, event_data)

        except Exception as e:
            logger.error(f"處理用戶加入事件失敗: {e}")

    @commands.Cog.listener()
    async def on_member_remove(self, member):
        """用戶離開事件"""
        try:
            event_data = {
                "guild_id": member.guild.id,
                "user_id": member.id,
                "user": {
                    "id": member.id,
                    "name": member.name,
                    "display_name": member.display_name,
                },
            }

            # 處理事件
            await self.engine.process_event(TriggerType.USER_LEAVE, event_data)

        except Exception as e:
            logger.error(f"處理用戶離開事件失敗: {e}")

    @commands.Cog.listener()
    async def on_message(self, message):
        """訊息發送事件"""
        try:
            # 忽略機器人訊息
            if message.author.bot:
                return

            event_data = {
                "guild_id": message.guild.id if message.guild else None,
                "channel_id": message.channel.id,
                "message_id": message.id,
                "user_id": message.author.id,
                "message": {
                    "content": message.content,
                    "author": {
                        "id": message.author.id,
                        "name": message.author.name,
                        "display_name": message.author.display_name,
                    },
                    "channel": {
                        "id": message.channel.id,
                        "name": getattr(message.channel, "name", "dm"),
                    },
                },
            }

            # 處理事件
            if message.guild:
                await self.engine.process_event(TriggerType.MESSAGE_SENT, event_data)

        except Exception as e:
            logger.error(f"處理訊息事件失敗: {e}")

    # ========== 錯誤處理 ==========

    async def cog_app_command_error(
        self,
        interaction: discord.Interaction,
        error: app_commands.AppCommandError,
    ):
        """處理應用指令錯誤"""
        logger.error(f"自動化指令錯誤: {error}")

        if not interaction.response.is_done():
            await interaction.response.send_message(
                "❌ 指令執行時發生錯誤，請稍後再試", ephemeral=True
            )
        else:
            await interaction.followup.send("❌ 操作失敗，請檢查系統狀態", ephemeral=True)


async def setup(bot):
    await bot.add_cog(AutomationCore(bot))
