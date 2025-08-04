# register/persistent_views.py
"""
集中註冊所有 PersistentView（跨模組集中管理）
如有新系統 PersistentView 只需在這裡引入與加入
"""

from bot.views.ticket_views import TicketPanelView, TicketControlView
from bot.views.vote_views import VotePanelView, VoteResultView
# 可依系統新增 import

def register_all_persistent_views(bot, all_settings: dict = None):
    """
    一次註冊所有 PersistentView
    :param bot: discord.ext.commands.Bot
    :param all_settings: 各模組 view 初始化所需的設定（可選，視需要決定）
    """
    # --- 票券系統 ---
    ticket_settings = all_settings.get("ticket") if all_settings else {}
    bot.add_view(TicketPanelView(ticket_settings, timeout=None))
    bot.add_view(TicketControlView(timeout=None))

    # --- 投票系統 ---
    vote_settings = all_settings.get("vote") if all_settings else {}
    bot.add_view(VotePanelView(vote_settings, timeout=None))
    bot.add_view(VoteResultView(timeout=None))
    
    # --- 新會員系統 / 其他 ---
    # from bot.views.member_views import NewMemberView
    # member_settings = all_settings.get("member") if all_settings else {}
    # bot.add_view(NewMemberView(member_settings, timeout=None))

    # ...依需求添加更多 PersistentView
