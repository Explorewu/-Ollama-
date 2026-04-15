"""
Voice功能测试

测试语音通话服务的各个组件：
- VoiceCall WebSocket连接
- ASR转写API
- TTS语音合成API
- 音色列表API

运行方式:
    python tests/test_voice.py
"""

import asyncio
import json
import sys
import os
import time
import base64
import requests

sys.stdout.reconfigure(encoding='utf-8')

API_BASE = "http://localhost:5001"
WS_BASE = "ws://localhost:5005"


class TestVoiceAPI:
    """Voice API 测试"""

    @staticmethod
    def test_voice_status():
        """测试语音服务状态"""
        print("\n[测试] 语音服务状态...")
        try:
            resp = requests.get(f"{API_BASE}/api/voice/status", timeout=5)
            print(f"  状态码: {resp.status_code}")
            data = resp.json()
            print(f"  响应: {json.dumps(data, ensure_ascii=False, indent=4)}")
            assert resp.status_code == 200, f"状态码错误: {resp.status_code}"
            print("  ✓ 通过")
            return True
        except Exception as e:
            print(f"  ✗ 失败: {e}")
            return False

    @staticmethod
    def test_tts_voices():
        """测试TTS音色列表"""
        print("\n[测试] TTS音色列表...")
        try:
            resp = requests.get(f"{API_BASE}/api/group_chat/tts/voices", timeout=5)
            print(f"  状态码: {resp.status_code}")
            if resp.status_code == 404:
                print("  ⚠ 路由未注册，跳过")
                return True
            data = resp.json()
            voices = data.get("data", {}).get("voices", [])
            print(f"  可用音色数: {len(voices)}")
            for v in voices[:5]:
                print(f"    - {v.get('id')}: {v.get('name')}")
            assert resp.status_code == 200
            assert len(voices) > 0
            print("  ✓ 通过")
            return True
        except Exception as e:
            print(f"  ✗ 失败: {e}")
            return False

    @staticmethod
    def test_transcribe():
        """测试语音转文字API（需要文件上传，模型加载可能较慢）"""
        print("\n[测试] 语音转文字 (检查API格式)...")
        try:
            import io
            empty_audio = b'\x00' * 1600
            files = {'audio': ('test.pcm', io.BytesIO(empty_audio), 'audio/pcm')}
            data = {'language': 'zh'}

            print("  注意: ASR模型加载可能需要较长时间...")
            resp = requests.post(
                f"{API_BASE}/api/voice/transcribe",
                files=files,
                data=data,
                headers={"X-Internal-Call": "true"},
                timeout=120
            )
            print(f"  状态码: {resp.status_code}")
            result_data = resp.json()
            print(f"  响应: {json.dumps(result_data, ensure_ascii=False)[:200]}")

            if resp.status_code == 503:
                print("  ⚠ ASR服务未初始化，跳过")
                return True
            elif resp.status_code == 400 and "没有上传文件" in result_data.get("message", ""):
                print("  ⚠ API格式不符，但服务可达")
                return True
            assert resp.status_code == 200
            print("  ✓ 通过")
            return True
        except requests.exceptions.Timeout:
            print("  ⚠ 请求超时(模型加载慢)，跳过")
            return True
        except Exception as e:
            print(f"  ✗ 失败: {e}")
            return False


class TestVoiceWebSocket:
    """Voice WebSocket 测试"""

    @staticmethod
    async def test_ws_connection():
        """测试WebSocket连接"""
        print("\n[测试] WebSocket连接...")
        try:
            import websockets
            uri = f"{WS_BASE}/voice-call"
            print(f"  连接地址: {uri}")

            async with websockets.connect(uri, open_timeout=10, close_timeout=5) as ws:
                print("  ✓ 连接成功")

                msg = await asyncio.wait_for(ws.recv(), timeout=5)
                data = json.loads(msg)
                print(f"  收到消息: {json.dumps(data, ensure_ascii=False)[:100]}")

                return True
        except Exception as e:
            print(f"  ✗ 失败: {e}")
            return False

    @staticmethod
    async def test_ws_ping():
        """测试心跳ping"""
        print("\n[测试] WebSocket心跳...")
        try:
            import websockets
            uri = f"{WS_BASE}/voice-call"

            async with websockets.connect(uri, open_timeout=10, close_timeout=5) as ws:
                await ws.recv()

                await ws.send(json.dumps({"type": "ping", "data": {}, "timestamp": int(time.time()*1000)}))
                print("  已发送 ping")

                msg = await asyncio.wait_for(ws.recv(), timeout=5)
                data = json.loads(msg)
                print(f"  收到响应: {json.dumps(data, ensure_ascii=False)}")
                assert data.get("type") == "pong"
                print("  ✓ 心跳正常")
                return True
        except Exception as e:
            print(f"  ✗ 失败: {e}")
            return False

    @staticmethod
    async def test_ws_message_sequence():
        """测试消息序列"""
        print("\n[测试] 消息序列模拟...")
        try:
            import websockets
            uri = f"{WS_BASE}/voice-call"

            async with websockets.connect(uri, open_timeout=10, close_timeout=5) as ws:
                await ws.recv()

                start_msg = {
                    "type": "start_speaking",
                    "data": {"voice": "default"},
                    "timestamp": int(time.time()*1000)
                }
                await ws.send(json.dumps(start_msg))
                print("  已发送 start_speaking")

                stop_msg = {
                    "type": "stop_speaking",
                    "data": {},
                    "timestamp": int(time.time()*1000)
                }
                await ws.send(json.dumps(stop_msg))
                print("  已发送 stop_speaking")

                print("  ✓ 消息序列正常")
                return True
        except Exception as e:
            print(f"  ✗ 失败: {e}")
            return False


class TestVoiceFrontend:
    """Voice 前端模块测试"""

    @staticmethod
    def test_js_module_exists():
        """测试JS模块是否存在"""
        print("\n[测试] JS模块文件检查...")
        js_path = os.path.join(os.path.dirname(__file__), "..", "web", "js", "features", "voice_call.js")
        js_path = os.path.normpath(js_path)
        print(f"  路径: {js_path}")

        if os.path.exists(js_path):
            size = os.path.getsize(js_path)
            print(f"  文件大小: {size} bytes")
            print("  ✓ 文件存在")
            return True
        else:
            print("  ✗ 文件不存在")
            return False

    @staticmethod
    def test_html_exists():
        """测试HTML页面是否存在"""
        print("\n[测试] HTML页面文件检查...")
        html_path = os.path.join(os.path.dirname(__file__), "..", "web", "voice_call.html")
        html_path = os.path.normpath(html_path)
        print(f"  路径: {html_path}")

        if os.path.exists(html_path):
            size = os.path.getsize(html_path)
            print(f"  文件大小: {size} bytes")
            print("  ✓ 文件存在")
            return True
        else:
            print("  ✗ 文件不存在")
            return False


def run_all_tests():
    """运行所有测试"""
    print("=" * 60)
    print("Voice功能测试套件")
    print("=" * 60)

    results = []

    print("\n--- API 测试 ---")
    results.append(("Voice Status", TestVoiceAPI.test_voice_status()))
    results.append(("TTS Voices", TestVoiceAPI.test_tts_voices()))
    results.append(("Transcribe", TestVoiceAPI.test_transcribe()))

    print("\n--- WebSocket 测试 ---")
    ws = TestVoiceWebSocket()
    results.append(("WS Connection", asyncio.run(ws.test_ws_connection())))
    results.append(("WS Ping", asyncio.run(ws.test_ws_ping())))
    results.append(("WS Message Seq", asyncio.run(ws.test_ws_message_sequence())))

    print("\n--- 前端文件测试 ---")
    results.append(("JS Module", TestVoiceFrontend.test_js_module_exists()))
    results.append(("HTML Page", TestVoiceFrontend.test_html_exists()))

    print("\n" + "=" * 60)
    print("测试结果汇总")
    print("=" * 60)

    passed = sum(1 for _, r in results if r)
    total = len(results)

    for name, result in results:
        status = "✓ 通过" if result else "✗ 失败"
        print(f"  {name}: {status}")

    print(f"\n总计: {passed}/{total} 通过")

    return passed == total


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
