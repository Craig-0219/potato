# bot/api/routes/oauth.py
"""
Discord OAuth 認證 API 端點
提供 Discord 帳號登入和權限管理
"""

from fastapi import APIRouter, HTTPException, Query, Request, Response
from fastapi.responses import RedirectResponse
import httpx
import jwt
import secrets
from datetime import datetime, timedelta
from typing import Optional
import os

from ..models import BaseResponse
from shared.logger import logger
from shared.config import DISCORD_TOKEN

router = APIRouter()

# Discord OAuth 設定
DISCORD_CLIENT_ID = os.getenv('DISCORD_CLIENT_ID', '1392536746922741852')  # 您的 Bot Client ID
DISCORD_CLIENT_SECRET = os.getenv('DISCORD_CLIENT_SECRET', '')  # 需要設置
DISCORD_REDIRECT_URI = os.getenv('DISCORD_REDIRECT_URI', 'http://36.50.249.118:3000/auth/discord/callback')
DISCORD_GUILD_ID = os.getenv('DISCORD_GUILD_ID', '1392536804355014676')  # 您的伺服器 ID

# JWT 設定
JWT_SECRET = os.getenv('JWT_SECRET', secrets.token_urlsafe(32))
JWT_ALGORITHM = 'HS256'
JWT_EXPIRATION_HOURS = 24

# Discord API URLs
DISCORD_API_BASE = 'https://discord.com/api/v10'
DISCORD_OAUTH_BASE = 'https://discord.com/oauth2'

@router.get("/discord/login", summary="開始 Discord OAuth 登入流程")
async def discord_login(request: Request):
    """
    重定向到 Discord OAuth 頁面
    """
    try:
        # 生成 state 參數防止 CSRF 攻擊
        state = secrets.token_urlsafe(32)
        
        # 構建 Discord OAuth URL
        oauth_params = {
            'client_id': DISCORD_CLIENT_ID,
            'redirect_uri': DISCORD_REDIRECT_URI,
            'response_type': 'code',
            'scope': 'identify guilds.members.read',
            'state': state
        }
        
        # 儲存 state 到 session (簡化版本)
        oauth_url = f"{DISCORD_OAUTH_BASE}/authorize?" + "&".join([f"{k}={v}" for k, v in oauth_params.items()])
        
        logger.info(f"Discord OAuth 登入開始，重定向到: {oauth_url}")
        
        return RedirectResponse(url=oauth_url)
        
    except Exception as e:
        logger.error(f"Discord OAuth 登入錯誤: {e}")
        raise HTTPException(status_code=500, detail="Discord 登入失敗")

@router.get("/discord/callback", summary="Discord OAuth 回調處理")
async def discord_callback(
    code: str = Query(..., description="Discord 授權碼"),
    state: Optional[str] = Query(None, description="CSRF 保護狀態"),
    error: Optional[str] = Query(None, description="OAuth 錯誤")
):
    """
    處理 Discord OAuth 回調
    """
    try:
        if error:
            logger.error(f"Discord OAuth 錯誤: {error}")
            # 重定向到前端錯誤頁面
            return RedirectResponse(url=f"http://36.50.249.118:3000/auth/error?error={error}")
        
        if not code:
            raise HTTPException(status_code=400, detail="缺少授權碼")
        
        # 交換 access token
        token_data = await exchange_code_for_token(code)
        if not token_data:
            raise HTTPException(status_code=400, detail="無法獲取 access token")
        
        # 獲取用戶資訊
        user_info = await get_discord_user_info(token_data['access_token'])
        if not user_info:
            raise HTTPException(status_code=400, detail="無法獲取用戶資訊")
        
        # 檢查用戶權限
        user_permissions = await check_user_permissions(token_data['access_token'], user_info['id'])
        
        # 生成 JWT token
        jwt_token = generate_jwt_token(user_info, user_permissions)
        
        # 重定向到前端並帶上 token
        redirect_url = f"http://36.50.249.118:3000/auth/success?token={jwt_token}"
        return RedirectResponse(url=redirect_url)
        
    except Exception as e:
        logger.error(f"Discord OAuth 回調錯誤: {e}")
        return RedirectResponse(url=f"http://36.50.249.118:3000/auth/error?error=callback_failed")

async def exchange_code_for_token(code: str) -> Optional[dict]:
    """
    交換授權碼獲取 access token
    """
    try:
        data = {
            'client_id': DISCORD_CLIENT_ID,
            'client_secret': DISCORD_CLIENT_SECRET,
            'grant_type': 'authorization_code',
            'code': code,
            'redirect_uri': DISCORD_REDIRECT_URI
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{DISCORD_OAUTH_BASE}/token",
                data=data,
                headers={'Content-Type': 'application/x-www-form-urlencoded'}
            )
            
            if response.status_code == 200:
                return response.json()
            else:
                logger.error(f"Token 交換失敗: {response.status_code} - {response.text}")
                return None
                
    except Exception as e:
        logger.error(f"Token 交換錯誤: {e}")
        return None

async def get_discord_user_info(access_token: str) -> Optional[dict]:
    """
    獲取 Discord 用戶資訊
    """
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{DISCORD_API_BASE}/users/@me",
                headers={'Authorization': f'Bearer {access_token}'}
            )
            
            if response.status_code == 200:
                return response.json()
            else:
                logger.error(f"獲取用戶資訊失敗: {response.status_code}")
                return None
                
    except Exception as e:
        logger.error(f"獲取用戶資訊錯誤: {e}")
        return None

async def check_user_permissions(access_token: str, user_id: str) -> dict:
    """
    檢查用戶在伺服器中的權限
    """
    try:
        # 獲取用戶在指定伺服器的成員資訊
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{DISCORD_API_BASE}/users/@me/guilds/{DISCORD_GUILD_ID}/member",
                headers={'Authorization': f'Bearer {access_token}'}
            )
            
            if response.status_code == 200:
                member_data = response.json()
                roles = member_data.get('roles', [])
                
                # 根據角色 ID 判斷權限（需要根據您的伺服器設置）
                permissions = {
                    'is_admin': False,
                    'is_staff': False,
                    'is_member': True,
                    'roles': roles
                }
                
                # 檢查管理員權限（您需要設置實際的角色 ID）
                admin_role_ids = [
                    '1392536804355014681',  # 管理員角色 ID - 請替換為實際 ID
                    '1392536804355014682',  # 版主角色 ID - 請替換為實際 ID
                ]
                
                staff_role_ids = [
                    '1392536804355014683',  # 員工角色 ID - 請替換為實際 ID
                ]
                
                # 檢查是否有管理員角色
                if any(role_id in admin_role_ids for role_id in roles):
                    permissions['is_admin'] = True
                    permissions['is_staff'] = True
                elif any(role_id in staff_role_ids for role_id in roles):
                    permissions['is_staff'] = True
                
                return permissions
            else:
                logger.warning(f"用戶不在指定伺服器中: {response.status_code}")
                return {'is_admin': False, 'is_staff': False, 'is_member': False, 'roles': []}
                
    except Exception as e:
        logger.error(f"檢查用戶權限錯誤: {e}")
        return {'is_admin': False, 'is_staff': False, 'is_member': False, 'roles': []}

def generate_jwt_token(user_info: dict, permissions: dict) -> str:
    """
    生成 JWT token
    """
    try:
        payload = {
            'user_id': user_info['id'],
            'username': user_info['username'],
            'discriminator': user_info.get('discriminator', '0'),
            'avatar': user_info.get('avatar'),
            'email': user_info.get('email'),
            'permissions': permissions,
            'exp': datetime.utcnow() + timedelta(hours=JWT_EXPIRATION_HOURS),
            'iat': datetime.utcnow(),
            'iss': 'potato-bot'
        }
        
        token = jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)
        return token
        
    except Exception as e:
        logger.error(f"生成 JWT token 錯誤: {e}")
        raise

@router.get("/verify", summary="驗證 JWT token")
async def verify_token(request: Request):
    """
    驗證 JWT token 有效性
    """
    try:
        # 從 Authorization header 獲取 token
        auth_header = request.headers.get('Authorization', '')
        if not auth_header.startswith('Bearer '):
            raise HTTPException(status_code=401, detail="缺少 Authorization header")
        
        token = auth_header.split(' ')[1]
        
        # 驗證 token
        try:
            payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
            return {
                'success': True,
                'user': {
                    'id': payload['user_id'],
                    'username': payload['username'],
                    'avatar': payload.get('avatar'),
                    'permissions': payload['permissions']
                }
            }
        except jwt.ExpiredSignatureError:
            raise HTTPException(status_code=401, detail="Token 已過期")
        except jwt.InvalidTokenError:
            raise HTTPException(status_code=401, detail="無效的 token")
            
    except Exception as e:
        logger.error(f"驗證 token 錯誤: {e}")
        raise HTTPException(status_code=401, detail="Token 驗證失敗")

@router.post("/logout", summary="登出")
async def logout():
    """
    登出（前端清除 token）
    """
    return {
        'success': True,
        'message': '登出成功'
    }

# 用於測試的簡化登入端點（開發環境使用）
@router.post("/test-login", summary="測試登入（開發環境）")
async def test_login(username: str = "admin", role: str = "admin"):
    """
    測試用的簡化登入，僅在開發環境使用
    """
    if os.getenv('NODE_ENV') == 'production':
        raise HTTPException(status_code=403, detail="生產環境不可用")
    
    fake_user_info = {
        'id': '123456789',
        'username': username,
        'discriminator': '0001',
        'avatar': None,
        'email': f'{username}@test.com'
    }
    
    fake_permissions = {
        'is_admin': role == 'admin',
        'is_staff': role in ['admin', 'staff'],
        'is_member': True,
        'roles': ['test_role']
    }
    
    token = generate_jwt_token(fake_user_info, fake_permissions)
    
    return {
        'success': True,
        'token': token,
        'user': fake_user_info
    }