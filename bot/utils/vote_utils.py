# vote_utils.py - v5.1
# ✅ 功能：
# - 統一進度條樣式
# - 格式化選項顯示（票數 / 百分比 / 進度條）
# - 建立投票 Embed（含模式顯示和投票編號）
# - 建立結果 Embed（結束時公告）

from datetime import datetime

from discord import Embed


# ✅ 產生進度條（預設長度為 10）
def calculate_progress_bar(percent: float, length: int = 10) -> str:
    filled = int(percent / 100 * length)
    empty = length - filled
    return "█" * filled + "░" * empty


# ✅ 格式化選項文字（顯示：票數 + 百分比 + 條）
def format_option_label(option: str, stats: dict, total_votes: int) -> str:
    count = stats.get(option, 0)
    percent = (count / total_votes * 100) if total_votes else 0
    bar = calculate_progress_bar(percent)
    return f"{option} | {count} 票 ({percent:.1f}%) {bar}"


# ✅ 時間格式化（UTC 顯示）
def format_time(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%d %H:%M UTC")


# ✅ 建立投票 Embed（加入投票編號）
def build_vote_embed(
    title: str,
    start_time,
    end_time,
    is_multi: bool,
    anonymous: bool,
    total: int = 0,
    vote_id: int = None,
) -> Embed:
    # ✅ 在標題中加入投票編號
    embed_title = f"🗳 {title}"
    if vote_id is not None:
        embed_title = f"🗳 #{vote_id} - {title}"

    embed = Embed(
        title=embed_title,
        description=(
            f"請點選以下選項參與投票：\n\n"
            f"⏰ 開始：{format_time(start_time)}\n"
            f"⏳ 結束：{format_time(end_time)}\n"
            f"🧮 目前總票數：{total} 票"
        ),
        color=0x3498DB,
    )
    embed.add_field(
        name="📌 投票模式",
        value=f"{'匿名' if anonymous else '公開'}、{'多選' if is_multi else '單選'}",
        inline=False,
    )
    return embed


# ✅ 建立投票結果 Embed（進度條樣式，加入投票編號）
def build_result_embed(
    title: str, stats: dict, total: int, vote_id: int = None
) -> Embed:
    # ✅ 在標題中加入投票編號
    embed_title = f"📢 投票結束：{title}"
    if vote_id is not None:
        embed_title = f"📢 #{vote_id} 投票結束：{title}"

    embed = Embed(title=embed_title, color=0xE74C3C)
    embed.description = f"🧮 總票數：{total} 票"
    for opt, count in stats.items():
        percent = (count / total * 100) if total else 0
        bar = calculate_progress_bar(percent)
        embed.add_field(
            name=opt, value=f"{count} 票 ({percent:.1f}%)\n{bar}", inline=False
        )
    return embed
