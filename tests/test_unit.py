"""单元测试"""
import sys, os, unittest
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "server"))

from utils.config import DEFAULT_CHAT_MODEL


class TestAuthInternalCall(unittest.TestCase):
    """测试内部调用认证放行"""
    def test_internal_header(self):
        from utils.auth import require_api_key
        from functools import wraps
        from flask import Flask, request, jsonify

        app = Flask(__name__)

        @app.route("/test")
        @require_api_key
        def test_route():
            return jsonify({"ok": True})

        client = app.test_client()
        resp = client.post("/test", headers={"X-Internal-Call": "true", "X-Forwarded-For": "127.0.0.1"})
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertEqual(data.get("ok"), True)


class TestLocalModelLoader(unittest.TestCase):
    """测试本地模型加载器"""
    def test_gguf_model_path_exists(self):
        from local_model_loader import get_gguf_model_path, get_available_gguf_models
        models = get_available_gguf_models()
        if not models:
            self.skipTest("没有可用的GGUF模型")
        first_model = models[0]["name"]
        path = get_gguf_model_path(first_model)
        self.assertIsNotNone(path)
        self.assertTrue(os.path.exists(path))
        self.assertGreater(len(models), 0)


class TestChatAPI(unittest.TestCase):
    """测试聊天 API"""
    def test_backend_chat(self):
        import requests
        resp = requests.post(
            "http://localhost:5001/api/chat",
            json={"message": "hi", "model": DEFAULT_CHAT_MODEL, "stream": False},
            headers={"X-Internal-Call": "true"},
            timeout=120
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data.get("code"), 200)
        self.assertIsNotNone(data.get("data", {}).get("response"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
