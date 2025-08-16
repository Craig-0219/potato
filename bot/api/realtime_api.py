# bot/api/realtime_api.py
"""
實時投票統計 API
提供 WebSocket 和 HTTP 端點用於即時投票數據更新
"""

import asyncio
import json
from datetime import datetime
from typing import Dict, List, Set, Optional, Any
from fastapi import WebSocket, WebSocketDisconnect, APIRouter, HTTPException
from fastapi.responses import JSONResponse
import aiomysql

from bot.db.pool import db_pool
from bot.services.statistics_manager import StatisticsManager
from shared.logger import logger

# WebSocket 連接管理器
class ConnectionManager:
    """WebSocket 連接管理器"""
    
    def __init__(self):
        self.active_connections: Dict[str, Set[WebSocket]] = {}
        self.guild_subscriptions: Dict[int, Set[WebSocket]] = {}
        
    async def connect(self, websocket: WebSocket, guild_id: int, client_id: str):
        """連接新的 WebSocket 客戶端"""
        await websocket.accept()
        
        # 添加到活躍連接
        if client_id not in self.active_connections:
            self.active_connections[client_id] = set()
        self.active_connections[client_id].add(websocket)
        
        # 添加到公會訂閱
        if guild_id not in self.guild_subscriptions:
            self.guild_subscriptions[guild_id] = set()
        self.guild_subscriptions[guild_id].add(websocket)
        
        logger.info(f"WebSocket 客戶端已連接: {client_id}, 公會: {guild_id}")
        
    def disconnect(self, websocket: WebSocket, guild_id: int, client_id: str):
        """斷開 WebSocket 連接"""
        try:
            # 從活躍連接移除
            if client_id in self.active_connections:
                self.active_connections[client_id].discard(websocket)
                if not self.active_connections[client_id]:
                    del self.active_connections[client_id]
            
            # 從公會訂閱移除
            if guild_id in self.guild_subscriptions:
                self.guild_subscriptions[guild_id].discard(websocket)
                if not self.guild_subscriptions[guild_id]:
                    del self.guild_subscriptions[guild_id]
            
            logger.info(f"WebSocket 客戶端已斷開: {client_id}, 公會: {guild_id}")
        except Exception as e:
            logger.error(f"斷開連接時發生錯誤: {e}")
    
    async def send_personal_message(self, message: str, client_id: str):
        """發送個人訊息"""
        if client_id in self.active_connections:
            disconnected = set()
            for websocket in self.active_connections[client_id]:
                try:
                    await websocket.send_text(message)
                except:
                    disconnected.add(websocket)
            
            # 清理已斷開的連接
            for websocket in disconnected:
                self.active_connections[client_id].discard(websocket)
    
    async def broadcast_to_guild(self, message: str, guild_id: int):
        """向特定公會廣播訊息"""
        if guild_id in self.guild_subscriptions:
            disconnected = set()
            for websocket in self.guild_subscriptions[guild_id]:
                try:
                    await websocket.send_text(message)
                except:
                    disconnected.add(websocket)
            
            # 清理已斷開的連接
            for websocket in disconnected:
                self.guild_subscriptions[guild_id].discard(websocket)
    
    async def broadcast_to_all(self, message: str):
        """向所有連接廣播訊息"""
        for guild_id in self.guild_subscriptions:
            await self.broadcast_to_guild(message, guild_id)

# 全局連接管理器和統計管理器
manager = ConnectionManager()
stats_manager = StatisticsManager()

# API 路由器
router = APIRouter(prefix="/api/realtime", tags=["realtime"])

@router.websocket("/ws/{guild_id}/{client_id}")
async def websocket_endpoint(websocket: WebSocket, guild_id: int, client_id: str):
    """WebSocket 端點"""
    await manager.connect(websocket, guild_id, client_id)
    
    try:
        # 發送初始數據
        initial_data = await get_real_time_vote_stats(guild_id)
        await websocket.send_text(json.dumps({
            "type": "initial_data",
            "data": initial_data,
            "timestamp": datetime.now().isoformat()
        }))
        
        # 保持連接並處理訊息
        while True:
            try:
                # 等待客戶端訊息（心跳或請求）
                data = await asyncio.wait_for(websocket.receive_text(), timeout=30.0)
                message = json.loads(data)
                
                if message.get("type") == "ping":
                    # 回應心跳
                    await websocket.send_text(json.dumps({
                        "type": "pong",
                        "timestamp": datetime.now().isoformat()
                    }))
                elif message.get("type") == "request_update":
                    # 發送最新數據
                    current_data = await get_real_time_vote_stats(guild_id)
                    await websocket.send_text(json.dumps({
                        "type": "data_update",
                        "data": current_data,
                        "timestamp": datetime.now().isoformat()
                    }))
                    
            except asyncio.TimeoutError:
                # 心跳超時，發送ping
                await websocket.send_text(json.dumps({
                    "type": "ping",
                    "timestamp": datetime.now().isoformat()
                }))
                
    except WebSocketDisconnect:
        manager.disconnect(websocket, guild_id, client_id)
    except Exception as e:
        logger.error(f"WebSocket 連接錯誤: {e}")
        manager.disconnect(websocket, guild_id, client_id)

async def get_real_time_vote_stats(guild_id: int) -> Dict[str, Any]:
    """獲取實時投票統計數據"""
    try:
        async with db_pool.connection() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cursor:
                # 獲取活躍投票
                await cursor.execute("""
                    SELECT 
                        v.id,
                        v.title,
                        v.start_time,
                        v.end_time,
                        v.is_multi as is_multiple,
                        v.is_anonymous,
                        (SELECT COUNT(DISTINCT user_id) FROM vote_responses vr WHERE vr.vote_id = v.id) as total_participants,
                        (SELECT JSON_ARRAYAGG(
                            JSON_OBJECT(
                                'option_id', vo.id,
                                'text', vo.option_text,
                                'votes', (
                                    SELECT COUNT(*) 
                                    FROM vote_responses vr2 
                                    WHERE vr2.vote_id = v.id 
                                    AND JSON_CONTAINS(vr2.selected_options, CAST(vo.id AS JSON))
                                )
                            )
                        ) FROM vote_options vo WHERE vo.vote_id = v.id) as options_data
                    FROM votes v
                    WHERE v.guild_id = %s 
                    AND v.end_time > NOW()
                    ORDER BY v.start_time DESC
                    LIMIT 10
                """, (guild_id,))
                active_votes = await cursor.fetchall()
                
                # 獲取最近完成的投票
                await cursor.execute("""
                    SELECT 
                        v.id,
                        v.title,
                        v.start_time,
                        v.end_time,
                        v.is_multi as is_multiple,
                        v.is_anonymous,
                        (SELECT COUNT(DISTINCT user_id) FROM vote_responses vr WHERE vr.vote_id = v.id) as total_participants,
                        (SELECT JSON_ARRAYAGG(
                            JSON_OBJECT(
                                'option_id', vo.id,
                                'text', vo.option_text,
                                'votes', (
                                    SELECT COUNT(*) 
                                    FROM vote_responses vr2 
                                    WHERE vr2.vote_id = v.id 
                                    AND JSON_CONTAINS(vr2.selected_options, CAST(vo.id AS JSON))
                                )
                            )
                        ) FROM vote_options vo WHERE vo.vote_id = v.id) as options_data
                    FROM votes v
                    WHERE v.guild_id = %s 
                    AND v.end_time <= NOW()
                    ORDER BY v.end_time DESC
                    LIMIT 5
                """, (guild_id,))
                recent_completed = await cursor.fetchall()
                
                # 獲取今日統計
                await cursor.execute("""
                    SELECT 
                        COUNT(*) as votes_created_today,
                        COUNT(CASE WHEN end_time <= NOW() THEN 1 END) as votes_completed_today,
                        COALESCE(SUM(
                            (SELECT COUNT(DISTINCT user_id) FROM vote_responses vr WHERE vr.vote_id = v.id)
                        ), 0) as total_participants_today
                    FROM votes v
                    WHERE v.guild_id = %s 
                    AND DATE(v.start_time) = CURDATE()
                """, (guild_id,))
                today_stats = await cursor.fetchone()
                
                # 處理選項數據
                def process_vote_data(votes):
                    processed = []
                    for vote in votes:
                        vote_data = dict(vote)
                        if vote_data.get('options_data'):
                            try:
                                vote_data['options'] = json.loads(vote_data['options_data'])
                            except:
                                vote_data['options'] = []
                        else:
                            vote_data['options'] = []
                        del vote_data['options_data']
                        processed.append(vote_data)
                    return processed
                
                return {
                    'active_votes': process_vote_data(active_votes),
                    'recent_completed': process_vote_data(recent_completed),
                    'today_statistics': {
                        'votes_created': today_stats['votes_created_today'] if today_stats else 0,
                        'votes_completed': today_stats['votes_completed_today'] if today_stats else 0,
                        'total_participants': today_stats['total_participants_today'] if today_stats else 0
                    },
                    'summary': {
                        'active_count': len(active_votes),
                        'total_active_participants': sum(vote.get('total_participants', 0) for vote in active_votes)
                    },
                    'last_updated': datetime.now().isoformat()
                }
                
    except Exception as e:
        logger.error(f"獲取實時投票統計失敗: {e}")
        return {
            'error': str(e),
            'active_votes': [],
            'recent_completed': [],
            'today_statistics': {'votes_created': 0, 'votes_completed': 0, 'total_participants': 0},
            'summary': {'active_count': 0, 'total_active_participants': 0}
        }

@router.get("/vote-stats/{guild_id}")
async def get_realtime_vote_stats_endpoint(guild_id: int):
    """HTTP 端點獲取實時投票統計"""
    try:
        data = await get_real_time_vote_stats(guild_id)
        return JSONResponse(content=data)
    except Exception as e:
        logger.error(f"HTTP 端點錯誤: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/broadcast/{guild_id}")
async def broadcast_update(guild_id: int, update_type: str = "vote_update"):
    """手動觸發廣播更新"""
    try:
        # 獲取最新數據
        current_data = await get_real_time_vote_stats(guild_id)
        
        # 廣播更新
        message = json.dumps({
            "type": "data_update",
            "update_type": update_type,
            "data": current_data,
            "timestamp": datetime.now().isoformat()
        })
        
        await manager.broadcast_to_guild(message, guild_id)
        
        return JSONResponse(content={
            "success": True,
            "message": f"已向公會 {guild_id} 廣播更新",
            "connections": len(manager.guild_subscriptions.get(guild_id, set()))
        })
        
    except Exception as e:
        logger.error(f"廣播更新失敗: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/connections")
async def get_connection_status():
    """獲取連接狀態"""
    return JSONResponse(content={
        "total_connections": sum(len(connections) for connections in manager.active_connections.values()),
        "guilds_connected": len(manager.guild_subscriptions),
        "guild_connections": {
            str(guild_id): len(connections) 
            for guild_id, connections in manager.guild_subscriptions.items()
        }
    })

# 自動更新任務
async def auto_update_task():
    """自動更新任務，定期向所有連接的客戶端發送更新"""
    while True:
        try:
            await asyncio.sleep(30)  # 每30秒更新一次
            
            # 為每個活躍的公會發送更新
            for guild_id in list(manager.guild_subscriptions.keys()):
                if manager.guild_subscriptions.get(guild_id):
                    try:
                        current_data = await get_real_time_vote_stats(guild_id)
                        message = json.dumps({
                            "type": "auto_update",
                            "data": current_data,
                            "timestamp": datetime.now().isoformat()
                        })
                        await manager.broadcast_to_guild(message, guild_id)
                    except Exception as e:
                        logger.error(f"自動更新公會 {guild_id} 失敗: {e}")
                        
        except Exception as e:
            logger.error(f"自動更新任務錯誤: {e}")

# 自動更新任務將在應用啟動時創建
# 不在模組載入時啟動，避免事件循環問題
auto_update_task_handle = None

async def start_auto_update_task():
    """啟動自動更新任務"""
    global auto_update_task_handle
    if auto_update_task_handle is None:
        auto_update_task_handle = asyncio.create_task(auto_update_task())
        logger.info("✅ 自動更新任務已啟動")

async def stop_auto_update_task():
    """停止自動更新任務"""
    global auto_update_task_handle
    if auto_update_task_handle and not auto_update_task_handle.done():
        auto_update_task_handle.cancel()
        try:
            await auto_update_task_handle
        except asyncio.CancelledError:
            pass
        auto_update_task_handle = None
        logger.info("🔄 自動更新任務已停止")