# bot/cogs/auto_updater.py
"""
自動更新器 Cog - Discord Bot 內部自動更新系統
用於繞過託管商外部訪問限制，實現內部自動更新機制
"""
import asyncio
import os
import subprocess
import tempfile
import zipfile
from datetime import datetime, timedelta
from typing import Dict, Optional

import aiohttp
import discord
from discord.ext import commands, tasks

try:
    from shared.logger import logger
except ImportError:
    import logging
    logger = logging.getLogger(__name__)


class AutoUpdateManager:
    """自動更新管理器 - 內部實現"""
    
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.github_api_base = "https://api.github.com"
        self.repo_owner = os.getenv("GITHUB_REPO_OWNER", "your-username")
        self.repo_name = os.getenv("GITHUB_REPO_NAME", "potato")
        self.github_token = os.getenv("GITHUB_TOKEN")
        
        # 更新配置
        self.auto_update_enabled = os.getenv("AUTO_UPDATE_ENABLED", "true").lower() == "true"
        self.update_channel_id = int(os.getenv("UPDATE_CHANNEL_ID", "0")) if os.getenv("UPDATE_CHANNEL_ID") else None
        self.maintenance_window_start = int(os.getenv("MAINTENANCE_WINDOW_START", "2"))  # 2 AM
        self.maintenance_window_end = int(os.getenv("MAINTENANCE_WINDOW_END", "6"))     # 6 AM
        
        # 狀態追蹤
        self.last_check = None
        self.last_update = None
        self.update_in_progress = False
        self.current_version = None
        self.available_version = None
        
        # 安全設置
        self.max_retries = 3
        self.backup_enabled = True
        
    async def initialize(self):
        """初始化更新器"""
        logger.info("🔄 初始化自動更新器...")
        
        try:
            # 獲取當前版本
            self.current_version = await self._get_current_version()
            logger.info(f"📋 當前版本: {self.current_version}")
            
            # 檢查配置
            if not self.github_token:
                logger.warning("⚠️ 未配置 GITHUB_TOKEN，將使用公共 API（有速率限制）")
            
            if not self.update_channel_id:
                logger.warning("⚠️ 未配置 UPDATE_CHANNEL_ID，更新通知將記錄到日誌")
            
            logger.info("✅ 自動更新器初始化完成")
            
        except Exception as e:
            logger.error(f"❌ 自動更新器初始化失敗: {e}")
            raise
    
    async def _get_current_version(self) -> str:
        """獲取當前版本"""
        try:
            # 嘗試從 git 獲取版本
            result = subprocess.run(
                ["git", "describe", "--tags", "--abbrev=0"],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if result.returncode == 0:
                return result.stdout.strip()
            
            # 備選：從 git log 獲取簡短 hash
            result = subprocess.run(
                ["git", "rev-parse", "--short", "HEAD"],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if result.returncode == 0:
                return f"commit-{result.stdout.strip()}"
            
            # 最後備選：使用時間戳
            return f"unknown-{datetime.now().strftime('%Y%m%d')}"
            
        except Exception as e:
            logger.error(f"獲取版本失敗: {e}")
            return "unknown"
    
    async def check_for_updates(self) -> Dict:
        """檢查更新"""
        self.last_check = datetime.now()
        
        try:
            headers = {}
            if self.github_token:
                headers["Authorization"] = f"token {self.github_token}"
            
            async with aiohttp.ClientSession() as session:
                # 獲取最新 release
                url = f"{self.github_api_base}/repos/{self.repo_owner}/{self.repo_name}/releases/latest"
                async with session.get(url, headers=headers) as response:
                    if response.status == 200:
                        release_data = await response.json()
                        latest_version = release_data["tag_name"]
                        
                        result = {
                            "has_update": latest_version != self.current_version,
                            "current_version": self.current_version,
                            "latest_version": latest_version,
                            "release_notes": release_data.get("body", ""),
                            "published_at": release_data.get("published_at", ""),
                            "download_url": release_data.get("zipball_url", "")
                        }
                        
                        if result["has_update"]:
                            self.available_version = latest_version
                            logger.info(f"🎉 發現新版本: {latest_version}")
                        else:
                            logger.info("✅ 已是最新版本")
                        
                        return result
                    else:
                        logger.error(f"GitHub API 請求失敗: {response.status}")
                        return {"error": f"API請求失敗: {response.status}"}
        
        except Exception as e:
            logger.error(f"檢查更新失敗: {e}")
            return {"error": str(e)}
    
    async def perform_update(self, force: bool = False) -> Dict:
        """執行更新"""
        if self.update_in_progress:
            return {"error": "更新已在進行中"}
        
        # 檢查維護窗口
        if not force and not self._is_maintenance_window():
            next_window = self._get_next_maintenance_window()
            return {
                "error": f"非維護窗口時間，下次維護窗口: {next_window}"
            }
        
        self.update_in_progress = True
        
        try:
            logger.info("🔄 開始執行更新...")
            await self._notify_update_start()
            
            # 1. 創建備份
            if self.backup_enabled:
                backup_result = await self._create_backup()
                if not backup_result.get("success"):
                    raise Exception(f"備份失敗: {backup_result.get('error')}")
                logger.info(f"✅ 備份創建成功: {backup_result.get('backup_path')}")
            
            # 2. 執行 git pull
            update_result = await self._execute_git_update()
            if not update_result.get("success"):
                raise Exception(f"Git 更新失敗: {update_result.get('error')}")
            
            # 3. 重啟準備
            self.last_update = datetime.now()
            logger.info("✅ 更新完成，準備重啟...")
            
            await self._notify_update_success()
            
            # 4. 延遲重啟以確保通知發送
            await asyncio.sleep(3)
            await self._restart_bot()
            
            return {
                "success": True,
                "message": "更新完成，Bot 即將重啟"
            }
        
        except Exception as e:
            logger.error(f"❌ 更新失敗: {e}")
            await self._notify_update_error(str(e))
            return {"error": str(e)}
        
        finally:
            self.update_in_progress = False
    
    async def _create_backup(self) -> Dict:
        """創建備份"""
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_dir = "/tmp/bot_backups"
            os.makedirs(backup_dir, exist_ok=True)
            
            backup_path = f"{backup_dir}/backup_{timestamp}.tar.gz"
            
            # 排除不必要的文件
            exclude_patterns = [
                "--exclude=__pycache__",
                "--exclude=*.pyc", 
                "--exclude=.git",
                "--exclude=logs/*",
                "--exclude=temp/*"
            ]
            
            cmd = [
                "tar", "czf", backup_path,
                *exclude_patterns,
                "."
            ]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=300  # 5分鐘超時
            )
            
            if result.returncode == 0:
                return {
                    "success": True,
                    "backup_path": backup_path
                }
            else:
                return {
                    "success": False,
                    "error": result.stderr
                }
        
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
    
    async def _execute_git_update(self) -> Dict:
        """執行 Git 更新"""
        try:
            # 1. Stash 任何本地更改
            stash_result = subprocess.run(
                ["git", "stash"],
                capture_output=True,
                text=True,
                timeout=60
            )
            
            # 2. Pull 最新更改
            pull_result = subprocess.run(
                ["git", "pull", "origin", "main"],
                capture_output=True,
                text=True,
                timeout=300
            )
            
            if pull_result.returncode == 0:
                return {
                    "success": True,
                    "output": pull_result.stdout
                }
            else:
                return {
                    "success": False,
                    "error": pull_result.stderr
                }
        
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
    
    async def _restart_bot(self):
        """重啟 Bot"""
        logger.info("🔄 重啟 Bot...")
        
        # 優雅關閉
        await self.bot.close()
        
        # 如果在 systemd 或其他進程管理器下運行，
        # 退出後應該會被自動重啟
        os._exit(0)
    
    def _is_maintenance_window(self) -> bool:
        """檢查是否在維護窗口時間"""
        now = datetime.now()
        current_hour = now.hour
        
        if self.maintenance_window_start <= self.maintenance_window_end:
            # 同一天的維護窗口
            return self.maintenance_window_start <= current_hour < self.maintenance_window_end
        else:
            # 跨天的維護窗口
            return current_hour >= self.maintenance_window_start or current_hour < self.maintenance_window_end
    
    def _get_next_maintenance_window(self) -> str:
        """獲取下次維護窗口時間"""
        now = datetime.now()
        next_window = now.replace(
            hour=self.maintenance_window_start,
            minute=0,
            second=0,
            microsecond=0
        )
        
        if next_window <= now:
            next_window += timedelta(days=1)
        
        return next_window.strftime("%Y-%m-%d %H:%M")
    
    async def _notify_update_start(self):
        """通知更新開始"""
        message = "🔄 **自動更新開始**\n\n"
        message += f"• 當前版本: `{self.current_version}`\n"
        message += f"• 目標版本: `{self.available_version}`\n"
        message += f"• 更新時間: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
        message += "⏳ 更新過程中 Bot 可能會短暫離線..."
        
        await self._send_notification(message)
    
    async def _notify_update_success(self):
        """通知更新成功"""
        message = "✅ **自動更新完成**\n\n"
        message += f"• 已更新到版本: `{self.available_version}`\n"
        message += f"• 更新時間: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
        message += "🔄 Bot 即將重啟以應用更新..."
        
        await self._send_notification(message)
    
    async def _notify_update_error(self, error: str):
        """通知更新錯誤"""
        message = "❌ **自動更新失敗**\n\n"
        message += f"• 錯誤: `{error}`\n"
        message += f"• 時間: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
        message += "🛠️ 請檢查日誌並手動處理更新問題"
        
        await self._send_notification(message)
    
    async def _send_notification(self, message: str):
        """發送通知"""
        try:
            if self.update_channel_id:
                channel = self.bot.get_channel(self.update_channel_id)
                if channel:
                    embed = discord.Embed(
                        description=message,
                        color=discord.Color.blue(),
                        timestamp=datetime.now()
                    )
                    embed.set_footer(text="Potato Bot 自動更新系統")
                    await channel.send(embed=embed)
                    return
            
            # 備選：記錄到日誌
            logger.info(f"更新通知: {message}")
            
        except Exception as e:
            logger.error(f"發送更新通知失敗: {e}")
    
    def get_status(self) -> Dict:
        """獲取更新器狀態"""
        return {
            "auto_update_enabled": self.auto_update_enabled,
            "current_version": self.current_version,
            "available_version": self.available_version,
            "last_check": self.last_check.isoformat() if self.last_check else None,
            "last_update": self.last_update.isoformat() if self.last_update else None,
            "update_in_progress": self.update_in_progress,
            "maintenance_window": f"{self.maintenance_window_start:02d}:00 - {self.maintenance_window_end:02d}:00",
            "is_maintenance_window": self._is_maintenance_window(),
            "next_maintenance_window": self._get_next_maintenance_window()
        }


class AutoUpdateCog(commands.Cog):
    """自動更新器 Cog"""
    
    def __init__(self, bot):
        self.bot = bot
        self.update_manager = AutoUpdateManager(bot)
        self.auto_check_updates.start()
    
    async def cog_load(self):
        """Cog 載入時的初始化"""
        await self.update_manager.initialize()
        logger.info("✅ AutoUpdateCog 載入完成")
    
    def cog_unload(self):
        """Cog 卸載時的清理"""
        self.auto_check_updates.cancel()
        logger.info("🔄 AutoUpdateCog 已卸載")
    
    @tasks.loop(hours=6)  # 每6小時檢查一次
    async def auto_check_updates(self):
        """自動檢查更新任務"""
        if not self.update_manager.auto_update_enabled:
            return
        
        try:
            result = await self.update_manager.check_for_updates()
            
            if result.get("has_update") and self.update_manager._is_maintenance_window():
                logger.info("🎉 發現新版本且處於維護窗口，開始自動更新...")
                await self.update_manager.perform_update()
            
        except Exception as e:
            logger.error(f"自動檢查更新失敗: {e}")
    
    @auto_check_updates.before_loop
    async def before_auto_check(self):
        """等待 Bot 準備完成"""
        await self.bot.wait_until_ready()
        # 延遲啟動以避免啟動時的負載
        await asyncio.sleep(60)
    
    @commands.hybrid_command(name="update")
    @commands.is_owner()
    async def update_command(self, ctx):
        """更新管理主命令"""
        embed = discord.Embed(
            title="🔄 自動更新系統",
            description="可用的更新命令：\n\n"
                       "`/update check` - 檢查更新\n"
                       "`/update now` - 立即更新\n"
                       "`/update status` - 查看狀態\n"
                       "`/update toggle` - 切換自動更新",
            color=discord.Color.blue()
        )
        await ctx.send(embed=embed, ephemeral=True)
    
    @commands.hybrid_command(name="update_check")
    @commands.is_owner()
    async def check_updates(self, ctx):
        """檢查更新"""
        await ctx.defer(ephemeral=True)
        
        try:
            result = await self.update_manager.check_for_updates()
            
            if result.get("error"):
                embed = discord.Embed(
                    title="❌ 檢查更新失敗",
                    description=f"錯誤: {result['error']}",
                    color=discord.Color.red()
                )
            elif result.get("has_update"):
                embed = discord.Embed(
                    title="🎉 發現新版本!",
                    color=discord.Color.green()
                )
                embed.add_field(name="當前版本", value=result["current_version"], inline=True)
                embed.add_field(name="最新版本", value=result["latest_version"], inline=True)
                embed.add_field(name="發布時間", value=result["published_at"][:10], inline=True)
                
                if result["release_notes"]:
                    notes = result["release_notes"][:500] + "..." if len(result["release_notes"]) > 500 else result["release_notes"]
                    embed.add_field(name="更新說明", value=f"```\n{notes}\n```", inline=False)
            else:
                embed = discord.Embed(
                    title="✅ 已是最新版本",
                    description=f"當前版本: `{result['current_version']}`",
                    color=discord.Color.green()
                )
                embed.add_field(name="最後檢查", value=datetime.now().strftime("%Y-%m-%d %H:%M:%S"), inline=True)
            
            await ctx.followup.send(embed=embed)
            
        except Exception as e:
            embed = discord.Embed(
                title="❌ 檢查更新失敗",
                description=f"發生錯誤: {str(e)}",
                color=discord.Color.red()
            )
            await ctx.followup.send(embed=embed)
    
    @commands.hybrid_command(name="update_now") 
    @commands.is_owner()
    async def update_now(self, ctx, force: bool = False):
        """立即執行更新"""
        await ctx.defer(ephemeral=True)
        
        try:
            result = await self.update_manager.perform_update(force=force)
            
            if result.get("error"):
                embed = discord.Embed(
                    title="❌ 更新失敗",
                    description=result["error"],
                    color=discord.Color.red()
                )
            else:
                embed = discord.Embed(
                    title="✅ 更新啟動",
                    description=result["message"],
                    color=discord.Color.green()
                )
            
            await ctx.followup.send(embed=embed)
            
        except Exception as e:
            embed = discord.Embed(
                title="❌ 更新失敗",
                description=f"發生錯誤: {str(e)}",
                color=discord.Color.red()
            )
            await ctx.followup.send(embed=embed)
    
    @commands.hybrid_command(name="update_status")
    @commands.is_owner()
    async def update_status(self, ctx):
        """查看更新器狀態"""
        status = self.update_manager.get_status()
        
        embed = discord.Embed(
            title="📊 自動更新器狀態",
            color=discord.Color.blue()
        )
        
        # 基本狀態
        embed.add_field(
            name="系統狀態",
            value=f"自動更新: {'✅ 啟用' if status['auto_update_enabled'] else '❌ 停用'}\n"
                  f"當前版本: `{status['current_version']}`\n"
                  f"可用版本: `{status['available_version'] or 'N/A'}`",
            inline=False
        )
        
        # 時間資訊
        time_info = f"最後檢查: {status['last_check'] or 'N/A'}\n"
        time_info += f"最後更新: {status['last_update'] or 'N/A'}\n"
        time_info += f"更新進行中: {'是' if status['update_in_progress'] else '否'}"
        
        embed.add_field(name="時間資訊", value=time_info, inline=True)
        
        # 維護窗口
        maintenance_info = f"維護窗口: {status['maintenance_window']}\n"
        maintenance_info += f"目前狀態: {'🟢 維護時間' if status['is_maintenance_window'] else '🔴 非維護時間'}\n"
        maintenance_info += f"下次窗口: {status['next_maintenance_window']}"
        
        embed.add_field(name="維護窗口", value=maintenance_info, inline=True)
        
        embed.set_footer(text=f"查詢時間: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        await ctx.send(embed=embed, ephemeral=True)
    
    @commands.hybrid_command(name="update_toggle")
    @commands.is_owner()
    async def toggle_auto_update(self, ctx):
        """切換自動更新開關"""
        self.update_manager.auto_update_enabled = not self.update_manager.auto_update_enabled
        
        status = "啟用" if self.update_manager.auto_update_enabled else "停用"
        embed = discord.Embed(
            title="🔄 自動更新設定",
            description=f"自動更新已{status}",
            color=discord.Color.green() if self.update_manager.auto_update_enabled else discord.Color.orange()
        )
        
        await ctx.send(embed=embed, ephemeral=True)


async def setup(bot):
    """Cog 設置函數"""
    await bot.add_cog(AutoUpdateCog(bot))