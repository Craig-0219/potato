"""
批次票券操作指令模組（完整實作版 v1.0）
支援批次關閉未活動票券、批次匯出 JSON 等
"""

import discord
from discord.ext import commands
from discord import app_commands
import json
import asyncio
from datetime import datetime, timedelta, timezone

from bot.db.ticket_dao import TicketDAO
from bot.services.ticket_manager import TicketManager
from shared.logger import logger

class TicketBatch(commands.Cog):
    """批次票券管理指令"""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.repository = TicketDAO()
        self.manager = TicketManager(self.repository)

    @app_commands.command(
        name="batch", 
        description="批次執行票券管理任務（僅限管理員）"
    )
    @app_commands.describe(
        operation_type="操作名稱（如 close_inactive, export_json）", 
        params="JSON 格式參數（選填）"
    )
    async def batch(
        self, 
        interaction: discord.Interaction, 
        operation_type: str, 
        params: str = None
    ):
        """批次票券操作主指令"""
        # 僅限管理員使用
        if not interaction.user.guild_permissions.manage_guild:
            await interaction.response.send_message(
                "❌ 只有管理員可以使用此指令。", ephemeral=True
            )
            return

        # 解析參數
        parsed_params = {}
        if params:
            try:
                parsed_params = json.loads(params)
            except Exception as e:
                await interaction.response.send_message(
                    f"❌ 參數解析錯誤：{e}", ephemeral=True
                )
                return

        # 分流
        if operation_type == "close_inactive":
            days = int(parsed_params.get("days", 7))
            result_msg = await self._close_inactive_tickets(interaction, days)
            await interaction.response.send_message(result_msg, ephemeral=True)

        elif operation_type == "export_json":
            status = parsed_params.get("status", "all")
            priority = parsed_params.get("priority", "all")
            data_bytes, count = await self._export_tickets_json(interaction, status, priority)
            if count == 0:
                await interaction.response.send_message("❌ 查無票券紀錄。", ephemeral=True)
                return
            file = discord.File(fp=data_bytes, filename=f"tickets_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
            await interaction.response.send_message(
                f"✅ 匯出 {count} 筆票券，資料如下：", file=file, ephemeral=True
            )
        else:
            await interaction.response.send_message(
                f"⚠️ 不支援的 operation_type: `{operation_type}`", ephemeral=True
            )

    async def _close_inactive_tickets(self, interaction: discord.Interaction, days: int) -> str:
        """批次關閉未活動票券"""
        guild_id = interaction.guild.id
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        # 取出所有超過 x 天沒互動且狀態為 open 的票券
        tickets = await self.repository.get_inactive_tickets(guild_id, cutoff)
        if not tickets:
            return f"✅ 沒有 {days} 天未活動的 OPEN 狀態票券。"
        
        closed_count = 0
        failed = []
        for ticket in tickets:
            try:
                # 預設由系統關閉
                success = await self.manager.close_ticket(
                    ticket_id=ticket['id'],
                    closed_by=0,
                    reason=f"批次自動關閉（{days}天未活動）"
                )
                if success:
                    closed_count += 1
            except Exception as e:
                failed.append(str(ticket['id']))
                logger.error(f"[批次關閉] 關閉票券 {ticket['id']} 時錯誤：{e}")
        
        return f"✅ 已批次關閉 {closed_count} 張票券。" + (f"\n失敗票券: {','.join(failed)}" if failed else "")

    async def _export_tickets_json(self, interaction: discord.Interaction, status: str, priority: str):
        """匯出票券 JSON 檔案"""
        # 批次匯出所有票券（可加條件，例：status, priority, user_id）
        query = {"guild_id": interaction.guild.id}
        if status != "all":
            query["status"] = status
        if priority != "all":
            query["priority"] = priority

        tickets, total = await self.repository.get_tickets(**query, page=1, page_size=5000)
        # 移除不必要欄位，或格式化時間（如有需要）
        for t in tickets:
            if isinstance(t.get('created_at'), datetime):
                t['created_at'] = t['created_at'].isoformat()
            if t.get('closed_at') and isinstance(t['closed_at'], datetime):
                t['closed_at'] = t['closed_at'].isoformat()
        import io
        file_bytes = io.BytesIO()
        file_bytes.write(json.dumps(tickets, ensure_ascii=False, indent=2).encode("utf-8"))
        file_bytes.seek(0)
        return file_bytes, total

async def setup(bot: commands.Bot):
    await bot.add_cog(TicketBatch(bot))
