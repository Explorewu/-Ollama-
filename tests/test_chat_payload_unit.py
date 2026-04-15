import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch


PROJECT_DIR = Path(__file__).resolve().parents[1]
SERVER_DIR = PROJECT_DIR / "server"
if str(SERVER_DIR) not in sys.path:
    sys.path.insert(0, str(SERVER_DIR))

from api.chat import _build_ollama_payload, _send_ollama_chat  # noqa: E402
from utils.config import DEFAULT_CHAT_RUNTIME_CONFIG, build_ollama_options  # noqa: E402


class ChatPayloadTests(unittest.TestCase):
    def test_build_ollama_options_excludes_num_thread(self):
        options = build_ollama_options(DEFAULT_CHAT_RUNTIME_CONFIG)

        self.assertNotIn("num_thread", options)
        self.assertEqual(options["num_ctx"], DEFAULT_CHAT_RUNTIME_CONFIG["num_ctx"])

    def test_build_ollama_payload_disables_thinking_by_default(self):
        payload = _build_ollama_payload(
            "qwen3.5:0.8b",
            [{"role": "user", "content": "hello"}],
            DEFAULT_CHAT_RUNTIME_CONFIG,
            False,
        )

        self.assertIn("think", payload)
        self.assertFalse(payload["think"])

    @patch("api.chat.requests.post")
    def test_send_ollama_chat_retries_when_only_thinking_is_returned(self, mock_post):
        first_response = MagicMock()
        first_response.raise_for_status.return_value = None
        first_response.json.return_value = {
            "message": {"content": "", "thinking": "long reasoning"},
            "done_reason": "length",
        }

        second_response = MagicMock()
        second_response.raise_for_status.return_value = None
        second_response.json.return_value = {
            "message": {"content": "success"},
            "done_reason": "stop",
        }

        mock_post.side_effect = [first_response, second_response]

        result, used_payload = _send_ollama_chat(
            {
                "model": "qwen3.5:0.8b",
                "messages": [{"role": "user", "content": "hello"}],
                "stream": False,
                "options": {"num_predict": 64},
                "think": True,
            }
        )

        self.assertEqual(result["message"]["content"], "success")
        self.assertFalse(used_payload["think"])
        self.assertEqual(mock_post.call_count, 2)

    @patch("api.chat.requests.post")
    def test_send_ollama_chat_respects_explicit_thinking_request(self, mock_post):
        response = MagicMock()
        response.raise_for_status.return_value = None
        response.json.return_value = {
            "message": {"content": "", "thinking": "long reasoning"},
            "done_reason": "length",
        }
        mock_post.return_value = response

        result, used_payload = _send_ollama_chat(
            {
                "model": "qwen3.5:0.8b",
                "messages": [{"role": "user", "content": "hello"}],
                "stream": False,
                "options": {"num_predict": 64},
                "think": True,
            },
            allow_thinking_retry=False,
        )

        self.assertEqual(result["message"]["thinking"], "long reasoning")
        self.assertTrue(used_payload["think"])
        self.assertEqual(mock_post.call_count, 1)


if __name__ == "__main__":
    unittest.main()
