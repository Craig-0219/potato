# bot/views/security_views.py - 安全管理視圖組件 v1.7.0
"""
安全管理互動式視圖組件
提供安全監控、警報管理和合規報告的UI介面
"""

import json
from datetime import datetime, timezone
from typing import Any, Dict, List

import discord

from shared.logger import logger


class SecurityView(discord.ui.View):
    """安全監控主視圖"""

    def __init__(self, user_id: int, security_stats: Dict[str, Any]):
        super().__init__(timeout=600)
        self.user_id = user_id
        self.security_stats = security_stats

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        """檢查互動權限"""
        if interaction.user.id != self.user_id:
            await interaction.response.send_message(
                "❌ 只有指令執行者可以操作此介面", ephemeral=True
            )
            return False
        return True

    @discord.ui.button(label="📊 詳細統計", style=discord.ButtonStyle.primary, row=1)
    async def detailed_stats(self, interaction: discord.Interaction, button: discord.ui.Button):
        """查看詳細統計"""
        embed = discord.Embed(
            title="📊 安全統計詳情", description="系統安全狀態詳細分析", color=0x3498DB
        )

        # 事件分析
        total_events = self.security_stats.get("total_events", 0)
        high_risk = self.security_stats.get("high_risk_events", 0)
        critical = self.security_stats.get("critical_events", 0)

        risk_percentage = 0
        if total_events > 0:
            risk_percentage = ((high_risk + critical) / total_events) * 100

        embed.add_field(
            name="🎯 風險分析",
            value=f"風險事件比例: {risk_percentage:.1f}%\n"
            f"高風險: {high_risk} ({(high_risk/max(total_events,1)*100):.1f}%)\n"
            f"嚴重事件: {critical} ({(critical/max(total_events,1)*100):.1f}%)",
            inline=False,
        )

        # 趨勢分析
        trend_emoji = "📈"
        trend_text = "數據收集中"
        if total_events > 100:
            trend_emoji = "📉" if risk_percentage < 10 else "⚠️"
            trend_text = f"趨勢: {'改善' if risk_percentage < 10 else '需要關注'}"

        embed.add_field(
            name="📈 安全趋勢",
            value=f"{trend_emoji} {trend_text}\n"
            f"活躍用戶: {self.security_stats.get('unique_users', 0)}\n"
            f"系統健康度: {'良好' if risk_percentage < 5 else '一般' if risk_percentage < 15 else '需改善'}",
            inline=True,
        )

        await interaction.response.send_message(embed=embed, ephemeral=True)

    @discord.ui.button(label="🚨 活躍警報", style=discord.ButtonStyle.danger, row=1)
    async def active_alerts(self, interaction: discord.Interaction, button: discord.ui.Button):
        """查看活躍警報"""
        await interaction.response.send_message(
            "請使用 `/security_alerts` 指令查看詳細的活躍警報資訊", ephemeral=True
        )

    @discord.ui.button(label="📋 生成報告", style=discord.ButtonStyle.secondary, row=1)
    async def generate_report(self, interaction: discord.Interaction, button: discord.ui.Button):
        """生成安全報告"""
        await interaction.response.send_message(
            "請使用 `/compliance_report` 指令生成詳細的合規報告", ephemeral=True
        )

    @discord.ui.button(label="🔄 刷新數據", style=discord.ButtonStyle.secondary, row=1)
    async def refresh_data(self, interaction: discord.Interaction, button: discord.ui.Button):
        """刷新數據"""
        await interaction.response.send_message(
            "請重新使用 `/security_dashboard` 指令獲取最新數據", ephemeral=True
        )


class AlertView(discord.ui.View):
    """安全警報管理視圖"""

    def __init__(self, user_id: int, alerts: List[Dict[str, Any]]):
        super().__init__(timeout=600)
        self.user_id = user_id
        self.alerts = alerts

        # 如果有警報，添加選擇器
        if alerts:
            self.add_item(AlertSelectDropdown(alerts[:25]))  # Discord限制25個選項

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        """檢查互動權限"""
        if interaction.user.id != self.user_id:
            await interaction.response.send_message(
                "❌ 只有指令執行者可以操作此介面", ephemeral=True
            )
            return False
        return True

    @discord.ui.button(label="🔍 篩選警報", style=discord.ButtonStyle.secondary, row=2)
    async def filter_alerts(self, interaction: discord.Interaction, button: discord.ui.Button):
        """篩選警報"""
        modal = AlertFilterModal()
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="📊 警報統計", style=discord.ButtonStyle.primary, row=2)
    async def alert_statistics(self, interaction: discord.Interaction, button: discord.ui.Button):
        """查看警報統計"""
        if not self.alerts:
            await interaction.response.send_message("❌ 沒有警報數據", ephemeral=True)
            return

        # 統計分析
        severity_counts = {}
        status_counts = {}

        for alert in self.alerts:
            sev = alert["severity"]
            status = alert["status"]
            severity_counts[sev] = severity_counts.get(sev, 0) + 1
            status_counts[status] = status_counts.get(status, 0) + 1

        embed = discord.Embed(
            title="📊 警報統計分析",
            description=f"基於 {len(self.alerts)} 個警報的統計",
            color=0xE74C3C,
        )

        # 嚴重程度分佈
        severity_text = []
        severity_emojis = {"critical": "🔴", "high": "🟠", "medium": "🟡", "low": "🟢"}
        for sev, count in severity_counts.items():
            emoji = severity_emojis.get(sev, "⚪")
            percentage = (count / len(self.alerts)) * 100
            severity_text.append(f"{emoji} {sev.capitalize()}: {count} ({percentage:.1f}%)")

        embed.add_field(name="🎯 嚴重程度分佈", value="\n".join(severity_text), inline=True)

        # 狀態分佈
        status_text = []
        status_emojis = {
            "open": "🔓",
            "investigating": "🔍",
            "resolved": "✅",
            "false_positive": "❌",
        }
        for status, count in status_counts.items():
            emoji = status_emojis.get(status, "❓")
            percentage = (count / len(self.alerts)) * 100
            status_text.append(
                f"{emoji} {status.replace('_', ' ').title()}: {count} ({percentage:.1f}%)"
            )

        embed.add_field(name="📋 處理狀態分佈", value="\n".join(status_text), inline=True)

        await interaction.response.send_message(embed=embed, ephemeral=True)

    @discord.ui.button(label="🔄 刷新列表", style=discord.ButtonStyle.secondary, row=2)
    async def refresh_alerts(self, interaction: discord.Interaction, button: discord.ui.Button):
        """刷新警報列表"""
        await interaction.response.send_message(
            "請重新使用 `/security_alerts` 指令獲取最新警報", ephemeral=True
        )


class AlertSelectDropdown(discord.ui.Select):
    """警報選擇下拉選單"""

    def __init__(self, alerts: List[Dict[str, Any]]):
        options = []

        for alert in alerts[:25]:
            severity_emoji = {
                "low": "🟢",
                "medium": "🟡",
                "high": "🟠",
                "critical": "🔴",
            }.get(alert["severity"], "⚪")

            status_emoji = {"open": "🔓", "investigating": "🔍", "resolved": "✅"}.get(
                alert["status"], "❓"
            )

            options.append(
                discord.SelectOption(
                    label=f"{alert['title'][:45]}{'...' if len(alert['title']) > 45 else ''}",
                    value=alert["id"],
                    description=f"{severity_emoji} {alert['severity'].title()} | {status_emoji} {alert['status'].replace('_', ' ').title()}",
                    emoji="🚨",
                )
            )

        super().__init__(
            placeholder="選擇要操作的警報...",
            min_values=1,
            max_values=1,
            options=options,
        )

    async def callback(self, interaction: discord.Interaction):
        """處理警報選擇"""
        try:
            alert_id = self.values[0]

            # 創建警報詳情視圖
            view = AlertDetailView(interaction.user.id, alert_id)

            embed = discord.Embed(
                title="🚨 警報操作", description=f"請選擇對警報的操作", color=0xE74C3C
            )

            await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

        except Exception as e:
            logger.error(f"處理警報選擇失敗: {e}")
            await interaction.response.send_message("❌ 操作失敗", ephemeral=True)


class AlertDetailView(discord.ui.View):
    """警報詳情操作視圖"""

    def __init__(self, user_id: int, alert_id: str):
        super().__init__(timeout=300)
        self.user_id = user_id
        self.alert_id = alert_id

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        """檢查互動權限"""
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("❌ 只有指令執行者可以操作", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="📋 查看詳情", style=discord.ButtonStyle.secondary)
    async def view_details(self, interaction: discord.Interaction, button: discord.ui.Button):
        """查看警報詳情"""
        embed = discord.Embed(
            title="📋 警報詳細資訊",
            description=f"警報ID: {self.alert_id}",
            color=0x3498DB,
        )

        embed.add_field(
            name="ℹ️ 說明",
            value="詳細警報資訊需要從資料庫獲取\n請聯繫系統管理員查看完整詳情",
            inline=False,
        )

        await interaction.response.send_message(embed=embed, ephemeral=True)

    @discord.ui.button(label="🔍 開始調查", style=discord.ButtonStyle.primary)
    async def start_investigation(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        """開始調查警報"""
        await interaction.response.send_message(
            f"✅ 警報 {self.alert_id[:8]}... 已標記為「調查中」\n" f"請記錄調查過程並及時更新狀態",
            ephemeral=True,
        )

    @discord.ui.button(label="✅ 標記已解決", style=discord.ButtonStyle.success)
    async def mark_resolved(self, interaction: discord.Interaction, button: discord.ui.Button):
        """標記警報已解決"""
        modal = AlertResolutionModal(self.alert_id)
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="❌ 誤報", style=discord.ButtonStyle.danger)
    async def mark_false_positive(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        """標記為誤報"""
        await interaction.response.send_message(
            f"✅ 警報 {self.alert_id[:8]}... 已標記為「誤報」\n"
            f"系統將學習此類模式以減少類似誤報",
            ephemeral=True,
        )


class AlertFilterModal(discord.ui.Modal):
    """警報篩選模態框"""

    def __init__(self):
        super().__init__(title="🔍 篩選安全警報")

        self.severity_input = discord.ui.TextInput(
            label="嚴重程度",
            placeholder="low, medium, high, critical (可多選，用逗號分隔)",
            max_length=50,
            required=False,
        )

        self.status_input = discord.ui.TextInput(
            label="處理狀態",
            placeholder="open, investigating, resolved, false_positive",
            max_length=50,
            required=False,
        )

        self.days_input = discord.ui.TextInput(
            label="時間範圍（天）", placeholder="7", max_length=3, required=False
        )

        self.add_item(self.severity_input)
        self.add_item(self.status_input)
        self.add_item(self.days_input)

    async def on_submit(self, interaction: discord.Interaction):
        """提交篩選條件"""
        try:
            filters = []

            if self.severity_input.value:
                filters.append(f"嚴重程度: {self.severity_input.value}")

            if self.status_input.value:
                filters.append(f"狀態: {self.status_input.value}")

            if self.days_input.value:
                filters.append(f"時間範圍: {self.days_input.value} 天")

            embed = discord.Embed(
                title="🔍 警報篩選條件", description="篩選條件已設定", color=0x3498DB
            )

            if filters:
                embed.add_field(name="📋 篩選設定", value="\n".join(filters), inline=False)

                embed.add_field(
                    name="⚡ 下一步",
                    value="請使用 `/security_alerts` 指令並手動設定對應參數",
                    inline=False,
                )
            else:
                embed.add_field(
                    name="ℹ️ 提示",
                    value="未設定任何篩選條件，將顯示所有警報",
                    inline=False,
                )

            await interaction.response.send_message(embed=embed, ephemeral=True)

        except Exception as e:
            logger.error(f"警報篩選失敗: {e}")
            await interaction.response.send_message("❌ 篩選設定失敗", ephemeral=True)


class AlertResolutionModal(discord.ui.Modal):
    """警報解決模態框"""

    def __init__(self, alert_id: str):
        super().__init__(title="✅ 標記警報已解決")
        self.alert_id = alert_id

        self.resolution_note = discord.ui.TextInput(
            label="解決說明",
            placeholder="描述如何解決此警報，包括採取的行動和結果...",
            style=discord.TextStyle.paragraph,
            max_length=1000,
            required=True,
        )

        self.preventive_actions = discord.ui.TextInput(
            label="預防措施",
            placeholder="描述為防止類似問題再次發生所採取的預防措施...",
            style=discord.TextStyle.paragraph,
            max_length=500,
            required=False,
        )

        self.add_item(self.resolution_note)
        self.add_item(self.preventive_actions)

    async def on_submit(self, interaction: discord.Interaction):
        """提交解決方案"""
        try:
            embed = discord.Embed(
                title="✅ 警報已解決",
                description=f"警報 {self.alert_id[:8]}... 已成功標記為已解決",
                color=0x2ECC71,
            )

            embed.add_field(
                name="📝 解決說明",
                value=(
                    self.resolution_note.value[:200] + "..."
                    if len(self.resolution_note.value) > 200
                    else self.resolution_note.value
                ),
                inline=False,
            )

            if self.preventive_actions.value:
                embed.add_field(
                    name="🛡️ 預防措施",
                    value=(
                        self.preventive_actions.value[:200] + "..."
                        if len(self.preventive_actions.value) > 200
                        else self.preventive_actions.value
                    ),
                    inline=False,
                )

            embed.set_footer(
                text=f"解決時間: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')} UTC"
            )

            await interaction.response.send_message(embed=embed, ephemeral=True)

        except Exception as e:
            logger.error(f"標記警報解決失敗: {e}")
            await interaction.response.send_message("❌ 操作失敗", ephemeral=True)


class ComplianceReportView(discord.ui.View):
    """合規報告操作視圖"""

    def __init__(self, user_id: int, report: Any):
        super().__init__(timeout=600)
        self.user_id = user_id
        self.report = report

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        """檢查互動權限"""
        if interaction.user.id != self.user_id:
            await interaction.response.send_message(
                "❌ 只有指令執行者可以操作此介面", ephemeral=True
            )
            return False
        return True

    @discord.ui.button(label="📋 完整報告", style=discord.ButtonStyle.primary, row=1)
    async def full_report(self, interaction: discord.Interaction, button: discord.ui.Button):
        """查看完整報告"""
        embed = discord.Embed(
            title=f"📋 {self.report.standard.value.upper()} 完整合規報告",
            description=f"報告ID: {self.report.id}",
            color=0x9B59B6,
        )

        # 報告期間
        embed.add_field(
            name="📅 報告期間",
            value=f"{self.report.period_start.strftime('%Y-%m-%d')} 至 {self.report.period_end.strftime('%Y-%m-%d')}",
            inline=False,
        )

        # 詳細統計
        summary = self.report.summary
        embed.add_field(
            name="📊 詳細統計",
            value=f"總事件數: {summary.get('total_events', 0)}\n"
            f"資料存取事件: {summary.get('data_access_events', 0)}\n"
            f"用戶管理事件: {summary.get('user_management_events', 0)}\n"
            f"涉及用戶數: {summary.get('unique_users', 0)}",
            inline=True,
        )

        # 風險分析
        high_risk = summary.get("high_risk_events", 0)
        critical = summary.get("critical_events", 0)
        total = summary.get("total_events", 0)
        risk_ratio = ((high_risk + critical) / max(total, 1)) * 100

        embed.add_field(
            name="⚠️ 風險分析",
            value=f"高風險事件: {high_risk}\n"
            f"嚴重事件: {critical}\n"
            f"風險比例: {risk_ratio:.1f}%",
            inline=True,
        )

        # 違規詳情
        if self.report.violations:
            violations_text = []
            for violation in self.report.violations:
                sev_emoji = {
                    "low": "🟢",
                    "medium": "🟡",
                    "high": "🟠",
                    "critical": "🔴",
                }.get(violation["severity"], "⚪")
                violations_text.append(f"{sev_emoji} {violation['description']}")

            embed.add_field(
                name="⚠️ 發現的違規",
                value="\n".join(violations_text[:10]),
                inline=False,  # 限制10個
            )

        # 改善建議
        if self.report.recommendations:
            recommendations_text = []
            for i, rec in enumerate(self.report.recommendations[:8], 1):  # 限制8個
                recommendations_text.append(f"{i}. {rec}")

            embed.add_field(name="💡 改善建議", value="\n".join(recommendations_text), inline=False)

        embed.set_footer(
            text=f"生成時間: {self.report.generated_at.strftime('%Y-%m-%d %H:%M:%S')} UTC"
        )

        await interaction.response.send_message(embed=embed, ephemeral=True)

    @discord.ui.button(label="📈 趨勢分析", style=discord.ButtonStyle.secondary, row=1)
    async def trend_analysis(self, interaction: discord.Interaction, button: discord.ui.Button):
        """趨勢分析"""
        embed = discord.Embed(
            title="📈 合規趨勢分析",
            description=f"基於 {self.report.standard.value.upper()} 標準的趨勢分析",
            color=0x3498DB,
        )

        summary = self.report.summary
        total_events = summary.get("total_events", 0)

        # 活動水平分析
        if total_events > 1000:
            activity_level = "🔴 高活動"
            activity_desc = "系統活動頻繁，建議加強監控"
        elif total_events > 500:
            activity_level = "🟡 中活動"
            activity_desc = "系統活動正常"
        else:
            activity_level = "🟢 低活動"
            activity_desc = "系統活動較少"

        embed.add_field(name="📊 活動水平", value=f"{activity_level}\n{activity_desc}", inline=True)

        # 合規健康度
        violations_count = len(self.report.violations)
        if violations_count == 0:
            compliance_health = "🟢 優秀"
            health_desc = "完全合規，無發現違規"
        elif violations_count <= 3:
            compliance_health = "🟡 良好"
            health_desc = f"發現 {violations_count} 個輕微違規"
        else:
            compliance_health = "🔴 需改善"
            health_desc = f"發現 {violations_count} 個違規，需要立即處理"

        embed.add_field(
            name="🛡️ 合規健康度",
            value=f"{compliance_health}\n{health_desc}",
            inline=True,
        )

        # 改善進度
        recommendations_count = len(self.report.recommendations)
        if recommendations_count == 0:
            improvement = "✅ 無需改善"
        elif recommendations_count <= 5:
            improvement = f"📋 {recommendations_count} 項建議"
        else:
            improvement = f"📋 {recommendations_count} 項建議（優先處理）"

        embed.add_field(name="🎯 改善機會", value=improvement, inline=True)

        await interaction.response.send_message(embed=embed, ephemeral=True)

    @discord.ui.button(label="📤 匯出報告", style=discord.ButtonStyle.success, row=1)
    async def export_report(self, interaction: discord.Interaction, button: discord.ui.Button):
        """匯出報告"""
        # 創建報告摘要
        report_summary = {
            "id": self.report.id,
            "standard": self.report.standard.value,
            "period": f"{self.report.period_start} to {self.report.period_end}",
            "generated_at": self.report.generated_at.isoformat(),
            "summary": self.report.summary,
            "violations_count": len(self.report.violations),
            "recommendations_count": len(self.report.recommendations),
        }

        embed = discord.Embed(title="📤 報告匯出", description="合規報告匯出資訊", color=0x2ECC71)

        embed.add_field(
            name="📋 報告摘要",
            value=f"標準: {self.report.standard.value.upper()}\n"
            f"期間: {(self.report.period_end - self.report.period_start).days} 天\n"
            f"違規數: {len(self.report.violations)}\n"
            f"建議數: {len(self.report.recommendations)}",
            inline=True,
        )

        embed.add_field(
            name="📄 匯出格式",
            value="• JSON 格式摘要\n• 完整報告需要透過系統管理員獲取\n• 支援 PDF/Excel 格式",
            inline=True,
        )

        # 簡化的JSON匯出
        json_preview = json.dumps(report_summary, indent=2, ensure_ascii=False)[:1500]
        if len(json_preview) >= 1500:
            json_preview += "\n... (截斷)"

        embed.add_field(name="🔍 JSON預覽", value=f"```json\n{json_preview}\n```", inline=False)

        await interaction.response.send_message(embed=embed, ephemeral=True)

    @discord.ui.button(label="🔄 重新生成", style=discord.ButtonStyle.secondary, row=2)
    async def regenerate_report(self, interaction: discord.Interaction, button: discord.ui.Button):
        """重新生成報告"""
        await interaction.response.send_message(
            f"📋 重新生成 {self.report.standard.value.upper()} 合規報告\n\n"
            f"請使用以下指令重新生成最新報告：\n"
            f"`/compliance_report standard:{self.report.standard.value} days:{(self.report.period_end - self.report.period_start).days}`",
            ephemeral=True,
        )

    @discord.ui.button(label="📚 查看歷史", style=discord.ButtonStyle.secondary, row=2)
    async def view_history(self, interaction: discord.Interaction, button: discord.ui.Button):
        """查看報告歷史"""
        await interaction.response.send_message(
            f"📚 查看 {self.report.standard.value.upper()} 合規報告歷史\n\n"
            f"請使用以下指令查看歷史報告：\n"
            f"`/compliance_history standard:{self.report.standard.value}`",
            ephemeral=True,
        )
