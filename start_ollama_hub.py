#!/usr/bin/env python3
"""
Desktop launcher for Ollama Hub.

This launcher starts:
- Ollama on port 11434
- intelligent_api on port 5001
- voice_call_service on port 5005
- static frontend on port 8080
"""

from __future__ import annotations

import os
import socket
import subprocess
import sys
import time
import webbrowser
from http.server import SimpleHTTPRequestHandler
from pathlib import Path
from typing import Dict, List, Optional, Tuple

PROJECT_DIR = Path(__file__).resolve().parent
SERVER_DIR = PROJECT_DIR / "server"
WEB_DIR = PROJECT_DIR / "web"
LOG_DIR = PROJECT_DIR / "logs"

PYTHON_EXE = sys.executable or "python"
PYTHON_BG_EXE = PYTHON_EXE
if os.name == "nt":
    pythonw_candidate = Path(PYTHON_EXE).with_name("pythonw.exe")
    if pythonw_candidate.exists():
        PYTHON_BG_EXE = str(pythonw_candidate)
OLLAMA_EXE = PROJECT_DIR / "ollama.exe"

FRONTEND_PORT = 8080
OLLAMA_PORT = 11434
API_PORT = 5001
VOICE_PORT = 5005

CREATE_FLAGS = 0
if os.name == "nt":
    CREATE_FLAGS = subprocess.CREATE_NEW_PROCESS_GROUP


def is_port_open(port: int, host: str = "127.0.0.1", timeout: float = 0.5) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(timeout)
        return sock.connect_ex((host, port)) == 0


def wait_for_port(port: int, timeout: float = 20.0, host: str = "127.0.0.1") -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if is_port_open(port, host=host):
            return True
        time.sleep(0.5)
    return False


def ensure_logs() -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)


def launch_process(name: str, cmd: List[str], cwd: Path) -> subprocess.Popen:
    ensure_logs()
    stdout_path = LOG_DIR / f"{name}.out.log"
    stderr_path = LOG_DIR / f"{name}.err.log"
    stdout_file = open(stdout_path, "a", encoding="utf-8", errors="ignore")
    stderr_file = open(stderr_path, "a", encoding="utf-8", errors="ignore")
    return subprocess.Popen(
        cmd,
        cwd=str(cwd),
        stdout=stdout_file,
        stderr=stderr_file,
        creationflags=CREATE_FLAGS,
    )


def start_service(name: str, port: int, cmd: List[str], cwd: Path, timeout: float = 20.0) -> Tuple[str, Optional[subprocess.Popen]]:
    if is_port_open(port):
        return "already_running", None

    process = launch_process(name, cmd, cwd)
    if wait_for_port(port, timeout=timeout):
        return "started", process

    try:
        process.terminate()
    except Exception:
        pass
    return "failed", process


def open_browser() -> None:
    webbrowser.open(f"http://127.0.0.1:{FRONTEND_PORT}")


class NoCacheHttpHandler(SimpleHTTPRequestHandler):
    """Serve the frontend with no-store headers for HTML entrypoints."""

    def end_headers(self) -> None:
        if self.path.endswith(".html") or self.path in {"/", "/index.html"}:
            self.send_header("Cache-Control", "no-store, no-cache, must-revalidate, max-age=0")
            self.send_header("Pragma", "no-cache")
            self.send_header("Expires", "0")
        super().end_headers()


def print_status(results: Dict[str, str]) -> None:
    print("=" * 56)
    print("Ollama Hub launcher")
    print("=" * 56)
    for name, state in results.items():
        # 美化状态显示
        if state in ["started", "started_with_api", "already_running"]:
            status = "✓ 运行中"
        elif state == "failed":
            status = "✗ 失败"
        else:
            status = state
        print(f"{name:<18} {status}")
    print("-" * 56)
    print(f"Frontend: http://127.0.0.1:{FRONTEND_PORT}")
    print(f"API:      http://127.0.0.1:{API_PORT}")
    print(f"Voice WS: ws://127.0.0.1:{VOICE_PORT}/voice-call")
    print(f"Ollama:   http://127.0.0.1:{OLLAMA_PORT}")
    print(f"Logs:     {LOG_DIR}")


def main() -> int:
    results: Dict[str, str] = {}

    if not WEB_DIR.exists():
        print(f"[ERROR] Missing web directory: {WEB_DIR}")
        return 1

    if not is_port_open(OLLAMA_PORT):
        if not OLLAMA_EXE.exists():
            print(f"[ERROR] Ollama is not listening on {OLLAMA_PORT} and executable is missing: {OLLAMA_EXE}")
            return 1
        state, _ = start_service("ollama", OLLAMA_PORT, [str(OLLAMA_EXE), "serve"], PROJECT_DIR, timeout=12.0)
        results["ollama"] = state
        if state == "failed":
            print_status(results)
            return 1
    else:
        results["ollama"] = "already_running"

    state, _ = start_service(
        "intelligent_api",
        API_PORT,
        [PYTHON_BG_EXE, str(SERVER_DIR / "intelligent_api.py")],
        PROJECT_DIR,
        timeout=35.0,
    )
    results["intelligent_api"] = state
    if state == "failed":
        print_status(results)
        return 1

    # voice_call_service 已在 intelligent_api 中启动，只需检测端口
    if wait_for_port(VOICE_PORT, timeout=25.0):
        results["voice_call_service"] = "started_with_api"
    else:
        results["voice_call_service"] = "check_api_logs"

    state, _ = start_service(
        "frontend",
        FRONTEND_PORT,
        [
            PYTHON_BG_EXE,
            "-c",
            (
                "import functools, os; "
                "from socketserver import TCPServer; "
                "from start_ollama_hub import NoCacheHttpHandler; "
                f"os.chdir(r'{WEB_DIR}'); "
                f"TCPServer.allow_reuse_address = True; "
                f"handler = functools.partial(NoCacheHttpHandler, directory=r'{WEB_DIR}'); "
                f"httpd = TCPServer(('127.0.0.1', {FRONTEND_PORT}), handler); "
                "httpd.serve_forever()"
            ),
        ],
        PROJECT_DIR,
        timeout=8.0,
    )
    results["frontend"] = state
    if state == "failed":
        print_status(results)
        return 1

    print_status(results)

    if "--no-browser" not in sys.argv:
        try:
            open_browser()
        except Exception as exc:
            print(f"[WARN] Failed to open browser: {exc}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
