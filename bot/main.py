# bot/main.py - Discord Bot 啟動主程式

import os
import sys
import asyncio
import discord
from dotenv import load_dotenv
from discord.ext import commands

# 👉 Windows 相容：避免 asyncio event loop 已關閉錯誤
if sys.platform.startswith('win'):
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

# 👉 載入 .env 環境變數
load_dotenv()

# 👉 檢查必需的環境變數
required_vars = ["DISCORD_TOKEN", "DB_HOST", "DB_USER", "DB_PASSWORD", "DB_NAME"]
missing = [var for var in required_vars if os.getenv(var) is None]
if missing:
    print(f"⚠️ 缺少 .env 設定：{', '.join(missing)}")
    print("請參考 .env.example 並建立 .env 後再重新啟動。")
    sys.exit(1)

# 👉 建立 Discord Bot 實例
intents = discord.Intents.default()
intents.message_content = True  # 若要支援 on_message 監聽器
bot = commands.Bot(command_prefix="/", intents=intents)

# 👉 Bot 上線時執行
@bot.event
async def on_ready():
    print(f"✅ 機器人已上線：{bot.user} (ID: {bot.user.id})")
    
    # 檢查載入的指令
    commands_list = [cmd.name for cmd in bot.tree.get_commands()]
    print(f"載入的指令：{commands_list}")
    
    # ✅ 強制同步指令到 Discord
    try:
        print("🔄 開始同步指令到 Discord...")
        
        # 方法一：全域同步（推薦，但需要1小時生效）
        synced = await bot.tree.sync()
        print(f"✅ 全域同步成功：{len(synced)} 個指令")
        
        # 方法二：如果你想立即在特定伺服器測試，使用這個（替換為你的伺服器ID）
        # guild = discord.Object(id=1392396522905276446)  # 替換為你的伺服器ID
        # synced = await bot.tree.sync(guild=guild)
        # print(f"✅ 伺服器同步成功：{len(synced)} 個指令")
        
        for cmd in synced:
            print(f"  - /{cmd.name}: {cmd.description}")
            
    except Exception as e:
        print(f"❌ 指令同步失敗：{e}")

# 👉 可選：加入手動同步指令（用於測試）
@bot.command()
async def sync(ctx):
    """手動同步指令（測試用）"""
    if ctx.author.id != 292993868092276736:  # 替換為你的 Discord 用戶 ID
        await ctx.send("❌ 只有開發者可以使用此指令。")
        return
    
    try:
        synced = await bot.tree.sync()
        await ctx.send(f"✅ 同步成功：{len(synced)} 個指令")
    except Exception as e:
        await ctx.send(f"❌ 同步失敗：{e}")

# 👉 主執行邏輯
async def main():
    try:
        # ✅ 資料庫初始化
        from bot.db.pool import db_pool
        from shared import config  # 共用設定值來自 shared/config.py

        await db_pool.init_pool(
            host=config.DB_HOST,
            port=config.DB_PORT,
            user=config.DB_USER,
            password=config.DB_PASSWORD,
            db_name=config.DB_NAME
        )

        # ✅ 自動建立資料表（若尚未存在）
        from bot.db import vote_dao
        await vote_dao.create_tables()

        # ✅ 載入功能模組（Cogs）
        print("🔄 載入功能模組...")
        await bot.load_extension("bot.cogs.vote")
        print("✅ vote.py 載入成功")
        
        await bot.load_extension("bot.cogs.vote_listener")
        print("✅ vote_listener.py 載入成功")

        await bot.load_extension("bot.cogs.ticket")
        print("✅ ticket.py 載入成功")
        # ✅ 啟動機器人
        print("🚀 啟動機器人...")
        await bot.start(config.DISCORD_TOKEN)

    except Exception as e:
        print(f"❌ 機器人啟動失敗：{e}")
        import traceback
        print(f"完整錯誤：{traceback.format_exc()}")
        raise

# 👉 執行 main 函式
if __name__ == "__main__":
    asyncio.run(main())