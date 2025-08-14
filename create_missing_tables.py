#!/usr/bin/env python3
"""
創建缺失的資料庫表格 - v2.2.0
使用標準 mysql 客戶端執行 SQL 腳本
"""

import os
import sys
import subprocess
from typing import Optional

def run_mysql_command(sql_file: str, host: str = "localhost", user: str = "root", 
                     password: Optional[str] = None, database: str = "potato_db") -> bool:
    """執行 MySQL 命令"""
    try:
        # 構建 mysql 命令
        cmd = ["mysql", f"--host={host}", f"--user={user}"]
        
        if password:
            cmd.append(f"--password={password}")
        
        cmd.extend([database])
        
        print(f"🔄 執行 SQL 腳本: {sql_file}")
        print(f"📡 連接資訊: {user}@{host}/{database}")
        
        # 執行 SQL 檔案
        with open(sql_file, 'r', encoding='utf-8') as f:
            result = subprocess.run(
                cmd,
                stdin=f,
                capture_output=True,
                text=True
            )
        
        if result.returncode == 0:
            print("✅ SQL 腳本執行成功")
            if result.stdout.strip():
                print("📄 輸出:")
                print(result.stdout)
            return True
        else:
            print("❌ SQL 腳本執行失敗")
            print("錯誤訊息:")
            print(result.stderr)
            return False
            
    except FileNotFoundError:
        print("❌ 找不到 mysql 客戶端")
        print("請安裝 MySQL 客戶端或使用其他方法執行 SQL 腳本")
        return False
    except Exception as e:
        print(f"❌ 執行過程中發生錯誤: {e}")
        return False

def create_tables_directly():
    """直接在 Python 中創建表格的替代方法"""
    print("\n🔄 嘗試使用 Python 直接創建表格...")
    
    try:
        # 嘗試導入並使用現有的資料庫連接
        import sys
        import os
        sys.path.append(os.path.dirname(os.path.abspath(__file__)))
        
        from shared.config import DB_HOST, DB_USER, DB_PASSWORD, DB_NAME
        
        # 顯示連接資訊但隱藏密碼
        print(f"📡 資料庫連接資訊: {DB_USER}@{DB_HOST}/{DB_NAME}")
        
        # 提示用戶手動執行 SQL
        print("\n💡 由於依賴項限制，請手動執行以下操作之一:")
        print(f"1. 使用 MySQL 客戶端執行 SQL 腳本:")
        print(f"   mysql -h {DB_HOST} -u {DB_USER} -p {DB_NAME} < create_missing_tables.sql")
        
        print(f"\n2. 或者登入 MySQL 控制台手動執行:")
        print(f"   mysql -h {DB_HOST} -u {DB_USER} -p")
        print(f"   USE {DB_NAME};")
        print(f"   SOURCE create_missing_tables.sql;")
        
        print("\n3. 或者安裝完整依賴項後執行:")
        print("   pip install -r requirements.txt")
        print("   python scripts/create_cross_platform_tables.py")
        
        return False
        
    except Exception as e:
        print(f"❌ 無法讀取資料庫配置: {e}")
        return False

def main():
    """主函數"""
    print("🏗️ Potato Bot v2.2.0 - 創建缺失的資料庫表格")
    print("=" * 50)
    
    sql_file = "create_missing_tables.sql"
    
    # 檢查 SQL 檔案是否存在
    if not os.path.exists(sql_file):
        print(f"❌ SQL 檔案不存在: {sql_file}")
        return False
    
    print(f"📄 找到 SQL 腳本: {sql_file}")
    
    # 從環境變數或配置中獲取資料庫連接資訊
    try:
        from dotenv import load_dotenv
        load_dotenv()
        
        host = os.getenv("DB_HOST", "localhost")
        user = os.getenv("DB_USER", "root")
        password = os.getenv("DB_PASSWORD")
        database = os.getenv("DB_NAME", "potato_db")
        
    except ImportError:
        print("⚠️ python-dotenv 未安裝，使用默認值")
        host = "localhost"
        user = "root"
        password = None
        database = "potato_db"
    
    # 如果沒有密碼，提示用戶
    if not password:
        import getpass
        password = getpass.getpass(f"請輸入 MySQL 用戶 '{user}' 的密碼: ")
    
    # 嘗試執行 SQL 腳本
    success = run_mysql_command(sql_file, host, user, password, database)
    
    if not success:
        success = create_tables_directly()
    
    print("\n" + "=" * 50)
    if success:
        print("🎉 資料庫表格創建完成！")
        print("✅ 跨平台經濟系統現在應該能正常運作")
        print("✅ 投票系統現在應該能正常運作")
        
        print("\n📋 已創建的表格:")
        tables = [
            "cross_platform_users - 跨平台用戶綁定", 
            "cross_platform_transactions - 交易記錄",
            "platform_configs - 平台配置",
            "cross_platform_achievements - 跨平台成就",
            "sync_logs - 同步日誌",
            "vote_results - 投票結果"
        ]
        
        for table in tables:
            print(f"  • {table}")
            
    else:
        print("❌ 資料庫表格創建失敗")
        print("請參考上述建議手動執行 SQL 腳本")
    
    return success

if __name__ == "__main__":
    try:
        success = main()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n👋 操作已取消")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ 程序執行錯誤: {e}")
        sys.exit(1)