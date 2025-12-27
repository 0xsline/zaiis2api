import logging
import time
import json
from datetime import datetime, timedelta
from .extensions import db
from .models import SystemConfig, Token, RequestLog
from .zai_token import DiscordOAuthHandler
import jwt # pyjwt
from flask import current_app

logger = logging.getLogger(__name__)

def get_zai_handler():
    # Assume we are in app context so we can query SystemConfig
    config = SystemConfig.query.first()
    handler = DiscordOAuthHandler()
    if config and config.proxy_enabled and config.proxy_url:
        handler.session.proxies = {
            'http': config.proxy_url,
            'https': config.proxy_url
        }
    return handler

def update_token_info(token_id, use_oauth=False):
    # Caller must ensure app context
    token = db.session.get(Token, token_id)
    if not token:
        return False, "Token not found"

    handler = get_zai_handler()
    
    # 如果使用 OAuth 登录
    if use_oauth:
        print(f"[*] Token {token_id} 使用 OAuth 登录更新...")
        result = handler.oauth_login_with_browser()
        source = result.get('source', 'oauth')
    else:
        # 使用后端登录
        result = handler.backend_login(token.discord_token)
        source = 'backend'
    
    if 'error' in result:
        token.error_count += 1
        token.remark = f"Refresh failed: {result['error']}"
        db.session.commit()
        return False, result['error']

    # Save cookies
    cookies = handler.session.cookies.get_dict()
    token.cookies_json = json.dumps(cookies)

    at = result.get('token')
    user_info = result.get('user_info', {})
    
    if at == 'SESSION_AUTH':
         token.email = user_info.get('email') or user_info.get('name') or token.email
         token.is_active = True
         token.error_count = 0
         token.zai_token = "SESSION_AUTH_COOKIE"
         token.remark = f"Updated via {source} (Session Auth)"
         # For SESSION_AUTH, set expiry based on system config
         config = SystemConfig.query.first()
         refresh_interval = config.token_refresh_interval if config else 3600
         token.at_expires = datetime.now() + timedelta(seconds=refresh_interval)
         db.session.commit()
         return True, f"Session Auth Active ({source})"
    
    token.zai_token = at
    token.error_count = 0
    token.remark = f"Updated via {source}"
    
    # Get system config for fallback expiry
    config = SystemConfig.query.first()
    refresh_interval = config.token_refresh_interval if config else 3600
    now = datetime.now()
    desired_exp = now + timedelta(seconds=refresh_interval)
    jwt_exp_dt = None
    
    # Decode JWT to get expiry and email
    try:
        decoded = jwt.decode(at, options={"verify_signature": False})
        if 'exp' in decoded:
            jwt_exp_dt = datetime.fromtimestamp(decoded['exp'])
        if 'email' in decoded:
            token.email = decoded['email']
    except Exception as e:
        logger.warning(f"Failed to decode JWT: {e}")
    
    # Use the earlier of JWT exp and configured refresh interval to keep UI倒计时一致
    token.at_expires = min(jwt_exp_dt, desired_exp) if jwt_exp_dt else desired_exp
    
    db.session.commit()
    return True, f"Success ({source})"

def create_or_update_token_from_oauth():
    """通过 OAuth 登录创建或更新 Token"""
    handler = get_zai_handler()
    
    # 执行 OAuth 登录
    result = handler.oauth_login_with_browser()
    
    if 'error' in result:
        return {'success': False, 'error': result['error']}
    
    # 获取 token 信息
    zai_token = result.get('token')
    user_info = result.get('user_info', {})
    source = result.get('source', 'unknown')
    
    if not zai_token:
        return {'success': False, 'error': '未能获取到有效的 Token'}
    
    # 解析 JWT 获取用户信息
    email = None
    at_expires = None
    
    if zai_token != 'SESSION_AUTH':
        try:
            decoded = jwt.decode(zai_token, options={"verify_signature": False})
            email = decoded.get('email')
            if 'exp' in decoded:
                at_expires = datetime.fromtimestamp(decoded['exp'])
        except Exception as e:
            logger.warning(f"Failed to decode JWT: {e}")
    else:
        # Session auth 情况
        email = user_info.get('email') or user_info.get('name')
    
    # 如果没有 email，从 user_info 获取
    if not email and user_info:
        email = user_info.get('email') or user_info.get('name')
    
    if not email:
        email = f"oauth_user_{int(time.time())}"
    
    # 查找或创建 Token
    token = Token.query.filter_by(email=email).first()
    
    if not token:
        # 创建新 token
        token = Token(
            email=email,
            discord_token="OAUTH_LOGIN",  # 占位符
            is_active=True
        )
        db.session.add(token)
    
    # 更新 token 信息
    token.zai_token = zai_token if zai_token != 'SESSION_AUTH' else "SESSION_AUTH_COOKIE"
    token.is_active = True
    token.error_count = 0
    token.remark = f"Updated via OAuth login ({source})"
    
    # 设置过期时间（与配置刷新间隔对齐）
    config = SystemConfig.query.first()
    refresh_interval = config.token_refresh_interval if config else 3600
    now = datetime.now()
    desired_exp = now + timedelta(seconds=refresh_interval)
    token.at_expires = min(at_expires, desired_exp) if at_expires else desired_exp
    
    db.session.commit()
    
    return {
        'success': True,
        'token': token.zai_token,
        'email': token.email,
        'source': source,
        'expires': token.at_expires.isoformat() if token.at_expires else None
    }

def refresh_all_tokens(force=False):
    # Caller must ensure app context
    tokens = Token.query.filter_by(is_active=True).all()
    for token in tokens:
        if not force and token.at_expires and token.at_expires > datetime.now() + timedelta(minutes=10):
            continue
        
        try:
            success, msg = update_token_info(token.id)
            logger.info(f"Refreshed token {token.id}: {msg}")
        except Exception as e:
            logger.error(f"Error refreshing token {token.id}: {e}")
