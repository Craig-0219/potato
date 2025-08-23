"""
🎮 UI Module - Discord Bot User Interface Components
GUI 選單系統和互動式介面元件

Author: Potato Bot Development Team
Version: 3.2.0 - Phase 7 Stage 2
Date: 2025-08-20
"""

from .menu_system import (
    MenuSystemManager,
    MainMenuView,
    AdminMenuView,
    AIMenuView,
    TicketMenuView,
    VoteMenuView,
    WelcomeMenuView,
    SettingsMenuView,
    MenuType,
    MenuStyle
)

__all__ = [
    "MenuSystemManager",
    "MainMenuView", 
    "AdminMenuView",
    "AIMenuView",
    "TicketMenuView",
    "VoteMenuView",
    "WelcomeMenuView",
    "SettingsMenuView",
    "MenuType",
    "MenuStyle"
]

__version__ = "3.2.0"