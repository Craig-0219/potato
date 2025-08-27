#!/usr/bin/env python3
"""修復 vote_dao.py 中的 try 區塊語法問題"""

import re


def fix_vote_dao():
    with open("bot/db/vote_dao.py", "r", encoding="utf-8") as f:
        content = f.read()

    # 修復模式：找到孤立的 return 語句在 try 區塊外
    patterns_to_fix = [
        # 修復 get_vote_statistics 函式
        (
            r"(async def get_vote_statistics\(vote_id\):.*?try:.*?stats\[row\[0\]\] = row\[1\])\s*return \{\}",
            r'\1\n                return stats\n                \n    except Exception as e:\n        logger.error(f"取得投票統計時發生錯誤: {e}", exc_info=True)\n        return {}',
        ),
    ]

    # 應用修復
    for pattern, replacement in patterns_to_fix:
        content = re.sub(pattern, replacement, content, flags=re.DOTALL)

    # 更通用的修復：找到未關閉的 try 區塊
    # 這個更複雜，需要手動處理

    with open("bot/db/vote_dao.py", "w", encoding="utf-8") as f:
        f.write(content)

    print("修復完成")


if __name__ == "__main__":
    fix_vote_dao()
