# -*- coding: utf-8 -*-
"""
API Key 管理服务
提供 API Key 的生成、验证、列表和撤销功能
"""

import os
import json
import uuid
import hashlib
import secrets
import time
from datetime import datetime
from typing import Optional, Dict, List

API_KEYS_FILE = os.path.join(os.path.dirname(__file__), 'data', 'api_keys.json')


class APIKeyService:
    """API Key 管理服务类"""

    def __init__(self):
        self.keys = {}
        self._load_keys()

    def _load_keys(self):
        """从文件加载 API Keys"""
        try:
            os.makedirs(os.path.dirname(API_KEYS_FILE), exist_ok=True)
            if os.path.exists(API_KEYS_FILE):
                with open(API_KEYS_FILE, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.keys = {k: v for k, v in data.get('keys', {}).items()}
            else:
                self.keys = {}
        except Exception as e:
            print(f"[API Key] 加载密钥文件失败: {e}")
            self.keys = {}

    def _save_keys(self):
        """保存 API Keys 到文件"""
        try:
            os.makedirs(os.path.dirname(API_KEYS_FILE), exist_ok=True)
            data = {
                'keys': self.keys,
                'updated_at': datetime.now().isoformat()
            }
            with open(API_KEYS_FILE, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[API Key] 保存密钥文件失败: {e}")

    def generate_key(self, name: str = None, description: str = None) -> Dict:
        """
        生成新的 API Key

        Args:
            name: Key 名称
            description: Key 描述

        Returns:
            Dict: 包含 key_info 和 secret
        """
        key_id = str(uuid.uuid4())[:8]
        secret = secrets.token_urlsafe(32)
        key_prefix = f"oll_{key_id[:4]}"
        full_key = f"{key_prefix}_{secret}"

        key_info = {
            'id': key_id,
            'name': name or f"API Key #{len(self.keys) + 1}",
            'description': description or '',
            'key_hash': self._hash_key(full_key),
            'prefix': key_prefix,
            'created_at': datetime.now().isoformat(),
            'last_used_at': None,
            'usage_count': 0,
            'is_active': True
        }

        self.keys[key_id] = key_info
        self._save_keys()

        return {
            'success': True,
            'message': 'API Key 生成成功',
            'code': 200,
            'data': {
                'id': key_id,
                'key': full_key,
                'name': key_info['name'],
                'created_at': key_info['created_at']
            }
        }

    def _hash_key(self, key: str) -> str:
        """对 API Key 进行哈希处理（用于存储）"""
        return hashlib.sha256(key.encode()).hexdigest()

    def verify_key(self, key: str) -> Optional[Dict]:
        """
        验证 API Key 是否有效

        Args:
            key: 完整的 API Key

        Returns:
            Dict: Key 信息，如果无效返回 None
        """
        if not key or not key.startswith('oll_'):
            return None

        key_hash = self._hash_key(key)

        for key_id, key_info in self.keys.items():
            if key_info['key_hash'] == key_hash and key_info['is_active']:
                return key_info

        return None

    def list_keys(self) -> List[Dict]:
        """
        获取所有 API Key 列表

        Returns:
            List: API Key 列表（不包含完整 Key）
        """
        result = []
        for key_id, key_info in self.keys.items():
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
        return {
            'success': True,
            'message': 'API Key 列表获取成功',
            'code': 200,
            'data': result
        }

    def revoke_key(self, key_id: str) -> Dict:
        """
        撤销（删除）API Key

        Args:
            key_id: Key ID

        Returns:
            Dict: 操作结果
        """
        if key_id not in self.keys:
            return {
                'success': False,
                'message': 'API Key 不存在',
                'code': 404,
                'data': None
            }

        del self.keys[key_id]
        self._save_keys()

        return {
            'success': True,
            'message': 'API Key 已撤销',
            'code': 200,
            'data': {'id': key_id}
        }

    def update_key(self, key_id: str, name: str = None, description: str = None) -> Dict:
        """
        更新 API Key 信息

        Args:
            key_id: Key ID
            name: 新名称
            description: 新描述
        Returns:
            Dict: 更新后的 Key 信息
        """
        if key_id not in self.keys:
            return {
                'success': False,
                'message': 'API Key 不存在',
                'code': 404,
                'data': None
            }

        if name:
            self.keys[key_id]['name'] = name
        if description is not None:
            self.keys[key_id]['description'] = description

        self._save_keys()

        return {
            'success': True,
            'message': 'API Key 更新成功',
            'code': 200,
            'data': {
                'id': key_id,
                'name': self.keys[key_id]['name'],
                'description': self.keys[key_id]['description']
            }
        }

    def use_key(self, key_id: str):
        """记录 Key 使用"""
        if key_id in self.keys:
            self.keys[key_id]['last_used_at'] = datetime.now().isoformat()
            self.keys[key_id]['usage_count'] += 1
            self._save_keys()


_api_key_service = None


def get_api_key_service() -> APIKeyService:
    """获取 API Key 服务单例"""
    global _api_key_service
    if _api_key_service is None:
        _api_key_service = APIKeyService()
    return _api_key_service

