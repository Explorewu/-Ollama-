"""
摘要 API 模块

提供对话摘要相关接口
"""

import logging
from flask import request, jsonify

from utils.helpers import success_response, error_response

logger = logging.getLogger(__name__)

summary_service = None


def init_summary_service(ollama_url):
    """初始化摘要服务"""
    global summary_service
    try:
        from summary_service import get_summary_service, SummaryLevel
        summary_service = get_summary_service(ollama_url)
        logger.info("摘要服务初始化成功")
    except Exception as e:
        logger.warning(f"摘要服务初始化失败：{e}")


def register_summary_routes(app):
    """注册摘要相关路由"""
    
    @app.route('/api/conversation', methods=['POST'])
    def create_conversation():
        """创建新对话"""
        try:
            data = request.json
            title = data.get('title', '新对话')
            
            if not summary_service:
                return jsonify(error_response("摘要服务未初始化", 503)), 503
            
            conversation = summary_service.create_conversation(title)
            
            return jsonify(success_response(data={
                "id": conversation.id,
                "title": conversation.title,
                "created_at": conversation.created_at
            }))
        except Exception as e:
            logger.error(f"创建对话失败：{e}")
            return jsonify(error_response(str(e), 500)), 500
    
    @app.route('/api/conversation/<conversation_id>/message', methods=['POST'])
    def add_conversation_message(conversation_id):
        """添加对话消息"""
        try:
            data = request.json
            role = data.get('role', 'user')
            content = data.get('content', '')
            
            if not content:
                return jsonify(error_response("消息内容不能为空", 400)), 400
            
            if not summary_service:
                return jsonify(error_response("摘要服务未初始化", 503)), 503
            
            conversation = summary_service.add_message(conversation_id, role, content)
            
            if conversation:
                return jsonify(success_response(data={
                    "message_count": conversation.message_count,
                    "updated_at": conversation.updated_at
                }))
            else:
                return jsonify(error_response("对话不存在", 404)), 404
        except Exception as e:
            logger.error(f"添加消息失败：{e}")
            return jsonify(error_response(str(e), 500)), 500
    
    @app.route('/api/conversation/<conversation_id>/summary', methods=['POST'])
    def generate_summary(conversation_id):
        """生成对话摘要"""
        try:
            data = request.json
            level_str = data.get('level', 'concise')
            
            if not summary_service:
                return jsonify(error_response("摘要服务未初始化", 503)), 503
            
            try:
                from summary_service import SummaryLevel
                level = SummaryLevel(level_str)
            except ValueError:
                level = SummaryLevel.CONCISE
            
            summary = summary_service.manual_summarize(conversation_id, level)
            
            if summary:
                return jsonify(success_response(data=summary.to_dict()))
            else:
                return jsonify(error_response("摘要生成失败", 500)), 500
        except Exception as e:
            logger.error(f"生成摘要失败：{e}")
            return jsonify(error_response(str(e), 500)), 500
    
    @app.route('/api/conversation/<conversation_id>/context', methods=['GET'])
    def get_conversation_context(conversation_id):
        """获取对话上下文"""
        try:
            max_messages = request.args.get('max_messages', 10, type=int)
            
            if not summary_service:
                return jsonify(error_response("摘要服务未初始化", 503)), 503
            
            context = summary_service.get_context_for_llm(conversation_id, max_messages)
            
            return jsonify(success_response(data=[msg.to_dict() for msg in context]))
        except Exception as e:
            logger.error(f"获取上下文失败：{e}")
            return jsonify(error_response(str(e), 500)), 500
    
    @app.route('/api/conversations', methods=['GET'])
    def list_conversations():
        """列出所有对话"""
        try:
            include_archived = request.args.get('include_archived', 'false').lower() == 'true'
            
            if not summary_service:
                return jsonify(error_response("摘要服务未初始化", 503)), 503
            
            conversations = summary_service.list_conversations(include_archived)
            
            return jsonify(success_response(data=[
                {
                    "id": c.id,
                    "title": c.title,
                    "message_count": c.message_count,
                    "created_at": c.created_at,
                    "updated_at": c.updated_at,
                    "summary_count": len(c.summaries)
                }
                for c in conversations
            ]))
        except Exception as e:
            logger.error(f"列出对话失败：{e}")
            return jsonify(error_response(str(e), 500)), 500

    # === 兼容 /api/summary/* 路由，便于旧前端调用 ===
    @app.route('/api/summary/generate', methods=['POST'])
    def generate_summary_compat():
        try:
            data = request.json or {}
            conversation_id = data.get('conversation_id')
            level_str = data.get('style') or data.get('level', 'concise')
            
            if not conversation_id:
                return jsonify(error_response("conversation_id 不能为空", 400)), 400
            if not summary_service:
                return jsonify(error_response("摘要服务未初始化", 503)), 503
            
            try:
                from summary_service import SummaryLevel
                level = SummaryLevel(level_str)
            except Exception:
                from summary_service import SummaryLevel
                level = SummaryLevel.CONCISE
            
            summary = summary_service.manual_summarize(conversation_id, level)
            if summary:
                return jsonify(success_response(data=summary.to_dict(), message="摘要生成成功"))
            return jsonify(error_response("摘要生成失败", 500)), 500
        except Exception as e:
            logger.error(f"摘要生成失败：{e}")
            return jsonify(error_response(str(e), 500)), 500

    @app.route('/api/summary', methods=['GET'])
    def list_summaries_compat():
        try:
            conversation_id = request.args.get('conversation_id')
            if not conversation_id:
                return jsonify(error_response("conversation_id 不能为空", 400)), 400
            if not summary_service:
                return jsonify(error_response("摘要服务未初始化", 503)), 503
            
            summaries = summary_service.get_summaries(conversation_id)
            return jsonify(success_response(data=[s.to_dict() for s in summaries]))
        except Exception as e:
            logger.error(f"获取摘要列表失败：{e}")
            return jsonify(error_response(str(e), 500)), 500

    @app.route('/api/summary/<summary_id>', methods=['GET', 'DELETE'])
    def summary_detail_compat(summary_id):
        try:
            if not summary_service:
                return jsonify(error_response("摘要服务未初始化", 503)), 503
            
            found = summary_service.store.get_summary_by_id(summary_id)
            if not found:
                return jsonify(error_response("摘要不存在", 404)), 404
            
            conv, summary = found
            if request.method == 'DELETE':
                deleted = summary_service.store.delete_summary(summary_id)
                if deleted:
                    return jsonify(success_response(data={"id": summary_id}, message="摘要已成功移除"))
                return jsonify(error_response("摘要删除失败", 500)), 500
            
            return jsonify(success_response(data=summary.to_dict()))
        except Exception as e:
            logger.error(f"摘要详情失败：{e}")
            return jsonify(error_response(str(e), 500)), 500

    @app.route('/api/summary/<summary_id>/export', methods=['POST'])
    def export_summary_compat(summary_id):
        try:
            format_type = (request.json or {}).get('format', 'markdown')
            found = summary_service.store.get_summary_by_id(summary_id) if summary_service else None
            if not found:
                return jsonify(error_response("摘要不存在", 404)), 404
            conv, summary = found
            export_data = {
                "summary_id": summary.id,
                "conversation_id": conv.id,
                "format": format_type,
                "content": summary.content,
                "topics": summary.topics,
                "key_points": summary.key_points
            }
            return jsonify(success_response(data=export_data, message="导出成功"))
        except Exception as e:
            logger.error(f"导出摘要失败：{e}")
            return jsonify(error_response(str(e), 500)), 500

    @app.route('/api/summary/batch_export', methods=['POST'])
    def batch_export_summary_compat():
        try:
            data = request.json or {}
            summary_ids = data.get('summary_ids', [])
            format_type = data.get('format', 'markdown')
            if not summary_ids:
                return jsonify(error_response("summary_ids 不能为空", 400)), 400
            exports = []
            for sid in summary_ids:
                found = summary_service.store.get_summary_by_id(sid) if summary_service else None
                if found:
                    conv, summary = found
                    exports.append({
                        "summary_id": summary.id,
                        "conversation_id": conv.id,
                        "format": format_type,
                        "content": summary.content,
                        "topics": summary.topics,
                        "key_points": summary.key_points
                    })
            return jsonify(success_response(data=exports, message="批量导出成功"))
        except Exception as e:
            logger.error(f"批量导出摘要失败：{e}")
            return jsonify(error_response(str(e), 500)), 500

    _conversation_state = {"mode": "standard"}
    _CONVERSATION_MODES = {
        "standard": {
            "name": "标准模式",
            "description": "严格的内容过滤，适合通用场景"
        },
        "adult": {
            "name": "成人模式",
            "description": "宽松的交流政策，更自由的表达"
        }
    }

    @app.route('/api/conversation/mode', methods=['GET'])
    def get_conversation_mode():
        """获取当前对话模式"""
        mode = _conversation_state["mode"]
        return jsonify(success_response(data={
            "mode": mode,
            "name": _CONVERSATION_MODES.get(mode, {}).get("name", mode),
            "description": _CONVERSATION_MODES.get(mode, {}).get("description", "")
        }))

    @app.route('/api/conversation/mode', methods=['POST'])
    def set_conversation_mode():
        """设置对话模式"""
        try:
            data = request.json or {}
            mode = data.get('mode', 'standard')
            
            if mode not in _CONVERSATION_MODES:
                return jsonify(error_response(f"无效的模式: {mode}", 400)), 400
            
            _conversation_state["mode"] = mode
            return jsonify(success_response(data={
                "mode": mode,
                "name": _CONVERSATION_MODES[mode]["name"],
                "description": _CONVERSATION_MODES[mode]["description"]
            }, message="对话模式已更新"))
        except Exception as e:
            logger.error(f"设置对话模式失败：{e}")
            return jsonify(error_response(str(e), 500)), 500

    @app.route('/api/conversation/modes', methods=['GET'])
    def list_conversation_modes():
        """列出所有对话模式"""
        return jsonify(success_response(data=[
            {
                "mode": mode,
                "name": info["name"],
                "description": info["description"]
            }
            for mode, info in _CONVERSATION_MODES.items()
        ]))

    logger.info("Summary API routes registered")
