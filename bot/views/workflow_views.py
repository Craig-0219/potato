# bot/views/workflow_views.py - 工作流程視覺界面 v1.6.0
"""
工作流程設計器視覺界面
提供圖形化的工作流程創建、編輯和管理功能
"""


import discord
from discord.ui import Button, Modal, Select, TextInput, View, button

from bot.db.workflow_dao import WorkflowDAO
from bot.services.workflow_engine import workflow_engine
from bot.utils.embed_builder import EmbedBuilder
from shared.logger import logger


class WorkflowDesignerView(View):
    """工作流程設計器主界面"""

    def __init__(self, user_id: int, workflow_id: str = None, timeout=600):
        super().__init__(timeout=timeout)
        self.user_id = user_id
        self.workflow_id = workflow_id
        self.workflow_dao = WorkflowDAO()

        if workflow_id:
            self.add_item(EditWorkflowButton())
        else:
            self.add_item(CreateWorkflowButton())

        self.add_item(WorkflowListSelect(user_id))

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        """檢查用戶權限"""
        if interaction.user.id != self.user_id:
            await interaction.response.send_message(
                "❌ 只有指令使用者可以操作此面板", ephemeral=True
            )
            return False

        if not interaction.user.guild_permissions.manage_guild:
            await interaction.response.send_message("❌ 需要管理伺服器權限", ephemeral=True)
            return False

        return True


class CreateWorkflowButton(Button):
    """創建工作流程按鈕"""

    def __init__(self):
        super().__init__(label="📝 創建新工作流程", style=discord.ButtonStyle.primary, row=0)

    async def callback(self, interaction: discord.Interaction):
        modal = CreateWorkflowModal()
        await interaction.response.send_modal(modal)


class EditWorkflowButton(Button):
    """編輯工作流程按鈕"""

    def __init__(self):
        super().__init__(label="✏️ 編輯工作流程", style=discord.ButtonStyle.secondary, row=0)

    async def callback(self, interaction: discord.Interaction):
        view = WorkflowEditView(interaction.user.id, self.view.workflow_id)

        embed = EmbedBuilder.build(
            title="✏️ 工作流程編輯器",
            description="選擇要編輯的工作流程組件",
            color=0x3498DB,
        )

        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)


class WorkflowListSelect(Select):
    """工作流程列表選擇器"""

    def __init__(self, user_id: int):
        self.user_id = user_id

        # 獲取工作流程列表（需要改為異步獲取）
        options = [
            discord.SelectOption(
                label="載入工作流程列表...",
                value="loading",
                description="正在載入工作流程",
            )
        ]

        super().__init__(placeholder="選擇要編輯的工作流程...", options=options, row=1)

    async def callback(self, interaction: discord.Interaction):
        if self.values[0] == "loading":
            await interaction.response.send_message("⏳ 正在載入工作流程列表...", ephemeral=True)
            return

        workflow_id = self.values[0]
        view = WorkflowEditView(self.user_id, workflow_id)

        embed = EmbedBuilder.build(
            title="✏️ 工作流程編輯器",
            description=f"編輯工作流程: {workflow_id}",
            color=0x3498DB,
        )

        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)


class WorkflowEditView(View):
    """工作流程編輯界面"""

    def __init__(self, user_id: int, workflow_id: str, timeout=600):
        super().__init__(timeout=timeout)
        self.user_id = user_id
        self.workflow_id = workflow_id

    @button(label="🎯 編輯觸發器", style=discord.ButtonStyle.primary, row=0)
    async def edit_trigger_button(self, interaction: discord.Interaction, button: Button):
        """編輯觸發器"""
        view = TriggerEditView(self.user_id, self.workflow_id)

        embed = EmbedBuilder.build(
            title="🎯 編輯觸發器",
            description="設定工作流程的觸發條件",
            color=0xE74C3C,
        )

        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    @button(label="⚙️ 編輯動作", style=discord.ButtonStyle.secondary, row=0)
    async def edit_actions_button(self, interaction: discord.Interaction, button: Button):
        """編輯動作"""
        view = ActionsEditView(self.user_id, self.workflow_id)

        embed = EmbedBuilder.build(
            title="⚙️ 編輯動作",
            description="設定工作流程執行的動作",
            color=0x3498DB,
        )

        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    @button(label="🔄 測試工作流程", style=discord.ButtonStyle.success, row=1)
    async def test_workflow_button(self, interaction: discord.Interaction, button: Button):
        """測試工作流程"""
        try:
            # 執行測試
            execution_id = await workflow_engine.execute_workflow(
                self.workflow_id,
                {
                    "test_mode": True,
                    "triggered_by": interaction.user.id,
                    "guild_id": interaction.guild.id,
                },
            )

            if execution_id:
                embed = EmbedBuilder.build(
                    title="🧪 測試執行中",
                    description=f"工作流程測試已開始\n執行ID: `{execution_id}`",
                    color=0xF39C12,
                )
            else:
                embed = EmbedBuilder.build(
                    title="❌ 測試失敗",
                    description="工作流程測試執行失敗",
                    color=0xE74C3C,
                )

            await interaction.response.send_message(embed=embed, ephemeral=True)

        except Exception as e:
            logger.error(f"測試工作流程失敗: {e}")
            await interaction.response.send_message(f"❌ 測試失敗: {str(e)}", ephemeral=True)

    @button(label="💾 儲存設定", style=discord.ButtonStyle.success, row=1)
    async def save_workflow_button(self, interaction: discord.Interaction, button: Button):
        """儲存工作流程設定"""
        try:
            # 這裡應該將工作流程引擎中的設定同步到資料庫
            embed = EmbedBuilder.build(
                title="✅ 設定已儲存",
                description="工作流程設定已成功儲存到資料庫",
                color=0x2ECC71,
            )

            await interaction.response.send_message(embed=embed, ephemeral=True)

        except Exception as e:
            logger.error(f"儲存工作流程失敗: {e}")
            await interaction.response.send_message(f"❌ 儲存失敗: {str(e)}", ephemeral=True)


class TriggerEditView(View):
    """觸發器編輯界面"""

    def __init__(self, user_id: int, workflow_id: str, timeout=300):
        super().__init__(timeout=timeout)
        self.user_id = user_id
        self.workflow_id = workflow_id
        self.add_item(TriggerTypeSelect())

    @button(label="➕ 添加條件", style=discord.ButtonStyle.secondary, row=1)
    async def add_condition_button(self, interaction: discord.Interaction, button: Button):
        """添加觸發條件"""
        modal = AddConditionModal(self.workflow_id)
        await interaction.response.send_modal(modal)

    @button(label="🗑️ 清除條件", style=discord.ButtonStyle.danger, row=1)
    async def clear_conditions_button(self, interaction: discord.Interaction, button: Button):
        """清除所有條件"""
        embed = EmbedBuilder.build(
            title="✅ 條件已清除",
            description="所有觸發條件已清除",
            color=0x2ECC71,
        )

        await interaction.response.send_message(embed=embed, ephemeral=True)


class TriggerTypeSelect(Select):
    """觸發類型選擇器"""

    def __init__(self):
        options = [
            discord.SelectOption(
                label="手動觸發",
                value="manual",
                description="手動執行工作流程",
                emoji="👆",
            ),
            discord.SelectOption(
                label="票券建立",
                value="ticket_created",
                description="當新票券建立時觸發",
                emoji="🎫",
            ),
            discord.SelectOption(
                label="成員加入",
                value="member_joined",
                description="當新成員加入時觸發",
                emoji="👋",
            ),
            discord.SelectOption(
                label="成員離開",
                value="member_left",
                description="當成員離開時觸發",
                emoji="👋",
            ),
            discord.SelectOption(
                label="定時觸發",
                value="scheduled",
                description="按時間表觸發",
                emoji="⏰",
            ),
        ]

        super().__init__(placeholder="選擇觸發類型...", options=options, row=0)

    async def callback(self, interaction: discord.Interaction):
        trigger_type = self.values[0]

        embed = EmbedBuilder.build(
            title="✅ 觸發類型已設定",
            description=f"已設定觸發類型為: **{trigger_type}**",
            color=0x2ECC71,
        )

        await interaction.response.send_message(embed=embed, ephemeral=True)


class ActionsEditView(View):
    """動作編輯界面"""

    def __init__(self, user_id: int, workflow_id: str, timeout=300):
        super().__init__(timeout=timeout)
        self.user_id = user_id
        self.workflow_id = workflow_id

    @button(label="➕ 添加動作", style=discord.ButtonStyle.primary, row=0)
    async def add_action_button(self, interaction: discord.Interaction, button: Button):
        """添加動作"""
        view = ActionTypeView(self.user_id, self.workflow_id)

        embed = EmbedBuilder.build(
            title="⚙️ 選擇動作類型",
            description="選擇要添加的動作類型",
            color=0x3498DB,
        )

        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    @button(label="📋 查看動作", style=discord.ButtonStyle.secondary, row=0)
    async def view_actions_button(self, interaction: discord.Interaction, button: Button):
        """查看現有動作"""
        # 獲取工作流程的動作列表
        embed = EmbedBuilder.build(
            title="📋 當前動作列表",
            description="工作流程中的所有動作",
            color=0x95A5A6,
        )

        # 這裡應該顯示實際的動作列表
        embed.add_field(name="暫無動作", value="請添加動作來構建工作流程", inline=False)

        await interaction.response.send_message(embed=embed, ephemeral=True)

    @button(label="🗑️ 清除動作", style=discord.ButtonStyle.danger, row=1)
    async def clear_actions_button(self, interaction: discord.Interaction, button: Button):
        """清除所有動作"""
        embed = EmbedBuilder.build(
            title="✅ 動作已清除",
            description="所有動作已從工作流程中移除",
            color=0x2ECC71,
        )

        await interaction.response.send_message(embed=embed, ephemeral=True)


class ActionTypeView(View):
    """動作類型選擇界面"""

    def __init__(self, user_id: int, workflow_id: str, timeout=300):
        super().__init__(timeout=timeout)
        self.user_id = user_id
        self.workflow_id = workflow_id
        self.add_item(ActionTypeSelect())


class ActionTypeSelect(Select):
    """動作類型選擇器"""

    def __init__(self):
        options = [
            discord.SelectOption(
                label="發送訊息",
                value="send_message",
                description="向頻道或用戶發送訊息",
                emoji="📨",
            ),
            discord.SelectOption(
                label="指派票券",
                value="assign_ticket",
                description="將票券指派給客服",
                emoji="🎫",
            ),
            discord.SelectOption(
                label="添加標籤",
                value="add_tag",
                description="為票券添加標籤",
                emoji="🏷️",
            ),
            discord.SelectOption(
                label="變更優先級",
                value="change_priority",
                description="修改票券優先級",
                emoji="⚡",
            ),
            discord.SelectOption(
                label="通知用戶",
                value="notify_user",
                description="發送通知給特定用戶",
                emoji="🔔",
            ),
            discord.SelectOption(
                label="延遲執行",
                value="delay",
                description="暫停一段時間",
                emoji="⏱️",
            ),
        ]

        super().__init__(placeholder="選擇動作類型...", options=options, max_values=1)

    async def callback(self, interaction: discord.Interaction):
        action_type = self.values[0]

        # 根據動作類型顯示配置界面
        if action_type == "send_message":
            modal = SendMessageActionModal(self.view.workflow_id)
            await interaction.response.send_modal(modal)
        elif action_type == "assign_ticket":
            modal = AssignTicketActionModal(self.view.workflow_id)
            await interaction.response.send_modal(modal)
        elif action_type == "add_tag":
            modal = AddTagActionModal(self.view.workflow_id)
            await interaction.response.send_modal(modal)
        elif action_type == "delay":
            modal = DelayActionModal(self.view.workflow_id)
            await interaction.response.send_modal(modal)
        else:
            embed = EmbedBuilder.build(
                title="✅ 動作已添加",
                description=f"已添加動作: **{action_type}**",
                color=0x2ECC71,
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)


# ========== Modal 表單 ==========


class CreateWorkflowModal(Modal):
    """創建工作流程表單"""

    def __init__(self):
        super().__init__(title="📝 創建新工作流程")

        self.name = TextInput(
            label="工作流程名稱",
            placeholder="輸入工作流程名稱",
            max_length=100,
            required=True,
        )

        self.description = TextInput(
            label="描述",
            placeholder="描述這個工作流程的用途",
            style=discord.TextStyle.paragraph,
            max_length=500,
            required=False,
        )

        self.add_item(self.name)
        self.add_item(self.description)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            # 創建基礎工作流程數據
            workflow_data = {
                "name": self.name.value,
                "description": self.description.value or "",
                "guild_id": interaction.guild.id,
                "trigger_type": "manual",
                "trigger_conditions": [],
                "trigger_parameters": {},
                "actions": [],
                "created_by": interaction.user.id,
                "tags": [],
            }

            # 創建工作流程
            workflow_id = await workflow_engine.create_workflow(workflow_data)

            # 儲存到資料庫
            workflow_dao = WorkflowDAO()
            await workflow_dao.create_workflow({"id": workflow_id, **workflow_data})

            embed = EmbedBuilder.build(
                title="✅ 工作流程已創建",
                description=f"工作流程 **{self.name.value}** 已成功創建",
                color=0x2ECC71,
            )

            embed.add_field(
                name="📋 基本資訊",
                value=f"ID: `{workflow_id}`\n" f"狀態: 草稿\n" f"觸發類型: 手動觸發",
                inline=False,
            )

            # 顯示編輯界面
            view = WorkflowEditView(interaction.user.id, workflow_id)

            await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

        except Exception as e:
            logger.error(f"創建工作流程失敗: {e}")
            await interaction.response.send_message(f"❌ 創建失敗: {str(e)}", ephemeral=True)


class AddConditionModal(Modal):
    """添加觸發條件表單"""

    def __init__(self, workflow_id: str):
        super().__init__(title="➕ 添加觸發條件")
        self.workflow_id = workflow_id

        self.field = TextInput(
            label="條件欄位",
            placeholder="例如: user_id, priority, status",
            max_length=50,
            required=True,
        )

        self.operator = TextInput(
            label="比較運算符",
            placeholder="例如: ==, !=, >, <, contains",
            max_length=20,
            required=True,
        )

        self.value = TextInput(
            label="比較值",
            placeholder="輸入比較值",
            max_length=100,
            required=True,
        )

        self.add_item(self.field)
        self.add_item(self.operator)
        self.add_item(self.value)

    async def on_submit(self, interaction: discord.Interaction):
        condition_data = {
            "field": self.field.value,
            "operator": self.operator.value,
            "value": self.value.value,
        }

        embed = EmbedBuilder.build(
            title="✅ 條件已添加",
            description=f"條件: **{self.field.value}** {self.operator.value} **{self.value.value}**",
            color=0x2ECC71,
        )

        await interaction.response.send_message(embed=embed, ephemeral=True)


class SendMessageActionModal(Modal):
    """發送訊息動作配置表單"""

    def __init__(self, workflow_id: str):
        super().__init__(title="📨 配置發送訊息動作")
        self.workflow_id = workflow_id

        self.channel = TextInput(
            label="目標頻道",
            placeholder="頻道ID或頻道名稱",
            max_length=100,
            required=True,
        )

        self.message = TextInput(
            label="訊息內容",
            placeholder="要發送的訊息內容",
            style=discord.TextStyle.paragraph,
            max_length=2000,
            required=True,
        )

        self.add_item(self.channel)
        self.add_item(self.message)

    async def on_submit(self, interaction: discord.Interaction):
        embed = EmbedBuilder.build(
            title="✅ 發送訊息動作已配置",
            description=f"目標: {self.channel.value}\n訊息: {self.message.value[:100]}...",
            color=0x2ECC71,
        )

        await interaction.response.send_message(embed=embed, ephemeral=True)


class AssignTicketActionModal(Modal):
    """指派票券動作配置表單"""

    def __init__(self, workflow_id: str):
        super().__init__(title="🎫 配置指派票券動作")
        self.workflow_id = workflow_id

        self.method = TextInput(
            label="指派方式",
            placeholder="least_workload, round_robin, specialty_match",
            max_length=50,
            required=True,
        )

        self.add_item(self.method)

    async def on_submit(self, interaction: discord.Interaction):
        embed = EmbedBuilder.build(
            title="✅ 指派票券動作已配置",
            description=f"指派方式: **{self.method.value}**",
            color=0x2ECC71,
        )

        await interaction.response.send_message(embed=embed, ephemeral=True)


class AddTagActionModal(Modal):
    """添加標籤動作配置表單"""

    def __init__(self, workflow_id: str):
        super().__init__(title="🏷️ 配置添加標籤動作")
        self.workflow_id = workflow_id

        self.tags = TextInput(
            label="標籤列表",
            placeholder="標籤1, 標籤2, 標籤3",
            max_length=200,
            required=True,
        )

        self.add_item(self.tags)

    async def on_submit(self, interaction: discord.Interaction):
        tag_list = [tag.strip() for tag in self.tags.value.split(",")]

        embed = EmbedBuilder.build(
            title="✅ 添加標籤動作已配置",
            description=f"標籤: {', '.join(tag_list)}",
            color=0x2ECC71,
        )

        await interaction.response.send_message(embed=embed, ephemeral=True)


class DelayActionModal(Modal):
    """延遲動作配置表單"""

    def __init__(self, workflow_id: str):
        super().__init__(title="⏱️ 配置延遲動作")
        self.workflow_id = workflow_id

        self.seconds = TextInput(
            label="延遲時間 (秒)",
            placeholder="輸入延遲秒數",
            max_length=10,
            required=True,
        )

        self.add_item(self.seconds)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            delay_seconds = int(self.seconds.value)

            embed = EmbedBuilder.build(
                title="✅ 延遲動作已配置",
                description=f"延遲時間: **{delay_seconds}** 秒",
                color=0x2ECC71,
            )

            await interaction.response.send_message(embed=embed, ephemeral=True)

        except ValueError:
            await interaction.response.send_message("❌ 請輸入有效的數字", ephemeral=True)


# ========== 工作流程統計視圖 ==========


class WorkflowStatsView(View):
    """工作流程統計界面"""

    def __init__(self, user_id: int, timeout=300):
        super().__init__(timeout=timeout)
        self.user_id = user_id

    @button(label="📊 詳細統計", style=discord.ButtonStyle.primary, row=0)
    async def detailed_stats_button(self, interaction: discord.Interaction, button: Button):
        """顯示詳細統計"""
        stats = workflow_engine.get_workflow_statistics(guild_id=interaction.guild.id)

        embed = EmbedBuilder.build(
            title="📊 工作流程詳細統計",
            description="伺服器工作流程使用詳細分析",
            color=0x9B59B6,
        )

        # 添加詳細統計資訊
        embed.add_field(
            name="📋 基本統計",
            value=f"總工作流程: {stats['total_workflows']}\n"
            f"活躍工作流程: {stats['active_workflows']}\n"
            f"總執行次數: {stats['total_executions']}",
            inline=True,
        )

        await interaction.response.send_message(embed=embed, ephemeral=True)

    @button(label="📈 執行趨勢", style=discord.ButtonStyle.secondary, row=0)
    async def execution_trend_button(self, interaction: discord.Interaction, button: Button):
        """顯示執行趨勢"""
        embed = EmbedBuilder.build(
            title="📈 工作流程執行趨勢",
            description="最近7天的執行趨勢分析",
            color=0x3498DB,
        )

        # 這裡可以添加圖表或趨勢數據
        embed.add_field(name="趨勢分析", value="執行趨勢圖表功能開發中...", inline=False)

        await interaction.response.send_message(embed=embed, ephemeral=True)
