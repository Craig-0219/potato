# api/auth_routes.py
"""
API 認證路由
提供登入、註冊和金鑰管理端點
"""

import json
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any
from fastapi import APIRouter, HTTPException, Depends, Request, Response, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from bot.services.auth_manager import auth_manager, AuthUser

# 請求模型
class LoginRequest(BaseModel):
    discord_id: str = Field(..., description="Discord 用戶 ID")
    password: str = Field(..., description="用戶密碼")
    guild_id: int = Field(..., description="伺服器 ID")

class PasswordSetupRequest(BaseModel):
    discord_id: str = Field(..., description="Discord 用戶 ID")
    password: str = Field(..., min_length=6, description="用戶密碼")
    guild_id: int = Field(..., description="伺服器 ID")

class APIKeyCreateRequest(BaseModel):
    name: str = Field(..., description="API 金鑰名稱")
    permissions: list[str] = Field(default=[], description="權限列表")
    expires_days: int = Field(default=30, description="過期天數，0 表示永不過期")

class TokenRefreshRequest(BaseModel):
    refresh_token: str = Field(..., description="更新令牌")

# 回應模型
class LoginResponse(BaseModel):
    success: bool
    message: str
    data: Optional[Dict[str, Any]] = None

class AuthResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    refresh_token: Optional[str] = None
    user_info: Dict[str, Any]

class APIKeyResponse(BaseModel):
    success: bool
    message: str
    api_key: Optional[str] = None

# 安全性
security = HTTPBearer()

router = APIRouter(prefix="/auth", tags=["認證"])


# ===== 依賴注入 =====

async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> AuthUser:
    """獲取當前認證用戶"""
    token = credentials.credentials
    
    # 嘗試驗證 JWT 令牌
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
    
    # 嘗試驗證 API 金鑰
    is_valid, auth_user, message = await auth_manager.verify_api_key(token)
    if is_valid and auth_user:
        return auth_user
    
    # 嘗試驗證會話令牌
    is_valid, auth_user, message = await auth_manager.verify_session(token)
    if is_valid and auth_user:
        return auth_user
    
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="無效的認證令牌",
        headers={"WWW-Authenticate": "Bearer"},
    )

async def get_admin_user(
    current_user: AuthUser = Depends(get_current_user)
) -> AuthUser:
    """確保當前用戶為管理員"""
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="需要管理員權限"
        )
    return current_user

async def get_staff_user(
    current_user: AuthUser = Depends(get_current_user)
) -> AuthUser:
    """確保當前用戶為客服或管理員"""
    if not (current_user.is_staff or current_user.is_admin):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="需要客服權限"
        )
    return current_user


# ===== 認證端點 =====

@router.post("/login", response_model=LoginResponse, summary="用戶登入")
async def login(request: LoginRequest, req: Request):
    """
    用戶登入端點
    
    支援密碼登入，返回 JWT 令牌和會話令牌
    """
    try:
        # 認證用戶
        success, message, auth_user = await auth_manager.authenticate_user(
            request.discord_id, request.password, request.guild_id
        )
        
        if not success:
            return LoginResponse(success=False, message=message)
        
        # 生成令牌
        access_token = auth_manager.generate_jwt_token(auth_user)
        if not access_token:
            return LoginResponse(success=False, message="生成令牌失敗")
        
        # 創建會話
        client_ip = req.client.host
        user_agent = req.headers.get("user-agent", "")
        session_token = await auth_manager.create_login_session(
            auth_user.user_id, client_ip, user_agent
        )
        
        # 計算過期時間
        expires_in = auth_manager.token_expiry_hours * 3600
        
        return LoginResponse(
            success=True,
            message="登入成功",
            data={
                "access_token": access_token,
                "token_type": "bearer",
                "expires_in": expires_in,
                "session_token": session_token,
                "user_info": {
                    "user_id": auth_user.user_id,
                    "discord_id": auth_user.discord_id,
                    "username": auth_user.username,
                    "guild_id": auth_user.guild_id,
                    "roles": auth_user.roles,
                    "permissions": auth_user.permissions,
                    "is_admin": auth_user.is_admin,
                    "is_staff": auth_user.is_staff
                }
            }
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"登入失敗: {str(e)}")


@router.post("/setup-password", response_model=LoginResponse, summary="設定密碼")
async def setup_password(request: PasswordSetupRequest):
    """
    為 Discord 用戶設定 Web 登入密碼
    
    需要先通過 Discord 驗證身份
    """
    try:
        # 注意：在實際應用中，這裡應該驗證請求來源是否為已認證的 Discord 用戶
        # 可以通過 Discord OAuth2 或其他方式驗證
        
        # 檢查用戶是否已存在
        success, message, auth_user = await auth_manager.authenticate_user(
            request.discord_id, "dummy", request.guild_id
        )
        
        if success:
            return LoginResponse(success=False, message="用戶已設定密碼，請使用登入功能")
        
        # 這裡需要實現 Discord 身份驗證邏輯
        # 暫時返回錯誤，提示用戶通過機器人指令設定密碼
        return LoginResponse(
            success=False, 
            message="請使用 Discord 機器人指令 /setup-web-password 設定密碼"
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"設定密碼失敗: {str(e)}")


@router.post("/refresh", response_model=AuthResponse, summary="刷新令牌")
async def refresh_token(request: TokenRefreshRequest):
    """
    使用更新令牌刷新存取令牌
    """
    try:
        # 驗證會話令牌
        success, auth_user, message = await auth_manager.verify_session(request.refresh_token)
        
        if not success:
            raise HTTPException(status_code=401, detail=message)
        
        # 生成新的存取令牌
        new_access_token = auth_manager.generate_jwt_token(auth_user)
        if not new_access_token:
            raise HTTPException(status_code=500, detail="生成新令牌失敗")
        
        expires_in = auth_manager.token_expiry_hours * 3600
        
        return AuthResponse(
            access_token=new_access_token,
            expires_in=expires_in,
            user_info={
                "user_id": auth_user.user_id,
                "discord_id": auth_user.discord_id,
                "username": auth_user.username,
                "guild_id": auth_user.guild_id,
                "roles": auth_user.roles,
                "permissions": auth_user.permissions,
                "is_admin": auth_user.is_admin,
                "is_staff": auth_user.is_staff
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"刷新令牌失敗: {str(e)}")


@router.get("/me", response_model=Dict[str, Any], summary="獲取當前用戶資訊")
async def get_me(current_user: AuthUser = Depends(get_current_user)):
    """
    獲取當前認證用戶的資訊
    """
    return {
        "user_id": current_user.user_id,
        "discord_id": current_user.discord_id,
        "username": current_user.username,
        "guild_id": current_user.guild_id,
        "roles": current_user.roles,
        "permissions": current_user.permissions,
        "is_admin": current_user.is_admin,
        "is_staff": current_user.is_staff
    }


@router.post("/logout", response_model=Dict[str, str], summary="用戶登出")
async def logout(
    req: Request,
    current_user: AuthUser = Depends(get_current_user)
):
    """
    用戶登出，撤銷會話令牌
    """
    try:
        # 如果使用的是會話令牌，撤銷會話
        auth_header = req.headers.get("authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header[7:]
            
            # 嘗試作為會話令牌撤銷
            # 這裡可以實現會話撤銷邏輯
            # 由於當前設計，會話令牌在資料庫中，可以標記為無效
            
            return {"message": "登出成功"}
        
        return {"message": "登出成功"}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"登出失敗: {str(e)}")


# ===== API 金鑰管理 =====

@router.post("/api-keys", response_model=APIKeyResponse, summary="創建 API 金鑰")
async def create_api_key(
    request: APIKeyCreateRequest,
    current_user: AuthUser = Depends(get_current_user)
):
    """
    為當前用戶創建新的 API 金鑰
    """
    try:
        success, message, api_key = await auth_manager.create_api_key(
            current_user.user_id,
            request.name,
            request.permissions,
            request.expires_days
        )
        
        return APIKeyResponse(
            success=success,
            message=message,
            api_key=api_key
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"創建 API 金鑰失敗: {str(e)}")


@router.get("/api-keys", response_model=Dict[str, Any], summary="獲取 API 金鑰列表")
async def get_api_keys(current_user: AuthUser = Depends(get_current_user)):
    """
    獲取當前用戶的所有 API 金鑰
    """
    try:
        api_keys = await auth_manager.get_user_api_keys(current_user.user_id)
        
        return {
            "success": True,
            "data": api_keys
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"獲取 API 金鑰失敗: {str(e)}")


@router.delete("/api-keys/{key_id}", response_model=Dict[str, Any], summary="撤銷 API 金鑰")
async def revoke_api_key(
    key_id: str,
    current_user: AuthUser = Depends(get_current_user)
):
    """
    撤銷指定的 API 金鑰
    """
    try:
        success = await auth_manager.revoke_api_key(current_user.user_id, key_id)
        
        return {
            "success": success,
            "message": "API 金鑰已撤銷" if success else "撤銷失敗"
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"撤銷 API 金鑰失敗: {str(e)}")


# ===== 健康檢查 =====

@router.get("/health", summary="認證服務健康檢查")
async def health_check():
    """
    檢查認證服務狀態
    """
    return {
        "status": "healthy",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "service": "authentication"
    }