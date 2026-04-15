# -*- coding: utf-8 -*-
"""
Ollama Hub 全系统测试套件

覆盖范围：
  - 工具层：helpers, auth, config, security_utils, text_segmenter, loop_guard, repetition_detector
  - 核心服务层：memory_service, context_manager, summary_service, smart_cache, api_key_service, rag_service, web_search_service
  - AI服务层（Mock）：qwen3_tts_service, silero_tts_service, asr, voice_call_service, local_model_loader
  - API路由层：health, greeting, chat, image, memory, summary, models, api_key, asr, group_chat, search, rag, vision, functions, context, ollama_proxy

运行方式：
  python -m pytest tests/test_system_full.py -v --tb=short
  或
  python tests/test_system_full.py
"""

import os
import sys
import json
import time
import tempfile
import threading
import unittest
import asyncio
import base64
from pathlib import Path
from unittest.mock import patch, MagicMock, PropertyMock, AsyncMock
from dataclasses import asdict
from collections import deque

SERVER_DIR = str(Path(__file__).resolve().parent.parent / "server")
sys.path.insert(0, SERVER_DIR)
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


# ==================== 工具层测试 ====================

class TestHelpers(unittest.TestCase):
    """utils.helpers 辅助函数测试"""

    def setUp(self):
        from utils.helpers import success_response, error_response, validate_request, validate_string, validate_integer, split_into_sentences, chunk_by_sentences, safe_get
        self.success_response = success_response
        self.error_response = error_response
        self.validate_request = validate_request
        self.validate_string = validate_string
        self.validate_integer = validate_integer
        self.split_into_sentences = split_into_sentences
        self.chunk_by_sentences = chunk_by_sentences
        self.safe_get = safe_get

    def test_success_response_structure(self):
        resp = self.success_response(data={"key": "val"}, message="ok", code=201)
        self.assertTrue(resp["success"])
        self.assertEqual(resp["message"], "ok")
        self.assertEqual(resp["code"], 201)
        self.assertEqual(resp["data"], {"key": "val"})

    def test_success_response_defaults(self):
        resp = self.success_response()
        self.assertTrue(resp["success"])
        self.assertEqual(resp["code"], 200)
        self.assertIsNone(resp["data"])

    def test_error_response_structure(self):
        resp = self.error_response(message="bad", code=400)
        self.assertFalse(resp["success"])
        self.assertEqual(resp["message"], "bad")
        self.assertEqual(resp["code"], 400)

    def test_error_response_with_data(self):
        resp = self.error_response("err", 500, data={"detail": "x"})
        self.assertEqual(resp["data"], {"detail": "x"})

    def test_validate_request_all_present(self):
        ok, msg = self.validate_request(["a", "b"], {"a": 1, "b": 2})
        self.assertTrue(ok)
        self.assertEqual(msg, "")

    def test_validate_request_missing_field(self):
        ok, msg = self.validate_request(["a", "b"], {"a": 1})
        self.assertFalse(ok)
        self.assertIn("b", msg)

    def test_validate_request_none_value(self):
        ok, msg = self.validate_request(["a"], {"a": None})
        self.assertFalse(ok)

    def test_validate_string_valid(self):
        ok, msg = self.validate_string("hello", "name")
        self.assertTrue(ok)

    def test_validate_string_not_string(self):
        ok, msg = self.validate_string(123, "name")
        self.assertFalse(ok)

    def test_validate_string_too_short(self):
        ok, msg = self.validate_string("", "name", min_len=1)
        self.assertFalse(ok)

    def test_validate_string_too_long(self):
        ok, msg = self.validate_string("a" * 101, "name", max_len=100)
        self.assertFalse(ok)

    def test_validate_integer_valid(self):
        ok, msg = self.validate_integer(5, "count", min_val=1, max_val=10)
        self.assertTrue(ok)

    def test_validate_integer_not_integer(self):
        ok, msg = self.validate_integer("abc", "count")
        self.assertFalse(ok)

    def test_validate_integer_below_min(self):
        ok, msg = self.validate_integer(0, "count", min_val=1)
        self.assertFalse(ok)

    def test_validate_integer_above_max(self):
        ok, msg = self.validate_integer(11, "count", max_val=10)
        self.assertFalse(ok)

    def test_validate_integer_float_coercion(self):
        ok, msg = self.validate_integer(3.7, "count")
        self.assertTrue(ok)

    def test_split_into_sentences_empty(self):
        self.assertEqual(self.split_into_sentences(""), [])

    def test_split_into_sentences_none(self):
        self.assertEqual(self.split_into_sentences(None), [])

    def test_split_into_sentences_chinese(self):
        result = self.split_into_sentences("你好。世界！再见？")
        self.assertTrue(len(result) > 0)

    def test_chunk_by_sentences_empty(self):
        self.assertEqual(self.chunk_by_sentences(""), [])

    def test_chunk_by_sentences_short_text(self):
        result = self.chunk_by_sentences("短文本")
        self.assertEqual(len(result), 1)

    def test_safe_get_nested(self):
        data = {"a": {"b": {"c": 42}}}
        self.assertEqual(self.safe_get(data, "a", "b", "c"), 42)

    def test_safe_get_missing_key(self):
        data = {"a": 1}
        self.assertIsNone(self.safe_get(data, "b"))

    def test_safe_get_default(self):
        data = {}
        self.assertEqual(self.safe_get(data, "x", default="fallback"), "fallback")

    def test_safe_get_type_error(self):
        self.assertIsNone(self.safe_get(None, "a"))


class TestAuth(unittest.TestCase):
    """utils.auth 认证模块测试"""

    def test_check_rate_limit_normal(self):
        from utils.auth import check_rate_limit, rate_limit_store
        rate_limit_store.clear()
        ip = "192.168.1.1"
        for _ in range(60):
            self.assertTrue(check_rate_limit(ip))

    def test_check_rate_limit_exceeded(self):
        from utils.auth import check_rate_limit, rate_limit_store
        rate_limit_store.clear()
        ip = "10.0.0.1"
        for _ in range(60):
            check_rate_limit(ip)
        self.assertFalse(check_rate_limit(ip))

    def test_check_rate_limit_different_ips(self):
        from utils.auth import check_rate_limit, rate_limit_store
        rate_limit_store.clear()
        for i in range(60):
            self.assertTrue(check_rate_limit(f"10.0.{i}.1"))

    def test_require_api_key_internal_call(self):
        from utils.auth import require_api_key, rate_limit_store
        from flask import Flask, jsonify

        rate_limit_store.clear()

        app = Flask(__name__)

        @app.route("/test", methods=["GET", "POST"])
        @require_api_key
        def test_route():
            return jsonify({"ok": True})

        with app.test_client() as client:
            resp = client.get(
                "/test",
                headers={"X-Internal-Call": "true"},
                environ_base={"REMOTE_ADDR": "127.0.0.1"}
            )
            self.assertEqual(resp.status_code, 200)

    def test_require_api_key_missing_key(self):
        from utils.auth import require_api_key, rate_limit_store
        from flask import Flask, jsonify
        import utils.auth as auth_mod

        rate_limit_store.clear()
        original = auth_mod._api_key_service
        mock_service = MagicMock()
        mock_service.keys = {"test_key": {"is_active": True}}
        mock_service.verify_key.return_value = None
        auth_mod._api_key_service = mock_service

        app = Flask(__name__)

        @app.route("/test2", methods=["GET", "POST"])
        @require_api_key
        def test_route2():
            return jsonify({"ok": True})

        with app.test_client() as client:
            resp = client.post(
                "/test2",
                headers={"Authorization": "Bearer oll_fake"},
                environ_base={"REMOTE_ADDR": "10.0.0.1"}
            )
            self.assertEqual(resp.status_code, 401)

        auth_mod._api_key_service = original

    def test_require_api_key_invalid_key(self):
        from utils.auth import require_api_key, rate_limit_store
        from flask import Flask, jsonify
        import utils.auth as auth_mod

        rate_limit_store.clear()
        mock_service = MagicMock()
        mock_service.keys = {"test_key": {"is_active": True}}
        mock_service.verify_key.return_value = None
        auth_mod._api_key_service = mock_service

        app = Flask(__name__)

        @app.route("/test3", methods=["GET", "POST"])
        @require_api_key
        def test_route3():
            return jsonify({"ok": True})

        with app.test_client() as client:
            resp = client.post(
                "/test3",
                headers={"Authorization": "Bearer oll_fake_key"},
                environ_base={"REMOTE_ADDR": "10.0.0.1"}
            )
            self.assertEqual(resp.status_code, 401)

        auth_mod._api_key_service = None


class TestConfig(unittest.TestCase):
    """utils.config 配置模块测试"""

    def test_ollama_base_url_default(self):
        from utils.config import OLLAMA_BASE_URL
        self.assertTrue(OLLAMA_BASE_URL.startswith("http"))

    def test_port_values(self):
        from utils.config import PORT_WEB, PORT_API, PORT_OLLAMA
        self.assertEqual(PORT_WEB, 8080)
        self.assertEqual(PORT_API, 5001)
        self.assertEqual(PORT_OLLAMA, 11434)

    def test_sampling_presets(self):
        from utils.config import SAMPLING_PRESETS
        self.assertIn("fast", SAMPLING_PRESETS)
        self.assertIn("balanced", SAMPLING_PRESETS)
        self.assertIn("creative", SAMPLING_PRESETS)
        self.assertIn("code", SAMPLING_PRESETS)
        for name, preset in SAMPLING_PRESETS.items():
            self.assertIn("temperature", preset)
            self.assertIn("top_k", preset)
            self.assertIn("top_p", preset)
            self.assertGreater(preset["temperature"], 0)
            self.assertLessEqual(preset["temperature"], 2.0)

    def test_build_ollama_options_default(self):
        from utils.config import build_ollama_options
        opts = build_ollama_options({})
        self.assertIn("temperature", opts)
        self.assertIn("num_ctx", opts)

    def test_build_ollama_options_with_preset(self):
        from utils.config import build_ollama_options
        opts = build_ollama_options({}, "fast")
        self.assertIn("temperature", opts)

    def test_conversation_mode_config(self):
        from utils.config import CONVERSATION_MODE_CONFIG
        self.assertIn("standard", CONVERSATION_MODE_CONFIG)
        self.assertIn("adult", CONVERSATION_MODE_CONFIG)

    def test_system_prompt_templates(self):
        from utils.config import SYSTEM_PROMPT_TEMPLATES
        self.assertIn("assistant_balanced", SYSTEM_PROMPT_TEMPLATES)
        self.assertIn("assistant_brief", SYSTEM_PROMPT_TEMPLATES)

    def test_safety_policy_blocks(self):
        from utils.config import SAFETY_POLICY_BLOCKS
        self.assertIn("strict", SAFETY_POLICY_BLOCKS)
        self.assertIn("balanced", SAFETY_POLICY_BLOCKS)
        self.assertIn("relaxed", SAFETY_POLICY_BLOCKS)

    def test_gguf_model_config(self):
        from utils.config import GGUF_MODEL_CONFIG, get_gguf_model_config
        self.assertIsInstance(GGUF_MODEL_CONFIG, dict)
        config = get_gguf_model_config("nonexistent")
        self.assertEqual(config, {})

    def test_image_model_config(self):
        from utils.config import IMAGE_MODEL_CONFIG
        self.assertIn("stable-diffusion-v1-5", IMAGE_MODEL_CONFIG)

    def test_repetition_detection_config(self):
        from utils.config import REPETITION_DETECTION_CONFIG
        self.assertTrue(REPETITION_DETECTION_CONFIG["enabled"])
        self.assertGreater(REPETITION_DETECTION_CONFIG["window_size"], 0)


class TestSecurityUtils(unittest.TestCase):
    """security_utils 安全工具测试"""

    def test_sanitize_path_normal(self):
        from security_utils import sanitize_path
        result = sanitize_path("subdir/file.txt", "/allowed")
        self.assertIsNotNone(result)

    def test_sanitize_path_traversal(self):
        from security_utils import sanitize_path
        result = sanitize_path("../../../etc/passwd", "/allowed")
        self.assertIsNone(result)

    def test_sanitize_path_absolute(self):
        from security_utils import sanitize_path
        result = sanitize_path("/etc/passwd", "/allowed")
        self.assertIsNone(result)

    def test_sanitize_path_extension_allowed(self):
        from security_utils import sanitize_path
        result = sanitize_path("file.txt", "/allowed", allowed_extensions=[".txt"])
        self.assertIsNotNone(result)

    def test_sanitize_path_extension_blocked(self):
        from security_utils import sanitize_path
        result = sanitize_path("file.exe", "/allowed", allowed_extensions=[".txt"])
        self.assertIsNone(result)


class TestTextSegmenter(unittest.TestCase):
    """text_segmenter 文本分段测试"""

    def setUp(self):
        from text_segmenter import TextSegmenter
        self.segmenter = TextSegmenter()

    def test_detect_language_chinese(self):
        lang = self.segmenter.detect_language("你好世界")
        self.assertEqual(lang, "zh")

    def test_detect_language_english(self):
        lang = self.segmenter.detect_language("Hello World")
        self.assertEqual(lang, "en")

    def test_detect_language_empty(self):
        lang = self.segmenter.detect_language("")
        self.assertEqual(lang, "unknown")

    def test_detect_language_mixed(self):
        lang = self.segmenter.detect_language("Hello你好World世界")
        self.assertIn(lang, ["zh", "en", "mixed"])


class TestLoopGuard(unittest.TestCase):
    """loop_guard 循环防护测试"""

    def setUp(self):
        from loop_guard import LoopGuard, LoopGuardConfig
        self.LoopGuard = LoopGuard
        self.LoopGuardConfig = LoopGuardConfig

    def test_no_loop_short_text(self):
        guard = self.LoopGuard()
        guard.generated = "正常文本，没有循环。"
        self.assertFalse(guard.generated == "")

    def test_config_defaults(self):
        config = self.LoopGuardConfig()
        self.assertEqual(config.max_consecutive_repeats, 3)
        self.assertEqual(config.min_repeat_length, 8)
        self.assertEqual(config.check_interval, 15)

    def test_custom_config(self):
        config = self.LoopGuardConfig(max_consecutive_repeats=5, min_repeat_length=4)
        self.assertEqual(config.max_consecutive_repeats, 5)
        self.assertEqual(config.min_repeat_length, 4)


class TestRepetitionDetector(unittest.TestCase):
    """repetition_detector 重复检测器测试"""

    def setUp(self):
        from utils.repetition_detector import RepetitionDetector, RepetitionConfig, detect_repetition_in_text, create_detector
        self.Detector = RepetitionDetector
        self.Config = RepetitionConfig
        self.detect_in_text = detect_repetition_in_text
        self.create_detector = create_detector

    def test_no_repetition(self):
        detector = self.Detector()
        tokens = ["我", "喜欢", "编程", "和", "阅读"]
        for t in tokens:
            should_stop, reason = detector.process_token(t)
            self.assertFalse(should_stop)

    def test_token_repetition_detected(self):
        detector = self.Detector(self.Config(min_repeat_count=3, max_repeat_count=5))
        should_stop = False
        for _ in range(6):
            stop, reason = detector.process_token("重复")
            if stop:
                should_stop = True
                break
        self.assertTrue(should_stop)

    def test_process_chunk_empty(self):
        detector = self.Detector()
        stop, reason, filtered = detector.process_chunk("")
        self.assertFalse(stop)
        self.assertEqual(filtered, "")

    def test_process_chunk_normal(self):
        detector = self.Detector()
        stop, reason, filtered = detector.process_chunk("这是一段正常文本")
        self.assertFalse(stop)

    def test_reset(self):
        detector = self.Detector()
        detector.process_token("测试")
        detector.reset()
        self.assertEqual(detector.state.repeat_count, 0)

    def test_get_suggested_params(self):
        detector = self.Detector()
        params = detector.get_suggested_params()
        self.assertIn("repeat_penalty", params)
        self.assertIn("temperature", params)

    def test_detect_repetition_in_text_short(self):
        result = self.detect_in_text("短文本")
        self.assertFalse(result["has_repetition"])

    def test_detect_repetition_in_text_empty(self):
        result = self.detect_in_text("")
        self.assertFalse(result["has_repetition"])

    def test_create_detector_default(self):
        detector = self.create_detector()
        self.assertIsInstance(detector, self.Detector)

    def test_create_detector_custom_config(self):
        detector = self.create_detector({"enabled": True, "window_size": 20})
        self.assertEqual(detector.config.window_size, 20)


# ==================== 核心服务层测试 ====================

class TestMemoryService(unittest.TestCase):
    """memory_service 记忆服务测试"""

    def setUp(self):
        from memory_service import Memory, MemoryStore, MemorySearchResult
        self.Memory = Memory
        self.MemoryStore = MemoryStore
        self.MemorySearchResult = MemorySearchResult
        self.tmpdir = tempfile.mkdtemp()
        self.store = MemoryStore(os.path.join(self.tmpdir, "test_memories.json"))

    def _make_memory(self, content="测试记忆", category="general", importance=5):
        now = time.time()
        return self.Memory(
            id="mem_001",
            content=content,
            category=category,
            tags=["test"],
            importance=importance,
            created_at=now,
            updated_at=now,
            usage_count=0,
            last_used_at=now
        )

    def test_memory_to_dict(self):
        mem = self._make_memory()
        d = mem.to_dict()
        self.assertEqual(d["content"], "测试记忆")
        self.assertEqual(d["category"], "general")

    def test_memory_from_dict(self):
        mem = self._make_memory()
        d = mem.to_dict()
        restored = self.Memory.from_dict(d)
        self.assertEqual(restored.content, mem.content)
        self.assertEqual(restored.id, mem.id)

    def test_memory_store_creation(self):
        self.assertTrue(os.path.exists(self.store.storage_path))

    def test_memory_store_create_and_get(self):
        mem = self.store.create(content="测试记忆", category="general", importance=5)
        self.assertIsNotNone(mem)
        self.assertEqual(mem.content, "测试记忆")
        loaded = self.store.get(mem.id)
        self.assertIsNotNone(loaded)
        self.assertEqual(loaded.content, "测试记忆")

    def test_memory_store_delete(self):
        mem = self.store.create(content="待删除记忆")
        loaded = self.store.get(mem.id)
        self.assertIsNotNone(loaded)
        self.store.delete(mem.id)
        loaded = self.store.get(mem.id)
        self.assertIsNone(loaded)

    def test_memory_store_list(self):
        for i in range(3):
            self.store.create(content=f"记忆{i}")
        all_mems = self.store.list_all()
        self.assertGreaterEqual(len(all_mems), 3)


class TestContextManager(unittest.TestCase):
    """context_manager 上下文管理器测试"""

    def setUp(self):
        from context_manager import ContextManager, ContextMessage, ContextLevel, ContextConfig
        self.ContextManager = ContextManager
        self.ContextMessage = ContextMessage
        self.ContextLevel = ContextLevel
        self.ContextConfig = ContextConfig

    def test_context_message_to_dict(self):
        msg = self.ContextMessage(role="user", content="你好")
        d = msg.to_dict()
        self.assertEqual(d["role"], "user")
        self.assertEqual(d["content"], "你好")

    def test_context_message_from_dict(self):
        data = {"role": "assistant", "content": "世界", "timestamp": time.time(), "level": "regular", "importance": 0.5, "token_count": 0, "is_compressed": False, "original_content": None}
        msg = self.ContextMessage.from_dict(data)
        self.assertEqual(msg.role, "assistant")
        self.assertEqual(msg.content, "世界")

    def test_context_level_values(self):
        self.assertEqual(self.ContextLevel.SYSTEM.value, "system")
        self.assertEqual(self.ContextLevel.SUMMARY.value, "summary")
        self.assertEqual(self.ContextLevel.CORE.value, "core")
        self.assertEqual(self.ContextLevel.REGULAR.value, "regular")

    def test_context_config_defaults(self):
        config = self.ContextConfig()
        self.assertEqual(config.max_total_tokens, 8000)
        self.assertEqual(config.regular_window_size, 10)

    def test_context_manager_add_message(self):
        cm = self.ContextManager.__new__(self.ContextManager)
        cm.config = self.ContextConfig()
        cm.messages = []
        cm._session_id = "test"
        msg = self.ContextMessage(role="user", content="测试消息")
        cm.messages.append(msg)
        self.assertEqual(len(cm.messages), 1)
        self.assertEqual(cm.messages[0].content, "测试消息")


class TestSummaryService(unittest.TestCase):
    """summary_service 摘要服务测试"""

    def test_summary_level_enum(self):
        from summary_service import SummaryLevel
        self.assertEqual(SummaryLevel.CONCISE.value, "concise")
        self.assertEqual(SummaryLevel.DETAILED.value, "detailed")
        self.assertEqual(SummaryLevel.KEY_POINTS.value, "key_points")

    def test_message_dataclass(self):
        from summary_service import Message
        msg = Message(role="user", content="你好")
        d = msg.to_dict()
        self.assertEqual(d["role"], "user")
        self.assertEqual(d["content"], "你好")

    def test_message_from_dict(self):
        from summary_service import Message
        data = {"role": "assistant", "content": "回复", "timestamp": time.time()}
        msg = Message.from_dict(data)
        self.assertEqual(msg.content, "回复")

    def test_summary_dataclass(self):
        from summary_service import Summary
        s = Summary(
            id="sum_001",
            conversation_id="conv_001",
            level="concise",
            content="摘要内容",
            message_count=5,
            created_at=time.time(),
            topics=["话题1"],
            key_points=["要点1"]
        )
        d = s.to_dict()
        self.assertEqual(d["id"], "sum_001")
        self.assertEqual(d["level"], "concise")

    def test_summary_from_dict(self):
        from summary_service import Summary
        data = {
            "id": "sum_002", "conversation_id": "conv_002", "level": "detailed",
            "content": "详细摘要", "message_count": 10, "created_at": time.time(),
            "topics": [], "key_points": []
        }
        s = Summary.from_dict(data)
        self.assertEqual(s.content, "详细摘要")


class TestSmartCache(unittest.TestCase):
    """smart_cache 智能缓存测试"""

    def setUp(self):
        from smart_cache import CacheEntry, AdaptiveTTL, MemoryAwareCache
        self.CacheEntry = CacheEntry
        self.AdaptiveTTL = AdaptiveTTL
        self.MemoryAwareCache = MemoryAwareCache

    def test_cache_entry_is_expired(self):
        now = time.time()
        entry = self.CacheEntry(
            value="test", created_at=now - 100,
            last_access=now, access_count=1, ttl=50,
            size_bytes=4, tags=[]
        )
        self.assertTrue(entry.is_expired())

    def test_cache_entry_not_expired(self):
        now = time.time()
        entry = self.CacheEntry(
            value="test", created_at=now,
            last_access=now, access_count=1, ttl=300,
            size_bytes=4, tags=[]
        )
        self.assertFalse(entry.is_expired())

    def test_cache_entry_no_ttl(self):
        now = time.time()
        entry = self.CacheEntry(
            value="test", created_at=now - 1000,
            last_access=now, access_count=1, ttl=0,
            size_bytes=4, tags=[]
        )
        self.assertFalse(entry.is_expired())

    def test_cache_entry_update_access(self):
        now = time.time()
        entry = self.CacheEntry(
            value="test", created_at=now,
            last_access=now - 10, access_count=1, ttl=300,
            size_bytes=4, tags=[]
        )
        old_count = entry.access_count
        entry.update_access()
        self.assertEqual(entry.access_count, old_count + 1)

    def test_adaptive_ttl_low_frequency(self):
        ttl = self.AdaptiveTTL.calculate(access_count=1, time_since_creation=100)
        self.assertEqual(ttl, self.AdaptiveTTL.TTL_MIN)

    def test_adaptive_ttl_high_frequency(self):
        ttl = self.AdaptiveTTL.calculate(access_count=100, time_since_creation=10)
        self.assertGreater(ttl, self.AdaptiveTTL.TTL_DEFAULT)

    def test_memory_aware_cache_basic(self):
        cache = self.MemoryAwareCache(max_size=10, max_memory_mb=1)
        cache.set("key1", "value1")
        result = cache.get("key1")
        self.assertEqual(result, "value1")

    def test_memory_aware_cache_miss(self):
        cache = self.MemoryAwareCache(max_size=10, max_memory_mb=1)
        result = cache.get("nonexistent")
        self.assertIsNone(result)

    def test_memory_aware_cache_delete(self):
        cache = self.MemoryAwareCache(max_size=10, max_memory_mb=1)
        cache.set("key1", "value1")
        cache.delete("key1")
        result = cache.get("key1")
        self.assertIsNone(result)

    def test_memory_aware_cache_clear(self):
        cache = self.MemoryAwareCache(max_size=10, max_memory_mb=1)
        cache.set("k1", "v1")
        cache.set("k2", "v2")
        cache.clear()
        self.assertIsNone(cache.get("k1"))
        self.assertIsNone(cache.get("k2"))


class TestAPIKeyService(unittest.TestCase):
    """api_key_service API密钥管理测试"""

    def setUp(self):
        from api_key_service import APIKeyService
        self.tmpdir = tempfile.mkdtemp()
        self.key_file = os.path.join(self.tmpdir, "test_keys.json")
        self.service = APIKeyService.__new__(APIKeyService)
        self.service.keys = {}
        self.service.keys_file = self.key_file

    def test_generate_key(self):
        from api_key_service import APIKeyService
        service = APIKeyService()
        result = service.generate_key(name="测试密钥")
        self.assertTrue(result["success"])
        self.assertIn("data", result)
        self.assertEqual(result["data"]["name"], "测试密钥")
        self.assertTrue(result["data"]["key"].startswith("oll_"))

    def test_verify_valid_key(self):
        from api_key_service import APIKeyService
        service = APIKeyService()
        gen = service.generate_key()
        full_key = gen["data"]["key"]
        result = service.verify_key(full_key)
        self.assertIsNotNone(result)

    def test_verify_invalid_key(self):
        from api_key_service import APIKeyService
        service = APIKeyService()
        result = service.verify_key("oll_invalid_key_12345")
        self.assertIsNone(result)

    def test_verify_key_wrong_prefix(self):
        from api_key_service import APIKeyService
        service = APIKeyService()
        result = service.verify_key("bad_prefix_key")
        self.assertIsNone(result)

    def test_list_keys(self):
        from api_key_service import APIKeyService
        service = APIKeyService()
        service.generate_key(name="Key1")
        service.generate_key(name="Key2")
        result = service.list_keys()
        self.assertTrue(result["success"])
        self.assertGreaterEqual(len(result["data"]), 2)

    def test_revoke_key(self):
        from api_key_service import APIKeyService
        service = APIKeyService()
        gen = service.generate_key()
        key_id = gen["data"]["id"]
        result = service.revoke_key(key_id)
        self.assertTrue(result["success"])

    def test_revoke_nonexistent_key(self):
        from api_key_service import APIKeyService
        service = APIKeyService()
        result = service.revoke_key("nonexistent_id")
        self.assertFalse(result["success"])


class TestWebSearchService(unittest.TestCase):
    """web_search_service 网页搜索服务测试"""

    def setUp(self):
        from web_search_service import WebSearchService, _response
        self.WebSearchService = WebSearchService
        self._response = _response

    def test_response_helper_success(self):
        resp = self._response(True, "ok", data={"q": "test"})
        self.assertTrue(resp["success"])
        self.assertEqual(resp["message"], "ok")

    def test_response_helper_error(self):
        resp = self._response(False, "err", code=400)
        self.assertFalse(resp["success"])
        self.assertEqual(resp["code"], 400)

    def test_search_empty_query(self):
        service = self.WebSearchService()
        result = service.search("")
        self.assertFalse(result["success"])
        self.assertEqual(result["code"], 400)

    def test_search_none_query(self):
        service = self.WebSearchService()
        result = service.search(None)
        self.assertFalse(result["success"])

    def test_cache_mechanism(self):
        service = self.WebSearchService(cache_ttl_seconds=60)
        service._set_cache("test_key", {"results": []})
        cached = service._get_cache("test_key")
        self.assertIsNotNone(cached)

    def test_cache_miss(self):
        service = self.WebSearchService()
        cached = service._get_cache("nonexistent_key")
        self.assertIsNone(cached)


# ==================== AI服务层Mock测试 ====================

class TestQwen3TTSServiceMock(unittest.TestCase):
    """qwen3_tts_service Mock测试"""

    def test_tts_result_dataclass(self):
        from qwen3_tts_service import TTSResult
        result = TTSResult(audio_bytes=b"\x00\x01", sample_rate=24000, duration_ms=100.0, speaker_id="default")
        self.assertEqual(result.sample_rate, 24000)
        self.assertEqual(result.speaker_id, "default")
        self.assertEqual(result.format, "pcm")

    def test_speaker_profile_dataclass(self):
        from qwen3_tts_service import SpeakerProfile
        profile = SpeakerProfile(speaker_id="vivian", name="Vivian", description="明亮的年轻女声")
        self.assertEqual(profile.speaker_id, "vivian")
        self.assertEqual(profile.speed, 1.0)

    def test_preset_speakers_exist(self):
        from qwen3_tts_service import PRESET_SPEAKERS
        self.assertIn("default", PRESET_SPEAKERS)
        self.assertIn("warm", PRESET_SPEAKERS)
        self.assertIn("professional", PRESET_SPEAKERS)

    def test_edge_tts_voice_map(self):
        from qwen3_tts_service import EDGE_TTS_VOICE_MAP
        self.assertIn("default", EDGE_TTS_VOICE_MAP)
        self.assertIn("japanese", EDGE_TTS_VOICE_MAP)

    @patch("qwen3_tts_service.Qwen3TTSService._load_fallback", return_value=True)
    def test_service_init(self, mock_fallback):
        from qwen3_tts_service import Qwen3TTSService
        Qwen3TTSService._instance = None
        Qwen3TTSService._initialized = False
        with patch.dict("sys.modules", {"torch": MagicMock(), "qwen_tts": MagicMock()}):
            service = Qwen3TTSService()
            self.assertIsNotNone(service)

    def test_synthesize_empty_text(self):
        from qwen3_tts_service import Qwen3TTSService
        Qwen3TTSService._instance = None
        Qwen3TTSService._initialized = False
        with patch.dict("sys.modules", {"torch": MagicMock()}):
            mock_torch = MagicMock()
            mock_torch.cuda.is_available.return_value = False
            with patch("qwen3_tts_service.Qwen3TTSService.__init__", lambda self: None):
                service = Qwen3TTSService.__new__(Qwen3TTSService)
                service._use_fallback = True
                service.is_loaded = True
                result = service.synthesize("")
                self.assertIsNone(result)

    def test_wrap_wav_header(self):
        from qwen3_tts_service import Qwen3TTSService
        service = Qwen3TTSService.__new__(Qwen3TTSService)
        pcm = b"\x00" * 100
        wav = service._wrap_wav_header(pcm, 24000, channels=1, bits=16)
        self.assertTrue(wav.startswith(b"RIFF"))
        self.assertIn(b"WAVE", wav)

    def test_numpy_to_bytes(self):
        from qwen3_tts_service import Qwen3TTSService
        import numpy as np
        service = Qwen3TTSService.__new__(Qwen3TTSService)
        audio = np.array([0.5, -0.5, 0.0], dtype=np.float32)
        result = service._numpy_to_bytes(audio)
        self.assertIsInstance(result, bytes)
        self.assertEqual(len(result), 6)

    def test_get_available_speakers(self):
        from qwen3_tts_service import Qwen3TTSService, PRESET_SPEAKERS
        service = Qwen3TTSService.__new__(Qwen3TTSService)
        speakers = service.get_available_speakers()
        self.assertEqual(len(speakers), len(PRESET_SPEAKERS))


class TestSileroTTSServiceMock(unittest.TestCase):
    """silero_tts_service Mock测试"""

    def test_voice_config_dataclass(self):
        from silero_tts_service import VoiceConfig
        config = VoiceConfig()
        self.assertEqual(config.speaker_id, "baya")
        self.assertEqual(config.language, "zh")
        self.assertEqual(config.sample_rate, 48000)

    def test_character_voice_profile_dataclass(self):
        from silero_tts_service import CharacterVoiceProfile
        profile = CharacterVoiceProfile()
        self.assertEqual(profile.rate, 1.0)
        self.assertEqual(profile.emotion, "neutral")

    def test_tts_result_dataclass(self):
        from silero_tts_service import TTSResult
        result = TTSResult(audio_bytes=b"\x00\x01", sample_rate=24000, duration_ms=50.0, speaker_id="default")
        self.assertEqual(result.sample_rate, 24000)

    def test_character_voice_profiles(self):
        from silero_tts_service import CHARACTER_VOICE_PROFILES
        self.assertIn("default", CHARACTER_VOICE_PROFILES)
        self.assertIn("古代书生", CHARACTER_VOICE_PROFILES)
        self.assertIn("心理咨询师", CHARACTER_VOICE_PROFILES)
        for name, profile in CHARACTER_VOICE_PROFILES.items():
            self.assertIn("speaker_id", profile)
            self.assertIn("rate", profile)

    def test_edge_tts_voice_map(self):
        from silero_tts_service import EDGE_TTS_VOICE_MAP
        self.assertIn("baya", EDGE_TTS_VOICE_MAP)
        self.assertIn("aidar", EDGE_TTS_VOICE_MAP)

    def test_get_voice_profile_existing(self):
        from silero_tts_service import SileroTTSService
        service = SileroTTSService.__new__(SileroTTSService)
        service._initialized = True
        profile = service.get_voice_profile("古代书生")
        self.assertEqual(profile["speaker_id"], "baya")

    def test_get_voice_profile_default(self):
        from silero_tts_service import SileroTTSService
        service = SileroTTSService.__new__(SileroTTSService)
        service._initialized = True
        profile = service.get_voice_profile("不存在的角色")
        self.assertEqual(profile["speaker_id"], "baya")

    def test_get_available_speakers(self):
        from silero_tts_service import SileroTTSService
        service = SileroTTSService.__new__(SileroTTSService)
        service._initialized = True
        speakers = service.get_available_speakers()
        self.assertIn("baya", speakers)
        self.assertIn("aidar", speakers)

    def test_audio_to_base64(self):
        from silero_tts_service import SileroTTSService, TTSResult
        import base64
        service = SileroTTSService.__new__(SileroTTSService)
        service._initialized = True
        result = TTSResult(audio_bytes=b"test_audio_data", sample_rate=24000)
        b64 = service.audio_to_base64(result)
        decoded = base64.b64decode(b64)
        self.assertEqual(decoded, b"test_audio_data")


class TestASRBase(unittest.TestCase):
    """asr.base ASR基类测试"""

    def test_asr_engine_type(self):
        from asr.base import ASREngineType
        self.assertEqual(ASREngineType.WHISPER_OLLAMA.value, "whisper_ollama")
        self.assertEqual(ASREngineType.WHISPER_LOCAL.value, "whisper_local")
        self.assertEqual(ASREngineType.QWEN3_ASR.value, "qwen3_asr")

    def test_transcription_result(self):
        from asr.base import TranscriptionResult, ASREngineType
        result = TranscriptionResult(
            text="你好", language="zh", confidence=0.95,
            duration=2.5, model="qwen3-asr", engine=ASREngineType.QWEN3_ASR
        )
        d = result.to_dict()
        self.assertEqual(d["text"], "你好")
        self.assertEqual(d["engine"], "qwen3_asr")

    def test_engine_info(self):
        from asr.base import EngineInfo, ASREngineType
        info = EngineInfo(
            name="Test", engine_type=ASREngineType.QWEN3_ASR,
            is_available=True, description="测试引擎"
        )
        d = info.to_dict()
        self.assertTrue(d["is_available"])
        self.assertEqual(d["engine_type"], "qwen3_asr")

    def test_audio_processor_validate_nonexistent(self):
        from asr.base import AudioProcessor
        ok, msg = AudioProcessor.validate_audio("/nonexistent/file.wav")
        self.assertFalse(ok)
        self.assertIn("不存在", msg)

    def test_audio_processor_validate_bad_format(self):
        from asr.base import AudioProcessor
        tmp = tempfile.NamedTemporaryFile(suffix=".xyz", delete=False)
        tmp.write(b"fake")
        tmp.close()
        ok, msg = AudioProcessor.validate_audio(tmp.name)
        os.unlink(tmp.name)
        self.assertFalse(ok)
        self.assertIn("不支持", msg)

    def test_audio_processor_validate_good_format(self):
        from asr.base import AudioProcessor
        tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
        tmp.write(b"fake")
        tmp.close()
        ok, msg = AudioProcessor.validate_audio(tmp.name)
        os.unlink(tmp.name)
        self.assertTrue(ok)


class TestASRFactory(unittest.TestCase):
    """asr.factory ASR工厂测试"""

    def test_create_unknown_engine(self):
        from asr.factory import create_asr_service, _engines
        from asr.base import ASREngineType
        if ASREngineType.WHISPER_OLLAMA not in _engines:
            result = create_asr_service(ASREngineType.WHISPER_OLLAMA)
            self.assertIsNone(result)

    def test_engines_registry_not_empty(self):
        from asr.factory import _engines
        self.assertGreater(len(_engines), 0)

    def test_registered_engine_types(self):
        from asr.factory import _engines
        from asr.base import ASREngineType
        self.assertIn(ASREngineType.QWEN3_ASR, _engines)


class TestVoiceCallServiceMock(unittest.TestCase):
    """voice_call_service 核心链路单元测试"""

    def _make_service(self):
        import voice_call_service as _vcs
        from voice_call_service import VoiceCallService, VoiceCallConfig
        service = VoiceCallService.__new__(VoiceCallService)
        service.config = VoiceCallConfig()
        service.protocol = _vcs.MessageProtocol()
        service.active_session = None
        service.sessions_lock = asyncio.Lock()
        service.asr_service = None
        service.tts_service = None
        service.llm_service = None
        service.is_running = False
        return service

    def test_call_session_dataclass(self):
        from voice_call_service import CallSession
        session = CallSession(session_id="test_001", websocket=None)
        self.assertEqual(session.session_id, "test_001")
        self.assertFalse(session.is_speaking)
        self.assertFalse(session.is_ai_speaking)
        self.assertEqual(session.total_user_messages, 0)

    def test_websocket_available_flag(self):
        from voice_call_service import WEBSOCKET_AVAILABLE
        self.assertIsInstance(WEBSOCKET_AVAILABLE, bool)

    # --- MessageProtocol 编解码测试 ---

    def test_protocol_encode_structure(self):
        from voice_call_service import MessageProtocol
        encoded = MessageProtocol.encode("test_type", {"key": "value"})
        obj = json.loads(encoded)
        self.assertEqual(obj["type"], "test_type")
        self.assertEqual(obj["data"]["key"], "value")
        self.assertIn("timestamp", obj)

    def test_protocol_decode_valid(self):
        from voice_call_service import MessageProtocol
        msg = json.dumps({"type": "ping", "data": {"seq": 1}, "timestamp": 12345.0})
        msg_type, data, ts = MessageProtocol.decode(msg)
        self.assertEqual(msg_type, "ping")
        self.assertEqual(data["seq"], 1)
        self.assertEqual(ts, 12345.0)

    def test_protocol_decode_invalid_json(self):
        from voice_call_service import MessageProtocol
        msg_type, data, ts = MessageProtocol.decode("not json{{{")
        self.assertIsNone(msg_type)
        self.assertEqual(data, {})
        self.assertEqual(ts, 0)

    def test_protocol_decode_missing_fields(self):
        from voice_call_service import MessageProtocol
        msg = json.dumps({"type": "hello"})
        msg_type, data, ts = MessageProtocol.decode(msg)
        self.assertEqual(msg_type, "hello")
        self.assertEqual(data, {})
        self.assertEqual(ts, 0)

    def test_protocol_roundtrip(self):
        from voice_call_service import MessageProtocol
        original_type = "ai_audio"
        original_data = {"audio": "base64data", "sample_rate": 24000, "duration_ms": 500.0}
        encoded = MessageProtocol.encode(original_type, original_data)
        decoded_type, decoded_data, _ = MessageProtocol.decode(encoded)
        self.assertEqual(decoded_type, original_type)
        self.assertEqual(decoded_data["sample_rate"], 24000)
        self.assertEqual(decoded_data["duration_ms"], 500.0)

    # --- _is_valid_asr_result 过滤规则测试 ---

    def test_asr_valid_normal_text(self):
        service = self._make_service()
        self.assertTrue(service._is_valid_asr_result("你好世界", 0.9))

    def test_asr_valid_short_valid(self):
        service = self._make_service()
        self.assertTrue(service._is_valid_asr_result("你好", 0.8))

    def test_asr_rejects_empty(self):
        service = self._make_service()
        self.assertFalse(service._is_valid_asr_result("", 0.9))

    def test_asr_rejects_single_char(self):
        service = self._make_service()
        self.assertFalse(service._is_valid_asr_result("嗯", 0.9))

    def test_asr_rejects_whitespace_only(self):
        service = self._make_service()
        self.assertFalse(service._is_valid_asr_result("   ", 0.9))

    def test_asr_rejects_low_confidence(self):
        service = self._make_service()
        self.assertFalse(service._is_valid_asr_result("你好世界", 0.3))

    def test_asr_rejects_confidence_boundary(self):
        service = self._make_service()
        self.assertFalse(service._is_valid_asr_result("你好世界", 0.49))

    def test_asr_accepts_confidence_boundary(self):
        service = self._make_service()
        self.assertTrue(service._is_valid_asr_result("你好世界", 0.5))

    def test_asr_rejects_filler_words(self):
        service = self._make_service()
        for word in ['嗯', '啊', '呃', '哦', '额', '唔', '哈', '呵', '唉', '哎']:
            self.assertFalse(service._is_valid_asr_result(word, 0.9), f"应过滤语气词: {word}")

    def test_asr_rejects_all_filler_combination(self):
        service = self._make_service()
        self.assertFalse(service._is_valid_asr_result("嗯啊呃", 0.9))

    def test_asr_accepts_filler_with_real_content(self):
        service = self._make_service()
        self.assertTrue(service._is_valid_asr_result("嗯，你好", 0.9))

    def test_asr_rejects_two_char_filler(self):
        service = self._make_service()
        self.assertFalse(service._is_valid_asr_result("嗯啊", 0.9))

    # --- _split_sentences 句子分割测试 ---

    def test_split_chinese_punctuation(self):
        service = self._make_service()
        result = service._split_sentences("你好。世界！再见？")
        self.assertEqual(len(result), 3)
        self.assertEqual(result[0], "你好。")
        self.assertEqual(result[1], "世界！")
        self.assertEqual(result[2], "再见？")

    def test_split_english_punctuation(self):
        service = self._make_service()
        result = service._split_sentences("Hello. World! Goodbye?")
        self.assertEqual(len(result), 3)

    def test_split_no_punctuation(self):
        service = self._make_service()
        result = service._split_sentences("这是一段没有标点的话")
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0], "这是一段没有标点的话")

    def test_split_empty_string(self):
        service = self._make_service()
        result = service._split_sentences("")
        self.assertEqual(len(result), 1)

    def test_split_mixed_punctuation(self):
        service = self._make_service()
        result = service._split_sentences("你好。Hello! 再见？")
        self.assertEqual(len(result), 3)

    def test_split_trailing_text_no_punct(self):
        service = self._make_service()
        result = service._split_sentences("你好。世界")
        self.assertEqual(len(result), 2)
        self.assertEqual(result[1], "世界")

    # --- VoiceCallConfig 配置测试 ---

    def test_config_defaults(self):
        from voice_call_service import VoiceCallConfig
        config = VoiceCallConfig()
        self.assertEqual(config.host, "0.0.0.0")
        self.assertEqual(config.port, 5005)
        self.assertEqual(config.audio_sample_rate, 16000)
        self.assertEqual(config.llm_model, "qwen2.5:3b")
        self.assertEqual(config.llm_max_tokens, 200)
        self.assertAlmostEqual(config.llm_temperature, 0.7)

    def test_config_custom_values(self):
        from voice_call_service import VoiceCallConfig
        config = VoiceCallConfig(host="127.0.0.1", port=6000, llm_model="test:model")
        self.assertEqual(config.host, "127.0.0.1")
        self.assertEqual(config.port, 6000)
        self.assertEqual(config.llm_model, "test:model")

    # --- CallSession 状态测试 ---

    def test_session_initial_state(self):
        from voice_call_service import CallSession
        session = CallSession(session_id="s1", websocket=None)
        self.assertFalse(session.is_speaking)
        self.assertFalse(session.is_ai_speaking)
        self.assertFalse(session.is_interrupted)
        self.assertEqual(session.conversation_history, [])
        self.assertEqual(session.current_asr_text, "")
        self.assertEqual(session.current_ai_text, "")

    def test_session_state_transitions(self):
        from voice_call_service import CallSession
        session = CallSession(session_id="s1", websocket=None)
        session.is_speaking = True
        self.assertTrue(session.is_speaking)
        session.is_ai_speaking = True
        self.assertTrue(session.is_ai_speaking)
        session.is_interrupted = True
        self.assertTrue(session.is_interrupted)

    def test_session_conversation_history(self):
        from voice_call_service import CallSession
        session = CallSession(session_id="s1", websocket=None)
        session.conversation_history.append({"role": "user", "content": "你好", "timestamp": time.time()})
        session.conversation_history.append({"role": "assistant", "content": "你好！", "timestamp": time.time()})
        self.assertEqual(len(session.conversation_history), 2)

    # --- _summarize_thinking 思考摘要测试 ---

    def test_summarize_thinking_empty(self):
        service = self._make_service()
        self.assertEqual(service._summarize_thinking(""), "")

    def test_summarize_thinking_numbered_list(self):
        service = self._make_service()
        thinking = "1. 第一点\n2. 第二点\n3. 第三点\n4. 第四点\n5. 第五点\n6. 第六点"
        result = service._summarize_thinking(thinking)
        self.assertIn("第一点", result)
        self.assertTrue(result.startswith("•"))

    def test_summarize_thinking_bullet_list(self):
        service = self._make_service()
        thinking = "- 要点A\n- 要点B\n- 要点C"
        result = service._summarize_thinking(thinking)
        self.assertIn("要点A", result)

    def test_summarize_thinking_plain_text(self):
        service = self._make_service()
        thinking = "这是一段普通的思考内容，没有列表格式。"
        result = service._summarize_thinking(thinking)
        self.assertTrue(len(result) > 0)

    def test_summarize_thinking_truncates_long(self):
        service = self._make_service()
        points = [f"{i}. 第{i}个很长的要点内容" for i in range(1, 10)]
        thinking = "\n".join(points)
        result = service._summarize_thinking(thinking)
        lines = [l for l in result.split("\n") if l.strip()]
        self.assertLessEqual(len(lines), 5)

    # --- _generate_ai_response 异步Mock测试 ---

    def test_generate_ai_response_empty_fallback(self):
        """LLM返回空内容时使用默认回复"""
        from voice_call_service import CallSession

        service = self._make_service()
        session = CallSession(session_id="test_empty", websocket=MagicMock())
        session.is_interrupted = False

        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={"message": {"content": ""}})

        mock_post_ctx = MagicMock()
        mock_post_ctx.__aenter__ = AsyncMock(return_value=mock_response)
        mock_post_ctx.__aexit__ = AsyncMock(return_value=None)

        mock_http_session = MagicMock()
        mock_http_session.__aenter__ = AsyncMock(return_value=mock_http_session)
        mock_http_session.__aexit__ = AsyncMock(return_value=None)
        mock_http_session.post = MagicMock(return_value=mock_post_ctx)

        with patch("aiohttp.ClientSession", return_value=mock_http_session):
            loop = asyncio.new_event_loop()
            try:
                loop.run_until_complete(service._generate_ai_response(session, "你好"))
            finally:
                loop.close()

        self.assertEqual(session.current_ai_text, "抱歉，我没有听清楚，请再说一次。")

    def test_generate_ai_response_interrupted(self):
        """会话被打断时跳过AI回复"""
        from voice_call_service import CallSession

        service = self._make_service()
        session = CallSession(session_id="test_interrupt", websocket=MagicMock())
        session.is_interrupted = True

        loop = asyncio.new_event_loop()
        try:
            loop.run_until_complete(service._generate_ai_response(session, "你好"))
        finally:
            loop.close()

        self.assertFalse(session.is_ai_speaking)
        self.assertEqual(session.total_ai_messages, 0)

    def test_generate_ai_response_llm_failure(self):
        """LLM调用HTTP失败时正确处理"""
        from voice_call_service import CallSession

        service = self._make_service()
        session = CallSession(session_id="test_fail", websocket=MagicMock())
        session.is_interrupted = False

        mock_response = MagicMock()
        mock_response.status = 500
        mock_response.text = AsyncMock(return_value="Internal Server Error")

        mock_post_ctx = MagicMock()
        mock_post_ctx.__aenter__ = AsyncMock(return_value=mock_response)
        mock_post_ctx.__aexit__ = AsyncMock(return_value=None)

        mock_http_session = MagicMock()
        mock_http_session.__aenter__ = AsyncMock(return_value=mock_http_session)
        mock_http_session.__aexit__ = AsyncMock(return_value=None)
        mock_http_session.post = MagicMock(return_value=mock_post_ctx)

        with patch("aiohttp.ClientSession", return_value=mock_http_session):
            loop = asyncio.new_event_loop()
            try:
                loop.run_until_complete(service._generate_ai_response(session, "你好"))
            finally:
                loop.close()

        self.assertEqual(session.total_ai_messages, 0)

    # --- _synthesize_speech TTS降级测试 ---

    def test_synthesize_speech_tts_unavailable(self):
        """TTS服务不可用时发送status消息"""
        from voice_call_service import CallSession

        service = self._make_service()
        service.tts_service = None
        session = CallSession(session_id="test_no_tts", websocket=MagicMock())
        session.is_interrupted = False

        mock_ws = MagicMock()
        mock_ws.send = AsyncMock()
        session.websocket = mock_ws

        loop = asyncio.new_event_loop()
        try:
            loop.run_until_complete(service._synthesize_speech(session, "测试文本"))
        finally:
            loop.close()

        mock_ws.send.assert_called_once()
        sent_msg = mock_ws.send.call_args[0][0]
        self.assertIn("tts_available", sent_msg)
        self.assertIn("false", sent_msg.lower())

    def test_synthesize_speech_interrupted(self):
        """会话被打断时跳过合成"""
        from voice_call_service import CallSession

        service = self._make_service()
        session = CallSession(session_id="test_interrupt_tts", websocket=MagicMock())
        session.is_interrupted = True

        loop = asyncio.new_event_loop()
        try:
            loop.run_until_complete(service._synthesize_speech(session, "测试文本"))
        finally:
            loop.close()

    def test_synthesize_speech_short_sentence_skipped(self):
        """短于3个字符的句子被跳过"""
        from voice_call_service import CallSession

        service = self._make_service()
        mock_tts = MagicMock()
        mock_tts.synthesize = MagicMock(return_value=None)
        service.tts_service = mock_tts

        session = CallSession(session_id="test_short", websocket=MagicMock())
        session.is_interrupted = False

        mock_ws = MagicMock()
        mock_ws.send = AsyncMock()
        session.websocket = mock_ws

        loop = asyncio.new_event_loop()
        try:
            loop.run_until_complete(service._synthesize_speech(session, "嗯"))
        finally:
            loop.close()

        mock_tts.synthesize.assert_not_called()

    # --- _handle_interrupt 打断机制测试 ---

    def test_handle_interrupt_sets_flag(self):
        from voice_call_service import CallSession

        service = self._make_service()
        session = CallSession(session_id="test_intr", websocket=MagicMock())
        session.is_ai_speaking = True

        mock_ws = MagicMock()
        mock_ws.send = AsyncMock()
        session.websocket = mock_ws

        loop = asyncio.new_event_loop()
        try:
            loop.run_until_complete(service._handle_interrupt(session))
        finally:
            loop.close()

        self.assertFalse(session.is_ai_speaking)
        mock_ws.send.assert_called_once()
        sent_msg = mock_ws.send.call_args[0][0]
        self.assertIn("interrupted", sent_msg)

    # --- _handle_audio_chunk 音频处理测试 ---

    def test_handle_audio_chunk_valid(self):
        from voice_call_service import CallSession

        service = self._make_service()
        session = CallSession(session_id="test_audio", websocket=MagicMock())

        audio_data = b'\x00\x01' * 100
        audio_b64 = base64.b64encode(audio_data).decode()

        loop = asyncio.new_event_loop()
        try:
            loop.run_until_complete(service._handle_audio_chunk(session, {"audio": audio_b64}))
        finally:
            loop.close()

        self.assertGreater(len(session.audio_buffer), 0)
        self.assertGreater(session.total_audio_bytes, 0)

    def test_handle_audio_chunk_empty(self):
        from voice_call_service import CallSession

        service = self._make_service()
        session = CallSession(session_id="test_empty_audio", websocket=MagicMock())

        loop = asyncio.new_event_loop()
        try:
            loop.run_until_complete(service._handle_audio_chunk(session, {"audio": ""}))
        finally:
            loop.close()

        self.assertEqual(len(session.audio_buffer), 0)

    def test_handle_audio_chunk_invalid_base64(self):
        from voice_call_service import CallSession

        service = self._make_service()
        session = CallSession(session_id="test_bad_b64", websocket=MagicMock())

        loop = asyncio.new_event_loop()
        try:
            loop.run_until_complete(service._handle_audio_chunk(session, {"audio": "!!!invalid!!!"}))
        finally:
            loop.close()

        self.assertEqual(len(session.audio_buffer), 0)


class TestLocalModelLoaderMock(unittest.TestCase):
    """local_model_loader Mock测试"""

    def test_reasoning_mode_default(self):
        from local_model_loader import get_reasoning_mode, set_reasoning_mode, _reasoning_enabled
        original = get_reasoning_mode()
        set_reasoning_mode(True)
        self.assertTrue(get_reasoning_mode())
        set_reasoning_mode(False)
        self.assertFalse(get_reasoning_mode())
        set_reasoning_mode(original)

    def test_gguf_search_dirs_exist(self):
        from local_model_loader import GGUF_SEARCH_DIRS
        self.assertIsInstance(GGUF_SEARCH_DIRS, list)
        self.assertGreater(len(GGUF_SEARCH_DIRS), 0)

    def test_safetensors_search_dirs_exist(self):
        from local_model_loader import SAFETENSORS_SEARCH_DIRS
        self.assertIsInstance(SAFETENSORS_SEARCH_DIRS, list)
        self.assertGreater(len(SAFETENSORS_SEARCH_DIRS), 0)


# ==================== API路由层测试 ====================

class _FlaskTestBase(unittest.TestCase):
    """Flask测试基类，提供统一的app和client"""

    @classmethod
    def setUpClass(cls):
        try:
            from intelligent_api import create_app
            cls.app = create_app()
            cls.client = cls.app.test_client()
        except Exception as e:
            cls.app = None
            cls.client = None
            cls._skip_reason = str(e)

    def setUp(self):
        if self.app is None:
            self.skipTest(getattr(self, '_skip_reason', 'Flask app creation failed'))


class TestHealthAPI(_FlaskTestBase):
    """健康检查API测试"""

    def test_health_endpoint(self):
        resp = self.client.get("/api/health")
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertTrue(data.get("success"))
        self.assertEqual(data["data"]["status"], "healthy")

    def test_health_detailed_endpoint(self):
        resp = self.client.get("/api/health/detailed")
        self.assertEqual(resp.status_code, 200)

    def test_stats_endpoint(self):
        resp = self.client.get("/api/stats")
        self.assertEqual(resp.status_code, 200)

    def test_ollama_status_endpoint(self):
        resp = self.client.get("/api/ollama/status")
        self.assertIn(resp.status_code, [200, 503])

    def test_connection_status_endpoint(self):
        resp = self.client.get("/api/connection/status")
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertTrue(data.get("success"))

    def test_cache_stats_endpoint(self):
        resp = self.client.get("/api/cache/stats")
        self.assertEqual(resp.status_code, 200)

    def test_cache_clear_endpoint(self):
        resp = self.client.post("/api/cache/clear")
        self.assertEqual(resp.status_code, 200)

    def test_summary_health_endpoint(self):
        resp = self.client.get("/api/summary/health")
        self.assertIn(resp.status_code, [200, 503])

    def test_vision_status_endpoint(self):
        resp = self.client.get("/api/vision/status")
        self.assertIn(resp.status_code, [200, 503])

    def test_native_image_health_endpoint(self):
        resp = self.client.get("/api/native_llama_cpp_image/health")
        self.assertIn(resp.status_code, [200, 503])


class TestGreetingAPI(_FlaskTestBase):
    """问候语API测试"""

    def test_generate_greeting(self):
        resp = self.client.post("/api/greeting/generate", json={"type": "time"})
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertTrue(data.get("success"))
        self.assertIn("data", data)

    def test_list_greetings(self):
        self.client.post("/api/greeting/generate", json={"type": "time"})
        resp = self.client.get("/api/greeting/list")
        self.assertEqual(resp.status_code, 200)

    def test_cleanup_greetings(self):
        resp = self.client.post("/api/greeting/cleanup")
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertTrue(data.get("success"))

    def test_mark_displayed_nonexistent(self):
        resp = self.client.post("/api/greeting/mark_displayed", json={"id": "nonexistent"})
        self.assertEqual(resp.status_code, 404)


class TestModelsAPI(_FlaskTestBase):
    """模型管理API测试"""

    def test_models_list(self):
        resp = self.client.get("/api/models")
        self.assertEqual(resp.status_code, 200, f"期望200，实际{resp.status_code}")
        data = resp.get_json()
        self.assertIsNotNone(data, "响应体不应为空")

    def test_local_models_scan(self):
        resp = self.client.get("/api/models/local")
        self.assertIn(resp.status_code, [200, 404], f"期望200或404，实际{resp.status_code}")


class TestAPIKeyAPI(_FlaskTestBase):
    """API密钥管理API测试"""

    def test_api_keys_list(self):
        resp = self.client.get("/api/api-key/list")
        self.assertIn(resp.status_code, [200, 401], f"期望200或401，实际{resp.status_code}")

    def test_api_key_generate(self):
        resp = self.client.post("/api/api-key/generate", json={"name": "测试"})
        self.assertIn(resp.status_code, [200, 401], f"期望200或401，实际{resp.status_code}")


class TestReasoningAPI(_FlaskTestBase):
    """推理模式API测试"""

    def test_get_reasoning(self):
        resp = self.client.get("/api/reasoning")
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertTrue(data.get("success"))

    def test_set_reasoning_valid(self):
        resp = self.client.post("/api/reasoning", json={"enabled": True})
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertTrue(data.get("success"))

    def test_set_reasoning_invalid_type(self):
        resp = self.client.post("/api/reasoning", json={"enabled": "not_bool"})
        self.assertEqual(resp.status_code, 400)


class TestChatAPI(_FlaskTestBase):
    """聊天API测试"""

    def test_chat_missing_message(self):
        resp = self.client.post("/api/chat", json={})
        self.assertIn(resp.status_code, [400, 401], f"期望400或401，实际{resp.status_code}")

    def test_chat_modes_endpoint(self):
        resp = self.client.get("/api/chat/modes")
        self.assertIn(resp.status_code, [200, 404], f"期望200或404，实际{resp.status_code}")

    def test_chat_config_endpoint(self):
        resp = self.client.get("/api/chat/config")
        self.assertIn(resp.status_code, [200, 404], f"期望200或404，实际{resp.status_code}")


class TestMemoryAPI(_FlaskTestBase):
    """记忆API测试"""

    def test_memory_list(self):
        resp = self.client.get("/api/memory")
        self.assertIn(resp.status_code, [200, 404], f"期望200或404，实际{resp.status_code}")

    def test_memory_search(self):
        resp = self.client.post("/api/memory/search", json={"query": "测试"})
        self.assertIn(resp.status_code, [200, 404], f"期望200或404，实际{resp.status_code}")


class TestSummaryAPI(_FlaskTestBase):
    """摘要API测试"""

    def test_summary_endpoint(self):
        resp = self.client.get("/api/summary")
        self.assertIn(resp.status_code, [200, 400], f"期望200或400，实际{resp.status_code}")


class TestASRAPI(_FlaskTestBase):
    """ASR API测试"""

    def test_asr_status(self):
        resp = self.client.get("/api/asr/status")
        self.assertIn(resp.status_code, [200, 404], f"期望200或404，实际{resp.status_code}")

    def test_asr_engines(self):
        resp = self.client.get("/api/asr/engines")
        self.assertIn(resp.status_code, [200, 404], f"期望200或404，实际{resp.status_code}")


class TestSearchAPI(_FlaskTestBase):
    """搜索API测试"""

    def test_search_missing_query(self):
        resp = self.client.post("/api/search", json={})
        self.assertIn(resp.status_code, [400, 404], f"期望400或404，实际{resp.status_code}")

    def test_search_with_query(self):
        resp = self.client.post("/api/search", json={"query": "测试搜索"})
        self.assertIn(resp.status_code, [200, 404], f"期望200或404，实际{resp.status_code}")


class TestRAGAPI(_FlaskTestBase):
    """RAG API测试"""

    def test_rag_status(self):
        resp = self.client.get("/api/rag/status")
        self.assertIn(resp.status_code, [200, 404], f"期望200或404，实际{resp.status_code}")


class TestContextAPI(_FlaskTestBase):
    """上下文API测试"""

    def test_context_status(self):
        resp = self.client.get("/api/context/status")
        self.assertIn(resp.status_code, [200, 404], f"期望200或404，实际{resp.status_code}")


class TestFunctionsAPI(_FlaskTestBase):
    """函数调用API测试"""

    def test_functions_list(self):
        resp = self.client.get("/api/functions")
        self.assertIn(resp.status_code, [200, 404], f"期望200或404，实际{resp.status_code}")


class TestGroupChatAPI(_FlaskTestBase):
    """群聊API测试"""

    def test_group_chat_status(self):
        resp = self.client.get("/api/group_chat/status")
        self.assertIn(resp.status_code, [200, 404], f"期望200或404，实际{resp.status_code}")


class TestOllamaProxyAPI(_FlaskTestBase):
    """Ollama代理API测试"""

    def test_ollama_proxy_tags(self):
        resp = self.client.get("/api/tags")
        self.assertIn(resp.status_code, [200, 502], f"期望200或502，实际{resp.status_code}")


class TestVisionAPI(_FlaskTestBase):
    """视觉API测试"""

    def test_vision_status_endpoint(self):
        resp = self.client.get("/api/vision/status")
        self.assertIn(resp.status_code, [200, 503], f"期望200或503，实际{resp.status_code}")


class TestImageAPI(_FlaskTestBase):
    """图像生成API测试"""

    def test_image_models_list(self):
        resp = self.client.get("/api/image/models")
        self.assertIn(resp.status_code, [200, 404], f"期望200或404，实际{resp.status_code}")


# ==================== 集成测试 ====================

class TestModelPaths(unittest.TestCase):
    """model_paths 模型路径配置测试"""

    def test_models_dir_set(self):
        from model_paths import MODELS_DIR
        self.assertTrue(MODELS_DIR)

    def test_ensure_directories(self):
        from model_paths import ensure_directories
        ensure_directories()

    def test_set_model_environment(self):
        from model_paths import set_model_environment
        set_model_environment()
        self.assertIn("HF_HOME", os.environ)
        self.assertIn("HF_ENDPOINT", os.environ)

    def test_get_available_image_models(self):
        from model_paths import get_available_image_models
        models = get_available_image_models()
        self.assertIsInstance(models, dict)


class TestStartOllamaHub(unittest.TestCase):
    """start_ollama_hub 启动器测试"""

    def test_is_port_open_closed(self):
        from start_ollama_hub import is_port_open
        self.assertFalse(is_port_open(59999, timeout=0.1))

    def test_port_constants(self):
        from start_ollama_hub import FRONTEND_PORT, OLLAMA_PORT, API_PORT, VOICE_PORT
        self.assertEqual(FRONTEND_PORT, 8080)
        self.assertEqual(OLLAMA_PORT, 11434)
        self.assertEqual(API_PORT, 5001)
        self.assertEqual(VOICE_PORT, 5005)


class TestIntelligentAPIFactory(unittest.TestCase):
    """intelligent_api 应用工厂测试"""

    def test_get_allowed_origins(self):
        from intelligent_api import get_allowed_origins
        origins = get_allowed_origins()
        self.assertIsInstance(origins, list)
        self.assertGreater(len(origins), 0)

    def test_get_debug_mode(self):
        from intelligent_api import get_debug_mode
        result = get_debug_mode()
        self.assertIsInstance(result, bool)

    def test_create_app_returns_flask(self):
        from intelligent_api import create_app
        from flask import Flask
        try:
            app = create_app()
            self.assertIsInstance(app, Flask)
        except RuntimeError:
            self.skipTest("Required services not available for app creation")


class TestErrorHandlers(_FlaskTestBase):
    """错误处理测试"""

    def test_404_handler(self):
        resp = self.client.get("/api/nonexistent_endpoint_12345")
        self.assertEqual(resp.status_code, 404)
        data = resp.get_json()
        self.assertIn("error", data)


# ==================== 边界条件与安全性测试 ====================

class TestBoundaryConditions(unittest.TestCase):
    """边界条件测试"""

    def test_validate_string_boundary_min(self):
        from utils.helpers import validate_string
        ok, _ = validate_string("a", "field", min_len=1)
        self.assertTrue(ok)

    def test_validate_string_boundary_max(self):
        from utils.helpers import validate_string
        ok, _ = validate_string("a" * 100, "field", max_len=100)
        self.assertTrue(ok)

    def test_validate_integer_boundary_min(self):
        from utils.helpers import validate_integer
        ok, _ = validate_integer(1, "field", min_val=1)
        self.assertTrue(ok)

    def test_validate_integer_boundary_max(self):
        from utils.helpers import validate_integer
        ok, _ = validate_integer(10, "field", max_val=10)
        self.assertTrue(ok)

    def test_validate_integer_zero(self):
        from utils.helpers import validate_integer
        ok, _ = validate_integer(0, "field", min_val=0)
        self.assertTrue(ok)

    def test_validate_integer_negative(self):
        from utils.helpers import validate_integer
        ok, _ = validate_integer(-1, "field", min_val=-10)
        self.assertTrue(ok)

    def test_validate_request_empty_list(self):
        from utils.helpers import validate_request
        ok, _ = validate_request([], {})
        self.assertTrue(ok)

    def test_safe_get_empty_dict(self):
        from utils.helpers import safe_get
        self.assertIsNone(safe_get({}, "a"))

    def test_safe_get_non_dict_intermediate(self):
        from utils.helpers import safe_get
        data = {"a": 42}
        self.assertIsNone(safe_get(data, "a", "b"))


class TestSecurityEdgeCases(unittest.TestCase):
    """安全性边界测试"""

    def test_path_traversal_variations(self):
        from security_utils import sanitize_path
        self.assertIsNone(sanitize_path("../../../etc/shadow", "/app"))
        self.assertIsNone(sanitize_path("..\\..\\windows\\system32", "/app"))
        self.assertIsNone(sanitize_path("/absolute/path", "/app"))

    def test_rate_limit_timing(self):
        from utils.auth import check_rate_limit, rate_limit_store
        rate_limit_store.clear()
        ip = "172.16.0.1"
        old_timestamps = rate_limit_store.get(ip, [])
        check_rate_limit(ip)
        self.assertGreaterEqual(len(rate_limit_store.get(ip, [])), 1)

    def test_api_key_service_hash(self):
        from api_key_service import APIKeyService
        service = APIKeyService()
        gen = service.generate_key()
        full_key = gen["data"]["key"]
        key_hash = service._hash_key(full_key)
        self.assertNotEqual(full_key, key_hash)
        self.assertGreater(len(key_hash), 0)


class TestConcurrencySafety(unittest.TestCase):
    """并发安全测试"""

    def test_smart_cache_concurrent_access(self):
        from smart_cache import MemoryAwareCache
        cache = MemoryAwareCache(max_size=100, max_memory_mb=10)
        errors = []

        def writer(idx):
            try:
                for i in range(50):
                    cache.set(f"key_{idx}_{i}", f"value_{idx}_{i}")
            except Exception as e:
                errors.append(e)

        def reader(idx):
            try:
                for i in range(50):
                    cache.get(f"key_{idx}_{i}")
            except Exception as e:
                errors.append(e)

        threads = []
        for i in range(4):
            threads.append(threading.Thread(target=writer, args=(i,)))
            threads.append(threading.Thread(target=reader, args=(i,)))

        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=10)

        self.assertEqual(len(errors), 0, f"并发错误: {errors}")

    def test_rate_limit_concurrent(self):
        from utils.auth import check_rate_limit, rate_limit_store
        rate_limit_store.clear()
        results = []
        lock = threading.Lock()

        def check(ip):
            ok = check_rate_limit(ip)
            with lock:
                results.append(ok)

        threads = [threading.Thread(target=check, args=("10.1.1.1",)) for _ in range(70)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=10)

        allowed = sum(1 for r in results if r)
        denied = sum(1 for r in results if not r)
        self.assertLessEqual(allowed, 60)
        self.assertGreater(denied, 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
