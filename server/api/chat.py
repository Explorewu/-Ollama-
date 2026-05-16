"""
Chat API routes.
"""

import json
import logging
import os
import re
import time
import uuid

import requests
from flask import Response, jsonify, request, stream_with_context

from utils.auth import require_api_key
from utils.config import (
    DEFAULT_CHAT_MODEL,
    DEFAULT_CHAT_RUNTIME_CONFIG,
    DEFAULT_OPENAI_COMPAT_MODEL,
    OLLAMA_BASE_URL,
    REPETITION_DETECTION_CONFIG,
)
from utils.behavior_contract import compile_system_prompt
from utils.helpers import error_response, success_response
from utils.repetition_detector import create_detector
from chat_pipeline import (
    build_ollama_payload as _build_ollama_payload,
    build_runtime_config as _build_runtime_config,
    extract_ollama_message as _extract_ollama_message,
    normalize_message_input as _normalize_message_input,
    resolve_n_ctx as _resolve_n_ctx,
)

try:
    from server.timing_collector import TimingCollector
    TIMING_AVAILABLE = True
except ImportError:
    try:
        from timing_collector import TimingCollector
        TIMING_AVAILABLE = True
    except ImportError:
        TIMING_AVAILABLE = False

try:
    from server.context_compressor import get_context_compressor, CompressionConfig
    CONTEXT_COMPRESSOR_AVAILABLE = True
except ImportError:
    try:
        from context_compressor import get_context_compressor, CompressionConfig
        CONTEXT_COMPRESSOR_AVAILABLE = True
    except ImportError:
        CONTEXT_COMPRESSOR_AVAILABLE = False

try:
    from local_model_loader import generate_chat_response, is_local_model_available, is_gguf_model
    LOCAL_MODEL_AVAILABLE = True
except ImportError:
    LOCAL_MODEL_AVAILABLE = False

try:
    from model_registry import is_model_available, get_model_registry, init_model_registry
    MODEL_REGISTRY_AVAILABLE = True
except ImportError:
    MODEL_REGISTRY_AVAILABLE = False

try:
    from model_availability import check_model_availability
    MODEL_AVAILABILITY_AVAILABLE = True
except ImportError:
    MODEL_AVAILABILITY_AVAILABLE = False

try:
    from request_router import classify_request, RequestPath
    REQUEST_ROUTER_AVAILABLE = True
except ImportError:
    REQUEST_ROUTER_AVAILABLE = False

try:
    from auto_heal import auto_heal
    AUTO_HEAL_AVAILABLE = True
except ImportError:
    AUTO_HEAL_AVAILABLE = False

try:
    from dialogue_enhancement import DialogueEnhancementMiddleware, EnhancementContext
    DEM_AVAILABLE = True
except ImportError:
    try:
        from server.dialogue_enhancement import DialogueEnhancementMiddleware, EnhancementContext
        DEM_AVAILABLE = True
    except ImportError:
        DEM_AVAILABLE = False

try:
    from unified_engine import UnifiedEngine
    UNIFIED_ENGINE_AVAILABLE = True
except ImportError:
    try:
        from server.unified_engine import UnifiedEngine
        UNIFIED_ENGINE_AVAILABLE = True
    except ImportError:
        UNIFIED_ENGINE_AVAILABLE = False

try:
    from lsmpe_engine import LSMPEEngine, TYPE_AI_REPLY, STATUS_COMPLETED, STATUS_FAILED
    LSMPE_AVAILABLE = True
except ImportError:
    LSMPE_AVAILABLE = False

try:
    from temg_engine import TEMGEngine
    TEMG_AVAILABLE = True
except ImportError:
    try:
        from server.temg_engine import TEMGEngine
        TEMG_AVAILABLE = True
    except ImportError:
        TEMG_AVAILABLE = False

try:
    from casc_engine import CASCEngine
    CASC_AVAILABLE = True
except ImportError:
    try:
        from server.casc_engine import CASCEngine
        CASC_AVAILABLE = True
    except ImportError:
        CASC_AVAILABLE = False

try:
    from elpe_engine import ELPEEngine, TimeState
    ELPE_AVAILABLE = True
except ImportError:
    try:
        from server.elpe_engine import ELPEEngine, TimeState
        ELPE_AVAILABLE = True
    except ImportError:
        ELPE_AVAILABLE = False

try:
    from auto_tool_caller import get_auto_tool_caller, register_builtin_tools, ToolCallParser
    AUTO_TOOL_CALL_AVAILABLE = True
except ImportError:
    try:
        from server.auto_tool_caller import get_auto_tool_caller, register_builtin_tools, ToolCallParser
        AUTO_TOOL_CALL_AVAILABLE = True
    except ImportError:
        AUTO_TOOL_CALL_AVAILABLE = False

try:
    from knowledge_graph import extract_async as _kg_extract_async
    KNOWLEDGE_GRAPH_AVAILABLE = True
except ImportError:
    try:
        from server.knowledge_graph import extract_async as _kg_extract_async
        KNOWLEDGE_GRAPH_AVAILABLE = True
    except ImportError:
        KNOWLEDGE_GRAPH_AVAILABLE = False

try:
    from unified_memory import UnifiedMemoryLayer
    UNIFIED_MEMORY_AVAILABLE = True
except ImportError:
    try:
        from server.unified_memory import UnifiedMemoryLayer
        UNIFIED_MEMORY_AVAILABLE = True
    except ImportError:
        UNIFIED_MEMORY_AVAILABLE = False

logger = logging.getLogger(__name__)

if AUTO_TOOL_CALL_AVAILABLE:
    try:
        register_builtin_tools()
        logger.info("[AutoToolCaller] 内置工具已注册")
    except Exception as e:
        logger.warning(f"[AutoToolCaller] 注册内置工具失败(非致命): {e}")


def _kg_extract_if_available(user_msg, ai_msg, conv_id, model):
    if KNOWLEDGE_GRAPH_AVAILABLE and user_msg and ai_msg:
        try:
            _kg_extract_async(user_msg, ai_msg, conv_id, model=model)
        except Exception as e:
            logger.debug(f"[KnowledgeGraph] 异步提取失败(非致命): {e}")


def _lsmpe_create(session_id, model):
    """创建LSMPE流式消息记录（非致命，失败不影响聊天）"""
    if not LSMPE_AVAILABLE:
        return None
    try:
        engine = LSMPEEngine.get_instance()
        msg = engine.create_message(session_id, TYPE_AI_REPLY, model)
        return msg.msg_id
    except Exception as e:
        logger.debug(f"LSMPE创建消息失败(非致命): {e}")
        return None


def _lsmpe_append(msg_id, chunk, chunk_type="content"):
    """追加LSMPE chunk"""
    if not msg_id or not LSMPE_AVAILABLE:
        return
    try:
        engine = LSMPEEngine.get_instance()
        if chunk_type == "thinking":
            engine.append_thinking(msg_id, chunk)
        else:
            engine.append_chunk(msg_id, chunk)
    except Exception:
        pass


def _lsmpe_finish(msg_id, status=STATUS_COMPLETED):
    """完成LSMPE消息"""
    if not msg_id or not LSMPE_AVAILABLE:
        return
    try:
        LSMPEEngine.get_instance().finish_message(msg_id, status)
    except Exception:
        pass


def _elpe_decide_proactive(persona_id: str) -> dict:
    """调用ELPE决策是否需要主动发送消息。返回字典包含action字段。"""
    if not ELPE_AVAILABLE or not persona_id:
        return {"action": "skip", "reason": "ELPE不可用"}
    try:
        elpe = ELPEEngine(persona_id=persona_id)
        decision = elpe.decide()
        return decision
    except Exception as e:
        logger.debug(f"[ELPE] proactive decision failed (non-fatal): {e}")
        return {"action": "skip", "reason": str(e)}


def _proactive_record_activity(persona_id: str, session_id: str):
    """记录用户活动到ProactiveEngine"""
    try:
        from proactive_engine import ProactiveEngine
        engine = ProactiveEngine.get_instance(persona_id)
        engine.record_user_activity(session_id)
    except Exception:
        pass


def _elpe_build_sse_event(decision: dict) -> str:
    """将ELPE决策结果封装为SSE事件字符串。仅在decision.action=='send'时返回有效事件。"""
    if not decision or decision.get("action") != "send":
        return ""
    payload = {
        "event": "proactive_suggestion",
        "content": decision.get("utterance", ""),
        "score": decision.get("score", 0),
        "type_label": decision.get("type_label", ""),
        "done": False,
    }
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"


def _temg_ingest_turn(persona_id: str, user_message: str, assistant_message: str):
    """将user+assistant对话对摄入TEMG记忆引擎。需满足min_turns=2的要求。"""
    if not TEMG_AVAILABLE or not persona_id:
        return
    try:
        temg = TEMGEngine.get_instance(persona_id)
        temg.ingest([
            {"role": "user", "content": user_message},
            {"role": "assistant", "content": assistant_message},
        ])
    except Exception as e:
        logger.debug(f"[TEMG] ingest failed (non-fatal): {e}")


def _unified_memory_store(user_message: str, ai_message: str, persona_id: str = "",
                          session_id: str = "", conversation_id: str = "", model: str = ""):
    """通过统一记忆层异步存储对话轮次（替代分散的 _temg_ingest_turn + _kg_extract_if_available）"""
    if not UNIFIED_MEMORY_AVAILABLE:
        _kg_extract_if_available(user_message, ai_message, conversation_id, model)
        if persona_id:
            _temg_ingest_turn(persona_id, user_message, ai_message)
        return
    try:
        uml = UnifiedMemoryLayer.get_instance()
        uml.store_conversation_turn(
            user_message=user_message,
            ai_message=ai_message,
            persona_id=persona_id or "default",
            session_id=session_id,
            conversation_id=conversation_id,
            model=model,
        )
    except Exception as e:
        logger.debug(f"[UnifiedMemory] store failed (non-fatal): %s", e)
        _kg_extract_if_available(user_message, ai_message, conversation_id, model)
        if persona_id:
            _temg_ingest_turn(persona_id, user_message, ai_message)


def _lsmpe_intercept_sse(msg_id, sse_line):
    """从SSE数据行中提取内容并追加到LSMPE
    
    Returns:
        bool: 是否已经调用过finish（用于避免重复finish）
    """
    if not msg_id or not LSMPE_AVAILABLE:
        return False
    try:
        line = sse_line.strip()
        if not line.startswith("data: "):
            return False
        json_str = line[6:]
        if json_str.strip() == "[DONE]":
            return False
        obj = json.loads(json_str)
        event = obj.get("event", "")
        content = obj.get("content", "")
        done = obj.get("done", False)
        if event == "thinking_chunk" and content:
            _lsmpe_append(msg_id, content, "thinking")
        elif event == "answer_chunk" and content:
            _lsmpe_append(msg_id, content)
        if done and event != "reasoning_summary_chunk":
            _lsmpe_finish(msg_id)
            return True
        return False
    except Exception:
        return False


class SemanticStreamBuffer:
    """语义流式缓冲器 - 按语义边界智能分段输出
    
    核心优化：
    1. 按句子边界缓冲，减少前端DOM更新次数
    2. 支持代码块、列表等特殊格式的完整输出
    3. 动态调整缓冲大小，平衡延迟和性能
    """
    
    def __init__(self, min_chunk_size=50, max_chunk_size=300, max_delay_ms=150):
        self.buffer = ""
        self.min_chunk_size = min_chunk_size
        self.max_chunk_size = max_chunk_size
        self.max_delay_ms = max_delay_ms
        self.last_flush_time = time.time() * 1000
        self.sentence_enders = {'.', '。', '!', '！', '?', '？', '\n', ';', '；', ':', '：'}
        self.block_markers = {'```', '```\n', '**', '*', '#', '##', '###', '- ', '1. ', '2. ', '3. '}
        
    def add_content(self, content):
        """添加内容到缓冲区"""
        self.buffer += content
        
    def should_flush(self, force=False):
        """判断是否应该刷新缓冲区
        
        刷新条件（满足任一）：
        1. 强制刷新
        2. 缓冲区达到最大大小
        3. 包含完整句子且达到最小大小
        4. 包含代码块标记
        5. 超过最大延迟时间
        """
        if force:
            return True
            
        buffer_len = len(self.buffer)
        
        # 条件2：达到最大大小
        if buffer_len >= self.max_chunk_size:
            return True
            
        # 条件3：包含完整句子且达到最小大小
        if buffer_len >= self.min_chunk_size:
            # 检查是否有句子结束符
            for char in reversed(self.buffer):
                if char in self.sentence_enders:
                    return True
                if char.isalnum():
                    break
                    
        # 条件4：包含代码块标记（确保代码块完整输出）
        if '```' in self.buffer and buffer_len >= 30:
            return True
            
        # 条件5：超过最大延迟
        current_time = time.time() * 1000
        if current_time - self.last_flush_time > self.max_delay_ms and buffer_len > 0:
            return True
            
        return False
        
    def flush(self):
        """刷新缓冲区，返回内容并清空"""
        content = self.buffer
        self.buffer = ""
        self.last_flush_time = time.time() * 1000
        return content
        
    def get_buffer_length(self):
        """获取当前缓冲区长度"""
        return len(self.buffer)


def get_mode_settings():
    """Compatibility helper for older routes that expect chat defaults."""
    return {
        "temperature": DEFAULT_CHAT_RUNTIME_CONFIG["temperature"],
        "repeat_penalty": DEFAULT_CHAT_RUNTIME_CONFIG["repeat_penalty"],
        "top_k": DEFAULT_CHAT_RUNTIME_CONFIG["top_k"],
        "top_p": DEFAULT_CHAT_RUNTIME_CONFIG["top_p"],
        "max_response_tokens": DEFAULT_CHAT_RUNTIME_CONFIG["max_response_tokens"],
    }


def build_system_prompt(runtime_cfg, persona=None):
    """
    构建系统提示词

    使用行为契约系统编译system prompt，替代旧版的分块拼接逻辑。
    如果存在角色卡的systemPrompt，优先使用角色卡内容。
    """
    # 优先级1: 角色卡的systemPrompt（前端编译的完整角色设定）
    if persona and isinstance(persona, dict) and persona.get("systemPrompt", "").strip():
        return persona["systemPrompt"].strip()

    # 优先级2: 行为契约编译
    return compile_system_prompt(runtime_cfg)


def _summarize_reasoning(message, level):
    if level == "off":
        return ""
    if level == "brief":
        return f"Focused on the core request: {message[:32]}"
    return f"Focused on the goal, constraints, and the shortest workable answer for: {message[:48]}"


def _should_search(message):
    """判断是否需要触发网络搜索
    
    使用更智能的逻辑避免误触发：
    1. 检查否定词（不、不要、别、无需等）
    2. 检查关键词是否在命令式语境中
    3. 排除纯聊天场景
    """
    lowered = message.lower()
    
    # 否定词列表（中英文）
    negative_patterns = [
        "不搜索", "不要搜索", "别搜索", "无需搜索", "不用搜索",
        "no search", "don't search", "do not search", "no need to search",
        "不需要", "不用", "别", "不要", "no need", "don't"
    ]
    
    # 如果包含否定词，不触发搜索
    if any(neg in lowered for neg in negative_patterns):
        return False
    
    # 搜索关键词列表
    search_keywords = ["search", "look up", "latest", "current", "news", "查一下", "搜索", "最新"]
    
    # 检查是否包含搜索关键词
    has_search_keyword = any(keyword in lowered for keyword in search_keywords)
    
    # 如果包含搜索关键词，进一步判断是否为命令式语境
    if has_search_keyword:
        # 命令式指示词（增加触发概率）
        imperative_indicators = [
            "请", "帮我", "帮我", "给我", "帮我查", "请搜索", "please", 
            "can you", "could you", "would you", "帮我找", "查一下"
        ]
        
        # 疑问词（增加触发概率）
        question_indicators = [
            "什么", "哪里", "怎么", "如何", "为什么", "多少", "什么时候",
            "what", "where", "how", "why", "when", "which", "who"
        ]
        
        # 如果包含命令式或疑问词，更可能真的需要搜索
        has_imperative = any(ind in lowered for ind in imperative_indicators)
        has_question = any(q in lowered for q in question_indicators)
        
        # 检查是否以问号结尾（强烈指示需要搜索）
        ends_with_question = message.strip().endswith('?') or message.strip().endswith('？')
        
        # 综合判断
        return has_imperative or has_question or ends_with_question
    
    return False


def _extract_search_query(message):
    query = message
    for trigger in ["search", "look up", "查一下", "搜索", "最新", "current", "latest"]:
        query = query.replace(trigger, "")
    return " ".join(query.split()).strip()


def _perform_web_search(query):
    if not query:
        return []
    try:
        from web_search_service import WebSearchService

        result = WebSearchService().search(query, max_results=2)
        data = result.get("data") or {}
        return data.get("results") or result.get("results") or []
    except Exception as e:
        logger.warning(f"search context unavailable: {e}")
        return []


def _format_search_results(results):
    if not results:
        return ""
    lines = ["Web search context:"]
    for item in results[:2]:
        title = item.get("title", "")
        snippet = item.get("snippet", "")[:120]
        if title or snippet:
            lines.append(f"- {title}: {snippet}")
    return "\n".join(lines)


def _build_chat_messages(user_message, runtime_cfg, persona=None, existing_messages=None, incoming_system_prompt=None, dem_ctx=None, session_id=None, persona_id=None, path_budget=None):
    """构建对话消息（支持历史消息 + 分层压缩 + 对话增强 + 路径预算控制）

    Args:
        user_message: 当前用户消息
        runtime_cfg: 运行配置
        persona: 人设
        existing_messages: 已有的历史消息数组
        incoming_system_prompt: 前端传入的系统提示词（优先使用）
        dem_ctx: 对话增强上下文（DialogueEnhancementMiddleware提供）
        session_id: 会话ID（统一引擎使用）
        persona_id: 角色ID（统一引擎使用）
        path_budget: 路径预算配置（RequestRouter生成），控制哪些增强步骤执行
    """
    # 解析路径预算
    skip_stages = path_budget.get("skip_stages", []) if path_budget else []
    budget = path_budget.get("budget", {}) if path_budget else {}

    if incoming_system_prompt and incoming_system_prompt.strip():
        system_prompt = incoming_system_prompt.strip()
    else:
        system_prompt = build_system_prompt(runtime_cfg, persona)

    _tc = TimingCollector.get_instance() if TIMING_AVAILABLE else None

    # Fast 路径跳过网络搜索
    search_context = ""
    if "web_search" not in skip_stages and _should_search(user_message):
        if _tc: _tc.start_stage("web_search")
        search_query = _extract_search_query(user_message)
        search_results = _perform_web_search(search_query)
        search_context = _format_search_results(search_results)
        if _tc: _tc.end_stage("web_search")

    # Fast 路径跳过 pre_enhance
    unified_addon = ""
    if "pre_enhance" not in skip_stages and UNIFIED_ENGINE_AVAILABLE and session_id:
        try:
            if _tc: _tc.start_stage("pre_enhance")
            engine = UnifiedEngine.get_instance()
            engine.record_turn(session_id, "user", user_message, persona_id or "default")
            pre_result = engine.pre_enhance(session_id, user_message, persona_id or "default")
            unified_addon = pre_result.get("system_prompt_addon", "")
            if _tc: _tc.end_stage("pre_enhance")
        except Exception as e:
            if _tc: _tc.end_stage("pre_enhance")
            logger.debug(f"[UnifiedEngine] pre_enhance failed (non-fatal): {e}")

    # Fast 路径跳过 DEM
    if "dem_pre_enhance" not in skip_stages and not unified_addon and dem_ctx and DEM_AVAILABLE:
        try:
            if _tc: _tc.start_stage("dem_pre_enhance")
            dem = DialogueEnhancementMiddleware.get_instance()
            dem_ctx.user_message = user_message
            dem_ctx.messages = existing_messages or []
            dem_ctx = dem.pre_enhance(dem_ctx)
            system_prompt = dem.inject_into_system_prompt(system_prompt, dem_ctx)
            if _tc: _tc.end_stage("dem_pre_enhance")
        except Exception as e:
            if _tc: _tc.end_stage("dem_pre_enhance")
            logger.debug(f"[DEM] pre_enhance failed (non-fatal): {e}")

    # Fast 路径跳过 memory
    memory_addon = ""
    if "memory_recall" not in skip_stages and UNIFIED_MEMORY_AVAILABLE and session_id and persona_id:
        try:
            if _tc: _tc.start_stage("unified_memory")
            uml = UnifiedMemoryLayer.get_instance()
            uml_result = uml.query(user_message, persona_id=persona_id, session_id=session_id)
            if uml_result and uml_result.system_prompt_addon:
                memory_addon = "\n" + uml_result.system_prompt_addon + "\n"
            if _tc: _tc.end_stage("unified_memory")
        except Exception as e:
            if _tc: _tc.end_stage("unified_memory")
            logger.debug(f"[UnifiedMemory] query failed (non-fatal): {e}")
    elif TEMG_AVAILABLE and session_id and persona_id:
        try:
            if _tc: _tc.start_stage("temg_recall")
            temg = TEMGEngine.get_instance(persona_id)
            mem_context = temg.recall(user_message, max_depth=3, top_k=3)
            if mem_context and mem_context.get("episodes"):
                episode_summaries = [ep.get("summary", "") for ep in mem_context["episodes"] if ep.get("summary")]
                if episode_summaries:
                    memory_addon = "\n[相关记忆]\n" + "\n".join(episode_summaries[:3]) + "\n"
            if _tc: _tc.end_stage("temg_recall")
        except Exception as e:
            if _tc: _tc.end_stage("temg_recall")
            logger.debug(f"[TEMG] recall failed (non-fatal): {e}")

    casc_addon = ""
    casc_intent = ""
    if CASC_AVAILABLE and session_id:
        try:
            if _tc: _tc.start_stage("casc_classify")
            casc = CASCEngine.get_instance(session_id=session_id)
            intent_result = casc.classify(user_message)
            if intent_result and intent_result.primary_intent:
                intent_val = intent_result.primary_intent.value
                casc_intent = intent_val
                if intent_val in ("command", "request", "technical"):
                    casc_addon = "\n[用户意图: 指令/请求，请直接执行并提供结果]\n"
                elif intent_val in ("question",):
                    casc_addon = "\n[用户意图: 提问，请给出详细解释]\n"
                elif intent_val in ("personal", "complaint", "praise", "greeting", "farewell", "small_talk"):
                    casc_addon = "\n[用户意图: 个人分享/情感表达，请表达共情和支持]\n"
                elif intent_val in ("creative_write", "brainstorm"):
                    casc_addon = "\n[用户意图: 创意/头脑风暴，请提供创意建议]\n"
            if _tc: _tc.end_stage("casc_classify")
        except Exception as e:
            if _tc: _tc.end_stage("casc_classify")
            logger.debug(f"[CASC] classify failed (non-fatal): {e}")

    if unified_addon:
        system_prompt = system_prompt + unified_addon
    if memory_addon:
        system_prompt = system_prompt + memory_addon
    if casc_addon:
        system_prompt = system_prompt + casc_addon

    messages = []
    if existing_messages and isinstance(existing_messages, list):
        for msg in existing_messages:
            if isinstance(msg, dict) and "role" in msg and "content" in msg:
                messages.append(msg)

    if CONTEXT_COMPRESSOR_AVAILABLE and messages and runtime_cfg.get("enable_context_compression", True):
        if _tc: _tc.start_stage("context_compress")
        num_ctx = _resolve_n_ctx(runtime_cfg)
        if num_ctx and num_ctx > 0:
            max_tokens = min(num_ctx, 8192)
        else:
            max_tokens = 8192

        config = CompressionConfig(
            max_context_tokens=max_tokens,
            system_prompt_reserve=len(system_prompt) // 3 + 200,
            recent_window_turns=runtime_cfg.get("recent_window_turns", 6),
            enable_l1=runtime_cfg.get("enable_l1_compression", True),
            enable_l2=runtime_cfg.get("enable_l2_compression", True),
            enable_l3=runtime_cfg.get("enable_l3_compression", True),
        )
        compressor = get_context_compressor(config)
        messages, comp_info = compressor.compress(messages)
        if _tc: _tc.end_stage("context_compress")

        if comp_info.get("compressed"):
            logger.info(
                f"[ContextCompressor] {comp_info['method']} | "
                f"{comp_info['original_tokens']}→{comp_info['compressed_tokens']} tokens | "
                f"节省 {comp_info['savings_pct']}%"
            )
    else:
        if _tc: _tc.end_stage("context_compress")

    if messages and messages[0]["role"] == "system":
        existing_system = messages.pop(0)
        existing_content = existing_system['content'].strip()
        # 角色卡内容放在前面（优先级最高），后端构建的system_prompt作为补充
        if existing_content:
            system_prompt = f"{existing_content}\n\n{system_prompt}"
        if search_context:
            system_prompt = f"{search_context}\n\n{system_prompt}"
    else:
        if search_context:
            system_prompt = f"{search_context}\n\n{system_prompt}"

    messages.insert(0, {"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": user_message})
    return messages, casc_intent


def _should_retry_without_thinking(payload, result, allow_retry=True):
    if not allow_retry:
        return False

    if payload.get("think") is False:
        return False

    content, thinking, _ = _extract_ollama_message(result)
    return not content and bool(thinking)


def _send_ollama_chat(payload, timeout=900, allow_thinking_retry=True, request_id=""):
    """
    发送 Ollama Chat 请求

    细粒度 timing：
    - ollama_connect: 连接建立时间
    - ollama_request: 实际请求+LLM生成时间
    - ollama_total: 总时间
    """
    _tc = TimingCollector.get_instance() if TIMING_AVAILABLE else None

    if _tc: _tc.start_stage("ollama_connect", request_id=request_id)

    start_total = time.time()
    start_conn = time.time()
    response = requests.post(f"{OLLAMA_BASE_URL}/api/chat", json=payload, timeout=timeout)
    conn_ms = round((time.time() - start_conn) * 1000, 1)

    if _tc: _tc.end_stage("ollama_connect", request_id=request_id)

    if _tc: _tc.start_stage("ollama_request", request_id=request_id)

    if response.status_code == 404:
        model_name = payload.get("model", "unknown")
        try:
            err_body = response.json()
            err_msg = err_body.get("error", "")
        except Exception:
            err_msg = response.text[:200]
        logger.warning(f"Ollama 404: 模型 \"{model_name}\" 未找到: {err_msg}")
        raise ValueError(f"模型 \"{model_name}\" 未在 Ollama 中注册: {err_msg}")
    response.raise_for_status()
    result = response.json()

    if not _should_retry_without_thinking(payload, result, allow_retry=allow_thinking_retry):
        if _tc: _tc.end_stage("ollama_request", request_id=request_id)
        total_ms = round((time.time() - start_total) * 1000, 1)
        if _tc: _tc.start_stage("ollama_total", request_id=request_id)
        if _tc: _tc.end_stage("ollama_total", request_id=request_id)
        logger.debug(f"[Ollama Timing] connect={conn_ms}ms, request={total_ms - conn_ms}ms, total={total_ms}ms")
        return result, payload

    if _tc: _tc.end_stage("ollama_request", request_id=request_id)

    retry_payload = dict(payload)
    retry_payload["think"] = False
    logger.warning("Ollama returned thinking without final content; retrying with think=false")

    if _tc: _tc.start_stage("ollama_request_retry", request_id=request_id)
    retry_response = requests.post(f"{OLLAMA_BASE_URL}/api/chat", json=retry_payload, timeout=timeout)
    retry_response.raise_for_status()
    result = retry_response.json()
    if _tc: _tc.end_stage("ollama_request_retry", request_id=request_id)

    total_ms = round((time.time() - start_total) * 1000, 1)
    if _tc: _tc.start_stage("ollama_total", request_id=request_id)
    if _tc: _tc.end_stage("ollama_total", request_id=request_id)
    logger.debug(f"[Ollama Timing] connect={conn_ms}ms, total={total_ms}ms (含重试)")

    return result, retry_payload


def _check_ollama_available():
    """检查 Ollama 服务是否可用"""
    try:
        response = requests.get(f"{OLLAMA_BASE_URL}/api/tags", timeout=2)
        return response.status_code == 200
    except Exception:
        return False


_ollama_model_cache = {"names": None, "timestamp": 0}
_OLLAMA_MODEL_CACHE_TTL = 30


def _get_ollama_model_names():
    """获取 Ollama 已注册模型名称列表（带30秒缓存）"""
    now = time.time()
    if _ollama_model_cache["names"] is not None and (now - _ollama_model_cache["timestamp"]) < _OLLAMA_MODEL_CACHE_TTL:
        return _ollama_model_cache["names"]
    try:
        resp = requests.get(f"{OLLAMA_BASE_URL}/api/tags", timeout=3)
        if resp.ok:
            data = resp.json()
            models = data.get("models", [])
            names = set()
            for m in models:
                n = m.get("name", "")
                if n:
                    names.add(n)
                    names.add(n.replace(":latest", ""))
            _ollama_model_cache["names"] = names
            _ollama_model_cache["timestamp"] = now
            return names
    except Exception:
        pass
    return _ollama_model_cache["names"] or set()


def _is_model_in_ollama(model_name: str) -> bool:
    """检查模型是否在 Ollama 注册表中"""
    # -local 后缀的模型强制走本地 llama.cpp 路线
    if model_name.endswith('-local'):
        return False
    names = _get_ollama_model_names()
    if not names:
        return True
    return model_name in names or model_name.replace(":latest", "") in names


def _try_local_model_chat(
    model,
    messages,
    stream=False,
    temperature=0.7,
    max_tokens=2048,
    repeat_penalty=1.1,
    top_k=40,
    top_p=0.9,
    thinking_requested=False,
    n_ctx=8192
):
    """尝试使用本地模型进行对话（自动检测 GGUF / safetensors）"""
    if not LOCAL_MODEL_AVAILABLE:
        return None

    # -local 后缀的模型，去掉后缀再传给加载器（实际 GGUF 文件不带 -local）
    actual_model = model[:-6] if model.endswith('-local') else model
    logger.info(f"尝试本地模型: {model} -> actual: {actual_model}, temperature={temperature}, repeat_penalty={repeat_penalty}, n_ctx={n_ctx}")

    if stream:
        def generate_local():
            try:
                thinking_sent_start = False
                for chunk in generate_chat_response(
                    model_name=actual_model,
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    stream=True,
                    repeat_penalty=repeat_penalty,
                    top_k=top_k,
                    top_p=top_p,
                    n_ctx=n_ctx
                ):
                    if "error" in chunk:
                        yield f"data: {json.dumps({'error': chunk['error'], 'done': True}, ensure_ascii=False)}\n\n"
                        return

                    content = chunk.get("message", {}).get("content", "")
                    thinking = chunk.get("message", {}).get("thinking", "")
                    done = chunk.get("done", False)
                    repeat_detected = chunk.get("repeat_detected", False)
                    suggested_temp = chunk.get("suggested_temperature", None)

                    if thinking and thinking_requested and not thinking_sent_start:
                        thinking_sent_start = True
                        yield f"data: {json.dumps({'event': 'thinking_start', 'done': False, 'created': int(time.time())}, ensure_ascii=False)}\n\n"

                    if thinking and thinking_requested:
                        yield f"data: {json.dumps({'event': 'thinking_chunk', 'content': thinking, 'done': False, 'created': int(time.time())}, ensure_ascii=False)}\n\n"

                    payload = {
                        "event": "answer_chunk",
                        "content": content,
                        "done": done,
                        "model": model,
                        "created": int(time.time()),
                        "repeat_detected": repeat_detected,
                        "suggested_temperature": suggested_temp,
                    }
                    yield f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"

                    if done:
                        break
            except Exception as e:
                logger.error(f"本地模型生成失败: {e}")
                yield f"data: {json.dumps({'error': str(e), 'done': True}, ensure_ascii=False)}\n\n"

        return generate_local()
    else:
        result = None
        for chunk in generate_chat_response(
            model_name=actual_model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            stream=False,
            repeat_penalty=repeat_penalty,
            top_k=top_k,
            top_p=top_p,
            n_ctx=n_ctx
        ):
            if "error" in chunk:
                return {"error": chunk["error"]}
            result = chunk

        return result


def _handle_auto_tool_call_stream(messages, model, runtime_cfg, conversation_id,
                                   ollama_available, local_available, lsmpe_msg_id,
                                   dem_ctx, persona_id, user_message, thinking_requested,
                                   model_in_ollama=False):
    if not AUTO_TOOL_CALL_AVAILABLE:
        return jsonify(error_response("auto_tool_call not available", 500)), 500

    caller = get_auto_tool_caller()

    def generate_agent_response():
        full_content = ""

        if model_in_ollama:
            gen = caller.run_agent_loop_stream(
                messages, model, runtime_cfg, OLLAMA_BASE_URL,
            )
            final_text = ""
            try:
                while True:
                    try:
                        sse_event = next(gen)
                        if isinstance(sse_event, str):
                            yield sse_event
                            try:
                                line = sse_event.strip()
                                if line.startswith("data: "):
                                    obj = json.loads(line[6:])
                                    if obj.get("event") == "answer_chunk" and obj.get("content"):
                                        full_content += obj["content"]
                            except (json.JSONDecodeError, IndexError):
                                pass
                    except StopIteration as e:
                        final_text = e.value if e.value else ("", None)
                        break
            except Exception as e:
                logger.error(f"[AutoToolCaller] Ollama流式agent循环异常: {e}")
                final_text = f"工具调用异常: {e}", None

            if isinstance(final_text, tuple):
                response_text, state = final_text
            else:
                response_text = str(final_text)
                state = None

            if not full_content and response_text:
                full_content = response_text
                yield f"data: {json.dumps({'event': 'answer_chunk', 'content': response_text, 'done': False, 'model': model, 'created': int(time.time())}, ensure_ascii=False)}\n\n"

            yield f"data: {json.dumps({'event': 'answer_chunk', 'content': '', 'done': True, 'model': model, 'created': int(time.time()), 'tool_call_state': state.to_dict() if state else None}, ensure_ascii=False)}\n\n"

            if lsmpe_msg_id:
                _lsmpe_append(lsmpe_msg_id, full_content)
                _lsmpe_finish(lsmpe_msg_id)

            if dem_ctx and DEM_AVAILABLE:
                try:
                    dem_ctx.assistant_message = full_content
                    DialogueEnhancementMiddleware.get_instance().post_enhance(dem_ctx)
                except Exception:
                    pass
            if UNIFIED_ENGINE_AVAILABLE:
                try:
                    engine = UnifiedEngine.get_instance()
                    engine.record_turn(conversation_id, "assistant", full_content, persona_id)
                    enhance_result = engine.post_enhance(conversation_id, user_message, full_content, persona_id)
                    if enhance_result and enhance_result.enhanced and enhance_result.enhanced != full_content:
                        full_content = enhance_result.enhanced
                except Exception:
                    pass

            elpe_decision = _elpe_decide_proactive(persona_id)
            elpe_event = _elpe_build_sse_event(elpe_decision)
            if elpe_event:
                yield elpe_event

            _unified_memory_store(user_message, full_content, persona_id=persona_id,
                                  session_id=conversation_id, conversation_id=conversation_id, model=model)

            return

        local_model_name = model[:-6] if model.endswith('-local') else model
        gen = caller.run_agent_loop_local_model_stream(
            messages, local_model_name, runtime_cfg,
        )
        final_text = ""
        try:
            while True:
                try:
                    sse_event = next(gen)
                    if isinstance(sse_event, str):
                        yield sse_event
                        try:
                            line = sse_event.strip()
                            if line.startswith("data: "):
                                obj = json.loads(line[6:])
                                if obj.get("event") == "answer_chunk" and obj.get("content"):
                                    full_content += obj["content"]
                        except (json.JSONDecodeError, IndexError):
                            pass
                except StopIteration as e:
                    final_text = e.value if e.value else ("", None)
                    break
        except Exception as e:
            logger.error(f"[AutoToolCaller] llama.cpp流式agent循环异常: {e}")
            final_text = f"工具调用异常: {e}", None

        if isinstance(final_text, tuple):
            response_text, state = final_text
        else:
            response_text = str(final_text)
            state = None

        if not full_content and response_text:
            full_content = response_text
            yield f"data: {json.dumps({'event': 'answer_chunk', 'content': response_text, 'done': False, 'model': model, 'created': int(time.time())}, ensure_ascii=False)}\n\n"

        yield f"data: {json.dumps({'event': 'answer_chunk', 'content': '', 'done': True, 'model': model, 'created': int(time.time()), 'tool_call_state': state.to_dict() if state else None}, ensure_ascii=False)}\n\n"

        if lsmpe_msg_id:
            _lsmpe_append(lsmpe_msg_id, full_content)
            _lsmpe_finish(lsmpe_msg_id)

        if dem_ctx and DEM_AVAILABLE:
            try:
                dem_ctx.assistant_message = full_content
                DialogueEnhancementMiddleware.get_instance().post_enhance(dem_ctx)
            except Exception:
                pass
        if UNIFIED_ENGINE_AVAILABLE:
            try:
                engine = UnifiedEngine.get_instance()
                engine.record_turn(conversation_id, "assistant", full_content, persona_id)
                enhance_result = engine.post_enhance(conversation_id, user_message, full_content, persona_id)
                if enhance_result and enhance_result.enhanced and enhance_result.enhanced != full_content:
                    full_content = enhance_result.enhanced
            except Exception:
                pass

        elpe_decision = _elpe_decide_proactive(persona_id)
        elpe_event = _elpe_build_sse_event(elpe_decision)
        if elpe_event:
            yield elpe_event

        _unified_memory_store(user_message, full_content, persona_id=persona_id,
                              session_id=conversation_id, conversation_id=conversation_id, model=model)

    return Response(
        stream_with_context(generate_agent_response()),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


def _handle_auto_tool_call_non_stream(messages, model, runtime_cfg, conversation_id,
                                       ollama_available, local_available, lsmpe_msg_id,
                                       dem_ctx, persona_id, user_message,
                                       model_in_ollama=False):
    _tc = TimingCollector.get_instance() if TIMING_AVAILABLE else None
    if _tc: _tc.mark_llm_start()

    if not AUTO_TOOL_CALL_AVAILABLE:
        if _tc: _tc.finish_request()
        return jsonify(error_response("auto_tool_call not available", 500)), 500

    caller = get_auto_tool_caller()

    response_text = ""
    state = None

    if model_in_ollama:
        response_text, state = caller.run_agent_loop_non_stream(
            messages, model, runtime_cfg, OLLAMA_BASE_URL,
        )
    else:
        local_model_name = model[:-6] if model.endswith('-local') else model
        response_text, state = caller.run_agent_loop_local_model(messages, local_model_name, runtime_cfg)

    if response_text and _tc: _tc.record_token(response_text)

    if lsmpe_msg_id:
        _lsmpe_append(lsmpe_msg_id, response_text)
        _lsmpe_finish(lsmpe_msg_id)

    if dem_ctx and DEM_AVAILABLE:
        try:
            dem_ctx.assistant_message = response_text
            DialogueEnhancementMiddleware.get_instance().post_enhance(dem_ctx)
        except Exception:
            pass
    if UNIFIED_ENGINE_AVAILABLE:
        try:
            engine = UnifiedEngine.get_instance()
            engine.record_turn(conversation_id, "assistant", response_text, persona_id)
            enhance_result = engine.post_enhance(conversation_id, user_message, response_text, persona_id)
            if enhance_result and enhance_result.enhanced and enhance_result.enhanced != response_text:
                response_text = enhance_result.enhanced
        except Exception:
            pass

    _unified_memory_store(user_message, response_text, persona_id=persona_id,
                          session_id=conversation_id, conversation_id=conversation_id, model=model)

    elpe_decision = _elpe_decide_proactive(persona_id)

    reasoning_summary = ""
    if runtime_cfg.get("show_reasoning_summary", False):
        reasoning_summary = _summarize_reasoning(user_message, runtime_cfg.get("reasoning_summary_level", "off"))

    response_data = {
        "response": response_text,
        "reasoning_summary": reasoning_summary,
        "conversation_id": conversation_id,
        "model": model,
        "options": {},
        "tool_call_state": state.to_dict() if state else None,
    }
    if elpe_decision and elpe_decision.get("action") == "send":
        response_data["proactive_suggestion"] = {
            "content": elpe_decision.get("utterance", ""),
            "score": elpe_decision.get("score", 0),
            "type_label": elpe_decision.get("type_label", ""),
        }

    if _tc: _tc.finish_request()
    return jsonify(success_response(data=response_data))


def register_chat_routes(app):
    @app.route("/api/chat", methods=["POST"])
    @require_api_key
    def chat_with_context():
        try:
            _tc = TimingCollector.get_instance() if TIMING_AVAILABLE else None
            req_id = str(uuid.uuid4())[:12]
            _tc_state = None

            data = request.json or {}
            if _tc: _tc_state = _tc.start_request(req_id)

            if _tc: _tc.start_stage("input_parse")
            message = _normalize_message_input(data)
            if not message:
                return jsonify(error_response("message is required", 400)), 400

            stream = bool(data.get("stream", False))
            model = data.get("model") or DEFAULT_CHAT_MODEL
            conversation_id = data.get("conversation_id") or str(uuid.uuid4())
            persona = data.get("persona") if isinstance(data.get("persona"), dict) else None
            incoming_system_prompt = data.get("system_prompt", "")
            incoming_chat_settings = data.get("chat_settings", {})
            runtime_cfg = _build_runtime_config(conversation_id, incoming_chat_settings)
            thinking_requested = isinstance(incoming_chat_settings, dict) and bool(incoming_chat_settings.get("thinking"))

            dem_ctx = None
            if DEM_AVAILABLE:
                try:
                    dem_ctx = EnhancementContext(
                        conversation_id=conversation_id,
                        persona_id=data.get("persona_id", "default") if isinstance(data.get("persona_id"), str) else "default",
                        model=model,
                    )
                except Exception:
                    dem_ctx = None

            persona_id = data.get("persona_id", "default") if isinstance(data.get("persona_id"), str) else "default"
            _proactive_record_activity(persona_id, conversation_id)
            if _tc: _tc.end_stage("input_parse")

            # 请求路由分类（决定走 Fast/Normal/Deep 哪条路径）
            if _tc: _tc.start_stage("request_route")
            existing_messages = data.get("messages") or []
            history_length = len(existing_messages) // 2 if isinstance(existing_messages, list) else 0

            if REQUEST_ROUTER_AVAILABLE:
                route_config = classify_request(
                    message=message,
                    history_length=history_length,
                    has_tool_intent=False,  # TODO: 从 CASC 获取工具意图
                    estimated_tokens=len(message) + sum(len(m.get("content", "")) for m in existing_messages if isinstance(m, dict))
                )
                path_budget = route_config
                logger.debug(f"[RequestRouter] 路径: {route_config['path_name']}, 跳过: {route_config['skip_stages']}")
            else:
                path_budget = None
            if _tc: _tc.end_stage("request_route")

            if _tc: _tc.start_stage("build_messages")
            messages, casc_intent = _build_chat_messages(
                message, runtime_cfg, persona, existing_messages,
                incoming_system_prompt, dem_ctx,
                session_id=conversation_id, persona_id=persona_id,
                path_budget=path_budget
            )
            if _tc: _tc.end_stage("build_messages")

            if UNIFIED_ENGINE_AVAILABLE:
                try:
                    if _tc: _tc.start_stage("manage_context")
                    _ue = UnifiedEngine.get_instance()
                    _sys_content = ""
                    if messages and messages[0].get("role") == "system":
                        _sys_content = messages[0].get("content", "")
                    messages = _ue.manage_context(messages, _sys_content)
                    if _tc: _tc.end_stage("manage_context")
                except Exception as _ctx_err:
                    if _tc: _tc.end_stage("manage_context")
                    logger.debug(f"[UnifiedEngine] manage_context failed (non-fatal): {_ctx_err}")

            if _tc: _tc.start_stage("build_payload")
            ollama_payload = _build_ollama_payload(model, messages, runtime_cfg, stream)
            if _tc: _tc.end_stage("build_payload")

            if _tc: _tc.start_stage("check_availability")
            if MODEL_AVAILABILITY_AVAILABLE:
                avail = check_model_availability(model)
                ollama_available = avail['ollama_available']
                local_available = avail['local_available']
                model_in_ollama = avail['model_in_ollama']
                is_gguf = avail['is_gguf']
            else:
                # -local 后缀的模型强制走本地路线
                if model.endswith('-local'):
                    model_in_ollama = False
                    ollama_available = False
                    local_available = LOCAL_MODEL_AVAILABLE and is_local_model_available(model[:-6])
                    is_gguf = LOCAL_MODEL_AVAILABLE and is_gguf_model(model[:-6])
                else:
                    if MODEL_REGISTRY_AVAILABLE:
                        model_in_ollama = is_model_available(model)
                        ollama_available = True
                    else:
                        model_in_ollama = True
                        ollama_available = True
                    local_available = LOCAL_MODEL_AVAILABLE and is_local_model_available(model)
                    is_gguf = LOCAL_MODEL_AVAILABLE and is_gguf_model(model)
            if _tc: _tc.end_stage("check_availability")

            _TOOL_INTENTS = {"command", "request", "technical"}
            auto_tool_call_enabled = (
                AUTO_TOOL_CALL_AVAILABLE
                and runtime_cfg.get("auto_tool_call", False)
                and get_auto_tool_caller().is_enabled()
                and (not casc_intent or casc_intent in _TOOL_INTENTS)
            )

            if stream:
                lsmpe_msg_id = _lsmpe_create(conversation_id, model)

                if auto_tool_call_enabled:
                    return _handle_auto_tool_call_stream(
                        messages, model, runtime_cfg, conversation_id,
                        ollama_available, local_available, lsmpe_msg_id,
                        dem_ctx, persona_id, message, thinking_requested,
                        model_in_ollama=model_in_ollama,
                    )

                def generate_response():
                    # 先回声：立即输出 pending 状态，让用户感知到响应已经开始
                    yield f"data: {json.dumps({'event': 'status', 'status': 'thinking', 'done': False, 'created': int(time.time())}, ensure_ascii=False)}\n\n"

                    if _tc: _tc.mark_llm_start(request_id=req_id)
                    level = runtime_cfg.get("reasoning_summary_level", "off")
                    if runtime_cfg.get("show_reasoning_summary", False) and level != "off":
                        summary = _summarize_reasoning(message, level)
                        yield f"data: {json.dumps({'event': 'reasoning_summary_chunk', 'content': summary, 'done': False, 'created': int(time.time())}, ensure_ascii=False)}\n\n"

                    repetition_detector = create_detector(REPETITION_DETECTION_CONFIG)
                    full_content = ""

                    # ========== 路由策略：Ollama有的走Ollama，没有的直接走llama.cpp ==========
                    if model_in_ollama:
                        logger.info(f"模型在Ollama中，使用Ollama: {model}")
                        try:
                            semantic_buffer = SemanticStreamBuffer(
                                min_chunk_size=30,
                                max_chunk_size=300,
                                max_delay_ms=80
                            )

                            ollama_timeout = runtime_cfg.get("ollama_timeout", 900)
                            connect_timeout = min(30, ollama_timeout)
                            read_timeout = max(ollama_timeout, 120)
                            try:
                                if _tc: _tc.start_stage("ollama_connect", request_id=req_id)
                                start_total = time.time()
                                with requests.post(
                                    f"{OLLAMA_BASE_URL}/api/chat",
                                    json=ollama_payload,
                                    timeout=(connect_timeout, read_timeout),
                                    stream=True,
                                ) as response:
                                    conn_ms = round((time.time() - start_total) * 1000, 1)
                                    if _tc: _tc.end_stage("ollama_connect", request_id=req_id)
                                    if _tc: _tc.start_stage("ollama_stream", request_id=req_id)

                                    if response.status_code == 404:
                                        try:
                                            err_body = response.json()
                                            err_msg = err_body.get("error", "")
                                        except Exception:
                                            err_msg = response.text[:200]
                                        logger.warning(f"Ollama 流式 404: 模型 \"{model}\" 未找到: {err_msg}")
                                        raise ValueError(f"模型 \"{model}\" 未在 Ollama 中注册: {err_msg}")
                                    response.raise_for_status()
                                    thinking_sent_start = False
                                    for line in response.iter_lines():
                                        if not line:
                                            continue
                                        try:
                                            chunk = json.loads(line.decode("utf-8"))
                                        except json.JSONDecodeError:
                                            continue

                                        content = chunk.get("message", {}).get("content", "")
                                        thinking = chunk.get("message", {}).get("thinking", "")
                                        full_content += content
                                        if content and _tc: _tc.record_token(content)

                                        if thinking and thinking_requested and not thinking_sent_start:
                                            thinking_sent_start = True
                                            yield f"data: {json.dumps({'event': 'thinking_start', 'done': False, 'created': int(time.time())}, ensure_ascii=False)}\n\n"

                                        if thinking and thinking_requested:
                                            yield f"data: {json.dumps({'event': 'thinking_chunk', 'content': thinking, 'done': False, 'created': int(time.time())}, ensure_ascii=False)}\n\n"
                                            _lsmpe_append(lsmpe_msg_id, thinking, "thinking")

                                        should_stop, reason = repetition_detector.process_token(content)

                                        if should_stop:
                                            logger.warning(f"重复检测触发截断: {reason}")
                                            if semantic_buffer.get_buffer_length() > 0:
                                                buffered_content = semantic_buffer.flush()
                                                payload = {
                                                    "event": "answer_chunk",
                                                    "content": buffered_content,
                                                    "done": False,
                                                    "model": model,
                                                    "created": int(time.time()),
                                                }
                                                yield f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"

                                            payload = {
                                                "event": "answer_chunk",
                                                "content": content,
                                                "done": True,
                                                "model": model,
                                                "created": int(time.time()),
                                                "truncated": True,
                                                "truncation_reason": reason,
                                                "suggested_params": repetition_detector.get_suggested_params(),
                                            }
                                            yield f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"
                                            _lsmpe_finish(lsmpe_msg_id)
                                            break

                                        semantic_buffer.add_content(content)
                                        _lsmpe_append(lsmpe_msg_id, content)

                                        if semantic_buffer.should_flush(chunk.get("done", False)):
                                            buffered_content = semantic_buffer.flush()
                                            payload = {
                                                "event": "answer_chunk",
                                                "content": buffered_content,
                                                "done": chunk.get("done", False),
                                                "model": model,
                                                "created": int(time.time()),
                                            }
                                            yield f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"

                                        if chunk.get("done", False):
                                            if semantic_buffer.get_buffer_length() > 0:
                                                final_content = semantic_buffer.flush()
                                                final_payload = {
                                                    "event": "answer_chunk",
                                                    "content": final_content,
                                                    "done": True,
                                                    "model": model,
                                                    "created": int(time.time()),
                                                }
                                                yield f"data: {json.dumps(final_payload, ensure_ascii=False)}\n\n"
                                            _lsmpe_finish(lsmpe_msg_id)

                                            if dem_ctx and DEM_AVAILABLE:
                                                try:
                                                    dem_ctx.assistant_message = full_content
                                                    dem = DialogueEnhancementMiddleware.get_instance()
                                                    dem.post_enhance(dem_ctx)
                                                except Exception as e:
                                                    logger.debug(f"[DEM] stream post_enhance failed (non-fatal): {e}")

                                            if UNIFIED_ENGINE_AVAILABLE:
                                                try:
                                                    engine = UnifiedEngine.get_instance()
                                                    engine.record_turn(conversation_id, "assistant", full_content, persona_id)
                                                    engine.post_enhance(conversation_id, message, full_content, persona_id)
                                                except Exception as e:
                                                    logger.debug(f"[UnifiedEngine] stream post_enhance failed (non-fatal): {e}")

                                            _kg_extract_if_available(message, full_content, conversation_id, model)

                                            if _tc:
                                                total_ms = round((time.time() - start_total) * 1000, 1)
                                                _tc.end_stage("ollama_stream", request_id=req_id)
                                                logger.debug(f"[Ollama Stream] connect={conn_ms}ms, stream={total_ms - conn_ms}ms, total={total_ms}ms")
                                                timing_result = _tc.finish_request(request_id=req_id)
                                                if timing_result:
                                                    timing_payload = {
                                                        "event": "timing",
                                                        "timing": timing_result.to_dict(),
                                                        "done": True,
                                                    }
                                                    yield f"data: {json.dumps(timing_payload, ensure_ascii=False)}\n\n"

                                            break
                                return
                            except Exception as e:
                                logger.error(f"Ollama 流式请求失败: {e}")
                                _lsmpe_finish(lsmpe_msg_id, STATUS_FAILED)
                                yield f"data: {json.dumps({'error': f'Ollama 请求失败: {e}', 'done': True}, ensure_ascii=False)}\n\n"
                                return
                        except Exception as e:
                            logger.error(f"Ollama 分支异常: {e}")
                            _lsmpe_finish(lsmpe_msg_id, STATUS_FAILED)
                            yield f"data: {json.dumps({'error': f'Ollama 异常: {e}', 'done': True}, ensure_ascii=False)}\n\n"
                            return
                    else:
                        logger.info(f"模型不在Ollama中，使用llama.cpp: {model}")
                        try:
                            local_result = _try_local_model_chat(
                                model, messages, stream=True,
                                temperature=runtime_cfg.get("temperature", 0.7),
                                max_tokens=runtime_cfg.get("max_response_tokens", -1),
                                repeat_penalty=runtime_cfg.get("repeat_penalty", 1.1),
                                top_k=runtime_cfg.get("top_k", 40),
                                top_p=runtime_cfg.get("top_p", 0.9),
                                thinking_requested=thinking_requested,
                                n_ctx=_resolve_n_ctx(runtime_cfg)
                            )
                            if local_result:
                                has_content = False
                                full_local_content = ""
                                lsmpe_already_finished = False
                                for sse_line in local_result:
                                    has_content = True
                                    if _lsmpe_intercept_sse(lsmpe_msg_id, sse_line):
                                        lsmpe_already_finished = True
                                    yield sse_line
                                    try:
                                        chunk_data = json.loads(sse_line.strip().split("data: ", 1)[1] if sse_line.strip().startswith("data: ") else "{}")
                                        if chunk_data.get("content"):
                                            full_local_content += chunk_data["content"]
                                            if _tc: _tc.record_token(chunk_data["content"])
                                    except Exception:
                                        pass
                                if has_content:
                                    if dem_ctx and DEM_AVAILABLE:
                                        try:
                                            dem_ctx.assistant_message = full_local_content
                                            dem = DialogueEnhancementMiddleware.get_instance()
                                            dem.post_enhance(dem_ctx)
                                        except Exception as e:
                                            logger.debug(f"[DEM] local stream post_enhance failed (non-fatal): {e}")

                                    if UNIFIED_ENGINE_AVAILABLE:
                                        try:
                                            engine = UnifiedEngine.get_instance()
                                            engine.record_turn(conversation_id, "assistant", full_local_content, persona_id)
                                            engine.post_enhance(conversation_id, message, full_local_content, persona_id)
                                        except Exception as e:
                                            logger.debug(f"[UnifiedEngine] local stream post_enhance failed (non-fatal): {e}")

                                    _kg_extract_if_available(message, full_local_content, conversation_id, model)

                                    if not lsmpe_already_finished:
                                        _lsmpe_finish(lsmpe_msg_id)

                                    if _tc:
                                        timing_result = _tc.finish_request()
                                        if timing_result:
                                            timing_payload = {
                                                "event": "timing",
                                                "timing": timing_result.to_dict(),
                                                "done": True,
                                            }
                                            yield f"data: {json.dumps(timing_payload, ensure_ascii=False)}\n\n"

                                    return
                            logger.warning("llama.cpp 无输出")
                            _lsmpe_finish(lsmpe_msg_id, STATUS_FAILED)
                            yield f"data: {json.dumps({'error': f'llama.cpp 模型 \"{model}\" 无输出', 'done': True}, ensure_ascii=False)}\n\n"
                        except Exception as e:
                            logger.error(f"llama.cpp 异常: {e}")
                            _lsmpe_finish(lsmpe_msg_id, STATUS_FAILED)
                            yield f"data: {json.dumps({'error': f'llama.cpp 异常: {e}', 'done': True}, ensure_ascii=False)}\n\n"

                return Response(
                    stream_with_context(generate_response()),
                    mimetype="text/event-stream",
                    headers={
                        "Cache-Control": "no-cache, no-transform",
                        "X-Accel-Buffering": "no",
                        "Connection": "keep-alive",
                    },
                )

            logger.info(f"[DEBUG] ollama_available={ollama_available}, local_available={local_available}, model={model}")

            lsmpe_msg_id = _lsmpe_create(conversation_id, model)

            if auto_tool_call_enabled:
                return _handle_auto_tool_call_non_stream(
                    messages, model, runtime_cfg, conversation_id,
                    ollama_available, local_available, lsmpe_msg_id,
                    dem_ctx, persona_id, message,
                    model_in_ollama=model_in_ollama,
                )

            # ========== 路由策略：Ollama有的走Ollama，没有的直接走llama.cpp ==========
            if model_in_ollama:
                try:
                    logger.info(f"模型在Ollama中，使用Ollama: {model}")
                    ollama_timeout = runtime_cfg.get("ollama_timeout", 900)
                    result, used_payload = _send_ollama_chat(
                        ollama_payload,
                        timeout=ollama_timeout,
                        allow_thinking_retry=not thinking_requested,
                        request_id=req_id,
                    )
                    response_text, thinking_text, done_reason = _extract_ollama_message(result)
                    logger.info(
                        "[DEBUG] Ollama response content length: %s, thinking length: %s, done_reason=%s",
                        len(response_text),
                        len(thinking_text),
                        done_reason or "unknown",
                    )
                    _lsmpe_append(lsmpe_msg_id, response_text)
                    if thinking_text:
                        _lsmpe_append(lsmpe_msg_id, thinking_text, "thinking")
                    _lsmpe_finish(lsmpe_msg_id)

                    if dem_ctx and DEM_AVAILABLE:
                        try:
                            dem_ctx.assistant_message = response_text
                            dem = DialogueEnhancementMiddleware.get_instance()
                            dem.post_enhance(dem_ctx)
                        except Exception as e:
                            logger.debug(f"[DEM] post_enhance failed (non-fatal): {e}")

                    if UNIFIED_ENGINE_AVAILABLE:
                        try:
                            engine = UnifiedEngine.get_instance()
                            engine.record_turn(conversation_id, "assistant", response_text, persona_id)
                            engine.post_enhance(conversation_id, message, response_text, persona_id)
                        except Exception as e:
                            logger.debug(f"[UnifiedEngine] post_enhance failed (non-fatal): {e}")

                    _kg_extract_if_available(message, response_text, conversation_id, model)

                    reasoning_summary = ""
                    if runtime_cfg.get("show_reasoning_summary", False):
                        reasoning_summary = _summarize_reasoning(message, runtime_cfg.get("reasoning_summary_level", "off"))

                    if _tc: _tc.finish_request(request_id=req_id)
                    return jsonify(
                        success_response(
                            data={
                                "response": response_text,
                                "reasoning_summary": reasoning_summary,
                                "conversation_id": conversation_id,
                                "model": model,
                                "options": used_payload["options"],
                            }
                        )
                    )
                except Exception as e:
                    logger.error(f"Ollama chat failed: {e}")
                    _lsmpe_finish(lsmpe_msg_id, STATUS_FAILED)
                    if AUTO_HEAL_AVAILABLE:
                        auto_heal.diagnose_and_repair(
                            error_message=str(e),
                            source="chat.ollama",
                            extra={"model": model},
                        )
                    if _tc: _tc.finish_request(request_id=req_id)
                    return jsonify(error_response(f"Ollama 请求失败: {e}", 500)), 500
            
            # ========== 模型不在Ollama中，直接走llama.cpp ==========
            try:
                logger.info(f"模型不在Ollama中，使用llama.cpp: {model}")
                local_result = _try_local_model_chat(
                    model, messages, stream=False,
                    temperature=runtime_cfg.get("temperature", 0.7),
                    max_tokens=runtime_cfg.get("max_response_tokens", 2048),
                    repeat_penalty=runtime_cfg.get("repeat_penalty", 1.1),
                    top_k=runtime_cfg.get("top_k", 40),
                    top_p=runtime_cfg.get("top_p", 0.9),
                    thinking_requested=thinking_requested,
                    n_ctx=_resolve_n_ctx(runtime_cfg)
                )
                
                if local_result and "error" not in local_result:
                    response_text = local_result.get("message", {}).get("content", "")
                    thinking_text = local_result.get("message", {}).get("thinking", "")
                    if not response_text and thinking_text:
                        response_text = thinking_text
                        logger.info("非流式llama.cpp: content为空，使用thinking作为回复")
                    _lsmpe_append(lsmpe_msg_id, response_text)
                    if thinking_text:
                        _lsmpe_append(lsmpe_msg_id, thinking_text, "thinking")
                    _lsmpe_finish(lsmpe_msg_id)

                    if dem_ctx and DEM_AVAILABLE:
                        try:
                            dem_ctx.assistant_message = response_text
                            dem = DialogueEnhancementMiddleware.get_instance()
                            dem.post_enhance(dem_ctx)
                        except Exception as e:
                            logger.debug(f"[DEM] local post_enhance failed (non-fatal): {e}")

                    if UNIFIED_ENGINE_AVAILABLE:
                        try:
                            engine = UnifiedEngine.get_instance()
                            engine.record_turn(conversation_id, "assistant", response_text, persona_id)
                            engine.post_enhance(conversation_id, message, response_text, persona_id)
                        except Exception as e:
                            logger.debug(f"[UnifiedEngine] local post_enhance failed (non-fatal): {e}")

                    reasoning_summary = ""
                    if runtime_cfg.get("show_reasoning_summary", False):
                        reasoning_summary = _summarize_reasoning(message, runtime_cfg.get("reasoning_summary_level", "off"))
                    
                    if _tc: _tc.finish_request(request_id=req_id)
                    return jsonify(
                        success_response(
                            data={
                                "response": response_text,
                                "reasoning_summary": reasoning_summary,
                                "conversation_id": conversation_id,
                                "model": model,
                                "options": {},
                            }
                        )
                    )
                error_detail = local_result.get('error', 'unknown') if local_result else 'no result'
                logger.warning(f"llama.cpp 失败: {error_detail}")
                _lsmpe_finish(lsmpe_msg_id, STATUS_FAILED)
                if _tc: _tc.finish_request(request_id=req_id)
                return jsonify(error_response(f"llama.cpp 模型 \"{model}\" 失败: {error_detail}", 500)), 500
            except Exception as e:
                logger.error(f"llama.cpp 异常: {e}")
                _lsmpe_finish(lsmpe_msg_id, STATUS_FAILED)
                if _tc: _tc.finish_request(request_id=req_id)
                return jsonify(error_response(f"llama.cpp 异常: {e}", 500)), 500
            
        except Exception as e:
            logger.error(f"chat failed: {e}")
            if _tc: _tc.finish_request(request_id=req_id)
            return jsonify(error_response(str(e), 500)), 500

    @app.route("/v1/chat/completions", methods=["POST"])
    @app.route("/v1/completions", methods=["POST"])
    @require_api_key
    def openai_chat_completion():
        try:
            data = request.json or {}
            messages = data.get("messages") or []
            prompt = data.get("prompt", "")
            if not messages and prompt:
                messages = [{"role": "user", "content": prompt}]
            if not messages:
                return jsonify(error_response("messages is required", 400)), 400

            model = data.get("model") or DEFAULT_OPENAI_COMPAT_MODEL
            temperature = float(data.get("temperature", DEFAULT_CHAT_RUNTIME_CONFIG["temperature"]))
            max_tokens = int(data.get("max_tokens", DEFAULT_CHAT_RUNTIME_CONFIG["max_response_tokens"]))
            stream = bool(data.get("stream", False))
            request_id = f"chatcmpl-{uuid.uuid4().hex[:8]}"

            runtime_cfg = {
                **DEFAULT_CHAT_RUNTIME_CONFIG,
                "temperature": temperature,
                "max_response_tokens": max_tokens,
            }
            payload = _build_ollama_payload(model, messages, runtime_cfg, stream)

            if stream:
                def generate_stream():
                    try:
                        ollama_timeout = runtime_cfg.get("ollama_timeout", 900)

                        if _tc: _tc.start_stage("ollama_connect", request_id=request_id)
                        start_total = time.time()
                        with requests.post(
                            f"{OLLAMA_BASE_URL}/api/chat",
                            json=payload,
                            timeout=ollama_timeout,
                            stream=True,
                        ) as response:
                            conn_ms = round((time.time() - start_total) * 1000, 1)
                            if _tc: _tc.end_stage("ollama_connect", request_id=request_id)
                            if _tc: _tc.start_stage("ollama_stream", request_id=request_id)

                            if response.status_code == 404:
                                try:
                                    err_body = response.json()
                                    err_msg = err_body.get("error", "")
                                except Exception:
                                    err_msg = response.text[:200]
                                raise ValueError(f"模型 \"{model}\" 未在 Ollama 中注册: {err_msg}")
                            response.raise_for_status()
                            for line in response.iter_lines():
                                if not line:
                                    continue
                                try:
                                    chunk = json.loads(line.decode("utf-8"))
                                except json.JSONDecodeError:
                                    continue
                                content = chunk.get("message", {}).get("content", "")
                                done = chunk.get("done", False)
                                openai_chunk = {
                                    "id": request_id,
                                    "object": "chat.completion.chunk",
                                    "created": int(time.time()),
                                    "model": model,
                                    "choices": [{
                                        "index": 0,
                                        "delta": {"content": content},
                                        "finish_reason": "stop" if done else None,
                                    }],
                                }
                                yield f"data: {json.dumps(openai_chunk, ensure_ascii=False)}\n\n"
                                if done:
                                    break
                            if _tc: _tc.end_stage("ollama_stream", request_id=request_id)
                            total_ms = round((time.time() - start_total) * 1000, 1)
                            logger.debug(f"[Ollama Stream] connect={conn_ms}ms, stream={total_ms - conn_ms}ms, total={total_ms}ms")
                            yield "data: [DONE]\n\n"
                    except Exception as e:
                        logger.error(f"openai stream failed: {e}")
                        yield f"data: {json.dumps({'error': str(e)})}\n\n"

                return Response(stream_with_context(generate_stream()), mimetype="text/event-stream")

            ollama_timeout = runtime_cfg.get("ollama_timeout", 900)
            result, _ = _send_ollama_chat(payload, timeout=ollama_timeout, request_id=request_id)
            content, _, _ = _extract_ollama_message(result)

            last_user_msg = ""
            for m in reversed(messages):
                if m.get("role") == "user":
                    last_user_msg = m.get("content", "")
                    break
            _kg_extract_if_available(last_user_msg, content, request_id, model)

            return jsonify(
                {
                    "id": request_id,
                    "object": "chat.completion",
                    "created": int(time.time()),
                    "model": model,
                    "choices": [{
                        "index": 0,
                        "message": {"role": "assistant", "content": content},
                        "finish_reason": "stop",
                    }],
                    "usage": {
                        "prompt_tokens": result.get("prompt_eval_count", 0),
                        "completion_tokens": result.get("eval_count", 0),
                        "total_tokens": result.get("prompt_eval_count", 0) + result.get("eval_count", 0),
                    },
                }
            )
        except Exception as e:
            logger.error(f"openai compatible chat failed: {e}")
            return jsonify(error_response(str(e), 500)), 500

    @app.route("/api/context/compress", methods=["POST"])
    def compress_context():
        """压缩上下文消息 - 用于测试和预览压缩效果"""
        try:
            data = request.json or {}
            messages = data.get("messages", [])
            if not messages:
                return jsonify(error_response("messages is required", 400)), 400

            num_ctx = data.get("num_ctx", 8192)
            max_tokens = min(num_ctx, 8192) if num_ctx and num_ctx > 0 else 8192

            if not CONTEXT_COMPRESSOR_AVAILABLE:
                return jsonify(error_response("context_compressor module not available", 500)), 500

            config = CompressionConfig(
                max_context_tokens=max_tokens,
                enable_l1=data.get("enable_l1", True),
                enable_l2=data.get("enable_l2", True),
                enable_l3=data.get("enable_l3", True),
            )
            compressor = get_context_compressor(config)
            compressed, info = compressor.compress(messages)

            return jsonify(success_response(data={
                "compressed_messages": compressed,
                "compression_info": info,
                "stats": compressor.get_stats(),
            }))
        except Exception as e:
            logger.error(f"context compress failed: {e}")
            return jsonify(error_response(str(e), 500)), 500

    @app.route("/api/context/compression-stats", methods=["GET"])
    def context_compression_stats():
        """获取压缩引擎统计信息"""
        if not CONTEXT_COMPRESSOR_AVAILABLE:
            return jsonify(success_response(data={"available": False}))
        compressor = get_context_compressor()
        return jsonify(success_response(data={
            "available": True,
            "stats": compressor.get_stats(),
        }))

    @app.route("/api/intent", methods=["POST"])
    def classify_intent():
        try:
            from intent_classifier import IntentClassifier
            from smart_cache import FastPathRouter, get_three_level_cache
            data = request.json or {}
            message = (data.get("message") or "").strip()
            if not message:
                return jsonify(error_response("message is required", 400)), 400

            model = data.get("model", "")
            history = data.get("history")
            engine_mode = data.get("engine", "casc")
            user_id = data.get("user_id", "default")
            session_id = data.get("session_id", "")

            classifier = IntentClassifier(engine=engine_mode, model=model, user_id=user_id, session_id=session_id)
            result = classifier.classify(message, history=history)

            intent_data = {
                "intent": result.primary_intent,
                "description": classifier.get_intent_description(result.primary_intent),
                "confidence": result.confidence,
                "emotion": result.emotion,
                "entities": result.entities,
                "engine": result.engine,
                "exit_level": result.exit_level,
                "latency_ms": result.latency_ms,
            }

            tlc = get_three_level_cache()
            router = FastPathRouter(tlc)
            route_result = router.route(message, intent_data)
            intent_data["_path"] = route_result.get("_path", "fast_casc")

            if hasattr(result, "intent_analysis") and result.intent_analysis:
                intent_data["intent_analysis"] = result.intent_analysis

            return jsonify(success_response(intent_data))
        except Exception as e:
            logger.error(f"intent classification failed: {e}")
            return jsonify(error_response(str(e), 500)), 500

    @app.route("/api/recommend", methods=["POST"])
    def get_recommendations():
        try:
            from session_store import SessionStore
            from intent_miner import IntentMiner
            data = request.json or {}
            user_id = data.get("user_id", "default")
            current_intent = data.get("current_intent", "")
            limit = min(data.get("limit", 5), 10)

            store = SessionStore.get_instance()
            miner = IntentMiner(store)
            recs = miner.recommend(user_id, current_intent, limit)

            return jsonify(success_response({
                "user_id": user_id,
                "recommendations": recs,
                "count": len(recs),
            }))
        except Exception as e:
            logger.error(f"recommendation failed: {e}")
            return jsonify(error_response(str(e), 500)), 500

    @app.route("/api/chat/settings", methods=["POST"])
    def update_chat_settings():
        try:
            data = request.json or {}
            chat_settings = data.get("chat_settings", {})
            if not isinstance(chat_settings, dict):
                return jsonify(error_response("chat_settings must be an object", 400)), 400

            validated = {}
            if "temperature" in chat_settings:
                validated["temperature"] = max(0.0, min(2.0, float(chat_settings["temperature"])))
            if "top_p" in chat_settings:
                validated["top_p"] = max(0.0, min(1.0, float(chat_settings["top_p"])))
            if "top_k" in chat_settings:
                validated["top_k"] = max(1, min(100, int(chat_settings["top_k"])))
            if "repeat_penalty" in chat_settings:
                validated["repeat_penalty"] = max(1.0, min(2.0, float(chat_settings["repeat_penalty"])))
            if "max_response_tokens" in chat_settings:
                val = int(chat_settings["max_response_tokens"])
                validated["max_response_tokens"] = val if val == -1 else max(1, min(32768, val))
            if "num_ctx" in chat_settings:
                val = int(chat_settings["num_ctx"])
                validated["num_ctx"] = val if val == -1 else max(512, min(131072, val))

            import json as _json
            settings_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "chat_settings.json")
            os.makedirs(os.path.dirname(settings_path), exist_ok=True)

            existing = {}
            if os.path.exists(settings_path):
                try:
                    with open(settings_path, "r", encoding="utf-8") as f:
                        existing = _json.load(f)
                except Exception:
                    existing = {}

            existing.update(validated)
            existing["_updated_at"] = time.time()

            # 原子写入：先写临时文件，再重命名（避免并发写入竞争）
            temp_path = settings_path + ".tmp"
            try:
                with open(temp_path, "w", encoding="utf-8") as f:
                    _json.dump(existing, f, ensure_ascii=False, indent=2)
                os.replace(temp_path, settings_path)  # 原子操作
            except Exception:
                if os.path.exists(temp_path):
                    os.remove(temp_path)
                raise

            return jsonify(success_response({
                "message": "设置已保存",
                "settings": {k: v for k, v in existing.items() if not k.startswith("_")}
            }))
        except Exception as e:
            logger.error(f"update chat settings failed: {e}")
            return jsonify(error_response(str(e), 500)), 500

    @app.route("/api/chat/settings", methods=["GET"])
    def get_chat_settings():
        try:
            import json as _json
            settings_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "chat_settings.json")
            existing = {}
            if os.path.exists(settings_path):
                try:
                    with open(settings_path, "r", encoding="utf-8") as f:
                        existing = _json.load(f)
                except Exception:
                    existing = {}

            return jsonify(success_response({
                "settings": {k: v for k, v in existing.items() if not k.startswith("_")}
            }))
        except Exception as e:
            logger.error(f"get chat settings failed: {e}")
            return jsonify(error_response(str(e), 500)), 500

    @app.route("/api/enhancement/settings", methods=["GET"])
    def get_enhancement_settings():
        try:
            if not DEM_AVAILABLE:
                return jsonify(success_response({
                    "available": False,
                    "settings": {
                        "enable_context_compression": False,
                        "enable_dialogue_enhancement": False,
                        "enable_memory_injection": False,
                        "compression_threshold": 0.7,
                        "max_history_messages": 20,
                    },
                }))
            dem = DialogueEnhancementMiddleware.get_instance()
            return jsonify(success_response({
                "available": True,
                "settings": dem.get_settings(),
            }))
        except Exception as e:
            logger.error(f"get enhancement settings failed: {e}")
            return jsonify(error_response(str(e), 500)), 500

    @app.route("/api/enhancement/settings", methods=["POST"])
    def update_enhancement_settings():
        try:
            if not DEM_AVAILABLE:
                return jsonify(error_response("Dialogue Enhancement Middleware not available", 503)), 503

            data = request.json or {}
            new_settings = data.get("settings", {})
            if not isinstance(new_settings, dict):
                return jsonify(error_response("settings must be an object", 400)), 400

            dem = DialogueEnhancementMiddleware.get_instance()
            saved = dem.save_settings(new_settings)
            return jsonify(success_response({
                "message": "对话增强设置已保存",
                "settings": saved,
            }))
        except Exception as e:
            logger.error(f"update enhancement settings failed: {e}")
            return jsonify(error_response(str(e), 500)), 500

    @app.route("/api/enhancement/status", methods=["GET"])
    def get_enhancement_status():
        try:
            if not DEM_AVAILABLE:
                return jsonify(success_response({"available": False}))
            dem = DialogueEnhancementMiddleware.get_instance()
            persona_id = request.args.get("persona_id", "default")
            return jsonify(success_response(dem.get_enhancement_status(persona_id)))
        except Exception as e:
            logger.error(f"get enhancement status failed: {e}")
            return jsonify(error_response(str(e), 500)), 500

    @app.route("/api/tools/list", methods=["GET"])
    def list_available_tools():
        if not AUTO_TOOL_CALL_AVAILABLE:
            return jsonify(success_response({"available": False, "tools": []}))
        try:
            try:
                from function_engine import skill_registry
            except ImportError:
                from server.function_engine import skill_registry
            tools = []
            for skill in skill_registry.list_skills():
                if skill.require_confirmation:
                    continue
                params = []
                if hasattr(skill, 'parameters'):
                    for p in skill.parameters:
                        params.append({
                            "name": p.name,
                            "type": p.type,
                            "description": p.description,
                            "required": p.required,
                        })
                tools.append({
                    "name": skill.name,
                    "description": skill.description,
                    "category": skill.category.value if hasattr(skill.category, 'value') else str(skill.category),
                    "tier": skill.tier.value if hasattr(skill.tier, 'value') else str(skill.tier),
                    "parameters": params,
                    "confidence": getattr(skill, 'confidence', 0),
                    "vitality": getattr(skill, 'vitality', 0),
                })
            caller = get_auto_tool_caller()
            return jsonify(success_response({
                "available": True,
                "enabled": caller.is_enabled(),
                "tools": tools,
                "count": len(tools),
            }))
        except Exception as e:
            logger.error(f"list tools failed: {e}")
            return jsonify(error_response(str(e), 500)), 500

    @app.route("/api/tools/toggle", methods=["POST"])
    def toggle_auto_tool_call():
        if not AUTO_TOOL_CALL_AVAILABLE:
            return jsonify(error_response("auto_tool_call not available", 503)), 503
        try:
            data = request.json or {}
            enabled = bool(data.get("enabled", True))
            caller = get_auto_tool_caller()
            caller.set_enabled(enabled)
            return jsonify(success_response({
                "enabled": enabled,
                "message": f"自动工具调用已{'开启' if enabled else '关闭'}",
            }))
        except Exception as e:
            logger.error(f"toggle auto tool call failed: {e}")
            return jsonify(error_response(str(e), 500)), 500

    @app.route("/api/tools/execute", methods=["POST"])
    def manual_execute_tool():
        if not AUTO_TOOL_CALL_AVAILABLE:
            return jsonify(error_response("auto_tool_call not available", 503)), 503
        try:
            data = request.json or {}
            tool_name = data.get("name", "")
            arguments = data.get("arguments", {})
            if not tool_name:
                return jsonify(error_response("tool name is required", 400)), 400
            try:
                from function_engine import skill_registry
            except ImportError:
                from server.function_engine import skill_registry
            result = skill_registry.execute_skill(tool_name, arguments)
            return jsonify(success_response(result))
        except Exception as e:
            logger.error(f"manual execute tool failed: {e}")
            return jsonify(error_response(str(e), 500)), 500

    @app.route("/api/prompt/analyze", methods=["POST"])
    def analyze_prompt():
        """
        分析用户编写的system prompt，返回健康检查结果。
        使用jieba分词+关键词词典+Jaccard相似度，纯规则引擎，不调用大模型。
        """
        try:
            data = request.json or {}
            prompt = data.get("prompt", "").strip()
            if not prompt:
                return jsonify(error_response("prompt is required", 400)), 400

            issues = []
            stats = {}
            dimensions = {}

            # 1. 基础统计
            stats["length"] = len(prompt)
            stats["estimated_tokens"] = max(1, len(prompt) // 2)
            stats["line_count"] = len([l for l in prompt.split("\n") if l.strip()])

            # 2. 语言检测
            chinese_chars = len(re.findall(r'[\u4e00-\u9fff]', prompt))
            total_chars = len(prompt.replace(" ", "").replace("\n", ""))
            stats["chinese_ratio"] = round(chinese_chars / max(total_chars, 1), 2)
            stats["language"] = "zh" if stats["chinese_ratio"] > 0.5 else "en"

            # 3. 矛盾指令检测
            # 使用整句匹配避免误报（如"展开细节"中的"详细"不是真正的"详细"指令）
            contradiction_pairs = [
                (["简洁", "简短", "精简"], ["详细", "深入", "充分展开", "详尽"]),
                (["快速", "迅速", "马上"], ["仔细", "谨慎", "慢慢来"]),
                (["正式", "严肃", "严谨"], ["随意", "轻松", "口语化", "幽默"]),
                (["保守", "谨慎", "稳妥"], ["开放", "大胆", "激进"]),
                (["理性", "客观", "逻辑"], ["感性", "主观", "情感"]),
            ]
            # 提取指令性句子（以"- "开头的行为描述，排除格式要求段落）
            in_behavior_section = False
            directive_lines = []
            for line in prompt.split("\n"):
                line = line.strip()
                if line.startswith("核心要求") or line.startswith("行为准则"):
                    in_behavior_section = True
                    continue
                if line.startswith("格式要求"):
                    in_behavior_section = False
                    continue
                if in_behavior_section and line.startswith("-"):
                    directive_lines.append(line)

            for pos_words, neg_words in contradiction_pairs:
                pos_found = [w for w in pos_words if any(w in dl for dl in directive_lines)]
                neg_found = [w for w in neg_words if any(w in dl for dl in directive_lines)]
                if pos_found and neg_found:
                    issues.append({
                        "type": "contradiction",
                        "severity": "high",
                        "message": f"矛盾指令：'{pos_found[0]}' 与 '{neg_found[0]}' 同时出现",
                        "suggestion": f"建议删除其中一个，或改为更精确的表述",
                    })

            # 4. 冗余重复检测（简单实现：检查是否有完全相同的句子）
            sentences = re.split(r'[。！？\n]', prompt)
            sentences = [s.strip() for s in sentences if len(s.strip()) > 10]
            seen = set()
            for i, s in enumerate(sentences):
                for j in range(i + 1, len(sentences)):
                    if s == sentences[j] or (len(s) > 20 and sentences[j] in s):
                        if s not in seen:
                            seen.add(s)
                            issues.append({
                                "type": "redundancy",
                                "severity": "medium",
                                "message": f"冗余重复：'{s[:30]}...' 出现多次",
                                "suggestion": "建议删除重复内容，保留一次即可",
                            })

            # 5. 模糊表述检测
            vague_words = {
                "友好": "建议具体化为'使用轻松自然的口语化表达'",
                "准确": "建议具体化为'基于事实和数据回答'",
                "尽量": "建议删除，改为明确的指令",
                "适当": "建议具体化为'在必要时'或'根据复杂度'",
                "合理": "建议具体化为'符合逻辑'或'有依据'",
                "尽量": "建议删除模糊词，给出明确标准",
                "可能": "建议评估后给出确定性判断",
                "也许": "建议评估后给出确定性判断",
            }
            for word, suggestion in vague_words.items():
                if word in prompt:
                    issues.append({
                        "type": "vague",
                        "severity": "low",
                        "message": f"模糊表述：'{word}' 无法衡量",
                        "suggestion": suggestion,
                    })

            # 6. 英文混杂检测（中文prompt中出现未翻译英文指令）
            if stats["language"] == "zh":
                english_phrases = re.findall(r'[a-zA-Z]{4,}', prompt)
                if english_phrases:
                    issues.append({
                        "type": "language_mix",
                        "severity": "low",
                        "message": f"英文混杂：检测到 {len(english_phrases)} 个英文词组",
                        "suggestion": "建议翻译为中文，9B模型对中文指令理解更好",
                    })

            # 7. 过长警告
            if stats["estimated_tokens"] > 500:
                issues.append({
                    "type": "length",
                    "severity": "low",
                    "message": f"提示词较长（约{stats['estimated_tokens']} token）",
                    "suggestion": "建议精简到300 token以内，避免浪费上下文窗口",
                })

            # 8. 维度分析（基于关键词频率）
            dimension_keywords = {
                "concise_detailed": {
                    "positive": ["简洁", "简短", "精炼", "概括", "要点"],
                    "negative": ["详细", "深入", "充分", "展开", "全面"],
                },
                "rational_emotional": {
                    "positive": ["理性", "逻辑", "客观", "分析", "数据"],
                    "negative": ["感性", "情感", "主观", "感受", "直觉"],
                },
                "formal_casual": {
                    "positive": ["正式", "严谨", "专业", "规范"],
                    "negative": ["随意", "轻松", "口语", "幽默", "聊天"],
                },
            }
            for dim_name, keywords in dimension_keywords.items():
                pos_count = sum(prompt.count(w) for w in keywords["positive"])
                neg_count = sum(prompt.count(w) for w in keywords["negative"])
                total = pos_count + neg_count
                if total > 0:
                    score = (pos_count - neg_count) / total
                else:
                    score = 0
                dimensions[dim_name] = round(score, 2)

            # 去重：相同类型的issue只保留最严重的
            seen_types = {}
            filtered_issues = []
            for issue in issues:
                key = issue["type"]
                if key not in seen_types:
                    seen_types[key] = issue
                    filtered_issues.append(issue)
                elif issue["severity"] == "high" and seen_types[key]["severity"] != "high":
                    # 替换为更严重的
                    idx = filtered_issues.index(seen_types[key])
                    filtered_issues[idx] = issue
                    seen_types[key] = issue

            return jsonify(success_response({
                "issues": filtered_issues,
                "stats": stats,
                "dimensions": dimensions,
                "score": max(0, 100 - len(filtered_issues) * 15),
            }))
        except Exception as e:
            logger.error(f"analyze prompt failed: {e}")
            return jsonify(error_response(str(e), 500)), 500

    @app.route("/api/prompt/abtest", methods=["POST"])
    def abtest_prompt():
        """
        A/B测试：用同一条测试消息对比两个system prompt的效果。
        调用Ollama生成两条回复，返回对比结果。
        """
        try:
            data = request.json or {}
            test_message = data.get("test_message", "").strip()
            prompt_a = data.get("prompt_a", "").strip()
            prompt_b = data.get("prompt_b", "").strip()
            model = data.get("model", DEFAULT_CHAT_MODEL)

            if not test_message:
                return jsonify(error_response("test_message is required", 400)), 400
            if not prompt_a or not prompt_b:
                return jsonify(error_response("prompt_a and prompt_b are required", 400)), 400

            def generate_reply(system_prompt, user_message, model_name):
                """调用Ollama生成单条回复"""
                payload = {
                    "model": model_name,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_message},
                    ],
                    "stream": False,
                    "options": {
                        "temperature": 0.7,
                        "num_predict": 512,
                    },
                }
                try:
                    resp = requests.post(
                        f"{OLLAMA_BASE_URL}/api/chat",
                        json=payload,
                        timeout=60,
                    )
                    resp.raise_for_status()
                    result = resp.json()
                    content = result.get("message", {}).get("content", "")
                    eval_count = result.get("eval_count", 0)
                    prompt_eval_count = result.get("prompt_eval_count", 0)
                    total_duration = result.get("total_duration", 0) / 1e9  # 纳秒转秒
                    return {
                        "content": content,
                        "tokens": eval_count,
                        "prompt_tokens": prompt_eval_count,
                        "time_ms": round(total_duration * 1000, 1),
                        "success": True,
                    }
                except Exception as e:
                    return {
                        "content": f"生成失败: {str(e)}",
                        "tokens": 0,
                        "prompt_tokens": 0,
                        "time_ms": 0,
                        "success": False,
                    }

            # 顺序生成两条回复（避免并发对Ollama的压力）
            result_a = generate_reply(prompt_a, test_message, model)
            result_b = generate_reply(prompt_b, test_message, model)

            # 生成对比摘要
            comparison = {}
            if result_a["success"] and result_b["success"]:
                len_diff = len(result_b["content"]) - len(result_a["content"])
                token_diff = result_b["tokens"] - result_a["tokens"]
                time_diff = result_b["time_ms"] - result_a["time_ms"]

                comparison = {
                    "length_diff": f"{'+' if len_diff > 0 else ''}{len_diff} 字符",
                    "token_diff": f"{'+' if token_diff > 0 else ''}{token_diff} token",
                    "speed_diff": f"{'+' if time_diff > 0 else ''}{round(time_diff, 1)} ms",
                    "style_note": (
                        "版本B回复更长更详细" if len_diff > 50 else
                        "版本A回复更长更详细" if len_diff < -50 else
                        "两者长度相近"
                    ),
                }

            return jsonify(success_response({
                "result_a": result_a,
                "result_b": result_b,
                "comparison": comparison,
            }))
        except Exception as e:
            logger.error(f"abtest prompt failed: {e}")
            return jsonify(error_response(str(e), 500)), 500

    _feedback_store_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "feedback_store.json")

    def _load_feedback_store():
        if os.path.exists(_feedback_store_path):
            try:
                with open(_feedback_store_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                return {"records": [], "stats": {"positive": 0, "negative": 0}}
        return {"records": [], "stats": {"positive": 0, "negative": 0}}

    def _save_feedback_store(store):
        os.makedirs(os.path.dirname(_feedback_store_path), exist_ok=True)
        with open(_feedback_store_path, "w", encoding="utf-8") as f:
            json.dump(store, f, ensure_ascii=False, indent=2)

    @app.route("/api/prompt/feedback", methods=["POST"])
    @require_api_key
    def submit_feedback():
        try:
            data = request.json or {}
            feedback_type = data.get("type")
            if feedback_type not in ("positive", "negative"):
                return jsonify(error_response("type 必须为 positive 或 negative", 400)), 400

            store = _load_feedback_store()
            record = {
                "id": str(uuid.uuid4()),
                "type": feedback_type,
                "message_id": data.get("message_id", ""),
                "message_preview": data.get("message_preview", "")[:200],
                "model": data.get("model", ""),
                "conversation_id": data.get("conversation_id", ""),
                "contract_snapshot": data.get("contract_snapshot", {}),
                "timestamp": data.get("timestamp") or time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            }
            store["records"].append(record)
            store["stats"][feedback_type] = store["stats"].get(feedback_type, 0) + 1
            if len(store["records"]) > 500:
                store["records"] = store["records"][-500:]
            _save_feedback_store(store)

            return jsonify(success_response({
                "recorded": True,
                "total_positive": store["stats"]["positive"],
                "total_negative": store["stats"]["negative"],
            }))
        except Exception as e:
            logger.error(f"submit feedback failed: {e}")
            return jsonify(error_response(str(e), 500)), 500

    @app.route("/api/prompt/suggestions", methods=["GET"])
    @require_api_key
    def get_suggestions():
        try:
            store = _load_feedback_store()
            records = store["records"]
            stats = store["stats"]
            total = stats.get("positive", 0) + stats.get("negative", 0)

            suggestions = []

            if total >= 5:
                neg_ratio = stats.get("negative", 0) / total
                if neg_ratio > 0.6:
                    suggestions.append({
                        "id": "high_negative",
                        "priority": "high",
                        "title": "差评率偏高",
                        "description": f"最近 {total} 条反馈中差评占比 {round(neg_ratio * 100)}%，建议调整行为契约",
                        "action": "adjust_contract",
                        "hints": ["降低回答长度", "增加先给结论规则", "减少冗余表达"],
                    })
                elif neg_ratio < 0.15 and stats.get("positive", 0) > 3:
                    suggestions.append({
                        "id": "high_positive",
                        "priority": "low",
                        "title": "好评率优秀",
                        "description": f"最近好评率达 {round((1 - neg_ratio) * 100)}%，当前契约配置效果良好",
                        "action": "maintain",
                        "hints": [],
                    })

            recent_records = records[-20:] if len(records) >= 20 else records
            if recent_records:
                recent_neg = sum(1 for r in recent_records if r["type"] == "negative")
                recent_pos = sum(1 for r in recent_records if r["type"] == "positive")
                if recent_neg > recent_pos and recent_neg >= 3:
                    suggestions.append({
                        "id": "trend_declining",
                        "priority": "medium",
                        "title": "近期反馈趋势下降",
                        "description": f"最近 20 条中差评 {recent_neg} 条 vs 好评 {recent_pos} 条",
                        "action": "review_recent",
                        "hints": ["检查最近对话主题是否偏移", "考虑增加特定领域规则"],
                    })

            model_stats = {}
            for r in records[-50:]:
                m = r.get("model", "unknown")
                if m not in model_stats:
                    model_stats[m] = {"positive": 0, "negative": 0}
                model_stats[m][r["type"]] = model_stats[m].get(r["type"], 0) + 1
            for m, ms in model_stats.items():
                m_total = ms["positive"] + ms["negative"]
                if m_total >= 3 and ms["negative"] / m_total > 0.7:
                    suggestions.append({
                        "id": f"model_{m}",
                        "priority": "medium",
                        "title": f"模型 {m} 反馈较差",
                        "description": f"该模型差评率 {round(ms['negative'] / m_total * 100)}%",
                        "action": "switch_model",
                        "hints": [f"考虑为 {m} 配置专属行为契约"],
                    })

            return jsonify(success_response({
                "suggestions": suggestions,
                "stats": stats,
                "total_feedback": total,
            }))
        except Exception as e:
            logger.error(f"get suggestions failed: {e}")
            return jsonify(error_response(str(e), 500)), 500

    @app.route("/api/chat/timing", methods=["GET"])
    @require_api_key
    def get_timing_stats():
        try:
            if not TIMING_AVAILABLE:
                return jsonify(error_response("TimingCollector not available", 503)), 503
            collector = TimingCollector.get_instance()
            action = request.args.get("action", "stats")
            if action == "recent":
                limit = min(int(request.args.get("limit", 20)), 100)
                return jsonify(success_response({"recent": collector.get_recent(limit)}))
            elif action == "clear":
                collector.clear()
                return jsonify(success_response({"cleared": True}))
            else:
                return jsonify(success_response(collector.get_stats()))
        except Exception as e:
            logger.error(f"get timing stats failed: {e}")
            return jsonify(error_response(str(e), 500)), 500

    logger.info("Chat API routes registered")
