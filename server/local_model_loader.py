# -*- coding: utf-8 -*-
"""
本地模型加载器 - 支持 safetensors (Transformers) 和 GGUF (llama-server HTTP API) 模型
"""

import os
import re
import logging
import subprocess
import time
import urllib.request
import urllib.error
import json
import requests
import threading
from typing import Optional, List, Dict, Any, Generator

logger = logging.getLogger(__name__)

SERVER_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(SERVER_DIR)

LLAMA_SERVER_EXE = os.path.join(PROJECT_DIR, "llama", "llama-server.exe")
LLAMA_SERVER_HOST = "127.0.0.1"

_llama_server_instances: Dict[str, subprocess.Popen] = {}
_port_counter = 8081
_port_lock = threading.Lock()

TRANSFORMERS_AVAILABLE = False
try:
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer, TextIteratorStreamer
    from threading import Thread
    TRANSFORMERS_AVAILABLE = True
except ImportError:
    logger.warning("Transformers 库不可用，safetensors 模型将无法加载")

LOCAL_MODEL_AVAILABLE = True

_tokenizer_cache: Dict[str, Any] = {}
_model_cache: Dict[str, Any] = {}
_gguf_model_cache: Dict[str, Any] = {}

# 推理模式全局配置
_reasoning_enabled: bool = False

def set_reasoning_mode(enabled: bool):
    """设置推理模式（需要重启模型生效）"""
    global _reasoning_enabled
    _reasoning_enabled = enabled
    logger.info(f"推理模式已设置为: {'开启' if enabled else '关闭'}")

def get_reasoning_mode() -> bool:
    """获取当前推理模式"""
    return _reasoning_enabled

GGUF_SEARCH_DIRS = [
    os.path.join(PROJECT_DIR, "models", "llm", "gguf"),
    os.path.join(PROJECT_DIR, "models", "llm"),
]

SAFETENSORS_SEARCH_DIRS = [
    os.path.join(PROJECT_DIR, "models", "llm", "hf"),
    os.path.join(PROJECT_DIR, "models", "vlm"),
    os.path.join(PROJECT_DIR, "models", "llm"),
]


def _discover_gguf_models() -> Dict[str, str]:
    """自动发现所有 GGUF 模型文件"""
    discovered = {}
    for base_dir in GGUF_SEARCH_DIRS:
        if not os.path.exists(base_dir):
            continue
        for root, dirs, files in os.walk(base_dir):
            for f in files:
                if not f.endswith('.gguf'):
                    continue
                filepath = os.path.join(root, f)
                model_name = f[:-5]
                if model_name not in discovered:
                    discovered[model_name] = filepath
    return discovered


def _discover_safetensors_models() -> Dict[str, str]:
    """自动发现所有 safetensors 模型目录"""
    discovered = {}
    for base_dir in SAFETENSORS_SEARCH_DIRS:
        if not os.path.exists(base_dir):
            continue
        for root, dirs, files in os.walk(base_dir):
            has_safetensors = any(f.endswith('.safetensors') for f in files)
            if not has_safetensors:
                continue
            model_name = os.path.basename(root)
            if model_name.startswith('.') or model_name.startswith('_'):
                continue
            if model_name not in discovered:
                discovered[model_name] = root
    return discovered


def _allocate_port() -> int:
    global _port_counter
    with _port_lock:
        port = _port_counter
        _port_counter += 1
        return port


def _wait_for_server(host: str, port: int, timeout: int = 60) -> bool:
    start = time.time()
    while time.time() - start < timeout:
        try:
            req = urllib.request.Request(f"http://{host}:{port}/v1/models")
            resp = urllib.request.urlopen(req, timeout=5)
            if resp.status == 200:
                return True
        except Exception:
            pass
        time.sleep(2)
    return False


class LlamaServerManager:
    def __init__(self, model_path: str, model_name: str, n_ctx: int = 4096, n_threads: int = 8):
        self.model_path = model_path
        self.model_name = model_name
        self.n_ctx = n_ctx
        self.n_threads = n_threads
        self.process: Optional[subprocess.Popen] = None
        self.port = _allocate_port()
        self.host = LLAMA_SERVER_HOST
        self._bat_file: Optional[str] = None

    def start(self) -> bool:
        global _llama_server_instances
        if self.model_name in _llama_server_instances:
            logger.info(f"llama-server 已运行: {self.model_name} @ port {self.port}")
            return True

        if not os.path.exists(self.model_path):
            logger.error(f"模型文件不存在: {self.model_path}")
            return False

        if not os.path.exists(LLAMA_SERVER_EXE):
            logger.error(f"llama-server 不存在: {LLAMA_SERVER_EXE}")
            return False

        cmd = [
            LLAMA_SERVER_EXE,
            "-m", self.model_path,
            "-c", str(self.n_ctx),
            "-t", str(self.n_threads),
            "--host", self.host,
            "--port", str(self.port),
            "-ngl", "0",
            "--reasoning", "off",
        ]

        logger.info(f"启动 llama-server: {' '.join(cmd)}")
        try:
            import tempfile
            bat_content = f"@echo off\r\nchcp 65001 >nul 2>&1\r\n{' '.join('\"' + c + '\"' if ' ' in c else c for c in cmd)} %*\r\n"
            bat_file = tempfile.NamedTemporaryFile(mode='w', suffix='.bat', delete=False, encoding='utf-8', dir=tempfile.gettempdir())
            bat_file.write(bat_content)
            bat_file.close()
            self.process = subprocess.Popen(
                [bat_file.name],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
            )
            self._bat_file = bat_file.name
        except Exception as e:
            logger.error(f"启动 llama-server 失败: {e}")
            return False

        _llama_server_instances[self.model_name] = self.process

        if not _wait_for_server(self.host, self.port, timeout=120):
            logger.error(f"llama-server 启动超时: {self.model_name}")
            self.stop()
            return False

        logger.info(f"llama-server 启动成功: {self.model_name} @ http://{self.host}:{self.port}")
        return True

    def stop(self):
        global _llama_server_instances
        if self.model_name not in _llama_server_instances:
            return
        try:
            self.process.terminate()
            self.process.wait(timeout=10)
        except Exception:
            try:
                self.process.kill()
            except Exception:
                pass
        del _llama_server_instances[self.model_name]
        if self._bat_file:
            try:
                os.unlink(self._bat_file)
            except Exception:
                pass
            self._bat_file = None
        logger.info(f"llama-server 已停止: {self.model_name}")

    def chat(self, messages: List[Dict], temperature: float = 0.7, max_tokens: int = 2048,
             stream: bool = False, repeat_penalty: float = 1.1, top_k: int = 40,
             top_p: float = 0.9) -> Dict[str, Any]:
        url = f"http://{self.host}:{self.port}/v1/chat/completions"
        payload = {
            "model": os.path.basename(self.model_path),
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": stream,
            "repeat_penalty": repeat_penalty,
            "top_k": top_k,
            "top_p": top_p,
        }
        try:
            if stream:
                resp = requests.post(url, json=payload, stream=True, timeout=120)
                resp.raise_for_status()
                return {"_stream_response": resp}
            resp = requests.post(url, json=payload, timeout=120)
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            logger.error(f"llama-server 请求失败: {e}")
            return {"error": str(e)}

    def completion(self, prompt: str, temperature: float = 0.7, max_tokens: int = 2048,
                   stream: bool = False) -> Dict[str, Any]:
        url = f"http://{self.host}:{self.port}/v1/completions"
        payload = {
            "model": os.path.basename(self.model_path),
            "prompt": prompt,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": stream,
        }
        try:
            resp = requests.post(url, json=payload, timeout=120)
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            logger.error(f"llama-server completion 请求失败: {e}")
            return {"error": str(e)}


_llama_server_manager_cache: Dict[str, LlamaServerManager] = {}


def _get_llama_server(model_name: str, n_ctx: int = 4096) -> Optional[LlamaServerManager]:
    global _llama_server_manager_cache
    cache_key = f"{model_name}_{n_ctx}"
    if cache_key in _llama_server_manager_cache:
        return _llama_server_manager_cache[cache_key]

    model_path = get_gguf_model_path(model_name)
    if not model_path:
        logger.error(f"找不到 GGUF 模型: {model_name}")
        return None

    manager = LlamaServerManager(model_path, model_name, n_ctx=n_ctx)
    if not manager.start():
        return None

    _llama_server_manager_cache[cache_key] = manager
    return manager

def is_gguf_model(model_name: str) -> bool:
    """判断是否为 GGUF 格式模型——基于实际文件发现"""
    return get_gguf_model_path(model_name) is not None


def get_gguf_model_path(model_name: str) -> Optional[str]:
    """获取 GGUF 模型路径——自动发现 + 模糊匹配"""
    discovered = _discover_gguf_models()
    cleaned = model_name.lower().replace(':latest', '').replace(':', '-')

    if cleaned in discovered:
        return discovered[cleaned]

    for name, path in discovered.items():
        name_lower = name.lower()
        if cleaned == name_lower or cleaned in name_lower or name_lower in cleaned:
            return path

    if os.path.isabs(model_name) and model_name.endswith('.gguf') and os.path.exists(model_name):
        return model_name

    return None


def get_local_model_path(model_name: str) -> Optional[str]:
    """获取本地 safetensors 模型路径——自动发现"""
    discovered = _discover_safetensors_models()
    cleaned = model_name.lower().replace(':latest', '').replace(':', '-')

    if cleaned in discovered:
        return discovered[cleaned]

    for name, path in discovered.items():
        name_lower = name.lower()
        if cleaned == name_lower or cleaned in name_lower or name_lower in cleaned:
            return path

    return None


def load_gguf_model(model_name: str, n_ctx: int = 4096, n_gpu_layers: int = 0):
    """加载 GGUF 格式模型（通过 llama-server HTTP API）"""
    manager = _get_llama_server(model_name, n_ctx=n_ctx)
    if not manager:
        logger.error(f"无法启动 llama-server: {model_name}")
        return None
    logger.info(f"GGUF 模型已就绪: {model_name} @ port {manager.port}")
    return ('llama_server', manager)


def load_local_model(model_name: str):
    """加载本地 safetensors 模型"""
    global _model_cache, _tokenizer_cache
    
    if not TRANSFORMERS_AVAILABLE:
        logger.error("Transformers 未安装，无法加载 safetensors 模型")
        return None, None
    
    if model_name in _model_cache and model_name in _tokenizer_cache:
        logger.info(f"使用缓存的模型: {model_name}")
        return _model_cache[model_name], _tokenizer_cache[model_name]
    
    model_path = get_local_model_path(model_name)
    if not model_path:
        logger.error(f"找不到本地模型: {model_name}")
        return None, None
    
    logger.info(f"正在加载本地模型: {model_path}")
    
    try:
        tokenizer = AutoTokenizer.from_pretrained(
            model_path,
            trust_remote_code=True,
            local_files_only=True
        )
        
        if tokenizer.pad_token is None:
            tokenizer.pad_token = tokenizer.eos_token
        
        model = AutoModelForCausalLM.from_pretrained(
            model_path,
            torch_dtype=torch.float16,
            device_map="auto",
            trust_remote_code=True,
            local_files_only=True
        )
        
        _model_cache[model_name] = model
        _tokenizer_cache[model_name] = tokenizer
        
        logger.info(f"模型加载成功: {model_name}")
        return model, tokenizer
        
    except Exception as e:
        logger.error(f"加载模型失败: {e}")
        return None, None


def generate_gguf_chat_response(
    model_name: str,
    messages: List[Dict[str, str]],
    temperature: float = 0.7,
    max_tokens: int = 2048,
    stream: bool = False,
    n_ctx: int = 4096,
    repeat_penalty: float = 1.1,
    top_k: int = 40,
    top_p: float = 0.9
) -> Generator[Dict[str, Any], None, None]:
    """使用 llama-server HTTP API 生成对话响应"""
    manager = _get_llama_server(model_name, n_ctx=n_ctx)
    if not manager:
        yield {"error": f"无法加载 GGUF 模型: {model_name}"}
        return

    try:
        resp_data = manager.chat(
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            stream=stream,
            repeat_penalty=repeat_penalty,
            top_k=top_k,
            top_p=top_p,
        )

        if "error" in resp_data:
            yield {"error": resp_data["error"]}
            return

        if stream:
            resp_wrapper = resp_data.get("_stream_response")
            if not resp_wrapper:
                yield {"error": "流式响应获取失败"}
                return
            full_content = ""
            try:
                for line in resp_wrapper.iter_lines():
                    if not line:
                        continue
                    line = line.decode("utf-8", errors="replace").strip()
                    if line == "data: [DONE]":
                        break
                    if not line.startswith("data: "):
                        continue
                    try:
                        obj = json.loads(line[6:])
                        delta = obj.get("choices", [{}])[0].get("delta", {})
                        content = delta.get("content", "")
                        if content:
                            full_content += content
                            yield {"message": {"role": "assistant", "content": content}, "done": False}
                    except json.JSONDecodeError:
                        pass
            except Exception as e:
                logger.error(f"流式读取失败: {e}")
            yield {"message": {"role": "assistant", "content": full_content}, "done": True}
        else:
            content = resp_data.get("choices", [{}])[0].get("message", {}).get("content", "")
            yield {"message": {"role": "assistant", "content": content}, "done": True}

    except Exception as e:
        logger.error(f"GGUF 模型生成响应失败: {e}")
        yield {"error": str(e)}


SENTENCE_SPLITTERS = ['。', '！', '？', '.\n', '!\n', '?\n', '\n\n', '。\n', '！\n', '？\n']

_MIN_SENTENCE_LENGTH = 4


def _split_into_sentences(text: str) -> list:
    """将文本分割成句子，支持中英文标点"""
    if not text or not text.strip():
        return []

    sentences = []
    current = ""
    for char in text:
        current += char
        if char in '。！？\n':
            if len(current.strip()) >= _MIN_SENTENCE_LENGTH:
                sentences.append(current.strip())
                current = ""
            elif current.strip():
                current = current.strip() + " "
                if len(current) >= _MIN_SENTENCE_LENGTH * 3:
                    sentences.append(current.strip())
                    current = ""

    if current.strip() and len(current.strip()) >= _MIN_SENTENCE_LENGTH:
        sentences.append(current.strip())
    elif current.strip():
        if sentences:
            sentences[-1] = sentences[-1] + current.strip()
        else:
            sentences.append(current.strip())

    return sentences


def _normalize_sentence(s: str) -> str:
    """标准化句子用于比较（去除多余空白、小写化、去除标点）"""
    s = re.sub(r'[，,、；;：:\u201c\u201d\u2018\u2019\'\"()\uff08\uff09\[\]\u3010\u3011\s]+', ' ', s)
    return ' '.join(s.split()).lower().strip()


class SentenceCache:
    """句子缓存，用于检测上下文级重复"""

    def __init__(self, similarity_threshold: float = 0.80, max_cache_size: int = 100):
        self.sentences: list = []
        self.normalized: list = []
        self.similarity_threshold = similarity_threshold
        self.max_cache_size = max_cache_size

    def add(self, sentence: str):
        """添加句子到缓存"""
        if not sentence or len(sentence) < _MIN_SENTENCE_LENGTH:
            return
        norm = _normalize_sentence(sentence)
        if not norm or norm in self.normalized:
            return
        self.sentences.append(sentence)
        self.normalized.append(norm)
        if len(self.sentences) > self.max_cache_size:
            self.sentences.pop(0)
            self.normalized.pop(0)

    def is_duplicate(self, sentence: str) -> bool:
        """检查句子是否与历史句子重复"""
        if not sentence or len(sentence) < _MIN_SENTENCE_LENGTH:
            return False
        norm = _normalize_sentence(sentence)
        if not norm:
            return False
        if norm in self.normalized:
            return True
        for existing_norm in self.normalized:
            if self._similarity(norm, existing_norm) >= self.similarity_threshold:
                return True
        return False

    def _similarity(self, s1: str, s2: str) -> float:
        """计算两个句子的相似度（基于字符级n-gram，比词级更准确）"""
        if s1 == s2:
            return 1.0
        if abs(len(s1) - len(s2)) > max(len(s1), len(s2)) * 0.5:
            return 0.0
        n = 2
        ngrams1 = set(s1[i:i+n] for i in range(len(s1)-n+1))
        ngrams2 = set(s2[i:i+n] for i in range(len(s2)-n+1))
        if not ngrams1 or not ngrams2:
            return 0.0
        common = ngrams1 & ngrams2
        total = ngrams1 | ngrams2
        return len(common) / len(total)

    def clear(self):
        """清空缓存"""
        self.sentences.clear()
        self.normalized.clear()


def generate_chat_response(
    model_name: str,
    messages: List[Dict[str, str]],
    temperature: float = 0.7,
    max_tokens: int = 2048,
    stream: bool = False,
    repeat_penalty: float = 1.1,
    top_k: int = 40,
    top_p: float = 0.9,
    enable_repeat_check: bool = True
) -> Generator[Dict[str, Any], None, None]:
    """生成对话响应 - 自动检测模型格式"""
    
    if is_gguf_model(model_name):
        logger.info(f"检测到 GGUF 模型: {model_name}")
        yield from generate_gguf_chat_response(
            model_name, messages, temperature, max_tokens, stream,
            repeat_penalty=repeat_penalty, top_k=top_k, top_p=top_p
        )
        return
    
    if not TRANSFORMERS_AVAILABLE:
        yield {"error": "Transformers 库不可用"}
        return
    
    model, tokenizer = load_local_model(model_name)
    
    if not model or not tokenizer:
        yield {"error": f"无法加载模型: {model_name}"}
        return
    
    try:
        prompt = tokenizer.apply_chat_template(
            messages,
            tokenize=False,
            add_generation_prompt=True
        )
        
        inputs = tokenizer(prompt, return_tensors="pt").to(model.device)
        
        sentence_cache = SentenceCache()
        repeat_detected = False
        suggested_temperature = None
        
        if stream:
            streamer = TextIteratorStreamer(
                tokenizer,
                skip_prompt=True,
                skip_special_tokens=True
            )

            generation_kwargs = dict(
                input_ids=inputs["input_ids"],
                streamer=streamer,
                max_new_tokens=max_tokens,
                temperature=temperature,
                top_k=top_k,
                top_p=top_p,
                repetition_penalty=repeat_penalty,
                do_sample=True,
                pad_token_id=tokenizer.pad_token_id,
                eos_token_id=tokenizer.eos_token_id
            )

            thread = Thread(target=model.generate, kwargs=generation_kwargs)
            thread.start()

            buffer = ""

            for text in streamer:
                buffer += text
                sentences = _split_into_sentences(buffer)

                if len(sentences) > 1:
                    complete_sentences = sentences[:-1]
                    buffer = sentences[-1]

                    for sent in complete_sentences:
                        if sentence_cache.is_duplicate(sent):
                            logger.info(f"检测到重复句子: {sent[:50]}...")
                            repeat_detected = True
                            if not suggested_temperature:
                                suggested_temperature = min(temperature + 0.15, 1.2)
                            continue
                        sentence_cache.add(sent)
                        yield {
                            "message": {"role": "assistant", "content": sent},
                            "done": False,
                            "repeat_detected": repeat_detected,
                            "suggested_temperature": suggested_temperature
                        }
                else:
                    last_char = text[-1] if text else ""
                    if last_char in '。！？':
                        if sentence_cache.is_duplicate(buffer):
                            logger.info(f"检测到重复句子: {buffer[:50]}...")
                            repeat_detected = True
                            if not suggested_temperature:
                                suggested_temperature = min(temperature + 0.15, 1.2)
                            buffer = ""
                            continue
                        sentence_cache.add(buffer)
                        yield {
                            "message": {"role": "assistant", "content": buffer},
                            "done": False,
                            "repeat_detected": repeat_detected,
                            "suggested_temperature": suggested_temperature
                        }
                        buffer = ""

            if buffer:
                if sentence_cache.is_duplicate(buffer):
                    logger.info(f"检测到重复句子: {buffer[:50]}...")
                    repeat_detected = True
                    if not suggested_temperature:
                        suggested_temperature = min(temperature + 0.15, 1.2)
                else:
                    sentence_cache.add(buffer)
                    yield {
                        "message": {"role": "assistant", "content": buffer},
                        "done": False,
                        "repeat_detected": repeat_detected,
                        "suggested_temperature": suggested_temperature
                    }

            yield {
                "message": {"role": "assistant", "content": ""},
                "done": True,
                "repeat_detected": repeat_detected,
                "suggested_temperature": suggested_temperature
            }

            thread.join()
            
        else:
            with torch.no_grad():
                outputs = model.generate(
                    **inputs,
                    max_new_tokens=max_tokens,
                    temperature=temperature,
                    top_k=top_k,
                    top_p=top_p,
                    repetition_penalty=repeat_penalty,
                    do_sample=True,
                    pad_token_id=tokenizer.pad_token_id,
                    eos_token_id=tokenizer.eos_token_id
                )
            
            response = tokenizer.decode(
                outputs[0][inputs["input_ids"].shape[1]:],
                skip_special_tokens=True
            )
            
            yield {
                "message": {"role": "assistant", "content": response},
                "done": True,
                "repeat_detected": repeat_detected,
                "suggested_temperature": suggested_temperature
            }
            
    except Exception as e:
        logger.error(f"生成响应失败: {e}")
        yield {"error": str(e)}


def is_local_model_available(model_name: str) -> bool:
    """检查本地模型是否可用"""
    if is_gguf_model(model_name):
        return get_gguf_model_path(model_name) is not None
    return get_local_model_path(model_name) is not None


def get_available_gguf_models() -> List[Dict[str, str]]:
    """获取所有可用的 GGUF 模型列表"""
    available = []
    discovered = _discover_gguf_models()

    for name, path in discovered.items():
        file_size = os.path.getsize(path) / (1024 * 1024 * 1024)
        available.append({
            "name": name,
            "path": path,
            "size_gb": round(file_size, 2),
            "format": "gguf"
        })

    return available


def get_available_safetensors_models() -> List[Dict[str, str]]:
    """获取所有可用的 safetensors 模型列表"""
    available = []
    discovered = _discover_safetensors_models()

    for name, path in discovered.items():
        dir_size = _get_dir_size(path) / (1024 * 1024 * 1024)
        available.append({
            "name": name,
            "path": path,
            "size_gb": round(dir_size, 2),
            "format": "safetensors"
        })

    return available


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


def unload_all_models():
    """卸载所有模型，释放内存"""
    global _model_cache, _tokenizer_cache, _gguf_model_cache

    for name, manager in list(_llama_server_manager_cache.items()):
        try:
            manager.stop()
        except Exception:
            pass
    _llama_server_manager_cache.clear()

    if TRANSFORMERS_AVAILABLE:
        for name in list(_model_cache.keys()):
            try:
                del _model_cache[name]
                del _tokenizer_cache[name]
            except Exception:
                pass

        import gc
        gc.collect()

        try:
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
        except Exception:
            pass

    _gguf_model_cache.clear()

    logger.info("所有本地模型已卸载")
