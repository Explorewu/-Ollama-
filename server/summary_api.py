"""
讨论总结API服务 - Summary API Service

提供讨论总结的生成、查询、更新、删除等RESTful API接口

API端点：
- POST /api/summary/generate - 生成讨论总结
- GET /api/summary/:id - 获取总结详情
- GET /api/summary/conversation/:conv_id - 获取会话的所有总结
- PUT /api/summary/:id - 更新总结内容
- DELETE /api/summary/:id - 删除总结
- GET /api/summary/:id/export - 导出总结

作者：AI Assistant
日期：2026-02-03
版本：v1.0
"""

import os
import sys
import json
import uuid
from datetime import datetime
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, asdict

from flask import Flask, request, jsonify
from flask_cors import CORS

# 导入总结生成器
from discussion_summarizer import (
    DiscussionSummarizer, DiscussionSummary, Message,
    get_summarizer, TextPreprocessor
)


app = Flask(__name__)
CORS(app)

# 配置
DATA_DIR = os.path.join(os.path.dirname(__file__), '..', 'data', 'summaries')
os.makedirs(DATA_DIR, exist_ok=True)

# 初始化总结器
summarizer = get_summarizer(use_llm=False)


def _generate_id() -> str:
    """生成唯一ID"""
    return f"summary_{uuid.uuid4().hex[:12]}"


def _save_summary(summary: DiscussionSummary) -> bool:
    """保存总结到文件"""
    try:
        filepath = os.path.join(DATA_DIR, f"{summary.id}.json")
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(asdict(summary), f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        print(f"保存总结失败: {e}")
        return False


def _load_summary(summary_id: str) -> Optional[DiscussionSummary]:
    """从文件加载总结"""
    try:
        filepath = os.path.join(DATA_DIR, f"{summary_id}.json")
        if not os.path.exists(filepath):
            return None
        
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return DiscussionSummary(**data)
    except Exception as e:
        print(f"加载总结失败: {e}")
        return None


def _load_summaries_by_conversation(conv_id: str) -> List[DiscussionSummary]:
    """加载会话的所有总结"""
    summaries = []
    
    try:
        for filename in os.listdir(DATA_DIR):
            if not filename.endswith('.json'):
                continue
            
            filepath = os.path.join(DATA_DIR, filename)
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            if data.get('conversation_id') == conv_id:
                summaries.append(DiscussionSummary(**data))
    except Exception as e:
        print(f"加载会话总结失败: {e}")
    
    # 按创建时间倒序排列
    summaries.sort(key=lambda s: s.created_at, reverse=True)
    return summaries


def _delete_summary_file(summary_id: str) -> bool:
    """删除总结文件"""
    try:
        filepath = os.path.join(DATA_DIR, f"{summary_id}.json")
        if os.path.exists(filepath):
            os.remove(filepath)
        return True
    except Exception as e:
        print(f"删除总结失败: {e}")
        return False


# ==================== API路由 ====================

@app.route('/api/summary/health', methods=['GET'])
def health_check():
    """健康检查"""
    return jsonify({
        'status': 'healthy',
        'service': 'summary-api',
        'timestamp': int(datetime.now().timestamp() * 1000)
    })


@app.route('/api/summary/generate', methods=['POST'])
def generate_summary():
    """
    生成讨论总结
    
    请求体：
    {
        "conversation_id": "conv_123",
        "messages": [
            {
                "id": "msg_1",
                "role": "user",
                "content": "...",
                "timestamp": 1700000000000,
                "model": "",
                "character_name": ""
            }
        ],
        "options": {
            "include_timeline": true,
            "include_viewpoints": true,
            "max_key_points": 5
        }
    }
    """
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({'error': '请求体不能为空'}), 400
        
        conversation_id = data.get('conversation_id')
        messages = data.get('messages', [])
        options = data.get('options', {})
        
        if not conversation_id:
            return jsonify({'error': 'conversation_id不能为空'}), 400
        
        if not messages:
            return jsonify({'error': 'messages不能为空'}), 400
        
        # 验证消息格式
        for msg in messages:
            if not all(k in msg for k in ['id', 'role', 'content', 'timestamp']):
                return jsonify({'error': '消息格式不完整'}), 400
        
        # 生成总结
        summary = summarizer.generate_summary(messages, conversation_id)
        
        # 应用选项
        if not options.get('include_timeline', True):
            summary.timeline = []
        if not options.get('include_viewpoints', True):
            summary.viewpoints = []
        
        max_key_points = options.get('max_key_points', 5)
        if len(summary.key_points) > max_key_points:
            summary.key_points = summary.key_points[:max_key_points]
        
        # 保存总结
        if not _save_summary(summary):
            return jsonify({'error': '保存总结失败'}), 500
        
        return jsonify({
            'success': True,
            'data': asdict(summary)
        })
    
    except Exception as e:
        print(f"生成总结失败: {e}")
        return jsonify({'error': f'生成总结失败: {str(e)}'}), 500


@app.route('/api/summary/<summary_id>', methods=['GET'])
def get_summary(summary_id: str):
    """
    获取总结详情
    
    响应：
    {
        "success": true,
        "data": { ...summary object... }
    }
    """
    try:
        summary = _load_summary(summary_id)
        
        if not summary:
            return jsonify({'error': '总结不存在'}), 404
        
        return jsonify({
            'success': True,
            'data': asdict(summary)
        })
    
    except Exception as e:
        print(f"获取总结失败: {e}")
        return jsonify({'error': f'获取总结失败: {str(e)}'}), 500


@app.route('/api/summary/conversation/<conversation_id>', methods=['GET'])
def get_conversation_summaries(conversation_id: str):
    """
    获取会话的所有总结
    
    查询参数：
    - limit: 返回数量限制（默认10）
    - offset: 偏移量（默认0）
    
    响应：
    {
        "success": true,
        "data": [ ...summary objects... ],
        "total": 5
    }
    """
    try:
        limit = request.args.get('limit', 10, type=int)
        offset = request.args.get('offset', 0, type=int)
        
        summaries = _load_summaries_by_conversation(conversation_id)
        total = len(summaries)
        
        # 分页
        summaries = summaries[offset:offset + limit]
        
        return jsonify({
            'success': True,
            'data': [asdict(s) for s in summaries],
            'total': total
        })
    
    except Exception as e:
        print(f"获取会话总结失败: {e}")
        return jsonify({'error': f'获取会话总结失败: {str(e)}'}), 500


@app.route('/api/summary/<summary_id>', methods=['PUT'])
def update_summary(summary_id: str):
    """
    更新总结内容
    
    请求体：
    {
        "overview": "新的概述",
        "key_points": ["要点1", "要点2"],
        "conclusions": ["结论1"],
        "edited_by": "user_id"
    }
    """
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({'error': '请求体不能为空'}), 400
        
        # 加载原总结
        summary = _load_summary(summary_id)
        
        if not summary:
            return jsonify({'error': '总结不存在'}), 404
        
        # 应用更新
        summary = summarizer.update_summary(summary, data)
        
        # 保存更新
        if not _save_summary(summary):
            return jsonify({'error': '保存更新失败'}), 500
        
        return jsonify({
            'success': True,
            'data': asdict(summary)
        })
    
    except Exception as e:
        print(f"更新总结失败: {e}")
        return jsonify({'error': f'更新总结失败: {str(e)}'}), 500


@app.route('/api/summary/<summary_id>', methods=['DELETE'])
def delete_summary(summary_id: str):
    """删除总结"""
    try:
        summary = _load_summary(summary_id)
        
        if not summary:
            return jsonify({'error': '总结不存在'}), 404
        
        if not _delete_summary_file(summary_id):
            return jsonify({'error': '删除失败'}), 500
        
        return jsonify({
            'success': True,
            'message': '总结已删除'
        })
    
    except Exception as e:
        print(f"删除总结失败: {e}")
        return jsonify({'error': f'删除总结失败: {str(e)}'}), 500


@app.route('/api/summary/<summary_id>/export', methods=['GET'])
def export_summary(summary_id: str):
    """
    导出总结
    
    查询参数：
    - format: 导出格式（json, markdown, text）默认json
    """
    try:
        export_format = request.args.get('format', 'json')
        
        summary = _load_summary(summary_id)
        
        if not summary:
            return jsonify({'error': '总结不存在'}), 404
        
        if export_format == 'json':
            return jsonify({
                'success': True,
                'data': asdict(summary)
            })
        
        elif export_format == 'markdown':
            md_content = _export_to_markdown(summary)
            return md_content, 200, {'Content-Type': 'text/markdown'}
        
        elif export_format == 'text':
            text_content = _export_to_text(summary)
            return text_content, 200, {'Content-Type': 'text/plain'}
        
        else:
            return jsonify({'error': '不支持的导出格式'}), 400
    
    except Exception as e:
        print(f"导出总结失败: {e}")
        return jsonify({'error': f'导出总结失败: {str(e)}'}), 500


def _export_to_markdown(summary: DiscussionSummary) -> str:
    """导出为Markdown格式"""
    md = f"""# 讨论总结

## 基本信息
- **会话ID**: {summary.conversation_id}
- **生成时间**: {datetime.fromtimestamp(summary.created_at / 1000).strftime('%Y-%m-%d %H:%M:%S')}
- **消息数量**: {summary.message_count}
- **参与人数**: {summary.participant_count}
- **讨论时长**: {summary.duration_minutes} 分钟
- **置信度**: {summary.confidence_score:.2%}

## 总体概述
{summary.overview}

## 关键要点
"""
    
    for i, point in enumerate(summary.key_points, 1):
        md += f"{i}. {point}\n"
    
    if summary.topics:
        md += "\n## 讨论主题\n"
        for topic in summary.topics:
            md += f"\n### {topic.get('title', '未命名主题')}\n"
            md += f"- **关键词**: {', '.join(topic.get('keywords', []))}\n"
            md += f"- **相关度**: {topic.get('score', 0):.3f}\n"
    
    if summary.viewpoints:
        md += "\n## 观点汇总\n"
        for vp in summary.viewpoints:
            md += f"\n### {vp.get('participant', '未知参与者')}\n"
            md += f"- **消息数**: {vp.get('message_count', 0)}\n"
            md += f"- **立场**: {vp.get('stance', 'neutral')}\n"
            md += f"- **情感**: {vp.get('sentiment', {}).get('label', 'neutral')}\n"
            if vp.get('key_points'):
                md += "- **关键观点**:\n"
                for kp in vp['key_points']:
                    md += f"  - {kp}\n"
    
    if summary.conclusions:
        md += "\n## 结论建议\n"
        for conclusion in summary.conclusions:
            md += f"- {conclusion}\n"
    
    if summary.timeline:
        md += "\n## 讨论时间线\n"
        for phase in summary.timeline:
            start_time = datetime.fromtimestamp(phase.get('start_time', 0) / 1000).strftime('%H:%M')
            end_time = datetime.fromtimestamp(phase.get('end_time', 0) / 1000).strftime('%H:%M')
            md += f"\n### {start_time} - {end_time}\n"
            md += f"- **类型**: {phase.get('type', 'discussing')}\n"
            md += f"- **消息数**: {phase.get('message_count', 0)}\n"
            md += f"- **参与者**: {', '.join(phase.get('participants', []))}\n"
            md += f"- **摘要**: {phase.get('summary', '')}\n"
    
    md += f"\n\n---\n*由AI自动生成，版本 {summary.version}*"
    
    return md


def _export_to_text(summary: DiscussionSummary) -> str:
    """导出为纯文本格式"""
    text = f"""讨论总结
{'=' * 50}

会话ID: {summary.conversation_id}
生成时间: {datetime.fromtimestamp(summary.created_at / 1000).strftime('%Y-%m-%d %H:%M:%S')}
消息数量: {summary.message_count}
参与人数: {summary.participant_count}
讨论时长: {summary.duration_minutes} 分钟
置信度: {summary.confidence_score:.2%}

总体概述
{'-' * 50}
{summary.overview}

关键要点
{'-' * 50}
"""
    
    for i, point in enumerate(summary.key_points, 1):
        text += f"{i}. {point}\n"
    
    if summary.conclusions:
        text += f"\n结论建议\n{'-' * 50}\n"
        for conclusion in summary.conclusions:
            text += f"- {conclusion}\n"
    
    text += f"\n{'=' * 50}\n由AI自动生成，版本 {summary.version}"
    
    return text


@app.route('/api/summary/analyze-keywords', methods=['POST'])
def analyze_keywords():
    """
    分析关键词
    
    请求体：
    {
        "text": "要分析的文本",
        "top_k": 10
    }
    """
    try:
        data = request.get_json()
        
        if not data or 'text' not in data:
            return jsonify({'error': 'text不能为空'}), 400
        
        text = data['text']
        top_k = data.get('top_k', 10)
        
        keywords = TextPreprocessor.extract_keywords(text, top_k)
        
        return jsonify({
            'success': True,
            'data': [
                {'word': word, 'score': score}
                for word, score in keywords
            ]
        })
    
    except Exception as e:
        print(f"分析关键词失败: {e}")
        return jsonify({'error': f'分析关键词失败: {str(e)}'}), 500


@app.route('/api/summary/stats', methods=['GET'])
def get_stats():
    """获取统计信息"""
    try:
        total_summaries = 0
        total_conversations = set()
        
        for filename in os.listdir(DATA_DIR):
            if filename.endswith('.json'):
                total_summaries += 1
                
                filepath = os.path.join(DATA_DIR, filename)
                with open(filepath, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    total_conversations.add(data.get('conversation_id'))
        
        return jsonify({
            'success': True,
            'data': {
                'total_summaries': total_summaries,
                'total_conversations': len(total_conversations),
                'data_directory': DATA_DIR
            }
        })
    
    except Exception as e:
        print(f"获取统计信息失败: {e}")
        return jsonify({'error': f'获取统计信息失败: {str(e)}'}), 500


# 错误处理
@app.errorhandler(404)
def not_found(error):
    return jsonify({'error': '接口不存在'}), 404


@app.errorhandler(500)
def internal_error(error):
    return jsonify({'error': '服务器内部错误'}), 500


if __name__ == '__main__':
    print("=" * 60)
    print("讨论总结API服务")
    print("=" * 60)
    print(f"数据目录: {DATA_DIR}")
    print("API端点:")
    print("  POST /api/summary/generate - 生成总结")
    print("  GET  /api/summary/<id> - 获取总结")
    print("  GET  /api/summary/conversation/<conv_id> - 获取会话总结")
    print("  PUT  /api/summary/<id> - 更新总结")
    print("  DELETE /api/summary/<id> - 删除总结")
    print("  GET  /api/summary/<id>/export - 导出总结")
    print("=" * 60)
    
    app.run(host='::', port=5002, debug=True)
