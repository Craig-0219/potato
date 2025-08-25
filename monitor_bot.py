#!/usr/bin/env python3
"""
監控 Bot 狀態和命令同步進度
"""

import asyncio
import time
from datetime import datetime, timedelta

async def monitor_bot_status():
    """監控 Bot 狀態"""
    print("🔍 開始監控 Bot 狀態...")
    print("⏰ Discord API 速率限制通常會在約 6-7 分鐘後重置")
    print("📊 預計下次成功同步時間：", (datetime.now() + timedelta(minutes=6)).strftime('%H:%M:%S'))
    
    start_time = datetime.now()
    check_count = 0
    
    while True:
        check_count += 1
        elapsed = datetime.now() - start_time
        
        print(f"\n📋 檢查 #{check_count} - 已等待 {elapsed.total_seconds():.0f} 秒")
        
        # 檢查命令是否已同步
        try:
            result = await asyncio.create_subprocess_exec(
                'python3', 'check_commands.py',
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await result.communicate()
            
            stdout_text = stdout.decode('utf-8', errors='ignore')
            
            if "/menu" in stdout_text:
                print("🎉 成功！/menu 命令已同步到 Discord！")
                break
            elif "找到" in stdout_text and "個已註冊的斜線命令" in stdout_text:
                print("✅ 有命令已同步，但可能不包含 /menu")
                print(stdout_text)
            else:
                print("⏳ 命令尚未同步，繼續等待...")
        
        except Exception as e:
            print(f"❌ 檢查時發生錯誤: {e}")
        
        # 如果等待超過 10 分鐘，建議手動檢查
        if elapsed.total_seconds() > 600:
            print("⚠️ 已等待超過 10 分鐘，建議手動檢查 Bot 狀態")
            break
        
        # 等待 30 秒後再檢查
        await asyncio.sleep(30)

if __name__ == "__main__":
    asyncio.run(monitor_bot_status())