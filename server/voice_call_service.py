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
from typing import Dict, Optional, Any, Set
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

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
    tts_speaker_id: str = "default"
    tts_speed: float = 1.0
    
    # LLM配置
    llm_model: str = "qwen2.5:3b"
    llm_max_tokens: int = 200
    llm_temperature: float = 0.7
    
    # 超时配置
    connection_timeout: int = 300  # 5分钟无活动断开
    max_session_duration: int = 1800  # 最大通话时长30分钟


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
    1. 单路通话：同一时间只允许一个会话
    2. 流式处理：音频流实时处理，不缓存大量数据
    3. 低延迟：端到端延迟控制在500ms以内
    4. 容错处理：模型加载失败时优雅降级
    """
    
    def __init__(self, config: Optional[VoiceCallConfig] = None):
        self.config = config or VoiceCallConfig()
        self.protocol = MessageProtocol()
        
        # 会话管理
        self.active_session: Optional[CallSession] = None
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
        """文本对话WebSocket流式处理"""
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
            history_messages = data.get("messages", [])
            if not message:
                await websocket.send(self.protocol.encode("error", {"message": "empty message"}))
                return
            system_prompt = data.get("system_prompt", "你是一个智能助手。")

            thinking_content = ""
            answer_content = ""
            in_thinking_phase = False

            ollama_ok = await self._try_ollama_stream(
                websocket, model, system_prompt, message,
                thinking_chain_mode,
                thinking_content, answer_content, in_thinking_phase,
                history_messages
            )

            if not ollama_ok:
                await self._try_backend_fallback(
                    websocket, model, message,
                    thinking_chain_mode,
                    history_messages
                )
        except Exception as e:
            await websocket.send(self.protocol.encode("error", {"message": str(e)}))

    async def _try_ollama_stream(self, websocket, model, system_prompt, message,
                                  thinking_chain_mode,
                                  thinking_content, answer_content, in_thinking_phase,
                                  history_messages=None):
        import aiohttp
        ollama_messages = [{"role": "system", "content": system_prompt}]
        if history_messages and isinstance(history_messages, list):
            for hm in history_messages:
                if isinstance(hm, dict) and hm.get("role") in ("user", "assistant") and hm.get("content", "").strip():
                    ollama_messages.append({"role": hm["role"], "content": hm["content"]})
        ollama_messages.append({"role": "user", "content": message})
        payload = {
            "model": model,
            "messages": ollama_messages,
            "stream": True
        }
        try:
            async with aiohttp.ClientSession() as sess:
                async with sess.post("http://localhost:11434/api/chat", json=payload, timeout=aiohttp.ClientTimeout(total=300)) as resp:
                    if resp.status != 200:
                        logger.warning(f"Ollama 返回 {resp.status}，将降级到后端 API")
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
                            elif content:
                                if in_thinking_phase:
                                    in_thinking_phase = False
                                answer_content += content
                                await websocket.send(self.protocol.encode("answer_chunk", {
                                    "content": content,
                                    "model": model,
                                    "created": int(time.time())
                                }))

                            if done:
                                await websocket.send(self.protocol.encode("done", {
                                    "thinking_summary": self._summarize_thinking(thinking_content) if thinking_chain_mode == "brief" and thinking_content else thinking_content,
                                    "model": model,
                                    "created": int(time.time())
                                }))
                                break
                        except Exception:
                            continue
            return True
        except Exception as e:
            logger.warning(f"Ollama 流式请求失败: {e}，将降级到后端 API")
            return False

    async def _try_backend_fallback(self, websocket, model, message, thinking_chain_mode, history_messages=None):
        import aiohttp
        payload = {
            "message": message,
            "model": model,
            "stream": False,
            "messages": history_messages or []
        }
        headers = {"X-Internal-Call": "true"}
        try:
            async with aiohttp.ClientSession() as sess:
                async with sess.post("http://localhost:5001/api/chat", json=payload, headers=headers, timeout=aiohttp.ClientTimeout(total=120)) as resp:
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
                "conversation_length": len(session.conversation_history)
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
            # 使用内存buffer代替临时文件（避免磁盘IO）
            import io
            import wave
            
            wav_buffer = io.BytesIO()
            with wave.open(wav_buffer, 'wb') as wav_file:
                wav_file.setnchannels(1)
                wav_file.setsampwidth(2)
                wav_file.setframerate(self.config.audio_sample_rate)
                wav_file.writeframes(audio_data)
            
            wav_buffer.seek(0)
            
            # ASR识别（异步调用，避免阻塞事件循环）
            if self.asr_service:
                logger.info(f"[Voice Debug] 开始ASR识别，音频大小: {len(audio_data)} bytes, 采样率: {self.config.audio_sample_rate}")
                loop = asyncio.get_event_loop()
                result = await loop.run_in_executor(
                    None,  # 使用默认线程池
                    lambda: self.asr_service.transcribe(wav_buffer, language="zh")
                )

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
        """生成AI回复"""
        logger.info(f"[Voice Debug] _generate_ai_response 被调用, 用户文本: '{user_text[:50]}'")
        
        if session.is_interrupted:
            logger.info("[Voice Debug] 会话已被打断，跳过AI回复")
            return
        
        session.is_ai_speaking = True
        
        try:
            # 构建对话历史
            messages = []
            for msg in session.conversation_history[-10:]:  # 保留最近10轮
                messages.append({"role": msg["role"], "content": msg["content"]})
            
            messages.append({"role": "user", "content": user_text})
            
            # 系统提示词
            system_prompt = """你是一个智能语音助手，使用Qwen3.5模型。
请用简洁、自然的口语化中文回答，长度控制在1-3句话。
保持友好、专业的态度，响应要快。"""
            
            # 调用Ollama生成回复
            logger.info(f"[Voice Debug] 调用Ollama LLM, model={self.config.llm_model}")
            import aiohttp
            
            async with aiohttp.ClientSession() as http_session:
                async with http_session.post(
                    "http://localhost:11434/api/chat",
                    json={
                        "model": self.config.llm_model,
                        "messages": [{"role": "system", "content": system_prompt}] + messages,
                        "stream": False,
                        "options": {
                            "temperature": self.config.llm_temperature,
                            "num_predict": self.config.llm_max_tokens
                        }
                    }
                ) as response:
                    logger.info(f"[Voice Debug] Ollama响应状态: {response.status}")
                    if response.status == 200:
                        result = await response.json()
                        logger.info(f"[Voice Debug] Ollama完整响应: {str(result)[:300]}")
                        ai_text = result.get("message", {}).get("content", "").strip()
                        logger.info(f"[Voice Debug] LLM回复: '{ai_text[:80]}' (长度: {len(ai_text)})")
                        
                        if not ai_text:
                            logger.warning("[Voice Debug] LLM返回空回复，发送默认回复")
                            ai_text = "抱歉，我没有听清楚，请再说一次。"
                        
                        if not session.is_interrupted:
                            session.current_ai_text = ai_text
                            session.total_ai_messages += 1
                            
                            # 保存到对话历史
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
                            
                            # 发送AI文本
                            await session.websocket.send(self.protocol.encode("ai_text", {
                                "text": ai_text
                            }))
                            
                            logger.info(f"[Voice Debug] 发送ai_text消息，准备合成语音")
                            
                            # 合成语音
                            await self._synthesize_speech(session, ai_text)
                    else:
                        logger.error(f"[Voice Debug] LLM调用失败: HTTP {response.status}")
                        try:
                            error_text = await response.text()
                            logger.error(f"[Voice Debug] LLM错误详情: {error_text[:200]}")
                        except:
                            pass
                        
        except Exception as e:
            logger.error(f"[Voice Debug] 生成AI回复异常: {e}")
            import traceback
            logger.error(f"[Voice Debug] 异常堆栈: {traceback.format_exc()}")
        finally:
            session.is_ai_speaking = False
    
    async def _synthesize_speech(self, session: CallSession, text: str):
        """合成语音"""
        logger.info(f"[TTS Debug] _synthesize_speech 被调用, text长度={len(text)}, interrupted={session.is_interrupted}")
        
        if session.is_interrupted:
            logger.info("[TTS Debug] 会话已被打断，跳过合成")
            return

        if not self.tts_service:
            logger.error("[TTS Debug] TTS服务不可用，无法合成语音")
            try:
                await session.websocket.send(self.protocol.encode("status", {
                    "tts_available": False,
                    "reason": "tts_service_unavailable"
                }))
            except Exception:
                pass
            return
        
        logger.info(f"[TTS Debug] TTS服务可用，开始处理文本: '{text[:50]}...'")
        
        try:
            # 分段合成（按句子分割）
            sentences = self._split_sentences(text)
            
            for sentence in sentences:
                if session.is_interrupted:
                    break
                
                if len(sentence) < 3:
                    continue
                
                # 合成语音（在线程池中执行，避免阻塞事件循环）
                logger.info(f"[TTS Debug] 开始合成语音: '{sentence[:30]}...' speaker={self.config.tts_speaker_id}")
                loop = asyncio.get_event_loop()
                result = await loop.run_in_executor(
                    None,
                    lambda s=sentence: self.tts_service.synthesize(
                        s,
                        speaker_id=self.config.tts_speaker_id,
                        speed=self.config.tts_speed
                    )
                )
                
                logger.info(f"[TTS Debug] 合成结果: {result is not None}, interrupted={session.is_interrupted}")
                
                if result and not session.is_interrupted:
                    # 转换为base64
                    audio_base64 = self.tts_service.audio_to_base64(result)
                    logger.info(f"[TTS Debug] base64转换完成, 长度: {len(audio_base64) if audio_base64 else 0}")
                    
                    # 发送音频
                    await session.websocket.send(self.protocol.encode("ai_audio", {
                        "audio": audio_base64,
                        "sample_rate": result.sample_rate,
                        "duration_ms": result.duration_ms
                    }))
                    
                    logger.info(f"[TTS Debug] ai_audio 消息已发送, 时长: {result.duration_ms:.0f}ms, 采样率: {result.sample_rate}")
                    
                    # 非阻塞等待，让前端有时间播放
                    await asyncio.sleep(min(result.duration_ms / 1000, 0.5))
        
        except Exception as e:
            logger.error(f"语音合成失败: {e}")
            try:
                await session.websocket.send(self.protocol.encode("status", {
                    "tts_available": False,
                    "reason": f"tts_synthesis_failed: {str(e)}"
                }))
            except Exception:
                pass
    
    def _split_sentences(self, text: str) -> list:
        """将文本分割成句子"""
        import re
        # 按标点符号分割
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
            ping_interval=20,  # 每20秒发送一次ping
            ping_timeout=30,   # 30秒内无响应才断开（更宽容）
            close_timeout=10   # 关闭连接超时
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
