"""
Helpers for inspecting/logging persistent views.
"""

import asyncio

from potato_shared.logger import logger


async def log_persistent_views(bot) -> None:
    """Log basic info about registered persistent views (best-effort, non-fatal)."""
    try:
        await asyncio.sleep(1)
        views = getattr(bot, "persistent_views", None)
        if views:
            logger.info(f"✅ 已註冊 {len(views)} 個 Persistent Views")
        else:
            logger.info("ℹ️ 尚未發現 Persistent Views 註冊")
    except Exception as e:
        logger.error(f"❌ Persistent Views 記錄失敗：{e}")
