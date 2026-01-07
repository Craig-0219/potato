from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import List

try:
    from potato_shared.logger import logger
except ImportError:
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger("cog_loader")

COGS_PREFIX = "potato_bot.cogs."
COGS_DIR = Path(__file__).resolve().parents[1] / "cogs"


def normalize_cog_name(name: str) -> str:
    """Normalize user input to a cog module name (without prefix)."""
    trimmed = name.strip().lower()
    if trimmed.startswith(COGS_PREFIX):
        trimmed = trimmed[len(COGS_PREFIX) :]
    if trimmed.endswith(".py"):
        trimmed = trimmed[:-3]
    # 常見別名映射（讓舊名稱可對應新的子模組路徑）
    alias = {
        "ticket_listener": "ticket.listener.ticket_listener",
        "ticket.cache.cached_ticket_core": "ticket_core",
        "cached_ticket_core": "ticket_core",
        "vote_listener": "vote.listener.vote_listener",
    }
    if trimmed in alias:
        return alias[trimmed]
    return trimmed


def discover_cog_modules() -> List[str]:
    """Scan the cogs directory and return loadable module names (without prefix)."""
    if not COGS_DIR.is_dir():
        logger.warning(f"⚠️ 找不到 cogs 目錄：{COGS_DIR}")
        return []

    modules: list[str] = []
    for filename in os.listdir(COGS_DIR):
        if not filename.endswith(".py"):
            continue
        if filename.startswith("_") or filename == "__init__.py":
            continue
        # 跳過已停用的 security_admin_core（依賴缺失）
        if filename == "security_admin_core.py":
            continue
        name = filename[:-3]
        modules.append(name)  # strip .py

    # 手動加入子目錄的票券相關模組（不在頂層，但需要自動載入）
    modules.sort()
    return modules
