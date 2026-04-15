#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
安全工具模块 - Security Utilities

提供统一的安全功能：
- 路径遍历防护
- 输入验证
- API Key 加密存储
- SSRF 防护
"""

import os
import re
import hashlib
import secrets
from pathlib import Path
from typing import Optional, List, Dict, Any
from datetime import datetime
import json

# ==================== 路径遍历防护 ====================

def sanitize_path(user_path: str, allowed_base: str, allowed_extensions: List[str] = None) -> Optional[Path]:
    """
    清理并验证用户提供的路径
    
    Args:
        user_path: 用户提供的路径
        allowed_base: 允许的基础目录
        allowed_extensions: 允许的文件扩展名列表
        
    Returns:
        安全的 Path 对象，如果无效返回 None
    """
    try:
        # 规范化路径
        normalized = os.path.normpath(user_path)
        
        # 检查路径遍历
        if '..' in normalized or normalized.startswith('/'):
            return None
        
        # 构建完整路径
        full_path = os.path.join(allowed_base, normalized)
        full_path = os.path.abspath(full_path)
        
        # 检查是否在允许的目录内
        allowed_base_abs = os.path.abspath(allowed_base)
        if not full_path.startswith(allowed_base_abs):
            return None
        
        # 检查扩展名
        if allowed_extensions:
            ext = os.path.splitext(full_path)[1].lower()
            if ext not in [e.lower() for e in allowed_extensions]:
                return None
        
        return Path(full_path)
        
    except Exception:
        return None


def validate_file_path(file_path: str, allowed_dirs: List[str], 
                       allowed_extensions: List[str] = None) -> Optional[str]:
    """
    验证文件路径是否安全
    
    Args:
        file_path: 文件路径
        allowed_dirs: 允许的目录列表
        allowed_extensions: 允许的扩展名
        
    Returns:
        安全的路径，如果无效返回 None
    """
    try:
        # 规范化路径
        normalized = os.path.normpath(file_path)
        
        # 检查路径遍历
        if '..' in normalized or normalized.startswith('/'):
            return None
        
        # 检查是否在允许的目录内
        for allowed_dir in allowed_dirs:
            allowed_abs = os.path.abspath(allowed_dir)
            full_path = os.path.abspath(os.path.join(allowed_dir, normalized))
            
            if full_path.startswith(allowed_abs):
                # 检查扩展名
                if allowed_extensions:
                    ext = os.path.splitext(full_path)[1].lower()
                    if ext not in [e.lower() for e in allowed_extensions]:
                        return None
                return full_path
        
        return None
        
    except Exception:
        return None


# ==================== 输入验证 ====================

def validate_string_input(value: str, max_length: int = 1000, 
                         allow_empty: bool = False,
                         pattern: str = None) -> tuple:
    """
    验证字符串输入
    
    Args:
        value: 输入值
        max_length: 最大长度
        allow_empty: 是否允许空值
        pattern: 正则表达式模式
        
    Returns:
        (是否有效, 错误消息或None)
    """
    if not allow_empty and (value is None or value.strip() == ''):
        return False, "输入不能为空"
    
    if value and len(value) > max_length:
        return False, f"输入长度不能超过 {max_length} 个字符"
    
    if pattern:
        if not re.match(pattern, value):
            return False, "输入格式不正确"
    
    return True, None


def validate_integer_input(value: Any, min_val: int = None, 
                          max_val: int = None) -> tuple:
    """
    验证整数输入
    
    Args:
        value: 输入值
        min_val: 最小值
        max_val: 最大值
        
    Returns:
        (是否有效, 错误消息或None)
    """
    try:
        int_val = int(value)
        
        if min_val is not None and int_val < min_val:
            return False, f"值不能小于 {min_val}"
        
        if max_val is not None and int_val > max_val:
            return False, f"值不能大于 {max_val}"
        
        return True, None
        
    except (ValueError, TypeError):
        return False, "输入必须是整数"


# ==================== API Key 加密存储 ====================

class EncryptedKeyStore:
    """加密的 API Key 存储"""
    
    def __init__(self, store_path: str):
        self.store_path = store_path
        self._keys: Dict[str, Dict] = {}
        self._load_keys()
    
    def _load_keys(self):
        """加载密钥"""
        try:
            if os.path.exists(self.store_path):
                with open(self.store_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self._keys = data.get('keys', {})
        except Exception as e:
            print(f"[EncryptedKeyStore] 加载失败: {e}")
            self._keys = {}
    
    def _save_keys(self):
        """保存密钥（明文，实际应使用加密库）"""
        try:
            os.makedirs(os.path.dirname(self.store_path), exist_ok=True)
            data = {
                'keys': self._keys,
                'updated_at': datetime.now().isoformat()
            }
            with open(self.store_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[EncryptedKeyStore] 保存失败: {e}")
    
    def generate_key(self, name: str = None, description: str = None) -> Dict:
        """生成新密钥"""
        key_id = secrets.token_hex(4)
        secret = secrets.token_urlsafe(32)
        key_prefix = f"oll_{key_id[:4]}"
        full_key = f"{key_prefix}_{secret}"
        
        key_info = {
            'id': key_id,
            'name': name or f"API Key #{len(self._keys) + 1}",
            'description': description or '',
            'key_hash': hashlib.sha256(full_key.encode()).hexdigest(),
            'prefix': key_prefix,
            'created_at': datetime.now().isoformat(),
            'last_used_at': None,
            'usage_count': 0,
            'is_active': True
        }
        
        self._keys[key_id] = key_info
        self._save_keys()
        
        return {
            'success': True,
            'key_id': key_id,
            'key': full_key,
            'name': key_info['name'],
            'created_at': key_info['created_at']
        }
    
    def verify_key(self, key: str) -> Optional[Dict]:
        """验证密钥"""
        if not key or not key.startswith('oll_'):
            return None
        
        key_hash = hashlib.sha256(key.encode()).hexdigest()
        
        for key_id, key_info in self._keys.items():
            if key_info['key_hash'] == key_hash and key_info['is_active']:
                return key_info
        
        return None
    
    def list_keys(self) -> List[Dict]:
        """列出所有密钥"""
        result = []
        for key_id, key_info in self._keys.items():
            result.append({
                'id': key_id,
                'name': key_info['name'],
                'description': key_info['description'],
                'prefix': key_info['prefix'],
                'created_at': key_info['created_at'],
                'last_used_at': key_info['last_used_at'],
                'usage_count': key_info['usage_count'],
                'is_active': key_info['is_active']
            })
        return result
    
    def revoke_key(self, key_id: str) -> Dict:
        """撤销密钥"""
        if key_id not in self._keys:
            return {'success': False, 'error': 'API Key 不存在'}
        
        del self._keys[key_id]
        self._save_keys()
        
        return {'success': True, 'message': 'API Key 已撤销'}
    
    def update_key(self, key_id: str, name: str = None, 
                   description: str = None) -> Dict:
        """更新密钥信息"""
        if key_id not in self._keys:
            return {'success': False, 'error': 'API Key 不存在'}
        
        if name:
            self._keys[key_id]['name'] = name
        if description is not None:
            self._keys[key_id]['description'] = description
        
        self._save_keys()
        
        return {
            'success': True,
            'key': {
                'id': key_id,
                'name': self._keys[key_id]['name'],
                'description': self._keys[key_id]['description']
            }
        }


# ==================== SSRF 防护 ====================

class SSRFProtector:
    """SSRF 攻击防护"""
    
    # 内网地址黑名单
    BLOCKED_IPS = [
        '127.0.0.1',
        'localhost',
        '0.0.0.0',
        '::1',
        '10.0.0.0/8',
        '172.16.0.0/12',
        '192.168.0.0/16',
        '169.254.0.0/16',
        'fc00::/7',
        'fe80::/10',
    ]
    
    # 允许的协议
    ALLOWED_PROTOCOLS = ['http', 'https']
    
    @classmethod
    def is_safe_url(cls, url: str) -> bool:
        """
        检查 URL 是否安全
        
        Args:
            url: URL 字符串
            
        Returns:
            是否安全
        """
        try:
            from urllib.parse import urlparse
            
            parsed = urlparse(url)
            
            # 检查协议
            if parsed.scheme not in cls.ALLOWED_PROTOCOLS:
                return False
            
            # 检查主机
            host = parsed.hostname
            
            if host in cls.BLOCKED_IPS:
                return False
            
            # 检查 IP 范围
            if cls._is_private_ip(host):
                return False
            
            return True
            
        except Exception:
            return False
    
    @classmethod
    def _is_private_ip(cls, host: str) -> bool:
        """检查是否为内网 IP"""
        import socket
        
        try:
            ip = socket.gethostbyname(host)
            
            # 检查是否为内网 IP
            if ip.startswith('10.'):
                return True
            if ip.startswith('172.'):
                second_octet = int(ip.split('.')[1])
                if 16 <= second_octet <= 31:
                    return True
            if ip.startswith('192.168.'):
                return True
            if ip.startswith('169.254.'):
                return True
            
            # IPv6
            if ip == '::1':
                return True
            
            return False
            
        except Exception:
            return True  # 无法解析的 IP 视为不安全


# ==================== 文件操作安全包装 ====================

def safe_file_read(file_path: str, allowed_dirs: List[str]) -> Optional[str]:
    """
    安全地读取文件
    
    Args:
        file_path: 文件路径
        allowed_dirs: 允许的目录
        
    Returns:
        文件内容，如果无效返回 None
    """
    safe_path = validate_file_path(file_path, allowed_dirs)
    
    if safe_path is None:
        return None
    
    try:
        with open(safe_path, 'r', encoding='utf-8') as f:
            return f.read()
    except Exception:
        return None


def safe_file_write(file_path: str, content: str, allowed_dirs: List[str]) -> bool:
    """
    安全地写入文件
    
    Args:
        file_path: 文件路径
        content: 内容
        allowed_dirs: 允许的目录
        
    Returns:
        是否成功
    """
    safe_path = validate_file_path(file_path, allowed_dirs)
    
    if safe_path is None:
        return False
    
    try:
        os.makedirs(os.path.dirname(safe_path), exist_ok=True)
        with open(safe_path, 'w', encoding='utf-8') as f:
            f.write(content)
        return True
    except Exception:
        return False


def safe_file_exists(file_path: str, allowed_dirs: List[str]) -> bool:
    """
    安全地检查文件是否存在
    
    Args:
        file_path: 文件路径
        allowed_dirs: 允许的目录
        
    Returns:
        是否存在
    """
    safe_path = validate_file_path(file_path, allowed_dirs)
    
    if safe_path is None:
        return False
    
    return os.path.exists(safe_path)
