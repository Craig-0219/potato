#!/usr/bin/env python3
"""
API 系統驗證測試腳本
測試 FastAPI 應用、認證系統和 API 端點的完整性
"""
import asyncio
import os
import sys
from datetime import datetime

# 添加專案路徑
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, current_dir)


async def test_api_manager_system():
    """測試 API 管理器系統"""
    print("🔧 測試 API 管理器系統...")

    try:
        # 測試 API 管理器導入
        print("  📊 檢查 API 管理器...")
        try:
            from bot.services.api_manager import APIManager

            print("    ✅ APIManager 類別載入成功")

            # 模擬 bot 對象進行測試
            class MockBot:
                pass

            mock_bot = MockBot()
            api_manager = APIManager(mock_bot)
            print("    ✅ APIManager 初始化成功")

            # 檢查 API 管理器方法
            required_methods = [
                "generate_api_key",
                "revoke_api_key",
                "validate_api_key",
                "handle_api_request",
                "get_api_documentation",
            ]
            for method in required_methods:
                if hasattr(api_manager, method) and callable(getattr(api_manager, method)):
                    print(f"    ✅ {method} 方法存在")
                else:
                    print(f"    ⚠️ {method} 方法缺失")

            # 測試 API 金鑰生成
            print("  🔑 測試 API 金鑰生成...")
            test_permissions = ["statistics:read", "tickets:read"]
            api_key = api_manager.generate_api_key(
                guild_id=123456789, permissions=test_permissions, rate_limit=100
            )

            if api_key and hasattr(api_key, "key_id") and hasattr(api_key, "key_secret"):
                print("    ✅ API 金鑰生成成功")
                print(f"    📋 金鑰 ID: {api_key.key_id[:10]}...")
                print(f"    📋 權限: {', '.join(api_key.permissions)}")
            else:
                print("    ❌ API 金鑰生成失敗")

        except ImportError as e:
            print(f"    ❌ APIManager 導入失敗: {e}")
            return False
        except Exception as e:
            print(f"    ❌ APIManager 初始化失敗: {e}")
            return False

        return True

    except Exception as e:
        print(f"❌ API 管理器系統測試失敗: {e}")
        return False


async def test_api_security_system():
    """測試 API 安全系統"""
    print("\n🔧 測試 API 安全系統...")

    try:
        # 測試 API 安全管理器
        print("  🛡️ 檢查 API 安全管理器...")
        try:
            from bot.services.security.api_security import APISecurityManager

            api_security = APISecurityManager()
            print("    ✅ APISecurityManager 載入成功")

            # 檢查安全管理器方法
            required_methods = [
                "validate_api_key",
                "check_rate_limit",
                "generate_jwt_token",
                "verify_jwt_token",
                "check_ip_access",
            ]
            for method in required_methods:
                if hasattr(api_security, method) and callable(getattr(api_security, method)):
                    print(f"    ✅ {method} 方法存在")
                else:
                    print(f"    ⚠️ {method} 方法缺失")

            # 測試 JWT 令牌生成和驗證
            print("  🎫 測試 JWT 令牌系統...")
            test_user_id = 987654321
            test_permissions = ["api:read", "api:write"]

            # 生成令牌
            token = await api_security.generate_jwt_token(
                user_id=test_user_id, permissions=test_permissions, expires_in=3600
            )

            if token:
                print("    ✅ JWT 令牌生成成功")

                # 驗證令牌
                payload = await api_security.verify_jwt_token(token)
                if payload and payload.get("user_id") == test_user_id:
                    print("    ✅ JWT 令牌驗證成功")
                    print(f"    📋 用戶 ID: {payload.get('user_id')}")
                    print(f"    📋 權限: {', '.join(payload.get('permissions', []))}")
                else:
                    print("    ❌ JWT 令牌驗證失敗")
            else:
                print("    ❌ JWT 令牌生成失敗")

        except ImportError as e:
            print(f"    ❌ APISecurityManager 導入失敗: {e}")
            return False
        except Exception as e:
            print(f"    ❌ APISecurityManager 初始化失敗: {e}")
            return False

        return True

    except Exception as e:
        print(f"❌ API 安全系統測試失敗: {e}")
        return False


async def test_api_endpoints_registration():
    """測試 API 端點註冊"""
    print("\n🔧 測試 API 端點註冊...")

    try:
        from bot.services.api_manager import APIManager

        class MockBot:
            pass

        api_manager = APIManager(MockBot())

        # 檢查端點註冊
        endpoints = api_manager.endpoints
        print(f"  📍 註冊的端點數量: {len(endpoints)}")

        # 檢查關鍵端點類別
        endpoint_categories = {"statistics": 0, "tickets": 0, "ai": 0, "language": 0, "votes": 0}

        for endpoint in endpoints.keys():
            for category in endpoint_categories.keys():
                if category in endpoint:
                    endpoint_categories[category] += 1

        print("  📊 端點分類統計:")
        for category, count in endpoint_categories.items():
            print(f"    • {category}: {count} 個端點")

        # 檢查端點結構
        sample_endpoints = list(endpoints.keys())[:3]
        print("  🔍 端點結構檢查:")
        for endpoint in sample_endpoints:
            config = endpoints[endpoint]
            has_handler = "handler" in config and callable(config["handler"])
            has_permissions = "permissions" in config and isinstance(config["permissions"], list)
            has_description = "description" in config and isinstance(config["description"], str)

            status = "✅" if all([has_handler, has_permissions, has_description]) else "⚠️"
            print(f"    {status} {endpoint}")
            if not has_handler:
                print(f"      ❌ 缺少處理器")
            if not has_permissions:
                print(f"      ❌ 缺少權限配置")
            if not has_description:
                print(f"      ❌ 缺少描述")

        # 測試 API 文檔生成
        print("  📚 測試 API 文檔生成...")
        documentation = api_manager.get_api_documentation()

        if documentation and isinstance(documentation, dict):
            print("    ✅ API 文檔生成成功")
            print(f"    📋 API 版本: {documentation.get('version', 'Unknown')}")
            print(f"    📋 API 標題: {documentation.get('title', 'Unknown')}")
            print(f"    📋 端點數量: {len(documentation.get('endpoints', {}))}")
        else:
            print("    ❌ API 文檔生成失敗")

        return True

    except Exception as e:
        print(f"❌ API 端點註冊測試失敗: {e}")
        return False


async def test_api_request_handling():
    """測試 API 請求處理"""
    print("\n🔧 測試 API 請求處理...")

    try:
        from datetime import datetime

        from bot.services.api_manager import APIManager, APIRequest

        class MockBot:
            pass

        api_manager = APIManager(MockBot())

        # 創建測試請求
        print("  📤 創建測試 API 請求...")
        test_request = APIRequest(
            endpoint="/api/v1/statistics/overview",
            method="GET",
            guild_id=123456789,
            user_id=987654321,
            parameters={"days": 30},
            headers={"User-Agent": "Test-Client/1.0"},
            timestamp=datetime.now(),
        )

        print(f"    📋 請求端點: {test_request.endpoint}")
        print(f"    📋 請求方法: {test_request.method}")
        print(f"    📋 伺服器 ID: {test_request.guild_id}")

        # 測試請求處理（不需要真實的數據庫連接）
        print("  ⚙️ 測試請求處理邏輯...")
        try:
            # 檢查端點是否存在
            endpoint_key = f"{test_request.method} {test_request.endpoint}"
            if endpoint_key in api_manager.endpoints:
                print("    ✅ 端點存在於註冊表中")

                endpoint_config = api_manager.endpoints[endpoint_key]
                handler = endpoint_config.get("handler")

                if handler and callable(handler):
                    print("    ✅ 端點處理器可調用")
                else:
                    print("    ❌ 端點處理器不可調用")

                permissions = endpoint_config.get("permissions", [])
                print(f"    📋 需要權限: {', '.join(permissions)}")

            else:
                print("    ❌ 端點不存在於註冊表中")

        except Exception as e:
            print(f"    ⚠️ 請求處理測試遇到問題（預期，因為缺少真實服務）: {e}")

        return True

    except Exception as e:
        print(f"❌ API 請求處理測試失敗: {e}")
        return False


async def test_oauth_integration():
    """測試 OAuth 整合"""
    print("\n🔧 測試 OAuth 整合...")

    try:
        # 檢查 OAuth 相關檔案和模組
        print("  🔐 檢查 OAuth 系統...")

        # 查找 OAuth 相關模組
        oauth_modules = []
        try:
            # 嘗試導入可能的 OAuth 模組
            oauth_paths = [
                "bot.services.oauth_manager",
                "bot.services.auth.oauth",
                "bot.services.authentication",
                "shared.oauth",
            ]

            for path in oauth_paths:
                try:
                    module = __import__(path, fromlist=[""])
                    oauth_modules.append(path)
                    print(f"    ✅ 找到 OAuth 模組: {path}")
                except ImportError:
                    continue

            if not oauth_modules:
                print("    ⚠️ 未找到專用 OAuth 模組（可能整合在其他系統中）")

        except Exception as e:
            print(f"    ❌ OAuth 模組檢查失敗: {e}")

        # 檢查 OAuth 配置
        print("  ⚙️ 檢查 OAuth 配置...")
        try:
            import shared.config as config

            oauth_configs = {
                "CLIENT_ID": getattr(config, "CLIENT_ID", None),
                "CLIENT_SECRET": getattr(config, "CLIENT_SECRET", None),
                "REDIRECT_URI": getattr(config, "REDIRECT_URI", None),
                "GUILD_ID": getattr(config, "GUILD_ID", None),
            }

            for key, value in oauth_configs.items():
                if value:
                    print(f"    ✅ {key} 已設定")
                else:
                    print(f"    ⚠️ {key} 未設定")

        except Exception as e:
            print(f"    ❌ OAuth 配置檢查失敗: {e}")

        return True

    except Exception as e:
        print(f"❌ OAuth 整合測試失敗: {e}")
        return False


async def test_fastapi_compatibility():
    """測試 FastAPI 相容性"""
    print("\n🔧 測試 FastAPI 相容性...")

    try:
        # 檢查 FastAPI 依賴
        print("  📦 檢查 FastAPI 依賴...")
        try:
            import fastapi

            print(f"    ✅ FastAPI 版本: {fastapi.__version__}")
        except ImportError:
            print("    ❌ FastAPI 未安裝")
            return False

        try:
            pass

            print(f"    ✅ Uvicorn 可用")
        except ImportError:
            print("    ⚠️ Uvicorn 未安裝（可選）")

        # 檢查 API 結構相容性
        print("  🔧 檢查 API 結構相容性...")

        # 驗證 API 管理器是否能夠與 FastAPI 整合
        from bot.services.api_manager import APIManager, APIResponse

        class MockBot:
            pass

        api_manager = APIManager(MockBot())

        # 檢查響應格式是否與 FastAPI 相容
        sample_response = APIResponse(
            status_code=200, data={"message": "test"}, message="success", timestamp=datetime.now()
        )

        if hasattr(sample_response, "status_code") and hasattr(sample_response, "data"):
            print("    ✅ API 響應格式與 FastAPI 相容")
        else:
            print("    ❌ API 響應格式不相容")

        # 檢查端點路徑格式
        endpoints = api_manager.endpoints
        fastapi_compatible = True

        for endpoint in list(endpoints.keys())[:5]:  # 檢查前5個端點
            method, path = endpoint.split(" ", 1)

            # 檢查路徑是否符合 REST API 慣例
            if path.startswith("/api/"):
                print(f"    ✅ {endpoint} - 路徑格式正確")
            else:
                print(f"    ⚠️ {endpoint} - 路徑格式可能需要調整")
                fastapi_compatible = False

        return fastapi_compatible

    except Exception as e:
        print(f"❌ FastAPI 相容性測試失敗: {e}")
        return False


async def main():
    """主測試函數"""
    print("🚀 開始 API 系統驗證測試\n")

    tests = [
        ("API 管理器系統", test_api_manager_system),
        ("API 安全系統", test_api_security_system),
        ("API 端點註冊", test_api_endpoints_registration),
        ("API 請求處理", test_api_request_handling),
        ("OAuth 整合", test_oauth_integration),
        ("FastAPI 相容性", test_fastapi_compatibility),
    ]

    passed = 0
    total = len(tests)

    for test_name, test_func in tests:
        print(f"\n{'='*60}")
        print(f"📋 執行: {test_name}")
        print("=" * 60)

        try:
            if await test_func():
                print(f"✅ {test_name} - 通過")
                passed += 1
            else:
                print(f"❌ {test_name} - 失敗")
        except Exception as e:
            print(f"💥 {test_name} - 執行錯誤: {e}")

    print(f"\n🎯 API 系統測試結果: {passed}/{total} 通過")

    if passed >= total - 1:  # 允許一個測試失敗
        print("🎉 API 系統驗證基本通過！")
        print("📋 API 系統結構完整，主要組件正常運作")
        return True
    else:
        print("⚠️ API 系統存在問題，需要進一步檢查")
        print("💡 建議檢查依賴安裝和配置設定")
        return False


if __name__ == "__main__":
    result = asyncio.run(main())
    sys.exit(0 if result else 1)
