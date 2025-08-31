"""
自動更新服務
內建在 Discord Bot 中，支援從 GitHub 自動拉取更新並重啟
解決託管商禁止外部訪問的問題
"""

import asyncio
import json
import logging
import os
import signal
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

import aiohttp
import discord
from discord.ext import commands, tasks

logger = logging.getLogger(__name__)


class AutoUpdater:
    """自動更新管理器"""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.config = self._load_config()
        self.update_lock = asyncio.Lock()
        self.last_check = None
        self.current_commit = self._get_current_commit()
        self.update_channel_id = self.config.get("update_channel_id")
        self.authorized_users = self.config.get("authorized_users", [])

        # GitHub API 認證
        self.github_token = os.getenv("GITHUB_TOKEN")
        if not self.github_token:
            logger.warning("⚠️ 未配置 GITHUB_TOKEN 環境變數，GitHub API 請求可能受速率限制影響")
        else:
            # 驗證 token 格式
            if self.github_token.startswith(("ghp_", "github_pat_")):
                logger.info(f"✅ 已載入 GITHUB_TOKEN (類型: {self.github_token[:4]}...)")
            else:
                logger.warning(f"⚠️ GITHUB_TOKEN 格式可能不正確 (開頭: {self.github_token[:4]}...)")

            # 記錄 token 長度（用於除錯）
            logger.debug(f"🔍 GITHUB_TOKEN 長度: {len(self.github_token)} 字符")

        # 啟動自動檢查任務
        if self.config.get("auto_check_enabled", True):
            self.check_updates.start()

    def _load_config(self) -> Dict[str, Any]:
        """載入自動更新配置"""
        config_path = Path("auto_update_config.json")
        default_config = {
            "auto_check_enabled": True,
            "check_interval_minutes": 10,
            "auto_update_enabled": False,  # 預設需要手動確認
            "branch": "ptero",
            "github_repo": "Craig-0219/potato",
            "webhook_secret": None,
            "update_channel_id": None,
            "authorized_users": [],
            "maintenance_window": {
                "start_hour": 2,
                "end_hour": 6,
            },  # UTC 2:00  # UTC 6:00
            "backup_before_update": True,
            "rollback_on_failure": True,
        }

        if config_path.exists():
            try:
                with open(config_path, "r") as f:
                    user_config = json.load(f)
                    default_config.update(user_config)
            except Exception as e:
                logger.error(f"載入更新配置失敗: {e}")

        return default_config

    def _save_config(self):
        """保存配置"""
        try:
            with open("auto_update_config.json", "w") as f:
                json.dump(self.config, f, indent=2)
        except Exception as e:
            logger.error(f"保存配置失敗: {e}")

    def _get_current_commit(self) -> Optional[str]:
        """獲取當前 Git 提交雜湊"""
        try:
            result = subprocess.run(
                ["git", "rev-parse", "HEAD"], capture_output=True, text=True, timeout=10
            )
            if result.returncode == 0:
                return result.stdout.strip()
        except Exception as e:
            logger.error(f"獲取當前提交失敗: {e}")
        return None

    async def _get_latest_commit(self) -> Optional[Tuple[str, Dict[str, Any]]]:
        """從 GitHub API 獲取最新提交信息"""
        try:
            url = f"https://api.github.com/repos/{self.config['github_repo']}/commits/{self.config['branch']}"

            # 準備請求標頭
            headers = {
                "Accept": "application/vnd.github.v3+json",
                "User-Agent": "Potato-Bot-Auto-Updater/1.0",
            }

            if self.github_token:
                headers["Authorization"] = f"token {self.github_token}"
                logger.debug("🔑 使用認證的 GitHub API 請求")
            else:
                logger.debug("🔓 使用未認證的 GitHub API 請求")

            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers) as response:
                    if response.status == 200:
                        commit_info = await response.json()
                        return commit_info["sha"], commit_info
                    elif response.status == 401:
                        if self.github_token:
                            logger.error("❌ GitHub API 認證失敗 (401)：GITHUB_TOKEN 無效或已過期")
                            # 嘗試不使用 token 重新請求
                            logger.info("🔄 嘗試使用未認證請求...")
                            headers_no_auth = {
                                k: v for k, v in headers.items() if k != "Authorization"
                            }
                            async with session.get(url, headers=headers_no_auth) as retry_response:
                                if retry_response.status == 200:
                                    commit_info = await retry_response.json()
                                    logger.info("✅ 未認證請求成功")
                                    return commit_info["sha"], commit_info
                                else:
                                    logger.error(f"❌ 未認證請求也失敗: {retry_response.status}")
                        else:
                            logger.error("❌ GitHub API 認證失敗 (401)：可能需要訪問私有倉庫")
                    elif response.status == 403:
                        logger.error(
                            "❌ GitHub API 速率限制 (403)：請配置有效的 GITHUB_TOKEN 以提高限制"
                        )
                    elif response.status == 404:
                        logger.error("❌ GitHub 倉庫或分支不存在 (404)")
                    else:
                        logger.error(f"❌ GitHub API 請求失敗: {response.status}")

                    # 記錄詳細的錯誤資訊
                    error_text = await response.text()
                    logger.debug(f"🔍 API 錯誤詳情: {error_text[:200]}...")
        except Exception as e:
            logger.error(f"❌ 獲取最新提交失敗: {e}")

        return None, None

    async def _validate_github_token(self) -> bool:
        """驗證 GitHub Token 是否有效"""
        if not self.github_token:
            return False

        try:
            # 測試 token 有效性 - 調用用戶資訊 API
            headers = {
                "Accept": "application/vnd.github.v3+json",
                "User-Agent": "Potato-Bot-Auto-Updater/1.0",
                "Authorization": f"token {self.github_token}",
            }

            async with aiohttp.ClientSession() as session:
                async with session.get("https://api.github.com/user", headers=headers) as response:
                    if response.status == 200:
                        user_data = await response.json()
                        logger.info(
                            f"✅ GitHub Token 驗證成功 (用戶: {user_data.get('login', 'unknown')})"
                        )
                        return True
                    elif response.status == 401:
                        logger.error("❌ GitHub Token 無效或已過期")
                        return False
                    elif response.status == 403:
                        logger.warning("⚠️ GitHub Token 權限不足或達到速率限制")
                        return False
                    else:
                        logger.warning(f"⚠️ GitHub Token 驗證異常: {response.status}")
                        return False
        except Exception as e:
            logger.error(f"❌ GitHub Token 驗證失敗: {e}")
            return False

    async def check_for_updates(self) -> Tuple[bool, Optional[Dict[str, Any]]]:
        """檢查是否有可用更新"""
        # 如果有 token，先驗證其有效性
        if self.github_token:
            token_valid = await self._validate_github_token()
            if not token_valid:
                logger.error("🚫 GitHub Token 驗證失敗，將使用未認證請求 (可能有速率限制)")

        latest_commit, commit_info = await self._get_latest_commit()

        if not latest_commit:
            return False, None

        # 比較提交雜湊
        has_update = latest_commit != self.current_commit

        if has_update:
            update_info = {
                "latest_commit": latest_commit,
                "current_commit": self.current_commit,
                "commit_info": commit_info,
                "commit_message": commit_info.get("commit", {}).get("message", ""),
                "commit_date": commit_info.get("commit", {}).get("author", {}).get("date"),
                "author": commit_info.get("commit", {}).get("author", {}).get("name"),
                "files_changed": (
                    len(commit_info.get("files", [])) if "files" in commit_info else "未知"
                ),
            }
            return True, update_info

        return False, None

    def _is_in_maintenance_window(self) -> bool:
        """檢查是否在維護窗口內"""
        now = datetime.utcnow()
        start_hour = self.config["maintenance_window"]["start_hour"]
        end_hour = self.config["maintenance_window"]["end_hour"]

        if start_hour <= end_hour:
            return start_hour <= now.hour < end_hour
        else:  # 跨越午夜的情況
            return now.hour >= start_hour or now.hour < end_hour

    async def _create_backup(self) -> bool:
        """創建代碼備份"""
        try:
            backup_dir = Path("backups")
            backup_dir.mkdir(exist_ok=True)

            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_name = f"backup_{self.current_commit[:7]}_{timestamp}"

            # 創建 Git stash 備份
            result = subprocess.run(
                ["git", "stash", "push", "-m", backup_name],
                capture_output=True,
                text=True,
                timeout=30,
            )

            if result.returncode == 0:
                logger.info(f"備份創建成功: {backup_name}")
                return True
            else:
                logger.error(f"備份創建失敗: {result.stderr}")
                return False

        except Exception as e:
            logger.error(f"創建備份時發生錯誤: {e}")
            return False

    async def _pull_updates(self) -> Tuple[bool, str]:
        """從 Git 拉取更新"""
        try:
            # 先 fetch
            result = subprocess.run(
                ["git", "fetch", "origin", self.config["branch"]],
                capture_output=True,
                text=True,
                timeout=60,
            )

            if result.returncode != 0:
                return False, f"Git fetch 失敗: {result.stderr}"

            # 然後 pull
            result = subprocess.run(
                ["git", "pull", "origin", self.config["branch"]],
                capture_output=True,
                text=True,
                timeout=60,
            )

            if result.returncode == 0:
                return True, "更新拉取成功"
            else:
                return False, f"Git pull 失敗: {result.stderr}"

        except subprocess.TimeoutExpired:
            return False, "Git 操作超時"
        except Exception as e:
            return False, f"拉取更新時發生錯誤: {e}"

    async def _update_dependencies(self) -> Tuple[bool, str]:
        """更新依賴包"""
        try:
            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "pip",
                    "install",
                    "-r",
                    "requirements.txt",
                    "--upgrade",
                ],
                capture_output=True,
                text=True,
                timeout=300,  # 5分鐘超時
            )

            if result.returncode == 0:
                return True, "依賴更新成功"
            else:
                return False, f"依賴更新失敗: {result.stderr}"

        except subprocess.TimeoutExpired:
            return False, "依賴更新超時"
        except Exception as e:
            return False, f"更新依賴時發生錯誤: {e}"

    async def _send_update_notification(self, message: str, embed: Optional[discord.Embed] = None):
        """發送更新通知"""
        if not self.update_channel_id:
            return

        try:
            channel = self.bot.get_channel(self.update_channel_id)
            if channel:
                if embed:
                    await channel.send(message, embed=embed)
                else:
                    await channel.send(message)
        except Exception as e:
            logger.error(f"發送更新通知失敗: {e}")

    async def perform_update(self, user_id: Optional[int] = None) -> Dict[str, Any]:
        """執行更新流程"""
        async with self.update_lock:
            update_result = {
                "success": False,
                "steps": {},
                "error": None,
                "started_by": user_id,
                "timestamp": datetime.utcnow().isoformat(),
            }

            try:
                # 步驟 1: 檢查更新
                await self._send_update_notification("🔍 檢查可用更新...")
                has_update, update_info = await self.check_for_updates()
                update_result["steps"]["check_update"] = has_update

                if not has_update:
                    update_result["error"] = "沒有可用更新"
                    return update_result

                # 步驟 2: 創建備份
                if self.config.get("backup_before_update", True):
                    await self._send_update_notification("💾 創建備份...")
                    backup_success = await self._create_backup()
                    update_result["steps"]["backup"] = backup_success

                    if not backup_success:
                        update_result["error"] = "備份創建失敗"
                        return update_result

                # 步驟 3: 拉取更新
                await self._send_update_notification("📥 拉取更新...")
                pull_success, pull_message = await self._pull_updates()
                update_result["steps"]["pull_updates"] = pull_success
                update_result["pull_message"] = pull_message

                if not pull_success:
                    update_result["error"] = pull_message
                    return update_result

                # 步驟 4: 更新依賴
                await self._send_update_notification("📦 更新依賴包...")
                deps_success, deps_message = await self._update_dependencies()
                update_result["steps"]["update_dependencies"] = deps_success
                update_result["deps_message"] = deps_message

                if not deps_success:
                    logger.warning(f"依賴更新失敗: {deps_message}")
                    # 依賴更新失敗不一定致命，繼續執行

                # 步驟 5: 準備重啟
                await self._send_update_notification("🔄 準備重啟 Bot...")

                # 更新當前提交記錄
                self.current_commit = update_info["latest_commit"]

                update_result["success"] = True
                update_result["update_info"] = update_info

                # 創建重啟通知
                embed = discord.Embed(
                    title="✅ 更新完成 - 準備重啟",
                    color=0x00FF00,
                    timestamp=datetime.utcnow(),
                )
                embed.add_field(
                    name="🔄 新版本信息",
                    value=f"**提交:** {update_info['latest_commit'][:8]}\n"
                    f"**作者:** {update_info['author']}\n"
                    f"**時間:** {update_info['commit_date']}",
                    inline=False,
                )
                embed.add_field(
                    name="📝 更新內容",
                    value=update_info["commit_message"][:500]
                    + ("..." if len(update_info["commit_message"]) > 500 else ""),
                    inline=False,
                )

                await self._send_update_notification("🚀 Bot 將在 5 秒後重啟...", embed)

                # 延遲重啟
                await asyncio.sleep(5)

                return update_result

            except Exception as e:
                update_result["error"] = str(e)
                logger.error(f"更新流程發生錯誤: {e}")
                await self._send_update_notification(f"❌ 更新失敗: {e}")
                return update_result

    def restart_bot(self):
        """重啟 Bot"""
        logger.info("正在重啟 Discord Bot...")

        # 發送 SIGTERM 信號給當前進程
        if hasattr(signal, "SIGTERM"):
            os.kill(os.getpid(), signal.SIGTERM)
        else:
            # Windows 系統
            sys.exit(0)

    @tasks.loop(minutes=10)
    async def check_updates(self):
        """定期檢查更新任務"""
        try:
            if not self.config.get("auto_check_enabled", True):
                return

            # 更新檢查間隔
            interval = self.config.get("check_interval_minutes", 10)
            self.check_updates.change_interval(minutes=interval)

            has_update, update_info = await self.check_for_updates()

            if has_update:
                logger.info(f"發現新更新: {update_info['latest_commit'][:8]}")

                # 發送更新通知
                embed = discord.Embed(
                    title="🔔 發現新更新", color=0xFFA500, timestamp=datetime.utcnow()
                )
                embed.add_field(
                    name="📝 更新內容",
                    value=update_info["commit_message"][:500]
                    + ("..." if len(update_info["commit_message"]) > 500 else ""),
                    inline=False,
                )
                embed.add_field(
                    name="🔧 操作選項",
                    value="• 使用 `!update now` 立即更新\n"
                    "• 使用 `!update info` 查看詳細信息\n"
                    "• 使用 `!update config` 修改設定",
                    inline=False,
                )

                await self._send_update_notification("🔔 發現可用更新!", embed)

                # 如果啟用自動更新且在維護窗口內
                if (
                    self.config.get("auto_update_enabled", False)
                    and self._is_in_maintenance_window()
                ):

                    logger.info("在維護窗口內，執行自動更新")
                    result = await self.perform_update()

                    if result["success"]:
                        # 自動重啟
                        self.restart_bot()
                    else:
                        await self._send_update_notification(f"❌ 自動更新失敗: {result['error']}")

            self.last_check = datetime.utcnow()

        except Exception as e:
            logger.error(f"檢查更新時發生錯誤: {e}")

    @check_updates.before_loop
    async def before_check_updates(self):
        """等待 Bot 準備就緒"""
        await self.bot.wait_until_ready()
        logger.info("自動更新服務已啟動")


# Discord Commands Cog
class AutoUpdateCog(commands.Cog, name="自動更新"):
    """自動更新命令組"""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.updater = AutoUpdater(bot)

    def _is_authorized(self, user_id: int) -> bool:
        """檢查用戶是否有更新權限"""
        if not self.updater.authorized_users:
            return True  # 如果沒有設定授權用戶，允許所有人
        return user_id in self.updater.authorized_users

    @commands.group(name="update", aliases=["更新"])
    async def update_group(self, ctx):
        """自動更新命令組"""
        if ctx.invoked_subcommand is None:
            embed = discord.Embed(
                title="🔄 自動更新系統",
                description="管理 Discord Bot 的自動更新功能",
                color=0x0099FF,
            )
            embed.add_field(
                name="📋 可用命令",
                value="`!update check` - 檢查更新\n"
                "`!update now` - 立即更新\n"
                "`!update info` - 查看更新信息\n"
                "`!update config` - 更新配置\n"
                "`!update status` - 查看狀態",
                inline=False,
            )
            await ctx.send(embed=embed)

    @update_group.command(name="check", aliases=["檢查"])
    async def check_update(self, ctx):
        """檢查是否有可用更新"""
        async with ctx.typing():
            has_update, update_info = await self.updater.check_for_updates()

            if has_update:
                embed = discord.Embed(
                    title="✅ 發現新更新", color=0x00FF00, timestamp=datetime.utcnow()
                )
                embed.add_field(
                    name="🔧 版本信息",
                    value=f"**當前:** {self.updater.current_commit[:8] if self.updater.current_commit else '未知'}\n"
                    f"**最新:** {update_info['latest_commit'][:8]}\n"
                    f"**作者:** {update_info['author']}",
                    inline=True,
                )
                embed.add_field(
                    name="📝 更新內容",
                    value=update_info["commit_message"][:500]
                    + ("..." if len(update_info["commit_message"]) > 500 else ""),
                    inline=False,
                )
                embed.add_field(name="⏰ 提交時間", value=update_info["commit_date"], inline=True)
            else:
                embed = discord.Embed(
                    title="✅ 已是最新版本",
                    description="當前 Bot 已經是最新版本，無需更新。",
                    color=0x00FF00,
                )

            await ctx.send(embed=embed)

    @update_group.command(name="now", aliases=["立即", "execute"])
    async def update_now(self, ctx):
        """立即執行更新"""
        if not self._is_authorized(ctx.author.id):
            await ctx.send("❌ 您沒有執行更新的權限。")
            return

        # 確認更新
        embed = discord.Embed(
            title="⚠️ 確認更新",
            description="執行更新將會重啟 Bot，所有進行中的操作將被中斷。\n\n確定要繼續嗎？",
            color=0xFF9900,
        )

        msg = await ctx.send(embed=embed)
        await msg.add_reaction("✅")
        await msg.add_reaction("❌")

        def check(reaction, user):
            return (
                user == ctx.author
                and str(reaction.emoji) in ["✅", "❌"]
                and reaction.message.id == msg.id
            )

        try:
            reaction, user = await self.bot.wait_for("reaction_add", timeout=30.0, check=check)

            if str(reaction.emoji) == "✅":
                await ctx.send("🔄 開始執行更新...")
                result = await self.updater.perform_update(ctx.author.id)

                if result["success"]:
                    await ctx.send("✅ 更新完成！Bot 即將重啟...")
                    # 重啟 Bot
                    await asyncio.sleep(2)
                    self.updater.restart_bot()
                else:
                    await ctx.send(f"❌ 更新失敗: {result['error']}")
            else:
                await ctx.send("❌ 已取消更新。")

        except asyncio.TimeoutError:
            await ctx.send("⏰ 確認超時，已取消更新。")

    @update_group.command(name="status", aliases=["狀態"])
    async def update_status(self, ctx):
        """查看自動更新狀態"""
        embed = discord.Embed(title="📊 自動更新狀態", color=0x0099FF, timestamp=datetime.utcnow())

        embed.add_field(
            name="⚙️ 配置狀態",
            value=f"**自動檢查:** {'✅ 啟用' if self.updater.config.get('auto_check_enabled') else '❌ 停用'}\n"
            f"**自動更新:** {'✅ 啟用' if self.updater.config.get('auto_update_enabled') else '❌ 停用'}\n"
            f"**檢查間隔:** {self.updater.config.get('check_interval_minutes', 10)} 分鐘\n"
            f"**分支:** {self.updater.config.get('branch', 'ptero')}",
            inline=True,
        )

        embed.add_field(
            name="📋 運行狀態",
            value=f"**當前提交:** {self.updater.current_commit[:8] if self.updater.current_commit else '未知'}\n"
            f"**上次檢查:** {self.updater.last_check.strftime('%Y-%m-%d %H:%M:%S UTC') if self.updater.last_check else '未檢查'}\n"
            f"**檢查任務:** {'✅ 運行中' if self.updater.check_updates.is_running() else '❌ 已停止'}",
            inline=True,
        )

        # 維護窗口
        maint = self.updater.config.get("maintenance_window", {})
        embed.add_field(
            name="🕐 維護窗口",
            value=f"**時間:** {maint.get('start_hour', 2):02d}:00 - {maint.get('end_hour', 6):02d}:00 UTC\n"
            f"**當前狀態:** {'🟢 在維護窗口內' if self.updater._is_in_maintenance_window() else '🔴 不在維護窗口內'}",
            inline=False,
        )

        await ctx.send(embed=embed)

    @update_group.command(name="config", aliases=["配置", "設定"])
    async def update_config(self, ctx, setting: str = None, value: str = None):
        """修改更新配置"""
        if not self._is_authorized(ctx.author.id):
            await ctx.send("❌ 您沒有修改配置的權限。")
            return

        if not setting:
            # 顯示當前配置
            embed = discord.Embed(title="⚙️ 自動更新配置", color=0x0099FF)

            config_display = {
                "auto_check_enabled": "自動檢查",
                "auto_update_enabled": "自動更新",
                "check_interval_minutes": "檢查間隔(分鐘)",
                "branch": "更新分支",
            }

            config_text = ""
            for key, display_name in config_display.items():
                config_text += f"**{display_name}:** `{self.updater.config.get(key)}`\n"

            embed.add_field(name="📋 當前配置", value=config_text, inline=False)
            embed.add_field(
                name="💡 使用方法",
                value="`!update config <設定> <值>`\n例如: `!update config auto_update_enabled true`",
                inline=False,
            )

            await ctx.send(embed=embed)
            return

        # 修改配置
        if value is None:
            await ctx.send("❌ 請提供設定值。")
            return

        # 轉換值類型
        if value.lower() in ["true", "1", "yes", "on"]:
            value = True
        elif value.lower() in ["false", "0", "no", "off"]:
            value = False
        elif value.isdigit():
            value = int(value)

        # 更新配置
        old_value = self.updater.config.get(setting)
        self.updater.config[setting] = value
        self.updater._save_config()

        # 如果修改了檢查間隔，重啟任務
        if setting == "check_interval_minutes":
            self.updater.check_updates.restart()

        await ctx.send(f"✅ 配置已更新: `{setting}` = `{old_value}` → `{value}`")


async def setup(bot):
    """設置 Cog"""
    await bot.add_cog(AutoUpdateCog(bot))
