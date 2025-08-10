# bot/cogs/security_core.py - 企業級安全管理核心 v1.7.0
"""
企業級安全管理核心功能
提供安全監控、審計管理和合規報告的Discord指令介面
"""

import discord
from discord.ext import commands
from discord import app_commands
from typing import Dict, List, Optional, Any
import json
import asyncio
from datetime import datetime, timezone, timedelta

from bot.services.security_audit_manager import (
    security_audit_manager, SecurityEventType, RiskLevel, AuditAction, ComplianceStandard
)
from bot.db.security_dao import SecurityDAO
from bot.utils.embed_builder import EmbedBuilder
from bot.views.security_views import SecurityView, AlertView, ComplianceReportView
from shared.logger import logger


class SecurityCore(commands.Cog):
    """企業級安全管理核心功能"""
    
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.security_manager = security_audit_manager
        self.security_dao = SecurityDAO()
        logger.info("✅ 企業級安全管理核心已初始化")
    
    # ========== 安全監控指令 ==========
    
    @app_commands.command(name="security_dashboard", description="查看安全監控儀表板")
    @app_commands.describe(days="統計天數")
    async def security_dashboard(self, interaction: discord.Interaction, days: int = 30):
        """查看安全監控儀表板"""
        try:
            # 檢查權限
            if not interaction.user.guild_permissions.administrator:
                await interaction.response.send_message("❌ 需要管理員權限才能查看安全儀表板", ephemeral=True)
                return
            
            if not 1 <= days <= 365:
                await interaction.response.send_message("❌ 天數必須在1-365之間", ephemeral=True)
                return
            
            await interaction.response.defer(ephemeral=True)
            
            # 獲取安全統計
            stats = await self.security_dao.get_security_statistics(interaction.guild.id, days)
            
            # 獲取活躍警報
            alerts = await self.security_dao.get_active_alerts(interaction.guild.id)
            
            # 創建儀表板嵌入式訊息
            embed = EmbedBuilder.build(
                title="🛡️ 安全監控儀表板",
                description=f"伺服器安全狀態概覽 - 最近 {days} 天",
                color=0xe74c3c
            )
            
            # 總體安全狀態
            security_level = "🟢 良好"
            if stats.get('critical_events', 0) > 0:
                security_level = "🔴 嚴重"
            elif stats.get('high_risk_events', 0) > 10:
                security_level = "🟡 警戒"
            
            embed.add_field(
                name="🛡️ 安全等級",
                value=security_level,
                inline=True
            )
            
            # 事件統計
            embed.add_field(
                name="📊 事件統計",
                value=f"總事件: {stats.get('total_events', 0)}\n"
                      f"高風險: {stats.get('high_risk_events', 0)}\n"
                      f"嚴重事件: {stats.get('critical_events', 0)}\n"
                      f"活躍用戶: {stats.get('unique_users', 0)}",
                inline=True
            )
            
            # 警報統計
            alert_status = "✅ 正常"
            if stats.get('active_alerts', 0) > 0:
                alert_status = f"⚠️ {stats.get('active_alerts')} 個待處理"
            
            embed.add_field(
                name="🚨 警報狀態",
                value=alert_status,
                inline=True
            )
            
            # 事件類型分佈
            if stats.get('event_type_distribution'):
                event_types_text = []
                for event_type in stats['event_type_distribution'][:5]:
                    event_name = self._get_event_display_name(event_type['type'])
                    event_types_text.append(f"• {event_name}: {event_type['count']}")
                
                embed.add_field(
                    name="📈 主要事件類型",
                    value="\n".join(event_types_text),
                    inline=False
                )
            
            # 最新警報
            if alerts:
                recent_alerts_text = []
                for alert in alerts[:3]:
                    severity_emoji = {
                        'low': '🟢', 'medium': '🟡', 'high': '🟠', 'critical': '🔴'
                    }.get(alert['severity'], '⚪')
                    
                    time_str = alert['created_at'].strftime('%m-%d %H:%M')
                    recent_alerts_text.append(
                        f"{severity_emoji} **{alert['title']}**\n"
                        f"時間: {time_str} | 狀態: {alert['status']}"
                    )
                
                embed.add_field(
                    name="🚨 最新警報",
                    value="\n\n".join(recent_alerts_text),
                    inline=False
                )
            
            embed.set_footer(text=f"數據期間: {days} 天 | 實時更新")
            
            # 創建互動視圖
            view = SecurityView(interaction.user.id, stats)
            
            await interaction.followup.send(embed=embed, view=view, ephemeral=True)
            
        except Exception as e:
            logger.error(f"查看安全儀表板失敗: {e}")
            await interaction.followup.send(f"❌ 獲取安全儀表板失敗: {str(e)}", ephemeral=True)
    
    @app_commands.command(name="security_events", description="查看安全事件記錄")
    @app_commands.describe(
        event_type="事件類型",
        risk_level="風險等級",
        user="指定用戶",
        days="查看天數"
    )
    @app_commands.choices(
        event_type=[
            app_commands.Choice(name="全部", value="all"),
            app_commands.Choice(name="登入事件", value="login_success"),
            app_commands.Choice(name="權限拒絕", value="permission_denied"),
            app_commands.Choice(name="資料存取", value="data_access"),
            app_commands.Choice(name="系統配置", value="system_configuration"),
            app_commands.Choice(name="可疑活動", value="suspicious_activity")
        ],
        risk_level=[
            app_commands.Choice(name="全部", value="all"),
            app_commands.Choice(name="低風險", value="low"),
            app_commands.Choice(name="中風險", value="medium"),
            app_commands.Choice(name="高風險", value="high"),
            app_commands.Choice(name="嚴重", value="critical")
        ]
    )
    async def security_events(
        self, 
        interaction: discord.Interaction,
        event_type: str = "all",
        risk_level: str = "all",
        user: discord.Member = None,
        days: int = 7
    ):
        """查看安全事件記錄"""
        try:
            # 檢查權限
            if not interaction.user.guild_permissions.manage_guild:
                await interaction.response.send_message("❌ 需要管理伺服器權限才能查看安全事件", ephemeral=True)
                return
            
            if not 1 <= days <= 90:
                await interaction.response.send_message("❌ 天數必須在1-90之間", ephemeral=True)
                return
            
            await interaction.response.defer(ephemeral=True)
            
            # 構建查詢參數
            start_date = datetime.now(timezone.utc) - timedelta(days=days)
            query_event_type = event_type if event_type != "all" else None
            query_risk_level = risk_level if risk_level != "all" else None
            query_user_id = user.id if user else None
            
            # 獲取事件列表
            events, total_count = await self.security_dao.get_security_events(
                guild_id=interaction.guild.id,
                user_id=query_user_id,
                event_type=query_event_type,
                risk_level=query_risk_level,
                start_date=start_date,
                page=1,
                page_size=20
            )
            
            # 創建嵌入式訊息
            embed = EmbedBuilder.build(
                title="🔍 安全事件記錄",
                description=f"安全事件查詢結果 - 最近 {days} 天",
                color=0x3498db
            )
            
            if not events:
                embed.add_field(
                    name="📋 查詢結果",
                    value="在指定條件下沒有找到安全事件",
                    inline=False
                )
            else:
                # 統計資訊
                risk_counts = {}
                for event in events:
                    risk = event['risk_level']
                    risk_counts[risk] = risk_counts.get(risk, 0) + 1
                
                embed.add_field(
                    name="📊 統計摘要",
                    value=f"找到 {total_count} 個事件（顯示前 {len(events)} 個）\n"
                          f"高風險: {risk_counts.get('high', 0)} | 嚴重: {risk_counts.get('critical', 0)}",
                    inline=False
                )
                
                # 事件列表
                events_text = []
                for event in events[:10]:
                    risk_emoji = {
                        'low': '🟢', 'medium': '🟡', 'high': '🟠', 'critical': '🔴'
                    }.get(event['risk_level'], '⚪')
                    
                    event_name = self._get_event_display_name(event['event_type'])
                    time_str = event['timestamp'].strftime('%m-%d %H:%M')
                    
                    events_text.append(
                        f"{risk_emoji} **{event_name}**\n"
                        f"用戶: <@{event['user_id']}> | 時間: {time_str}\n"
                        f"資源: {event['resource'][:30]}{'...' if len(event['resource']) > 30 else ''}"
                    )
                
                embed.add_field(
                    name="🕐 最新事件",
                    value="\n\n".join(events_text),
                    inline=False
                )
            
            # 篩選條件摘要
            filters = []
            if query_event_type:
                filters.append(f"類型: {self._get_event_display_name(query_event_type)}")
            if query_risk_level:
                filters.append(f"風險: {query_risk_level}")
            if user:
                filters.append(f"用戶: {user.display_name}")
            
            if filters:
                embed.set_footer(text=f"篩選條件: {' | '.join(filters)}")
            
            await interaction.followup.send(embed=embed, ephemeral=True)
            
        except Exception as e:
            logger.error(f"查看安全事件失敗: {e}")
            await interaction.followup.send(f"❌ 獲取安全事件失敗: {str(e)}", ephemeral=True)
    
    @app_commands.command(name="security_alerts", description="查看安全警報")
    @app_commands.describe(severity="警報嚴重程度")
    @app_commands.choices(severity=[
        app_commands.Choice(name="全部", value="all"),
        app_commands.Choice(name="低級", value="low"),
        app_commands.Choice(name="中級", value="medium"),
        app_commands.Choice(name="高級", value="high"),
        app_commands.Choice(name="嚴重", value="critical")
    ])
    async def security_alerts(self, interaction: discord.Interaction, severity: str = "all"):
        """查看安全警報"""
        try:
            # 檢查權限
            if not interaction.user.guild_permissions.manage_guild:
                await interaction.response.send_message("❌ 需要管理伺服器權限才能查看安全警報", ephemeral=True)
                return
            
            await interaction.response.defer(ephemeral=True)
            
            # 獲取活躍警報
            query_severity = severity if severity != "all" else None
            alerts = await self.security_dao.get_active_alerts(interaction.guild.id, query_severity)
            
            # 創建嵌入式訊息
            embed = EmbedBuilder.build(
                title="🚨 安全警報管理",
                description="當前活躍的安全警報",
                color=0xe74c3c
            )
            
            if not alerts:
                embed.add_field(
                    name="✅ 警報狀態",
                    value="目前沒有活躍的安全警報\n系統運行正常",
                    inline=False
                )
            else:
                # 按嚴重程度分組
                alerts_by_severity = {}
                for alert in alerts:
                    sev = alert['severity']
                    if sev not in alerts_by_severity:
                        alerts_by_severity[sev] = []
                    alerts_by_severity[sev].append(alert)
                
                # 顯示各級別警報
                severity_order = ['critical', 'high', 'medium', 'low']
                severity_emojis = {
                    'critical': '🔴', 'high': '🟠', 'medium': '🟡', 'low': '🟢'
                }
                severity_names = {
                    'critical': '嚴重', 'high': '高級', 'medium': '中級', 'low': '低級'
                }
                
                for sev in severity_order:
                    if sev in alerts_by_severity:
                        sev_alerts = alerts_by_severity[sev]
                        emoji = severity_emojis[sev]
                        name = severity_names[sev]
                        
                        alerts_text = []
                        for alert in sev_alerts[:5]:
                            time_str = alert['created_at'].strftime('%m-%d %H:%M')
                            status_emoji = {'open': '🔓', 'investigating': '🔍', 'resolved': '✅'}.get(alert['status'], '❓')
                            
                            alerts_text.append(
                                f"{status_emoji} **{alert['title']}**\n"
                                f"規則: {alert['rule_name'] or 'N/A'} | 時間: {time_str}"
                            )
                        
                        if len(sev_alerts) > 5:
                            alerts_text.append(f"...還有 {len(sev_alerts) - 5} 個警報")
                        
                        embed.add_field(
                            name=f"{emoji} {name}警報 ({len(sev_alerts)})",
                            value="\n\n".join(alerts_text),
                            inline=False
                        )
            
            embed.set_footer(text=f"總計 {len(alerts)} 個活躍警報")
            
            # 創建警報管理視圖
            view = AlertView(interaction.user.id, alerts[:10]) if alerts else None
            
            await interaction.followup.send(embed=embed, view=view, ephemeral=True)
            
        except Exception as e:
            logger.error(f"查看安全警報失敗: {e}")
            await interaction.followup.send(f"❌ 獲取安全警報失敗: {str(e)}", ephemeral=True)
    
    # ========== 合規報告指令 ==========
    
    @app_commands.command(name="compliance_report", description="生成合規報告")
    @app_commands.describe(
        standard="合規標準",
        days="報告期間天數"
    )
    @app_commands.choices(standard=[
        app_commands.Choice(name="GDPR - 一般資料保護規範", value="gdpr"),
        app_commands.Choice(name="SOX - 薩班斯-奧克斯利法案", value="sox"),
        app_commands.Choice(name="ISO27001 - 資訊安全管理", value="iso27001"),
        app_commands.Choice(name="HIPAA - 健康保險便利和責任法案", value="hipaa"),
        app_commands.Choice(name="PCI DSS - 支付卡行業數據安全標準", value="pci_dss")
    ])
    async def compliance_report(
        self, 
        interaction: discord.Interaction,
        standard: str,
        days: int = 90
    ):
        """生成合規報告"""
        try:
            # 檢查權限
            if not interaction.user.guild_permissions.administrator:
                await interaction.response.send_message("❌ 需要管理員權限才能生成合規報告", ephemeral=True)
                return
            
            if not 30 <= days <= 365:
                await interaction.response.send_message("❌ 報告期間必須在30-365天之間", ephemeral=True)
                return
            
            await interaction.response.defer(ephemeral=True)
            
            # 生成報告
            end_date = datetime.now(timezone.utc)
            start_date = end_date - timedelta(days=days)
            compliance_standard = ComplianceStandard(standard)
            
            report = await self.security_manager.generate_compliance_report(
                guild_id=interaction.guild.id,
                standard=compliance_standard,
                start_date=start_date,
                end_date=end_date,
                generated_by=interaction.user.id
            )
            
            # 保存報告到資料庫
            await self.security_dao.create_compliance_report({
                'id': report.id,
                'standard': report.standard.value,
                'period_start': report.period_start,
                'period_end': report.period_end,
                'guild_id': report.guild_id,
                'generated_by': report.generated_by,
                'summary': report.summary,
                'violations': report.violations,
                'recommendations': report.recommendations
            })
            
            # 創建報告嵌入式訊息
            embed = EmbedBuilder.build(
                title=f"📋 {standard.upper()} 合規報告",
                description=f"報告期間: {start_date.strftime('%Y-%m-%d')} 至 {end_date.strftime('%Y-%m-%d')}",
                color=0x9b59b6
            )
            
            # 報告摘要
            summary = report.summary
            embed.add_field(
                name="📊 報告摘要",
                value=f"總事件: {summary.get('total_events', 0)}\n"
                      f"高風險: {summary.get('high_risk_events', 0)}\n"
                      f"嚴重事件: {summary.get('critical_events', 0)}\n"
                      f"涉及用戶: {summary.get('unique_users', 0)}",
                inline=True
            )
            
            # 合規狀態
            compliance_status = "✅ 合規"
            if report.violations:
                compliance_status = f"⚠️ {len(report.violations)} 個違規"
            
            embed.add_field(
                name="🛡️ 合規狀態",
                value=compliance_status,
                inline=True
            )
            
            # 風險評級
            risk_score = 0
            if summary.get('critical_events', 0) > 0:
                risk_score = 4
            elif summary.get('high_risk_events', 0) > 10:
                risk_score = 3
            elif len(report.violations) > 0:
                risk_score = 2
            else:
                risk_score = 1
            
            risk_levels = {1: "🟢 低", 2: "🟡 中", 3: "🟠 高", 4: "🔴 嚴重"}
            
            embed.add_field(
                name="⚡ 風險評級",
                value=risk_levels[risk_score],
                inline=True
            )
            
            # 違規情況
            if report.violations:
                violation_text = []
                for violation in report.violations[:3]:
                    sev_emoji = {'low': '🟢', 'medium': '🟡', 'high': '🟠', 'critical': '🔴'}.get(violation['severity'], '⚪')
                    violation_text.append(f"{sev_emoji} {violation['description']}")
                
                if len(report.violations) > 3:
                    violation_text.append(f"...還有 {len(report.violations) - 3} 個違規")
                
                embed.add_field(
                    name="⚠️ 主要違規",
                    value="\n".join(violation_text),
                    inline=False
                )
            
            # 建議
            if report.recommendations:
                recommendations_text = []
                for i, rec in enumerate(report.recommendations[:5], 1):
                    recommendations_text.append(f"{i}. {rec}")
                
                embed.add_field(
                    name="💡 改善建議",
                    value="\n".join(recommendations_text),
                    inline=False
                )
            
            embed.set_footer(text=f"報告ID: {report.id} | 生成時間: {report.generated_at.strftime('%Y-%m-%d %H:%M')}")
            
            # 創建報告操作視圖
            view = ComplianceReportView(interaction.user.id, report)
            
            await interaction.followup.send(embed=embed, view=view, ephemeral=True)
            
        except Exception as e:
            logger.error(f"生成合規報告失敗: {e}")
            await interaction.followup.send(f"❌ 生成合規報告失敗: {str(e)}", ephemeral=True)
    
    @app_commands.command(name="compliance_history", description="查看合規報告歷史")
    @app_commands.describe(standard="合規標準")
    @app_commands.choices(standard=[
        app_commands.Choice(name="全部", value="all"),
        app_commands.Choice(name="GDPR", value="gdpr"),
        app_commands.Choice(name="SOX", value="sox"),
        app_commands.Choice(name="ISO27001", value="iso27001"),
        app_commands.Choice(name="HIPAA", value="hipaa"),
        app_commands.Choice(name="PCI DSS", value="pci_dss")
    ])
    async def compliance_history(self, interaction: discord.Interaction, standard: str = "all"):
        """查看合規報告歷史"""
        try:
            # 檢查權限
            if not interaction.user.guild_permissions.manage_guild:
                await interaction.response.send_message("❌ 需要管理伺服器權限才能查看合規歷史", ephemeral=True)
                return
            
            await interaction.response.defer(ephemeral=True)
            
            # 獲取報告歷史
            query_standard = standard if standard != "all" else None
            reports = await self.security_dao.get_compliance_reports(interaction.guild.id, query_standard)
            
            # 創建嵌入式訊息
            embed = EmbedBuilder.build(
                title="📚 合規報告歷史",
                description="歷史合規報告記錄",
                color=0x9b59b6
            )
            
            if not reports:
                embed.add_field(
                    name="📋 報告狀態",
                    value="目前沒有合規報告記錄\n使用 `/compliance_report` 生成新報告",
                    inline=False
                )
            else:
                # 按標準分組
                reports_by_standard = {}
                for report in reports:
                    std = report['standard']
                    if std not in reports_by_standard:
                        reports_by_standard[std] = []
                    reports_by_standard[std].append(report)
                
                # 顯示各標準的報告
                standard_names = {
                    'gdpr': 'GDPR',
                    'sox': 'SOX',
                    'iso27001': 'ISO27001',
                    'hipaa': 'HIPAA',
                    'pci_dss': 'PCI DSS'
                }
                
                for std, std_reports in reports_by_standard.items():
                    std_name = standard_names.get(std, std.upper())
                    
                    reports_text = []
                    for report in std_reports[:5]:
                        generated_time = report['generated_at'].strftime('%m-%d %H:%M')
                        period = f"{report['period_start']} 至 {report['period_end']}"
                        
                        violation_count = len(report['violations'])
                        status_emoji = "✅" if violation_count == 0 else f"⚠️({violation_count})"
                        
                        reports_text.append(
                            f"{status_emoji} **{period}**\n"
                            f"生成: {generated_time} | 狀態: {report['status']}"
                        )
                    
                    if len(std_reports) > 5:
                        reports_text.append(f"...還有 {len(std_reports) - 5} 個報告")
                    
                    embed.add_field(
                        name=f"📋 {std_name} ({len(std_reports)})",
                        value="\n\n".join(reports_text),
                        inline=False
                    )
            
            embed.set_footer(text=f"共 {len(reports)} 個歷史報告")
            
            await interaction.followup.send(embed=embed, ephemeral=True)
            
        except Exception as e:
            logger.error(f"查看合規歷史失敗: {e}")
            await interaction.followup.send(f"❌ 獲取合規歷史失敗: {str(e)}", ephemeral=True)
    
    # ========== 輔助方法 ==========
    
    def _get_event_display_name(self, event_type: str) -> str:
        """獲取事件類型顯示名稱"""
        names = {
            'login_success': '登入成功',
            'login_failure': '登入失敗',
            'permission_denied': '權限拒絕',
            'data_access': '資料存取',
            'data_modification': '資料修改',
            'system_configuration': '系統配置',
            'user_management': '用戶管理',
            'role_assignment': '角色分配',
            'suspicious_activity': '可疑活動',
            'security_violation': '安全違規',
            'command_execution': '指令執行',
            'file_access': '檔案存取',
            'database_query': '資料庫查詢',
            'api_call': 'API呼叫'
        }
        return names.get(event_type, event_type)
    
    # ========== 事件監聽器 ==========
    
    @commands.Cog.listener()
    async def on_guild_role_create(self, role):
        """角色創建事件"""
        try:
            # 記錄角色創建事件
            await self.security_manager.log_security_event(
                event_type=SecurityEventType.SYSTEM_CONFIGURATION,
                user_id=0,  # 系統事件
                guild_id=role.guild.id,
                action=AuditAction.CREATE,
                resource=f"role:{role.id}",
                details={
                    'role_name': role.name,
                    'role_permissions': [perm for perm, value in role.permissions if value],
                    'created_at': datetime.now(timezone.utc).isoformat()
                },
                risk_level=RiskLevel.MEDIUM
            )
            
        except Exception as e:
            logger.error(f"記錄角色創建事件失敗: {e}")
    
    @commands.Cog.listener()
    async def on_member_ban(self, guild, member):
        """成員封禁事件"""
        try:
            # 記錄封禁事件
            await self.security_manager.log_security_event(
                event_type=SecurityEventType.USER_MANAGEMENT,
                user_id=member.id,
                guild_id=guild.id,
                action=AuditAction.DELETE,
                resource=f"member:{member.id}",
                details={
                    'member_name': member.name,
                    'member_roles': [role.name for role in member.roles],
                    'ban_timestamp': datetime.now(timezone.utc).isoformat()
                },
                risk_level=RiskLevel.HIGH
            )
            
        except Exception as e:
            logger.error(f"記錄封禁事件失敗: {e}")
    
    @commands.Cog.listener()
    async def on_guild_channel_delete(self, channel):
        """頻道刪除事件"""
        try:
            # 記錄頻道刪除事件
            await self.security_manager.log_security_event(
                event_type=SecurityEventType.SYSTEM_CONFIGURATION,
                user_id=0,
                guild_id=channel.guild.id,
                action=AuditAction.DELETE,
                resource=f"channel:{channel.id}",
                details={
                    'channel_name': channel.name,
                    'channel_type': str(channel.type),
                    'deleted_at': datetime.now(timezone.utc).isoformat()
                },
                risk_level=RiskLevel.MEDIUM
            )
            
        except Exception as e:
            logger.error(f"記錄頻道刪除事件失敗: {e}")
    
    # ========== 定期任務 ==========
    
    @commands.Cog.listener()
    async def on_ready(self):
        """Bot準備完成時啟動定期任務"""
        if not hasattr(self, 'cleanup_task'):
            self.cleanup_task = asyncio.create_task(self._periodic_cleanup())
    
    async def _periodic_cleanup(self):
        """定期清理任務"""
        while True:
            try:
                await asyncio.sleep(3600)  # 每小時執行一次
                
                # 清理過期會話
                await self.security_manager.cleanup_expired_sessions()
                
                # 清理舊的安全事件（每天執行一次）
                import random
                if random.randint(1, 24) == 1:  # 約1/24的機率
                    await self.security_dao.cleanup_old_events(90)
                    await self.security_dao.cleanup_old_sessions(30)
                
                logger.info("🧹 安全系統定期清理完成")
                
            except Exception as e:
                logger.error(f"定期清理任務失敗: {e}")
    
    # ========== 錯誤處理 ==========
    
    async def cog_app_command_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        """處理應用指令錯誤"""
        logger.error(f"安全管理指令錯誤: {error}")
        
        if not interaction.response.is_done():
            await interaction.response.send_message("❌ 安全指令執行時發生錯誤，請稍後再試", ephemeral=True)
        else:
            await interaction.followup.send("❌ 操作失敗，請檢查系統狀態", ephemeral=True)


async def setup(bot):
    await bot.add_cog(SecurityCore(bot))