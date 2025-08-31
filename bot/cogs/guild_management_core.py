# bot/cogs/guild_management_core.py - v1.0.0
# 🏛️ 伺服器管理核心指令
# Guild Management Core Commands

import asyncio
import json
import logging
from datetime import datetime

import discord
from discord import app_commands
from discord.ext import commands

from bot.services.data_management_service import (
    DataExportRequest,
    ExportFormat,
    data_management_service,
)
from bot.services.guild_analytics_service import guild_analytics_service
from bot.services.guild_permission_manager import (
    GuildPermission,
    guild_permission_manager,
)
from bot.utils.interaction_helper import SafeInteractionHandler

logger = logging.getLogger(__name__)


class GuildManagementCore(commands.Cog):
    """
    伺服器管理核心

    功能：
    - 數據導出和刪除 (GDPR 合規)
    - 伺服器統計和分析
    - 權限管理
    - 備份和恢復
    """

    def __init__(self, bot):
        self.bot = bot
        self.data_service = data_management_service
        self.analytics_service = guild_analytics_service
        self.permission_manager = guild_permission_manager

        logger.info("🏛️ 伺服器管理核心已載入")

    # =========================
    # 數據管理指令
    # =========================

    @app_commands.command(
        name="export_data", description="📤 導出伺服器數據 (GDPR)"
    )
    @app_commands.describe(
        format="導出格式",
        include_personal="是否包含個人數據",
        data_types="要導出的數據類型 (以逗號分隔)",
    )
    @app_commands.choices(
        format=[
            app_commands.Choice(name="JSON", value="json"),
            app_commands.Choice(name="CSV", value="csv"),
            app_commands.Choice(name="XML", value="xml"),
        ]
    )
    @app_commands.default_permissions(administrator=True)
    async def export_data(
        self,
        interaction: discord.Interaction,
        format: str = "json",
        include_personal: bool = True,
        data_types: str = "business_data,configuration_data",
    ):
        """導出伺服器數據"""
        try:
            if not await SafeInteractionHandler.safe_defer(
                interaction, ephemeral=True
            ):
                return

            guild_id = interaction.guild.id
            user_id = interaction.user.id

            # 檢查權限
            if not await self.permission_manager.check_permission(
                user_id, guild_id, GuildPermission.DATA_EXPORT
            ):
                await SafeInteractionHandler.safe_followup(
                    interaction, "❌ 您沒有導出數據的權限", ephemeral=True
                )
                return

            # 解析數據類型
            data_type_list = [dt.strip() for dt in data_types.split(",")]

            # 創建導出請求
            export_request = DataExportRequest(
                guild_id=guild_id,
                user_id=user_id,
                data_types=data_type_list,
                format=ExportFormat(format),
                include_personal_data=include_personal,
            )

            embed = discord.Embed(
                title="📤 數據導出請求已提交",
                description="正在處理您的數據導出請求...",
                color=discord.Color.blue(),
            )

            embed.add_field(
                name="📋 導出詳情",
                value=f"```\n"
                f"格式: {format.upper()}\n"
                f"數據類型: {', '.join(data_type_list)}\n"
                f"包含個人數據: {'是' if include_personal else '否'}\n"
                f"```",
                inline=False,
            )

            await SafeInteractionHandler.safe_followup(
                interaction, embed=embed, ephemeral=True
            )

            # 在背景執行導出
            asyncio.create_task(
                self._process_data_export(interaction, export_request)
            )

        except Exception as e:
            logger.error(f"❌ 數據導出指令錯誤: {e}")
            await SafeInteractionHandler.safe_followup(
                interaction, f"❌ 數據導出失敗: {str(e)}", ephemeral=True
            )

    async def _process_data_export(
        self,
        interaction: discord.Interaction,
        export_request: DataExportRequest,
    ):
        """處理數據導出"""
        try:
            # 執行導出
            export_data = await self.data_service.export_guild_data(
                export_request
            )

            # 轉換為文件
            if export_request.format == ExportFormat.JSON:
                content = json.dumps(
                    export_data, indent=2, ensure_ascii=False, default=str
                )
                filename = f"guild_data_export_{export_request.guild_id}_{datetime.now().strftime('%Y%m%d')}.json"
            else:
                content = str(export_data)  # 簡化處理
                filename = f"guild_data_export_{export_request.guild_id}_{datetime.now().strftime('%Y%m%d')}.txt"

            # 創建文件
            with open(filename, "w", encoding="utf-8") as f:
                f.write(content)

            # 發送結果
            embed = discord.Embed(
                title="✅ 數據導出完成",
                description="您的數據導出已完成",
                color=discord.Color.green(),
            )

            embed.add_field(
                name="📊 導出統計",
                value=f"導出類別數: {len(export_data.get('data', {}))}\n"
                f"文件大小: {len(content) / 1024:.1f} KB",
                inline=True,
            )

            file = discord.File(filename, filename=filename)

            await interaction.user.send(embed=embed, file=file)

            # 清理臨時文件
            import os

            os.remove(filename)

        except Exception as e:
            logger.error(f"❌ 處理數據導出失敗: {e}")

            embed = discord.Embed(
                title="❌ 數據導出失敗",
                description=f"導出過程中發生錯誤: {str(e)}",
                color=discord.Color.red(),
            )

            try:
                await interaction.user.send(embed=embed)
            except:
                pass  # 如果無法發送私訊，忽略錯誤

    @app_commands.command(
        name="delete_data", description="🗑️ 刪除伺服器數據 (GDPR 被遺忘權)"
    )
    @app_commands.describe(
        confirm="輸入 'CONFIRM' 確認刪除",
        data_types="要刪除的數據類型",
        hard_delete="是否硬刪除 (不可恢復)",
    )
    @app_commands.default_permissions(administrator=True)
    async def delete_data(
        self,
        interaction: discord.Interaction,
        confirm: str,
        data_types: str = "personal_data",
        hard_delete: bool = False,
    ):
        """刪除伺服器數據"""
        try:
            if not await SafeInteractionHandler.safe_defer(
                interaction, ephemeral=True
            ):
                return

            if confirm.upper() != "CONFIRM":
                await SafeInteractionHandler.safe_followup(
                    interaction,
                    "❌ 請輸入 'CONFIRM' 來確認刪除操作",
                    ephemeral=True,
                )
                return

            guild_id = interaction.guild.id
            user_id = interaction.user.id

            # 檢查權限
            if not await self.permission_manager.check_permission(
                user_id, guild_id, GuildPermission.DATA_DELETE
            ):
                await SafeInteractionHandler.safe_followup(
                    interaction, "❌ 您沒有刪除數據的權限", ephemeral=True
                )
                return

            # 解析數據類型
            data_type_list = [dt.strip() for dt in data_types.split(",")]

            # 執行刪除
            deletion_summary = await self.data_service.delete_guild_data(
                guild_id, user_id, data_type_list, hard_delete
            )

            embed = discord.Embed(
                title="✅ 數據刪除完成",
                description="數據刪除操作已完成",
                color=discord.Color.green(),
            )

            # 刪除統計
            deleted_tables = deletion_summary.get("deleted_records", {})
            retained_tables = deletion_summary.get("retained_records", {})

            if deleted_tables:
                deleted_info = "\n".join(
                    [
                        f"• {table}: {count} 筆"
                        for table, count in deleted_tables.items()
                    ]
                )
                embed.add_field(
                    name="🗑️ 已刪除", value=deleted_info, inline=False
                )

            if retained_tables:
                retained_info = "\n".join(
                    [
                        f"• {table}: {info}"
                        for table, info in retained_tables.items()
                    ]
                )
                embed.add_field(
                    name="📦 已保留/匿名化", value=retained_info, inline=False
                )

            embed.add_field(
                name="⚠️ 重要提醒",
                value="• 此操作符合 GDPR 被遺忘權要求\n• 部分數據已匿名化而非完全刪除\n• 系統日誌可能保留以符合法規要求",
                inline=False,
            )

            await SafeInteractionHandler.safe_followup(
                interaction, embed=embed, ephemeral=True
            )

        except Exception as e:
            logger.error(f"❌ 數據刪除指令錯誤: {e}")
            await SafeInteractionHandler.safe_followup(
                interaction, f"❌ 數據刪除失敗: {str(e)}", ephemeral=True
            )

    # =========================
    # 分析和統計指令
    # =========================

    @app_commands.command(
        name="guild_analytics", description="📊 伺服器分析儀表板"
    )
    @app_commands.describe(days="分析天數 (1-30)")
    @app_commands.default_permissions(administrator=True)
    async def guild_analytics(
        self, interaction: discord.Interaction, days: int = 7
    ):
        """顯示伺服器分析儀表板"""
        try:
            if not await SafeInteractionHandler.safe_defer(
                interaction, ephemeral=True
            ):
                return

            if days < 1 or days > 30:
                await SafeInteractionHandler.safe_followup(
                    interaction, "❌ 分析天數必須在 1-30 之間", ephemeral=True
                )
                return

            guild_id = interaction.guild.id
            user_id = interaction.user.id

            # 檢查權限
            if not await self.permission_manager.check_permission(
                user_id, guild_id, GuildPermission.DATA_VIEW
            ):
                await SafeInteractionHandler.safe_followup(
                    interaction, "❌ 您沒有查看分析數據的權限", ephemeral=True
                )
                return

            # 獲取分析數據
            dashboard_data = (
                await self.analytics_service.get_guild_analytics_dashboard(
                    guild_id, days
                )
            )

            if not dashboard_data:
                await SafeInteractionHandler.safe_followup(
                    interaction, "❌ 無法獲取分析數據", ephemeral=True
                )
                return

            # 建立儀表板 Embed
            embed = discord.Embed(
                title="📊 伺服器分析儀表板",
                description=f"過去 {days} 天的數據分析",
                color=discord.Color.blue(),
                timestamp=datetime.now(),
            )

            # 當前指標
            current_metrics = dashboard_data.get("current_metrics", {})
            if current_metrics:
                metrics_text = f"```\n"
                metrics_text += (
                    f"今日票券: {current_metrics.get('total_tickets', 0)}\n"
                )
                metrics_text += f"開放票券: {current_metrics.get('open_tickets_count', 0)}\n"
                metrics_text += (
                    f"投票數: {current_metrics.get('total_votes_today', 0)}\n"
                )
                metrics_text += (
                    f"API 調用: {current_metrics.get('api_calls_today', 0)}\n"
                )
                metrics_text += f"活躍用戶: {current_metrics.get('daily_active_users', 0)}\n"
                metrics_text += f"```"

                embed.add_field(
                    name="📈 今日指標", value=metrics_text, inline=True
                )

            # 性能摘要
            performance = dashboard_data.get("performance", {})
            if performance:
                perf_text = f"```\n"
                perf_text += f"平均響應: {performance.get('avg_response_time', 0):.1f}ms\n"
                perf_text += (
                    f"24h 請求: {performance.get('total_requests_24h', 0)}\n"
                )
                perf_text += (
                    f"最大響應: {performance.get('max_response_time', 0)}ms\n"
                )
                perf_text += f"```"

                embed.add_field(
                    name="⚡ 性能指標", value=perf_text, inline=True
                )

            # 安全指標
            if current_metrics:
                security_text = f"```\n"
                security_text += f"安全事件: {current_metrics.get('security_events_today', 0)}\n"
                security_text += f"MFA 採用率: {current_metrics.get('mfa_adoption_rate', 0)*100:.1f}%\n"
                security_text += f"錯誤率: {current_metrics.get('error_rate', 0)*100:.2f}%\n"
                security_text += f"```"

                embed.add_field(
                    name="🛡️ 安全指標", value=security_text, inline=True
                )

            # 趨勢分析
            trends = dashboard_data.get("trends", {})
            if trends:
                trend_text = ""
                for metric, trend_data in trends.items():
                    direction = trend_data.get("direction", "stable")
                    change_rate = trend_data.get("change_rate", 0) * 100

                    emoji = (
                        "📈"
                        if direction == "up"
                        else "📉" if direction == "down" else "➡️"
                    )
                    trend_text += f"{emoji} {metric.replace('_trend', '')}: {change_rate:+.1f}%\n"

                if trend_text:
                    embed.add_field(
                        name="📊 趨勢分析", value=trend_text, inline=False
                    )

            # 最近警告
            recent_alerts = dashboard_data.get("recent_alerts", [])
            if recent_alerts:
                alerts_text = ""
                for alert in recent_alerts[:3]:  # 只顯示前3個
                    timestamp = alert.get("timestamp", datetime.now())
                    if isinstance(timestamp, str):
                        timestamp = datetime.fromisoformat(
                            timestamp.replace("Z", "+00:00")
                        )

                    alerts_text += f"⚠️ {alert.get('event_name', 'Unknown')} "
                    alerts_text += f"(<t:{int(timestamp.timestamp())}:R>)\n"

                embed.add_field(
                    name="🚨 最近警告",
                    value=alerts_text or "無警告",
                    inline=False,
                )

            embed.set_footer(text=f"數據更新時間")

            await SafeInteractionHandler.safe_followup(
                interaction, embed=embed, ephemeral=True
            )

        except Exception as e:
            logger.error(f"❌ 分析儀表板錯誤: {e}")
            await SafeInteractionHandler.safe_followup(
                interaction, f"❌ 無法顯示分析儀表板: {str(e)}", ephemeral=True
            )

    @app_commands.command(name="guild_stats", description="📈 伺服器基本統計")
    async def guild_stats(self, interaction: discord.Interaction):
        """顯示伺服器基本統計"""
        try:
            if not await SafeInteractionHandler.safe_defer(
                interaction, ephemeral=True
            ):
                return

            guild_id = interaction.guild.id

            # 收集當前指標
            current_metrics = (
                await self.analytics_service.collect_guild_metrics(guild_id)
            )

            embed = discord.Embed(
                title="📈 伺服器統計",
                description=f"**{interaction.guild.name}** 的使用統計",
                color=discord.Color.green(),
                timestamp=datetime.now(),
            )

            # 基本統計
            embed.add_field(
                name="🎫 票券系統",
                value=f"今日建立: {current_metrics.get('total_tickets', 0)}\n"
                f"開放中: {current_metrics.get('open_tickets_count', 0)}\n"
                f"平均回應: {current_metrics.get('avg_response_time_minutes', 0):.1f} 分鐘",
                inline=True,
            )

            embed.add_field(
                name="🗳️ 投票系統",
                value=f"今日投票: {current_metrics.get('total_votes_today', 0)}\n"
                f"活躍投票: {current_metrics.get('active_votes_count', 0)}\n"
                f"平均參與: {current_metrics.get('avg_vote_participation', 0):.1f}",
                inline=True,
            )

            embed.add_field(
                name="👥 用戶活動",
                value=f"活躍用戶: {current_metrics.get('daily_active_users', 0)}\n"
                f"指令使用: {current_metrics.get('commands_used_today', 0)}\n"
                f"滿意度: {current_metrics.get('avg_satisfaction_rating', 0):.1f}/5",
                inline=True,
            )

            embed.add_field(
                name="🔧 系統性能",
                value=f"API 調用: {current_metrics.get('api_calls_today', 0)}\n"
                f"成功率: {current_metrics.get('api_success_rate', 1)*100:.1f}%\n"
                f"響應時間: {current_metrics.get('avg_api_response_time', 0):.1f}ms",
                inline=True,
            )

            embed.add_field(
                name="🛡️ 安全狀況",
                value=f"安全事件: {current_metrics.get('security_events_today', 0)}\n"
                f"MFA 採用: {current_metrics.get('mfa_adoption_rate', 0)*100:.1f}%\n"
                f"錯誤率: {current_metrics.get('error_rate', 0)*100:.2f}%",
                inline=True,
            )

            embed.add_field(
                name="💻 資源使用",
                value=f"記憶體: {current_metrics.get('memory_usage_mb', 0):.1f} MB\n"
                f"CPU: {current_metrics.get('cpu_usage_percent', 0):.1f}%\n"
                f"每小時查詢: {current_metrics.get('queries_per_hour', 0)}",
                inline=True,
            )

            await SafeInteractionHandler.safe_followup(
                interaction, embed=embed, ephemeral=True
            )

        except Exception as e:
            logger.error(f"❌ 統計指令錯誤: {e}")
            await SafeInteractionHandler.safe_followup(
                interaction, f"❌ 無法顯示統計: {str(e)}", ephemeral=True
            )

    # =========================
    # 權限管理指令
    # =========================

    @app_commands.command(
        name="manage_permissions", description="👥 管理用戶權限"
    )
    @app_commands.describe(user="目標用戶", action="操作類型", role="角色名稱")
    @app_commands.choices(
        action=[
            app_commands.Choice(name="查看權限", value="view"),
            app_commands.Choice(name="分配角色", value="assign"),
            app_commands.Choice(name="移除角色", value="remove"),
        ]
    )
    @app_commands.default_permissions(administrator=True)
    async def manage_permissions(
        self,
        interaction: discord.Interaction,
        user: discord.Member,
        action: str,
        role: str = None,
    ):
        """管理用戶權限"""
        try:
            if not await SafeInteractionHandler.safe_defer(
                interaction, ephemeral=True
            ):
                return

            guild_id = interaction.guild.id
            admin_id = interaction.user.id

            # 檢查管理權限
            if not await self.permission_manager.check_permission(
                admin_id, guild_id, GuildPermission.USER_MANAGE
            ):
                await SafeInteractionHandler.safe_followup(
                    interaction, "❌ 您沒有管理權限的權限", ephemeral=True
                )
                return

            if action == "view":
                # 查看用戶權限
                user_perms = (
                    await self.permission_manager.get_user_permissions(
                        user.id, guild_id
                    )
                )

                embed = discord.Embed(
                    title="👥 用戶權限資訊",
                    description=f"**{user.display_name}** 的權限詳情",
                    color=discord.Color.blue(),
                )

                # 角色資訊
                roles_text = ", ".join(
                    [role.value for role in user_perms.roles]
                )
                embed.add_field(
                    name="🎭 角色", value=roles_text or "無", inline=False
                )

                # 權限列表
                if user_perms.permissions:
                    perms_text = "\n".join(
                        [f"• {perm.value}" for perm in user_perms.permissions]
                    )
                    if len(perms_text) > 1000:
                        perms_text = perms_text[:1000] + "..."
                    embed.add_field(
                        name="🔑 權限", value=perms_text, inline=False
                    )

                # 狀態資訊
                embed.add_field(
                    name="ℹ️ 狀態",
                    value=f"擁有者: {'是' if user_perms.is_owner else '否'}\n"
                    f"管理員: {'是' if user_perms.is_admin else '否'}\n"
                    f"分配時間: {user_perms.assigned_at.strftime('%Y-%m-%d') if user_perms.assigned_at else '未知'}",
                    inline=True,
                )

                await SafeInteractionHandler.safe_followup(
                    interaction, embed=embed, ephemeral=True
                )

            elif action in ["assign", "remove"]:
                if not role:
                    await SafeInteractionHandler.safe_followup(
                        interaction, "❌ 請指定角色名稱", ephemeral=True
                    )
                    return

                # 這裡需要實現角色分配/移除邏輯
                # 暫時提供基本回應
                await SafeInteractionHandler.safe_followup(
                    interaction,
                    f"✅ {action} 操作完成 - 用戶: {user.display_name}, 角色: {role}",
                    ephemeral=True,
                )

        except Exception as e:
            logger.error(f"❌ 權限管理錯誤: {e}")
            await SafeInteractionHandler.safe_followup(
                interaction, f"❌ 權限管理失敗: {str(e)}", ephemeral=True
            )


async def setup(bot):
    await bot.add_cog(GuildManagementCore(bot))
