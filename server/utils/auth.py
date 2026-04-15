"""
认证模块

提供 API 密钥认证和速率限制功能
"""

import os
import time
import logging
from functools import wraps
from flask import request, jsonify

logger = logging.getLogger(__name__)

rate_limit_store = {}
RATE_LIMIT_REQUESTS = 60
RATE_LIMIT_WINDOW = 60

_api_key_service = None


def _get_api_key_service():
    """获取 API Key 服务实例"""
    global _api_key_service
    if _api_key_service is None:
        try:
            from api_key_service import get_api_key_service
            _api_key_service = get_api_key_service()
        except Exception as e:
            logger.debug(f"API Key 服务初始化失败: {e}")
    return _api_key_service


def check_rate_limit(ip: str) -> bool:
    """检查请求速率限制"""
    current_time = time.time()
    if ip not in rate_limit_store:
        rate_limit_store[ip] = []
    
    rate_limit_store[ip] = [
        t for t in rate_limit_store[ip] 
        if current_time - t < RATE_LIMIT_WINDOW
    ]
    
    if len(rate_limit_store[ip]) >= RATE_LIMIT_REQUESTS:
        return False
    
    rate_limit_store[ip].append(current_time)
    return True


def require_api_key(f):
    """API 密钥认证装饰器"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        client_ip = request.remote_addr
        
        if request.headers.get('X-Internal-Call') == 'true' and client_ip in ('127.0.0.1', '::1'):
            return f(*args, **kwargs)
        
        if not check_rate_limit(client_ip):
            return jsonify({
                "success": False,
                "error": "请求过于频繁，请稍后再试",
                "code": "RATE_LIMIT_EXCEEDED"
            }), 429
        
        api_key_service = _get_api_key_service()
        if api_key_service is None:
            return f(*args, **kwargs)
        
        if not api_key_service.keys:
            return f(*args, **kwargs)
        
        client_api_key = None
        
        auth_header = request.headers.get('Authorization', '')
        if auth_header.startswith('Bearer '):
            client_api_key = auth_header[7:]
        elif auth_header.startswith('ApiKey '):
            client_api_key = auth_header[7:]
        
        if not client_api_key:
            client_api_key = request.args.get('api_key')
        if not client_api_key:
            client_api_key = request.form.get('api_key')
        if not client_api_key and request.is_json:
            client_api_key = request.json.get('api_key') if request.json else None
        
        if not client_api_key:
            logger.warning(f"缺少 API 密钥 from {client_ip}")
            return jsonify({
                "success": False,
                "error": "缺少 API 密钥",
                "code": "MISSING_API_KEY"
            }), 401
        
        key_info = api_key_service.verify_key(client_api_key)
        if not key_info:
            logger.warning(f"无效的 API 密钥访问尝试 from {client_ip}")
            return jsonify({
                "success": False,
                "error": "无效的 API 密钥",
                "code": "INVALID_API_KEY"
            }), 401
        
        return f(*args, **kwargs)
    return decorated_function
