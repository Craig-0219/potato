# bot/views/webhook_views.py - Webhook整合系統UI組件 v1.7.0
"""
Webhook整合系統的Discord互動介面
提供Webhook管理、配置、測試等功能的視覺化操作界面
"""

import json
from datetime import datetime
from typing import Any, Dict

import discord
from discord import ui

from bot.services.webhook_manager import WebhookEvent, webhook_manager
from bot.utils.embed_builder import EmbedBuilder
from shared.logger import logger


class WebhookManagerView(ui.View):
    """Webhook管理主界面"""

    def __init__(self, user_id: int, guild_id: int, timeout=300):
        super().__init__(timeout=timeout)
        self.user_id = user_id
        self.guild_id = guild_id

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        """檢查互動權限"""
        if interaction.user.id != self.user_id:
            await interaction.response.send_message(
                "❌ 只有原始命令使用者可以操作此介面", ephemeral=True
            )
            return False
        return True

    @ui.button(label="刷新列表", style=discord.ButtonStyle.secondary, emoji="🔄")
    async def refresh_list(self, interaction: discord.Interaction, button: ui.Button):
        """刷新Webhook列表"""
        await interaction.response.defer()

        try:
            webhooks = webhook_manager.get_webhooks(guild_id=self.guild_id)

            embed = EmbedBuilder.build(
                title="📋 Webhook列表 (已刷新)",
                description=f"共 {len(webhooks)} 個Webhook",
                color=0x3498DB,
            )

            if webhooks:
                for webhook in webhooks[:10]:
                    status_emoji = {
                        "active": "✅",
                        "inactive": "⏸️",
                        "paused": "⏸️",
                        "error": "❌",
                    }.get(webhook["status"], "❓")

                    type_emoji = {"outgoing": "📤", "incoming": "📥", "both": "🔄"}.get(
                        webhook["type"], "🔧"
                    )

                    embed.add_field(
                        name=f"{status_emoji} {webhook['name']}",
                        value=f"{type_emoji} {webhook['type'].title()}\n"
                        f"事件: {len(webhook['events'])} 個\n"
                        f"成功率: {webhook['success_count']}/{webhook['success_count'] + webhook['failure_count']}",
                        inline=True,
                    )
            else:
                embed.description = "目前沒有Webhook"

            await interaction.followup.edit_message(interaction.message.id, embed=embed, view=self)

        except Exception as e:
            logger.error(f"刷新Webhook列表失敗: {e}")
            await interaction.followup.send("❌ 刷新失敗，請稍後再試", ephemeral=True)

    @ui.button(label="創建Webhook", style=discord.ButtonStyle.primary, emoji="➕")
    async def create_webhook(self, interaction: discord.Interaction, button: ui.Button):
        """創建新Webhook"""
        modal = WebhookCreateModal(self.guild_id)
        await interaction.response.send_modal(modal)

    @ui.button(label="系統統計", style=discord.ButtonStyle.secondary, emoji="📊")
    async def view_statistics(self, interaction: discord.Interaction, button: ui.Button):
        """查看系統統計"""
        await interaction.response.defer(ephemeral=True)

        try:
            stats = webhook_manager.get_webhook_statistics()

            embed = EmbedBuilder.build(
                title="📊 Webhook系統統計",
                description="系統整體使用統計",
                color=0x9B59B6,
            )

            embed.add_field(
                name="📋 基本統計",
                value=f"總Webhook數: {stats['total_webhooks']}\n"
                f"啟用中: {stats['active_webhooks']}\n"
                f"總請求數: {stats['total_sent'] + stats['total_received']}",
                inline=True,
            )

            embed.add_field(
                name="📊 執行統計",
                value=f"發送請求: {stats['total_sent']}\n"
                f"接收請求: {stats['total_received']}\n"
                f"成功率: {stats['success_rate']:.1f}%",
                inline=True,
            )

            if stats["event_distribution"]:
                event_info = []
                for event, count in list(stats["event_distribution"].items())[:5]:
                    event_info.append(f"• {event}: {count}")

                embed.add_field(name="🎯 熱門事件", value="\n".join(event_info), inline=False)

            await interaction.followup.send(embed=embed, ephemeral=True)

        except Exception as e:
            logger.error(f"獲取統計失敗: {e}")
            await interaction.followup.send("❌ 獲取統計失敗", ephemeral=True)


class WebhookCreateModal(ui.Modal):
    """創建Webhook模態框"""

    def __init__(self, guild_id: int):
        super().__init__(title="創建新Webhook")
        self.guild_id = guild_id

    name = ui.TextInput(
        label="Webhook名稱",
        placeholder="輸入Webhook名稱",
        required=True,
        max_length=100,
    )

    url = ui.TextInput(
        label="目標URL",
        placeholder="https://example.com/webhook",
        required=True,
        max_length=500,
    )

    webhook_type = ui.TextInput(
        label="Webhook類型",
        placeholder="outgoing, incoming, 或 both",
        required=False,
        default="outgoing",
        max_length=20,
    )

    events = ui.TextInput(
        label="監聽事件",
        placeholder="ticket_created,ticket_closed (用逗號分隔)",
        style=discord.TextStyle.paragraph,
        required=False,
        default="custom_event",
    )

    async def on_submit(self, interaction: discord.Interaction):
        """提交創建請求"""
        await interaction.response.defer(ephemeral=True)

        try:
            # 驗證URL格式
            if not self.url.value.startswith(("http://", "https://")):
                await interaction.followup.send(
                    "❌ 請提供有效的URL (必須以http://或https://開頭)", ephemeral=True
                )
                return

            # 驗證Webhook類型
            webhook_type = self.webhook_type.value.lower()
            if webhook_type not in ["outgoing", "incoming", "both"]:
                webhook_type = "outgoing"

            # 解析事件列表
            event_list = []
            if self.events.value:
                events_str = self.events.value.replace(" ", "").split(",")
                for event_str in events_str:
                    if event_str:
                        event_list.append(event_str)

            if not event_list:
                event_list = ["custom_event"]

            # 創建配置數據
            config_data = {
                "name": self.name.value,
                "url": self.url.value,
                "type": webhook_type,
                "events": event_list,
                "guild_id": self.guild_id,
                "created_by": interaction.user.id,
            }

            # 創建Webhook
            webhook_id = await webhook_manager.create_webhook(config_data)

            # 獲取創建的Webhook信息
            webhook_info = webhook_manager.webhooks[webhook_id]

            embed = EmbedBuilder.build(
                title="✅ Webhook已創建",
                description=f"Webhook **{self.name.value}** 已成功創建",
                color=0x2ECC71,
            )

            embed.add_field(
                name="📋 基本資訊",
                value=f"ID: `{webhook_id}`\n"
                f"類型: {webhook_type.title()}\n"
                f"URL: {self.url.value[:50]}{'...' if len(self.url.value) > 50 else ''}\n"
                f"狀態: 啟用",
                inline=False,
            )

            if webhook_info.secret:
                embed.add_field(
                    name="🔐 安全資訊",
                    value=f"密鑰: `{webhook_info.secret[:16]}...`\n" f"簽名驗證: 已啟用",
                    inline=False,
                )

            embed.add_field(name="🎯 監聽事件", value=", ".join(event_list), inline=False)

            await interaction.followup.send(embed=embed, ephemeral=True)

        except Exception as e:
            logger.error(f"創建Webhook失敗: {e}")
            await interaction.followup.send(f"❌ 創建失敗: {str(e)}", ephemeral=True)


class WebhookConfigModal(ui.Modal):
    """Webhook配置模態框"""

    def __init__(self, webhook_id: str, webhook_data: Dict[str, Any]):
        super().__init__(title=f"配置 {webhook_data['name']}")
        self.webhook_id = webhook_id
        self.webhook_data = webhook_data

    events = ui.TextInput(
        label="監聽事件",
        placeholder="ticket_created,ticket_closed (用逗號分隔)",
        style=discord.TextStyle.paragraph,
        required=False,
        default="",
    )

    headers = ui.TextInput(
        label="自定義請求頭",
        placeholder='{"Authorization": "Bearer token", "Content-Type": "application/json"}',
        style=discord.TextStyle.paragraph,
        required=False,
        default="{}",
    )

    timeout = ui.TextInput(label="超時時間 (秒)", placeholder="30", required=False, default="30")

    status = ui.TextInput(
        label="狀態",
        placeholder="active, inactive, paused",
        required=False,
        default="active",
    )

    async def on_submit(self, interaction: discord.Interaction):
        """提交配置更新"""
        await interaction.response.defer(ephemeral=True)

        try:
            updates = {}

            # 更新事件列表
            if self.events.value:
                event_list = []
                events_str = self.events.value.replace(" ", "").split(",")
                for event_str in events_str:
                    if event_str:
                        event_list.append(event_str)
                if event_list:
                    updates["events"] = event_list

            # 更新自定義請求頭
            if self.headers.value and self.headers.value.strip() != "{}":
                try:
                    headers_dict = json.loads(self.headers.value)
                    updates["headers"] = headers_dict
                except json.JSONDecodeError:
                    await interaction.followup.send(
                        "❌ 自定義請求頭格式錯誤，請使用有效的JSON格式", ephemeral=True
                    )
                    return

            # 更新超時時間
            if self.timeout.value:
                try:
                    timeout_val = int(self.timeout.value)
                    if 1 <= timeout_val <= 300:
                        updates["timeout"] = timeout_val
                    else:
                        await interaction.followup.send(
                            "❌ 超時時間必須在1-300秒之間", ephemeral=True
                        )
                        return
                except ValueError:
                    await interaction.followup.send("❌ 超時時間必須是有效數字", ephemeral=True)
                    return

            # 更新狀態
            if self.status.value:
                status_val = self.status.value.lower()
                if status_val in ["active", "inactive", "paused", "error"]:
                    updates["status"] = status_val
                else:
                    await interaction.followup.send(
                        "❌ 狀態必須是 active, inactive, paused 或 error",
                        ephemeral=True,
                    )
                    return

            if not updates:
                await interaction.followup.send("❌ 沒有提供任何更新內容", ephemeral=True)
                return

            # 執行更新
            success = await webhook_manager.update_webhook(self.webhook_id, updates)

            if success:
                embed = EmbedBuilder.build(
                    title="✅ Webhook配置已更新",
                    description=f"Webhook **{self.webhook_data['name']}** 配置已成功更新",
                    color=0x2ECC71,
                )

                update_info = []
                for key, value in updates.items():
                    if key == "events":
                        update_info.append(f"• 事件: {', '.join(value)}")
                    elif key == "headers":
                        update_info.append(f"• 請求頭: {len(value)} 個")
                    elif key == "timeout":
                        update_info.append(f"• 超時時間: {value}秒")
                    elif key == "status":
                        update_info.append(f"• 狀態: {value}")

                if update_info:
                    embed.add_field(name="🔄 更新項目", value="\n".join(update_info), inline=False)

                await interaction.followup.send(embed=embed, ephemeral=True)
            else:
                await interaction.followup.send("❌ 配置更新失敗，請稍後再試", ephemeral=True)

        except Exception as e:
            logger.error(f"更新Webhook配置失敗: {e}")
            await interaction.followup.send(f"❌ 配置更新失敗: {str(e)}", ephemeral=True)


class WebhookDetailView(ui.View):
    """Webhook詳情查看界面"""

    def __init__(self, webhook_id: str, webhook_data: Dict[str, Any], user_id: int, timeout=300):
        super().__init__(timeout=timeout)
        self.webhook_id = webhook_id
        self.webhook_data = webhook_data
        self.user_id = user_id

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        """檢查互動權限"""
        if interaction.user.id != self.user_id:
            await interaction.response.send_message(
                "❌ 只有原始命令使用者可以操作此介面", ephemeral=True
            )
            return False
        return True

    @ui.button(label="編輯配置", style=discord.ButtonStyle.primary, emoji="⚙️")
    async def edit_config(self, interaction: discord.Interaction, button: ui.Button):
        """編輯Webhook配置"""
        # 填入當前配置作為預設值
        modal = WebhookConfigModal(self.webhook_id, self.webhook_data)
        modal.events.default = ", ".join(self.webhook_data.get("events", []))
        modal.headers.default = json.dumps(self.webhook_data.get("headers", {}))
        modal.timeout.default = str(self.webhook_data.get("timeout", 30))
        modal.status.default = self.webhook_data.get("status", "active")

        await interaction.response.send_modal(modal)

    @ui.button(label="測試Webhook", style=discord.ButtonStyle.secondary, emoji="🧪")
    async def test_webhook(self, interaction: discord.Interaction, button: ui.Button):
        """測試Webhook"""
        await interaction.response.defer(ephemeral=True)

        try:
            # 發送測試事件
            test_data = {
                "test": True,
                "message": "This is a test webhook from Potato Bot",
                "timestamp": datetime.utcnow().isoformat(),
                "triggered_by": interaction.user.name,
                "guild_name": (interaction.guild.name if interaction.guild else "Unknown"),
            }

            await webhook_manager.trigger_webhook_event(
                WebhookEvent.CUSTOM_EVENT, self.webhook_data["guild_id"], test_data
            )

            embed = EmbedBuilder.build(
                title="🧪 Webhook測試",
                description=f"測試事件已發送到 **{self.webhook_data['name']}**",
                color=0xF39C12,
            )

            embed.add_field(
                name="📋 測試資料",
                value=f"事件類型: custom_event\n"
                f"觸發者: {interaction.user.name}\n"
                f"時間戳: {datetime.utcnow().strftime('%H:%M:%S UTC')}",
                inline=False,
            )

            embed.add_field(name="ℹ️ 說明", value="請檢查目標端點是否收到測試數據", inline=False)

            await interaction.followup.send(embed=embed, ephemeral=True)

        except Exception as e:
            logger.error(f"測試Webhook失敗: {e}")
            await interaction.followup.send(f"❌ 測試失敗: {str(e)}", ephemeral=True)

    @ui.button(label="查看日誌", style=discord.ButtonStyle.secondary, emoji="📜")
    async def view_logs(self, interaction: discord.Interaction, button: ui.Button):
        """查看執行日誌"""
        await interaction.response.defer(ephemeral=True)

        try:
            from bot.db.webhook_dao import WebhookDAO

            webhook_dao = WebhookDAO()

            logs, total_count = await webhook_dao.get_webhook_logs(
                webhook_id=self.webhook_id, days=7, page=1, page_size=10
            )

            embed = EmbedBuilder.build(
                title=f"📜 {self.webhook_data['name']} 執行日誌",
                description=f"最近7天的執行記錄 (共 {total_count} 筆)",
                color=0x95A5A6,
            )

            if logs:
                for log in logs[:5]:  # 只顯示最近5筆
                    status_emoji = {
                        "success": "✅",
                        "failure": "❌",
                        "timeout": "⏰",
                        "error": "🚫",
                    }.get(log["status"], "❓")

                    embed.add_field(
                        name=f"{status_emoji} {log['event_type']}",
                        value=f"時間: <t:{int(log['created_at'].timestamp())}:R>\n"
                        f"執行時間: {log['execution_time']:.3f}s\n"
                        f"HTTP狀態: {log['http_status'] or 'N/A'}",
                        inline=True,
                    )
            else:
                embed.add_field(name="ℹ️ 無記錄", value="最近7天沒有執行記錄", inline=False)

            await interaction.followup.send(embed=embed, ephemeral=True)

        except Exception as e:
            logger.error(f"獲取日誌失敗: {e}")
            await interaction.followup.send("❌ 獲取日誌失敗", ephemeral=True)

    @ui.button(label="刪除Webhook", style=discord.ButtonStyle.danger, emoji="🗑️")
    async def delete_webhook(self, interaction: discord.Interaction, button: ui.Button):
        """刪除Webhook (需要確認)"""
        embed = EmbedBuilder.build(
            title="⚠️ 確認刪除",
            description=f"確定要刪除Webhook **{self.webhook_data['name']}** 嗎？",
            color=0xE74C3C,
        )

        embed.add_field(
            name="ℹ️ 警告",
            value="此操作無法復原，所有相關設定和統計數據將被永久刪除",
            inline=False,
        )

        view = WebhookDeleteConfirmView(self.webhook_id, self.webhook_data["name"], self.user_id)
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)


class WebhookDeleteConfirmView(ui.View):
    """刪除Webhook確認界面"""

    def __init__(self, webhook_id: str, webhook_name: str, user_id: int, timeout=60):
        super().__init__(timeout=timeout)
        self.webhook_id = webhook_id
        self.webhook_name = webhook_name
        self.user_id = user_id

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        """檢查互動權限"""
        if interaction.user.id != self.user_id:
            await interaction.response.send_message(
                "❌ 只有原始命令使用者可以操作此介面", ephemeral=True
            )
            return False
        return True

    @ui.button(label="確認刪除", style=discord.ButtonStyle.danger, emoji="✅")
    async def confirm_delete(self, interaction: discord.Interaction, button: ui.Button):
        """確認刪除"""
        await interaction.response.defer()

        try:
            success = await webhook_manager.delete_webhook(self.webhook_id)

            if success:
                embed = EmbedBuilder.build(
                    title="✅ Webhook已刪除",
                    description=f"Webhook **{self.webhook_name}** 已成功刪除",
                    color=0x2ECC71,
                )
            else:
                embed = EmbedBuilder.build(
                    title="❌ 刪除失敗",
                    description="刪除Webhook時發生錯誤",
                    color=0xE74C3C,
                )

            await interaction.followup.edit_message(interaction.message.id, embed=embed, view=None)

        except Exception as e:
            logger.error(f"刪除Webhook失敗: {e}")
            embed = EmbedBuilder.build(
                title="❌ 刪除失敗",
                description=f"刪除過程中發生錯誤: {str(e)}",
                color=0xE74C3C,
            )
            await interaction.followup.edit_message(interaction.message.id, embed=embed, view=None)

    @ui.button(label="取消", style=discord.ButtonStyle.secondary, emoji="❌")
    async def cancel_delete(self, interaction: discord.Interaction, button: ui.Button):
        """取消刪除"""
        embed = EmbedBuilder.build(
            title="❌ 已取消", description="Webhook刪除已取消", color=0x95A5A6
        )
        await interaction.response.edit_message(embed=embed, view=None)
