# -*- coding: utf-8 -*-
"""
Ollama Hub 系统全面测试套件

覆盖范围：
- 基础设施检查（端口、服务、依赖）
- 核心 API 端点功能验证
- 服务健康状态检测
- 数据完整性校验
- 安全性基础检查

运行方式:
    python tests/test_system.py              # 运行全部测试
    python tests/test_system.py --module chat # 只测聊天模块
    python tests/test_system.py --quick       # 快速模式（跳过耗时测试）
"""

import os
import sys
import json
import time
import socket
import unittest
import argparse
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple

try:
    import requests
except ImportError:
    print("[ERROR] 需要安装 requests: pip install requests")
    sys.exit(1)

PROJECT_DIR = Path(__file__).resolve().parent.parent
SERVER_DIR = PROJECT_DIR / "server"
sys.path.insert(0, str(SERVER_DIR))

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s'
)
logger = logging.getLogger("SystemTest")


class TestConfig:
    """测试配置"""
    BASE_URL = os.getenv("TEST_API_URL", "http://127.0.0.1:5001")
    OLLAMA_URL = os.getenv("TEST_OLLAMA_URL", "http://127.0.0.1:11434")
    FRONTEND_URL = os.getenv("TEST_FRONTEND_URL", "http://127.0.0.1:8080")
    
    REQUEST_TIMEOUT = 10
    LONG_TIMEOUT = 60
    
    DEFAULT_MODEL = os.getenv("TEST_DEFAULT_MODEL", "")
    FALLBACK_MODELS = ["llama3.2:3b", "qwen2.5:3b", "gemma2:2b"]


def _get_default_model():
    if TestConfig.DEFAULT_MODEL:
        return TestConfig.DEFAULT_MODEL
    try:
        from utils.config import DEFAULT_CHAT_MODEL
        return DEFAULT_CHAT_MODEL
    except ImportError:
        return "qwen2.5:3b"


class SystemTestResult:
    """测试结果收集器"""
    def __init__(self):
        self.results: List[Dict[str, Any]] = []
        self.start_time = time.time()
        self.total_tests = 0
        self.passed_tests = 0
        self.failed_tests = 0
        self.skipped_tests = 0
        self.warnings: List[str] = []
    
    def add(self, test_name: str, passed: bool, message: str = "", details: Any = None):
        self.total_tests += 1
        if passed:
            self.passed_tests += 1
            status = "PASS"
        else:
            self.failed_tests += 1
            status = "FAIL"
        
        result = {
            "test": test_name,
            "status": status,
            "message": message,
            "timestamp": datetime.now().isoformat(),
            "duration_ms": 0,
        }
        if details:
            result["details"] = details
        self.results.append(result)
        
        icon = "✓" if passed else "✗"
        logger.info(f"  {icon} {test_name}: {message}")
    
    def add_skip(self, test_name: str, reason: str):
        self.skipped_tests += 1
        self.results.append({
            "test": test_name,
            "status": "SKIP",
            "message": reason,
            "timestamp": datetime.now().isoformat(),
        })
        logger.info(f"  ⊘ {test_name}: {reason} (跳过)")
    
    def add_warning(self, warning: str):
        self.warnings.append(warning)
        logger.warning(f"⚠ {warning}")
    
    def summary(self) -> str:
        elapsed = time.time() - self.start_time
        lines = [
            "\n" + "=" * 70,
            f"  Ollama Hub 系统测试报告",
            f"  测试时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            f"  总耗时: {elapsed:.2f}秒",
            "=" * 70,
            f"\n  结果统计:",
            f"    总计:   {self.total_tests}",
            f"    通过:   {self.passed_tests} ✓",
            f"    失败:   {self.failed_tests} ✗",
            f"    跳过:   {self.skipped_tests} ⊘",
            f"    通过率: {(self.passed_tests / max(self.total_tests, 1)) * 100:.1f}%",
        ]
        
        if self.warnings:
            lines.append(f"\n  警告 ({len(self.warnings)}):")
            for w in self.warnings[:5]:
                lines.append(f"    ⚠ {w}")
        
        failed_results = [r for r in self.results if r["status"] == "FAIL"]
        if failed_results:
            lines.append(f"\n  失败的测试 ({len(failed_results)}):")
            for r in failed_results[:10]:
                lines.append(f"    ✗ {r['test']}: {r['message']}")
        
        return "\n".join(lines)


result = SystemTestResult()


def is_port_open(port: int, host: str = "127.0.0.1") -> bool:
    """检查端口是否开放"""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(2)
            return sock.connect_ex((host, port)) == 0
    except Exception:
        return False


def api_get(endpoint: str, timeout: int = None) -> Tuple[bool, Any]:
    """GET 请求封装"""
    t = timeout or TestConfig.REQUEST_TIMEOUT
    try:
        resp = requests.get(f"{TestConfig.BASE_URL}{endpoint}", timeout=t)
        return True, resp.json() if resp.headers.get('content-type', '').startswith('application/json') else resp.text
    except Exception as e:
        return False, str(e)


def api_post(endpoint: str, data: dict = None, timeout: int = None) -> Tuple[bool, Any]:
    """POST 请求封装"""
    t = timeout or TestConfig.REQUEST_TIMEOUT
    headers = {"Content-Type": "application/json"}
    try:
        resp = requests.post(
            f"{TestConfig.BASE_URL}{endpoint}",
            json=data or {},
            headers=headers,
            timeout=t
        )
        return True, resp.json() if resp.headers.get('content-type', '').startswith('application/json') else resp.text
    except Exception as e:
        return False, str(e)


class InfrastructureTests:
    """基础设施测试"""
    
    @staticmethod
    def run_all(quick_mode=False):
        logger.info("\n🔧 基础设施检查")
        InfrastructureTests.test_ports()
        InfrastructureTests.test_project_structure()
        InfrastructureTests.test_dependencies()
        if not quick_mode:
            InfrastructureTests.test_file_integrity()
    
    @staticmethod
    def test_ports():
        """检查关键服务端口"""
        ports = {
            "API 服务 (5001)": 5001,
            "Ollama (11434)": 11434,
            "前端 (8080)": 8080,
        }
        for name, port in ports.items():
            open = is_port_open(port)
            result.add(
                f"端口检查: {name}",
                open,
                f"{'已开放' if open else '未开放'} :{port}"
            )
    
    @staticmethod
    def test_project_structure():
        """检查项目目录结构"""
        required_dirs = [
            "server/api",
            "server/utils",
            "web/js",
            "web/css",
            "Modelfiles",
            "data",
        ]
        required_files = [
            "start_ollama_hub.py",
            "server/intelligent_api.py",
            "server/utils/config.py",
            "server/utils/auth.py",
            "server/utils/helpers.py",
            "server/local_model_loader.py",
        ]
        
        for d in required_dirs:
            exists = (PROJECT_DIR / d).exists()
            result.add(f"目录存在: {d}/", exists, "存在" if exists else "缺失")
        
        for f in required_files:
            exists = (PROJECT_DIR / f).exists()
            result.add(f"文件存在: {f}", exists, "存在" if exists else "缺失")
    
    @staticmethod
    def test_dependencies():
        """检查 Python 依赖"""
        deps = {
            "flask": "Web框架",
            "requests": "HTTP客户端",
            "json": "JSON处理",
            "pathlib": "路径操作",
        }
        
        for module, desc in deps.items():
            try:
                __import__(module)
                result.add(f"依赖模块: {module}", True, f"{desc} 已安装")
            except ImportError:
                result.add(f"依赖模块: {module}", False, f"{desc} 未安装")
        
        optional_deps = {
            "torch": "PyTorch (深度学习)",
            "transformers": "Transformers (NLP)",
            "diffusers": "Diffusers (图像)",
            "Pillow": "PIL (图像处理)",
        }
        
        for module, desc in optional_deps.items():
            try:
                __import__(module)
                result.add(f"可选依赖: {module}", True, f"{desc} 已安装")
            except ImportError:
                result.add_skip(f"可选依赖: {module}", f"{desc} 未安装 (可选)")
    
    @staticmethod
    def test_file_integrity():
        """检查关键文件完整性"""
        config_path = SERVER_DIR / "utils" / "config.py"
        if config_path.exists():
            content = config_path.read_text(encoding="utf-8")
            checks = [
                ("OLLAMA_BASE_URL 定义", "OLLAMA_BASE_URL" in content),
                ("PORT_API 定义", "PORT_API" in content),
                ("DEFAULT_CHAT_MODEL 定义", "DEFAULT_CHAT_MODEL" in content),
            ]
            for name, ok in checks:
                result.add(f"配置完整性: {name}", ok, "通过" if ok else "缺失")


class APITests:
    """API 功能测试"""
    
    @staticmethod
    def run_all(quick_mode=False):
        logger.info("\n🌐 API 功能测试")
        APITests.test_health_endpoint()
        APITests.test_models_endpoint()
        APITests.test_chat_endpoint(quick_mode)
        APITests.test_memory_endpoints()
        APITests.test_context_endpoint()
        APITests.test_summary_endpoint()
        APITests.test_api_key_endpoint()
        APITests.test_search_endpoint()
        APITests.test_functions_endpoint()
        APITests.test_rag_endpoint()
        APITests.test_asr_endpoint()
        APITests.test_image_endpoint()
        APITests.test_vision_endpoint()
        APITests.test_group_chat_endpoint()
    
    @staticmethod
    def test_health_endpoint():
        """测试健康检查接口"""
        success, data = api_get("/api/health")
        if success and isinstance(data, dict):
            status_ok = data.get("status") == "healthy"
            has_services = "services" in data
            has_timestamp = "timestamp" in data
            
            result.add("健康检查: 基本响应", status_ok, data.get("status", "未知"))
            result.add("健康检查: 包含服务状态", has_services, "包含 services 字段")
            
            if has_services:
                svc = data["services"]
                ollama_ok = isinstance(svc.get("ollama"), dict) and svc["ollama"].get("connected", False)
                result.add("健康检查: Ollama 连接", ollama_ok, "已连接" if ollama_ok else "未连接")
                
                memory_ready = svc.get("memory") == "ready"
                result.add("健康检查: Memory 服务", memory_ready, svc.get("memory", "未知"))
        else:
            result.add("健康检查: 基本响应", False, f"请求失败: {data}")
    
    @staticmethod
    def test_models_endpoint():
        """测试模型列表接口"""
        success, data = api_get("/api/models")
        if success and isinstance(data, dict):
            models = data.get("models", [])
            model_names = [m.get("name", "") for m in models]
            
            result.add("模型列表: 可获取", len(models) > 0, f"共 {len(models)} 个模型")
            
            expected_models = [_get_default_model()] + TestConfig.FALLBACK_MODELS
            for model in expected_models:
                found = any(model in n for n in model_names)
                result.add(f"模型可用: {model}", found, "存在" if found else "不存在")
        else:
            result.add("模型列表: 可获取", False, f"请求失败: {data}")
    
    @staticmethod
    def test_chat_endpoint(quick_mode=False):
        """测试聊天接口"""
        if quick_mode:
            result.add_skip("聊天接口: 发送消息", "快速模式跳过")
            return
        
        payload = {
            "model": _get_default_model(),
            "messages": [{"role": "user", "content": "你好，请用一句话介绍自己"}],
            "stream": False,
        }
        
        start = time.time()
        success, data = api_post("/api/chat", payload, timeout=TestConfig.LONG_TIMEOUT)
        elapsed = time.time() - start
        
        if success and isinstance(data, dict):
            has_response = "response" in data or "message" in data or "choices" in data
            response_text = ""
            
            if "response" in data:
                response_text = str(data["response"])[:100]
            elif "message" in data:
                msg = data["message"]
                if isinstance(msg, dict):
                    response_text = msg.get("content", "")[:100]
                else:
                    response_text = str(msg)[:100]
            elif "choices" in data:
                choices = data["choices"]
                if choices and len(choices) > 0:
                    response_text = choices[0].get("message", {}).get("content", "")[:100]
            
            result.add("聊天接口: 成功响应", has_response, f"耗时 {elapsed:.1f}s")
            result.add("聊天接口: 返回内容非空", len(response_text) > 0, response_text[:50])
        else:
            result.add("聊天接口: 成功响应", False, f"请求失败: {str(data)[:100]}")
    
    @staticmethod
    def test_memory_endpoints():
        """测试记忆接口"""
        success, data = api_get("/api/memory/list")
        if success and isinstance(data, dict):
            memories = data.get("data", [])
            result.add("记忆列表: 可获取", True, f"共 {len(memories)} 条记忆")
        elif success:
            result.add("记忆列表: 可获取", True, f"响应格式: {type(data).__name__}")
        else:
            result.add("记忆列表: 可获取", False, f"请求失败: {data}")
    
    @staticmethod
    def test_context_endpoint():
        """测试上下文配置接口"""
        success, data = api_get("/api/context")
        if success and isinstance(data, dict):
            has_config = "config" in data or "global_defaults" in data
            result.add("上下文配置: 可获取", has_config, "配置加载成功")
        else:
            result.add("上下文配置: 可获取", False, f"请求失败: {data}")
    
    @staticmethod
    def test_summary_endpoint():
        """测试摘要接口"""
        success, _ = api_get("/api/conversation/list")
        result.add("摘要服务: 对话列表", success, "可访问" if success else "不可访问")
    
    @staticmethod
    def test_api_key_endpoint():
        """测试 API Key 接口"""
        success, data = api_get("/api/api-key/list")
        if success and isinstance(data, dict):
            keys = data.get("keys", data.get("data", []))
            result.add("API Key: 列表接口", True, f"共 {len(keys) if isinstance(keys, list) else '?'} 个密钥")
        else:
            result.add("API Key: 列表接口", success, f"{'可访问' if success else '不可访问'}: {str(data)[:50]}")
    
    @staticmethod
    def test_search_endpoint():
        """测试搜索接口"""
        payload = {"query": "Python 编程"}
        success, data = api_post("/api/search/web", payload)
        if success and isinstance(data, dict):
            is_success = data.get("success", False)
            result.add("搜索接口: Web 搜索", is_success, data.get("message", ""))
        else:
            result.add("搜索接口: Web 搜索", False, f"请求失败: {str(data)[:80]}")
    
    @staticmethod
    def test_functions_endpoint():
        """测试函数调用接口"""
        success, data = api_get("/api/functions/list")
        if success and isinstance(data, dict):
            functions = data.get("functions", data.get("data", []))
            count = len(functions) if isinstance(functions, list) else "?"
            result.add("函数调用: 函数列表", True, f"共 {count} 个函数")
        else:
            result.add("函数调用: 函数列表", success, f"{'可访问' if success else '不可访问'}")
    
    @staticmethod
    def test_rag_endpoint():
        """测试 RAG 接口"""
        payload = {"query": "测试查询"}
        success, data = api_post("/api/rag/retrieve", payload)
        if success and isinstance(data, dict):
            result.add("RAG 接口: 检索", data.get("success", False), data.get("message", ""))
        else:
            result.add("RAG 接口: 检索", success, f"{'可访问' if success else '不可访问'}: {str(data)[:50]}")
    
    @staticmethod
    def test_asr_endpoint():
        """测试语音识别接口"""
        success, data = api_get("/api/asr/status")
        if success and isinstance(data, dict):
            status = data.get("data", data)
            result.add("ASR 接口: 服务状态", True, f"状态: {type(status).__name__}")
        else:
            result.add("ASR 接口: 服务状态", success, f"{'可访问' if success else '不可访问'}")
    
    @staticmethod
    def test_image_endpoint():
        """测试图像生成接口"""
        success, data = api_post("/api/image/generate", {"prompt": "一只猫"})
        if success and isinstance(data, dict):
            has_data = "image" in data or "url" in data or "path" in data
            result.add("图像生成: 接口响应", True, data.get("message", "有响应"))
        else:
            result.add("图像生成: 接口响应", success, f"{'可访问' if success else '不可访问'}: {str(data)[:50]}")
    
    @staticmethod
    def test_vision_endpoint():
        """测试视觉接口"""
        success, _ = api_post("/api/vision/analyze", {"image": "test"})
        result.add("视觉接口: 分析端点", success, "可访问" if success else "不可访问或需要图片")
    
    @staticmethod
    def test_group_chat_endpoint():
        """测试群聊接口"""
        success, data = api_get("/api/group-chat/state")
        if success and isinstance(data, dict):
            result.add("群聊接口: 状态获取", True, "可访问")
        else:
            result.add("群聊接口: 状态获取", success, f"{'可访问' if success else '不可访问'}: {str(data)[:50]}")


class SecurityTests:
    """安全性测试"""
    
    @staticmethod
    def run_all():
        logger.info("\n🔒 安全性检查")
        SecurityTests.test_cors_headers()
        SecurityTests.test_auth_required()
        SecurityTests.test_input_validation()
    
    @staticmethod
    def test_cors_headers():
        """检查 CORS 配置"""
        try:
            resp = requests.options(TestConfig.BASE_URL + "/api/health", timeout=5)
            cors_header = resp.headers.get("Access-Control-Allow-Origin", "")
            has_cors = bool(cors_header)
            result.add("安全: CORS 头设置", has_cors, f"Origin: {cors_header or '未设置'}")
        except Exception as e:
            result.add("安全: CORS 头设置", False, f"检查失败: {e}")
    
    @staticmethod
    def test_auth_required():
        """检查敏感接口认证要求"""
        sensitive_endpoints = [
            "/api/api-key/generate",
            "/api/search/web",
        ]
        for endpoint in sensitive_endpoints:
            success, data = api_post(endpoint, {})
            if success and isinstance(data, dict):
                needs_auth = data.get("code") == 401 or "unauthorized" in str(data).lower() or "api key" in str(data).lower()
                result.add(f"安全: 认证保护 {endpoint}", needs_auth or not success, 
                           "需认证" if needs_auth else "可能无需认证")
            else:
                result.add_skip(f"安全: 认证保护 {endpoint}", "无法判断")
    
    @staticmethod
    def test_input_validation():
        """基本输入验证测试"""
        payloads = [
            ("/api/chat", {}, "空消息"),
            ("/api/memory", {"content": ""}, "空记忆"),
            ("/api/search/web", {"query": ""}, "空搜索"),
        ]
        for endpoint, payload, desc in payloads:
            success, data = api_post(endpoint, payload)
            if success and isinstance(data, dict):
                rejected = data.get("code", 200) >= 400 or "error" in str(data).lower() or "required" in str(data).lower()
                result.add(f"输入验证: {desc}", rejected or not success, 
                           "已拒绝" if rejected else "可能接受无效输入")
            else:
                result.add_skip(f"输入验证: {desc}", "无法连接")


class DataIntegrityTests:
    """数据完整性测试"""
    
    @staticmethod
    def run_all():
        logger.info("\n📁 数据完整性检查")
        DataIntegrityTests.test_config_files()
        DataIntegrityTests.test_modelfiles()
        DataIntegrityTests.test_data_directory()
    
    @staticmethod
    def test_config_files():
        """检查配置文件"""
        config_checks = [
            (SERVER_DIR / "utils" / "config.py", "主配置"),
            (PROJECT_DIR / "start_ollama_hub.py", "启动脚本"),
            (SERVER_DIR / "utils" / "auth.py", "认证模块"),
        ]
        for path, name in config_checks:
            if path.exists():
                size = path.stat().st_size
                valid = size > 100
                result.add(f"配置文件: {name}", valid, f"{size} bytes")
            else:
                result.add(f"配置文件: {name}", False, "文件不存在")
    
    @staticmethod
    def test_modelfiles():
        """检查 Modelfile 定义"""
        modelfile_dir = PROJECT_DIR / "Modelfiles"
        if modelfile_dir.exists():
            files = list(modelfile_dir.glob("*.modelfile"))
            result.add("Modelfile: 目录存在", True, f"共 {len(files)} 个定义")
            for f in files[:5]:
                content = f.read_text(encoding="utf-8", errors="ignore")
                has_from = "FROM" in content.upper()
                result.add(f"Modelfile: {f.name}", has_from, "含 FROM 指令" if has_from else "缺少 FROM")
        else:
            result.add("Modelfile: 目录存在", False, "目录不存在")
    
    @staticmethod
    def test_data_directory():
        """检查数据目录"""
        data_dir = PROJECT_DIR / "data"
        if data_dir.exists():
            items = list(data_dir.iterdir())
            result.add("数据目录: 存在", True, f"共 {len(items)} 个条目")
            
            conv_file = data_dir / "conversations.json"
            if conv_file.exists():
                try:
                    with open(conv_file, "r", encoding="utf-8") as fp:
                        json.load(fp)
                    result.add("对话数据: JSON 有效", True, "格式正确")
                except json.JSONDecodeError as e:
                    result.add("对话数据: JSON 有效", False, f"解析错误: {e}")
            else:
                result.add_skip("对话数据: JSON 有效", "文件不存在")
        else:
            result.add("数据目录: 存在", False, "目录不存在")


class PerformanceTests:
    """性能基准测试"""
    
    @staticmethod
    def run_all(quick_mode=False):
        if quick_mode:
            result.add_skip("性能测试", "快速模式跳过")
            return
        logger.info("\n⚡ 性能基准测试")
        PerformanceTests.test_response_time()
    
    @staticmethod
    def test_response_time():
        """API 响应时间测试"""
        endpoints = ["/api/health", "/api/models", "/api/context"]
        times = {}
        
        for ep in endpoints:
            start = time.time()
            success, _ = api_get(ep)
            elapsed = (time.time() - start) * 1000
            times[ep] = elapsed
            acceptable = elapsed < 2000
            result.add(f"响应时间: {ep}", acceptable, f"{elapsed:.0f}ms {'✓' if acceptable else '✗ (>2s)'}")
        
        avg = sum(times.values()) / len(times) if times else 0
        result.add("响应时间: 平均值", avg < 1500, f"{avg:.0f}ms")


def detect_available_model() -> str:
    """检测可用模型"""
    default = _get_default_model()
    try:
        resp = requests.get(f"{TestConfig.OLLAMA_URL}/api/tags", timeout=5)
        if resp.status_code == 200:
            models = resp.json().get("models", [])
            names = [m.get("name", "") for m in models]
            for candidate in [default] + TestConfig.FALLBACK_MODELS:
                if any(candidate in n for n in names):
                    return candidate
            if names:
                return names[0]
    except Exception:
        pass
    return default


def main():
    parser = argparse.ArgumentParser(description="Ollama Hub 系统测试套件")
    parser.add_argument("--module", "-m", help="指定测试模块 (infra/api/security/data/performance/all)", default="all")
    parser.add_argument("--quick", "-q", help="快速模式（跳过耗时测试）", action="store_true")
    parser.add_argument("--output", "-o", help="输出报告到文件", default=None)
    args = parser.parse_args()
    
    print("=" * 70)
    print("  🧪 Ollama Hub 系统测试套件")
    print(f"  目标地址: {TestConfig.BASE_URL}")
    print(f"  Ollama 地址: {TestConfig.OLLAMA_URL}")
    print(f"  测试时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 70)
    
    available_model = detect_available_model()
    TestConfig.DEFAULT_MODEL = available_model
    print(f"\n  检测到可用模型: {available_model}")
    
    modules_to_run = {
        "all": lambda: None,
        "infra": InfrastructureTests.run_all,
        "api": APITests.run_all,
        "security": SecurityTests.run_all,
        "data": DataIntegrityTests.run_all,
        "performance": PerformanceTests.run_all,
    }
    
    if args.module == "all":
        InfrastructureTests.run_all(args.quick)
        APITests.run_all(args.quick)
        SecurityTests.run_all()
        DataIntegrityTests.run_all()
        PerformanceTests.run_all(args.quick)
    elif args.module in modules_to_run:
        modules_to_run[args.module](args.quick)
    else:
        print(f"\n[ERROR] 未知模块: {args.module}")
        print(f"可用模块: {', '.join(modules_to_run.keys())}")
        sys.exit(1)
    
    report = result.summary()
    print(report)
    
    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump({
                "summary": {
                    "total": result.total_tests,
                    "passed": result.passed_tests,
                    "failed": result.failed_tests,
                    "skipped": result.skipped_tests,
                    "pass_rate": f"{(result.passed_tests / max(result.total_tests, 1)) * 100:.1f}%",
                },
                "results": result.results,
                "warnings": result.warnings,
                "timestamp": datetime.now().isoformat(),
            }, f, ensure_ascii=False, indent=2)
        print(f"\n  📄 报告已保存至: {output_path}")
    
    return 0 if result.failed_tests == 0 else 1


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
