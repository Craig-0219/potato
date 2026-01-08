# bot/services/chat_transcript_manager.py
"""
票券聊天記錄管理器
負責記錄、存儲和匯出票券對話內容
"""

import asyncio
import json
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

import aiofiles
import aiomysql
import discord

from potato_bot.db.pool import db_pool
from potato_shared.logger import logger


@dataclass
class ChatMessage:
    """聊天訊息資料類別"""

    message_id: int
    author_id: int
    author_name: str
    content: str
    attachments: List[Dict[str, str]]
    message_type: str  # 'user', 'staff', 'system'
    timestamp: datetime
    edited_timestamp: Optional[datetime] = None
    reply_to: Optional[int] = None


@dataclass
class TranscriptConfig:
    """聊天記錄配置"""

    auto_export_on_close: bool = True
    include_attachments: bool = True
    format_preference: str = "html"  # 'html', 'text', 'json'
    max_messages_per_ticket: int = 10000
    retention_days: int = 365


class ChatTranscriptManager:
    """聊天記錄管理器"""

    def __init__(self, config: Optional[TranscriptConfig] = None):
        self.config = config or TranscriptConfig()
        self.db = db_pool
        self.transcript_dir = Path("transcripts")
        self.transcript_dir.mkdir(exist_ok=True)

    async def record_message(self, ticket_id: int, message: discord.Message) -> bool:
        """記錄單一聊天訊息"""
        try:
            # 判斷訊息類型
            message_type = self._determine_message_type(message)

            # 處理附件
            attachments = []
            if message.attachments:
                for attachment in message.attachments:
                    attachments.append(
                        {
                            "filename": attachment.filename,
                            "url": attachment.url,
                            "size": attachment.size,
                            "content_type": attachment.content_type,
                        }
                    )

            # 處理回覆
            reply_to = None
            if hasattr(message, "reference") and message.reference:
                reply_to = message.reference.message_id

            async with self.db.connection() as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute(
                        """
                        INSERT INTO ticket_messages
                        (ticket_id, message_id, author_id, author_name, content,
                         attachments, message_type, timestamp, reply_to)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                        ON DUPLICATE KEY UPDATE
                        content = VALUES(content),
                        edited_timestamp = NOW()
                    """,
                        (
                            ticket_id,
                            message.id,
                            message.author.id,
                            message.author.display_name,
                            message.content or "[無文字內容]",
                            json.dumps(attachments, ensure_ascii=False),
                            message_type,
                            message.created_at,
                            reply_to,
                        ),
                    )

                    await conn.commit()
                    return True

        except Exception as e:
            logger.error(f"記錄訊息失敗 (ticket_id={ticket_id}, message_id={message.id}): {e}")
            return False

    def _determine_message_type(self, message: discord.Message) -> str:
        """判斷訊息類型"""
        if message.author.bot:
            return "bot"
        elif any(
            role.name in ["客服", "管理員", "Staff", "Admin"] for role in message.author.roles
        ):
            return "staff"
        else:
            return "user"

    async def get_ticket_messages(
        self, ticket_id: int, limit: Optional[int] = None
    ) -> List[ChatMessage]:
        """獲取票券的所有聊天訊息"""
        try:
            async with self.db.connection() as conn:
                async with conn.cursor(aiomysql.DictCursor) as cursor:
                    query = """
                        SELECT * FROM ticket_messages
                        WHERE ticket_id = %s
                        ORDER BY timestamp ASC
                    """
                    params = [ticket_id]

                    if limit:
                        query += " LIMIT %s"
                        params.append(limit)

                    await cursor.execute(query, params)
                    messages = await cursor.fetchall()

                    return [
                        ChatMessage(
                            message_id=msg["message_id"],
                            author_id=msg["author_id"],
                            author_name=msg["author_name"],
                            content=msg["content"],
                            attachments=(
                                json.loads(msg["attachments"]) if msg["attachments"] else []
                            ),
                            message_type=msg["message_type"],
                            timestamp=msg["timestamp"],
                            edited_timestamp=msg["edited_timestamp"],
                            reply_to=msg["reply_to"],
                        )
                        for msg in messages
                    ]

        except Exception as e:
            logger.error(f"獲取票券訊息失敗 (ticket_id={ticket_id}): {e}")
            return []

    async def export_transcript(self, ticket_id: int, format_type: str = "html") -> Optional[str]:
        """匯出票券聊天記錄"""
        try:
            # 獲取票券訊息
            messages = await self.get_ticket_messages(ticket_id)
            if not messages:
                logger.warning(f"票券 {ticket_id} 沒有聊天記錄")
                return None

            # 獲取票券基本資訊
            ticket_info = await self._get_ticket_info(ticket_id)

            # 根據格式類型生成記錄
            if format_type == "html":
                content = await self._generate_html_transcript(ticket_info, messages)
                file_extension = "html"
            elif format_type == "text":
                content = await self._generate_text_transcript(ticket_info, messages)
                file_extension = "txt"
            elif format_type == "json":
                content = await self._generate_json_transcript(ticket_info, messages)
                file_extension = "json"
            else:
                raise ValueError(f"不支援的格式: {format_type}")

            # 生成檔案路徑
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"ticket_{ticket_id:04d}_{timestamp}.{file_extension}"
            file_path = self.transcript_dir / filename

            # 寫入檔案
            async with aiofiles.open(file_path, "w", encoding="utf-8") as f:
                await f.write(content)

            # 保存到資料庫
            await self._save_transcript_record(
                ticket_id, content, format_type, str(file_path), len(messages)
            )

            logger.info(f"✅ 票券 {ticket_id} 聊天記錄匯出完成: {filename}")
            return str(file_path)

        except Exception as e:
            logger.error(f"❌ 匯出票券 {ticket_id} 聊天記錄失敗: {e}")
            return None

    async def _get_ticket_info(self, ticket_id: int) -> Dict[str, Any]:
        """獲取票券基本資訊"""
        try:
            async with self.db.connection() as conn:
                async with conn.cursor(aiomysql.DictCursor) as cursor:
                    await cursor.execute(
                        """
                        SELECT * FROM tickets WHERE id = %s
                    """,
                        (ticket_id,),
                    )

                    return await cursor.fetchone() or {}

        except Exception as e:
            logger.error(f"獲取票券資訊失敗 (ticket_id={ticket_id}): {e}")
            return {}

    async def _generate_html_transcript(
        self, ticket_info: Dict, messages: List[ChatMessage]
    ) -> str:
        """生成 HTML 格式聊天記錄"""
        html = f"""
        <!DOCTYPE html>
        <html lang="zh-TW">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>票券 #{ticket_info.get('id', 'Unknown'):04d} 聊天記錄</title>
            <style>
                body {{
                    font-family: 'Microsoft JhengHei', Arial, sans-serif;
                    margin: 20px;
                    background-color: #f5f5f5;
                }}
                .header {{
                    background: #7289da;
                    color: white;
                    padding: 20px;
                    border-radius: 8px;
                    margin-bottom: 20px;
                }}
                .message {{
                    background: white;
                    margin: 10px 0;
                    padding: 15px;
                    border-radius: 8px;
                    box-shadow: 0 2px 4px rgba(0,0,0,0.1);
                }}
                .message.staff {{ background: #e8f5e8; }}
                .message.bot {{ background: #fff2e8; }}
                .message.system {{ background: #f0f0f0; }}
                .author {{
                    font-weight: bold;
                    color: #7289da;
                    margin-bottom: 5px;
                }}
                .timestamp {{
                    font-size: 12px;
                    color: #666;
                    margin-bottom: 8px;
                }}
                .content {{
                    line-height: 1.4;
                    word-wrap: break-word;
                }}
                .attachments {{
                    margin-top: 10px;
                    padding: 10px;
                    background: #f8f8f8;
                    border-radius: 4px;
                }}
                .attachment {{
                    margin: 5px 0;
                }}
                .reply {{
                    border-left: 4px solid #7289da;
                    padding-left: 10px;
                    margin-bottom: 8px;
                    background: rgba(114, 137, 218, 0.1);
                }}
            </style>
        </head>
        <body>
            <div class="header">
                <h1>票券 #{ticket_info.get('id', 'Unknown'):04d} 聊天記錄</h1>
                <p><strong>建立者:</strong> {ticket_info.get('username', 'Unknown')}</p>
                <p><strong>類型:</strong> {ticket_info.get('type', 'Unknown')}</p>
                <p><strong>狀態:</strong> {ticket_info.get('status', 'Unknown')}</p>
                <p><strong>建立時間:</strong> {ticket_info.get('created_at', 'Unknown')}</p>
                <p><strong>訊息數量:</strong> {len(messages)} 條</p>
            </div>
        """

        for message in messages:
            # 處理回覆
            reply_html = ""
            if message.reply_to:
                reply_html = '<div class="reply">回覆某則訊息</div>'

            # 處理附件
            attachments_html = ""
            if message.attachments:
                attachments_html = '<div class="attachments"><strong>附件:</strong><br>'
                for att in message.attachments:
                    attachments_html += f'<div class="attachment">📎 {att["filename"]} ({att.get("size", 0)} bytes)</div>'
                attachments_html += "</div>"

            # 處理訊息內容
            content = (
                message.content.replace("\n", "<br>").replace("<", "&lt;").replace(">", "&gt;")
            )

            html += f"""
            <div class="message {message.message_type}">
                <div class="author">{message.author_name} <span style="font-size: 12px; color: #888;">({message.message_type})</span></div>
                <div class="timestamp">{message.timestamp.strftime('%Y-%m-%d %H:%M:%S')}</div>
                {reply_html}
                <div class="content">{content}</div>
                {attachments_html}
            </div>
            """

        html += """
        </body>
        </html>
        """

        return html

    async def _generate_text_transcript(
        self, ticket_info: Dict, messages: List[ChatMessage]
    ) -> str:
        """生成純文字格式聊天記錄"""
        lines = [
            f"票券 #{ticket_info.get('id', 'Unknown'):04d} 聊天記錄",
            "=" * 50,
            f"建立者: {ticket_info.get('username', 'Unknown')}",
            f"類型: {ticket_info.get('type', 'Unknown')}",
            f"狀態: {ticket_info.get('status', 'Unknown')}",
            f"建立時間: {ticket_info.get('created_at', 'Unknown')}",
            f"訊息數量: {len(messages)} 條",
            "=" * 50,
            "",
        ]

        for message in messages:
            lines.append(
                f"[{message.timestamp.strftime('%Y-%m-%d %H:%M:%S')}] {message.author_name} ({message.message_type}):"
            )
            lines.append(f"  {message.content}")

            if message.attachments:
                lines.append("  附件:")
                for att in message.attachments:
                    lines.append(f"    📎 {att['filename']}")

            lines.append("")

        return "\n".join(lines)

    async def _generate_json_transcript(
        self, ticket_info: Dict, messages: List[ChatMessage]
    ) -> str:
        """生成 JSON 格式聊天記錄"""
        data = {
            "ticket_info": {
                "id": ticket_info.get("id"),
                "username": ticket_info.get("username"),
                "type": ticket_info.get("type"),
                "status": ticket_info.get("status"),
                "created_at": str(ticket_info.get("created_at")),
                "message_count": len(messages),
            },
            "messages": [],
        }

        for message in messages:
            data["messages"].append(
                {
                    "message_id": message.message_id,
                    "author_id": message.author_id,
                    "author_name": message.author_name,
                    "content": message.content,
                    "attachments": message.attachments,
                    "message_type": message.message_type,
                    "timestamp": message.timestamp.isoformat(),
                    "edited_timestamp": (
                        message.edited_timestamp.isoformat() if message.edited_timestamp else None
                    ),
                    "reply_to": message.reply_to,
                }
            )

        return json.dumps(data, ensure_ascii=False, indent=2)

    async def _save_transcript_record(
        self,
        ticket_id: int,
        content: str,
        format_type: str,
        file_path: str,
        message_count: int,
    ):
        """保存聊天記錄到資料庫"""
        try:
            file_size = Path(file_path).stat().st_size

            async with self.db.connection() as conn:
                async with conn.cursor() as cursor:
                    # 根據格式類型決定儲存欄位
                    if format_type == "html":
                        await cursor.execute(
                            """
                            INSERT INTO ticket_transcripts
                            (ticket_id, transcript_html, message_count, file_path, file_size, export_format)
                            VALUES (%s, %s, %s, %s, %s, %s)
                            ON DUPLICATE KEY UPDATE
                            transcript_html = VALUES(transcript_html),
                            message_count = VALUES(message_count),
                            file_path = VALUES(file_path),
                            file_size = VALUES(file_size),
                            export_format = VALUES(export_format)
                        """,
                            (
                                ticket_id,
                                content,
                                message_count,
                                file_path,
                                file_size,
                                format_type,
                            ),
                        )
                    elif format_type == "text":
                        await cursor.execute(
                            """
                            INSERT INTO ticket_transcripts
                            (ticket_id, transcript_text, message_count, file_path, file_size, export_format)
                            VALUES (%s, %s, %s, %s, %s, %s)
                            ON DUPLICATE KEY UPDATE
                            transcript_text = VALUES(transcript_text),
                            message_count = VALUES(message_count),
                            file_path = VALUES(file_path),
                            file_size = VALUES(file_size),
                            export_format = VALUES(export_format)
                        """,
                            (
                                ticket_id,
                                content,
                                message_count,
                                file_path,
                                file_size,
                                format_type,
                            ),
                        )
                    elif format_type == "json":
                        await cursor.execute(
                            """
                            INSERT INTO ticket_transcripts
                            (ticket_id, transcript_json, message_count, file_path, file_size, export_format)
                            VALUES (%s, %s, %s, %s, %s, %s)
                            ON DUPLICATE KEY UPDATE
                            transcript_json = VALUES(transcript_json),
                            message_count = VALUES(message_count),
                            file_path = VALUES(file_path),
                            file_size = VALUES(file_size),
                            export_format = VALUES(export_format)
                        """,
                            (
                                ticket_id,
                                content,
                                message_count,
                                file_path,
                                file_size,
                                format_type,
                            ),
                        )

                    await conn.commit()

        except Exception as e:
            logger.error(f"保存聊天記錄到資料庫失敗 (ticket_id={ticket_id}): {e}")

    async def cleanup_old_transcripts(self, days: int = 30) -> int:
        """清理舊的聊天記錄檔案"""
        try:
            cutoff_date = datetime.now() - timedelta(days=days)
            deleted_count = 0

            # 清理檔案系統中的舊檔案
            for file_path in self.transcript_dir.iterdir():
                if file_path.is_file():
                    file_time = datetime.fromtimestamp(file_path.stat().st_mtime)
                    if file_time < cutoff_date:
                        try:
                            file_path.unlink()
                            deleted_count += 1
                            logger.info(f"🗑️ 已刪除舊聊天記錄檔案: {file_path.name}")
                        except Exception as e:
                            logger.warning(f"刪除檔案 {file_path.name} 失敗: {e}")

            return deleted_count

        except Exception as e:
            logger.error(f"清理舊聊天記錄失敗: {e}")
            return 0

    async def batch_record_channel_history(
        self, ticket_id: int, channel: discord.TextChannel, limit: int = None
    ) -> int:
        """批量記錄頻道歷史訊息"""
        try:
            recorded_count = 0

            logger.info(f"開始批量記錄頻道歷史訊息 (ticket_id={ticket_id}, channel={channel.id})")

            async for message in channel.history(limit=limit, oldest_first=True):
                success = await self.record_message(ticket_id, message)
                if success:
                    recorded_count += 1

                # 避免 API 限制
                await asyncio.sleep(0.1)

            logger.debug(f"✅ 批量記錄完成，共記錄 {recorded_count} 條訊息")
            return recorded_count

        except Exception as e:
            logger.error(f"❌ 批量記錄頻道歷史失敗: {e}")
            return 0
