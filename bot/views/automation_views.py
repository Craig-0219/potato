# bot/views/automation_views.py - 自動化規則視圖組件 v1.7.0
"""
自動化規則互動式視圖組件
提供規則管理、建構器和執行監控的UI介面
"""

import json
import uuid
from typing import Any, Dict, List

import discord

from shared.logger import logger


class AutomationView(discord.ui.View):
    """自動化規則主視圖"""

    def __init__(self, user_id: int, rules: List[Dict[str, Any]]):
        super().__init__(timeout=600)
        self.user_id = user_id
        self.rules = rules

        # 如果有規則，添加選擇器
        if rules:
            self.add_item(RuleSelectDropdown(rules[:25]))  # Discord限制25個選項

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        """檢查互動權限"""
        if interaction.user.id != self.user_id:
            await interaction.response.send_message(
                "❌ 只有命令執行者可以操作此介面", ephemeral=True
            )
            return False
        return True

    @discord.ui.button(label="📊 查看統計", style=discord.ButtonStyle.secondary, row=1)
    async def view_statistics(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        """查看統計資訊"""
        await interaction.response.send_message(
            "請使用 `/automation_stats` 指令查看詳細統計", ephemeral=True
        )

    @discord.ui.button(label="📜 執行記錄", style=discord.ButtonStyle.secondary, row=1)
    async def view_history(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        """查看執行記錄"""
        await interaction.response.send_message(
            "請使用 `/automation_history` 指令查看執行記錄", ephemeral=True
        )

    @discord.ui.button(label="➕ 創建規則", style=discord.ButtonStyle.primary, row=1)
    async def create_rule(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        """創建新規則"""
        modal = RuleBuilderModal("", "", interaction.guild.id, interaction.user.id)
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="🔄 刷新", style=discord.ButtonStyle.secondary, row=1)
    async def refresh(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        """刷新列表"""
        await interaction.response.send_message(
            "請重新使用 `/automation_list` 指令獲取最新資料", ephemeral=True
        )


class RuleSelectDropdown(discord.ui.Select):
    """規則選擇下拉選單"""

    def __init__(self, rules: List[Dict[str, Any]]):
        # 構建選項
        options = []
        for rule in rules[:25]:  # Discord限制25個選項
            status_emoji = {
                "active": "🟢",
                "draft": "⚪",
                "paused": "🟡",
                "disabled": "🔴",
                "error": "❌",
            }.get(rule["status"], "⚪")

            trigger_name = self._get_trigger_display_name(rule["trigger_type"])

            options.append(
                discord.SelectOption(
                    label=f"{rule['name'][:50]}",  # 限制長度
                    value=rule["id"],
                    description=f"{status_emoji} {trigger_name} | 執行: {rule['execution_count']}次",
                    emoji="🤖",
                )
            )

        super().__init__(
            placeholder="選擇要操作的規則...",
            min_values=1,
            max_values=1,
            options=options,
        )

    def _get_trigger_display_name(self, trigger_type: str) -> str:
        """獲取觸發類型顯示名稱"""
        names = {
            "ticket_created": "票券創建",
            "ticket_closed": "票券關閉",
            "user_join": "用戶加入",
            "user_leave": "用戶離開",
            "message_sent": "訊息發送",
            "scheduled": "定時排程",
            "webhook": "Webhook",
        }
        return names.get(trigger_type, trigger_type)

    async def callback(self, interaction: discord.Interaction):
        """處理選擇回調"""
        try:
            rule_id = self.values[0]

            # 創建規則操作視圖
            view = RuleOperationsView(interaction.user.id, rule_id)

            embed = discord.Embed(
                title="🤖 規則操作", description=f"請選擇對規則的操作", color=0x9B59B6
            )

            await interaction.response.send_message(
                embed=embed, view=view, ephemeral=True
            )

        except Exception as e:
            logger.error(f"處理規則選擇失敗: {e}")
            await interaction.response.send_message("❌ 操作失敗", ephemeral=True)


class RuleOperationsView(discord.ui.View):
    """規則操作視圖"""

    def __init__(self, user_id: int, rule_id: str):
        super().__init__(timeout=300)
        self.user_id = user_id
        self.rule_id = rule_id

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        """檢查互動權限"""
        if interaction.user.id != self.user_id:
            await interaction.response.send_message(
                "❌ 只有命令執行者可以操作", ephemeral=True
            )
            return False
        return True

    @discord.ui.button(label="📋 查看詳情", style=discord.ButtonStyle.secondary)
    async def view_details(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        """查看規則詳情"""
        await interaction.response.send_message(
            f"請使用 `/automation_detail {self.rule_id}` 查看詳細資訊", ephemeral=True
        )

    @discord.ui.button(label="🟢 啟用", style=discord.ButtonStyle.success)
    async def enable_rule(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        """啟用規則"""
        await interaction.response.send_message(
            f"請使用 `/automation_toggle {self.rule_id} active` 啟用規則",
            ephemeral=True,
        )

    @discord.ui.button(label="🟡 暫停", style=discord.ButtonStyle.secondary)
    async def pause_rule(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        """暫停規則"""
        await interaction.response.send_message(
            f"請使用 `/automation_toggle {self.rule_id} paused` 暫停規則",
            ephemeral=True,
        )

    @discord.ui.button(label="🔴 停用", style=discord.ButtonStyle.danger)
    async def disable_rule(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        """停用規則"""
        await interaction.response.send_message(
            f"請使用 `/automation_toggle {self.rule_id} disabled` 停用規則",
            ephemeral=True,
        )


class RuleBuilderModal(discord.ui.Modal):
    """規則建構器模態框"""

    def __init__(self, name: str, description: str, guild_id: int, user_id: int):
        super().__init__(title="🤖 創建自動化規則")
        self.guild_id = guild_id
        self.user_id = user_id

        self.name_input = discord.ui.TextInput(
            label="規則名稱",
            placeholder="為您的自動化規則命名...",
            default=name,
            max_length=100,
            required=True,
        )

        self.description_input = discord.ui.TextInput(
            label="規則描述",
            placeholder="描述這個規則的用途...",
            default=description,
            style=discord.TextStyle.paragraph,
            max_length=500,
            required=False,
        )

        self.trigger_input = discord.ui.TextInput(
            label="觸發條件 (JSON格式)",
            placeholder='{"type": "ticket_created", "conditions": []}',
            style=discord.TextStyle.paragraph,
            max_length=1000,
            required=True,
        )

        self.actions_input = discord.ui.TextInput(
            label="執行動作 (JSON格式)",
            placeholder='[{"type": "send_message", "parameters": {"content": "Hello!"}}]',
            style=discord.TextStyle.paragraph,
            max_length=2000,
            required=True,
        )

        self.add_item(self.name_input)
        self.add_item(self.description_input)
        self.add_item(self.trigger_input)
        self.add_item(self.actions_input)

    async def on_submit(self, interaction: discord.Interaction):
        """提交規則創建"""
        try:
            await interaction.response.defer(ephemeral=True)

            # 解析輸入
            try:
                trigger_data = json.loads(self.trigger_input.value)
                actions_data = json.loads(self.actions_input.value)
            except json.JSONDecodeError as e:
                await interaction.followup.send(
                    f"❌ JSON格式錯誤: {str(e)}", ephemeral=True
                )
                return

            # 驗證必要欄位
            if "type" not in trigger_data:
                await interaction.followup.send(
                    "❌ 觸發條件必須包含 'type' 欄位", ephemeral=True
                )
                return

            if not isinstance(actions_data, list) or not actions_data:
                await interaction.followup.send(
                    "❌ 動作必須是非空的陣列", ephemeral=True
                )
                return

            for action in actions_data:
                if "type" not in action or "parameters" not in action:
                    await interaction.followup.send(
                        "❌ 每個動作必須包含 'type' 和 'parameters' 欄位",
                        ephemeral=True,
                    )
                    return

            # 創建規則資料
            rule_data = {
                "id": str(uuid.uuid4()),
                "name": self.name_input.value,
                "description": self.description_input.value,
                "guild_id": self.guild_id,
                "trigger_type": trigger_data["type"],
                "trigger_conditions": trigger_data.get("conditions", []),
                "trigger_parameters": trigger_data.get("parameters", {}),
                "actions": actions_data,
                "created_by": self.user_id,
                "status": "draft",
                "tags": [],
                "priority": 5,
                "cooldown_seconds": trigger_data.get("cooldown_seconds", 0),
            }

            # 儲存規則到資料庫
            from bot.db.automation_dao import AutomationDAO

            dao = AutomationDAO()

            rule_id = await dao.create_rule(rule_data)

            # 同步到引擎
            from bot.services.automation_engine import automation_engine

            await automation_engine.create_rule(rule_data)

            # 創建成功回應
            embed = discord.Embed(
                title="✅ 規則創建成功",
                description=f"自動化規則 **{rule_data['name']}** 已創建",
                color=0x2ECC71,
            )

            embed.add_field(
                name="📋 規則資訊",
                value=f"ID: `{rule_id}`\n"
                f"觸發: {trigger_data['type']}\n"
                f"動作數: {len(actions_data)}\n"
                f"狀態: 草稿 (需手動啟用)",
                inline=False,
            )

            embed.add_field(
                name="⚡ 下一步",
                value=f"使用 `/automation_toggle {rule_id} active` 啟用規則\n"
                f"使用 `/automation_detail {rule_id}` 查看詳情",
                inline=False,
            )

            await interaction.followup.send(embed=embed, ephemeral=True)

        except Exception as e:
            logger.error(f"創建規則失敗: {e}")
            await interaction.followup.send(
                f"❌ 創建規則失敗: {str(e)}", ephemeral=True
            )


class RuleExecutionView(discord.ui.View):
    """規則執行監控視圖"""

    def __init__(self, user_id: int, execution_data: Dict[str, Any]):
        super().__init__(timeout=300)
        self.user_id = user_id
        self.execution_data = execution_data

        # 根據執行狀態調整按鈕
        if execution_data.get("status") == "running":
            self.add_item(self.stop_execution)
        else:
            self.add_item(self.view_results)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        """檢查互動權限"""
        if interaction.user.id != self.user_id:
            await interaction.response.send_message(
                "❌ 只有命令執行者可以操作", ephemeral=True
            )
            return False
        return True

    @discord.ui.button(label="🛑 停止執行", style=discord.ButtonStyle.danger)
    async def stop_execution(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        """停止執行"""
        await interaction.response.send_message(
            "❌ 執行停止功能尚未實現", ephemeral=True
        )

    @discord.ui.button(label="📋 查看結果", style=discord.ButtonStyle.secondary)
    async def view_results(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        """查看執行結果"""
        try:
            execution_id = self.execution_data.get("id")

            embed = discord.Embed(
                title="📋 執行結果",
                description=f"執行ID: {execution_id}",
                color=0x2ECC71 if self.execution_data.get("success") else 0xE74C3C,
            )

            # 基本資訊
            embed.add_field(
                name="📊 執行統計",
                value=f"狀態: {'✅ 成功' if self.execution_data.get('success') else '❌ 失敗'}\n"
                f"執行動作: {self.execution_data.get('executed_actions', 0)}\n"
                f"失敗動作: {self.execution_data.get('failed_actions', 0)}\n"
                f"執行時間: {self.execution_data.get('execution_time', 0):.2f}秒",
                inline=True,
            )

            # 時間資訊
            started_at = self.execution_data.get("started_at")
            completed_at = self.execution_data.get("completed_at")

            if started_at:
                time_info = f"開始: {started_at.strftime('%H:%M:%S')}"
                if completed_at:
                    time_info += f"\n完成: {completed_at.strftime('%H:%M:%S')}"

                embed.add_field(name="🕐 時間資訊", value=time_info, inline=True)

            # 錯誤資訊
            if self.execution_data.get("error_message"):
                embed.add_field(
                    name="❌ 錯誤資訊",
                    value=self.execution_data["error_message"][:500],
                    inline=False,
                )

            await interaction.response.send_message(embed=embed, ephemeral=True)

        except Exception as e:
            logger.error(f"查看執行結果失敗: {e}")
            await interaction.response.send_message("❌ 查看結果失敗", ephemeral=True)

    @discord.ui.button(label="🔄 重新執行", style=discord.ButtonStyle.primary)
    async def re_execute(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        """重新執行規則"""
        await interaction.response.send_message(
            "❌ 重新執行功能尚未實現", ephemeral=True
        )


class TriggerBuilderModal(discord.ui.Modal):
    """觸發器建構器模態框"""

    def __init__(self):
        super().__init__(title="⚡ 設定觸發器")

        self.trigger_type = discord.ui.TextInput(
            label="觸發類型",
            placeholder="ticket_created, user_join, message_sent 等",
            max_length=50,
            required=True,
        )

        self.conditions = discord.ui.TextInput(
            label="觸發條件 (JSON格式)",
            placeholder='[{"field": "priority", "operator": "equals", "value": "high"}]',
            style=discord.TextStyle.paragraph,
            max_length=1000,
            required=False,
        )

        self.parameters = discord.ui.TextInput(
            label="額外參數 (JSON格式)",
            placeholder='{"cooldown_seconds": 300}',
            style=discord.TextStyle.paragraph,
            max_length=500,
            required=False,
        )

        self.add_item(self.trigger_type)
        self.add_item(self.conditions)
        self.add_item(self.parameters)

    async def on_submit(self, interaction: discord.Interaction):
        """提交觸發器設定"""
        try:
            # 解析條件和參數
            conditions = []
            parameters = {}

            if self.conditions.value:
                conditions = json.loads(self.conditions.value)

            if self.parameters.value:
                parameters = json.loads(self.parameters.value)

            # 構建觸發器資料
            trigger_data = {
                "type": self.trigger_type.value,
                "conditions": conditions,
                "parameters": parameters,
            }

            # 顯示確認資訊
            embed = discord.Embed(
                title="⚡ 觸發器設定完成",
                description="觸發器配置已準備就緒",
                color=0xF39C12,
            )

            embed.add_field(
                name="🎯 觸發器資訊",
                value=f"類型: {self.trigger_type.value}\n"
                f"條件數: {len(conditions)}\n"
                f"參數: {len(parameters)} 個",
                inline=False,
            )

            embed.add_field(
                name="📝 JSON配置",
                value=f"```json\n{json.dumps(trigger_data, indent=2, ensure_ascii=False)[:500]}\n```",
                inline=False,
            )

            await interaction.response.send_message(embed=embed, ephemeral=True)

        except json.JSONDecodeError as e:
            await interaction.response.send_message(
                f"❌ JSON格式錯誤: {str(e)}", ephemeral=True
            )
        except Exception as e:
            logger.error(f"設定觸發器失敗: {e}")
            await interaction.response.send_message(
                f"❌ 設定失敗: {str(e)}", ephemeral=True
            )


class ActionBuilderModal(discord.ui.Modal):
    """動作建構器模態框"""

    def __init__(self):
        super().__init__(title="🎯 設定執行動作")

        self.actions = discord.ui.TextInput(
            label="動作列表 (JSON格式)",
            placeholder='[{"type": "send_message", "parameters": {"channel_id": "123", "content": "Hello!"}}]',
            style=discord.TextStyle.paragraph,
            max_length=2000,
            required=True,
        )

        self.add_item(self.actions)

    async def on_submit(self, interaction: discord.Interaction):
        """提交動作設定"""
        try:
            # 解析動作列表
            actions_data = json.loads(self.actions.value)

            if not isinstance(actions_data, list):
                await interaction.response.send_message(
                    "❌ 動作必須是陣列格式", ephemeral=True
                )
                return

            # 驗證動作格式
            for i, action in enumerate(actions_data):
                if (
                    not isinstance(action, dict)
                    or "type" not in action
                    or "parameters" not in action
                ):
                    await interaction.response.send_message(
                        f"❌ 動作 {i+1} 格式錯誤，必須包含 'type' 和 'parameters'",
                        ephemeral=True,
                    )
                    return

            # 顯示確認資訊
            embed = discord.Embed(
                title="🎯 動作設定完成",
                description=f"已設定 {len(actions_data)} 個執行動作",
                color=0x3498DB,
            )

            # 顯示動作摘要
            action_summary = []
            for i, action in enumerate(actions_data[:5]):  # 最多顯示5個
                action_type = action["type"]
                action_name = self._get_action_display_name(action_type)
                action_summary.append(f"{i+1}. {action_name}")

            if len(actions_data) > 5:
                action_summary.append(f"...還有 {len(actions_data) - 5} 個動作")

            embed.add_field(
                name="📋 動作列表", value="\n".join(action_summary), inline=False
            )

            embed.add_field(
                name="📝 JSON配置",
                value=f"```json\n{json.dumps(actions_data, indent=2, ensure_ascii=False)[:500]}\n```",
                inline=False,
            )

            await interaction.response.send_message(embed=embed, ephemeral=True)

        except json.JSONDecodeError as e:
            await interaction.response.send_message(
                f"❌ JSON格式錯誤: {str(e)}", ephemeral=True
            )
        except Exception as e:
            logger.error(f"設定動作失敗: {e}")
            await interaction.response.send_message(
                f"❌ 設定失敗: {str(e)}", ephemeral=True
            )

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
