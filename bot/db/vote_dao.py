# bot/db/vote_dao.py - v5.0 修正版（移除重複初始化）
"""
投票系統資料存取層 - 修正版
移除重複的初始化功能，統一由 DatabaseManager 管理
"""

from bot.db.pool import db_pool
from datetime import datetime, timedelta, timezone
import json
import aiomysql
from typing import Dict, List, Optional, Any
from shared.logger import logger


class VoteDAO:
    """投票系統資料存取層"""
    
    def __init__(self):
        self.db = db_pool
    
    async def get_votes_by_date_range(self, guild_id: int, start_date: datetime, end_date: datetime) -> List[Dict[str, Any]]:
        """取得指定日期範圍內的投票"""
        try:
            # 確保日期時間格式一致 (移除timezone info以匹配資料庫)
            if start_date.tzinfo is not None:
                start_date = start_date.replace(tzinfo=None)
            if end_date.tzinfo is not None:
                end_date = end_date.replace(tzinfo=None)
                
            async with self.db.connection() as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute("""
                        SELECT id, title, is_multi, anonymous, creator_id, 
                               start_time, end_time, channel_id,
                               (SELECT COUNT(*) FROM vote_responses vr WHERE vr.vote_id = v.id) as total_votes
                        FROM votes v
                        WHERE guild_id = %s AND start_time BETWEEN %s AND %s
                        ORDER BY start_time DESC
                    """, (guild_id, start_date, end_date))
                    
                    rows = await cursor.fetchall()
                    votes = []
                    
                    for row in rows:
                        # 取得選項數量
                        await cursor.execute("SELECT COUNT(*) FROM vote_options WHERE vote_id = %s", (row[0],))
                        options_count = (await cursor.fetchone())[0]
                        
                        vote = {
                            'id': row[0],
                            'title': row[1],
                            'is_multi': bool(row[2]),
                            'anonymous': bool(row[3]),
                            'creator_id': row[4],
                            'start_time': row[5],
                            'end_time': row[6],
                            'ended_at': row[6] if row[6] and row[6] < datetime.now().replace(tzinfo=None) else None,
                            'channel_id': row[7],
                            'total_votes': row[8],
                            'options': {'count': options_count}
                        }
                        votes.append(vote)
                    
                    return votes
                    
        except Exception as e:
            logger.error(f"取得投票列表錯誤: {e}")
            return []

# ===== 核心投票操作 =====

async def create_vote(session, creator_id):
    """建立新投票記錄"""
    try:
        async with db_pool.connection() as conn:
            async with conn.cursor() as cur:
                logger.debug(f"準備插入投票：{session['title']}")
                
                await cur.execute("""
                    INSERT INTO votes (title, is_multi, anonymous, allowed_roles, channel_id, guild_id, creator_id, end_time, start_time)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    session['title'],
                    bool(session['is_multi']),
                    bool(session['anonymous']),
                    json.dumps(session['allowed_roles']),
                    session['origin_channel'].id,
                    session['guild_id'],
                    str(creator_id),
                    session['end_time'],
                    session['start_time']
                ))
                await conn.commit()
                vote_id = cur.lastrowid
                logger.info(f"投票插入成功，ID：{vote_id}")
                
                # 驗證插入
                await cur.execute("SELECT COUNT(*) FROM votes WHERE id = %s", (vote_id,))
                count = await cur.fetchone()
                logger.debug(f"驗證投票存在：{count[0]} 筆")
                
                return vote_id
                
    except Exception as e:
        logger.error(f"create_vote 失敗：{e}")
        raise

async def add_vote_option(vote_id, option):
    """寫入單個投票選項"""
    try:
        async with db_pool.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute("""
                    INSERT INTO vote_options (vote_id, option_text)
                    VALUES (%s, %s)
                """, (vote_id, option))
                await conn.commit()
                logger.debug(f"選項插入成功：{option}")
                
    except Exception as e:
        logger.error(f"add_vote_option 失敗：{e}")
        raise

async def get_active_votes():
    """取得目前尚未結束的投票清單"""
    try:
        async with db_pool.connection() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cur:
                await cur.execute("""
                    SELECT id, title, is_multi, anonymous, allowed_roles, channel_id, end_time, start_time, announced, guild_id, creator_id
                    FROM votes 
                    WHERE end_time > UTC_TIMESTAMP()
                    ORDER BY start_time DESC
                """)
                rows = await cur.fetchall()
                logger.debug(f"get_active_votes 查詢到 {len(rows)} 筆資料")
                
                if not rows:
                    return []
                
                # 處理每一行資料
                processed_votes = []
                for row in rows:
                    try:
                        # 確保布林值正確轉換
                        row['is_multi'] = bool(row['is_multi'])
                        row['anonymous'] = bool(row['anonymous'])
                        row['announced'] = bool(row.get('announced', False))
                        
                        # 處理 JSON 欄位
                        allowed_roles_str = row.get('allowed_roles', '[]')
                        if allowed_roles_str:
                            try:
                                row['allowed_roles'] = json.loads(allowed_roles_str)
                            except (json.JSONDecodeError, TypeError):
                                row['allowed_roles'] = []
                        else:
                            row['allowed_roles'] = []
                        
                        # 確保時間欄位有時區資訊
                        if row['start_time'] and row['start_time'].tzinfo is None:
                            row['start_time'] = row['start_time'].replace(tzinfo=timezone.utc)
                        if row['end_time'] and row['end_time'].tzinfo is None:
                            row['end_time'] = row['end_time'].replace(tzinfo=timezone.utc)
                        
                        processed_votes.append(row)
                        logger.debug(f"處理投票成功：#{row['id']} - {row['title']}")
                        
                    except Exception as row_error:
                        logger.error(f"處理投票資料錯誤 (ID: {row.get('id', 'unknown')}): {row_error}")
                        continue
                
                return processed_votes
                
    except Exception as e:
        logger.error(f"get_active_votes 錯誤: {e}")
        import traceback
        logger.error(f"完整追蹤: {traceback.format_exc()}")
        return []

async def get_vote_by_id(vote_id):
    """查詢特定投票詳細資料"""
    try:
        async with db_pool.connection() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cur:
                await cur.execute("""
                    SELECT id, title, is_multi, anonymous, allowed_roles, channel_id, end_time, start_time, announced, guild_id, creator_id
                    FROM votes 
                    WHERE id = %s
                """, (vote_id,))
                vote = await cur.fetchone()
                
                if not vote:
                    logger.debug(f"找不到投票 #{vote_id}")
                    return None
                
                # 資料處理
                vote['is_multi'] = bool(vote['is_multi'])
                vote['anonymous'] = bool(vote['anonymous'])
                vote['announced'] = bool(vote.get('announced', False))
                
                # 處理 JSON 欄位
                allowed_roles_str = vote.get('allowed_roles', '[]')
                try:
                    vote['allowed_roles'] = json.loads(allowed_roles_str) if allowed_roles_str else []
                except (json.JSONDecodeError, TypeError):
                    vote['allowed_roles'] = []
                
                # 確保時間欄位有時區資訊
                if vote['start_time'] and vote['start_time'].tzinfo is None:
                    vote['start_time'] = vote['start_time'].replace(tzinfo=timezone.utc)
                if vote['end_time'] and vote['end_time'].tzinfo is None:
                    vote['end_time'] = vote['end_time'].replace(tzinfo=timezone.utc)
                
                logger.debug(f"成功取得投票 #{vote_id}")
                return vote
                
    except Exception as e:
        logger.error(f"get_vote_by_id({vote_id}) 錯誤: {e}")
        import traceback
        logger.error(f"完整追蹤: {traceback.format_exc()}")
        return None

async def get_vote_options(vote_id):
    """取得某投票的所有選項清單"""
    try:
        async with db_pool.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute("""
                    SELECT option_text FROM vote_options
                    WHERE vote_id = %s
                    ORDER BY id
                """, (vote_id,))
                options = []
                async for row in cur:
                    options.append(row[0])
                logger.debug(f"投票 #{vote_id} 有 {len(options)} 個選項")
                return options
                
    except Exception as e:
        logger.error(f"get_vote_options({vote_id}) 錯誤: {e}")
        return []

async def has_voted(vote_id, user_id):
    """檢查某用戶是否已投票"""
    try:
        async with db_pool.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute("""
                    SELECT 1 FROM vote_responses
                    WHERE vote_id = %s AND user_id = %s
                    LIMIT 1
                """, (vote_id, user_id))
                result = await cur.fetchone() is not None
                logger.debug(f"用戶 {user_id} 在投票 #{vote_id} 的投票狀態：{'已投票' if result else '未投票'}")
                return result
                
    except Exception as e:
        logger.error(f"has_voted({vote_id}, {user_id}) 錯誤: {e}")
        return False

async def insert_vote_response(vote_id, user_id, option):
    """寫入投票結果"""
    try:
        async with db_pool.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute("""
                    INSERT INTO vote_responses (vote_id, user_id, option_text)
                    VALUES (%s, %s, %s)
                """, (vote_id, user_id, option))
                await conn.commit()
                logger.debug(f"投票回應插入成功：用戶 {user_id} 選擇 {option}")
                
    except Exception as e:
        logger.error(f"insert_vote_response 錯誤: {e}")
        raise

async def get_vote_statistics(vote_id):
    """統計票數：依選項計算總票數"""
    try:
        async with db_pool.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute("""
                    SELECT option_text, COUNT(*) FROM vote_responses
                    WHERE vote_id = %s
                    GROUP BY option_text
                """, (vote_id,))
                stats = {}
                async for row in cur:
                    stats[row[0]] = row[1]
                logger.debug(f"投票 #{vote_id} 統計：{stats}")
                return stats
                
    except Exception as e:
        logger.error(f"get_vote_statistics({vote_id}) 錯誤: {e}")
        return {}

async def get_expired_votes_to_announce():
    """查詢所有已過期但尚未公告的投票"""
    try:
        async with db_pool.connection() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cur:
                await cur.execute("""
                    SELECT * FROM votes
                    WHERE end_time <= UTC_TIMESTAMP() AND announced = FALSE
                """)
                rows = await cur.fetchall()
                
                processed_votes = []
                for row in rows:
                    row['is_multi'] = bool(row['is_multi'])
                    row['anonymous'] = bool(row['anonymous'])
                    
                    # 處理 JSON 欄位
                    try:
                        row['allowed_roles'] = json.loads(row.get('allowed_roles', '[]'))
                    except:
                        row['allowed_roles'] = []
                    
                    # 確保時間有時區資訊
                    if row['start_time'] and row['start_time'].tzinfo is None:
                        row['start_time'] = row['start_time'].replace(tzinfo=timezone.utc)
                    if row['end_time'] and row['end_time'].tzinfo is None:
                        row['end_time'] = row['end_time'].replace(tzinfo=timezone.utc)
                    
                    processed_votes.append(row)
                        
                return processed_votes
                
    except Exception as e:
        logger.error(f"get_expired_votes_to_announce 錯誤: {e}")
        return []

async def mark_vote_announced(vote_id):
    """將已公告的投票標記為 announced = TRUE"""
    try:
        async with db_pool.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute("""
                    UPDATE votes SET announced = TRUE WHERE id = %s
                """, (vote_id,))
                await conn.commit()
                logger.debug(f"投票 #{vote_id} 已標記為已公告")
                
    except Exception as e:
        logger.error(f"mark_vote_announced({vote_id}) 錯誤: {e}")

# ===== 歷史查詢功能 =====

async def get_vote_history(page: int = 1, status: str = "all", per_page: int = 10):
    """分頁查詢投票歷史記錄"""
    try:
        offset = (page - 1) * per_page
        
        # 根據狀態建立查詢條件
        if status == "active":
            where_clause = "WHERE end_time > UTC_TIMESTAMP()"
        elif status == "finished":
            where_clause = "WHERE end_time <= UTC_TIMESTAMP()"
        else:  # all
            where_clause = ""
        
        async with db_pool.connection() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cur:
                query = f"""
                    SELECT id, title, is_multi, anonymous, allowed_roles, 
                           channel_id, end_time, start_time, announced, guild_id, creator_id
                    FROM votes 
                    {where_clause}
                    ORDER BY start_time DESC 
                    LIMIT %s OFFSET %s
                """
                await cur.execute(query, (per_page, offset))
                rows = await cur.fetchall()
                
                # 處理資料格式
                processed_votes = []
                for row in rows:
                    row['is_multi'] = bool(row['is_multi'])
                    row['anonymous'] = bool(row['anonymous'])
                    row['announced'] = bool(row.get('announced', False))
                    
                    # 處理 JSON 欄位
                    try:
                        row['allowed_roles'] = json.loads(row.get('allowed_roles', '[]'))
                    except:
                        row['allowed_roles'] = []
                    
                    # 時區處理
                    if row['start_time'] and row['start_time'].tzinfo is None:
                        row['start_time'] = row['start_time'].replace(tzinfo=timezone.utc)
                    if row['end_time'] and row['end_time'].tzinfo is None:
                        row['end_time'] = row['end_time'].replace(tzinfo=timezone.utc)
                    
                    processed_votes.append(row)
                
                logger.debug(f"get_vote_history 返回 {len(processed_votes)} 筆記錄")
                return processed_votes
                
    except Exception as e:
        logger.error(f"get_vote_history 錯誤: {e}")
        return []

async def get_vote_count(status: str = "all") -> int:
    """取得投票總數"""
    try:
        # 根據狀態建立查詢條件
        if status == "active":
            where_clause = "WHERE end_time > UTC_TIMESTAMP()"
        elif status == "finished":
            where_clause = "WHERE end_time <= UTC_TIMESTAMP()"
        else:  # all
            where_clause = ""
        
        async with db_pool.connection() as conn:
            async with conn.cursor() as cur:
                query = f"SELECT COUNT(*) FROM votes {where_clause}"
                await cur.execute(query)
                result = await cur.fetchone()
                return result[0] if result else 0
                
    except Exception as e:
        logger.error(f"get_vote_count 錯誤: {e}")
        return 0

async def get_user_vote_history(user_id: int):
    """查詢特定用戶的投票記錄"""
    try:
        async with db_pool.connection() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cur:
                # 修正 SQL 查詢
                query = """
                    SELECT DISTINCT 
                        vr.vote_id,
                        v.title as vote_title,
                        v.start_time,
                        v.end_time
                    FROM vote_responses vr
                    JOIN votes v ON vr.vote_id = v.id
                    WHERE vr.user_id = %s
                    GROUP BY vr.vote_id, v.title, v.start_time, v.end_time
                    ORDER BY v.start_time DESC
                    LIMIT 50
                """
                await cur.execute(query, (user_id,))
                votes = await cur.fetchall()
                
                # 為每個投票取得用戶的選擇
                result = []
                for vote in votes:
                    # 取得該用戶在這個投票中的所有選擇
                    await cur.execute("""
                        SELECT option_text FROM vote_responses 
                        WHERE vote_id = %s AND user_id = %s
                    """, (vote['vote_id'], user_id))
                    
                    choices = []
                    async for choice_row in cur:
                        choices.append(choice_row[0])
                    
                    # 確保時間有時區資訊
                    vote_time = vote['start_time']
                    if vote_time and vote_time.tzinfo is None:
                        vote_time = vote_time.replace(tzinfo=timezone.utc)
                    
                    vote_info = {
                        'vote_id': vote['vote_id'],
                        'vote_title': vote['vote_title'],
                        'vote_time': vote_time,
                        'my_choices': choices
                    }
                    result.append(vote_info)
                
                return result
                
    except Exception as e:
        logger.error(f"get_user_vote_history({user_id}) 錯誤: {e}")
        return []

async def search_votes(keyword: str, limit: int = 20):
    """根據關鍵字搜尋投票"""
    try:
        async with db_pool.connection() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cur:
                await cur.execute("""
                    SELECT id, title, start_time, end_time, 
                           CASE WHEN end_time > UTC_TIMESTAMP() THEN 1 ELSE 0 END as is_active
                    FROM votes 
                    WHERE title LIKE %s
                    ORDER BY start_time DESC 
                    LIMIT %s
                """, (f"%{keyword}%", limit))
                
                results = []
                async for row in cur:
                    # 時區處理
                    if row['start_time'] and row['start_time'].tzinfo is None:
                        row['start_time'] = row['start_time'].replace(tzinfo=timezone.utc)
                    if row['end_time'] and row['end_time'].tzinfo is None:
                        row['end_time'] = row['end_time'].replace(tzinfo=timezone.utc)
                    
                    results.append(row)
                
                return results
                
    except Exception as e:
        logger.error(f"search_votes 錯誤: {e}")
        return []

# ===== 投票系統設定管理 =====

async def get_vote_settings(guild_id: int):
    """取得投票系統設定"""
    try:
        async with db_pool.connection() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cur:
                await cur.execute("""
                    SELECT * FROM vote_settings WHERE guild_id = %s
                """, (guild_id,))
                
                result = await cur.fetchone()
                if result:
                    # 處理JSON欄位
                    if result['allowed_creator_roles']:
                        result['allowed_creator_roles'] = json.loads(result['allowed_creator_roles'])
                    else:
                        result['allowed_creator_roles'] = []
                
                return result
                
    except Exception as e:
        logger.error(f"get_vote_settings({guild_id}) 錯誤: {e}")
        return None

async def update_vote_settings(guild_id: int, settings: dict):
    """更新投票系統設定"""
    try:
        async with db_pool.connection() as conn:
            async with conn.cursor() as cur:
                # 處理JSON欄位
                allowed_roles_json = json.dumps(settings.get('allowed_creator_roles', [])) if settings.get('allowed_creator_roles') else None
                
                await cur.execute("""
                    INSERT INTO vote_settings (
                        guild_id, default_vote_channel_id, announcement_channel_id,
                        max_vote_duration_hours, min_vote_duration_minutes,
                        require_role_to_create, allowed_creator_roles,
                        auto_announce_results, allow_anonymous_votes,
                        allow_multi_choice, is_enabled
                    ) VALUES (
                        %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                    ) ON DUPLICATE KEY UPDATE
                        default_vote_channel_id = VALUES(default_vote_channel_id),
                        announcement_channel_id = VALUES(announcement_channel_id),
                        max_vote_duration_hours = VALUES(max_vote_duration_hours),
                        min_vote_duration_minutes = VALUES(min_vote_duration_minutes),
                        require_role_to_create = VALUES(require_role_to_create),
                        allowed_creator_roles = VALUES(allowed_creator_roles),
                        auto_announce_results = VALUES(auto_announce_results),
                        allow_anonymous_votes = VALUES(allow_anonymous_votes),
                        allow_multi_choice = VALUES(allow_multi_choice),
                        is_enabled = VALUES(is_enabled),
                        updated_at = CURRENT_TIMESTAMP
                """, (
                    guild_id,
                    settings.get('default_vote_channel_id'),
                    settings.get('announcement_channel_id'),
                    settings.get('max_vote_duration_hours', 72),
                    settings.get('min_vote_duration_minutes', 60),
                    settings.get('require_role_to_create', False),
                    allowed_roles_json,
                    settings.get('auto_announce_results', True),
                    settings.get('allow_anonymous_votes', True),
                    settings.get('allow_multi_choice', True),
                    settings.get('is_enabled', True)
                ))
                
                await conn.commit()
                logger.info(f"投票系統設定已更新 (guild_id: {guild_id})")
                return True
                
    except Exception as e:
        logger.error(f"update_vote_settings({guild_id}) 錯誤: {e}")
        return False

async def set_default_vote_channel(guild_id: int, channel_id: int):
    """設定預設投票頻道"""
    try:
        async with db_pool.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute("""
                    INSERT INTO vote_settings (guild_id, default_vote_channel_id, is_enabled)
                    VALUES (%s, %s, TRUE)
                    ON DUPLICATE KEY UPDATE
                        default_vote_channel_id = VALUES(default_vote_channel_id),
                        updated_at = CURRENT_TIMESTAMP
                """, (guild_id, channel_id))
                
                await conn.commit()
                logger.info(f"預設投票頻道已設定: {channel_id} (guild_id: {guild_id})")
                return True
                
    except Exception as e:
        logger.error(f"set_default_vote_channel({guild_id}, {channel_id}) 錯誤: {e}")
        return False

async def set_announcement_channel(guild_id: int, channel_id: int):
    """設定投票結果公告頻道"""
    try:
        async with db_pool.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute("""
                    INSERT INTO vote_settings (guild_id, announcement_channel_id, is_enabled)
                    VALUES (%s, %s, TRUE)
                    ON DUPLICATE KEY UPDATE
                        announcement_channel_id = VALUES(announcement_channel_id),
                        updated_at = CURRENT_TIMESTAMP
                """, (guild_id, channel_id))
                
                await conn.commit()
                logger.info(f"投票結果公告頻道已設定: {channel_id} (guild_id: {guild_id})")
                return True
                
    except Exception as e:
        logger.error(f"set_announcement_channel({guild_id}, {channel_id}) 錯誤: {e}")
        return False

async def is_vote_system_enabled(guild_id: int):
    """檢查投票系統是否啟用"""
    try:
        settings = await get_vote_settings(guild_id)
        return settings and settings.get('is_enabled', True)
    except Exception as e:
        logger.error(f"is_vote_system_enabled({guild_id}) 錯誤: {e}")
        return True  # 預設啟用
