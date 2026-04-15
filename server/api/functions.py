"""
函数调用 API 模块

提供函数调用相关接口
"""

import logging
from flask import request, jsonify

from utils.auth import require_api_key
from utils.helpers import success_response, error_response

logger = logging.getLogger(__name__)

function_registry = None


def init_functions_service():
    """初始化函数调用服务"""
    global function_registry
    try:
        from function_engine import create_function_registry
        function_registry = create_function_registry()
        logger.info("函数调用服务初始化成功")
    except Exception as e:
        logger.warning(f"函数调用服务初始化失败: {e}")


def register_functions_routes(app):
    """注册函数调用相关路由"""
    
    @app.route('/api/functions/list', methods=['GET'])
    def list_functions_api():
        """获取可用函数列表"""
        try:
            from function_engine import list_functions
            functions = list_functions(enabled_only=True)
            return jsonify(success_response(data={
                'functions': functions,
                'count': len(functions)
            }))
        except Exception as e:
            logger.error(f"获取函数列表失败: {e}")
            return jsonify(error_response(str(e), 500)), 500
    
    @app.route('/api/functions/execute', methods=['POST'])
    @require_api_key
    def execute_function_api():
        """执行函数调用"""
        try:
            data = request.json or {}
            
            function_name = data.get('function', '')
            arguments = data.get('arguments', {})
            
            if not function_name:
                return jsonify(error_response("缺少 function 参数", 400)), 400
            
            from function_engine import execute_function, function_registry
            
            func_def = function_registry.get(function_name)
            require_confirmation = data.get('require_confirmation', False)
            
            if func_def and func_def.require_confirmation and not require_confirmation:
                return jsonify(error_response(
                    message=f'函数 "{function_name}" 需要用户确认才能执行',
                    code=403,
                    data={
                        'require_confirmation': True,
                        'function': function_name,
                        'description': func_def.description
                    }
                )), 403
            
            result = execute_function(function_name, arguments)
            if result.get('success'):
                return jsonify(success_response(
                    data=result.get('data'),
                    message=result.get('message', '函数执行成功')
                ))
            else:
                return jsonify(error_response(
                    message=result.get('message', result.get('error', '函数执行失败')),
                    code=result.get('code', 500)
                )), result.get('code', 500)
        except Exception as e:
            logger.error(f"函数执行失败: {e}")
            return jsonify(error_response(str(e), 500)), 500
    
    @app.route('/api/functions/history', methods=['GET'])
    @require_api_key
    def function_history_api():
        """获取函数执行历史"""
        try:
            from function_engine import get_execution_history
            limit = request.args.get('limit', 50, type=int)
            history = get_execution_history(limit)
            return jsonify(success_response(data={
                'history': history,
                'count': len(history)
            }))
        except Exception as e:
            logger.error(f"获取历史失败: {e}")
            return jsonify(error_response(str(e), 500)), 500

    @app.route('/api/assistant/computer', methods=['POST'])
    def computer_assist():
        """电脑协助功能（占位符实现）"""
        try:
            data = request.get_json() or {}
            instruction = data.get('instruction', '')
            safe_mode = data.get('safe_mode', True)
            
            return jsonify(success_response(data={
                "message": "电脑协助功能暂未启用",
                "instruction": instruction,
                "safe_mode": safe_mode,
                "control_session": None,
                "operation_ticket": [],
                "steps": []
            }, message="电脑协助功能需要额外配置才能使用"))
        except Exception as e:
            logger.error(f"电脑协助请求失败: {e}")
            return jsonify(error_response(str(e), 500)), 500

    @app.route('/api/assistant/computer/execute', methods=['POST'])
    def computer_assist_execute():
        """电脑协助执行（占位符实现）"""
        try:
            data = request.get_json() or {}
            session_id = data.get('session_id', '')
            
            return jsonify(success_response(data={
                "message": "电脑协助执行功能暂未启用",
                "session_id": session_id,
                "executed": False
            }, message="电脑协助功能需要额外配置才能使用"))
        except Exception as e:
            logger.error(f"电脑协助执行失败: {e}")
            return jsonify(error_response(str(e), 500)), 500

    logger.info("✓ 函数调用 API 路由已注册")
