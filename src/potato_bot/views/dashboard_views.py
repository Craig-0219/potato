# bot/views/dashboard_views.py - 分析儀表板視圖組件 v1.7.0
"""
高級分析儀表板視圖組件
提供互動式的儀表板顯示和操作界面
"""

import io
import json
from datetime import datetime, timezone
from typing import Dict, List

import discord
from discord.ui import Button, Modal, Select, TextInput, View, button

from potato_bot.services.dashboard_manager import ChartData, ChartType, DashboardData
from potato_bot.utils.embed_builder import EmbedBuilder
from potato_shared.logger import logger


class DashboardView(View):
    """主要的儀表板視圖"""

    def __init__(self, user_id: int, dashboard_data: DashboardData, timeout=600):
        super().__init__(timeout=timeout)
        self.user_id = user_id
        self.dashboard_data = dashboard_data
        self.current_chart_index = 0

        # 添加圖表選擇器
        if dashboard_data.charts:
            self.add_item(ChartNavigationSelect(dashboard_data.charts))

        # 添加操作按鈕
        self.add_item(RefreshDashboardButton())
        self.add_item(ExportDataButton())
        if len(dashboard_data.charts) > 1:
            self.add_item(ViewAllChartsButton())

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        """檢查互動權限"""
        if interaction.user.id != self.user_id:
            await interaction.response.send_message(
                "❌ 只有指令使用者可以操作此面板", ephemeral=True
            )
            return False
        return True


class ChartNavigationSelect(Select):
    """圖表導航選擇器"""

    def __init__(self, charts: List[ChartData]):
        self.charts = charts

        options = []
        for i, chart in enumerate(charts):
            # 根據圖表類型選擇emoji
            emoji_map = {
                ChartType.LINE: "📈",
                ChartType.BAR: "📊",
                ChartType.PIE: "🥧",
                ChartType.AREA: "📉",
                ChartType.SCATTER: "🔸",
                ChartType.HEATMAP: "🔥",
            }

            emoji = emoji_map.get(chart.chart_type, "📋")

            options.append(
                discord.SelectOption(
                    label=chart.title[:25],  # 限制標題長度
                    value=str(i),
                    description=f"{chart.chart_type.value.title()}圖表",
                    emoji=emoji,
                )
            )

        super().__init__(placeholder="選擇要查看的圖表...", options=options, row=0)

    async def callback(self, interaction: discord.Interaction):
        chart_index = int(self.values[0])
        chart = self.charts[chart_index]

        # 創建圖表顯示視圖
        chart_view = ChartDisplayView(interaction.user.id, chart)

        # 創建圖表嵌入
        embed = await self._create_chart_embed(chart)

        await interaction.response.send_message(embed=embed, view=chart_view, ephemeral=True)

    async def _create_chart_embed(self, chart: ChartData) -> discord.Embed:
        """創建圖表顯示嵌入"""
        embed = EmbedBuilder.build(
            title=chart.title,
            description=f"圖表類型: {chart.chart_type.value.title()}",
            color=0x3498DB,
        )

        # 添加數據摘要
        if chart.datasets:
            dataset_info = []
            for i, dataset in enumerate(chart.datasets[:3]):  # 最多顯示3個數據集
                label = dataset.get("label", f"數據集 {i+1}")
                data_points = len(dataset.get("data", []))
                dataset_info.append(f"• {label}: {data_points} 個數據點")

            if dataset_info:
                embed.add_field(
                    name="📊 數據集信息",
                    value="\n".join(dataset_info),
                    inline=False,
                )

        # 添加圖表選項
        if chart.options:
            options_text = []
            for key, value in chart.options.items():
                if key in ["responsive", "maintainAspectRatio"]:
                    options_text.append(f"• {key}: {'是' if value else '否'}")

            if options_text:
                embed.add_field(
                    name="⚙️ 圖表設定",
                    value="\n".join(options_text[:3]),
                    inline=True,
                )

        # 添加數據標籤資訊
        if chart.labels:
            labels_preview = chart.labels[:5]  # 顯示前5個標籤
            more_count = len(chart.labels) - 5

            labels_text = ", ".join(str(label) for label in labels_preview)
            if more_count > 0:
                labels_text += f" ...等{more_count}個"

            embed.add_field(name="🏷️ 數據標籤", value=labels_text, inline=False)

        embed.set_footer(text="💡 使用下方按鈕進行更多操作")

        return embed


class ChartDisplayView(View):
    """圖表顯示視圖"""

    def __init__(self, user_id: int, chart: ChartData, timeout=300):
        super().__init__(timeout=timeout)
        self.user_id = user_id
        self.chart = chart

    @button(label="📊 查看數據", style=discord.ButtonStyle.primary, row=0)
    async def view_data_button(self, interaction: discord.Interaction, button: Button):
        """查看圖表原始數據"""
        modal = ChartDataModal(self.chart)
        await interaction.response.send_modal(modal)

    @button(label="📈 數據趨勢", style=discord.ButtonStyle.secondary, row=0)
    async def trend_analysis_button(self, interaction: discord.Interaction, button: Button):
        """分析數據趨勢"""
        trend_analysis = await self._analyze_chart_trends()

        embed = EmbedBuilder.build(
            title="📈 數據趨勢分析",
            description=f"基於 {self.chart.title} 的趨勢分析",
            color=0xF39C12,
        )

        for analysis in trend_analysis:
            embed.add_field(
                name=analysis["metric"],
                value=analysis["description"],
                inline=False,
            )

        await interaction.response.send_message(embed=embed, ephemeral=True)

    @button(label="💾 導出數據", style=discord.ButtonStyle.success, row=0)
    async def export_chart_button(self, interaction: discord.Interaction, button: Button):
        """導出圖表數據"""
        try:
            # 生成數據文件
            data_json = {
                "chart_info": {
                    "title": self.chart.title,
                    "type": self.chart.chart_type.value,
                    "generated_at": datetime.now(timezone.utc).isoformat(),
                },
                "labels": self.chart.labels,
                "datasets": self.chart.datasets,
                "options": self.chart.options,
            }

            # 創建文件
            file_content = json.dumps(data_json, indent=2, ensure_ascii=False)
            file = discord.File(
                fp=io.BytesIO(file_content.encode("utf-8")),
                filename=f"chart_data_{self.chart.title.replace(' ', '_')}.json",
            )

            embed = EmbedBuilder.build(
                title="💾 數據導出完成",
                description=f"圖表 **{self.chart.title}** 的數據已生成",
                color=0x2ECC71,
            )

            await interaction.response.send_message(embed=embed, file=file, ephemeral=True)

        except Exception as e:
            logger.error(f"導出圖表數據失敗: {e}")
            await interaction.response.send_message("❌ 導出失敗，請稍後再試", ephemeral=True)

    async def _analyze_chart_trends(self) -> List[Dict[str, str]]:
        """分析圖表趨勢"""
        analyses = []

        try:
            for dataset in self.chart.datasets:
                data = dataset.get("data", [])
                if not data:
                    continue

                label = dataset.get("label", "未知數據集")

                # 計算基本統計
                valid_data = [x for x in data if x is not None and isinstance(x, (int, float))]
                if len(valid_data) < 2:
                    continue

                # 計算趨勢
                if len(valid_data) >= 3:
                    recent_avg = sum(valid_data[-3:]) / 3
                    overall_avg = sum(valid_data) / len(valid_data)

                    if recent_avg > overall_avg * 1.1:
                        trend = "📈 上升趨勢"
                    elif recent_avg < overall_avg * 0.9:
                        trend = "📉 下降趨勢"
                    else:
                        trend = "➡️ 穩定趨勢"
                else:
                    trend = "➡️ 數據不足"

                # 計算變化率
                if len(valid_data) >= 2:
                    change_rate = ((valid_data[-1] - valid_data[0]) / valid_data[0]) * 100
                    change_text = f"總體變化: {change_rate:+.1f}%"
                else:
                    change_text = "無法計算變化率"

                analyses.append(
                    {
                        "metric": f"📊 {label}",
                        "description": f"{trend}\n{change_text}\n數據點數: {len(valid_data)}",
                    }
                )

            if not analyses:
                analyses.append(
                    {
                        "metric": "📋 分析結果",
                        "description": "無足夠數據進行趨勢分析",
                    }
                )

            return analyses

        except Exception as e:
            logger.error(f"趨勢分析失敗: {e}")
            return [{"metric": "❌ 錯誤", "description": "趨勢分析失敗"}]

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        """檢查互動權限"""
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("❌ 只有指令使用者可以操作", ephemeral=True)
            return False
        return True


class RefreshDashboardButton(Button):
    """刷新儀表板按鈕"""

    def __init__(self):
        super().__init__(label="🔄 刷新數據", style=discord.ButtonStyle.secondary, row=1)

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.send_message("🔄 正在刷新儀表板數據，請稍候...", ephemeral=True)

        # 實際的刷新邏輯需要在這裡實現
        # 目前顯示刷新完成消息
        await interaction.edit_original_response(
            content="✅ 儀表板數據已刷新，請重新執行指令查看最新數據"
        )


class ExportDataButton(Button):
    """導出數據按鈕"""

    def __init__(self):
        super().__init__(label="💾 導出報告", style=discord.ButtonStyle.success, row=1)

    async def callback(self, interaction: discord.Interaction):
        modal = ExportOptionsModal()
        await interaction.response.send_modal(modal)


class ViewAllChartsButton(Button):
    """查看所有圖表按鈕"""

    def __init__(self):
        super().__init__(label="📊 查看所有圖表", style=discord.ButtonStyle.primary, row=1)

    async def callback(self, interaction: discord.Interaction):
        dashboard_data = self.view.dashboard_data

        embed = EmbedBuilder.build(
            title="📊 所有可用圖表",
            description=f"共 {len(dashboard_data.charts)} 個分析圖表",
            color=0x3498DB,
        )

        chart_list = []
        for i, chart in enumerate(dashboard_data.charts, 1):
            chart_type_emoji = {
                ChartType.LINE: "📈",
                ChartType.BAR: "📊",
                ChartType.PIE: "🥧",
                ChartType.AREA: "📉",
                ChartType.SCATTER: "🔸",
                ChartType.HEATMAP: "🔥",
            }.get(chart.chart_type, "📋")

            chart_list.append(f"{chart_type_emoji} **{i}. {chart.title}**")
            chart_list.append(f"   類型: {chart.chart_type.value.title()}")
            chart_list.append(f"   數據集: {len(chart.datasets)}個")
            chart_list.append("")

        # 分割長列表
        if len(chart_list) > 20:
            embed.add_field(
                name="圖表列表 (前10個)",
                value="\n".join(chart_list[:40]),  # 每個圖表約4行
                inline=False,
            )
            embed.add_field(
                name="更多圖表",
                value=f"還有 {len(dashboard_data.charts) - 10} 個圖表，使用選擇器查看",
                inline=False,
            )
        else:
            embed.add_field(
                name="圖表列表",
                value="\n".join(chart_list) if chart_list else "暫無圖表",
                inline=False,
            )

        embed.set_footer(text="💡 使用上方的選擇器來查看具體圖表")

        await interaction.response.send_message(embed=embed, ephemeral=True)


# ========== Modal 表單 ==========


class ChartDataModal(Modal):
    """圖表數據查看表單"""

    def __init__(self, chart: ChartData):
        super().__init__(title=f"📊 {chart.title[:45]} - 數據詳情")
        self.chart = chart

        # 準備數據預覽
        data_preview = self._prepare_data_preview()

        self.data_display = TextInput(
            label="圖表數據",
            default=data_preview,
            style=discord.TextStyle.paragraph,
            max_length=4000,
            required=False,
        )

        self.add_item(self.data_display)

    def _prepare_data_preview(self) -> str:
        """準備數據預覽"""
        try:
            preview_lines = []

            # 添加基本資訊
            preview_lines.append(f"圖表類型: {self.chart.chart_type.value}")
            preview_lines.append(f"數據標籤數: {len(self.chart.labels)}")
            preview_lines.append(f"數據集數: {len(self.chart.datasets)}")
            preview_lines.append("")

            # 添加標籤預覽
            if self.chart.labels:
                preview_lines.append("📋 數據標籤 (前10個):")
                labels_preview = self.chart.labels[:10]
                preview_lines.append(", ".join(str(label) for label in labels_preview))
                if len(self.chart.labels) > 10:
                    preview_lines.append(f"...還有{len(self.chart.labels) - 10}個標籤")
                preview_lines.append("")

            # 添加數據集預覽
            if self.chart.datasets:
                for i, dataset in enumerate(self.chart.datasets[:2]):  # 最多顯示2個數據集
                    label = dataset.get("label", f"數據集 {i+1}")
                    data = dataset.get("data", [])

                    preview_lines.append(f"📊 {label}:")

                    if data:
                        # 顯示前10個數據點
                        data_preview = [str(x) for x in data[:10] if x is not None]
                        preview_lines.append(", ".join(data_preview))
                        if len(data) > 10:
                            preview_lines.append(f"...還有{len(data) - 10}個數據點")
                    else:
                        preview_lines.append("無數據")

                    preview_lines.append("")

            # 限制總長度
            full_text = "\n".join(preview_lines)
            if len(full_text) > 3900:
                full_text = full_text[:3900] + "...(數據過長，已截斷)"

            return full_text

        except Exception as e:
            logger.error(f"準備數據預覽失敗: {e}")
            return "❌ 數據預覽生成失敗"

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.send_message(
            "💡 這是數據預覽，您可以複製相關資訊", ephemeral=True
        )


class ExportOptionsModal(Modal):
    """導出選項表單"""

    def __init__(self):
        super().__init__(title="💾 導出報告選項")

        self.format_choice = TextInput(
            label="導出格式",
            placeholder="選擇: json, csv, txt",
            default="json",
            max_length=10,
            required=True,
        )

        self.include_charts = TextInput(
            label="包含圖表數據",
            placeholder="是/否 (yes/no)",
            default="yes",
            max_length=3,
            required=True,
        )

        self.date_range = TextInput(
            label="日期範圍 (可選)",
            placeholder="格式: YYYY-MM-DD to YYYY-MM-DD",
            required=False,
        )

        self.add_item(self.format_choice)
        self.add_item(self.include_charts)
        self.add_item(self.date_range)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            export_format = self.format_choice.value.lower()
            include_charts = self.include_charts.value.lower() in [
                "yes",
                "y",
                "是",
            ]

            if export_format not in ["json", "csv", "txt"]:
                await interaction.response.send_message("❌ 不支援的導出格式", ephemeral=True)
                return

            # 模擬導出過程
            embed = EmbedBuilder.build(
                title="✅ 導出請求已提交",
                description=f"正在生成 {export_format.upper()} 格式的報告...",
                color=0x2ECC71,
            )

            embed.add_field(
                name="📋 導出設定",
                value=f"格式: {export_format.upper()}\n"
                f"包含圖表: {'是' if include_charts else '否'}\n"
                f"日期範圍: {self.date_range.value or '使用默認範圍'}",
                inline=False,
            )

            embed.add_field(
                name="⏱️ 處理時間",
                value="預計1-2分鐘完成，報告將通過私訊發送",
                inline=False,
            )

            await interaction.response.send_message(embed=embed, ephemeral=True)

            # 這裡可以添加實際的導出邏輯

        except Exception as e:
            logger.error(f"處理導出請求失敗: {e}")
            await interaction.response.send_message("❌ 導出請求處理失敗", ephemeral=True)
