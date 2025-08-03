# bot/register/view_registry.py

from bot.views.ticket_views import (
    TicketPanelView, RatingView, TicketControlView
)

from bot.views.vote_views import (
    FinalStepView, DurationSelectView, RoleSelectView,
    AnonSelectView, MultiSelectView, VoteButtonView
)

def register_all_views(bot):
    """
    集中註冊所有 Persistent View。
    呼叫範例：register_all_views(bot)
    """
    # 🎫 票券相關
    bot.add_view(TicketPanelView())
    bot.add_view(RatingView())
    bot.add_view(TicketControlView())

    # 🗳 投票相關
    bot.add_view(FinalStepView())
    bot.add_view(DurationSelectView())
    bot.add_view(RoleSelectView())
    bot.add_view(AnonSelectView())
    bot.add_view(MultiSelectView())
    bot.add_view(VoteButtonView())
