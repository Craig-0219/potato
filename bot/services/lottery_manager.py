# bot/services/lottery_manager.py
"""
抽獎系統管理器
處理抽獎的創建、管理、開獎等核心邏輯
"""

import asyncio
import random
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
import discord
from discord.ext import tasks

from bot.db.lottery_dao import LotteryDAO, LotteryData
from bot.utils.embed_builder import EmbedBuilder
from shared.logger import logger


class LotteryManager:
    """抽獎系統管理器"""
    
    def __init__(self, bot=None):
        self.bot = bot
        self.dao = LotteryDAO()
        self._running_lotteries = {}  # lottery_id -> task
        
        # 啟動背景任務
        if bot:
            self.lottery_scheduler.start()

    async def create_lottery(self, guild: discord.Guild, creator: discord.Member, 
                           lottery_config: Dict[str, Any]) -> Tuple[bool, str, Optional[int]]:
        """創建抽獎"""
        try:
            # 檢查權限和限制
            settings = await self.dao.get_lottery_settings(guild.id)
            
            # 檢查同時抽獎數量限制
            active_lotteries = await self.dao.get_active_lotteries(guild.id)
            if len(active_lotteries) >= settings.get('max_concurrent_lotteries', 3):
                return False, f"同時進行的抽獎數量已達上限 ({settings.get('max_concurrent_lotteries', 3)})，請等待現有抽獎結束", None
            
            # 檢查管理權限
            if not await self._check_lottery_permission(creator, settings):
                return False, "您沒有權限創建抽獎", None
            
            # 處理時間設定
            start_time = datetime.now()
            if lottery_config.get('start_delay_minutes', 0) > 0:
                start_time += timedelta(minutes=lottery_config['start_delay_minutes'])
            
            # 計算結束時間
            duration_hours = lottery_config.get('duration_hours', settings.get('default_duration_hours', 24))
            end_time = start_time + timedelta(hours=duration_hours)
            
            # 創建抽獎資料
            lottery_data = LotteryData(
                guild_id=guild.id,
                name=lottery_config['name'],
                description=lottery_config.get('description'),
                creator_id=creator.id,
                channel_id=lottery_config['channel_id'],
                prize_type=lottery_config.get('prize_type', 'custom'),
                prize_data=lottery_config.get('prize_data'),
                winner_count=lottery_config.get('winner_count', 1),
                entry_method=lottery_config.get('entry_method', 'reaction'),
                required_roles=lottery_config.get('required_roles'),
                excluded_roles=lottery_config.get('excluded_roles'),
                min_account_age_days=lottery_config.get('min_account_age_days', 0),
                min_server_join_days=lottery_config.get('min_server_join_days', 0),
                start_time=start_time,
                end_time=end_time,
                auto_end=lottery_config.get('auto_end', True)
            )
            
            # 儲存到資料庫
            lottery_id = await self.dao.create_lottery(lottery_data)
            
            if lottery_id:
                logger.info(f"創建抽獎成功: {lottery_id} - {lottery_data.name}")
                return True, f"抽獎 '{lottery_data.name}' 創建成功！ID: {lottery_id}", lottery_id
            else:
                return False, "創建抽獎失敗，請稍後再試", None
                
        except Exception as e:
            logger.error(f"創建抽獎失敗: {e}")
            return False, f"創建抽獎時發生錯誤: {str(e)}", None

    async def start_lottery(self, lottery_id: int, channel: discord.TextChannel) -> Tuple[bool, str, Optional[discord.Message]]:
        """開始抽獎"""
        try:
            lottery = await self.dao.get_lottery(lottery_id)
            if not lottery:
                return False, "抽獎不存在", None
            
            if lottery['status'] != 'pending':
                return False, f"抽獎狀態不正確: {lottery['status']}", None
            
            # 創建抽獎公告嵌入
            embed = await self._create_lottery_embed(lottery)
            
            # 發送訊息
            message = await channel.send(embed=embed)
            
            # 如果是反應參與，添加反應
            if lottery['entry_method'] in ['reaction', 'both']:
                await message.add_reaction('🎉')
            
            # 更新抽獎狀態和訊息ID
            await self.dao.update_lottery_status(lottery_id, 'active', message.id)
            
            # 安排自動結束
            if lottery['auto_end']:
                await self._schedule_lottery_end(lottery_id, lottery['end_time'])
            
            logger.info(f"抽獎開始: {lottery_id} - {lottery['name']}")
            return True, "抽獎已開始！", message
            
        except Exception as e:
            logger.error(f"開始抽獎失敗: {e}")
            return False, f"開始抽獎時發生錯誤: {str(e)}", None

    async def join_lottery(self, lottery_id: int, user: discord.Member, method: str = "reaction") -> Tuple[bool, str]:
        """參與抽獎"""
        try:
            lottery = await self.dao.get_lottery(lottery_id)
            if not lottery:
                return False, "抽獎不存在"
            
            if lottery['status'] != 'active':
                return False, f"抽獎未在進行中 (狀態: {lottery['status']})"
            
            # 檢查是否已過期
            if lottery['end_time'] < datetime.now():
                return False, "抽獎已結束"
            
            # 檢查參與條件
            validation_result = await self._validate_participant(user, lottery)
            if not validation_result[0]:
                return False, validation_result[1]
            
            # 添加參與者
            success = await self.dao.add_entry(lottery_id, user.id, user.display_name, method)
            
            if success:
                return True, "成功參與抽獎！"
            else:
                return False, "參與抽獎失敗，您可能已經參與過了"
                
        except Exception as e:
            logger.error(f"參與抽獎失敗: {e}")
            return False, f"參與抽獎時發生錯誤: {str(e)}"

    async def leave_lottery(self, lottery_id: int, user: discord.Member) -> Tuple[bool, str]:
        """退出抽獎"""
        try:
            lottery = await self.dao.get_lottery(lottery_id)
            if not lottery:
                return False, "抽獎不存在"
            
            if lottery['status'] != 'active':
                return False, f"抽獎未在進行中 (狀態: {lottery['status']})"
            
            # 移除參與者
            success = await self.dao.remove_entry(lottery_id, user.id)
            
            if success:
                return True, "已退出抽獎"
            else:
                return False, "您沒有參與這個抽獎"
                
        except Exception as e:
            logger.error(f"退出抽獎失敗: {e}")
            return False, f"退出抽獎時發生錯誤: {str(e)}"

    async def end_lottery(self, lottery_id: int, channel: discord.TextChannel, forced: bool = False) -> Tuple[bool, str, List[Dict]]:
        """結束抽獎並選出中獎者"""
        try:
            lottery = await self.dao.get_lottery(lottery_id)
            if not lottery:
                return False, "抽獎不存在", []
            
            if lottery['status'] != 'active' and not forced:
                return False, f"抽獎狀態不正確: {lottery['status']}", []
            
            # 獲取所有參與者
            entries = await self.dao.get_entries(lottery_id)
            
            if not entries:
                # 沒有參與者
                await self.dao.update_lottery_status(lottery_id, 'cancelled')
                embed = EmbedBuilder.build(
                    title="🎲 抽獎結束",
                    description=f"**{lottery['name']}**\n\n❌ 沒有參與者，抽獎已取消",
                    color='warning'
                )
                await channel.send(embed=embed)
                return True, "抽獎因沒有參與者而取消", []
            
            # 選出中獎者
            winner_count = min(lottery['winner_count'], len(entries))
            winners_data = []
            
            # 隨機選擇中獎者
            selected_entries = random.sample(entries, winner_count)
            
            for i, entry in enumerate(selected_entries, 1):
                winners_data.append((entry['user_id'], entry['username'], i))
            
            # 儲存中獎者
            await self.dao.select_winners(lottery_id, winners_data)
            
            # 創建結果公告
            winners = await self.dao.get_winners(lottery_id)
            embed = await self._create_results_embed(lottery, winners, len(entries))
            await channel.send(embed=embed)
            
            # 取消自動結束任務
            if lottery_id in self._running_lotteries:
                self._running_lotteries[lottery_id].cancel()
                del self._running_lotteries[lottery_id]
            
            logger.info(f"抽獎結束: {lottery_id} - {lottery['name']}, 中獎者: {len(winners)}")
            return True, f"抽獎已結束，共 {len(winners)} 位中獎者", winners
            
        except Exception as e:
            logger.error(f"結束抽獎失敗: {e}")
            return False, f"結束抽獎時發生錯誤: {str(e)}", []

    async def get_lottery_info(self, lottery_id: int) -> Optional[Dict]:
        """獲取抽獎資訊"""
        try:
            lottery = await self.dao.get_lottery(lottery_id)
            if not lottery:
                return None
            
            # 獲取參與者數量
            entries = await self.dao.get_entries(lottery_id)
            lottery['participant_count'] = len(entries)
            
            # 獲取中獎者（如果已結束）
            if lottery['status'] == 'ended':
                winners = await self.dao.get_winners(lottery_id)
                lottery['winners'] = winners
            
            return lottery
            
        except Exception as e:
            logger.error(f"獲取抽獎資訊失敗: {e}")
            return None

    async def _validate_participant(self, user: discord.Member, lottery: Dict) -> Tuple[bool, str]:
        """驗證參與者條件"""
        try:
            # 檢查帳號年齡
            if lottery['min_account_age_days'] > 0:
                account_age = (datetime.now(user.created_at.tzinfo) - user.created_at).days
                if account_age < lottery['min_account_age_days']:
                    return False, f"帳號年齡需要至少 {lottery['min_account_age_days']} 天"
            
            # 檢查加入伺服器時間
            if lottery['min_server_join_days'] > 0 and user.joined_at:
                join_age = (datetime.now(user.joined_at.tzinfo) - user.joined_at).days
                if join_age < lottery['min_server_join_days']:
                    return False, f"加入伺服器需要至少 {lottery['min_server_join_days']} 天"
            
            # 檢查必需角色
            if lottery['required_roles']:
                user_role_ids = [role.id for role in user.roles]
                required_roles = lottery['required_roles']
                if not any(role_id in user_role_ids for role_id in required_roles):
                    return False, "您沒有參與抽獎所需的角色"
            
            # 檢查排除角色
            if lottery['excluded_roles']:
                user_role_ids = [role.id for role in user.roles]
                excluded_roles = lottery['excluded_roles']
                if any(role_id in user_role_ids for role_id in excluded_roles):
                    return False, "您的角色被排除在抽獎之外"
            
            return True, "驗證通過"
            
        except Exception as e:
            logger.error(f"驗證參與者條件失敗: {e}")
            return False, f"驗證失敗: {str(e)}"

    async def _check_lottery_permission(self, user: discord.Member, settings: Dict) -> bool:
        """檢查抽獎創建權限"""
        try:
            # 檢查是否為管理員
            if user.guild_permissions.administrator:
                return True
            
            # 檢查抽獎管理角色
            admin_roles = settings.get('admin_roles', [])
            user_role_ids = [role.id for role in user.roles]
            
            return any(role_id in user_role_ids for role_id in admin_roles)
            
        except Exception as e:
            logger.error(f"檢查抽獎權限失敗: {e}")
            return False

    async def _create_lottery_embed(self, lottery: Dict) -> discord.Embed:
        """創建抽獎公告嵌入"""
        embed = EmbedBuilder.build(
            title=f"🎉 {lottery['name']}",
            description=lottery['description'] or "參與抽獎贏得獎品！",
            color='success'
        )
        
        # 獎品資訊
        if lottery['prize_data']:
            prize_info = lottery['prize_data']
            if isinstance(prize_info, dict):
                embed.add_field(
                    name="🎁 獎品",
                    value=prize_info.get('description', '未知獎品'),
                    inline=False
                )
            else:
                embed.add_field(name="🎁 獎品", value=str(prize_info), inline=False)
        
        embed.add_field(name="👥 中獎人數", value=f"{lottery['winner_count']} 人", inline=True)
        embed.add_field(name="⏰ 結束時間", value=f"<t:{int(lottery['end_time'].timestamp())}:R>", inline=True)
        
        # 參與方式
        entry_methods = {
            'reaction': '點擊 🎉 反應',
            'command': '使用指令參與',
            'both': '點擊反應或使用指令'
        }
        embed.add_field(
            name="📝 參與方式",
            value=entry_methods.get(lottery['entry_method'], '未知'),
            inline=True
        )
        
        # 參與條件
        conditions = []
        if lottery['min_account_age_days'] > 0:
            conditions.append(f"帳號年齡: {lottery['min_account_age_days']} 天以上")
        if lottery['min_server_join_days'] > 0:
            conditions.append(f"加入伺服器: {lottery['min_server_join_days']} 天以上")
        
        if conditions:
            embed.add_field(name="📋 參與條件", value="\n".join(conditions), inline=False)
        
        embed.set_footer(text=f"抽獎 ID: {lottery['id']} | 創建者: {lottery.get('creator_name', 'Unknown')}")
        
        return embed

    async def _create_results_embed(self, lottery: Dict, winners: List[Dict], total_participants: int) -> discord.Embed:
        """創建抽獎結果嵌入"""
        embed = EmbedBuilder.build(
            title=f"🏆 {lottery['name']} - 抽獎結果",
            color='success'
        )
        
        if winners:
            winner_list = []
            for winner in winners:
                position_emoji = ["🥇", "🥈", "🥉"][winner['win_position'] - 1] if winner['win_position'] <= 3 else "🏅"
                winner_list.append(f"{position_emoji} <@{winner['user_id']}> ({winner['username']})")
            
            embed.add_field(
                name=f"🎊 中獎者 ({len(winners)} 人)",
                value="\n".join(winner_list),
                inline=False
            )
        
        embed.add_field(name="👥 總參與人數", value=f"{total_participants} 人", inline=True)
        embed.add_field(name="🎲 中獎機率", value=f"{len(winners)/max(total_participants, 1)*100:.1f}%", inline=True)
        
        embed.set_footer(text=f"抽獎 ID: {lottery['id']} | 結束時間")
        embed.timestamp = datetime.now()
        
        return embed

    async def _schedule_lottery_end(self, lottery_id: int, end_time: datetime):
        """安排抽獎自動結束"""
        try:
            delay = (end_time - datetime.now()).total_seconds()
            if delay <= 0:
                return  # 已過期
            
            async def end_task():
                try:
                    await asyncio.sleep(delay)
                    
                    # 獲取頻道
                    lottery = await self.dao.get_lottery(lottery_id)
                    if lottery and self.bot:
                        channel = self.bot.get_channel(lottery['channel_id'])
                        if channel:
                            await self.end_lottery(lottery_id, channel, forced=True)
                            
                except asyncio.CancelledError:
                    pass
                except Exception as e:
                    logger.error(f"自動結束抽獎失敗: {e}")
            
            # 創建並儲存任務
            task = asyncio.create_task(end_task())
            self._running_lotteries[lottery_id] = task
            
        except Exception as e:
            logger.error(f"安排抽獎結束失敗: {e}")

    @tasks.loop(minutes=10)
    async def lottery_scheduler(self):
        """抽獎排程器 - 定期檢查和清理"""
        try:
            # 清理過期抽獎
            await self.dao.cleanup_expired_lotteries()
            
        except Exception as e:
            logger.error(f"抽獎排程器錯誤: {e}")

    @lottery_scheduler.before_loop
    async def before_lottery_scheduler(self):
        await self.bot.wait_until_ready()

    async def get_lottery_statistics(self, guild_id: int, days: int = 30) -> Dict[str, Any]:
        """獲取抽獎統計"""
        return await self.dao.get_lottery_statistics(guild_id, days)