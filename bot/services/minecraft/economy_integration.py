"""
Minecraft 經濟整合系統
基於 zientis 架構設計，實現 Discord ↔ Minecraft 經濟跨平台同步
參考：zientis/discord/api/ZientisDiscordAPI.java
"""

import asyncio
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timedelta
from enum import Enum
import discord

from shared.logger import logger
from bot.db.database_manager import DatabaseManager
from bot.services.economy_manager import EconomyManager
from .rcon_manager import RCONManager


class TransactionType(Enum):
    """交易類型"""
    TRANSFER = "transfer"           # 玩家間轉帳
    PURCHASE = "purchase"           # 購買
    REWARD = "reward"              # 獎勵
    DAILY_BONUS = "daily_bonus"    # 每日獎勵
    EVENT_REWARD = "event_reward"  # 活動獎勵
    PENALTY = "penalty"            # 罰款


class EconomyIntegrationService:
    """經濟整合服務 - Discord ↔ Minecraft 跨平台同步"""
    
    def __init__(self, bot, rcon_manager: RCONManager):
        self.bot = bot
        self.db = DatabaseManager()
        self.economy_manager = EconomyManager()
        self.rcon = rcon_manager
        
        # 交易快取
        self._pending_transactions = {}
        self._transaction_history = {}
    
    async def initialize(self):
        """初始化經濟整合系統"""
        try:
            await self._create_tables()
            await self._sync_existing_data()
            logger.info("EconomyIntegrationService 初始化完成")
        except Exception as e:
            logger.error(f"EconomyIntegrationService 初始化失敗: {e}")
    
    async def _create_tables(self):
        """建立經濟整合相關資料庫表格"""
        tables = [
            # 跨平台經濟同步表
            """
            CREATE TABLE IF NOT EXISTS cross_platform_economy (
                id INT AUTO_INCREMENT PRIMARY KEY,
                discord_id BIGINT NOT NULL,
                minecraft_uuid VARCHAR(36),
                discord_balance DECIMAL(15,2) DEFAULT 0.00,
                minecraft_balance DECIMAL(15,2) DEFAULT 0.00,
                sync_enabled BOOLEAN DEFAULT TRUE,
                last_sync TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                UNIQUE KEY unique_discord (discord_id),
                INDEX idx_minecraft_uuid (minecraft_uuid),
                INDEX idx_sync_enabled (sync_enabled)
            )
            """,
            
            # 跨平台交易記錄表
            """
            CREATE TABLE IF NOT EXISTS cross_platform_transactions (
                id INT AUTO_INCREMENT PRIMARY KEY,
                transaction_id VARCHAR(64) UNIQUE NOT NULL,
                from_discord_id BIGINT,
                to_discord_id BIGINT,
                from_minecraft_uuid VARCHAR(36),
                to_minecraft_uuid VARCHAR(36),
                amount DECIMAL(15,2) NOT NULL,
                transaction_type ENUM('transfer', 'purchase', 'reward', 'daily_bonus', 'event_reward', 'penalty') NOT NULL,
                platform_source ENUM('discord', 'minecraft', 'system') DEFAULT 'discord',
                status ENUM('pending', 'completed', 'failed', 'cancelled') DEFAULT 'pending',
                description TEXT,
                metadata JSON,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                completed_at TIMESTAMP NULL,
                INDEX idx_from_discord (from_discord_id),
                INDEX idx_to_discord (to_discord_id),
                INDEX idx_status_type (status, transaction_type),
                INDEX idx_platform_time (platform_source, created_at)
            )
            """,
            
            # 經濟統計表
            """
            CREATE TABLE IF NOT EXISTS economy_statistics (
                id INT AUTO_INCREMENT PRIMARY KEY,
                date DATE NOT NULL,
                total_discord_balance DECIMAL(18,2) DEFAULT 0.00,
                total_minecraft_balance DECIMAL(18,2) DEFAULT 0.00,
                daily_transactions INT DEFAULT 0,
                daily_volume DECIMAL(15,2) DEFAULT 0.00,
                active_users INT DEFAULT 0,
                sync_operations INT DEFAULT 0,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                UNIQUE KEY unique_date (date)
            )
            """
        ]
        
        for table_sql in tables:
            await self.db.execute(table_sql)
    
    async def link_economy_account(self, discord_id: int, minecraft_uuid: str) -> bool:
        """連結 Discord 和 Minecraft 的經濟帳戶"""
        try:
            # 檢查是否已經連結
            existing = await self.db.fetchone(
                "SELECT id FROM cross_platform_economy WHERE discord_id = %s",
                (discord_id,)
            )
            
            if existing:
                # 更新 Minecraft UUID
                await self.db.execute(
                    "UPDATE cross_platform_economy SET minecraft_uuid = %s WHERE discord_id = %s",
                    (minecraft_uuid, discord_id)
                )
            else:
                # 建立新的連結
                await self.db.execute(
                    """
                    INSERT INTO cross_platform_economy (discord_id, minecraft_uuid, discord_balance, minecraft_balance)
                    VALUES (%s, %s, 0.00, 0.00)
                    """,
                    (discord_id, minecraft_uuid)
                )
            
            # 初始同步餘額
            await self._sync_balance(discord_id)
            
            logger.info(f"經濟帳戶連結成功: Discord {discord_id} ↔ Minecraft {minecraft_uuid}")
            return True
            
        except Exception as e:
            logger.error(f"連結經濟帳戶失敗: {e}")
            return False
    
    async def get_balance(self, discord_id: int, platform: str = "both") -> Dict[str, float]:
        """獲取玩家餘額"""
        try:
            result = await self.db.fetchone(
                "SELECT discord_balance, minecraft_balance FROM cross_platform_economy WHERE discord_id = %s",
                (discord_id,)
            )
            
            if not result:
                return {"discord": 0.0, "minecraft": 0.0, "total": 0.0}
            
            discord_balance = float(result['discord_balance'])
            minecraft_balance = float(result['minecraft_balance'])
            total_balance = discord_balance + minecraft_balance
            
            if platform == "discord":
                return {"discord": discord_balance}
            elif platform == "minecraft":
                return {"minecraft": minecraft_balance}
            else:
                return {
                    "discord": discord_balance,
                    "minecraft": minecraft_balance,
                    "total": total_balance
                }
                
        except Exception as e:
            logger.error(f"獲取餘額失敗 ({discord_id}): {e}")
            return {"discord": 0.0, "minecraft": 0.0, "total": 0.0}
    
    async def transfer_money(self, from_discord_id: int, to_discord_id: int, 
                           amount: float, description: str = "") -> Tuple[bool, str]:
        """玩家間轉帳"""
        try:
            # 驗證發送者餘額
            sender_balance = await self.get_balance(from_discord_id)
            if sender_balance["total"] < amount:
                return False, f"餘額不足。您的總餘額: {sender_balance['total']:.2f}，需要: {amount:.2f}"
            
            # 檢查接收者是否存在
            receiver = await self.db.fetchone(
                "SELECT id FROM cross_platform_economy WHERE discord_id = %s",
                (to_discord_id,)
            )
            
            if not receiver:
                # 自動建立接收者帳戶
                await self.db.execute(
                    "INSERT INTO cross_platform_economy (discord_id, discord_balance, minecraft_balance) VALUES (%s, 0.00, 0.00)",
                    (to_discord_id,)
                )
            
            # 生成交易 ID
            transaction_id = f"transfer_{from_discord_id}_{to_discord_id}_{int(datetime.now().timestamp())}"
            
            # 記錄交易
            await self.db.execute(
                """
                INSERT INTO cross_platform_transactions 
                (transaction_id, from_discord_id, to_discord_id, amount, transaction_type, 
                 platform_source, status, description)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (transaction_id, from_discord_id, to_discord_id, amount, 
                 TransactionType.TRANSFER.value, "discord", "pending", description)
            )
            
            # 執行轉帳 (優先從 Discord 餘額扣除)
            sender_info = await self.db.fetchone(
                "SELECT discord_balance, minecraft_balance FROM cross_platform_economy WHERE discord_id = %s",
                (from_discord_id,)
            )
            
            discord_deduct = min(amount, float(sender_info['discord_balance']))
            minecraft_deduct = amount - discord_deduct
            
            # 更新發送者餘額
            await self.db.execute(
                """
                UPDATE cross_platform_economy 
                SET discord_balance = discord_balance - %s,
                    minecraft_balance = minecraft_balance - %s
                WHERE discord_id = %s
                """,
                (discord_deduct, minecraft_deduct, from_discord_id)
            )
            
            # 更新接收者餘額 (優先加到 Discord 餘額)
            await self.db.execute(
                """
                UPDATE cross_platform_economy 
                SET discord_balance = discord_balance + %s
                WHERE discord_id = %s
                """,
                (amount, to_discord_id)
            )
            
            # 標記交易完成
            await self.db.execute(
                "UPDATE cross_platform_transactions SET status = 'completed', completed_at = NOW() WHERE transaction_id = %s",
                (transaction_id,)
            )
            
            # 如果涉及 Minecraft 餘額，同步到遊戲內
            if minecraft_deduct > 0:
                await self._sync_minecraft_balance(from_discord_id)
            await self._sync_minecraft_balance(to_discord_id)
            
            logger.info(f"轉帳成功: {from_discord_id} → {to_discord_id}, 金額: {amount}")
            return True, f"轉帳成功！已將 {amount:.2f} 點數轉給目標用戶"
            
        except Exception as e:
            logger.error(f"轉帳失敗: {e}")
            return False, f"轉帳失敗: {str(e)}"
    
    async def add_money(self, discord_id: int, amount: float, transaction_type: TransactionType, 
                       description: str = "") -> bool:
        """為玩家增加金錢 (獎勵、每日獎勵等)"""
        try:
            # 檢查帳戶是否存在
            account = await self.db.fetchone(
                "SELECT id FROM cross_platform_economy WHERE discord_id = %s",
                (discord_id,)
            )
            
            if not account:
                # 建立帳戶
                await self.db.execute(
                    "INSERT INTO cross_platform_economy (discord_id, discord_balance, minecraft_balance) VALUES (%s, 0.00, 0.00)",
                    (discord_id,)
                )
            
            # 生成交易 ID
            transaction_id = f"{transaction_type.value}_{discord_id}_{int(datetime.now().timestamp())}"
            
            # 記錄交易
            await self.db.execute(
                """
                INSERT INTO cross_platform_transactions 
                (transaction_id, to_discord_id, amount, transaction_type, 
                 platform_source, status, description)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                """,
                (transaction_id, discord_id, amount, transaction_type.value, "system", "completed", description)
            )
            
            # 增加餘額 (加到 Discord 餘額)
            await self.db.execute(
                "UPDATE cross_platform_economy SET discord_balance = discord_balance + %s WHERE discord_id = %s",
                (amount, discord_id)
            )
            
            logger.info(f"增加金錢成功: {discord_id}, 金額: {amount}, 類型: {transaction_type.value}")
            return True
            
        except Exception as e:
            logger.error(f"增加金錢失敗: {e}")
            return False
    
    async def get_transaction_history(self, discord_id: int, limit: int = 10) -> List[Dict[str, Any]]:
        """獲取交易記錄"""
        try:
            transactions = await self.db.fetchall(
                """
                SELECT transaction_id, from_discord_id, to_discord_id, amount, 
                       transaction_type, platform_source, status, description, 
                       created_at, completed_at
                FROM cross_platform_transactions 
                WHERE from_discord_id = %s OR to_discord_id = %s
                ORDER BY created_at DESC
                LIMIT %s
                """,
                (discord_id, discord_id, limit)
            )
            
            result = []
            for tx in transactions:
                result.append({
                    'transaction_id': tx['transaction_id'],
                    'from_discord_id': tx['from_discord_id'],
                    'to_discord_id': tx['to_discord_id'],
                    'amount': float(tx['amount']),
                    'transaction_type': tx['transaction_type'],
                    'platform_source': tx['platform_source'],
                    'status': tx['status'],
                    'description': tx['description'],
                    'created_at': tx['created_at'],
                    'completed_at': tx['completed_at'],
                    'is_sender': tx['from_discord_id'] == discord_id,
                    'is_receiver': tx['to_discord_id'] == discord_id
                })
            
            return result
            
        except Exception as e:
            logger.error(f"獲取交易記錄失敗 ({discord_id}): {e}")
            return []
    
    async def get_wealth_ranking(self, limit: int = 10) -> List[Dict[str, Any]]:
        """獲取財富排行榜"""
        try:
            ranking = await self.db.fetchall(
                """
                SELECT cpe.discord_id, 
                       (cpe.discord_balance + cpe.minecraft_balance) as total_balance,
                       cpe.discord_balance, cpe.minecraft_balance,
                       mp.minecraft_username
                FROM cross_platform_economy cpe
                LEFT JOIN minecraft_players mp ON cpe.discord_id = mp.discord_id
                WHERE cpe.sync_enabled = TRUE
                ORDER BY total_balance DESC
                LIMIT %s
                """,
                (limit,)
            )
            
            result = []
            for i, record in enumerate(ranking):
                result.append({
                    'rank': i + 1,
                    'discord_id': record['discord_id'],
                    'minecraft_username': record['minecraft_username'],
                    'total_balance': float(record['total_balance']),
                    'discord_balance': float(record['discord_balance']),
                    'minecraft_balance': float(record['minecraft_balance'])
                })
            
            return result
            
        except Exception as e:
            logger.error(f"獲取財富排行榜失敗: {e}")
            return []
    
    async def _sync_balance(self, discord_id: int) -> bool:
        """同步 Discord 和 Minecraft 餘額"""
        try:
            # 這裡可以實現與 Minecraft 經濟系統的實際同步
            # 目前作為框架，實際實施時需要根據具體的 Minecraft 經濟插件調整
            
            # 獲取當前記錄
            record = await self.db.fetchone(
                "SELECT minecraft_uuid FROM cross_platform_economy WHERE discord_id = %s",
                (discord_id,)
            )
            
            if record and record['minecraft_uuid']:
                # 使用 RCON 查詢 Minecraft 內的餘額 (假設使用 EssentialsX)
                # result = await self.rcon.execute_command(f"money {record['minecraft_uuid']}")
                # 這裡需要解析返回結果並更新資料庫
                pass
            
            # 更新同步時間
            await self.db.execute(
                "UPDATE cross_platform_economy SET last_sync = NOW() WHERE discord_id = %s",
                (discord_id,)
            )
            
            return True
            
        except Exception as e:
            logger.error(f"同步餘額失敗 ({discord_id}): {e}")
            return False
    
    async def _sync_minecraft_balance(self, discord_id: int) -> bool:
        """同步餘額到 Minecraft"""
        try:
            # 獲取用戶資訊
            record = await self.db.fetchone(
                """
                SELECT cpe.minecraft_balance, mp.minecraft_username
                FROM cross_platform_economy cpe
                LEFT JOIN minecraft_players mp ON cpe.discord_id = mp.discord_id
                WHERE cpe.discord_id = %s
                """,
                (discord_id,)
            )
            
            if record and record['minecraft_username']:
                # 使用 RCON 設置 Minecraft 內的餘額 (假設使用 EssentialsX)
                balance = float(record['minecraft_balance'])
                username = record['minecraft_username']
                
                # 這裡需要根據實際的 Minecraft 經濟插件調整指令
                # await self.rcon.execute_command(f"eco set {username} {balance}")
                
                logger.debug(f"同步 Minecraft 餘額: {username} = {balance}")
            
            return True
            
        except Exception as e:
            logger.error(f"同步 Minecraft 餘額失敗 ({discord_id}): {e}")
            return False
    
    async def _sync_existing_data(self):
        """同步現有數據"""
        try:
            # 載入現有的玩家綁定資料，建立經濟帳戶
            players = await self.db.fetchall(
                """
                SELECT discord_id, minecraft_uuid, minecraft_username 
                FROM minecraft_players 
                WHERE is_active = TRUE
                """
            )
            
            for player in players:
                existing = await self.db.fetchone(
                    "SELECT id FROM cross_platform_economy WHERE discord_id = %s",
                    (player['discord_id'],)
                )
                
                if not existing:
                    await self.db.execute(
                        """
                        INSERT INTO cross_platform_economy 
                        (discord_id, minecraft_uuid, discord_balance, minecraft_balance)
                        VALUES (%s, %s, 0.00, 0.00)
                        """,
                        (player['discord_id'], player['minecraft_uuid'])
                    )
            
            logger.info(f"同步了 {len(players)} 個現有玩家的經濟帳戶")
            
        except Exception as e:
            logger.error(f"同步現有數據失敗: {e}")
    
    def format_balance_display(self, balance_data: Dict[str, float], username: str = None) -> str:
        """格式化餘額顯示"""
        total = balance_data.get('total', 0.0)
        discord_bal = balance_data.get('discord', 0.0)
        minecraft_bal = balance_data.get('minecraft', 0.0)
        
        display_name = username or "您"
        
        return f"""
        💰 **{display_name}的經濟狀況**
        
        **總餘額**: {total:,.2f} 點數
        
        **平台分佈**:
        🔮 Discord: {discord_bal:,.2f} 點數
        ⛏️ Minecraft: {minecraft_bal:,.2f} 點數
        
        *跨平台餘額可自由轉換和使用*
        """
    
    def format_ranking_display(self, ranking: List[Dict[str, Any]]) -> str:
        """格式化排行榜顯示"""
        if not ranking:
            return "目前沒有排行榜資料"
        
        result = "🏆 **財富排行榜** 💰\n\n"
        
        for entry in ranking:
            rank_emoji = {1: "🥇", 2: "🥈", 3: "🥉"}.get(entry['rank'], "🏅")
            username = entry.get('minecraft_username') or f"玩家{entry['discord_id']}"
            total = entry['total_balance']
            
            result += f"{rank_emoji} **#{entry['rank']}** {username}: {total:,.2f} 點數\n"
        
        return result