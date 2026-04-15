"""
API Key 管理 API 模块

提供 API 密钥管理接口
"""

import logging
from flask import request, jsonify

from utils.auth import require_api_key
from utils.helpers import success_response, error_response

logger = logging.getLogger(__name__)

api_key_service = None


def init_api_key_service():
    """初始化 API Key 服务"""
    global api_key_service
    try:
        from api_key_service import get_api_key_service
        api_key_service = get_api_key_service()
        logger.info("API Key 服务初始化成功")
    except Exception as e:
        logger.warning(f"API Key 服务初始化失败：{e}")


def register_api_key_routes(app):
    """注册 API Key 管理相关路由"""
    
    @app.route('/api/api-key/generate', methods=['POST'])
    def generate_api_key():
        """生成新的 API Key"""
        try:
            data = request.json or {}
            name = data.get('name')
            description = data.get('description')
            
            if not api_key_service:
                return jsonify(error_response("API Key 服务未初始化", 503)), 503
            
            result = api_key_service.generate_key(name, description)
            
            if result.get('success'):
                logger.info(f"新建密钥：{result.get('key_id')}")
                return jsonify(success_response(
                    data=result.get('data'),
                    message=result.get('message', '密钥生成成功')
                ))
            else:
                return jsonify(error_response(
                    message=result.get('message', result.get('error', '密钥生成失败')),
                    code=result.get('code', 400)
                )), result.get('code', 400)
        except Exception as e:
            logger.error(f"生成密钥失败：{e}")
            return jsonify(error_response(str(e), 500)), 500
    
    @app.route('/api/api-key/list', methods=['GET'])
    def list_api_keys():
        """获取所有 API Key 列表"""
        try:
            if not api_key_service:
                return jsonify(error_response("API Key 服务未初始化", 503)), 503
            
            result = api_key_service.list_keys()
            if result.get('success'):
                return jsonify(success_response(
                    data=result.get('data'),
                    message=result.get('message', '密钥列表获取成功')
                ))
            else:
                return jsonify(error_response(
                    message=result.get('message', result.get('error', '获取失败')),
                    code=result.get('code', 500)
                )), result.get('code', 500)
        except Exception as e:
            logger.error(f"获取列表失败：{e}")
            return jsonify(error_response(str(e), 500)), 500
    
    @app.route('/api/api-key/revoke', methods=['POST'])
    def revoke_api_key():
        """撤销 API Key"""
        try:
            data = request.json or {}
            key_id = data.get('key_id')
            
            if not key_id:
                return jsonify(error_response("缺少 key_id 参数", 400)), 400
            
            if not api_key_service:
                return jsonify(error_response("API Key 服务未初始化", 503)), 503
            
            result = api_key_service.revoke_key(key_id)
            
            if result.get('success'):
                logger.info(f"撤销密钥：{key_id}")
                return jsonify(success_response(
                    data=result.get('data'),
                    message=result.get('message', '密钥已撤销')
                ))
            else:
                return jsonify(error_response(
                    message=result.get('message', result.get('error', '撤销失败')),
                    code=result.get('code', 400)
                )), result.get('code', 400)
        except Exception as e:
            logger.error(f"撤销失败：{e}")
            return jsonify(error_response(str(e), 500)), 500
    
    @app.route('/api/api-key/update', methods=['POST'])
    def update_api_key():
        """更新 API Key 信息"""
        try:
            data = request.json or {}
            key_id = data.get('key_id')
            name = data.get('name')
            description = data.get('description')
            
            if not key_id:
                return jsonify(error_response("缺少 key_id 参数", 400)), 400
            
            if not api_key_service:
                return jsonify(error_response("API Key 服务未初始化", 503)), 503
            
            result = api_key_service.update_key(key_id, name, description)
            
            if result.get('success'):
                logger.info(f"更新密钥：{key_id}")
                return jsonify(success_response(
                    data=result.get('data'),
                    message=result.get('message', '密钥已更新')
                ))
            else:
                return jsonify(error_response(
                    message=result.get('message', result.get('error', '更新失败')),
                    code=result.get('code', 400)
                )), result.get('code', 400)
        except Exception as e:
            logger.error(f"更新失败：{e}")
            return jsonify(error_response(str(e), 500)), 500
    
    @app.route('/api/api-key/verify', methods=['POST'])
    def verify_api_key():
        """验证 API Key"""
        try:
            data = request.json or {}
            key = data.get('key')
            
            if not key:
                return jsonify(error_response("缺少 key 参数", 400)), 400
            
            if not api_key_service:
                return jsonify(error_response("API Key 服务未初始化", 503)), 503
            
            result = api_key_service.verify_key(key)
            
            return jsonify(success_response(
                data=result.get('data'),
                message=result.get('message', '验证成功' if result.get('success') else '验证失败')
            ))
        except Exception as e:
            logger.error(f"验证失败：{e}")
            return jsonify(error_response(str(e), 500)), 500
    
    logger.info("API Key routes registered")
