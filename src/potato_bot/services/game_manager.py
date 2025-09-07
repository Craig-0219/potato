# bot/services/game_manager.py - 遊戲管理器
"""
遊戲管理器 v2.2.0
負責管理各種遊戲的核心邏輯和狀態
"""

import json
import random
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from bot.db.pool import db_pool
from shared.cache_manager import cache_manager
from shared.logger import logger


class GameManager:
    """遊戲管理器"""

    def __init__(self):
        self.active_games: Dict[str, Any] = {}
        logger.info("🎮 遊戲管理器初始化完成")

    async def create_game_session(
        self, game_type: str, player_id: int, guild_id: int, **kwargs
    ) -> str:
        """創建遊戲會話"""
        try:
            game_id = f"{game_type}_{player_id}_{int(time.time())}"

            session_data = {
                "game_id": game_id,
                "game_type": game_type,
                "player_id": player_id,
                "guild_id": guild_id,
                "start_time": datetime.now(timezone.utc),
                "status": "active",
                "data": kwargs,
            }

            self.active_games[game_id] = session_data

            # 快取會話數據
            await cache_manager.set(f"game_session:{game_id}", session_data, 1800)  # 30分鐘

            return game_id

        except Exception as e:
            logger.error(f"❌ 創建遊戲會話失敗: {e}")
            raise

    async def get_game_session(self, game_id: str) -> Optional[Dict[str, Any]]:
        """獲取遊戲會話"""
        try:
            # 先從記憶體獲取
            if game_id in self.active_games:
                return self.active_games[game_id]

            # 從快取獲取
            cached_session = await cache_manager.get(f"game_session:{game_id}")
            if cached_session:
                self.active_games[game_id] = cached_session
                return cached_session

            return None

        except Exception as e:
            logger.error(f"❌ 獲取遊戲會話失敗: {e}")
            return None

    async def update_game_session(self, game_id: str, update_data: Dict[str, Any]):
        """更新遊戲會話"""
        try:
            if game_id in self.active_games:
                self.active_games[game_id].update(update_data)

                # 更新快取
                await cache_manager.set(f"game_session:{game_id}", self.active_games[game_id], 1800)

        except Exception as e:
            logger.error(f"❌ 更新遊戲會話失敗: {e}")
            raise

    async def end_game_session(self, game_id: str, result_data: Dict[str, Any]):
        """結束遊戲會話"""
        try:
            if game_id in self.active_games:
                session = self.active_games[game_id]
                session["end_time"] = datetime.now(timezone.utc)
                session["status"] = "completed"
                session.update(result_data)

                # 保存到資料庫
                await self._save_game_result(session)

                # 清理記憶體和快取
                del self.active_games[game_id]
                await cache_manager.delete(f"game_session:{game_id}")

        except Exception as e:
            logger.error(f"❌ 結束遊戲會話失敗: {e}")
            raise

    async def _save_game_result(self, session: Dict[str, Any]):
        """保存遊戲結果"""
        try:
            async with db_pool.connection() as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute(
                        """
                        INSERT INTO game_results
                        (game_id, game_type, player_id, guild_id, channel_id,
                         start_time, end_time, won, score, game_data)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                        (
                            session["game_id"],
                            session["game_type"],
                            session["player_id"],
                            session["guild_id"],
                            session.get("channel_id", 0),
                            session["start_time"],
                            session.get("end_time"),
                            session.get("won", False),
                            session.get("score", 0),
                            json.dumps(session.get("data", {})),
                        ),
                    )
                    await conn.commit()

        except Exception as e:
            logger.error(f"❌ 保存遊戲結果失敗: {e}")

    async def get_user_game_stats(self, user_id: int, guild_id: int) -> Dict[str, Any]:
        """獲取用戶遊戲統計"""
        try:
            async with db_pool.connection() as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute(
                        """
                        SELECT
                            game_type,
                            COUNT(*) as total_games,
                            SUM(won) as wins,
                            AVG(score) as avg_score,
                            MAX(score) as best_score
                        FROM game_results
                        WHERE player_id = %s AND guild_id = %s
                        GROUP BY game_type
                    """,
                        (user_id, guild_id),
                    )

                    results = await cursor.fetchall()

                    stats = {}
                    for row in results:
                        game_type, total, wins, avg_score, best_score = row
                        stats[game_type] = {
                            "total_games": total,
                            "wins": wins,
                            "win_rate": ((wins / total * 100) if total > 0 else 0),
                            "avg_score": float(avg_score) if avg_score else 0,
                            "best_score": best_score or 0,
                        }

                    return stats

        except Exception as e:
            logger.error(f"❌ 獲取用戶遊戲統計失敗: {e}")
            return {}

    async def get_leaderboard(
        self,
        guild_id: int,
        game_type: str,
        metric: str = "wins",
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """獲取排行榜"""
        try:
            # 快取鍵
            cache_key = f"game_leaderboard:{guild_id}:{game_type}:{metric}:{limit}"

            # 嘗試從快取獲取
            cached_result = await cache_manager.get(cache_key)
            if cached_result:
                return cached_result

            async with db_pool.connection() as conn:
                async with conn.cursor() as cursor:
                    if metric == "wins":
                        order_by = "SUM(won) DESC"
                    elif metric == "games":
                        order_by = "COUNT(*) DESC"
                    elif metric == "win_rate":
                        order_by = "(SUM(won) / COUNT(*)) DESC"
                    elif metric == "avg_score":
                        order_by = "AVG(score) DESC"
                    else:
                        order_by = "SUM(won) DESC"

                    await cursor.execute(
                        f"""
                        SELECT
                            player_id,
                            COUNT(*) as total_games,
                            SUM(won) as total_wins,
                            AVG(score) as avg_score,
                            MAX(score) as best_score,
                            (SUM(won) / COUNT(*)) as win_rate
                        FROM game_results
                        WHERE guild_id = %s AND game_type = %s
                        GROUP BY player_id
                        ORDER BY {order_by}
                        LIMIT %s
                    """,
                        (guild_id, game_type, limit),
                    )

                    results = await cursor.fetchall()

                    leaderboard = []
                    for i, row in enumerate(results, 1):
                        (
                            player_id,
                            total_games,
                            total_wins,
                            avg_score,
                            best_score,
                            win_rate,
                        ) = row

                        leaderboard.append(
                            {
                                "rank": i,
                                "player_id": player_id,
                                "total_games": total_games,
                                "total_wins": total_wins,
                                "avg_score": (float(avg_score) if avg_score else 0),
                                "best_score": best_score or 0,
                                "win_rate": (float(win_rate) * 100 if win_rate else 0),
                            }
                        )

                    # 快取結果
                    await cache_manager.set(cache_key, leaderboard, 300)  # 5分鐘快取

                    return leaderboard

        except Exception as e:
            logger.error(f"❌ 獲取遊戲排行榜失敗: {e}")
            return []

    async def cleanup_expired_sessions(self):
        """清理過期會話"""
        try:
            current_time = datetime.now(timezone.utc)
            expired_sessions = []

            for game_id, session in self.active_games.items():
                start_time = session.get("start_time")
                if isinstance(start_time, str):
                    start_time = datetime.fromisoformat(start_time.replace("Z", "+00:00"))

                # 超過30分鐘視為過期
                if (current_time - start_time).total_seconds() > 1800:
                    expired_sessions.append(game_id)

            for game_id in expired_sessions:
                session = self.active_games[game_id]
                session["status"] = "expired"
                session["end_time"] = current_time

                # 保存過期會話
                await self._save_game_result(session)

                # 清理
                del self.active_games[game_id]
                await cache_manager.delete(f"game_session:{game_id}")

            if expired_sessions:
                logger.info(f"🧹 清理過期遊戲會話: {len(expired_sessions)} 個")

        except Exception as e:
            logger.error(f"❌ 清理過期會話失敗: {e}")

    # ========== 具體遊戲邏輯 ==========

    def generate_guess_number_game(self, difficulty: str) -> Dict[str, Any]:
        """生成猜數字遊戲"""
        configs = {
            "easy": {"max_num": 50, "attempts": 8, "reward": 50},
            "medium": {"max_num": 100, "attempts": 6, "reward": 100},
            "hard": {"max_num": 200, "attempts": 5, "reward": 200},
        }

        config = configs.get(difficulty, configs["medium"])
        secret_number = random.randint(1, config["max_num"])

        return {
            "secret_number": secret_number,
            "max_number": config["max_num"],
            "attempts_left": config["attempts"],
            "max_attempts": config["attempts"],
            "reward": config["reward"],
            "guesses": [],
        }

    def process_guess(self, game_data: Dict[str, Any], guess: int) -> Dict[str, Any]:
        """處理猜測"""
        secret_number = game_data["secret_number"]
        game_data["attempts_left"] -= 1
        game_data["guesses"].append(guess)

        if guess == secret_number:
            return {
                "result": "correct",
                "message": "🎉 恭喜！您猜中了！",
                "won": True,
                "score": game_data["attempts_left"] + 1,
            }
        elif game_data["attempts_left"] <= 0:
            return {
                "result": "game_over",
                "message": f"💔 遊戲結束！答案是 {secret_number}",
                "won": False,
                "score": 0,
            }
        else:
            hint = "太小了！" if guess < secret_number else "太大了！"
            return {
                "result": "continue",
                "message": f"{hint} 還有 {game_data['attempts_left']} 次機會",
                "won": None,
                "score": None,
            }

    def play_rock_paper_scissors(self, player_choice: str) -> Dict[str, Any]:
        """玩剪刀石頭布"""
        choices = ["rock", "paper", "scissors"]
        computer_choice = random.choice(choices)

        # 判斷結果
        if player_choice == computer_choice:
            result = "draw"
            reward = 10
        elif (
            player_choice == "rock"
            and computer_choice == "scissors"
            or player_choice == "paper"
            and computer_choice == "rock"
            or player_choice == "scissors"
            and computer_choice == "paper"
        ):
            result = "win"
            reward = 30
        else:
            result = "lose"
            reward = 0

        return {
            "player_choice": player_choice,
            "computer_choice": computer_choice,
            "result": result,
            "reward": reward,
            "won": result == "win",
        }

    def flip_coin(self, bet_amount: int, choice: str) -> Dict[str, Any]:
        """拋硬幣"""
        result = random.choice(["heads", "tails"])
        won = choice == result
        winnings = bet_amount * 2 if won else 0

        return {
            "choice": choice,
            "result": result,
            "won": won,
            "bet_amount": bet_amount,
            "winnings": winnings,
            "profit": winnings - bet_amount,
        }

    def spin_roulette(
        self, bet_amount: int, bet_type: str, bet_value: Any = None
    ) -> Dict[str, Any]:
        """輪盤遊戲"""
        # 生成結果數字 (0-36)
        result_number = random.randint(0, 36)

        # 定義紅色數字
        red_numbers = [
            1,
            3,
            5,
            7,
            9,
            12,
            14,
            16,
            18,
            19,
            21,
            23,
            25,
            27,
            30,
            32,
            34,
            36,
        ]

        # 判斷屬性
        is_red = result_number in red_numbers
        is_black = result_number != 0 and not is_red
        is_odd = result_number % 2 == 1 and result_number != 0
        is_even = result_number % 2 == 0 and result_number != 0

        # 判斷是否中獎
        won = False
        payout_multiplier = 0

        if bet_type == "red" and is_red:
            won = True
            payout_multiplier = 2
        elif bet_type == "black" and is_black:
            won = True
            payout_multiplier = 2
        elif bet_type == "odd" and is_odd:
            won = True
            payout_multiplier = 2
        elif bet_type == "even" and is_even:
            won = True
            payout_multiplier = 2
        elif bet_type == "number" and bet_value == result_number:
            won = True
            payout_multiplier = 35

        winnings = bet_amount * payout_multiplier if won else 0

        return {
            "result_number": result_number,
            "is_red": is_red,
            "is_black": is_black,
            "is_odd": is_odd,
            "is_even": is_even,
            "bet_type": bet_type,
            "bet_value": bet_value,
            "bet_amount": bet_amount,
            "won": won,
            "payout_multiplier": payout_multiplier,
            "winnings": winnings,
            "profit": winnings - bet_amount,
        }

    async def get_daily_game_stats(self, guild_id: int) -> Dict[str, Any]:
        """獲取每日遊戲統計"""
        try:
            async with db_pool.connection() as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute(
                        """
                        SELECT
                            COUNT(*) as total_games,
                            COUNT(DISTINCT player_id) as unique_players,
                            SUM(won) as total_wins,
                            AVG(score) as avg_score
                        FROM game_results
                        WHERE guild_id = %s
                        AND DATE(start_time) = CURDATE()
                    """,
                        (guild_id,),
                    )

                    result = await cursor.fetchone()

                    if result:
                        total_games, unique_players, total_wins, avg_score = result
                        return {
                            "total_games": total_games or 0,
                            "unique_players": unique_players or 0,
                            "total_wins": total_wins or 0,
                            "win_rate": (
                                (total_wins / total_games * 100) if total_games > 0 else 0
                            ),
                            "avg_score": float(avg_score) if avg_score else 0,
                        }

                    return {
                        "total_games": 0,
                        "unique_players": 0,
                        "total_wins": 0,
                        "win_rate": 0,
                        "avg_score": 0,
                    }

        except Exception as e:
            logger.error(f"❌ 獲取每日遊戲統計失敗: {e}")
            return {}
