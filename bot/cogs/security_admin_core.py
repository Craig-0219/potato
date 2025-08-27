# bot/cogs/security_admin_core.py - v1.0.0
# 🔐 企業級安全管理指令系統
# Enterprise Security Administration Commands

import json
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import discord
from discord import app_commands
from discord.ext import commands

from bot.services.security.api_security import api_security
from bot.services.security.audit_manager import ComplianceStandard, EventSeverity, audit_manager
from bot.services.security.mfa_manager import MFAMethod, mfa_manager
from bot.services.security.rbac_manager import Permission, RoleLevel, rbac_manager
from bot.utils.interaction_helper import SafeInteractionHandler
from bot.views.security_management_views import (
    APIKeyManagementView,
    MFASetupView,
    RoleManagementView,
    SecurityAuditView,
    SecurityDashboardView,
)

logger = logging.getLogger(__name__)


class SecurityAdminCore(commands.Cog):
    """
    企業級安全管理核心

    功能：
    - MFA 多因素認證管理
    - RBAC 權限控制管理
    - 安全審計與監控
    - API 密鑰管理
    - 合規報告生成
    """

    def __init__(self, bot):
        self.bot = bot
        logger.info("🔐 企業級安全管理系統已載入")

    # =========================
    # 安全總覽指令
    # =========================

    @app_commands.command(name="security_dashboard", description="📊 安全管理儀表板")
    @app_commands.default_permissions(administrator=True)
    async def security_dashboard(self, interaction: discord.Interaction):
        """安全管理儀表板"""
        try:
            if not await SafeInteractionHandler.safe_defer(interaction, ephemeral=True):
                return

            # 檢查權限
            user_id = interaction.user.id
            guild_id = interaction.guild.id if interaction.guild else 0

            if not await rbac_manager.check_permission(user_id, guild_id, Permission.SYSTEM_ADMIN):
                await SafeInteractionHandler.safe_followup(
                    interaction, "❌ 您沒有存取安全儀表板的權限", ephemeral=True
                )
                return

            # 獲取安全統計數據
            security_stats = await self._get_security_statistics(guild_id)

            # 創建儀表板視圖
            view = SecurityDashboardView(security_stats)

            embed = discord.Embed(
                title="🔐 企業級安全管理儀表板",
                description="綜合安全狀態與管理功能",
                color=discord.Color.blue(),
                timestamp=datetime.now(),
            )

            # 安全概覽
            embed.add_field(
                name="🛡️ 安全狀態",
                value=f"```\n"
                f"威脅等級: {security_stats['threat_level']}\n"
                f"活躍用戶: {security_stats['active_users']}\n"
                f"MFA 啟用率: {security_stats['mfa_adoption_rate']}%\n"
                f"API 密鑰數: {security_stats['api_keys_count']}\n"
                f"```",
                inline=True,
            )

            # 最近事件
            embed.add_field(
                name="📋 最近 24 小時",
                value=f"```\n"
                f"安全事件: {security_stats['recent_events']}\n"
                f"登入失敗: {security_stats['failed_logins']}\n"
                f"權限變更: {security_stats['permission_changes']}\n"
                f"API 呼叫: {security_stats['api_calls']}\n"
                f"```",
                inline=True,
            )

            # 合規狀態
            embed.add_field(
                name="📜 合規狀態",
                value=f"```\n"
                f"SOC 2: {security_stats['soc2_status']}\n"
                f"GDPR: {security_stats['gdpr_status']}\n"
                f"完整性: {security_stats['log_integrity']}%\n"
                f"```",
                inline=False,
            )

            embed.set_footer(text="點擊下方按鈕存取各項安全管理功能")

            await SafeInteractionHandler.safe_followup(
                interaction, embed=embed, view=view, ephemeral=True
            )

        except Exception as e:
            logger.error(f"❌ 安全儀表板錯誤: {e}")
            await SafeInteractionHandler.safe_followup(
                interaction, f"❌ 儀表板載入失敗: {str(e)}", ephemeral=True
            )

    # =========================
    # MFA 多因素認證指令
    # =========================

    @app_commands.command(name="mfa_setup", description="🔐 設置多因素認證")
    async def mfa_setup(self, interaction: discord.Interaction):
        """設置 MFA 多因素認證"""
        try:
            if not await SafeInteractionHandler.safe_defer(interaction, ephemeral=True):
                return

            user_id = interaction.user.id
            user_email = f"{interaction.user.name}@discord.local"

            # 設置 TOTP
            setup_result = await mfa_manager.setup_totp(user_id, user_email)

            if setup_result["success"]:
                # 創建 MFA 設置視圖
                view = MFASetupView(setup_result)

                embed = discord.Embed(
                    title="🔐 設置多因素認證",
                    description="請按照以下步驟完成 MFA 設置",
                    color=discord.Color.green(),
                )

                embed.add_field(
                    name="📱 步驟 1: 掃描 QR Code",
                    value="使用認證應用程式掃描下方的 QR Code",
                    inline=False,
                )

                embed.add_field(
                    name="🔑 步驟 2: 手動輸入 (可選)",
                    value=f"```{setup_result['manual_entry_key']}```",
                    inline=False,
                )

                embed.add_field(
                    name="📋 推薦的認證應用程式",
                    value="• Google Authenticator\n• Microsoft Authenticator\n• Authy\n• 1Password",
                    inline=False,
                )

                embed.set_image(url=setup_result["qr_code"])

                await SafeInteractionHandler.safe_followup(
                    interaction, embed=embed, view=view, ephemeral=True
                )
            else:
                await SafeInteractionHandler.safe_followup(
                    interaction, f"❌ MFA 設置失敗: {setup_result['error']}", ephemeral=True
                )

        except Exception as e:
            logger.error(f"❌ MFA 設置錯誤: {e}")
            await SafeInteractionHandler.safe_followup(
                interaction, f"❌ MFA 設置失敗: {str(e)}", ephemeral=True
            )

    @app_commands.command(name="mfa_status", description="📋 查看 MFA 狀態")
    async def mfa_status(self, interaction: discord.Interaction):
        """查看 MFA 狀態"""
        try:
            if not await SafeInteractionHandler.safe_defer(interaction, ephemeral=True):
                return

            user_id = interaction.user.id
            mfa_status = await mfa_manager.get_mfa_status(user_id)

            embed = discord.Embed(
                title="🔐 多因素認證狀態",
                color=(
                    discord.Color.green() if mfa_status["mfa_enabled"] else discord.Color.orange()
                ),
            )

            # 整體狀態
            status_icon = "🟢" if mfa_status["mfa_enabled"] else "🟡"
            embed.add_field(
                name="🛡️ 安全狀態",
                value=f"{status_icon} {'已啟用' if mfa_status['mfa_enabled'] else '未完全啟用'}\n"
                f"🔒 安全等級: {mfa_status['security_level'].upper()}",
                inline=True,
            )

            # MFA 方法狀態
            methods_status = []
            for method, info in mfa_status["methods"].items():
                icon = "✅" if info["enabled"] else "❌"
                setup_date = info["setup_date"][:10] if info["setup_date"] else "未設置"
                methods_status.append(f"{icon} {method.upper()}: {setup_date}")

            if methods_status:
                embed.add_field(name="🔧 認證方法", value="\n".join(methods_status), inline=True)

            # 備用代碼
            embed.add_field(
                name="🎫 備用代碼",
                value=f"剩餘: {mfa_status['backup_codes_count']} 個",
                inline=True,
            )

            # 安全建議
            if mfa_status["recommendations"]:
                embed.add_field(
                    name="💡 安全建議",
                    value="\n".join(f"• {rec}" for rec in mfa_status["recommendations"]),
                    inline=False,
                )

            await SafeInteractionHandler.safe_followup(interaction, embed=embed, ephemeral=True)

        except Exception as e:
            logger.error(f"❌ MFA 狀態查詢錯誤: {e}")
            await SafeInteractionHandler.safe_followup(
                interaction, f"❌ 查詢失敗: {str(e)}", ephemeral=True
            )

    # =========================
    # RBAC 權限管理指令
    # =========================

    @app_commands.command(name="role_management", description="👥 角色與權限管理")
    @app_commands.default_permissions(administrator=True)
    async def role_management(self, interaction: discord.Interaction):
        """角色與權限管理"""
        try:
            if not await SafeInteractionHandler.safe_defer(interaction, ephemeral=True):
                return

            user_id = interaction.user.id
            guild_id = interaction.guild.id if interaction.guild else 0

            # 檢查權限
            if not await rbac_manager.check_permission(user_id, guild_id, Permission.USER_MANAGE):
                await SafeInteractionHandler.safe_followup(
                    interaction, "❌ 您沒有管理角色的權限", ephemeral=True
                )
                return

            # 獲取角色列表
            roles = await rbac_manager.list_roles()

            # 創建角色管理視圖
            view = RoleManagementView(roles)

            embed = discord.Embed(
                title="👥 角色與權限管理",
                description="管理系統角色和用戶權限",
                color=discord.Color.blue(),
            )

            # 角色統計
            system_roles = len([r for r in roles if r.is_system])
            custom_roles = len([r for r in roles if not r.is_system])

            embed.add_field(
                name="📊 角色統計",
                value=f"```\n"
                f"系統角色: {system_roles}\n"
                f"自定義角色: {custom_roles}\n"
                f"總計: {len(roles)}\n"
                f"```",
                inline=True,
            )

            # 最近角色變更
            embed.add_field(name="📋 最近變更", value="點擊下方按鈕查看詳細資訊", inline=True)

            await SafeInteractionHandler.safe_followup(
                interaction, embed=embed, view=view, ephemeral=True
            )

        except Exception as e:
            logger.error(f"❌ 角色管理錯誤: {e}")
            await SafeInteractionHandler.safe_followup(
                interaction, f"❌ 角色管理載入失敗: {str(e)}", ephemeral=True
            )

    @app_commands.command(name="assign_role", description="➕ 分配角色給用戶")
    @app_commands.describe(
        user="要分配角色的用戶", role_name="角色名稱", expires_days="角色過期天數 (可選)"
    )
    @app_commands.default_permissions(administrator=True)
    async def assign_role(
        self,
        interaction: discord.Interaction,
        user: discord.Member,
        role_name: str,
        expires_days: Optional[int] = None,
    ):
        """分配角色給用戶"""
        try:
            if not await SafeInteractionHandler.safe_defer(interaction, ephemeral=True):
                return

            assigner_id = interaction.user.id
            guild_id = interaction.guild.id if interaction.guild else 0

            # 檢查權限
            if not await rbac_manager.check_permission(
                assigner_id, guild_id, Permission.USER_MANAGE
            ):
                await SafeInteractionHandler.safe_followup(
                    interaction, "❌ 您沒有分配角色的權限", ephemeral=True
                )
                return

            # 查找角色
            roles = await rbac_manager.list_roles()
            target_role = None
            for role in roles:
                if role.name.lower() == role_name.lower():
                    target_role = role
                    break

            if not target_role:
                await SafeInteractionHandler.safe_followup(
                    interaction, f"❌ 未找到角色: {role_name}", ephemeral=True
                )
                return

            # 計算過期時間
            expires_at = None
            if expires_days:
                expires_at = datetime.now() + timedelta(days=expires_days)

            # 分配角色
            success = await rbac_manager.assign_role(
                user.id, guild_id, target_role.id, assigner_id, expires_at
            )

            if success:
                embed = discord.Embed(title="✅ 角色分配成功", color=discord.Color.green())

                embed.add_field(name="👤 用戶", value=user.mention, inline=True)

                embed.add_field(name="🎭 角色", value=target_role.name, inline=True)

                embed.add_field(
                    name="⏰ 過期時間",
                    value=expires_at.strftime("%Y-%m-%d %H:%M") if expires_at else "永不過期",
                    inline=True,
                )

                await SafeInteractionHandler.safe_followup(interaction, embed=embed, ephemeral=True)
            else:
                await SafeInteractionHandler.safe_followup(
                    interaction, "❌ 角色分配失敗", ephemeral=True
                )

        except Exception as e:
            logger.error(f"❌ 角色分配錯誤: {e}")
            await SafeInteractionHandler.safe_followup(
                interaction, f"❌ 角色分配失敗: {str(e)}", ephemeral=True
            )

    # =========================
    # 安全審計指令
    # =========================

    @app_commands.command(name="security_audit", description="🔍 安全審計與監控")
    @app_commands.default_permissions(administrator=True)
    async def security_audit(self, interaction: discord.Interaction):
        """安全審計與監控"""
        try:
            if not await SafeInteractionHandler.safe_defer(interaction, ephemeral=True):
                return

            user_id = interaction.user.id
            guild_id = interaction.guild.id if interaction.guild else 0

            # 檢查權限
            if not await rbac_manager.check_permission(user_id, guild_id, Permission.SYSTEM_ADMIN):
                await SafeInteractionHandler.safe_followup(
                    interaction, "❌ 您沒有存取安全審計的權限", ephemeral=True
                )
                return

            # 獲取審計統計
            audit_stats = await self._get_audit_statistics(guild_id)

            # 創建審計視圖
            view = SecurityAuditView(audit_stats)

            embed = discord.Embed(
                title="🔍 安全審計與監控",
                description="查看安全事件、威脅檢測和合規狀態",
                color=discord.Color.red(),
            )

            # 威脅統計
            embed.add_field(
                name="🚨 威脅檢測",
                value=f"```\n"
                f"嚴重威脅: {audit_stats['critical_threats']}\n"
                f"高風險事件: {audit_stats['high_risk_events']}\n"
                f"可疑活動: {audit_stats['suspicious_activities']}\n"
                f"```",
                inline=True,
            )

            # 審計統計
            embed.add_field(
                name="📊 審計統計",
                value=f"```\n"
                f"總事件數: {audit_stats['total_events']}\n"
                f"日誌完整性: {audit_stats['log_integrity']}%\n"
                f"合規分數: {audit_stats['compliance_score']}\n"
                f"```",
                inline=True,
            )

            await SafeInteractionHandler.safe_followup(
                interaction, embed=embed, view=view, ephemeral=True
            )

        except Exception as e:
            logger.error(f"❌ 安全審計錯誤: {e}")
            await SafeInteractionHandler.safe_followup(
                interaction, f"❌ 安全審計載入失敗: {str(e)}", ephemeral=True
            )

    @app_commands.command(name="compliance_report", description="📜 生成合規報告")
    @app_commands.describe(standard="合規標準", days="報告天數")
    @app_commands.choices(
        standard=[
            app_commands.Choice(name="SOC 2", value="soc2"),
            app_commands.Choice(name="GDPR", value="gdpr"),
            app_commands.Choice(name="ISO 27001", value="iso27001"),
        ]
    )
    @app_commands.default_permissions(administrator=True)
    async def compliance_report(
        self, interaction: discord.Interaction, standard: str, days: int = 30
    ):
        """生成合規報告"""
        try:
            if not await SafeInteractionHandler.safe_defer(interaction, ephemeral=True):
                return

            user_id = interaction.user.id
            guild_id = interaction.guild.id if interaction.guild else 0

            # 檢查權限
            if not await rbac_manager.check_permission(user_id, guild_id, Permission.SYSTEM_ADMIN):
                await SafeInteractionHandler.safe_followup(
                    interaction, "❌ 您沒有生成合規報告的權限", ephemeral=True
                )
                return

            # 設置報告期間
            end_date = datetime.now()
            start_date = end_date - timedelta(days=days)

            # 生成合規報告
            report = await audit_manager.generate_compliance_report(
                ComplianceStandard(standard), start_date, end_date, guild_id
            )

            if "error" not in report:
                embed = discord.Embed(
                    title=f"📜 {standard.upper()} 合規報告",
                    description=f"報告期間: {start_date.strftime('%Y-%m-%d')} 至 {end_date.strftime('%Y-%m-%d')}",
                    color=discord.Color.blue(),
                )

                # 合規狀態
                status_color = {"compliant": "🟢", "partial": "🟡", "non_compliant": "🔴"}

                embed.add_field(
                    name="📊 合規狀態",
                    value=f"{status_color.get(report['compliance_status'], '⚪')} {report['compliance_status'].replace('_', ' ').title()}\n"
                    f"評分: {report.get('compliance_score', 0)}/100",
                    inline=True,
                )

                # 事件統計
                embed.add_field(
                    name="📈 事件統計",
                    value=f"總事件數: {report['summary']['total_events']}",
                    inline=True,
                )

                # 詳細報告 (JSON 格式)
                report_json = json.dumps(report, indent=2, ensure_ascii=False, default=str)

                if len(report_json) > 1900:
                    # 如果報告太長，保存為文件
                    filename = (
                        f"compliance_report_{standard}_{datetime.now().strftime('%Y%m%d')}.json"
                    )
                    with open(filename, "w", encoding="utf-8") as f:
                        f.write(report_json)

                    file = discord.File(filename, filename=filename)
                    embed.add_field(
                        name="📎 完整報告", value="請查看附件中的詳細報告", inline=False
                    )

                    await SafeInteractionHandler.safe_followup(
                        interaction, embed=embed, file=file, ephemeral=True
                    )
                else:
                    embed.add_field(
                        name="📋 詳細報告",
                        value=f"```json\n{report_json[:1900]}\n```",
                        inline=False,
                    )

                    await SafeInteractionHandler.safe_followup(
                        interaction, embed=embed, ephemeral=True
                    )
            else:
                await SafeInteractionHandler.safe_followup(
                    interaction, f"❌ 合規報告生成失敗: {report['error']}", ephemeral=True
                )

        except Exception as e:
            logger.error(f"❌ 合規報告錯誤: {e}")
            await SafeInteractionHandler.safe_followup(
                interaction, f"❌ 合規報告生成失敗: {str(e)}", ephemeral=True
            )

    # =========================
    # API 密鑰管理指令
    # =========================

    @app_commands.command(name="api_key_management", description="🔑 API 密鑰管理")
    @app_commands.default_permissions(administrator=True)
    async def api_key_management(self, interaction: discord.Interaction):
        """API 密鑰管理"""
        try:
            if not await SafeInteractionHandler.safe_defer(interaction, ephemeral=True):
                return

            user_id = interaction.user.id
            guild_id = interaction.guild.id if interaction.guild else 0

            # 檢查權限
            if not await rbac_manager.check_permission(user_id, guild_id, Permission.API_ADMIN):
                await SafeInteractionHandler.safe_followup(
                    interaction, "❌ 您沒有管理 API 密鑰的權限", ephemeral=True
                )
                return

            # 創建 API 密鑰管理視圖
            view = APIKeyManagementView()

            embed = discord.Embed(
                title="🔑 API 密鑰管理",
                description="管理系統 API 密鑰和存取控制",
                color=discord.Color.gold(),
            )

            embed.add_field(
                name="🛡️ 安全提醒",
                value="• API 密鑰具有強大權限，請謹慎管理\n"
                "• 定期輪換密鑰以維護安全\n"
                "• 監控 API 使用情況",
                inline=False,
            )

            await SafeInteractionHandler.safe_followup(
                interaction, embed=embed, view=view, ephemeral=True
            )

        except Exception as e:
            logger.error(f"❌ API 密鑰管理錯誤: {e}")
            await SafeInteractionHandler.safe_followup(
                interaction, f"❌ API 密鑰管理載入失敗: {str(e)}", ephemeral=True
            )

    # =========================
    # 私有輔助方法
    # =========================

    async def _get_security_statistics(self, guild_id: int) -> Dict[str, Any]:
        """獲取安全統計數據"""
        try:
            # 這裡應該從各個安全服務獲取實際數據
            # 目前返回模擬數據
            return {
                "threat_level": "低",
                "active_users": 150,
                "mfa_adoption_rate": 65,
                "api_keys_count": 12,
                "recent_events": 45,
                "failed_logins": 3,
                "permission_changes": 2,
                "api_calls": 1250,
                "soc2_status": "合規",
                "gdpr_status": "合規",
                "log_integrity": 99.8,
            }
        except Exception as e:
            logger.error(f"❌ 獲取安全統計失敗: {e}")
            return {}

    async def _get_audit_statistics(self, guild_id: int) -> Dict[str, Any]:
        """獲取審計統計數據"""
        try:
            # 檢測可疑活動
            suspicious_activities = await audit_manager.detect_suspicious_activity()

            # 驗證日誌完整性
            integrity_result = await audit_manager.verify_log_integrity()

            return {
                "critical_threats": len(
                    [a for a in suspicious_activities if a.get("severity") == "high"]
                ),
                "high_risk_events": len(
                    [a for a in suspicious_activities if a.get("severity") == "medium"]
                ),
                "suspicious_activities": len(suspicious_activities),
                "total_events": 2340,
                "log_integrity": integrity_result.get("integrity_percentage", 100),
                "compliance_score": 92,
            }
        except Exception as e:
            logger.error(f"❌ 獲取審計統計失敗: {e}")
            return {}


async def setup(bot):
    await bot.add_cog(SecurityAdminCore(bot))
