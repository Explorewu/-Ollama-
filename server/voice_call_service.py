"""
语音通话服务模块

基于Qwen3-ASR + Qwen3.5-4B + Qwen3-TTS的实时语音交互系统
特点：低延迟、流式处理、单路通话、支持打断

架构流程：
用户语音 → Qwen3-ASR → 文本 → Qwen3.5-4B → 文本 → Qwen3-TTS → AI语音
     ↑                                                    ↓
     └──────────────── 打断检测 ←─────────────────────────┘

WebSocket协议：
- 客户端 → 服务器：音频流、控制指令
- 服务器 → 客户端：识别文本、AI回复、音频流

使用方法:
    python voice_call_service.py
    # 然后在前端连接 ws://localhost:5005/voice-call
"""

import os
import sys
import json
import time
import base64
import asyncio
import logging
import numpy as np
from typing import Dict, Optional, Any, Set
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

try:
    from unified_engine import UnifiedEngine
    _UNIFIED_ENGINE_AVAILABLE = True
except ImportError:
    try:
        from server.unified_engine import UnifiedEngine
        _UNIFIED_ENGINE_AVAILABLE = True
    except ImportError:
        _UNIFIED_ENGINE_AVAILABLE = False

# 添加项目根目录到路径
SERVER_DIR = Path(__file__).resolve().parent
PROJECT_DIR = SERVER_DIR.parent
sys.path.insert(0, str(SERVER_DIR))

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)-8s | %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

# 尝试导入WebSocket库
try:
    import websockets
    from websockets.server import WebSocketServerProtocol
    WEBSOCKET_AVAILABLE = True

    # 抑制 websockets 库内部握手失败的 ERROR 日志
    # 这些错误通常是浏览器预连接或健康检查导致的正常现象
    _ws_logger = logging.getLogger("websockets")
    _ws_logger.setLevel(logging.WARNING)
except ImportError:
    WEBSOCKET_AVAILABLE = False
    logger.warning("websockets库未安装，语音通话服务将不可用")
    logger.warning("安装命令: pip install websockets")


@dataclass
class CallSession:
    """通话会话状态"""
    session_id: str
    websocket: Any
    created_at: datetime = field(default_factory=datetime.now)
    
    # 音频缓冲区
    audio_buffer: bytes = field(default_factory=bytes)
    
    # 对话状态
    is_speaking: bool = False  # 用户是否正在说话
    is_ai_speaking: bool = False  # AI是否正在说话
    is_interrupted: bool = False  # 是否被打断
    
    # 对话历史
    conversation_history: list = field(default_factory=list)
    
    # 当前处理状态
    current_asr_text: str = ""  # 当前ASR识别文本
    current_ai_text: str = ""  # 当前AI回复文本
    
    # 统计信息
    total_user_messages: int = 0
    total_ai_messages: int = 0
    total_audio_bytes: int = 0


@dataclass
class VoiceCallConfig:
    """语音通话配置"""
    host: str = "0.0.0.0"
    port: int = 5005
    
    # 音频配置
    audio_sample_rate: int = 16000
    audio_chunk_ms: int = 100  # 100ms分片
    
    # ASR配置
    asr_buffer_chunks: int = 2  # 累积2个分片后识别（优化延迟）
    
    # TTS配置
    tts_speaker_id: str = "vivian"
    tts_speed: float = 1.0
    
    # LLM配置
    llm_model: str = "qwen2.5:3b"
    llm_max_tokens: int = 200
    llm_temperature: float = 0.7
    
    # 超时配置
    connection_timeout: int = 3000  # 30分钟无活动断开
    max_session_duration: int = 18000  # 最大通话时长30分钟


class MessageProtocol:
    """WebSocket消息协议"""
    
    @staticmethod
    def encode(msg_type: str, data: dict) -> str:
        """编码消息"""
        return json.dumps({
            "type": msg_type,
            "data": data,
            "timestamp": time.time()
        }, ensure_ascii=False)
    
    @staticmethod
    def decode(message: str) -> tuple:
        """解码消息"""
        try:
            obj = json.loads(message)
            return obj.get("type"), obj.get("data", {}), obj.get("timestamp", 0)
        except json.JSONDecodeError:
            logger.error(f"消息解码失败: {message[:100]}")
            return None, {}, 0


class VoiceCallService:
    """
    语音通话服务
    
    设计原则：
    1. 多路并发：支持多个chat-stream会话并发
    2. 流式处理：音频流实时处理，不缓存大量数据
    3. 低延迟：端到端延迟控制在500ms以内
    4. 容错处理：模型加载失败时优雅降级
    """
    
    MAX_CHAT_SESSIONS = 8
    
    def __init__(self, config: Optional[VoiceCallConfig] = None):
        self.config = config or VoiceCallConfig()
        self.protocol = MessageProtocol()
        
        # 会话管理 - 支持并发
        self.active_session: Optional[CallSession] = None
        self.active_chat_sessions: Dict[str, Any] = {}
        self.sessions_lock = asyncio.Lock()
        
        # 服务组件
        self.asr_service = None
        self.tts_service = None
        self.llm_service = None
        
        # 运行状态
        self.is_running = False
        
        logger.info(f"语音通话服务初始化完成，监听地址: {self.config.host}:{self.config.port}")
    
    async def initialize_services(self):
        """初始化服务组件"""
        logger.info("正在初始化服务组件...")
        
        # 初始化ASR服务 - 使用Qwen3-ASR
        try:
            from qwen3_asr_service import get_asr_service
            self.asr_service = get_asr_service()
            logger.info("Qwen3-ASR服务初始化完成")
        except Exception as e:
            logger.error(f"ASR服务初始化失败: {e}")
        
        # 初始化TTS服务
        try:
            # 使用 Qwen3-TTS（通过Ollama）
            from qwen3_tts_service import get_tts_service
            self.tts_service = get_tts_service()
            logger.info(f"[TTS Debug] Qwen3-TTS服务初始化完成, tts_service={self.tts_service is not None}")
            if self.tts_service:
                status = self.tts_service.check_status() if hasattr(self.tts_service, 'check_status') else {}
                logger.info(f"[TTS Debug] TTS状态: {status}")
        except Exception as e:
            logger.error(f"[TTS Debug] Qwen3-TTS服务初始化失败: {e}")
            import traceback
            logger.error(f"[TTS Debug] 初始化错误堆栈: {traceback.format_exc()}")
            self.tts_service = None
        
        # 初始化LLM服务（通过Ollama）
        try:
            # 这里使用现有的Ollama接口
            self.llm_service = None  # 将在处理时动态调用
            logger.info("LLM服务配置完成（通过Ollama）")
        except Exception as e:
            logger.error(f"LLM服务初始化失败: {e}")
        
        logger.info("服务组件初始化完成")
    
    async def handle_websocket(self, websocket: WebSocketServerProtocol):
        """处理WebSocket连接"""
        client_id = f"{websocket.remote_address[0]}:{websocket.remote_address[1]}"
        logger.info(f"新的WebSocket连接: {client_id}")
        
        # 获取请求路径（新版本websockets通过request属性获取）
        path = "/"
        if hasattr(websocket, 'request') and websocket.request:
            path = websocket.request.path
        elif hasattr(websocket, 'path'):
            path = websocket.path
        
        if path == "/chat-stream":
            try:
                await websocket.send(self.protocol.encode("connected", {"message": "chat ws connected"}))
                await self._handle_chat_ws(websocket)
            except Exception as e:
                logger.error(f"chat ws error: {e}")
            finally:
                try:
                    await websocket.close()
                except Exception:
                    pass
            return
        
        if path == "/group-stream":
            try:
                await websocket.send(self.protocol.encode("connected", {"message": "group ws connected"}))
                await self._handle_group_ws(websocket)
            except Exception as e:
                logger.error(f"group ws error: {e}")
            finally:
                try:
                    await websocket.close()
                except Exception:
                    pass
            return
        
        # 如果已有活跃会话，先关闭旧会话
        async with self.sessions_lock:
            if self.active_session is not None:
                old_session = self.active_session
                logger.info(f"关闭旧会话，接受新连接: {old_session.session_id}")
                try:
                    await old_session.websocket.close()
                except Exception:
                    pass
                self.active_session = None
        
        # 创建新会话
        session_id = f"call_{int(time.time())}_{client_id.replace(':', '_')}"
        session = CallSession(
            session_id=session_id,
            websocket=websocket
        )
        
        async with self.sessions_lock:
            self.active_session = session
        
        logger.info(f"通话会话已创建: {session_id}")
        
        try:
            # 发送连接成功消息
            await websocket.send(self.protocol.encode("connected", {
                "session_id": session_id,
                "message": "语音通话已连接"
            }))
            
            # 处理消息循环
            async for message in websocket:
                await self._handle_message(session, message)
                
        except websockets.exceptions.ConnectionClosed:
            logger.info(f"连接已关闭: {client_id}")
        except Exception as e:
            logger.error(f"处理连接时出错: {e}")
        finally:
            # 清理会话
            async with self.sessions_lock:
                if self.active_session == session:
                    self.active_session = None
            
            logger.info(f"通话会话已结束: {session_id}")
            logger.info(f"会话统计: 用户消息={session.total_user_messages}, "
                       f"AI消息={session.total_ai_messages}, "
                       f"音频数据={session.total_audio_bytes} bytes")
    
    async def _handle_chat_ws(self, websocket: Any):
        """文本对话WebSocket流式处理 - 支持并发"""
        session_id = f"chat_{int(time.time())}_{id(websocket)}"
        
        async with self.sessions_lock:
            if len(self.active_chat_sessions) >= self.MAX_CHAT_SESSIONS:
                await websocket.send(self.protocol.encode("error", {"message": f"并发会话数已达上限 ({self.MAX_CHAT_SESSIONS})"}))
                return
            self.active_chat_sessions[session_id] = websocket
        
        try:
            import aiohttp
            start_payload = await websocket.recv()
            msg_type, data, _ = self.protocol.decode(start_payload)
            if msg_type != "chat_start":
                await websocket.send(self.protocol.encode("error", {"message": "invalid start"}))
                return
            message = data.get("message", "")
            model = data.get("model", self.config.llm_model)
            thinking_chain_mode = data.get("thinking_chain_mode", "brief")
            thinking_enabled = data.get("thinking_enabled", False)
            history_messages = data.get("messages", [])
            chat_settings = data.get("chat_settings", {})
            if not message:
                await websocket.send(self.protocol.encode("error", {"message": "empty message"}))
                return
            system_prompt = data.get("system_prompt", "你是一个智能助手。")

            # 统一引擎增强：为WebSocket路径添加记忆和风格上下文
            if _UNIFIED_ENGINE_AVAILABLE:
                try:
                    engine = UnifiedEngine.get_instance()
                    persona_id = data.get("persona_id", "default")
                    engine.record_turn(session_id, "user", message, persona_id)
                    pre_result = engine.pre_enhance(session_id, message, persona_id)
                    addon = pre_result.get("system_prompt_addon", "")
                    if addon:
                        system_prompt = system_prompt + addon
                except Exception as e:
                    logger.debug(f"[UnifiedEngine] WebSocket pre_enhance failed (non-fatal): {e}")

            thinking_content = ""
            answer_content = ""
            in_thinking_phase = False

            # LSMPE流式消息持久化：创建消息记录
            lsmpe_msg_id = None
            try:
                from lsmpe_engine import LSMPEEngine, TYPE_AI_REPLY
                lsmpe = LSMPEEngine.get_instance()
                conv_id = data.get("conversation_id", session_id)
                lsmpe_msg = lsmpe.create_message(conv_id, TYPE_AI_REPLY, model)
                lsmpe_msg_id = lsmpe_msg.msg_id
            except Exception as e:
                logger.debug(f"LSMPE创建消息失败(非致命): {e}")

            # 优先使用本地模型 (llama.cpp)，通过后端API调用
            local_ok = await self._try_local_model_stream(
                websocket, model, system_prompt, message,
                thinking_chain_mode, history_messages, thinking_enabled, chat_settings,
                lsmpe_msg_id=lsmpe_msg_id, data=data, session_id=session_id
            )

            if not local_ok:
                # 降级到 Ollama
                ollama_ok = await self._try_ollama_stream(
                    websocket, model, system_prompt, message,
                    thinking_chain_mode, history_messages, thinking_enabled, chat_settings,
                    lsmpe_msg_id=lsmpe_msg_id, data=data, session_id=session_id
                )

                if not ollama_ok:
                    error_msg = f"模型服务不可用: {model}"
                    error_detail = "本地模型和 Ollama 均不可用"
                    await websocket.send(self.protocol.encode("error", {
                        "message": error_msg,
                        "detail": error_detail,
                        "model": model,
                        "suggestion": "请尝试: 1) 切换其他模型 2) 运行 ollama pull 重新下载 3) 检查模型文件是否完整"
                    }))
                    try:
                        from auto_heal import auto_heal
                        auto_heal.diagnose_and_repair(
                            error_message=error_msg,
                            source="voice_call.all_failed",
                            extra={"model": model},
                        )
                    except ImportError:
                        pass
        except Exception as e:
            try:
                await websocket.send(self.protocol.encode("error", {"message": str(e)}))
                try:
                    from auto_heal import auto_heal
                    auto_heal.diagnose_and_repair(
                        error_message=str(e),
                        source="voice_call.exception",
                        extra={"model": data.get("model", "") if isinstance(data, dict) else ""},
                    )
                except ImportError:
                    pass
            except Exception:
                pass
        finally:
            async with self.sessions_lock:
                self.active_chat_sessions.pop(session_id, None)
            logger.info(f"chat会话已结束: {session_id}, 当前并发数: {len(self.active_chat_sessions)}")

    async def _try_local_model_stream(self, websocket, model, system_prompt, message,
                                      thinking_chain_mode, history_messages=None, thinking_enabled=False, chat_settings=None,
                                      lsmpe_msg_id=None, data=None, session_id=None):
        """通过后端API调用本地模型 (llama.cpp) 流式响应"""
        import aiohttp
        try:
            from model_availability import check_model_availability
            avail = check_model_availability(model)
            if not avail['local_available']:
                logger.info(f"本地模型不可用: {model}，跳过")
                return False
        except ImportError:
            try:
                from local_model_loader import is_local_model_available
                if not is_local_model_available(model):
                    logger.info(f"本地模型不可用: {model}，跳过")
                    return False
            except ImportError:
                return False

        logger.info(f"本地模型可用，优先使用: {model}")

        fallback_chat_settings = {"thinking": thinking_enabled}
        if chat_settings and isinstance(chat_settings, dict):
            for key in ("temperature", "top_p", "top_k", "repeat_penalty", "max_response_tokens"):
                if key in chat_settings:
                    fallback_chat_settings[key] = chat_settings[key]

        payload = {
            "message": message,
            "model": model,
            "stream": True,
            "messages": history_messages or [],
            "system_prompt": system_prompt,
            "chat_settings": fallback_chat_settings
        }
        headers = {"X-Internal-Call": "true"}
        try:
            async with aiohttp.ClientSession() as sess:
                async with sess.post("http://127.0.0.1:5001/api/chat", json=payload, headers=headers, timeout=aiohttp.ClientTimeout(total=3600)) as resp:
                    if resp.status != 200:
                        body = await resp.text()
                        logger.warning(f"本地模型API返回 {resp.status}，将降级到 Ollama")
                        return False

                    thinking_content = ""
                    answer_content = ""
                    async for raw_line in resp.content:
                        line = raw_line.decode("utf-8").strip()
                        if not line or not line.startswith("data: "):
                            continue
                        json_str = line[6:]
                        if json_str.strip() == "[DONE]":
                            break
                        try:
                            obj = json.loads(json_str)
                        except json.JSONDecodeError:
                            continue

                        if "error" in obj:
                            logger.warning(f"本地模型流式错误: {obj['error']}")
                            return False

                        event = obj.get("event", "")
                        content = obj.get("content", "")
                        done = obj.get("done", False)

                        if event == "thinking_start":
                            await websocket.send(self.protocol.encode("thinking_start", {}))
                        elif event == "thinking_chunk" and content:
                            thinking_content += content
                            await websocket.send(self.protocol.encode("thinking_chunk", {
                                "content": content,
                                "model": model,
                                "created": int(time.time())
                            }))
                            if lsmpe_msg_id:
                                try:
                                    from lsmpe_engine import LSMPEEngine
                                    LSMPEEngine.get_instance().append_thinking(lsmpe_msg_id, content)
                                except Exception:
                                    pass
                        elif event == "answer_chunk" and content:
                            answer_content += content
                            await websocket.send(self.protocol.encode("answer_chunk", {
                                "content": content,
                                "model": model,
                                "created": int(time.time())
                            }))
                            if lsmpe_msg_id:
                                try:
                                    from lsmpe_engine import LSMPEEngine
                                    LSMPEEngine.get_instance().append_chunk(lsmpe_msg_id, content)
                                except Exception:
                                    pass

                        if done:
                            await websocket.send(self.protocol.encode("done", {
                                "thinking_summary": self._summarize_thinking(thinking_content) if thinking_chain_mode == "brief" and thinking_content else thinking_content,
                                "model": model,
                                "created": int(time.time())
                            }))
                            if lsmpe_msg_id:
                                try:
                                    from lsmpe_engine import LSMPEEngine, STATUS_COMPLETED
                                    LSMPEEngine.get_instance().finish_message(lsmpe_msg_id, STATUS_COMPLETED)
                                except Exception:
                                    pass
                            # 统一引擎post_enhance（本地模型路径）
                            if _UNIFIED_ENGINE_AVAILABLE and answer_content:
                                try:
                                    engine = UnifiedEngine.get_instance()
                                    persona_id = data.get("persona_id", "default") if isinstance(data, dict) else "default"
                                    engine.record_turn(session_id, "assistant", answer_content, persona_id)
                                    engine.post_enhance(session_id, message, answer_content, persona_id)
                                except Exception as e:
                                    logger.debug(f"[UnifiedEngine] local post_enhance failed (non-fatal): {e}")
                            return True
            return True
        except Exception as e:
            logger.warning(f"本地模型流式请求失败: {e}，将降级到 Ollama")
            return False

    async def _try_ollama_stream(self, websocket, model, system_prompt, message,
                                 thinking_chain_mode, history_messages=None, thinking_enabled=False, chat_settings=None,
                                 lsmpe_msg_id=None, data=None, session_id=None):
        import aiohttp
        try:
            from model_availability import check_model_availability
            avail = check_model_availability(model)
            if not avail['ollama_available']:
                logger.info(f"Ollama模型不可用: {model}，跳过")
                return False
        except ImportError:
            pass
        thinking_content = ""
        answer_content = ""
        in_thinking_phase = False
        ollama_messages = [{"role": "system", "content": system_prompt}]
        if history_messages and isinstance(history_messages, list):
            for hm in history_messages:
                if isinstance(hm, dict) and hm.get("role") in ("user", "assistant") and hm.get("content", "").strip():
                    ollama_messages.append({"role": hm["role"], "content": hm["content"]})
        ollama_messages.append({"role": "user", "content": message})

        options = {}
        if chat_settings and isinstance(chat_settings, dict):
            if "temperature" in chat_settings:
                options["temperature"] = float(chat_settings["temperature"])
            if "top_p" in chat_settings:
                options["top_p"] = float(chat_settings["top_p"])
            if "top_k" in chat_settings:
                options["top_k"] = int(chat_settings["top_k"])
            if "repeat_penalty" in chat_settings:
                options["repeat_penalty"] = float(chat_settings["repeat_penalty"])

        payload = {
            "model": model,
            "messages": ollama_messages,
            "stream": True,
            "think": thinking_enabled
        }
        if options:
            payload["options"] = options
        try:
            async with aiohttp.ClientSession() as sess:
                async with sess.post("http://localhost:11434/api/chat", json=payload, timeout=aiohttp.ClientTimeout(total=3600)) as resp:
                    if resp.status == 404:
                        error_body = await resp.text()
                        error_detail = ""
                        try:
                            error_obj = json.loads(error_body)
                            error_detail = error_obj.get("error", "")
                        except Exception:
                            error_detail = error_body[:200]
                        logger.warning(f"Ollama 404: 模型 \"{model}\" 未注册: {error_detail}，将降级到后端 API")
                        return False
                    if resp.status != 200:
                        error_body = await resp.text()
                        error_detail = ""
                        try:
                            error_obj = json.loads(error_body)
                            error_detail = error_obj.get("error", "")
                        except Exception:
                            error_detail = error_body[:200]
                        logger.warning(f"Ollama 返回 {resp.status}: {error_detail}，将降级到后端 API")
                        return False

                    async for raw in resp.content:
                        line = raw.decode("utf-8").strip()
                        if not line:
                            continue
                        try:
                            obj = json.loads(line)
                            msg = obj.get("message", {})
                            content = msg.get("content", "")
                            thinking = msg.get("thinking", "")
                            done = obj.get("done", False)

                            if thinking and not content:
                                if not in_thinking_phase:
                                    in_thinking_phase = True
                                    await websocket.send(self.protocol.encode("thinking_start", {}))
                                thinking_content += thinking
                                await websocket.send(self.protocol.encode("thinking_chunk", {
                                    "content": thinking,
                                    "model": model,
                                    "created": int(time.time())
                                }))
                                if lsmpe_msg_id:
                                    try:
                                        from lsmpe_engine import LSMPEEngine
                                        LSMPEEngine.get_instance().append_thinking(lsmpe_msg_id, thinking)
                                    except Exception:
                                        pass
                            elif content:
                                if in_thinking_phase:
                                    in_thinking_phase = False
                                answer_content += content
                                await websocket.send(self.protocol.encode("answer_chunk", {
                                    "content": content,
                                    "model": model,
                                    "created": int(time.time())
                                }))
                                if lsmpe_msg_id:
                                    try:
                                        from lsmpe_engine import LSMPEEngine
                                        LSMPEEngine.get_instance().append_chunk(lsmpe_msg_id, content)
                                    except Exception:
                                        pass

                            if done:
                                await websocket.send(self.protocol.encode("done", {
                                    "thinking_summary": self._summarize_thinking(thinking_content) if thinking_chain_mode == "brief" and thinking_content else thinking_content,
                                    "model": model,
                                    "created": int(time.time())
                                }))
                                if lsmpe_msg_id:
                                    try:
                                        from lsmpe_engine import LSMPEEngine, STATUS_COMPLETED
                                        LSMPEEngine.get_instance().finish_message(lsmpe_msg_id, STATUS_COMPLETED)
                                    except Exception:
                                        pass
                                # 统一引擎post_enhance（Ollama路径）
                                if _UNIFIED_ENGINE_AVAILABLE and answer_content:
                                    try:
                                        engine = UnifiedEngine.get_instance()
                                        persona_id = data.get("persona_id", "default") if isinstance(data, dict) else "default"
                                        engine.record_turn(session_id, "assistant", answer_content, persona_id)
                                        engine.post_enhance(session_id, message, answer_content, persona_id)
                                    except Exception as e:
                                        logger.debug(f"[UnifiedEngine] ollama post_enhance failed (non-fatal): {e}")
                                break
                        except Exception:
                            continue
            return True
        except Exception as e:
            logger.warning(f"Ollama 流式请求失败: {e}，将降级到后端 API")
            return False

    async def _try_backend_fallback(self, websocket, model, message, thinking_chain_mode, history_messages=None, thinking_enabled=False, chat_settings=None):
        import aiohttp
        fallback_chat_settings = {"thinking": thinking_enabled}
        if chat_settings and isinstance(chat_settings, dict):
            for key in ("temperature", "top_p", "top_k", "repeat_penalty", "max_response_tokens"):
                if key in chat_settings:
                    fallback_chat_settings[key] = chat_settings[key]

        payload = {
            "message": message,
            "model": model,
            "stream": False,
            "messages": history_messages or [],
            "chat_settings": fallback_chat_settings
        }
        headers = {"X-Internal-Call": "true"}
        try:
            async with aiohttp.ClientSession() as sess:
                async with sess.post("http://127.0.0.1:5001/api/chat", json=payload, headers=headers, timeout=aiohttp.ClientTimeout(total=3600)) as resp:
                    if resp.status != 200:
                        body = await resp.text()
                        logger.error(f"后端降级也失败: {resp.status} {body[:200]}")
                        await websocket.send(self.protocol.encode("error", {"message": f"服务不可用 ({resp.status})"}))
                        return
                    data = await resp.json()
                    if data.get("code") == 200 and data.get("data", {}).get("response"):
                        content = data["data"]["response"]
                        await websocket.send(self.protocol.encode("answer_chunk", {
                            "content": content,
                            "model": model,
                            "created": int(time.time())
                        }))
                        await websocket.send(self.protocol.encode("done", {
                            "thinking_summary": "",
                            "model": model,
                            "created": int(time.time())
                        }))
                    else:
                        err_msg = data.get("message", "未知错误")
                        await websocket.send(self.protocol.encode("error", {"message": err_msg}))
        except Exception as e:
            logger.error(f"后端降级请求失败: {e}")
            await websocket.send(self.protocol.encode("error", {"message": str(e)}))
    
    def _summarize_thinking(self, thinking: str) -> str:
        """简要总结思考内容"""
        if not thinking:
            return ""
        
        lines = thinking.strip().split('\n')
        key_points = []
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
            if any(line.startswith(prefix) for prefix in ['1.', '2.', '3.', '4.', '5.', '6.', '7.', '8.', '9.', '-', '*', '•']):
                clean_line = line.lstrip('0123456789.-*• ').strip()
                if clean_line and len(clean_line) >= 2:
                    key_points.append(clean_line)
            elif line.endswith(':') or line.endswith('：'):
                key_points.append(line.rstrip('：:'))
        
        if len(key_points) > 5:
            key_points = key_points[:5]
        
        if key_points:
            return "• " + "\n• ".join(key_points)
        
        sentences = thinking.replace('。', '。\n').replace('！', '！\n').replace('？', '？\n').split('\n')
        sentences = [s.strip() for s in sentences if s.strip() and len(s.strip()) > 5]
        if len(sentences) > 3:
            sentences = sentences[:3]
        
        return "。".join(sentences) + "。" if sentences else thinking[:200]
    
    async def _handle_group_ws(self, websocket: Any):
        """群聊只读增量推送"""
        try:
            from hybrid_group_chat_controller import get_group_chat_controller
            controller = get_group_chat_controller()
            last_len = 0
            try:
                msgs = controller.get_messages(10_000)
                last_len = len(msgs)
            except Exception:
                last_len = 0
            await websocket.send(self.protocol.encode("group_ready", {}))
            while True:
                msgs = controller.get_messages(10_000)
                if len(msgs) > last_len:
                    for m in msgs[last_len:]:
                        await websocket.send(self.protocol.encode("group_chunk", {
                            "content": m.get("content", ""),
                            "done": False,
                            "model": m.get("model_name", ""),
                            "character": m.get("character_name", ""),
                            "created": int(time.time())
                        }))
                    last_len = len(msgs)
                await asyncio.sleep(1.0)
        except Exception as e:
            await websocket.send(self.protocol.encode("error", {"message": str(e)}))
    
    async def _handle_message(self, session: CallSession, message: str):
        """处理客户端消息"""
        msg_type, data, timestamp = self.protocol.decode(message)
        
        if msg_type is None:
            return
        
        logger.info(f"[Voice Debug] 收到消息: {msg_type}")
        
        if msg_type == "audio_chunk":
            # 处理音频数据
            await self._handle_audio_chunk(session, data)
        
        elif msg_type == "start_speaking":
            # 用户开始说话
            session.is_speaking = True
            session.audio_buffer = b""
            logger.info("[Voice Debug] 用户开始说话")
        
        elif msg_type == "stop_speaking":
            # 用户停止说话
            session.is_speaking = False
            logger.info(f"[Voice Debug] 用户停止说话, 缓冲区大小: {len(session.audio_buffer)} bytes")
            # 处理累积的音频
            await self._process_audio_buffer(session)
        
        elif msg_type == "interrupt":
            # 用户打断
            await self._handle_interrupt(session)
        
        elif msg_type == "ping":
            # 心跳检测
            await session.websocket.send(self.protocol.encode("pong", {}))
        
        elif msg_type == "get_status":
            # 获取状态
            await session.websocket.send(self.protocol.encode("status", {
                "is_speaking": session.is_speaking,
                "is_ai_speaking": session.is_ai_speaking,
                "conversation_length": len(session.conversation_history),
                "current_speaker": self.config.tts_speaker_id
            }))
        
        elif msg_type == "set_voice":
            speaker_id = data.get("speaker_id", "vivian")
            if hasattr(self.tts_service, 'set_speaker'):
                self.tts_service.set_speaker(speaker_id)
                self.config.tts_speaker_id = self.tts_service.current_speaker
            else:
                self.config.tts_speaker_id = speaker_id
            logger.info(f"[Voice] 音色已切换: {speaker_id}")
            await session.websocket.send(self.protocol.encode("voice_changed", {
                "speaker_id": speaker_id,
                "success": True
            }))
        
        else:
            logger.warning(f"未知消息类型: {msg_type}")
    
    async def _handle_audio_chunk(self, session: CallSession, data: dict):
        """处理音频数据块"""
        audio_base64 = data.get("audio", "")
        if not audio_base64:
            logger.warning("[Voice Debug] 收到空音频块")
            return

        try:
            # 解码音频数据
            audio_bytes = base64.b64decode(audio_base64)
            session.audio_buffer += audio_bytes
            session.total_audio_bytes += len(audio_bytes)

            logger.info(f"[Voice Debug] 收到音频块: {len(audio_bytes)} bytes, 缓冲区: {len(session.audio_buffer)} bytes")

        except Exception as e:
            logger.error(f"[Voice Debug] 处理音频数据失败: {e}")
    
    async def _process_audio_buffer(self, session: CallSession):
        """处理音频缓冲区"""
        logger.info(f"[Voice Debug] _process_audio_buffer 被调用, 缓冲区: {len(session.audio_buffer)} bytes")
        
        if not session.audio_buffer:
            logger.info("[Voice Debug] 缓冲区为空，跳过处理")
            return
        
        audio_data = session.audio_buffer
        session.audio_buffer = b""
        
        # 音频数据太短，跳过（至少0.2秒，降低阈值加快响应）
        min_audio_bytes = self.config.audio_sample_rate * 2 * 0.2
        if len(audio_data) < min_audio_bytes:
            logger.info(f"[Voice Debug] 音频数据太短({len(audio_data)} bytes < {min_audio_bytes} bytes)，跳过")
            return
        
        try:
            import io
            import wave
            import tempfile
            import subprocess
            
            # 第一步：将原始音频保存为临时WAV文件
            temp_raw = tempfile.mktemp(suffix='.wav')
            temp_denoised = tempfile.mktemp(suffix='.wav')
            
            with wave.open(temp_raw, 'wb') as wav_file:
                wav_file.setnchannels(1)
                wav_file.setsampwidth(2)
                wav_file.setframerate(self.config.audio_sample_rate)
                wav_file.writeframes(audio_data)
            
            # 第二步：使用ffmpeg进行降噪处理
            # - highpass=f=80: 去除低频噪声（空调、风扇等）
            # - lowpass=f=4000: 去除高频噪声（嘶嘶声、电流声）
            # - afftdn=nf=-25: 频域降噪，降噪强度-25dB
            # - silenceremove: 去除静音段
            # - volume=2.0: 音量增强
            try:
                subprocess.run([
                    'ffmpeg', '-y', '-i', temp_raw,
                    '-af', 'highpass=f=80,lowpass=f=4000,afftdn=nf=-25,volume=2.0',
                    '-ar', '16000', '-ac', '1', '-c:a', 'pcm_s16le',
                    temp_denoised
                ], capture_output=True, check=True, timeout=10)
                
                # 使用降噪后的音频
                wav_path = temp_denoised
            except (subprocess.TimeoutExpired, subprocess.CalledProcessError, FileNotFoundError) as e:
                logger.warning(f"[Voice Debug] ffmpeg降噪失败({e})，使用原始音频")
                wav_path = temp_raw
            
            # 第三步：ASR识别
            if self.asr_service:
                logger.info(f"[Voice Debug] 开始ASR识别，音频文件: {wav_path}")
                loop = asyncio.get_event_loop()
                result = await loop.run_in_executor(
                    None,
                    lambda: self.asr_service.transcribe(wav_path, language="zh")
                )

                # 清理临时文件
                for f in [temp_raw, temp_denoised]:
                    if os.path.exists(f):
                        try:
                            os.remove(f)
                        except:
                            pass

                if result:
                    text = result.text.strip()
                    logger.info(f"[Voice Debug] ASR结果: '{text}' (置信度: {result.confidence:.2f})")

                    # 过滤无效识别结果
                    if self._is_valid_asr_result(text, result.confidence):
                        session.current_asr_text = text
                        session.total_user_messages += 1

                        # 发送识别结果
                        await session.websocket.send(self.protocol.encode("transcript", {
                            "text": text,
                            "is_final": True
                        }))

                        logger.info(f"[Voice Debug] ASR识别有效，发送transcript，准备生成AI回复")

                        # 生成AI回复
                        await self._generate_ai_response(session, text)
                    else:
                        logger.info(f"[Voice Debug] ASR结果被过滤: '{text}' (置信度: {result.confidence:.2f})")
                else:
                    logger.warning("[Voice Debug] ASR返回空结果")
            else:
                logger.error("[Voice Debug] ASR服务不可用！")
                # 清理临时文件
                for f in [temp_raw, temp_denoised]:
                    if os.path.exists(f):
                        try:
                            os.remove(f)
                        except:
                            pass
            
        except Exception as e:
            logger.error(f"[Voice Debug] 处理音频失败: {e}")
            import traceback
            logger.error(f"[Voice Debug] 异常堆栈: {traceback.format_exc()}")
    
    def _is_valid_asr_result(self, text: str, confidence: float) -> bool:
        """
        检查ASR识别结果是否有效
        
        过滤规则：
        1. 文本长度至少2个字符
        2. 置信度至少0.5
        3. 排除常见的误识别词（如"嗯"、"啊"等单字）
        """
        if not text or len(text.strip()) < 2:
            return False
        
        if confidence < 0.5:
            return False
        
        # 常见的误识别词（静音/噪声被误识别）
        invalid_words = {'嗯', '啊', '呃', '哦', '额', '唔', '哈', '呵', '唉', '哎'}
        
        # 如果只有单个字且是误识别词，过滤
        stripped = text.strip()
        if len(stripped) <= 2 and stripped in invalid_words:
            return False
        
        # 如果全是误识别词，过滤
        if all(c in invalid_words or c.isspace() for c in stripped):
            return False
        
        return True
    
    async def _generate_ai_response(self, session: CallSession, user_text: str):
        logger.info(f"[Voice Debug] _generate_ai_response 被调用, 用户文本: '{user_text[:50]}'")

        if session.is_interrupted:
            logger.info("[Voice Debug] 会话已被打断，跳过AI回复")
            return

        session.is_ai_speaking = True

        try:
            messages = []
            for msg in session.conversation_history[-10:]:
                messages.append({"role": msg["role"], "content": msg["content"]})
            messages.append({"role": "user", "content": user_text})

            system_prompt = """你是一个智能语音助手，使用Qwen3.5模型。
请用简洁、自然的口语化中文回答，长度控制在1-3句话。
保持友好、专业的态度，响应要快。"""

            import aiohttp

            sentence_queue = asyncio.Queue()
            full_text_holder = [""]

            async def _stream_llm():
                payload = {
                    "model": self.config.llm_model,
                    "messages": [{"role": "system", "content": system_prompt}] + messages,
                    "stream": True,
                    "options": {
                        "temperature": self.config.llm_temperature,
                        "num_predict": self.config.llm_max_tokens
                    }
                }
                try:
                    async with aiohttp.ClientSession() as http_sess:
                        async with http_sess.post(
                            "http://localhost:11434/api/chat",
                            json=payload,
                            timeout=aiohttp.ClientTimeout(total=120)
                        ) as resp:
                            if resp.status == 404:
                                logger.error(f"[Voice] LLM模型 \"{self.config.llm_model}\" 未在 Ollama 中注册")
                                await sentence_queue.put(None)
                                return
                            if resp.status != 200:
                                logger.error(f"[Voice] LLM流式请求失败: HTTP {resp.status}")
                                await sentence_queue.put(None)
                                return

                            buffer = ""
                            async for raw in resp.content:
                                if session.is_interrupted:
                                    break
                                line = raw.decode("utf-8").strip()
                                if not line:
                                    continue
                                try:
                                    obj = json.loads(line)
                                    content = obj.get("message", {}).get("content", "")
                                    done = obj.get("done", False)
                                    if content:
                                        buffer += content
                                        full_text_holder[0] += content
                                        sentence = self._extract_complete_sentence(buffer)
                                        if sentence:
                                            buffer = buffer[len(sentence):]
                                            await sentence_queue.put(sentence)
                                    if done:
                                        break
                                except json.JSONDecodeError:
                                    continue

                            if buffer.strip() and not session.is_interrupted:
                                await sentence_queue.put(buffer.strip())
                except Exception as e:
                    logger.error(f"[Voice] LLM流式异常: {e}")
                finally:
                    await sentence_queue.put(None)

            llm_task = asyncio.create_task(_stream_llm())

            pending_tts = []

            while True:
                sentence = await sentence_queue.get()
                if sentence is None:
                    break
                if session.is_interrupted:
                    break
                if len(sentence) < 2:
                    continue

                await session.websocket.send(self.protocol.encode("ai_text", {
                    "text": sentence,
                    "is_chunk": True
                }))

                synth_task = asyncio.create_task(self._synthesize_only(session, sentence))
                pending_tts.append(synth_task)

                if len(pending_tts) >= 2:
                    result = await pending_tts.pop(0)
                    if result and not session.is_interrupted:
                        await self._send_audio(session, result)

            for task in pending_tts:
                if not session.is_interrupted:
                    result = await task
                    if result:
                        await self._send_audio(session, result)

            llm_task.cancel()
            try:
                await llm_task
            except asyncio.CancelledError:
                pass

            ai_text = full_text_holder[0].strip()
            if ai_text and not session.is_interrupted:
                session.current_ai_text = ai_text
                session.total_ai_messages += 1
                session.conversation_history.append({
                    "role": "user",
                    "content": user_text,
                    "timestamp": time.time()
                })
                session.conversation_history.append({
                    "role": "assistant",
                    "content": ai_text,
                    "timestamp": time.time()
                })

                await session.websocket.send(self.protocol.encode("ai_text", {
                    "text": ai_text,
                    "is_final": True
                }))

        except Exception as e:
            logger.error(f"[Voice Debug] 生成AI回复异常: {e}")
            import traceback
            logger.error(f"[Voice Debug] 异常堆栈: {traceback.format_exc()}")
        finally:
            session.is_ai_speaking = False
    
    def _split_sentences(self, text: str) -> list:
        import re
        sentences = re.split(r'([。！？.!?])', text)
        result = []
        current = ""
        for part in sentences:
            current += part
            if part in '。！？.!?':
                if current.strip():
                    result.append(current.strip())
                current = ""
        if current.strip():
            result.append(current.strip())
        return result if result else [text]

    def _extract_complete_sentence(self, buffer: str) -> str:
        import re
        match = re.search(r'.*?[。！？.!?；;]', buffer)
        if match:
            return match.group(0)
        if len(buffer) > 60:
            match = re.search(r'.*?[，,、]', buffer)
            if match:
                return match.group(0)
        return ""

    def _infer_emotion(self, text: str, history: list) -> str:
        if not text:
            return None
        excl = text.count('！') + text.count('!')
        ques = text.count('？') + text.count('?')
        if excl >= 2:
            return "cheerful"
        if ques > 0:
            return "calm"
        warm_kw = {'谢谢', '感谢', '很高兴', '欢迎', '喜欢', '开心', '好的', '没问题'}
        if any(kw in text for kw in warm_kw):
            return "warm"
        sorry_kw = {'抱歉', '对不起', '不好意思', '遗憾'}
        if any(kw in text for kw in sorry_kw):
            return "calm"
        return None

    async def _synthesize_only(self, session: CallSession, sentence: str):
        if session.is_interrupted:
            return None
        if not self.tts_service:
            return None
        if len(sentence) < 3:
            return None

        try:
            emotion = self._infer_emotion(sentence, session.conversation_history)
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None,
                lambda s=sentence, e=emotion: self.tts_service.synthesize(
                    s,
                    speaker_id=self.config.tts_speaker_id,
                    speed=self.config.tts_speed,
                    emotion=e
                )
            )
            return result
        except Exception as e:
            logger.error(f"[TTS] 合成失败: {e}")
            return None

    async def _send_audio(self, session: CallSession, result):
        if not result or session.is_interrupted:
            return
        try:
            audio_base64 = self.tts_service.audio_to_base64(result)
            payload = {
                "audio": audio_base64,
                "sample_rate": result.sample_rate,
                "duration_ms": result.duration_ms
            }
            await session.websocket.send(self.protocol.encode("ai_audio", payload))
            logger.info(f"[TTS] 音频已发送, 时长={result.duration_ms:.0f}ms")
        except Exception as e:
            logger.error(f"[TTS] 发送音频失败: {e}")
    
    async def _handle_interrupt(self, session: CallSession):
        """处理打断"""
        logger.info("用户打断")
        session.is_interrupted = True
        session.is_ai_speaking = False
        
        # 发送打断确认
        await session.websocket.send(self.protocol.encode("interrupted", {
            "message": "AI已停止"
        }))
        
        # 重置打断状态
        await asyncio.sleep(0.1)
        session.is_interrupted = False
    
    async def start(self):
        """启动服务"""
        if not WEBSOCKET_AVAILABLE:
            logger.error("websockets库未安装，无法启动服务")
            return
        
        self.is_running = True
        
        # 初始化服务
        await self.initialize_services()
        
        # 启动WebSocket服务器
        logger.info(f"启动语音通话服务: ws://{self.config.host}:{self.config.port}")
        
        async with websockets.serve(
            self.handle_websocket,
            self.config.host,
            self.config.port,
            ping_interval=60,
            ping_timeout=120,
            close_timeout=30,
        ):
            logger.info("语音通话服务已启动")
            await asyncio.Future()  # 永久运行
    
    def stop(self):
        """停止服务"""
        self.is_running = False
        logger.info("语音通话服务已停止")


async def main():
    """主函数"""
    service = VoiceCallService()
    
    try:
        await service.start()
    except KeyboardInterrupt:
        logger.info("收到中断信号，正在关闭服务...")
        service.stop()
    except Exception as e:
        logger.error(f"服务运行出错: {e}")


if __name__ == "__main__":
    asyncio.run(main())
