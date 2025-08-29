# bot/views/security_management_views.py - v1.0.0
# 🔐 安全管理互動視圖
# Security Management Interactive Views

import logging
from datetime import datetime
from typing import Any, Dict, List

import discord

from bot.services.security.api_security import api_security
from bot.services.security.mfa_manager import mfa_manager
from bot.services.security.rbac_manager import Permission, rbac_manager
from bot.utils.interaction_helper import SafeInteractionHandler

logger = logging.getLogger(__name__)


class SecurityDashboardView(discord.ui.View):
    """安全管理儀表板視圖"""

    def __init__(self, security_stats: Dict[str, Any]):
        super().__init__(timeout=300)
        self.security_stats = security_stats

    @discord.ui.button(label="🔐 MFA 管理", style=discord.ButtonStyle.primary, row=0)
    async def mfa_management(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        """MFA 管理按鈕"""
        try:
            user_id = interaction.user.id
            mfa_status = await mfa_manager.get_mfa_status(user_id)

            embed = discord.Embed(
                title="🔐 MFA 多因素認證管理",
                color=(
                    discord.Color.green()
                    if mfa_status["mfa_enabled"]
                    else discord.Color.orange()
                ),
            )

            # MFA 狀態摘要
            status_text = "✅ 已啟用" if mfa_status["mfa_enabled"] else "⚠️ 未完全啟用"
            embed.add_field(
                name="📊 當前狀態",
                value=f"{status_text}\n安全等級: {mfa_status['security_level'].upper()}",
                inline=True,
            )

            # 備用代碼狀態
            embed.add_field(
                name="🎫 備用代碼",
                value=f"剩餘: {mfa_status['backup_codes_count']} 個",
                inline=True,
            )

            # 操作按鈕
            view = MFAManagementView(mfa_status)

            await SafeInteractionHandler.safe_response(
                interaction, embed=embed, view=view, ephemeral=True
            )

        except Exception as e:
            logger.error(f"❌ MFA 管理視圖錯誤: {e}")
            await SafeInteractionHandler.safe_response(
                interaction, f"❌ MFA 管理載入失敗: {str(e)}", ephemeral=True
            )

    @discord.ui.button(label="👥 角色管理", style=discord.ButtonStyle.secondary, row=0)
    async def role_management(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        """角色管理按鈕"""
        try:
            # 檢查權限
            user_id = interaction.user.id
            guild_id = interaction.guild.id if interaction.guild else 0

            if not await rbac_manager.check_permission(
                user_id, guild_id, Permission.USER_MANAGE
            ):
                await SafeInteractionHandler.safe_response(
                    interaction, "❌ 您沒有管理角色的權限", ephemeral=True
                )
                return

            # 獲取角色列表
            roles = await rbac_manager.list_roles()

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
                value=f"系統角色: {system_roles}\n自定義角色: {custom_roles}\n總計: {len(roles)}",
                inline=True,
            )

            # 創建角色管理視圖
            view = RoleManagementView(roles)

            await SafeInteractionHandler.safe_response(
                interaction, embed=embed, view=view, ephemeral=True
            )

        except Exception as e:
            logger.error(f"❌ 角色管理視圖錯誤: {e}")
            await SafeInteractionHandler.safe_response(
                interaction, f"❌ 角色管理載入失敗: {str(e)}", ephemeral=True
            )

    @discord.ui.button(label="🔍 安全審計", style=discord.ButtonStyle.danger, row=0)
    async def security_audit(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        """安全審計按鈕"""
        try:
            # 檢查權限
            user_id = interaction.user.id
            guild_id = interaction.guild.id if interaction.guild else 0

            if not await rbac_manager.check_permission(
                user_id, guild_id, Permission.SYSTEM_ADMIN
            ):
                await SafeInteractionHandler.safe_response(
                    interaction, "❌ 您沒有存取安全審計的權限", ephemeral=True
                )
                return

            embed = discord.Embed(
                title="🔍 安全審計與監控",
                description="查看安全事件和威脅分析",
                color=discord.Color.red(),
            )

            # 威脅統計
            embed.add_field(
                name="🚨 威脅統計",
                value=f"嚴重威脅: {self.security_stats.get('critical_threats', 0)}\n"
                f"高風險事件: {self.security_stats.get('high_risk_events', 0)}\n"
                f"可疑活動: {self.security_stats.get('suspicious_activities', 0)}",
                inline=True,
            )

            # 創建審計視圖
            view = SecurityAuditView(self.security_stats)

            await SafeInteractionHandler.safe_response(
                interaction, embed=embed, view=view, ephemeral=True
            )

        except Exception as e:
            logger.error(f"❌ 安全審計視圖錯誤: {e}")
            await SafeInteractionHandler.safe_response(
                interaction, f"❌ 安全審計載入失敗: {str(e)}", ephemeral=True
            )

    @discord.ui.button(label="🔑 API 密鑰", style=discord.ButtonStyle.secondary, row=1)
    async def api_key_management(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        """API 密鑰管理按鈕"""
        try:
            # 檢查權限
            user_id = interaction.user.id
            guild_id = interaction.guild.id if interaction.guild else 0

            if not await rbac_manager.check_permission(
                user_id, guild_id, Permission.API_ADMIN
            ):
                await SafeInteractionHandler.safe_response(
                    interaction, "❌ 您沒有管理 API 密鑰的權限", ephemeral=True
                )
                return

            embed = discord.Embed(
                title="🔑 API 密鑰管理",
                description="管理系統 API 密鑰和存取控制",
                color=discord.Color.gold(),
            )

            embed.add_field(
                name="🛡️ 安全提醒",
                value="• API 密鑰具有強大權限\n• 定期輪換密鑰\n• 監控使用情況",
                inline=False,
            )

            # 創建 API 密鑰管理視圖
            view = APIKeyManagementView()

            await SafeInteractionHandler.safe_response(
                interaction, embed=embed, view=view, ephemeral=True
            )

        except Exception as e:
            logger.error(f"❌ API 密鑰管理視圖錯誤: {e}")
            await SafeInteractionHandler.safe_response(
                interaction, f"❌ API 密鑰管理載入失敗: {str(e)}", ephemeral=True
            )

    @discord.ui.button(label="📊 系統狀態", style=discord.ButtonStyle.success, row=1)
    async def system_status(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        """系統狀態按鈕"""
        try:
            embed = discord.Embed(
                title="📊 系統安全狀態",
                description="實時安全監控數據",
                color=discord.Color.green(),
                timestamp=datetime.now(),
            )

            # 安全指標
            embed.add_field(
                name="🛡️ 安全指標",
                value=f"威脅等級: {self.security_stats.get('threat_level', '未知')}\n"
                f"MFA 啟用率: {self.security_stats.get('mfa_adoption_rate', 0)}%\n"
                f"日誌完整性: {self.security_stats.get('log_integrity', 100)}%",
                inline=True,
            )

            # 活動統計
            embed.add_field(
                name="📈 活動統計",
                value=f"活躍用戶: {self.security_stats.get('active_users', 0)}\n"
                f"API 呼叫: {self.security_stats.get('api_calls', 0)}\n"
                f"安全事件: {self.security_stats.get('recent_events', 0)}",
                inline=True,
            )

            # 合規狀態
            embed.add_field(
                name="📜 合規狀態",
                value=f"SOC 2: {self.security_stats.get('soc2_status', '未知')}\n"
                f"GDPR: {self.security_stats.get('gdpr_status', '未知')}",
                inline=True,
            )

            await SafeInteractionHandler.safe_response(
                interaction, embed=embed, ephemeral=True
            )

        except Exception as e:
            logger.error(f"❌ 系統狀態視圖錯誤: {e}")
            await SafeInteractionHandler.safe_response(
                interaction, f"❌ 系統狀態載入失敗: {str(e)}", ephemeral=True
            )


class MFASetupView(discord.ui.View):
    """MFA 設置視圖"""

    def __init__(self, setup_result: Dict[str, Any]):
        super().__init__(timeout=300)
        self.setup_result = setup_result

    @discord.ui.button(label="✅ 完成設置", style=discord.ButtonStyle.success)
    async def complete_setup(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        """完成 MFA 設置"""
        await SafeInteractionHandler.safe_response(
            interaction,
            "請在認證應用程式中輸入顯示的驗證碼來完成 MFA 設置。\n使用 `/mfa_verify <驗證碼>` 命令來啟用 MFA。",
            ephemeral=True,
        )

    @discord.ui.button(label="🔄 重新生成", style=discord.ButtonStyle.secondary)
    async def regenerate_setup(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        """重新生成 MFA 設置"""
        try:
            user_id = interaction.user.id
            user_email = f"{interaction.user.name}@discord.local"

            # 重新設置 TOTP
            setup_result = await mfa_manager.setup_totp(user_id, user_email)

            if setup_result["success"]:
                embed = discord.Embed(
                    title="🔄 MFA 重新設置",
                    description="新的 QR Code 已生成",
                    color=discord.Color.blue(),
                )

                embed.add_field(
                    name="🔑 新的密鑰",
                    value=f"```{setup_result['manual_entry_key']}```",
                    inline=False,
                )

                embed.set_image(url=setup_result["qr_code"])

                await SafeInteractionHandler.safe_response(
                    interaction, embed=embed, ephemeral=True
                )
            else:
                await SafeInteractionHandler.safe_response(
                    interaction,
                    f"❌ 重新設置失敗: {setup_result['error']}",
                    ephemeral=True,
                )

        except Exception as e:
            logger.error(f"❌ MFA 重新設置錯誤: {e}")
            await SafeInteractionHandler.safe_response(
                interaction, f"❌ 重新設置失敗: {str(e)}", ephemeral=True
            )


class MFAManagementView(discord.ui.View):
    """MFA 管理視圖"""

    def __init__(self, mfa_status: Dict[str, Any]):
        super().__init__(timeout=300)
        self.mfa_status = mfa_status

        # 根據 MFA 狀態調整按鈕
        if not mfa_status["mfa_enabled"]:
            self.add_item(self.setup_mfa_button())
        else:
            self.add_item(self.regenerate_backup_codes_button())
            self.add_item(self.disable_mfa_button())

    def setup_mfa_button(self):
        """設置 MFA 按鈕"""
        button = discord.ui.Button(
            label="🔐 設置 MFA", style=discord.ButtonStyle.primary
        )

        async def callback(interaction):
            await SafeInteractionHandler.safe_response(
                interaction,
                "請使用 `/mfa_setup` 命令來設置多因素認證。",
                ephemeral=True,
            )

        button.callback = callback
        return button

    def regenerate_backup_codes_button(self):
        """重新生成備用代碼按鈕"""
        button = discord.ui.Button(
            label="🎫 重新生成備用代碼", style=discord.ButtonStyle.secondary
        )

        async def callback(interaction):
            try:
                user_id = interaction.user.id
                backup_codes = await mfa_manager.generate_backup_codes(user_id)

                if backup_codes:
                    codes_text = "\n".join(backup_codes)

                    embed = discord.Embed(
                        title="🎫 新的備用代碼",
                        description="請妥善保存這些備用代碼，每個代碼只能使用一次",
                        color=discord.Color.gold(),
                    )

                    embed.add_field(
                        name="🔑 備用代碼",
                        value=f"```\n{codes_text}\n```",
                        inline=False,
                    )

                    embed.add_field(
                        name="⚠️ 重要提醒",
                        value="• 請將代碼保存在安全的地方\n• 不要將代碼分享給他人\n• 每個代碼只能使用一次",
                        inline=False,
                    )

                    await SafeInteractionHandler.safe_response(
                        interaction, embed=embed, ephemeral=True
                    )
                else:
                    await SafeInteractionHandler.safe_response(
                        interaction, "❌ 備用代碼生成失敗", ephemeral=True
                    )

            except Exception as e:
                logger.error(f"❌ 備用代碼生成錯誤: {e}")
                await SafeInteractionHandler.safe_response(
                    interaction, f"❌ 備用代碼生成失敗: {str(e)}", ephemeral=True
                )

        button.callback = callback
        return button

    def disable_mfa_button(self):
        """停用 MFA 按鈕"""
        button = discord.ui.Button(
            label="❌ 停用 MFA", style=discord.ButtonStyle.danger
        )

        async def callback(interaction):
            # 創建確認視圖
            confirm_view = MFADisableConfirmView()

            embed = discord.Embed(
                title="⚠️ 停用多因素認證",
                description="停用 MFA 將降低您的帳戶安全性",
                color=discord.Color.red(),
            )

            embed.add_field(
                name="🚨 風險警告",
                value="• 帳戶將失去額外的安全保護\n• 建議只在必要時停用\n• 可隨時重新啟用",
                inline=False,
            )

            await SafeInteractionHandler.safe_response(
                interaction, embed=embed, view=confirm_view, ephemeral=True
            )

        button.callback = callback
        return button


class MFADisableConfirmView(discord.ui.View):
    """MFA 停用確認視圖"""

    def __init__(self):
        super().__init__(timeout=60)

    @discord.ui.button(label="✅ 確認停用", style=discord.ButtonStyle.danger)
    async def confirm_disable(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        """確認停用 MFA"""
        await SafeInteractionHandler.safe_response(
            interaction,
            "請輸入您的 MFA 驗證碼來確認停用：使用 `/mfa_disable <驗證碼>` 命令。",
            ephemeral=True,
        )

    @discord.ui.button(label="❌ 取消", style=discord.ButtonStyle.secondary)
    async def cancel_disable(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        """取消停用"""
        await SafeInteractionHandler.safe_response(
            interaction, "✅ 已取消停用 MFA，您的帳戶保持安全保護。", ephemeral=True
        )


class RoleManagementView(discord.ui.View):
    """角色管理視圖"""

    def __init__(self, roles: List):
        super().__init__(timeout=300)
        self.roles = roles

    @discord.ui.button(label="📋 查看所有角色", style=discord.ButtonStyle.primary)
    async def view_all_roles(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        """查看所有角色"""
        try:
            embed = discord.Embed(title="📋 系統角色列表", color=discord.Color.blue())

            # 按層級分組顯示角色
            system_roles = [r for r in self.roles if r.is_system]
            custom_roles = [r for r in self.roles if not r.is_system]

            if system_roles:
                system_role_list = []
                for role in sorted(
                    system_roles, key=lambda x: x.level.value, reverse=True
                ):
                    status = "🟢" if role.is_active else "🔴"
                    system_role_list.append(
                        f"{status} **{role.name}** (級別 {role.level.value})"
                    )

                embed.add_field(
                    name="🏛️ 系統角色",
                    value="\n".join(system_role_list[:10]),  # 限制顯示數量
                    inline=False,
                )

            if custom_roles:
                custom_role_list = []
                for role in sorted(
                    custom_roles, key=lambda x: x.level.value, reverse=True
                ):
                    status = "🟢" if role.is_active else "🔴"
                    custom_role_list.append(
                        f"{status} **{role.name}** (級別 {role.level.value})"
                    )

                embed.add_field(
                    name="👤 自定義角色",
                    value="\n".join(custom_role_list[:10]),  # 限制顯示數量
                    inline=False,
                )

            await SafeInteractionHandler.safe_response(
                interaction, embed=embed, ephemeral=True
            )

        except Exception as e:
            logger.error(f"❌ 角色列表錯誤: {e}")
            await SafeInteractionHandler.safe_response(
                interaction, f"❌ 角色列表載入失敗: {str(e)}", ephemeral=True
            )

    @discord.ui.button(label="➕ 創建角色", style=discord.ButtonStyle.success)
    async def create_role(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        """創建新角色"""
        await SafeInteractionHandler.safe_response(
            interaction,
            "要創建新角色，請聯繫系統管理員或使用管理面板。",
            ephemeral=True,
        )


class SecurityAuditView(discord.ui.View):
    """安全審計視圖"""

    def __init__(self, audit_stats: Dict[str, Any]):
        super().__init__(timeout=300)
        self.audit_stats = audit_stats

    @discord.ui.button(label="🚨 威脅分析", style=discord.ButtonStyle.danger)
    async def threat_analysis(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        """威脅分析"""
        await SafeInteractionHandler.safe_response(
            interaction,
            "🔍 正在進行威脅分析...\n請使用 `/security_audit` 命令查看詳細威脅報告。",
            ephemeral=True,
        )

    @discord.ui.button(label="📊 生成報告", style=discord.ButtonStyle.primary)
    async def generate_report(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        """生成審計報告"""
        await SafeInteractionHandler.safe_response(
            interaction,
            "📋 要生成合規報告，請使用 `/compliance_report` 命令並選擇相應的合規標準。",
            ephemeral=True,
        )


class APIKeyManagementView(discord.ui.View):
    """API 密鑰管理視圖"""

    def __init__(self):
        super().__init__(timeout=300)

    @discord.ui.button(label="🔑 創建 API 密鑰", style=discord.ButtonStyle.primary)
    async def create_api_key(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        """創建 API 密鑰"""
        try:
            # 創建選擇類型的下拉選單
            view = APIKeyTypeSelectionView()

            embed = discord.Embed(
                title="🔑 創建新的 API 密鑰",
                description="請選擇 API 密鑰類型",
                color=discord.Color.blue(),
            )

            embed.add_field(
                name="🔒 密鑰類型說明",
                value="• **唯讀**: 僅限查詢操作\n"
                "• **讀寫**: 可進行資料修改\n"
                "• **管理員**: 完整管理權限\n"
                "• **服務**: 系統間通訊",
                inline=False,
            )

            await SafeInteractionHandler.safe_response(
                interaction, embed=embed, view=view, ephemeral=True
            )

        except Exception as e:
            logger.error(f"❌ API 密鑰創建視圖錯誤: {e}")
            await SafeInteractionHandler.safe_response(
                interaction, f"❌ API 密鑰創建失敗: {str(e)}", ephemeral=True
            )

    @discord.ui.button(label="📋 查看密鑰", style=discord.ButtonStyle.secondary)
    async def view_api_keys(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        """查看現有 API 密鑰"""
        await SafeInteractionHandler.safe_response(
            interaction,
            "📋 API 密鑰列表功能正在開發中，請透過管理面板查看現有密鑰。",
            ephemeral=True,
        )


class APIKeyTypeSelectionView(discord.ui.View):
    """API 密鑰類型選擇視圖"""

    def __init__(self):
        super().__init__(timeout=120)

    @discord.ui.select(
        placeholder="選擇 API 密鑰類型...",
        options=[
            discord.SelectOption(
                label="唯讀密鑰",
                value="read_only",
                description="僅限查詢操作",
                emoji="👁️",
            ),
            discord.SelectOption(
                label="讀寫密鑰",
                value="read_write",
                description="可進行資料修改",
                emoji="✏️",
            ),
            discord.SelectOption(
                label="管理員密鑰",
                value="admin",
                description="完整管理權限",
                emoji="👑",
            ),
            discord.SelectOption(
                label="服務密鑰", value="service", description="系統間通訊", emoji="🔧"
            ),
        ],
    )
    async def select_api_key_type(
        self, interaction: discord.Interaction, select: discord.ui.Select
    ):
        """選擇 API 密鑰類型"""
        try:
            key_type = APIKeyType(select.values[0])
            user_id = interaction.user.id
            guild_id = interaction.guild.id if interaction.guild else 0

            # 創建 API 密鑰
            api_key = await api_security.create_api_key(
                name=f"{interaction.user.name}_{key_type.value}_{datetime.now().strftime('%Y%m%d')}",
                key_type=key_type,
                user_id=user_id,
                guild_id=guild_id,
            )

            if api_key:
                embed = discord.Embed(
                    title="✅ API 密鑰創建成功", color=discord.Color.green()
                )

                embed.add_field(
                    name="🔑 API 密鑰", value=f"```{api_key.key}```", inline=False
                )

                embed.add_field(
                    name="ℹ️ 密鑰資訊",
                    value=f"**名稱**: {api_key.name}\n"
                    f"**類型**: {api_key.key_type.value}\n"
                    f"**創建時間**: {api_key.created_at.strftime('%Y-%m-%d %H:%M')}",
                    inline=True,
                )

                embed.add_field(
                    name="⚠️ 安全提醒",
                    value="• 請妥善保存此密鑰\n• 此密鑰不會再次顯示\n• 如有洩露請立即撤銷",
                    inline=True,
                )

                await SafeInteractionHandler.safe_response(
                    interaction, embed=embed, ephemeral=True
                )
            else:
                await SafeInteractionHandler.safe_response(
                    interaction, "❌ API 密鑰創建失敗", ephemeral=True
                )

        except Exception as e:
            logger.error(f"❌ API 密鑰創建錯誤: {e}")
            await SafeInteractionHandler.safe_response(
                interaction, f"❌ API 密鑰創建失敗: {str(e)}", ephemeral=True
            )
