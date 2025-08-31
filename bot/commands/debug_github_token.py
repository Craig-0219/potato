"""
GitHub Token 診斷指令
用於除錯 GitHub API 401 錯誤問題
"""

import os
import aiohttp
import discord
from discord.ext import commands


class GitHubTokenDebug(commands.Cog):
    """GitHub Token 診斷工具"""

    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="debug_github_token", aliases=["dgt"])
    @commands.has_permissions(administrator=True)
    async def debug_github_token(self, ctx):
        """診斷 GitHub Token 配置"""
        
        embed = discord.Embed(
            title="🔍 GitHub Token 診斷報告",
            color=discord.Color.blue(),
            description="檢查 GitHub API 認證狀態"
        )
        
        # 1. 檢查環境變數
        github_token = os.getenv("GITHUB_TOKEN")
        if not github_token:
            embed.add_field(
                name="❌ 環境變數",
                value="GITHUB_TOKEN 未設置",
                inline=False
            )
        else:
            # 驗證 token 格式
            if github_token.startswith(('ghp_', 'github_pat_')):
                token_status = f"✅ 已設置 ({github_token[:4]}...{github_token[-4:]})"
            else:
                token_status = f"⚠️ 格式異常 ({github_token[:4]}...)"
                
            embed.add_field(
                name="🔑 環境變數",
                value=f"{token_status}\n長度: {len(github_token)} 字符",
                inline=False
            )
        
        # 2. 測試 API 連接
        if github_token:
            try:
                headers = {
                    "Accept": "application/vnd.github.v3+json",
                    "User-Agent": "Potato-Bot-Debug/1.0",
                    "Authorization": f"token {github_token}"
                }
                
                async with aiohttp.ClientSession() as session:
                    # 測試用戶資訊
                    async with session.get("https://api.github.com/user", headers=headers) as response:
                        if response.status == 200:
                            user_data = await response.json()
                            embed.add_field(
                                name="✅ Token 驗證",
                                value=f"用戶: {user_data.get('login', 'unknown')}\n"
                                      f"ID: {user_data.get('id', 'unknown')}",
                                inline=True
                            )
                        else:
                            error_text = await response.text()
                            embed.add_field(
                                name="❌ Token 驗證",
                                value=f"狀態碼: {response.status}\n錯誤: {error_text[:100]}",
                                inline=True
                            )
                    
                    # 測試倉庫存取
                    repo_url = "https://api.github.com/repos/Craig-0219/potato"
                    async with session.get(repo_url, headers=headers) as response:
                        if response.status == 200:
                            repo_data = await response.json()
                            embed.add_field(
                                name="✅ 倉庫存取",
                                value=f"名稱: {repo_data.get('full_name')}\n"
                                      f"私有: {'是' if repo_data.get('private') else '否'}",
                                inline=True
                            )
                        else:
                            embed.add_field(
                                name="❌ 倉庫存取",
                                value=f"狀態碼: {response.status}",
                                inline=True
                            )
                    
                    # 檢查速率限制
                    async with session.get("https://api.github.com/rate_limit", headers=headers) as response:
                        if response.status == 200:
                            rate_data = await response.json()
                            core_limit = rate_data.get('resources', {}).get('core', {})
                            embed.add_field(
                                name="📊 速率限制",
                                value=f"剩餘: {core_limit.get('remaining', 0)}/{core_limit.get('limit', 0)}\n"
                                      f"重置: <t:{core_limit.get('reset', 0)}:R>",
                                inline=True
                            )
                            
            except Exception as e:
                embed.add_field(
                    name="❌ API 測試失敗",
                    value=f"錯誤: {str(e)[:100]}",
                    inline=False
                )
        
        # 3. 建議
        suggestions = []
        if not github_token:
            suggestions.append("• 設置 GITHUB_TOKEN 環境變數")
        elif not github_token.startswith(('ghp_', 'github_pat_')):
            suggestions.append("• 檢查 Token 格式是否正確")
        
        if suggestions:
            embed.add_field(
                name="💡 建議",
                value="\n".join(suggestions),
                inline=False
            )
        
        embed.set_footer(text="GitHub Token 診斷工具 • 用於除錯 API 401 錯誤")
        
        await ctx.send(embed=embed)


async def setup(bot):
    await bot.add_cog(GitHubTokenDebug(bot))