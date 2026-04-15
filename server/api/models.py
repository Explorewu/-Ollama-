"""
模型管理 API 模块

提供模型列表、下载等接口
"""

import os
import json
import time
import logging
import requests
from datetime import datetime
from flask import request, jsonify, Response, stream_with_context

from utils.config import OLLAMA_BASE_URL, PROJECT_DIR
from utils.auth import require_api_key
from utils.helpers import success_response, error_response

logger = logging.getLogger(__name__)

BASE_DIR = str(PROJECT_DIR)

GGUF_META_CACHE = {}


def _get_dir_size(path):
    """计算目录总大小"""
    total = 0
    try:
        for entry in os.scandir(path):
            if entry.is_file():
                total += entry.stat().st_size
            elif entry.is_dir():
                total += _get_dir_size(entry.path)
    except Exception:
        pass
    return total


def _read_gguf_metadata(filepath: str) -> dict | None:
    """读取 GGUF 文件元数据（带缓存）"""
    if filepath in GGUF_META_CACHE:
        return GGUF_META_CACHE[filepath]

    info = None
    try:
        from check_gguf import extract_model_info
        info = extract_model_info(filepath)
    except Exception as e:
        logger.debug(f"读取 GGUF 元数据失败 {filepath}: {e}")

    GGUF_META_CACHE[filepath] = info
    return info


def _scan_local_models():
    """扫描本地模型目录"""
    local_models = []
    scanned_models = set()

    scan_dirs = [
        os.path.join(BASE_DIR, 'models'),
        os.path.join(BASE_DIR, '.ollama', 'models'),
        os.path.expanduser('~/.ollama/models'),
    ]

    if os.environ.get('LOCAL_MODELS_DIR'):
        scan_dirs.insert(0, os.environ.get('LOCAL_MODELS_DIR'))

    for scan_dir in scan_dirs:
        if not os.path.exists(scan_dir):
            continue

        try:
            for root, dirs, files in os.walk(scan_dir):
                for file in files:
                    if not file.endswith('.gguf'):
                        continue
                    file_path = os.path.join(root, file)
                    try:
                        stat = os.stat(file_path)
                        model_name = file.replace('.gguf', '')

                        if model_name in scanned_models:
                            continue
                        scanned_models.add(model_name)

                        meta = _read_gguf_metadata(file_path)
                        family = meta.get('family', 'unknown') if meta else 'unknown'
                        parameter_size = meta.get('parameter_size', 'unknown') if meta else 'unknown'
                        quantization = meta.get('quantization', 'unknown') if meta else 'unknown'
                        context_length = meta.get('context_length', None) if meta else None

                        local_models.append({
                            'name': model_name,
                            'model': model_name,
                            'modified_at': datetime.fromtimestamp(stat.st_mtime).isoformat(),
                            'size': stat.st_size,
                            'digest': '',
                            'details': {
                                'format': 'gguf',
                                'family': family,
                                'parameter_size': parameter_size,
                                'quantization': quantization,
                                'context_length': context_length,
                            },
                            'source': 'local_file',
                            'provider': 'local_scan',
                            'runnable': True,
                            'path': file_path
                        })
                    except Exception as e:
                        logger.warning(f"扫描 GGUF 文件失败 {file_path}: {e}")
        except Exception as e:
            logger.warning(f"扫描目录失败 {scan_dir}: {e}")

    llm_dir = os.path.join(BASE_DIR, 'models', 'llm')
    vlm_dir = os.path.join(BASE_DIR, 'models', 'vlm')
    hf_dirs = [llm_dir, vlm_dir]

    for scan_dir in hf_dirs:
        if not os.path.exists(scan_dir):
            continue
        try:
            for root, dirs, files in os.walk(scan_dir):
                safetensors_files = [f for f in files if f.endswith('.safetensors')]
                if not safetensors_files:
                    continue

                model_dir = os.path.basename(root)
                model_path = root

                if model_dir in scanned_models:
                    continue
                if model_dir.startswith('.') or model_dir.startswith('_'):
                    continue
                scanned_models.add(model_dir)

                model_size = _get_dir_size(model_path)
                stat = os.stat(model_path)

                parameter_size = 'unknown'
                family = 'transformers'
                config_path = os.path.join(model_path, 'config.json')
                if os.path.exists(config_path):
                    try:
                        with open(config_path, 'r', encoding='utf-8') as f:
                            config = json.load(f)
                            model_type = config.get('model_type', '')
                            if model_type:
                                family = model_type
                            if 'num_parameters' in config:
                                params = config['num_parameters']
                                if params >= 1e9:
                                    parameter_size = f"{params/1e9:.1f}B"
                                elif params >= 1e6:
                                    parameter_size = f"{params/1e6:.1f}M"
                            elif 'num_hidden_layers' in config and 'hidden_size' in config:
                                num_layers = config['num_hidden_layers']
                                hidden_size = config['hidden_size']
                                intermediate_size = config.get('intermediate_size', hidden_size * 4)
                                vocab_size = config.get('vocab_size', 32000)
                                embed_params = vocab_size * hidden_size
                                attn_params = num_layers * 4 * hidden_size * hidden_size
                                ff_params = num_layers * 2 * hidden_size * intermediate_size
                                total_params = embed_params + attn_params + ff_params
                                if total_params >= 1e9:
                                    parameter_size = f"~{total_params/1e9:.1f}B"
                                elif total_params >= 1e6:
                                    parameter_size = f"~{total_params/1e6:.1f}M"
                    except Exception:
                        pass

                local_models.append({
                    'name': model_dir,
                    'model': model_dir,
                    'modified_at': datetime.fromtimestamp(stat.st_mtime).isoformat(),
                    'size': model_size,
                    'digest': '',
                    'details': {
                        'format': 'safetensors',
                        'family': family,
                        'parameter_size': parameter_size
                    },
                    'source': 'local_file',
                    'provider': 'transformers',
                    'runnable': True,
                    'path': model_path
                })
                logger.info(f"扫描到 safetensors 模型: {model_dir}, 大小: {model_size / (1024**3):.2f} GB")
        except Exception as e:
            logger.warning(f"扫描目录失败 {scan_dir}: {e}")

    return local_models


def register_models_routes(app):
    """注册模型管理相关路由"""

    @app.route('/api/models', methods=['GET'])
    def get_models_list():
        """获取模型列表"""
        try:
            all_models = []

            try:
                response = requests.get(f"{OLLAMA_BASE_URL}/api/tags", timeout=10)
                if response.ok:
                    data = response.json()
                    ollama_models = data.get('models', [])
                    for model in ollama_models:
                        model.setdefault('source', 'ollama')
                        model.setdefault('provider', 'ollama')
                        model.setdefault('runnable', True)
                    all_models.extend(ollama_models)
                    logger.info(f"从 Ollama 获取到 {len(ollama_models)} 个模型")
            except Exception as e:
                if "Connection refused" in str(e) or "NewConnectionError" in str(e):
                    logger.debug("Ollama 服务未运行，使用本地模型")
                else:
                    logger.debug(f"从 Ollama 获取模型失败：{type(e).__name__}: {e}")

            try:
                local_models = _scan_local_models()
                existing_names = {m['name'] for m in all_models}
                for local_model in local_models:
                    if local_model['name'] not in existing_names:
                        all_models.append(local_model)
            except Exception as e:
                logger.warning(f"扫描本地模型失败: {e}")

            return jsonify(success_response(
                data={'models': all_models, 'count': len(all_models)},
                message='获取模型列表成功'
            ))
        except Exception as e:
            logger.error(f"获取模型列表失败: {e}")
            return jsonify(error_response(str(e), 500)), 500

    @app.route('/api/models/pull', methods=['POST'])
    @require_api_key
    def pull_model():
        """下载模型"""
        try:
            data = request.json or {}
            model_name = data.get('name', '')

            if not model_name:
                return jsonify(error_response("缺少 model name 参数", 400)), 400

            logger.info(f"开始下载模型: {model_name}")

            response = requests.post(
                f"{OLLAMA_BASE_URL}/api/pull",
                json={"name": model_name},
                stream=True,
                timeout=300
            )

            if not response.ok:
                return jsonify(error_response(f"Ollama API 错误: {response.status_code}", 500)), 500

            def generate():
                for line in response.iter_lines():
                    if line:
                        try:
                            chunk = line.decode('utf-8')
                            data = json.loads(chunk)
                            yield f"data: {json.dumps(data)}\n\n"

                            if data.get('status') == 'success':
                                logger.info(f"模型下载完成: {model_name}")
                        except Exception:
                            continue

            return Response(
                stream_with_context(generate()),
                mimetype='text/event-stream'
            )
        except Exception as e:
            logger.error(f"下载模型失败: {e}")
            return jsonify(error_response(str(e), 500)), 500

    @app.route('/v1/models', methods=['GET'])
    @require_api_key
    def openai_list_models():
        """OpenAI 兼容模型列表"""
        try:
            response = requests.get(f"{OLLAMA_BASE_URL}/api/tags", timeout=5)

            if response.ok:
                ollama_models = response.json().get('models', [])
                models = [{
                    "id": m.get('name', ''),
                    "object": "model",
                    "created": int(time.time()),
                    "owned_by": "local"
                } for m in ollama_models]

                return jsonify(success_response(data={"object": "list", "data": models}))
            else:
                return jsonify(error_response("获取模型列表失败", 500)), 500
        except Exception as e:
            return jsonify(error_response(str(e), 500)), 500

    logger.info("✓ 模型管理 API 路由已注册")
