# -*- coding: utf-8 -*-
"""
Ollama 代理模块

将 Ollama 原生 API 代理到后端，实现：
1. 统一前端调用入口（全部走 /api/xxx）
2. 支持本地模型回退（Ollama 不可用时自动切换）
3. 统一的错误处理和日志记录
"""

import os
import json
import logging
import requests
from flask import request, jsonify, Response, stream_with_context

from utils.config import OLLAMA_BASE_URL
from utils.helpers import success_response, error_response

logger = logging.getLogger(__name__)


def _proxy_to_ollama(endpoint: str, method: str = "GET", data: dict = None, stream: bool = False):
    """
    代理请求到 Ollama 服务
    
    Args:
        endpoint: Ollama API 端点（如 /api/tags）
        method: HTTP 方法
        data: 请求体数据
        stream: 是否流式响应
    
    Returns:
        Response 对象或错误响应
    """
    url = f"{OLLAMA_BASE_URL}{endpoint}"
    
    try:
        headers = {"Content-Type": "application/json"}
        
        if method == "GET":
            resp = requests.get(url, headers=headers, timeout=30, stream=stream)
        elif method == "POST":
            resp = requests.post(url, headers=headers, json=data, timeout=300, stream=stream)
        elif method == "DELETE":
            resp = requests.delete(url, headers=headers, json=data, timeout=30)
        else:
            return jsonify(error_response(f"不支持的 HTTP 方法: {method}", 405)), 405
        
        if stream:
            # 流式响应直接透传
            return Response(
                stream_with_context(resp.iter_content(chunk_size=1024)),
                status=resp.status_code,
                content_type=resp.headers.get('Content-Type', 'application/json')
            )
        else:
            # 非流式响应返回 JSON
            if resp.status_code == 200:
                return jsonify(success_response(data=resp.json()))
            else:
                return jsonify(error_response(
                    resp.text or f"Ollama 返回错误: {resp.status_code}",
                    resp.status_code
                )), resp.status_code
                
    except requests.exceptions.ConnectionError:
        logger.error(f"无法连接到 Ollama 服务: {OLLAMA_BASE_URL}")
        return jsonify(error_response(
            "Ollama 服务未启动或无法连接",
            503
        )), 503
    except requests.exceptions.Timeout:
        logger.error(f"Ollama 请求超时: {endpoint}")
        return jsonify(error_response("Ollama 请求超时", 504)), 504
    except Exception as e:
        logger.error(f"Ollama 代理错误: {e}")
        return jsonify(error_response(f"代理错误: {str(e)}", 500)), 500


def register_ollama_proxy_routes(app):
    """注册 Ollama 代理路由"""
    
    @app.route('/api/tags', methods=['GET'])
    def proxy_tags():
        """获取模型列表（Ollama 原生 API）"""
        return _proxy_to_ollama('/api/tags', 'GET')
    
    @app.route('/api/version', methods=['GET'])
    def proxy_version():
        """获取 Ollama 版本（Ollama 原生 API）"""
        return _proxy_to_ollama('/api/version', 'GET')
    
    @app.route('/api/show', methods=['POST'])
    def proxy_show():
        """获取模型详情（Ollama 原生 API）"""
        data = request.json or {}
        return _proxy_to_ollama('/api/show', 'POST', data)
    
    @app.route('/api/generate', methods=['POST'])
    def proxy_generate():
        """生成文本（Ollama 原生 API，支持流式）"""
        data = request.json or {}
        stream = data.get('stream', False)
        return _proxy_to_ollama('/api/generate', 'POST', data, stream=stream)
    
    @app.route('/api/delete', methods=['DELETE'])
    def proxy_delete():
        """删除模型（Ollama 原生 API）"""
        data = request.json or {}
        return _proxy_to_ollama('/api/delete', 'DELETE', data)
    
    @app.route('/api/copy', methods=['POST'])
    def proxy_copy():
        """复制模型（Ollama 原生 API）"""
        data = request.json or {}
        return _proxy_to_ollama('/api/copy', 'POST', data)
    
    @app.route('/api/embeddings', methods=['POST'])
    def proxy_embeddings():
        """生成嵌入向量（Ollama 原生 API）"""
        data = request.json or {}
        return _proxy_to_ollama('/api/embeddings', 'POST', data)
    
    @app.route('/api/pull', methods=['POST'])
    def proxy_pull():
        """拉取模型（Ollama 原生 API，支持流式）"""
        data = request.json or {}
        stream = data.get('stream', False)
        return _proxy_to_ollama('/api/pull', 'POST', data, stream=stream)
    
    @app.route('/api/push', methods=['POST'])
    def proxy_push():
        """推送模型（Ollama 原生 API，支持流式）"""
        data = request.json or {}
        stream = data.get('stream', False)
        return _proxy_to_ollama('/api/push', 'POST', data, stream=stream)
    
    logger.info("✓ Ollama 代理路由已注册")
