"""
Bootstrap utilities for path/environment setup.

Call `bootstrap_paths(__file__)` at process start to:
- Normalize project root and add it to sys.path
- Add common hosting roots that may contain the `shared` package
- Return (current_dir, project_root) for further use
"""

from __future__ import annotations

import importlib
import os
import sys
from pathlib import Path
from typing import Tuple


def bootstrap_paths(current_file: str) -> Tuple[Path, Path]:
    current_dir = Path(current_file).resolve().parent
    project_root = current_dir.parent

    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))

    possible_roots = [
        project_root,
        project_root.parent,
        Path("/home/container"),
        Path.cwd(),
    ]

    for root in possible_roots:
        shared_path = root / "shared"
        if shared_path.exists() and str(root) not in sys.path:
            sys.path.insert(0, str(root))
            break

    # Backward compatibility: add grandparent for legacy imports
    legacy_root = project_root.parent
    if str(legacy_root) not in sys.path:
        sys.path.append(str(legacy_root))

    # Alias package name "bot" -> "potato_bot" for existing imports
    try:
        potato_pkg = importlib.import_module("potato_bot")
        sys.modules.setdefault("bot", potato_pkg)
        # Pre-alias common subpackages to avoid重複載入造成不同 singleton
        for sub in ["db", "services", "utils", "views", "features", "cogs"]:
            try:
                mod = importlib.import_module(f"potato_bot.{sub}")
                sys.modules.setdefault(f"bot.{sub}", mod)
            except ImportError:
                continue
        # 常見子模組直接別名，避免同檔案載入兩次
        for mod_name in ["db.pool"]:
            try:
                mod = importlib.import_module(f"potato_bot.{mod_name}")
                sys.modules.setdefault(f"bot.{mod_name}", mod)
            except ImportError:
                continue
    except ImportError:
        pass

    # Alias package name "shared" -> "potato_shared" for existing imports
    try:
        shared_pkg = importlib.import_module("potato_shared")
        sys.modules.setdefault("shared", shared_pkg)
    except ImportError:
        pass

    return current_dir, project_root
