# api/middleware/auth_middleware.py
"""
認證中介軟體
為 FastAPI 提供全局認證處理
"""

import time
from typing import Callable, Optional
from fastapi import Request, Response, HTTPException
from fastapi.security.utils import get_authorization_scheme_param
from bot.services.auth_manager import auth_manager, AuthUser
from shared.logger import logger


class AuthMiddleware:
    """認證中介軟體"""
    
    def __init__(self):
        # 不需要認證的路徑
        self.public_paths = {
            "/docs",
            "/redoc", 
            "/openapi.json",
            "/auth/login",
            "/auth/setup-password",
            "/auth/health",
            "/health",
            "/"
        }
        
        # 需要管理員權限的路徑
        self.admin_paths = {
            "/admin",
            "/users",
            "/system/settings"
        }
        
        # 需要客服權限的路徑  
        self.staff_paths = {
            "/tickets",
            "/statistics",
            "/data"
        }
    
    async def __call__(self, request: Request, call_next: Callable) -> Response:
        """處理請求"""
        start_time = time.time()
        
        # 檢查是否為公開路徑
        if self._is_public_path(request.url.path):
            response = await call_next(request)
            return self._add_timing_header(response, start_time)
        
        # 提取認證令牌
        auth_user = None
        try:
            auth_user = await self._extract_auth_user(request)
        except HTTPException as e:
            return Response(
                content=f'{{"error": "{e.detail}"}}',
                status_code=e.status_code,
                media_type="application/json"
            )
        
        # 檢查路徑權限
        if not self._check_path_permission(request.url.path, auth_user):
            return Response(
                content='{"error": "權限不足"}',
                status_code=403,
                media_type="application/json"
            )
        
        # 將認證用戶加入請求狀態
        request.state.user = auth_user
        
        # 繼續處理請求
        response = await call_next(request)
        
        # 記錄請求日誌
        self._log_request(request, response, auth_user, time.time() - start_time)
        
        return self._add_timing_header(response, start_time)
    
    def _is_public_path(self, path: str) -> bool:
        """檢查是否為公開路徑"""
        # 完全匹配
        if path in self.public_paths:
            return True
        
        # 前綴匹配
        for public_path in self.public_paths:
            if path.startswith(public_path):
                return True
        
        # 靜態資源
        if path.startswith('/static/') or path.startswith('/assets/'):
            return True
        
        return False
    
    async def _extract_auth_user(self, request: Request) -> Optional[AuthUser]:
        """提取並驗證認證用戶"""
        # 從 Authorization header 提取令牌
        authorization = request.headers.get("authorization")
        if not authorization:
            # 嘗試從 cookie 獲取會話令牌
            session_token = request.cookies.get("session_token")
            if session_token:
                success, auth_user, _ = await auth_manager.verify_session(session_token)
                if success:
                    return auth_user
            
            raise HTTPException(status_code=401, detail="缺少認證令牌")
        
        scheme, token = get_authorization_scheme_param(authorization)
        
        if not token or scheme.lower() != "bearer":
            raise HTTPException(status_code=401, detail="認證格式錯誤")
        
        # 依序嘗試不同的認證方式
        
        # 1. JWT 令牌
        is_valid, payload, message = auth_manager.verify_jwt_token(token)
        if is_valid and payload:
            return AuthUser(
                user_id=payload['user_id'],
                discord_id=payload['discord_id'], 
                username=payload['username'],
                guild_id=payload['guild_id'],
                roles=payload['roles'],
                permissions=payload['permissions'],
                is_admin=payload['is_admin'],
                is_staff=payload['is_staff']
            )
        
        # 2. API 金鑰
        is_valid, auth_user, message = await auth_manager.verify_api_key(token)
        if is_valid and auth_user:
            return auth_user
        
        # 3. 會話令牌
        is_valid, auth_user, message = await auth_manager.verify_session(token)
        if is_valid and auth_user:
            return auth_user
        
        raise HTTPException(status_code=401, detail="認證令牌無效")
    
    def _check_path_permission(self, path: str, auth_user: Optional[AuthUser]) -> bool:
        """檢查路徑權限"""
        if not auth_user:
            return False
        
        # 檢查管理員路徑
        if any(path.startswith(admin_path) for admin_path in self.admin_paths):
            return auth_user.is_admin
        
        # 檢查客服路徑
        if any(path.startswith(staff_path) for staff_path in self.staff_paths):
            return auth_user.is_staff or auth_user.is_admin
        
        # 其他路徑，只要認證過就可以訪問
        return True
    
    def _check_resource_permission(self, path: str, method: str, auth_user: AuthUser) -> bool:
        """檢查資源級別權限"""
        # 根據路徑和方法檢查細粒度權限
        
        if path.startswith('/tickets'):
            if method == 'GET':
                return auth_manager.check_permission(auth_user, 'tickets.read')
            elif method in ['POST', 'PUT', 'PATCH']:
                return auth_manager.check_permission(auth_user, 'tickets.write')
            elif method == 'DELETE':
                return auth_manager.check_permission(auth_user, 'tickets.delete')
        
        elif path.startswith('/statistics'):
            return auth_manager.check_permission(auth_user, 'statistics.read')
        
        elif path.startswith('/users'):
            if method == 'GET':
                return auth_manager.check_permission(auth_user, 'users.read')
            else:
                return auth_manager.check_permission(auth_user, 'users.manage')
        
        elif path.startswith('/data'):
            if 'export' in path:
                return auth_manager.check_permission(auth_user, 'data.export')
            elif 'cleanup' in path:
                return auth_manager.check_permission(auth_user, 'data.cleanup')
        
        # 預設允許
        return True
    
    def _log_request(self, request: Request, response: Response, 
                    auth_user: Optional[AuthUser], duration: float):
        """記錄請求日誌"""
        try:
            log_data = {
                'method': request.method,
                'path': request.url.path,
                'status_code': response.status_code,
                'duration': f"{duration:.3f}s",
                'ip': request.client.host if request.client else 'unknown',
                'user_agent': request.headers.get('user-agent', 'unknown')
            }
            
            if auth_user:
                log_data.update({
                    'user_id': auth_user.user_id,
                    'username': auth_user.username,
                    'discord_id': auth_user.discord_id
                })
            
            # 只記錄錯誤和重要操作
            if response.status_code >= 400 or request.method != 'GET':
                if response.status_code >= 400:
                    logger.warning(f"API請求失敗: {log_data}")
                else:
                    logger.info(f"API請求: {log_data}")
        
        except Exception as e:
            logger.error(f"記錄請求日誌失敗: {e}")
    
    def _add_timing_header(self, response: Response, start_time: float) -> Response:
        """添加請求時間標頭"""
        process_time = time.time() - start_time
        response.headers["X-Process-Time"] = str(process_time)
        return response


# CORS 中介軟體配置
def get_cors_middleware_config():
    """獲取 CORS 中介軟體配置"""
    return {
        "allow_origins": [
            "http://localhost:3000",
            "http://localhost:8080", 
            "http://127.0.0.1:3000",
            "http://127.0.0.1:8080"
        ],
        "allow_credentials": True,
        "allow_methods": ["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        "allow_headers": [
            "Authorization", 
            "Content-Type", 
            "Accept",
            "Origin",
            "X-Requested-With"
        ],
    }


# 安全標頭中介軟體
class SecurityHeadersMiddleware:
    """安全標頭中介軟體"""
    
    async def __call__(self, request: Request, call_next: Callable) -> Response:
        response = await call_next(request)
        
        # 添加安全標頭
        response.headers.update({
            "X-Content-Type-Options": "nosniff",
            "X-Frame-Options": "DENY", 
            "X-XSS-Protection": "1; mode=block",
            "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
            "Referrer-Policy": "strict-origin-when-cross-origin"
        })
        
        return response


# 速率限制中介軟體 (簡化版)
class RateLimitMiddleware:
    """速率限制中介軟體"""
    
    def __init__(self, requests_per_minute: int = 60):
        self.requests_per_minute = requests_per_minute
        self.request_counts = {}
        self.last_reset = {}
    
    async def __call__(self, request: Request, call_next: Callable) -> Response:
        client_ip = request.client.host if request.client else "unknown"
        current_time = time.time()
        
        # 重設計數器 (每分鐘)
        if client_ip not in self.last_reset or current_time - self.last_reset[client_ip] >= 60:
            self.request_counts[client_ip] = 0
            self.last_reset[client_ip] = current_time
        
        # 檢查速率限制
        self.request_counts[client_ip] += 1
        
        if self.request_counts[client_ip] > self.requests_per_minute:
            return Response(
                content='{"error": "速率限制：請求過於頻繁"}',
                status_code=429,
                media_type="application/json",
                headers={"Retry-After": "60"}
            )
        
        response = await call_next(request)
        
        # 添加速率限制標頭
        response.headers["X-RateLimit-Limit"] = str(self.requests_per_minute)
        response.headers["X-RateLimit-Remaining"] = str(
            max(0, self.requests_per_minute - self.request_counts[client_ip])
        )
        response.headers["X-RateLimit-Reset"] = str(int(self.last_reset[client_ip] + 60))
        
        return response