# bot/services/github_update_checker.py
# 🔄 GitHub 自動更新檢查服務
# GitHub Auto Update Checker Service

import json
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import aiohttp
from packaging import version

logger = logging.getLogger(__name__)


class GitHubUpdateChecker:
    """GitHub 自動更新檢查器"""

    def __init__(self, owner: str, repo: str, token: Optional[str] = None):
        self.owner = owner
        self.repo = repo
        self.token = token
        self.base_url = "https://api.github.com"
        self.headers = {
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": "Potato-Bot-Auto-Updater/1.0",
        }

        if self.token:
            self.headers["Authorization"] = f"token {token}"

    async def get_latest_release(self) -> Optional[Dict[str, Any]]:
        """獲取最新發布版本"""
        try:
            url = f"{self.base_url}/repos/{self.owner}/{self.repo}/releases/latest"

            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=self.headers) as response:
                    if response.status == 200:
                        data = await response.json()
                        return {
                            "tag_name": data.get("tag_name"),
                            "name": data.get("name"),
                            "body": data.get("body"),
                            "published_at": data.get("published_at"),
                            "html_url": data.get("html_url"),
                            "download_url": data.get("tarball_url"),
                            "prerelease": data.get("prerelease", False),
                            "draft": data.get("draft", False),
                        }
                    else:
                        logger.error(f"❌ GitHub API 錯誤: {response.status}")
                        return None

        except Exception as e:
            logger.error(f"❌ 獲取最新版本失敗: {e}")
            return None

    async def get_all_releases(self, per_page: int = 10) -> List[Dict[str, Any]]:
        """獲取所有發布版本"""
        try:
            url = f"{self.base_url}/repos/{self.owner}/{self.repo}/releases"
            params = {"per_page": per_page}

            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=self.headers, params=params) as response:
                    if response.status == 200:
                        data = await response.json()
                        return [
                            {
                                "tag_name": release.get("tag_name"),
                                "name": release.get("name"),
                                "published_at": release.get("published_at"),
                                "prerelease": release.get("prerelease", False),
                            }
                            for release in data
                        ]
                    else:
                        logger.error(f"❌ GitHub API 錯誤: {response.status}")
                        return []

        except Exception as e:
            logger.error(f"❌ 獲取版本列表失敗: {e}")
            return []

    async def get_latest_commits(
        self, branch: str = "main", per_page: int = 10
    ) -> List[Dict[str, Any]]:
        """獲取最新提交"""
        try:
            url = f"{self.base_url}/repos/{self.owner}/{self.repo}/commits"
            params = {"sha": branch, "per_page": per_page}

            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=self.headers, params=params) as response:
                    if response.status == 200:
                        data = await response.json()
                        return [
                            {
                                "sha": commit["sha"][:8],
                                "message": commit["commit"]["message"],
                                "author": commit["commit"]["author"]["name"],
                                "date": commit["commit"]["author"]["date"],
                                "url": commit["html_url"],
                            }
                            for commit in data
                        ]
                    else:
                        logger.error(f"❌ GitHub API 錯誤: {response.status}")
                        return []

        except Exception as e:
            logger.error(f"❌ 獲取提交記錄失敗: {e}")
            return []

    async def compare_versions(self, current_version: str, target_version: str) -> Dict[str, Any]:
        """比較版本差異"""
        try:
            # 使用 packaging 庫比較版本
            current_ver = version.parse(current_version.lstrip("v"))
            target_ver = version.parse(target_version.lstrip("v"))

            comparison = {
                "current": current_version,
                "target": target_version,
                "needs_update": target_ver > current_ver,
                "is_major_update": target_ver.major > current_ver.major,
                "is_minor_update": target_ver.minor > current_ver.minor,
                "is_patch_update": target_ver.micro > current_ver.micro,
            }

            # 獲取版本間的差異
            if comparison["needs_update"]:
                commits_diff = await self.get_commits_between_tags(current_version, target_version)
                comparison["commits_count"] = len(commits_diff)
                comparison["commits"] = commits_diff[:5]  # 限制顯示 5 個提交

            return comparison

        except Exception as e:
            logger.error(f"❌ 版本比較失敗: {e}")
            return {"error": str(e)}

    async def get_commits_between_tags(self, base: str, head: str) -> List[Dict[str, Any]]:
        """獲取兩個標籤之間的提交"""
        try:
            url = f"{self.base_url}/repos/{self.owner}/{self.repo}/compare/{base}...{head}"

            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=self.headers) as response:
                    if response.status == 200:
                        data = await response.json()
                        commits = data.get("commits", [])
                        return [
                            {
                                "sha": commit["sha"][:8],
                                "message": commit["commit"]["message"].split("\n")[0][:80],
                                "author": commit["commit"]["author"]["name"],
                                "date": commit["commit"]["author"]["date"],
                            }
                            for commit in commits
                        ]
                    else:
                        logger.error(f"❌ GitHub API 錯誤: {response.status}")
                        return []

        except Exception as e:
            logger.error(f"❌ 獲取提交差異失敗: {e}")
            return []

    async def check_rate_limit(self) -> Dict[str, Any]:
        """檢查 API 使用限制"""
        try:
            url = f"{self.base_url}/rate_limit"

            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=self.headers) as response:
                    if response.status == 200:
                        data = await response.json()
                        core_limit = data.get("resources", {}).get("core", {})
                        return {
                            "limit": core_limit.get("limit", 0),
                            "remaining": core_limit.get("remaining", 0),
                            "reset_at": datetime.fromtimestamp(core_limit.get("reset", 0)),
                            "used": core_limit.get("limit", 0) - core_limit.get("remaining", 0),
                        }
                    else:
                        logger.error(f"❌ GitHub API 錯誤: {response.status}")
                        return {}

        except Exception as e:
            logger.error(f"❌ 檢查速率限制失敗: {e}")
            return {}

    async def download_update(self, release_info: Dict[str, Any], download_path: str) -> bool:
        """下載更新檔案"""
        try:
            download_url = release_info.get("download_url")
            if not download_url:
                logger.error("❌ 缺少下載連結")
                return False

            async with aiohttp.ClientSession() as session:
                async with session.get(download_url, headers=self.headers) as response:
                    if response.status == 200:
                        with open(download_path, "wb") as f:
                            async for chunk in response.content.iter_chunked(8192):
                                f.write(chunk)

                        logger.info(f"✅ 下載完成: {download_path}")
                        return True
                    else:
                        logger.error(f"❌ 下載失敗: {response.status}")
                        return False

        except Exception as e:
            logger.error(f"❌ 下載更新失敗: {e}")
            return False


class AutoUpdateManager:
    """自動更新管理器"""

    def __init__(self, owner: str, repo: str, current_version: str, token: Optional[str] = None):
        self.checker = GitHubUpdateChecker(owner, repo, token)
        self.current_version = current_version
        self.update_check_interval = timedelta(hours=6)  # 每 6 小時檢查一次
        self.last_check = None

    async def check_for_updates(self, force: bool = False) -> Optional[Dict[str, Any]]:
        """檢查更新"""
        now = datetime.now()

        # 檢查是否需要更新檢查
        if not force and self.last_check:
            if now - self.last_check < self.update_check_interval:
                logger.debug("⏰ 距離上次檢查時間太短，跳過檢查")
                return None

        self.last_check = now

        try:
            # 獲取最新版本
            latest_release = await self.checker.get_latest_release()
            if not latest_release:
                return None

            # 比較版本
            comparison = await self.checker.compare_versions(
                self.current_version, latest_release["tag_name"]
            )

            if comparison.get("needs_update"):
                logger.info(f"🆕 發現新版本: {latest_release['tag_name']}")
                return {
                    "has_update": True,
                    "current_version": self.current_version,
                    "latest_version": latest_release["tag_name"],
                    "release_info": latest_release,
                    "comparison": comparison,
                    "checked_at": now.isoformat(),
                }
            else:
                logger.info(f"✅ 已是最新版本: {self.current_version}")
                return {
                    "has_update": False,
                    "current_version": self.current_version,
                    "checked_at": now.isoformat(),
                }

        except Exception as e:
            logger.error(f"❌ 檢查更新失敗: {e}")
            return {"error": str(e)}

    async def get_update_summary(self) -> Dict[str, Any]:
        """獲取更新摘要"""
        try:
            # 檢查更新
            update_info = await self.check_for_updates()
            if not update_info or not update_info.get("has_update"):
                return {"message": "目前已是最新版本"}

            release_info = update_info["release_info"]
            comparison = update_info["comparison"]

            # 獲取速率限制資訊
            rate_limit = await self.checker.check_rate_limit()

            return {
                "update_available": True,
                "current_version": self.current_version,
                "latest_version": release_info["tag_name"],
                "release_name": release_info["name"],
                "published_at": release_info["published_at"],
                "is_major_update": comparison.get("is_major_update", False),
                "commits_count": comparison.get("commits_count", 0),
                "release_notes": (
                    release_info["body"][:500] + "..."
                    if len(release_info["body"]) > 500
                    else release_info["body"]
                ),
                "download_url": release_info["html_url"],
                "rate_limit": rate_limit,
            }

        except Exception as e:
            logger.error(f"❌ 獲取更新摘要失敗: {e}")
            return {"error": str(e)}


# 使用範例
async def example_usage():
    """使用範例"""
    # 初始化更新管理器
    updater = AutoUpdateManager(
        owner="Craig-0219",
        repo="potato",
        current_version="v2025.08.30",
        token="your_github_token_here",  # 可選，但建議使用以避免速率限制
    )

    # 檢查更新
    update_info = await updater.check_for_updates()
    print(json.dumps(update_info, indent=2, ensure_ascii=False))

    # 獲取更新摘要
    summary = await updater.get_update_summary()
    print(json.dumps(summary, indent=2, ensure_ascii=False))
