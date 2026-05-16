# -*- coding: utf-8 -*-
"""
本地模型加载器 - 支持 safetensors (Transformers) 和 GGUF (llama-server HTTP API) 模型

核心改进:
  1. 后台线程消费 llama-server stdout，防止管道堵塞导致进程崩溃
  2. 缓存失效时正确终止旧进程，避免僵尸进程
  3. 定期健康检查线程，主动发现并修复失效的 llama-server
  4. 请求失败自动重试（重启服务器后重试一次）
  5. 端口池复用，避免长时间运行后端口耗尽
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
import signal
from typing import Optional, List, Dict, Any, Generator, Set

logger = logging.getLogger(__name__)

SERVER_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(SERVER_DIR)

LLAMA_SERVER_EXE = os.path.join(PROJECT_DIR, "llama", "llama-server.exe")
LLAMA_SERVER_HOST = "127.0.0.1"
GPU_LAYERS = int(os.environ.get("LLAMA_GPU_LAYERS", "40"))
VULKAN_SDK_DIR = os.environ.get("VULKAN_SDK", r"D:\Explore\Vulkan SDK 1.4.341.1")

HEALTH_CHECK_INTERVAL = 30
HEALTH_CHECK_RETRIES = 2
PORT_RANGE_START = 8081
PORT_RANGE_END = 8099
STARTUP_TIMEOUT = 120
REQUEST_TIMEOUT = 3600
RETRY_ON_FAILURE = True

import multiprocessing
_DEFAULT_THREADS = min(multiprocessing.cpu_count(), 16)

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

_reasoning_enabled: bool = False


def set_reasoning_mode(enabled: bool):
    global _reasoning_enabled
    _reasoning_enabled = enabled
    logger.info(f"推理模式已设置为: {'开启' if enabled else '关闭'}")


def get_reasoning_mode() -> bool:
    return _reasoning_enabled


GGUF_SEARCH_DIRS = [
    os.path.join(PROJECT_DIR, "models", "llm", "gguf"),
    os.path.join(PROJECT_DIR, "models", "llm"),
    os.path.join(PROJECT_DIR, "models", "gguf"),
    os.path.join(PROJECT_DIR, "models"),
    os.path.join(PROJECT_DIR, ".ollama", "models"),
]

if os.environ.get('LOCAL_MODELS_DIR'):
    GGUF_SEARCH_DIRS.insert(0, os.environ.get('LOCAL_MODELS_DIR'))

SAFETENSORS_SEARCH_DIRS = [
    os.path.join(PROJECT_DIR, "models", "llm", "hf"),
    os.path.join(PROJECT_DIR, "models", "vlm"),
    os.path.join(PROJECT_DIR, "models", "llm"),
]


class PortPool:
    """端口池管理器，支持分配与回收"""

    def __init__(self, start: int = PORT_RANGE_START, end: int = PORT_RANGE_END):
        self._lock = threading.Lock()
        self._available: List[int] = list(range(start, end + 1))
        self._used: Set[int] = set()

    def allocate(self) -> int:
        with self._lock:
            if not self._available:
                for port in list(self._used):
                    if not _is_port_in_use(port):
                        self._used.discard(port)
                        self._available.append(port)
                        break
            if not self._available:
                raise RuntimeError("无可用端口")
            port = self._available.pop(0)
            self._used.add(port)
            return port

    def release(self, port: int):
        with self._lock:
            if port in self._used:
                self._used.discard(port)
                self._available.append(port)

    def used_ports(self) -> Set[int]:
        with self._lock:
            return set(self._used)


_port_pool = PortPool()


def _is_port_in_use(port: int) -> bool:
    import socket
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(1)
        return s.connect_ex(("127.0.0.1", port)) == 0


_DISCOVER_CACHE_TTL = 30
_gguf_discover_cache = {"data": None, "timestamp": 0}
_safetensors_discover_cache = {"data": None, "timestamp": 0}
_discover_cache_lock = threading.Lock()


def invalidate_discover_cache():
    """使发现缓存失效（模型文件变更时调用）"""
    with _discover_cache_lock:
        _gguf_discover_cache["data"] = None
        _gguf_discover_cache["timestamp"] = 0
        _safetensors_discover_cache["data"] = None
        _safetensors_discover_cache["timestamp"] = 0


def _discover_gguf_models() -> Dict[str, str]:
    with _discover_cache_lock:
        now = time.time()
        if _gguf_discover_cache["data"] is not None and (now - _gguf_discover_cache["timestamp"]) < _DISCOVER_CACHE_TTL:
            return _gguf_discover_cache["data"]

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

    with _discover_cache_lock:
        _gguf_discover_cache["data"] = discovered
        _gguf_discover_cache["timestamp"] = time.time()
    return discovered


def _discover_safetensors_models() -> Dict[str, str]:
    with _discover_cache_lock:
        now = time.time()
        if _safetensors_discover_cache["data"] is not None and (now - _safetensors_discover_cache["timestamp"]) < _DISCOVER_CACHE_TTL:
            return _safetensors_discover_cache["data"]

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

    with _discover_cache_lock:
        _safetensors_discover_cache["data"] = discovered
        _safetensors_discover_cache["timestamp"] = time.time()
    return discovered


def _wait_for_server(host: str, port: int, timeout: int = STARTUP_TIMEOUT, process=None) -> bool:
    start = time.time()
    interval = 0.5
    while time.time() - start < timeout:
        if process is not None and process.poll() is not None:
            return False
        try:
            req = urllib.request.Request(f"http://{host}:{port}/v1/models")
            resp = urllib.request.urlopen(req, timeout=5)
            if resp.status == 200:
                return True
        except Exception:
            pass
        elapsed = time.time() - start
        if elapsed < 10:
            interval = 0.5
        elif elapsed < 30:
            interval = 1.0
        else:
            interval = 2.0
        time.sleep(interval)
    return False


def _consume_stdout(proc: subprocess.Popen, model_name: str):
    """后台线程持续消费子进程 stdout，防止管道堵塞导致进程挂起或崩溃"""
    try:
        for line in proc.stdout:
            line_str = line.strip()
            if line_str:
                logger.debug(f"[llama-server:{model_name}] {line_str}")
    except Exception:
        pass
    finally:
        try:
            proc.stdout.close()
        except Exception:
            pass


class LlamaServerManager:
    """llama-server 进程管理器，负责启动/停止/健康检查/请求"""

    def __init__(self, model_path: str, model_name: str, n_ctx: int = 8192, n_threads: int = 0):
        self.model_path = model_path
        self.model_name = model_name
        if n_ctx <= 0:
            logger.warning(f"LlamaServerManager n_ctx={n_ctx} 无效，回退到8192")
            n_ctx = 8192
        self.n_ctx = n_ctx
        self.n_threads = n_threads if n_threads > 0 else _DEFAULT_THREADS
        self.process: Optional[subprocess.Popen] = None
        self.port: int = 0
        self.host = LLAMA_SERVER_HOST
        self._bat_file: Optional[str] = None
        self._reader_thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()
        self._last_active: float = 0.0

    def is_alive(self) -> bool:
        if self.process is None:
            return False
        return self.process.poll() is None

    def health_check(self) -> bool:
        if not self.is_alive():
            return False
        try:
            resp = urllib.request.urlopen(
                f"http://{self.host}:{self.port}/v1/models", timeout=3
            )
            return resp.status == 200
        except Exception:
            return False

    def start(self) -> bool:
        with self._lock:
            return self._start_internal()

    def _start_internal(self) -> bool:
        if self.is_alive() and self.health_check():
            logger.info(f"llama-server 已运行且健康: {self.model_name} @ port {self.port}")
            return True

        if self.is_alive():
            logger.warning(f"llama-server 进程存活但健康检查失败，先停止: {self.model_name}")
            self._stop_internal()

        if not os.path.exists(self.model_path):
            logger.error(f"模型文件不存在: {self.model_path}")
            return False

        if not os.path.exists(LLAMA_SERVER_EXE):
            logger.error(f"llama-server 不存在: {LLAMA_SERVER_EXE}")
            return False

        self.port = _port_pool.allocate()

        cmd = [
            LLAMA_SERVER_EXE,
            "-m", self.model_path,
            "-t", str(self.n_threads),
            "--host", self.host,
            "--port", str(self.port),
            "-ngl", str(GPU_LAYERS),
        ]

        reasoning_mode = "on" if _reasoning_enabled else "off"
        cmd.extend(["--reasoning", reasoning_mode])
        if _reasoning_enabled:
            cmd.extend(["--reasoning-format", "deepseek"])
            chat_template_path = os.path.join(os.path.dirname(LLAMA_SERVER_EXE), "qwen3_thinking.jinja")
            if os.path.exists(chat_template_path):
                cmd.extend(["--chat-template-file", chat_template_path, "--jinja"])
                logger.info(f"推理模式启用，使用 chat template: {chat_template_path}")

        logger.info(f"启动 llama-server: {' '.join(cmd)} (reasoning={reasoning_mode})")
        try:
            import tempfile
            bat_content = (
                f"@echo off\r\nchcp 65001 >nul 2>&1\r\n"
                + ' '.join('"' + c + '"' if ' ' in c else c for c in cmd)
                + " %*\r\n"
            )
            bat_file = tempfile.NamedTemporaryFile(
                mode='w', suffix='.bat', delete=False,
                encoding='utf-8', dir=tempfile.gettempdir()
            )
            bat_file.write(bat_content)
            bat_file.close()

            vulkan_bin = os.path.join(VULKAN_SDK_DIR, "Bin")
            subproc_env = os.environ.copy()
            if os.path.isdir(vulkan_bin):
                subproc_env["PATH"] = vulkan_bin + ";" + subproc_env.get("PATH", "")

            self.process = subprocess.Popen(
                [bat_file.name],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                env=subproc_env,
                creationflags=subprocess.CREATE_NEW_PROCESS_GROUP,
            )
            self._bat_file = bat_file.name

            self._reader_thread = threading.Thread(
                target=_consume_stdout,
                args=(self.process, self.model_name),
                daemon=True,
                name=f"llama-stdout-{self.model_name}",
            )
            self._reader_thread.start()

        except Exception as e:
            logger.error(f"启动 llama-server 失败: {e}")
            _port_pool.release(self.port)
            self.port = 0
            return False

        logger.info(f"等待服务器就绪 (host={self.host}, port={self.port}, timeout={STARTUP_TIMEOUT})...")
        if not _wait_for_server(self.host, self.port, timeout=STARTUP_TIMEOUT, process=self.process):
            logger.error(f"llama-server 启动超时: {self.model_name}")
            if self.process.poll() is not None:
                logger.error(f"进程已退出, returncode={self.process.returncode}")
            self._stop_internal()
            return False

        self._last_active = time.time()
        logger.info(f"llama-server 启动成功: {self.model_name} @ http://{self.host}:{self.port}")
        return True

    def stop(self):
        with self._lock:
            self._stop_internal()

    def _stop_internal(self):
        if self.process is not None:
            try:
                os.kill(self.process.pid, signal.CTRL_BREAK_EVENT)
                self.process.wait(timeout=5)
            except Exception:
                try:
                    self.process.terminate()
                    self.process.wait(timeout=5)
                except Exception:
                    try:
                        self.process.kill()
                        self.process.wait(timeout=3)
                    except Exception:
                        pass

            if self._reader_thread and self._reader_thread.is_alive():
                self._reader_thread.join(timeout=3)

            self.process = None
            self._reader_thread = None

        if self.port:
            _port_pool.release(self.port)
            self.port = 0

        if self._bat_file:
            try:
                os.unlink(self._bat_file)
            except Exception:
                pass
            self._bat_file = None

        logger.info(f"llama-server 已停止: {self.model_name}")

    def chat(self, messages: List[Dict], temperature: float = 0.7, max_tokens: int = -1,
             stream: bool = False, repeat_penalty: float = 1.1, top_k: int = 40,
             top_p: float = 0.9) -> Dict[str, Any]:
        url = f"http://{self.host}:{self.port}/v1/chat/completions"
        payload = {
            "model": os.path.basename(self.model_path),
            "messages": messages,
            "temperature": temperature,
            "stream": stream,
            "repeat_penalty": repeat_penalty,
            "top_k": top_k,
            "top_p": top_p,
        }
        if max_tokens is not None and max_tokens > 0:
            payload["max_tokens"] = max_tokens
        try:
            if stream:
                resp = requests.post(url, json=payload, stream=True, timeout=REQUEST_TIMEOUT)
                if resp.status_code != 200:
                    error_body = resp.text[:500]
                    logger.error(f"llama-server 流式请求失败: status={resp.status_code}, body={error_body}")
                    return {"error": f"llama-server 返回 {resp.status_code}: {error_body}"}
                self._last_active = time.time()
                return {"_stream_response": resp}
            resp = requests.post(url, json=payload, timeout=REQUEST_TIMEOUT)
            if resp.status_code != 200:
                error_body = resp.text[:500]
                logger.error(f"llama-server 请求失败: status={resp.status_code}, body={error_body}")
                return {"error": f"llama-server 返回 {resp.status_code}: {error_body}"}
            self._last_active = time.time()
            return resp.json()
        except Exception as e:
            logger.error(f"llama-server 请求异常: {e}")
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
            resp = requests.post(url, json=payload, timeout=REQUEST_TIMEOUT)
            resp.raise_for_status()
            self._last_active = time.time()
            return resp.json()
        except Exception as e:
            logger.error(f"llama-server completion 请求失败: {e}")
            return {"error": str(e)}


_llama_server_manager_cache: Dict[str, LlamaServerManager] = {}
_cache_lock = threading.Lock()
_model_start_locks: Dict[str, threading.Lock] = {}
_model_start_locks_guard = threading.Lock()


def _get_model_start_lock(cache_key: str) -> threading.Lock:
    with _model_start_locks_guard:
        if cache_key not in _model_start_locks:
            _model_start_locks[cache_key] = threading.Lock()
        return _model_start_locks[cache_key]


def _get_llama_server(model_name: str, n_ctx: int = 8192) -> Optional[LlamaServerManager]:
    cache_key = f"{model_name}_{n_ctx}"

    with _cache_lock:
        if cache_key in _llama_server_manager_cache:
            manager = _llama_server_manager_cache[cache_key]
            if manager.is_alive() and manager.health_check():
                return manager
            logger.warning(f"缓存的 llama-server 已失效，正在清理并重新启动: {model_name}")
            manager.stop()
            del _llama_server_manager_cache[cache_key]

    start_lock = _get_model_start_lock(cache_key)
    with start_lock:
        with _cache_lock:
            if cache_key in _llama_server_manager_cache:
                manager = _llama_server_manager_cache[cache_key]
                if manager.is_alive() and manager.health_check():
                    return manager

        model_path = get_gguf_model_path(model_name)
        if not model_path:
            logger.error(f"找不到 GGUF 模型: {model_name}")
            return None

        manager = LlamaServerManager(model_path, model_name, n_ctx=n_ctx)
        if not manager.start():
            return None

        with _cache_lock:
            _llama_server_manager_cache[cache_key] = manager

    return manager


def clear_llama_server_cache():
    with _cache_lock:
        for key, manager in list(_llama_server_manager_cache.items()):
            if manager:
                manager.stop()
        _llama_server_manager_cache.clear()
    logger.info("llama-server 缓存已清除")


def _health_check_loop():
    """定期检查所有 llama-server 实例的健康状态"""
    while True:
        time.sleep(HEALTH_CHECK_INTERVAL)
        try:
            with _cache_lock:
                items = list(_llama_server_manager_cache.items())

            for cache_key, manager in items:
                if not manager.is_alive():
                    logger.warning(f"[健康检查] llama-server 进程已死: {manager.model_name}, 将清理缓存")
                    with _cache_lock:
                        manager.stop()
                        _llama_server_manager_cache.pop(cache_key, None)
                    continue

                failed = True
                for attempt in range(HEALTH_CHECK_RETRIES):
                    if manager.health_check():
                        failed = False
                        break
                    if attempt < HEALTH_CHECK_RETRIES - 1:
                        time.sleep(3)
                if failed:
                    logger.warning(f"[健康检查] llama-server 健康检查连续{HEALTH_CHECK_RETRIES}次失败: {manager.model_name}, 将重启")
                    with _cache_lock:
                        manager.stop()
                        _llama_server_manager_cache.pop(cache_key, None)
        except Exception as e:
            logger.error(f"[健康检查] 异常: {e}")


_health_thread: Optional[threading.Thread] = None
_health_thread_started = False


def start_health_monitor():
    global _health_thread, _health_thread_started
    if _health_thread_started:
        return
    _health_thread_started = True
    _health_thread = threading.Thread(
        target=_health_check_loop,
        daemon=True,
        name="llama-health-monitor",
    )
    _health_thread.start()
    logger.info("llama-server 健康监控已启动")


def _fuzzy_match_model_name(query: str, candidate: str) -> bool:
    """分隔符边界匹配：query 和 candidate 在分隔符处对齐才算匹配"""
    if query == candidate:
        return True
    sep = re.compile(r'[-_\s]')
    q_parts = {p for p in sep.split(query) if len(p) > 1}
    c_parts = {p for p in sep.split(candidate) if len(p) > 1}
    common = q_parts & c_parts
    if len(common) >= 2:
        return True
    if candidate.startswith(query) and (len(candidate) == len(query) or sep.match(candidate[len(query)])):
        return True
    if query.startswith(candidate) and (len(query) == len(candidate) or sep.match(query[len(candidate)])):
        return True
    return False


def is_gguf_model(model_name: str) -> bool:
    return get_gguf_model_path(model_name) is not None


def get_gguf_model_path(model_name: str) -> Optional[str]:
    discovered = _discover_gguf_models()
    cleaned = model_name.lower().replace(':latest', '').replace(':', '-')

    if cleaned in discovered:
        return discovered[cleaned]

    for name, path in discovered.items():
        name_lower = name.lower()
        if _fuzzy_match_model_name(cleaned, name_lower):
            return path

    from utils.config import GGUF_MODEL_CONFIG
    for config_key, config_val in GGUF_MODEL_CONFIG.items():
        config_key_clean = config_key.lower().replace(':latest', '').replace(':', '-')
        if _fuzzy_match_model_name(cleaned, config_key_clean):
            cfg_path = config_val.get('path', '')
            if cfg_path and os.path.exists(cfg_path):
                return cfg_path
            logger.warning(f"GGUF_MODEL_CONFIG 中 {config_key} 的路径不存在: {cfg_path}")

    if os.path.isabs(model_name) and model_name.endswith('.gguf') and os.path.exists(model_name):
        return model_name

    return None


def get_local_model_path(model_name: str) -> Optional[str]:
    discovered = _discover_safetensors_models()
    cleaned = model_name.lower().replace(':latest', '').replace(':', '-')

    if cleaned in discovered:
        return discovered[cleaned]

    for name, path in discovered.items():
        name_lower = name.lower()
        if _fuzzy_match_model_name(cleaned, name_lower):
            return path

    return None


def load_gguf_model(model_name: str, n_ctx: int = 8192, n_gpu_layers: int = 0):
    manager = _get_llama_server(model_name, n_ctx=n_ctx)
    if not manager:
        logger.error(f"无法启动 llama-server: {model_name}")
        return None
    logger.info(f"GGUF 模型已就绪: {model_name} @ port {manager.port}")
    return ('llama_server', manager)


def load_local_model(model_name: str):
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
    max_tokens: int = -1,
    stream: bool = False,
    n_ctx: int = 8192,
    repeat_penalty: float = 1.1,
    top_k: int = 40,
    top_p: float = 0.9,
    _retry_count: int = 0,
) -> Generator[Dict[str, Any], None, None]:
    manager = _get_llama_server(model_name, n_ctx=n_ctx)
    if not manager:
        yield {"error": f"无法加载 GGUF 模型: {model_name}"}
        return

    logger.info(f"[剧场] GGUF 请求: model={model_name}, port={manager.port}, "
                f"msgs={len(messages)}, temp={temperature}, max_tokens={max_tokens}, stream={stream}")

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
            if RETRY_ON_FAILURE and _retry_count == 0:
                logger.warning(f"GGUF 请求失败，尝试重启模型重试: {model_name}, 错误: {resp_data['error']}")
                with _cache_lock:
                    cache_key = f"{model_name}_{n_ctx}"
                    old = _llama_server_manager_cache.pop(cache_key, None)
                    if old:
                        old.stop()
                yield from generate_gguf_chat_response(
                    model_name, messages, temperature, max_tokens, stream,
                    repeat_penalty=repeat_penalty, top_k=top_k, top_p=top_p,
                    n_ctx=n_ctx, _retry_count=1,
                )
                return
            yield {"error": resp_data["error"]}
            return

        if stream:
            yield from _handle_stream_response(resp_data, model_name)
        else:
            msg_obj = resp_data.get("choices", [{}])[0].get("message", {})
            content = msg_obj.get("content", "")
            reasoning = msg_obj.get("reasoning_content", "")
            if not content and reasoning:
                content = reasoning
                reasoning = ""
            result_msg = {"role": "assistant", "content": content}
            if reasoning:
                result_msg["thinking"] = reasoning
            yield {"message": result_msg, "done": True}

    except Exception as e:
        if RETRY_ON_FAILURE and _retry_count == 0:
            logger.warning(f"GGUF 生成异常，尝试重启模型重试: {model_name}, 错误: {e}")
            with _cache_lock:
                cache_key = f"{model_name}_{n_ctx}"
                old = _llama_server_manager_cache.pop(cache_key, None)
                if old:
                    old.stop()
            yield from generate_gguf_chat_response(
                model_name, messages, temperature, max_tokens, stream,
                repeat_penalty=repeat_penalty, top_k=top_k, top_p=top_p,
                n_ctx=n_ctx, _retry_count=1,
            )
            return
        logger.error(f"GGUF 模型生成响应失败: {e}")
        yield {"error": str(e)}


def _handle_stream_response(resp_data: Dict, model_name: str) -> Generator[Dict[str, Any], None, None]:
    resp_wrapper = resp_data.get("_stream_response")
    if not resp_wrapper:
        yield {"error": "流式响应获取失败"}
        return

    full_content = ""
    full_thinking = ""
    chunk_count = 0

    try:
        for line in resp_wrapper.iter_lines():
            if line is None:
                continue
            line_str = line.decode("utf-8", errors="replace").strip()
            if line_str == "data: [DONE]":
                break
            if not line_str.startswith("data: "):
                continue
            try:
                obj = json.loads(line_str[6:])
                delta = obj.get("choices", [{}])[0].get("delta", {})
                content = delta.get("content") or ""
                reasoning = delta.get("reasoning_content") or ""
                chunk_msg = {"role": "assistant", "content": content}
                if reasoning:
                    full_thinking += reasoning
                    chunk_msg["thinking"] = reasoning
                if content:
                    full_content += content
                chunk_count += 1
                if chunk_count <= 3 or chunk_count % 100 == 0:
                    logger.debug(
                        f"[GGUF] chunk {chunk_count}: "
                        f"reasoning={len(reasoning)}, content={len(content)}, "
                        f"total_thinking={len(full_thinking)}, total_content={len(full_content)}"
                    )
                if content or reasoning:
                    yield {"message": chunk_msg, "done": False}
            except json.JSONDecodeError:
                pass
    except Exception as e:
        logger.error(f"流式读取失败: {e}")
        import traceback
        logger.error(traceback.format_exc())

    final_msg = {"role": "assistant", "content": full_content}
    if full_thinking:
        final_msg["thinking"] = full_thinking
    logger.debug(
        f"[GGUF] final: content_len={len(full_content)}, "
        f"thinking_len={len(full_thinking)}, total_chunks={chunk_count}"
    )
    yield {"message": final_msg, "done": True}


SENTENCE_SPLITTERS = ['。', '！', '？', '.\n', '!\n', '?\n', '\n\n', '。\n', '！\n', '？\n']
_MIN_SENTENCE_LENGTH = 4


def _split_into_sentences(text: str) -> list:
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
    enable_repeat_check: bool = True,
    n_ctx: int = 8192
) -> Generator[Dict[str, Any], None, None]:
    if is_gguf_model(model_name):
        logger.info(f"检测到 GGUF 模型: {model_name}, n_ctx={n_ctx}")
        yield from generate_gguf_chat_response(
            model_name, messages, temperature, max_tokens, stream,
            repeat_penalty=repeat_penalty, top_k=top_k, top_p=top_p,
            n_ctx=n_ctx
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
            yield from _stream_transformers_response(
                model, tokenizer, inputs, sentence_cache,
                temperature, max_tokens, repeat_penalty, top_k, top_p
            )
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


def _stream_transformers_response(
    model, tokenizer, inputs, sentence_cache: SentenceCache,
    temperature: float, max_tokens: int, repeat_penalty: float,
    top_k: int, top_p: float
) -> Generator[Dict[str, Any], None, None]:
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
    repeat_detected = False
    suggested_temperature = None

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


def is_local_model_available(model_name: str) -> bool:
    if is_gguf_model(model_name):
        return True
    return get_local_model_path(model_name) is not None


def get_available_models() -> List[str]:
    models = []
    discovered_gguf = _discover_gguf_models()
    discovered_st = _discover_safetensors_models()
    models.extend(discovered_gguf.keys())
    models.extend(discovered_st.keys())
    return models


def unload_model(model_name: str):
    with _cache_lock:
        prefix = f"{model_name}_"
        keys_to_remove = [
            k for k in _llama_server_manager_cache
            if k.startswith(prefix) and k[len(prefix):].isdigit()
        ]
        for key in keys_to_remove:
            manager = _llama_server_manager_cache.pop(key)
            if manager:
                manager.stop()

    if model_name in _model_cache:
        try:
            del _model_cache[model_name]
            del _tokenizer_cache[model_name]
        except Exception:
            pass

    logger.info(f"模型已卸载: {model_name}")


def get_available_gguf_models() -> List[Dict[str, str]]:
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
    global _model_cache, _tokenizer_cache, _gguf_model_cache

    with _cache_lock:
        for key, manager in list(_llama_server_manager_cache.items()):
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


start_health_monitor()
